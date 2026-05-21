from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, QEvent
from PySide6.QtGui import QColor, QGuiApplication, QPixmap, QKeyEvent
from PySide6.QtWidgets import QWidget

from core.settings.models._enums import WidgetPosition, coerce_widget_position
from rendering.custom_layout_manager import CustomLayoutManager
from rendering.custom_layout_contract import get_screen_signature
from widgets.edit_shell_widget import EditShellWidget


class _SettingsStub:
    def __init__(self) -> None:
        self._widgets_map: dict = {}
        self.saved = False

    def get_widgets_map(self) -> dict:
        return dict(self._widgets_map)

    def set_widgets_map(self, widgets: dict) -> None:
        self._widgets_map = dict(widgets)

    def save(self) -> None:
        self.saved = True


class _EditableTestWidget(QWidget):
    def __init__(self, parent: QWidget, *, font_size: int = 48) -> None:
        super().__init__(parent)
        self._font_size = font_size
        self._icon_size = 32
        self._detail_icon_size = 16
        self._artwork_size = 80
        self.setGeometry(30, 40, 180, 80)
        self.show()

    def grab(self) -> QPixmap:  # type: ignore[override]
        pm = QPixmap(max(1, self.width()), max(1, self.height()))
        pm.fill(QColor(20, 20, 20, 180))
        return pm

    def set_font_size(self, size: int) -> None:
        self._font_size = int(size)

    def set_icon_size(self, size: int) -> None:
        self._icon_size = int(size)

    def set_detail_icon_size(self, size: int) -> None:
        self._detail_icon_size = int(size)

    def set_artwork_size(self, size: int) -> None:
        self._artwork_size = int(size)

    def _update_position(self) -> None:
        custom_rect = getattr(self, "_custom_layout_local_rect", None)
        if isinstance(custom_rect, QRect):
            self.setGeometry(custom_rect)


class _FakeScreen:
    def __init__(self, name: str, geometry: QRect) -> None:
        self._name = name
        self._geometry = QRect(geometry)

    def name(self) -> str:
        return self._name

    def geometry(self) -> QRect:
        return QRect(self._geometry)


class _DisplayStub(QWidget):
    def __init__(self, settings_stub: _SettingsStub, *, screen=None, screen_index: int = 0) -> None:
        super().__init__()
        self.settings_manager = settings_stub
        self.screen_index = screen_index
        self._screen = screen or QGuiApplication.primaryScreen()
        self._custom_layout_edit_active = False
        self._context_menu_calls: list = []
        self._setup_widgets_calls = 0
        self._apply_saved_layouts_calls = 0
        self._runtime_reload_requests = 0
        self._custom_layout_manager_proxy = None
        self._custom_layout_manager = None
        self._dimming_enabled = False
        self._dimming_opacity = 0.0
        self._gl_compositor = None
        self.clock_widget: _EditableTestWidget | None = None
        self.clock2_widget = None
        self.clock3_widget = None
        self.weather_widget = None
        self.media_widget = None
        self.reddit_widget = None
        self.reddit2_widget = None
        self.gmail_widget = None
        self.imgur_widget = None
        self.spotify_visualizer_widget = None
        self.spotify_volume_widget = None
        self.mute_button_widget = None
        self.setGeometry(0, 0, 800, 600)

    def _show_context_menu(self, global_pos) -> None:
        self._context_menu_calls.append(global_pos)

    def set_processed_image(self, processed_pixmap, original_pixmap, image_path: str = "") -> None:
        self._last_processed = (processed_pixmap, original_pixmap, image_path)

    def _setup_widgets(self) -> None:
        self._setup_widgets_calls += 1
        proxy = getattr(self, "_custom_layout_manager_proxy", None)
        if proxy is not None:
            self._apply_saved_custom_layouts()

    def _apply_saved_custom_layouts(self) -> None:
        self._apply_saved_layouts_calls += 1
        proxy = getattr(self, "_custom_layout_manager_proxy", None)
        if proxy is not None:
            proxy.apply_saved_layouts_to_display()

    def _request_custom_layout_runtime_reload(self) -> None:
        self._runtime_reload_requests += 1


class _RedditLikeTestWidget(_EditableTestWidget):
    def __init__(self, parent: QWidget, *, font_size: int = 18) -> None:
        super().__init__(parent, font_size=font_size)
        self.setGeometry(40, 60, 320, 180)

    def set_font_size(self, size: int) -> None:
        self._font_size = int(size)


class _GmailLikeTestWidget(_EditableTestWidget):
    def __init__(self, parent: QWidget, *, font_size: int = 13) -> None:
        super().__init__(parent, font_size=font_size)
        self.setGeometry(50, 70, 600, 220)

    def set_font_size(self, size: int) -> None:
        self._font_size = int(size)


class _ImgurLikeTestWidget(_EditableTestWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent, font_size=14)
        self._header_font_size = 14
        self._image_spacing = 4
        self._cell_base_width = 120
        self._image_border_width = 2
        self.setGeometry(60, 80, 520, 260)

    def set_header_font_size(self, size: int) -> None:
        self._header_font_size = int(size)

    def set_image_spacing(self, spacing: int) -> None:
        self._image_spacing = int(spacing)

    def set_cell_base_width(self, width: int) -> None:
        self._cell_base_width = int(width)

    def set_image_border_width(self, width: int) -> None:
        self._image_border_width = int(width)


class _VisualizerLikeTestWidget(_EditableTestWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent, font_size=14)
        self._base_height = 80
        self._vis_mode_str = "spectrum"
        self._started = True
        self.setGeometry(70, 360, 320, 160)

    def stop(self) -> None:
        self._started = False

    def start(self) -> None:
        self._started = True


class _FakeCompositor:
    def __init__(self) -> None:
        self.calls: list[tuple[bool, float]] = []

    def set_dimming(self, enabled: bool, opacity: float = 0.3) -> None:
        self.calls.append((bool(enabled), float(opacity)))


def _reset_custom_layout_manager_state() -> None:
    CustomLayoutManager._active_managers = []


def _attach_manager(display: _DisplayStub, manager: CustomLayoutManager) -> None:
    display._custom_layout_manager_proxy = manager
    display._custom_layout_manager = manager


def test_custom_layout_manager_saves_and_reapplies_clock_geometry(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"clock": {"position": "Top Right"}}
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()

    clock = _EditableTestWidget(display, font_size=48)
    display.clock_widget = clock
    qtbot.addWidget(clock)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True
    assert display._custom_layout_edit_active is True

    state = manager._shell_states["clock"]
    updated_rect = QRect(state.current_global_rect.x() + 48, state.current_global_rect.y() + 36, 240, 120)
    state.current_global_rect = QRect(updated_rect)
    state.current_size_payload = {"font_size": 72}
    state.resize_scale = 1.5
    state.shell.set_shell_geometry(updated_rect)

    assert manager.save_session() is True
    assert settings_stub.saved is True
    assert display._custom_layout_edit_active is False

    custom_layout = settings_stub.get_widgets_map()["custom_layout"]
    displays = custom_layout["displays"]
    assert len(displays) == 1
    payload = next(iter(displays.values()))["clock"]
    assert payload["size_payload"]["font_size"] == 72
    assert payload["resize_mode"] == "clock_font"
    assert settings_stub.get_widgets_map()["clock"]["position"] == "Custom"

    assert display._runtime_reload_requests == 1
    assert clock.isVisible() is False


def test_custom_widget_position_normalizes_without_fallback():
    assert coerce_widget_position("Custom", WidgetPosition.TOP_RIGHT) == WidgetPosition.CUSTOM
    assert coerce_widget_position("custom", WidgetPosition.TOP_RIGHT) == WidgetPosition.CUSTOM


def test_edit_shell_reset_buttons_are_bottom_centered(qtbot):
    pm = QPixmap(300, 160)
    pm.fill(QColor("black"))
    shell = EditShellWidget(
        widget_id="clock",
        snapshot=pm,
        initial_global_rect=QRect(0, 0, 300, 160),
        resizable=True,
    )
    qtbot.addWidget(shell)
    shell.show()

    size_btn = shell._reset_size_btn
    pos_btn = shell._reset_position_btn
    for btn in (size_btn, pos_btn):
        assert btn.x() >= 6
        assert btn.y() >= 6
        assert btn.x() + btn.width() <= shell.width() - 6
        assert btn.y() + btn.height() <= shell.height() - 6

    left = size_btn.x()
    right = pos_btn.x() + pos_btn.width()
    assert abs(((left + right) / 2) - (shell.width() / 2)) <= 3


def test_edit_shell_reset_buttons_ignore_shell_drag_and_can_be_enabled(qtbot):
    pm = QPixmap(300, 160)
    pm.fill(QColor("black"))
    shell = EditShellWidget(
        widget_id="clock",
        snapshot=pm,
        initial_global_rect=QRect(0, 0, 300, 160),
        resizable=True,
    )
    qtbot.addWidget(shell)
    shell.show()

    assert shell._reset_size_btn.isEnabled() is False
    assert shell._reset_position_btn.isEnabled() is False
    shell.set_reset_size_enabled(True)
    shell.set_reset_position_enabled(True)
    assert shell._reset_size_btn.isEnabled() is True
    assert shell._reset_position_btn.isEnabled() is True


def test_edit_shell_reset_buttons_emit_requests(qtbot):
    size_emitted: list[str] = []
    position_emitted: list[str] = []
    pm = QPixmap(300, 160)
    pm.fill(QColor("black"))
    shell = EditShellWidget(
        widget_id="clock",
        snapshot=pm,
        initial_global_rect=QRect(0, 0, 300, 160),
        resizable=True,
    )
    shell.reset_size_requested.connect(size_emitted.append)
    shell.reset_position_requested.connect(position_emitted.append)
    qtbot.addWidget(shell)
    shell.show()
    shell.set_reset_size_enabled(True)
    shell.set_reset_position_enabled(True)

    qtbot.mouseClick(shell._reset_size_btn, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(shell._reset_position_btn, Qt.MouseButton.LeftButton)

    assert size_emitted == ["clock"]
    assert position_emitted == ["clock"]


def test_custom_layout_manager_escape_cancels_active_session(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()
    display.clock_widget = _EditableTestWidget(display)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True
    assert CustomLayoutManager._key_filter is not None

    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
    assert CustomLayoutManager._key_filter.eventFilter(display, event) is True
    assert manager.is_active() is False


def test_custom_layout_manager_enter_saves_active_session(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"clock": {"position": "Top Right"}}
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()
    display.clock_widget = _EditableTestWidget(display)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True
    assert CustomLayoutManager._key_filter is not None

    event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    assert CustomLayoutManager._key_filter.eventFilter(display, event) is True
    assert settings_stub.saved is True
    assert manager.is_active() is False


def test_custom_layout_manager_raises_dimming_to_minimum_during_edit_mode(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    display = _DisplayStub(settings_stub)
    display._gl_compositor = _FakeCompositor()
    display._dimming_enabled = False
    display._dimming_opacity = 0.0
    qtbot.addWidget(display)
    display.show()
    display.clock_widget = _EditableTestWidget(display)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True
    assert display._gl_compositor.calls[-1] == (True, 0.5)

    manager.cancel_session()
    assert display._gl_compositor.calls[-1] == (False, 0.0)


def test_custom_layout_manager_preserves_stronger_existing_dimming(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    display = _DisplayStub(settings_stub)
    display._gl_compositor = _FakeCompositor()
    display._dimming_enabled = True
    display._dimming_opacity = 0.7
    qtbot.addWidget(display)
    display.show()
    display.clock_widget = _EditableTestWidget(display)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True
    assert display._gl_compositor.calls[-1] == (True, 0.7)

    manager.cancel_session()
    assert display._gl_compositor.calls[-1] == (True, 0.7)


def test_custom_layout_manager_defers_and_flushes_processed_images(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()
    display.clock_widget = _EditableTestWidget(display)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    pm = QPixmap(40, 40)
    pm.fill(QColor("red"))
    manager.defer_processed_image(pm, pm, "example.png")
    assert not hasattr(display, "_last_processed")

    manager.cancel_session()
    assert display._last_processed[2] == "example.png"


def test_custom_layout_manager_saves_and_reapplies_spotify_volume_geometry(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"media": {"position": "Bottom Left", "monitor": "1"}}
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()

    volume = _EditableTestWidget(display, font_size=14)
    volume.setGeometry(260, 80, 32, 180)
    display.spotify_volume_widget = volume
    qtbot.addWidget(volume)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    state = manager._shell_states["spotify_volume"]
    updated_rect = QRect(state.current_global_rect.x() + 80, state.current_global_rect.y() + 24, 32, 180)
    state.current_global_rect = QRect(updated_rect)
    state.shell.set_shell_geometry(updated_rect)

    assert manager.save_session() is True
    widgets_map = settings_stub.get_widgets_map()
    assert widgets_map["media"]["position"] == "Custom"
    displays = widgets_map["custom_layout"]["displays"]
    payload = next(iter(displays.values()))["spotify_volume"]
    assert payload["resize_mode"] == "none"
    assert display._runtime_reload_requests == 1


def test_custom_layout_manager_volume_save_does_not_clobber_media_monitor_route(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"media": {"position": "Custom", "monitor": "2"}}
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()

    media = _EditableTestWidget(display, font_size=18)
    media.setGeometry(420, 80, 400, 180)
    display.media_widget = media
    qtbot.addWidget(media)

    volume = _EditableTestWidget(display, font_size=14)
    volume.setGeometry(260, 80, 32, 180)
    display.spotify_volume_widget = volume
    qtbot.addWidget(volume)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    media_state = manager._shell_states["media"]
    media_state.current_monitor_value = "2"
    volume_state = manager._shell_states["spotify_volume"]
    volume_state.current_monitor_value = "1"

    assert manager.save_session() is True
    widgets_map = settings_stub.get_widgets_map()
    assert widgets_map["media"]["monitor"] == "2"


def test_custom_layout_manager_creates_and_destroys_grid_overlay(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"clock": {"position": "Top Right"}}
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()
    display.clock_widget = _EditableTestWidget(display)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True
    assert manager._grid_overlay is not None
    assert manager._grid_overlay.isVisible() is True

    assert manager.cancel_session() is True
    assert manager._grid_overlay is None


def test_custom_layout_manager_applies_move_only_volume_rect_using_authored_size(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    screen = _FakeScreen("A", QRect(0, 0, 800, 600))
    settings_stub._widgets_map = {
        "media": {"position": "Custom", "monitor": "1"},
        "custom_layout": {
            "version": 1,
            "displays": {
                get_screen_signature(screen): {
                    "spotify_volume": {
                        "rect": {"x": 0.4, "y": 0.2, "width": 0.25, "height": 0.55},
                        "size_payload": {},
                        "resize_mode": "none",
                    }
                }
            },
        },
    }
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.show()

    volume = _EditableTestWidget(display, font_size=14)
    volume.setGeometry(260, 80, 32, 180)
    display.spotify_volume_widget = volume
    qtbot.addWidget(volume)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    manager.apply_saved_layouts_to_display()

    custom_rect = getattr(volume, "_custom_layout_local_rect", None)
    assert isinstance(custom_rect, QRect)
    assert custom_rect.width() == 32
    assert custom_rect.height() == 180


def test_custom_layout_manager_reset_position_restores_source_rect_without_resetting_size(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"clock": {"position": "Top Right"}}
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()
    display.clock_widget = _EditableTestWidget(display)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    state = manager._shell_states["clock"]
    state.current_global_rect = QRect(
        state.current_global_rect.x() + 120,
        state.current_global_rect.y() + 80,
        state.current_global_rect.width() + 40,
        state.current_global_rect.height() + 20,
    )
    state.resize_scale = 1.15
    state.current_size_payload = {"font_size": 55}

    manager._on_shell_reset_position_requested("clock")

    assert state.current_global_rect.topLeft() == state.baseline_global_rect.topLeft()
    assert state.current_global_rect.size() != state.baseline_global_rect.size()
    assert state.resize_scale == 1.15


def test_custom_layout_manager_reapply_skips_saved_rects_when_position_not_custom(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "clock": {"position": "Top Right"},
        "custom_layout": {
            "version": 1,
            "displays": {
                "screen:test": {
                    "clock": {
                        "rect": {"x": 0.2, "y": 0.2, "width": 0.3, "height": 0.2},
                        "size_payload": {"font_size": 64},
                        "resize_mode": "clock_font",
                    }
                }
            },
        },
    }
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()

    clock = _EditableTestWidget(display, font_size=48)
    display.clock_widget = clock
    qtbot.addWidget(clock)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    manager._screen_signature = "screen:test"
    manager.apply_saved_layouts_to_display()

    assert not hasattr(clock, "_custom_layout_local_rect")


def test_custom_layout_manager_apply_saved_layouts_does_not_force_widget_visible(qtbot):
    _reset_custom_layout_manager_state()
    screen = _FakeScreen("screen0", QRect(0, 0, 800, 600))
    signature = get_screen_signature(screen)
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "clock": {"position": "Custom"},
        "custom_layout": {
            "version": 1,
            "displays": {
                signature: {
                    "clock": {
                        "rect": {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.2},
                        "size_payload": {"font_size": 64},
                        "resize_mode": "clock_font",
                    }
                }
            },
        },
    }
    display = _DisplayStub(settings_stub, screen=screen, screen_index=0)
    qtbot.addWidget(display)
    display.show()

    clock = _EditableTestWidget(display, font_size=48)
    clock.hide()
    display.clock_widget = clock
    qtbot.addWidget(clock)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    manager.apply_saved_layouts_to_display()

    assert hasattr(clock, "_custom_layout_local_rect")
    assert clock.isVisible() is False


def test_custom_layout_manager_late_screen_binding_saves_under_live_signature(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"clock": {"position": "Top Right"}}
    live_screen = _FakeScreen("screen0", QRect(0, 0, 800, 600))
    display = _DisplayStub(settings_stub, screen=live_screen, screen_index=0)
    display._screen = None
    qtbot.addWidget(display)
    display.show()

    clock = _EditableTestWidget(display, font_size=48)
    display.clock_widget = clock
    qtbot.addWidget(clock)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)

    # Simulate the real DisplayWidget lifecycle where the manager is created
    # before the live screen reference becomes available.
    display._screen = live_screen

    assert manager.start_session() is True
    assert manager.save_session() is True

    widgets_map = settings_stub.get_widgets_map()
    custom_layout = widgets_map["custom_layout"]["displays"]
    assert get_screen_signature(live_screen) in custom_layout
    assert "screen:none" not in custom_layout
    assert "clock" in custom_layout[get_screen_signature(live_screen)]


def test_custom_layout_manager_reapplies_legacy_signature_after_late_screen_binding(qtbot):
    _reset_custom_layout_manager_state()
    legacy_signature = "serial:abc|manufacturer:LG|model:TV|name:LG TV|geom:2560_0_2560x1440"
    live_screen = _FakeScreen("LG TV", QRect(2560, 0, 2560, 1439))
    live_screen.serialNumber = lambda: "abc"  # type: ignore[attr-defined]
    live_screen.manufacturer = lambda: "LG"  # type: ignore[attr-defined]
    live_screen.model = lambda: "TV"  # type: ignore[attr-defined]
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "clock": {"position": "Custom"},
        "custom_layout": {
            "version": 1,
            "displays": {
                legacy_signature: {
                    "clock": {
                        "rect": {"x": 0.2, "y": 0.2, "width": 0.3, "height": 0.2},
                        "size_payload": {"font_size": 64},
                        "resize_mode": "clock_font",
                    }
                }
            },
        },
    }
    display = _DisplayStub(settings_stub, screen=live_screen, screen_index=0)
    display._screen = None
    qtbot.addWidget(display)
    display.show()

    clock = _EditableTestWidget(display, font_size=48)
    display.clock_widget = clock
    qtbot.addWidget(clock)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    display._screen = live_screen

    manager.apply_saved_layouts_to_display()

    custom_rect = getattr(clock, "_custom_layout_local_rect", None)
    assert isinstance(custom_rect, QRect)
    assert custom_rect.width() > 0
    assert custom_rect.height() > 0


def test_custom_layout_manager_live_drag_snaps_to_peer_guides(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()

    clock = _EditableTestWidget(display, font_size=48)
    weather = _EditableTestWidget(display, font_size=18)
    weather.setGeometry(320, 60, 180, 80)
    display.clock_widget = clock
    display.weather_widget = weather
    qtbot.addWidget(clock)
    qtbot.addWidget(weather)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    clock_state = manager._shell_states["clock"]
    weather_state = manager._shell_states["weather"]
    proposal = QRect(
        weather_state.current_global_rect.x() - clock_state.current_global_rect.width() - 6,
        weather_state.current_global_rect.y() + 7,
        clock_state.current_global_rect.width(),
        clock_state.current_global_rect.height(),
    )
    manager._on_shell_geometry_live_changed("clock", proposal)
    snapped = manager._shell_states["clock"].current_global_rect

    assert snapped != proposal
    assert manager._shell_states["clock"].shell.current_global_rect() == snapped


def test_custom_layout_manager_cross_display_transfer_updates_monitor_and_reloads(qtbot, monkeypatch):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"clock2": {"position": "Bottom Right", "monitor": "2"}}
    screen0 = _FakeScreen("screen0", QRect(0, 0, 800, 600))
    screen1 = _FakeScreen("screen1", QRect(800, 0, 800, 600))
    display0 = _DisplayStub(settings_stub, screen=screen0, screen_index=0)
    display1 = _DisplayStub(settings_stub, screen=screen1, screen_index=1)
    qtbot.addWidget(display0)
    qtbot.addWidget(display1)
    display0.show()
    display1.show()

    clock2 = _EditableTestWidget(display1, font_size=32)
    display1.clock2_widget = clock2
    qtbot.addWidget(clock2)

    manager0 = CustomLayoutManager(display0)
    manager1 = CustomLayoutManager(display1)
    _attach_manager(display0, manager0)
    _attach_manager(display1, manager1)
    monkeypatch.setattr(
        manager1,
        "_get_display_instance_for_screen",
        lambda screen: display0 if screen is screen0 else display1,
    )

    class _CoordinatorStub:
        def get_all_instances(self):
            return [display0, display1]

    monkeypatch.setattr("rendering.custom_layout_manager.get_coordinator", lambda: _CoordinatorStub())

    assert manager1.start_session() is True
    state = manager1._shell_states["clock2"]
    assert state.descriptor.get_effective_position_settings_key() == "clock"
    proposal = QRect(120, 80, state.current_global_rect.width(), state.current_global_rect.height())
    manager1._on_shell_drag_finished("clock2", proposal, proposal.center())

    assert state.current_screen is screen0
    assert state.current_screen_signature == get_screen_signature(screen0)

    assert manager1.save_session() is True
    widgets_map = settings_stub.get_widgets_map()
    assert widgets_map["clock2"]["monitor"] == "1"
    assert "clock" in widgets_map, widgets_map
    assert widgets_map["clock"]["position"] == "Custom"
    custom_layout = widgets_map["custom_layout"]["displays"]
    assert get_screen_signature(screen0) in custom_layout
    assert "clock2" in custom_layout[get_screen_signature(screen0)]
    assert get_screen_signature(screen1) not in custom_layout or "clock2" not in custom_layout[get_screen_signature(screen1)]
    assert display0._runtime_reload_requests == 0
    assert display1._runtime_reload_requests == 1


def test_custom_layout_manager_blocks_all_widget_cross_display_transfer(qtbot, monkeypatch):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"clock": {"position": "Top Right", "monitor": "ALL"}}
    screen0 = _FakeScreen("screen0", QRect(0, 0, 800, 600))
    screen1 = _FakeScreen("screen1", QRect(800, 0, 800, 600))
    display1 = _DisplayStub(settings_stub, screen=screen1, screen_index=1)
    qtbot.addWidget(display1)
    display1.show()

    clock = _EditableTestWidget(display1, font_size=48)
    display1.clock_widget = clock
    qtbot.addWidget(clock)

    manager = CustomLayoutManager(display1)
    _attach_manager(display1, manager)
    monkeypatch.setattr(manager, "_get_available_screens", lambda: [screen0, screen1])
    monkeypatch.setattr(manager, "_get_display_instance_for_screen", lambda screen: display1)

    assert manager.start_session() is True
    state = manager._shell_states["clock"]
    source_signature = state.current_screen_signature
    proposal = QRect(580, 90, state.current_global_rect.width(), state.current_global_rect.height())
    manager._on_shell_drag_finished("clock", proposal, QPoint(760, 120))

    assert state.current_screen_signature == source_signature
    assert state.shell._transfer_blocked is True
    assert state.shell._transfer_block_reason == "Locked to ALL displays"


def test_custom_layout_manager_starts_global_session_for_all_active_displays(qtbot, monkeypatch):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    screen0 = _FakeScreen("screen0", QRect(0, 0, 800, 600))
    screen1 = _FakeScreen("screen1", QRect(800, 0, 800, 600))
    display0 = _DisplayStub(settings_stub, screen=screen0, screen_index=0)
    display1 = _DisplayStub(settings_stub, screen=screen1, screen_index=1)
    qtbot.addWidget(display0)
    qtbot.addWidget(display1)
    display0.show()
    display1.show()

    display0.clock_widget = _EditableTestWidget(display0, font_size=48)
    display1.weather_widget = _EditableTestWidget(display1, font_size=18)

    manager0 = CustomLayoutManager(display0)
    manager1 = CustomLayoutManager(display1)
    _attach_manager(display0, manager0)
    _attach_manager(display1, manager1)

    class _CoordinatorStub:
        def get_all_instances(self):
            return [display0, display1]

    monkeypatch.setattr("rendering.custom_layout_manager.get_coordinator", lambda: _CoordinatorStub())

    assert manager1.start_session() is True
    assert display0._custom_layout_edit_active is True
    assert display1._custom_layout_edit_active is True
    assert CustomLayoutManager.is_any_session_active() is True
    assert set(CustomLayoutManager.active_managers()) == {manager0, manager1}
    assert "clock" in manager0._shell_states
    assert "weather" in manager1._shell_states


def test_custom_layout_manager_transfer_targets_only_active_displays(qtbot, monkeypatch):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"clock2": {"position": "Bottom Right", "monitor": "2"}}
    screen0 = _FakeScreen("screen0", QRect(0, 0, 800, 600))
    screen1 = _FakeScreen("screen1", QRect(800, 0, 800, 600))
    screen2 = _FakeScreen("screen2", QRect(1600, 0, 800, 600))
    display0 = _DisplayStub(settings_stub, screen=screen0, screen_index=0)
    display1 = _DisplayStub(settings_stub, screen=screen1, screen_index=1)
    qtbot.addWidget(display0)
    qtbot.addWidget(display1)
    display0.show()
    display1.show()

    clock2 = _EditableTestWidget(display1, font_size=32)
    display1.clock2_widget = clock2
    qtbot.addWidget(clock2)

    manager0 = CustomLayoutManager(display0)
    manager1 = CustomLayoutManager(display1)
    _attach_manager(display0, manager0)
    _attach_manager(display1, manager1)

    class _CoordinatorStub:
        def get_all_instances(self):
            return [display0, display1]

    monkeypatch.setattr("rendering.custom_layout_manager.get_coordinator", lambda: _CoordinatorStub())
    monkeypatch.setattr(QGuiApplication, "screens", staticmethod(lambda: [screen0, screen1, screen2]))

    assert manager1._get_available_screens() == [screen0, screen1]
    assert manager1.start_session() is True
    state = manager1._shell_states["clock2"]

    proposal = QRect(1700, 120, state.current_global_rect.width(), state.current_global_rect.height())
    manager1._on_shell_drag_finished("clock2", proposal, QPoint(1750, 140))

    assert state.current_screen is screen1


def test_custom_layout_manager_same_display_near_edge_does_not_transfer(qtbot, monkeypatch):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"clock2": {"position": "Bottom Right", "monitor": "2"}}
    screen0 = _FakeScreen("screen0", QRect(0, 0, 800, 600))
    screen1 = _FakeScreen("screen1", QRect(800, 0, 800, 600))
    display1 = _DisplayStub(settings_stub, screen=screen1, screen_index=1)
    qtbot.addWidget(display1)
    display1.show()

    clock2 = _EditableTestWidget(display1, font_size=32)
    display1.clock2_widget = clock2
    qtbot.addWidget(clock2)

    manager = CustomLayoutManager(display1)
    _attach_manager(display1, manager)
    monkeypatch.setattr(manager, "_get_available_screens", lambda: [screen0, screen1])
    monkeypatch.setattr(manager, "_get_display_instance_for_screen", lambda screen: display1)

    assert manager.start_session() is True
    state = manager._shell_states["clock2"]
    source_signature = state.current_screen_signature

    proposal = QRect(790, 100, state.current_global_rect.width(), state.current_global_rect.height())
    manager._on_shell_drag_finished("clock2", proposal, QPoint(795, 120))

    assert state.current_screen_signature == source_signature
    assert state.shell._transfer_blocked is False

    assert manager.save_session() is True
    assert display1._runtime_reload_requests == 1


def test_custom_layout_manager_saves_and_reapplies_reddit_font_resize(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"reddit": {"position": "Bottom Right"}}
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()

    reddit = _RedditLikeTestWidget(display, font_size=18)
    display.reddit_widget = reddit
    qtbot.addWidget(reddit)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    state = manager._shell_states["reddit"]
    state.current_size_payload = {"font_size": 24}
    state.resize_scale = 1.3
    state.current_global_rect = QRect(state.current_global_rect.x(), state.current_global_rect.y(), 360, 220)

    assert manager.save_session() is True
    payload = next(iter(settings_stub.get_widgets_map()["custom_layout"]["displays"].values()))["reddit"]
    assert payload["size_payload"]["font_size"] == 24
    assert payload["resize_mode"] == "reddit_font"


def test_custom_layout_manager_saves_and_reapplies_gmail_font_resize(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"gmail": {"position": "Top Left"}}
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()

    gmail = _GmailLikeTestWidget(display, font_size=13)
    display.gmail_widget = gmail
    qtbot.addWidget(gmail)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    state = manager._shell_states["gmail"]
    state.current_size_payload = {"font_size": 18}
    state.resize_scale = 1.4
    state.current_global_rect = QRect(state.current_global_rect.x(), state.current_global_rect.y(), 680, 260)

    assert manager.save_session() is True
    payload = next(iter(settings_stub.get_widgets_map()["custom_layout"]["displays"].values()))["gmail"]
    assert payload["size_payload"]["font_size"] == 18
    assert payload["resize_mode"] == "gmail_font"


def test_custom_layout_manager_saves_and_reapplies_imgur_scale_resize(qtbot, monkeypatch):
    monkeypatch.setenv("SRPSS_ENABLE_DEV", "true")
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"imgur": {"position": "Top Right"}}
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()

    imgur = _ImgurLikeTestWidget(display)
    display.imgur_widget = imgur
    qtbot.addWidget(imgur)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    state = manager._shell_states["imgur"]
    state.current_size_payload = {
        "header_font_size": 18,
        "image_spacing": 6,
        "cell_base_width": 150,
        "image_border_width": 3,
    }
    state.resize_scale = 1.25
    state.current_global_rect = QRect(state.current_global_rect.x(), state.current_global_rect.y(), 640, 320)

    assert manager.save_session() is True
    payload = next(iter(settings_stub.get_widgets_map()["custom_layout"]["displays"].values()))["imgur"]
    assert payload["size_payload"]["header_font_size"] == 18
    assert payload["size_payload"]["image_spacing"] == 6
    assert payload["size_payload"]["cell_base_width"] == 150
    assert payload["size_payload"]["image_border_width"] == 3
    assert payload["resize_mode"] == "imgur_scale"


def test_custom_layout_manager_visualizer_shell_snapshot_uses_display_composite(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"media": {"position": "Custom", "monitor": "ALL"}}
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()

    visualizer = _VisualizerLikeTestWidget(display)
    display.spotify_visualizer_widget = visualizer
    class _OverlayStub(QWidget):
        def grabFramebuffer(self):
            pm = QPixmap(max(1, self.width()), max(1, self.height()))
            pm.fill(QColor(40, 120, 240, 180))
            return pm.toImage()

    overlay = _OverlayStub(display)
    overlay.setGeometry(visualizer.geometry())
    overlay.show()
    display._spotify_bars_overlay = overlay
    qtbot.addWidget(visualizer)
    qtbot.addWidget(overlay)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    original_grab = display.grab
    display.grab = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("display.grab should not be used"))  # type: ignore[assignment]
    assert manager.start_session() is True
    display.grab = original_grab  # type: ignore[assignment]

    state = manager._shell_states["spotify_visualizer"]
    assert not state.shell._snapshot.isNull()
    assert overlay.isVisible() is False
    assert visualizer._started is False


def test_custom_layout_manager_saves_visualizer_rect_under_visualizer_custom_slot(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "media": {"position": "Bottom Left", "monitor": "2"},
        "spotify_visualizer": {"position": "Custom", "monitor": "1"},
    }
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()

    visualizer = _VisualizerLikeTestWidget(display)
    display.spotify_visualizer_widget = visualizer
    qtbot.addWidget(visualizer)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    state = manager._shell_states["spotify_visualizer"]
    updated_rect = QRect(
        state.current_global_rect.x() + 22,
        state.current_global_rect.y() + 18,
        420,
        210,
    )
    state.current_global_rect = QRect(updated_rect)
    state.resize_scale = 1.25
    state.shell.set_shell_geometry(updated_rect)

    assert manager.save_session() is True
    widgets_map = settings_stub.get_widgets_map()
    assert widgets_map["media"]["position"] == "Bottom Left"
    assert widgets_map["spotify_visualizer"]["position"] == "Custom"
    payload = next(iter(widgets_map["custom_layout"]["displays"].values()))["spotify_visualizer"]
    assert payload["resize_mode"] == "visualizer_rect"


def test_custom_layout_manager_promotes_visualizer_from_follow_media_to_visualizer_custom_slot(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "media": {"position": "Bottom Left", "monitor": "2"},
        "spotify_visualizer": {"enabled": True, "monitor": "1"},
    }
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()

    visualizer = _VisualizerLikeTestWidget(display)
    display.spotify_visualizer_widget = visualizer
    qtbot.addWidget(visualizer)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    state = manager._shell_states["spotify_visualizer"]
    state.current_monitor_value = "1"
    state.current_global_rect = QRect(
        state.current_global_rect.x() + 18,
        state.current_global_rect.y() + 14,
        state.current_global_rect.width(),
        state.current_global_rect.height(),
    )

    assert manager.save_session() is True
    widgets_map = settings_stub.get_widgets_map()
    assert widgets_map["media"]["position"] == "Bottom Left"
    assert widgets_map["media"]["monitor"] == "2"
    assert widgets_map["spotify_visualizer"]["position"] == "Custom"
    assert widgets_map["spotify_visualizer"]["monitor"] == "1"


def test_custom_layout_manager_reset_to_authored_layout_clears_custom_geometry_and_restores_route(qtbot, monkeypatch):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "clock": {"position": "Custom"},
        "clock2": {"monitor": "2"},
        "custom_layout": {
            "version": 1,
            "displays": {
                "screen:test": {
                    "clock": {
                        "rect": {"x": 0.2, "y": 0.2, "width": 0.3, "height": 0.2},
                        "size_payload": {"font_size": 64},
                        "resize_mode": "clock_font",
                    }
                }
            },
        },
        "custom_layout_restore": {
            "version": 1,
            "widgets": {
                "clock": {"position": "Top Right", "monitor": "ALL"},
            },
        },
    }
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()

    clock = _EditableTestWidget(display, font_size=48)
    display.clock_widget = clock
    qtbot.addWidget(clock)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)

    class _CoordinatorStub:
        def get_all_instances(self):
            return [display]

    monkeypatch.setattr("rendering.custom_layout_manager.get_coordinator", lambda: _CoordinatorStub())

    assert manager.start_session() is True
    assert manager.reset_to_authored_layout() is True

    widgets_map = settings_stub.get_widgets_map()
    assert widgets_map["clock"]["position"] == "Top Right"
    assert widgets_map["clock2"]["monitor"] == "2"
    displays = widgets_map["custom_layout"]["displays"]
    assert not any("clock" in layout for layout in displays.values())
    assert display._runtime_reload_requests == 1


def test_custom_layout_manager_live_drag_uses_softer_snap_threshold(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()

    clock = _EditableTestWidget(display, font_size=48)
    weather = _EditableTestWidget(display, font_size=18)
    weather.setGeometry(320, 60, 180, 80)
    display.clock_widget = clock
    display.weather_widget = weather
    qtbot.addWidget(clock)
    qtbot.addWidget(weather)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    clock_state = manager._shell_states["clock"]
    weather_state = manager._shell_states["weather"]
    proposal = QRect(
        weather_state.current_global_rect.x() - clock_state.current_global_rect.width() - 30,
        weather_state.current_global_rect.y() + 30,
        clock_state.current_global_rect.width(),
        clock_state.current_global_rect.height(),
    )
    manager._on_shell_geometry_live_changed("clock", proposal)
    not_snapped = manager._shell_states["clock"].current_global_rect

    assert not_snapped == QRect(120, 120, 180, 80)
    assert clock.isVisible() is False
