"""The OFF/ON oracle must expose delay, scale leaks and changed simulation state."""
from types import SimpleNamespace

import pytest

from tools.visualizer_replay.bubble_fidelity import compare_observations, radius_response, replay_bubbles, tracks


def _clip(count):
    return SimpleNamespace(frames=tuple(SimpleNamespace(
        timestamp_us=index * 11_111, real=None,
        energy=SimpleNamespace(bubble=SimpleNamespace(overall=0.0),
                               transient=SimpleNamespace(onset_detected=False)),
    ) for index in range(count)))


def _observations(radii, *, identity=0):
    # TEST INPUT, NOT A DEFAULT GOLDEN: radius values are physical pixels at
    # the test's chosen 100px projection; identities deliberately survive motion.
    return [[dict(track=identity, radius=radius / 100.0, x=index / 100.0, y=0.5,
                  alpha=1.0, big=False, promoted=False, popping=False, exiting=False,
                  physics=(index,), authority_height=100.0)]
            for index, radius in enumerate(radii)]


def test_comparison_cannot_hide_a_one_frame_response_or_peak_delay():
    off = _observations([4, 5, 6, 6, 5])
    on = _observations([4, 4, 5, 6, 6])
    report = compare_observations(_clip(5), off, on, px_per_unit=100)
    assert report["counts"]["first_radius_change_frame_changed_windows"] == 1
    assert report["counts"]["peak_frame_changed_windows"] == 1
    assert report["responses"][0]["off"]["first_radius_change_frame"] == 1
    assert report["responses"][0]["on"]["first_radius_change_frame"] == 2
    assert report["responses"][0]["off"]["peak_frame"] == 2
    assert report["responses"][0]["on"]["peak_frame"] == 3


def test_comparison_exposes_physical_bound_representation_and_physics_leaks():
    off, on = _observations([3.9, 9]), _observations([5.1, 9.5])
    on[0][0]["physics"] = ("unexpected simulation mutation",)
    report = compare_observations(_clip(2), off, on, px_per_unit=100)
    counts = report["counts"]
    assert counts["over_one_pixel_samples"] == 1
    assert counts["representation_changed_samples"] == 1
    assert counts["outside_radius_or_lifecycle_changed_samples"] == 1
    assert counts["physics_changed_samples"] == 1
    assert report["max_radius_error_px"] == pytest.approx(1.2)


def test_crossing_positions_do_not_swap_bubble_tracks():
    observations = _observations([3, 4, 5], identity=7)
    other = _observations([6, 5, 4], identity=8)
    for left, right in zip(observations, other):
        right[0]["x"] = 0.02 - left[0]["x"]
        left.extend(right)
    observed = tracks(observations)
    assert [sample["radius"] for _frame, sample in observed[7]] == pytest.approx([0.03, 0.04, 0.05])
    assert [sample["radius"] for _frame, sample in observed[8]] == pytest.approx([0.06, 0.05, 0.04])


def test_turn_timing_names_the_first_frame_moving_in_the_new_direction():
    response = radius_response(tracks(_observations([4, 5, 6, 6, 5]))[0], px_per_unit=100)
    assert response["turn_frames"] == [4]


def test_observer_preserves_the_production_logical_and_quick_series(qt_app):
    from dataclasses import asdict
    from core.settings.models import SpotifyVisualizerSettings
    from tests._visualizer_frozen_settings import frozen_visualizer_settings
    from tools.visualizer_replay.driver import load_clips, replay_clip

    clip = load_clips()["isolated_impulse"]
    ordinary = replay_clip(clip, "bubble", settings=frozen_visualizer_settings)
    observed, samples, settings = replay_bubbles(clip, settings=frozen_visualizer_settings)
    assert observed["logical_series"] == ordinary["logical_series"]
    assert observed["metrics"] == ordinary["metrics"]
    assert observed["presentation_trace"] == ordinary["presentation_trace"]
    assert len(samples) == len(clip.frames) and tracks(samples)
    expected = SpotifyVisualizerSettings.from_mapping(
        frozen_visualizer_settings("bubble"), apply_preset_overlay=False, resolve_preset_indices=False)
    assert settings == asdict(expected)
