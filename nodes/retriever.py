from __future__ import annotations

import difflib

from config.rag_routing import RAG_SIMILARITY_THRESHOLD, classify_rag_route
from mocks.retriever import retriever
from schemas.outputs import AuditEvent
from schemas.state import PulseState
from src.ingestion.models import SGK_BASELINE_DOCUMENT_IDS

# Cosine similarity floor: do not treat a weak Chroma hit as "the" old madde.
MIN_RETRIEVAL_SIMILARITY = RAG_SIMILARITY_THRESHOLD
_STATUTE_IDS = ("4857", "5510", "6331", "6698", "4447", "4632", "5174")
_GENERIC_LEGAL = {
    "idari",
    "cezası",
    "cezasına",
    "halinde",
    "süresi",
    "süresinin",
    "madde",
    "hakkında",
    "zorundadır",
    "yükümlüdür",
    "uygulanır",
    "yürürlüğe",
    "kararı",
}


def _has_legal_connection(
    query: str,
    hit: dict,
    allowed_document_ids: list[str] | None = None,
) -> bool:
    """Reject a high-ish embedding that has no shared statute or tokens."""
    hit_doc = str(hit.get("document_id") or "")
    if allowed_document_ids and hit_doc in allowed_document_ids:
        return True
    query_blob = (query or "").casefold()
    hit_blob = (
        f"{hit.get('article') or ''}\n"
        f"{hit.get('text') or ''}\n"
        f"{hit.get('chunk_id') or ''}\n"
        f"{hit.get('title') or ''}\n"
        f"{hit_doc}"
    ).casefold()
    if any(sid in query_blob and sid in hit_blob for sid in _STATUTE_IDS):
        return True
    query_tokens = {
        part
        for part in query_blob.replace("'", " ").split()
        if len(part) > 4 and part not in _GENERIC_LEGAL
    }
    hit_tokens = {
        part
        for part in hit_blob.replace("'", " ").split()
        if len(part) > 4 and part not in _GENERIC_LEGAL
    }
    return len(query_tokens & hit_tokens) >= 2


def _unified_diff(old_text: str, new_text: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            (old_text or "").splitlines(),
            (new_text or "").splitlines(),
            fromfile="old",
            tofile="new",
            lineterm="",
        )
    )


def retriever_node(state: PulseState) -> dict:
    """Retriever node: score Chroma hits and choose RAG vs fallback.

    Queries `iso_mevzuat_baseline` via `mocks.retriever` (same collection /
    BGE-M3 path as `scripts/index_mevzuat.py`). High-confidence hits are
    injected as `old_text` for provision-level RAG. Low-confidence or empty
    hits leave `old_text` empty and set `rag_mode=fallback` so specialists
    skip Chroma context and ask the LLM for a general analysis.
    """
    query = f"{state.get('title') or ''}\n{state.get('new_text') or ''}".strip()
    document_ids = list(state.get("baseline_document_ids") or [])
    if state.get("source") == "sgk" and not document_ids:
        document_ids = list(SGK_BASELINE_DOCUMENT_IDS)
    raw_hits = retriever.query_baseline(query, k=5 if document_ids else 3, document_ids=document_ids or None)
    hits = [
        hit
        for hit in raw_hits
        if float(hit.get("similarity") or 0.0) >= MIN_RETRIEVAL_SIMILARITY
        and _has_legal_connection(query, hit, document_ids or None)
    ]
    route = classify_rag_route(
        accepted_hits=hits,
        raw_hits=raw_hits,
        bound_old_text=state.get("old_text"),
    )
    top = hits[0] if hits and route.use_rag else None

    existing_old = (state.get("old_text") or "").strip()
    retrieved_text = (top.get("text") or "").strip() if top else ""
    if route.use_rag:
        old_text = existing_old or retrieved_text or None
        stored_hits = hits
    else:
        # Bypass RAG injection: do not pass a weak Chroma row as old_text.
        old_text = existing_old or None
        stored_hits = []

    existing_diff = (state.get("diff") or "").strip()
    if existing_old and existing_diff:
        diff = state["diff"]
    elif route.use_rag and old_text:
        diff = _unified_diff(old_text, state.get("new_text") or "")
    else:
        diff = existing_diff

    labels = [
        f"{hit['chunk_id']}@{float(hit.get('similarity') or 0):.3f}"
        for hit in raw_hits
    ]
    kept = [f"{hit['chunk_id']}" for hit in stored_hits]
    detail = (
        f"mode={route.mode}; confidence={route.confidence:.3f}; "
        f"raw={len(raw_hits)}; kept={len(stored_hits)} floor={MIN_RETRIEVAL_SIMILARITY}; "
        f"top={labels[0] if labels else 'none'}; "
        f"accepted={','.join(kept) or 'none'}; "
        f"old_text={'kept' if existing_old else ('chroma' if retrieved_text else 'empty')}; "
        f"baseline={','.join(document_ids) or 'any'}"
    )
    return {
        "old_text": old_text,
        "diff": diff,
        "retrieved_chunks": stored_hits,
        "retrieved_provision_id": top["chunk_id"] if top else "",
        "rag_mode": route.mode,
        "rag_confidence": route.confidence,
        "rag_status": route.status,
        "rag_reason": route.reason,
        "audit_log": [
            AuditEvent(
                node="Retriever_Node",
                action="retrieve",
                detail=detail,
            )
        ],
    }
