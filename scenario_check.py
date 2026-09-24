#!/usr/bin/env python3
"""E2E scenario check for orientation: skip 403, sequential quiz, report/PDF 200."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from uuid import uuid4

import httpx

from db.models import EmployeeProfile
from db.session import session_scope

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
API = "/api/v1/hr/orientation"


class ScenarioCheck:
    def __init__(self, base_url: str, employee_id: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.employee_id = employee_id
        self.client = httpx.Client(
            base_url=self.base_url,
            headers={"X-Employee-Id": str(employee_id)},
            timeout=30.0,
        )
        self.passed = 0
        self.failed = 0

    def close(self) -> None:
        self.client.close()

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        status = "PASS" if ok else "FAIL"
        if ok:
            self.passed += 1
        else:
            self.failed += 1
        suffix = f" — {detail}" if detail else ""
        print(f"[{status}] {name}{suffix}")

    def _error_code(self, response: httpx.Response) -> str | None:
        try:
            payload = response.json()
        except ValueError:
            return None
        detail = payload.get("detail")
        if isinstance(detail, dict):
            return detail.get("code")
        return None

    def skip_step_is_forbidden(self, videos: list[dict]) -> None:
        if len(videos) < 2:
            self.check("skip locked step", False, "need at least two modules")
            return
        second_id = videos[1]["id"]
        response = self.client.get(f"{API}/videos/{second_id}/questions")
        code = self._error_code(response)
        self.check(
            "GET /questions on step 2 without finishing step 1 returns 403",
            response.status_code == 403 and code == "STEP_LOCKED",
            f"status={response.status_code} code={code}",
        )

    def complete_all_steps(self, videos: list[dict]) -> None:
        for index, video in enumerate(videos, start=1):
            video_id = video["id"]
            complete = self.client.post(f"{API}/videos/{video_id}/complete")
            self.check(
                f"step {index} POST /complete",
                complete.status_code == 200,
                f"status={complete.status_code}",
            )
            if complete.status_code != 200:
                return

            quiz = self.client.get(f"{API}/videos/{video_id}/questions")
            self.check(
                f"step {index} GET /questions",
                quiz.status_code == 200 and "correct_index" not in quiz.text,
                f"status={quiz.status_code}",
            )
            if quiz.status_code != 200:
                return

            questions = quiz.json().get("questions") or []
            payload = {
                "answers": [
                    {"question_id": question["id"], "selected_index": 0}
                    for question in questions
                ]
            }
            submitted = self.client.post(
                f"{API}/videos/{video_id}/answers",
                json=payload,
            )
            body = submitted.json() if submitted.headers.get("content-type", "").startswith("application/json") else {}
            last = index == len(videos)
            unlocked = body.get("next_step_unlocked") is True
            finished = body.get("orientation_completed") is True
            ok = submitted.status_code == 200 and (
                finished if last else unlocked or body.get("next_step_id") is None
            )
            self.check(
                f"step {index} POST /answers",
                ok,
                (
                    f"status={submitted.status_code} "
                    f"score={body.get('correct')}/{body.get('total')} "
                    f"next_unlocked={body.get('next_step_unlocked')} "
                    f"completed={body.get('orientation_completed')}"
                ),
            )
            if submitted.status_code != 200:
                return

        status = self.client.get(f"{API}/status")
        payload = status.json() if status.status_code == 200 else {}
        self.check(
            "GET /status after last quiz",
            status.status_code == 200
            and payload.get("completed") is True
            and payload.get("report_ready") is True,
            f"status={status.status_code} body={payload}",
        )

    def report_and_pdf_ok(self) -> None:
        report = self.client.get(f"{API}/report")
        body = report.json() if report.status_code == 200 else {}
        self.check(
            "GET /report returns 200 with summary",
            report.status_code == 200
            and bool(body.get("summary"))
            and isinstance(body.get("strengths"), list)
            and isinstance(body.get("gaps"), list)
            and bool(body.get("recommendation")),
            f"status={report.status_code} keys={list(body)}",
        )

        pdf = self.client.get(f"{API}/report/pdf")
        content_type = pdf.headers.get("content-type", "")
        self.check(
            "GET /report/pdf returns 200 PDF binary",
            pdf.status_code == 200
            and content_type.startswith("application/pdf")
            and pdf.content[:4] == b"%PDF"
            and len(pdf.content) > 200,
            f"status={pdf.status_code} type={content_type} bytes={len(pdf.content)}",
        )


def create_employee() -> int:
    email = f"e2e.{uuid4().hex[:10]}@iso.org.tr"
    with session_scope() as session:
        employee = EmployeeProfile(
            email=email,
            full_name="E2E Senaryo",
            hire_date=date(2026, 9, 21),
            department="İnsan Kaynakları",
        )
        session.add(employee)
        session.flush()
        employee_id = employee.id
    print(f"Created employee id={employee_id} email={email}")
    return employee_id


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Orientation E2E scenario check.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--employee-id",
        type=int,
        default=None,
        help="Use an existing employee. Default: insert a fresh new hire.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    employee_id = args.employee_id or create_employee()
    scenario = ScenarioCheck(args.base_url, employee_id)
    try:
        videos_response = scenario.client.get(f"{API}/videos")
        if videos_response.status_code != 200:
            print(
                f"[FAIL] GET /videos status={videos_response.status_code}. "
                f"Is the API running at {args.base_url}?"
            )
            return 1
        videos = sorted(videos_response.json(), key=lambda item: item["sort_order"])
        print(f"Modules: {[item['title'] for item in videos]}")
        scenario.skip_step_is_forbidden(videos)
        scenario.complete_all_steps(videos)
        scenario.report_and_pdf_ok()
    except httpx.ConnectError:
        print(f"[FAIL] cannot connect to {args.base_url}")
        return 1
    finally:
        scenario.close()

    print(
        f"\n{scenario.passed} passed, {scenario.failed} failed "
        f"(employee_id={employee_id})"
    )
    return 0 if scenario.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
