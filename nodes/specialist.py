from __future__ import annotations

from config.executive_copy import (
    coerce_executive_summary,
    grounded_action,
    grounded_obligation,
    is_generic_executive_copy,
    list_allowed_date_tokens,
    usable_model_copy,
)
from config.prompts import SPECIALIST_FALLBACK_ADDENDUM, SPECIALIST_NO_MATCH, SPECIALIST_SYSTEMS
from config.rag_routing import RAG_SIMILARITY_THRESHOLD
from config.relevance import audience_scope, is_administrative_out_of_scope, is_financial_corporate_keep
from mocks.llm import complete
from mocks.retriever import LawChunk, retriever
from schemas.outputs import AuditEvent, Department, DepartmentAnalysis, department_label
from schemas.state import PulseState

NO_MATCH_TEXT = SPECIALIST_NO_MATCH
MIN_RETRIEVAL_SIMILARITY = RAG_SIMILARITY_THRESHOLD


def _is_rag_mode(state: PulseState) -> bool:
    mode = str(state.get("rag_mode") or "")
    if mode == "fallback":
        return False
    if mode == "rag":
        return True
    accepted = [
        hit
        for hit in (state.get("retrieved_chunks") or [])
        if float(hit.get("similarity") or 0.0) >= MIN_RETRIEVAL_SIMILARITY
    ]
    has_fixture_old = bool((state.get("old_text") or "").strip()) and str(
        state.get("document_id") or ""
    ).startswith(("ik-", "hukuk-", "multi-", "demo-"))
    return bool(accepted or has_fixture_old)


def run_specialist(
    state: PulseState,
    department: Department,
    extra_instructions: str = "",
) -> dict:
    """Retrieve active law chunks, compare old vs new, write one department analysis."""
    rag_mode = _is_rag_mode(state)
    query = f"{state['title']}\n{state['new_text']}"
    accepted_ids = {
        str(hit.get("chunk_id"))
        for hit in (state.get("retrieved_chunks") or [])
        if float(hit.get("similarity") or 0.0) >= MIN_RETRIEVAL_SIMILARITY
    }
    has_fixture_old = bool((state.get("old_text") or "").strip()) and str(
        state.get("document_id") or ""
    ).startswith(("ik-", "hukuk-", "multi-", "demo-"))

    chunks: list[LawChunk] = []
    if rag_mode and (accepted_ids or has_fixture_old):
        chunks = retriever.retrieve(query, department)
        injected = [
            {
                "chunk_id": str(hit.get("chunk_id") or ""),
                "department": department,
                "text": str(hit.get("text") or ""),
                "is_active": True,
                "article": str(hit.get("article") or hit.get("chunk_id") or ""),
            }
            for hit in (state.get("retrieved_chunks") or [])
            if hit.get("text")
        ]
        if injected:
            seen = {chunk["chunk_id"] for chunk in chunks}
            for extra in injected:
                if extra["chunk_id"] not in seen:
                    chunks.append(extra)  # type: ignore[arg-type]
                    seen.add(extra["chunk_id"])
        if accepted_ids:
            chunks = [chunk for chunk in chunks if chunk["chunk_id"] in accepted_ids]
        elif not has_fixture_old:
            chunks = []

    rag_match = rag_mode and (bool(chunks) or has_fixture_old)
    chunk_ids = [chunk["chunk_id"] for chunk in chunks]
    system_prompt = SPECIALIST_SYSTEMS[department]
    if not rag_match:
        system_prompt = f"{system_prompt}\n{SPECIALIST_FALLBACK_ADDENDUM.strip()}"
    if extra_instructions.strip():
        system_prompt = f"{system_prompt}\n{extra_instructions.strip()}"
    analysis = complete(
        DepartmentAnalysis,
        system_prompt,
        _analysis_user_prompt(state, department, chunks, rag_match=rag_match),
        context={
            "document_id": state["document_id"],
            "title": state["title"],
            "old_text": state.get("old_text") if rag_match else None,
            "new_text": state["new_text"],
            "department": department,
            "rag_chunk_ids": chunk_ids if rag_match else [],
            "rag_match": rag_match,
            "rag_mode": "rag" if rag_match else "fallback",
        },
    )
    if not rag_match:
        analysis = analysis.model_copy(
            update={
                "department": department,
                "summary": _ensure_no_match_notice(analysis.summary, state, department),
                "obligation_change": _ensure_ozet(analysis.obligation_change, state),
                "operational_impact": _ensure_action(
                    analysis.operational_impact, department, state
                ),
                "rag_chunk_ids": [],
                "analysis_mode": "fallback",
            }
        )
    else:
        analysis = analysis.model_copy(
            update={
                "department": department,
                "summary": _ensure_summary(analysis.summary, state, department),
                "obligation_change": _ensure_ozet(analysis.obligation_change, state),
                "operational_impact": _ensure_action(
                    analysis.operational_impact, department, state
                ),
                "rag_chunk_ids": analysis.rag_chunk_ids or chunk_ids,
                "analysis_mode": "rag",
            }
        )
    node_names = {"ik": "IK_Node", "hukuk": "Hukuk_Node", "mali": "Mali_Node"}
    chunk_ids_label = ",".join(chunk_ids) or "none"
    mode_label = "rag" if rag_match else "fallback"
    return {
        "analyses": {department: analysis},
        "audit_log": [
            AuditEvent(
                node=node_names[department],
                action="analyze",
                detail=(
                    f"mode={mode_label}; rag_match={rag_match}; "
                    f"rag_chunks={chunk_ids_label}"
                ),
            )
        ],
    }


def _analysis_user_prompt(
    state: PulseState,
    department: Department,
    chunks: list[LawChunk],
    *,
    rag_match: bool,
) -> str:
    floor = MIN_RETRIEVAL_SIMILARITY
    confidence = float(state.get("rag_confidence") or 0.0)
    if rag_match and chunks:
        rag_block = "\n".join(
            f"- VALID [{chunk['chunk_id']}] {chunk['article']}: {chunk['text']}"
            for chunk in chunks
        )
        match_rule = (
            "RAG MODE (high confidence). Use the baseline context for a detailed "
            "provision-level diff, impact, and action items. "
            "Write Eski durum vs Yeni durum in obligation_change."
        )
        old_text = state.get("old_text") or "(no previous version)"
        rag_section = f"RAG:\n{rag_block}\n\n"
    else:
        match_rule = (
            "FALLBACK MODE (low similarity / no match). Bypass RAG context.\n"
            "READ new_text. Write a HIGH-DETAIL executive `summary` with ALL "
            "three headings: Önemli Düzenlemeler & Maddeler; Sanayi ve "
            "İşverene Etkisi; Sorumlu Departman İçin Aksiyon Maddeleri.\n"
            "Extract numbers, madde/code refs, percentages, geography, and "
            "sector scope. Minimum 3+2+3 bullets.\n"
            "FORBIDDEN: title-only 'yürürlüğe konulmuştur', "
            "'ilgili departman metni incelemelidir', "
            "'sanayi işverenini bağlayan resmi bir düzenlemedir'.\n"
            "obligation_change lists operative maddeler/oranlar from new_text.\n"
            f"operational_impact is numbered Aksiyon steps for {department_label(department)}.\n"
            "Do not invent a baseline madde or attach unrelated Chroma chunks."
        )
        old_text = "(RAG bypassed — no baseline context injected)"
        rag_section = (
            "RAG:\n(bypassed — do not use İş Kanunu m.41, SGK, or any seed chunk)\n\n"
        )
    dates = list_allowed_date_tokens(
        str(state.get("title") or ""), str(state.get("new_text") or "")
    )
    date_rule = (
        "DATE LOCK: copy dates/years only from this allow-list (or omit dates). "
        "Do not use RAG chunk dates unless they also appear here: "
        + (", ".join(dates) if dates else "(no date token in new_text)")
        + ".\n"
    )
    specialized = ""
    title = str(state.get("title") or "")
    new_text = str(state.get("new_text") or "")
    scope = str(state.get("sector_scope") or "") or audience_scope(title, new_text)
    if is_administrative_out_of_scope(title, new_text):
        specialized = (
            "ADMINISTRATIVE / OUT OF SCOPE (TMMOB, Chamber Rules, Public Personnel, "
            "or court decisions unrelated to commercial/labour law). "
            "output EXACTLY this action block:\n"
            "Sorumlu Departman İçin Aksiyon Maddeleri:\n"
            "1. Herhangi bir aksiyon gerekmemektedir (Kurum içi / Kamusal düzenleme).\n"
            "Do NOT write private-sector HR, bordro, or maliye steps.\n"
        )
    elif is_financial_corporate_keep(title, new_text):
        specialized = (
            "AUDIENCE = industrial compliance (MASAK/AML, tax, customs, TTK). "
            "This is NOT kamu personeli. Do NOT output the kamu no-action sentence. "
            "Write Maliye/Hukuk compliance steps for manufacturers and traders.\n"
        )
    elif scope == "kamu":
        specialized = (
            "AUDIENCE = Düşük / Kamu Kurumları Kapsamı. Do NOT write private "
            "factory HR/finance tasks. First Aksiyon MUST be: "
            "Bu düzenleme kamu personeline/kurumlarına yönelik olup, özel sektör "
            "sanayi işletmeleri için doğrudan bir aksiyon yükümlülüğü doğurmamaktadır.\n"
        )
    elif scope == "specialized":
        specialized = (
            "SECTOR SCOPE = Düşük / Özel Sektör Kapsamı. Name the sub-sector "
            "(nükleer / sivil havacılık / gıda-alkol kodeksi / noterlik). "
            "Do NOT write generic İSO factory HR, bordro, or maliye actions. "
            "Typical manufacturing plants are out of scope.\n"
        )
    return (
        f"department: {department}\n"
        f"document_id: {state['document_id']}\n"
        f"title: {state['title']}\n"
        f"similarity_floor: {floor}\n"
        f"rag_confidence: {confidence:.3f}\n"
        f"rag_mode: {'rag' if rag_match else 'fallback'}\n"
        f"rag_status: {state.get('rag_status') or ''}\n\n"
        f"{date_rule}{specialized}"
        f"{match_rule}\n\n"
        f"old_text:\n{old_text}\n\n"
        f"new_text:\n{state['new_text']}\n\n"
        f"diff:\n{state['diff'] if rag_match else '(RAG bypassed)'}\n\n"
        f"{rag_section}"
        "Analyze ONLY from this department's operational perspective.\n"
        "Bu değişiklikle sanayicinin üzerindeki hukuki ve operasyonel "
        "yükümlülük nasıl değişmiştir?"
    )


def _ensure_summary(summary: str, state: PulseState, department: Department) -> str:
    extra = (summary or "").replace(NO_MATCH_TEXT, "").strip(" .")
    return coerce_executive_summary(
        extra,
        str(state.get("title") or ""),
        str(state.get("new_text") or ""),
        department,
    )


def _ensure_no_match_notice(
    summary: str, state: PulseState, department: Department
) -> str:
    return _ensure_summary(summary, state, department)


def _ensure_ozet(obligation: str, state: PulseState) -> str:
    text = usable_model_copy(obligation.replace(NO_MATCH_TEXT, "") if obligation else "")
    if text and len(text) > 60 and not is_generic_executive_copy(text):
        return text
    return grounded_obligation(
        str(state.get("title") or ""),
        str(state.get("new_text") or ""),
    )


def _ensure_action(impact: str, department: Department, state: PulseState) -> str:
    title = str(state.get("title") or "")
    new_text = str(state.get("new_text") or "")
    if is_administrative_out_of_scope(title, new_text) or is_financial_corporate_keep(
        title, new_text
    ) or audience_scope(title, new_text) in {"kamu", "specialized"}:
        return grounded_action(department, title, new_text)
    text = usable_model_copy(impact.replace(NO_MATCH_TEXT, "") if impact else "")
    if text and len(text) > 40 and not is_generic_executive_copy(text):
        return text
    return grounded_action(department, title, new_text)
