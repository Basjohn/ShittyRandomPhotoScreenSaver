"""The GPU drift solver integrates the logical step log like the CPU reference (MaterialPaths/ProceduralOffsets).

Test-owned controls only; the comparison reads the solver's output back, which production never does.
"""
from dataclasses import replace

import numpy as np
import pytest

from widgets.spotify_visualizer.extruded_bubble_drift import DRIFT_DIRECTIONS
from widgets.spotify_visualizer.extruded_bubble_drift_log import (
    KNOT_DECISION, STEP_FLOATS, STEP_HISTORY, MaterialDriftReference, newest_knots,
)
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
        yield state.drift_families, state.drift_steps, state.drift_knots


def run_solvers(log, every, solvers):
    """Feed one log to each solver (label -> solver) and to the CPU reference, reading each output back.

    Per solver: the worst displacement difference (relative to the reference's largest), the worst fourth-channel
    difference (shift, phase offset or progress) and the motes whose packed progress sits a whole wrap from the
    reference's (a recycle on another tick). Also how many published knot decisions equal the reference's."""
    from OpenGL import GL as gl
    from rendering.quick.scene3d.resources import MeshResources
    from tools.labs.render_target import OffscreenRenderTarget
    target, resources = OffscreenRenderTarget(16, 16), MeshResources('drift solver test')
    reference, frames, moved = MaterialDriftReference(), 0, [0, 0]
    results = {label: {'worst': {}, 'absolute': {}, 'channel': {}, 'wraps': 0} for label in solvers}
    try:
        for index, (families, steps, knots) in enumerate(log):
            if index % every or not families:
                continue
            payload = reference.apply(families, steps)
            if 'chains' in payload and reference._state['chains'][1].clock.moved is not None:
                published = np.frombuffer(newest_knots(steps, knots)[1], dtype=KNOT_DECISION)['moved']
                moved[0] += int(np.array_equal(published, reference._state['chains'][1].clock.moved))
                moved[1] += 1
            for label, solver in solvers.items():
                offsets = (solver.update(resources, families, steps, knots) if isinstance(solver, _new_solver())
                           else solver.update(resources, families, steps))
                gl.glFinish()
                data = np.empty(offsets['_total'] * 4, dtype=np.float32)
                gl.glGetNamedBufferSubData(solver.output, 0, data.nbytes, data)
                data = data.reshape(-1, 4)
                result = results[label]
                for family in families:
                    expected = np.frombuffer(payload[family.family], dtype=np.float32).reshape(-1, 4)
                    got = data[offsets[family.family]:offsets[family.family] + len(expected)]
                    scale = max(1.0, float(np.abs(expected[:, :3]).max(initial=0.)))
                    name = family.family
                    channel = np.abs(got[:, 3] - expected[:, 3])
                    # Motes a whole wrap away (recycled on another tick) are counted below, not measured here.
                    absolute = float(np.abs(got[:, :3] - expected[:, :3])[channel <= .5].max(initial=0.))
                    result['absolute'][name] = max(result['absolute'].get(name, 0.), absolute)
                    result['worst'][name] = max(result['worst'].get(name, 0.),
                                                float(np.abs(got[:, :3] - expected[:, :3]).max(initial=0.)) / scale)
                    result['channel'][name] = max(result['channel'].get(name, 0.), float(channel.max(initial=0.)))
                    result['wraps'] += int((channel > .5).sum())
            frames += 1
    finally:
        for solver in solvers.values():
            solver.release()
        resources.release_resources()
        target.close()
    return frames, results, moved


def _new_solver():
    from rendering.quick.visualizer.implementations.extruded_bubble_drift_solver import DriftSolver
    return DriftSolver


def _compare(log, every):
    frames, results, _moved = run_solvers(log, every, {'new': _new_solver()('test')})
    # The fourth channel (shift, phase offset, progress) to the existing bound on every family.
    assert max(results['new']['channel'].values()) < 1e-4, results['new']['channel']
    return frames, results['new']['worst']


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
        assert all(state.serial == int(np.frombuffer(log[-1][1][-8 * STEP_FLOATS:], dtype=np.float64)[0])
                   for state in solver._families.values())
    finally:
        solver.release()
        resources.release_resources()
        target.close()


def test_a_frame_with_no_new_step_dispatches_and_uploads_nothing_and_the_ring_follows_the_chain_rows(
        qt_app, monkeypatch):
    from OpenGL import GL as gl
    from rendering.quick.scene3d.resources import MeshResources
    from rendering.quick.visualizer.implementations import extruded_bubble_drift_solver as module
    from tools.labs.render_target import OffscreenRenderTarget
    from widgets.spotify_visualizer.extruded_bubble_drift_log import STEP_INDEX, unpack_steps
    log = list(_log(replace(_controls('wander'), bead_chains=(1., 1.5)), 40))
    grown = list(_log(replace(_controls('wander'), bead_chains=(3., 4.)), 40))
    calls = []
    for name in ('glDispatchCompute', 'glBindBuffersRange'):
        original = getattr(module.gl, name)
        monkeypatch.setattr(module.gl, name, lambda *args, _o=original, _n=name: (calls.append(_n), _o(*args))[1])
    monkeypatch.setattr(module.StreamRing, 'rebind', lambda self, *args, _o=module.StreamRing.rebind:
                        (calls.append('ring write'), _o(self, *args))[1])
    target, resources, solver = OffscreenRenderTarget(16, 16), MeshResources('drift rest test'), module.DriftSolver('rest')
    try:
        solver.update(resources, *log[-2])
        assert 'glDispatchCompute' in calls and 'ring write' in calls      # the counters see real work
        calls.clear()
        solver.update(resources, *log[-2])                                # the same frame again: no new step
        assert calls == []
        rows = int(unpack_steps(log[-2][1])[:, STEP_INDEX['chain_rows']].max())
        assert solver._ring.hold_bytes == module.hold_bytes(rows)
        solver.update(resources, *grown[-1])                              # more chains: the ring grows once
        more = int(unpack_steps(grown[-1][1])[:, STEP_INDEX['chain_rows']].max())
        assert more > rows and solver._ring.hold_bytes == module.hold_bytes(more)
        gl.glFinish()
    finally:
        solver.release()
        resources.release_resources()
        target.close()


def test_the_pair_check_runs_once_and_reports_a_compiler_that_breaks_the_pairs(qt_app, monkeypatch, caplog):
    from OpenGL import GL as gl
    from rendering.quick.scene3d.resources import MeshResources
    from rendering.quick.visualizer.implementations import extruded_bubble_drift_solver as module
    from tools.labs.render_target import OffscreenRenderTarget
    target = OffscreenRenderTarget(16, 16)
    resources, solver = MeshResources('pair check test'), module.DriftSolver('check')
    broken_resources, broken = MeshResources('broken pair check test'), module.DriftSolver('broken')
    try:
        assert solver.check(resources) is False and solver.pairs_exact is True, solver.pairs_report
        assert solver.pairs_report == {'fraction_error': solver.pairs_report['fraction_error'],
                                       'product_mismatches': 0, 'sum_mismatches': 0}
        dispatches = []
        monkeypatch.setattr(module.gl, 'glDispatchCompute', lambda *args: dispatches.append(args))
        assert solver.check(resources) is True and not dispatches     # done once, never again
        monkeypatch.undo()
        # What a compiler that ignores ``precise`` may do: reassociate the error terms away (and plain products).
        name, source = module.PROGRAMS[2]
        source = (source.replace("precise float e = (a - (s - v)) + (b - v);", "precise float e = 0.0;")
                  .replace("precise float e = ((x.x * y.x - p) + x.x * y.y + x.y * y.x) + x.y * y.y;",
                           "precise float e = 0.0;"))
        assert source != module.PROGRAMS[2][1]
        monkeypatch.setattr(module, 'PROGRAMS', (*module.PROGRAMS[:2], (name, source)))
        with caplog.at_level('ERROR'):
            broken.check(broken_resources)
        assert broken.pairs_exact is False
        assert broken.pairs_report['sum_mismatches'] and broken.pairs_report['product_mismatches']
        assert broken.pairs_report['fraction_error'] > 1e-6
        assert 'does not keep the drift solver' in caplog.text
        gl.glFinish()
    finally:
        solver.release()
        broken.release()
        resources.release_resources()
        broken_resources.release_resources()
        target.close()


def _read_output(solver, vec4s):
    from OpenGL import GL as gl
    gl.glFinish()
    data = np.empty(vec4s * 4, dtype=np.float32)
    gl.glGetNamedBufferSubData(solver.output, 0, data.nbytes, data)
    return data


def test_a_failed_allocation_keeps_the_current_state_drawn_logs_once_and_retries_only_a_new_key(
        qt_app, monkeypatch, caplog):
    """D3, failed swap: the new state is allocated before the old is released. An allocation that fails leaves the
    current buffers alive, current and unchanged (the draws keep reading them), is logged once and is not retried on
    later frames for the same (revision, capacity); a new key is tried."""
    from OpenGL import GL as gl
    from rendering.quick.scene3d.resources import MeshResources
    from rendering.quick.visualizer.implementations import extruded_bubble_drift_solver as module
    from tools.labs.render_target import OffscreenRenderTarget
    first, second, third = (list(_log(_controls('wander'), 30, seed=seed)) for seed in (11, 12, 13))
    target, resources = OffscreenRenderTarget(16, 16), MeshResources('drift failed swap test')
    solver = module.DriftSolver('failed swap')
    try:
        offsets = solver.update(resources, *first[-1])
        held = dict(solver._families)
        assert set(held) == {'chains', 'snow', 'specks'}
        before = _read_output(solver, offsets['_total'])
        # The second stream's revisions are new keys for every family (the revision-change edge).
        assert not {family.revision for family in second[-1][0]} & {state.revision for state in held.values()}
        attempts = []

        def refuse(size):
            attempts.append(size)
            raise RuntimeError('injected allocation failure')
        monkeypatch.setattr(module, '_buffer', refuse)
        with caplog.at_level('ERROR'):
            for frame in second[-4:]:
                solver.update(resources, *frame)
        monkeypatch.undo()
        assert all(solver._families[name] is state for name, state in held.items())
        assert all(gl.glIsBuffer(name) for state in held.values() for name in (state.geometry, state.state, state.aux))
        assert np.array_equal(_read_output(solver, offsets['_total']), before)          # drawn, unchanged
        failures = [record for record in caplog.records if 'could not be allocated' in record.getMessage()]
        assert len(failures) == len(held) and len(attempts) == len(held), (failures, attempts)   # once per key
        caplog.clear()
        solver.update(resources, *third[-1])                                  # new keys: tried, and they succeed
        assert {name: state.revision for name, state in solver._families.items()} == \
            {family.family: family.revision for family in third[-1][0]}
        current = {name for state in solver._families.values() for name in (state.geometry, state.state, state.aux)}
        assert all(not gl.glIsBuffer(name) or name in current         # the old released once replaced (GL may
                   for state in held.values() for name in (state.geometry, state.state, state.aux))  # reuse a name)
        assert not solver._failed and 'could not be allocated' not in caplog.text
    finally:
        solver.release()
        resources.release_resources()
        target.close()


def test_no_compute_program_declares_a_64_bit_float():
    import re
    from rendering.quick.visualizer.implementations.extruded_bubble_drift_solver import PROGRAMS
    for _name, source in PROGRAMS:
        assert not re.search(r"\b(double|dvec[234]|dmat[234]|uint64_t|int64_t)\b|\d(LF|lf)\b", source), _name


@pytest.mark.parametrize('start', ('hour', 'eight_hours'))
@pytest.mark.parametrize('kind', ('swish_across', 'swirl_cw'))
def test_solver_matches_the_reference_at_long_horizon_with_tick_exact_chains(qt_app, kind, start):
    """Runs that start at an hour's and eight hours' travel and motion phase, every tick compared, across a
    geometry edit and a chain-count change: the published knot decisions equal the reference's on every tick, and
    the solver (no 64-bit float) stays within the existing bound with no mote recycling on another tick."""
    from tests.test_extruded_bubble_drift_precision import EIGHT_HOURS, HOUR, long_log
    log = long_log(kind, 160, HOUR if start == 'hour' else EIGHT_HOURS, edit_at=80, resize_at=120,
                   emission=(.15, .3))
    frames, results, moved = run_solvers(log, 1, {'new': _new_solver()('long')})
    result = results['new']
    assert frames > 150 and set(result['worst']) == {'chains', 'snow', 'specks'}
    assert moved[1] > 150 and moved[0] == moved[1]
    assert result['wraps'] == 0
    assert max(result['worst'].values()) < 1e-4, result['worst']
    assert max(result['channel'].values()) < 1e-4, result['channel']
