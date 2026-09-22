from __future__ import annotations

import json
import unittest
from datetime import date

from collectors.common import CollectionError
from collectors.resmi_gazete import build_index_artifact, collect_index, extract_document_text, parse_fihrist_links, resolve_document_urls


def row(number: int, *, day: str = "2026-09-19", duplicate: bool = False) -> dict:
    return {
        "konu": f"Test publication {number}",
        "mevzuatAdi": "KANUNLAR",
        "resmiGazeteSayisi": 33375,
        "resmiGazeteTarihi": f"{day}T00:00:00",
        "kanunKararNo": str(number),
        "mukerrer": "EVET" if duplicate else "HAYIR",
        "mukerrerSayisi": "1" if duplicate else "",
        "url": f"/fihrist?tarih={day}" + ("&mukerrer=1" if duplicate else ""),
    }


class FakeClient:
    def __init__(self, pages: list[dict]):
        self.pages = pages
        self.requests: list[dict] = []

    def post_json(self, url: str, payload: dict, headers: dict) -> bytes:
        self.requests.append(payload)
        return json.dumps(self.pages.pop(0)).encode("utf-8")


class GazetteIndexTests(unittest.TestCase):
    def test_paginates_and_keeps_mukerrer_identity(self):
        first = [row(i) for i in range(100)]
        second = [row(100, duplicate=True)]
        client = FakeClient([
            {"recordsFiltered": 101, "data": first},
            {"recordsFiltered": 101, "data": second},
        ])
        records, raw = collect_index(date(2026, 9, 19), client)
        self.assertEqual(101, len(records))
        self.assertEqual(2, len(raw))
        self.assertEqual(100, client.requests[1]["start"])
        self.assertTrue(records[-1]["is_duplicate_issue"])
        self.assertIn("mukerrer=1", records[-1]["issue_url"])
        self.assertIsNone(records[-1]["document_url"])

    def test_rejects_homepage_or_other_invalid_response(self):
        client = FakeClient([{"recordsFiltered": 1, "data": None}])
        with self.assertRaises(CollectionError):
            collect_index(date(2026, 9, 19), client)

    def test_rejects_incomplete_pagination(self):
        client = FakeClient([{"recordsFiltered": 2, "data": [row(1)]}, {"recordsFiltered": 2, "data": []}])
        with self.assertRaises(CollectionError):
            collect_index(date(2026, 9, 19), client)

    def test_rejects_wrong_date(self):
        client = FakeClient([{"recordsFiltered": 1, "data": [row(1, day="2026-09-18")]}])
        with self.assertRaises(CollectionError):
            collect_index(date(2026, 9, 19), client)

    def test_matches_real_item_link_in_fihrist(self):
        records = [{"title": "İş Kanununda Değişiklik", "issue_url": "https://www.resmigazete.gov.tr/fihrist?tarih=2026-09-19"}]
        class Getter:
            def get(self, url, headers=None):
                body = '<a href="/eskiler/2026/09/20260919-1.htm">→ İş Kanununda Değişiklik</a>'.encode("utf-8")
                return body, "text/html", "utf-8"
        raw = resolve_document_urls(records, Getter(), date(2026, 9, 19))
        self.assertEqual(1, len(raw))
        self.assertEqual("https://www.resmigazete.gov.tr/eskiler/2026/09/20260919-1.htm", records[0]["document_url"])

    def test_rejects_missing_item_link(self):
        html = b'<a href="/eskiler/2026/09/20260919-1.htm">Different title</a>'
        links = parse_fihrist_links(html, day=date(2026, 9, 19), issue_url="https://www.resmigazete.gov.tr/fihrist?tarih=2026-09-19", charset="utf-8")
        self.assertNotIn("İş Kanununda Değişiklik", links)

    def test_unmatched_title_is_explicit_and_never_assigned_a_guessed_url(self):
        records = [{"title": "Different title", "issue_url": "https://www.resmigazete.gov.tr/fihrist?tarih=2026-09-19", "document_url": None, "content_status": "discovered"}]
        class Getter:
            def get(self, url, headers=None):
                return b'<a href="/eskiler/2026/09/20260919-1.htm">Another title</a>', "text/html", "utf-8"
        resolve_document_urls(records, Getter(), date(2026, 9, 19))
        self.assertEqual("link_unresolved", records[0]["content_status"])
        self.assertIsNone(records[0]["document_url"])

    def test_html_extraction_uses_body_and_ignores_script(self):
        html = b'<html><head><title>Navigation</title></head><body><script>wrong()</script><p>MADDE 1 - Sample law.</p></body></html>'
        text = extract_document_text(html, "text/html", "utf-8", "https://www.resmigazete.gov.tr/eskiler/2026/09/20260919-1.htm")
        self.assertEqual("MADDE 1 - Sample law.", text)

    def test_utf8_bytes_win_over_incorrect_legacy_charset_declaration(self):
        html = '<html><head><meta charset="Windows-1254"></head><body><p>İş Kanunu</p></body></html>'.encode("utf-8")
        text = extract_document_text(html, "text/html", None, "https://www.resmigazete.gov.tr/item.htm")
        self.assertEqual("İş Kanunu", text)

    def test_artifact_counts_final_resolved_state(self):
        record = {"document_url": "https://www.resmigazete.gov.tr/item.htm", "content_status": "text_extracted"}
        artifact = build_index_artifact(date(2026, 9, 19), [record], [b'{}'])
        self.assertEqual(1, artifact["link_resolved_count"])
        self.assertEqual(1, artifact["text_extracted_count"])


if __name__ == "__main__":
    unittest.main()
