"""High-precision Eski Metin / Yeni Metin comparison for İSO Pulse.

Used by the Streamlit comparison tab and persisted on pipeline records.
Specialist RAG routing stays on the 0.45 floor; this module is stricter:
cosine >= 0.85, matching legislation domain, and no invented old articles.
"""

from __future__ import annotations

import html
import re
from difflib import SequenceMatcher
from typing import Any, Mapping, Sequence

from config.relevance import is_aml_or_masak, is_financial_corporate_keep

COMPARISON_SIMILARITY_THRESHOLD = 0.85

FALLBACK_OLD_TEXT = (
    "ℹ️ Bu düzenleme mevzuata yeni eklenen bir maddedir veya eski metin "
    "veritabanında henüz yer almamaktadır (Doğrudan Ek / Değişiklik Maddesi)."
)

PROCEDURAL_NOTICE = (
    "Bu yayındaki Amaç, Kapsam, Dayanak, Yürürlük ve Yürütme maddelerinde "
    "üretici açısından maddi bir hüküm değişikliği bulunmamaktadır."
)

LegislationDomain = str  # "finance_aml" | "sgk_social" | "labor" | "other"

_FINANCE_LAW_IDS = frozenset(
    {"193", "213", "488", "3065", "4458", "4760", "5520", "5549", "6102"}
)
_SGK_LAW_IDS = frozenset({"5510", "4447"})
_LABOR_LAW_IDS = frozenset({"4857", "6331", "6356"})

_INVALID_ARTICLE_TOKENS = frozenset(
    {"", "—", "-", "–", "undefined", "nan", "none", "null", "n/a", "na"}
)

_NAMED_SIGNATURES = (
    "recep tayyip erdoğan",
    "recep tayyip erdogan",
    "c. başkanı",
    "c. baskanı",
)

_SIGNATURE_LINE = re.compile(
    r"(?i)^\s*(?:cumhurbaşkanı|cumhurbaskani|bakanı|bakani|bakan|"
    r"hazine ve maliye bakanı|hazine ve maliye bakani|"
    r"çalışma ve sosyal güvenlik bakanı|calisma ve sosyal guvenlik bakani|"
    r"enerji ve tabii kaynaklar bakanı|enerji ve tabii kaynaklar bakani|"
    r"ticaret bakanı|ticaret bakani)\s*[.]?\s*$"
)

_HEADER_LINE = re.compile(
    r"(?i)^\s*(?:t\.?c\.?|resmî gazete|resmi gazete|yürütme ve idare bölümü|"
    r"yurutme ve idare bolumu|cumhurbaşkanı kararı|cumhurbaskani karari|"
    r"karar\s+say[ıi]s[ıi]\s*:?\s*\d*|"
    r"sayı\s*:?\s*\d+|sayi\s*:?\s*\d+|tarih\s*:?\s*.{0,24}|"
    r"yönetmelik|yonetmelik|tebliğ|teblig|kanun|genelge)\s*$"
)
_TR_MONTHS = (
    r"(?:ocak|şubat|subat|mart|nisan|may[ıi]s|haziran|temmuz|"
    r"a[gğ]ustos|eyl[uü]l|ekim|kas[ıi]m|aral[ıi]k)"
)
_TR_DATE_LINE = re.compile(
    rf"(?i)^\s*\d{{1,2}}\s+{_TR_MONTHS}\s+\d{{4}}\b.*$"
)

_ISSUE_LINE = re.compile(
    r"(?i)^\s*(?:sayı|sayi)\s*:?\s*\d+\s*$|"
    r"^\s*(?:resmî|resmi)\s+gazete\s+(?:sayı|sayi)\s*:?\s*\d+\s*$|"
    r"^\s*\d{1,2}\s+\w+\s+\d{4}\s+\w+\s+(?:resmî|resmi)\s+gazete\s+(?:sayı|sayi)\s*:?\s*\d+\s*$"
)

_CLICK_EK = re.compile(
    r"(?i)^\s*ek(?:leri|i)?\s+i[cç]in\s+t[ıi]klay[ıi]n[ıi]z\.?\s*$"
)

_ISSUING_LINE = re.compile(
    r"(?i)^.{0,100}(?:bakanl[ıi][gğ][ıi]ndan|ba[sş]kanl[ıi][gğ][ıi]ndan|"
    r"odasından|odasindan|kurumundan|birliğinden|birliginden)\s*:?\s*$"
)

_ORDINAL_MADDE = re.compile(
    r"(?i)(\d+\s*/\s*[A-Za-zÇĞİÖŞÜçğıöşü]|\d+)\s*"
    r"(?:['’]?inci|nci|üncü|uncu|ncı|ıncı|inci)?\s*maddes"
)

_EK_GECICI_TARGET = re.compile(
    r"(?i)(ek\s+madde|geçici\s+madde|gecici\s+madde)\s+"
    r"(\d+(?:\s*/\s*[A-Za-zÇĞİÖŞÜçğıöşü])?)"
)

# Line-start only. Number is mandatory so "MADDE —" cannot be produced.
_MADDE_HEADER = re.compile(
    r"(?im)^\s*((?:EK\s+|GEÇİCİ\s+|Geçici\s+|Ek\s+)?)(MADDE|Madde)\s+"
    r"(\d+(?:\s*/\s*[A-Za-zÇĞİÖŞÜçğıöşü])?)"
    r"(?=\s*(?:[–—.:(-]|$|\s))"
)

_AMENDING_HINT = re.compile(
    r"(?i)("
    r"aşağıdaki şekilde değiştir|asagidaki sekilde degistir|"
    r"şeklinde değiştir|seklinde degistir|"
    r"ekteki şekilde değiştir|ekteki sekilde degistir|"
    r"ibaresi eklen|ibaresinden sonra|"
    r"fıkra eklen|fikra eklen|fıkralar eklen|"
    r"yürürlükten kaldır|yururlukten kaldir|"
    r"fıkrasının|fikrasinin|fıkrası|fikrasi|"
    r"bendinin|bendi|cümlesi|cumlesi"
    r")"
)

_BASIS_HINT = re.compile(
    r"(?i)(dayanılarak|dayanilarak|istinaden|uyarınca|uyarinca)"
)

_LAW_NO = re.compile(r"(?i)\b(\d{3,5})\s*sayılı")
_DOC_LAW = re.compile(r"(?i)\blaw:(\d+)")
_CHUNK_ARTICLE = re.compile(
    r"(?i):(?:article|ek-madde|gecici-madde):(.+)$"
)
_LABEL_ARTICLE = re.compile(
    r"(?i)(?:geçici\s+madde|gecici\s+madde|ek\s+madde|madde)\s+"
    r"(\d+(?:\s*/\s*[A-Za-zÇĞİÖŞÜçğıöşü])?)"
)

_LIST_ITEM = re.compile(
    r"(?m)^\s*(?:[-*•]|\(\s*[a-zçğıöşü0-9]+\s*\)|[a-zçğıöşü]\s*[.)]|"
    r"\d+[.)]|[A-ZÇĞİÖŞÜ]\s*[.)])\s+(.+?)\s*$"
)
_APPENDIX_LABEL = re.compile(
    r"(?i)\bEK[-–]?\s*\d+(?:\s*/\s*[A-Za-zÇĞİÖŞÜçğıöşü0-9\-]+)?"
)
_LIST_TOPIC = re.compile(
    r"(?i)(ulusal meslek standart|ötv|otv list|ekli liste|"
    r"ücret tarifes|cetvel)"
)
_APPENDIX_SWAP = re.compile(
    r"(?i)ekteki\s+şekilde\s+değiştir|ekteki\s+sekilde\s+degistir"
)

_REWRITE_RATIO = 0.35
_STRUCTURAL_CHANGE_RATIO = 0.92


def _fold(value: str) -> str:
    return (
        (value or "")
        .replace("İ", "i")
        .replace("I", "ı")
        .casefold()
        .replace("\u0307", "")
    )


def _compact(value: str) -> str:
    text = (value or "").replace("\xa0", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _law_id_from_document(document_id: str) -> str:
    match = _DOC_LAW.search(document_id or "")
    return match.group(1) if match else ""


def legislation_domain(
    title: str,
    text: str = "",
    *,
    document_id: str = "",
    source: str = "",
) -> LegislationDomain:
    """Classify a gazette item or a baseline hit for the domain lock."""
    law_id = _law_id_from_document(document_id)
    if law_id in _SGK_LAW_IDS:
        return "sgk_social"
    if law_id in _FINANCE_LAW_IDS:
        return "finance_aml"
    if law_id in _LABOR_LAW_IDS:
        return "labor"
    if (source or "").lower() == "sgk":
        return "sgk_social"
    if is_aml_or_masak(title, text) or is_financial_corporate_keep(title, text):
        return "finance_aml"
    blob = _fold(f"{title}\n{text}\n{document_id}")
    if any(
        token in blob
        for token in (
            "sgk",
            "5510",
            "4447",
            "sosyal sigorta",
            "sosyal güvenlik",
            "sosyal guvenlik",
            "e-bildirge",
            "işsizlik sigorta",
        )
    ):
        return "sgk_social"
    if any(token in blob for token in ("4857", "iş kanunu", "is kanunu", "fazla çalışma", "kıdem")):
        return "labor"
    return "other"


def domains_conflict(left: LegislationDomain, right: LegislationDomain) -> bool:
    """Financial/AML must never bind to SGK/social-security, or vice versa."""
    return {left, right} == {"finance_aml", "sgk_social"}


def _is_signature_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    folded = _fold(stripped)
    if any(name in folded for name in _NAMED_SIGNATURES):
        return True
    if _SIGNATURE_LINE.match(stripped):
        return True
    letters = re.sub(r"[^A-Za-zÇĞİÖŞÜçğıöşü ]", "", stripped)
    if 8 <= len(stripped) <= 48 and stripped == stripped.upper() and " " in letters:
        if any(part in folded for part in ("erdoğan", "erdogan", "bakan")):
            return True
    return False


def _is_header_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if _HEADER_LINE.match(stripped):
        return True
    if _TR_DATE_LINE.match(stripped):
        return True
    if _ISSUE_LINE.match(stripped):
        return True
    if _CLICK_EK.match(stripped):
        return True
    if _ISSUING_LINE.match(stripped):
        return True
    if re.fullmatch(r"\d{1,2}[./]\d{1,2}[./]\d{4}", stripped):
        return True
    return bool(re.fullmatch(r"(?i)sayı\s*:?\s*\d+", stripped))


def _is_execution_block(block: str) -> bool:
    folded = _fold(block)
    short = len(_compact(block)) < 280
    if "yürütür" in folded or "yurutur" in folded:
        if "hükümlerini" in folded or "hukumlerini" in folded or short:
            return True
    if "yürütülmesinden" in folded or "yurutulmesinden" in folded:
        return True
    if "yürürlüğe girer" in folded or "yururluge girer" in folded:
        if "yayımı tarihinde" in folded or "yayimi tarihinde" in folded:
            return True
        if short:
            return True
    return False


def _lead_after_header(block: str) -> str:
    header = _MADDE_HEADER.search(block or "")
    rest = block[header.end() :] if header else (block or "")
    rest = re.sub(r"^[\s–—.:-]+", "", rest)
    return _fold(_compact(rest))


def _is_procedural_block(block: str) -> bool:
    """Amaç / Kapsam / Dayanak / Yürürlük / Yürütme boilerplate."""
    if _is_execution_block(block):
        return True
    folded = _fold(block)
    lead = _lead_after_header(block)[:160]
    if lead.startswith(("amaç", "kapsam", "dayanak", "yürürlük", "yururluk", "yürütme", "yurutme")):
        return True
    if _BASIS_HINT.search(folded) and (
        "hazırlanmış" in folded or "hazirlanmis" in folded or "dayanak" in lead[:40]
    ):
        return True
    if re.search(r"(?i)\bamaç[ıi]\b.{0,60}d[uü]zenlemektir", folded) and len(_compact(block)) < 420:
        return True
    if re.search(r"(?i)bu y[oö]netmeli[gğ]in kapsam[ıi]", folded) and len(_compact(block)) < 420:
        return True
    return False


def _split_madde_blocks(text: str) -> list[str]:
    """Split on actual MADDE / GEÇİCİ MADDE / EK MADDE headers only.

    Instrument titles and ministry lines before the first header are dropped.
    """
    matches = list(_MADDE_HEADER.finditer(text or ""))
    if not matches:
        return [text] if (text or "").strip() else []
    blocks: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        block = (text or "")[match.start() : end].strip()
        if block:
            blocks.append(block)
    return blocks


def clean_comparison_chrome(raw: str) -> str:
    """Strip gazette künye, signatures and click-here lines; keep article citations."""
    text = _compact(raw)
    if not text:
        return ""
    kept: list[str] = []
    for line in text.splitlines():
        if _is_header_line(line) or _is_signature_line(line):
            continue
        kept.append(line.rstrip())
    body = "\n".join(kept).strip()
    matches = list(_MADDE_HEADER.finditer(body))
    if matches:
        body = body[matches[0].start() :].strip()
    return _compact(body)


def clean_new_text(raw: str) -> str:
    """Strip gazette chrome, signatures, and yürürlük/yürütme articles."""
    body = clean_comparison_chrome(raw)
    if not body:
        return ""
    substantive: list[str] = []
    for block in _split_madde_blocks(body) or [body]:
        if _is_execution_block(block):
            continue
        if _is_signature_line(block):
            continue
        substantive.append(block.strip())
    cleaned = _compact("\n\n".join(substantive))
    if len(cleaned) < 40 and not _MADDE_HEADER.search(cleaned):
        return ""
    return cleaned


def _normalize_article_token(value: str) -> str:
    token = re.sub(r"\s+", "", (value or "").upper().replace("İ", "I"))
    folded = _fold(token)
    if folded in _INVALID_ARTICLE_TOKENS:
        return ""
    if not re.match(r"^\d", token):
        return ""
    return token


def format_article_no(kind: str, number: str) -> str:
    token = _normalize_article_token(number)
    if not token:
        return ""
    kind_l = _fold(kind)
    if "geçici" in kind_l or "gecici" in kind_l:
        return f"Geçici Madde {token}"
    if kind_l.startswith("ek"):
        return f"Ek Madde {token}"
    return f"Madde {token}"


def is_valid_article_label(label: str) -> bool:
    """Reject broken titles such as 'MADDE —', 'MADDE undefined', 'MADDE NaN'."""
    text = (label or "").strip()
    if not text:
        return False
    folded = _fold(text)
    if any(bad in folded for bad in ("undefined", "nan", "none", "null")):
        return False
    digits = re.search(r"(\d+(?:\s*/\s*[A-Za-zÇĞİÖŞÜçğıöşü])?)", text)
    if not digits:
        return False
    return bool(_normalize_article_token(digits.group(1)))


def article_key(label: str) -> str:
    folded = _fold(label or "")
    match = _LABEL_ARTICLE.search(label or "")
    number = _normalize_article_token(match.group(1) if match else "")
    if not number:
        digits = re.search(r"(\d+(?:\s*/\s*[A-Za-zÇĞİÖŞÜçğıöşü])?)", label or "")
        number = _normalize_article_token(digits.group(1) if digits else "")
    if not number:
        return ""
    if "geçici" in folded or "gecici" in folded:
        return f"gecici:{number}"
    if re.search(r"\bek\b", folded) and "madde" in folded:
        return f"ek:{number}"
    return number


def _window_has(pattern: re.Pattern[str], text: str, start: int, end: int, radius: int = 140) -> bool:
    lo = max(0, start - 24)
    hi = min(len(text), end + radius)
    return bool(pattern.search(text[lo:hi]))


def extract_gazette_article(text: str) -> str:
    """MADDE / GEÇİCİ MADDE / EK MADDE header of the published instrument."""
    header = _MADDE_HEADER.search(text or "")
    if not header:
        return ""
    prefix = header.group(1) or ""
    return format_article_no(f"{prefix}Madde", header.group(3))


def extract_target_article(text: str) -> str:
    """Article of the active regulation — never a dayanak / citation ordinal.

    Amending gazettes ('5 inci maddesi aşağıdaki şekilde değiştirilmiştir')
    resolve to the parent provision. '252 nci maddesine dayanılarak' does not.
    """
    blob = text or ""
    ek_hits = list(_EK_GECICI_TARGET.finditer(blob))
    for ek in ek_hits:
        if _window_has(_BASIS_HINT, blob, ek.start(), ek.end()):
            continue
        if _window_has(_AMENDING_HINT, blob, ek.start(), ek.end()) or _AMENDING_HINT.search(blob):
            return format_article_no(ek.group(1), ek.group(2))
    ordinals = list(_ORDINAL_MADDE.finditer(blob))
    for ordinal in ordinals:
        if _window_has(_BASIS_HINT, blob, ordinal.start(), ordinal.end()):
            continue
        if not _window_has(_AMENDING_HINT, blob, ordinal.start(), ordinal.end(), radius=220):
            continue
        return format_article_no("Madde", ordinal.group(1))
    appendices = extract_appendix_labels(blob)
    if appendices and _APPENDIX_SWAP.search(blob):
        return " / ".join(appendices[:4])
    return extract_gazette_article(blob)


def extract_all_target_articles(text: str) -> list[str]:
    seen: list[str] = []
    for block in _split_madde_blocks(text) or ([text] if text.strip() else []):
        if _is_procedural_block(block):
            continue
        label = extract_target_article(block)
        if is_valid_article_label(label) and label not in seen:
            seen.append(label)
    return seen


_QUOTED_BLOCK = re.compile(r'"([^"]{12,})"')


def extract_operative_new(block: str) -> str:
    """Prefer the quoted replacement fıkra over the amending MADDE wrapper."""
    normalized = (
        (block or "")
        .replace("“", '"')
        .replace("”", '"')
        .replace("„", '"')
        .replace("‟", '"')
    )
    quoted = [chunk.strip() for chunk in _QUOTED_BLOCK.findall(normalized) if chunk.strip()]
    if quoted:
        return _compact("\n\n".join(quoted))
    return _compact(block)


_KNOWN_LAW_IDS = _FINANCE_LAW_IDS | _SGK_LAW_IDS | _LABOR_LAW_IDS


def extract_law_numbers(*blobs: str) -> set[str]:
    """Return statute numbers only — ignore Resmî Gazete issue numbers."""
    found: set[str] = set()
    for blob in blobs:
        for number in _LAW_NO.findall(blob or ""):
            if number in _KNOWN_LAW_IDS:
                found.add(number)
        doc = _DOC_LAW.search(blob or "")
        if doc:
            found.add(doc.group(1))
    return found


def hit_article_label(hit: Mapping[str, Any] | None) -> str:
    row = hit or {}
    article = str(row.get("article") or "").strip()
    if article:
        labeled = _LABEL_ARTICLE.search(article)
        if labeled:
            return extract_target_article(article) or format_article_no("Madde", labeled.group(1)) or article
        gazette = extract_gazette_article(article)
        if gazette:
            return gazette
        return article if is_valid_article_label(article) else ""
    chunk = str(row.get("chunk_id") or "")
    match = _CHUNK_ARTICLE.search(chunk)
    if match:
        kind = "Madde"
        if ":ek-madde:" in chunk:
            kind = "Ek Madde"
        elif ":gecici-madde:" in chunk:
            kind = "Geçici Madde"
        return format_article_no(kind, match.group(1))
    return ""


def comparison_query(title: str, new_text: str) -> str:
    """Strict matcher: legislation title + exact article numbers only."""
    cleaned = clean_new_text(new_text)
    articles = extract_all_target_articles(cleaned)
    if not articles:
        article = extract_target_article(cleaned) or extract_target_article(title)
        if is_valid_article_label(article):
            articles = [article]
    parts = [title.strip(), *articles]
    return "\n".join(part for part in parts if part).strip()


def _article_matches(target: str, hit: Mapping[str, Any]) -> bool:
    if not target:
        return False
    hit_label = hit_article_label(hit)
    if not hit_label:
        return False
    left = article_key(target)
    right = article_key(hit_label)
    return bool(left) and left == right


def hit_passes_comparison_gate(
    title: str,
    new_text: str,
    hit: Mapping[str, Any],
    *,
    source: str = "",
    document_id: str = "",
    target_article: str = "",
    threshold: float = COMPARISON_SIMILARITY_THRESHOLD,
) -> bool:
    similarity = float(hit.get("similarity") or 0.0)
    if similarity < threshold:
        return False
    query_domain = legislation_domain(title, new_text, document_id=document_id, source=source)
    hit_domain = legislation_domain(
        str(hit.get("title") or hit.get("article") or ""),
        str(hit.get("text") or ""),
        document_id=str(hit.get("document_id") or ""),
    )
    if domains_conflict(query_domain, hit_domain):
        return False
    query_laws = extract_law_numbers(title, new_text, document_id)
    hit_laws = extract_law_numbers(
        str(hit.get("title") or ""),
        str(hit.get("document_id") or ""),
        str(hit.get("chunk_id") or ""),
    )
    if query_laws and hit_laws and query_laws.isdisjoint(hit_laws):
        if query_domain in {"finance_aml", "sgk_social"} or hit_domain in {
            "finance_aml",
            "sgk_social",
        }:
            return False
    target = target_article or extract_target_article(clean_new_text(new_text) or new_text)
    if is_valid_article_label(target) and not _article_matches(target, hit):
        return False
    return True


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\S+|\s+", text or "")


def _wrap_added(chunk: str) -> str:
    leading, core, trailing = re.match(r"^(\s*)(.*?)(\s*)$", chunk, re.S).groups()  # type: ignore[union-attr]
    if not core:
        return html.escape(chunk)
    return f'{leading}<mark style="background:#d4edda; color:#155724;">+ {html.escape(core)}</mark>{trailing}'


def _wrap_removed(chunk: str) -> str:
    leading, core, trailing = re.match(r"^(\s*)(.*?)(\s*)$", chunk, re.S).groups()  # type: ignore[union-attr]
    if not core:
        return html.escape(chunk)
    return f'{leading}<del style="background:#f8d7da; color:#721c24;">- {html.escape(core)}</del>{trailing}'


def highlight_pair(old_text: str, new_text: str) -> tuple[str, str]:
    """Word-level HTML diff. Unchanged tokens are escaped plain text."""
    old_tokens = _tokenize(old_text)
    new_tokens = _tokenize(new_text)
    matcher = SequenceMatcher(a=old_tokens, b=new_tokens, autojunk=False)
    old_out: list[str] = []
    new_out: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        old_chunk = "".join(old_tokens[i1:i2])
        new_chunk = "".join(new_tokens[j1:j2])
        if tag == "equal":
            old_out.append(html.escape(old_chunk))
            new_out.append(html.escape(new_chunk))
        elif tag == "delete":
            old_out.append(_wrap_removed(old_chunk))
        elif tag == "insert":
            new_out.append(_wrap_added(new_chunk))
        else:
            old_out.append(_wrap_removed(old_chunk))
            new_out.append(_wrap_added(new_chunk))
    return "".join(old_out), "".join(new_out)


def _ratio(old_text: str, new_text: str) -> float:
    old = " ".join((old_text or "").split())
    new = " ".join((new_text or "").split())
    if not old or not new:
        return 0.0
    return SequenceMatcher(None, old, new).ratio()


def _token_jaccard(old_text: str, new_text: str) -> float:
    old_set = {
        token.casefold()
        for token in _tokenize(old_text)
        if token.strip() and len(token.strip()) > 3
    }
    new_set = {
        token.casefold()
        for token in _tokenize(new_text)
        if token.strip() and len(token.strip()) > 3
    }
    if not old_set or not new_set:
        return 0.0
    return len(old_set & new_set) / len(old_set | new_set)


def is_complete_rewrite(old_text: str, new_text: str) -> bool:
    """True when the provision was replaced, not lightly edited."""
    return _ratio(old_text, new_text) < _REWRITE_RATIO or _token_jaccard(old_text, new_text) < 0.22


def extract_list_items(text: str) -> list[str]:
    items = [_compact(match.group(1)) for match in _LIST_ITEM.finditer(text or "")]
    return [item for item in items if item]


def extract_appendix_labels(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in _APPENDIX_LABEL.finditer(text or ""):
        raw = re.sub(r"\s+", "", match.group(0).upper().replace("İ", "I"))
        if raw.startswith("EK") and not raw.startswith("EK-"):
            raw = "EK-" + raw[2:]
        key = _fold(raw)
        if key not in seen:
            seen.add(key)
            found.append(raw)
    return found


def is_list_or_appendix(text: str, title: str = "") -> bool:
    """True only for annex swaps or dedicated lists (ÖTV, meslek standartları)."""
    blob = f"{title}\n{text}"
    if _APPENDIX_SWAP.search(text or "") and extract_appendix_labels(text):
        return True
    if not _LIST_TOPIC.search(blob):
        return False
    return bool(extract_list_items(text) or extract_appendix_labels(text))


def list_diff_items(old_text: str, new_text: str) -> tuple[list[str], list[str]]:
    old_items = extract_list_items(old_text) or extract_appendix_labels(old_text)
    new_items = extract_list_items(new_text) or extract_appendix_labels(new_text)
    if not old_items and not new_items:
        old_items = [ln.strip() for ln in (old_text or "").splitlines() if ln.strip()]
        new_items = [ln.strip() for ln in (new_text or "").splitlines() if ln.strip()]
    old_keys = {_fold(item) for item in old_items}
    new_keys = {_fold(item) for item in new_items}
    added = [item for item in new_items if _fold(item) not in old_keys]
    removed = [item for item in old_items if _fold(item) not in new_keys]
    return added, removed


def _one_sentence(text: str, limit: int = 180) -> str:
    compact = " ".join((text or "").split())
    if not compact:
        return ""
    cut = re.split(r"(?<=[.;])\s+", compact, maxsplit=1)[0]
    if len(cut) > limit:
        cut = cut[: limit - 1].rstrip() + "…"
    return cut


def rewrite_summary(old_text: str, new_text: str) -> str:
    old_tokens = [tok for tok in _tokenize(old_text) if tok.strip()]
    new_tokens = [tok for tok in _tokenize(new_text) if tok.strip()]
    matcher = SequenceMatcher(a=old_tokens, b=new_tokens, autojunk=False)
    added: list[str] = []
    removed: list[str] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in {"replace", "delete"}:
            removed.append(" ".join(old_tokens[i1:i2]))
        if tag in {"replace", "insert"}:
            added.append(" ".join(new_tokens[j1:j2]))
    added_line = _one_sentence(" ".join(added)) or "Yeni hüküm önceki metni bütünüyle karşılamamaktadır."
    removed_line = (
        _one_sentence(" ".join(removed)) or "Önceki hüküm bu metinde yer almamaktadır."
    )
    return (
        f"🟢 **Ne Eklendi/Değişti:** {added_line}\n"
        f"🔴 **Ne Yürürlükten Kalktı:** {removed_line}"
    )


def _bullets(items: Sequence[str], limit: int = 12) -> str:
    lines = [f"• {item}" for item in list(items)[:limit] if item]
    if len(items) > limit:
        lines.append(f"• … (+{len(items) - limit} kalem)")
    return "\n".join(lines)


def _change_summary(
    *,
    article_no: str,
    new_clean: str,
    old_clean: str,
    matched: bool,
    added_items: Sequence[str] | None = None,
    removed_items: Sequence[str] | None = None,
    list_mode: bool = False,
) -> str:
    prefix = f"{article_no}: " if is_valid_article_label(article_no) else ""
    if list_mode:
        added_block = _bullets(added_items or []) or "• —"
        removed_block = _bullets(removed_items or []) or (
            f"• {FALLBACK_OLD_TEXT}" if not matched else "• —"
        )
        return (
            f"{prefix}liste / ek değişikliği\n"
            f"🟢 **Eklenen / değişen kalemler:**\n{added_block}\n"
            f"🔴 **Kaldırılan / önceki kalemler:**\n{removed_block}"
        )
    if not matched:
        return (
            f"{prefix}eski madde tabanında doğrulanmış eşleşme yok "
            "(doğrudan ek / değişiklik maddesi)."
        ).strip()
    if is_complete_rewrite(old_clean, new_clean):
        return rewrite_summary(old_clean, new_clean)
    lead = _one_sentence(new_clean)
    if lead:
        return f"{prefix}{lead}".strip()
    return f"{prefix}hüküm metni güncellenmiştir.".strip()


def _comparison_payload(
    *,
    article_no: str,
    old_text_clean: str,
    new_text_clean: str,
    has_exact_old_match: bool,
    render_mode: str = "side_by_side",
    added_items: Sequence[str] | None = None,
    removed_items: Sequence[str] | None = None,
) -> dict[str, Any]:
    label = article_no if is_valid_article_label(article_no) else ""
    added = [item for item in (added_items or []) if item]
    removed = [item for item in (removed_items or []) if item]
    list_mode = render_mode == "list_summary"
    old_html: str
    new_html: str
    if render_mode == "procedural_notice":
        old_html = ""
        new_html = html.escape(PROCEDURAL_NOTICE)
    elif list_mode:
        old_html = html.escape(_bullets(removed) or (old_text_clean if not has_exact_old_match else "—"))
        new_html = html.escape(_bullets(added) or new_text_clean)
    elif has_exact_old_match:
        old_html, new_html = highlight_pair(old_text_clean, new_text_clean)
    else:
        old_html = html.escape(old_text_clean)
        new_html = html.escape(new_text_clean)
    summary = (
        PROCEDURAL_NOTICE
        if render_mode == "procedural_notice"
        else _change_summary(
            article_no=label,
            new_clean=new_text_clean,
            old_clean=old_text_clean if has_exact_old_match else "",
            matched=has_exact_old_match,
            added_items=added,
            removed_items=removed,
            list_mode=list_mode,
        )
    )
    return {
        "article_no": label,
        "old_text_clean": old_text_clean,
        "new_text_clean": new_text_clean,
        "change_summary": summary,
        "has_exact_old_match": has_exact_old_match,
        "old_text_html": old_html,
        "new_text_html": new_html,
        "is_rewrite": bool(
            has_exact_old_match and is_complete_rewrite(old_text_clean, new_text_clean)
        ),
        "render_mode": render_mode,
        "added_items": added,
        "removed_items": removed,
    }


def _best_hit(
    title: str,
    new_text: str,
    hits: Sequence[Mapping[str, Any]],
    *,
    source: str,
    document_id: str,
    target_article: str,
) -> Mapping[str, Any] | None:
    eligible = [
        hit
        for hit in hits
        if hit_passes_comparison_gate(
            title,
            new_text,
            hit,
            source=source,
            document_id=document_id,
            target_article=target_article,
        )
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda hit: float(hit.get("similarity") or 0.0))


def _fallback_row(article_no: str, new_text_clean: str, **extra: Any) -> dict[str, Any]:
    return _comparison_payload(
        article_no=article_no,
        old_text_clean=FALLBACK_OLD_TEXT,
        new_text_clean=new_text_clean,
        has_exact_old_match=False,
        **extra,
    )


def build_legal_comparisons(
    *,
    title: str,
    new_text: str,
    hits: Sequence[Mapping[str, Any]] | None = None,
    source: str = "",
    document_id: str = "",
) -> list[dict[str, Any]]:
    """Return one JSON object per substantive madde (always at least one)."""
    cleaned = clean_new_text(new_text)
    blocks = [block for block in _split_madde_blocks(cleaned) if block]
    if not blocks:
        blocks = [cleaned] if cleaned else [""]
    rows: list[dict[str, Any]] = []
    skipped_procedural = 0
    used_chunk_ids: set[str] = set()
    for block in blocks:
        article_no = extract_target_article(block) or extract_gazette_article(block)
        if not is_valid_article_label(article_no):
            article_no = ""
        remaining = [
            hit
            for hit in (hits or [])
            if str(hit.get("chunk_id") or "") not in used_chunk_ids
        ]
        hit = _best_hit(
            title,
            block,
            remaining,
            source=source,
            document_id=document_id,
            target_article=article_no,
        )
        old_body = clean_comparison_chrome(str(hit.get("text") or "")) if hit else ""
        if _is_procedural_block(block):
            if not old_body or _ratio(old_body, extract_operative_new(block) or block) >= _STRUCTURAL_CHANGE_RATIO:
                skipped_procedural += 1
                continue
        if not article_no and not _MADDE_HEADER.search(block) and len(blocks) > 1:
            continue
        operative_new = extract_operative_new(block) or block or cleaned
        list_mode = is_list_or_appendix(operative_new, title) or is_list_or_appendix(block, title)
        added: list[str] = []
        removed: list[str] = []
        if list_mode:
            added, removed = list_diff_items(old_body, operative_new)
            if not added:
                added = extract_appendix_labels(block) or extract_list_items(operative_new)
        render_mode = "list_summary" if list_mode and (added or removed or extract_appendix_labels(block)) else "side_by_side"
        if hit is None:
            rows.append(
                _fallback_row(
                    article_no,
                    block or cleaned,
                    render_mode=render_mode,
                    added_items=added,
                    removed_items=removed,
                )
            )
            continue
        used_chunk_ids.add(str(hit.get("chunk_id") or ""))
        label = hit_article_label(hit) or article_no
        if is_valid_article_label(label) and article_key(label) == article_key(article_no):
            article_no = label
        rows.append(
            _comparison_payload(
                article_no=article_no,
                old_text_clean=old_body,
                new_text_clean=operative_new,
                has_exact_old_match=True,
                render_mode=render_mode,
                added_items=added,
                removed_items=removed,
            )
        )
    if not rows and skipped_procedural:
        return [
            _comparison_payload(
                article_no="",
                old_text_clean="",
                new_text_clean=cleaned,
                has_exact_old_match=False,
                render_mode="procedural_notice",
            )
        ]
    return rows or [
        _fallback_row("", cleaned)
    ]
