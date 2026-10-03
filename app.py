#!/usr/bin/env python3
"""İSO Mevzuat Radar — Streamlit operations dashboard.

Run from the repository root:

    streamlit run app.py
"""

from __future__ import annotations

import html
import json
import os
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
from schemas.outputs import department_label

NAVY = "#003366"
NAVY_DEEP = "#002244"
GOLD = "#C5A572"
BG = "#F8FAFC"
CARD_BORDER = "#E2E8F0"
TEXT = "#1E293B"
MUTED = "#64748B"

SOURCE_LABELS = {
    "all": "All",
    "resmi_gazete": "resmi_gazete",
    "sgk": "sgk",
    "mevzuat": "mevzuat",
}

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
        [data-testid="stHeader"] {{ background: transparent; }}
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {NAVY} 0%, {NAVY_DEEP} 100%);
        }}
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] .stCaption,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{
            color: #F8FAFC !important;
        }}
        [data-testid="stSidebar"] .stButton > button {{
            background: {GOLD};
            color: {NAVY_DEEP};
            font-weight: 700;
            border: 0;
            border-radius: 12px;
            padding: 0.7rem 1rem;
            width: 100%;
        }}
        [data-testid="stSidebar"] .stButton > button:hover {{
            background: #d4b57f;
        }}
        .iso-header {{
            background: {NAVY};
            color: white;
            border-radius: 12px;
            padding: 1.25rem 1.5rem;
            margin-bottom: 1rem;
            box-shadow: 0 10px 28px rgba(0, 51, 102, 0.18);
        }}
        .iso-kicker {{
            letter-spacing: 0.14em;
            font-size: 0.72rem;
            color: {GOLD};
            font-weight: 700;
            text-transform: uppercase;
        }}
        .iso-title {{
            font-size: 1.4rem;
            font-weight: 700;
            margin: 0.2rem 0 0 0;
        }}
        .iso-chip {{
            display: inline-block;
            background: #E8EEF5;
            color: {NAVY};
            border-radius: 999px;
            padding: 0.22rem 0.7rem;
            margin: 0.15rem 0.25rem 0.15rem 0;
            font-size: 0.8rem;
            font-weight: 600;
        }}
        .iso-badge {{
            display: inline-block;
            background: {NAVY};
            color: #FFFFFF;
            border-radius: 999px;
            padding: 0.28rem 0.85rem;
            margin: 0.15rem 0.3rem 0.15rem 0;
            font-size: 0.82rem;
            font-weight: 700;
            border: 1px solid {GOLD};
            letter-spacing: 0.01em;
        }}
        .iso-dept-head {{
            color: {NAVY};
            font-size: 1.05rem;
            font-weight: 800;
            margin: 0.85rem 0 0.35rem 0;
        }}
        .iso-compare {{
            background: {BG};
            border-radius: 12px;
            padding: 0.85rem 1rem;
            border: 1px solid {CARD_BORDER};
            font-size: 0.9rem;
            line-height: 1.5;
            max-height: 22rem;
            overflow-y: auto;
            white-space: pre-wrap;
        }}
        .iso-label {{
            font-size: 0.72rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: {MUTED};
            font-weight: 700;
            margin-bottom: 0.35rem;
        }}
        .block-container {{ padding-top: 1.25rem; max-width: 1280px; }}
        div.stButton > button[kind="primary"] {{
            background: {NAVY};
            color: #FFFFFF;
            font-weight: 700;
            border-radius: 12px;
            padding: 0.85rem 1.2rem;
            border: 0;
            box-shadow: 0 8px 20px rgba(0, 51, 102, 0.22);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def list_dated_dirs(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    found: list[str] = []
    for path in root.iterdir():
        if path.is_dir() and not path.name.startswith("."):
            try:
                datetime.strptime(path.name, "%Y-%m-%d")
            except ValueError:
                continue
            found.append(path.name)
    return sorted(found, reverse=True)


def report_dir(day: str) -> Path:
    return REPORTS_ROOT / day


def load_summary(day: str) -> str | None:
    path = report_dir(day) / "summary.md"
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def load_items(day: str) -> list[dict[str, Any]]:
    folder = report_dir(day)
    items_dir = folder / "items"
    rows: list[dict[str, Any]] = []
    if items_dir.is_dir():
        for path in sorted(items_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    if rows:
        return rows
    combined = folder / "items.json"
    if combined.is_file():
        try:
            payload = json.loads(combined.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
    return []


def load_daily_updates(day: str) -> dict[str, dict[str, Any]]:
    folder = UPDATES_ROOT / day
    by_url: dict[str, dict[str, Any]] = {}
    if not folder.is_dir():
        return by_url
    files = ["all.json", "resmi_gazete.json", "sgk.json", "mevzuat.json"]
    for name in files:
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


def filter_items(items: list[dict[str, Any]], source: str) -> list[dict[str, Any]]:
    if source == "all":
        return items
    return [row for row in items if row.get("source") == source]


def department_codes(item: dict[str, Any]) -> list[str]:
    raw = item.get("departments") or (item.get("delivery") or {}).get("departments") or []
    return [str(code) for code in raw]


def department_chips(item: dict[str, Any]) -> str:
    depts = department_codes(item)
    if not depts:
        return "—"
    return " · ".join(department_label(code) for code in depts)


def department_badges_html(item: dict[str, Any]) -> str:
    depts = department_codes(item)
    if not depts:
        return '<span class="iso-chip">Birim yok</span>'
    return "".join(
        f'<span class="iso-badge">{html.escape(department_label(code))}</span>'
        for code in depts
    )


def old_text_for(item: dict[str, Any]) -> str:
    chunks = item.get("retrieved_chunks") or []
    if chunks:
        top = chunks[0]
        article = top.get("article") or top.get("chunk_id") or ""
        body = (top.get("text") or "").strip()
        if article and body:
            return f"{article}\n\n{body}"
        return body or article
    return ""


def new_text_for(item: dict[str, Any], daily: dict[str, dict[str, Any]]) -> str:
    url = str(item.get("url") or "")
    if url and url in daily:
        return (daily[url].get("raw_text") or "").strip()
    delivery = item.get("delivery") or {}
    return (delivery.get("summary") or item.get("relevance_reason") or "").strip()


def pipeline_env(fast_mock: bool) -> dict[str, str]:
    env = os.environ.copy()
    if fast_mock:
        env["ISO_PULSE_USE_MOCK_LLM"] = "true"
        env["OMP_NUM_THREADS"] = env.get("OMP_NUM_THREADS") or "1"
        env["MKL_NUM_THREADS"] = env.get("MKL_NUM_THREADS") or "1"
        env["TOKENIZERS_PARALLELISM"] = "false"
    return env


def pipeline_cmd(day: str, source: str, limit: int) -> list[str]:
    return [
        PYTHON,
        str(ROOT / "scripts" / "run_pipeline.py"),
        "--date",
        day,
        "--source",
        source,
        "--limit",
        str(limit),
    ]


def run_command(args: list[str], *, env: dict[str, str] | None = None) -> tuple[int, str]:
    proc = subprocess.run(
        args,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=None,
        env=env,
    )
    chunks = []
    if proc.stdout:
        chunks.append(proc.stdout)
    if proc.stderr:
        chunks.append(proc.stderr)
    return proc.returncode, "\n".join(chunks).strip()


def run_fetch_and_pipeline(
    day: str,
    source: str,
    *,
    limit: int,
    fast_mock: bool,
) -> tuple[int, str]:
    """Scrape the selected date, then run the LangGraph pipeline."""
    env = pipeline_env(fast_mock)
    fetch_cmd = [
        PYTHON,
        "-m",
        "src.ingestion.fetch_daily_updates",
        "--date",
        day,
        "--source",
        source,
        "--max-items",
        str(limit),
    ]
    pipe_cmd = pipeline_cmd(day, source, limit)
    sections: list[str] = ["$ " + " ".join(fetch_cmd)]
    fetch_code, fetch_log = run_command(fetch_cmd, env=env)
    if fetch_log:
        sections.append(fetch_log)
    sections.append(f"[fetch exit {fetch_code}]")
    sections.append("\n$ " + " ".join(pipe_cmd))
    pipeline_code, pipeline_log = run_command(pipe_cmd, env=env)
    if pipeline_log:
        sections.append(pipeline_log)
    sections.append(f"[pipeline exit {pipeline_code}]")
    code = 0 if fetch_code == 0 and pipeline_code == 0 else (pipeline_code or fetch_code)
    return code, "\n".join(sections).strip()


def remember_job(cmd: str, code: int, log: str) -> None:
    st.session_state["last_job"] = {"cmd": cmd, "code": code, "log": log}


@st.cache_resource(show_spinner=False)
def chroma_retriever():
    from mocks.retriever import retriever

    return retriever


def render_header() -> None:
    st.markdown(
        f"""
        <div class="iso-header">
          <div class="iso-kicker">İstanbul Sanayi Odası · Data-sovereign</div>
          <p class="iso-title">İSO Mevzuat Radar</p>
          <div style="color:#CBD5E1;font-size:0.92rem;">
            Günlük resmi kaynaklar → LangGraph ajanları → yönetici etki raporu
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def empty_state(message: str) -> None:
    st.info(message)


def compare_box(text: str, fallback: str) -> None:
    body = (text or "").strip() or fallback
    st.markdown(
        f'<div class="iso-compare">{html.escape(body)}</div>',
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="İSO Mevzuat Radar",
        page_icon="📡",
        layout="wide",
    )
    inject_css()
    render_header()

    report_dates = list_dated_dirs(REPORTS_ROOT)
    update_dates = list_dated_dirs(UPDATES_ROOT)
    known = sorted(set(report_dates + update_dates), reverse=True)

    with st.sidebar:
        st.markdown("### Kontroller")
        today = date.today()
        default_day = today
        if known:
            try:
                default_day = datetime.strptime(known[0], "%Y-%m-%d").date()
            except ValueError:
                default_day = today
        selected_day = st.date_input("Rapor tarihi", value=default_day)
        day = selected_day.isoformat()
        if known:
            st.caption("Kayıtlı klasörler: " + ", ".join(known[:10]))
        else:
            st.caption("Henüz `data/reports/` veya `data/daily_updates/` kaydı yok.")

        source_label = st.selectbox(
            "Kaynak",
            options=list(SOURCE_LABELS.keys()),
            format_func=lambda key: SOURCE_LABELS[key],
            index=0,
        )
        cli_source = source_label

        item_limit = st.slider(
            "Limit items",
            min_value=1,
            max_value=10,
            value=3,
            help="Kaç gazete/SGK kaydının LangGraph'tan geçeceği. Düşük tutun; Qwen tüm çekirdekleri doldurur.",
        )
        fast_mock = st.checkbox(
            "Fast Mock Mode",
            value=True,
            help="ISO_PULSE_USE_MOCK_LLM=true — Qwen / BGE-M3 çıkarımı olmadan UI akışını test eder.",
        )

        st.markdown("---")
        st.caption(
            "LLM: "
            + ("mock (fast)" if fast_mock or settings.use_mock_llm else settings.model_name)
        )
        st.caption(f"Chroma: `{settings.chroma_collection}` · pipeline --limit {item_limit}")

        fetch_clicked = st.button(
            "📥 Günlük Veri Çek (Fetch Scraper)",
            use_container_width=True,
            key="sidebar_fetch",
        )
        pipeline_clicked = st.button(
            "⚙️ Ajan Pipeline'ı Çalıştır (Run Pipeline)",
            use_container_width=True,
            key="sidebar_pipeline",
        )

    if fetch_clicked:
        cmd = [
            PYTHON,
            "-m",
            "src.ingestion.fetch_daily_updates",
            "--date",
            day,
            "--source",
            cli_source,
        ]
        with st.spinner("Scraper çalışıyor… resmi kaynaklar çekiliyor."):
            code, log = run_command(cmd)
        remember_job(" ".join(cmd), code, log)
        if code == 0:
            st.success(f"Günlük veri çekildi → `data/daily_updates/{day}/`")
        else:
            st.error(f"Scraper çıkış kodu {code}")

    if pipeline_clicked:
        cmd = pipeline_cmd(day, cli_source, item_limit)
        with st.spinner(
            f"LangGraph pipeline çalışıyor (--limit {item_limit}"
            f"{', mock' if fast_mock else ''})…"
        ):
            code, log = run_command(cmd, env=pipeline_env(fast_mock))
        remember_job(" ".join(cmd), code, log)
        if code == 0:
            st.success(f"Raporlar yazıldı → `data/reports/{day}/` ({item_limit} kayıt)")
            st.rerun()
        else:
            st.error(f"Pipeline çıkış kodu {code}")

    summary = load_summary(day)
    if not summary:
        st.warning(
            f"`data/reports/{day}/summary.md` bulunamadı. "
            "Bu tarih için henüz rapor üretilmemiş. Aşağıdaki düğmeyle scraper ve "
            "LangGraph ajan pipeline'ını sırayla çalıştırabilirsiniz."
        )
        _left, mid, _right = st.columns([0.12, 0.76, 0.12])
        with mid:
            run_today = st.button(
                "🚀 Bugünün Pipeline'ını Çalıştır (Fetch + Run Agent Pipeline)",
                type="primary",
                use_container_width=True,
                key="main_fetch_and_run",
            )
        if run_today:
            with st.spinner(
                "Günlük veriler çekiliyor ve LangGraph ajanları çalıştırılıyor... Lütfen bekleyin."
            ):
                code, log = run_fetch_and_pipeline(
                    day,
                    cli_source,
                    limit=item_limit,
                    fast_mock=fast_mock,
                )
            remember_job(
                f"fetch + pipeline --date {day} --source {cli_source} --limit {item_limit}",
                code,
                log,
            )
            if code == 0:
                st.success(f"Raporlar hazır → `data/reports/{day}/`")
                st.rerun()
            else:
                st.error(f"Pipeline tamamlanamadı (çıkış kodu {code}). Ayrıntı aşağıda.")

    last_job = st.session_state.get("last_job")
    if last_job:
        with st.expander("Son komut çıktısı", expanded=last_job.get("code", 0) != 0):
            st.code(last_job.get("cmd", ""))
            st.text(last_job.get("log") or "(çıktı yok)")

    items = filter_items(load_items(day), source_label)
    daily = load_daily_updates(day)
    relevant = [row for row in items if row.get("is_relevant")]
    review = [row for row in items if row.get("needs_review")]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rapor kaydı", len(items))
    c2.metric("Filtre geçti", len(relevant))
    c3.metric("İnceleme (verifier)", len(review))
    c4.metric("Tarih", day)

    tab_summary, tab_items, tab_chroma = st.tabs(
        [
            "📊 Yönetici Özeti",
            "🔍 Detaylı Maddeler & Diff",
            "🗄️ ChromaDB Baseline Arama",
        ]
    )

    with tab_summary:
        if not summary:
            empty_state(
                f"`data/reports/{day}/summary.md` bulunamadı. "
                "Önce scraper, ardından ajan pipeline'ını çalıştırın."
            )
        else:
            st.markdown(summary)

    with tab_items:
        if not items:
            empty_state(
                f"Bu tarih ve kaynak için madde raporu yok (`data/reports/{day}/items/`). "
                "Pipeline'ı çalıştırdıktan sonra kayıtlar burada listelenir."
            )
        else:
            for index, item in enumerate(items, start=1):
                title = item.get("title") or item.get("document_id") or f"Kayıt {index}"
                relevant_flag = "✓ ilgili" if item.get("is_relevant") else "✗ gürültü"
                with st.expander(f"{index}. {title}  ·  {relevant_flag}"):
                    meta1, meta2, meta3 = st.columns(3)
                    meta1.markdown(f"**Kategori:** {item.get('category') or '—'}")
                    meta2.markdown(
                        f"**Birim:** {department_badges_html(item)}",
                        unsafe_allow_html=True,
                    )
                    meta3.markdown(f"**Kaynak:** `{item.get('source') or '—'}`")
                    if item.get("url"):
                        st.caption(item["url"])
                    if item.get("retrieved_provision_id"):
                        st.caption(f"Baseline madde: `{item['retrieved_provision_id']}`")

                    left, right = st.columns(2)
                    old = old_text_for(item)
                    new = new_text_for(item, daily)
                    with left:
                        st.markdown('<div class="iso-label">Eski Kanun Maddesi (ChromaDB Baseline)</div>', unsafe_allow_html=True)
                        compare_box(old, "Baseline eşleşmesi yok.")
                    with right:
                        st.markdown('<div class="iso-label">Yeni Değişiklik Metni (Resmî Gazete / SGK)</div>', unsafe_allow_html=True)
                        compare_box(new, "Yeni metin bu raporda yok. Daily updates JSON'ını kontrol edin.")

                    st.markdown("##### Uzman ajan analizi")
                    analyses = item.get("analyses") or {}
                    if not analyses:
                        st.caption("Bu kayıt için uzman çıktısı yok (filtre düşürmüş veya Send yok).")
                    for dept, analysis in analyses.items():
                        if not isinstance(analysis, dict):
                            continue
                        label = department_label(str(dept))
                        st.markdown(
                            f'<div class="iso-dept-head">{html.escape(label)}</div>',
                            unsafe_allow_html=True,
                        )
                        st.markdown(f"- {analysis.get('obligation_change') or analysis.get('summary') or '—'}")
                        st.markdown(f"- {analysis.get('operational_impact') or '—'}")
                        if analysis.get("summary"):
                            st.caption(analysis["summary"])

                    st.markdown("##### Verifier onayı")
                    verification = item.get("verification") or {}
                    if not verification:
                        st.caption("Verifier çalışmadı (kayıt filtrede düşmüş olabilir).")
                    else:
                        v1, v2, v3 = st.columns(3)
                        passed = verification.get("passed")
                        v1.metric("Geçti", "Evet" if passed else "Hayır")
                        v2.metric("Hallüsinasyon", f"{float(verification.get('hallucination_score') or item.get('hallucination_score') or 0):.2f}")
                        v3.metric("İnceleme", "Evet" if verification.get("needs_review") or item.get("needs_review") else "Hayır")
                        notes = verification.get("notes") or ""
                        unsupported = verification.get("unsupported_claims") or []
                        if notes:
                            st.caption(notes)
                        if unsupported:
                            st.warning("Desteklenmeyen iddialar: " + "; ".join(map(str, unsupported)))

    with tab_chroma:
        st.markdown("Yerel koleksiyon `iso_mevzuat_baseline` üzerinde BGE-M3 anlamsal arama.")
        query = st.text_input(
            "Sorgu",
            placeholder="ör. kıdem tazminatı şartları ve bildirim süreleri",
        )
        top_k = st.slider("Sonuç sayısı (k)", min_value=1, max_value=10, value=5)
        search = st.button("Ara", type="primary")
        if search:
            if not query.strip():
                st.warning("Bir sorgu girin.")
            else:
                with st.spinner("Chroma sorgulanıyor…"):
                    try:
                        hits = chroma_retriever().query_baseline(query.strip(), k=top_k)
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Arama başarısız: {exc}")
                        hits = []
                if not hits:
                    empty_state(
                        "Eşleşme yok. `python3 scripts/index_mevzuat.py` ile baseline'ı indexleyin; "
                        "koleksiyon boşsa bellek içi tohum kullanılır."
                    )
                else:
                    for rank, hit in enumerate(hits, start=1):
                        sim = float(hit.get("similarity") or 0)
                        with st.expander(
                            f"#{rank}  benzerlik {sim:.3f}  ·  {hit.get('article') or hit.get('chunk_id')}"
                        ):
                            st.caption(
                                f"`{hit.get('chunk_id')}` · {hit.get('title') or ''} · "
                                f"{'aktif' if hit.get('is_active', True) else 'pasif'}"
                            )
                            st.write(hit.get("text") or "")


if __name__ == "__main__":
    main()
