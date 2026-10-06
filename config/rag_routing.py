"""RAG vs fallback routing from Chroma cosine similarity.

High-confidence baseline hits inject provision-level RAG context.
Low-confidence or empty hits skip Chroma injection and send the new
regulation text to the LLM for a general executive analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Sequence

RagMode = Literal["rag", "fallback"]

# Cosine similarity floor (1 - Chroma distance). Below this we do not treat
# a Chroma row as the matching old madde.
RAG_SIMILARITY_THRESHOLD = 0.45

RAG_STATUS_RAG = "🟢 Baseline Context Matched (RAG Enabled)"
RAG_STATUS_FALLBACK = "🟡 General Legal Analysis (Fallback Mode - Low Similarity)"


@dataclass(frozen=True)
class RagRouteDecision:
    mode: RagMode
    confidence: float
    status: str
    reason: str
    top_raw_similarity: float = 0.0

    @property
    def use_rag(self) -> bool:
        return self.mode == "rag"


def top_similarity(hits: Sequence[Mapping] | None) -> float:
    scores = [float(hit.get("similarity") or 0.0) for hit in (hits or [])]
    return max(scores) if scores else 0.0


def classify_rag_route(
    *,
    accepted_hits: Sequence[Mapping] | None,
    raw_hits: Sequence[Mapping] | None = None,
    bound_old_text: str | None = None,
    threshold: float = RAG_SIMILARITY_THRESHOLD,
) -> RagRouteDecision:
    """Decide whether specialists receive Chroma context or a fallback prompt."""
    accepted = list(accepted_hits or [])
    accepted_score = top_similarity(accepted)
    raw_score = top_similarity(raw_hits)
    has_bound = bool((bound_old_text or "").strip())

    if accepted and accepted_score >= threshold:
        return RagRouteDecision(
            mode="rag",
            confidence=accepted_score,
            status=RAG_STATUS_RAG,
            reason=(
                f"Top baseline similarity {accepted_score:.3f} "
                f">= {threshold:.2f}; injecting Chroma context for provision-level RAG."
            ),
            top_raw_similarity=raw_score or accepted_score,
        )
    if has_bound:
        return RagRouteDecision(
            mode="rag",
            confidence=max(accepted_score, 0.99),
            status=RAG_STATUS_RAG,
            reason="Bound previous version present; running provision-level RAG.",
            top_raw_similarity=raw_score,
        )
    return RagRouteDecision(
        mode="fallback",
        confidence=raw_score,
        status=RAG_STATUS_FALLBACK,
        reason=(
            f"No valid baseline (top similarity {raw_score:.3f} < {threshold:.2f} "
            "or empty). Bypassing RAG injection; LLM general analysis."
        ),
        top_raw_similarity=raw_score,
    )


def status_from_record(item: Mapping | None) -> tuple[str, float] | None:
    """Resolve a UI badge from a pipeline record or live graph result.

    Returns ``(status_label, confidence)`` or ``None`` when retrieval did not run
    (filtered noise / missing fields).
    """
    row = item or {}
    delivery = row.get("delivery") or {}
    if hasattr(delivery, "model_dump"):
        delivery = delivery.model_dump(mode="json")
    mode = row.get("rag_mode") or delivery.get("rag_mode")
    confidence = float(
        row.get("rag_confidence")
        if row.get("rag_confidence") is not None
        else delivery.get("rag_confidence") or 0.0
    )
    status = str(row.get("rag_status") or delivery.get("rag_status") or "")
    if mode == "rag":
        return status or RAG_STATUS_RAG, confidence
    if mode == "fallback":
        return status or RAG_STATUS_FALLBACK, confidence

    chunks = list(row.get("retrieved_chunks") or [])
    if chunks and top_similarity(chunks) >= RAG_SIMILARITY_THRESHOLD:
        return RAG_STATUS_RAG, top_similarity(chunks)
    if row.get("is_relevant"):
        return RAG_STATUS_FALLBACK, top_similarity(chunks)
    return None
