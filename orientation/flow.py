from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from config.prompts import ORIENTATION_REPORT_SYSTEM
from db.models import (
    EmployeeProfile,
    OrientationAnswer,
    OrientationQuestion,
    OrientationResult,
    OrientationVideo,
    OrientationWatchEvent,
)
from mocks.llm import complete
from orientation.errors import (
    InvalidAnswersError,
    QuizNotReadyError,
    ReportNotReadyError,
    StepLockedError,
)
from orientation.pdf import render_report_pdf, report_from_result
from orientation.schemas import (
    AnswerIn,
    AnswerResult,
    AnswersResponse,
    QuestionPublic,
    QuestionsResponse,
    ReportResponse,
    StatusResponse,
    VideoOut,
    WatchCompleteResponse,
)
from schemas.outputs import OrientationReport
from orientation.service import (
    all_questions_answered,
    can_unlock_step,
    marked_complete,
    quiz_available,
)

Step = OrientationVideo | int


def _as_video(session: Session, step: Step) -> OrientationVideo:
    if isinstance(step, OrientationVideo):
        return step
    video = session.get(OrientationVideo, step)
    if video is None:
        raise LookupError(f"orientation step {step} not found")
    return video


def list_ordered_videos(session: Session) -> list[OrientationVideo]:
    return list(
        session.scalars(select(OrientationVideo).order_by(OrientationVideo.sort_order))
    )


def next_required_step(step: Step, session: Session) -> OrientationVideo | None:
    video = _as_video(session, step)
    return session.scalar(
        select(OrientationVideo)
        .where(
            OrientationVideo.is_required.is_(True),
            OrientationVideo.sort_order > video.sort_order,
        )
        .order_by(OrientationVideo.sort_order.asc())
        .limit(1)
    )


def list_required_videos(session: Session) -> list[OrientationVideo]:
    return list(
        session.scalars(
            select(OrientationVideo)
            .where(OrientationVideo.is_required.is_(True))
            .order_by(OrientationVideo.sort_order)
        )
    )


def orientation_is_complete(employee_id: int, session: Session) -> bool:
    required = list_required_videos(session)
    if not required:
        return False
    return all(
        marked_complete(employee_id, video, session)
        and all_questions_answered(employee_id, video, session)
        for video in required
    )


def _report_ready(employee_id: int, session: Session) -> bool:
    result = session.scalar(
        select(OrientationResult).where(OrientationResult.employee_id == employee_id)
    )
    return bool(result and result.report_summary and result.completed_at)


def require_unlocked(employee_id: int, step: Step, session: Session) -> OrientationVideo:
    video = _as_video(session, step)
    if not can_unlock_step(employee_id, video, session):
        raise StepLockedError(video.id)
    return video


def require_quiz(employee_id: int, step: Step, session: Session) -> OrientationVideo:
    video = require_unlocked(employee_id, step, session)
    if not marked_complete(employee_id, video, session):
        raise QuizNotReadyError(video.id)
    return video


def get_status(employee_id: int, session: Session) -> StatusResponse:
    videos = list_ordered_videos(session)
    locked_step_ids = [
        video.id for video in videos if not can_unlock_step(employee_id, video, session)
    ]
    current_step_id: int | None = None
    quiz_pending = False
    for video in videos:
        if not can_unlock_step(employee_id, video, session):
            continue
        quiz_done = all_questions_answered(employee_id, video, session)
        completed = marked_complete(employee_id, video, session)
        if completed and quiz_done:
            continue
        current_step_id = video.id
        quiz_pending = completed and not quiz_done
        break
    return StatusResponse(
        current_step_id=current_step_id,
        locked_step_ids=locked_step_ids,
        quiz_pending=quiz_pending,
        completed=orientation_is_complete(employee_id, session),
        report_ready=_report_ready(employee_id, session),
    )


def list_videos(employee_id: int, session: Session) -> list[VideoOut]:
    videos = list_ordered_videos(session)
    return [
        VideoOut(
            id=video.id,
            title=video.title,
            description=video.description,
            source_url=video.source_url,
            duration_seconds=video.duration_seconds,
            sort_order=video.sort_order,
            is_required=video.is_required,
            unlocked=can_unlock_step(employee_id, video, session),
            completed=marked_complete(employee_id, video, session),
            quiz_done=all_questions_answered(employee_id, video, session),
        )
        for video in videos
    ]


def complete_video(employee_id: int, video_id: int, session: Session) -> WatchCompleteResponse:
    video = require_unlocked(employee_id, video_id, session)
    existing = session.scalar(
        select(OrientationWatchEvent).where(
            OrientationWatchEvent.employee_id == employee_id,
            OrientationWatchEvent.video_id == video.id,
        )
    )
    if existing is None:
        existing = OrientationWatchEvent(
            employee_id=employee_id,
            video_id=video.id,
            completed_at=datetime.now(timezone.utc),
        )
        session.add(existing)
        session.flush()
    return WatchCompleteResponse(
        video_id=video.id,
        completed_at=existing.completed_at,
        quiz_available=quiz_available(employee_id, video, session),
    )


def get_questions(employee_id: int, video_id: int, session: Session) -> QuestionsResponse:
    video = require_quiz(employee_id, video_id, session)
    questions = session.scalars(
        select(OrientationQuestion)
        .where(OrientationQuestion.video_id == video.id)
        .order_by(OrientationQuestion.sort_order)
    )
    return QuestionsResponse(
        video_id=video.id,
        questions=[
            QuestionPublic(
                id=question.id,
                prompt=question.prompt,
                choices=list(question.choices),
                sort_order=question.sort_order,
            )
            for question in questions
        ],
    )


def _load_video_with_questions(session: Session, video_id: int) -> OrientationVideo:
    video = session.scalar(
        select(OrientationVideo)
        .options(selectinload(OrientationVideo.questions))
        .where(OrientationVideo.id == video_id)
    )
    if video is None:
        raise LookupError(f"orientation step {video_id} not found")
    return video


def _upsert_answer(
    session: Session,
    *,
    employee_id: int,
    question: OrientationQuestion,
    selected_index: int,
) -> OrientationAnswer:
    if selected_index >= len(question.choices):
        raise InvalidAnswersError(
            f"selected_index {selected_index} is out of range for question {question.id}."
        )
    is_correct = selected_index == question.correct_index
    now = datetime.now(timezone.utc)
    existing = session.scalar(
        select(OrientationAnswer).where(
            OrientationAnswer.employee_id == employee_id,
            OrientationAnswer.question_id == question.id,
        )
    )
    if existing is None:
        existing = OrientationAnswer(
            employee_id=employee_id,
            question_id=question.id,
            selected_index=selected_index,
            is_correct=is_correct,
            answered_at=now,
        )
        session.add(existing)
    else:
        existing.selected_index = selected_index
        existing.is_correct = is_correct
        existing.answered_at = now
    session.flush()
    return existing


def compute_scores_snapshot(employee_id: int, session: Session) -> dict:
    videos = list_ordered_videos(session)
    by_module: list[dict] = []
    total_questions = 0
    total_correct = 0
    for video in videos:
        questions = list(
            session.scalars(
                select(OrientationQuestion).where(OrientationQuestion.video_id == video.id)
            )
        )
        if not questions:
            by_module.append(
                {"video_id": video.id, "title": video.title, "correct": 0, "total": 0}
            )
            continue
        question_ids = [question.id for question in questions]
        answers = list(
            session.scalars(
                select(OrientationAnswer).where(
                    OrientationAnswer.employee_id == employee_id,
                    OrientationAnswer.question_id.in_(question_ids),
                )
            )
        )
        correct = sum(1 for answer in answers if answer.is_correct)
        total_questions += len(questions)
        total_correct += correct
        by_module.append(
            {
                "video_id": video.id,
                "title": video.title,
                "correct": correct,
                "total": len(questions),
            }
        )
    return {
        "total_questions": total_questions,
        "correct": total_correct,
        "incorrect": total_questions - total_correct,
        "by_module": by_module,
    }


def _missed_question_prompts(employee_id: int, session: Session) -> list[str]:
    return list(
        session.scalars(
            select(OrientationQuestion.prompt)
            .join(
                OrientationAnswer,
                OrientationAnswer.question_id == OrientationQuestion.id,
            )
            .where(
                OrientationAnswer.employee_id == employee_id,
                OrientationAnswer.is_correct.is_(False),
            )
            .order_by(OrientationQuestion.id)
        )
    )


def _build_orientation_report(employee_id: int, scores: dict, session: Session) -> OrientationReport:
    missed = _missed_question_prompts(employee_id, session)
    return complete(
        OrientationReport,
        ORIENTATION_REPORT_SYSTEM,
        (
            f"Doğru: {scores.get('correct', 0)}/{scores.get('total_questions', 0)}. "
            f"Yanlış sorular: {missed or 'yok'}."
        ),
        context={
            "correct": scores.get("correct", 0),
            "incorrect": scores.get("incorrect", 0),
            "total_questions": scores.get("total_questions", 0),
            "missed_prompts": missed,
            "by_module": scores.get("by_module") or [],
        },
    )


def _persist_result_if_finished(employee_id: int, session: Session) -> None:
    if not orientation_is_complete(employee_id, session):
        return
    scores = compute_scores_snapshot(employee_id, session)
    report = _build_orientation_report(employee_id, scores, session)
    payload = {**scores, "report": report.model_dump()}
    now = datetime.now(timezone.utc)
    result = session.scalar(
        select(OrientationResult).where(OrientationResult.employee_id == employee_id)
    )
    if result is None:
        session.add(
            OrientationResult(
                employee_id=employee_id,
                scores_json=payload,
                report_summary=report.summary,
                completed_at=now,
            )
        )
    else:
        result.scores_json = payload
        result.report_summary = report.summary
        if result.completed_at is None:
            result.completed_at = now
    session.flush()


def _load_completed_result(employee_id: int, session: Session) -> OrientationResult:
    if not orientation_is_complete(employee_id, session):
        raise ReportNotReadyError()
    result = session.scalar(
        select(OrientationResult).where(OrientationResult.employee_id == employee_id)
    )
    if result is None or result.completed_at is None or not result.report_summary:
        raise ReportNotReadyError()
    return result


def get_report(employee_id: int, session: Session) -> ReportResponse:
    result = _load_completed_result(employee_id, session)
    report = report_from_result(result)
    scores = dict(result.scores_json or {})
    scores.pop("report", None)
    return ReportResponse(
        summary=report.summary,
        strengths=report.strengths,
        gaps=report.gaps,
        recommendation=report.recommendation,
        scores=scores,
        completed_at=result.completed_at,
        report_ready=True,
    )


def get_report_pdf(employee: EmployeeProfile, session: Session) -> bytes:
    result = _load_completed_result(employee.id, session)
    return render_report_pdf(employee, result)


def submit_answers(
    employee_id: int,
    video_id: int,
    answers: list[AnswerIn],
    session: Session,
) -> AnswersResponse:
    video = require_quiz(employee_id, video_id, session)
    video = _load_video_with_questions(session, video.id)
    questions = {question.id: question for question in video.questions}
    payload_ids = [item.question_id for item in answers]
    if len(payload_ids) != len(set(payload_ids)):
        raise InvalidAnswersError("Each question can be answered only once in this request.")
    if set(payload_ids) != set(questions):
        raise InvalidAnswersError("Submit an answer for every question on this step.")

    stored: list[OrientationAnswer] = []
    for item in answers:
        stored.append(
            _upsert_answer(
                session,
                employee_id=employee_id,
                question=questions[item.question_id],
                selected_index=item.selected_index,
            )
        )

    results = [
        AnswerResult(
            question_id=answer.question_id,
            selected_index=answer.selected_index,
            is_correct=answer.is_correct,
        )
        for answer in stored
    ]
    correct = sum(1 for result in results if result.is_correct)
    total = len(results)
    score_percent = round((correct / total) * 100, 2) if total else 100.0

    nxt = next_required_step(video, session)
    next_unlocked = bool(nxt) and can_unlock_step(employee_id, nxt, session)
    finished = orientation_is_complete(employee_id, session)
    _persist_result_if_finished(employee_id, session)

    return AnswersResponse(
        video_id=video.id,
        correct=correct,
        total=total,
        score_percent=score_percent,
        next_step_id=nxt.id if nxt else None,
        next_step_unlocked=next_unlocked,
        orientation_completed=finished,
        results=results,
    )
