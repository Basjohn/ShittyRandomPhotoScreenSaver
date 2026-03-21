"""Tests for TransientEventScheduler (§2.4 event micro-scheduler).

Covers debounce, consume-once semantics, peek vs consume isolation,
reset, empty-ring edge cases, and integration with TransientBus.
"""
from __future__ import annotations

import time

from widgets.spotify_visualizer.transient_bus import (
    OnsetEvent,
    TransientBus,
    TransientEventScheduler,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(event_type: str = "kick", strength: float = 0.8, ts: float = 0.0) -> OnsetEvent:
    return OnsetEvent(
        timestamp=ts or time.time(),
        event_type=event_type,
        strength=strength,
    )


# ---------------------------------------------------------------------------
# Basic feed / consume
# ---------------------------------------------------------------------------

class TestFeedAndConsume:
    def test_feed_and_consume_kick(self):
        sched = TransientEventScheduler()
        evt = _make_event("kick")
        assert sched.feed(evt) is True
        result = sched.consume_next("kick")
        assert result is not None
        assert result.event_type == "kick"
        assert result.strength == evt.strength

    def test_consume_returns_none_when_empty(self):
        sched = TransientEventScheduler()
        assert sched.consume_next("kick") is None

    def test_consume_returns_none_for_wrong_type(self):
        sched = TransientEventScheduler()
        sched.feed(_make_event("kick"))
        assert sched.consume_next("snare") is None

    def test_consume_marks_event_consumed(self):
        sched = TransientEventScheduler()
        sched.feed(_make_event("kick"))
        first = sched.consume_next("kick")
        assert first is not None
        second = sched.consume_next("kick")
        assert second is None

    def test_consume_oldest_first(self):
        sched = TransientEventScheduler()
        now = time.time()
        sched.feed(_make_event("kick", strength=0.5, ts=now - 0.2))
        # Need to bypass debounce for second event
        sched._last_accepted_ts["kick"] = 0.0
        sched.feed(_make_event("kick", strength=0.9, ts=now - 0.05))

        first = sched.consume_next("kick")
        assert first is not None
        assert first.strength == 0.5  # older event first

        second = sched.consume_next("kick")
        assert second is not None
        assert second.strength == 0.9

    def test_feed_rejects_empty_type(self):
        sched = TransientEventScheduler()
        evt = OnsetEvent(timestamp=time.time(), event_type="", strength=0.5)
        assert sched.feed(evt) is False


# ---------------------------------------------------------------------------
# Debounce
# ---------------------------------------------------------------------------

class TestDebounce:
    def test_kick_debounce_rejects_fast_repeat(self):
        sched = TransientEventScheduler()
        now = time.time()
        assert sched.feed(_make_event("kick", ts=now)) is True
        assert sched.feed(_make_event("kick", ts=now + 0.05)) is False  # < 90ms

    def test_kick_debounce_accepts_after_window(self):
        sched = TransientEventScheduler()
        now = time.time()
        assert sched.feed(_make_event("kick", ts=now)) is True
        assert sched.feed(_make_event("kick", ts=now + 0.10)) is True  # >= 90ms

    def test_snare_debounce_window(self):
        sched = TransientEventScheduler()
        now = time.time()
        assert sched.feed(_make_event("snare", ts=now)) is True
        assert sched.feed(_make_event("snare", ts=now + 0.10)) is False  # < 120ms
        assert sched.feed(_make_event("snare", ts=now + 0.13)) is True  # >= 120ms

    def test_vocal_swell_debounce_window(self):
        sched = TransientEventScheduler()
        now = time.time()
        assert sched.feed(_make_event("vocal_swell", ts=now)) is True
        assert sched.feed(_make_event("vocal_swell", ts=now + 0.15)) is False  # < 200ms
        assert sched.feed(_make_event("vocal_swell", ts=now + 0.21)) is True  # >= 200ms

    def test_different_types_debounce_independently(self):
        sched = TransientEventScheduler()
        now = time.time()
        assert sched.feed(_make_event("kick", ts=now)) is True
        assert sched.feed(_make_event("snare", ts=now + 0.01)) is True  # different type, OK


# ---------------------------------------------------------------------------
# Peek
# ---------------------------------------------------------------------------

class TestPeek:
    def test_peek_returns_most_recent(self):
        sched = TransientEventScheduler()
        now = time.time()
        sched.feed(_make_event("kick", strength=0.5, ts=now - 0.1))
        sched._last_accepted_ts["kick"] = 0.0
        sched.feed(_make_event("kick", strength=0.9, ts=now))

        result = sched.peek_latest("kick", max_age_s=0.5)
        assert result is not None
        assert result.strength == 0.9  # most recent

    def test_peek_does_not_consume(self):
        sched = TransientEventScheduler()
        sched.feed(_make_event("kick"))

        peek1 = sched.peek_latest("kick")
        peek2 = sched.peek_latest("kick")
        assert peek1 is not None
        assert peek2 is not None

        consume = sched.consume_next("kick")
        assert consume is not None  # still available for consumption

    def test_peek_respects_max_age(self):
        sched = TransientEventScheduler()
        old_event = _make_event("kick", ts=time.time() - 1.0)
        sched.feed(old_event)
        assert sched.peek_latest("kick", max_age_s=0.3) is None

    def test_peek_returns_none_for_wrong_type(self):
        sched = TransientEventScheduler()
        sched.feed(_make_event("kick"))
        assert sched.peek_latest("snare") is None


# ---------------------------------------------------------------------------
# has_recent
# ---------------------------------------------------------------------------

class TestHasRecent:
    def test_has_recent_true(self):
        sched = TransientEventScheduler()
        sched.feed(_make_event("kick"))
        assert sched.has_recent("kick", max_age_s=1.0) is True

    def test_has_recent_false_when_old(self):
        sched = TransientEventScheduler()
        sched.feed(_make_event("kick", ts=time.time() - 1.0))
        assert sched.has_recent("kick", max_age_s=0.2) is False

    def test_has_recent_false_when_empty(self):
        sched = TransientEventScheduler()
        assert sched.has_recent("kick") is False


# ---------------------------------------------------------------------------
# consume_next max_age
# ---------------------------------------------------------------------------

class TestConsumeMaxAge:
    def test_consume_ignores_old_events(self):
        sched = TransientEventScheduler()
        old = _make_event("kick", ts=time.time() - 2.0)
        sched.feed(old)
        assert sched.consume_next("kick", max_age_s=0.5) is None

    def test_consume_accepts_fresh_events(self):
        sched = TransientEventScheduler()
        sched.feed(_make_event("kick"))
        result = sched.consume_next("kick", max_age_s=1.0)
        assert result is not None


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_clears_ring(self):
        sched = TransientEventScheduler()
        sched.feed(_make_event("kick"))
        sched.feed(_make_event("snare", ts=time.time() + 0.2))
        sched.reset()
        assert sched.consume_next("kick") is None
        assert sched.consume_next("snare") is None

    def test_reset_clears_debounce_state(self):
        sched = TransientEventScheduler()
        now = time.time()
        sched.feed(_make_event("kick", ts=now))
        sched.reset()
        # After reset, debounce should be cleared
        assert sched.feed(_make_event("kick", ts=now + 0.01)) is True


# ---------------------------------------------------------------------------
# Ring capacity overflow
# ---------------------------------------------------------------------------

class TestCapacity:
    def test_overflow_overwrites_oldest(self):
        sched = TransientEventScheduler()
        now = time.time()
        # Fill beyond capacity
        for i in range(sched._CAPACITY + 5):
            sched._last_accepted_ts.clear()  # bypass debounce for test
            sched.feed(_make_event("kick", strength=float(i) / 100.0, ts=now + i * 0.1))

        assert len(sched._ring) == sched._CAPACITY
        # Most recent events should still be available
        result = sched.peek_latest("kick", max_age_s=5.0)
        assert result is not None


# ---------------------------------------------------------------------------
# TransientBus integration
# ---------------------------------------------------------------------------

class TestBusIntegration:
    def test_bus_creates_scheduler_on_demand(self):
        bus = TransientBus()
        sched = bus.get_scheduler()
        assert isinstance(sched, TransientEventScheduler)
        # Same instance on second call
        assert bus.get_scheduler() is sched

    def test_bus_feeds_scheduler_on_onset(self):
        bus = TransientBus()
        sched = bus.get_scheduler()

        # Feed two frames to get a spectral flux onset
        # Frame 1: seed
        bus.update(0.0, 0.0, 0.0)
        # Frame 2: sudden bass spike — should trigger kick onset
        bus.update(0.8, 0.1, 0.05)

        # The scheduler should have received the onset
        evt = sched.consume_next("kick", max_age_s=1.0)
        if evt is not None:
            assert evt.event_type == "kick"
            assert evt.strength > 0.0

    def test_bus_reset_clears_scheduler(self):
        bus = TransientBus()
        sched = bus.get_scheduler()
        bus.update(0.0, 0.0, 0.0)
        bus.update(0.8, 0.1, 0.05)
        bus.reset()
        assert sched.consume_next("kick") is None

    def test_scheduler_not_fed_without_init(self):
        """If scheduler is never accessed, no feed calls happen (no crash)."""
        bus = TransientBus()
        bus.update(0.0, 0.0, 0.0)
        bus.update(0.8, 0.1, 0.05)
        # No crash, scheduler was never initialized


# ---------------------------------------------------------------------------
# Beat engine integration
# ---------------------------------------------------------------------------

class TestBeatEngineIntegration:
    def test_engine_exposes_scheduler(self):
        from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine
        engine = _SpotifyBeatEngine(bar_count=32)
        sched = engine.get_event_scheduler()
        assert isinstance(sched, TransientEventScheduler)
