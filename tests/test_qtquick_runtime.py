"""Phase B gates for Quick display-runtime lifecycle and recreate ownership."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import subprocess
import sys

from PySide6.QtCore import QObject

from rendering.quick.runtime import QuickDisplayRuntime


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_is_a_narrow_qobject_owner_with_queued_window_retirement():
    assert issubclass(QuickDisplayRuntime, QObject)
    source = (ROOT / "rendering" / "quick" / "runtime.py").read_text(
        encoding="utf-8"
    )
    tree = ast.parse(source)

    assert "QuickDisplayWindow(" in source
    assert "QuickSceneController(" in source
    assert "QuickFramePacer(" in source
    assert "self.window.queue_close()" in source
    assert "self.window.close(" not in source
    assert "self.window.releaseResources(" not in source
    direct_release_calls = [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "releaseResources"
    ]
    close_calls = [
        ast.unparse(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "close"
    ]
    assert direct_release_calls == []
    assert close_calls == ["self.frame_pacer.close"]
    assert source.index("self.frame_pacer.close()") < source.index(
        "self.scene_controller.quiesce_for_retirement()"
    )
    assert source.index("self.scene_controller.quiesce_for_retirement()") < source.index(
        "self.window.queue_close()"
    )
    assert source.index("not self._scene_readiness.qml_objects_retired") < source.index(
        "window.deleteLater()"
    )
    assert "window.isSceneGraphInitialized()" in source
    for forbidden in (
        "QWidget",
        "QQuickWidget",
        "DisplayWidget",
        "WidgetManager",
        "GLCompositorWidget",
        "SettingsManager",
    ):
        assert forbidden not in source


def test_threaded_runtime_teardown_recreates_generation_zero_to_one():
    env = os.environ.copy()
    env["QSG_RENDER_LOOP"] = "basic"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.qtquick_render_node_smoke",
            "--windows",
            "1",
            "--generations",
            "2",
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
    assert report["completed_generations"] == 2
    assert report["created_windows"] == 2
    assert [window["generation"] for window in report["windows"]] == [0, 1]

    object_names = []
    for generation, window in enumerate(report["windows"]):
        runtime = window["runtime_state"]
        object_names.append(window["window_state"]["object_name"])
        assert window["runtime_type"] == "QuickDisplayRuntime"
        assert window["display_identity"]["runtime_generation"] == generation
        assert runtime["phase"] == "retired"
        assert runtime["close_meta_calls_queued"] is True
        assert runtime["window_delete_queued"] is True
        assert runtime["retirement_completed"] is True
        assert runtime["frame_pacer"]["closed"] is True
        assert window["final_scene_state"]["readiness"]["qml_objects_retired"] is True
        assert window["final"]["release_count"] == 1
        assert window["final"]["release_thread_id"] == window["final"]["render_thread_id"]
        assert window["final"]["invalidation_count"] >= 1

    assert object_names == [
        "srpss-quick-display-0-generation-0",
        "srpss-quick-display-0-generation-1",
    ]
