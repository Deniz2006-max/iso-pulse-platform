from __future__ import annotations

from config.prompts import ROUTER_SYSTEM
from config.routing import constrain_departments
from mocks.llm import complete
from schemas.outputs import AuditEvent, RouteDecision
from schemas.state import PulseState


def router_node(state: PulseState) -> dict:
    """Router_Agent_Node: Send only to departments whose core domain changed."""
    result = complete(
        RouteDecision,
        ROUTER_SYSTEM,
        (
            "Route ONLY for a direct core-domain change. "
            "Overtime/payroll without tax-base or statutory-deduction changes "
            "must be ik only; do not Send mali or hukuk.\n\n"
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
    departments = constrain_departments(result.departments, source_blob)
    return {
        "departments": departments,
        "audit_log": [
            AuditEvent(
                node="Router_Agent_Node",
                action="route",
                detail=(
                    f"departments={','.join(departments)}; {result.reason}"
                ),
            )
        ],
    }
