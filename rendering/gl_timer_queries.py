"""Passive, owner-local OpenGL timer-query sampling.

The helper never waits for a result and never schedules work.  Callers poll it
only while their existing owner context is current, wrap an already-occurring
render span, and delete the handles on that same context during strict teardown.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
from typing import Any, Iterable

from PySide6.QtCore import QByteArray

from core.logging.logger import get_logger


logger = get_logger(__name__)


@dataclass
class _QuerySlot:
    handle: int
    resource_id: str | None = None
    label: str = ""
    pending: bool = False


def _scalar_int(value: Any) -> int:
    """Normalize PyOpenGL/list/numpy scalar return shapes."""

    if isinstance(value, (list, tuple)):
        if not value:
            return 0
        value = value[0]
    item = getattr(value, "item", None)
    if callable(item):
        value = item()
    return int(value)


def _query_ids(value: Any) -> list[int]:
    if isinstance(value, (list, tuple)):
        return [int(item) for item in value]
    try:
        if not isinstance(value, (str, bytes, bytearray)):
            return [int(item) for item in value]
    except TypeError:
        pass
    return [int(value)]


def _percentile(values: Iterable[float], quantile: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    index = int(math.ceil(max(0.0, min(1.0, quantile)) * len(ordered))) - 1
    return ordered[max(0, min(len(ordered) - 1, index))]


class GLTimerQueryRing:
    """A fixed-size, non-blocking ``GL_TIME_ELAPSED`` query ring."""

    def __init__(
        self,
        *,
        owner: str,
        generation: object,
        ring_size: int = 4,
        resource_group: str = "gl_timer_queries",
        resource_manager: Any | None = None,
    ) -> None:
        self._owner = str(owner)
        self._generation = generation
        self._ring_size = max(2, int(ring_size))
        self._resource_group = str(resource_group)
        self._resource_manager = resource_manager

        self._probed = False
        self._supported = False
        self._support_reason = "not_probed"
        self._slots: list[_QuerySlot] = []
        self._active_slot: _QuerySlot | None = None

        self._window_submitted: Counter[str] = Counter()
        self._window_collected: Counter[str] = Counter()
        self._window_dropped_pending: Counter[str] = Counter()
        self._window_discarded: Counter[str] = Counter()
        self._window_samples_ms: dict[str, list[float]] = defaultdict(list)
        self._window_errors = 0

    @property
    def supported(self) -> bool:
        return bool(self._supported)

    @property
    def support_reason(self) -> str:
        return self._support_reason

    def has_live_queries(self) -> bool:
        return bool(self._slots)

    @staticmethod
    def _context_supports_timer_queries(context: Any) -> bool:
        if context is None:
            return False
        try:
            surface_format = context.format()
            major = int(surface_format.majorVersion())
            minor = int(surface_format.minorVersion())
            if (major, minor) >= (3, 3):
                return True
        except Exception:
            pass
        try:
            return bool(
                context.hasExtension(QByteArray(b"GL_ARB_timer_query"))
            )
        except Exception:
            return False

    def initialize(self, gl_api: Any, *, context: Any) -> bool:
        """Probe and allocate the fixed ring while the owner context is current."""

        if self._probed:
            return self._supported
        self._probed = True

        required = (
            "glGenQueries",
            "glBeginQuery",
            "glEndQuery",
            "glGetQueryObjectiv",
            "glGetQueryObjectui64v",
            "glDeleteQueries",
            "GL_TIME_ELAPSED",
            "GL_QUERY_RESULT_AVAILABLE",
            "GL_QUERY_RESULT",
        )
        missing = [name for name in required if not hasattr(gl_api, name)]
        if missing:
            self._support_reason = "missing_api:" + "+".join(missing)
            return False
        if not self._context_supports_timer_queries(context):
            self._support_reason = "context_unsupported"
            return False

        try:
            handles = [
                handle
                for handle in _query_ids(gl_api.glGenQueries(self._ring_size))
                if int(handle) > 0
            ]
        except Exception as exc:
            self._support_reason = f"allocation_error:{type(exc).__name__}"
            return False

        for handle in handles:
            self._slots.append(
                _QuerySlot(
                    handle=int(handle),
                    resource_id=self._register_tracking(int(handle)),
                )
            )
        if len(self._slots) != self._ring_size:
            self._support_reason = "allocation_incomplete"
            return False

        self._supported = True
        self._support_reason = "supported"
        return True

    def _resolve_resource_manager(self) -> Any | None:
        if self._resource_manager is not None:
            return self._resource_manager
        try:
            from core.resources.manager import ResourceManager

            self._resource_manager = ResourceManager.get_or_create_app_shared()
        except Exception:
            logger.debug("[PERF][GPU_QUERY] ResourceManager unavailable", exc_info=True)
            self._resource_manager = None
        return self._resource_manager

    def _register_tracking(self, handle: int) -> str | None:
        manager = self._resolve_resource_manager()
        if manager is None:
            return None
        try:
            return manager.register_gl_handle(
                handle,
                "query",
                description=f"GL timer query {handle}",
                group=self._resource_group,
                owner=self._owner,
                generation=self._generation,
                dimensions=None,
                format="GL_TIME_ELAPSED",
                tracked_bytes=None,
            )
        except Exception:
            logger.debug("[PERF][GPU_QUERY] Query tracking failed", exc_info=True)
            return None

    def _release_tracking(self, resource_id: str | None) -> None:
        if not resource_id:
            return
        manager = self._resolve_resource_manager()
        if manager is None:
            return
        try:
            manager.release_tracking(resource_id)
        except Exception:
            logger.debug("[PERF][GPU_QUERY] Tracking release failed", exc_info=True)

    def _discard_in_flight(self) -> None:
        if self._active_slot is not None:
            label = self._active_slot.label or "<unknown>"
            self._window_discarded[label] += 1
            self._active_slot = None
        for slot in self._slots:
            if slot.pending:
                self._window_discarded[slot.label or "<unknown>"] += 1
            slot.pending = False
            slot.label = ""

    def _disable_runtime(self, reason: str) -> None:
        self._window_errors += 1
        self._discard_in_flight()
        self._supported = False
        self._support_reason = str(reason)

    def poll(self, gl_api: Any) -> None:
        """Collect only results the driver already reports as available."""

        if not self._supported:
            return
        for slot in self._slots:
            if not slot.pending:
                continue
            try:
                available = _scalar_int(
                    gl_api.glGetQueryObjectiv(
                        slot.handle,
                        gl_api.GL_QUERY_RESULT_AVAILABLE,
                    )
                )
            except Exception as exc:
                self._disable_runtime(
                    f"availability_error:{type(exc).__name__}"
                )
                return
            if not available:
                continue
            try:
                elapsed_ns = _scalar_int(
                    gl_api.glGetQueryObjectui64v(
                        slot.handle,
                        gl_api.GL_QUERY_RESULT,
                    )
                )
            except Exception as exc:
                self._disable_runtime(f"result_error:{type(exc).__name__}")
                return
            label = slot.label or "<unknown>"
            self._window_collected[label] += 1
            self._window_samples_ms[label].append(max(0.0, elapsed_ns / 1_000_000.0))
            slot.pending = False
            slot.label = ""

    def begin(self, gl_api: Any, *, label: str) -> bool:
        """Begin one query if a slot is free; otherwise drop the sample."""

        normalized_label = str(label or "<unknown>")
        if not self._supported:
            return False
        if self._active_slot is not None:
            self._window_dropped_pending[normalized_label] += 1
            return False
        slot = next((candidate for candidate in self._slots if not candidate.pending), None)
        if slot is None:
            self._window_dropped_pending[normalized_label] += 1
            return False
        try:
            gl_api.glBeginQuery(gl_api.GL_TIME_ELAPSED, slot.handle)
        except Exception as exc:
            self._disable_runtime(f"begin_error:{type(exc).__name__}")
            return False
        slot.label = normalized_label
        self._active_slot = slot
        return True

    def end(self, gl_api: Any) -> None:
        slot = self._active_slot
        if slot is None:
            return
        try:
            gl_api.glEndQuery(gl_api.GL_TIME_ELAPSED)
        except Exception as exc:
            self._disable_runtime(f"end_error:{type(exc).__name__}")
            return
        self._active_slot = None
        slot.pending = True
        self._window_submitted[slot.label or "<unknown>"] += 1

    def consume_window(self, *, include_labels: Iterable[str] = ()) -> dict[str, Any]:
        """Return and reset window counters without touching pending queries."""

        pending = Counter(
            slot.label or "<unknown>"
            for slot in self._slots
            if slot.pending
        )
        labels = {
            str(label or "<unknown>") for label in include_labels
        }
        labels.update(self._window_submitted)
        labels.update(self._window_collected)
        labels.update(self._window_dropped_pending)
        labels.update(self._window_discarded)
        labels.update(self._window_samples_ms)
        labels.update(pending)

        by_label: dict[str, dict[str, Any]] = {}
        for label in sorted(labels):
            samples = tuple(self._window_samples_ms.get(label, ()))
            by_label[label] = {
                "submitted": int(self._window_submitted.get(label, 0)),
                "collected": int(self._window_collected.get(label, 0)),
                "pending": int(pending.get(label, 0)),
                "dropped_pending": int(
                    self._window_dropped_pending.get(label, 0)
                ),
                "discarded": int(self._window_discarded.get(label, 0)),
                "samples": len(samples),
                "p50_ms": _percentile(samples, 0.50),
                "p95_ms": _percentile(samples, 0.95),
                "max_ms": max(samples) if samples else None,
            }

        result = {
            "supported": bool(self._supported),
            "reason": self._support_reason,
            "pending": sum(pending.values()),
            "errors": int(self._window_errors),
            "by_label": by_label,
        }
        self._window_submitted.clear()
        self._window_collected.clear()
        self._window_dropped_pending.clear()
        self._window_discarded.clear()
        self._window_samples_ms.clear()
        self._window_errors = 0
        return result

    def cleanup(self, gl_api: Any) -> None:
        """Strictly delete every query while the exact owner context is current."""

        if not self._slots:
            return
        self._discard_in_flight()
        errors: list[str] = []
        retained: list[_QuerySlot] = []
        for slot in self._slots:
            try:
                gl_api.glDeleteQueries(1, [int(slot.handle)])
            except Exception as exc:
                retained.append(slot)
                errors.append(f"query:{slot.handle}:{type(exc).__name__}:{exc}")
                continue
            self._release_tracking(slot.resource_id)
        self._slots = retained
        if errors:
            raise RuntimeError(
                "GL timer-query deletion incomplete: " + " | ".join(errors)
            )

