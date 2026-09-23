"""Deterministic article-block extraction from consolidated Bedesten law text."""

from __future__ import annotations

import re
from typing import Any

from collectors.common import CollectionError, sha256_bytes

PARSER_VERSION = "bedesten-article-block-v6"
ARTICLE_RE = re.compile(
    r"(?m)^[ \t]*(?P<kind>MÜKERRER(?:[ \t]+|\n[ \t]*)MADDE|Mükerrer(?:[ \t]+|\n[ \t]*)Madde|"
    r"GEÇİCİ(?:[ \t]+|\n[ \t]*)MADDE|Geçici(?:[ \t]+|\n[ \t]*)Madde|"
    r"EK(?:[ \t]+|\n[ \t]*)MADDE|Ek(?:[ \t]+|\n[ \t]*)Madde|MADDE|Madde)"
    r"[ \t]*(?:\n[ \t]*)?(?P<number>\d+(?:/[A-Za-zÇĞİÖŞÜçğıöşü]+)?)[ \t]*[-–—(]"
)
APPENDIX_RE = re.compile(
    r"(?im)^[ \t]*\d+[ \t]*(?:\n[ \t]*)?SAYILI[ \t]+KANUNA[ \t]+EK\s+VE\s+DEĞİŞİKLİK"
)
UNINCORPORATED_RE = re.compile(r"İŞLENEMEYEN\s+(?:GEÇİCİ\s+MADDELER|HÜKÜMLER)")


def _kind(label: str) -> str:
    # Turkish dotted İ does not casefold to plain i; match the source spellings.
    if label.startswith(("MÜKERRER", "Mükerrer")):
        return "repeated"
    if label.startswith(("GEÇİCİ", "Geçici")):
        return "temporary"
    if label.startswith(("EK", "Ek")):
        return "additional"
    return "normal"


def _hash_text(text: str) -> str:
    """Ignore layout whitespace only; preserve punctuation and wording."""
    return sha256_bytes(" ".join(text.split()).encode("utf-8"))


def extract_articles(law_number: str, text: str) -> dict[str, Any]:
    if not law_number.isdigit() or not text.strip():
        raise CollectionError("article parser needs a law number and nonempty text")
    appendix = next((m for m in APPENDIX_RE.finditer(text) if m.start() > len(text) // 2), None)
    body_end = appendix.start() if appendix else len(text)
    body = text[:body_end]
    supplemental = next((m for m in UNINCORPORATED_RE.finditer(body) if m.start() > len(body) // 2), None)
    supplemental_start = body.rfind("\n", 0, supplemental.start()) + 1 if supplemental else None
    matches = list(ARTICLE_RE.finditer(body))
    warnings: list[str] = []
    review_reasons: list[str] = []
    if not appendix:
        review_reasons.append("appendix_boundary_not_found")
    if not matches:
        review_reasons.append("no_article_markers")
    if supplemental:
        warnings.append("contains_unincorporated_supplemental_provisions")
    articles: list[dict[str, Any]] = []
    occurrences: dict[str, int] = {}
    normal_numbers: list[int] = []
    for index, match in enumerate(matches):
        kind = _kind(match.group("kind"))
        number_label = match.group("number")
        number = int(number_label.split("/", 1)[0])
        id_kind = {"normal": "article", "additional": "ek-madde", "temporary": "gecici-madde",
                   "repeated": "mukerrer-madde"}[kind]
        base_id = f"law:{law_number}:{id_kind}:{number_label}"
        occurrences[base_id] = occurrences.get(base_id, 0) + 1
        article_id = base_id if occurrences[base_id] == 1 else f"{base_id}#{occurrences[base_id]}"
        if occurrences[base_id] > 1:
            warnings.append(f"repeated_article_number:{base_id}")
            if kind == "normal":
                review_reasons.append(f"repeated_normal_article_number:{base_id}")
        if kind == "normal":
            normal_numbers.append(number)
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else body_end
        if supplemental_start is not None and start < supplemental_start < end:
            end = supplemental_start
        block = body[start:end].strip()
        scope = "supplemental_unincorporated" if supplemental_start is not None and start >= supplemental_start else "main_law"
        articles.append({"article_id": article_id, "kind": kind, "number": number,
                         "number_label": number_label, "scope": scope,
                         "text": block, "normalized_sha256": _hash_text(block),
                         "start_offset": start, "end_offset": end})
    if normal_numbers and normal_numbers[0] != 1:
        review_reasons.append("normal_articles_do_not_start_at_one")
    if any(current != previous + 1 for previous, current in zip(normal_numbers, normal_numbers[1:])):
        warnings.append("normal_article_sequence_gap_or_reorder")
    if len(articles) < 5:
        review_reasons.append("too_few_article_blocks")
    return {
        "schema_version": 1, "parser_version": PARSER_VERSION, "law_number": law_number,
        "source_text_sha256": sha256_bytes(text.encode("utf-8")),
        "status": "trusted" if not review_reasons else "review_required",
        "warnings": warnings, "review_reasons": review_reasons,
        "preamble_sha256": _hash_text(body[:matches[0].start()]) if matches else None,
        "appendix_start_offset": body_end if appendix else None,
        "supplemental_start_offset": supplemental_start,
        "appendix_sha256": _hash_text(text[body_end:]) if appendix else None,
        "article_count": len(articles), "articles": articles,
    }


def compare_articles(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    if previous and previous.get("law_number") != current.get("law_number"):
        raise CollectionError("article snapshots belong to different laws")
    result: dict[str, Any] = {
        "schema_version": 1, "law_number": current["law_number"],
        "old_source_text_sha256": previous.get("source_text_sha256") if previous else None,
        "new_source_text_sha256": current["source_text_sha256"],
        "status": "baseline_created" if previous is None else "compared",
        "counts": {"added": 0, "removed": 0, "changed": 0, "unchanged": 0},
        "changes": [], "warnings": [],
    }
    if current.get("status") != "trusted" or (previous and previous.get("status") != "trusted") or (
        previous and previous.get("parser_version") != current.get("parser_version")
    ):
        result["status"] = "review_required"
        result["warnings"] = ["article_boundary_validation_failed_or_parser_version_changed"]
        return result
    if previous is None:
        return result
    old = {article["article_id"]: article for article in previous["articles"]}
    new = {article["article_id"]: article for article in current["articles"]}
    for article_id in sorted(old.keys() | new.keys()):
        before, after = old.get(article_id), new.get(article_id)
        status = "added" if before is None else "removed" if after is None else (
            "unchanged" if before["normalized_sha256"] == after["normalized_sha256"] and before.get("scope") == after.get("scope")
            else "changed")
        result["counts"][status] += 1
        if status != "unchanged":
            result["changes"].append({
                "article_id": article_id, "change_status": status,
                "old_normalized_sha256": before["normalized_sha256"] if before else None,
                "new_normalized_sha256": after["normalized_sha256"] if after else None,
                "old_text": before["text"] if before else None,
                "new_text": after["text"] if after else None,
                "old_scope": before.get("scope") if before else None,
                "new_scope": after.get("scope") if after else None,
            })
    if previous.get("preamble_sha256") != current.get("preamble_sha256"):
        result["warnings"].append("preamble_changed_outside_article_blocks")
    if previous.get("appendix_sha256") != current.get("appendix_sha256"):
        result["warnings"].append("appendix_changed_outside_article_blocks")
    if (previous.get("source_text_sha256") != current.get("source_text_sha256")
            and not result["changes"]):
        result["status"] = "non_article_text_changed"
        result["warnings"].append("full_text_changed_without_article_hash_change")
    return result
