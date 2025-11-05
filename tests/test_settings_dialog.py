"""Tests for settings dialog."""
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from ui.settings_dialog import SettingsDialog, CustomTitleBar, TabButton
from core.settings.settings_manager import SettingsManager
from core.animation import AnimationManager


@pytest.fixture
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def settings_manager():
    """Create settings manager."""
    return SettingsManager()


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
    assert dialog.minimumSize().width() == 900
    assert dialog.minimumSize().height() == 600


def test_settings_dialog_has_title_bar(qapp, settings_manager, animation_manager):
    """Test dialog has custom title bar."""
    dialog = SettingsDialog(settings_manager, animation_manager)
    
    assert hasattr(dialog, 'title_bar')
    assert isinstance(dialog.title_bar, CustomTitleBar)


def test_settings_dialog_has_tabs(qapp, settings_manager, animation_manager):
    """Test dialog has all tab buttons."""
    dialog = SettingsDialog(settings_manager, animation_manager)
    
    assert hasattr(dialog, 'sources_tab_btn')
    assert hasattr(dialog, 'transitions_tab_btn')
    assert hasattr(dialog, 'widgets_tab_btn')
    assert hasattr(dialog, 'about_tab_btn')
    
    assert len(dialog.tab_buttons) == 4


def test_settings_dialog_has_content_stack(qapp, settings_manager, animation_manager):
    """Test dialog has stacked widget for content."""
    dialog = SettingsDialog(settings_manager, animation_manager)
    
    assert hasattr(dialog, 'content_stack')
    assert dialog.content_stack.count() == 4


def test_settings_dialog_default_tab(qapp, settings_manager, animation_manager):
    """Test dialog shows sources tab by default."""
    dialog = SettingsDialog(settings_manager, animation_manager)
    
    assert dialog.sources_tab_btn.isChecked() is True
    assert dialog.content_stack.currentIndex() == 0


def test_settings_dialog_tab_switching(qapp, settings_manager, animation_manager):
    """Test tab switching functionality."""
    dialog = SettingsDialog(settings_manager, animation_manager)
    
    # Switch to transitions tab
    dialog._switch_tab(1)
    assert dialog.transitions_tab_btn.isChecked() is True
    assert dialog.sources_tab_btn.isChecked() is False
    
    # Switch to widgets tab
    dialog._switch_tab(2)
    assert dialog.widgets_tab_btn.isChecked() is True
    assert dialog.transitions_tab_btn.isChecked() is False
    
    # Switch to about tab
    dialog._switch_tab(3)
    assert dialog.about_tab_btn.isChecked() is True
    assert dialog.widgets_tab_btn.isChecked() is False


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


def test_settings_dialog_has_drop_shadow(qapp, settings_manager, animation_manager):
    """Test dialog has drop shadow effect."""
    dialog = SettingsDialog(settings_manager, animation_manager)
    
    effect = dialog.graphicsEffect()
    assert effect is not None


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
