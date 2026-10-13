"""Bespoke sections of the spec-built Spectrum Settings body."""
from __future__ import annotations

from PySide6.QtWidgets import QButtonGroup, QCheckBox, QLabel, QPushButton
from ui.tabs.media.builder_scaffold import bind_setting_signal
from ui.tabs import shared_styles
from ui.tabs.shared_styles import add_aligned_row


def _aligned_row(layout, label):
    content, _ = add_aligned_row(layout, label, label_width=150)
    return content


def build_spectrum_ui(tab, parent_layout) -> None:
    from ui.tabs.media.spec_mode_builder import build_spec_mode_ui

    build_spec_mode_ui(tab, parent_layout, "spectrum")


def build_spectrum_shape(tab, shape_bucket) -> None:
    # Mirrored Layout
    _mirror_row = _aligned_row(shape_bucket, "Mirrored Layout:")
    tab.spectrum_mirrored = QCheckBox("Center-Out (Mirrored Shape)")
    tab.spectrum_mirrored.setProperty("circleIndicator", True)
    _mirror_default = tab._default_bool('spotify_visualizer', 'spectrum_mirrored')
    tab.spectrum_mirrored.setChecked(_mirror_default)
    tab.spectrum_mirrored.setToolTip(
        "On: mirrored shape profile around the center divider (center ↔ edge symmetry).\n"
        "Off: bars use left-to-right linear profile mapping."
    )
    bind_setting_signal(tab, tab.spectrum_mirrored.stateChanged)
    _mirror_row.addWidget(tab.spectrum_mirrored)
    _mirror_row.addStretch()

    # --- Spectrum Shaping section ---
    _shape_hint = QLabel(
        "Left-click to add a control node (max 5). "
        "Right-click a node to remove it. Drag to reshape."
    )
    shared_styles.apply_shared_label_style(_shape_hint, "ADV_HELPER_LABEL_STYLE")
    _shape_hint.setWordWrap(True)
    shape_bucket.addWidget(_shape_hint)

    # Visual shape editor
    from ui.tabs.media.spectrum_shape_editor import SpectrumShapeEditor
    _mirror_default_for_editor = tab._default_bool('spotify_visualizer', 'spectrum_mirrored')
    tab.spectrum_shape_editor = SpectrumShapeEditor(
        parent=None,
        mirrored=_mirror_default_for_editor,
        default_nodes=tab._widget_default('spotify_visualizer', 'spectrum_shape_nodes'),
        default_notches_mirrored=tab._widget_default(
            'spotify_visualizer', 'spectrum_notch_positions_mirrored'
        ),
        default_notches_linear=tab._widget_default(
            'spotify_visualizer', 'spectrum_notch_positions_linear'
        ),
        default_lane_strengths_mirrored=tab._widget_default(
            'spotify_visualizer', 'spectrum_lane_strengths_mirrored'
        ),
        default_lane_strengths_linear=tab._widget_default(
            'spotify_visualizer', 'spectrum_lane_strengths_linear'
        ),
    )
    tab.spectrum_shape_editor.nodes_changed.connect(tab._save_settings)
    tab.spectrum_shape_editor.notch_positions_changed.connect(tab._save_settings)
    tab.spectrum_shape_editor.lane_strengths_changed.connect(tab._save_settings)
    shape_bucket.addWidget(tab.spectrum_shape_editor)
    # Connect mirrored checkbox to update editor display
    tab.spectrum_mirrored.stateChanged.connect(
        lambda state: tab.spectrum_shape_editor.set_mirrored(bool(state))
    )


def build_spectrum_render_mode(tab, render_bucket) -> None:
    render_mode_row = _aligned_row(render_bucket, "Render Mode:")
    tab.spectrum_render_mode_group = QButtonGroup(tab)
    tab.spectrum_render_mode_group.setExclusive(True)
    tab.spectrum_render_mode_buttons = {}

    def _make_render_mode_button(text: str, mode: str) -> QPushButton:
        button = QPushButton(text)
        button.setCheckable(True)
        shared_styles.bind_shared_styles(
            button, "MODE_TOGGLE_BUTTON_STYLE", base_style=""
        )
        button.setProperty("renderMode", mode)
        button.clicked.connect(lambda _checked=False, selected=mode: _set_render_mode(selected))
        tab.spectrum_render_mode_group.addButton(button)
        tab.spectrum_render_mode_buttons[mode] = button
        return button

    def _set_render_mode(mode: str, *, save: bool = True) -> None:
        for key, button in tab.spectrum_render_mode_buttons.items():
            previous = button.blockSignals(True)
            try:
                button.setChecked(key == mode)
            finally:
                button.blockSignals(previous)
        changed = getattr(tab, "_spectrum_render_mode", None) != mode
        if changed:
            tab._spectrum_render_mode = mode
            if save:
                tab._force_visualizer_preset_to_custom()
        if save:
            tab._save_settings()

    tab._set_spectrum_render_mode = _set_render_mode
    tab._spectrum_render_mode = tab._default_str(
        "spotify_visualizer", "spectrum_render_mode"
    ).strip().lower()
    if not tab._spectrum_render_mode:
        raise ValueError("Canonical Spectrum render mode is empty")
    render_mode_row.addWidget(_make_render_mode_button("SEGMENTS", "segment"))
    render_mode_row.addWidget(_make_render_mode_button("BAR", "bars"))
    render_mode_row.addStretch()
    for key, button in tab.spectrum_render_mode_buttons.items():
        button.setChecked(key == ("segment" if tab._spectrum_render_mode == "segment" else "bars"))


def build_spectrum_smoothing(tab, render_bucket) -> None:
    from ui.tabs.media.spectrum_smoothing_controls import build_spectrum_smoothing_controls

    build_spectrum_smoothing_controls(tab, render_bucket, mode_key="spectrum")


def build_spectrum_audio_hint(tab, audio_bucket) -> None:
    # --- Audio controls that remain global instead of lane-authored ---
    _influence_hint = QLabel(
        "Lane strength now lives in the top arrows inside the shaper. "
        "These controls only handle global reactivity, shape-floor support, and falloff."
    )
    shared_styles.apply_shared_label_style(_influence_hint, "ADV_HELPER_LABEL_STYLE")
    _influence_hint.setWordWrap(True)
    audio_bucket.addWidget(_influence_hint)
