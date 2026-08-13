from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from rendering import gl_compositor
from rendering.gl_compositor import GLCompositorWidget
from rendering.gl_compositor_pkg import paint, shader_dispatch
from rendering.gl_programs.crossfade_program import CrossfadeProgram
from rendering.gl_programs.texture_manager import GLTextureManager
from rendering.gl_transition_renderer import GLTransitionRenderer
from rendering import gl_transition_renderer


def test_cached_texture_lookup_never_uploads_or_counts_transition_hit() -> None:
    manager = GLTextureManager()
    pixmap = MagicMock()
    pixmap.isNull.return_value = False
    pixmap.cacheKey.return_value = 77
    manager._texture_cache = {77: 901}
    manager._texture_lru = [77]
    manager.upload_pixmap = MagicMock(return_value=902)

    assert manager.get_cached_texture_id(pixmap) == 901
    manager.upload_pixmap.assert_not_called()
    assert manager.get_stats()["texture_cache_hits"] == 0


def test_crossfade_single_texture_binds_same_retained_texture(monkeypatch) -> None:
    program = CrossfadeProgram()
    captured = {}
    monkeypatch.setattr(program, "_render_textures", lambda **kwargs: captured.update(kwargs))

    program.render_single_texture(
        program=11,
        uniforms={"u_progress": 3},
        viewport=(2560, 1440),
        texture_id=901,
        quad_vao=17,
    )

    assert captured["old_tex"] == captured["new_tex"] == 901
    assert captured["progress"] == 1.0
    assert captured["viewport"] == (2560, 1440)


def test_transition_renderer_draws_retained_texture_without_state_allocation(
    monkeypatch,
) -> None:
    calls = []
    helper = SimpleNamespace(
        render_single_texture=lambda **kwargs: calls.append(kwargs)
    )
    pipeline = SimpleNamespace(
        crossfade_program=13,
        crossfade_uniforms={"u_progress": 2},
        quad_vao=19,
    )
    renderer = GLTransitionRenderer(
        compositor=object(),
        get_pipeline=lambda: pipeline,
        get_texture_manager=lambda: None,
        get_profiler=lambda: None,
        get_viewport_size=lambda: (3840, 2160),
        get_render_progress=lambda fallback: fallback,
    )
    renderer.set_program_getters({"crossfade": lambda: helper})
    monkeypatch.setattr(gl_transition_renderer, "gl", object())

    assert renderer.render_retained_base_texture(901) is True
    assert calls == [
        {
            "program": 13,
            "uniforms": {"u_progress": 2},
            "viewport": (3840, 2160),
            "texture_id": 901,
            "quad_vao": 19,
        }
    ]


def test_retained_base_dispatch_preserves_dimming_and_overlay_order(monkeypatch) -> None:
    calls = []
    pixmap = SimpleNamespace(isNull=lambda: False)
    comp = SimpleNamespace(
        _gl_disabled_for_session=False,
        _gl_pipeline=SimpleNamespace(initialized=True, crossfade_program=13),
        _texture_manager=SimpleNamespace(
            get_cached_texture_id=lambda candidate: 901 if candidate is pixmap else 0
        ),
        _base_pixmap=pixmap,
        _transition_renderer=SimpleNamespace(
            render_retained_base_texture=lambda texture_id: calls.append(
                ("base", texture_id)
            )
            or True
        ),
    )
    monkeypatch.setattr(shader_dispatch, "gl", object())
    monkeypatch.setattr(
        "rendering.gl_compositor_pkg.overlays.paint_dimming_gl",
        lambda owner: calls.append(("dimming", owner)),
    )
    monkeypatch.setattr(
        shader_dispatch,
        "paint_qpainter_overlays_gl",
        lambda owner: calls.append(("overlays", owner)),
    )

    assert shader_dispatch.paint_retained_base_texture(comp, object()) is True
    assert calls == [("base", 901), ("dimming", comp), ("overlays", comp)]


def test_idle_paint_uses_retained_texture_path_without_qpainter(monkeypatch) -> None:
    calls = []

    class _Widget:
        _frame_state = None
        _gl_state = SimpleNamespace(is_ready=lambda: True)
        _blockspin = None
        _blockflip = None
        _raindrops = None
        _warp = None
        _diffuse = None
        _blinds = None
        _crumble = None
        _particle = None
        _burn = None
        _crossfade = None
        _slide = None
        _wipe = None

        def rect(self):
            return "target"

        def _paint_retained_base_texture(self, target):
            calls.append(("retained", target))
            return True

    monkeypatch.setattr(paint, "is_perf_metrics_enabled", lambda: False)
    monkeypatch.setattr(
        paint,
        "QPainter",
        lambda _owner: (_ for _ in ()).throw(
            AssertionError("idle retained texture must not enter QPainter base path")
        ),
    )

    paint.paintGL_impl(_Widget())

    assert calls == [("retained", "target")]


@pytest.mark.qt_no_exception_capture
def test_real_compositor_retained_base_draw_preserves_quadrant_orientation(qapp) -> None:
    if gl_compositor.gl is None:
        pytest.skip("PyOpenGL unavailable")

    parent = QWidget()
    parent.resize(96, 96)
    comp = GLCompositorWidget(parent)
    comp.setGeometry(parent.rect())
    comp.show()
    parent.show()
    qapp.processEvents()

    pixmap = QPixmap(96, 96)
    painter = QPainter(pixmap)
    try:
        painter.fillRect(QRect(0, 0, 48, 48), QColor("red"))
        painter.fillRect(QRect(48, 0, 48, 48), QColor("green"))
        painter.fillRect(QRect(0, 48, 48, 48), QColor("blue"))
        painter.fillRect(QRect(48, 48, 48, 48), QColor("yellow"))
    finally:
        painter.end()

    try:
        comp.grabFramebuffer()
        if (
            comp._texture_manager is None
            or comp._gl_pipeline is None
            or not comp._gl_pipeline.initialized
        ):
            pytest.skip("Compositor GL pipeline unavailable")
        comp.makeCurrent()
        texture_id = comp._texture_manager.get_or_create_texture(pixmap)
        comp.doneCurrent()
        if not texture_id:
            pytest.skip("Texture upload unavailable")

        comp.set_base_pixmap(pixmap)
        frame = comp.grabFramebuffer()
        samples = (
            frame.pixelColor(frame.width() // 4, frame.height() // 4),
            frame.pixelColor(3 * frame.width() // 4, frame.height() // 4),
            frame.pixelColor(frame.width() // 4, 3 * frame.height() // 4),
            frame.pixelColor(3 * frame.width() // 4, 3 * frame.height() // 4),
        )

        expected = (QColor("red"), QColor("green"), QColor("blue"), QColor("yellow"))
        for actual, wanted in zip(samples, expected):
            assert abs(actual.red() - wanted.red()) <= 3
            assert abs(actual.green() - wanted.green()) <= 3
            assert abs(actual.blue() - wanted.blue()) <= 3
    finally:
        comp.cleanup()
        parent.close()
        parent.deleteLater()
