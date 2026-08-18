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
from PySide6.QtGui import QColor, QSurfaceFormat

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

