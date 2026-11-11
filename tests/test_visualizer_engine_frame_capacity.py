"""Activation-time admission covers the canonical bounded frame, before a writer can overflow."""
import pytest


def test_extruded_bubble_capacity_covers_full_geometry_and_dormant_modes_stay_small():
    from core.visualizer_engine.frame_capacity import required_slot_bytes
    from core.visualizer_engine.packet_mailbox import DEFAULT_SLOT_BYTES
    from core.visualizer_engine.packet_abi import SLOT_OVERHEAD
    from core.constants.extruded_bubble_world import SPECKS_FULL, SNOW_FULL
    from widgets.spotify_visualizer.extruded_bubble_drift_log import (
        CLOUD_GEOMETRY_BYTES, CHAIN_GEOMETRY_BYTES, KNOT_DECISION_BYTES, STEP_HISTORY,
    )
    from widgets.spotify_visualizer.extruded_bubble_material_paths import CHAIN_PATHS

    controls = {'extruded_bubble_drift': [.2, .8], 'extruded_bubble_drift_chains': [.4, 1.],
                'extruded_bubble_drift_snow': [.2, .7], 'extruded_bubble_drift_specks': [-.4, .9],
                'extruded_bubble_particles': [.1, .35], 'extruded_bubble_bead_chains': [20., 20.]}
    size = required_slot_bytes('extruded_bubble', controls)
    assert size % 16 == 0
    geometry = ((SPECKS_FULL+SNOW_FULL)*CLOUD_GEOMETRY_BYTES
                + CHAIN_PATHS*(CHAIN_GEOMETRY_BYTES+STEP_HISTORY*KNOT_DECISION_BYTES))
    assert size-SLOT_OVERHEAD >= geometry+DEFAULT_SLOT_BYTES-SLOT_OVERHEAD
    # Endpoint-only sizing would under-admit musical overshoot. Any active cloud reserves its full canonical cap.
    assert required_slot_bytes('extruded_bubble', {**controls, 'extruded_bubble_particles': [.01, .02]}) == size
    dormant = {**controls, 'extruded_bubble_drift': [0., 0.]}
    assert required_slot_bytes('extruded_bubble', dormant) == DEFAULT_SLOT_BYTES
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
    for mode in iter_all_visualizer_mode_descriptors():
        if mode.mode_id != 'extruded_bubble':
            assert required_slot_bytes(mode.mode_id, {}) == DEFAULT_SLOT_BYTES
    with pytest.raises((KeyError, ValueError)):
        required_slot_bytes('extruded_bubble', {})


def test_mapping_grows_only_on_acknowledged_identity_and_preserves_packet_bytes():
    from core.visualizer_engine.packet_mailbox import PacketMailbox
    from core.visualizer_engine import frame_codec
    from multiprocessing.shared_memory import SharedMemory

    reader = PacketMailbox(role='reader', slot_bytes=65536)
    writer = PacketMailbox(role='writer', attach=reader.mapping_name)
    old = reader.mapping_name
    try:
        change = reader.stage_capacity(131072)
        assert change['previous_mapping'] == old and change['mapping'] != old
        assert reader.mapping_name == old
        with pytest.raises(ValueError):
            reader.commit_capacity({**change, 'previous_mapping': 'stale'})
        writer.attach_capacity(change)
        value = b'geometry\x00\xff'*10000
        writer.publish(value, generation=7, activation_id=9, now_ts=12.)
        reader.commit_capacity(change)
        assert reader.mapping_name == writer.mapping_name == change['mapping']
        from core.visualizer_engine.packet_abi import FramePacketReader
        inspection = FramePacketReader(reader._memory.buf)
        try:
            packet = inspection.read_latest()
        finally:
            inspection.release()
        assert packet.runtime_generation == 7 and packet.activation_id == 9
        assert packet.payload == frame_codec.encode((7, 9, 12., value))
        assert reader.take().state == value
        assert reader.stage_capacity(65536) is None
        with pytest.raises(FileNotFoundError):
            SharedMemory(name=old)
    finally:
        writer.close()
        reader.close()


def test_staged_mapping_is_released_on_abort_or_retirement():
    from core.visualizer_engine.packet_mailbox import PacketMailbox
    from multiprocessing.shared_memory import SharedMemory

    reader = PacketMailbox(role='reader', slot_bytes=65536)
    try:
        change = reader.stage_capacity(131072)
        reader.abort_capacity(change)
        assert reader.mapping_name == change['previous_mapping']
        with pytest.raises(FileNotFoundError):
            SharedMemory(name=change['mapping'])
        change = reader.stage_capacity(131072)
    finally:
        reader.close()
    with pytest.raises(FileNotFoundError):
        SharedMemory(name=change['mapping'])


def test_capacity_commit_waits_for_existing_reader_lock_and_refuses_stale_writer():
    import threading
    from core.visualizer_engine.packet_mailbox import PacketMailbox

    reader = PacketMailbox(role='reader', slot_bytes=1024)
    writer = PacketMailbox(role='writer', attach=reader.mapping_name)
    change = reader.stage_capacity(2048)
    begun, done = threading.Event(), threading.Event()

    def commit():
        begun.set()
        reader.commit_capacity(change)
        done.set()

    thread = threading.Thread(target=commit)
    try:
        with pytest.raises(ValueError):
            writer.attach_capacity({**change, 'previous_mapping': 'retired'})
        writer.attach_capacity(change)
        with reader._lock:
            thread.start()
            assert begun.wait(1.)
            assert not done.wait(.02)
            assert reader.mapping_name == change['previous_mapping']
        assert done.wait(1.)
    finally:
        thread.join(1.)
        writer.close()
        reader.close()


def test_failed_allocation_and_mismatched_ack_never_adopt_a_mapping(monkeypatch):
    from core.visualizer_engine.packet_mailbox import PacketMailbox
    from widgets.spotify_visualizer.engine_worker_link import EngineWorkerLink
    from widgets.spotify_visualizer.feature_replay import offline_activation_request
    from multiprocessing.shared_memory import SharedMemory
    import core.visualizer_engine.packet_mailbox as module

    reader = PacketMailbox(role='reader')
    old = reader.mapping_name
    create = module.create_frame_mapping
    try:
        def refused(**kwargs):
            raise OSError('allocation refused')

        monkeypatch.setattr(module, 'create_frame_mapping', refused)
        with pytest.raises(OSError, match='allocation refused'):
            reader.stage_capacity(2*reader.slot_bytes)
        assert reader.mapping_name == old and reader._staged_memory is None
        monkeypatch.setattr(module, 'create_frame_mapping', create)
        link = object.__new__(EngineWorkerLink)
        link._mailbox, link.mapping_name = reader, old
        failed, committed, sent = [], [], []

        def reply_with_stale_mapping(message, payload, *, on_reply, on_failed):
            sent.append(payload)
            on_reply({'mapping': old, 'engine_generation': 2, 'activation_id': 4})

        link._send = reply_with_stale_mapping
        activation = offline_activation_request('extruded_bubble', 0, None, _settings('extruded_bubble', True))
        link.set_mode('extruded_bubble', activation, on_committed=lambda *a: committed.append(a),
                      on_failed=failed.append)
        assert failed and not committed and reader.mapping_name == old and reader._staged_memory is None
        with pytest.raises(FileNotFoundError):
            SharedMemory(name=sent[0]['capacity_change']['mapping'])
    finally:
        reader.close()


def test_refused_wake_pipe_never_allocates_a_mapping(monkeypatch):
    import multiprocessing
    import core.visualizer_engine.packet_mailbox as module
    from widgets.spotify_visualizer.engine_worker_link import EngineWorkerLink
    from widgets.spotify_visualizer.feature_replay import offline_activation_request

    allocated = []

    def refused(*args, **kwargs):
        raise OSError('wake pipe refused')

    monkeypatch.setattr(multiprocessing, 'Pipe', refused)
    monkeypatch.setattr(module, 'PacketMailbox', lambda **kwargs: allocated.append(kwargs))
    link = object.__new__(EngineWorkerLink)
    with pytest.raises(OSError, match='wake pipe refused'):
        link.configure(runtime_generation=1, mode='spectrum', bar_count=32,
                       activation=offline_activation_request('spectrum', 0, None, _settings('spectrum', False)),
                       on_configured=lambda identity: None)
    assert not allocated


def test_oversized_packet_records_atomic_failure_before_any_slot_changes():
    from core.visualizer_engine.packet_abi import FrameCapacityError
    from core.visualizer_engine.packet_mailbox import PacketMailbox

    reader = PacketMailbox(role='reader', slot_bytes=1024)
    writer = PacketMailbox(role='writer', attach=reader.mapping_name)
    try:
        writer.publish(b'fits', generation=1)
        with pytest.raises(FrameCapacityError):
            writer.publish(b'x'*2048, generation=1)
        report = reader.capacity_failure
        assert report['actual_bytes'] > report['capacity_bytes']
        assert reader.take().state == b'fits'
        change = reader.stage_capacity(4096)
        writer.attach_capacity(change)
        with pytest.raises(FrameCapacityError):
            writer.publish(b'x'*8192, generation=2)
        # A new writer can fail before its ack reaches the GUI; EOF must still expose the candidate's report.
        assert reader.mapping_name == change['previous_mapping']
        assert reader.capacity_failure['actual_bytes'] > 8192
        assert reader.capacity_failure['capacity_bytes'] == writer._writer.capacity
    finally:
        writer.close()
        reader.close()


def _settings(mode, maximum):
    from tests._visualizer_frozen_settings import frozen_visualizer_settings
    from core.settings.visualizer_mode_settings import require_mode_settings, Slider, Range, Choice, Toggle

    result = frozen_visualizer_settings(mode)
    for control in require_mode_settings(mode).controls:
        if isinstance(control, (Slider, Range)):
            high = getattr(control, 'admission_high', None)
            high = control.high if high is None else high
            low = getattr(control, 'admission_low', None)
            low = control.low if low is None else low
            value = high if maximum else low+(high-low)*.37
            if control.integer:
                value = round(value)
            result[control.key] = [value, value] if isinstance(control, Range) else value
        elif isinstance(control, Choice):
            index = len(control.choices)-1 if maximum else min(1, len(control.choices)-1)
            result[control.key] = index if control.indexed else control.choices[index]
        elif isinstance(control, Toggle):
            result[control.key] = True
    return result


def _modes():
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
    return tuple(mode.mode_id for mode in iter_all_visualizer_mode_descriptors())


@pytest.mark.qt
@pytest.mark.parametrize('mode', _modes())
@pytest.mark.parametrize('maximum', (False, True), ids=('nondefault', 'schema_max'))
def test_every_mode_fits_at_nondefault_and_schema_maximum(qt_app, monkeypatch, mode, maximum):
    from core.visualizer_engine.frame_capacity import required_slot_bytes
    from core.visualizer_engine.packet_mailbox import PacketMailbox
    import tools.expanded_visualizer_evidence as evidence
    from widgets.spotify_visualizer.feature_replay import offline_activation_request

    settings = _settings(mode, maximum)
    activation = offline_activation_request(mode, 0, None, settings)
    mailbox = PacketMailbox(slot_bytes=required_slot_bytes(mode, activation['logical_kwargs']))
    digest, seen = evidence.frame_digest, []

    def checked(frame):
        mailbox.publish(frame, generation=frame.runtime_generation, activation_id=frame.activation_id)
        back = mailbox.take().state
        assert digest(back) == digest(frame)
        seen.append(frame)
        return digest(frame)

    monkeypatch.setattr(evidence, 'frame_digest', checked)
    try:
        evidence.owner_replay(evidence.shipped_clip(.15), mode, settings=settings)
        assert seen
    finally:
        mailbox.close()


@pytest.mark.qt
def test_full_extruded_bubble_geometry_step_wake_and_body_frame_reproduces_old_overflow(qt_app, monkeypatch):
    from dataclasses import replace
    from core.visualizer_engine.frame_capacity import required_slot_bytes
    from core.visualizer_engine.packet_mailbox import PacketMailbox
    from core.visualizer_engine.packet_abi import FrameCapacityError
    from core.visualizer_engine import frame_codec
    from core.constants.extruded_bubble_world import SPECKS_FULL, SNOW_FULL, WAKE_STRIDE
    import numpy as np
    from widgets.spotify_visualizer.extruded_bubble_drift_log import (
        DriftFamily, CHAIN_GEOMETRY_BYTES, CLOUD_GEOMETRY_BYTES, KNOT_DECISION_BYTES, STEP_HISTORY, STEP_FLOATS,
        STEP_INDEX,
    )
    from widgets.spotify_visualizer.extruded_bubble_material_paths import CHAIN_PATHS
    from widgets.spotify_visualizer.extruded_bubble_simulation import MAX_BUBBLES, BUBBLE_STRIDE, CLUSTER_STRIDE
    from widgets.spotify_visualizer.feature_replay import offline_activation_request
    import tools.expanded_visualizer_evidence as evidence

    settings = _settings('extruded_bubble', True)
    activation = offline_activation_request('extruded_bubble', 0, None, settings)
    original = evidence.frame_digest
    frames = []

    def captured(frame):
        frames.append(frame)
        return original(frame)

    monkeypatch.setattr(evidence, 'frame_digest', captured)
    evidence.owner_replay(evidence.shipped_clip(.03), 'extruded_bubble', settings=settings)
    frame = frames[-1]
    families = tuple(DriftFamily(name, index, 0, 1, count, b'\0'*(count*stride))
                     for index, (name, count, stride) in enumerate((
                         ('chains', CHAIN_PATHS, CHAIN_GEOMETRY_BYTES),
                         ('snow', SNOW_FULL, CLOUD_GEOMETRY_BYTES),
                         ('specks', SPECKS_FULL, CLOUD_GEOMETRY_BYTES)), 1))
    # A full history in which every step moves every chain: its knot decisions ride beside the steps.
    steps = np.zeros((STEP_HISTORY, STEP_FLOATS))
    steps[:, STEP_INDEX['chain_rows']] = CHAIN_PATHS
    full = replace(frame, mode_state=replace(frame.mode_state, drift_families=families,
                   drift_steps=steps.tobytes(), drift_knots=b'\0'*(STEP_HISTORY*CHAIN_PATHS*KNOT_DECISION_BYTES),
                   wakes=b'\0'*(2*MAX_BUBBLES*WAKE_STRIDE*4), bubbles=(0.,)*(MAX_BUBBLES*BUBBLE_STRIDE),
                   clusters=(0.,)*((MAX_BUBBLES//2)*CLUSTER_STRIDE)))
    old = PacketMailbox()
    admitted = PacketMailbox(slot_bytes=required_slot_bytes('extruded_bubble', activation['logical_kwargs']))
    try:
        with pytest.raises(FrameCapacityError):
            old.publish(full, generation=full.runtime_generation, activation_id=full.activation_id)
        admitted.publish(full, generation=full.runtime_generation, activation_id=full.activation_id)
        back = admitted.take().state
        assert frame_codec.encode(back) == frame_codec.encode(full)
    finally:
        old.close()
        admitted.close()


@pytest.mark.qt
@pytest.mark.parametrize('initial_mode', ('spectrum', 'extruded_bubble'), ids=('mode_change', 'settings_change'))
def test_real_hidden_activation_joins_writer_before_remapping_and_keeps_one_mailbox_and_wake(
        qt_app, monkeypatch, initial_mode):
    from core.visualizer_engine.packet_mailbox import PacketMailbox
    from core.visualizer_engine.frame_capacity import required_slot_bytes
    from widgets.spotify_visualizer import engine_worker_link
    from widgets.spotify_visualizer.feature_replay import offline_activation_request
    from tools.visualizer_replay.live_engine_gate import paced_pcm
    from tests.test_visualizer_owner_engine_worker import _InProcessSupervisor, _pump
    from tools.visualizer_replay import owner_worker_gate as gate
    from multiprocessing.shared_memory import SharedMemory

    supervisor = _InProcessSupervisor()
    clock = [0.]
    rig = gate.OwnerRig(initial_mode, worker=True, supervisor=supervisor, cadence='thread', clock=clock,
                        extra_modes=('extruded_bubble',))
    if initial_mode == 'extruded_bubble':
        from core.settings.visualizer_presets import get_custom_preset_index
        rig.widgets['spotify_visualizer'].update({key: value for key, value in _settings(initial_mode, False).items()
                                                 if key.startswith('extruded_bubble_')})
        rig.widgets['spotify_visualizer'].update(
            preset_extruded_bubble=get_custom_preset_index(initial_mode), extruded_bubble_drift=[0., 0.])
    attach, joined = PacketMailbox.attach_capacity, []

    def after_join(mailbox, change):
        assert supervisor.worker._session._controller.logical_runtime is None
        joined.append(change)
        attach(mailbox, change)

    monkeypatch.setattr(PacketMailbox, 'attach_capacity', after_join)
    try:
        pcm, rate = paced_pcm(.5)
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm, pcm_rate=rate):
            owner = rig.build()
        mailbox = owner._worker.mailbox
        old_name, wake = mailbox.mapping_name, mailbox._wake_thread
        inputs = offline_activation_request('extruded_bubble', 0, None, _settings('extruded_bubble', True))
        request = owner.request_preset_change if initial_mode == 'extruded_bubble' else owner.request_mode_change
        assert request('extruded_bubble', **inputs)
        for step in range(100):
            clock[0] = .05*(step+1)
            _pump(rig, .01)
            if mailbox.mapping_name != old_name and owner._worker_commit is None:
                break
        assert owner.controller.mode_id == 'extruded_bubble'
        assert len(joined) == 1 and owner._worker.mailbox is mailbox and mailbox._wake_thread is wake
        assert mailbox.slot_bytes >= required_slot_bytes('extruded_bubble', inputs['logical_kwargs'])
        assert mailbox.mapping_name == supervisor.worker._session.mapping_name != old_name
        assert owner._worker.mapping_name == mailbox.mapping_name
        assert mailbox._reader.read_identity()[1:3] == owner._worker_identity
        with pytest.raises(FileNotFoundError):
            SharedMemory(name=old_name)
    finally:
        rig.close()
        supervisor.close()
        engine_worker_link.reset_run_state_for_testing()


@pytest.mark.qt
def test_capacity_violation_fails_closed_without_recovery_or_in_process_fallback(qt_app, monkeypatch, caplog):
    from core.visualizer_engine.packet_abi import FrameCapacityError
    from widgets.spotify_visualizer import engine_worker_link
    from tools.visualizer_replay.live_engine_gate import paced_pcm
    from tests.test_visualizer_owner_engine_worker import _InProcessSupervisor, _pump
    from tools.visualizer_replay import owner_worker_gate as gate

    supervisor = _InProcessSupervisor()
    rig = gate.OwnerRig('spectrum', worker=True, supervisor=supervisor, cadence='thread')
    attempts = []
    try:
        pcm, rate = paced_pcm(.5)
        with engine_worker_link.recorded_capture_for_testing(pcm=pcm, pcm_rate=rate):
            owner = rig.build()
        monkeypatch.setattr(owner, '_fall_back_in_process', lambda *a, **k: attempts.append('fallback'))
        monkeypatch.setattr(owner, '_on_engine_worker_failed', lambda *a, **k: attempts.append('recovery'))
        session = supervisor.worker._session

        def overflow(now):
            session.mailbox.publish(b'x'*(session.mailbox.slot_bytes+1), generation=owner.controller.runtime_generation)

        monkeypatch.setattr(session, '_paced_step_body', overflow)
        with pytest.raises(FrameCapacityError):
            session._paced_step(0.)
        _pump(rig, .2)
        assert owner._mode_transition_phase == 'failed' and not attempts
        assert 'actual_bytes=' in caplog.text and 'capacity_bytes=' in caplog.text
    finally:
        rig.close()
        supervisor.close()
        engine_worker_link.reset_run_state_for_testing()
