"""
Transitions configuration tab for settings dialog.

Allows users to configure transition settings:
- Transition type selection
- Duration
- Direction (for directional transitions)
- Easing curves
"""
from collections.abc import Mapping
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QGroupBox, QScrollArea, QPushButton, QButtonGroup,
    QSpinBox, QDoubleSpinBox,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor

from core.settings.default_contract import require_canonical_default
from core.settings.settings_manager import SettingsManager
from core.settings.capability_activation import (
    is_transition_activated,
    normalize_transition_capability_state,
)
from core.logging.logger import get_logger
from rendering.transition_settings import (
    Choice,
    Colour,
    Number,
    Toggle,
    TransitionSettings,
    iter_transition_settings,
    transition_settings,
    widget_attr,
)
from rendering.transition_registry import (
    canonicalize_transition_name,
    is_transition_available,
    transition_unavailability_reason,
    get_transition_setting_names,
)
from ui.tabs import shared_styles
from ui.tabs.shared_styles import (
    add_swatch_label,
    style_group_box,
    add_aligned_row_widget as shared_add_aligned_row_widget,
    add_aligned_row as shared_add_aligned_row,
    NoWheelSlider,
)
from ui.styled_popup import ColorSwatchButton, StyledColorPicker
from ui.widgets import StyledComboBox
from ui.flow_layout import FlowContainer

_MODULE_ROW_MIN_WIDTH = 220

logger = get_logger(__name__)

_TRANSITION_SETTING_NAMES = get_transition_setting_names()

_SETUP_NAV_KEY = "__setup__"
def _transition_default(path: str):
    """Return one persisted Transition product default from canonical authority."""

    return require_canonical_default(f"transitions.{path}")


def _transition_defaults_root() -> dict:
    """Return the complete canonical Transitions mapping or fail loudly."""

    value = require_canonical_default("transitions")
    if not isinstance(value, dict):
        raise TypeError("Canonical transitions defaults must be a mapping")
    return value


class TransitionsTab(QWidget):
    """Transitions configuration tab."""
    
    # Signals
    transitions_changed = Signal()
    
    def __init__(self, settings: SettingsManager, parent: Optional[QWidget] = None):
        """
        Initialize transitions tab.
        
        Args:
            settings: Settings manager
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._settings = settings
        # Each transition's Direction selection, by section, from the one canonical defaults
        # authority until persisted state is hydrated. The shared Direction box edits the current
        # transition's entry, so a transition whose page is not built still keeps its direction.
        self._direction_by_type = {
            spec.section: str(_transition_default(f"{spec.section}.direction"))
            for spec in iter_transition_settings()
            if spec.directions is not None
        }
        # Per-transition pool membership for random/switch behaviour.
        self._pool_by_type = {}
        self._duration_by_type = {}
        # Per-transition application-level capability activation (E2 SETUP).
        self._activation_by_type = {}
        # Authoritative currently-edited / manual transition selection (E2). The
        # hidden combo only mirrors this; it is never a second authority.
        self._current_transition = ""
        self._loading = False
        # Reentrancy guard so our own writes do not bounce back through the
        # cross-manager settings_changed broadcast as an "external" change.
        self._writing_settings = False
        self._setup_ui()
        self._load_settings()

        # Live link: reflect external `transitions` mutations (e.g. the
        # screensaver context-menu Random action) without becoming a second
        # authority. Auto-disconnected when this QObject is destroyed.
        try:
            self._settings.settings_changed.connect(self._on_external_settings_changed)
        except Exception as e:
            logger.debug("[TRANSITIONS_TAB] settings_changed subscribe skipped: %s", e)

        logger.debug("TransitionsTab created")

    def _on_external_settings_changed(self, key: str, value: object) -> None:
        """Reflect an external transitions-root mutation into the live controls.

        This makes `Use Random Transitions` and the context-menu `Random` action
        two views of the one canonical `transitions.random_always` state. It never
        builds unbuilt transition pages, never saves in response, and is guarded
        against our own writes / load to avoid signal loops.
        """
        if getattr(self, "_writing_settings", False) or getattr(self, "_loading", False):
            return
        if not (key in ("*", "transitions") or (isinstance(key, str) and key.startswith("transitions."))):
            return
        cfg = self._settings.get("transitions")
        if not isinstance(cfg, dict):
            return
        self._loading = True
        try:
            for name, cb in getattr(self, "_activation_checkboxes", {}).items():
                desired = is_transition_activated(cfg, name)
                if cb.isChecked() != desired:
                    cb.blockSignals(True)
                    cb.setChecked(desired)
                    cb.blockSignals(False)
                self._activation_by_type[name] = desired
            canonical_pool = _transition_default("pool")
            if not isinstance(canonical_pool, dict):
                raise TypeError("Canonical transitions.pool default must be a mapping")
            pool = cfg.get("pool", canonical_pool)
            if not isinstance(pool, dict):
                pool = canonical_pool
            for name, cb in getattr(self, "_pool_checkboxes", {}).items():
                default_enabled = bool(canonical_pool[name])
                desired = bool(SettingsManager.to_bool(
                    pool.get(name, default_enabled), default_enabled
                ))
                if cb.isChecked() != desired:
                    cb.blockSignals(True)
                    cb.setChecked(desired)
                    cb.blockSignals(False)
                self._pool_by_type[name] = desired
            default_random = bool(_transition_default("random_always"))
            use_random = SettingsManager.to_bool(
                cfg.get("random_always", default_random), default_random
            )
            cbr = getattr(self, "_use_random_checkbox", None)
            if cbr is not None and cbr.isChecked() != use_random:
                cbr.blockSignals(True)
                cbr.setChecked(use_random)
                cbr.blockSignals(False)
            default_type = str(_transition_default("type"))
            new_type = canonicalize_transition_name(
                cfg.get("type", default_type), fallback=default_type
            )
            if new_type and new_type != "Random":
                self._current_transition = new_type
                self.transition_combo.blockSignals(True)
                self.transition_combo.setCurrentText(new_type)
                self.transition_combo.blockSignals(False)

            # External writes can arrive while a specific page is already
            # visible.  Refresh the in-memory duration/direction authorities
            # and only hydrate controls that have actually been built; this
            # keeps a later duration commit from writing stale parameters.
            self._refresh_external_transition_state(cfg)

            # Checkbox signals are blocked above, so their normal retirement
            # callback cannot run.  Retire pages explicitly at this seam.
            for name in tuple(getattr(self, "_built_transition_pages", ())):
                if not self._transition_activated(name):
                    self._retire_transition_page(name)
        finally:
            self._loading = False
        # Reconcile pill visibility (may redirect to SETUP if current deactivated).
        self._apply_transition_pill_visibility()
        self._update_specific_settings()

    def _refresh_external_transition_state(self, transitions_config: dict) -> None:
        """Refresh live state without building any lazy transition page."""
        canonical = _transition_defaults_root()
        try:
            default_duration = int(
                transitions_config.get("duration_ms", canonical["duration_ms"])
            )
        except (TypeError, ValueError):
            default_duration = int(canonical["duration_ms"])
        durations_cfg = transitions_config.get("durations", canonical["durations"])
        if not isinstance(durations_cfg, dict):
            durations_cfg = dict(canonical["durations"])
        self._duration_by_type = {}
        for name in _TRANSITION_SETTING_NAMES:
            if name == "Ripple":
                raw = durations_cfg.get(
                    "Ripple", durations_cfg.get("Rain Drops", default_duration)
                )
            else:
                raw = durations_cfg.get(name, default_duration)
            try:
                self._duration_by_type[name] = int(raw)
            except (TypeError, ValueError):
                self._duration_by_type[name] = default_duration

        def _section(name: str) -> dict:
            section = transitions_config.get(name, canonical[name])
            return section if isinstance(section, dict) else dict(canonical[name])

        for name in self._direction_by_type:
            self._direction_by_type[name] = str(
                _section(name).get("direction", canonical[name]["direction"])
            )

        current = self._current_transition or self.transition_combo.currentText()
        duration = self._duration_by_type.get(current)
        if duration is not None:
            self.duration_slider.blockSignals(True)
            try:
                self.duration_slider.setValue(duration)
                self.duration_value_label.setText(f"{duration} ms")
            finally:
                self.duration_slider.blockSignals(False)

        self._hydrate_built_transition_groups(transitions_config, canonical)
    
    def load_from_settings(self) -> None:
        """Reload all UI controls from settings manager (called after preset change)."""
        self._load_settings()
        logger.debug("[TRANSITIONS_TAB] Reloaded from settings")
    
    _LABEL_WIDTH = 160
    _VALUE_LABEL_WIDTH = 72

    def _aligned_row_widget(self, parent_layout, label_text, *, wrap: bool = True):
        row_widget, content, _ = shared_add_aligned_row_widget(
            parent_layout, label_text, label_width=self._LABEL_WIDTH, wrap=wrap,
        )
        return row_widget, content

    def _aligned_row(self, parent_layout, label_text, *, wrap: bool = True):
        content, _ = shared_add_aligned_row(
            parent_layout, label_text, label_width=self._LABEL_WIDTH, wrap=wrap,
        )
        return content

    def _swatch_row(self, parent_layout, label_text):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 8, 0, 8)
        row_layout.setSpacing(12)
        add_swatch_label(row_layout, label_text, self._LABEL_WIDTH)
        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(12)
        row_layout.addLayout(content, 1)
        parent_layout.addWidget(row_widget)
        return content

    def _add_value_label(self, row_layout, text, *, width: int | None = None):
        label = QLabel(text)
        label.setMinimumWidth(self._VALUE_LABEL_WIDTH if width is None else width)
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        row_layout.addWidget(label)
        return label

    def _style_group_box(self, box: QGroupBox) -> None:
        style_group_box(box)

    def _setup_ui(self) -> None:
        """Setup tab UI with scroll area."""
        # Create scroll area
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet(shared_styles.SCROLL_AREA_STYLE)
        shared_styles.bind_shared_styles(scroll, "SLIDER_STYLE")
        self._scroll_area = scroll
        
        # Layout helpers are instance methods (see below) so lazy per-transition
        # page builders can reuse them; local aliases keep the rest of this
        # method unchanged.
        _aligned_row_widget = self._aligned_row_widget
        _aligned_row = self._aligned_row
        _swatch_row = self._swatch_row
        _add_value_label = self._add_value_label
        _style_group_box = self._style_group_box

        # Create content widget
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        
        # Title
        title = QLabel("Transition Settings")
        shared_styles.apply_shared_label_style(title, "PAGE_TITLE_STYLE")
        layout.addWidget(title)
        
        # Internal selection model. The old visible dropdown is replaced by the
        # pill nav below (E2.3); this combo is retained (not shown) purely as the
        # "currently edited transition" value model that the existing per-transition
        # load/update/save logic already reads from. Phase I removes it once that
        # logic is migrated off it.
        self.transition_combo = StyledComboBox(size_variant="hero")
        self.transition_combo.addItems(_TRANSITION_SETTING_NAMES)
        # No signal connection: the combo is a passive selection MIRROR only.
        # ``_current_transition`` is the authoritative selection; the pill nav
        # drives updates so the hidden combo can never be a second authority.
        self.transition_combo.setVisible(False)

        # Pill/subtab navigation: SETUP first, then one pill per transition.
        # A responsive FlowLayout wraps pills onto extra rows instead of clipping.
        nav_container = FlowContainer(h_spacing=8, v_spacing=8)
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        self._nav_buttons = {}

        def _add_nav_pill(key: str, label: str) -> None:
            button = QPushButton(label)
            button.setCheckable(True)
            shared_styles.bind_shared_styles(
                button, "TRANSITION_NAV_PILL_STYLE", base_style=""
            )
            self._nav_buttons[key] = button
            self._nav_group.addButton(button)
            button.clicked.connect(lambda _checked=False, k=key: self._on_nav_selected(k))
            nav_container.addWidget(button)

        _add_nav_pill(_SETUP_NAV_KEY, "Setup")
        for name in _TRANSITION_SETTING_NAMES:
            _add_nav_pill(name, name)
        layout.addWidget(nav_container)

        # Duration group (slider: short → long)
        duration_group = QGroupBox("Timing")
        _style_group_box(duration_group)
        duration_layout = QVBoxLayout(duration_group)
        duration_layout.setContentsMargins(0, 12, 0, 0)
        duration_layout.setSpacing(12)
        duration_row = _aligned_row(duration_layout, "Duration (Short → Long):")
        self.duration_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.duration_slider.setRange(100, 15000)  # store milliseconds directly (15s max)
        self.duration_slider.setSingleStep(100)
        self.duration_slider.setPageStep(500)
        initial_duration = int(_transition_default("duration_ms"))
        self.duration_slider.setValue(initial_duration)
        self.duration_slider.valueChanged.connect(self._on_duration_changed)
        self.duration_slider.valueCommitted.connect(self._save_settings)
        duration_row.addWidget(self.duration_slider, 1)
        self.duration_value_label = _add_value_label(
            duration_row, f"{initial_duration} ms", width=86
        )
        duration_row.addStretch()
        layout.addWidget(duration_group)
        
        # Direction group (for directional transitions)
        self.direction_group = QGroupBox("Direction")
        _style_group_box(self.direction_group)
        direction_layout = QVBoxLayout(self.direction_group)
        direction_layout.setContentsMargins(0, 12, 0, 0)
        direction_layout.setSpacing(12)
        
        direction_row = _aligned_row(direction_layout, "Direction:")
        self.direction_combo = StyledComboBox()
        # Items are populated dynamically per transition in _update_specific_settings()
        self.direction_combo.currentTextChanged.connect(self._save_settings)
        direction_row.addWidget(self.direction_combo)
        direction_row.addStretch()
        
        layout.addWidget(self.direction_group)

        # Host for lazily-built per-transition specific settings groups. The
        # groups themselves are built on demand (see _ensure_transition_page),
        # not eagerly here, so a deactivated transition is never constructed.
        self._specific_group_host = QWidget()
        self._specific_group_host_layout = QVBoxLayout(self._specific_group_host)
        self._specific_group_host_layout.setContentsMargins(0, 0, 0, 0)
        self._specific_group_host_layout.setSpacing(20)
        layout.addWidget(self._specific_group_host)
        self._built_transition_pages: set[str] = set()
        self._transition_page_attr_names: dict[str, set[str]] = {}

        # Shared groups toggled as a set against the SETUP page. Per-transition
        # specific groups live inside self._specific_group_host and are shown
        # individually by _update_specific_settings once built.
        self._transition_setting_groups = [
            duration_group,
            self.direction_group,
            self._specific_group_host,
        ]

        # SETUP page (activation + Use Random + effective random pool).
        self._setup_page = self._build_setup_page()
        layout.addWidget(self._setup_page)

        layout.addStretch()

        # Set scroll area widget and add to main layout
        scroll.setWidget(content)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

        # Update visibility based on default transition
        self._update_specific_settings()
        # Enforce GL-only availability on initial build
        self._refresh_hw_dependent_options()
        # Default landing is the SETUP page (E2.3).
        setup_button = self._nav_buttons.get(_SETUP_NAV_KEY)
        if setup_button is not None:
            setup_button.setChecked(True)
        self._on_nav_selected(_SETUP_NAV_KEY)

        shared_styles.bind_shared_styles(
            self,
            "SPINBOX_STYLE",
            "COMBOBOX_STYLE",
            "CIRCLE_CHECKBOX_STYLE",
        )

    # ---- E2 capability SETUP subtab ---------------------------------------

    def _build_setup_page(self) -> QWidget:
        """Build the Transitions SETUP page: activation, Use Random, random pool."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(16)

        # Activation module list — a responsive grid that gains columns with width.
        activation_group = QGroupBox("Transition Modules")
        style_group_box(activation_group)
        activation_layout = QVBoxLayout(activation_group)
        activation_layout.setContentsMargins(0, 12, 0, 0)
        activation_layout.setSpacing(8)

        activation_grid_host = FlowContainer(h_spacing=18, v_spacing=8, uniform_cells=True)
        self._activation_checkboxes = {}
        for name in _TRANSITION_SETTING_NAMES:
            row = QCheckBox(name)
            row.setProperty("circleIndicator", True)
            row.setMinimumWidth(_MODULE_ROW_MIN_WIDTH)
            row.setChecked(True)
            row.toggled.connect(
                lambda checked, n=name: self._on_transition_activation_toggled(n, checked)
            )
            self._activation_checkboxes[name] = row
            activation_grid_host.addWidget(row)
        activation_layout.addWidget(activation_grid_host)

        # Enable/Disable All in a wrapping flow so they stay reachable at any width.
        action_host = FlowContainer(h_spacing=10, v_spacing=8)
        enable_all = QPushButton("Enable All")
        disable_all = QPushButton("Disable All")
        shared_styles.bind_shared_styles(
            enable_all, "TRANSITION_SETUP_ACTION_STYLE", base_style=""
        )
        shared_styles.bind_shared_styles(
            disable_all, "TRANSITION_SETUP_ACTION_STYLE", base_style=""
        )
        enable_all.clicked.connect(lambda: self._set_all_transition_activation(True))
        disable_all.clicked.connect(lambda: self._set_all_transition_activation(False))
        action_host.addWidget(enable_all)
        action_host.addWidget(disable_all)
        activation_layout.addWidget(action_host)
        page_layout.addWidget(activation_group)

        # Random mode + effective pool.
        random_group = QGroupBox("Random Transitions")
        style_group_box(random_group)
        random_layout = QVBoxLayout(random_group)
        random_layout.setContentsMargins(0, 12, 0, 0)
        random_layout.setSpacing(8)

        self._use_random_checkbox = QCheckBox("Use Random Transitions")
        self._use_random_checkbox.setProperty("circleIndicator", True)
        self._use_random_checkbox.toggled.connect(self._on_use_random_toggled)
        random_layout.addWidget(self._use_random_checkbox)

        pool_label = QLabel("Random Pool")
        shared_styles.apply_shared_label_style(pool_label, "PAGE_TITLE_STYLE")
        random_layout.addWidget(pool_label)

        pool_grid_host = FlowContainer(h_spacing=18, v_spacing=8, uniform_cells=True)
        self._pool_checkboxes = {}
        for name in _TRANSITION_SETTING_NAMES:
            row = QCheckBox(name)
            row.setProperty("circleIndicator", True)
            row.setMinimumWidth(_MODULE_ROW_MIN_WIDTH)
            row.toggled.connect(
                lambda checked, n=name: self._on_pool_membership_toggled(n, checked)
            )
            self._pool_checkboxes[name] = row
            pool_grid_host.addWidget(row)
        random_layout.addWidget(pool_grid_host)

        page_layout.addWidget(random_group)
        return page

    # ---- Lazy per-transition settings pages -------------------------------
    #
    # Each transition with its own controls is built on demand the first time
    # its pill is selected (doc 07 E2), not eagerly at tab construction. A
    # deactivated transition's page is never built; deactivating a built page
    # retires it; reactivation restores the pill without rebuilding until it is
    # selected again. A page is described by its spec in
    # ``rendering/transition_settings.py``; Crossfade and Warp Dissolve have none
    # and Wipe has only the shared Direction box.

    @staticmethod
    def _page_spec(name: str) -> TransitionSettings | None:
        spec = transition_settings(name)
        return spec if spec is not None and spec.has_page else None

    def _page_group_attr(self, name: str) -> str | None:
        spec = self._page_spec(name)
        return f"{spec.section}_group" if spec is not None else None

    def _ensure_transition_page(self, name: str) -> None:
        """Lazily build one transition's specific settings group + hydrate it."""
        spec = self._page_spec(name)
        if spec is None:
            return
        # A deactivated transition page is never built/hydrated.
        if not self._transition_activated(name):
            return
        if hasattr(self, f"{spec.section}_group"):
            return  # already built
        attrs_before_build = set(vars(self))
        try:
            if spec.custom:
                getattr(self, f"_build_{spec.section}_group")()
            else:
                self._build_spec_page(spec)
            self._transition_page_attr_names[name] = set(vars(self)) - attrs_before_build
            self._hydrate_transition_page(name)
        except Exception:
            # Builders attach their group before hydration.  Roll back both
            # the host child and every widget reference so a retry starts from
            # a clean lazy-page boundary.
            self._retire_transition_page(name)
            raise
        self._built_transition_pages.add(name)

    @staticmethod
    def _widget_belongs_to_group(widget: object, group: object) -> bool:
        """Return whether a QObject widget is a descendant of ``group``."""
        if widget is group:
            return True
        try:
            parent = widget.parentWidget()
            while parent is not None:
                if parent is group:
                    return True
                parent = parent.parentWidget()
        except (AttributeError, RuntimeError):
            # A stale Qt wrapper may already be deleted; it is safe to drop
            # the Python reference while retiring the page.
            return False
        return False

    def _clear_transition_page_refs(self, group: QWidget) -> None:
        """Drop instance attributes pointing into a retired lazy page."""
        for attr, value in tuple(vars(self).items()):
            if attr.startswith("_") and attr not in {"_specific_group_host_layout"}:
                continue
            if self._widget_belongs_to_group(value, group):
                try:
                    delattr(self, attr)
                except AttributeError:
                    pass

    def _retire_transition_page(self, name: str) -> None:
        """Destroy a built transition page cleanly (on deactivation)."""
        group_attr = self._page_group_attr(name)
        if not group_attr or not hasattr(self, group_attr):
            self._transition_page_attr_names.pop(name, None)
            return
        group = getattr(self, group_attr)
        tracked_attrs = self._transition_page_attr_names.pop(name, set())
        # Clear references while the parent relationship is still available;
        # the tracked set also covers a wrapper whose QObject was already
        # deleted by Qt before this retirement callback ran.
        self._clear_transition_page_refs(group)
        for attr in tracked_attrs:
            if hasattr(self, attr):
                try:
                    delattr(self, attr)
                except AttributeError:
                    pass
        try:
            self._specific_group_host_layout.removeWidget(group)
            group.setParent(None)
            group.deleteLater()
        except Exception as e:
            logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)
        if hasattr(self, group_attr):
            delattr(self, group_attr)
        self._built_transition_pages.discard(name)

    def _hydrate_transition_page(self, name: str) -> None:
        """Hydrate a just-built transition page from the current persisted settings."""
        cfg = self._settings.get('transitions') or {}
        if not isinstance(cfg, dict):
            cfg = {}
        canonical = _transition_defaults_root()
        previous_loading = getattr(self, "_loading", False)
        self._loading = True
        try:
            self._hydrate_built_transition_groups(cfg, canonical)
        finally:
            self._loading = previous_loading

    @staticmethod
    def _new_transition_section(
        transitions_config: Mapping[str, object],
        section_name: str,
        canonical: Mapping[str, object],
    ) -> Mapping[str, object]:
        section = transitions_config.get(section_name, canonical)
        if isinstance(section, Mapping):
            return section
        logger.warning(
            "[TRANSITIONS_TAB] Repaired malformed transition section %s",
            section_name,
        )
        return canonical

    def _hydrate_built_transition_groups(self, transitions_config: dict, canonical_transitions: dict) -> None:
        """Hydrate only the transition-specific groups that are currently built.

        Called at load (before any specific group exists -> no-op for specifics)
        and again whenever a transition page is lazily built. Guarded per group so
        an unbuilt page never touches non-existent controls. Callers set
        ``self._loading`` so control signals do not trigger saves during hydration.
        """
        for spec in iter_transition_settings():
            if not spec.has_page or not hasattr(self, f"{spec.section}_group"):
                continue
            canonical = canonical_transitions[spec.section]
            section = self._new_transition_section(transitions_config, spec.section, canonical)
            for control in spec.all_controls:
                self._hydrate_control(spec, control, section, canonical)
            self._sync_enabled_controls(spec)
            if spec.custom:
                getattr(self, f"_hydrate_{spec.section}_page")(section, canonical)

    def _hydrate_control(self, spec: TransitionSettings, control, section: Mapping[str, object],
                         canonical: Mapping[str, object]) -> None:
        """Show one persisted value, repaired exactly as request admission repairs it."""
        widget = getattr(self, widget_attr(spec.section, control))
        raw = section.get(control.field, canonical[control.field])
        value = control.admit(raw, canonical[control.field])
        if isinstance(control, Number):
            if raw != value:
                logger.warning("[TRANSITIONS_TAB] Repaired transition field %s.%s", spec.section, control.field)
            widget.setValue(value)
        elif isinstance(control, Toggle):
            widget.setChecked(value)
        elif isinstance(control, Choice):
            widget.setCurrentText(value)
        else:
            widget.set_color(QColor(*value))

    def _control_value(self, spec: TransitionSettings, control) -> object:
        """One built control's value, as it is persisted."""
        widget = getattr(self, widget_attr(spec.section, control))
        if isinstance(control, Number):
            return int(widget.value()) if control.integer else float(widget.value())
        if isinstance(control, Toggle):
            return widget.isChecked()
        if isinstance(control, Choice):
            return widget.currentText()
        color = widget.color()
        return [color.red(), color.green(), color.blue(), 255]

    def _page_widgets(self) -> list[QWidget]:
        """Every built transition page control declared by a spec (for signal blocking)."""
        widgets = []
        for spec in iter_transition_settings():
            if hasattr(self, f"{spec.section}_group"):
                widgets.extend(getattr(self, widget_attr(spec.section, control)) for control in spec.all_controls)
        return widgets

    def _build_spec_page(self, spec: TransitionSettings) -> None:
        """Build a transition's page from its spec: its controls, then its closed Advanced bucket."""
        group = QGroupBox(spec.page_title)
        self._style_group_box(group)
        setattr(self, f"{spec.section}_group", group)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(0, 12, 0, 0)
        for control in spec.controls:
            self._build_control(layout, spec, control)
        self._build_advanced(layout, spec)
        self._sync_enabled_controls(spec)
        self._specific_group_host_layout.addWidget(group)

    def _build_advanced(self, layout, spec: TransitionSettings) -> None:
        # Operator direction (2026-09-29): a page's optional quality and look choices, which will
        # grow, live in one closed "Advanced" bucket; the controls that shape the effect itself
        # stay on the page.
        if not spec.advanced:
            return
        bucket_id = f"transitions:{spec.section}"
        toggle, body, advanced = shared_styles.build_bucket_toggle(
            layout, "Advanced",
            expanded=self._settings.get("ui.basic_bucket_path") == bucket_id,
            on_toggle=lambda checked, k=bucket_id: self._set_transition_bucket(k, checked),
        )
        toggle.setToolTip("Quality and optional effects for this transition.")
        setattr(self, f"{spec.section}_advanced_toggle", toggle)
        setattr(self, f"{spec.section}_advanced_body", body)
        for control in spec.advanced:
            self._build_control(advanced, spec, control)

    def _build_control(self, layout, spec: TransitionSettings, control) -> QWidget:
        """Build one declared control in its own row, showing the canonical default until hydrated."""
        default = _transition_default(f"{spec.section}.{control.field}")
        if isinstance(control, Number):
            row = self._aligned_row(layout, control.label)
            widget = QSpinBox() if control.integer else QDoubleSpinBox()
            if control.integer:
                widget.setRange(int(control.low), int(control.high))
            else:
                widget.setDecimals(control.decimals)
                widget.setRange(float(control.low), float(control.high))
                widget.setSingleStep(control.step)
            if control.suffix:
                widget.setSuffix(control.suffix)
            widget.setValue(control.admit(default, default))
            widget.valueChanged.connect(self._save_settings)
        elif isinstance(control, Toggle):
            row = self._aligned_row(layout, "", wrap=False)
            widget = QCheckBox(control.label)
            widget.setProperty("circleIndicator", True)
            widget.setChecked(control.admit(default, default))
            widget.stateChanged.connect(self._save_settings)
        elif isinstance(control, Choice):
            row = self._aligned_row(layout, control.label)
            widget = StyledComboBox(size_variant="compact") if control.compact else StyledComboBox()
            widget.addItems(list(control.choices))
            widget.setCurrentText(control.admit(default, default))
            if any(isinstance(other, Colour) and other.enabled_when and other.enabled_when[0] == control.field
                   for other in spec.all_controls):
                widget.currentTextChanged.connect(lambda _text, s=spec: self._sync_enabled_controls(s))
            widget.currentTextChanged.connect(self._save_settings)
        else:
            row = self._swatch_row(layout, control.label)
            widget = ColorSwatchButton(title=control.title, show_alpha=False, auto_picker=False)
            widget.set_color(QColor(*control.admit(default, default)))
            widget.setFixedSize(60, 24)
            widget.clicked.connect(lambda _checked=False, s=spec, c=control: self._pick_control_colour(s, c))
        if control.tooltip:
            widget.setToolTip(control.tooltip)
        row.addWidget(widget)
        row.addStretch()
        setattr(self, widget_attr(spec.section, control), widget)
        return widget

    def _sync_enabled_controls(self, spec: TransitionSettings) -> None:
        """A colour that applies under one choice only is disabled under the others."""
        for control in spec.all_controls:
            if isinstance(control, Colour) and control.enabled_when is not None:
                field, label = control.enabled_when
                combo = getattr(self, widget_attr(spec.section, spec.control(field)), None)
                button = getattr(self, widget_attr(spec.section, control), None)
                if combo is not None and button is not None:
                    button.setEnabled(combo.currentText() == label)

    def _pick_control_colour(self, spec: TransitionSettings, control: Colour) -> None:
        button = getattr(self, widget_attr(spec.section, control))
        color = StyledColorPicker.get_color(button.color(), self, control.label.rstrip(":"), show_alpha=False)
        if color is not None:
            button.set_color(color)
            self._save_settings()

    # ---- Pages with their own controls (spec ``custom``) ------------------

    def _hydrate_blinds_page(self, blinds: Mapping[str, object], canonical: Mapping[str, object]) -> None:
        try:
            value = int(blinds.get('feather', canonical['feather']))
        except (TypeError, ValueError):
            value = int(canonical['feather'])
        self.blinds_feather_slider.setValue(value)
        self.blinds_feather_label.setText(str(self.blinds_feather_slider.value()))
        self._sync_blinds_style()

    def _save_blinds_page(self, values: dict) -> None:
        self.blinds_feather_label.setText(str(self.blinds_feather_slider.value()))
        values['feather'] = self.blinds_feather_slider.value()

    def _hydrate_particle_page(self, particle: Mapping[str, object], canonical_particle: Mapping[str, object]) -> None:
        mode = particle.get('mode', canonical_particle['mode'])
        idx = self.particle_mode_combo.findText(mode)
        if idx >= 0:
            self.particle_mode_combo.setCurrentIndex(idx)
        direction = particle.get('direction', canonical_particle['direction'])
        idx = self.particle_direction_combo.findText(direction)
        if idx >= 0:
            self.particle_direction_combo.setCurrentIndex(idx)
        self.particle_radius_spin.setValue(int(particle.get('particle_radius', canonical_particle['particle_radius'])))
        self.particle_trail_check.setChecked(particle.get('trail_strength', canonical_particle['trail_strength']) > 0.01)
        self.particle_3d_check.setChecked(particle.get('use_3d_shading', canonical_particle['use_3d_shading']))
        self.particle_texture_check.setChecked(particle.get('texture_mapping', canonical_particle['texture_mapping']))
        self.particle_wobble_check.setChecked(particle.get('wobble', canonical_particle['wobble']))
        self.particle_gloss_spin.setValue(int(particle.get('gloss_size', canonical_particle['gloss_size'])))
        light_idx = particle.get('light_direction', canonical_particle['light_direction'])
        if 0 <= light_idx < self.particle_light_combo.count():
            self.particle_light_combo.setCurrentIndex(light_idx)
        self.particle_swirl_turns_spin.setValue(particle.get('swirl_turns', canonical_particle['swirl_turns']))
        swirl_order_idx = particle.get('swirl_order', canonical_particle['swirl_order'])
        if 0 <= swirl_order_idx < self.particle_swirl_order_combo.count():
            self.particle_swirl_order_combo.setCurrentIndex(swirl_order_idx)
        self._update_particle_mode_visibility()
    def _save_particle_page(self, values: dict) -> None:
        trail = self.particle_trail_check.isChecked()
        values.update({
            'mode': self.particle_mode_combo.currentText(),
            'direction': self.particle_direction_combo.currentText(),
            'particle_radius': float(self.particle_radius_spin.value()),
            'overlap': 4.0,
            'trail_length': 0.15 if trail else 0.0,
            'trail_strength': 0.6 if trail else 0.0,
            'swirl_strength': 1.0,
            'swirl_turns': self.particle_swirl_turns_spin.value(),
            'use_3d_shading': self.particle_3d_check.isChecked(),
            'texture_mapping': self.particle_texture_check.isChecked(),
            'wobble': self.particle_wobble_check.isChecked(),
            'gloss_size': float(self.particle_gloss_spin.value()),
            'light_direction': self.particle_light_combo.currentIndex(),
            'swirl_order': self.particle_swirl_order_combo.currentIndex(),
        })

    def _particle_widgets(self) -> list[QWidget]:
        return [getattr(self, f"particle_{name}", None) for name in (
            "mode_combo", "direction_combo", "radius_spin", "trail_check", "3d_check", "texture_check",
            "wobble_check", "gloss_spin", "light_combo", "swirl_turns_spin", "swirl_order_combo")]

    def _hydrate_burn_page(self, burn: Mapping[str, object], canonical_burn: Mapping[str, object]) -> None:
        canonical_burn_dir = str(canonical_burn['direction']).strip()
        if not canonical_burn_dir:
            raise ValueError("Canonical transitions.burn.direction is empty")
        burn_dir = str(burn.get('direction', canonical_burn_dir) or '').strip()
        idx = self.burn_direction_combo.findText(burn_dir)
        if idx < 0:
            idx = self.burn_direction_combo.findText(canonical_burn_dir)
        if idx < 0:
            raise ValueError(
                f"Canonical burn direction is not represented by the UI: {canonical_burn_dir!r}"
            )
        self.burn_direction_combo.setCurrentIndex(idx)
        jag = int(round(burn.get('jaggedness', canonical_burn['jaggedness']) * 100))
        self.burn_jaggedness_slider.setValue(max(0, min(100, jag)))
        self.burn_jaggedness_label.setText(f"{self.burn_jaggedness_slider.value()}%")
        glow_i = int(round(burn.get('glow_intensity', canonical_burn['glow_intensity']) * 100))
        self.burn_glow_intensity_slider.setValue(max(0, min(100, glow_i)))
        self.burn_glow_intensity_label.setText(f"{self.burn_glow_intensity_slider.value()}%")
        char_w = int(round(burn.get('char_width', canonical_burn['char_width']) * 100))
        self.burn_char_width_slider.setValue(max(10, min(100, char_w)))
        self.burn_char_width_label.setText(f"{self.burn_char_width_slider.value()}%")
        glow_col = burn.get('glow_color', canonical_burn['glow_color'])
        if isinstance(glow_col, (list, tuple)) and len(glow_col) >= 3:
            self._burn_glow_color = QColor(int(glow_col[0]), int(glow_col[1]), int(glow_col[2]),
                                           int(glow_col[3]) if len(glow_col) > 3 else 255)
            self._apply_burn_glow_color_btn()
        ember_col = burn.get('ember_color', canonical_burn['ember_color'])
        if isinstance(ember_col, (list, tuple)) and len(ember_col) >= 3:
            self._burn_ember_color = QColor(int(ember_col[0]), int(ember_col[1]), int(ember_col[2]),
                                            int(ember_col[3]) if len(ember_col) > 3 else 255)
            self._apply_burn_ember_color_btn()
        self.burn_smoke_check.setChecked(bool(burn.get('smoke_enabled', canonical_burn['smoke_enabled'])))
        smoke_d = int(round(burn.get('smoke_density', canonical_burn['smoke_density']) * 100))
        self.burn_smoke_density_slider.setValue(max(0, min(100, smoke_d)))
        self.burn_smoke_density_label.setText(f"{self.burn_smoke_density_slider.value()}%")
        self.burn_ash_check.setChecked(bool(burn.get('ash_enabled', canonical_burn['ash_enabled'])))
        ash_d = int(round(burn.get('ash_density', canonical_burn['ash_density']) * 100))
        self.burn_ash_density_slider.setValue(max(0, min(100, ash_d)))
        self.burn_ash_density_label.setText(f"{self.burn_ash_density_slider.value()}%")
        self.burn_flames_check.setChecked(bool(burn.get('flames', canonical_burn['flames'])))
        self.burn_veins_check.setChecked(bool(burn.get('ember_veins', canonical_burn['ember_veins'])))
    def _save_burn_page(self, values: dict) -> None:
        glow, ember = self._burn_glow_color, self._burn_ember_color
        values.update({
            'direction': self.burn_direction_combo.currentText(),
            'jaggedness': self.burn_jaggedness_slider.value() / 100.0,
            'glow_intensity': self.burn_glow_intensity_slider.value() / 100.0,
            'char_width': self.burn_char_width_slider.value() / 100.0,
            'glow_color': [glow.red(), glow.green(), glow.blue(), glow.alpha()],
            'ember_color': [ember.red(), ember.green(), ember.blue(), ember.alpha()],
            'smoke_enabled': self.burn_smoke_check.isChecked(),
            'smoke_density': self.burn_smoke_density_slider.value() / 100.0,
            'ash_enabled': self.burn_ash_check.isChecked(),
            'ash_density': self.burn_ash_density_slider.value() / 100.0,
            'flames': self.burn_flames_check.isChecked(),
            'ember_veins': self.burn_veins_check.isChecked(),
        })

    def _burn_widgets(self) -> list[QWidget]:
        return [getattr(self, f"burn_{name}", None) for name in (
            "direction_combo", "jaggedness_slider", "glow_intensity_slider", "char_width_slider", "smoke_check",
            "smoke_density_slider", "ash_check", "flames_check", "veins_check", "ash_density_slider")]

    def _sync_blinds_style(self, *_args) -> None:
        """Show the controls of the chosen Blinds style only."""
        slats = self.blinds_style_combo.currentText() == "3D Slats"
        self.blinds_flat_box.setVisible(not slats)
        self.blinds_slats_box.setVisible(slats)

    def _build_blinds_group(self) -> None:
        spec = transition_settings("blinds")
        self.blinds_group = QGroupBox(spec.page_title)
        self._style_group_box(self.blinds_group)
        blinds_layout = QVBoxLayout(self.blinds_group)
        blinds_layout.setContentsMargins(0, 12, 0, 0)
        self._build_control(blinds_layout, spec, spec.control("style"))
        self.blinds_style_combo.currentTextChanged.connect(self._sync_blinds_style)
        self._build_control(blinds_layout, spec, spec.control("direction"))

        self.blinds_flat_box = QWidget()
        flat_layout = QVBoxLayout(self.blinds_flat_box)
        flat_layout.setContentsMargins(0, 0, 0, 0)
        blinds_layout.addWidget(self.blinds_flat_box)
        blinds_feather_row = self._aligned_row(flat_layout, "Edge Softness:")
        self.blinds_feather_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.blinds_feather_slider.setRange(0, 25)
        self.blinds_feather_slider.setSingleStep(1)
        self.blinds_feather_slider.setValue(int(_transition_default("blinds.feather")))
        self.blinds_feather_slider.valueCommitted.connect(self._save_settings)
        blinds_feather_row.addWidget(self.blinds_feather_slider, 1)
        self.blinds_feather_label = self._add_value_label(blinds_feather_row, "2")
        blinds_feather_row.addStretch()

        self.blinds_slats_box = QWidget()
        slats_layout = QVBoxLayout(self.blinds_slats_box)
        slats_layout.setContentsMargins(0, 0, 0, 0)
        blinds_layout.addWidget(self.blinds_slats_box)
        self._build_control(slats_layout, spec, spec.control("slats"))
        self._build_control(slats_layout, spec, spec.control("gloss"))
        self._build_advanced(slats_layout, spec)
        self._sync_blinds_style()

        self._specific_group_host_layout.addWidget(self.blinds_group)

    def _build_particle_group(self) -> None:
        _aligned_row = self._aligned_row
        self.particle_group = QGroupBox("Particle Settings")
        self._style_group_box(self.particle_group)
        particle_layout = QVBoxLayout(self.particle_group)
        particle_layout.setContentsMargins(0, 12, 0, 0)

        particle_mode_row = _aligned_row(particle_layout, "Mode:")
        self.particle_mode_combo = StyledComboBox(size_variant="compact")
        self.particle_mode_combo.addItems(["Directional", "Swirl", "Converge", "Random"])
        self.particle_mode_combo.currentIndexChanged.connect(self._on_particle_mode_changed)
        self.particle_mode_combo.currentIndexChanged.connect(self._save_settings)
        particle_mode_row.addWidget(self.particle_mode_combo)
        particle_mode_row.addStretch()

        particle_direction_row = _aligned_row(particle_layout, "Direction:")
        self.particle_direction_combo = StyledComboBox(size_variant="compact")
        self.particle_direction_combo.addItems([
            "Left to Right",
            "Right to Left",
            "Top to Bottom",
            "Bottom to Top",
            "Random",
        ])
        self.particle_direction_combo.currentTextChanged.connect(self._save_settings)
        particle_direction_row.addWidget(self.particle_direction_combo)
        particle_direction_row.addStretch()

        particle_radius_row = _aligned_row(particle_layout, "Particle Radius:")
        self.particle_radius_spin = QSpinBox()
        self.particle_radius_spin.setRange(4, 80)
        self.particle_radius_spin.setValue(int(round(float(_transition_default("particle.particle_radius")))))
        self.particle_radius_spin.valueChanged.connect(self._save_settings)
        particle_radius_row.addWidget(self.particle_radius_spin)
        particle_radius_row.addStretch()

        particle_trail_row = _aligned_row(particle_layout, "", wrap=False)
        self.particle_trail_check = QCheckBox("Motion Trail")
        self.particle_trail_check.setProperty("circleIndicator", True)
        self.particle_trail_check.setChecked(float(_transition_default("particle.trail_strength")) > 0.01)
        self.particle_trail_check.stateChanged.connect(self._save_settings)
        particle_trail_row.addWidget(self.particle_trail_check)
        particle_trail_row.addStretch()

        particle_3d_row = _aligned_row(particle_layout, "", wrap=False)
        self.particle_3d_check = QCheckBox("3D Ball Shading")
        self.particle_3d_check.setProperty("circleIndicator", True)
        self.particle_3d_check.setChecked(bool(_transition_default("particle.use_3d_shading")))
        self.particle_3d_check.stateChanged.connect(self._save_settings)
        particle_3d_row.addWidget(self.particle_3d_check)
        particle_3d_row.addStretch()

        particle_texture_row = _aligned_row(particle_layout, "", wrap=False)
        self.particle_texture_check = QCheckBox("Map Image to Particles")
        self.particle_texture_check.setProperty("circleIndicator", True)
        self.particle_texture_check.setChecked(bool(_transition_default("particle.texture_mapping")))
        self.particle_texture_check.stateChanged.connect(self._save_settings)
        particle_texture_row.addWidget(self.particle_texture_check)
        particle_texture_row.addStretch()

        particle_wobble_row = _aligned_row(particle_layout, "", wrap=False)
        self.particle_wobble_check = QCheckBox("Wobble on Arrival")
        self.particle_wobble_check.setProperty("circleIndicator", True)
        self.particle_wobble_check.setChecked(bool(_transition_default("particle.wobble")))
        self.particle_wobble_check.stateChanged.connect(self._save_settings)
        particle_wobble_row.addWidget(self.particle_wobble_check)
        particle_wobble_row.addStretch()

        particle_gloss_row = _aligned_row(particle_layout, "Gloss Size:")
        self.particle_gloss_spin = QSpinBox()
        self.particle_gloss_spin.setRange(10, 200)
        self.particle_gloss_spin.setValue(int(round(float(_transition_default("particle.gloss_size")))))
        self.particle_gloss_spin.valueChanged.connect(self._save_settings)
        particle_gloss_row.addWidget(self.particle_gloss_spin)
        particle_gloss_row.addStretch()

        particle_light_row = _aligned_row(particle_layout, "Light Direction:")
        self.particle_light_combo = StyledComboBox(size_variant="compact")
        self.particle_light_combo.addItems([
            "NW",
            "NE",
            "Front",
            "SW",
            "SE",
        ])
        self.particle_light_combo.currentIndexChanged.connect(self._save_settings)
        particle_light_row.addWidget(self.particle_light_combo)
        particle_light_row.addStretch()

        particle_swirl_turns_row = _aligned_row(particle_layout, "Swirl Turns:")
        self.particle_swirl_turns_spin = QDoubleSpinBox()
        self.particle_swirl_turns_spin.setDecimals(2)
        self.particle_swirl_turns_spin.setRange(0.5, 6.0)
        self.particle_swirl_turns_spin.setSingleStep(0.1)
        self.particle_swirl_turns_spin.setValue(float(_transition_default("particle.swirl_turns")))
        self.particle_swirl_turns_spin.valueChanged.connect(self._save_settings)
        particle_swirl_turns_row.addWidget(self.particle_swirl_turns_spin)
        particle_swirl_turns_row.addStretch()

        particle_swirl_order_row = _aligned_row(particle_layout, "Swirl Build Order:")
        self.particle_swirl_order_combo = StyledComboBox(size_variant="compact")
        self.particle_swirl_order_combo.addItems([
            "Typical",
            "Center Outward",
            "Edges Inward",
        ])
        self.particle_swirl_order_combo.currentIndexChanged.connect(self._save_settings)
        particle_swirl_order_row.addWidget(self.particle_swirl_order_combo)
        particle_swirl_order_row.addStretch()

        self._specific_group_host_layout.addWidget(self.particle_group)
        self._update_particle_mode_visibility()

    def _build_burn_group(self) -> None:
        _aligned_row = self._aligned_row
        _swatch_row = self._swatch_row
        self.burn_group = QGroupBox("Burn Settings")
        self._style_group_box(self.burn_group)
        burn_layout = QVBoxLayout(self.burn_group)
        burn_layout.setContentsMargins(0, 12, 0, 0)

        burn_dir_row = _aligned_row(burn_layout, "Direction:")
        self.burn_direction_combo = StyledComboBox(size_variant="compact")
        self.burn_direction_combo.addItems([
            "Left to Right",
            "Right to Left",
            "Top to Bottom",
            "Bottom to Top",
            "Diagonal TL-BR",
            "Diagonal TR-BL",
            "Random",
        ])
        self.burn_direction_combo.currentIndexChanged.connect(self._save_settings)
        burn_dir_row.addWidget(self.burn_direction_combo)
        burn_dir_row.addStretch()

        burn_jag_row = _aligned_row(burn_layout, "Jaggedness:")
        self.burn_jaggedness_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.burn_jaggedness_slider.setRange(0, 100)
        burn_jaggedness_default = int(round(float(_transition_default("burn.jaggedness")) * 100.0))
        self.burn_jaggedness_slider.setValue(burn_jaggedness_default)
        self.burn_jaggedness_slider.setToolTip("Edge noise amplitude (0 = smooth wipe, 100 = very jagged)")
        self.burn_jaggedness_slider.valueCommitted.connect(self._save_settings)
        burn_jag_row.addWidget(self.burn_jaggedness_slider, 1)
        self.burn_jaggedness_label = self._add_value_label(
            burn_jag_row, f"{burn_jaggedness_default}%"
        )
        self.burn_jaggedness_slider.valueChanged.connect(
            lambda v: self.burn_jaggedness_label.setText(f"{v}%")
        )

        burn_glow_row = _aligned_row(burn_layout, "Glow Intensity:")
        self.burn_glow_intensity_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.burn_glow_intensity_slider.setRange(0, 100)
        burn_glow_default = int(round(float(_transition_default("burn.glow_intensity")) * 100.0))
        self.burn_glow_intensity_slider.setValue(burn_glow_default)
        self.burn_glow_intensity_slider.setToolTip("Warm glow brightness on the burning edge")
        self.burn_glow_intensity_slider.valueCommitted.connect(self._save_settings)
        burn_glow_row.addWidget(self.burn_glow_intensity_slider, 1)
        self.burn_glow_intensity_label = self._add_value_label(
            burn_glow_row, f"{burn_glow_default}%"
        )
        self.burn_glow_intensity_slider.valueChanged.connect(
            lambda v: self.burn_glow_intensity_label.setText(f"{v}%")
        )

        burn_char_row = _aligned_row(burn_layout, "Char Width:")
        self.burn_char_width_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.burn_char_width_slider.setRange(10, 100)
        burn_char_default = int(round(float(_transition_default("burn.char_width")) * 100.0))
        self.burn_char_width_slider.setValue(burn_char_default)
        self.burn_char_width_slider.setToolTip("Width of the charred/blackened zone behind the burn front")
        self.burn_char_width_slider.valueCommitted.connect(self._save_settings)
        burn_char_row.addWidget(self.burn_char_width_slider, 1)
        self.burn_char_width_label = self._add_value_label(
            burn_char_row, f"{burn_char_default}%"
        )
        self.burn_char_width_slider.valueChanged.connect(
            lambda v: self.burn_char_width_label.setText(f"{v}%")
        )

        burn_color_row = _swatch_row(burn_layout, "Glow Colour:")
        self.burn_glow_color_btn = ColorSwatchButton(
            title="Choose Burn Glow Colour", show_alpha=True, auto_picker=False
        )
        self._burn_glow_color = QColor(*_transition_default("burn.glow_color"))
        self._apply_burn_glow_color_btn()
        self.burn_glow_color_btn.setFixedSize(60, 24)
        self.burn_glow_color_btn.setToolTip("Primary glow colour on the burning edge")
        self.burn_glow_color_btn.clicked.connect(self._pick_burn_glow_color)
        burn_color_row.addWidget(self.burn_glow_color_btn)
        burn_color_row.addStretch()

        burn_ember_color_row = _swatch_row(burn_layout, "Ember Colour:")
        self.burn_ember_color_btn = ColorSwatchButton(
            title="Choose Burn Ember Colour", show_alpha=True, auto_picker=False
        )
        self._burn_ember_color = QColor(*_transition_default("burn.ember_color"))
        self._apply_burn_ember_color_btn()
        self.burn_ember_color_btn.setFixedSize(60, 24)
        self.burn_ember_color_btn.setToolTip(
            "Secondary ember/char colour behind the burn front"
        )
        self.burn_ember_color_btn.clicked.connect(self._pick_burn_ember_color)
        burn_ember_color_row.addWidget(self.burn_ember_color_btn)
        burn_ember_color_row.addStretch()

        burn_smoke_row = _aligned_row(burn_layout, "", wrap=False)
        self.burn_smoke_check = QCheckBox("Sparks")
        self.burn_smoke_check.setProperty("circleIndicator", True)
        self.burn_smoke_check.setChecked(bool(_transition_default("burn.smoke_enabled")))
        self.burn_smoke_check.setToolTip("Enable bright sparks flying off the burn front")
        self.burn_smoke_check.stateChanged.connect(self._save_settings)
        burn_smoke_row.addWidget(self.burn_smoke_check)
        burn_smoke_row.addStretch()

        burn_smoke_density_row = _aligned_row(burn_layout, "Spark Intensity:")
        self.burn_smoke_density_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.burn_smoke_density_slider.setRange(0, 100)
        burn_smoke_density_default = int(round(float(_transition_default("burn.smoke_density")) * 100.0))
        self.burn_smoke_density_slider.setValue(burn_smoke_density_default)
        self.burn_smoke_density_slider.valueCommitted.connect(self._save_settings)
        burn_smoke_density_row.addWidget(self.burn_smoke_density_slider, 1)
        self.burn_smoke_density_label = self._add_value_label(
            burn_smoke_density_row, f"{burn_smoke_density_default}%"
        )
        self.burn_smoke_density_slider.valueChanged.connect(
            lambda v: self.burn_smoke_density_label.setText(f"{v}%")
        )

        burn_ash_row = _aligned_row(burn_layout, "", wrap=False)
        self.burn_ash_check = QCheckBox("Ash Particles")
        self.burn_ash_check.setProperty("circleIndicator", True)
        self.burn_ash_check.setChecked(bool(_transition_default("burn.ash_enabled")))
        self.burn_ash_check.setToolTip("Enable falling ash specks below the burn front")
        self.burn_ash_check.stateChanged.connect(self._save_settings)
        burn_ash_row.addWidget(self.burn_ash_check)
        burn_ash_row.addStretch()

        burn_flames_row = _aligned_row(burn_layout, "", wrap=False)
        self.burn_flames_check = QCheckBox("Flames")
        self.burn_flames_check.setProperty("circleIndicator", True)
        self.burn_flames_check.setChecked(bool(_transition_default("burn.flames")))
        self.burn_flames_check.setToolTip("Flames licking up from the burning edge, in the glow and ember colours.")
        self.burn_flames_check.stateChanged.connect(self._save_settings)
        burn_flames_row.addWidget(self.burn_flames_check)
        burn_flames_row.addStretch()

        burn_veins_row = _aligned_row(burn_layout, "", wrap=False)
        self.burn_veins_check = QCheckBox("Ember Veins")
        self.burn_veins_check.setProperty("circleIndicator", True)
        self.burn_veins_check.setChecked(bool(_transition_default("burn.ember_veins")))
        self.burn_veins_check.setToolTip("Thin glowing cracks crawling through the fresh char.")
        self.burn_veins_check.stateChanged.connect(self._save_settings)
        burn_veins_row.addWidget(self.burn_veins_check)
        burn_veins_row.addStretch()

        burn_ash_density_row = _aligned_row(burn_layout, "Ash Density:")
        self.burn_ash_density_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.burn_ash_density_slider.setRange(0, 100)
        burn_ash_density_default = int(round(float(_transition_default("burn.ash_density")) * 100.0))
        self.burn_ash_density_slider.setValue(burn_ash_density_default)
        self.burn_ash_density_slider.valueCommitted.connect(self._save_settings)
        burn_ash_density_row.addWidget(self.burn_ash_density_slider, 1)
        self.burn_ash_density_label = self._add_value_label(
            burn_ash_density_row, f"{burn_ash_density_default}%"
        )
        self.burn_ash_density_slider.valueChanged.connect(
            lambda v: self.burn_ash_density_label.setText(f"{v}%")
        )

        self._specific_group_host_layout.addWidget(self.burn_group)

    def _admit_nav_key(self, key: str) -> str:
        """Return SETUP for any deactivated transition; otherwise the key.

        Centralized transition-navigation admission so a stale/programmatic
        selection of a deactivated transition never leaves SETUP, mutates
        _current_transition, mirrors the combo, builds a page, or saves.
        """
        if key == _SETUP_NAV_KEY:
            return key
        if not self._transition_activated(key):
            return _SETUP_NAV_KEY
        return key

    def _reset_view_scroll(self) -> None:
        """Anchor semantic Transition navigation at the top of its section."""

        scroll = getattr(self, "_scroll_area", None)
        if scroll is None:
            return
        # 0 survives the later layout pass (a range change only clamps values
        # above the new maximum), so no deferred second reset is needed.
        scroll.verticalScrollBar().setValue(0)

    def get_view_state(self) -> dict[str, str]:
        """Persist the selected Transition pill, never a pixel scroll offset."""

        return {"pill": self._current_nav_key()}

    def restore_view_state(self, state: dict) -> None:
        """Restore an admitted Transition pill and start it at the section top."""

        requested = _SETUP_NAV_KEY
        if isinstance(state, dict):
            value = state.get("pill")
            if isinstance(value, str) and value in getattr(self, "_nav_buttons", {}):
                requested = value
        admitted = self._admit_nav_key(requested)
        button = getattr(self, "_nav_buttons", {}).get(admitted)
        previous_loading = getattr(self, "_loading", False)
        self._loading = True
        try:
            if button is not None:
                button.setChecked(True)
            self._on_nav_selected(admitted)
        finally:
            self._loading = previous_loading
        self._reset_view_scroll()

    def _set_transition_bucket(self, bucket_id: str, checked: bool) -> None:
        previous = self._settings.get("ui.basic_bucket_path")
        if checked or previous == bucket_id:
            self._settings.set("ui.basic_bucket_path", bucket_id if checked else "", emit_change=False)

    def retire_bucket_context(self) -> None:
        shared_styles.collapse_settings_bucket_tree(self)
        if str(self._settings.get("ui.basic_bucket_path") or "").startswith("transitions:"):
            self._settings.set("ui.basic_bucket_path", "", emit_change=False)

    def _on_nav_selected(self, key: str) -> None:
        """Show either the SETUP page or one transition's settings groups."""
        # Admission first: a deactivated transition redirects to SETUP before any
        # selection state, mirror, page build, or save happens.
        admitted = self._admit_nav_key(key)
        if admitted != key:
            button = self._nav_buttons.get(admitted)
            if button is not None:
                button.setChecked(True)
        key = admitted
        old_key = getattr(self, "_active_bucket_nav_key", None)
        if (old_key is not None and old_key != key
                and not getattr(self, "_loading", False)):
            self.retire_bucket_context()
        self._active_bucket_nav_key = key
        show_setup = key == _SETUP_NAV_KEY
        self._setup_page.setVisible(show_setup)
        for group in getattr(self, "_transition_setting_groups", []):
            group.setVisible(not show_setup)
        if show_setup:
            self._reset_view_scroll()
            return
        # ``_current_transition`` is the authoritative edited/manual selection.
        # The hidden combo is only a passive mirror kept for legacy readers.
        self._current_transition = key
        self.transition_combo.blockSignals(True)
        try:
            self.transition_combo.setCurrentText(key)
        finally:
            self.transition_combo.blockSignals(False)
        # Lazy-build this transition's page on first entry, then reflect it.
        self._ensure_transition_page(key)
        self._update_specific_settings()
        cur_duration = self._duration_by_type.get(key, self.duration_slider.value())
        self.duration_slider.blockSignals(True)
        try:
            self.duration_slider.setValue(cur_duration)
            self.duration_value_label.setText(f"{cur_duration} ms")
        finally:
            self.duration_slider.blockSignals(False)
        # Selecting a transition records it as the remembered manual selection.
        # It never changes random_always (owned by the Use Random checkbox), so
        # browsing while Random is on leaves Random enabled.
        if not getattr(self, "_loading", False):
            self._save_settings()
        self._reset_view_scroll()

    def _apply_transition_pill_visibility(self) -> None:
        """Reconcile descriptor admission, activation and quarantined controls."""
        deactivated_current = False
        current = self._current_transition or self.transition_combo.currentText()
        for name, button in self._nav_buttons.items():
            if name == _SETUP_NAV_KEY:
                continue
            available = is_transition_available(name)
            activated = self._transition_activated(name)
            button.setVisible(available and activated)
            button.setEnabled(available and activated)
            button.setToolTip(transition_unavailability_reason(name) if not available else "")
            pool_row = getattr(self, "_pool_checkboxes", {}).get(name)
            if pool_row is not None:
                pool_row.setVisible(available and activated)
                pool_row.setEnabled(available and activated)
                pool_row.setToolTip(transition_unavailability_reason(name) if not available else "")
            activation_row = getattr(self, "_activation_checkboxes", {}).get(name)
            if activation_row is not None:
                activation_row.setEnabled(available)
                activation_row.setToolTip(transition_unavailability_reason(name) if not available else "")
            if not activated and name == current:
                deactivated_current = True
        if not getattr(self, "_loading", False) and deactivated_current:
            setup_button = self._nav_buttons.get(_SETUP_NAV_KEY)
            if setup_button is not None:
                setup_button.setChecked(True)
            self._on_nav_selected(_SETUP_NAV_KEY)

    def _transition_activated(self, name: str) -> bool:
        if not is_transition_available(name):
            return False
        checkbox = getattr(self, "_activation_checkboxes", {}).get(name)
        if checkbox is not None:
            return bool(checkbox.isChecked())
        return bool(
            self._activation_by_type.get(
                name, bool(_transition_default(f"activation.{name}"))
            )
        )

    def _on_transition_activation_toggled(self, name: str, checked: bool) -> None:
        self._activation_by_type[name] = bool(checked)
        if not checked:
            # Retire a built page cleanly on deactivation.
            self._retire_transition_page(name)
        self._apply_transition_pill_visibility()
        if not getattr(self, "_loading", False):
            self._save_settings()

    def _set_all_transition_activation(self, activated: bool) -> None:
        changed = False
        for name, checkbox in getattr(self, "_activation_checkboxes", {}).items():
            if checkbox.isChecked() != activated:
                checkbox.blockSignals(True)
                checkbox.setChecked(activated)
                checkbox.blockSignals(False)
                self._activation_by_type[name] = bool(activated)
                if not activated:
                    self._retire_transition_page(name)
                changed = True
        self._apply_transition_pill_visibility()
        if changed and not getattr(self, "_loading", False):
            self._save_settings()

    def _on_use_random_toggled(self, checked: bool) -> None:
        if not getattr(self, "_loading", False):
            self._save_settings()

    def _on_pool_membership_toggled(self, name: str, checked: bool) -> None:
        self._pool_by_type[name] = bool(checked)
        if not getattr(self, "_loading", False):
            self._save_settings()

    def _load_settings(self) -> None:
        """Load settings from settings manager."""
        self._loading = True
        try:
            self._load_settings_impl()
        finally:
            self._loading = False
        # Reflect activation on the pills, then reconcile which page is shown
        # (load's _update_specific_settings may have re-shown a transition group).
        self._apply_transition_pill_visibility()
        self._on_nav_selected(self._current_nav_key())

    def _current_nav_key(self) -> str:
        for key, button in getattr(self, "_nav_buttons", {}).items():
            if button.isChecked():
                return key
        return _SETUP_NAV_KEY

    def _load_settings_impl(self) -> None:
        transitions_config = self._settings.get('transitions') or {}
        if not isinstance(transitions_config, dict):
            transitions_config = {}

        # E2.6: normalize legacy state to the single Random authority before the
        # UI reads it — most importantly convert a legacy type="Random" into
        # random_always=True + a concrete manual type, and repair any malformed
        # activation/empty-pool state. Persist when a repair actually happened.
        if normalize_transition_capability_state(transitions_config):
            self._settings.set('transitions', transitions_config)
            self._settings.save()

        canonical_transitions = _transition_defaults_root()

        # Canonical global default duration matches SettingsManager._set_defaults().
        default_duration_raw = transitions_config.get(
            'duration_ms',
            canonical_transitions['duration_ms'],
        )
        try:
            default_duration = int(default_duration_raw)
        except Exception as e:
            logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)
            default_duration = int(canonical_transitions['duration_ms'])

        durations_cfg = transitions_config.get('durations', canonical_transitions['durations'])
        if not isinstance(durations_cfg, dict):
            durations_cfg = dict(canonical_transitions['durations'])

        type_keys = list(_TRANSITION_SETTING_NAMES)
        self._duration_by_type = {}
        for name in type_keys:
            # Migrate any legacy "Rain Drops" duration to the new "Ripple"
            # label when no explicit Ripple entry exists.
            if name == "Ripple":
                raw = durations_cfg.get("Ripple", durations_cfg.get("Rain Drops", default_duration))
            else:
                raw = durations_cfg.get(name, default_duration)
            try:
                value = int(raw)
            except Exception as e:
                logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)
                value = default_duration
            self._duration_by_type[name] = value

        pool_cfg = transitions_config.get('pool', canonical_transitions['pool'])
        if not isinstance(pool_cfg, dict):
            pool_cfg = dict(canonical_transitions['pool'])
        self._pool_by_type = {}
        for name in type_keys:
            if name == "Ripple":
                raw_flag = pool_cfg.get(
                    "Ripple",
                    pool_cfg.get("Rain Drops", canonical_transitions["pool"]["Ripple"]),
                )
            else:
                raw_flag = pool_cfg.get(name, canonical_transitions["pool"][name])
            try:
                enabled = SettingsManager.to_bool(
                    raw_flag, bool(canonical_transitions["pool"][name])
                )
            except Exception as e:
                logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)
                enabled = bool(canonical_transitions["pool"][name])
            self._pool_by_type[name] = bool(enabled)

        # Application-level activation (E2). Missing => activated (True).
        self._activation_by_type = {
            name: is_transition_activated(transitions_config, name)
            for name in type_keys
        }
        use_random = SettingsManager.to_bool(
            transitions_config.get('random_always', canonical_transitions['random_always']),
            bool(canonical_transitions['random_always'])
        )

        # Block signals while we apply settings to avoid recursive saves with stale state
        blockers = []
        for w in [
            getattr(self, 'transition_combo', None),
            getattr(self, 'duration_slider', None),
            getattr(self, 'direction_combo', None),
            getattr(self, 'blinds_feather_slider', None),
            *self._page_widgets(),
            *self._particle_widgets(),
            *self._burn_widgets(),
        ]:
            if w is not None and hasattr(w, 'blockSignals'):
                w.blockSignals(True)
                blockers.append(w)

        # Also block the SETUP page controls while applying their state.
        for w in (
            list(getattr(self, '_activation_checkboxes', {}).values())
            + list(getattr(self, '_pool_checkboxes', {}).values())
            + [getattr(self, '_use_random_checkbox', None)]
        ):
            if w is not None and hasattr(w, 'blockSignals'):
                w.blockSignals(True)
                blockers.append(w)

        try:
            # Load transition type (default to Wipe to match SettingsManager defaults)
            transition_type = canonicalize_transition_name(
                transitions_config.get('type', canonical_transitions['type']),
                fallback=str(canonical_transitions['type']),
            )
            index = self.transition_combo.findText(transition_type)
            if index >= 0:
                self.transition_combo.setCurrentIndex(index)
            # Authoritative manual/edited selection mirrors the persisted type.
            self._current_transition = transition_type

            duration = self._duration_by_type.get(transition_type, default_duration)
            self.duration_slider.setValue(duration)
            self.duration_value_label.setText(f"{duration} ms")

            # Apply SETUP page state: activation, Use Random, and pool membership.
            for name, checkbox in getattr(self, '_activation_checkboxes', {}).items():
                checkbox.setChecked(
                    bool(
                        self._activation_by_type.get(
                            name, bool(canonical_transitions['activation'][name])
                        )
                    )
                )
            for name, checkbox in getattr(self, '_pool_checkboxes', {}).items():
                checkbox.setChecked(
                    bool(
                        self._pool_by_type.get(
                            name, bool(canonical_transitions['pool'][name])
                        )
                    )
                )
            if getattr(self, '_use_random_checkbox', None) is not None:
                self._use_random_checkbox.setChecked(bool(use_random))

            # Load per-transition directions (nested)
            for section in self._direction_by_type:
                canonical_section = canonical_transitions[section]
                persisted_section = transitions_config.get(section, {})
                if not isinstance(persisted_section, dict):
                    persisted_section = {}
                self._direction_by_type[section] = str(
                    persisted_section.get("direction", canonical_section["direction"])
                    or canonical_section["direction"]
                )

            # Note: GPU acceleration is controlled globally in Display tab

            # Remember the loaded config so a lazily-built transition page can be
            # hydrated later from the same persisted state.
            self._loaded_transitions_config = transitions_config
            self._loaded_canonical_transitions = canonical_transitions

            # Hydrate only the transition-specific groups that are already built
            # (none at first load; the current pill's page is built afterward).
            self._hydrate_built_transition_groups(transitions_config, canonical_transitions)

            # Now that in-memory per-type directions are loaded, update the direction combo
            self._update_specific_settings()

            logger.debug("Loaded transition settings")
        finally:
            for w in blockers:
                try:
                    w.blockSignals(False)
                except Exception as e:
                    logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)
    
    def _on_transition_changed(self, transition: str) -> None:
        """Handle transition type change."""
        # If a GL-only transition was selected while HW is off, revert to Crossfade
        self._enforce_gl_only_selection()
        self._update_specific_settings()
        cur_type = self.transition_combo.currentText()
        try:
            value = self._duration_by_type.get(cur_type, self.duration_slider.value())
        except Exception as e:
            logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)
            value = self.duration_slider.value()
        try:
            self.duration_slider.blockSignals(True)
            self.duration_slider.setValue(value)
            self.duration_value_label.setText(f"{value} ms")
        finally:
            self.duration_slider.blockSignals(False)

        self._save_settings()
    
    def _update_specific_settings(self) -> None:
        """Update visibility of transition-specific settings.

        Uses the authoritative ``_current_transition`` (not the hidden mirror
        combo) and only touches specific groups that have been lazily built.
        """
        transition = self._current_transition or self.transition_combo.currentText()

        # The shared Direction box shows for transitions whose spec offers directions.
        spec = transition_settings(transition)
        directions = spec.directions if spec is not None else None
        self.direction_group.setVisible(directions is not None)
        if directions is not None:
            self.direction_combo.blockSignals(True)
            try:
                self.direction_combo.clear()
                self.direction_combo.addItems(list(directions.choices))
                # A retired or unknown stored direction shows as Random.
                idx = self.direction_combo.findText(self._direction_by_type[spec.section])
                if idx < 0:
                    idx = self.direction_combo.findText("Random")
                self.direction_combo.setCurrentIndex(max(0, idx))
            finally:
                self.direction_combo.blockSignals(False)

        # Show only the built specific group matching the current transition.
        # Unbuilt groups (lazy) simply have nothing to show.
        for page in iter_transition_settings():
            group = getattr(self, f"{page.section}_group", None)
            if group is not None:
                group.setVisible(transition == page.name)
        if transition == "Particle" and hasattr(self, "particle_group"):
            self._update_particle_mode_visibility()

    def _on_particle_mode_changed(self, index: int) -> None:
        """Handle particle mode change - show/hide direction vs swirl settings."""
        self._update_particle_mode_visibility()
    
    def _update_particle_mode_visibility(self) -> None:
        """Update visibility of particle mode-specific settings."""
        mode = self.particle_mode_combo.currentText()
        is_random = mode == "Random"
        is_directional = mode == "Directional"
        is_swirl = mode == "Swirl"
        is_converge = mode == "Converge"
        # Direction only applies to Directional/Converge modes (disabled for Random - auto-selected)
        self.particle_direction_combo.setEnabled((is_directional or is_converge) and not is_random)
        # Swirl settings only apply to Swirl mode (disabled for Random - auto-selected)
        self.particle_swirl_turns_spin.setEnabled(is_swirl and not is_random)
        self.particle_swirl_order_combo.setEnabled(is_swirl and not is_random)

    def _apply_burn_glow_color_btn(self) -> None:
        """Update the burn glow colour button background to reflect the current colour."""
        c = self._burn_glow_color
        try:
            self.burn_glow_color_btn.set_color(c)
        except Exception:
            pass

    def _pick_burn_glow_color(self) -> None:
        """Open colour picker for the burn glow colour."""
        color = StyledColorPicker.get_color(
            self._burn_glow_color,
            self,
            "Burn Glow Colour",
            show_alpha=True,
        )
        if color is not None:
            self._burn_glow_color = color
            self._apply_burn_glow_color_btn()
            self._save_settings()

    def _apply_burn_ember_color_btn(self) -> None:
        """Reflect the independently authored burn ember/char colour."""
        c = self._burn_ember_color
        try:
            self.burn_ember_color_btn.set_color(c)
        except Exception:
            pass

    def _pick_burn_ember_color(self) -> None:
        """Open colour picker for the burn ember/char colour."""
        color = StyledColorPicker.get_color(
            self._burn_ember_color,
            self,
            "Burn Ember Colour",
            show_alpha=True,
        )
        if color is not None:
            self._burn_ember_color = color
            self._apply_burn_ember_color_btn()
            self._save_settings()

    def _refresh_hw_dependent_options(self) -> None:
        """No-op — renderer is always GL, all transitions available."""
        pass

    def _enforce_gl_only_selection(self) -> None:
        """No-op — renderer is always GL, all transitions available."""
        pass
    
    def _save_settings(self) -> None:
        """Persist transition settings, normalizing capability state first.

        Lazy-safe: unbuilt transition pages keep their existing persisted detail
        subdicts (never reconstructed from controls that were never built). Every
        mutation passes through ``normalize_transition_capability_state`` before
        persistence, and any repair is reflected back into the live UI (§2).
        """
        if getattr(self, "_loading", False):
            return

        existing = self._settings.get('transitions')
        existing = existing if isinstance(existing, dict) else {}

        def _existing_subdict(key: str) -> dict:
            value = existing.get(key, {})
            return dict(value) if isinstance(value, dict) else {}

        default_type = str(_transition_default("type"))
        cur_type = self._current_transition or canonicalize_transition_name(
            existing.get('type', default_type), fallback=default_type
        )
        spec = transition_settings(cur_type)
        if spec is not None and spec.directions is not None:
            self._direction_by_type[spec.section] = self.direction_combo.currentText()

        cur_duration = self.duration_slider.value()
        self._duration_by_type[cur_type] = cur_duration

        for name, checkbox in getattr(self, "_activation_checkboxes", {}).items():
            self._activation_by_type[name] = bool(checkbox.isChecked())
        try:
            use_random = bool(self._use_random_checkbox.isChecked())
        except Exception as e:
            logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)
            use_random = bool(_transition_default('random_always'))

        config = {
            'type': cur_type,
            'duration_ms': cur_duration,
            'durations': dict(self._duration_by_type),
            'pool': dict(self._pool_by_type),
            'activation': dict(self._activation_by_type),
            'random_always': use_random,
        }
        # A built page writes its section fresh (dropping retired/stale keys); an
        # unbuilt page keeps its persisted section. The shared Direction box's
        # selection is written either way.
        for page in iter_transition_settings():
            if page.has_page and hasattr(self, f"{page.section}_group"):
                values = {control.field: self._control_value(page, control) for control in page.all_controls}
                if page.custom:
                    getattr(self, f"_save_{page.section}_page")(values)
            else:
                values = _existing_subdict(page.section)
            if page.directions is not None:
                values['direction'] = self._direction_by_type[page.section]
            config[page.section] = values

        # Preserve engine-managed transient random-choice bookkeeping.
        for transient_key in ('random_choice', 'last_random_choice'):
            if transient_key in existing:
                config[transient_key] = existing[transient_key]

        # Canonical normalization at the mutation boundary (§2): repair
        # zero-activated / empty-effective-pool / deactivated-manual / legacy
        # type="Random" before persistence, then reflect the repair live.
        normalize_transition_capability_state(config)

        self._writing_settings = True
        try:
            self._settings.set('transitions', config)
            self._settings.save()
        finally:
            self._writing_settings = False
        self.transitions_changed.emit()

        self._reflect_capability_state(config)
        logger.debug(f"Saved transition settings: {config['type']}")

    def _reflect_capability_state(self, config: dict) -> None:
        """Reflect a (possibly normalized) capability state back into the UI."""
        canonical_activation = _transition_default("activation")
        if not isinstance(canonical_activation, dict):
            raise TypeError("Canonical transitions.activation default must be a mapping")
        activation = config.get('activation', canonical_activation)
        if isinstance(activation, dict):
            for name, checkbox in getattr(self, "_activation_checkboxes", {}).items():
                desired = bool(activation.get(name, canonical_activation[name]))
                if checkbox.isChecked() != desired:
                    checkbox.blockSignals(True)
                    checkbox.setChecked(desired)
                    checkbox.blockSignals(False)
                self._activation_by_type[name] = desired
        use_random = bool(config.get('random_always', _transition_default('random_always')))
        cb = getattr(self, "_use_random_checkbox", None)
        if cb is not None and cb.isChecked() != use_random:
            cb.blockSignals(True)
            cb.setChecked(use_random)
            cb.blockSignals(False)
        # Keep the mirror + authoritative manual selection aligned with any
        # normalized concrete type.
        default_type = str(_transition_default('type'))
        new_type = canonicalize_transition_name(
            config.get('type', default_type), fallback=default_type
        )
        if new_type and new_type != "Random":
            self._current_transition = new_type
            if self.transition_combo.currentText() != new_type:
                self.transition_combo.blockSignals(True)
                self.transition_combo.setCurrentText(new_type)
                self.transition_combo.blockSignals(False)
        self._apply_transition_pill_visibility()

    def _on_duration_changed(self, value: int) -> None:
        """Update duration presentation/state live; persistence commits on release."""
        self.duration_value_label.setText(f"{value} ms")
        cur_type = self._current_transition or self.transition_combo.currentText()
        if cur_type:
            self._duration_by_type[cur_type] = value
