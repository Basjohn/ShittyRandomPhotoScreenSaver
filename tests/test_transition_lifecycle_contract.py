"""Every showcase transition keeps the lifecycle contract, counted by the GL object ledger
(``tools/gl_object_ledger.py``) on a real offscreen context (no window):

* once warmed (geometry prepared as COMPUTE does, then warm steps to completion) a run's frames
  create no GL object: no compile, texture, buffer or target on a visible frame;
* what ``park()`` keeps does not depend on the run: three runs leave the same objects alive;
* ``release_resources()`` deletes every object the renderer ever created.

A new transition joins automatically through the release-media catalogue. Counts, not timings:
the result is the same on a busy machine.
"""
from __future__ import annotations

import pytest

from tools.gl_object_ledger import GLObjectLedger
from tools.release_media import _transition_run, catalogue

pytestmark = pytest.mark.qt

W, H = 256, 144
_CASES = [case for case in catalogue() if case.kind == "transition"]


@pytest.mark.parametrize("case", _CASES, ids=[f"{c.identity}/{c.variant}" for c in _CASES])
def test_warmed_runs_create_nothing_park_holds_steady_and_release_frees_everything(qt_app, case):
    from rendering.quick.transitions.run_geometry import prepare_run_geometry
    from tools.transition_contact_sheet import TransitionCapture

    capture = TransitionCapture(W, H)
    try:
        with GLObjectLedger() as ledger:
            parked = []
            for cycle, seed in enumerate((713, 99, 4242)):
                run = _transition_run(capture, case.identity, case.duration_ms, case.settings, seed=seed,
                                      run_id=cycle + 1)
                request = run.request
                prepare_run_geometry(request.transition_id, request.parameter_dict(), (W / H,), request.direction)
                steps = 0
                while not capture.host.warm_step(request.transition_id, request.parameter_dict(), (W, H)):
                    steps += 1
                    assert steps < 200, "warm-up never finished"
                warmed = dict(ledger.created)
                for progress in (0.0, 0.3, 0.6, 0.95, 1.0):
                    capture.render(run, progress)
                created = {kind: ledger.created[kind] - warmed[kind] for kind in warmed if ledger.created[kind] != warmed[kind]}
                assert not created, f"run {cycle + 1}'s frames created GL objects after warm-up: {created}"
                capture.host.park()
                parked.append(ledger.live())
            assert parked[0] == parked[1] == parked[2], f"park keeps run-dependent objects: {parked}"
            capture.host.release_resources()
            assert not ledger.live(), ledger.describe()
            assert not capture.host._implementations
    finally:
        capture.close()


def test_the_ledger_sees_creates_and_deletes(qt_app):
    from OpenGL import GL as gl

    from tools.transition_contact_sheet import TransitionCapture

    capture = TransitionCapture(16, 16)
    try:
        with GLObjectLedger() as ledger:
            textures = gl.glGenTextures(2)
            buffer = gl.glGenBuffers(1)
            program = gl.glCreateProgram()
            assert ledger.live() == {"textures": 2, "buffers": 1, "programs": 1}
            gl.glDeleteTextures(2, textures)
            gl.glDeleteBuffers(1, [buffer])
            gl.glDeleteProgram(program)
            assert not ledger.live() and ledger.created["textures"] == 2
        assert gl.glGenTextures.__name__ != "call"          # uninstalled on exit
    finally:
        capture.close()
