from __future__ import annotations

import asyncio
import io
import logging
import re
from html import unescape

from bs4 import BeautifulSoup, NavigableString, Tag

LOGGER = logging.getLogger("iso_pulse.ingestion.extract")
for _noisy in (
    "pdfminer",
    "pdfminer.pdfinterp",
    "pdfminer.pdfpage",
    "pdfminer.psparser",
    "pdfminer.pdfdocument",
    "pdfminer.converter",
    "pypdf",
):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

DEFAULT_MAX_PDF_PAGES = 40

_DROP_TAGS = {"script", "style", "noscript", "svg", "iframe", "form"}
_BLOCK_TAGS = {
    "p",
    "div",
    "br",
    "tr",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "table",
    "section",
    "article",
}


def tr_fold(value: str) -> str:
    """Case-fold Turkish text without mapping i → I."""
    table = str.maketrans(
        {
            "i": "İ",
            "ı": "I",
            "ğ": "Ğ",
            "ü": "Ü",
            "ş": "Ş",
            "ö": "Ö",
            "ç": "Ç",
        }
    )
    compact = re.sub(r"[\s\xa0]+", " ", value).strip()
    return compact.translate(table).upper()


def compact_ws(value: str) -> str:
    value = unescape(value.replace("\xa0", " ").replace("\u2009", " "))
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_DROP_TAGS):
        tag.decompose()
    chunks: list[str] = []

    def walk(node: Tag | NavigableString) -> None:
        if isinstance(node, NavigableString):
            text = str(node)
            if text.strip():
                chunks.append(text)
            return
        if not isinstance(node, Tag):
            return
        if node.name in _DROP_TAGS:
            return
        if node.name in _BLOCK_TAGS:
            chunks.append("\n")
        for child in node.children:
            walk(child)
        if node.name in _BLOCK_TAGS:
            chunks.append("\n")

    root = soup.body or soup
    walk(root)
    return compact_ws("".join(chunks))


def soup_from_html(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def pdf_bytes_to_text(data: bytes, *, max_pages: int | None = DEFAULT_MAX_PDF_PAGES) -> str:
    """Extract text from PDF bytes. Prefers pypdf; pdfplumber is the fallback."""
    if not data:
        return ""
    text = _pypdf_text(data, max_pages=max_pages)
    if text.strip():
        return compact_ws(text)
    # Image-only gazete PDFs often have no text layer; skip the slow plumber pass
    # unless the file is small enough that a second parse is cheap.
    if len(data) > 400_000:
        LOGGER.info("PDF has no text layer (%s bytes); skipping pdfplumber", len(data))
        return ""
    text = _pdfplumber_text(data, max_pages=min(max_pages or 4, 4))
    return compact_ws(text)


async def pdf_bytes_to_text_async(
    data: bytes, *, timeout_s: float = 20.0, max_pages: int | None = DEFAULT_MAX_PDF_PAGES
) -> str:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(pdf_bytes_to_text, data, max_pages=max_pages),
            timeout=timeout_s,
        )
    except asyncio.TimeoutError:
        LOGGER.warning("PDF text extraction timed out after %ss", timeout_s)
        return ""


def _pdfplumber_text(data: bytes, *, max_pages: int | None) -> str:
    try:
        import pdfplumber
    except ImportError:
        LOGGER.debug("pdfplumber not installed")
        return ""
    try:
        pages: list[str] = []
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for index, page in enumerate(pdf.pages):
                if max_pages is not None and index >= max_pages:
                    break
                pages.append(page.extract_text() or "")
        return "\n".join(pages)
    except Exception as exc:  # noqa: BLE001 — PDF parsers fail on many files
        LOGGER.warning("pdfplumber failed: %s", exc)
        return ""


def _pypdf_text(data: bytes, *, max_pages: int | None) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        LOGGER.debug("pypdf not installed")
        return ""
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = reader.pages[:max_pages] if max_pages is not None else reader.pages
        return "\n".join(page.extract_text() or "" for page in pages)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("pypdf failed: %s", exc)
        return ""


def looks_like_pdf(content_type: str | None, url: str, body: bytes) -> bool:
    if body[:5] == b"%PDF-":
        return True
    if content_type and "pdf" in content_type.lower():
        return True
    return url.lower().split("?", 1)[0].endswith(".pdf")
