"""GL errors are checked once per rendered frame, not after every GL call (H7).

The application entry turns PyOpenGL's per-call checking off before ``OpenGL.GL`` loads (the
render thread's largest CPU cost: 45-60% per Visualizer mode), and each Quick render node drains
the GL error flags after its frame, so an error still reaches the node's failure log."""
from __future__ import annotations

import subprocess
import sys

import pytest


def test_the_application_entry_disables_per_call_checking_before_gl_loads():
    code = ("import sys, main, OpenGL\n"
            "print(OpenGL.ERROR_CHECKING, 'OpenGL.GL' in sys.modules)\n")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180, check=True)
    assert result.stdout.strip().splitlines()[-1] == "False True"
    # Too late once OpenGL.GL is bound: the policy says so instead of pretending.
    code = ("import OpenGL.GL\nfrom rendering.gl_error_policy import disable_per_call_gl_error_checking\n"
            "import OpenGL\nprint(disable_per_call_gl_error_checking(), OpenGL.ERROR_CHECKING)\n")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120, check=True)
    assert result.stdout.strip().splitlines()[-1] == "False True"


@pytest.mark.qt
def test_a_pending_gl_error_is_drained_and_raised_once_per_frame(qt_app):
    from OpenGL import GL as gl
    from OpenGL.platform import PLATFORM

    from rendering.gl_error_policy import GLFrameError, pending_gl_errors, raise_pending_gl_error
    from tools.transition_contact_sheet import TransitionCapture

    capture = TransitionCapture(64, 64)
    try:
        assert pending_gl_errors(gl) == ()
        raise_pending_gl_error(gl, "clean frame")                      # nothing set: no error
        PLATFORM.GL.glEnable(0xFFFF)              # GL_INVALID_ENUM straight through ctypes, unchecked
        with pytest.raises(GLFrameError, match=r"Visualizer render node: GL error\(s\) 0x0500"):
            raise_pending_gl_error(gl, "Visualizer render node")
        assert pending_gl_errors(gl) == ()                              # drained
    finally:
        capture.close()


def test_both_quick_render_nodes_check_once_inside_their_failure_handling():
    """The check sits in each GL render node's ``try`` before success is noted, so an error
    reaches its ``RenderFailureLog`` like any render failure."""
    import inspect

    from rendering.quick.render.background_node import BackgroundRenderNode
    from rendering.quick.visualizer.node import VisualizerRenderNode

    for node, label in ((BackgroundRenderNode, "Background render node"),
                        (VisualizerRenderNode, "Visualizer render node")):
        source = inspect.getsource(node.render)
        check = source.index(f'raise_pending_gl_error(gl, "{label}")')
        assert source.index("try:") < check < source.index("note_success()") < source.index("except Exception")
        assert source.count("raise_pending_gl_error") == 1
