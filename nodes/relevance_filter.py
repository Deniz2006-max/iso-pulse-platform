from __future__ import annotations

from config.prompts import RELEVANCE_FILTER_SYSTEM
from mocks.llm import complete
from schemas.outputs import AuditEvent, RelevanceResult
from schemas.state import PulseState


def relevance_filter_node(state: PulseState) -> dict:
    """ISO_Relevance_Filter_Node: drop industrial noise before routing."""
    result = complete(
        RelevanceResult,
        RELEVANCE_FILTER_SYSTEM,
        (
            f"document_id: {state['document_id']}\n"
            f"source: {state['source']}\n"
            f"title: {state['title']}\n"
            f"new_text:\n{state['new_text']}\n"
        ),
        context={
            "document_id": state["document_id"],
            "title": state["title"],
            "new_text": state["new_text"],
        },
    )
    return {
        "is_relevant": result.is_relevant,
        "relevance_reason": result.reason,
        "audit_log": [
            AuditEvent(
                node="ISO_Relevance_Filter_Node",
                action="filter",
                detail=f"is_relevant={result.is_relevant}; {result.reason}",
            )
        ],
    }
