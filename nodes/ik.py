from __future__ import annotations

from nodes.specialist import run_specialist
from schemas.state import PulseState

IK_OPERATIONAL_LENS = """
Operational lens (mandatory):
- Write only HR policy and payroll-process impacts.
- Cover: iş sözleşmesi, çalışma süresi / fazla mesai, izin (analık, babalık,
  yıllık), ücret standardı, SGK e-bildirge, bordro, özlük, vardiya, OHS
  attendance, sendika.
- Name concrete HR actions (update leave policy, recode bordro, file e-bildirge).
- Do not discuss tax bases, stopaj codes, muhasebe journals, or licensing.
"""


def ik_node(state: PulseState) -> dict:
    """IK_Node: HR / labor specialist wrapper."""
    return run_specialist(state, "ik", extra_instructions=IK_OPERATIONAL_LENS)
