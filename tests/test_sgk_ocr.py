from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from collectors.common import CollectionError, sha256_bytes
from scripts.ocr_sgk import run_ocr


class SgkOcrTests(unittest.TestCase):
    def test_enrichment_is_separate_and_marked_unverified(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            page_dir = output / "sgk" / "TumBirimler" / "page-001"
            source = page_dir / "runs" / "run-1" / "attachment.pdf"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"%PDF-fake")
            index = {"source": "sgk", "page": 1, "source_capture_complete": True,
                     "records": [{"source_record_id": "/duyuru/detay/example",
                                  "attachments": [{"url": "https://www.sgk.gov.tr/example.pdf",
                                                   "raw_path": "runs/run-1/attachment.pdf",
                                                   "raw_sha256": sha256_bytes(source.read_bytes()),
                                                   "text_status": "needs_ocr"}]}]}
            index_path = page_dir / "index.json"
            index_path.write_text(json.dumps(index), encoding="utf-8")
            original = index_path.read_bytes()

            with patch("scripts.ocr_sgk._tool", side_effect=lambda name: name), \
                 patch("scripts.ocr_sgk._run", side_effect=lambda args: (
                     "List of available languages\ntur" if "--list-langs" in args else
                     "tesseract 5.0" if "--version" in args else "")), \
                 patch("scripts.ocr_sgk.ocr_pdf", return_value=("[Sayfa 1]\nGerçek tarama metni", 1)):
                results = run_ocr(1, output)
            self.assertEqual(1, len(results))
            metadata_path = Path(results[0]["metadata"])
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual("ocr_unverified", metadata["status"])
            self.assertTrue(metadata["requires_human_review"])
            self.assertEqual(sha256_bytes(original), metadata["source_index_sha256"])
            self.assertEqual(original, index_path.read_bytes())
            self.assertIn("Gerçek tarama metni", (page_dir / metadata["ocr_text_path"]).read_text(encoding="utf-8"))
            self.assertEqual(
                metadata["ocr_text_sha256"],
                sha256_bytes((page_dir / metadata["ocr_text_path"]).read_bytes()),
            )

            source.write_bytes(b"%PDF-tampered")
            with patch("scripts.ocr_sgk._tool", side_effect=lambda name: name), \
                 patch("scripts.ocr_sgk._run", return_value="tur"):
                with self.assertRaises(CollectionError):
                    run_ocr(1, output)


if __name__ == "__main__":
    unittest.main()
