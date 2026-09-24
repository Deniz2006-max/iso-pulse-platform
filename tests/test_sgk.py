from __future__ import annotations

import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from collectors.common import CollectionError
from collectors.office_text import extract_office_text
from collectors.sgk import BASE_URL, attachment_info, listing_url, parse_detail, parse_listing
from scripts.collect_sgk import run_collection

DETAIL_A = BASE_URL + "/duyuru/detay/Test-Duyuru-2022-12-13-03-08-24"
DETAIL_B = BASE_URL + "/duyuru/detay/Ikinci-Duyuru-2026-09-23-11-39-31"
PDF_URL = BASE_URL + "/Download/DownloadFile?f=43bc3786-c5d1-434a-abaf-04b6792342ad.pdf&d=a4767a73-8eb9-4a3d-bfb0-fb13c5cad8ce"
XLSX_URL = BASE_URL + "/Download/DownloadFile?f=c3e501ee-be7c-44d0-a1d3-1c33e7f01dd7.xlsx&d=be7c5f8b-5982-45e0-8445-ebb4f8a28fa9"


def ooxml(parts: dict[str, str]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, content in parts.items():
            archive.writestr(name, content)
    return buffer.getvalue()


XLSX_BYTES = ooxml({
    "xl/sharedStrings.xml": '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>Prim tutarı</t></si></sst>',
    "xl/worksheets/sheet1.xml": '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1"><v>123</v></c></row></sheetData></worksheet>',
})

LISTING = f'''<html><body>
<a href="/duyuru/index/SIGORTA-PRIMLERI-GENEL-MUDURLUGU-2026-01-01-00-00-00">unit</a>
<a class="announcement-card" href="{DETAIL_A.removeprefix(BASE_URL)}">A</a>
<a href="{DETAIL_B.removeprefix(BASE_URL)}" class="announcement-card">B</a>
</body></html>'''.encode()


def detail(*, title: str, date: str, unit: str, body: str, attachments: tuple[str, ...] = ()) -> bytes:
    links = "".join(f'<a href="{url.removeprefix(BASE_URL).replace("&", "&amp;")}">File</a>' for url in attachments)
    return f'''<html><body><span>ANA SAYFA</span>
<div class="announcement-detail-title"><h1>{title}</h1>
<span class="announcement-detail-subtitle">{unit}</span>
<span class="announcement-detail-date">{date}</span></div>
<div class="speak-area text-left"><p>{body}</p></div>{links}
</body></html>'''.encode()


class FakeClient:
    def __init__(self, *, pdf: bytes = b"%PDF-fake", fallback: bool = False) -> None:
        self.pdf = pdf
        self.fallback = fallback
        self.request_log: list[dict] = []

    def get(self, url, headers=None, *, stage="request"):
        self.request_log.append({"stage": stage, "url": url, "outcome": "ok"})
        if url == listing_url(1):
            return LISTING, "text/html", "utf-8"
        if url == DETAIL_A:
            return detail(title="İlk duyuru", date="22 Mart 2011 Salı", unit="SİGORTA PRİMLERİ GENEL MÜDÜRLÜĞÜ",
                          body="Prim uygulaması.", attachments=(PDF_URL, XLSX_URL)), "text/html", "utf-8"
        if url == DETAIL_B:
            return detail(title="İkinci duyuru", date="23 Eylül 2026 Çarşamba", unit="PERSONEL DAİRE BAŞKANLIĞI",
                          body="Yeni açıklama."), "text/html", "utf-8"
        if url == PDF_URL:
            if self.fallback:
                return b"<html>fallback</html>", "text/html", "utf-8"
            return self.pdf, "application/pdf", None
        if url == XLSX_URL:
            return XLSX_BYTES, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", None
        raise AssertionError(url)


class SgkTests(unittest.TestCase):
    def test_office_text_extraction_and_incomplete_formula(self):
        text, status = extract_office_text(XLSX_BYTES, "xlsx")
        self.assertEqual("text_extracted", status)
        self.assertIn("A1=Prim tutarı | B1=123", text)
        docx = ooxml({"word/document.xml": '<document xmlns="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><body><p><r><t>SGK açıklaması</t></r></p></body></document>'})
        self.assertEqual(("SGK açıklaması", "text_extracted"), extract_office_text(docx, "docx"))
        formula = ooxml({"xl/worksheets/sheet1.xml": '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row><c r="A1"><v>5</v></c><c r="B1"><f>A1*2</f></c></row></sheetData></worksheet>'})
        self.assertEqual("partial_text_requires_review", extract_office_text(formula, "xlsx")[1])
        with self.assertRaises(CollectionError):
            extract_office_text(b"not a zip", "docx")

    def test_listing_and_detail_use_content_classes_not_nav_or_slug_date(self):
        links = parse_listing(LISTING, "text/html", "utf-8", listing_url(1))
        self.assertEqual([DETAIL_A, DETAIL_B], links)
        raw = detail(title="İlk duyuru", date="22 Mart 2011 Salı", unit="SİGORTA PRİMLERİ GENEL MÜDÜRLÜĞÜ",
                     body="Prim uygulaması.", attachments=(PDF_URL, XLSX_URL))
        parsed = parse_detail(raw, "text/html", "utf-8", DETAIL_A)
        self.assertEqual("2011-03-22", parsed["source_published_at"])
        self.assertEqual("2022-12-13-03-08-24", parsed["url_embedded_timestamp"])
        self.assertEqual("SİGORTA PRİMLERİ GENEL MÜDÜRLÜĞÜ", parsed["publishing_unit"])
        self.assertEqual(2, len(parsed["attachments"]))
        self.assertEqual("xlsx", attachment_info(XLSX_URL)["extension"])

    def test_empty_listing_and_bogus_detail_are_rejected(self):
        with self.assertRaises(CollectionError):
            parse_listing(b"<html>no results</html>", "text/html", "utf-8", listing_url(1))
        with self.assertRaises(CollectionError):
            parse_detail(detail(title="Title", date="23 Eylül 2026", unit="ANA SAYFA", body="Body"),
                         "text/html", "utf-8", DETAIL_B)

    def test_complete_recheck_attachment_change_and_failed_run_preserves_index(self):
        with tempfile.TemporaryDirectory() as root, patch("scripts.collect_sgk.extract_document_text", return_value="PDF text"):
            output = Path(root)
            code, first = run_collection(1, output, FakeClient, delay_seconds=0)
            self.assertEqual(0, code)
            self.assertEqual({"baseline_created": 2}, first["change_counts"])
            self.assertTrue(first["attachment_text_complete"])
            index_path = Path(first["latest_index"])
            old_raw = index_path.read_bytes()
            index = json.loads(old_raw)
            self.assertEqual(2, len(index["records"][0]["attachments"]))
            self.assertEqual("text_extracted", index["records"][0]["attachments"][1]["text_status"])
            code, second = run_collection(1, output, FakeClient, delay_seconds=0)
            self.assertEqual(0, code)
            self.assertEqual({"unchanged": 2}, second["change_counts"])
            code, changed = run_collection(1, output, lambda: FakeClient(pdf=b"%PDF-other"), delay_seconds=0)
            self.assertEqual(0, code)
            self.assertEqual({"attachments_changed": 1, "unchanged": 1}, changed["change_counts"])
            accepted = index_path.read_bytes()
            code, failed = run_collection(1, output, lambda: FakeClient(fallback=True), delay_seconds=0)
            self.assertEqual(1, code)
            self.assertEqual("failed", failed["status"])
            self.assertEqual(accepted, index_path.read_bytes())
            self.assertTrue((Path(failed["run"]) / "partial-index.json").exists())
            self.assertTrue((Path(failed["run"]) / "request-log.json").exists())

    def test_image_only_pdf_is_retained_and_explicitly_needs_ocr(self):
        with tempfile.TemporaryDirectory() as root, patch("scripts.collect_sgk.extract_document_text", return_value=""):
            code, result = run_collection(1, Path(root), FakeClient, delay_seconds=0)
            self.assertEqual(0, code)
            self.assertEqual("complete", result["status"])
            self.assertEqual(1, result["needs_ocr_count"])
            self.assertFalse(result["attachment_text_complete"])
            index = json.loads(Path(result["latest_index"]).read_bytes())
            pdf = index["records"][0]["attachments"][0]
            self.assertEqual("needs_ocr", pdf["text_status"])
            self.assertIsNone(pdf["text_path"])
            self.assertTrue((Path(root) / "sgk" / "TumBirimler" / "page-001" / pdf["raw_path"]).exists())

    def test_reextraction_does_not_claim_official_attachment_change(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root)
            with patch("scripts.collect_sgk.extract_document_text", return_value="First extraction"):
                code, _ = run_collection(1, output, FakeClient, delay_seconds=0)
                self.assertEqual(0, code)
            with patch("scripts.collect_sgk.extract_document_text", return_value="Revised extraction"):
                code, result = run_collection(1, output, FakeClient, delay_seconds=0)
            self.assertEqual(0, code)
            self.assertEqual({"extraction_changed": 1, "unchanged": 1}, result["change_counts"])


if __name__ == "__main__":
    unittest.main()
