"""Pinned-address, bounded public image transport (FEEDS artwork and wallpaper feeds).

No scheduling, Qt, requests.Session, background thread, or global connection pool.
Every redirect hop is resolved and vetted *before* opening a socket, and the
chosen global address is pinned to the connection (including TLS SNI/hostname
validation against the original DNS name).  Merely vetting DNS and then asking
requests to resolve the host again would leave a DNS-rebinding hole.
"""
from __future__ import annotations

import http.client
import ipaddress
import socket
import ssl
import time
from typing import Callable, Iterator
from urllib.parse import urljoin, urlsplit, urlunsplit

from .artwork import ArtworkCancelled, MAX_DOWNLOAD_BYTES, safe_artwork_url
from core.network.bounded_dns import resolve_bounded

MAX_ARTWORK_REDIRECTS = 3
CONNECT_TIMEOUT_SECONDS = 4.0
READ_TIMEOUT_SECONDS = 5.0
MAX_TOTAL_SECONDS = 18.0


class ArtworkFetchError(ValueError):
    """An optional feed image failed validation, transport or byte bounds."""


def _target(url: str) -> tuple[str, str, int, str]:
    if not safe_artwork_url(url):
        raise ArtworkFetchError("unsafe artwork URL")
    parsed = urlsplit(url)
    host = (parsed.hostname or "").rstrip(".").lower()
    scheme = parsed.scheme.lower()
    port = parsed.port or (443 if scheme == "https" else 80)
    # Default ports only: no implicit proxying or arbitrary TCP service access.
    if port != (443 if scheme == "https" else 80):
        raise ArtworkFetchError("nonstandard artwork port")
    target = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    return scheme, host, port, target


def _public_address(host: str, port: int, *, resolve: Callable[..., object]) -> str:
    try:
        answers = resolve(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ArtworkFetchError("artwork DNS lookup failed") from exc
    addresses = []
    for answer in answers:
        try:
            address = ipaddress.ip_address(answer[4][0])
        except (ValueError, IndexError, TypeError) as exc:
            raise ArtworkFetchError("invalid artwork DNS answer") from exc
        # Reject a mixed public/private DNS response rather than silently
        # allowing a future connection or redirect to use a private address.
        if not address.is_global:
            raise ArtworkFetchError("nonpublic artwork DNS address")
        addresses.append(str(address))
    if not addresses:
        raise ArtworkFetchError("artwork host has no usable addresses")
    return addresses[0]


def iter_public_image(
    url: str, *,
    still_needed: Callable[[], bool],
    max_bytes: int,
    max_seconds: float,
    resolve: Callable[..., object] | None = None,
    connect_timeout: float = CONNECT_TIMEOUT_SECONDS,
    read_timeout: float = READ_TIMEOUT_SECONDS,
    user_agent: str = "SRPSS/FeedArtwork",
    accept: str = "image/png,image/jpeg,image/webp,image/gif;q=0.8,*/*;q=0.1",
    chunk_size: int = 16 * 1024,
) -> Iterator[bytes]:
    """Stream one public image's bytes: the one vetted image path for every family.

    Each redirect hop is resolved (bounded, cancellable) and vetted before a
    socket opens, and the connection is pinned to that global address with TLS
    SNI/hostname verification against the original name. The whole stream is
    bounded by ``max_bytes`` and ``max_seconds`` and checks ``still_needed``
    between reads. Chunks are yielded as they arrive; closing the generator
    early (a caller that has seen enough) closes the connection. A declared
    length must be met exactly, so a truncated body never completes.
    """
    budget = max(1, int(max_bytes))
    deadline = time.monotonic() + max(0.1, float(max_seconds))
    current = url
    for hop in range(MAX_ARTWORK_REDIRECTS + 1):
        if not still_needed():
            raise ArtworkCancelled()
        if time.monotonic() >= deadline:
            raise ArtworkFetchError("artwork time budget exhausted")
        scheme, host, port, request_target = _target(current)
        hop_resolve = resolve
        if hop_resolve is None:
            # Bounded like the rest of the fetch: a stalled DNS server can
            # neither outlast the connect budget nor ignore retirement.
            dns_budget = min(max(0.1, connect_timeout), max(0.1, deadline - time.monotonic()))

            def hop_resolve(name, number, type=socket.SOCK_STREAM, _budget=dns_budget):
                return resolve_bounded(name, number, timeout=_budget,
                                       should_continue=still_needed, type=type)
        try:
            address = _public_address(host, port, resolve=hop_resolve)
        except ArtworkFetchError as exc:
            if not still_needed():
                raise ArtworkCancelled() from exc
            raise
        if not still_needed():
            raise ArtworkCancelled()
        remaining = max(0.1, deadline - time.monotonic())
        timeout = min(max(0.1, connect_timeout), remaining)
        if scheme == "https":
            connection = http.client.HTTPSConnection(
                host, port, timeout=timeout, context=ssl.create_default_context())
        else:
            connection = http.client.HTTPConnection(host, port, timeout=timeout)
        # http.client retains the hostname for TLS SNI/certificate verification
        # and the Host header, while the socket connects to the vetted IP only.
        connection._create_connection = (
            lambda _host_port, timeout=timeout, source_address=None:
                socket.create_connection((address, port), timeout, source_address)
        )
        try:
            connection.request("GET", request_target, headers={
                "Host": host,
                "User-Agent": user_agent,
                "Accept": accept,
                "Accept-Encoding": "identity",
                "Connection": "close",
            })
            response = connection.getresponse()
            if response.status in {301, 302, 303, 307, 308}:
                location = response.getheader("Location", "")
                if not location or hop >= MAX_ARTWORK_REDIRECTS:
                    raise ArtworkFetchError("artwork redirect rejected")
                current = urljoin(current, location)
                # Target validation and DNS resolution happen before opening
                # the next connection. Never hand an unvetted redirect to HTTP.
                _target(current)
                continue
            if response.status != 200:
                raise ArtworkFetchError("artwork HTTP status is not successful")
            if response.getheader("Content-Encoding", "identity").lower() != "identity":
                raise ArtworkFetchError("compressed artwork response rejected")
            declared = response.getheader("Content-Length")
            declared_bytes: int | None = None
            if declared is not None:
                try:
                    declared_bytes = int(declared)
                except (TypeError, ValueError) as exc:
                    raise ArtworkFetchError("invalid artwork content length") from exc
                if declared_bytes < 0:
                    raise ArtworkFetchError("invalid artwork content length")
                if declared_bytes > budget:
                    raise ArtworkFetchError("artwork content length exceeds bound")
            received = 0
            while True:
                if not still_needed():
                    raise ArtworkCancelled()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ArtworkFetchError("artwork time budget exhausted")
                if connection.sock is not None:
                    connection.sock.settimeout(min(max(0.1, read_timeout), remaining))
                chunk = response.read(min(max(1, int(chunk_size)), budget + 1 - received))
                if not chunk:
                    break
                received += len(chunk)
                if received > budget:
                    raise ArtworkFetchError("artwork payload exceeds bound")
                yield chunk
            if declared_bytes is not None and received != declared_bytes:
                raise ArtworkFetchError("truncated artwork response")
            if not received:
                raise ArtworkFetchError("empty artwork response")
            if not still_needed():
                raise ArtworkCancelled()
            return
        except (OSError, http.client.HTTPException, ssl.SSLError) as exc:
            if not still_needed():
                raise ArtworkCancelled() from exc
            raise ArtworkFetchError("artwork connection failed") from exc
        finally:
            connection.close()
    raise ArtworkFetchError("artwork redirect limit")


def fetch_artwork_bytes(
    url: str, *,
    still_needed: Callable[[], bool],
    resolve: Callable[..., object] | None = None,
    max_bytes: int = MAX_DOWNLOAD_BYTES,
    connect_timeout: float = CONNECT_TIMEOUT_SECONDS,
    read_timeout: float = READ_TIMEOUT_SECONDS,
    max_seconds: float = MAX_TOTAL_SECONDS,
) -> bytes:
    """Fetch one optional feed image in the caller's existing bounded worker job.

    Explicit address pinning prevents a second DNS resolution after vetting.
    HTTP connections are short-lived and not shared across source generations.
    Both redirect count and wall-clock budget cover the *entire* image fetch.
    The caller owns retirement; it supplies its per-source cancellation fence.
    """
    return b"".join(iter_public_image(
        url,
        still_needed=still_needed,
        max_bytes=max(1, min(MAX_DOWNLOAD_BYTES, int(max_bytes))),
        max_seconds=min(MAX_TOTAL_SECONDS, max(0.1, float(max_seconds))),
        resolve=resolve,
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
    ))
