from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from nodes.delivery import delivery_node
from nodes.hukuk import hukuk_node
from nodes.ik import ik_node
from nodes.mali import mali_node
from nodes.relevance_filter import relevance_filter_node
from nodes.router import router_node
from nodes.verifier import verifier_node
from schemas.outputs import Department
from schemas.state import PulseState

_SPECIALIST_NODES: dict[Department, str] = {
    "ik": "ik",
    "hukuk": "hukuk",
    "mali": "mali",
}


def route_after_filter(state: PulseState) -> str:
    if state.get("is_relevant"):
        return "router"
    return END


def fanout_specialists(state: PulseState) -> list[Send] | str:
    sends = [
        Send(node_name, state)
        for department, node_name in _SPECIALIST_NODES.items()
        if department in (state.get("departments") or [])
    ]
    return sends if sends else END


def build_graph():
    builder = StateGraph(PulseState)
    builder.add_node("relevance_filter", relevance_filter_node)
    builder.add_node("router", router_node)
    builder.add_node("ik", ik_node)
    builder.add_node("hukuk", hukuk_node)
    builder.add_node("mali", mali_node)
    builder.add_node("verifier", verifier_node)
    builder.add_node("delivery", delivery_node)

    builder.add_edge(START, "relevance_filter")
    builder.add_conditional_edges(
        "relevance_filter",
        route_after_filter,
        {"router": "router", END: END},
    )
    builder.add_conditional_edges(
        "router",
        fanout_specialists,
        ["ik", "hukuk", "mali", END],
    )
    builder.add_edge("ik", "verifier")
    builder.add_edge("hukuk", "verifier")
    builder.add_edge("mali", "verifier")
    builder.add_edge("verifier", "delivery")
    builder.add_edge("delivery", END)
    return builder.compile()


graph = build_graph()
