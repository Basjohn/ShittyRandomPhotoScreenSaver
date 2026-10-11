"""Recorder completion, cancellation and UI use the same private capture owner."""
from types import SimpleNamespace

import numpy as np
import pytest

from tools.visualizer_replay import record
from widgets.spotify_visualizer.energy_bands import EnergyBands
from widgets.spotify_visualizer.feature_frame import load_jsonl
from widgets.spotify_visualizer.transient_bus import TransientEnergyBands


@pytest.fixture
def recording(monkeypatch, tmp_path, qt_app):
    clock = [0.0]
    healthy = [False]
    history = np.linspace(-0.8, 0.8, 4096, dtype="float32")
    band = EnergyBands(0.2, 0.3, 0.1, 0.2)
    worker = SimpleNamespace(is_capture_healthy=lambda: healthy[0], is_capture_starting=lambda: True,
                             _backend=SimpleNamespace(sample_rate=48000))
    engine = SimpleNamespace(
        _audio_worker=worker, acquire=lambda: None, set_playback_state=lambda _: None,
        ensure_started=lambda: None, tick=lambda: [0.4] * 32,
        get_waveform_history=lambda: history, get_waveform=lambda: history[-256:].tolist(),
        get_waveform_count=lambda: 256, get_onset_events=lambda _: (), get_event_scheduler=lambda: None,
        get_transient_energy_bands=TransientEnergyBands, get_energy_bands=lambda: band,
        get_pre_agc_energy_bands=lambda: band, get_bubble_energy_bands=lambda: band,
        get_live_pre_agc_energy_bands=lambda: band, get_pre_agc_analysis_spectrum=lambda: (0.4,) * 64,
        get_musical_level=lambda: (4.0, 0.5),
    )
    closed = []
    monkeypatch.setattr(record, "OUTPUT", tmp_path)
    monkeypatch.setattr(record, "time", SimpleNamespace(perf_counter=lambda: clock[0]))
    monkeypatch.setattr(record, "_configured_engine", lambda: (object(), engine))
    monkeypatch.setattr(record, "_close_configured_engine", lambda *args: closed.append(args))
    return SimpleNamespace(clock=clock, healthy=healthy, history=history, engine=engine, closed=closed, root=tmp_path)


def test_full_minute_starts_after_capture_ready_and_streams_exact_history(recording):
    session = record.RecorderSession("Quiet piano intro")
    session.start()
    recording.clock[0] = 2.0
    session._tick()
    assert session.frame_count == 0
    recording.healthy[0] = True
    session._tick()
    assert session.frame_count == 1 and not session.path.exists()
    recording.clock[0] = 61.99
    session._tick()
    assert session.active
    recording.clock[0] = 62.0
    session._tick()
    clip = load_jsonl(session.path)
    assert clip.frames[-1].timestamp_us - clip.frames[0].timestamp_us == 60_000_000
    assert clip.frames[0].capture_history.pcm_f32le == recording.history.astype("<f4").tobytes()
    assert clip.frames[0].capture_history.capture_serial == clip.frames[-1].capture_history.capture_serial
    assert len(recording.closed) == 1
    assert not session.timer.isActive()
    assert not tuple(recording.root.glob("*.partial"))
    with pytest.raises(RuntimeError, match="single-use"):
        session.start()


@pytest.mark.parametrize("outcome", ["cancel", "lost_capture", "write_failure", "racing_file", "cleanup_failure"])
def test_incomplete_or_failed_capture_never_publishes_and_retires_once(recording, monkeypatch, outcome):
    session = record.RecorderSession("take")
    session.start()
    recording.healthy[0] = True
    session._tick()
    if outcome == "cleanup_failure":
        def fail_close(*args):
            recording.closed.append(args)
            raise RuntimeError("ownership did not drain")
        monkeypatch.setattr(record, "_close_configured_engine", fail_close)
    if outcome == "racing_file":
        session.path.write_bytes(b"keep existing take")
    if outcome == "write_failure":
        session._file.close()
    if outcome == "lost_capture":
        recording.healthy[0] = False
    if outcome == "cancel":
        session.cancel()
    else:
        recording.clock[0] = 60.0
        session._tick()
    assert not session.saved and not session.active and not session.timer.isActive()
    assert (session.error is None) == (outcome == "cancel")
    assert len(recording.closed) == 1
    assert not tuple(recording.root.glob("*.partial"))
    if outcome == "racing_file":
        assert session.path.read_bytes() == b"keep existing take"
    else:
        assert not session.path.exists()


@pytest.mark.parametrize("name", ["", "..", "CON", "take_v2", "take_noevents", "x" * 101])
def test_invalid_or_archival_names_rejected_before_capture(name):
    with pytest.raises(ValueError):
        record.clip_name(name)


def test_ui_records_cancels_and_disables_duplicate_name_without_idle_timer(recording, qt_app):
    from tools.music_recorder import MusicRecorder

    window = MusicRecorder()
    try:
        assert window.session is None
        assert not window.start_button.isEnabled()
        window.name.setText("Friendly title")
        assert window.start_button.isEnabled()
        window.start_recording()
        assert not window.name.isEnabled() and window.cancel_button.isEnabled()
        recording.healthy[0] = True
        window.session._tick()
        assert window.signal.peaks
        window.cancel_recording()
        assert not window.session.timer.isActive() and window.name.isEnabled()
        (recording.root / "friendly_title.jsonl").write_bytes(b"existing")
        window._name_changed()
        assert not window.start_button.isEnabled()
    finally:
        window.close()
