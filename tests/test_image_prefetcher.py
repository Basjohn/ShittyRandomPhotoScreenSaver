"""Parent-side contracts for bounded, supervisor-owned ImageWorker batches."""
from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from typing import Any

import pytest
from PySide6.QtGui import QColor, QImage

from rendering.display_modes import DisplayMode
from utils.image_prefetcher import ImagePrefetcher


def _image(width: int = 16, height: int = 9, color: str = "steelblue") -> QImage:
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(QColor(color))
    return image


class _Cache:
    def __init__(self, store: dict[str, QImage] | None = None) -> None:
        self.store = dict(store or {})

    def put(self, key: str, value: QImage) -> None:
        self.store[key] = value

    def contains(self, key: str) -> bool:
        return key in self.store


class _SelfEvictingCache(_Cache):
    def __init__(self, evicted_key: str) -> None:
        super().__init__()
        self.evicted_key = evicted_key

    def put(self, key: str, value: QImage) -> None:
        super().put(key, value)
        if key == self.evicted_key:
            self.store.pop(key)


class _AsyncDerive:
    """Records supervisor submissions and lets each test deliver its callback."""

    def __init__(self) -> None:
        self.submissions: list[dict[str, Any]] = []
        self.raise_submit: Exception | None = None
        self.complete_synchronously = False

    def __call__(
        self,
        path: str,
        requests: list[dict[str, Any]],
        generation: int,
        complete: Callable[[dict[str, QImage], Exception | None], None],
    ) -> Callable[[], None]:
        if self.raise_submit is not None:
            raise self.raise_submit
        submission = {
            "path": path,
            "requests": requests,
            "generation": generation,
            "complete": complete,
            "cancel_count": 0,
        }
        self.submissions.append(submission)

        def cancel() -> None:
            submission["cancel_count"] += 1

        if self.complete_synchronously:
            self.complete_synchronously = False
            complete(self._images_for(submission))
        return cancel

    @staticmethod
    def _images_for(submission: dict[str, Any]) -> dict[str, QImage]:
        return {
            str(request["cache_key"]): _image(int(request["width"]), int(request["height"]))
            for request in submission["requests"]
        }

    def deliver(
        self,
        index: int,
        images: dict[str, QImage] | None = None,
        error: Exception | None = None,
    ) -> None:
        submission = self.submissions[index]
        completed = images if images is not None else self._images_for(submission)
        submission["complete"](completed, error)


def _request(
    path: str,
    key: str,
    *,
    width: int = 16,
    height: int = 9,
    stats: dict[str, int] | None = None,
    resample_filter: str = "smooth",
    sharpen: bool = False,
) -> dict[str, object]:
    return {
        "stats": stats if stats is not None else {},
        "path": path,
        "cache_key": key,
        "width": width,
        "height": height,
        "display_mode": DisplayMode.FILL,
        "resample_filter": resample_filter,
        "sharpen": sharpen,
    }


def _prefetcher(cache: _Cache, derive: _AsyncDerive, **kwargs: object) -> ImagePrefetcher:
    return ImagePrefetcher(cache, derive=derive, **kwargs)


def test_source_batch_derives_all_display_variants_once(qt_app) -> None:
    path = r"C:\wall\shared-source.jpg"
    cache, derive = _Cache(), _AsyncDerive()
    prefetcher = _prefetcher(cache, derive)
    stats = [{}, {}, {}]

    assert prefetcher.register_scaled_requests([
        _request(path, "fill", width=1920, height=1080, stats=stats[0]),
        _request(path, "fit", width=1280, height=720, stats=stats[1]),
        _request(path, "second-display", width=1024, height=768, stats=stats[2]),
    ]) == 3
    assert len(derive.submissions) == 1
    assert derive.submissions[0]["path"] == path
    assert [request["cache_key"] for request in derive.submissions[0]["requests"]] == [
        "fill", "fit", "second-display",
    ]

    derive.deliver(0)

    assert set(cache.store) == {"fill", "fit", "second-display"}
    assert [entry["scaled_prefetch_completed"] for entry in stats] == [1, 1, 1]
    assert prefetcher.snapshot_state() == {"scaled_inflight": 0, "scaled_pending": 0}


def test_strict_single_flight_preserves_other_source_queue_order(qt_app) -> None:
    first, second, third = r"C:\wall\first.jpg", r"C:\wall\second.jpg", r"C:\wall\third.jpg"
    cache, derive = _Cache(), _AsyncDerive()
    prefetcher = _prefetcher(cache, derive, max_concurrent=4)

    assert prefetcher.register_scaled_requests([_request(first, "first")]) == 1
    assert prefetcher.register_scaled_requests([_request(second, "second"), _request(third, "third")]) == 2
    assert len(derive.submissions) == 1
    assert prefetcher.snapshot_state() == {"scaled_inflight": 1, "scaled_pending": 2}

    derive.deliver(0)
    assert len(derive.submissions) == 2
    derive.deliver(1)
    assert len(derive.submissions) == 3
    derive.deliver(2)

    assert [submission["path"] for submission in derive.submissions] == [first, second, third]


def test_foreground_admission_fences_only_new_source_batches_and_resumes_event_driven(qt_app) -> None:
    """An in-flight response may finish; subsequent speculative work waits."""
    cache, derive = _Cache(), _AsyncDerive()
    foreground_active = [False]
    prefetcher = _prefetcher(
        cache, derive,
        may_start_source_batch=lambda: not foreground_active[0],
    )
    first, second, third = [
        _request(path, path) for path in ("first", "second", "third")
    ]
    assert prefetcher.register_scaled_requests([first, second, third]) == 3
    assert [entry["path"] for entry in derive.submissions] == ["first"]

    foreground_active[0] = True
    derive.deliver(0)
    assert cache.contains("first")
    assert [entry["path"] for entry in derive.submissions] == ["first"]
    assert prefetcher.snapshot_state() == {"scaled_inflight": 0, "scaled_pending": 2}
    assert prefetcher.snapshot_budget_state()["scaled_pending_bytes"] > 0

    # The existing final-transition-complete owner re-registers the preview
    # (possibly empty when all intents were already admitted) and pumps them.
    foreground_active[0] = False
    prefetcher.register_scaled_requests([])
    assert [entry["path"] for entry in derive.submissions] == ["first", "second"]
    derive.deliver(1)
    derive.deliver(2)
    assert [entry["path"] for entry in derive.submissions] == ["first", "second", "third"]
    assert prefetcher.snapshot_budget_state()["scaled_pending_bytes"] == 0
    assert all(cache.contains(name) for name in ("first", "second", "third"))


def test_normal_transition_resume_drains_retained_intents_without_new_derivatives(qt_app, monkeypatch) -> None:
    """A cache-ready lookahead must still wake the existing blocked prefetch queue."""
    from types import SimpleNamespace
    import engine.image_pipeline as pipeline

    cache, derive = _Cache(), _AsyncDerive()
    foreground_active = [True]
    prefetcher = _prefetcher(
        cache, derive,
        may_start_source_batch=lambda: not foreground_active[0],
    )
    assert prefetcher.register_scaled_requests([_request("queued", "queued")]) == 1
    assert not derive.submissions
    assert prefetcher.snapshot_state()["scaled_pending"] == 1

    engine = SimpleNamespace(
        image_queue=SimpleNamespace(
            preview_upcoming=lambda count: [SimpleNamespace(local_path="cached", url=None)]
        ),
        _prefetcher=prefetcher,
        _prefetch_ahead=2,
        _image_cache=SimpleNamespace(set_protected_keys=lambda keys: None),
    )
    monkeypatch.setattr(pipeline, "_has_transition_work_pending", lambda _engine: False)
    monkeypatch.setattr(pipeline, "_build_immediate_prefetch_protected_keys", lambda *args: [])
    monkeypatch.setattr(pipeline, "_build_prefetch_scaled_requests", lambda *args: [])
    monkeypatch.setattr(pipeline, "_bump_cache_runtime_stat", lambda *args: None)

    foreground_active[0] = False
    pipeline.schedule_prefetch(engine)
    assert [entry["path"] for entry in derive.submissions] == ["queued"]
    derive.deliver(0)
    assert cache.contains("queued")
    assert prefetcher.snapshot_state() == {"scaled_inflight": 0, "scaled_pending": 0}


def test_foreground_admission_during_stagger_preserves_liveness_and_order(qt_app) -> None:
    cache, derive = _Cache(), _AsyncDerive()
    continuation = []
    busy = [False]
    prefetcher = _prefetcher(
        cache, derive,
        may_start_source_batch=lambda: not busy[0],
        schedule_next_batch=lambda delay, fn: continuation.append((delay, fn)),
        batch_stagger_ms=100,
    )
    prefetcher.register_scaled_requests([_request("a", "a"), _request("b", "b")])
    derive.deliver(0)
    assert len(continuation) == 1
    busy[0] = True
    delay, resume = continuation.pop(0)
    assert delay == 100
    resume()
    assert [entry["path"] for entry in derive.submissions] == ["a"]
    assert prefetcher.snapshot_state() == {"scaled_inflight": 0, "scaled_pending": 1}
    busy[0] = False
    prefetcher.register_scaled_requests([])
    assert [entry["path"] for entry in derive.submissions] == ["a", "b"]
    derive.deliver(1)
    assert not continuation


def test_owned_source_batch_stagger_and_new_registration_do_not_bypass_gap(qt_app) -> None:
    """One owned one-shot between source batches; never a per-frame poll."""
    cache, derive = _Cache(), _AsyncDerive()
    callbacks = []
    prefetcher = _prefetcher(
        cache, derive,
        schedule_next_batch=lambda ms, fn: callbacks.append((ms, fn)),
        batch_stagger_ms=100,
    )
    assert prefetcher.register_scaled_requests([_request("first", "a"), _request("second", "b")]) == 2
    derive.deliver(0)
    assert len(derive.submissions) == 1
    assert len(callbacks) == 1 and callbacks[0][0] == 100
    assert prefetcher.register_scaled_requests([_request("third", "c")]) == 1
    assert len(derive.submissions) == 1
    callbacks.pop(0)[1]()
    assert [entry["path"] for entry in derive.submissions] == ["first", "second"]
    derive.deliver(1)
    assert len(derive.submissions) == 2 and len(callbacks) == 1
    callbacks.pop(0)[1]()
    assert len(derive.submissions) == 3
    derive.deliver(2)
    assert callbacks == []


def test_stale_prefetch_batch_stagger_never_restarts_retired_generation(qt_app) -> None:
    cache, derive = _Cache(), _AsyncDerive()
    callbacks = []
    prefetcher = _prefetcher(
        cache, derive,
        schedule_next_batch=lambda ms, fn: callbacks.append(fn),
        batch_stagger_ms=100,
    )
    prefetcher.register_scaled_requests([_request("old", "old"), _request("stale", "stale")])
    derive.deliver(0)
    assert len(callbacks) == 1
    prefetcher.clear_inflight()
    prefetcher.register_scaled_requests([_request("new", "new")])
    assert len(derive.submissions) == 2
    callbacks.pop(0)()
    assert [entry["path"] for entry in derive.submissions] == ["old", "new"]
    derive.deliver(1)
    assert cache.contains("new") and not cache.contains("stale")


def test_prefetch_stagger_scheduler_failure_does_not_strand_source(qt_app) -> None:
    cache, derive = _Cache(), _AsyncDerive()
    def unavailable(_ms, _fn):
        raise RuntimeError("scheduler stopped")
    prefetcher = _prefetcher(cache, derive, schedule_next_batch=unavailable, batch_stagger_ms=100)
    prefetcher.register_scaled_requests([_request("a", "a"), _request("b", "b")])
    derive.deliver(0)
    assert [entry["path"] for entry in derive.submissions] == ["a", "b"]
    derive.deliver(1)
    assert cache.contains("b")


def test_duplicate_requests_are_not_admitted_while_source_is_active(qt_app) -> None:
    path = r"C:\wall\active.jpg"
    cache, derive = _Cache(), _AsyncDerive()
    prefetcher = _prefetcher(cache, derive)

    assert prefetcher.register_scaled_requests([_request(path, "already-planned")]) == 1
    assert prefetcher.register_scaled_requests([
        _request(path, "already-planned"),
        _request(path, "late-variant"),
    ]) == 0
    assert len(derive.submissions) == 1

    derive.deliver(0)
    assert "late-variant" not in cache.store


def test_registration_survives_cooldown_and_explicit_pump_resumes(qt_app) -> None:
    cache, derive = _Cache(), _AsyncDerive()
    prefetcher = _prefetcher(cache, derive, post_transition_delay_ms=10_000)
    prefetcher.notify_transition_complete()

    assert prefetcher.register_scaled_requests([_request(r"C:\wall\cooldown.jpg", "cooldown")]) == 1
    assert derive.submissions == []
    assert prefetcher.snapshot_state() == {"scaled_inflight": 0, "scaled_pending": 1}

    prefetcher._transition_end_time = 0.0
    prefetcher._pump_scaled_prefetch()
    assert len(derive.submissions) == 1


def test_admission_is_atomic_per_source_group_for_count_and_bytes(qt_app) -> None:
    active, admitted, rejected = r"C:\wall\active.jpg", r"C:\wall\admitted.jpg", r"C:\wall\rejected.jpg"
    cache, derive = _Cache(), _AsyncDerive()
    prefetcher = _prefetcher(
        cache,
        derive,
        max_concurrent=1,
        max_pending_requests=3,
        max_pending_scaled_bytes=20 * 1024 * 1024,
    )
    assert prefetcher.register_scaled_requests([_request(active, "active")]) == 1

    six_mib = {"width": 1536, "height": 1024}
    assert prefetcher.register_scaled_requests([
        _request(admitted, "admitted-a", **six_mib),
        _request(admitted, "admitted-b", **six_mib),
    ]) == 2
    assert prefetcher.register_scaled_requests([
        _request(rejected, "rejected-a", **six_mib),
        _request(rejected, "rejected-b", **six_mib),
    ]) == 0

    budget = prefetcher.snapshot_budget_state()
    assert budget["scaled_pending"] == 2
    assert budget["scaled_pending_bytes"] == 12 * 1024 * 1024
    assert [request["cache_key"] for request in prefetcher._pending_scaled_requests] == [
        "admitted-a", "admitted-b",
    ]


def test_pruning_stale_and_externally_cached_requests_reconciles_exact_bytes(qt_app) -> None:
    cache, derive = _Cache(), _AsyncDerive()
    prefetcher = _prefetcher(cache, derive, post_transition_delay_ms=10_000)
    prefetcher.notify_transition_complete()
    stale = _request(r"C:\wall\stale.jpg", "stale", width=10, height=20)
    cached = _request(r"C:\wall\cached.jpg", "cached", width=20, height=30)

    assert prefetcher.register_scaled_requests([stale, cached]) == 2
    prefetcher._pending_scaled_requests[0]["_prefetch_generation"] = -1
    cache.store["cached"] = _image()
    prefetcher._transition_end_time = 0.0
    prefetcher._pump_scaled_prefetch()

    assert prefetcher.snapshot_budget_state()["scaled_pending"] == 0
    assert prefetcher.snapshot_budget_state()["scaled_pending_bytes"] == 0
    assert prefetcher._pending_scaled_keys == set()
    assert derive.submissions == []


def test_clearing_queued_requests_avoids_worker_derivation(qt_app) -> None:
    cache, derive = _Cache(), _AsyncDerive()
    prefetcher = _prefetcher(cache, derive, post_transition_delay_ms=10_000)
    prefetcher.notify_transition_complete()
    assert prefetcher.register_scaled_requests([_request(r"C:\wall\queued.jpg", "queued")]) == 1

    prefetcher.clear_inflight()
    prefetcher._transition_end_time = 0.0
    prefetcher._pump_scaled_prefetch()

    assert derive.submissions == []


def test_clearing_running_batch_cancels_once_and_late_delivery_cannot_release_new_owner(qt_app) -> None:
    old_path, new_path = r"C:\wall\old.jpg", r"C:\wall\new.jpg"
    cache, derive = _Cache(), _AsyncDerive()
    prefetcher = _prefetcher(cache, derive)
    assert prefetcher.register_scaled_requests([_request(old_path, "old")]) == 1

    prefetcher.clear_inflight()
    prefetcher.clear_inflight()
    assert derive.submissions[0]["cancel_count"] == 1
    assert prefetcher.snapshot_state() == {"scaled_inflight": 0, "scaled_pending": 0}

    assert prefetcher.register_scaled_requests([_request(new_path, "new")]) == 1
    assert len(derive.submissions) == 2
    derive.deliver(0, {"old": _image(color="red")})

    assert "old" not in cache.store
    assert prefetcher.snapshot_state() == {"scaled_inflight": 1, "scaled_pending": 0}
    derive.deliver(1)
    assert cache.contains("new")


def test_clear_allows_same_path_resubmission_and_rejects_old_delivery(qt_app) -> None:
    path = r"C:\wall\same-path.jpg"
    cache, derive = _Cache(), _AsyncDerive()
    prefetcher = _prefetcher(cache, derive)
    request = _request(path, "same-path")
    assert prefetcher.register_scaled_requests([request]) == 1

    prefetcher.clear_inflight()
    assert derive.submissions[0]["cancel_count"] == 1
    assert prefetcher.register_scaled_requests([request]) == 1
    assert len(derive.submissions) == 2

    derive.deliver(0, {"same-path": _image(color="red")})
    assert "same-path" not in cache.store
    assert prefetcher.snapshot_state() == {"scaled_inflight": 1, "scaled_pending": 0}
    derive.deliver(1)
    assert cache.contains("same-path")


def test_synchronous_completion_before_cancel_handle_returns_caches_once_and_cancels_handle(qt_app) -> None:
    cache, derive = _Cache(), _AsyncDerive()
    derive.complete_synchronously = True
    prefetcher = _prefetcher(cache, derive)

    assert prefetcher.register_scaled_requests([_request(r"C:\wall\sync.jpg", "sync")]) == 1
    assert cache.contains("sync")
    assert derive.submissions[0]["cancel_count"] == 1
    assert prefetcher.snapshot_state() == {"scaled_inflight": 0, "scaled_pending": 0}


def test_cache_self_eviction_does_not_count_derivative_as_completed(qt_app) -> None:
    stats: dict[str, int] = {}
    cache, derive = _SelfEvictingCache("evicted"), _AsyncDerive()
    prefetcher = _prefetcher(cache, derive)

    assert prefetcher.register_scaled_requests([
        _request(r"C:\wall\evict.jpg", "evicted", stats=stats)
    ]) == 1
    derive.deliver(0)

    assert not cache.contains("evicted")
    assert stats.get("scaled_prefetch_completed", 0) == 0


def test_quality_requests_are_admitted_to_the_existing_bounded_worker_batch(qt_app) -> None:
    cache, derive = _Cache(), _AsyncDerive()
    prefetcher = _prefetcher(cache, derive)

    assert prefetcher.register_scaled_requests([
        _request(r"C:\wall\quality.jpg", "lanczos", resample_filter="lanczos"),
        _request(r"C:\wall\quality.jpg", "second-lanczos", resample_filter="lanczos"),
    ]) == 2
    assert len(derive.submissions) == 1
    assert [request["resample_filter"] for request in derive.submissions[0]["requests"]] == [
        "lanczos", "lanczos",
    ]


@pytest.mark.parametrize("resample_filter", ["nearest", None, ["lanczos"]])
def test_unresolved_or_unknown_resample_filter_is_rejected_before_submission(qt_app, resample_filter: object) -> None:
    cache, derive = _Cache(), _AsyncDerive()
    prefetcher = _prefetcher(cache, derive)
    request = _request(r"C:\wall\quality.jpg", "quality")
    request["resample_filter"] = resample_filter

    with pytest.raises(TypeError, match="resolved resample filter"):
        prefetcher.register_scaled_requests([request])
    assert derive.submissions == []


def test_mixed_quality_source_group_is_rejected_before_worker_submission(qt_app) -> None:
    cache, derive = _Cache(), _AsyncDerive()
    prefetcher = _prefetcher(cache, derive)
    with pytest.raises(ValueError, match="share one resolved resample filter"):
        prefetcher.register_scaled_requests([
            _request(r"C:\wall\quality.jpg", "smooth"),
            _request(r"C:\wall\quality.jpg", "lanczos", resample_filter="lanczos"),
        ])
    assert derive.submissions == []


def test_worker_failure_logs_loudly_retires_slot_and_continues_queue(qt_app, caplog) -> None:
    first, second = r"C:\wall\failed.jpg", r"C:\wall\next.jpg"
    cache, derive = _Cache(), _AsyncDerive()
    prefetcher = _prefetcher(cache, derive)
    prefetcher.register_scaled_requests([_request(first, "failed"), _request(second, "next")])

    with caplog.at_level(logging.ERROR):
        derive.deliver(0, error=RuntimeError("worker boom"))

    assert "Worker derivative batch failed" in caplog.text
    assert len(derive.submissions) == 2
    derive.deliver(1)
    assert cache.contains("next")


def test_submission_failure_logs_loudly_retires_slot_and_allows_later_admission(qt_app, caplog) -> None:
    cache, derive = _Cache(), _AsyncDerive()
    derive.raise_submit = RuntimeError("supervisor unavailable")
    prefetcher = _prefetcher(cache, derive)
    request = _request(r"C:\wall\retry.jpg", "retry")

    with caplog.at_level(logging.ERROR), pytest.raises(RuntimeError, match="supervisor unavailable"):
        prefetcher.register_scaled_requests([request])

    assert "Failed to submit worker derivative batch" in caplog.text
    assert prefetcher.snapshot_state() == {"scaled_inflight": 0, "scaled_pending": 0}
    derive.raise_submit = None
    assert prefetcher.register_scaled_requests([request]) == 1
    assert len(derive.submissions) == 1


def test_parent_prefetcher_has_no_parent_pool_or_scaler(qt_app) -> None:
    source = inspect.getsource(ImagePrefetcher)
    assert "ThreadManager" not in source
    assert "submit_background_task" not in source
    assert "QPixmap" not in source
    assert "AsyncImageProcessor" not in source
