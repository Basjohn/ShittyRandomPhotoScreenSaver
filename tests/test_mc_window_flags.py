import pytest


@pytest.mark.qt
def test_mc_window_uses_tool_flag(qt_app, qtbot, settings_manager, monkeypatch):
    """Manual Controller build must stay off taskbar via Qt.Tool."""

    monkeypatch.setattr("sys.argv", ["SRPSS_Media_Center.exe"])

    from rendering.display_widget import DisplayWidget, MC_USE_SPLASH_FLAGS

    # MC build now uses splash-style flags (MC_USE_SPLASH_FLAGS=True).
    assert MC_USE_SPLASH_FLAGS is True, "Splash flags should be enabled for MC build"

    widget = DisplayWidget(screen_index=0, display_mode=None, settings_manager=settings_manager)
    qtbot.addWidget(widget)
    widget.resize(320, 200)
    widget.show()
    qt_app.processEvents()

    # With MC_USE_SPLASH_FLAGS=True, MC build uses splash-style flags
    assert getattr(widget, "_mc_window_flag_mode", None) in ("splash", "tool")


@pytest.mark.qt
def test_main_build_does_not_use_tool_flag(qt_app, qtbot, settings_manager, monkeypatch):
    """Normal build must not inherit MC's tool-window behavior."""

    monkeypatch.setattr("sys.argv", ["SRPSS.exe"])

    from rendering.display_widget import DisplayWidget

    widget = DisplayWidget(screen_index=0, display_mode=None, settings_manager=settings_manager)
    qtbot.addWidget(widget)
    widget.resize(320, 200)
    widget.show()
    qt_app.processEvents()

    assert getattr(widget, "_mc_window_flag_mode", None) is None
