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
    use_lanczos: bool = False,
    sharpen: bool = False,
) -> dict[str, object]:
    return {
        "stats": stats if stats is not None else {},
        "path": path,
        "cache_key": key,
        "width": width,
        "height": height,
        "display_mode": DisplayMode.FILL,
        "use_lanczos": use_lanczos,
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


def test_foreground_quality_requests_are_skipped_without_decoding(qt_app) -> None:
    cache, derive = _Cache(), _AsyncDerive()
    prefetcher = _prefetcher(cache, derive)

    assert prefetcher.register_scaled_requests([
        _request(r"C:\wall\quality.jpg", "lanczos", use_lanczos=True),
        _request(r"C:\wall\quality.jpg", "sharpen", sharpen=True),
    ]) == 0
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
