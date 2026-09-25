from __future__ import annotations

from schemas.outputs import Department

# A department is selected only when the text itself changes that domain's
# core rules. Secondary operational knock-ons (payroll software, generic
# documentation, incidental penalties) must not open extra Send branches.

IK_CORE = (
    "fazla çalışma",
    "fazla mesai",
    "asgari ücret",
    "iş kanunu",
    "iş sözleş",
    "çalışma süresi",
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
)

HUKUK_CORE = (
    "çevre izin",
    "çevre kanunu",
    "emisyon",
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
)

MALI_CORE = (
    "vergi",
    "gelir vergisi",
    "kurumlar vergisi",
    "kdv",
    "istisna",
    "stopaj",
    "tevkifat",
    "damga",
    "gümrük",
    "teşvik",
    "fatura",
    "e-fatura",
    "muhasebe",
    "vergi usul",
)


def core_departments(text: str) -> list[Department]:
    blob = text.lower()
    found: list[Department] = []
    if any(hint in blob for hint in IK_CORE):
        found.append("ik")
    if any(hint in blob for hint in HUKUK_CORE):
        found.append("hukuk")
    if any(hint in blob for hint in MALI_CORE):
        found.append("mali")
    return found


def constrain_departments(
    proposed: list[Department],
    text: str,
) -> list[Department]:
    """Keep LLM picks that match a core domain; never add side-effect routes."""
    allowed = core_departments(text)
    if not allowed:
        return _unique(proposed)
    kept = [department for department in _unique(proposed) if department in allowed]
    return kept or allowed


def _unique(departments: list[Department]) -> list[Department]:
    seen: set[Department] = set()
    ordered: list[Department] = []
    for department in departments:
        if department not in seen:
            seen.add(department)
            ordered.append(department)
    return ordered
