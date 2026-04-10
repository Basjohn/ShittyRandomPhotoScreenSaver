from __future__ import annotations

import pytest


def test_blob_pockets_rotate_across_family_slots_for_rapid_hits() -> None:
    from widgets.spotify_visualizer.blob_pockets import advance_blob_pocket_state, make_blob_pocket_state

    state = make_blob_pocket_state()
    state = advance_blob_pocket_state(
        state,
        dt=0.016,
        time_seconds=1.0,
        playing=True,
        shaper_enabled=False,
        kick_raw=0.9,
        snare_raw=0.0,
        bass_transient=0.95,
        mid_transient=0.0,
        high_transient=0.0,
        bass_energy=0.8,
        mid_energy=0.1,
        high_energy=0.05,
        overall_energy=0.55,
    )
    state = advance_blob_pocket_state(
        state,
        dt=0.060,
        time_seconds=1.06,
        playing=True,
        shaper_enabled=False,
        kick_raw=0.88,
        snare_raw=0.0,
        bass_transient=0.92,
        mid_transient=0.0,
        high_transient=0.0,
        bass_energy=0.78,
        mid_energy=0.1,
        high_energy=0.05,
        overall_energy=0.52,
    )

    assert state.pockets[0].amplitude > 0.0
    assert state.pockets[1].amplitude > 0.0
    assert state.pockets[0].angle_frac != pytest.approx(state.pockets[1].angle_frac)


def test_blob_pockets_decay_while_preserving_parallel_activity() -> None:
    from widgets.spotify_visualizer.blob_pockets import advance_blob_pocket_state, make_blob_pocket_state

    state = make_blob_pocket_state()
    state = advance_blob_pocket_state(
        state,
        dt=0.016,
        time_seconds=2.0,
        playing=True,
        shaper_enabled=False,
        kick_raw=0.0,
        snare_raw=0.82,
        bass_transient=0.0,
        mid_transient=0.88,
        high_transient=0.34,
        bass_energy=0.15,
        mid_energy=0.62,
        high_energy=0.28,
        overall_energy=0.46,
    )
    first_amp = state.pockets[2].amplitude
    state = advance_blob_pocket_state(
        state,
        dt=0.120,
        time_seconds=2.12,
        playing=True,
        shaper_enabled=False,
        kick_raw=0.0,
        snare_raw=0.0,
        bass_transient=0.0,
        mid_transient=0.0,
        high_transient=0.0,
        bass_energy=0.0,
        mid_energy=0.0,
        high_energy=0.0,
        overall_energy=0.0,
    )

    assert 0.0 < state.pockets[2].amplitude < first_amp


def test_blob_pockets_do_not_spawn_for_shaped_blob() -> None:
    from widgets.spotify_visualizer.blob_pockets import (
        advance_blob_pocket_state,
        build_blob_pocket_uniform_payload,
        make_blob_pocket_state,
    )

    state = make_blob_pocket_state()
    state = advance_blob_pocket_state(
        state,
        dt=0.016,
        time_seconds=3.0,
        playing=True,
        shaper_enabled=True,
        kick_raw=0.95,
        snare_raw=0.90,
        bass_transient=1.0,
        mid_transient=0.8,
        high_transient=0.4,
        bass_energy=0.75,
        mid_energy=0.44,
        high_energy=0.22,
        overall_energy=0.58,
    )
    data, mix = build_blob_pocket_uniform_payload(state)

    assert all(v == pytest.approx(0.0) for idx, v in enumerate(data) if idx % 4 == 1)
    assert all(v == pytest.approx(0.0) for v in mix)


def test_blob_pockets_cooldown_prevents_same_frame_slot_spam() -> None:
    from widgets.spotify_visualizer.blob_pockets import advance_blob_pocket_state, make_blob_pocket_state

    state = make_blob_pocket_state()
    state = advance_blob_pocket_state(
        state,
        dt=0.016,
        time_seconds=4.0,
        playing=True,
        shaper_enabled=False,
        kick_raw=0.92,
        snare_raw=0.0,
        bass_transient=0.96,
        mid_transient=0.0,
        high_transient=0.0,
        bass_energy=0.84,
        mid_energy=0.08,
        high_energy=0.02,
        overall_energy=0.50,
    )
    cursor_after_first = state.kick_cursor
    state = advance_blob_pocket_state(
        state,
        dt=0.010,
        time_seconds=4.01,
        playing=True,
        shaper_enabled=False,
        kick_raw=0.91,
        snare_raw=0.0,
        bass_transient=0.95,
        mid_transient=0.0,
        high_transient=0.0,
        bass_energy=0.83,
        mid_energy=0.08,
        high_energy=0.02,
        overall_energy=0.50,
    )

    assert state.kick_cursor == cursor_after_first


def test_blob_pockets_can_rotate_on_fresh_rapid_alternating_hits() -> None:
    from widgets.spotify_visualizer.blob_pockets import advance_blob_pocket_state, make_blob_pocket_state

    state = make_blob_pocket_state()
    state = advance_blob_pocket_state(
        state,
        dt=0.016,
        time_seconds=5.0,
        playing=True,
        shaper_enabled=False,
        kick_raw=0.28,
        snare_raw=0.0,
        bass_transient=0.20,
        mid_transient=0.0,
        high_transient=0.0,
        bass_energy=0.18,
        mid_energy=0.08,
        high_energy=0.02,
        overall_energy=0.14,
    )
    cursor_after_first = state.kick_cursor
    state = advance_blob_pocket_state(
        state,
        dt=0.020,
        time_seconds=5.02,
        playing=True,
        shaper_enabled=False,
        kick_raw=0.92,
        snare_raw=0.0,
        bass_transient=0.96,
        mid_transient=0.0,
        high_transient=0.0,
        bass_energy=0.48,
        mid_energy=0.08,
        high_energy=0.02,
        overall_energy=0.34,
    )

    assert state.kick_cursor > cursor_after_first
    assert state.pockets[0].amplitude > 0.0
    assert state.pockets[1].amplitude > 0.0
