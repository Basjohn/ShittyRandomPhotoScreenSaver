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
import weakref
from PySide6.QtWidgets import QMenu, QWidget
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction

from core.logging.logger import get_logger
from rendering.transition_registry import get_transition_setting_names
from ui.settings_theme_runtime import (
    get_active_settings_theme,
    subscribe_settings_theme,
)
from ui.settings_theme_spec import SettingsThemeSpec

logger = get_logger(__name__)

_SETTINGS_THEME = get_active_settings_theme()
_LIVE_CONTEXT_MENUS: weakref.WeakSet = weakref.WeakSet()


def _theme_hex(token: str) -> str:
    """Render one opaque semantic context-menu colour as QSS hex."""

    value = _SETTINGS_THEME.color(token)
    if value.a != 255:
        raise ValueError(f"Context-menu theme colour {token!r} is not opaque")
    return f"#{value.r:02x}{value.g:02x}{value.b:02x}"


def _theme_rgba255(token: str) -> str:
    """Render one semantic context-menu colour with integer alpha."""

    value = _SETTINGS_THEME.color(token)
    return f"rgba({value.r}, {value.g}, {value.b}, {value.a})"


# Dark theme matching settings dialog - app-owned, no Windows accent bleed
# Uses same color palette as settings_dialog.py for consistency
def _build_menu_style() -> str:
    return f"""
    QMenu {{
        background-color: {_theme_rgba255('context.menu.surface')};
        border: 3px solid {_theme_hex('context.menu.border')};
        border-radius: 10px;
        padding: 8px 6px;
    }}
    QMenu::item {{
        background-color: transparent;
        color: {_theme_hex('context.menu.text')};
        padding: 10px 26px 10px 10px;
        margin: 3px 5px;
        border-radius: 6px;
        font-size: 14px;
        font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';
        font-weight: 600;
    }}
    QMenu::item:selected {{
        background-color: {_theme_rgba255('context.menu.selected_surface')};
    }}
    QMenu::item:disabled {{
        color: {_theme_rgba255('context.menu.disabled_text')};
    }}
    QMenu::separator {{
        height: 1px;
        background-color: {_theme_rgba255('context.menu.separator')};
        margin: 4px 12px;
    }}
    QMenu::indicator {{
        width: 22px;
        height: 22px;
        margin-left: 8px;
        margin-right: 8px;
        border-radius: 11px;
        border: none;
    }}
    QMenu::indicator:checked {{
        image: url(:/ui/assets/circle_checkbox_checked.svg);
    }}
    QMenu::indicator:unchecked {{
        image: url(:/ui/assets/circle_checkbox_unchecked.svg);
    }}
    """


MENU_STYLE = _build_menu_style()


def _build_submenu_style() -> str:
    return f"""
    QMenu {{
        background-color: {_theme_rgba255('context.submenu.surface')};
        border: 3px solid {_theme_hex('context.submenu.border')};
        border-radius: 8px;
        padding: 6px 4px;
    }}
    QMenu::item {{
        background-color: transparent;
        color: {_theme_hex('context.submenu.text')};
        padding: 8px 22px 8px 12px;
        margin: 2px 4px;
        border-radius: 4px;
        font-size: 13px;
        font-family: 'Jost', 'Segoe UI', 'Arial', 'Sans Serif';
        font-weight: 600;
    }}
    QMenu::item:selected {{
        background-color: {_theme_rgba255('context.submenu.selected_surface')};
    }}
    QMenu::item:checked {{
        color: {_theme_hex('context.submenu.checked_text')};
        font-weight: 700;
        background-color: {_theme_rgba255('context.submenu.checked_surface')};
    }}
    QMenu::indicator {{
        width: 20px;
        height: 20px;
        margin-left: 6px;
        margin-right: 4px;
        border-radius: 10px;
        border: none;
    }}
    QMenu::indicator:checked {{
        image: url(:/ui/assets/circle_checkbox_checked.svg);
    }}
    QMenu::indicator:unchecked {{
        image: url(:/ui/assets/circle_checkbox_unchecked.svg);
    }}
    """



SUBMENU_STYLE = _build_submenu_style()



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
        _LIVE_CONTEXT_MENUS.add(self)
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

        # Transition submenu - monochrome arrows. Entries are (re)built from the
        # currently ACTIVATED transitions (E2), refreshed each time the menu is
        # shown via refresh_transition_modes().
        self._transition_menu = QMenu("⟳  Change Transition", self)
        self._transition_menu.setStyleSheet(SUBMENU_STYLE)
        self._transition_actions: dict[str, QAction] = {}
        self._random_selectable = True
        self._populate_transition_submenu()
        self.addMenu(self._transition_menu)

        # Visualizer submenu — populated from active mode registry (gate-aware).
        # Its availability follows the Visualizers capability (+ its Media
        # dependency), refreshed on show via set_visualizer_available().
        self._visualizer_menu = QMenu("⟳  Change Visualizer", self)
        self._visualizer_menu.setStyleSheet(SUBMENU_STYLE)
        self._visualizer_actions: dict[str, QAction] = {}
        self._populate_visualizer_submenu()
        self._visualizer_menu_action = self.addMenu(self._visualizer_menu)
        self._visualizer_available = True

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

    def _populate_transition_submenu(self) -> None:
        """Rebuild the transition submenu from the current activated set."""
        self._transition_menu.clear()
        self._transition_actions.clear()

        # 'Random' option at the top (disabled when it cannot legally run).
        random_action = self._transition_menu.addAction("Random")
        random_action.setCheckable(True)
        random_action.setChecked(self._random_enabled)
        random_action.setEnabled(self._random_selectable)
        random_action.triggered.connect(lambda checked: self._on_transition_selected("Random"))
        self._transition_actions["Random"] = random_action

        self._transition_menu.addSeparator()

        for trans_name in self._transition_types:
            action = self._transition_menu.addAction(trans_name)
            action.setCheckable(True)
            action.setChecked(not self._random_enabled and trans_name == self._current_transition)
            action.triggered.connect(lambda checked, name=trans_name: self._on_transition_selected(name))
            self._transition_actions[trans_name] = action

    def refresh_transition_modes(
        self,
        activated_names: List[str],
        current_transition: str,
        random_enabled: bool,
        *,
        random_selectable: bool = True,
    ) -> None:
        """Rebuild the transition submenu from current activation + random state.

        Only ACTIVATED transitions appear; the Random entry is disabled when the
        effective pool is empty so it cannot be selected into an invalid state.
        """
        self._transition_types = list(activated_names)
        self._current_transition = current_transition
        self._random_enabled = bool(random_enabled)
        self._random_selectable = bool(random_selectable)
        self._populate_transition_submenu()

    def _on_transition_selected(self, name: str) -> None:
        """Handle transition selection."""
        # Update checkmarks
        for trans_name, action in self._transition_actions.items():
            if trans_name == "Random":
                action.setChecked(name == "Random")
            else:
                action.setChecked(name != "Random" and trans_name == name)
        self._current_transition = name if name != "Random" else self._current_transition
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

    def set_visualizer_available(self, available: bool) -> None:
        """Show/hide the whole Change Visualizer submenu by capability state."""
        self._visualizer_available = bool(available)
        action = getattr(self, "_visualizer_menu_action", None)
        if action is not None:
            action.setVisible(self._visualizer_available)

    def is_visualizer_available(self) -> bool:
        return bool(getattr(self, "_visualizer_available", True))

    def refresh_visualizer_modes(self) -> None:
        """Rebuild the visualizer submenu (e.g. after gate changes)."""
        self._populate_visualizer_submenu()

def _refresh_live_context_menus(theme: SettingsThemeSpec) -> None:
    """Refresh existing main/submenu QSS after the active theme changes."""

    global _SETTINGS_THEME, MENU_STYLE, SUBMENU_STYLE
    _SETTINGS_THEME = theme
    MENU_STYLE = _build_menu_style()
    SUBMENU_STYLE = _build_submenu_style()

    for menu in tuple(_LIVE_CONTEXT_MENUS):
        try:
            menu.setStyleSheet(MENU_STYLE)
            transition_menu = getattr(menu, "_transition_menu", None)
            if transition_menu is not None:
                transition_menu.setStyleSheet(SUBMENU_STYLE)
            visualizer_menu = getattr(menu, "_visualizer_menu", None)
            if visualizer_menu is not None:
                visualizer_menu.setStyleSheet(SUBMENU_STYLE)
        except RuntimeError:
            continue


_THEME_UNSUBSCRIBE = subscribe_settings_theme(_refresh_live_context_menus)

