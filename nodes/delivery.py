from __future__ import annotations

from config.prompts import DELIVERY_SYSTEM
from mocks.llm import complete
from schemas.outputs import AuditEvent, DeliveryPayload
from schemas.state import PulseState


def delivery_node(state: PulseState) -> dict:
    """Delivery_Agent_Node: urgency + UI JSON. Still emits when needs_review is true."""
    analyses = state.get("analyses") or {}
    dropped = set(state.get("dropped_departments") or [])
    analyses = {
        department: item
        for department, item in analyses.items()
        if department not in dropped
    }
    departments = [
        department
        for department in (state.get("departments") or [])
        if department not in dropped
    ]
    analysis_json = {
        department: item.model_dump(mode="json")
        for department, item in analyses.items()
    }
    payload = complete(
        DeliveryPayload,
        DELIVERY_SYSTEM,
        (
            f"document_id: {state['document_id']}\n"
            f"source: {state['source']}\n"
            f"title: {state['title']}\n"
            f"departments: {departments}\n"
            f"needs_review: {state.get('needs_review', False)}\n"
            f"hallucination_score: {state.get('hallucination_score', 0.0)}\n"
            f"relevance_reason: {state.get('relevance_reason', '')}\n"
            f"new_text:\n{state['new_text']}\n"
            f"analyses:\n{analysis_json}\n"
        ),
        context={
            "document_id": state["document_id"],
            "source": state["source"],
            "title": state["title"],
            "departments": departments,
            "analyses": analyses,
            "needs_review": state.get("needs_review", False),
            "hallucination_score": state.get("hallucination_score", 0.0),
        },
    )
    updates = {}
    if payload.analyses:
        updates["analyses"] = {
            department: item
            for department, item in payload.analyses.items()
            if department not in dropped
        } or analyses
    elif analyses:
        updates["analyses"] = analyses
    if departments and payload.departments:
        updates["departments"] = [
            department
            for department in payload.departments
            if department not in dropped
        ] or departments
    if payload.document_id != state["document_id"]:
        updates["document_id"] = state["document_id"]
    if payload.source != state["source"]:
        updates["source"] = state["source"]
    if updates:
        payload = payload.model_copy(update=updates)

    return {
        "delivery": payload,
        "urgency": payload.urgency,
        "needs_review": payload.needs_review,
        "hallucination_score": payload.hallucination_score,
        "audit_log": [
            AuditEvent(
                node="Delivery_Agent_Node",
                action="deliver",
                detail=(
                    f"urgency={payload.urgency}; "
                    f"needs_review={payload.needs_review}"
                ),
            )
        ],
    }
