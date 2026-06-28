from __future__ import annotations

import pytest

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QEvent
from PySide6.QtGui import QColor, QGuiApplication, QPixmap, QKeyEvent
from PySide6.QtWidgets import QApplication, QWidget

from core.settings.models._enums import WidgetPosition, coerce_widget_position
from rendering.custom_layout_manager import CustomLayoutManager
from rendering.custom_layout_contract import get_screen_signature, resolve_snap_local_rect_for_edit
from widgets.base_overlay_widget import BaseOverlayWidget, OverlayPosition
from widgets.edit_shell_widget import EditShellWidget
from widgets.spotify_visualizer_widget import SpotifyVisualizerWidget


class _SettingsStub:
    def __init__(self) -> None:
        self._widgets_map: dict = {}
        self.saved = False

    def get_widgets_map(self) -> dict:
        return dict(self._widgets_map)

    def set_widgets_map(self, widgets: dict, *, emit_change: bool = True) -> None:
        self._widgets_map = dict(widgets)

    def save(self) -> None:
        self.saved = True


class _EditableTestWidget(QWidget):
    def __init__(self, parent: QWidget, *, font_size: int = 48) -> None:
        super().__init__(parent)
        self._font_size = font_size
        self._display_mode = "digital"
        self._icon_size = 32
        self._detail_icon_size = 16
        self._artwork_size = 80
        self.double_click_calls = 0
        self.setGeometry(30, 40, 180, 80)
        self.show()

    def grab(self) -> QPixmap:  # type: ignore[override]
        pm = QPixmap(max(1, self.width()), max(1, self.height()))
        pm.fill(QColor(20, 20, 20, 180))
        return pm

    def set_font_size(self, size: int) -> None:
        self._font_size = int(size)

    def set_display_mode(self, mode: str) -> None:
        self._display_mode = str(mode)

    def set_icon_size(self, size: int) -> None:
        self._icon_size = int(size)

    def set_detail_icon_size(self, size: int) -> None:
        self._detail_icon_size = int(size)

    def set_artwork_size(self, size: int) -> None:
        self._artwork_size = int(size)

    def handle_double_click(self, local_pos) -> bool:
        self.double_click_calls += 1
        self._display_mode = "analog" if self._display_mode == "digital" else "digital"
        return True

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
        self._ctrl_cursor_hint = None
        self._input_handler = None
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

    def set_display_mode(self, mode: str) -> None:
        self._display_mode = str(mode)


class _ConstrainedOverlayWidget(BaseOverlayWidget):
    def __init__(self, parent: QWidget, *, overlay_name: str = "constraint", font_size: int = 18) -> None:
        super().__init__(parent, position=OverlayPosition.TOP_LEFT, overlay_name=overlay_name)
        self._font_size = font_size
        self._show_background = True
        self._apply_base_styling()
        self.setGeometry(40, 60, 600, 320)
        self.setMinimumWidth(600)
        self.setMinimumHeight(320)
        self.show()

    def set_font_size(self, size: int) -> None:
        self._font_size = int(size)
        self._update_font()
        self.setMinimumWidth(600)
        self.setMinimumHeight(320)


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
        self._blob_width = 1.0
        self._spectrum_growth = 2.0
        self._blob_growth = 3.5
        self._osc_growth = 2.0
        self._bubble_growth = 3.0
        self._devcurve_growth = 3.0
        self._sine_wave_growth = 2.0
        self._started = True
        self.setGeometry(70, 360, 320, 160)

    def stop(self) -> None:
        self._started = False

    def start(self) -> None:
        self._started = True


class _TrackingVisualizerTestWidget(_VisualizerLikeTestWidget):
    def __init__(self, parent: QWidget) -> None:
        self.geometry_history: list[QRect] = []
        super().__init__(parent)

    def setGeometry(self, *args) -> None:  # type: ignore[override]
        super().setGeometry(*args)
        self.geometry_history.append(QRect(self.geometry()))


class _OverlayGeometryStub:
    def __init__(self, rect: QRect) -> None:
        self._geometry = QRect(rect)
        self.history: list[QRect] = [QRect(rect)]
        self.updated = 0

    def geometry(self) -> QRect:
        return QRect(self._geometry)

    def setGeometry(self, rect: QRect) -> None:
        self._geometry = QRect(rect)
        self.history.append(QRect(rect))

    def update(self) -> None:
        self.updated += 1


class _VolumeLikeTestWidget(_EditableTestWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent, font_size=14)
        self._track_width = 18
        self._track_margin = 6
        self.setGeometry(260, 80, 32, 180)

    def apply_scale_contract(
        self,
        *,
        width: int,
        height: int,
        track_width: int,
        track_margin: int,
    ) -> None:
        self._track_width = int(track_width)
        self._track_margin = int(track_margin)
        self.setMinimumWidth(int(width))
        self.setMinimumHeight(int(height))


class _FakeCompositor:
    def __init__(self) -> None:
        self.calls: list[tuple[bool, float]] = []

    def set_dimming(self, enabled: bool, opacity: float = 0.3) -> None:
        self.calls.append((bool(enabled), float(opacity)))


class _HaloStub:
    def __init__(self) -> None:
        self.cancelled = False
        self.hidden = False
        self.opacity = None

    def cancel_animation(self) -> None:
        self.cancelled = True

    def hide(self) -> None:
        self.hidden = True

    def setOpacity(self, value: float) -> None:
        self.opacity = float(value)


class _InputHandlerStub:
    def __init__(self) -> None:
        self.ctrl_states: list[bool] = []

    def set_ctrl_held(self, held: bool) -> None:
        self.ctrl_states.append(bool(held))


def _reset_custom_layout_manager_state() -> None:
    try:
        CustomLayoutManager._uninstall_global_key_filter()
    except Exception:
        pass
    CustomLayoutManager._active_managers = []
    CustomLayoutManager._menu_interaction_depth = 0
    CustomLayoutManager._restack_scheduled = False
    CustomLayoutManager._restack_pending_during_menu = False


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
    assert payload["size_payload"]["display_mode"] == "digital"
    assert payload["resize_mode"] == "clock_font"
    assert settings_stub.get_widgets_map()["clock"]["position"] == "Custom"

    assert display._runtime_reload_requests == 1
    assert clock.isVisible() is False


def test_custom_layout_manager_clock_payload_reapplies_display_mode(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"clock": {"position": "Top Right"}}
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()

    clock = _EditableTestWidget(display, font_size=48)
    clock._display_mode = "analog"
    display.clock_widget = clock
    qtbot.addWidget(clock)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    state = manager._shell_states["clock"]
    manager._apply_size_payload(
        state.descriptor,
        clock,
        {"font_size": 54, "display_mode": "digital"},
    )

    assert clock._font_size == 54
    assert clock._display_mode == "digital"


def test_custom_layout_manager_save_session_persists_untouched_widgets_as_authoritative_custom_scene(qtbot):
    _reset_custom_layout_manager_state()
    screen = _FakeScreen("Display-A", QRect(0, 0, 800, 600))
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "clock": {"position": "Top Right"},
        "gmail": {"position": "Top Left"},
    }
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.show()

    clock = _EditableTestWidget(display, font_size=48)
    gmail = _GmailLikeTestWidget(display, font_size=13)
    display.clock_widget = clock
    display.gmail_widget = gmail
    qtbot.addWidget(clock)
    qtbot.addWidget(gmail)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    clock_state = manager._shell_states["clock"]
    updated_rect = QRect(clock_state.current_global_rect.x() + 36, clock_state.current_global_rect.y() + 24, 260, 140)
    clock_state.current_global_rect = QRect(updated_rect)
    clock_state.current_size_payload = {"font_size": 60}
    clock_state.resize_scale = 1.25
    clock_state.shell.set_shell_geometry(updated_rect)

    gmail_state = manager._shell_states["gmail"]
    untouched_rect = QRect(gmail_state.current_global_rect)

    assert manager.save_session() is True

    widgets_map = settings_stub.get_widgets_map()
    displays = widgets_map["custom_layout"]["displays"]
    payloads = next(iter(displays.values()))
    assert set(payloads.keys()) >= {"clock", "gmail"}
    assert widgets_map["clock"]["position"] == "Custom"
    assert widgets_map["gmail"]["position"] == "Custom"
    assert payloads["clock"]["size_payload"]["font_size"] == 60
    assert payloads["gmail"]["size_payload"]["font_size"] == 13
    assert payloads["gmail"]["resize_mode"] == "gmail_font"
    assert payloads["gmail"]["rect"]["x"] == pytest.approx(untouched_rect.x() / screen.geometry().width())
    assert payloads["gmail"]["rect"]["y"] == pytest.approx(untouched_rect.y() / screen.geometry().height())
    assert payloads["gmail"]["rect"]["width"] == pytest.approx(untouched_rect.width() / screen.geometry().width())
    assert payloads["gmail"]["rect"]["height"] == pytest.approx(untouched_rect.height() / screen.geometry().height())


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


def test_edit_shell_cursor_policy_uses_hand_and_all_corner_resize_shapes(qtbot):
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

    assert shell._resolve_cursor_shape(QPoint(120, 70)) == Qt.CursorShape.OpenHandCursor
    assert shell._resolve_cursor_shape(QPoint(4, 4)) == Qt.CursorShape.SizeFDiagCursor
    assert shell._resolve_cursor_shape(QPoint(shell.width() - 4, 4)) == Qt.CursorShape.SizeBDiagCursor
    assert shell._resolve_cursor_shape(QPoint(4, shell.height() - 4)) == Qt.CursorShape.SizeBDiagCursor
    assert shell._resolve_cursor_shape(QPoint(shell.width() - 4, shell.height() - 4)) == Qt.CursorShape.SizeFDiagCursor
    shell._resizing = True
    shell._resize_corner = shell._RESIZE_CORNER_TOP_LEFT
    assert shell._resolve_cursor_shape(QPoint(120, 70)) == Qt.CursorShape.SizeFDiagCursor


def test_custom_layout_session_suspends_halo_and_restores_blank_cursor(qtbot, monkeypatch):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"clock": {"position": "Top Right"}}
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()
    display.setCursor(Qt.CursorShape.BlankCursor)
    display._ctrl_held = True
    display._ctrl_cursor_hint = _HaloStub()
    display._input_handler = _InputHandlerStub()
    display.clock_widget = _EditableTestWidget(display)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)

    class _CoordinatorStub:
        def __init__(self) -> None:
            self.ctrl_states: list[bool] = []
            self.cleared = False

        def get_all_instances(self):
            return [display]

        def set_ctrl_held(self, held: bool) -> None:
            self.ctrl_states.append(bool(held))

        def clear_halo_owner(self):
            self.cleared = True
            return None

    coordinator = _CoordinatorStub()
    monkeypatch.setattr("rendering.custom_layout_manager.get_coordinator", lambda: coordinator)

    assert manager.start_session() is True
    assert display.cursor().shape() == Qt.CursorShape.ArrowCursor
    assert display._ctrl_held is False
    assert display._input_handler.ctrl_states[-1] is False
    assert coordinator.ctrl_states[-1] is False
    assert coordinator.cleared is True
    assert display._ctrl_cursor_hint.cancelled is True
    assert display._ctrl_cursor_hint.hidden is True
    assert display._ctrl_cursor_hint.opacity == 0.0

    assert manager.cancel_session() is True
    assert display.cursor().shape() == Qt.CursorShape.BlankCursor


def test_custom_layout_corner_drag_resize_scales_from_top_center_anchor(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"clock": {"position": "Top Right"}}
    screen = _FakeScreen("Display-A", QRect(0, 0, 520, 420))
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.show()

    clock = _EditableTestWidget(display, font_size=48)
    display.clock_widget = clock
    qtbot.addWidget(clock)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    state = manager._shell_states["clock"]
    origin_rect = QRect(state.current_global_rect)
    origin_top = origin_rect.y()
    manager._on_shell_resize_drag_started(
        "clock",
        "bottom_right",
        origin_rect,
        origin_rect.bottomRight(),
    )
    manager._on_shell_resize_drag_live_changed(
        "clock",
        "bottom_right",
        QRect(origin_rect),
        QPoint(origin_rect.right() + 60, origin_rect.bottom() + 40),
    )

    assert state.resize_scale > 1.0
    assert state.current_size_payload["font_size"] > state.baseline_size_payload["font_size"]
    assert state.current_global_rect.y() == origin_top
    assert state.current_global_rect.width() > origin_rect.width()
    assert state.current_global_rect.height() > origin_rect.height()
    assert state.current_global_rect.x() >= screen.geometry().x()
    assert state.current_global_rect.right() <= screen.geometry().right()

    manager._on_shell_resize_drag_finished(
        "clock",
        "bottom_right",
        QRect(state.current_global_rect),
        QPoint(state.current_global_rect.right(), state.current_global_rect.bottom()),
    )
    assert state.resize_corner is None
    assert state.resize_origin_rect is None


def test_custom_layout_resize_wheel_uses_absolute_half_scale_minimum_and_display_bounded_maximum(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    screen = _FakeScreen("Display-A", QRect(0, 0, 240, 220))
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.show()

    clock = _EditableTestWidget(display, font_size=48)
    display.clock_widget = clock
    qtbot.addWidget(clock)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    state = manager._shell_states["clock"]
    origin_rect = QRect(state.current_global_rect)
    origin_top = origin_rect.y()
    origin_center_x = origin_rect.center().x()

    manager._on_shell_resize_wheel_requested("clock", -12000)

    assert state.resize_scale == pytest.approx(0.5)
    assert state.current_global_rect.y() == origin_top
    assert abs(state.current_global_rect.center().x() - origin_center_x) <= 1
    assert state.current_global_rect.width() == int(round(origin_rect.width() * 0.5))
    assert state.current_global_rect.height() == int(round(origin_rect.height() * 0.5))

    manager._on_shell_resize_wheel_requested("clock", 120000)

    assert state.resize_scale > 1.0
    assert state.current_global_rect.y() == origin_top
    assert state.current_global_rect.x() >= screen.geometry().x()
    assert state.current_global_rect.x() + state.current_global_rect.width() <= screen.geometry().x() + screen.geometry().width()
    assert (
        state.current_global_rect.x() == screen.geometry().x()
        or state.current_global_rect.x() + state.current_global_rect.width() == screen.geometry().x() + screen.geometry().width()
    )
    assert state.current_global_rect.height() > origin_rect.height()


def test_custom_layout_resize_wheel_can_grow_by_pushing_back_inside_screen(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    screen = _FakeScreen("Display-A", QRect(0, 0, 400, 320))
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.show()

    clock = _EditableTestWidget(display, font_size=48)
    display.clock_widget = clock
    qtbot.addWidget(clock)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    state = manager._shell_states["clock"]
    constrained_rect = QRect(0, 20, 180, 200)
    state.baseline_global_rect = QRect(constrained_rect)
    state.current_global_rect = QRect(constrained_rect)
    manager._set_shell_geometry_silently(state, constrained_rect)

    manager._on_shell_resize_wheel_requested("clock", 12000)

    assert state.resize_scale > 1.0
    assert state.current_global_rect.width() > constrained_rect.width()
    assert state.current_global_rect.height() > constrained_rect.height()
    assert state.current_global_rect.x() >= screen.geometry().x()
    assert state.current_global_rect.right() <= screen.geometry().right()


def test_custom_layout_corner_drag_does_not_jump_when_press_starts_inside_resize_gutter(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    screen = _FakeScreen("Display-A", QRect(0, 0, 800, 600))
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.show()

    clock = _EditableTestWidget(display, font_size=48)
    display.clock_widget = clock
    qtbot.addWidget(clock)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    state = manager._shell_states["clock"]
    origin_rect = QRect(state.current_global_rect)
    press_cursor = QPoint(origin_rect.right() - 18, origin_rect.bottom() - 18)

    manager._on_shell_resize_drag_started(
        "clock",
        "bottom_right",
        origin_rect,
        press_cursor,
    )
    manager._on_shell_resize_drag_live_changed(
        "clock",
        "bottom_right",
        QRect(origin_rect),
        QPoint(press_cursor),
    )

    assert state.resize_scale == pytest.approx(1.0)
    assert state.current_global_rect == origin_rect


def test_custom_layout_resize_preview_refresh_does_not_mutate_live_widget_geometry_or_state(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"clock": {"position": "Top Right"}}
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()

    class _PreviewMutationProbe(_EditableTestWidget):
        def __init__(self, parent: QWidget) -> None:
            self.geometry_mutations = 0
            self.font_size_mutations = 0
            super().__init__(parent, font_size=48)

        def setGeometry(self, *args):  # type: ignore[override]
            self.geometry_mutations += 1
            return super().setGeometry(*args)

        def set_font_size(self, size: int) -> None:
            self.font_size_mutations += 1
            super().set_font_size(size)

    clock = _PreviewMutationProbe(display)
    display.clock_widget = clock
    qtbot.addWidget(clock)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    state = manager._shell_states["clock"]
    clock.geometry_mutations = 0
    clock.font_size_mutations = 0

    manager._refresh_shell_snapshot_for_resize_preview(state, QSize(260, 140))

    assert clock.geometry_mutations == 0
    assert clock.font_size_mutations == 0


def test_edit_shell_clears_resize_state_on_mouse_ungrab(qtbot):
    shell = EditShellWidget(
        widget_id="clock",
        snapshot=QPixmap(80, 40),
        initial_global_rect=QRect(20, 20, 160, 90),
        resizable=True,
    )
    qtbot.addWidget(shell)
    shell.show()

    shell._resizing = True
    shell._resize_corner = "bottom_right"

    QApplication.sendEvent(shell, QEvent(QEvent.Type.UngrabMouse))

    assert shell._resizing is False
    assert shell._resize_corner is None


def test_custom_layout_corner_resize_stays_on_current_screen(qtbot, monkeypatch):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    screen_a = _FakeScreen("Display-A", QRect(0, 0, 800, 600))
    screen_b = _FakeScreen("Display-B", QRect(800, 0, 800, 600))
    settings_stub._widgets_map = {"clock": {"position": "Top Right"}}
    display_a = _DisplayStub(settings_stub, screen=screen_a, screen_index=0)
    display_b = _DisplayStub(settings_stub, screen=screen_b, screen_index=1)
    qtbot.addWidget(display_a)
    qtbot.addWidget(display_b)
    display_a.show()
    display_b.show()

    clock_a = _EditableTestWidget(display_a, font_size=48)
    display_a.clock_widget = clock_a
    qtbot.addWidget(clock_a)

    manager_a = CustomLayoutManager(display_a)
    manager_b = CustomLayoutManager(display_b)
    _attach_manager(display_a, manager_a)
    _attach_manager(display_b, manager_b)

    class _CoordinatorStub:
        def get_all_instances(self):
            return [display_a, display_b]

    monkeypatch.setattr("rendering.custom_layout_manager.get_coordinator", lambda: _CoordinatorStub())

    assert manager_a.start_session() is True
    state = manager_a._shell_states["clock"]
    origin_signature = state.current_screen_signature
    manager_a._on_shell_resize_drag_started(
        "clock",
        "top_right",
        QRect(state.current_global_rect),
        state.current_global_rect.topRight(),
    )
    manager_a._on_shell_resize_drag_live_changed(
        "clock",
        "top_right",
        QRect(state.current_global_rect),
        QPoint(screen_b.geometry().x() + 10, state.current_global_rect.y() - 10),
    )

    assert state.current_screen_signature == origin_signature


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


def test_custom_layout_manager_enter_saves_active_session(qtbot, monkeypatch):
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
    monkeypatch.setattr(
        CustomLayoutManager,
        "active_manager",
        classmethod(lambda cls: manager),
    )

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

    volume = _VolumeLikeTestWidget(display)
    display.spotify_volume_widget = volume
    qtbot.addWidget(volume)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    state = manager._shell_states["spotify_volume"]
    updated_rect = QRect(state.current_global_rect.x() + 80, state.current_global_rect.y() + 24, 144, 320)
    state.current_global_rect = QRect(updated_rect)
    state.current_size_payload = {
        "width": 144,
        "height": 320,
        "track_width": 28,
        "track_margin": 10,
    }
    state.resize_scale = 1.35
    state.shell.set_shell_geometry(updated_rect)

    assert manager.save_session() is True
    widgets_map = settings_stub.get_widgets_map()
    assert widgets_map["media"]["position"] == "Custom"
    displays = widgets_map["custom_layout"]["displays"]
    payload = next(iter(displays.values()))["spotify_volume"]
    assert payload["resize_mode"] == "volume_scale"
    assert payload["size_payload"] == {
        "width": 144,
        "height": 320,
        "track_width": 28,
        "track_margin": 10,
    }
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

    volume = _VolumeLikeTestWidget(display)
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


def test_custom_layout_manager_media_shell_reset_visualizer_recovers_edit_rect_without_committing(qtbot):
    _reset_custom_layout_manager_state()
    screen = _FakeScreen("reset-vis-screen", QRect(0, 0, 800, 600))
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "media": {"enabled": True, "position": "Bottom Left", "monitor": "ALL"},
        "spotify_visualizer": {
            "enabled": True,
            "position": "Custom",
            "monitor": "1",
            "mode": "bubble",
            "preset_bubble": 3,
            "bubble_big_count": 7,
        },
        "custom_layout": {
            "version": 1,
            "displays": {
                get_screen_signature(screen): {
                    "media": {
                        "rect": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.2},
                        "size_payload": {"font_size": 22, "artwork_size": 220},
                        "resize_mode": "media_scale",
                    },
                    "spotify_visualizer": {
                        "rect": {"x": 0.2, "y": 0.1, "width": 0.4, "height": 0.2},
                        "size_payload": {"width": 420, "height": 180},
                        "resize_mode": "visualizer_rect",
                    },
                }
            },
        },
    }
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.show()
    media = _EditableTestWidget(display, font_size=22)
    visualizer = _VisualizerLikeTestWidget(display)
    setattr(visualizer, "_custom_layout_local_rect", QRect(160, 60, 320, 120))
    display.media_widget = media
    display.spotify_visualizer_widget = visualizer
    qtbot.addWidget(media)
    qtbot.addWidget(visualizer)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True
    media_shell = manager._shell_states["media"].shell
    assert media_shell._reset_visualizer_btn.isVisible() is True
    assert media_shell._reset_visualizer_btn.isEnabled() is True

    assert manager._reset_visualizer_from_media_shell() is True

    assert manager.is_active() is True
    assert settings_stub.saved is False
    assert display._runtime_reload_requests == 0

    widgets_map = settings_stub.get_widgets_map()
    assert widgets_map["media"]["position"] == "Bottom Left"
    assert widgets_map["spotify_visualizer"]["position"] == "Custom"
    assert widgets_map["spotify_visualizer"]["monitor"] == "1"
    assert widgets_map["spotify_visualizer"]["mode"] == "bubble"
    assert widgets_map["spotify_visualizer"]["preset_bubble"] == 3
    assert widgets_map["spotify_visualizer"]["bubble_big_count"] == 7
    saved_layout = widgets_map["custom_layout"]["displays"][get_screen_signature(screen)]
    assert "media" in saved_layout
    assert "spotify_visualizer" in saved_layout
    assert hasattr(visualizer, "_custom_layout_local_rect")

    state = manager._shell_states["spotify_visualizer"]
    assert state.removed is False
    assert state.shell.isVisible() is True
    local_rect = QRect(display.mapFromGlobal(state.current_global_rect.topLeft()), state.current_global_rect.size())
    assert local_rect == QRect(160, 60, 320, 120)
    assert state.current_size_payload == {"width": 320, "height": 120}

    assert manager.save_session() is True
    widgets_map = settings_stub.get_widgets_map()
    assert widgets_map["spotify_visualizer"]["position"] == "Custom"
    assert widgets_map["spotify_visualizer"]["monitor"] == "1"
    saved_layout = widgets_map["custom_layout"]["displays"][get_screen_signature(screen)]
    assert "spotify_visualizer" in saved_layout
    assert settings_stub.saved is True
    assert display._runtime_reload_requests == 1


def test_custom_layout_manager_media_shell_reset_visualizer_creates_transparent_shell_without_live_widget(qtbot):
    _reset_custom_layout_manager_state()
    screen = _FakeScreen("reset-vis-placeholder-screen", QRect(0, 0, 800, 600))
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "media": {"enabled": True, "position": "Bottom Left", "monitor": "ALL"},
        "spotify_visualizer": {
            "enabled": True,
            "position": "Custom",
            "monitor": "1",
            "mode": "spectrum",
        },
        "custom_layout": {
            "version": 1,
            "displays": {
                get_screen_signature(screen): {
                    "media": {
                        "rect": {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.2},
                        "size_payload": {"font_size": 22, "artwork_size": 220},
                        "resize_mode": "media_scale",
                    },
                    "spotify_visualizer": {
                        "rect": {"x": 0.25, "y": 0.15, "width": 0.5, "height": 0.25},
                        "size_payload": {"width": 400, "height": 150},
                        "resize_mode": "visualizer_rect",
                    },
                }
            },
        },
    }
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.show()
    media = _EditableTestWidget(display, font_size=22)
    display.media_widget = media
    display.spotify_visualizer_widget = None
    qtbot.addWidget(media)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True
    assert "spotify_visualizer" not in manager._shell_states

    assert manager._reset_visualizer_from_media_shell() is True

    assert manager.is_active() is True
    assert settings_stub.saved is False
    assert display._runtime_reload_requests == 0
    state = manager._shell_states["spotify_visualizer"]
    assert getattr(state.widget, "_custom_layout_recovery_placeholder", False) is True
    assert state.shell.isVisible() is True
    local_rect = QRect(display.mapFromGlobal(state.current_global_rect.topLeft()), state.current_global_rect.size())
    assert local_rect == QRect(200, 90, 400, 150)

    assert manager.save_session() is True
    widgets_map = settings_stub.get_widgets_map()
    assert widgets_map["spotify_visualizer"]["position"] == "Custom"
    assert widgets_map["spotify_visualizer"]["monitor"] == "1"
    saved_layout = widgets_map["custom_layout"]["displays"][get_screen_signature(screen)]
    assert "spotify_visualizer" in saved_layout
    assert display._runtime_reload_requests == 1


def test_custom_layout_manager_media_shell_reset_visualizer_uses_foreign_saved_as_centered_rescue_rect(qtbot, monkeypatch):
    _reset_custom_layout_manager_state()
    screen_a = _FakeScreen("foreign-vis-a", QRect(0, 0, 800, 600))
    screen_b = _FakeScreen("foreign-vis-b", QRect(800, 0, 800, 600))
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "media": {"enabled": True, "position": "Bottom Left", "monitor": "2"},
        "spotify_visualizer": {
            "enabled": True,
            "position": "Custom",
            "monitor": "2",
            "mode": "spectrum",
        },
        "custom_layout": {
            "version": 1,
            "displays": {
                get_screen_signature(screen_a): {
                    "spotify_visualizer": {
                        "rect": {"x": 0.1, "y": 0.2, "width": 0.525, "height": 0.4667},
                        "size_payload": {"width": 420, "height": 280},
                        "resize_mode": "visualizer_rect",
                    },
                }
            },
        },
    }
    display_a = _DisplayStub(settings_stub, screen=screen_a, screen_index=0)
    display_b = _DisplayStub(settings_stub, screen=screen_b, screen_index=1)
    qtbot.addWidget(display_a)
    qtbot.addWidget(display_b)
    display_a.show()
    display_b.show()
    media = _EditableTestWidget(display_b, font_size=22)
    display_b.media_widget = media
    display_b.spotify_visualizer_widget = None
    qtbot.addWidget(media)

    manager_a = CustomLayoutManager(display_a)
    manager_b = CustomLayoutManager(display_b)
    _attach_manager(display_a, manager_a)
    _attach_manager(display_b, manager_b)

    class _CoordinatorStub:
        def get_all_instances(self):
            return [display_a, display_b]

    monkeypatch.setattr("rendering.custom_layout_manager.get_coordinator", lambda: _CoordinatorStub())

    assert manager_b.start_session() is True
    assert "spotify_visualizer" not in manager_b._shell_states
    assert manager_b._reset_visualizer_from_media_shell() is True

    state = manager_b._shell_states["spotify_visualizer"]
    local_rect = QRect(display_b.mapFromGlobal(state.current_global_rect.topLeft()), state.current_global_rect.size())
    assert local_rect == QRect(190, 160, 420, 280)
    assert state.current_size_payload == {"width": 420, "height": 280}
    assert state.current_monitor_value == "2"


def test_custom_layout_manager_duplicate_all_shell_can_be_removed_to_single_display(qtbot, monkeypatch):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"clock": {"position": "Top Left", "monitor": "ALL"}}

    screen_a = _FakeScreen("Display-A", QRect(0, 0, 800, 600))
    screen_b = _FakeScreen("Display-B", QRect(800, 0, 800, 600))
    display_a = _DisplayStub(settings_stub, screen=screen_a, screen_index=0)
    display_b = _DisplayStub(settings_stub, screen=screen_b, screen_index=1)
    qtbot.addWidget(display_a)
    qtbot.addWidget(display_b)
    display_a.show()
    display_b.show()

    clock_a = _EditableTestWidget(display_a, font_size=48)
    clock_b = _EditableTestWidget(display_b, font_size=48)
    display_a.clock_widget = clock_a
    display_b.clock_widget = clock_b
    qtbot.addWidget(clock_a)
    qtbot.addWidget(clock_b)

    manager_a = CustomLayoutManager(display_a)
    manager_b = CustomLayoutManager(display_b)
    _attach_manager(display_a, manager_a)
    _attach_manager(display_b, manager_b)

    class _CoordinatorStub:
        def get_all_instances(self):
            return [display_a, display_b]

    monkeypatch.setattr("rendering.custom_layout_manager.get_coordinator", lambda: _CoordinatorStub())

    assert manager_a.start_session() is True
    state_a = manager_a._shell_states["clock"]
    state_b = manager_b._shell_states["clock"]

    assert state_a.shell._remove_btn.isVisible() is True
    assert state_b.shell._remove_btn.isVisible() is True

    restack_events: list[str] = []
    monkeypatch.setattr(state_a.shell, "raise_", lambda: restack_events.append("shell_a"), raising=False)

    manager_b._on_shell_remove_requested("clock")

    assert state_b.removed is True
    assert state_b.shell.isVisible() is False
    assert state_a.shell._remove_btn.isVisible() is False
    assert "shell_a" in restack_events

    assert manager_a.save_session() is True
    widgets_map = settings_stub.get_widgets_map()
    assert widgets_map["clock"]["position"] == "Custom"
    assert widgets_map["clock"]["monitor"] == "1"
    displays = widgets_map["custom_layout"]["displays"]
    assert len(displays) == 1
    payload = next(iter(displays.values()))["clock"]
    assert payload["resize_mode"] == "clock_font"


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


def test_custom_layout_manager_raise_all_active_shells_normalizes_overlay_stack(qtbot, monkeypatch):
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
    calls: list[str] = []
    monkeypatch.setattr(state.shell, "raise_", lambda: calls.append("shell"), raising=False)

    CustomLayoutManager.raise_all_active_shells()

    assert calls == ["shell"]


def test_custom_layout_manager_raise_all_active_shells_does_not_force_show_or_update(qtbot, monkeypatch):
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
    forced_calls: list[str] = []
    monkeypatch.setattr(manager._grid_overlay, "show", lambda: forced_calls.append("overlay_show"), raising=False)
    monkeypatch.setattr(state.shell, "show", lambda: forced_calls.append("shell_show"), raising=False)
    monkeypatch.setattr(state.shell, "update", lambda: forced_calls.append("shell_update"), raising=False)

    CustomLayoutManager.raise_all_active_shells()

    assert forced_calls == []


def test_custom_layout_manager_global_restack_keeps_cross_display_shells_in_shell_phase(qtbot, monkeypatch):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"clock": {"position": "Top Right"}}
    screen_a = _FakeScreen("Display-A", QRect(0, 0, 800, 600))
    screen_b = _FakeScreen("Display-B", QRect(800, 0, 800, 600))
    display_a = _DisplayStub(settings_stub, screen=screen_a, screen_index=0)
    display_b = _DisplayStub(settings_stub, screen=screen_b, screen_index=1)
    qtbot.addWidget(display_a)
    qtbot.addWidget(display_b)
    display_a.show()
    display_b.show()
    display_a.clock_widget = _EditableTestWidget(display_a)
    display_b.clock_widget = _EditableTestWidget(display_b)

    manager_a = CustomLayoutManager(display_a)
    manager_b = CustomLayoutManager(display_b)
    _attach_manager(display_a, manager_a)
    _attach_manager(display_b, manager_b)

    class _CoordinatorStub:
        def get_all_instances(self):
            return [display_a, display_b]

    monkeypatch.setattr("rendering.custom_layout_manager.get_coordinator", lambda: _CoordinatorStub())

    assert manager_a.start_session() is True
    state_a = manager_a._shell_states["clock"]
    state_b = manager_b._shell_states["clock"]
    state_a.current_screen = screen_b
    state_a.current_screen_signature = get_screen_signature(screen_b)

    calls: list[str] = []
    monkeypatch.setattr(state_a.shell, "raise_", lambda: calls.append("shell_a"), raising=False)
    monkeypatch.setattr(state_b.shell, "raise_", lambda: calls.append("shell_b"), raising=False)

    CustomLayoutManager.raise_all_active_shells()

    assert calls == ["shell_a", "shell_b"]


def test_custom_layout_manager_restore_shells_for_display_targets_only_current_display(qtbot, monkeypatch):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"clock": {"position": "Top Right"}}
    screen_a = _FakeScreen("Display-A", QRect(0, 0, 800, 600))
    screen_b = _FakeScreen("Display-B", QRect(800, 0, 800, 600))
    display_a = _DisplayStub(settings_stub, screen=screen_a, screen_index=0)
    display_b = _DisplayStub(settings_stub, screen=screen_b, screen_index=1)
    qtbot.addWidget(display_a)
    qtbot.addWidget(display_b)
    display_a.show()
    display_b.show()
    display_a.clock_widget = _EditableTestWidget(display_a)
    display_b.clock_widget = _EditableTestWidget(display_b)

    manager_a = CustomLayoutManager(display_a)
    manager_b = CustomLayoutManager(display_b)
    _attach_manager(display_a, manager_a)
    _attach_manager(display_b, manager_b)

    class _CoordinatorStub:
        def get_all_instances(self):
            return [display_a, display_b]

    monkeypatch.setattr("rendering.custom_layout_manager.get_coordinator", lambda: _CoordinatorStub())

    assert manager_a.start_session() is True
    state_a = manager_a._shell_states["clock"]
    state_b = manager_b._shell_states["clock"]
    state_a.current_screen = screen_b
    state_a.current_screen_signature = get_screen_signature(screen_b)

    calls: list[str] = []
    monkeypatch.setattr(state_a.shell, "raise_", lambda: calls.append("shell_a"), raising=False)
    monkeypatch.setattr(state_b.shell, "raise_", lambda: calls.append("shell_b"), raising=False)

    CustomLayoutManager.restore_shells_for_display(display_b)

    assert calls == ["shell_a", "shell_b"]


def test_edit_shell_widget_child_parent_preserves_global_geometry(qtbot):
    host = QWidget()
    host.setGeometry(200, 120, 600, 400)
    qtbot.addWidget(host)
    host.show()

    snapshot = QPixmap(100, 60)
    snapshot.fill(QColor(20, 20, 20, 180))
    shell = EditShellWidget(
        widget_id="clock",
        snapshot=snapshot,
        initial_global_rect=QRect(260, 190, 100, 60),
        resizable=True,
        parent=host,
    )
    qtbot.addWidget(shell)
    shell.show()

    assert shell.current_global_rect() == QRect(260, 190, 100, 60)

    shell.set_shell_geometry(QRect(320, 240, 120, 70))

    assert shell.current_global_rect() == QRect(320, 240, 120, 70)


def test_custom_layout_manager_reparents_shell_to_target_display(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    screen_a = _FakeScreen("Screen A", QRect(0, 0, 800, 600))
    screen_b = _FakeScreen("Screen B", QRect(800, 0, 800, 600))
    display_a = _DisplayStub(settings_stub, screen=screen_a, screen_index=0)
    display_b = _DisplayStub(settings_stub, screen=screen_b, screen_index=1)
    qtbot.addWidget(display_a)
    qtbot.addWidget(display_b)
    display_a.show()
    display_b.show()

    display_a.clock_widget = _EditableTestWidget(display_a)
    manager = CustomLayoutManager(display_a)
    _attach_manager(display_a, manager)
    assert manager._start_session_local() is True

    state = manager._shell_states["clock"]
    assert state.shell.parentWidget() is display_a

    target_rect = QRect(860, 90, state.current_global_rect.width(), state.current_global_rect.height())
    state.current_screen = screen_b
    state.current_screen_signature = get_screen_signature(screen_b)
    state.current_global_rect = QRect(target_rect)
    manager._get_display_instance_for_screen = lambda screen: display_b if screen is screen_b else display_a  # type: ignore[method-assign]

    manager._sync_shell_parent_to_state(state)

    assert state.shell.parentWidget() is display_b
    assert state.shell.current_global_rect().size() == target_rect.size()


def test_custom_layout_manager_live_apply_reparents_shell_before_cross_display_drag_commits(qtbot, monkeypatch):
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

    clock = _EditableTestWidget(display1, font_size=32)
    display1.clock2_widget = clock
    qtbot.addWidget(clock)

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
    target_rect = QRect(120, 90, state.current_global_rect.width(), state.current_global_rect.height())
    resolved = manager1._resolve_shell_geometry_for_widget_id(
        "clock2",
        target_rect,
        cursor_global=target_rect.center(),
        snap_to_grid=False,
    )
    manager1._apply_live_shell_geometry_for_widget_id("clock2", resolved)

    assert state.current_screen is screen0
    assert state.shell.parentWidget() is display0
    assert state.shell.current_global_rect() == resolved


def test_custom_layout_manager_schedule_raise_all_active_shells_coalesces(monkeypatch):
    _reset_custom_layout_manager_state()
    scheduled: list[int] = []
    invocations: list[str] = []
    queued_callbacks: list[object] = []

    monkeypatch.setattr(
        "rendering.custom_layout_manager.ThreadManager.single_shot",
        lambda delay_ms, callback, *args, **kwargs: (
            scheduled.append(int(delay_ms)),
            queued_callbacks.append(lambda: callback(*args, **kwargs)),
        ),
    )
    monkeypatch.setattr(
        CustomLayoutManager,
        "is_any_session_active",
        classmethod(lambda cls: True),
    )
    monkeypatch.setattr(
        CustomLayoutManager,
        "raise_all_active_shells",
        classmethod(lambda cls: invocations.append("raised")),
    )
    monkeypatch.setattr(
        CustomLayoutManager,
        "is_any_session_active",
        classmethod(lambda cls: True),
    )

    CustomLayoutManager._restack_scheduled = False
    CustomLayoutManager.schedule_raise_all_active_shells()
    CustomLayoutManager.schedule_raise_all_active_shells()
    assert scheduled == [0]
    assert invocations == []

    queued_callbacks.pop(0)()

    assert invocations == ["raised"]


def test_custom_layout_manager_schedule_raise_all_active_shells_defers_during_menu(monkeypatch):
    _reset_custom_layout_manager_state()
    scheduled: list[int] = []
    invocations: list[str] = []

    monkeypatch.setattr(
        "rendering.custom_layout_manager.ThreadManager.single_shot",
        lambda delay_ms, callback, *args, **kwargs: scheduled.append(int(delay_ms)),
    )
    monkeypatch.setattr(
        CustomLayoutManager,
        "raise_all_active_shells",
        classmethod(lambda cls: invocations.append("raised")),
    )
    monkeypatch.setattr(
        CustomLayoutManager,
        "is_any_session_active",
        classmethod(lambda cls: True),
    )

    CustomLayoutManager._menu_interaction_depth = 1
    CustomLayoutManager._restack_pending_during_menu = False
    CustomLayoutManager._restack_scheduled = False

    CustomLayoutManager.schedule_raise_all_active_shells()

    assert scheduled == []
    assert invocations == []
    assert CustomLayoutManager._restack_pending_during_menu is True

    monkeypatch.setattr(
        "rendering.custom_layout_manager.ThreadManager.single_shot",
        lambda delay_ms, callback, *args, **kwargs: callback(*args, **kwargs),
    )
    CustomLayoutManager.end_menu_interaction()

    assert invocations == ["raised"]
    assert CustomLayoutManager._menu_interaction_depth == 0
    assert CustomLayoutManager._restack_pending_during_menu is False


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
                        "rect": {"x": 0.4, "y": 0.2, "width": 0.18, "height": 0.48},
                        "size_payload": {
                            "width": 144,
                            "height": 288,
                            "track_width": 26,
                            "track_margin": 9,
                        },
                        "resize_mode": "volume_scale",
                    }
                }
            },
        },
    }
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.show()

    volume = _VolumeLikeTestWidget(display)
    display.spotify_volume_widget = volume
    qtbot.addWidget(volume)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    manager.apply_saved_layouts_to_display()

    custom_rect = getattr(volume, "_custom_layout_local_rect", None)
    assert isinstance(custom_rect, QRect)
    assert custom_rect.width() == 144
    assert custom_rect.height() == 288
    assert volume.minimumWidth() == 144
    assert volume.minimumHeight() == 288
    assert volume._track_width == 26
    assert volume._track_margin == 9


def test_custom_layout_manager_reasserts_volume_outer_rect_after_scale_contract(qtbot):
    _reset_custom_layout_manager_state()
    screen = _FakeScreen("A", QRect(0, 0, 800, 600))
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "media": {"position": "Custom", "monitor": "1"},
        "custom_layout": {
            "version": 1,
            "displays": {
                get_screen_signature(screen): {
                    "spotify_volume": {
                        "rect": {"x": 0.4, "y": 0.2, "width": 0.18, "height": 0.48},
                        "size_payload": {
                            "width": 144,
                            "height": 288,
                            "track_width": 26,
                            "track_margin": 9,
                        },
                        "resize_mode": "volume_scale",
                    }
                }
            },
        },
    }
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.show()

    class _StretchyVolume(_VolumeLikeTestWidget):
        def apply_scale_contract(self, **kwargs) -> None:
            super().apply_scale_contract(**kwargs)
            self.setGeometry(self.x(), self.y(), self.width() + 40, self.height() + 80)

    volume = _StretchyVolume(display)
    display.spotify_volume_widget = volume
    qtbot.addWidget(volume)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    manager.apply_saved_layouts_to_display()

    custom_rect = getattr(volume, "_custom_layout_local_rect", None)
    assert isinstance(custom_rect, QRect)
    assert custom_rect.width() == 144
    assert custom_rect.height() == 288
    assert volume.geometry() == custom_rect


def test_custom_layout_manager_volume_resize_rect_uses_payload_dimensions(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"media": {"position": "Bottom Left", "monitor": "1"}}
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()

    volume = _VolumeLikeTestWidget(display)
    display.spotify_volume_widget = volume
    qtbot.addWidget(volume)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    state = manager._shell_states["spotify_volume"]
    state.resize_scale = 1.5
    state.current_size_payload = {
        "width": 48,
        "height": 270,
        "track_width": 22,
        "track_margin": 8,
    }

    rect = manager._scaled_rect_from_baseline(state)
    assert rect.width() == 48
    assert rect.height() == 270
    assert manager._min_size_for_state(state) == QSize(24, 120)


def test_custom_layout_manager_volume_scale_payload_biases_shrink_more_aggressively(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    display = _DisplayStub(settings_stub, screen=_FakeScreen("screen0", QRect(0, 0, 800, 600)))
    qtbot.addWidget(display)

    manager = CustomLayoutManager(display)

    class _Descriptor:
        custom_layout_resize_mode = "volume_scale"

    payload = manager._scale_size_payload(
        _Descriptor(),
        {
            "width": 32,
            "height": 234,
            "track_width": 18,
            "track_margin": 6,
        },
        0.8,
    )

    assert payload == {
        "width": 24,
        "height": 168,
        "track_width": 13,
        "track_margin": 4,
    }


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


def test_custom_layout_manager_apply_saved_layouts_clamps_rect_within_display_bounds(qtbot):
    _reset_custom_layout_manager_state()
    screen = _FakeScreen("screen0", QRect(0, 0, 800, 600))
    signature = get_screen_signature(screen)
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "gmail": {"position": "Custom"},
        "custom_layout": {
            "version": 1,
            "displays": {
                signature: {
                    "gmail": {
                        "rect": {"x": 0.7, "y": 0.75, "width": 0.45, "height": 0.4},
                        "size_payload": {"font_size": 20},
                        "resize_mode": "gmail_font",
                    }
                }
            },
        },
    }
    display = _DisplayStub(settings_stub, screen=screen, screen_index=0)
    qtbot.addWidget(display)
    display.show()

    gmail = _GmailLikeTestWidget(display, font_size=13)
    display.gmail_widget = gmail
    qtbot.addWidget(gmail)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    manager.apply_saved_layouts_to_display()

    custom_rect = getattr(gmail, "_custom_layout_local_rect", None)
    assert isinstance(custom_rect, QRect)
    assert custom_rect.x() >= 0
    assert custom_rect.y() >= 0
    assert custom_rect.right() <= screen.geometry().width() - 1
    assert custom_rect.bottom() <= screen.geometry().height() - 1


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
    resolved = manager._shell_states["clock"].current_global_rect

    assert resolved == proposal
    assert manager._shell_states["clock"].shell.current_global_rect() == resolved
    assert manager._shell_states["clock"].shell._active_vertical_guides


def test_custom_layout_manager_live_drag_guides_without_forcing_snap(qtbot):
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

    resolved = manager._resolve_shell_geometry_for_widget_id(
        "clock",
        proposal,
        cursor_global=proposal.center(),
        snap_to_grid=False,
    )

    assert resolved == proposal
    assert clock_state.shell.current_global_rect() == clock_state.current_global_rect
    assert clock_state.shell._active_vertical_guides


def test_custom_layout_display_center_guides_are_real_snap_candidates(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    display = _DisplayStub(settings_stub, screen=_FakeScreen("screen0", QRect(0, 0, 800, 600)))
    qtbot.addWidget(display)
    display.show()

    clock = _EditableTestWidget(display, font_size=48)
    display.clock_widget = clock
    qtbot.addWidget(clock)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    clock_state = manager._shell_states["clock"]
    proposal = QRect(
        309,
        40,
        clock_state.current_global_rect.width(),
        clock_state.current_global_rect.height(),
    )

    live_resolved = manager._resolve_shell_geometry_for_widget_id(
        "clock",
        proposal,
        cursor_global=proposal.center(),
        snap_to_grid=False,
    )

    assert live_resolved == proposal
    assert clock_state.shell._active_vertical_guides[0][1] == "display_center"
    assert manager._grid_overlay._active_vertical_guides[0][1] == "display_center"

    committed = manager._resolve_shell_geometry_for_widget_id(
        "clock",
        proposal,
        cursor_global=proposal.center(),
        snap_to_grid=True,
    )

    assert committed.x() == 310
    assert committed.center().x() in (399, 400)


def test_custom_layout_peer_center_guides_are_real_snap_candidates(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()

    clock = _EditableTestWidget(display, font_size=48)
    weather = _EditableTestWidget(display, font_size=18)
    weather.setGeometry(300, 60, 220, 80)
    display.clock_widget = clock
    display.weather_widget = weather
    qtbot.addWidget(clock)
    qtbot.addWidget(weather)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    clock_state = manager._shell_states["clock"]
    weather_state = manager._shell_states["weather"]
    peer_center = int(
        round(
            (
                float(weather_state.current_global_rect.x())
                + float(weather_state.current_global_rect.x() + weather_state.current_global_rect.width())
            )
            / 2.0
        )
    )
    target_x = peer_center - int(round(float(clock_state.current_global_rect.width()) / 2.0))
    proposal = QRect(
        target_x,
        weather_state.current_global_rect.y() + weather_state.current_global_rect.height() + 16,
        clock_state.current_global_rect.width(),
        clock_state.current_global_rect.height(),
    )

    live_resolved = manager._resolve_shell_geometry_for_widget_id(
        "clock",
        proposal,
        cursor_global=proposal.center(),
        snap_to_grid=False,
    )

    assert live_resolved == proposal
    assert clock_state.shell._active_vertical_guides[0][1] == "peer_center"
    assert manager._grid_overlay._active_vertical_guides[0][1] == "peer_center"

    committed = manager._resolve_shell_geometry_for_widget_id(
        "clock",
        proposal,
        cursor_global=proposal.center(),
        snap_to_grid=True,
    )

    assert committed.x() == target_x
    assert committed.center().x() in (peer_center - 1, peer_center)


def test_custom_layout_snap_resolution_includes_peer_center_assists():
    resolution = resolve_snap_local_rect_for_edit(
        QRect(318, 160, 180, 80),
        QSize(800, 600),
        peer_rects=(QRect(300, 60, 220, 80),),
        threshold_px=8,
    )

    assert resolution.vertical_guides[0].kind == "peer_center"
    assert resolution.vertical_guides[0].position == 410


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


def test_custom_layout_manager_marks_runtime_reload_pending_during_save(qtbot):
    _reset_custom_layout_manager_state()

    class _CheckingSettingsStub(_SettingsStub):
        def __init__(self, display: _DisplayStub) -> None:
            super().__init__()
            self._display = display
            self.flags_seen: list[bool] = []

        def save(self) -> None:
            self.flags_seen.append(bool(getattr(self._display, "_custom_layout_runtime_reload_pending", False)))
            super().save()

    display = _DisplayStub(_SettingsStub())
    settings_stub = _CheckingSettingsStub(display)
    display.settings_manager = settings_stub
    qtbot.addWidget(display)
    display.show()

    reddit = _RedditLikeTestWidget(display, font_size=18)
    display.reddit_widget = reddit
    qtbot.addWidget(reddit)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    state = manager._shell_states["reddit"]
    state.current_size_payload = {"font_size": 20}

    assert manager.save_session() is True
    assert settings_stub.flags_seen == [True]
    assert getattr(display, "_custom_layout_runtime_reload_pending", False) is False


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
    state.current_size_payload = {"width": 420, "height": 210}
    state.shell.set_shell_geometry(updated_rect)

    assert manager.save_session() is True
    widgets_map = settings_stub.get_widgets_map()
    assert widgets_map["media"]["position"] == "Bottom Left"
    assert widgets_map["spotify_visualizer"]["position"] == "Custom"
    payload = next(iter(widgets_map["custom_layout"]["displays"].values()))["spotify_visualizer"]
    assert payload["resize_mode"] == "visualizer_rect"
    assert payload["size_payload"] == {"width": 420, "height": 210}


def test_custom_layout_manager_reapplies_visualizer_custom_rect_size(qtbot):
    _reset_custom_layout_manager_state()
    screen = _FakeScreen("Display-A", QRect(0, 0, 1000, 700))
    signature = get_screen_signature(screen)
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "media": {"position": "Bottom Left", "monitor": "2"},
        "spotify_visualizer": {"position": "Custom", "monitor": "1"},
        "custom_layout": {
            "version": 1,
            "displays": {
                signature: {
                    "spotify_visualizer": {
                        "rect": {"x": 0.22, "y": 0.38, "width": 0.42, "height": 0.31},
                        "size_payload": {"width_scale": 1.0, "height_scale": 1.0},
                        "resize_mode": "visualizer_rect",
                    }
                }
            },
        },
    }
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.show()

    visualizer = _VisualizerLikeTestWidget(display)
    display.spotify_visualizer_widget = visualizer
    qtbot.addWidget(visualizer)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    manager.apply_saved_layouts_to_display()

    custom_rect = getattr(visualizer, "_custom_layout_local_rect", None)
    assert isinstance(custom_rect, QRect)
    assert custom_rect.width() == 420
    assert custom_rect.height() == 217
    assert visualizer.geometry() == custom_rect


def test_custom_layout_manager_keeps_committed_visualizer_rect_even_if_mode_height_differs(qtbot):
    _reset_custom_layout_manager_state()
    screen = _FakeScreen("Display-A", QRect(0, 0, 800, 600))
    signature = get_screen_signature(screen)
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "media": {"position": "Custom", "monitor": "1"},
        "spotify_visualizer": {"position": "Custom", "monitor": "1"},
        "custom_layout": {
            "version": 1,
            "displays": {
                signature: {
                    "spotify_visualizer": {
                        "rect": {"x": 0.045, "y": 0.20, "width": 0.36, "height": 0.40},
                        "size_payload": {"width_scale": 1.0, "height_scale": 1.0},
                        "resize_mode": "visualizer_rect",
                    }
                }
            },
        },
    }
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.show()

    visualizer = _VisualizerLikeTestWidget(display)
    visualizer._vis_mode_str = "bubble"
    visualizer._bubble_growth = 5.0
    visualizer._base_height = 80
    visualizer.setGeometry(0, 0, 100, 400)
    display.spotify_visualizer_widget = visualizer
    qtbot.addWidget(visualizer)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    manager.apply_saved_layouts_to_display()

    custom_rect = getattr(visualizer, "_custom_layout_local_rect", None)
    assert isinstance(custom_rect, QRect)
    assert custom_rect == QRect(36, 120, 288, 240)
    assert visualizer.geometry() == custom_rect


def test_custom_layout_manager_replays_real_visualizer_rect_over_authored_min_height(qtbot):
    _reset_custom_layout_manager_state()
    screen = _FakeScreen("Display-A", QRect(0, 0, 800, 600))
    signature = get_screen_signature(screen)
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "spotify_visualizer": {"position": "Custom", "monitor": "1"},
        "custom_layout": {
            "version": 1,
            "displays": {
                signature: {
                    "spotify_visualizer": {
                        "rect": {"x": 0.255, "y": 0.30, "width": 0.525, "height": 0.4666666667},
                        "size_payload": {"width_scale": 0.7, "height_scale": 0.7},
                        "resize_mode": "visualizer_rect",
                    }
                }
            },
        },
    }
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.resize(800, 600)
    display.show()

    visualizer = SpotifyVisualizerWidget(display, bar_count=8)
    visualizer.setMinimumHeight(400)
    visualizer.setGeometry(0, 0, 100, 400)
    display.spotify_visualizer_widget = visualizer
    qtbot.addWidget(visualizer)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    manager.apply_saved_layouts_to_display()

    custom_rect = getattr(visualizer, "_custom_layout_local_rect", None)
    assert isinstance(custom_rect, QRect)
    assert custom_rect == QRect(204, 180, 420, 280)
    assert visualizer.geometry() == custom_rect
    assert visualizer.minimumHeight() == 280
    assert visualizer.maximumHeight() == 280


def test_custom_layout_manager_primes_visualizer_rect_before_constraint_lock_and_syncs_overlay(qtbot):
    _reset_custom_layout_manager_state()
    screen = _FakeScreen("Display-A", QRect(0, 0, 800, 600))
    signature = get_screen_signature(screen)
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "spotify_visualizer": {"position": "Custom", "monitor": "1"},
        "custom_layout": {
            "version": 1,
            "displays": {
                signature: {
                    "spotify_visualizer": {
                        "rect": {"x": 0.255, "y": 0.30, "width": 0.525, "height": 0.4666666667},
                        "size_payload": {"width": 420, "height": 280},
                        "resize_mode": "visualizer_rect",
                    }
                }
            },
        },
    }
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.resize(800, 600)
    display.show()

    class _TrackingRealVisualizer(SpotifyVisualizerWidget):
        def __init__(self, parent: QWidget) -> None:
            self.geometry_history: list[QRect] = []
            super().__init__(parent=parent, bar_count=8)

        def setGeometry(self, *args) -> None:  # type: ignore[override]
            super().setGeometry(*args)
            self.geometry_history.append(QRect(self.geometry()))

    visualizer = _TrackingRealVisualizer(display)
    visualizer.setMinimumHeight(400)
    visualizer.setGeometry(0, 0, 100, 400)
    display.spotify_visualizer_widget = visualizer
    display._spotify_bars_overlay = _OverlayGeometryStub(QRect(0, 0, 100, 400))
    qtbot.addWidget(visualizer)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    manager.apply_saved_layouts_to_display()

    custom_rect = QRect(204, 180, 420, 280)
    assert visualizer.geometry() == custom_rect
    assert visualizer.minimumHeight() == 280
    assert visualizer.maximumHeight() == 280
    assert QRect(0, 0, 420, 280) not in visualizer.geometry_history
    assert display._spotify_bars_overlay.geometry() == custom_rect


def test_widget_setup_finalize_resettles_visualizer_custom_rect_after_startup_square_pressure(qtbot, monkeypatch):
    from rendering import widget_setup_all

    _reset_custom_layout_manager_state()
    screen = _FakeScreen("Display-A", QRect(0, 0, 800, 600))
    signature = get_screen_signature(screen)
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "spotify_visualizer": {"position": "Custom", "monitor": "1"},
        "custom_layout": {
            "version": 1,
            "displays": {
                signature: {
                    "spotify_visualizer": {
                        "rect": {"x": 0.255, "y": 0.30, "width": 0.525, "height": 0.4666666667},
                        "size_payload": {"width": 420, "height": 280},
                        "resize_mode": "visualizer_rect",
                    }
                }
            },
        },
    }
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.resize(800, 600)
    display.show()

    class _TrackingRealVisualizer(SpotifyVisualizerWidget):
        def __init__(self, parent: QWidget) -> None:
            self.geometry_history: list[QRect] = []
            super().__init__(parent=parent, bar_count=8)

        def setGeometry(self, *args) -> None:  # type: ignore[override]
            super().setGeometry(*args)
            self.geometry_history.append(QRect(self.geometry()))

    visualizer = _TrackingRealVisualizer(display)
    visualizer.setMinimumHeight(400)
    visualizer.setGeometry(0, 0, 100, 400)
    display.spotify_visualizer_widget = visualizer
    display._spotify_bars_overlay = _OverlayGeometryStub(QRect(0, 0, 100, 400))
    qtbot.addWidget(visualizer)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)

    created = {"spotify_visualizer_widget": visualizer}
    wm = type(
        "_FakeWM",
        (),
        {"_parent": display, "_fade_coordinator": type("_Fade", (), {"describe": staticmethod(lambda: {"participants": []})})()},
    )()

    def _simulate_startup_pressure(_widgets):
        visualizer.setGeometry(QRect(0, 0, 357, 357))
        display._spotify_bars_overlay.setGeometry(QRect(0, 0, 357, 357))

    scheduled_callbacks: list[tuple[int, object]] = []

    monkeypatch.setattr(widget_setup_all, "_start_widgets", _simulate_startup_pressure)
    monkeypatch.setattr(
        widget_setup_all.ThreadManager,
        "single_shot",
        lambda delay, callback, *args, **kwargs: scheduled_callbacks.append(
            (int(delay), lambda: callback(*args, **kwargs))
        ),
    )

    widget_setup_all._finalize_widget_startup(wm, created)

    assert len(scheduled_callbacks) == 1
    assert scheduled_callbacks[0][0] == widget_setup_all.SPOTIFY_CUSTOM_LAYOUT_STABILIZE_VERIFY_MS
    scheduled_callbacks[0][1]()

    custom_rect = QRect(204, 180, 420, 280)
    assert display._apply_saved_layouts_calls == 2
    assert visualizer.geometry() == custom_rect
    assert visualizer.minimumWidth() == 420
    assert visualizer.maximumWidth() == 420
    assert visualizer.minimumHeight() == 280
    assert visualizer.maximumHeight() == 280
    assert display._spotify_bars_overlay.geometry() == custom_rect
    assert QRect(0, 0, 357, 357) in display._spotify_bars_overlay.history
    assert QRect(0, 0, 357, 357) not in visualizer.geometry_history
    assert custom_rect in visualizer.geometry_history


def test_widget_setup_startup_stabilizer_waits_for_persistent_visualizer_custom_rect_mismatch(qtbot, monkeypatch):
    from rendering import widget_setup_all

    _reset_custom_layout_manager_state()
    screen = _FakeScreen("Display-A", QRect(0, 0, 800, 600))
    signature = get_screen_signature(screen)
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "spotify_visualizer": {"position": "Custom", "monitor": "1"},
        "custom_layout": {
            "version": 1,
            "displays": {
                signature: {
                    "spotify_visualizer": {
                        "rect": {"x": 0.255, "y": 0.30, "width": 0.525, "height": 0.4666666667},
                        "size_payload": {"width": 420, "height": 280},
                        "resize_mode": "visualizer_rect",
                    }
                }
            },
        },
    }
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.resize(800, 600)
    display.show()

    class _TrackingRealVisualizer(SpotifyVisualizerWidget):
        def __init__(self, parent: QWidget) -> None:
            self.geometry_history: list[QRect] = []
            super().__init__(parent=parent, bar_count=8)

        def setGeometry(self, *args) -> None:  # type: ignore[override]
            super().setGeometry(*args)
            self.geometry_history.append(QRect(self.geometry()))

    visualizer = _TrackingRealVisualizer(display)
    visualizer.setMinimumHeight(400)
    visualizer.setGeometry(0, 0, 100, 400)
    display.spotify_visualizer_widget = visualizer
    display._spotify_bars_overlay = _OverlayGeometryStub(QRect(0, 0, 100, 400))
    qtbot.addWidget(visualizer)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)

    scheduled_callbacks: list[tuple[int, object]] = []

    monkeypatch.setattr(
        widget_setup_all.ThreadManager,
        "single_shot",
        lambda delay, callback, *args, **kwargs: scheduled_callbacks.append(
            (int(delay), lambda: callback(*args, **kwargs))
        ),
    )

    widget_setup_all._reapply_saved_custom_layouts_after_startup(
        display,
        log_prefix="[TEST]",
    )

    custom_rect = QRect(204, 180, 420, 280)
    assert display._apply_saved_layouts_calls == 1
    assert visualizer.geometry() == custom_rect
    assert display._spotify_bars_overlay.geometry() == custom_rect
    assert len(scheduled_callbacks) == 1
    assert scheduled_callbacks[0][0] == widget_setup_all.SPOTIFY_CUSTOM_LAYOUT_STABILIZE_VERIFY_MS

    visualizer._restore_custom_layout_size_constraints()
    QWidget.setGeometry(visualizer, QRect(0, 0, 357, 357))
    display._spotify_bars_overlay.setGeometry(QRect(0, 0, 357, 357))

    scheduled_callbacks.pop(0)[1]()

    assert bool(getattr(display, "_custom_layout_runtime_stabilize_pending", False)) is True
    assert len(scheduled_callbacks) == 1
    assert scheduled_callbacks[0][0] == widget_setup_all.SPOTIFY_CUSTOM_LAYOUT_STABILIZE_CONFIRM_MS
    assert display._apply_saved_layouts_calls == 1

    scheduled_callbacks.pop(0)[1]()

    assert bool(getattr(display, "_custom_layout_runtime_stabilize_pending", False)) is False
    assert display._apply_saved_layouts_calls == 2
    assert visualizer.geometry() == custom_rect
    assert display._spotify_bars_overlay.geometry() == custom_rect


def test_custom_layout_manager_reasserts_media_outer_rect_after_artwork_scale_apply(qtbot):
    _reset_custom_layout_manager_state()
    screen = _FakeScreen("Display-A", QRect(0, 0, 1000, 700))
    signature = get_screen_signature(screen)
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "media": {"position": "Custom", "monitor": "1"},
        "custom_layout": {
            "version": 1,
            "displays": {
                signature: {
                    "media": {
                        "rect": {"x": 0.10, "y": 0.12, "width": 0.40, "height": 0.30},
                        "size_payload": {"font_size": 18, "artwork_size": 220},
                        "resize_mode": "media_scale",
                    }
                }
            },
        },
    }
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.show()

    class _StretchyMedia(_EditableTestWidget):
        def set_artwork_size(self, size: int) -> None:
            super().set_artwork_size(size)
            self.setGeometry(self.x(), self.y(), self.width() + 120, self.height() + 40)

    media = _StretchyMedia(display, font_size=14)
    media.setGeometry(30, 40, 320, 180)
    display.media_widget = media
    qtbot.addWidget(media)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    manager.apply_saved_layouts_to_display()

    custom_rect = getattr(media, "_custom_layout_local_rect", None)
    assert isinstance(custom_rect, QRect)
    assert custom_rect.width() == 400
    assert custom_rect.height() == 210
    assert media.geometry() == custom_rect


def test_custom_layout_manager_reasserts_weather_outer_rect_after_scale_apply(qtbot):
    _reset_custom_layout_manager_state()
    screen = _FakeScreen("Display-A", QRect(0, 0, 1000, 700))
    signature = get_screen_signature(screen)
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "weather": {"position": "Custom", "monitor": "1"},
        "custom_layout": {
            "version": 1,
            "displays": {
                signature: {
                    "weather": {
                        "rect": {"x": 0.08, "y": 0.10, "width": 0.36, "height": 0.24},
                        "size_payload": {"font_size": 22, "icon_size": 50, "detail_icon_size": 24},
                        "resize_mode": "weather_scale",
                    }
                }
            },
        },
    }
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.show()

    class _StretchyWeather(_EditableTestWidget):
        def set_font_size(self, size: int) -> None:
            super().set_font_size(size)
            self.setGeometry(self.x(), self.y(), self.width() + 110, self.height() + 25)

    weather = _StretchyWeather(display, font_size=18)
    weather.setGeometry(30, 40, 220, 120)
    display.weather_widget = weather
    qtbot.addWidget(weather)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    manager.apply_saved_layouts_to_display()

    custom_rect = getattr(weather, "_custom_layout_local_rect", None)
    assert isinstance(custom_rect, QRect)
    assert custom_rect.width() == 360
    assert custom_rect.height() == 168
    assert weather.geometry() == custom_rect


def test_custom_layout_manager_reasserts_reddit_outer_rect_after_font_payload_apply(qtbot):
    _reset_custom_layout_manager_state()
    screen = _FakeScreen("Display-A", QRect(0, 0, 1000, 700))
    signature = get_screen_signature(screen)
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "reddit": {"position": "Custom", "monitor": "1"},
        "custom_layout": {
            "version": 1,
            "displays": {
                signature: {
                    "reddit": {
                        "rect": {"x": 0.10, "y": 0.14, "width": 0.42, "height": 0.32},
                        "size_payload": {"font_size": 24},
                        "resize_mode": "reddit_font",
                    }
                }
            },
        },
    }
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.show()

    class _StretchyReddit(_RedditLikeTestWidget):
        def set_font_size(self, size: int) -> None:
            super().set_font_size(size)
            self.setGeometry(self.x(), self.y(), self.width() + 140, self.height() + 60)

    reddit = _StretchyReddit(display, font_size=18)
    reddit.setGeometry(40, 60, 320, 180)
    display.reddit_widget = reddit
    qtbot.addWidget(reddit)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    manager.apply_saved_layouts_to_display()

    custom_rect = getattr(reddit, "_custom_layout_local_rect", None)
    assert isinstance(custom_rect, QRect)
    assert custom_rect.width() == 420
    assert custom_rect.height() == 224
    assert reddit.geometry() == custom_rect


def test_custom_layout_manager_reasserts_gmail_outer_rect_after_font_payload_apply(qtbot):
    _reset_custom_layout_manager_state()
    screen = _FakeScreen("Display-A", QRect(0, 0, 1000, 700))
    signature = get_screen_signature(screen)
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "gmail": {"position": "Custom", "monitor": "1"},
        "custom_layout": {
            "version": 1,
            "displays": {
                signature: {
                    "gmail": {
                        "rect": {"x": 0.12, "y": 0.16, "width": 0.44, "height": 0.28},
                        "size_payload": {"font_size": 18},
                        "resize_mode": "gmail_font",
                    }
                }
            },
        },
    }
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.show()

    class _StretchyGmail(_GmailLikeTestWidget):
        def set_font_size(self, size: int) -> None:
            super().set_font_size(size)
            self.setGeometry(self.x(), self.y(), self.width() + 160, self.height() + 45)

    gmail = _StretchyGmail(display, font_size=13)
    gmail.setGeometry(50, 70, 600, 220)
    display.gmail_widget = gmail
    qtbot.addWidget(gmail)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    manager.apply_saved_layouts_to_display()

    custom_rect = getattr(gmail, "_custom_layout_local_rect", None)
    assert isinstance(custom_rect, QRect)
    assert custom_rect.width() == 440
    assert custom_rect.height() == 196
    assert gmail.geometry() == custom_rect


def test_custom_layout_manager_can_shrink_overlay_below_authored_minimums_when_custom_rect_is_active(qtbot):
    _reset_custom_layout_manager_state()
    screen = _FakeScreen("Display-A", QRect(0, 0, 1000, 700))
    signature = get_screen_signature(screen)
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "gmail": {"position": "Custom", "monitor": "1"},
        "custom_layout": {
            "version": 1,
            "displays": {
                signature: {
                    "gmail": {
                        "rect": {"x": 0.08, "y": 0.10, "width": 0.28, "height": 0.20},
                        "size_payload": {"font_size": 18},
                        "resize_mode": "gmail_font",
                    }
                }
            },
        },
    }
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.show()

    gmail = _ConstrainedOverlayWidget(display, overlay_name="gmail", font_size=13)
    display.gmail_widget = gmail
    qtbot.addWidget(gmail)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    manager.apply_saved_layouts_to_display()

    custom_rect = getattr(gmail, "_custom_layout_local_rect", None)
    assert isinstance(custom_rect, QRect)
    assert custom_rect.width() == 280
    assert custom_rect.height() == 140
    assert gmail.minimumWidth() == 280
    assert gmail.minimumHeight() == 140
    assert gmail.maximumWidth() == 280
    assert gmail.maximumHeight() == 140
    assert gmail.geometry() == custom_rect


def test_custom_layout_manager_persists_runtime_vertical_growth_for_reddit_custom_rect(qtbot):
    _reset_custom_layout_manager_state()
    screen = _FakeScreen("Display-A", QRect(0, 0, 1000, 700))
    signature = get_screen_signature(screen)
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "reddit": {"position": "Custom", "monitor": "1"},
        "custom_layout": {
            "version": 1,
            "displays": {
                signature: {
                    "reddit": {
                        "rect": {"x": 0.10, "y": 0.14, "width": 0.42, "height": 0.20},
                        "size_payload": {"font_size": 18},
                        "resize_mode": "reddit_font",
                    }
                }
            },
        },
    }
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.show()

    reddit = _ConstrainedOverlayWidget(display, overlay_name="reddit", font_size=18)
    display.reddit_widget = reddit
    qtbot.addWidget(reddit)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    manager.apply_saved_layouts_to_display()

    assert reddit._apply_runtime_content_height_in_custom_layout(260) is True  # type: ignore[attr-defined]

    custom_rect = getattr(reddit, "_custom_layout_local_rect", None)
    assert isinstance(custom_rect, QRect)
    assert custom_rect.width() == 420
    assert custom_rect.height() == 260
    assert reddit.geometry() == custom_rect

    payload = next(iter(settings_stub.get_widgets_map()["custom_layout"]["displays"].values()))["reddit"]
    assert payload["rect"]["width"] == pytest.approx(0.42)
    assert payload["rect"]["height"] == pytest.approx(260 / 700)


def test_custom_layout_manager_persists_runtime_vertical_shrink_for_gmail_custom_rect(qtbot):
    _reset_custom_layout_manager_state()
    screen = _FakeScreen("Display-A", QRect(0, 0, 1000, 700))
    signature = get_screen_signature(screen)
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "gmail": {"position": "Custom", "monitor": "1"},
        "custom_layout": {
            "version": 1,
            "displays": {
                signature: {
                    "gmail": {
                        "rect": {"x": 0.12, "y": 0.16, "width": 0.44, "height": 0.40},
                        "size_payload": {"font_size": 13},
                        "resize_mode": "gmail_font",
                    }
                }
            },
        },
    }
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.show()

    gmail = _ConstrainedOverlayWidget(display, overlay_name="gmail", font_size=13)
    display.gmail_widget = gmail
    qtbot.addWidget(gmail)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    manager.apply_saved_layouts_to_display()

    assert gmail._apply_runtime_content_height_in_custom_layout(180) is True  # type: ignore[attr-defined]

    custom_rect = getattr(gmail, "_custom_layout_local_rect", None)
    assert isinstance(custom_rect, QRect)
    assert custom_rect.width() == 440
    assert custom_rect.height() == 180
    assert gmail.geometry() == custom_rect

    payload = next(iter(settings_stub.get_widgets_map()["custom_layout"]["displays"].values()))["gmail"]
    assert payload["rect"]["width"] == pytest.approx(0.44)
    assert payload["rect"]["height"] == pytest.approx(180 / 700)


def test_custom_layout_manager_persists_runtime_vertical_resize_for_reddit2_without_touching_reddit1(qtbot):
    _reset_custom_layout_manager_state()
    screen = _FakeScreen("Display-A", QRect(0, 0, 1000, 700))
    signature = get_screen_signature(screen)
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "reddit": {"position": "Custom", "monitor": "1"},
        "reddit2": {"position": "Custom", "monitor": "1"},
        "custom_layout": {
            "version": 1,
            "displays": {
                signature: {
                    "reddit": {
                        "rect": {"x": 0.10, "y": 0.14, "width": 0.42, "height": 0.28},
                        "size_payload": {"font_size": 18},
                        "resize_mode": "reddit_font",
                    },
                    "reddit2": {
                        "rect": {"x": 0.55, "y": 0.16, "width": 0.42, "height": 0.24},
                        "size_payload": {"font_size": 18},
                        "resize_mode": "reddit_font",
                    },
                }
            },
        },
    }
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.show()

    reddit = _ConstrainedOverlayWidget(display, overlay_name="reddit", font_size=18)
    reddit2 = _ConstrainedOverlayWidget(display, overlay_name="reddit2", font_size=18)
    display.reddit_widget = reddit
    display.reddit2_widget = reddit2
    qtbot.addWidget(reddit)
    qtbot.addWidget(reddit2)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    manager.apply_saved_layouts_to_display()

    assert reddit2._apply_runtime_content_height_in_custom_layout(210) is True  # type: ignore[attr-defined]

    displays_payload = next(iter(settings_stub.get_widgets_map()["custom_layout"]["displays"].values()))
    assert displays_payload["reddit"]["rect"]["height"] == pytest.approx(0.28)
    assert displays_payload["reddit2"]["rect"]["height"] == pytest.approx(210 / 700)


def test_custom_layout_manager_visualizer_shell_uses_maximum_envelope(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"spotify_visualizer": {"position": "Custom", "monitor": "1"}}
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
    assert state.baseline_global_rect.width() == 320
    assert state.baseline_global_rect.height() == 280
    assert state.shell._snapshot.size() == QSize(320, 280)


def test_custom_layout_manager_visualizer_shell_qol_preview_only_grows_height(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"spotify_visualizer": {"position": "Custom", "monitor": "1"}}
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()

    media = _EditableTestWidget(display, font_size=14)
    media.setGeometry(20, 40, 450, 180)
    display.media_widget = media
    qtbot.addWidget(media)

    visualizer = _VisualizerLikeTestWidget(display)
    visualizer._anchor_media = media
    visualizer._custom_layout_local_rect = QRect(70, 360, 300, 160)
    display.spotify_visualizer_widget = visualizer
    qtbot.addWidget(visualizer)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    state = manager._shell_states["spotify_visualizer"]
    assert display.mapFromGlobal(state.baseline_global_rect.topLeft()) == QPoint(70, 360)
    assert display.mapFromGlobal(state.current_global_rect.topLeft()) == QPoint(70, 360)
    assert state.baseline_global_rect.size() == QSize(300, 280)
    assert state.current_global_rect.size() == QSize(300, 280)
    assert state.shell._snapshot.size() == QSize(300, 280)


def test_custom_layout_manager_visualizer_shell_prefers_committed_custom_rect_over_stale_live_geometry(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"spotify_visualizer": {"position": "Custom", "monitor": "1"}}
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()

    media = _EditableTestWidget(display, font_size=14)
    media.setGeometry(20, 40, 450, 180)
    display.media_widget = media
    qtbot.addWidget(media)

    visualizer = _VisualizerLikeTestWidget(display)
    visualizer._anchor_media = media
    visualizer._custom_layout_visualizer_scale_payload = {
        "width_scale": 0.868,
        "height_scale": 0.868,
    }
    visualizer._custom_layout_local_rect = QRect(12, 252, 521, 347)
    visualizer.setGeometry(12, 252, 391, 347)
    display.spotify_visualizer_widget = visualizer
    qtbot.addWidget(visualizer)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    state = manager._shell_states["spotify_visualizer"]
    assert display.mapFromGlobal(state.baseline_global_rect.topLeft()) == QPoint(12, 252)
    assert display.mapFromGlobal(state.current_global_rect.topLeft()) == QPoint(12, 252)
    assert state.baseline_global_rect.size() == QSize(521, 347)
    assert state.current_global_rect.size() == QSize(521, 347)
    assert state.baseline_size_payload == {"width": 521, "height": 347}
    assert state.shell._snapshot.size() == QSize(521, 347)


def test_custom_layout_manager_saves_visualizer_absolute_rect_payload(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"spotify_visualizer": {"position": "Custom", "monitor": "1"}}
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
    state.current_size_payload = {"width": 448, "height": 224}
    state.resize_scale = 1.2

    assert manager.save_session() is True
    payload = next(iter(settings_stub.get_widgets_map()["custom_layout"]["displays"].values()))["spotify_visualizer"]
    assert payload["size_payload"] == {"width": 448, "height": 224}


def test_custom_layout_manager_visualizer_uniform_resize_uses_committed_rect_baseline(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {"spotify_visualizer": {"position": "Custom", "monitor": "1"}}
    display = _DisplayStub(settings_stub)
    qtbot.addWidget(display)
    display.show()

    media = _EditableTestWidget(display, font_size=14)
    media.setGeometry(20, 40, 486, 232)
    display.media_widget = media
    qtbot.addWidget(media)

    visualizer = _VisualizerLikeTestWidget(display)
    visualizer._anchor_media = media
    visualizer._vis_mode_str = "spectrum"
    visualizer._custom_layout_local_rect = QRect(56, 900, 372, 276)
    visualizer.setGeometry(56, 900, 372, 276)
    display.spotify_visualizer_widget = visualizer
    qtbot.addWidget(visualizer)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    state = manager._shell_states["spotify_visualizer"]
    assert state.baseline_size_payload == {"width": 372, "height": 276}

    scaled = manager._scaled_rect_from_top_center(
        state,
        anchor_x=state.current_global_rect.center().x(),
        top_y=state.current_global_rect.top(),
        next_scale=1.1024,
        fallback_rect=state.current_global_rect,
    )

    assert scaled.size() == QSize(410, 304)


def test_custom_layout_manager_visualizer_legacy_scale_payload_rebaselines_to_committed_rect(qtbot):
    _reset_custom_layout_manager_state()
    screen = _FakeScreen("A", QRect(0, 0, 1600, 1200))
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "spotify_visualizer": {"position": "Custom", "monitor": "1"},
        "custom_layout": {
            "version": 1,
            "displays": {
                get_screen_signature(screen): {
                    "spotify_visualizer": {
                        "rect": {"x": 0.035, "y": 0.75, "width": 0.335, "height": 0.23},
                        "size_payload": {"width_scale": 1.1024, "height_scale": 1.1024},
                        "resize_mode": "visualizer_rect",
                    }
                }
            },
        },
    }
    display = _DisplayStub(settings_stub, screen=screen)
    qtbot.addWidget(display)
    display.show()

    media = _EditableTestWidget(display, font_size=14)
    media.setGeometry(20, 40, 486, 232)
    display.media_widget = media
    qtbot.addWidget(media)

    visualizer = _VisualizerLikeTestWidget(display)
    visualizer._anchor_media = media
    display.spotify_visualizer_widget = visualizer
    qtbot.addWidget(visualizer)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    manager.apply_saved_layouts_to_display()

    assert getattr(visualizer, "_custom_layout_local_rect", None) == QRect(56, 900, 536, 276)
    assert visualizer.geometry() == QRect(56, 900, 536, 276)

    assert manager.start_session() is True
    state = manager._shell_states["spotify_visualizer"]
    assert state.baseline_size_payload == {"width": 536, "height": 276}


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


def test_custom_layout_manager_repairs_visualizer_monitor_from_rect_owner_on_save(qtbot, monkeypatch):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "media": {"position": "Bottom Left", "monitor": "2"},
        "spotify_visualizer": {"enabled": True, "position": "Custom", "monitor": "2"},
    }
    screen_a = _FakeScreen("Display-A", QRect(0, 0, 800, 600))
    screen_b = _FakeScreen("Display-B", QRect(800, 0, 800, 600))
    display_a = _DisplayStub(settings_stub, screen=screen_a, screen_index=0)
    display_b = _DisplayStub(settings_stub, screen=screen_b, screen_index=1)
    qtbot.addWidget(display_a)
    qtbot.addWidget(display_b)
    display_a.show()
    display_b.show()

    visualizer = _VisualizerLikeTestWidget(display_a)
    visualizer.setGeometry(70, 240, 420, 280)
    display_a.spotify_visualizer_widget = visualizer
    qtbot.addWidget(visualizer)

    manager_a = CustomLayoutManager(display_a)
    _attach_manager(display_a, manager_a)

    class _CoordinatorStub:
        def get_all_instances(self):
            return [display_a, display_b]

    monkeypatch.setattr("rendering.custom_layout_manager.get_coordinator", lambda: _CoordinatorStub())

    assert manager_a.start_session() is True
    state = manager_a._shell_states["spotify_visualizer"]
    assert state.current_monitor_value == "2"
    assert state.current_screen is screen_a

    assert manager_a.save_session() is True
    widgets_map = settings_stub.get_widgets_map()
    assert widgets_map["spotify_visualizer"]["position"] == "Custom"
    assert widgets_map["spotify_visualizer"]["monitor"] == "1"
    displays = widgets_map["custom_layout"]["displays"]
    assert "spotify_visualizer" in displays[get_screen_signature(screen_a)]
    assert "spotify_visualizer" not in displays.get(get_screen_signature(screen_b), {})


def test_custom_layout_manager_promotes_visualizer_from_all_follow_media_to_numbered_custom_slot(qtbot):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "media": {"position": "Bottom Left", "monitor": "ALL"},
        "spotify_visualizer": {"enabled": True, "monitor": "ALL"},
    }
    display = _DisplayStub(settings_stub, screen_index=0)
    qtbot.addWidget(display)
    display.show()

    visualizer = _VisualizerLikeTestWidget(display)
    display.spotify_visualizer_widget = visualizer
    qtbot.addWidget(visualizer)

    manager = CustomLayoutManager(display)
    _attach_manager(display, manager)
    assert manager.start_session() is True

    state = manager._shell_states["spotify_visualizer"]
    assert state.current_monitor_value == "ALL"

    assert manager.save_session() is True
    widgets_map = settings_stub.get_widgets_map()
    assert widgets_map["spotify_visualizer"]["position"] == "Custom"
    assert widgets_map["spotify_visualizer"]["monitor"] == "1"


def test_custom_layout_manager_does_not_persist_visualizer_custom_all_with_multiple_survivors(qtbot, monkeypatch):
    _reset_custom_layout_manager_state()
    settings_stub = _SettingsStub()
    settings_stub._widgets_map = {
        "media": {"position": "Bottom Left", "monitor": "ALL"},
        "spotify_visualizer": {"enabled": True, "monitor": "ALL"},
    }

    screen_a = _FakeScreen("Display-A", QRect(0, 0, 800, 600))
    screen_b = _FakeScreen("Display-B", QRect(800, 0, 800, 600))
    display_a = _DisplayStub(settings_stub, screen=screen_a, screen_index=0)
    display_b = _DisplayStub(settings_stub, screen=screen_b, screen_index=1)
    qtbot.addWidget(display_a)
    qtbot.addWidget(display_b)
    display_a.show()
    display_b.show()

    vis_a = _VisualizerLikeTestWidget(display_a)
    vis_b = _VisualizerLikeTestWidget(display_b)
    display_a.spotify_visualizer_widget = vis_a
    display_b.spotify_visualizer_widget = vis_b
    qtbot.addWidget(vis_a)
    qtbot.addWidget(vis_b)

    manager_a = CustomLayoutManager(display_a)
    manager_b = CustomLayoutManager(display_b)
    _attach_manager(display_a, manager_a)
    _attach_manager(display_b, manager_b)

    class _CoordinatorStub:
        def get_all_instances(self):
            return [display_a, display_b]

    monkeypatch.setattr("rendering.custom_layout_manager.get_coordinator", lambda: _CoordinatorStub())

    assert manager_a.start_session() is True
    assert manager_a.save_session() is True

    widgets_map = settings_stub.get_widgets_map()
    assert widgets_map["spotify_visualizer"].get("position", "Follow Media") != "Custom"
    assert widgets_map["spotify_visualizer"].get("monitor", "ALL") == "ALL"
    displays = widgets_map.get("custom_layout", {}).get("displays", {})
    for layouts in displays.values():
        assert "spotify_visualizer" not in layouts


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

    assert not_snapped == proposal
    assert clock.isVisible() is False
