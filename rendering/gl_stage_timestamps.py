"""Compositor-owned GL_TIMESTAMP stage markers for P4 stage attribution.

Partitions the work already inside the existing outer ``GL_TIME_ELAPSED`` scope
without nesting elapsed queries. Khronos permits ``glQueryCounter`` markers
inside an active ``GL_TIME_ELAPSED`` block, so this adds markers rather than a
second measurement scope.

Strictly observational:

- no ``glFinish``, ``glFlush``, fence, wait or sleep;
- results are read only after ``GL_QUERY_RESULT_AVAILABLE`` reports them ready;
- fixed-size storage - when no packet or query capacity is free the frame's
  attribution is dropped, never waited for;
- allocated only when ``--diag-p4-stages`` is active.

Resource ownership follows the existing ``GLTimerQueryRing`` model: query
objects are compositor-context-owned, registered with ``ResourceManager`` under
an owner/generation identity, and deleted strictly on the owning context.
Failed deletion remains a hard cleanup failure and retains ownership.
"""
from __future__ import annotations

import ctypes
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from core.logging.logger import get_logger
from rendering.gl_timer_queries import _query_ids

logger = get_logger(__name__)

CLI_FLAG = "--diag-p4-stages"

# Marker order along the common compositor path.
STAGE_MARKERS = ("t0", "t1", "t2", "t3", "t4")

# Derived spans reported from those markers.
STAGE_SPANS = (
    ("prep_gpu_ms", "t0", "t1"),
    ("core_draw_gpu_ms", "t1", "t2"),
    ("dimming_gpu_ms", "t2", "t3"),
    ("overlay_gpu_ms", "t3", "t4"),
    ("marked_gpu_ms", "t0", "t4"),
)


def cli_enabled(argv) -> bool:
    """Whether the CLI diagnostic gate is present. No environment-variable path."""
    return any(str(value).strip().lower() == CLI_FLAG for value in (argv or ()))


@dataclass
class StagePacket:
    """One sampled frame's markers plus its authoritative identity."""

    scene_generation: int
    frame_index: int
    transition: str
    render_path: str
    query_ids: dict[str, int] = field(default_factory=dict)
    # Markers actually issued. A packet that falls back before later markers
    # must not wait on queries that were never submitted.
    issued: set = field(default_factory=set)
    results_ns: dict[str, int] = field(default_factory=dict)
    cpu_ms: dict[str, float] = field(default_factory=dict)
    hud: dict[str, Any] = field(default_factory=dict)
    # Set post-hoc from the matching outer GL_TIME_ELAPSED sample.
    outer_gpu_ms: float | None = None
    complete: bool = False

    def spans_ms(self) -> dict[str, float]:
        """Derived GPU spans, only where both endpoints resolved."""
        out: dict[str, float] = {}
        for name, start, end in STAGE_SPANS:
            a = self.results_ns.get(start)
            b = self.results_ns.get(end)
            if a is None or b is None:
                continue
            out[name] = max(0.0, (b - a) / 1_000_000.0)
        return out


class GLStageTimestampRing:
    """Fixed-size ring of GL_TIMESTAMP queries for stage attribution."""

    def __init__(
        self,
        *,
        owner: str,
        generation: int,
        capacity: int = 4,
        resource_group: str = "gl_compositor_stage_timestamp_queries",
    ) -> None:
        self._owner = str(owner)
        self._resource_group = str(resource_group)
        self._generation = int(generation)
        self._capacity = max(1, int(capacity))
        self._handles: list[int] = []
        self._resource_ids: list[str | None] = []
        self._free: deque[int] = deque()
        self._initialized = False
        self._supported = False
        self._support_reason = "uninitialized"
        self._active: StagePacket | None = None
        self._pending: deque[StagePacket] = deque(maxlen=self._capacity)
        self._completed: deque[StagePacket] = deque(maxlen=256)
        self._dropped_no_capacity = 0
        self._resource_manager: Any | None = None

    # ------------------------------------------------------------------ state
    @property
    def supported(self) -> bool:
        return self._supported

    @property
    def support_reason(self) -> str:
        return self._support_reason

    @property
    def dropped_no_capacity(self) -> int:
        return self._dropped_no_capacity

    def has_live_queries(self) -> bool:
        """True while any GL query object remains allocated."""
        return bool(self._handles)

    # ----------------------------------------------------------------- setup
    def initialize(self, gl_api: Any, *, context: Any, resource_manager: Any = None) -> bool:
        """Allocate the fixed query set. Only called when the CLI gate is active."""
        if self._initialized:
            return self._supported
        self._initialized = True
        self._resource_manager = resource_manager
        if gl_api is None:
            self._support_reason = "no_gl_api"
            return False
        if not hasattr(gl_api, "glQueryCounter"):
            self._support_reason = "no_query_counter"
            return False
        # One query per marker per in-flight packet, allocated in a single
        # call and normalized through the established contract - PyOpenGL may
        # return a scalar, a sequence or a numpy-like object.
        total = self._capacity * len(STAGE_MARKERS)
        try:
            handles = [h for h in _query_ids(gl_api.glGenQueries(total)) if int(h) > 0]
        except Exception as exc:
            self._support_reason = f"gen_error:{type(exc).__name__}"
            return False
        if len(handles) != total:
            self._support_reason = "allocation_incomplete"
            return False
        for handle in handles:
            self._handles.append(int(handle))
            self._resource_ids.append(self._register(int(handle)))
        for slot in range(self._capacity):
            self._free.append(slot)
        self._supported = True
        self._support_reason = "supported"
        return True

    def _resolve_resource_manager(self):
        """Same lazy app-shared resolution policy as GLTimerQueryRing."""
        if self._resource_manager is not None:
            return self._resource_manager
        try:
            from core.resources.manager import ResourceManager

            self._resource_manager = ResourceManager.instance()
        except Exception:
            self._resource_manager = None
        return self._resource_manager

    def _register(self, handle: int) -> str | None:
        manager = self._resolve_resource_manager()
        if manager is None or not hasattr(manager, "register_gl_handle"):
            return None
        try:
            return manager.register_gl_handle(
                handle,
                "query",
                description=f"GL timestamp stage query {handle}",
                group=self._resource_group,
                owner=self._owner,
                generation=self._generation,
                dimensions=None,
                format="GL_TIMESTAMP",
                tracked_bytes=None,
            )
        except Exception:
            logger.debug("[GL STAGE] resource registration failed", exc_info=True)
            return None

    def _slot_queries(self, slot: int) -> dict[str, int]:
        base = slot * len(STAGE_MARKERS)
        return {name: self._handles[base + i] for i, name in enumerate(STAGE_MARKERS)}

    # ----------------------------------------------------------------- frames
    def begin_frame(
        self,
        *,
        scene_generation: int,
        frame_index: int,
        transition: str,
        render_path: str,
    ) -> bool:
        """Claim a packet for this sampled frame, or drop attribution.

        Never waits. If no packet slot is free the frame contributes nothing.
        """
        if not self._supported or self._active is not None:
            return False
        if not self._free:
            self._dropped_no_capacity += 1
            return False
        slot = self._free.popleft()
        packet = StagePacket(
            scene_generation=int(scene_generation),
            frame_index=int(frame_index),
            transition=str(transition),
            render_path=str(render_path),
            query_ids=self._slot_queries(slot),
        )
        packet.cpu_ms["_slot"] = slot
        self._active = packet
        return True

    def mark(self, gl_api: Any, marker: str) -> None:
        """Place one GL_TIMESTAMP marker. Legal inside an active elapsed query."""
        packet = self._active
        if packet is None or marker not in packet.query_ids:
            return
        try:
            gl_api.glQueryCounter(packet.query_ids[marker], gl_api.GL_TIMESTAMP)
            packet.issued.add(marker)
        except Exception as exc:
            logger.debug("[GL STAGE] glQueryCounter failed: %s", exc)

    def end_frame(self) -> None:
        """Close the active packet and queue it for availability-checked collection."""
        packet = self._active
        self._active = None
        if packet is None:
            return
        if len(self._pending) == self._pending.maxlen:
            # Oldest in-flight packet is evicted; return its slot rather than wait.
            evicted = self._pending.popleft()
            self._release_slot(evicted)
            self._dropped_no_capacity += 1
        self._pending.append(packet)

    def _release_slot(self, packet: StagePacket) -> None:
        slot = packet.cpu_ms.pop("_slot", None)
        if slot is not None:
            self._free.append(int(slot))

    # ------------------------------------------------------------- collection
    def poll(self, gl_api: Any) -> None:
        """Collect results that are already available. Never blocks."""
        if not self._supported or not self._pending:
            return
        still_pending: deque[StagePacket] = deque(maxlen=self._pending.maxlen)
        for packet in self._pending:
            if self._try_collect(gl_api, packet):
                self._release_slot(packet)
                packet.complete = True
                self._completed.append(packet)
            else:
                still_pending.append(packet)
        self._pending = still_pending

    def abandon_frame(self) -> None:
        """Release the active packet's slot without waiting for markers.

        Used when a sampled frame returns early - the QPainter fallback, or a
        shader path that bailed - so a never-issued query cannot wedge the ring.
        """
        packet = self._active
        self._active = None
        if packet is not None:
            self._release_slot(packet)

    def _try_collect(self, gl_api: Any, packet: StagePacket) -> bool:
        # Only markers actually submitted can ever resolve.
        for marker in list(packet.issued):
            handle = packet.query_ids[marker]
            if marker in packet.results_ns:
                continue
            try:
                available = (ctypes.c_uint32 * 1)()
                gl_api.glGetQueryObjectuiv(
                    handle, gl_api.GL_QUERY_RESULT_AVAILABLE, available
                )
                if not available[0]:
                    return False
                out = (ctypes.c_uint64 * 1)()
                gl_api.glGetQueryObjectui64v(handle, gl_api.GL_QUERY_RESULT, out)
                packet.results_ns[marker] = int(out[0])
            except Exception as exc:
                logger.debug("[GL STAGE] result fetch failed: %s", exc)
                return False
        return True

    def take_completed(self) -> list[StagePacket]:
        """Drain fully collected packets for post-hoc association."""
        drained = list(self._completed)
        self._completed.clear()
        return drained

    # ---------------------------------------------------------------- cleanup
    def cleanup(self, gl_api: Any) -> None:
        """Delete query objects on the owning context. Failure retains ownership."""
        if not self._handles:
            return
        if gl_api is None:
            raise RuntimeError(
                "GLStageTimestampRing.cleanup called without a GL API; "
                "query ownership retained"
            )
        surviving: list[int] = []
        surviving_ids: list[str | None] = []
        for handle, resource_id in zip(self._handles, self._resource_ids):
            try:
                gl_api.glDeleteQueries(1, [handle])
            except Exception as exc:
                logger.error(
                    "[GL STAGE] Failed to delete timestamp query %s owner=%s gen=%s: %s",
                    handle,
                    self._owner,
                    self._generation,
                    exc,
                )
                surviving.append(handle)
                surviving_ids.append(resource_id)
                continue
            self._release_tracking(resource_id)
        self._handles = surviving
        self._resource_ids = surviving_ids
        self._active = None
        self._pending.clear()
        self._completed.clear()
        self._free.clear()
        self._supported = False
        if surviving:
            raise RuntimeError(
                f"GLStageTimestampRing retained {len(surviving)} undeleted queries"
            )

    def _release_tracking(self, resource_id: str | None) -> None:
        manager = self._resolve_resource_manager()
        if manager is None or resource_id is None:
            return
        try:
            if hasattr(manager, "release_tracking"):
                manager.release_tracking(resource_id)
        except Exception:
            logger.debug("[GL STAGE] resource release failed", exc_info=True)
