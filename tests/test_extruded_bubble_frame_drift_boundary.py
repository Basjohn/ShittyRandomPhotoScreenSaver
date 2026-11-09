"""CPU oracle arrays stop at logical capture; GPU geometry and step bytes survive exactly."""
from dataclasses import fields, replace

import pytest


@pytest.mark.qt
def test_production_capture_omits_cpu_sources_and_preserves_renderer_bytes(qt_app, monkeypatch):
    from core.visualizer_engine import frame_codec
    from tests._visualizer_frozen_settings import frozen_visualizer_settings
    import tools.expanded_visualizer_evidence as evidence
    from widgets.spotify_visualizer.extruded_bubble_simulation import ExtrudedBubbleSimulation

    # Independent non-default controls exercise every drift family, including changing capacity.
    settings = {**frozen_visualizer_settings('extruded_bubble'),
                'extruded_bubble_drift_chains': [.7, 1.2],
                'extruded_bubble_drift_snow': [.8, 1.1],
                'extruded_bubble_drift_specks': [.9, 1.3],
                'extruded_bubble_particles': [.17, .43],
                'extruded_bubble_bead_chains': [1., 3.]}
    advance = ExtrudedBubbleSimulation.advance
    digest = evidence.frame_digest
    snapshots, seen = [], []

    def snapshot(sim, *args, **kwargs):
        result = advance(sim, *args, **kwargs)
        snapshots.append(result)
        return result

    def checked(logical):
        state, source = logical.mode_state, snapshots[-1]
        assert state.drift_steps == source.drift_steps
        assert len(state.drift_families) == len(source.drift_families)
        for rendered, original in zip(state.drift_families, source.drift_families):
            assert original.source, 'the fixture must exercise the actual CPU-oracle arrays'
            assert not rendered.source, 'CPU reference arrays crossed the publication boundary'
            assert rendered.geometry is original.geometry
            for field in fields(original):
                if field.name != 'source':
                    assert getattr(rendered, field.name) == getattr(original, field.name)
        payload = frame_codec.encode(logical)
        back = frame_codec.decode(payload)
        assert frame_codec.encode(back) == payload
        assert repr(back) == repr(logical)
        assert all(not family.source for family in back.mode_state.drift_families)
        if state.drift_families:
            # Restoring the old publication produces the same renderer digest but needlessly ships arrays.
            old = replace(logical, mode_state=replace(state, drift_families=source.drift_families))
            assert digest(old) == digest(logical)
            assert len(frame_codec.encode(old)) > len(payload)
            seen.append({family.family for family in state.drift_families})
        return digest(logical)

    monkeypatch.setattr(ExtrudedBubbleSimulation, 'advance', snapshot)
    monkeypatch.setattr(evidence, 'frame_digest', checked)
    evidence.owner_replay(evidence.shipped_clip(.35), 'extruded_bubble', settings=settings)
    assert seen and set.union(*seen) == {'chains', 'snow', 'specks'}


def test_render_descriptor_is_reused_until_geometry_changes_or_grows():
    import gc
    import weakref
    import numpy as np
    from widgets.spotify_visualizer.extruded_bubble_drift_log import DriftLog, cloud_lifetime

    log = DriftLog()

    def geometry(count):
        return (np.ones((count, 3)), np.ones(count), np.arange(count, dtype=float), .5, np.zeros(count))

    def admit(key, count):
        log.admit('specks', key, count, geometry, cloud_lifetime)
        return log.family('specks')

    original = admit(('first',), 3)
    rendered = original.render_descriptor
    assert rendered is original.render_descriptor
    assert rendered.render_descriptor is rendered
    assert not rendered.source and rendered.geometry is original.geometry
    assert admit(('first',), 3).render_descriptor is rendered
    grown = admit(('first',), 5)
    assert grown.revision == original.revision
    assert grown.render_descriptor is not rendered
    assert grown.render_descriptor.capacity == 5
    assert grown.render_descriptor.geometry is grown.geometry
    edited = admit(('edited',), 5)
    assert edited.revision != grown.revision and edited.rebase_from == grown.revision
    assert edited.render_descriptor is not grown.render_descriptor
    assert edited.render_descriptor.geometry is edited.geometry and not edited.render_descriptor.source
    # Source-free descriptors must not cache themselves: that would retain per-frame geometry until cyclic GC.
    reference = weakref.ref(rendered)
    gc.disable()
    try:
        del original, rendered
        assert reference() is None
    finally:
        gc.enable()
