"""Waveform Ribbon's native schema (N5.4; ``core.visualizer_engine.waveform_native_schema``): one field per pass-file
member the frame decides, holding ``waveform_pass_values``'s value; the card's members are the settings'; the streams
and counts as the draws read them; a frame without a framed view is refused. Test-owned frames only."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from tests.test_waveform_pulse_rim import _settled, _state


def _logical(state):
    return SimpleNamespace(mode_id="waveform_ribbon", mode_state=state)


def _frame_state():
    values, configuration, _model, snapshot = _settled(floor_give=.6, strands_enabled=True)
    return replace(_state(values, configuration, snapshot), framed_view=(1.6, 1.0, 1.0))


def test_the_fields_are_the_pass_files_members_but_the_cards():
    from core.visualizer_engine import waveform_native_schema as schema
    from rendering.gl_programs.waveform_shader_files import member_name, pass_numbers

    expected = {member_name(pass_id, member): numbers for pass_id, members in pass_numbers().items()
                for member, numbers in members.items()}
    record = {name: count for name, _kind, count in schema.MEMBER_ENTRIES}
    assert set(record) == set(expected) - schema.SETTINGS_MEMBERS
    assert all(record[name] == expected[name] for name in record)
    assert schema.SETTINGS_MEMBERS <= set(expected)
    assert schema.LAYOUT.size % 16 == 0 and schema.LAYOUT.size <= (1 << 21)


def test_the_record_holds_the_pass_values_streams_and_counts():
    from core.visualizer_engine import waveform_native_schema as schema
    from rendering.gl_programs.waveform_shader_files import member_name
    from rendering.quick.visualizer.implementations.waveform_ribbon import waveform_pass_values

    state = _frame_state()
    decoded = schema.decode(schema.encode(_logical(state)))
    from rendering.gl_programs.waveform_shader_files import pass_numbers

    passes, counts = waveform_pass_values(state, (1, 1))
    blocks = pass_numbers()
    for pass_id, members in passes.items():
        for member, value in members.items():
            name = member_name(pass_id, member)
            if name in schema.SETTINGS_MEMBERS or member not in blocks[pass_id]:
                continue                 # a card member, or a sampler's unit the Python draw sets beside its block
            got = np.atleast_1d(np.asarray(decoded[name], float))
            want = np.asarray(schema.flat_numbers(value), float)
            np.testing.assert_array_equal(got, want, err_msg=name)
    assert decoded["ribbon_knots"][:len(state.packet.payload)] == state.packet.payload
    assert decoded["ribbon_knot_floats"] == len(state.packet.payload) // 4
    assert decoded["ribbon_pulse_floats"] == len(state.pulse) // 4
    assert decoded["ribbon_instances"] == state.packet.instances
    assert decoded["ribbon_vertices"] == counts["ribbon_vertices"] > 0
    assert decoded["give_groups"] == -(-counts["give_samples"] // 64) > 0
    assert decoded["u_hdr_exposure"] == state.scene.exposure
    # Negative control: another frame's record differs in its per-frame members.
    later = replace(state, time=state.time + .5)
    assert schema.decode(schema.encode(_logical(later)))["ribbon_uAge"] != decoded["ribbon_uAge"]


def test_a_frame_without_its_framed_view_is_refused():
    from core.visualizer_engine import waveform_native_schema as schema
    from core.visualizer_engine.native_schema import NativeSchemaError

    with pytest.raises(NativeSchemaError):
        schema.encode(_logical(replace(_frame_state(), framed_view=())))
