"""Gate 1 - paused Spectrum idle bars must be VISIBLE PIXELS, not just non-zero.

`Docs/P2_Behavioral_Gates.md` Gate 1, and Current_Plan Slice G.

The prior Gate 1 rendered nothing: it recorded the frame kwargs a stub parent
received and asserted `max(bars) > 0`. The first installed run proved that is
not a visibility oracle - the real renderer received idle values of 0.010-0.030,
scaled them by 0.55, applied pow(1.15) and the card height-scale, and produced a
tallest bar of ~1px on an 80px card and ~4px on the installed enlarged card in
single-piece mode. Non-zero, and invisible.

These bars render the real compositor Spectrum shader into a real offscreen GL
target and read the pixels back, exactly like `test_p2_single_surface_gl_render`.
They assert the tallest resting bar occupies a deliberately visible minimum
height across representative card sizes, DPRs and both the single-piece and
segmented paths - and that it stays a calm resting hump rather than full signal.

`max(bars) > 0` is deliberately absent as a visibility assertion here.
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
    VisualizerRenderState,
)
from widgets.spotify_bars_gl_overlay import SpotifyBarsGLOverlay  # noqa: E402
from widgets.spotify_visualizer import spectrum_presentation_smoothing as sps  # noqa: E402

SURFACE = QSize(800, 600)
_BAR_COUNT = 16
_SEGMENTS = 18

# The resting-scene contract: the tallest idle bar must render at least this many
# physical pixels on the smallest supported card. Single-piece is the path the
# first installed run showed invisible (<= 4px across every card size), so it
# carries the strict threshold. Segmented mode always lights at least one whole
# segment for any non-zero value, but on a small card 18 segments quantize the
# bottom segment to ~2-4px, so it carries a looser floor - it was never the
# invisible case.
_MIN_VISIBLE_PX_SOLID = 5
_MIN_VISIBLE_PX_SEGMENTED = 3

# It must also stay a resting hump, not full signal.
_MAX_RESTING_FRACTION = 0.35


def _min_visible_px(single_piece: bool) -> int:
    return _MIN_VISIBLE_PX_SOLID if single_piece else _MIN_VISIBLE_PX_SEGMENTED


# ---------------------------------------------------------------------------
# Real offscreen GL target (mirrors test_p2_single_surface_gl_render)
# ---------------------------------------------------------------------------


class _GLTarget:
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

    def clear(self):
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, self.fbo)
        gl.glViewport(0, 0, self.size.width(), self.size.height())
        gl.glDisable(gl.GL_SCISSOR_TEST)
        gl.glClearColor(0.0, 0.0, 0.0, 1.0)
        gl.glClearStencil(0)
        gl.glClear(
            gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT | gl.GL_STENCIL_BUFFER_BIT
        )

    def read(self) -> np.ndarray:
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
    def __init__(self, ctx):
        self._rhi_gl = type(
            "_Borrowed", (), {
                "context": ctx, "generation": 1,
                "is_attached": staticmethod(lambda: True),
                "make_current": staticmethod(lambda: True),
            },
        )()


def _render_idle_spectrum(ctx, *, card_h, single_piece, dpr=1.0, bars=None):
    """Render a paused idle Spectrum scene and return (drew, tallest_px, lit_cols).

    `bars` defaults to the real `idle_spectrum_baseline` output; a caller may
    pass an alternate scene to exercise a different resting magnitude.
    """
    card = QRect(120, 80, 400, int(card_h))
    if bars is None:
        bars = sps.idle_spectrum_baseline(_BAR_COUNT)

    overlay = SpotifyBarsGLOverlay(None)
    overlay.set_state(
        rect=QRect(0, 0, card.width(), card.height()),
        bars=list(bars),
        bar_count=len(bars),
        segments=_SEGMENTS,
        fill_color=QColor(255, 255, 255),
        border_color=QColor(255, 255, 255),
        fade=1.0,
        playing=False,          # paused: this is the idle scene
        visible=True,
        vis_mode="spectrum",
    )
    overlay._single_piece = bool(single_piece)
    overlay._compositor_card_surface_enabled = False

    target = _GLTarget(SURFACE)
    try:
        target.clear()
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, target.fbo)
        layer = CompositorVisualizerLayer(_FakeCompositor(ctx))
        layer.publish(VisualizerRenderState(overlay, card))
        drew = bool(layer.render(SURFACE.height(), dpr))
        pixels = target.read()
    finally:
        try:
            overlay.cleanup_gl()
        except Exception:
            pass
        target.destroy()

    x0, y0 = int(card.x() * dpr), int(card.y() * dpr)
    region = pixels[y0:y0 + int(card_h * dpr), x0:x0 + int(card.width() * dpr)]
    lit = region[..., :3].max(axis=-1) > 8
    col_heights = lit.sum(axis=0)
    return drew, int(col_heights.max()), int((col_heights > 0).sum())


_CARD_HEIGHTS = (80, 160, 277)


class TestPausedSpectrumIdleHasVisiblePixels:
    @pytest.mark.parametrize("card_h", _CARD_HEIGHTS)
    @pytest.mark.parametrize("single_piece", [True, False])
    def test_the_tallest_resting_bar_is_visibly_tall(
        self, gl_context, qapp, single_piece, card_h
    ):
        drew, tallest, lit_cols = _render_idle_spectrum(
            gl_context, card_h=card_h, single_piece=single_piece
        )
        if not drew:
            pytest.skip("spectrum shader unavailable in this environment")

        minimum = _min_visible_px(single_piece)
        assert tallest >= minimum, (
            f"paused idle Spectrum tallest bar is only {tallest}px on a {card_h}px "
            f"card (single_piece={single_piece}); the resting scene is not "
            f"perceptibly visible (need >= {minimum}px)"
        )

    @pytest.mark.parametrize("card_h", _CARD_HEIGHTS)
    @pytest.mark.parametrize("single_piece", [True, False])
    def test_the_resting_scene_spans_the_card(
        self, gl_context, qapp, single_piece, card_h
    ):
        drew, tallest, lit_cols = _render_idle_spectrum(
            gl_context, card_h=card_h, single_piece=single_piece
        )
        if not drew:
            pytest.skip("spectrum shader unavailable in this environment")

        # A resting hump should light most of the card width, not one center bar.
        assert lit_cols > 200, (
            f"the idle scene lit only {lit_cols} columns; the resting bars do not "
            f"span the card"
        )

    @pytest.mark.parametrize("card_h", _CARD_HEIGHTS)
    def test_the_resting_scene_is_visible_at_dpr_1_5(self, gl_context, qapp, card_h):
        drew, tallest, _ = _render_idle_spectrum(
            gl_context, card_h=card_h, single_piece=True, dpr=1.5
        )
        if not drew:
            pytest.skip("spectrum shader unavailable in this environment")

        assert tallest >= _MIN_VISIBLE_PX_SOLID, (
            f"idle Spectrum is only {tallest}px tall at DPR 1.5 on a {card_h}px card"
        )

    @pytest.mark.parametrize("card_h", _CARD_HEIGHTS)
    @pytest.mark.parametrize("single_piece", [True, False])
    def test_the_resting_scene_stays_a_hump_not_full_signal(
        self, gl_context, qapp, single_piece, card_h
    ):
        drew, tallest, _ = _render_idle_spectrum(
            gl_context, card_h=card_h, single_piece=single_piece
        )
        if not drew:
            pytest.skip("spectrum shader unavailable in this environment")

        assert tallest <= card_h * _MAX_RESTING_FRACTION, (
            f"idle Spectrum tallest bar is {tallest}px on a {card_h}px card - that "
            f"reads as signal, not a resting scene"
        )


class TestTheGateCatchesTheInstalledInvisibleMagnitude:
    """Gate 10 - the visible-pixel gate must fail on the installed-invisible scene.

    Rendering the old 0.010-0.030 baseline through the same real renderer must
    fall below the visible minimum in single-piece mode, proving this gate would
    have caught the first installed run's absent idle bars.
    """

    @pytest.mark.parametrize("card_h", _CARD_HEIGHTS)
    def test_the_old_baseline_magnitude_is_below_the_visible_minimum(
        self, gl_context, qapp, card_h
    ):
        old_baseline = [
            0.010 + (0.030 - 0.010) * (np.sin((i / (_BAR_COUNT - 1)) * np.pi))
            for i in range(_BAR_COUNT)
        ]
        drew, tallest, _ = _render_idle_spectrum(
            gl_context, card_h=card_h, single_piece=True, bars=old_baseline
        )
        if not drew:
            pytest.skip("spectrum shader unavailable in this environment")

        assert tallest < _MIN_VISIBLE_PX_SOLID, (
            f"the installed-invisible 0.010-0.030 baseline rendered {tallest}px on "
            f"a {card_h}px card, so this gate would not have caught it"
        )
