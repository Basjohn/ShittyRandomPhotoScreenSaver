"""
Widgets configuration tab for settings dialog.

Allows users to configure overlay widgets:
- Clock widget (enable, position, format, size, font, style)
- Weather widget (enable, position, location, API key, size, font, style)
- Media/Spotify widget
- Reddit widget
- Imgur widget (dev-only)

Per-widget UI, load, and save logic is delegated to extraction modules:
  widgets_tab_clock.py, widgets_tab_weather.py, widgets_tab_media.py,
  widgets_tab_reddit.py, widgets_tab_imgur.py
"""
from typing import Optional, Dict, Any, Mapping
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QCheckBox, QPushButton,
    QScrollArea, QSlider, QButtonGroup,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor

from core.settings.settings_manager import SettingsManager
from core.logging.logger import get_logger
from core.settings.defaults import get_default_settings
from ui.tabs.shared_styles import SPINBOX_STYLE, TOOLTIP_STYLE
from ui.styled_popup import StyledColorPicker
from ui.widget_stack_predictor import WidgetType, get_position_status_for_widget
from widgets.timezone_utils import get_local_timezone, get_common_timezones

logger = get_logger(__name__)


class NoWheelSlider(QSlider):
    def wheelEvent(self, event):  # type: ignore[override]
        event.ignore()


class WidgetsTab(QWidget):
    """Widgets configuration tab."""
    
    # Signals
    widgets_changed = Signal()
    
    def __init__(self, settings: SettingsManager, parent: Optional[QWidget] = None):
        """
        Initialize widgets tab.
        
        Args:
            settings: Settings manager
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._settings = settings
        self._widget_defaults = self._load_widget_defaults()
        self._current_subtab = 0
        self._scroll_area: Optional[QScrollArea] = None
        self._clock_color = self._color_from_default('clock', 'color', [255, 255, 255, 230])
        self._weather_color = self._color_from_default('weather', 'color', [255, 255, 255, 230])
        self._clock_border_color = self._color_from_default('clock', 'border_color', [128, 128, 128, 255])
        self._clock_bg_color = self._color_from_default('clock', 'bg_color', [64, 64, 64, 255])
        # Weather widget frame defaults mirror WeatherWidget internals
        self._weather_bg_color = self._color_from_default('weather', 'bg_color', [64, 64, 64, 255])
        self._weather_border_color = self._color_from_default('weather', 'border_color', [128, 128, 128, 255])
        # Media widget frame defaults mirror other overlay widgets
        self._media_color = self._color_from_default('media', 'color', [255, 255, 255, 230])
        self._media_bg_color = self._color_from_default('media', 'bg_color', [64, 64, 64, 255])
        self._media_border_color = self._color_from_default('media', 'border_color', [128, 128, 128, 255])
        # Spotify Beat Visualizer frame defaults inherit Spotify/media styling
        self._spotify_vis_fill_color = self._color_from_default(
            'spotify_visualizer', 'bar_fill_color', [255, 255, 255, 230]
        )
        self._spotify_vis_border_color = self._color_from_default(
            'spotify_visualizer', 'bar_border_color', [255, 255, 255, 230]
        )
        # Reddit widget frame defaults mirror Spotify/media widget styling
        self._reddit_color = self._color_from_default('reddit', 'color', [255, 255, 255, 230])
        self._reddit_bg_color = self._color_from_default('reddit', 'bg_color', [64, 64, 64, 255])
        self._reddit_border_color = self._color_from_default('reddit', 'border_color', [128, 128, 128, 255])
        # Imgur widget colors
        self._imgur_color = self._color_from_default('imgur', 'color', [255, 255, 255, 230])
        self._imgur_bg_color = self._color_from_default('imgur', 'bg_color', [35, 35, 35, 255])
        self._imgur_border_color = self._color_from_default('imgur', 'border_color', [255, 255, 255, 255])
        self._media_artwork_size = int(self._widget_default('media', 'artwork_size', 200))
        self._loading = True
        self._save_coalesce_pending = False
        self._setup_ui()
        self._load_settings()
        self._loading = False
        
        logger.debug("WidgetsTab created")
    
    def load_from_settings(self) -> None:
        """Reload all UI controls from settings manager (called after preset change)."""
        self._loading = True
        try:
            self._load_settings()
        finally:
            self._loading = False
        logger.debug("[WIDGETS_TAB] Reloaded from settings")
    
    def _load_widget_defaults(self) -> Dict[str, Dict[str, Any]]:
        """Load canonical widget defaults once for reuse."""
        try:
            defaults = get_default_settings()
            widgets_defaults = defaults.get('widgets', {})
            return widgets_defaults if isinstance(widgets_defaults, dict) else {}
        except Exception:
            logger.debug("[WIDGETS_TAB] Failed to load widget defaults", exc_info=True)
            return {}
    
    def _widget_default(self, section: str, key: str, fallback: Any) -> Any:
        """Fetch a default value for a widget section/key combo."""
        section_defaults = self._widget_defaults.get(section, {})
        if isinstance(section_defaults, dict) and key in section_defaults:
            return section_defaults[key]
        return fallback
    
    def _color_from_default(self, section: str, key: str, fallback: list[int]) -> QColor:
        """Return a QColor built from canonical defaults with fallback."""
        value = self._widget_default(section, key, fallback)
        try:
            if isinstance(value, (list, tuple)) and len(value) >= 3:
                return QColor(*value)
        except Exception:
            logger.debug("[WIDGETS_TAB] Invalid color default for %s.%s", section, key, exc_info=True)
        return QColor(*fallback)
    
    def _default_int(self, section: str, key: str, fallback: int) -> int:
        """Return widget default coerced to int."""
        value = self._widget_default(section, key, fallback)
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(fallback)
    
    def _default_float(self, section: str, key: str, fallback: float) -> float:
        """Return widget default coerced to float."""
        value = self._widget_default(section, key, fallback)
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(fallback)
    
    def _default_bool(self, section: str, key: str, fallback: bool) -> bool:
        """Return widget default coerced to bool via SettingsManager helper."""
        value = self._widget_default(section, key, fallback)
        return SettingsManager.to_bool(value, fallback)
    
    def _default_str(self, section: str, key: str, fallback: str) -> str:
        """Return widget default coerced to string."""
        value = self._widget_default(section, key, fallback)
        if value is None:
            return fallback
        return str(value)
    
    def _config_bool(self, section: str, config: Mapping[str, Any], key: str, fallback: bool) -> bool:
        default = self._default_bool(section, key, fallback)
        raw = config.get(key, default) if isinstance(config, Mapping) else default
        return SettingsManager.to_bool(raw, default)
    
    def _config_int(self, section: str, config: Mapping[str, Any], key: str, fallback: int) -> int:
        default = self._default_int(section, key, fallback)
        raw = config.get(key, default) if isinstance(config, Mapping) else default
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default
    
    def _config_float(self, section: str, config: Mapping[str, Any], key: str, fallback: float) -> float:
        default = self._default_float(section, key, fallback)
        raw = config.get(key, default) if isinstance(config, Mapping) else default
        try:
            return float(raw)
        except (TypeError, ValueError):
            return default
    
    def _config_str(self, section: str, config: Mapping[str, Any], key: str, fallback: str) -> str:
        default = self._default_str(section, key, fallback)
        raw = config.get(key, default) if isinstance(config, Mapping) else default
        if raw is None:
            return default
        return str(raw)
    
    @staticmethod
    def _set_combo_text(combo: QComboBox, text: str) -> None:
        """Select combo entry by visible text if present."""
        if text is None:
            return
        idx = combo.findText(text, Qt.MatchFlag.MatchFixedString)
        if idx >= 0:
            combo.setCurrentIndex(idx)
    
    @staticmethod
    def _set_combo_data(combo: QComboBox, data: Any) -> None:
        """Select combo entry by user data if present."""
        idx = combo.findData(data)
        if idx >= 0:
            combo.setCurrentIndex(idx)
    
    def _setup_ui(self) -> None:
        """Setup tab UI with scroll area."""
        # Check dev features gate once at the start
        import os
        dev_features_enabled = os.getenv('SRPSS_ENABLE_DEV', 'false').lower() == 'true'
        
        # Create scroll area
        scroll = QScrollArea(self)
        self._scroll_area = scroll
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea { 
                border: none; 
                background: transparent; 
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QScrollArea QWidget {
                background: transparent;
            }
        """)
        
        # Create content widget
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Overlay Widgets")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)

        # Global widget options
        global_row = QHBoxLayout()
        self.widget_shadows_enabled = QCheckBox("Enable Widget Drop Shadows")
        self.widget_shadows_enabled.setChecked(self._default_bool('shadows', 'enabled', True))
        self.widget_shadows_enabled.setToolTip(
            "Applies a subtle bottom-right drop shadow to overlay widgets (clocks, "
            "weather, media) when enabled."
        )
        self.widget_shadows_enabled.stateChanged.connect(self._save_settings)
        global_row.addWidget(self.widget_shadows_enabled)
        global_row.addStretch()
        layout.addLayout(global_row)

        # Subtab-style toggle buttons (Clocks / Weather / Media / Reddit)
        subtab_row = QHBoxLayout()
        self._subtab_group = QButtonGroup(self)
        self._subtab_group.setExclusive(True)

        self._btn_clocks = QPushButton("Clocks")
        self._btn_weather = QPushButton("Weather")
        self._btn_media = QPushButton("Media")
        self._btn_reddit = QPushButton("Reddit")
        
        # Imgur button - gated by SRPSS_ENABLE_DEV
        if dev_features_enabled:
            self._btn_imgur = QPushButton("Imgur")

        button_style = (
            "QPushButton {"
            " background-color: #2a2a2a;"
            " color: #ffffff;"
            " border-radius: 4px;"
            " padding: 4px 12px;"
            " border-top: 1px solid rgba(110, 110, 110, 0.8);"
            " border-left: 1px solid rgba(110, 110, 110, 0.8);"
            " border-right: 2px solid rgba(0, 0, 0, 0.75);"
            " border-bottom: 2px solid rgba(0, 0, 0, 0.8);"
            " }"
            "QPushButton:checked {"
            " background-color: #3a3a3a;"
            " font-weight: bold;"
            " border-top: 2px solid rgba(0, 0, 0, 0.75);"
            " border-left: 2px solid rgba(0, 0, 0, 0.75);"
            " border-right: 1px solid rgba(140, 140, 140, 0.85);"
            " border-bottom: 1px solid rgba(140, 140, 140, 0.85);"
            " }"
        )

        # Build button list conditionally
        buttons = [self._btn_clocks, self._btn_weather, self._btn_media, self._btn_reddit]
        if dev_features_enabled:
            buttons.append(self._btn_imgur)
        
        for idx, btn in enumerate(buttons):
            btn.setCheckable(True)
            btn.setStyleSheet(button_style)
            self._subtab_group.addButton(btn, idx)
            subtab_row.addWidget(btn)

        subtab_row.addStretch()
        layout.addLayout(subtab_row)

        self._subtab_group.idClicked.connect(self._on_subtab_changed)
        self._btn_clocks.setChecked(True)

        # --- Per-widget sections (delegated to extraction modules) ---
        from ui.tabs.widgets_tab_clock import build_clock_ui
        from ui.tabs.widgets_tab_weather import build_weather_ui
        from ui.tabs.widgets_tab_media import build_media_ui
        from ui.tabs.widgets_tab_reddit import build_reddit_ui

        self._clocks_container = build_clock_ui(self, layout)
        layout.addWidget(self._clocks_container)

        self._weather_container = build_weather_ui(self, layout)
        layout.addWidget(self._weather_container)

        self._media_container = build_media_ui(self, layout)
        layout.addWidget(self._media_container)

        self._reddit_container = build_reddit_ui(self, layout)
        layout.addWidget(self._reddit_container)

        # NOTE: Gmail widget removed - archived in archive/gmail_feature/

        # Imgur widget group - gated by SRPSS_ENABLE_DEV
        if dev_features_enabled:
            from ui.tabs.widgets_tab_imgur import build_imgur_ui
            self._imgur_container = build_imgur_ui(self, layout)
            layout.addWidget(self._imgur_container)

        layout.addStretch()

        # Set scroll area widget and add to main layout
        scroll.setWidget(content)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

        self.setStyleSheet(self.styleSheet() + SPINBOX_STYLE + TOOLTIP_STYLE)

        # Default to "Clocks" subtab
        self._on_subtab_changed(0)

    def _on_subtab_changed(self, subtab_id: int) -> None:
        """Show/hide widget sections based on selected subtab."""
        self._current_subtab = int(subtab_id)
        try:
            self._clocks_container.setVisible(subtab_id == 0)
            self._weather_container.setVisible(subtab_id == 1)
            self._media_container.setVisible(subtab_id == 2)
            self._reddit_container.setVisible(subtab_id == 3)
            self._imgur_container.setVisible(subtab_id == 4)
        except Exception:
            # If containers are not yet initialized, ignore
            pass
    
    def _on_imgur_tag_changed(self, tag: str) -> None:
        """Handle imgur tag selection change - enable/disable custom tag field."""
        if not hasattr(self, 'imgur_custom_tag'):
            return
        try:
            self.imgur_custom_tag.setEnabled(tag == "custom")
        except Exception:
            pass
    
    def _update_imgur_grid_total(self) -> None:
        """Update the grid total label."""
        if not hasattr(self, 'imgur_grid_total'):
            return
        try:
            rows = self.imgur_grid_rows.value()
            cols = self.imgur_grid_cols.value()
            total = rows * cols
            self.imgur_grid_total.setText(f"= {total} images")
        except Exception:
            pass

    def get_view_state(self) -> Dict[str, Any]:
        state: Dict[str, Any] = {"subtab": int(getattr(self, "_current_subtab", 0))}
        scroll = getattr(self, "_scroll_area", None)
        if scroll is not None:
            try:
                state["scroll"] = int(scroll.verticalScrollBar().value())
            except Exception as e:
                logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
        return state

    def restore_view_state(self, state: Dict[str, Any]) -> None:
        if not isinstance(state, dict):
            return
        subtab = state.get("subtab")
        try:
            subtab_id = int(subtab)
        except (TypeError, ValueError):
            subtab_id = 0
        button = self._subtab_group.button(subtab_id)
        if button is not None:
            button.setChecked(True)
            self._on_subtab_changed(subtab_id)
        scroll_value = state.get("scroll")
        if scroll_value is not None:
            scroll = getattr(self, "_scroll_area", None)
            if scroll is not None:
                try:
                    scroll.verticalScrollBar().setValue(int(scroll_value))
                except Exception as e:
                    logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
    
    def _load_settings(self) -> None:
        """Load settings from settings manager.
        
        Delegates per-widget loading to extraction modules.
        """
        from ui.tabs.widgets_tab_clock import load_clock_settings
        from ui.tabs.widgets_tab_weather import load_weather_settings
        from ui.tabs.widgets_tab_media import load_media_settings
        from ui.tabs.widgets_tab_reddit import load_reddit_settings
        from ui.tabs.widgets_tab_imgur import load_imgur_settings

        # Block all signals during load to prevent unintended saves
        blockers = []
        try:
            widgets_value = self._settings.get('widgets', {})
            if isinstance(widgets_value, dict):
                widgets = dict(widgets_value)
            else:
                widgets = {}

            # Collect all widget controls that need signal blocking
            _widget_attrs = [
                'widget_shadows_enabled',
                'clock_enabled', 'clock_format', 'clock_seconds', 'clock_timezone',
                'clock_show_tz', 'clock_position', 'clock_font_combo', 'clock_font_size',
                'clock_margin', 'clock_show_background', 'clock_bg_opacity',
                'clock_border_opacity', 'clock_monitor_combo',
                'clock2_enabled', 'clock2_timezone', 'clock2_monitor_combo',
                'clock3_enabled', 'clock3_timezone', 'clock3_monitor_combo',
                'weather_enabled', 'weather_location', 'weather_position',
                'weather_font_combo', 'weather_font_size', 'weather_show_forecast',
                'weather_show_background', 'weather_bg_opacity', 'weather_border_opacity',
                'weather_margin', 'weather_monitor_combo',
                'media_enabled', 'media_position', 'media_monitor_combo',
                'media_font_combo', 'media_font_size', 'media_margin',
                'media_show_background', 'media_bg_opacity', 'media_border_opacity',
                'media_artwork_size', 'media_rounded_artwork',
                'media_show_header_frame', 'media_show_controls',
                'media_spotify_volume_enabled',
                'spotify_vis_enabled', 'spotify_vis_bar_count',
                'spotify_vis_border_opacity', 'spotify_vis_ghost_enabled',
                'spotify_vis_ghost_opacity', 'spotify_vis_ghost_decay',
                'reddit_enabled', 'reddit_subreddit', 'reddit_items',
                'reddit_position', 'reddit_monitor_combo',
                'reddit_font_combo', 'reddit_font_size', 'reddit_margin',
                'reddit_show_background', 'reddit_show_separators',
                'reddit_bg_opacity', 'reddit_border_opacity',
                'reddit2_enabled', 'reddit2_subreddit', 'reddit2_items',
                'reddit2_position', 'reddit2_monitor_combo',
                'reddit_exit_on_click',
            ]
            for attr_name in _widget_attrs:
                w = getattr(self, attr_name, None)
                if w is not None and hasattr(w, 'blockSignals'):
                    w.blockSignals(True)
                    blockers.append(w)

            # Global widget shadow settings
            shadows_config = widgets.get('shadows', {}) if isinstance(widgets, dict) else {}
            if isinstance(shadows_config, dict):
                shadows_enabled_raw = shadows_config.get('enabled', True)
                enabled = SettingsManager.to_bool(shadows_enabled_raw, True)
                self.widget_shadows_enabled.setChecked(enabled)
            else:
                self.widget_shadows_enabled.setChecked(True)

            # Delegate per-widget loading to extraction modules
            load_clock_settings(self, widgets)
            load_weather_settings(self, widgets)
            load_media_settings(self, widgets)
            load_reddit_settings(self, widgets)
            load_imgur_settings(self, widgets)

        finally:
            for w in blockers:
                try:
                    w.blockSignals(False)
                except Exception as e:
                    logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
        
        # Update stack status labels after loading settings
        try:
            self._update_stack_status()
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)

    # ------------------------------------------------------------------ #
    #  Color picker callbacks                                              #
    # ------------------------------------------------------------------ #

    def _choose_clock_color(self) -> None:
        """Choose clock text color."""
        color = StyledColorPicker.get_color(self._clock_color, self, "Choose Clock Color")
        if color is not None:
            self._clock_color = color
            self._save_settings()
    
    def _choose_clock_bg_color(self) -> None:
        """Choose clock background color."""
        color = StyledColorPicker.get_color(self._clock_bg_color, self, "Choose Clock Background Color")
        if color is not None:
            self._clock_bg_color = color
            self._save_settings()
    
    def _choose_clock_border_color(self) -> None:
        """Choose clock border color."""
        color = StyledColorPicker.get_color(self._clock_border_color, self, "Choose Clock Border Color")
        if color is not None:
            self._clock_border_color = color
            self._save_settings()
    
    def _choose_weather_color(self) -> None:
        """Choose weather text color."""
        color = StyledColorPicker.get_color(self._weather_color, self, "Choose Weather Color")
        if color is not None:
            self._weather_color = color
            self._save_settings()
    
    def _choose_weather_bg_color(self) -> None:
        """Choose weather background color."""
        color = StyledColorPicker.get_color(self._weather_bg_color, self, "Choose Weather Background Color")
        if color is not None:
            self._weather_bg_color = color
            self._save_settings()

    def _choose_weather_border_color(self) -> None:
        """Choose weather border color."""
        color = StyledColorPicker.get_color(self._weather_border_color, self, "Choose Weather Border Color")
        if color is not None:
            self._weather_border_color = color
            self._save_settings()
    
    def _choose_media_color(self) -> None:
        """Choose media text color."""
        color = StyledColorPicker.get_color(self._media_color, self, "Choose Spotify Color")
        if color is not None:
            self._media_color = color
            self._save_settings()

    def _choose_media_bg_color(self) -> None:
        """Choose media background color."""
        color = StyledColorPicker.get_color(self._media_bg_color, self, "Choose Spotify Background Color")
        if color is not None:
            self._media_bg_color = color
            self._save_settings()

    def _choose_media_border_color(self) -> None:
        """Choose media border color."""
        color = StyledColorPicker.get_color(self._media_border_color, self, "Choose Spotify Border Color")
        if color is not None:
            self._media_border_color = color
            self._save_settings()

    def _choose_media_volume_fill_color(self) -> None:
        """Choose Spotify volume slider fill color."""
        color = StyledColorPicker.get_color(
            getattr(self, "_media_volume_fill_color", self._media_color),
            self,
            "Choose Spotify Volume Fill Color",
        )
        if color is not None:
            self._media_volume_fill_color = color
            self._save_settings()

    def _choose_spotify_vis_fill_color(self) -> None:
        """Choose Spotify Beat Visualizer bar fill color."""
        color = StyledColorPicker.get_color(
            self._spotify_vis_fill_color,
            self,
            "Choose Beat Bar Fill Color",
        )
        if color is not None:
            self._spotify_vis_fill_color = color
            self._save_settings()

    def _choose_spotify_vis_border_color(self) -> None:
        """Choose Spotify Beat Visualizer bar border color."""
        color = StyledColorPicker.get_color(
            self._spotify_vis_border_color,
            self,
            "Choose Beat Bar Border Color",
        )
        if color is not None:
            self._spotify_vis_border_color = color
            self._save_settings()

    def _choose_osc_line_color(self) -> None:
        color = StyledColorPicker.get_color(
            getattr(self, '_osc_line_color', QColor(255, 255, 255, 255)),
            self, "Choose Oscilloscope Line Color")
        if color is not None:
            self._osc_line_color = color
            self._save_settings()

    def _choose_osc_glow_color(self) -> None:
        color = StyledColorPicker.get_color(
            getattr(self, '_osc_glow_color', QColor(0, 200, 255, 230)),
            self, "Choose Oscilloscope Glow Color")
        if color is not None:
            self._osc_glow_color = color
            self._save_settings()

    def _choose_sine_glow_color(self) -> None:
        color = StyledColorPicker.get_color(
            getattr(self, '_sine_glow_color', QColor(0, 200, 255, 230)),
            self, "Choose Sine Wave Glow Color")
        if color is not None:
            self._sine_glow_color = color
            self._save_settings()

    def _choose_sine_line_color(self) -> None:
        color = StyledColorPicker.get_color(
            getattr(self, '_sine_line_color', QColor(255, 255, 255, 255)),
            self, "Choose Sine Wave Line Color")
        if color is not None:
            self._sine_line_color = color
            self._save_settings()

    def _choose_sine_line2_color(self) -> None:
        color = StyledColorPicker.get_color(
            getattr(self, '_sine_line2_color', QColor(255, 120, 50, 230)),
            self, "Choose Sine Line 2 Color")
        if color is not None:
            self._sine_line2_color = color
            self._save_settings()

    def _choose_sine_line2_glow_color(self) -> None:
        color = StyledColorPicker.get_color(
            getattr(self, '_sine_line2_glow_color', QColor(255, 120, 50, 180)),
            self, "Choose Sine Line 2 Glow Color")
        if color is not None:
            self._sine_line2_glow_color = color
            self._save_settings()

    def _choose_sine_line3_color(self) -> None:
        color = StyledColorPicker.get_color(
            getattr(self, '_sine_line3_color', QColor(50, 255, 120, 230)),
            self, "Choose Sine Line 3 Color")
        if color is not None:
            self._sine_line3_color = color
            self._save_settings()

    def _choose_sine_line3_glow_color(self) -> None:
        color = StyledColorPicker.get_color(
            getattr(self, '_sine_line3_glow_color', QColor(50, 255, 120, 180)),
            self, "Choose Sine Line 3 Glow Color")
        if color is not None:
            self._sine_line3_glow_color = color
            self._save_settings()

    def _choose_osc_line2_color(self) -> None:
        color = StyledColorPicker.get_color(
            getattr(self, '_osc_line2_color', QColor(255, 120, 50, 230)),
            self, "Choose Line 2 Color")
        if color is not None:
            self._osc_line2_color = color
            self._save_settings()

    def _choose_osc_line2_glow_color(self) -> None:
        color = StyledColorPicker.get_color(
            getattr(self, '_osc_line2_glow_color', QColor(255, 120, 50, 180)),
            self, "Choose Line 2 Glow Color")
        if color is not None:
            self._osc_line2_glow_color = color
            self._save_settings()

    def _choose_osc_line3_color(self) -> None:
        color = StyledColorPicker.get_color(
            getattr(self, '_osc_line3_color', QColor(50, 255, 120, 230)),
            self, "Choose Line 3 Color")
        if color is not None:
            self._osc_line3_color = color
            self._save_settings()

    def _choose_osc_line3_glow_color(self) -> None:
        color = StyledColorPicker.get_color(
            getattr(self, '_osc_line3_glow_color', QColor(50, 255, 120, 180)),
            self, "Choose Line 3 Glow Color")
        if color is not None:
            self._osc_line3_glow_color = color
            self._save_settings()

    def _choose_blob_fill_color(self) -> None:
        color = StyledColorPicker.get_color(
            getattr(self, '_blob_color', QColor(0, 180, 255, 230)),
            self, "Choose Blob Fill Color")
        if color is not None:
            self._blob_color = color
            self._save_settings()

    def _choose_blob_glow_color(self) -> None:
        color = StyledColorPicker.get_color(
            getattr(self, '_blob_glow_color', QColor(0, 140, 255, 180)),
            self, "Choose Blob Glow Color")
        if color is not None:
            self._blob_glow_color = color
            self._save_settings()

    def _choose_blob_edge_color(self) -> None:
        color = StyledColorPicker.get_color(
            getattr(self, '_blob_edge_color', QColor(100, 220, 255, 230)),
            self, "Choose Blob Edge Color")
        if color is not None:
            self._blob_edge_color = color
            self._save_settings()

    def _choose_blob_outline_color(self) -> None:
        color = StyledColorPicker.get_color(
            getattr(self, '_blob_outline_color', QColor(0, 0, 0, 0)),
            self, "Choose Blob Outline Color")
        if color is not None:
            self._blob_outline_color = color
            self._save_settings()

    def _choose_helix_glow_color(self) -> None:
        color = StyledColorPicker.get_color(
            getattr(self, '_helix_glow_color', QColor(0, 200, 255, 180)),
            self, "Choose Helix Glow Color")
        if color is not None:
            self._helix_glow_color = color

    def _choose_nebula_tint1(self) -> None:
        color = StyledColorPicker.get_color(
            getattr(self, '_nebula_tint1', QColor(20, 40, 120)),
            self, "Choose Nebula Tint 1")
        if color is not None:
            self._nebula_tint1 = color
            self._save_settings()

    def _choose_nebula_tint2(self) -> None:
        color = StyledColorPicker.get_color(
            getattr(self, '_nebula_tint2', QColor(80, 20, 100)),
            self, "Choose Nebula Tint 2")
        if color is not None:
            self._nebula_tint2 = color
            self._save_settings()

    def _choose_reddit_color(self) -> None:
        """Choose Reddit text color."""
        color = StyledColorPicker.get_color(self._reddit_color, self, "Choose Reddit Color")
        if color is not None:
            self._reddit_color = color
            self._save_settings()

    def _choose_reddit_bg_color(self) -> None:
        """Choose Reddit background color."""
        color = StyledColorPicker.get_color(self._reddit_bg_color, self, "Choose Reddit Background Color")
        if color is not None:
            self._reddit_bg_color = color
            self._save_settings()

    def _choose_reddit_border_color(self) -> None:
        """Choose Reddit border color."""
        color = StyledColorPicker.get_color(self._reddit_border_color, self, "Choose Reddit Border Color")
        if color is not None:
            self._reddit_border_color = color
            self._save_settings()

    def _choose_imgur_color(self) -> None:
        """Choose Imgur text color."""
        if not hasattr(self, '_imgur_color'):
            return
        color = StyledColorPicker.get_color(self._imgur_color, self, "Choose Imgur Text Color")
        if color is not None:
            self._imgur_color = color
            self._save_settings()

    def _choose_imgur_bg_color(self) -> None:
        """Choose Imgur background color."""
        if not hasattr(self, '_imgur_bg_color'):
            return
        color = StyledColorPicker.get_color(self._imgur_bg_color, self, "Choose Imgur Background Color")
        if color is not None:
            self._imgur_bg_color = color
            self._save_settings()

    def _choose_imgur_border_color(self) -> None:
        """Choose Imgur border color."""
        if not hasattr(self, '_imgur_border_color'):
            return
        color = StyledColorPicker.get_color(self._imgur_border_color, self, "Choose Imgur Border Color")
        if color is not None:
            self._imgur_border_color = color
            self._save_settings()

    # Gmail methods removed - archived in archive/gmail_feature/
    
    _SAVE_COALESCE_MS = 200

    def _save_settings(self) -> None:
        """Debounced save — coalesces rapid slider/checkbox changes.

        Each call resets a 200ms single-shot timer so only ONE actual
        write occurs after user input settles.  This reduces JSON writes
        from 10+/sec during slider drags to 1-2.
        """
        if getattr(self, "_loading", False):
            return
        if not getattr(self, "_save_coalesce_pending", False):
            self._save_coalesce_pending = True
            from PySide6.QtCore import QTimer
            QTimer.singleShot(self._SAVE_COALESCE_MS, self._save_settings_now)
        # If already pending, the timer is already ticking — we just
        # let it fire.  For very fast bursts this may occasionally
        # coalesce 2 writes instead of 1, which is acceptable.

    def _save_settings_now(self) -> None:
        """Perform the actual settings save (called by coalesce timer)."""
        self._save_coalesce_pending = False
        if getattr(self, "_loading", False):
            return

        from ui.tabs.widgets_tab_clock import save_clock_settings
        from ui.tabs.widgets_tab_weather import save_weather_settings
        from ui.tabs.widgets_tab_media import save_media_settings
        from ui.tabs.widgets_tab_reddit import save_reddit_settings
        from ui.tabs.widgets_tab_imgur import save_imgur_settings

        try:
            logger.debug("[WIDGETS_TAB] _save_settings_now start")
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)

        # Delegate per-widget saving to extraction modules
        clock_config, clock2_config, clock3_config = save_clock_settings(self)
        weather_config = save_weather_settings(self)
        media_config, spotify_vis_config = save_media_settings(self)
        reddit_config, reddit2_config = save_reddit_settings(self)

        existing_widgets = self._settings.get('widgets', {})
        if not isinstance(existing_widgets, dict):
            existing_widgets = {}

        # Global widget shadow configuration
        shadows_config = existing_widgets.get('shadows', {})
        if not isinstance(shadows_config, dict):
            shadows_config = {}
        shadows_config['enabled'] = self.widget_shadows_enabled.isChecked()
        existing_widgets['shadows'] = shadows_config
        existing_widgets['clock'] = clock_config
        existing_widgets['clock2'] = clock2_config
        existing_widgets['clock3'] = clock3_config
        existing_widgets['weather'] = weather_config
        existing_widgets['media'] = media_config
        existing_widgets['spotify_visualizer'] = spotify_vis_config
        existing_widgets['reddit'] = reddit_config
        existing_widgets['reddit2'] = reddit2_config

        # Imgur config - only save if dev features enabled
        imgur_config = save_imgur_settings(self)
        if imgur_config is not None:
            existing_widgets['imgur'] = imgur_config

        # Gmail config - archived, see archive/gmail_feature/

        try:
            logger.debug(
                "[WIDGETS_TAB] Saving widgets config: "
                "clock.enabled=%s, clock.analog_shadow_intense=%s, "
                "reddit.limit=%s, reddit.enabled=%s",
                clock_config.get('enabled'),
                clock_config.get('analog_shadow_intense'),
                reddit_config.get('limit'),
                reddit_config.get('enabled'),
            )
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)

        self._settings.set('widgets', existing_widgets)
        self._settings.save()

    def _update_vis_mode_sections(self) -> None:
        """Show/hide per-mode settings containers based on selected visualizer type."""
        try:
            mode = self.spotify_vis_type_combo.currentData() or 'spectrum'
        except Exception:
            mode = 'spectrum'

        containers = {
            'spectrum': getattr(self, '_spectrum_settings_container', None),
            'oscilloscope': getattr(self, '_osc_settings_container', None),
            'starfield': getattr(self, '_starfield_settings_container', None),
            'blob': getattr(self, '_blob_settings_container', None),
            'helix': getattr(self, '_helix_settings_container', None),
            'sine_wave': getattr(self, '_sine_wave_settings_container', None),
        }
        for m, container in containers.items():
            if container is not None:
                container.setVisible(m == mode)

    def _update_spotify_vis_sensitivity_enabled_state(self) -> None:
        try:
            recommended = self.spotify_vis_recommended.isChecked()
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
            recommended = True
        try:
            self.spotify_vis_sensitivity.setEnabled(not recommended)
            self.spotify_vis_sensitivity_label.setEnabled(not recommended)
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)

    def _update_spotify_vis_floor_enabled_state(self) -> None:
        try:
            dynamic = self.spotify_vis_dynamic_floor.isChecked()
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
            dynamic = True

        try:
            self.spotify_vis_manual_floor.setEnabled(not dynamic)
            self.spotify_vis_manual_floor_label.setEnabled(not dynamic)
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
    
    def _populate_timezones_for_combo(self, combo) -> None:
        timezones = get_common_timezones()
        for display_name, tz_str in timezones:
            combo.addItem(display_name, tz_str)

    def _populate_timezones(self) -> None:
        """Populate timezone dropdown with common timezones and UTC offsets."""
        self._populate_timezones_for_combo(self.clock_timezone)
    
    def _auto_detect_timezone(self) -> None:
        """Auto-detect user's local timezone."""
        detected_tz = get_local_timezone()
        
        # Find the timezone in the dropdown
        tz_index = self.clock_timezone.findData(detected_tz)
        if tz_index >= 0:
            self.clock_timezone.setCurrentIndex(tz_index)
            logger.info(f"Auto-detected timezone: {detected_tz}")
        else:
            # Try to add it if not found
            self.clock_timezone.addItem(f"Detected: {detected_tz}", detected_tz)
            self.clock_timezone.setCurrentIndex(self.clock_timezone.count() - 1)
            logger.info(f"Added detected timezone: {detected_tz}")
        
        # Save settings with new timezone
        self._save_settings()
    
    def _update_stack_status(self) -> None:
        """Update all widget stack status labels based on current settings.
        
        This is called when any position combo changes. It recalculates
        stacking predictions for all widgets and updates their status labels.
        """
        try:
            # Build current settings from UI state (not saved yet)
            widgets_config = self._build_current_widgets_config()
            
            # Define widget status label mappings
            status_mappings = [
                (WidgetType.CLOCK, 'clock_stack_status', 'clock_position', 'clock_monitor_combo'),
                (WidgetType.WEATHER, 'weather_stack_status', 'weather_position', 'weather_monitor_combo'),
                (WidgetType.MEDIA, 'media_stack_status', 'media_position', 'media_monitor_combo'),
                (WidgetType.REDDIT, 'reddit_stack_status', 'reddit_position', 'reddit_monitor_combo'),
                (WidgetType.REDDIT2, 'reddit2_stack_status', 'reddit2_position', 'reddit2_monitor_combo'),
            ]
            
            for widget_type, status_attr, pos_attr, mon_attr in status_mappings:
                status_label = getattr(self, status_attr, None)
                pos_combo = getattr(self, pos_attr, None)
                mon_combo = getattr(self, mon_attr, None)
                
                if status_label is None or pos_combo is None or mon_combo is None:
                    continue
                
                position = pos_combo.currentText()
                monitor = mon_combo.currentText()
                
                can_stack, message = get_position_status_for_widget(
                    widgets_config, widget_type, position, monitor
                )
                
                if message:
                    if can_stack:
                        status_label.setText(message)
                        status_label.setStyleSheet("color: #4CAF50; font-size: 11px; font-weight: bold;")
                    else:
                        status_label.setText(message)
                        status_label.setStyleSheet("color: #FF9800; font-size: 11px; font-weight: bold;")
                else:
                    status_label.setText("")
                    status_label.setStyleSheet("")
        except Exception as e:
            logger.debug("Stack status update failed: %s", e, exc_info=True)
    
    def _build_current_widgets_config(self) -> dict:
        """Build widgets config dict from current UI state.
        
        This creates a config dict that mirrors what would be saved,
        but from current UI values (before save).
        """
        config = {}
        
        # Clock
        config['clock'] = {
            'enabled': getattr(self, 'clock_enabled', None) and self.clock_enabled.isChecked(),
            'mode': getattr(self, 'clock_mode_combo', None) and self.clock_mode_combo.currentText() or 'Digital',
            'position': getattr(self, 'clock_position', None) and self.clock_position.currentText() or 'Top Right',
            'monitor': getattr(self, 'clock_monitor_combo', None) and self.clock_monitor_combo.currentText() or 'ALL',
            'font_size': getattr(self, 'clock_font_size', None) and self.clock_font_size.value() or 48,
            'show_seconds': getattr(self, 'clock_seconds', None) and self.clock_seconds.isChecked(),
            'show_timezone_label': getattr(self, 'clock_show_tz_label', None) and self.clock_show_tz_label.isChecked(),
        }
        
        # Clock 2
        config['clock2'] = {
            'enabled': getattr(self, 'clock2_enabled', None) and self.clock2_enabled.isChecked(),
            'monitor': getattr(self, 'clock2_monitor_combo', None) and self.clock2_monitor_combo.currentText() or 'ALL',
        }
        
        # Clock 3
        config['clock3'] = {
            'enabled': getattr(self, 'clock3_enabled', None) and self.clock3_enabled.isChecked(),
            'monitor': getattr(self, 'clock3_monitor_combo', None) and self.clock3_monitor_combo.currentText() or 'ALL',
        }
        
        # Weather
        config['weather'] = {
            'enabled': getattr(self, 'weather_enabled', None) and self.weather_enabled.isChecked(),
            'position': getattr(self, 'weather_position', None) and self.weather_position.currentText() or 'Top Left',
            'monitor': getattr(self, 'weather_monitor_combo', None) and self.weather_monitor_combo.currentText() or 'ALL',
            'font_size': getattr(self, 'weather_font_size', None) and self.weather_font_size.value() or 18,
            'show_forecast': getattr(self, 'weather_show_forecast', None) and self.weather_show_forecast.isChecked(),
        }
        
        # Media
        config['media'] = {
            'enabled': getattr(self, 'media_enabled', None) and self.media_enabled.isChecked(),
            'position': getattr(self, 'media_position', None) and self.media_position.currentText() or 'Bottom Right',
            'monitor': getattr(self, 'media_monitor_combo', None) and self.media_monitor_combo.currentText() or 'ALL',
            'font_size': getattr(self, 'media_font_size', None) and self.media_font_size.value() or 14,
            'artwork_size': getattr(self, 'media_artwork_size', None) and self.media_artwork_size.value() or 80,
        }
        
        # Reddit
        reddit_limit = 10
        reddit_items_combo = getattr(self, 'reddit_items', None)
        if reddit_items_combo is not None:
            try:
                reddit_limit = int(reddit_items_combo.currentText())
            except Exception as e:
                logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
                reddit_limit = 10
        config['reddit'] = {
            'enabled': getattr(self, 'reddit_enabled', None) and self.reddit_enabled.isChecked(),
            'position': getattr(self, 'reddit_position', None) and self.reddit_position.currentText() or 'Bottom Right',
            'monitor': getattr(self, 'reddit_monitor_combo', None) and self.reddit_monitor_combo.currentText() or 'ALL',
            'font_size': getattr(self, 'reddit_font_size', None) and self.reddit_font_size.value() or 18,
            'limit': reddit_limit,
        }
        
        # Reddit 2
        config['reddit2'] = {
            'enabled': getattr(self, 'reddit2_enabled', None) and self.reddit2_enabled.isChecked(),
            'position': getattr(self, 'reddit2_position', None) and self.reddit2_position.currentText() or 'Top Left',
            'monitor': getattr(self, 'reddit2_monitor_combo', None) and self.reddit2_monitor_combo.currentText() or 'ALL',
            'limit': 4,
        }
        try:
            config['reddit2']['limit'] = int(self.reddit2_items.currentText())
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
        
        # Spotify Visualizer
        config['spotify_visualizer'] = {
            'enabled': getattr(self, 'spotify_vis_enabled', None) and self.spotify_vis_enabled.isChecked(),
            'monitor': getattr(self, 'spotify_vis_monitor_combo', None) and self.spotify_vis_monitor_combo.currentText() or 'ALL',
            'bar_count': getattr(self, 'spotify_vis_bar_count', None) and self.spotify_vis_bar_count.value() or 16,
            'mode': getattr(self, 'spotify_vis_type_combo', None) and self.spotify_vis_type_combo.currentData() or 'spectrum',
            'osc_glow_enabled': getattr(self, 'osc_glow_enabled', None) and self.osc_glow_enabled.isChecked(),
            'osc_glow_intensity': (getattr(self, 'osc_glow_intensity', None) and self.osc_glow_intensity.value() or 50) / 100.0,
            'osc_reactive_glow': getattr(self, 'osc_reactive_glow', None) and self.osc_reactive_glow.isChecked(),
            'star_travel_speed': (getattr(self, 'star_travel_speed', None) and self.star_travel_speed.value() or 50) / 100.0,
            'star_reactivity': (getattr(self, 'star_reactivity', None) and self.star_reactivity.value() or 100) / 100.0,
            'blob_pulse': (getattr(self, 'blob_pulse', None) and self.blob_pulse.value() or 100) / 100.0,
            'helix_turns': getattr(self, 'helix_turns', None) and self.helix_turns.value() or 4,
            'helix_double': getattr(self, 'helix_double', None) and self.helix_double.isChecked(),
            'helix_speed': (getattr(self, 'helix_speed', None) and self.helix_speed.value() or 100) / 100.0,
            'helix_glow_enabled': getattr(self, 'helix_glow_enabled', None) and self.helix_glow_enabled.isChecked(),
            'helix_glow_intensity': (getattr(self, 'helix_glow_intensity', None) and self.helix_glow_intensity.value() or 50) / 100.0,
            'starfield_growth': (getattr(self, 'starfield_growth', None) and self.starfield_growth.value() or 200) / 100.0,
            'blob_growth': (getattr(self, 'blob_growth', None) and self.blob_growth.value() or 250) / 100.0,
            'helix_growth': (getattr(self, 'helix_growth', None) and self.helix_growth.value() or 200) / 100.0,
        }
        
        return config
