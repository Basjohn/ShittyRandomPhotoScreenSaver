"""Spectrum must have a real idle presentation, without inventing audio.

Current_Plan section 5. Spectrum was the only mode whose startup/card reveal was
gated on real playback: both `startup_staging.mode_allows_idle_reveal()` and
`tick_pipeline._mode_allows_idle_reveal_key()` allowed bubble, sine_wave,
oscilloscope and devcurve while excluding spectrum. Starting on Spectrum with no
music therefore showed no visualizer card at all, and playback had to bring the
whole scene into existence from a dormant state.

Idle Spectrum is presentation state. These bars hold both halves: the card is
allowed to exist while idle, and the idle scene never becomes fake source data.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from widgets.spotify_visualizer.spectrum_presentation_smoothing import (
    _IDLE_BASELINE_MAX,
    _IDLE_BASELINE_MIN,
    idle_spectrum_baseline,
    resolve_widget_spectrum_presentation,
)
from widgets.spotify_visualizer.startup_staging import mode_allows_idle_reveal
from widgets.spotify_visualizer.tick_pipeline import (
    _mode_allows_idle_reveal_key,
    _mode_is_idle_self_animating,
    _mode_requires_authoritative_first_source,
)


def _widget(*, playing: bool, bar_count: int = 48, mode: str = "spectrum"):
    return SimpleNamespace(
        _vis_mode_str=mode,
        _spotify_playing=playing,
        _bar_count=bar_count,
        _spectrum_visual_smoothing_enabled=True,
        _spectrum_visual_smoothing=0.5,
        _spectrum_single_piece=False,
        _spectrum_presentation_bars=[],
        _spectrum_presentation_last_ts=0.0,
        _spectrum_presentation_identity=None,
        _spectrum_presentation_pending=False,
        _display_bars_source_generation=3,
        _display_bars_source_activation=3,
    )


# ---------------------------------------------------------------------------
# All five modes may exist while idle
# ---------------------------------------------------------------------------


class TestIdleRevealGates:
    @pytest.mark.parametrize(
        "mode", ["bubble", "sine_wave", "oscilloscope", "devcurve", "spectrum"]
    )
    def test_every_mode_may_reveal_while_idle(self, mode):
        assert mode_allows_idle_reveal(SimpleNamespace(_vis_mode_str=mode)) is True
        assert _mode_allows_idle_reveal_key(mode) is True

    def test_spectrum_reveals_while_idle_but_stays_source_authoritative(self):
        """The two contracts are separate and must stay separate.

        Spectrum may now show a resting card with no playback, but every bar it
        shows during playback is still purely source-derived, so it must keep
        proving its first reactive frame came from the current activation.
        """
        assert _mode_allows_idle_reveal_key("spectrum") is True
        assert _mode_is_idle_self_animating("spectrum") is False
        assert _mode_requires_authoritative_first_source("spectrum") is True

    @pytest.mark.parametrize("mode", ["bubble", "sine_wave", "oscilloscope", "devcurve"])
    def test_self_animating_modes_are_unchanged(self, mode):
        assert _mode_is_idle_self_animating(mode) is True
        assert _mode_requires_authoritative_first_source(mode) is False

    def test_an_unknown_mode_still_requires_authoritative_source(self):
        assert _mode_allows_idle_reveal_key("not_a_mode") is False
        assert _mode_requires_authoritative_first_source("not_a_mode") is True


# ---------------------------------------------------------------------------
# The idle scene itself
# ---------------------------------------------------------------------------


class TestIdleBaseline:
    def test_the_baseline_is_small_but_visible(self):
        bars = idle_spectrum_baseline(48)
        assert len(bars) == 48
        assert all(0.0 < value <= _IDLE_BASELINE_MAX for value in bars)
        assert max(bars) >= _IDLE_BASELINE_MIN

    def test_the_baseline_is_deterministic(self):
        """Steady idle must settle to one scene revision."""
        assert idle_spectrum_baseline(48) == idle_spectrum_baseline(48)

    def test_the_baseline_has_some_bar_to_bar_variation(self):
        bars = idle_spectrum_baseline(48)
        assert len(set(round(value, 6) for value in bars)) > 1

    def test_degenerate_counts_are_safe(self):
        assert idle_spectrum_baseline(0) == []
        assert idle_spectrum_baseline(-5) == []
        assert len(idle_spectrum_baseline(1)) == 1


class TestIdlePresentation:
    def test_idle_spectrum_presents_the_baseline(self):
        widget = _widget(playing=False)

        bars, changed = resolve_widget_spectrum_presentation(
            widget, [], now_ts=1.0, first_frame=True
        )

        assert bars, "idle Spectrum still presents nothing"
        assert len(bars) == 48
        assert changed is True

    def test_steady_idle_stops_reporting_change(self):
        """Otherwise idle would defeat unchanged-scene suppression."""
        widget = _widget(playing=False)
        resolve_widget_spectrum_presentation(widget, [], now_ts=1.0, first_frame=True)

        for tick in range(2, 12):
            _bars, changed = resolve_widget_spectrum_presentation(
                widget, [], now_ts=float(tick), first_frame=False
            )
            assert changed is False, "idle Spectrum produced a continuous scene stream"

    def test_real_data_wins_over_the_idle_floor(self):
        widget = _widget(playing=False)

        bars, _changed = resolve_widget_spectrum_presentation(
            widget, [0.9] * 48, now_ts=1.0, first_frame=True
        )

        assert all(value == pytest.approx(0.9) for value in bars)

    def test_play_takes_over_from_idle_in_place(self):
        widget = _widget(playing=False)
        idle_bars, _ = resolve_widget_spectrum_presentation(
            widget, [], now_ts=1.0, first_frame=True
        )
        assert max(idle_bars) <= _IDLE_BASELINE_MAX

        widget._spotify_playing = True
        live_bars, changed = resolve_widget_spectrum_presentation(
            widget, [0.8] * 48, now_ts=1.02, first_frame=False
        )

        assert changed is True
        assert max(live_bars) > _IDLE_BASELINE_MAX
        assert len(live_bars) == len(idle_bars), "the bar layout was recreated"

    def test_pause_returns_to_idle_presentation(self):
        widget = _widget(playing=True)
        resolve_widget_spectrum_presentation(
            widget, [0.8] * 48, now_ts=1.0, first_frame=True
        )

        widget._spotify_playing = False
        bars, _changed = resolve_widget_spectrum_presentation(
            widget, [0.0] * 48, now_ts=2.0, first_frame=False
        )

        assert max(bars) <= _IDLE_BASELINE_MAX
        assert min(bars) > 0.0

    def test_other_modes_are_untouched_while_idle(self):
        widget = _widget(playing=False, mode="bubble")

        bars, changed = resolve_widget_spectrum_presentation(
            widget, [0.0] * 48, now_ts=1.0, first_frame=True
        )

        assert bars == [0.0] * 48
        assert changed is False


class TestNoInventedAudio:
    def test_the_idle_scene_never_touches_source_state(self):
        """Presentation only: no source generation/activation may move."""
        widget = _widget(playing=False)
        before = (
            widget._display_bars_source_generation,
            widget._display_bars_source_activation,
        )

        resolve_widget_spectrum_presentation(widget, [], now_ts=1.0, first_frame=True)

        assert (
            widget._display_bars_source_generation,
            widget._display_bars_source_activation,
        ) == before

    def test_the_idle_scene_does_not_mutate_the_source_bars(self):
        widget = _widget(playing=False)
        source = [0.0] * 48

        resolve_widget_spectrum_presentation(
            widget, source, now_ts=1.0, first_frame=True
        )

        assert source == [0.0] * 48, "the idle floor was written back into source"

    def test_the_baseline_has_no_time_or_energy_input(self):
        import ast
        import inspect

        from widgets.spotify_visualizer import spectrum_presentation_smoothing

        tree = ast.parse(
            inspect.getsource(spectrum_presentation_smoothing.idle_spectrum_baseline)
        )
        function = tree.body[0]
        # Compare the executable body only; the docstring legitimately explains
        # which inputs the baseline deliberately avoids.
        body = function.body[1:] if ast.get_docstring(function) else function.body
        names = {
            node.id
            for statement in body
            for node in ast.walk(statement)
            if isinstance(node, ast.Name)
        } | {
            node.attr
            for statement in body
            for node in ast.walk(statement)
            if isinstance(node, ast.Attribute)
        }

        for forbidden in ("time", "random", "energy", "transient", "onset", "engine"):
            assert forbidden not in names, (
                f"the idle baseline referenced {forbidden}; it must stay a pure "
                "function of the bar count"
            )
