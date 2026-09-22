from __future__ import annotations

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError
from urllib.request import Request

from collectors.common import CollectionError, HttpClient
from scripts.collect_resmi_gazete import run_collection


class RunTests(unittest.TestCase):
    def test_failed_fihrist_keeps_previous_success_and_partial_evidence(self):
        day = date(2026, 9, 18)
        page = {"recordsFiltered": 1, "data": [{
            "konu": "Test decision", "mevzuatAdi": "KARARLAR", "resmiGazeteSayisi": 33375,
            "resmiGazeteTarihi": "2026-09-18T00:00:00", "kanunKararNo": "1",
            "mukerrer": "HAYIR", "mukerrerSayisi": "", "url": "/fihrist?tarih=2026-09-18"}]}
        class TimeoutClient:
            request_log = [{"stage": "fihrist", "attempt": 3, "outcome": "error", "error_type": "URLError"}]
            def post_json(self, url, payload, headers, *, stage="request"):
                return json.dumps(page).encode()
            def get(self, url, headers=None, *, stage="request"):
                raise CollectionError("fihrist: simulated timeout")
        with tempfile.TemporaryDirectory() as root:
            output = Path(root)
            day_dir = output / "resmi_gazete" / day.isoformat()
            day_dir.mkdir(parents=True)
            prior = json.dumps({"source": "resmi_gazete", "requested_date": day.isoformat(), "records": []}).encode() + b"\n"
            (day_dir / "index.json").write_bytes(prior)
            code, result = run_collection(day, output, TimeoutClient)
            self.assertEqual(1, code)
            self.assertEqual("failed", result["status"])
            self.assertEqual("fihrist", result["stage"])
            self.assertEqual(prior, (day_dir / "index.json").read_bytes())
            run_dir = Path(result["run"])
            self.assertTrue((run_dir / "filter-page-001.json").is_file())
            self.assertTrue((run_dir / "partial-index.json").is_file())
            self.assertEqual("failed", json.loads((run_dir / "manifest.json").read_text())["status"])
            self.assertEqual("fihrist", json.loads((run_dir / "request-log.json").read_text())[0]["stage"])

    def test_http_attempt_log_contains_stage_timing_and_retry(self):
        client = HttpClient(timeout=0.01)
        class Response:
            status = 200
            class Headers:
                def get_content_type(self): return "text/html"
                def get_content_charset(self): return "utf-8"
            headers = Headers()
            def __enter__(self): return self
            def __exit__(self, *_): return None
            def read(self): return b"ok"
        with patch("collectors.common.urlopen", side_effect=[URLError("timeout"), Response()]), \
             patch("collectors.common.time.sleep"):
            raw, _, _ = client.get("https://www.resmigazete.gov.tr/test", stage="fihrist")
        self.assertEqual(b"ok", raw)
        self.assertEqual(["error", "ok"], [event["outcome"] for event in client.request_log])
        self.assertTrue(all(event["stage"] == "fihrist" and event["elapsed_ms"] >= 0 for event in client.request_log))
        self.assertEqual([1, 2], [event["attempt"] for event in client.request_log])


if __name__ == "__main__":
    unittest.main()
