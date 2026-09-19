from __future__ import annotations

from config.prompts import ROUTER_SYSTEM
from mocks.llm import complete
from schemas.outputs import AuditEvent, RouteDecision
from schemas.state import PulseState


def router_node(state: PulseState) -> dict:
    """Router_Agent_Node: send a relevant change to IK, Hukuk, and/or Mali."""
    result = complete(
        RouteDecision,
        ROUTER_SYSTEM,
        (
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
    return {
        "departments": result.departments,
        "audit_log": [
            AuditEvent(
                node="Router_Agent_Node",
                action="route",
                detail=f"departments={','.join(result.departments)}; {result.reason}",
            )
        ],
    }
