from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

from config.relevance import classify_relevance
from src.ingestion.daily_cache import DailyRevisionsCache
from src.ingestion.day_window import (
    filter_published_today,
    is_on_or_after_midnight,
    local_midnight,
    parse_publication_timestamp,
)
from src.ingestion.models import DailyUpdate
from src.ingestion.sgk_scraper import parse_listing


def _item(day: str, title: str = "ÖTV tebliğ", source: str = "resmi_gazete") -> DailyUpdate:
    return DailyUpdate(
        source=source,  # type: ignore[arg-type]
        publication_date=day,
        title=title,
        category="Tebliğ",
        url=f"https://example.test/{day}/{title}",
        raw_text="Sanayi işverenleri için vergi yükümlülüğü.",
    )


class DayWindowTests(unittest.TestCase):
    def test_midnight_is_start_of_local_day(self):
        stamp = local_midnight(date(2026, 10, 6))
        self.assertEqual(stamp.hour, 0)
        self.assertEqual(stamp.minute, 0)

    def test_date_only_counts_as_midnight(self):
        parsed = parse_publication_timestamp("2026-10-06")
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.hour, 0)
        self.assertTrue(is_on_or_after_midnight("2026-10-06", date(2026, 10, 6)))

    def test_same_day_afternoon_is_kept(self):
        self.assertTrue(is_on_or_after_midnight("2026-10-06T14:30:00", date(2026, 10, 6)))

    def test_yesterday_is_dropped(self):
        self.assertFalse(is_on_or_after_midnight("2026-10-05", date(2026, 10, 6)))
        kept = filter_published_today(
            [_item("2026-10-05"), _item("2026-10-06")],
            date(2026, 10, 6),
        )
        self.assertEqual([row.publication_date for row in kept], ["2026-10-06"])


class RelevancePrefilterTests(unittest.TestCase):
    def test_job_posting_is_dropped(self):
        verdict, _reason = classify_relevance("Açık iş ilanı", "Fabrika personel alım ilanı")
        self.assertEqual(verdict, "drop")

    def test_tender_is_dropped(self):
        verdict, _reason = classify_relevance("Mal alımı ihale ilanı", "İhale sonuç duyurusu")
        self.assertEqual(verdict, "drop")

    def test_labor_rule_is_kept(self):
        verdict, _reason = classify_relevance(
            "İş sağlığı ve güvenliği tebliği",
            "6331 sayılı kanun kapsamında işveren yükümlülüğü değişti.",
        )
        self.assertEqual(verdict, "keep")

    def test_iskolu_tespit_is_kept_for_hr(self):
        from config.relevance import implied_departments

        title = "İşkolu Tespit Kararları (No: 2026/62, 63, 64, 65, 66, 67, 68, 69)"
        verdict, _reason = classify_relevance(title, "")
        self.assertEqual(verdict, "keep")
        self.assertIn("ik", implied_departments(title, ""))

    def test_cevre_yonetmeligi_is_kept_for_legal(self):
        from config.relevance import implied_departments

        title = (
            "Çevre Yönetimi Hizmetleri Hakkında Yönetmelikte "
            "Değişiklik Yapılmasına Dair Yönetmelik"
        )
        verdict, _reason = classify_relevance(title, "")
        self.assertEqual(verdict, "keep")
        self.assertIn("hukuk", implied_departments(title, ""))

    def test_osb_incentive_is_kept_for_finance(self):
        from config.relevance import implied_departments

        title = (
            "Organize Sanayi Bölgeleri İçinde ve Dışında Açılan Özel Meslekî "
            "ve Teknik Anadolu Liselerinde Eğitim ve Öğretim Desteği Tebliği"
        )
        verdict, _reason = classify_relevance(title, "")
        self.assertEqual(verdict, "keep")
        self.assertIn("mali", implied_departments(title, ""))

    def test_personal_aym_application_is_dropped(self):
        verdict, _reason = classify_relevance(
            "Anayasa Mahkemesinin 8/1/2026 Tarihli ve 2021/56755 Başvuru Numaralı Kararı",
            "Tebliğ metni.",
        )
        self.assertEqual(verdict, "drop")

    def test_university_exam_regulation_is_dropped(self):
        verdict, _reason = classify_relevance(
            "Ankara Üniversitesi Lisansüstü Eğitim-Öğretim ve Sınav Yönetmeliği",
            "",
        )
        self.assertEqual(verdict, "drop")
        lisans, _ = classify_relevance(
            "X Üniversitesi Lisans Eğitim-Öğretim ve Sınav Yönetmeliğinde Değişiklik",
            "",
        )
        self.assertEqual(lisans, "drop")

    def test_real_estate_sale_ad_is_dropped(self):
        verdict, _reason = classify_relevance(
            "Gayrimenkul Satış İlanı",
            "Tapu müdürlüğü satış ilanı.",
        )
        self.assertEqual(verdict, "drop")

    def test_generic_yonetmelik_without_industry_signal_is_dropped(self):
        verdict, _reason = classify_relevance(
            "Bazı Yönetmeliklerde Değişiklik Yapılmasına Dair Yönetmelik",
            "",
        )
        self.assertEqual(verdict, "drop")

    def test_sgk_announcement_is_kept(self):
        from config.relevance import implied_departments

        title = "SGK e-Bildirge uygulama duyurusu"
        verdict, _reason = classify_relevance(title, "", source="sgk")
        self.assertEqual(verdict, "keep")
        self.assertIn("ik", implied_departments(title, "", "iso:sgk:1"))

    def test_tmmob_oda_ana_yonetmeligi_is_dropped(self):
        from config.executive_copy import NO_ACTION_ADMINISTRATIVE, coerce_executive_summary
        from config.relevance import is_administrative_out_of_scope

        title = (
            "Türk Mühendis ve Mimar Odaları Birliği Şehir Plancıları Odası "
            "Ana Yönetmeliğinde Değişiklik Yapılmasına Dair Yönetmelik"
        )
        text = (
            "TMMOB Şehir Plancıları Odası Ana Yönetmeliği oda organları, "
            "üyelik ve oda personel esaslarını düzenler."
        )
        verdict, reason = classify_relevance(title, text)
        self.assertEqual(verdict, "drop")
        self.assertIn("İdari Duyuru / Kapsam Dışı", reason)
        self.assertTrue(is_administrative_out_of_scope(title, text))
        card = coerce_executive_summary(
            "İK bordro takvimini güncelleyin ve işe alım ilanı yayınlayın.",
            title,
            text,
            "ik",
        )
        self.assertIn(NO_ACTION_ADMINISTRATIVE, card)
        self.assertNotIn("bordro takvimini", card)

    def test_birlik_ic_yonetmeligi_is_dropped(self):
        verdict, reason = classify_relevance(
            "Birlik İç Yönetmeliğinde Değişiklik Yapılmasına Dair Yönetmelik",
            "Birlik organlarının çalışma usulü.",
        )
        self.assertEqual(verdict, "drop")
        self.assertIn("İdari Duyuru", reason)

    def test_sgk_civil_servant_kadro_notice_is_dropped(self):
        from config.executive_copy import NO_ACTION_ADMINISTRATIVE, grounded_executive_summary
        from config.relevance import audience_scope, is_administrative_out_of_scope

        title = (
            "Sosyal Güvenlik Denetmen Yardımcısı Kadrosuna Yerleşen "
            "Adaylardan İstenen Belgeler"
        )
        verdict, reason = classify_relevance(title, "Adayların teslim edeceği belgeler.", source="sgk")
        self.assertEqual(verdict, "drop")
        self.assertIn("İdari Duyuru / Kapsam Dışı", reason)
        self.assertTrue(is_administrative_out_of_scope(title, ""))
        self.assertNotEqual(audience_scope(title, ""), "kamu")
        card = grounded_executive_summary(title, "Adayların teslim edeceği belgeler.", "ik")
        self.assertIn(NO_ACTION_ADMINISTRATIVE, card)
        self.assertNotIn("işe alım ilanı", card)
        self.assertNotIn("bordro takvimini", card)

    def test_harcirah_and_657_are_kamu_scope(self):
        from config.relevance import audience_scope

        title = "6245 Sayılı Harcırah Kanunu Genel Tebliği"
        verdict, reason = classify_relevance(title, "Memurlara ödenecek harcırah esasları.")
        self.assertEqual(verdict, "keep")
        self.assertEqual(audience_scope(title, ""), "kamu")
        self.assertIn("Kamu Kurumları", reason)
        esas = "Sözleşmeli Personel Çalıştırılmasına İlişkin Esaslarda Değişiklik"
        self.assertEqual(audience_scope(esas, "4/B kamu personeli."), "kamu")

    def test_masak_aml_is_kept_as_finance_compliance_not_kamu(self):
        from config.relevance import audience_scope, implied_departments

        title = (
            "Suç Gelirlerinin Aklanmasının ve Terörün Finansmanının Önlenmesine "
            "Dair Tedbirler Hakkında Yönetmelik"
        )
        text = (
            "MASAK yükümlüleri müşteri tanıma ve şüpheli işlem bildirimi esasları; "
            "kamu kurum ve kuruluşları da yükümlü sayılabilir."
        )
        verdict, reason = classify_relevance(title, text)
        self.assertEqual(verdict, "keep")
        self.assertNotIn("Kamu Kurumları", reason)
        self.assertNotEqual(audience_scope(title, text), "kamu")
        depts = implied_departments(title, text)
        self.assertTrue({"mali", "hukuk"} & set(depts))
        self.assertNotIn("ik", depts)

    def test_masak_card_does_not_use_kamu_no_action(self):
        from config.executive_copy import KAMU_NO_PRIVATE_ACTION, coerce_executive_summary

        title = (
            "Suç Gelirlerinin Aklanmasının ve Terörün Finansmanının Önlenmesine "
            "Dair Tedbirler Hakkında Yönetmelik"
        )
        leaked = (
            "📌 **Önemli Düzenlemeler & Maddeler**\n- Madde 1 tedbir.\n\n"
            "🏭 **Sanayi ve İşverene Etkisi**\n- Kamu kapsamı.\n\n"
            "📋 **Sorumlu Departman İçin Aksiyon Maddeleri**\n"
            f"1. {KAMU_NO_PRIVATE_ACTION}"
        )
        card = coerce_executive_summary(leaked, title, "MASAK yükümlüleri.", "mali")
        self.assertNotIn(KAMU_NO_PRIVATE_ACTION, card)
        self.assertIn("MASAK", card)

    def test_care_home_not_university_when_body_mentions_universite(self):
        title = "Engelli Bireylere Yönelik Özel Bakım Merkezleri Yönetmeliği"
        body = "Dokuz Eylül Üniversitesi Lisansüstü Eğitim ve Öğretim Yönetmeliği de yayımlandı."
        verdict, reason = classify_relevance(title, body)
        self.assertEqual(verdict, "drop")
        self.assertIn("bakımevi", reason)
        atama, atama_reason = classify_relevance(
            "Kentsel Dönüşüm Başkanlığı Personelinin Atama ve Yer Değiştirme Yönetmeliği",
            body,
        )
        self.assertEqual(atama, "drop")
        self.assertIn("İdari Duyuru", atama_reason)

    def test_corporate_tax_customs_and_ttk_are_kept(self):
        from config.relevance import implied_departments

        kv, _ = classify_relevance("Kurumlar Vergisi Genel Tebliği", "Matrah değişikliği.")
        self.assertEqual(kv, "keep")
        self.assertIn("mali", implied_departments("Kurumlar Vergisi Genel Tebliği", ""))
        ttk, _ = classify_relevance(
            "Türk Ticaret Kanunu Yönetmeliğinde Değişiklik",
            "6102 sayılı Kanun kapsamında sicil.",
        )
        self.assertEqual(ttk, "keep")
        self.assertIn("hukuk", implied_departments("Türk Ticaret Kanunu", "6102"))

    def test_kamulas_and_care_home_remain_dropped(self):
        parcel, reason = classify_relevance(
            "Acele Kamulaştırma Kararı",
            "Parselinin kamulaştırılması hakkında ekli kroki.",
        )
        self.assertEqual(parcel, "drop")
        self.assertIn("kamulaştır", reason)
        home, _ = classify_relevance(
            "Engelli Bakım ve Rehabilitasyon Merkezi Yönetmeliği",
            "Bakımevi personel esasları.",
        )
        self.assertEqual(home, "drop")

    def test_nuclear_facility_rule_is_specialized_low_scope(self):
        from config.relevance import is_specialized_sector_scope, specialized_subsector_label

        title = "Nükleer Güç Santrali İşletme Lisansı Hakkında Yönetmelik"
        text = "Akkuyu nükleer tesis işleticisine lisans şartı getirilmiştir."
        verdict, reason = classify_relevance(title, text)
        self.assertEqual(verdict, "keep")
        self.assertTrue(is_specialized_sector_scope(title, text))
        self.assertIn("Özel Sektör Kapsamı", reason)
        self.assertIn("nükleer", specialized_subsector_label(title, text))

    def test_noterlik_and_aviation_are_specialized_not_general_industry(self):
        from config.relevance import audience_scope, specialized_subsector_label

        noter = "Noterlik Kanunu Yönetmeliğinde Değişiklik Yapılmasına Dair Yönetmelik"
        self.assertEqual(audience_scope(noter, "Teminat Ziraat Bankası."), "specialized")
        self.assertEqual(specialized_subsector_label(noter, ""), "noterlik")
        air = "Uydu ve Yer Tabanlı Radyo Seyrüsefer Sistemleri Uçuş Kontrol Yönetmeliği"
        self.assertEqual(audience_scope(air, ""), "specialized")
        self.assertEqual(specialized_subsector_label(air, ""), "sivil havacılık")

    def test_kept_item_always_has_a_department(self):
        from config.relevance import implied_departments

        depts = implied_departments("Resmî Gazete sayısı 33392", "Yayımlanmıştır.")
        self.assertTrue(depts)
        self.assertTrue(set(depts) <= {"ik", "hukuk", "mali"})


class DailyCacheTests(unittest.TestCase):
    def test_store_and_warm_hit(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DailyRevisionsCache(Path(tmp) / "daily_revisions_cache.sqlite")
            status = store.status("2026-10-06", "all")
            self.assertFalse(status.warm)
            stored = store.store_run(
                "2026-10-06",
                "all",
                [
                    {
                        "document_id": "iso:rg:1",
                        "title": "ÖTV",
                        "is_relevant": True,
                        "url": "https://example.test/1",
                    }
                ],
            )
            self.assertTrue(stored.warm)
            self.assertEqual(stored.relevant_count, 1)
            again = store.status("2026-10-06", "all")
            self.assertTrue(again.warm)
            rows = store.load_records("2026-10-06", "all")
            self.assertEqual(rows[0]["title"], "ÖTV")

    def test_drop_day_clears_warm_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DailyRevisionsCache(Path(tmp) / "daily_revisions_cache.sqlite")
            store.store_run(
                "2026-10-05",
                "all",
                [{"document_id": "iso:1", "title": "old", "is_relevant": True}],
            )
            self.assertTrue(store.status("2026-10-05", "all").warm)
            store.drop_day("2026-10-05")
            self.assertFalse(store.status("2026-10-05", "all").warm)
            self.assertEqual(store.load_records("2026-10-05", "all"), [])

    def test_zero_relevant_complete_run_is_warm_for_raw_feed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = DailyRevisionsCache(Path(tmp) / "daily_revisions_cache.sqlite")
            stored = store.store_run(
                "2026-10-06",
                "all",
                [{"document_id": "iso:1", "title": "empty", "is_relevant": False}],
            )
            self.assertEqual(stored.relevant_count, 0)
            again = store.status("2026-10-06", "all")
            self.assertTrue(again.warm)
            self.assertEqual(again.relevant_count, 0)

    def test_ensure_today_skips_scrape_when_warm(self):
        from unittest.mock import patch

        from src.ingestion import daily_pipeline as pipeline

        with tempfile.TemporaryDirectory() as tmp:
            store = DailyRevisionsCache(Path(tmp) / "daily_revisions_cache.sqlite")
            store.store_run(
                "2026-10-06",
                "all",
                [{"document_id": "iso:1", "title": "cached", "is_relevant": True}],
            )
            with patch.object(pipeline, "_run_fetch", return_value=0) as fetch, \
                 patch.object(pipeline, "_run_pipeline", return_value=0) as analyse, \
                 patch.object(pipeline, "restore_reports"):
                result = pipeline.ensure_today(
                    "2026-10-06", "all", cache=store, force=False
                )
            fetch.assert_not_called()
            analyse.assert_not_called()
            self.assertTrue(result.cache_hit)
            self.assertEqual(result.records[0]["title"], "cached")

    def test_ensure_today_serves_zero_relevant_cache_for_raw_view(self):
        from unittest.mock import patch

        from src.ingestion import daily_pipeline as pipeline

        with tempfile.TemporaryDirectory() as tmp:
            store = DailyRevisionsCache(Path(tmp) / "daily_revisions_cache.sqlite")
            store.store_run(
                "2026-10-05",
                "all",
                [{"document_id": "iso:1", "title": "üniversite", "is_relevant": False}],
            )
            with patch.object(pipeline, "_run_fetch", return_value=0) as fetch, \
                 patch.object(pipeline, "_run_pipeline", return_value=0) as analyse, \
                 patch.object(pipeline, "restore_reports"):
                result = pipeline.ensure_today(
                    "2026-10-05", "all", cache=store, force=False
                )
            fetch.assert_not_called()
            analyse.assert_not_called()
            self.assertTrue(result.cache_hit)
            self.assertEqual(result.relevant_count, 0)


class SgkListingDayFilterTests(unittest.TestCase):
    HTML = """
    <a class="announcement-card" href="/duyuru/detay/old-2026-10-05">
      <span class="announcement-title">Dünkü duyuru</span>
      <span class="date-day">5</span><span class="date-month">Ekim</span>
      <span class="date-year">2026</span>
    </a>
    <a class="announcement-card" href="/duyuru/detay/today-2026-10-06">
      <span class="announcement-title">Bugünkü genelge</span>
      <span class="date-day">6</span><span class="date-month">Ekim</span>
      <span class="date-year">2026</span>
    </a>
    """

    def test_keeps_only_requested_calendar_day(self):
        rows = parse_listing(
            self.HTML,
            "https://www.sgk.gov.tr/duyuru/",
            limit=10,
            published_on=date(2026, 10, 6),
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["publication_date"], "2026-10-06")
        self.assertIn("Bugünkü", rows[0]["title"])


if __name__ == "__main__":
    unittest.main()
