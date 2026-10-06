"""Grounded Turkish executive-card copy (no generic placeholders)."""

from __future__ import annotations

import re

from config.relevance import (
    _fold,
    audience_scope,
    is_administrative_out_of_scope,
    is_financial_corporate_keep,
    specialized_subsector_label,
)
from schemas.outputs import Department, department_label

GENERIC_PHRASES = (
    "sanayi işverenini bağlayan resmi bir düzenlemedir",
    "sanayi işverenini ilgilendiren resmi bir düzenlemedir",
    "metni inceleyip uyum adımlarını belirlemelidir",
    "yükümlülüğü incelemeli ve uyum adımlarını başlatmalıdır",
    "ilgili süreç, sözleşme ve kayıtları yeni metne göre güncelleyin",
    "ilgili birim yükümlülüğü incelemeli",
    "ilgili departman metni incelemelidir",
    "ilgili birim metni incelemelidir",
    "ilgili departman metni incelemeli",
    "ilgili birim metni incelemeli",
    "inceleme yapılmalıdır",
)

KAMU_NO_PRIVATE_ACTION = (
    "Bu düzenleme kamu personeline/kurumlarına yönelik olup, özel sektör "
    "sanayi işletmeleri için doğrudan bir aksiyon yükümlülüğü doğurmamaktadır."
)

NO_ACTION_ADMINISTRATIVE = (
    "Herhangi bir aksiyon gerekmemektedir (Kurum içi / Kamusal düzenleme)."
)

HIGH_LEVEL_PHRASES = (
    "yürürlüğe konulmuştur",
    "yururluge konulmustur",
    "yürürlüğe konuldu",
    "yürürlüğe girmiştir",
    "yururluge girmistir",
)

SECTION_ONEMLI = "📌 **Önemli Düzenlemeler & Maddeler**"
SECTION_ETKI = "🏭 **Sanayi ve İşverene Etkisi**"
SECTION_AKSIYON = "📋 **Sorumlu Departman İçin Aksiyon Maddeleri**"

_SENTENCE_SPLIT = re.compile(r"(?<=[\.!?])\s+|\n+")
_BOILERPLATE = (
    "yürürlüğe girer",
    "yürürlüğe girmiştir",
    "yürürlüğe konulmuştur",
    "resmî gazete",
    "yayımlanmıştır",
    "ile ilgili olarak",
)
_DETAIL_TOKENS = (
    "madde",
    "yüzde",
    "%",
    "işkolu",
    "nace",
    "osb",
    "tl",
    "oran",
    "sayılı",
    "teşvik",
    "izin",
    "sendika",
    "prim",
    "danışman",
    "kapsam",
    "eşik",
    "seviye",
    "ek-1",
    "meslek",
)
_HEADING_MARKERS = (
    _fold("önemli düzenlemeler"),
    _fold("sanayi ve işverene etkisi"),
    _fold("sorumlu departman"),
)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_NUMERIC_DATE_RE = re.compile(r"\b\d{1,2}[/.\-]\d{1,2}[/.\-](?:\d{2}|\d{4})\b")
_ISO_DATE_RE = re.compile(r"\b(?:19|20)\d{2}-\d{2}-\d{2}\b")
_TR_MONTHS = (
    "ocak",
    "şubat",
    "subat",
    "mart",
    "nisan",
    "mayıs",
    "mayis",
    "haziran",
    "temmuz",
    "ağustos",
    "agustos",
    "eylül",
    "eylul",
    "ekim",
    "kasım",
    "kasim",
    "aralık",
    "aralik",
)
_TR_DATE_RE = re.compile(
    r"\b\d{1,2}\s+(?:" + "|".join(_TR_MONTHS) + r")\s+(?:19|20)\d{2}\b",
    re.IGNORECASE,
)


def source_years(*parts: str) -> set[str]:
    blob = "\n".join(part or "" for part in parts)
    years = set(_YEAR_RE.findall(blob))
    for match in _ISO_DATE_RE.findall(blob):
        years.add(match[:4])
    return years


def list_allowed_date_tokens(*parts: str) -> list[str]:
    blob = "\n".join(part or "" for part in parts)
    tokens: list[str] = []
    seen: set[str] = set()
    for match in (
        *_ISO_DATE_RE.findall(blob),
        *_NUMERIC_DATE_RE.findall(blob),
        *_TR_DATE_RE.findall(blob),
        *_YEAR_RE.findall(blob),
    ):
        key = match.casefold()
        if key in seen:
            continue
        seen.add(key)
        tokens.append(match)
    return tokens


def ungrounded_years(text: str, *source_parts: str) -> set[str]:
    allowed = source_years(*source_parts)
    if not allowed:
        return set()
    return set(_YEAR_RE.findall(text or "")) - allowed


def strip_ungrounded_date_lines(text: str, *source_parts: str) -> str:
    """Drop bullets/lines that cite a year absent from the scraped source."""
    invented = ungrounded_years(text, *source_parts)
    if not invented or not (text or "").strip():
        return text
    kept: list[str] = []
    for line in (text or "").splitlines():
        years = set(_YEAR_RE.findall(line))
        if years and years & invented and not any(
            marker in _fold(line) for marker in _HEADING_MARKERS
        ):
            continue
        kept.append(line)
    cleaned = "\n".join(kept).strip()
    return cleaned or text


def is_generic_executive_copy(text: str) -> bool:
    blob = _fold(text or "")
    if not (text or "").strip():
        return True
    return any(_fold(phrase) in blob for phrase in GENERIC_PHRASES)


def has_executive_structure(text: str) -> bool:
    blob = _fold(text or "")
    return (
        _fold("önemli düzenlemeler") in blob
        and _fold("sanayi ve işverene etkisi") in blob
        and _fold("sorumlu departman") in blob
        and _fold("aksiyon") in blob
    )


def _strip_markdown_headings(text: str) -> str:
    lines: list[str] = []
    for raw in (text or "").splitlines():
        folded = _fold(raw)
        if any(marker in folded for marker in _HEADING_MARKERS):
            continue
        lines.append(raw)
    return " ".join(lines)


def is_high_level_summary(text: str, title: str = "") -> bool:
    """True for title-only yürürlüğe lines or banned generic copy."""
    if is_generic_executive_copy(text):
        return True
    body = _fold(_strip_markdown_headings(text))
    if not body:
        return True
    title_f = _fold(title or "")
    short = len(body) < 220
    if short and any(_fold(phrase) in body for phrase in HIGH_LEVEL_PHRASES):
        if title_f and title_f[:48] in body:
            return True
        leftover = body
        for phrase in HIGH_LEVEL_PHRASES:
            leftover = leftover.replace(_fold(phrase), " ")
        leftover = re.sub(r"\s+", " ", leftover).strip(" .:-")
        if len(leftover) < 80:
            return True
    if title_f and title_f[:40] in body and len(body) < len(title_f) + 90:
        if any(token in body for token in ("yururluge", "yayımlan", "yayimlan")):
            return True
    return False


def _clean_sentence(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" •-\t")


def _content_sentences(title: str, new_text: str, *, limit: int = 3) -> list[str]:
    blob = f"{title}\n{new_text}"
    found: list[str] = []
    seen: set[str] = set()
    for raw in _SENTENCE_SPLIT.split(blob):
        sentence = _clean_sentence(raw)
        if len(sentence) < 28:
            continue
        folded = _fold(sentence)
        if any(token in folded for token in _BOILERPLATE) and len(sentence) < 80:
            continue
        key = folded[:80]
        if key in seen:
            continue
        seen.add(key)
        found.append(sentence[:320])
        if len(found) >= limit:
            break
    if not found and title.strip():
        found.append(_clean_sentence(title)[:320])
    return found


def _has_detail(text: str) -> bool:
    folded = _fold(text or "")
    if len((text or "").strip()) > 100:
        return True
    if re.search(r"\d", text or ""):
        return True
    return any(token in folded for token in _DETAIL_TOKENS)


def _detail_sentences(title: str, new_text: str, *, limit: int = 6) -> list[str]:
    candidates = _content_sentences(title, new_text, limit=24)
    ranked: list[tuple[int, int, str]] = []
    for index, sentence in enumerate(candidates):
        folded = _fold(sentence)
        score = 0
        if re.search(r"\d", sentence):
            score += 3
        if any(token in folded for token in _DETAIL_TOKENS):
            score += 2
        if len(sentence) > 70:
            score += 1
        ranked.append((score, index, sentence))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    chosen = {item[2] for item in ranked[:limit]}
    return [sentence for sentence in candidates if sentence in chosen][:limit]


def _as_points(value: str | list[str]) -> list[str]:
    if isinstance(value, list):
        return [_clean_sentence(item) for item in value if _clean_sentence(item)]
    text = (value or "").strip()
    if not text:
        return []
    parts = re.split(r"\n+|•|\u2022|(?:^|\s)\d+[\.\)]\s+", text)
    points = [_clean_sentence(part) for part in parts if _clean_sentence(part)]
    return points or [_clean_sentence(text)]


def assemble_executive_summary(
    maddeler: str | list[str],
    etki: str | list[str],
    aksiyon: str | list[str],
) -> str:
    madde_lines = "\n".join(f"- {point}" for point in _as_points(maddeler)[:8])
    etki_lines = "\n".join(f"- {point}" for point in _as_points(etki)[:6])
    aksiyon_points = _as_points(aksiyon)[:8]
    aksiyon_lines = "\n".join(
        f"{index}. {point}" for index, point in enumerate(aksiyon_points, start=1)
    )
    return "\n\n".join(
        [
            f"{SECTION_ONEMLI}\n{madde_lines or '- Metindeki operatif hükümler incelenmelidir.'}",
            f"{SECTION_ETKI}\n{etki_lines or '- Sanayi işvereninin yükümlülüğü değişmiştir.'}",
            f"{SECTION_AKSIYON}\n{aksiyon_lines or '1. Sorumlu birim ilgili kaydı güncellemelidir.'}",
        ]
    )


def _audience(title: str, new_text: str) -> str:
    blob = _fold(f"{title}\n{new_text}")
    if is_administrative_out_of_scope(title, new_text):
        return (
            "Muhatap TMMOB / meslek odası-birliği içi organlar veya kamu personeli "
            "alımıdır; özel sektör sanayi işletmesi bu kuralın muhatabı değildir"
        )
    scope = audience_scope(title, new_text)
    if scope == "kamu":
        return (
            "Muhatap kamu kurumları ve kamu personelidir; özel sektör sanayi "
            "işletmesi / fabrika işvereni bu kuralın doğrudan muhatabı değildir"
        )
    if scope == "specialized":
        label = specialized_subsector_label(title, new_text)
        return (
            f"Yalnızca {label} işleticileri / meslek mensupları; "
            "standart İSO imalat tesisi / OSB işvereni genel muhatap değildir"
        )
    if "işkolu" in blob or "sendika" in blob or "6356" in blob:
        return (
            "İşkolu tespitine tabi imalat işyerleri, yetkili işçi sendikaları ve "
            "bu tesislerdeki işverenler; TİS yetkisi ve işyeri kapsamı değişebilir"
        )
    if "çevre yönet" in blob or "cevre yonet" in blob:
        return (
            "Çevre yönetimi hizmeti alan imalat tesisleri, OSB işletmeleri, yetkili "
            "çevre danışmanlık firmaları ve izin/lisans yükümlüsü işverenler"
        )
    if "organize sanayi" in blob or "osb" in blob or "öğretim desteği" in blob:
        return (
            "OSB içi ve dışı özel mesleki-teknik anadolu lisesi işleten işverenler "
            "ile destek tutarını bütçeleyen maliye birimleri"
        )
    if "sgk" in blob or "sosyal sigorta" in blob or "e-bildirge" in blob:
        return "SGK yükümlüsü sanayi işverenleri; bordro, özlük ve e-bildirge operasyonu"
    if (
        "masak" in blob
        or "aklanmas" in blob
        or "suç gelir" in blob
        or "terörün finansman" in blob
        or "terorun finansman" in blob
    ):
        return (
            "MASAK yükümlüsü sanayi şirketleri; dış ticaret, nakit, müşteri tanıma "
            "ve uyum (compliance) süreçleri — kamu içi personel kuralı değildir"
        )
    if (
        "ötv" in blob
        or "kdv" in blob
        or "vergi" in blob
        or "teşvik" in blob
        or "gümrük" in blob
        or "gumruk" in blob
        or "dış ticaret" in blob
        or "ticaret kanunu" in blob
        or "ttk" in blob
    ):
        return "Vergi, gümrük, dış ticaret veya TTK yükümlüsü imalatçı / ithalatçı işverenler ve maliye-hukuk kayıtları"
    return "Metinde sayılan yükümlü gerçek ve tüzel kişiler (sanayi işverenleri ve tesis işleticileri)"


def _impact_points(title: str, new_text: str) -> list[str]:
    audience = _audience(title, new_text)
    details = _detail_sentences(title, new_text, limit=4)
    blob = _fold(f"{title}\n{new_text}")
    points = [audience]
    if is_administrative_out_of_scope(title, new_text):
        points.append(
            "İdari duyuru / kurum içi düzenleme: fabrika İK, bordro veya maliye "
            "sürecine işlemeyin; özel sektör yükümlülüğü doğmaz."
        )
        return points[:4]
    scope = audience_scope(title, new_text)
    if scope == "kamu":
        points.append(
            "Özel sektör fabrika sahipleri için operasyonel görev veya mali yük "
            "doğurmaz; İK/maliye bordro sürecine işlemeyin."
        )
        return points[:4]
    if scope == "specialized":
        label = specialized_subsector_label(title, new_text)
        points.append(
            f"Standart imalat tesisi İK, bordro ve maliye süreçlerini değiştirmeyin; "
            f"aksiyon yalnızca {label} muhataplarınadır."
        )
        return points[:4]
    if "işkolu" in blob:
        points.append(
            "İK, işyerinin yeni işkolu koduna göre sendika yetkisini ve toplu iş "
            "sözleşmesi kapsamını yeniden tespit etmek zorundadır."
        )
    elif "çevre" in blob or "cevre" in blob:
        points.append(
            "Tesis, çevre danışmanlığı yeterliği / izin-lisans şartı değiştiyse "
            "sözleşme ve faaliyet iznini durdurma riskine karşı güncellemelidir."
        )
    elif (
        "masak" in blob
        or "aklanmas" in blob
        or "suç gelir" in blob
        or "terörün finansman" in blob
    ):
        points.append(
            "Maliye ve hukuk, şüpheli işlem bildirimi, müşteri tanıma ve nakit/"
            "dış ticaret kontrollerini yönetmeliğe göre güncellemelidir; İK kadro "
            "işlemi değildir."
        )
    elif "osb" in blob or "öğretim desteği" in blob or "destek" in blob:
        points.append(
            "Maliye, destek tutarı, öğrenci sayısı ve yararlanma dönemini tebliğdeki "
            "şartlara göre muhasebeleştirmeli; nakit akışı ve teşvik dosyası etkilenir."
        )
    elif details:
        points.append(details[min(1, len(details) - 1)])
    return points[:4]


def _action_line(department: Department, title: str, new_text: str) -> str:
    blob = _fold(f"{title}\n{new_text}")
    label = department_label(department)
    if is_administrative_out_of_scope(title, new_text):
        return NO_ACTION_ADMINISTRATIVE
    scope = audience_scope(title, new_text)
    if scope == "kamu":
        return KAMU_NO_PRIVATE_ACTION
    if scope == "specialized":
        sub = specialized_subsector_label(title, new_text)
        return (
            f"{label}: kuralın {sub} muhataplarına ait olduğunu not edin; "
            "standart imalat İK-mali süreçlerine genel aksiyon açmayın."
        )
    if department == "ik":
        if "işkolu" in blob or "sendika" in blob:
            return (
                f"{label}: yetkili sendika ve TİS yetkisini yeni işkolu tespit "
                "kararına göre kontrol edin; özlük/toplu iş ilişkisi dosyasını güncelleyin."
            )
        return (
            f"{label}: personel sözleşmesi, bordro ve SGK bildirimlerini yeni "
            "esasa göre uyarlayın; yürürlük tarihini bordro takvimine işleyin."
        )
    if (
        "masak" in blob
        or "aklanmas" in blob
        or "suç gelir" in blob
        or "terörün finansman" in blob
    ):
        return (
            f"{label}: MASAK yükümlü işlem, müşteri tanıma ve şüpheli işlem bildirimi "
            "prosedürünü yeni tedbir maddelerine göre güncelleyin; kamu personel "
            "süreci açmayın."
        )
    if department == "mali":
        if "öğretim desteği" in blob or "osb" in blob or "teşvik" in blob:
            return (
                f"{label}: destek tutarı, başvuru belgesi ve muhasebe hesabını "
                "tebliğdeki oran/şartlara göre kaydedin; yararlanma dönemini doğrulayın."
            )
        return (
            f"{label}: vergi/teşvik kodunu ve ilk beyanname dönemini yeni metindeki "
            "tutar veya şarta göre güncelleyin."
        )
    if "çevre" in blob or "cevre" in blob:
        return (
            f"{label}: çevre izni/lisans ve danışmanlık sözleşmesini yeni yönetmelik "
            "hükümleriyle karşılaştırın; eksik yükümlülüğü kapatın."
        )
    return (
        f"{label}: yeni metindeki izin, sözleşme ve uyum maddesini kontrol listesine "
        "alın; yürürlük tarihine kadar gerekli tadili işleyin."
    )


def _action_points(department: Department, title: str, new_text: str) -> list[str]:
    primary = _action_line(department, title, new_text)
    blob = _fold(f"{title}\n{new_text}")
    if is_administrative_out_of_scope(title, new_text):
        return [NO_ACTION_ADMINISTRATIVE]
    scope = audience_scope(title, new_text)
    if scope == "kamu":
        return [
            KAMU_NO_PRIVATE_ACTION,
            "Kartı arşivleyin; özel sektör İK, bordro veya maliye sürecine işlemeyin.",
            "Yalnızca kamu kurumu / kamu personeli uyum takvimini izleyenler için not edin.",
        ]
    if scope == "specialized":
        sub = specialized_subsector_label(title, new_text)
        return [
            primary,
            f"Kapsamı {sub} lisansı / faaliyeti ile doğrulayın; İSO genel üye "
            "bordro veya teşvik dosyasına işlemeyin.",
            "Yürürlük tarihini yalnızca ilgili alt sektör uyum takvimine işleyin.",
        ]
    second = (
        "Yürürlük / başvuru tarihini birim takvimine işleyin ve ilgili sicil, "
        "sözleşme veya beyanname kaydını yeni metindeki madde numarasıyla eşleştirin."
    )
    if "işkolu" in blob:
        third = (
            "İşyeri bildirimi ve sendika yazışmasını yeni tespit kararıyla "
            "mutabık hale getirin; uyumsuz TİS maddesini işaretleyin."
        )
    elif "çevre" in blob or "cevre" in blob:
        third = (
            "Danışman yeterlik belgesi ve emisyon/izin eklerini dosyaya ekleyin; "
            "idari yaptırım maddesini sözleşme ekine yansıtın."
        )
    elif (
        "masak" in blob
        or "aklanmas" in blob
        or "suç gelir" in blob
        or "terörün finansman" in blob
    ):
        third = (
            "Yükümlü işlem listesini, nakit eşiklerini ve dış ticaret evrakını "
            "yeni madde numarasıyla eşleştirin; MASAK bildirim kanalını test edin."
        )
    elif "osb" in blob or "öğretim desteği" in blob or "destek" in blob:
        third = (
            "Destekten yararlanan öğrenci/okul listesini tebliğ şartlarıyla "
            "kontrol edin; ödeme belgesini mali arşive alın."
        )
    else:
        third = (
            "Operatif maddeyi iç kontrol listesine yazın ve ilk uygulama "
            "döneminde kanıt (kayıt, evrak, sistem ekranı) saklayın."
        )
    return [primary, second, third]


def grounded_executive_summary(
    title: str,
    new_text: str = "",
    department: Department | str = "hukuk",
) -> str:
    """Three-section executive card from scraped title/body — never a generic stub."""
    dept: Department = department if department in {"ik", "hukuk", "mali"} else "hukuk"
    maddeler = _detail_sentences(title, new_text, limit=6)
    if not maddeler:
        maddeler = _content_sentences(title, new_text, limit=3)
    return assemble_executive_summary(
        maddeler,
        _impact_points(title, new_text),
        _action_points(dept, title, new_text),
    )


def grounded_obligation(title: str, new_text: str = "") -> str:
    sentences = _detail_sentences(title, new_text, limit=3)
    if not sentences:
        sentences = _content_sentences(title, new_text, limit=2)
    body = " ".join(sentences) or title
    return (
        f"{SECTION_ONEMLI}\n"
        + "\n".join(f"- {sentence}" for sentence in sentences)
        if sentences
        else f"{SECTION_ONEMLI}\n- {body}"
    )


def grounded_action(
    department: Department | str,
    title: str,
    new_text: str = "",
) -> str:
    dept: Department = department if department in {"ik", "hukuk", "mali"} else "hukuk"
    steps = _action_points(dept, title, new_text)
    numbered = "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))
    return f"{SECTION_AKSIYON}\n{numbered}"


def usable_model_copy(text: str) -> str:
    """Return the model text only if it is non-empty and not a banned placeholder."""
    cleaned = (text or "").strip()
    if is_generic_executive_copy(cleaned):
        return ""
    return cleaned


def _extract_section(text: str, heading: str) -> str:
    needle = _fold(heading)
    capture = False
    out: list[str] = []
    for line in (text or "").splitlines():
        folded = _fold(line)
        if any(marker in folded for marker in _HEADING_MARKERS):
            capture = needle in folded
            continue
        if capture:
            out.append(line)
    return "\n".join(out).strip()


def coerce_executive_summary(
    text: str,
    title: str,
    new_text: str = "",
    department: Department | str = "hukuk",
) -> str:
    """Keep a detailed model card; otherwise wrap or replace with grounded copy."""
    dept: Department = department if department in {"ik", "hukuk", "mali"} else "hukuk"
    cleaned = usable_model_copy(text)
    if cleaned:
        cleaned = strip_ungrounded_date_lines(cleaned, title, new_text)
        if ungrounded_years(cleaned, title, new_text):
            cleaned = ""
    if is_administrative_out_of_scope(title, new_text) or is_financial_corporate_keep(
        title, new_text
    ):
        maddeler = ""
        if cleaned and has_executive_structure(cleaned):
            maddeler = _extract_section(cleaned, "önemli düzenlemeler")
        if not maddeler or not _has_detail(maddeler):
            maddeler = "\n".join(
                f"- {line}"
                for line in (
                    _detail_sentences(title, new_text, limit=6)
                    or _content_sentences(title, new_text, limit=3)
                )
            )
        return assemble_executive_summary(
            maddeler,
            _impact_points(title, new_text),
            _action_points(dept, title, new_text),
        )
    scope = audience_scope(title, new_text)
    if scope in {"kamu", "specialized"}:
        maddeler = ""
        if cleaned and has_executive_structure(cleaned):
            maddeler = _extract_section(cleaned, "önemli düzenlemeler")
        if not maddeler or not _has_detail(maddeler):
            maddeler = "\n".join(
                f"- {line}"
                for line in (
                    _detail_sentences(title, new_text, limit=6)
                    or _content_sentences(title, new_text, limit=3)
                )
            )
        return assemble_executive_summary(
            maddeler,
            _impact_points(title, new_text),
            _action_points(dept, title, new_text),
        )
    if (
        cleaned
        and has_executive_structure(cleaned)
        and not is_high_level_summary(cleaned, title)
    ):
        return cleaned
    if (
        cleaned
        and not is_high_level_summary(cleaned, title)
        and _has_detail(cleaned)
    ):
        return assemble_executive_summary(
            _as_points(cleaned),
            _impact_points(title, new_text),
            _action_points(dept, title, new_text),
        )
    return grounded_executive_summary(title, new_text, dept)
