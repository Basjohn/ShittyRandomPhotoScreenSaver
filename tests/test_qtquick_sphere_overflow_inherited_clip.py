"""Sphere overflow must follow Qt's scene clip, never prior widget GL residue."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_overflow_uses_shared_qt_clip_boundary_without_changing_clipped_modes():
    node = (ROOT / "rendering/quick/visualizer/node.py").read_text(encoding="utf-8")
    clip = (ROOT / "rendering/quick/visualizer/clip_host.py").read_text(encoding="utf-8")
    overflow = node.split("            if overflow:", 1)[1].split("            else:", 1)[0]
    assert "self._clip_host.prepare_unclipped_render_state(state)" in overflow
    assert overflow.index("prepare_unclipped_render_state(state)") < overflow.index(
        "self._render_host.render("
    )
    assert "self._clip_host.begin(clip_frame, state)" in node
    assert "VisualizerClipHost._apply_incoming_scissor(render_state)" in clip
    assert "if not render_state.stencilEnabled():" in clip
    assert "gl.glDisable(gl.GL_STENCIL_TEST)" in clip
    # Do not introduce expensive glGet*/glIsEnabled calls in the overflow
    # correction: the Qt render state already has the clip information.
    preparation = clip.split("    def prepare_unclipped_render_state(", 1)[1].split(
        "    @staticmethod", 1
    )[0]
    assert "glGet" not in preparation
    assert "glIsEnabled" not in preparation


@pytest.mark.qt
def test_sphere_overflow_discards_stale_widget_scissor_and_stencil(monkeypatch):
    from rendering.quick.visualizer import clip_host

    gl = SimpleNamespace(
        GL_SCISSOR_TEST=1,
        GL_STENCIL_TEST=2,
        glEnable=Mock(),
        glDisable=Mock(),
        glScissor=Mock(),
    )
    monkeypatch.setattr(clip_host, "gl", gl)

    class NoQtClip:
        def scissorEnabled(self):
            return False

        def stencilEnabled(self):
            return False

        def scissorRect(self):
            raise AssertionError("no Qt clip should not read a stale scissor box")

    clip_host.VisualizerClipHost.prepare_unclipped_render_state(NoQtClip())
    assert [call.args for call in gl.glDisable.call_args_list] == [
        (gl.GL_SCISSOR_TEST,),
        (gl.GL_STENCIL_TEST,),
    ]
    gl.glScissor.assert_not_called()


@pytest.mark.qt
def test_sphere_overflow_preserves_real_qt_ancestor_clip(monkeypatch):
    from rendering.quick.visualizer import clip_host
    from PySide6.QtCore import QRect

    gl = SimpleNamespace(
        GL_SCISSOR_TEST=1,
        GL_STENCIL_TEST=2,
        glEnable=Mock(),
        glDisable=Mock(),
        glScissor=Mock(),
    )
    monkeypatch.setattr(clip_host, "gl", gl)

    class QtClip:
        def scissorEnabled(self):
            return True

        def scissorRect(self):
            return QRect(11, 22, 320, 180)

        def stencilEnabled(self):
            return True

    clip_host.VisualizerClipHost.prepare_unclipped_render_state(QtClip())
    gl.glEnable.assert_called_once_with(gl.GL_SCISSOR_TEST)
    gl.glScissor.assert_called_once_with(11, 22, 320, 180)
    gl.glDisable.assert_not_called()
