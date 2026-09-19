from __future__ import annotations

from config.prompts import DELIVERY_SYSTEM
from mocks.llm import complete
from schemas.outputs import AuditEvent, DeliveryPayload
from schemas.state import PulseState


def delivery_node(state: PulseState) -> dict:
    """Delivery_Agent_Node: urgency + UI JSON. Still emits when needs_review is true."""
    payload = complete(
        DeliveryPayload,
        DELIVERY_SYSTEM,
        (
            f"document_id: {state['document_id']}\n"
            f"source: {state['source']}\n"
            f"title: {state['title']}\n"
            f"departments: {state.get('departments') or []}\n"
            f"needs_review: {state.get('needs_review', False)}\n"
            f"hallucination_score: {state.get('hallucination_score', 0.0)}\n"
            f"relevance_reason: {state.get('relevance_reason', '')}\n"
            f"new_text:\n{state['new_text']}\n"
        ),
        context={
            "document_id": state["document_id"],
            "source": state["source"],
            "title": state["title"],
            "departments": state.get("departments") or [],
            "analyses": state.get("analyses") or {},
            "needs_review": state.get("needs_review", False),
            "hallucination_score": state.get("hallucination_score", 0.0),
        },
    )
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
