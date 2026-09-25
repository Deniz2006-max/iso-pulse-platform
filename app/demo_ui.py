"""İSO PULSE — enterprise Streamlit demo dashboard.

Run from the repository root:

    streamlit run app/demo_ui.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings
from graph import graph
from main import prepare_state
from schemas.outputs import URGENCY_LABELS

MEVZUAT_DIR = ROOT / "data" / "mevzuat"

NAVY = "#003366"
NAVY_DEEP = "#002244"
GOLD = "#C5A572"
BG = "#F8FAFC"
CARD_BORDER = "#E2E8F0"
TEXT = "#1E293B"
MUTED = "#64748B"

DEPARTMENT_LABELS = {
    "ik": "HR (İK)",
    "hukuk": "Legal (Hukuk)",
    "mali": "Finance (Maliye)",
}

SEVERITY_STYLES = {
    "critical": ("Critical", "#991B1B", "#FEE2E2"),
    "medium": ("Medium", "#92400E", "#FEF3C7"),
    "low": ("Low", "#166534", "#DCFCE7"),
}

CUSTOM_SCENARIO = "Custom Scenario (Manual Input)"

SCENARIO_NAMES = [
    "Labor Law 4857 - Maternity/Paternity Leave Amendment",
    "Social Security Law 5510 - Manufacturing Sector Incentive Update",
    "KVKK 6698 - Personal Data Processing Conditions Regulation",
    CUSTOM_SCENARIO,
]


def _load_provision(filename: str, provision_id: str) -> dict[str, str]:
    path = MEVZUAT_DIR / filename
    payload = json.loads(path.read_text(encoding="utf-8"))
    document = payload["documents"][0]
    for provision in document.get("included_provisions") or []:
        if provision.get("provision_id") == provision_id:
            text = " ".join((provision.get("text") or "").split())
            return {
                "law_title": document.get("title", ""),
                "label": provision.get("label", ""),
                "provision_id": provision_id,
                "text": text,
            }
    raise KeyError(f"Provision {provision_id} not found in {filename}")


def _inventory() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not MEVZUAT_DIR.exists():
        return rows
    for path in sorted(MEVZUAT_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        document = (payload.get("documents") or [{}])[0]
        rows.append(
            {
                "file": path.name,
                "title": document.get("title", path.stem),
                "document_id": document.get("document_id", ""),
                "provisions": len(document.get("included_provisions") or []),
            }
        )
    return rows


@st.cache_data(show_spinner=False)
def corpus_inventory() -> list[dict[str, Any]]:
    return _inventory()


@st.cache_data(show_spinner=False)
def scenario_catalog() -> dict[str, dict[str, Any]]:
    labor = _load_provision("4857_is_kanunu.json", "law:4857:article:74")
    sgk = _load_provision("5510_sosyal_sigortalar.json", "law:5510:gecici-madde:108")
    kvkk = _load_provision("6698_kvkk.json", "law:6698:article:5")

    return {
        SCENARIO_NAMES[0]: {
            "document_id": "demo-4857-maternity",
            "title": "4857 sayılı İş Kanunu Madde 74 analık / babalık izni değişikliği",
            "reference": "Law No. 4857, Article 74",
            "category": "Labor & Social Policy",
            "old_text": labor["text"],
            "gazette": (
                "T.C. RESMÎ GAZETE\n"
                "Sayı: 32780  |  Kanun No: 4857 (Değişiklik)\n\n"
                "MADDE 1 – 22/5/2003 tarihli ve 4857 sayılı İş Kanununun 74 üncü maddesi "
                "aşağıdaki şekilde değiştirilmiştir.\n\n"
                "Madde 74 – Kadın işçilerin doğumdan önce sekiz ve doğumdan sonra onaltı "
                "hafta olmak üzere toplam yirmidört haftalık süre için çalıştırılmamaları "
                "esastır. Çoğul gebelikte doğum öncesi süreye iki hafta eklenir.\n\n"
                "Doğum sonrası analık izninin bitimini izleyen on iş günü içinde, çocuğun "
                "hayatta olması kaydıyla, aynı işyerinde çalışan baba işçiye on iş günü "
                "ücretli babalık izni verilir. Bu süre yıllık ücretli izin hakkından düşülemez.\n\n"
                "İşveren, analık ve babalık izni kullanan işçinin işe dönüşünde aynı veya "
                "eşdeğer pozisyonu korumak, vardiya ve fazla çalışma planını on beş gün "
                "önceden güncellemek ve izin sürelerini işçinin özlük dosyası ile bordroya "
                "işlemek zorundadır.\n\n"
                "MADDE 2 – Bu Kanun yayımı tarihinde yürürlüğe girer.\n"
            ),
        },
        SCENARIO_NAMES[1]: {
            "document_id": "demo-5510-manufacturing",
            "title": "5510 sayılı Kanun imalat sektörü prim teşviki güncellemesi",
            "reference": "Law No. 5510, Provisional Article 108 / Article 81",
            "category": "Social Security Incentives",
            "old_text": sgk["text"],
            "gazette": (
                "T.C. RESMÎ GAZETE\n"
                "Sayı: 32781  |  5510 sayılı Sosyal Sigortalar ve Genel Sağlık Sigortası Kanunu\n\n"
                "MADDE 1 – 31/5/2006 tarihli ve 5510 sayılı Kanunun geçici 108 inci maddesi "
                "aşağıdaki şekilde değiştirilmiştir.\n\n"
                "GEÇİCİ MADDE 108 – 81 inci maddenin birinci fıkrasının (ı) bendinin birinci "
                "cümlesinde yer alan “iki” ibaresi; işverenin imalat sektöründe faaliyet "
                "göstermesi halinde “altı” olarak uygulanır.\n\n"
                "İmalat işyerlerinde, prime esas kazanç alt sınırı üzerinden hesaplanan "
                "işveren hissesi prim teşviki, SGK'ya süresinde verilen aylık prim ve hizmet "
                "belgesi ile e-bildirge kaydı şartıyla uygulanır. Teşvikten yararlanan "
                "işveren, bordro ve muhasebe kayıtlarında teşvik kodunu ayrıca göstermek "
                "zorundadır.\n\n"
                "Uygulama 31/12/2027 tarihine kadar devam eder. Cumhurbaşkanı süreyi "
                "31/12/2028 tarihine kadar uzatmaya yetkilidir.\n\n"
                "MADDE 2 – Bu madde yayımı tarihinde yürürlüğe girer.\n"
            ),
        },
        SCENARIO_NAMES[2]: {
            "document_id": "demo-6698-processing",
            "title": "6698 sayılı KVKK kişisel veri işleme şartları düzenlemesi",
            "reference": "Law No. 6698, Article 5",
            "category": "Data Protection / Compliance",
            "old_text": kvkk["text"],
            "gazette": (
                "T.C. RESMÎ GAZETE\n"
                "Sayı: 32782  |  6698 sayılı Kişisel Verilerin Korunması Kanunu\n\n"
                "MADDE 1 – 24/3/2016 tarihli ve 6698 sayılı Kanunun 5 inci maddesine "
                "aşağıdaki fıkra eklenmiştir.\n\n"
                "(3) İşverenler, çalışanlara ve ziyaretçilere ait kişisel verileri işyerinde "
                "PDKS, kamera ve erişim kontrol sistemleri üzerinden işledikleri takdirde; "
                "açık rıza veya 5 inci maddenin ikinci fıkrasındaki şartlardan hangisine "
                "dayandıklarını yazılı olarak kayıt altına almak, aydınlatma metnini işe "
                "girişte tebliğ etmek ve işleme amacının sona ermesinden itibaren azami "
                "on iki ay içinde verileri silmek, yok etmek veya anonim hale getirmek "
                "zorundadır.\n\n"
                "Veri sorumlusu sıfatını haiz sanayi işletmeleri, bu yükümlülüğe aykırılık "
                "halinde Kurul tarafından belirlenecek idari tedbir ve para cezalarına tabidir.\n\n"
                "MADDE 2 – Bu Kanun yayımı tarihinde yürürlüğe girer.\n"
            ),
        },
        CUSTOM_SCENARIO: {
            "document_id": "demo-custom",
            "title": "Custom Official Gazette submission",
            "reference": "User-supplied instrument",
            "category": "Unclassified / Manual",
            "old_text": "",
            "gazette": (
                "T.C. RESMÎ GAZETE\n"
                "Sayı: ____\n\n"
                "Paste or draft the simulated Official Gazette text here.\n"
            ),
        },
    }


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    return {"value": str(value)}


def inject_css() -> None:
    st.markdown(
        f"""
        <style>
        html, body, .stApp {{
            font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
            color: {TEXT};
        }}
        .stApp {{
            background: {BG};
        }}
        [data-testid="stHeader"] {{
            background: transparent;
        }}
        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {NAVY} 0%, {NAVY_DEEP} 100%);
        }}
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] .stCaption,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{
            color: #F8FAFC !important;
        }}
        [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div,
        [data-testid="stSidebar"] textarea {{
            background: rgba(255,255,255,0.08) !important;
            color: #F8FAFC !important;
            border-radius: 12px !important;
            border: 1px solid rgba(255,255,255,0.18) !important;
        }}
        [data-testid="stSidebar"] .stButton > button {{
            background: {GOLD};
            color: {NAVY_DEEP};
            font-weight: 700;
            border: 0;
            border-radius: 12px;
            padding: 0.7rem 1rem;
            box-shadow: 0 8px 20px rgba(0,0,0,0.18);
            width: 100%;
        }}
        [data-testid="stSidebar"] .stButton > button:hover {{
            background: #d4b57f;
        }}
        .iso-header {{
            background: {NAVY};
            color: white;
            border-radius: 12px;
            padding: 1.35rem 1.6rem;
            box-shadow: 0 10px 28px rgba(0, 51, 102, 0.18);
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            flex-wrap: wrap;
            gap: 1rem;
            margin-bottom: 1.1rem;
        }}
        .iso-kicker {{
            letter-spacing: 0.14em;
            font-size: 0.72rem;
            color: {GOLD};
            font-weight: 700;
            text-transform: uppercase;
        }}
        .iso-title {{
            font-size: 1.45rem;
            font-weight: 700;
            margin: 0.2rem 0 0 0;
        }}
        .iso-badge {{
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(197,165,114,0.45);
            border-radius: 999px;
            padding: 0.45rem 0.85rem;
            font-size: 0.86rem;
            white-space: nowrap;
        }}
        .iso-card {{
            background: #FFFFFF;
            border: 1px solid {CARD_BORDER};
            border-radius: 12px;
            padding: 1.2rem 1.3rem 1.1rem 1.3rem;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06);
            margin-bottom: 1rem;
        }}
        .iso-card h3 {{
            color: {NAVY};
            margin: 0 0 0.75rem 0;
            font-size: 1.05rem;
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
        .iso-severity {{
            display: inline-block;
            border-radius: 999px;
            padding: 0.28rem 0.8rem;
            font-weight: 700;
            font-size: 0.82rem;
        }}
        .iso-muted {{
            color: {MUTED};
            font-size: 0.86rem;
        }}
        .iso-compare {{
            background: {BG};
            border-radius: 12px;
            padding: 0.85rem 1rem;
            border: 1px solid {CARD_BORDER};
            font-size: 0.9rem;
            line-height: 1.45;
        }}
        .iso-label {{
            font-size: 0.72rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: {MUTED};
            font-weight: 700;
            margin-bottom: 0.35rem;
        }}
        .block-container {{
            padding-top: 1.4rem;
            max-width: 1200px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(corpus_count: int) -> None:
    st.markdown(
        f"""
        <div class="iso-header">
          <div>
            <div class="iso-kicker">Istanbul Chamber of Industry</div>
            <p class="iso-title">İSO PULSE - AI-Driven Regulatory Radar Dashboard</p>
            <div class="iso-muted" style="color:#CBD5E1;">
              Regulatory Radar &amp; AI Agentic Platform · {corpus_count} consolidated statutes in local RAG
            </div>
          </div>
          <div class="iso-badge">🟢 System Online | Local RAG Ready</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def run_workflow(scenario_name: str, gazette_text: str, catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    spec = catalog[scenario_name]
    state = prepare_state(
        {
            "document_id": spec["document_id"],
            "source": "resmi_gazete",
            "title": spec["title"],
            "old_text": spec.get("old_text") or None,
            "new_text": gazette_text.strip(),
        }
    )
    return graph.invoke(state)


def render_router_card(result: dict[str, Any], spec: dict[str, Any]) -> None:
    departments = result.get("departments") or []
    chips = "".join(
        f'<span class="iso-chip">{DEPARTMENT_LABELS.get(dept, dept)}</span>'
        for dept in departments
    ) or '<span class="iso-chip">No specialist dispatch</span>'
    relevant = result.get("is_relevant", False)
    reason = result.get("relevance_reason") or "—"
    verdict = "Relevant — dispatched to core-domain specialists" if relevant else "Filtered as industrial noise"
    st.markdown(
        f"""
        <div class="iso-card">
          <h3>Card 1 · Router Agent Verdict</h3>
          <div class="iso-label">Regulatory categorization</div>
          <p><strong>{spec['category']}</strong> · {spec['reference']}</p>
          <div class="iso-label">Targeted departments</div>
          <p>{chips}</p>
          <div class="iso-label">Filter decision</div>
          <p>{verdict}</p>
          <p class="iso-muted">{reason}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_department_card(result: dict[str, Any], spec: dict[str, Any]) -> None:
    analyses = result.get("analyses") or {}
    old_preview = (spec.get("old_text") or "No baseline provision was bound to this scenario.")[:700]
    new_preview = (result.get("new_text") or "")[:700]
    st.markdown(
        '<div class="iso-card"><h3>Card 2 · Department Agent Summaries</h3>'
        '<div class="iso-label">Provision-level old vs. new comparative analysis</div></div>',
        unsafe_allow_html=True,
    )
    left, right = st.columns(2)
    with left:
        st.markdown(
            f'<div class="iso-compare"><div class="iso-label">Baseline (local corpus)</div>'
            f"{old_preview}</div>",
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            f'<div class="iso-compare"><div class="iso-label">Simulated Official Gazette</div>'
            f"{new_preview}</div>",
            unsafe_allow_html=True,
        )

    if not analyses:
        st.info("No department specialist was invoked. The router treated this as noise or found no core-domain match.")
        return

    for department, raw in analyses.items():
        analysis = _as_dict(raw)
        st.markdown(
            f"""
            <div class="iso-card">
              <span class="iso-chip">{DEPARTMENT_LABELS.get(department, department)}</span>
              <p><strong>{analysis.get('summary') or '—'}</strong></p>
              <div class="iso-label">Obligation change</div>
              <p>{analysis.get('obligation_change') or '—'}</p>
              <div class="iso-label">Actionable recommendations for İSO members &amp; internal operations</div>
              <p>{analysis.get('operational_impact') or '—'}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_delivery_card(result: dict[str, Any], spec: dict[str, Any]) -> None:
    delivery = _as_dict(result.get("delivery"))
    verification = _as_dict(result.get("verification"))
    if not delivery and not result.get("is_relevant", False):
        st.markdown(
            """
            <div class="iso-card">
              <h3>Card 3 · Delivery &amp; Verification</h3>
              <p>Workflow stopped after the relevance filter. No delivery payload was emitted.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    urgency = delivery.get("urgency") or result.get("urgency") or "low"
    label, fg, bg = SEVERITY_STYLES.get(urgency, SEVERITY_STYLES["low"])
    tr_label = URGENCY_LABELS.get(urgency, label)
    score = float(result.get("hallucination_score", delivery.get("hallucination_score", 0.0)) or 0.0)
    confidence = max(0, min(100, round((1.0 - score) * 100)))
    passed = verification.get("passed")
    if passed is None:
        passed = not bool(delivery.get("needs_review", result.get("needs_review")))
    check = (
        f"{confidence}% Confidence — Hallucination Check Passed"
        if passed
        else f"{confidence}% Confidence — Hallucination Check Flagged (needs review)"
    )

    citations: list[str] = [spec["reference"]]
    for raw in (result.get("analyses") or {}).values():
        analysis = _as_dict(raw)
        citations.extend(analysis.get("citations") or [])
        citations.extend(analysis.get("rag_chunk_ids") or [])
    unique_refs = []
    for item in citations:
        if item and item not in unique_refs:
            unique_refs.append(item)
    refs = "".join(f'<span class="iso-chip">{item}</span>' for item in unique_refs[:8])

    st.markdown(
        f"""
        <div class="iso-card">
          <h3>Card 3 · Delivery &amp; Verification</h3>
          <div class="iso-label">Severity level</div>
          <p><span class="iso-severity" style="color:{fg};background:{bg};">{label} · {tr_label}</span></p>
          <div class="iso-label">Groundedness / confidence score</div>
          <p><strong>{check}</strong></p>
          <p class="iso-muted">{delivery.get('summary') or verification.get('notes') or ''}</p>
          <div class="iso-label">Reference provision mapping</div>
          <p>{refs}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="İSO PULSE | Regulatory Radar",
        page_icon="⬤",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_css()
    catalog = scenario_catalog()
    inventory = corpus_inventory()
    render_header(len(inventory))

    if "scenario_name" not in st.session_state:
        st.session_state.scenario_name = SCENARIO_NAMES[0]
        st.session_state.gazette_text = catalog[SCENARIO_NAMES[0]]["gazette"]

    with st.sidebar:
        st.markdown("### Control Panel")
        st.caption("Select a pre-configured İSO member scenario or draft a custom Official Gazette event.")
        selected = st.selectbox(
            "Test scenarios",
            SCENARIO_NAMES,
            key="scenario_select",
        )
        if selected != st.session_state.scenario_name:
            st.session_state.scenario_name = selected
            st.session_state.gazette_text = catalog[selected]["gazette"]

        st.text_area(
            "Simulated Official Gazette text",
            key="gazette_text",
            height=280,
        )
        trigger = st.button("🚀 Trigger Legislation Radar & Agent Workflow")

        st.markdown("---")
        llm_mode = "Mock LLM" if settings.use_mock_llm else f"ChatOllama · {settings.model_name}"
        st.caption(f"Runtime: {llm_mode}")
        st.caption("Local corpus")
        for row in inventory:
            st.caption(f"• {row['title']} ({row['provisions']} provisions)")

    spec = catalog[st.session_state.scenario_name]
    if trigger:
        if not (st.session_state.gazette_text or "").strip():
            st.warning("Please provide Official Gazette text before triggering the workflow.")
        else:
            with st.spinner("Agents analyzing regulatory updates and cross-referencing ChromaDB..."):
                st.session_state.result = run_workflow(
                    st.session_state.scenario_name,
                    st.session_state.gazette_text,
                    catalog,
                )
                st.session_state.result_spec = spec

    result = st.session_state.get("result")
    result_spec = st.session_state.get("result_spec")
    if not result:
        st.markdown(
            """
            <div class="iso-card">
              <h3>Awaiting a legislation event</h3>
              <p class="iso-muted">
                Choose a test scenario from the control panel and trigger the agent workflow.
                The router will dispatch only to departments whose core regulatory domain is
                directly amended, then specialist agents will compare the baseline corpus
                provision with the simulated Official Gazette text.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    render_router_card(result, result_spec)
    render_department_card(result, result_spec)
    render_delivery_card(result, result_spec)

    with st.expander("Audit trail"):
        events = []
        for event in result.get("audit_log") or []:
            events.append(_as_dict(event))
        st.json(events)


if __name__ == "__main__":
    main()
