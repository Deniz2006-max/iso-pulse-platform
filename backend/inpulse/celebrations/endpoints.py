"""
Kutlama Modülü — Doğum Günü & İşe Giriş Yıldönümü
GET  /api/v1/hr/celebrations/today   → Bugün ve önümüzdeki 7 gün içindeki kutlamalar
POST /api/v1/hr/celebrations/notify  → Platform bildirimi + email gönder (günlük tetiklenir)
"""
from datetime import date, timedelta
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid

from db.database import get_db
from db.models import EmployeeProfile, Notification
from inpulse.celebrations.schemas import (
    CelebrationItem, CelebrationType,
    KutlamaRequest, KutlamaEmailRequest, EmailTestRequest,
)
from inpulse.celebrations.email_service import (
    send_celebration_email, send_peer_celebration_email, send_test_email,
)

router = APIRouter()


def _gun_fark(ay: int, gun: int, referans: date) -> int:
    """Yıl bağımsız — bugünden kaç gün sonra bu ay/gün gelir (0-365)."""
    try:
        hedef = date(referans.year, ay, gun)
    except ValueError:
        return 366
    delta = (hedef - referans).days
    if delta < 0:
        try:
            hedef = date(referans.year + 1, ay, gun)
        except ValueError:
            return 366
        delta = (hedef - referans).days
    return delta


@router.get(
    "/today",
    response_model=list[CelebrationItem],
    summary="Bugünkü ve yaklaşan kutlamalar",
)
async def get_celebrations(
    gun_aralik: int = 7,
    db: AsyncSession = Depends(get_db),
) -> list[CelebrationItem]:
    """Önümüzdeki `gun_aralik` gün içindeki doğum günü ve işe giriş yıldönümlerini döndürür."""
    bugun = date.today()
    result = await db.execute(
        select(EmployeeProfile).where(EmployeeProfile.aktif == True)  # noqa
    )
    employees = result.scalars().all()
    kutlamalar: list[CelebrationItem] = []

    for emp in employees:
        if emp.dogum_tarihi:
            fark = _gun_fark(emp.dogum_tarihi.month, emp.dogum_tarihi.day, bugun)
            if 0 <= fark <= gun_aralik:
                kutlamalar.append(CelebrationItem(
                    employee_id=emp.id,
                    ad_soyad=emp.ad_soyad,
                    sube=emp.sube or "—",
                    tur=CelebrationType.dogum_gunu,
                    tarih=bugun + timedelta(days=fark),
                    kac_gun_sonra=fark,
                    kac_yil=None,
                ))

        fark_yd = _gun_fark(emp.ise_giris_tarihi.month, emp.ise_giris_tarihi.day, bugun)
        if 0 <= fark_yd <= gun_aralik:
            hedef_tarih = bugun + timedelta(days=fark_yd)
            kac_yil = hedef_tarih.year - emp.ise_giris_tarihi.year
            if kac_yil > 0:
                kutlamalar.append(CelebrationItem(
                    employee_id=emp.id,
                    ad_soyad=emp.ad_soyad,
                    sube=emp.sube or "—",
                    tur=CelebrationType.yil_donumu,
                    tarih=hedef_tarih,
                    kac_gun_sonra=fark_yd,
                    kac_yil=kac_yil,
                ))

    kutlamalar.sort(key=lambda x: x.kac_gun_sonra)
    return kutlamalar


@router.post(
    "/notify",
    summary="Bugünkü kutlamalar için bildirim ve email gönder",
)
async def notify_celebrations(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Bugün doğum günü veya işe giriş yıldönümü olan çalışanlara:
    - Platform içi bildirim gönderir (hem çalışana hem İK'ya)
    - Arkaplanda kutlama e-postası gönderir
    Günlük 09:00'da scheduler tarafından otomatik çağrılır.
    """
    bugun = date.today()

    # Tüm aktif çalışanları çek
    result = await db.execute(
        select(EmployeeProfile).where(EmployeeProfile.aktif == True)  # noqa
    )
    employees = result.scalars().all()

    # İK kullanıcılarını çek
    hr_result = await db.execute(
        select(EmployeeProfile).where(EmployeeProfile.is_hr == True)  # noqa
    )
    hr_users = hr_result.scalars().all()

    gonderilen = []

    for emp in employees:
        # ── Doğum günü kontrolü ─────────────────────────────────────────────
        if emp.dogum_tarihi:
            if emp.dogum_tarihi.month == bugun.month and emp.dogum_tarihi.day == bugun.day:
                mesaj_calisan = (
                    f"🎂 Doğum günün kutlu olsun, {emp.ad_soyad.split()[0]}! "
                    "İSO Pulse ailesi bu özel günde seninle! 🎉"
                )
                mesaj_ik = (
                    f"🎂 Bugün {emp.ad_soyad} adlı çalışanımızın doğum günü! "
                    "Tebrik mesajı otomatik olarak iletildi."
                )

                # Çalışana bildirim
                db.add(Notification(
                    id=str(uuid.uuid4()),
                    user_id=emp.id,
                    tur="dogum_gunu",
                    mesaj=mesaj_calisan,
                ))

                # İK ekibine bildirim
                for hr in hr_users:
                    db.add(Notification(
                        id=str(uuid.uuid4()),
                        user_id=hr.id,
                        tur="dogum_gunu_ik",
                        mesaj=mesaj_ik,
                    ))

                # E-posta (arkaplanda)
                if emp.email:
                    background_tasks.add_task(
                        send_celebration_email,
                        emp.email, emp.ad_soyad, "dogum_gunu", None,
                    )

                gonderilen.append({
                    "employee_id": emp.id,
                    "ad_soyad": emp.ad_soyad,
                    "tur": "dogum_gunu",
                    "email_var": bool(emp.email),
                })

        # ── İşe giriş yıldönümü kontrolü ───────────────────────────────────
        if (emp.ise_giris_tarihi.month == bugun.month
                and emp.ise_giris_tarihi.day == bugun.day
                and emp.ise_giris_tarihi.year != bugun.year):

            kac_yil = bugun.year - emp.ise_giris_tarihi.year
            mesaj_calisan = (
                f"🏆 İSO Pulse ailesine katılışının {kac_yil}. yılı! "
                f"Katkıların için teşekkür ederiz, {emp.ad_soyad.split()[0]}! 🌟"
            )
            mesaj_ik = (
                f"🏆 {emp.ad_soyad} bugün {kac_yil}. çalışma yılını kutluyor! "
                "Tebrik bildirimi gönderildi."
            )

            # Çalışana bildirim
            db.add(Notification(
                id=str(uuid.uuid4()),
                user_id=emp.id,
                tur="yil_donumu",
                mesaj=mesaj_calisan,
            ))

            # İK ekibine bildirim
            for hr in hr_users:
                db.add(Notification(
                    id=str(uuid.uuid4()),
                    user_id=hr.id,
                    tur="yil_donumu_ik",
                    mesaj=mesaj_ik,
                ))

            # E-posta (arkaplanda)
            if emp.email:
                background_tasks.add_task(
                    send_celebration_email,
                    emp.email, emp.ad_soyad, "yil_donumu", kac_yil,
                )

            gonderilen.append({
                "employee_id": emp.id,
                "ad_soyad": emp.ad_soyad,
                "tur": "yil_donumu",
                "kac_yil": kac_yil,
                "email_var": bool(emp.email),
            })

    await db.commit()
    return {
        "tarih": bugun.isoformat(),
        "gonderilen_sayisi": len(gonderilen),
        "detay": gonderilen,
    }


# ── Peer-to-peer kutlama ────────────────────────────────────────────────────

@router.post(
    "/kutla",
    summary="İş arkadaşına platform bildirimi olarak kutlama gönder",
)
async def kutla_bildirim(
    req: KutlamaRequest,
    db: AsyncSession = Depends(get_db),
):
    """Belirtilen çalışana platform içi kutlama bildirimi gönder."""
    # Hedef çalışanı doğrula
    result = await db.execute(
        select(EmployeeProfile).where(EmployeeProfile.id == req.hedef_id)
    )
    hedef = result.scalar_one_or_none()
    if not hedef:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Çalışan bulunamadı")

    tur_emoji = {"dogum_gunu": "🎂", "yil_donumu": "🏆", "genel": "🎉"}.get(req.tur, "🎉")
    mesaj_metni = f"{tur_emoji} {req.gonderen_ad}: {req.mesaj}"

    db.add(Notification(
        id=str(uuid.uuid4()),
        user_id=req.hedef_id,
        tur=f"peer_{req.tur}",
        mesaj=mesaj_metni,
    ))
    await db.commit()
    return {"basarili": True, "mesaj": "Kutlama bildirimi gönderildi"}


@router.post(
    "/kutla/email",
    summary="İş arkadaşına email olarak kutlama gönder",
)
async def kutla_email(
    req: KutlamaEmailRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Belirtilen adrese peer kutlama emaili gönder (arkaplanda)."""
    if not req.hedef_email:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Email adresi gerekli")

    background_tasks.add_task(
        send_peer_celebration_email,
        req.hedef_email,
        req.hedef_ad_soyad,
        req.gonderen_ad,
        req.tur,
        req.mesaj,
        req.kac_yil,
    )
    return {"basarili": True, "mesaj": "Kutlama emaili gönderiliyor"}


@router.post(
    "/email-test",
    summary="SMTP bağlantı testi — test emaili gönder",
)
async def email_baglanti_test(
    req: EmailTestRequest,
    background_tasks: BackgroundTasks,
):
    """Belirtilen adrese SMTP test emaili gönder."""
    background_tasks.add_task(send_test_email, req.test_email)
    return {"basarili": True, "mesaj": f"Test emaili {req.test_email} adresine gönderiliyor"}
