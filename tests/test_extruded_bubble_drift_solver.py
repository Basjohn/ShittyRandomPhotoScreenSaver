"""The GPU drift solver integrates the logical step log like the CPU reference (MaterialPaths/ProceduralOffsets).

Test-owned controls only; the comparison reads the solver's output back, which production never does.
"""
from dataclasses import replace

import numpy as np
import pytest

from widgets.spotify_visualizer.extruded_bubble_drift import DRIFT_DIRECTIONS
from widgets.spotify_visualizer.extruded_bubble_drift_log import STEP_HISTORY, MaterialDriftReference
from widgets.spotify_visualizer.extruded_bubble_simulation import (
    ExtrudedBubbleControls, ExtrudedBubbleSimulation, MusicInput,
)


def _controls(kind, **extra):
    return ExtrudedBubbleControls(large_count=(2, 2), mid_count=(3, 3), bead_chains=(2., 3.), emission=(.2, .5),
                                  stream_path=(0., -1., 0., .2, 1., .1), emission_geometry='SCENE',
                                  drift=(.6, 1.), drift_chains=(1., 1.5), drift_snow=(1., 1.), drift_specks=(1., 1.),
                                  drift_direction=kind, stream_speed=(.05, .2), collision_scope='off', **extra)


def _log(controls, ticks, seed=11, edit_at=None):
    sim = ExtrudedBubbleSimulation(seed)
    for tick in range(ticks):
        body = .8 if tick % 30 < 12 else .3
        if edit_at is not None and tick == edit_at:
            controls = replace(controls, stream_path=(.1, -1., .1, -.2, 1., .2), particle_spread=1.2)
        state = sim.advance(MusicInput(1 / 60, True, body, (('kick', 1.),) if tick % 20 == 0 else (),
                                       (body, body * .8, .5)), controls)
        yield state.drift_families, state.drift_steps


def _compare(log, every):
    from OpenGL import GL as gl
    from rendering.quick.scene3d.resources import MeshResources
    from rendering.quick.visualizer.implementations.extruded_bubble_drift_solver import DriftSolver
    from tools.labs.render_target import OffscreenRenderTarget
    target, resources, solver = OffscreenRenderTarget(16, 16), MeshResources('drift solver test'), DriftSolver('test')
    reference, worst, frames = MaterialDriftReference(), {}, 0
    try:
        for index, (families, steps) in enumerate(log):
            if index % every or not families:
                continue
            offsets = solver.update(resources, families, steps)
            payload = reference.apply(families, steps)
            gl.glFinish()
            data = np.empty(offsets['_total'] * 4, dtype=np.float32)
            gl.glGetNamedBufferSubData(solver.output, 0, data.nbytes, data)
            data = data.reshape(-1, 4)
            for family in families:
                expected = np.frombuffer(payload[family.family], dtype=np.float32).reshape(-1, 4)
                got = data[offsets[family.family]:offsets[family.family] + len(expected)]
                scale = max(1.0, float(np.abs(expected[:, :3]).max()))
                worst[family.family] = max(worst.get(family.family, 0.),
                                           float(np.abs(got[:, :3] - expected[:, :3]).max()) / scale)
                # Chains carry the knot shift exactly (fp64 geometry); clouds' float32 spans differ from the CPU's
                # float64 ones by ~6e-8 relative, a fixed and smooth difference in progress that grows with travel.
                assert np.abs(got[:, 3] - expected[:, 3]).max() < 1e-4, family.family
            frames += 1
    finally:
        solver.release()
        resources.release_resources()
        target.close()
    return frames, worst


@pytest.mark.parametrize('kind', DRIFT_DIRECTIONS)
def test_solver_matches_the_cpu_reference_for_every_drift_direction(qt_app, kind):
    frames, worst = _compare(_log(_controls(kind), 150), every=2)
    assert frames > 60 and set(worst) == {'chains', 'snow', 'specks'}
    assert max(worst.values()) < 1e-4, worst


def test_solver_applies_several_steps_per_frame_and_continues_history_across_a_geometry_edit(qt_app):
    frames, worst = _compare(_log(_controls('swirl_cw'), 240, edit_at=120), every=5)
    assert frames > 40 and max(worst.values()) < 1e-4, worst


def test_a_render_gap_beyond_the_published_history_restarts_cleanly(qt_app):
    from OpenGL import GL as gl
    from rendering.quick.scene3d.resources import MeshResources
    from rendering.quick.visualizer.implementations.extruded_bubble_drift_solver import DriftSolver
    from tools.labs.render_target import OffscreenRenderTarget
    log = list(_log(_controls('swirl_ccw'), STEP_HISTORY + 60))
    target, resources, solver = OffscreenRenderTarget(16, 16), MeshResources('drift gap test'), DriftSolver('gap')
    try:
        solver.update(resources, *log[10])
        offsets = solver.update(resources, *log[-1])     # more than STEP_HISTORY ticks later
        gl.glFinish()
        data = np.empty(offsets['_total'] * 4, dtype=np.float32)
        gl.glGetNamedBufferSubData(solver.output, 0, data.nbytes, data)
        assert np.isfinite(data).all()
        assert all(state.serial == int(np.frombuffer(log[-1][1][-8 * 24:], dtype=np.float64)[0])
                   for state in solver._families.values())
    finally:
        solver.release()
        resources.release_resources()
        target.close()
