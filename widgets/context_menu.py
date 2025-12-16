"""
Context menu for screensaver with dark glass styling.

Provides quick access to:
- Previous/Next image
- Transition selection
- Settings
- Background dimming toggle
- Hard exit mode toggle
- Exit
"""
from typing import Optional, List
from PySide6.QtWidgets import QMenu, QWidget
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction

from core.logging.logger import get_logger

logger = get_logger(__name__)

# Dark theme matching settings dialog - app-owned, no Windows accent bleed
# Uses same color palette as settings_dialog.py for consistency
MENU_STYLE = """
QMenu {
    background-color: rgba(43, 43, 43, 255);
    border: 2px solid rgba(154, 154, 154, 200);
    border-radius: 8px;
    padding: 6px 4px;
}
QMenu::item {
    background-color: transparent;
    color: #ffffff;
    padding: 8px 24px 8px 16px;
    margin: 2px 4px;
    border-radius: 4px;
    font-size: 13px;
}
QMenu::item:selected {
    background-color: rgba(62, 62, 62, 220);
}
QMenu::item:disabled {
    color: rgba(120, 120, 130, 150);
}
QMenu::separator {
    height: 1px;
    background-color: rgba(90, 90, 90, 150);
    margin: 4px 12px;
}
QMenu::indicator {
    width: 16px;
    height: 16px;
    margin-left: 6px;
    margin-right: 4px;
}
QMenu::indicator:checked {
    background-color: #ffffff;
    border: 2px solid #888888;
    border-radius: 3px;
    image: url(none);
}
QMenu::indicator:unchecked {
    background-color: rgba(30, 30, 30, 220);
    border: 2px solid #555555;
    border-radius: 3px;
}
"""

SUBMENU_STYLE = """
QMenu {
    background-color: rgba(43, 43, 43, 255);
    border: 2px solid rgba(154, 154, 154, 200);
    border-radius: 6px;
    padding: 4px 2px;
}
QMenu::item {
    background-color: transparent;
    color: #ffffff;
    padding: 6px 20px 6px 12px;
    margin: 1px 3px;
    border-radius: 3px;
    font-size: 12px;
}
QMenu::item:selected {
    background-color: rgba(62, 62, 62, 220);
}
QMenu::item:checked {
    color: #ffffff;
    font-weight: bold;
    background-color: rgba(62, 62, 62, 220);
}
QMenu::indicator {
    width: 14px;
    height: 14px;
    margin-left: 4px;
    margin-right: 2px;
}
QMenu::indicator:checked {
    background-color: #ffffff;
    border: 2px solid #888888;
    border-radius: 3px;
}
QMenu::indicator:unchecked {
    background-color: rgba(30, 30, 30, 220);
    border: 2px solid #555555;
    border-radius: 3px;
}
"""


class ScreensaverContextMenu(QMenu):
    """Dark glass themed context menu for screensaver."""
    
    # Signals for menu actions
    previous_requested = Signal()
    next_requested = Signal()
    transition_selected = Signal(str)  # transition name
    settings_requested = Signal()
    dimming_toggled = Signal(bool)  # new state
    hard_exit_toggled = Signal(bool)  # new state
    exit_requested = Signal()
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        transition_types: Optional[List[str]] = None,
        current_transition: str = "Crossfade",
        dimming_enabled: bool = False,
        hard_exit_enabled: bool = False,
    ):
        super().__init__(parent)
        
        self._transition_types = transition_types or [
            "Ripple", "Wipe", "3D Block Spins", "Diffuse", "Slide",
            "Crossfade", "Peel", "Block Puzzle Flip", "Warp Dissolve",
            "Blinds", "Crumble",
        ]
        self._current_transition = current_transition
        self._dimming_enabled = dimming_enabled
        self._hard_exit_enabled = hard_exit_enabled
        
        self.setStyleSheet(MENU_STYLE)
        try:
            self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)
        except Exception:
            pass
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        except Exception:
            pass
        try:
            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        except Exception:
            pass
        
        self._setup_menu()
        logger.debug("ScreensaverContextMenu created")
    
    def _setup_menu(self) -> None:
        """Build the menu structure."""
        # Previous Image - monochrome triangle
        prev_action = self.addAction("◂  Previous Image")
        prev_action.triggered.connect(self.previous_requested.emit)
        
        # Next Image - monochrome triangle
        next_action = self.addAction("▸  Next Image")
        next_action.triggered.connect(self.next_requested.emit)
        
        self.addSeparator()
        
        # Transition submenu - monochrome arrows
        self._transition_menu = QMenu("⟳  Change Transition", self)
        self._transition_menu.setStyleSheet(SUBMENU_STYLE)
        self._transition_actions: dict[str, QAction] = {}
        
        for trans_name in self._transition_types:
            action = self._transition_menu.addAction(trans_name)
            action.setCheckable(True)
            action.setChecked(trans_name == self._current_transition)
            action.triggered.connect(lambda checked, name=trans_name: self._on_transition_selected(name))
            self._transition_actions[trans_name] = action
        
        self.addMenu(self._transition_menu)
        
        self.addSeparator()
        
        # Settings - monochrome gear
        settings_action = self.addAction("⚙  Settings")
        settings_action.triggered.connect(self.settings_requested.emit)
        
        self.addSeparator()
        
        # Background Dimming toggle - monochrome circle
        self._dimming_action = self.addAction("◐  Background Dimming")
        self._dimming_action.setCheckable(True)
        self._dimming_action.setChecked(self._dimming_enabled)
        self._dimming_action.triggered.connect(self._on_dimming_toggled)
        
        # Hard Exit Mode toggle - monochrome lock
        self._hard_exit_action = self.addAction("⊘  Hard Exit Mode")
        self._hard_exit_action.setCheckable(True)
        self._hard_exit_action.setChecked(self._hard_exit_enabled)
        self._hard_exit_action.triggered.connect(self._on_hard_exit_toggled)
        
        self.addSeparator()
        
        # Exit - monochrome X
        exit_action = self.addAction("✕  Exit Screensaver")
        exit_action.triggered.connect(self.exit_requested.emit)
    
    def _on_transition_selected(self, name: str) -> None:
        """Handle transition selection."""
        # Update checkmarks
        for trans_name, action in self._transition_actions.items():
            action.setChecked(trans_name == name)
        self._current_transition = name
        self.transition_selected.emit(name)
        logger.debug("Context menu: transition selected: %s", name)
    
    def _on_dimming_toggled(self) -> None:
        """Handle dimming toggle."""
        self._dimming_enabled = self._dimming_action.isChecked()
        self.dimming_toggled.emit(self._dimming_enabled)
        logger.debug("Context menu: dimming toggled: %s", self._dimming_enabled)
    
    def _on_hard_exit_toggled(self) -> None:
        """Handle hard exit toggle."""
        self._hard_exit_enabled = self._hard_exit_action.isChecked()
        self.hard_exit_toggled.emit(self._hard_exit_enabled)
        logger.debug("Context menu: hard exit toggled: %s", self._hard_exit_enabled)
    
    def update_current_transition(self, name: str) -> None:
        """Update the currently selected transition."""
        self._current_transition = name
        for trans_name, action in self._transition_actions.items():
            action.setChecked(trans_name == name)
    
    def update_dimming_state(self, enabled: bool) -> None:
        """Update the dimming checkbox state."""
        self._dimming_enabled = enabled
        self._dimming_action.setChecked(enabled)
    
    def update_hard_exit_state(self, enabled: bool) -> None:
        """Update the hard exit checkbox state."""
        self._hard_exit_enabled = enabled
        self._hard_exit_action.setChecked(enabled)
