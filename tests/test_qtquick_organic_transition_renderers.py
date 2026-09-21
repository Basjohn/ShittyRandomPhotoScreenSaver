"""Focused finite-shader contracts for the three organic transition identities."""

from __future__ import annotations

import pytest

from rendering.gl_programs.ink_bloom_program import INK_BLOOM_FRAGMENT_SOURCE
from rendering.gl_programs.melt_drip_program import MELT_DRIP_FRAGMENT_SOURCE
from rendering.gl_programs.tendril_reveal_program import TENDRIL_REVEAL_FRAGMENT_SOURCE
from rendering.quick.transitions.implementations.ink_bloom import (
    QuickInkBloomRenderer,
    ink_bloom_parameters,
)
from rendering.quick.transitions.implementations.melt_drip import (
    QuickMeltDripRenderer,
    melt_drip_parameters,
)
from rendering.quick.transitions.implementations.tendril_reveal import (
    QuickTendrilRevealRenderer,
    tendril_reveal_parameters,
)


@pytest.mark.parametrize(
    ("resolver", "name"),
    ((ink_bloom_parameters, "Ink Bloom"), (tendril_reveal_parameters, "Tendril Reveal")),
)
def test_nondirectional_organic_effects_accept_only_bounded_seed_and_detail(resolver, name):
    params = resolver({"seed": 412, "detail": 1.45})
    assert params.seed == 412
    assert params.detail == pytest.approx(1.45)
    for invalid in (0, 65536, True, 3.5):
        with pytest.raises(ValueError, match="seed"):
            resolver({"seed": invalid, "detail": 1.0})
    for invalid in (0.49, 2.01, float("inf"), True, "fine"):
        with pytest.raises(ValueError, match="detail"):
            resolver({"seed": 1, "detail": invalid})


@pytest.mark.parametrize(
    ("direction", "expected"),
    (("down", (0.0, 1.0)), ("up", (0.0, -1.0)), ("left", (-1.0, 0.0)), ("right", (1.0, 0.0))),
)
def test_melt_drip_uses_one_resolved_gravity_direction(direction, expected):
    params = melt_drip_parameters({"seed": 12, "detail": 0.5}, direction)
    assert params.direction == expected
    for invalid in (None, "Random", "diagonal", 3):
        with pytest.raises(ValueError, match="resolved direction"):
            melt_drip_parameters({"seed": 12, "detail": 1.0}, invalid)


def test_organic_renderers_are_distinct_lazy_local_surfaces():
    assert QuickInkBloomRenderer.transition_id == "ink_bloom"
    assert QuickTendrilRevealRenderer.transition_id == "tendril_reveal"
    assert QuickMeltDripRenderer.transition_id == "melt_drip"
    assert not QuickInkBloomRenderer().has_resources
    assert not QuickTendrilRevealRenderer().has_resources
    assert not QuickMeltDripRenderer().has_resources


def test_organic_shaders_have_exact_endpoints_and_distinct_bounded_identities():
    for source in (INK_BLOOM_FRAGMENT_SOURCE, TENDRIL_REVEAL_FRAGMENT_SOURCE, MELT_DRIP_FRAGMENT_SOURCE):
        assert "if (t <= 0.0) { FragColor = texture(uOldTex, uv); return; }" in source
        assert "if (t >= 1.0) { FragColor = texture(uNewTex, uv); return; }" in source
        assert "u_seed" in source
        assert "u_detail" in source
        assert "raymarch" not in source.lower()
        assert "while (" not in source
    assert "bloomField" in INK_BLOOM_FRAGMENT_SOURCE
    assert "for (int i = 0; i < 6; ++i)" in INK_BLOOM_FRAGMENT_SOURCE
    assert "wetEdge" in INK_BLOOM_FRAGMENT_SOURCE
    assert "segmentDistance" in TENDRIL_REVEAL_FRAGMENT_SOURCE
    assert "for (int i = 0; i < 9; ++i)" in TENDRIL_REVEAL_FRAGMENT_SOURCE
    assert "roundedDrips" in MELT_DRIP_FRAGMENT_SOURCE
    assert "sourceUv" in MELT_DRIP_FRAGMENT_SOURCE
    assert "u_direction" in MELT_DRIP_FRAGMENT_SOURCE
    assert "1.0 - smoothstep(" in INK_BLOOM_FRAGMENT_SOURCE
    assert "1.0 - smoothstep(" in TENDRIL_REVEAL_FRAGMENT_SOURCE
    assert "1.0 - smoothstep(" in MELT_DRIP_FRAGMENT_SOURCE


@pytest.mark.qt
def test_organic_fragment_shaders_compile_on_the_installed_core_driver(qt_app):
    """Keep syntax and bounded-loop changes honest against the real GLSL driver."""

    from OpenGL import GL as gl
    from PySide6.QtGui import QOffscreenSurface, QOpenGLContext, QSurfaceFormat

    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.OpenGL)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setVersion(4, 1)
    context = QOpenGLContext()
    context.setFormat(fmt)
    if not context.create():
        pytest.skip("OpenGL 4.1 context unavailable")
    surface = QOffscreenSurface()
    surface.setFormat(fmt)
    surface.create()
    if not surface.isValid() or not context.makeCurrent(surface):
        pytest.skip("offscreen OpenGL context unavailable")
    try:
        for label, source in (
            ("ink bloom", INK_BLOOM_FRAGMENT_SOURCE),
            ("tendril reveal", TENDRIL_REVEAL_FRAGMENT_SOURCE),
            ("melt drip", MELT_DRIP_FRAGMENT_SOURCE),
        ):
            shader = gl.glCreateShader(gl.GL_FRAGMENT_SHADER)
            try:
                gl.glShaderSource(shader, source)
                gl.glCompileShader(shader)
                log = gl.glGetShaderInfoLog(shader)
                if isinstance(log, bytes):
                    log = log.decode("utf-8", errors="ignore")
                assert gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS) == gl.GL_TRUE, (
                    f"{label} fragment shader failed to compile: {str(log).strip()}"
                )
            finally:
                gl.glDeleteShader(shader)
    finally:
        context.doneCurrent()
        surface.destroy()
