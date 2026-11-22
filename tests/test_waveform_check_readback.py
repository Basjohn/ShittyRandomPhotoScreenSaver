"""Waveform's readback round (``native/core/python/waveform_check.py``, E13 and E15): one backend's scene targets and
storage images against the other's, name by name, with rows or slices running the other way caught."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "native" / "core" / "python"))


def _volume(values) -> tuple:
    values = np.asarray(values, np.float16)
    depth, height, width, _channels = values.shape
    return ("rgba16f", (width, height, depth), 0, values.tobytes())


def _field():
    z, y, x = np.meshgrid(np.arange(4), np.arange(5), np.arange(6), indexing="ij")
    return np.stack([x * .1, y * .2, z * .3, x * y * .01 + z], axis=-1)


def test_matching_readbacks_pass_and_reversed_ones_fail():
    import waveform_check as wc

    field = _field()
    same = wc.compare_readback({"medium": _volume(field)}, {"medium": _volume(field)})
    assert same["pass"] and same["resources"]["medium"]["exact"]
    near = wc.compare_readback({"medium": _volume(field)}, {"medium": _volume(field + 1e-3)})
    assert near["pass"] and near["resources"]["medium"]["max_abs"] < 2e-3
    # Negative controls: the other backend's rows reversed, its slices reversed, a size or a name missing all fail.
    assert not wc.compare_readback({"medium": _volume(field)}, {"medium": _volume(field[:, ::-1])})["pass"]
    assert not wc.compare_readback({"medium": _volume(field)}, {"medium": _volume(field[::-1])})["pass"]
    assert not wc.compare_readback({"medium": _volume(field)}, {"medium": _volume(field[:, :, :5])})["pass"]
    assert not wc.compare_readback({"medium": _volume(field)}, {})["pass"]


def test_a_target_is_judged_as_a_single_slice():
    import waveform_check as wc

    rows = (np.arange(6 * 5 * 4).reshape(5, 6, 4) % 251).astype(np.uint8)
    target = ("rgba8", (6, 5), 0, rows.tobytes())
    assert wc.compare_readback({"reflection@0": target}, {"reflection@0": target})["pass"]
    flipped = ("rgba8", (6, 5), 0, rows[::-1].copy().tobytes())
    assert not wc.compare_readback({"reflection@0": target}, {"reflection@0": flipped})["pass"]
    # A chain's last level (one texel) has no rows to reverse: judged by its values alone, never failed for that.
    texel = ("rgba16f", (1, 1), 7, np.array([.5, .25, .125, 1.], np.float16).tobytes())
    near = ("rgba16f", (1, 1), 7, np.array([.5, .25, .125 + 2 ** -10, 1.], np.float16).tobytes())
    judged = wc.compare_readback({"reflection@7": texel}, {"reflection@7": near})
    assert judged["pass"] and judged["resources"]["reflection@7"]["row_reversed_mean_abs"] is None
