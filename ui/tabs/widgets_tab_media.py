"""Media + Beat Visualizer section for widgets tab.

Extracted from widgets_tab.py to reduce monolith size.
Contains UI building, settings loading/saving for Media widget and the Beat Visualizer.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QGroupBox, QCheckBox,
    QSlider, QWidget, QPushButton,
    QGraphicsDropShadowEffect, QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from core.logging.logger import get_logger
from ui.color_utils import qcolor_to_list as _qcolor_to_list
from ui.styled_popup import ColorSwatchButton
from ui.tabs.shared_styles import (
    STATUS_LABEL_STYLE,
    add_section_label,
    add_swatch_label,
    style_group_box,
    LABEL_WIDTH,  # Promoted to module-level constant
    add_aligned_row,
    create_inline_label,
)
from ui.widgets import StyledComboBox, StyledFontComboBox
from ui.tabs.settings_binding import (
    ColorBinding,
    apply_bindings_load,
    collect_bindings_save,
)
from ui.tabs.media.technical_controls import (
    collect_per_mode_technical_controls,
    load_per_mode_technical_controls,
)
from ui.tabs.media.blob_settings_binding import (
    collect_blob_mode_settings,
    load_blob_mode_settings,
)
from ui.tabs.media.bubble_settings_binding import (
    collect_bubble_mode_settings,
    load_bubble_mode_settings,
)
from ui.tabs.media.devcurve_settings_binding import (
    collect_devcurve_mode_settings,
    load_devcurve_mode_settings,
)
from ui.tabs.media.oscilloscope_settings_binding import (
    collect_oscilloscope_mode_settings,
    load_oscilloscope_mode_settings,
)
from ui.tabs.media.spectrum_settings_binding import (
    collect_spectrum_mode_settings,
    load_spectrum_mode_settings,
)
from ui.tabs.media.sine_wave_settings_binding import (
    collect_sine_wave_mode_settings,
    load_sine_wave_mode_settings,
)
from ui.tabs.media.visualizer_mode_binding import (
    collect_visualizer_mode_selection,
    collect_visualizer_preset_indices,
    collect_visualizer_rainbow_state,
    initialize_visualizer_mode_combo,
    load_visualizer_preset_indices,
    load_visualizer_mode_selection,
    load_visualizer_rainbow_state,
)

if TYPE_CHECKING:
    from ui.tabs.widgets_tab import WidgetsTab

logger = get_logger(__name__)


_OSC_MULTI_LINE_COLOR_BINDINGS = [
    ColorBinding('osc_line2_color', '_osc_line2_color', [255, 120, 50, 230]),
    ColorBinding('osc_line2_glow_color', '_osc_line2_glow_color', [255, 120, 50, 180]),
    ColorBinding('osc_line3_color', '_osc_line3_color', [50, 255, 120, 230]),
    ColorBinding('osc_line3_glow_color', '_osc_line3_glow_color', [50, 255, 120, 180]),
    ColorBinding('osc_line4_color', '_osc_line4_color', [255, 0, 150, 230]),
    ColorBinding('osc_line4_glow_color', '_osc_line4_glow_color', [255, 0, 150, 180]),
    ColorBinding('osc_line5_color', '_osc_line5_color', [0, 255, 200, 230]),
    ColorBinding('osc_line5_glow_color', '_osc_line5_glow_color', [0, 255, 200, 180]),
    ColorBinding('osc_line6_color', '_osc_line6_color', [200, 100, 255, 230]),
    ColorBinding('osc_line6_glow_color', '_osc_line6_glow_color', [200, 100, 255, 180]),
]


def _load_osc_multi_line_color_bindings(tab, spotify_vis_config) -> None:
    """Load oscilloscope secondary line colors through the shared binding helper."""
    apply_bindings_load(tab, spotify_vis_config, _OSC_MULTI_LINE_COLOR_BINDINGS)


def _collect_osc_multi_line_color_bindings(tab) -> dict:
    """Collect oscilloscope secondary line colors through the shared binding helper."""
    return collect_bindings_save(tab, _OSC_MULTI_LINE_COLOR_BINDINGS)


def _update_media_enabled_visibility(tab) -> None:
    """Show/hide all media controls based on media_enabled checkbox."""
    enabled = getattr(tab, 'media_enabled', None) and tab.media_enabled.isChecked()
    container = getattr(tab, '_media_controls_container', None)
    if container is not None:
        container.setVisible(bool(enabled))


def _update_spotify_vis_enabled_visibility(tab) -> None:
    """Show/hide all visualizer controls based on the Beat Visualizer toggle."""
    enabled_box = getattr(tab, 'vis_enabled_checkbox', None)
    enabled = enabled_box is not None and enabled_box.isChecked()
    container = getattr(tab, '_vis_controls_container', None)
    if container is not None:
        container.setVisible(bool(enabled))


def _update_visualizers_enabled_visibility(tab) -> None:
    """Gate the entire Visualizers section off the top-level toggle."""
    enabled = getattr(tab, 'visualizers_enabled', None) and tab.visualizers_enabled.isChecked()
    container = getattr(tab, '_visualizers_controls_container', None)
    if container is not None:
        container.setVisible(bool(enabled))


def _update_ghost_visibility(tab) -> None:
    """Show/hide ghost opacity/decay sliders based on ghost_enabled checkbox."""
    show = getattr(tab, 'vis_ghost_enabled', None) and tab.vis_ghost_enabled.isChecked()
    container = getattr(tab, '_ghost_sub_container', None)
    if container is not None:
        container.setVisible(bool(show))


def _update_media_bg_visibility(tab) -> None:
    """Show/hide media background styling controls based on show_background checkbox."""
    show = getattr(tab, 'media_show_background', None) and tab.media_show_background.isChecked()
    container = getattr(tab, '_media_bg_container', None)
    if container is not None:
        container.setVisible(bool(show))


def _update_osc_multi_line_visibility(tab) -> None:
    """Show/hide multi-line sub-controls based on checkbox and line count."""
    enabled = getattr(tab, 'osc_multi_line', None) and tab.osc_multi_line.isChecked()
    container = getattr(tab, '_osc_multi_container', None)
    if container is not None:
        container.setVisible(bool(enabled))
    # Line 3 controls only visible when count == 3
    line_count = getattr(tab, 'osc_line_count', None)
    show_l3 = enabled and line_count is not None and line_count.value() >= 3
    for w in (getattr(tab, '_osc_line3_label', None), getattr(tab, '_osc_l3_row_widget', None)):
        if w is not None:
            w.setVisible(bool(show_l3))


def _update_sine_multi_line_visibility(tab) -> None:
    """Show/hide sine wave multi-line sub-controls based on checkbox and line count."""
    enabled = getattr(tab, 'sine_multi_line', None) and tab.sine_multi_line.isChecked()
    container = getattr(tab, '_sine_multi_container', None)
    if container is not None:
        container.setVisible(bool(enabled))
    # Line 3 controls only visible when count == 3
    line_count = getattr(tab, 'sine_line_count_slider', None)
    show_l3 = enabled and line_count is not None and line_count.value() >= 3
    for w in (getattr(tab, '_sine_line3_label', None), getattr(tab, '_sine_l3_row_widget', None)):
        if w is not None:
            w.setVisible(bool(show_l3))


def _update_musicbee_plugin_visibility(tab) -> None:
    """Show/hide the MusicBee plugin button based on the selected provider."""
    btn = getattr(tab, '_musicbee_plugin_btn', None)
    combo = getattr(tab, 'media_provider_combo', None)
    if btn is not None and combo is not None:
        btn.setVisible(combo.currentData() == "musicbee")


def build_media_ui(tab: WidgetsTab, layout: QVBoxLayout) -> QWidget:
    """Build the Media widget UI section.

    Returns the media container widget.
    """
    from ui.tabs.widgets_tab import NoWheelSlider

    def _aligned_row(
        parent: QVBoxLayout,
        label_text: str,
        *,
        wrap: bool = True,
    ) -> QHBoxLayout:
        row, _ = add_aligned_row(
            parent,
            label_text,
            label_width=LABEL_WIDTH,
            wrap=wrap,
        )
        return row

    def _swatch_row(parent: QVBoxLayout, label_text: str) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 8, 0, 8)
        row.setSpacing(12)
        add_swatch_label(row, label_text, LABEL_WIDTH)
        content = QHBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(12)
        row.addLayout(content, 1)
        parent.addLayout(row)
        return content

    def _inline_label(text: str) -> QLabel:
        return create_inline_label(text)

    # --- Media Widget Group ---
    media_group = QGroupBox("Media Widget")
    style_group_box(media_group)
    media_layout = QVBoxLayout(media_group)
    media_layout.setSpacing(16)

    tab.media_enabled = QCheckBox("Enable Media Widget")
    tab.media_enabled.setProperty("circleIndicator", True)
    tab.media_enabled.setToolTip(
        "Shows current media playback using Windows media controls (GSMTC)."
    )
    tab.media_enabled.stateChanged.connect(tab._save_settings)
    tab.media_enabled.stateChanged.connect(tab._update_stack_status)
    media_layout.addWidget(tab.media_enabled)

    # Provider toggle row
    _provider_row = _aligned_row(media_layout, "Provider:")
    tab.media_provider_combo = StyledComboBox()
    tab.media_provider_combo.addItem("Spotify", "spotify")
    tab.media_provider_combo.addItem("MusicBee", "musicbee")
    tab.media_provider_combo.setMinimumWidth(150)
    tab.media_provider_combo.setToolTip(
        "Select which media player to monitor via Windows GSMTC.\n"
        "Change takes effect on next screensaver launch."
    )
    tab.media_provider_combo.currentIndexChanged.connect(tab._save_settings)
    tab.media_provider_combo.currentIndexChanged.connect(
        lambda: _update_musicbee_plugin_visibility(tab)
    )
    _provider_row.addWidget(tab.media_provider_combo)

    # GET PLUGIN button — visible only when MusicBee is selected
    tab._musicbee_plugin_btn = QPushButton("Get GSMTC Plugin")
    tab._musicbee_plugin_btn.setToolTip(
        "Opens the MusicBee Windows 10 Media Control Overlay plugin page.\n"
        "This plugin lets MusicBee register with Windows GSMTC for\n"
        "track info, artwork, and playback controls."
    )
    tab._musicbee_plugin_btn.setMinimumHeight(28)
    tab._musicbee_plugin_btn.setStyleSheet("padding: 4px 12px;")
    tab._musicbee_plugin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    tab._musicbee_plugin_btn.clicked.connect(
        lambda: __import__('webbrowser').open(
            "https://www.getmusicbee.com/addons/plugins/98/windows-10-media-control-overlay/"
        )
    )
    tab._musicbee_plugin_btn.setVisible(False)
    _provider_row.addWidget(tab._musicbee_plugin_btn)
    _provider_row.addStretch()

    # Container for all media controls gated by enable checkbox
    tab._media_controls_container = QWidget()
    _media_ctrl_layout = QVBoxLayout(tab._media_controls_container)
    _media_ctrl_layout.setContentsMargins(0, 0, 0, 12)
    _media_ctrl_layout.setSpacing(12)

    media_pos_row = _aligned_row(_media_ctrl_layout, "Position:")
    tab.media_position = StyledComboBox()
    tab.media_position.addItems([
        "Top Left", "Top Center", "Top Right",
        "Middle Left", "Center", "Middle Right",
        "Bottom Left", "Bottom Center", "Bottom Right",
    ])
    tab.media_position.currentTextChanged.connect(tab._save_settings)
    tab.media_position.currentTextChanged.connect(tab._update_stack_status)
    tab.media_position.setMinimumWidth(150)
    media_pos_row.addWidget(tab.media_position)
    tab._set_combo_text(tab.media_position, tab._default_str('media', 'position', 'Bottom Left'))
    tab.media_stack_status = QLabel("")
    tab.media_stack_status.setMinimumWidth(100)
    tab.media_stack_status.setStyleSheet(STATUS_LABEL_STYLE)
    media_pos_row.addWidget(tab.media_stack_status)
    media_pos_row.addStretch()

    media_disp_row = _aligned_row(_media_ctrl_layout, "Display:")
    tab.media_monitor_combo = StyledComboBox(size_variant="compact")
    tab.media_monitor_combo.addItems(["ALL", "1", "2", "3"])
    tab.media_monitor_combo.currentTextChanged.connect(tab._save_settings)
    tab.media_monitor_combo.currentTextChanged.connect(tab._update_stack_status)
    tab.media_monitor_combo.setMinimumWidth(120)
    media_disp_row.addWidget(tab.media_monitor_combo)
    media_monitor_default = tab._widget_default('media', 'monitor', 'ALL')
    tab._set_combo_text(tab.media_monitor_combo, str(media_monitor_default))
    media_disp_row.addStretch()

    media_font_family_row = _aligned_row(_media_ctrl_layout, "Font:")
    tab.media_font_combo = StyledFontComboBox(size_variant="hero")
    default_media_font = tab._default_str('media', 'font_family', 'Inter')
    tab.media_font_combo.setCurrentFont(QFont(default_media_font))
    tab.media_font_combo.setMinimumWidth(220)
    tab.media_font_combo.currentFontChanged.connect(tab._save_settings)
    media_font_family_row.addWidget(tab.media_font_combo)
    media_font_family_row.addStretch()

    media_font_row = _aligned_row(_media_ctrl_layout, "Font Size:")
    tab.media_font_size = QSpinBox()
    tab.media_font_size.setRange(10, 72)
    tab.media_font_size.setValue(tab._default_int('media', 'font_size', 20))
    tab.media_font_size.setAccelerated(True)
    tab.media_font_size.valueChanged.connect(tab._save_settings)
    tab.media_font_size.valueChanged.connect(tab._update_stack_status)
    media_font_row.addWidget(tab.media_font_size)
    font_px = _inline_label("px")
    font_px.setMinimumWidth(24)
    media_font_row.addWidget(font_px)
    media_font_row.addStretch()

    media_margin_row = _aligned_row(_media_ctrl_layout, "Margin:")
    tab.media_margin = QSpinBox()
    tab.media_margin.setRange(0, 100)
    tab.media_margin.setValue(tab._default_int('media', 'margin', 30))
    tab.media_margin.setAccelerated(True)
    tab.media_margin.valueChanged.connect(tab._save_settings)
    media_margin_row.addWidget(tab.media_margin)
    margin_px = _inline_label("px")
    margin_px.setMinimumWidth(24)
    media_margin_row.addWidget(margin_px)
    media_margin_row.addStretch()

    media_color_row = _swatch_row(_media_ctrl_layout, "Text Color:")
    tab.media_color_btn = ColorSwatchButton(title="Choose Spotify Text Color")
    tab.media_color_btn.set_color(tab._media_color)
    tab.media_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_media_color', c), tab._save_settings())
    )
    media_color_row.addWidget(tab.media_color_btn)
    media_color_row.addStretch()

    tab.media_show_background = QCheckBox("Show Background Frame")
    tab.media_show_background.setProperty("circleIndicator", True)
    tab.media_show_background.setChecked(tab._default_bool('media', 'show_background', True))
    tab.media_show_background.stateChanged.connect(tab._save_settings)
    _media_ctrl_layout.addWidget(tab.media_show_background)

    # Background sub-controls container (shown only when show_background is checked)
    tab._media_bg_container = QWidget()
    _mbg_layout = QVBoxLayout(tab._media_bg_container)
    _mbg_layout.setContentsMargins(0, 0, 0, 12)
    _mbg_layout.setSpacing(12)

    media_opacity_row = _aligned_row(_mbg_layout, "Background Opacity:")
    tab.media_bg_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.media_bg_opacity.setMinimum(0)
    tab.media_bg_opacity.setMaximum(100)
    media_bg_opacity_pct = int(tab._default_float('media', 'bg_opacity', 0.6) * 100)
    tab.media_bg_opacity.setValue(media_bg_opacity_pct)
    tab.media_bg_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.media_bg_opacity.setTickInterval(10)
    tab.media_bg_opacity.valueChanged.connect(tab._save_settings)
    media_opacity_row.addWidget(tab.media_bg_opacity)
    tab.media_bg_opacity_label = QLabel(f"{media_bg_opacity_pct}%")
    tab.media_bg_opacity.valueChanged.connect(
        lambda v: tab.media_bg_opacity_label.setText(f"{v}%")
    )
    tab.media_bg_opacity_label.setMinimumWidth(50)
    media_opacity_row.addWidget(tab.media_bg_opacity_label)

    media_bg_color_row = _swatch_row(_mbg_layout, "Background Color:")
    tab.media_bg_color_btn = ColorSwatchButton(title="Choose Spotify Background Color")
    tab.media_bg_color_btn.set_color(tab._media_bg_color)
    tab.media_bg_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_media_bg_color', c), tab._save_settings())
    )
    media_bg_color_row.addWidget(tab.media_bg_color_btn)
    media_bg_color_row.addStretch()

    media_border_color_row = _swatch_row(_mbg_layout, "Border Color:")
    tab.media_border_color_btn = ColorSwatchButton(title="Choose Spotify Border Color")
    tab.media_border_color_btn.set_color(tab._media_border_color)
    tab.media_border_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_media_border_color', c), tab._save_settings())
    )
    media_border_color_row.addWidget(tab.media_border_color_btn)
    media_border_color_row.addStretch()

    media_border_opacity_row = _aligned_row(_mbg_layout, "Border Opacity:")
    tab.media_border_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.media_border_opacity.setMinimum(0)
    tab.media_border_opacity.setMaximum(100)
    media_border_opacity_pct = int(tab._default_float('media', 'border_opacity', 1.0) * 100)
    tab.media_border_opacity.setValue(media_border_opacity_pct)
    tab.media_border_opacity.setTickPosition(QSlider.TickPosition.TicksBelow)
    tab.media_border_opacity.setTickInterval(10)
    tab.media_border_opacity.valueChanged.connect(tab._save_settings)
    media_border_opacity_row.addWidget(tab.media_border_opacity)
    tab.media_border_opacity_label = QLabel(f"{media_border_opacity_pct}%")
    tab.media_border_opacity.valueChanged.connect(
        lambda v: tab.media_border_opacity_label.setText(f"{v}%")
    )
    tab.media_border_opacity_label.setMinimumWidth(50)
    media_border_opacity_row.addWidget(tab.media_border_opacity_label)

    _media_ctrl_layout.addWidget(tab._media_bg_container)
    tab.media_show_background.stateChanged.connect(lambda: _update_media_bg_visibility(tab))
    _update_media_bg_visibility(tab)

    media_volume_fill_row = _swatch_row(_media_ctrl_layout, "Volume Fill Color:")
    tab.media_volume_fill_color_btn = ColorSwatchButton(title="Choose Spotify Volume Fill Color")
    tab.media_volume_fill_color_btn.set_color(getattr(tab, '_media_volume_fill_color', tab._media_color))
    tab.media_volume_fill_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_media_volume_fill_color', c), tab._save_settings())
    )
    media_volume_fill_row.addWidget(tab.media_volume_fill_color_btn)
    media_volume_fill_row.addStretch()

    media_artwork_row = _aligned_row(_media_ctrl_layout, "Artwork Size:")
    tab.media_artwork_size = QSpinBox()
    tab.media_artwork_size.setRange(100, 300)
    tab.media_artwork_size.setValue(tab._default_int('media', 'artwork_size', 200))
    tab.media_artwork_size.setAccelerated(True)
    tab.media_artwork_size.valueChanged.connect(tab._save_settings)
    tab.media_artwork_size.valueChanged.connect(tab._update_stack_status)
    media_artwork_row.addWidget(tab.media_artwork_size)
    art_px = _inline_label("px")
    art_px.setMinimumWidth(24)
    media_artwork_row.addWidget(art_px)
    media_artwork_row.addStretch()

    tab.media_rounded_artwork = QCheckBox("Rounded Artwork Border")
    tab.media_rounded_artwork.setProperty("circleIndicator", True)
    tab.media_rounded_artwork.setChecked(
        tab._default_bool('media', 'rounded_artwork_border', True)
    )
    tab.media_rounded_artwork.stateChanged.connect(tab._save_settings)
    _media_ctrl_layout.addWidget(tab.media_rounded_artwork)

    tab.media_show_header_frame = QCheckBox("Header Border Around Logo + Title")
    tab.media_show_header_frame.setProperty("circleIndicator", True)
    tab.media_show_header_frame.setChecked(
        tab._default_bool('media', 'show_header_frame', True)
    )
    tab.media_show_header_frame.stateChanged.connect(tab._save_settings)
    _media_ctrl_layout.addWidget(tab.media_show_header_frame)

    tab.media_show_controls = QCheckBox("Show Transport Controls")
    tab.media_show_controls.setProperty("circleIndicator", True)
    tab.media_show_controls.setChecked(
        tab._default_bool('media', 'show_controls', True)
    )
    tab.media_show_controls.stateChanged.connect(tab._save_settings)
    _media_ctrl_layout.addWidget(tab.media_show_controls)

    tab.media_spotify_volume_enabled = QCheckBox("Enable Spotify Volume Slider")
    tab.media_spotify_volume_enabled.setProperty("circleIndicator", True)
    tab.media_spotify_volume_enabled.setToolTip(
        "Show a slim vertical volume slider next to the Spotify card when Core Audio/pycaw is available. "
        "The slider only affects the Spotify session volume and is gated by hard-exit / Ctrl interaction modes."
    )
    tab.media_spotify_volume_enabled.setChecked(
        tab._default_bool('media', 'spotify_volume_enabled', True)
    )
    tab.media_spotify_volume_enabled.stateChanged.connect(tab._save_settings)
    _media_ctrl_layout.addWidget(tab.media_spotify_volume_enabled)

    tab.media_mute_button_enabled = QCheckBox("Enable System Mute Button")
    tab.media_mute_button_enabled.setProperty("circleIndicator", True)
    tab.media_mute_button_enabled.setToolTip(
        "Show a small mute toggle button near the media card. "
        "Single-click toggles system-wide mute on/off (requires pycaw/Core Audio)."
    )
    tab.media_mute_button_enabled.setChecked(
        tab._default_bool('media', 'mute_button_enabled', False)
    )
    tab.media_mute_button_enabled.stateChanged.connect(tab._save_settings)
    _media_ctrl_layout.addWidget(tab.media_mute_button_enabled)

    media_layout.addWidget(tab._media_controls_container)
    tab.media_enabled.stateChanged.connect(lambda: _update_media_enabled_visibility(tab))
    _update_media_enabled_visibility(tab)

    container = QWidget()
    container_layout = QVBoxLayout(container)
    container_layout.setContentsMargins(0, 20, 0, 0)
    container_layout.addWidget(media_group)
    return container


def build_visualizers_ui(tab: "WidgetsTab", layout: QVBoxLayout) -> QWidget:
    """Build the Visualizers widget UI section (separate toggle)."""

    from ui.tabs.widgets_tab import NoWheelSlider

    visualizers_group = QGroupBox("Visualizers")
    style_group_box(visualizers_group)
    visualizers_layout = QVBoxLayout(visualizers_group)

    tab.visualizers_enabled = QCheckBox("Enable Visualizers")
    tab.visualizers_enabled.setProperty("circleIndicator", True)
    tab.visualizers_enabled.setChecked(tab._default_bool('spotify_visualizer', 'visualizers_enabled', True))
    tab.visualizers_enabled.setToolTip("Master switch for all visualizer controls.")
    tab.visualizers_enabled.stateChanged.connect(tab._save_settings)
    tab.visualizers_enabled.stateChanged.connect(lambda: _update_visualizers_enabled_visibility(tab))
    visualizers_layout.addWidget(tab.visualizers_enabled)

    tab._visualizers_controls_container = QWidget()
    _viz_ctrls = QVBoxLayout(tab._visualizers_controls_container)
    _viz_ctrls.setContentsMargins(0, 0, 0, 0)
    _viz_ctrls.setSpacing(8)

    # --- Beat Visualizer Group ---
    spotify_vis_group = QGroupBox("Beat Visualizer")
    spotify_vis_group.setObjectName("beatVisualizerGroup")
    style_group_box(spotify_vis_group)
    spotify_vis_group.setStyleSheet(
        spotify_vis_group.styleSheet() +
        "\nQGroupBox#beatVisualizerGroup::title { font-size: 15px; }"
    )
    spotify_vis_layout = QVBoxLayout(spotify_vis_group)

    spotify_vis_enable_row = QHBoxLayout()
    tab.vis_enabled_checkbox = QCheckBox("Enable Beat Visualizer")
    tab.vis_enabled_checkbox.setProperty("circleIndicator", True)
    tab.vis_enabled_checkbox.setChecked(tab._default_bool('spotify_visualizer', 'enabled', True))
    tab.vis_enabled_checkbox.setToolTip(
        "Shows a thin bar visualizer tied to Spotify playback, positioned just above the Spotify widget."
    )
    tab.vis_enabled_checkbox.stateChanged.connect(tab._save_settings)
    spotify_vis_enable_row.addWidget(tab.vis_enabled_checkbox)

    spotify_vis_enable_row.addStretch()
    spotify_vis_layout.addLayout(spotify_vis_enable_row)

    # Container for all visualizer controls gated by enable checkbox
    tab._vis_controls_container = QWidget()
    _svctl = QVBoxLayout(tab._vis_controls_container)
    _svctl.setContentsMargins(0, 0, 0, 0)
    _svctl.setSpacing(4)

    # --- Taste The Rainbow (per-mode hue shift) ---
    # Cache dict: stores {mode: (enabled, speed)} so mode switches are instant.
    tab._rainbow_per_mode: dict = {}
    rainbow_row = QHBoxLayout()
    rainbow_row.setContentsMargins(0, 0, 0, 0)
    rainbow_row.setSpacing(6)
    rainbow_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)

    tab.rainbow_enabled = QCheckBox("Taste The Rainbow")
    tab.rainbow_enabled.setProperty("circleIndicator", True)
    tab.rainbow_enabled.setAccessibleName("Taste The Rainbow")
    tab.rainbow_enabled.setToolTip(
        "Slowly shift the hue of visualiser colours through the spectrum. "
        "Saved independently per visualizer mode."
    )
    tab.rainbow_enabled.setChecked(False)
    tab.rainbow_enabled.setCursor(Qt.CursorShape.PointingHandCursor)
    tab.rainbow_enabled.stateChanged.connect(tab._save_settings)
    tab.rainbow_enabled.stateChanged.connect(
        lambda _: tab._update_rainbow_visibility()
    )
    tab.rainbow_enabled.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    rainbow_row.addWidget(tab.rainbow_enabled)

    glow_effect = QGraphicsDropShadowEffect(tab.rainbow_enabled)
    glow_effect.setColor(QColor(255, 255, 255, 160))
    glow_effect.setBlurRadius(26.0)
    glow_effect.setOffset(0, 0)
    glow_effect.setEnabled(False)
    tab.rainbow_enabled.setGraphicsEffect(glow_effect)

    tab._rainbow_plain_label = tab.rainbow_enabled
    tab._rainbow_glow_effect = glow_effect
    tab._rainbow_label_stack = None
    tab._rainbow_glow_label = None

    rainbow_row.addStretch()
    _svctl.addLayout(rainbow_row)

    # Rainbow speed slider (conditional on checkbox)
    tab._rainbow_speed_container = QWidget()
    _rsc_layout = QHBoxLayout(tab._rainbow_speed_container)
    _rsc_layout.setContentsMargins(0, 0, 0, 0)
    _rsc_layout.setSpacing(6)
    add_section_label(_rsc_layout, "Speed:", LABEL_WIDTH)

    speed_content = QHBoxLayout()
    speed_content.setContentsMargins(0, 0, 0, 0)
    speed_content.setSpacing(6)
    _rsc_layout.addLayout(speed_content, 1)
    tab.rainbow_speed_slider = NoWheelSlider(Qt.Orientation.Horizontal)
    tab.rainbow_speed_slider.setRange(1, 100)
    tab.rainbow_speed_slider.setValue(50)
    tab.rainbow_speed_slider.setToolTip("How fast the hue cycles through the spectrum.")
    tab.rainbow_speed_slider.valueChanged.connect(tab._save_settings)
    tab.rainbow_speed_label = QLabel("0.50")
    tab.rainbow_speed_slider.valueChanged.connect(
        lambda v: tab.rainbow_speed_label.setText(f"{v / 100.0:.2f}")
    )
    speed_content.addWidget(tab.rainbow_speed_slider, 1)
    speed_content.addWidget(tab.rainbow_speed_label)
    _svctl.addWidget(tab._rainbow_speed_container)
    tab._rainbow_speed_container.setVisible(False)

    # --- Visualizer Type Selector ---
    vis_type_row = QHBoxLayout()
    vis_type_row.setContentsMargins(0, 0, 0, 0)
    vis_type_row.setSpacing(6)
    vis_type_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
    add_section_label(vis_type_row, "Visualizer Type:", LABEL_WIDTH)
    vis_type_content = QHBoxLayout()
    vis_type_content.setContentsMargins(9, 0, 0, 0)
    vis_type_content.setSpacing(6)
    tab.vis_mode_combo = StyledComboBox(size_variant="hero")
    tab.vis_mode_combo.setMinimumWidth(160)
    import os as _os
    _dev_features = _os.getenv('SRPSS_ENABLE_DEV', 'false').lower() == 'true'
    initialize_visualizer_mode_combo(tab)
    tab.vis_mode_combo.setToolTip(
        "Select the visualization style. Spectrum is the classic segmented bar display."
    )
    tab.vis_mode_combo.currentIndexChanged.connect(tab._save_settings)
    tab.vis_mode_combo.currentIndexChanged.connect(
        lambda _: tab._update_vis_mode_sections()
    )
    vis_type_content.addWidget(tab.vis_mode_combo)
    vis_type_content.addStretch()
    vis_type_row.addLayout(vis_type_content, 1)
    _svctl.addLayout(vis_type_row)

    # ==========================================
    # Per-visualizer settings — delegated to builder modules
    # ==========================================
    from ui.tabs.media.spectrum_builder import build_spectrum_ui
    from ui.tabs.media.oscilloscope_builder import build_oscilloscope_ui
    from ui.tabs.media.blob_builder import build_blob_ui, build_blob_growth
    from ui.tabs.media.sine_wave_builder import build_sine_wave_ui
    from ui.tabs.media.bubble_builder import build_bubble_ui
    from core.dev_gates import is_devcurve_enabled
    from ui.tabs.media.devcurve_builder import build_devcurve_ui

    build_spectrum_ui(tab, _svctl)
    build_oscilloscope_ui(tab, _svctl)
    build_blob_ui(tab, _svctl)
    build_sine_wave_ui(tab, _svctl)
    build_bubble_ui(tab, _svctl)
    if is_devcurve_enabled():
        build_devcurve_ui(tab, _svctl)

    # Append growth sliders that were originally added after sine section
    build_blob_growth(tab)

    spotify_vis_layout.addWidget(tab._vis_controls_container)
    tab.vis_enabled_checkbox.stateChanged.connect(lambda: _update_spotify_vis_enabled_visibility(tab))
    _update_spotify_vis_enabled_visibility(tab)

    _viz_ctrls.addWidget(spotify_vis_group)
    visualizers_layout.addWidget(tab._visualizers_controls_container)
    _update_visualizers_enabled_visibility(tab)

    # Initial visibility
    tab._update_vis_mode_sections()

    container = QWidget()
    container_layout = QVBoxLayout(container)
    container_layout.setContentsMargins(0, 20, 0, 0)
    container_layout.addWidget(visualizers_group)
    return container


def load_media_settings(tab: "WidgetsTab", widgets: dict | None) -> None:
    """Load media widget settings from the widgets config dict."""

    def _apply_color_to_button(btn_attr: str, color_attr: str) -> None:
        btn = getattr(tab, btn_attr, None)
        color = getattr(tab, color_attr, None)
        if btn is not None and color is not None and hasattr(btn, "set_color"):
            try:
                btn.set_color(color)
            except Exception:
                logger.debug(
                    "[MEDIA_TAB] Failed to sync %s with %s", btn_attr, color_attr, exc_info=True
                )

    widgets = widgets or {}

    media_config = widgets.get('media', {}) if isinstance(widgets, dict) else {}
    spotify_vis_config = widgets.get('spotify_visualizer', {}) if isinstance(widgets, dict) else {}
    tab.media_enabled.setChecked(tab._config_bool('media', media_config, 'enabled', True))

    # Provider (spotify / musicbee)
    provider = tab._config_str('media', media_config, 'provider', 'spotify').lower()
    combo = getattr(tab, 'media_provider_combo', None)
    if combo is not None:
        idx = combo.findData(provider)
        if idx >= 0:
            combo.setCurrentIndex(idx)
    _update_musicbee_plugin_visibility(tab)

    media_pos = tab._config_str('media', media_config, 'position', 'Bottom Left')
    index = tab.media_position.findText(media_pos)
    if index >= 0:
        tab.media_position.setCurrentIndex(index)

    tab.media_font_combo.setCurrentFont(QFont(tab._config_str('media', media_config, 'font_family', 'Inter')))
    tab.media_font_size.setValue(tab._config_int('media', media_config, 'font_size', 22))
    tab.media_margin.setValue(tab._config_int('media', media_config, 'margin', 30))
    tab.media_show_background.setChecked(tab._config_bool('media', media_config, 'show_background', True))
    media_opacity_pct = int(tab._config_float('media', media_config, 'bg_opacity', 0.6) * 100)
    tab.media_bg_opacity.setValue(media_opacity_pct)
    tab.media_bg_opacity_label.setText(f"{media_opacity_pct}%")

    tab._media_artwork_size = tab._config_int('media', media_config, 'artwork_size', 250)
    tab.media_artwork_size.setValue(tab._media_artwork_size)
    tab.media_rounded_artwork.setChecked(tab._config_bool('media', media_config, 'rounded_artwork_border', True))
    tab.media_show_header_frame.setChecked(tab._config_bool('media', media_config, 'show_header_frame', True))
    tab.media_show_controls.setChecked(tab._config_bool('media', media_config, 'show_controls', True))
    tab.media_spotify_volume_enabled.setChecked(
        tab._config_bool('media', media_config, 'spotify_volume_enabled', True)
    )
    tab.media_mute_button_enabled.setChecked(
        tab._config_bool('media', media_config, 'mute_button_enabled', True)
    )

    # Colors
    media_color_data = media_config.get('color', tab._widget_default('media', 'color', [255, 255, 255, 230]))
    tab._media_color = QColor(*media_color_data)
    media_bg_color_data = media_config.get('bg_color', tab._widget_default('media', 'bg_color', [35, 35, 35, 255]))
    try:
        tab._media_bg_color = QColor(*media_bg_color_data)
    except Exception:
        logger.debug("[MEDIA_TAB] Failed to set media bg_color=%s", media_bg_color_data, exc_info=True)
        tab._media_bg_color = QColor(35, 35, 35, 255)
    media_border_color_data = media_config.get('border_color', tab._widget_default('media', 'border_color', [255, 255, 255, 255]))
    try:
        tab._media_border_color = QColor(*media_border_color_data)
    except Exception:
        logger.debug("[MEDIA_TAB] Failed to set media border_color=%s", media_border_color_data, exc_info=True)
        tab._media_border_color = QColor(255, 255, 255, 255)
    media_border_opacity_pct = int(tab._config_float('media', media_config, 'border_opacity', 1.0) * 100)
    tab.media_border_opacity.setValue(media_border_opacity_pct)
    tab.media_border_opacity_label.setText(f"{media_border_opacity_pct}%")

    volume_fill_data = media_config.get('spotify_volume_fill_color', tab._widget_default('media', 'spotify_volume_fill_color', [66, 66, 66, 255]))
    try:
        tab._media_volume_fill_color = QColor(*volume_fill_data)
    except Exception:
        logger.debug("[MEDIA_TAB] Failed to set volume_fill_color=%s", volume_fill_data, exc_info=True)
        tab._media_volume_fill_color = QColor(66, 66, 66, 255)
    _apply_color_to_button('media_color_btn', '_media_color')
    _apply_color_to_button('media_bg_color_btn', '_media_bg_color')
    _apply_color_to_button('media_border_color_btn', '_media_border_color')
    _apply_color_to_button('media_volume_fill_color_btn', '_media_volume_fill_color')

    m_monitor_sel = media_config.get('monitor', tab._widget_default('media', 'monitor', 'ALL'))
    m_mon_text = str(m_monitor_sel) if isinstance(m_monitor_sel, (int, str)) else 'ALL'
    midx = tab.media_monitor_combo.findText(m_mon_text)
    if midx >= 0:
        tab.media_monitor_combo.setCurrentIndex(midx)

    _update_media_bg_visibility(tab)

    tab.vis_enabled_checkbox.setChecked(
        tab._config_bool('spotify_visualizer', spotify_vis_config, 'enabled', True)
    )
    load_per_mode_technical_controls(tab, spotify_vis_config)

    fill_color_data = spotify_vis_config.get('bar_fill_color', tab._widget_default('spotify_visualizer', 'bar_fill_color', [0, 255, 128, 230]))
    try:
        tab._spotify_vis_fill_color = QColor(*fill_color_data)
    except Exception:
        logger.debug("[MEDIA_TAB] Failed to set vis fill_color=%s", fill_color_data, exc_info=True)
        tab._spotify_vis_fill_color = QColor(0, 255, 128, 230)

    border_color_data = spotify_vis_config.get('bar_border_color', tab._widget_default('spotify_visualizer', 'bar_border_color', [255, 255, 255, 230]))
    try:
        tab._spotify_vis_border_color = QColor(*border_color_data)
    except Exception:
        logger.debug("[MEDIA_TAB] Failed to set vis border_color=%s", border_color_data, exc_info=True)
        tab._spotify_vis_border_color = QColor(255, 255, 255, 230)

    _apply_color_to_button('vis_fill_color_btn', '_spotify_vis_fill_color')
    _apply_color_to_button('vis_border_color_btn', '_spotify_vis_border_color')

    border_opacity_pct = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'bar_border_opacity', 0.85) * 100)
    tab.vis_border_opacity.setValue(border_opacity_pct)
    tab.vis_border_opacity_label.setText(f"{border_opacity_pct}%")

    # Visualizer mode combobox
    load_visualizer_mode_selection(tab, spotify_vis_config)

    load_oscilloscope_mode_settings(
        tab,
        spotify_vis_config,
        sync_color_button=_apply_color_to_button,
        load_extra_color_bindings=_load_osc_multi_line_color_bindings,
        update_multi_line_visibility=_update_osc_multi_line_visibility,
    )
    load_spectrum_mode_settings(
        tab,
        spotify_vis_config,
        sync_color_button=_apply_color_to_button,
        update_ghost_visibility=_update_ghost_visibility,
    )

    load_sine_wave_mode_settings(
        tab,
        spotify_vis_config,
        sync_color_button=_apply_color_to_button,
        update_multi_line_visibility=_update_sine_multi_line_visibility,
    )

    # Update per-mode section visibility
    tab._update_vis_mode_sections()

    load_blob_mode_settings(
        tab,
        spotify_vis_config,
        sync_color_button=_apply_color_to_button,
    )

    load_visualizer_rainbow_state(tab, spotify_vis_config)
    load_bubble_mode_settings(
        tab,
        spotify_vis_config,
        sync_color_button=_apply_color_to_button,
    )
    from core.dev_gates import is_devcurve_enabled
    if is_devcurve_enabled():
        load_devcurve_mode_settings(
            tab,
            spotify_vis_config,
            sync_color_button=_apply_color_to_button,
        )

    load_visualizer_preset_indices(tab, spotify_vis_config)

    _update_media_enabled_visibility(tab)
    _update_spotify_vis_enabled_visibility(tab)


def save_media_settings(tab: WidgetsTab) -> tuple[dict, dict]:
    """Return (media_config, spotify_vis_config) from current UI state."""
    _provider_combo = getattr(tab, 'media_provider_combo', None)
    _provider_val = _provider_combo.currentData() if _provider_combo is not None else "spotify"
    media_config = {
        'enabled': tab.media_enabled.isChecked(),
        'provider': _provider_val or "spotify",
        'position': tab.media_position.currentText(),
        'font_family': tab.media_font_combo.currentFont().family(),
        'font_size': tab.media_font_size.value(),
        'margin': tab.media_margin.value(),
        'show_background': tab.media_show_background.isChecked(),
        'bg_opacity': tab.media_bg_opacity.value() / 100.0,
        'color': [tab._media_color.red(), tab._media_color.green(),
                  tab._media_color.blue(), tab._media_color.alpha()],
        'bg_color': [tab._media_bg_color.red(), tab._media_bg_color.green(),
                     tab._media_bg_color.blue(), tab._media_bg_color.alpha()],
        'border_color': [tab._media_border_color.red(), tab._media_border_color.green(),
                         tab._media_border_color.blue(), tab._media_border_color.alpha()],
        'border_opacity': tab.media_border_opacity.value() / 100.0,
        'spotify_volume_fill_color': [
            tab._media_volume_fill_color.red(),
            tab._media_volume_fill_color.green(),
            tab._media_volume_fill_color.blue(),
            tab._media_volume_fill_color.alpha(),
        ],
        'artwork_size': tab.media_artwork_size.value(),
        'rounded_artwork_border': tab.media_rounded_artwork.isChecked(),
        'show_header_frame': tab.media_show_header_frame.isChecked(),
        'show_controls': tab.media_show_controls.isChecked(),
        'spotify_volume_enabled': tab.media_spotify_volume_enabled.isChecked(),
        'mute_button_enabled': tab.media_mute_button_enabled.isChecked(),
    }
    mmon_text = tab.media_monitor_combo.currentText()
    media_config['monitor'] = mmon_text if mmon_text == 'ALL' else int(mmon_text)

    spotify_vis_config = {
        'visualizers_enabled': tab.visualizers_enabled.isChecked() if hasattr(tab, 'visualizers_enabled') else True,
        'enabled': tab.vis_enabled_checkbox.isChecked(),
        'mode': collect_visualizer_mode_selection(tab),
        'software_visualizer_enabled': False,
        'bar_fill_color': [
            tab._spotify_vis_fill_color.red(),
            tab._spotify_vis_fill_color.green(),
            tab._spotify_vis_fill_color.blue(),
            tab._spotify_vis_fill_color.alpha(),
        ],
        'bar_border_color': [
            tab._spotify_vis_border_color.red(),
            tab._spotify_vis_border_color.green(),
            tab._spotify_vis_border_color.blue(),
            tab._spotify_vis_border_color.alpha(),
        ],
        'bar_border_opacity': tab.vis_border_opacity.value() / 100.0,
        'ghosting_enabled': tab.vis_ghost_enabled.isChecked(),
        'ghost_alpha': tab.vis_ghost_opacity_slider.value() / 100.0,
        'ghost_decay': max(0.1, tab.vis_ghost_decay_slider.value() / 100.0),
        'spectrum_ghosting_enabled': tab.vis_ghost_enabled.isChecked(),
        'spectrum_ghost_alpha': tab.vis_ghost_opacity_slider.value() / 100.0,
        'spectrum_ghost_decay': max(0.1, tab.vis_ghost_decay_slider.value() / 100.0),
        'rainbow_enabled': tab.rainbow_enabled.isChecked() if hasattr(tab, 'rainbow_enabled') else False,
        'rainbow_speed': (tab.rainbow_speed_slider.value() if hasattr(tab, 'rainbow_speed_slider') else 50) / 100.0,
    }
    collect_visualizer_rainbow_state(tab, spotify_vis_config)
    
    # Option A: Only collect settings for the CURRENT visualizer mode
    # to prevent cross-mode pollution when saving presets
    _cur_mode = collect_visualizer_mode_selection(tab)
    if _cur_mode == 'spectrum':
        spotify_vis_config.update(collect_spectrum_mode_settings(tab))
    elif _cur_mode == 'oscilloscope':
        spotify_vis_config.update(
            collect_oscilloscope_mode_settings(
                tab,
                collect_extra_color_bindings=_collect_osc_multi_line_color_bindings,
            )
        )
    elif _cur_mode == 'sine_wave':
        spotify_vis_config.update(collect_sine_wave_mode_settings(tab))
    elif _cur_mode == 'blob':
        spotify_vis_config.update(collect_blob_mode_settings(tab))
    elif _cur_mode == 'bubble':
        spotify_vis_config.update(collect_bubble_mode_settings(tab))
    elif _cur_mode == 'devcurve':
        spotify_vis_config.update(collect_devcurve_mode_settings(tab))
    collect_per_mode_technical_controls(tab, spotify_vis_config, current_mode=_cur_mode)

    collect_visualizer_preset_indices(tab, spotify_vis_config)

    return media_config, spotify_vis_config


