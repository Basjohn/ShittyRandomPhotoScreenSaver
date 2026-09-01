"""Inline QSGRenderNode host for immutable visualizer snapshots."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QRectF
from PySide6.QtGui import QOpenGLContext
from PySide6.QtQuick import QSGRenderNode

from core.logging.logger import get_logger

from widgets.spotify_visualizer.render_bridge import VisualizerRenderIdentity
from widgets.spotify_visualizer.render_state import VisualizerRenderSnapshot

from .clip_host import VisualizerClipFrame, VisualizerClipHost
from .render_contract import snapshot_is_render_admissible
from .render_host import QuickVisualizerRenderHost
from .telemetry import VisualizerRenderNodeTelemetry


logger = get_logger(__name__)


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

    Mode implementations resolve lazily behind one small common host.  This
    node owns identity reset, immutable state, the selected local clip, shared
    GL resources, and legal invalidation teardown.
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
        self._render_host = QuickVisualizerRenderHost()
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

    @property
    def render_host(self) -> QuickVisualizerRenderHost:
        return self._render_host

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
            if snapshot_is_render_admissible(snapshot):
                self._snapshot = snapshot
            else:
                # A playing source-gated mode keeps its last admitted idle/live
                # pixels until a current source replaces them. A non-present
                # logical publication likewise cannot erase a valid scene.
                self._telemetry.note_admission_rejected()
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
        return (
            QSGRenderNode.StateFlag.BlendState
            | QSGRenderNode.StateFlag.CullState
            | QSGRenderNode.StateFlag.DepthState
            | QSGRenderNode.StateFlag.StencilState
        )

    def _inherited_scene_opacity(self) -> float:
        """Return the QML-inherited opacity applied to this node's content.

        ``QSGRenderNode.inheritedOpacity()`` carries the effective opacity of the
        item subtree (here: authored visualizer scene fade x generation startup
        reveal gate). It is clamped to ``[0, 1]``; any binding/availability gap
        fails open to a fully opaque draw rather than hiding the visualizer.
        """

        getter = getattr(self, "inheritedOpacity", None)
        if not callable(getter):
            return 1.0
        try:
            return max(0.0, min(1.0, float(getter())))
        except (TypeError, ValueError):
            return 1.0

    def render(self, state: QSGRenderNode.RenderState) -> None:
        """Draw the latest admitted state without advancing logical state."""

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
            snapshot = self._snapshot
            if snapshot is None or min(self._logical_size) <= 0.0:
                return
            # The QML root's inherited opacity (the generation startup-reveal gate
            # multiplied by the authored scene fade) must fade the GL content
            # coherently with the card, exactly as it fades every other Quick
            # item. This node draws raw GL, so the scene graph cannot apply that
            # opacity for us; fold it into the authored content fade the shaders
            # already honour via ``u_fade``. Rebasing only allocates while the
            # scene is genuinely mid-fade, so steady-state rendering is unchanged.
            inherited_opacity = self._inherited_scene_opacity()
            if inherited_opacity < 1.0:
                presentation = snapshot.presentation
                snapshot = replace(
                    snapshot,
                    presentation=replace(
                        presentation,
                        content_fade=max(
                            0.0, presentation.content_fade * inherited_opacity
                        ),
                    ),
                )
            render_target = self.renderTarget()
            if render_target is None:
                raise RuntimeError("Quick visualizer has no active render target")
            target_size = render_target.pixelSize()
            viewport = (
                0,
                0,
                int(target_size.width()),
                int(target_size.height()),
            )
            if min(viewport[2:]) <= 0:
                raise RuntimeError(
                    f"Quick visualizer has invalid render target: {viewport[2:]}"
                )
            matrix = self.projectionMatrix() * self.matrix()
            matrix_values = tuple(float(value) for value in matrix.data())
            clip_frame = VisualizerClipFrame.from_presentation(
                snapshot.presentation,
                matrix_values=matrix_values,
                viewport=viewport,
            )
            clip_run = self._clip_host.begin(clip_frame, state)
            try:
                mode_id = self._render_host.render(
                    snapshot=snapshot,
                    viewport=viewport,
                    logical_size=self._logical_size,
                    matrix_values=matrix_values,
                )
            finally:
                self._clip_host.end(clip_run)
            self._telemetry.note_draw(
                mode_id,
                logical_revision=snapshot.logical_revision,
                logical_timestamp=snapshot.logical.logical_timestamp,
            )
        except Exception as exc:
            self._telemetry.note_error(f"{type(exc).__name__}: {exc}")
            logger.exception("[QUICK] Visualizer render node failed: %s", exc)

    def releaseResources(self) -> None:
        """Retire node-owned state on Qt Quick's render/context owner."""

        if self._released:
            return
        if QOpenGLContext.currentContext() is None and (
            self._clip_host.has_resources or self._render_host.has_resources
        ):
            self._telemetry.note_error(
                "visualizer resources released without a current GL context"
            )
            return
        errors: list[str] = []
        for label, release in (
            ("mode host", self._render_host.release_resources),
            ("clip host", self._clip_host.release_resources),
        ):
            try:
                release()
            except Exception as exc:
                errors.append(f"{label}:{type(exc).__name__}:{exc}")
        if errors:
            self._telemetry.note_error(
                "visualizer resource release failed: " + " | ".join(errors)
            )
            return
        self._released = True
        self._snapshot = None
        self._identity = None
        self._telemetry.note_release()


__all__ = ["VisualizerRenderNode"]
