"""
Context menu for screensaver with dark glass styling.

Provides quick access to:
- Previous/Next image
- Transition selection
- Settings
- Hard exit mode toggle
- Exit
"""
from typing import Optional, List
from PySide6.QtWidgets import QMenu, QWidget
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction

from core.logging.logger import get_logger

logger = get_logger(__name__)

# Dark glass theme colors matching existing widgets
MENU_STYLE = """
QMenu {
    background-color: rgba(20, 20, 25, 220);
    border: 1px solid rgba(80, 80, 90, 180);
    border-radius: 8px;
    padding: 6px 4px;
}
QMenu::item {
    background-color: transparent;
    color: rgba(240, 240, 245, 230);
    padding: 8px 24px 8px 16px;
    margin: 2px 4px;
    border-radius: 4px;
    font-size: 13px;
}
QMenu::item:selected {
    background-color: rgba(70, 70, 85, 200);
}
QMenu::item:disabled {
    color: rgba(120, 120, 130, 150);
}
QMenu::separator {
    height: 1px;
    background-color: rgba(80, 80, 90, 120);
    margin: 4px 12px;
}
QMenu::indicator {
    width: 16px;
    height: 16px;
    margin-left: 4px;
}
QMenu::indicator:checked {
    background-color: rgba(100, 180, 255, 200);
    border: 1px solid rgba(120, 200, 255, 220);
    border-radius: 3px;
}
QMenu::indicator:unchecked {
    background-color: rgba(50, 50, 60, 150);
    border: 1px solid rgba(80, 80, 90, 180);
    border-radius: 3px;
}
"""

SUBMENU_STYLE = """
QMenu {
    background-color: rgba(25, 25, 30, 225);
    border: 1px solid rgba(80, 80, 90, 180);
    border-radius: 6px;
    padding: 4px 2px;
}
QMenu::item {
    background-color: transparent;
    color: rgba(235, 235, 240, 220);
    padding: 6px 20px 6px 12px;
    margin: 1px 3px;
    border-radius: 3px;
    font-size: 12px;
}
QMenu::item:selected {
    background-color: rgba(65, 65, 80, 190);
}
QMenu::item:checked {
    color: rgba(130, 200, 255, 255);
    font-weight: bold;
}
"""


class ScreensaverContextMenu(QMenu):
    """Dark glass themed context menu for screensaver."""
    
    # Signals for menu actions
    previous_requested = Signal()
    next_requested = Signal()
    transition_selected = Signal(str)  # transition name
    settings_requested = Signal()
    hard_exit_toggled = Signal(bool)  # new state
    exit_requested = Signal()
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        transition_types: Optional[List[str]] = None,
        current_transition: str = "Crossfade",
        hard_exit_enabled: bool = False,
    ):
        super().__init__(parent)
        
        self._transition_types = transition_types or [
            "Ripple", "Wipe", "3D Block Spins", "Diffuse", "Slide",
            "Crossfade", "Peel", "Block Puzzle Flip", "Warp Dissolve",
            "Blinds", "Crumble",
        ]
        self._current_transition = current_transition
        self._hard_exit_enabled = hard_exit_enabled
        
        self.setStyleSheet(MENU_STYLE)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self._setup_menu()
        logger.debug("ScreensaverContextMenu created")
    
    def _setup_menu(self) -> None:
        """Build the menu structure."""
        # Previous Image
        prev_action = self.addAction("◀  Previous Image")
        prev_action.triggered.connect(self.previous_requested.emit)
        
        # Next Image
        next_action = self.addAction("▶  Next Image")
        next_action.triggered.connect(self.next_requested.emit)
        
        self.addSeparator()
        
        # Transition submenu
        self._transition_menu = QMenu("🔄  Change Transition", self)
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
        
        # Settings
        settings_action = self.addAction("⚙  Settings")
        settings_action.triggered.connect(self.settings_requested.emit)
        
        self.addSeparator()
        
        # Hard Exit Mode toggle
        self._hard_exit_action = self.addAction("🔒  Hard Exit Mode")
        self._hard_exit_action.setCheckable(True)
        self._hard_exit_action.setChecked(self._hard_exit_enabled)
        self._hard_exit_action.triggered.connect(self._on_hard_exit_toggled)
        
        self.addSeparator()
        
        # Exit
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
    
    def update_hard_exit_state(self, enabled: bool) -> None:
        """Update the hard exit checkbox state."""
        self._hard_exit_enabled = enabled
        self._hard_exit_action.setChecked(enabled)
