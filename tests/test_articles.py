from __future__ import annotations

import unittest

from collectors.articles import compare_articles, extract_articles


def law_text(article_two: str = "Second text.", *, add_article: bool = False) -> str:
    text = """TEST KANUNU
Madde
1 - First text.
Madde 2 - """ + article_two + """
Madde 3 - Third text.
Madde 4 - Fourth text.
Madde 5 - Fifth text.
Geçici
Madde 1 - Temporary text.
"""
    if add_article:
        text += "Ek Madde 1 - Added text.\n"
    text += """1234 SAYILI KANUNA EK VE DEĞİŞİKLİK
GETİREN MEVZUATIN YÜRÜRLÜĞE GİRİŞ TARİHLERİ
Madde 99 - This is an appendix reference, not an article.
"""
    return text


class ArticleTests(unittest.TestCase):
    def test_extracts_article_blocks_and_stops_before_appendix(self):
        snapshot = extract_articles("1234", law_text())
        self.assertEqual("trusted", snapshot["status"])
        self.assertEqual(6, snapshot["article_count"])
        self.assertEqual("law:1234:article:1", snapshot["articles"][0]["article_id"])
        self.assertEqual("law:1234:gecici-madde:1", snapshot["articles"][-1]["article_id"])
        self.assertNotIn("appendix", snapshot["articles"][-1]["text"])

    def test_diff_reports_only_changed_or_added_articles_with_evidence(self):
        old = extract_articles("1234", law_text())
        new = extract_articles("1234", law_text("Corrected text.", add_article=True))
        diff = compare_articles(old, new)
        self.assertEqual("compared", diff["status"])
        self.assertEqual({"added": 1, "removed": 0, "changed": 1, "unchanged": 5}, diff["counts"])
        changed = next(item for item in diff["changes"] if item["article_id"] == "law:1234:article:2")
        self.assertIn("Second text", changed["old_text"])
        self.assertIn("Corrected text", changed["new_text"])
        self.assertEqual("baseline_created", compare_articles(None, old)["status"])

    def test_ambiguous_duplicate_or_missing_appendix_requires_review(self):
        duplicated = law_text().replace("Madde 5 - Fifth text.", "Madde 4 - Duplicate.\nMadde 5 - Fifth text.")
        old = extract_articles("1234", duplicated)
        self.assertEqual("review_required", old["status"])
        self.assertTrue(any(warning.startswith("duplicate_article_id") for warning in old["warnings"]))
        self.assertEqual("review_required", compare_articles(old, extract_articles("1234", law_text()))["status"])
        self.assertEqual("review_required", extract_articles("1234", law_text().split("1234 SAYILI")[0])["status"])

    def test_layout_whitespace_does_not_change_article_hash(self):
        old = extract_articles("1234", law_text("Second text."))
        new = extract_articles("1234", law_text("Second\ntext."))
        self.assertEqual(6, compare_articles(old, new)["counts"]["unchanged"])
        self.assertEqual("non_article_text_changed", compare_articles(old, new)["status"])

    def test_appendix_change_is_not_misreported_as_article_change(self):
        old = extract_articles("1234", law_text())
        new = extract_articles("1234", law_text().replace("appendix reference", "corrected appendix reference"))
        diff = compare_articles(old, new)
        self.assertEqual("non_article_text_changed", diff["status"])
        self.assertEqual(0, len(diff["changes"]))
        self.assertIn("appendix_changed_outside_article_blocks", diff["warnings"])


if __name__ == "__main__":
    unittest.main()
