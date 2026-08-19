"""A mode switch must end with the target mode actually visible.

This bar exists because a whole round of unit gates passed while every installed
mode switch was broken. The logical cadence owner had been moved to a worker
thread, but `logical_tick()` still reached `check_mode_teardown_ready()` ->
`begin_mode_fade_in()`, which invalidates the shadow cache, applies the pending
transition layout and starts the widget fade. Those are QWidget/QPixmap
operations; off the GUI thread they failed inside the broad handlers and the
switch left data flowing with nothing on screen:

    [OVERLAY] reason=cleanup mode=oscilloscope set_state=338 paint=0
              visible=False enabled=False

Every existing test asserted pieces - the runtime stepped, the mailbox
published, the timer existed - and none asserted the only thing that matters:
after a switch, the target mode is revealed.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from widgets.spotify_visualizer import mode_transition, tick_helpers, tick_pipeline


class _Engine:
    def __init__(self, generation=7):
        self._generation = generation

    def get_latest_generation_with_frame(self):
        return self._generation

    def get_latest_generation_with_waveform(self):
        return self._generation


def _switching_widget(*, mode: str, playing: bool):
    now = time.time()
    return SimpleNamespace(
        _mode_teardown_state="waiting_bars",
        _mode_teardown_wait_started_ts=now,
        _mode_transition_ts=now,
        _mode_teardown_target_generation=7,
        _mode_transition_ready=False,
        _mode_transition_phase=3,
        _mode_teardown_block_until_ready=True,
        _vis_mode_str=mode,
        _spotify_playing=playing,
        _should_capture_audio_now=lambda: playing,
        _mode_transition_apply_height_on_resume=False,
    )


@pytest.fixture
def reveal(monkeypatch):
    """Record the GUI-owned reveal work a completed switch must perform."""
    calls: list[str] = []
    monkeypatch.setattr(
        mode_transition,
        "invalidate_shadow_cache_if_needed",
        lambda w: calls.append("shadow"),
    )
    monkeypatch.setattr(
        mode_transition,
        "apply_pending_mode_transition_layout",
        lambda w: calls.append("layout"),
    )
    monkeypatch.setattr(
        mode_transition, "start_widget_fade_in", lambda w: calls.append("fade")
    )
    return calls


class TestASwitchReveals:
    @pytest.mark.parametrize(
        "mode", ["bubble", "spectrum", "sine_wave", "oscilloscope", "devcurve"]
    )
    def test_a_playing_switch_reveals_the_target_mode(self, mode, reveal):
        widget = _switching_widget(mode=mode, playing=True)

        mode_transition.check_mode_teardown_ready(widget, _Engine(), time.time())

        assert widget._mode_teardown_state == "fading_in", (
            f"switching to {mode} never reached its fade-in"
        )
        assert "fade" in reveal, (
            f"switching to {mode} completed without starting the widget fade - "
            "data would flow with nothing visible"
        )
        assert widget._mode_transition_ready is True
        assert widget._mode_teardown_block_until_ready is False

    @pytest.mark.parametrize(
        "mode", ["bubble", "spectrum", "sine_wave", "oscilloscope", "devcurve"]
    )
    def test_a_paused_switch_reveals_the_target_mode(self, mode, reveal):
        widget = _switching_widget(mode=mode, playing=False)

        mode_transition.check_mode_teardown_ready(widget, _Engine(), time.time())

        assert widget._mode_teardown_state == "fading_in"
        assert "fade" in reveal

    def test_the_reveal_applies_the_pending_layout_and_shadow(self, reveal):
        widget = _switching_widget(mode="oscilloscope", playing=True)

        mode_transition.check_mode_teardown_ready(widget, _Engine(), time.time())

        assert "shadow" in reveal and "layout" in reveal


class TestTheRevealWorkIsGuiOwned:
    """The reason the extraction is not finished yet.

    `check_mode_teardown_ready()` is reachable from the logical half of the
    tick, and it performs QWidget/QPixmap work. Until that moves, the cadence
    owner must stay on the GUI thread - so this bar fails loudly if a logical
    runtime is wired up while the GUI-bound work is still in the logical path.
    """

    def test_the_logical_half_still_reaches_gui_owned_reveal_work(self):
        import inspect

        source = inspect.getsource(tick_pipeline.logical_tick)
        assert "_check_mode_teardown_ready" in source, (
            "if the mode-teardown check has moved out of the logical half, this "
            "guard and `ensure_tick_source` should be revisited together"
        )

    def test_the_cadence_owner_stays_on_the_gui_thread_meanwhile(self):
        import inspect

        import ast

        tree = ast.parse(inspect.getsource(tick_helpers.ensure_tick_source))
        function = tree.body[0]
        body = function.body[1:] if ast.get_docstring(function) else function.body
        names = {
            node.attr for statement in body
            for node in ast.walk(statement) if isinstance(node, ast.Attribute)
        } | {
            node.id for statement in body
            for node in ast.walk(statement) if isinstance(node, ast.Name)
        } | {
            alias.name for statement in body
            for node in ast.walk(statement)
            if isinstance(node, (ast.Import, ast.ImportFrom))
            for alias in node.names
        }

        assert "schedule_recurring" in names, (
            "cadence was moved off the GUI thread while the logical half still "
            "performs QWidget work - this is the broken-mode-switch defect"
        )
        assert "VisualizerLogicalRuntime" not in names

    def test_begin_mode_fade_in_is_gui_work(self):
        """Names the exact calls that must move before the thread can own cadence."""
        import inspect

        source = inspect.getsource(mode_transition.begin_mode_fade_in)
        for gui_call in (
            "invalidate_shadow_cache_if_needed",
            "apply_pending_mode_transition_layout",
            "start_widget_fade_in",
        ):
            assert gui_call in source
