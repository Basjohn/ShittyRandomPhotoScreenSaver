"""Gates 2, 4 and 5 - a mode switch must really present, off-thread work must fail loudly.

`Docs/P2_Behavioral_Gates.md`.

Gate 2 replaces the previous mode-switch bar, which built a `SimpleNamespace`
and monkeypatched `start_widget_fade_in` into a list append. That proved a
function was invoked, not that anything was presented - the exact class of gate
that certified a visualizer which rendered nothing.

Here a real `SpotifyVisualizerWidget` under a live Qt application switches into
each of the five modes and must actually publish a target-mode frame and reach
its fade-in.

Gate 4 pins the ownership boundary: the logical half decides readiness as plain
data and never performs the reveal, and a GUI-only reveal called off the GUI
thread raises instead of vanishing into a broad handler.

Gate 5 pins that required handoffs are not optional lookups.
"""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QWidget

from widgets.spotify_visualizer import mode_transition, tick_pipeline
from widgets.spotify_visualizer.audio_worker import VisualizerMode
from widgets.spotify_visualizer.thread_affinity import (
    GuiThreadAffinityError,
    assert_gui_thread,
)


_MODES = [
    (VisualizerMode.BUBBLE, "bubble"),
    (VisualizerMode.SPECTRUM, "spectrum"),
    (VisualizerMode.SINE_WAVE, "sine_wave"),
    (VisualizerMode.OSCILLOSCOPE, "oscilloscope"),
    (VisualizerMode.DEVCURVE, "devcurve"),
]


class _OverlayStub:
    def __init__(self):
        self._vis_mode = ""
        self._activation_id = None
        self._engine_generation = None
        self._pending_mode_resets: set = set()


class _RecordingParent(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._spotify_bars_overlay = _OverlayStub()
        self.frames: list[dict] = []

    def push_spotify_visualizer_frame(self, **kwargs):
        self.frames.append(dict(kwargs))
        return True


class _SettledEngine:
    """An engine that has already delivered the target generation.

    Only the reads the tick performs; no audio, no threads. It lets the real
    transition wait complete the way production does, instead of the test
    reaching in and clearing the teardown block.
    """

    def __init__(self, bar_count: int):
        self._bars = [0.4] * bar_count

    def tick(self):
        return None

    def set_smoothing(self, _value):
        return None

    def get_generation_id(self):
        return 10**6

    def get_activation_id(self):
        return 2

    def get_latest_generation_with_frame(self):
        return 10**6

    def get_latest_generation_with_waveform(self):
        return 10**6

    def get_smoothed_bars(self):
        return list(self._bars)

    def get_latest_authoritative_frame(self):
        return None

    def get_energy_bands(self):
        return None

    def get_pre_agc_energy_bands(self):
        return None

    def get_transient_energy_bands(self):
        return None

    def get_event_scheduler(self):
        return None

    def get_waveform(self):
        return None

    def __getattr__(self, name):
        # Anything else the tick reads is absent in this settled state.
        if name.startswith("get_"):
            return lambda *args, **kwargs: None
        raise AttributeError(name)


def _live_widget(qtbot, mode, *, playing: bool, bar_count=16):
    from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

    parent = _RecordingParent()
    qtbot.addWidget(parent)
    widget = SpotifyVisualizerWidget(parent=parent, bar_count=bar_count)
    qtbot.addWidget(widget)

    widget._enabled = True
    widget.set_visualization_mode(mode)
    widget._spotify_playing = playing
    # Switching away from the default mode starts a real transition that
    # correctly withholds frames until its target generation arrives, so the
    # engine must actually satisfy it rather than the test skipping the wait.
    widget._engine = _SettledEngine(bar_count)
    widget._waiting_for_fresh_engine_frame = False
    widget._waiting_for_fresh_frame = False
    widget._display_bars = [0.4] * bar_count
    widget._display_bars_source_generation = 10**6
    widget._display_bars_source_activation = 2
    widget._has_pushed_first_frame = False
    # The overlay reflects the same source identity the settled engine reports,
    # as it does in production once a frame has been accepted.
    parent._spotify_bars_overlay._engine_generation = 10**6
    parent._spotify_bars_overlay._activation_id = 2
    widget._get_scene_fade_factor = lambda _now: 1.0
    widget._get_gpu_fade_factor = lambda _now: 1.0
    widget._mode_transition_fade_factor = lambda _now: 1.0
    return widget, parent


def _drive(widget, qt_app, ticks: int = 4):
    """Run the real tick until the transition settles, as the timer would."""
    for _ in range(ticks):
        widget._on_tick()
        qt_app.processEvents()


class TestEveryModeActuallyPresents:
    @pytest.mark.parametrize("mode,name", _MODES)
    def test_a_playing_mode_publishes_a_target_mode_frame(
        self, qt_app, qtbot, mode, name
    ):
        widget, parent = _live_widget(qtbot, mode, playing=True)
        parent._spotify_bars_overlay._vis_mode = name

        _drive(widget, qt_app)

        target = [f for f in parent.frames if f.get("vis_mode") == name]
        assert target, f"switching to {name} published no frame at all"
        assert float(target[-1]["fade"]) > 0.0, (
            f"{name} was published with the scene faded out"
        )

    @pytest.mark.parametrize("mode,name", _MODES)
    def test_an_idle_mode_publishes_a_target_mode_frame(
        self, qt_app, qtbot, mode, name
    ):
        """Every mode allows idle reveal, so a paused switch must present too."""
        widget, parent = _live_widget(qtbot, mode, playing=False)
        parent._spotify_bars_overlay._vis_mode = name

        _drive(widget, qt_app)

        target = [f for f in parent.frames if f.get("vis_mode") == name]
        assert target, f"paused switch to {name} published no frame"

    @pytest.mark.parametrize("mode,name", _MODES)
    def test_the_first_frame_handoff_completes_for_every_mode(
        self, qt_app, qtbot, mode, name
    ):
        widget, parent = _live_widget(qtbot, mode, playing=True)
        parent._spotify_bars_overlay._vis_mode = name

        _drive(widget, qt_app)

        assert widget._has_pushed_first_frame is True, (
            f"{name} never completed its first-frame reveal handoff"
        )

    @pytest.mark.parametrize("mode,name", _MODES)
    def test_the_presented_mode_is_the_target_mode(self, qt_app, qtbot, mode, name):
        widget, parent = _live_widget(qtbot, mode, playing=True)
        parent._spotify_bars_overlay._vis_mode = name

        _drive(widget, qt_app)

        assert parent.frames[-1]["vis_mode"] == name, (
            "the old mode remained the presented mode after the switch"
        )


class TestRevealCompletesThroughTheBoundary:
    def test_a_ready_teardown_reaches_the_reveal(self, qt_app, qtbot):
        """Readiness decided in the logical half must still reveal."""
        widget, _parent = _live_widget(qtbot, VisualizerMode.OSCILLOSCOPE, playing=True)
        widget._mode_teardown_state = "waiting_bars"
        widget._mode_teardown_target_generation = 7
        widget._mode_teardown_wait_started_ts = time.time()
        widget._mode_transition_ready = False
        widget._mode_teardown_block_until_ready = True
        widget._mode_teardown_target_generation = 10**6

        widget._on_tick()
        qt_app.processEvents()

        assert widget._mode_teardown_state == "fading_in", (
            "the mode reached readiness but was never revealed"
        )
        assert widget._mode_transition_ready is True

    def test_a_blocked_tick_still_delivers_the_reveal_intent(self, qt_app, qtbot):
        """The fresh-frame gate must not strand a completed transition."""
        widget, parent = _live_widget(qtbot, VisualizerMode.BUBBLE, playing=True)
        widget._waiting_for_fresh_engine_frame = True
        widget._pending_engine_generation = 10**9
        widget._display_bars = [0.0] * 16
        widget._mode_teardown_state = "waiting_bars"
        widget._mode_teardown_target_generation = 7
        widget._mode_teardown_wait_started_ts = time.time()
        widget._mode_transition_ready = False
        widget._mode_teardown_target_generation = 10**6
        before = len(parent.frames)

        widget._on_tick()

        assert widget._mode_teardown_state == "fading_in"
        assert len(parent.frames) == before, (
            "a frame was pushed while the fresh-engine-frame gate was closed"
        )


class TestOwnershipBoundary:
    def test_the_logical_half_only_decides_readiness(self):
        import inspect

        source = inspect.getsource(tick_pipeline.logical_tick)
        for gui_call in (
            "begin_mode_fade_in",
            "invalidate_shadow_cache_if_needed",
            "apply_pending_mode_transition_layout",
            "start_widget_fade_in",
            "execute_mode_reveal",
        ):
            assert gui_call not in source, (
                f"the logical half reaches {gui_call}() - this is the ownership "
                "violation that broke every mode switch"
            )

    def test_the_presentation_half_performs_the_reveal(self):
        import inspect

        assert "execute_mode_reveal" in inspect.getsource(tick_pipeline.present_tick)

    def test_the_evaluator_returns_plain_data(self, qt_app, qtbot):
        widget, _parent = _live_widget(qtbot, VisualizerMode.BUBBLE, playing=True)
        widget._mode_teardown_state = "waiting_bars"
        widget._mode_teardown_target_generation = 7
        widget._mode_teardown_wait_started_ts = time.time()
        widget._mode_transition_ready = False

        result = mode_transition.evaluate_mode_teardown_ready(
            widget,
            SimpleNamespace(
                get_latest_generation_with_frame=lambda: 7,
                get_latest_generation_with_waveform=lambda: 7,
            ),
            time.time(),
        )

        assert isinstance(result, bool)
        assert widget._mode_teardown_state == "waiting_bars", (
            "the evaluator performed the reveal instead of reporting readiness"
        )


class TestGuiOnlyWorkFailsLoudlyOffThread:
    def test_assert_gui_thread_raises_on_a_worker(self, qt_app):
        captured: list[BaseException] = []

        def _worker():
            try:
                assert_gui_thread("execute_mode_reveal")
            except BaseException as exc:  # noqa: BLE001 - recording for the assert
                captured.append(exc)

        thread = threading.Thread(target=_worker)
        thread.start()
        thread.join(5)

        assert captured and isinstance(captured[0], GuiThreadAffinityError), (
            "a GUI-only operation ran on a worker thread without complaint"
        )

    def test_assert_gui_thread_is_silent_on_the_gui_thread(self, qt_app):
        assert_gui_thread("execute_mode_reveal")

    def test_execute_mode_reveal_declares_its_affinity(self):
        import inspect

        source = inspect.getsource(mode_transition.execute_mode_reveal)
        assert "assert_gui_thread" in source

    def test_begin_mode_fade_in_declares_its_affinity(self):
        import inspect

        source = inspect.getsource(mode_transition.begin_mode_fade_in)
        assert "assert_gui_thread" in source


class TestRequiredHandoffsAreNotOptional:
    def test_publication_uses_a_required_mailbox(self):
        import inspect

        source = inspect.getsource(tick_pipeline._publish_logical_state)
        assert 'getattr(widget, "_logical_mailbox"' not in source, (
            "the presentation handoff is optional again - a missing mailbox "
            "would silently produce zero frames"
        )
        assert "widget._logical_mailbox" in source

    def test_a_missing_mailbox_fails_loudly(self):
        widget = SimpleNamespace(_runtime_generation=1, _activation_id=1,
                                 _vis_mode_str="bubble", _logical_runtime=None)

        with pytest.raises(AttributeError):
            tick_pipeline._publish_logical_state(
                widget, 1.0, changed=True, mode_reveal_ready=False
            )
