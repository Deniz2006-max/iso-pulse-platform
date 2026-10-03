from __future__ import annotations

from nodes.specialist import run_specialist
from schemas.state import PulseState

MALI_OPERATIONAL_LENS = """
Operational lens (mandatory):
- Write only accounting and tax impacts.
- Cover: tax base, statutory deductions, KDV / stopaj / tevkifat / damga,
  teşvik, fatura / e-fatura, muhasebe, prim işveren hissesi, declaration dates.
- Name concrete finance actions (change rate/code, rebook, file muhtasar).
- Do not write HR leave policy, shift plans, or permit-renewal playbooks.
"""


def mali_node(state: PulseState) -> dict:
    """Mali_Node: tax / finance specialist wrapper."""
    return run_specialist(state, "mali", extra_instructions=MALI_OPERATIONAL_LENS)
