"""
Demo Seed Scripti — İSO Pulse
Geliştirme ortamı için örnek çalışan ve izin verisi oluşturur.
Kullanım: cd backend && python scripts/seed.py
"""
import asyncio
import uuid
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import text

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import get_settings
from db.database import Base
from db.models import EmployeeProfile, LeaveBalance, LeaveRequest, Task, TaskAuditLog, OrientationResult, OrientationMessage
from inpulse.leave.calculator import yillik_izin_hakki

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def seed():
    # Tabloları oluştur (dev)
    async with engine.begin() as conn:
        import db.models  # noqa
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        # Mevcut verileri temizle — CASCADE ile FK bağımlılıklarını otomatik çöz
        await db.execute(text("""
            TRUNCATE TABLE
                orientation_messages,
                orientation_results,
                task_audit_log,
                task_assignment_history,
                notifications,
                leave_documents,
                tasks,
                leave_requests,
                leave_balance,
                employee_profiles
            RESTART IDENTITY CASCADE
        """))
        await db.commit()

        # ── Çalışanlar ─────────────────────────────────────────────────────
        yonetici = EmployeeProfile(
            id="demo-manager-001",
            ad_soyad="Mehmet Kaya",
            sube="Yazılım Geliştirme",
            ise_giris_tarihi=date(2016, 3, 15),
            dogum_tarihi=date(1985, 7, 20),
            email="mehmet.kaya@iso.org.tr",
            yonetici_id=None,
            is_yonetici=True,
            is_hr=False,
        )

        hr_yonetici = EmployeeProfile(
            id="demo-hr-001",
            ad_soyad="Selin Arslan",
            sube="İnsan Kaynakları",
            ise_giris_tarihi=date(2014, 9, 1),
            dogum_tarihi=date(1988, 11, 5),
            email="selin.arslan@iso.org.tr",
            yonetici_id=None,
            is_yonetici=False,
            is_hr=True,
        )

        calisan1 = EmployeeProfile(
            id="demo-employee-001",
            ad_soyad="Zeynep Yılmaz",
            sube="Yazılım Geliştirme",
            ise_giris_tarihi=date(2023, 9, 18),
            dogum_tarihi=date(1998, 10, 15),  # Yakında doğum günü!
            email="zeynep.yilmaz@iso.org.tr",
            yonetici_id="demo-manager-001",
            is_yonetici=False,
            is_hr=False,
        )

        calisan2 = EmployeeProfile(
            id="demo-employee-002",
            ad_soyad="Kemal Demir",
            sube="İnsan Kaynakları",
            ise_giris_tarihi=date(2020, 10, 1),
            dogum_tarihi=date(1995, 10, 1),
            email="kemal.demir@iso.org.tr",
            yonetici_id="demo-manager-001",
            is_yonetici=False,
            is_hr=False,
        )

        calisan3 = EmployeeProfile(
            id="demo-employee-003",
            ad_soyad="Selin Kaya",
            sube="Muhasebe",
            ise_giris_tarihi=date(2018, 5, 10),
            dogum_tarihi=date(1991, 4, 22),
            email="selin.kaya@iso.org.tr",
            yonetici_id="demo-manager-001",
            is_yonetici=False,
            is_hr=False,
        )

        # Yeni çalışan — bugün ilk iş günü, oryantasyon yapacak
        calisan_yeni = EmployeeProfile(
            id="demo-employee-ayse",
            ad_soyad="Ayşe Aydın",
            sube="Yazılım Geliştirme",
            ise_giris_tarihi=date(2026, 10, 5),
            dogum_tarihi=date(2001, 3, 22),
            email="ayse.aydin@iso.org.tr",
            yonetici_id="demo-manager-001",
            is_yonetici=False,
            is_hr=False,
        )

        db.add_all([yonetici, hr_yonetici, calisan1, calisan2, calisan3, calisan_yeni])
        await db.flush()

        # ── Bakiyeler (2026) ───────────────────────────────────────────────
        from decimal import Decimal

        bakiye1 = LeaveBalance(
            id=str(uuid.uuid4()),
            employee_id="demo-employee-001",
            yil=2026,
            onceki_yildan=Decimal("5"),
            yillik_hak=yillik_izin_hakki(calisan1.ise_giris_tarihi, 2026),
            idari_eklenen=Decimal("0"),
            kullanilan=Decimal("3"),
        )

        bakiye2 = LeaveBalance(
            id=str(uuid.uuid4()),
            employee_id="demo-employee-002",
            yil=2026,
            onceki_yildan=Decimal("0"),
            yillik_hak=yillik_izin_hakki(calisan2.ise_giris_tarihi, 2026),
            idari_eklenen=Decimal("2"),
            kullanilan=Decimal("10"),
        )

        bakiye3 = LeaveBalance(
            id=str(uuid.uuid4()),
            employee_id="demo-employee-003",
            yil=2026,
            onceki_yildan=Decimal("3"),
            yillik_hak=yillik_izin_hakki(calisan3.ise_giris_tarihi, 2026),
            idari_eklenen=Decimal("0"),
            kullanilan=Decimal("7"),
        )

        db.add_all([bakiye1, bakiye2, bakiye3])
        await db.flush()

        # ── Demo İzin Talepleri ─────────────────────────────────────────────
        talepler = [
            LeaveRequest(
                id=str(uuid.uuid4()),
                employee_id="demo-employee-001",
                balance_id=bakiye1.id,
                izin_turu="yillik",
                cikis_tarihi=date(2026, 9, 1),
                giris_tarihi=date(2026, 9, 6),
                sure_gun=Decimal("3"),
                neden="Yıllık tatil",
                durum="onaylandi",
                yonetici_id="demo-manager-001",
            ),
            LeaveRequest(
                id=str(uuid.uuid4()),
                employee_id="demo-employee-001",
                balance_id=None,
                izin_turu="hastalik",
                cikis_tarihi=date(2026, 8, 15),
                giris_tarihi=date(2026, 8, 17),
                sure_gun=Decimal("2"),
                neden="Raporlu hastalık",
                durum="onaylandi",
                yonetici_id="demo-manager-001",
            ),
            LeaveRequest(
                id=str(uuid.uuid4()),
                employee_id="demo-employee-001",
                balance_id=bakiye1.id,
                izin_turu="yillik",
                cikis_tarihi=date(2026, 10, 20),
                giris_tarihi=date(2026, 10, 25),
                sure_gun=Decimal("4"),
                neden=None,
                durum="beklemede",
                yonetici_id="demo-manager-001",
            ),
            LeaveRequest(
                id=str(uuid.uuid4()),
                employee_id="demo-employee-002",
                balance_id=bakiye2.id,
                izin_turu="yillik",
                cikis_tarihi=date(2026, 10, 5),
                giris_tarihi=date(2026, 10, 12),
                sure_gun=Decimal("5"),
                neden="Tatil",
                durum="beklemede",
                yonetici_id="demo-manager-001",
            ),
            LeaveRequest(
                id=str(uuid.uuid4()),
                employee_id="demo-employee-003",
                balance_id=None,
                izin_turu="2saat",
                cikis_tarihi=date(2026, 9, 25),
                giris_tarihi=date(2026, 9, 25),
                sure_gun=Decimal("0.27"),
                neden="Doktor randevusu",
                durum="onaylandi",
                yonetici_id="demo-manager-001",
            ),
        ]
        db.add_all(talepler)
        await db.flush()

        # ── Demo Görevler ───────────────────────────────────────────────────
        from datetime import timedelta
        bugun = date.today()

        gorevler = [
            Task(
                id=str(uuid.uuid4()),
                baslik="Q4 Raporu Hazırla",
                aciklama="2026 Q4 çeyrek dönem performans raporunu hazırla ve yöneticiye sun.",
                oncelik="yuksek",
                durum="devam_ediyor",
                bitis_tarihi=bugun + timedelta(days=7),
                employee_id="demo-employee-001",
                yonetici_id="demo-manager-001",
            ),
            Task(
                id=str(uuid.uuid4()),
                baslik="Müşteri Sunumu Hazırlığı",
                aciklama="İSO Üye sunumu için slayt hazırla.",
                oncelik="orta",
                durum="atandi",
                bitis_tarihi=bugun + timedelta(days=14),
                employee_id="demo-employee-001",
                yonetici_id="demo-manager-001",
            ),
            Task(
                id=str(uuid.uuid4()),
                baslik="Kod İncelemesi",
                aciklama="Pulse modülündeki açık PR'ları incele ve geri bildirim ver.",
                oncelik="dusuk",
                durum="tamamlandi",
                bitis_tarihi=bugun - timedelta(days=5),
                employee_id="demo-employee-001",
                yonetici_id="demo-manager-001",
                tamamlandi_at=datetime.now(),
            ),
            Task(
                id=str(uuid.uuid4()),
                baslik="İK Politika Güncellemesi",
                aciklama="2026 yılı izin politikası güncellemelerini dokümana yansıt.",
                oncelik="orta",
                durum="onay_bekliyor",
                bitis_tarihi=bugun + timedelta(days=3),
                employee_id="demo-employee-002",
                yonetici_id="demo-manager-001",
                teslim_edildi_at=datetime.now(),
            ),
            Task(
                id=str(uuid.uuid4()),
                baslik="Bütçe Tablosu Güncelle",
                aciklama="Ekim ayı bütçe tablolarını güncelle ve onaya gönder.",
                oncelik="yuksek",
                durum="atandi",
                bitis_tarihi=bugun + timedelta(days=2),
                employee_id="demo-employee-003",
                yonetici_id="demo-manager-001",
            ),
        ]
        db.add_all(gorevler)
        await db.commit()

    print("✅ Seed tamamlandı!")
    print("   Çalışanlar : 6 (1 yönetici, 1 HR, 3 çalışan, 1 yeni çalışan)")
    print("   Bakiye     : 3 çalışan için 2026 bakiyesi oluşturuldu")
    print("   Talepler   : 5 örnek izin talebi eklendi")
    print("   Görevler   : 5 örnek görev eklendi (yuksek/orta/dusuk öncelikli)")
    print()
    print("   Demo IDs:")
    print("   Zeynep Yılmaz (çalışan) → demo-employee-001")
    print("   Ayşe Aydın   (yeni)     → demo-employee-ayse")
    print("   Yönetici                → demo-manager-001")
    print("   HR                      → demo-hr-001")


if __name__ == "__main__":
    asyncio.run(seed())
