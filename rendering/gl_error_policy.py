"""GL error reporting: one check per rendered frame, not one per GL call.

PyOpenGL, by default, calls ``glGetError`` after every GL call and raises ``GLError``. On the
render thread that is a GIL-held C round trip per call, measured (2026-10-03, offscreen, RTX 4090)
at 45-60% of each Visualizer mode's render-thread CPU: Bubble 0.37 -> 0.17 ms, Spectrum 0.43 ->
0.24, Extruded Spectrum 0.65 -> 0.35, Shockwave Grid with glow 1.04 -> 0.41 ms per frame; the
transitions pay the same per call.

The application therefore turns that off once at process start
(``disable_per_call_gl_error_checking``, before ``OpenGL.GL`` is first imported, which is when
PyOpenGL binds its checker), and each Quick render node drains the GL error flags once after its
frame (``raise_pending_gl_error``) inside its existing failure handling, so a GL error is still
reported (through the node's ``RenderFailureLog``), now per node and frame rather than per call.
An error left by GL work outside a node's frame (warm-up steps, releases) surfaces at the next
node frame. Tests and tools keep PyOpenGL's per-call checking, which is stricter, except tools that measure
production cost (``tools/visualizer_cost_probe.py``), which turn it off as the application does.
"""
from __future__ import annotations

import sys

_DRAIN_LIMIT = 8   # GL keeps one flag per error kind; this many reads empties any queue


def disable_per_call_gl_error_checking() -> bool:
    """Turn PyOpenGL's per-call error checking off; True when it takes effect (``OpenGL.GL``
    not imported yet). Call first thing at application start."""
    import OpenGL

    if "OpenGL.GL" in sys.modules:
        return False
    OpenGL.ERROR_CHECKING = False
    return True


class GLFrameError(RuntimeError):
    """GL error flags found after a render node's frame."""


def pending_gl_errors(gl) -> tuple[int, ...]:
    """Drain and return the GL error flags currently set (empty when there are none)."""
    errors: list[int] = []
    for _ in range(_DRAIN_LIMIT):
        error = int(gl.glGetError())
        if error == int(gl.GL_NO_ERROR):
            break
        errors.append(error)
    return tuple(errors)


def raise_pending_gl_error(gl, label: str) -> None:
    """Raise ``GLFrameError`` naming ``label`` if GL error flags are set after its frame."""
    errors = pending_gl_errors(gl)
    if errors:
        raise GLFrameError(f"{label}: GL error(s) " + ", ".join(f"0x{error:04X}" for error in errors))


__all__ = ["GLFrameError", "disable_per_call_gl_error_checking", "pending_gl_errors", "raise_pending_gl_error"]
