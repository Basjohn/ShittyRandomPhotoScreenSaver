from __future__ import annotations

from pathlib import Path
from typing import Any

from core.resources.types import ResourceType
from sources.rss.cache import RSSCache
from sources.rss.coordinator import RSSCoordinator


class _ResourceManager:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def register(self, resource: Any, **kwargs: Any) -> str:
        self.calls.append({"resource": resource, **kwargs})
        return "image_cache_test"


class _ThreadManager:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def submit_io_task(self, worker, *args: Any, **kwargs: Any) -> str:
        self.calls.append({"worker": worker, "args": args, **kwargs})
        return "task"


def test_rss_cache_registers_as_image_cache(tmp_path: Path) -> None:
    manager = _ResourceManager()

    cache = RSSCache(cache_dir=tmp_path / "rss", resource_manager=manager)

    assert cache._resource_id == "image_cache_test"
    assert len(manager.calls) == 1
    assert manager.calls[0]["resource"] is cache
    assert manager.calls[0]["resource_type"] is ResourceType.IMAGE_CACHE


def test_rss_startup_load_has_diagnostics_category(tmp_path: Path) -> None:
    manager = _ThreadManager()
    coordinator = RSSCoordinator(
        feed_urls=[],
        cache_dir=tmp_path / "rss",
        thread_manager=manager,
    )

    coordinator.load_async()

    assert len(manager.calls) == 1
    assert manager.calls[0]["category"] == "rss_startup_load"
