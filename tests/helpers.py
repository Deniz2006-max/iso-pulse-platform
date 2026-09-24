from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from db.models import (
    OrientationAnswer,
    OrientationQuestion,
    OrientationVideo,
    OrientationWatchEvent,
)


def add_step(
    session: Session,
    *,
    title: str,
    sort_order: int,
    question_count: int = 2,
    is_required: bool = True,
) -> OrientationVideo:
    video = OrientationVideo(
        title=title,
        description=f"Mock module: {title}",
        source_url=None,
        duration_seconds=60 * sort_order,
        sort_order=sort_order,
        is_required=is_required,
    )
    for index in range(question_count):
        video.questions.append(
            OrientationQuestion(
                prompt=f"{title} soru {index + 1}",
                choices=["A", "B", "C", "D"],
                correct_index=0,
                sort_order=index + 1,
            )
        )
    session.add(video)
    session.flush()
    return video


def complete_step(session: Session, employee_id: int, step: OrientationVideo) -> None:
    session.add(
        OrientationWatchEvent(
            employee_id=employee_id,
            video_id=step.id,
            completed_at=datetime.now(timezone.utc),
        )
    )
    session.flush()


def answer_questions(
    session: Session,
    employee_id: int,
    step: OrientationVideo,
    *,
    limit: int | None = None,
    skip: int = 0,
    correct: bool = True,
) -> None:
    questions = sorted(step.questions, key=lambda item: item.sort_order)
    selected_questions = questions[skip:] if limit is None else questions[skip : skip + limit]
    for question in selected_questions:
        selected = question.correct_index if correct else (question.correct_index + 1) % 4
        session.add(
            OrientationAnswer(
                employee_id=employee_id,
                question_id=question.id,
                selected_index=selected,
                is_correct=selected == question.correct_index,
                answered_at=datetime.now(timezone.utc),
            )
        )
    session.flush()
