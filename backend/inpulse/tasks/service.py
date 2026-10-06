"""
Görev Yönetimi — Servis Katmanı
İş mantığı: oluşturma, durum geçişleri, devir, çakışma kontrolü
"""
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from db.models import Task, TaskAssignmentHistory, TaskAuditLog, Notification, EmployeeProfile
from inpulse.tasks.schemas import TaskCreate, TaskUpdate, TaskReassign, TaskConflict, LeaveConflictInfo

# Özel izin türleri → görev devri gerektirir (sadece uyarı değil)
OZEL_IZIN_TURLERI = {"olum", "dogum_kadin", "baba_dogum", "hastalik"}

# Geçerli durum geçişleri
GECERLI_GECISLER = {
    "atandi": {"devam_ediyor"},
    "devam_ediyor": {"teslim_edildi"},
    "teslim_edildi": {"onay_bekliyor"},       # Otomatik: teslimden sonra
    "onay_bekliyor": {"tamamlandi", "atandi"}, # Ret → atandi'ya geri döner
    "tamamlandi": set(),
}


async def _audit(
    db: AsyncSession,
    task_id: str,
    eylem: str,
    yapan_id: Optional[str],
    eski: Optional[str] = None,
    yeni: Optional[str] = None,
):
    """Değişmez denetim kaydı yaz."""
    log = TaskAuditLog(
        task_id=task_id,
        eylem=eylem,
        yapan_id=yapan_id,
        eski_deger=eski,
        yeni_deger=yeni,
    )
    db.add(log)


async def _notify(
    db: AsyncSession,
    user_id: str,
    tur: str,
    mesaj: str,
    task_id: Optional[str] = None,
    leave_id: Optional[str] = None,
):
    """Bildirim oluştur."""
    notif = Notification(
        user_id=user_id,
        tur=tur,
        ilgili_task_id=task_id,
        ilgili_leave_id=leave_id,
        mesaj=mesaj,
    )
    db.add(notif)


# ─── Görev oluşturma ────────────────────────────────────────────────────────
async def create_task(
    db: AsyncSession,
    yonetici_id: str,
    data: TaskCreate,
) -> Task:
    # Çalışan kontrolü
    emp_result = await db.execute(
        select(EmployeeProfile).where(EmployeeProfile.id == data.employee_id)
    )
    calisan = emp_result.scalar_one_or_none()
    if not calisan:
        raise ValueError("Çalışan bulunamadı")

    if data.bitis_tarihi < date.today():
        raise ValueError("Bitiş tarihi geçmiş olamaz")

    task = Task(
        baslik=data.baslik,
        aciklama=data.aciklama,
        oncelik=data.oncelik,
        bitis_tarihi=data.bitis_tarihi,
        employee_id=data.employee_id,
        yonetici_id=yonetici_id,
        durum="atandi",
    )
    db.add(task)
    await db.flush()  # id oluşsun

    # Denetim kaydı
    await _audit(db, task.id, "created", yonetici_id, yeni=f"{data.baslik} → {data.employee_id}")

    # Bildirim: çalışana
    await _notify(
        db, data.employee_id, "task_assigned",
        f"Size yeni bir görev atandı: {data.baslik} (Son tarih: {data.bitis_tarihi})",
        task_id=task.id,
    )

    await db.commit()
    await db.refresh(task)
    return task


# ─── Görev listeleme ────────────────────────────────────────────────────────
async def list_employee_tasks(
    db: AsyncSession,
    employee_id: str,
    durum: Optional[str] = None,
) -> list[Task]:
    conditions = [Task.employee_id == employee_id]
    if durum:
        conditions.append(Task.durum == durum)

    result = await db.execute(
        select(Task).where(and_(*conditions)).order_by(Task.bitis_tarihi.asc())
    )
    return list(result.scalars().all())


async def list_manager_tasks(
    db: AsyncSession,
    yonetici_id: str,
    durum: Optional[str] = None,
    oncelik: Optional[str] = None,
    employee_id: Optional[str] = None,
) -> list[Task]:
    conditions = [Task.yonetici_id == yonetici_id]
    if durum:
        conditions.append(Task.durum == durum)
    if oncelik:
        conditions.append(Task.oncelik == oncelik)
    if employee_id:
        conditions.append(Task.employee_id == employee_id)

    result = await db.execute(
        select(Task).where(and_(*conditions)).order_by(Task.bitis_tarihi.asc())
    )
    return list(result.scalars().all())


# ─── Durum güncelleme ────────────────────────────────────────────────────────
async def update_task_status(
    db: AsyncSession,
    task_id: str,
    yeni_durum: str,
    yapan_id: str,
    ret_notu: Optional[str] = None,
) -> Task:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise ValueError("Görev bulunamadı")

    gecerli_gecisler = GECERLI_GECISLER.get(task.durum, set())
    if yeni_durum not in gecerli_gecisler:
        raise ValueError(f"'{task.durum}' durumundan '{yeni_durum}' durumuna geçiş geçersiz")

    eski_durum = task.durum
    task.durum = yeni_durum

    now = datetime.now(timezone.utc)
    if yeni_durum == "teslim_edildi":
        task.teslim_edildi_at = now
        task.durum = "onay_bekliyor"  # Otomatik onay beklemeye geçer
        yeni_durum = "onay_bekliyor"
    elif yeni_durum == "tamamlandi":
        task.tamamlandi_at = now
    elif yeni_durum == "atandi" and ret_notu:
        task.ret_notu = ret_notu

    await _audit(db, task_id, "status_changed", yapan_id, eski=eski_durum, yeni=yeni_durum)

    # Bildirimler
    if yeni_durum == "onay_bekliyor":
        await _notify(
            db, task.yonetici_id, "task_submitted",
            f"{task.baslik} görevi teslim edildi, onayınızı bekliyor.",
            task_id=task_id,
        )
    elif yeni_durum == "tamamlandi":
        await _notify(
            db, task.employee_id, "task_approved",
            f"{task.baslik} göreviniz onaylandı.",
            task_id=task_id,
        )
    elif yeni_durum == "atandi" and ret_notu:
        await _notify(
            db, task.employee_id, "task_rejected",
            f"{task.baslik} görevi reddedildi: {ret_notu}",
            task_id=task_id,
        )

    await db.commit()
    await db.refresh(task)
    return task


# ─── Görev devir ─────────────────────────────────────────────────────────────
async def reassign_task(
    db: AsyncSession,
    task_id: str,
    devir_eden_id: str,
    data: TaskReassign,
) -> Task:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise ValueError("Görev bulunamadı")

    # Yeni çalışan kontrolü
    emp_result = await db.execute(
        select(EmployeeProfile).where(EmployeeProfile.id == data.yeni_employee_id)
    )
    if not emp_result.scalar_one_or_none():
        raise ValueError("Hedef çalışan bulunamadı")

    onceki_id = task.employee_id
    task.employee_id = data.yeni_employee_id
    task.durum = "atandi"

    # Atama geçmişi
    gecmis = TaskAssignmentHistory(
        task_id=task_id,
        onceki_employee_id=onceki_id,
        yeni_employee_id=data.yeni_employee_id,
        devir_eden_id=devir_eden_id,
        sebep=data.sebep,
    )
    db.add(gecmis)

    await _audit(
        db, task_id, "reassigned", devir_eden_id,
        eski=onceki_id, yeni=data.yeni_employee_id,
    )

    # Bildirimler
    await _notify(
        db, data.yeni_employee_id, "task_reassigned",
        f"Size bir görev devredildi: {task.baslik} (Son tarih: {task.bitis_tarihi})",
        task_id=task_id,
    )

    await db.commit()
    await db.refresh(task)
    return task


# ─── İzin-görev çakışma kontrolü ────────────────────────────────────────────
async def check_leave_conflicts(
    db: AsyncSession,
    employee_id: str,
    leave_start: date,
    leave_end: date,
    izin_turu: str,
) -> LeaveConflictInfo:
    """
    İzin tarih aralığında çalışanın bitmemiş görevlerini kontrol eder.
    Tamamlanan görevler hariç.
    """
    tamamlandi_durumlar = {"tamamlandi"}
    stmt = select(Task).where(
        and_(
            Task.employee_id == employee_id,
            Task.bitis_tarihi >= leave_start,
            Task.bitis_tarihi <= leave_end,
            Task.durum.notin_(tamamlandi_durumlar),
        )
    ).order_by(Task.bitis_tarihi.asc())

    result = await db.execute(stmt)
    cakisan = list(result.scalars().all())

    return LeaveConflictInfo(
        employee_id=employee_id,
        leave_start=leave_start,
        leave_end=leave_end,
        cakisan_gorevler=[
            TaskConflict(
                task_id=t.id,
                baslik=t.baslik,
                bitis_tarihi=t.bitis_tarihi,
                oncelik=t.oncelik,
            )
            for t in cakisan
        ],
        ozel_izin=izin_turu in OZEL_IZIN_TURLERI,
    )


# ─── Denetim kaydı listeleme ─────────────────────────────────────────────────
async def get_audit_log(db: AsyncSession, task_id: str) -> list[TaskAuditLog]:
    result = await db.execute(
        select(TaskAuditLog)
        .where(TaskAuditLog.task_id == task_id)
        .order_by(TaskAuditLog.olusturma.asc())
    )
    return list(result.scalars().all())


# ─── Görev güncelleme (yönetici) ─────────────────────────────────────────────
async def update_task_fields(
    db: AsyncSession,
    task_id: str,
    yapan_id: str,
    data: TaskUpdate,
) -> Task:
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise ValueError("Görev bulunamadı")

    changes = []
    if data.baslik is not None:
        changes.append(f"baslik: {task.baslik} → {data.baslik}")
        task.baslik = data.baslik
    if data.aciklama is not None:
        task.aciklama = data.aciklama
    if data.oncelik is not None:
        changes.append(f"oncelik: {task.oncelik} → {data.oncelik}")
        task.oncelik = data.oncelik
    if data.bitis_tarihi is not None:
        changes.append(f"bitis: {task.bitis_tarihi} → {data.bitis_tarihi}")
        task.bitis_tarihi = data.bitis_tarihi

    if changes:
        await _audit(db, task_id, "updated", yapan_id, yeni="; ".join(changes))

    await db.commit()
    await db.refresh(task)
    return task
