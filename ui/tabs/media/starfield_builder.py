"""Starfield visualizer UI builder — extracted from widgets_tab_media.py."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QSlider, QWidget,
)
from PySide6.QtCore import Qt

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab


def build_starfield_ui(tab: "WidgetsTab", parent_layout: QVBoxLayout) -> None:
    """Build Starfield settings and add to parent_layout."""
    from ui.tabs.widgets_tab import NoWheelSlider

    tab._starfield_settings_container = QWidget()
    star_layout = QVBoxLayout(tab._starfield_settings_container)
    star_layout.setContentsMargins(0, 0, 0, 0)

    star_speed_row = QHBoxLayout()
    star_speed_row.addWidget(QLabel("Travel Speed:"))
    tab.star_travel_speed = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.star_travel_speed.setMinimum(0)
    tab.star_travel_speed.setMaximum(100)
    star_speed_val = int(tab._default_float('spotify_visualizer', 'star_travel_speed', 0.5) * 100)
    tab.star_travel_speed.setValue(star_speed_val)
    tab.star_travel_speed.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.star_travel_speed.setTickInterval(10)
    tab.star_travel_speed.valueChanged.connect(tab._save_settings)
    star_speed_row.addWidget(tab.star_travel_speed)
    tab.star_travel_speed_label = QLabel(f"{star_speed_val / 100.0:.2f}")
    tab.star_travel_speed.valueChanged.connect(
        lambda v: tab.star_travel_speed_label.setText(f"{v / 100.0:.2f}")
    )
    star_speed_row.addWidget(tab.star_travel_speed_label)
    star_layout.addLayout(star_speed_row)

    star_react_row = QHBoxLayout()
    star_react_row.addWidget(QLabel("Bass Reactivity:"))
    tab.star_reactivity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.star_reactivity.setMinimum(0)
    tab.star_reactivity.setMaximum(200)
    star_react_val = int(tab._default_float('spotify_visualizer', 'star_reactivity', 1.0) * 100)
    tab.star_reactivity.setValue(star_react_val)
    tab.star_reactivity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.star_reactivity.setTickInterval(25)
    tab.star_reactivity.valueChanged.connect(tab._save_settings)
    star_react_row.addWidget(tab.star_reactivity)
    tab.star_reactivity_label = QLabel(f"{star_react_val / 100.0:.2f}x")
    tab.star_reactivity.valueChanged.connect(
        lambda v: tab.star_reactivity_label.setText(f"{v / 100.0:.2f}x")
    )
    star_react_row.addWidget(tab.star_reactivity_label)
    star_layout.addLayout(star_react_row)

    nebula_tint_row = QHBoxLayout()
    nebula_tint_row.addWidget(QLabel("Nebula Tint 1:"))
    tab.nebula_tint1_btn = QPushButton("Choose Color...")
    tab.nebula_tint1_btn.clicked.connect(tab._choose_nebula_tint1)
    nebula_tint_row.addWidget(tab.nebula_tint1_btn)
    nebula_tint_row.addWidget(QLabel("Tint 2:"))
    tab.nebula_tint2_btn = QPushButton("Choose Color...")
    tab.nebula_tint2_btn.clicked.connect(tab._choose_nebula_tint2)
    nebula_tint_row.addWidget(tab.nebula_tint2_btn)
    nebula_tint_row.addStretch()
    star_layout.addLayout(nebula_tint_row)

    nebula_speed_row = QHBoxLayout()
    nebula_speed_row.addWidget(QLabel("Nebula Cycle:"))
    tab.nebula_cycle_speed = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.nebula_cycle_speed.setMinimum(0)
    tab.nebula_cycle_speed.setMaximum(100)
    nebula_spd_val = int(tab._default_float('spotify_visualizer', 'nebula_cycle_speed', 0.3) * 100)
    tab.nebula_cycle_speed.setValue(nebula_spd_val)
    tab.nebula_cycle_speed.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.nebula_cycle_speed.setTickInterval(10)
    tab.nebula_cycle_speed.setToolTip("Speed at which nebula colours cycle between Tint 1 and Tint 2. 0 = static.")
    tab.nebula_cycle_speed.valueChanged.connect(tab._save_settings)
    nebula_speed_row.addWidget(tab.nebula_cycle_speed)
    tab.nebula_cycle_speed_label = QLabel(f"{nebula_spd_val}%")
    tab.nebula_cycle_speed.valueChanged.connect(
        lambda v: tab.nebula_cycle_speed_label.setText(f"{v}%")
    )
    nebula_speed_row.addWidget(tab.nebula_cycle_speed_label)
    star_layout.addLayout(nebula_speed_row)

    parent_layout.addWidget(tab._starfield_settings_container)


def build_starfield_growth(tab: "WidgetsTab") -> None:
    """Append height growth slider to the starfield container (called after sine section)."""
    from ui.tabs.widgets_tab import NoWheelSlider

    star_layout = tab._starfield_settings_container.layout()
    star_growth_row = QHBoxLayout()
    star_growth_row.addWidget(QLabel("Card Height:"))
    tab.starfield_growth = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.starfield_growth.setMinimum(100)
    tab.starfield_growth.setMaximum(400)
    star_growth_val = int(tab._default_float('spotify_visualizer', 'starfield_growth', 2.0) * 100)
    tab.starfield_growth.setValue(star_growth_val)
    tab.starfield_growth.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.starfield_growth.setTickInterval(50)
    tab.starfield_growth.valueChanged.connect(tab._save_settings)
    star_growth_row.addWidget(tab.starfield_growth)
    tab.starfield_growth_label = QLabel(f"{star_growth_val / 100.0:.1f}x")
    tab.starfield_growth.valueChanged.connect(
        lambda v: tab.starfield_growth_label.setText(f"{v / 100.0:.1f}x")
    )
    star_growth_row.addWidget(tab.starfield_growth_label)
    star_layout.addLayout(star_growth_row)
