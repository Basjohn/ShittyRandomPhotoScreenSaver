"""Integration tests for widgets settings persistence.

These tests bridge WidgetsTab (UI) and DisplayWidget runtime wiring to ensure
that changes persisted via the widgets tab are reflected correctly when
DisplayWidget sets up overlay widgets, and that per-monitor routing works.
"""

import pytest

from rendering.display_widget import DisplayWidget
from rendering.display_modes import DisplayMode
from ui.tabs.widgets_tab import WidgetsTab
from widgets.clock_widget import TimeFormat, ClockPosition, ClockWidget
from widgets.weather_widget import WeatherWidget, WeatherPosition


@pytest.mark.qt
def test_widgets_tab_changes_reflected_in_display_widget(qt_app, settings_manager, qtbot, monkeypatch):
    """WidgetsTab -> settings -> DisplayWidget roundtrip for clock + weather.

    This simulates a user changing settings in the Widgets tab, then the
    screensaver restarting and DisplayWidget reading those settings to
    configure overlay widgets on screen 0.
    """
    # Create WidgetsTab bound to the shared SettingsManager
    tab = WidgetsTab(settings_manager)
    qtbot.addWidget(tab)

    # Configure clock via UI controls
    tab.clock_enabled.setChecked(True)
    tab.clock_format.setCurrentText("24 Hour")
    tab.clock_seconds.setChecked(True)
    tab.clock_position.setCurrentText("Top Right")
    tab.clock_monitor_combo.setCurrentText("1")  # primary monitor
    tab.clock_show_background.setChecked(True)
    tab.clock_bg_opacity.setValue(80)  # 80%

    # Configure weather via UI controls
    tab.weather_enabled.setChecked(True)
    tab.weather_location.setText("Johannesburg")
    tab.weather_position.setCurrentText("Top Left")
    tab.weather_monitor_combo.setCurrentText("ALL")  # show on all monitors
    tab.weather_show_background.setChecked(True)
    tab.weather_bg_opacity.setValue(80)  # 80%

    # Persist settings through the tab (canonical nested `widgets` dict)
    tab._save_settings()

    # Avoid real network/weather fetches during DisplayWidget._setup_widgets
    def _fake_weather_start(self):  # type: ignore[override]
        self._enabled = True

    monkeypatch.setattr(WeatherWidget, "start", _fake_weather_start, raising=False)

    # Simulate a restart: new DisplayWidget instance using the same settings
    widget = DisplayWidget(
        screen_index=0,
        display_mode=DisplayMode.FILL,
        settings_manager=settings_manager,
    )
    qtbot.addWidget(widget)
    widget.resize(800, 600)

    # Normally called from show_on_screen(); invoke directly here
    widget._setup_widgets()

    # Clock should reflect the settings from WidgetsTab
    assert widget.clock_widget is not None
    assert isinstance(widget.clock_widget, ClockWidget)
    assert widget.clock_widget._position == ClockPosition.TOP_RIGHT
    assert widget.clock_widget._time_format == TimeFormat.TWENTY_FOUR_HOUR
    assert widget.clock_widget._show_seconds is True
    assert widget.clock_widget._enabled is True

    # Weather should also reflect the settings from WidgetsTab on screen 0
    assert widget.weather_widget is not None
    assert widget.weather_widget._location == "JohANNESBURG".title() or widget.weather_widget._location == "Johannesburg"  # allow internal normalization
    assert widget.weather_widget._position == WeatherPosition.TOP_LEFT
    assert widget.weather_widget._enabled is True


@pytest.mark.qt
def test_display_widget_respects_widget_monitor_selection(qt_app, settings_manager, qtbot, monkeypatch):
    """Per-monitor routing: widgets appear on the configured screens only.

    This test writes the nested `widgets` config directly, then creates
    DisplayWidget instances for two screens and verifies that the primary
    clock, secondary clock, and weather widget are routed to the correct
    monitors based on their `monitor` selectors.
    """

    # Avoid timers and network work from widgets while keeping creation logic.
    def _fake_clock_start(self):  # type: ignore[override]
        self._enabled = True

    def _fake_weather_start(self):  # type: ignore[override]
        self._enabled = True

    monkeypatch.setattr(ClockWidget, "start", _fake_clock_start, raising=False)
    monkeypatch.setattr(WeatherWidget, "start", _fake_weather_start, raising=False)

    # Configure widgets with explicit per-monitor selectors.
    # Main clock on monitor 1, Clock 2 on monitor 2, weather on monitor 2.
    settings_manager.set(
        "widgets",
        {
            "clock": {
                "enabled": True,
                "monitor": "1",
                "position": "Top Right",
            },
            "clock2": {
                "enabled": True,
                "monitor": "2",
                "position": "Top Right",
            },
            "weather": {
                "enabled": True,
                "monitor": "2",
                "location": "Johannesburg",
                "position": "Bottom Left",
            },
        },
    )

    # Screen 0 (index 0 -> monitor 1)
    w0 = DisplayWidget(
        screen_index=0,
        display_mode=DisplayMode.FILL,
        settings_manager=settings_manager,
    )
    qtbot.addWidget(w0)
    w0.resize(800, 600)
    w0._setup_widgets()

    # Primary clock should be present; secondary clock and weather should not.
    assert w0.clock_widget is not None
    assert w0.clock2_widget is None
    assert w0.weather_widget is None

    # Screen 1 (index 1 -> monitor 2)
    w1 = DisplayWidget(
        screen_index=1,
        display_mode=DisplayMode.FILL,
        settings_manager=settings_manager,
    )
    qtbot.addWidget(w1)
    w1.resize(800, 600)
    w1._setup_widgets()

    # Secondary clock and weather should be present here; primary clock should not.
    assert w1.clock_widget is None
    assert w1.clock2_widget is not None
    assert isinstance(w1.clock2_widget, ClockWidget)
    assert w1.weather_widget is not None
    assert w1.weather_widget._position == WeatherPosition.BOTTOM_LEFT
    assert w1.weather_widget._location == "Johannesburg"
    assert w1.weather_widget._enabled is True
