"""
Türkçe doğal dil ayrıştırıcı — tarih, izin türü, niyet tespiti
"""
import re
from datetime import date, timedelta
from typing import Optional


# ─── Türkçe ay isimleri ──────────────────────────────────────────────────────
AYLAR = {
    "ocak": 1, "şubat": 2, "mart": 3, "nisan": 4,
    "mayıs": 5, "haziran": 6, "temmuz": 7, "ağustos": 8,
    "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12,
    "ocakta": 1, "şubatta": 2, "martta": 3, "nisanda": 4,
    "mayısta": 5, "haziranda": 6, "temmuzda": 7, "ağustosta": 8,
    "eylülde": 9, "ekimde": 10, "kasımda": 11, "aralıkta": 12,
}

# ─── İzin türü anahtar kelimeleri ────────────────────────────────────────────
IZIN_TURU_MAP = {
    "yillik": ["yıllık", "yıllık izin", "yillik", "senelik"],
    "2saat": ["2 saat", "iki saat", "2saat", "kısa izin"],
    "2saat_uzeri": ["mazeret", "2 saatten fazla", "yarım gün", "2saat_uzeri"],
    "evlilik": ["evlilik", "nikah", "düğün", "evleneceğim"],
    "olum": ["ölüm", "vefat", "cenaze"],
    # "baba_dogum" kodu hem doğal dil hem hızlı-aksiyon değeri olarak tanınır
    "baba_dogum": [
        "babalık", "doğum babalık", "bebek oldu",
        "baba_dogum", "babalik", "babalık izni", "babalık izin",
        "babalık izni almak istiyorum", "babalık izni almak",
    ],
    # "dogum_kadin" kodu hem doğal dil hem hızlı-aksiyon değeri olarak tanınır
    "dogum_kadin": [
        "doğum", "analık", "hamile", "bebek bekliyorum",
        "doğum izni", "dogum_kadin", "doğum izni almak",
    ],
    "ucretsiz": ["ücretsiz", "maaşsız", "ucretsiz"],
    "hastalik": ["hastalık", "hasta", "rapor", "doktor", "hastalik"],
    "idari": ["idari", "resmi"],
}

# ─── Kapsam dışı konu algılama ───────────────────────────────────────────────
IZIN_KONULAR = [
    "izin", "tatil", "gün", "tarih", "talep", "başvur", "bakiye",
    "iznim", "izinsiz", "kıdem", "hakk", "hak", "kaç gün",
    "yıllık", "evlilik", "babalık", "doğum", "ölüm", "mazeret",
    "hastalık", "rapor", "ücretsiz", "idari",
    "ne zaman", "tarihte", "hafta", "ay", "bugün", "yarın"
]

KAPSAM_DISI_SINYALLER = [
    "maaş", "ücret", "bordro", "prim", "performans", "terfi",
    "işten", "istifa", "sözleşme", "sağlık sigortası", "sgk",
    "vergi", "hukuk", "dava", "şikayet",
    "proje", "görev", "kod", "yazılım", "toplantı",
    "staj", "referans", "belge", "cvim",
    "yemek", "servis", "araç", "giderleri",
]


def normalize(text: str) -> str:
    return text.lower().strip()


def detect_intent(msg: str) -> str:
    """
    'izin_al' | 'izin_bilgi' | 'kapsam_disi' | 'selam' döndürür.
    """
    m = normalize(msg)

    # Selamlama
    if m in ["merhaba", "selam", "günaydın", "iyi günler", "hello", "hi"] or \
       (len(m) < 20 and not any(k in m for k in IZIN_KONULAR)):
        # Basit selamlama ise karşıla
        if any(s in m for s in ["merhaba", "selam", "günaydın", "iyi", "nasılsın"]):
            return "selam"

    # İzin talebi niyeti
    TALEP_SINYALLER = [
        "izin almak", "izin talep", "izin istiyorum", "izin almak istiyorum",
        "izin alabilir miyim", "izne çıkmak", "izin kullanmak", "gün izin",
        "günlük izin", "hafta izin", "tatile", "izinli olacağım",
    ]
    if any(s in m for s in TALEP_SINYALLER):
        return "izin_al"

    # Kapsam dışı sinyal var ama izin konusu yok → kapsam dışı
    if any(s in m for s in KAPSAM_DISI_SINYALLER) and \
       not any(k in m for k in IZIN_KONULAR):
        return "kapsam_disi"

    # İzin konusu var → işle
    if any(k in m for k in IZIN_KONULAR):
        return "izin_al"

    # Evet / Hayır yanıtları — konuşma akışında yakalanır
    return "belirsiz"


def detect_leave_type(msg: str) -> Optional[str]:
    m = normalize(msg)
    for kod, keywords in IZIN_TURU_MAP.items():
        if any(kw in m for kw in keywords):
            return kod
    return None


# ─── Tarih ayrıştırma ────────────────────────────────────────────────────────
def parse_date_from_text(text: str, referans: date = None) -> Optional[date]:
    """
    "5 Ekim", "15 kasım 2026", "yarın", "pazartesi" gibi ifadeleri ayrıştırır.
    """
    if referans is None:
        referans = date.today()

    t = normalize(text)

    # Yarın / bugün
    if "yarın" in t:
        return referans + timedelta(days=1)
    if "bugün" in t:
        return referans

    # "gelecek hafta pazartesi" gibi ifadeler
    GUNLER = {"pazartesi": 0, "salı": 1, "çarşamba": 2, "perşembe": 3,
               "cuma": 4, "cumartesi": 5, "pazar": 6}
    for gun_adi, gun_no in GUNLER.items():
        if gun_adi in t:
            bugun_no = referans.weekday()
            fark = (gun_no - bugun_no) % 7
            if fark == 0:
                fark = 7
            return referans + timedelta(days=fark)

    # "5 Ekim", "5 ekim 2026", "5'inci ekim" gibi
    for ay_adi, ay_no in AYLAR.items():
        pattern = rf"(\d{{1,2}})\s*(?:'[a-zçğışöü]{{1,4}}\s*)?{ay_adi}(?:\s*(\d{{4}}))?"
        m = re.search(pattern, t)
        if m:
            gun = int(m.group(1))
            yil = int(m.group(2)) if m.group(2) else referans.year
            try:
                d = date(yil, ay_no, gun)
                # Geçmiş tarih ise gelecek yıla taşı
                if d < referans and not m.group(2):
                    d = date(yil + 1, ay_no, gun)
                return d
            except ValueError:
                continue

    # "YYYY-MM-DD" ya da "DD.MM.YYYY"
    iso = re.search(r"(\d{4})-(\d{2})-(\d{2})", t)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            pass

    tr_fmt = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", t)
    if tr_fmt:
        try:
            return date(int(tr_fmt.group(3)), int(tr_fmt.group(2)), int(tr_fmt.group(1)))
        except ValueError:
            pass

    return None


def parse_date_range(msg: str):
    """
    "5 Ekim'den 10 Ekim'e kadar", "5-10 Ekim", "5 ile 10 Ekim arası" gibi.
    Tuple[Optional[date], Optional[date]] döndürür: (cikis, giris)
    """
    m = normalize(msg)

    # "X-Y Ay" veya "X ile Y arası Ay"
    for ay_adi, ay_no in AYLAR.items():
        # "5-10 ekim" veya "5 - 10 ekim"
        p1 = rf"(\d{{1,2}})\s*[-–]\s*(\d{{1,2}})\s*{ay_adi}"
        match = re.search(p1, m)
        if match:
            g1, g2 = int(match.group(1)), int(match.group(2))
            yil = date.today().year
            try:
                d1 = date(yil, ay_no, g1)
                d2 = date(yil, ay_no, g2) + timedelta(days=1)
                if d1 < date.today():
                    d1 = date(yil + 1, ay_no, g1)
                    d2 = date(yil + 1, ay_no, g2) + timedelta(days=1)
                return d1, d2
            except ValueError:
                pass

        # "X aydan Y aya kadar" (farklı aylar)
        p2 = rf"(\d{{1,2}})\s*{ay_adi}.{{0,20}}?(\d{{1,2}})\s+(\w+)\s*(kadar|e kadar|'e kadar)?"
        match2 = re.search(p2, m)
        if match2:
            d1 = parse_date_from_text(f"{match2.group(1)} {ay_adi}")
            # Geriye kalan kısmı ayrıştır
            rest = m[match2.end():]
            d2_candidate = parse_date_from_text(rest)
            if d1 and d2_candidate:
                return d1, d2_candidate + timedelta(days=1)

    # "Xden Ye kadar" genel pattern — iki ayrı tarih dene
    dates_found = []
    for ay_adi in AYLAR:
        pattern = rf"\d{{1,2}}\s*(?:'[a-zçğışöü]{{1,4}}\s*)?{ay_adi}(?:\s*\d{{4}})?"
        for match in re.finditer(pattern, m):
            d = parse_date_from_text(match.group(0))
            if d:
                dates_found.append(d)

    if len(dates_found) >= 2:
        dates_found.sort()
        return dates_found[0], dates_found[-1] + timedelta(days=1)

    if len(dates_found) == 1:
        return dates_found[0], None

    return None, None


# ─── Kadın adı tahmini (cinsiyet hak kontrolü için) ──────────────────────────
KADIN_ADI_ONEKLERI = {
    "amira", "selin", "zeynep", "ayşe", "fatma", "elif", "esra", "gül",
    "nur", "özlem", "şeyma", "büşra", "merve", "tuğba", "seda",
    "ebru", "melek", "cansu", "derya", "berna", "dilek", "nihal",
    "yasemin", "leyla", "sibel", "sevgi", "arzu", "nazan", "nevin",
    "hatice", "hacer", "rüya", "serap", "aslı", "bahar", "filiz",
    "gamze", "irem", "kübra", "lale", "müge", "nur", "pınar",
}

ERKEK_ADI_ONEKLERI = {
    "mehmet", "ahmet", "mustafa", "ali", "hüseyin", "ibrahim",
    "osman", "murat", "emre", "can", "berkay", "burak", "deniz",
    "enes", "furkan", "hasan", "kemal", "koray", "volkan", "yusuf",
    "serhat", "onur", "ömer", "recep", "suat", "tayfun", "uğur",
}


def cinsiyet_tahmin(ad_soyad: str) -> str:
    """'kadin' | 'erkek' | 'bilinmiyor' döndürür."""
    ad = ad_soyad.strip().lower().split()[0]
    if ad in KADIN_ADI_ONEKLERI:
        return "kadin"
    if ad in ERKEK_ADI_ONEKLERI:
        return "erkek"
    return "bilinmiyor"
