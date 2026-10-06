from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from config.rag_routing import RagMode

from pydantic import BaseModel, Field, computed_field

Department = Literal["ik", "hukuk", "mali"]
Urgency = Literal["low", "medium", "critical"]
SourceName = Literal["resmi_gazete", "mevzuat", "sgk", "csgb"]

DEPARTMENT_DISPLAY = {
    "ik": "İnsan Kaynakları (İK)",
    "hukuk": "Hukuk & Mevzuat",
    "mali": "Maliye / Finans",
    "maliye": "Maliye / Finans",
}


def department_label(code: str | None) -> str:
    key = str(code or "").strip().lower()
    return DEPARTMENT_DISPLAY.get(key, str(code or "—"))

URGENCY_LABELS: dict[Urgency, Literal["Düşük", "Orta", "Kritik"]] = {
    "low": "Düşük",
    "medium": "Orta",
    "critical": "Kritik",
}


class RelevanceResult(BaseModel):
    """Structured output from ISO_Relevance_Filter_Node."""

    is_relevant: bool = Field(
        description="False for industrial noise (appointments, tenders, personal notices)."
    )
    reason: str = Field(description="Short Turkish explanation of the keep/drop decision.")


class DepartmentScore(BaseModel):
    """Router confidence for one department. Send only if confidence >= 0.75."""

    department: Department
    confidence: float = Field(ge=0.0, le=1.0)


class RouteDecision(BaseModel):
    """Structured output from Router_Agent_Node."""

    departments: list[Department] = Field(
        min_length=1,
        description=(
            "Only departments whose core domain is directly amended. "
            "Do not include mali or hukuk for a pure overtime/payroll (ik) change. "
            "Do not include mali without a monetary/tax threshold. "
            "Do not include ik for pure corporate governance."
        ),
    )
    scores: list[DepartmentScore] = Field(
        default_factory=list,
        description="Per-department confidence. Omit a department if confidence < 0.75.",
    )
    reason: str = Field(description="Short Turkish explanation of the routing choice.")


class DepartmentAnalysis(BaseModel):
    """Structured output from IK_Node, Hukuk_Node, or Mali_Node."""

    department: Department
    summary: str = Field(
        description=(
            "HIGH-DETAIL Turkish executive card with three sections: "
            "📌 Önemli Düzenlemeler & Maddeler (numbers, madde/code refs, "
            "percentages, geography); 🏭 Sanayi ve İşverene Etkisi "
            "(factory/OSB/HR/finance impact); 📋 Sorumlu Departman İçin "
            "Aksiyon Maddeleri (numbered steps). Never a title-only "
            "'yürürlüğe konulmuştur' sentence."
        )
    )
    obligation_change: str = Field(
        description=(
            "RAG: Eski durum vs Yeni durum with specific madde/eşik numbers. "
            "Fallback: operative maddeler, rates, and scope from new_text. "
            "Never a title-only yürürlüğe line."
        )
    )
    operational_impact: str = Field(
        description=(
            "Numbered step-by-step actions for this department (İK, Maliye, "
            "or Hukuk): verb + artefact (sözleşme, bordro, izin, muhasebe)."
        )
    )
    rag_chunk_ids: list[str] = Field(default_factory=list)
    analysis_mode: RagMode | None = Field(
        default=None,
        description="rag = provision-level Chroma context; fallback = LLM general analysis.",
    )
    citations: list[str] = Field(
        default_factory=list,
        description="Article numbers or phrases grounded in source/RAG text.",
    )
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class VerificationResult(BaseModel):
    """Structured output from Verifier_Critic_Node."""

    passed: bool = Field(
        description="True only if hallucination_score < 0.35 and no critical unsupported claim."
    )
    hallucination_score: float = Field(ge=0.0, le=1.0)
    needs_review: bool = Field(
        description="True when verification fails; delivery still emits JSON."
    )
    unsupported_claims: list[str] = Field(default_factory=list)
    dropped_departments: list[str] = Field(
        default_factory=list,
        description="Specialist analyses dropped for missing domain keywords/actions.",
    )
    notes: str = ""


class DeliveryPayload(BaseModel):
    """UI-ready JSON from Delivery_Agent_Node."""

    document_id: str
    source: str
    title: str
    summary: str = Field(
        description=(
            "UI card body in Turkish with ALL three headings: "
            "📌 **Önemli Düzenlemeler & Maddeler**; "
            "🏭 **Sanayi ve İşverene Etkisi**; "
            "📋 **Sorumlu Departman İçin Aksiyon Maddeleri**. "
            "Multi-bullet, cite numbers/articles from new_text. "
            "Forbidden: title-only 'yürürlüğe konulmuştur' or "
            "'ilgili departman metni incelemelidir'."
        )
    )
    urgency: Urgency
    departments: list[Department]
    needs_review: bool
    hallucination_score: float = Field(ge=0.0, le=1.0)
    analyses: dict[str, DepartmentAnalysis] = Field(default_factory=dict)
    rag_mode: RagMode | None = Field(
        default=None,
        description="rag when Chroma similarity is above the floor; fallback otherwise.",
    )
    rag_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    rag_status: str = Field(
        default="",
        description="UI badge: RAG Enabled vs Fallback Mode.",
    )

    @computed_field
    @property
    def urgency_label(self) -> Literal["Düşük", "Orta", "Kritik"]:
        return URGENCY_LABELS[self.urgency]


class AuditEvent(BaseModel):
    """One LangGraph step for later backend audit-log persistence."""

    node: str
    action: str
    detail: str = ""
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
