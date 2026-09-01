from __future__ import annotations

import pytest

from widgets.spotify_visualizer.bubble_simulation import (
    BubbleSimulation,
    POP_FADE_S,
    RUNTIME_SPAWN_FADE_ACTIVE_S,
    RUNTIME_SPAWN_FADE_IDLE_S,
)


def _settings() -> dict[str, object]:
    return {
        "bubble_big_count": 0,
        "bubble_small_count": 0,
        "bubble_stream_direction": "up",
        "bubble_drift_direction": "none",
        "bubble_surface_reach": 100.0,
        "bubble_trail_strength": 0.0,
        "bubble_ghosting_enabled": False,
    }


def test_runtime_birth_fade_changes_alpha_only_and_uses_sampled_active_duration() -> None:
    sim = BubbleSimulation()
    sim._runtime_spawn_fade_seconds = RUNTIME_SPAWN_FADE_ACTIVE_S
    sim._spawn_bubble_at(False, 0.5, 0.5, "up", 1.0, "none")
    bubble = sim._bubbles[0]
    start = (bubble.x, bubble.y, bubble.radius, bubble.pulse_energy)
    assert bubble.alpha == pytest.approx(0.0)
    assert bubble.fade_in_duration == pytest.approx(0.20)

    # Drive only half of the sampled birth fade. Position may move because the
    # normal simulation remains alive; radius/pulse/domain authority is not
    # rewritten by the fade itself.
    sim.tick(0.10, {"overall": 0.5, "bass": 0.0, "mid": 0.0, "high": 0.0}, _settings())
    assert bubble.alpha == pytest.approx(0.5, abs=0.08)
    assert bubble.radius == pytest.approx(start[2])


def test_idle_runtime_birth_samples_gentler_half_second_fade() -> None:
    sim = BubbleSimulation()
    sim.tick(0.01, {"overall": 0.0}, _settings())
    sim._spawn_bubble_at(False, 0.5, 0.5, "up", 1.0, "none")
    bubble = sim._bubbles[0]
    assert bubble.fade_in_duration == pytest.approx(RUNTIME_SPAWN_FADE_IDLE_S)
    sim.tick(0.10, {"overall": 0.0}, _settings())
    assert bubble.alpha == pytest.approx(0.20, abs=0.05)


def test_pop_fades_concurrently_over_about_four_hundred_ms() -> None:
    sim = BubbleSimulation()
    sim._runtime_spawn_fade_seconds = 0.0
    sim._spawn_bubble_at(False, 0.5, 0.5, "none", 1.0, "none")
    bubble = sim._bubbles[0]
    bubble.alpha = 1.0
    BubbleSimulation._trigger_collision_pop(bubble)

    sim.tick(POP_FADE_S / 2.0, {"overall": 0.0}, _settings())
    assert 0.35 <= bubble.alpha <= 0.65
    sim.tick(POP_FADE_S / 2.0, {"overall": 0.0}, _settings())
    assert bubble not in sim._bubbles


def test_birth_fade_constants_are_not_viewport_or_domain_dependent() -> None:
    assert RUNTIME_SPAWN_FADE_ACTIVE_S == pytest.approx(0.20)
    assert RUNTIME_SPAWN_FADE_IDLE_S == pytest.approx(0.50)
    assert POP_FADE_S == pytest.approx(0.40)


@pytest.mark.parametrize("extent", [(420.0, 280.0), (1400.0, 280.0), (420.0, 1200.0)])
def test_birth_fade_alpha_is_identical_across_canonical_wide_and_tall_domains(extent) -> None:
    sim = BubbleSimulation()
    sim._runtime_spawn_fade_seconds = RUNTIME_SPAWN_FADE_ACTIVE_S
    sim._spawn_bubble_at(False, 0.5, 0.5, "up", 1.0, "none")
    bubble = sim._bubbles[0]
    settings = _settings()
    settings["_bubble_viewport_extent"] = extent

    sim.tick(0.10, {"overall": 0.5}, settings)

    # R-69 guard: lifecycle visibility is an alpha envelope only. CUSTOM
    # viewport/domain shape may reflow motion but cannot attenuate the fade.
    assert bubble.alpha == pytest.approx(0.5, abs=0.08)
