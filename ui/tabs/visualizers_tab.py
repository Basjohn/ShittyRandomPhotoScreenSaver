"""Top-level Visualizers Settings surface (V7).

The tab rehosts the existing Visualizer Settings builders without acquiring any
runtime or Media activation authority. SETUP owns family-level controls and mode
admission. Stable Spectrum bar-appearance controls and shared rainbow controls live
on the mode page outside retireable bodies; mode-specific bodies stay lazy under
:class:`VisualizerModeBodyHost` and are constructed only when their visible mode
pill is selected.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QGraphicsDropShadowEffect,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.logging.logger import get_logger
from core.settings.defaults import get_default_settings
from core.settings.settings_manager import SettingsManager
from core.settings.visualizer_mode_registry import (
    apply_visualizer_mode_disable,
    can_disable_visualizer_mode,
    iter_visualizer_mode_descriptors,
    resolve_effective_enabled_modes,
    resolve_effective_mode,
)
from core.settings.visualizer_presets import (
    apply_preset_to_config,
    resolve_preset_index_from_mapping,
)
from core.threading.manager import ThreadManager
from rendering.widget_descriptors import (
    get_widget_settings_section_descriptor,
)
from ui.flow_layout import FlowContainer
from ui.tabs import shared_styles
from ui.tabs.media.shared_appearance_controls import (
    build_shared_visualizer_appearance_controls,
)
from ui.tabs.visualizer_settings_context import (
    DEFAULT_VISUALIZER_MODE,
    VisualizerSettingsContextMixin,
)
from ui.tabs.widgets_tab_media import (
    _install_visualizer_body_host,
    _update_spotify_vis_enabled_visibility,
    _update_visualizers_enabled_visibility,
    load_shared_visualizer_appearance_settings,
    load_visualizer_settings,
    save_visualizer_settings,
)
from ui.tabs.shared_styles import NoWheelSlider, add_section_label, style_group_box

logger = get_logger(__name__)


class VisualizersTab(VisualizerSettingsContextMixin, QWidget):
    """Top-level Settings owner for Visualizer presentation and persistence."""

    _SAVE_COALESCE_MS = 200

    def __init__(
        self,
        settings: SettingsManager,
        parent: Optional[QWidget] = None,
        *,
        widget_defaults: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._provided_widget_defaults = widget_defaults
        self._widget_defaults = self._load_widget_defaults()

        visualizers_descriptor = get_widget_settings_section_descriptor("visualizers")
        if visualizers_descriptor is None:
            raise RuntimeError("Canonical visualizers Settings descriptor is missing")
        self._widget_section_descriptors = (visualizers_descriptor,)

        self._loading = True
        self._writing_settings = False
        self._save_coalesce_pending = False
        self._save_coalesce_token = 0
        self._runtime_generation = 0
        self._scroll_area: Optional[QScrollArea] = None
        self._active_visualizer_mode_id = DEFAULT_VISUALIZER_MODE
        self._last_vis_mode_section = None
        self._mode_pills: dict[str, QPushButton] = {}
        self._mode_admission_checkboxes: dict[str, QCheckBox] = {}

        self._initialize_visualizer_settings_context_state()
        self._setup_ui()
        self._load_settings(construct_active_body=False)
        self._sync_mode_admission_controls()
        self._sync_mode_pills()
        self._select_setup_page()
        self._loading = False

        logger.debug("VisualizersTab created")

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _load_widget_defaults(self) -> Dict[str, Dict[str, Any]]:
        """Resolve canonical widget defaults; construction failures stay fail-loud."""
        defaults = get_default_settings()
        widgets_defaults = defaults.get("widgets", {})
        loaded = widgets_defaults if isinstance(widgets_defaults, dict) else {}
        if not isinstance(self._provided_widget_defaults, dict):
            return loaded
        merged = dict(loaded)
        for section, section_defaults in self._provided_widget_defaults.items():
            if isinstance(section_defaults, dict) and isinstance(merged.get(section), dict):
                current = dict(merged[section])
                current.update(section_defaults)
                merged[section] = current
            else:
                merged[section] = section_defaults
        return merged

    def _setup_ui(self) -> None:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet(shared_styles.SCROLL_AREA_STYLE)
        self._scroll_area = scroll

        content = QWidget()
        root = QVBoxLayout(content)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)

        title = QLabel("Visualizers")
        shared_styles.apply_shared_label_style(title, "PAGE_TITLE_STYLE")
        root.addWidget(title)

        intro = QLabel(
            "Configure Visualizer availability and appearance, then open an enabled mode "
            "to edit its presets and mode-specific controls."
        )
        intro.setWordWrap(True)
        shared_styles.apply_shared_label_style(intro, "INFO_LABEL_STYLE")
        root.addWidget(intro)

        self.visualizers_enabled = QCheckBox("Enable Visualizers")
        self.visualizers_enabled.setProperty("circleIndicator", True)
        self.visualizers_enabled.setChecked(
            self._default_bool("spotify_visualizer", "visualizers_enabled", True)
        )
        self.visualizers_enabled.setToolTip("Master switch for all visualizer controls.")
        self.visualizers_enabled.stateChanged.connect(self._save_settings)
        self.visualizers_enabled.stateChanged.connect(
            lambda _state: _update_visualizers_enabled_visibility(self)
        )
        root.addWidget(self.visualizers_enabled)

        self._visualizers_controls_container = QWidget()
        detail_layout = QVBoxLayout(self._visualizers_controls_container)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(14)
        root.addWidget(self._visualizers_controls_container)

        self._nav_flow = FlowContainer(h_spacing=8, v_spacing=8)
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)

        self._setup_pill = self._make_mode_pill("Setup")
        self._nav_group.addButton(self._setup_pill)
        self._setup_pill.clicked.connect(self._select_setup_page)
        self._nav_flow.addWidget(self._setup_pill)

        for descriptor in iter_visualizer_mode_descriptors():
            pill = self._make_mode_pill(descriptor.display_name)
            self._mode_pills[descriptor.mode_id] = pill
            self._nav_group.addButton(pill)
            pill.clicked.connect(
                lambda _checked=False, mode=descriptor.mode_id: self._select_mode_page(mode)
            )
            self._nav_flow.addWidget(pill)
        detail_layout.addWidget(self._nav_flow)

        self._page_stack = QStackedWidget()
        self._setup_page = self._build_setup_page()
        self._mode_page = self._build_mode_page()
        self._page_stack.addWidget(self._setup_page)
        self._page_stack.addWidget(self._mode_page)
        detail_layout.addWidget(self._page_stack, 1)

        _update_visualizers_enabled_visibility(self)
        scroll.setWidget(content)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        # V7 acceptance: the old Widgets-hosted builders inherited this complete
        # control skin from WidgetsTab. Rebind the same canonical Settings-theme
        # vocabulary at the new top-level owner so sliders/spinboxes/combos do not
        # fall through to platform/Qt presentation.
        shared_styles.bind_shared_styles(
            self,
            "SPINBOX_STYLE",
            "TOOLTIP_STYLE",
            "CIRCLE_CHECKBOX_STYLE",
            "COMBOBOX_STYLE",
            "SLIDER_STYLE",
        )

    def _make_mode_pill(self, text: str) -> QPushButton:
        button = QPushButton(text)
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        shared_styles.bind_shared_styles(
            button,
            "MODE_TOGGLE_BUTTON_STYLE",
            base_style="",
        )
        return button

    def _build_setup_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        behavior_group = QGroupBox("Setup")
        style_group_box(behavior_group)
        behavior_layout = QVBoxLayout(behavior_group)
        behavior_layout.setContentsMargins(18, 18, 18, 18)
        behavior_layout.setSpacing(10)

        self.vis_enabled_checkbox = QCheckBox("Enable Beat Visualizer")
        self.vis_enabled_checkbox.setProperty("circleIndicator", True)
        self.vis_enabled_checkbox.setChecked(
            self._default_bool("spotify_visualizer", "enabled", True)
        )
        self.vis_enabled_checkbox.setToolTip(
            "Enable the Media-linked visualizer presentation while preserving its settings."
        )
        self.vis_enabled_checkbox.stateChanged.connect(self._save_settings)
        self.vis_enabled_checkbox.stateChanged.connect(
            lambda _state: _update_spotify_vis_enabled_visibility(self)
        )
        behavior_layout.addWidget(self.vis_enabled_checkbox)

        mode_intro = QLabel(
            "Enabled modes receive navigation pills. At least one mode remains enabled "
            "while the Visualizer family is available."
        )
        mode_intro.setWordWrap(True)
        shared_styles.apply_shared_label_style(mode_intro, "INFO_LABEL_STYLE")
        behavior_layout.addWidget(mode_intro)

        for descriptor in iter_visualizer_mode_descriptors():
            checkbox = QCheckBox(descriptor.display_name)
            checkbox.setProperty("circleIndicator", True)
            checkbox.toggled.connect(
                lambda checked, mode=descriptor.mode_id: self._on_mode_admission_toggled(
                    mode, checked
                )
            )
            self._mode_admission_checkboxes[descriptor.mode_id] = checkbox
            behavior_layout.addWidget(checkbox)

        layout.addWidget(behavior_group)
        layout.addStretch()
        return page

    def _build_mode_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # These controls historically appeared only with Spectrum. Keep their
        # widgets permanently owned by the stable mode page so Spectrum retirement
        # cannot destroy them, but do not expose the old shared-ownership mechanism
        # as user-facing SETUP/UI.
        self._base_appearance_group = QGroupBox("Bar Appearance")
        style_group_box(self._base_appearance_group)
        base_appearance_layout = QVBoxLayout(self._base_appearance_group)
        base_appearance_layout.setContentsMargins(18, 18, 18, 18)
        base_appearance_layout.setSpacing(4)
        build_shared_visualizer_appearance_controls(self, base_appearance_layout)
        layout.addWidget(self._base_appearance_group)

        # Detailed mode controls preserve the old Beat-Visualizer enable gate.
        self._vis_controls_container = QWidget()
        controls_layout = QVBoxLayout(self._vis_controls_container)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)

        self._build_rainbow_controls(controls_layout)

        self._mode_body_host_widget = QWidget()
        self._mode_body_layout = QVBoxLayout(self._mode_body_host_widget)
        self._mode_body_layout.setContentsMargins(0, 0, 0, 0)
        self._mode_body_layout.setSpacing(4)
        controls_layout.addWidget(self._mode_body_host_widget)
        layout.addWidget(self._vis_controls_container)
        layout.addStretch()

        self._vis_loaded_config = None
        _install_visualizer_body_host(
            self,
            self._mode_body_layout,
            retire_body=self._retire_visualizer_mode_body,
        )
        _update_spotify_vis_enabled_visibility(self)
        return page

    def _build_rainbow_controls(self, parent_layout: QVBoxLayout) -> None:
        self._rainbow_controls_container = QWidget()
        bucket_layout = QVBoxLayout(self._rainbow_controls_container)
        bucket_layout.setContentsMargins(0, 0, 0, 0)
        bucket_layout.setSpacing(4)
        self._rainbow_per_mode: dict[str, tuple[bool, int]] = {}

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        self.rainbow_enabled = QCheckBox("Taste The Rainbow")
        self.rainbow_enabled.setProperty("circleIndicator", True)
        self.rainbow_enabled.setAccessibleName("Taste The Rainbow")
        self.rainbow_enabled.setToolTip(
            "Slowly shift the hue of visualiser colours through the spectrum. "
            "Saved independently per visualizer mode."
        )
        self.rainbow_enabled.setChecked(False)
        self.rainbow_enabled.setCursor(Qt.CursorShape.PointingHandCursor)
        self.rainbow_enabled.stateChanged.connect(self._save_settings)
        self.rainbow_enabled.stateChanged.connect(
            lambda _state: self._update_rainbow_visibility()
        )
        self.rainbow_enabled.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        row.addWidget(self.rainbow_enabled)

        glow_effect = QGraphicsDropShadowEffect(self.rainbow_enabled)
        glow_effect.setColor(QColor(255, 255, 255, 160))
        glow_effect.setBlurRadius(26.0)
        glow_effect.setOffset(0, 0)
        glow_effect.setEnabled(False)
        self.rainbow_enabled.setGraphicsEffect(glow_effect)

        self._rainbow_plain_label = self.rainbow_enabled
        self._rainbow_glow_effect = glow_effect
        self._rainbow_label_stack = None
        self._rainbow_glow_label = None

        row.addStretch()
        bucket_layout.addLayout(row)

        self._rainbow_speed_container = QWidget()
        speed_row = QHBoxLayout(self._rainbow_speed_container)
        speed_row.setContentsMargins(0, 0, 0, 0)
        speed_row.setSpacing(6)
        add_section_label(speed_row, "Speed:", 150)
        self.rainbow_speed_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.rainbow_speed_slider.setRange(1, 100)
        self.rainbow_speed_slider.setValue(50)
        self.rainbow_speed_slider.setTickPosition(NoWheelSlider.TickPosition.TicksBelow)
        self.rainbow_speed_slider.setTickInterval(10)
        self.rainbow_speed_slider.setToolTip("How fast the hue cycles through the spectrum.")
        self.rainbow_speed_slider.valueChanged.connect(self._save_settings)
        self.rainbow_speed_label = QLabel("0.50")
        self.rainbow_speed_slider.valueChanged.connect(
            lambda value: self.rainbow_speed_label.setText(f"{value / 100.0:.2f}")
        )
        speed_row.addWidget(self.rainbow_speed_slider, 1)
        speed_row.addWidget(self.rainbow_speed_label)
        bucket_layout.addWidget(self._rainbow_speed_container)
        self._rainbow_speed_container.setVisible(False)

        parent_layout.addWidget(self._rainbow_controls_container)

    def set_family_capability_available(self, available: bool) -> None:
        """Mirror external Widget-family capability without owning that state.

        Capability admission remains owned by Widgets SETUP. When it closes,
        retire any constructed mode bodies immediately so a disabled family has
        no hidden Settings owner. Persisted state and the stable mode-page
        controls remain intact for a later re-enable.
        """
        available = bool(available)
        if not available:
            self._flush_pending_visualizer_save()
            host = getattr(self, "_vis_body_host", None)
            if host is not None:
                host.retire_all()
            self._select_setup_page()
        self.setEnabled(available)

    # ------------------------------------------------------------------
    # Mode admission / selection
    # ------------------------------------------------------------------

    def _select_setup_page(self, _checked: bool = False) -> None:
        self._setup_pill.setChecked(True)
        self._page_stack.setCurrentWidget(self._setup_page)

    def _select_mode_page(self, mode_id: str) -> None:
        target = str(mode_id or "").strip().lower()
        host = self._vis_body_host
        if target not in host.enabled_modes:
            raise ValueError(f"Disabled visualizer mode has no selectable pill: {target!r}")

        previous = self._get_active_visualizer_mode()
        if previous != target:
            self._flush_pending_visualizer_save()

        self._active_visualizer_mode_id = target
        resolved = self._prepare_mode_hydration_config(target)
        self._vis_loaded_config = resolved

        previous_loading = self._loading
        self._loading = True
        try:
            load_shared_visualizer_appearance_settings(self, resolved, target)

            # Pills are the actual selection authority. The host records selection;
            # the shared context then handles visibility/scroll/rainbow on the same
            # cached body without a second selector. Programmatic hydration is kept
            # inside the load guard so it cannot schedule duplicate writes.
            host.select(target)
            self._update_vis_mode_sections()
        finally:
            self._loading = previous_loading

        # V6a's fill/border rows were user-visible only in Spectrum. Preserve that
        # presentation contract while keeping their lifetime outside its retireable
        # body. Other modes use their own authored appearance controls.
        self._base_appearance_group.setVisible(target == "spectrum")

        self._page_stack.setCurrentWidget(self._mode_page)
        self._mode_pills[target].setChecked(True)
        # A mode change is a discrete authority change, not slider chatter: persist
        # it immediately so any subsequent preset interaction reads the same mode.
        self._save_settings_now()

    def _prepare_mode_hydration_config(self, mode_id: str) -> dict[str, Any]:
        widgets = self._settings.get("widgets", {})
        if not isinstance(widgets, dict):
            widgets = {}
        stored = widgets.get("spotify_visualizer", {})
        section = deepcopy(stored) if isinstance(stored, dict) else {}
        section["mode"] = mode_id
        section["enabled_modes"] = list(self._vis_body_host.enabled_modes)
        preset_index = resolve_preset_index_from_mapping(mode_id, section)
        return apply_preset_to_config(mode_id, preset_index, section)

    def _on_mode_admission_toggled(self, mode_id: str, checked: bool) -> None:
        if self._loading:
            return
        host = self._vis_body_host
        current_enabled = host.enabled_modes
        target = str(mode_id or "").strip().lower()

        if checked:
            requested = tuple(current_enabled) + (target,)
            new_enabled = resolve_effective_enabled_modes(requested)
        else:
            if not can_disable_visualizer_mode(current_enabled, target):
                self._sync_mode_admission_controls()
                return
            new_enabled = apply_visualizer_mode_disable(current_enabled, target)

        self._flush_pending_visualizer_save()
        host.set_enabled_modes(new_enabled)

        active = self._get_active_visualizer_mode()
        effective, substituted = resolve_effective_mode(active, host.enabled_modes)
        if substituted:
            self._active_visualizer_mode_id = effective
            resolved = self._prepare_mode_hydration_config(effective)
            self._vis_loaded_config = resolved
            previous_loading = self._loading
            self._loading = True
            try:
                load_shared_visualizer_appearance_settings(self, resolved, effective)
            finally:
                self._loading = previous_loading

        self._sync_mode_admission_controls()
        self._sync_mode_pills()
        self._save_settings_now()

    def _sync_mode_admission_controls(self) -> None:
        enabled = set(self._vis_body_host.enabled_modes)
        for mode_id, checkbox in self._mode_admission_checkboxes.items():
            checkbox.blockSignals(True)
            checkbox.setChecked(mode_id in enabled)
            checkbox.setEnabled(mode_id not in enabled or len(enabled) > 1)
            checkbox.blockSignals(False)

    def _sync_mode_pills(self) -> None:
        enabled = set(self._vis_body_host.enabled_modes)
        for mode_id, pill in self._mode_pills.items():
            pill.setVisible(mode_id in enabled)
            pill.setEnabled(mode_id in enabled)
            if mode_id not in enabled:
                pill.setChecked(False)

    # ------------------------------------------------------------------
    # Real Qt body retirement
    # ------------------------------------------------------------------

    @staticmethod
    def _value_contains_body_widget(value: Any, body: QWidget) -> bool:
        if isinstance(value, QWidget):
            return value is body or body.isAncestorOf(value)
        if isinstance(value, dict):
            return any(
                VisualizersTab._value_contains_body_widget(item, body)
                for item in value.values()
            )
        if isinstance(value, (list, tuple, set, frozenset)):
            return any(
                VisualizersTab._value_contains_body_widget(item, body)
                for item in value
            )
        return False

    def _retire_visualizer_mode_body(self, mode_id: str, body: QWidget) -> None:
        """Destroy one disabled mode body and clear stale QWidget wrappers.

        Persisted state is untouched. Shared appearance controls cannot be
        descendants here because V7 owns them permanently under SETUP.
        """
        body.hide()
        self._mode_body_layout.removeWidget(body)

        # Technical controls use one shared mode-indexed store, so retire only
        # this mode's entry rather than deleting the store for other live bodies.
        tech_store = getattr(self, "_per_mode_technical_controls", None)
        if isinstance(tech_store, dict):
            modes = tech_store.get("modes")
            if isinstance(modes, dict):
                modes.pop(mode_id, None)

        protected = {
            "_per_mode_technical_controls",
            "_vis_body_host",
            "_mode_body_layout",
            "_mode_body_host_widget",
            "_mode_pills",
            "_mode_admission_checkboxes",
        }
        for attr_name, value in list(vars(self).items()):
            if attr_name in protected:
                continue
            if self._value_contains_body_widget(value, body):
                try:
                    delattr(self, attr_name)
                except AttributeError:
                    pass

        if getattr(self, "_last_vis_mode_section", None) == mode_id:
            self._last_vis_mode_section = None
        # Keep the existing Qt parent until deferred destruction. Removing the
        # layout entry + hiding is sufficient; detaching would create a transient
        # orphan/top-level lifetime that V7 does not need.
        body.deleteLater()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _schedule_owned_single_shot(self, delay_ms: int, callback) -> None:
        callback._srpss_timer_owner = self
        callback._srpss_runtime_generation = self._runtime_generation
        ThreadManager.single_shot(delay_ms, callback)

    def _save_settings(self) -> None:
        if self._loading or self._writing_settings:
            return
        self._auto_switch_preset_to_custom()
        self._save_coalesce_pending = True
        self._save_coalesce_token += 1
        token = self._save_coalesce_token

        def _save() -> None:
            self._save_settings_now(token)

        self._schedule_owned_single_shot(self._SAVE_COALESCE_MS, _save)

    def _flush_pending_visualizer_save(self) -> None:
        if not self._save_coalesce_pending or self._loading:
            return
        self._save_coalesce_token += 1
        self._save_settings_now()

    def _save_settings_now(self, token: int | None = None) -> None:
        if token is not None and token != self._save_coalesce_token:
            return
        self._save_coalesce_pending = False
        if self._loading or self._writing_settings:
            return

        self._writing_settings = True
        try:
            widgets = self._settings.get("widgets", {})
            if not isinstance(widgets, dict):
                widgets = {}
            else:
                widgets = deepcopy(widgets)

            result = save_visualizer_settings(self)
            spotify_vis, mode_id, preset_index = self._merge_visualizer_section_save(
                widgets,
                result,
                hydrated=True,
            )
            widgets["spotify_visualizer"] = spotify_vis
            self._settings.set_widgets_map(widgets)
            logger.debug(
                "[VISUALIZERS_TAB] saved mode=%s preset=%d enabled_modes=%s",
                mode_id,
                preset_index,
                spotify_vis.get("enabled_modes"),
            )
        finally:
            self._writing_settings = False

    def _load_settings(self, *, construct_active_body: bool = False) -> None:
        widgets = self._settings.get("widgets", {})
        if not isinstance(widgets, dict):
            widgets = {}
        section = widgets.get("spotify_visualizer", {})
        requested_enabled = section.get("enabled_modes") if isinstance(section, dict) else None
        # Retire newly-disabled bodies before a full loader can rehydrate them.
        self._vis_body_host.set_enabled_modes(requested_enabled)
        load_visualizer_settings(
            self,
            widgets,
            construct_active_body=construct_active_body,
        )
        # Loader resolves effective mode; host owns the effective enabled set.
        effective, _substituted = resolve_effective_mode(
            self._get_active_visualizer_mode(),
            self._vis_body_host.enabled_modes,
        )
        self._active_visualizer_mode_id = effective
        self._sync_mode_admission_controls()
        self._sync_mode_pills()

    def load_from_settings(self) -> None:
        """Explicit full reload after preset/import changes without eager bodies."""
        self._flush_pending_visualizer_save()
        self._loading = True
        try:
            self._load_settings(construct_active_body=False)
        finally:
            self._loading = False
        self._select_setup_page()
        logger.debug("[VISUALIZERS_TAB] Reloaded from settings")
