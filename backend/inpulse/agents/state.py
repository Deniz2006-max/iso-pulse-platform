"""
İnpulse LangGraph durum tanımları
"""
from typing import TypedDict, Annotated, Literal
from langgraph.graph.message import add_messages


class IcKanalState(TypedDict):
    """İnpulse kanal için ortak durum nesnesi"""
    messages: Annotated[list, add_messages]
    employee_id: str
    intent: Literal["izin_al", "izin_takip", "bilgi", "diger"] | None
    izin_turu: str | None
    # İzin talebinin ara sonuçları
    leave_request_data: dict | None
    leave_balance: dict | None
    # Guardrail bayrağı
    is_out_of_scope: bool
    # Son cevap
    final_response: str | None
