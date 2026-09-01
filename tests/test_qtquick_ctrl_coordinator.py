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
    publish_a = coord.publisher_for(0)
    publish_b = coord.publisher_for(1)

    assert coord.is_held() is False

    publish_a(True)
    assert coord.is_held() is True  # A holds -> globally held
    assert coord.is_display_held(0) is True
    assert coord.is_display_held(1) is False

    publish_b(True)
    assert coord.is_held() is True

    # A releasing does not clear B's independent hold.
    publish_a(False)
    assert coord.is_held() is True
    publish_b(False)
    assert coord.is_held() is False


def test_forget_drops_a_retired_displays_stuck_contribution() -> None:
    coord = SharedCtrlCoordinator()
    coord.publisher_for(0)(True)  # A holds and never releases
    assert coord.is_held() is True

    # A's generation retires without releasing -> its contribution is forgotten.
    coord.forget(0)
    assert coord.is_held() is False
    assert coord.contributing_display_count == 0


@pytest.mark.qt
def test_ctrl_held_on_display_a_is_authoritative_on_display_b(qt_app) -> None:
    from rendering.quick.input_controller import QuickInputController

    # Event-driven cross-display Ctrl (R6/§4.5): each display publishes only its
    # own contribution and receives the authoritative global OR pushed through
    # the coordinator's subscription. No display polls a provider.
    coord = SharedCtrlCoordinator()
    key_a = (1, 0)
    key_b = (1, 1)
    controller_a = QuickInputController(
        screen_index=0,
        runtime_generation=1,
        interaction_mode_enabled=True,
        ctrl_state_publisher=coord.publisher_for(key_a),
    )
    controller_b = QuickInputController(
        screen_index=1,
        runtime_generation=1,
        interaction_mode_enabled=True,
        ctrl_state_publisher=coord.publisher_for(key_b),
    )
    coord.subscribe(key_a, controller_a.set_shared_ctrl_held)
    coord.subscribe(key_b, controller_b.set_shared_ctrl_held)
    try:
        assert controller_b.is_ctrl_mode_active() is False

        # Ctrl pressed on A publishes into the shared truth and is broadcast.
        controller_a.set_ctrl_held(True)
        # B, which never saw the key, is Ctrl-active via the broadcast global OR.
        assert controller_b.is_ctrl_mode_active() is True

        # A releases -> B is no longer Ctrl-active (not stuck).
        controller_a.set_ctrl_held(False)
        assert controller_b.is_ctrl_mode_active() is False
    finally:
        controller_a.deleteLater()
        controller_b.deleteLater()
        qt_app.processEvents()
