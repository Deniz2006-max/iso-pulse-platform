from __future__ import annotations

from config.prompts import VERIFIER_SYSTEM
from config.routing import analysis_has_domain_signal
from mocks.llm import complete
from schemas.outputs import AuditEvent, VerificationResult
from schemas.state import PulseState


def verifier_node(state: PulseState) -> dict:
    """Verifier_Critic_Node: score grounding; drop off-domain specialist output."""
    analyses = dict(state.get("analyses") or {})
    dropped: list[str] = []
    for department, item in list(analyses.items()):
        if not analysis_has_domain_signal(department, item):  # type: ignore[arg-type]
            dropped.append(department)
            analyses.pop(department)

    analysis_block = "\n\n".join(
        (
            f"[{department}]\n"
            f"summary: {item.summary}\n"
            f"obligation_change: {item.obligation_change}\n"
            f"citations: {', '.join(item.citations)}"
        )
        for department, item in analyses.items()
    ) or "(no analyses)"

    result = complete(
        VerificationResult,
        VERIFIER_SYSTEM,
        (
            f"document_id: {state['document_id']}\n"
            f"rag_mode: {state.get('rag_mode') or ''}\n"
            f"rag_confidence: {float(state.get('rag_confidence') or 0.0):.3f}\n"
            f"old_text:\n{state.get('old_text') or '(none)'}\n\n"
            f"new_text:\n{state['new_text']}\n\n"
            f"diff:\n{state['diff']}\n\n"
            f"kept_analyses:\n{analysis_block}\n"
            f"already_dropped_for_domain_mismatch: {dropped}\n"
            "If rag_mode is fallback, specialists used internal knowledge of "
            "new_text (no Chroma context). Do not treat missing RAG citations "
            "as hallucinations when claims are grounded in the new regulation.\n"
        ),
        context={
            "document_id": state["document_id"],
            "title": state["title"],
            "new_text": state["new_text"],
            "analyses": analyses,
            "dropped_departments": dropped,
        },
    )
    merged_dropped = list(dict.fromkeys([*dropped, *result.dropped_departments]))
    result = result.model_copy(update={"dropped_departments": merged_dropped})
    if dropped and not analyses:
        result = result.model_copy(update={"needs_review": True, "passed": False})

    departments = [
        department
        for department in (state.get("departments") or [])
        if department not in merged_dropped
    ]
    return {
        "verification": result,
        "hallucination_score": result.hallucination_score,
        "needs_review": result.needs_review,
        "dropped_departments": merged_dropped,
        "departments": departments,
        "audit_log": [
            AuditEvent(
                node="Verifier_Critic_Node",
                action="verify",
                detail=(
                    f"passed={result.passed}; "
                    f"hallucination_score={result.hallucination_score}; "
                    f"needs_review={result.needs_review}; "
                    f"dropped={','.join(merged_dropped) or 'none'}"
                ),
            )
        ],
    }
