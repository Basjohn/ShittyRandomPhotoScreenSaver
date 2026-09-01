"""Bounded immutable handoff into the Qt Quick visualizer renderer.

The bridge owns one current snapshot for one explicitly opened runtime/engine
activation.  It is deliberately not a queue: newer state replaces older
unread state.  Protected authored results are coalesced by edge kind until the
next synchronization consume, so a short-lived result can survive without
turning presentation into catch-up replay.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, replace

from widgets.spotify_visualizer.render_state import (
    VisualizerProtectedEdge,
    VisualizerRenderSnapshot,
)


_MAX_PROTECTED_EDGE_KINDS = 8


@dataclass(frozen=True, slots=True)
class VisualizerRenderIdentity:
    runtime_generation: int
    engine_generation: int
    activation_id: int
    mode_id: str

    def __post_init__(self) -> None:
        for name in ("runtime_generation", "engine_generation", "activation_id"):
            value = int(getattr(self, name))
            if value < 0:
                raise ValueError(f"{name} must be non-negative")
            object.__setattr__(self, name, value)
        mode_id = str(self.mode_id or "").strip().lower()
        if not mode_id:
            raise ValueError("mode_id must not be empty")
        object.__setattr__(self, "mode_id", mode_id)


class VisualizerSnapshotBridge:
    """One latest immutable render snapshot for an explicit activation."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._identity: VisualizerRenderIdentity | None = None
        self._snapshot: VisualizerRenderSnapshot | None = None
        self._protected_edges: dict[str, VisualizerProtectedEdge] = {}
        self._last_revision = 0
        self._superseded_count = 0
        self._rejected_count = 0
        self._presentation_mismatch_count = 0

    @property
    def identity(self) -> VisualizerRenderIdentity | None:
        with self._lock:
            return self._identity

    @property
    def is_open(self) -> bool:
        with self._lock:
            return self._identity is not None

    @property
    def superseded_count(self) -> int:
        with self._lock:
            return self._superseded_count

    @property
    def rejected_count(self) -> int:
        with self._lock:
            return self._rejected_count

    @property
    def presentation_mismatch_count(self) -> int:
        with self._lock:
            return self._presentation_mismatch_count

    def begin_activation(
        self,
        *,
        runtime_generation: int,
        engine_generation: int,
        activation_id: int,
        mode_id: str,
    ) -> VisualizerRenderIdentity:
        """Open admission for one exact generation-scoped activation."""

        identity = VisualizerRenderIdentity(
            runtime_generation=runtime_generation,
            engine_generation=engine_generation,
            activation_id=activation_id,
            mode_id=mode_id,
        )
        with self._lock:
            if self._identity == identity:
                return identity
            self._identity = identity
            self._snapshot = None
            self._protected_edges.clear()
            self._last_revision = 0
        return identity

    def close_admission(self) -> None:
        """Reject future publication and remove all state from render reach."""

        with self._lock:
            self._identity = None
            self._snapshot = None
            self._protected_edges.clear()
            self._last_revision = 0

    @staticmethod
    def _snapshot_identity(
        snapshot: VisualizerRenderSnapshot,
    ) -> VisualizerRenderIdentity | None:
        logical = snapshot.logical
        try:
            return VisualizerRenderIdentity(
                runtime_generation=logical.runtime_generation,
                engine_generation=logical.engine_generation,
                activation_id=logical.activation_id,
                mode_id=logical.mode_id,
            )
        except ValueError:
            return None

    def _merge_protected_edges(
        self,
        incoming: tuple[VisualizerProtectedEdge, ...],
    ) -> tuple[VisualizerProtectedEdge, ...]:
        merged = dict(self._protected_edges)
        for edge in incoming:
            current = merged.get(edge.kind)
            if current is None or edge.token >= current.token:
                merged[edge.kind] = edge
        if len(merged) > _MAX_PROTECTED_EDGE_KINDS:
            raise RuntimeError(
                "visualizer protected-edge kinds exceeded the bounded bridge contract"
            )
        self._protected_edges = merged
        return tuple(
            merged[kind]
            for kind in sorted(merged)
        )

    def publish(self, snapshot: VisualizerRenderSnapshot) -> bool:
        """Admit one complete immutable snapshot when identity is current."""

        if not isinstance(snapshot, VisualizerRenderSnapshot):
            raise TypeError("render bridge accepts only VisualizerRenderSnapshot")
        snapshot_identity = self._snapshot_identity(snapshot)
        with self._lock:
            if (
                self._identity is None
                or snapshot_identity != self._identity
                or snapshot.logical_revision <= self._last_revision
            ):
                self._rejected_count += 1
                return False
            merged_edges = self._merge_protected_edges(
                snapshot.logical.protected_edges
            )
            if merged_edges != snapshot.logical.protected_edges:
                logical = replace(snapshot.logical, protected_edges=merged_edges)
                snapshot = replace(snapshot, logical=logical)
            if self._snapshot is not None:
                self._superseded_count += 1
            self._snapshot = snapshot
            self._last_revision = snapshot.logical_revision
            return True

    def peek(self) -> VisualizerRenderSnapshot | None:
        """Inspect the current slot without acknowledging presentation."""

        with self._lock:
            return self._snapshot

    def take_for_render(
        self,
        *,
        runtime_generation: int,
        engine_generation: int,
        activation_id: int,
        mode_id: str,
        required_presentation: object | None = None,
        allow_presentation_rebase: bool = False,
    ) -> VisualizerRenderSnapshot | None:
        """Consume the slot at the Quick synchronization boundary.

        This is synchronization consumption only. It is not a paint/swap
        acknowledgement and never feeds producer admission or logical cadence.
        """

        try:
            requested = VisualizerRenderIdentity(
                runtime_generation=runtime_generation,
                engine_generation=engine_generation,
                activation_id=activation_id,
                mode_id=mode_id,
            )
        except ValueError:
            return None
        with self._lock:
            if self._identity != requested:
                return None
            snapshot = self._snapshot
            if (
                snapshot is not None
                and required_presentation is not None
                and snapshot.presentation != required_presentation
            ):
                if allow_presentation_rebase:
                    # During an active CUSTOM session the editor is the explicit
                    # authority for temporary working geometry.  Logical mode
                    # state remains newest-state truth, so rebase only the
                    # immutable presentation record instead of rejecting every
                    # fresh revision while a wheel/corner/edge resize is active.
                    snapshot = replace(
                        snapshot,
                        presentation=required_presentation,
                    )
                else:
                    # Outside CUSTOM, a geometry mismatch is stale presentation
                    # and must not be consumed. Keep the last admitted pixels
                    # until the next coherent publication supersedes this slot.
                    self._presentation_mismatch_count += 1
                    return None
            self._snapshot = None
            self._protected_edges.clear()
            return snapshot


__all__ = [
    "VisualizerRenderIdentity",
    "VisualizerSnapshotBridge",
]
