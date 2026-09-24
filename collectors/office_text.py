"""Conservative text extraction from SGK OOXML attachments."""

from __future__ import annotations

from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import BadZipFile, ZipFile

from collectors.common import CollectionError

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
S = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
MAX_XML_BYTES = 20_000_000
MAX_TEXT_CHARS = 2_000_000


def _xml(archive: ZipFile, name: str) -> ET.Element:
    entry = archive.getinfo(name)
    if entry.file_size > MAX_XML_BYTES:
        raise CollectionError(f"Office XML part exceeds extraction limit: {name}")
    return ET.fromstring(archive.read(name))


def extract_office_text(raw: bytes, extension: str) -> tuple[str, str]:
    """Return (text, status); never claim embedded images or formulas were read."""
    if extension not in {"docx", "xlsx"}:
        raise ValueError(f"unsupported Office extension: {extension}")
    try:
        with ZipFile(BytesIO(raw)) as archive:
            names = set(archive.namelist())
            if extension == "docx":
                if "word/document.xml" not in names:
                    raise CollectionError("DOCX has no word/document.xml")
                root = _xml(archive, "word/document.xml")
                paragraphs = []
                for paragraph in root.iter(W + "p"):
                    value = "".join(node.text or "" for node in paragraph.iter(W + "t"))
                    if value.strip():
                        paragraphs.append(value.strip())
                text = "\n".join(paragraphs)
                partial = any(name.startswith(("word/media/", "word/header", "word/footer",
                                               "word/footnotes", "word/endnotes", "word/comments"))
                              for name in names)
            else:
                sheets = sorted(name for name in names if name.startswith("xl/worksheets/sheet")
                                and name.endswith(".xml") and "/_rels/" not in name)
                if not sheets:
                    raise CollectionError("XLSX has no worksheets")
                shared = []
                if "xl/sharedStrings.xml" in names:
                    shared_root = _xml(archive, "xl/sharedStrings.xml")
                    shared = ["".join(node.text or "" for node in item.iter(S + "t"))
                              for item in shared_root.iter(S + "si")]
                lines = []
                partial = any(name.startswith("xl/media/") or name.startswith("xl/drawings/") for name in names)
                for sheet in sheets:
                    root = _xml(archive, sheet)
                    lines.append(f"[{sheet}]")
                    for row in root.iter(S + "row"):
                        values = []
                        for cell in row.iter(S + "c"):
                            kind = cell.get("t")
                            value = cell.find(S + "v")
                            if kind == "inlineStr":
                                inline = cell.find(S + "is")
                                cell_text = "".join(n.text or "" for n in inline.iter(S + "t")) if inline is not None else ""
                            elif value is not None and value.text is not None:
                                if kind == "s":
                                    index = int(value.text)
                                    if index < 0 or index >= len(shared):
                                        raise CollectionError("XLSX shared-string index is invalid")
                                    cell_text = shared[index]
                                else:
                                    cell_text = value.text
                            else:
                                cell_text = ""
                                if cell.find(S + "f") is not None:
                                    partial = True  # No cached formula result.
                            if cell_text.strip():
                                values.append(f"{cell.get('r', '?')}={cell_text.strip()}")
                        if values:
                            lines.append(" | ".join(values))
                text = "\n".join(lines)
            if len(text) > MAX_TEXT_CHARS:
                raise CollectionError("Office extracted text exceeds extraction limit")
            if not text.strip():
                return "", "no_extractable_text"
            return text, "partial_text_requires_review" if partial else "text_extracted"
    except (BadZipFile, KeyError, ET.ParseError, ValueError) as exc:
        raise CollectionError(f"invalid {extension.upper()} attachment: {exc}") from exc
