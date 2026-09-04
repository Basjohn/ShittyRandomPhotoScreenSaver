"""Media + Beat Visualizer section for widgets tab.

Extracted from widgets_tab.py to reduce monolith size.
Contains UI building, settings loading/saving for Media widget and the Beat Visualizer.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel,
    QSpinBox, QGroupBox, QCheckBox,
    QSlider, QWidget, QPushButton,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont

from core.logging.logger import get_logger, is_perf_metrics_enabled
from core.media.provider_registry import (
    iter_media_providers,
    normalize_provider_id,
    preserve_provider_setting,
    provider_supports_app_volume,
)
from core.settings.visualizer_presets import (
    apply_preset_to_config,
    resolve_preset_index_from_mapping,
)
from rendering.widget_descriptors import get_widget_position_option_labels
from ui.color_utils import qcolor_to_list as _qcolor_to_list
from ui.styled_popup import ColorSwatchButton
from ui.tabs import shared_styles
from ui.tabs.shared_styles import (
    STATUS_LABEL_STYLE,
    add_swatch_label,
    style_group_box,
    LABEL_WIDTH,  # Promoted to module-level constant
    add_aligned_row,
    create_inline_label,
    build_bucket_toggle,
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
    load_visualizer_preset_indices,
    load_visualizer_mode_selection,
    load_visualizer_rainbow_state,
)

if TYPE_CHECKING:
    from ui.tabs.visualizer_settings_context import VisualizerSettingsContextMixin
    from ui.tabs.widgets_tab import WidgetsTab

logger = get_logger(__name__)


def _run_visualizer_settings_step(label: str, func) -> None:
    """Run one visualizer settings UI step with optional settings-side timing."""
    if not is_perf_metrics_enabled():
        func()
        return
    start = time.perf_counter()
    try:
        func()
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        logger.info("[PERF][SETTINGS][VisualizersTab] %s in %.1f ms", label, elapsed_ms)


def _finalize_bucket_body(toggle, body: QWidget) -> None:
    expanded = bool(toggle.isChecked())
    if body.isHidden() == expanded:
        body.setVisible(expanded)


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


def _update_media_progress_controls(tab) -> None:
    """Gate seek-bar styling behind the seek-bar toggle only."""

    progress_toggle = getattr(tab, "media_playback_progress_enabled", None)
    options = getattr(tab, "_media_progress_options_container", None)
    if options is not None:
        options.setEnabled(
            progress_toggle is not None
            and progress_toggle.isChecked()
        )
    shadow_color = getattr(tab, "media_playback_progress_shadow_color_btn", None)
    shadow_toggle = getattr(tab, "media_playback_progress_shadow_enabled", None)
    if shadow_color is not None:
        shadow_color.setEnabled(
            options is not None
            and options.isEnabled()
            and shadow_toggle is not None
            and shadow_toggle.isChecked()
        )
    glow_color = getattr(tab, "media_playback_progress_glow_color_btn", None)
    glow_toggle = getattr(tab, "media_playback_progress_glow_enabled", None)
    if glow_color is not None:
        glow_color.setEnabled(
            options is not None
            and options.isEnabled()
            and glow_toggle is not None
            and glow_toggle.isChecked()
        )


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


def _update_media_provider_controls(tab) -> None:
    """Apply provider-owned conditional controls without changing preferences."""

    btn = getattr(tab, '_musicbee_plugin_btn', None)
    combo = getattr(tab, 'media_provider_combo', None)
    if combo is None:
        return
    raw_provider = combo.currentData()
    provider = normalize_provider_id(raw_provider)
    if btn is not None:
        btn.setVisible(provider == "musicbee")

    browser_note = getattr(tab, '_spotify_browser_provider_note', None)
    if browser_note is not None:
        browser_note.setVisible(provider == "spotify_browser")

    unsupported_note = getattr(tab, '_unsupported_media_provider_note', None)
    if unsupported_note is not None:
        unsupported = provider is None and bool(str(raw_provider or '').strip())
        unsupported_note.setVisible(unsupported)
        if unsupported:
            unsupported_note.setText(
                f"Unsupported saved media provider: {raw_provider}. "
                "Media monitoring stays disabled until a supported provider is selected."
            )

    volume = getattr(tab, 'media_spotify_volume_enabled', None)
    if volume is not None:
        direct_app_volume = provider_supports_app_volume(provider)
        browser_volume_fallback = provider == "spotify_browser"
        volume.setEnabled(direct_app_volume or browser_volume_fallback)
        if direct_app_volume:
            volume.setToolTip(
                "Show a slim vertical volume slider next to the media card when "
                "Core Audio/pycaw is available. It affects only the selected "
                "desktop application's audio session."
            )
        elif browser_volume_fallback:
            volume.setToolTip(
                "Show the volume slider when Browser GSMTC identifies an exact "
                "browser host. Desktop Spotify is preferred when available; "
                "otherwise this adjusts the selected browser's whole audio session, "
                "not only its Spotify tab."
            )
        else:
            volume.setToolTip(
                "This provider has no registered application-volume contract. "
                "Your saved preference is preserved when you choose a supported provider."
            )


def _update_musicbee_plugin_visibility(tab) -> None:
    """Compatibility wrapper for the consolidated provider conditional owner."""

    _update_media_provider_controls(tab)


def build_media_ui(tab: WidgetsTab, layout: QVBoxLayout) -> QWidget:
    """Build the Media widget UI section.

    Returns the media container widget.
    """
    from ui.tabs.shared_styles import NoWheelSlider

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

    # Container for all media controls gated by enable checkbox
    tab._media_controls_container = QWidget()
    _media_ctrl_layout = QVBoxLayout(tab._media_controls_container)
    _media_ctrl_layout.setContentsMargins(0, 0, 0, 12)
    _media_ctrl_layout.setSpacing(12)

    provider_toggle, provider_body, provider_layout = build_bucket_toggle(
        _media_ctrl_layout,
        "Provider & Layout",
        expanded=tab.get_widget_bucket_state("media", "provider_layout", default=False),
        on_toggle=lambda checked: tab.set_widget_bucket_state("media", "provider_layout", checked),
        defer_initial_visibility=True,
    )
    appearance_toggle, appearance_body, appearance_layout = build_bucket_toggle(
        _media_ctrl_layout,
        "Appearance",
        expanded=tab.get_widget_bucket_state("media", "appearance", default=False),
        on_toggle=lambda checked: tab.set_widget_bucket_state("media", "appearance", checked),
        defer_initial_visibility=True,
    )
    artwork_toggle, artwork_body, artwork_layout = build_bucket_toggle(
        _media_ctrl_layout,
        "Artwork",
        expanded=tab.get_widget_bucket_state("media", "artwork_header", default=False),
        on_toggle=lambda checked: tab.set_widget_bucket_state("media", "artwork_header", checked),
        defer_initial_visibility=True,
    )
    controls_toggle, controls_body, controls_layout = build_bucket_toggle(
        _media_ctrl_layout,
        "Transport Controls",
        expanded=tab.get_widget_bucket_state("media", "controls", default=False),
        on_toggle=lambda checked: tab.set_widget_bucket_state("media", "controls", checked),
        defer_initial_visibility=True,
    )
    seek_toggle, seek_body, seek_layout = build_bucket_toggle(
        _media_ctrl_layout,
        "Seek Bar",
        expanded=tab.get_widget_bucket_state("media", "seek_bar", default=False),
        on_toggle=lambda checked: tab.set_widget_bucket_state("media", "seek_bar", checked),
        defer_initial_visibility=True,
    )
    volume_toggle, volume_body, volume_layout = build_bucket_toggle(
        _media_ctrl_layout,
        "Volume Control",
        expanded=tab.get_widget_bucket_state("media", "volume_control", default=False),
        on_toggle=lambda checked: tab.set_widget_bucket_state("media", "volume_control", checked),
        defer_initial_visibility=True,
    )
    # Provider toggle row
    provider_row = _aligned_row(provider_layout, "Provider:")
    tab.media_provider_combo = StyledComboBox()
    for provider in iter_media_providers():
        tab.media_provider_combo.addItem(provider.display_name, provider.provider_id)
    tab.media_provider_combo.setMinimumWidth(150)
    tab.media_provider_combo.setToolTip(
        "Select which media player to monitor via Windows GSMTC.\n"
        "Spotify Browser uses the active session exposed by a supported browser; "
        "Windows does not reveal the website or tab origin."
    )
    tab.media_provider_combo.currentIndexChanged.connect(tab._save_settings)
    tab.media_provider_combo.currentIndexChanged.connect(
        lambda: _update_media_provider_controls(tab)
    )
    provider_row.addWidget(tab.media_provider_combo)

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
    provider_row.addWidget(tab._musicbee_plugin_btn)
    provider_row.addStretch()

    tab._spotify_browser_provider_note = QLabel(
        "Browser GSMTC identifies Chrome, Edge, Firefox, Brave, Opera, or "
        "Vivaldi—not a specific website. The browser's active media session is used. "
        "Volume fallback therefore affects that browser's whole audio session, not "
        "only its Spotify tab."
    )
    tab._spotify_browser_provider_note.setWordWrap(True)
    shared_styles.apply_shared_label_style(tab._spotify_browser_provider_note, "INFO_LABEL_STYLE")
    tab._spotify_browser_provider_note.setVisible(False)
    provider_layout.addWidget(tab._spotify_browser_provider_note)

    tab._unsupported_media_provider_note = QLabel("")
    tab._unsupported_media_provider_note.setWordWrap(True)
    shared_styles.apply_shared_label_style(tab._unsupported_media_provider_note, "INFO_LABEL_STYLE")
    tab._unsupported_media_provider_note.setVisible(False)
    provider_layout.addWidget(tab._unsupported_media_provider_note)

    media_pos_row = _aligned_row(provider_layout, "Position:")
    tab.media_position = StyledComboBox()
    tab.media_position.addItems(list(get_widget_position_option_labels("media")))
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

    media_disp_row = _aligned_row(provider_layout, "Display:")
    tab.media_monitor_combo = StyledComboBox(size_variant="compact")
    tab.media_monitor_combo.addItems(["ALL", "1", "2", "3"])
    tab.media_monitor_combo.currentTextChanged.connect(tab._save_settings)
    tab.media_monitor_combo.currentTextChanged.connect(tab._update_stack_status)
    tab.media_monitor_combo.setMinimumWidth(120)
    media_disp_row.addWidget(tab.media_monitor_combo)
    media_monitor_default = tab._widget_default('media', 'monitor', 'ALL')
    tab._set_combo_text(tab.media_monitor_combo, str(media_monitor_default))
    media_disp_row.addStretch()

    media_font_family_row = _aligned_row(provider_layout, "Font:")
    tab.media_font_combo = StyledFontComboBox(size_variant="hero")
    default_media_font = tab._default_str('media', 'font_family', 'Inter')
    tab.media_font_combo.setCurrentFont(QFont(default_media_font))
    tab.media_font_combo.setMinimumWidth(220)
    tab.media_font_combo.currentFontChanged.connect(tab._save_settings)
    media_font_family_row.addWidget(tab.media_font_combo)
    media_font_family_row.addStretch()

    media_font_row = _aligned_row(provider_layout, "Font Size:")
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

    media_margin_row = _aligned_row(provider_layout, "Margin:")
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

    media_color_row = _swatch_row(appearance_layout, "Text Color:")
    tab.media_color_btn = ColorSwatchButton(title="Choose Spotify Text Color")
    tab.media_color_btn.set_color(tab._media_color)
    tab.media_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_media_color', c), tab._save_settings())
    )
    media_color_row.addWidget(tab.media_color_btn)
    media_color_row.addStretch()

    # Header appearance is one shared Widget Theme semantic. Media no longer
    # exposes a higher-precedence family colour bucket; the explicit reset action
    # in General -> Style Overrides handles old persisted family colours.

    tab.media_show_album = QCheckBox("Show Album Line")
    tab.media_show_album.setProperty("circleIndicator", True)
    tab.media_show_album.setChecked(tab._default_bool('media', 'show_album', True))
    tab.media_show_album.stateChanged.connect(tab._save_settings)
    appearance_layout.addWidget(tab.media_show_album)

    tab.media_show_playback_state = QCheckBox("Show Playback State Line")
    tab.media_show_playback_state.setProperty("circleIndicator", True)
    tab.media_show_playback_state.setToolTip(
        "Shows the Playing/Paused state line beneath the track metadata."
    )
    tab.media_show_playback_state.setChecked(
        tab._default_bool('media', 'show_playback_state', True)
    )
    tab.media_show_playback_state.stateChanged.connect(tab._save_settings)
    appearance_layout.addWidget(tab.media_show_playback_state)

    tab.media_show_background = QCheckBox("Show Background Frame")
    tab.media_show_background.setProperty("circleIndicator", True)
    tab.media_show_background.setChecked(tab._default_bool('media', 'show_background', True))
    tab.media_show_background.stateChanged.connect(tab._save_settings)
    appearance_layout.addWidget(tab.media_show_background)

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

    appearance_layout.addWidget(tab._media_bg_container)
    tab.media_show_background.stateChanged.connect(lambda: _update_media_bg_visibility(tab))
    _update_media_bg_visibility(tab)

    media_volume_track_row = _swatch_row(volume_layout, "Track Color:")
    tab.media_volume_track_color_btn = ColorSwatchButton(
        title="Choose App Volume Track Color", show_alpha=True
    )
    tab.media_volume_track_color_btn.set_color(
        getattr(tab, '_media_volume_track_color', QColor(35, 35, 35, 255))
    )
    tab.media_volume_track_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_media_volume_track_color', c), tab._save_settings())
    )
    media_volume_track_row.addWidget(tab.media_volume_track_color_btn)
    media_volume_track_row.addStretch()

    media_volume_fill_row = _swatch_row(volume_layout, "Fill Color:")
    tab.media_volume_fill_color_btn = ColorSwatchButton(
        title="Choose Spotify Volume Fill Color", show_alpha=True
    )
    tab.media_volume_fill_color_btn.set_color(getattr(tab, '_media_volume_fill_color', tab._media_color))
    tab.media_volume_fill_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_media_volume_fill_color', c), tab._save_settings())
    )
    media_volume_fill_row.addWidget(tab.media_volume_fill_color_btn)
    media_volume_fill_row.addStretch()

    media_volume_border_row = _swatch_row(volume_layout, "Outline Color:")
    tab.media_volume_border_color_btn = ColorSwatchButton(
        title="Choose Spotify Volume Outline Color", show_alpha=True
    )
    tab.media_volume_border_color_btn.set_color(tab._media_volume_border_color)
    tab.media_volume_border_color_btn.color_changed.connect(
        lambda c: (setattr(tab, '_media_volume_border_color', c), tab._save_settings())
    )
    media_volume_border_row.addWidget(tab.media_volume_border_color_btn)
    media_volume_border_row.addStretch()

    media_artwork_row = _aligned_row(artwork_layout, "Artwork Size:")
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
    artwork_layout.addWidget(tab.media_rounded_artwork)

    tab.media_show_header_frame = QCheckBox("Show Header Pill (Logo + Title)")
    tab.media_show_header_frame.setProperty("circleIndicator", True)
    tab.media_show_header_frame.setChecked(
        tab._default_bool('media', 'show_header_frame', True)
    )
    tab.media_show_header_frame.stateChanged.connect(tab._save_settings)
    appearance_layout.addWidget(tab.media_show_header_frame)

    tab.media_show_controls = QCheckBox("Show Transport Controls")
    tab.media_show_controls.setProperty("circleIndicator", True)
    tab.media_show_controls.setChecked(
        tab._default_bool('media', 'show_controls', True)
    )
    tab.media_show_controls.stateChanged.connect(tab._save_settings)
    controls_layout.addWidget(tab.media_show_controls)

    tab.media_playback_progress_enabled = QCheckBox("Show Playback Progress Bar")
    tab.media_playback_progress_enabled.setProperty("circleIndicator", True)
    tab.media_playback_progress_enabled.setChecked(
        tab._default_bool('media', 'playback_progress_enabled', False)
    )
    tab.media_playback_progress_enabled.setToolTip(
        "Draws the interactive playback/seek pill from the existing Media runtime snapshot. "
        "It adds no timer, polling cadence, or independent media request."
    )
    tab.media_playback_progress_enabled.stateChanged.connect(tab._save_settings)
    tab.media_playback_progress_enabled.stateChanged.connect(
        lambda: _update_media_progress_controls(tab)
    )
    seek_layout.addWidget(tab.media_playback_progress_enabled)

    tab._media_progress_options_container = QWidget()
    progress_options_layout = QVBoxLayout(tab._media_progress_options_container)
    progress_options_layout.setContentsMargins(18, 0, 0, 4)
    progress_options_layout.setSpacing(6)

    progress_height_row = _aligned_row(progress_options_layout, "Bar Height:")
    tab.media_playback_progress_height = QSpinBox()
    tab.media_playback_progress_height.setRange(3, 18)
    tab.media_playback_progress_height.setValue(
        tab._default_int('media', 'playback_progress_height', 6)
    )
    tab.media_playback_progress_height.valueChanged.connect(tab._save_settings)
    progress_height_row.addWidget(tab.media_playback_progress_height)
    progress_height_row.addWidget(_inline_label("px"))
    progress_height_row.addStretch()

    progress_track_row = _swatch_row(progress_options_layout, "Track Color:")
    tab.media_playback_progress_track_color_btn = ColorSwatchButton(
        title="Choose Media Seek Track Color", show_alpha=True
    )
    tab.media_playback_progress_track_color_btn.set_color(
        getattr(tab, '_media_progress_track_color', QColor(255, 255, 255, 74))
    )
    tab.media_playback_progress_track_color_btn.color_changed.connect(
        lambda color: (
            setattr(tab, '_media_progress_track_color', color),
            tab._save_settings(),
        )
    )
    progress_track_row.addWidget(tab.media_playback_progress_track_color_btn)
    progress_track_row.addStretch()

    progress_fill_row = _swatch_row(progress_options_layout, "Fill Color:")
    tab.media_playback_progress_fill_color_btn = ColorSwatchButton(
        title="Choose Media Playback Progress Fill Color", show_alpha=True
    )
    tab.media_playback_progress_fill_color_btn.set_color(tab._media_progress_fill_color)
    tab.media_playback_progress_fill_color_btn.color_changed.connect(
        lambda color: (
            setattr(tab, '_media_progress_fill_color', color),
            tab._save_settings(),
        )
    )
    progress_fill_row.addWidget(tab.media_playback_progress_fill_color_btn)
    progress_fill_row.addStretch()

    tab.media_playback_progress_shadow_enabled = QCheckBox("Progress Bar Shadow")
    tab.media_playback_progress_shadow_enabled.setProperty("circleIndicator", True)
    tab.media_playback_progress_shadow_enabled.setChecked(
        tab._default_bool('media', 'playback_progress_shadow_enabled', False)
    )
    tab.media_playback_progress_shadow_enabled.stateChanged.connect(tab._save_settings)
    tab.media_playback_progress_shadow_enabled.stateChanged.connect(
        lambda: _update_media_progress_controls(tab)
    )
    progress_options_layout.addWidget(tab.media_playback_progress_shadow_enabled)

    progress_shadow_row = _swatch_row(progress_options_layout, "Shadow Color:")
    tab.media_playback_progress_shadow_color_btn = ColorSwatchButton(
        title="Choose Media Seek Shadow Color", show_alpha=True
    )
    tab.media_playback_progress_shadow_color_btn.set_color(
        getattr(tab, '_media_progress_shadow_color', QColor(0, 0, 0, 102))
    )
    tab.media_playback_progress_shadow_color_btn.color_changed.connect(
        lambda color: (
            setattr(tab, '_media_progress_shadow_color', color),
            tab._save_settings(),
        )
    )
    progress_shadow_row.addWidget(tab.media_playback_progress_shadow_color_btn)
    progress_shadow_row.addStretch()

    tab.media_playback_progress_glow_enabled = QCheckBox("Progress Bar Glow")
    tab.media_playback_progress_glow_enabled.setProperty("circleIndicator", True)
    tab.media_playback_progress_glow_enabled.setChecked(
        tab._default_bool('media', 'playback_progress_glow_enabled', False)
    )
    tab.media_playback_progress_glow_enabled.stateChanged.connect(tab._save_settings)
    tab.media_playback_progress_glow_enabled.stateChanged.connect(
        lambda: _update_media_progress_controls(tab)
    )
    progress_options_layout.addWidget(tab.media_playback_progress_glow_enabled)

    progress_glow_row = _swatch_row(progress_options_layout, "Glow Color:")
    tab.media_playback_progress_glow_color_btn = ColorSwatchButton(
        title="Choose Media Playback Progress Glow Color", show_alpha=True
    )
    tab.media_playback_progress_glow_color_btn.set_color(tab._media_progress_glow_color)
    tab.media_playback_progress_glow_color_btn.color_changed.connect(
        lambda color: (
            setattr(tab, '_media_progress_glow_color', color),
            tab._save_settings(),
        )
    )
    progress_glow_row.addWidget(tab.media_playback_progress_glow_color_btn)
    progress_glow_row.addStretch()
    seek_layout.addWidget(tab._media_progress_options_container)
    _update_media_progress_controls(tab)

    tab.media_spotify_volume_enabled = QCheckBox("Enable App Volume Slider")
    tab.media_spotify_volume_enabled.setProperty("circleIndicator", True)
    tab.media_spotify_volume_enabled.setToolTip(
        "Show a slim vertical volume slider next to the media card when Core Audio/pycaw is available. "
        "It affects only the selected desktop application's audio session and is gated by Interaction Mode / Ctrl-held interaction modes."
    )
    tab.media_spotify_volume_enabled.setChecked(
        tab._default_bool('media', 'spotify_volume_enabled', True)
    )
    tab.media_spotify_volume_enabled.stateChanged.connect(tab._save_settings)
    volume_layout.addWidget(tab.media_spotify_volume_enabled)

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
    controls_layout.addWidget(tab.media_mute_button_enabled)

    for toggle, body in (
        (provider_toggle, provider_body),
        (appearance_toggle, appearance_body),
        (artwork_toggle, artwork_body),
        (controls_toggle, controls_body),
        (seek_toggle, seek_body),
        (volume_toggle, volume_body),
    ):
        _finalize_bucket_body(toggle, body)

    media_layout.addWidget(tab._media_controls_container)
    tab.media_enabled.stateChanged.connect(lambda: _update_media_enabled_visibility(tab))
    _update_media_enabled_visibility(tab)

    container = QWidget()
    container_layout = QVBoxLayout(container)
    container_layout.setContentsMargins(0, 20, 0, 0)
    container_layout.addWidget(media_group)
    return container


# ---------------------------------------------------------------------------
# V5b lazy Settings-body construction (Option-1: Spectrum eager exception)
# ---------------------------------------------------------------------------
#
# Spectrum is built eagerly because it hosts the genuinely shared Bar Fill/Border
# colour + Border Opacity controls physically nested in its Appearance bucket
# (extracting them is a V6 pixel move). Oscilloscope / Sine / Bubble / DevCurve
# are constructed lazily on first selection and hydrated ONCE at construction.
_LAZY_VISUALIZER_MODES = ("oscilloscope", "sine_wave", "bubble", "devcurve")

_VIS_MODE_CONTAINER_ATTR = {
    "spectrum": "_spectrum_settings_container",
    "oscilloscope": "_osc_settings_container",
    "sine_wave": "_sine_wave_settings_container",
    "bubble": "_bubble_settings_container",
    "devcurve": "_devcurve_settings_container",
}


def _apply_vis_color_to_button(tab, btn_attr: str, color_attr: str) -> None:
    """Sync a colour swatch button with its stored QColor.

    Module-level so the lazy hydrate path can reuse it outside the local
    closure in ``load_visualizer_settings``.
    """
    btn = getattr(tab, btn_attr, None)
    color = getattr(tab, color_attr, None)
    if btn is not None and color is not None and hasattr(btn, "set_color"):
        try:
            btn.set_color(color)
        except Exception:
            logger.debug(
                "[MEDIA_TAB] Failed to sync %s with %s", btn_attr, color_attr, exc_info=True
            )


def _hydrate_visualizer_mode_body(tab, mode_id: str, config) -> None:
    """Hydrate exactly one freshly-constructed mode body from the canonical config.

    Called ONCE at construction (never on reselection of a cached body), so
    unsaved in-session edits are never overwritten. Uses the same loaders +
    arguments the eager path used, so it is behaviour-neutral.
    """
    from core.settings.visualizer_mode_registry import get_preset_slider_attr
    from core.settings.visualizer_presets import resolve_preset_index_from_mapping

    cfg = config or {}

    def _sync(btn_attr, color_attr):
        _apply_vis_color_to_button(tab, btn_attr, color_attr)

    if mode_id == "spectrum":
        load_spectrum_mode_settings(
            tab,
            cfg,
            sync_color_button=_sync,
            update_ghost_visibility=_update_ghost_visibility,
        )
    elif mode_id == "oscilloscope":
        load_oscilloscope_mode_settings(
            tab,
            cfg,
            sync_color_button=_sync,
            load_extra_color_bindings=_load_osc_multi_line_color_bindings,
            update_multi_line_visibility=_update_osc_multi_line_visibility,
        )
    elif mode_id == "sine_wave":
        load_sine_wave_mode_settings(
            tab,
            cfg,
            sync_color_button=_sync,
            update_multi_line_visibility=_update_sine_multi_line_visibility,
        )
    elif mode_id == "bubble":
        load_bubble_mode_settings(tab, cfg, sync_color_button=_sync)
    elif mode_id == "devcurve":
        load_devcurve_mode_settings(tab, cfg, sync_color_button=_sync)
    else:
        return

    # The section-level technical-controls loader runs before this body existed,
    # so hydrate this freshly-built mode's technical controls now. Scoped to this
    # mode only, so building it never re-hydrates (and clobbers unsaved edits in)
    # another already-built mode.
    load_per_mode_technical_controls(tab, cfg, only_mode=mode_id)

    slider = getattr(tab, get_preset_slider_attr(mode_id), None)
    if slider is not None:
        slider.set_preset_index(resolve_preset_index_from_mapping(mode_id, cfg))


def _install_visualizer_body_host(tab, controls_layout, *, retire_body=None) -> None:
    """Create the lazy-body host + production factory on the tab.

    All five modes (Spectrum included, V6a) are lazy — none is pre-built or
    adopted. The factory builds a mode's controls into ``controls_layout`` and
    hydrates it once from ``tab._vis_loaded_config``; it returns the mode's real
    settings container. The container is a hard contract: if the builder fails to
    create it the factory raises rather than returning a placeholder, so the host
    never caches a failed construction as success.
    """
    from core.settings.visualizer_mode_body_host import VisualizerModeBodyHost
    from core.settings.visualizer_mode_registry import (
        load_mode_settings_builder,
        resolve_effective_enabled_modes,
    )

    def _factory(mode_id):
        builder = load_mode_settings_builder(mode_id)
        builder(tab, controls_layout)
        container_attr = _VIS_MODE_CONTAINER_ATTR.get(mode_id, "")
        container = getattr(tab, container_attr, None) if container_attr else None
        if container is None:
            # Contract violation: the builder ran but did not create the mode's
            # settings container. Fail loudly (and hydrate nothing) rather than
            # returning a placeholder the host would cache as a real body.
            raise RuntimeError(
                f"Visualizer mode {mode_id!r} builder did not create its settings "
                f"container attribute {container_attr!r}"
            )
        _hydrate_visualizer_mode_body(
            tab, mode_id, getattr(tab, "_vis_loaded_config", None)
        )
        return container

    widgets_value = tab._settings.get("widgets", {}) if hasattr(tab, "_settings") else {}
    section = widgets_value.get("spotify_visualizer", {}) if isinstance(widgets_value, dict) else {}
    enabled = resolve_effective_enabled_modes(
        section.get("enabled_modes") if isinstance(section, dict) else None
    )
    tab._vis_body_host = VisualizerModeBodyHost(
        body_factory=_factory,
        retire_body=retire_body,
        enabled_modes=enabled,
    )


def ensure_visualizer_mode_body(tab, mode_id: str) -> None:
    """Construct + hydrate a lazy mode body on first selection (idempotent).

    All five modes are lazy (V6a). No-op before the section has loaded
    (``_vis_loaded_config`` unset — the hydration source is not yet available),
    so build-time visibility passes never construct an un-hydratable body.
    """
    mode = str(mode_id or "").strip().lower()
    if getattr(tab, "_vis_loaded_config", None) is None:
        return
    host = getattr(tab, "_vis_body_host", None)
    if host is None:
        return
    if mode in host.enabled_modes:
        # No swallow: a construction/hydration failure must stay visible and
        # actionable. The host only caches on a successful factory return, so a
        # raised body is never recorded as constructed.
        host.ensure(mode)


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
    tab.media_enabled.setChecked(tab._config_bool('media', media_config, 'enabled', True))

    # Registered GSMTC provider.
    provider = preserve_provider_setting(
        tab._config_str('media', media_config, 'provider', 'spotify')
    )
    combo = getattr(tab, 'media_provider_combo', None)
    if combo is not None:
        for item_index in range(combo.count() - 1, -1, -1):
            if normalize_provider_id(combo.itemData(item_index)) is None:
                combo.removeItem(item_index)
        idx = combo.findData(provider)
        if idx < 0:
            combo.addItem(f"Unsupported ({provider})", provider)
            idx = combo.findData(provider)
        combo.setCurrentIndex(idx)

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
    tab.media_show_album.setChecked(tab._config_bool('media', media_config, 'show_album', True))
    tab.media_show_playback_state.setChecked(
        tab._config_bool('media', media_config, 'show_playback_state', True)
    )
    tab.media_show_controls.setChecked(tab._config_bool('media', media_config, 'show_controls', True))
    tab.media_playback_progress_enabled.setChecked(
        tab._config_bool('media', media_config, 'playback_progress_enabled', False)
    )
    tab.media_playback_progress_height.setValue(
        tab._config_int('media', media_config, 'playback_progress_height', 6)
    )
    tab.media_playback_progress_shadow_enabled.setChecked(
        tab._config_bool('media', media_config, 'playback_progress_shadow_enabled', False)
    )
    tab.media_playback_progress_glow_enabled.setChecked(
        tab._config_bool('media', media_config, 'playback_progress_glow_enabled', False)
    )
    tab.media_spotify_volume_enabled.setChecked(
        tab._config_bool('media', media_config, 'spotify_volume_enabled', True)
    )
    _update_media_provider_controls(tab)
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

    header_fill_data = media_config.get(
        'header_fill_color', tab._widget_default('media', 'header_fill_color', [0, 0, 0, 0])
    )
    tab._media_header_fill_color = QColor(*header_fill_data)
    header_text_data = media_config.get(
        'header_text_color', tab._widget_default('media', 'header_text_color', [255, 255, 255, 230])
    )
    tab._media_header_text_color = QColor(*header_text_data)
    header_border_data = media_config.get(
        'header_border_color', tab._widget_default('media', 'header_border_color', [255, 255, 255, 255])
    )
    tab._media_header_border_color = QColor(*header_border_data)

    volume_track_data = media_config.get(
        'spotify_volume_track_color',
        tab._widget_default('media', 'spotify_volume_track_color', [35, 35, 35, 255]),
    )
    try:
        tab._media_volume_track_color = QColor(*volume_track_data)
    except Exception:
        logger.debug("[MEDIA_TAB] Failed to set volume_track_color=%s", volume_track_data, exc_info=True)
        tab._media_volume_track_color = QColor(35, 35, 35, 255)
    volume_fill_data = media_config.get(
        'spotify_volume_fill_color',
        tab._widget_default('media', 'spotify_volume_fill_color', [79, 79, 79, 150]),
    )
    try:
        tab._media_volume_fill_color = QColor(*volume_fill_data)
    except Exception:
        logger.debug("[MEDIA_TAB] Failed to set volume_fill_color=%s", volume_fill_data, exc_info=True)
        tab._media_volume_fill_color = QColor(79, 79, 79, 150)
    volume_border_data = media_config.get(
        'spotify_volume_border_color',
        tab._widget_default('media', 'spotify_volume_border_color', [255, 255, 255, 255]),
    )
    try:
        tab._media_volume_border_color = QColor(*volume_border_data)
    except Exception:
        logger.debug("[MEDIA_TAB] Failed to set volume_border_color=%s", volume_border_data, exc_info=True)
        tab._media_volume_border_color = QColor(255, 255, 255, 255)
    progress_track_data = media_config.get(
        'playback_progress_track_color',
        tab._widget_default('media', 'playback_progress_track_color', [255, 255, 255, 74]),
    )
    try:
        tab._media_progress_track_color = QColor(*progress_track_data)
    except Exception:
        logger.debug("[MEDIA_TAB] Failed to set progress track color=%s", progress_track_data, exc_info=True)
        tab._media_progress_track_color = QColor(255, 255, 255, 74)
    progress_fill_data = media_config.get(
        'playback_progress_fill_color',
        tab._widget_default('media', 'playback_progress_fill_color', [255, 255, 255, 230]),
    )
    try:
        tab._media_progress_fill_color = QColor(*progress_fill_data)
    except Exception:
        logger.debug("[MEDIA_TAB] Failed to set progress fill color=%s", progress_fill_data, exc_info=True)
        tab._media_progress_fill_color = QColor(255, 255, 255, 230)
    progress_shadow_data = media_config.get(
        'playback_progress_shadow_color',
        tab._widget_default('media', 'playback_progress_shadow_color', [0, 0, 0, 102]),
    )
    try:
        tab._media_progress_shadow_color = QColor(*progress_shadow_data)
    except Exception:
        logger.debug("[MEDIA_TAB] Failed to set progress shadow color=%s", progress_shadow_data, exc_info=True)
        tab._media_progress_shadow_color = QColor(0, 0, 0, 102)
    progress_glow_data = media_config.get(
        'playback_progress_glow_color',
        tab._widget_default('media', 'playback_progress_glow_color', [255, 255, 255, 180]),
    )
    try:
        tab._media_progress_glow_color = QColor(*progress_glow_data)
    except Exception:
        logger.debug("[MEDIA_TAB] Failed to set progress glow color=%s", progress_glow_data, exc_info=True)
        tab._media_progress_glow_color = QColor(255, 255, 255, 180)
    _apply_color_to_button('media_color_btn', '_media_color')
    _apply_color_to_button('media_bg_color_btn', '_media_bg_color')
    _apply_color_to_button('media_border_color_btn', '_media_border_color')
    _apply_color_to_button('media_volume_track_color_btn', '_media_volume_track_color')
    _apply_color_to_button('media_volume_fill_color_btn', '_media_volume_fill_color')
    _apply_color_to_button('media_volume_border_color_btn', '_media_volume_border_color')
    _apply_color_to_button('media_playback_progress_track_color_btn', '_media_progress_track_color')
    _apply_color_to_button('media_playback_progress_fill_color_btn', '_media_progress_fill_color')
    _apply_color_to_button('media_playback_progress_shadow_color_btn', '_media_progress_shadow_color')
    _apply_color_to_button('media_playback_progress_glow_color_btn', '_media_progress_glow_color')

    m_monitor_sel = media_config.get('monitor', tab._widget_default('media', 'monitor', 'ALL'))
    m_mon_text = str(m_monitor_sel) if isinstance(m_monitor_sel, (int, str)) else 'ALL'
    midx = tab.media_monitor_combo.findText(m_mon_text)
    if midx >= 0:
        tab.media_monitor_combo.setCurrentIndex(midx)

    _update_media_bg_visibility(tab)
    _update_media_progress_controls(tab)
    _update_media_enabled_visibility(tab)


def load_shared_visualizer_appearance_settings(
    tab: "VisualizerSettingsContextMixin",
    spotify_vis_config: dict,
    active_vis_mode: str,
) -> None:
    """Hydrate the stable SETUP-owned shared appearance controls for one mode.

    Fill/border/opacity are physically shared controls whose values are stored
    per active mode.  V7 keeps the widgets under SETUP permanently and swaps only
    their values when mode selection changes, so retiring a mode body can never
    delete these controls.
    """
    fill_color_key = f'{active_vis_mode}_bar_fill_color'
    border_color_key = f'{active_vis_mode}_bar_border_color'
    border_opacity_key = f'{active_vis_mode}_bar_border_opacity'

    fill_color_data = spotify_vis_config.get(
        fill_color_key,
        tab._widget_default('spotify_visualizer', fill_color_key, [0, 255, 128, 230]),
    )
    try:
        tab._spotify_vis_fill_color = QColor(*fill_color_data)
    except Exception:
        logger.debug(
            "[MEDIA_TAB] Failed to set vis fill_color=%s",
            fill_color_data,
            exc_info=True,
        )
        tab._spotify_vis_fill_color = QColor(0, 255, 128, 230)

    border_color_data = spotify_vis_config.get(
        border_color_key,
        tab._widget_default('spotify_visualizer', border_color_key, [255, 255, 255, 230]),
    )
    try:
        tab._spotify_vis_border_color = QColor(*border_color_data)
    except Exception:
        logger.debug(
            "[MEDIA_TAB] Failed to set vis border_color=%s",
            border_color_data,
            exc_info=True,
        )
        tab._spotify_vis_border_color = QColor(255, 255, 255, 230)

    _apply_vis_color_to_button(tab, 'vis_fill_color_btn', '_spotify_vis_fill_color')
    _apply_vis_color_to_button(tab, 'vis_border_color_btn', '_spotify_vis_border_color')

    border_opacity_pct = int(
        tab._config_float(
            'spotify_visualizer', spotify_vis_config, border_opacity_key, 0.85
        ) * 100
    )
    tab.vis_border_opacity.setValue(border_opacity_pct)
    tab.vis_border_opacity_label.setText(f"{border_opacity_pct}%")


def load_visualizer_settings(
    tab: "VisualizerSettingsContextMixin",
    widgets: dict | None,
    *,
    construct_active_body: bool = False,
) -> None:
    """Load Spotify visualizer settings from the widgets config dict."""

    widgets = widgets or {}
    raw_spotify_vis_config = (
        widgets.get('spotify_visualizer', {}) if isinstance(widgets, dict) else {}
    )
    spotify_vis_config = (
        dict(raw_spotify_vis_config)
        if isinstance(raw_spotify_vis_config, dict)
        else {}
    )
    # V7: resolve stale/disabled persisted modes before any preset/body hydration.
    # The persisted mapping remains the authority; this only resolves the
    # effective Settings presentation state and keeps the mode/enable set coherent.
    from core.settings.visualizer_mode_registry import resolve_effective_visualizer_section

    (
        spotify_vis_config,
        _mode_substituted,
        _requested_mode,
        _effective_mode,
    ) = resolve_effective_visualizer_section(spotify_vis_config)
    active_vis_mode = (
        str(spotify_vis_config.get('mode', 'spectrum')).strip().lower()
        or 'spectrum'
    )
    active_preset_index = resolve_preset_index_from_mapping(
        active_vis_mode,
        spotify_vis_config,
    )
    # Runtime applies curated presets before constructing the visualizer.  The
    # Settings controls must display that same authoritative state; otherwise
    # Move To Custom snapshots stale underlying values that were never active
    # in runtime (observed in the 2026-08-08 main_mc evidence).
    resolved_spotify_vis_config = apply_preset_to_config(
        active_vis_mode,
        active_preset_index,
        spotify_vis_config,
    )
    if resolved_spotify_vis_config != spotify_vis_config:
        logger.debug(
            "[VIS_PRESETS] Settings load applied runtime-authoritative preset "
            "mode=%s index=%d",
            active_vis_mode,
            active_preset_index,
        )
    spotify_vis_config = resolved_spotify_vis_config
    # Canonical hydration source for lazy mode bodies constructed on first select.
    # Stashed before mode selection so the construct-on-select path below
    # can hydrate a freshly-built body from exactly this resolved config.
    tab._vis_loaded_config = spotify_vis_config
    if hasattr(tab, 'visualizers_enabled'):
        tab.visualizers_enabled.setChecked(
            tab._config_bool(
                'spotify_visualizer', spotify_vis_config, 'visualizers_enabled', True
            )
        )
    tab.vis_enabled_checkbox.setChecked(
        tab._config_bool('spotify_visualizer', spotify_vis_config, 'enabled', True)
    )
    load_per_mode_technical_controls(tab, spotify_vis_config)

    load_shared_visualizer_appearance_settings(
        tab, spotify_vis_config, active_vis_mode
    )

    # Context-owned mode selection (V7 pills are presentation only).
    load_visualizer_mode_selection(tab, spotify_vis_config)

    # No mode loader runs eagerly here (V6a): an *unbuilt* mode is built +
    # hydrated once on first selection through the lazy body factory, so it runs
    # no loader and requires no QWidget. But this is a FULL reload, so every mode
    # whose body is already built is re-hydrated from the new config (an explicit
    # reload intentionally replaces in-session UI state). Ordinary mode
    # *reselection* goes through the cached-body path and never re-hydrates, so
    # unsaved edits survive a plain switch. The shared Bar Fill/Border/Opacity
    # controls are hydrated above because they are shared-owned and always exist.
    _vis_host = getattr(tab, "_vis_body_host", None)
    if _vis_host is not None:
        for _built_mode in _vis_host.constructed_modes():
            _hydrate_visualizer_mode_body(tab, _built_mode, spotify_vis_config)

    # V7 lands on SETUP and constructs *zero* mode bodies until a mode pill is
    # explicitly selected. Focused callers may opt into active-body admission,
    # but descriptor/full-reload paths remain dormant by default.
    if construct_active_body:
        tab._update_vis_mode_sections()

    load_visualizer_rainbow_state(tab, spotify_vis_config)

    load_visualizer_preset_indices(tab, spotify_vis_config)

    _update_spotify_vis_enabled_visibility(tab)
    _update_visualizers_enabled_visibility(tab)


def save_media_settings(tab: WidgetsTab) -> dict:
    """Return media_config from current UI state."""
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
        'header_fill_color': _qcolor_to_list(tab._media_header_fill_color),
        'header_text_color': _qcolor_to_list(tab._media_header_text_color),
        'header_border_color': _qcolor_to_list(tab._media_header_border_color),
        'spotify_volume_track_color': _qcolor_to_list(tab._media_volume_track_color),
        'spotify_volume_fill_color': [
            tab._media_volume_fill_color.red(),
            tab._media_volume_fill_color.green(),
            tab._media_volume_fill_color.blue(),
            tab._media_volume_fill_color.alpha(),
        ],
        'spotify_volume_border_color': _qcolor_to_list(tab._media_volume_border_color),
        'artwork_size': tab.media_artwork_size.value(),
        'rounded_artwork_border': tab.media_rounded_artwork.isChecked(),
        'show_header_frame': tab.media_show_header_frame.isChecked(),
        'show_album': tab.media_show_album.isChecked(),
        'show_playback_state': tab.media_show_playback_state.isChecked(),
        'show_controls': tab.media_show_controls.isChecked(),
        'playback_progress_enabled': tab.media_playback_progress_enabled.isChecked(),
        'playback_progress_height': tab.media_playback_progress_height.value(),
        'playback_progress_track_color': _qcolor_to_list(tab._media_progress_track_color),
        'playback_progress_fill_color': _qcolor_to_list(tab._media_progress_fill_color),
        'playback_progress_shadow_color': _qcolor_to_list(tab._media_progress_shadow_color),
        'playback_progress_shadow_enabled': tab.media_playback_progress_shadow_enabled.isChecked(),
        'playback_progress_glow_enabled': tab.media_playback_progress_glow_enabled.isChecked(),
        'playback_progress_glow_color': _qcolor_to_list(tab._media_progress_glow_color),
        'spotify_volume_enabled': tab.media_spotify_volume_enabled.isChecked(),
        'mute_button_enabled': tab.media_mute_button_enabled.isChecked(),
    }
    mmon_text = tab.media_monitor_combo.currentText()
    media_config['monitor'] = mmon_text if mmon_text == 'ALL' else int(mmon_text)

    return media_config


def save_visualizer_settings(tab: "VisualizerSettingsContextMixin") -> dict:
    """Return spotify_visualizer config from current UI state."""
    current_mode = collect_visualizer_mode_selection(tab)
    spotify_vis_config = {
        'visualizers_enabled': tab.visualizers_enabled.isChecked() if hasattr(tab, 'visualizers_enabled') else True,
        'enabled': tab.vis_enabled_checkbox.isChecked(),
        'mode': current_mode,
        'software_visualizer_enabled': False,
        f'{current_mode}_bar_fill_color': [
            tab._spotify_vis_fill_color.red(),
            tab._spotify_vis_fill_color.green(),
            tab._spotify_vis_fill_color.blue(),
            tab._spotify_vis_fill_color.alpha(),
        ],
        f'{current_mode}_bar_border_color': [
            tab._spotify_vis_border_color.red(),
            tab._spotify_vis_border_color.green(),
            tab._spotify_vis_border_color.blue(),
            tab._spotify_vis_border_color.alpha(),
        ],
        f'{current_mode}_bar_border_opacity': tab.vis_border_opacity.value() / 100.0,
        'rainbow_enabled': tab.rainbow_enabled.isChecked() if hasattr(tab, 'rainbow_enabled') else False,
        'rainbow_speed': (tab.rainbow_speed_slider.value() if hasattr(tab, 'rainbow_speed_slider') else 50) / 100.0,
    }
    _host = getattr(tab, '_vis_body_host', None)
    if _host is not None:
        spotify_vis_config['enabled_modes'] = list(_host.enabled_modes)

    # Spectrum-owned ghost controls: only present when Spectrum's body is built
    # (V6a lazy). When Spectrum is unbuilt its persisted ghost state stays
    # authoritative via the save merge and is never synthesized here.
    if hasattr(tab, 'vis_ghost_enabled'):
        spotify_vis_config['spectrum_ghosting_enabled'] = tab.vis_ghost_enabled.isChecked()
        spotify_vis_config['spectrum_ghost_alpha'] = tab.vis_ghost_opacity_slider.value() / 100.0
        spotify_vis_config['spectrum_ghost_decay'] = max(0.1, tab.vis_ghost_decay_slider.value() / 100.0)
    collect_visualizer_rainbow_state(tab, spotify_vis_config)
    
    # Option A: only collect settings for the CURRENT visualizer mode to prevent
    # cross-mode pollution. Under lazy bodies the current mode may be unbuilt
    # while SETUP is active; collecting an unbuilt mode would require QWidgets that do not
    # exist. Skip it — the mode's persisted state stays authoritative via the
    # save merge, never synthesized here.
    _cur_mode = current_mode
    _cur_mode_built = hasattr(tab, _VIS_MODE_CONTAINER_ATTR.get(_cur_mode, ''))
    if _cur_mode_built:
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
        elif _cur_mode == 'bubble':
            spotify_vis_config.update(collect_bubble_mode_settings(tab))
        elif _cur_mode == 'devcurve':
            spotify_vis_config.update(collect_devcurve_mode_settings(tab))
    collect_per_mode_technical_controls(tab, spotify_vis_config, current_mode=_cur_mode)

    collect_visualizer_preset_indices(tab, spotify_vis_config)

    return spotify_vis_config


