from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from db.models import EmployeeProfile
from orientation.deps import get_current_employee, get_db
from orientation.errors import OrientationAPIError
from orientation.flow import (
    complete_video,
    get_questions,
    get_report,
    get_report_pdf,
    get_status,
    list_videos,
    submit_answers,
)
from orientation.schemas import (
    AnswersRequest,
    AnswersResponse,
    QuestionsResponse,
    ReportResponse,
    StatusResponse,
    VideoOut,
    WatchCompleteResponse,
)

router = APIRouter()


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(
            status_code=404,
            detail={"code": "STEP_NOT_FOUND", "message": str(exc)},
        )
    if isinstance(exc, OrientationAPIError):
        return HTTPException(status_code=exc.status_code, detail=exc.to_detail())
    raise exc


@router.get("/status", response_model=StatusResponse)
def orientation_status(
    employee: EmployeeProfile = Depends(get_current_employee),
    session: Session = Depends(get_db),
) -> StatusResponse:
    return get_status(employee.id, session)


@router.get("/videos", response_model=list[VideoOut])
def orientation_videos(
    employee: EmployeeProfile = Depends(get_current_employee),
    session: Session = Depends(get_db),
) -> list[VideoOut]:
    return list_videos(employee.id, session)


@router.post("/videos/{video_id}/complete", response_model=WatchCompleteResponse)
def complete_orientation_video(
    video_id: int,
    employee: EmployeeProfile = Depends(get_current_employee),
    session: Session = Depends(get_db),
) -> WatchCompleteResponse:
    try:
        return complete_video(employee.id, video_id, session)
    except (LookupError, OrientationAPIError) as exc:
        raise _http_error(exc) from exc


@router.get("/videos/{video_id}/questions", response_model=QuestionsResponse)
def orientation_questions(
    video_id: int,
    employee: EmployeeProfile = Depends(get_current_employee),
    session: Session = Depends(get_db),
) -> QuestionsResponse:
    try:
        return get_questions(employee.id, video_id, session)
    except (LookupError, OrientationAPIError) as exc:
        raise _http_error(exc) from exc


@router.post("/videos/{video_id}/answers", response_model=AnswersResponse)
def orientation_answers(
    video_id: int,
    payload: AnswersRequest,
    employee: EmployeeProfile = Depends(get_current_employee),
    session: Session = Depends(get_db),
) -> AnswersResponse:
    try:
        return submit_answers(employee.id, video_id, payload.answers, session)
    except (LookupError, OrientationAPIError) as exc:
        raise _http_error(exc) from exc


@router.get("/report", response_model=ReportResponse)
def orientation_report(
    employee: EmployeeProfile = Depends(get_current_employee),
    session: Session = Depends(get_db),
) -> ReportResponse:
    try:
        return get_report(employee.id, session)
    except (LookupError, OrientationAPIError) as exc:
        raise _http_error(exc) from exc


@router.get("/report/pdf")
def orientation_report_pdf(
    employee: EmployeeProfile = Depends(get_current_employee),
    session: Session = Depends(get_db),
) -> Response:
    try:
        pdf_bytes = get_report_pdf(employee, session)
    except (LookupError, OrientationAPIError) as exc:
        raise _http_error(exc) from exc
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="oryantasyon-raporu.pdf"',
        },
    )
