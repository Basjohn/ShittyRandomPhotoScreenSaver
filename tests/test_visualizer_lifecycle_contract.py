"""Visualizer modes keep the lifecycle contract, counted by the GL object ledger
(``tools/gl_object_ledger.py``) on a real offscreen context (no window): cycling every mode holds only the current
mode's objects and ``release_resources()`` frees all. (The transitions' own lifecycle is the native core's, N5.2h.)
Counts, not timings: the result is the same on a busy machine.
"""
from __future__ import annotations

import pytest

from tools.gl_object_ledger import GLObjectLedger

pytestmark = pytest.mark.qt


def test_visualizer_modes_hold_only_the_current_mode_and_release_frees_everything(qt_app):
    """Cycling every Visualizer mode three times through one production host: the objects alive
    after each mode are the same in every cycle (a switch retires the previous mode's), and
    ``release_resources()`` deletes everything."""
    from OpenGL import GL as gl

    from core.settings.visualizer_mode_registry import iter_visualizer_mode_descriptors
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot
    from tools.labs.render_target import OffscreenRenderTarget

    width, height = 160, 90
    capture = OffscreenRenderTarget(width, height)
    matrix = (2 / width, 0, 0, 0, 0, -2 / height, 0, 0, 0, 0, 1, 0, -1, 1, 0, 1)
    modes = [descriptor.mode_id for descriptor in iter_visualizer_mode_descriptors()]
    snapshots = {mode: _build_spectrum_preview_snapshot(width=width, height=height, mode=mode) for mode in modes}
    try:
        with GLObjectLedger() as ledger:
            host = QuickVisualizerRenderHost()
            cycles = []
            for _cycle in range(3):
                alive = {}
                for mode in modes:
                    for _frame in range(2):
                        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
                        host.render(snapshot=snapshots[mode], viewport=(0, 0, width, height),
                                    logical_size=(float(width), float(height)), matrix_values=matrix)
                    alive[mode] = ledger.live()
                cycles.append(alive)
            assert cycles[0] == cycles[1] == cycles[2], cycles
            host.release_resources()
            assert not ledger.live(), ledger.describe()
    finally:
        capture.close()
