"""Blob visualizer UI builder — extracted from widgets_tab_media.py."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QSlider, QWidget,
)
from PySide6.QtCore import Qt

from core.settings.visualizer_blob_contract import (
    BLOB_TYPE_SHAPED,
    normalize_blob_type,
)
from ui.styled_popup import ColorSwatchButton
from ui.tabs.media.blob_mighty_builder import build_blob_mighty_controls
from ui.tabs.media.blob_shaped_builder import build_blob_shaped_controls
from ui.tabs.media.builder_scaffold import (
    add_builder_swatch_row,
    bind_color_button,
    bind_setting_signal,
    build_collapsible_bucket,
    build_mode_scaffold,
)
from ui.tabs.shared_styles import (
    add_aligned_row_widget as shared_add_aligned_row_widget,
)
from ui.widgets import StyledComboBox

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab


def build_blob_ui(tab: "WidgetsTab", parent_layout: QVBoxLayout) -> None:
    """Build Blob settings and add to parent_layout."""
    from ui.tabs.widgets_tab import NoWheelSlider

    LABEL_WIDTH = 140
    tab._blob_label_width = LABEL_WIDTH

    scaffold = build_mode_scaffold(
        tab,
        parent_layout,
        mode_key="blob",
        settings_container_attr="_blob_settings_container",
        preset_slider_attr="_blob_preset_slider",
        normal_attr="_blob_normal",
        advanced_host_attr="_blob_advanced_host",
        advanced_toggle_attr="_blob_adv_toggle",
        advanced_helper_attr="_blob_adv_helper",
        advanced_attr="_blob_advanced",
    )
    _blob_layout = scaffold.layout  # noqa: F841 — held by scaffold
    normal_layout = scaffold.normal_layout
    adv_layout = scaffold.advanced_layout

    def _make_aligned_row(target_layout: QVBoxLayout, label_text: str) -> tuple[QWidget, QHBoxLayout]:
        row_widget, inner, _ = shared_add_aligned_row_widget(
            target_layout,
            label_text,
            label_width=LABEL_WIDTH,
        )
        return row_widget, inner

    def _swatch_row(label_text: str) -> tuple[QWidget, QHBoxLayout]:
        row_widget, inner, _ = add_builder_swatch_row(
            appearance_bucket,
            label_text,
            label_width=LABEL_WIDTH,
        )
        return row_widget, inner

    _, type_bucket = build_collapsible_bucket(
        tab,
        normal_layout,
        mode_key="blob",
        bucket_key="type",
        title="Blob Type",
        helper_text="Mighty and Shaped Blob keep separate creative controls and preset ownership.",
        default_expanded=True,
    )
    _, body_bucket = build_collapsible_bucket(
        tab,
        normal_layout,
        mode_key="blob",
        bucket_key="body",
        title="Body",
        helper_text="Body size response controls still apply when hidden.",
        default_expanded=True,
    )
    _, appearance_bucket = build_collapsible_bucket(
        tab,
        normal_layout,
        mode_key="blob",
        bucket_key="appearance",
        title="Appearance",
        helper_text="Blob fill and edge colors still apply when hidden.",
        default_expanded=True,
    )
    _, layout_bucket = build_collapsible_bucket(
        tab,
        normal_layout,
        mode_key="blob",
        bucket_key="layout",
        title="Layout",
        helper_text="Blob card/layout sizing still applies when hidden.",
        default_expanded=True,
    )
    _, glow_bucket = build_collapsible_bucket(
        tab,
        normal_layout,
        mode_key="blob",
        bucket_key="glow",
        title="Glow",
        helper_text="Glow controls still apply when hidden.",
        default_expanded=True,
    )
    _, ghost_bucket = build_collapsible_bucket(
        tab,
        adv_layout,
        mode_key="blob",
        bucket_key="ghost",
        title="Ghost",
        helper_text="Ghost controls still apply when hidden.",
        default_expanded=True,
    )

    def _body_row(label_text: str) -> tuple[QWidget, QHBoxLayout]:
        return _make_aligned_row(body_bucket, label_text)

    def _glow_row(label_text: str) -> tuple[QWidget, QHBoxLayout]:
        return _make_aligned_row(glow_bucket, label_text)

    def _ghost_bucket_row(label_text: str) -> tuple[QWidget, QHBoxLayout]:
        return _make_aligned_row(ghost_bucket, label_text)

    type_row, type_row_layout = _make_aligned_row(type_bucket, "Blob Type:")
    tab._blob_type_row = type_row
    tab.blob_type_combo = StyledComboBox()
    tab.blob_type_combo.addItems(["Mighty Blob", "Shaped Blob"])
    default_blob_type = normalize_blob_type(
        tab._default_str("spotify_visualizer", "blob_type", "mighty"),
        legacy_shaper_enabled=tab._default_bool(
            "spotify_visualizer",
            "blob_shaper_enabled",
            False,
        ),
    )
    tab.blob_type_combo.setCurrentIndex(1 if default_blob_type == BLOB_TYPE_SHAPED else 0)
    tab.blob_type_combo.setToolTip(
        "Mighty Blob is the freeform organic body; Shaped Blob follows an authored contour."
    )
    bind_setting_signal(tab, tab.blob_type_combo.currentIndexChanged, auto_switch=True)
    type_row_layout.addWidget(tab.blob_type_combo)
    type_row_layout.addStretch()

    build_blob_mighty_controls(tab, type_bucket, label_width=LABEL_WIDTH)
    build_blob_shaped_controls(tab, type_bucket, label_width=LABEL_WIDTH)

    def _update_blob_type_controls(*_args) -> None:
        shaped = tab.blob_type_combo.currentIndex() == 1
        tab._blob_mighty_container.setVisible(not shaped)
        tab._blob_mighty_container.setEnabled(not shaped)
        tab._blob_shaped_container.setVisible(shaped)
        tab._blob_shaped_container.setEnabled(shaped)

    tab._update_blob_type_controls = _update_blob_type_controls
    tab.blob_type_combo.currentIndexChanged.connect(_update_blob_type_controls)
    _update_blob_type_controls()

    pulse_widget, pulse_layout = _body_row("Body Response:")
    tab._blob_pulse_row = pulse_widget
    tab.blob_pulse = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_pulse.setMinimum(0)
    tab.blob_pulse.setMaximum(200)
    pulse_val = int(tab._default_float('spotify_visualizer', 'blob_pulse', 1.0) * 100)
    tab.blob_pulse.setValue(pulse_val)
    tab.blob_pulse.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_pulse.setTickInterval(25)
    tab.blob_pulse_label = QLabel(f"{pulse_val / 100.0:.2f}x")
    bind_setting_signal(
        tab,
        tab.blob_pulse.valueChanged,
        updater=lambda v: tab.blob_pulse_label.setText(f"{v / 100.0:.2f}x"),
        auto_switch=True,
    )
    pulse_layout.addWidget(tab.blob_pulse)
    pulse_layout.addWidget(tab.blob_pulse_label)

    def _ms_label(ms: int) -> str:
        return f"{ms / 1000:.2f}s"

    pulse_release_row, pulse_release_layout = _body_row("Body Release:")
    tab._blob_pulse_release_row = pulse_release_row
    tab.blob_pulse_release_ms = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_pulse_release_ms.setMinimum(60)
    tab.blob_pulse_release_ms.setMaximum(1500)
    blob_pulse_release_val = tab._default_int('spotify_visualizer', 'blob_pulse_release_ms', 220)
    tab.blob_pulse_release_ms.setValue(max(60, min(1500, blob_pulse_release_val)))
    tab.blob_pulse_release_ms.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_pulse_release_ms.setTickInterval(50)
    tab.blob_pulse_release_ms.setToolTip(
        "Controls how quickly whole-body pulse size settles back after a hit."
    )
    tab.blob_pulse_release_ms_label = QLabel(_ms_label(tab.blob_pulse_release_ms.value()))
    bind_setting_signal(
        tab,
        tab.blob_pulse_release_ms.valueChanged,
        updater=lambda v: tab.blob_pulse_release_ms_label.setText(_ms_label(v)),
        auto_switch=True,
    )
    pulse_release_layout.addWidget(tab.blob_pulse_release_ms)
    pulse_release_layout.addWidget(tab.blob_pulse_release_ms_label)

    fill_widget, fill_layout = _swatch_row("Fill Color:")
    tab.blob_fill_color_btn = ColorSwatchButton(title="Choose Blob Fill Color")
    bind_color_button(
        tab,
        tab.blob_fill_color_btn,
        '_blob_color',
        auto_switch=True,
        initial_color=getattr(tab, '_blob_color', None),
    )
    fill_layout.addWidget(tab.blob_fill_color_btn)
    fill_layout.addStretch()

    edge_widget, edge_layout = _swatch_row("Edge Color:")
    tab.blob_edge_color_btn = ColorSwatchButton(title="Choose Blob Edge Color")
    bind_color_button(
        tab,
        tab.blob_edge_color_btn,
        '_blob_edge_color',
        auto_switch=True,
        initial_color=getattr(tab, '_blob_edge_color', None),
    )
    edge_layout.addWidget(tab.blob_edge_color_btn)
    edge_layout.addStretch()

    outline_widget, outline_layout = _swatch_row("Outline Color:")
    tab.blob_outline_color_btn = ColorSwatchButton(title="Choose Blob Outline Color")
    bind_color_button(
        tab,
        tab.blob_outline_color_btn,
        '_blob_outline_color',
        auto_switch=True,
        initial_color=getattr(tab, '_blob_outline_color', None),
    )
    outline_layout.addWidget(tab.blob_outline_color_btn)
    outline_layout.addStretch()

    inward_liquid_enabled_row_w, inward_liquid_enabled_row = _swatch_row("Inward Liquid:")
    tab._blob_inward_liquid_enabled_row = inward_liquid_enabled_row_w
    tab.blob_inward_liquid_enabled = QCheckBox("Enable")
    tab.blob_inward_liquid_enabled.setProperty("circleIndicator", True)
    tab.blob_inward_liquid_enabled.setChecked(
        tab._default_bool('spotify_visualizer', 'blob_inward_liquid_enabled', False)
    )
    tab.blob_inward_liquid_enabled.setToolTip(
        "Optional contour-following inner liquid layer. It stays secondary to the main blob body."
    )
    bind_setting_signal(tab, tab.blob_inward_liquid_enabled.stateChanged, auto_switch=True)
    inward_liquid_enabled_row.addWidget(tab.blob_inward_liquid_enabled)
    inward_liquid_enabled_row.addStretch()

    inward_liquid_color_row, inward_liquid_color_layout = _swatch_row("Inward Liquid Color:")
    tab._blob_inward_liquid_color_row = inward_liquid_color_row
    tab.blob_inward_liquid_color_btn = ColorSwatchButton(title="Choose Inward Liquid Color")
    bind_color_button(
        tab,
        tab.blob_inward_liquid_color_btn,
        '_blob_inward_liquid_color',
        auto_switch=True,
        initial_color=getattr(tab, '_blob_inward_liquid_color', None),
    )
    inward_liquid_color_layout.addWidget(tab.blob_inward_liquid_color_btn)
    inward_liquid_color_layout.addStretch()

    inward_liquid_reactivity_row, inward_liquid_reactivity_layout = _make_aligned_row(
        appearance_bucket,
        "Liquid Reactivity:",
    )
    tab._blob_inward_liquid_reactivity_row = inward_liquid_reactivity_row
    tab.blob_inward_liquid_reactivity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_inward_liquid_reactivity.setMinimum(0)
    tab.blob_inward_liquid_reactivity.setMaximum(200)
    ilr_val = int(tab._default_float('spotify_visualizer', 'blob_inward_liquid_reactivity', 1.0) * 100)
    tab.blob_inward_liquid_reactivity.setValue(max(0, min(200, ilr_val)))
    tab.blob_inward_liquid_reactivity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_inward_liquid_reactivity.setTickInterval(25)
    tab.blob_inward_liquid_reactivity.setToolTip(
        "How strongly the inward liquid reacts to pressure and audio motion."
    )
    tab.blob_inward_liquid_reactivity_label = QLabel(f"{ilr_val}%")
    bind_setting_signal(
        tab,
        tab.blob_inward_liquid_reactivity.valueChanged,
        updater=lambda v: tab.blob_inward_liquid_reactivity_label.setText(f"{v}%"),
        auto_switch=True,
    )
    inward_liquid_reactivity_layout.addWidget(tab.blob_inward_liquid_reactivity)
    inward_liquid_reactivity_layout.addWidget(tab.blob_inward_liquid_reactivity_label)

    inward_liquid_max_size_row, inward_liquid_max_size_layout = _make_aligned_row(
        appearance_bucket,
        "Liquid Maximum Size:",
    )
    tab._blob_inward_liquid_max_size_row = inward_liquid_max_size_row
    tab.blob_inward_liquid_max_size = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_inward_liquid_max_size.setMinimum(5)
    tab.blob_inward_liquid_max_size.setMaximum(45)
    ilm_val = int(tab._default_float('spotify_visualizer', 'blob_inward_liquid_max_size', 0.28) * 100)
    tab.blob_inward_liquid_max_size.setValue(max(5, min(45, ilm_val)))
    tab.blob_inward_liquid_max_size.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_inward_liquid_max_size.setTickInterval(5)
    tab.blob_inward_liquid_max_size.setToolTip(
        "Maximum allowed inward depth before the no-contact safety cap takes over."
    )
    tab.blob_inward_liquid_max_size_label = QLabel(f"{ilm_val}%")
    bind_setting_signal(
        tab,
        tab.blob_inward_liquid_max_size.valueChanged,
        updater=lambda v: tab.blob_inward_liquid_max_size_label.setText(f"{v}%"),
        auto_switch=True,
    )
    inward_liquid_max_size_layout.addWidget(tab.blob_inward_liquid_max_size)
    inward_liquid_max_size_layout.addWidget(tab.blob_inward_liquid_max_size_label)

    reactive_glow_row_w, reactive_glow_row = _glow_row("Reactive Glow:")
    tab._blob_reactive_glow_row = reactive_glow_row_w
    tab.blob_reactive_glow = QCheckBox("Enable")
    tab.blob_reactive_glow.setProperty("circleIndicator", True)
    tab.blob_reactive_glow.setChecked(tab._default_bool('spotify_visualizer', 'blob_reactive_glow', True))
    tab.blob_reactive_glow.setToolTip("Outer glow pulses with audio energy.")
    bind_setting_signal(tab, tab.blob_reactive_glow.stateChanged, auto_switch=True)
    reactive_glow_row.addWidget(tab.blob_reactive_glow)
    reactive_glow_row.addStretch()

    glow_widget, glow_layout = _glow_row("Glow Color:")
    tab._blob_glow_color_row = glow_widget
    tab.blob_glow_color_btn = ColorSwatchButton(title="Choose Blob Glow Color")
    bind_color_button(
        tab,
        tab.blob_glow_color_btn,
        '_blob_glow_color',
        auto_switch=True,
        initial_color=getattr(tab, '_blob_glow_color', None),
    )
    glow_layout.addWidget(tab.blob_glow_color_btn)
    glow_layout.addStretch()

    glow_row, glow_layout = _glow_row("Glow Intensity:")
    tab._blob_glow_intensity_row = glow_row
    tab.blob_glow_intensity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_glow_intensity.setMinimum(0)
    tab.blob_glow_intensity.setMaximum(100)
    blob_gi_val = int(tab._default_float('spotify_visualizer', 'blob_glow_intensity', 0.5) * 100)
    tab.blob_glow_intensity.setValue(max(0, min(100, blob_gi_val)))
    tab.blob_glow_intensity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_glow_intensity.setTickInterval(10)
    tab.blob_glow_intensity.setToolTip("Controls the overall brightness and spread of the blob glow.")
    tab.blob_glow_intensity_label = QLabel(f"{tab.blob_glow_intensity.value()}%")
    bind_setting_signal(
        tab,
        tab.blob_glow_intensity.valueChanged,
        updater=lambda v: tab.blob_glow_intensity_label.setText(f"{v}%"),
        auto_switch=True,
    )
    glow_layout.addWidget(tab.blob_glow_intensity)
    glow_layout.addWidget(tab.blob_glow_intensity_label)

    glow_react_row, glow_react_layout = _glow_row("Glow Reactivity:")
    tab._blob_glow_reactivity_row = glow_react_row
    tab.blob_glow_reactivity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_glow_reactivity.setMinimum(0)
    tab.blob_glow_reactivity.setMaximum(200)
    blob_gr_val = int(tab._default_float('spotify_visualizer', 'blob_glow_reactivity', 1.0) * 100)
    tab.blob_glow_reactivity.setValue(max(0, min(200, blob_gr_val)))
    tab.blob_glow_reactivity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_glow_reactivity.setTickInterval(25)
    tab.blob_glow_reactivity.setToolTip("How strongly the glow responds to audio energy. 0% = static glow, 200% = very reactive.")
    tab.blob_glow_reactivity_label = QLabel(f"{tab.blob_glow_reactivity.value()}%")
    bind_setting_signal(
        tab,
        tab.blob_glow_reactivity.valueChanged,
        updater=lambda v: tab.blob_glow_reactivity_label.setText(f"{v}%"),
        auto_switch=True,
    )
    glow_react_layout.addWidget(tab.blob_glow_reactivity)
    glow_react_layout.addWidget(tab.blob_glow_reactivity_label)

    glow_drive_row, glow_drive_layout = _glow_row("Glow Drive:")
    tab._blob_glow_drive_row = glow_drive_row
    tab.blob_glow_drive_mode = StyledComboBox(size_variant="compact")
    tab.blob_glow_drive_mode.addItems(["Bass Driven", "Vocal Driven"])
    default_glow_drive = tab._default_str(
        'spotify_visualizer',
        'blob_glow_drive_mode',
        'bass',
    ).strip().lower()
    tab.blob_glow_drive_mode.setCurrentIndex(1 if default_glow_drive == "vocal" else 0)
    tab.blob_glow_drive_mode.setToolTip(
        "Choose whether reactive glow follows bass/body support or vocal-side energy."
    )
    bind_setting_signal(tab, tab.blob_glow_drive_mode.currentIndexChanged)
    glow_drive_layout.addWidget(tab.blob_glow_drive_mode)
    glow_drive_layout.addStretch()

    glow_max_row, glow_max_layout = _glow_row("Glow Max Size:")
    tab._blob_glow_max_size_row = glow_max_row
    tab.blob_glow_max_size = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_glow_max_size.setMinimum(10)
    tab.blob_glow_max_size.setMaximum(300)
    blob_gms_val = int(tab._default_float('spotify_visualizer', 'blob_glow_max_size', 1.0) * 100)
    tab.blob_glow_max_size.setValue(max(10, min(300, blob_gms_val)))
    tab.blob_glow_max_size.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_glow_max_size.setTickInterval(25)
    tab.blob_glow_max_size.setToolTip("Maximum radius the glow can spread to. Higher = larger glow halo.")
    tab.blob_glow_max_size_label = QLabel(f"{tab.blob_glow_max_size.value()}%")
    bind_setting_signal(
        tab,
        tab.blob_glow_max_size.valueChanged,
        updater=lambda v: tab.blob_glow_max_size_label.setText(f"{v}%"),
        auto_switch=True,
    )
    glow_max_layout.addWidget(tab.blob_glow_max_size)
    glow_max_layout.addWidget(tab.blob_glow_max_size_label)

    def _update_glow_controls() -> None:
        enabled = tab.blob_reactive_glow.isChecked()
        for row in (
            glow_widget,
            glow_row,
            glow_react_row,
            glow_drive_row,
            glow_max_row,
        ):
            row.setVisible(enabled)
            row.setEnabled(enabled)

    tab.blob_reactive_glow.stateChanged.connect(lambda _s: _update_glow_controls())
    _update_glow_controls()

    tab._blob_card_size_layout = QVBoxLayout()
    tab._blob_card_size_layout.setSpacing(12)
    layout_bucket.addLayout(tab._blob_card_size_layout)

    def _card_size_row(label_text: str) -> tuple[QWidget, QHBoxLayout]:
        return _make_aligned_row(tab._blob_card_size_layout, label_text)

    width_widget, width_layout = _card_size_row("Card Width:")
    tab.blob_width = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_width.setMinimum(30)
    tab.blob_width.setMaximum(100)
    blob_width_val = int(tab._default_float('spotify_visualizer', 'blob_width', 1.0) * 100)
    tab.blob_width.setValue(max(30, min(100, blob_width_val)))
    tab.blob_width.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_width.setTickInterval(10)
    tab.blob_width_label = QLabel(f"{tab.blob_width.value()}%")
    bind_setting_signal(
        tab,
        tab.blob_width.valueChanged,
        updater=lambda v: tab.blob_width_label.setText(f"{v}%"),
        auto_switch=True,
    )
    width_layout.addWidget(tab.blob_width)
    width_layout.addWidget(tab.blob_width_label)

    size_widget, size_layout = _card_size_row("Blob Size:")
    tab.blob_size = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_size.setMinimum(30)
    tab.blob_size.setMaximum(200)
    blob_size_val = int(tab._default_float('spotify_visualizer', 'blob_size', 1.0) * 100)
    tab.blob_size.setValue(max(30, min(200, blob_size_val)))
    tab.blob_size.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_size.setTickInterval(20)
    tab.blob_size.setToolTip("Base SDF size (pre-staging). 100% = default card fit.")
    tab.blob_size_label = QLabel(f"{tab.blob_size.value()}%")
    bind_setting_signal(
        tab,
        tab.blob_size.valueChanged,
        updater=lambda v: tab.blob_size_label.setText(f"{v}%"),
        auto_switch=True,
    )
    size_layout.addWidget(tab.blob_size)
    size_layout.addWidget(tab.blob_size_label)

    ghost_toggle_row_w, ghost_toggle_row = _ghost_bucket_row("Ghosting:")
    tab.blob_ghost_enabled = QCheckBox("Enable Ghosting")
    tab.blob_ghost_enabled.setProperty("circleIndicator", True)
    tab.blob_ghost_enabled.setChecked(
        tab._default_bool('spotify_visualizer', 'blob_ghosting_enabled', False)
    )
    tab.blob_ghost_enabled.setToolTip(
        "Show a faded outline ring at the blob's recent peak size."
    )
    bind_setting_signal(tab, tab.blob_ghost_enabled.stateChanged)
    ghost_toggle_row.addWidget(tab.blob_ghost_enabled)
    ghost_toggle_row.addStretch()

    tab._blob_ghost_sub = QWidget()
    _ghost_layout = QVBoxLayout(tab._blob_ghost_sub)
    _ghost_layout.setContentsMargins(0, 0, 0, 12)
    _ghost_layout.setSpacing(12)

    def _ghost_row(label_text: str) -> tuple[QWidget, QHBoxLayout]:
        return _make_aligned_row(_ghost_layout, label_text)

    ghost_opa_w, ghost_opa_l = _ghost_row("Ghost Opacity:")
    tab.blob_ghost_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_ghost_opacity.setMinimum(0)
    tab.blob_ghost_opacity.setMaximum(100)
    _bg_alpha_pct = int(tab._default_float('spotify_visualizer', 'blob_ghost_alpha', 0.4) * 100)
    tab.blob_ghost_opacity.setValue(max(0, min(100, _bg_alpha_pct)))
    tab.blob_ghost_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_ghost_opacity.setTickInterval(5)
    bind_setting_signal(
        tab,
        tab.blob_ghost_opacity.valueChanged,
        updater=lambda v: tab.blob_ghost_opacity_label.setText(f"{v}%"),
    )
    ghost_opa_l.addWidget(tab.blob_ghost_opacity)
    tab.blob_ghost_opacity_label = QLabel(f"{_bg_alpha_pct}%")
    ghost_opa_l.addWidget(tab.blob_ghost_opacity_label)

    ghost_dec_w, ghost_dec_l = _ghost_row("Ghost Decay:")
    tab.blob_ghost_decay_slider = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_ghost_decay_slider.setMinimum(10)
    tab.blob_ghost_decay_slider.setMaximum(100)
    _bg_decay_pct = int(tab._default_float('spotify_visualizer', 'blob_ghost_decay', 0.3) * 100)
    tab.blob_ghost_decay_slider.setValue(max(10, min(100, _bg_decay_pct)))
    tab.blob_ghost_decay_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_ghost_decay_slider.setTickInterval(5)
    bind_setting_signal(
        tab,
        tab.blob_ghost_decay_slider.valueChanged,
        updater=lambda v: tab.blob_ghost_decay_label.setText(f"{v / 100.0:.2f}x"),
    )
    ghost_dec_l.addWidget(tab.blob_ghost_decay_slider)
    tab.blob_ghost_decay_label = QLabel(f"{tab.blob_ghost_decay_slider.value() / 100.0:.2f}x")
    ghost_dec_l.addWidget(tab.blob_ghost_decay_label)

    ghost_bucket.addWidget(tab._blob_ghost_sub)

    def _update_blob_ghost_vis(tab=tab):
        tab._blob_ghost_sub.setVisible(tab.blob_ghost_enabled.isChecked())

    tab.blob_ghost_enabled.stateChanged.connect(lambda _s: _update_blob_ghost_vis())
    _update_blob_ghost_vis()

    def _update_blob_inward_liquid_vis(tab=tab):
        enabled = tab.blob_inward_liquid_enabled.isChecked()
        for row in (
            tab._blob_inward_liquid_color_row,
            tab._blob_inward_liquid_reactivity_row,
            tab._blob_inward_liquid_max_size_row,
        ):
            row.setVisible(enabled)
            row.setEnabled(enabled)

    tab.blob_inward_liquid_enabled.stateChanged.connect(lambda _s: _update_blob_inward_liquid_vis())
    _update_blob_inward_liquid_vis()

def build_blob_growth(tab: "WidgetsTab") -> None:
    """Append height growth slider to the blob advanced container."""
    from ui.tabs.widgets_tab import NoWheelSlider

    parent_layout = getattr(tab, '_blob_card_size_layout', None)
    if parent_layout is None:
        parent_layout = tab._blob_advanced.layout()

    label_width = getattr(tab, '_blob_label_width', 120)
    blob_growth_row = QHBoxLayout()
    label = QLabel("Card Height:")
    label.setFixedWidth(label_width)
    blob_growth_row.addWidget(label)
    tab.blob_growth = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.blob_growth.setMinimum(100)
    tab.blob_growth.setMaximum(500)
    blob_growth_val = int(tab._default_float('spotify_visualizer', 'blob_growth', 2.5) * 100)
    tab.blob_growth.setValue(blob_growth_val)
    tab.blob_growth.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.blob_growth.setTickInterval(50)
    bind_setting_signal(
        tab,
        tab.blob_growth.valueChanged,
        updater=lambda v: tab.blob_growth_label.setText(f"{v / 100.0:.1f}x"),
        auto_switch=True,
    )
    blob_growth_row.addWidget(tab.blob_growth)
    tab.blob_growth_label = QLabel(f"{blob_growth_val / 100.0:.1f}x")
    blob_growth_row.addWidget(tab.blob_growth_label)
    parent_layout.addLayout(blob_growth_row)
