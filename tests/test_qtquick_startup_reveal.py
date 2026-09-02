"""Runtime-shaped contract tests for the coordinated ordinary Quick startup reveal."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from rendering.quick.startup_reveal import (
    QUICK_STARTUP_DESKTOP_CROSSFADE_DURATION_MS,
    QuickStartupRevealCoordinator,
)


def _app() -> QCoreApplication:
    # A GUI QApplication (offscreen in tests), matching every other DisplayManager
    # test: DisplayManager connects QGuiApplication screen-hotplug signals and a
    # bare QCoreApplication both lacks them and crashes PySide teardown here.
    return QApplication.instance() or QApplication([])


def test_startup_reveal_primes_zero_then_completes_at_one_once() -> None:
    _app()
    values: list[float] = []
    completions: list[int] = []

    def sink(value: float) -> int:
        values.append(float(value))
        return 3

    reveal = QuickStartupRevealCoordinator(
        runtime_generation=7,
        opacity_sink=sink,
        duration_ms=12,
    )
    reveal.completed.connect(completions.append)

    assert reveal.prime() == 3
    assert values == [0.0]
    assert reveal.start() is True
    assert reveal.start() is False

    loop = QEventLoop()
    reveal.completed.connect(lambda _generation: loop.quit())
    QTimer.singleShot(500, loop.quit)
    loop.exec()

    assert completions == [7]
    assert reveal.is_completed is True
    assert values[-1] == 1.0
    assert all(0.0 <= value <= 1.0 for value in values)


def test_startup_reveal_cancel_never_publishes_completion() -> None:
    _app()
    values: list[float] = []
    completions: list[int] = []

    reveal = QuickStartupRevealCoordinator(
        runtime_generation=9,
        opacity_sink=lambda value: values.append(float(value)) or 2,
        duration_ms=50,
    )
    reveal.completed.connect(completions.append)

    reveal.prime()
    assert reveal.start() is True
    assert reveal.cancel() is True
    assert reveal.cancel() is False

    loop = QEventLoop()
    QTimer.singleShot(80, loop.quit)
    loop.exec()

    assert values[0] == 0.0
    assert completions == []
    assert reveal.is_completed is False


def test_startup_reveal_with_no_initial_targets_still_runs_shared_scalar() -> None:
    _app()
    values: list[float] = []
    completions: list[int] = []

    reveal = QuickStartupRevealCoordinator(
        runtime_generation=11,
        opacity_sink=lambda value: values.append(float(value)) or 0,
        duration_ms=12,
    )
    reveal.completed.connect(completions.append)

    assert reveal.prime() == 0
    assert reveal.start() is True
    assert completions == []

    loop = QEventLoop()
    reveal.completed.connect(lambda _generation: loop.quit())
    QTimer.singleShot(500, loop.quit)
    loop.exec()

    assert completions == [11]
    assert reveal.is_completed is True
    assert values[0] == 0.0
    assert values[-1] == 1.0



def test_startup_reveal_rescans_targets_created_during_wallpaper_crossfade() -> None:
    _app()
    values: list[float] = []
    target_count = 0

    def sink(value: float) -> int:
        values.append(float(value))
        return target_count

    reveal = QuickStartupRevealCoordinator(
        runtime_generation=13,
        opacity_sink=sink,
        duration_ms=12,
    )

    # Nothing existed when the hidden scene was primed. A retained family then
    # finishes construction while the desktop -> wallpaper crossfade is running.
    assert reveal.prime() == 0
    target_count = 2
    assert reveal.start() is True
    assert reveal.target_count == 2
    assert values[:2] == [0.0, 0.0]

    loop = QEventLoop()
    reveal.completed.connect(lambda _generation: loop.quit())
    QTimer.singleShot(500, loop.quit)
    loop.exec()

    assert reveal.is_completed is True
    assert values[-1] == 1.0

def test_startup_desktop_crossfade_is_one_shot_signal_driven_and_precedes_reveal() -> None:
    root = Path(__file__).resolve().parents[1]
    manager = (root / "engine" / "display_manager.py").read_text(encoding="utf-8")
    engine = (root / "engine" / "screensaver_engine.py").read_text(encoding="utf-8")
    overlay = (root / "rendering" / "quick" / "qml" / "OverlayWidget.qml").read_text(encoding="utf-8")

    assert QUICK_STARTUP_DESKTOP_CROSSFADE_DURATION_MS == 1300
    assert "screen.grabWindow(0)" in manager
    assert 'transition_id="crossfade"' in manager
    assert "_startup_desktop_seed_screens" in manager
    assert manager.index("_prime_quick_startup_desktop_sources(pending_displays)") < manager.index(
        "_prepare_quick_startup_reveal(pending_displays)"
    )
    assert "self._startup_desktop_seed_screens.discard(int(screen_index))" in manager
    assert "if not self._desktop_startup_crossfade_enabled:" in manager
    assert "desktop_startup_crossfade_enabled=(self._runtime_generation == 0)" in engine
    assert "startupRevealOpacity" in overlay
    assert "opacity: fadeOpacity * startupRevealOpacity" in overlay

    # Startup staging must not introduce a recurring timer/poller. The existing
    # reveal uses one bounded QVariantAnimation and the crossfade uses the retained
    # transition lifecycle/finalization signal.
    prime_start = manager.index("    def _prime_quick_startup_desktop_sources")
    prime_end = manager.index("    def _apply_quick_startup_reveal_opacity", prime_start)
    prime = manager[prime_start:prime_end]
    assert "QTimer" not in prime
    assert "singleShot" not in prime



def test_replacement_runtime_does_not_recapture_desktop(qt_app) -> None:
    from engine.display_manager import DisplayManager

    class _MustNotBeTouched:
        @property
        def is_retired(self):
            raise AssertionError("disabled desktop staging must return before display access")

    manager = DisplayManager(
        runtime_generation=4,
        desktop_startup_crossfade_enabled=False,
    )
    manager._startup_desktop_seed_screens = {99}
    try:
        manager._prime_quick_startup_desktop_sources([_MustNotBeTouched()])
        assert manager._startup_desktop_seed_screens == set()
    finally:
        manager.disconnect_monitor_detection()
        manager.deleteLater()
        qt_app.processEvents()

def test_seeded_first_image_uses_fixed_crossfade_without_settings_transition(qt_app) -> None:
    from types import SimpleNamespace

    from PySide6.QtGui import QPixmap

    from engine.display_manager import DisplayManager
    from rendering.quick.display_image_route import presentation_image_from_processed_pixmap

    class _Unit:
        def __init__(self) -> None:
            self.screen_index = 0
            self._current = presentation_image_from_processed_pixmap(
                QPixmap(6, 4),
                image_path="__startup_desktop_screen_0__",
            )
            self.request = None
            self.is_retired = False
            self.runtime = SimpleNamespace(
                scene_controller=SimpleNamespace(presentation_image=self._current)
            )

        def capture_image(self, pixmap, *, image_path=""):
            return presentation_image_from_processed_pixmap(
                pixmap, image_path=image_path
            )

        def current_image(self):
            return self._current

        def present_captured_image(self, image) -> None:
            self._current = image
            self.runtime.scene_controller.presentation_image = image

        def start_transition(self, request) -> None:
            self.request = request

        def has_running_transition(self) -> bool:
            return False

    manager = DisplayManager(runtime_generation=23)
    unit = _Unit()
    manager.displays = [unit]
    manager._startup_desktop_seed_screens = {0}
    destination = QPixmap(8, 5)
    try:
        # A presentation-only desktop seed is deliberately NOT image/history
        # authority, so engine admission still treats this as the first image.
        assert manager.has_presented_image() is False
        result = manager._present_quick_image(
            unit,
            destination,
            "first-wallpaper.jpg",
            implicit_expected_screens={0},
        )
        assert result == "transition_started"
        assert unit.request is not None
        assert unit.request.transition_id == "crossfade"
        assert unit.request.duration_ms == QUICK_STARTUP_DESKTOP_CROSSFADE_DURATION_MS
        assert unit.request.source_image.source_path == "__startup_desktop_screen_0__"
        assert unit.request.destination_image.source_path == "first-wallpaper.jpg"
        assert manager.current_images == {}

        manager._on_image_displayed(0, "first-wallpaper.jpg")
        assert manager.current_images == {0: "first-wallpaper.jpg"}
        assert manager._startup_desktop_seed_screens == set()
        assert manager.has_presented_image() is True
    finally:
        manager.displays = []
        manager.disconnect_monitor_detection()
        manager.deleteLater()
        qt_app.processEvents()
