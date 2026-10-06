"""
Kutlama modülü şemaları
"""
from datetime import date
from enum import Enum
from typing import Optional, Literal

from pydantic import BaseModel


class CelebrationType(str, Enum):
    dogum_gunu = "dogum_gunu"
    yil_donumu = "yil_donumu"


class CelebrationItem(BaseModel):
    employee_id: str
    ad_soyad: str
    sube: str
    tur: CelebrationType
    tarih: date
    kac_gun_sonra: int     # 0 = bugün
    kac_yil: Optional[int]  # Yıldönümü için kaçıncı yıl; doğum günü için None

    model_config = {"from_attributes": True}


# ── Akran kutlama (peer-to-peer) ─────────────────────────────────────────────

class KutlamaRequest(BaseModel):
    """Platform bildirimi olarak kutlama gönder."""
    hedef_id: str
    gonderen_id: str
    gonderen_ad: str
    tur: Literal["dogum_gunu", "yil_donumu", "genel"]
    mesaj: str


class KutlamaEmailRequest(BaseModel):
    """Email olarak kutlama gönder."""
    hedef_email: str
    hedef_ad_soyad: str
    gonderen_ad: str
    tur: Literal["dogum_gunu", "yil_donumu", "genel"]
    mesaj: str
    kac_yil: Optional[int] = None


class EmailTestRequest(BaseModel):
    """SMTP bağlantı testi — test emaili gönder."""
    test_email: str
