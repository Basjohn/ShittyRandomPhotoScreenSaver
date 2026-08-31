"""Sub-rect Quick item synchronizing immutable visualizer state."""

from __future__ import annotations

import threading
import time

from PySide6.QtCore import Slot, Qt
from PySide6.QtQuick import QQuickItem, QQuickWindow, QSGNode

from core.logging.logger import get_logger, is_viz_diagnostics_enabled
from widgets.spotify_visualizer.render_bridge import (
    VisualizerRenderIdentity,
    VisualizerSnapshotBridge,
)
from widgets.spotify_visualizer.render_state import (
    BubbleFrame,
    ResolvedVisualizerPresentation,
)

from .node import VisualizerRenderNode
from .telemetry import VisualizerRenderNodeTelemetry

logger = get_logger(__name__)


class _RenderNodeRetirement:
    """Direct render-thread invalidation owner for the current node."""

    def __init__(self, telemetry: VisualizerRenderNodeTelemetry) -> None:
        self._telemetry = telemetry
        self._lock = threading.Lock()
        self._node: VisualizerRenderNode | None = None

    def set_node(self, node: VisualizerRenderNode) -> None:
        with self._lock:
            self._node = node

    def invalidate(self) -> None:
        self._telemetry.note_invalidation()
        with self._lock:
            node = self._node
            self._node = None
        if node is not None:
            node.releaseResources()


class VisualizerRenderItem(QQuickItem):
    """Consume one latest immutable snapshot at the Quick sync boundary.

    Clipping is owned by the render node's single local SDF/stencil host. The
    pinned PySide scene-graph clip-node path failed its D3 runtime bar, so no
    second selectable clip implementation remains.
    """

    def __init__(
        self,
        parent: QQuickItem | None = None,
        *,
        telemetry: VisualizerRenderNodeTelemetry | None = None,
    ) -> None:
        self._telemetry = telemetry or VisualizerRenderNodeTelemetry()
        self._retirement = _RenderNodeRetirement(self._telemetry)
        self._bridge: VisualizerSnapshotBridge | None = None
        self._identity: VisualizerRenderIdentity | None = None
        self._presentation: ResolvedVisualizerPresentation | None = None
        self._bound_window: QQuickWindow | None = None
        self._diag_last_render_playing: bool | None = None
        self._diag_spectrum_handoff_remaining = 0
        self._diag_bubble_geometry_last_ts = 0.0
        self._diag_bubble_geometry_burst_remaining = 0
        super().__init__(parent)
        self.setFlag(QQuickItem.Flag.ItemHasContents, True)
        self.windowChanged.connect(self._bind_window_invalidation)
        self._bind_window_invalidation(self.window())

    @property
    def telemetry(self) -> VisualizerRenderNodeTelemetry:
        return self._telemetry

    @property
    def render_identity(self) -> VisualizerRenderIdentity | None:
        return self._identity

    @property
    def presentation(self) -> ResolvedVisualizerPresentation | None:
        return self._presentation

    def bind_render_source(
        self,
        bridge: VisualizerSnapshotBridge,
        identity: VisualizerRenderIdentity,
    ) -> None:
        if not isinstance(bridge, VisualizerSnapshotBridge):
            raise TypeError("visualizer item requires a VisualizerSnapshotBridge")
        if not isinstance(identity, VisualizerRenderIdentity):
            raise TypeError("visualizer item requires a VisualizerRenderIdentity")
        if bridge.identity != identity:
            raise ValueError("visualizer bridge is not open for the requested identity")
        self._bridge = bridge
        self._identity = identity
        self.update()

    def clear_render_source(self) -> None:
        if self._bridge is None and self._identity is None:
            return
        self._bridge = None
        self._identity = None
        self.update()

    def set_presentation(
        self,
        presentation: ResolvedVisualizerPresentation | None,
    ) -> None:
        if presentation is not None and not isinstance(
            presentation,
            ResolvedVisualizerPresentation,
        ):
            raise TypeError("visualizer presentation must already be resolved")
        if presentation == self._presentation:
            return
        self._presentation = presentation
        if presentation is not None:
            _x, _y, width, height = presentation.outer_rect
            self.setX(0.0)
            self.setY(0.0)
            self.setWidth(width)
            self.setHeight(height)
        self.update()

    @Slot(QQuickWindow)
    def _bind_window_invalidation(self, window: QQuickWindow | None) -> None:
        bound_window = getattr(self, "_bound_window", None)
        retirement = getattr(self, "_retirement", None)
        if window is bound_window or retirement is None:
            return
        if bound_window is not None:
            try:
                bound_window.sceneGraphInvalidated.disconnect(retirement.invalidate)
            except (RuntimeError, TypeError):
                pass
        self._bound_window = window
        if window is not None:
            window.sceneGraphInvalidated.connect(
                retirement.invalidate,
                Qt.ConnectionType.DirectConnection,
            )

    def _create_render_node(self) -> VisualizerRenderNode:
        return VisualizerRenderNode(self._telemetry)

    def updatePaintNode(
        self,
        old_node: QSGNode | None,
        _update_data: QQuickItem.UpdatePaintNodeData,
    ) -> QSGNode:
        node = (
            old_node
            if isinstance(old_node, VisualizerRenderNode)
            else self._create_render_node()
        )
        presentation = self._presentation
        bridge = self._bridge
        identity = self._identity
        snapshot = None
        clear_snapshot = presentation is None or identity is None
        if bridge is not None and identity is not None and presentation is not None:
            snapshot = bridge.take_for_render(
                runtime_generation=identity.runtime_generation,
                engine_generation=identity.engine_generation,
                activation_id=identity.activation_id,
                mode_id=identity.mode_id,
            )
            if snapshot is not None and snapshot.presentation != presentation:
                self._telemetry.note_error(
                    "visualizer snapshot presentation does not match committed item geometry"
                )
                snapshot = None
                clear_snapshot = True

        if snapshot is not None and is_viz_diagnostics_enabled():
            logical = snapshot.logical
            common = logical.common
            playing = bool(logical.playing)
            previous = self._diag_last_render_playing
            bars_level = max((float(value) for value in common.bars), default=0.0)
            energy = common.energy
            energy_level = max(
                float(energy.overall),
                float(energy.bass),
                float(energy.mid),
                float(energy.high),
            )
            waveform_level = max(
                (abs(float(value)) for value in common.waveform),
                default=0.0,
            )
            if previous is not None and previous != playing:
                source_age_ms = -1.0
                if logical.source_timestamp is not None:
                    source_age_ms = max(
                        0.0,
                        (time.time() - logical.source_timestamp) * 1000.0,
                    )
                logger.debug(
                    "[VIS_PLAYBACK_EDGE] stage=T7 mode=%s playing=%s revision=%d "
                    "source=%d/%d source_age_ms=%.1f energy_level=%.3f "
                    "bars_level=%.3f waveform_level=%.3f",
                    logical.mode_id,
                    playing,
                    snapshot.logical_revision,
                    logical.source_generation,
                    logical.source_activation_id,
                    source_age_ms,
                    energy_level,
                    bars_level,
                    waveform_level,
                )
                if logical.mode_id == "spectrum" and not playing:
                    # Capture only the first few retained states after pause so
                    # a physical zero->idle-floor handoff is attributable to
                    # authored/bridge state without adding a diagnostic timer.
                    self._diag_spectrum_handoff_remaining = 4
            if (
                logical.mode_id == "spectrum"
                and not playing
                and self._diag_spectrum_handoff_remaining > 0
            ):
                logger.debug(
                    "[VIS_SPECTRUM_HANDOFF] revision=%d bars_level=%.3f "
                    "energy_level=%.3f source=%d/%d",
                    snapshot.logical_revision,
                    bars_level,
                    energy_level,
                    logical.source_generation,
                    logical.source_activation_id,
                )
                self._diag_spectrum_handoff_remaining -= 1
            if logical.mode_id == "bubble" and isinstance(
                logical.mode_state,
                BubbleFrame,
            ):
                if previous is None or previous != playing:
                    self._diag_bubble_geometry_burst_remaining = 8
                now_mono = time.monotonic()
                interval_s = (
                    0.12
                    if self._diag_bubble_geometry_burst_remaining > 0
                    else 0.8
                )
                if (
                    self._diag_bubble_geometry_last_ts <= 0.0
                    or now_mono - self._diag_bubble_geometry_last_ts >= interval_s
                    or (
                        previous is not None
                        and previous != playing
                    )
                ):
                    mode_state = logical.mode_state
                    geometry = dict(mode_state.geometry_diagnostics)
                    frozen_big_max_radius = geometry.get(
                        "frozen_big_max_radius",
                        max(mode_state.positions[2::4], default=0.0),
                    )
                    frozen_max_alpha = geometry.get(
                        "frozen_max_alpha",
                        max(mode_state.positions[3::4], default=0.0),
                    )
                    content_height = float(presentation.content_rect[3])
                    logical_radius_px = frozen_big_max_radius * content_height
                    device_radius_px = logical_radius_px * float(presentation.dpr)
                    logger.debug(
                        "[VIS_BUBBLE_GEOMETRY] stage=B8 revision=%d "
                        "sim_ts=%.6f playing=%s final_big_max_r=%.5f "
                        "frozen_big_max_r=%.5f radius_logical_px=%.2f "
                        "radius_device_px=%.2f dpr=%.3f alpha=%.3f "
                        "domain_h=%.3f "
                        "track(token=%.0f index=%.0f target=%.5f "
                        "display=%.5f delta=%.5f step=%.5f "
                        "rate_hz=%.3f mix=%.3f)",
                        snapshot.logical_revision,
                        mode_state.simulation_timestamp,
                        playing,
                        geometry.get("final_big_max_radius", 0.0),
                        frozen_big_max_radius,
                        logical_radius_px,
                        device_radius_px,
                        presentation.dpr,
                        frozen_max_alpha,
                        geometry.get("domain_h", 1.0),
                        geometry.get("tracked_big_token", 0.0),
                        geometry.get("tracked_big_index", -1.0),
                        geometry.get("tracked_big_target_radius", 0.0),
                        geometry.get("tracked_big_display_radius", 0.0),
                        geometry.get("tracked_big_target_delta", 0.0),
                        geometry.get("tracked_big_smoothing_step", 0.0),
                        geometry.get("tracked_big_smoothing_rate_hz", 0.0),
                        geometry.get("tracked_big_smoothing_mix", 0.0),
                    )
                    self._diag_bubble_geometry_last_ts = now_mono
                    if self._diag_bubble_geometry_burst_remaining > 0:
                        self._diag_bubble_geometry_burst_remaining -= 1
            self._diag_last_render_playing = playing

        logical_size = (
            (0.0, 0.0)
            if presentation is None
            else (presentation.outer_rect[2], presentation.outer_rect[3])
        )
        node.synchronize(
            identity=identity,
            snapshot=snapshot,
            logical_size=logical_size,
            device_pixel_ratio=(1.0 if presentation is None else presentation.dpr),
            clear_snapshot=clear_snapshot,
        )
        self._retirement.set_node(node)
        return node


__all__ = ["VisualizerRenderItem"]
