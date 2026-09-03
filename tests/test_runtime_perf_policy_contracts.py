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


def test_runtime_gc_policy_freezes_stable_generation_once_and_unfreezes_on_stop():
    from core.performance.gc_policy import RuntimeGCPolicy

    baseline = gc.get_freeze_count()
    policy = RuntimeGCPolicy()
    try:
        # No freeze before the policy is active.
        assert policy.freeze_stable_generation() is False
        assert policy.frozen is False

        assert policy.start() is True
        retained = [{"k": [1, 2, 3]} for _ in range(1000)]
        assert policy.freeze_stable_generation() is True
        assert policy.frozen is True
        assert gc.get_freeze_count() > baseline
        # Idempotent: a second freeze is a no-op.
        assert policy.freeze_stable_generation() is False
        assert retained  # keep the frozen set alive across the freeze
    finally:
        policy.stop()
        gc.unfreeze()  # belt-and-suspenders: never leak freeze state to other tests
    # stop() released the pinned snapshot and cleared the flag.
    assert policy.frozen is False


def test_derive_warmup_thresholds_defers_only_gen2():
    from core.performance.gc_policy import (
        _WARMUP_FULL_DEFERRAL,
        derive_runtime_thresholds,
        derive_warmup_thresholds,
    )

    active = derive_runtime_thresholds((700, 10, 10))  # (700, 20, 50)
    warmup = derive_warmup_thresholds(active)
    # Young/middle keep the active cadence; only gen2 (full) is deferred.
    assert warmup[0] == active[0]
    assert warmup[1] == active[1]
    assert warmup[2] == active[2] * _WARMUP_FULL_DEFERRAL
    assert warmup[2] > active[2]
    # An intentionally disabled collector stays disabled.
    assert derive_warmup_thresholds((0, 10, 10)) == (0, 10, 10)


def test_gc_policy_defers_gen2_in_warmup_then_restores_active_on_freeze():
    from core.performance.gc_policy import RuntimeGCPolicy

    original = tuple(gc.get_threshold())
    policy = RuntimeGCPolicy()
    try:
        assert policy.start() is True
        # During warmup the gen2 trigger is deferred above the active value, so the
        # first expensive gen2 cannot race the one-shot freeze.
        warmup = tuple(gc.get_threshold())
        assert warmup == policy._warmup_thresholds
        if original[0] > 0:
            assert warmup[2] > policy._active_thresholds[2]
        # Freezing the stable set restores the normal active cadence so post-freeze
        # objects (recreated runtime/display/Settings generations) collect normally.
        assert policy.freeze_stable_generation() is True
        assert tuple(gc.get_threshold()) == policy._active_thresholds
    finally:
        policy.stop()
        gc.unfreeze()
    assert tuple(gc.get_threshold()) == original


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


def test_shared_ctrl_coordinator_pushes_global_truth_without_polling():
    module = _load_module(
        "_srpss_test_ctrl_coordinator",
        ROOT / "rendering" / "quick" / "ctrl_coordinator.py",
    )
    coordinator = module.SharedCtrlCoordinator()
    seen_a: list[bool] = []
    seen_b: list[bool] = []
    key_a = (7, 0)
    key_b = (7, 1)
    coordinator.subscribe(key_a, seen_a.append)
    coordinator.subscribe(key_b, seen_b.append)
    assert seen_a == [False]
    assert seen_b == [False]

    publish_a = coordinator.publisher_for(key_a)
    publish_b = coordinator.publisher_for(key_b)
    publish_a(True)
    assert seen_a[-1] is True and seen_b[-1] is True
    publish_b(True)
    # Global truth did not change; do not republish unchanged semantic state.
    assert seen_a == [False, True]
    assert seen_b == [False, True]
    publish_a(False)
    assert seen_a == [False, True]  # B still holds Ctrl.
    publish_b(False)
    assert seen_a[-1] is False and seen_b[-1] is False

    coordinator.forget(key_a)
    assert coordinator.listener_count == 1
    assert coordinator.contributing_display_count == 1

    # A replacement generation on the same physical screen owns a distinct
    # key. Retiring the old generation must not clear the replacement listener
    # or contribution.
    replacement_key = (8, 1)
    seen_replacement: list[bool] = []
    coordinator.subscribe(replacement_key, seen_replacement.append)
    publish_replacement = coordinator.publisher_for(replacement_key)
    publish_replacement(True)
    assert seen_replacement[-1] is True
    coordinator.forget(key_b)
    assert coordinator.listener_count == 1
    assert coordinator.is_display_held(replacement_key) is True
    assert coordinator.is_held() is True


def test_cursor_halo_uses_native_cursor_and_cached_semantic_input():
    window = (ROOT / "rendering/quick/window.py").read_text()
    runtime = (ROOT / "rendering/quick/runtime.py").read_text()
    auxiliary = (ROOT / "rendering/quick/auxiliary.py").read_text()
    input_controller = (ROOT / "rendering/quick/input_controller.py").read_text()
    cursor_controller = (ROOT / "rendering/quick/cursor_controller.py").read_text()
    scene_controller = (ROOT / "rendering/quick/scene_controller.py").read_text()
    display_scene = (ROOT / "rendering/quick/qml/DisplayScene.qml").read_text()
    display_manager = (ROOT / "engine/display_manager.py").read_text()
    ctrl_coordinator = (ROOT / "rendering/quick/ctrl_coordinator.py").read_text()

    # The pointer visual itself must not be a moving retained-QML item. Native
    # QCursor motion is owned by Qt/the window system and cannot dirty the
    # wallpaper/Visualizer scene simply because pointer coordinates changed.
    assert "CursorHalo" not in display_scene
    assert "scenePointerHover" not in display_scene
    assert "HoverHandler" not in display_scene
    assert "haloEnabled" not in display_scene
    assert 'setProperty("haloEnabled"' not in scene_controller
    assert 'setProperty("nativeCursorVisible"' not in scene_controller
    assert 'setProperty("haloShape"' not in scene_controller
    assert "QCursor" in cursor_controller
    assert "self._window.setCursor(cursor)" in cursor_controller
    assert '"pointer_owner": "native_qcursor"' in cursor_controller
    assert '"scene_position_binding": False' in cursor_controller
    assert "QQuickItem" not in cursor_controller
    assert "requestUpdate" not in cursor_controller

    # The two-second inactivity contract is deadline-based. Mouse polling only
    # updates last_motion_ns; it does not restart a Python/QML timer per event.
    assert "self._last_motion_ns = now" in cursor_controller
    assert "if not self._timer.isActive():" in cursor_controller
    assert "self._timer.start(_CURSOR_INACTIVITY_MS)" in cursor_controller
    assert ".restart()" not in cursor_controller
    assert "_CURSOR_INACTIVITY_MS: Final[int] = 2000" in cursor_controller

    # Halo motion bypasses RuntimeInputOwner entirely. The remaining mouse-move
    # route exists only for the classic non-interaction >10px exit gesture.
    assert "cursor.tracks_pointer_motion" in window
    assert "controller.passive_mouse_move_requires_routing" in window
    assert "interaction_mode_provider=interaction_mode_provider" not in input_controller
    assert "global_ctrl_held_provider=global_ctrl_held_provider" not in input_controller
    assert "interaction_mode_provider=None" in input_controller
    assert "global_ctrl_held_provider=None" in input_controller
    assert "return bool(self._state.interaction_mode_enabled)" in input_controller
    assert "return bool(self._state.ctrl_held)" in input_controller
    assert '"interaction_owner"] = "event_cached"' in input_controller
    assert '"ctrl_owner"] = "event_cached_shared"' in input_controller

    # Settings and cross-display Ctrl are pushed on semantic changes, not read
    # from providers at mouse polling frequency.
    assert "interaction_mode_enabled=self._interaction_mode_enabled()" in display_manager
    assert "self._set_quick_interaction_mode_enabled(persisted)" in display_manager
    assert "ctrl_coordinator.subscribe(" in (
        ROOT / "rendering/quick/display_unit.py"
    ).read_text()
    assert "def subscribe(" in ctrl_coordinator
    assert "self._broadcast_if_changed()" in ctrl_coordinator
    assert "held_provider" not in ctrl_coordinator

    # Auxiliary state still owns low-rate semantic admission/shape only and
    # explicitly identifies the native cursor as pointer presentation owner.
    assert "halo_enabled" in auxiliary
    assert "native_cursor_visible" in auxiliary
    assert '"halo_pointer_owner": "native_qcursor"' in auxiliary
    assert "pointer_position_changed" not in runtime
    assert "halo_x" not in auxiliary
    assert "halo_y" not in auxiliary


def test_replacement_runtime_first_frames_reseed_existing_prefetch_owner():
    engine = (ROOT / "engine/screensaver_engine.py").read_text()
    pipeline = (ROOT / "engine/image_pipeline.py").read_text()

    # Replacement runtimes have a deterministic readiness seam. Do not add a
    # second prefetch timer/owner: arm the existing generation-fenced retry only
    # after authoritative first frames have arrived.
    assert "def _on_authoritative_first_frames_ready" in engine
    assert 'self._runtime_lifecycle_event != "cold_start"' in engine
    assert "schedule_prefetch_after_runtime_ready(self)" in engine

    assert "def schedule_prefetch_after_runtime_ready" in pipeline
    assert 'reason="runtime_ready"' in pipeline
    assert "def _schedule_prefetch_resume" in pipeline
    assert "_has_transition_work_pending(engine)" in pipeline
    assert "_schedule_engine_delay(" in pipeline
    assert "_prefetch_resume_claim" in pipeline
    assert "_prefetch_resume_scheduled" not in pipeline
    assert "waiting on transition event" in pipeline
    assert "prefetch_resume_{reason}_transition_pending" not in pipeline
    assert "schedule_prefetch(engine)" in pipeline
    assert "def notify_transition_complete" in pipeline
    assert 'reason="transition_complete"' in pipeline
    assert "from PySide6.QtCore import QTimer" not in pipeline



def test_image_change_admission_is_transactional_and_never_snaps_active_transition():
    engine = (ROOT / "engine/screensaver_engine.py").read_text()
    manager = (ROOT / "engine/display_manager.py").read_text()

    show_start = engine.index("    def _show_next_image")
    show_end = engine.index("    def _schedule_startup_first_image_retry", show_start)
    show = engine[show_start:show_end]
    assert "if not self._try_begin_image_change_work():" in show
    assert show.index("_try_begin_image_change_work") < show.index("self.image_queue.next()")
    assert show.index("_prepare_random_transition_if_needed") < show.index("self.image_queue.next()")
    assert show.index("has_admissible_transition_for_open_batch") < show.index("self.image_queue.next()")

    claim_start = engine.index("    def _try_begin_image_change_work")
    claim_end = engine.index("    def _clear_unaccepted_image_change_work", claim_start)
    claim = engine[claim_start:claim_end]
    assert "has_transition_work_pending" in claim
    assert claim.index("has_transition_work_pending") < claim.index("self._loading_in_progress = True")
    assert "Image-change admission rejected while opening" in claim

    assert "def has_admissible_transition_for_open_batch" in manager
    assert "if not self.has_presented_image():" in manager
    assert "return self._resolve_quick_transition_batch_spec() is not None" in manager

    present_start = manager.index("    def _present_quick_image")
    present_end = manager.index("    def _on_quick_transition_finalized", present_start)
    present = manager[present_start:present_end]
    assert 'cancel(reason="image-replacement")' not in present
    assert "still owns an active Quick transition" in present
    source_none_start = present.index("if source is None:")
    # The one-session startup desktop->wallpaper crossfade made the transition
    # spec a conditional, so anchor on the block that follows the source-none
    # direct-publish path rather than the old single-line resolve call.
    source_none_end = present.index("startup_desktop_transition = (", source_none_start)
    source_none = present[source_none_start:source_none_end]
    assert source_none.index("_finish_quick_transition_batch_if_complete()") < source_none.index(
        "_on_image_displayed(screen_index, image_path)"
    )

    spec_start = present.index("startup_desktop_transition = (")
    spec_end = present.index("request = spec.build_request", spec_start)
    spec_block = present[spec_start:spec_end]
    assert "destination withheld" in spec_block
    assert "publish(destination)" not in spec_block
    assert 'return "base_published"' in present
    assert 'return "transition_started"' in present

    pipeline = (ROOT / "engine/image_pipeline.py").read_text()
    assert '"base_image_published"' in pipeline
    assert '"transition_started"' in pipeline

    finalized_start = manager.index("    def _on_quick_transition_finalized")
    finalized_end = manager.index("    def _on_image_displayed", finalized_start)
    finalized = manager[finalized_start:finalized_end]
    assert finalized.index("_finish_quick_transition_batch_if_complete()") < finalized.index(
        "self.transition_completed.emit(screen_index)"
    )


def test_fullscreen_compat_overscan_preserves_shared_edges_and_logs_device_sizes():
    window = (ROOT / "rendering/quick/window.py").read_text()
    start = window.index("    def _fullscreen_compat_geometry")
    end = window.index("    def _queue_meta_call", start)
    block = window[start:end]

    assert "virtual_geometry" in block
    assert "geometry.top() == virtual.top()" in block
    assert "geometry.bottom() == virtual.bottom()" in block
    assert "geometry.left() == virtual.left()" in block
    assert "geometry.right() == virtual.right()" in block
    assert "adjust(-1, -1, 1, 1)" not in block
    assert "screen_device_size=%dx%d window_device_size=%dx%d" in block
    assert "screen.virtualGeometry()" in block
    # R-63 device-space lesson: mixed-DPR rounding may yield a harmless bounded
    # one-pixel shared-edge overshoot. Never hard-code the observed monitor pair
    # or force exact cover at the cost of resurrecting black flashes.
    assert "2560" not in block
    assert "1440" not in block
    assert "1.5" not in block
    assert "device_pixel_ratio" not in block.lower() or "screen_device_size" in block
