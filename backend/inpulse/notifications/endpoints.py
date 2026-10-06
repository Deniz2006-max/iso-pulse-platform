"""
Bildirim Sistemi API Endpoint'leri
Base prefix: /api/v1/hr/notifications
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
import uuid

from db.database import get_db
from db.models import Notification
from inpulse.notifications.schemas import NotificationResponse, NotificationSummary

router = APIRouter()


class NotificationCreate(BaseModel):
    user_id: str
    tur: str
    mesaj: str
    ilgili_leave_id: str | None = None
    ilgili_task_id: str | None = None


# ── 0. Bildirim oluştur (frontend tetikli) ───────────────────────────────────
@router.post(
    "/",
    response_model=NotificationResponse,
    summary="Yeni bildirim oluştur",
)
async def create_notification(
    body: NotificationCreate,
    db: AsyncSession = Depends(get_db),
):
    notif = Notification(
        id=str(uuid.uuid4()),
        user_id=body.user_id,
        tur=body.tur,
        mesaj=body.mesaj,
        ilgili_leave_id=body.ilgili_leave_id,
        ilgili_task_id=body.ilgili_task_id,
    )
    db.add(notif)
    await db.commit()
    await db.refresh(notif)
    return NotificationResponse.model_validate(notif)


# ── 1. Kullanıcının bildirimleri ─────────────────────────────────────────────
@router.get(
    "/{user_id}",
    response_model=NotificationSummary,
    summary="Kullanıcı bildirimleri",
)
async def get_notifications(
    user_id: str,
    limit: int = Query(default=20, le=50),
    sadece_okunmamis: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    conditions = [Notification.user_id == user_id]
    if sadece_okunmamis:
        conditions.append(Notification.okundu == False)

    result = await db.execute(
        select(Notification)
        .where(and_(*conditions))
        .order_by(Notification.olusturma.desc())
        .limit(limit)
    )
    bildirimler = list(result.scalars().all())

    # Okunmamış sayısı
    okunmamis_result = await db.execute(
        select(Notification).where(
            and_(Notification.user_id == user_id, Notification.okundu == False)
        )
    )
    okunmamis_sayi = len(list(okunmamis_result.scalars().all()))

    return NotificationSummary(
        okunmamis_sayi=okunmamis_sayi,
        bildirimler=[NotificationResponse.model_validate(b) for b in bildirimler],
    )


# ── 2. Bildirimi okundu işaretle ─────────────────────────────────────────────
@router.patch(
    "/{notification_id}/read",
    summary="Bildirimi okundu işaretle",
)
async def mark_as_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id)
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail="Bildirim bulunamadı")

    notif.okundu = True
    await db.commit()
    return {"ok": True}


# ── 3. Tüm bildirimleri okundu işaretle ─────────────────────────────────────
@router.patch(
    "/{user_id}/read-all",
    summary="Tüm bildirimleri okundu işaretle",
)
async def mark_all_read(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        update(Notification)
        .where(and_(Notification.user_id == user_id, Notification.okundu == False))
        .values(okundu=True)
    )
    await db.commit()
    return {"ok": True}
