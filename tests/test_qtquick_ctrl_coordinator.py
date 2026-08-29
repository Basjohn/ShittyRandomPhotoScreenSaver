"""Shared cross-display Ctrl coordinator bars (H).

Prove the OR-of-displays authoritative semantics and, through two real
QuickInputControllers, that Ctrl held on display A is visible to display B and
that A releasing (or retiring) clears the shared truth - the G8 cross-display
stuck-Ctrl invariant.
"""

from __future__ import annotations

import pytest

from rendering.quick.ctrl_coordinator import SharedCtrlCoordinator


def test_global_held_is_or_across_displays() -> None:
    coord = SharedCtrlCoordinator()
    provider = coord.held_provider()
    publish_a = coord.publisher_for(0)
    publish_b = coord.publisher_for(1)

    assert provider() is False

    publish_a(True)
    assert provider() is True  # A holds -> globally held
    assert coord.is_display_held(0) is True
    assert coord.is_display_held(1) is False

    publish_b(True)
    assert provider() is True

    # A releasing does not clear B's independent hold.
    publish_a(False)
    assert provider() is True
    publish_b(False)
    assert provider() is False


def test_forget_drops_a_retired_displays_stuck_contribution() -> None:
    coord = SharedCtrlCoordinator()
    provider = coord.held_provider()
    coord.publisher_for(0)(True)  # A holds and never releases
    assert provider() is True

    # A's generation retires without releasing -> its contribution is forgotten.
    coord.forget(0)
    assert provider() is False
    assert coord.contributing_display_count == 0


@pytest.mark.qt
def test_ctrl_held_on_display_a_is_authoritative_on_display_b(qt_app) -> None:
    from rendering.quick.input_controller import QuickInputController

    coord = SharedCtrlCoordinator()
    controller_a = QuickInputController(
        screen_index=0,
        runtime_generation=1,
        interaction_mode_provider=lambda: True,
        global_ctrl_held_provider=coord.held_provider(),
        ctrl_state_publisher=coord.publisher_for(0),
    )
    controller_b = QuickInputController(
        screen_index=1,
        runtime_generation=1,
        interaction_mode_provider=lambda: True,
        global_ctrl_held_provider=coord.held_provider(),
        ctrl_state_publisher=coord.publisher_for(1),
    )
    try:
        assert controller_b.is_ctrl_mode_active() is False

        # Ctrl pressed on A publishes into the shared truth.
        controller_a.set_ctrl_held(True)
        # B, which never saw the key, is Ctrl-active via the authoritative provider.
        assert controller_b.is_ctrl_mode_active() is True

        # A releases -> B is no longer Ctrl-active (not stuck).
        controller_a.set_ctrl_held(False)
        assert controller_b.is_ctrl_mode_active() is False
    finally:
        controller_a.deleteLater()
        controller_b.deleteLater()
        qt_app.processEvents()
