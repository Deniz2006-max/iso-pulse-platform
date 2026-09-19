from __future__ import annotations

from nodes.specialist import run_specialist
from schemas.state import PulseState


def mali_node(state: PulseState) -> dict:
    """Mali_Node: tax / finance specialist wrapper."""
    return run_specialist(state, "mali")
