from __future__ import annotations

from config.prompts import SPECIALIST_SYSTEMS
from mocks.llm import complete
from mocks.retriever import LawChunk, retriever
from schemas.outputs import AuditEvent, Department, DepartmentAnalysis
from schemas.state import PulseState


def run_specialist(state: PulseState, department: Department) -> dict:
    """Retrieve active law chunks, compare old vs new, write one department analysis."""
    query = f"{state['title']}\n{state['new_text']}"
    chunks = retriever.retrieve(query, department)
    analysis = complete(
        DepartmentAnalysis,
        SPECIALIST_SYSTEMS[department],
        _analysis_user_prompt(state, department, chunks),
        context={
            "document_id": state["document_id"],
            "title": state["title"],
            "old_text": state.get("old_text"),
            "new_text": state["new_text"],
            "department": department,
            "rag_chunk_ids": [chunk["chunk_id"] for chunk in chunks],
        },
    )
    node_names = {"ik": "IK_Node", "hukuk": "Hukuk_Node", "mali": "Mali_Node"}
    chunk_ids = ",".join(chunk["chunk_id"] for chunk in chunks) or "none"
    return {
        "analyses": {department: analysis},
        "audit_log": [
            AuditEvent(
                node=node_names[department],
                action="analyze",
                detail=f"rag_chunks={chunk_ids}",
            )
        ],
    }


def _analysis_user_prompt(
    state: PulseState,
    department: Department,
    chunks: list[LawChunk],
) -> str:
    rag_block = "\n".join(
        f"- [{chunk['chunk_id']}] {chunk['article']}: {chunk['text']}"
        for chunk in chunks
    ) or "(no active chunks)"
    old_text = state.get("old_text") or "(no previous version)"
    return (
        f"department: {department}\n"
        f"document_id: {state['document_id']}\n"
        f"title: {state['title']}\n\n"
        f"old_text:\n{old_text}\n\n"
        f"new_text:\n{state['new_text']}\n\n"
        f"diff:\n{state['diff']}\n\n"
        f"RAG (is_active=true):\n{rag_block}\n\n"
        "Bu değişiklikle sanayicinin üzerindeki hukuki ve operasyonel "
        "yükümlülük nasıl değişmiştir?"
    )
