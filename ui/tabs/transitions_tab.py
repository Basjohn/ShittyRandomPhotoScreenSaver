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
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QSpinBox, QDoubleSpinBox, QGroupBox, QScrollArea, QSlider, QCheckBox
)
from PySide6.QtCore import Signal, Qt

from core.settings.defaults import get_default_settings
from core.settings.settings_manager import SettingsManager
from core.logging.logger import get_logger

logger = get_logger(__name__)


class NoWheelSlider(QSlider):
    def wheelEvent(self, event):  # type: ignore[override]
        event.ignore()


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
        self._dir_peel: str = "Random"
        self._dir_blockspin: str = "Left to Right"
        self._dir_blockflip: str = "Center Burst"
        # Per-transition pool membership for random/switch behaviour.
        self._pool_by_type = {}
        self._duration_by_type = {}
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
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollArea > QWidget > QWidget { background: transparent; }
            QScrollArea QWidget { background: transparent; }
        """)

        # Create content widget
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Title
        title = QLabel("Transition Settings")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        layout.addWidget(title)

        # Transition type group
        type_group = QGroupBox("Transition Type")
        type_layout = QVBoxLayout(type_group)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Transition:"))
        self.transition_combo = QComboBox()
        self.transition_combo.addItems([
            "Ripple",            # 1. GL-only (formerly Rain Drops)
            "Wipe",              # 2. Directional
            "3D Block Spins",    # 3. GL-only
            "Diffuse",           # 4. Particle dissolve
            "Slide",             # 5. Directional
            "Crossfade",         # 6. Classic fallback
            "Peel",              # 7. GL-only, directional
            "Block Puzzle Flip", # 8. Tile flip
            "Warp Dissolve",     # 9. GL-only
            "Blinds",            # 10. GL-only
            "Crumble",           # 11. GL-only, falling pieces
            "Particle",          # 12. GL-only, particle balls
        ])
        self.transition_combo.currentTextChanged.connect(self._on_transition_changed)
        type_row.addWidget(self.transition_combo)
        type_row.addStretch()
        type_layout.addLayout(type_row)

        # Random transitions option
        random_row = QHBoxLayout()
        self.random_checkbox = QCheckBox("Always use random transitions")
        self.random_checkbox.stateChanged.connect(self._save_settings)
        random_row.addWidget(self.random_checkbox)
        random_row.addStretch()
        type_layout.addLayout(random_row)

        # Per-transition pool membership: controls whether the selected
        # transition participates in the engine's random rotation and C-key
        # cycling. Explicit selection via the dropdown remains available
        # regardless of this flag.
        pool_row = QHBoxLayout()
        self.pool_checkbox = QCheckBox("Include in switch/random pool")
        self.pool_checkbox.stateChanged.connect(self._save_settings)
        pool_row.addWidget(self.pool_checkbox)
        pool_row.addStretch()
        type_layout.addLayout(pool_row)

        layout.addWidget(type_group)

        # Duration group (slider: short → long)
        duration_group = QGroupBox("Timing")
        duration_layout = QVBoxLayout(duration_group)
        duration_row = QHBoxLayout()
        duration_row.addWidget(QLabel("Duration (short → long):"))
        self.duration_slider = NoWheelSlider(Qt.Orientation.Horizontal)
        self.duration_slider.setRange(100, 15000)  # store milliseconds directly (15s max)
        self.duration_slider.setSingleStep(100)
        self.duration_slider.setPageStep(500)
        self.duration_slider.setValue(1300)  # BUG FIX #5: Increased from 1000ms (30% slower)
        self.duration_slider.valueChanged.connect(self._on_duration_changed)
        duration_row.addWidget(self.duration_slider, 1)
        self.duration_value_label = QLabel("1300 ms")
        duration_row.addWidget(self.duration_value_label)
        duration_row.addStretch()
        duration_layout.addLayout(duration_row)
        layout.addWidget(duration_group)

        # Direction group (for directional transitions)
        self.direction_group = QGroupBox("Direction")
        direction_layout = QVBoxLayout(self.direction_group)

        direction_row = QHBoxLayout()
        direction_row.addWidget(QLabel("Direction:"))
        self.direction_combo = QComboBox()
        # Items are populated dynamically per transition in _update_specific_settings()
        self.direction_combo.currentTextChanged.connect(self._save_settings)
        direction_row.addWidget(self.direction_combo)
        direction_row.addStretch()
        direction_layout.addLayout(direction_row)

        layout.addWidget(self.direction_group)

        # Easing group
        easing_group = QGroupBox("Easing Curve")
        easing_layout = QVBoxLayout(easing_group)

        easing_row = QHBoxLayout()
        easing_row.addWidget(QLabel("Easing:"))
        self.easing_combo = QComboBox()
        self.easing_combo.addItems([
            "Auto",
            "Linear",
            "InQuad", "OutQuad", "InOutQuad",
            "InCubic", "OutCubic", "InOutCubic",
            "InQuart", "OutQuart", "InOutQuart",
            "InExpo", "OutExpo", "InOutExpo",
            "InSine", "OutSine", "InOutSine",
            "InCirc", "OutCirc", "InOutCirc",
            "InBack", "OutBack", "InOutBack"
        ])
        self.easing_combo.currentTextChanged.connect(self._save_settings)
        easing_row.addWidget(self.easing_combo)
        easing_row.addStretch()
        easing_layout.addLayout(easing_row)

        layout.addWidget(easing_group)

        # Block flip specific settings
        self.flip_group = QGroupBox("Block Flip Settings")
        flip_layout = QVBoxLayout(self.flip_group)

        grid_row = QHBoxLayout()
        grid_row.addWidget(QLabel("Grid Size:"))
        self.grid_rows_spin = QSpinBox()
        self.grid_rows_spin.setRange(2, 25)
        self.grid_rows_spin.setValue(4)
        self.grid_rows_spin.setAccelerated(True)
        self.grid_rows_spin.valueChanged.connect(self._save_settings)
        grid_row.addWidget(QLabel("Rows:"))
        grid_row.addWidget(self.grid_rows_spin)
        self.grid_cols_spin = QSpinBox()
        self.grid_cols_spin.setRange(2, 25)
        self.grid_cols_spin.setValue(6)
        self.grid_cols_spin.setAccelerated(True)
        self.grid_cols_spin.valueChanged.connect(self._save_settings)
        grid_row.addWidget(QLabel("Cols:"))
        grid_row.addWidget(self.grid_cols_spin)
        grid_row.addStretch()
        flip_layout.addLayout(grid_row)

        # Block Puzzle Flip direction
        flip_dir_row = QHBoxLayout()
        flip_dir_row.addWidget(QLabel("Direction:"))
        self.blockflip_direction_combo = QComboBox()
        self.blockflip_direction_combo.addItems([
            "Center Burst",
            "Left to Right",
            "Right to Left",
            "Top to Bottom",
            "Bottom to Top",
            "Diagonal TL→BR",
            "Diagonal TR→BL",
            "Random",
        ])
        self.blockflip_direction_combo.currentTextChanged.connect(self._save_settings)
        flip_dir_row.addWidget(self.blockflip_direction_combo)
        flip_dir_row.addStretch()
        flip_layout.addLayout(flip_dir_row)

        layout.addWidget(self.flip_group)

        # 3D Block Spins specific settings (single-slab only, no grid)
        self.blockspin_group = QGroupBox("3D Block Spins Settings")
        blockspin_layout = QVBoxLayout(self.blockspin_group)

        bs_row = QHBoxLayout()
        bs_row.addWidget(QLabel("Direction:"))
        self.blockspin_direction_combo = QComboBox()
        self.blockspin_direction_combo.addItems([
            "Left to Right",
            "Right to Left",
            "Top to Bottom",
            "Bottom to Top",
            "Random",
        ])
        self.blockspin_direction_combo.currentTextChanged.connect(self._save_settings)
        bs_row.addWidget(self.blockspin_direction_combo)
        bs_row.addStretch()
        blockspin_layout.addLayout(bs_row)

        # Experimental diagonal directions (currently disabled due to UV mapping issues)
        # "Diagonal TL→BR",
        # "Diagonal TR→BL",

        layout.addWidget(self.blockspin_group)

        # Diffuse specific settings
        self.diffuse_group = QGroupBox("Diffuse Settings")
        diffuse_layout = QVBoxLayout(self.diffuse_group)

        block_size_row = QHBoxLayout()
        block_size_row.addWidget(QLabel("Block Size (px):"))
        self.block_size_spin = QSpinBox()
        self.block_size_spin.setRange(4, 256)
        self.block_size_spin.setValue(50)
        self.block_size_spin.setAccelerated(True)
        self.block_size_spin.valueChanged.connect(self._save_settings)
        block_size_row.addWidget(self.block_size_spin)
        block_size_row.addStretch()
        diffuse_layout.addLayout(block_size_row)

        shape_row = QHBoxLayout()
        shape_row.addWidget(QLabel("Shape:"))
        self.diffuse_shape_combo = QComboBox()
        # GLSL-backed Diffuse currently supports only Rectangle and Membrane
        # (shaped variants like Circle/Diamond/Plus were removed due to
        # timing/visual issues). Keep the UI in sync with the active paths.
        self.diffuse_shape_combo.addItems(["Rectangle", "Membrane"])
        self.diffuse_shape_combo.currentTextChanged.connect(self._save_settings)
        shape_row.addWidget(self.diffuse_shape_combo)
        shape_row.addStretch()
        diffuse_layout.addLayout(shape_row)

        layout.addWidget(self.diffuse_group)

        # Crumble specific settings
        self.crumble_group = QGroupBox("Crumble Settings")
        crumble_layout = QVBoxLayout(self.crumble_group)

        piece_count_row = QHBoxLayout()
        piece_count_row.addWidget(QLabel("Piece Count:"))
        self.crumble_piece_count_spin = QSpinBox()
        self.crumble_piece_count_spin.setRange(4, 16)
        self.crumble_piece_count_spin.setValue(8)
        self.crumble_piece_count_spin.setAccelerated(True)
        self.crumble_piece_count_spin.valueChanged.connect(self._save_settings)
        piece_count_row.addWidget(self.crumble_piece_count_spin)
        piece_count_row.addStretch()
        crumble_layout.addLayout(piece_count_row)

        complexity_row = QHBoxLayout()
        complexity_row.addWidget(QLabel("Crack Complexity:"))
        self.crumble_complexity_spin = QDoubleSpinBox()
        self.crumble_complexity_spin.setRange(0.5, 2.0)
        self.crumble_complexity_spin.setSingleStep(0.1)
        self.crumble_complexity_spin.setValue(1.0)
        self.crumble_complexity_spin.valueChanged.connect(self._save_settings)
        complexity_row.addWidget(self.crumble_complexity_spin)
        complexity_row.addStretch()
        crumble_layout.addLayout(complexity_row)

        weight_row = QHBoxLayout()
        weight_row.addWidget(QLabel("Fall Weighting:"))
        self.crumble_weight_combo = QComboBox()
        self.crumble_weight_combo.addItems([
            "Top Weighted",
            "Bottom Weighted",
            "Random Weighted",
            "Random Choice",
            "Age Weighted",
        ])
        self.crumble_weight_combo.setCurrentIndex(0)
        self.crumble_weight_combo.currentIndexChanged.connect(self._save_settings)
        weight_row.addWidget(self.crumble_weight_combo)
        weight_row.addStretch()
        crumble_layout.addLayout(weight_row)

        layout.addWidget(self.crumble_group)

        # Blinds specific settings (Phase 4.1)
        self.blinds_group = QGroupBox("Blinds Settings")
        blinds_layout = QVBoxLayout(self.blinds_group)

        feather_row = QHBoxLayout()
        feather_row.addWidget(QLabel("Edge Feather:"))
        self.blinds_feather_spin = QSpinBox()
        self.blinds_feather_spin.setRange(0, 10)
        self.blinds_feather_spin.setValue(2)
        self.blinds_feather_spin.setSuffix(" px")
        self.blinds_feather_spin.setToolTip("Softness of slat edges (0 = sharp, 10 = very soft)")
        self.blinds_feather_spin.valueChanged.connect(self._save_settings)
        feather_row.addWidget(self.blinds_feather_spin)
        feather_row.addStretch()
        blinds_layout.addLayout(feather_row)

        layout.addWidget(self.blinds_group)

        # Peel specific settings
        self.peel_group = QGroupBox("Peel Settings")
        peel_layout = QVBoxLayout(self.peel_group)

        strips_row = QHBoxLayout()
        strips_row.addWidget(QLabel("Strip Count:"))
        self.peel_strips_spin = QSpinBox()
        self.peel_strips_spin.setRange(4, 32)
        self.peel_strips_spin.setValue(12)
        self.peel_strips_spin.setToolTip("Number of strips in the peel effect (4-32)")
        self.peel_strips_spin.valueChanged.connect(self._save_settings)
        strips_row.addWidget(self.peel_strips_spin)
        strips_row.addStretch()
        peel_layout.addLayout(strips_row)

        layout.addWidget(self.peel_group)

        # Particle specific settings
        self.particle_group = QGroupBox("Particle Settings")
        particle_layout = QVBoxLayout(self.particle_group)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self.particle_mode_combo = QComboBox()
        self.particle_mode_combo.addItems(["Directional", "Swirl", "Converge", "Random"])
        self.particle_mode_combo.currentIndexChanged.connect(self._on_particle_mode_changed)
        self.particle_mode_combo.currentIndexChanged.connect(self._save_settings)
        mode_row.addWidget(self.particle_mode_combo)
        mode_row.addStretch()
        particle_layout.addLayout(mode_row)

        direction_row = QHBoxLayout()
        direction_row.addWidget(QLabel("Direction:"))
        self.particle_direction_combo = QComboBox()
        self.particle_direction_combo.addItems([
            "Left to Right",
            "Right to Left",
            "Top to Bottom",
            "Bottom to Top",
            "Top-Left to Bottom-Right",
            "Top-Right to Bottom-Left",
            "Bottom-Left to Top-Right",
            "Bottom-Right to Top-Left",
            "Random Direction",
            "Random Placement",
        ])
        self.particle_direction_combo.currentIndexChanged.connect(self._save_settings)
        direction_row.addWidget(self.particle_direction_combo)
        direction_row.addStretch()
        particle_layout.addLayout(direction_row)

        radius_row = QHBoxLayout()
        radius_row.addWidget(QLabel("Particle Size:"))
        self.particle_radius_spin = QSpinBox()
        self.particle_radius_spin.setRange(8, 64)
        self.particle_radius_spin.setValue(24)
        self.particle_radius_spin.setSuffix(" px")
        self.particle_radius_spin.valueChanged.connect(self._save_settings)
        radius_row.addWidget(self.particle_radius_spin)
        radius_row.addStretch()
        particle_layout.addLayout(radius_row)

        trail_row = QHBoxLayout()
        self.particle_trail_check = QCheckBox("Motion Trail")
        self.particle_trail_check.setChecked(True)
        self.particle_trail_check.stateChanged.connect(self._save_settings)
        trail_row.addWidget(self.particle_trail_check)
        trail_row.addStretch()
        particle_layout.addLayout(trail_row)

        shading_row = QHBoxLayout()
        self.particle_3d_check = QCheckBox("3D Ball Shading")
        self.particle_3d_check.setChecked(True)
        self.particle_3d_check.stateChanged.connect(self._save_settings)
        shading_row.addWidget(self.particle_3d_check)
        shading_row.addStretch()
        particle_layout.addLayout(shading_row)

        texture_row = QHBoxLayout()
        self.particle_texture_check = QCheckBox("Map Image to Particles")
        self.particle_texture_check.setChecked(True)
        self.particle_texture_check.stateChanged.connect(self._save_settings)
        texture_row.addWidget(self.particle_texture_check)
        texture_row.addStretch()
        particle_layout.addLayout(texture_row)

        wobble_row = QHBoxLayout()
        self.particle_wobble_check = QCheckBox("Wobble on Arrival")
        self.particle_wobble_check.setChecked(False)
        self.particle_wobble_check.stateChanged.connect(self._save_settings)
        wobble_row.addWidget(self.particle_wobble_check)
        wobble_row.addStretch()
        particle_layout.addLayout(wobble_row)

        # Gloss/specular settings
        gloss_row = QHBoxLayout()
        gloss_row.addWidget(QLabel("Gloss Sharpness:"))
        self.particle_gloss_spin = QSpinBox()
        self.particle_gloss_spin.setRange(16, 128)
        self.particle_gloss_spin.setValue(64)
        self.particle_gloss_spin.setToolTip("Higher = smaller/sharper specular highlight")
        self.particle_gloss_spin.valueChanged.connect(self._save_settings)
        gloss_row.addWidget(self.particle_gloss_spin)
        gloss_row.addStretch()
        particle_layout.addLayout(gloss_row)

        light_row = QHBoxLayout()
        light_row.addWidget(QLabel("Light Direction:"))
        self.particle_light_combo = QComboBox()
        self.particle_light_combo.addItems([
            "Top-Left",
            "Top-Right",
            "Center",
            "Bottom-Left",
            "Bottom-Right",
        ])
        self.particle_light_combo.currentIndexChanged.connect(self._save_settings)
        light_row.addWidget(self.particle_light_combo)
        light_row.addStretch()
        particle_layout.addLayout(light_row)

        # Swirl-specific settings
        swirl_turns_row = QHBoxLayout()
        swirl_turns_row.addWidget(QLabel("Swirl Turns:"))
        self.particle_swirl_turns_spin = QDoubleSpinBox()
        self.particle_swirl_turns_spin.setRange(0.5, 5.0)
        self.particle_swirl_turns_spin.setSingleStep(0.5)
        self.particle_swirl_turns_spin.setValue(2.0)
        self.particle_swirl_turns_spin.valueChanged.connect(self._save_settings)
        swirl_turns_row.addWidget(self.particle_swirl_turns_spin)
        swirl_turns_row.addStretch()
        particle_layout.addLayout(swirl_turns_row)

        swirl_order_row = QHBoxLayout()
        swirl_order_row.addWidget(QLabel("Build Order:"))
        self.particle_swirl_order_combo = QComboBox()
        self.particle_swirl_order_combo.addItems([
            "Typical",
            "Center Outward",
            "Edges Inward",
        ])
        self.particle_swirl_order_combo.setToolTip("How particles fill in during swirl mode")
        self.particle_swirl_order_combo.currentIndexChanged.connect(self._save_settings)
        swirl_order_row.addWidget(self.particle_swirl_order_combo)
        swirl_order_row.addStretch()
        particle_layout.addLayout(swirl_order_row)

        layout.addWidget(self.particle_group)

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

        # Improve +/- button clarity and feedback on spin boxes
        self.setStyleSheet(
            self.styleSheet() + """
            QSpinBox, QDoubleSpinBox {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding-right: 28px; /* more space for larger buttons */
                min-height: 24px;
            }
            QSpinBox::up-button, QDoubleSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 24px;
                height: 12px;
                background: #2a2a2a;
                border-left: 1px solid #3a3a3a;
                border-top: 1px solid #3a3a3a;
                border-right: 1px solid #3a3a3a;
                border-bottom: 1px solid #3a3a3a;
                margin: 0px;
            }
            QSpinBox::down-button, QDoubleSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 24px;
                height: 12px;
                background: #2a2a2a;
                border-left: 1px solid #3a3a3a;
                border-right: 1px solid #3a3a3a;
                border-bottom: 1px solid #3a3a3a;
                margin: 0px;
            }
            QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
            QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
                background: #3a3a3a;
            }
            QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
            QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {
                background: #505050;
            }
            QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
                image: none;
                width: 0px;
                height: 0px;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-bottom: 6px solid #ffffff;
                margin-top: 2px;
            }
            QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
                image: none;
                width: 0px;
                height: 0px;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #ffffff;
                margin-bottom: 2px;
            }
            """
        )

    def _load_settings(self) -> None:
        """Load settings from settings manager."""
        transitions_config = self._settings.get('transitions', {}) or {}
        if not isinstance(transitions_config, dict):
            transitions_config = {}

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

        type_keys = [
            "Crossfade",
            "Slide",
            "Wipe",
            "Peel",
            "Diffuse",
            "Block Puzzle Flip",
            "3D Block Spins",
            "Ripple",       # UI label for the former Rain Drops transition
            "Warp Dissolve",
            "Blinds",
            "Crumble",
            "Particle",
        ]
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

        # Block signals while we apply settings to avoid recursive saves with stale state
        blockers = []
        for w in [
            getattr(self, 'transition_combo', None),
            getattr(self, 'random_checkbox', None),
            getattr(self, 'pool_checkbox', None),
            getattr(self, 'duration_slider', None),
            getattr(self, 'direction_combo', None),
            getattr(self, 'easing_combo', None),
            getattr(self, 'grid_rows_spin', None),
            getattr(self, 'grid_cols_spin', None),
            getattr(self, 'blockspin_direction_combo', None),
            getattr(self, 'block_size_spin', None),
            getattr(self, 'diffuse_shape_combo', None),
            # Crumble widgets
            getattr(self, 'crumble_piece_count_spin', None),
            getattr(self, 'crumble_complexity_spin', None),
            getattr(self, 'crumble_weight_combo', None),
            # Blinds widgets (Phase 4.1)
            getattr(self, 'blinds_feather_spin', None),
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
        ]:
            if w is not None and hasattr(w, 'blockSignals'):
                w.blockSignals(True)
                blockers.append(w)

        try:
            # Load transition type (default to Wipe to match SettingsManager defaults)
            transition_type = transitions_config.get('type', canonical_transitions.get('type', 'Ripple'))
            # Map legacy labels to their modern equivalents.
            if transition_type == 'Rain Drops':
                transition_type = 'Ripple'
            elif transition_type == 'Claw Marks':
                # Claw Marks was removed as a transition; treat any saved
                # configuration as Crossfade for backwards compatibility.
                transition_type = 'Crossfade'
            index = self.transition_combo.findText(transition_type)
            if index >= 0:
                self.transition_combo.setCurrentIndex(index)

            duration = self._duration_by_type.get(transition_type, default_duration)
            self.duration_slider.setValue(duration)
            self.duration_value_label.setText(f"{duration} ms")

            # Load per-transition pool membership for the current type
            current_pool = self._pool_by_type.get(transition_type, True)
            try:
                self.pool_checkbox.setChecked(bool(current_pool))
            except Exception as e:
                logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)

            # Load per-transition directions (nested)
            slide_cfg = transitions_config.get('slide', {}) if isinstance(transitions_config.get('slide', {}), dict) else {}
            wipe_cfg = transitions_config.get('wipe', {}) if isinstance(transitions_config.get('wipe', {}), dict) else {}
            peel_cfg = transitions_config.get('peel', {}) if isinstance(transitions_config.get('peel', {}), dict) else {}
            blockspin_cfg = transitions_config.get('blockspin', {}) if isinstance(transitions_config.get('blockspin', {}), dict) else {}

            blockflip_cfg = transitions_config.get('block_flip', {}) if isinstance(transitions_config.get('block_flip', {}), dict) else {}

            slide_dir = slide_cfg.get('direction', 'Random') or 'Random'
            wipe_dir = wipe_cfg.get('direction', 'Random') or 'Random'
            peel_dir = peel_cfg.get('direction', 'Random') or 'Random'
            blockspin_dir = blockspin_cfg.get('direction', 'Random') or 'Random'
            blockflip_dir = blockflip_cfg.get('direction', 'Center Burst') or 'Center Burst'

            self._dir_slide = slide_dir
            self._dir_wipe = wipe_dir
            self._dir_peel = peel_dir
            self._dir_blockspin = blockspin_dir
            self._dir_blockflip = blockflip_dir

            # Load easing
            easing = transitions_config.get('easing', 'Auto')
            index = self.easing_combo.findText(easing)
            if index >= 0:
                self.easing_combo.setCurrentIndex(index)

            # Load random transitions flag (prefer nested config)
            rnd = transitions_config.get('random_always', False)
            rnd = SettingsManager.to_bool(rnd, False)
            self.random_checkbox.setChecked(rnd)

            # Note: GPU acceleration is controlled globally in Display tab

            # Load block flip settings - use canonical defaults from defaults.py
            canonical_block_flip = canonical_transitions.get('block_flip', {})
            block_flip = transitions_config.get('block_flip', {})
            self.grid_rows_spin.setValue(block_flip.get('rows', canonical_block_flip.get('rows', 12)))
            self.grid_cols_spin.setValue(block_flip.get('cols', canonical_block_flip.get('cols', 24)))

            # Load block flip direction
            try:
                idx = self.blockflip_direction_combo.findText(self._dir_blockflip)
                if idx < 0:
                    idx = 0
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

            # Load blinds settings (Phase 4.1)
            canonical_blinds = canonical_transitions.get('blinds', {})
            blinds = transitions_config.get('blinds', {})
            self.blinds_feather_spin.setValue(blinds.get('feather', canonical_blinds.get('feather', 2)))

            # Load peel settings
            canonical_peel = canonical_transitions.get('peel', {})
            peel = transitions_config.get('peel', {})
            self.peel_strips_spin.setValue(peel.get('strips', canonical_peel.get('strips', 12)))

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

        # Update pool checkbox to reflect stored membership for this type
        try:
            self.pool_checkbox.blockSignals(True)
            enabled = self._pool_by_type.get(cur_type, True)
            self.pool_checkbox.setChecked(bool(enabled))
        finally:
            self.pool_checkbox.blockSignals(False)

        self._save_settings()

    def _update_specific_settings(self) -> None:
        """Update visibility of transition-specific settings."""
        transition = self.transition_combo.currentText()

        # Show/hide direction for directional transitions (Slide/Wipe/Peel only)
        show_direction = transition in ["Slide", "Wipe", "Peel"]
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
                elif transition == "Peel":
                    # Peel: cardinal + diagonal directions
                    peel_items = [
                        "Left to Right",
                        "Right to Left",
                        "Top to Bottom",
                        "Bottom to Top",
                        "Diagonal TL→BR",
                        "Diagonal TR→BL",
                        "Random",
                    ]
                    self.direction_combo.addItems(peel_items)
                    idx = self.direction_combo.findText(self._dir_peel)
                    if idx < 0:
                        idx = self.direction_combo.findText("Random") if self._dir_peel == "Random" else 0
                    self.direction_combo.setCurrentIndex(max(0, idx))
            finally:
                self.direction_combo.blockSignals(False)

        # Show/hide block flip settings
        self.flip_group.setVisible(transition == "Block Puzzle Flip")

        # Show/hide diffuse settings
        self.diffuse_group.setVisible(transition == "Diffuse")

        # Show/hide 3D Block Spins settings
        self.blockspin_group.setVisible(transition == "3D Block Spins")

        # Show/hide Crumble settings
        self.crumble_group.setVisible(transition == "Crumble")

        # Show/hide Blinds settings (Phase 4.1)
        self.blinds_group.setVisible(transition == "Blinds")

        # Show/hide Peel settings
        self.peel_group.setVisible(transition == "Peel")

        # Show/hide Particle settings
        self.particle_group.setVisible(transition == "Particle")
        if transition == "Particle":
            self._update_particle_mode_visibility()

    def _on_particle_mode_changed(self, index: int) -> None:
        """Handle particle mode change - show/hide direction vs swirl settings."""
        self._update_particle_mode_visibility()

    def _update_particle_mode_visibility(self) -> None:
        """Update visibility of particle mode-specific settings."""
        mode = self.particle_mode_combo.currentText()
        is_directional = mode == "Directional"
        is_swirl = mode == "Swirl"
        # Direction only applies to Directional mode (Converge/Random auto-select direction)
        # Converge mode particles always converge to center regardless of direction setting
        self.particle_direction_combo.setEnabled(is_directional)
        # Swirl settings only apply to Swirl mode
        self.particle_swirl_turns_spin.setEnabled(is_swirl)
        self.particle_swirl_order_combo.setEnabled(is_swirl)

    def _refresh_hw_dependent_options(self) -> None:
        """Grey out GL-only transitions when HW acceleration is disabled."""
        try:
            from PySide6.QtCore import Qt
            hw = self._settings.get_bool('display.hw_accel', True)
            gl_only = ["Blinds", "Peel", "3D Block Spins", "Ripple", "Warp Dissolve", "Crumble", "Particle"]
            for name in gl_only:
                idx = self.transition_combo.findText(name)
                if idx >= 0:
                    self.transition_combo.setItemData(
                        idx,
                        True if hw else False,
                        Qt.ItemDataRole.EnabledRole
                    )
                    self.transition_combo.setItemData(
                        idx,
                        "Requires GPU acceleration",
                        Qt.ItemDataRole.ToolTipRole
                    )
            # If HW is off and currently selected is GL-only, force Crossfade
            if not hw:
                self._enforce_gl_only_selection()
        except Exception as e:
            logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)

    def _enforce_gl_only_selection(self) -> None:
        """If a GL-only transition is selected with HW off, switch to Crossfade and persist."""
        hw = self._settings.get_bool('display.hw_accel', True)
        cur = self.transition_combo.currentText()
        gl_only = {"Blinds", "Peel", "3D Block Spins", "Ripple", "Warp Dissolve", "Crumble", "Particle"}
        if cur in gl_only and not hw:
            idx = self.transition_combo.findText("Crossfade")
            if idx >= 0:
                self.transition_combo.blockSignals(True)
                try:
                    self.transition_combo.setCurrentIndex(idx)
                finally:
                    self.transition_combo.blockSignals(False)
                self._save_settings()
        if not hw:
            cached_choice = self._settings.get('transitions.random_choice', None)
            if isinstance(cached_choice, str) and cached_choice in gl_only:
                self._settings.remove('transitions.random_choice')
                self._settings.remove('transitions.last_random_choice')

    def _save_settings(self) -> None:
        """Save current settings."""
        cur_type = self.transition_combo.currentText()
        cur_dir = self.direction_combo.currentText()
        # Update in-memory per-type direction
        if cur_type == "Slide":
            self._dir_slide = cur_dir
        elif cur_type == "Wipe":
            self._dir_wipe = cur_dir
        elif cur_type == "Peel":
            self._dir_peel = cur_dir

        # 3D Block Spins use their own controls; always capture the latest
        # choices from that group.
        try:
            self._dir_blockspin = self.blockspin_direction_combo.currentText() or "Left to Right"
        except Exception as e:
            logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)

        # Block Puzzle Flip direction
        try:
            self._dir_blockflip = self.blockflip_direction_combo.currentText() or "Center Burst"
        except Exception as e:
            logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)

        cur_duration = self.duration_slider.value()
        try:
            self._duration_by_type[cur_type] = cur_duration
        except Exception as e:
            logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)

        # Update in-memory per-type pool membership
        try:
            cur_pool = self.pool_checkbox.isChecked()
        except Exception as e:
            logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)
            cur_pool = True
        try:
            self._pool_by_type[cur_type] = bool(cur_pool)
        except Exception as e:
            logger.debug("[TRANSITIONS_TAB] Exception suppressed: %s", e)

        config = {
            'type': cur_type,
            'duration_ms': cur_duration,
            'easing': self.easing_combo.currentText(),
            'random_always': self.random_checkbox.isChecked(),
            'block_flip': {
                'rows': self.grid_rows_spin.value(),
                'cols': self.grid_cols_spin.value(),
                'direction': self._dir_blockflip,
            },
            'diffuse': {
                'block_size': self.block_size_spin.value(),
                'shape': self.diffuse_shape_combo.currentText()
            },
            'crumble': {
                'piece_count': self.crumble_piece_count_spin.value(),
                'crack_complexity': self.crumble_complexity_spin.value(),
                'weighting': self.crumble_weight_combo.currentText(),
            },
            'blinds': {
                'feather': self.blinds_feather_spin.value(),
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
            'durations': dict(self._duration_by_type),
            'pool': dict(self._pool_by_type),
            # New nested per-transition direction settings
            'slide': {
                'direction': self._dir_slide,
            },
            'wipe': {
                'direction': self._dir_wipe,
            },
            'peel': {
                'direction': self._dir_peel,
                'strips': self.peel_strips_spin.value(),
            },
            'blockspin': {
                'direction': self._dir_blockspin,
            },
        }

        self._settings.set('transitions', config)

        if not config['random_always']:
            # Manual selection requires clearing any cached random choice so DisplayWidget honors explicit type
            self._settings.remove('transitions.random_choice')
            self._settings.remove('transitions.last_random_choice')

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
