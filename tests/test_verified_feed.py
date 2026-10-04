"""Offline contract and evidence-integrity tests for the app input adapter."""

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from src.ingestion.models import DailyUpdate
from src.ingestion.verified_feed import _canonical_json, _sha256, build_feed


class VerifiedFeedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rg = self.root / "rg"
        self.sgk = self.root / "sgk"
        self.rg.mkdir()
        self.sgk.mkdir()
        self.day = date(2026, 9, 25)
        self.rg_text = "4857 sayılı İş Kanunu anılıyor. " * 5
        self.rg_raw = b"<html>official publication</html>"
        (self.rg / "source.html").write_bytes(self.rg_raw)
        (self.rg / "source.txt").write_bytes((self.rg_text + "\n").encode("utf-8"))
        self.rg_record = {
            "source_record_id": "rg:test", "publication_id": "rgpub:test",
            "source_published_at": self.day.isoformat(), "title": "Test yönetmeliği",
            "document_type": "YÖNETMELİKLER", "document_url": "https://example.test/rg/one",
            "change_status": "new", "content_status": "text_extracted",
            "raw_path": "source.html", "raw_sha256": _sha256(self.rg_raw),
            "text_path": "source.txt", "normalized_sha256": _sha256(self.rg_text.encode()),
        }
        self.sgk_body = "5510 sayılı Kanun kapsamındaki işverenler için duyuru metni. " * 3
        self.sgk_raw = b"<html>official announcement</html>"
        self.sgk_listing = b"<html>listing</html>"
        (self.sgk / "listing.html").write_bytes(self.sgk_listing)
        (self.sgk / "detail.html").write_bytes(self.sgk_raw)
        self.sgk_record = {
            "source_record_id": "/duyuru/detay/test", "canonical_url": "https://example.test/sgk/test",
            "title": "İşveren duyurusu", "publishing_unit": "Birim",
            "source_published_at": self.day.isoformat(), "body_text": self.sgk_body,
            "normalized_sha256": _sha256(_canonical_json({
                "title": "İşveren duyurusu", "unit": "Birim",
                "published_at": self.day.isoformat(), "body": self.sgk_body,
            })),
            "detail_raw_path": "detail.html", "detail_raw_sha256": _sha256(self.sgk_raw),
            "attachments": [], "change_status": "new",
        }
        self.write_indexes()

    def write_indexes(self):
        (self.rg / "index.json").write_text(json.dumps({
            "source": "resmi_gazete", "requested_date": self.day.isoformat(),
            "record_count": 1, "retrieved_at": "2026-09-25T12:00:00+00:00",
            "records": [self.rg_record],
        }), encoding="utf-8")
        (self.sgk / "index.json").write_text(json.dumps({
            "source": "sgk", "record_count": 1, "source_capture_complete": True,
            "collected_at": "2026-09-25T12:00:00+00:00",
            "listing_raw_path": "listing.html", "listing_raw_sha256": _sha256(self.sgk_listing),
            "records": [self.sgk_record],
        }), encoding="utf-8")

    def feed(self):
        return build_feed(self.rg / "index.json", self.sgk / "index.json", self.day)

    def test_verified_rows_match_unchanged_app_schema(self):
        payload, evidence = self.feed()
        self.assertEqual(2, len(payload["all.json"]))
        self.assertEqual({"resmi_gazete", "sgk"},
                         {DailyUpdate.model_validate(row).source for row in payload["all.json"]})
        expected_keys = set(DailyUpdate.model_fields)
        self.assertTrue(all(set(row) == expected_keys for row in payload["all.json"]))
        self.assertFalse(evidence["legal_effect_verified"])
        self.assertEqual("mention_only", evidence["records"][0]["literal_numbered_references"][0]["relation"])

    def test_tampered_text_is_held_out_of_feed(self):
        (self.rg / "source.txt").write_text("tampered\n", encoding="utf-8")
        payload, evidence = self.feed()
        self.assertEqual(1, len(payload["all.json"]))
        self.assertEqual("held_for_review", evidence["records"][0]["status"])
        self.assertIn("SHA-256 mismatch", evidence["records"][0]["reason"])

    def test_shared_pdf_cannot_be_attributed_to_one_publication(self):
        second = {**self.rg_record, "source_record_id": "rg:second", "publication_id": "rgpub:second"}
        index = json.loads((self.rg / "index.json").read_text(encoding="utf-8"))
        index["records"].append(second)
        index["record_count"] = 2
        (self.rg / "index.json").write_text(json.dumps(index), encoding="utf-8")
        payload, evidence = self.feed()
        self.assertEqual([], payload["resmi_gazete.json"])
        self.assertEqual(2, sum(row["status"] == "held_for_review" for row in evidence["records"]))

    def test_tampered_sgk_body_is_held_out_of_feed(self):
        self.sgk_record["body_text"] = "A different body " * 15
        self.write_indexes()
        payload, evidence = self.feed()
        self.assertEqual([], payload["sgk.json"])
        self.assertEqual("held_for_review", evidence["records"][1]["status"])
        self.assertIn("hash mismatch", evidence["records"][1]["reason"])

    def test_incomplete_sgk_attachment_is_held_out_of_feed(self):
        self.sgk_record["attachments"] = [{
            "url": "https://example.test/attachment.pdf", "raw_path": "attachment.pdf",
            "raw_sha256": _sha256(b"attachment"), "text_status": "partial_text_requires_review",
        }]
        (self.sgk / "attachment.pdf").write_bytes(b"attachment")
        self.write_indexes()
        payload, evidence = self.feed()
        self.assertEqual([], payload["sgk.json"])
        self.assertEqual("held_for_review", evidence["records"][1]["status"])
        self.assertIn("attachment text incomplete", evidence["records"][1]["reason"])


if __name__ == "__main__":
    unittest.main()
