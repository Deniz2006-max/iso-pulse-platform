"""
Görev Yönetimi — Pydantic Şemaları
"""
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


# ─── Görev oluşturma / güncelleme ───────────────────────────────────────────
class TaskCreate(BaseModel):
    baslik: str
    aciklama: Optional[str] = None
    oncelik: str = "orta"          # yuksek | orta | dusuk
    bitis_tarihi: date
    employee_id: str               # Atanan çalışan


class TaskUpdate(BaseModel):
    baslik: Optional[str] = None
    aciklama: Optional[str] = None
    oncelik: Optional[str] = None
    bitis_tarihi: Optional[date] = None
    durum: Optional[str] = None
    ret_notu: Optional[str] = None


class TaskReassign(BaseModel):
    yeni_employee_id: str
    sebep: Optional[str] = None


# ─── Görev yanıtı ────────────────────────────────────────────────────────────
class EmployeeBasic(BaseModel):
    id: str
    ad_soyad: str

    model_config = {"from_attributes": True}


class TaskResponse(BaseModel):
    id: str
    baslik: str
    aciklama: Optional[str]
    oncelik: str
    durum: str
    bitis_tarihi: date
    employee_id: str
    yonetici_id: str
    teslim_edildi_at: Optional[datetime]
    tamamlandi_at: Optional[datetime]
    ret_notu: Optional[str]
    olusturma: datetime
    guncelleme: datetime

    # İlişkili bilgiler (JOIN ile doldurulur)
    calisan_adi: Optional[str] = None
    yonetici_adi: Optional[str] = None

    model_config = {"from_attributes": True}


# ─── Denetim kaydı yanıtı ────────────────────────────────────────────────────
class AuditLogResponse(BaseModel):
    id: str
    task_id: str
    eylem: str
    yapan_id: Optional[str]
    eski_deger: Optional[str]
    yeni_deger: Optional[str]
    olusturma: datetime

    model_config = {"from_attributes": True}


# ─── Çakışma bilgisi ────────────────────────────────────────────────────────
class TaskConflict(BaseModel):
    task_id: str
    baslik: str
    bitis_tarihi: date
    oncelik: str


class LeaveConflictInfo(BaseModel):
    """İzin talebi için görev çakışma raporu"""
    employee_id: str
    leave_start: date
    leave_end: date
    cakisan_gorevler: list[TaskConflict]
    ozel_izin: bool  # Özel izin → devir gerekli; normal izin → sadece uyarı
