from __future__ import annotations

from unittest.mock import patch

from config.rag_routing import (
    RAG_SIMILARITY_THRESHOLD,
    RAG_STATUS_FALLBACK,
    RAG_STATUS_RAG,
    classify_rag_route,
    status_from_record,
)
from nodes.retriever import retriever_node
from nodes.specialist import run_specialist


def test_classify_high_confidence_uses_rag():
    decision = classify_rag_route(
        accepted_hits=[{"similarity": 0.81, "chunk_id": "law:4857:m41"}],
        raw_hits=[{"similarity": 0.81}],
    )
    assert decision.use_rag
    assert decision.mode == "rag"
    assert decision.status == RAG_STATUS_RAG
    assert decision.confidence >= RAG_SIMILARITY_THRESHOLD


def test_classify_low_confidence_falls_back():
    decision = classify_rag_route(
        accepted_hits=[],
        raw_hits=[{"similarity": 0.22, "chunk_id": "law:4857:m41"}],
    )
    assert not decision.use_rag
    assert decision.mode == "fallback"
    assert decision.status == RAG_STATUS_FALLBACK
    assert decision.confidence == 0.22


def test_classify_empty_hits_falls_back():
    decision = classify_rag_route(accepted_hits=[], raw_hits=[])
    assert decision.mode == "fallback"
    assert decision.confidence == 0.0


def test_bound_old_text_keeps_rag():
    decision = classify_rag_route(
        accepted_hits=[],
        raw_hits=[],
        bound_old_text="İş Kanunu madde 41 metni",
    )
    assert decision.mode == "rag"


def test_status_from_record_infers_legacy_chunks():
    badge = status_from_record(
        {
            "is_relevant": True,
            "retrieved_chunks": [{"similarity": 0.7, "chunk_id": "x"}],
        }
    )
    assert badge is not None
    assert badge[0] == RAG_STATUS_RAG


def test_retriever_fallback_skips_old_text_and_chunks():
    state = {
        "title": "Özel Tüketim Vergisi tutarları",
        "new_text": "Cumhurbaşkanı kararı ile bazı malların ÖTV tutarları güncellendi.",
        "old_text": None,
        "diff": "",
        "source": "resmi_gazete",
        "document_id": "iso:test-otv",
        "baseline_document_ids": [],
    }
    weak = [
        {
            "chunk_id": "law:4857:m41",
            "similarity": 0.21,
            "text": "Fazla çalışma ücreti",
            "document_id": "law:4857",
            "article": "m.41",
            "title": "İş Kanunu",
        }
    ]
    with patch("nodes.retriever.retriever.query_baseline", return_value=weak):
        out = retriever_node(state)
    assert out["rag_mode"] == "fallback"
    assert out["rag_status"] == RAG_STATUS_FALLBACK
    assert not out["retrieved_chunks"]
    assert not out["old_text"]
    assert out["retrieved_provision_id"] == ""


def test_retriever_high_confidence_injects_baseline():
    state = {
        "title": "Özel Tüketim Vergisi tutarları",
        "new_text": "ÖTV tutarları bazı mallar için yeniden belirlendi.",
        "old_text": None,
        "diff": "",
        "source": "resmi_gazete",
        "document_id": "iso:test-otv-hit",
        "baseline_document_ids": [],
    }
    strong = [
        {
            "chunk_id": "law:4760:m1",
            "similarity": 0.88,
            "text": "Özel tüketim vergisi tutarları ekli listelerde gösterilir.",
            "document_id": "law:4760",
            "article": "ÖTV m.1",
            "title": "Özel Tüketim Vergisi Kanunu",
        }
    ]
    with patch("nodes.retriever.retriever.query_baseline", return_value=strong):
        out = retriever_node(state)
    assert out["rag_mode"] == "rag"
    assert out["rag_status"] == RAG_STATUS_RAG
    assert out["retrieved_chunks"]
    assert "Özel tüketim" in (out["old_text"] or "")


def test_specialist_fallback_does_not_call_chroma():
    state = {
        "title": "Karar 11822 ÖTV",
        "new_text": "Bazı mallara uygulanan özel tüketim vergisi tutarları güncellendi.",
        "old_text": None,
        "diff": "",
        "source": "resmi_gazete",
        "document_id": "iso:otv-fallback",
        "rag_mode": "fallback",
        "rag_confidence": 0.21,
        "rag_status": RAG_STATUS_FALLBACK,
        "retrieved_chunks": [],
        "analyses": {},
        "audit_log": [],
    }
    with patch("nodes.specialist.retriever.retrieve") as retrieve:
        out = run_specialist(state, "mali")
        retrieve.assert_not_called()
    analysis = out["analyses"]["mali"]
    assert analysis.analysis_mode == "fallback"
    assert analysis.rag_chunk_ids == []
    assert len(analysis.obligation_change) > 40
    assert "Aksiyon" in analysis.operational_impact
    from config.executive_copy import has_executive_structure

    assert has_executive_structure(analysis.summary)
