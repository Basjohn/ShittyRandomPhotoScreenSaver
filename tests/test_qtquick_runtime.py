"""Phase B gates for Quick display-runtime lifecycle and recreate ownership."""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from PySide6.QtCore import QObject

from rendering.quick.runtime import QuickDisplayRuntime
from rendering.quick.state import capture_display_identity


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
    assert source.index("self.input_controller.close_input()") < source.index(
        "self.frame_pacer.close()"
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
            "--hide-show-cycles",
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
    assert report["completed_generations"] == 2
    assert report["created_windows"] == 2
    assert report["requested_hide_show_cycles"] == 1
    assert [window["generation"] for window in report["windows"]] == [0, 1]
    barriers = report["runtime_root_destruction_barriers"]
    assert [barrier["generation"] for barrier in barriers] == [0, 1]
    assert all(barrier["crossed"] is True for barrier in barriers)
    assert all(barrier["expected_runtime_roots"] == 1 for barrier in barriers)
    assert all(barrier["destroyed_runtime_roots"] == 1 for barrier in barriers)
    assert barriers[0]["next_generation_started"] is True
    assert barriers[0]["next_generation_started_after_crossing"] is True
    assert barriers[1]["next_generation_started"] is False

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
        assert runtime["input"]["admission_open"] is False
        assert runtime["input"]["runtime_generation"] == generation
        assert len(window["hide_show_cycles"]) == 1
        cycle = window["hide_show_cycles"][0]
        assert cycle["hidden_runtime_state"]["phase"] == "paused"
        assert cycle["hidden_runtime_state"]["window"]["visible"] is False
        assert cycle["hidden_runtime_state"]["frame_pacer"]["paused"] is True
        assert cycle["hidden_runtime_state"]["frame_pacer"]["demands"] == [
            "visualizer"
        ]
        assert cycle["hidden_runtime_state"]["scene_readiness"][
            "qml_objects_retired"
        ] is False
        assert cycle["resumed_runtime_state"]["phase"] == "visible"
        assert cycle["resumed_runtime_state"]["window"]["visible"] is True
        assert cycle["resumed_runtime_state"]["frame_pacer"]["active"] is True
        assert cycle["resumed_runtime_state"]["scene_readiness"][
            "ready_for_reveal"
        ] is True
        assert cycle["qml_root_preserved_while_hidden"] is True
        assert cycle["qml_root_preserved_after_resume"] is True
        assert cycle["resumed_runtime_state"]["runtime_generation"] == generation
        assert window["final_scene_state"]["readiness"]["qml_objects_retired"] is True
        assert window["final"]["initialize_count"] == 2
        assert window["final"]["release_count"] == 2
        assert window["final"]["release_thread_id"] == window["final"]["render_thread_id"]
        assert window["final"]["invalidation_count"] >= 1

    assert object_names == [
        "srpss-quick-display-0-generation-0",
        "srpss-quick-display-0-generation-1",
    ]


def test_threaded_runtime_input_exit_retires_complete_display_set():
    env = os.environ.copy()
    env["QSG_RENDER_LOOP"] = "basic"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.qtquick_render_node_smoke",
            "--windows",
            "2",
            "--generations",
            "1",
            "--exit-via-input",
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
    assert report["requested_exit_via_input"] is True
    assert report["completed_generations"] == 1
    assert report["created_windows"] == report["concurrent_windows"]
    barriers = report["runtime_root_destruction_barriers"]
    assert len(barriers) == 1
    assert barriers[0]["crossed"] is True
    assert barriers[0]["expected_runtime_roots"] == report["concurrent_windows"]
    assert barriers[0]["destroyed_runtime_roots"] == report["concurrent_windows"]
    assert barriers[0]["next_generation_started"] is False

    exit_sequence = report["exit_sequence"]
    assert exit_sequence["source_screen_index"] == 0
    assert exit_sequence["source_runtime_generation"] == 0
    assert exit_sequence["source_event_accepted"] is True
    assert exit_sequence["request_count"] == 1
    assert exit_sequence["retirement_deferred"] is True
    assert exit_sequence["runtime_phases_at_request"] == [
        "visible"
    ] * report["concurrent_windows"]
    assert exit_sequence["runtime_state_at_request"]["input"]["exiting"] is True
    assert (
        exit_sequence["runtime_state_at_request"]["input"]["admission_open"]
        is True
    )
    assert exit_sequence["coordinated_runtime_count"] == report["concurrent_windows"]
    assert exit_sequence["post_close_event_accepted"] is True
    assert exit_sequence["request_count_after_post_close_event"] == 1

    retiring_states = exit_sequence["runtime_states_after_admission_close"]
    assert len(retiring_states) == report["concurrent_windows"]
    for state in retiring_states:
        assert state["phase"] == "retiring"
        assert state["input"]["admission_open"] is False
        assert state["close_meta_calls_queued"] is True

    for window in report["windows"]:
        runtime = window["runtime_state"]
        assert runtime["phase"] == "retired"
        assert runtime["retirement_completed"] is True
        assert runtime["input"]["admission_open"] is False
        assert window["final"]["release_thread_id"] == window["final"][
            "render_thread_id"
        ]


def test_threaded_runtime_uses_exact_identity_for_two_physical_displays(qt_app):
    screens = list(qt_app.screens())
    if len(screens) < 2:
        pytest.skip("two physical displays are required for the multi-display gate")
    expected = [
        capture_display_identity(
            screen_index=index,
            runtime_generation=0,
            screen=screen,
        )
        for index, screen in enumerate(screens[:2])
    ]

    env = os.environ.copy()
    env["QSG_RENDER_LOOP"] = "basic"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.qtquick_render_node_smoke",
            "--windows",
            "2",
            "--generations",
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
    assert report["concurrent_windows"] == 2
    assert report["created_windows"] == 2
    assert report["physical_screens"] >= 2
    assert report["requested_hide_show_cycles"] == 0

    for index, (window, identity) in enumerate(zip(report["windows"], expected)):
        actual = window["display_identity"]
        assert window["index"] == index
        assert actual["screen_index"] == index
        assert actual["runtime_generation"] == 0
        assert actual["screen_key"] == identity.screen_key
        assert actual["geometry"] == list(identity.geometry)
        assert actual["available_geometry"] == list(identity.available_geometry)
        assert actual["device_pixel_ratio"] == pytest.approx(
            identity.device_pixel_ratio,
            abs=1e-6,
        )
        assert actual["refresh_rate_hz"] == pytest.approx(
            identity.refresh_rate_hz,
            abs=0.1,
        )
        assert window["hide_show_cycles"] == []
        assert window["runtime_state"]["phase"] == "retired"
        assert window["final"]["initialize_count"] == 1
        assert window["final"]["release_count"] == 1
        assert window["final"]["release_thread_id"] == window["final"][
            "render_thread_id"
        ]
