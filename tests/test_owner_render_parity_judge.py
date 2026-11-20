"""The cheaper judge (fast long-clip proof, part 2 step 1) never changes a verdict:

- ``pixel_tolerance.judge`` reads the reference's content edges only at its ties and flips (``content_edges_at``):
  its verdicts equal the whole-frame path (``judge_delta`` with ``content_edges`` of the whole reference);
- ``owner_render_parity.judged_pass`` (one decompress and one delta per differing input) gives exactly what
  ``pair_difference``, ``frame_differences``, ``rule_a_frames`` and ``classify_differences`` give.

Frames are synthetic (seeded): content with hard edges, scatter, ties on and off edges, flips, translucent masks, a
region that differs and a whole-display-only difference. Control: a judge that read no edges would differ (seen
failing: its ties off isolation fail where the whole-frame path passes them on an edge).
"""
from __future__ import annotations

import hashlib
import zlib

import numpy as np
import pytest

from tools import pixel_tolerance as pt


def _reference(rng, shape=(48, 64)):
    h, w = shape
    frame = np.zeros((h, w, 4), np.uint8)
    frame[..., 3] = 255
    for _ in range(6):                                     # hard-edged blocks: content edges
        y, x = rng.integers(0, h - 8), rng.integers(0, w - 8)
        frame[y:y + rng.integers(4, 12), x:x + rng.integers(4, 16), :3] = rng.integers(40, 255, 3)
    frame[..., :3] += rng.integers(0, 3, (h, w, 3)).astype(np.uint8)    # a soft gradient-like texture
    return frame


def _candidate(rng, reference, kind):
    out = reference.astype(np.int16).copy()
    h, w = reference.shape[:2]
    if kind == "scatter":
        for _ in range(rng.integers(1, 30)):
            out[rng.integers(0, h), rng.integers(0, w), rng.integers(0, 3)] += 1
    elif kind == "ties":
        for _ in range(rng.integers(1, 14)):
            out[rng.integers(0, h), rng.integers(0, w), 0] += int(rng.integers(2, 4))
    elif kind == "patch":
        y, x = rng.integers(0, h - 6), rng.integers(0, w - 6)
        out[y:y + 5, x:x + 5, 1] += 1
        out[y + 2, x + 2, 1] += 2
    elif kind == "flips":
        out[rng.integers(0, h), rng.integers(0, w), 2] += 9
    elif kind == "shift":
        out[..., :3] += 1
    return np.clip(out, 0, 255).astype(np.uint8)


TOLERANCES = [
    pt.Tolerance("composite", masked_level=1, tie_pixels=10, tie_level=3, edge_class=True),
    pt.Tolerance("scatter spread", masked_level=1, scatter_pixels=68, tie_pixels=10, tie_level=3, edge_class=True,
                 scatter_cluster_pixels=22),
    pt.Tolerance("flips", tie_pixels=4, flip_pixels=1),
    pt.EXACT,
]


def _whole_frame_judge(candidate, reference, tolerance, mask=None):
    """The judge before step 1: the reference's content edges over the whole frame."""
    delta = pt.levels(candidate, reference)
    edges = pt.content_edges(reference, tolerance.edge_contrast) if delta.any() else None
    return pt.judge_delta(delta, tolerance, mask=mask, edges=edges)


def _cases(seed=7, count=60):
    rng = np.random.default_rng(seed)
    kinds = ("scatter", "ties", "patch", "flips", "shift", "same")
    for index in range(count):
        reference = _reference(rng)
        candidate = _candidate(rng, reference, kinds[index % len(kinds)])
        mask = rng.random(reference.shape[:2]) < 0.1 if index % 3 == 0 else None
        yield candidate, reference, mask


@pytest.mark.parametrize("tolerance", TOLERANCES, ids=lambda t: t.name)
def test_the_judge_reads_edges_only_where_it_needs_them_and_never_changes_a_verdict(tolerance):
    judged = 0
    for candidate, reference, mask in _cases():
        assert pt.judge(candidate, reference, tolerance, mask=mask) == \
            _whole_frame_judge(candidate, reference, tolerance, mask)
        judged += 1
    assert judged == 60


def test_edges_at_flagged_pixels_equal_the_whole_frame_edges_there():
    rng = np.random.default_rng(3)
    reference = _reference(rng)
    flags = rng.random(reference.shape[:2]) < 0.3
    flags[0, :] = flags[-1, :] = flags[:, 0] = flags[:, -1] = True        # the replicated borders
    whole = pt.content_edges(reference)
    assert (pt.content_edges_at(reference, flags) == (whole & flags)).all()
    assert whole[flags].any() and (~whole[flags]).any()


def test_control_a_judge_reading_no_edges_differs():
    tolerance = TOLERANCES[0]
    differs = sum(pt.judge_delta(pt.levels(c, r), tolerance, mask=m) != _whole_frame_judge(c, r, tolerance, m)
                  for c, r, m in _cases())
    assert differs > 0


def _run(frames, records):
    return {"pixels": records, "frames": frames}


def _runs(seed=11, count=40):
    rng = np.random.default_rng(seed)
    native_frames, python_frames, native_records, python_records = [], [], [], []
    kinds = ("scatter", "ties", "patch", "flips", "shift", "same")
    for index in range(count):
        reference = _reference(rng)
        candidate = _candidate(rng, reference, kinds[index % len(kinds)])
        region = [0, 0, reference.shape[1], reference.shape[0]]
        for frames, records, image in ((native_frames, native_records, candidate),
                                       (python_frames, python_records, reference)):
            frames.append((image.shape, zlib.compress(image.tobytes(), 1)))
            records.append({"region": list(region), "hash": hashlib.sha256(image.tobytes()).hexdigest()})
        if index == 5:                                        # only the whole-display hash differs
            native_records[-1]["full"], python_records[-1]["full"] = "a", "b"
        if index == 9:                                        # a region that differs
            native_records[-1]["region"] = [1, 0, reference.shape[1], reference.shape[0]]
    return _run(native_frames, native_records), _run(python_frames, python_records)


@pytest.mark.parametrize("mode", [None, "bubble"])
def test_the_single_pass_gives_what_the_four_passes_give(mode):
    from tools.visualizer_replay import owner_render_parity as parity

    native, python = _runs()
    rng = np.random.default_rng(5)
    masks = {index: rng.random((48, 64)) < 0.1 for index in range(0, 40, 4)}
    switch_input = 30
    single = parity.judged_pass(native, python, masks, switch_input, mode)
    assert single["paths"] == parity.pair_difference(native, python)
    assert single["rows"] == parity.frame_differences(native, python)
    assert single["classes"] == parity.classify_differences(native, python, switch_input)
    old = []
    for index, (x, y) in enumerate(zip(native["pixels"], python["pixels"])):
        if x["hash"] == y["hash"]:
            continue
        if x["region"] != y["region"]:
            old.append({"pass": False, "reasons": [f"input {index}: the regions differ"], "max_level": None,
                        "input": index})
            continue
        verdict = _whole_frame_judge(parity._pixels(native, index), parity._pixels(python, index),
                                     parity.composite_tolerance(mode), masks.get(index))
        verdict["input"] = index
        old.append(verdict)
    assert single["judged"] == old == parity.rule_a_frames(native, python, masks, mode)
    # Not vacuous: passes and failures, a region mismatch and classified pixels are all present.
    assert any(v["pass"] for v in old) and any(not v["pass"] for v in old)
    assert single["paths"]["regions_equal"] is False and single["paths"]["frames"] > 20
    assert sum(entry["pixels"] for entry in single["classes"].values()) > 0
