"""
Oryantasyon Endpointleri — İSO Pulse
Yeni çalışan oryantasyon quiz sonuçlarını kaydeder ve İK mesajlaşmasını yönetir.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import uuid

from db.database import get_db
from db.models import OrientationResult, OrientationMessage, EmployeeProfile, Notification

router = APIRouter()


# ─── Pydantic Schemas ────────────────────────────────────────────────────────

class OrientationResultIn(BaseModel):
    employee_id: str
    dogru_sayisi: int
    toplam_soru: int
    puan: int  # 0-100


class OrientationResultOut(BaseModel):
    id: str
    employee_id: str
    ad_soyad: str
    dogru_sayisi: int
    toplam_soru: int
    puan: int
    tamamlama_tarihi: datetime

    class Config:
        from_attributes = True


class OrientationMessageIn(BaseModel):
    employee_id: str
    gonderen_id: str
    gonderen_rol: str
    mesaj: str


class OrientationMessageOut(BaseModel):
    id: str
    employee_id: str
    gonderen_id: str
    gonderen_rol: str
    mesaj: str
    okundu: bool
    olusturma: datetime

    class Config:
        from_attributes = True


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/results", response_model=OrientationResultOut)
async def save_orientation_result(
    payload: OrientationResultIn,
    db: AsyncSession = Depends(get_db),
):
    """Yeni çalışan quiz sonucunu kaydet ve İK'ya bildirim gönder."""
    # Çalışan kontrolü
    calisan = await db.get(EmployeeProfile, payload.employee_id)
    if not calisan:
        raise HTTPException(status_code=404, detail="Çalışan bulunamadı")

    # Sonuç kaydet
    result = OrientationResult(
        id=str(uuid.uuid4()),
        employee_id=payload.employee_id,
        dogru_sayisi=payload.dogru_sayisi,
        toplam_soru=payload.toplam_soru,
        puan=payload.puan,
    )
    db.add(result)
    await db.flush()

    # İK kullanıcılarına bildirim gönder
    hr_users = await db.execute(
        select(EmployeeProfile).where(EmployeeProfile.is_hr == True)
    )
    for hr in hr_users.scalars().all():
        notif = Notification(
            id=str(uuid.uuid4()),
            user_id=hr.id,
            tur="orientation_completed",
            mesaj=(
                f"🎓 {calisan.ad_soyad} oryantasyon quizini tamamladı — "
                f"Puan: {payload.puan}/100 ({payload.dogru_sayisi}/{payload.toplam_soru} doğru)"
            ),
        )
        db.add(notif)

    await db.commit()
    await db.refresh(result)

    return OrientationResultOut(
        id=result.id,
        employee_id=result.employee_id,
        ad_soyad=calisan.ad_soyad,
        dogru_sayisi=result.dogru_sayisi,
        toplam_soru=result.toplam_soru,
        puan=result.puan,
        tamamlama_tarihi=result.tamamlama_tarihi,
    )


@router.get("/results", response_model=list[OrientationResultOut])
async def list_orientation_results(
    db: AsyncSession = Depends(get_db),
):
    """Tüm oryantasyon quiz sonuçlarını listele (İK için)."""
    rows = await db.execute(
        select(OrientationResult)
        .order_by(desc(OrientationResult.tamamlama_tarihi))
    )
    results = []
    for r in rows.scalars().all():
        calisan = await db.get(EmployeeProfile, r.employee_id)
        results.append(OrientationResultOut(
            id=r.id,
            employee_id=r.employee_id,
            ad_soyad=calisan.ad_soyad if calisan else r.employee_id,
            dogru_sayisi=r.dogru_sayisi,
            toplam_soru=r.toplam_soru,
            puan=r.puan,
            tamamlama_tarihi=r.tamamlama_tarihi,
        ))
    return results


@router.get("/results/{employee_id}", response_model=Optional[OrientationResultOut])
async def get_employee_result(
    employee_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Belirli bir çalışanın son oryantasyon sonucunu getir."""
    row = await db.execute(
        select(OrientationResult)
        .where(OrientationResult.employee_id == employee_id)
        .order_by(desc(OrientationResult.tamamlama_tarihi))
        .limit(1)
    )
    r = row.scalar_one_or_none()
    if not r:
        return None
    calisan = await db.get(EmployeeProfile, r.employee_id)
    return OrientationResultOut(
        id=r.id,
        employee_id=r.employee_id,
        ad_soyad=calisan.ad_soyad if calisan else r.employee_id,
        dogru_sayisi=r.dogru_sayisi,
        toplam_soru=r.toplam_soru,
        puan=r.puan,
        tamamlama_tarihi=r.tamamlama_tarihi,
    )


# ─── Mesajlaşma ──────────────────────────────────────────────────────────────

@router.post("/messages", response_model=OrientationMessageOut)
async def send_message(
    payload: OrientationMessageIn,
    db: AsyncSession = Depends(get_db),
):
    """Oryantasyon sürecinde mesaj gönder (çalışan ↔ İK)."""
    msg = OrientationMessage(
        id=str(uuid.uuid4()),
        employee_id=payload.employee_id,
        gonderen_id=payload.gonderen_id,
        gonderen_rol=payload.gonderen_rol,
        mesaj=payload.mesaj,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


@router.get("/messages/{employee_id}", response_model=list[OrientationMessageOut])
async def get_messages(
    employee_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Belirli bir çalışana ait tüm oryantasyon mesajlarını getir."""
    rows = await db.execute(
        select(OrientationMessage)
        .where(OrientationMessage.employee_id == employee_id)
        .order_by(OrientationMessage.olusturma)
    )
    return rows.scalars().all()


@router.patch("/messages/{message_id}/read")
async def mark_message_read(
    message_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Mesajı okundu olarak işaretle."""
    msg = await db.get(OrientationMessage, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Mesaj bulunamadı")
    msg.okundu = True
    await db.commit()
    return {"ok": True}
