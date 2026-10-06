from __future__ import annotations

import re
from typing import Mapping

from config.prompts import SPECIALIST_NO_MATCH
from config.relevance import _fold, implied_departments
from schemas.outputs import Department, DepartmentAnalysis, DepartmentScore

# A department is selected only when the text itself changes that domain's
# core rules. Secondary operational knock-ons (payroll software, generic
# documentation, incidental penalties) must not open extra Send branches.

SEND_CONFIDENCE_FLOOR = 0.75

IK_CORE = (
    "fazla çalışma",
    "fazla mesai",
    "asgari ücret",
    "iş kanunu",
    "iş sözleş",
    "sözleşmeli personel",
    "personel çalıştır",
    "personel esas",
    "istihdam",
    "çalışma koşul",
    "harcırah",
    "çalışma süresi",
    "çalışma izni",
    "yıllık izin",
    "kıdem",
    "ihbar",
    "iş sağlığı",
    "iş güvenliği",
    "işkolu",
    "sendika",
    "toplu iş",
    "sgk",
    "e-bildirge",
    "bordro",
    "yan hak",
    "4857",
    "5510",
    "6331",
    "6356",
)

HUKUK_CORE = (
    "çevre yönet",
    "çevre izin",
    "çevre kanunu",
    "çevre",
    "emisyon",
    "karbon",
    "atık yönet",
    "yeşil mutabakat",
    "lisans",
    "izin belgesi",
    "faaliyet durdur",
    "şirketler hukuku",
    "ticaret kanunu",
    "sözleşme hukuku",
    "kvkk",
    "kişisel veri",
    "idari yargı",
    "imtiyaz",
    "sorumluluk hukuku",
    "üretim standard",
    "kota",
    "yönetmelik",
    "tebliğ",
    "standart",
)

MALI_CORE = (
    "vergi",
    "gelir vergisi",
    "kurumlar vergisi",
    "kdv",
    "ötv",
    "istisna",
    "stopaj",
    "tevkifat",
    "damga",
    "gümrük",
    "teşvik",
    "organize sanayi",
    "osb",
    "fatura",
    "e-fatura",
    "muhasebe",
    "vergi usul",
    "tarife",
    "enerji",
    "banka",
    "finansal raporlama",
    "dış ticaret",
)

MALI_TAX_INSTRUMENTS = (
    "vergi",
    "gelir vergisi",
    "kurumlar vergisi",
    "kdv",
    "ötv",
    "stopaj",
    "tevkifat",
    "istisna",
    "damga",
    "gümrük",
    "vergi usul",
    "matrah",
    "e-fatura",
    "fatura",
    "muhasebe",
    "teşvik",
    "organize sanayi",
    "osb",
    "tarife",
    "enerji",
    "banka",
    "finansal raporlama",
)

_MALI_THRESHOLD = re.compile(
    r"(\d+[.,]?\d*|\b%|yüzde|puan|\btl\b|lira|oran|prim|tarife|matrah)",
    re.IGNORECASE,
)

# Corporate governance / company-law language that is not an HR event.
CORPORATE_GOVERNANCE = (
    "yönetim kurulu",
    "genel kurul",
    "ana sözleşme",
    "pay senedi",
    "ticaret sicil",
    "sermaye artır",
    "ortaklık pay",
    "şirket unvan",
    "mersis",
    "pay defteri",
    "imtiyazlı pay",
)

IK_LABOR_STRONG = (
    "fazla çalışma",
    "fazla mesai",
    "asgari ücret",
    "iş sözleş",
    "sözleşmeli personel",
    "personel çalıştır",
    "istihdam",
    "çalışma koşul",
    "harcırah",
    "çalışma süresi",
    "çalışma izni",
    "yan hak",
    "yıllık izin",
    "kıdem",
    "ihbar",
    "iş sağlığı",
    "iş güvenliği",
    "sgk",
    "e-bildirge",
    "bordro",
    "sendika",
    "toplu iş",
    "işkolu",
    "analık",
    "babalık",
    "ücretli izin",
    "işe iade",
    "özlük",
    "işçi",
)

ANALYSIS_DOMAIN_KEYWORDS: dict[Department, tuple[str, ...]] = {
    "ik": (
        "bordro",
        "sgk",
        "e-bildirge",
        "işçi",
        "izin",
        "mesai",
        "ücret",
        "özlük",
        "vardiya",
        "analık",
        "babalık",
        "kıdem",
        "ihbar",
        "sendika",
        "pdks",
        "işe dönüş",
        "çalışma süresi",
        "asgari ücret",
        "çalışma izni",
        "yan hak",
        "sözleşmeli",
        "personel",
        "istihdam",
        "harcırah",
    ),
    "mali": (
        "vergi",
        "stopaj",
        "kdv",
        "ötv",
        "tarife",
        "enerji",
        "gümrük",
        "tevkifat",
        "istisna",
        "teşvik",
        "muhasebe",
        "fatura",
        "matrah",
        "prim",
        "damga",
        "gümrük",
        "tahakkuk",
        "muhtasar",
        "e-fatura",
    ),
    "hukuk": (
        "lisans",
        "izin belgesi",
        "sözleşme",
        "kvkk",
        "kişisel veri",
        "aydınlatma",
        "faaliyet durdur",
        "emisyon",
        "veri sorumlusu",
        "kurul",
        "yükümlülük",
        "dava",
        "idari para",
        "anonim",
        "silme",
        "karbon",
        "atık",
        "kota",
    ),
}

ANALYSIS_ACTIONS = (
    "güncelle",
    "öde",
    "bildir",
    "başvur",
    "kayıt",
    "sil",
    "yok et",
    "anonim",
    "tebliğ",
    "uygula",
    "planla",
    "koru",
    "hesap",
    "zorunda",
    "yükümlü",
    "vermek",
    "işlemek",
    "sunmak",
    "kesmek",
    "yatır",
    "denetle",
)


def core_departments(text: str) -> list[Department]:
    blob = _fold(text)
    found: list[Department] = []
    if any(hint in blob for hint in IK_CORE):
        found.append("ik")
    if any(hint in blob for hint in HUKUK_CORE):
        found.append("hukuk")
    if any(hint in blob for hint in MALI_CORE):
        found.append("mali")
    return apply_negative_constraints(found, text)


def has_mali_threshold(text: str) -> bool:
    """Maliye: tax instrument + threshold, or an OSB/incentive rule."""
    blob = _fold(text)
    if any(token in blob for token in ("teşvik", "tesvik", "organize sanayi", "osb")):
        return True
    has_instrument = any(token in blob for token in MALI_TAX_INSTRUMENTS)
    has_threshold = bool(_MALI_THRESHOLD.search(blob))
    return has_instrument and has_threshold


def is_pure_corporate_governance(text: str) -> bool:
    blob = _fold(text)
    return any(token in blob for token in CORPORATE_GOVERNANCE) and not any(
        token in blob for token in IK_LABOR_STRONG
    )


def is_work_permit_hr(text: str) -> bool:
    """Çalışma izni / yabancı işçi is IK; 'izin belgesi' must not open Hukuk."""
    blob = _fold(text)
    hr_permit = "çalışma izni" in blob or "yabancı uyruk" in blob
    hukuk_core = any(
        token in blob
        for token in ("çevre izin", "kvkk", "emisyon", "karbon", "lisans", "kişisel veri")
    )
    return hr_permit and not hukuk_core


def apply_negative_constraints(
    departments: list[Department],
    text: str,
) -> list[Department]:
    """Drop departments that only appear as side effects."""
    kept: list[Department] = []
    for department in _unique(departments):
        if department == "mali" and not has_mali_threshold(text):
            continue
        if department == "ik" and is_pure_corporate_governance(text):
            continue
        if department == "hukuk" and is_work_permit_hr(text):
            continue
        kept.append(department)
    return kept


def heuristic_confidence(department: Department, text: str) -> float:
    blob = _fold(text)
    cores = {"ik" : IK_CORE, "hukuk": HUKUK_CORE, "mali": MALI_CORE}[department]
    hits = sum(1 for hint in cores if hint in blob)
    if hits == 0:
        return 0.0
    if hits == 1:
        return 0.80
    return min(0.95, 0.82 + 0.04 * hits)


def scores_to_map(
    scores: list[DepartmentScore] | None,
) -> dict[Department, float]:
    mapped: dict[Department, float] = {}
    for item in scores or []:
        mapped[item.department] = item.confidence
    return mapped


def constrain_departments(
    proposed: list[Department],
    text: str,
    scores: Mapping[Department, float] | None = None,
) -> tuple[list[Department], dict[str, float]]:
    """Keep core-domain picks; always emit at least one department for a kept item."""
    keyword_allowed = set(core_departments(text))
    candidates = _unique(proposed)
    if keyword_allowed:
        intersected = [department for department in candidates if department in keyword_allowed]
        candidates = intersected or sorted(keyword_allowed)
    candidates = apply_negative_constraints(candidates, text)
    if not candidates:
        fallback = [
            department
            for department in implied_departments(text, "")
            if department in {"ik", "hukuk", "mali"}
        ]
        candidates = fallback or ["hukuk"]

    kept: list[Department] = []
    scored: dict[str, float] = {}
    for department in candidates:
        confidence = (
            float(scores[department])
            if scores and department in scores
            else heuristic_confidence(department, text)
        )
        if confidence < SEND_CONFIDENCE_FLOOR:
            confidence = SEND_CONFIDENCE_FLOOR
        scored[department] = confidence
        kept.append(department)
    if not kept:
        scored["hukuk"] = SEND_CONFIDENCE_FLOOR
        kept = ["hukuk"]
    return kept, scored


def analysis_has_domain_signal(
    department: Department,
    analysis: DepartmentAnalysis,
) -> bool:
    """True when the specialist named domain keywords and a concrete action."""
    blob = " ".join(
        [
            analysis.summary,
            analysis.obligation_change,
            analysis.operational_impact,
            " ".join(analysis.citations),
        ]
    )
    if SPECIALIST_NO_MATCH in blob:
        return True
    lowered = blob.lower()
    has_keyword = any(token in lowered for token in ANALYSIS_DOMAIN_KEYWORDS[department])
    has_action = any(token in lowered for token in ANALYSIS_ACTIONS)
    return has_keyword and has_action


def _unique(departments: list[Department]) -> list[Department]:
    seen: set[Department] = set()
    ordered: list[Department] = []
    for department in departments:
        if department not in seen:
            seen.add(department)
            ordered.append(department)
    return ordered
