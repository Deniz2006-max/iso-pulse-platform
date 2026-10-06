from __future__ import annotations

from typing import Annotated, NotRequired, TypedDict

from schemas.outputs import (
    AuditEvent,
    DeliveryPayload,
    Department,
    DepartmentAnalysis,
    SourceName,
    Urgency,
    VerificationResult,
)


def merge_analyses(
    left: dict[str, DepartmentAnalysis] | None,
    right: dict[str, DepartmentAnalysis] | None,
) -> dict[str, DepartmentAnalysis]:
    """Reducer so parallel IK/Hukuk/Mali nodes can each write one analysis."""
    merged: dict[str, DepartmentAnalysis] = dict(left or {})
    merged.update(right or {})
    return merged


def concat_audit(
    left: list[AuditEvent] | None,
    right: list[AuditEvent] | None,
) -> list[AuditEvent]:
    return list(left or []) + list(right or [])


class PulseState(TypedDict):
    """Shared LangGraph state for a single legislation-change run."""

    source: SourceName
    document_id: str
    title: str
    old_text: str | None
    new_text: str
    diff: str
    sha256: str
    analyses: Annotated[dict[str, DepartmentAnalysis], merge_analyses]
    audit_log: Annotated[list[AuditEvent], concat_audit]
    is_relevant: NotRequired[bool]
    relevance_reason: NotRequired[str]
    sector_scope: NotRequired[str]
    departments: NotRequired[list[Department]]
    verification: NotRequired[VerificationResult]
    delivery: NotRequired[DeliveryPayload]
    hallucination_score: NotRequired[float]
    needs_review: NotRequired[bool]
    urgency: NotRequired[Urgency]
    department_scores: NotRequired[dict[str, float]]
    dropped_departments: NotRequired[list[str]]
    retrieved_chunks: NotRequired[list[dict]]
    retrieved_provision_id: NotRequired[str]
    baseline_document_ids: NotRequired[list[str]]
    rag_mode: NotRequired[str]
    rag_confidence: NotRequired[float]
    rag_status: NotRequired[str]
    rag_reason: NotRequired[str]
