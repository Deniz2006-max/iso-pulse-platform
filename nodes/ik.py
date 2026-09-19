from __future__ import annotations

from nodes.specialist import run_specialist
from schemas.state import PulseState


def ik_node(state: PulseState) -> dict:
    """IK_Node: HR / labor specialist wrapper."""
    return run_specialist(state, "ik")
