"""S19 Voxel Sphere promotion golden: the behavioural reference the shared-Scene3D promotion is
measured against (``Docs/Reference/Sphere_Visualizer.md`` "Promotion golden gate").

A reference, not a lock: an intended reaction change re-records it with
``python -m tools.visualizer_replay.sphere_golden --write`` and documents the measured
difference. An unreviewed difference fails here, with the per-segment change in the message."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.usefixtures("qt_app")


@pytest.fixture(scope="module")
def golden():
    from tools.visualizer_replay.sphere_golden import load_golden

    return load_golden()


@pytest.fixture(scope="module")
def current(qt_app, golden):
    from tools.visualizer_replay.sphere_golden import capture

    return capture(golden)               # from the golden's frozen settings, never the preset files


def _segments(document):
    bounds = document["clip"]["segments"]
    edges = [start for _name, start in bounds] + [document["clip"]["frames"]]
    return {name: (start, stop) for (name, start), stop in zip(bounds, edges[1:])}


def test_sphere_matches_its_promotion_golden(golden, current):
    from tools.visualizer_replay.sphere_golden import differences

    lines = [line for line in differences(golden, current) if not line.startswith("info:")]
    assert not lines, "Sphere differs from its promotion golden (re-record only for an intended, " \
                      "documented change):\n" + "\n".join(lines)


def test_the_golden_holds_the_vocabulary_that_must_not_be_lost(golden):
    """Event ownership (nothing authored in silence), intake and outtake cohorts, local
    fragmentation, and stronger reactions where the music is stronger."""
    segments = _segments(golden)
    for name, preset in golden["presets"].items():
        frames = preset["frames"]
        start, stop = segments["silence"]
        assert all(not f["cohorts"] and max(f["section_drives"] or [0.0]) == 0.0 for f in frames[start:stop]), name

        def launches(segment):
            a, b = segments[segment]
            return sum(1 for prev, cur in zip(frames[a:b], frames[a + 1:b]) if len(cur["cohorts"]) > len(prev["cohorts"]))

        def peak(segment, settle=0.5):
            a, b = segments[segment]                  # past the previous segment's decay
            return max(max(f["section_drives"] or [0.0]) for f in frames[a + int(settle * 90):b])

        # Quiet passages after loud ones react far less once the passage level has fallen (it falls
        # gently, PassageIntensity.LEVEL_FALL_S, as "fast up, gentle down" asks).
        assert launches("flat_low") < launches("kicks") and launches("tail_silence") == 0, name
        assert peak("flat_low", 1.5) < 0.5 * peak("kicks") and peak("quiet_outro", 1.5) < 0.5 * peak("kicks"), name
        assert peak("big_hit") >= 0.5, name
        outtake = {c["outtake"] for f in frames for c in f["cohorts"]}
        assert outtake == ({True} if preset["overrides"].get("sphere_particle_outtake_enabled") else {False}), name
    assert set(golden["presets"]) == {"glass_current", "voxel_bloom", "voxel_bloom_outtake"}


def test_a_behaviour_change_is_caught_and_described(golden, current):
    import copy

    from tools.visualizer_replay.sphere_golden import differences

    changed = copy.deepcopy(current)
    start, _stop = _segments(golden)["kicks"]
    changed["presets"]["glass_current"]["frames"][start + 30]["tracer_drive"] += 0.25
    changed["presets"]["voxel_bloom"]["technical_profile"]["sensitivity"] = 0.9
    lines = differences(golden, changed)
    assert any("glass_current: frames differ from frame" in line for line in lines)
    assert any(line.strip().startswith("kicks:") and "tracer" in line for line in lines)
    # Authored/default values are reported, never failing.
    assert any(line.startswith("info:") and "technical_profile differs: ['sensitivity']" in line for line in lines)


def test_editing_a_curated_preset_never_moves_the_golden(golden, monkeypatch):
    """Presets are authored content (operator 2026-10-04): the golden replays its frozen settings."""
    from core.settings import visualizer_presets
    from tools.visualizer_replay import sphere_golden

    def edited(payload, *args, **kwargs):
        raise AssertionError("the golden must not resolve a curated preset when it holds frozen settings")

    monkeypatch.setattr(visualizer_presets, "resolve_visualizer_activation_payload", edited)
    settings = sphere_golden.case_settings(golden)
    assert set(settings) == set(golden["presets"])
    assert all(value == golden["presets"][name]["settings"] for name, value in settings.items())


def test_sphere_renders_visible_distinct_cases_from_frozen_test_settings(qt_app):
    """Check actual GL output and effect behaviour, not historical artist-chosen pixels.

    The prior pixel golden failed whenever the renderer's intentional reflection filter
    changed. A fixed image is optional REVIEW evidence, not an automatic acceptance oracle.
    Curated preset files have no influence on these frozen test-owned captures.
    """
    pytest.importorskip("OpenGL")
    import numpy as np
    from tools.visualizer_replay.sphere_golden import VISUAL_CASES, render_visual_cases

    images = render_visual_cases()
    assert set(images) == {case[0] for case in VISUAL_CASES}
    for name, pixels in images.items():
        assert pixels.dtype == np.uint8, name
        assert pixels.shape[2] == 4, name
        assert int((pixels[..., 3] > 0).sum()) > 5000, name  # scene actually drawn

    # Paused/quiet and active passages must not collapse into identical rendering.
    for family in ("glass_current", "voxel_bloom"):
        rest, kicks = images[f"{family}_rest"], images[f"{family}_kicks"]
        assert rest.shape == kicks.shape
        assert np.any(rest != kicks), f"{family}: active passage renders identically to silence"

    # Mirrored faces have a real effect over the synthetic backdrop, independent of
    # authored settings and without declaring one historic reflection filter sacred.
    plain, mirrored = images["voxel_bloom_kicks"], images["voxel_bloom_mirror"]
    assert plain.shape == mirrored.shape
    assert np.any(plain != mirrored), "Mirror Cubes had no visible effect"
