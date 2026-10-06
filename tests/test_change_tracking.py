from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.ingestion.change_tracking import content_sha256, stable_item_id, track_changes
from src.ingestion.models import DailyUpdate


def item(*, url: str = "https://example.test/notice/1", raw_text: str = "Published text") -> DailyUpdate:
    return DailyUpdate(
        source="sgk",
        publication_date="2026-10-05",
        title="Example notice",
        category="Duyuru",
        url=url,
        raw_text=raw_text,
    )


class ChangeTrackingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_path = Path(self.temp_dir.name) / "state.json"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_first_verified_capture_is_new(self) -> None:
        report = track_changes([item()], state_path=self.state_path, run_date="2026-10-05")

        self.assertEqual(
            report["counts"], {"new": 1, "changed": 0, "unchanged": 0, "unverified": 0}
        )
        self.assertEqual(len(report["items"][0]["content_sha256"]), 64)
        self.assertEqual(json.loads(self.state_path.read_text(encoding="utf-8"))["schema_version"], 1)

    def test_same_content_is_unchanged_and_same_day_rerun_is_idempotent(self) -> None:
        first = track_changes([item()], state_path=self.state_path, run_date="2026-10-05")
        repeat = track_changes([item()], state_path=self.state_path, run_date="2026-10-05")

        self.assertEqual(first["items"][0]["change_status"], "new")
        self.assertEqual(repeat["items"][0]["change_status"], "new")
        self.assertIsNone(repeat["items"][0]["previous_content_sha256"])
        next_day = track_changes([item()], state_path=self.state_path, run_date="2026-10-06")
        self.assertEqual(next_day["items"][0]["change_status"], "unchanged")

    def test_changed_text_reports_both_hashes(self) -> None:
        track_changes([item()], state_path=self.state_path, run_date="2026-10-05")
        report = track_changes(
            [item(raw_text="Revised published text")],
            state_path=self.state_path,
            run_date="2026-10-06",
        )

        row = report["items"][0]
        self.assertEqual(row["change_status"], "changed")
        self.assertNotEqual(row["content_sha256"], row["previous_content_sha256"])

    def test_same_day_rerun_preserves_changed_event_baseline(self) -> None:
        track_changes([item()], state_path=self.state_path, run_date="2026-10-05")
        changed = track_changes(
            [item(raw_text="Revised published text")],
            state_path=self.state_path,
            run_date="2026-10-06",
        )
        repeat = track_changes(
            [item(raw_text="Revised published text")],
            state_path=self.state_path,
            run_date="2026-10-06",
        )

        self.assertEqual(repeat["items"][0]["change_status"], "changed")
        self.assertEqual(
            repeat["items"][0]["previous_content_sha256"],
            changed["items"][0]["previous_content_sha256"],
        )

    def test_whitespace_only_variation_does_not_count_as_change(self) -> None:
        track_changes(
            [item(raw_text="Line one\n\nLine two")],
            state_path=self.state_path,
            run_date="2026-10-05",
        )
        report = track_changes(
            [item(raw_text="Line one  Line two")],
            state_path=self.state_path,
            run_date="2026-10-06",
        )

        self.assertEqual(report["items"][0]["change_status"], "unchanged")

    def test_blank_extraction_is_unverified_and_does_not_replace_verified_hash(self) -> None:
        track_changes([item()], state_path=self.state_path, run_date="2026-10-05")
        prior_hash = content_sha256(item())
        blank = track_changes(
            [item(raw_text="")],
            state_path=self.state_path,
            run_date="2026-10-06",
        )
        snapshot = json.loads(self.state_path.read_text(encoding="utf-8"))["items"][stable_item_id(item())]

        self.assertEqual(blank["items"][0]["change_status"], "unverified")
        self.assertEqual(snapshot["content_sha256"], prior_hash)
        recovered = track_changes([item()], state_path=self.state_path, run_date="2026-10-07")
        self.assertEqual(recovered["items"][0]["change_status"], "unchanged")

    def test_successful_recovery_after_same_day_blank_capture_is_verified(self) -> None:
        track_changes([item()], state_path=self.state_path, run_date="2026-10-05")
        track_changes([item(raw_text="")], state_path=self.state_path, run_date="2026-10-06")

        recovered = track_changes([item()], state_path=self.state_path, run_date="2026-10-06")

        self.assertEqual(recovered["items"][0]["change_status"], "unchanged")

    def test_missing_record_is_not_reported_as_deleted(self) -> None:
        track_changes([item()], state_path=self.state_path, run_date="2026-10-05")
        report = track_changes([], state_path=self.state_path, run_date="2026-10-06")

        self.assertEqual(report["items"], [])
        self.assertFalse(report["missing_items_are_deletions"])
        self.assertEqual(len(json.loads(self.state_path.read_text(encoding="utf-8"))["items"]), 1)


if __name__ == "__main__":
    unittest.main()
