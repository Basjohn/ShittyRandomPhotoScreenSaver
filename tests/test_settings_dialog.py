"""Tests for settings dialog."""
import inspect
import json
from pathlib import Path

import pytest
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import Shiboken
import ui.settings_dialog as settings_dialog_module
from ui.settings_dialog import SettingsDialog, CustomTitleBar, TabButton, ResetDefaultsDialog
from core.settings.settings_manager import SettingsManager
from core.settings.capability_activation import set_widget_family_activated
from core.animation import AnimationManager
from engine.runtime_destruction import RuntimeDestructionBarrier


@pytest.fixture
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def settings_manager(tmp_path):
    """Create isolated settings manager that won't migrate from production QSettings."""
    return SettingsManager(application="test_dialog", storage_base_dir=tmp_path)


@pytest.fixture
def animation_manager():
    """Create animation manager."""
    return AnimationManager()


def test_custom_title_bar_creation(qapp):
    """Test custom title bar creation."""
    title_bar = CustomTitleBar()
    
    assert title_bar is not None
    assert title_bar.height() == 40
    assert hasattr(title_bar, 'title_label')
    assert hasattr(title_bar, 'minimize_btn')
    assert hasattr(title_bar, 'maximize_btn')
    assert hasattr(title_bar, 'close_btn')


def test_custom_title_bar_signals(qapp, qtbot):
    """Test custom title bar signals."""
    title_bar = CustomTitleBar()
    
    close_clicks = []
    minimize_clicks = []
    maximize_clicks = []
    
    title_bar.close_clicked.connect(lambda: close_clicks.append(True))
    title_bar.minimize_clicked.connect(lambda: minimize_clicks.append(True))
    title_bar.maximize_clicked.connect(lambda: maximize_clicks.append(True))
    
    # Simulate clicks
    title_bar.close_btn.click()
    title_bar.minimize_btn.click()
    title_bar.maximize_btn.click()
    
    assert len(close_clicks) == 1
    assert len(minimize_clicks) == 1
    assert len(maximize_clicks) == 1


def test_tab_button_creation(qapp):
    """Test tab button creation."""
    button = TabButton("Test Tab", "📁")
    
    assert button is not None
    assert "Test Tab" in button.text()
    assert button.isCheckable() is True


def test_settings_dialog_creation(qapp, settings_manager, animation_manager):
    """Test settings dialog creation."""
    dialog = SettingsDialog(settings_manager, animation_manager)
    
    assert dialog is not None
    assert dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert dialog.minimumSize().width() == 1280
    assert dialog.minimumSize().height() == 700


@pytest.mark.qt
def test_real_settings_dialog_delete_on_close_is_observed_before_modal_exec(
    qapp,
    qtbot,
    settings_manager,
    animation_manager,
):
    class _Engine:
        _terminal_shutdown_requested = False
        _pending_runtime_destruction_barrier = None

    engine = _Engine()
    dialog = SettingsDialog(settings_manager, animation_manager)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    signal_order = []
    barrier = RuntimeDestructionBarrier(
        engine,
        reason="settings_dialog_close",
        retiring_generation=None,
    )
    barrier.watch_qobject(dialog, label="SettingsDialog")
    dialog.destroyed.connect(lambda *_args: signal_order.append("destroyed"))
    barrier.seal()

    signal_order.append("exec")
    QTimer.singleShot(0, dialog.accept)
    dialog.exec()
    signal_order.append("returned")

    assert signal_order == ["exec", "destroyed", "returned"]
    assert Shiboken.isValid(dialog) is False
    qtbot.waitUntil(lambda: barrier.is_complete, timeout=2000)

    animation_manager.cleanup()


def test_reset_defaults_toast_owns_and_stops_auto_close_timer(qapp):
    """The reset toast should own its timeout and stop it on early close."""
    parent = QWidget()
    toast = ResetDefaultsDialog(parent)
    try:
        timer = toast._auto_close_timer
        assert timer.parent() is toast
        assert timer.isSingleShot() is True
        assert timer.isActive() is True

        toast.reject()

        assert timer.isActive() is False
    finally:
        toast.deleteLater()
        parent.deleteLater()


def test_settings_dialog_has_title_bar(qapp, settings_manager, animation_manager):
    """Test dialog has custom title bar."""
    dialog = SettingsDialog(settings_manager, animation_manager)
    
    assert hasattr(dialog, 'title_bar')
    assert isinstance(dialog.title_bar, CustomTitleBar)


def test_settings_dialog_has_tabs(qapp, settings_manager, animation_manager):
    """Dialog exposes the current top-level tab set, including Visualizers."""
    dialog = SettingsDialog(settings_manager, animation_manager)

    # V7 promoted Visualizers to its own top-level tab, sitting after Widgets.
    expected_keys = [
        "sources",
        "display",
        "transitions",
        "widgets",
        "visualizers",
        "accessibility",
        "themes",
        "about",
    ]
    assert dialog._tab_keys == expected_keys

    for key in expected_keys:
        assert hasattr(dialog, f"{key}_tab_btn"), key

    # One button per key, in key order; the count follows _tab_keys rather than a
    # hard-coded number so adding/removing a tab updates in one place.
    assert len(dialog.tab_buttons) == len(dialog._tab_keys)
    assert dialog.tab_buttons == [
        dialog._tab_button_by_key[key] for key in dialog._tab_keys
    ]




def test_visualizers_navigation_mirrors_media_and_family_capabilities(
    qapp, settings_manager, animation_manager
):
    dialog = SettingsDialog(settings_manager, animation_manager)
    button = dialog.visualizers_tab_btn

    assert button.isEnabled()
    enabled_text_style = button._tab_text_label.styleSheet()

    widgets = settings_manager.get("widgets", {})
    set_widget_family_activated(widgets, "media", True)
    set_widget_family_activated(widgets, "visualizers", False)
    settings_manager.set("widgets", widgets)
    dialog._refresh_visualizers_tab_eligibility()
    assert not button.isEnabled()
    assert button.toolTip() == "Enable Visualizers In Widgets"
    assert button._tab_text_label.styleSheet() != enabled_text_style

    widgets = settings_manager.get("widgets", {})
    set_widget_family_activated(widgets, "visualizers", True)
    set_widget_family_activated(widgets, "media", False)
    settings_manager.set("widgets", widgets)
    dialog._refresh_visualizers_tab_eligibility()
    assert not button.isEnabled()
    assert button.toolTip() == "Enable Media In Widgets"

    widgets = settings_manager.get("widgets", {})
    set_widget_family_activated(widgets, "media", True)
    set_widget_family_activated(widgets, "visualizers", True)
    settings_manager.set("widgets", widgets)
    dialog._refresh_visualizers_tab_eligibility()
    assert button.isEnabled()
    assert button.toolTip() == ""


def test_settings_dialog_has_content_stack(qapp, settings_manager, animation_manager):
    """Test dialog has stacked widget for content."""
    dialog = SettingsDialog(settings_manager, animation_manager)

    assert hasattr(dialog, 'content_stack')
    assert dialog.content_stack.count() == len(dialog._tab_keys)


def test_settings_dialog_default_tab(qapp, settings_manager, animation_manager):
    """Test dialog shows sources tab by default."""
    dialog = SettingsDialog(settings_manager, animation_manager)
    
    assert dialog.sources_tab_btn.isChecked() is True
    assert dialog.content_stack.currentIndex() == 0


def test_settings_dialog_tab_switching(qapp, settings_manager, animation_manager):
    """Test tab switching functionality."""
    dialog = SettingsDialog(settings_manager, animation_manager)

    display_idx = dialog._tab_index_for_key("display")
    transitions_idx = dialog._tab_index_for_key("transitions")
    widgets_idx = dialog._tab_index_for_key("widgets")
    accessibility_idx = dialog._tab_index_for_key("accessibility")
    about_idx = dialog._tab_index_for_key("about")

    # Switch to display tab
    dialog._switch_tab(display_idx)
    assert dialog.display_tab_btn.isChecked() is True
    assert dialog.sources_tab_btn.isChecked() is False

    # Switch to transitions tab
    dialog._switch_tab(transitions_idx)
    assert dialog.transitions_tab_btn.isChecked() is True
    assert dialog.display_tab_btn.isChecked() is False

    # Switch to widgets tab
    dialog._switch_tab(widgets_idx)
    assert dialog.widgets_tab_btn.isChecked() is True
    assert dialog.transitions_tab_btn.isChecked() is False

    # Switch to accessibility tab
    dialog._switch_tab(accessibility_idx)
    assert dialog.tab_buttons[accessibility_idx].isChecked() is True
    assert dialog.widgets_tab_btn.isChecked() is False

    # Optional presets tab
    presets_idx = dialog._tab_index_for_key("presets")
    if presets_idx >= 0:
        dialog._switch_tab(presets_idx)
        assert dialog.tab_buttons[presets_idx].isChecked() is True
        assert dialog.tab_buttons[accessibility_idx].isChecked() is False

    # Switch to about tab
    dialog._switch_tab(about_idx)
    assert dialog.about_tab_btn.isChecked() is True
    if presets_idx >= 0:
        assert dialog.tab_buttons[presets_idx].isChecked() is False


def test_settings_dialog_has_size_grip(qapp, settings_manager, animation_manager):
    """Test dialog has size grip for resizing."""
    dialog = SettingsDialog(settings_manager, animation_manager)
    
    assert hasattr(dialog, 'size_grip')
    assert dialog.size_grip is not None


def test_settings_dialog_toggle_maximize(qapp, settings_manager, animation_manager):
    """Test maximize toggle functionality."""
    dialog = SettingsDialog(settings_manager, animation_manager)
    
    initial_state = dialog._is_maximized
    dialog._toggle_maximize()
    assert dialog._is_maximized != initial_state
    
    dialog._toggle_maximize()
    assert dialog._is_maximized == initial_state


def test_settings_dialog_show_does_not_install_global_shadow_filter():
    """showEvent should not opt into the app-wide shadow refresh filter."""
    source = inspect.getsource(SettingsDialog.showEvent)
    assert "_install_shadow_event_filter()" not in source


def test_settings_dialog_show_does_not_schedule_shell_shadow_refresh():
    """showEvent should not trigger shell-shadow refresh churn."""
    source = inspect.getsource(SettingsDialog.showEvent)
    assert "_schedule_shell_shadow_refresh()" not in source


def test_settings_dialog_background_hydration_delay_respects_closing(
    qapp,
    settings_manager,
    animation_manager,
    monkeypatch,
):
    """Delayed settings hydration must not wake hidden tab work after close."""
    dialog = SettingsDialog(settings_manager, animation_manager)
    callbacks = []
    scheduled_builds = []
    try:
        monkeypatch.setattr(
            settings_dialog_module.ThreadManager,
            "single_shot",
            staticmethod(lambda _delay, callback: callbacks.append(callback)),
        )
        monkeypatch.setattr(
            dialog,
            "_schedule_next_background_build",
            lambda: scheduled_builds.append(True),
        )
        dialog._background_tab_queue = [1]

        dialog._start_background_tab_hydration()
        assert len(callbacks) == 1

        dialog._closing = True
        callbacks[0]()

        assert scheduled_builds == []
    finally:
        dialog.deleteLater()


def test_settings_dialog_scheduled_background_build_respects_closing(
    qapp,
    settings_manager,
    animation_manager,
    monkeypatch,
):
    """Queued hidden-tab builds should clear instead of constructing after close."""
    dialog = SettingsDialog(settings_manager, animation_manager)
    callbacks = []
    built = []
    try:
        monkeypatch.setattr(
            settings_dialog_module.ThreadManager,
            "single_shot",
            staticmethod(lambda _delay, callback: callbacks.append(callback)),
        )
        monkeypatch.setattr(dialog, "_ensure_tab_built", lambda index: built.append(index))
        dialog._background_tab_queue = [1]

        dialog._schedule_next_background_build()
        assert len(callbacks) == 1

        dialog._closing = True
        callbacks[0]()

        assert built == []
        assert dialog._background_tab_queue == []
        assert dialog._background_build_scheduled is False
    finally:
        dialog.deleteLater()


def test_settings_dialog_runtime_single_shot_wraps_bound_method_with_owner(
    qapp,
    settings_manager,
    animation_manager,
    monkeypatch,
):
    """Bound callbacks retain dialog lifecycle ownership without attribute errors."""
    dialog = SettingsDialog(settings_manager, animation_manager)
    scheduled = []
    calls = []

    class _Receiver:
        def callback(self):
            calls.append(True)

    receiver = _Receiver()
    try:
        monkeypatch.setattr(
            settings_dialog_module.ThreadManager,
            "single_shot",
            staticmethod(lambda delay, callback: scheduled.append((delay, callback))),
        )

        dialog._schedule_runtime_single_shot(7, receiver.callback)

        assert len(scheduled) == 1
        delay, callback = scheduled[0]
        assert delay == 7
        assert getattr(callback, "_srpss_timer_owner", None) is dialog
        assert (
            getattr(callback, "_srpss_runtime_generation", None)
            == dialog._runtime_generation
        )
        callback()
        assert calls == [True]
    finally:
        dialog.deleteLater()


def test_settings_dialog_move_does_not_schedule_shell_shadow_refresh():
    """moveEvent should not trigger shell-shadow refresh churn."""
    source = inspect.getsource(SettingsDialog.moveEvent)
    assert "_schedule_shell_shadow_refresh()" not in source


def test_settings_dialog_switch_tab_does_not_schedule_shell_shadow_refresh():
    """Tab switches should not rebuild the shell shadow."""
    source = inspect.getsource(SettingsDialog._switch_tab)
    assert "_schedule_shell_shadow_refresh()" not in source


def test_settings_dialog_background_hydration_defers_until_show_and_uses_delays():
    """Remaining tab hydration should not compete with first dialog interaction."""
    hydrate_source = inspect.getsource(SettingsDialog._hydrate_remaining_tabs_async)
    start_source = inspect.getsource(SettingsDialog._start_background_tab_hydration)
    schedule_source = inspect.getsource(SettingsDialog._schedule_next_background_build)
    show_source = inspect.getsource(SettingsDialog.showEvent)

    assert "self.isVisible()" in hydrate_source
    assert "_start_background_tab_hydration()" in show_source
    assert "self._background_hydration_delay_ms" in start_source
    assert "self._background_hydration_step_delay_ms" in schedule_source
    assert "QTimer.singleShot(0, _run)" not in schedule_source


def test_settings_dialog_close_cancels_background_hydration_work():
    """Settings-close must not leave hidden tab hydration queued into runtime."""
    close_source = inspect.getsource(SettingsDialog.closeEvent)
    start_source = inspect.getsource(SettingsDialog._start_background_tab_hydration)
    schedule_source = inspect.getsource(SettingsDialog._schedule_next_background_build)

    assert "self._closing = True" in close_source
    assert "self._background_tab_queue.clear()" in close_source
    assert "if self._closing" in start_source
    assert "if self._closing" in schedule_source


def test_settings_dialog_close_flushes_after_geometry_save(
    qapp,
    settings_manager,
    animation_manager,
    monkeypatch,
):
    """A completed Settings session acknowledges geometry before durability."""
    dialog = SettingsDialog(settings_manager, animation_manager)
    order = []

    monkeypatch.setattr(dialog, "_has_image_sources", lambda: True)
    monkeypatch.setattr(dialog, "_save_geometry", lambda: order.append("geometry"))

    def _flush(*, timeout):
        order.append(("flush", timeout))
        return True

    monkeypatch.setattr(settings_manager, "flush", _flush)

    event = QCloseEvent()
    dialog.closeEvent(event)

    assert event.isAccepted() is True
    assert order == ["geometry", ("flush", 2.0)]


def test_settings_dialog_close_flushes_built_tab_before_manager_without_lazy_build(
    qapp,
    settings_manager,
    animation_manager,
    monkeypatch,
):
    """Tab-local coalesced edits must cross the close durability boundary first."""
    dialog = SettingsDialog(settings_manager, animation_manager)
    order = []

    class _BuiltTab:
        def flush_pending_changes(self):
            order.append("tab")

    dialog.visualizers_tab = _BuiltTab()
    monkeypatch.setattr(dialog, "_has_image_sources", lambda: True)
    monkeypatch.setattr(dialog, "_save_geometry", lambda: order.append("geometry"))
    monkeypatch.setattr(
        dialog,
        "_get_tab_instance",
        lambda *_args, **_kwargs: pytest.fail("close must not build dormant tabs"),
    )

    def _flush(*, timeout):
        order.append(("manager", timeout))
        return True

    monkeypatch.setattr(settings_manager, "flush", _flush)

    event = QCloseEvent()
    dialog.closeEvent(event)

    assert event.isAccepted() is True
    assert order == ["geometry", "tab", ("manager", 2.0)]


def test_visualizer_preset_import_refreshes_only_existing_top_level_owner() -> None:
    source = inspect.getsource(SettingsDialog._refresh_visualizer_import_state)
    assert "self.__dict__.get('visualizers_tab')" in source
    assert "_get_tab_instance('widgets')" not in source
    assert "load_from_settings" in source


def test_reset_defaults_reuses_built_only_reload_path() -> None:
    source = inspect.getsource(SettingsDialog._on_reset_to_defaults_clicked)
    assert "self._reload_all_tab_settings()" in source
    assert "_get_tab_instance(key)" not in source


def test_settings_dialog_restores_persisted_top_level_tab(qapp, settings_manager, animation_manager):
    """Persisted top-level tab selection should remain authoritative."""
    settings_manager.set('ui.last_tab_index', 3)

    dialog = SettingsDialog(settings_manager, animation_manager)

    assert dialog._initial_tab_index == 3
    assert dialog.content_stack.currentIndex() == 3
    assert dialog.widgets_tab_btn.isChecked() is True


def test_settings_dialog_background_hydration_skips_widgets_and_visualizers(
    qapp, settings_manager, animation_manager
):
    """Widgets and Visualizers are excluded from off-screen background hydration,
    and the Visualizers tab (once built) keeps every mode body dormant."""
    dialog = SettingsDialog(settings_manager, animation_manager)

    # The dialog is never shown in the test, so background hydration is queued but
    # not drained by timers: the queue is a deterministic view of what WOULD be
    # built off-screen. Widgets and Visualizers must not appear in it, while other
    # non-initial tabs do.
    queued_keys = {dialog._tab_key_for_index(i) for i in dialog._background_tab_queue}
    assert "widgets" not in queued_keys
    assert "visualizers" not in queued_keys
    assert {"display", "transitions", "accessibility", "themes"} <= queued_keys

    # Neither excluded tab has been constructed: their stacked-widget slots are
    # still the placeholders installed at setup.
    for key in ("widgets", "visualizers"):
        idx = dialog._tab_keys.index(key)
        assert dialog.__dict__.get(f"{key}_tab") is None
        assert dialog.content_stack.widget(idx).objectName() == f"{key}_placeholder"

    # Building the Visualizers tab on demand must not eagerly construct any mode
    # body: no per-mode preset slider exists until a mode pill is selected.
    from core.settings.visualizer_mode_registry import iter_visualizer_mode_descriptors

    vis = dialog.visualizers_tab
    assert vis is not None
    for descriptor in iter_visualizer_mode_descriptors():
        assert getattr(vis, descriptor.preset_slider_attr, None) is None


def test_settings_dialog_builds_widgets_tab_in_lazy_mode():
    """Settings dialog should opt WidgetsTab into lazy section construction."""
    source = inspect.getsource(SettingsDialog._setup_ui)
    assert "lazy_sections=True" in source
    assert 'self._tab_state_cache.get("widgets", {}).get("view_state", {})' in source


def test_settings_dialog_exposes_widgets_tab_via_lazy_accessor(qapp, settings_manager, animation_manager):
    dialog = SettingsDialog(settings_manager, animation_manager)

    tab = dialog.widgets_tab

    assert tab is not None
    assert dialog._tab_key_for_index(dialog.content_stack.currentIndex()) == "sources"


def test_settings_dialog_restores_media_on_widgets_and_visualizer_on_visualizers_tab(
    qapp, settings_manager, animation_manager
):
    """Media stays on WidgetsTab; the visualizer enable + active mode restore on
    the canonical top-level VisualizersTab owner (V7 rehost)."""
    settings_manager.set("widgets", {
        "media": {"enabled": True, "position": "Bottom Right", "monitor": "ALL"},
        "spotify_visualizer": {"enabled": False, "visualizers_enabled": True, "mode": "bubble"},
        "shadows": {"enabled": True, "text_enabled": True, "header_enabled": True},
        "global": {"card_border_width_px": 3},
    })

    dialog = SettingsDialog(settings_manager, animation_manager)

    # Media capability remains owned by WidgetsTab.
    assert dialog.widgets_tab.media_enabled.isChecked() is True

    # The Beat-Visualizer enable checkbox and the active mode now live on the
    # top-level VisualizersTab; the retired vis_mode_combo is gone, so the active
    # mode is read from the context-owned canonical id instead.
    vis = dialog.visualizers_tab
    assert vis.vis_enabled_checkbox.isChecked() is False
    assert vis._get_active_visualizer_mode() == "bubble"


def test_settings_dialog_hidden_close_skips_no_sources_popup(qapp, settings_manager, animation_manager):
    dialog = SettingsDialog(settings_manager, animation_manager)

    dialog.close()

    assert dialog.isVisible() is False


def test_settings_dialog_theme_loaded(qapp, settings_manager, animation_manager):
    """Test dialog has stylesheet applied."""
    dialog = SettingsDialog(settings_manager, animation_manager)
    
    stylesheet = dialog.styleSheet()
    assert len(stylesheet) > 0
    assert "QDialog" in stylesheet or "#customTitleBar" in stylesheet


def test_settings_dialog_tab_button_clicks(qapp, settings_manager, animation_manager, qtbot):
    """Test clicking tab buttons switches tabs."""
    dialog = SettingsDialog(settings_manager, animation_manager)
    
    # Click transitions button
    dialog.transitions_tab_btn.click()
    qtbot.wait(200)  # Wait for animation
    assert dialog.transitions_tab_btn.isChecked() is True
    
    # Click widgets button
    dialog.widgets_tab_btn.click()
    qtbot.wait(200)  # Wait for animation
    assert dialog.widgets_tab_btn.isChecked() is True


def test_about_tab_uses_visualizer_import_export_buttons(qapp, settings_manager, animation_manager):
    """About tab should expose visualizer import/export actions."""
    dialog = SettingsDialog(settings_manager, animation_manager)
    dialog._switch_tab(dialog._tab_index_for_key("about"))

    assert hasattr(dialog, "export_visualizers_btn")
    assert hasattr(dialog, "import_visualizers_btn")
    assert dialog.export_visualizers_btn.text() == "Export Visualizers"
    assert dialog.import_visualizers_btn.text() == "Import Visualizers"
    assert not hasattr(dialog, "replace_visualizers_btn")


def test_settings_dialog_does_not_expose_legacy_presets_tab(
    qapp, settings_manager, animation_manager, monkeypatch
):
    monkeypatch.setenv("SRPSS_ENABLE_GENERAL_PRESETS", "1")
    dialog = SettingsDialog(settings_manager, animation_manager)

    assert "presets" not in dialog._tab_keys
    assert dialog._tab_index_for_key("presets") == -1


def test_open_logs_folder_uses_resolved_log_dir(
    qapp, settings_manager, animation_manager, tmp_path, monkeypatch
):
    dialog = SettingsDialog(settings_manager, animation_manager)
    opened = []
    log_dir = tmp_path / "runtime_logs"

    monkeypatch.setattr(settings_dialog_module, "get_log_dir", lambda: log_dir)
    monkeypatch.setattr(
        settings_dialog_module.QDesktopServices,
        "openUrl",
        lambda url: opened.append(url) or True,
    )

    dialog._open_logs_folder()

    assert opened
    assert Path(opened[-1].toLocalFile()).resolve() == log_dir.resolve()
    assert log_dir.exists()


def test_open_settings_folder_uses_public_settings_dir(
    qapp, settings_manager, animation_manager, monkeypatch
):
    dialog = SettingsDialog(settings_manager, animation_manager)
    opened = []

    monkeypatch.setattr(
        settings_dialog_module.QDesktopServices,
        "openUrl",
        lambda url: opened.append(url) or True,
    )

    dialog._open_settings_folder()

    assert opened
    assert Path(opened[-1].toLocalFile()).resolve() == settings_manager.get_settings_dir().resolve()


def test_import_settings_reload_all_tabs_after_success(
    qapp, settings_manager, animation_manager, tmp_path, monkeypatch
):
    dialog = SettingsDialog(settings_manager, animation_manager)
    snapshot = tmp_path / "settings.sst"
    snapshot.write_text(json.dumps({"snapshot": {"ui": {"theme": "dark"}}}), encoding="utf-8")
    reloaded = []

    monkeypatch.setattr(
        settings_dialog_module.QFileDialog,
        "getOpenFileName",
        lambda *args, **kwargs: (str(snapshot), ""),
    )
    monkeypatch.setattr(dialog, "_reload_all_tab_settings", lambda: reloaded.append(True))
    monkeypatch.setattr(settings_dialog_module.StyledPopup, "show_success", lambda *args, **kwargs: None)

    dialog._on_import_settings_clicked()

    assert reloaded == [True]
