from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, computed_field

Department = Literal["ik", "hukuk", "mali"]
Urgency = Literal["low", "medium", "critical"]
SourceName = Literal["resmi_gazete", "mevzuat", "sgk", "csgb"]

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


class RouteDecision(BaseModel):
    """Structured output from Router_Agent_Node."""

    departments: list[Department] = Field(
        min_length=1,
        description="One or more of ik, hukuk, mali.",
    )
    reason: str = Field(description="Short Turkish explanation of the routing choice.")


class DepartmentAnalysis(BaseModel):
    """Structured output from IK_Node, Hukuk_Node, or Mali_Node."""

    department: Department
    summary: str = Field(description="Turkish summary of the change for this department.")
    obligation_change: str = Field(
        description=(
            "Answer to: Bu değişiklikle sanayicinin üzerindeki hukuki ve "
            "operasyonel yükümlülük nasıl değişmiştir?"
        )
    )
    operational_impact: str = Field(
        description="Practical operational impact for an industrial employer."
    )
    rag_chunk_ids: list[str] = Field(default_factory=list)
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
    notes: str = ""


class DeliveryPayload(BaseModel):
    """UI-ready JSON from Delivery_Agent_Node."""

    document_id: str
    source: str
    title: str
    summary: str
    urgency: Urgency
    departments: list[Department]
    needs_review: bool
    hallucination_score: float = Field(ge=0.0, le=1.0)
    analyses: dict[str, DepartmentAnalysis] = Field(default_factory=dict)

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
