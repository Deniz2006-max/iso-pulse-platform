"""
SQLAlchemy ORM modelleri — İSO Pulse (Inpulse + Outpulse)
"""
import uuid
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import (
    UUID, String, Integer, Date, DateTime, Numeric,
    ForeignKey, Text, Boolean, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.database import Base


# ─── Ortak yardımcı ────────────────────────────────────────────────────────
def new_uuid():
    return str(uuid.uuid4())


# ─── Çalışan profili ────────────────────────────────────────────────────────
class EmployeeProfile(Base):
    __tablename__ = "employee_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    ad_soyad: Mapped[str] = mapped_column(String(120), nullable=False)
    sube: Mapped[str | None] = mapped_column(String(100))
    ise_giris_tarihi: Mapped[date] = mapped_column(Date, nullable=False)
    dogum_tarihi: Mapped[date | None] = mapped_column(Date)
    email: Mapped[str | None] = mapped_column(String(200))
    yonetici_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("employee_profiles.id"))
    is_hr: Mapped[bool] = mapped_column(Boolean, default=False)
    is_yonetici: Mapped[bool] = mapped_column(Boolean, default=False)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True)
    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # İlişkiler
    izin_bakiye: Mapped[list["LeaveBalance"]] = relationship(back_populates="calisan")
    izin_talepler: Mapped[list["LeaveRequest"]] = relationship(
        back_populates="calisan", foreign_keys="LeaveRequest.employee_id"
    )


# ─── İzin bakiyesi ──────────────────────────────────────────────────────────
class LeaveBalance(Base):
    __tablename__ = "leave_balance"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("employee_profiles.id"), nullable=False)
    yil: Mapped[int] = mapped_column(Integer, nullable=False)
    onceki_yildan: Mapped[Decimal] = mapped_column(Numeric(5, 1), default=Decimal("0"))
    yillik_hak: Mapped[Decimal] = mapped_column(Numeric(5, 1), nullable=False)
    idari_eklenen: Mapped[Decimal] = mapped_column(Numeric(5, 1), default=Decimal("0"))
    kullanilan: Mapped[Decimal] = mapped_column(Numeric(5, 1), default=Decimal("0"))
    # bakiye = onceki_yildan + yillik_hak + idari_eklenen - kullanilan
    # (PostgreSQL'de GENERATED ALWAYS AS ile; uygulama katmanında da hesaplanabilir)

    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    guncelleme: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    calisan: Mapped["EmployeeProfile"] = relationship(back_populates="izin_bakiye")
    izin_talepler: Mapped[list["LeaveRequest"]] = relationship(back_populates="bakiye")

    @property
    def bakiye(self) -> Decimal:
        return self.onceki_yildan + self.yillik_hak + self.idari_eklenen - self.kullanilan


# ─── İzin talebi ────────────────────────────────────────────────────────────
class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("employee_profiles.id"), nullable=False)
    balance_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("leave_balance.id"))

    # İzin türü: yillik | 2saat | 2saat_uzeri | evlilik | olum | baba_dogum |
    #            dogum_kadin | ucretsiz | hastalik | idari
    izin_turu: Mapped[str] = mapped_column(String(30), nullable=False)

    cikis_tarihi: Mapped[date] = mapped_column(Date, nullable=False)
    giris_tarihi: Mapped[date] = mapped_column(Date, nullable=False)
    sure_gun: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))   # 2h izin → 0.27
    neden: Mapped[str | None] = mapped_column(Text)

    # Durum: beklemede | onaylandi | reddedildi | iptal
    durum: Mapped[str] = mapped_column(String(20), default="beklemede")
    ret_nedeni: Mapped[str | None] = mapped_column(Text)

    yonetici_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("employee_profiles.id"))

    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    guncelleme: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    calisan: Mapped["EmployeeProfile"] = relationship(
        back_populates="izin_talepler", foreign_keys=[employee_id]
    )
    bakiye: Mapped["LeaveBalance | None"] = relationship(back_populates="izin_talepler")


# ─── Görev yönetimi ─────────────────────────────────────────────────────────
class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    baslik: Mapped[str] = mapped_column(String(200), nullable=False)
    aciklama: Mapped[str | None] = mapped_column(Text)

    # Öncelik: yuksek | orta | dusuk
    oncelik: Mapped[str] = mapped_column(String(20), default="orta")

    # Durum: atandi | devam_ediyor | teslim_edildi | onay_bekliyor | tamamlandi
    durum: Mapped[str] = mapped_column(String(30), default="atandi")

    bitis_tarihi: Mapped[date] = mapped_column(Date, nullable=False)

    employee_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("employee_profiles.id"), nullable=False
    )
    yonetici_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("employee_profiles.id"), nullable=False
    )

    teslim_edildi_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tamamlandi_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ret_notu: Mapped[str | None] = mapped_column(Text)

    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    guncelleme: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # İlişkiler
    calisan: Mapped["EmployeeProfile"] = relationship(foreign_keys=[employee_id])
    yonetici: Mapped["EmployeeProfile"] = relationship(foreign_keys=[yonetici_id])
    atama_gecmisi: Mapped[list["TaskAssignmentHistory"]] = relationship(back_populates="gorev")
    denetim_logu: Mapped[list["TaskAuditLog"]] = relationship(back_populates="gorev")


class TaskAssignmentHistory(Base):
    """Görev devir geçmişi — özel izinlerde (ölüm, doğum, hastalık) görev devri"""
    __tablename__ = "task_assignment_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=False)
    onceki_employee_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("employee_profiles.id"))
    yeni_employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("employee_profiles.id"), nullable=False)
    devir_eden_id: Mapped[str] = mapped_column(String(36), ForeignKey("employee_profiles.id"), nullable=False)
    sebep: Mapped[str | None] = mapped_column(Text)   # Hangi izin sebebiyle devredildi
    devir_tarihi: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    gorev: Mapped["Task"] = relationship(back_populates="atama_gecmisi")


class TaskAuditLog(Base):
    """Değişmez denetim kaydı — tüm görev yaşam döngüsü olayları"""
    __tablename__ = "task_audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=False)

    # Eylem: created | status_changed | reassigned | note_added | deadline_changed
    eylem: Mapped[str] = mapped_column(String(50), nullable=False)
    yapan_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("employee_profiles.id"))
    eski_deger: Mapped[str | None] = mapped_column(Text)
    yeni_deger: Mapped[str | None] = mapped_column(Text)
    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    gorev: Mapped["Task"] = relationship(back_populates="denetim_logu")


class Notification(Base):
    """Bildirim — görev ve izin olayları için"""
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("employee_profiles.id"), nullable=False)

    # Tür: task_assigned | task_deadline_7 | task_deadline_3 | task_deadline_1 |
    #       task_submitted | task_approved | task_rejected | task_reassigned
    tur: Mapped[str] = mapped_column(String(50), nullable=False)

    ilgili_task_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tasks.id"))
    ilgili_leave_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("leave_requests.id"))
    mesaj: Mapped[str] = mapped_column(Text, nullable=False)
    okundu: Mapped[bool] = mapped_column(Boolean, default=False)
    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    kullanici: Mapped["EmployeeProfile"] = relationship(foreign_keys=[user_id])


class LeaveDocument(Base):
    """İzin belgesi — hastalık raporu, doğum belgesi vb."""
    __tablename__ = "leave_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    leave_request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("leave_requests.id"), nullable=False
    )

    # Belge türü: hastalik_raporu | dogum_belgesi | diger
    belge_turu: Mapped[str] = mapped_column(String(50), nullable=False)
    dosya_yolu: Mapped[str] = mapped_column(String(500), nullable=False)
    dosya_adi: Mapped[str] = mapped_column(String(200), nullable=False)
    yukleyen_id: Mapped[str] = mapped_column(String(36), ForeignKey("employee_profiles.id"), nullable=False)
    yuklenme_tarihi: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    izin_talebi: Mapped["LeaveRequest"] = relationship(foreign_keys=[leave_request_id])


# ─── Oryantasyon ────────────────────────────────────────────────────────────
class OrientationResult(Base):
    """Yeni çalışan oryantasyon quiz sonucu"""
    __tablename__ = "orientation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("employee_profiles.id"), nullable=False)
    dogru_sayisi: Mapped[int] = mapped_column(Integer, nullable=False)
    toplam_soru: Mapped[int] = mapped_column(Integer, nullable=False)
    puan: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-100
    tamamlama_tarihi: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    calisan: Mapped["EmployeeProfile"] = relationship(foreign_keys=[employee_id])


class OrientationMessage(Base):
    """Oryantasyon sürecinde çalışan ↔ İK mesajlaşma"""
    __tablename__ = "orientation_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey("employee_profiles.id"), nullable=False)
    gonderen_id: Mapped[str] = mapped_column(String(36), ForeignKey("employee_profiles.id"), nullable=False)
    # rol: calisan | ik | yonetici
    gonderen_rol: Mapped[str] = mapped_column(String(20), nullable=False)
    mesaj: Mapped[str] = mapped_column(Text, nullable=False)
    okundu: Mapped[bool] = mapped_column(Boolean, default=False)
    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    calisan: Mapped["EmployeeProfile"] = relationship(foreign_keys=[employee_id])
    gonderen: Mapped["EmployeeProfile"] = relationship(foreign_keys=[gonderen_id])


# ─── Outpulse: Mevzuat kaydı ────────────────────────────────────────────────
class MevzuatKaydi(Base):
    __tablename__ = "mevzuat_kayitlar"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    kaynak: Mapped[str] = mapped_column(String(50), nullable=False)  # resmi_gazete | mevzuat | sgk | csgb
    baslik: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str | None] = mapped_column(String(1000))
    icerik_hash: Mapped[str | None] = mapped_column(String(64))       # SHA-256
    ozet: Mapped[str | None] = mapped_column(Text)
    kategori: Mapped[str | None] = mapped_column(String(50))          # ik | hukuk | mali
    yayin_tarihi: Mapped[date | None] = mapped_column(Date)
    chroma_id: Mapped[str | None] = mapped_column(String(100))
    bildirim_gonderildi: Mapped[bool] = mapped_column(Boolean, default=False)
    olusturma: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
