#!/usr/bin/env python3
"""OCR retained SGK image-only PDFs without changing the source index."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from pypdf import PdfReader

from collectors.common import CollectionError, atomic_write, canonical_json, sha256_bytes, utc_now
from collectors.sgk import UNIT


def _tool(command: str) -> str:
    resolved = shutil.which(command)
    if not resolved:
        raise CollectionError(f"required OCR tool not found: {command}")
    return resolved


def _run(args: list[str], *, timeout: int = 120) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CollectionError(f"OCR command failed: {args[0]}: {exc}") from exc
    if result.returncode:
        raise CollectionError(f"OCR command failed: {args[0]}: {result.stderr.strip()[:500]}")
    return result.stdout.strip() or result.stderr.strip()


def ocr_pdf(raw: bytes, *, tesseract: str, pdftoppm: str) -> tuple[str, int]:
    """OCR every page with Turkish model; text is unverified extraction."""
    if not raw.startswith(b"%PDF-"):
        raise CollectionError("OCR input is not a PDF")
    with tempfile.TemporaryDirectory(prefix="iso-sgk-ocr-") as temporary:
        folder = Path(temporary)
        source = folder / "source.pdf"
        source.write_bytes(raw)
        try:
            pages = len(PdfReader(source).pages)
        except Exception as exc:
            raise CollectionError(f"cannot read OCR PDF: {exc}") from exc
        if not 1 <= pages <= 50:
            raise CollectionError(f"OCR page count outside pilot limit: {pages}")
        chunks = []
        for number in range(1, pages + 1):
            image = folder / f"page-{number:03d}"
            _run([pdftoppm, "-f", str(number), "-l", str(number), "-r", "250",
                  "-png", "-singlefile", str(source), str(image)])
            png = image.with_suffix(".png")
            if not png.is_file():
                raise CollectionError(f"PDF renderer did not produce page {number}")
            text = _run([tesseract, str(png), "stdout", "-l", "tur", "--psm", "3"])
            if not text:
                raise CollectionError(f"OCR returned no text for page {number}")
            chunks.append(f"[Sayfa {number}]\n{text}")
        return "\n\n".join(chunks), pages


def run_ocr(page: int, output: Path, *, tesseract_cmd: str = "tesseract",
            pdftoppm_cmd: str = "pdftoppm") -> list[dict]:
    if page < 1:
        raise ValueError("page must be >= 1")
    page_dir = output / "sgk" / UNIT / f"page-{page:03d}"
    index_path = page_dir / "index.json"
    index_raw = index_path.read_bytes()
    index = json.loads(index_raw)
    if index.get("source") != "sgk" or index.get("page") != page or not index.get("source_capture_complete"):
        raise CollectionError("SGK index is missing or incomplete")
    targets = [(record, attachment) for record in index["records"]
               for attachment in record["attachments"] if attachment["text_status"] == "needs_ocr"]
    if not targets:
        return []
    tesseract = _tool(tesseract_cmd)
    pdftoppm = _tool(pdftoppm_cmd)
    if "tur" not in _run([tesseract, "--list-langs"]).splitlines():
        raise CollectionError("Tesseract Turkish language model ('tur') is not installed")
    engine_version = _run([tesseract, "--version"]).splitlines()[0]
    renderer_version = _run([pdftoppm, "-v"]) or "see renderer executable"
    results = []
    root = page_dir.resolve()
    for record, attachment in targets:
        source = (page_dir / attachment["raw_path"]).resolve()
        if not source.is_relative_to(root) or not source.is_file():
            raise CollectionError("SGK attachment path is missing or outside page directory")
        raw = source.read_bytes()
        if sha256_bytes(raw) != attachment["raw_sha256"]:
            raise CollectionError("SGK attachment hash does not match index")
        text, pages = ocr_pdf(raw, tesseract=tesseract, pdftoppm=pdftoppm)
        run_id = utc_now().replace(":", "-").replace("+", "-")
        result_dir = page_dir / "ocr-runs" / attachment["raw_sha256"] / run_id
        text_path = result_dir / "text.txt"
        metadata_path = result_dir / "metadata.json"
        text_bytes = (text + "\n").encode("utf-8")
        metadata = {"schema_version": 1, "source": "sgk", "kind": "ocr_enrichment",
                    "source_record_id": record["source_record_id"],
                    "attachment_url": attachment["url"],
                    "source_index_sha256": sha256_bytes(index_raw),
                    "source_pdf_sha256": attachment["raw_sha256"],
                    "source_pdf_path": attachment["raw_path"], "page_count": pages,
                    "ocr_text_sha256": sha256_bytes(text_bytes),
                    "ocr_text_path": str(text_path.relative_to(page_dir)).replace("\\", "/"),
                    "ocr_engine": engine_version, "renderer": renderer_version,
                    "language": "tur", "dpi": 250, "status": "ocr_unverified",
                    "requires_human_review": True, "processed_at": utc_now()}
        atomic_write(text_path, text_bytes)
        atomic_write(metadata_path, canonical_json(metadata) + b"\n")
        results.append({"metadata": str(metadata_path), "pages": pages,
                        "characters": len(text), "status": metadata["status"]})
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--output", type=Path, default=Path("var/collectors"))
    parser.add_argument("--tesseract", default="tesseract")
    parser.add_argument("--pdftoppm", default="pdftoppm")
    args = parser.parse_args()
    try:
        print(json.dumps(run_ocr(args.page, args.output, tesseract_cmd=args.tesseract,
                                 pdftoppm_cmd=args.pdftoppm), ensure_ascii=False))
    except (CollectionError, OSError, ValueError, json.JSONDecodeError, KeyError) as exc:
        print(f"SGK OCR failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
