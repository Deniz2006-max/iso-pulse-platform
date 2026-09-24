from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from db.models import EmployeeProfile
from db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_current_employee(
    session: Session = Depends(get_db),
    x_employee_id: int | None = Header(default=None, alias="X-Employee-Id"),
) -> EmployeeProfile:
    if x_employee_id is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "X-Employee-Id header required"},
        )
    employee = session.get(EmployeeProfile, x_employee_id)
    if employee is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "EMPLOYEE_NOT_FOUND", "message": "Employee profile not found"},
        )
    return employee
