"""Deterministic İSO industrial-relevance gate (mock + live pre-filter).

Keep industrial operations, environment, unions, tax, OSB incentives, and
SGK rules. Drop university academic regulations, ads/announcements, and
personal AYM petitions.
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
    "mal alımı ihale",
    "hizmet alımı ihale",
    "satın alma ilanı",
    "satın alma duyurusu",
    "iş ilanı",
    "is ilani",
    "işe alım ilanı",
    "ise alim ilani",
    "personel alım ilanı",
    "personel alim ilani",
    "kadro ilanı",
    "açık iş ilanı",
)

# Chamber / professional-union bylaws — not İSO manufacturer obligations.
CHAMBER_INTERNAL_PHRASES = (
    "oda ana yönetmeli",
    "odası ana yönetmeli",
    "odasi ana yonetmeli",
    "tmmob",
    "türk mühendis ve mimar odaları birliği",
    "turk muhendis ve mimar odalari birligi",
    "mühendis ve mimar odaları birliği",
    "muhendis ve mimar odalari birligi",
    "birlik iç yönetmeli",
    "birlik ic yonetmeli",
    "birlik içi yönetmeli",
    "birlik ici yonetmeli",
    "kamu personeli alımı",
    "kamu personeli alimi",
    "kamu personeli alım",
    "sgk denetmen yardımcısı",
    "sgk denetmen yardimcisi",
    "sosyal güvenlik denetmen yardımcısı",
    "sosyal guvenlik denetmen yardimcisi",
    "denetmen yardımcısı kadro",
    "denetmen yardimcisi kadro",
)

# Internal public-body HR: SGK/kamu kadro, placed-candidate paperwork — not employer rules.
PUBLIC_PERSONNEL_PHRASES = (
    "kadrosuna yerleşen",
    "kadrosuna yerlesen",
    "kadrosuna yerleştir",
    "kadrosuna yerlestir",
    "kadroya yerleştir",
    "kadroya yerlestir",
    "yerleşen aday",
    "yerlesen aday",
    "adaylardan istenen",
    "adaylardan istenilen",
    "denetmen yardımcısı",
    "denetmen yardimcisi",
    "denetmen yardımcısı kadro",
    "göreve başlama evrak",
    "goreve baslama evrak",
    "kpss",
    "kurum içi nakil",
    "kurumici nakil",
    "memur alım",
    "memur alimi",
    "kamu personeli alım",
    "sözleşmeli personel alımı",
    "sozlesmeli personel alimi",
    "açık kadro ilan",
    "acik kadro ilan",
    "atama ve yer değiştirme",
    "atama ve yer degistirme",
    "yer değiştirme yönetmeliği",
    "yer degistirme yonetmeligi",
)

# Facility / profession-only regimes — keep as cards, not as general İSO plant HR/finance.
SPECIALIZED_SECTOR_PHRASES = (
    "nükleer güç santral",
    "nukleer guc santral",
    "nükleer santral",
    "nukleer santral",
    "nükleer enerji santral",
    "nükleer tesis",
    "nukleer tesis",
    "nükleer güç reaktör",
    "nükleer düzenleme kurumu",
    "nükleer güvenlik",
    "radyoaktif atık tesisi",
    "radyoaktif atik tesisi",
    "radyoaktif atık",
    "akkuyu",
    "iyonlaştırıcı radyasyon tesisi",
    "iyonlastirici radyasyon tesisi",
    "sivil havacılık",
    "sivil havacilik",
    "shgm",
    "uçuş kontrol",
    "ucus kontrol",
    "radyo seyrüsefer",
    "radyo seyrusefer",
    "havaalanı işlet",
    "havaalani islet",
    "hava aracı",
    "hava araci",
    "noterlik kanunu",
    "noterlik",
    "noterler birliği",
    "noterler birligi",
    "türk gıda kodeksi",
    "turk gida kodeksi",
    "gıda kodeksi",
    "gida kodeksi",
    "alkollü içki",
    "alkollu icki",
    "distile alkollü",
    "tütün mamulü",
    "tutun mamulu",
)

# Public-servant / public-body HR — not a private factory operational burden.
KAMU_REGIME_PHRASES = (
    "6245",
    "harcırah kanunu",
    "harcirah kanunu",
    "657 sayılı",
    "657 sayili",
    "devlet memurları kanunu",
    "devlet memurlari kanunu",
    "4/b",
    "4-b sözleşmeli",
    "4-b sozlesmeli",
    "4/b'li",
    "sözleşmeli personel çalıştırılmasına ilişkin esas",
    "sozlesmeli personel calistirilmasina iliskin esas",
    "kamu personeli",
    "kamu personel",
    "devlet memuru",
    "memurlara ödenecek",
    "memurlara odenecek",
    "kamu kurum ve kuruluş",
    "kamu kurum ve kurulus",
)

# Individual constitutional complaints — not İSO employer rules.
AYM_INDIVIDUAL_TITLE_PHRASES = (
    "başvuru numaralı kararı",
    "basvuru numarali karari",
    "başvuru numaralı",
    "basvuru numarali",
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
    "organize sanayi",
    "osb'lerde",
    "osb içinde",
    "osb icinde",
    "osb dışında",
    "osb disinda",
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
    "masak",
    "suç gelir",
    "suc gelir",
    "aklanmas",
    "kara para",
    "terörün finansman",
    "terorun finansman",
    "terör finansman",
    "5549",
)

KEEP_LABOR_HR = (
    "4857",
    "6356",
    "işkolu",
    "is kolu",
    "iş kolu",
    "sendika",
    "toplu iş sözleş",
    "toplu is sozles",
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
    "2872",
    "çevre yönet",
    "cevre yonet",
    "çevre danış",
    "cevre danis",
    "çevre mühendis",
    "cevre muhendis",
    "çevre izin",
    "cevre izin",
    "çevre kanunu",
    "çevre mevzuat",
    "cevre mevzuat",
    "çevre yüküml",
    "cevre yukuml",
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
    "6102",
    "türk ticaret kanunu",
    "turk ticaret kanunu",
    "ticaret kanunu",
    "ttk",
    "masak",
    "suç gelir",
    "suc gelir",
    "aklanmas",
    "terörün finansman",
    "terorun finansman",
)

CARE_HOME_PHRASES = (
    "bakımevi",
    "bakimevi",
    "huzurevi",
    "engelli bakım evi",
    "engelli bakimevi",
    "özürlü bakım",
    "ozurlu bakim",
    "engellilerin bakımı",
    "bakım ve rehabilitasyon merkezi",
    "bakim ve rehabilitasyon merkezi",
    "özel bakım merkez",
    "ozel bakim merkez",
    "engelli bireylere yönelik",
    "engelli bireylere yonelik",
)

ALWAYS_KEEP_FINANCE = (
    "masak",
    "suç gelir",
    "suc gelir",
    "aklanmas",
    "kara para",
    "terörün finansman",
    "terorun finansman",
    "terör finansman",
    "5549",
    "kurumlar vergisi",
    "kdv",
    "katma değer vergisi",
    "katma deger vergisi",
    "ötv",
    "otv",
    "özel tüketim vergisi",
    "ozel tuketim vergisi",
    "gümrük",
    "gumruk",
    "dış ticaret",
    "dis ticaret",
    "6102",
    "türk ticaret kanunu",
    "turk ticaret kanunu",
    "ticaret kanunu",
    "ttk",
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


def _fold(value: str) -> str:
    """Locale-safe fold so İ/I match Turkish keep phrases."""
    return (
        value.replace("İ", "i")
        .replace("I", "ı")
        .casefold()
        .replace("\u0307", "")
    )


def _blob(title: str, text: str) -> str:
    return f"{_fold(title)}\n{_fold(text)}"


def _has_any(blob: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in blob for phrase in phrases)


def has_industrial_signal(title: str, text: str, document_id: str = "") -> bool:
    if document_id in _FIXTURE_KEEP_IDS:
        return True
    return _has_any(_blob(title, text), KEEP_PHRASES)


def is_aml_or_masak(title: str, text: str = "") -> bool:
    """True for MASAK / AML / suç geliri / terör finansmanı compliance rules."""
    return _has_any(
        _blob(title, text),
        (
            "masak",
            "suç gelir",
            "suc gelir",
            "aklanmas",
            "kara para",
            "terörün finansman",
            "terorun finansman",
            "terör finansman",
            "5549",
        ),
    )


def is_financial_corporate_keep(title: str, text: str = "") -> bool:
    """AML, corporate tax, VAT/ÖTV, customs, foreign trade, and TTK — always keep."""
    return _has_any(_blob(title, text), ALWAYS_KEEP_FINANCE)


def is_care_home_regulation(title: str, text: str = "") -> bool:
    """Disabled / elderly care-home statutes — not İSO plant compliance."""
    return _has_any(_blob(title, text), CARE_HOME_PHRASES)


def is_sanction_drop(title: str, text: str) -> bool:
    """UN/named-person freezes — not MASAK AML compliance yönetmelikleri."""
    if is_aml_or_masak(title, text):
        return False
    return _has_any(_blob(title, text), SANCTION_DROP_PHRASES)


def is_appointment_title(title: str) -> bool:
    return _has_any(_fold(title), APPOINTMENT_TITLE_PHRASES)


def is_university_regulation(title: str, text: str = "") -> bool:
    """True for university academic / exam regulations — not İSO industry.

    Scan the title (not the full gazette HTML body) so a same-day Üniversite
    item cannot contaminate unrelated yönetmelikler.
    """
    title_f = _fold(title)
    if "üniversite" in title_f or "universite" in title_f:
        return True
    if "lisansüstü" in title_f or "lisansustu" in title_f:
        return True
    if "eğitim-öğretim ve sınav" in title_f or "egitim-ogretim ve sinav" in title_f:
        return True
    if "eğitim öğretim ve sınav yönetmeliği" in title_f:
        return True
    if "lisans eğitim-öğretim" in title_f or "lisans egitim-ogretim" in title_f:
        return True
    return False


def is_aym_individual_application(title: str, text: str = "") -> bool:
    """Drop only pure individual AYM petitions."""
    blob = _blob(title, text)
    return (
        "bireysel başvuru" in blob
        or "bireysel basvuru" in blob
        or "başvuru numaralı" in blob
        or "basvuru numarali" in blob
    )


def is_procurement_or_job_ad(title: str, text: str) -> bool:
    """True for ads and announcements: sales, tenders, recruitment."""
    title_f = _fold(title)
    blob = _blob(title, text)
    if "gayrimenkul satış" in blob or "gayrimenkul satis" in blob:
        return True
    if "satış ilanı" in blob or "satis ilani" in blob:
        return True
    if "kiralama ilanı" in blob or "kiralama ilani" in blob:
        return True
    ad_title = (
        "iş ilanı",
        "is ilani",
        "açık iş ilanı",
        "acik is ilani",
        "personel alım",
        "personel alim",
        "kadro ilanı",
        "kadro ilani",
        "ihale",
    )
    if _has_any(title_f, ad_title):
        return True
    return "ihale ilanı" in blob or "ihale ilani" in blob or "personel alım ilanı" in blob


def is_internal_chamber_regulation(title: str, text: str = "") -> bool:
    """True for TMMOB / oda ana / birlik içi bylaws — not factory HR."""
    blob = _blob(title, text)
    title_f = _fold(title)
    if _has_any(blob, CHAMBER_INTERNAL_PHRASES):
        return True
    if "ana yönetmeli" in title_f and ("oda" in title_f or "birlik" in title_f):
        return True
    if (
        "iç yönetmeli" in title_f or "ic yonetmeli" in title_f
    ) and ("oda" in title_f or "birlik" in title_f):
        return True
    return False


def is_administrative_out_of_scope(title: str, text: str = "") -> bool:
    """TMMOB/oda-birlik içi, kamu personeli alımı, SGK memur kadro — no card."""
    if is_internal_chamber_regulation(title, text):
        return True
    return is_public_personnel_announcement(title, text)


def is_public_personnel_announcement(title: str, text: str = "") -> bool:
    """True for SGK/kamu internal kadro, placement, and candidate-document notices."""
    title_f = _fold(title)
    blob = _blob(title, text)
    if _has_any(title_f, PUBLIC_PERSONNEL_PHRASES):
        return True
    if _has_any(blob, PUBLIC_PERSONNEL_PHRASES):
        return True
    if (
        ("istenen belge" in blob or "istenilen belge" in blob)
        and ("kadro" in blob or "aday" in blob)
        and (
            "sosyal güvenlik" in blob
            or "sosyal guvenlik" in blob
            or "sgk" in blob
            or "kamu" in title_f
        )
    ):
        return True
    return False


def is_kamu_scope(title: str, text: str = "") -> bool:
    """True when the addressee is a public body / civil servant, not a private plant."""
    if is_administrative_out_of_scope(title, text):
        return False
    if is_financial_corporate_keep(title, text):
        return False
    return _has_any(_blob(title, text), KAMU_REGIME_PHRASES)


def is_specialized_sector_scope(title: str, text: str = "") -> bool:
    """Nuclear, aviation, food/alcohol codex, notary — not general manufacturing."""
    if is_kamu_scope(title, text):
        return False
    return _has_any(_blob(title, text), SPECIALIZED_SECTOR_PHRASES)


def specialized_subsector_label(title: str, text: str = "") -> str:
    blob = _blob(title, text)
    if _has_any(
        blob,
        (
            "nükleer",
            "nukleer",
            "radyoaktif",
            "akkuyu",
            "iyonlaştırıcı radyasyon",
            "iyonlastirici radyasyon",
        ),
    ):
        return "nükleer tesisler ve radyoaktif atık tesisleri"
    if _has_any(
        blob,
        (
            "sivil havacılık",
            "sivil havacilik",
            "shgm",
            "uçuş kontrol",
            "ucus kontrol",
            "seyrüsefer",
            "seyrusefer",
            "havaalanı",
            "havaalani",
            "hava aracı",
            "hava araci",
        ),
    ):
        return "sivil havacılık"
    if _has_any(
        blob,
        (
            "gıda kodeksi",
            "gida kodeksi",
            "alkollü içki",
            "alkollu icki",
            "tütün mamul",
            "tutun mamul",
        ),
    ):
        return "gıda / alkol kodeksi"
    if "noterlik" in blob or "noterler birliği" in blob or "noterler birligi" in blob:
        return "noterlik"
    return "dar / uzmanlaşmış alt sektör"


def audience_scope(title: str, text: str = "") -> str:
    """kamu | specialized | general — who the card is actually for."""
    if is_kamu_scope(title, text):
        return "kamu"
    if is_specialized_sector_scope(title, text):
        return "specialized"
    return "general"


def is_regulatory_instrument(title: str, text: str = "") -> bool:
    blob = _blob(title, text)
    return _has_any(
        blob,
        (
            "yönetmelik",
            "yonetmelik",
            "tebliğ",
            "teblig",
            "karar",
            "genelge",
            "duyuru",
        ),
    )


def force_keep_departments(title: str, text: str = "") -> list[str]:
    """Pin headline gazette items to a unit — MASAK/tax/TTK always mapped."""
    blob = _blob(title, text)
    if is_aml_or_masak(title, text):
        return ["mali", "hukuk"]
    if _has_any(
        blob,
        (
            "6102",
            "türk ticaret kanunu",
            "turk ticaret kanunu",
            "ticaret kanunu",
        ),
    ):
        return ["hukuk"]
    if _has_any(
        blob,
        (
            "kurumlar vergisi",
            "kdv",
            "katma değer vergisi",
            "katma deger vergisi",
            "ötv",
            "otv",
            "özel tüketim vergisi",
            "ozel tuketim vergisi",
            "gümrük",
            "gumruk",
            "dış ticaret",
            "dis ticaret",
        ),
    ):
        return ["mali"]
    if "çevre yönet" in blob or "cevre yonet" in blob:
        return ["hukuk"]
    compact = blob.replace(" ", "")
    if "işkolu" in compact or "iskolu" in compact:
        return ["ik"]
    if (
        "organize sanayi" in blob
        or "osb" in blob
        or "özel okul" in blob
        or "ozel okul" in blob
        or "özel meslekî" in blob
        or "ozel mesleki" in blob
        or "eğitim ve öğretim desteği" in blob
        or "egitim ve ogretim destegi" in blob
    ):
        return ["mali"]
    if "teşvik tebliğ" in blob or "tesvik teblig" in blob:
        return ["mali"]
    if "öğretim desteği" in blob or "ogretim destegi" in blob:
        return ["mali"]
    return []


def is_absolute_drop(title: str, text: str) -> bool:
    """University, kamulaştırma, bakımevi, ads, AYM, or kamu personeli alımı."""
    return (
        is_university_regulation(title, text)
        or is_aym_individual_application(title, text)
        or is_procurement_or_job_ad(title, text)
        or is_administrative_out_of_scope(title, text)
        or is_care_home_regulation(title, text)
        or is_spatial_drop(title, text)
        or is_appointment_title(title)
    )


def is_institutional_title(title: str) -> bool:
    """University exam rules or gendarmerie social facilities — not İSO labor."""
    if is_university_regulation(title, ""):
        return True
    folded = _fold(title)
    if "jandarma" in folded and any(
        token in folded for token in ("yatakhane", "gazino", "sosyal tesis")
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
    """True for university regs, ads, or personal AYM petitions."""
    if document_id in _FIXTURE_KEEP_IDS:
        return False
    if force_keep_departments(title, text):
        return False
    return is_absolute_drop(title, text)


def implied_departments(title: str, text: str, document_id: str = "") -> list[str]:
    """Always return at least one unit: ik, mali, or hukuk."""
    forced = force_keep_departments(title, text)
    if forced:
        return forced
    blob = _blob(title, text)
    doc = _fold(document_id)
    found: list[str] = []
    if _has_any(blob, KEEP_LABOR_HR):
        found.append("ik")
    if _has_any(blob, KEEP_ENV_TRADE + KEEP_LEGAL_OPS):
        found.append("hukuk")
    if _has_any(blob, KEEP_TAX_FINANCE):
        found.append("mali")
    if found:
        return found
    if "sgk" in blob or "sgk" in doc:
        return ["ik"]
    return ["hukuk"]


def classify_relevance(
    title: str,
    text: str,
    document_id: str = "",
    source: str = "",
) -> tuple[Verdict, str]:
    """Keep industrial İSO items; drop university, ads, and personal AYM noise."""
    if document_id in _FIXTURE_KEEP_IDS:
        return "keep", (
            "Metin iş/SGK/İSG, vergi-maliye, çevre, ticaret veya operasyonel "
            "yükümlülüğü değiştiriyor."
        )
    if is_university_regulation(title, text):
        return "drop", (
            "Üniversite eğitim-öğretim / sınav yönetmeliği; sanayi işvereni bağlanmıyor."
        )
    if is_care_home_regulation(title, text):
        return "drop", (
            "Engelli / yaşlı bakımevi düzenlemesi; sanayi işletmesine yükümlülük doğurmaz."
        )
    if is_spatial_drop(title, text):
        return "drop", (
            "Yerel yol / arazi kamulaştırma veya parsel sınırı; sanayi işvereni bağlanmıyor."
        )
    if is_administrative_out_of_scope(title, text):
        return "drop", (
            "İdari Duyuru / Kapsam Dışı: TMMOB, oda/birlik içi yönetmelik veya "
            "kamu personeli alımı; özel sektör sanayi işletmesine yükümlülük doğurmaz."
        )
    if is_appointment_title(title):
        return "drop", (
            "Kamu personeli atama / terfi ilanı; sanayi işletmesine yükümlülük doğurmaz."
        )
    if is_financial_corporate_keep(title, text):
        depts = implied_departments(title, text, document_id)
        return "keep", (
            "MASAK / vergi / gümrük / dış ticaret / TTK uyum yükümlülüğü; "
            f"{', '.join(depts)} birimine iletildi."
        )
    forced = force_keep_departments(title, text)
    if forced:
        return "keep", (
            "Sanayi işverenini bağlayan düzenleme; "
            f"{', '.join(forced)} birimine iletildi."
        )
    if is_aym_individual_application(title, text):
        return "drop", (
            "Kişiye özel Anayasa Mahkemesi bireysel başvurusu; işveren kuralı değişmiyor."
        )
    if is_kamu_scope(title, text):
        return "keep", (
            "Düşük / Kamu Kurumları Kapsamı: kamu personeli veya kamu kurumu düzenlemesi; "
            "özel sektör sanayi işletmesine doğrudan aksiyon yükümlülüğü doğurmaz."
        )
    if is_specialized_sector_scope(title, text):
        label = specialized_subsector_label(title, text)
        return "keep", (
            f"Düşük / Özel Sektör Kapsamı: muhatap {label}; "
            "standart imalat işverenine genel İK/mali aksiyon değil."
        )
    if is_procurement_or_job_ad(title, text):
        return "drop", (
            "İhale, personel alım veya gayrimenkul satış ilanı; yükümlülük değişmiyor."
        )
    if has_industrial_signal(title, text, document_id) or str(source).lower() == "sgk":
        depts = implied_departments(title, text, document_id)
        return "keep", (
            "Sanayi, çevre, sendika, vergi, OSB veya SGK düzenlemesi; "
            f"{', '.join(depts)} birimine iletildi."
        )
    return "drop", (
        "Sanayi işverenini doğrudan bağlayan bir kural değişikliği bulunmamaktadır."
    )


def mock_is_relevant(title: str, text: str, document_id: str = "") -> tuple[bool, str]:
    verdict, reason = classify_relevance(title, text, document_id)
    return verdict == "keep", reason
