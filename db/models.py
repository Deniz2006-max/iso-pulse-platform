from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class EmployeeProfile(Base):
    __tablename__ = "employee_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    department: Mapped[str] = mapped_column(String(128), nullable=False)

    watch_events: Mapped[list[OrientationWatchEvent]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
    )
    answers: Mapped[list[OrientationAnswer]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
    )
    result: Mapped[OrientationResult | None] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        uselist=False,
    )


class OrientationVideo(Base):
    __tablename__ = "orientation_videos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
    )

    questions: Mapped[list[OrientationQuestion]] = relationship(
        back_populates="video",
        cascade="all, delete-orphan",
        order_by="OrientationQuestion.sort_order",
    )
    watch_events: Mapped[list[OrientationWatchEvent]] = relationship(
        back_populates="video",
        cascade="all, delete-orphan",
    )


class OrientationQuestion(Base):
    __tablename__ = "orientation_questions"
    __table_args__ = (
        CheckConstraint("correct_index >= 0", name="ck_orientation_questions_correct_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(
        ForeignKey("orientation_videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    choices: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    correct_index: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    video: Mapped[OrientationVideo] = relationship(back_populates="questions")
    answers: Mapped[list[OrientationAnswer]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
    )


class OrientationWatchEvent(Base):
    __tablename__ = "orientation_watch_events"
    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "video_id",
            name="uq_orientation_watch_events_employee_video",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employee_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[int] = mapped_column(
        ForeignKey("orientation_videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    employee: Mapped[EmployeeProfile] = relationship(back_populates="watch_events")
    video: Mapped[OrientationVideo] = relationship(back_populates="watch_events")


class OrientationAnswer(Base):
    __tablename__ = "orientation_answers"
    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "question_id",
            name="uq_orientation_answers_employee_question",
        ),
        CheckConstraint("selected_index >= 0", name="ck_orientation_answers_selected_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employee_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("orientation_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    selected_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    employee: Mapped[EmployeeProfile] = relationship(back_populates="answers")
    question: Mapped[OrientationQuestion] = relationship(back_populates="answers")


class OrientationResult(Base):
    __tablename__ = "orientation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employee_profiles.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    scores_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    report_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    employee: Mapped[EmployeeProfile] = relationship(back_populates="result")
