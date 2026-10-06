from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class LoadItemsTests(unittest.TestCase):
    def test_prefers_items_json_and_drops_synthetic_demo_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            day = "2026-10-06"
            folder = Path(tmp) / day
            items_dir = folder / "items"
            items_dir.mkdir(parents=True)
            (folder / "items.json").write_text(
                json.dumps(
                    [
                        {
                            "document_id": "iso:resmi_gazete:abc",
                            "title": "Resmî Gazete tebliğ",
                            "is_relevant": True,
                        },
                        {
                            "document_id": "ik-overtime",
                            "title": "Fazla çalışma süresi üst sınırının güncellenmesi",
                            "is_relevant": True,
                        },
                    ]
                ),
                encoding="utf-8",
            )
            (items_dir / "otv-rate.json").write_text(
                json.dumps(
                    {
                        "document_id": "otv-rate",
                        "title": "Özel Tüketim Vergisi (ÖTV) oranının güncellenmesi",
                        "is_relevant": True,
                    }
                ),
                encoding="utf-8",
            )
            with (
                patch.object(app, "REPORTS_ROOT", Path(tmp)),
                patch.object(app, "load_cached_analysis", return_value=None),
            ):
                rows = app.load_items(day)
        self.assertEqual([row["document_id"] for row in rows], ["iso:resmi_gazete:abc"])


class MetricCountsTests(unittest.TestCase):
    def test_passed_items_are_not_zeroed_without_rag(self) -> None:
        from src.ingestion.records import metric_counts

        rows = [
            {
                "document_id": "iso:1",
                "title": "Çevre Yönetimi Hizmetleri Hakkında Yönetmelik",
                "is_relevant": True,
                "departments": ["hukuk"],
                "delivery": {"summary": "Çevre uyum yükümlülüğü değişti.", "urgency": "medium"},
            },
            {
                "document_id": "iso:2",
                "title": "İşkolu Tespit Kararları",
                "is_relevant": True,
                "departments": ["ik"],
                "rag_status": "fallback",
            },
            {
                "document_id": "iso:3",
                "title": "Başvuru Numaralı Kararı",
                "is_relevant": False,
            },
        ]
        examined, passed, mapped = metric_counts(rows)
        self.assertEqual(examined, 3)
        self.assertEqual(passed, 2)
        self.assertEqual(mapped, 2)

    def test_zero_relevant_json_keeps_raw_rows_without_executive_cards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            day = "2026-10-05"
            folder = Path(tmp) / day
            folder.mkdir()
            rows = [
                {
                    "document_id": f"iso:{i}",
                    "title": f"Üniversite yönetmeliği {i}",
                    "is_relevant": False,
                }
                for i in range(7)
            ]
            (folder / "items.json").write_text(json.dumps(rows), encoding="utf-8")
            with (
                patch.object(app, "REPORTS_ROOT", Path(tmp)),
                patch.object(app, "load_cached_analysis", return_value=None),
            ):
                loaded = app.load_items(day)
                self.assertEqual(len(loaded), 7)
                self.assertEqual(app.passed_records(loaded), [])
                self.assertTrue(app.analysis_complete(day))
                self.assertEqual(app.INDUSTRY_EMPTY_NOTICE[:20], "Seçilen tarihte sana")


class DatePickerAnalysisTests(unittest.TestCase):
    def test_button_label_uses_selected_date(self) -> None:
        self.assertEqual(
            app.analysis_button_label("2026-10-01"),
            "🔍 01.10.2026 Mevzuatını Analiz Et",
        )
        self.assertEqual(
            app.analysis_button_label("2026-10-05"),
            "🔍 05.10.2026 Mevzuatını Analiz Et",
        )

    def test_warm_cache_skips_live_scrape(self) -> None:
        cached = [{"document_id": "iso:1", "title": "cached", "is_relevant": True}]
        with (
            patch.object(app, "load_cached_analysis", return_value=cached),
            patch.object(app, "run_command") as run,
            patch.object(app, "openai_key_configured", return_value=False),
        ):
            ok, reason = app.run_daily_analysis("2026-10-01")
        self.assertTrue(ok)
        self.assertEqual(reason, "ready")
        run.assert_not_called()

    def test_cache_miss_scrapes_selected_date_without_refresh(self) -> None:
        with (
            patch.object(app, "load_cached_analysis", return_value=None),
            patch.object(app, "openai_key_configured", return_value=True),
            patch.object(app, "purge_synthetic_reports"),
            patch.object(app, "run_command", return_value=0) as run,
        ):
            ok, reason = app.run_daily_analysis("2026-10-05")
        self.assertTrue(ok)
        self.assertEqual(reason, "fresh")
        cmd = run.call_args[0][0]
        self.assertEqual(cmd[1:3], ["-m", "src.ingestion.daily_pipeline"])
        self.assertEqual(cmd[cmd.index("--date") + 1], "2026-10-05")
        self.assertIn("--refresh", cmd)
        self.assertEqual(run.call_args.kwargs["env"]["ISO_PULSE_USE_MOCK_LLM"], "false")

    def test_missing_analysis_is_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(app, "REPORTS_ROOT", Path(tmp)),
                patch("app.DailyRevisionsCache") as cache_cls,
            ):
                cache_cls.return_value.status.return_value.warm = False
                self.assertFalse(app.analysis_ready("2026-10-06"))

    def test_empty_cached_analysis_is_complete_and_skips_scrape(self):
        with (
            patch.object(app, "load_cached_analysis", return_value=[]),
            patch.object(app, "openai_key_configured", return_value=True),
            patch.object(app, "run_command") as run,
        ):
            ok, reason = app.run_daily_analysis("2026-10-05")
        self.assertTrue(ok)
        self.assertEqual(reason, "ready")
        run.assert_not_called()

    def test_missing_openai_key_blocks_live_run_only(self) -> None:
        with (
            patch.object(app, "load_cached_analysis", return_value=None),
            patch.object(app, "openai_key_configured", return_value=False),
            patch.object(app, "run_command") as run,
        ):
            ok, reason = app.run_daily_analysis("2026-10-05")
        self.assertFalse(ok)
        self.assertEqual(reason, "key")
        run.assert_not_called()


class DualViewTests(unittest.TestCase):
    def test_executive_view_hides_noise_and_keeps_industry_titles(self) -> None:
        from config.relevance import classify_relevance

        noise = [
            "Ankara Üniversitesi Lisansüstü Eğitim-Öğretim ve Sınav Yönetmeliği",
            "Gayrimenkul Satış İlanı",
            "Anayasa Mahkemesinin 2021/1 Başvuru Numaralı Kararı",
            "TMMOB Şehir Plancıları Odası Ana Yönetmeliği",
            "Sosyal Güvenlik Denetmen Yardımcısı Kadrosuna Yerleşen Adaylardan İstenen Belgeler",
            "Kamu Personeli Alımı",
        ]
        kept = [
            "Çevre Yönetimi Hizmetleri Hakkında Yönetmelik",
            "İşkolu Tespit Kararları",
            "Organize Sanayi Bölgeleri Eğitim ve Öğretim Desteği Tebliği",
            "Suç Gelirlerinin Aklanmasının ve Terörün Finansmanının Önlenmesine Dair Tedbirler Hakkında Yönetmelik",
        ]
        for title in noise:
            self.assertEqual(classify_relevance(title, "")[0], "drop")
        for title in kept:
            self.assertEqual(classify_relevance(title, "")[0], "keep")

    def test_raw_publications_loader_returns_all_scraped_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            day = "2026-10-05"
            folder = Path(tmp) / day
            folder.mkdir()
            payload = [
                {"title": f"Yayın {i}", "url": f"https://example.test/{i}"}
                for i in range(7)
            ]
            (folder / "all.json").write_text(json.dumps(payload), encoding="utf-8")
            with patch.object(app, "UPDATES_ROOT", Path(tmp)):
                rows = app.load_raw_publications(day)
            self.assertEqual(len(rows), 7)

    def test_oct6_industry_titles_map_to_units(self) -> None:
        from config.relevance import implied_departments

        self.assertIn(
            "hukuk",
            implied_departments("Çevre Yönetimi Hizmetleri Hakkında Yönetmelik", ""),
        )
        self.assertIn("ik", implied_departments("İşkolu Tespit Kararları", ""))
        self.assertIn(
            "mali",
            implied_departments(
                "Organize Sanayi Bölgeleri Eğitim ve Öğretim Desteği Tebliği",
                "",
            ),
        )


class ExecutiveCopyTests(unittest.TestCase):
    def test_generic_placeholders_are_rejected(self) -> None:
        from config.executive_copy import is_generic_executive_copy

        self.assertTrue(
            is_generic_executive_copy(
                "Çevre Yönetimi sanayi işverenini ilgilendiren resmi bir düzenlemedir. "
                "Hukuk birimi metni inceleyip uyum adımlarını belirlemelidir."
            )
        )
        self.assertTrue(
            is_generic_executive_copy("İlgili departman metni incelemelidir.")
        )

    def test_title_only_yururluge_line_is_high_level(self) -> None:
        from config.executive_copy import is_high_level_summary

        title = "Ulusal Meslek Standartları Tebliği"
        self.assertTrue(
            is_high_level_summary(
                "Ulusal Meslek Standartları Tebliği yürürlüğe konulmuştur",
                title,
            )
        )

    def test_grounded_summary_has_three_executive_sections(self) -> None:
        from config.executive_copy import (
            has_executive_structure,
            grounded_executive_summary,
        )

        text = grounded_executive_summary(
            "İşkolu Tespit Kararları (No: 2026/62)",
            "6356 sayılı Kanun uyarınca işkolu tespiti yayımlanmıştır. "
            "Yetkili işçi sendikası bu işyerinde TİS yetkisi kazanabilir.",
            "ik",
        )
        self.assertTrue(has_executive_structure(text))
        self.assertIn("Önemli Düzenlemeler", text)
        self.assertIn("Sanayi ve İşverene Etkisi", text)
        self.assertIn("Aksiyon Maddeleri", text)
        self.assertNotIn("sanayi işverenini ilgilendiren resmi bir düzenlemedir", text)
        self.assertIn("sendika", text.casefold())

    def test_coerce_wraps_detailed_copy_into_sections(self) -> None:
        from config.executive_copy import coerce_executive_summary, has_executive_structure

        wrapped = coerce_executive_summary(
            "Yıllık fazla çalışma tavanı 270 saatten 360 saate çıkar. "
            "SGK bildirimi ayın 10'una kadar verilir.",
            "Fazla çalışma süresi",
            "Yıllık fazla çalışma tavanı 360 saattir.",
            "ik",
        )
        self.assertTrue(has_executive_structure(wrapped))
        self.assertIn("360", wrapped)

    def test_invented_year_is_stripped_from_model_copy(self) -> None:
        from config.executive_copy import coerce_executive_summary

        source = (
            "Nükleer tesis işletme lisansı 2 Ekim 2026 tarihinde yürürlüğe girer. "
            " MADDE 1 işleticiye bildirim yükümlülüğü getirir."
        )
        hallucinated = (
            "📌 **Önemli Düzenlemeler & Maddeler**\n"
            "- İşletme lisansı 2023 yılında yeniden belirlendi.\n"
            "- 2 Ekim 2026 tarihinde yürürlüğe girer.\n\n"
            "🏭 **Sanayi ve İşverene Etkisi**\n"
            "- Yalnızca nükleer tesis işleticisi muhataptır.\n\n"
            "📋 **Sorumlu Departman İçin Aksiyon Maddeleri**\n"
            "1. Tesis lisansını 2 Ekim 2026 takvimine işleyin."
        )
        text = coerce_executive_summary(
            hallucinated,
            "Nükleer Güç Santrali İşletme Lisansı",
            source,
            "hukuk",
        )
        self.assertNotIn("2023", text)
        self.assertIn("2026", text)

    def test_specialized_copy_does_not_issue_general_hr_steps(self) -> None:
        from config.executive_copy import grounded_executive_summary

        text = grounded_executive_summary(
            "Nükleer Güç Santrali İşletme Lisansı",
            "Akkuyu nükleer tesis işleticisine lisans şartı. 2 Ekim 2026 yürürlük.",
            "ik",
        )
        self.assertIn("nükleer", text.casefold())
        self.assertIn("imalat", text.casefold())
        self.assertNotIn("e-bildirge", text.casefold())


class ObligationCaptionTests(unittest.TestCase):
    def test_ozet_degisiklik_caption_is_treated_as_duplicate(self) -> None:
        self.assertTrue(
            app._obligation_duplicates_summary(
                "Özet & Değişiklik: İşkolu tespiti yayımlanmıştır.",
                "• Konu: İşkolu tespiti yayımlanmıştır.",
            )
        )

    def test_unique_eski_yeni_caption_is_kept(self) -> None:
        self.assertFalse(
            app._obligation_duplicates_summary(
                "Eski durum: 30 gün. Yeni durum: 45 gün.",
                "• Konu: Süre değişti.",
                "Birim Aksiyonu (İK): Takvimi güncelleyin.",
            )
        )


if __name__ == "__main__":
    unittest.main()
