from __future__ import annotations

from nodes.specialist import run_specialist
from schemas.state import PulseState


def hukuk_node(state: PulseState) -> dict:
    """Hukuk_Node: legal specialist wrapper."""
    return run_specialist(state, "hukuk")
