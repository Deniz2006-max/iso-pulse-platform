"""
Görev Yönetimi API Endpoint'leri
Base prefix: /api/v1/hr/tasks  (inpulse/router.py'de ayarlanır)
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.database import get_db
from db.models import Task, EmployeeProfile
from inpulse.tasks.schemas import (
    TaskCreate, TaskUpdate, TaskReassign,
    TaskResponse, AuditLogResponse, LeaveConflictInfo,
)
from inpulse.tasks.service import (
    create_task, list_employee_tasks, list_manager_tasks,
    update_task_status, reassign_task, check_leave_conflicts,
    get_audit_log, update_task_fields,
)

router = APIRouter()


def _task_to_response(task: Task, calisan_adi: str = None, yonetici_adi: str = None) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        baslik=task.baslik,
        aciklama=task.aciklama,
        oncelik=task.oncelik,
        durum=task.durum,
        bitis_tarihi=task.bitis_tarihi,
        employee_id=task.employee_id,
        yonetici_id=task.yonetici_id,
        teslim_edildi_at=task.teslim_edildi_at,
        tamamlandi_at=task.tamamlandi_at,
        ret_notu=task.ret_notu,
        olusturma=task.olusturma,
        guncelleme=task.guncelleme,
        calisan_adi=calisan_adi,
        yonetici_adi=yonetici_adi,
    )


async def _enrich_tasks(db: AsyncSession, tasks: list[Task]) -> list[TaskResponse]:
    """Görevlere çalışan ve yönetici adı ekler."""
    emp_ids = {t.employee_id for t in tasks} | {t.yonetici_id for t in tasks}
    if not emp_ids:
        return [_task_to_response(t) for t in tasks]

    result = await db.execute(
        select(EmployeeProfile).where(EmployeeProfile.id.in_(emp_ids))
    )
    emp_map = {e.id: e.ad_soyad for e in result.scalars().all()}

    return [
        _task_to_response(
            t,
            calisan_adi=emp_map.get(t.employee_id),
            yonetici_adi=emp_map.get(t.yonetici_id),
        )
        for t in tasks
    ]


# ── 1. Görev oluştur (Yönetici) ─────────────────────────────────────────────
@router.post(
    "/manager/{yonetici_id}",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Görev oluştur",
)
async def create_task_endpoint(
    yonetici_id: str,
    data: TaskCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        task = await create_task(db, yonetici_id, data)
        return _task_to_response(task)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── 2. Çalışanın görevleri ───────────────────────────────────────────────────
@router.get(
    "/employee/{employee_id}",
    response_model=list[TaskResponse],
    summary="Çalışanın görevleri",
)
async def get_employee_tasks(
    employee_id: str,
    durum: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    tasks = await list_employee_tasks(db, employee_id, durum)
    return await _enrich_tasks(db, tasks)


# ── 3. Yöneticinin ekip görevleri ───────────────────────────────────────────
@router.get(
    "/manager/{yonetici_id}",
    response_model=list[TaskResponse],
    summary="Yöneticinin ekip görevleri",
)
async def get_manager_tasks(
    yonetici_id: str,
    durum: Optional[str] = Query(default=None),
    oncelik: Optional[str] = Query(default=None),
    employee_id: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    tasks = await list_manager_tasks(db, yonetici_id, durum, oncelik, employee_id)
    return await _enrich_tasks(db, tasks)


# ── 4. Görev detayı ─────────────────────────────────────────────────────────
@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Görev detayı",
)
async def get_task(task_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Görev bulunamadı")
    enriched = await _enrich_tasks(db, [task])
    return enriched[0]


# ── 5. Durum güncelle ────────────────────────────────────────────────────────
@router.patch(
    "/{task_id}/status",
    response_model=TaskResponse,
    summary="Görev durumunu güncelle",
)
async def change_task_status(
    task_id: str,
    yeni_durum: str = Query(..., description="Yeni durum: devam_ediyor | teslim_edildi | tamamlandi | atandi"),
    yapan_id: str = Query(...),
    ret_notu: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    try:
        task = await update_task_status(db, task_id, yeni_durum, yapan_id, ret_notu)
        enriched = await _enrich_tasks(db, [task])
        return enriched[0]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── 6. Görev devret ─────────────────────────────────────────────────────────
@router.post(
    "/{task_id}/reassign",
    response_model=TaskResponse,
    summary="Görevi devret",
)
async def reassign_task_endpoint(
    task_id: str,
    devir_eden_id: str = Query(...),
    data: TaskReassign = ...,
    db: AsyncSession = Depends(get_db),
):
    try:
        task = await reassign_task(db, task_id, devir_eden_id, data)
        enriched = await _enrich_tasks(db, [task])
        return enriched[0]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── 7. İzin-görev çakışma kontrolü ─────────────────────────────────────────
@router.get(
    "/conflicts/check",
    response_model=LeaveConflictInfo,
    summary="İzin görev çakışması kontrolü",
)
async def check_conflicts(
    employee_id: str = Query(...),
    leave_start: str = Query(..., description="YYYY-MM-DD"),
    leave_end: str = Query(..., description="YYYY-MM-DD"),
    izin_turu: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    from datetime import date as date_type
    try:
        start = date_type.fromisoformat(leave_start)
        end = date_type.fromisoformat(leave_end)
    except ValueError:
        raise HTTPException(status_code=400, detail="Geçersiz tarih formatı (YYYY-MM-DD)")

    return await check_leave_conflicts(db, employee_id, start, end, izin_turu)


# ── 8. Görev denetim kaydı ──────────────────────────────────────────────────
@router.get(
    "/{task_id}/audit",
    response_model=list[AuditLogResponse],
    summary="Görev denetim kaydı",
)
async def get_task_audit(task_id: str, db: AsyncSession = Depends(get_db)):
    logs = await get_audit_log(db, task_id)
    return [AuditLogResponse.model_validate(l) for l in logs]


# ── 9. Görev güncelle (yönetici) ─────────────────────────────────────────────
@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Görevi güncelle",
)
async def update_task_endpoint(
    task_id: str,
    yapan_id: str = Query(...),
    data: TaskUpdate = ...,
    db: AsyncSession = Depends(get_db),
):
    try:
        task = await update_task_fields(db, task_id, yapan_id, data)
        enriched = await _enrich_tasks(db, [task])
        return enriched[0]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
