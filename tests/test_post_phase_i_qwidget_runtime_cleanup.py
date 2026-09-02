from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


_DELETED_RUNTIME_MODULES = (
    "widgets/shadow_utils.py",
    "widgets/spotify_visualizer/card_surface.py",
    "widgets/spotify_visualizer/legacy_render_snapshot_adapter.py",
    "widgets/spotify_visualizer/logical_tick_state_adapter.py",
    "widgets/spotify_visualizer/mode_transition.py",
    "widgets/spotify_visualizer/overlay_diagnostics.py",
    "widgets/spotify_visualizer/overlay_frame_shell.py",
    "widgets/spotify_visualizer/overlay_mask.py",
    "widgets/spotify_visualizer/overlay_render_dispatch.py",
    "widgets/spotify_visualizer/overlay_state.py",
    "widgets/spotify_visualizer/overlay_uniforms.py",
    "widgets/spotify_visualizer/presentation_fade.py",
    "widgets/spotify_visualizer/presentation_state_adapter.py",
    "widgets/spotify_visualizer/runtime_adapter.py",
    "widgets/spotify_visualizer/spectrum_presentation_smoothing.py",
    "widgets/spotify_visualizer/thread_affinity.py",
    "rendering/gl_error_handler.py",
    "rendering/gl_profiler.py",
    "rendering/gl_stage_timestamps.py",
    "rendering/gl_state_manager.py",
    "rendering/gl_timer_queries.py",
    "rendering/gl_programs/texture_manager.py",
    "rendering/gl_programs/program_cache.py",
    "rendering/gl_programs/geometry_manager.py",
    "rendering/gl_programs/gl_state_tracker.py",
)

# Settings GUI and standalone developer tools are intentionally QWidget-based.
# Tests are excluded because this contract is about production imports.
_SCAN_ROOTS = ("core", "engine", "rendering", "widgets")
_EXCLUDED_PARTS = {"ui", "tools", "tests", "Docs", "__pycache__"}


def _production_python_files() -> list[Path]:
    files: list[Path] = []
    for root_name in _SCAN_ROOTS:
        for path in (ROOT / root_name).rglob("*.py"):
            rel = path.relative_to(ROOT)
            if any(part in _EXCLUDED_PARTS for part in rel.parts):
                continue
            files.append(path)
    # main.py owns QApplication/app-shell error UI, not a screensaver presenter.
    # It is deliberately not part of the retained widget-presentation scan.
    return files


def _qtwidgets_imported_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "PySide6.QtWidgets":
            names.update(alias.name for alias in node.names)
    return names


def test_retired_qwidget_visualizer_presenter_modules_are_absent() -> None:
    existing = [relative for relative in _DELETED_RUNTIME_MODULES if (ROOT / relative).exists()]
    assert existing == []


def test_production_runtime_has_no_qwidget_or_qopenglwidget_import() -> None:
    offenders: dict[str, list[str]] = {}
    forbidden = {"QWidget", "QOpenGLWidget"}
    for path in _production_python_files():
        imported = _qtwidgets_imported_names(path) & forbidden
        if imported:
            offenders[path.relative_to(ROOT).as_posix()] = sorted(imported)
    assert offenders == {}


def test_visualizer_tick_pipeline_is_logical_only() -> None:
    source = (ROOT / "widgets/spotify_visualizer/tick_pipeline.py").read_text(
        encoding="utf-8"
    )
    for retired_symbol in (
        "push_spotify_visualizer_frame",
        "def push_gpu_frame(",
        "def present_tick(",
        "def present_logical_frame(",
        "def request_logical_present(",
        "from PySide6.QtCore import QRect",
        "from shiboken6 import Shiboken",
    ):
        assert retired_symbol not in source


def test_current_immutable_capture_has_current_name_and_owner() -> None:
    capture = ROOT / "widgets/spotify_visualizer/logical_frame_capture.py"
    assert capture.exists()
    source = capture.read_text(encoding="utf-8")
    assert "def capture_visualizer_logical_frame(" in source
    assert "capture_legacy_visualizer_logical_frame" not in source

    pipeline = (ROOT / "widgets/spotify_visualizer/tick_pipeline.py").read_text(
        encoding="utf-8"
    )
    assert "widgets.spotify_visualizer.logical_frame_capture" in pipeline
    assert "capture_visualizer_logical_frame(" in pipeline
    assert "legacy_render_snapshot_adapter" not in pipeline


def test_audio_worker_parent_contract_is_qobject_not_qwidget() -> None:
    source = (ROOT / "widgets/spotify_visualizer/audio_worker.py").read_text(
        encoding="utf-8"
    )
    assert "parent: Optional[QObject]" in source
    assert "from PySide6.QtWidgets import QWidget" not in source
    assert "parent: Optional[QWidget]" not in source


def test_quick_transition_shader_modules_remain_after_compositor_cleanup() -> None:
    required = (
        "rendering/gl_programs/base_program.py",
        "rendering/gl_programs/crossfade_program.py",
        "rendering/gl_programs/wipe_program.py",
        "rendering/gl_programs/warp_program.py",
        "rendering/gl_programs/blinds_program.py",
        "rendering/gl_programs/diffuse_program.py",
        "rendering/gl_programs/raindrops_program.py",
        "rendering/gl_programs/crumble_program.py",
        "rendering/gl_programs/particle_program.py",
        "rendering/gl_programs/burn_program.py",
        "rendering/gl_programs/blockspin_program.py",
    )
    missing = [relative for relative in required if not (ROOT / relative).exists()]
    assert missing == []

    package_source = (ROOT / "rendering/gl_programs/__init__.py").read_text(encoding="utf-8")
    assert "GLProgramCache" not in package_source
    assert "GLGeometryManager" not in package_source
