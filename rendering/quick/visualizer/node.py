"""Inline QSGRenderNode foundation for immutable visualizer snapshots."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtQuick import QSGRenderNode

from widgets.spotify_visualizer.render_bridge import VisualizerRenderIdentity
from widgets.spotify_visualizer.render_state import VisualizerRenderSnapshot

from .clip_host import VisualizerClipHost
from .telemetry import VisualizerRenderNodeTelemetry


def _rect_tuple(value: object) -> tuple[int, int, int, int] | None:
    if value is None:
        return None
    try:
        return (
            int(value.x()),
            int(value.y()),
            int(value.width()),
            int(value.height()),
        )
    except (AttributeError, TypeError, ValueError):
        return None


class VisualizerRenderNode(QSGRenderNode):
    """Render-thread owner for one current visualizer activation.

    Mode GL implementations land behind this node in the following Phase-D
    checkpoints.  This foundation already owns identity reset, immutable state,
    clip-state observation, bounded geometry, and legal invalidation teardown.
    """

    def __init__(
        self,
        telemetry: VisualizerRenderNodeTelemetry | None = None,
    ) -> None:
        super().__init__()
        self._telemetry = telemetry or VisualizerRenderNodeTelemetry()
        self._identity: VisualizerRenderIdentity | None = None
        self._snapshot: VisualizerRenderSnapshot | None = None
        self._logical_size = (0.0, 0.0)
        self._device_pixel_ratio = 1.0
        self._clip_host = VisualizerClipHost()
        self._released = False

    @property
    def identity(self) -> VisualizerRenderIdentity | None:
        return self._identity

    @property
    def snapshot(self) -> VisualizerRenderSnapshot | None:
        return self._snapshot

    @property
    def telemetry(self) -> VisualizerRenderNodeTelemetry:
        return self._telemetry

    @property
    def clip_host(self) -> VisualizerClipHost:
        return self._clip_host

    def synchronize(
        self,
        *,
        identity: VisualizerRenderIdentity | None,
        snapshot: VisualizerRenderSnapshot | None,
        logical_size: tuple[float, float],
        device_pixel_ratio: float,
        clear_snapshot: bool = False,
    ) -> None:
        """Accept detached state during the blocked-GUI synchronization phase."""

        if identity != self._identity:
            self._identity = identity
            self._snapshot = None
        if clear_snapshot:
            self._snapshot = None
        if snapshot is not None:
            if identity is None:
                raise ValueError("visualizer snapshot requires an active identity")
            logical = snapshot.logical
            snapshot_identity = VisualizerRenderIdentity(
                runtime_generation=logical.runtime_generation,
                engine_generation=logical.engine_generation,
                activation_id=logical.activation_id,
                mode_id=logical.mode_id,
            )
            if snapshot_identity != identity:
                raise ValueError("visualizer snapshot identity does not match render node")
            self._snapshot = snapshot
        self._logical_size = (
            max(0.0, float(logical_size[0])),
            max(0.0, float(logical_size[1])),
        )
        self._device_pixel_ratio = max(0.01, float(device_pixel_ratio))
        self._telemetry.note_sync()

    def rect(self) -> QRectF:
        return QRectF(0.0, 0.0, *self._logical_size)

    def flags(self) -> QSGRenderNode.RenderingFlag:
        return QSGRenderNode.RenderingFlag.BoundedRectRendering

    def changedStates(self) -> QSGRenderNode.StateFlag:
        # The foundation changes no GL state.  Mode implementations must
        # preserve inherited scene-graph state before this remains true.
        return QSGRenderNode.StateFlag(0)

    def render(self, state: QSGRenderNode.RenderState) -> None:
        """Record the inherited clip contract without advancing logical state."""

        try:
            scissor_enabled = bool(state.scissorEnabled())
            stencil_enabled = bool(state.stencilEnabled())
            self._telemetry.note_render(
                scissor_enabled=scissor_enabled,
                scissor_rect=(
                    _rect_tuple(state.scissorRect()) if scissor_enabled else None
                ),
                stencil_enabled=stencil_enabled,
                stencil_value=(
                    int(state.stencilValue()) if stencil_enabled else None
                ),
            )
        except Exception as exc:
            self._telemetry.note_error(f"{type(exc).__name__}: {exc}")

    def releaseResources(self) -> None:
        """Retire node-owned state on Qt Quick's render/context owner."""

        if self._released:
            return
        try:
            self._clip_host.release_resources()
        except Exception as exc:
            self._telemetry.note_error(
                f"visualizer resource release failed: {type(exc).__name__}: {exc}"
            )
            return
        self._released = True
        self._snapshot = None
        self._identity = None
        self._telemetry.note_release()


__all__ = ["VisualizerRenderNode"]
