"""
İzin Modülü API Endpoint'leri
Base prefix: /api/v1/hr/leave  (inpulse/router.py'de ayarlanır)
"""
import os
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.database import get_db
from db.models import EmployeeProfile, LeaveRequest, LeaveBalance, LeaveDocument
from inpulse.leave.schemas import (
    LeaveRequestCreate, LeaveRequestResponse,
    LeaveBalanceResponse, IzinTurleriResponse,
    ManagerDecision, EmployeeLeaveOverview,
)
from inpulse.leave.service import (
    create_leave_request, list_employee_requests,
    list_pending_for_manager, apply_manager_decision,
    cancel_leave_request, get_leave_balance, ensure_balance_row,
)
from inpulse.leave.calculator import IZIN_TURLERI, bakiye_hesapla

router = APIRouter()


# ── Yardımcı: çalışan getir ─────────────────────────────────────────────────
async def _get_employee(employee_id: str, db: AsyncSession) -> EmployeeProfile:
    result = await db.execute(
        select(EmployeeProfile).where(EmployeeProfile.id == employee_id)
    )
    emp = result.scalar_one_or_none()
    if not emp:
        raise HTTPException(status_code=404, detail="Çalışan bulunamadı")
    return emp


# ── 1. İzin türleri listesi ─────────────────────────────────────────────────
@router.get("/types", response_model=list[IzinTurleriResponse], summary="İzin türleri")
async def get_izin_turleri():
    """Sistemdeki tüm izin türlerini ve açıklamalarını döndürür."""
    return [
        IzinTurleriResponse(
            kod=kod,
            label=bilgi["label"],
            aciklama=bilgi["aciklama"],
            max_gun=bilgi.get("max_gun"),
            bakiyeden_dusuler=bilgi.get("bakiyeden_dusuler", False),
        )
        for kod, bilgi in IZIN_TURLERI.items()
    ]


# ── 2. Bakiye sorgulama ─────────────────────────────────────────────────────
@router.get(
    "/balance/{employee_id}",
    response_model=LeaveBalanceResponse,
    summary="İzin bakiyesi",
)
async def get_balance(
    employee_id: str,
    yil: int = Query(default=2026),
    db: AsyncSession = Depends(get_db),
):
    """Çalışanın yıllık izin bakiyesini döndürür."""
    employee = await _get_employee(employee_id, db)
    balance = await get_leave_balance(db, employee_id, yil)
    if not balance:
        # İlk bakiye satırını oluştur
        balance = await ensure_balance_row(db, employee, yil)

    return LeaveBalanceResponse(
        employee_id=balance.employee_id,
        yil=balance.yil,
        onceki_yildan=balance.onceki_yildan,
        yillik_hak=balance.yillik_hak,
        idari_eklenen=balance.idari_eklenen,
        kullanilan=balance.kullanilan,
        bakiye=bakiye_hesapla(
            balance.onceki_yildan, balance.yillik_hak,
            balance.idari_eklenen, balance.kullanilan
        ),
    )


# ── 3. İzin talebi oluşturma ────────────────────────────────────────────────
@router.post(
    "/request/{employee_id}",
    response_model=LeaveRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="İzin talebi oluştur",
)
async def create_request(
    employee_id: str,
    data: LeaveRequestCreate,
    db: AsyncSession = Depends(get_db),
):
    """Çalışan adına yeni izin talebi oluşturur."""
    try:
        talep = await create_leave_request(db, employee_id, data)
        return LeaveRequestResponse.model_validate(talep)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── 4. Çalışanın talepleri ──────────────────────────────────────────────────
@router.get(
    "/requests/{employee_id}",
    response_model=list[LeaveRequestResponse],
    summary="Çalışanın izin talepleri",
)
async def get_employee_requests(
    employee_id: str,
    yil: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Çalışanın tüm izin taleplerini listeler."""
    await _get_employee(employee_id, db)
    talepler = await list_employee_requests(db, employee_id, yil)
    return [LeaveRequestResponse.model_validate(t) for t in talepler]


# ── 5. Tek talep detayı ─────────────────────────────────────────────────────
@router.get(
    "/request/detail/{talep_id}",
    response_model=LeaveRequestResponse,
    summary="Talep detayı",
)
async def get_request_detail(
    talep_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(LeaveRequest).where(LeaveRequest.id == talep_id))
    talep = result.scalar_one_or_none()
    if not talep:
        raise HTTPException(status_code=404, detail="Talep bulunamadı")
    return LeaveRequestResponse.model_validate(talep)


# ── 6. Çalışan talebi iptal ─────────────────────────────────────────────────
@router.patch(
    "/request/{talep_id}/cancel",
    response_model=LeaveRequestResponse,
    summary="İzin talebini iptal et",
)
async def cancel_request(
    talep_id: str,
    employee_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        talep = await cancel_leave_request(db, talep_id, employee_id)
        return LeaveRequestResponse.model_validate(talep)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── 7. Yöneticinin bekleyen talepleri ───────────────────────────────────────
@router.get(
    "/manager/{yonetici_id}/pending",
    response_model=list[LeaveRequestResponse],
    summary="Bekleyen onay talepleri",
)
async def get_pending_requests(
    yonetici_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Yöneticinin onayını bekleyen tüm talepleri döndürür."""
    talepler = await list_pending_for_manager(db, yonetici_id)
    return [LeaveRequestResponse.model_validate(t) for t in talepler]


# ── 7b. Yöneticinin TÜM çalışan talepleri (geçmiş dahil) ───────────────────
@router.get(
    "/manager/{yonetici_id}/all",
    response_model=list[LeaveRequestResponse],
    summary="Yöneticiye bağlı tüm çalışanların talepleri",
)
async def get_all_manager_requests(
    yonetici_id: str,
    yil: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Yöneticinin ekibindeki tüm çalışanların izin taleplerini döndürür (tüm durumlar)."""
    from sqlalchemy import and_, extract
    conditions = [LeaveRequest.yonetici_id == yonetici_id]
    if yil:
        conditions.append(extract("year", LeaveRequest.cikis_tarihi) == yil)
    stmt = (
        select(LeaveRequest)
        .where(and_(*conditions))
        .order_by(LeaveRequest.olusturma.desc())
        .limit(200)
    )
    result = await db.execute(stmt)
    talepler = result.scalars().all()
    return [LeaveRequestResponse.model_validate(t) for t in talepler]


# ── 8. Yönetici kararı (onayla / reddet) ────────────────────────────────────
@router.post(
    "/manager/{yonetici_id}/decide/{talep_id}",
    response_model=LeaveRequestResponse,
    summary="İzin talebini onayla veya reddet",
)
async def manager_decide(
    yonetici_id: str,
    talep_id: str,
    karar: ManagerDecision,
    db: AsyncSession = Depends(get_db),
):
    try:
        talep = await apply_manager_decision(db, talep_id, yonetici_id, karar)
        return LeaveRequestResponse.model_validate(talep)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── 9. Çalışan özeti (bakiye + son talepler) ────────────────────────────────
@router.get(
    "/overview/{employee_id}",
    response_model=EmployeeLeaveOverview,
    summary="Çalışan izin özeti",
)
async def employee_overview(
    employee_id: str,
    yil: int = Query(default=2026),
    db: AsyncSession = Depends(get_db),
):
    employee = await _get_employee(employee_id, db)
    balance = await get_leave_balance(db, employee_id, yil)
    if not balance:
        balance = await ensure_balance_row(db, employee, yil)

    son_talepler = await list_employee_requests(db, employee_id, yil)

    return EmployeeLeaveOverview(
        employee_id=employee_id,
        ad_soyad=employee.ad_soyad,
        bakiye=LeaveBalanceResponse(
            employee_id=balance.employee_id,
            yil=balance.yil,
            onceki_yildan=balance.onceki_yildan,
            yillik_hak=balance.yillik_hak,
            idari_eklenen=balance.idari_eklenen,
            kullanilan=balance.kullanilan,
            bakiye=bakiye_hesapla(
                balance.onceki_yildan, balance.yillik_hak,
                balance.idari_eklenen, balance.kullanilan
            ),
        ),
        son_talepler=[LeaveRequestResponse.model_validate(t) for t in son_talepler[:10]],
    )


# ── 10. HR: tüm çalışanların talepleri ─────────────────────────────────────
@router.get(
    "/hr/all-requests",
    response_model=list[LeaveRequestResponse],
    summary="Tüm izin talepleri (HR)",
)
async def hr_all_requests(
    durum: Optional[str] = Query(default=None),
    yil: Optional[int] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    """HR yöneticileri için tüm çalışanların taleplerini görüntüler."""
    from sqlalchemy import extract
    conditions = []
    if durum:
        conditions.append(LeaveRequest.durum == durum)
    if yil:
        conditions.append(extract("year", LeaveRequest.cikis_tarihi) == yil)

    from sqlalchemy import and_
    stmt = (
        select(LeaveRequest)
        .where(and_(*conditions) if conditions else True)
        .order_by(LeaveRequest.olusturma.desc())
        .limit(200)
    )
    result = await db.execute(stmt)
    talepler = result.scalars().all()
    return [LeaveRequestResponse.model_validate(t) for t in talepler]


# ── 11. Belge yükleme (hastalık raporu vb.) ─────────────────────────────────
UPLOAD_DIR = "/app/uploads/leave_documents"
ALLOWED_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/jpg"}
MAX_SIZE_MB = 10


@router.post(
    "/document/{talep_id}/upload",
    status_code=status.HTTP_201_CREATED,
    summary="İzin belgesi yükle (rapor, doğum belgesi)",
)
async def upload_leave_document(
    talep_id: str,
    yukleyen_id: str = Query(..., description="Yükleyen çalışan/yönetici ID"),
    belge_turu: str = Query(default="hastalik_raporu", description="hastalik_raporu | dogum_belgesi | diger"),
    dosya: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    # Talep kontrolü
    result = await db.execute(select(LeaveRequest).where(LeaveRequest.id == talep_id))
    talep = result.scalar_one_or_none()
    if not talep:
        raise HTTPException(status_code=404, detail="İzin talebi bulunamadı")

    # Dosya türü kontrolü
    if dosya.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Yalnızca PDF, JPEG ve PNG dosyaları kabul edilir",
        )

    # Boyut kontrolü
    contents = await dosya.read()
    if len(contents) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"Dosya {MAX_SIZE_MB} MB'dan büyük olamaz")

    # Kaydet
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext = os.path.splitext(dosya.filename or "belge")[1] or ".pdf"
    dosya_adi_disk = f"{uuid.uuid4()}{ext}"
    dosya_yolu = os.path.join(UPLOAD_DIR, dosya_adi_disk)

    with open(dosya_yolu, "wb") as f:
        f.write(contents)

    doc = LeaveDocument(
        leave_request_id=talep_id,
        belge_turu=belge_turu,
        dosya_yolu=dosya_yolu,
        dosya_adi=dosya.filename or dosya_adi_disk,
        yukleyen_id=yukleyen_id,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    return {
        "id": doc.id,
        "dosya_adi": doc.dosya_adi,
        "belge_turu": doc.belge_turu,
        "yuklenme_tarihi": doc.yuklenme_tarihi,
    }


# ── 12. Belgeleri listele (yönetici / HR) ────────────────────────────────────
@router.get(
    "/document/{talep_id}",
    summary="İzin belgeleri listesi",
)
async def list_leave_documents(
    talep_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(LeaveDocument).where(LeaveDocument.leave_request_id == talep_id)
    )
    docs = result.scalars().all()
    return [
        {
            "id": d.id,
            "dosya_adi": d.dosya_adi,
            "belge_turu": d.belge_turu,
            "yukleyen_id": d.yukleyen_id,
            "yuklenme_tarihi": d.yuklenme_tarihi,
        }
        for d in docs
    ]
