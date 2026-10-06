from __future__ import annotations

import logging

from config.executive_copy import (
    KAMU_NO_PRIVATE_ACTION,
    NO_ACTION_ADMINISTRATIVE,
    coerce_executive_summary,
    list_allowed_date_tokens,
)
from config.prompts import DELIVERY_SYSTEM
from config.relevance import (
    audience_scope,
    implied_departments,
    is_administrative_out_of_scope,
    is_financial_corporate_keep,
    specialized_subsector_label,
)
from mocks.llm import complete
from schemas.outputs import AuditEvent, DeliveryPayload
from schemas.state import PulseState

LOGGER = logging.getLogger("iso_pulse.delivery")


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
    scope = str(state.get("sector_scope") or "") or audience_scope(
        str(state.get("title") or ""), str(state.get("new_text") or "")
    )
    dates = list_allowed_date_tokens(
        str(state.get("title") or ""), str(state.get("new_text") or "")
    )
    date_lock = (
        "DATE LOCK — use only these date/year tokens from new_text: "
        + (", ".join(dates) if dates else "(none; omit calendar dates)")
        + ". Do not cite RAG or prior-year dates missing from this list."
    )
    if is_administrative_out_of_scope(
        str(state.get("title") or ""), str(state.get("new_text") or "")
    ):
        scope_lock = (
            "ADMINISTRATIVE / OUT OF SCOPE. Do not write factory HR actions. "
            "output EXACTLY:\n"
            "Sorumlu Departman İçin Aksiyon Maddeleri:\n"
            f"1. {NO_ACTION_ADMINISTRATIVE}"
        )
    elif is_financial_corporate_keep(
        str(state.get("title") or ""), str(state.get("new_text") or "")
    ):
        scope_lock = (
            "AUDIENCE = industrial MASAK/AML/tax/customs/TTK compliance. "
            "Do NOT output the kamu no-action sentence. "
            "Write real Maliye/Finans and Hukuk steps for manufacturers."
        )
    elif scope == "kamu":
        scope_lock = (
            "AUDIENCE = Düşük / Kamu Kurumları Kapsamı. urgency MUST be low. "
            "Do NOT present an operational or financial burden for private "
            "factory owners. First action item MUST be: "
            f"{KAMU_NO_PRIVATE_ACTION}"
        )
    elif scope == "specialized":
        sub = specialized_subsector_label(
            str(state.get("title") or ""), str(state.get("new_text") or "")
        )
        scope_lock = (
            f"SECTOR SCOPE = Düşük / Özel Sektör Kapsamı ({sub}). "
            "urgency MUST be low. Name this sub-sector in 🏭. "
            "Do not issue general HR/Finance actions for all manufacturers."
        )
    else:
        scope_lock = ""
    try:
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
                f"rag_mode: {state.get('rag_mode') or ''}\n"
                f"rag_confidence: {state.get('rag_confidence') or 0.0}\n"
                f"rag_status: {state.get('rag_status') or ''}\n"
                f"{date_lock}\n"
                f"{scope_lock}\n"
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
                "rag_mode": state.get("rag_mode"),
                "rag_confidence": state.get("rag_confidence") or 0.0,
                "rag_status": state.get("rag_status") or "",
            },
        )
    except Exception:
        LOGGER.exception("Delivery LLM failed; synthesizing card from specialist analyses")
        payload = _payload_from_specialists(state, analyses, departments)
    updates = {
        "rag_mode": state.get("rag_mode"),
        "rag_confidence": float(state.get("rag_confidence") or 0.0),
        "rag_status": str(state.get("rag_status") or ""),
    }
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

    summary = coerce_executive_summary(
        payload.summary,
        str(state.get("title") or ""),
        str(state.get("new_text") or ""),
        departments[0] if departments else "hukuk",
    )
    payload = payload.model_copy(update={"summary": summary})
    if scope in {"kamu", "specialized"} and payload.urgency != "low":
        payload = payload.model_copy(update={"urgency": "low"})
    if not payload.departments:
        payload = payload.model_copy(
            update={
                "departments": departments
                or implied_departments(
                    str(state.get("title") or ""),
                    str(state.get("new_text") or ""),
                    str(state.get("document_id") or ""),
                )
            }
        )

    return {
        "delivery": payload,
        "urgency": payload.urgency,
        "sector_scope": scope if scope in {"kamu", "specialized"} else "general",
        "needs_review": payload.needs_review,
        "hallucination_score": payload.hallucination_score,
        "audit_log": [
            AuditEvent(
                node="Delivery_Agent_Node",
                action="deliver",
                detail=(
                    f"urgency={payload.urgency}; "
                    f"needs_review={payload.needs_review}; "
                    f"rag_mode={payload.rag_mode or 'n/a'}"
                ),
            )
        ],
    }


def _payload_from_specialists(
    state: PulseState,
    analyses: dict,
    departments: list,
) -> DeliveryPayload:
    first = next(iter(analyses.values()), None)
    summary = coerce_executive_summary(
        getattr(first, "summary", "") if first is not None else "",
        str(state.get("title") or ""),
        str(state.get("new_text") or ""),
        departments[0] if departments else "hukuk",
    )
    routed = departments or implied_departments(
        str(state.get("title") or ""),
        str(state.get("new_text") or ""),
        str(state.get("document_id") or ""),
    )
    scope = str(state.get("sector_scope") or "") or audience_scope(
        str(state.get("title") or ""), str(state.get("new_text") or "")
    )
    return DeliveryPayload(
        document_id=str(state.get("document_id") or ""),
        source=str(state.get("source") or "resmi_gazete"),
        title=str(state.get("title") or ""),
        summary=summary,
        urgency="low" if scope in {"kamu", "specialized"} else "medium",
        departments=routed or ["hukuk"],
        needs_review=True,
        hallucination_score=float(state.get("hallucination_score") or 0.0),
        analyses=analyses,
        rag_mode=state.get("rag_mode"),
        rag_confidence=float(state.get("rag_confidence") or 0.0),
        rag_status=str(state.get("rag_status") or ""),
    )
