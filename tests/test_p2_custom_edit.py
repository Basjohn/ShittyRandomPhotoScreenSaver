"""P2-CUSTOM-EDIT: edit mode on the finalized single-surface contract.

CUSTOM still carried assumptions from the retired independently presented
visualizer surface:

* the edit preview was built from ``overlay.grabFramebuffer()`` plus a grab of
  the card QWidget - the overlay owns no framebuffer any more, and the card
  paints nothing while the compositor owns its visual, so both halves were
  blank;
* ``overlay.show()``/``hide()``/``isVisible()`` were treated as presentation
  truth, so entering edit mode suspended nothing the compositor was drawing.

The corrected contract: one compositor-owned snapshot at edit entry, compositor
presentation suspended without destroying generation-owned GL resources, preview
drag/resize that never touches the GPU, and a single restore on Cancel/Save.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QRect

from rendering import custom_layout_manager as clm
from rendering.gl_compositor import GLCompositorWidget
from rendering.gl_compositor_pkg.visualizer_layer import (
    CompositorVisualizerLayer,
    VisualizerRenderState,
)


# ---------------------------------------------------------------------------
# The retired surface is gone
# ---------------------------------------------------------------------------


class TestNoRetiredSurfaceDependency:
    def test_custom_layout_never_grabs_the_overlay_framebuffer(self):
        source = inspect.getsource(clm)
        assert "grabFramebuffer" not in source, (
            "the visualizer overlay is not a presented surface and owns no framebuffer"
        )

    def test_the_preview_comes_from_the_compositor(self):
        source = inspect.getsource(clm.CustomLayoutManager._capture_visualizer_shell_snapshot)
        assert "_capture_compositor_visualizer_scene" in source

    def test_the_snapshot_seam_is_compositor_owned(self):
        source = inspect.getsource(clm.CustomLayoutManager._capture_compositor_visualizer_scene)
        assert "_gl_compositor" in source
        assert "capture_visualizer_scene_pixmap" in source

    def test_edit_pause_suspends_compositor_presentation_not_widget_visibility(self):
        source = inspect.getsource(clm.CustomLayoutManager._pause_visualizer_for_edit_mode)
        assert "_suspend_compositor_visualizer_presentation" in source
        assert "overlay.hide()" not in source

    def test_restore_does_not_show_the_overlay_widget(self):
        source = inspect.getsource(clm.CustomLayoutManager._restore_special_widgets)
        assert "overlay.show()" not in source, (
            "overlay visibility is not presentation truth"
        )


# ---------------------------------------------------------------------------
# Suspension retains generation-owned GL resources
# ---------------------------------------------------------------------------


class TestSuspensionRetainsResources:
    def test_suspend_only_clears_published_state(self):
        source = inspect.getsource(
            clm.CustomLayoutManager._suspend_compositor_visualizer_presentation
        )
        assert "clear_visualizer_state" in source
        for forbidden in ("cleanup", "cleanup_gl", "releaseResources", "_destroy_parent_overlay"):
            assert forbidden not in source

    def test_clearing_the_layer_keeps_its_destruction_authority(self):
        """Hiding must never lose the reference needed to free the GL later."""
        owner = object()
        layer = CompositorVisualizerLayer(SimpleNamespace())
        layer.publish(VisualizerRenderState(owner, QRect(0, 0, 400, 200)))
        assert layer._resource_owner is owner

        layer.clear()

        assert layer.state is None, "presentation state must be released"
        assert layer._resource_owner is owner, (
            "an edit session must not drop card/visualizer destruction authority"
        )

    def test_clear_visualizer_state_releases_both_liveness_reasons(self):
        released: list[str] = []
        layer = CompositorVisualizerLayer(SimpleNamespace())
        layer.publish(VisualizerRenderState(object(), QRect(0, 0, 10, 10)))
        comp = SimpleNamespace(
            _visualizer_layer=layer,
            PRESENTATION_VISUALIZER_ACTIVE=GLCompositorWidget.PRESENTATION_VISUALIZER_ACTIVE,
            PRESENTATION_VISUALIZER_PREPARING=GLCompositorWidget.PRESENTATION_VISUALIZER_PREPARING,
            release_presentation_reason=released.append,
        )
        GLCompositorWidget.clear_visualizer_state(comp)
        assert released == [
            GLCompositorWidget.PRESENTATION_VISUALIZER_ACTIVE,
            GLCompositorWidget.PRESENTATION_VISUALIZER_PREPARING,
        ]


# ---------------------------------------------------------------------------
# One snapshot, serviced inside the render pass
# ---------------------------------------------------------------------------


class TestSnapshotSeam:
    def _layer(self):
        layer = CompositorVisualizerLayer(SimpleNamespace())
        return layer

    def test_capture_is_not_requested_by_default(self):
        layer = self._layer()
        assert layer._capture_requested is False
        assert layer.take_captured_scene_image() is None

    def test_a_request_is_serviced_once_and_popped_once(self, monkeypatch):
        layer = self._layer()
        layer.request_scene_capture()
        assert layer._capture_requested is True

        layer._capture_requested = False
        layer._captured_scene_image = "image"
        assert layer.take_captured_scene_image() == "image"
        assert layer.take_captured_scene_image() is None

    def test_clearing_the_layer_drops_an_unserviced_request(self):
        layer = self._layer()
        layer.publish(VisualizerRenderState(object(), QRect(0, 0, 10, 10)))
        layer.request_scene_capture()
        layer._captured_scene_image = "stale"

        layer.clear()

        assert layer._capture_requested is False
        assert layer.take_captured_scene_image() is None, (
            "a stale edit snapshot must not survive into the next session"
        )

    def test_capture_renders_card_local_rather_than_display_local(self):
        """Otherwise the preview carries the card's display position baked in."""
        source = inspect.getsource(CompositorVisualizerLayer._capture_scene_image)
        assert "_compositor_mask_origin_px = (0.0, 0.0)" in source
        assert "glReadPixels" in source
        # It must render into its own target, not read back the display.
        assert "glGenFramebuffers" in source
        assert "glClearColor(0.0, 0.0, 0.0, 0.0)" in source

    def test_capture_uses_separate_alpha_blending(self):
        source = inspect.getsource(CompositorVisualizerLayer._capture_scene_image)
        assert "glBlendFuncSeparate" in source, (
            "straight SRC_ALPHA compositing onto a transparent target loses alpha"
        )

    def test_capture_releases_its_target(self):
        source = inspect.getsource(CompositorVisualizerLayer._capture_scene_image)
        for deleter in ("glDeleteFramebuffers", "glDeleteTextures", "glDeleteRenderbuffers"):
            assert deleter in source
        tree = ast.parse(textwrap.dedent(source)).body[0]
        assert any(
            isinstance(node, ast.Try) and node.finalbody for node in ast.walk(tree)
        ), "the capture target must be released on every path"

    def test_the_compositor_seam_discards_the_whole_surface_image(self):
        source = inspect.getsource(GLCompositorWidget.capture_visualizer_scene_pixmap)
        assert "take_captured_scene_image" in source
        # The forced grab exists only to drive one render pass.
        assert "self.grabFramebuffer()" in source
        assert "QPixmap.fromImage(image)" in source

    def test_the_seam_refuses_when_nothing_is_being_presented(self):
        source = inspect.getsource(GLCompositorWidget.capture_visualizer_scene_pixmap)
        assert "has_visible_state" in source


# ---------------------------------------------------------------------------
# Drag/resize stays a preview
# ---------------------------------------------------------------------------


class TestDragResizeStaysAPreview:
    def test_live_geometry_application_does_not_touch_the_compositor(self):
        source = inspect.getsource(
            clm.CustomLayoutManager._apply_live_shell_geometry_for_widget_id
        )
        for forbidden in (
            "_gl_compositor",
            "capture_visualizer_scene_pixmap",
            "ensure_uploaded",
            "publish_visualizer_state",
        ):
            assert forbidden not in source, (
                "mouse-driven preview geometry must not become live GPU work"
            )

    def test_the_snapshot_is_taken_once_per_shell_creation(self):
        source = inspect.getsource(clm.CustomLayoutManager._create_shell_state)
        assert source.count("_capture_visualizer_shell_snapshot") == 1


# ---------------------------------------------------------------------------
# Cancel / Save restore exactly once
# ---------------------------------------------------------------------------


class TestRestoreHappensOnce:
    def _manager(self):
        manager = clm.CustomLayoutManager.__new__(clm.CustomLayoutManager)
        manager._special_hidden = []
        return manager

    def test_restore_resumes_the_visualizer_exactly_once(self):
        starts: list[int] = []

        vis = SimpleNamespace(start=lambda: starts.append(1))
        manager = self._manager()
        manager._paused_visualizer = (vis, True, None, False)

        clm.CustomLayoutManager._restore_special_widgets(manager)
        clm.CustomLayoutManager._restore_special_widgets(manager)

        assert starts == [1], "a second restore resumed the visualizer twice"
        assert manager._paused_visualizer is None

    def test_a_visualizer_that_was_not_visible_is_not_started(self):
        starts: list[int] = []
        vis = SimpleNamespace(start=lambda: starts.append(1))
        manager = self._manager()
        manager._paused_visualizer = (vis, False, None, False)

        clm.CustomLayoutManager._restore_special_widgets(manager)

        assert starts == []
        assert manager._paused_visualizer is None

    def test_pause_is_idempotent_within_one_session(self):
        suspends: list[int] = []

        manager = clm.CustomLayoutManager.__new__(clm.CustomLayoutManager)
        manager._paused_visualizer = None
        manager._display = SimpleNamespace(_spotify_bars_overlay=None)
        manager._suspend_compositor_visualizer_presentation = lambda: suspends.append(1)

        vis = SimpleNamespace(
            isVisible=lambda: True,
            stop=lambda: None,
            hide=lambda: None,
        )
        clm.CustomLayoutManager._pause_visualizer_for_edit_mode(manager, vis)
        clm.CustomLayoutManager._pause_visualizer_for_edit_mode(manager, vis)

        assert suspends == [1], "presentation was suspended twice for one session"


# ---------------------------------------------------------------------------
# Stale generations cannot publish after a rebuild
# ---------------------------------------------------------------------------


class TestStaleGenerationCannotPublish:
    def test_a_retired_runtime_generation_is_rejected(self):
        """Save rebuilds the runtime; the old generation must not draw."""
        layer = CompositorVisualizerLayer(SimpleNamespace())
        comp = SimpleNamespace(
            _visualizer_layer=layer,
            PRESENTATION_VISUALIZER_ACTIVE=GLCompositorWidget.PRESENTATION_VISUALIZER_ACTIVE,
            PRESENTATION_VISUALIZER_PREPARING=GLCompositorWidget.PRESENTATION_VISUALIZER_PREPARING,
            parentWidget=lambda: SimpleNamespace(_runtime_generation=9),
            acquire_presentation_reason=lambda r: None,
            release_presentation_reason=lambda r: None,
        )
        GLCompositorWidget.publish_visualizer_state(
            comp, object(), QRect(0, 0, 400, 200), runtime_generation=8
        )
        assert layer.state is None

        GLCompositorWidget.publish_visualizer_state(
            comp, object(), QRect(0, 0, 400, 200), runtime_generation=9
        )
        assert layer.state is not None

    def test_a_stale_preparing_publication_is_also_rejected(self):
        layer = CompositorVisualizerLayer(SimpleNamespace())
        comp = SimpleNamespace(
            _visualizer_layer=layer,
            PRESENTATION_VISUALIZER_ACTIVE=GLCompositorWidget.PRESENTATION_VISUALIZER_ACTIVE,
            PRESENTATION_VISUALIZER_PREPARING=GLCompositorWidget.PRESENTATION_VISUALIZER_PREPARING,
            parentWidget=lambda: SimpleNamespace(_runtime_generation=9),
            acquire_presentation_reason=lambda r: None,
            release_presentation_reason=lambda r: None,
        )
        GLCompositorWidget.publish_visualizer_state(
            comp,
            object(),
            QRect(0, 0, 400, 200),
            runtime_generation=8,
            visible=False,
            preparing=True,
        )
        assert layer.state is None, "a retired generation must not even prepare"


# ---------------------------------------------------------------------------
# Geometry authority
# ---------------------------------------------------------------------------


class TestGeometryAuthority:
    @pytest.mark.parametrize("dpr", [1.0, 1.5, 2.0])
    def test_presentation_geometry_derives_from_the_compositor_dpr(self, dpr):
        from rendering.gl_compositor_pkg.visualizer_layer import PresentationGeometry

        rect = QRect(300, 120, 400, 200)
        geometry = PresentationGeometry(rect, dpr, int(600 * dpr))
        width_px, height_px = geometry.framebuffer_size_px
        assert width_px == round(400 * dpr)
        assert height_px == round(200 * dpr)
        # Card-local shaders keep authored geometry regardless of DPR.
        assert geometry.local_rect() == QRect(0, 0, 400, 200)

    def test_a_saved_non_zero_custom_rect_defines_the_preview(self):
        source = inspect.getsource(clm.CustomLayoutManager._create_shell_state)
        assert "prior_custom_rect" in source
        assert "prior_custom_rect.width() > 0" in source
