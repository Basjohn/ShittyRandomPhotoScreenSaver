"""P2-SINGLE-SURFACE: one accelerated presentation surface per display.

P2-RHI measured that a second independently dirtied texture-backed surface
degrades delivery even when it shares the top-level QRhi. The correction is that
the visualizer stops being a presented surface at all and becomes a layer inside
the display compositor.

These bars pin the parts that a later change could silently undo:

* the visualizer must not reacquire a presentation surface of any class;
* accepted publications must equal logical integrations, independently of how
  often the display presents — explicitly NOT publications == paints;
* the card rect must be converted to display coordinates, including a non-zero
  CUSTOM offset and a DPR, rather than relying on the old overlay's local rect;
* the stencil mask reads gl_FragCoord, so it needs the display-space origin;
* a visualizer failure must clear the layer, never substitute CPU bars.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QRect

from rendering.gl_compositor import GLCompositorWidget
from rendering.gl_compositor_pkg import shader_dispatch
from rendering.gl_compositor_pkg.visualizer_layer import (
    CompositorVisualizerLayer,
    VisualizerRenderState,
)
from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay


class _RecordingGL:
    """Captures the GL state the layer sets, without a real context."""

    GL_SCISSOR_TEST = "scissor"
    GL_STENCIL_TEST = "stencil"
    GL_BLEND = "blend"
    GL_SRC_ALPHA = "src_alpha"
    GL_ONE_MINUS_SRC_ALPHA = "inv_src_alpha"

    def __init__(self) -> None:
        self.viewport = None
        self.scissor = None
        self.enabled: list[str] = []
        self.disabled: list[str] = []
        self.cleared_color = False
        self.color_mask = None
        self.stencil_mask = None

    def glColorMask(self, r, g, b, a):
        self.color_mask = (r, g, b, a)

    def glStencilMask(self, mask):
        self.stencil_mask = mask

    def glViewport(self, x, y, w, h):
        self.viewport = (x, y, w, h)

    def glScissor(self, x, y, w, h):
        self.scissor = (x, y, w, h)

    def glEnable(self, cap):
        self.enabled.append(cap)

    def glDisable(self, cap):
        self.disabled.append(cap)

    def glBlendFunc(self, *_a):
        pass

    def glUseProgram(self, *_a):
        pass

    def glBindVertexArray(self, *_a):
        pass

    def glClear(self, *_a):
        self.cleared_color = True


def _owner(*, enabled=True, fade=1.0):
    painted: list[tuple] = []
    owner = SimpleNamespace(
        _enabled=enabled,
        _fade=fade,
        _compositor_mask_origin_px=None,
        _presentation_geometry=None,
        painted=painted,
        initialize_layer_gl=lambda ctx: True,
    )
    owner.paint_layer = lambda rect, f: painted.append((QRect(rect), f))
    owner.parentWidget = lambda: None
    return owner


def _layer_with(owner, card_rect):
    comp = SimpleNamespace(
        _rhi_gl=SimpleNamespace(context=object(), generation=1, is_attached=lambda: True)
    )
    layer = CompositorVisualizerLayer(comp)
    layer.publish(VisualizerRenderState(owner, card_rect))
    return layer


# ---------------------------------------------------------------------------
# One surface per display
# ---------------------------------------------------------------------------


class TestOneAcceleratedSurfacePerDisplay:
    def test_visualizer_is_not_a_presented_surface(self):
        from PySide6.QtWidgets import QRhiWidget
        from PySide6.QtOpenGLWidgets import QOpenGLWidget

        assert not issubclass(SpotifyBarsGLOverlay, QOpenGLWidget)
        assert not issubclass(SpotifyBarsGLOverlay, QRhiWidget)

    def test_visualizer_module_references_no_surface_class(self):
        module_src = pytest.importorskip("widgets.spotify_bars_gl_overlay")
        tree = ast.parse(inspect.getsource(module_src))
        referenced = {
            alias.name.split(".")[-1]
            for node in ast.walk(tree)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        } | {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        for surface in ("QOpenGLWidget", "QRhiWidget", "ExternalOpenGLRhiWidget"):
            assert surface not in referenced, (
                f"the visualizer must not reacquire a {surface} presentation surface"
            )

    def test_visualizer_has_no_paint_or_surface_callbacks(self):
        for retired in ("paintGL", "initializeGL", "gl_render", "gl_initialize"):
            assert not hasattr(SpotifyBarsGLOverlay, retired), (
                f"{retired} implies a presentation surface"
            )

    def test_the_compositor_is_the_only_accelerated_surface(self):
        from rendering.gl_rhi_surface import ExternalOpenGLRhiWidget

        assert issubclass(GLCompositorWidget, ExternalOpenGLRhiWidget)

    def test_visualizer_owns_no_context_of_its_own(self):
        tree = ast.parse(inspect.getsource(SpotifyBarsGLOverlay))
        offenders = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
            and node.func.attr in {"makeCurrent", "doneCurrent", "isValid", "context"}
        }
        assert offenders == set(), f"QOpenGLWidget context ownership remains: {offenders}"


# ---------------------------------------------------------------------------
# Publication contract
# ---------------------------------------------------------------------------


class TestPublicationContract:
    def test_publication_goes_to_the_compositor_not_a_surface(self):
        method = ast.parse(
            textwrap.dedent(inspect.getsource(SpotifyBarsGLOverlay._request_frame_update))
        ).body[0]
        self_calls = {
            n.func.attr
            for n in ast.walk(method)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "self"
        }
        assert "update" not in self_calls
        assert "_publication_target_compositor" in self_calls

    def test_publication_is_latest_wins_not_a_queue(self):
        layer = CompositorVisualizerLayer(SimpleNamespace())
        first, second = object(), object()
        layer.publish(VisualizerRenderState(first, QRect(0, 0, 10, 10)))
        layer.publish(VisualizerRenderState(second, QRect(0, 0, 10, 10)))
        assert layer.state.owner is second, "only the latest state may survive"

    def test_stale_runtime_generation_is_rejected(self):
        comp = SimpleNamespace(
            _visualizer_layer=CompositorVisualizerLayer(SimpleNamespace()),
            _presentation_reasons=set(),
            PRESENTATION_VISUALIZER_ACTIVE=GLCompositorWidget.PRESENTATION_VISUALIZER_ACTIVE,
            parentWidget=lambda: SimpleNamespace(_runtime_generation=7),
            acquire_presentation_reason=lambda r: None,
            release_presentation_reason=lambda r: None,
        )
        GLCompositorWidget.publish_visualizer_state(
            comp, object(), QRect(0, 0, 10, 10), runtime_generation=3
        )
        assert comp._visualizer_layer.state is None, "stale generation must not draw"

    def test_current_generation_is_accepted_and_acquires_liveness(self):
        acquired: list[str] = []
        comp = SimpleNamespace(
            _visualizer_layer=CompositorVisualizerLayer(SimpleNamespace()),
            PRESENTATION_VISUALIZER_ACTIVE=GLCompositorWidget.PRESENTATION_VISUALIZER_ACTIVE,
            parentWidget=lambda: SimpleNamespace(_runtime_generation=7),
            acquire_presentation_reason=acquired.append,
            release_presentation_reason=lambda r: None,
        )
        GLCompositorWidget.publish_visualizer_state(
            comp, object(), QRect(0, 0, 10, 10), runtime_generation=7
        )
        assert comp._visualizer_layer.state is not None
        assert acquired == [GLCompositorWidget.PRESENTATION_VISUALIZER_ACTIVE]

    def test_invisible_publication_clears_and_releases(self):
        released: list[str] = []
        layer = CompositorVisualizerLayer(SimpleNamespace())
        layer.publish(VisualizerRenderState(object(), QRect(0, 0, 10, 10)))
        comp = SimpleNamespace(
            _visualizer_layer=layer,
            PRESENTATION_VISUALIZER_ACTIVE=GLCompositorWidget.PRESENTATION_VISUALIZER_ACTIVE,
            parentWidget=lambda: SimpleNamespace(_runtime_generation=1),
            acquire_presentation_reason=lambda r: None,
            release_presentation_reason=released.append,
        )
        GLCompositorWidget.publish_visualizer_state(
            comp, object(), QRect(0, 0, 10, 10), runtime_generation=1, visible=False
        )
        assert layer.state is None
        assert released == [GLCompositorWidget.PRESENTATION_VISUALIZER_ACTIVE]

    def test_no_admission_pacing_or_acknowledgement_was_introduced(self):
        """AST, not text: prose about the contract must not trip the bar."""
        method = ast.parse(
            textwrap.dedent(inspect.getsource(SpotifyBarsGLOverlay._request_frame_update))
        ).body[0]
        names = {n.id for n in ast.walk(method) if isinstance(n, ast.Name)}
        attrs = {n.attr for n in ast.walk(method) if isinstance(n, ast.Attribute)}
        forbidden = {
            "_update_pending", "singleShot", "QTimer", "elapsed", "monotonic",
            "_owner_target_fps", "target_fps", "acknowledge",
        }
        assert not ((names | attrs) & forbidden), (
            f"P2 must not add admission/pacing: {(names | attrs) & forbidden}"
        )


# ---------------------------------------------------------------------------
# Coordinates: card-local to display space
# ---------------------------------------------------------------------------


class TestDisplayCoordinateConversion:
    def _render(self, monkeypatch, card_rect, *, surface_h, dpr):
        rec = _RecordingGL()
        monkeypatch.setattr(
            "rendering.gl_compositor_pkg.visualizer_layer.gl", rec
        )
        monkeypatch.setattr(
            "widgets.spotify_visualizer.overlay_frame_shell.resolve_frame_fade",
            lambda o, l: 1.0,
        )
        owner = _owner()
        layer = _layer_with(owner, card_rect)
        drew = layer.render(surface_h, dpr)
        return rec, owner, drew

    def test_non_zero_custom_offset_maps_to_display_space(self, monkeypatch):
        """A CUSTOM card is rarely at (0, 0); the old local rect is not enough."""
        rec, owner, drew = self._render(
            monkeypatch, QRect(300, 120, 400, 200), surface_h=1080, dpr=1.0
        )
        assert drew
        # y is flipped: GL origin is bottom-left.
        assert rec.viewport == (300, 1080 - 120 - 200, 400, 200)
        assert rec.scissor == rec.viewport

    def test_device_pixel_ratio_scales_the_card_rect(self, monkeypatch):
        rec, _owner, drew = self._render(
            monkeypatch, QRect(100, 50, 200, 100), surface_h=1440, dpr=1.5
        )
        assert drew
        assert rec.viewport == (150, 1440 - 75 - 150, 300, 150)

    def test_shaders_still_receive_a_card_sized_local_rect(self, monkeypatch):
        """Authored geometry must not change because the target got bigger."""
        _rec, owner, drew = self._render(
            monkeypatch, QRect(300, 120, 400, 200), surface_h=1080, dpr=1.0
        )
        assert drew
        (local_rect, fade), = owner.painted
        assert local_rect == QRect(0, 0, 400, 200)
        assert fade == 1.0

    def test_mask_origin_is_published_in_display_space(self, monkeypatch):
        """The mask shader reads gl_FragCoord, which is window space."""
        seen: list[tuple] = []
        rec = _RecordingGL()
        monkeypatch.setattr("rendering.gl_compositor_pkg.visualizer_layer.gl", rec)
        monkeypatch.setattr(
            "widgets.spotify_visualizer.overlay_frame_shell.resolve_frame_fade",
            lambda o, l: 1.0,
        )
        owner = _owner()
        owner.paint_layer = lambda r, f: seen.append(owner._compositor_mask_origin_px)
        layer = _layer_with(owner, QRect(300, 120, 400, 200))
        layer.render(1080, 1.0)
        assert seen == [(300.0, 760.0)]

    def test_mask_origin_is_cleared_after_the_frame(self, monkeypatch):
        _rec, owner, _drew = self._render(
            monkeypatch, QRect(10, 10, 100, 100), surface_h=600, dpr=1.0
        )
        assert owner._compositor_mask_origin_px is None

    def test_mask_uniform_adds_the_display_origin(self):
        source = inspect.getsource(
            SpotifyBarsGLOverlay._draw_painted_card_stencil_mask
        )
        assert "_compositor_mask_origin_px" in source
        assert "origin_x" in source and "origin_y" in source


# ---------------------------------------------------------------------------
# Scene safety
# ---------------------------------------------------------------------------


class TestSceneSafety:
    def test_layer_scissors_every_write_to_the_card(self, monkeypatch):
        rec = _RecordingGL()
        monkeypatch.setattr("rendering.gl_compositor_pkg.visualizer_layer.gl", rec)
        monkeypatch.setattr(
            "widgets.spotify_visualizer.overlay_frame_shell.resolve_frame_fade",
            lambda o, l: 1.0,
        )
        layer = _layer_with(_owner(), QRect(40, 30, 120, 80))
        layer.render(600, 1.0)
        assert rec.GL_SCISSOR_TEST in rec.enabled
        assert rec.GL_SCISSOR_TEST in rec.disabled, "scissor must not leak to later draws"

    def test_layer_never_clears_the_compositor_colour_buffer(self):
        """The base image and transition are already in that framebuffer."""
        source = inspect.getsource(SpotifyBarsGLOverlay.paint_layer)
        assert "clear_overlay_backbuffer" not in source
        assert "glClearColor" not in source

    def test_clear_overlay_buffer_does_no_raw_gl(self):
        method = ast.parse(
            textwrap.dedent(inspect.getsource(SpotifyBarsGLOverlay.clear_overlay_buffer))
        ).body[0]
        gl_calls = {
            n.func.attr
            for n in ast.walk(method)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and isinstance(n.func.value, ast.Name)
            and n.func.value.id == "gl"
        }
        assert gl_calls == set(), f"no raw GL outside the render pass: {gl_calls}"

    def test_visualizer_layer_is_drawn_after_base_and_transition(self):
        """Scene order: base/transition, then visualizer, then HUD overlays."""
        for fn in (
            shader_dispatch.try_shader_path,
            shader_dispatch.paint_retained_base_texture,
        ):
            source = inspect.getsource(fn)
            vis = source.index("render_visualizer_layer")
            hud = source.index("paint_qpainter_overlays_gl")
            assert vis < hud, "the PERF HUD must stay above the visualizer layer"

    def test_viewport_is_restored_after_the_layer(self):
        source = inspect.getsource(shader_dispatch.render_visualizer_layer)
        assert "_restore_full_viewport" in source


# ---------------------------------------------------------------------------
# Failure policy
# ---------------------------------------------------------------------------


class TestFailurePolicy:
    def test_invisible_or_faded_state_draws_nothing(self):
        layer = _layer_with(_owner(enabled=False), QRect(0, 0, 10, 10))
        assert layer.has_visible_state() is False
        layer2 = _layer_with(_owner(fade=0.0), QRect(0, 0, 10, 10))
        assert layer2.has_visible_state() is False

    def test_zero_sized_card_draws_nothing(self):
        layer = _layer_with(_owner(), QRect(0, 0, 0, 0))
        assert layer.has_visible_state() is False

    def test_render_failure_is_bounded_and_creates_no_cpu_visualizer(self, monkeypatch, caplog):
        import logging

        rec = _RecordingGL()
        monkeypatch.setattr("rendering.gl_compositor_pkg.visualizer_layer.gl", rec)
        monkeypatch.setattr(
            "widgets.spotify_visualizer.overlay_frame_shell.resolve_frame_fade",
            lambda o, l: 1.0,
        )
        owner = _owner()

        def _boom(rect, fade):
            raise RuntimeError("shader failed")

        owner.paint_layer = _boom
        layer = _layer_with(owner, QRect(0, 0, 100, 50))

        with caplog.at_level(logging.DEBUG):
            for _ in range(50):
                assert layer.render(600, 1.0) is False

        records = [r for r in caplog.records if "[SPOTIFY_VIS][LAYER]" in r.getMessage()]
        assert len(records) == 1, "loud once, not once per frame"
        assert records[0].levelno >= logging.ERROR

        tree = ast.parse(textwrap.dedent(inspect.getsource(CompositorVisualizerLayer)))
        referenced = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
            n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
        }
        assert "QPainter" not in referenced, "no CPU visualizer substitute"

    def test_layer_cleanup_delegates_to_the_strict_owner(self):
        cleaned: list[int] = []
        owner = _owner()
        owner.cleanup_gl = lambda: cleaned.append(1)
        layer = _layer_with(owner, QRect(0, 0, 10, 10))
        layer.cleanup()
        assert cleaned == [1]
        assert layer.state is None

    def test_compositor_teardown_cleans_the_layer(self):
        source = inspect.getsource(GLCompositorWidget.cleanup)
        assert "_visualizer_layer" in source
        assert "make_current" in source, (
            "deletion must happen with the borrowed context current"
        )

# ---------------------------------------------------------------------------
# Publications == integrations, independent of presentation rate
# ---------------------------------------------------------------------------


@pytest.mark.qt
class TestPublicationsEqualIntegrations:
    """The actual P2 correction, stated as a contract.

    Deliberately NOT `publications == paints`: presentation is now the
    compositor's display-refresh decision, so a 60 Hz display legitimately
    presents fewer times than a ~100 Hz logical source publishes. What must hold
    is that every accepted publication is integrated exactly once, whatever the
    presentation schedule does.
    """

    def _drive(self, qt_app, publications, present_every):
        from PySide6.QtGui import QColor

        overlay = SpotifyBarsGLOverlay(None)
        compositor = _RecordingPublishCompositor()
        overlay._publication_target_compositor = lambda: compositor

        presented = 0
        for i in range(publications):
            overlay.set_state(
                rect=QRect(0, 0, 320, 180),
                bars=[(i % 7) / 7.0] * 8,
                bar_count=8,
                segments=4,
                fill_color=QColor(255, 255, 255),
                border_color=QColor(255, 255, 255),
                fade=1.0,
                playing=True,
                visible=True,
                vis_mode="spectrum",
            )
            # Simulated presentation opportunities; they must not feed back.
            if present_every and i % present_every == 0:
                presented += 1
        return overlay, compositor, presented

    def test_every_publication_integrates_at_60hz_presentation(self, qt_app):
        overlay, compositor, presented = self._drive(qt_app, 100, present_every=2)
        assert overlay._perf_set_state_total == 100
        assert len(compositor.publications) == 100
        assert presented < 100, "the display presented fewer times than published"

    def test_every_publication_integrates_at_165hz_presentation(self, qt_app):
        overlay, compositor, _ = self._drive(qt_app, 100, present_every=1)
        assert overlay._perf_set_state_total == 100
        assert len(compositor.publications) == 100

    def test_integration_count_is_identical_across_presentation_schedules(self, qt_app):
        slow, slow_pub, _ = self._drive(qt_app, 60, present_every=4)
        fast, fast_pub, _ = self._drive(qt_app, 60, present_every=1)
        assert slow._perf_set_state_total == fast._perf_set_state_total == 60
        assert len(slow_pub.publications) == len(fast_pub.publications) == 60
        assert list(slow._bars) == pytest.approx(list(fast._bars)), (
            "logical state must not depend on the presentation schedule"
        )

    def test_no_presentation_at_all_still_integrates_every_publication(self, qt_app):
        overlay, compositor, _ = self._drive(qt_app, 40, present_every=0)
        assert overlay._perf_set_state_total == 40
        assert len(compositor.publications) == 40


class _RecordingPublishCompositor:
    def __init__(self) -> None:
        self.publications: list[tuple] = []
        self.cleared = 0

    def publish_visualizer_state(self, owner, card_rect, **kwargs):
        self.publications.append((card_rect, kwargs))

    def clear_visualizer_state(self):
        self.cleared += 1


# ---------------------------------------------------------------------------
# Card visual ownership
# ---------------------------------------------------------------------------


class TestCardVisualOwnership:
    def test_card_stops_painting_when_the_compositor_owns_it(self):
        """Otherwise the card QWidget sibling paints over the bars beneath it."""
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

        source = inspect.getsource(SpotifyVisualizerWidget.paintEvent)
        assert "_compositor_owns_card_visual" in source
        tree = ast.parse(textwrap.dedent(source)).body[0]
        first = tree.body[0] if not isinstance(tree.body[0], ast.Expr) else tree.body[1]
        assert isinstance(first, ast.If), (
            "the compositor-ownership check must gate painting, not follow it"
        )

    def test_card_visual_is_drawn_before_the_shader_layer(self):
        source = inspect.getsource(CompositorVisualizerLayer.render)
        card = source.index("_render_card_visual")
        shader = source.index("paint_layer")
        assert card < shader, "the card must be beneath the bars"

    def test_card_ownership_is_released_when_the_layer_clears(self):
        for name in ("clear", "cleanup"):
            source = inspect.getsource(getattr(CompositorVisualizerLayer, name))
            assert "_release_card_visual" in source, (
                f"{name} must hand the card visual back"
            )

    def test_card_layer_reuses_the_existing_cached_pixmap(self):
        """Authored border/radius/shadow must not be reimplemented in GL."""
        source = inspect.getsource(CompositorVisualizerLayer._render_card_visual)
        assert "ensure_painted_frame_shadow_pixmap" in source

    def test_card_keeps_geometry_and_interaction_ownership(self):
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

        for retained in ("setGeometry", "geometry", "show", "hide"):
            assert hasattr(SpotifyVisualizerWidget, retained)

