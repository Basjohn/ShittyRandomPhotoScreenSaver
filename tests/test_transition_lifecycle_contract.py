"""Every showcase transition keeps the lifecycle contract, counted by the GL object ledger
(``tools/gl_object_ledger.py``) on a real offscreen context (no window):

* once warmed (geometry prepared as COMPUTE does, then warm steps to completion) a run's frames
  create no GL object: no compile, texture, buffer or target on a visible frame;
* what ``park()`` keeps does not depend on the run: three runs leave the same objects alive;
* ``release_resources()`` deletes every object the renderer ever created;
* Visualizer modes: cycling every mode holds only the current mode's objects and release frees all;
* rounds of every transition retain no Python objects (no type rises in every round).

A new transition joins automatically through the release-media catalogue. Counts, not timings:
the result is the same on a busy machine.
"""
from __future__ import annotations

import pytest

from tools.gl_object_ledger import GLObjectLedger
from tools.release_media import catalogue

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
                run = capture.production_run(case.identity, case.duration_ms, case.settings, seed=seed,
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


def test_visualizer_modes_hold_only_the_current_mode_and_release_frees_everything(qt_app):
    """Cycling every Visualizer mode three times through one production host: the objects alive
    after each mode are the same in every cycle (a switch retires the previous mode's), and
    ``release_resources()`` deletes everything."""
    from OpenGL import GL as gl

    from core.settings.visualizer_mode_registry import iter_visualizer_mode_descriptors
    from rendering.quick.visualizer.render_host import QuickVisualizerRenderHost
    from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot
    from tools.transition_contact_sheet import TransitionCapture

    width, height = 160, 90
    capture = TransitionCapture(width, height)
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


def test_rounds_of_every_transition_leave_no_python_objects_behind(qt_app):
    """Python-side retention (a per-run cache entry, ctypes type or closure kept forever) is
    invisible to the GL ledger. After two rounds fill the legitimate caches, four more rounds of
    every transition with fresh seeds run; a type whose live count rises in **every** round is
    retaining something per run (one leaked ctypes type per Crossfade run alone is caught),
    while incidental churn never rises four times running."""
    import gc
    import json
    from collections import Counter

    from rendering.quick.transitions.run_geometry import prepare_run_geometry
    from tools.transition_contact_sheet import TransitionCapture

    width, height = 128, 72
    capture = TransitionCapture(width, height)

    def one_round(index):
        for number, case in enumerate(_CASES):
            run = capture.production_run(case.identity, case.duration_ms, case.settings,
                                  seed=1000 * index + number, run_id=100 * index + number + 1)
            request = run.request
            prepare_run_geometry(request.transition_id, request.parameter_dict(), (width / height,), request.direction)
            while not capture.host.warm_step(request.transition_id, request.parameter_dict(), (width, height)):
                pass
            for progress in (0.0, 0.4, 1.0):
                capture.host.render(capture.frame(run, progress))
            capture.host.park()

    def census() -> str:
        gc.collect()
        # Kept as a string, which the collector does not track, so the census never counts itself.
        return json.dumps(Counter(type(item).__name__ for item in gc.get_objects()))

    try:
        one_round(0)
        one_round(1)
        snapshots = [census()]
        for index in (2, 3, 4, 5):
            one_round(index)
            snapshots.append(census())
    finally:
        capture.close()
    counts = [json.loads(snapshot) for snapshot in snapshots]
    names = set().union(*counts)
    rising = {name: [c.get(name, 0) for c in counts] for name in names
              if all(b.get(name, 0) > a.get(name, 0) for a, b in zip(counts, counts[1:]))}
    assert not rising, f"types retained per round of transitions: {rising}"
