from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import (
    OrientationAnswer,
    OrientationQuestion,
    OrientationVideo,
    OrientationWatchEvent,
)

Step = OrientationVideo | int


def _as_video(session: Session, step: Step) -> OrientationVideo:
    if isinstance(step, OrientationVideo):
        return step
    video = session.get(OrientationVideo, step)
    if video is None:
        raise LookupError(f"orientation step {step} not found")
    return video


def previous_required_step(step: Step, session: Session) -> OrientationVideo | None:
    """Return the nearest earlier required module, or None for the first gate."""
    video = _as_video(session, step)
    return session.scalar(
        select(OrientationVideo)
        .where(
            OrientationVideo.is_required.is_(True),
            OrientationVideo.sort_order < video.sort_order,
        )
        .order_by(OrientationVideo.sort_order.desc())
        .limit(1)
    )


def marked_complete(employee_id: int, step: Step, session: Session) -> bool:
    video = _as_video(session, step)
    completed_at = session.scalar(
        select(OrientationWatchEvent.completed_at).where(
            OrientationWatchEvent.employee_id == employee_id,
            OrientationWatchEvent.video_id == video.id,
        )
    )
    return completed_at is not None


def all_questions_answered(employee_id: int, step: Step, session: Session) -> bool:
    video = _as_video(session, step)
    question_ids = list(
        session.scalars(
            select(OrientationQuestion.id).where(OrientationQuestion.video_id == video.id)
        )
    )
    if not question_ids:
        return True
    answered = session.scalar(
        select(func.count())
        .select_from(OrientationAnswer)
        .where(
            OrientationAnswer.employee_id == employee_id,
            OrientationAnswer.question_id.in_(question_ids),
        )
    )
    return int(answered or 0) == len(question_ids)


def can_unlock_step(employee_id: int, step: Step, session: Session) -> bool:
    """Unlock a step only after the previous required module is done.

    The first required step is always open. Later steps stay locked until the
    previous required step's mock video is completed and every question on
    that step has been answered. Score does not affect the lock.
    """
    prev = previous_required_step(step, session)
    if prev is None:
        return True
    return marked_complete(employee_id, prev, session) and all_questions_answered(
        employee_id, prev, session
    )


def quiz_available(employee_id: int, step: Step, session: Session) -> bool:
    """Quiz is offered only for an unlocked step that has been marked complete."""
    if not can_unlock_step(employee_id, step, session):
        return False
    return marked_complete(employee_id, step, session)
