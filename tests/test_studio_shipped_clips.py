"""The Visualizer Studios' shipped audio clips (``assets/production/studio_clips``, ``tools/build_studio_clips.py``).

The source recordings (``logs/visualizer_recordings``) never ship; three short compact windows of them do. Proven here:
the clips stay small; a clip replays through the production Waveform analysis to the drive sequence of its source
window (when that recording is on this machine); the Studios list them with no recordings folder (as a frozen build
does) and default to them; a frozen build can run the clip worker; and Settings never reads them.
"""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
CLIPS = ROOT / "assets" / "production" / "studio_clips"
RECORDINGS = ROOT / "logs" / "visualizer_recordings"
LABELS = ("Rag Doll", "Human", "Growing Pains")


def _manifest():
    return json.loads((CLIPS / "clips.json").read_text(encoding="utf-8"))["clips"]


def _values():
    """Test-owned inputs: the code-owned canonical defaults, never an authored preset."""
    from core.settings.default_contract import require_canonical_default
    return dict(require_canonical_default("widgets.spotify_visualizer"))


# ------------------------------------------------------------------------------------------ budget
def test_exactly_three_named_clips_ship_within_the_size_budget():
    entries = _manifest()
    assert tuple(entry["label"] for entry in entries) == LABELS
    files = sorted(path for path in CLIPS.iterdir() if path.is_file())
    assert sorted(path.name for path in files) == sorted(["clips.json"] + [e["file"] for e in entries])
    assert sum(path.stat().st_size for path in files) < 4_000_000
    for entry in entries:
        data = (CLIPS / entry["file"]).read_bytes()
        assert len(data) < 1_500_000, entry["file"]
        assert hashlib.sha256(data).hexdigest() == entry["sha256"]      # the manifest describes what ships
        assert 10.0 <= entry["seconds"] <= 20.0


def test_a_shipped_clip_decodes_to_valid_native_frames():
    from widgets.spotify_visualizer.compact_clip import load_feature_clip, read_header
    entry = _manifest()[0]
    path = CLIPS / entry["file"]
    clip = load_feature_clip(path)
    header = read_header(path)
    assert len(clip.frames) == entry["frames"] == header["frames"]
    assert header["provenance"]["window_sha256"] == entry["window_sha256"]
    assert header["clipped_samples"] == 0
    assert all(frame.capture_history is not None and frame.real is not None for frame in clip.frames)
    assert clip.frames[0].timestamp_us == header["first_timestamp_us"]


def test_both_product_builds_package_the_clips_and_the_studio_shell():
    """Plain data files by path (never the Qt .rcc Settings registers), in both product workers and every gate."""
    for script in ("build_nuitka.ps1", "build_nuitka_mc_onedir.ps1"):
        source = (ROOT / "scripts" / "venv" / script).read_text(encoding="utf-8")
        assert "--include-data-dir=assets/production/studio_clips=assets/production/studio_clips" in source
        assert "--include-data-dir=ui/studio/qml=ui/studio/qml" in source
    layout = (ROOT / "tools" / "build_layout.ps1").read_text(encoding="utf-8")
    preflight = (ROOT / "tools" / "build_runner.py").read_text(encoding="utf-8")
    for name in ["clips.json"] + [entry["file"] for entry in _manifest()]:
        assert layout.count("assets\\production\\studio_clips\\" + name) == 2    # source and onedir payload gates
        assert f'"studio_clips" / "{name}"' in preflight
    assert layout.count("ui\\studio\\qml\\StudioShell.qml") == 2
    for qrc in (ROOT / "ui" / "resources").glob("*.qrc"):
        assert "studio_clips" not in qrc.read_text(encoding="utf-8")


# --------------------------------------------------------------------------------- replay equivalence
def _drive(data):
    steps = data["steps"]
    return (np.array([s["now_ts"] for s in steps]), np.array([s["body_bands"] for s in steps], dtype=float),
            np.array([[s["intensity"], s["loudness"], s["presence"]] for s in steps], dtype=float),
            [(round(o["timestamp"], 6), o["kind"]) for s in steps for o in s["onsets"]],
            np.array([o["magnitude"] for s in steps for o in s["onsets"]], dtype=float))


@pytest.mark.parametrize("entry", _manifest(), ids=lambda entry: entry["id"])
def test_shipped_clip_replays_the_drive_sequence_of_its_source_window(entry, qt_app, tmp_path):
    source = RECORDINGS / entry["source"]
    if not source.is_file():
        pytest.skip(f"source recording {entry['source']} is not on this machine (logs never ship)")
    from tools.build_studio_clips import window_frames
    from ui.studio.waveform_recorded_inputs import extract
    from widgets.spotify_visualizer.feature_frame import FeatureClip
    frames = window_frames(source, *entry["window_s"])
    original = FeatureClip(name=entry["id"], frames=frames)
    assert original.sha256() == entry["window_sha256"]                     # the window the clip was built from
    reference = tmp_path / f"{entry['id']}.jsonl"
    reference.write_bytes(original.to_jsonl_bytes())                      # float32 PCM, every frame as recorded
    values = _values()
    expected = extract(reference, values, seconds=4.0)
    shipped = extract(CLIPS / entry["file"], values, seconds=4.0)
    now_a, bands_a, levels_a, onsets_a, magnitude_a = _drive(expected)
    now_b, bands_b, levels_b, onsets_b, magnitude_b = _drive(shipped)
    assert len(now_a) >= 300 and np.array_equal(now_a, now_b)            # same production ticks
    assert sum(s["ready"] for s in shipped["steps"]) >= 250
    assert shipped["origin"] == expected["origin"]
    assert onsets_a == onsets_b                                            # the same typed onsets, at the same times
    assert np.max(np.abs(magnitude_a - magnitude_b), initial=0.0) < 2e-3
    assert np.max(np.abs(bands_a - bands_b)) < 5e-4                       # body bands live in 0..1
    scale = np.maximum(np.abs(levels_a), 1.0)
    assert np.max(np.abs(levels_a - levels_b) / scale) < 5e-4             # passage, loudness, presence


# ------------------------------------------------------------------------------------- Studio lookup
def test_studio_fixtures_resolve_to_the_shipped_clips_without_recordings(tmp_path, monkeypatch):
    import ui.studio.waveform_adapter as waveform_adapter
    import ui.studio.waveform_recorded_inputs as inputs
    from ui.studio.adapter import RECORDED
    from ui.studio.registry import create_adapter, studio_modes
    empty = tmp_path / "visualizer_recordings"
    empty.mkdir()
    monkeypatch.setattr(waveform_adapter, "recordings_directory", lambda: empty)
    # Every registered Studio that offers recorded music lists the shipped clips (no hand list of modes).
    adapters = [create_adapter(entry.mode_id if hasattr(entry, "mode_id") else entry) for entry in studio_modes()]
    adapters = [adapter for adapter in adapters if callable(getattr(adapter, "recorded_clips", None))]
    assert len(adapters) >= 2
    for adapter in adapters:
        clips = adapter.recorded_clips()
        assert tuple(c.label for c in clips) == LABELS
        assert all(c.kind == RECORDED and Path(c.description).parent == CLIPS for c in clips)
        assert all(inputs.has_native_history(c.description) for c in clips)
    # A frozen build lists exactly the same clips (the Studio's default source is the first).
    monkeypatch.setattr(inputs, "frozen_build", lambda: True)
    monkeypatch.setattr(waveform_adapter, "recordings_directory", lambda: tmp_path / "absent")
    assert tuple(c.label for c in waveform_adapter.WaveformStudioAdapter().recorded_clips()) == LABELS


def test_a_checkout_lists_its_recordings_after_the_shipped_clips(tmp_path, monkeypatch):
    import ui.studio.waveform_adapter as waveform_adapter
    recording = tmp_path / "some_take.jsonl"
    recording.write_text('{"capture_history":{"capture_serial":1}}\n', encoding="utf-8")
    monkeypatch.setattr(waveform_adapter, "recordings_directory", lambda: tmp_path)
    clips = waveform_adapter.WaveformStudioAdapter().recorded_clips()
    assert tuple(c.label for c in clips) == (*LABELS, "Some Take")


def test_the_shipped_clip_is_the_studios_default_recorded_source(qt_app, tmp_path, monkeypatch):
    """The controller's default source is the first recorded clip: Rag Doll, in a checkout and a frozen build."""
    import ui.studio.waveform_adapter as waveform_adapter
    from ui.studio.controller import StudioController
    monkeypatch.setattr(waveform_adapter, "recordings_directory", lambda: tmp_path / "absent")
    loads = []

    class Probe:
        adapter = waveform_adapter.WaveformStudioAdapter()
        evaluator = waveform_adapter.WaveformStudioEvaluator()
        transport = type("T", (), {"set_duration": lambda self, value: None})()
        _load_clip = loads.append
    StudioController._choose_default_source(Probe())
    assert loads == ["clip:" + _manifest()[0]["id"]]


# -------------------------------------------------------------------------------------- frozen worker
def test_a_frozen_build_runs_the_clip_worker_through_its_own_executable(monkeypatch):
    import ui.studio.waveform_recorded_inputs as inputs
    monkeypatch.setattr(inputs, "frozen_build", lambda: True)
    program, arguments = inputs.worker_command("ui.studio.waveform_recorded_inputs", ["clip", "s", "o", "30"])
    assert program == sys.executable and arguments[:2] == [inputs.WORKER_FLAG, "ui.studio.waveform_recorded_inputs"]
    monkeypatch.setattr(inputs, "frozen_build", lambda: False)
    assert inputs.worker_command("m", [])[1] == ["-m", "m"]
    # Only the Studios' recorded-input workers can be named; anything else is refused before an import.
    assert inputs.run_frozen_worker(["exe", inputs.WORKER_FLAG, "os", "a", "b", "c", "d"]) == 2
    assert inputs.run_frozen_worker(["exe", "/s"]) is None
    text = (ROOT / "main.py").read_text(encoding="utf-8")
    assert f'STUDIO_CLIP_WORKER_FLAG = "{inputs.WORKER_FLAG}"' in text


def test_the_app_entry_point_analyses_a_shipped_clip_as_the_worker(tmp_path):
    """``main.py --studio-clip-worker`` (what a frozen build runs) produces the worker's inputs file."""
    entry = _manifest()[1]
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(_values()), encoding="utf-8")
    output = tmp_path / "inputs.json"
    done = subprocess.run([sys.executable, str(ROOT / "main.py"), "--studio-clip-worker",
                           "ui.studio.waveform_recorded_inputs", str(CLIPS / entry["file"]), str(settings),
                           str(output), "1.5", "/s"], cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["clip"] == str(CLIPS / entry["file"]) and any(step["ready"] for step in data["steps"])


# ---------------------------------------------------------------------------------- Settings dormancy
def _open_spy(monkeypatch):
    seen: list[str] = []
    real_open = io.open

    def spying_open(file, *args, **kwargs):
        if isinstance(file, (str, Path)):
            seen.append(str(Path(file).resolve()))
        return real_open(file, *args, **kwargs)
    monkeypatch.setattr(io, "open", spying_open)
    monkeypatch.setattr("builtins.open", spying_open)
    return seen


def test_opening_settings_never_reads_the_studio_clips(qt_app, tmp_path, monkeypatch):
    from copy import deepcopy
    from PySide6.QtCore import QCoreApplication, QEvent
    from core.animation import AnimationManager
    from core.settings.capability_activation import set_widget_family_activated
    from core.settings.default_contract import require_canonical_default
    from core.settings.settings_manager import SettingsManager
    from core.settings.visualizer_mode_registry import build_visualizer_mode_activation
    import ui.studio.waveform_recorded_inputs as inputs
    from ui.settings_dialog import SettingsDialog

    monkeypatch.setattr(inputs, "_shipped_cache", {})
    clips_root = str(CLIPS.resolve())
    seen = _open_spy(monkeypatch)
    manager = SettingsManager(application="studio_clip_dormancy", storage_base_dir=tmp_path)
    config = deepcopy(require_canonical_default("widgets.spotify_visualizer"))
    config.update({"enabled": True, "visualizers_enabled": True, "mode": "waveform_ribbon",
                   "mode_activation": build_visualizer_mode_activation(["waveform_ribbon"])})
    widgets = manager.get("widgets", {})
    widgets["spotify_visualizer"] = config
    for family in ("media", "visualizers"):
        set_widget_family_activated(widgets, family, True)
    manager.set("widgets", widgets)
    manager.set("sources.folders", [str(tmp_path)])
    dialog = SettingsDialog(manager, AnimationManager())
    try:
        QCoreApplication.processEvents()
        index = dialog._tab_index_for_key("visualizers")
        dialog._switch_tab(index, animate=False)                # the page that hosts the Studio launchers
        QCoreApplication.processEvents()
        assert seen, "the spy saw no file opens at all; it is not observing Settings"
        assert not [path for path in seen if path.startswith(clips_root)]
        # Negative control: the same spy sees the Studio's clip list and a clip load read them.
        from ui.studio.waveform_adapter import WaveformStudioAdapter
        from widgets.spotify_visualizer.compact_clip import read_header
        clips = WaveformStudioAdapter().recorded_clips()
        read_header(clips[0].description)
        assert [path for path in seen if path.startswith(clips_root)]
    finally:
        dialog.close()
        QCoreApplication.processEvents()
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        assert manager.flush(timeout=5.0)
