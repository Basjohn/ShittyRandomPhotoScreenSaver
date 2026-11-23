import struct
from dataclasses import replace

import numpy as np
import pytest

from core.visualizer_engine.extruded_bubble_native_schema import DRIFT_RECORD_ENTRIES, DriftRecordProjector
from core.visualizer_engine.native_schema import NativeLayout, NativeSchemaError, native_schema_id
from core.visualizer_engine.packet_abi import MODE_CODES
from widgets.spotify_visualizer.extruded_bubble_drift_log import (
    CHAIN_GEOMETRY_BYTES, KNOT_DECISION_BYTES, STEP_FLOATS, STEP_HISTORY, STEP_INDEX, DriftFamily,
)
from widgets.spotify_visualizer.render_state import ExtrudedBubbleFrame


def _frame(serials, *families, knot_counts=None):
    rows = np.zeros((len(serials), STEP_FLOATS), dtype="<f8")
    rows[:, STEP_INDEX["serial"]] = serials
    counts = [0] * len(serials) if knot_counts is None else knot_counts
    rows[:, STEP_INDEX["chain_rows"]] = counts
    knots = b"".join(bytes([i + 1]) * KNOT_DECISION_BYTES * count for i, count in enumerate(counts))
    return ExtrudedBubbleFrame(drift_families=families, drift_steps=rows.tobytes(), drift_knots=knots)


def _family(revision, step, *, capacity=2, rebase_from=0):
    return DriftFamily("chains", revision, rebase_from, step, capacity, bytes(CHAIN_GEOMETRY_BYTES * capacity))


def test_d3_key_keeps_the_full_stream_identity_and_revision_through_native_layout():
    namespace, revision = 0x0123456789ABCDEF, 0xFEDCBA9876543210
    descriptor = _family(revision, 1)
    frame = _frame([1], descriptor)
    fields, _ = DriftRecordProjector(namespace, 2, 3).project(frame)
    layout = NativeLayout.build(DRIFT_RECORD_ENTRIES)
    payload = layout.pack(native_schema_id(MODE_CODES["extruded_bubble"], 1), fields)
    off = layout.field("chains_geometry_key").offset
    # Read the key as ABI 42's arena reader sees it, including the capacity word after the full revision.
    assert struct.unpack_from("<QIIIQI", payload, off) == (namespace, 2, 3, 0, revision, descriptor.capacity)
    read = layout.unpack(payload)
    assert read["chains_geometry_key"] == fields["chains_geometry_key"]
    assert read["chains_epoch"] == 1
    assert read["snow_geometry_key"] == (0,) * 8
    for identity in ((namespace + (1 << 32), 2, 3), (namespace, 3, 3), (namespace, 2, 4)):
        changed, _ = DriftRecordProjector(*identity).project(frame)
        assert changed["chains_geometry_key"] != read["chains_geometry_key"]


def test_epochs_follow_revisions_and_keep_the_predecessor_across_republication():
    projector = DriftRecordProjector(7, 2, 3)
    first = _family((7 << 32) + 3, 1)
    grew = replace(first, capacity=3, geometry=bytes(3 * CHAIN_GEOMETRY_BYTES))
    edited = _family(first.revision + (1 << 32), 3, rebase_from=first.revision)

    def fields(frame):
        return projector.project(frame)[0]

    a = fields(_frame([1], first))
    b = fields(_frame([1, 2], grew))
    assert a["chains_geometry_key"][:-1] == b["chains_geometry_key"][:-1]
    assert b["chains_geometry_key"][-1] == grew.capacity
    assert a["chains_epoch"] == b["chains_epoch"] == 1
    assert b["chains_rebase_from_epoch"] == 0
    c = fields(_frame([1, 2, 3], edited))
    d = fields(_frame([2, 3, 4], edited))
    assert c["chains_geometry_key"] == d["chains_geometry_key"]
    assert c["chains_epoch"] == d["chains_epoch"] == 2
    assert c["chains_rebase_from_epoch"] == d["chains_rebase_from_epoch"] == 1
    assert c["chains_first_step"] == d["chains_first_step"] == 3

    skipped = _family(edited.revision + 2, 5, rebase_from=edited.revision + 1)
    assert fields(_frame([3, 4, 5], skipped))["chains_rebase_from_epoch"] == 0
    retired = fields(_frame([3, 4, 5]))
    assert retired["chains_epoch"] == retired["drift_last_step"] == 0
    revived = _family(skipped.revision + 1, 7, rebase_from=skipped.revision)
    fields_after_retire = fields(_frame([3, 4, 5, 7], revived))
    assert fields_after_retire["chains_epoch"] == 4
    assert fields_after_retire["chains_rebase_from_epoch"] == 0


def test_step_window_is_authored_and_uses_an_applied_cursor_to_detect_a_gap():
    projector = DriftRecordProjector(7, 2, 3)
    frame = _frame(range(2, STEP_HISTORY + 2), _family(7, 1), knot_counts=[1, 0, 2] + [0] * (STEP_HISTORY - 3))
    fields, window = projector.project(frame)
    assert window.steps is frame.drift_steps and window.knots is frame.drift_knots
    assert (fields["drift_first_step"], fields["drift_last_step"]) == (2, STEP_HISTORY + 1)
    missed, fresh = window.after(0)
    assert missed is window and fresh
    next_window, fresh = window.after(3)
    assert not fresh and next_window.first_serial == 4
    assert next_window.steps == frame.drift_steps[2 * 8 * STEP_FLOATS:]
    assert next_window.knots == frame.drift_knots[KNOT_DECISION_BYTES:]
    assert not window.after(STEP_HISTORY + 1)[0].steps
    assert not fields["chains_rebase_from_epoch"]


def test_failed_projection_does_not_advance_any_familys_epoch_or_step():
    projector = DriftRecordProjector(7, 2, 3)
    first = _family(2, 1)
    projector.project(_frame([1], first))
    edited = _family(3, 2, rebase_from=2)
    bad = replace(edited, family="snow", source=("reference only",))
    with pytest.raises(NativeSchemaError, match="source-free"):
        projector.project(_frame([1, 2, 3], edited, bad))
    fields, _ = projector.project(_frame([1, 2], edited))
    assert fields["chains_epoch"] == 2 and fields["chains_rebase_from_epoch"] == 1
    with pytest.raises(NativeSchemaError, match="went backwards"):
        projector.project(_frame([1], first))


@pytest.mark.parametrize("serials", ([1, 3, 2, 4], [1, 2, 2, 4], [1, 2.5, 4], [1, 0, 4], [1, 1 << 32, 4]))
def test_invalid_interior_serial_leaves_the_cursor_and_epoch_untouched(serials):
    projector = DriftRecordProjector(7, 2, 3)
    first = _family(2, 1)
    projector.project(_frame([1], first))
    invalid = _family(3, 2, rebase_from=2)
    with pytest.raises(NativeSchemaError, match="drift step"):
        projector.project(_frame(serials, invalid))

    edited = _family(4, 2, rebase_from=2)
    fields, window = projector.project(_frame([1, 3], edited))
    assert fields["chains_epoch"] == 2 and fields["chains_rebase_from_epoch"] == 1
    assert fields["drift_last_step"] == 3
    pending, restart = window.after(1)
    assert restart and pending.first_serial == pending.last_serial == 3
