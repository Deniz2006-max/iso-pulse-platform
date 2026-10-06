"""
Bildirim Sistemi — Pydantic Şemaları
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: str
    user_id: str
    tur: str
    ilgili_task_id: Optional[str]
    ilgili_leave_id: Optional[str]
    mesaj: str
    okundu: bool
    olusturma: datetime

    model_config = {"from_attributes": True}


class NotificationSummary(BaseModel):
    """Bildirim zili için özet"""
    okunmamis_sayi: int
    bildirimler: list[NotificationResponse]
