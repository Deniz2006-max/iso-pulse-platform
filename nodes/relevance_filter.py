from __future__ import annotations

from config.relevance import audience_scope, classify_relevance, force_keep_departments
from schemas.outputs import AuditEvent
from schemas.state import PulseState


def _filter_payload(
    is_relevant: bool,
    reason: str,
    *,
    via: str,
    sector_scope: str = "general",
) -> dict:
    return {
        "is_relevant": is_relevant,
        "relevance_reason": reason,
        "sector_scope": sector_scope,
        "audit_log": [
            AuditEvent(
                node="ISO_Relevance_Filter_Node",
                action="filter",
                detail=f"is_relevant={is_relevant}; {via}; {reason}",
            )
        ],
    }


def relevance_filter_node(state: PulseState) -> dict:
    """Drop university, ads, and AYM noise; keep industrial İSO items."""
    title = str(state.get("title") or "")
    new_text = str(state.get("new_text") or "")
    document_id = str(state.get("document_id") or "")
    source = str(state.get("source") or "")
    scope = audience_scope(title, new_text)

    if force_keep_departments(title, new_text):
        verdict, reason = classify_relevance(title, new_text, document_id, source=source)
        return _filter_payload(True, reason, via="taxonomy-keep", sector_scope=scope)
    verdict, reason = classify_relevance(title, new_text, document_id, source=source)
    if verdict == "drop":
        return _filter_payload(False, reason, via="taxonomy-drop", sector_scope=scope)
    return _filter_payload(True, reason, via="taxonomy-keep", sector_scope=scope)
