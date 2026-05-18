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
    QComboBox, QPushButton,
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
from rendering.widget_descriptors import (
    apply_widget_section_save_results,
    build_widget_section_buttons,
    build_widget_stack_preview_config,
    collect_widget_section_containers,
    collect_widget_section_save_results,
    collect_widget_section_signal_block_targets,
    collect_widget_stack_status_targets,
    get_default_widget_section_index,
    get_widget_default_init_descriptors,
    get_widget_lazy_dependency_indices,
    get_widget_lazy_bootstrap_indices,
    get_widget_settings_section_descriptors,
    get_widget_stack_preview_descriptors,
    load_widget_sections,
    resolve_widget_section_index_from_view_state,
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
    NoWheelSlider,  # noqa: F401 — re-exported
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
    "devcurve": ("_devcurve_normal", "_devcurve_advanced", "_devcurve_advanced_host"),
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
        lazy_sections: bool = False,
        initial_view_state: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize widgets tab.
        
        Args:
            settings: Settings manager
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._settings = settings
        self._provided_widget_defaults = widget_defaults
        self._lazy_sections = bool(lazy_sections)
        self._initial_view_state = dict(initial_view_state) if isinstance(initial_view_state, dict) else {}
        self._widget_section_descriptors = get_widget_settings_section_descriptors()
        self._widget_defaults = self._load_widget_defaults()
        self._current_subtab = get_default_widget_section_index(self._widget_section_descriptors)
        self._subtab_scroll_cache: Dict[int, int] = {}
        self._scroll_area: Optional[QScrollArea] = None
        self._subtab_content_built: set[int] = set()
        self._subtab_host_layouts: list[QVBoxLayout | None] = []
        self._initialize_descriptor_default_attrs()
        self._visualizer_adv_state: Dict[str, bool] = self._load_adv_states()
        self._visualizer_tech_state: Dict[str, bool] = self._load_tech_states()
        self._visualizer_tech_bucket_state: Dict[str, bool] = self._load_tech_bucket_states()
        self._visualizer_bucket_state: Dict[str, bool] = self._load_bucket_states()
        self._gmail_bucket_state: Dict[str, bool] = self._load_gmail_bucket_states()
        self._widget_bucket_state: Dict[str, bool] = self._load_widget_bucket_states()
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
            loaded_defaults = widgets_defaults if isinstance(widgets_defaults, dict) else {}
            if isinstance(self._provided_widget_defaults, dict):
                merged = dict(loaded_defaults)
                for section, section_defaults in self._provided_widget_defaults.items():
                    if (
                        isinstance(section_defaults, dict)
                        and isinstance(merged.get(section), dict)
                    ):
                        merged_section = dict(merged[section])
                        merged_section.update(section_defaults)
                        merged[section] = merged_section
                    else:
                        merged[section] = section_defaults
                return merged
            return loaded_defaults
        except Exception:
            logger.debug("[WIDGETS_TAB] Failed to load widget defaults", exc_info=True)
            return self._provided_widget_defaults if isinstance(self._provided_widget_defaults, dict) else {}

    def _initialize_descriptor_default_attrs(self) -> None:
        """Seed standard widget default-backed attrs from canonical descriptor metadata."""
        for descriptor in get_widget_default_init_descriptors():
            if descriptor.value_kind == "color":
                value = self._color_from_default(
                    descriptor.section,
                    descriptor.key,
                    descriptor.fallback,
                )
            elif descriptor.value_kind == "int":
                value = self._default_int(
                    descriptor.section,
                    descriptor.key,
                    descriptor.fallback,
                )
            else:
                value = self._widget_default(
                    descriptor.section,
                    descriptor.key,
                    descriptor.fallback,
                )
            setattr(self, descriptor.attr_name, value)
    
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
    _GMAIL_BUCKET_STATE_KEY = "ui.gmail_bucket_states"
    _WIDGET_BUCKET_STATE_KEY = "ui.widget_bucket_states"

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

    def _load_gmail_bucket_states(self) -> Dict[str, bool]:
        """Load persisted Gmail bucket expanded states."""
        raw = self._settings.get(self._GMAIL_BUCKET_STATE_KEY, {})
        if isinstance(raw, dict):
            return {str(k): bool(v) for k, v in raw.items()}
        return {}

    def _load_widget_bucket_states(self) -> Dict[str, bool]:
        """Load persisted non-Gmail widget bucket expanded states."""
        raw = self._settings.get(self._WIDGET_BUCKET_STATE_KEY, {})
        if isinstance(raw, dict):
            return {str(k): bool(v) for k, v in raw.items()}
        return {}

    def get_gmail_bucket_state(self, bucket: str, default: bool = False) -> bool:
        """Return remembered expanded state for a Gmail bucket."""
        states = getattr(self, "_gmail_bucket_state", {})
        return bool(states.get(bucket, default))

    def set_gmail_bucket_state(self, bucket: str, expanded: bool) -> None:
        """Persist expanded/collapsed state for a Gmail bucket."""
        states = getattr(self, "_gmail_bucket_state", None)
        if not isinstance(states, dict):
            states = {}
            self._gmail_bucket_state = states
        if states.get(bucket) == bool(expanded):
            return
        states[bucket] = bool(expanded)
        try:
            self._settings.set(self._GMAIL_BUCKET_STATE_KEY, dict(states))
        except Exception:
            pass

    def get_widget_bucket_state(self, section: str, bucket: str, default: bool = False) -> bool:
        """Return remembered expanded state for a non-Gmail widget bucket."""
        states = getattr(self, "_widget_bucket_state", {})
        return bool(states.get(f"{section}:{bucket}", default))

    def set_widget_bucket_state(self, section: str, bucket: str, expanded: bool) -> None:
        """Persist expanded/collapsed state for a non-Gmail widget bucket."""
        states = getattr(self, "_widget_bucket_state", None)
        if not isinstance(states, dict):
            states = {}
            self._widget_bucket_state = states
        key = f"{section}:{bucket}"
        if states.get(key) == bool(expanded):
            return
        states[key] = bool(expanded)
        try:
            self._settings.set(self._WIDGET_BUCKET_STATE_KEY, dict(states))
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

    def _resolve_initial_subtab_id(self) -> int:
        """Resolve the first Widgets subtab to build/show."""
        state = self._initial_view_state if isinstance(self._initial_view_state, dict) else {}
        if not state:
            raw_state = self._settings.get('ui.tab_state', {})
            if isinstance(raw_state, dict):
                widgets_state = raw_state.get('widgets', {})
                if isinstance(widgets_state, dict):
                    candidate = widgets_state.get('view_state')
                    if isinstance(candidate, dict):
                        state = candidate
        return resolve_widget_section_index_from_view_state(state, self._widget_section_descriptors)

    def _create_subtab_host(self) -> tuple[QWidget, QVBoxLayout]:
        host = QWidget()
        host_layout = QVBoxLayout(host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(0)
        return host, host_layout

    def _build_lazy_subtab_content(self, subtab_id: int) -> None:
        """Build the requested subtab section only when needed."""
        if subtab_id in self._subtab_content_built:
            return
        if subtab_id < 0 or subtab_id >= len(getattr(self, "_subtab_containers", [])):
            return

        for dep_index in get_widget_lazy_dependency_indices(
            subtab_id,
            self._widget_section_descriptors,
        ):
            if dep_index != subtab_id:
                self._build_lazy_subtab_content(dep_index)

        host_layout = self._subtab_host_layouts[subtab_id] if subtab_id < len(self._subtab_host_layouts) else None
        if host_layout is None:
            return

        build_start = time.perf_counter()
        self._build_section_descriptor_content(
            self._widget_section_descriptors[subtab_id],
            host_layout,
            subtab_id,
        )

        if is_perf_metrics_enabled():
            self._perf_log(f"lazy_build_subtab_{subtab_id}", build_start)

        self._load_settings()

    def ensure_all_sections_built(self) -> None:
        """Materialize every lazy section for programmatic callers/tests.

        The visible settings dialog keeps lazy construction for UX/perf, but
        callers that explicitly request the WidgetsTab instance historically
        expected the standard section controls to exist immediately.
        """
        if not self._lazy_sections:
            return
        for idx in range(len(self._widget_section_descriptors)):
            self._build_lazy_subtab_content(idx)

    def ensure_programmatic_media_sections_built(self) -> None:
        """Materialize the programmatic media sections expected by older callers.

        Keep this intentionally narrow. Building every lazy section here can
        pull in heavier widget settings surfaces and leave more timers/background
        activity alive than simple programmatic media tests actually need.
        """
        if not self._lazy_sections:
            return
        wanted = {"media", "visualizers", "defaults"}
        for idx, descriptor in enumerate(self._widget_section_descriptors):
            if descriptor.section_id in wanted:
                self._build_lazy_subtab_content(idx)
    
    def _setup_ui(self) -> None:
        """Setup tab UI with scroll area."""
        perf_scope = time.perf_counter()
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

        button_style = (
            "QPushButton {"
            f" {NAV_TAB_FONT_STYLE}"
            " background-color: rgba(42, 42, 42, 215);"
            " color: #ffffff;"
            " border-radius: 8px;"
            " padding: 6px 18px;"
            " min-width: 70px;"
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

        buttons = build_widget_section_buttons(
            self,
            self._subtab_group,
            button_style,
            self._widget_section_descriptors,
        )
        for btn in buttons:
            subtab_row.addWidget(btn)

        subtab_row.addStretch()
        layout.addLayout(subtab_row)

        self._subtab_group.idClicked.connect(self._on_subtab_changed)
        default_subtab = get_default_widget_section_index(self._widget_section_descriptors)
        if 0 <= default_subtab < len(buttons):
            buttons[default_subtab].setChecked(True)

        self._subtab_containers = []
        self._subtab_host_layouts = []
        if self._lazy_sections:
            for _idx, _btn in enumerate(buttons):
                host, host_layout = self._create_subtab_host()
                self._subtab_containers.append(host)
                self._subtab_host_layouts.append(host_layout)
                layout.addWidget(host)
            layout.addStretch()
            initial_subtab = self._resolve_initial_subtab_id()
            for bootstrap_index in get_widget_lazy_bootstrap_indices(
                initial_subtab,
                self._widget_section_descriptors,
            ):
                self._build_lazy_subtab_content(bootstrap_index)
            if 0 <= initial_subtab < len(buttons):
                buttons[initial_subtab].setChecked(True)
            self._on_subtab_changed(initial_subtab)
        else:
            for idx, descriptor in enumerate(self._widget_section_descriptors):
                section_start = time.perf_counter()
                self._build_section_descriptor_content(descriptor, layout, idx)
                builder_name = descriptor.builder_name or descriptor.method_name or descriptor.section_id
                self._perf_log(builder_name, section_start)

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

        if not self._lazy_sections:
            self._subtab_containers = list(
                collect_widget_section_containers(self, self._widget_section_descriptors)
            )
            self._on_subtab_changed(default_subtab)
        self._perf_log("_setup_ui_sections", perf_scope)

    def _build_section_descriptor_content(self, descriptor, host_layout: QVBoxLayout, subtab_id: int) -> None:
        """Build one descriptor-owned WidgetsTab section into the target layout."""
        if hasattr(self, descriptor.container_attr_name):
            self._subtab_content_built.add(subtab_id)
            return

        builder = descriptor.resolve_builder(self)
        widget = builder(self, host_layout) if descriptor.builder_module else builder()
        setattr(self, descriptor.container_attr_name, widget)
        host_layout.addWidget(widget)
        self._subtab_content_built.add(subtab_id)

    def _on_subtab_changed(self, subtab_id: int) -> None:
        """Show/hide widget sections based on selected subtab."""
        if self._lazy_sections:
            self._build_lazy_subtab_content(int(subtab_id))
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
        current_subtab = int(getattr(self, "_current_subtab", 0))
        state: Dict[str, Any] = {"subtab": current_subtab}
        if 0 <= current_subtab < len(self._widget_section_descriptors):
            state["subtab_id"] = self._widget_section_descriptors[current_subtab].section_id
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
        subtab_id = resolve_widget_section_index_from_view_state(state, self._widget_section_descriptors)
        button = self._subtab_group.button(subtab_id)
        if button is not None:
            button.setChecked(True)
            self._on_subtab_changed(subtab_id)
    
    def _load_settings(self) -> None:
        """Load settings from settings manager.
        
        Delegates per-widget loading to extraction modules.
        """
        from ui.tabs.widgets_tab_gmail import GMAIL_SIGNAL_BLOCK_ATTRS

        # Block all signals during load to prevent unintended saves
        blockers = []
        try:
            widgets_value = self._settings.get('widgets', {})
            if isinstance(widgets_value, dict):
                widgets = dict(widgets_value)
            else:
                widgets = {}

            # Collect all widget controls that need signal blocking
            _base_signal_block_attrs = (
                'visualizers_enabled', 'vis_enabled_checkbox',
                'vis_border_opacity', 'vis_ghost_enabled',
                'vis_ghost_opacity_slider', 'vis_ghost_decay_slider',
                'devcurve_base_level',
                'devcurve_motion_power', 'devcurve_idle_motion',
                'devcurve_idle_speed',
                'devcurve_smoothness',
                'devcurve_growth',
                'devcurve_active_layer_order',
                'devcurve_active_layer_outline_width',
                'devcurve_ghost_enabled', 'devcurve_ghost_opacity', 'devcurve_ghost_decay',
                'devcurve_layer_bass_enabled', 'devcurve_layer_bass_alpha', 'devcurve_layer_bass_offset',
                'devcurve_layer_vocals_enabled', 'devcurve_layer_vocals_alpha', 'devcurve_layer_vocals_offset',
                'devcurve_layer_mids_enabled', 'devcurve_layer_mids_alpha', 'devcurve_layer_mids_offset',
                'devcurve_layer_transients_enabled', 'devcurve_layer_transients_alpha', 'devcurve_layer_transients_offset',
            )
            for widget in collect_widget_section_signal_block_targets(
                self,
                extra_attr_names=_base_signal_block_attrs + GMAIL_SIGNAL_BLOCK_ATTRS,
            ):
                widget.blockSignals(True)
                blockers.append(widget)

            # Delegate per-widget loading through the canonical section descriptors.
            load_widget_sections(self, widgets, self._widget_section_descriptors)

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
        
        # DEBUG: Log what keys are in the snapshot before filtering
        logger.debug("[VIS_PRESETS_SAVE] Before filtering for %s: %d keys", mode_key, len(snapshot))
        
        snapshot = normalize_visualizer_mode_payload(mode_key, snapshot)
        
        # DEBUG: Log what keys remain after filtering
        logger.debug("[VIS_PRESETS_SAVE] After filtering for %s: %d keys - %s", 
                     mode_key, len(snapshot), list(snapshot.keys())[:10])
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

        try:
            logger.debug("[WIDGETS_TAB] _save_settings_now start")
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)

        existing_widgets = self._settings.get('widgets', {})
        if not isinstance(existing_widgets, dict):
            existing_widgets = {}

        section_results = collect_widget_section_save_results(
            self,
            existing_widgets,
            self._widget_section_descriptors,
        )
        spotify_vis_config = section_results.get('spotify_visualizer', {})

        apply_widget_section_save_results(
            existing_widgets,
            section_results,
            exclude_keys=("spotify_visualizer",),
            descriptors=self._widget_section_descriptors,
        )

        clock_config = existing_widgets.get('clock', {})
        weather_config = existing_widgets.get('weather', {})
        media_config = existing_widgets.get('media', {})
        reddit_config = existing_widgets.get('reddit', {})

        # Merge current-mode visualizer settings into the existing config so
        # that other modes' persisted keys are preserved across save cycles.
        # save_media_settings only collects shared + active-mode keys; without
        # the merge every save would wipe all inactive-mode settings.
        existing_vis = existing_widgets.get('spotify_visualizer', {})
        if not isinstance(existing_vis, dict):
            existing_vis = {}
        existing_vis.update(spotify_vis_config)

        spotify_vis_config = normalize_visualizer_section_mapping(
            existing_vis,
            apply_preset_overlay=False,
        )

        existing_widgets['spotify_visualizer'] = spotify_vis_config

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

        try:
            logger.debug(
                "[WIDGETS_TAB] Saving widgets config: "
                "clock.enabled=%s, shadows=%s/%s/%s, reddit.limit=%s, reddit.enabled=%s",
                clock_config.get('enabled'),
                existing_widgets.get('shadows', {}).get('enabled') if isinstance(existing_widgets.get('shadows'), dict) else None,
                existing_widgets.get('shadows', {}).get('text_enabled') if isinstance(existing_widgets.get('shadows'), dict) else None,
                existing_widgets.get('shadows', {}).get('header_enabled') if isinstance(existing_widgets.get('shadows'), dict) else None,
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
        # Use REPLACE semantics, not merge — .update() would leave stale
        # custom mode-specific keys (e.g. blob_shaper_enabled) that the
        # preset didn't include, causing settings to "stick" across presets.
        restore_visualizer_snapshot(mode_key, spotify_vis_config, applied)
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
            'devcurve': getattr(self, '_devcurve_settings_container', None),
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

            for target in collect_widget_stack_status_targets(self):
                status_label = target.status_label
                widget_type = WidgetType(target.widget_type_key)

                can_stack, message = get_position_status_for_widget(
                    widgets_config, widget_type, target.position_value, target.monitor_value
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
        config = build_widget_stack_preview_config(self)

        # Spotify Visualizer
        stored_widgets = self._settings.get("widgets", {}) or {}
        base_visualizer = {}
        if isinstance(stored_widgets, Mapping):
            candidate = stored_widgets.get("spotify_visualizer", {})
            if isinstance(candidate, Mapping):
                base_visualizer = dict(candidate)
        config['spotify_visualizer'] = self._build_current_spotify_visualizer_config(base_visualizer)
        
        return config


