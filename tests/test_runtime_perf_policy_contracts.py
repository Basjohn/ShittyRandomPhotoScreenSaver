"""Source-only contracts for the H/J performance checkpoint.

These tests intentionally avoid importing the full PySide6 runtime so the ZIP
checkpoint can self-audit in a source-only environment.
"""
from __future__ import annotations

import gc
import importlib.util
from pathlib import Path
import sys
import types


ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_runtime_gc_policy_preserves_young_and_relaxes_deep_scans():
    from core.performance.gc_policy import derive_runtime_thresholds

    assert derive_runtime_thresholds((700, 10, 10)) == (700, 20, 50)
    assert derive_runtime_thresholds((2000, 25, 80)) == (2000, 25, 80)
    assert derive_runtime_thresholds((0, 10, 10)) == (0, 10, 10)


def test_runtime_gc_policy_restores_interpreter_thresholds_and_callback():
    from core.performance.gc_policy import RuntimeGCPolicy

    original = tuple(gc.get_threshold())
    policy = RuntimeGCPolicy()
    try:
        assert policy.start() is True
        active = tuple(gc.get_threshold())
        assert active[0] == original[0]
        if original[0] > 0:
            assert active[1] >= max(original[1], 20)
            assert active[2] >= max(original[2], 50)
        assert policy._gc_callback in gc.callbacks
    finally:
        policy.stop()
    assert tuple(gc.get_threshold()) == original
    assert policy._gc_callback not in gc.callbacks


def _install_fake_pyside() -> tuple[type, type]:
    qtgui = types.ModuleType("PySide6.QtGui")
    pyside = types.ModuleType("PySide6")

    class _ImageBase:
        def __init__(self, width=1, height=1, depth=32):
            self._width = width
            self._height = height
            self._depth = depth

        def isNull(self):
            return False

        def width(self):
            return self._width

        def height(self):
            return self._height

        def depth(self):
            return self._depth

    class QImage(_ImageBase):
        def sizeInBytes(self):
            return self._width * self._height * 4

        def format(self):
            return "fake"

    class QPixmap(_ImageBase):
        pass

    qtgui.QImage = QImage
    qtgui.QPixmap = QPixmap
    pyside.QtGui = qtgui
    sys.modules["PySide6"] = pyside
    sys.modules["PySide6.QtGui"] = qtgui
    return QImage, QPixmap


def test_image_cache_near_future_protection_changes_lru_order_not_hard_caps():
    old_pyside = sys.modules.get("PySide6")
    old_qtgui = sys.modules.get("PySide6.QtGui")
    try:
        QImage, _QPixmap = _install_fake_pyside()
        module = _load_module(
            "_srpss_test_image_cache",
            ROOT / "utils" / "image_cache.py",
        )
        cache = module.ImageCache(max_items=2, max_memory_mb=64)
        cache.put("next", QImage(4, 4))
        cache.put("old", QImage(4, 4))
        cache.set_protected_keys(["next"])
        cache.put("deep_prefetch", QImage(4, 4))
        assert cache.contains("next")
        assert cache.contains("deep_prefetch")
        assert not cache.contains("old")
        assert cache.get_stats()["protected_items"] == 1

        # Protection is advisory: a pathological one-item hard cap can still
        # evict a protected entry rather than violating the configured bound.
        tiny = module.ImageCache(max_items=1, max_memory_mb=64)
        tiny.put("protected", QImage(4, 4))
        tiny.set_protected_keys(["protected", "also_protected"])
        tiny.put("also_protected", QImage(4, 4))
        assert tiny.size() == 1
    finally:
        if old_pyside is None:
            sys.modules.pop("PySide6", None)
        else:
            sys.modules["PySide6"] = old_pyside
        if old_qtgui is None:
            sys.modules.pop("PySide6.QtGui", None)
        else:
            sys.modules["PySide6.QtGui"] = old_qtgui


def test_image_change_perf_parser_separates_timer_and_manual_sources():
    parser = _load_module(
        "_srpss_test_image_change_perf_parser",
        ROOT / "tools" / "image_change_perf_parser.py",
    )
    report = parser.parse_lines(
        [
            "[PERF][IMAGE_CHANGE] id=1 origin=timer stage=request elapsed_ms=0 delta_ms=0 previous=request",
            "[PERF][IMAGE_CHANGE] id=1 origin=timer stage=display_processed elapsed_ms=210 delta_ms=205 previous=worker_started source=image_worker",
            "[PERF][IMAGE_CHANGE] id=1 origin=timer stage=finished elapsed_ms=230 delta_ms=20 previous=transition_admitted outcome=admitted",
            "[PERF][IMAGE_CHANGE] id=2 origin=manual_next stage=request elapsed_ms=0 delta_ms=0 previous=request",
            "[PERF][IMAGE_CHANGE] id=2 origin=manual_next stage=display_processed elapsed_ms=3 delta_ms=2 previous=worker_started source=scaled_cache",
            "[PERF][IMAGE_CHANGE] id=2 origin=manual_next stage=finished elapsed_ms=8 delta_ms=5 previous=transition_admitted outcome=admitted",
            "[PERF][GC_POLICY] generation=2 duration_ms=41.50 collected=0 uncollectable=0",
            "[PERF] [PREFETCH] scheduled preview_paths=5 raw_producers=2 scaled_requests=4 protected_immediate=2 source=preview_upcoming",
        ]
    )
    text = report.render()
    assert "origin=timer" in text
    assert "origin=manual_next" in text
    assert "timer_image_worker=1" in text
    assert "manual_image_worker=0" in text
    assert "gc_events=1" in text and "zero_collect=1" in text
    assert "prefetch_protected_samples=1 min=2 max=2" in text
