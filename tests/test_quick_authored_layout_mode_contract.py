"""Source-level guardrails for the global authored-layout/CUSTOM boundary."""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _function_source(relative: str, name: str) -> str:
    source = _source(relative)
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            segment = ast.get_source_segment(source, node)
            assert segment is not None
            return segment
    raise AssertionError(f"function {name!r} not found in {relative}")


def test_presenter_construction_disables_authored_layout_when_any_route_is_custom() -> None:
    source = _function_source("rendering/quick/display_presenter.py", "bind_families")
    assert "is_global_custom_layout_mode_selected" in source
    assert "self._authored_layout_enabled = not" in source


def test_live_edit_disables_authored_layout_before_custom_session_capture() -> None:
    source = _function_source("engine/display_manager.py", "_start_quick_custom_layout_session")
    disable_at = source.index("_set_quick_authored_layout_enabled(False")
    start_at = source.index("_quick_custom_layout_owner.start()")
    assert disable_at < start_at


def test_number_key_slot_load_quiesces_authored_layout_before_rebuild() -> None:
    source = _function_source("engine/display_manager.py", "_load_layout_slot")
    disable_at = source.index("_set_quick_authored_layout_enabled(False")
    cancel_at = source.index("_quick_custom_layout_owner.cancel()")
    reload_at = source.index('_request_custom_layout_runtime_reload("slot_load")')
    assert disable_at < cancel_at < reload_at


def test_global_disable_detaches_adjacency_observer_and_obstacles() -> None:
    source = _function_source("engine/display_manager.py", "_set_quick_authored_layout_enabled")
    assert "set_layout_observer(None)" in source
    assert "set_external_stack_obstacles(None, reflow=False)" in source
    assert "_project_quick_visualizer_base_authored_origin()" in source


def test_visualizer_adjacency_requires_global_authored_layout_admission() -> None:
    source = _function_source("engine/display_manager.py", "_resolve_quick_visualizer_authored_layout")
    assert "not chosen.presenter.authored_layout_enabled" in source
    assert "is_global_custom_layout_mode_selected(widgets)" in source


def test_global_custom_visualizer_uses_plain_authored_anchor_not_zero_origin() -> None:
    source = _function_source("engine/display_manager.py", "_construct_quick_visualizer_owner_on")
    adjacency_at = source.index("_resolve_quick_visualizer_authored_layout")
    base_at = source.index("_resolve_quick_visualizer_base_authored_origin")
    assert adjacency_at < base_at
    assert "owner.set_authored_outer_origin(base_origin[0], base_origin[1])" in source
