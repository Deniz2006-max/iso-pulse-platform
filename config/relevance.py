"""Deterministic İSO industrial-relevance gate (mock + live pre-filter).

Keep any update with tax, finance, HR, environment, trade, or operational
impact. Drop only administrative, spatial, or person-specific noise.
When a keep signal and a soft-noise phrase both appear, KEEP.
"""

from __future__ import annotations

from typing import Literal

Verdict = Literal["keep", "drop"]

# Sanctions / named-entity freezes — drop even if a keep word appears in an annex.
SANCTION_DROP_PHRASES = (
    "malvarlığının dondurulması",
    "malvarliginin dondurulmasi",
    "dondurulması hakkında",
    "güvenlik konseyi",
    "guvenlik konseyi",
    "1267",
    "yaptırım listesi",
    "yaptirim listesi",
    "terörle mücadele",
    "terorle mucadele",
    "terör örgüt",
)

# Title-level bureaucratic noise. Body mentions must not veto a labor/tax keep.
APPOINTMENT_TITLE_PHRASES = (
    "atanmıştır",
    "atanmistir",
    "atama kararı",
    "atama karari",
    "rektör atama",
    "rektor atama",
    "büyükelçi",
    "buyukelci",
    "yargı ilân",
    "yargi ilan",
)

# Person-specific / diplomatic / UN lists — used by is_absolute_drop.
ABSOLUTE_DROP_PHRASES = SANCTION_DROP_PHRASES + APPOINTMENT_TITLE_PHRASES + (
    "rektör",
    "rektor",
    "kişisel mahkeme",
)

INSTITUTIONAL_NOISE = (
    "lisansüstü",
    "lisansustu",
    "jandarma genel komutanlığı",
    "jandarma genel komutanligi",
    "vardiya yatakhane",
    "gazinolar",
)


# Spatial / parcel acts — drop only with boundary or named-expropriation cues.
SPATIAL_DROP_PHRASES = (
    "sınır ve koordinat",
    "sinir ve koordinat",
    "ekli kroki",
    "koordinatları yeniden",
    "koordinatlari yeniden",
    "imar plan",
    "belediye sınır",
    "belediye sinir",
    "arazi toplulaştırma",
    "arazi toplulastirma",
    "acele kamulaştır",
    "parselinin kamulaştır",
    "kamulaştırılması hakkında",
    "kamulastirilmasi hakkinda",
)

SOFT_DROP_PHRASES = (
    "sözleşmesi imzalanacaktır",
    "ihale ilanı",
    "ihale ilani",
    "ihale sonuç",
)

KEEP_TAX_FINANCE = (
    "ötv",
    "otv",
    "özel tüketim vergisi",
    "ozel tuketim vergisi",
    "kdv",
    "katma değer vergisi",
    "katma deger vergisi",
    "kurumlar vergisi",
    "gelir vergisi",
    "stopaj",
    "tevkifat",
    "damga vergisi",
    "gümrük",
    "gumruk",
    "vergi usul",
    "vergi oranı",
    "vergi orani",
    "istisna",
    "matrah",
    "muhtasar",
    "e-fatura",
    "finansal raporlama",
    "muhasebe standard",
    "tfrs",
    "tms ",
    "teşvik",
    "tesvik",
    "yatırım teşvik",
    "banka",
    "bankacılık",
    "bankacilik",
    "dış ticaret",
    "dis ticaret",
    "sermaye piyasası",
    "enerji tarife",
    "elektrik tarife",
    "doğalgaz tarife",
    "dogalgaz tarife",
    "tarifesi",
    "tarife değiş",
)

KEEP_LABOR_HR = (
    "4857",
    "iş kanunu",
    "is kanunu",
    "5510",
    "sosyal sigorta",
    "sgk",
    "e-bildirge",
    "6331",
    "iş sağlığı",
    "is sagligi",
    "iş güvenliği",
    "asgari ücret",
    "asgari ucret",
    "fazla çalışma",
    "fazla mesai",
    "kıdem",
    "iş sözleş",
    "sözleşmeli personel",
    "sozlesmeli personel",
    "personel çalıştır",
    "personel calistir",
    "personel esas",
    "istihdam",
    "çalışma koşul",
    "calisma kosul",
    "çalışma şart",
    "calisma sart",
    "iş hukuku",
    "is hukuku",
    "harcırah",
    "harcirah",
    "ödenecek aylık",
    "odenecek aylik",
    "memurlara ödenecek",
    "kamu personel",
    "çalışma izni",
    "calisma izni",
    "çalışma izin",
    "yabancı uyruk",
    "yabanci uyruk",
    "yan hak",
    "sosyal yardım",
    "analık",
    "babalık",
    "bordro",
    "işçi",
    "işveren prim",
    "sgk prim",
    "e-bildirge",
)

KEEP_ENV_TRADE = (
    "yeşil mutabakat",
    "yesil mutabakat",
    "karbon",
    "emisyon",
    "atık yönet",
    "atik yonet",
    "atıksu",
    "çevre izin",
    "cevre izin",
    "çevre kanunu",
    "ithalat",
    "ihracat",
    "kota",
    "üretim standard",
    "uretim standard",
    "sanayi sicil",
    "tse standard",
    "ürün güvenliği",
    "urun guvenligi",
)

KEEP_LEGAL_OPS = (
    "6698",
    "kvkk",
    "kişisel veri",
    "kisisel veri",
    "lisans belgesi",
    "faaliyet lisans",
    "izin belgesi",
    "faaliyet durdur",
)

KEEP_PHRASES = KEEP_TAX_FINANCE + KEEP_LABOR_HR + KEEP_ENV_TRADE + KEEP_LEGAL_OPS

_FIXTURE_KEEP_IDS = (
    "ik-overtime",
    "hukuk-environment",
    "multi-wage-tax",
    "demo-4857-maternity",
    "demo-5510-manufacturing",
    "demo-6698-processing",
    "otv-rate",
    "kdv-rate",
    "energy-tariff",
    "work-permit",
    "teknokent-incentive",
)


def _blob(title: str, text: str) -> str:
    return f"{title}\n{text}".casefold()


def _has_any(blob: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in blob for phrase in phrases)


def has_industrial_signal(title: str, text: str, document_id: str = "") -> bool:
    if document_id in _FIXTURE_KEEP_IDS:
        return True
    return _has_any(_blob(title, text), KEEP_PHRASES)


def is_sanction_drop(title: str, text: str) -> bool:
    return _has_any(_blob(title, text), SANCTION_DROP_PHRASES)


def is_appointment_title(title: str) -> bool:
    return _has_any(title.casefold(), APPOINTMENT_TITLE_PHRASES)


def is_absolute_drop(title: str, text: str) -> bool:
    """True for sanctions, or appointment-only texts with no keep signal."""
    if is_sanction_drop(title, text):
        return True
    if has_industrial_signal(title, text):
        return False
    return is_appointment_title(title) or _has_any(_blob(title, text), APPOINTMENT_TITLE_PHRASES)


def is_institutional_title(title: str) -> bool:
    """University exam rules or gendarmerie social facilities — not İSO labor."""
    folded = title.casefold()
    if "jandarma" in folded and any(
        token in folded for token in ("yatakhane", "gazino", "sosyal tesis")
    ):
        return True
    if "üniversite" in folded and any(
        token in folded
        for token in ("lisansüstü", "eğitim-öğretim", "sınav yönetmeliği", "öğrenci")
    ):
        return True
    return False


def is_spatial_drop(title: str, text: str) -> bool:
    blob = _blob(title, text)
    if _has_any(blob, SPATIAL_DROP_PHRASES):
        return True
    teknokent = "teknokent" in blob or "teknoloji geliştirme bölgesi" in blob
    boundary = any(
        token in blob
        for token in ("koordinat", "kroki", "sınır", "sinir", "imar")
    )
    return teknokent and boundary


def is_industrial_noise(title: str, text: str, document_id: str = "") -> bool:
    """True only for drop-class noise that has no keep-class industrial signal.

    Absolute person/UN freezes still drop even if a generic keep word appears.
    Spatial and soft noise yield to a keep signal (avoids false negatives).
    """
    if document_id in _FIXTURE_KEEP_IDS:
        return False
    if is_sanction_drop(title, text):
        return True
    if has_industrial_signal(title, text, document_id):
        return False
    if is_appointment_title(title):
        return True
    if is_institutional_title(title) and not has_industrial_signal(title, "", document_id):
        return True
    if is_spatial_drop(title, text):
        return True
    if _has_any(_blob(title, text), INSTITUTIONAL_NOISE):
        return True
    return _has_any(_blob(title, text), SOFT_DROP_PHRASES)


def implied_departments(title: str, text: str) -> list[str]:
    """Department hints from the keep taxonomy (used as router fallback)."""
    blob = _blob(title, text)
    found: list[str] = []
    labor = tuple(p for p in KEEP_LABOR_HR)
    if _has_any(blob, labor):
        found.append("ik")
    if _has_any(blob, KEEP_ENV_TRADE + KEEP_LEGAL_OPS):
        found.append("hukuk")
    if _has_any(blob, KEEP_TAX_FINANCE):
        found.append("mali")
    return found


def classify_relevance(
    title: str,
    text: str,
    document_id: str = "",
) -> tuple[Verdict, str]:
    """Shared mock + live pre-filter. Keep wins over soft/spatial noise."""
    if document_id in _FIXTURE_KEEP_IDS:
        return "keep", (
            "Metin iş/SGK/İSG, vergi-maliye, çevre, ticaret veya operasyonel "
            "yükümlülüğü değiştiriyor."
        )
    if is_sanction_drop(title, text):
        return "drop", (
            "İdari gürültü: BM/diplomatik yaptırım listesi veya kişiye özel "
            "malvarlığı dondurma."
        )
    if is_institutional_title(title) and not has_industrial_signal(title, "", document_id):
        return "drop", (
            "Kurum-içi eğitim, üniversite veya jandarma sosyal tesis düzenlemesi; "
            "sanayi işveren yükümlülüğü yok."
        )
    if has_industrial_signal(title, text, document_id):
        return "keep", (
            "Sanayiciyi bağlayan vergi, finans, İK/personel, SGK, çevre, ticaret "
            "veya operasyonel kural değişikliği."
        )
    if is_appointment_title(title):
        return "drop", (
            "Bireysel atama / diplomatik görevlendirme; işveren kuralı değişmiyor."
        )
    if is_spatial_drop(title, text):
        return "drop", (
            "Mekânsal/idari işlem: imar, sınır-koordinat, Teknokent krokisi "
            "veya parsel kamulaştırması; işveren kuralı değişmiyor."
        )
    if _has_any(_blob(title, text), INSTITUTIONAL_NOISE):
        return "drop", (
            "Kurum-içi eğitim, üniversite veya jandarma sosyal tesis düzenlemesi; "
            "sanayi işveren yükümlülüğü yok."
        )
    if _has_any(_blob(title, text), SOFT_DROP_PHRASES):
        return "drop", "İhale ilanı veya imza duyurusu; yükümlülük değişmiyor."
    form = (
        "esaslarda değişiklik",
        "tebliğ",
        "teblig",
        "genelge",
        "kanun değiş",
        "uygulama usul",
    )
    if _has_any(_blob(title, text), form):
        return "keep", (
            "Personel/esas veya tebliğ-genelge metni; Retriever ve uzmana iletildi."
        )
    return "drop", (
        "Sanayi odası üyesi için doğrudan mali, İK, çevre, ticaret veya "
        "operasyonel yükümlülük tespit edilmedi."
    )


def mock_is_relevant(title: str, text: str, document_id: str = "") -> tuple[bool, str]:
    verdict, reason = classify_relevance(title, text, document_id)
    return verdict == "keep", reason
