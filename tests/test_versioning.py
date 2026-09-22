from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from collectors.common import CollectionError
from collectors.versioning import classify_version, compare_law, compare_publications, publication_identity
from scripts.collect_resmi_gazete import run_collection


class VersioningTests(unittest.TestCase):
    def test_hash_statuses_and_law_identity(self):
        old = {"law_number": "4857", "source_record_id": "103054", "title": "İş Kanunu",
               "raw_sha256": "a", "normalized_sha256": "x", "document_url": "u"}
        self.assertEqual("new", compare_law(None, old))
        self.assertEqual("unchanged", compare_law(old, dict(old)))
        self.assertEqual("raw_changed_only", compare_law(old, {**old, "raw_sha256": "b"}))
        self.assertEqual("text_changed", compare_law(old, {**old, "normalized_sha256": "y", "raw_sha256": "b"}))
        self.assertEqual("extraction_changed", classify_version(old, {**old, "normalized_sha256": "y"}))
        self.assertEqual("normalizer_changed", classify_version({**old, "normalizer_version": "v1"},
            {**old, "normalizer_version": "v2", "normalized_sha256": "y", "raw_sha256": "b"}))
        self.assertEqual("source_id_changed", compare_law(old, {**old, "source_record_id": "other"}))
        self.assertEqual("metadata_changed_only", classify_version(old, {**old, "title": "New title"}))
        with self.assertRaises(CollectionError):
            compare_law(old, {**old, "law_number": "6331"})

    def test_gazette_identity_survives_title_or_url_correction_when_number_exists(self):
        record = {"source_published_at": "2026-09-18", "issue_number": "33374",
                  "duplicate_issue_number": None, "document_type": "KARARLAR",
                  "law_or_decision_number": "11805", "title": "Original", "document_url": "url1"}
        self.assertEqual(publication_identity(record)[0], publication_identity({**record, "title": "Corrected", "document_url": "url2"})[0])

    def test_two_successful_gazette_runs_compare_against_last_complete(self):
        day = date(2026, 9, 18)
        row = {"konu": "Test publication (Karar Sayısı: 42)", "mevzuatAdi": "KARARLAR",
               "resmiGazeteSayisi": 33374, "resmiGazeteTarihi": "2026-09-18T00:00:00",
               "kanunKararNo": "42", "mukerrer": "HAYIR", "mukerrerSayisi": "",
               "url": "/fihrist?tarih=2026-09-18"}
        class Client:
            request_log = []
            def __init__(self, body): self.body = body
            def post_json(self, url, payload, headers, *, stage="request"):
                return json.dumps({"recordsFiltered": 1, "data": [row]}).encode()
            def get(self, url, headers=None, *, stage="request"):
                if stage == "fihrist":
                    return b'<a href="/eskiler/2026/09/20260918-1.htm">Test publication (Karar Sayisi: 42)</a>', "text/html", "utf-8"
                return self.body, "text/html", "utf-8"
        # Exact-title normalization treats Turkish dotless i and ASCII i alike.
        with tempfile.TemporaryDirectory() as root:
            output = Path(root)
            html1 = b"<html><body><p>MADDE 1 - Original.</p></body></html>"
            html2 = b"<html><body><p>MADDE 1 - Corrected.</p></body></html>"
            first_code, first = run_collection(day, output, lambda: Client(html1))
            self.assertEqual(0, first_code)
            self.assertEqual(1, first["change_counts"]["new"])
            second_code, second = run_collection(day, output, lambda: Client(html1))
            self.assertEqual(0, second_code)
            self.assertEqual(1, second["change_counts"]["unchanged"])
            third_code, third = run_collection(day, output, lambda: Client(html2))
            self.assertEqual(0, third_code)
            self.assertEqual(1, third["change_counts"]["text_changed"])
            comparison = json.loads((Path(third["run"]) / "comparison.json").read_text())
            self.assertEqual(1, len(comparison["changes"]))
            self.assertTrue(comparison["changes"][0]["old_raw_path"])
            self.assertTrue(comparison["changes"][0]["new_raw_path"])


if __name__ == "__main__":
    unittest.main()
