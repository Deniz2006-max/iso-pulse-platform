"""
İzin İş Mantığı Katmanı
- Bakiye kontrolü
- Talep oluşturma / güncelleme
- Otomatik iş günü hesabı
- E-posta bildirimi tetikleme
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from db.models import LeaveRequest, LeaveBalance, EmployeeProfile, Notification
from inpulse.leave.schemas import LeaveRequestCreate, ManagerDecision
from inpulse.leave.calculator import (
    yillik_izin_hakki, bakiyeden_dusurmeli, bakiye_hesapla, IZIN_TURLERI
)
from inpulse.leave.holidays import is_gunu_say, giris_tarihini_bul
from inpulse.leave.notifications import izin_bildir
import uuid


# ─── Bakiye sorgulama ────────────────────────────────────────────────────────
async def get_leave_balance(
    db: AsyncSession, employee_id: str, yil: int
) -> Optional[LeaveBalance]:
    stmt = select(LeaveBalance).where(
        and_(LeaveBalance.employee_id == employee_id, LeaveBalance.yil == yil)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def ensure_balance_row(
    db: AsyncSession, employee: EmployeeProfile, yil: int
) -> LeaveBalance:
    """Bakiye satırı yoksa kıdem bazlı olarak oluştur."""
    balance = await get_leave_balance(db, employee.id, yil)
    if balance:
        return balance

    hak = yillik_izin_hakki(employee.ise_giris_tarihi, yil)
    balance = LeaveBalance(
        id=str(uuid.uuid4()),
        employee_id=employee.id,
        yil=yil,
        onceki_yildan=Decimal("0"),
        yillik_hak=hak,
        idari_eklenen=Decimal("0"),
        kullanilan=Decimal("0"),
    )
    db.add(balance)
    await db.flush()
    return balance


# ─── İzin talebi oluşturma ──────────────────────────────────────────────────
async def create_leave_request(
    db: AsyncSession,
    employee_id: str,
    data: LeaveRequestCreate,
) -> LeaveRequest:
    # Çalışanı bul
    emp_result = await db.execute(
        select(EmployeeProfile).where(EmployeeProfile.id == employee_id)
    )
    employee = emp_result.scalar_one_or_none()
    if not employee:
        raise ValueError(f"Çalışan bulunamadı: {employee_id}")

    # İş günü sayısını hesapla
    sure_gun = Decimal(str(is_gunu_say(data.cikis_tarihi, data.giris_tarihi - __import__('datetime').timedelta(days=1))))

    # 2 saatlik izin özel durumu
    if data.izin_turu == "2saat":
        sure_gun = Decimal("0.27")   # 2h / 7.5h

    # Bakiye kontrolü (yıllık + 2saat_uzeri için)
    balance_id = None
    if bakiyeden_dusurmeli(data.izin_turu):
        balance = await ensure_balance_row(db, employee, data.cikis_tarihi.year)
        mevcut_bakiye = bakiye_hesapla(
            balance.onceki_yildan, balance.yillik_hak,
            balance.idari_eklenen, balance.kullanilan
        )
        if sure_gun > mevcut_bakiye:
            raise ValueError(
                f"Yetersiz izin bakiyesi. Mevcut: {mevcut_bakiye} gün, Talep: {sure_gun} gün"
            )
        balance_id = balance.id

    # Talebi kaydet
    talep = LeaveRequest(
        id=str(uuid.uuid4()),
        employee_id=employee_id,
        balance_id=balance_id,
        izin_turu=data.izin_turu,
        cikis_tarihi=data.cikis_tarihi,
        giris_tarihi=data.giris_tarihi,
        sure_gun=sure_gun,
        neden=data.neden,
        durum="beklemede",
        yonetici_id=employee.yonetici_id,
    )
    db.add(talep)
    await db.flush()

    # ── Yöneticiye uygulama içi bildirim ────────────────────────────────────
    if employee.yonetici_id:
        izin_label = IZIN_TURLERI.get(data.izin_turu, {}).get("label", data.izin_turu)
        notif = Notification(
            id=str(uuid.uuid4()),
            user_id=employee.yonetici_id,
            tur="leave_request",
            ilgili_leave_id=talep.id,
            mesaj=(
                f"{employee.ad_soyad} — {izin_label} talebi oluşturdu "
                f"({data.cikis_tarihi.strftime('%d.%m.%Y')} → {data.giris_tarihi.strftime('%d.%m.%Y')})"
            ),
        )
        db.add(notif)

    # ── Çalışana da bildirim (talep alındı) ─────────────────────────────────
    calisan_notif = Notification(
        id=str(uuid.uuid4()),
        user_id=employee_id,
        tur="leave_submitted",
        ilgili_leave_id=talep.id,
        mesaj=f"İzin talebiniz alındı ve yöneticinize iletildi.",
    )
    db.add(calisan_notif)

    # Yöneticiye bildirim e-postası
    if employee.yonetici_id and employee.email:
        try:
            yonetici_result = await db.execute(
                select(EmployeeProfile).where(EmployeeProfile.id == employee.yonetici_id)
            )
            yonetici = yonetici_result.scalar_one_or_none()
            if yonetici and yonetici.email:
                await izin_bildir(
                    kime=yonetici.email,
                    sablon="yeni_talep",
                    context={
                        "calisan": employee.ad_soyad,
                        "izin_turu": IZIN_TURLERI.get(data.izin_turu, {}).get("label", data.izin_turu),
                        "cikis": data.cikis_tarihi.strftime("%d.%m.%Y"),
                        "giris": data.giris_tarihi.strftime("%d.%m.%Y"),
                        "sure": str(sure_gun),
                        "talep_id": talep.id,
                    }
                )
        except Exception:
            pass   # Bildirim hatası talebi engellemez

    await db.refresh(talep)
    return talep


# ─── İzin talebi listesi ────────────────────────────────────────────────────
async def list_employee_requests(
    db: AsyncSession, employee_id: str, yil: Optional[int] = None
) -> list[LeaveRequest]:
    conditions = [LeaveRequest.employee_id == employee_id]
    if yil:
        from sqlalchemy import extract
        conditions.append(extract("year", LeaveRequest.cikis_tarihi) == yil)

    stmt = select(LeaveRequest).where(and_(*conditions)).order_by(LeaveRequest.olusturma.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def list_pending_for_manager(
    db: AsyncSession, yonetici_id: str
) -> list[LeaveRequest]:
    stmt = (
        select(LeaveRequest)
        .where(and_(
            LeaveRequest.yonetici_id == yonetici_id,
            LeaveRequest.durum == "beklemede"
        ))
        .order_by(LeaveRequest.olusturma.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ─── Yönetici kararı ─────────────────────────────────────────────────────────
async def apply_manager_decision(
    db: AsyncSession,
    talep_id: str,
    yonetici_id: str,
    karar: ManagerDecision,
) -> LeaveRequest:
    talep_result = await db.execute(
        select(LeaveRequest).where(LeaveRequest.id == talep_id)
    )
    talep = talep_result.scalar_one_or_none()
    if not talep:
        raise ValueError("Talep bulunamadı")
    if talep.yonetici_id != yonetici_id:
        raise PermissionError("Bu talep üzerinde yetkiniz yok")
    if talep.durum != "beklemede":
        raise ValueError(f"Talep zaten işlenmiş: {talep.durum}")

    talep.durum = karar.durum
    talep.ret_nedeni = karar.ret_nedeni

    # Onaylandıysa bakiyeden düş
    if karar.durum == "onaylandi" and talep.balance_id and talep.sure_gun:
        balance_result = await db.execute(
            select(LeaveBalance).where(LeaveBalance.id == talep.balance_id)
        )
        balance = balance_result.scalar_one_or_none()
        if balance:
            balance.kullanilan += talep.sure_gun

    # Çalışana bildirim
    emp_result = await db.execute(
        select(EmployeeProfile).where(EmployeeProfile.id == talep.employee_id)
    )
    calisan = emp_result.scalar_one_or_none()

    # Çalışana uygulama içi bildirim (onay/red)
    if calisan:
        izin_label = IZIN_TURLERI.get(talep.izin_turu, {}).get("label", talep.izin_turu)
        if karar.durum == "onaylandi":
            msg = f"✅ {izin_label} talebiniz onaylandı."
        else:
            msg = f"❌ {izin_label} talebiniz reddedildi."
            if karar.ret_nedeni:
                msg += f" Neden: {karar.ret_nedeni}"
        db.add(Notification(
            id=str(uuid.uuid4()),
            user_id=talep.employee_id,
            tur="leave_decided",
            ilgili_leave_id=talep.id,
            mesaj=msg,
        ))

    if calisan and calisan.email:
        try:
            sablon = "onaylandi" if karar.durum == "onaylandi" else "reddedildi"
            await izin_bildir(
                kime=calisan.email,
                sablon=sablon,
                context={
                    "calisan": calisan.ad_soyad,
                    "izin_turu": IZIN_TURLERI.get(talep.izin_turu, {}).get("label", talep.izin_turu),
                    "cikis": talep.cikis_tarihi.strftime("%d.%m.%Y"),
                    "sure": str(talep.sure_gun),
                    "ret_nedeni": karar.ret_nedeni or "",
                }
            )
        except Exception:
            pass

    await db.flush()
    await db.refresh(talep)
    return talep


# ─── İptal ───────────────────────────────────────────────────────────────────
async def cancel_leave_request(
    db: AsyncSession, talep_id: str, employee_id: str
) -> LeaveRequest:
    talep_result = await db.execute(
        select(LeaveRequest).where(LeaveRequest.id == talep_id)
    )
    talep = talep_result.scalar_one_or_none()
    if not talep:
        raise ValueError("Talep bulunamadı")
    if talep.employee_id != employee_id:
        raise PermissionError("Bu talebi iptal etme yetkiniz yok")
    if talep.durum not in ("beklemede",):
        raise ValueError(f"Bu aşamada iptal edilemez: {talep.durum}")

    talep.durum = "iptal"
    await db.flush()
    await db.refresh(talep)
    return talep
