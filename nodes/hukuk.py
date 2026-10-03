from __future__ import annotations

from nodes.specialist import run_specialist
from schemas.state import PulseState

HUKUK_OPERATIONAL_LENS = """
Operational lens (mandatory):
- Write only legal / compliance impacts.
- Cover: permits, licenses, contracts, liability, litigation, KVKK,
  environmental regime, corporate law.
- Name concrete legal actions (amend contract, file permit, update aydınlatma,
  evidence retention).
- Do not rewrite payroll calendars or tax journal entries.
"""


def hukuk_node(state: PulseState) -> dict:
    """Hukuk_Node: legal specialist wrapper."""
    return run_specialist(state, "hukuk", extra_instructions=HUKUK_OPERATIONAL_LENS)
