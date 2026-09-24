from __future__ import annotations


class OrientationAPIError(Exception):
    status_code = 400
    code = "ORIENTATION_ERROR"

    def __init__(self, message: str, *, step_id: int | None = None):
        super().__init__(message)
        self.message = message
        self.step_id = step_id

    def to_detail(self) -> dict:
        detail: dict = {"code": self.code, "message": self.message}
        if self.step_id is not None:
            detail["step_id"] = self.step_id
        return detail


class StepLockedError(OrientationAPIError):
    status_code = 403
    code = "STEP_LOCKED"

    def __init__(self, step_id: int):
        super().__init__(
            "Previous required step is incomplete; this step stays locked.",
            step_id=step_id,
        )


class QuizNotReadyError(OrientationAPIError):
    status_code = 409
    code = "QUIZ_NOT_READY"

    def __init__(self, step_id: int):
        super().__init__(
            "Mark this mock step complete before requesting or submitting the quiz.",
            step_id=step_id,
        )


class InvalidAnswersError(OrientationAPIError):
    status_code = 400
    code = "INVALID_ANSWERS"


class ReportNotReadyError(OrientationAPIError):
    status_code = 409
    code = "REPORT_NOT_READY"

    def __init__(self) -> None:
        super().__init__("Complete every required orientation step before viewing the report.")
