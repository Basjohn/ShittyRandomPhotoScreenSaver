"""Bounded conditional HTTP transport shared by feed consumers.

No parser, cache, schedule or Qt ownership lives here.  The response body is
bounded *after* requests decompression, preventing compressed payloads from
expanding without limit.  Feed URLs may contain private query tokens; logs must
use ``redacted_url_for_log`` rather than raw URLs.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import TYPE_CHECKING, Callable, Mapping
from urllib.parse import urlparse

if TYPE_CHECKING:
    import requests


DEFAULT_MAX_FEED_BYTES = 4 * 1024 * 1024
DEFAULT_CONNECT_TIMEOUT = 4.0
DEFAULT_READ_TIMEOUT = 8.0
MAX_REDIRECTS = 5


class FeedTransportError(RuntimeError):
    """A failed bounded fetch.

    ``status_code`` is the HTTP status when the server answered with an error,
    and ``None`` for network-level failure, cancellation or a byte-limit breach.
    Feed discovery uses it to tell a missing/blocked page from being offline.
    """

    def __init__(self, message: str = "", *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class FeedHttpResponse:
    status: str  # "ok" | "not_modified"
    payload: bytes
    final_url: str
    etag: str = ""
    last_modified: str = ""
    content_type: str = ""
    # RFC 8288 ``Link`` header (bounded); a site may advertise its feed here.
    link_header: str = ""


_BARE_HOST_RE = re.compile(r"^(localhost|[a-z0-9-]+(\.[a-z0-9-]+)+)(:\d{1,5})?([/?#]|$)", re.IGNORECASE)


def normalize_feed_address(value: object) -> str:
    """User-typed feed/site address -> URL text (not yet validated).

    Accepts a bare host such as ``arstechnica.com`` (HTTPS is assumed), a
    protocol-relative ``//host/path`` and the legacy ``feed:`` pseudo-scheme.
    Anything else is returned unchanged for ``validate_feed_url`` to judge, so
    this never widens the HTTP/S-only admission rule.
    """
    text = str(value or "").strip()
    lowered = text.casefold()
    if lowered.startswith("feed:"):
        text = text[5:]
        if text.startswith("//"):
            text = "https:" + text
        lowered = text.casefold()
    if text.startswith("//"):
        return "https:" + text
    if "://" not in lowered and _BARE_HOST_RE.match(text):
        return "https://" + text
    return text


def validate_feed_url(url: str) -> str:
    text = str(url or "").strip()
    if not text or len(text) > 8192:
        raise ValueError("feed URL is empty or too long")
    try:
        parsed = urlparse(text)
    except ValueError as exc:
        raise ValueError("feed URL is malformed") from exc
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("feed URL must use http or https")
    return text


class FeedHttpTransport:
    def __init__(
        self,
        *,
        max_bytes: int = DEFAULT_MAX_FEED_BYTES,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
        read_timeout: float = DEFAULT_READ_TIMEOUT,
        user_agent: str = "SRPSS/FeedReader",
        should_continue: Callable[[], bool] | None = None,
        session: "requests.Session | None" = None,
    ) -> None:
        self.max_bytes = max(32 * 1024, int(max_bytes))
        self.timeout = (max(0.5, float(connect_timeout)), max(0.5, float(read_timeout)))
        self.user_agent = str(user_agent or "SRPSS/FeedReader")[:240]
        self.should_continue = should_continue
        self._owns_session = session is None
        if session is None:
            # Keep the third-party HTTP stack entirely asleep until a real
            # transport is constructed for network work. Importing feed config,
            # cache or source modules must remain network-library neutral.
            import requests
            session = requests.Session()
        self.session = session
        self.session.max_redirects = MAX_REDIRECTS

    def _alive(self) -> bool:
        return True if self.should_continue is None else bool(self.should_continue())

    def close(self) -> None:
        """Release the internally-owned HTTP connection pool deterministically."""
        if not self._owns_session:
            return
        close = getattr(self.session, "close", None)
        if callable(close):
            close()

    def fetch(
        self,
        url: str,
        *,
        etag: str = "",
        last_modified: str = "",
        extra_headers: Mapping[str, str] | None = None,
    ) -> FeedHttpResponse:
        target = validate_feed_url(url)
        if not self._alive():
            raise FeedTransportError("feed fetch cancelled")
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/atom+xml, application/rss+xml, application/xml, text/xml, */*;q=0.2",
            "Accept-Encoding": "gzip, deflate",
        }
        if etag:
            headers["If-None-Match"] = str(etag)[:1024]
        if last_modified:
            headers["If-Modified-Since"] = str(last_modified)[:1024]
        if extra_headers:
            for key, value in extra_headers.items():
                if key and value:
                    headers[str(key)] = str(value)

        # ``requests`` is imported only on the actual network path.  This also
        # supplies the precise RequestException class without making module
        # discovery/configuration pay the import cost.
        import requests

        response = None
        try:
            response = self.session.get(
                target,
                headers=headers,
                timeout=self.timeout,
                stream=True,
                allow_redirects=True,
            )
            final_url = validate_feed_url(str(response.url or target))
            if response.status_code == 304:
                return FeedHttpResponse(
                    status="not_modified",
                    payload=b"",
                    final_url=final_url,
                    etag=str(response.headers.get("ETag") or etag or "")[:1024],
                    last_modified=str(response.headers.get("Last-Modified") or last_modified or "")[:1024],
                    content_type=str(response.headers.get("Content-Type") or "")[:240],
                    link_header=str(response.headers.get("Link") or "")[:4096],
                )
            status_code = int(response.status_code)
            if status_code >= 400:
                raise FeedTransportError(f"HTTP {status_code}", status_code=status_code)
            declared = response.headers.get("Content-Length")
            if declared:
                try:
                    if int(declared) > self.max_bytes:
                        raise FeedTransportError("feed response exceeds byte limit")
                except ValueError:
                    pass
            chunks: list[bytes] = []
            total = 0
            for chunk in response.iter_content(chunk_size=32 * 1024):
                if not self._alive():
                    raise FeedTransportError("feed fetch cancelled")
                if not chunk:
                    continue
                total += len(chunk)
                if total > self.max_bytes:
                    raise FeedTransportError("feed response exceeds byte limit")
                chunks.append(bytes(chunk))
            payload = b"".join(chunks)
            if not payload:
                raise FeedTransportError("feed response is empty")
            return FeedHttpResponse(
                status="ok",
                payload=payload,
                final_url=final_url,
                etag=str(response.headers.get("ETag") or "")[:1024],
                last_modified=str(response.headers.get("Last-Modified") or "")[:1024],
                content_type=str(response.headers.get("Content-Type") or "")[:240],
                link_header=str(response.headers.get("Link") or "")[:4096],
            )
        except FeedTransportError:
            raise
        except requests.RequestException as exc:
            raise FeedTransportError(type(exc).__name__) from exc
        finally:
            if response is not None:
                response.close()
