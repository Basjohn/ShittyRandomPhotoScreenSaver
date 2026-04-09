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
import os
import time
from copy import deepcopy
from typing import Optional, Dict, Any, Mapping
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QCheckBox, QPushButton, QSpinBox,
    QScrollArea, QButtonGroup, QGroupBox,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen

from core.settings.settings_manager import SettingsManager
from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.settings.defaults import get_default_settings
from core.settings.visualizer_settings_snapshot import (
    normalize_visualizer_mode_payload,
    normalize_visualizer_section_mapping,
)
from core.settings.visualizer_presets import (
    GLOBAL_ALLOWED_KEYS,
    MODE_KEY_PREFIXES,
    VISUALIZER_CUSTOM_STORAGE_KEY,
    apply_preset_to_config,
    build_normalized_custom_snapshot,
    extract_visualizer_snapshot,
    get_custom_preset_index,
    restore_visualizer_snapshot,
    resolve_preset_index_from_mapping,
)
from core.settings.visualizer_mode_registry import (
    get_default_visualizer_mode_id,
    get_preset_slider_attr,
)
from ui.tabs.shared_styles import (
    SPINBOX_STYLE,
    TOOLTIP_STYLE,
    COMBOBOX_STYLE,
    PAGE_TITLE_STYLE,
    NAV_TAB_FONT_STYLE,
    NAV_TAB_FONT_STYLE_ACTIVE,
    STATUS_LABEL_STYLE,
    SCROLL_AREA_STYLE,
    FORM_ROW_LABEL_STYLE,
    add_aligned_row,
    NoWheelSlider,  # noqa: F401 — re-exported
    style_group_box,
)
from ui.styled_popup import StyledColorPicker
from ui.widget_stack_predictor import WidgetType, get_position_status_for_widget
from widgets.timezone_utils import get_local_timezone, get_common_timezones
from ui.tabs.media.technical_controls import load_per_mode_technical_controls

logger = get_logger(__name__)


class _RainbowGlowLabel(QWidget):
    """Overlay widget that paints per-letter rainbow text with matching coloured glow.

    Qt rich-text does not support ``text-shadow``, so glow is done via
    QPainter.  Each letter gets a subtle 1px cardinal-direction glow at low
    alpha, then the crisp coloured letter on top.
    """

    _GLOW_ALPHA = 60

    def __init__(self, parent: QWidget | None = None, *, left_pad: int = 38) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        self._letters: list[tuple[str, QColor]] = []
        self._left_pad = left_pad

    def set_rainbow_text(self, text: str, hex_colors: list[str]) -> None:
        n = len(hex_colors)
        self._letters = [(ch, QColor(hex_colors[i % n])) for i, ch in enumerate(text)]
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        if not self._letters:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        font = self.font()
        fm = QFontMetrics(font)
        y_base = (self.height() + fm.ascent() - fm.descent()) // 2
        x = self._left_pad

        _offsets = ((-1, 0), (1, 0), (0, -1), (0, 1))

        for ch, color in self._letters:
            adv = fm.horizontalAdvance(ch)
            glow_c = QColor(color)
            glow_c.setAlpha(self._GLOW_ALPHA)
            p.setPen(QPen(glow_c, 0))
            for dx, dy in _offsets:
                p.drawText(x + dx, y_base + dy, ch)

            p.setPen(QPen(color, 0))
            p.drawText(x, y_base, ch)
            x += adv

        p.end()


_DEFAULT_VISUALIZER_MODE = get_default_visualizer_mode_id()
_DEPRECATED_VISUALIZER_EXPORT_SUFFIXES = ("energy_boost", "use_raw_energy")
_VISUALIZER_ADVANCED_ROOT_ATTRS = {
    "spectrum": ("_spectrum_advanced",),
    "oscilloscope": ("_osc_advanced",),
    "sine_wave": ("_sine_advanced", "_sine_advanced_host"),
    "blob": ("_blob_advanced",),
    "bubble": ("_bubble_advanced",),
}


class WidgetsTab(QWidget):
    """Widgets configuration tab."""
    
    # Signals
    widgets_changed = Signal()
    
    def __init__(
        self,
        settings: SettingsManager,
        parent: Optional[QWidget] = None,
        widget_defaults: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize widgets tab.
        
        Args:
            settings: Settings manager
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._settings = settings
        self._widget_defaults = widget_defaults or self._load_widget_defaults()
        self._current_subtab = 0
        self._subtab_scroll_cache: Dict[int, int] = {}
        self._scroll_area: Optional[QScrollArea] = None
        self._global_card_border_width = int(self._widget_default('global', 'card_border_width_px', 3))
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
        self._media_volume_fill_color = self._color_from_default('media', 'spotify_volume_fill_color', [66, 66, 66, 255])
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
        self._visualizer_adv_state: Dict[str, bool] = self._load_adv_states()
        self._visualizer_tech_state: Dict[str, bool] = self._load_tech_states()
        self._visualizer_tech_bucket_state: Dict[str, bool] = self._load_tech_bucket_states()
        self._visualizer_bucket_state: Dict[str, bool] = self._load_bucket_states()
        self._loading = True
        self._save_coalesce_pending = False
        _ui_start = time.perf_counter()
        self._setup_ui()
        self._perf_log("_setup_ui", _ui_start)
        _load_start = time.perf_counter()
        self._load_settings()
        self._perf_log("_load_settings", _load_start)
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

    # --- Visualizer advanced toggle persistence helpers -------------------

    _ADV_STATE_KEY = "ui.visualizer_adv_states"
    _TECH_STATE_KEY = "ui.visualizer_tech_states"
    _TECH_BUCKET_STATE_KEY = "ui.visualizer_tech_bucket_states"
    _BUCKET_STATE_KEY = "ui.visualizer_bucket_states"
    _SCROLL_POS_KEY = "ui.visualizer_scroll_positions"

    def _load_adv_states(self) -> Dict[str, bool]:
        """Load persisted advanced toggle states from SettingsManager."""
        raw = self._settings.get(self._ADV_STATE_KEY, {})
        if isinstance(raw, dict):
            return {k: bool(v) for k, v in raw.items()}
        return {}

    def _load_tech_states(self) -> Dict[str, bool]:
        """Load persisted Technical bucket toggle states from SettingsManager."""
        raw = self._settings.get(self._TECH_STATE_KEY, {})
        if isinstance(raw, dict):
            return {k: bool(v) for k, v in raw.items()}
        return {}

    def _load_tech_bucket_states(self) -> Dict[str, bool]:
        """Load persisted per-mode Technical subsection visibility states."""
        raw = self._settings.get(self._TECH_BUCKET_STATE_KEY, {})
        if isinstance(raw, dict):
            return {str(k): bool(v) for k, v in raw.items()}
        return {}

    def _load_bucket_states(self) -> Dict[str, bool]:
        """Load persisted per-mode visualizer bucket states."""
        raw = self._settings.get(self._BUCKET_STATE_KEY, {})
        if isinstance(raw, dict):
            return {str(k): bool(v) for k, v in raw.items()}
        return {}

    def get_visualizer_adv_state(self, mode: str) -> bool:
        """Return remembered expanded state for a visualizer mode."""
        return bool(self._visualizer_adv_state.get(mode, False))

    def set_visualizer_adv_state(self, mode: str, expanded: bool) -> None:
        """Persist expanded/collapsed state for a visualizer mode."""
        self._visualizer_adv_state[mode] = bool(expanded)
        try:
            self._settings.set(self._ADV_STATE_KEY, dict(self._visualizer_adv_state))
        except Exception:
            pass

    def get_visualizer_tech_state(self, mode: str) -> bool:
        """Return remembered Technical bucket state for a visualizer mode."""
        return bool(self._visualizer_tech_state.get(mode, True))

    def set_visualizer_tech_state(self, mode: str, expanded: bool) -> None:
        """Persist Technical bucket expanded/collapsed state for a visualizer mode."""
        self._visualizer_tech_state[mode] = bool(expanded)
        try:
            self._settings.set(self._TECH_STATE_KEY, dict(self._visualizer_tech_state))
        except Exception:
            pass

    def get_visualizer_tech_bucket_state(self, mode: str, bucket: str, default: bool = True) -> bool:
        """Return remembered visibility state for a per-mode Technical subsection."""
        states = getattr(self, "_visualizer_tech_bucket_state", {})
        key = f"{mode}:{bucket}"
        return bool(states.get(key, default))

    def set_visualizer_tech_bucket_state(self, mode: str, bucket: str, visible: bool) -> None:
        """Persist visibility state for a per-mode Technical subsection."""
        states = getattr(self, "_visualizer_tech_bucket_state", None)
        if not isinstance(states, dict):
            states = {}
            self._visualizer_tech_bucket_state = states
        states[f"{mode}:{bucket}"] = bool(visible)
        try:
            self._settings.set(self._TECH_BUCKET_STATE_KEY, dict(states))
        except Exception:
            pass

    def get_visualizer_bucket_state(self, mode: str, bucket: str, default: bool = False) -> bool:
        """Return remembered expanded state for a visualizer bucket."""
        states = getattr(self, "_visualizer_bucket_state", {})
        key = f"{mode}:{bucket}"
        return bool(states.get(key, default))

    def set_visualizer_bucket_state(self, mode: str, bucket: str, expanded: bool) -> None:
        """Persist expanded/collapsed state for a visualizer bucket."""
        states = getattr(self, "_visualizer_bucket_state", None)
        if not isinstance(states, dict):
            states = {}
            self._visualizer_bucket_state = states
        states[f"{mode}:{bucket}"] = bool(expanded)
        try:
            self._settings.set(self._BUCKET_STATE_KEY, dict(states))
        except Exception:
            pass

    def save_scroll_position(self, mode: str) -> None:
        """Save current scroll position for a visualizer mode."""
        sa = getattr(self, '_scroll_area', None)
        if sa is None:
            return
        vbar = sa.verticalScrollBar()
        if vbar is None:
            return
        positions = self._settings.get(self._SCROLL_POS_KEY, {})
        if not isinstance(positions, dict):
            positions = {}
        positions[mode] = vbar.value()
        try:
            self._settings.set(self._SCROLL_POS_KEY, positions)
        except Exception:
            pass

    def restore_scroll_position(self, mode: str) -> None:
        """Restore saved scroll position for a visualizer mode."""
        sa = getattr(self, '_scroll_area', None)
        if sa is None:
            return
        vbar = sa.verticalScrollBar()
        if vbar is None:
            return
        positions = self._settings.get(self._SCROLL_POS_KEY, {})
        if isinstance(positions, dict) and mode in positions:
            try:
                from PySide6.QtCore import QTimer
                pos = int(positions[mode])
                QTimer.singleShot(0, lambda: vbar.setValue(pos))
            except Exception:
                pass
    
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
        perf_scope = time.perf_counter()
        # Check dev features gate once at the start
        dev_features_enabled = os.getenv('SRPSS_ENABLE_DEV', 'false').lower() == 'true'
        
        # Create scroll area
        scroll = QScrollArea(self)
        self._scroll_area = scroll
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet(SCROLL_AREA_STYLE)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Title
        title = QLabel("Overlay Widgets")
        title.setStyleSheet(PAGE_TITLE_STYLE)
        layout.addWidget(title)

        # Subtab-style toggle buttons (Clocks / Weather / Media / Reddit / Defaults)
        subtab_row = QHBoxLayout()
        self._subtab_group = QButtonGroup(self)
        self._subtab_group.setExclusive(True)

        self._btn_clocks = QPushButton("Clocks")
        self._btn_weather = QPushButton("Weather")
        self._btn_media = QPushButton("Media")
        self._btn_visualizers = QPushButton("Visualizers")
        self._btn_reddit = QPushButton("Reddit")
        self._btn_defaults = QPushButton("Defaults")
        
        # Imgur button - gated by SRPSS_ENABLE_DEV
        if dev_features_enabled:
            self._btn_imgur = QPushButton("Imgur")

        button_style = (
            "QPushButton {"
            f" {NAV_TAB_FONT_STYLE}"
            " background-color: rgba(42, 42, 42, 215);"
            " color: #ffffff;"
            " border-radius: 8px;"
            " padding: 6px 18px;"
            " min-width: 90px;"
            " border: 1px solid #ffffff;"
            " }"
            "QPushButton:hover {"
            " background-color: rgba(52, 52, 52, 220);"
            " }"
            "QPushButton:checked {"
            f" {NAV_TAB_FONT_STYLE_ACTIVE}"
            " background-color: rgba(58, 58, 58, 220);"
            " border: 1px solid #ffffff;"
            " }"
        )

        # Build button list conditionally
        buttons = [
            self._btn_clocks,
            self._btn_weather,
            self._btn_media,
            self._btn_visualizers,
            self._btn_reddit,
            self._btn_defaults,
        ]
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
        from ui.tabs.widgets_tab_media import build_media_ui, build_visualizers_ui
        from ui.tabs.widgets_tab_reddit import build_reddit_ui

        section_start = time.perf_counter()
        self._clocks_container = build_clock_ui(self, layout)
        self._perf_log("build_clock_ui", section_start)
        layout.addWidget(self._clocks_container)

        section_start = time.perf_counter()
        self._weather_container = build_weather_ui(self, layout)
        self._perf_log("build_weather_ui", section_start)
        layout.addWidget(self._weather_container)

        section_start = time.perf_counter()
        self._media_container = build_media_ui(self, layout)
        self._perf_log("build_media_ui", section_start)
        layout.addWidget(self._media_container)

        section_start = time.perf_counter()
        self._visualizers_container = build_visualizers_ui(self, layout)
        self._perf_log("build_visualizers_ui", section_start)
        layout.addWidget(self._visualizers_container)

        section_start = time.perf_counter()
        self._reddit_container = build_reddit_ui(self, layout)
        self._perf_log("build_reddit_ui", section_start)
        layout.addWidget(self._reddit_container)

        self._defaults_container = self._build_defaults_section()
        layout.addWidget(self._defaults_container)

        # NOTE: Gmail widget removed - archived in archive/gmail_feature/

        # Imgur widget group - gated by SRPSS_ENABLE_DEV
        if dev_features_enabled:
            from ui.tabs.widgets_tab_imgur import build_imgur_ui
            section_start = time.perf_counter()
            self._imgur_container = build_imgur_ui(self, layout)
            self._perf_log("build_imgur_ui", section_start)
            layout.addWidget(self._imgur_container)

        layout.addStretch()

        # Set scroll area widget and add to main layout
        scroll.setWidget(content)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

        from ui.tabs.shared_styles import CIRCLE_CHECKBOX_STYLE, SLIDER_STYLE
        self.setStyleSheet(
            self.styleSheet()
            + SPINBOX_STYLE
            + TOOLTIP_STYLE
            + CIRCLE_CHECKBOX_STYLE
            + COMBOBOX_STYLE
            + SLIDER_STYLE
        )

        # Default to "Clocks" subtab
        self._subtab_containers: list[QWidget | None] = [
            self._clocks_container,
            self._weather_container,
            self._media_container,
            self._visualizers_container,
            self._reddit_container,
            self._defaults_container,
        ]
        if dev_features_enabled and hasattr(self, '_imgur_container'):
            self._subtab_containers.append(self._imgur_container)

        self._on_subtab_changed(0)
        self._perf_log("_setup_ui_sections", perf_scope)

    def _on_subtab_changed(self, subtab_id: int) -> None:
        """Show/hide widget sections based on selected subtab."""
        prev = self._current_subtab
        # Save outgoing subtab scroll position
        sa = getattr(self, '_scroll_area', None)
        if sa is not None and prev != subtab_id:
            try:
                self._subtab_scroll_cache[prev] = sa.verticalScrollBar().value()
            except Exception:
                pass

        self._current_subtab = int(subtab_id)
        for idx, container in enumerate(self._subtab_containers):
            if container is None:
                continue
            try:
                container.setVisible(subtab_id == idx)
            except Exception:
                pass

        # Restore incoming subtab scroll position (deferred so layout settles)
        if sa is not None and subtab_id in self._subtab_scroll_cache:
            saved = self._subtab_scroll_cache[subtab_id]
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: sa.verticalScrollBar().setValue(saved))

    def _build_defaults_section(self) -> QWidget:
        """Create the Defaults subtab content styled like other groups."""

        LABEL_WIDTH = 150

        group = QGroupBox("Global Widget Defaults")
        style_group_box(group)
        content_layout = QVBoxLayout(group)
        content_layout.setContentsMargins(18, 16, 18, 16)
        content_layout.setSpacing(12)

        # Drop shadow toggle row
        row = QHBoxLayout()
        row.setContentsMargins(0, 8, 0, 8)
        row.setSpacing(12)
        self.widget_shadows_enabled = QCheckBox("Enable Widget Drop Shadows")
        self.widget_shadows_enabled.setProperty("circleIndicator", True)
        self.widget_shadows_enabled.setToolTip(
            "Applies a subtle drop shadow to every widget card when enabled."
        )
        self.widget_shadows_enabled.setChecked(
            self._default_bool('shadows', 'enabled', True)
        )
        self.widget_shadows_enabled.stateChanged.connect(self._save_settings)
        row.addWidget(self.widget_shadows_enabled)
        row.addStretch()
        content_layout.addLayout(row)

        # Card border width row (aligned helper to keep wrap + gutter)
        border_row, _ = add_aligned_row(
            content_layout,
            "Card Border Width:",
            label_width=LABEL_WIDTH,
            wrap=False,
        )

        self.card_border_width_spin = QSpinBox()
        self.card_border_width_spin.setRange(0, 12)
        self.card_border_width_spin.setValue(self._global_card_border_width)
        self.card_border_width_spin.valueChanged.connect(
            self._on_global_border_width_changed
        )
        border_row.addWidget(self.card_border_width_spin)

        px_label = QLabel("px")
        px_label.setStyleSheet(FORM_ROW_LABEL_STYLE)
        px_label.setMinimumWidth(24)
        border_row.addWidget(px_label)
        border_row.addStretch()

        return group

    def _perf_log(self, label: str, start_time: float) -> None:
        if not is_perf_metrics_enabled():
            return
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        logger.info("[PERF][SETTINGS][WidgetsTab] %s in %.1f ms", label, elapsed_ms)
    
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
        # Snapshot current subtab's scroll position into cache before saving
        sa = getattr(self, "_scroll_area", None)
        if sa is not None:
            try:
                self._subtab_scroll_cache[self._current_subtab] = sa.verticalScrollBar().value()
            except Exception as e:
                logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
        state["subtab_scrolls"] = dict(self._subtab_scroll_cache)
        return state

    def restore_view_state(self, state: Dict[str, Any]) -> None:
        if not isinstance(state, dict):
            return
        # Restore per-subtab scroll cache
        saved_scrolls = state.get("subtab_scrolls")
        if isinstance(saved_scrolls, dict):
            for k, v in saved_scrolls.items():
                try:
                    self._subtab_scroll_cache[int(k)] = int(v)
                except (TypeError, ValueError):
                    pass
        subtab = state.get("subtab")
        try:
            subtab_id = int(subtab)
        except (TypeError, ValueError):
            subtab_id = 0
        button = self._subtab_group.button(subtab_id)
        if button is not None:
            button.setChecked(True)
            self._on_subtab_changed(subtab_id)
    
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
                'card_border_width_spin',
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
                'visualizers_enabled', 'vis_enabled_checkbox',
                'vis_border_opacity', 'vis_ghost_enabled',
                'vis_ghost_opacity_slider', 'vis_ghost_decay_slider',
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

            global_cfg = widgets.get('global', {}) if isinstance(widgets, dict) else {}
            try:
                border_width = int(global_cfg.get('card_border_width_px', self._widget_default('global', 'card_border_width_px', 3)))
            except Exception:
                border_width = self._widget_default('global', 'card_border_width_px', 3)
            border_width = max(0, min(12, border_width))
            self._global_card_border_width = border_width
            if hasattr(self, 'card_border_width_spin'):
                self.card_border_width_spin.setValue(border_width)

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

    def _snapshot_custom_visualizer_mode(self, mode_key: str, spotify_vis_config: dict) -> None:
        live_config = self._build_current_spotify_visualizer_config(spotify_vis_config)
        snapshot = build_normalized_custom_snapshot(mode_key, live_config)
        cache = self._settings.get(VISUALIZER_CUSTOM_STORAGE_KEY, {})
        if not isinstance(cache, dict):
            cache = {}
        cache[mode_key] = snapshot
        self._settings.set(VISUALIZER_CUSTOM_STORAGE_KEY, cache)

    def _restore_custom_visualizer_mode(self, mode_key: str, spotify_vis_config: dict) -> bool:
        cache = self._settings.get(VISUALIZER_CUSTOM_STORAGE_KEY, {})
        if not isinstance(cache, dict):
            return False
        payload = cache.get(mode_key)
        if not isinstance(payload, dict):
            return False
        return restore_visualizer_snapshot(mode_key, spotify_vis_config, payload)

    def _extract_visualizer_snapshot(self, mode_key: str, spotify_vis_config: dict) -> dict:
        return extract_visualizer_snapshot(mode_key, spotify_vis_config)

    def build_visualizer_preset_payload(self, mode_key: str) -> dict[str, Any]:
        """Construct a lean curated-preset payload from current settings."""
        widgets_cfg = self._settings.get('widgets', {})
        if not isinstance(widgets_cfg, dict):
            return {}
        spotify_vis_config = widgets_cfg.get('spotify_visualizer', {})
        if not isinstance(spotify_vis_config, dict):
            return {}

        live_config = self._build_current_spotify_visualizer_config(spotify_vis_config)
        normalized_live = normalize_visualizer_section_mapping(
            live_config,
            apply_preset_overlay=False,
        )
        snapshot = self._extract_visualizer_snapshot(mode_key, normalized_live)
        snapshot = normalize_visualizer_mode_payload(mode_key, snapshot)
        prefixes = MODE_KEY_PREFIXES.get(mode_key, [])
        for prefix in prefixes:
            for suffix in _DEPRECATED_VISUALIZER_EXPORT_SUFFIXES:
                snapshot.pop(f"{prefix}{suffix}", None)
        if not snapshot:
            return {}

        preset_index = self._resolve_visualizer_preset_index(mode_key, normalized_live)
        snapshot_copy = deepcopy(snapshot)

        payload: dict[str, Any] = {
            "mode": mode_key,
            "name": f"Custom {mode_key.title()} Preset",
            "preset_index": preset_index,
            "visualizer_preset_override": True,
            "visualizer_preset_mode": mode_key,
            "snapshot": {
                "widgets": {
                    "spotify_visualizer": snapshot_copy,
                },
            },
        }
        return payload

    @staticmethod
    def _is_key_for_mode(key: str, prefixes: list[str]) -> bool:
        if not prefixes:
            return False
        return any(key.startswith(prefix) for prefix in prefixes)

    @staticmethod
    def _is_global_visualizer_key(key: str) -> bool:
        if key in GLOBAL_ALLOWED_KEYS:
            return True
        return key in {
            'mode',
            'enabled',
            'visualizers_enabled',
            'monitor',
            'bar_count',
            'ghosting_enabled',
            'ghost_alpha',
            'ghost_decay',
            'rainbow_enabled',
            'rainbow_speed',
        }

    def _build_current_spotify_visualizer_config(
        self,
        base_config: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return a live spotify_visualizer config built from current UI state.

        This preserves any unrelated stored keys while overlaying the current
        widget state exactly as save_media_settings would serialize it.
        """
        config: dict[str, Any] = {}
        if isinstance(base_config, Mapping):
            config.update(deepcopy(dict(base_config)))

        # This helper is used by stack-status/live-preview paths before every
        # lazy-built Media/Visualizer control necessarily exists. In that case,
        # preserve the stored visualizer config instead of logging a misleading
        # preset/runtime failure.
        required_attrs = (
            'media_enabled',
            'media_position',
            'media_font_combo',
            'vis_enabled_checkbox',
            'vis_mode_combo',
        )
        if any(getattr(self, attr, None) is None for attr in required_attrs):
            return config

        try:
            from ui.tabs.widgets_tab_media import save_media_settings

            _, live_visualizer = save_media_settings(self)
            if isinstance(live_visualizer, dict):
                config.update(deepcopy(live_visualizer))
        except Exception:
            logger.debug("[WIDGETS_TAB] Failed to build live visualizer config", exc_info=True)

        return config

    def cycle_visualizer_preset(self, mode_key: str, direction: int) -> None:
        """Cycle the preset slider for *mode_key* by *direction* (+1/-1)."""
        if not direction:
            return
        slider = self._get_visualizer_preset_slider(mode_key)
        if slider is None:
            return
        if direction > 0:
            slider.cycle_next()
        else:
            slider.cycle_previous()

    def _get_active_visualizer_mode(self) -> str:
        """Return the active visualizer mode using the shared registry fallback."""
        try:
            mode = self.vis_mode_combo.currentData()
        except Exception:
            mode = None
        if isinstance(mode, str) and mode:
            return mode
        return _DEFAULT_VISUALIZER_MODE

    def _get_visualizer_preset_slider(self, mode: str):
        """Return the preset slider widget for *mode* using the shared registry."""
        try:
            slider_attr = get_preset_slider_attr(str(mode))
        except Exception:
            return None
        return getattr(self, slider_attr, None)

    def _get_visualizer_advanced_roots(self, mode: str) -> list[QWidget]:
        """Return advanced container roots for *mode*."""
        roots: list[QWidget] = []
        for attr in _VISUALIZER_ADVANCED_ROOT_ATTRS.get(mode, ()):
            root = getattr(self, attr, None)
            if isinstance(root, QWidget):
                roots.append(root)
        return roots

    @staticmethod
    def _resolve_visualizer_preset_index(mode: str, config: Mapping[str, Any] | None) -> int:
        """Resolve a mode preset index through the shared visualizer preset contract."""
        return resolve_preset_index_from_mapping(mode, config)

    def _on_global_border_width_changed(self, value: int) -> None:
        self._global_card_border_width = int(value)
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
            getattr(self, "_media_volume_fill_color", self._media_volume_fill_color),
            self,
            "Choose Spotify Volume Fill Color",
        )
        if color is not None:
            self._media_volume_fill_color = color
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
        self._auto_switch_preset_to_custom()
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

        spotify_vis_config = normalize_visualizer_section_mapping(
            spotify_vis_config,
            apply_preset_overlay=False,
        )

        existing_widgets = self._settings.get('widgets', {})
        if not isinstance(existing_widgets, dict):
            existing_widgets = {}

        # Global widget shadow configuration
        shadows_config = existing_widgets.get('shadows', {})
        if not isinstance(shadows_config, dict):
            shadows_config = {}
        shadows_config['enabled'] = self.widget_shadows_enabled.isChecked()
        existing_widgets['shadows'] = shadows_config

        global_config = existing_widgets.get('global', {})
        if not isinstance(global_config, dict):
            global_config = {}
        global_config['card_border_width_px'] = int(self._global_card_border_width)
        existing_widgets['global'] = global_config

        existing_widgets['clock'] = clock_config
        existing_widgets['clock2'] = clock2_config
        existing_widgets['clock3'] = clock3_config
        existing_widgets['weather'] = weather_config
        existing_widgets['media'] = media_config
        existing_widgets['spotify_visualizer'] = spotify_vis_config
        existing_widgets['reddit'] = reddit_config
        existing_widgets['reddit2'] = reddit2_config

        current_vis_mode = str(spotify_vis_config.get('mode', _DEFAULT_VISUALIZER_MODE) or _DEFAULT_VISUALIZER_MODE)
        current_preset_index = self._resolve_visualizer_preset_index(current_vis_mode, spotify_vis_config)
        current_custom_index = get_custom_preset_index(current_vis_mode)
        if current_preset_index == current_custom_index:
            snapshot = self._extract_visualizer_snapshot(current_vis_mode, spotify_vis_config)
            cache = self._settings.get(VISUALIZER_CUSTOM_STORAGE_KEY, {})
            if not isinstance(cache, dict):
                cache = {}
            cache[current_vis_mode] = snapshot
            self._settings.set(VISUALIZER_CUSTOM_STORAGE_KEY, cache)

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

    def _auto_switch_preset_to_custom(self) -> None:
        """Auto-switch to Custom preset when a visualizer-specific setting changes.

        Only fires when:
        1. The change did NOT come from the preset slider itself.
        2. We are not programmatically loading settings (_loading guard).
        3. The sender widget is a descendant of the current mode's advanced
           container (so clock/weather/etc. changes never trigger this).
        4. The current preset is NOT already Custom.
        """
        if getattr(self, '_preset_slider_changing', False):
            return
        if getattr(self, '_loading', False):
            return

        # Identify the sender and the current mode's advanced container.
        mode = self._get_active_visualizer_mode()
        adv_roots = self._get_visualizer_advanced_roots(mode)
        slider = self._get_visualizer_preset_slider(mode)
        if not adv_roots or slider is None:
            return

        # If already on Custom, nothing to switch.
        custom_index = slider.custom_index() if hasattr(slider, 'custom_index') else slider.preset_index()
        if slider.preset_index() == custom_index:
            return

        # Check sender is inside the advanced container
        try:
            sender = self.sender()
        except Exception:
            sender = None

        # Sender-less saves happen during preset application and other
        # programmatic flows. They must never be treated as "advanced edit"
        # signals or we will silently force curated presets back to Custom.
        if sender is None:
            return

        w = sender
        inside_adv = False
        while w is not None:
            if any(w is root for root in adv_roots):
                inside_adv = True
                break
            w = w.parent()
        if not inside_adv:
            return

        slider.set_preset_index(custom_index)

    def _force_visualizer_preset_to_custom(self, mode: str | None = None) -> None:
        """Switch the active visualizer preset to Custom without relying on sender ancestry."""
        if getattr(self, '_preset_slider_changing', False):
            return
        if getattr(self, '_loading', False):
            return

        if mode is None:
            mode = self._get_active_visualizer_mode()

        slider = self._get_visualizer_preset_slider(mode)
        if slider is None:
            return

        custom_index = slider.custom_index() if hasattr(slider, 'custom_index') else slider.preset_index()
        if slider.preset_index() == custom_index:
            return
        slider.set_preset_index(custom_index)

    def _on_visualizer_preset_changed(self, mode_key: str, preset_index: int) -> None:
        """Handle preset slider changes by applying curated settings before save."""
        if getattr(self, '_loading', False):
            return

        slider = self._get_visualizer_preset_slider(mode_key)
        if slider is None:
            return

        custom_index = slider.custom_index() if hasattr(slider, 'custom_index') else get_custom_preset_index(mode_key)

        widgets_cfg = self._settings.get('widgets', {}) or {}
        spotify_vis_config = widgets_cfg.get('spotify_visualizer', {})
        if not isinstance(spotify_vis_config, dict):
            spotify_vis_config = {}

        prev_index = self._resolve_visualizer_preset_index(mode_key, spotify_vis_config)
        move_to_custom_pending = bool(getattr(slider, "_pending_move_to_custom", False))

        if preset_index == custom_index:
            restored = False
            if move_to_custom_pending:
                self._snapshot_custom_visualizer_mode(mode_key, spotify_vis_config)
                try:
                    setattr(slider, "_pending_move_to_custom", False)
                except Exception:
                    pass
            else:
                restored = self._restore_custom_visualizer_mode(mode_key, spotify_vis_config)
            spotify_vis_config[f"preset_{mode_key}"] = custom_index
            if restored:
                self._loading = True
                try:
                    from ui.tabs.widgets_tab_media import load_media_settings

                    full_widgets = dict(widgets_cfg)
                    full_widgets['spotify_visualizer'] = dict(spotify_vis_config)
                    load_media_settings(self, full_widgets)
                    load_per_mode_technical_controls(self, spotify_vis_config)
                finally:
                    self._loading = False
            if move_to_custom_pending:
                self._save_settings_now()
            else:
                self._save_settings()
            return

        if move_to_custom_pending:
            try:
                setattr(slider, "_pending_move_to_custom", False)
            except Exception:
                pass

        if prev_index == custom_index:
            self._snapshot_custom_visualizer_mode(mode_key, spotify_vis_config)

        working_config = dict(spotify_vis_config)
        working_config['mode'] = mode_key
        applied = apply_preset_to_config(mode_key, preset_index, working_config)
        spotify_vis_config.update(applied)
        spotify_vis_config[f"preset_{mode_key}"] = preset_index

        # Push preset values into UI widgets so the debounced save reads
        # the correct (preset) values instead of stale widget state.
        # Pass full widgets dict (with media intact) so load_media_settings
        # doesn't reset unrelated widgets to defaults.
        if applied != working_config:
            full_widgets = dict(widgets_cfg)
            # Pass the full spotify_vis_config (with all global keys) so the
            # media loader doesn't drop unrelated settings when the preset
            # only overrides a per-mode subset.
            full_widgets['spotify_visualizer'] = dict(spotify_vis_config)
            self._loading = True
            try:
                from ui.tabs.widgets_tab_media import load_media_settings
                load_media_settings(self, full_widgets)
                load_per_mode_technical_controls(self, spotify_vis_config)
            finally:
                self._loading = False

        self._save_settings()

    def _update_vis_mode_sections(self) -> None:
        """Show/hide per-mode settings containers based on selected visualizer type."""
        try:
            mode = self._get_active_visualizer_mode()
        except Exception:
            mode = _DEFAULT_VISUALIZER_MODE

        # Save scroll position for the previous mode before switching
        prev_mode = getattr(self, '_last_vis_mode_section', None)
        if prev_mode and prev_mode != mode:
            self.save_scroll_position(prev_mode)
        self._last_vis_mode_section = mode

        containers = {
            'spectrum': getattr(self, '_spectrum_settings_container', None),
            'oscilloscope': getattr(self, '_osc_settings_container', None),
            'blob': getattr(self, '_blob_settings_container', None),
            'sine_wave': getattr(self, '_sine_wave_settings_container', None),
            'bubble': getattr(self, '_bubble_settings_container', None),
        }
        for m, container in containers.items():
            if container is not None:
                container.setVisible(m == mode)

        # Restore scroll position for the new mode
        if prev_mode != mode:
            self.restore_scroll_position(mode)

        # --- Per-mode rainbow sync ---
        # Stash the outgoing mode's rainbow state, restore the incoming mode's.
        cache = getattr(self, '_rainbow_per_mode', None)
        if cache is not None and hasattr(self, 'rainbow_enabled') and hasattr(self, 'rainbow_speed_slider'):
            if prev_mode and prev_mode != mode:
                cache[prev_mode] = (
                    self.rainbow_enabled.isChecked(),
                    self.rainbow_speed_slider.value(),
                )
            if mode in cache:
                enabled, speed = cache[mode]
            else:
                enabled, speed = False, 50
            self.rainbow_enabled.blockSignals(True)
            self.rainbow_speed_slider.blockSignals(True)
            self.rainbow_enabled.setChecked(enabled)
            self.rainbow_speed_slider.setValue(speed)
            self.rainbow_speed_label.setText(f"{speed / 100.0:.2f}")
            self.rainbow_enabled.blockSignals(False)
            self.rainbow_speed_slider.blockSignals(False)
            self._update_rainbow_visibility()

    _RAINBOW_COLORS = [
        "#FF0000", "#FF7F00", "#FFFF00", "#00FF00",
        "#0000FF", "#4B0082", "#8F00FF",
    ]

    def _update_rainbow_visibility(self) -> None:
        """Show/hide rainbow speed slider and apply rainbow text easter egg."""
        try:
            enabled = self.rainbow_enabled.isChecked()
            container = getattr(self, '_rainbow_speed_container', None)
            if container is not None:
                container.setVisible(enabled)

            glow_effect = getattr(self, '_rainbow_glow_effect', None)
            if glow_effect is not None:
                glow_effect.setEnabled(enabled)

            plain_label = getattr(self, '_rainbow_plain_label', None)
            if plain_label is not None:
                palette = plain_label.palette()
                color = QColor("#ffffff")
                if enabled:
                    color = QColor("#f7f7f7")
                palette.setColor(plain_label.foregroundRole(), color)
                plain_label.setPalette(palette)
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
                        status_label.setStyleSheet(
                            f"{STATUS_LABEL_STYLE} color: #4CAF50;"
                        )
                    else:
                        status_label.setText(message)
                        status_label.setStyleSheet(
                            f"{STATUS_LABEL_STYLE} color: #FF9800;"
                        )
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
            if hasattr(self, 'reddit2_items'):
                config['reddit2']['limit'] = int(self.reddit2_items.currentText())
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
        
        # Spotify Visualizer
        stored_widgets = self._settings.get("widgets", {}) or {}
        base_visualizer = {}
        if isinstance(stored_widgets, Mapping):
            candidate = stored_widgets.get("spotify_visualizer", {})
            if isinstance(candidate, Mapping):
                base_visualizer = dict(candidate)
        config['spotify_visualizer'] = self._build_current_spotify_visualizer_config(base_visualizer)
        
        return config
