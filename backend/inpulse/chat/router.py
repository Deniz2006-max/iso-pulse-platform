"""
Chatbot API endpoint'leri
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.database import get_db
from db.models import EmployeeProfile
from inpulse.chat.schemas import ChatMessageIn, ChatResponse, HRMessageIn, HRMessageResponse
from inpulse.chat.engine import process_message

router = APIRouter(tags=["chat"])


@router.post("/message", response_model=ChatResponse)
async def chat_message(
    body: ChatMessageIn,
    db: AsyncSession = Depends(get_db),
):
    """Chatbot mesajını işle ve yanıt döndür."""
    response = await process_message(
        session_id=body.session_id,
        employee_id=body.employee_id,
        message=body.message,
        db=db,
    )
    # Chatbot izin talebi oluşturduysa (engine.py: db.flush) commit et
    await db.commit()
    response.session_id = body.session_id
    return response


@router.post("/hr-message", response_model=HRMessageResponse)
async def send_hr_message(
    body: HRMessageIn,
    db: AsyncSession = Depends(get_db),
):
    """Çalışanın İK'ya doğrudan mesaj göndermesini sağlar."""
    # Çalışan adını al
    stmt = select(EmployeeProfile).where(EmployeeProfile.id == body.employee_id)
    result = await db.execute(stmt)
    employee = result.scalar_one_or_none()

    if not employee:
        return HRMessageResponse(success=False, info="Çalışan bulunamadı.")

    # İK e-postasını bul
    stmt_hr = select(EmployeeProfile).where(EmployeeProfile.is_hr == True)
    res_hr = await db.execute(stmt_hr)
    hr_employees = res_hr.scalars().all()

    # Gerçek projede e-posta gönderilir; demo'da sadece loglama
    print(
        f"[Chat → İK] {employee.ad_soyad} → İK:\n{body.message}\n"
        f"İK alıcılar: {[h.email for h in hr_employees]}"
    )

    return HRMessageResponse(
        success=True,
        info=(
            f"Mesajınız İK ekibine iletildi. "
            f"En kısa sürede {employee.ad_soyad.split()[0]} Hanım/Bey ile iletişime geçilecek."
        ),
    )
