"""Waveform Ribbon's logical tick publishes exactly what its straightforward forms publish (6 Nov 2026 tick cut).

The hot paths of the Waveform logical tick (the ribbon springs, the pulse transport, the along-curve surge, the
per-ribbon count/direction fade, the scene recipe, the capture's settings reads and the material check) were rewritten
to hold the logical thread's GIL for less time. Waveform's output is accepted, protected behaviour (Preset 4 is the
operator's baseline), so every rewrite must be byte-identical. These tests run the production dynamics and scene on a
seeded input sequence twice, once with the pre-cut forms (``tests/_waveform_reference_forms.py``) patched in, and
compare a digest of every published frame, in every Reaction Mode, through a count change and a Travel Direction
change, with sparks, strands, Kick Accent, Tilt Shift and Static Height. A negative control proves the digest sees the
classic slip (an fp64 fade multiply instead of the packet's float32). Settings are the frozen test copy plus
test-owned overrides; no preset or default value is pinned.
"""
from __future__ import annotations

from contextlib import ExitStack
import hashlib
import math
import random
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

import core.ribbon_bursts as bursts
from core.ribbon_packet import KNOT_ROWS
from core.ribbon_style import RibbonMaterial, _MATERIAL_FIELDS
import core.waveform_ribbon_dynamics as dyn
from core.waveform_ribbon_dynamics import WaveformDynamics
from tests import _waveform_reference_forms as reference
from tests import _waveform_reference_forms_cut2 as reference_cut2
from tests._visualizer_frozen_settings import frozen_visualizer_settings
from widgets.spotify_visualizer.waveform_ribbon_parameters import CompiledWaveformSettings

P = 'waveform_ribbon_'
# Test-owned workloads covering every rewritten branch: each Reaction Mode, both edge directions and Centre Out,
# sparks and strands (bursts read the packet), Kick Accent, Tilt Shift and Static Height.
_CASES = {
    'travelling_edge': {'reaction_mode': 'Travelling Pulse', 'pulse_direction': 'Head To Tail', 'tilt_shift': True},
    'travelling_centre': {'reaction_mode': 'Travelling Pulse', 'pulse_direction': 'Centre Out'},
    'frozen_tail': {'reaction_mode': 'Frozen Past', 'pulse_direction': 'Tail To Head'},
    'whole_static': {'reaction_mode': 'Whole Swell', 'height_mode': 'Static Height'},
    'group': {'reaction_mode': 'Group Wave', 'kick_accent': 1.},
}
_TICKS = 700


def _compiled(case, **changes):
    overrides = {P+key: value for key, value in {'sparks_enabled': True, 'strands_enabled': True, 'count': 3,
                                                  **_CASES[case], **changes}.items()}
    return CompiledWaveformSettings({**frozen_visualizer_settings('waveform_ribbon'), **overrides})


def _published(case):
    """Digest of every published frame: the packet, sparks, strands, pulse field, drives and the resolved scene."""
    first = _compiled(case)
    later = _compiled(case, count=4, travel_direction='Left To Right')   # a count fade and a direction fade
    model = WaveformDynamics(first.controls)
    rng = random.Random(7)
    bands = [.4, .3, .2]
    digests = []
    for tick in range(_TICKS):
        compiled = first if tick < _TICKS//2 else later
        bands = [min(1., max(0., value+rng.uniform(-.08, .08))) for value in bands]
        beat = tick % 40 == 0 or rng.random() < .03
        snapshot = model.advance(1/90+rng.uniform(-.002, .002), bands=tuple(bands), intensity=.3+.6*bands[0],
                                 presence=0. if 200 <= tick < 260 else 1., hit=rng.uniform(.3, 1.) if beat else 0.,
                                 hit_components=(rng.random(), rng.random(), rng.random()) if beat else None,
                                 accent=rng.uniform(.1, .6) if beat else 0., controls=compiled.controls,
                                 dynamic_zoom=True, view_span=(-16., 16., 7.5))
        digest = hashlib.sha256()
        for part in (snapshot.packet.payload, snapshot.particles, snapshot.strands, snapshot.pulse):
            digest.update(part)
        digest.update(repr((snapshot.time, snapshot.travel, snapshot.rotation_angle, snapshot.rotation_speed,
                            snapshot.drives, snapshot.realized, snapshot.zoom, snapshot.passage)).encode())
        digest.update(repr(compiled.scene(snapshot)).encode())
        digests.append(digest.hexdigest())
    assert model.ready and len(set(digests)) > _TICKS//2
    return digests


def _with(forms):
    stack = ExitStack()
    for owner, name, form in forms:
        stack.enter_context(patch.object(owner, name, form))
    return stack


_REFERENCE = ((WaveformDynamics, '_advance_springs', reference.advance_springs),
              (WaveformDynamics, '_carry_fields', reference.carry_fields),
              (WaveformDynamics, '_surge', reference.surge),
              (WaveformDynamics, '_fade_ribbons', reference.fade_ribbons),
              (CompiledWaveformSettings, 'scene', reference.scene),
              # Group Wave's lead gradient was np.gradient: every uniform_gradient must equal it exactly.
              (dyn, 'uniform_gradient', lambda field, spacing: np.gradient(field, spacing)))


# The second cut (7 Nov, main cba6ee54): the snapshot's per-packet terms, card crest and HSV columns, exact remainders
# and flat-index surge gathers; the spark emitter's cloth evaluation; the drive routing's clamped sources. The snapshot's
# reference form has no packet terms, so it always runs with the surge's reference form.
_REFERENCE_CUT2 = ((WaveformDynamics, 'snapshot', reference_cut2.snapshot),
                   (WaveformDynamics, '_surge', reference.surge),
                   (bursts, 'cloth_values', reference_cut2.cloth_values),
                   (dyn, 'clamp_sources', lambda sources: sources),
                   (dyn, 'route_clamped', reference_cut2.route))


@pytest.mark.parametrize('case', sorted(_CASES))
def test_every_published_frame_is_byte_identical_to_the_straightforward_forms(case):
    production = _published(case)
    with _with(_REFERENCE):
        straightforward = _published(case)
    assert production == straightforward
    with _with(_REFERENCE_CUT2):
        assert _published(case) == production


def _crest_fp64(self, cards, n):
    """Negative control: the card crest against float64 heights (NumPy would have cast them to the carrier's float32)."""
    magnitude = np.abs(self.carrier[:n])
    crest = np.clip(magnitude/np.asarray([max(1.5*card['height'], 1e-5) for card in cards])[:, None], 0., 1.)
    return crest, .25+.75*crest


def test_the_digest_sees_a_float64_crest_slip():
    production = _published('travelling_edge')
    with _with(((dyn._PacketTerms, 'crest', _crest_fp64),)):
        assert _published('travelling_edge') != production


def _float32_band(centre, count=50_000):
    """Every float32 within ``count`` steps of ``centre`` on its side of zero (zero itself included)."""
    bits = np.int32(np.float32(centre).view(np.int32))
    band = np.arange(max(int(bits)-count, 0 if centre >= 0 else int(np.float32(-0.).view(np.int32))),
                     int(bits)+count+1, dtype=np.int64).astype(np.int32)
    return band.view(np.float32)


def test_the_colour_remainders_are_numpys_remainder_bit_for_bit():
    rng = np.random.default_rng(3)
    edges = [0., -0., .5, -.5, 1., -1., 2., -2., 1e-30, -1e-30, 1e30, -1e30, np.inf, -np.inf, np.nan]
    for dtype in (np.float32, np.float64):
        for scale in (1e-6, .5, 1., 3., 1e7):
            values = np.concatenate([(rng.standard_normal(200_000)*scale).astype(dtype), np.asarray(edges, dtype)])
            with np.errstate(invalid='ignore'):
                expected, produced = np.remainder(values, 1.), dyn.unit_remainder(values.copy())
            finite = np.isfinite(values)
            assert produced.dtype == expected.dtype
            assert produced[finite].tobytes() == expected[finite].tobytes()
            assert np.isnan(produced[~finite]).all() and np.isnan(expected[~finite]).all()
    for centre in (0., -0., .5, -.5, 1., -1., 2., -2.):
        values = _float32_band(centre)
        assert dyn.unit_remainder(values.copy()).tobytes() == np.remainder(values, 1.).tobytes()
    # The HSV sector: every element in [0, 12).
    for dtype in (np.float32, np.float64):
        values = (rng.random(400_000)*12.).astype(dtype)
        values = np.concatenate([values[values < 12.], np.asarray([0., 1., 6., 11.], dtype),
                                 np.nextafter(np.asarray([6., 6., 12.], dtype), np.asarray([0., 12., 0.], dtype))])
        assert dyn.sector_remainder(values.copy()).tobytes() == np.remainder(values, 6.).tobytes()
    for centre in (0., 1., 6.):
        values = _float32_band(centre)
        assert dyn.sector_remainder(values.copy()).tobytes() == np.remainder(values, 6.).tobytes()
    below_twelve = _float32_band(np.nextafter(np.float32(12.), np.float32(0.)))
    below_twelve = below_twelve[below_twelve < 12.]
    assert dyn.sector_remainder(below_twelve.copy()).tobytes() == np.remainder(below_twelve, 6.).tobytes()


def test_routing_from_clamped_sources_is_the_straightforward_routing():
    from core.waveform_ribbon_authoring import clamp_sources, route, route_clamped
    rng = random.Random(11)
    for _ in range(20_000):
        row = [[rng.uniform(0., 2.), rng.uniform(.25, 4.)] for _ in range(6)]
        sources = [rng.choice((rng.uniform(-.5, 1.5), 0., 1., -0., rng.uniform(0., 1e-6))) for _ in range(6)]
        passage = rng.uniform(.35, 1.)
        expected = reference_cut2.route(row, sources, passage=passage)
        assert repr(route_clamped(row, clamp_sources(sources), passage=passage)) == repr(expected)
        assert repr(route(row, sources, passage=passage)) == repr(expected)


def test_the_camera_admission_memo_admits_what_a_fresh_admission_admits():
    from core.settings.framed_camera import admit_camera_parameters, spec_for_mode
    from widgets.spotify_visualizer.view_orbit import CameraAdmissionMemo, _camera_values
    spec = spec_for_mode('waveform_ribbon')
    turn, pan, position = spec.key('turn'), spec.key('scene_pan_x'), spec.key('camera_position')
    base = _camera_values(SimpleNamespace(), spec)   # every camera input at its canonical value
    base[position] = tuple(base[position])
    memo = CameraAdmissionMemo()
    # (values, whether it repeats the previous inputs strictly, so the memo must hand back the very same offset)
    sequence = [(base, False), (dict(base), True), ({**base, turn: .25}, False), ({**base, turn: .25}, True),
                ({**base, pan: .5}, False), ({**base, pan: .5}, True), ({**base, pan: 0.}, False),
                ({**base, pan: -0.}, False), ({**base, position: list(base[position])}, False),
                ({**base, position: list(base[position])}, False), ({**base, position: (9., 9., 9.)}, False),
                (dict(base), False)]
    previous = None
    for values, repeat in sequence:
        admitted = memo.admit(spec, values)
        assert admitted == admit_camera_parameters(spec, values)
        if repeat:
            assert admitted is previous   # an unchanged camera is not solved again
        previous = admitted
    with pytest.raises((TypeError, ValueError, KeyError)):
        memo.admit(spec, {key: value for key, value in base.items() if key != turn})
    assert memo.admit(spec, base) == admit_camera_parameters(spec, base)


def _fade_ribbons_fp64(self, data, rows):
    """Negative control: the vectorised fade with float64 shares (multiplied before the float32 cast)."""
    shares = np.asarray([share*self.direction_share for share in self.count_share])
    for index, card in enumerate(self.controls.cards):
        data[index, 2, :3] = card['quiet'][0]
        data[index, 3, :3] = card['quiet'][1]
    rows[:, :, 1:3] *= shares[:, None, None]
    rows[:, :, 3] = np.maximum(1e-5, rows[:, :, 3]*shares[:, None])
    data[:, 2:4, 3] *= shares[:, None]
    data[:, 7::KNOT_ROWS, 3] *= shares[:, None]
    data[:, 6::KNOT_ROWS, 3] *= shares[:, None]


def test_the_digest_sees_an_fp64_fade_slip():
    production = _published('travelling_centre')
    with _with(((WaveformDynamics, '_fade_ribbons', _fade_ribbons_fp64),)):
        slipped = _published('travelling_centre')
    assert production[:_TICKS//2] == slipped[:_TICKS//2]   # no fade in progress: the slip is invisible
    assert production != slipped


def test_source_shapes_are_recomputed_when_their_origin_or_width_changes():
    model = WaveformDynamics(_compiled('travelling_edge').controls)
    for origin, sigma in ((44., 1.), (44., 2.), (-3., 1.), (44., 1.), (0., .5), (1., .5), (2., .5)):
        expected = np.exp(-.5*((np.linspace(-48., 48., 385)-origin)/sigma)**2)
        assert model._source_shape(origin, sigma).tobytes() == expected.tobytes()
    assert len(model._source_shapes) <= 4


def test_capture_reads_match_the_straightforward_reads_in_value_and_order():
    from core.settings.visualizer_mode_settings import control_runtime_attr, require_mode_settings
    from widgets.spotify_visualizer import waveform_ribbon_capture as capture
    spec = require_mode_settings('waveform_ribbon')
    widget, pres = SimpleNamespace(), SimpleNamespace()
    for index, control in enumerate(spec.controls):   # distinct values per host, so a host swap shows
        setattr(widget, control_runtime_attr(control), ('logical', index))
        setattr(pres, control_runtime_attr(control), ('presentation', index))
    values, configuration, camera = reference.capture_values(widget, pres, spec)
    reads, configuration_keys, camera_keys = capture._reads(spec)
    produced = {key: getattr(widget if logical else pres, attr) for key, logical, attr in reads}
    assert list(produced.items()) == list(values.items())
    assert list({key: produced[key] for key in configuration_keys}.items()) == list(configuration.items())
    assert list({key: produced[key] for key in camera_keys}.items()) == list(camera.items())
    assert camera and configuration


def test_material_check_reads_the_values_astuple_read():
    material = _compiled('group').base.material
    assert tuple(getattr(material, name) for name in _MATERIAL_FIELDS) == reference.material_values(material)
    for bad in ((1., 2.), [1.], True, math.nan, -1.):
        with pytest.raises(ValueError):
            RibbonMaterial(strand_light=bad)
