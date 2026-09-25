"""A healthy display's widgets are never held behind a failed or stalled sibling.

The coordinated retained reveal used to wait for *every* selected display
without bound, so one display whose Quick readiness failed, or that never
reached a first frame, kept all widgets on the healthy displays at opacity 0.

These bars run the real DisplayManager gate, the real startup-reveal
coordinator (QVariantAnimation) and ThreadManager's real one-shot on the Qt
loop. Display units are primitive stand-ins; they prove the gating contract,
not native Windows presentation.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import engine.display_manager as display_manager_module
from engine.display_manager import DisplayManager
from rendering.quick.startup_reveal import QuickStartupRevealCoordinator
from rendering.quick.state import QuickSceneReadiness


@pytest.fixture
def two_display_manager(qt_app, monkeypatch):
    monkeypatch.setattr(
        display_manager_module,
        "QUICK_STARTUP_REVEAL_STALL_DEADLINE_MS",
        120,
    )
    manager = DisplayManager(
        resource_manager=object(),
        thread_manager=None,
        runtime_generation=91,
    )
    manager.displays = [
        SimpleNamespace(screen_index=0),
        SimpleNamespace(screen_index=1),
    ]
    opacities: list[float] = []
    coordinator = QuickStartupRevealCoordinator(
        runtime_generation=91,
        opacity_sink=lambda value: opacities.append(float(value)) or 1,
        duration_ms=40,
        parent=manager,
    )
    coordinator.completed.connect(manager._on_quick_startup_reveal_finished)
    manager._quick_startup_reveal = coordinator
    coordinator.prime()
    reveals: list[int] = []
    first_frames: list[int] = []
    manager.startup_reveal_completed.connect(reveals.append)
    manager.authoritative_first_frames_ready.connect(first_frames.append)
    yield manager, coordinator, opacities, reveals, first_frames
    manager._cancel_quick_startup_reveal()
    manager.disconnect_monitor_detection()
    manager.displays = []
    manager.deleteLater()


def test_all_ready_displays_reveal_together_without_waiting(two_display_manager, qtbot):
    manager, coordinator, _opacities, reveals, _first = two_display_manager

    manager._mark_startup_reveal_ready(0)
    assert coordinator.is_started is False
    manager._mark_startup_reveal_ready(1)
    assert coordinator.is_started is True
    qtbot.waitUntil(lambda: reveals == [91], timeout=2000)


def test_stalled_display_releases_healthy_reveal_after_bounded_wait(
    two_display_manager,
    qtbot,
):
    manager, coordinator, opacities, reveals, _first = two_display_manager

    manager._mark_startup_reveal_ready(0)
    # Healthy siblings are still given the bounded window to arrive.
    qtbot.wait(40)
    assert coordinator.is_started is False

    qtbot.waitUntil(lambda: coordinator.is_started, timeout=2000)
    qtbot.waitUntil(lambda: reveals == [91], timeout=2000)
    assert opacities[-1] == 1.0

    # The late sibling joining afterwards neither restarts nor re-emits.
    manager._mark_startup_reveal_ready(1)
    qtbot.wait(200)
    assert reveals == [91]


def test_failed_display_readiness_stops_gating_immediately(two_display_manager, qtbot):
    manager, coordinator, _opacities, reveals, first_frames = two_display_manager
    failed_unit = manager.displays[1]

    manager._on_image_displayed(0, "healthy.jpg")
    manager._mark_startup_reveal_ready(0)
    assert first_frames == []
    assert coordinator.is_started is False

    manager._on_quick_readiness_changed(
        failed_unit,
        QuickSceneReadiness(
            screen_index=1,
            runtime_generation=91,
            qml_root_created=True,
            error="render thread failed",
        ),
        manager._display_startup_generation,
    )

    assert first_frames == [91]
    assert coordinator.is_started is True
    qtbot.waitUntil(lambda: reveals == [91], timeout=2000)


def test_retired_manager_deadline_never_reveals(two_display_manager, qtbot):
    manager, coordinator, _opacities, reveals, _first = two_display_manager

    manager._mark_startup_reveal_ready(0)
    manager._display_startup_generation += 1  # the generation's displays retired
    qtbot.wait(300)
    assert coordinator.is_started is False
    assert reveals == []
