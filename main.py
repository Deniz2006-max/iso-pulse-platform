from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import sys

from graph import graph
from mocks.documents import (
    DEFAULT_DOCUMENT_ID,
    MockDocument,
    get_document,
    list_documents,
)
from schemas.state import PulseState


def prepare_state(document: MockDocument) -> PulseState:
    new_text = document["new_text"]
    old_text = document.get("old_text") or ""
    diff = "\n".join(
        difflib.unified_diff(
            old_text.splitlines(),
            new_text.splitlines(),
            fromfile="old",
            tofile="new",
            lineterm="",
        )
    )
    return {
        "source": document["source"],
        "document_id": document["document_id"],
        "title": document["title"],
        "old_text": document["old_text"],
        "new_text": new_text,
        "diff": diff,
        "sha256": hashlib.sha256(new_text.encode("utf-8")).hexdigest(),
        "analyses": {},
        "audit_log": [],
    }


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def run(document_id: str) -> int:
    state = prepare_state(get_document(document_id))
    result = graph.invoke(state)

    print("=== Delivery JSON ===")
    delivery = result.get("delivery")
    if delivery is not None:
        _print_json(delivery.model_dump(mode="json"))
    else:
        _print_json(
            {
                "skipped": True,
                "document_id": result["document_id"],
                "is_relevant": result.get("is_relevant", False),
                "relevance_reason": result.get("relevance_reason", ""),
            }
        )

    print("\n=== Audit trail ===")
    audit = []
    for event in result.get("audit_log") or []:
        audit.append(event.model_dump(mode="json"))
    _print_json(audit)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the ISO-PULSE LangGraph pipeline on a mock document.",
    )
    parser.add_argument(
        "--doc",
        default=DEFAULT_DOCUMENT_ID,
        help=f"Mock document id (default: {DEFAULT_DOCUMENT_ID})",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List mock document ids and exit.",
    )
    args = parser.parse_args(argv)

    if args.list:
        for doc_id in list_documents():
            document = get_document(doc_id)
            print(f"{doc_id}\t{document['source']}\t{document['title']}")
        return 0

    try:
        return run(args.doc)
    except KeyError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
