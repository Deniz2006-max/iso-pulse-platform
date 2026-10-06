"""
Outpulse Mevzuat Tarayıcısı
RSS / HTTP tabanlı — Resmi Gazete, SGK, ÇSGB'den başlıkları çeker.
Gerçek scraping yerine şimdilik mock data üretir; üretimde httpx + feedparser kullanılır.
"""
import hashlib
import uuid
from datetime import date, datetime
from typing import Any

import httpx

# ─── Mock Kaynak Katalog ─────────────────────────────────────────────────────
KAYNAKLAR = {
    "resmi_gazete": {
        "url": "https://www.resmigazete.gov.tr/",
        "rss": "https://www.resmigazete.gov.tr/rss/son_ekler.xml",
        "ad": "Resmî Gazete",
    },
    "sgk": {
        "url": "https://www.sgk.gov.tr/",
        "rss": None,
        "ad": "Sosyal Güvenlik Kurumu",
    },
    "csgb": {
        "url": "https://www.csgb.gov.tr/",
        "rss": "https://www.csgb.gov.tr/rss.xml",
        "ad": "Çalışma ve Sosyal Güvenlik Bakanlığı",
    },
    "mevzuat": {
        "url": "https://www.mevzuat.gov.tr/",
        "rss": None,
        "ad": "Mevzuat Bilgi Sistemi",
    },
}

# ─── Demo mevzuat kayıtları ──────────────────────────────────────────────────
DEMO_MEVZUAT = [
    {
        "kaynak": "resmi_gazete",
        "baslik": "4857 Sayılı İş Kanununda Değişiklik — Babalık İzni 5 İş Gününe Çıkarıldı",
        "url": "https://www.resmigazete.gov.tr/eskiler/2022/01/20220115.htm",
        "ozet": "İş Kanunu'nun 74. maddesi değiştirilerek babalık izninin süresi 3'ten 5 iş gününe yükseltilmiştir.",
        "kategori": "ik",
        "yayin_tarihi": date(2022, 1, 15).isoformat(),
    },
    {
        "kaynak": "sgk",
        "baslik": "2026 Yılı Asgari Ücret 22.104 TL Olarak Belirlendi",
        "url": "https://www.sgk.gov.tr/sgk/content/conn/WCNLT1_UCM/path/Contribution%20Folders/webcontent/kategori/haberler/2026-asgari-ucret.htm",
        "ozet": "Asgari Ücret Tespit Komisyonu kararıyla 01.01.2026 tarihinden itibaren aylık brüt asgari ücret 22.104 TL olarak belirlenmiştir.",
        "kategori": "mali",
        "yayin_tarihi": date(2025, 12, 28).isoformat(),
    },
    {
        "kaynak": "csgb",
        "baslik": "Uzaktan Çalışma Yönetmeliğinde Güncelleme — Yeni Ekipman Yükümlülükleri",
        "url": "https://www.csgb.gov.tr/haberler/uzaktan-calisma-yonetmeligi-guncellendi/",
        "ozet": "Uzaktan çalışma yönetmeliğinde yapılan değişiklikle işverenin uzaktan çalışan işçilere sağlaması gereken ekipman ve katkı payı yükümlülükleri netleştirilmiştir.",
        "kategori": "ik",
        "yayin_tarihi": date(2026, 3, 10).isoformat(),
    },
    {
        "kaynak": "mevzuat",
        "baslik": "Kısa Çalışma Ödeneği Uygulamasında Süre Uzatımı",
        "url": "https://www.mevzuat.gov.tr/mevzuat?MevzuatNo=31234&MevzuatTur=7",
        "ozet": "Covid sonrası uygulanan kısa çalışma ödeneği süre uzatımı 6 ay daha devam edecek.",
        "kategori": "mali",
        "yayin_tarihi": date(2026, 2, 20).isoformat(),
    },
    {
        "kaynak": "csgb",
        "baslik": "İş Sağlığı ve Güvenliği Kanunu Revize — Risk Değerlendirmesi Zorunlu",
        "url": "https://www.csgb.gov.tr/isg/risk-degerlendirmesi-2026/",
        "ozet": "6331 sayılı İSG Kanunu çerçevesinde tüm işyerlerinde yıllık risk değerlendirmesi belgesi hazırlanması zorunlu hale getirilmiştir.",
        "kategori": "hukuk",
        "yayin_tarihi": date(2026, 6, 1).isoformat(),
    },
    {
        "kaynak": "sgk",
        "baslik": "SGK Prim Oranları — 2026 II. Dönem Güncellemesi",
        "url": "https://www.sgk.gov.tr/prim/2026-II",
        "ozet": "İşçi ve işveren prim oranlarında 2026 II. dönem için güncelleme yapılmıştır. İşveren hissesi %20.5 olarak sabitlenmiştir.",
        "kategori": "mali",
        "yayin_tarihi": date(2026, 7, 1).isoformat(),
    },
]


def _icerik_hash(baslik: str, url: str) -> str:
    return hashlib.sha256(f"{baslik}{url}".encode()).hexdigest()


async def kaynaklari_tara() -> list[dict[str, Any]]:
    """
    Gerçek ortamda RSS/HTTP taraması yapar.
    Bu demo versiyonda mock kayıtları döndürür.
    Üretimde: httpx ile RSS fetch → feedparser → DB insert
    """
    bugun = date.today()
    kayitlar = []
    for item in DEMO_MEVZUAT:
        kayitlar.append({
            "id": str(uuid.uuid4()),
            "kaynak": item["kaynak"],
            "baslik": item["baslik"],
            "url": item["url"],
            "icerik_hash": _icerik_hash(item["baslik"], item["url"]),
            "ozet": item["ozet"],
            "kategori": item["kategori"],
            "yayin_tarihi": item["yayin_tarihi"],
            "chroma_id": None,
            "bildirim_gonderildi": False,
            "olusturma": datetime.now().isoformat(),
        })
    return kayitlar


async def _rss_fetch(url: str) -> str | None:
    """Gerçek RSS fetch — demo'da kullanılmaz."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
            if r.status_code == 200:
                return r.text
    except Exception:
        pass
    return None
