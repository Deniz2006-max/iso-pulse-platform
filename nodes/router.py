from __future__ import annotations

from config.prompts import ROUTER_SYSTEM
from config.routing import SEND_CONFIDENCE_FLOOR, constrain_departments, scores_to_map
from mocks.llm import complete
from schemas.outputs import AuditEvent, RouteDecision
from schemas.state import PulseState


def router_node(state: PulseState) -> dict:
    """Router_Agent_Node: Send only high-confidence core-domain departments."""
    result = complete(
        RouteDecision,
        ROUTER_SYSTEM,
        (
            "Route ONLY for a direct core-domain change. "
            "Overtime/payroll without tax-base or statutory-deduction changes "
            "must be ik only; do not Send mali or hukuk.\n"
            "Exclude mali unless a monetary/tax threshold is in the text. "
            "Exclude ik if the text is purely corporate governance.\n"
            f"Do not include a department unless scores.confidence >= {SEND_CONFIDENCE_FLOOR}.\n\n"
            f"document_id: {state['document_id']}\n"
            f"source: {state['source']}\n"
            f"title: {state['title']}\n"
            f"new_text:\n{state['new_text']}\n"
            f"diff:\n{state['diff']}\n"
        ),
        context={
            "document_id": state["document_id"],
            "title": state["title"],
            "new_text": state["new_text"],
        },
    )
    source_blob = (
        f"{state['title']}\n{state.get('old_text') or ''}\n"
        f"{state['new_text']}\n{state['diff']}"
    )
    departments, department_scores = constrain_departments(
        result.departments,
        source_blob,
        scores_to_map(result.scores),
    )
    score_label = ",".join(
        f"{department}:{department_scores.get(department, 0):.2f}"
        for department in departments
    ) or "none"
    return {
        "departments": departments,
        "department_scores": department_scores,
        "audit_log": [
            AuditEvent(
                node="Router_Agent_Node",
                action="route",
                detail=(
                    f"departments={','.join(departments) or 'none'}; "
                    f"scores={score_label}; floor={SEND_CONFIDENCE_FLOOR}; "
                    f"{result.reason}"
                ),
            )
        ],
    }
