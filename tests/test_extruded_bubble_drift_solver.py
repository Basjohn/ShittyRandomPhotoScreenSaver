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


def _counted_deletes(monkeypatch, module):
    deleted = []
    original = module._delete
    monkeypatch.setattr(module, '_delete', lambda *names: (deleted.extend(n for n in names if n), original(*names)))
    return deleted


def test_a_carried_history_whose_target_allocation_fails_stays_drawn_and_is_released_once(qt_app, monkeypatch, caplog):
    """A display move (1C.2) hands the drift history to another window's solver; the target's next allocation (a new
    key) fails: the carried state stays current and drawn, the failure is logged once, and every carried name is
    released exactly once with the target."""
    from OpenGL import GL as gl
    from rendering.quick.scene3d.resources import MeshResources
    from rendering.quick.visualizer.implementations import extruded_bubble_drift_solver as module
    from tools.labs.render_target import OffscreenRenderTarget
    first, second = (list(_log(_controls('wander'), 30, seed=seed)) for seed in (11, 12))
    target_gl, resources = OffscreenRenderTarget(16, 16), MeshResources('drift carryover test')
    source, target = module.DriftSolver('source'), module.DriftSolver('target')
    try:
        offsets = source.update(resources, *first[-1])
        before = _read_output(source, offsets['_total'])
        carryover = source.export()
        carried = dict(carryover.families)
        names = [name for state in carried.values() for name in (state.geometry, state.state, state.aux)]
        names.append(carryover.output)
        target.check(resources)
        target.adopt(carryover)
        deleted = _counted_deletes(monkeypatch, module)
        attempts = []

        def refuse(size):
            attempts.append(size)
            raise RuntimeError('injected allocation failure')
        monkeypatch.setattr(module, '_buffer', refuse)
        with caplog.at_level('ERROR'):
            for frame in second[-3:]:
                target.update(resources, *frame)
        assert all(target._families[name] is state for name, state in carried.items())
        assert all(gl.glIsBuffer(name) for name in names) and not deleted
        assert np.array_equal(_read_output(target, offsets['_total']), before)
        assert len(attempts) == len(carried)
        assert len([r for r in caplog.records if 'could not be allocated' in r.getMessage()]) == len(carried)
        target.release()
        source.release()
        assert sorted(deleted) == sorted(names)                     # each carried name released exactly once
        assert not any(gl.glIsBuffer(name) for name in names)
    finally:
        monkeypatch.undo()
        source.release()
        target.release()
        resources.release_resources()
        target_gl.close()


def test_a_handoff_whose_wait_fails_releases_the_carried_history_once_and_keeps_the_targets_own(qt_app, monkeypatch):
    from OpenGL import GL as gl
    from rendering.quick.scene3d.resources import MeshResources
    from rendering.quick.visualizer.implementations import extruded_bubble_drift_solver as module
    from tools.labs.render_target import OffscreenRenderTarget
    first, second = (list(_log(_controls('wander'), 30, seed=seed)) for seed in (11, 12))
    target_gl, resources = OffscreenRenderTarget(16, 16), MeshResources('drift handoff wait test')
    source, target = module.DriftSolver('source'), module.DriftSolver('target')
    try:
        source.update(resources, *first[-1])
        target.update(resources, *second[-1])
        own = dict(target._families)
        own_output = target.output
        carryover = source.export()
        carried = [name for state in carryover.families.values() for name in (state.geometry, state.state, state.aux)]
        carried.append(carryover.output)
        deleted = _counted_deletes(monkeypatch, module)

        def broken_wait(*args):
            raise RuntimeError('injected wait failure')
        monkeypatch.setattr(module.gl, 'glWaitSync', broken_wait)
        with pytest.raises(RuntimeError, match='injected'):
            target.adopt(carryover)
        assert sorted(deleted) == sorted(carried) and carryover.fence is None and not carryover.families
        assert target._families == own and target.output == own_output
        assert all(gl.glIsBuffer(state.geometry) for state in own.values())
        carryover.discard()                                         # a second discard deletes nothing again
        assert sorted(deleted) == sorted(carried)
    finally:
        monkeypatch.undo()
        source.release()
        target.release()
        resources.release_resources()
        target_gl.close()


def test_an_output_that_cannot_be_allocated_draws_without_drift_and_is_not_retried(qt_app, monkeypatch, caplog):
    from rendering.quick.scene3d.resources import MeshResources
    from rendering.quick.visualizer.implementations import extruded_bubble_drift_solver as module
    from tools.labs.render_target import OffscreenRenderTarget
    log = list(_log(_controls('wander'), 30))
    target_gl, resources, solver = OffscreenRenderTarget(16, 16), MeshResources('drift output test'), \
        module.DriftSolver('output')
    try:
        solver.check(resources)
        attempts = []

        def refuse(size):
            attempts.append(size)
            raise RuntimeError('injected allocation failure')
        monkeypatch.setattr(module, '_buffer', refuse)
        with caplog.at_level('ERROR'):
            for frame in log[-3:]:
                solver.update(resources, *frame)
        assert solver.output == 0 and not solver._families and len(attempts) == 1
        assert len([r for r in caplog.records if 'drift output' in r.getMessage()]) == 1
    finally:
        monkeypatch.undo()
        solver.release()
        resources.release_resources()
        target_gl.close()


def test_a_dispatch_that_raises_at_a_geometry_edit_leaks_no_buffer(qt_app, monkeypatch):
    """The geometry edit continues the old rows onto the new geometry; a raise inside that dispatch still releases
    the old rows (counted: every buffer the solver created is gone after its release)."""
    from OpenGL import GL as gl
    from rendering.quick.scene3d.resources import MeshResources
    from rendering.quick.visualizer.implementations import extruded_bubble_drift_solver as module
    from tools.labs.render_target import OffscreenRenderTarget
    log = _log(_controls('swirl_cw'), 160, edit_at=120)
    created, injected = [], []
    original_buffer, original_dispatch = module._buffer, module.DriftSolver._dispatch
    monkeypatch.setattr(module, '_buffer', lambda size: created.append(original_buffer(size)) or created[-1])

    def dispatch(self, *args, old_geometry=0, **kwargs):
        if old_geometry:
            injected.append(old_geometry)
            raise RuntimeError('injected dispatch failure')
        return original_dispatch(self, *args, old_geometry=old_geometry, **kwargs)
    monkeypatch.setattr(module.DriftSolver, '_dispatch', dispatch)
    target, resources, solver = OffscreenRenderTarget(16, 16), MeshResources('drift edit leak test'), \
        module.DriftSolver('edit leak')
    try:
        for families, steps, knots in log:
            if not families:
                continue
            try:
                solver.update(resources, families, steps, knots)
            except RuntimeError as exc:
                assert 'injected' in str(exc)
                break
        assert injected, 'the geometry edit never dispatched onto the new rows'
        gl.glFinish()
        solver.release()
        assert not solver.has_resources
        assert [name for name in created if gl.glIsBuffer(name)] == []
    finally:
        solver.release()
        resources.release_resources()
        target.close()


def _session_frames(namespace, settings):
    """Every drifting frame one production engine session publishes (its own label namespace, as each configure
    takes one), read through the frame packet ABI as the owner reads them."""
    import tools.expanded_visualizer_evidence as evidence
    from core.visualizer_engine.engine_worker import EngineSession
    from core.visualizer_engine.packet_mailbox import PacketMailbox
    from core.visualizer_engine.frame_capacity import required_slot_bytes
    reader = PacketMailbox(role='reader', slot_bytes=required_slot_bytes('extruded_bubble', settings))
    session = EngineSession(mapping=reader.mapping_name, mode='extruded_bubble', runtime_generation=1,
                            label_namespace=namespace, settings=settings)
    frames = []
    try:
        for feature in evidence.shipped_clip(1.0).frames:
            session.tick(feature)
            state = reader.take().state.mode_state
            if state.drift_families:
                frames.append((state.drift_families, state.drift_steps, state.drift_knots))
    finally:
        session.close()
        reader.close()
    return frames


@pytest.mark.qt
def test_a_replacement_stream_never_presents_an_alias_of_the_old_streams_geometry(qt_app, monkeypatch):
    """D3's identity test against this solver, which keys a family's state on its revision: a worker and its
    replacement (two sessions, each in a fresh process as far as the revision counter goes) publish different geometry;
    after the replacement's frames the uploaded geometry is the replacement's, byte for byte (hashed)."""
    import hashlib
    from OpenGL import GL as gl
    from rendering.quick.scene3d.resources import MeshResources
    from rendering.quick.visualizer.implementations.extruded_bubble_drift_solver import DriftSolver
    from tools.labs.render_target import OffscreenRenderTarget
    from widgets.spotify_visualizer import extruded_bubble_drift_log
    monkeypatch.setattr(extruded_bubble_drift_log, '_REVISIONS', extruded_bubble_drift_log._REVISIONS)  # restored
    from widgets.spotify_visualizer.engine_worker_link import next_label_namespace
    from tests._visualizer_frozen_settings import frozen_visualizer_settings
    settings = {**frozen_visualizer_settings('extruded_bubble'), 'extruded_bubble_drift': [.6, 1.],
                **{f'extruded_bubble_drift_{name}': [1., 1.] for name in ('chains', 'snow', 'specks')}}
    # The replacement runs with an edited spread, so its seeded geometry differs from the first stream's.
    spread = float(settings['extruded_bubble_particle_spread'])
    edited = {**settings, 'extruded_bubble_particle_spread': spread * 0.8 if spread > 0.5 else spread + 0.4}
    worker, replacement = (_session_frames(next_label_namespace(), values) for values in (settings, edited))
    assert worker and replacement
    old = {family.family: hashlib.sha256(family.geometry).hexdigest() for family in worker[-1][0]}
    new = {family.family: hashlib.sha256(family.geometry).hexdigest() for family in replacement[-1][0]}
    assert set(old) == set(new) and all(old[name] != new[name] for name in new)   # the streams differ
    target, resources, solver = OffscreenRenderTarget(16, 16), MeshResources('drift identity test'), \
        DriftSolver('identity')
    try:
        solver.update(resources, *worker[-1])
        for frame in replacement:
            solver.update(resources, *frame)
        gl.glFinish()
        uploaded = {}
        for name, state in solver._families.items():
            size = len(next(f.geometry for f in replacement[-1][0] if f.family == name))
            data = np.empty(size, dtype=np.uint8)
            gl.glGetNamedBufferSubData(state.geometry, 0, size, data)
            uploaded[name] = hashlib.sha256(data.tobytes()).hexdigest()
        assert uploaded == new
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
