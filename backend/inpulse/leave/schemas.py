"""
Pydantic v2 şemaları — İzin modülü
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ─── İzin türü sabit listesi ─────────────────────────────────────────────────
IzinTuru = Literal[
    "yillik", "2saat", "2saat_uzeri", "evlilik", "olum",
    "baba_dogum", "dogum_kadin", "ucretsiz", "hastalik", "idari"
]

IzinDurum = Literal["beklemede", "onaylandi", "reddedildi", "iptal"]


# ─── Talep oluşturma ─────────────────────────────────────────────────────────
class LeaveRequestCreate(BaseModel):
    izin_turu: IzinTuru
    cikis_tarihi: date
    giris_tarihi: date
    neden: Optional[str] = Field(None, max_length=500)

    @model_validator(mode="after")
    def tarih_kontrolu(self):
        if self.giris_tarihi <= self.cikis_tarihi:
            raise ValueError("Giriş tarihi çıkış tarihinden sonra olmalıdır")
        if self.cikis_tarihi < date.today():
            raise ValueError("Çıkış tarihi geçmiş bir tarih olamaz")
        return self


class LeaveRequestUpdate(BaseModel):
    """Çalışan iptal edebilir; yönetici onaylar/reddeder."""
    durum: Optional[IzinDurum] = None
    ret_nedeni: Optional[str] = Field(None, max_length=500)


# ─── Yanıt modelleri ──────────────────────────────────────────────────────────
class LeaveRequestResponse(BaseModel):
    id: str
    employee_id: str
    izin_turu: str
    cikis_tarihi: date
    giris_tarihi: date
    sure_gun: Optional[Decimal]
    neden: Optional[str]
    durum: str
    ret_nedeni: Optional[str]
    yonetici_id: Optional[str]
    olusturma: datetime
    guncelleme: datetime

    model_config = {"from_attributes": True}


class LeaveBalanceResponse(BaseModel):
    employee_id: str
    yil: int
    onceki_yildan: Decimal
    yillik_hak: Decimal
    idari_eklenen: Decimal
    kullanilan: Decimal
    bakiye: Decimal     # hesaplanan alan

    model_config = {"from_attributes": True}


class IzinTurleriResponse(BaseModel):
    """Kullanılabilir izin türleri listesi"""
    kod: str
    label: str
    aciklama: str
    max_gun: Optional[Decimal]
    bakiyeden_dusuler: bool


# ─── Yönetici onay isteği ─────────────────────────────────────────────────────
class ManagerDecision(BaseModel):
    durum: Literal["onaylandi", "reddedildi"]
    ret_nedeni: Optional[str] = Field(None, max_length=500)

    @model_validator(mode="after")
    def ret_nedeni_zorunlu(self):
        if self.durum == "reddedildi" and not self.ret_nedeni:
            raise ValueError("Red durumunda ret_nedeni zorunludur")
        return self


# ─── Çalışan özet ─────────────────────────────────────────────────────────────
class EmployeeLeaveOverview(BaseModel):
    employee_id: str
    ad_soyad: str
    bakiye: LeaveBalanceResponse
    son_talepler: list[LeaveRequestResponse]
