from __future__ import annotations

from config.prompts import SPECIALIST_NO_MATCH, SPECIALIST_SYSTEMS
from mocks.llm import complete
from mocks.retriever import LawChunk, retriever
from nodes.retriever import MIN_RETRIEVAL_SIMILARITY
from schemas.outputs import AuditEvent, Department, DepartmentAnalysis, department_label
from schemas.state import PulseState

NO_MATCH_TEXT = SPECIALIST_NO_MATCH


def run_specialist(
    state: PulseState,
    department: Department,
    extra_instructions: str = "",
) -> dict:
    """Retrieve active law chunks, compare old vs new, write one department analysis."""
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
    if accepted_ids or has_fixture_old:
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

    rag_match = bool(chunks) or has_fixture_old
    chunk_ids = [chunk["chunk_id"] for chunk in chunks]
    system_prompt = SPECIALIST_SYSTEMS[department]
    if extra_instructions.strip():
        system_prompt = f"{system_prompt}\n{extra_instructions.strip()}"
    analysis = complete(
        DepartmentAnalysis,
        system_prompt,
        _analysis_user_prompt(state, department, chunks, rag_match=rag_match),
        context={
            "document_id": state["document_id"],
            "title": state["title"],
            "old_text": state.get("old_text"),
            "new_text": state["new_text"],
            "department": department,
            "rag_chunk_ids": chunk_ids,
            "rag_match": rag_match,
        },
    )
    if not rag_match:
        analysis = analysis.model_copy(
            update={
                "department": department,
                "summary": _ensure_no_match_notice(analysis.summary),
                "obligation_change": _ensure_ozet(analysis.obligation_change, state),
                "operational_impact": _ensure_action(
                    analysis.operational_impact, department, state
                ),
                "rag_chunk_ids": [],
            }
        )
    else:
        analysis = analysis.model_copy(
            update={
                "department": department,
                "rag_chunk_ids": analysis.rag_chunk_ids or chunk_ids,
            }
        )
    node_names = {"ik": "IK_Node", "hukuk": "Hukuk_Node", "mali": "Mali_Node"}
    chunk_ids_label = ",".join(chunk_ids) or "none"
    return {
        "analyses": {department: analysis},
        "audit_log": [
            AuditEvent(
                node=node_names[department],
                action="analyze",
                detail=f"rag_match={rag_match}; rag_chunks={chunk_ids_label}",
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
    if rag_match and chunks:
        rag_block = "\n".join(
            f"- VALID [{chunk['chunk_id']}] {chunk['article']}: {chunk['text']}"
            for chunk in chunks
        )
        match_rule = (
            "VALID match. Write Eski durum vs Yeni durum in obligation_change."
        )
        old_text = state.get("old_text") or "(no previous version)"
    else:
        rag_block = (
            "(no valid baseline match — do not use İş Kanunu m.41, SGK, or any "
            "unrelated seed chunk)"
        )
        label = department_label(department)
        match_rule = (
            f"NO VALID MATCH. Put this sentence in summary:\n{NO_MATCH_TEXT}\n"
            f"Then analyze the NEW text only.\n"
            f"obligation_change MUST start with 'Özet & Değişiklik:' (2 sentences).\n"
            f"operational_impact MUST start with 'Birim Aksiyonu ({label}):' "
            "and list concrete department steps. Do not invent a baseline madde."
        )
        old_text = "(no valid previous version)"
    return (
        f"department: {department}\n"
        f"document_id: {state['document_id']}\n"
        f"title: {state['title']}\n"
        f"similarity_floor: {MIN_RETRIEVAL_SIMILARITY}\n"
        f"rag_match: {rag_match}\n\n"
        f"{match_rule}\n\n"
        f"old_text:\n{old_text}\n\n"
        f"new_text:\n{state['new_text']}\n\n"
        f"diff:\n{state['diff']}\n\n"
        f"RAG:\n{rag_block}\n\n"
        "Analyze ONLY from this department's operational perspective.\n"
        "Bu değişiklikle sanayicinin üzerindeki hukuki ve operasyonel "
        "yükümlülük nasıl değişmiştir?"
    )


def _ensure_no_match_notice(summary: str) -> str:
    text = (summary or "").strip()
    if NO_MATCH_TEXT in text and len(text) > len(NO_MATCH_TEXT) + 10:
        return text
    extra = text.replace(NO_MATCH_TEXT, "").strip(" .")
    if extra:
        return f"{NO_MATCH_TEXT} {extra}"
    return NO_MATCH_TEXT


def _ensure_ozet(obligation: str, state: PulseState) -> str:
    text = (obligation or "").strip()
    if text and text != NO_MATCH_TEXT and "Özet" in text:
        return text
    title = str(state.get("title") or "Yeni düzenleme")
    body = str(state.get("new_text") or "").strip()
    snippet = body.split("\n", 1)[0][:180] if body else title
    return (
        f"Özet & Değişiklik: {title} yürürlüğe girer. "
        f"Taban kanunda doğrudan madde eşleşmesi yoktur; yükümlülük yeni metinden "
        f"doğar ({snippet})."
    )


def _ensure_action(impact: str, department: Department, state: PulseState) -> str:
    text = (impact or "").strip()
    if text and text != NO_MATCH_TEXT and "Aksiyon" in text:
        return text
    label = department_label(department)
    title = str(state.get("title") or "yeni karar")
    verbs = {
        "mali": (
            "vergi/tarife tutarlarını ve muhasebe-ERP kodlarını güncelleyin, "
            "ilk beyannamede yeni oranı doğrulayın"
        ),
        "ik": (
            "personel/özlük ve sözleşme şablonlarını gözden geçirin, "
            "bordro ve SGK süreçlerini yeni esasa göre uyarlayın"
        ),
        "hukuk": (
            "uyum kontrol listesini ve ilgili sözleşmeleri güncelleyin, "
            "yürürlük tarihini takip edin"
        ),
    }
    return f"Birim Aksiyonu ({label}): {verbs[department]}. Kaynak: {title}."
