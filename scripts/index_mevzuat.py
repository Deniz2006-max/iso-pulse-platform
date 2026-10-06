#!/usr/bin/env python3
"""Index baseline mevzuat JSON into a persistent local ChromaDB collection.

Reads every `data/mevzuat/*.json` file, skips repealed (`mulga`) provisions,
embeds active articles with BAAI/bge-m3, and upserts them in batches of 100.

Usage (from repository root):

    python3 scripts/index_mevzuat.py
    python3 scripts/index_mevzuat.py --skip-query
"""

from __future__ import annotations

import argparse
import inspect
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings

LOGGER = logging.getLogger("iso_pulse.index")

DEFAULT_MEVZUAT_DIR = ROOT / "data" / "mevzuat"
DEFAULT_PERSIST_DIR = Path(settings.chroma_persist_dir)
if not DEFAULT_PERSIST_DIR.is_absolute():
    DEFAULT_PERSIST_DIR = ROOT / DEFAULT_PERSIST_DIR
DEFAULT_COLLECTION = settings.chroma_collection
DEFAULT_MODEL = settings.embedding_model
BATCH_SIZE = 100
SAMPLE_QUERY = "kıdem tazminatı şartları ve bildirim süreleri"


@dataclass(frozen=True)
class ProvisionRecord:
    chroma_id: str
    document: str
    metadata: dict[str, str | bool]


def configure_logging(verbose: bool) -> None:
    try:
        from rich.logging import RichHandler

        logging.basicConfig(
            level=logging.DEBUG if verbose else logging.INFO,
            format="%(message)s",
            datefmt="%H:%M:%S",
            handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
        )
    except ImportError:
        logging.basicConfig(
            level=logging.DEBUG if verbose else logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
        )


def build_embedding_function(model_name: str):
    """Build BGE-M3 embeddings via Chroma's HuggingFace helper.

    HuggingFaceEmbeddingFunction talks to the Inference API in some Chroma
    versions and requires an API key. When no key is set, fall back to a
    local SentenceTransformer with the same model so indexing stays offline.
    """
    from chromadb.utils.embedding_functions import HuggingFaceEmbeddingFunction

    api_key = (
        os.getenv("HF_TOKEN")
        or os.getenv("HUGGINGFACEHUB_API_TOKEN")
        or os.getenv("CHROMA_HUGGINGFACE_API_KEY")
    )
    init_params = inspect.signature(HuggingFaceEmbeddingFunction.__init__).parameters
    kwargs: dict[str, Any] = {"model_name": model_name}
    if "api_key" in init_params:
        if api_key:
            kwargs["api_key"] = api_key
            LOGGER.info("Using HuggingFaceEmbeddingFunction (Inference API) model=%s", model_name)
            return HuggingFaceEmbeddingFunction(**kwargs)
        from chromadb.utils.embedding_functions import (
            SentenceTransformerEmbeddingFunction,
        )

        LOGGER.info(
            "No HF API key; using local SentenceTransformerEmbeddingFunction model=%s",
            model_name,
        )
        return SentenceTransformerEmbeddingFunction(
            model_name=model_name,
            normalize_embeddings=True,
        )
    LOGGER.info("Using HuggingFaceEmbeddingFunction model=%s", model_name)
    return HuggingFaceEmbeddingFunction(**kwargs)


def _as_meta_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def load_provisions(mevzuat_dir: Path) -> tuple[list[ProvisionRecord], int, int]:
    files = sorted(mevzuat_dir.glob("*.json"))
    LOGGER.info("Scanning %s JSON file(s) in %s", len(files), mevzuat_dir)

    records: list[ProvisionRecord] = []
    skipped_mulga = 0
    seen_ids: set[str] = set()

    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        documents = payload.get("documents") or []
        LOGGER.info("  %s — %s document(s)", path.name, len(documents))
        for document in documents:
            title = _as_meta_str(document.get("title"))
            document_id = _as_meta_str(document.get("document_id"))
            canonical_url = _as_meta_str(document.get("canonical_url"))
            for provision in document.get("included_provisions") or []:
                if provision.get("mulga") is True:
                    skipped_mulga += 1
                    continue
                provision_id = _as_meta_str(provision.get("provision_id")).strip()
                text = _as_meta_str(provision.get("text")).strip()
                if not provision_id or not text:
                    continue
                if provision_id in seen_ids:
                    LOGGER.warning("Duplicate provision_id skipped: %s", provision_id)
                    continue
                seen_ids.add(provision_id)
                label = _as_meta_str(provision.get("label"))
                heading = _as_meta_str(provision.get("heading")).strip()
                records.append(
                    ProvisionRecord(
                        chroma_id=provision_id,
                        document=f"[{title}] [{label}]"
                                 + (f" [{heading}]" if heading else "") + f"\n{text}",
                        metadata={
                            "document_id": document_id,
                            "title": title,
                            "canonical_url": canonical_url,
                            "provision_id": provision_id,
                            "label": label,
                            "heading": heading,
                            "madde_turu": _as_meta_str(provision.get("madde_turu")),
                            "normalized_hash": _as_meta_str(provision.get("normalized_hash")),
                        },
                    )
                )

    LOGGER.info(
        "Active provisions to index: %s | mülga skipped: %s",
        len(records),
        skipped_mulga,
    )
    return records, len(files), skipped_mulga


def batched(items: Sequence[ProvisionRecord], size: int) -> Iterable[Sequence[ProvisionRecord]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def get_collection(persist_dir: Path, collection_name: str, model_name: str):
    import chromadb

    persist_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(persist_dir))
    embedding_fn = build_embedding_function(model_name)
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )
    LOGGER.info("Collection '%s' at %s", collection_name, persist_dir)
    return client, collection


def upsert_records(collection, records: Sequence[ProvisionRecord], batch_size: int) -> None:
    total = len(records)
    if total == 0:
        LOGGER.warning("Nothing to upsert.")
        return

    try:
        from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn

        progress: Any = Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
        )
        progress.__enter__()
        task_id = progress.add_task("Embedding + upsert", total=total)
    except ImportError:
        progress = None
        task_id = None

    try:
        for batch_index, batch in enumerate(batched(records, batch_size), start=1):
            collection.upsert(
                ids=[row.chroma_id for row in batch],
                documents=[row.document for row in batch],
                metadatas=[row.metadata for row in batch],
            )
            done = min(batch_index * batch_size, total)
            if progress is not None:
                progress.update(task_id, advance=len(batch))
            else:
                LOGGER.info("Upserted batch %s (%s / %s)", batch_index, done, total)
    finally:
        if progress is not None:
            progress.__exit__(None, None, None)


def sample_query(collection, query: str, n_results: int = 2) -> None:
    LOGGER.info("Sample query: %s", query)
    result = collection.query(
        query_texts=[query],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )
    ids = (result.get("ids") or [[]])[0]
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    if not ids:
        LOGGER.warning("Query returned no hits.")
        return
    for rank, (chroma_id, document, metadata, distance) in enumerate(
        zip(ids, docs, metas, distances),
        start=1,
    ):
        similarity = 1.0 - float(distance)
        title = (metadata or {}).get("title", "")
        label = (metadata or {}).get("label", "")
        preview = " ".join((document or "").split())[:280]
        LOGGER.info(
            "  #%s  similarity=%.4f  id=%s  %s %s",
            rank,
            similarity,
            chroma_id,
            title,
            label,
        )
        LOGGER.info("      %s", preview)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Embed data/mevzuat JSON into a local ChromaDB collection.",
    )
    parser.add_argument(
        "--mevzuat-dir",
        type=Path,
        default=DEFAULT_MEVZUAT_DIR,
        help="Directory of baseline statute JSON files.",
    )
    parser.add_argument(
        "--persist-dir",
        type=Path,
        default=DEFAULT_PERSIST_DIR,
        help="Chroma persistent directory (default: data/chroma_db).",
    )
    parser.add_argument(
        "--collection",
        default=DEFAULT_COLLECTION,
        help="Collection name (default: iso_mevzuat_baseline).",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Embedding model (default: BAAI/bge-m3).",
    )
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument(
        "--skip-query",
        action="store_true",
        help="Skip the sample retrieval check after indexing.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.verbose)

    mevzuat_dir = args.mevzuat_dir
    if not mevzuat_dir.is_absolute():
        mevzuat_dir = ROOT / mevzuat_dir
    persist_dir = args.persist_dir
    if not persist_dir.is_absolute():
        persist_dir = ROOT / persist_dir

    if not mevzuat_dir.is_dir():
        LOGGER.error("Mevzuat directory not found: %s", mevzuat_dir)
        return 1

    records, file_count, skipped_mulga = load_provisions(mevzuat_dir)
    LOGGER.info(
        "Summary — files scanned: %s | active: %s | mülga skipped: %s",
        file_count,
        len(records),
        skipped_mulga,
    )
    if not records:
        LOGGER.error("No active provisions found.")
        return 1

    _client, collection = get_collection(persist_dir, args.collection, args.model)
    upsert_records(collection, records, args.batch_size)

    count = collection.count()
    LOGGER.info("ChromaDB record count in '%s': %s", args.collection, count)

    if not args.skip_query:
        sample_query(collection, SAMPLE_QUERY, n_results=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
