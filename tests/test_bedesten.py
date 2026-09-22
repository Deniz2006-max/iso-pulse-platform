from __future__ import annotations

import base64
import json
import unittest

from collectors.bedesten import fetch_law, search_law
from collectors.common import CollectionError


class FakeClient:
    def __init__(self, responses: list[dict]):
        self.responses = responses

    def post_json(self, url, payload, headers):
        return json.dumps(self.responses.pop(0)).encode("utf-8")


class BedestenTests(unittest.TestCase):
    def test_exact_law_search_and_full_text(self):
        catalog = {"metadata": {"FMTY": "SUCCESS"}, "data": {"total": 1, "mevzuatList": [
            {"mevzuatId": "103054", "mevzuatNo": 4857, "mevzuatAdi": "İŞ KANUNU"}
        ]}}
        html = ("<html><body><p>MADDE 1 - " + "A real text sentence. " * 10 + "</p></body></html>").encode()
        content = {"metadata": {"FMTY": "SUCCESS"}, "data": {
            "mimeType": "text/html", "content": base64.b64encode(html).decode(), "version": 1
        }}
        client = FakeClient([catalog, content])
        row, _ = search_law("4857", client)
        record, _, source, text = fetch_law(row, client)
        self.assertEqual("103054", record["source_record_id"])
        self.assertEqual(html, source)
        self.assertIn("MADDE 1", text)
        self.assertEqual(64, len(record["normalized_sha256"]))

    def test_rejects_ambiguous_catalog(self):
        client = FakeClient([{"metadata": {"FMTY": "SUCCESS"}, "data": {"total": 2, "mevzuatList": []}}])
        with self.assertRaises(CollectionError):
            search_law("4857", client)

    def test_rejects_api_error(self):
        client = FakeClient([{"metadata": {"FMTY": "ERROR"}, "data": {}}])
        with self.assertRaises(CollectionError):
            search_law("4857", client)


if __name__ == "__main__":
    unittest.main()
