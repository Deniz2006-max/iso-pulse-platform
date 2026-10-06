"""
İSO Pulse Zamanlayıcı
- Outpulse: Her gece 02:00 mevzuat taraması
- Inpulse: Her sabah 09:00 doğum günü & yıldönümü bildirimleri
main.py lifespan'ında başlatılır.
"""
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from outpulse.scraper import kaynaklari_tara

scheduler = AsyncIOScheduler(timezone="Europe/Istanbul")


async def _gece_tarama():
    """Her gece 02:00'de çalışan mevzuat taraması."""
    print(f"[Outpulse] Mevzuat taraması başladı — {datetime.now():%Y-%m-%d %H:%M}")
    try:
        kayitlar = await kaynaklari_tara()
        print(f"[Outpulse] {len(kayitlar)} kayıt işlendi.")
    except Exception as exc:
        print(f"[Outpulse] Tarama hatası: {exc}")


async def _sabah_kutlama():
    """Her sabah 09:00'da doğum günü ve yıldönümü bildirimlerini gönder."""
    print(f"[Inpulse] Kutlama bildirimleri kontrol ediliyor — {datetime.now():%Y-%m-%d %H:%M}")
    try:
        # Lokal import — döngüsel import önlemek için
        from db.database import AsyncSessionLocal
        from inpulse.celebrations.endpoints import notify_celebrations
        from fastapi import BackgroundTasks

        async with AsyncSessionLocal() as db:
            bg = BackgroundTasks()
            sonuc = await notify_celebrations(background_tasks=bg, db=db)
            # Bekleyen arka plan görevlerini çalıştır
            for task in bg.tasks:
                try:
                    import asyncio
                    if asyncio.iscoroutinefunction(task.func):
                        await task.func(*task.args, **task.kwargs)
                    else:
                        task.func(*task.args, **task.kwargs)
                except Exception as e:
                    print(f"[Inpulse] Arka plan görevi hatası: {e}")
            print(f"[Inpulse] {sonuc['gonderilen_sayisi']} kutlama bildirimi gönderildi.")
    except Exception as exc:
        print(f"[Inpulse] Kutlama bildirimi hatası: {exc}")


def start_scheduler():
    """Scheduler'ı başlat (main.py lifespan'ından çağrılır)."""
    # Mevzuat taraması — her gece 02:00
    scheduler.add_job(
        _gece_tarama,
        CronTrigger(hour=2, minute=0),
        id="gece_tarama",
        replace_existing=True,
    )
    # Kutlama bildirimleri — her sabah 09:00
    scheduler.add_job(
        _sabah_kutlama,
        CronTrigger(hour=9, minute=0),
        id="sabah_kutlama",
        replace_existing=True,
    )
    scheduler.start()
    print("[Scheduler] Başlatıldı — 02:00 mevzuat, 09:00 kutlama bildirimleri aktif.")


def stop_scheduler():
    """Scheduler'ı durdur."""
    if scheduler.running:
        scheduler.shutdown(wait=False)
