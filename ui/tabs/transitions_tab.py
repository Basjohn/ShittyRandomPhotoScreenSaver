"""
Transitions configuration tab for settings dialog.

Allows users to configure transition settings:
- Transition type selection
- Duration
- Direction (for directional transitions)
- Easing curves
"""
from collections.abc import Mapping
import math
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
from rendering.gl_programs.blinds_options import BLINDS_SLATS_RANGE, BLINDS_STYLE_CHOICES
from rendering.gl_programs.blockspin_options import BLOCK_SPIN_EDGE_GLASS_CHOICES
from rendering.gl_programs.cube_turn_options import CUBE_TURN_DIRECTION_CHOICES
from rendering.gl_programs.jigsaw_options import JIGSAW_ORDER_CHOICES, JIGSAW_PIECES_RANGE
from rendering.gl_programs.page_curl_options import PAGE_CURL_ORIGIN_CHOICES
from rendering.gl_programs.edge_bloom_options import EDGE_BLOOM_COLOUR_SOURCE_CHOICES
from rendering.gl_programs.vhs_options import VHS_DIRECTION_CHOICES
from rendering.gl_programs.chromatic_shear_program import SHEAR_SLICES_RANGE
from rendering.gl_programs.chromatic_shear_options import SHEAR_DIRECTION_CHOICES
from rendering.gl_programs.surface_tension_program import TENSION_POOLS_RANGE
from rendering.gl_programs.membrane_options import MEMBRANE_SWEEP_CHOICES
from rendering.gl_programs.liquid_lens_options import LIQUID_LENS_ORIGIN_CHOICES
from rendering.gl_programs.volumetric_dissolve_options import (
    VOLUMETRIC_DIRECTION_CHOICES,
    VOLUMETRIC_PARTICLE_SIZE_RANGE,
)
from rendering.gl_programs.scene3d import (
    SCENE3D_ANTIALIASING_CHOICES,
    SCENE3D_EFFECT_CHOICES,
    SCENE3D_TRAIL_CHOICES,
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
        # Maintain per-transition direction selections in-memory from the one
        # canonical defaults authority until persisted state is hydrated.
        self._dir_slide: str = str(_transition_default("slide.direction"))
        self._dir_wipe: str = str(_transition_default("wipe.direction"))
        self._dir_blockspin: str = str(_transition_default("blockspin.direction"))
        self._direction_by_type = {
            name: str(_transition_default(f"{name}.direction"))
            for name in (
                "glass_shatter",
                "exploding_tiles",
                "pixel_accretion",
                "melt_drip",
                "page_curl",
                "disintegrate",
                "cube_turn",
                "beam",
                "jigsaw",
                "volumetric_dissolve",
                "vhs",
                "liquid_lens",
                "membrane",
                "chromatic_shear",
            )
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

        self._dir_slide = str(_section("slide").get("direction", canonical["slide"]["direction"]))
        self._dir_wipe = str(_section("wipe").get("direction", canonical["wipe"]["direction"]))
        self._dir_blockspin = str(
            _section("blockspin").get("direction", canonical["blockspin"]["direction"])
        )
        for name in self._direction_by_type:
            section = _section(name)
            self._direction_by_type[name] = str(
                section.get("direction", canonical[name]["direction"])
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
    # selected again. Crossfade and Warp Dissolve have no specific page; Wipe
    # uses only the shared Direction group, while Slide has a lazy motion page.

    _TRANSITION_PAGE_BUILDERS = {
        "Slide": "_build_slide_group",
        "3D Block Spins": "_build_blockspin_group",
        "Blinds": "_build_blinds_group",
        "Ripple": "_build_ripple_group",
        "Crumble": "_build_crumble_group",
        "Particle": "_build_particle_group",
        "Burn": "_build_burn_group",
        "Glass Shatter": "_build_glass_shatter_group",
        "Exploding Tiles": "_build_exploding_tiles_group",
        "Directional Pixel Accretion": "_build_pixel_accretion_group",
        "Melt Drip": "_build_melt_drip_group",
        "Page Curl": "_build_page_curl_group",
        "Disintegrate": "_build_disintegrate_group",
        "Cube Turn": "_build_cube_turn_group",
        "Beam": "_build_beam_group",
        "Jigsaw Piece Flip": "_build_jigsaw_group",
        "Volumetric Dissolve": "_build_volumetric_dissolve_group",
        "VHS Distortion": "_build_vhs_group",
        "Chromatic Shear": "_build_chromatic_shear_group",
        "Surface Tension Merge": "_build_surface_tension_group",
        "Membrane Turnover": "_build_membrane_group",
        "Liquid Lens": "_build_liquid_lens_group",
        "Edge Bloom Reveal": "_build_edge_bloom_group",
    }

    _SPECIFIC_GROUP_ATTRS = {
        "Slide": "slide_group",
        "3D Block Spins": "blockspin_group",
        "Blinds": "blinds_group",
        "Ripple": "ripple_group",
        "Crumble": "crumble_group",
        "Particle": "particle_group",
        "Burn": "burn_group",
        "Glass Shatter": "glass_shatter_group",
        "Exploding Tiles": "exploding_tiles_group",
        "Directional Pixel Accretion": "pixel_accretion_group",
        "Melt Drip": "melt_drip_group",
        "Page Curl": "page_curl_group",
        "Disintegrate": "disintegrate_group",
        "Cube Turn": "cube_turn_group",
        "Beam": "beam_group",
        "Jigsaw Piece Flip": "jigsaw_group",
        "Volumetric Dissolve": "volumetric_dissolve_group",
        "VHS Distortion": "vhs_group",
        "Chromatic Shear": "chromatic_shear_group",
        "Surface Tension Merge": "surface_tension_group",
        "Membrane Turnover": "membrane_group",
        "Liquid Lens": "liquid_lens_group",
        "Edge Bloom Reveal": "edge_bloom_group",
    }

    _DIRECTIONAL_TRANSITIONS = frozenset(
        {
            "Slide",
            "Wipe",
            "Glass Shatter",
            "Exploding Tiles",
            "Directional Pixel Accretion",
            "Melt Drip",
            "Page Curl",
            "Disintegrate",
            "Cube Turn",
            "Beam",
            "Jigsaw Piece Flip",
            "Volumetric Dissolve",
            "VHS Distortion",
            "Liquid Lens",
            "Membrane Turnover",
            "Chromatic Shear",
        }
    )

    def _ensure_transition_page(self, name: str) -> None:
        """Lazily build one transition's specific settings group + hydrate it."""
        builder_name = self._TRANSITION_PAGE_BUILDERS.get(name)
        if builder_name is None:
            return
        # A deactivated transition page is never built/hydrated.
        if not self._transition_activated(name):
            return
        group_attr = self._SPECIFIC_GROUP_ATTRS.get(name)
        if group_attr and hasattr(self, group_attr):
            return  # already built
        attrs_before_build = set(vars(self))
        try:
            getattr(self, builder_name)()
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
        group_attr = self._SPECIFIC_GROUP_ATTRS.get(name)
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

    @staticmethod
    def _new_transition_number(
        section: Mapping[str, object],
        field_name: str,
        section_name: str,
        canonical_value: object,
        widget: object,
        converter,
    ):
        raw = section.get(field_name, canonical_value)
        try:
            value = converter(raw)
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError
        except (TypeError, ValueError, OverflowError):
            logger.warning(
                "[TRANSITIONS_TAB] Repaired malformed transition field %s.%s",
                section_name,
                field_name,
            )
            value = converter(canonical_value)

        # The controls own the same ranges used by request admission.  Clamp
        # through those ranges so hydration adds no second numeric contract.
        lower = widget.minimum()
        upper = widget.maximum()
        clamped = max(lower, min(upper, value))
        if clamped != value:
            logger.warning(
                "[TRANSITIONS_TAB] Repaired out-of-range transition field %s",
                f"{section_name}.{field_name}",
            )
        return clamped

    def _hydrate_built_transition_groups(self, transitions_config: dict, canonical_transitions: dict) -> None:
        """Hydrate only the transition-specific groups that are currently built.

        Called at load (before any specific group exists -> no-op for specifics)
        and again whenever a transition page is lazily built. Guarded per group so
        an unbuilt page never touches non-existent controls. Callers set
        ``self._loading`` so control signals do not trigger saves during hydration.
        """
        if hasattr(self, 'slide_group'):
            canonical_slide = canonical_transitions['slide']
            slide = transitions_config.get('slide', canonical_slide)
            style = slide.get('motion_style', canonical_slide['motion_style'])
            index = self.slide_motion_style_combo.findText(str(style))
            self.slide_motion_style_combo.setCurrentIndex(max(0, index))

        if hasattr(self, 'glass_shatter_group'):
            canonical = canonical_transitions['glass_shatter']
            cfg = self._new_transition_section(transitions_config, 'glass_shatter', canonical)
            self.glass_shards_spin.setValue(self._new_transition_number(
                cfg, 'shards', 'glass_shatter', canonical['shards'], self.glass_shards_spin, int,
            ))
            self.glass_depth_spin.setValue(self._new_transition_number(
                cfg, 'depth', 'glass_shatter', canonical['depth'], self.glass_depth_spin, float,
            ))
            for field, check in (("collisions", self.glass_collisions_check),
                                 ("reshatter", self.glass_reshatter_check)):
                check.setChecked(bool(SettingsManager.to_bool(
                    cfg.get(field, canonical[field]), bool(canonical[field]))))

        if hasattr(self, 'exploding_tiles_group'):
            canonical = canonical_transitions['exploding_tiles']
            cfg = self._new_transition_section(transitions_config, 'exploding_tiles', canonical)
            self.exploding_tiles_columns_spin.setValue(self._new_transition_number(
                cfg, 'columns', 'exploding_tiles', canonical['columns'], self.exploding_tiles_columns_spin, int,
            ))
            self.exploding_tiles_depth_spin.setValue(self._new_transition_number(
                cfg, 'depth', 'exploding_tiles', canonical['depth'], self.exploding_tiles_depth_spin, float,
            ))

        if hasattr(self, 'pixel_accretion_group'):
            canonical = canonical_transitions['pixel_accretion']
            cfg = self._new_transition_section(transitions_config, 'pixel_accretion', canonical)
            self.pixel_tile_size_spin.setValue(self._new_transition_number(
                cfg, 'tile_size', 'pixel_accretion', canonical['tile_size'], self.pixel_tile_size_spin, int,
            ))
            self.pixel_travel_spin.setValue(self._new_transition_number(
                cfg, 'travel', 'pixel_accretion', canonical['travel'], self.pixel_travel_spin, float,
            ))

        if hasattr(self, 'melt_drip_group'):
            canonical = canonical_transitions['melt_drip']
            cfg = self._new_transition_section(transitions_config, 'melt_drip', canonical)
            self.melt_drip_detail_spin.setValue(self._new_transition_number(
                cfg, 'detail', 'melt_drip', canonical['detail'], self.melt_drip_detail_spin, float,
            ))

        if hasattr(self, 'beam_group'):
            canonical = canonical_transitions['beam']
            cfg = self._new_transition_section(transitions_config, 'beam', canonical)
            color = cfg.get('color', canonical['color'])
            if not (isinstance(color, (list, tuple)) and len(color) >= 3
                    and all(isinstance(c, (int, float)) for c in color[:3])):
                color = canonical['color']
            self._beam_color = QColor(*(max(0, min(255, int(c))) for c in color[:3]))
            self.beam_color_btn.set_color(self._beam_color)
            self.beam_sparks_check.setChecked(bool(cfg.get('sparks', canonical['sparks'])))
        if hasattr(self, 'liquid_lens_group'):
            canonical = canonical_transitions['liquid_lens']
            cfg = self._new_transition_section(transitions_config, 'liquid_lens', canonical)
            self.liquid_lens_droplets_check.setChecked(bool(cfg.get('droplets', canonical['droplets'])))
        if hasattr(self, 'surface_tension_group'):
            canonical = canonical_transitions['surface_tension']
            cfg = self._new_transition_section(transitions_config, 'surface_tension', canonical)
            self.surface_tension_pools_spin.setValue(self._new_transition_number(
                cfg, 'pools', 'surface_tension', canonical['pools'], self.surface_tension_pools_spin, int,
            ))
        if hasattr(self, 'chromatic_shear_group'):
            canonical = canonical_transitions['chromatic_shear']
            cfg = self._new_transition_section(transitions_config, 'chromatic_shear', canonical)
            self.chromatic_shear_slices_spin.setValue(self._new_transition_number(
                cfg, 'slices', 'chromatic_shear', canonical['slices'], self.chromatic_shear_slices_spin, int,
            ))
        if hasattr(self, 'edge_bloom_group'):
            canonical = canonical_transitions['edge_bloom']
            cfg = self._new_transition_section(transitions_config, 'edge_bloom', canonical)
            color = cfg.get('color', canonical['color'])
            if not (isinstance(color, (list, tuple)) and len(color) >= 3
                    and all(isinstance(c, (int, float)) for c in color[:3])):
                color = canonical['color']
            self._edge_bloom_color = QColor(*(max(0, min(255, int(c))) for c in color[:3]))
            self.edge_bloom_color_btn.set_color(self._edge_bloom_color)
            source = cfg.get('color_source', canonical['color_source'])
            self.edge_bloom_colour_source_combo.setCurrentText(
                str(source if source in EDGE_BLOOM_COLOUR_SOURCE_CHOICES else canonical['color_source']))
            self._sync_edge_bloom_colour_source()
        if hasattr(self, 'volumetric_dissolve_group'):
            canonical = canonical_transitions['volumetric_dissolve']
            cfg = self._new_transition_section(transitions_config, 'volumetric_dissolve', canonical)
            self.volumetric_dissolve_size_spin.setValue(self._new_transition_number(
                cfg, 'particle_size', 'volumetric_dissolve', canonical['particle_size'],
                self.volumetric_dissolve_size_spin, int,
            ))
        if hasattr(self, 'jigsaw_group'):
            canonical = canonical_transitions['jigsaw']
            cfg = self._new_transition_section(transitions_config, 'jigsaw', canonical)
            self.jigsaw_pieces_spin.setValue(self._new_transition_number(
                cfg, 'pieces', 'jigsaw', canonical['pieces'], self.jigsaw_pieces_spin, int,
            ))
        if hasattr(self, 'disintegrate_group'):
            canonical = canonical_transitions['disintegrate']
            cfg = self._new_transition_section(transitions_config, 'disintegrate', canonical)
            self.disintegrate_grain_spin.setValue(self._new_transition_number(
                cfg, 'grain_size', 'disintegrate', canonical['grain_size'], self.disintegrate_grain_spin, int,
            ))

        for section, controls in self._SURFACE_CONTROLS.items():
            if hasattr(self, f"{section}_group"):
                canonical = canonical_transitions[section]
                cfg = self._new_transition_section(transitions_config, section, canonical)
                for field, *_ in controls:
                    spin = getattr(self, f"{section}_{field}_spin")
                    spin.setValue(self._new_transition_number(
                        cfg, field, section, canonical[field], spin, float,
                    ))

        for section, controls in self._SCENE3D_CHOICES.items():
            if hasattr(self, f"{section}_group"):
                canonical = canonical_transitions[section]
                cfg = transitions_config.get(section, canonical)
                cfg = cfg if isinstance(cfg, dict) else canonical
                for field, _label, choices, _tip in controls:
                    value = cfg.get(field, canonical[field])
                    getattr(self, f"{section}_{field}_combo").setCurrentText(
                        str(value if value in choices else canonical[field]))

        if hasattr(self, 'blockspin_group'):
            try:
                idx = self.blockspin_direction_combo.findText(self._dir_blockspin)
                if idx < 0:
                    idx = 0
                self.blockspin_direction_combo.setCurrentIndex(max(0, idx))
            except Exception as e:
                logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)

        if hasattr(self, 'blinds_group'):
            canonical_blinds = canonical_transitions['blinds']
            blinds = transitions_config.get('blinds', canonical_blinds)
            if not isinstance(blinds, dict):
                blinds = {}
            self.blinds_feather_slider.setValue(int(blinds.get('feather', canonical_blinds['feather'])))
            self.blinds_feather_label.setText(str(self.blinds_feather_slider.value()))
            style = blinds.get('style', canonical_blinds['style'])
            self.blinds_style_combo.setCurrentText(
                str(style if style in BLINDS_STYLE_CHOICES else canonical_blinds['style']))
            self._sync_blinds_style()
            self.blinds_slats_spin.setValue(self._new_transition_number(
                blinds, 'slats', 'blinds', canonical_blinds['slats'], self.blinds_slats_spin, int,
            ))
            blinds_dir = blinds.get('direction', canonical_blinds['direction'])
            try:
                idx = self.blinds_direction_combo.findText(str(blinds_dir))
                if idx < 0:
                    idx = 0
                self.blinds_direction_combo.setCurrentIndex(idx)
            except Exception as e:
                logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)

        if hasattr(self, 'ripple_group'):
            canonical_ripple = canonical_transitions['ripple']
            ripple = transitions_config.get('ripple', canonical_ripple)
            self.ripple_count_spin.setValue(int(ripple.get('ripple_count', canonical_ripple['ripple_count'])))

        if hasattr(self, 'crumble_group'):
            canonical_crumble = canonical_transitions['crumble']
            crumble = transitions_config.get('crumble', canonical_crumble)
            self.crumble_piece_count_spin.setValue(crumble.get('piece_count', canonical_crumble['piece_count']))
            self.crumble_complexity_spin.setValue(crumble.get('crack_complexity', canonical_crumble['crack_complexity']))
            weight = crumble.get('weighting', canonical_crumble['weighting'])
            # These former labels both executed Top Weighted; preserve the
            # behavior while retiring the misleading spelling on the next save.
            if weight in ("Bias Old Image", "Bias New Image"):
                weight = "Top Weighted"
            try:
                idx = self.crumble_weight_combo.findText(weight)
                if idx < 0:
                    idx = 0
                self.crumble_weight_combo.setCurrentIndex(idx)
            except Exception as e:
                logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)
            self.crumble_collisions_check.setChecked(bool(SettingsManager.to_bool(
                crumble.get('collisions', canonical_crumble['collisions']),
                bool(canonical_crumble['collisions']))))

        if hasattr(self, 'particle_group'):
            canonical_particle = canonical_transitions['particle']
            particle = transitions_config.get('particle', canonical_particle)
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

        if hasattr(self, 'burn_group'):
            canonical_burn = canonical_transitions['burn']
            burn = transitions_config.get('burn', canonical_burn)
            if not isinstance(burn, dict):
                burn = {}
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

    def _build_slide_group(self) -> None:
        self.slide_group = QGroupBox("Slide Motion")
        self._style_group_box(self.slide_group)
        slide_layout = QVBoxLayout(self.slide_group)
        slide_layout.setContentsMargins(0, 12, 0, 0)
        motion_row = self._aligned_row(slide_layout, "Motion Style:")
        self.slide_motion_style_combo = StyledComboBox(size_variant="compact")
        self.slide_motion_style_combo.addItems(
            ["Linear", "Elastic", "Wobble", "Flex", "Perspective Push"]
        )
        self.slide_motion_style_combo.currentTextChanged.connect(self._save_settings)
        motion_row.addWidget(self.slide_motion_style_combo)
        motion_row.addStretch()
        self._specific_group_host_layout.addWidget(self.slide_group)

    # Presentation only: ranges/labels live here; values always come from the
    # canonical defaults, never from this control description.
    _SURFACE_CONTROLS = {
        "crumble": (
            ("depth", "Collapse Depth:", .2, 1.5, "Out-of-plane movement and tumble of falling wall chunks."),
            ("thickness", "Wall Thickness:", 0., 1., "Thickness of the solid wall and its broken edges."),
            ("debris", "Crumbling Debris:", 0., 1., "Small solid fragments released around falling chunks. Zero disables debris geometry and drawing."),
        ),
        "glass_shatter": (
            ("thickness", "Glass Thickness:", 0., 1., "Thickness of the solid shards and their beveled edges. Zero makes a thin pane."),
            ("transparency", "Transparency:", 0., 1., "How much of the next image is visible through moving glass. Zero keeps opaque image faces."),
            ("refraction", "Refraction:", 0., 1., "Bending of the next image through the glass. Visible with transparency; zero disables distortion."),
            ("dispersion", "Color Dispersion:", 0., 1., "Prismatic color separation in refraction. Zero disables it."),
            ("sheen", "Reflections / Sheen:", 0., 1., "Reflections, rim glints and bevel highlights. Zero removes the optical highlights."),
        ),
        "exploding_tiles": (
            ("thickness", "Tile Thickness:", 0., 1., "Solid tile thickness relative to tile size, with beveled edges."),
            ("force", "Explosion Force:", .5, 2., "Strength of the outward launch and tumble. Tiles travel beyond the screen edge."),
            ("bloom_strength", "Bloom Strength:", 0., 1., "How strongly sparks, hot edges and glowing cracks glow "
             "when Bloom is on."),
        ),
        "blinds": (
            ("gloss", "Slat Gloss:", 0., 1., "Shine and reflections of the next image on the turning slats."),
        ),
        "page_curl": (
            ("size", "Curl Size:", 0., 1., "How large the peeled sheet's roll grows: thin and tight up to a "
             "loose, wide curl."),
            ("gloss", "Gloss:", 0., 1., "Shine of the laminated sheet and reflections of the next image on it."),
        ),
        "cube_turn": (
            ("gloss", "Gloss:", 0., 1., "Shine and reflections of the next image on the turning box."),
        ),
        "beam": (
            ("glow", "Glow:", 0., 1., "How far the beam's light reaches and how strongly it lights the picture."),
            ("scorch", "Scorch:", 0., 1., "How strongly the beam scorches the new picture before it cures clean."),
            ("cure", "Cure Time:", 0., 1., "How long the scorch takes to cure clean. A longer cure has the beam "
             "cross sooner, so the run still ends on the clean picture."),
        ),
        "disintegrate": (
            ("wind", "Wind:", .5, 2., "How hard the wind blows the grains away: their speed and how far they fly."),
        ),
        "volumetric_dissolve": (
            ("mist", "Mist:", 0., 1., "How much luminous mist, coloured by the old picture, rises as it dissolves."),
            ("depth", "Depth:", 0., 1., "How far the particles fly toward you, growing and blurring as they near."),
        ),
        "edge_bloom": (
            ("glow", "Glow:", 0., 1., "How brightly the edges and the growing fill glow."),
            ("detail", "Detail:", 0., 1., "How many edges light up: only the strongest outlines at 0, fine "
             "detail at 1."),
        ),
        "liquid_lens": (
            ("refraction", "Refraction:", 0.0, 1.0, "How strongly the water bends the next picture: thin and clear at 0, a thick, magnifying lens at 1."),
            ("dispersion", "Colour Fringes:", 0.0, 1.0, "Rainbow fringes where the water's rim bends the light most. Zero keeps the colours together."),
        ),
        "membrane": (
            ("gloss", "Gloss:", 0.0, 1.0, "Shine of the membrane and reflections of the next picture on it as it twists."),
        ),
        "surface_tension": (
            ("gloss", "Gloss:", 0.0, 1.0, "Light on the liquid where the two pictures meet: highlights and sheen along every edge."),
        ),
        "chromatic_shear": (
            ("spread", "Spread:", 0.0, 1.0, "How far the slices shear apart and the colours fan out."),
        ),
        "vhs": (
            ("tracking", "Tracking:", 0., 1., "How badly tracking is lost: jittering, swaying and tearing lines, "
             "and the bent top of each frame as the picture rolls."),
            ("bleed", "Colour Bleed:", 0., 1., "How far colour smears and lags behind the picture, with ringing "
             "edges, as on worn tape."),
            ("noise", "Noise:", 0., 1., "Snow, dropout streaks, scanlines and a drifting interference band."),
        ),
        "melt_drip": (
            ("depth", "Liquid Depth:", 0., 1., "Thickness and relief of the liquid sheet and falling drops."),
            ("gloss", "Wet Gloss:", 0., 1., "Reflections on the rounded liquid surfaces."),
        ),
    }

    # Each 3D transition's own choices. For quality, "Auto" follows the 3D Transitions tier on
    # the 3D tab; anything else is authoritative for that transition (one resolver combines them).
    _AUTO_TIP = " Auto follows 3D Transitions on the 3D tab."
    _ANTIALIASING_CONTROL = ("antialiasing", "Anti-aliasing:", SCENE3D_ANTIALIASING_CHOICES,
                             "Multisampling that smooths the 3D edges; 4x and 8x cost the most GPU time." + _AUTO_TIP)
    _MOTION_BLUR_CONTROL = ("motion_blur", "Motion Blur:", SCENE3D_EFFECT_CHOICES,
                            "Blurs fast pieces along their motion, as a camera would; still parts stay sharp."
                            + _AUTO_TIP)
    _MOTION_TRAILS_CONTROL = ("motion_trails", "Motion Trails:", SCENE3D_TRAIL_CHOICES,
                              "Faint, fading outlines of where fast pieces just were.")
    _SCENE3D_CHOICES = {
        "exploding_tiles": (
            _ANTIALIASING_CONTROL,
            ("bloom", "Bloom:", SCENE3D_EFFECT_CHOICES,
             "Glow around sparks, hot edges and glowing cracks; the photographs never glow." + _AUTO_TIP),
            _MOTION_BLUR_CONTROL,
            _MOTION_TRAILS_CONTROL,
        ),
        "glass_shatter": (_ANTIALIASING_CONTROL, _MOTION_BLUR_CONTROL, _MOTION_TRAILS_CONTROL),
        "crumble": (_ANTIALIASING_CONTROL, _MOTION_BLUR_CONTROL, _MOTION_TRAILS_CONTROL),
        "pixel_accretion": (_ANTIALIASING_CONTROL, _MOTION_BLUR_CONTROL, _MOTION_TRAILS_CONTROL),
        "blinds": (_ANTIALIASING_CONTROL,),
        "page_curl": (_ANTIALIASING_CONTROL,),
        "disintegrate": (_ANTIALIASING_CONTROL,),
        "cube_turn": (_ANTIALIASING_CONTROL,),
        "jigsaw": (_ANTIALIASING_CONTROL,),
        "volumetric_dissolve": (_ANTIALIASING_CONTROL,),
        "membrane": (_ANTIALIASING_CONTROL,),
        "blockspin": (
            ("edge_glass", "Edge Glass:", BLOCK_SPIN_EDGE_GLASS_CHOICES,
             "Polished glass edges on the spinning slab, showing the next image: Reflection, Refraction or Both. "
             "The sheen and gloss stay."),
            _ANTIALIASING_CONTROL,
            _MOTION_BLUR_CONTROL,
            _MOTION_TRAILS_CONTROL,
        ),
    }

    # Operator direction (2026-09-29): a page's optional quality and look choices, which will
    # grow, live in one closed "Advanced" bucket; the controls that shape the effect itself
    # stay on the page. A surface value that belongs to a choice sits right under it.
    _ADVANCED_SURFACE_FIELDS = {"exploding_tiles": {"bloom": ("bloom_strength",)}}

    def _build_scene3d_choices(self, layout, section: str) -> None:
        toggle, body, advanced = shared_styles.build_bucket_toggle(layout, "Advanced", expanded=False)
        toggle.setToolTip("Quality and optional effects for this transition.")
        setattr(self, f"{section}_advanced_toggle", toggle)
        setattr(self, f"{section}_advanced_body", body)
        attached = self._ADVANCED_SURFACE_FIELDS.get(section, {})
        surface = {control[0]: control for control in self._SURFACE_CONTROLS.get(section, ())}
        for field, label, choices, tooltip in self._SCENE3D_CHOICES[section]:
            row = self._aligned_row(advanced, label)
            combo = StyledComboBox(size_variant="compact")
            combo.addItems(list(choices))
            combo.setCurrentText(str(_transition_default(f"{section}.{field}")))
            combo.setToolTip(tooltip)
            combo.currentTextChanged.connect(self._save_settings)
            row.addWidget(combo)
            row.addStretch()
            setattr(self, f"{section}_{field}_combo", combo)
            for extra in attached.get(field, ()):
                self._build_surface_control(advanced, section, *surface[extra])

    def _build_surface_controls(self, layout, section: str) -> None:
        advanced = {field for fields in self._ADVANCED_SURFACE_FIELDS.get(section, {}).values() for field in fields}
        for control in self._SURFACE_CONTROLS[section]:
            if control[0] not in advanced:
                self._build_surface_control(layout, section, *control)

    def _build_surface_control(self, layout, section: str, field: str, label: str, low: float, high: float,
                               tooltip: str) -> None:
        row = self._aligned_row(layout, label)
        spin = QDoubleSpinBox()
        spin.setDecimals(2)
        spin.setRange(low, high)
        spin.setSingleStep(.05)
        spin.setValue(float(_transition_default(f"{section}.{field}")))
        spin.setToolTip(tooltip)
        spin.valueChanged.connect(self._save_settings)
        row.addWidget(spin)
        row.addStretch()
        setattr(self, f"{section}_{field}_spin", spin)

    def _build_glass_shatter_group(self) -> None:
        self.glass_shatter_group = QGroupBox("Glass Shatter Settings")
        self._style_group_box(self.glass_shatter_group)
        layout = QVBoxLayout(self.glass_shatter_group)
        layout.setContentsMargins(0, 12, 0, 0)
        shards_row = self._aligned_row(layout, "Shard Count:")
        self.glass_shards_spin = QSpinBox()
        self.glass_shards_spin.setRange(24, 180)
        self.glass_shards_spin.setValue(int(_transition_default("glass_shatter.shards")))
        self.glass_shards_spin.valueChanged.connect(self._save_settings)
        shards_row.addWidget(self.glass_shards_spin)
        shards_row.addStretch()
        depth_row = self._aligned_row(layout, "Depth:")
        self.glass_depth_spin = QDoubleSpinBox()
        self.glass_depth_spin.setDecimals(2)
        self.glass_depth_spin.setRange(0.2, 1.5)
        self.glass_depth_spin.setSingleStep(0.05)
        self.glass_depth_spin.setValue(float(_transition_default("glass_shatter.depth")))
        self.glass_depth_spin.valueChanged.connect(self._save_settings)
        depth_row.addWidget(self.glass_depth_spin)
        depth_row.addStretch()
        collide_row = self._aligned_row(layout, "", wrap=False)
        self.glass_collisions_check = QCheckBox("Shards Collide")
        self.glass_collisions_check.setProperty("circleIndicator", True)
        self.glass_collisions_check.setToolTip(
            "Shards that meet in flight bounce off each other and spin away."
        )
        self.glass_collisions_check.setChecked(bool(_transition_default("glass_shatter.collisions")))
        self.glass_collisions_check.stateChanged.connect(self._save_settings)
        collide_row.addWidget(self.glass_collisions_check)
        collide_row.addStretch()
        reshatter_row = self._aligned_row(layout, "", wrap=False)
        self.glass_reshatter_check = QCheckBox("Shards Break Again")
        self.glass_reshatter_check.setProperty("circleIndicator", True)
        self.glass_reshatter_check.setToolTip(
            "Shards crack into smaller pieces in flight: when they collide if "
            "Shards Collide is on, otherwise about 30% of shards crack at random."
        )
        self.glass_reshatter_check.setChecked(bool(_transition_default("glass_shatter.reshatter")))
        self.glass_reshatter_check.stateChanged.connect(self._save_settings)
        reshatter_row.addWidget(self.glass_reshatter_check)
        reshatter_row.addStretch()
        self._build_surface_controls(layout, "glass_shatter")
        self._build_scene3d_choices(layout, "glass_shatter")
        self._specific_group_host_layout.addWidget(self.glass_shatter_group)

    def _build_exploding_tiles_group(self) -> None:
        self.exploding_tiles_group = QGroupBox("Exploding Tiles Settings")
        self._style_group_box(self.exploding_tiles_group)
        layout = QVBoxLayout(self.exploding_tiles_group)
        layout.setContentsMargins(0, 12, 0, 0)
        columns_row = self._aligned_row(layout, "Tile Columns:")
        self.exploding_tiles_columns_spin = QSpinBox()
        self.exploding_tiles_columns_spin.setRange(6, 48)
        self.exploding_tiles_columns_spin.setValue(int(_transition_default("exploding_tiles.columns")))
        self.exploding_tiles_columns_spin.valueChanged.connect(self._save_settings)
        columns_row.addWidget(self.exploding_tiles_columns_spin)
        columns_row.addStretch()
        depth_row = self._aligned_row(layout, "Depth:")
        self.exploding_tiles_depth_spin = QDoubleSpinBox()
        self.exploding_tiles_depth_spin.setDecimals(2)
        self.exploding_tiles_depth_spin.setRange(0.2, 1.5)
        self.exploding_tiles_depth_spin.setSingleStep(0.05)
        self.exploding_tiles_depth_spin.setValue(float(_transition_default("exploding_tiles.depth")))
        self.exploding_tiles_depth_spin.valueChanged.connect(self._save_settings)
        depth_row.addWidget(self.exploding_tiles_depth_spin)
        depth_row.addStretch()
        self._build_surface_controls(layout, "exploding_tiles")
        self._build_scene3d_choices(layout, "exploding_tiles")
        self._specific_group_host_layout.addWidget(self.exploding_tiles_group)

    def _build_pixel_accretion_group(self) -> None:
        self.pixel_accretion_group = QGroupBox("Directional Pixel Accretion Settings")
        self._style_group_box(self.pixel_accretion_group)
        layout = QVBoxLayout(self.pixel_accretion_group)
        layout.setContentsMargins(0, 12, 0, 0)
        tile_row = self._aligned_row(layout, "Tile Size:")
        self.pixel_tile_size_spin = QSpinBox()
        self.pixel_tile_size_spin.setRange(4, 32)
        self.pixel_tile_size_spin.setValue(int(_transition_default("pixel_accretion.tile_size")))
        self.pixel_tile_size_spin.valueChanged.connect(self._save_settings)
        tile_row.addWidget(self.pixel_tile_size_spin)
        tile_row.addStretch()
        travel_row = self._aligned_row(layout, "Travel:")
        self.pixel_travel_spin = QDoubleSpinBox()
        self.pixel_travel_spin.setDecimals(2)
        self.pixel_travel_spin.setRange(0.1, 1.0)
        self.pixel_travel_spin.setSingleStep(0.05)
        self.pixel_travel_spin.setValue(float(_transition_default("pixel_accretion.travel")))
        self.pixel_travel_spin.valueChanged.connect(self._save_settings)
        travel_row.addWidget(self.pixel_travel_spin)
        travel_row.addStretch()
        self._build_scene3d_choices(layout, "pixel_accretion")
        self._specific_group_host_layout.addWidget(self.pixel_accretion_group)

    def _build_melt_drip_group(self) -> None:
        self.melt_drip_group = QGroupBox("Melt Drip Settings")
        self._style_group_box(self.melt_drip_group)
        layout = QVBoxLayout(self.melt_drip_group)
        layout.setContentsMargins(0, 12, 0, 0)
        detail_row = self._aligned_row(layout, "Detail:")
        self.melt_drip_detail_spin = QDoubleSpinBox()
        self.melt_drip_detail_spin.setDecimals(2)
        self.melt_drip_detail_spin.setRange(0.5, 2.0)
        self.melt_drip_detail_spin.setSingleStep(0.05)
        self.melt_drip_detail_spin.setValue(float(_transition_default("melt_drip.detail")))
        self.melt_drip_detail_spin.valueChanged.connect(self._save_settings)
        detail_row.addWidget(self.melt_drip_detail_spin)
        detail_row.addStretch()
        self._build_surface_controls(layout, "melt_drip")
        self._specific_group_host_layout.addWidget(self.melt_drip_group)

    def _build_beam_group(self) -> None:
        self.beam_group = QGroupBox("Beam Settings")
        self._style_group_box(self.beam_group)
        layout = QVBoxLayout(self.beam_group)
        layout.setContentsMargins(0, 12, 0, 0)
        color_row = self._swatch_row(layout, "Beam Colour:")
        self.beam_color_btn = ColorSwatchButton(title="Choose Beam Colour", show_alpha=False, auto_picker=False)
        self._beam_color = QColor(*_transition_default("beam.color"))
        self.beam_color_btn.set_color(self._beam_color)
        self.beam_color_btn.setFixedSize(60, 24)
        self.beam_color_btn.setToolTip("The colour of the beam and its glow; its core always burns white.")
        self.beam_color_btn.clicked.connect(self._pick_beam_color)
        color_row.addWidget(self.beam_color_btn)
        color_row.addStretch()
        self._build_surface_controls(layout, "beam")
        sparks_row = self._aligned_row(layout, "", wrap=False)
        self.beam_sparks_check = QCheckBox("Sparks")
        self.beam_sparks_check.setProperty("circleIndicator", True)
        self.beam_sparks_check.setChecked(bool(_transition_default("beam.sparks")))
        self.beam_sparks_check.setToolTip("Sparks spraying from where the beam cuts the picture.")
        self.beam_sparks_check.stateChanged.connect(self._save_settings)
        sparks_row.addWidget(self.beam_sparks_check)
        sparks_row.addStretch()
        self._specific_group_host_layout.addWidget(self.beam_group)

    def _pick_beam_color(self) -> None:
        color = StyledColorPicker.get_color(self._beam_color, self, "Beam Colour", show_alpha=False)
        if color is not None:
            self._beam_color = color
            self.beam_color_btn.set_color(color)
            self._save_settings()

    def _build_cube_turn_group(self) -> None:
        self.cube_turn_group = QGroupBox("Cube Turn Settings")
        self._style_group_box(self.cube_turn_group)
        layout = QVBoxLayout(self.cube_turn_group)
        layout.setContentsMargins(0, 12, 0, 0)
        self._build_surface_controls(layout, "cube_turn")
        self._build_scene3d_choices(layout, "cube_turn")
        self._specific_group_host_layout.addWidget(self.cube_turn_group)

    def _build_edge_bloom_group(self) -> None:
        self.edge_bloom_group = QGroupBox("Edge Bloom Reveal Settings")
        self._style_group_box(self.edge_bloom_group)
        layout = QVBoxLayout(self.edge_bloom_group)
        layout.setContentsMargins(0, 12, 0, 0)
        source_row = self._aligned_row(layout, "Glow Colour:")
        self.edge_bloom_colour_source_combo = StyledComboBox(size_variant="compact")
        self.edge_bloom_colour_source_combo.addItems(list(EDGE_BLOOM_COLOUR_SOURCE_CHOICES))
        self.edge_bloom_colour_source_combo.setCurrentText(str(_transition_default("edge_bloom.color_source")))
        self.edge_bloom_colour_source_combo.setToolTip(
            "Custom: the colour you choose. Next Picture: every line glows in the next picture's most vivid "
            "colour. Each Picture: each picture's lines glow in its own colour.")
        self.edge_bloom_colour_source_combo.currentTextChanged.connect(self._sync_edge_bloom_colour_source)
        self.edge_bloom_colour_source_combo.currentTextChanged.connect(self._save_settings)
        source_row.addWidget(self.edge_bloom_colour_source_combo)
        source_row.addStretch()
        color_row = self._swatch_row(layout, "Custom Colour:")
        self.edge_bloom_color_btn = ColorSwatchButton(title="Choose Glow Colour", show_alpha=False, auto_picker=False)
        self._edge_bloom_color = QColor(*_transition_default("edge_bloom.color")[:3])
        self.edge_bloom_color_btn.set_color(self._edge_bloom_color)
        self.edge_bloom_color_btn.setFixedSize(60, 24)
        self.edge_bloom_color_btn.setToolTip("The colour of the glowing edges; the strongest lines burn toward white.")
        self.edge_bloom_color_btn.clicked.connect(self._pick_edge_bloom_color)
        color_row.addWidget(self.edge_bloom_color_btn)
        self._build_surface_controls(layout, "edge_bloom")
        self._sync_edge_bloom_colour_source()
        self._specific_group_host_layout.addWidget(self.edge_bloom_group)

    def _sync_edge_bloom_colour_source(self, *_args) -> None:
        """The custom colour applies only to the Custom source."""
        self.edge_bloom_color_btn.setEnabled(self.edge_bloom_colour_source_combo.currentText() == "Custom")

    def _pick_edge_bloom_color(self) -> None:
        color = StyledColorPicker.get_color(self._edge_bloom_color, self, "Glow Colour", show_alpha=False)
        if color is not None:
            self._edge_bloom_color = color
            self.edge_bloom_color_btn.set_color(color)
            self._save_settings()

    def _build_liquid_lens_group(self) -> None:
        self.liquid_lens_group = QGroupBox("Liquid Lens Settings")
        self._style_group_box(self.liquid_lens_group)
        layout = QVBoxLayout(self.liquid_lens_group)
        layout.setContentsMargins(0, 12, 0, 0)
        self._build_surface_controls(layout, "liquid_lens")
        droplets_row = self._aligned_row(layout, "", wrap=False)
        self.liquid_lens_droplets_check = QCheckBox("Droplets")
        self.liquid_lens_droplets_check.setProperty("circleIndicator", True)
        self.liquid_lens_droplets_check.setChecked(bool(_transition_default("liquid_lens.droplets")))
        self.liquid_lens_droplets_check.setToolTip("Drops of water flung from the lens's leading edge.")
        self.liquid_lens_droplets_check.stateChanged.connect(self._save_settings)
        droplets_row.addWidget(self.liquid_lens_droplets_check)
        droplets_row.addStretch()
        self._specific_group_host_layout.addWidget(self.liquid_lens_group)

    def _build_membrane_group(self) -> None:
        self.membrane_group = QGroupBox("Membrane Turnover Settings")
        self._style_group_box(self.membrane_group)
        layout = QVBoxLayout(self.membrane_group)
        layout.setContentsMargins(0, 12, 0, 0)
        self._build_surface_controls(layout, "membrane")
        self._build_scene3d_choices(layout, "membrane")
        self._specific_group_host_layout.addWidget(self.membrane_group)

    def _build_surface_tension_group(self) -> None:
        self.surface_tension_group = QGroupBox("Surface Tension Merge Settings")
        self._style_group_box(self.surface_tension_group)
        layout = QVBoxLayout(self.surface_tension_group)
        layout.setContentsMargins(0, 12, 0, 0)
        pools_row = self._aligned_row(layout, "Pools:")
        self.surface_tension_pools_spin = QSpinBox()
        self.surface_tension_pools_spin.setRange(*TENSION_POOLS_RANGE)
        self.surface_tension_pools_spin.setValue(int(_transition_default("surface_tension.pools")))
        self.surface_tension_pools_spin.setToolTip("How many pools of the next picture appear: a few large ones up to many small ones.")
        self.surface_tension_pools_spin.valueChanged.connect(self._save_settings)
        pools_row.addWidget(self.surface_tension_pools_spin)
        pools_row.addStretch()
        self._build_surface_controls(layout, "surface_tension")
        self._specific_group_host_layout.addWidget(self.surface_tension_group)

    def _build_chromatic_shear_group(self) -> None:
        self.chromatic_shear_group = QGroupBox("Chromatic Shear Settings")
        self._style_group_box(self.chromatic_shear_group)
        layout = QVBoxLayout(self.chromatic_shear_group)
        layout.setContentsMargins(0, 12, 0, 0)
        slices_row = self._aligned_row(layout, "Slices:")
        self.chromatic_shear_slices_spin = QSpinBox()
        self.chromatic_shear_slices_spin.setRange(*SHEAR_SLICES_RANGE)
        self.chromatic_shear_slices_spin.setValue(int(_transition_default("chromatic_shear.slices")))
        self.chromatic_shear_slices_spin.setToolTip("How many broad slices the picture shears into.")
        self.chromatic_shear_slices_spin.valueChanged.connect(self._save_settings)
        slices_row.addWidget(self.chromatic_shear_slices_spin)
        slices_row.addStretch()
        self._build_surface_controls(layout, "chromatic_shear")
        self._specific_group_host_layout.addWidget(self.chromatic_shear_group)

    def _build_vhs_group(self) -> None:
        self.vhs_group = QGroupBox("VHS Distortion Settings")
        self._style_group_box(self.vhs_group)
        layout = QVBoxLayout(self.vhs_group)
        layout.setContentsMargins(0, 12, 0, 0)
        self._build_surface_controls(layout, "vhs")
        self._specific_group_host_layout.addWidget(self.vhs_group)

    def _build_volumetric_dissolve_group(self) -> None:
        self.volumetric_dissolve_group = QGroupBox("Volumetric Dissolve Settings")
        self._style_group_box(self.volumetric_dissolve_group)
        layout = QVBoxLayout(self.volumetric_dissolve_group)
        layout.setContentsMargins(0, 12, 0, 0)
        size_row = self._aligned_row(layout, "Particle Size:")
        self.volumetric_dissolve_size_spin = QSpinBox()
        self.volumetric_dissolve_size_spin.setRange(*VOLUMETRIC_PARTICLE_SIZE_RANGE)
        self.volumetric_dissolve_size_spin.setSuffix(" px")
        self.volumetric_dissolve_size_spin.setValue(int(_transition_default("volumetric_dissolve.particle_size")))
        self.volumetric_dissolve_size_spin.setToolTip(
            "Size of each particle in screen pixels. Very large screens use slightly bigger particles.")
        self.volumetric_dissolve_size_spin.valueChanged.connect(self._save_settings)
        size_row.addWidget(self.volumetric_dissolve_size_spin)
        size_row.addStretch()
        self._build_surface_controls(layout, "volumetric_dissolve")
        self._build_scene3d_choices(layout, "volumetric_dissolve")
        self._specific_group_host_layout.addWidget(self.volumetric_dissolve_group)

    def _build_jigsaw_group(self) -> None:
        self.jigsaw_group = QGroupBox("Jigsaw Piece Flip Settings")
        self._style_group_box(self.jigsaw_group)
        layout = QVBoxLayout(self.jigsaw_group)
        layout.setContentsMargins(0, 12, 0, 0)
        pieces_row = self._aligned_row(layout, "Pieces:")
        self.jigsaw_pieces_spin = QSpinBox()
        self.jigsaw_pieces_spin.setRange(*JIGSAW_PIECES_RANGE)
        self.jigsaw_pieces_spin.setValue(int(_transition_default("jigsaw.pieces")))
        self.jigsaw_pieces_spin.setToolTip(
            "About how many pieces the picture is cut into. More pieces flip faster, more at once.")
        self.jigsaw_pieces_spin.valueChanged.connect(self._save_settings)
        pieces_row.addWidget(self.jigsaw_pieces_spin)
        pieces_row.addStretch()
        self._build_scene3d_choices(layout, "jigsaw")
        self._specific_group_host_layout.addWidget(self.jigsaw_group)

    def _build_disintegrate_group(self) -> None:
        self.disintegrate_group = QGroupBox("Disintegrate Settings")
        self._style_group_box(self.disintegrate_group)
        layout = QVBoxLayout(self.disintegrate_group)
        layout.setContentsMargins(0, 12, 0, 0)
        grain_row = self._aligned_row(layout, "Grain Size:")
        self.disintegrate_grain_spin = QSpinBox()
        self.disintegrate_grain_spin.setRange(2, 8)
        self.disintegrate_grain_spin.setSuffix(" px")
        self.disintegrate_grain_spin.setValue(int(_transition_default("disintegrate.grain_size")))
        self.disintegrate_grain_spin.setToolTip(
            "Size of each grain in screen pixels. Very large screens use slightly bigger grains.")
        self.disintegrate_grain_spin.valueChanged.connect(self._save_settings)
        grain_row.addWidget(self.disintegrate_grain_spin)
        grain_row.addStretch()
        self._build_surface_controls(layout, "disintegrate")
        self._build_scene3d_choices(layout, "disintegrate")
        self._specific_group_host_layout.addWidget(self.disintegrate_group)

    def _build_page_curl_group(self) -> None:
        self.page_curl_group = QGroupBox("Page Curl Settings")
        self._style_group_box(self.page_curl_group)
        layout = QVBoxLayout(self.page_curl_group)
        layout.setContentsMargins(0, 12, 0, 0)
        self._build_surface_controls(layout, "page_curl")
        self._build_scene3d_choices(layout, "page_curl")
        self._specific_group_host_layout.addWidget(self.page_curl_group)

    def _build_blockspin_group(self) -> None:
        _aligned_row = self._aligned_row
        self.blockspin_group = QGroupBox("3D Block Spins Settings")
        self._style_group_box(self.blockspin_group)
        blockspin_layout = QVBoxLayout(self.blockspin_group)
        blockspin_layout.setContentsMargins(0, 12, 0, 0)

        bs_row = _aligned_row(blockspin_layout, "Direction:")
        self.blockspin_direction_combo = StyledComboBox()
        self.blockspin_direction_combo.addItems([
            "Left to Right",
            "Right to Left",
            "Top to Bottom",
            "Bottom to Top",
            "Diagonal TL-BR",
            "Diagonal TR-BL",
            "Random",
        ])
        self.blockspin_direction_combo.currentTextChanged.connect(self._save_settings)
        bs_row.addWidget(self.blockspin_direction_combo)
        bs_row.addStretch()
        self._build_scene3d_choices(blockspin_layout, "blockspin")

        self._specific_group_host_layout.addWidget(self.blockspin_group)

    def _sync_blinds_style(self, *_args) -> None:
        """Show the controls of the chosen Blinds style only."""
        slats = self.blinds_style_combo.currentText() == "3D Slats"
        self.blinds_flat_box.setVisible(not slats)
        self.blinds_slats_box.setVisible(slats)

    def _build_blinds_group(self) -> None:
        _aligned_row = self._aligned_row
        self.blinds_group = QGroupBox("Blinds Settings")
        self._style_group_box(self.blinds_group)
        blinds_layout = QVBoxLayout(self.blinds_group)
        blinds_layout.setContentsMargins(0, 12, 0, 0)

        style_row = _aligned_row(blinds_layout, "Style:")
        self.blinds_style_combo = StyledComboBox(size_variant="compact")
        self.blinds_style_combo.addItems(list(BLINDS_STYLE_CHOICES))
        self.blinds_style_combo.setCurrentText(str(_transition_default("blinds.style")))
        self.blinds_style_combo.setToolTip(
            "Flat: soft bands open over the picture. 3D Slats: solid slats turn over one after "
            "another, the next image on their backs.")
        self.blinds_style_combo.currentTextChanged.connect(self._sync_blinds_style)
        self.blinds_style_combo.currentTextChanged.connect(self._save_settings)
        style_row.addWidget(self.blinds_style_combo)
        style_row.addStretch()

        blinds_dir_row = _aligned_row(blinds_layout, "Direction:")
        self.blinds_direction_combo = StyledComboBox(size_variant="compact")
        self.blinds_direction_combo.addItems(["Horizontal", "Vertical", "Diagonal", "Random"])
        self.blinds_direction_combo.setToolTip(
            "Horizontal: upright stripes. Vertical: lying stripes. 3D Slats turn only these two "
            "ways; Diagonal or Random picks one of them per transition.")
        self.blinds_direction_combo.currentTextChanged.connect(self._save_settings)
        blinds_dir_row.addWidget(self.blinds_direction_combo)
        blinds_dir_row.addStretch()

        self.blinds_flat_box = QWidget()
        flat_layout = QVBoxLayout(self.blinds_flat_box)
        flat_layout.setContentsMargins(0, 0, 0, 0)
        blinds_layout.addWidget(self.blinds_flat_box)
        blinds_feather_row = _aligned_row(flat_layout, "Edge Softness:")
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
        slats_row = _aligned_row(slats_layout, "Slats:")
        self.blinds_slats_spin = QSpinBox()
        self.blinds_slats_spin.setRange(*BLINDS_SLATS_RANGE)
        self.blinds_slats_spin.setValue(int(_transition_default("blinds.slats")))
        self.blinds_slats_spin.setToolTip("How many slats cover the picture.")
        self.blinds_slats_spin.valueChanged.connect(self._save_settings)
        slats_row.addWidget(self.blinds_slats_spin)
        slats_row.addStretch()
        self._build_surface_controls(slats_layout, "blinds")
        self._build_scene3d_choices(slats_layout, "blinds")
        self._sync_blinds_style()

        self._specific_group_host_layout.addWidget(self.blinds_group)

    def _build_ripple_group(self) -> None:
        _aligned_row = self._aligned_row
        self.ripple_group = QGroupBox("Ripple Settings")
        self._style_group_box(self.ripple_group)
        ripple_layout = QVBoxLayout(self.ripple_group)
        ripple_layout.setContentsMargins(0, 12, 0, 0)

        ripple_count_row = _aligned_row(ripple_layout, "Ripple Count:")
        self.ripple_count_spin = QSpinBox()
        self.ripple_count_spin.setRange(1, 8)
        self.ripple_count_spin.setValue(int(_transition_default("ripple.ripple_count")))
        self.ripple_count_spin.valueChanged.connect(self._save_settings)
        ripple_count_row.addWidget(self.ripple_count_spin)
        ripple_count_row.addStretch()

        self._specific_group_host_layout.addWidget(self.ripple_group)

    def _build_crumble_group(self) -> None:
        _aligned_row = self._aligned_row
        self.crumble_group = QGroupBox("Crumble Settings")
        self._style_group_box(self.crumble_group)
        crumble_layout = QVBoxLayout(self.crumble_group)
        crumble_layout.setContentsMargins(0, 12, 0, 0)

        crumble_piece_row = _aligned_row(crumble_layout, "Piece Count:")
        self.crumble_piece_count_spin = QSpinBox()
        self.crumble_piece_count_spin.setRange(4, 128)
        self.crumble_piece_count_spin.setValue(int(_transition_default("crumble.piece_count")))
        self.crumble_piece_count_spin.valueChanged.connect(self._save_settings)
        crumble_piece_row.addWidget(self.crumble_piece_count_spin)
        crumble_piece_row.addStretch()

        crumble_complexity_row = _aligned_row(crumble_layout, "Crack Complexity:")
        self.crumble_complexity_spin = QDoubleSpinBox()
        self.crumble_complexity_spin.setDecimals(2)
        self.crumble_complexity_spin.setRange(0.5, 2.0)
        self.crumble_complexity_spin.setSingleStep(0.1)
        self.crumble_complexity_spin.setValue(float(_transition_default("crumble.crack_complexity")))
        self.crumble_complexity_spin.valueChanged.connect(self._save_settings)
        crumble_complexity_row.addWidget(self.crumble_complexity_spin)
        crumble_complexity_row.addStretch()

        crumble_weight_row = _aligned_row(crumble_layout, "Weighting:")
        self.crumble_weight_combo = StyledComboBox(size_variant="compact")
        self.crumble_weight_combo.addItems([
            "Random Choice",
            "Top Weighted",
            "Bottom Weighted",
            "Random Weighted",
            "Age Weighted",
        ])
        self.crumble_weight_combo.currentTextChanged.connect(self._save_settings)
        crumble_weight_row.addWidget(self.crumble_weight_combo)
        crumble_weight_row.addStretch()

        collide_row = self._aligned_row(crumble_layout, "", wrap=False)
        self.crumble_collisions_check = QCheckBox("Slabs Collide")
        self.crumble_collisions_check.setProperty("circleIndicator", True)
        self.crumble_collisions_check.setToolTip(
            "Falling slabs bounce off each other instead of passing through, and a "
            "standing slab struck by a falling one is knocked loose."
        )
        self.crumble_collisions_check.setChecked(bool(_transition_default("crumble.collisions")))
        self.crumble_collisions_check.stateChanged.connect(self._save_settings)
        collide_row.addWidget(self.crumble_collisions_check)
        collide_row.addStretch()

        self._build_surface_controls(crumble_layout, "crumble")
        self._build_scene3d_choices(crumble_layout, "crumble")
        self._specific_group_host_layout.addWidget(self.crumble_group)

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
            getattr(self, 'slide_motion_style_combo', None),
            getattr(self, 'blockspin_direction_combo', None),
            # Blinds widgets
            getattr(self, 'blinds_direction_combo', None),
            getattr(self, 'blinds_feather_slider', None),
            getattr(self, 'blinds_style_combo', None),
            getattr(self, 'edge_bloom_colour_source_combo', None),
            getattr(self, 'blinds_slats_spin', None),
            getattr(self, 'disintegrate_grain_spin', None),
            getattr(self, 'jigsaw_pieces_spin', None),
            getattr(self, 'volumetric_dissolve_size_spin', None),
            getattr(self, 'beam_sparks_check', None),
            getattr(self, 'chromatic_shear_slices_spin', None),
            getattr(self, 'surface_tension_pools_spin', None),
            getattr(self, 'liquid_lens_droplets_check', None),
            # Ripple widgets
            getattr(self, 'ripple_count_spin', None),
            # Crumble widgets
            getattr(self, 'crumble_piece_count_spin', None),
            getattr(self, 'crumble_complexity_spin', None),
            getattr(self, 'crumble_weight_combo', None),
            getattr(self, 'crumble_collisions_check', None),
            # Particle widgets
            getattr(self, 'particle_mode_combo', None),
            getattr(self, 'particle_direction_combo', None),
            getattr(self, 'particle_radius_spin', None),
            getattr(self, 'particle_trail_check', None),
            getattr(self, 'particle_3d_check', None),
            getattr(self, 'particle_texture_check', None),
            getattr(self, 'particle_wobble_check', None),
            getattr(self, 'particle_gloss_spin', None),
            getattr(self, 'particle_light_combo', None),
            getattr(self, 'particle_swirl_turns_spin', None),
            getattr(self, 'particle_swirl_order_combo', None),
            # Burn widgets
            getattr(self, 'burn_direction_combo', None),
            getattr(self, 'burn_jaggedness_slider', None),
            getattr(self, 'burn_glow_intensity_slider', None),
            getattr(self, 'burn_char_width_slider', None),
            getattr(self, 'burn_smoke_check', None),
            getattr(self, 'burn_smoke_density_slider', None),
            getattr(self, 'burn_ash_check', None),
            getattr(self, 'burn_flames_check', None),
            getattr(self, 'burn_veins_check', None),
            getattr(self, 'burn_ash_density_slider', None),
            # Future transition pages (lazy; absent until selected)
            getattr(self, 'glass_shards_spin', None),
            getattr(self, 'glass_depth_spin', None),
            getattr(self, 'glass_collisions_check', None),
            getattr(self, 'glass_reshatter_check', None),
            getattr(self, 'exploding_tiles_columns_spin', None),
            getattr(self, 'exploding_tiles_depth_spin', None),
            getattr(self, 'pixel_tile_size_spin', None),
            getattr(self, 'pixel_travel_spin', None),
            getattr(self, 'melt_drip_detail_spin', None),
        ]:
            if w is not None and hasattr(w, 'blockSignals'):
                w.blockSignals(True)
                blockers.append(w)

        for section, controls in self._SURFACE_CONTROLS.items():
            for field, *_ in controls:
                spin = getattr(self, f"{section}_{field}_spin", None)
                if spin is not None:
                    spin.blockSignals(True)
                    blockers.append(spin)
        for section, controls in self._SCENE3D_CHOICES.items():
            for field, *_ in controls:
                combo = getattr(self, f"{section}_{field}_combo", None)
                if combo is not None:
                    combo.blockSignals(True)
                    blockers.append(combo)

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
            slide_cfg = transitions_config.get('slide', canonical_transitions['slide'])
            if not isinstance(slide_cfg, dict):
                slide_cfg = dict(canonical_transitions['slide'])
            wipe_cfg = transitions_config.get('wipe', canonical_transitions['wipe'])
            if not isinstance(wipe_cfg, dict):
                wipe_cfg = dict(canonical_transitions['wipe'])
            blockspin_cfg = transitions_config.get('blockspin', canonical_transitions['blockspin'])
            if not isinstance(blockspin_cfg, dict):
                blockspin_cfg = dict(canonical_transitions['blockspin'])

            slide_dir = slide_cfg.get('direction', canonical_transitions['slide']['direction']) or str(canonical_transitions['slide']['direction'])
            wipe_dir = wipe_cfg.get('direction', canonical_transitions['wipe']['direction']) or str(canonical_transitions['wipe']['direction'])
            blockspin_dir = blockspin_cfg.get('direction', canonical_transitions['blockspin']['direction']) or str(canonical_transitions['blockspin']['direction'])

            self._dir_slide = slide_dir
            self._dir_wipe = wipe_dir
            self._dir_blockspin = blockspin_dir
            for section in ("glass_shatter", "exploding_tiles", "pixel_accretion", "melt_drip", "page_curl",
                            "disintegrate", "cube_turn", "beam", "jigsaw", "volumetric_dissolve", "vhs",
                            "liquid_lens", "membrane", "chromatic_shear"):
                canonical_section = canonical_transitions.get(section, {})
                persisted_section = transitions_config.get(section, {})
                if not isinstance(canonical_section, dict):
                    canonical_section = {}
                if not isinstance(persisted_section, dict):
                    persisted_section = {}
                self._direction_by_type[section] = str(
                    persisted_section.get(
                        "direction", canonical_section["direction"]
                    )
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

        # Show/hide direction for transitions that resolve one event vector.
        show_direction = transition in self._DIRECTIONAL_TRANSITIONS
        self.direction_group.setVisible(show_direction)

        # Populate direction options per transition
        if show_direction:
            self.direction_combo.blockSignals(True)
            try:
                self.direction_combo.clear()
                if transition == "Slide":
                    slide_items = [
                        "Left to Right",
                        "Right to Left",
                        "Top to Bottom",
                        "Bottom to Top",
                        "Random",
                    ]
                    self.direction_combo.addItems(slide_items)
                    # Set previously stored selection
                    idx = self.direction_combo.findText(self._dir_slide)
                    if idx < 0:
                        idx = self.direction_combo.findText("Random") if self._dir_slide == "Random" else 0
                    self.direction_combo.setCurrentIndex(max(0, idx))
                elif transition == "Wipe":
                    # Wipe: include diagonals
                    wipe_items = [
                        "Left to Right",
                        "Right to Left",
                        "Top to Bottom",
                        "Bottom to Top",
                        "Diagonal TL-BR",
                        "Diagonal TR-BL",
                        "Random",
                    ]
                    self.direction_combo.addItems(wipe_items)
                    idx = self.direction_combo.findText(self._dir_wipe)
                    if idx < 0:
                        idx = self.direction_combo.findText("Random") if self._dir_wipe == "Random" else 0
                    self.direction_combo.setCurrentIndex(max(0, idx))
                elif transition in {"Glass Shatter", "Exploding Tiles"}:
                    self.direction_combo.addItems([
                        "Left to Right", "Right to Left", "Top to Bottom",
                        "Bottom to Top", "Diagonal TL-BR", "Diagonal TR-BL",
                        "Center Out", "Random",
                    ])
                    current = self._direction_by_type["glass_shatter" if transition == "Glass Shatter" else "exploding_tiles"]
                    idx = self.direction_combo.findText(current)
                    if idx < 0:
                        idx = self.direction_combo.findText("Random")
                    self.direction_combo.setCurrentIndex(max(0, idx))
                elif transition in {"Directional Pixel Accretion", "Disintegrate", "Beam"}:
                    self.direction_combo.addItems([
                        "Left to Right", "Right to Left", "Top to Bottom",
                        "Bottom to Top", "Diagonal TL-BR", "Diagonal TR-BL",
                        "Diagonal BL-TR", "Diagonal BR-TL", "Random",
                    ])
                    current = self._direction_by_type[{"Directional Pixel Accretion": "pixel_accretion",
                                                       "Disintegrate": "disintegrate",
                                                       "Beam": "beam"}[transition]]
                    idx = self.direction_combo.findText(current)
                    if idx < 0:
                        idx = self.direction_combo.findText("Random")
                    self.direction_combo.setCurrentIndex(max(0, idx))
                elif transition == "Melt Drip":
                    # Melt starts at an origin, not an edge; retired edge
                    # directions from older profiles show as Random.
                    self.direction_combo.addItems([
                        "Top Left", "Top Center", "Top Right",
                        "Center Out", "Center In", "Random",
                    ])
                    current = self._direction_by_type["melt_drip"]
                    idx = self.direction_combo.findText(current)
                    if idx < 0:
                        idx = self.direction_combo.findText("Random")
                    self.direction_combo.setCurrentIndex(max(0, idx))
                elif transition == "Cube Turn":
                    # The way the box turns: its front moves toward this side.
                    self.direction_combo.addItems(list(CUBE_TURN_DIRECTION_CHOICES))
                    idx = self.direction_combo.findText(self._direction_by_type["cube_turn"])
                    if idx < 0:
                        idx = self.direction_combo.findText("Random")
                    self.direction_combo.setCurrentIndex(max(0, idx))
                elif transition == "Page Curl":
                    # Where the page starts to peel: a corner or an edge.
                    self.direction_combo.addItems(list(PAGE_CURL_ORIGIN_CHOICES))
                    idx = self.direction_combo.findText(self._direction_by_type["page_curl"])
                    if idx < 0:
                        idx = self.direction_combo.findText("Random")
                    self.direction_combo.setCurrentIndex(max(0, idx))
                elif transition == "Volumetric Dissolve":
                    # Where the dissolve starts and the way it sweeps, or from the centre out.
                    self.direction_combo.addItems(list(VOLUMETRIC_DIRECTION_CHOICES))
                    idx = self.direction_combo.findText(self._direction_by_type["volumetric_dissolve"])
                    if idx < 0:
                        idx = self.direction_combo.findText("Random")
                    self.direction_combo.setCurrentIndex(max(0, idx))
                elif transition == "Liquid Lens":
                    self.direction_combo.addItems(list(LIQUID_LENS_ORIGIN_CHOICES))
                    idx = self.direction_combo.findText(self._direction_by_type["liquid_lens"])
                    if idx < 0:
                        idx = self.direction_combo.findText("Random")
                    self.direction_combo.setCurrentIndex(max(0, idx))
                elif transition == "Membrane Turnover":
                    self.direction_combo.addItems(list(MEMBRANE_SWEEP_CHOICES))
                    idx = self.direction_combo.findText(self._direction_by_type["membrane"])
                    if idx < 0:
                        idx = self.direction_combo.findText("Random")
                    self.direction_combo.setCurrentIndex(max(0, idx))
                elif transition == "Chromatic Shear":
                    self.direction_combo.addItems(list(SHEAR_DIRECTION_CHOICES))
                    idx = self.direction_combo.findText(self._direction_by_type["chromatic_shear"])
                    if idx < 0:
                        idx = self.direction_combo.findText("Random")
                    self.direction_combo.setCurrentIndex(max(0, idx))
                elif transition == "VHS Distortion":
                    # The way the picture rolls: where the new picture comes in.
                    self.direction_combo.addItems(list(VHS_DIRECTION_CHOICES))
                    idx = self.direction_combo.findText(self._direction_by_type["vhs"])
                    if idx < 0:
                        idx = self.direction_combo.findText("Random")
                    self.direction_combo.setCurrentIndex(max(0, idx))
                elif transition == "Jigsaw Piece Flip":
                    # The order the pieces flip in: from a corner, from a random piece, or shuffled.
                    self.direction_combo.addItems(list(JIGSAW_ORDER_CHOICES))
                    idx = self.direction_combo.findText(self._direction_by_type["jigsaw"])
                    if idx < 0:
                        idx = self.direction_combo.findText("Random")
                    self.direction_combo.setCurrentIndex(max(0, idx))
            finally:
                self.direction_combo.blockSignals(False)

        # Show only the built specific group matching the current transition.
        # Unbuilt groups (lazy) simply have nothing to show.
        for group_transition, group_attr in self._SPECIFIC_GROUP_ATTRS.items():
            group = getattr(self, group_attr, None)
            if group is not None:
                group.setVisible(transition == group_transition)
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
        cur_dir = self.direction_combo.currentText()
        if cur_type == "Slide":
            self._dir_slide = cur_dir
        elif cur_type == "Wipe":
            self._dir_wipe = cur_dir
        elif cur_type == "Glass Shatter":
            self._direction_by_type["glass_shatter"] = cur_dir
        elif cur_type == "Exploding Tiles":
            self._direction_by_type["exploding_tiles"] = cur_dir
        elif cur_type == "Directional Pixel Accretion":
            self._direction_by_type["pixel_accretion"] = cur_dir
        elif cur_type == "Melt Drip":
            self._direction_by_type["melt_drip"] = cur_dir
        elif cur_type == "Page Curl":
            self._direction_by_type["page_curl"] = cur_dir
        elif cur_type == "Disintegrate":
            self._direction_by_type["disintegrate"] = cur_dir
        elif cur_type == "Cube Turn":
            self._direction_by_type["cube_turn"] = cur_dir
        elif cur_type == "Beam":
            self._direction_by_type["beam"] = cur_dir
        elif cur_type == "Jigsaw Piece Flip":
            self._direction_by_type["jigsaw"] = cur_dir
        elif cur_type == "Volumetric Dissolve":
            self._direction_by_type["volumetric_dissolve"] = cur_dir
        elif cur_type == "VHS Distortion":
            self._direction_by_type["vhs"] = cur_dir
        elif cur_type == "Chromatic Shear":
            self._direction_by_type["chromatic_shear"] = cur_dir
        elif cur_type == "Membrane Turnover":
            self._direction_by_type["membrane"] = cur_dir
        elif cur_type == "Liquid Lens":
            self._direction_by_type["liquid_lens"] = cur_dir
        if hasattr(self, 'blockspin_direction_combo'):
            self._dir_blockspin = (
                self.blockspin_direction_combo.currentText()
                or str(_transition_default("blockspin.direction"))
            )

        cur_duration = self.duration_slider.value()
        self._duration_by_type[cur_type] = cur_duration

        for name, checkbox in getattr(self, "_activation_checkboxes", {}).items():
            self._activation_by_type[name] = bool(checkbox.isChecked())
        try:
            use_random = bool(self._use_random_checkbox.isChecked())
        except Exception as e:
            logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)
            use_random = bool(_transition_default('random_always'))

        # Build the section fresh (dropping retired/stale keys), preserving only
        # the transient random-choice bookkeeping and any UNBUILT transition's
        # detail subdict from the existing persisted state.
        if hasattr(self, 'blinds_group'):
            self.blinds_feather_label.setText(str(self.blinds_feather_slider.value()))
            blinds = {
                'feather': self.blinds_feather_slider.value(),
                'direction': self.blinds_direction_combo.currentText(),
                'style': self.blinds_style_combo.currentText(),
                'slats': self.blinds_slats_spin.value(),
            }
        else:
            blinds = _existing_subdict('blinds')
        if hasattr(self, 'ripple_group'):
            ripple = {'ripple_count': self.ripple_count_spin.value()}
        else:
            ripple = _existing_subdict('ripple')
        if hasattr(self, 'crumble_group'):
            crumble = {
                'piece_count': self.crumble_piece_count_spin.value(),
                'crack_complexity': self.crumble_complexity_spin.value(),
                'weighting': self.crumble_weight_combo.currentText(),
                'collisions': self.crumble_collisions_check.isChecked(),
            }
        else:
            crumble = _existing_subdict('crumble')
        if hasattr(self, 'particle_group'):
            particle = {
                'mode': self.particle_mode_combo.currentText(),
                'direction': self.particle_direction_combo.currentText(),
                'particle_radius': float(self.particle_radius_spin.value()),
                'overlap': 4.0,
                'trail_length': 0.15 if self.particle_trail_check.isChecked() else 0.0,
                'trail_strength': 0.6 if self.particle_trail_check.isChecked() else 0.0,
                'swirl_strength': 1.0,
                'swirl_turns': self.particle_swirl_turns_spin.value(),
                'use_3d_shading': self.particle_3d_check.isChecked(),
                'texture_mapping': self.particle_texture_check.isChecked(),
                'wobble': self.particle_wobble_check.isChecked(),
                'gloss_size': float(self.particle_gloss_spin.value()),
                'light_direction': self.particle_light_combo.currentIndex(),
                'swirl_order': self.particle_swirl_order_combo.currentIndex(),
            }
        else:
            particle = _existing_subdict('particle')
        if hasattr(self, 'burn_group'):
            burn = {
                'direction': self.burn_direction_combo.currentText(),
                'jaggedness': self.burn_jaggedness_slider.value() / 100.0,
                'glow_intensity': self.burn_glow_intensity_slider.value() / 100.0,
                'char_width': self.burn_char_width_slider.value() / 100.0,
                'glow_color': [
                    self._burn_glow_color.red(),
                    self._burn_glow_color.green(),
                    self._burn_glow_color.blue(),
                    self._burn_glow_color.alpha(),
                ],
                'ember_color': [
                    self._burn_ember_color.red(),
                    self._burn_ember_color.green(),
                    self._burn_ember_color.blue(),
                    self._burn_ember_color.alpha(),
                ],
                'smoke_enabled': self.burn_smoke_check.isChecked(),
                'smoke_density': self.burn_smoke_density_slider.value() / 100.0,
                'ash_enabled': self.burn_ash_check.isChecked(),
                'ash_density': self.burn_ash_density_slider.value() / 100.0,
                'flames': self.burn_flames_check.isChecked(),
                'ember_veins': self.burn_veins_check.isChecked(),
            }
        else:
            burn = _existing_subdict('burn')

        if hasattr(self, 'glass_shatter_group'):
            glass_shatter = {
                'shards': self.glass_shards_spin.value(),
                'depth': float(self.glass_depth_spin.value()),
                'direction': self._direction_by_type['glass_shatter'],
                'collisions': self.glass_collisions_check.isChecked(),
                'reshatter': self.glass_reshatter_check.isChecked(),
            }
        else:
            glass_shatter = _existing_subdict('glass_shatter')
        if hasattr(self, 'exploding_tiles_group'):
            exploding_tiles = {
                'columns': self.exploding_tiles_columns_spin.value(),
                'depth': float(self.exploding_tiles_depth_spin.value()),
                'direction': self._direction_by_type['exploding_tiles'],
            }
        else:
            exploding_tiles = _existing_subdict('exploding_tiles')
        if hasattr(self, 'pixel_accretion_group'):
            pixel_accretion = {
                'tile_size': self.pixel_tile_size_spin.value(),
                'travel': float(self.pixel_travel_spin.value()),
                'direction': self._direction_by_type['pixel_accretion'],
            }
        else:
            pixel_accretion = _existing_subdict('pixel_accretion')
        if hasattr(self, 'melt_drip_group'):
            melt_drip = {
                'detail': float(self.melt_drip_detail_spin.value()),
                'direction': self._direction_by_type['melt_drip'],
            }
        else:
            melt_drip = _existing_subdict('melt_drip')
        if hasattr(self, 'beam_group'):
            c = self._beam_color
            beam = {'direction': self._direction_by_type['beam'],
                    'color': [c.red(), c.green(), c.blue(), 255],
                    'sparks': self.beam_sparks_check.isChecked()}
        else:
            beam = {**_existing_subdict('beam'), 'direction': self._direction_by_type['beam']}
        if hasattr(self, 'cube_turn_group'):
            cube_turn = {'direction': self._direction_by_type['cube_turn']}
        else:
            cube_turn = {**_existing_subdict('cube_turn'), 'direction': self._direction_by_type['cube_turn']}
        if hasattr(self, 'disintegrate_group'):
            disintegrate = {'direction': self._direction_by_type['disintegrate'],
                            'grain_size': self.disintegrate_grain_spin.value()}
        else:
            disintegrate = {**_existing_subdict('disintegrate'), 'direction': self._direction_by_type['disintegrate']}
        if hasattr(self, 'page_curl_group'):
            page_curl = {'direction': self._direction_by_type['page_curl']}
        else:
            page_curl = {**_existing_subdict('page_curl'), 'direction': self._direction_by_type['page_curl']}
        if hasattr(self, 'volumetric_dissolve_group'):
            volumetric_dissolve = {'direction': self._direction_by_type['volumetric_dissolve'],
                                   'particle_size': self.volumetric_dissolve_size_spin.value()}
        else:
            volumetric_dissolve = {**_existing_subdict('volumetric_dissolve'),
                                   'direction': self._direction_by_type['volumetric_dissolve']}
        if hasattr(self, 'edge_bloom_group'):
            c = self._edge_bloom_color
            edge_bloom = {'color': [c.red(), c.green(), c.blue(), 255],
                          'color_source': self.edge_bloom_colour_source_combo.currentText()}
        else:
            edge_bloom = _existing_subdict('edge_bloom')
        if hasattr(self, 'liquid_lens_group'):
            liquid_lens = {'direction': self._direction_by_type['liquid_lens'], 'droplets': self.liquid_lens_droplets_check.isChecked()}
        else:
            liquid_lens = {**_existing_subdict('liquid_lens'), 'direction': self._direction_by_type['liquid_lens']}
        if hasattr(self, 'membrane_group'):
            membrane = {'direction': self._direction_by_type['membrane']}
        else:
            membrane = {**_existing_subdict('membrane'), 'direction': self._direction_by_type['membrane']}
        if hasattr(self, 'surface_tension_group'):
            surface_tension = {'pools': self.surface_tension_pools_spin.value()}
        else:
            surface_tension = _existing_subdict('surface_tension')
        if hasattr(self, 'chromatic_shear_group'):
            chromatic_shear = {'direction': self._direction_by_type['chromatic_shear'], 'slices': self.chromatic_shear_slices_spin.value()}
        else:
            chromatic_shear = {**_existing_subdict('chromatic_shear'), 'direction': self._direction_by_type['chromatic_shear']}
        if hasattr(self, 'vhs_group'):
            vhs = {'direction': self._direction_by_type['vhs']}
        else:
            vhs = {**_existing_subdict('vhs'), 'direction': self._direction_by_type['vhs']}
        if hasattr(self, 'jigsaw_group'):
            jigsaw = {'direction': self._direction_by_type['jigsaw'], 'pieces': self.jigsaw_pieces_spin.value()}
        else:
            jigsaw = {**_existing_subdict('jigsaw'), 'direction': self._direction_by_type['jigsaw']}

        for section, values in (("blinds", blinds), ("crumble", crumble), ("glass_shatter", glass_shatter),
                                ("exploding_tiles", exploding_tiles),
                                ("melt_drip", melt_drip), ("page_curl", page_curl),
                                ("disintegrate", disintegrate), ("cube_turn", cube_turn), ("beam", beam),
                                ("volumetric_dissolve", volumetric_dissolve), ("vhs", vhs),
                                ("edge_bloom", edge_bloom), ("liquid_lens", liquid_lens), ("membrane", membrane), ("surface_tension", surface_tension), ("chromatic_shear", chromatic_shear)):
            if hasattr(self, f"{section}_group"):
                for field, *_ in self._SURFACE_CONTROLS[section]:
                    values[field] = float(getattr(self, f"{section}_{field}_spin").value())

        config = {
            'type': cur_type,
            'duration_ms': cur_duration,
            'durations': dict(self._duration_by_type),
            'pool': dict(self._pool_by_type),
            'activation': dict(self._activation_by_type),
            'random_always': use_random,
            'slide': (
                {
                    'direction': self._dir_slide,
                    'motion_style': self.slide_motion_style_combo.currentText(),
                }
                if hasattr(self, 'slide_group')
                else {
                    **_existing_subdict('slide'),
                    'direction': self._dir_slide,
                }
            ),
            'wipe': {'direction': self._dir_wipe},
            'blockspin': {**_existing_subdict('blockspin'), 'direction': self._dir_blockspin},
            'blinds': blinds,
            'ripple': ripple,
            'crumble': crumble,
            'particle': particle,
            'burn': burn,
            'glass_shatter': glass_shatter,
            'exploding_tiles': exploding_tiles,
            'pixel_accretion': pixel_accretion,
            'melt_drip': melt_drip,
            'page_curl': page_curl,
            'disintegrate': disintegrate,
            'cube_turn': cube_turn,
            'beam': beam,
            'jigsaw': jigsaw,
            'volumetric_dissolve': volumetric_dissolve,
            'vhs': vhs,
            'edge_bloom': edge_bloom,
            'chromatic_shear': chromatic_shear,
            'surface_tension': surface_tension,
            'membrane': membrane,
            'liquid_lens': liquid_lens,
        }
        for section, controls in self._SCENE3D_CHOICES.items():
            if hasattr(self, f"{section}_group"):
                for field, *_ in controls:
                    config[section][field] = getattr(self, f"{section}_{field}_combo").currentText()

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
