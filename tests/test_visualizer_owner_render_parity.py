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
    assert parity.against_baseline(baseline, report)["same"] is True
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
