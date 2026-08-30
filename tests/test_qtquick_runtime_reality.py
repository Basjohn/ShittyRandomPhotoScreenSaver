"""Focused post-cutover runtime-reality regressions.

Added after the first real source-mode Quick production run
(`logs/evidence_chest/08_30_RuntimeSwap_03_37/`, source 427eafed...) exposed
live product seams that the otherwise-green H destination profile did not
falsify.

The file intentionally proves end-to-end facts rather than restating ownership:
- successive Visualizer logical revisions reach the retained item;
- a valid image replacement during an active transition is admitted;
- real QWindow pointer dispatch leaves the retained QML menu visibly open;
- controller-owned logical state contains diagnostics its tick path reads.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtQuick import QQuickItem

from core.settings.visualizer_mode_registry import (
    VisualizerClipPolicy,
    VisualizerShellPolicy,
    get_visualizer_presentation_policy,
)
from engine.display_manager import DisplayManager
from rendering.quick.context_menu import build_quick_context_menu_entries
from rendering.quick.display_image_route import (
    presentation_image_from_processed_pixmap,
)
from rendering.quick.runtime import QuickDisplayRuntime
from rendering.quick.scene_controller import QuickSceneFactory
from rendering.quick.state import QuickWindowPolicy
from widgets.spotify_visualizer import tick_helpers
from widgets.spotify_visualizer.logical_tick_state import (
    install_default_logical_tick_state,
)
from widgets.spotify_visualizer.quick_display_visualizer_owner import (
    QuickDisplayVisualizerOwner,
)
from widgets.spotify_visualizer.render_state import (
    ResolvedVisualizerPresentation,
    SpectrumFrame,
    VisualizerCommonState,
    VisualizerLogicalFrame,
)
from widgets.spotify_visualizer.runtime_controller import (
    VisualizerRuntimeController,
)


def _logical_frame(
    *,
    runtime_generation: int,
    engine_generation: int,
    activation_id: int,
    logical_timestamp: float,
    bars: tuple[float, ...],
) -> VisualizerLogicalFrame:
    return VisualizerLogicalFrame(
        runtime_generation=runtime_generation,
        engine_generation=engine_generation,
        activation_id=activation_id,
        source_generation=-1,
        source_activation_id=-1,
        mode_id="spectrum",
        playing=False,
        logical_timestamp=logical_timestamp,
        source_timestamp=None,
        changed=True,
        present_frame=True,
        mode_reveal_ready=False,
        common=VisualizerCommonState(
            bars=bars,
            bar_count=len(bars),
        ),
        mode_state=SpectrumFrame(animation_time=logical_timestamp),
        protected_edges=(),
    )


def _visualizer_presentation() -> ResolvedVisualizerPresentation:
    policy = get_visualizer_presentation_policy("spectrum")
    assert policy.shell_policy is VisualizerShellPolicy.CARD
    assert policy.clip_policy is VisualizerClipPolicy.CARD_INTERIOR
    return ResolvedVisualizerPresentation(
        shell_policy=policy.shell_policy,
        clip_policy=policy.clip_policy,
        viewport_resize_capable=policy.viewport_resize_capable,
        outer_rect=(40.0, 60.0, 420.0, 280.0),
        content_rect=(44.0, 64.0, 412.0, 272.0),
        dpr=1.0,
        baseline_viewport_size=(420.0, 280.0),
        baseline_aspect_ratio=1.5,
        uniform_visual_scale=1.0,
        viewport_extent=(412.0, 272.0),
        current_aspect_ratio=412.0 / 272.0,
        scene_fade=1.0,
        content_fade=1.0,
        border_width=4.0,
        shell_style={},
    )


@pytest.mark.qt
def test_successive_visualizer_revisions_reach_retained_sync_item(
    qt_app,
    qtbot,
) -> None:
    """A healthy logical producer is useless if the retained item syncs once."""

    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(
        screen_index=0,
        runtime_generation=901,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(
            always_on_top=False,
            blank_cursor=False,
        ),
    )
    owner = QuickDisplayVisualizerOwner(
        runtime,
        bar_count=2,
        initial_mode="spectrum",
        engine_factory=lambda _count: object(),
        presentation_resolver=_visualizer_presentation,
    )
    try:
        owner.bind(engine_generation=3, activation_id=7)
        runtime.show_on_screen()
        qtbot.waitUntil(runtime.window.isVisible, timeout=3000)

        controller = owner.controller
        mailbox = controller.logical_mailbox

        mailbox.publish(
            _logical_frame(
                runtime_generation=901,
                engine_generation=3,
                activation_id=7,
                logical_timestamp=1.0,
                bars=(0.15, 0.55),
            ),
            generation=901,
            activation_id=7,
        )
        assert owner.sync_present() is True
        runtime.window.update()
        qtbot.waitUntil(
            lambda: runtime.scene_controller.visualizer_telemetry.snapshot().sync_count
            >= 1,
            timeout=3000,
        )
        first_sync_count = (
            runtime.scene_controller.visualizer_telemetry.snapshot().sync_count
        )

        # Same presentation geometry, different authored logical revision.
        # The retained item must still become dirty so updatePaintNode consumes
        # the new bridge snapshot. QQuickWindow.update() alone is not proof.
        mailbox.publish(
            _logical_frame(
                runtime_generation=901,
                engine_generation=3,
                activation_id=7,
                logical_timestamp=2.0,
                bars=(0.85, 0.25),
            ),
            generation=901,
            activation_id=7,
        )
        assert owner.sync_present() is True
        runtime.window.update()

        qtbot.waitUntil(
            lambda: runtime.scene_controller.visualizer_telemetry.snapshot().sync_count
            > first_sync_count,
            timeout=1500,
        )
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()


@pytest.mark.qt
def test_active_transition_replacement_cancels_to_destination_then_starts_new(
    qt_app,
) -> None:
    """A valid C request during A->B must replace the run, not be rejected."""

    class _Settings:
        def get(self, key: str, default=None):
            if key == "transitions":
                return {
                    "type": "Slide",
                    "random_always": False,
                    "durations": {"Slide": 275},
                    "slide": {"direction": "Random"},
                }
            if key == "display.hw_accel":
                return False
            return default

    class _Unit:
        def __init__(self, manager: DisplayManager) -> None:
            self.manager = manager
            self.screen_index = 0
            self._current = presentation_image_from_processed_pixmap(
                QPixmap(4, 3),
                image_path="a.jpg",
            )
            self.active_request = None
            self.history = []
            self.cancel_reasons = []

        def capture_image(self, pixmap, *, image_path: str = ""):
            return presentation_image_from_processed_pixmap(
                pixmap,
                image_path=image_path,
            )

        def current_image(self):
            return self._current

        def present_captured_image(self, image) -> None:
            self._current = image

        def start_transition(self, request) -> None:
            assert self.active_request is None
            self.active_request = request
            self.history.append(request)

        def has_running_transition(self) -> bool:
            return self.active_request is not None

        def cancel_transition(self, *, reason: str) -> bool:
            request = self.active_request
            if request is None:
                return False
            self.cancel_reasons.append(str(reason))
            self._current = request.destination_image
            self.active_request = None
            self.manager._on_quick_transition_finalized(
                self,
                SimpleNamespace(
                    destination_image_identity=self._current.identity,
                ),
            )
            return True

        def finalize_active(self) -> None:
            request = self.active_request
            assert request is not None
            self._current = request.destination_image
            self.active_request = None
            self.manager._on_quick_transition_finalized(
                self,
                SimpleNamespace(
                    destination_image_identity=self._current.identity,
                ),
            )

    manager = DisplayManager(
        settings_manager=_Settings(),
        runtime_generation=902,
    )
    unit = _Unit(manager)
    manager.displays = [unit]
    try:
        manager.present_processed_image(
            0,
            QPixmap(8, 6),
            QPixmap(),
            "b.jpg",
        )
        assert unit.active_request is not None
        first = unit.active_request
        assert first.source_image.source_path == "a.jpg"
        assert first.destination_image.source_path == "b.jpg"

        # 427eafed raised "screen 0 already has an active Quick transition".
        manager.present_processed_image(
            0,
            QPixmap(10, 7),
            QPixmap(),
            "c.jpg",
        )

        assert len(unit.cancel_reasons) == 1
        assert len(unit.history) == 2
        second = unit.active_request
        assert second is not None
        # QuickTransitionController.cancel_current() resolves the interrupted
        # run to B; B therefore becomes the authoritative source for B->C.
        assert second.source_image.source_path == "b.jpg"
        assert second.destination_image.source_path == "c.jpg"

        unit.finalize_active()
        assert manager.current_images == {0: "c.jpg"}
        assert manager.has_transition_work_pending() is False
    finally:
        manager.displays = []
        manager.disconnect_monitor_detection()
        manager.deleteLater()
        qt_app.processEvents()


def _menu_entries():
    return build_quick_context_menu_entries(
        transition_names=("Crossfade", "Wipe"),
        current_transition="Crossfade",
        random_enabled=False,
        random_selectable=False,
        visualizer_modes=(("spectrum", "Spectrum"), ("bubble", "Bubble")),
        current_visualizer="bubble",
        visualizer_available=True,
        dimming_enabled=False,
        interaction_mode_enabled=True,
        interaction_mode_locked=False,
        edit_mode_active=False,
        layout_actions_available=True,
    )


@pytest.mark.qt
def test_qwindow_right_click_leaves_retained_qml_context_menu_visibly_open(
    qt_app,
    qtbot,
) -> None:
    """Model admission alone is not proof that the operator can see the menu."""

    screen = qt_app.primaryScreen()
    assert screen is not None
    factory = QuickSceneFactory()
    runtime = QuickDisplayRuntime(
        screen_index=0,
        runtime_generation=903,
        screen=screen,
        scene_factory=factory,
        window_policy=QuickWindowPolicy(
            always_on_top=False,
            blank_cursor=False,
        ),
        interaction_mode_provider=lambda: True,
    )
    model = runtime.context_menu_model
    model.replace_entries(_menu_entries())
    model.set_action_handler(lambda _action_id, _payload: True)
    try:
        runtime.show_on_screen()
        qtbot.waitUntil(runtime.window.isVisible, timeout=3000)

        root = runtime.scene_controller.scene_root
        menu = root.findChild(QQuickItem, "retainedContextMenu")
        surface = root.findChild(QQuickItem, "retainedContextMenuSurface")
        assert menu is not None
        assert surface is not None

        # Drive the right-click through the QQuickWindow delivery agent
        # (QCoreApplication.sendEvent) rather than QTest.mouseClick's OS input
        # queue: this is the SAME real delivery path that flips menuVisible and
        # then re-delivers the opening press to the retained dismiss scrim - the
        # path that reproduced the self-dismiss - and it is deterministic and
        # hang-free, whereas the OS-queue synthetic click is unreliable headless.
        local = QPointF(120.0, 120.0)
        global_pos = QPointF(runtime.window.mapToGlobal(local.toPoint()))
        press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            local,
            global_pos,
            Qt.MouseButton.RightButton,
            Qt.MouseButton.RightButton,
            Qt.KeyboardModifier.NoModifier,
        )
        release = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            local,
            global_pos,
            Qt.MouseButton.RightButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        QCoreApplication.sendEvent(runtime.window, press)
        QCoreApplication.sendEvent(runtime.window, release)
        qtbot.waitUntil(lambda: model.menuVisible, timeout=1000)

        # Give the retained QML delivery/dismiss-scrim arming a full stable turn;
        # the opening event must NOT have self-dismissed the menu.
        qtbot.wait(60)

        assert model.menuVisible is True
        assert menu.isVisible() is True
        assert surface.isVisible() is True
        assert model.anchorX == pytest.approx(120.0)
        assert model.anchorY == pytest.approx(120.0)
    finally:
        runtime.close_runtime()
        factory.deleteLater()
        qt_app.processEvents()


def test_controller_owned_logical_state_installs_tick_spike_diagnostics(
    monkeypatch,
) -> None:
    """Every field read by the neutral tick diagnostic must exist before tick 1."""

    controller = VisualizerRuntimeController(
        runtime_generation=904,
        bar_count=2,
        initial_mode="spectrum",
        engine_factory=lambda _count: object(),
    )
    state = controller.logical_tick_state
    install_default_logical_tick_state(state, bar_count=2)

    # The 427eafed runtime run raised AttributeError for the first of these.
    assert state._last_tick_spike_log_ts == 0.0
    assert float(state._dt_spike_log_cooldown) > 0.0

    warnings = []
    monkeypatch.setattr(tick_helpers.time, "time", lambda: 100.0)
    monkeypatch.setattr(
        tick_helpers.logger,
        "warning",
        lambda *args, **kwargs: warnings.append((args, kwargs)),
    )

    state._log_tick_spike(
        0.050,
        {
            "running": False,
            "name": None,
            "elapsed": None,
            "idle_age": None,
        },
    )

    assert state._last_tick_spike_log_ts == 100.0
    assert len(warnings) == 1
