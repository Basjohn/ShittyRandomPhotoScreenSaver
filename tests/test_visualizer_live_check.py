"""CLI overrides must survive the same curated/Custom activation used by the live owner."""
import json
import pytest
from tools.visualizer_live_check import _prepare_profile, parse_display_off
from core.settings.visualizer_presets import resolve_visualizer_activation_payload


def test_display_off_schedule_is_sorted_pairs_and_rejects_overlap_or_nonpositive_times():
    assert parse_display_off("50:10,20:5") == [(20.0, 25.0), (50.0, 60.0)]
    for bad in ("20:0", "0:5", "20:10,25:5", "x:1"):
        with pytest.raises(ValueError):
            parse_display_off(bad)


def test_isolated_profile_overrides_survive_curated_activation_without_editing_presets(tmp_path):
    appdata=tmp_path/'source'
    (appdata/'SRPSS').mkdir(parents=True)
    (appdata/'SRPSS_MC').mkdir()
    source=appdata/'SRPSS_MC/settings_v2.json'
    before=json.dumps({'snapshot':{'widgets':{'spotify_visualizer':{'mode':'waveform_ribbon','preset_waveform_ribbon':0}}}})
    source.write_text(before)
    overrides={'waveform_ribbon_mist_enabled':False,'waveform_ribbon_input_gain':.37}
    root=_prepare_profile(tmp_path/'run','waveform_ribbon',1,overrides,appdata_root=appdata)
    raw=json.loads((root/'SRPSS_MC/settings_v2.json').read_text())['snapshot']['widgets']['spotify_visualizer']
    activation=resolve_visualizer_activation_payload(raw,mode='waveform_ribbon')
    assert activation.is_custom
    assert {key:activation.resolved_config[key] for key in overrides}==overrides
    assert source.read_text()==before


def test_observation_reads_the_applied_worker_instead_of_requested_settings(qt_app):
    from tests.test_waveform_ribbon_source_policy import configured
    from tools.eb_live_phases import waveform_worker_configuration
    engine=configured()
    try:
        engine.set_input_gain(.37)
        engine._audio_worker.set_audio_block_size(256)
        actual=waveform_worker_configuration(engine)
        assert actual['waveform_ribbon_input_gain']==.37
        assert actual['waveform_ribbon_audio_block_size']==256
        # Only the analysis settings Waveform owns are reported (its sensitivity and floor ones are retired).
        from core.settings.visualizer_mode_registry import get_owned_mode_setting_keys
        owned=set(get_owned_mode_setting_keys('waveform_ribbon','technical').values())
        assert set(actual)-{'waveform_ribbon_raw_musical_signals'}==owned
    finally:engine.force_stop()


# -- The profile copy lives only while the run needs it (operator, 7 Nov 2026: 9.8 GB over 36 runs) ----------


class _FakeRunner:
    """Stands in for the saver child: no process, exits at once with ``returncode``."""

    def __init__(self, returncode):
        self.returncode = returncode
        self.pid = 0

    def poll(self):
        return self.returncode


def _fake_appdata(tmp_path):
    appdata = tmp_path / "appdata"
    (appdata / "SRPSS" / "cache" / "steam").mkdir(parents=True)
    (appdata / "SRPSS" / "cache" / "steam" / "art.bin").write_bytes(b"\0" * 4096)
    (appdata / "SRPSS" / "gmail_imap.enc").write_bytes(b"encrypted")
    (appdata / "SRPSS" / "settings_v2.json").write_text('{"shared": true}')
    (appdata / "SRPSS_MC").mkdir()
    (appdata / "SRPSS_MC" / "settings_v2.json").write_text(json.dumps(
        {"snapshot": {"widgets": {"spotify_visualizer": {"mode": "bubble", "preset_bubble": 0}}}}))
    return appdata


def _run_live_check(monkeypatch, tmp_path, returncode, report=None):
    import tools.visualizer_live_check as live_check
    from tools import artifact_paths

    monkeypatch.setenv("APPDATA", str(_fake_appdata(tmp_path)))
    monkeypatch.setattr(live_check.subprocess, "Popen", lambda *a, **k: _FakeRunner(returncode))
    if report is not None:
        monkeypatch.setattr(live_check, "_report", report)
    with artifact_paths.use_root(tmp_path / ".artifacts"):
        out = artifact_paths.evidence_dir("visualizers/bubble", "live_check", "unit")
        try:
            code = live_check.main(["--mode", "bubble", "--preset", "1", "--load", "none", "--visible",
                                    "--clip", "none", "--out", str(out)])
        except RuntimeError as exc:
            return exc, out
    return code, out


def test_a_finished_run_keeps_its_settings_and_deletes_the_profile_copy(monkeypatch, tmp_path):
    seen = {}

    def report(args, out, *rest):
        # The copy exists for the whole run, up to the report.
        seen["profile_during_report"] = (out / "profile" / "SRPSS_MC" / "settings_v2.json").is_file()
        return 0

    code, out = _run_live_check(monkeypatch, tmp_path, 0, report)
    assert code == 0 and seen["profile_during_report"]
    assert not (out / "profile").exists(), "the profile copy outlived the run"
    mc = json.loads((out / "run_settings_v2_mc.json").read_text())
    assert mc["snapshot"]["widgets"]["spotify_visualizer"]["mode"] == "bubble"
    assert json.loads((out / "run_settings_v2.json").read_text()) == {"shared": True}


def test_a_failed_run_still_deletes_the_profile_copy(monkeypatch, tmp_path):
    outcome, out = _run_live_check(monkeypatch, tmp_path, 1)
    assert isinstance(outcome, RuntimeError) and "Live runner exited 1" in str(outcome)
    assert not (out / "profile").exists(), "a failed run left the profile copy behind"
    assert (out / "run_settings_v2_mc.json").is_file()


# -- the age chain on the engine-worker path (native core P2 gate 3 preparation) ----------------------------------

def _write_trace(path, *, worker, publishes=True, seconds=6):
    """A synthetic ``--frame-trace``: 90 Hz publications, sync 5 ms and swap 12 ms after each publish, a 2 ms tick.
    ``worker``: the main side records only the frames it took (every other one), at the worker's publish stamp."""
    from tools.frame_trace_report import HEADER, MAGIC, RECORD

    base, period, rows = 10 ** 12, 1e9 / 90, [(10 ** 12, 63, -1, 0)]          # LIFECYCLE_END: startup over
    for revision in range(1, 90 * seconds + 1):
        if worker and revision % 2:
            continue                                                            # superseded in the worker's slots
        publish = base + int(revision * period)
        if publishes:
            rows.append((publish, 1, revision, publish - 2_000_000))
        rows += [(publish + 5_000_000, 4, revision, 0), (publish + 12_000_000, 6, revision, 0)]
    data = HEADER.pack(MAGIC, 1, RECORD.size, 0) + b"".join(
        RECORD.pack(ts, event, 0, revision, logical, 0) for ts, event, revision, logical in rows)
    path.write_bytes(data)
    return path


def test_the_worker_paths_trace_reads_the_same_age_chain_as_in_process(tmp_path):
    from tools.visualizer_live_check import analyse_trace

    inproc = analyse_trace(_write_trace(tmp_path / "in.bin", worker=False))
    worker = analyse_trace(_write_trace(tmp_path / "worker.bin", worker=True), worker_path=True)
    assert (inproc["path"], worker["path"]) == ("in_process", "engine_worker")
    for key in ("consumed_age_at_sync_ms", "publish_to_swap_ms", "tick_to_publish_ms", "newest_age_at_sync_ms"):
        assert inproc[key] == worker[key], key
    assert worker["consumed_age_at_sync_ms"]["median"] == 5.0 and worker["publish_to_swap_ms"]["median"] == 12.0
    assert worker["tick_to_publish_ms"]["median"] == 2.0
    # Phase-boundary audit L2: this worker trace superseded every second frame, and main recorded none of them, so a
    # waiting count read from it would be zero by construction. It is reported as not measured, never as a zero.
    assert worker["revisions_waiting_at_sync"] is None and "not measured" in worker["revisions_waiting_at_sync_note"]
    assert inproc["revisions_waiting_at_sync"]["median"] == 0
    # The worker publishes at 90/s although main took 45/s: the revisions are the worker's publication count.
    assert abs(worker["revisions_per_s"] - 90.0) < 1.0 and abs(worker["publish_records_per_s"] - 45.0) < 1.0
    assert abs(inproc["revisions_per_s"] - 90.0) < 1.0
    assert inproc["revisions_per_s"] == inproc["publish_records_per_s"]


def test_negative_controls_the_worker_rate_needs_the_flag_and_the_chain_needs_the_stamps(tmp_path):
    from tools.visualizer_live_check import analyse_trace

    # Read as in process, the taken frames alone halve the worker's publication rate.
    assert abs(analyse_trace(_write_trace(tmp_path / "w.bin", worker=True))["revisions_per_s"] - 45.0) < 1.0
    # Before the stamps (no publish records on the worker path) the age chain is empty, not measured.
    blind = analyse_trace(_write_trace(tmp_path / "blind.bin", worker=True, publishes=False), worker_path=True)
    assert blind["publish_records_per_s"] == 0 and blind["revisions_per_s"] is None
    assert blind["consumed_age_at_sync_ms"] is None and blind["publish_to_swap_ms"] is None
    assert blind["tick_to_publish_ms"] is None


def test_the_tick_and_mains_work_are_labelled_by_process_and_by_what_was_measured():
    """Phase-boundary audit L2: the shares are wall time (an upper bound on GIL hold) and thread CPU time, named as
    such; no field claims a GIL share, and each path states how its audio was delivered."""
    from tools.visualizer_live_check import revision_rate, tick_shares

    worker = tick_shares({"frame_take_ms": {"median": 0.5, "cpu_mean": 0.25}, "publish_records_per_s": 40.0,
                          "revisions_per_s": 90.0, "tick_to_publish_ms": {"median": 2.0}}, worker_path=True)
    assert worker["tick_process"] == "engine_worker" and worker["main_per_frame_work"].startswith("frame take")
    assert worker["main_wall_share"] == 0.02 and worker["main_cpu_share"] == 0.01
    assert worker["worker_tick_wall_share"] == worker["tick_wall_share"] == 0.18
    assert worker["worker_tick_ms"] == {"median": 2.0}
    inproc = tick_shares({"logical_tick_wall_share": 0.21, "logical_tick_ms": {"median": 2.3, "cpu_mean": 1.0},
                          "tick_to_publish_ms": {"median": 2.0}, "revisions_per_s": 90.0}, worker_path=False)
    assert inproc["tick_process"] == "main" and inproc["main_wall_share"] == 0.21 and inproc["tick_wall_share"] == 0.18
    assert inproc["main_cpu_share"] == 0.09                    # what the tick's thread ran: below its wall share
    assert inproc["worker_tick_ms"] is None and inproc["worker_tick_wall_share"] is None
    for summary in (worker, inproc):
        assert not any("gil" in key for key in summary), sorted(summary)
    assert worker["audio_delivery"] != inproc["audio_delivery"]
    assert "cadence" in worker["audio_delivery"] and "capture thread" in inproc["audio_delivery"]
    # A run from before the CPU reading (no ``cpu_mean``) reports the wall share and no CPU share.
    older = tick_shares({"frame_take_ms": {"median": 0.5}, "publish_records_per_s": 40.0, "revisions_per_s": 90.0,
                         "tick_to_publish_ms": {"median": 2.0}}, worker_path=True)
    assert older["main_wall_share"] == 0.02 and older["main_cpu_share"] is None
    # A new session's revisions start again: the step back adds nothing.
    assert revision_rate([(0, 1), (10 ** 9, 91), (2 * 10 ** 9, 5), (3 * 10 ** 9, 95)]) == 60.0
    assert revision_rate([(0, 1)]) is None


# -- the recorded-PCM receipt on both paths (native core P2 gate 3 record) --------------------------------------------

_IDENTITY = (2, 5, 7)          # (runtime generation, engine generation, activation id)


def _worker_frame(*, playing=True, source=_IDENTITY[1:], bands=(.7, .6, .5), loudness=8.0, intensity=.8):
    """The worker-to-main seam with the real body: ``WaveformRibbonFrameRuntime.advance`` (the Waveform body) ticked
    at 90 Hz on synthetic inputs until ready and 2 s beyond, its frame built as the capture builds it, wrapped in the
    logical frame and carried through the frame codec (what main decodes from the worker's slot)."""
    from core.visualizer_engine import frame_codec
    from core.settings.visualizer_mode_settings import require_mode_settings
    from tests._visualizer_frozen_settings import frozen_visualizer_settings
    from widgets.spotify_visualizer.render_state import (
        VisualizerCommonState, VisualizerLogicalFrame, WaveformRibbonFrame)
    from widgets.spotify_visualizer.waveform_ribbon_frame_runtime import WaveformRibbonFrameRuntime

    frozen = dict(frozen_visualizer_settings("waveform_ribbon"))
    runtime = WaveformRibbonFrameRuntime()
    configuration = runtime.configure({control.key: frozen[control.key]
                                       for control in require_mode_settings("waveform_ribbon").controls})
    tick, extra = 0, None
    while extra is None or extra > 0:
        snapshot = runtime.advance(onsets=(), now_ts=tick / 90, playing=playing, identity=_IDENTITY,
                                   source_identity=source, controls=configuration.controls, body_bands=bands,
                                   intensity=intensity, loudness=loudness, presence=1.0)
        tick += 1
        if snapshot.ready:
            extra = 180 if extra is None else extra - 1
        assert tick < 5000, "the body never became ready"
    state = WaveformRibbonFrame(snapshot.packet, configuration.scene(snapshot), snapshot.time, snapshot.travel,
                                snapshot.rotation_angle, snapshot.rotation_speed, snapshot.drives, snapshot.realized,
                                ready=snapshot.ready, particle_serial=snapshot.particle_serial,
                                passage=snapshot.passage)
    logical = VisualizerLogicalFrame(
        runtime_generation=_IDENTITY[0], engine_generation=_IDENTITY[1], activation_id=_IDENTITY[2],
        source_generation=source[0], source_activation_id=source[1], mode_id="waveform_ribbon", playing=playing,
        logical_timestamp=tick / 90, source_timestamp=tick / 90, changed=True, present_frame=True,
        mode_reveal_ready=True, common=VisualizerCommonState(bars=(), bar_count=0), mode_state=state)
    return frame_codec.decode(frame_codec.encode(logical))


def test_a_rendered_worker_frame_is_the_receipt_only_when_audible_input_reached_a_live_body():
    from tools.eb_live_phases import note_waveform_frame

    receipt = {}
    assert note_waveform_frame(receipt, _worker_frame())
    assert receipt["rendered_frames"] == 1 and receipt["first_identity"] == list(_IDENTITY)
    assert receipt["passage_max"] > 0.
    # Negative controls through the same seam: silence, a paused body and another activation's source all leave the
    # body's passage at 0 or the frame not live, so none of them is a receipt.
    for kwargs in ({"bands": (0., 0., 0.), "loudness": 0., "intensity": 0.}, {"playing": False},
                   {"source": (4, 7)}):
        assert not note_waveform_frame(receipt, _worker_frame(**kwargs)), kwargs
    assert receipt["rendered_frames"] == 1


def test_the_pcm_check_is_path_aware_and_fails_closed_on_both_paths():
    from tools.visualizer_live_check import waveform_pcm_receipt

    row = {"bands": [.4, .2, .1], "playing": True, "identity": [2, 5, 7], "source_identity": [5, 7], "bursts": 3}
    receipt = {"rendered_frames": 120, "first_identity": [2, 5, 7], "passage_max": .6, "burst_serial": 9}
    inproc = waveform_pcm_receipt({"waveform_signals": [row]}, recorded=True, worker_path=False)
    assert inproc["waveform_signal_samples"] == 1 and inproc["waveform_burst_serial"] == 3
    assert inproc["waveform_pcm_evidence"].startswith("body input rows")
    worker = waveform_pcm_receipt({"waveform_frame_receipt": receipt}, recorded=True, worker_path=True)
    assert worker["waveform_signal_samples"] == 0 and worker["waveform_burst_serial"] == 9
    assert worker["waveform_pcm_evidence"].startswith("rendered worker frames")
    # Negative controls: no evidence on either path is an error (the 8 Nov gate 3 worker run's crash was the in-process
    # check reading an empty list on the worker path); a stale or silent row is no evidence; rendered frames do not
    # stand in for the input rows in process; input rows on the worker path mean the body ran in main.
    for phases, worker_path in (({}, True), ({"waveform_frame_receipt": {"rendered_frames": 0}}, True), ({}, False),
                                ({"waveform_signals": [dict(row, source_identity=[4, 7])]}, False),
                                ({"waveform_signals": [dict(row, bands=[0., 0., 0.])]}, False),
                                ({"waveform_frame_receipt": receipt}, False),
                                ({"waveform_signals": [row], "waveform_frame_receipt": receipt}, True)):
        with pytest.raises(RuntimeError):
            waveform_pcm_receipt(phases, recorded=True, worker_path=worker_path)
    # Without a recording nothing is required.
    assert waveform_pcm_receipt({}, recorded=False, worker_path=True)["waveform_pcm_evidence"] is None
