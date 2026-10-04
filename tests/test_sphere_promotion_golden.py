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
def current(qt_app):
    from tools.visualizer_replay.sphere_golden import capture

    return capture()


def _segments(document):
    bounds = document["clip"]["segments"]
    edges = [start for _name, start in bounds] + [document["clip"]["frames"]]
    return {name: (start, stop) for (name, start), stop in zip(bounds, edges[1:])}


def test_sphere_matches_its_promotion_golden(golden, current):
    from tools.visualizer_replay.sphere_golden import differences

    lines = differences(golden, current)
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

        def peak(segment):
            a, b = segments[segment]                  # past the previous segment's decay (0.5 s)
            return max(max(f["section_drives"] or [0.0]) for f in frames[a + 45:b])

        # Quiet passages after loud ones (the passage ramp) react less than the loud ones.
        assert launches("flat_low") < launches("kicks") and launches("tail_silence") == 0, name
        assert peak("flat_low") < 0.75 * peak("kicks") and peak("quiet_outro") < 0.75 * peak("kicks"), name
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
    assert any("technical_profile differs: ['sensitivity']" in line for line in lines)


def test_sphere_renders_its_visual_reference(qt_app):
    """Visual parity is a floor, not a ceiling: a deliberate upgrade is reviewed on the before/after
    sheets (``sphere_golden --visual``) and re-recorded (``--write-visual``). Unreviewed drift fails;
    driver noise (a couple of 255ths on a few pixels) does not."""
    pytest.importorskip("OpenGL")
    from tools.visualizer_replay.sphere_golden import VISUAL_CASES, VISUAL_DIR, load_png, render_visual_cases, \
        visual_difference

    images = render_visual_cases()
    assert set(images) == {case[0] for case in VISUAL_CASES}
    drift = {}
    for name, pixels in images.items():
        assert (pixels[..., 3] > 0).sum() > 5000, name             # the sphere is actually drawn
        difference = visual_difference(load_png(VISUAL_DIR / f"{name}.png"), pixels)
        if difference["changed"] > 0.002 or difference["mean"] > 0.05:
            drift[name] = difference
    assert not drift, f"Sphere's rendering differs from its visual reference: {drift}"
