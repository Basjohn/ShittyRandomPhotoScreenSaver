"""Exactly one retained context menu may be visible across all displays.

The operator observed that opening a menu on one display left an earlier menu
still visible on another display. The retained menu models are per display
generation; the cross-display owner (DisplayManager) must retire the others when
one opens. These bars pin the pure coordination helper and prove it retires a
sibling display's menu through the real production model + input-suppression
wiring, without creating a second menu, window or surface.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from rendering.quick.context_menu import (
    QuickContextMenuEntry,
    QuickContextMenuModel,
    enforce_single_visible_context_menu,
)
from rendering.quick.runtime import QuickDisplayRuntime
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy


def _entries() -> tuple[QuickContextMenuEntry, ...]:
    return (
        QuickContextMenuEntry("next", "Next Image"),
        QuickContextMenuEntry("exit", "Exit"),
    )


def _open_model(screen_index: int) -> QuickContextMenuModel:
    model = QuickContextMenuModel(screen_index=screen_index, runtime_generation=1)
    model.replace_entries(_entries())
    assert model.open_at(10.0, 10.0) is True
    assert model.menuVisible is True
    return model


def test_enforce_keeps_only_the_opened_menu_visible() -> None:
    models = [_open_model(0), _open_model(1), _open_model(2)]
    opened = models[1]

    dismissed = enforce_single_visible_context_menu(models, opened)

    assert opened.menuVisible is True
    assert models[0].menuVisible is False
    assert models[2].menuVisible is False
    assert set(dismissed) == {models[0], models[2]}


def test_enforce_is_idempotent_for_already_hidden_siblings() -> None:
    opened = _open_model(0)
    hidden = QuickContextMenuModel(screen_index=1, runtime_generation=1)
    hidden.replace_entries(_entries())  # never opened -> not visible

    dismissed = enforce_single_visible_context_menu([opened, hidden], opened)

    assert opened.menuVisible is True
    assert dismissed == []  # nothing was visible to dismiss


def test_enforce_skips_a_retired_sibling_without_faulting() -> None:
    class _DeadModel:
        def dismiss(self) -> bool:
            raise RuntimeError("underlying C++ object already retired")

    opened = _open_model(0)
    live_sibling = _open_model(1)

    dismissed = enforce_single_visible_context_menu(
        [opened, _DeadModel(), live_sibling], opened
    )

    assert opened.menuVisible is True
    assert live_sibling.menuVisible is False
    assert dismissed == [live_sibling]


def test_opening_one_display_menu_retires_the_other_through_production_wiring(
    qt_app,
) -> None:
    """Two real display runtimes: opening B's menu must retire A's menu and its
    input suppression, proving the coordinator works through production models."""

    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    runtime_a = QuickDisplayRuntime(
        screen_index=0,
        runtime_generation=51,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
        interaction_mode_provider=lambda: True,
    )
    runtime_b = QuickDisplayRuntime(
        screen_index=1,
        runtime_generation=51,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(always_on_top=False, blank_cursor=False),
        interaction_mode_provider=lambda: True,
    )
    try:
        for runtime in (runtime_a, runtime_b):
            model = runtime.context_menu_model
            model.replace_entries(_entries())
            model.set_action_handler(lambda action_id, payload: True)

        assert runtime_a.context_menu_model.open_at(20.0, 20.0) is True
        assert runtime_a.input_controller.input_state.context_menu_active is True

        # Opening B routes through the same enforcement the DisplayManager wires.
        assert runtime_b.context_menu_model.open_at(40.0, 40.0) is True
        enforce_single_visible_context_menu(
            [runtime_a.context_menu_model, runtime_b.context_menu_model],
            runtime_b.context_menu_model,
        )

        assert runtime_b.context_menu_model.menuVisible is True
        assert runtime_a.context_menu_model.menuVisible is False
        # The dismiss must propagate through the real visibility -> input chain.
        assert runtime_a.input_controller.input_state.context_menu_active is False
        assert runtime_b.input_controller.input_state.context_menu_active is True
    finally:
        runtime_a.close_runtime()
        runtime_b.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()
