"""
Context menu for screensaver with dark glass styling.

Provides quick access to:
- Previous/Next image
- Transition selection
- Settings
- Background dimming toggle
- Interaction Mode toggle
- Exit
"""
from typing import Optional, List
from PySide6.QtWidgets import QMenu, QWidget
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction

from core.logging.logger import get_logger
from rendering.transition_registry import get_transition_setting_names

logger = get_logger(__name__)

# Dark theme matching settings dialog - app-owned, no Windows accent bleed
# Uses same color palette as settings_dialog.py for consistency
MENU_STYLE = """
QMenu {
    background-color: rgba(43, 43, 43, 255);
    border: 3px solid #ffffff;
    border-radius: 10px;
    padding: 8px 6px;
}
QMenu::item {
    background-color: transparent;
    color: #ffffff;
    padding: 10px 26px 10px 10px;
    margin: 3px 5px;
    border-radius: 6px;
    font-size: 14px;
    font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';
    font-weight: 600;
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
    width: 22px;
    height: 22px;
    margin-left: 8px;
    margin-right: 8px;
    border-radius: 11px;
    border: none;
}
QMenu::indicator:checked {
    image: url(:/ui/assets/circle_checkbox_checked.svg);
}
QMenu::indicator:unchecked {
    image: url(:/ui/assets/circle_checkbox_unchecked.svg);
}
"""

SUBMENU_STYLE = """
QMenu {
    background-color: rgba(43, 43, 43, 255);
    border: 3px solid #ffffff;
    border-radius: 8px;
    padding: 6px 4px;
}
QMenu::item {
    background-color: transparent;
    color: #ffffff;
    padding: 8px 22px 8px 12px;
    margin: 2px 4px;
    border-radius: 4px;
    font-size: 13px;
    font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';
    font-weight: 600;
}
QMenu::item:selected {
    background-color: rgba(62, 62, 62, 220);
}
QMenu::item:checked {
    color: #ffffff;
    font-weight: 700;
    background-color: rgba(62, 62, 62, 220);
}
QMenu::indicator {
    width: 20px;
    height: 20px;
    margin-left: 6px;
    margin-right: 4px;
    border-radius: 10px;
    border: none;
}
QMenu::indicator:checked {
    image: url(:/ui/assets/circle_checkbox_checked.svg);
}
QMenu::indicator:unchecked {
    image: url(:/ui/assets/circle_checkbox_unchecked.svg);
}
"""


class ScreensaverContextMenu(QMenu):
    """Dark glass themed context menu for screensaver."""
    
    # Signals for menu actions
    previous_requested = Signal()
    next_requested = Signal()
    transition_selected = Signal(str)  # transition name
    visualizer_selected = Signal(str)  # mode_id
    settings_requested = Signal()
    edit_mode_requested = Signal()
    save_edit_mode_requested = Signal()
    cancel_edit_mode_requested = Signal()
    reset_edit_mode_requested = Signal()
    dimming_toggled = Signal(bool)  # new state
    interaction_mode_toggled = Signal(bool)  # new state
    always_on_top_toggled = Signal(bool)  # new state (MC mode only)
    exit_requested = Signal()
    
    def __init__(
        self,
        parent: Optional[QWidget] = None,
        transition_types: Optional[List[str]] = None,
        current_transition: str = "Crossfade",
        dimming_enabled: bool = False,
        interaction_mode_enabled: bool = False,
        is_mc_build: bool = False,
        always_on_top: bool = False,
        random_enabled: bool = False,
        current_visualizer: str = "spectrum",
    ):
        super().__init__(parent)
        
        self._is_mc_build = is_mc_build
        self._always_on_top = always_on_top
        self._transition_types = transition_types or get_transition_setting_names()
        self._current_transition = current_transition
        self._random_enabled = random_enabled
        self._dimming_enabled = dimming_enabled
        self._interaction_mode_locked = bool(is_mc_build)
        self._interaction_mode_enabled = True if self._interaction_mode_locked else interaction_mode_enabled
        self._current_visualizer = current_visualizer
        
        self.setStyleSheet(MENU_STYLE)
        try:
            self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        except Exception as e:
            logger.debug("[CONTEXT_MENU] Exception suppressed: %s", e)
        try:
            self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, True)
        except Exception as e:
            logger.debug("[CONTEXT_MENU] Exception suppressed: %s", e)
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        except Exception as e:
            logger.debug("[CONTEXT_MENU] Exception suppressed: %s", e)
        try:
            self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        except Exception as e:
            logger.debug("[CONTEXT_MENU] Exception suppressed: %s", e)
        
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
        
        # Add 'Random' option at the top
        random_action = self._transition_menu.addAction("Random")
        random_action.setCheckable(True)
        random_action.setChecked(self._random_enabled)
        random_action.triggered.connect(lambda checked: self._on_transition_selected("Random"))
        self._transition_actions["Random"] = random_action
        
        self._transition_menu.addSeparator()
        
        for trans_name in self._transition_types:
            action = self._transition_menu.addAction(trans_name)
            action.setCheckable(True)
            action.setChecked(trans_name == self._current_transition)
            action.triggered.connect(lambda checked, name=trans_name: self._on_transition_selected(name))
            self._transition_actions[trans_name] = action
        
        self.addMenu(self._transition_menu)
        
        # Visualizer submenu — populated from active mode registry (gate-aware)
        self._visualizer_menu = QMenu("⟳  Change Visualizer", self)
        self._visualizer_menu.setStyleSheet(SUBMENU_STYLE)
        self._visualizer_actions: dict[str, QAction] = {}
        self._populate_visualizer_submenu()
        self.addMenu(self._visualizer_menu)
        
        self.addSeparator()
        
        # Settings - monochrome gear
        settings_action = self.addAction("⚙  Settings")
        settings_action.triggered.connect(self.settings_requested.emit)

        self._edit_mode_action = self.addAction("✥  Edit Widget Layout")
        self._edit_mode_action.triggered.connect(self.edit_mode_requested.emit)

        self._save_edit_mode_action = self.addAction("✓  Save Widget Layout")
        self._save_edit_mode_action.triggered.connect(self.save_edit_mode_requested.emit)

        self._cancel_edit_mode_action = self.addAction("↺  Cancel Widget Layout")
        self._cancel_edit_mode_action.triggered.connect(self.cancel_edit_mode_requested.emit)

        self._reset_edit_mode_action = self.addAction("⟲  Reset To Saved Layout")
        self._reset_edit_mode_action.triggered.connect(self.reset_edit_mode_requested.emit)

        self.addSeparator()
        
        # Background Dimming toggle - monochrome circle
        self._dimming_action = self.addAction("◐  Background Dimming")
        self._dimming_action.setCheckable(True)
        self._dimming_action.setChecked(self._dimming_enabled)
        self._dimming_action.triggered.connect(self._on_dimming_toggled)
        
        # Interaction Mode toggle - monochrome lock
        self._interaction_mode_action = self.addAction("⊘  Interaction Mode")
        self._interaction_mode_action.setCheckable(True)
        self._interaction_mode_action.setChecked(self._interaction_mode_enabled)
        if self._interaction_mode_locked:
            self._interaction_mode_action.setEnabled(False)
            self._interaction_mode_action.setToolTip(
                "Media Center builds keep Interaction Mode always enabled."
            )
        self._interaction_mode_action.triggered.connect(self._on_interaction_mode_toggled)
        
        # Always On Top toggle (MC mode only) - monochrome pin
        # COMMENTED OUT: Removed from MC mode context menu per user request
        self._on_top_action: Optional[QAction] = None
        # if self._is_mc_build:
        #     self._on_top_action = self.addAction("📌  Always On Top")
        #     self._on_top_action.setCheckable(True)
        #     self._on_top_action.setChecked(self._always_on_top)
        #     self._on_top_action.triggered.connect(self._on_always_on_top_toggled)
        
        self.addSeparator()
        
        # Exit - monochrome X
        exit_action = self.addAction("✕  Exit Screensaver")
        exit_action.triggered.connect(self.exit_requested.emit)
    
    def _on_transition_selected(self, name: str) -> None:
        """Handle transition selection."""
        # Update checkmarks
        for trans_name, action in self._transition_actions.items():
            if trans_name == "Random":
                action.setChecked(name == "Random")
            else:
                action.setChecked(not self._random_enabled and trans_name == name)
        self._current_transition = name
        self._random_enabled = (name == "Random")
        self.transition_selected.emit(name)
        logger.debug("Context menu: transition selected: %s", name)
    
    def update_transition_state(self, name: str, random_enabled: bool) -> None:
        """Sync menu checkmarks with current transition and random mode."""
        self._random_enabled = random_enabled
        self._current_transition = name
        for trans_name, action in self._transition_actions.items():
            if trans_name == "Random":
                action.setChecked(random_enabled)
            else:
                action.setChecked(not random_enabled and trans_name == name)
    
    def _on_dimming_toggled(self) -> None:
        """Handle dimming toggle."""
        self._dimming_enabled = self._dimming_action.isChecked()
        self.dimming_toggled.emit(self._dimming_enabled)
        logger.debug("Context menu: dimming toggled: %s", self._dimming_enabled)
    
    def _on_interaction_mode_toggled(self) -> None:
        """Handle Interaction Mode toggle."""
        if self._interaction_mode_locked:
            self._interaction_mode_action.setChecked(True)
            return
        self._interaction_mode_enabled = self._interaction_mode_action.isChecked()
        self.interaction_mode_toggled.emit(self._interaction_mode_enabled)
        logger.debug("Context menu: interaction mode toggled: %s", self._interaction_mode_enabled)
    
    def update_current_transition(self, name: str) -> None:
        """Update the currently selected transition."""
        self.update_transition_state(name, self._random_enabled)
    
    def update_dimming_state(self, enabled: bool) -> None:
        """Update the dimming checkbox state."""
        self._dimming_enabled = enabled
        self._dimming_action.setChecked(enabled)
    
    def update_interaction_mode_state(self, enabled: bool) -> None:
        """Update the Interaction Mode checkbox state."""
        self._interaction_mode_enabled = True if self._interaction_mode_locked else enabled
        self._interaction_mode_action.setChecked(self._interaction_mode_enabled)
    
    def _on_always_on_top_toggled(self) -> None:
        """Handle always on top toggle."""
        if self._on_top_action is not None:
            self._always_on_top = self._on_top_action.isChecked()
            self.always_on_top_toggled.emit(self._always_on_top)
            logger.debug("Context menu: always on top toggled: %s", self._always_on_top)
    
    def update_always_on_top_state(self, on_top: bool) -> None:
        """Update the always on top checkbox state."""
        self._always_on_top = on_top
        if self._on_top_action is not None:
            self._on_top_action.setChecked(on_top)

    def update_edit_mode_state(self, active: bool) -> None:
        """Update edit-mode actions to reflect the active session state."""

        self._edit_mode_action.setVisible(not active)
        self._save_edit_mode_action.setVisible(active)
        self._cancel_edit_mode_action.setVisible(active)
        self._reset_edit_mode_action.setVisible(active)
    
    def _populate_visualizer_submenu(self) -> None:
        """Build visualizer submenu entries from active mode descriptors."""
        try:
            from core.settings.visualizer_mode_registry import iter_visualizer_mode_descriptors
            descriptors = iter_visualizer_mode_descriptors()
        except Exception:
            logger.debug("[CONTEXT_MENU] Failed to load visualizer mode descriptors", exc_info=True)
            descriptors = ()
        
        self._visualizer_menu.clear()
        self._visualizer_actions.clear()
        
        for desc in descriptors:
            action = self._visualizer_menu.addAction(desc.display_name)
            action.setCheckable(True)
            action.setChecked(desc.mode_id == self._current_visualizer)
            action.triggered.connect(
                lambda checked, mid=desc.mode_id: self._on_visualizer_selected(mid)
            )
            self._visualizer_actions[desc.mode_id] = action
    
    def _on_visualizer_selected(self, mode_id: str) -> None:
        """Handle visualizer mode selection."""
        self._current_visualizer = mode_id
        for mid, action in self._visualizer_actions.items():
            action.setChecked(mid == mode_id)
        self.visualizer_selected.emit(mode_id)
        logger.debug("Context menu: visualizer selected: %s", mode_id)
    
    def update_visualizer_state(self, mode_id: str) -> None:
        """Sync visualizer checkmarks with the current mode."""
        self._current_visualizer = mode_id
        for mid, action in self._visualizer_actions.items():
            action.setChecked(mid == mode_id)
    
    def refresh_visualizer_modes(self) -> None:
        """Rebuild the visualizer submenu (e.g. after gate changes)."""
        self._populate_visualizer_submenu()
