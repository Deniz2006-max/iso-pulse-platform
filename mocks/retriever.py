"""Chroma-backed and in-memory retrievers.

Specialists call `retriever.retrieve(query, department)`. The graph-level
`retriever_node` calls `retriever.query_baseline(query)` so the baseline
provision is injected before routing.

Chroma queries reuse `scripts.index_mevzuat.get_collection` (same BGE-M3
embedding function and `iso_mevzuat_baseline` collection). If the persistent
DB is missing or empty, the in-memory seed corpus is used.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypedDict

from schemas.outputs import Department

LOGGER = logging.getLogger("iso_pulse.retriever")

ROOT = Path(__file__).resolve().parent.parent


class LawChunk(TypedDict):
    """One Chroma-like chunk. Only is_active=True rows are retrieved."""

    chunk_id: str
    department: Department
    text: str
    is_active: bool
    article: str


class BaselineHit(TypedDict):
    """Top-k hit from the statute collection (graph retriever node)."""

    chunk_id: str
    article: str
    text: str
    document_id: str
    title: str
    similarity: float
    is_active: bool


_SEED_CHUNKS: list[LawChunk] = [
    {
        "chunk_id": "ik-isk-41-active",
        "department": "ik",
        "is_active": True,
        "article": "İş Kanunu m.41",
        "text": (
            "Yürürlükteki İş Kanunu m.41: fazla çalışmanın yıllık üst sınırı, "
            "yazılı/elektronik belgeleme ve SGK'ya bildirim yükümlülüğü."
        ),
    },
    {
        "chunk_id": "ik-isk-41-passive",
        "department": "ik",
        "is_active": False,
        "article": "İş Kanunu m.41 (eski)",
        "text": (
            "Pasif versiyon: fazla çalışma süresi bir yılda iki yüz yetmiş saati "
            "aşamaz. Bu kayıt is_active=false olduğu için RAG'e girmez."
        ),
    },
    {
        "chunk_id": "ik-sgk-board-active",
        "department": "ik",
        "is_active": True,
        "article": "SGK / 5510 bildirim usulü",
        "text": (
            "5510 sayılı Kanun: işveren ücret ve fazla çalışma bildirimlerini "
            "SGK'ya süresi içinde vermekle yükümlüdür. Geç bildirim idari para "
            "cezasına yol açabilir."
        ),
    },
    {
        "chunk_id": "ik-4447-unemp-active",
        "department": "ik",
        "is_active": True,
        "article": "4447 İşsizlik Sigortası",
        "text": (
            "4447 sayılı İşsizlik Sigortası Kanunu: işveren işsizlik sigortası "
            "primini ve kısa çalışma / işsizlik ödeneği bildirimlerini süresi "
            "içinde Kuruma vermekle yükümlüdür."
        ),
    },
    {
        "chunk_id": "hukuk-cevre-8-active",
        "department": "hukuk",
        "is_active": True,
        "article": "Çevre İzin Yönetmeliği m.8",
        "text": (
            "Çevre izin belgesinin geçerlilik süresi, yenileme başvuru penceresi "
            "ve belgesiz faaliyette durdurma ile idari para cezası yaptırımı."
        ),
    },
    {
        "chunk_id": "hukuk-cevre-8-passive",
        "department": "hukuk",
        "is_active": False,
        "article": "Çevre İzin Yönetmeliği m.8 (eski)",
        "text": "Pasif versiyon: belge beş yıl geçerlidir, doksan gün önce yenilenir.",
    },
    {
        "chunk_id": "mali-gv-istisna-active",
        "department": "mali",
        "is_active": True,
        "article": "Gelir Vergisi ücret istisnası",
        "text": (
            "Asgari ücrete kadar olan ücretlerin gelir vergisi istisnası ve "
            "bordro/stopaj hesaplarına etkisi."
        ),
    },
    {
        "chunk_id": "mali-asgari-teblig-active",
        "department": "mali",
        "is_active": True,
        "article": "Asgari ücret tebliği",
        "text": (
            "Yürürlükteki net asgari ücret tutarı ve işverenin fark ödemesini "
            "izleyen bordroda yansıtma yükümlülüğü."
        ),
    },
]


_SEED_DOCUMENT_IDS = {
    "ik-isk-41-active": "law:4857",
    "ik-isk-41-passive": "law:4857",
    "ik-sgk-board-active": "law:5510",
    "ik-4447-unemp-active": "law:4447",
    "hukuk-cevre-8-active": "law:2872",
    "hukuk-cevre-8-passive": "law:2872",
    "mali-gv-istisna-active": "law:193",
    "mali-asgari-teblig-active": "law:193",
}


def _seed_document_id(chunk: LawChunk) -> str:
    return _SEED_DOCUMENT_IDS.get(chunk["chunk_id"], chunk["chunk_id"])


def _overlap_score(query: str, chunk: LawChunk) -> int:
    tokens = {part for part in query.lower().replace("'", " ").split() if len(part) > 3}
    haystack = f"{chunk['text']} {chunk['article']}".lower()
    return sum(1 for token in tokens if token in haystack)


def _unpack_query(result: dict[str, Any]) -> list[BaselineHit]:
    ids = (result.get("ids") or [[]])[0]
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    hits: list[BaselineHit] = []
    for chroma_id, document, metadata, distance in zip(ids, docs, metas, distances):
        meta = metadata or {}
        label = str(meta.get("label") or "")
        title = str(meta.get("title") or "")
        article = " ".join(part for part in (title, label) if part).strip() or str(chroma_id)
        text = document or ""
        if "\n" in text:
            text = text.split("\n", 1)[-1]
        hits.append(
            {
                "chunk_id": str(chroma_id),
                "article": article,
                "text": text,
                "document_id": str(meta.get("document_id") or ""),
                "title": title,
                "similarity": 1.0 - float(distance),
                "is_active": True,
            }
        )
    return hits


@dataclass
class InMemoryChromaRetriever:
    """Stand-in for ChromaDB when the persistent collection is empty."""

    chunks: list[LawChunk] = field(default_factory=lambda: list(_SEED_CHUNKS))

    def retrieve(
        self,
        query: str,
        department: Department,
        k: int = 3,
    ) -> list[LawChunk]:
        eligible = [
            chunk
            for chunk in self.chunks
            if chunk["is_active"] and chunk["department"] == department
        ]
        ranked = sorted(
            eligible,
            key=lambda chunk: _overlap_score(query, chunk),
            reverse=True,
        )
        return ranked[:k]

    def query_baseline(
        self,
        query: str,
        k: int = 3,
        document_ids: list[str] | None = None,
    ) -> list[BaselineHit]:
        eligible = [chunk for chunk in self.chunks if chunk["is_active"]]
        if document_ids:
            allowed = set(document_ids)
            scoped = [
                chunk
                for chunk in eligible
                if _seed_document_id(chunk) in allowed
            ]
            eligible = scoped or eligible
        ranked = sorted(
            eligible,
            key=lambda chunk: _overlap_score(query, chunk),
            reverse=True,
        )
        ranked = [chunk for chunk in ranked if _overlap_score(query, chunk) > 0]
        hits: list[BaselineHit] = []
        for chunk in ranked[:k]:
            hits.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "article": chunk["article"],
                    "text": chunk["text"],
                    "document_id": _seed_document_id(chunk),
                    "title": chunk["article"],
                    "similarity": min(1.0, _overlap_score(query, chunk) / 8.0),
                    "is_active": True,
                }
            )
        return hits


class ChromaBaselineRetriever:
    """Queries the persistent `iso_mevzuat_baseline` collection via the indexer."""

    def __init__(self) -> None:
        self._collection: Any | None = None
        self._failed = False

    def _load_collection(self) -> Any | None:
        if self._failed:
            return None
        if self._collection is not None:
            return self._collection
        try:
            from config.settings import settings
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Cannot load settings for Chroma: %s", exc)
            self._failed = True
            return None

        persist = Path(settings.chroma_persist_dir)
        if not persist.is_absolute():
            persist = ROOT / persist
        sqlite = persist / "chroma.sqlite3"
        if not sqlite.is_file():
            LOGGER.info("No Chroma SQLite at %s; using in-memory retriever", sqlite)
            self._failed = True
            return None
        try:
            import chromadb

            bare_client = chromadb.PersistentClient(path=str(persist))
            bare = bare_client.get_collection(name=settings.chroma_collection)
            count = bare.count()
        except Exception as exc:  # noqa: BLE001
            LOGGER.info("Chroma collection not ready (%s); using in-memory retriever", exc)
            self._failed = True
            return None
        if count <= 0:
            LOGGER.info("Chroma collection is empty; using in-memory retriever")
            self._failed = True
            return None
        try:
            from scripts.index_mevzuat import get_collection

            _client, collection = get_collection(
                persist, settings.chroma_collection, settings.embedding_model
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Chroma embedding client unavailable: %s", exc)
            self._failed = True
            return None
        LOGGER.info("Chroma retriever ready (%s records)", count)
        self._collection = collection
        return collection

    def query_baseline(
        self,
        query: str,
        k: int = 3,
        document_ids: list[str] | None = None,
    ) -> list[BaselineHit]:
        collection = self._load_collection()
        if collection is None or not (query or "").strip():
            return []
        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": max(1, k),
            "include": ["documents", "metadatas", "distances"],
        }
        if document_ids:
            kwargs["where"] = {"document_id": {"$in": list(document_ids)}}
        try:
            result = collection.query(**kwargs)
        except Exception as exc:  # noqa: BLE001
            LOGGER.info("Chroma where-filter failed (%s); retrying unscoped", exc)
            kwargs.pop("where", None)
            result = collection.query(**kwargs)
        hits = _unpack_query(result)
        if document_ids:
            scoped = [hit for hit in hits if hit.get("document_id") in document_ids]
            return scoped or hits
        return hits

    def retrieve(
        self,
        query: str,
        department: Department,
        k: int = 3,
    ) -> list[LawChunk]:
        from config.routing import core_departments

        hits = self.query_baseline(query, k=max(k * 3, 6))
        if not hits:
            return []
        matched: list[LawChunk] = []
        fallback: list[LawChunk] = []
        for hit in hits:
            blob = f"{hit['article']}\n{hit['text']}"
            inferred = core_departments(blob)
            chunk: LawChunk = {
                "chunk_id": hit["chunk_id"],
                "department": department,
                "text": hit["text"],
                "is_active": True,
                "article": hit["article"],
            }
            fallback.append(chunk)
            if not inferred or department in inferred:
                matched.append(chunk)
        return (matched or fallback)[:k]


@dataclass
class CompositeRetriever:
    """Prefer live Chroma; fall back to the in-memory seed corpus."""

    memory: InMemoryChromaRetriever = field(default_factory=InMemoryChromaRetriever)
    chroma: ChromaBaselineRetriever = field(default_factory=ChromaBaselineRetriever)

    def retrieve(
        self,
        query: str,
        department: Department,
        k: int = 3,
    ) -> list[LawChunk]:
        hits = self.chroma.retrieve(query, department, k=k)
        if hits:
            return hits
        return self.memory.retrieve(query, department, k=k)

    def query_baseline(
        self,
        query: str,
        k: int = 3,
        document_ids: list[str] | None = None,
    ) -> list[BaselineHit]:
        hits = self.chroma.query_baseline(query, k=k, document_ids=document_ids)
        if hits:
            return hits
        return self.memory.query_baseline(query, k=k, document_ids=document_ids)


retriever = CompositeRetriever()
