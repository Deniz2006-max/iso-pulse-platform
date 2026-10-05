"""Exercise the ingestion runner and persisted reports with controlled source responses."""

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from src.ingestion import fetch_daily_updates as runner
from src.ingestion.models import DailyUpdate
from src.ingestion.resmi_gazete import _fetch_full_pdf_fallback


class DailyTrackingIntegrationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.args = runner.parse_args([
            "--source", "all", "--date", "2026-10-05",
            "--out-dir", str(self.root), "--max-items", "1",
        ])

    def report(self, name="change_report.json"):
        return json.loads((self.root / self.args.date / name).read_text(encoding="utf-8"))

    def record(self, source, text="Synthetic test text"):
        return DailyUpdate(source=source, title="Test fixture", category="Duyuru",
                           publication_date=self.args.date,
                           url=f"https://example.test/{source}/1", raw_text=text)

    async def collect(self, rg, sgk):
        with patch.object(runner, "FetchClient", return_value=AsyncMock()), \
             patch.object(runner, "fetch_edition", new=rg), \
             patch.object(runner, "fetch_announcements", new=sgk), \
             patch.object(runner, "fetch_mevzuat", new=AsyncMock(return_value=[])):
            return await runner.run(self.args)

    async def test_persisted_comparison_and_legacy_payload(self):
        rg = AsyncMock(return_value=[self.record("resmi_gazete")])
        sgk = AsyncMock(return_value=[self.record("sgk")])
        self.assertEqual(await self.collect(rg, sgk), 0)
        self.assertEqual(self.report()["counts"]["new"], 2)
        payload = self.report("all.json")
        self.assertEqual(len(payload), 2)
        self.assertNotIn("change_status", payload[0])

        sgk.return_value = [self.record("sgk", "Changed synthetic test text")]
        self.assertEqual(await self.collect(rg, sgk), 0)
        changed = next(row for row in self.report()["items"] if row["source"] == "sgk")
        self.assertEqual(changed["change_status"], "changed")
        self.assertNotEqual(changed["content_sha256"], changed["previous_content_sha256"])

    async def test_failed_rg_is_visible_and_sgk_is_retained(self):
        # An earlier successful run's derived file must not survive a failed rerun.
        folder = self.root / self.args.date
        folder.mkdir()
        (folder / "mevzuat.json").write_text('[{"old": true}]', encoding="utf-8")
        result = await self.collect(
            AsyncMock(side_effect=httpx.ConnectError("Synthetic connection failure")),
            AsyncMock(return_value=[self.record("sgk")]),
        )
        self.assertEqual(result, 1)
        collection = self.report()["collection"]
        self.assertIn("resmi_gazete", collection["failed_sources"])
        self.assertIn("mevzuat", collection["failed_sources"])
        self.assertTrue(collection["partial"])
        self.assertEqual(self.report("mevzuat.json"), [])
        self.assertEqual(self.report("all.json")[0]["source"], "sgk")

    async def test_empty_collection_does_not_claim_confirmed_coverage(self):
        await self.collect(AsyncMock(return_value=[]), AsyncMock(return_value=[]))
        collection = self.report()["collection"]
        self.assertEqual(collection["unconfirmed_sources"], ["resmi_gazete", "sgk"])
        self.assertTrue(collection["partial"])

    async def test_rg_pdf_fallback_propagates_failure(self):
        client = AsyncMock()
        client.get_bytes.side_effect = httpx.ConnectError("Synthetic failure")
        with self.assertRaises(httpx.ConnectError):
            await _fetch_full_pdf_fallback(client, date(2026, 10, 5))
        client.get_bytes.side_effect = None
        client.get_bytes.return_value = (b"Unavailable", "text/html", 503)
        with self.assertRaises(RuntimeError):
            await _fetch_full_pdf_fallback(client, date(2026, 10, 5))
