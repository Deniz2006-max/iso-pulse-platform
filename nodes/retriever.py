from __future__ import annotations

import difflib

from mocks.retriever import retriever
from schemas.outputs import AuditEvent
from schemas.state import PulseState
from src.ingestion.models import SGK_BASELINE_DOCUMENT_IDS

# Cosine similarity floor: do not treat a weak Chroma hit as "the" old madde.
MIN_RETRIEVAL_SIMILARITY = 0.45
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
    """Retriever node: top matching active provision (v1.0) from Chroma.

    Queries `iso_mevzuat_baseline` via `mocks.retriever` (same collection /
    BGE-M3 path as `scripts/index_mevzuat.py`). Injects the hit as `old_text`
    when the incoming state has no prior version, and always stores the
    retrieved chunks for specialists and the verifier.
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
    top = hits[0] if hits else None

    existing_old = (state.get("old_text") or "").strip()
    retrieved_text = (top.get("text") or "").strip() if top else ""
    # Never inject a weak / unrelated baseline as old_text.
    old_text = existing_old or retrieved_text or None

    existing_diff = (state.get("diff") or "").strip()
    if existing_old and existing_diff:
        diff = state["diff"]
    elif old_text:
        diff = _unified_diff(old_text, state.get("new_text") or "")
    else:
        diff = existing_diff

    labels = [
        f"{hit['chunk_id']}@{float(hit.get('similarity') or 0):.3f}"
        for hit in raw_hits
    ]
    kept = [f"{hit['chunk_id']}" for hit in hits]
    detail = (
        f"raw={len(raw_hits)}; kept={len(hits)} floor={MIN_RETRIEVAL_SIMILARITY}; "
        f"top={labels[0] if labels else 'none'}; "
        f"accepted={','.join(kept) or 'none'}; "
        f"old_text={'kept' if existing_old else ('chroma' if retrieved_text else 'empty')}; "
        f"baseline={','.join(document_ids) or 'any'}"
    )
    return {
        "old_text": old_text,
        "diff": diff,
        "retrieved_chunks": hits,
        "retrieved_provision_id": top["chunk_id"] if top else "",
        "audit_log": [
            AuditEvent(
                node="Retriever_Node",
                action="retrieve",
                detail=detail,
            )
        ],
    }
