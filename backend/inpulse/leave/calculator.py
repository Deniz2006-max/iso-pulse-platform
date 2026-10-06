"""
İzin Hesaplama Motoru — 4857 sayılı İş Kanunu
Kıdem yılına göre yıllık izin hakkı belirlenir.
"""
from datetime import date
from decimal import Decimal


# ─── Kıdem → Yıllık İzin Hakkı (İş Kanunu Madde 53) ────────────────────────
def yillik_izin_hakki(ise_giris: date, referans_yil: int = None) -> Decimal:
    """
    Çalışanın kıdem yılına göre yıllık izin hakkını hesaplar.

    Kıdem < 5 yıl  → 14 iş günü
    5 ≤ kıdem < 15 → 20 iş günü
    kıdem ≥ 15     → 26 iş günü
    18 yaş altı ve 50 yaş üstü → minimum 20 gün (doğum tarihi gerekli, burada kıdem bazlı)
    """
    if referans_yil is None:
        referans_yil = date.today().year

    referans = date(referans_yil, 1, 1)
    kidem_yil = (referans - ise_giris).days / 365.25

    if kidem_yil < 1:
        # Henüz 1 yılını doldurmamış — izin hakkı yok
        return Decimal("0")
    elif kidem_yil < 5:
        return Decimal("14")
    elif kidem_yil < 15:
        return Decimal("20")
    else:
        return Decimal("26")


def kidem_yil_hesapla(ise_giris: date, referans_yil: int = None) -> float:
    """Kıdem yılını ondalıklı olarak döndürür."""
    if referans_yil is None:
        referans_yil = date.today().year
    referans = date(referans_yil, 1, 1)
    return round((referans - ise_giris).days / 365.25, 2)


# ─── İzin türü bazlı hak kontrolü ────────────────────────────────────────────
IZIN_TURLERI = {
    "yillik": {
        "label": "Yıllık İzin",
        "max_gun": None,        # Bakiyeye bağlı
        "bakiyeden_dusuler": True,
        "aciklama": "Kıdeme göre 14/20/26 iş günü",
    },
    "2saat": {
        "label": "2 Saat İzin",
        "max_gun": Decimal("0.27"),   # 2h / 7.5h
        "bakiyeden_dusuler": False,   # Politikaya göre değişebilir
        "aciklama": "Günlük 2 saat — tam iş günü sayılmaz",
    },
    "2saat_uzeri": {
        "label": "2 Saat Üzeri Mazeret İzni",
        "max_gun": None,
        "bakiyeden_dusuler": True,
        "aciklama": "2 saatten uzun mazeret izni",
    },
    "evlilik": {
        "label": "Evlilik İzni",
        "max_gun": Decimal("3"),
        "bakiyeden_dusuler": False,
        "aciklama": "İş Kanunu Md.74 — 3 iş günü",
    },
    "olum": {
        "label": "Ölüm İzni",
        "max_gun": Decimal("3"),
        "bakiyeden_dusuler": False,
        "aciklama": "Eş, çocuk, anne, baba, kardeş vefatı — 3 iş günü",
    },
    "baba_dogum": {
        "label": "Babalık İzni",
        "max_gun": Decimal("5"),
        "bakiyeden_dusuler": False,
        "aciklama": "2022 yasal değişikliği — 5 iş günü",
    },
    "dogum_kadin": {
        "label": "Doğum İzni (Kadın)",
        "max_gun": Decimal("112"),   # 16 hafta (8+8)
        "bakiyeden_dusuler": False,
        "aciklama": "Doğum öncesi 8 hafta + doğum sonrası 8 hafta",
    },
    "ucretsiz": {
        "label": "Ücretsiz İzin",
        "max_gun": None,
        "bakiyeden_dusuler": False,
        "aciklama": "Çalışan talebi, işveren onayı gerekir",
    },
    "hastalik": {
        "label": "Hastalık İzni",
        "max_gun": None,
        "bakiyeden_dusuler": False,
        "aciklama": "Raporlu hastalık izni",
    },
    "idari": {
        "label": "İdari İzin",
        "max_gun": None,
        "bakiyeden_dusuler": False,
        "aciklama": "İşveren kararıyla verilen ek izin",
    },
}


def izin_turu_bilgi(izin_turu: str) -> dict:
    return IZIN_TURLERI.get(izin_turu, {})


def bakiyeden_dusurmeli(izin_turu: str) -> bool:
    """Bu izin türü yıllık bakiyeden düşülmeli mi?"""
    bilgi = IZIN_TURLERI.get(izin_turu, {})
    return bilgi.get("bakiyeden_dusuler", False)


def bakiye_hesapla(
    onceki_yildan: Decimal,
    yillik_hak: Decimal,
    idari_eklenen: Decimal,
    kullanilan: Decimal,
) -> Decimal:
    return onceki_yildan + yillik_hak + idari_eklenen - kullanilan
