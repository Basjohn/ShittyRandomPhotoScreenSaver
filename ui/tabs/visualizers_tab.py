"""Top-level Visualizers Settings surface (V7).

The tab rehosts the existing Visualizer Settings builders without acquiring any
runtime or Media activation authority. SETUP owns family-level controls and mode
admission; FULLSCREEN MODE (first after Setup) owns the Expanded Visualizer's full-display
overlays (``ui/tabs/visualizers_fullscreen_page.py``). Stable Spectrum bar-appearance and Rainbow widgets are presented inside
the selected mode's Custom controls. Their tab-owned references are evacuated before
a retireable mode body is destroyed; mode-specific bodies stay lazy under
:class:`VisualizerModeBodyHost` and are constructed only when their visible mode pill
is selected.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.logging.logger import get_logger
from core.settings.defaults import get_default_settings
from core.settings.settings_manager import SettingsManager
from core.settings.visualizer_mode_registry import (
    apply_visualizer_mode_disable,
    build_visualizer_mode_activation,
    can_disable_visualizer_mode,
    iter_visualizer_mode_descriptors,
    iter_all_visualizer_mode_descriptors,
    is_mode_active,
    is_mode_available_on_backend,
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
from ui.tabs.media.visualizer_mode_binding import load_visualizer_family_values
from ui.tabs.visualizer_settings_context import (
    DEFAULT_VISUALIZER_MODE,
    VisualizerSettingsContextMixin,
)
from ui.tabs.visualizers_fullscreen_page import FULLSCREEN_BUCKET_SCOPE, FullscreenModePage
from ui.tabs.widgets_tab_media import (
    _install_visualizer_body_host,
    _update_spotify_vis_enabled_visibility,
    _update_visualizers_enabled_visibility,
    load_visualizer_settings,
    save_visualizer_settings,
)
from ui.tabs.shared_styles import style_group_box
from ui.widget_display_routes import DisplayRouteLeaveGuard

logger = get_logger(__name__)


class VisualizersTab(VisualizerSettingsContextMixin, QWidget):
    """Top-level Settings owner for Visualizer presentation and persistence."""

    _SAVE_COALESCE_MS = 200

    def __init__(
        self,
        settings: SettingsManager,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._widget_defaults = self._load_widget_defaults()

        visualizers_descriptor = get_widget_settings_section_descriptor("visualizers")
        if visualizers_descriptor is None:
            raise RuntimeError("Canonical visualizers Settings descriptor is missing")
        self._widget_section_descriptors = (visualizers_descriptor,)
        self._display_route_guard = DisplayRouteLeaveGuard(settings)

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
        # D10 point 2 on the diagnostic backend (the Vulkan rehearsal): a mode with no renderer there is greyed, with
        # its reason. On OpenGL every mode has one and this is empty. Read once: the backend never changes.
        self._modes_without_renderer = self._resolve_modes_without_renderer()

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

    @staticmethod
    def _resolve_modes_without_renderer() -> dict[str, str]:
        """{mode id: the one-line reason} for every active mode with no renderer on the process's backend."""
        from rendering.quick.bootstrap import QuickBackend, quick_backend_api

        backend = QuickBackend(api=quick_backend_api()).qt_graphics_api
        return {
            descriptor.mode_id: f"No {backend} renderer yet: the saver skips this mode on the {backend} backend."
            for descriptor in iter_all_visualizer_mode_descriptors()
            if is_mode_active(descriptor.mode_id) and not is_mode_available_on_backend(descriptor.mode_id)
        }

    def _load_widget_defaults(self) -> Dict[str, Dict[str, Any]]:
        """Load canonical Widget defaults for the active application profile."""
        defaults = get_default_settings(self._settings.get_application_name())
        widgets_defaults = defaults["widgets"]
        if not isinstance(widgets_defaults, dict):
            raise TypeError("Canonical defaults are missing the widgets mapping")
        return widgets_defaults

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
            self._default_bool("spotify_visualizer", "visualizers_enabled")
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

        # The Expanded Visualizer's full-display overlays: first after Setup, before the mode pills (operator, 8 Nov).
        self._fullscreen_pill = self._make_mode_pill("Fullscreen Mode")
        self._nav_group.addButton(self._fullscreen_pill)
        self._fullscreen_pill.clicked.connect(self._select_fullscreen_page)
        self._nav_flow.addWidget(self._fullscreen_pill)

        for descriptor in iter_all_visualizer_mode_descriptors():
            if not is_mode_active(descriptor.mode_id):
                continue
            pill = self._make_mode_pill(descriptor.display_name)
            if descriptor.mode_id in self._modes_without_renderer:
                pill.setToolTip(self._modes_without_renderer[descriptor.mode_id])
            self._mode_pills[descriptor.mode_id] = pill
            self._nav_group.addButton(pill)
            pill.clicked.connect(
                lambda _checked=False, mode=descriptor.mode_id: self._select_mode_page(mode)
            )
            self._nav_flow.addWidget(pill)
        detail_layout.addWidget(self._nav_flow)

        self._page_stack = QStackedWidget()
        self._setup_page = self._build_setup_page()
        self._fullscreen_page = FullscreenModePage(self, changed=self._save_settings)
        self._mode_page = self._build_mode_page()
        self._page_stack.addWidget(self._setup_page)
        self._page_stack.addWidget(self._fullscreen_page)
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
            self._default_bool("spotify_visualizer", "enabled")
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
        if self._modes_without_renderer:
            # Only on the diagnostic backend: one line for the greyed modes; each says why in its tooltip.
            from rendering.quick.bootstrap import QuickBackend, quick_backend_api

            backend = QuickBackend(api=quick_backend_api()).qt_graphics_api
            unported = QLabel(f"Greyed modes have no {backend} renderer yet: the saver skips them on the "
                              f"{backend} backend.")
            unported.setObjectName("visualizerModesWithoutRenderer")
            unported.setWordWrap(True)
            shared_styles.apply_shared_label_style(unported, "INFO_LABEL_STYLE")
            behavior_layout.addWidget(unported)

        for descriptor in iter_all_visualizer_mode_descriptors():
            if not is_mode_active(descriptor.mode_id):
                continue
            checkbox = QCheckBox(descriptor.display_name)
            checkbox.setProperty("circleIndicator", True)
            if descriptor.mode_id in self._modes_without_renderer:
                checkbox.setToolTip(self._modes_without_renderer[descriptor.mode_id])
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

        # Detailed mode controls preserve the old Beat-Visualizer enable gate.
        self._vis_controls_container = QWidget()
        controls_layout = QVBoxLayout(self._vis_controls_container)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)

        self._mode_body_host_widget = QWidget()
        self._mode_body_layout = QVBoxLayout(self._mode_body_host_widget)
        self._mode_body_layout.setContentsMargins(0, 0, 0, 0)
        self._mode_body_layout.setSpacing(4)
        controls_layout.addWidget(self._mode_body_host_widget)

        # The shared Bar Appearance and Rainbow families (stored per owning mode, declared in each mode's spec) are
        # edited in the Studios; the page holds their values in a value cache and builds no widget for them.
        load_visualizer_family_values(self, {})

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

    def _reset_view_scroll(self) -> None:
        scroll = self._scroll_area
        if scroll is None:
            return

        # 0 survives the later layout pass: no deferred second reset needed.
        scroll.verticalScrollBar().setValue(0)

    def get_view_state(self) -> Dict[str, Any]:
        """Persist the selected Visualizer builder, never a pixel scroll offset."""

        if self._page_stack.currentWidget() is self._mode_page:
            return {
                "page": "mode",
                "mode_id": str(self._active_visualizer_mode_id),
            }
        if self._page_stack.currentWidget() is self._fullscreen_page:
            return {"page": FULLSCREEN_BUCKET_SCOPE}
        return {"page": "setup"}

    def restore_view_state(self, state: Dict[str, Any]) -> None:
        if not isinstance(state, dict):
            self._select_setup_page()
            return
        page = str(state.get("page", "setup") or "setup").strip().lower()
        mode_id = str(state.get("mode_id", "") or "").strip().lower()
        if (page == "mode" and mode_id in self._vis_body_host.enabled_modes
                and mode_id not in self._modes_without_renderer):
            previous_loading = self._loading
            self._loading = True
            try:
                self._select_mode_page(mode_id)
            finally:
                self._loading = previous_loading
        elif page == FULLSCREEN_BUCKET_SCOPE:
            previous_loading = self._loading
            self._loading = True
            try:
                self._select_fullscreen_page()
            finally:
                self._loading = previous_loading
        else:
            self._select_setup_page()
        self._reset_view_scroll()

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
            self._select_setup_page()
            host = getattr(self, "_vis_body_host", None)
            if host is not None:
                host.retire_all()
        self.setEnabled(available)

    # ------------------------------------------------------------------
    # Mode admission / selection
    # ------------------------------------------------------------------

    def _leave_bucket_page(self, target: QWidget) -> None:
        """Leaving a page with buckets (a mode page or Fullscreen Mode) for another page closes its editing path."""
        current = self._page_stack.currentWidget()
        if (not getattr(self, "_loading", False) and current is not target
                and current in (self._mode_page, self._fullscreen_page)):
            self.retire_bucket_context()

    def _select_setup_page(self, _checked: bool = False) -> None:
        self._leave_bucket_page(self._setup_page)
        self._setup_pill.setChecked(True)
        self._page_stack.setCurrentWidget(self._setup_page)
        self._reset_view_scroll()

    def _select_fullscreen_page(self, _checked: bool = False) -> None:
        self._leave_bucket_page(self._fullscreen_page)
        self._fullscreen_pill.setChecked(True)
        self._page_stack.setCurrentWidget(self._fullscreen_page)
        self._reset_view_scroll()

    def _select_mode_page(self, mode_id: str) -> None:
        target = str(mode_id or "").strip().lower()
        host = self._vis_body_host
        if target not in host.enabled_modes:
            raise ValueError(f"Disabled visualizer mode has no selectable pill: {target!r}")
        if target in self._modes_without_renderer:
            raise ValueError(f"Visualizer mode {target!r} is greyed: {self._modes_without_renderer[target]}")

        previous = self._get_active_visualizer_mode()
        if self._page_stack.currentWidget() is self._fullscreen_page:
            self._leave_bucket_page(self._mode_page)
        # A lazy builder can raise before the body host commits its new mode.
        # Retain the last *visible* selection to restore coherent Settings
        # presentation on failure.
        previous_page_is_mode = self._page_stack.currentWidget() is self._mode_page
        previous_host_mode = host.selected_mode
        previous_config = self._vis_loaded_config
        if previous != target:
            self._flush_pending_visualizer_save()
            if not getattr(self, "_loading", False):
                self.retire_bucket_context()

        self._active_visualizer_mode_id = target
        resolved = self._prepare_mode_hydration_config(target)
        self._vis_loaded_config = resolved

        previous_loading = self._loading
        self._loading = True
        try:
            # Pills are the actual selection authority. The host records selection;
            # the shared context then handles visibility/scroll on the same cached
            # body without a second selector. The shared families follow the same
            # resolved preset.
            host.select(target)
            load_visualizer_family_values(self, resolved)
            self._update_vis_mode_sections()
        except Exception:
            # If construction failed mid-scaffold, remove its uncommitted
            # QWidget now rather than leaving it to overlap the old page.
            # The error still propagates; this only restores the last valid UI.
            if not host.is_constructed(target):
                for index in reversed(range(self._mode_body_layout.count())):
                    item = self._mode_body_layout.itemAt(index)
                    candidate = item.widget() if item is not None else None
                    if (candidate is not None and candidate.objectName()
                            == f"visualizer_mode_body_{target}"):
                        self._retire_visualizer_mode_body(target, candidate)
            self._active_visualizer_mode_id = previous
            self._vis_loaded_config = previous_config
            if (previous_page_is_mode and previous_host_mode
                    and host.is_constructed(previous_host_mode)):
                self._active_visualizer_mode_id = previous_host_mode
                restored = self._prepare_mode_hydration_config(previous_host_mode)
                self._vis_loaded_config = restored
                load_visualizer_family_values(self, restored)
                self._update_vis_mode_sections()
                self._mode_pills[previous_host_mode].setChecked(True)
            else:
                self._select_setup_page()
            raise
        finally:
            self._loading = previous_loading

        self._page_stack.setCurrentWidget(self._mode_page)
        self._mode_pills[target].setChecked(True)
        self._reset_view_scroll()
        # A mode change is a discrete authority change, not slider chatter: persist
        # it immediately so any subsequent preset interaction reads the same mode.
        self._save_settings_now()

    def _prepare_mode_hydration_config(self, mode_id: str) -> dict[str, Any]:
        widgets = self._settings.get("widgets")
        if not isinstance(widgets, dict):
            widgets = {}
        stored = widgets.get("spotify_visualizer", {})
        section = deepcopy(stored) if isinstance(stored, dict) else {}
        section["mode"] = mode_id
        section["mode_activation"] = build_visualizer_mode_activation(
            self._vis_body_host.enabled_modes
        )
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
            new_enabled = resolve_effective_enabled_modes(
                build_visualizer_mode_activation(requested)
            )
        else:
            if not can_disable_visualizer_mode(current_enabled, target):
                self._sync_mode_admission_controls()
                return
            new_enabled = apply_visualizer_mode_disable(current_enabled, target)

        self._flush_pending_visualizer_save()
        host.set_mode_activation(build_visualizer_mode_activation(new_enabled))

        active = self._get_active_visualizer_mode()
        effective, substituted = resolve_effective_mode(
            active, build_visualizer_mode_activation(host.enabled_modes)
        )
        if substituted:
            self._active_visualizer_mode_id = effective
            resolved = self._prepare_mode_hydration_config(effective)
            self._vis_loaded_config = resolved
            previous_loading = self._loading
            self._loading = True
            try:
                load_visualizer_family_values(self, resolved)
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
            checkbox.setEnabled((mode_id not in enabled or len(enabled) > 1)
                                and mode_id not in self._modes_without_renderer)
            checkbox.blockSignals(False)

    def _sync_mode_pills(self) -> None:
        enabled = set(self._vis_body_host.enabled_modes)
        for mode_id, pill in self._mode_pills.items():
            selectable = mode_id in enabled and mode_id not in self._modes_without_renderer
            pill.setVisible(mode_id in enabled)
            pill.setEnabled(selectable)
            if not selectable:
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

        Persisted state is untouched.
        """
        body.hide()
        self._mode_body_layout.removeWidget(body)

        protected = {
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

    def _schedule_owned_single_shot(self, delay_ms: int, callback):
        callback._srpss_timer_owner = self
        callback._srpss_runtime_generation = self._runtime_generation
        return ThreadManager.single_shot(delay_ms, callback)

    def _save_settings(self) -> None:
        if self._loading or self._writing_settings:
            return
        self._save_coalesce_pending = True
        self._save_coalesce_token += 1
        token = self._save_coalesce_token

        def _save() -> None:
            self._save_settings_now(token)

        # One live coalescing timer: replace (cancel) the previous one.
        previous = getattr(self, "_save_coalesce_handle", None)
        if previous is not None:
            previous.cancel()
        self._save_coalesce_handle = self._schedule_owned_single_shot(self._SAVE_COALESCE_MS, _save)

    def _flush_pending_visualizer_save(self) -> None:
        handle = getattr(self, "_save_coalesce_handle", None)
        if handle is not None:
            handle.cancel()
            self._save_coalesce_handle = None
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
            widgets = self._settings.get("widgets")
            if not isinstance(widgets, dict):
                widgets = {}
            else:
                widgets = deepcopy(widgets)

            result = save_visualizer_settings(self)
            # The Fullscreen Mode page's one value (a global Visualizer setting, never a preset value).
            result["fullscreen_overlays"] = self._fullscreen_page.values()
            spotify_vis, mode_id, preset_index = self._merge_visualizer_section_save(
                widgets,
                result,
                hydrated=True,
            )
            widgets["spotify_visualizer"] = spotify_vis
            self._settings.set_widgets_map(widgets)
            logger.debug(
                "[VISUALIZERS_TAB] saved mode=%s preset=%d mode_activation=%s",
                mode_id,
                preset_index,
                spotify_vis.get("mode_activation"),
            )
        finally:
            self._writing_settings = False

    def resolve_leave_display_routes(self, on_switched=None) -> bool:
        """Leaving Visualizers: settle a Visualizer only a disabled display would show
        (``ui/widget_display_routes``). False means stay."""

        return self._display_route_guard.resolve(
            self, self._widget_section_descriptors[0].persisted_widget_keys,
            flush=self.flush_pending_changes,
            on_switched=on_switched if on_switched is not None else self.load_from_settings)

    def flush_pending_changes(self) -> None:
        """Commit this tab's coalesced UI edits before a Settings durability boundary."""
        self._flush_pending_visualizer_save()

    def _load_settings(self, *, construct_active_body: bool = False) -> None:
        widgets = self._settings.get("widgets")
        if not isinstance(widgets, dict):
            widgets = {}
        section = widgets.get("spotify_visualizer", {})
        requested_activation = section.get("mode_activation") if isinstance(section, dict) else None
        self._fullscreen_page.load(section.get("fullscreen_overlays") if isinstance(section, dict) else None)
        # Retire newly-disabled bodies before a full loader can rehydrate them.
        self._vis_body_host.set_mode_activation(requested_activation)
        load_visualizer_settings(
            self,
            widgets,
            construct_active_body=construct_active_body,
        )
        # Loader resolves effective mode; host owns the effective enabled set.
        effective, _substituted = resolve_effective_mode(
            self._get_active_visualizer_mode(),
            build_visualizer_mode_activation(self._vis_body_host.enabled_modes),
        )
        self._active_visualizer_mode_id = effective
        self._sync_mode_admission_controls()
        self._sync_mode_pills()

    def load_from_settings(self) -> None:
        """Explicit full reload after preset/import changes without eager bodies."""
        self._flush_pending_visualizer_save()
        self._loading = True
        try:
            # UI state is independently replaceable by reset/SST import. Do
            # not leave constructed disclosures checked against changed maps.
            self._initialize_visualizer_settings_context_state()
            shared_styles.collapse_settings_bucket_tree(self)
            self._load_settings(construct_active_body=False)
            self._select_setup_page()
        finally:
            self._loading = False
        logger.debug("[VISUALIZERS_TAB] Reloaded from settings")
