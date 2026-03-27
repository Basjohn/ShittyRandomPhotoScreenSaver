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
]


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
    default_media_font = tab._default_str('media', 'font_family', 'Segoe UI')
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

    tab.media_intense_shadow = QCheckBox("Intense Shadows")
    tab.media_intense_shadow.setProperty("circleIndicator", True)
    tab.media_intense_shadow.setChecked(tab._default_bool('media', 'intense_shadow', True))
    tab.media_intense_shadow.setToolTip(
        "Doubles shadow blur, opacity, and offset for dramatic effect on large displays."
    )
    tab.media_intense_shadow.stateChanged.connect(tab._save_settings)
    _mbg_layout.addWidget(tab.media_intense_shadow)

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

    build_spectrum_ui(tab, _svctl)
    build_oscilloscope_ui(tab, _svctl)
    build_blob_ui(tab, _svctl)
    build_sine_wave_ui(tab, _svctl)
    build_bubble_ui(tab, _svctl)

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

    tab.media_font_combo.setCurrentFont(QFont(tab._config_str('media', media_config, 'font_family', 'Segoe UI')))
    tab.media_font_size.setValue(tab._config_int('media', media_config, 'font_size', 22))
    tab.media_margin.setValue(tab._config_int('media', media_config, 'margin', 30))
    tab.media_show_background.setChecked(tab._config_bool('media', media_config, 'show_background', True))
    tab.media_intense_shadow.setChecked(tab._config_bool('media', media_config, 'intense_shadow', True))
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

    # Per-mode settings: Oscilloscope
    if hasattr(tab, 'osc_glow_enabled'):
        tab.osc_glow_enabled.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'osc_glow_enabled', True)
        )
    if hasattr(tab, 'osc_glow_intensity'):
        osc_glow_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'osc_glow_intensity', 0.5) * 100)
        tab.osc_glow_intensity.setValue(max(0, min(100, osc_glow_val)))
        tab.osc_glow_intensity_label.setText(f"{osc_glow_val}%")
    if hasattr(tab, 'osc_glow_reactivity'):
        osc_gr_val = int(
            tab._config_float(
                'spotify_visualizer',
                spotify_vis_config,
                'osc_glow_reactivity',
                tab._config_float('spotify_visualizer', spotify_vis_config, 'osc_glow_size', 1.0),
            ) * 100
        )
        tab.osc_glow_reactivity.setValue(max(0, min(200, osc_gr_val)))
        tab.osc_glow_reactivity_label.setText(f"{osc_gr_val}%")
    if hasattr(tab, 'osc_reactive_glow'):
        tab.osc_reactive_glow.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'osc_reactive_glow', True)
        )
    if hasattr(tab, 'osc_line_amplitude'):
        osc_amp_val = int(
            tab._config_float(
                'spotify_visualizer',
                spotify_vis_config,
                'osc_line_amplitude',
                tab._config_float('spotify_visualizer', spotify_vis_config, 'osc_sensitivity', 3.0),
            )
            * 10
        )
        tab.osc_line_amplitude.setValue(max(5, min(100, osc_amp_val)))
        tab.osc_line_amplitude_label.setText(f"{osc_amp_val / 10.0:.1f}x")
    if hasattr(tab, 'osc_smoothing'):
        osc_smooth_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'osc_smoothing', 0.7) * 100)
        tab.osc_smoothing.setValue(max(0, min(100, osc_smooth_val)))
        tab.osc_smoothing_label.setText(f"{osc_smooth_val}%")
    if hasattr(tab, 'osc_growth'):
        osc_growth_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'osc_growth', 1.0) * 100)
        tab.osc_growth.setValue(max(100, min(500, osc_growth_val)))
        tab.osc_growth_label.setText(f"{osc_growth_val / 100.0:.1f}x")
    if hasattr(tab, 'osc_speed'):
        osc_speed_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'osc_speed', 1.0) * 100)
        tab.osc_speed.setValue(max(10, min(100, osc_speed_val)))
        tab.osc_speed_label.setText(f"{osc_speed_val}%")
    if hasattr(tab, 'osc_line_dim'):
        tab.osc_line_dim.setChecked(bool(spotify_vis_config.get('osc_line_dim', False)))
    if hasattr(tab, 'osc_line_offset_bias'):
        osc_lob_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'osc_line_offset_bias', 0.0) * 100)
        tab.osc_line_offset_bias.setValue(max(0, min(100, osc_lob_val)))
        tab.osc_line_offset_bias_label.setText(f"{osc_lob_val}%")
    if hasattr(tab, 'osc_vertical_shift'):
        osc_vs = int(spotify_vis_config.get('osc_vertical_shift', 0))
        if isinstance(spotify_vis_config.get('osc_vertical_shift'), bool):
            osc_vs = 100 if spotify_vis_config.get('osc_vertical_shift') else 0
        tab.osc_vertical_shift.setValue(max(-50, min(200, osc_vs)))
        tab.osc_vertical_shift_label.setText(f"{osc_vs}")
    if hasattr(tab, 'spectrum_growth'):
        spectrum_growth_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'spectrum_growth', 1.0) * 100)
        tab.spectrum_growth.setValue(max(100, min(500, spectrum_growth_val)))
        tab.spectrum_growth_label.setText(f"{spectrum_growth_val / 100.0:.1f}x")
    if hasattr(tab, 'spectrum_single_piece'):
        tab.spectrum_single_piece.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'spectrum_single_piece', False)
        )
    if hasattr(tab, 'spectrum_rainbow_per_bar'):
        tab.spectrum_rainbow_per_bar.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'spectrum_rainbow_per_bar', False)
        )
    if hasattr(tab, 'spectrum_bass_emphasis'):
        _be = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'spectrum_bass_emphasis', 0.50) * 100)
        tab.spectrum_bass_emphasis.setValue(max(0, min(100, _be)))
        tab.spectrum_bass_emphasis_label.setText(f"{_be}%")
    if hasattr(tab, 'spectrum_vocal_position'):
        _vp = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'spectrum_vocal_position', 0.40) * 100)
        tab.spectrum_vocal_position.setValue(max(20, min(60, _vp)))
    if hasattr(tab, 'spectrum_mid_suppression'):
        _ms = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'spectrum_mid_suppression', 0.50) * 100)
        tab.spectrum_mid_suppression.setValue(max(0, min(100, _ms)))
        tab.spectrum_mid_suppression_label.setText(f"{_ms}%")
    if hasattr(tab, 'spectrum_wave_amplitude'):
        _wa = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'spectrum_wave_amplitude', 0.50) * 100)
        tab.spectrum_wave_amplitude.setValue(max(0, min(100, _wa)))
        tab.spectrum_wave_amplitude_label.setText(f"{_wa}%")
    if hasattr(tab, 'spectrum_profile_floor'):
        _pf = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'spectrum_profile_floor', 0.12) * 100)
        tab.spectrum_profile_floor.setValue(max(5, min(30, _pf)))
        tab.spectrum_profile_floor_label.setText(f"{_pf / 100.0:.2f}")
    if hasattr(tab, 'spectrum_drop_speed'):
        _ds = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'spectrum_drop_speed', 1.0) * 100)
        tab.spectrum_drop_speed.setValue(max(50, min(300, _ds)))
        tab.spectrum_drop_speed_label.setText(f"{_ds / 100.0:.1f}x")
    if hasattr(tab, 'spectrum_border_radius'):
        br_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'spectrum_border_radius', 0.0))
        tab.spectrum_border_radius.setValue(max(0, min(12, br_val)))
        tab.spectrum_border_radius_label.setText(f"{br_val}px")
    if hasattr(tab, 'spectrum_glow_enabled'):
        tab.spectrum_glow_enabled.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'spectrum_glow_enabled', False)
        )
    if hasattr(tab, 'spectrum_glow_intensity'):
        sg_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'spectrum_glow_intensity', 0.55) * 100)
        tab.spectrum_glow_intensity.setValue(max(0, min(150, sg_val)))
        tab.spectrum_glow_intensity_label.setText(f"{sg_val}%")
    spectrum_glow_color_data = spotify_vis_config.get('spectrum_glow_color', [110, 220, 255, 235])
    try:
        tab._spectrum_glow_color = QColor(*spectrum_glow_color_data)
    except Exception:
        logger.debug("[MEDIA_TAB] Failed to set spectrum_glow_color=%s", spectrum_glow_color_data, exc_info=True)
        tab._spectrum_glow_color = QColor(110, 220, 255, 235)
    _apply_color_to_button('spectrum_glow_color_btn', '_spectrum_glow_color')
    if hasattr(tab, 'spectrum_mirrored'):
        tab.spectrum_mirrored.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'spectrum_mirrored', True)
        )
    if hasattr(tab, 'spectrum_shape_editor'):
        _default_nodes = [[0.0, 0.45], [0.4, 0.62], [1.0, 0.70]]
        _saved_nodes = spotify_vis_config.get('spectrum_shape_nodes', _default_nodes)
        if isinstance(_saved_nodes, list) and len(_saved_nodes) >= 1:
            tab.spectrum_shape_editor.set_nodes(_saved_nodes)
        tab.spectrum_shape_editor.set_mirrored(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'spectrum_mirrored', True)
        )
        _notch_mir = spotify_vis_config.get('spectrum_notch_positions_mirrored', None)
        if isinstance(_notch_mir, list) and len(_notch_mir) >= 2:
            tab.spectrum_shape_editor.set_notch_positions(_notch_mir, mirrored=True)
        _notch_lin = spotify_vis_config.get('spectrum_notch_positions_linear', None)
        if isinstance(_notch_lin, list) and len(_notch_lin) >= 2:
            tab.spectrum_shape_editor.set_notch_positions(_notch_lin, mirrored=False)

    # Oscilloscope colours
    osc_line_color_data = spotify_vis_config.get('osc_line_color', [255, 255, 255, 255])
    try:
        tab._osc_line_color = QColor(*osc_line_color_data)
    except Exception:
        logger.debug("[MEDIA_TAB] Failed to set osc_line_color=%s", osc_line_color_data, exc_info=True)
        tab._osc_line_color = QColor(255, 255, 255, 255)
    osc_glow_color_data = spotify_vis_config.get('osc_glow_color', [0, 200, 255, 230])
    try:
        tab._osc_glow_color = QColor(*osc_glow_color_data)
    except Exception:
        logger.debug("[MEDIA_TAB] Failed to set osc_glow_color=%s", osc_glow_color_data, exc_info=True)
        tab._osc_glow_color = QColor(0, 200, 255, 230)
    _apply_color_to_button('osc_line_color_btn', '_osc_line_color')
    _apply_color_to_button('osc_glow_color_btn', '_osc_glow_color')

    # Multi-line
    osc_line_count = int(spotify_vis_config.get('osc_line_count', 1))
    if hasattr(tab, 'osc_multi_line'):
        tab.osc_multi_line.setChecked(osc_line_count > 1)
    if hasattr(tab, 'osc_line_count'):
        tab.osc_line_count.setValue(max(2, min(3, osc_line_count)))
        tab.osc_line_count_label.setText(str(max(2, min(3, osc_line_count))))
    apply_bindings_load(tab, spotify_vis_config, _OSC_MULTI_LINE_COLOR_BINDINGS)
    _apply_color_to_button('osc_line2_color_btn', '_osc_line2_color')
    _apply_color_to_button('osc_line2_glow_btn', '_osc_line2_glow_color')
    _apply_color_to_button('osc_line3_color_btn', '_osc_line3_color')
    _apply_color_to_button('osc_line3_glow_btn', '_osc_line3_glow_color')
    _update_osc_multi_line_visibility(tab)

    # Sine Wave settings
    if hasattr(tab, 'sine_glow_enabled'):
        tab.sine_glow_enabled.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'sine_glow_enabled', True)
        )
    if hasattr(tab, 'sine_glow_intensity'):
        sine_gi_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_glow_intensity', 0.5) * 100)
        tab.sine_glow_intensity.setValue(max(0, min(100, sine_gi_val)))
        tab.sine_glow_intensity_label.setText(f"{sine_gi_val}%")
    if hasattr(tab, 'sine_glow_reactivity'):
        sine_gr_val = int(
            tab._config_float(
                'spotify_visualizer',
                spotify_vis_config,
                'sine_glow_reactivity',
                tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_glow_size', 1.0),
            ) * 100
        )
        tab.sine_glow_reactivity.setValue(max(0, min(200, sine_gr_val)))
        tab.sine_glow_reactivity_label.setText(f"{sine_gr_val}%")
    sine_glow_color_data = spotify_vis_config.get('sine_glow_color', [0, 200, 255, 230])
    try:
        tab._sine_glow_color = QColor(*sine_glow_color_data)
    except Exception:
        logger.debug("[MEDIA_TAB] Failed to set sine_glow_color=%s", sine_glow_color_data, exc_info=True)
        tab._sine_glow_color = QColor(0, 200, 255, 230)
    _apply_color_to_button('sine_glow_color_btn', '_sine_glow_color')
    sine_line_color_data = spotify_vis_config.get('sine_line_color', [255, 255, 255, 255])
    try:
        tab._sine_line_color = QColor(*sine_line_color_data)
    except Exception:
        logger.debug("[MEDIA_TAB] Failed to set sine_line_color=%s", sine_line_color_data, exc_info=True)
        tab._sine_line_color = QColor(255, 255, 255, 255)
    _apply_color_to_button('sine_line_color_btn', '_sine_line_color')
    if hasattr(tab, 'sine_reactive_glow'):
        tab.sine_reactive_glow.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'sine_reactive_glow', True)
        )
    if hasattr(tab, 'sine_sensitivity'):
        sine_sens_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_sensitivity', 1.0) * 100)
        tab.sine_sensitivity.setValue(max(10, min(500, sine_sens_val)))
        tab.sine_sensitivity_label.setText(f"{sine_sens_val / 100.0:.2f}x")
    if hasattr(tab, 'sine_speed'):
        sine_speed_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_speed', 1.0) * 100)
        tab.sine_speed.setValue(max(10, min(100, sine_speed_val)))
        tab.sine_speed_label.setText(f"{sine_speed_val / 100.0:.2f}x")
    if hasattr(tab, 'sine_wave_effect'):
        sine_wfx = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_wave_effect',
                       tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_wobble_amount', 0.0)) * 100)
        tab.sine_wave_effect.setValue(max(0, min(100, sine_wfx)))
        tab.sine_wave_effect_label.setText(f"{sine_wfx}%")
    if hasattr(tab, 'sine_micro_wobble'):
        sine_mw_default = tab._default_float('spotify_visualizer', 'sine_micro_wobble', 0.0)
        sine_mw = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_micro_wobble', sine_mw_default) * 100)
        tab.sine_micro_wobble.setValue(max(0, min(100, sine_mw)))
        tab.sine_micro_wobble_label.setText(f"{sine_mw}%")
    if hasattr(tab, 'sine_crawl_slider'):
        sine_crawl_default = tab._default_float('spotify_visualizer', 'sine_crawl_amount', 0.25)
        sine_crawl = int(tab._config_float(
            'spotify_visualizer', spotify_vis_config, 'sine_crawl_amount', sine_crawl_default
        ) * 100)
        tab.sine_crawl_slider.setValue(max(0, min(100, sine_crawl)))
        tab.sine_crawl_label.setText(f"{sine_crawl}%")
    if hasattr(tab, 'sine_width_reaction'):
        sine_wr = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_width_reaction', 0.0) * 100)
        tab.sine_width_reaction.setValue(max(0, min(100, sine_wr)))
        tab.sine_width_reaction_label.setText(f"{sine_wr}%")
    if hasattr(tab, 'sine_vertical_shift'):
        sine_vs = int(spotify_vis_config.get('sine_vertical_shift', 0))
        if isinstance(spotify_vis_config.get('sine_vertical_shift'), bool):
            sine_vs = 100 if spotify_vis_config.get('sine_vertical_shift') else 0
        tab.sine_vertical_shift.setValue(max(-50, min(200, sine_vs)))
        tab.sine_vertical_shift_label.setText(f"{sine_vs}")
    if hasattr(tab, 'sine_line1_shift'):
        sine_l1_shift = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_line1_shift', 0.0) * 100)
        tab.sine_line1_shift.setValue(max(-100, min(100, sine_l1_shift)))
        tab.sine_line1_shift_label.setText(f"{sine_l1_shift / 100.0:.2f} cycles")
    if hasattr(tab, 'sine_travel'):
        sine_travel_val = int(spotify_vis_config.get('sine_wave_travel', 0) or 0)
        tab.sine_travel.setCurrentIndex(max(0, min(2, sine_travel_val)))
    if hasattr(tab, 'sine_travel_line2'):
        stl2 = int(spotify_vis_config.get('sine_travel_line2', 0) or 0)
        tab.sine_travel_line2.setCurrentIndex(max(0, min(2, stl2)))
    if hasattr(tab, 'sine_travel_line3'):
        stl3 = int(spotify_vis_config.get('sine_travel_line3', 0) or 0)
        tab.sine_travel_line3.setCurrentIndex(max(0, min(2, stl3)))
    if hasattr(tab, 'sine_multi_line'):
        sine_lc = int(spotify_vis_config.get('sine_line_count', 1) or 1)
        tab.sine_multi_line.setChecked(sine_lc > 1)
    if hasattr(tab, 'sine_line_count_slider'):
        sine_lc = int(spotify_vis_config.get('sine_line_count', 2) or 2)
        tab.sine_line_count_slider.setValue(max(2, min(3, sine_lc)))
        tab.sine_line_count_label.setText(str(max(2, min(3, sine_lc))))
    # Sine line 2/3 colours
    for attr, key, fallback in (
        ('_sine_line2_color', 'sine_line2_color', [255, 120, 50, 230]),
        ('_sine_line2_glow_color', 'sine_line2_glow_color', [255, 120, 50, 180]),
        ('_sine_line3_color', 'sine_line3_color', [50, 255, 120, 230]),
        ('_sine_line3_glow_color', 'sine_line3_glow_color', [50, 255, 120, 180]),
    ):
        data = spotify_vis_config.get(key, fallback)
        try:
            setattr(tab, attr, QColor(*data))
        except Exception:
            logger.debug("[MEDIA_TAB] Failed to set %s=%s", attr, data, exc_info=True)
            setattr(tab, attr, QColor(*fallback))
    _apply_color_to_button('sine_line2_color_btn', '_sine_line2_color')
    _apply_color_to_button('sine_line2_glow_btn', '_sine_line2_glow_color')
    _apply_color_to_button('sine_line3_color_btn', '_sine_line3_color')
    _apply_color_to_button('sine_line3_glow_btn', '_sine_line3_glow_color')
    _update_sine_multi_line_visibility(tab)
    if hasattr(tab, 'sine_line2_shift'):
        sine_l2_shift = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_line2_shift', 0.0) * 100)
        tab.sine_line2_shift.setValue(max(-100, min(100, sine_l2_shift)))
        tab.sine_line2_shift_label.setText(f"{sine_l2_shift / 100.0:.2f} cycles")
    if hasattr(tab, 'sine_line3_shift'):
        sine_l3_shift = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_line3_shift', 0.0) * 100)
        tab.sine_line3_shift.setValue(max(-100, min(100, sine_l3_shift)))
        tab.sine_line3_shift_label.setText(f"{sine_l3_shift / 100.0:.2f} cycles")
    if hasattr(tab, 'sine_line_offset_bias'):
        sine_lob_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_line_offset_bias', 0.0) * 100)
        tab.sine_line_offset_bias.setValue(max(0, min(100, sine_lob_val)))
        tab.sine_line_offset_bias_label.setText(f"{sine_lob_val}%")
    if hasattr(tab, 'sine_card_adaptation'):
        sine_adapt = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_card_adaptation', 0.30) * 100)
        tab.sine_card_adaptation.setValue(max(5, min(100, sine_adapt)))
        tab.sine_card_adaptation_label.setText(f"{sine_adapt}%")
    if hasattr(tab, 'sine_wave_growth'):
        sine_gv = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_wave_growth', 1.0) * 100)
        tab.sine_wave_growth.setValue(max(100, min(500, sine_gv)))
        tab.sine_wave_growth_label.setText(f"{sine_gv / 100.0:.1f}x")

    # Update per-mode section visibility
    tab._update_vis_mode_sections()

    # Ghosting (prefer mode-specific spectrum keys, fall back to global)
    _ghost_en = spotify_vis_config.get(
        'spectrum_ghosting_enabled',
        tab._config_bool('spotify_visualizer', spotify_vis_config, 'ghosting_enabled', True),
    )
    tab.vis_ghost_enabled.setChecked(bool(_ghost_en))
    _ghost_a = float(spotify_vis_config.get(
        'spectrum_ghost_alpha',
        tab._config_float('spotify_visualizer', spotify_vis_config, 'ghost_alpha', 0.4),
    ))
    ghost_alpha_pct = max(0, min(100, int(_ghost_a * 100)))
    tab.vis_ghost_opacity_slider.setValue(ghost_alpha_pct)
    tab.vis_ghost_opacity_label.setText(f"{ghost_alpha_pct}%")

    _ghost_d = float(spotify_vis_config.get(
        'spectrum_ghost_decay',
        tab._config_float('spotify_visualizer', spotify_vis_config, 'ghost_decay', 0.4),
    ))
    ghost_decay_slider = max(10, min(100, int(_ghost_d * 100.0)))
    tab.vis_ghost_decay_slider.setValue(ghost_decay_slider)
    tab.vis_ghost_decay_label.setText(f"{ghost_decay_slider / 100.0:.2f}x")
    _update_ghost_visibility(tab)

    # Sine Density / Heartbeat / Displacement
    if hasattr(tab, 'sine_density'):
        sd = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_density', 1.0) * 100)
        tab.sine_density.setValue(max(25, min(300, sd)))
        tab.sine_density_label.setText(f"{tab.sine_density.value() / 100.0:.2f}×")
    if hasattr(tab, 'sine_heartbeat'):
        shb = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_heartbeat', 0.0) * 100)
        tab.sine_heartbeat.setValue(max(0, min(100, shb)))
        tab.sine_heartbeat_label.setText(f"{shb}%")
    if hasattr(tab, 'sine_displacement'):
        sdp = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_displacement', 0.0) * 100)
        tab.sine_displacement.setValue(max(0, min(100, sdp)))
        tab.sine_displacement_label.setText(f"{sdp}%")

    # Oscilloscope ghost trail
    if hasattr(tab, 'osc_ghost_enabled'):
        tab.osc_ghost_enabled.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'osc_ghosting_enabled', False)
        )
    if hasattr(tab, 'osc_ghost_intensity'):
        gi = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'osc_ghost_intensity', 0.4) * 100)
        tab.osc_ghost_intensity.setValue(max(5, min(100, gi)))
        tab.osc_ghost_intensity_label.setText(f"{gi}%")
    if hasattr(tab, 'osc_ghost_line2_enabled'):
        tab.osc_ghost_line2_enabled.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'osc_ghost_line2_enabled', True)
        )
    if hasattr(tab, 'osc_ghost_line3_enabled'):
        tab.osc_ghost_line3_enabled.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'osc_ghost_line3_enabled', True)
        )

    load_blob_mode_settings(
        tab,
        spotify_vis_config,
        sync_color_button=_apply_color_to_button,
    )

    # Sine wave ghost
    if hasattr(tab, 'sine_ghost_enabled'):
        tab.sine_ghost_enabled.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'sine_ghosting_enabled', True)
        )
    if hasattr(tab, 'sine_ghost_opacity'):
        sga = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_ghost_alpha', 0.45) * 100)
        tab.sine_ghost_opacity.setValue(max(0, min(100, sga)))
        tab.sine_ghost_opacity_label.setText(f"{sga}%")
    if hasattr(tab, 'sine_ghost_decay_slider'):
        sgd = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'sine_ghost_decay', 0.3) * 100)
        tab.sine_ghost_decay_slider.setValue(max(10, min(100, sgd)))
        tab.sine_ghost_decay_label.setText(f"{sgd / 100.0:.2f}x")
    if hasattr(tab, 'sine_ghost_line2_enabled'):
        tab.sine_ghost_line2_enabled.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'sine_ghost_line2_enabled', True)
        )
    if hasattr(tab, 'sine_ghost_line3_enabled'):
        tab.sine_ghost_line3_enabled.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'sine_ghost_line3_enabled', True)
        )

    # Bubble ghost
    if hasattr(tab, 'bubble_ghost_enabled'):
        tab.bubble_ghost_enabled.setChecked(
            tab._config_bool('spotify_visualizer', spotify_vis_config, 'bubble_ghosting_enabled', False)
        )
    if hasattr(tab, 'bubble_ghost_opacity'):
        buga = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'bubble_ghost_alpha', 0.0) * 100)
        tab.bubble_ghost_opacity.setValue(max(0, min(100, buga)))
        tab.bubble_ghost_opacity_label.setText(f"{buga}%")
    if hasattr(tab, 'bubble_ghost_decay_slider'):
        bugd = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'bubble_ghost_decay', 0.4) * 100)
        tab.bubble_ghost_decay_slider.setValue(max(10, min(100, bugd)))
        tab.bubble_ghost_decay_label.setText(f"{bugd / 100.0:.2f}x")

    load_visualizer_rainbow_state(tab, spotify_vis_config)

    # Bubble settings load
    if hasattr(tab, 'bubble_big_bass_pulse'):
        v = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'bubble_big_bass_pulse', 0.5) * 100)
        tab.bubble_big_bass_pulse.setValue(max(0, min(200, v)))
        tab.bubble_big_bass_pulse_label.setText(f"{v}%")
    if hasattr(tab, 'bubble_small_freq_pulse'):
        v = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'bubble_small_freq_pulse', 0.5) * 100)
        tab.bubble_small_freq_pulse.setValue(max(0, min(200, v)))
        tab.bubble_small_freq_pulse_label.setText(f"{v}%")
    if hasattr(tab, 'bubble_stream_direction'):
        sd = tab._config_str('spotify_visualizer', spotify_vis_config, 'bubble_stream_direction', 'up').lower()
        sd_map = {"none": 0, "up": 1, "down": 2, "left": 3, "right": 4, "diagonal": 5, "random": 6}
        tab.bubble_stream_direction.setCurrentIndex(sd_map.get(sd, 1))
    if hasattr(tab, 'bubble_stream_constant_speed'):
        v = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'bubble_stream_constant_speed', 0.5) * 100)
        tab.bubble_stream_constant_speed.setValue(max(0, min(200, v)))
        tab.bubble_stream_constant_speed_label.setText(f"{v}%")
    if hasattr(tab, 'bubble_stream_speed_cap'):
        v = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'bubble_stream_speed_cap', 2.0) * 100)
        tab.bubble_stream_speed_cap.setValue(max(50, min(400, v)))
        tab.bubble_stream_speed_cap_label.setText(f"{v}%")
    if hasattr(tab, 'bubble_stream_reactivity'):
        v = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'bubble_stream_reactivity', 0.5) * 100)
        clamped_v = max(0, min(200, v))
        tab.bubble_stream_reactivity.setValue(clamped_v)
        tab.bubble_stream_reactivity_label.setText(f"{clamped_v}%")
    if hasattr(tab, 'bubble_rotation_amount'):
        v = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'bubble_rotation_amount', 0.5) * 100)
        tab.bubble_rotation_amount.setValue(max(0, min(100, v)))
        tab.bubble_rotation_amount_label.setText(f"{v}%")
    if hasattr(tab, 'bubble_drift_amount'):
        v = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'bubble_drift_amount', 0.5) * 100)
        tab.bubble_drift_amount.setValue(max(0, min(100, v)))
        tab.bubble_drift_amount_label.setText(f"{v}%")
    if hasattr(tab, 'bubble_drift_speed'):
        v = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'bubble_drift_speed', 0.5) * 100)
        tab.bubble_drift_speed.setValue(max(0, min(100, v)))
        tab.bubble_drift_speed_label.setText(f"{v}%")
    if hasattr(tab, 'bubble_drift_frequency'):
        v = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'bubble_drift_frequency', 0.5) * 100)
        tab.bubble_drift_frequency.setValue(max(0, min(100, v)))
        tab.bubble_drift_frequency_label.setText(f"{v}%")
    if hasattr(tab, 'bubble_drift_direction'):
        dd = tab._config_str('spotify_visualizer', spotify_vis_config, 'bubble_drift_direction', 'random').lower()
        is_swirl = dd in ('swirl_cw', 'swirl_ccw')
        # Restore swirl checkbox + combo
        if hasattr(tab, 'bubble_swirl_enabled'):
            tab.bubble_swirl_enabled.setChecked(is_swirl)
        if hasattr(tab, 'bubble_swirl_direction') and is_swirl:
            sd_idx = tab.bubble_swirl_direction.findData(dd)
            if sd_idx >= 0:
                tab.bubble_swirl_direction.setCurrentIndex(sd_idx)
        # Restore drift direction combo (use 'none' if swirl active)
        combo = tab.bubble_drift_direction
        if is_swirl:
            idx = combo.findData('none')
        else:
            idx = combo.findData(dd)
        if idx < 0:
            idx = combo.findData('random')
        if idx < 0:
            idx = 0
        combo.setCurrentIndex(idx)
    if hasattr(tab, 'bubble_big_count'):
        v = tab._config_int('spotify_visualizer', spotify_vis_config, 'bubble_big_count', 8)
        tab.bubble_big_count.setValue(max(1, min(30, v)))
        tab.bubble_big_count_label.setText(str(v))
    if hasattr(tab, 'bubble_small_count'):
        v = tab._config_int('spotify_visualizer', spotify_vis_config, 'bubble_small_count', 25)
        tab.bubble_small_count.setValue(max(5, min(80, v)))
        tab.bubble_small_count_label.setText(str(v))
    if hasattr(tab, 'bubble_surface_reach'):
        v = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'bubble_surface_reach', 0.6) * 100)
        tab.bubble_surface_reach.setValue(max(0, min(100, v)))
        tab.bubble_surface_reach_label.setText(f"{v}%")
    if hasattr(tab, 'bubble_specular_direction'):
        sd = tab._config_str('spotify_visualizer', spotify_vis_config, 'bubble_specular_direction', 'top_left').lower()
        combo = tab.bubble_specular_direction
        idx = combo.findData(sd)
        if idx < 0:
            idx = combo.findData('top_left')
        if idx < 0:
            idx = 0
        combo.setCurrentIndex(idx)
    if hasattr(tab, 'bubble_gradient_direction'):
        gd = tab._config_str('spotify_visualizer', spotify_vis_config, 'bubble_gradient_direction', 'top').lower()
        combo = tab.bubble_gradient_direction
        idx = combo.findData(gd)
        if idx < 0:
            idx = combo.findData('top')
        if idx < 0:
            idx = 0
        combo.setCurrentIndex(idx)
    if hasattr(tab, 'bubble_big_size_max'):
        v = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'bubble_big_size_max', 0.038) * 1000)
        tab.bubble_big_size_max.setValue(max(10, min(60, v)))
        tab.bubble_big_size_max_label.setText(str(v))
    if hasattr(tab, 'bubble_small_size_max'):
        v = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'bubble_small_size_max', 0.018) * 1000)
        tab.bubble_small_size_max.setValue(max(4, min(30, v)))
        tab.bubble_small_size_max_label.setText(str(v))
    if hasattr(tab, 'bubble_big_specular_max_size'):
        v = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'bubble_big_specular_max_size', 2.5) * 100)
        tab.bubble_big_specular_max_size.setValue(max(50, min(500, v)))
        tab.bubble_big_specular_max_size_label.setText(f"{v / 100.0:.1f}x")
    if hasattr(tab, 'bubble_big_size_clamp'):
        v = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'bubble_big_size_clamp', 4.0) * 100)
        tab.bubble_big_size_clamp.setValue(max(150, min(800, v)))
        tab.bubble_big_size_clamp_label.setText(f"{v / 100.0:.1f}x")
    if hasattr(tab, 'bubble_big_contraction_bias'):
        v = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'bubble_big_contraction_bias', 1.0) * 100)
        tab.bubble_big_contraction_bias.setValue(max(0, min(100, v)))
        tab.bubble_big_contraction_bias_label.setText(f"{v}%")
    if hasattr(tab, 'bubble_growth'):
        bubble_growth_val = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'bubble_growth', 3.0) * 100)
        tab.bubble_growth.setValue(max(100, min(500, bubble_growth_val)))
        tab.bubble_growth_label.setText(f"{bubble_growth_val / 100.0:.1f}x")
    if hasattr(tab, 'bubble_trail_strength'):
        v = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'bubble_trail_strength', 0.0) * 100)
        tab.bubble_trail_strength.setValue(max(0, min(150, v)))
        tab.bubble_trail_strength_label.setText(f"{v}%")
    if hasattr(tab, 'bubble_tail_opacity'):
        v = int(tab._config_float('spotify_visualizer', spotify_vis_config, 'bubble_tail_opacity', 0.0) * 100)
        tab.bubble_tail_opacity.setValue(max(0, min(85, v)))
        tab.bubble_tail_opacity_label.setText(f"{v}%")
    # Bubble colours
    for attr, key, default in (
        ('_bubble_outline_color', 'bubble_outline_color', [255, 255, 255, 230]),
        ('_bubble_specular_color', 'bubble_specular_color', [255, 255, 255, 255]),
        ('_bubble_gradient_light', 'bubble_gradient_light', [210, 170, 120, 255]),
        ('_bubble_gradient_dark', 'bubble_gradient_dark', [80, 60, 50, 255]),
        ('_bubble_pop_color', 'bubble_pop_color', [255, 255, 255, 180]),
    ):
        cd = spotify_vis_config.get(key, default)
        try:
            setattr(tab, attr, QColor(*cd))
        except Exception:
            logger.debug("[MEDIA_TAB] Failed to set %s=%s", attr, cd, exc_info=True)
            setattr(tab, attr, QColor(*default))
    _apply_color_to_button('bubble_outline_color_btn', '_bubble_outline_color')
    _apply_color_to_button('bubble_specular_color_btn', '_bubble_specular_color')
    _apply_color_to_button('bubble_gradient_light_btn', '_bubble_gradient_light')
    _apply_color_to_button('bubble_gradient_dark_btn', '_bubble_gradient_dark')
    _apply_color_to_button('bubble_pop_color_btn', '_bubble_pop_color')

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
        'intense_shadow': tab.media_intense_shadow.isChecked(),
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
        'osc_glow_enabled': tab.osc_glow_enabled.isChecked() if hasattr(tab, 'osc_glow_enabled') else True,
        'osc_glow_intensity': (tab.osc_glow_intensity.value() if hasattr(tab, 'osc_glow_intensity') else 50) / 100.0,
        'osc_glow_reactivity': (tab.osc_glow_reactivity.value() if hasattr(tab, 'osc_glow_reactivity') else 100) / 100.0,
        'osc_reactive_glow': tab.osc_reactive_glow.isChecked() if hasattr(tab, 'osc_reactive_glow') else True,
        'osc_line_amplitude': (tab.osc_line_amplitude.value() if hasattr(tab, 'osc_line_amplitude') else 30) / 10.0,
        'osc_smoothing': (tab.osc_smoothing.value() if hasattr(tab, 'osc_smoothing') else 70) / 100.0,
        'osc_line_color': _qcolor_to_list(getattr(tab, '_osc_line_color', None), [255, 255, 255, 255]),
        'osc_glow_color': _qcolor_to_list(getattr(tab, '_osc_glow_color', None), [0, 200, 255, 230]),
        'osc_line_count': (tab.osc_line_count.value() if hasattr(tab, 'osc_line_count') and hasattr(tab, 'osc_multi_line') and tab.osc_multi_line.isChecked() else 1),
        'spectrum_growth': (tab.spectrum_growth.value() if hasattr(tab, 'spectrum_growth') else 100) / 100.0,
        'spectrum_single_piece': tab.spectrum_single_piece.isChecked() if hasattr(tab, 'spectrum_single_piece') else False,
        'spectrum_rainbow_per_bar': tab.spectrum_rainbow_per_bar.isChecked() if hasattr(tab, 'spectrum_rainbow_per_bar') else False,
        'spectrum_border_radius': float(tab.spectrum_border_radius.value()) if hasattr(tab, 'spectrum_border_radius') else 0.0,
        'spectrum_glow_enabled': tab.spectrum_glow_enabled.isChecked() if hasattr(tab, 'spectrum_glow_enabled') else False,
        'spectrum_glow_intensity': (tab.spectrum_glow_intensity.value() if hasattr(tab, 'spectrum_glow_intensity') else 55) / 100.0,
        'spectrum_glow_color': _qcolor_to_list(getattr(tab, '_spectrum_glow_color', None), [110, 220, 255, 235]),
        'spectrum_mirrored': tab.spectrum_mirrored.isChecked() if hasattr(tab, 'spectrum_mirrored') else True,
        'spectrum_shape_nodes': tab.spectrum_shape_editor.get_nodes() if hasattr(tab, 'spectrum_shape_editor') else [[0.0, 0.40], [0.35, 0.75], [0.65, 0.55], [1.0, 0.80]],
        'spectrum_notch_positions_mirrored': tab.spectrum_shape_editor._notches_mirrored if hasattr(tab, 'spectrum_shape_editor') else [[0.0, "Mid"], [0.30, "Vocal"], [0.65, "Low-Mid"], [1.0, "Bass"]],
        'spectrum_notch_positions_linear': tab.spectrum_shape_editor._notches_linear if hasattr(tab, 'spectrum_shape_editor') else [[0.0, "Bass"], [0.25, "Low"], [0.50, "Mid"], [0.75, "Hi-Mid"], [1.0, "Treble"]],
        'spectrum_bass_emphasis': (tab.spectrum_bass_emphasis.value() if hasattr(tab, 'spectrum_bass_emphasis') else 50) / 100.0,
        'spectrum_vocal_position': (tab.spectrum_vocal_position.value() if hasattr(tab, 'spectrum_vocal_position') else 40) / 100.0,
        'spectrum_mid_suppression': (tab.spectrum_mid_suppression.value() if hasattr(tab, 'spectrum_mid_suppression') else 50) / 100.0,
        'spectrum_wave_amplitude': (tab.spectrum_wave_amplitude.value() if hasattr(tab, 'spectrum_wave_amplitude') else 50) / 100.0,
        'spectrum_profile_floor': (tab.spectrum_profile_floor.value() if hasattr(tab, 'spectrum_profile_floor') else 12) / 100.0,
        'spectrum_drop_speed': (tab.spectrum_drop_speed.value() if hasattr(tab, 'spectrum_drop_speed') else 100) / 100.0,
        'osc_growth': (tab.osc_growth.value() if hasattr(tab, 'osc_growth') else 100) / 100.0,
        'osc_speed': (tab.osc_speed.value() if hasattr(tab, 'osc_speed') else 100) / 100.0,
        'osc_line_dim': tab.osc_line_dim.isChecked() if hasattr(tab, 'osc_line_dim') else False,
        'osc_line_offset_bias': (tab.osc_line_offset_bias.value() if hasattr(tab, 'osc_line_offset_bias') else 0) / 100.0,
        'osc_vertical_shift': tab.osc_vertical_shift.value() if hasattr(tab, 'osc_vertical_shift') else 0,
        'sine_glow_enabled': tab.sine_glow_enabled.isChecked() if hasattr(tab, 'sine_glow_enabled') else True,
        'sine_glow_intensity': (tab.sine_glow_intensity.value() if hasattr(tab, 'sine_glow_intensity') else 50) / 100.0,
        'sine_glow_reactivity': (tab.sine_glow_reactivity.value() if hasattr(tab, 'sine_glow_reactivity') else 100) / 100.0,
        'sine_glow_color': _qcolor_to_list(getattr(tab, '_sine_glow_color', None), [0, 200, 255, 230]),
        'sine_line_color': _qcolor_to_list(getattr(tab, '_sine_line_color', None), [255, 255, 255, 255]),
        'sine_reactive_glow': tab.sine_reactive_glow.isChecked() if hasattr(tab, 'sine_reactive_glow') else True,
        'sine_sensitivity': (tab.sine_sensitivity.value() if hasattr(tab, 'sine_sensitivity') else 100) / 100.0,
        'sine_speed': (tab.sine_speed.value() if hasattr(tab, 'sine_speed') else 100) / 100.0,
        'sine_wave_effect': (tab.sine_wave_effect.value() if hasattr(tab, 'sine_wave_effect') else 0) / 100.0,
        'sine_crawl_amount': (tab.sine_crawl_slider.value() if hasattr(tab, 'sine_crawl_slider') else 25) / 100.0,
        'sine_micro_wobble': (tab.sine_micro_wobble.value() if hasattr(tab, 'sine_micro_wobble') else 0) / 100.0,
        'sine_width_reaction': (tab.sine_width_reaction.value() if hasattr(tab, 'sine_width_reaction') else 0) / 100.0,
        'sine_density': (tab.sine_density.value() if hasattr(tab, 'sine_density') else 100) / 100.0,
        'sine_heartbeat': (tab.sine_heartbeat.value() if hasattr(tab, 'sine_heartbeat') else 0) / 100.0,
        'sine_displacement': (tab.sine_displacement.value() if hasattr(tab, 'sine_displacement') else 0) / 100.0,
        'sine_vertical_shift': tab.sine_vertical_shift.value() if hasattr(tab, 'sine_vertical_shift') else 0,
        'sine_line1_shift': (tab.sine_line1_shift.value() if hasattr(tab, 'sine_line1_shift') else 0) / 100.0,
        'sine_wave_travel': tab.sine_travel.currentIndex() if hasattr(tab, 'sine_travel') else 0,
        'sine_travel_line2': tab.sine_travel_line2.currentIndex() if hasattr(tab, 'sine_travel_line2') else 0,
        'sine_travel_line3': tab.sine_travel_line3.currentIndex() if hasattr(tab, 'sine_travel_line3') else 0,
        'sine_line_count': (tab.sine_line_count_slider.value() if hasattr(tab, 'sine_line_count_slider') else 2) if (hasattr(tab, 'sine_multi_line') and tab.sine_multi_line.isChecked()) else 1,
        'sine_line_dim': tab.sine_line_dim.isChecked() if hasattr(tab, 'sine_line_dim') else False,
        'sine_line_offset_bias': (tab.sine_line_offset_bias.value() if hasattr(tab, 'sine_line_offset_bias') else 0) / 100.0,
        'sine_card_adaptation': (tab.sine_card_adaptation.value() if hasattr(tab, 'sine_card_adaptation') else 30) / 100.0,
        'sine_wave_growth': (tab.sine_wave_growth.value() if hasattr(tab, 'sine_wave_growth') else 100) / 100.0,
        'sine_line2_color': _qcolor_to_list(getattr(tab, '_sine_line2_color', None), [255, 120, 50, 230]),
        'sine_line2_glow_color': _qcolor_to_list(getattr(tab, '_sine_line2_glow_color', None), [255, 120, 50, 180]),
        'sine_line3_color': _qcolor_to_list(getattr(tab, '_sine_line3_color', None), [50, 255, 120, 230]),
        'sine_line3_glow_color': _qcolor_to_list(getattr(tab, '_sine_line3_glow_color', None), [50, 255, 120, 180]),
        'sine_line2_shift': (tab.sine_line2_shift.value() if hasattr(tab, 'sine_line2_shift') else 0) / 100.0,
        'sine_line3_shift': (tab.sine_line3_shift.value() if hasattr(tab, 'sine_line3_shift') else 0) / 100.0,
        'rainbow_enabled': tab.rainbow_enabled.isChecked() if hasattr(tab, 'rainbow_enabled') else False,
        'rainbow_speed': (tab.rainbow_speed_slider.value() if hasattr(tab, 'rainbow_speed_slider') else 50) / 100.0,
    }
    collect_visualizer_rainbow_state(tab, spotify_vis_config)
    spotify_vis_config.update({
        'osc_ghosting_enabled': tab.osc_ghost_enabled.isChecked() if hasattr(tab, 'osc_ghost_enabled') else False,
        'osc_ghost_intensity': (tab.osc_ghost_intensity.value() if hasattr(tab, 'osc_ghost_intensity') else 40) / 100.0,
        'osc_ghost_line2_enabled': tab.osc_ghost_line2_enabled.isChecked() if hasattr(tab, 'osc_ghost_line2_enabled') else True,
        'osc_ghost_line3_enabled': tab.osc_ghost_line3_enabled.isChecked() if hasattr(tab, 'osc_ghost_line3_enabled') else True,
        'sine_ghosting_enabled': tab.sine_ghost_enabled.isChecked() if hasattr(tab, 'sine_ghost_enabled') else True,
        'sine_ghost_alpha': (tab.sine_ghost_opacity.value() if hasattr(tab, 'sine_ghost_opacity') else 45) / 100.0,
        'sine_ghost_decay': max(0.1, (tab.sine_ghost_decay_slider.value() if hasattr(tab, 'sine_ghost_decay_slider') else 30) / 100.0),
        'sine_ghost_line2_enabled': tab.sine_ghost_line2_enabled.isChecked() if hasattr(tab, 'sine_ghost_line2_enabled') else True,
        'sine_ghost_line3_enabled': tab.sine_ghost_line3_enabled.isChecked() if hasattr(tab, 'sine_ghost_line3_enabled') else True,
        'bubble_ghosting_enabled': tab.bubble_ghost_enabled.isChecked() if hasattr(tab, 'bubble_ghost_enabled') else False,
        'bubble_ghost_alpha': (tab.bubble_ghost_opacity.value() if hasattr(tab, 'bubble_ghost_opacity') else 0) / 100.0,
        'bubble_ghost_decay': max(0.1, (tab.bubble_ghost_decay_slider.value() if hasattr(tab, 'bubble_ghost_decay_slider') else 40) / 100.0),
        # Bubble
        'bubble_big_bass_pulse': (tab.bubble_big_bass_pulse.value() if hasattr(tab, 'bubble_big_bass_pulse') else 50) / 100.0,
        'bubble_small_freq_pulse': (tab.bubble_small_freq_pulse.value() if hasattr(tab, 'bubble_small_freq_pulse') else 50) / 100.0,
        'bubble_stream_direction': (tab.bubble_stream_direction.currentText().lower().replace(' ', '_') if hasattr(tab, 'bubble_stream_direction') else 'up'),
        'bubble_stream_constant_speed': (tab.bubble_stream_constant_speed.value() if hasattr(tab, 'bubble_stream_constant_speed') else 50) / 100.0,
        'bubble_stream_speed_cap': (tab.bubble_stream_speed_cap.value() if hasattr(tab, 'bubble_stream_speed_cap') else 200) / 100.0,
        'bubble_stream_reactivity': (tab.bubble_stream_reactivity.value() if hasattr(tab, 'bubble_stream_reactivity') else 50) / 100.0,
        'bubble_rotation_amount': (tab.bubble_rotation_amount.value() if hasattr(tab, 'bubble_rotation_amount') else 50) / 100.0,
        'bubble_drift_amount': (tab.bubble_drift_amount.value() if hasattr(tab, 'bubble_drift_amount') else 50) / 100.0,
        'bubble_drift_speed': (tab.bubble_drift_speed.value() if hasattr(tab, 'bubble_drift_speed') else 50) / 100.0,
        'bubble_drift_frequency': (tab.bubble_drift_frequency.value() if hasattr(tab, 'bubble_drift_frequency') else 50) / 100.0,
        'bubble_drift_direction': (
            (tab.bubble_swirl_direction.currentData() or 'swirl_cw')
            if hasattr(tab, 'bubble_swirl_enabled') and tab.bubble_swirl_enabled.isChecked()
            else (
                (tab.bubble_drift_direction.currentData() or 'random')
                if hasattr(tab, 'bubble_drift_direction') else 'random'
            )
        ),
        'bubble_big_count': tab.bubble_big_count.value() if hasattr(tab, 'bubble_big_count') else 8,
        'bubble_small_count': tab.bubble_small_count.value() if hasattr(tab, 'bubble_small_count') else 25,
        'bubble_surface_reach': (tab.bubble_surface_reach.value() if hasattr(tab, 'bubble_surface_reach') else 60) / 100.0,
        'bubble_outline_color': _qcolor_to_list(getattr(tab, '_bubble_outline_color', None), [255, 255, 255, 230]),
        'bubble_specular_color': _qcolor_to_list(getattr(tab, '_bubble_specular_color', None), [255, 255, 255, 255]),
        'bubble_gradient_light': _qcolor_to_list(getattr(tab, '_bubble_gradient_light', None), [210, 170, 120, 255]),
        'bubble_gradient_dark': _qcolor_to_list(getattr(tab, '_bubble_gradient_dark', None), [80, 60, 50, 255]),
        'bubble_pop_color': _qcolor_to_list(getattr(tab, '_bubble_pop_color', None), [255, 255, 255, 180]),
        'bubble_specular_direction': (
            tab.bubble_specular_direction.currentData()
            if hasattr(tab, 'bubble_specular_direction') else 'top_left'
        ),
        'bubble_gradient_direction': (
            tab.bubble_gradient_direction.currentData()
            if hasattr(tab, 'bubble_gradient_direction') else 'top'
        ),
        'bubble_big_size_max': (tab.bubble_big_size_max.value() if hasattr(tab, 'bubble_big_size_max') else 38) / 1000.0,
        'bubble_small_size_max': (tab.bubble_small_size_max.value() if hasattr(tab, 'bubble_small_size_max') else 18) / 1000.0,
        'bubble_big_specular_max_size': (tab.bubble_big_specular_max_size.value() if hasattr(tab, 'bubble_big_specular_max_size') else 250) / 100.0,
        'bubble_big_size_clamp': (tab.bubble_big_size_clamp.value() if hasattr(tab, 'bubble_big_size_clamp') else 400) / 100.0,
        'bubble_big_contraction_bias': (tab.bubble_big_contraction_bias.value() if hasattr(tab, 'bubble_big_contraction_bias') else 100) / 100.0,
        'bubble_growth': (tab.bubble_growth.value() if hasattr(tab, 'bubble_growth') else 300) / 100.0,
        'bubble_trail_strength': (tab.bubble_trail_strength.value() if hasattr(tab, 'bubble_trail_strength') else 0) / 100.0,
        'bubble_tail_opacity': (tab.bubble_tail_opacity.value() if hasattr(tab, 'bubble_tail_opacity') else 0) / 100.0,
    })
    spotify_vis_config.update(collect_blob_mode_settings(tab))
    collect_per_mode_technical_controls(tab, spotify_vis_config)

    _cur_mode = collect_visualizer_mode_selection(tab)

    def _per_mode_value(key: str, fallback):
        return spotify_vis_config.get(f'{_cur_mode}_{key}', fallback)

    spotify_vis_config['bar_count'] = _per_mode_value(
        'bar_count', tab._default_int('spotify_visualizer', 'bar_count', 32)
    )
    spotify_vis_config['adaptive_sensitivity'] = _per_mode_value(
        'adaptive_sensitivity', tab._default_bool('spotify_visualizer', 'adaptive_sensitivity', True)
    )
    spotify_vis_config['sensitivity'] = _per_mode_value(
        'sensitivity', tab._default_float('spotify_visualizer', 'sensitivity', 1.0)
    )
    spotify_vis_config['dynamic_floor'] = _per_mode_value(
        'dynamic_floor', tab._default_bool('spotify_visualizer', 'dynamic_floor', True)
    )
    spotify_vis_config['manual_floor'] = _per_mode_value(
        'manual_floor', tab._default_float('spotify_visualizer', 'manual_floor', 0.12)
    )
    spotify_vis_config['dynamic_range_enabled'] = _per_mode_value(
        'dynamic_range_enabled', tab._default_bool('spotify_visualizer', 'dynamic_range_enabled', False)
    )

    spotify_vis_config.update(collect_bindings_save(tab, _OSC_MULTI_LINE_COLOR_BINDINGS))
    collect_visualizer_preset_indices(tab, spotify_vis_config)

    return media_config, spotify_vis_config
