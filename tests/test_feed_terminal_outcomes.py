"""Fault-injection through FEEDS owner, retained presentation and NEWS aggregation."""
from dataclasses import replace
from threading import Thread
from types import SimpleNamespace

import pytest

from core.feeds.models import FeedDocument, FeedHealth, FeedItem, FeedRefreshResult, FeedSnapshot
from core.task_control import ExpectedTaskCancellation
from core.threading.refresh_transition_gate import RefreshTransitionGate, install_gate
from rendering.quick.widgets.feeds import FeedPresentationConfig, FeedPresentationModel, FeedPresentationStyle
from core.settings.default_contract import require_canonical_default
from widgets import feed_runtime


class Manager:
    def __init__(self):
        self.jobs = []
        self.reject = False
    def submit_io_task(self, work, *, callback, **kwargs):
        if self.reject:
            raise RuntimeError('submission rejected')
        self.jobs.append((work, callback))
    def finish(self, index, *, error=None):
        work, callback = self.jobs[index]
        if error is not None:
            callback(SimpleNamespace(success=False, result=None, error=error))
        else:
            callback(SimpleNamespace(success=True, result=work()))


class Source:
    def __init__(self, result):
        self.result = result
        self.calls = 0
        self.closed = 0
        self.transport = SimpleNamespace(close=self.close)
    def close(self):
        self.closed += 1
    def load_cached(self):
        return self.result
    def refresh(self):
        self.calls += 1
        return self.result


def result(now=1000., *, link=False):
    return FeedRefreshResult('available', FeedSnapshot(FeedDocument('Feed', '', 'rss', (
        FeedItem('one', 'Last good', 'https://example.test/article' if link else ''),)), now),
        FeedHealth(last_checked_at=now, last_success_at=now),
        local_artwork_by_item=(('one', 'file:///retained.png'),))


@pytest.fixture(autouse=True)
def runtime_boundary(qt_app):
    feed_runtime.reset_shared_feed_runtime_for_tests()
    gate = RefreshTransitionGate(870)
    install_gate(gate)
    yield gate
    feed_runtime.reset_shared_feed_runtime_for_tests()
    gate.close()
    install_gate(None)


def setup(monkeypatch, *, source_result=None, dispatch=None, news=False, images=False):
    manager = Manager()
    sources = {}
    source_result = result() if source_result is None else source_result
    def source_for(owner, state):
        source = sources.setdefault(state.spec.cache_key, Source(source_result))
        state.source = source
        return source
    monkeypatch.setattr(feed_runtime._FeedFamilyOwner, '_source_for', source_for)
    widget = 'feeds_news_world' if news else 'feeds_custom_1'
    values = {'enabled': True, 'feed_url': 'https://example.test/feed', 'show_images': images}
    config = FeedPresentationConfig.from_widgets_mapping({widget: values}, widget_id=widget)
    if news:
        custom = replace(config.custom, providers=config.custom.providers[:2])
        config = replace(config, custom=custom)
        service = feed_runtime.NewsRuntimeService(config=feed_runtime.NewsRuntimeConfig.from_news(custom, 15),
                                                 generation=870, manager=manager, ui_dispatch=dispatch or (lambda fn: fn()),
                                                 schedule=lambda ms, fn: (lambda: None), task_priority=0)
    else:
        service = feed_runtime.FeedRuntimeLease(config=feed_runtime.FeedRuntimeConfig.from_custom(config.custom, 15),
                                               generation=870, manager=manager, ui_dispatch=dispatch or (lambda fn: fn()),
                                               schedule=lambda ms, fn: (lambda: None), task_priority=0)
    model = FeedPresentationModel(config, FeedPresentationStyle.project(config, require_canonical_default('widgets.shadows')),
                                  runtime_generation=870)
    model.set_runtime_service(service)
    model.activate(manager)
    owner = service._leases[0][1]._owner if news else service._owner
    clock = [1000.]
    owner._now = lambda: clock[0]
    return model, service, owner, manager, sources, clock


def test_cache_worker_failure_settles_first_admission_and_gate(monkeypatch, runtime_boundary):
    model, lease, owner, manager, sources, clock = setup(monkeypatch)
    manager.finish(0, error=RuntimeError('cache read crashed'))
    state = next(iter(owner._states.values()))
    assert model._view_state == 'error'
    assert state.last_result.failure == 'worker_failed'
    assert owner._initial_admission_complete
    assert lease.presentation_settled and not state.in_flight
    assert runtime_boundary.snapshot == (False, 0, 0, False)
    assert len(manager.jobs) == 1  # failure is deferred, never a retry spin


@pytest.mark.parametrize('error', [RuntimeError('refresh crashed'), ExpectedTaskCancellation('lifecycle stop')])
def test_manual_terminal_outcome_keeps_last_good_and_clears_busy(monkeypatch, runtime_boundary, error):
    model, lease, owner, manager, sources, clock = setup(monkeypatch)
    manager.finish(0)
    before = next(iter(owner._states.values())).last_result
    assert model.request_refresh() and model.refreshing
    assert not lease.presentation_settled
    manager.finish(1, error=error)
    state = next(iter(owner._states.values()))
    assert not model.refreshing and lease.presentation_settled
    assert state.last_result.snapshot == before.snapshot
    assert state.last_result.local_artwork_by_item == before.local_artwork_by_item
    assert state.last_result.health == before.health
    assert not state.in_flight and owner._remote_bundle_key is None
    assert runtime_boundary.snapshot == (False, 0, 0, False)


def test_artwork_worker_failure_settles_without_losing_text_or_last_art(monkeypatch, runtime_boundary):
    model, lease, owner, manager, sources, clock = setup(monkeypatch, source_result=result(link=True), images=True)
    manager.finish(0)
    assert len(manager.jobs) == 2
    assert not lease.presentation_settled
    state = next(iter(owner._states.values()))
    text_deadline = state.due_at
    manager.finish(1, error=RuntimeError('artwork crashed'))
    state = next(iter(owner._states.values()))
    assert lease.presentation_settled and owner._initial_admission_complete
    assert state.last_result.snapshot.document.items[0].title == 'Last good'
    assert state.last_result.local_artwork_by_item == (('one', 'file:///retained.png'),)
    assert not owner._artwork_needed(state)
    assert state.due_at == text_deadline
    clock[0] += 61
    owner._admit_due_work()
    assert len(manager.jobs) == 2  # optional art failure never pulls text early
    assert runtime_boundary.snapshot == (False, 0, 0, False)


def test_submission_failure_has_visible_terminal_outcome_and_consumes_manual_intent(monkeypatch, runtime_boundary):
    model, lease, owner, manager, sources, clock = setup(monkeypatch)
    manager.finish(0)
    manager.reject = True
    assert model.request_refresh()
    state = next(iter(owner._states.values()))
    assert not model.refreshing and lease.presentation_settled
    assert state.last_result.failure == 'submission_failed'
    assert not state.force_refresh_pending and not state.in_flight
    assert owner._remote_bundle_key is None
    assert runtime_boundary.snapshot == (False, 0, 0, False)


@pytest.mark.parametrize('kind', ['raise_before', 'reject', 'raise_after'])
def test_dispatch_failures_settle_once_through_ui_owner(monkeypatch, runtime_boundary, kind):
    from core.threading.manager import ThreadManager
    deliveries = []
    def canonical(fn):
        deliveries.append(fn)
        fn()
        return True
    monkeypatch.setattr(ThreadManager, 'run_on_ui_thread', canonical)
    def dispatch(fn):
        if kind == 'raise_after':
            fn()
        if kind != 'reject':
            raise RuntimeError('dispatcher crashed')
        return False
    model, lease, owner, manager, sources, clock = setup(monkeypatch, dispatch=dispatch)
    publications = []
    model.stateChanged.connect(lambda: publications.append(model._view_state))
    manager.finish(0)
    assert len(deliveries) == (0 if kind == 'raise_after' else 1)
    assert owner._initial_admission_complete and lease.presentation_settled
    assert model._view_state == ('ready' if kind == 'raise_after' else 'error')
    # Startup barrier metadata can republish the terminal body; dispatch itself
    # is delivered once and never creates a second owner completion.
    assert len(publications) == (1 if kind == 'raise_after' else 2)
    assert runtime_boundary.snapshot == (False, 0, 0, False)


def test_rejected_delivery_never_publishes_on_io_thread(monkeypatch, runtime_boundary):
    from core.threading.manager import ThreadManager
    queued = []
    monkeypatch.setattr(ThreadManager, 'run_on_ui_thread', lambda fn: queued.append(fn) or True)
    model, lease, owner, manager, sources, clock = setup(monkeypatch, dispatch=lambda fn: False)
    worker = Thread(target=lambda: manager.finish(0, error=RuntimeError('worker failure')))
    worker.start(); worker.join()
    assert model._view_state == 'loading' and len(queued) == 1
    queued.pop()()
    assert model._view_state == 'error' and lease.presentation_settled
    assert runtime_boundary.snapshot == (False, 0, 0, False)


def test_consumer_exception_does_not_interrupt_other_consumers_or_bundle(monkeypatch, runtime_boundary):
    model, lease, owner, manager, sources, clock = setup(monkeypatch)
    second = feed_runtime.FeedRuntimeLease(config=lease.config, generation=870, manager=manager,
                                          ui_dispatch=lambda fn: fn(), schedule=lambda ms, fn: (lambda: None), task_priority=0)
    class Throwing:
        def is_feed_consumer_alive(self): return True
        def on_feed_runtime_result(self, result, *, from_cache): raise RuntimeError('consumer crashed')
    broken = Throwing()
    second.attach_consumer(broken)
    assert second.start()
    manager.finish(0)
    assert owner._initial_admission_complete and lease.presentation_settled and second.presentation_settled
    assert model._view_state == 'ready'
    assert model.request_refresh()
    manager.finish(1, error=RuntimeError('worker crashed'))
    assert not model.refreshing and owner._remote_bundle_key is None
    assert runtime_boundary.snapshot == (False, 0, 0, False)


def test_late_duplicate_completion_cannot_close_newer_source_or_claim(monkeypatch, runtime_boundary):
    model, lease, owner, manager, sources, clock = setup(monkeypatch)
    manager.finish(0)
    assert model.request_refresh()
    old_work, old_done = manager.jobs[1]
    old_result = old_work()
    old_done(SimpleNamespace(success=True, result=old_result))
    clock[0] += 3
    assert model.request_refresh()
    state = next(iter(owner._states.values()))
    token = state.work_token
    source = sources[state.spec.cache_key]
    old_done(SimpleNamespace(success=True, result=old_result))
    assert state.in_flight and state.work_token == token
    assert owner._remote_bundle_key == state.spec.cache_key
    assert source.closed == 0 and runtime_boundary.snapshot[1] == 1
    manager.finish(2)
    assert lease.presentation_settled and runtime_boundary.snapshot[1] == 0


def test_news_manual_queue_stays_busy_until_all_publishers_settle(monkeypatch, runtime_boundary):
    model, service, owner, manager, sources, clock = setup(monkeypatch, news=True)
    manager.finish(0); manager.finish(1)
    assert owner._initial_admission_complete
    clock[0] = max(clock[0], owner._remote_not_before)
    assert model.request_refresh() and model.refreshing
    assert len(manager.jobs) == 3, (owner._remote_bundle_key, owner._remote_not_before, clock,
                                  [(s.due_at, s.in_flight, s.force_refresh_pending) for s in owner._states.values()], owner._refresh_gate_deferred)
    assert all(not lease.presentation_settled for _, lease in service._leases)
    manager.finish(2, error=RuntimeError('publisher crashed'))
    assert model.refreshing
    assert not all(lease.presentation_settled for _, lease in service._leases)
    assert owner._remote_bundle_key is None and len(manager.jobs) == 3
    clock[0] += 2.5
    owner._admit_due_work()
    assert len(manager.jobs) == 4
    manager.finish(3, error=RuntimeError('other publisher crashed'))
    assert not model.refreshing
    assert all(lease.presentation_settled for _, lease in service._leases)
    assert owner._initial_admission_complete
    assert runtime_boundary.snapshot == (False, 0, 0, False)


def test_news_cache_failure_answers_all_provider_startup_barrier(monkeypatch, runtime_boundary):
    model, service, owner, manager, sources, clock = setup(monkeypatch, news=True)
    manager.finish(0, error=RuntimeError('first cache crashed'))
    assert model._view_state == 'loading'
    manager.finish(1, error=RuntimeError('second cache crashed'))
    assert model._view_state == 'error' and owner._initial_admission_complete
    assert len(service._results) == 2
    assert all(lease.presentation_settled for _, lease in service._leases)
    assert runtime_boundary.snapshot == (False, 0, 0, False)


def test_inline_manual_completion_consumes_intent_before_publication(monkeypatch, runtime_boundary):
    model, lease, owner, manager, sources, clock = setup(monkeypatch)
    manager.finish(0)
    def inline(work, *, callback, **kwargs):
        callback(SimpleNamespace(success=True, result=work()))
    manager.submit_io_task = inline
    assert model.request_refresh()
    state = next(iter(owner._states.values()))
    assert not model.refreshing and lease.presentation_settled
    assert not state.force_refresh_pending and not state.in_flight
    assert runtime_boundary.snapshot == (False, 0, 0, False)


def test_submit_raises_after_inline_completion_cannot_publish_a_second_outcome(monkeypatch, runtime_boundary):
    model, lease, owner, manager, sources, clock = setup(monkeypatch)
    manager.finish(0)
    def inline(work, *, callback, **kwargs):
        callback(SimpleNamespace(success=True, result=work()))
        raise RuntimeError('submit threw after callback')
    manager.submit_io_task = inline
    assert model.request_refresh()
    state = next(iter(owner._states.values()))
    assert not model.refreshing and lease.presentation_settled
    assert state.last_result.failure == ''
    assert runtime_boundary.snapshot == (False, 0, 0, False)


def test_manual_intent_respects_provider_floor_and_logs_once(monkeypatch, runtime_boundary, caplog):
    import logging
    backed_off = replace(result(), status='backoff_cache', health=FeedHealth(
        last_success_at=1000., last_checked_at=1000., backoff_until=1120., consecutive_failures=1, last_failure='offline'))
    model, lease, owner, manager, sources, clock = setup(monkeypatch, source_result=backed_off)
    manager.finish(0)
    with caplog.at_level(logging.INFO):
        assert model.request_refresh() and model.refreshing
        assert len(manager.jobs) == 1
        state = next(iter(owner._states.values()))
        assert state.force_refresh_pending and state.due_at == 1120.
        clock[0] = 1119.
        owner._admit_due_work()
        assert len(manager.jobs) == 1
        lines = [entry.message for entry in caplog.records if 'Manual refresh deferred by provider backoff' in entry.message]
        assert len(lines) == 1 and 'remaining_s=120.0' in lines[0]
    clock[0] = 1120.
    owner._admit_due_work()
    assert len(manager.jobs) == 2
    sources[state.spec.cache_key].result = result(1120.)
    manager.finish(1)
    assert not model.refreshing and lease.presentation_settled
    assert not state.force_refresh_pending
    assert runtime_boundary.snapshot == (False, 0, 0, False)


def test_retirement_releases_claim_once_and_late_completion_cannot_publish(monkeypatch, runtime_boundary):
    model, lease, owner, manager, sources, clock = setup(monkeypatch)
    work, done = manager.jobs[0]
    completed = work()
    publications = []
    model.stateChanged.connect(lambda: publications.append(model._view_state))
    released = []
    original = runtime_boundary.finish_refresh
    def finish(token):
        released.append(token)
        return original(token)
    monkeypatch.setattr(runtime_boundary, 'finish_refresh', finish)
    lease.retire()
    done(SimpleNamespace(success=True, result=completed))
    assert publications == [] and len(released) == 1
    assert list(sources.values())[0].closed == 1
    assert runtime_boundary.snapshot == (False, 0, 0, False)


def test_no_gui_dispatch_never_invokes_presentation_on_worker(monkeypatch, runtime_boundary):
    from core.threading.manager import ThreadManager
    monkeypatch.setattr(ThreadManager, 'run_on_ui_thread', lambda fn: False)
    model, lease, owner, manager, sources, clock = setup(monkeypatch, dispatch=lambda fn: False)
    worker = Thread(target=lambda: manager.finish(0, error=RuntimeError('worker failed')))
    worker.start(); worker.join()
    assert model._view_state == 'loading'
    assert runtime_boundary.snapshot[1] == 0
    lease.retire()
    assert owner.is_retired


def test_source_removal_closes_startup_barrier_without_waiting_for_retired_worker(monkeypatch, runtime_boundary):
    install_gate(None)  # exercise concurrent cache-first admissions, not gate serialization
    model, lease, owner, manager, sources, clock = setup(monkeypatch)
    from core.feeds.config import CustomFeedConfig
    other = feed_runtime.FeedRuntimeLease(config=feed_runtime.FeedRuntimeConfig.from_custom(CustomFeedConfig.from_mapping(
        'feeds_custom_2', {'enabled': True, 'feed_url': 'https://example.test/other'}), 15),
        generation=870, manager=manager, ui_dispatch=lambda fn: fn(), schedule=lambda ms, fn: (lambda: None), task_priority=0)
    class Consumer:
        def __init__(self): self.accepted = []
        def on_feed_runtime_result(self, result, *, from_cache): self.accepted.append(result)
    consumer = Consumer()
    other.attach_consumer(consumer)
    assert other.start()
    manager.finish(1)
    assert not owner._initial_admission_complete
    lease.retire()
    assert owner._initial_admission_complete
    assert consumer.accepted[-1].initial_admission_complete
    manager.finish(0, error=ExpectedTaskCancellation('removed endpoint'))
    assert len(owner._states) == 1
    assert runtime_boundary.snapshot == (False, 0, 0, False)


def test_removing_source_cancels_its_gate_waiter_before_replacement(monkeypatch, runtime_boundary):
    model, lease, owner, manager, sources, clock = setup(monkeypatch)
    manager.finish(0)
    # Keep the family alive with an attached sibling while this source is removed.
    from core.feeds.config import CustomFeedConfig
    other = feed_runtime.FeedRuntimeLease(config=feed_runtime.FeedRuntimeConfig.from_custom(CustomFeedConfig.from_mapping(
        'feeds_custom_2', {'enabled': True, 'feed_url': 'https://example.test/other'}), 15),
        generation=870, manager=manager, ui_dispatch=lambda fn: fn(), schedule=lambda ms, fn: (lambda: None), task_priority=0)
    class Consumer:
        def on_feed_runtime_result(self, result, *, from_cache): pass
    consumer = Consumer()
    other.attach_consumer(consumer)
    assert other.start()
    manager.finish(1)
    assert runtime_boundary.begin_transition() == 'started'
    assert model.request_refresh()
    assert runtime_boundary.snapshot[2] == 1
    lease.retire()
    assert runtime_boundary.snapshot[2] == 0
    assert not owner._refresh_gate_deferred
    runtime_boundary.end_transition()
    assert len(manager.jobs) == 2


def test_news_manual_empty_aggregate_stays_busy_until_final_publisher_failure(monkeypatch, runtime_boundary):
    unavailable = FeedRefreshResult('unavailable', None, FeedHealth(
        last_checked_at=1000., last_success_at=1000., backoff_until=1005.,
        consecutive_failures=1, last_failure='offline'), failure='offline')
    model, service, owner, manager, sources, clock = setup(monkeypatch, source_result=unavailable, news=True)
    manager.finish(0); manager.finish(1)
    assert owner._initial_admission_complete and model._snapshot is None
    assert model._view_state == 'error'
    assert model.request_refresh() and model.refreshing
    assert len(manager.jobs) == 2  # accepted intent waits for the provider floor
    clock[0] = 1005.
    owner._admit_due_work()
    manager.finish(2, error=RuntimeError('first publisher failed'))
    assert model.refreshing and model._snapshot is None
    assert not all(lease.presentation_settled for _, lease in service._leases)
    clock[0] += 2.5
    owner._admit_due_work()
    manager.finish(3, error=RuntimeError('final publisher failed'))
    assert not model.refreshing and model._view_state == 'error'
    assert all(lease.presentation_settled for _, lease in service._leases)
    assert runtime_boundary.snapshot == (False, 0, 0, False)


@pytest.mark.parametrize('with_gate', [False, True])
def test_news_share_growth_keeps_same_source_artwork_bundle_until_completion(monkeypatch, runtime_boundary, with_gate):
    if not with_gate:
        install_gate(None)  # also expose synchronous share-triggered admission
    monkeypatch.setattr(Source, 'load_cached', lambda self: FeedRefreshResult('unavailable', None, FeedHealth(), failure='no_cache'))
    monkeypatch.setattr(feed_runtime._FeedFamilyOwner, '_warm_artwork',
                        staticmethod(lambda base, **kwargs: base))
    model, service, owner, manager, sources, clock = setup(monkeypatch, source_result=result(link=True), news=True, images=True)
    manager.finish(0)
    manager.finish(1)
    assert len(manager.jobs) == 3  # two cache admissions plus first due publisher
    assert all(state.last_from_cache and state.last_result.failure == 'no_cache'
               for state in owner._states.values())
    first_key = owner._remote_bundle_key
    manager.finish(2)  # text publication grows NEWS's visible artwork share inline
    assert len(manager.jobs) == 4, (first_key, owner._remote_bundle_key, owner._remote_not_before,
                                  owner._refresh_gate_deferred, runtime_boundary.snapshot,
                                  [(s.spec.cache_key, s.in_flight, s.artwork_attempted_at, owner._artwork_limit(s), s.due_at) for s in owner._states.values()])
    assert owner._remote_bundle_key == first_key
    first_state = owner._states[first_key]
    assert first_state.in_flight
    clock[0] += 2.5
    owner._admit_due_work()
    assert len(manager.jobs) == 4  # second publisher cannot overlap the active art
    manager.finish(3)
    assert owner._remote_bundle_key is None
    assert len(manager.jobs) == 4
    clock[0] += 2.499
    owner._admit_due_work()
    assert len(manager.jobs) == 4
    clock[0] += .001
    owner._admit_due_work()
    assert len(manager.jobs) == 5  # full 2.5s gap starts at artwork completion


def test_removing_gate_deferred_artwork_releases_its_remote_bundle(monkeypatch, runtime_boundary):
    monkeypatch.setattr(Source, 'load_cached', lambda self: FeedRefreshResult('unavailable', None, FeedHealth(), failure='no_cache'))
    model, service, owner, manager, sources, clock = setup(monkeypatch, source_result=result(link=True), news=True, images=True)
    manager.finish(0); manager.finish(1)
    first_key = owner._remote_bundle_key
    assert runtime_boundary.begin_transition(lambda: None) == 'deferred'
    manager.finish(2)
    assert len(manager.jobs) == 3
    assert owner._remote_bundle_key == first_key
    assert first_key in owner._refresh_gate_deferred
    first_lease = next(lease for _, lease in service._leases if lease.config.source_spec.cache_key == first_key)
    first_lease.stop()
    assert owner._remote_bundle_key is None
    assert first_key not in owner._refresh_gate_deferred
    assert runtime_boundary.snapshot[2] == 0
    runtime_boundary.end_transition()
    clock[0] += 2.5
    owner._admit_due_work()
    assert len(manager.jobs) == 4
    assert owner._remote_bundle_key != first_key



def test_manual_intent_queued_before_cache_answer_survives_fresh_cache(monkeypatch, runtime_boundary):
    model, service, owner, manager, sources, clock = setup(monkeypatch, news=True)
    assert len(manager.jobs) == 1  # second publisher cache is gate-deferred
    assert model.request_refresh()
    assert len(manager.jobs) == 1  # no remote work before its cache answer
    manager.finish(0)
    assert len(manager.jobs) == 2
    manager.finish(1)
    assert len(manager.jobs) == 3  # fresh cache cannot consume queued manual intent
    state = next(state for state in owner._states.values() if state.in_flight)
    assert state.last_from_cache and not state.force_refresh_pending
    manager.finish(2)
    assert not model.refreshing
    assert all(lease.presentation_settled for _, lease in service._leases)
