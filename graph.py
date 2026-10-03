"""ISO-PULSE LangGraph: Filter → Retriever → Router → Specialists → Verifier.

Decision path:
- `relevance_filter` keeps tax, finance, HR/personnel (including sözleşmeli
  personel and working-condition esasları), SGK, İSG, environment, and trade.
  It drops only UN/diplomatic freezes, spatial kroki/coordinate acts, and
  person-specific appointment titles. Labor keep-signals beat body "atama"
  words so personnel regulations are not false-negatived.
- Keep-class signals win over soft noise (e.g. an ÖTV tebliğ that mentions
  ihale still passes). A Teknokent *incentive* is kept; a Teknokent *kroki*
  is dropped.
- Relevant items always fan out to at least one specialist (`ik` / `mali` /
  `hukuk`). Retriever injects `old_text` only when cosine ≥ 0.45 and a
  legal connection exists. If none exists, specialists still analyze the new
  text (Özet & Değişiklik + Birim Aksiyonu) and include the no-match notice.
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from config.relevance import implied_departments
from config.routing import SEND_CONFIDENCE_FLOOR
from nodes.delivery import delivery_node
from nodes.hukuk import hukuk_node
from nodes.ik import ik_node
from nodes.mali import mali_node
from nodes.relevance_filter import relevance_filter_node
from nodes.retriever import retriever_node
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
    """Drop filtered noise before Retriever / Chroma / specialists run."""
    if state.get("is_relevant"):
        return "retriever"
    return END


def fanout_specialists(state: PulseState) -> list[Send] | str:
    scores = state.get("department_scores") or {}
    routed = state.get("departments") or []
    sends = []
    for department, node_name in _SPECIALIST_NODES.items():
        if department not in routed:
            continue
        confidence = float(scores.get(department, 0.0))
        if confidence < SEND_CONFIDENCE_FLOOR:
            continue
        sends.append(Send(node_name, state))
    if sends:
        return sends
    if not state.get("is_relevant"):
        return END
    # Kept item with no scored Send: still reach a specialist (avoid FN).
    implied = implied_departments(
        str(state.get("title") or ""),
        str(state.get("new_text") or ""),
    )
    for department in implied:
        node_name = _SPECIALIST_NODES.get(department)  # type: ignore[arg-type]
        if node_name:
            sends.append(Send(node_name, state))
    if not sends:
        sends.append(Send("hukuk", state))
    return sends


def build_graph():
    builder = StateGraph(PulseState)
    builder.add_node("relevance_filter", relevance_filter_node)
    builder.add_node("retriever", retriever_node)
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
        {"retriever": "retriever", END: END},
    )
    builder.add_edge("retriever", "router")
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
