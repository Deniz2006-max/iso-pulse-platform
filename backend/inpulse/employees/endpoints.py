"""
Çalışan Profil API — İSO Pulse
GET  /api/v1/hr/employees          → Tüm aktif çalışanları listele
GET  /api/v1/hr/employees/{id}     → Tekil çalışan profili
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.database import get_db
from db.models import EmployeeProfile
from inpulse.employees.schemas import EmployeeListItem, EmployeeDetail

router = APIRouter()


@router.get(
    "",
    response_model=list[EmployeeListItem],
    summary="Tüm aktif çalışanları listele",
)
async def list_employees(db: AsyncSession = Depends(get_db)) -> list[EmployeeListItem]:
    result = await db.execute(
        select(EmployeeProfile)
        .where(EmployeeProfile.aktif == True)  # noqa
        .order_by(EmployeeProfile.ad_soyad)
    )
    return result.scalars().all()


@router.get(
    "/{employee_id}",
    response_model=EmployeeDetail,
    summary="Çalışan profili",
)
async def get_employee(employee_id: str, db: AsyncSession = Depends(get_db)) -> EmployeeDetail:
    result = await db.execute(
        select(EmployeeProfile).where(EmployeeProfile.id == employee_id)
    )
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Çalışan bulunamadı")
    return emp
