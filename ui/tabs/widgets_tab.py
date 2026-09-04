"""
Widgets configuration tab for settings dialog.

Allows users to configure overlay widgets:
- Clock widget (enable, position, format, size, font, style)
- Weather widget (enable, position, location, API key, size, font, style)
- Media/Spotify widget
- Reddit widget

Per-widget UI, load, and save logic is delegated to extraction modules:
  widgets_tab_clock.py, widgets_tab_weather.py, widgets_tab_media.py,
  widgets_tab_reddit.py
"""
import os
import time
from typing import Optional, Dict, Any, Mapping
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QCheckBox,
    QScrollArea, QButtonGroup, QGroupBox,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen

from core.settings.settings_manager import SettingsManager
from core.threading.manager import ThreadManager
from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.settings.defaults import get_default_settings
from rendering.widget_descriptors import (
    CUSTOM_POSITION_OPTION_LABEL,
    apply_widget_section_save_results,
    build_widget_section_buttons,
    build_widget_stack_preview_config,
    collect_widget_section_containers,
    collect_widget_section_save_results,
    collect_widget_section_signal_block_targets,
    collect_widget_section_signal_block_targets_for_sections,
    collect_widget_stack_status_targets,
    get_widget_custom_position_option_descriptors,
    get_default_widget_section_index,
    get_widget_custom_resize_lock_descriptors,
    get_widget_default_init_descriptors,
    get_widget_lazy_dependency_indices,
    get_widget_lazy_bootstrap_indices,
    get_widget_programmatic_dependency_indices,
    get_widget_family_descriptor,
    get_widget_family_descriptors,
    get_widget_runtime_descriptor,
    get_widget_settings_section_descriptor,
    get_widgets_tab_settings_section_descriptors,
    get_widget_stack_preview_descriptors,
    has_saved_custom_layout_for_widget,
    is_custom_position_selected_for_widget,
    load_widget_section,
    load_widget_sections,
    restore_all_custom_layouts_to_authored_layout,
    restore_all_widget_positions_to_application_defaults,
    resolve_widget_section_index_from_view_state,
    sync_custom_layout_restore_routes,
)
from core.settings.capability_activation import (
    is_widget_family_activated,
    normalize_widget_capability_state,
    set_widget_family_activated,
)
from ui.tabs import shared_styles
from ui.tabs.shared_styles import (
    NAV_TAB_FONT_STYLE,
    NAV_TAB_FONT_STYLE_ACTIVE,
    STATUS_LABEL_STYLE,
    SCROLL_AREA_STYLE,
    style_group_box,
    NoWheelSlider,  # noqa: F401 — re-exported
)
from ui.flow_layout import FlowContainer
from ui.tabs.visualizer_settings_context import VisualizerSettingsContextMixin

_WIDGET_MODULE_ROW_MIN_WIDTH = 220
from ui.styled_popup import StyledColorPicker, StyledPopup
from ui.widget_stack_predictor import WidgetType, get_position_status_for_widget
from widgets.timezone_utils import get_local_timezone, get_common_timezones

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


class WidgetsTab(VisualizerSettingsContextMixin, QWidget):
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
        self._widget_section_descriptors = get_widgets_tab_settings_section_descriptors()
        self._widget_defaults = self._load_widget_defaults()
        self._current_subtab = get_default_widget_section_index(self._widget_section_descriptors)
        self._subtab_scroll_cache: Dict[int, int] = {}
        self._scroll_area: Optional[QScrollArea] = None
        self._subtab_content_built: set[int] = set()
        self._subtab_content_building: set[int] = set()
        self._hydrated_widget_sections: set[str] = set()
        self._blocked_unhydrated_save_sections: set[str] = set()
        self._subtab_host_layouts: list[QVBoxLayout | None] = []
        self._custom_resize_lock_notice_labels: Dict[str, QLabel] = {}
        self._family_activation_checkboxes: Dict[str, QCheckBox] = {}
        self._initialize_descriptor_default_attrs()
        self._initialize_visualizer_settings_context_state()
        self._gmail_bucket_state: Dict[str, bool] = self._load_gmail_bucket_states()
        self._widget_bucket_state: Dict[str, bool] = self._load_widget_bucket_states()
        self._loading = True
        self._save_coalesce_pending = False
        self._save_coalesce_token = 0
        _ui_start = time.perf_counter()
        self._setup_ui()
        self._perf_log("_setup_ui", _ui_start)
        _load_start = time.perf_counter()
        self._load_settings()
        self._refresh_custom_resize_lock_state()
        self._perf_log("_load_settings", _load_start)
        self._loading = False
        # Final pass so a restored/deactivated family lands on Setup rather than
        # a hidden pill's dead page (switch is suppressed while _loading).
        self._apply_family_pill_visibility()

        logger.debug("WidgetsTab created")

    def _mark_widget_section_hydrated(self, section_id: str) -> None:
        section = str(section_id or "").strip()
        if not section:
            return
        self._hydrated_widget_sections.add(section)
        self._blocked_unhydrated_save_sections.discard(section)
        try:
            logger.debug(
                "[WIDGETS_HYDRATION] phase=load_complete section=%s hydrated=true",
                section,
            )
        except Exception:
            pass

    def _can_save_widget_section(self, section_id: str) -> bool:
        section = str(section_id or "").strip()
        if not section:
            return True
        if not getattr(self, "_lazy_sections", False):
            return True
        return section in getattr(self, "_hydrated_widget_sections", set())

    def _get_hydrated_widget_save_descriptors(self):
        """Return sections that normal save orchestration is allowed to collect."""
        return tuple(
            descriptor
            for descriptor in self._widget_section_descriptors
            if self._can_save_widget_section(descriptor.section_id)
        )

    def _log_widget_hydration_blocked_save(self, section_id: str) -> None:
        section = str(section_id or "").strip()
        if not section:
            return
        blocked = getattr(self, "_blocked_unhydrated_save_sections", set())
        if section in blocked:
            return
        blocked.add(section)
        self._blocked_unhydrated_save_sections = blocked
        try:
            logger.warning(
                "[WIDGETS_HYDRATION][WARNING] blocked_save_from_unhydrated_section=%s",
                section,
            )
        except Exception:
            pass
    
    def load_from_settings(self) -> None:
        """Reload all UI controls from settings manager (called after preset change)."""
        self._loading = True
        try:
            self._load_settings()
            self._refresh_custom_position_option_state()
            self._refresh_custom_resize_lock_state()
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
    
    
    
    
    
    
    
    
    
    

    # --- Visualizer advanced toggle persistence helpers -------------------

    _GMAIL_BUCKET_STATE_KEY = "ui.gmail_bucket_states"
    _WIDGET_BUCKET_STATE_KEY = "ui.widget_bucket_states"













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

    @staticmethod
    def _set_combo_item_enabled(combo: QComboBox, text: str, enabled: bool) -> None:
        idx = combo.findText(text, Qt.MatchFlag.MatchFixedString)
        if idx < 0:
            return
        model = combo.model()
        if model is None:
            return
        item = model.item(idx) if hasattr(model, "item") else None
        if item is not None and hasattr(item, "setEnabled"):
            item.setEnabled(bool(enabled))

    def _iter_custom_position_combo_bindings(self):
        return get_widget_custom_position_option_descriptors()

    def _refresh_custom_position_option_state(self) -> None:
        widgets_cfg = self._settings.get("widgets", {}) or {}
        if not isinstance(widgets_cfg, Mapping):
            widgets_cfg = {}

        for binding in self._iter_custom_position_combo_bindings():
            combo = getattr(self, binding.combo_attr, None)
            if combo is None:
                continue
            descriptor = get_widget_runtime_descriptor(binding.widget_id)
            if descriptor is None or not descriptor.supports_custom_position_slot:
                continue
            settings_key = descriptor.get_effective_position_settings_key()
            current_section = widgets_cfg.get(settings_key, {})
            if not isinstance(current_section, Mapping):
                current_section = {}
            current_position = str(
                current_section.get("position", binding.fallback_position) or binding.fallback_position
            )
            has_custom = has_saved_custom_layout_for_widget(binding.widget_id, widgets_cfg)
            allow_custom = has_custom or current_position.strip().lower() == CUSTOM_POSITION_OPTION_LABEL.lower()
            self._set_combo_item_enabled(combo, CUSTOM_POSITION_OPTION_LABEL, allow_custom)
            if not allow_custom and combo.currentText().strip().lower() == CUSTOM_POSITION_OPTION_LABEL.lower():
                self._set_combo_text(combo, binding.fallback_position)

    def _iter_custom_resize_lock_bindings(self):
        return get_widget_custom_resize_lock_descriptors()

    def _widgets_config_for_custom_resize_lock_state(self) -> Mapping[str, Any]:
        widgets_cfg = self._settings.get("widgets", {}) or {}
        if not isinstance(widgets_cfg, Mapping):
            widgets_cfg = {}
        return widgets_cfg

    def _is_custom_resize_lock_active(
        self,
        binding,
        widgets_cfg: Mapping[str, Any],
    ) -> bool:
        for combo_attr in binding.position_combo_attrs:
            combo = getattr(self, combo_attr, None)
            if combo is not None and str(combo.currentText()).strip().lower() == CUSTOM_POSITION_OPTION_LABEL.lower():
                return True
        return any(
            is_custom_position_selected_for_widget(widget_id, widgets_cfg)
            for widget_id in binding.widget_ids
        )

    def _ensure_custom_resize_lock_notice(self, binding) -> QLabel | None:
        section_id = str(binding.section_id)
        if not section_id:
            return None
        existing = self._custom_resize_lock_notice_labels.get(section_id)
        if existing is not None:
            return existing

        anchor_control = getattr(self, str(binding.anchor_attr), None)
        if anchor_control is None:
            return None
        row_widget = anchor_control.parentWidget()
        parent_widget = row_widget.parentWidget() if row_widget is not None else None
        parent_layout = parent_widget.layout() if parent_widget is not None else None
        if row_widget is None or parent_layout is None:
            return None

        notice = QLabel(parent_widget)
        notice.setWordWrap(True)
        notice.setTextFormat(Qt.TextFormat.RichText)
        notice.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        notice.setOpenExternalLinks(False)
        notice.setStyleSheet(
            "color: rgba(255, 176, 82, 235);"
            "font-size: 11px;"
            "padding: 0 0 6px 0;"
        )
        notice.setText(
            "<span style='color: rgba(255, 176, 82, 235);'>"
            "<a href='disable-custom' style='color: rgba(255, 176, 82, 255); text-decoration: underline;'>"
            "Disable Custom Mode</a> To Change!</span>"
        )
        notice.linkActivated.connect(lambda _link, sid=section_id: self._on_custom_resize_lock_link_activated(sid))
        insert_index = parent_layout.indexOf(row_widget)
        if insert_index < 0:
            parent_layout.addWidget(notice)
        else:
            parent_layout.insertWidget(insert_index + 1, notice)
        notice.hide()
        self._custom_resize_lock_notice_labels[section_id] = notice
        return notice

    def _refresh_custom_resize_lock_state(self) -> None:
        widgets_cfg = self._widgets_config_for_custom_resize_lock_state()
        active_sections: set[str] = set()
        for binding in self._iter_custom_resize_lock_bindings():
            section_id = str(binding.section_id)
            lock_active = self._is_custom_resize_lock_active(binding, widgets_cfg)
            controls = [getattr(self, attr, None) for attr in binding.control_attrs]
            controls = [control for control in controls if control is not None]
            for control in controls:
                control.setEnabled(not lock_active)
            notice = self._ensure_custom_resize_lock_notice(binding)
            if notice is not None:
                notice.setVisible(bool(lock_active))
            if lock_active:
                active_sections.add(section_id)

        for section_id, notice in list(self._custom_resize_lock_notice_labels.items()):
            if section_id not in active_sections:
                notice.hide()

    def _on_custom_resize_lock_link_activated(self, section_id: str) -> None:
        binding = next(
            (entry for entry in self._iter_custom_resize_lock_bindings() if entry.section_id == section_id),
            None,
        )
        if binding is None:
            return
        confirmed = StyledPopup.question(
            self,
            "Disable Custom Mode",
            "This will return your widgets to their last known good locations, are you sure?",
            yes_text="Revert",
            no_text="Nope",
            default_to_yes=False,
        )
        if not confirmed:
            return
        widgets_cfg = self._settings.get_widgets_map()
        restored_any = restore_all_custom_layouts_to_authored_layout(widgets_cfg)
        if not restored_any:
            return
        self._save_coalesce_token += 1
        self._save_coalesce_pending = False
        self._settings.set_widgets_map(widgets_cfg, emit_change=False)
        self._settings.save()
        self.load_from_settings()

    def _on_reset_widget_positions_to_defaults_clicked(self) -> None:
        """Reset widget positions/monitors to the current profile's shipped defaults."""

        confirmed = StyledPopup.question(
            self,
            "Reset Widget Positions",
            "This will restore all widget positions and monitor routes to the application defaults for this profile.",
            yes_text="Reset",
            no_text="Cancel",
            default_to_yes=False,
        )
        if not confirmed:
            return

        widgets_cfg = self._settings.get_widgets_map()
        default_widgets_cfg = get_default_settings().get("widgets", {})
        restored_any = restore_all_widget_positions_to_application_defaults(
            widgets_cfg,
            default_widgets_config=default_widgets_cfg if isinstance(default_widgets_cfg, Mapping) else {},
        )
        if not restored_any:
            return

        sync_custom_layout_restore_routes(widgets_cfg)
        self._save_coalesce_token += 1
        self._save_coalesce_pending = False
        self._settings.set_widgets_map(widgets_cfg, emit_change=False)
        self._settings.save()
        self.load_from_settings()

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
        resolved = resolve_widget_section_index_from_view_state(state, self._widget_section_descriptors)
        # Never land initial navigation on a deactivated family's page.
        return self._admit_section_index(resolved)

    def _create_subtab_host(self) -> tuple[QWidget, QVBoxLayout]:
        host = QWidget()
        host_layout = QVBoxLayout(host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(0)
        return host, host_layout

    def _build_lazy_subtab_content(self, subtab_id: int) -> None:
        """Build the requested subtab section only when needed."""
        # Admission: a section owned by a deactivated family is never built or
        # hydrated — redirect to SETUP first.
        subtab_id = self._admit_section_index(subtab_id)
        if subtab_id in self._subtab_content_built:
            return
        if subtab_id in self._subtab_content_building:
            return
        if subtab_id < 0 or subtab_id >= len(getattr(self, "_subtab_containers", [])):
            return

        self._subtab_content_building.add(subtab_id)
        try:
            previous_loading = self._loading
            self._loading = True
            dependency_indices = get_widget_lazy_dependency_indices(
                subtab_id,
                self._widget_section_descriptors,
            )
            try:
                requested_section = self._widget_section_descriptors[subtab_id].section_id
                dependency_sections = [
                    self._widget_section_descriptors[idx].section_id
                    for idx in dependency_indices
                    if 0 <= idx < len(self._widget_section_descriptors)
                ]
                logger.debug(
                    "[WIDGETS_HYDRATION] phase=build_start requested=%s dependency_chain=%s",
                    requested_section,
                    ">".join(dependency_sections + [requested_section]),
                )
            except Exception:
                pass
            for dep_index in dependency_indices:
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
                section_id = self._widget_section_descriptors[subtab_id].section_id
                self._perf_log(f"lazy_build_subtab_{subtab_id}:{section_id}", build_start)

            self._load_widget_sections_by_id(
                self._widget_section_descriptors[subtab_id].section_id,
            )
        finally:
            self._loading = previous_loading
            self._subtab_content_building.discard(subtab_id)

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

    def ensure_programmatic_widget_sections_built(self, *section_ids: str) -> None:
        """Materialize a narrow descriptor-owned set of sections for callers/tests."""
        if not self._lazy_sections:
            return
        target_ids = tuple(section_id for section_id in section_ids if isinstance(section_id, str) and section_id)
        if not target_ids:
            return
        for idx in get_widget_programmatic_dependency_indices(
            target_ids,
            self._widget_section_descriptors,
        ):
            self._build_lazy_subtab_content(idx)

    def ensure_programmatic_media_sections_built(self) -> None:
        """Materialize the narrow media/visualizer/defaults contract for callers/tests.

        Keep this intentionally narrow. Building every lazy section here can
        pull in heavier widget settings surfaces and leave more timers/background
        activity alive than simple programmatic media tests actually need.
        """
        self.ensure_programmatic_widget_sections_built("media")
    
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
        shared_styles.apply_shared_label_style(title, "PAGE_TITLE_STYLE")
        layout.addWidget(title)

        # Subtab-style toggle buttons (Setup / Clocks / Weather / ...). A
        # responsive FlowLayout wraps the pills onto extra rows instead of
        # clipping at narrower Settings widths.
        subtab_container = FlowContainer(h_spacing=8, v_spacing=8)
        self._subtab_group = QButtonGroup(self)
        self._subtab_group.setExclusive(True)

        button_style = shared_styles.WIDGET_NAV_PILL_STYLE


        buttons = build_widget_section_buttons(
            self,
            self._subtab_group,
            button_style,
            self._widget_section_descriptors,
        )
        for btn in buttons:
            shared_styles.bind_shared_styles(
                btn, "WIDGET_NAV_PILL_STYLE", base_style=""
            )
            subtab_container.addWidget(btn)

        layout.addWidget(subtab_container)

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

        shared_styles.bind_shared_styles(
            self,
            "SPINBOX_STYLE",
            "TOOLTIP_STYLE",
            "CIRCLE_CHECKBOX_STYLE",
            "COMBOBOX_STYLE",
            "SLIDER_STYLE",
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

    # ---- E2 capability SETUP subtab ----------------------------------------

    def _build_setup_ui(self) -> QWidget:
        """Build the always-present Widgets SETUP page (family capability activation).

        Application-level *activation* is distinct from a widget instance's
        ordinary ``enabled`` checkbox: deactivating a family hides its settings
        pill and stops it running, but keeps its stored configuration for later
        reactivation. Built only from cheap presentation-neutral catalog metadata.
        """
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        blurb = QLabel(
            "Activate the widget families you want available. Deactivating a "
            "family hides its settings and stops it running; its saved settings "
            "are kept for when you reactivate it."
        )
        blurb.setWordWrap(True)
        blurb.setStyleSheet(STATUS_LABEL_STYLE)
        layout.addWidget(blurb)

        widgets_config = self._settings.get('widgets', {})
        if not isinstance(widgets_config, dict):
            widgets_config = {}

        # Styled module frame, matching the Transitions SETUP / normal Settings
        # grammar (§6C), with a responsive activation grid (§6D).
        modules_group = QGroupBox("Widget Modules")
        style_group_box(modules_group)
        modules_layout = QVBoxLayout(modules_group)
        modules_layout.setContentsMargins(0, 12, 0, 0)
        modules_layout.setSpacing(8)

        grid_host = FlowContainer(h_spacing=18, v_spacing=8)
        self._family_activation_checkboxes = {}
        for family in get_widget_family_descriptors():
            row = QCheckBox(family.label)
            row.setProperty("circleIndicator", True)
            row.setMinimumWidth(_WIDGET_MODULE_ROW_MIN_WIDTH)
            if family.description:
                row.setToolTip(family.description)
            row.setChecked(is_widget_family_activated(widgets_config, family.family_id))
            row.toggled.connect(
                lambda checked, fid=family.family_id: self._on_family_activation_toggled(fid, checked)
            )
            self._family_activation_checkboxes[family.family_id] = row
            grid_host.addWidget(row)
        modules_layout.addWidget(grid_host)

        # Enable/Disable All in a wrapping flow so they stay reachable (§6E).
        action_host = FlowContainer(h_spacing=10, v_spacing=8)
        enable_all = QPushButton("Enable All")
        disable_all = QPushButton("Disable All")
        shared_styles.bind_shared_styles(
            enable_all, "WIDGET_SETUP_ACTION_STYLE", base_style=""
        )
        shared_styles.bind_shared_styles(
            disable_all, "WIDGET_SETUP_ACTION_STYLE", base_style=""
        )
        enable_all.clicked.connect(lambda: self._set_all_family_activation(True))
        disable_all.clicked.connect(lambda: self._set_all_family_activation(False))
        action_host.addWidget(enable_all)
        action_host.addWidget(disable_all)
        modules_layout.addWidget(action_host)

        layout.addWidget(modules_group)
        layout.addStretch()
        return container

    def _widget_section_index(self, section_id: str) -> int:
        for idx, descriptor in enumerate(self._widget_section_descriptors):
            if descriptor.section_id == section_id:
                return idx
        return -1

    def _family_activated(self, family_id: str) -> bool:
        """Return current activation for a family (live checkbox, else settings)."""
        checkboxes = getattr(self, "_family_activation_checkboxes", {})
        checkbox = checkboxes.get(family_id)
        if checkbox is not None:
            return bool(checkbox.isChecked())
        widgets_config = self._settings.get('widgets', {})
        if not isinstance(widgets_config, dict):
            widgets_config = {}
        return is_widget_family_activated(widgets_config, family_id)

    def _section_is_deactivated_family(self, section_id: str) -> bool:
        """True when a section belongs to a currently deactivated widget family."""
        for family in get_widget_family_descriptors():
            if family.settings_section_id == section_id:
                return not self._family_activated(family.family_id)
        return False

    def _admit_section_index(self, index) -> int:
        """Resolve a requested subtab index, redirecting a deactivated family to SETUP.

        Centralized admission derived from the neutral widget-family catalog: a
        section owned by a deactivated family must never be built/hydrated or
        selected. Applied before every build/selection so restored, initial, and
        programmatic navigation cannot resolve a hidden family's page.
        """
        try:
            idx = int(index)
        except (TypeError, ValueError):
            idx = -1
        if 0 <= idx < len(self._widget_section_descriptors):
            section_id = self._widget_section_descriptors[idx].section_id
            if self._section_is_deactivated_family(section_id):
                setup_idx = self._widget_section_index("setup")
                return setup_idx if setup_idx >= 0 else idx
        return idx

    def _family_section_button(self, family) -> Optional[QPushButton]:
        descriptor = get_widget_settings_section_descriptor(
            family.settings_section_id, self._widget_section_descriptors
        )
        if descriptor is None:
            return None
        return getattr(self, descriptor.button_attr_name, None)

    def _apply_family_pill_visibility(self) -> None:
        """Show/hide family settings pills to match current activation state."""
        checkboxes = getattr(self, "_family_activation_checkboxes", {})
        deactivated_indices: set[int] = set()
        for family in get_widget_family_descriptors():
            checkbox = checkboxes.get(family.family_id)
            activated = checkbox.isChecked() if checkbox is not None else True
            button = self._family_section_button(family)
            if button is not None:
                button.setVisible(activated)
            if not activated:
                idx = self._widget_section_index(family.settings_section_id)
                if idx >= 0:
                    deactivated_indices.add(idx)
        # If the currently shown subtab belongs to a now-deactivated family,
        # return to Setup rather than leaving a dead page selected.
        if not getattr(self, "_loading", False) and self._current_subtab in deactivated_indices:
            self._select_setup_subtab()

    def _select_setup_subtab(self) -> None:
        setup_index = self._widget_section_index("setup")
        if setup_index < 0:
            return
        button = self._subtab_group.button(setup_index)
        if button is not None:
            button.setChecked(True)
        self._on_subtab_changed(setup_index)

    def _apply_family_dependency_state(self) -> None:
        """Enforce widget-family dependencies live on the SETUP checkboxes.

        A family whose required families are not all activated is forced off,
        disabled, and given a "Requires <X>" tooltip; when its dependency is
        satisfied it is re-enabled (but never auto-reactivated). The single
        dependency authority is the neutral family catalog.
        """
        checkboxes = getattr(self, "_family_activation_checkboxes", {})
        active = {fid: cb.isChecked() for fid, cb in checkboxes.items()}
        for family in get_widget_family_descriptors():
            checkbox = checkboxes.get(family.family_id)
            if checkbox is None or not family.required_family_ids:
                continue
            deps_ok = all(
                active.get(req, is_widget_family_activated(self._settings.get('widgets', {}), req))
                for req in family.required_family_ids
            )
            checkbox.setEnabled(deps_ok)
            if not deps_ok:
                if checkbox.isChecked():
                    checkbox.blockSignals(True)
                    checkbox.setChecked(False)
                    checkbox.blockSignals(False)
                    active[family.family_id] = False
                req_labels = ", ".join(
                    desc.label
                    for req in family.required_family_ids
                    if (desc := get_widget_family_descriptor(req)) is not None
                )
                checkbox.setToolTip(f"Requires {req_labels}")
            else:
                checkbox.setToolTip(family.description or "")

    def _retire_widget_section(self, section_id: str) -> None:
        """Destroy a built family Settings section so it is genuinely rebuildable.

        Removes the section container, clears its built/hydrated ownership, and
        deletes its control attributes so loaders/savers/builders treat it as
        unbuilt. Persisted per-family configuration is untouched (save preserves
        unhydrated sections). SETUP is never retired.
        """
        if not section_id or section_id == "setup":
            return
        descriptor = get_widget_settings_section_descriptor(
            section_id, self._widget_section_descriptors
        )
        if descriptor is None:
            return
        idx = self._widget_section_index(section_id)
        container = getattr(self, descriptor.container_attr_name, None)
        if container is None:
            return  # not built; nothing to retire
        try:
            container.setParent(None)
            container.deleteLater()
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
        try:
            delattr(self, descriptor.container_attr_name)
        except Exception:
            pass
        if idx >= 0:
            self._subtab_content_built.discard(idx)
        self._hydrated_widget_sections.discard(section_id)
        self._blocked_unhydrated_save_sections.discard(section_id)
        # Delete control/guard attributes so the descriptor-driven load/save/
        # build guards (all hasattr-based) see the section as unbuilt again.
        stale_attrs = (
            set(descriptor.loader_guard_attrs)
            | set(descriptor.saver_guard_attrs)
            | set(descriptor.signal_block_attrs)
        )
        for attr in stale_attrs:
            if hasattr(self, attr):
                try:
                    delattr(self, attr)
                except Exception:
                    pass

    def _retire_deactivated_family_sections(self) -> None:
        """Retire built Settings pages for any currently deactivated family."""
        checkboxes = getattr(self, "_family_activation_checkboxes", {})
        for family in get_widget_family_descriptors():
            checkbox = checkboxes.get(family.family_id)
            activated = checkbox.isChecked() if checkbox is not None else True
            if not activated:
                self._retire_widget_section(family.settings_section_id)

    def _on_family_activation_toggled(self, family_id: str, checked: bool) -> None:
        self._apply_family_dependency_state()
        self._apply_family_pill_visibility()
        self._retire_deactivated_family_sections()
        if not getattr(self, "_loading", False):
            self._save_settings()

    def _set_all_family_activation(self, activated: bool) -> None:
        checkboxes = getattr(self, "_family_activation_checkboxes", {})
        changed = False
        for checkbox in checkboxes.values():
            if checkbox.isChecked() != activated:
                checkbox.blockSignals(True)
                checkbox.setChecked(activated)
                checkbox.blockSignals(False)
                changed = True
        self._apply_family_dependency_state()
        self._apply_family_pill_visibility()
        self._retire_deactivated_family_sections()
        if changed and not getattr(self, "_loading", False):
            self._save_settings()

    def _load_family_activation_state(self) -> None:
        """Refresh SETUP activation checkboxes from persisted settings."""
        checkboxes = getattr(self, "_family_activation_checkboxes", {})
        if not checkboxes:
            return
        widgets_config = self._settings.get('widgets', {})
        if not isinstance(widgets_config, dict):
            widgets_config = {}
        for family_id, checkbox in checkboxes.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(is_widget_family_activated(widgets_config, family_id))
            checkbox.blockSignals(False)
        self._apply_family_dependency_state()
        self._apply_family_pill_visibility()

    def _apply_family_activation_to_config(self, widgets_config: dict) -> None:
        """Write the SETUP activation checkbox states into a widgets config.

        Applies the neutral capability dependency normalization so an invalid
        combination (e.g. Visualizers on while Media off) is repaired before
        persistence rather than deferred to a later load/runtime seam.
        """
        checkboxes = getattr(self, "_family_activation_checkboxes", {})
        for family_id, checkbox in checkboxes.items():
            set_widget_family_activated(widgets_config, family_id, bool(checkbox.isChecked()))
        normalize_widget_capability_state(widgets_config)

    def _on_subtab_changed(self, subtab_id: int) -> None:
        """Show/hide widget sections based on selected subtab."""
        # Admission: never select a deactivated family's page; redirect to SETUP
        # and sync the nav button (programmatic setChecked does not re-fire this).
        admitted = self._admit_section_index(subtab_id)
        if admitted != int(subtab_id):
            redirect_button = self._subtab_group.button(admitted)
            if redirect_button is not None:
                redirect_button.setChecked(True)
        subtab_id = admitted
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
            def _restore() -> None:
                sa.verticalScrollBar().setValue(saved)

            self._schedule_owned_single_shot(0, _restore)

    def _perf_log(self, label: str, start_time: float) -> None:
        if not is_perf_metrics_enabled():
            return
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        logger.info("[PERF][SETTINGS][WidgetsTab] %s in %.1f ms", label, elapsed_ms)
    
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
        # Never restore navigation onto a deactivated family's page.
        subtab_id = self._admit_section_index(subtab_id)
        button = self._subtab_group.button(subtab_id)
        if button is not None:
            button.setChecked(True)
            self._on_subtab_changed(subtab_id)
    
    def _load_settings(self) -> None:
        """Load settings from settings manager.
        
        Delegates per-widget loading to extraction modules.
        """
        # Block all signals during load to prevent unintended saves
        blockers = []
        try:
            widgets_value = self._settings.get('widgets', {})
            if isinstance(widgets_value, dict):
                widgets = dict(widgets_value)
            else:
                widgets = {}

            # Collect all widget controls that need signal blocking
            for widget in collect_widget_section_signal_block_targets(
                self,
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
        
        # Refresh SETUP family-activation checkboxes from persisted settings.
        try:
            self._load_family_activation_state()
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)

        # Update stack status labels after loading settings
        try:
            self._refresh_custom_position_option_state()
            self._update_stack_status()
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)

    def _load_widget_sections_by_id(self, *section_ids: str) -> None:
        """Hydrate only the requested descriptor-owned sections from settings."""

        ordered_ids: list[str] = []
        seen_ids: set[str] = set()
        for section_id in section_ids:
            normalized_id = str(section_id or "").strip()
            if not normalized_id or normalized_id in seen_ids:
                continue
            seen_ids.add(normalized_id)
            ordered_ids.append(normalized_id)
        if not ordered_ids:
            return

        blockers = []
        previous_loading = self._loading
        self._loading = True
        try:
            widgets_value = self._settings.get("widgets", {})
            if isinstance(widgets_value, dict):
                widgets = dict(widgets_value)
            else:
                widgets = {}

            for widget in collect_widget_section_signal_block_targets_for_sections(
                self,
                tuple(ordered_ids),
                descriptors=self._widget_section_descriptors,
            ):
                widget.blockSignals(True)
                blockers.append(widget)

            for section_id in ordered_ids:
                loaded = load_widget_section(
                    self,
                    section_id,
                    widgets,
                    self._widget_section_descriptors,
                )
                if not loaded:
                    try:
                        logger.debug(
                            "[WIDGETS_HYDRATION] phase=load_deferred section=%s hydrated=false",
                            section_id,
                        )
                    except Exception:
                        pass

        finally:
            for widget in blockers:
                try:
                    widget.blockSignals(False)
                except Exception as e:
                    logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)
            self._loading = previous_loading

        try:
            self._refresh_custom_position_option_state()
            self._refresh_custom_resize_lock_state()
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

    _SAVE_COALESCE_MS = 200

    def _save_settings(self) -> None:
        """Debounced save — coalesces rapid slider/checkbox changes.

        Each call resets a 200ms single-shot timer so only ONE actual
        write occurs after user input settles.  This reduces JSON writes
        from 10+/sec during slider drags to 1-2.
        """
        if getattr(self, "_loading", False):
            return
        self._refresh_custom_resize_lock_state()
        self._auto_switch_preset_to_custom()
        self._save_coalesce_pending = True
        self._save_coalesce_token += 1
        token = self._save_coalesce_token
        def _save() -> None:
            self._save_settings_now(token)

        self._schedule_owned_single_shot(self._SAVE_COALESCE_MS, _save)

    def _save_settings_now(self, token: int | None = None) -> None:
        """Perform the actual settings save (called by coalesce timer)."""
        if token is not None and token != getattr(self, "_save_coalesce_token", 0):
            return
        self._save_coalesce_pending = False
        if getattr(self, "_loading", False):
            return

        try:
            logger.debug("[WIDGETS_TAB] _save_settings_now start")
            logger.debug(
                "[WIDGETS_HYDRATION] phase=save_start built_sections=%s hydrated_sections=%s",
                sorted(
                    self._widget_section_descriptors[idx].section_id
                    for idx in getattr(self, "_subtab_content_built", set())
                    if 0 <= idx < len(self._widget_section_descriptors)
                ),
                sorted(getattr(self, "_hydrated_widget_sections", set())),
            )
        except Exception as e:
            logger.debug("[WIDGETS_TAB] Exception suppressed: %s", e)

        existing_widgets = self._settings.get('widgets', {})
        if not isinstance(existing_widgets, dict):
            existing_widgets = {}

        save_descriptors = self._get_hydrated_widget_save_descriptors()
        section_results = collect_widget_section_save_results(
            self,
            existing_widgets,
            save_descriptors,
        )
        visualizers_hydrated = any(
            descriptor.section_id == "visualizers"
            for descriptor in save_descriptors
        )

        apply_widget_section_save_results(
            existing_widgets,
            section_results,
            exclude_keys=("spotify_visualizer",),
            descriptors=save_descriptors,
        )

        clock_config = existing_widgets.get('clock', {})
        weather_config = existing_widgets.get('weather', {})
        media_config = existing_widgets.get('media', {})
        reddit_config = existing_widgets.get('reddit', {})

        spotify_vis_config, current_vis_mode, current_preset_index = (
            self._merge_visualizer_section_save(
                existing_widgets,
                section_results.get('spotify_visualizer', {}),
                hydrated=visualizers_hydrated,
            )
        )

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

        # Persist application-level family capability activation (SETUP page).
        # SETUP is always built, so this never depends on lazy hydration and can
        # never overwrite a hidden family's stored per-instance settings.
        self._apply_family_activation_to_config(existing_widgets)

        sync_custom_layout_restore_routes(existing_widgets)
        try:
            logger.debug(
                "[WIDGETS_HYDRATION] phase=save_commit hydrated_sections=%s media_enabled=%s "
                "visualizer_enabled=%s visualizer_mode=%s visualizer_preset=%s",
                sorted(getattr(self, "_hydrated_widget_sections", set())),
                existing_widgets.get("media", {}).get("enabled") if isinstance(existing_widgets.get("media"), dict) else None,
                spotify_vis_config.get("enabled"),
                current_vis_mode,
                current_preset_index,
            )
        except Exception:
            pass
        self._settings.set('widgets', existing_widgets)
        self._settings.save()
        self._refresh_custom_resize_lock_state()







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


    def _schedule_owned_single_shot(self, delay_ms: int, callback) -> None:
        callback._srpss_timer_owner = self
        callback._srpss_runtime_generation = getattr(
            self,
            "_runtime_generation",
            None,
        )
        ThreadManager.single_shot(delay_ms, callback)
