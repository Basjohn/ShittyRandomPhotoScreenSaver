"""
Transitions configuration tab for settings dialog.

Allows users to configure transition settings:
- Transition type selection
- Duration
- Direction (for directional transitions)
- Easing curves
"""
from typing import Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QGroupBox, QScrollArea, QPushButton, QButtonGroup,
    QSpinBox, QDoubleSpinBox,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor

from core.settings.defaults import get_default_settings
from core.settings.settings_manager import SettingsManager
from core.settings.capability_activation import (
    is_transition_activated,
    normalize_transition_capability_state,
)
from core.logging.logger import get_logger
from rendering.transition_registry import (
    canonicalize_transition_name,
    get_transition_setting_names,
)
from ui.tabs.shared_styles import (
    COMBOBOX_STYLE,
    CIRCLE_CHECKBOX_STYLE,
    SLIDER_STYLE,
    SPINBOX_STYLE,
    PAGE_TITLE_STYLE,
    add_swatch_label,
    style_group_box,
    add_aligned_row_widget as shared_add_aligned_row_widget,
    add_aligned_row as shared_add_aligned_row,
    NoWheelSlider,
)
from ui.styled_popup import ColorSwatchButton, StyledColorPicker
from ui.widgets import StyledComboBox

logger = get_logger(__name__)

_TRANSITION_SETTING_NAMES = get_transition_setting_names()

_SETUP_NAV_KEY = "__setup__"

_NAV_PILL_STYLE = (
    "QPushButton {"
    " background-color: rgba(42, 42, 42, 215);"
    " color: #ffffff;"
    " border: 1px solid #ffffff;"
    " border-radius: 8px;"
    " padding: 5px 14px;"
    " }"
    "QPushButton:hover { background-color: rgba(52, 52, 52, 220); }"
    "QPushButton:checked { background-color: rgba(58, 58, 58, 220); }"
)

_SETUP_ACTION_BUTTON_STYLE = (
    "QPushButton {"
    " background-color: rgba(42, 42, 42, 215);"
    " color: #ffffff;"
    " border: 1px solid #ffffff;"
    " border-radius: 8px;"
    " padding: 6px 18px;"
    " min-width: 90px;"
    " }"
    "QPushButton:hover { background-color: rgba(58, 58, 58, 220); }"
)


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
        # Maintain per-transition direction selections in-memory (default: Random)
        self._dir_slide: str = "Random"
        self._dir_wipe: str = "Random"
        self._dir_blockspin: str = "Left to Right"
        # Per-transition pool membership for random/switch behaviour.
        self._pool_by_type = {}
        self._duration_by_type = {}
        # Per-transition application-level capability activation (E2 SETUP).
        self._activation_by_type = {}
        self._loading = False
        self._setup_ui()
        self._load_settings()
        
        logger.debug("TransitionsTab created")
    
    def load_from_settings(self) -> None:
        """Reload all UI controls from settings manager (called after preset change)."""
        self._load_settings()
        logger.debug("[TRANSITIONS_TAB] Reloaded from settings")
    
    def _setup_ui(self) -> None:
        """Setup tab UI with scroll area."""
        # Create scroll area
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QScrollArea.NoFrame)
        from ui.tabs.shared_styles import SCROLL_AREA_STYLE
        scroll.setStyleSheet(SCROLL_AREA_STYLE + SLIDER_STYLE)
        
        LABEL_WIDTH = 160
        VALUE_LABEL_WIDTH = 72

        def _aligned_row_widget(
            parent_layout: QVBoxLayout,
            label_text: str,
            *,
            wrap: bool = True,
        ) -> tuple[QWidget, QHBoxLayout]:
            row_widget, content, _ = shared_add_aligned_row_widget(
                parent_layout,
                label_text,
                label_width=LABEL_WIDTH,
                wrap=wrap,
            )
            return row_widget, content

        def _aligned_row(
            parent_layout: QVBoxLayout,
            label_text: str,
            *,
            wrap: bool = True,
        ) -> QHBoxLayout:
            content, _ = shared_add_aligned_row(
                parent_layout,
                label_text,
                label_width=LABEL_WIDTH,
                wrap=wrap,
            )
            return content

        def _swatch_row(parent_layout: QVBoxLayout, label_text: str) -> QHBoxLayout:
            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 8, 0, 8)
            row_layout.setSpacing(12)
            add_swatch_label(row_layout, label_text, LABEL_WIDTH)
            content = QHBoxLayout()
            content.setContentsMargins(0, 0, 0, 0)
            content.setSpacing(12)
            row_layout.addLayout(content, 1)
            parent_layout.addWidget(row_widget)
            return content

        def _add_value_label(
            row_layout: QHBoxLayout,
            text: str,
            *,
            width: int = VALUE_LABEL_WIDTH,
        ) -> QLabel:
            label = QLabel(text)
            label.setMinimumWidth(width)
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            row_layout.addWidget(label)
            return label

        def _style_group_box(box: QGroupBox) -> None:
            style_group_box(box)

        # Create content widget
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        
        # Title
        title = QLabel("Transition Settings")
        title.setStyleSheet(PAGE_TITLE_STYLE)
        layout.addWidget(title)
        
        # Internal selection model. The old visible dropdown is replaced by the
        # pill nav below (E2.3); this combo is retained (not shown) purely as the
        # "currently edited transition" value model that the existing per-transition
        # load/update/save logic already reads from. Phase I removes it once that
        # logic is migrated off it.
        self.transition_combo = StyledComboBox(size_variant="hero")
        self.transition_combo.addItems(_TRANSITION_SETTING_NAMES)
        self.transition_combo.currentTextChanged.connect(self._on_transition_changed)
        self.transition_combo.setVisible(False)

        # Pill/subtab navigation: SETUP first, then one pill per transition.
        nav_row = QHBoxLayout()
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        self._nav_buttons = {}

        def _add_nav_pill(key: str, label: str) -> None:
            button = QPushButton(label)
            button.setCheckable(True)
            button.setStyleSheet(_NAV_PILL_STYLE)
            self._nav_buttons[key] = button
            self._nav_group.addButton(button)
            button.clicked.connect(lambda _checked=False, k=key: self._on_nav_selected(k))
            nav_row.addWidget(button)

        _add_nav_pill(_SETUP_NAV_KEY, "Setup")
        for name in _TRANSITION_SETTING_NAMES:
            _add_nav_pill(name, name)
        nav_row.addStretch()
        layout.addLayout(nav_row)

        # Duration group (slider: short → long)
        duration_group = QGroupBox("Timing")
        _style_group_box(duration_group)
        duration_layout = QVBoxLayout(duration_group)
        duration_layout.setContentsMargins(0, 12, 0, 0)
        duration_layout.setSpacing(12)
        duration_row = _aligned_row(duration_layout, "Duration (short → long):")
        self.duration_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.duration_slider.setRange(100, 15000)  # store milliseconds directly (15s max)
        self.duration_slider.setSingleStep(100)
        self.duration_slider.setPageStep(500)
        self.duration_slider.setValue(1300)  # BUG FIX #5: Increased from 1000ms (30% slower)
        self.duration_slider.valueChanged.connect(self._on_duration_changed)
        duration_row.addWidget(self.duration_slider, 1)
        self.duration_value_label = _add_value_label(duration_row, "1300 ms", width=86)
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
        
        # Block flip specific settings
        self.flip_group = QGroupBox("Block Flip Settings")
        _style_group_box(self.flip_group)
        flip_layout = QVBoxLayout(self.flip_group)
        flip_layout.setContentsMargins(0, 12, 0, 0)
        
        grid_rows_row = _aligned_row(flip_layout, "Grid Rows:")
        self.grid_rows_spin = QSpinBox()
        self.grid_rows_spin.setRange(2, 25)
        self.grid_rows_spin.setValue(4)
        self.grid_rows_spin.setAccelerated(True)
        self.grid_rows_spin.valueChanged.connect(self._save_settings)
        grid_rows_row.addWidget(self.grid_rows_spin)
        grid_rows_row.addStretch()

        grid_cols_row = _aligned_row(flip_layout, "Grid Columns:")
        self.grid_cols_spin = QSpinBox()
        self.grid_cols_spin.setRange(2, 25)
        self.grid_cols_spin.setValue(6)
        self.grid_cols_spin.setAccelerated(True)
        self.grid_cols_spin.valueChanged.connect(self._save_settings)
        grid_cols_row.addWidget(self.grid_cols_spin)
        grid_cols_row.addStretch()

        flip_dir_row = _aligned_row(flip_layout, "Direction:")
        self.blockflip_direction_combo = StyledComboBox()
        self.blockflip_direction_combo.addItems([
            "Left to Right",
            "Right to Left",
            "Top to Bottom",
            "Bottom to Top",
            "Diagonal TL to BR",
            "Diagonal TR to BL",
            "Random",
        ])
        self.blockflip_direction_combo.currentTextChanged.connect(self._save_settings)
        flip_dir_row.addWidget(self.blockflip_direction_combo)
        flip_dir_row.addStretch()
        
        layout.addWidget(self.flip_group)

        # 3D Block Spins specific settings (single-slab only, no grid)
        self.blockspin_group = QGroupBox("3D Block Spins Settings")
        _style_group_box(self.blockspin_group)
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

        layout.addWidget(self.blockspin_group)

        # Blinds specific settings
        self.blinds_group = QGroupBox("Blinds Settings")
        _style_group_box(self.blinds_group)
        blinds_layout = QVBoxLayout(self.blinds_group)
        blinds_layout.setContentsMargins(0, 12, 0, 0)

        blinds_dir_row = _aligned_row(blinds_layout, "Direction:")
        self.blinds_direction_combo = StyledComboBox(size_variant="compact")
        self.blinds_direction_combo.addItems(["Horizontal", "Vertical", "Diagonal", "Random"])
        self.blinds_direction_combo.currentTextChanged.connect(self._save_settings)
        blinds_dir_row.addWidget(self.blinds_direction_combo)
        blinds_dir_row.addStretch()

        blinds_feather_row = _aligned_row(blinds_layout, "Edge Softness:")
        self.blinds_feather_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.blinds_feather_slider.setRange(0, 25)
        self.blinds_feather_slider.setSingleStep(1)
        self.blinds_feather_slider.setValue(2)
        self.blinds_feather_slider.valueChanged.connect(self._save_settings)
        blinds_feather_row.addWidget(self.blinds_feather_slider, 1)
        self.blinds_feather_label = _add_value_label(blinds_feather_row, "2")
        blinds_feather_row.addStretch()

        layout.addWidget(self.blinds_group)
        
        # Diffuse specific settings
        self.diffuse_group = QGroupBox("Diffuse Settings")
        _style_group_box(self.diffuse_group)
        diffuse_layout = QVBoxLayout(self.diffuse_group)
        diffuse_layout.setContentsMargins(0, 12, 0, 0)

        block_size_row = _aligned_row(diffuse_layout, "Block Size (px):")
        self.block_size_spin = QSpinBox()
        self.block_size_spin.setRange(4, 256)
        self.block_size_spin.setValue(18)
        self.block_size_spin.valueChanged.connect(self._save_settings)
        block_size_row.addWidget(self.block_size_spin)
        block_size_row.addStretch()

        shape_row = _aligned_row(diffuse_layout, "Shape:")
        self.diffuse_shape_combo = StyledComboBox(size_variant="compact")
        self.diffuse_shape_combo.addItems([
            "Rectangle",
            "Membrane",
            "Lines",
            "Diamonds",
            "Amorph",
        ])
        self.diffuse_shape_combo.currentTextChanged.connect(self._save_settings)
        shape_row.addWidget(self.diffuse_shape_combo)
        shape_row.addStretch()

        layout.addWidget(self.diffuse_group)

        # Ripple specific settings
        self.ripple_group = QGroupBox("Ripple Settings")
        _style_group_box(self.ripple_group)
        ripple_layout = QVBoxLayout(self.ripple_group)
        ripple_layout.setContentsMargins(0, 12, 0, 0)

        ripple_count_row = _aligned_row(ripple_layout, "Ripple Count:")
        self.ripple_count_spin = QSpinBox()
        self.ripple_count_spin.setRange(1, 8)
        self.ripple_count_spin.setValue(3)
        self.ripple_count_spin.valueChanged.connect(self._save_settings)
        ripple_count_row.addWidget(self.ripple_count_spin)
        ripple_count_row.addStretch()

        layout.addWidget(self.ripple_group)

        # Crumble specific settings
        self.crumble_group = QGroupBox("Crumble Settings")
        _style_group_box(self.crumble_group)
        crumble_layout = QVBoxLayout(self.crumble_group)
        crumble_layout.setContentsMargins(0, 12, 0, 0)

        crumble_piece_row = _aligned_row(crumble_layout, "Piece Count:")
        self.crumble_piece_count_spin = QSpinBox()
        self.crumble_piece_count_spin.setRange(4, 128)
        self.crumble_piece_count_spin.setValue(14)
        self.crumble_piece_count_spin.valueChanged.connect(self._save_settings)
        crumble_piece_row.addWidget(self.crumble_piece_count_spin)
        crumble_piece_row.addStretch()

        crumble_complexity_row = _aligned_row(crumble_layout, "Crack Complexity:")
        self.crumble_complexity_spin = QDoubleSpinBox()
        self.crumble_complexity_spin.setDecimals(2)
        self.crumble_complexity_spin.setRange(0.2, 5.0)
        self.crumble_complexity_spin.setSingleStep(0.1)
        self.crumble_complexity_spin.setValue(1.0)
        self.crumble_complexity_spin.valueChanged.connect(self._save_settings)
        crumble_complexity_row.addWidget(self.crumble_complexity_spin)
        crumble_complexity_row.addStretch()

        crumble_weight_row = _aligned_row(crumble_layout, "Weighting:")
        self.crumble_weight_combo = StyledComboBox(size_variant="compact")
        self.crumble_weight_combo.addItems([
            "Random Choice",
            "Bias Old Image",
            "Bias New Image",
        ])
        self.crumble_weight_combo.currentTextChanged.connect(self._save_settings)
        crumble_weight_row.addWidget(self.crumble_weight_combo)
        crumble_weight_row.addStretch()

        layout.addWidget(self.crumble_group)

        # Particle transition settings
        self.particle_group = QGroupBox("Particle Settings")
        _style_group_box(self.particle_group)
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
        self.particle_radius_spin.setValue(10)
        self.particle_radius_spin.valueChanged.connect(self._save_settings)
        particle_radius_row.addWidget(self.particle_radius_spin)
        particle_radius_row.addStretch()

        particle_trail_row = _aligned_row(particle_layout, "", wrap=False)
        self.particle_trail_check = QCheckBox("Motion Trail")
        self.particle_trail_check.setProperty("circleIndicator", True)
        self.particle_trail_check.setChecked(True)
        self.particle_trail_check.stateChanged.connect(self._save_settings)
        particle_trail_row.addWidget(self.particle_trail_check)
        particle_trail_row.addStretch()

        particle_3d_row = _aligned_row(particle_layout, "", wrap=False)
        self.particle_3d_check = QCheckBox("3D Ball Shading")
        self.particle_3d_check.setProperty("circleIndicator", True)
        self.particle_3d_check.setChecked(True)
        self.particle_3d_check.stateChanged.connect(self._save_settings)
        particle_3d_row.addWidget(self.particle_3d_check)
        particle_3d_row.addStretch()

        particle_texture_row = _aligned_row(particle_layout, "", wrap=False)
        self.particle_texture_check = QCheckBox("Map Image to Particles")
        self.particle_texture_check.setProperty("circleIndicator", True)
        self.particle_texture_check.setChecked(True)
        self.particle_texture_check.stateChanged.connect(self._save_settings)
        particle_texture_row.addWidget(self.particle_texture_check)
        particle_texture_row.addStretch()

        particle_wobble_row = _aligned_row(particle_layout, "", wrap=False)
        self.particle_wobble_check = QCheckBox("Wobble on Arrival")
        self.particle_wobble_check.setProperty("circleIndicator", True)
        self.particle_wobble_check.setChecked(False)
        self.particle_wobble_check.stateChanged.connect(self._save_settings)
        particle_wobble_row.addWidget(self.particle_wobble_check)
        particle_wobble_row.addStretch()

        particle_gloss_row = _aligned_row(particle_layout, "Gloss Size:")
        self.particle_gloss_spin = QSpinBox()
        self.particle_gloss_spin.setRange(10, 200)
        self.particle_gloss_spin.setValue(72)
        self.particle_gloss_spin.valueChanged.connect(self._save_settings)
        particle_gloss_row.addWidget(self.particle_gloss_spin)
        particle_gloss_row.addStretch()

        particle_light_row = _aligned_row(particle_layout, "Light Direction:")
        self.particle_light_combo = StyledComboBox(size_variant="compact")
        self.particle_light_combo.addItems([
            "Front",
            "Left",
            "Right",
            "Top",
            "Bottom",
        ])
        self.particle_light_combo.currentIndexChanged.connect(self._save_settings)
        particle_light_row.addWidget(self.particle_light_combo)
        particle_light_row.addStretch()

        particle_swirl_turns_row = _aligned_row(particle_layout, "Swirl Turns:")
        self.particle_swirl_turns_spin = QDoubleSpinBox()
        self.particle_swirl_turns_spin.setDecimals(2)
        self.particle_swirl_turns_spin.setRange(0.5, 6.0)
        self.particle_swirl_turns_spin.setSingleStep(0.1)
        self.particle_swirl_turns_spin.setValue(3.0)
        self.particle_swirl_turns_spin.valueChanged.connect(self._save_settings)
        particle_swirl_turns_row.addWidget(self.particle_swirl_turns_spin)
        particle_swirl_turns_row.addStretch()

        particle_swirl_order_row = _aligned_row(particle_layout, "Swirl Build Order:")
        self.particle_swirl_order_combo = StyledComboBox(size_variant="compact")
        self.particle_swirl_order_combo.addItems([
            "Inside-Out",
            "Outside-In",
            "Random",
        ])
        self.particle_swirl_order_combo.currentIndexChanged.connect(self._save_settings)
        particle_swirl_order_row.addWidget(self.particle_swirl_order_combo)
        particle_swirl_order_row.addStretch()

        layout.addWidget(self.particle_group)

        # Burn specific settings
        self.burn_group = QGroupBox("Burn Settings")
        _style_group_box(self.burn_group)
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
        self.burn_jaggedness_slider.setValue(50)
        self.burn_jaggedness_slider.setToolTip("Edge noise amplitude (0 = smooth wipe, 100 = very jagged)")
        self.burn_jaggedness_slider.valueChanged.connect(self._save_settings)
        burn_jag_row.addWidget(self.burn_jaggedness_slider, 1)
        self.burn_jaggedness_label = _add_value_label(burn_jag_row, "50%")
        self.burn_jaggedness_slider.valueChanged.connect(
            lambda v: self.burn_jaggedness_label.setText(f"{v}%")
        )

        burn_glow_row = _aligned_row(burn_layout, "Glow Intensity:")
        self.burn_glow_intensity_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.burn_glow_intensity_slider.setRange(0, 100)
        self.burn_glow_intensity_slider.setValue(70)
        self.burn_glow_intensity_slider.setToolTip("Warm glow brightness on the burning edge")
        self.burn_glow_intensity_slider.valueChanged.connect(self._save_settings)
        burn_glow_row.addWidget(self.burn_glow_intensity_slider, 1)
        self.burn_glow_intensity_label = _add_value_label(burn_glow_row, "70%")
        self.burn_glow_intensity_slider.valueChanged.connect(
            lambda v: self.burn_glow_intensity_label.setText(f"{v}%")
        )

        burn_char_row = _aligned_row(burn_layout, "Char Width:")
        self.burn_char_width_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.burn_char_width_slider.setRange(10, 100)
        self.burn_char_width_slider.setValue(50)
        self.burn_char_width_slider.setToolTip("Width of the charred/blackened zone behind the burn front")
        self.burn_char_width_slider.valueChanged.connect(self._save_settings)
        burn_char_row.addWidget(self.burn_char_width_slider, 1)
        self.burn_char_width_label = _add_value_label(burn_char_row, "50%")
        self.burn_char_width_slider.valueChanged.connect(
            lambda v: self.burn_char_width_label.setText(f"{v}%")
        )

        burn_color_row = _swatch_row(burn_layout, "Glow Colour:")
        self.burn_glow_color_btn = ColorSwatchButton(
            title="Choose Burn Glow Colour", show_alpha=True, auto_picker=False
        )
        self._burn_glow_color = QColor(255, 140, 30, 255)
        self._apply_burn_glow_color_btn()
        self.burn_glow_color_btn.setFixedSize(60, 24)
        self.burn_glow_color_btn.setToolTip("Primary glow colour on the burning edge")
        self.burn_glow_color_btn.clicked.connect(self._pick_burn_glow_color)
        burn_color_row.addWidget(self.burn_glow_color_btn)
        burn_color_row.addStretch()

        burn_smoke_row = _aligned_row(burn_layout, "", wrap=False)
        self.burn_smoke_check = QCheckBox("Sparks")
        self.burn_smoke_check.setProperty("circleIndicator", True)
        self.burn_smoke_check.setChecked(True)
        self.burn_smoke_check.setToolTip("Enable bright sparks flying off the burn front")
        self.burn_smoke_check.stateChanged.connect(self._save_settings)
        burn_smoke_row.addWidget(self.burn_smoke_check)
        burn_smoke_row.addStretch()

        burn_smoke_density_row = _aligned_row(burn_layout, "Spark Intensity:")
        self.burn_smoke_density_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.burn_smoke_density_slider.setRange(0, 100)
        self.burn_smoke_density_slider.setValue(50)
        self.burn_smoke_density_slider.valueChanged.connect(self._save_settings)
        burn_smoke_density_row.addWidget(self.burn_smoke_density_slider, 1)
        self.burn_smoke_density_label = _add_value_label(burn_smoke_density_row, "50%")
        self.burn_smoke_density_slider.valueChanged.connect(
            lambda v: self.burn_smoke_density_label.setText(f"{v}%")
        )

        burn_ash_row = _aligned_row(burn_layout, "", wrap=False)
        self.burn_ash_check = QCheckBox("Ash Particles")
        self.burn_ash_check.setProperty("circleIndicator", True)
        self.burn_ash_check.setChecked(True)
        self.burn_ash_check.setToolTip("Enable falling ash specks below the burn front")
        self.burn_ash_check.stateChanged.connect(self._save_settings)
        burn_ash_row.addWidget(self.burn_ash_check)
        burn_ash_row.addStretch()

        burn_ash_density_row = _aligned_row(burn_layout, "Ash Density:")
        self.burn_ash_density_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.burn_ash_density_slider.setRange(0, 100)
        self.burn_ash_density_slider.setValue(50)
        self.burn_ash_density_slider.valueChanged.connect(self._save_settings)
        burn_ash_density_row.addWidget(self.burn_ash_density_slider, 1)
        self.burn_ash_density_label = _add_value_label(burn_ash_density_row, "50%")
        self.burn_ash_density_slider.valueChanged.connect(
            lambda v: self.burn_ash_density_label.setText(f"{v}%")
        )

        layout.addWidget(self.burn_group)

        # Transition-settings groups toggled as a set against the SETUP page.
        self._transition_setting_groups = [
            duration_group,
            self.direction_group,
            self.flip_group,
            self.blockspin_group,
            self.blinds_group,
            self.diffuse_group,
            self.ripple_group,
            self.crumble_group,
            self.particle_group,
            self.burn_group,
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

        self.setStyleSheet(
            self.styleSheet() + SPINBOX_STYLE + COMBOBOX_STYLE + CIRCLE_CHECKBOX_STYLE
        )

    # ---- E2 capability SETUP subtab ---------------------------------------

    def _build_setup_page(self) -> QWidget:
        """Build the Transitions SETUP page: activation, Use Random, random pool."""
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(16)

        # Activation module list.
        activation_group = QGroupBox("Transition Modules")
        style_group_box(activation_group)
        activation_layout = QVBoxLayout(activation_group)
        activation_layout.setContentsMargins(0, 12, 0, 0)
        activation_layout.setSpacing(8)

        self._activation_checkboxes = {}
        for name in _TRANSITION_SETTING_NAMES:
            row = QCheckBox(name)
            row.setProperty("circleIndicator", True)
            row.setChecked(True)
            row.toggled.connect(
                lambda checked, n=name: self._on_transition_activation_toggled(n, checked)
            )
            self._activation_checkboxes[name] = row
            activation_layout.addWidget(row)

        action_row = QHBoxLayout()
        action_row.addStretch()
        enable_all = QPushButton("Enable All")
        disable_all = QPushButton("Disable All")
        enable_all.setStyleSheet(_SETUP_ACTION_BUTTON_STYLE)
        disable_all.setStyleSheet(_SETUP_ACTION_BUTTON_STYLE)
        enable_all.clicked.connect(lambda: self._set_all_transition_activation(True))
        disable_all.clicked.connect(lambda: self._set_all_transition_activation(False))
        action_row.addWidget(enable_all)
        action_row.addWidget(disable_all)
        activation_layout.addLayout(action_row)
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
        pool_label.setStyleSheet(PAGE_TITLE_STYLE)
        random_layout.addWidget(pool_label)

        self._pool_checkboxes = {}
        for name in _TRANSITION_SETTING_NAMES:
            row = QCheckBox(name)
            row.setProperty("circleIndicator", True)
            row.toggled.connect(
                lambda checked, n=name: self._on_pool_membership_toggled(n, checked)
            )
            self._pool_checkboxes[name] = row
            random_layout.addWidget(row)

        page_layout.addWidget(random_group)
        return page

    def _on_nav_selected(self, key: str) -> None:
        """Show either the SETUP page or one transition's settings groups."""
        show_setup = key == _SETUP_NAV_KEY
        self._setup_page.setVisible(show_setup)
        for group in getattr(self, "_transition_setting_groups", []):
            group.setVisible(not show_setup)
        if show_setup:
            return
        # Selecting a transition pill drives the internal selection model, which
        # updates the per-transition groups and (via save) the remembered manual
        # transition. Random mode is owned separately by the Use Random checkbox.
        if self.transition_combo.currentText() != key:
            self.transition_combo.setCurrentText(key)
        else:
            self._update_specific_settings()

    def _apply_transition_pill_visibility(self) -> None:
        """Show/hide transition pills and pool rows to match activation."""
        deactivated_current = False
        current = self.transition_combo.currentText()
        for name, button in self._nav_buttons.items():
            if name == _SETUP_NAV_KEY:
                continue
            activated = self._transition_activated(name)
            button.setVisible(activated)
            # The random pool only lists activated transitions.
            pool_row = getattr(self, "_pool_checkboxes", {}).get(name)
            if pool_row is not None:
                pool_row.setVisible(activated)
            if not activated and name == current:
                deactivated_current = True
        if not getattr(self, "_loading", False) and deactivated_current:
            setup_button = self._nav_buttons.get(_SETUP_NAV_KEY)
            if setup_button is not None:
                setup_button.setChecked(True)
            self._on_nav_selected(_SETUP_NAV_KEY)

    def _transition_activated(self, name: str) -> bool:
        checkbox = getattr(self, "_activation_checkboxes", {}).get(name)
        if checkbox is not None:
            return bool(checkbox.isChecked())
        return bool(self._activation_by_type.get(name, True))

    def _on_transition_activation_toggled(self, name: str, checked: bool) -> None:
        self._activation_by_type[name] = bool(checked)
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
        transitions_config = self._settings.get('transitions', {}) or {}
        if not isinstance(transitions_config, dict):
            transitions_config = {}

        # E2.6: normalize legacy state to the single Random authority before the
        # UI reads it — most importantly convert a legacy type="Random" into
        # random_always=True + a concrete manual type, and repair any malformed
        # activation/empty-pool state. Persist when a repair actually happened.
        if normalize_transition_capability_state(transitions_config):
            self._settings.set('transitions', transitions_config)
            self._settings.save()

        canonical_transitions = get_default_settings().get('transitions', {})
        if not isinstance(canonical_transitions, dict):
            canonical_transitions = {}

        # Canonical global default duration matches SettingsManager._set_defaults().
        default_duration_raw = transitions_config.get(
            'duration_ms',
            canonical_transitions.get('duration_ms', 3000),
        )
        try:
            default_duration = int(default_duration_raw)
        except Exception as e:
            logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)
            default_duration = 3000

        durations_cfg = transitions_config.get('durations', {})
        if not isinstance(durations_cfg, dict):
            durations_cfg = {}

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

        pool_cfg = transitions_config.get('pool', {})
        if not isinstance(pool_cfg, dict):
            pool_cfg = {}
        self._pool_by_type = {}
        for name in type_keys:
            if name == "Ripple":
                raw_flag = pool_cfg.get("Ripple", pool_cfg.get("Rain Drops", True))
            else:
                raw_flag = pool_cfg.get(name, True)
            try:
                enabled = SettingsManager.to_bool(raw_flag, True)
            except Exception as e:
                logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)
                enabled = True
            self._pool_by_type[name] = bool(enabled)

        # Application-level activation (E2). Missing => activated (True).
        self._activation_by_type = {
            name: is_transition_activated(transitions_config, name)
            for name in type_keys
        }
        use_random = SettingsManager.to_bool(
            transitions_config.get('random_always', False), False
        )

        # Block signals while we apply settings to avoid recursive saves with stale state
        blockers = []
        for w in [
            getattr(self, 'transition_combo', None),
            getattr(self, 'duration_slider', None),
            getattr(self, 'direction_combo', None),
            getattr(self, 'grid_rows_spin', None),
            getattr(self, 'grid_cols_spin', None),
            getattr(self, 'blockflip_direction_combo', None),
            getattr(self, 'blockspin_direction_combo', None),
            getattr(self, 'block_size_spin', None),
            getattr(self, 'diffuse_shape_combo', None),
            # Blinds widgets
            getattr(self, 'blinds_direction_combo', None),
            getattr(self, 'blinds_feather_slider', None),
            # Ripple widgets
            getattr(self, 'ripple_count_spin', None),
            # Crumble widgets
            getattr(self, 'crumble_piece_count_spin', None),
            getattr(self, 'crumble_complexity_spin', None),
            getattr(self, 'crumble_weight_combo', None),
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
            getattr(self, 'burn_ash_density_slider', None),
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
                transitions_config.get('type', canonical_transitions.get('type', 'Ripple')),
                fallback='Ripple',
            )
            index = self.transition_combo.findText(transition_type)
            if index >= 0:
                self.transition_combo.setCurrentIndex(index)

            duration = self._duration_by_type.get(transition_type, default_duration)
            self.duration_slider.setValue(duration)
            self.duration_value_label.setText(f"{duration} ms")

            # Apply SETUP page state: activation, Use Random, and pool membership.
            for name, checkbox in getattr(self, '_activation_checkboxes', {}).items():
                checkbox.setChecked(bool(self._activation_by_type.get(name, True)))
            for name, checkbox in getattr(self, '_pool_checkboxes', {}).items():
                checkbox.setChecked(bool(self._pool_by_type.get(name, True)))
            if getattr(self, '_use_random_checkbox', None) is not None:
                self._use_random_checkbox.setChecked(bool(use_random))

            # Load per-transition directions (nested)
            slide_cfg = transitions_config.get('slide', {}) if isinstance(transitions_config.get('slide', {}), dict) else {}
            wipe_cfg = transitions_config.get('wipe', {}) if isinstance(transitions_config.get('wipe', {}), dict) else {}
            blockspin_cfg = transitions_config.get('blockspin', {}) if isinstance(transitions_config.get('blockspin', {}), dict) else {}

            slide_dir = slide_cfg.get('direction', 'Random') or 'Random'
            wipe_dir = wipe_cfg.get('direction', 'Random') or 'Random'
            blockspin_dir = blockspin_cfg.get('direction', 'Random') or 'Random'

            self._dir_slide = slide_dir
            self._dir_wipe = wipe_dir
            self._dir_blockspin = blockspin_dir
            
            # Note: GPU acceleration is controlled globally in Display tab
            
            # Load block flip settings - use canonical defaults from defaults.py
            canonical_block_flip = canonical_transitions.get('block_flip', {})
            block_flip = transitions_config.get('block_flip', {})
            self.grid_rows_spin.setValue(block_flip.get('rows', canonical_block_flip.get('rows', 12)))
            self.grid_cols_spin.setValue(block_flip.get('cols', canonical_block_flip.get('cols', 24)))
            blockflip_dir = block_flip.get('direction', 'Random') or 'Random'
            try:
                idx = self.blockflip_direction_combo.findText(blockflip_dir)
                if idx < 0:
                    idx = self.blockflip_direction_combo.findText("Random")
                self.blockflip_direction_combo.setCurrentIndex(max(0, idx))
            except Exception as e:
                logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)

            # Load 3D Block Spins settings
            try:
                idx = self.blockspin_direction_combo.findText(self._dir_blockspin)
                if idx < 0:
                    idx = 0
                self.blockspin_direction_combo.setCurrentIndex(max(0, idx))
            except Exception as e:
                logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)

            # Load diffuse settings - use canonical defaults from defaults.py
            canonical_diffuse = canonical_transitions.get('diffuse', {})
            diffuse = transitions_config.get('diffuse', {})
            self.block_size_spin.setValue(diffuse.get('block_size', canonical_diffuse.get('block_size', 18)))
            shape = diffuse.get('shape', canonical_diffuse.get('shape', 'Rectangle'))
            index = self.diffuse_shape_combo.findText(shape)
            if index >= 0:
                self.diffuse_shape_combo.setCurrentIndex(index)

            # Load blinds settings - use canonical defaults from defaults.py
            canonical_blinds = canonical_transitions.get('blinds', {})
            blinds = transitions_config.get('blinds', {})
            if not isinstance(blinds, dict):
                blinds = {}
            self.blinds_feather_slider.setValue(int(blinds.get('feather', canonical_blinds.get('feather', 2))))
            self.blinds_feather_label.setText(str(self.blinds_feather_slider.value()))
            blinds_dir = blinds.get('direction', canonical_blinds.get('direction', 'Horizontal'))
            try:
                idx = self.blinds_direction_combo.findText(str(blinds_dir))
                if idx < 0:
                    idx = 0
                self.blinds_direction_combo.setCurrentIndex(idx)
            except Exception as e:
                logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)

            # Load ripple settings
            canonical_ripple = canonical_transitions.get('ripple', {})
            ripple = transitions_config.get('ripple', {})
            self.ripple_count_spin.setValue(int(ripple.get('ripple_count', canonical_ripple.get('ripple_count', 3))))

            # Load crumble settings - use canonical defaults from defaults.py
            canonical_crumble = canonical_transitions.get('crumble', {})
            crumble = transitions_config.get('crumble', {})
            self.crumble_piece_count_spin.setValue(crumble.get('piece_count', canonical_crumble.get('piece_count', 14)))
            self.crumble_complexity_spin.setValue(crumble.get('crack_complexity', canonical_crumble.get('crack_complexity', 1.0)))
            weight = crumble.get('weighting', canonical_crumble.get('weighting', 'Random Choice'))
            try:
                idx = self.crumble_weight_combo.findText(weight)
                if idx < 0:
                    idx = 0
                self.crumble_weight_combo.setCurrentIndex(idx)
            except Exception as e:
                logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)

            # Load particle settings - use canonical defaults from defaults.py
            canonical_particle = canonical_transitions.get('particle', {})
            particle = transitions_config.get('particle', {})
            mode = particle.get('mode', canonical_particle.get('mode', 'Converge'))
            idx = self.particle_mode_combo.findText(mode)
            if idx >= 0:
                self.particle_mode_combo.setCurrentIndex(idx)
            direction = particle.get('direction', canonical_particle.get('direction', 'Left to Right'))
            idx = self.particle_direction_combo.findText(direction)
            if idx >= 0:
                self.particle_direction_combo.setCurrentIndex(idx)
            self.particle_radius_spin.setValue(int(particle.get('particle_radius', canonical_particle.get('particle_radius', 10))))
            self.particle_trail_check.setChecked(particle.get('trail_strength', canonical_particle.get('trail_strength', 0.6)) > 0.01)
            self.particle_3d_check.setChecked(particle.get('use_3d_shading', canonical_particle.get('use_3d_shading', True)))
            self.particle_texture_check.setChecked(particle.get('texture_mapping', canonical_particle.get('texture_mapping', True)))
            self.particle_wobble_check.setChecked(particle.get('wobble', canonical_particle.get('wobble', True)))
            self.particle_gloss_spin.setValue(int(particle.get('gloss_size', canonical_particle.get('gloss_size', 72))))
            light_idx = particle.get('light_direction', canonical_particle.get('light_direction', 0))
            if 0 <= light_idx < self.particle_light_combo.count():
                self.particle_light_combo.setCurrentIndex(light_idx)
            self.particle_swirl_turns_spin.setValue(particle.get('swirl_turns', canonical_particle.get('swirl_turns', 3.0)))
            swirl_order_idx = particle.get('swirl_order', canonical_particle.get('swirl_order', 0))
            if 0 <= swirl_order_idx < self.particle_swirl_order_combo.count():
                self.particle_swirl_order_combo.setCurrentIndex(swirl_order_idx)

            # Load burn settings
            canonical_burn = canonical_transitions.get('burn', {})
            burn = transitions_config.get('burn', {})
            if not isinstance(burn, dict):
                burn = {}
            burn_dir = burn.get('direction', canonical_burn.get('direction', 'Left to Right')) or 'Left to Right'
            try:
                idx = self.burn_direction_combo.findText(burn_dir)
                if idx < 0:
                    idx = 0
                self.burn_direction_combo.setCurrentIndex(idx)
            except Exception as e:
                logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)
            jag = int(round(burn.get('jaggedness', canonical_burn.get('jaggedness', 0.5)) * 100))
            self.burn_jaggedness_slider.setValue(max(0, min(100, jag)))
            self.burn_jaggedness_label.setText(f"{self.burn_jaggedness_slider.value()}%")
            glow_i = int(round(burn.get('glow_intensity', canonical_burn.get('glow_intensity', 0.7)) * 100))
            self.burn_glow_intensity_slider.setValue(max(0, min(100, glow_i)))
            self.burn_glow_intensity_label.setText(f"{self.burn_glow_intensity_slider.value()}%")
            char_w = int(round(burn.get('char_width', canonical_burn.get('char_width', 0.5)) * 100))
            self.burn_char_width_slider.setValue(max(10, min(100, char_w)))
            self.burn_char_width_label.setText(f"{self.burn_char_width_slider.value()}%")
            glow_col = burn.get('glow_color', canonical_burn.get('glow_color', [255, 140, 30, 255]))
            if isinstance(glow_col, (list, tuple)) and len(glow_col) >= 3:
                self._burn_glow_color = QColor(int(glow_col[0]), int(glow_col[1]), int(glow_col[2]),
                                               int(glow_col[3]) if len(glow_col) > 3 else 255)
                self._apply_burn_glow_color_btn()
            self.burn_smoke_check.setChecked(bool(burn.get('smoke_enabled', canonical_burn.get('smoke_enabled', True))))
            smoke_d = int(round(burn.get('smoke_density', canonical_burn.get('smoke_density', 0.5)) * 100))
            self.burn_smoke_density_slider.setValue(max(0, min(100, smoke_d)))
            self.burn_smoke_density_label.setText(f"{self.burn_smoke_density_slider.value()}%")
            self.burn_ash_check.setChecked(bool(burn.get('ash_enabled', canonical_burn.get('ash_enabled', True))))
            ash_d = int(round(burn.get('ash_density', canonical_burn.get('ash_density', 0.5)) * 100))
            self.burn_ash_density_slider.setValue(max(0, min(100, ash_d)))
            self.burn_ash_density_label.setText(f"{self.burn_ash_density_slider.value()}%")

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
        """Update visibility of transition-specific settings."""
        transition = self.transition_combo.currentText()

        # Show/hide direction for directional transitions (Slide/Wipe only)
        show_direction = transition in ["Slide", "Wipe"]
        self.direction_group.setVisible(show_direction)

        # Populate direction options per transition
        if show_direction:
            self.direction_combo.blockSignals(True)
            try:
                self.direction_combo.clear()
                if transition == "Slide":
                    # Slide: no diagonals
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
            finally:
                self.direction_combo.blockSignals(False)

        # Show/hide block flip settings
        self.flip_group.setVisible(transition == "Block Puzzle Flip")
        
        # Show/hide diffuse settings
        self.diffuse_group.setVisible(transition == "Diffuse")

        # Show/hide ripple settings
        self.ripple_group.setVisible(transition == "Ripple")

        # Show/hide 3D Block Spins settings
        self.blockspin_group.setVisible(transition == "3D Block Spins")

        # Show/hide Blinds settings
        self.blinds_group.setVisible(transition == "Blinds")
        
        # Show/hide Crumble settings
        self.crumble_group.setVisible(transition == "Crumble")
        
        # Show/hide Particle settings
        self.particle_group.setVisible(transition == "Particle")
        if transition == "Particle":
            self._update_particle_mode_visibility()

        # Show/hide Burn settings
        self.burn_group.setVisible(transition == "Burn")

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

    def _refresh_hw_dependent_options(self) -> None:
        """No-op — renderer is always GL, all transitions available."""
        pass

    def _enforce_gl_only_selection(self) -> None:
        """No-op — renderer is always GL, all transitions available."""
        pass
    
    def _save_settings(self) -> None:
        """Save current settings."""
        cur_type = self.transition_combo.currentText()
        cur_dir = self.direction_combo.currentText()
        # Update in-memory per-type direction
        if cur_type == "Slide":
            self._dir_slide = cur_dir
        elif cur_type == "Wipe":
            self._dir_wipe = cur_dir

        # 3D Block Spins use their own controls; always capture the latest
        # choices from that group.
        try:
            self._dir_blockspin = self.blockspin_direction_combo.currentText() or "Left to Right"
        except Exception as e:
            logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)

        cur_duration = self.duration_slider.value()
        try:
            self._duration_by_type[cur_type] = cur_duration
        except Exception as e:
            logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)

        # Application-level activation + random-mode state are owned by the SETUP
        # page checkboxes (E2.3). Pool membership is owned by the SETUP pool list.
        for name, checkbox in getattr(self, "_activation_checkboxes", {}).items():
            self._activation_by_type[name] = bool(checkbox.isChecked())
        try:
            use_random = bool(self._use_random_checkbox.isChecked())
        except Exception as e:
            logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)
            use_random = False

        # Update blinds feather label
        try:
            self.blinds_feather_label.setText(str(self.blinds_feather_slider.value()))
        except Exception:
            pass

        config = {
            'type': cur_type,
            'duration_ms': cur_duration,
            'block_flip': {
                'rows': self.grid_rows_spin.value(),
                'cols': self.grid_cols_spin.value(),
                'direction': self.blockflip_direction_combo.currentText(),
            },
            'blinds': {
                'feather': self.blinds_feather_slider.value(),
                'direction': self.blinds_direction_combo.currentText(),
            },
            'diffuse': {
                'block_size': self.block_size_spin.value(),
                'shape': self.diffuse_shape_combo.currentText()
            },
            'ripple': {
                'ripple_count': self.ripple_count_spin.value(),
            },
            'crumble': {
                'piece_count': self.crumble_piece_count_spin.value(),
                'crack_complexity': self.crumble_complexity_spin.value(),
                'weighting': self.crumble_weight_combo.currentText(),
            },
            'particle': {
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
            },
            'burn': {
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
                'smoke_enabled': self.burn_smoke_check.isChecked(),
                'smoke_density': self.burn_smoke_density_slider.value() / 100.0,
                'ash_enabled': self.burn_ash_check.isChecked(),
                'ash_density': self.burn_ash_density_slider.value() / 100.0,
            },
            'durations': dict(self._duration_by_type),
            'pool': dict(self._pool_by_type),
            # E2 capability-activation authority + single random-mode authority.
            'activation': dict(self._activation_by_type),
            'random_always': use_random,
            # New nested per-transition direction settings
            'slide': {
                'direction': self._dir_slide,
            },
            'wipe': {
                'direction': self._dir_wipe,
            },
            'blockspin': {
                'direction': self._dir_blockspin,
            },
        }

        # Preserve engine-managed transient random-choice bookkeeping across a
        # wholesale section rewrite (the engine re-derives it each rotation).
        existing = self._settings.get('transitions', {})
        if isinstance(existing, dict):
            for transient_key in ('random_choice', 'last_random_choice'):
                if transient_key in existing:
                    config[transient_key] = existing[transient_key]

        self._settings.set('transitions', config)

        self._settings.save()
        self.transitions_changed.emit()
        
        logger.debug(f"Saved transition settings: {config['type']}")

    def _on_duration_changed(self, value: int) -> None:
        """Update label and persist duration to settings."""
        self.duration_value_label.setText(f"{value} ms")
        try:
            cur_type = self.transition_combo.currentText()
            self._duration_by_type[cur_type] = value
        except Exception as e:
            logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)
        self._save_settings()
