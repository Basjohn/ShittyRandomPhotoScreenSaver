"""Simultaneous retained payloads use production producers/capture, beyond a short schema-max replay."""
from dataclasses import replace

import pytest

from tests.test_visualizer_engine_frame_capacity import _settings


def _through_mailbox(frame, logical_kwargs):
    from core.visualizer_engine.frame_capacity import required_slot_bytes
    from core.visualizer_engine.packet_mailbox import PacketMailbox
    from core.visualizer_engine import frame_codec

    mailbox = PacketMailbox(slot_bytes=required_slot_bytes(frame.mode_id, logical_kwargs))
    try:
        mailbox.publish(frame, generation=frame.runtime_generation, activation_id=frame.activation_id, now_ts=1.)
        back = mailbox.take().state
        assert frame_codec.encode(back) == frame_codec.encode(frame)
        return len(frame_codec.encode((frame.runtime_generation, frame.activation_id, 1., frame)))
    finally:
        mailbox.close()


@pytest.mark.qt
@pytest.mark.parametrize('portable_maximum', (False, True), ids=('production_population', 'portable_ring_maximum'))
def test_waveform_simultaneous_full_history_cohort_and_burst_buffers_fit(qt_app, monkeypatch, portable_maximum):
    import numpy as np
    import tools.expanded_visualizer_evidence as evidence
    from core.ribbon_packet import MAX_RIBBONS, RIBBON_BYTES
    from core.ribbon_geometry import MAX_PATH_SAMPLES
    from core.ribbon_ring import RibbonRing
    from core.ribbon_bursts import CAPACITY, STRIDE, RibbonBursts
    from core.ribbon_strand_cohorts import COHORT_BYTES, RibbonStrandCohorts
    from core.waveform_ribbon_authoring import RIBBON_CAPACITY
    from core.waveform_ribbon_dynamics import PULSE_GRID
    from widgets.spotify_visualizer.waveform_ribbon_frame_runtime import WaveformRibbonFrameRuntime
    from widgets.spotify_visualizer.feature_replay import offline_activation_request

    settings = _settings('waveform_ribbon', True)
    activation = offline_activation_request('waveform_ribbon', 0, None, settings)
    advance = WaveformRibbonFrameRuntime.advance
    measured = []

    def high_water(runtime, **kwargs):
        advance(runtime, **kwargs)
        model, controls = runtime._model, kwargs['controls']
        # Complete the actual bounded activation preparation, rather than publishing a partially primed replay.
        for _ in range(MAX_PATH_SAMPLES):
            if model.ready:
                break
            model.advance(0., bands=(1., 1., 1.), intensity=1., presence=1., controls=controls)
        assert model.ready
        snapshot = model.advance(.1, bands=(1., 1., 1.), intensity=1., presence=1.,
                                 hit=1., accent=1., controls=controls)
        assert len(model.ring) == MAX_PATH_SAMPLES
        if portable_maximum:
            # Current authoring uses four; the reusable production ring/codec also admits eight. Exercise that
            # conservative ABI ceiling through append/packet and the real event producers, never fabricated bytes.
            ring = RibbonRing(MAX_RIBBONS)
            for index in range(MAX_PATH_SAMPLES):
                coordinate = (index-MAX_PATH_SAMPLES+1)/controls.scene.flow.knot_hz
                ring.append(coordinate, [(coordinate, 2.+owner*.1, 0.) for owner in range(MAX_RIBBONS)], .2)
            snapshot = replace(snapshot, packet=ring.packet(), head_x=0., travel=0.)
            bursts = RibbonBursts()
            assert bursts.admit(snapshot, controls.accents, 1.) > 0
            cohorts = RibbonStrandCohorts(MAX_RIBBONS)
            strands = cohorts.update(snapshot, controls.strands, 1., history=snapshot.packet,
                                     knot_hz=controls.scene.flow.knot_hz)
            snapshot = replace(snapshot, particles=bursts.visible_payload(snapshot.time), strands=strands,
                               particle_origin=bursts.origin, particle_serial=bursts.serial,
                               strand_origin=cohorts.origin)
        count = MAX_RIBBONS if portable_maximum else RIBBON_CAPACITY
        assert snapshot.packet.instances == count
        assert len(snapshot.packet.payload) == count*RIBBON_BYTES
        assert len(snapshot.strands) == count*COHORT_BYTES
        assert len(snapshot.particles) == CAPACITY*STRIDE*np.dtype(np.float32).itemsize
        assert len(snapshot.pulse) == PULSE_GRID.size*np.dtype(np.float32).itemsize
        measured.append(snapshot)
        return snapshot

    frames = []
    digest = evidence.frame_digest

    def captured(frame):
        frames.append(frame)
        return digest(frame)

    monkeypatch.setattr(WaveformRibbonFrameRuntime, 'advance', high_water)
    monkeypatch.setattr(evidence, 'frame_digest', captured)
    evidence.owner_replay(evidence.shipped_clip(.015), 'waveform_ribbon', settings=settings)
    assert frames and measured
    payload_bytes = _through_mailbox(frames[-1], activation['logical_kwargs'])
    print({'mode': 'waveform_ribbon', 'ribbons': measured[-1].packet.instances,
           'packet_bytes': len(measured[-1].packet.payload), 'strand_bytes': len(measured[-1].strands),
           'burst_bytes': len(measured[-1].particles), 'pulse_bytes': len(measured[-1].pulse),
           'publication_bytes': payload_bytes})


@pytest.mark.qt
def test_devcurve_all_layers_at_maximum_authored_nodes_have_fixed_sample_history(qt_app, monkeypatch):
    import tools.expanded_visualizer_evidence as evidence
    from ui.studio.devcurve_adapter import layers, node_limits, layer_key
    from widgets.spotify_visualizer.devcurve_runtime import DEVCURVE_SAMPLE_COUNT
    from widgets.spotify_visualizer.devcurve_frame_runtime import DevCurveFrameRuntime
    from widgets.spotify_visualizer.feature_replay import offline_activation_request

    settings = _settings('devcurve', True)
    maximum_nodes = node_limits()[1]
    for layer in layers():
        settings[layer_key(layer, 'enabled')] = True
        settings[layer_key(layer, 'shape_nodes')] = [[index/(maximum_nodes-1), .2+.6*(index % 2)]
                                                    for index in range(maximum_nodes)]
    activation = offline_activation_request('devcurve', 0, None, settings)
    advance, histories = DevCurveFrameRuntime.advance, []

    def stepped(runtime, **kwargs):
        resolved = advance(runtime, **kwargs)
        histories.append({name: len(values) for name, values in runtime.solver_state.previous_layers.items()})
        return resolved

    frames, digest = [], evidence.frame_digest

    def captured(frame):
        state = frame.mode_state
        assert {name for name, values in state.curves} == set(layers())
        assert all(len(values) == DEVCURVE_SAMPLE_COUNT for name, values in state.curves)
        assert all(len(state.parameters[layer_key(layer, 'shape_nodes')]) == maximum_nodes for layer in layers())
        assert set(state.draw_order) == set(layers()) and len(state.specular_slots) == 3
        # The production runtime deliberately publishes no ghost history; retained solver state is one prior curve.
        assert not state.ghost_curves
        frames.append(frame)
        return digest(frame)

    monkeypatch.setattr(DevCurveFrameRuntime, 'advance', stepped)
    monkeypatch.setattr(evidence, 'frame_digest', captured)
    evidence.owner_replay(evidence.shipped_clip(.15), 'devcurve', settings=settings)
    assert frames and all(history == dict.fromkeys(layers(), DEVCURVE_SAMPLE_COUNT) for history in histories)
    payload_bytes = max(_through_mailbox(frame, activation['logical_kwargs']) for frame in frames)
    print({'mode': 'devcurve', 'layers': len(layers()), 'samples_per_layer': DEVCURVE_SAMPLE_COUNT,
           'nodes_per_layer': maximum_nodes, 'specular_slots': len(frames[-1].mode_state.specular_slots),
           'publication_bytes': payload_bytes})


@pytest.mark.qt
def test_neon_maximum_extended_terrain_and_full_event_ring_fit_together(qt_app, monkeypatch):
    import tools.expanded_visualizer_evidence as evidence
    from rendering.gl_programs.heightfield import HEIGHTFIELD_MAX_SIZE, normalize_heightfield
    from rendering.gl_programs.shockwave_grid_program import SHOCKWAVE_EVENT_RING, SHOCKWAVE_EVENT_MEMORY, shockwave_gap
    from widgets.spotify_visualizer.shockwave_frame_runtime import ShockwaveGridFrameRuntime
    from widgets.spotify_visualizer.transient_bus import MusicalOnset
    from widgets.spotify_visualizer.feature_replay import offline_activation_request

    settings = _settings('shockwave_grid', True)
    size = HEIGHTFIELD_MAX_SIZE
    settings['shockwave_grid_terrain'] = normalize_heightfield(
        {'version': 1, 'size': size, 'heights': [.2]*(size*size)})
    activation = offline_activation_request('shockwave_grid', 0, None, settings)
    record = ShockwaveGridFrameRuntime.record_onsets
    gap = shockwave_gap(1.)*1.001
    assert (SHOCKWAVE_EVENT_RING-1)*gap < SHOCKWAVE_EVENT_MEMORY

    def full_ring(runtime, *, now_ts, **kwargs):
        serial = runtime.onset_serial
        onsets = tuple(MusicalOnset(serial+index+1, now_ts-(SHOCKWAVE_EVENT_RING-index-1)*gap,
                                    'kick', 1., 3., 1., 1.) for index in range(SHOCKWAVE_EVENT_RING))
        return record(runtime, onsets=onsets, now_ts=now_ts, playing=True, passage_intensity=1.)

    frames, digest = [], evidence.frame_digest

    def captured(frame):
        assert len(frame.mode_state.events) == SHOCKWAVE_EVENT_RING
        terrain = frame.mode_state.parameters['shockwave_grid_terrain']
        assert terrain['size'] == HEIGHTFIELD_MAX_SIZE and len(terrain['data']) == size*size*2*4
        frames.append(frame)
        return digest(frame)

    monkeypatch.setattr(ShockwaveGridFrameRuntime, 'record_onsets', full_ring)
    monkeypatch.setattr(evidence, 'frame_digest', captured)
    evidence.owner_replay(evidence.shipped_clip(.015), 'shockwave_grid', settings=settings)
    assert frames
    payload_bytes = _through_mailbox(frames[-1], activation['logical_kwargs'])
    print({'mode': 'shockwave_grid', 'terrain_side': size, 'terrain_bytes': size*size*2*4,
           'events': len(frames[-1].mode_state.events), 'publication_bytes': payload_bytes})
