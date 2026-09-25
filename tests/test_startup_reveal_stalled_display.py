"""A healthy display's widgets are never held behind a failed or stalled sibling.

The coordinated retained reveal used to wait for *every* selected display
without bound, so one display whose Quick readiness failed, or that never
reached a first frame, kept all widgets on the healthy displays at opacity 0.
The bounded wait that fixed it then drove the shared fade on every display,
so a stalled display inherited the fade before its first wallpaper presented.

These bars run the real DisplayManager gate and per-display gate projection,
the real startup-reveal coordinator (QVariantAnimation) and ThreadManager's
real one-shot on the Qt loop. Display units are primitive stand-ins that store
each display's startup gate the way the retained host does; they prove the
gating contract, not native Windows presentation.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

import engine.display_manager as display_manager_module
from engine.display_manager import DisplayManager
from rendering.quick.state import QuickSceneReadiness

GENERATION = 91


class _Gate:
    """One display's stored startup gate (host or Visualizer root)."""

    def __init__(self) -> None:
        self.value = 1.0  # the retained host's pre-prime default
        self.history: list[tuple[float, float]] = []

    def set(self, value: float) -> None:
        self.value = float(value)
        self.history.append((time.monotonic(), self.value))

    def set_startup_reveal_opacity(self, value: float) -> tuple[str, ...]:
        self.set(value)
        return ("clock",)


def _ready(screen_index: int) -> QuickSceneReadiness:
    return QuickSceneReadiness(
        screen_index=screen_index,
        runtime_generation=GENERATION,
        qml_root_created=True,
        scene_graph_initialized=True,
        background_renderer_ready=True,
        intentional_base_frame_ready=True,
    )


def _display(screen_index: int):
    widgets = _Gate()
    visualizer = _Gate()

    def _set_visualizer(value: float) -> bool:
        visualizer.set(value)
        return True

    unit = SimpleNamespace(
        screen_index=screen_index,
        is_retired=False,
        presenter=widgets,
        runtime=SimpleNamespace(
            scene_readiness=_ready(screen_index),
            scene_controller=SimpleNamespace(
                set_visualizer_startup_reveal_opacity=_set_visualizer,
            ),
        ),
    )
    return unit, widgets, visualizer


def _make_manager(monkeypatch, *, reveal_ms: int | None):
    monkeypatch.setattr(
        display_manager_module,
        "QUICK_STARTUP_REVEAL_STALL_DEADLINE_MS",
        120,
    )
    if reveal_ms is not None:
        monkeypatch.setattr(
            display_manager_module,
            "QUICK_STARTUP_REVEAL_DURATION_MS",
            reveal_ms,
        )
    manager = DisplayManager(
        resource_manager=object(),
        thread_manager=None,
        runtime_generation=GENERATION,
    )
    units = [_display(0), _display(1)]
    manager.displays = [unit for unit, _widgets, _visualizer in units]
    manager._prepare_quick_startup_reveal(manager.displays)
    reveals: list[int] = []
    first_frames: list[int] = []
    manager.startup_reveal_completed.connect(reveals.append)
    manager.authoritative_first_frames_ready.connect(first_frames.append)
    return manager, units, reveals, first_frames


def _retire(manager) -> None:
    manager._cancel_quick_startup_reveal()
    manager.disconnect_monitor_detection()
    manager.displays = []
    manager.deleteLater()


@pytest.fixture
def two_display_manager(qt_app, monkeypatch):
    manager, units, reveals, first_frames = _make_manager(monkeypatch, reveal_ms=40)
    yield manager, manager._quick_startup_reveal, units, reveals, first_frames
    _retire(manager)


def test_all_ready_displays_reveal_together_without_waiting(two_display_manager, qtbot):
    manager, coordinator, units, reveals, _first = two_display_manager

    manager._mark_startup_reveal_ready(0)
    assert coordinator.is_started is False
    manager._mark_startup_reveal_ready(1)
    assert coordinator.is_started is True
    qtbot.waitUntil(lambda: reveals == [GENERATION], timeout=2000)
    # The ordinary shape: one shared fade opened every display.
    for _unit, widgets, visualizer in units:
        assert widgets.value == 1.0
        assert visualizer.value == 1.0
    assert manager._late_startup_reveals == {}


def test_stalled_display_releases_healthy_reveal_after_bounded_wait(
    two_display_manager,
    qtbot,
):
    manager, coordinator, units, reveals, _first = two_display_manager
    (_u0, widgets0, _v0), (_u1, widgets1, visualizer1) = units

    manager._mark_startup_reveal_ready(0)
    # Healthy siblings are still given the bounded window to arrive.
    qtbot.wait(40)
    assert coordinator.is_started is False

    qtbot.waitUntil(lambda: coordinator.is_started, timeout=2000)
    qtbot.waitUntil(lambda: reveals == [GENERATION], timeout=2000)
    assert widgets0.value == 1.0
    # The stalled display did not inherit the healthy display's fade.
    assert widgets1.value == 0.0
    assert visualizer1.value == 0.0

    # The late sibling gets its own reveal; the shared one neither restarts
    # nor re-emits lifecycle completion.
    manager._mark_startup_reveal_ready(1)
    qtbot.waitUntil(lambda: widgets1.value == 1.0, timeout=2000)
    qtbot.wait(100)
    assert reveals == [GENERATION]
    manager._mark_startup_reveal_ready(1)  # every later image re-marks ready
    assert len(manager._late_startup_reveals) == 1


def test_failed_display_readiness_stops_gating_immediately(two_display_manager, qtbot):
    manager, coordinator, units, reveals, first_frames = two_display_manager
    failed_unit = manager.displays[1]
    widgets1 = units[1][1]

    manager._on_image_displayed(0, "healthy.jpg")
    manager._mark_startup_reveal_ready(0)
    assert first_frames == []
    assert coordinator.is_started is False

    manager._on_quick_readiness_changed(
        failed_unit,
        QuickSceneReadiness(
            screen_index=1,
            runtime_generation=GENERATION,
            qml_root_created=True,
            error="render thread failed",
        ),
        manager._display_startup_generation,
    )

    assert first_frames == [GENERATION]
    assert coordinator.is_started is True
    qtbot.waitUntil(lambda: reveals == [GENERATION], timeout=2000)
    assert widgets1.value == 0.0


def test_retired_manager_deadline_never_reveals(two_display_manager, qtbot):
    manager, coordinator, units, reveals, _first = two_display_manager

    manager._mark_startup_reveal_ready(0)
    manager._display_startup_generation += 1  # the generation's displays retired
    qtbot.wait(300)
    assert coordinator.is_started is False
    assert reveals == []
    assert [widgets.value for _unit, widgets, _vis in units] == [0.0, 0.0]


def _non_decreasing(history: list[tuple[float, float]]) -> bool:
    values = [value for _t, value in history]
    return all(later >= earlier for earlier, later in zip(values, values[1:]))


def test_late_display_fades_in_on_its_own_after_its_first_wallpaper(
    qt_app,
    qtbot,
    monkeypatch,
):
    """Two monitors, real 1,800 ms fades: display 1 stalls, then recovers mid-fade."""

    manager, units, reveals, _first = _make_manager(monkeypatch, reveal_ms=None)
    try:
        coordinator = manager._quick_startup_reveal
        (unit0, widgets0, visualizer0), (unit1, widgets1, visualizer1) = units
        startup = manager._display_startup_generation
        duration_s = display_manager_module.QUICK_STARTUP_REVEAL_DURATION_MS / 1000.0
        assert duration_s == 1.8

        # Before: every display is primed closed.
        assert [widgets0.value, visualizer0.value, widgets1.value, visualizer1.value] == [0.0] * 4

        # Display 0 becomes ready the production way; display 1 stalls.
        manager._on_quick_readiness_changed(unit0, _ready(0), startup)
        manager._on_image_displayed(0, "healthy.jpg")
        assert coordinator.is_started is False
        qtbot.waitUntil(lambda: coordinator.is_started, timeout=2000)
        shared_started = time.monotonic()

        # During the healthy fade the stalled display stays closed.
        qtbot.waitUntil(lambda: 0.2 < widgets0.value < 0.8, timeout=2000)
        assert widgets1.value == 0.0 and visualizer1.value == 0.0

        # Quick readiness alone (its wallpaper not yet presented) is not enough.
        manager._on_quick_readiness_changed(unit1, _ready(1), startup)
        qtbot.wait(100)
        assert widgets1.value == 0.0 and visualizer1.value == 0.0

        # Its first wallpaper finishes presenting mid-way through the healthy fade.
        healthy_at_recovery = widgets0.value
        assert 0.0 < healthy_at_recovery < 1.0
        late_started = time.monotonic()
        manager._on_image_displayed(1, "late.jpg")

        # The healthy display finishes on its own schedule, never restarted.
        qtbot.waitUntil(lambda: widgets0.value == 1.0, timeout=4000)
        healthy_done = time.monotonic()
        assert healthy_done - shared_started < duration_s + 0.6
        assert _non_decreasing(widgets0.history)
        assert reveals == [GENERATION]
        # Display 1 is still mid-fade when display 0 completes.
        assert 0.0 < widgets1.value < 1.0

        # After: display 1 reaches full opacity through its own gentle fade.
        qtbot.waitUntil(lambda: widgets1.value == 1.0, timeout=4000)
        late_done = time.monotonic()
        assert late_done - late_started >= duration_s - 0.2
        assert all(value == 0.0 for t, value in widgets1.history if t < late_started)
        assert _non_decreasing(widgets1.history)
        intermediate = [value for t, value in widgets1.history if 0.0 < value < 1.0]
        assert len(intermediate) >= 10  # gradual, not an abrupt jump to 1.0
        assert visualizer1.value == 1.0
        assert all(value == 0.0 for t, value in visualizer1.history if t < late_started)
        # The late reveal publishes no second generation completion.
        qtbot.wait(100)
        assert reveals == [GENERATION]
    finally:
        _retire(manager)
