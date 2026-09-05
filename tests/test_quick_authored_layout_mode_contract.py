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


# --- Behavioural: number-key slot save/load commit-once (current owner) ------ #
#
# The layout-slot save/load lifecycle moved off the retired DisplayWidget onto
# DisplayManager. These bars prove a single slot operation commits the CUSTOM
# session and requests the fenced runtime rebuild EXACTLY once (no duplicate
# session commit / duplicate lifecycle application), exercising the real
# engine.display_manager methods rather than a legacy shell.


def test_number_key_slot_save_commits_custom_and_reloads_exactly_once() -> None:
    from types import SimpleNamespace
    from unittest.mock import Mock

    from engine.display_manager import DisplayManager

    manager = DisplayManager.__new__(DisplayManager)
    reload_calls: list[str] = []
    manager._request_custom_layout_runtime_reload = lambda kind: reload_calls.append(kind)

    owner = Mock()
    owner.is_active = True
    owner.save.return_value = True
    owner.take_deferred_topology_reconciliation.return_value = "slot_save"
    manager._quick_custom_layout_owner = owner

    saved_maps: list[tuple[dict, bool]] = []
    settings = SimpleNamespace(
        get_widgets_map=lambda: {"clock": {"position": "Top Left", "font_size": 24}},
        set_widgets_map=lambda widgets, *, emit_change=True: saved_maps.append(
            (widgets, emit_change)
        ),
        save=Mock(),
    )
    manager.settings_manager = settings

    assert DisplayManager._save_layout_slot(manager, "1") is True

    # One CUSTOM session capture (deferring topology), one deferred reconcile take.
    owner.save.assert_called_once_with(defer_topology_reconciliation=True)
    owner.take_deferred_topology_reconciliation.assert_called_once_with()
    # Exactly one fenced lifecycle rebuild request, and no live-emit persistence.
    assert reload_calls == ["save_continue"]
    settings.save.assert_called_once_with()
    assert len(saved_maps) == 1 and saved_maps[0][1] is False
    assert "1" in saved_maps[0][0]["layout_slots"]["slots"]


def test_number_key_slot_load_quiesces_and_reloads_exactly_once() -> None:
    from copy import deepcopy
    from types import SimpleNamespace
    from unittest.mock import Mock

    from engine.display_manager import DisplayManager

    manager = DisplayManager.__new__(DisplayManager)
    reload_calls: list[str] = []
    disable_calls: list[tuple[bool, bool]] = []
    manager._request_custom_layout_runtime_reload = lambda kind: reload_calls.append(kind)
    manager._set_quick_authored_layout_enabled = (
        lambda enabled, *, restore_base=False: disable_calls.append(
            (enabled, restore_base)
        )
    )

    owner = Mock()
    owner.is_active = True
    manager._quick_custom_layout_owner = owner

    slot_payload = {
        "version": 1,
        "widgets": {"clock": {"position": "Bottom Right", "font_size": 64}},
        "custom_layout": {"version": 2, "displays": {}},
        "custom_layout_restore": {"widgets": {}},
    }
    widgets_map = {
        "clock": {"position": "Top Left", "font_size": 24, "timezone": "local"},
        "layout_slots": {"version": 1, "slots": {"1": deepcopy(slot_payload)}},
        "custom_layout": {"version": 2, "displays": {"screen:old": {"clock": {}}}},
    }
    saved_maps: list[tuple[dict, bool]] = []
    settings = SimpleNamespace(
        get_widgets_map=lambda: deepcopy(widgets_map),
        set_widgets_map=lambda widgets, *, emit_change=True: saved_maps.append(
            (widgets, emit_change)
        ),
        save=Mock(),
    )
    manager.settings_manager = settings

    assert DisplayManager._load_layout_slot(manager, "1") is True

    # Authored layout quiesced once, the live CUSTOM edit cancelled once, and a
    # single fenced runtime rebuild requested — never duplicated.
    assert disable_calls == [(False, True)]
    owner.cancel.assert_called_once_with()
    assert reload_calls == ["slot_load"]
    settings.save.assert_called_once_with()
    assert len(saved_maps) == 1 and saved_maps[0][1] is False
