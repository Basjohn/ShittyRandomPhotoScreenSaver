"""Cached Python references for rule (a) (``tools/visualizer_replay/python_references.py``, fast-proof part 2 step 3):
a stored reference reads back exactly what was stored, is found only by exactly its inputs, and a reference whose write
did not finish is never read. The key is the run's inputs; a lookup follows what the drawing used (its recorded
sources, N5.6): an edit to one of them makes the reference stale, a native-only edit keeps it."""
from __future__ import annotations

import sys
import zlib

import numpy as np
import pytest

from tools.visualizer_replay import python_references as refs


#: A drawing's recorded sources for stored test references: real repository files (``recording`` records only those).
_FILES = ["rendering/quick/visualizer/__init__.py", "rendering/gl_programs/conventions.py"]


def _drawing(files=_FILES):
    return {"files": list(files), "digest": refs.drawing_digest(files)}


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
    refs.store(folder, made_of, python, masks, mappings, backdrop_frames=5, drawing=_drawing())
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
    refs.store(folder, made_of, _python(), {}, [], backdrop_frames=5, drawing=_drawing())
    loaded = refs.load(folder, made_of)
    loaded[0]["frames"][0]                                   # a frame read: its file is open
    if sys.platform == "win32":
        # Control: not released, the old frames file cannot be removed (the run died here before the fix).
        with pytest.raises(PermissionError):
            refs.store(folder, made_of, _python(count=3), {}, [], backdrop_frames=3, drawing=_drawing())
    refs.release(loaded)
    refs.store(folder, made_of, _python(count=3), {}, [], backdrop_frames=3, drawing=_drawing())
    again = refs.load(folder, made_of)
    assert again is not None and again[3] == 3 and len(again[0]["frames"]) == 3
    assert not (tmp_path / "bubble_key.old").exists() and not (tmp_path / "bubble_key.partial").exists()
    refs.release(again)


def _edited(monkeypatch, rel: str) -> None:
    """``rel``'s bytes read as edited (one byte appended) for the rest of the test."""
    import pathlib

    original = pathlib.Path.read_bytes
    target = (refs.ROOT / rel).resolve()
    monkeypatch.setattr(pathlib.Path, "read_bytes",
                        lambda self: original(self) + (b"x" if self.resolve() == target else b""))


def test_the_key_follows_the_run_and_the_shared_sources(monkeypatch):
    frames = ["frame 0", "frame 1"]
    key, made_of = refs.reference_key("bubble", "", {"a": 1}, "take", frames, "display", 1.5)
    assert refs.reference_key("bubble", "", {"a": 1}, "take", frames, "display", 1.5)[0] == key
    assert made_of["shared_sources"] == refs.shared_source_hash()
    for changed in (("spectrum", "", {"a": 1}, "take", frames, "display", 1.5),
                    ("bubble", ":b", {"a": 1}, "take", frames, "display", 1.5),
                    ("bubble", "", {"a": 2}, "take", frames, "display", 1.5),
                    ("bubble", "", {"a": 1}, "take", frames[:1], "display", 1.5),
                    ("bubble", "", {"a": 1}, "take", frames, "overscan", 1.5),
                    ("bubble", "", {"a": 1}, "take", frames, "display", 1.0)):
        assert refs.reference_key(*changed)[0] != key
    # The shared sources are the scene's QML (no Python module: those are each reference's recorded drawing set).
    files = refs._source_files()
    assert any(p.suffix == ".qml" for p in files) and not any(p.suffix == ".py" for p in files)

    def shared():
        return refs.reference_key("bubble", "", {"a": 1}, "take", frames, "display", 1.5)[1]["shared_sources"]

    # Audit 9 M1's control: one GLSL comment added to the conventions every composed shader carries changes them.
    from rendering.gl_programs import conventions

    monkeypatch.setattr(conventions, "SRPSS_CONVENTIONS_GLSL", conventions.SRPSS_CONVENTIONS_GLSL + "\n// audit 9\n")
    assert shared() != made_of["shared_sources"]
    monkeypatch.undo()
    assert shared() == made_of["shared_sources"]
    # And the harness's mask code.
    from tools import pixel_tolerance

    monkeypatch.setattr(pixel_tolerance, "translucent_by_backgrounds", lambda *a: None)
    assert shared() != made_of["shared_sources"]
    monkeypatch.undo()
    _edited(monkeypatch, str(files[0].relative_to(refs.ROOT)))
    assert shared() != made_of["shared_sources"]


def test_a_lookup_follows_the_recorded_drawing_sources(tmp_path, monkeypatch):
    frames = ["frame 0"]
    key, made_of = refs.reference_key("bubble", "", {}, "take", frames, "display", 1.5)
    refs.store(tmp_path / key, made_of, _python(), {}, [], backdrop_frames=5, drawing=_drawing())
    loaded = refs.load(tmp_path / key, made_of)
    assert loaded is not None
    refs.release(loaded)
    # Control: one recorded file's bytes changed, the reference is stale (and the key itself is unchanged: the run's
    # inputs, so the redraw replaces it in place).
    _edited(monkeypatch, _FILES[1])
    assert refs.stale_sources({"files": _FILES, "digest": made_digest(_FILES)}) == "a recorded file's bytes changed"
    assert refs.load(tmp_path / key, made_of) is None
    assert refs.reference_key("bubble", "", {}, "take", frames, "display", 1.5)[0] == key
    monkeypatch.undo()
    # A recorded file gone is stale too; a reference without recorded sources cannot be stored.
    assert refs.stale_sources({"files": ["rendering/no_such_module.py"], "digest": "0"}).startswith("recorded files")
    with pytest.raises(ValueError):
        refs.store(tmp_path / "other", made_of, _python(), {}, [], backdrop_frames=5, drawing={"files": []})


def made_digest(files):
    """The digest ``files`` had before ``_edited`` (read with the original bytes)."""
    import hashlib

    digest = hashlib.sha256()
    for rel in files:
        digest.update(rel.encode() + b"\0" + open(refs.ROOT / rel, "rb").read() + b"\0")
    return digest.hexdigest()


def test_a_native_only_edit_keeps_the_key_and_the_reference(tmp_path, monkeypatch):
    # The native route is no drawing source of a Python reference (an OpenGL scene never imports it, N5.6); an edit to
    # it keeps the key (pre-change, the key hashed the whole visualizer package: seen failing) and the stored reference.
    native = "rendering/quick/visualizer/native_route.py"
    frames = ["frame 0"]
    key, made_of = refs.reference_key("bubble", "", {}, "take", frames, "display", 1.5)
    _edited(monkeypatch, native)
    assert (refs.ROOT / native).read_bytes().endswith(b"x")
    edited_key, edited_made_of = refs.reference_key("bubble", "", {}, "take", frames, "display", 1.5)
    assert edited_key == key and edited_made_of == made_of
    monkeypatch.undo()
    refs.store(tmp_path / key, made_of, _python(), {}, [], backdrop_frames=5, drawing=_drawing())
    _edited(monkeypatch, native)
    loaded = refs.load(tmp_path / key, edited_made_of)
    assert loaded is not None
    refs.release(loaded)


def test_recording_holds_what_the_drawing_used_and_not_what_the_process_loaded():
    # Loaded before the recording, never used during it: not a drawing source (the native side of a native run).
    import rendering.quick.visualizer.native_route  # noqa: F401

    with refs.recording() as used:
        from rendering.quick.visualizer.implementations import extruded_bubble  # noqa: F401  (a lazy import)
    files = used.files()
    assert "rendering/quick/visualizer/implementations/extruded_bubble.py" in files
    # Its top-level imports and its packages enter with it.
    assert "rendering/quick/visualizer/implementations/__init__.py" in files
    assert "rendering/quick/visualizer/__init__.py" in files and "rendering/__init__.py" in files
    assert "rendering/quick/visualizer/native_route.py" not in files
    assert not [rel for rel in files if rel.split("/")[0] in ("tools", "tests")]
    # Control: the same already-loaded route named by an import statement during the recording is recorded.
    with refs.recording() as named:
        import rendering.quick.visualizer.native_route  # noqa: F401,F811
    assert "rendering/quick/visualizer/native_route.py" in named.files()
    # Control: a function of a loaded module that runs during the recording is recorded (sys.monitoring).
    from rendering.quick import bootstrap

    with refs.recording() as ran:
        bootstrap.native_visualizer_route_wanted("opengl")
    assert "rendering/quick/bootstrap.py" in ran.files()


def test_a_judge_or_tool_only_change_keeps_the_key(monkeypatch):
    # The key is what draws the reference and its masks and nothing else: the judge, the tolerance rules and the
    # tools around them change without a redraw.
    from tools import pixel_tolerance
    from tools.visualizer_replay import owner_render_parity as parity

    frames = ["frame 0"]
    key = refs.reference_key("bubble", "", {"a": 1}, "take", frames, "display", 1.5)
    monkeypatch.setattr(parity.LiveJudge, "frame", lambda self, *a: None)
    monkeypatch.setattr(parity, "rule_a_verdict", lambda *a, **k: {})
    monkeypatch.setattr(parity, "native_parity", lambda *a, **k: {})
    monkeypatch.setattr(pixel_tolerance, "judge", lambda *a, **k: {})
    monkeypatch.setattr(pixel_tolerance, "judge_delta", lambda *a, **k: {})
    assert refs.reference_key("bubble", "", {"a": 1}, "take", frames, "display", 1.5) == key
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
        import rendering.quick.visualizer  # noqa: F401  (the drawing used a repository module: its recorded source)
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
    refs.store(tmp_path / key, made_of, _python(5), {}, [], backdrop_frames=5, drawing=_drawing())
    verdict = parity.native_parity(None, "bubble", "", {}, frames, tmp_path / "out", references=tmp_path,
                                   clip_name="take")
    assert drawn_again and verdict["python_reference"]["state"].startswith("stale")
    again = real_load(tmp_path / key, made_of)
    assert again is not None and again[3] == 3 and len(again[0]["frames"]) == 3
    refs.release(again)
    assert not (tmp_path / f"{key}.old").exists()
