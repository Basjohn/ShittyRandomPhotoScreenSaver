"""Cached Python references for rule (a) (``tools/visualizer_replay/python_references.py``, fast-proof part 2 step 3):
a stored reference reads back exactly what was stored, is found only by exactly its inputs, and a reference whose write
did not finish is never read. The key follows the Python drawing code."""
from __future__ import annotations

import zlib

import numpy as np

from tools.visualizer_replay import python_references as refs


def _python(count=5):
    rng = np.random.default_rng(1)
    frames, pixels = [], []
    for index in range(count):
        image = rng.integers(0, 255, (6, 9, 4), dtype=np.uint8)
        frames.append((image.shape, zlib.compress(image.tobytes(), 1)))
        pixels.append({"region": [0, 0, 9, 6], "hash": str(index)})
    return {"frames": frames, "pixels": pixels, "digests": [f"d{i}" for i in range(count)], "inputs": count,
            "final_mode": "oscilloscope"}


def test_a_reference_reads_back_exactly_what_was_stored(tmp_path):
    python = _python()
    masks = {0: np.eye(6, 9, dtype=bool), 3: np.ones((6, 9), bool)}
    mappings = [((1.0, 2.0, 3.0), (4.0, 5.0, 6.0), 7.0)]
    made_of = {"mode": "bubble", "run": "", "clip": "take"}
    folder = tmp_path / "bubble_key"
    refs.store(folder, made_of, python, masks, mappings, backdrop_frames=5)
    loaded = refs.load(folder, made_of)
    assert loaded is not None
    run, stored_masks, stored_mappings, backdrop = loaded
    assert backdrop == 5 and stored_mappings == mappings
    assert [run["frames"][i] for i in range(5)] == python["frames"]
    assert run["pixels"] == python["pixels"] and run["digests"] == python["digests"]
    assert set(stored_masks) == {0, 3}
    assert (stored_masks[0] == masks[0]).all() and (stored_masks.get(3) == masks[3]).all()
    assert stored_masks.get(1) is None
    # Controls: other inputs find nothing; a write that never finished is not a reference.
    assert refs.load(folder, dict(made_of, clip="other")) is None
    partial = tmp_path / "other_key.partial"
    partial.mkdir()
    (partial / "reference.json").write_text("{}", encoding="utf-8")
    assert refs.load(tmp_path / "other_key", made_of) is None


def test_a_read_reference_can_be_replaced_once_released(tmp_path):
    # Audit 9 M2: the stale path replaces a reference whose frames were read. Released, the store swaps the new one
    # into place; the old one's frames are gone and the new ones read back.
    import sys

    import pytest

    made_of = {"mode": "bubble"}
    folder = tmp_path / "bubble_key"
    refs.store(folder, made_of, _python(), {}, [], backdrop_frames=5)
    loaded = refs.load(folder, made_of)
    loaded[0]["frames"][0]                                   # a frame read: its file is open
    if sys.platform == "win32":
        # Control: not released, the old frames file cannot be removed (the run died here before the fix).
        with pytest.raises(PermissionError):
            refs.store(folder, made_of, _python(count=3), {}, [], backdrop_frames=3)
    refs.release(loaded)
    refs.store(folder, made_of, _python(count=3), {}, [], backdrop_frames=3)
    again = refs.load(folder, made_of)
    assert again is not None and again[3] == 3 and len(again[0]["frames"]) == 3
    assert not (tmp_path / "bubble_key.old").exists() and not (tmp_path / "bubble_key.partial").exists()
    refs.release(again)


def test_the_key_follows_the_run_and_the_drawing_code(monkeypatch):
    frames = ["frame 0", "frame 1"]
    key, made_of = refs.reference_key("bubble", "", {"a": 1}, "take", frames, "display", 1.5)
    assert refs.reference_key("bubble", "", {"a": 1}, "take", frames, "display", 1.5)[0] == key
    assert made_of["renderer_sources"] == refs.renderer_source_hash()
    for changed in (("spectrum", "", {"a": 1}, "take", frames, "display", 1.5),
                    ("bubble", ":b", {"a": 1}, "take", frames, "display", 1.5),
                    ("bubble", "", {"a": 2}, "take", frames, "display", 1.5),
                    ("bubble", "", {"a": 1}, "take", frames[:1], "display", 1.5),
                    ("bubble", "", {"a": 1}, "take", frames, "overscan", 1.5),
                    ("bubble", "", {"a": 1}, "take", frames, "display", 1.0)):
        assert refs.reference_key(*changed)[0] != key
    # The drawing code: one source file's bytes changed makes another key.
    files = refs._source_files()
    assert any(p.suffix == ".py" for p in files) and any(p.suffix == ".frag" for p in files)
    assert any(p.suffix == ".qml" for p in files)
    original = type(files[0]).read_bytes
    monkeypatch.setattr(type(files[0]), "read_bytes",
                        lambda self: original(self) + (b"x" if self == files[0] else b""))
    assert refs.reference_key("bubble", "", {"a": 1}, "take", frames, "display", 1.5)[0] != key
