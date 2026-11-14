"""Rendered parity of the production owner on its two process paths, at non-default settings (native core P2:
the design's gate 2, phase-boundary audit M4).

``tools/visualizer_replay/owner_render_parity.py`` builds the real ``QuickDisplayVisualizerOwner`` through the host
binding on a real ``WorkerType.VISUALIZER`` process and again in process, every spec control of the mode and of the
mode it switches to moved off its resting value (derived from the canonical spec, never a preset's value), and draws
what each owner commits to its scene on a hidden production scene (``QQuickRenderControl``: no window is shown).
Every drawn frame must be the same pixels on the two paths, with scene targets single-sampled (a multisampled
target does not repeat its own draw on this GPU: the tool's module notes), through play, a held orbit, a reflected
photograph, a warm pause, a park and a mode switch through the owner's crossfade.

Negative control (R-184): without the retained-frame drop in ``_activate_pending_mode_on_worker`` the worker path
keeps drawing the outgoing mode's last consumed frame for the input at which its fade-out completes, whenever the
switch changes layout profile (Voxel Sphere, Extruded Spectrum, Waveform Ribbon here): tens of thousands of pixels,
up to 31 levels, logical digests equal.
"""
import sys

import pytest


def _modes():
    from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors
    return tuple(d.mode_id for d in iter_all_visualizer_mode_descriptors())


@pytest.fixture(scope="module")
def supervisor():
    from core.process.supervisor import ProcessSupervisor
    from core.process.types import WorkerType
    from core.visualizer_engine.engine_worker import visualizer_worker_main

    supervisor = ProcessSupervisor()
    supervisor.register_worker_factory(WorkerType.VISUALIZER, visualizer_worker_main)
    assert supervisor.start(WorkerType.VISUALIZER)
    yield supervisor
    supervisor.shutdown()


@pytest.fixture
def no_device(monkeypatch):
    """No audio device is opened on either path; the worker's live edges get the gate's bound."""
    from core.visualizer_engine.engine_worker import EngineSession
    from widgets.spotify_visualizer import engine_worker_link

    def _device(_config=None):
        raise AssertionError("a test opened an audio device")

    monkeypatch.setattr("widgets.spotify_visualizer.audio_worker.create_audio_capture", _device)
    monkeypatch.setattr(EngineSession, "LIVE_EDGE_TIMEOUT_S", 10.0)
    engine_worker_link.reset_run_state_for_testing()
    try:
        yield
    finally:
        engine_worker_link.reset_run_state_for_testing()


@pytest.mark.qt
@pytest.mark.skipif(sys.platform != "win32", reason="the hidden production scene needs the Windows QPA GL")
@pytest.mark.parametrize("mode", _modes())
def test_the_worker_path_draws_the_in_process_pixels_at_non_default_settings(qt_app, supervisor, no_device, mode):
    import tools.expanded_visualizer_evidence as evidence
    from tools.visualizer_replay import owner_render_parity as parity

    if qt_app.platformName().strip().lower() != "windows":
        pytest.skip("the hidden production scene needs the Windows QPA GL")
    verdict = parity.rendered_parity(mode, "a", evidence.shipped_clip(5.5).frames, supervisor, sampling="single",
                                     controls=False)
    summary = {key: value for key, value in verdict.items() if key != "region"}
    assert verdict["stayed_on_worker"], summary
    assert verdict["digests_identical"], summary
    assert verdict["meaningful"], summary                     # the frames changed over the run and lit the card
    assert verdict["frames_drawn"][0] == verdict["frames_drawn"][1] == verdict["inputs"] > 300, summary
    assert verdict["paths"]["first"] is None, summary         # every drawn frame, pixel for pixel
    assert verdict["identical"], summary


@pytest.mark.qt
@pytest.mark.skipif(sys.platform != "win32", reason="the hidden production scene needs the Windows QPA GL")
def test_a_drawn_run_does_not_depend_on_the_wall_time_it_takes(qt_app, no_device, monkeypatch):
    """Rule (a)'s run is the replay's, frame for frame, however long the machine takes to draw it (N2.5 leftovers, 14
    Nov). The switch's target waits hidden for its prepared reveal on the replay's clock, while the owner's activation
    deadline is wall time: a run slowed by load passed the deadline mid-wait and the target was failed and reloaded,
    so every frame from there on moved (in process the owner read no progress from its own unshown scene; on the
    worker none before the commit's reply). Here the deadline is shorter than the wait instead of the run slower: the
    frames must equal a run under the product's deadline, and no activation fails. Red before the fix: the target
    failed at the deadline and every later frame differed."""
    import tools.expanded_visualizer_evidence as evidence
    from tools.visualizer_replay import owner_render_parity as parity
    from widgets.spotify_visualizer import engine_worker_link
    from widgets.spotify_visualizer import quick_display_visualizer_owner as owner_module

    if qt_app.platformName().strip().lower() != "windows":
        pytest.skip("the hidden production scene needs the Windows QPA GL")
    mode = "spectrum"
    script = parity.parity_script(evidence.shipped_clip(5.5).frames, mode)
    settings = parity.section_settings(mode, "a")
    failures: list = []
    signal = owner_module.QuickDisplayVisualizerOwner._signal_transition_failure

    def recording(self, reason):
        failures.append(str(reason))
        return signal(self, reason)

    monkeypatch.setattr(owner_module.QuickDisplayVisualizerOwner, "_signal_transition_failure", recording)
    with parity.single_sample_scene_targets():
        reference = parity.drawn_run(mode, script, worker=False, supervisor=None, namespace=None, settings=settings)
        assert failures == []
        # A window shorter than the target's hidden wait (its reveal is 1.5 s of the replay after a 0.25 s fade-out,
        # ~150 drawn frames, several seconds drawn here) and longer than the fade-out's 22 frames.
        monkeypatch.setattr(owner_module, "_ACTIVATION_TRANSACTION_DEADLINE_MS", 2500)
        engine_worker_link.reset_run_state_for_testing()
        hurried = parity.drawn_run(mode, script, worker=False, supervisor=None, namespace=None, settings=settings)
    assert failures == []
    from tools.visualizer_replay.owner_worker_gate import PARTNER

    assert reference["final_mode"] == hurried["final_mode"] == PARTNER[mode]
    a =[entry["hash"] for entry in reference["pixels"]]
    b = [entry["hash"] for entry in hurried["pixels"]]
    assert len(a) == len(b) == reference["inputs"] > 300
    assert [index for index, (x, y) in enumerate(zip(a, b)) if x != y] == []
    assert reference["digests"] == hurried["digests"]


def test_the_non_default_settings_move_every_ranged_control_and_differ_between_variants():
    """The gate's settings come from the canonical spec: every Slider and Range inside its admitted range, the two
    variants apart, the mode's Custom preset selected (no shipped preset's values are drawn)."""
    from core.settings.visualizer_mode_settings import Range, Slider, require_mode_settings
    from core.settings.visualizer_presets import get_custom_preset_index
    from tools.visualizer_replay import owner_render_parity as parity

    for mode in _modes():
        a, b = parity.nondefault_settings(mode, "a"), parity.nondefault_settings(mode, "b")
        assert a[f"preset_{mode}"] == b[f"preset_{mode}"] == get_custom_preset_index(mode)
        ranged = [c for c in require_mode_settings(mode).controls if isinstance(c, (Slider, Range))]
        assert ranged, mode
        for control in ranged:
            low = control.low if getattr(control, "admission_low", None) is None else control.admission_low
            high = control.high if getattr(control, "admission_high", None) is None else control.admission_high
            for values in (a, b):
                value = values[control.key]
                value = value[0] if isinstance(control, Range) else value
                assert low <= value <= high, (mode, control.key, value)
            if high - low > 2 or not control.integer:
                assert a[control.key] != b[control.key], (mode, control.key)
        nudged = parity.nondefault_settings(mode, "a", nudge=True)
        assert any(nudged[c.key] != a[c.key] for c in ranged if isinstance(c, Slider)), mode


def test_a_native_run_is_compared_with_its_accepted_baseline_run_by_run():
    # Rule (a) after a build round: the native frames bit-identical to the accepted run's (``--against``).
    import copy

    from tools.visualizer_replay import owner_render_parity as parity

    run = {"frames_drawn": [549, 549], "native_frames": 359, "differing_inputs": 2, "differing_pixels_total": 7,
           "max_level": 1, "differences": [{"input": 3, "pixels": 4, "max_level": 1}, {"input": 9, "pixels": 3,
                                                                                         "max_level": 1}]}
    baseline = {"results": {"spectrum": run, "spectrum:b": dict(run, native_frames=350)}}
    report = copy.deepcopy(baseline)
    # Without frame hashes only the difference rows compare (audit N29 round 2, L8): equal rows are
    # "difference-identical", never "same" (bit-identical frames are not proved by them).
    verdict = parity.against_baseline(baseline, report)
    assert verdict["same"] is False and verdict["difference_identical"] is True
    assert verdict["runs"]["spectrum"]["by"] == "differences" and verdict["runs"]["spectrum"]["same"] is False
    # Controls: one pixel more in one input, a run missing, a key missing are each a difference.
    moved = copy.deepcopy(report)
    moved["results"]["spectrum"]["differences"][1]["pixels"] = 4
    verdict = parity.against_baseline(baseline, moved)
    assert verdict["same"] is False and verdict["runs"]["spectrum"]["differing"] == ["differences"]
    missing = {"results": {"spectrum": run}}
    assert parity.against_baseline(baseline, missing)["runs"]["spectrum:b"] == {"same": False,
                                                                                 "only_in": "the baseline"}
    keyless = copy.deepcopy(report)
    del keyless["results"]["spectrum"]["differing_pixels_total"]
    assert parity.against_baseline(baseline, keyless)["same"] is False
    assert parity.against_baseline({"results": {}}, {"results": {}})["same"] is False      # nothing compared
    # With frame hashes on both sides the native frames decide: a moved Python reference alone is no difference.
    hashed = {"results": {"spectrum": dict(run, native_hashes=["n0", "n1"], python_hashes=["p0", "p1"])}}
    drifted = copy.deepcopy(hashed)
    drifted["results"]["spectrum"].update(python_hashes=["p0", "p9"], differing_pixels_total=8)
    verdict = parity.against_baseline(hashed, drifted)
    assert verdict["same"] is True and verdict["runs"]["spectrum"]["python_same"] is False
    drifted["results"]["spectrum"]["native_hashes"] = ["n0", "n9"]                     # control: a native frame moved
    verdict = parity.against_baseline(hashed, drifted)
    assert verdict["same"] is False and verdict["runs"]["spectrum"]["native_changed"] == [1]
