"""Small, source-neutral helpers for collection and local evidence storage."""

from __future__ import annotations

import hashlib
import json
import os
import ssl
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class CollectionError(RuntimeError):
    """A source failed or returned data that cannot safely be accepted."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write(path: Path, content: bytes) -> None:
    """Do not leave a successful-looking, half-written collector artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as file:
            temporary = file.name
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


class HttpClient:
    """Verified HTTPS only; an extra CA bundle can repair incomplete server chains."""

    def __init__(self, *, ca_bundle: str | None = None, extra_ca_pem: str | None = None, timeout: float = 30.0):
        self.timeout = timeout
        self.context = ssl.create_default_context()
        if ca_bundle:
            self.context.load_verify_locations(cafile=ca_bundle)
        if extra_ca_pem:
            self.context.load_verify_locations(cadata=extra_ca_pem)

    def _read(self, request: Request) -> tuple[bytes, str, str | None]:
        url = request.full_url
        for attempt in range(3):
            try:
                with urlopen(request, timeout=self.timeout, context=self.context) as response:
                    return response.read(), response.headers.get_content_type(), response.headers.get_content_charset()
            except HTTPError as exc:
                if exc.code != 429 and exc.code < 500:
                    raise CollectionError(f"{url}: HTTP {exc.code}") from exc
                error: Exception = exc
            except (URLError, TimeoutError) as exc:
                error = exc
            if attempt < 2:
                time.sleep(attempt + 1)
        reason = getattr(error, "reason", str(error))
        raise CollectionError(f"{url}: failed after 3 attempts: {reason}") from error

    def post_json(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> bytes:
        request = Request(url, data=canonical_json(payload), headers=headers, method="POST")
        raw, media_type, _ = self._read(request)
        if media_type != "application/json":
            raise CollectionError(f"{url}: expected JSON, received {media_type}")
        return raw

    def get(self, url: str, headers: dict[str, str] | None = None) -> tuple[bytes, str, str | None]:
        request = Request(url, headers=headers or {}, method="GET")
        return self._read(request)


def parse_json_object(raw: bytes, source: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CollectionError(f"{source}: invalid JSON response") from exc
    if not isinstance(value, dict):
        raise CollectionError(f"{source}: expected a JSON object")
    return value


def fetch_pinned_intermediate(url: str, expected_der_sha256: str) -> str:
    """Load a missing intermediate without trusting a replacement certificate."""
    request = Request(url, headers={"User-Agent": "ISO-Pulse/0.1 (certificate chain repair)"})
    try:
        with urlopen(request, timeout=20, context=ssl.create_default_context()) as response:
            pem = response.read().decode("ascii")
        der = ssl.PEM_cert_to_DER_cert(pem)
    except (HTTPError, URLError, TimeoutError, UnicodeDecodeError, ValueError) as exc:
        raise CollectionError(f"cannot load verified intermediate from {url}: {exc}") from exc
    if sha256_bytes(der) != expected_der_sha256:
        raise CollectionError(f"intermediate certificate fingerprint mismatch: {url}")
    return pem
