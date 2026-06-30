"""Tests for settings dialog."""
import inspect
import json
import sys

import pytest
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt
import ui.settings_dialog as settings_dialog_module
from ui.settings_dialog import SettingsDialog, CustomTitleBar, TabButton, ResetDefaultsDialog
from core.settings.settings_manager import SettingsManager
from core.animation import AnimationManager
from core.visualizer_preset_manifest import load_curated_visualizer_preset_manifest


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
    """Test dialog has all tab buttons."""
    dialog = SettingsDialog(settings_manager, animation_manager)
    
    assert hasattr(dialog, 'sources_tab_btn')
    assert hasattr(dialog, 'display_tab_btn')
    assert hasattr(dialog, 'transitions_tab_btn')
    assert hasattr(dialog, 'widgets_tab_btn')
    assert hasattr(dialog, 'about_tab_btn')

    expected = 7 if "presets" in dialog._tab_keys else 6
    assert len(dialog.tab_buttons) == expected


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
            settings_dialog_module.QTimer,
            "singleShot",
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
            settings_dialog_module.QTimer,
            "singleShot",
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


def test_settings_dialog_restores_persisted_top_level_tab(qapp, settings_manager, animation_manager):
    """Persisted top-level tab selection should remain authoritative."""
    settings_manager.set('ui.last_tab_index', 3)

    dialog = SettingsDialog(settings_manager, animation_manager)

    assert dialog._initial_tab_index == 3
    assert dialog.content_stack.currentIndex() == 3
    assert dialog.widgets_tab_btn.isChecked() is True


def test_settings_dialog_background_hydration_skips_widgets_tab_build():
    """Widgets tab should not be built off-screen during background hydration."""
    source = inspect.getsource(SettingsDialog._hydrate_remaining_tabs_async)
    assert 'self._tab_key_for_index(i) != "widgets"' in source


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


def test_settings_dialog_widgets_tab_accessor_keeps_visualizers_restore_hydrated(
    qapp, settings_manager, animation_manager
):
    settings_manager.set("ui.tab_state", {"widgets": {"view_state": {"subtab_id": "visualizers"}}})
    settings_manager.set("widgets", {
        "media": {"enabled": True, "position": "Bottom Right", "monitor": "ALL"},
        "spotify_visualizer": {"enabled": False, "visualizers_enabled": True, "mode": "bubble"},
        "shadows": {"enabled": True, "text_enabled": True, "header_enabled": True},
        "global": {"card_border_width_px": 3},
    })

    dialog = SettingsDialog(settings_manager, animation_manager)

    tab = dialog.widgets_tab

    assert tab.media_enabled.isChecked() is True
    assert tab.vis_enabled_checkbox.isChecked() is False
    assert tab.vis_mode_combo.currentData() == "bubble"


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


def test_about_tab_uses_replace_visualizers_button(qapp, settings_manager, animation_manager):
    """About tab should expose the shipped-preset replacement action, not reset."""
    dialog = SettingsDialog(settings_manager, animation_manager)
    dialog._switch_tab(dialog._tab_index_for_key("about"))

    assert hasattr(dialog, "replace_visualizers_btn")
    assert dialog.replace_visualizers_btn.text() == "Replace Visualizers"
    assert dialog.reset_visualizers_btn is dialog.replace_visualizers_btn


def test_settings_dialog_does_not_expose_legacy_presets_tab(
    qapp, settings_manager, animation_manager, monkeypatch
):
    monkeypatch.setenv("SRPSS_ENABLE_GENERAL_PRESETS", "1")
    dialog = SettingsDialog(settings_manager, animation_manager)

    assert "presets" not in dialog._tab_keys
    assert dialog._tab_index_for_key("presets") == -1


def test_replace_visualizers_source_root_is_script_safe(qapp, settings_manager, animation_manager):
    """Script-mode tests must never point the replacement flow at the repo tree."""
    dialog = SettingsDialog(settings_manager, animation_manager)

    root, source_kind = dialog._resolve_shipped_visualizer_source_root()
    assert root is None
    assert source_kind == "script"


def test_replace_visualizers_source_root_prefers_packaged_tree_in_frozen_build(
    qapp, settings_manager, animation_manager, tmp_path, monkeypatch
):
    dialog = SettingsDialog(settings_manager, animation_manager)
    packaged_root = tmp_path / "packaged" / "visualizer_modes"
    active_root = tmp_path / "ProgramData" / "SRPSS" / "presets" / "visualizer_modes"
    packaged_root.mkdir(parents=True)
    active_root.mkdir(parents=True)

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr("builtins.__compiled__", False, raising=False)
    monkeypatch.setattr(
        "core.settings.visualizer_presets.get_packaged_visualizer_presets_dir",
        lambda mode=None: packaged_root if mode is None else packaged_root / str(mode),
    )
    monkeypatch.setattr(
        "core.settings.visualizer_presets.get_visualizer_presets_dir",
        lambda mode=None: active_root if mode is None else active_root / str(mode),
    )

    root, source_kind = dialog._resolve_shipped_visualizer_source_root()

    assert root == packaged_root
    assert source_kind == "packaged"


def test_replace_visualizers_refreshes_target_manifest_with_reconciled_entries(
    qapp, settings_manager, animation_manager, tmp_path, monkeypatch
):
    dialog = SettingsDialog(settings_manager, animation_manager)
    source_root = tmp_path / "source" / "visualizer_modes"
    target_root = tmp_path / "target" / "visualizer_modes"
    source_mode = source_root / "blob"
    source_mode.mkdir(parents=True)
    (source_mode / "preset_1_alpha.json").write_text(
        json.dumps({"name": "Preset 1 (Alpha)", "preset_index": 0}),
        encoding="utf-8",
    )
    (source_mode / "preset_2_beta.json").write_text(
        json.dumps({"name": "Preset 2 (Beta)", "preset_index": 1}),
        encoding="utf-8",
    )
    (source_root.parent / "visualizer_modes_manifest.json").write_text(
        '{"managed_curated_files":["blob/preset_1_alpha.json"]}',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        dialog,
        "_resolve_shipped_visualizer_source_root",
        lambda: (source_root, "programdata"),
    )
    monkeypatch.setattr(
        "core.settings.visualizer_presets.get_visualizer_presets_dir",
        lambda mode=None: target_root if mode is None else target_root / str(mode),
    )
    monkeypatch.setattr("core.settings.visualizer_presets.reload_presets", lambda mode=None: None)

    written = dialog._replace_visualizer_presets_from_shipped()

    assert written == 2
    assert (target_root / "blob" / "preset_1_alpha.json").exists()
    assert (target_root / "blob" / "preset_2_beta.json").exists()
    assert load_curated_visualizer_preset_manifest(target_root) == {
        "blob/preset_1_alpha.json",
        "blob/preset_2_beta.json",
    }
