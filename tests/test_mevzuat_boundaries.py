"""Regression checks for lossless PDF-derived article re-segmentation."""

import json
import unittest
from pathlib import Path

from scripts.pdf_to_madde_json import maddelere_ayir, sha256_kisa
from scripts.repair_mevzuat_boundaries import repair


class BoundaryTests(unittest.TestCase):
    def test_parser_associates_heading_with_following_article(self):
        articles = maddelere_ayir(
            "MADDE 1 – İlk hüküm.\n \nKapsam\nMADDE 2 – İkinci hüküm."
        )
        self.assertEqual("MADDE 1 – İlk hüküm.", articles[0]["govde"])
        self.assertEqual("Kapsam", articles[1]["heading"])
        self.assertTrue(articles[1]["govde"].startswith("MADDE 2"))

    def test_migration_preserves_text_and_is_idempotent(self):
        source = ("Madde 20 – Eski hüküm.\n \nEmeklilik gözetim merkezi\n"
                  "Madde 20/A – Yeni hüküm.\n \nSonraki başlık")
        next_text = "Madde 21 – Sonraki hüküm."
        payload = {"documents": [{"document_id": "law:4632", "included_provisions": [
            {"provision_id": "law:4632:article:20", "label": "Madde 20",
             "madde_turu": "normal", "mulga": False, "text": source,
             "normalized_hash": sha256_kisa(source)},
            {"provision_id": "law:4632:article:21", "label": "Madde 21",
             "madde_turu": "normal", "mulga": False, "text": next_text,
             "normalized_hash": sha256_kisa(next_text)},
        ]}]}
        repaired, audit = repair(payload)
        rows = repaired["documents"][0]["included_provisions"]
        self.assertEqual(1, len(audit["lettered_articles_added"]))
        self.assertEqual("Emeklilik gözetim merkezi", rows[1]["heading"])
        self.assertEqual("Sonraki başlık", rows[2]["heading"])
        self.assertEqual(source, payload["documents"][0]["included_provisions"][0]["text"])
        self.assertEqual(repaired, repair(repaired)[0])

    def test_main_baselines_have_unique_ids_and_valid_hashes(self):
        root = Path(__file__).resolve().parents[1] / "data" / "mevzuat"
        for path in sorted(root.glob("*.json")):
            with self.subTest(file=path.name):
                rows = json.loads(path.read_text(encoding="utf-8"))["documents"][0]["included_provisions"]
                self.assertEqual(len(rows), len({row["provision_id"] for row in rows}))
                self.assertTrue(all(row["normalized_hash"] == sha256_kisa(row["text"])
                                    for row in rows))
        expected = {"6331_isg_kanunu.json": ("24/A", "25/A"),
                    "4632_bireysel_emeklilik.json": ("20/A",)}
        for filename, suffixes in expected.items():
            document = json.loads((root / filename).read_text(encoding="utf-8"))["documents"][0]
            ids = {row["provision_id"] for row in document["included_provisions"]}
            number = document["document_id"].split(":")[1]
            for suffix in suffixes:
                self.assertIn(f"law:{number}:article:{suffix}", ids)


if __name__ == "__main__":
    unittest.main()
