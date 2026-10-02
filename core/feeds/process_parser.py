"""Out-of-process FEEDS document parsing and discovery examination.

Large RSS/Atom/JSON documents and HTML feed-discovery pages are Python-heavy.
Running that work in an ordinary IO thread still shares the main interpreter's
GIL with Qt and can stall presentation even when source refreshes are perfectly
serialized.

One active FEEDS family owns one lazy parser process.  It owns no network,
scheduler, cache, artwork or presentation authority.  The existing family IO
worker waits for the child result; Qt does not.  When FEEDS becomes dormant the
executor is shut down and is recreated lazily on the next remote document.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
from threading import Lock
from typing import Final

from .models import FeedDocument
from .parser import FeedParseError, parse_feed_bytes
from .transport import FeedHttpResponse


_MAX_WORKERS: Final[int] = 1


class FeedParseProcessError(FeedParseError):
    """The isolated parser process could not accept/complete a parse job."""


def _parse_job(payload: bytes, source_url: str, max_items: int) -> FeedDocument:
    """Picklable child-process entry point. Contains no Qt/runtime ownership."""
    return parse_feed_bytes(payload, source_url=source_url, max_items=max_items)


def _examine_job(
    response: FeedHttpResponse,
    request_url: str,
    max_items: int,
):
    """Picklable child entry for all pure document examination/discovery work."""
    # Imported in the child so the parent's runtime lane owns no additional
    # discovery parser state. _examine performs no network or scheduling.
    from .discovery import _examine
    document, candidates = _examine(response, url=request_url, max_items=max_items)
    return document, tuple(candidates)


class FeedParseProcess:
    """Lazy single-process parser lane for one active FEEDS family."""

    def __init__(self) -> None:
        self._executor: ProcessPoolExecutor | None = None
        self._lock = Lock()

    def _ensure_executor(self) -> ProcessPoolExecutor:
        with self._lock:
            executor = self._executor
            if executor is None:
                # Spawn on every platform so tests and production exercise the
                # same isolation contract and never inherit the Qt interpreter.
                executor = ProcessPoolExecutor(
                    max_workers=_MAX_WORKERS,
                    mp_context=mp.get_context("spawn"),
                )
                self._executor = executor
            return executor

    def _result(self, function, *args):
        executor = self._ensure_executor()
        try:
            return executor.submit(function, *args).result()
        except FeedParseError:
            raise
        except Exception as exc:
            # A child/infrastructure failure is one source refresh failure,
            # never permission to fall back to main-process parsing and
            # reintroduce a presentation hitch.  The next legitimate demand
            # gets a fresh child.
            self.close()
            raise FeedParseProcessError(type(exc).__name__) from exc

    def parse(self, payload: bytes, *, source_url: str, max_items: int) -> FeedDocument:
        return self._result(_parse_job, bytes(payload), str(source_url), int(max_items))

    def examine(
        self,
        response: FeedHttpResponse,
        *,
        request_url: str,
        max_items: int,
    ):
        return self._result(_examine_job, response, str(request_url), int(max_items))

    def close(self) -> None:
        with self._lock:
            executor, self._executor = self._executor, None
        if executor is not None:
            # No recurring work survives dormancy.  A currently executing parse
            # may finish in the child, but no new job can be admitted and the
            # executor/process retires immediately afterward.
            executor.shutdown(wait=False, cancel_futures=True)

    @property
    def active(self) -> bool:
        return self._executor is not None
