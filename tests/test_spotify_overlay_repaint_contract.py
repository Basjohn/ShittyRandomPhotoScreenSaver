from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from widgets.spotify_bars_gl_overlay import (
    SpotifyBarsGLOverlay,
    _PERF_MICROGAP_BUCKET_UPPER_MS,
    _perf_histogram_bucket_index,
    _perf_histogram_percentile_ms,
)


def _method_tree(class_node: ast.ClassDef, method_name: str) -> ast.FunctionDef:
    for node in class_node.body:
        if isinstance(node, ast.FunctionDef) and node.name == method_name:
            return node
    raise AssertionError(f"method not found: {method_name}")


def _calls_self_update(method: ast.FunctionDef) -> bool:
    for node in ast.walk(method):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != "update":
            continue
        if isinstance(func.value, ast.Name) and func.value.id == "self":
            return True
    return False


def _calls_method(method: ast.FunctionDef, method_name: str) -> bool:
    for node in ast.walk(method):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not isinstance(func, ast.Attribute) or func.attr != method_name:
            continue
        if isinstance(func.value, ast.Name) and func.value.id == "self":
            return True
    return False


def _references_attribute(method: ast.FunctionDef, attr_name: str) -> bool:
    return any(
        isinstance(node, ast.Attribute) and node.attr == attr_name
        for node in ast.walk(method)
    )


def test_spotify_overlay_paintgl_does_not_self_schedule_repaint():
    source_path = Path(__file__).resolve().parents[1] / "widgets" / "spotify_bars_gl_overlay.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    overlay_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SpotifyBarsGLOverlay"
    )

    paint_gl = _method_tree(overlay_class, "paintGL")
    set_state = _method_tree(overlay_class, "set_state")
    request_frame_update = _method_tree(overlay_class, "_request_frame_update")

    assert not _calls_self_update(paint_gl)
    assert not _calls_self_update(set_state)
    assert _calls_method(set_state, "_request_frame_update")
    assert _calls_self_update(request_frame_update)
    assert _calls_method(request_frame_update, "_record_perf_update_request")
    assert _calls_method(paint_gl, "_record_perf_paint_delivery")
    assert not _references_attribute(request_frame_update, "_owner_target_fps")
    assert not _references_attribute(request_frame_update, "_update_pending")


def test_spotify_overlay_microgap_histogram_keeps_fixed_bucket_percentile():
    histogram = [0] * (len(_PERF_MICROGAP_BUCKET_UPPER_MS) + 1)
    for value_ms in (6.0, 7.0, 9.0, 11.0, 17.0, 121.4):
        histogram[_perf_histogram_bucket_index(value_ms)] += 1

    assert _perf_histogram_percentile_ms(histogram, 6, 121.4) == 150.0

    bounded_histogram = [0] * (len(_PERF_MICROGAP_BUCKET_UPPER_MS) + 1)
    for value_ms in (6.0, 7.0, 9.0, 11.0, 17.0):
        bounded_histogram[_perf_histogram_bucket_index(value_ms)] += 1
    assert _perf_histogram_percentile_ms(bounded_histogram, 5, 17.0) == 24.0


def test_spotify_overlay_microgap_context_separates_transition_and_mode_handoff():
    visualizer = SimpleNamespace(
        _mode_transition_phase=0,
        _mode_transition_pending=None,
    )
    parent = SimpleNamespace(
        spotify_visualizer_widget=visualizer,
        _transition_work_pending=False,
        _last_transition_finished_wall_ts=0.0,
        has_running_transition=lambda: False,
    )
    overlay = SimpleNamespace(parent=lambda: parent)
    overlay._perf_last_transition_active_ts = 0.0

    assert SpotifyBarsGLOverlay._perf_microgap_context_index(overlay, 10.0) == 3

    parent._transition_work_pending = True
    assert SpotifyBarsGLOverlay._perf_microgap_context_index(overlay, 11.0) == 0

    visualizer._mode_transition_phase = 1
    assert SpotifyBarsGLOverlay._perf_microgap_context_index(overlay, 11.1) == 2

    visualizer._mode_transition_phase = 0
    parent._transition_work_pending = False
    assert SpotifyBarsGLOverlay._perf_microgap_context_index(overlay, 11.5) == 1
    assert SpotifyBarsGLOverlay._perf_microgap_context_index(overlay, 12.0) == 3


def test_spotify_overlay_microgap_excludes_hidden_and_disabled_intervals():
    overlay = SimpleNamespace(
        _enabled=True,
        isVisible=lambda: False,
        _perf_last_paint_ts=10.0,
        _perf_last_transition_active_ts=15.0,
        _perf_oldest_unpainted_update_ts=20.0,
        _perf_oldest_unpainted_context=3,
    )
    overlay._reset_perf_delivery_origin = lambda: (
        SpotifyBarsGLOverlay._reset_perf_delivery_origin(overlay)
    )

    SpotifyBarsGLOverlay._record_perf_update_request(overlay)
    assert overlay._perf_last_paint_ts == 0.0
    assert overlay._perf_last_transition_active_ts == 0.0
    assert overlay._perf_oldest_unpainted_update_ts == 0.0
    assert overlay._perf_oldest_unpainted_context == -1

    overlay._perf_last_paint_ts = 10.0
    overlay._perf_last_transition_active_ts = 15.0
    overlay._perf_oldest_unpainted_update_ts = 20.0
    overlay._perf_oldest_unpainted_context = 3
    overlay._enabled = False
    SpotifyBarsGLOverlay._record_perf_paint_delivery(overlay)
    assert overlay._perf_last_paint_ts == 0.0
    assert overlay._perf_last_transition_active_ts == 0.0
    assert overlay._perf_oldest_unpainted_update_ts == 0.0
    assert overlay._perf_oldest_unpainted_context == -1
