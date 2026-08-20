"""Phase A2 gates for inline OpenGL inside the standalone Quick scene."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from PySide6.QtQuick import QQuickItem, QSGRenderNode

from rendering.quick.render import BackgroundRenderItem, BackgroundRenderNode


ROOT = Path(__file__).resolve().parents[1]


def test_background_item_and_node_use_the_selected_inline_primitive():
    assert issubclass(BackgroundRenderItem, QQuickItem)
    assert issubclass(BackgroundRenderNode, QSGRenderNode)

    item_tree = ast.parse(
        (ROOT / "rendering" / "quick" / "render" / "background_item.py").read_text(
            encoding="utf-8"
        )
    )
    calls = {
        node.func.attr
        for node in ast.walk(item_tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert "setFlag" in calls
    assert "updatePaintNode" not in calls


def test_render_node_owns_direct_gl_and_render_thread_cleanup():
    source = (
        ROOT / "rendering" / "quick" / "render" / "background_node.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    methods = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert {"render", "releaseResources", "changedStates", "rect"} <= methods
    assert "glDrawArrays" in source
    assert "QOpenGLContext.currentContext" in source
    assert "self.renderTarget()" in source
    assert "gl.glViewport(*viewport)" in source
    assert "gl.glViewport(*prior_viewport)" in source
    assert "beginExternalCommands" not in source
    assert "endExternalCommands" not in source


def test_quick_render_node_path_has_no_prohibited_surface_or_compatibility_owner():
    paths = (
        list((ROOT / "rendering" / "quick" / "render").rglob("*.py"))
        + [ROOT / "tools" / "qtquick_render_node_smoke.py"]
    )
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for forbidden in (
        "QQuickWidget",
        "QRhiWidget",
        "DisplayWidget",
        "GLCompositorWidget",
        "QOffscreenSurface",
        "QOpenGLWidget",
        "afterRendering.connect",
        "afterFrameEnd",
        "grabWindow(",
        "glFinish",
        "DwmFlush",
    ):
        assert forbidden not in source

    smoke_source = (ROOT / "tools" / "qtquick_render_node_smoke.py").read_text(
        encoding="utf-8"
    )
    window_source = (ROOT / "rendering" / "quick" / "window.py").read_text(
        encoding="utf-8"
    )
    runtime_source = (ROOT / "rendering" / "quick" / "runtime.py").read_text(
        encoding="utf-8"
    )
    assert "QMetaObject.invokeMethod" in window_source
    assert "self.window.queue_close()" in runtime_source
    assert "probe.runtime.close_runtime()" in smoke_source
    assert "probe.window.close()" not in smoke_source
    assert "probe.window.releaseResources()" not in smoke_source


def test_script_smoke_proves_threaded_draw_resize_dpr_and_invalidation():
    env = os.environ.copy()
    env["QSG_RENDER_LOOP"] = "basic"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.qtquick_render_node_smoke",
            "--windows",
            "1",
            "--size",
            "240x135",
            "--phase-delay-ms",
            "250",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(completed.stdout[completed.stdout.index("{") :])
    assert report["valid"] is True
    assert report["render_loop"] == "threaded"
    assert report["graphics_api"] == "OpenGL"
    assert report["qml_loaded"] is True
    assert report["qml_url"].endswith("DisplayScene.qml")
    assert report["completed_generations"] == 1
    assert report["created_windows"] == 1
    window = report["windows"][0]
    assert window["runtime_type"] == "QuickDisplayRuntime"
    assert window["window_type"] == "QuickDisplayWindow"
    assert window["display_identity"]["screen_index"] == 0
    assert window["display_identity"]["runtime_generation"] == 0
    assert window["initial_scene_state"]["readiness"]["ready_for_reveal"] is True
    assert (
        window["final_scene_state"]["readiness"]["scene_graph_invalidated"]
        is True
    )
    assert window["final_scene_state"]["readiness"]["qml_objects_retired"] is True
    assert window["initial"]["render_thread_id"] != window["initial"]["gui_thread_id"]
    assert window["final"]["release_count"] == 1
    assert window["final"]["invalidation_count"] >= 1
    assert window["initial"]["logical_size"] != window["final"]["logical_size"]
    assert window["initial"]["viewport"][2:] == window["initial"]["render_target_size"]
    assert window["final"]["viewport"][2:] == window["final"]["render_target_size"]
    assert window["initial_capture"]["size"] != window["resized_capture"]["size"]
    assert window["initial_capture"]["image_upload_count"] == 1
    assert window["resized_capture"]["image_upload_count"] == 1
    assert window["replacement_capture"]["image_upload_count"] == 2
    assert window["transition_run_id"] == 1
    assert window["transition_state_at_start"]["active"] is True
    assert window["transition_state_at_start"]["active_transition_id"] == "crossfade"
    assert window["transition_completion"]["outcome"] == "completed"
    assert window["transition_completion"]["destination_image_identity"] == (
        window["replacement_capture"]["active_image_identity"]
    )
    assert window["stale_transition_rejected"] is True
    assert (
        window["initial_capture"]["colors"]
        != window["replacement_capture"]["colors"]
    )
    assert window["final"]["image_upload_count"] == 2
    assert window["final"]["image_release_count"] == 2
    assert window["final"]["transition_sample_count"] >= 1
    assert window["final"]["last_transition_run_id"] == 1
    assert window["final"]["last_transition_generation"] == 0
    assert window["final"]["last_transition_id"] == "crossfade"
    assert window["final"]["transition_draw_count"] >= 1
    assert window["final"]["last_transition_renderer_id"] == "crossfade"
    assert window["final"]["transition_midpoint_run_id"] == 1
    assert 0.0 < window["final"]["transition_midpoint_eased_progress"] < 1.0
    assert window["final"]["transition_midpoint_colors"]
    assert window["final"]["transition_midpoint_colors"] != window[
        "resized_capture"
    ]["ordered_colors"]
    assert window["final"]["transition_midpoint_colors"] != window[
        "replacement_capture"
    ]["ordered_colors"]
    assert window["final"]["pending_image_release_count"] == 0
    assert window["final"]["active_image_identity"] is None


@pytest.mark.parametrize("direction", ("left", "right"))
def test_script_smoke_proves_lazy_slide_direction_pixels_and_teardown(direction):
    env = os.environ.copy()
    env["QSG_RENDER_LOOP"] = "basic"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.qtquick_render_node_smoke",
            "--windows",
            "1",
            "--size",
            "240x135",
            "--phase-delay-ms",
            "250",
            "--transition-id",
            "slide",
            "--transition-direction",
            direction,
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(completed.stdout[completed.stdout.index("{") :])
    assert report["valid"] is True
    assert report["requested_transition_id"] == "slide"
    assert report["requested_transition_direction"] == direction
    window = report["windows"][0]
    assert window["transition_state_at_start"]["active_transition_id"] == "slide"
    assert window["transition_completion"]["outcome"] == "completed"
    assert window["final"]["last_transition_id"] == "slide"
    assert window["final"]["last_transition_renderer_id"] == "slide"
    assert window["final"]["transition_draw_count"] >= 1
    assert window["final"]["transition_midpoint_run_id"] == 1
    assert window["final"]["transition_midpoint_colors"]
    assert window["final"]["release_count"] == 1
    assert window["final"]["image_upload_count"] == 2
    assert window["final"]["image_release_count"] == 2
    assert window["final"]["pending_image_release_count"] == 0


@pytest.mark.parametrize(
    "direction",
    (
        "left_to_right",
        "right_to_left",
        "top_to_bottom",
        "bottom_to_top",
        "diag_tl_br",
        "diag_tr_bl",
    ),
)
def test_script_smoke_proves_lazy_wipe_direction_pixels_and_teardown(direction):
    env = os.environ.copy()
    env["QSG_RENDER_LOOP"] = "basic"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.qtquick_render_node_smoke",
            "--windows",
            "1",
            "--size",
            "240x135",
            "--phase-delay-ms",
            "250",
            "--transition-id",
            "wipe",
            "--transition-direction",
            direction,
        ],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads(completed.stdout[completed.stdout.index("{") :])
    assert report["valid"] is True
    assert report["requested_transition_id"] == "wipe"
    assert report["requested_transition_direction"] == direction
    window = report["windows"][0]
    assert window["transition_state_at_start"]["active_transition_id"] == "wipe"
    assert window["transition_completion"]["outcome"] == "completed"
    assert window["final"]["last_transition_renderer_id"] == "wipe"
    assert window["final"]["transition_midpoint_run_id"] == 1
    assert len(window["final"]["transition_midpoint_colors"]) == 25
    assert window["final"]["release_count"] == 1
    assert window["final"]["image_upload_count"] == 2
    assert window["final"]["image_release_count"] == 2
    assert window["final"]["pending_image_release_count"] == 0
