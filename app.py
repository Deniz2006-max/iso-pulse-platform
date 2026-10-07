#!/usr/bin/env python3
"""İSO Mevzuat & Regülasyon Zekası — executive Streamlit dashboard.

Run from the repository root:

    streamlit run app.py
"""

from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings
from config.llm import openai_key_configured
from config.executive_copy import coerce_executive_summary, has_executive_structure
from config.rag_routing import RAG_STATUS_RAG, status_from_record
from config.relevance import audience_scope
from mocks.documents import MOCK_DOCUMENTS
from schemas.outputs import URGENCY_LABELS, department_label
from src.ingestion.daily_cache import DailyRevisionsCache
from src.ingestion.daily_pipeline import restore_reports
from src.ingestion.legal_compare import (
    FALLBACK_OLD_TEXT,
    PROCEDURAL_NOTICE,
    build_legal_comparisons,
    is_valid_article_label,
)
from src.ingestion.records import metric_counts, passed_records

NAVY = "#002B49"
NAVY_DEEP = "#00182C"
NAVY_MID = "#0A3A5C"
GOLD = "#C5A572"
GOLD_SOFT = "#E8D5B5"
BG = "#F3F5F7"
CARD = "#FFFFFF"
CARD_BORDER = "#D9E1E8"
TEXT = "#1B2430"
MUTED = "#5B6B7C"

BADGE_MATCH = "🟢 Doğrudan Madde Eşleşmesi (RAG)"
BADGE_GENERAL = "🟡 Genel Regülasyon Bildirimi"

SOURCE_DISPLAY = {
    "resmi_gazete": "Resmî Gazete",
    "sgk": "SGK",
    "mevzuat": "Mevzuat",
}

INDUSTRY_EMPTY_NOTICE = (
    "Seçilen tarihte sanayi işverenini doğrudan bağlayan bir kural değişikliği "
    "bulunmamaktadır."
)

PYTHON = sys.executable


def _as_root(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


REPORTS_ROOT = _as_root(Path(settings.reports_dir))
UPDATES_ROOT = _as_root(Path(settings.daily_updates_dir))


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        html, body, .stApp {{
            font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
            color: {TEXT};
        }}
        .stApp {{ background: {BG}; }}
        [data-testid="stHeader"] {{
            background: transparent !important;
        }}
        #MainMenu, footer,
        .stDeployButton, [data-testid="stAppDeployButton"], .stAppDeployButton,
        [data-testid="stDecoration"],
        [data-testid="stHeaderActionElements"],
        [data-testid="stToolbarActions"],
        [data-testid="stStatusWidget"],
        .stMarkdown a[href^="#"] {{ display: none !important; }}
        [data-testid="stSidebar"],
        [data-testid="stSidebar"] > div,
        [data-testid="stSidebarContent"],
        [data-testid="stMain"],
        [data-testid="stAppViewContainer"] {{
            transition: width 0.3s ease, min-width 0.3s ease, max-width 0.3s ease,
                margin 0.3s ease, padding 0.3s ease, transform 0.3s ease,
                left 0.3s ease !important;
        }}
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {NAVY} 0%, {NAVY_DEEP} 100%);
            border-right: 1px solid rgba(197,165,114,0.25);
        }}
        body:has([data-testid="stSidebar"][aria-expanded="true"]) [data-testid="stMain"] {{
            left: 300px !important;
            width: calc(100% - 300px) !important;
        }}
        body:has([data-testid="stSidebar"][aria-expanded="false"]) [data-testid="stMain"] {{
            left: 0 !important;
            width: 100% !important;
        }}
        [data-testid="stSidebarCollapseButton"] button {{
            background: rgba(197,165,114,0.16) !important;
            border: 1px solid rgba(197,165,114,0.45) !important;
            border-radius: 10px !important;
            width: 36px !important;
            height: 36px !important;
        }}
        [data-testid="stSidebarCollapseButton"] button:hover {{
            background: rgba(197,165,114,0.32) !important;
            border-color: {GOLD} !important;
        }}
        [data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"] {{
            color: {GOLD} !important;
        }}
        [data-testid="stSidebarHeader"] [data-testid="stSidebarCollapseButton"],
        [data-testid="stSidebarHeader"] [data-testid="stSidebarCollapseButton"] button,
        [data-testid="stSidebar"][aria-expanded="true"] [data-testid="stSidebarCollapseButton"],
        [data-testid="stSidebar"][aria-expanded="true"] [data-testid="stSidebarCollapseButton"] button {{
            visibility: visible !important;
            opacity: 1 !important;
        }}
        body:has([data-testid="stSidebar"][aria-expanded="true"]) [data-testid="stToolbar"],
        body:has([data-testid="stSidebar"][aria-expanded="true"]) [data-testid="stExpandSidebarButton"] {{
            display: none !important;
            opacity: 0 !important;
            pointer-events: none !important;
            visibility: hidden !important;
        }}
        body:has([data-testid="stSidebar"][aria-expanded="false"]) [data-testid="stToolbar"] {{
            display: block !important;
            position: fixed !important;
            top: 0.9rem !important;
            left: 0.9rem !important;
            width: 44px !important;
            height: 44px !important;
            min-width: 44px !important;
            overflow: visible !important;
            background: transparent !important;
            box-shadow: none !important;
            z-index: 1000001 !important;
            padding: 0 !important;
            margin: 0 !important;
        }}
        body:has([data-testid="stSidebar"][aria-expanded="false"]) [data-testid="stToolbar"] [data-testid="stAppDeployButton"],
        body:has([data-testid="stSidebar"][aria-expanded="false"]) [data-testid="stToolbar"] .stAppDeployButton {{
            display: none !important;
        }}
        body:has([data-testid="stSidebar"][aria-expanded="false"]) [data-testid="stExpandSidebarButton"] {{
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            position: fixed !important;
            top: 0.9rem !important;
            left: 0.9rem !important;
            width: 44px !important;
            height: 44px !important;
            min-width: 44px !important;
            opacity: 1 !important;
            visibility: visible !important;
            pointer-events: auto !important;
            background: {NAVY} !important;
            color: {GOLD} !important;
            border: 1px solid rgba(197,165,114,0.55) !important;
            border-radius: 12px !important;
            box-shadow: 0 8px 24px rgba(0, 43, 73, 0.28) !important;
            transition: background 0.3s ease, border-color 0.3s ease, transform 0.3s ease !important;
        }}
        body:has([data-testid="stSidebar"][aria-expanded="false"]) [data-testid="stExpandSidebarButton"]:hover {{
            background: {NAVY_MID} !important;
            border-color: {GOLD} !important;
            transform: translateY(-1px);
        }}
        body:has([data-testid="stSidebar"][aria-expanded="false"]) [data-testid="stExpandSidebarButton"] [data-testid="stIconMaterial"] {{
            color: {GOLD} !important;
            font-size: 1.35rem !important;
        }}
        [data-testid="stSidebar"] [data-testid="stDateInput"] input {{
            background: rgba(255,255,255,0.08);
            color: #F4F7FA;
            border: 1px solid rgba(197,165,114,0.45);
            border-radius: 10px;
        }}
        [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] .stCheckbox label p {{
            color: #F4F7FA !important;
        }}
        [data-testid="stExpander"] {{
            background: {CARD};
            border: 1px solid {CARD_BORDER};
            border-radius: 16px;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
            margin-bottom: 0.85rem;
        }}
        [data-testid="stExpander"] summary {{
            background: {NAVY};
            color: #F8FAFC;
            border-radius: 16px;
            font-weight: 700;
        }}
        [data-testid="stExpander"] details[open] summary {{
            border-radius: 16px 16px 0 0;
        }}
        .stTabs [data-baseweb="tab-list"] {{
            flex-wrap: wrap;
            gap: 0.2rem;
            background: transparent;
        }}
        .stTabs [data-baseweb="tab"] {{
            font-size: 0.86rem;
            font-weight: 700;
            color: {NAVY};
            background: #EEF3F8;
            border-radius: 999px;
            padding: 0.35rem 0.85rem;
        }}
        .stTabs [data-baseweb="tab"][aria-selected="true"] {{
            background: {NAVY};
            color: #FFFFFF;
        }}
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] .stCaption,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{
            color: #F4F7FA !important;
        }}
        [data-testid="stSidebar"] .stButton > button {{
            background: {GOLD};
            color: {NAVY_DEEP};
            font-weight: 700;
            font-size: 0.95rem;
            border: 0;
            border-radius: 14px;
            padding: 0.95rem 1.05rem;
            width: 100%;
            letter-spacing: 0.01em;
            box-shadow: 0 10px 22px rgba(0, 0, 0, 0.18);
        }}
        [data-testid="stSidebar"] .stButton > button:hover {{
            background: {GOLD_SOFT};
            color: {NAVY};
        }}
        .block-container {{ padding-top: 1.4rem; max-width: 1180px; }}
        .iso-hero {{
            background: linear-gradient(135deg, {NAVY} 0%, {NAVY_MID} 70%, {NAVY_DEEP} 100%);
            color: white;
            border-radius: 18px;
            padding: 1.7rem 1.85rem 1.55rem 1.85rem;
            margin-bottom: 1.25rem;
            box-shadow: 0 16px 40px rgba(0, 43, 73, 0.22);
            border: 1px solid rgba(197,165,114,0.35);
        }}
        .iso-kicker {{
            letter-spacing: 0.18em;
            font-size: 0.7rem;
            color: {GOLD};
            font-weight: 700;
            text-transform: uppercase;
        }}
        .iso-title {{
            font-size: 1.72rem;
            font-weight: 750;
            margin: 0.35rem 0 0.4rem 0;
            line-height: 1.25;
        }}
        .iso-sub {{
            color: #C9D6E2;
            font-size: 1.02rem;
            margin: 0;
        }}
        .iso-brand {{
            text-align: center;
            padding: 0.4rem 0.2rem 1.1rem 0.2rem;
        }}
        .iso-mark {{
            width: 54px;
            height: 54px;
            margin: 0 auto 0.7rem auto;
            border-radius: 16px;
            background: rgba(197,165,114,0.16);
            border: 1px solid {GOLD};
            display: flex;
            align-items: center;
            justify-content: center;
            color: {GOLD};
            font-weight: 800;
            font-size: 1.05rem;
            letter-spacing: 0.04em;
        }}
        .iso-brand h2 {{
            font-size: 1.08rem;
            font-weight: 750;
            margin: 0;
            color: #FFFFFF !important;
        }}
        .iso-brand p {{
            margin: 0.3rem 0 0 0;
            font-size: 0.8rem;
            color: {GOLD_SOFT} !important;
            letter-spacing: 0.04em;
        }}
        .iso-status {{
            display: block;
            text-align: center;
            border-radius: 999px;
            padding: 0.55rem 0.85rem;
            margin: 0.85rem 0 1.1rem 0;
            font-size: 0.86rem;
            font-weight: 700;
        }}
        .iso-status-on {{
            background: rgba(22, 101, 52, 0.35);
            color: #D1FAE5 !important;
            border: 1px solid #86EFAC;
        }}
        .iso-status-off {{
            background: rgba(146, 64, 14, 0.35);
            color: #FEF3C7 !important;
            border: 1px solid #FCD34D;
        }}
        .iso-metric {{
            background: {CARD};
            border: 1px solid {CARD_BORDER};
            border-radius: 16px;
            padding: 1.05rem 1.15rem 0.95rem 1.15rem;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
            min-height: 108px;
        }}
        .iso-metric .lbl {{
            font-size: 0.74rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: {MUTED};
            font-weight: 700;
        }}
        .iso-metric .val {{
            font-size: 1.85rem;
            font-weight: 800;
            color: {NAVY};
            margin-top: 0.25rem;
            line-height: 1.1;
        }}
        .iso-metric .hint {{
            font-size: 0.8rem;
            color: {MUTED};
            margin-top: 0.25rem;
        }}
        .iso-badge {{
            display: inline-block;
            background: {NAVY};
            color: #FFFFFF;
            border-radius: 999px;
            padding: 0.22rem 0.75rem;
            margin: 0.12rem 0.28rem 0.12rem 0;
            font-size: 0.78rem;
            font-weight: 700;
            border: 1px solid {GOLD};
        }}
        .iso-chip {{
            display: inline-block;
            background: #E8EEF5;
            color: {NAVY};
            border-radius: 999px;
            padding: 0.2rem 0.65rem;
            margin: 0.12rem 0.22rem 0.12rem 0;
            font-size: 0.76rem;
            font-weight: 600;
        }}
        .iso-rag-on {{
            display: inline-block;
            background: #14532D;
            color: #ECFDF5;
            border-radius: 999px;
            padding: 0.28rem 0.8rem;
            margin: 0.15rem 0.25rem 0.15rem 0;
            font-size: 0.8rem;
            font-weight: 700;
            border: 1px solid #86EFAC;
        }}
        .iso-rag-off {{
            display: inline-block;
            background: #78350F;
            color: #FFFBEB;
            border-radius: 999px;
            padding: 0.28rem 0.8rem;
            margin: 0.15rem 0.25rem 0.15rem 0;
            font-size: 0.8rem;
            font-weight: 700;
            border: 1px solid #FCD34D;
        }}
        .iso-urg-critical {{
            display: inline-block;
            background: #7F1D1D;
            color: #FEE2E2;
            border-radius: 999px;
            padding: 0.22rem 0.7rem;
            font-size: 0.76rem;
            font-weight: 700;
        }}
        .iso-urg-medium {{
            display: inline-block;
            background: #92400E;
            color: #FEF3C7;
            border-radius: 999px;
            padding: 0.22rem 0.7rem;
            font-size: 0.76rem;
            font-weight: 700;
        }}
        .iso-urg-low {{
            display: inline-block;
            background: #1E3A5F;
            color: #DBEAFE;
            border-radius: 999px;
            padding: 0.22rem 0.7rem;
            font-size: 0.76rem;
            font-weight: 700;
        }}
        .iso-dept-head {{
            color: {NAVY};
            font-size: 0.98rem;
            font-weight: 800;
            margin: 0.7rem 0 0.3rem 0;
        }}
        .iso-compare {{
            background: #F8FAFC;
            border-radius: 12px;
            padding: 0.9rem 1rem;
            border: 1px solid {CARD_BORDER};
            font-size: 0.9rem;
            line-height: 1.55;
            max-height: 22rem;
            overflow-y: auto;
            white-space: pre-wrap;
        }}
        .iso-compare mark {{
            background: #d4edda;
            color: #155724;
            padding: 0 0.12em;
            border-radius: 3px;
        }}
        .iso-compare del {{
            background: #f8d7da;
            color: #721c24;
            text-decoration: line-through;
            padding: 0 0.12em;
            border-radius: 3px;
        }}
        .iso-diff-summary {{
            background: #F8FAFC;
            border: 1px solid {CARD_BORDER};
            border-radius: 12px;
            padding: 0.75rem 1rem;
            margin: 0.35rem 0 0.85rem 0;
            font-size: 0.9rem;
            line-height: 1.55;
            color: {TEXT};
        }}
        .iso-article-tag {{
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            color: {NAVY};
            margin: 0.4rem 0 0.35rem 0;
        }}
        .iso-proc-notice {{
            background: #F8FAFC;
            border: 1px solid {CARD_BORDER};
            border-radius: 12px;
            padding: 0.85rem 1rem;
            font-size: 0.9rem;
            line-height: 1.55;
            color: {MUTED};
        }}
        .iso-diff-list {{
            background: #F8FAFC;
            border: 1px solid {CARD_BORDER};
            border-radius: 12px;
            padding: 0.85rem 1rem;
            margin: 0.35rem 0 0.85rem 0;
            font-size: 0.9rem;
            line-height: 1.55;
        }}
        .iso-diff-list ul {{
            margin: 0.25rem 0 0.7rem 1.1rem;
            padding: 0;
        }}
        .iso-diff-add {{ color: #155724; }}
        .iso-diff-del {{ color: #721c24; }}
        .iso-label {{
            font-size: 0.7rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: {MUTED};
            font-weight: 700;
            margin-bottom: 0.35rem;
        }}
        .iso-empty {{
            background: {CARD};
            border: 1px dashed {CARD_BORDER};
            border-radius: 16px;
            padding: 1.6rem 1.4rem;
            color: {MUTED};
            text-align: center;
        }}
        iframe[height="0"] {{
            position: absolute !important;
            width: 0 !important;
            height: 0 !important;
            border: 0 !important;
            overflow: hidden !important;
            left: -9999px !important;
            pointer-events: none !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    _inject_sidebar_toggle_script()


def _inject_sidebar_toggle_script() -> None:
    """Keep Streamlit's native expand control reachable after the << collapse."""
    import streamlit.components.v1 as components

    components.html(
        """
<script>
(function () {
  const doc = window.parent.document;
  function sync() {
    const sidebar = doc.querySelector('[data-testid="stSidebar"]');
    const main = doc.querySelector('[data-testid="stMain"]');
    const expand = doc.querySelector('[data-testid="stExpandSidebarButton"]');
    const collapse = doc.querySelector('[data-testid="stSidebarCollapseButton"]');
    const collapseBtn = collapse && collapse.querySelector("button");
    const open = !sidebar || sidebar.getAttribute("aria-expanded") === "true";
    if (main && sidebar) {
      const measured = Math.round(sidebar.getBoundingClientRect().width);
      const width = open ? (measured > 80 ? measured : 300) : 0;
      main.style.setProperty("left", width + "px", "important");
      main.style.setProperty("width", "calc(100% - " + width + "px)", "important");
    }
    if (collapse) {
      collapse.style.setProperty("visibility", "visible", "important");
      collapse.style.setProperty("opacity", "1", "important");
    }
    if (collapseBtn) {
      collapseBtn.style.setProperty("visibility", "visible", "important");
      collapseBtn.style.setProperty("opacity", "1", "important");
      collapseBtn.setAttribute("aria-label", "Kenar çubuğunu kapat");
      collapseBtn.setAttribute("title", "Kenar çubuğunu kapat");
    }
    if (!expand) return;
    expand.setAttribute("aria-label", "Kenar çubuğunu aç");
    expand.setAttribute("title", "Kenar çubuğunu aç");
    expand.setAttribute("aria-hidden", open ? "true" : "false");
  }
  if (doc.documentElement.dataset.isoSidebarToggle !== "3") {
    doc.documentElement.dataset.isoSidebarToggle = "3";
    new MutationObserver(sync).observe(doc.body, {
      subtree: true,
      attributes: true,
      attributeFilter: ["aria-expanded", "class", "style"],
    });
  }
  sync();
  requestAnimationFrame(sync);
  setTimeout(sync, 320);
})();
</script>
        """,
        height=0,
        width=0,
    )


def report_dir(day: str) -> Path:
    return REPORTS_ROOT / day


def is_synthetic_item(item: dict[str, Any]) -> bool:
    return str(item.get("document_id") or "") in MOCK_DOCUMENTS


def _read_json_dicts(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def live_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if not is_synthetic_item(row)]


def load_items(day: str) -> list[dict[str, Any]]:
    cached = load_cached_analysis(day)
    if cached is not None:
        return cached
    folder = report_dir(day)
    combined = folder / "items.json"
    if combined.is_file():
        return live_records(_read_json_dicts(combined))
    items_dir = folder / "items"
    rows: list[dict[str, Any]] = []
    if items_dir.is_dir():
        for path in sorted(items_dir.glob("*.json")):
            rows.extend(_read_json_dicts(path))
        return live_records(rows)
    return []


def load_raw_publications(day: str) -> list[dict[str, Any]]:
    """Unfiltered scrape JSON for the audit / ham yayın view."""
    folder = UPDATES_ROOT / day
    combined = folder / "all.json"
    if combined.is_file():
        return [row for row in _read_json_dicts(combined) if isinstance(row, dict)]
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name in ("resmi_gazete.json", "sgk.json"):
        for row in _read_json_dicts(folder / name):
            key = str(row.get("url") or row.get("title") or "")
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            rows.append(row)
    return rows


def load_daily_updates(day: str) -> dict[str, dict[str, Any]]:
    folder = UPDATES_ROOT / day
    by_url: dict[str, dict[str, Any]] = {}
    if not folder.is_dir():
        return by_url
    for name in ("all.json", "resmi_gazete.json", "sgk.json"):
        path = folder / name
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, list):
            continue
        for row in payload:
            if isinstance(row, dict) and row.get("url"):
                by_url[str(row["url"])] = row
    return by_url


def department_codes(item: dict[str, Any]) -> list[str]:
    raw = item.get("departments") or (item.get("delivery") or {}).get("departments") or []
    return [str(code) for code in raw]


def department_badges_html(item: dict[str, Any]) -> str:
    depts = department_codes(item)
    if not depts:
        return ""
    return "".join(
        f'<span class="iso-badge">{html.escape(department_label(code))}</span>'
        for code in depts
    )


def matching_badge_html(item: dict[str, Any]) -> str:
    resolved = status_from_record(item)
    if not resolved and not item.get("is_relevant"):
        return ""
    is_rag = bool(resolved and resolved[0] == RAG_STATUS_RAG)
    css = "iso-rag-on" if is_rag else "iso-rag-off"
    label = BADGE_MATCH if is_rag else BADGE_GENERAL
    return f'<span class="{css}">{html.escape(label)}</span>'


def urgency_badge_html(item: dict[str, Any]) -> str:
    scope = str(item.get("sector_scope") or "") or audience_scope(
        str(item.get("title") or ""),
        str(item.get("new_text") or item.get("raw_text") or ""),
    )
    if scope == "kamu":
        return (
            '<span class="iso-urg-low">'
            f"{html.escape('Düşük / Kamu Kurumları Kapsamı')}</span>"
        )
    if scope == "specialized":
        return (
            '<span class="iso-urg-low">'
            f"{html.escape('Düşük / Özel Sektör Kapsamı')}</span>"
        )
    urgency = str(
        item.get("urgency") or (item.get("delivery") or {}).get("urgency") or ""
    )
    if urgency not in URGENCY_LABELS:
        return ""
    css = {
        "critical": "iso-urg-critical",
        "medium": "iso-urg-medium",
        "low": "iso-urg-low",
    }[urgency]
    return f'<span class="{css}">{html.escape(URGENCY_LABELS[urgency])}</span>'  # type: ignore[index]


def source_label(item: dict[str, Any]) -> str:
    return SOURCE_DISPLAY.get(str(item.get("source") or ""), "Resmî kaynak")


def old_text_for(item: dict[str, Any]) -> str:
    chunks = item.get("retrieved_chunks") or []
    if chunks:
        top = chunks[0]
        article = top.get("article") or top.get("chunk_id") or ""
        body = (top.get("text") or "").strip()
        if article and body:
            return f"{article}\n\n{body}"
        return body or article
    return (item.get("old_text") or "").strip()


def new_text_for(item: dict[str, Any], daily: dict[str, dict[str, Any]]) -> str:
    candidates = [
        str(item.get("new_text") or "").strip(),
        str(item.get("raw_text") or "").strip(),
    ]
    url = str(item.get("url") or "")
    if url and url in daily:
        candidates.append(str(daily[url].get("raw_text") or "").strip())
    return max(candidates, key=len)


def legal_comparisons_for(
    item: dict[str, Any],
    daily: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    return build_legal_comparisons(
        title=str(item.get("title") or ""),
        new_text=new_text_for(item, daily) or str(item.get("new_text") or ""),
        hits=list(item.get("retrieved_chunks") or []),
        source=str(item.get("source") or ""),
        document_id=str(item.get("document_id") or ""),
    )


def _obligation_duplicates_summary(obligation: str, *others: str) -> bool:
    """True when the gray Özet line restates bullets already on the card."""
    text = " ".join((obligation or "").split()).strip()
    if not text:
        return True
    lowered = text.casefold()
    if lowered.startswith("özet & değişiklik:") or lowered.startswith(
        "ozet & degisiklik:"
    ):
        return True
    for other in others:
        blob = " ".join((other or "").split()).casefold()
        if lowered and blob and (lowered in blob or blob in lowered):
            return True
    return False


def delivery_summary(item: dict[str, Any]) -> str:
    delivery = item.get("delivery") or {}
    depts = department_codes(item)
    return coerce_executive_summary(
        delivery.get("summary") or item.get("relevance_reason") or "",
        str(item.get("title") or ""),
        str(item.get("new_text") or ""),
        depts[0] if depts else "hukuk",
    )


def pretty_day(day: str) -> str:
    return datetime.strptime(day, "%Y-%m-%d").strftime("%d.%m.%Y")


def analysis_button_label(day: str) -> str:
    return f"🔍 {pretty_day(day)} Mevzuatını Analiz Et"


def analysis_complete(day: str) -> bool:
    cache = DailyRevisionsCache().status(day, "all")
    if cache.warm:
        return True
    return (report_dir(day) / "items.json").is_file()


def analysis_ready(day: str) -> bool:
    return analysis_complete(day)


def pipeline_env() -> dict[str, str]:
    env = os.environ.copy()
    env["ISO_PULSE_USE_MOCK_LLM"] = "false"
    env["OMP_NUM_THREADS"] = env.get("OMP_NUM_THREADS") or "1"
    env["MKL_NUM_THREADS"] = env.get("MKL_NUM_THREADS") or "1"
    env["TOKENIZERS_PARALLELISM"] = "false"
    return env


def run_command(args: list[str], *, env: dict[str, str] | None = None) -> int:
    proc = subprocess.run(
        args,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=None,
        env=env,
    )
    return proc.returncode


def purge_synthetic_reports(day: str) -> None:
    folder = report_dir(day) / "items"
    if not folder.is_dir():
        return
    for path in folder.glob("*.json"):
        if path.stem in MOCK_DOCUMENTS:
            path.unlink(missing_ok=True)


def load_cached_analysis(day: str) -> list[dict[str, Any]] | None:
    cache = DailyRevisionsCache()
    status = cache.status(day, "all")
    if not status.warm:
        return None
    records = live_records(cache.load_records(day, "all"))
    restore_reports(day, records)
    return records


def run_daily_analysis(day: str) -> tuple[bool, str]:
    """Serve SQLite cache for the selected date, or scrape that calendar day live."""
    cached = load_cached_analysis(day)
    if cached is not None:
        return True, "ready"

    if not openai_key_configured():
        return False, "key"

    purge_synthetic_reports(day)
    code = run_command(
        [
            PYTHON,
            "-m",
            "src.ingestion.daily_pipeline",
            "--date",
            day,
            "--source",
            "all",
            "--refresh",
        ],
        env=pipeline_env(),
    )
    if code != 0:
        return False, "pipeline"
    purge_synthetic_reports(day)
    return True, "fresh"


def compare_box(text: str, fallback: str) -> None:
    body = (text or "").strip() or fallback
    st.markdown(
        f'<div class="iso-compare">{html.escape(body)}</div>',
        unsafe_allow_html=True,
    )


def compare_html_box(markup: str, fallback: str) -> None:
    body = (markup or "").strip() or html.escape(fallback)
    st.markdown(
        f'<div class="iso-compare">{body}</div>',
        unsafe_allow_html=True,
    )


def _render_summary_html(summary: str) -> None:
    rendered = html.escape(summary)
    rendered = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", rendered)
    rendered = rendered.replace("\n", "<br>\n")
    st.markdown(
        f'<div class="iso-diff-summary">{rendered}</div>',
        unsafe_allow_html=True,
    )


def _render_list_items(items: list[Any], css: str, empty: str) -> str:
    rows = [str(item).strip() for item in items if str(item).strip()]
    if not rows:
        return f"<p class='{css}'>{html.escape(empty)}</p>"
    bullets = "".join(f"<li>{html.escape(item)}</li>" for item in rows)
    return f"<ul class='{css}'>{bullets}</ul>"


def render_legal_comparisons(
    item: dict[str, Any],
    daily: dict[str, dict[str, Any]],
) -> None:
    rows = legal_comparisons_for(item, daily)
    if not rows:
        compare_box("", "Karşılaştırma metni üretilemedi.")
        return
    for index, row in enumerate(rows):
        mode = str(row.get("render_mode") or "side_by_side")
        if mode == "procedural_notice":
            st.markdown(
                f'<div class="iso-proc-notice">{html.escape(PROCEDURAL_NOTICE)}</div>',
                unsafe_allow_html=True,
            )
            continue
        article = str(row.get("article_no") or "").strip()
        if is_valid_article_label(article):
            st.markdown(
                f'<div class="iso-article-tag">{html.escape(article)}</div>',
                unsafe_allow_html=True,
            )
        summary = str(row.get("change_summary") or "").strip()
        if mode == "list_summary":
            added = list(row.get("added_items") or [])
            removed = list(row.get("removed_items") or [])
            if summary:
                _render_summary_html(summary)
            st.markdown(
                "<div class='iso-diff-list'>"
                "<div class='iso-label'>Eklenen / değişen kalemler</div>"
                f"{_render_list_items(added, 'iso-diff-add', '—')}"
                "<div class='iso-label'>Kaldırılan / önceki kalemler</div>"
                f"{_render_list_items(removed, 'iso-diff-del', FALLBACK_OLD_TEXT if not row.get('has_exact_old_match') else '—')}"
                "</div>",
                unsafe_allow_html=True,
            )
            if index < len(rows) - 1:
                st.markdown("")
            continue
        if summary and (row.get("is_rewrite") or not row.get("has_exact_old_match")):
            _render_summary_html(summary)
        left, right = st.columns(2)
        with left:
            st.markdown(
                '<div class="iso-label">Eski Metin</div>',
                unsafe_allow_html=True,
            )
            compare_html_box(
                str(row.get("old_text_html") or ""),
                str(row.get("old_text_clean") or FALLBACK_OLD_TEXT),
            )
        with right:
            st.markdown(
                '<div class="iso-label">Yeni Metin</div>',
                unsafe_allow_html=True,
            )
            compare_html_box(
                str(row.get("new_text_html") or ""),
                str(row.get("new_text_clean") or "Yeni metin bu raporda yer almıyor."),
            )
        if index < len(rows) - 1:
            st.markdown("")


def metric_card(label: str, value: str, hint: str = "") -> str:
    extra = f'<div class="hint">{html.escape(hint)}</div>' if hint else ""
    return (
        f'<div class="iso-metric"><div class="lbl">{html.escape(label)}</div>'
        f'<div class="val">{html.escape(str(value))}</div>{extra}</div>'
    )


def render_hero(day: str) -> None:
    pretty = pretty_day(day)
    st.markdown(
        f"""
        <div class="iso-hero">
          <div class="iso-kicker">İstanbul Sanayi Odası</div>
          <p class="iso-title">İSO Mevzuat &amp; Regülasyon Zekası Platformu</p>
          <p class="iso-sub">Resmî Gazete ve SGK Günlük Etki Analizi ve Aksiyon Raporu · {pretty}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_item_card(
    index: int,
    item: dict[str, Any],
    daily: dict[str, dict[str, Any]],
) -> None:
    title = item.get("title") or f"Yayın {index}"
    header = f"{index}. {title}"
    with st.expander(header, expanded=index == 1):
        bits = [
            matching_badge_html(item),
            urgency_badge_html(item),
            department_badges_html(item),
            f'<span class="iso-chip">{html.escape(source_label(item))}</span>',
        ]
        st.markdown(" ".join(part for part in bits if part), unsafe_allow_html=True)

        tab_ozet, tab_karsilastir, tab_aksiyon = st.tabs(
            [
                "📌 Özet & Etki Analizi",
                "⚖️ Madde Kıyaslama (Eski/Yeni Metin)",
                "✅ Alınması Gereken Aksiyonlar",
            ]
        )
        analyses = item.get("analyses") or {}
        with tab_ozet:
            summary = delivery_summary(item)
            if summary:
                st.markdown(summary)
            if not analyses:
                st.caption("Bu yayın için birim bazlı etki özeti üretilmedi.")
            for dept, analysis in analyses.items():
                if not isinstance(analysis, dict):
                    continue
                dept_summary = (
                    analysis.get("summary") or analysis.get("obligation_change") or ""
                )
                if summary and (
                    has_executive_structure(summary)
                    or _obligation_duplicates_summary(dept_summary, summary)
                ):
                    continue
                st.markdown(
                    f'<div class="iso-dept-head">{html.escape(department_label(str(dept)))}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(dept_summary or "—")

        with tab_karsilastir:
            render_legal_comparisons(item, daily)

        with tab_aksiyon:
            if not analyses:
                st.caption("Aksiyon maddesi bulunmuyor.")
            for dept, analysis in analyses.items():
                if not isinstance(analysis, dict):
                    continue
                st.markdown(
                    f'<div class="iso-dept-head">{html.escape(department_label(str(dept)))}</div>',
                    unsafe_allow_html=True,
                )
                impact = analysis.get("operational_impact") or "—"
                obligation = analysis.get("obligation_change") or ""
                st.markdown(impact)
                if obligation and not _obligation_duplicates_summary(
                    obligation,
                    delivery_summary(item),
                    analysis.get("summary") or "",
                    impact,
                ):
                    st.caption(obligation)


def render_raw_publication(index: int, item: dict[str, Any]) -> None:
    title = item.get("title") or f"Yayın {index}"
    category = item.get("category") or "—"
    reason = str(item.get("relevance_reason") or "").strip()
    snippet = (item.get("raw_text") or item.get("new_text") or "").strip()
    if len(snippet) > 600:
        snippet = snippet[:600].rstrip() + "…"
    with st.expander(f"{index}. {title}", expanded=False):
        bits = [
            f'<span class="iso-chip">{html.escape(source_label(item))}</span>',
            f'<span class="iso-chip">{html.escape(str(category))}</span>',
        ]
        if item.get("is_relevant") is False:
            reason_l = reason.casefold()
            if "kapsam dışı / idari duyuru" in reason_l or "idari duyuru" in reason_l:
                bits.append('<span class="iso-chip">Kapsam Dışı / İdari Duyuru</span>')
            else:
                bits.append('<span class="iso-chip">Kapsam dışı</span>')
        st.markdown(" ".join(bits), unsafe_allow_html=True)
        if reason:
            st.caption(reason)
        url = str(item.get("url") or "").strip()
        if url:
            st.markdown(f"[Kaynak]({html.escape(url)})")
        if snippet:
            compare_box(snippet, "")


def main() -> None:
    st.set_page_config(
        page_title="İSO Mevzuat & Regülasyon Zekası",
        page_icon="📡",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={"Get help": None, "Report a bug": None, "About": None},
    )
    inject_css()

    today = date.today()
    with st.sidebar:
        st.markdown(
            """
            <div class="iso-brand">
              <div class="iso-mark">İSO</div>
              <h2>İstanbul Sanayi Odası</h2>
              <p>Mevzuat Zekası</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        selected_day = st.date_input("Tarih Seçimi", value=today, format="DD.MM.YYYY")
        day = selected_day.isoformat() if hasattr(selected_day, "isoformat") else today.isoformat()

        ready = analysis_ready(day)
        if ready:
            st.markdown(
                '<div class="iso-status iso-status-on">🟢 Güncel Rapor Hazır</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="iso-status iso-status-off">🟡 Yeni Analiz Gerekli</div>',
                unsafe_allow_html=True,
            )

        run_clicked = st.button(
            analysis_button_label(day),
            use_container_width=True,
            type="primary",
        )
        show_all = st.toggle(
            "🌐 Tüm Değişiklikleri / Ham Resmi Gazete Yayınlarını Göster",
            value=False,
        )

    render_hero(day)

    if run_clicked:
        with st.spinner(
            f"{pretty_day(day)} tarihli Resmî Gazete ve SGK yayınları inceleniyor…"
        ):
            ok, reason = run_daily_analysis(day)
        if ok:
            st.rerun()
        elif reason == "key":
            st.error("Canlı analiz şu anda kullanılamıyor. Lütfen sistem yöneticinizle iletişime geçin.")
        else:
            st.error("Analiz tamamlanamadı. Lütfen daha sonra tekrar deneyin.")

    items = load_items(day)
    daily = load_daily_updates(day)
    raw = load_raw_publications(day)
    examined, passed_n, mapped_n = metric_counts(items)
    if not examined and raw:
        examined = len(raw)
    relevant = passed_records(items)

    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(
            metric_card("İncelenen Yayın", str(examined), "Seçilen güne ait resmi yayınlar"),
            unsafe_allow_html=True,
        )
    with m2:
        st.markdown(
            metric_card(
                "Kritik Değişiklik",
                str(passed_n),
                "Filtreyi geçen kural değişiklikleri",
            ),
            unsafe_allow_html=True,
        )
    with m3:
        st.markdown(
            metric_card(
                "Doğrudan İlgili Madde",
                str(mapped_n),
                "İK, Maliye veya Hukuk kartı üretilen kayıtlar",
            ),
            unsafe_allow_html=True,
        )

    st.markdown("")
    if not analysis_complete(day) and not items and not raw:
        st.markdown(
            f'<div class="iso-empty">{pretty_day(day)} için henüz bir etki raporu yok. '
            "Soldaki analiz düğmesiyle o günün Resmî Gazete ve SGK yayınlarını tarayabilirsiniz.</div>",
            unsafe_allow_html=True,
        )
        return

    if relevant:
        st.markdown("#### Günlük etki raporları")
        dropped = max(0, examined - len(relevant))
        if dropped:
            st.caption(
                f"{len(relevant)} ilgili değişiklik listeleniyor. "
                f"Kapsam Dışı Bırakılan Yayınlar: {dropped}."
            )
        for index, item in enumerate(relevant, start=1):
            render_item_card(index, item, daily)
    else:
        st.markdown(
            f'<div class="iso-empty">{html.escape(INDUSTRY_EMPTY_NOTICE)}</div>',
            unsafe_allow_html=True,
        )

    if show_all:
        feed = raw or items
        st.markdown("#### Ham Resmî Gazete / SGK yayınları")
        st.caption("LLM filtresi uygulanmadan, seçilen güne ait tüm çekilen yayınlar.")
        if not feed:
            st.caption("Bu tarih için ham yayın listesi yok. Önce analizi çalıştırın.")
        else:
            for index, item in enumerate(feed, start=1):
                render_raw_publication(index, item)


if __name__ == "__main__":
    main()
