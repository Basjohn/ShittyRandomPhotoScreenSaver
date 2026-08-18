from __future__ import annotations

import ast
from pathlib import Path


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


def test_spotify_overlay_render_does_not_self_schedule_repaint():
    source_path = Path(__file__).resolve().parents[1] / "widgets" / "spotify_bars_gl_overlay.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    overlay_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "SpotifyBarsGLOverlay"
    )

    # paintGL became paint_layer when the visualizer stopped owning a
    # surface. The contract it guards is unchanged: the render path is not a
    # repaint scheduler, set_state() remains the sole presentation authority.
    paint_gl = _method_tree(overlay_class, "paint_layer")
    set_state = _method_tree(overlay_class, "set_state")
    request_frame_update = _method_tree(overlay_class, "_request_frame_update")

    assert not _calls_self_update(paint_gl)
    assert not _calls_self_update(set_state)
    assert _calls_method(set_state, "_request_frame_update")

    # The visualizer no longer owns a presentation surface, so the request is a
    # publication to the display compositor rather than self.update(). Asserting
    # a self-repaint here would re-encode the architecture P2-RHI disproved.
    assert not _calls_self_update(request_frame_update), (
        "the visualizer must not repaint a surface of its own"
    )
    assert _calls_method(request_frame_update, "_publication_target_compositor"), (
        "presentation requests must reach the owning display compositor"
    )

    assert not _references_attribute(request_frame_update, "_owner_target_fps")
    assert not _references_attribute(request_frame_update, "_update_pending")
