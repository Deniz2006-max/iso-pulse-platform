from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.app import app
from db.models import EmployeeProfile, OrientationResult
from orientation.deps import get_db
from orientation.service import can_unlock_step
from tests.helpers import add_step

PREFIX = "/api/v1/hr/orientation"


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    def override_db() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(employee: EmployeeProfile) -> dict[str, str]:
    return {"X-Employee-Id": str(employee.id)}


@pytest.fixture
def modules(session: Session):
    first = add_step(session, title="Şirket tanıtımı", sort_order=1, question_count=2)
    second = add_step(session, title="İş güvenliği", sort_order=2, question_count=2)
    third = add_step(session, title="İK süreçleri", sort_order=3, question_count=1)
    return first, second, third


def _answer_payload(video, *, correct: bool = True) -> dict:
    answers = []
    for question in sorted(video.questions, key=lambda item: item.sort_order):
        selected = question.correct_index if correct else (question.correct_index + 1) % 4
        answers.append({"question_id": question.id, "selected_index": selected})
    return {"answers": answers}


def test_status_for_new_employee_locks_later_steps(client, auth_headers, modules):
    first, second, third = modules
    response = client.get(f"{PREFIX}/status", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["current_step_id"] == first.id
    assert body["locked_step_ids"] == [second.id, third.id]
    assert body["quiz_pending"] is False
    assert body["completed"] is False
    assert body["report_ready"] is False


def test_videos_flags_match_gate(client, auth_headers, modules):
    first, second, third = modules
    response = client.get(f"{PREFIX}/videos", headers=auth_headers)
    assert response.status_code == 200
    by_id = {item["id"]: item for item in response.json()}
    assert by_id[first.id]["unlocked"] is True
    assert by_id[first.id]["completed"] is False
    assert by_id[second.id]["unlocked"] is False
    assert by_id[third.id]["unlocked"] is False


def test_complete_and_questions_on_locked_step_are_forbidden(
    client, auth_headers, modules
):
    _first, second, _third = modules
    complete = client.post(f"{PREFIX}/videos/{second.id}/complete", headers=auth_headers)
    assert complete.status_code == 403
    assert complete.json()["detail"]["code"] == "STEP_LOCKED"

    questions = client.get(f"{PREFIX}/videos/{second.id}/questions", headers=auth_headers)
    assert questions.status_code == 403
    assert questions.json()["detail"]["code"] == "STEP_LOCKED"


def test_questions_require_complete_and_omit_correct_index(
    client, auth_headers, modules
):
    first, _second, _third = modules
    before = client.get(f"{PREFIX}/videos/{first.id}/questions", headers=auth_headers)
    assert before.status_code == 409
    assert before.json()["detail"]["code"] == "QUIZ_NOT_READY"

    marked = client.post(f"{PREFIX}/videos/{first.id}/complete", headers=auth_headers)
    assert marked.status_code == 200
    assert marked.json()["quiz_available"] is True

    quiz = client.get(f"{PREFIX}/videos/{first.id}/questions", headers=auth_headers)
    assert quiz.status_code == 200
    raw = quiz.text
    assert "correct_index" not in raw
    body = quiz.json()
    assert body["video_id"] == first.id
    assert len(body["questions"]) == 2
    for question in body["questions"]:
        assert set(question) == {"id", "prompt", "choices", "sort_order"}
        assert "correct_index" not in question


def test_answers_score_and_unlock_next_step(client, auth_headers, modules, session, employee):
    first, second, third = modules
    client.post(f"{PREFIX}/videos/{first.id}/complete", headers=auth_headers)

    payload = _answer_payload(first, correct=True)
    # Force one miss so score is not 100%.
    payload["answers"][1]["selected_index"] = (first.questions[1].correct_index + 1) % 4

    response = client.post(
        f"{PREFIX}/videos/{first.id}/answers",
        headers=auth_headers,
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["video_id"] == first.id
    assert body["total"] == 2
    assert body["correct"] == 1
    assert body["score_percent"] == 50.0
    assert body["next_step_id"] == second.id
    assert body["next_step_unlocked"] is True
    assert body["orientation_completed"] is False
    assert "correct_index" not in response.text
    assert can_unlock_step(employee.id, second.id, session) is True
    assert can_unlock_step(employee.id, third.id, session) is False

    status = client.get(f"{PREFIX}/status", headers=auth_headers).json()
    assert status["current_step_id"] == second.id
    assert second.id not in status["locked_step_ids"]
    assert third.id in status["locked_step_ids"]
    assert status["quiz_pending"] is False

    videos = {item["id"]: item for item in client.get(f"{PREFIX}/videos", headers=auth_headers).json()}
    assert videos[first.id]["quiz_done"] is True
    assert videos[second.id]["unlocked"] is True
    assert videos[second.id]["quiz_done"] is False


def test_answers_on_incomplete_step_conflict_and_missing_questions_rejected(
    client, auth_headers, modules
):
    first, _second, _third = modules
    rejected = client.post(
        f"{PREFIX}/videos/{first.id}/answers",
        headers=auth_headers,
        json=_answer_payload(first),
    )
    assert rejected.status_code == 409

    client.post(f"{PREFIX}/videos/{first.id}/complete", headers=auth_headers)
    partial = client.post(
        f"{PREFIX}/videos/{first.id}/answers",
        headers=auth_headers,
        json={"answers": [_answer_payload(first)["answers"][0]]},
    )
    assert partial.status_code == 400
    assert partial.json()["detail"]["code"] == "INVALID_ANSWERS"


def test_full_sequence_completes_orientation(client, auth_headers, modules, session, employee):
    first, second, third = modules
    for video in (first, second, third):
        complete = client.post(f"{PREFIX}/videos/{video.id}/complete", headers=auth_headers)
        assert complete.status_code == 200
        submitted = client.post(
            f"{PREFIX}/videos/{video.id}/answers",
            headers=auth_headers,
            json=_answer_payload(video, correct=True),
        )
        assert submitted.status_code == 200

    last = submitted.json()
    assert last["next_step_id"] is None
    assert last["next_step_unlocked"] is False
    assert last["orientation_completed"] is True
    assert last["correct"] == 1
    assert last["total"] == 1

    status = client.get(f"{PREFIX}/status", headers=auth_headers).json()
    assert status["completed"] is True
    assert status["current_step_id"] is None
    assert status["locked_step_ids"] == []
    assert status["report_ready"] is True

    result = session.query(OrientationResult).filter_by(employee_id=employee.id).one()
    assert result.completed_at is not None
    assert result.scores_json["correct"] == 5
    assert result.scores_json["total_questions"] == 5
    assert result.report_summary
    assert result.scores_json["report"]["summary"] == result.report_summary
    assert result.scores_json["report"]["strengths"]
    assert result.scores_json["report"]["recommendation"]


def test_missing_employee_header_unauthorized(client, modules):
    response = client.get(f"{PREFIX}/status")
    assert response.status_code == 401


def test_report_pdf_before_completion_is_conflict(client, auth_headers, modules):
    response = client.get(f"{PREFIX}/report/pdf", headers=auth_headers)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "REPORT_NOT_READY"


def test_report_pdf_returns_200_and_pdf_magic_bytes(
    client, auth_headers, modules, session, employee
):
    first, second, third = modules
    for video in (first, second, third):
        assert client.post(
            f"{PREFIX}/videos/{video.id}/complete", headers=auth_headers
        ).status_code == 200
        submitted = client.post(
            f"{PREFIX}/videos/{video.id}/answers",
            headers=auth_headers,
            json=_answer_payload(video, correct=True),
        )
        assert submitted.status_code == 200

    json_report = client.get(f"{PREFIX}/report", headers=auth_headers)
    assert json_report.status_code == 200
    body = json_report.json()
    assert "Oryantasyon tamamlandı" in body["summary"]
    assert body["scores"]["total_questions"] == 5
    assert "report" not in body["scores"]

    response = client.get(f"{PREFIX}/report/pdf", headers=auth_headers)
    assert response.status_code == 200
    content_type = response.headers["content-type"]
    assert content_type.startswith("application/pdf")
    assert response.content[:4] == b"%PDF"
    assert response.content.rstrip().endswith(b"%%EOF") or b"%%EOF" in response.content[-64:]
    assert len(response.content) > 200
    assert "attachment" in response.headers.get("content-disposition", "")


def test_demo_page_serves_quiz_ui_with_conditional_player():
    with TestClient(app) as test_client:
        response = test_client.get("/demo")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    html = response.text
    assert 'id="next-step"' in html
    assert 'id="download-pdf"' in html
    assert 'id="quiz-form"' in html
    assert 'id="complete-step"' in html
    assert "/status" in html
    assert "/videos" in html
    assert "/questions" in html
    assert "source_url" in html
    assert "ended" in html
    assert "<video" in html.lower()
    assert "youtube" not in html.lower()
    assert "els.next.disabled = !canGoNext()" in html
