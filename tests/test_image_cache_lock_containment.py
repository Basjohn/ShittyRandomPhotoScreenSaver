"""Cache concurrency guard: telemetry and QImage retirement cannot monopolize the shared mutex."""

from PySide6.QtGui import QImage

from utils import image_cache as cache_module
from utils.image_cache import ImageCache


def test_cache_io_telemetry_runs_outside_the_shared_lock(monkeypatch):
    cache = ImageCache(max_items=1)
    records = []

    def observe(message, *arguments):
        assert not cache._lock._is_owned(), message
        records.append(message % arguments)

    monkeypatch.setattr(cache_module, "_cache_trace", observe)
    first = QImage(2, 2, QImage.Format.Format_ARGB32)
    second = QImage(3, 2, QImage.Format.Format_ARGB32)

    cache.put("first", first)
    assert cache.get("first") is first
    assert cache.get("missing") is None
    cache.put("first", first)  # idempotent branch must also unlock before logging
    cache.put("second", second)  # evicts first under the hard item budget
    cache.set_protected_keys({"second"})
    assert cache.remove("second")

    assert cache.get_stats()["evictions"] == 1
    assert any("Evicted from cache" in line for line in records)
    assert any("identical cached object" in line for line in records)


def test_replaced_and_evicted_images_retire_after_unlock(monkeypatch):
    cache = ImageCache(max_items=1)
    releases = []

    class _TrackedImage:
        def __init__(self, marker):
            self.marker = marker

        def isNull(self):
            return False

        def sizeInBytes(self):
            return 16

        def width(self):
            return 2

        def height(self):
            return 2

        def format(self):
            return "fake-rgba"

        def __del__(self):
            releases.append((self.marker, cache._lock._is_owned()))

    # Test ownership of last-reference release without depending on Shiboken
    # QImage wrapper destructors, which differ across platforms.
    monkeypatch.setattr(cache_module, "QImage", _TrackedImage)
    cache.put("same", _TrackedImage("replaced"))
    cache.put("same", _TrackedImage("evicted"))
    cache.put("next", _TrackedImage("removed"))
    cache.remove("next")
    cache.put("last", _TrackedImage("cleared"))
    cache.clear()

    assert {marker for marker, _ in releases} == {
        "replaced", "evicted", "removed", "cleared"
    }
    assert all(not locked for _, locked in releases)
    assert cache.get_stats()["evictions"] == 1