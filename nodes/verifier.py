from __future__ import annotations

from config.prompts import VERIFIER_SYSTEM
from mocks.llm import complete
from schemas.outputs import AuditEvent, VerificationResult
from schemas.state import PulseState


def verifier_node(state: PulseState) -> dict:
    """Verifier_Critic_Node: score grounding; flag needs_review without rewriting."""
    analyses = state.get("analyses") or {}
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
            f"old_text:\n{state.get('old_text') or '(none)'}\n\n"
            f"new_text:\n{state['new_text']}\n\n"
            f"diff:\n{state['diff']}\n\n"
            f"analyses:\n{analysis_block}\n"
        ),
        context={
            "document_id": state["document_id"],
            "title": state["title"],
            "new_text": state["new_text"],
            "analyses": analyses,
        },
    )
    return {
        "verification": result,
        "hallucination_score": result.hallucination_score,
        "needs_review": result.needs_review,
        "audit_log": [
            AuditEvent(
                node="Verifier_Critic_Node",
                action="verify",
                detail=(
                    f"passed={result.passed}; "
                    f"hallucination_score={result.hallucination_score}; "
                    f"needs_review={result.needs_review}"
                ),
            )
        ],
    }
