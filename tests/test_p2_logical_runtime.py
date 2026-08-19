"""The Qt-free logical cadence owner (Current_Plan section 7).

These bars cover the runtime and its mailbox as a mechanism: the thread contract,
the deadline sequence, generation fencing and lifecycle. Mode fidelity is covered
by the existing all-mode suites.
"""

from __future__ import annotations

import threading
import time

import pytest

from widgets.spotify_visualizer.logical_runtime import (
    LatestStateMailbox,
    VisualizerLogicalRuntime,
)


# ---------------------------------------------------------------------------
# The module must stay Qt-free
# ---------------------------------------------------------------------------


class TestNoQtOwnership:
    def test_the_module_imports_no_qt(self):
        import ast
        import inspect

        from widgets.spotify_visualizer import logical_runtime

        tree = ast.parse(inspect.getsource(logical_runtime))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
                imported.update(alias.name for alias in node.names)
        identifiers = {
            node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
        } | {
            node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
        }

        # Prose in the docstring legitimately names what this module must avoid;
        # only real imports and identifiers count.
        for forbidden in (
            "PySide6",
            "QObject",
            "QTimer",
            "QWidget",
            "QPixmap",
            "QPainter",
            "shiboken",
            "shiboken6",
        ):
            assert not any(forbidden in name for name in imported), (
                f"the logical runtime imported {forbidden}"
            )
            assert forbidden not in identifiers, (
                f"the logical runtime referenced {forbidden}; it must own no Qt "
                "or GL state"
            )

    def test_no_qt_module_is_reachable_from_it(self):
        from widgets.spotify_visualizer import logical_runtime

        for name in vars(logical_runtime):
            assert "Q" != name[:1] or not name[1:2].isupper(), name


# ---------------------------------------------------------------------------
# Latest-wins mailbox
# ---------------------------------------------------------------------------


class TestMailbox:
    def test_publish_then_take_returns_the_state(self):
        mailbox = LatestStateMailbox()
        mailbox.publish("frame", generation=3, activation_id=1)

        publication = mailbox.take()

        assert publication is not None
        assert publication.state == "frame"
        assert publication.generation == 3

    def test_revision_increases_monotonically(self):
        mailbox = LatestStateMailbox()
        revisions = [mailbox.publish(n, generation=1) for n in range(5)]

        assert revisions == [1, 2, 3, 4, 5]
        assert mailbox.revision == 5

    def test_latest_replaces_older_latest(self):
        """No FIFO, no backlog, no catch-up."""
        mailbox = LatestStateMailbox()
        for n in range(10):
            mailbox.publish(n, generation=1)

        publication = mailbox.take()

        assert publication.state == 9
        assert mailbox.take() is None, "the mailbox queued a backlog"

    def test_superseded_states_are_counted_not_queued(self):
        mailbox = LatestStateMailbox()
        for n in range(4):
            mailbox.publish(n, generation=1)

        assert mailbox.superseded_count == 3

    def test_taking_twice_yields_nothing_the_second_time(self):
        mailbox = LatestStateMailbox()
        mailbox.publish("a", generation=1)

        assert mailbox.take() is not None
        assert mailbox.take() is None

    def test_peek_does_not_consume(self):
        mailbox = LatestStateMailbox()
        mailbox.publish("a", generation=1)

        assert mailbox.peek().state == "a"
        assert mailbox.peek().state == "a"
        assert mailbox.take().state == "a"

    def test_a_retired_generation_frame_is_rejected(self):
        mailbox = LatestStateMailbox()
        mailbox.publish("stale", generation=4)

        assert mailbox.take_for_generation(5) is None, (
            "a retired generation's frame reached the replacement runtime"
        )
        assert mailbox.take() is None, "the stale frame was left in the slot"

    def test_a_current_generation_frame_is_delivered(self):
        mailbox = LatestStateMailbox()
        mailbox.publish("live", generation=5)

        publication = mailbox.take_for_generation(5)

        assert publication is not None and publication.state == "live"

    def test_clear_empties_the_slot(self):
        mailbox = LatestStateMailbox()
        mailbox.publish("a", generation=1)
        mailbox.clear()

        assert mailbox.take() is None

    def test_concurrent_publishing_keeps_one_slot(self):
        mailbox = LatestStateMailbox()

        def _publish():
            for n in range(200):
                mailbox.publish(n, generation=1)

        threads = [threading.Thread(target=_publish) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert mailbox.revision == 800
        assert mailbox.take() is not None
        assert mailbox.take() is None


# ---------------------------------------------------------------------------
# The runtime thread
# ---------------------------------------------------------------------------


def _runtime(step, *, interval_s=0.005, generation=1):
    return VisualizerLogicalRuntime(
        step=step, interval_s=interval_s, generation=generation
    )


class TestRuntimeCadence:
    def test_step_timestamps_advance(self):
        seen: list[float] = []
        runtime = _runtime(lambda ts: seen.append(ts))
        runtime.start()
        try:
            deadline = time.monotonic() + 2.0
            while len(seen) < 5 and time.monotonic() < deadline:
                time.sleep(0.005)
        finally:
            runtime.stop()

        assert seen == sorted(seen)

    def test_it_is_not_a_daemon_thread(self):
        runtime = _runtime(lambda ts: None)
        runtime.start()
        try:
            assert runtime._thread.daemon is False, (
                "the logical runtime could silently outlive its owner"
            )
        finally:
            runtime.stop()

    def test_a_missed_deadline_is_skipped_not_replayed(self):
        """A held-off loop must not fire a burst of catch-up steps."""
        calls: list[float] = []

        def _slow(ts):
            calls.append(ts)
            if len(calls) == 1:
                time.sleep(0.12)

        runtime = _runtime(_slow, interval_s=0.005)
        runtime.start()
        try:
            time.sleep(0.35)
        finally:
            runtime.stop()

        # 120ms of stall at a 5ms interval would be ~24 replayed deadlines.
        assert runtime.describe()["skipped_deadlines"] > 0, (
            "the runtime did not record the deadlines it could not service"
        )
        gaps = [b - a for a, b in zip(calls, calls[1:])]
        immediate = [gap for gap in gaps if gap < 0.001]
        assert len(immediate) < 5, "the runtime replayed a backlog of deadlines"

    def test_cadence_can_be_retuned_without_restarting(self):
        runtime = _runtime(lambda ts: None, interval_s=0.05)
        runtime.start()
        try:
            runtime.set_interval(0.01)
            assert runtime.interval_s == pytest.approx(0.01)
            assert runtime.is_running() is True
        finally:
            runtime.stop()

    def test_a_zero_interval_is_clamped(self):
        runtime = _runtime(lambda ts: None, interval_s=0.0)
        assert runtime.interval_s > 0.0


class TestRuntimeLifecycle:
    def test_start_then_stop_joins(self):
        runtime = _runtime(lambda ts: None)
        assert runtime.start() is True
        assert runtime.is_running() is True

        assert runtime.stop() is True
        assert runtime.is_running() is False

    def test_starting_twice_is_a_no_op(self):
        runtime = _runtime(lambda ts: None)
        runtime.start()
        try:
            assert runtime.start() is False
        finally:
            runtime.stop()

    def test_stopping_an_unstarted_runtime_is_safe(self):
        runtime = _runtime(lambda ts: None)
        assert runtime.stop() is True

    def test_stopping_twice_is_safe(self):
        runtime = _runtime(lambda ts: None)
        runtime.start()
        assert runtime.stop() is True
        assert runtime.stop() is True

    def test_stop_is_prompt_even_on_a_long_interval(self):
        """The wait must be interruptible, not a fixed sleep."""
        runtime = _runtime(lambda ts: None, interval_s=5.0)
        runtime.start()
        started = time.monotonic()
        assert runtime.stop(timeout_s=2.0) is True
        assert time.monotonic() - started < 1.0, (
            "stop() waited out the cadence interval instead of waking the loop"
        )

    def test_the_runtime_carries_its_generation(self):
        runtime = _runtime(lambda ts: None, generation=9)
        assert runtime.generation == 9
        assert runtime.describe()["generation"] == 9


class TestRuntimeRobustness:
    def test_a_raising_step_does_not_kill_the_cadence(self):
        calls = {"n": 0}

        def _boom(ts):
            calls["n"] += 1
            raise RuntimeError("logical step blew up")

        runtime = _runtime(_boom)
        runtime.start()
        try:
            deadline = time.monotonic() + 1.5
            while calls["n"] < 5 and time.monotonic() < deadline:
                time.sleep(0.005)
        finally:
            runtime.stop()

        assert calls["n"] >= 5, "one bad step stopped the logical runtime"
        assert runtime.describe()["step_failures"] >= 5

    def test_slow_steps_are_counted(self):
        def _slow(ts):
            time.sleep(0.03)

        runtime = _runtime(_slow, interval_s=0.005)
        runtime.start()
        try:
            time.sleep(0.2)
        finally:
            runtime.stop()

        assert runtime.describe()["slow_steps"] >= 1


class TestGenerationFencing:
    def test_a_retired_runtime_cannot_publish_into_a_new_generation(self):
        mailbox = LatestStateMailbox()
        old = _runtime(
            lambda ts: mailbox.publish("old", generation=1, activation_id=1),
            generation=1,
        )
        old.start()
        try:
            deadline = time.monotonic() + 1.0
            while mailbox.revision == 0 and time.monotonic() < deadline:
                time.sleep(0.005)
        finally:
            assert old.stop() is True

        # The replacement generation samples the same mailbox.
        assert mailbox.take_for_generation(2) is None


# ---------------------------------------------------------------------------
# Gate 3 - scheduler cadence means actual cadence
#
# `Docs/P2_Behavioral_Gates.md` Gate 3. The replaced bar asserted only that ten
# callbacks arrived within two seconds, which passes at 5 Hz and certified a
# runtime that locked at ~64 Hz against an 11.11 ms request with ~29% of
# deadlines missed while `slow_steps=0` and `failures=0`.
#
# Two independent causes were measured on the installed platform:
#
#   time.monotonic()  -> GetTickCount64(),        resolution 15.625 ms
#   Event.wait(t)     -> quantised to the same ~15.6 ms tick
#   time.sleep(t)     -> high-resolution waitable timer, delivers the request
#
# So the deadline sequence now runs on perf_counter() and waits with bounded
# sleeps. This gate rejects the 64 Hz class decisively.
# ---------------------------------------------------------------------------


_TARGET_HZ = 90.0
_INTERVAL_S = 1.0 / _TARGET_HZ


@pytest.fixture(scope="module")
def cadence_run():
    """One real 12-second scheduler-only run, shared by the assertions."""
    stamps: list[float] = []

    def _step(deadline_ts):
        # A cheap representative logical step: a little arithmetic, no I/O.
        stamps.append(time.perf_counter())

    runtime = VisualizerLogicalRuntime(
        step=_step, interval_s=_INTERVAL_S, generation=1
    )
    window = 12.0
    runtime.start()
    started = time.perf_counter()
    try:
        time.sleep(window)
    finally:
        joined = runtime.stop()
    elapsed = time.perf_counter() - started
    gaps = [b - a for a, b in zip(stamps, stamps[1:])]
    described = runtime.describe()
    return {
        "stamps": stamps,
        "gaps": gaps,
        "elapsed": elapsed,
        "hz": len(stamps) / elapsed,
        "described": described,
        "joined": joined,
    }


class TestSchedulerQualification:
    def test_achieved_cadence_meets_the_bar(self, cadence_run):
        hz = cadence_run["hz"]
        assert hz >= 88.0, (
            f"the logical runtime achieved {hz:.2f} Hz against a {_TARGET_HZ:.0f} Hz "
            "request. The installed failure was an extremely stable ~64 Hz "
            "plateau; this is that class of defect."
        )

    def test_the_skipped_deadline_fraction_is_small(self, cadence_run):
        described = cadence_run["described"]
        serviced = described["steps"]
        skipped = described["skipped_deadlines"]
        total = serviced + skipped
        fraction = (skipped / total) if total else 1.0
        assert fraction <= 0.02, (
            f"{fraction * 100:.1f}% of deadlines were skipped "
            f"({skipped} of {total}); the installed failure was ~29%"
        )

    def test_the_typical_gap_is_the_authored_interval(self, cadence_run):
        gaps = sorted(cadence_run["gaps"])
        p50 = gaps[len(gaps) // 2]
        # Deliberately tolerant: the point is to reject the ~15.6ms tick class,
        # not to demand nanosecond precision from a general-purpose OS.
        assert p50 < _INTERVAL_S * 1.35, (
            f"median inter-step gap {p50 * 1000:.2f} ms against an authored "
            f"{_INTERVAL_S * 1000:.2f} ms"
        )

    def test_no_recurring_long_holes(self, cadence_run):
        gaps = cadence_run["gaps"]
        long_gaps = [g for g in gaps if g > 0.033]
        # A general-purpose OS may preempt occasionally; a recurring pattern is
        # the failure. Allow a hard ceiling well under any perceptible rate.
        assert len(long_gaps) <= max(2, int(len(gaps) * 0.001)), (
            f"{len(long_gaps)} gaps exceeded 33 ms under scheduler-only load: "
            f"{[round(g * 1000, 1) for g in long_gaps[:8]]}"
        )

    def test_no_catch_up_burst(self, cadence_run):
        """A missed deadline must be skipped, never replayed as a burst."""
        gaps = cadence_run["gaps"]
        immediate = [g for g in gaps if g < _INTERVAL_S * 0.25]
        assert len(immediate) <= max(2, int(len(gaps) * 0.005)), (
            f"{len(immediate)} steps fired back-to-back, which is a catch-up burst"
        )

    def test_no_step_failed(self, cadence_run):
        assert cadence_run["described"]["step_failures"] == 0

    def test_the_runtime_joined(self, cadence_run):
        assert cadence_run["joined"] is True

    def test_the_run_was_long_enough_to_mean_something(self, cadence_run):
        assert cadence_run["elapsed"] >= 10.0
        assert len(cadence_run["stamps"]) >= 800


class TestTheClockAndWaitAreHighResolution:
    def test_the_deadline_clock_is_not_the_coarse_one(self):
        """`time.monotonic()` is GetTickCount64 on Windows - 15.6 ms."""
        from widgets.spotify_visualizer import logical_runtime

        assert logical_runtime._clock is time.perf_counter, (
            "the deadline sequence is back on a clock too coarse to see an "
            "11.11 ms interval"
        )

    def test_the_wait_does_not_use_the_quantised_event_wait(self):
        import ast
        import inspect
        import textwrap

        from widgets.spotify_visualizer import logical_runtime

        tree = ast.parse(
            textwrap.dedent(
                inspect.getsource(
                    logical_runtime.VisualizerLogicalRuntime._wait_until
                )
            )
        )
        function = tree.body[0]
        body = function.body[1:] if ast.get_docstring(function) else function.body
        attrs = {
            node.attr for statement in body
            for node in ast.walk(statement) if isinstance(node, ast.Attribute)
        }
        assert "sleep" in attrs
        assert "wait" not in attrs, (
            "Event.wait() is quantised to the same ~15.6 ms tick and cannot "
            "deliver the authored cadence"
        )

    def test_the_wait_is_not_a_busy_spin(self):
        from widgets.spotify_visualizer import logical_runtime

        assert logical_runtime._MAX_SLEEP_SLICE_S > 0.0, (
            "a zero-length slice would make the wait a spin"
        )
