from __future__ import annotations

from config.prompts import RELEVANCE_FILTER_SYSTEM
from config.relevance import classify_relevance
from mocks.llm import complete
from schemas.outputs import AuditEvent, RelevanceResult
from schemas.state import PulseState


def _filter_payload(is_relevant: bool, reason: str, *, via: str) -> dict:
    return {
        "is_relevant": is_relevant,
        "relevance_reason": reason,
        "audit_log": [
            AuditEvent(
                node="ISO_Relevance_Filter_Node",
                action="filter",
                detail=f"is_relevant={is_relevant}; {via}; {reason}",
            )
        ],
    }


def relevance_filter_node(state: PulseState) -> dict:
    """ISO_Relevance_Filter_Node: keep industrial impact, drop admin noise."""
    title = str(state.get("title") or "")
    new_text = str(state.get("new_text") or "")
    document_id = str(state.get("document_id") or "")

    verdict, reason = classify_relevance(title, new_text, document_id)
    if verdict == "drop":
        return _filter_payload(False, reason, via="taxonomy-drop")
    if verdict == "keep":
        return _filter_payload(True, reason, via="taxonomy-keep")

    result = complete(
        RelevanceResult,
        RELEVANCE_FILTER_SYSTEM,
        (
            f"document_id: {document_id}\n"
            f"source: {state['source']}\n"
            f"title: {title}\n"
            f"new_text:\n{new_text}\n"
        ),
        context={
            "document_id": document_id,
            "title": title,
            "new_text": new_text,
        },
    )
    return _filter_payload(result.is_relevant, result.reason, via="llm")
