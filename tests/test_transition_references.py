"""The cached Python transition references (native/core/python/transition_references.py; N5.2h caller list point 1):
record stores what the live draw gave, cache reads it back exactly, and a missing, corrupted or differently made entry
is refused with the case named, never drawn in its place. GPU-free."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "native" / "core" / "python"
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))

import transition_references as refs  # noqa: E402

CASES = {("crossfade", 0.5): {"variant": "crossfade", "progress": 0.5, "dpr": 1.5, "photos": "abc"},
         ("crossfade", 1.0): {"variant": "crossfade", "progress": 1.0, "dpr": 1.5, "photos": "abc"}}


def _drawn():
    rng = np.random.default_rng(7)
    return {key: {"frame": rng.integers(0, 256, (6, 8, 4), dtype=np.uint8), "values": {"u_progress": key[1],
                                                                                       "u_pair": (1, 2.5)}}
            for key in CASES}


@pytest.fixture
def cache(tmp_path):
    yield tmp_path
    refs.configure("cache")


def _record(root):
    drawn = _drawn()
    refs.configure("record", root)
    calls = []
    out = refs.references("check", CASES, lambda: calls.append(1) or drawn)
    assert calls == [1] and out is drawn
    refs.configure("cache", root)
    return drawn


def test_record_then_cache_gives_the_same_frames_and_values(cache):
    drawn = _record(cache)
    out = refs.references("check", CASES, lambda: pytest.fail("cache mode never draws"))
    for key in CASES:
        assert np.array_equal(out[key]["frame"], drawn[key]["frame"])
        assert out[key]["values"] == drawn[key]["values"]          # tuples stay tuples
        assert isinstance(out[key]["values"]["u_pair"], tuple)


def test_a_missing_entry_is_refused_with_its_case(cache):
    refs.configure("cache", cache)
    with pytest.raises(refs.MissingReference, match=r"2 of 2 .*'variant': 'crossfade'.*--python-references record"):
        refs.references("check", CASES, lambda: pytest.fail("cache mode never draws"))


def test_a_corrupted_or_differently_made_entry_is_refused(cache):
    _record(cache)
    refs.references("check", CASES, lambda: None)                  # control: the whole cache reads
    name, _made_of = refs.case_key("check", CASES[("crossfade", 0.5)])
    frames = cache / "check" / f"{name}.npz"
    with np.load(frames) as stored:
        frame = stored["frame"].copy()
    frame[0, 0, 0] ^= 1                                            # one level at one pixel
    np.savez_compressed(frames, frame=frame)
    with pytest.raises(refs.MissingReference, match="1 of 2 .*corrupted"):
        refs.references("check", CASES, lambda: None)
    # Another case's inputs (a changed photo digest) have no entry: never a stale frame.
    changed = {key: dict(case, photos="other") for key, case in CASES.items()}
    with pytest.raises(refs.MissingReference, match="2 of 2"):
        refs.references("check", changed, lambda: None)


def test_python_cost_figures_are_stored_baselines_refused_when_missing_or_changed(cache, monkeypatch):
    import json

    monkeypatch.setattr(refs, "COST_BASELINES", cache)
    live = {key: {"python_product_frame_gpu": {"n": 30, "median_ms": 1.25}, "python_opengl": {"p90_ms": key[1]}}
            for key in CASES}
    refs.configure("record", cache)
    assert refs.cost_figures("check", CASES, lambda: live) is live
    refs.configure("cache", cache)
    assert refs.cost_figures("check", CASES, lambda: pytest.fail("cache mode never times")) == live
    path = refs.cost_baseline("check")
    stored = json.loads(path.read_text(encoding="utf-8"))
    first = sorted(stored)[0]
    stored[first]["figures"]["python_opengl"]["p90_ms"] = 99.0                # one figure edited
    path.write_text(json.dumps(stored), encoding="utf-8")
    with pytest.raises(refs.MissingReference, match="1 of 2 .*corrupted"):
        refs.cost_figures("check", CASES, lambda: None)
    with pytest.raises(refs.MissingReference, match="2 of 2 .*no stored Python cost"):
        refs.cost_figures("check", {k: dict(c, dpr=2.0) for k, c in CASES.items()}, lambda: None)
    path.unlink()
    with pytest.raises(refs.MissingReference, match="no readable Python cost baseline"):
        refs.cost_figures("check", CASES, lambda: None)


def test_the_four_checks_read_their_python_references_from_the_cache():
    for name in ("transition_route_check", "fullscreen_pass_check", "background_layer_check",
                 "backdrop_pyramid_check"):
        text = (HARNESS / f"{name}.py").read_text(encoding="utf-8")
        assert f'refs.references("{name}"' in text, name
        assert "refs.add_arguments(parser)" in text and "*refs.child_arguments(args)" in text, name
        assert "refs.configure_from(args)" in text, name
    for name in ("transition_route_check", "background_layer_check"):          # the two that time Python
        assert f'refs.cost_figures("{name}"' in (HARNESS / f"{name}.py").read_text(encoding="utf-8"), name
