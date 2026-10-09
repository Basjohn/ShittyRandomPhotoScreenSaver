"""Event-driven refresh/transition mutual exclusion and retirement fencing.

No Qt display or author-owned preset values participate in these tests.
"""
from core.threading.refresh_transition_gate import RefreshTransitionGate, current_gate, install_gate


def test_refresh_completes_before_transition_and_new_refresh_waits_for_both_displays():
    gate = RefreshTransitionGate(4)
    events = []
    first = gate.begin_refresh("feed", lambda: events.append("feed_retried"))
    assert first is not None
    assert gate.begin_transition(lambda: events.append("transition_admitted")) == "deferred"
    assert gate.begin_refresh("reddit", lambda: events.append("reddit_resumed")) is None
    assert gate.begin_refresh("reddit", lambda: events.append("reddit_newest")) is None
    assert gate.snapshot == (False, 1, 1, True)
    gate.finish_refresh(first)
    assert events == ["transition_admitted"]
    assert gate.snapshot == (True, 0, 1, False)
    gate.end_transition()  # only after every transition's finalization
    assert events == ["transition_admitted", "reddit_newest"]
    assert gate.snapshot == (False, 0, 0, False)


def test_transition_starts_immediately_then_cache_waits_without_polling():
    gate = RefreshTransitionGate(10)
    events = []
    assert gate.begin_transition() == "started"
    assert gate.begin_refresh("cache", lambda: events.append("cache_allowed")) is None
    assert gate.snapshot == (True, 0, 1, False)
    gate.end_transition()
    assert events == ["cache_allowed"]


def test_closed_generation_never_replays_retired_callbacks():
    gate = RefreshTransitionGate(8)
    events = []
    install_gate(gate)
    try:
        assert current_gate(8) is gate
        assert current_gate(9) is None
        assert gate.begin_transition() == "started"
        assert gate.begin_refresh("feed", lambda: events.append("stale")) is None
        gate.close()
        gate.end_transition()
        assert events == []
        assert current_gate(8) is None
    finally:
        install_gate(None)


def test_failed_resume_does_not_leave_forever_busy_transition():
    gate = RefreshTransitionGate(3)
    def broken():
        raise RuntimeError("retired owner")
    token = gate.begin_refresh("feed", lambda: None)
    assert token is not None
    assert gate.begin_transition(broken) == "deferred"
    import pytest
    with pytest.raises(RuntimeError, match="retired owner"):
        gate.finish_refresh(token)
    assert gate.snapshot == (False, 0, 0, False)


def test_refresh_release_is_idempotent():
    gate = RefreshTransitionGate(1)
    token = gate.begin_refresh("feed", lambda: None)
    assert token is not None
    gate.finish_refresh(token)
    gate.finish_refresh(token)
    assert gate.snapshot == (False, 0, 0, False)


def test_feed_cache_delivery_waits_for_transition_then_runs_once(monkeypatch):
    from tests import test_feed_runtime as examples
    from widgets import feed_runtime
    gate = RefreshTransitionGate(71)
    install_gate(gate)
    try:
        feed_runtime.reset_shared_feed_runtime_for_tests()
        fake_source = examples._Source(examples._result())
        monkeypatch.setattr(feed_runtime._FeedFamilyOwner, "_source_for",
                            lambda _owner, _state: fake_source)
        fake_manager = examples._Manager()
        lease = feed_runtime.FeedRuntimeLease(
            config=feed_runtime.FeedRuntimeConfig.from_custom(examples._config(), 15),
            generation=71, manager=fake_manager, ui_dispatch=lambda fn: fn(),
            schedule=lambda ms, cb: (lambda: None), task_priority=0,
        )
        consumer = examples._Consumer(71)
        lease.attach_consumer(consumer)
        assert gate.begin_transition() == "started"
        assert lease.start()
        assert fake_manager.submissions == 0
        assert consumer.accepted == []
        assert gate.snapshot[2] == 1
        gate.end_transition()
        assert fake_manager.submissions == 1
        assert len(consumer.accepted) >= 1
        assert gate.snapshot[1] == 0
        lease.retire()
    finally:
        feed_runtime.reset_shared_feed_runtime_for_tests()
        gate.close()
        install_gate(None)


def test_transition_waits_for_feed_worker_and_gui_delivery(monkeypatch):
    from tests import test_feed_runtime as examples
    from widgets import feed_runtime
    from types import SimpleNamespace
    gate = RefreshTransitionGate(75)
    install_gate(gate)
    try:
        feed_runtime.reset_shared_feed_runtime_for_tests()
        fake_source = examples._Source(examples._result())
        monkeypatch.setattr(feed_runtime._FeedFamilyOwner, "_source_for",
                            lambda _owner, _state: fake_source)
        class DelayedManager:
            def __init__(self):
                self.tasks = []
            def submit_io_task(self, work, *, callback, **kwargs):
                self.tasks.append((work, callback))
        manager = DelayedManager()
        deliveries = []
        lease = feed_runtime.FeedRuntimeLease(
            config=feed_runtime.FeedRuntimeConfig.from_custom(examples._config(), 15),
            generation=75, manager=manager,
            ui_dispatch=lambda fn: deliveries.append(fn),
            schedule=lambda ms, cb: (lambda: None), task_priority=0,
        )
        consumer = examples._Consumer(75)
        lease.attach_consumer(consumer)
        assert lease.start()
        assert len(manager.tasks) == 1
        admitted = []
        assert gate.begin_transition(lambda: admitted.append("started")) == "deferred"
        work, callback = manager.tasks.pop()
        callback(SimpleNamespace(success=True, result=work()))
        assert admitted == []  # IO completion is NOT GUI publication
        assert len(deliveries) == 1
        deliveries.pop()()
        assert consumer.accepted
        assert admitted == ["started"]
        assert gate.snapshot[0] is True
        lease.retire()
        gate.end_transition()
    finally:
        feed_runtime.reset_shared_feed_runtime_for_tests()
        gate.close()
        install_gate(None)


def test_multiple_deferred_families_resume_one_at_a_time_through_gui_publication():
    gate = RefreshTransitionGate(19)
    events = []
    tokens = {}
    assert gate.begin_transition() == "started"
    for source in ("feeds", "gmail", "reddit", "weather"):
        def resume(name=source):
            events.append(("resume", name))
            token = gate.begin_refresh(name, lambda: resume(name))
            assert token is not None
            tokens[name] = token
        assert gate.begin_refresh(source, resume) is None
    assert gate.snapshot == (True, 0, 4, False)
    gate.end_transition()
    assert events == [("resume", "feeds")]
    assert gate.snapshot == (False, 1, 3, False)
    gate.finish_refresh(tokens["feeds"])
    assert events[-1] == ("resume", "gmail")
    assert gate.snapshot == (False, 1, 2, False)
    # A manual image change must outrank all waiting refresh owners.
    events.append(("request", "transition"))
    assert gate.begin_transition(lambda: events.append(("start", "transition"))) == "deferred"
    gate.finish_refresh(tokens["gmail"])
    assert events[-1] == ("start", "transition")
    assert gate.snapshot == (True, 0, 2, False)
    gate.end_transition()
    assert events[-1] == ("resume", "reddit")
    gate.finish_refresh(tokens["reddit"])
    assert events[-1] == ("resume", "weather")
    gate.finish_refresh(tokens["weather"])
    assert gate.snapshot == (False, 0, 0, False)
    assert [e for e in events if e[0] == "resume"] == [
        ("resume", "feeds"), ("resume", "gmail"),
        ("resume", "reddit"), ("resume", "weather"),
    ]


def test_dormant_and_throwing_resumers_never_strand_waiting_refreshes():
    gate = RefreshTransitionGate(20)
    events = []
    assert gate.begin_transition() == "started"
    gate.begin_refresh("dead", lambda: events.append("dead"))
    gate.begin_refresh("throws", lambda: (_ for _ in ()).throw(ValueError("retired")))
    gate.begin_refresh("dormant", lambda: events.append("dormant_no_claim"))
    tokens = []
    def live():
        tokens.append(gate.begin_refresh("live", live))
    gate.begin_refresh("live", live)
    gate.cancel_refresh("dead")
    gate.end_transition()
    assert events == ["dormant_no_claim"]
    assert len(tokens) == 1 and tokens[0] is not None
    gate.finish_refresh(tokens[0])
    assert gate.snapshot == (False, 0, 0, False)


def test_latest_wins_per_key_without_replaying_more_than_one_refresh():
    gate = RefreshTransitionGate(21)
    events = []
    assert gate.begin_transition() == "started"
    assert gate.begin_refresh("gmail", lambda: events.append("old")) is None
    token_holder = []
    def latest():
        events.append("new")
        token_holder.append(gate.begin_refresh("gmail", latest))
    assert gate.begin_refresh("gmail", latest) is None
    assert gate.snapshot == (True, 0, 1, False)
    gate.end_transition()
    assert events == ["new"]
    assert token_holder[0] is not None
    gate.finish_refresh(token_holder[0])
    assert gate.snapshot == (False, 0, 0, False)


def test_feeds_false_ui_dispatch_falls_back_once_and_releases_transition(monkeypatch):
    """False means rejected, unlike legacy inline dispatchers returning None.

    A rejected GUI publication must not leave a source holding the shared
    refresh token and stall the waiting wallpaper transition indefinitely.
    """
    import sys
    import types
    from types import SimpleNamespace
    from tests import test_feed_runtime as examples
    from widgets import feed_runtime

    gate = RefreshTransitionGate(164)
    install_gate(gate)
    try:
        feed_runtime.reset_shared_feed_runtime_for_tests()
        source = examples._Source(examples._result())
        monkeypatch.setattr(feed_runtime._FeedFamilyOwner, "_source_for",
                            lambda _owner, _state: source)

        class DeferredManager:
            def __init__(self):
                self.jobs = []
            def submit_io_task(self, work, *, callback, **kwargs):
                self.jobs.append((work, callback))

        ui_deliveries = []
        class LiveUI:
            @staticmethod
            def run_on_ui_thread(callback):
                ui_deliveries.append(callback)
                callback()  # simulate admission by the owning Qt GUI loop
                return True

        # This narrow synthetic seam does not create a Qt app or pretend a
        # production UI dispatch can execute safely on a worker thread.
        manager_module = types.ModuleType("core.threading.manager")
        manager_module.ThreadManager = LiveUI
        monkeypatch.setitem(sys.modules, "core.threading.manager", manager_module)
        manager = DeferredManager()
        lease = feed_runtime.FeedRuntimeLease(
            config=feed_runtime.FeedRuntimeConfig.from_custom(examples._config(), 15),
            generation=164, manager=manager, ui_dispatch=lambda _callback: False,
            schedule=lambda _ms, _callback: (lambda: None), task_priority=0,
        )
        consumer = examples._Consumer(164)
        lease.attach_consumer(consumer)
        assert lease.start()
        assert len(manager.jobs) == 1
        assert gate.snapshot[1] == 1
        resumed = []
        assert gate.begin_transition(lambda: resumed.append("transition")) == "deferred"
        job, done = manager.jobs.pop()
        done(SimpleNamespace(success=True, result=job()))
        assert len(ui_deliveries) == 1
        assert consumer.accepted  # family startup settlement may republish metadata
        assert resumed == ["transition"]
        assert gate.snapshot == (True, 0, 0, False)
        lease.retire()
        gate.end_transition()
    finally:
        feed_runtime.reset_shared_feed_runtime_for_tests()
        gate.close()
        install_gate(None)


def test_gate_edge_logs_identify_family_and_queue_time_without_sensitive_cache_key(caplog):
    import logging
    gate = RefreshTransitionGate(165)
    assert gate.begin_transition() == "started"
    token_holder = []
    def resume():
        token_holder.append(gate.begin_refresh((444, "private-user-feed-url"), resume))
    with caplog.at_level(logging.INFO, logger="core.threading.refresh_transition_gate"):
        assert gate.begin_refresh((444, "private-user-feed-url"), resume) is None
        gate.end_transition()
        assert len(token_holder) == 1 and token_holder[0] is not None
        gate.finish_refresh(token_holder[0])
    assert "refresh_waits family=feeds" in caplog.text
    assert "refresh_resumes family=feeds wait_ms=" in caplog.text
    assert "refresh_finished family=feeds held_ms=" in caplog.text
    assert "private-user-feed-url" not in caplog.text
