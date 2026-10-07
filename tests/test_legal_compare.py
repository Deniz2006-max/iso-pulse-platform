from __future__ import annotations

from unittest.mock import patch

from src.ingestion.legal_compare import (
    COMPARISON_SIMILARITY_THRESHOLD,
    FALLBACK_OLD_TEXT,
    PROCEDURAL_NOTICE,
    build_legal_comparisons,
    clean_new_text,
    comparison_query,
    domains_conflict,
    extract_target_article,
    highlight_pair,
    hit_passes_comparison_gate,
    is_valid_article_label,
    legislation_domain,
)
from nodes.retriever import retriever_node


GAZETTE_NEW = """
Resmî Gazete
Sayı: 33012
7/10/2026
YÖNETMELİK

MADDE 1 – 27/11/2014 tarihli ve 29118 sayılı Yönetmeliğin 5 inci maddesinin
ikinci fıkrası aşağıdaki şekilde değiştirilmiştir.

"(2) Yükümlüler şüpheli işlem bildirimini MASAK'a beş iş günü içinde yapar."

MADDE 2 – Bu Yönetmelik yayımı tarihinde yürürlüğe girer.

MADDE 3 – Bu Yönetmelik hükümlerini Cumhurbaşkanı yürütür.

Recep Tayyip ERDOĞAN
CUMHURBAŞKANI
"""

MASAK_TITLE = (
    "Suç Gelirlerinin Aklanmasının Önlenmesi Hakkında Yönetmelikte "
    "Değişiklik Yapılmasına Dair Yönetmelik"
)

MASAK_HIT = {
    "chunk_id": "law:5549:article:5",
    "document_id": "law:5549",
    "title": "Suç Gelirlerinin Aklanmasının Önlenmesi Hakkında Yönetmelik",
    "article": "Madde 5",
    "text": (
        "(2) Yükümlüler şüpheli işlem bildirimini MASAK'a on iş günü içinde yapar."
    ),
    "similarity": 0.91,
}

SGK_HIT = {
    "chunk_id": "law:5510:article:5",
    "document_id": "law:5510",
    "title": "Sosyal Sigortalar ve Genel Sağlık Sigortası Kanunu",
    "article": "Madde 5",
    "text": (
        "Sigortalı sayılanlar ile işverenin Kuruma bildirim yükümlülüğü. "
        "Yükümlüler şüpheli işlem bildirimini beş iş günü içinde Kuruma yapar. "
        "5510 sayılı Kanun hükümlerine göre belirlenir."
    ),
    "similarity": 0.99,
}


def test_clean_new_text_strips_gazette_chrome_and_execution_articles():
    cleaned = clean_new_text(GAZETTE_NEW)
    folded = cleaned.casefold()
    assert "MADDE 1" in cleaned
    assert "5 inci maddesinin" in cleaned
    assert "MASAK" in cleaned
    assert "33012" not in cleaned
    assert "ERDOĞAN" not in cleaned.upper().replace("Ğ", "G")
    assert "erdoğan" not in folded
    assert "cumhurbaşkanı" not in folded
    assert "yayımı tarihinde yürürlüğe" not in folded
    assert "hükümlerini" not in folded


def test_extract_target_article_uses_amended_provision_not_madde_1():
    assert extract_target_article(clean_new_text(GAZETTE_NEW)) == "Madde 5"


def test_masak_never_matches_sgk_even_at_perfect_similarity():
    assert legislation_domain(MASAK_TITLE, GAZETTE_NEW) == "finance_aml"
    assert legislation_domain(
        SGK_HIT["title"], SGK_HIT["text"], document_id=SGK_HIT["document_id"]
    ) == "sgk_social"
    assert domains_conflict("finance_aml", "sgk_social")
    assert not hit_passes_comparison_gate(
        MASAK_TITLE, GAZETTE_NEW, SGK_HIT, source="resmi_gazete"
    )
    rows = build_legal_comparisons(
        title=MASAK_TITLE,
        new_text=GAZETTE_NEW,
        hits=[SGK_HIT],
        source="resmi_gazete",
    )
    assert rows[0]["has_exact_old_match"] is False
    assert rows[0]["old_text_clean"] == FALLBACK_OLD_TEXT
    assert "MASAK" in rows[0]["new_text_clean"]
    assert "ERDOĞAN" not in rows[0]["new_text_clean"]


def test_sgk_never_matches_masak_hit():
    sgk_new = (
        "MADDE 1 – 5510 sayılı Kanunun 5 inci maddesi aşağıdaki şekilde "
        "değiştirilmiştir.\nSigortalı bildirim süresi on beş gündür."
    )
    assert not hit_passes_comparison_gate(
        "SGK Genelge 2026/12",
        sgk_new,
        MASAK_HIT,
        source="sgk",
        document_id="iso:sgk:x",
    )


def test_below_0_85_does_not_guess_old_text():
    weak = {**MASAK_HIT, "similarity": 0.84}
    assert 0.84 < COMPARISON_SIMILARITY_THRESHOLD
    assert not hit_passes_comparison_gate(MASAK_TITLE, GAZETTE_NEW, weak)
    rows = build_legal_comparisons(
        title=MASAK_TITLE, new_text=GAZETTE_NEW, hits=[weak]
    )
    assert rows[0]["has_exact_old_match"] is False
    assert rows[0]["old_text_clean"] == FALLBACK_OLD_TEXT


def test_exact_same_domain_article_match_at_0_85():
    hit = {**MASAK_HIT, "similarity": 0.85}
    assert hit_passes_comparison_gate(MASAK_TITLE, GAZETTE_NEW, hit)
    rows = build_legal_comparisons(
        title=MASAK_TITLE, new_text=GAZETTE_NEW, hits=[hit]
    )
    payload = rows[0]
    assert payload["has_exact_old_match"] is True
    assert payload["article_no"] == "Madde 5"
    assert payload["old_text_clean"] == MASAK_HIT["text"]
    assert set(payload) >= {
        "article_no",
        "old_text_clean",
        "new_text_clean",
        "change_summary",
        "has_exact_old_match",
    }
    assert "yayımı tarihinde" not in payload["new_text_clean"].casefold()
    assert "+ " in payload["new_text_html"]
    assert "mark" in payload["new_text_html"]
    assert "- " in payload["old_text_html"]
    assert "del" in payload["old_text_html"]


def test_wrong_article_number_is_rejected():
    hit = {**MASAK_HIT, "chunk_id": "law:5549:article:12", "article": "Madde 12"}
    assert not hit_passes_comparison_gate(MASAK_TITLE, GAZETTE_NEW, hit)


def test_highlight_wraps_added_and_removed_spans():
    old_html, new_html = highlight_pair(
        "Bildirim on iş günü içinde yapılır.",
        "Bildirim beş iş günü içinde yapılır.",
    )
    assert '<del style="background:#f8d7da; color:#721c24;">- on</del>' in old_html
    assert '<mark style="background:#d4edda; color:#155724;">+ beş</mark>' in new_html
    assert "Bildirim" in old_html and "Bildirim" in new_html


def test_full_rewrite_emits_two_bullet_summary():
    hit = {
        **MASAK_HIT,
        "text": (
            "Eski fıkra: yükümlülük yalnızca nakit işlemler için geçerlidir "
            "ve bildirim yapılmaz."
        ),
        "similarity": 0.90,
    }
    rows = build_legal_comparisons(
        title=MASAK_TITLE, new_text=GAZETTE_NEW, hits=[hit]
    )
    summary = rows[0]["change_summary"]
    assert rows[0]["is_rewrite"] is True
    assert "🟢 **Ne Eklendi/Değişti:**" in summary
    assert "🔴 **Ne Yürürlükten Kalktı:**" in summary


def test_chrome_only_gazette_does_not_keep_issue_dates():
    chrome = (
        "YÖNETMELİK\n"
        "Karar Sayısı: 11845\n"
        "6 Ekim 2026\n"
        "Recep Tayyip ERDOĞAN\n"
        "CUMHURBAŞKANI\n"
        "7 Ekim 2026 ÇARŞAMBA Resmî Gazete Sayı : 33393\n"
    )
    assert clean_new_text(chrome) == ""
    rows = build_legal_comparisons(title=MASAK_TITLE, new_text=chrome, hits=[SGK_HIT])
    assert rows[0]["has_exact_old_match"] is False
    assert rows[0]["old_text_clean"] == FALLBACK_OLD_TEXT
    assert "33393" not in rows[0]["new_text_clean"]
    assert "ERDOĞAN" not in rows[0]["new_text_clean"]


def test_sgk_execution_article_is_not_a_masak_match():
    hit = {
        "chunk_id": "law:13973:article:127",
        "document_id": "law:13973",
        "title": "Sosyal Güvenlik Kurumu Teşkilatı Yönetmeliği",
        "article": "Madde 127",
        "text": "Bu Yönetmelik hükümlerini Sosyal Güvenlik Kurumu Başkanı yürütür.",
        "similarity": 0.99,
    }
    assert legislation_domain(hit["title"], hit["text"], document_id=hit["document_id"]) == "sgk_social"
    assert not hit_passes_comparison_gate(MASAK_TITLE, GAZETTE_NEW, hit)


def test_retriever_drops_sgk_hit_for_masak_query():
    state = {
        "title": MASAK_TITLE,
        "new_text": GAZETTE_NEW,
        "old_text": None,
        "diff": "",
        "source": "resmi_gazete",
        "document_id": "iso:test-masak",
        "baseline_document_ids": [],
    }
    with patch("nodes.retriever.retriever.query_baseline", return_value=[SGK_HIT]):
        out = retriever_node(state)
    assert out["rag_mode"] == "fallback"
    assert not out["old_text"]
    assert not out["retrieved_chunks"]
    assert out["legal_comparisons"][0]["has_exact_old_match"] is False
    assert out["legal_comparisons"][0]["old_text_clean"] == FALLBACK_OLD_TEXT


RES_AMENDING = """
3 Ekim 2026 CUMARTESİ
Resmî Gazete
Sayı : 33389
YÖNETMELİK
Enerji ve Tabii Kaynaklar Bakanlığından:
RÜZGAR KAYNAĞINA DAYALI ELEKTRİK ÜRETİMİ
MADDE 1- 20/10/2015 tarihli ve 29508 sayılı Resmî Gazete’de
 yayımlanan Rüzgar Kaynağına Dayalı Elektrik Üretimi Başvurularının Teknik
 Değerlendirmesi Hakkında Yönetmeliğin 3 üncü maddesinin birinci fıkrasının
 (a) bendi aşağıdaki şekilde değiştirilmiştir.

“a) Bağdaşmaz alan: YEKA alanlarını,”

MADDE 2- Aynı Yönetmeliğin 4 üncü maddesinin ikinci
 fıkrasının (a) bendi aşağıdaki şekilde değiştirilmiştir.

“a) EK-3’te yer alan bilgilerin eksik veya hatalı olması.”

MADDE 5- Aynı Yönetmeliğin EK-1’i, EK-2/Lahika-1’i,
 EK-2/Lahika-2’si ve EK-3’ü ekteki şekilde değiştirilmiştir.

MADDE 6- Bu Yönetmelik yayımı tarihinde yürürlüğe girer.
MADDE 7- Bu Yönetmelik hükümlerini Enerji ve Tabii
 Kaynaklar Bakanı yürütür.
Recep Tayyip ERDOĞAN
CUMHURBAŞKANI
"""

DAYANAK_TEXT = """
MADDE 1 – Amaç
(1) Bu Yönetmeliğin amacı lisanslı depoculuğu düzenlemektir.

MADDE 2 – Kapsam
(1) Bu Yönetmelik lisanslı depo işletmelerini kapsar.

MADDE 3 – Dayanak
(1) Bu Yönetmelik, 8/1/2002 tarihli ve 4737 sayılı Sanayi Bölgelerinin
Geliştirilmesi Hakkında Kanun Hükmünde Kararnamesinin 252 nci maddesine
dayanılarak hazırlanmıştır.

MADDE 4 – Bu Yönetmelik yayımı tarihinde yürürlüğe girer.
MADDE 5 – Bu Yönetmelik hükümlerini Cumhurbaşkanı yürütür.
"""

OTV_LIST_OLD = """
1) Benzin
2) Motorin
3) Fuel oil
4) LPG
"""

OTV_LIST_NEW = """
MADDE 1 – ÖTV listesi aşağıdaki şekilde değiştirilmiştir.
1) Benzin
2) Motorin
3) Jet yakıtı
4) Biyodizel
5) LPG
"""


def test_inline_gazette_citation_is_not_stripped():
    cleaned = clean_new_text(RES_AMENDING)
    assert "20/10/2015 tarihli ve 29508 sayılı Resmî Gazete" in cleaned
    assert "33389" not in cleaned
    assert "ERDOĞAN" not in cleaned.upper().replace("Ğ", "G")
    assert "yayımı tarihinde" not in cleaned.casefold()


def test_dayanak_ordinal_is_not_article_252():
    assert extract_target_article(DAYANAK_TEXT.split("MADDE 3")[1]) != "Madde 252"
    block = "MADDE 3 – Dayanak\n(1) Kararnamesinin 252 nci maddesine dayanılarak hazırlanmıştır."
    assert extract_target_article(block) == "Madde 3"
    rows = build_legal_comparisons(title="Örnek Yönetmelik", new_text=DAYANAK_TEXT)
    labels = [row["article_no"] for row in rows]
    assert "Madde 252" not in labels
    assert "Madde —" not in labels
    assert all(not label or is_valid_article_label(label) for label in labels)
    assert rows[0]["render_mode"] == "procedural_notice"
    assert PROCEDURAL_NOTICE in rows[0]["change_summary"]


def test_never_emits_broken_article_titles():
    rows = build_legal_comparisons(title="RES", new_text=RES_AMENDING)
    labels = [row["article_no"] for row in rows]
    assert labels
    assert "Madde —" not in labels
    assert "MADDE —" not in labels
    assert "MADDE undefined" not in labels
    assert "MADDE NaN" not in [label.upper() for label in labels]
    assert all(is_valid_article_label(label) for label in labels)
    assert "Madde 3" in labels
    assert "Madde 4" in labels


def test_amending_gazette_uses_parent_article_not_wrapper():
    assert extract_target_article(clean_new_text(RES_AMENDING).split("MADDE 2")[0]) == "Madde 3"


def test_comparison_query_is_title_plus_article_numbers():
    query = comparison_query(
        "Rüzgar Kaynağına Dayalı Elektrik Üretimi Hakkında Yönetmelik",
        RES_AMENDING,
    )
    assert query.startswith("Rüzgar Kaynağına Dayalı")
    assert "Madde 3" in query
    assert "Bağdaşmaz alan" not in query
    assert "YEKA" not in query


def test_appendix_swap_renders_structured_bullets_not_raw_block():
    rows = build_legal_comparisons(title="RES EK değişikliği", new_text=RES_AMENDING)
    appendix = [row for row in rows if "EK-1" in (row.get("new_text_clean") or "") or "EK-1" in " ".join(row.get("added_items") or [])]
    assert appendix
    row = appendix[0]
    assert row["render_mode"] == "list_summary"
    added = " ".join(row["added_items"])
    assert "EK-1" in added
    assert "EK-3" in added
    assert row["old_text_clean"] == FALLBACK_OLD_TEXT


def test_otv_list_emits_added_and_removed_bullets():
    hit = {
        "chunk_id": "law:4760:article:1",
        "document_id": "law:4760",
        "title": "Özel Tüketim Vergisi Kanunu",
        "article": "Madde 1",
        "text": OTV_LIST_OLD,
        "similarity": 0.91,
    }
    rows = build_legal_comparisons(
        title="Özel Tüketim Vergisi listeleri",
        new_text=OTV_LIST_NEW,
        hits=[hit],
    )
    row = rows[0]
    assert row["has_exact_old_match"] is True
    assert row["render_mode"] == "list_summary"
    joined_added = " ".join(row["added_items"]).casefold()
    joined_removed = " ".join(row["removed_items"]).casefold()
    assert "jet" in joined_added or "biyodizel" in joined_added
    assert "fuel" in joined_removed


def test_is_valid_article_label_rejects_broken_forms():
    assert not is_valid_article_label("Madde —")
    assert not is_valid_article_label("MADDE undefined")
    assert not is_valid_article_label("MADDE NaN")
    assert not is_valid_article_label("")
    assert is_valid_article_label("Madde 5")
    assert is_valid_article_label("GEÇİCİ MADDE 1")
