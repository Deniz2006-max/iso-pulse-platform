"""
Chatbot mesaj şemaları
"""
from pydantic import BaseModel
from typing import Optional


class ChatMessageIn(BaseModel):
    session_id: str
    employee_id: str
    message: str


class QuickAction(BaseModel):
    label: str
    value: str          # Bu değer otomatik mesaj olarak gönderilir


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    quick_actions: list[QuickAction] = []
    leave_created: bool = False
    leave_id: Optional[str] = None
    show_hr_button: bool = False   # "HR'a Mesaj At" butonu göster


class HRMessageIn(BaseModel):
    employee_id: str
    message: str


class HRMessageResponse(BaseModel):
    success: bool
    info: str
