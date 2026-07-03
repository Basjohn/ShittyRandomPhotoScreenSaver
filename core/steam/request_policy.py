"""Request coalescing, generation drops, and backoff policy for Steam work."""
from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from core.logging.logger import get_logger
from core.steam.models import SteamResult, SteamResultStatus, SteamSourceId

logger = get_logger(__name__)


@dataclass(frozen=True)
class SteamRequestKey:
    """Stable request identity used for coalescing and backoff."""

    profile_key: str
    source_id: SteamSourceId
    category: str
    appid: int | None = None
    params_fingerprint: str = ""

    @classmethod
    def from_params(
        cls,
        *,
        profile_key: str,
        source_id: SteamSourceId,
        category: str,
        appid: int | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> "SteamRequestKey":
        return cls(
            profile_key=profile_key,
            source_id=source_id,
            category=category,
            appid=appid,
            params_fingerprint=_fingerprint_params(params or {}),
        )


@dataclass(frozen=True)
class SteamRequestHandle:
    """Opaque request owner token returned by the coordinator."""

    key: SteamRequestKey
    generation: int
    token: int
    owner: bool


@dataclass(frozen=True)
class SteamBackoffDecision:
    """Decision returned before provider/cache work is attempted."""

    allowed: bool
    retry_after_seconds: float = 0.0
    reason: str = ""


class SteamRequestCoordinator:
    """Small synchronous coordinator for in-flight identity and generations.

    It does not own threads or timers. Runtime code remains responsible for
    scheduling through SRPSS ThreadManager; this helper only decides whether a
    request should start, join/drop, or be rejected as stale on completion.
    """

    def __init__(self, *, generation: int = 0) -> None:
        self._generation = int(generation)
        self._next_token = 1
        self._in_flight: dict[SteamRequestKey, SteamRequestHandle] = {}
        self._lock = threading.RLock()

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    def advance_generation(self) -> int:
        """Advance generation and clear stale in-flight ownership."""
        with self._lock:
            self._generation += 1
            self._in_flight.clear()
            logger.info("[STEAM] Request generation advanced generation=%d", self._generation)
            return self._generation

    def begin(self, key: SteamRequestKey) -> SteamRequestHandle:
        """Start or join an in-flight request for *key*."""
        with self._lock:
            existing = self._in_flight.get(key)
            if existing is not None:
                return SteamRequestHandle(
                    key=key,
                    generation=existing.generation,
                    token=existing.token,
                    owner=False,
                )
            handle = SteamRequestHandle(
                key=key,
                generation=self._generation,
                token=self._next_token,
                owner=True,
            )
            self._next_token += 1
            self._in_flight[key] = handle
            return handle

    def complete(self, handle: SteamRequestHandle, result: SteamResult) -> SteamResult:
        """Complete a request only if the handle still owns the current generation."""
        with self._lock:
            current = self._in_flight.get(handle.key)
            if not handle.owner:
                return SteamResult(
                    status=SteamResultStatus.STALE_GENERATION,
                    source_id=result.source_id,
                    message="Joined Steam request handle cannot complete provider work.",
                    attempted_sources=result.attempted_sources,
                )
            if current is None or current.token != handle.token or current.generation != handle.generation:
                logger.warning(
                    "[STEAM] Dropped stale request result source=%s category=%s generation=%s current=%s",
                    handle.key.source_id.value,
                    handle.key.category,
                    handle.generation,
                    self._generation,
                )
                return SteamResult(
                    status=SteamResultStatus.STALE_GENERATION,
                    source_id=result.source_id,
                    message="Steam request result belongs to a stale generation.",
                    attempted_sources=result.attempted_sources,
                )
            self._in_flight.pop(handle.key, None)
            return result

    def active_count(self) -> int:
        with self._lock:
            return len(self._in_flight)


class SteamBackoffPolicy:
    """Bounded per-request backoff without timers or background work."""

    def __init__(self, *, base_seconds: float = 60.0, max_seconds: float = 900.0) -> None:
        self.base_seconds = max(1.0, float(base_seconds))
        self.max_seconds = max(self.base_seconds, float(max_seconds))
        self._failures: dict[SteamRequestKey, int] = {}
        self._next_allowed_at: dict[SteamRequestKey, float] = {}

    def check(self, key: SteamRequestKey, *, now: float) -> SteamBackoffDecision:
        due = self._next_allowed_at.get(key, 0.0)
        if due > now:
            return SteamBackoffDecision(
                allowed=False,
                retry_after_seconds=max(0.0, due - now),
                reason="backoff_active",
            )
        return SteamBackoffDecision(allowed=True)

    def record_result(self, key: SteamRequestKey, result: SteamResult, *, now: float) -> None:
        if result.ok:
            self._failures.pop(key, None)
            self._next_allowed_at.pop(key, None)
            return
        if result.status not in {
            SteamResultStatus.NETWORK_ERROR,
            SteamResultStatus.RATE_LIMITED,
            SteamResultStatus.UNAUTHORIZED,
            SteamResultStatus.PRIVATE,
            SteamResultStatus.INVALID_RESPONSE,
        }:
            return
        failures = self._failures.get(key, 0) + 1
        self._failures[key] = failures
        delay = min(self.max_seconds, self.base_seconds * (2 ** (failures - 1)))
        self._next_allowed_at[key] = now + delay
        logger.warning(
            "[STEAM] Backoff armed source=%s category=%s failures=%d delay=%.1fs",
            key.source_id.value,
            key.category,
            failures,
            delay,
        )


def backoff_result(key: SteamRequestKey, decision: SteamBackoffDecision) -> SteamResult:
    """Return a provider-safe result for an active backoff gate."""
    return SteamResult(
        status=SteamResultStatus.BACKOFF_ACTIVE,
        source_id=key.source_id,
        message=f"Steam request backoff active for {decision.retry_after_seconds:.1f}s.",
        attempted_sources=(key.source_id,),
    )


def _fingerprint_params(params: Mapping[str, Any]) -> str:
    safe = json.dumps(params, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(safe.encode("utf-8")).hexdigest()[:16]
