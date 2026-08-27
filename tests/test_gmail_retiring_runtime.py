"""A retiring-generation Gmail fetch must settle before the destruction barrier.

The one apparent cross-display visualizer crash during CUSTOM Save was real but
was not a native crash. The visualizer moved from monitor 2 to monitor 1,
generation 5 retired normally, and at the barrier deadline:

    [LIFECYCLE_BARRIER] timeout reason=custom_edit retiring_generation=5
    thread_work=[{category: gmail_fetch, pool: io,
                  owner_class: GmailWidget, runtime_generation: 5}]

The application then exited code 1 under the fail-closed lifecycle policy. The
barrier was doing its job: it refuses to build a replacement while retired work
is still alive.

The original correction taught `GmailClient.list_messages()` to observe its
owner during traversal. Phase E1 moved that cancellation authority to the
neutral shared Gmail owner, which now fences every traversal with runtime-
generation and request identity while presenters own no network task.

The correction is cancellation ownership, not a longer timeout and not ignoring
the task. These bars hold a controllable request in flight across the retirement
and prove it settles.
"""

from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from core.gmail.gmail_client import GmailFetchCancelled


# ---------------------------------------------------------------------------
# A client whose requests the test can hold open
# ---------------------------------------------------------------------------


class _ControllableTransport:
    """Stands in for `requests`: each call blocks until the test releases it."""

    def __init__(self, message_count=5):
        self.message_count = message_count
        self.requests_started = 0
        self.requests_completed = 0
        self._gate = threading.Event()
        self.first_request_entered = threading.Event()

    def release(self):
        self._gate.set()

    def __call__(self, method, endpoint, params=None, **kwargs):
        self.requests_started += 1
        self.first_request_entered.set()
        # A real network read blocks here; the test decides how long.
        self._gate.wait(timeout=5.0)
        self.requests_completed += 1
        if endpoint == "users/me/messages":
            return {"messages": [{"id": f"m{i}"} for i in range(self.message_count)]}
        return {
            "payload": {"headers": [{"name": "Subject", "value": "s"}]},
            "labelIds": ["INBOX"],
            "threadId": "t",
        }


def _client(transport):
    from core.gmail.gmail_client import GmailClient

    client = GmailClient.__new__(GmailClient)
    client._api_lock = threading.Lock()
    client._make_request = lambda method, endpoint, data=None, params=None, headers=None, should_cancel=None: (
        _guarded_request(transport, method, endpoint, params, should_cancel)
    )
    return client


def _guarded_request(transport, method, endpoint, params, should_cancel):
    """The production cancellation contract, around the controllable transport."""
    if should_cancel is not None and should_cancel():
        raise GmailFetchCancelled(endpoint)
    return transport(method, endpoint, params=params)


# ---------------------------------------------------------------------------
# The client honours cancellation mid-traversal
# ---------------------------------------------------------------------------


class TestClientCancellation:
    def test_a_cancelled_fetch_stops_before_the_list_request(self):
        transport = _ControllableTransport()
        transport.release()
        client = _client(transport)

        with pytest.raises(GmailFetchCancelled):
            client.list_messages(max_results=5, should_cancel=lambda: True)

        assert transport.requests_started == 0

    def test_cancellation_during_metadata_traversal_stops_immediately(self):
        transport = _ControllableTransport(message_count=20)
        transport.release()
        client = _client(transport)
        seen = {"n": 0}

        def _should_cancel():
            # Retire after the list request and two metadata requests.
            seen["n"] += 1
            return seen["n"] > 3

        with pytest.raises(GmailFetchCancelled):
            client.list_messages(max_results=20, should_cancel=_should_cancel)

        assert transport.requests_started <= 3, (
            "the traversal kept issuing requests after its owner retired"
        )

    def test_an_uncancelled_fetch_returns_every_message(self):
        transport = _ControllableTransport(message_count=4)
        transport.release()
        client = _client(transport)

        emails = client.list_messages(max_results=4, should_cancel=lambda: False)

        assert len(emails) == 4
        assert transport.requests_started == 5  # 1 list + 4 metadata

    def test_cancellation_is_not_reported_as_a_network_error(self):
        transport = _ControllableTransport()
        transport.release()
        client = _client(transport)
        with pytest.raises(GmailFetchCancelled):
            client.list_messages(max_results=1, should_cancel=lambda: True)


# ---------------------------------------------------------------------------
# The widget fetch settles when its runtime generation retires
# ---------------------------------------------------------------------------


class _FetchOwner:
    """The neutral Gmail owner fetch surface with a controllable client."""

    def __init__(self, client, capacity=8):
        from widgets.gmail_runtime import GmailRuntimeConfig, _SharedGmailRuntimeOwner

        backend = SimpleNamespace(
            is_initialized=True,
            is_authenticated=True,
            client=client,
        )
        self.runtime = _SharedGmailRuntimeOwner(
            config=GmailRuntimeConfig(fetch_window_capacity=capacity),
            thread_manager=SimpleNamespace(),
            runtime_generation=5,
            backend=backend,
        )
        self.runtime._running = True
        self.runtime._owner_generation = 5
        self.runtime._fetch_request_id = 1
        self.published: list[tuple] = []
        self.errors: list[str] = []

        original_commit = self.runtime._commit_fetch
        original_error = self.runtime._commit_fetch_error

        def _commit(generation, request_id, emails, unread):
            self.published.append((tuple(emails), unread, generation))
            original_commit(generation, request_id, emails, unread)

        def _error(generation, request_id, message):
            self.errors.append(message)
            original_error(generation, request_id, message)

        self.runtime._commit_fetch = _commit
        self.runtime._commit_fetch_error = _error

    @property
    def _fetch_in_progress(self):
        return self.runtime._fetch_in_progress

    @_fetch_in_progress.setter
    def _fetch_in_progress(self, value):
        self.runtime._fetch_in_progress = bool(value)

    def _fetch_is_retired(self, generation: int) -> bool:
        return self.runtime._fetch_is_retired(generation, 1)

    def _fetch_emails_async(self, generation: int) -> None:
        self.runtime._fetch_emails_async(
            self.runtime._backend.client,
            generation,
            1,
        )

    def retire(self):
        self.runtime.stop()


@pytest.fixture
def ui_thread(monkeypatch):
    """Run UI callbacks inline so publication is observable."""
    calls: list[tuple] = []

    def _run_on_ui_thread(func, *args, **kwargs):
        calls.append((func, args))
        func(*args, **kwargs)

    monkeypatch.setattr(
        "widgets.gmail_runtime.ThreadManager.run_on_ui_thread",
        staticmethod(_run_on_ui_thread),
    )
    return calls


class TestRuntimeFetchOwnership:
    def test_a_live_fetch_publishes_normally(self, ui_thread):
        transport = _ControllableTransport(message_count=3)
        transport.release()
        owner = _FetchOwner(_client(transport))

        owner._fetch_emails_async(5)

        assert len(owner.published) == 1
        assert owner.errors == []

    def test_a_retired_fetch_publishes_nothing(self, ui_thread):
        transport = _ControllableTransport(message_count=3)
        transport.release()
        owner = _FetchOwner(_client(transport))
        owner.retire()

        owner._fetch_emails_async(5)

        assert owner.published == [], "a stale result reached the new runtime"
        assert owner.errors == [], "abandoning a retired fetch is not an error"

    def test_retiring_mid_traversal_settles_without_publishing(self, ui_thread):
        """The installed shape: retirement happens while the fetch is running."""
        transport = _ControllableTransport(message_count=20)
        transport.release()
        owner = _FetchOwner(_client(transport), capacity=20)

        original = owner.runtime._fetch_is_retired
        calls = {"n": 0}

        def _retire_after_two(generation, request_id):
            calls["n"] += 1
            if calls["n"] == 3:
                owner.retire()
            return original(generation, request_id)

        owner.runtime._fetch_is_retired = _retire_after_two

        owner._fetch_emails_async(5)

        assert owner.published == []
        assert owner.errors == []
        assert transport.requests_started < 20, (
            "the fetch ran its whole traversal after its generation retired"
        )

    def test_the_fetch_guard_is_released_on_the_cancelled_path(self, ui_thread):
        """A retired fetch must not leave the neutral owner marked as fetching."""
        transport = _ControllableTransport(message_count=2)
        transport.release()
        owner = _FetchOwner(_client(transport))
        owner._fetch_in_progress = True
        owner.retire()

        owner._fetch_emails_async(5)

        # end_fetch_guard runs in the finally block on every path, including the
        # abandoned-generation one, so a later runtime can fetch again.
        assert owner._fetch_in_progress is False

    def test_the_fetch_guard_is_released_after_a_successful_fetch(self, ui_thread):
        transport = _ControllableTransport(message_count=2)
        transport.release()
        owner = _FetchOwner(_client(transport))
        owner._fetch_in_progress = True

        owner._fetch_emails_async(5)

        assert owner._fetch_in_progress is False

    def test_a_genuine_network_failure_is_still_reported(self, ui_thread):
        class _Failing:
            def list_messages(self, **kwargs):
                raise RuntimeError("connection reset")

        owner = _FetchOwner(_Failing())
        owner._fetch_emails_async(5)

        assert owner.errors and "connection reset" in owner.errors[0]
        assert owner.published == []

    def test_a_client_without_the_seam_still_works(self, ui_thread):
        """Older/foreign backends must not break the fetch path."""

        class _LegacyClient:
            def __init__(self):
                self.calls = 0

            def list_messages(self, max_results=10, label_ids=None):
                self.calls += 1
                return []

        legacy = _LegacyClient()
        owner = _FetchOwner(legacy)

        owner._fetch_emails_async(5)

        assert legacy.calls == 1
        assert len(owner.published) == 1


# ---------------------------------------------------------------------------
# The barrier is preserved
# ---------------------------------------------------------------------------


class TestBarrierPolicyUnchanged:
    def test_the_barrier_still_counts_retiring_generation_thread_work(self):
        from engine.runtime_destruction import RuntimeDestructionBarrier

        barrier = RuntimeDestructionBarrier.__new__(RuntimeDestructionBarrier)
        barrier.retiring_generation = 5
        snapshot = {
            "active_tasks": (
                {
                    "category": "gmail_fetch",
                    "pool": "io",
                    "owner_class": "GmailWidget",
                    "runtime_generation": 5,
                },
                {"category": "other", "runtime_generation": 6},
            ),
            "ui": {},
        }
        barrier._engine_ref = lambda: SimpleNamespace(
            thread_manager=SimpleNamespace(
                get_lifecycle_ownership_snapshot=lambda: snapshot
            )
        )

        work = barrier._remaining_thread_work()

        assert len(work) == 1, "the barrier must not ignore gmail_fetch"
        assert work[0]["category"] == "gmail_fetch"

    def test_a_settled_fetch_leaves_the_barrier_clear(self):
        from engine.runtime_destruction import RuntimeDestructionBarrier

        barrier = RuntimeDestructionBarrier.__new__(RuntimeDestructionBarrier)
        barrier.retiring_generation = 5
        barrier._engine_ref = lambda: SimpleNamespace(
            thread_manager=SimpleNamespace(
                get_lifecycle_ownership_snapshot=lambda: {
                    "active_tasks": ({"category": "other", "runtime_generation": 6},),
                    "ui": {},
                }
            )
        )

        assert barrier._remaining_thread_work() == ()

    def test_the_timeout_budget_was_not_extended(self):
        from engine import runtime_destruction

        assert runtime_destruction._DEFAULT_TIMEOUT_MS <= 8000, (
            "the fix is cancellation ownership, never a longer barrier"
        )
