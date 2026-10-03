from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import httpx

LOGGER = logging.getLogger("iso_pulse.ingestion.http")

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,application/pdf;q=0.9,"
        "application/xml;q=0.8,*/*;q=0.7"
    ),
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
}

_CHARSET_RE = re.compile(br"charset\s*=\s*[\"']?([\w-]+)", re.I)
_META_CHARSET_RE = re.compile(
    br"<meta[^>]+charset\s*=\s*[\"']?([\w-]+)",
    re.I,
)


def charset_from_headers_and_body(
    content_type: str | None, body: bytes, default: str = "utf-8"
) -> str:
    if content_type:
        match = re.search(r"charset\s*=\s*['\"]?([\w-]+)", content_type, re.I)
        if match:
            return match.group(1)
    for pattern in (_CHARSET_RE, _META_CHARSET_RE):
        match = pattern.search(body[:4096])
        if match:
            return match.group(1).decode("ascii", "ignore")
    return default


def decode_html_bytes(
    body: bytes, content_type: str | None, default: str = "utf-8"
) -> str:
    charset = charset_from_headers_and_body(content_type, body, default)
    aliases = {
        "windows-1254": "cp1254",
        "iso-8859-9": "iso8859_9",
        "utf8": "utf-8",
    }
    encoding = aliases.get(charset.lower(), charset)
    try:
        return body.decode(encoding)
    except (LookupError, UnicodeDecodeError):
        return body.decode(default, errors="replace")


class FetchClient:
    """Async HTTP helper with retries, concurrency cap, and polite pauses."""

    def __init__(
        self,
        *,
        timeout: float = 45.0,
        max_concurrency: int = 4,
        pause_s: float = 0.3,
        retries: int = 3,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._timeout = timeout
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._pause_s = pause_s
        self._retries = retries
        self._headers = {**DEFAULT_HEADERS, **(headers or {})}
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> FetchClient:
        self._client = httpx.AsyncClient(
            headers=self._headers,
            timeout=httpx.Timeout(self._timeout),
            follow_redirects=True,
            http2=False,
        )
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("FetchClient must be used as an async context manager")
        return self._client

    async def get(
        self, url: str, *, extra_headers: dict[str, str] | None = None
    ) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(1, self._retries + 1):
            async with self._semaphore:
                try:
                    response = await self.client.get(url, headers=extra_headers)
                    if response.status_code in {429, 500, 502, 503, 504}:
                        raise httpx.HTTPStatusError(
                            f"{response.status_code} for {url}",
                            request=response.request,
                            response=response,
                        )
                    if self._pause_s:
                        await asyncio.sleep(self._pause_s)
                    return response
                except (httpx.HTTPError, httpx.TimeoutException) as exc:
                    last_error = exc
                    wait = min(2**attempt, 8)
                    LOGGER.warning(
                        "GET %s failed (attempt %s/%s): %s — retry in %ss",
                        url,
                        attempt,
                        self._retries,
                        exc,
                        wait,
                    )
                    await asyncio.sleep(wait)
        assert last_error is not None
        raise last_error

    async def get_bytes(self, url: str) -> tuple[bytes, str | None, int]:
        response = await self.get(url)
        return response.content, response.headers.get("content-type"), response.status_code

    async def get_html(self, url: str, *, default_encoding: str = "utf-8") -> str:
        body, content_type, status = await self.get_bytes(url)
        if status >= 400:
            raise httpx.HTTPStatusError(
                f"{status} for {url}",
                request=httpx.Request("GET", url),
                response=httpx.Response(status),
            )
        return decode_html_bytes(body, content_type, default=default_encoding)
