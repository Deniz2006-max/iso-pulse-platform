from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StatusResponse(BaseModel):
    current_step_id: int | None
    locked_step_ids: list[int]
    quiz_pending: bool
    completed: bool
    report_ready: bool


class VideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    source_url: str | None
    duration_seconds: int
    sort_order: int
    is_required: bool
    unlocked: bool
    completed: bool
    quiz_done: bool


class WatchCompleteResponse(BaseModel):
    video_id: int
    completed_at: datetime
    quiz_available: bool


class QuestionPublic(BaseModel):
    """Quiz item returned to the client. correct_index is intentionally omitted."""

    id: int
    prompt: str
    choices: list[str]
    sort_order: int


class QuestionsResponse(BaseModel):
    video_id: int
    questions: list[QuestionPublic]


class AnswerIn(BaseModel):
    question_id: int
    selected_index: int = Field(ge=0)


class AnswersRequest(BaseModel):
    answers: list[AnswerIn]


class AnswerResult(BaseModel):
    question_id: int
    selected_index: int
    is_correct: bool


class AnswersResponse(BaseModel):
    video_id: int
    correct: int
    total: int
    score_percent: float
    next_step_id: int | None
    next_step_unlocked: bool
    orientation_completed: bool
    results: list[AnswerResult]


class ReportResponse(BaseModel):
    summary: str
    strengths: list[str]
    gaps: list[str]
    recommendation: str
    scores: dict
    completed_at: datetime | None
    report_ready: bool = True
