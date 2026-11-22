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


def test_an_opengl_row_pitch_is_read_past_its_padding():
    import waveform_check as wc

    # fog_steady's shape in small: r16f, 27 columns (54 bytes a row), which OpenGL packs at 56 with garbage after.
    values = (np.arange(3 * 4 * 27).reshape(3, 4, 27) * 1e-3).astype(np.float16)
    tight = ("r16f", (27, 4, 3), 0, values.tobytes())
    rows = values.reshape(12, 27).view(np.uint8)
    padded_bytes = np.concatenate([rows, np.full((12, 2), 0x7e, np.uint8)], axis=1).tobytes()  # 0x7e7e: a NaN half
    padded = ("r16f", (27, 4, 3), 0, padded_bytes)
    decoded = wc._decoded(padded)
    assert decoded.shape == (3, 4, 27, 1) and np.isfinite(decoded).all()
    assert np.array_equal(decoded, wc._decoded(tight))
    assert wc.compare_readback({"fog_steady": tight}, {"fog_steady": padded})["resources"]["fog_steady"]["exact"]
    # Negative control: read tight, the padded rows drift a column a row and carry the padding's NaN halves.
    drifted = np.frombuffer(padded_bytes, np.float16)[:values.size].reshape(values.shape)
    assert not np.isfinite(drifted).all() and not np.array_equal(drifted, values)
    # Fewer bytes than the rows need is refused, never decoded short.
    try:
        wc._decoded(("r16f", (27, 4, 3), 0, values.tobytes()[:-2]))
    except ValueError:
        pass
    else:
        raise AssertionError("a short readback must be refused")
