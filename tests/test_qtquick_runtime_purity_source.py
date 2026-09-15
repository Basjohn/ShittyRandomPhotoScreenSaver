"""Source-level tripwires for the runtime Qt Quick purity boundary.

These tests deliberately need no PySide runtime. They prevent legacy QWidget/
QPixmap presentation escape hatches or a Python visualizer pacing clock from
quietly returning in a future refactor.
"""
from __future__ import annotations

from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")



def test_steady_state_runtime_import_graph_has_no_qtwidgets_or_eager_settings_dialog() -> None:
    # Settings is intentionally QWidget-based, but steady-state screensaver
    # runtime code must not import QtWidgets or the settings dialog. The one
    # SettingsDialog import is admitted only inside the post-destruction opener.
    runtime_roots = (
        ROOT / "engine",
        ROOT / "rendering" / "quick",
        ROOT / "widgets",
        ROOT / "core" / "audio",
    )
    offenders: list[str] = []
    for root in runtime_roots:
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if "PySide6.QtWidgets" in source:
                offenders.append(path.relative_to(ROOT).as_posix())
    assert offenders == []

    handlers = _text("engine/engine_handlers.py")
    tree = ast.parse(handlers)
    eager_ui_imports: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and str(node.module or "").startswith("ui."):
            eager_ui_imports.append(str(node.module))
        elif isinstance(node, ast.Import):
            eager_ui_imports.extend(
                alias.name for alias in node.names if alias.name.startswith("ui.")
            )
    assert eager_ui_imports == []

    resolver = handlers.split("def _settings_dialog_class", 1)[1].split(
        "def _record_diagnostic_stage", 1
    )[0]
    assert "from ui.settings_dialog import SettingsDialog" in resolver
    opener = handlers.split("def _open_settings_after_runtime_destroyed", 1)[1].split(
        "def _restart_after_settings_dialog_destroyed", 1
    )[0]
    assert "SettingsDialog = _settings_dialog_class()" in opener
    assert "QCoreApplication.instance()" in opener


def test_runtime_image_publication_has_no_generic_qpixmap_escape_hatch() -> None:
    for relative in (
        "engine/image_pipeline.py",
        "engine/display_manager.py",
        "rendering/quick/display_image_route.py",
        "rendering/quick/display_unit.py",
        "rendering/quick/image_boundary.py",
        "utils/image_cache.py",
    ):
        source = _text(relative)
        assert "QPixmap.fromImage" not in source, relative
        assert "def capture_qpixmap" not in source, relative
        assert "def show_image_synchronized" not in source, relative
        assert "def present_processed_image(" not in source, relative


def test_qpixmap_is_confined_to_named_gui_native_quick_seams() -> None:
    quick_dir = ROOT / "rendering" / "quick"
    offenders: list[str] = []
    allowed = {
        "rendering/quick/startup_desktop_capture.py",
        "rendering/quick/cursor_controller.py",
    }
    for path in quick_dir.rglob("*.py"):
        relative = path.relative_to(ROOT).as_posix()
        if "QPixmap" in path.read_text(encoding="utf-8") and relative not in allowed:
            offenders.append(relative)
    assert offenders == []


def test_visualizer_presentation_is_not_python_timer_paced() -> None:
    source = _text("rendering/quick/frame_pacer.py")
    tree = ast.parse(source)
    imported_names: set[str] = set()
    referenced_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported_names.update(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            imported_names.update(alias.asname or alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.Name):
            referenced_names.add(node.id)

    # Reject an actual Python timer clock while allowing comments/docstrings to
    # explain why the retired architecture is forbidden.
    assert "QTimer" not in imported_names
    assert "QTimer" not in referenced_names
    assert "PreciseTimer" not in referenced_names
    for forbidden in (
        "VISUALIZER =",
        "set_visualizer_active",
        "set_visualizer_sync",
        "_service_deadline",
    ):
        assert forbidden not in source

    owner = _text("widgets/spotify_visualizer/quick_display_visualizer_owner.py")
    mailbox = _text("widgets/spotify_visualizer/logical_runtime.py")
    assert "logical_mailbox.set_wake_callback" in owner
    assert "logical_mailbox.set_trace_screen_index" in owner
    assert "screen_index=trace_screen_index" in mailbox
    assert "previous is None" in mailbox
    assert "wake()" in mailbox


def test_frame_trace_is_explicit_and_not_a_default_foundry_diagnostic() -> None:
    main = _text("main.py")
    foundry = _text("tools/godzip_foundry_core.py")
    assert '"--frame-trace"' in main
    assert '"--frame-trace"' in foundry

    default_block = foundry.split("RUN_DEFAULT_FLAGS = (", 1)[1].split(")", 1)[0]
    assert '"--frame-trace"' not in default_block


def test_dead_generic_pixmap_pool_and_overlay_sanitizer_cannot_return() -> None:
    resources = _text("core/resources/manager.py")
    for forbidden in (
        "PIXMAP_POOL_MAX_SIZE",
        "_pixmap_pool",
        "def acquire_pixmap",
        "def release_pixmap",
        "pixmap_hits",
        "pixmap_misses",
    ):
        assert forbidden not in resources
    assert not (ROOT / "core" / "logging" / "overlay_telemetry.py").exists()


def test_image_worker_authority_is_checked_before_queue_selection() -> None:
    engine = _text("engine/screensaver_engine.py")
    preflight = engine.index("image_processing_authority_available(self)")
    selection = engine.index("image_meta = self.image_queue.next()", preflight)
    assert preflight < selection

    pipeline = _text("engine/image_pipeline.py")
    assert "class ImageProcessingAbortError" in pipeline
    assert "class ImageProcessingInfrastructureError(ImageProcessingAbortError)" in pipeline
    assert "class ImageProcessingStaleRuntimeError(ImageProcessingAbortError)" in pipeline
    assert "raise ImageProcessingInfrastructureError" in pipeline
    assert "isinstance(authority_error, ImageProcessingAbortError)" in pipeline
    assert "ImageWorker rejected display candidate" in pipeline
    assert "return None" in pipeline
    assert "parent-process decode/scale fallback is forbidden" in pipeline

    worker_loader = pipeline.split("def load_image_via_worker(", 1)[1].split(
        "# ------------------------------------------------------------------\n# Async image loading and display", 1
    )[0]
    assert "except ImageProcessingAbortError:" in worker_loader
    assert "except ImageProcessingInfrastructureError:" not in worker_loader

    candidate = pipeline.split("def _process_display_image_candidate(", 1)[1].split(
        "def _process_display_with_replacements(", 1
    )[0]
    assert "AsyncImageProcessor.process_qimage" not in candidate
    assert "load_image_via_worker(" in candidate


def test_event_driven_quick_lifecycle_keeps_pause_resume_and_retirement_edges() -> None:
    runtime = _text("rendering/quick/runtime.py")
    pacer = _text("rendering/quick/frame_pacer.py")
    owner = _text("widgets/spotify_visualizer/quick_display_visualizer_owner.py")
    smoke = _text("tools/qtquick_render_node_smoke.py")

    # Window visibility owns suspension/resume of genuine continuous demand.
    visibility = runtime.split("def _on_visibility_changed", 1)[1].split(
        "def _on_context_menu_requested", 1
    )[0]
    assert "self.frame_pacer.resume()" in visibility
    assert visibility.count("self.frame_pacer.pause()") >= 2

    # Runtime retirement closes demand before scene/window teardown so no
    # frameSwapped continuation can target a retiring scene.
    close_runtime = runtime.split("def close_runtime", 1)[1].split(
        "def describe_runtime_state", 1
    )[0]
    assert close_runtime.index("self.transition_controller.close()") < close_runtime.index(
        "self.frame_pacer.close()"
    )
    assert close_runtime.index("self.frame_pacer.close()") < close_runtime.index(
        "self.scene_controller.quiesce_for_retirement()"
    )
    assert close_runtime.index("self.scene_controller.quiesce_for_retirement()") < close_runtime.index(
        "self.window.queue_close()"
    )

    # The continuous owner is a one-request-at-a-time Qt frameSwapped chain.
    assert "window.frameSwapped.connect(self._on_frame_swapped)" in pacer
    assert "self._window.frameSwapped.disconnect(self._on_frame_swapped)" in pacer
    request_next = pacer.split("def _request_next_frame", 1)[1].split(
        "def _on_frame_swapped", 1
    )[0]
    assert "self._update_pending" in request_next
    assert "self._window.requestUpdate()" in request_next
    assert "self._window.update()" not in request_next
    swapped = pacer.split("def _on_frame_swapped", 1)[1]
    assert "self._update_pending = False" in swapped
    assert "if self.is_active():" in swapped

    # The visualizer's separate publication edge follows presentation transfer
    # and is detached before retirement. It must not sneak back into the pacer.
    transfer = owner.split("def set_presentation_runtime", 1)[1].split(
        "def set_authored_outer_origin", 1
    )[0]
    assert "logical_mailbox.peek()" in transfer
    assert "wake.request()" in transfer
    retire = owner.split("def retire", 1)[1].split("__all__", 1)[0]
    assert retire.index("logical_mailbox.set_wake_callback(None)") < retire.index(
        "stop_logical_runtime()"
    )
    assert "wake.close()" in retire

    # The physical smoke harness exercises hide/show with a real continuous QML
    # demand, not a resurrected fake visualizer demand.
    assert "set_widget_animation_active(True)" in smoke
    assert 'demands") != ["widget_animation"]' in smoke
    assert "set_visualizer_active" not in smoke
    assert "set_visualizer_sync" not in smoke
