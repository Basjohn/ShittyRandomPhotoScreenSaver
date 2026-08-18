"""Real-GL acceptance for the single-surface visualizer layer.

The first single-surface landing shipped a visually broken build: the shader was
confined to a narrow hard-edged region while the painted card occupied a much
larger rect. The coordinate tests did not catch it because they mocked
glViewport/glScissor and replaced paint_layer with a lambda, so they proved only
that Python computed a viewport tuple. They never exercised the actual fragment
coordinate mapping.

`gl_FragCoord` is framebuffer/window space, not viewport space. Setting a
viewport at a non-zero origin does NOT make it card-local, so every visualizer
mode's `gl_FragCoord`-derived coordinates were offset by the card origin.

These bars render the real compositor visualizer layer into a real whole-display
target and inspect pixels. They are the bars that would have failed on the
screenshot.
"""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QColor, QImage, QSurfaceFormat

gl = pytest.importorskip("OpenGL.GL")

from PySide6.QtGui import QOffscreenSurface, QOpenGLContext  # noqa: E402

from rendering.gl_compositor_pkg.visualizer_layer import (  # noqa: E402
    CompositorVisualizerLayer,
    PresentationGeometry,
    VisualizerRenderState,
)
from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay  # noqa: E402

SURFACE = QSize(800, 600)
CARD = QRect(300, 120, 400, 200)
ALL_MODES = ("bubble", "spectrum", "sine_wave", "oscilloscope", "devcurve")

# Modes whose authored output can be produced from a synthetic published state.
#
# Bubble is deliberately absent. Its renderer returns before uniform dispatch
# unless real runtime state is present, so a synthetic state yields an empty
# card - verified to behave identically at origin (0,0), i.e. under the OLD
# card-sized geometry, so it is a fixture limitation and not a coordinate
# regression. Weakening Bubble to make it draw here would change authored
# behaviour, which is forbidden. Bubble is instead covered by the shared-origin
# equivalence bar below plus the operator visual sanity run.
PIXEL_MODES = ("spectrum", "sine_wave", "oscilloscope", "devcurve")


# ---------------------------------------------------------------------------
# Real offscreen GL target
# ---------------------------------------------------------------------------


class _GLTarget:
    """An FBO standing in for the compositor's whole-display framebuffer."""

    def __init__(self, size: QSize):
        self.size = size
        self.fbo = int(gl.glGenFramebuffers(1))
        self.color = int(gl.glGenTextures(1))
        gl.glBindTexture(gl.GL_TEXTURE_2D, self.color)
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D, 0, gl.GL_RGBA8, size.width(), size.height(),
            0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, None,
        )
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)

        self.depth_stencil = int(gl.glGenRenderbuffers(1))
        gl.glBindRenderbuffer(gl.GL_RENDERBUFFER, self.depth_stencil)
        gl.glRenderbufferStorage(
            gl.GL_RENDERBUFFER, gl.GL_DEPTH24_STENCIL8, size.width(), size.height()
        )

        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        gl.glFramebufferTexture2D(
            gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0, gl.GL_TEXTURE_2D, self.color, 0
        )
        gl.glFramebufferRenderbuffer(
            gl.GL_FRAMEBUFFER, gl.GL_DEPTH_STENCIL_ATTACHMENT,
            gl.GL_RENDERBUFFER, self.depth_stencil,
        )
        status = gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
        if status != gl.GL_FRAMEBUFFER_COMPLETE:
            raise RuntimeError(f"incomplete FBO: {status}")

    def clear(self, rgba=(0.0, 0.0, 0.0, 1.0)):
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        gl.glViewport(0, 0, self.size.width(), self.size.height())
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glClearColor(*rgba)
        gl.glClearStencil(0)
        gl.glClear(
            gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT | gl.GL_STENCIL_BUFFER_BIT
        )

    def read(self) -> np.ndarray:
        """Return HxWx4 uint8 with row 0 at the TOP (Qt convention)."""
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        gl.glPixelStorei(gl.GL_PACK_ALIGNMENT, 1)
        raw = gl.glReadPixels(
            0, 0, self.size.width(), self.size.height(), gl.GL_RGBA, gl.GL_UNSIGNED_BYTE
        )
        arr = np.frombuffer(raw, dtype=np.uint8).reshape(
            self.size.height(), self.size.width(), 4
        )
        return np.flipud(arr).copy()

    def destroy(self):
        gl.glDeleteFramebuffers(1, [self.fbo])
        gl.glDeleteTextures(1, [self.color])
        gl.glDeleteRenderbuffers(1, [self.depth_stencil])


@pytest.fixture(scope="module")
def gl_context():
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
    fmt.setDepthBufferSize(24)
    fmt.setStencilBufferSize(8)

    surface = QOffscreenSurface()
    surface.setFormat(fmt)
    surface.create()
    if not surface.isValid():
        pytest.skip("offscreen surface unavailable")

    ctx = QOpenGLContext()
    ctx.setFormat(fmt)
    if not ctx.create() or not ctx.makeCurrent(surface):
        pytest.skip("GL context unavailable")
    yield ctx
    ctx.doneCurrent()
    surface.destroy()


class _FakeCompositor:
    """Compositor stand-in: owns the borrowed context, never a card painter."""

    def __init__(self, ctx):
        self._rhi_gl = type(
            "_Borrowed", (), {
                "context": ctx, "generation": 1,
                "is_attached": staticmethod(lambda: True),
                "make_current": staticmethod(lambda: True),
            },
        )()

    # No gl_target_painter: the card visual is covered separately so these bars
    # isolate the shader's own coordinate mapping.


def _bubble_payload():
    """Bubbles spread across the full card width, both halves populated.

    Bubble renders nothing from `bars` alone, so a bars-only state would make
    every Bubble bar vacuous. Positions are normalised card-local coordinates.
    """
    count = 8
    pos: list[float] = []
    extra: list[float] = []
    trail: list[float] = []
    for i in range(count):
        x = 0.06 + (i / (count - 1)) * 0.88  # spans left and right halves
        y = 0.5
        radius = 0.16
        # Flat float buffers: vec4 pos, vec4 extra, 3 x vec3 trail per bubble.
        pos.extend((x, y, radius, 1.0))
        extra.extend((1.0, 0.0, 0.0, 0.0))
        for _ in range(3):
            trail.extend((x, y, 1.0))
    return count, pos, extra, trail


def _overlay_for(mode: str) -> SpotifyBarsGLOverlay:
    """A visualizer carrying deterministic state that lights the whole card."""
    overlay = SpotifyBarsGLOverlay(None)
    bars = [0.85] * 16
    kwargs = {}
    if mode == "bubble":
        count, pos, extra, trail = _bubble_payload()
        kwargs = dict(
            bubble_count=count,
            bubble_pos_data=pos,
            bubble_extra_data=extra,
            bubble_trail_data=trail,
        )
    overlay.set_state(
        rect=QRect(0, 0, CARD.width(), CARD.height()),
        bars=bars,
        bar_count=len(bars),
        segments=4,
        fill_color=QColor(255, 255, 255),
        border_color=QColor(255, 255, 255),
        fade=1.0,
        playing=True,
        visible=True,
        vis_mode=mode,
        **kwargs,
    )
    # Painted-card stencil clipping is exercised in its own bar; these isolate
    # the fragment coordinate mapping.
    overlay._painted_frame_shadow_enabled = False
    return overlay


def _render(ctx, overlay, *, card=CARD, dpr=1.0, surface=SURFACE):
    target = _GLTarget(surface)
    try:
        target.clear()
        layer = CompositorVisualizerLayer(_FakeCompositor(ctx))
        layer.publish(VisualizerRenderState(overlay, card))
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
        drew = layer.render(surface.height(), dpr)
        pixels = target.read()
        return drew, pixels
    finally:
        try:
            overlay.cleanup_gl()
        except Exception:
            pass
        target.destroy()


def _card_slice(pixels, card=CARD, dpr=1.0):
    x0, y0 = int(card.x() * dpr), int(card.y() * dpr)
    return pixels[y0:y0 + int(card.height() * dpr), x0:x0 + int(card.width() * dpr)]


def _lit(region) -> np.ndarray:
    """Boolean mask of pixels that differ from the cleared background."""
    return region[..., :3].max(axis=-1) > 8


# ---------------------------------------------------------------------------
# The bars that would have failed on the screenshot
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", PIXEL_MODES)
def test_mode_draws_across_the_full_card_width_at_non_zero_offset(gl_context, qapp, mode):
    """The reported defect: output confined to a narrow region, right side clipped."""
    overlay = _overlay_for(mode)
    drew, pixels = _render(gl_context, overlay)
    if not drew:
        pytest.skip(f"{mode} shader unavailable in this environment")

    card = _card_slice(pixels)
    lit = _lit(card)
    assert lit.any(), (
        f"{mode} drew nothing inside the card. A blackout is a failure, not an "
        f"environment skip: it is exactly what a wrong fragment origin produces "
        f"when the content lands outside the scissor."
    )

    columns = np.flatnonzero(lit.any(axis=0))
    width = card.shape[1]
    coverage = (columns.max() - columns.min() + 1) / width

    assert coverage > 0.6, (
        f"{mode}: output spans only {coverage:.0%} of the card width - the shader "
        f"is confined to a narrow region, which is the reported defect"
    )
    # The specific screenshot symptom: everything crammed left, right side dead.
    assert lit[:, width // 2:].any(), (
        f"{mode}: the right-hand half of the card is empty at x offset "
        f"{CARD.x()}; gl_FragCoord is still being read as window space"
    )


@pytest.mark.parametrize("mode", PIXEL_MODES)
def test_mode_output_never_escapes_the_card(gl_context, qapp, mode):
    overlay = _overlay_for(mode)
    drew, pixels = _render(gl_context, overlay)
    if not drew:
        pytest.skip(f"{mode} shader unavailable in this environment")

    outside = _lit(pixels).copy()
    outside[CARD.y():CARD.y() + CARD.height(), CARD.x():CARD.x() + CARD.width()] = False
    assert not outside.any(), (
        f"{mode}: drew {int(outside.sum())} pixels outside the card; scissor "
        f"must bound every write the layer makes"
    )


def test_non_zero_y_offset_is_correct(gl_context, qapp):
    """A vertical offset must not shift content within the card."""
    overlay_a = _overlay_for("spectrum")
    drew_a, pixels_a = _render(gl_context, overlay_a, card=QRect(300, 0, 400, 200))
    overlay_b = _overlay_for("spectrum")
    drew_b, pixels_b = _render(gl_context, overlay_b, card=QRect(300, 250, 400, 200))
    if not (drew_a and drew_b):
        pytest.skip("spectrum shader unavailable in this environment")

    a = _lit(_card_slice(pixels_a, QRect(300, 0, 400, 200)))
    b = _lit(_card_slice(pixels_b, QRect(300, 250, 400, 200)))
    assert a.any() and b.any(), "a blackout at either Y offset is a failure"

    rows_a = np.flatnonzero(a.any(axis=1))
    rows_b = np.flatnonzero(b.any(axis=1))
    assert abs(int(rows_a.min()) - int(rows_b.min())) <= 2, (
        "card-local Y content moved when the card moved; the Y origin is wrong"
    )
    assert abs(int(rows_a.max()) - int(rows_b.max())) <= 2


def test_content_is_identical_at_zero_and_non_zero_origin(gl_context, qapp):
    """Card-local output must not depend on where the card sits."""
    at_origin = _overlay_for("spectrum")
    drew_o, pixels_o = _render(gl_context, at_origin, card=QRect(0, 0, 400, 200))
    offset = _overlay_for("spectrum")
    drew_x, pixels_x = _render(gl_context, offset, card=QRect(300, 120, 400, 200))
    if not (drew_o and drew_x):
        pytest.skip("spectrum shader unavailable in this environment")

    a = _lit(_card_slice(pixels_o, QRect(0, 0, 400, 200)))
    b = _lit(_card_slice(pixels_x, QRect(300, 120, 400, 200)))
    assert a.any(), "origin-zero render drew nothing"
    assert b.any(), "offset render drew nothing; content fell outside the scissor"

    agreement = float((a == b).mean())
    assert agreement > 0.97, (
        f"card-local output differs by {(1 - agreement):.1%} between origin (0,0) "
        f"and (300,120); the shader still depends on window-space coordinates"
    )


def test_mixed_dpr_uses_the_compositor_dpr_only(gl_context, qapp):
    """Compositor DPR is the sole presentation DPR authority."""
    overlay = _overlay_for("spectrum")
    # The hidden logical widget reports DPR 1; the compositor presents at 1.5.
    overlay._get_dpr = lambda: 1.0
    surface = QSize(1200, 900)
    drew, pixels = _render(
        gl_context, overlay, card=QRect(200, 100, 400, 200), dpr=1.5, surface=surface
    )
    if not drew:
        pytest.skip("spectrum shader unavailable in this environment")

    card = _lit(_card_slice(pixels, QRect(200, 100, 400, 200), dpr=1.5))
    assert card.any(), "blackout at DPR 1.5"

    columns = np.flatnonzero(card.any(axis=0))
    coverage = (columns.max() - columns.min() + 1) / card.shape[1]
    assert coverage > 0.6, (
        f"at DPR 1.5 output spans only {coverage:.0%} of the card; the shader is "
        f"consuming a different DPR than the viewport"
    )


def test_stale_live_widget_geometry_cannot_change_presentation(gl_context, qapp):
    """The screenshot shape: card sized from a different rect than the bars.

    The published rect is authoritative. A stale live QWidget geometry must not
    reach presentation geometry.
    """
    overlay = _overlay_for("spectrum")
    # Live widget geometry deliberately disagrees with the published rect.
    overlay.setGeometry(QRect(0, 0, 120, 60))

    authoritative = QRect(300, 120, 400, 200)
    drew, pixels = _render(gl_context, overlay, card=authoritative)
    if not drew:
        pytest.skip("spectrum shader unavailable in this environment")

    lit = _lit(pixels)
    assert lit.any(), "blackout with a stale live geometry present"

    rows = np.flatnonzero(lit.any(axis=1))
    cols = np.flatnonzero(lit.any(axis=0))
    assert cols.min() >= authoritative.x() - 1
    assert cols.max() <= authoritative.x() + authoritative.width() + 1
    assert rows.min() >= authoritative.y() - 1
    assert rows.max() <= authoritative.y() + authoritative.height() + 1

    width_span = cols.max() - cols.min() + 1
    assert width_span > authoritative.width() * 0.6, (
        f"output spans only {width_span}px of a {authoritative.width()}px card; "
        f"the stale 120px live geometry leaked into presentation"
    )


def test_presentation_geometry_is_one_derivation(gl_context, qapp):
    """Origin, size, viewport and local rect all come from one value."""
    geom = PresentationGeometry(QRect(300, 120, 400, 200), 1.5, 900)
    assert geom.framebuffer_origin_px == (450, 900 - 180 - 300)
    assert geom.framebuffer_size_px == (600, 300)
    assert geom.viewport == (450, 420, 600, 300)
    assert geom.local_rect() == QRect(0, 0, 400, 200)
    assert geom.dpr == 1.5


def test_layer_restores_compositor_gl_state(gl_context, qapp):
    """A leaked scissor/stencil/colour mask would corrupt the next frame."""
    overlay = _overlay_for("spectrum")
    target = _GLTarget(SURFACE)
    try:
        target.clear()
        layer = CompositorVisualizerLayer(_FakeCompositor(gl_context))
        layer.publish(VisualizerRenderState(overlay, CARD))
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
        if not layer.render(SURFACE.height(), 1.0):
            pytest.skip("spectrum shader unavailable in this environment")

        assert not gl.glIsEnabled(gl.GL_SCISSOR_TEST), "scissor leaked"
        assert not gl.glIsEnabled(gl.GL_STENCIL_TEST), "stencil test leaked"
        assert not gl.glIsEnabled(gl.GL_BLEND), "blend leaked"
        assert list(gl.glGetBooleanv(gl.GL_COLOR_WRITEMASK)) == [1, 1, 1, 1]
        assert int(gl.glGetIntegerv(gl.GL_CURRENT_PROGRAM)) == 0
        assert int(gl.glGetIntegerv(gl.GL_VERTEX_ARRAY_BINDING)) == 0
    finally:
        try:
            overlay.cleanup_gl()
        except Exception:
            pass
        target.destroy()


def test_stencil_masked_card_clips_to_rounded_bounds(gl_context, qapp):
    """With the painted card mask on, corners must be clipped, centre kept."""
    overlay = _overlay_for("spectrum")
    overlay._painted_frame_shadow_enabled = True
    drew, pixels = _render(gl_context, overlay)
    if not drew:
        pytest.skip("spectrum shader unavailable in this environment")

    card = _lit(_card_slice(pixels))
    assert card.any(), "the stencil mask clipped the entire card away"

    h, w = card.shape
    corner = 6
    assert not card[:corner, :corner].any(), "top-left corner not clipped by the mask"
    assert not card[:corner, -corner:].any(), "top-right corner not clipped"
    assert card[h // 3:2 * h // 3, w // 3:2 * w // 3].any(), (
        "the card interior was clipped away entirely"
    )

# ---------------------------------------------------------------------------
# Bubble: shared-origin equivalence
# ---------------------------------------------------------------------------


class TestSharedFragmentOriginContract:
    """One origin contract, identical in every mode - including Bubble.

    Bubble cannot be lit-pixel verified from a synthetic state (see PIXEL_MODES),
    so the contract it shares with the pixel-verified modes is asserted directly.
    Five independently invented fixes was the explicit failure mode to avoid.
    """

    def _shader_source(self, mode: str) -> str:
        from widgets.spotify_visualizer.shaders import load_fragment_shader

        source = load_fragment_shader(mode)
        assert source, f"{mode} fragment shader did not load"
        return source

    @pytest.mark.parametrize("mode", ALL_MODES)
    def test_mode_declares_the_shared_origin_uniform(self, mode):
        source = self._shader_source(mode)
        assert "uniform vec2 u_viewport_origin_px;" in source, (
            f"{mode} does not participate in the shared presentation-origin contract"
        )

    @pytest.mark.parametrize("mode", ALL_MODES)
    def test_mode_subtracts_the_origin_from_gl_fragcoord(self, mode):
        source = self._shader_source(mode)
        assert "gl_FragCoord.xy - u_viewport_origin_px" in source, (
            f"{mode} still reads gl_FragCoord as if it were card-local"
        )

    @pytest.mark.parametrize("mode", ALL_MODES)
    def test_mode_has_no_unadjusted_fragcoord_coordinate_derivation(self, mode):
        """Any other gl_FragCoord use must not rebuild card-local coordinates."""
        source = self._shader_source(mode)
        uses = [
            line.strip()
            for line in source.splitlines()
            if "gl_FragCoord" in line and not line.strip().startswith("//")
        ]
        for line in uses:
            assert "u_viewport_origin_px" in line or "localFrag" in line, (
                f"{mode}: unadjusted gl_FragCoord use: {line}"
            )

    def test_bubble_output_is_origin_independent(self, gl_context, qapp):
        """Whatever Bubble draws must not depend on where the card sits."""
        at_origin = _overlay_for("bubble")
        _d0, pixels_o = _render(
            gl_context, at_origin, card=QRect(0, 0, 400, 200), surface=QSize(800, 600)
        )
        offset = _overlay_for("bubble")
        _d1, pixels_x = _render(gl_context, offset, card=CARD, surface=QSize(800, 600))

        a = _card_slice(pixels_o, QRect(0, 0, 400, 200))[..., :3]
        b = _card_slice(pixels_x, CARD)[..., :3]
        assert a.shape == b.shape
        assert np.array_equal(a, b), (
            "Bubble card-local output changed when the card moved; its fragment "
            "origin is not card-local"
        )


# ---------------------------------------------------------------------------
# Card visual: cached GL texture, not a per-frame QPainter bridge
# ---------------------------------------------------------------------------


class _CardStub:
    """Minimal stand-in for the visualizer card's authored visual state."""

    def __init__(self, *, width=400, height=200):
        self._show_background = True
        self._bg_color = QColor(20, 30, 40)
        self._bg_opacity = 0.9
        self._card_border_color = QColor(255, 255, 255, 255)
        self._border_width = 2
        self._painted_frame_shadow_enabled = True
        self._painted_frame_shadow_pixmap = None
        self._painted_frame_shadow_cache_key = None
        self._w = width
        self._h = height
        self.owned = None

    def uses_painted_frame_shadow(self):
        return bool(self._painted_frame_shadow_enabled and self._show_background)

    def width(self):
        return self._w

    def height(self):
        return self._h

    def devicePixelRatioF(self):
        return 1.0

    def set_compositor_owns_card_visual(self, owned):
        self.owned = owned


def _layer_with_card(ctx, card, overlay, card_rect=CARD):
    from types import SimpleNamespace

    comp = _FakeCompositor(ctx)
    layer = CompositorVisualizerLayer(comp)
    overlay.parentWidget = lambda: SimpleNamespace(spotify_visualizer_widget=card)
    layer.publish(VisualizerRenderState(overlay, card_rect))
    return layer


class TestCardTextureUploadContract:
    def test_unchanged_card_uploads_once_across_many_paints(self, gl_context, qapp):
        """Ordinary visualizer publications must not re-upload the card."""
        card = _CardStub()
        overlay = _overlay_for("spectrum")
        layer = _layer_with_card(gl_context, card, overlay)
        target = _GLTarget(SURFACE)
        try:
            uploads = {"n": 0}
            original = layer._card_texture.ensure_uploaded

            def counting(pixmap, revision):
                if layer._card_texture.revision != revision:
                    uploads["n"] += 1
                return original(pixmap, revision)

            layer._card_texture.ensure_uploaded = counting

            target.clear()
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
            for _ in range(30):
                layer.render(SURFACE.height(), 1.0)

            assert uploads["n"] == 1, (
                "card uploaded %d times for an unchanged card" % uploads["n"]
            )
            assert layer._card_texture.has_texture()
        finally:
            try:
                layer._card_texture.cleanup()
                overlay.cleanup_gl()
            except Exception:
                pass
            target.destroy()

    def test_geometry_change_triggers_a_replacement_upload(self, gl_context, qapp):
        card = _CardStub()
        overlay = _overlay_for("spectrum")
        layer = _layer_with_card(gl_context, card, overlay)
        target = _GLTarget(SURFACE)
        try:
            target.clear()
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
            for _ in range(5):
                layer.render(SURFACE.height(), 1.0)
            first = layer._card_texture.revision

            layer.publish(VisualizerRenderState(overlay, QRect(300, 120, 360, 180)))
            for _ in range(5):
                layer.render(SURFACE.height(), 1.0)
            second = layer._card_texture.revision

            assert first is not None and second is not None
            assert first != second, "a geometry change must replace the texture"
        finally:
            try:
                layer._card_texture.cleanup()
                overlay.cleanup_gl()
            except Exception:
                pass
            target.destroy()

    def test_dpr_change_triggers_a_replacement_upload(self, gl_context, qapp):
        card = _CardStub()
        overlay = _overlay_for("spectrum")
        layer = _layer_with_card(gl_context, card, overlay)
        target = _GLTarget(QSize(1200, 900))
        try:
            target.clear()
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
            layer.render(900, 1.0)
            first = layer._card_texture.revision
            layer.render(900, 1.5)
            second = layer._card_texture.revision
            assert first != second, "DPR is part of the card revision"
        finally:
            try:
                layer._card_texture.cleanup()
                overlay.cleanup_gl()
            except Exception:
                pass
            target.destroy()

    def test_style_change_triggers_a_replacement_upload(self, gl_context, qapp):
        card = _CardStub()
        overlay = _overlay_for("spectrum")
        layer = _layer_with_card(gl_context, card, overlay)
        target = _GLTarget(SURFACE)
        try:
            target.clear()
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
            layer.render(SURFACE.height(), 1.0)
            first = layer._card_texture.revision

            card._border_width = 6
            card._bg_color = QColor(90, 10, 10)
            layer.render(SURFACE.height(), 1.0)
            assert layer._card_texture.revision != first
        finally:
            try:
                layer._card_texture.cleanup()
                overlay.cleanup_gl()
            except Exception:
                pass
            target.destroy()

    def test_fade_does_not_re_upload_the_texture(self, gl_context, qapp):
        """Fade is a GL alpha multiplier, not a texture property."""
        card = _CardStub()
        overlay = _overlay_for("spectrum")
        layer = _layer_with_card(gl_context, card, overlay)
        target = _GLTarget(SURFACE)
        try:
            target.clear()
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
            layer.render(SURFACE.height(), 1.0)
            revision = layer._card_texture.revision
            for fade in (0.1, 0.4, 0.75, 1.0):
                overlay._fade = fade
                layer.render(SURFACE.height(), 1.0)
            assert layer._card_texture.revision == revision, (
                "a fade animation must not re-upload the card texture"
            )
        finally:
            try:
                layer._card_texture.cleanup()
                overlay.cleanup_gl()
            except Exception:
                pass
            target.destroy()

    def test_card_texture_is_deleted_once_at_teardown(self, gl_context, qapp):
        card = _CardStub()
        overlay = _overlay_for("spectrum")
        layer = _layer_with_card(gl_context, card, overlay)
        target = _GLTarget(SURFACE)
        try:
            target.clear()
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
            layer.render(SURFACE.height(), 1.0)
            assert layer._card_texture.has_texture()

            layer._card_texture.cleanup()
            assert not layer._card_texture.has_texture()
            layer._card_texture.cleanup()
        finally:
            try:
                overlay.cleanup_gl()
            except Exception:
                pass
            target.destroy()


class TestCardTexturePixelsMatchTheAuthoredPixmap:
    def test_drawn_card_matches_the_authored_qpixmap(self, gl_context, qapp):
        """The GL path must reproduce the authored QPainter output."""
        from widgets.spotify_visualizer.card_paint import (
            ensure_painted_frame_shadow_pixmap,
        )

        card = _CardStub()
        overlay = _overlay_for("spectrum")
        layer = _layer_with_card(gl_context, card, overlay)
        target = _GLTarget(SURFACE)
        try:
            target.clear(rgba=(0.0, 0.0, 0.0, 1.0))
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
            geometry = PresentationGeometry(CARD, 1.0, SURFACE.height())
            gl.glViewport(*geometry.viewport)
            gl.glEnable(gl.GL_BLEND)
            gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
            layer._render_card_visual(geometry, 1.0)
            gl.glDisable(gl.GL_BLEND)
            pixels = target.read()

            reference = ensure_painted_frame_shadow_pixmap(
                card, logical_size=CARD.size(), dpr=1.0
            ).toImage().convertToFormat(QImage.Format.Format_RGBA8888)

            drawn = _card_slice(pixels)
            h, w = drawn.shape[0], drawn.shape[1]
            mismatches = 0
            samples = 0
            for y in range(h // 4, 3 * h // 4, max(1, h // 12)):
                for x in range(w // 4, 3 * w // 4, max(1, w // 12)):
                    samples += 1
                    ref = reference.pixelColor(x, y)
                    got = drawn[y, x]
                    a = ref.alpha() / 255.0
                    expected = [
                        int(round(ref.red() * a)),
                        int(round(ref.green() * a)),
                        int(round(ref.blue() * a)),
                    ]
                    if max(abs(int(got[i]) - expected[i]) for i in range(3)) > 6:
                        mismatches += 1
            assert samples > 0
            assert mismatches == 0, (
                "%d/%d card interior samples differ from the authored QPixmap"
                % (mismatches, samples)
            )
        finally:
            try:
                layer._card_texture.cleanup()
                overlay.cleanup_gl()
            except Exception:
                pass
            target.destroy()


class TestNoPerFrameQPainterBridge:
    def test_layer_never_opens_a_painter_in_steady_render(self):
        import ast
        import inspect
        import textwrap

        source = inspect.getsource(CompositorVisualizerLayer)
        tree = ast.parse(textwrap.dedent(source))
        called = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        } | {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        for forbidden in ("gl_target_painter", "QPainter", "QOpenGLPaintDevice"):
            assert forbidden not in called, (
                "steady visualizer render must not construct %s" % forbidden
            )


# ---------------------------------------------------------------------------
# INTEGRATED layer bounds with the card visual ENABLED
# ---------------------------------------------------------------------------
#
# The existing mode bars set `_painted_frame_shadow_enabled = False`, so they
# bypass the card-texture draw entirely. That is why they kept passing while the
# installed build painted the card across almost the whole display: the bubbles
# were correctly bounded, the card was not.
#
# These bars render the REAL layer with the card enabled and assert the whole
# framebuffer, not just the card interior.


def _distinct_background(target):
    """Fill the target with a pattern nothing in the card region produces."""
    gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
    gl.glViewport(0, 0, target.size.width(), target.size.height())
    gl.glDisable(gl.GL_SCISSOR_TEST)
    gl.glClearColor(0.0, 1.0, 0.0, 1.0)  # pure green
    gl.glClearStencil(0)
    gl.glClear(
        gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT | gl.GL_STENCIL_BUFFER_BIT
    )


def _render_with_card(ctx, overlay, card, *, card_rect, dpr, surface):
    from types import SimpleNamespace

    target = _GLTarget(surface)
    try:
        _distinct_background(target)
        comp = _FakeCompositor(ctx)
        layer = CompositorVisualizerLayer(comp)
        overlay.parentWidget = lambda: SimpleNamespace(spotify_visualizer_widget=card)
        layer.publish(VisualizerRenderState(overlay, card_rect))
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
        drew = layer.render(surface.height(), dpr)
        pixels = target.read()
        return drew, pixels, layer
    finally:
        target.destroy()


def _outside_card_mask(pixels, card_rect, dpr):
    x0 = int(round(card_rect.x() * dpr))
    y0 = int(round(card_rect.y() * dpr))
    w = int(round(card_rect.width() * dpr))
    h = int(round(card_rect.height() * dpr))
    mask = np.ones(pixels.shape[:2], dtype=bool)
    mask[y0:y0 + h, x0:x0 + w] = False
    return mask


class TestIntegratedLayerBoundsWithCardEnabled:
    """The regression the installed screenshot showed."""

    def _case(self, gl_context, *, card_rect, dpr, surface):
        overlay = _overlay_for("spectrum")
        overlay._painted_frame_shadow_enabled = True  # deliberately ENABLED
        card = _CardStub(width=card_rect.width(), height=card_rect.height())
        drew, pixels, layer = _render_with_card(
            gl_context, overlay, card,
            card_rect=card_rect, dpr=dpr, surface=surface,
        )
        try:
            assert drew, "the layer must draw with the card enabled"
        finally:
            try:
                layer._card_texture.cleanup()
                overlay.cleanup_gl()
            except Exception:
                pass
        return pixels

    def test_card_does_not_stain_the_whole_display(self, gl_context, qapp):
        pixels = self._case(
            gl_context, card_rect=CARD, dpr=1.0, surface=SURFACE
        )
        outside = _outside_card_mask(pixels, CARD, 1.0)
        rgb = pixels[..., :3]

        # Outside the card the deliberately distinct green background must be
        # exactly intact. A full-NDC card quad drawn under the previous owner's
        # whole-display viewport is what covered the entire framebuffer.
        outside_pixels = rgb[outside]
        stained = np.any(outside_pixels != np.array([0, 255, 0], dtype=np.uint8), axis=-1)
        assert not stained.any(), (
            f"{int(stained.sum())} pixels outside the card were modified; the "
            f"card texture escaped its viewport/scissor region"
        )

    def test_card_pixels_appear_inside_the_card_rect(self, gl_context, qapp):
        pixels = self._case(
            gl_context, card_rect=CARD, dpr=1.0, surface=SURFACE
        )
        card_region = _card_slice(pixels, CARD, 1.0)[..., :3]
        # The card interior must no longer be the background colour.
        differs = np.any(
            card_region != np.array([0, 255, 0], dtype=np.uint8), axis=-1
        )
        assert differs.any(), "no card/visualizer pixels were drawn in the card rect"
        assert differs.mean() > 0.5, (
            "the card should cover most of its own rect"
        )

    def test_non_zero_offset_and_dpr_stay_bounded(self, gl_context, qapp):
        surface = QSize(1200, 900)
        rect = QRect(200, 100, 400, 200)
        pixels = self._case(gl_context, card_rect=rect, dpr=1.5, surface=surface)
        outside = _outside_card_mask(pixels, rect, 1.5)
        rgb = pixels[..., :3]
        stained = np.any(
            rgb[outside] != np.array([0, 255, 0], dtype=np.uint8), axis=-1
        )
        assert not stained.any(), (
            f"{int(stained.sum())} pixels outside the card were modified at DPR 1.5"
        )

    def test_custom_non_square_geometry_stays_bounded(self, gl_context, qapp):
        """The installed CUSTOM card was 958x638 logical at DPR 1.5."""
        surface = QSize(1600, 1100)
        rect = QRect(120, 90, 958, 638)
        pixels = self._case(gl_context, card_rect=rect, dpr=1.5, surface=surface)
        outside = _outside_card_mask(pixels, rect, 1.5)
        rgb = pixels[..., :3]
        stained = np.any(
            rgb[outside] != np.array([0, 255, 0], dtype=np.uint8), axis=-1
        )
        assert not stained.any(), (
            f"{int(stained.sum())} pixels outside a 958x638 CUSTOM card were modified"
        )

    def test_transparent_card_pixels_composite_over_the_background(self, gl_context, qapp):
        """Shadow/transparent card pixels must blend, not replace."""
        pixels = self._case(
            gl_context, card_rect=CARD, dpr=1.0, surface=SURFACE
        )
        card_region = _card_slice(pixels, CARD, 1.0)[..., :3].astype(int)
        # The card's outermost ring is shadow/transparent, so the green
        # background must still show through there rather than being replaced
        # by opaque black.
        edge = np.concatenate([
            card_region[0, :, :], card_region[-1, :, :],
            card_region[:, 0, :], card_region[:, -1, :],
        ])
        assert edge[:, 1].max() > 40, (
            "the card edge fully replaced the background instead of "
            "alpha-compositing over it"
        )

    def test_card_and_shader_share_one_state_boundary(self):
        """Ordering bar: the state boundary must dominate BOTH draws."""
        import inspect

        source = inspect.getsource(CompositorVisualizerLayer.render)
        viewport = source.index("glViewport(x_px, y_px, w_px, h_px)")
        scissor = source.index("glScissor(x_px, y_px, w_px, h_px)")
        blend = source.index("glBlendFunc(")
        card = source.index("_render_card_visual(")
        shader = source.index("paint_layer(")

        assert viewport < card, (
            "the card texture is a full-NDC quad; drawing it before the card "
            "viewport covers the whole display"
        )
        assert scissor < card, "scissor must bound the card draw"
        assert blend < card, (
            "the card carries transparent shadow pixels and must be drawn with "
            "the layer's alpha blending active"
        )
        assert card < shader, "the card belongs beneath the bars"


# ---------------------------------------------------------------------------
# Lifecycle: the card texture must not leak when hidden at teardown
# ---------------------------------------------------------------------------


class TestCardTextureLifecycleAcrossVisibility:
    """The installed leak: gl_texture_bytes=5500836 survived to exit.

    1437 * 957 * 4 == 5,500,836, i.e. a 958x638 logical card at DPR 1.5 - the
    card texture exactly. cleanup() returned early when no state was published,
    so a hidden/cleared visualizer at teardown never freed it.
    """

    def _prepared(self, ctx):
        from types import SimpleNamespace

        overlay = _overlay_for("spectrum")
        overlay._painted_frame_shadow_enabled = True
        card = _CardStub()
        comp = _FakeCompositor(ctx)
        layer = CompositorVisualizerLayer(comp)
        # The parent exposes both the card widget and the compositor, so the
        # visualizer's own strict cleanup can reach the borrowed context just
        # as it does in production.
        overlay.parentWidget = lambda: SimpleNamespace(
            spotify_visualizer_widget=card, _gl_compositor=comp
        )
        layer.publish(VisualizerRenderState(overlay, CARD))
        target = _GLTarget(SURFACE)
        target.clear()
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
        layer.render(SURFACE.height(), 1.0)
        return overlay, layer, target

    def _assert_fully_released(self, layer):
        tex = layer._card_texture
        assert tex.texture_id == 0, "card texture leaked"
        assert tex._program == 0, "card program leaked"
        assert tex._vao == 0, "card VAO leaked"
        assert tex._vbo == 0, "card VBO leaked"
        assert tex.tracked_bytes == 0, "card GL bytes did not return to baseline"
        assert tex._resource_id is None, "ResourceManager tracking not released"

    def test_visible_then_cleanup_releases_everything(self, gl_context, qapp):
        overlay, layer, target = self._prepared(gl_context)
        try:
            assert layer._card_texture.has_texture()
            layer.cleanup()
            self._assert_fully_released(layer)
        finally:
            target.destroy()

    def test_hidden_then_cleanup_still_releases_everything(self, gl_context, qapp):
        """THE regression: cleared presentation state at teardown."""
        overlay, layer, target = self._prepared(gl_context)
        try:
            assert layer._card_texture.has_texture()
            layer.clear()
            assert layer.state is None, "presentation state must be cleared"

            layer.cleanup()
            self._assert_fully_released(layer)
        finally:
            target.destroy()

    def test_clear_then_republish_then_cleanup_releases_everything(self, gl_context, qapp):
        from types import SimpleNamespace

        overlay, layer, target = self._prepared(gl_context)
        try:
            layer.clear()
            card = _CardStub()
            overlay.parentWidget = lambda: SimpleNamespace(
                spotify_visualizer_widget=card, _gl_compositor=layer._compositor
            )
            layer.publish(VisualizerRenderState(overlay, CARD))
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
            layer.render(SURFACE.height(), 1.0)

            layer.cleanup()
            self._assert_fully_released(layer)
        finally:
            target.destroy()

    def test_repeated_cleanup_after_success_is_a_no_op(self, gl_context, qapp):
        overlay, layer, target = self._prepared(gl_context)
        try:
            layer.cleanup()
            layer.cleanup()
            layer.cleanup()
            self._assert_fully_released(layer)
        finally:
            target.destroy()

    def test_destruction_authority_survives_hiding(self, gl_context, qapp):
        """Hiding must not drop the reference needed to free GL resources."""
        overlay, layer, target = self._prepared(gl_context)
        try:
            layer.clear()
            assert layer._resource_owner is not None, (
                "a hidden visualizer still owns GL resources that must be freed"
            )
            layer.cleanup()
            assert layer._resource_owner is None, (
                "destruction authority is released only after successful cleanup"
            )
        finally:
            target.destroy()

    def test_failed_deletion_retains_ownership(self, gl_context, qapp):
        overlay, layer, target = self._prepared(gl_context)
        try:
            def _boom():
                raise RuntimeError("driver refused visualizer delete")

            overlay.cleanup_gl = _boom
            with pytest.raises(RuntimeError, match="cleanup incomplete"):
                layer.cleanup()
            assert layer._resource_owner is not None, (
                "a failed deletion must retain ownership, not silently drop it"
            )
        finally:
            try:
                layer._card_texture.cleanup()
            except Exception:
                pass
            target.destroy()


class TestCardRevisionHasOneAuthority:
    def test_revision_derives_from_the_canonical_card_cache_key(self):
        """Two parallel definitions would eventually disagree."""
        import inspect

        source = inspect.getsource(CompositorVisualizerLayer._card_revision)
        assert "painted_frame_shadow_cache_key" in source, (
            "the GL texture revision must derive from the authored card cache key"
        )

    def test_pixmap_and_texture_share_the_key_resolver(self, qapp):
        from widgets.spotify_visualizer.card_paint import (
            ensure_painted_frame_shadow_pixmap,
            painted_frame_shadow_cache_key,
        )

        card = _CardStub()
        key = painted_frame_shadow_cache_key(
            card, logical_size=CARD.size(), dpr=1.0
        )
        ensure_painted_frame_shadow_pixmap(
            card, logical_size=CARD.size(), dpr=1.0
        )
        assert card._painted_frame_shadow_cache_key == key, (
            "the pixmap cache and the shared resolver must agree exactly"
        )


# ---------------------------------------------------------------------------
# CUSTOM edit snapshot: compositor-owned, card-local, alpha-correct
# ---------------------------------------------------------------------------


class TestEditSceneCapture:
    """The visualizer owns no framebuffer, so edit preview pixels come here.

    These bars render for real and inspect the captured image, because the whole
    failure mode being corrected was a preview that looked plausible in code and
    was blank on screen.
    """

    def _capture(self, ctx, mode, *, card_rect=CARD, surface=SURFACE):
        card = _CardStub(width=card_rect.width(), height=card_rect.height())
        overlay = _overlay_for(mode)
        layer = _layer_with_card(ctx, card, overlay, card_rect=card_rect)
        target = _GLTarget(surface)
        try:
            target.clear()
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
            # One normal presented frame, then one capture request serviced by
            # the next frame - exactly the edit-entry sequence.
            layer.render(surface.height(), 1.0)
            layer.request_scene_capture()
            layer.render(surface.height(), 1.0)
            return layer.take_captured_scene_image(), layer, overlay, target
        except Exception:
            try:
                layer._card_texture.cleanup()
                overlay.cleanup_gl()
            except Exception:
                pass
            target.destroy()
            raise

    @staticmethod
    def _cleanup(layer, overlay, target):
        try:
            layer._card_texture.cleanup()
            overlay.cleanup_gl()
        except Exception:
            pass
        target.destroy()

    def test_capture_is_card_sized_not_display_sized(self, gl_context, qapp):
        image, layer, overlay, target = self._capture(gl_context, "spectrum")
        try:
            assert image is not None and not image.isNull()
            assert image.width() == CARD.width()
            assert image.height() == CARD.height()
            assert image.width() < SURFACE.width()
        finally:
            self._cleanup(layer, overlay, target)

    def test_capture_contains_the_authored_card_pixels(self, gl_context, qapp):
        image, layer, overlay, target = self._capture(gl_context, "spectrum")
        try:
            assert image is not None and not image.isNull()
            arr = _image_array(image)
            assert _lit(arr).any(), "the captured preview has no card pixels at all"
        finally:
            self._cleanup(layer, overlay, target)

    def test_capture_keeps_alpha_instead_of_baking_in_the_base_image(
        self, gl_context, qapp
    ):
        """A readback of the display would be fully opaque and carry the photo."""
        image, layer, overlay, target = self._capture(gl_context, "spectrum")
        try:
            assert image is not None and not image.isNull()
            arr = _image_array(image)
            alpha = arr[..., 3]
            assert alpha.max() > 0, "the capture is entirely transparent"
            assert alpha.min() < 255, (
                "every captured pixel is opaque; the card's alpha was lost"
            )
        finally:
            self._cleanup(layer, overlay, target)

    def test_capture_is_card_local_regardless_of_card_position(
        self, gl_context, qapp
    ):
        """The preview must not bake the card's display position into its pixels."""
        at_origin, l0, o0, t0 = self._capture(
            gl_context, "spectrum", card_rect=QRect(0, 0, 400, 200)
        )
        origin_arr = _image_array(at_origin)
        self._cleanup(l0, o0, t0)

        offset, l1, o1, t1 = self._capture(gl_context, "spectrum", card_rect=CARD)
        offset_arr = _image_array(offset)
        self._cleanup(l1, o1, t1)

        assert origin_arr.shape == offset_arr.shape
        assert np.array_equal(origin_arr[..., :3], offset_arr[..., :3])

    def test_a_serviced_request_is_not_repeated(self, gl_context, qapp):
        card = _CardStub()
        overlay = _overlay_for("spectrum")
        layer = _layer_with_card(gl_context, card, overlay)
        target = _GLTarget(SURFACE)
        try:
            target.clear()
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
            layer.request_scene_capture()
            layer.render(SURFACE.height(), 1.0)
            assert layer.take_captured_scene_image() is not None
            layer.render(SURFACE.height(), 1.0)
            assert layer.take_captured_scene_image() is None, (
                "the capture repeated without a new request"
            )
        finally:
            self._cleanup(layer, overlay, target)

    def test_capture_leaves_the_display_frame_intact(self, gl_context, qapp):
        """Capturing must not disturb the frame the compositor is drawing."""
        card = _CardStub()
        overlay = _overlay_for("spectrum")
        layer = _layer_with_card(gl_context, card, overlay)
        target = _GLTarget(SURFACE)
        try:
            target.clear(rgba=(0.1, 0.2, 0.3, 1.0))
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
            layer.render(SURFACE.height(), 1.0)
            without_capture = target.read().copy()

            target.clear(rgba=(0.1, 0.2, 0.3, 1.0))
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
            layer.request_scene_capture()
            layer.render(SURFACE.height(), 1.0)
            with_capture = target.read().copy()

            assert np.array_equal(without_capture, with_capture), (
                "the capture pass altered the presented display frame"
            )
        finally:
            self._cleanup(layer, overlay, target)


def _image_array(image) -> np.ndarray:
    """QImage -> HxWx4 uint8, without depending on Qt's stride."""
    converted = image.convertToFormat(QImage.Format.Format_RGBA8888)
    width, height = converted.width(), converted.height()
    ptr = converted.constBits()
    raw = bytes(ptr)[: width * height * 4]
    return np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 4)
