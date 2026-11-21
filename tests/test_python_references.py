"""Cached Python references for rule (a) (``tools/visualizer_replay/python_references.py``, fast-proof part 2 step 3):
a stored reference reads back exactly what was stored, is found only by exactly its inputs, and a reference whose write
did not finish is never read. The key follows the Python drawing code."""
from __future__ import annotations

import sys
import zlib

import numpy as np
import pytest

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
    assert any(p.suffix == ".py" for p in files) and any(p.suffix == ".qml" for p in files)
    assert any(p.parent.name == "gl_programs" for p in files)
    # Audit 9 M1's control: one GLSL comment added to the conventions every composed shader carries changes the key.
    from rendering.gl_programs import conventions

    monkeypatch.setattr(conventions, "SRPSS_CONVENTIONS_GLSL", conventions.SRPSS_CONVENTIONS_GLSL + "\n// audit 9\n")
    assert refs.reference_key("bubble", "", {"a": 1}, "take", frames, "display", 1.5)[0] != key
    monkeypatch.undo()
    assert refs.reference_key("bubble", "", {"a": 1}, "take", frames, "display", 1.5)[0] == key
    # And the harness's mask code.
    from tools import pixel_tolerance

    monkeypatch.setattr(pixel_tolerance, "translucent_by_backgrounds", lambda *a: None)
    assert refs.reference_key("bubble", "", {"a": 1}, "take", frames, "display", 1.5)[0] != key
    monkeypatch.undo()
    original = type(files[0]).read_bytes
    monkeypatch.setattr(type(files[0]), "read_bytes",
                        lambda self: original(self) + (b"x" if self == files[0] else b""))
    assert refs.reference_key("bubble", "", {"a": 1}, "take", frames, "display", 1.5)[0] != key


def test_a_judge_or_tool_only_change_keeps_the_key(monkeypatch):
    # The key is what draws the reference and its masks and nothing else: the judge, the tolerance rules and the
    # tools around them change without a redraw.
    from tools import pixel_tolerance
    from tools.visualizer_replay import owner_render_parity as parity

    frames = ["frame 0"]
    key = refs.reference_key("bubble", "", {"a": 1}, "take", frames, "display", 1.5)[0]
    monkeypatch.setattr(parity.LiveJudge, "frame", lambda self, *a: None)
    monkeypatch.setattr(parity, "rule_a_verdict", lambda *a, **k: {})
    monkeypatch.setattr(parity, "native_parity", lambda *a, **k: {})
    monkeypatch.setattr(pixel_tolerance, "judge", lambda *a, **k: {})
    monkeypatch.setattr(pixel_tolerance, "judge_delta", lambda *a, **k: {})
    assert refs.reference_key("bubble", "", {"a": 1}, "take", frames, "display", 1.5)[0] == key
    # Nothing of the judge or the tolerance rules is a hashed piece or file (a source change would otherwise redraw).
    pieces = {name for name, _text in refs._harness_sources()}
    assert not [n for n in pieces if any(w in n for w in ("Judge", "judge", "rule_a_verdict", "Tolerance"))], pieces
    assert not any(p.name in ("pixel_tolerance.py", "owner_render_parity.py") for p in refs._source_files())


@pytest.mark.qt
@pytest.mark.skipif(sys.platform != "win32", reason="the stale path's open file is a Windows failure")
def test_the_stale_reference_path_replaces_the_reference_end_to_end(qt_app, monkeypatch, tmp_path):
    # Audit 9 M2 end to end through native_parity: a stored reference is read (its frames file open), the native
    # run's logical digests differ, so the reference is drawn again and stored over it, on Windows.
    import contextlib

    from PySide6.QtGui import QGuiApplication

    from tools.visualizer_replay import owner_render_parity as parity

    frames = ["frame 0", "frame 1"]
    dpr = float(QGuiApplication.primaryScreen().devicePixelRatio())
    real_load = refs.load
    drawn_again = []

    def load_and_read(folder, made):
        loaded = real_load(folder, made)
        loaded[0]["frames"][0]                              # the frames file is open when the stale path runs
        return loaded

    def redraw(mode, script, settings):
        drawn_again.append(True)
        return {**_python(3), "digests": ["native"] * 3, "modes": []}, []

    class Judge:
        def __init__(self, python, *a, **k):
            pass

        def frame(self, *a):
            pass

        def result(self):
            return {"paths": {"first": None}, "rows": [], "judged": [], "carried": [], "failed": [],
                    "classes": {}}

    monkeypatch.setattr(refs, "load", load_and_read)
    monkeypatch.setattr(parity, "_python_reference", redraw)
    monkeypatch.setattr(parity, "parity_script", lambda clip, mode: [("input", 0), ("mode", "spectrum")])
    monkeypatch.setattr(parity, "_python_masks", lambda *a: ({}, 3))
    monkeypatch.setattr(parity, "single_sample_scene_targets", contextlib.nullcontext)
    monkeypatch.setattr(parity, "card_placement", lambda name: contextlib.nullcontext())
    monkeypatch.setattr(parity, "native_shader_control", lambda *a: contextlib.nullcontext())
    monkeypatch.setattr(parity, "LiveJudge", Judge)
    monkeypatch.setattr(parity, "native_drawn_run", lambda *a, **k: {
        "digests": ["native"] * 3, "pixels": [], "frames": [], "native_frames": 0, "native_published": 0, "mapping": {}})
    # The key is made under the stubs (their sources are the drawing code's here), then stored as the first run did.
    key, made_of = refs.reference_key("bubble", "", {}, "take", frames, "display", dpr)
    refs.store(tmp_path / key, made_of, _python(5), {}, [], backdrop_frames=5)
    verdict = parity.native_parity(None, "bubble", "", {}, frames, tmp_path / "out", references=tmp_path,
                                   clip_name="take")
    assert drawn_again and verdict["python_reference"]["state"].startswith("stale")
    again = real_load(tmp_path / key, made_of)
    assert again is not None and again[3] == 3 and len(again[0]["frames"]) == 3
    refs.release(again)
    assert not (tmp_path / f"{key}.old").exists()
