"""
Outpulse — Mevzuat Radar API
GET  /api/v1/radar/mevzuat          → Liste (filtreli)
GET  /api/v1/radar/mevzuat/{id}     → Tek kayıt
POST /api/v1/radar/scan             → Manuel tarama tetikle
GET  /api/v1/radar/kaynaklar        → Kaynak listesi
GET  /api/v1/radar/search           → Arama (mock)
"""
from typing import Optional
from datetime import date

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from outpulse.scraper import DEMO_MEVZUAT, KAYNAKLAR, _icerik_hash, kaynaklari_tara
import uuid as uuid_mod

outpulse_router = APIRouter(prefix="/api/v1/radar", tags=["outpulse"])


# ─── Şemalar ────────────────────────────────────────────────────────────────
class MevzuatItem(BaseModel):
    id: str
    kaynak: str
    baslik: str
    url: Optional[str]
    ozet: Optional[str]
    kategori: Optional[str]
    yayin_tarihi: Optional[str]


class KaynakInfo(BaseModel):
    kod: str
    ad: str
    url: str


# ─── Yardımcı: demo listeden sınırlı kayıtlar ────────────────────────────────
def _demo_liste() -> list[MevzuatItem]:
    items = []
    for i, m in enumerate(DEMO_MEVZUAT):
        items.append(MevzuatItem(
            id=str(uuid_mod.uuid5(uuid_mod.NAMESPACE_URL, m["url"])),
            kaynak=m["kaynak"],
            baslik=m["baslik"],
            url=m["url"],
            ozet=m["ozet"],
            kategori=m["kategori"],
            yayin_tarihi=m["yayin_tarihi"],
        ))
    return items


# ─── Endpoint'ler ────────────────────────────────────────────────────────────
@outpulse_router.get("/health")
async def radar_health():
    return {"status": "ok", "module": "outpulse-radar"}


@outpulse_router.get("/kaynaklar", response_model=list[KaynakInfo])
async def list_kaynaklar():
    """Desteklenen mevzuat kaynakları."""
    return [
        KaynakInfo(kod=kod, ad=bilgi["ad"], url=bilgi["url"])
        for kod, bilgi in KAYNAKLAR.items()
    ]


@outpulse_router.get("/mevzuat", response_model=list[MevzuatItem])
async def list_mevzuat(
    kategori: Optional[str] = Query(None, description="ik | mali | hukuk"),
    kaynak: Optional[str] = Query(None, description="resmi_gazete | sgk | csgb | mevzuat"),
    q: Optional[str] = Query(None, description="Başlık araması"),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Mevzuat kayıtlarını listeler.
    Demo modda mock veriden döndürür; üretimde PostgreSQL + ChromaDB kullanılır.
    """
    items = _demo_liste()

    if kategori:
        items = [i for i in items if i.kategori == kategori]
    if kaynak:
        items = [i for i in items if i.kaynak == kaynak]
    if q:
        q_lower = q.lower()
        items = [i for i in items if q_lower in i.baslik.lower() or (i.ozet and q_lower in i.ozet.lower())]

    return items[:limit]


@outpulse_router.get("/mevzuat/{kayit_id}", response_model=MevzuatItem)
async def get_mevzuat(kayit_id: str):
    """Tek mevzuat kaydını döndürür."""
    for m in DEMO_MEVZUAT:
        item_id = str(uuid_mod.uuid5(uuid_mod.NAMESPACE_URL, m["url"]))
        if item_id == kayit_id:
            return MevzuatItem(
                id=item_id,
                kaynak=m["kaynak"],
                baslik=m["baslik"],
                url=m["url"],
                ozet=m["ozet"],
                kategori=m["kategori"],
                yayin_tarihi=m["yayin_tarihi"],
            )
    raise HTTPException(status_code=404, detail="Kayıt bulunamadı")


@outpulse_router.get("/search", response_model=list[MevzuatItem])
async def search_mevzuat(
    q: str = Query(..., min_length=2, description="Aranacak metin"),
):
    """
    Mevzuat başlık ve özet içinde arama yapar.
    Üretimde ChromaDB semantik arama kullanılır.
    """
    q_lower = q.lower()
    results = [
        MevzuatItem(
            id=str(uuid_mod.uuid5(uuid_mod.NAMESPACE_URL, m["url"])),
            kaynak=m["kaynak"],
            baslik=m["baslik"],
            url=m["url"],
            ozet=m["ozet"],
            kategori=m["kategori"],
            yayin_tarihi=m["yayin_tarihi"],
        )
        for m in DEMO_MEVZUAT
        if q_lower in m["baslik"].lower() or q_lower in (m["ozet"] or "").lower()
    ]
    return results


@outpulse_router.post("/scan", summary="Manuel mevzuat taraması başlat")
async def manual_scan():
    """
    Mevzuat kaynaklarını tarar ve yeni kayıtları DB'ye ekler.
    Demo modda mock sonuç döndürür.
    """
    kayitlar = await kaynaklari_tara()
    return {
        "status": "tamamlandi",
        "taranan_kaynak_sayisi": len(KAYNAKLAR),
        "bulunan_kayit": len(kayitlar),
        "yeni_kayit": len(kayitlar),   # demo: hepsi yeni sayılır
    }
