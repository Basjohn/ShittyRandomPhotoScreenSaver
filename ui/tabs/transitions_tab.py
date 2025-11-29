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
    QSpinBox, QGroupBox, QScrollArea, QSlider, QCheckBox
)
from PySide6.QtCore import Signal, Qt

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
        # Per-transition pool membership for random/switch behaviour.
        self._pool_by_type = {}
        self._duration_by_type = {}
        self._setup_ui()
        self._load_settings()
        
        logger.debug("TransitionsTab created")
    
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
            "Crossfade",
            "Slide",
            "Wipe",
            "Peel",              # GL-only, directional
            "Diffuse",
            "Block Puzzle Flip",
            "3D Block Spins",    # GL-only
            "Ripple",            # GL-only (formerly Rain Drops)
            "Warp Dissolve",     # GL-only
            "Claw Marks",        # GL-only
            "Shuffle",           # GL-only
            "Blinds",            # GL-only
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
        self.duration_slider.setRange(100, 10000)  # store milliseconds directly
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
        self.diffuse_shape_combo.addItems(["Rectangle", "Circle", "Diamond", "Plus", "Triangle"])
        self.diffuse_shape_combo.currentTextChanged.connect(self._save_settings)
        shape_row.addWidget(self.diffuse_shape_combo)
        shape_row.addStretch()
        diffuse_layout.addLayout(shape_row)
        
        layout.addWidget(self.diffuse_group)
        
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

        # Canonical global default duration matches SettingsManager._set_defaults().
        default_duration_raw = transitions_config.get('duration_ms', 3000)
        try:
            default_duration = int(default_duration_raw)
        except Exception:
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
            "Claw Marks",
            "Shuffle",
            "Blinds",
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
            except Exception:
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
            except Exception:
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
        ]:
            if w is not None and hasattr(w, 'blockSignals'):
                w.blockSignals(True)
                blockers.append(w)

        try:
            # Load transition type (default to Wipe to match SettingsManager defaults)
            transition_type = transitions_config.get('type', 'Wipe')
            # Map legacy "Rain Drops" type to the new "Ripple" label.
            if transition_type == 'Rain Drops':
                transition_type = 'Ripple'
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
            except Exception:
                pass
            
            # Load per-transition directions (nested)
            slide_cfg = transitions_config.get('slide', {}) if isinstance(transitions_config.get('slide', {}), dict) else {}
            wipe_cfg = transitions_config.get('wipe', {}) if isinstance(transitions_config.get('wipe', {}), dict) else {}
            peel_cfg = transitions_config.get('peel', {}) if isinstance(transitions_config.get('peel', {}), dict) else {}
            blockspin_cfg = transitions_config.get('blockspin', {}) if isinstance(transitions_config.get('blockspin', {}), dict) else {}

            slide_dir = slide_cfg.get('direction', 'Random') or 'Random'
            wipe_dir = wipe_cfg.get('direction', 'Random') or 'Random'
            peel_dir = peel_cfg.get('direction', 'Random') or 'Random'
            blockspin_dir = blockspin_cfg.get('direction', 'Random') or 'Random'

            self._dir_slide = slide_dir
            self._dir_wipe = wipe_dir
            self._dir_peel = peel_dir
            self._dir_blockspin = blockspin_dir
            
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
            
            # Load block flip settings
            block_flip = transitions_config.get('block_flip', {})
            self.grid_rows_spin.setValue(block_flip.get('rows', 12))
            self.grid_cols_spin.setValue(block_flip.get('cols', 24))

            # Load 3D Block Spins settings
            try:
                idx = self.blockspin_direction_combo.findText(self._dir_blockspin)
                if idx < 0:
                    idx = 0
                self.blockspin_direction_combo.setCurrentIndex(max(0, idx))
            except Exception:
                pass

            # Load diffuse settings
            diffuse = transitions_config.get('diffuse', {})
            self.block_size_spin.setValue(diffuse.get('block_size', 18))
            shape = diffuse.get('shape', 'Diamond')
            index = self.diffuse_shape_combo.findText(shape)
            if index >= 0:
                self.diffuse_shape_combo.setCurrentIndex(index)

            # Now that in-memory per-type directions are loaded, update the direction combo
            self._update_specific_settings()

            logger.debug("Loaded transition settings")
        finally:
            for w in blockers:
                try:
                    w.blockSignals(False)
                except Exception:
                    pass
    
    def _on_transition_changed(self, transition: str) -> None:
        """Handle transition type change."""
        # If a GL-only transition was selected while HW is off, revert to Crossfade
        self._enforce_gl_only_selection()
        self._update_specific_settings()
        cur_type = self.transition_combo.currentText()
        try:
            value = self._duration_by_type.get(cur_type, self.duration_slider.value())
        except Exception:
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
                    # Peel: same cardinal directions model as Slide
                    peel_items = [
                        "Left to Right",
                        "Right to Left",
                        "Top to Bottom",
                        "Bottom to Top",
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

    def _refresh_hw_dependent_options(self) -> None:
        """Grey out GL-only transitions when HW acceleration is disabled."""
        try:
            from PySide6.QtCore import Qt
            hw = self._settings.get_bool('display.hw_accel', True)
            gl_only = ["Blinds", "Peel", "3D Block Spins", "Ripple", "Warp Dissolve", "Claw Marks", "Shuffle"]
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
        except Exception:
            pass

    def _enforce_gl_only_selection(self) -> None:
        """If a GL-only transition is selected with HW off, switch to Crossfade and persist."""
        hw = self._settings.get_bool('display.hw_accel', True)
        cur = self.transition_combo.currentText()
        gl_only = {"Blinds", "Peel", "3D Block Spins", "Ripple", "Warp Dissolve", "Claw Marks", "Shuffle"}
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
        except Exception:
            pass

        cur_duration = self.duration_slider.value()
        try:
            self._duration_by_type[cur_type] = cur_duration
        except Exception:
            pass

        # Update in-memory per-type pool membership
        try:
            cur_pool = self.pool_checkbox.isChecked()
        except Exception:
            cur_pool = True
        try:
            self._pool_by_type[cur_type] = bool(cur_pool)
        except Exception:
            pass

        config = {
            'type': cur_type,
            'duration_ms': cur_duration,
            'easing': self.easing_combo.currentText(),
            'random_always': self.random_checkbox.isChecked(),
            'block_flip': {
                'rows': self.grid_rows_spin.value(),
                'cols': self.grid_cols_spin.value()
            },
            'diffuse': {
                'block_size': self.block_size_spin.value(),
                'shape': self.diffuse_shape_combo.currentText()
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
        except Exception:
            pass
        self._save_settings()
