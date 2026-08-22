"""Gate 6 (one logical clock) and Gate 9 (stale generation cannot publish/reveal).

`Docs/P2_Behavioral_Gates.md`.
"""

from __future__ import annotations

import threading
import time
from dataclasses import replace

import pytest

from widgets.spotify_visualizer import tick_helpers
from widgets.spotify_visualizer.logical_runtime import (
    LatestStateMailbox,
    VisualizerLogicalRuntime,
    coerce_identity,
)


@pytest.fixture
def live_widget(qt_app, qtbot):
    from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
    from PySide6.QtWidgets import QWidget

    parent = QWidget()
    qtbot.addWidget(parent)
    widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
    qtbot.addWidget(widget)
    widget._enabled = True
    widget._thread_manager = _RealishThreadManager()
    yield widget
    widget.cleanup()


class _RealishThreadManager:
    """Enough of ThreadManager for cadence ownership: no GUI timer creation."""

    def schedule_recurring(self, interval_ms, callback):
        raise AssertionError(
            "a GUI recurring timer was created while a logical runtime should "
            "own cadence"
        )

    def run_on_ui_thread(self, func, *args, **kwargs):
        func(*args, **kwargs)


class TestGate6OneLogicalClock:
    def test_ensure_tick_source_creates_exactly_one_runtime(self, live_widget):
        tick_helpers.ensure_tick_source(live_widget)

        assert live_widget._logical_runtime is not None
        assert live_widget._logical_runtime.is_running() is True
        assert live_widget._bars_timer is None, (
            "a GUI fallback timer coexists with the logical runtime"
        )

    def test_calling_ensure_tick_source_again_does_not_create_a_second_runtime(
        self, live_widget
    ):
        tick_helpers.ensure_tick_source(live_widget)
        first = live_widget._logical_runtime

        tick_helpers.ensure_tick_source(live_widget)

        assert live_widget._logical_runtime is first

    def test_the_gui_recurring_timer_is_never_created_while_the_runtime_owns_cadence(
        self, live_widget
    ):
        # _RealishThreadManager.schedule_recurring raises if reached at all.
        tick_helpers.ensure_tick_source(live_widget)
        assert live_widget._bars_timer is None

    def test_stop_tick_source_leaves_no_owner_at_all(self, live_widget):
        tick_helpers.ensure_tick_source(live_widget)

        tick_helpers.stop_tick_source(live_widget)

        assert live_widget._logical_runtime is None
        assert live_widget._bars_timer is None

    def test_the_animation_manager_never_advances_logical_state(self, live_widget):
        """`attach_to_animation_manager` must remain a non-subscribing no-op."""
        import inspect

        source = inspect.getsource(tick_helpers.attach_to_animation_manager)
        assert "_using_animation_ticks = False" in source
        assert "add_tick_listener" not in source

    def test_pause_then_play_does_not_create_a_second_runtime(self, live_widget):
        tick_helpers.ensure_tick_source(live_widget)
        first = live_widget._logical_runtime

        live_widget._spotify_playing = False
        live_widget.handle_media_update({"state": "paused"})
        live_widget._spotify_playing = False
        tick_helpers.ensure_tick_source(live_widget)
        live_widget.handle_media_update({"state": "playing"})
        tick_helpers.ensure_tick_source(live_widget)

        assert live_widget._logical_runtime is first, (
            "pause/play created a second logical runtime"
        )

    def test_a_mode_switch_does_not_create_a_second_runtime(self, live_widget):
        from widgets.spotify_visualizer.audio_worker import VisualizerMode

        tick_helpers.ensure_tick_source(live_widget)
        first = live_widget._logical_runtime

        live_widget.set_visualization_mode(VisualizerMode.SPECTRUM)
        tick_helpers.ensure_tick_source(live_widget)

        assert live_widget._logical_runtime is first

    def test_cleanup_joins_the_runtime(self, live_widget):
        tick_helpers.ensure_tick_source(live_widget)
        runtime = live_widget._logical_runtime

        live_widget.cleanup()

        assert runtime.is_running() is False


class TestGate9StaleGenerationCannotPublishOrReveal:
    def test_a_retired_generation_frame_cannot_enter_the_new_generations_mailbox(self):
        mailbox = LatestStateMailbox()
        mailbox.publish({"stale": True}, generation=5, activation_id=1)

        # Retirement/rebuild moves the mailbox owner to generation 6.
        result = mailbox.take_for_generation(6)

        assert result is None
        assert mailbox.take() is None, "the stale publication was left for anyone to take"

    def test_delayed_old_generation_completion_cannot_win_after_replacement_starts(self):
        mailbox = LatestStateMailbox()

        # Old generation 3 is mid-step when retirement begins.
        old_runtime = VisualizerLogicalRuntime(
            step=lambda ts: mailbox.publish({"gen": 3}, generation=3, activation_id=1),
            interval_s=0.01,
            generation=3,
        )
        old_runtime.start()
        deadline = time.monotonic() + 1.0
        while mailbox.revision == 0 and time.monotonic() < deadline:
            time.sleep(0.005)
        assert old_runtime.stop() is True, "retirement did not join the old runtime"

        # A late, straggling publish from the old generation must still be
        # rejected by a consumer that samples for generation 4.
        mailbox.publish({"gen": 3, "late": True}, generation=3, activation_id=1)
        assert mailbox.take_for_generation(4) is None

    def test_generation_fencing_is_exercised_through_the_real_widget(
        self, qt_app, qtbot
    ):
        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        from PySide6.QtWidgets import QWidget
        from widgets.spotify_visualizer import tick_pipeline

        parent = QWidget()
        qtbot.addWidget(parent)
        widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
        qtbot.addWidget(widget)
        widget._enabled = True
        widget._runtime_generation = 5
        widget._engine = None
        widget._waiting_for_fresh_engine_frame = False
        widget._waiting_for_fresh_frame = False

        tick_pipeline.logical_tick(widget)
        # Retirement: a new generation takes over the same mailbox.
        widget._runtime_generation = 6

        stale = widget._logical_mailbox.take_for_generation(6)

        assert stale is None, (
            "a frame published under a retired generation was handed to the "
            "current generation's presenter"
        )
        widget.cleanup()


class TestGate9GenerationZeroFencing:
    """Slice F - a valid generation 0 must survive as 0, not collapse to -1.

    The first installed run started its logical runtime as `generation=-1`
    because `int(getattr(widget, "_runtime_generation", -1) or -1)` mapped the
    valid initial generation 0 to the invalid sentinel through truthiness. That
    disabled the `generation >= 0` presentation fence for the entire first
    generation. Each bar here fails if that `int(value or -1)` coercion returns.
    """

    def test_coerce_identity_preserves_zero_and_rejects_none(self):
        assert coerce_identity(0) == 0
        assert coerce_identity(1) == 1
        assert coerce_identity(None) == -1
        assert coerce_identity("not-an-int") == -1
        # The exact defect being guarded: the old truthiness coercion.
        assert (0 or -1) == -1
        assert coerce_identity(0) != (0 or -1)

    def test_ensure_tick_source_constructs_generation_zero_as_zero(self, live_widget):
        live_widget._runtime_generation = 0

        tick_helpers.ensure_tick_source(live_widget)

        assert live_widget._logical_runtime.generation == 0, (
            "a valid generation 0 was collapsed to the -1 sentinel at construction"
        )
        assert live_widget._logical_runtime.describe()["generation"] == 0

    def test_publication_under_generation_zero_carries_zero(self, qt_app, qtbot):
        from PySide6.QtWidgets import QWidget

        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        from widgets.spotify_visualizer import tick_pipeline

        parent = QWidget()
        qtbot.addWidget(parent)
        widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
        qtbot.addWidget(widget)
        widget._enabled = True
        widget._engine = None
        widget._waiting_for_fresh_engine_frame = False
        widget._waiting_for_fresh_frame = False
        widget._runtime_generation = 0

        tick_pipeline.logical_tick(widget)

        published = widget._logical_mailbox.peek()
        assert published is not None
        assert published.generation == 0, (
            "a frame published under generation 0 carried the -1 sentinel instead"
        )
        widget.cleanup()

    def test_the_present_fence_is_armed_at_generation_zero(
        self, qt_app, qtbot, monkeypatch
    ):
        """A foreign-generation frame must not reveal while we own generation 0.

        The observable is the reveal side effect, not `present_tick`'s return
        value: `push_gpu_frame` can return False on its own gating, so only a
        spy on `execute_mode_reveal` distinguishes an armed fence (never called)
        from a disabled one (called for the foreign generation).
        """
        from PySide6.QtWidgets import QWidget

        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        from widgets.spotify_visualizer import tick_pipeline

        reveals: list = []
        monkeypatch.setattr(
            tick_pipeline.mode_transition,
            "execute_mode_reveal",
            lambda w, now: reveals.append(now),
        )

        parent = QWidget()
        qtbot.addWidget(parent)
        widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
        qtbot.addWidget(widget)
        widget._enabled = True
        widget._engine = None
        widget._waiting_for_fresh_engine_frame = False
        widget._waiting_for_fresh_frame = False
        widget._runtime_generation = 5
        # A frame from some other generation is sitting in the slot, carrying a
        # decided reveal that only an armed fence will refuse.
        tick_pipeline.logical_tick(widget)
        published = widget._logical_mailbox.take()
        assert published is not None
        foreign = replace(published.state, mode_reveal_ready=True)
        widget._logical_mailbox.publish(
            foreign,
            generation=5,
            activation_id=foreign.activation_id,
        )
        widget._runtime_generation = 0

        tick_pipeline.present_tick(widget)

        assert reveals == [], (
            "the fence was disabled at generation 0, so a foreign-generation "
            "frame drove a reveal"
        )
        widget.cleanup()

    def test_retired_generation_zero_cannot_reveal_into_replacement_one(
        self, qt_app, qtbot, monkeypatch
    ):
        from PySide6.QtWidgets import QWidget

        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        from widgets.spotify_visualizer import tick_pipeline

        reveals: list = []
        monkeypatch.setattr(
            tick_pipeline.mode_transition,
            "execute_mode_reveal",
            lambda w, now: reveals.append(now),
        )

        parent = QWidget()
        qtbot.addWidget(parent)
        widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
        qtbot.addWidget(widget)
        widget._enabled = True
        widget._engine = None
        widget._waiting_for_fresh_engine_frame = False
        widget._waiting_for_fresh_frame = False
        widget._runtime_generation = 0

        # The initial generation 0 publishes a frame carrying a decided reveal...
        tick_pipeline.logical_tick(widget)
        published = widget._logical_mailbox.peek()
        assert published is not None and published.generation == 0
        decided_reveal = replace(published.state, mode_reveal_ready=True)
        widget._logical_mailbox.publish(
            decided_reveal,
            generation=0,
            activation_id=decided_reveal.activation_id,
        )
        # ...then retirement/recreation advances the owner to generation 1.
        widget._runtime_generation = 1

        tick_pipeline.present_tick(widget)

        assert reveals == [], (
            "a retired generation-0 frame revealed into replacement generation 1"
        )
        widget.cleanup()

    def test_retired_generation_one_cannot_publish_into_replacement_two(self):
        mailbox = LatestStateMailbox()
        mailbox.publish({"gen": 1}, generation=1, activation_id=0)

        assert mailbox.take_for_generation(2) is None
        assert mailbox.take() is None


class TestGate4LogicalCodeCannotReachGuiMutation:
    def test_logical_tick_source_contains_no_gui_mutation_calls(self):
        import ast
        import inspect

        from widgets.spotify_visualizer import tick_pipeline

        tree = ast.parse(inspect.getsource(tick_pipeline.logical_tick))
        function = tree.body[0]
        body = function.body[1:] if ast.get_docstring(function) else function.body
        calls = {
            node.func.attr
            for statement in body
            for node in ast.walk(statement)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        forbidden = {
            "show", "hide", "update", "setGeometry", "raise_",
            "begin_mode_fade_in", "execute_mode_reveal",
            "invalidate_shadow_cache_if_needed",
            "apply_pending_mode_transition_layout",
            "start_widget_fade_in",
        }
        hit = calls & forbidden
        assert not hit, f"logical_tick reaches GUI-owned calls: {hit}"

    def test_a_real_logical_step_runs_cleanly_on_a_worker_thread(
        self, qt_app, qtbot
    ):
        """The actual end-to-end proof: run it off-thread and watch for trouble."""
        from PySide6.QtWidgets import QWidget

        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget

        parent = QWidget()
        qtbot.addWidget(parent)
        widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
        qtbot.addWidget(widget)
        widget._enabled = True
        widget._engine = None
        widget._waiting_for_fresh_engine_frame = False
        widget._waiting_for_fresh_frame = False

        errors: list[BaseException] = []

        def _worker():
            from widgets.spotify_visualizer.tick_pipeline import logical_tick

            for _ in range(20):
                try:
                    logical_tick(widget)
                except BaseException as exc:  # noqa: BLE001
                    errors.append(exc)

        thread = threading.Thread(target=_worker)
        thread.start()
        thread.join(5)

        assert not thread.is_alive(), "the worker thread did not finish"
        assert errors == [], f"logical_tick raised off-thread: {errors}"
        assert widget._logical_mailbox.revision > 0, (
            "the worker thread never published a logical frame"
        )
        widget.cleanup()


class TestPublishedActivationIdentityIsReal:
    """`_activation_id` is not a widget attribute; a getattr default of -1
    made this silently always wrong rather than failing loudly.
    """

    def test_the_publish_path_reads_a_real_widget_attribute(self):
        import inspect

        from widgets.spotify_visualizer import tick_pipeline
        from widgets.spotify_visualizer import legacy_render_snapshot_adapter

        source = inspect.getsource(tick_pipeline._publish_logical_state)
        assert '"_activation_id"' not in source, (
            "mode_activation_id reads a widget attribute that does not exist "
            "and would always publish -1"
        )
        assert "capture_legacy_visualizer_logical_frame" in source
        capture_source = inspect.getsource(
            legacy_render_snapshot_adapter.capture_legacy_visualizer_logical_frame
        )
        assert "_last_engine_activation_seen" in capture_source

    def test_a_confirmed_activation_is_published(
        self, qt_app, qtbot, monkeypatch
    ):
        from PySide6.QtWidgets import QWidget

        from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget
        from widgets.spotify_visualizer import tick_pipeline

        parent = QWidget()
        qtbot.addWidget(parent)
        widget = SpotifyVisualizerWidget(parent=parent, bar_count=8)
        qtbot.addWidget(widget)
        widget._enabled = True
        widget._engine = None
        widget._waiting_for_fresh_engine_frame = False
        widget._waiting_for_fresh_frame = False
        widget._last_engine_activation_seen = 4
        monkeypatch.setattr(
            tick_pipeline,
            "consume_engine_bars",
            lambda *_args: (False, False),
        )

        tick_pipeline.logical_tick(widget)

        published = widget._logical_mailbox.peek()
        assert published is not None
        assert published.activation_id == 4
        widget.cleanup()
