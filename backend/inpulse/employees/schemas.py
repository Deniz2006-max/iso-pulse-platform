"""
Çalışan profil şemaları
"""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class EmployeeListItem(BaseModel):
    id: str
    ad_soyad: str
    sube: Optional[str]
    ise_giris_tarihi: date
    dogum_tarihi: Optional[date]
    is_hr: bool
    is_yonetici: bool

    model_config = {"from_attributes": True}


class EmployeeDetail(EmployeeListItem):
    email: Optional[str]
    aktif: bool
    olusturma: datetime
