"""Settings bodies built, loaded and saved from a Visualizer mode's spec
(``core/settings/visualizer_mode_settings.py``).

Widgets keep the names the hand-written bodies used: a slider, checkbox or drop-down is
``tab.<key>``; a colour is the QColor ``tab._<key>`` with its swatch ``tab.<key>_btn``. Every edit
moves a curated preset to Custom and saves, as the hand-written bodies did. A control with a ``when``
shows only while the control it names holds the value, following it live and on load.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QCheckBox, QLabel, QSlider, QWidget

from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
from core.settings.visualizer_mode_settings import (
    VISUAL_CONTROLS,
    Choice,
    Colour,
    Custom,
    Direction,
    ScenePath,
    SceneVolumePath,
    SceneCameraPosition,
    ModeSettings,
    Range,
    Slider,
    Toggle,
    Triangle,
    require_mode_settings,
    read_control_value,
)
from ui.color_utils import qcolor_to_list
from ui.styled_popup import ColorSwatchButton
from ui.tabs.media.builder_scaffold import (
    add_builder_swatch_row,
    bind_color_button,
    bind_setting_signal,
    build_collapsible_bucket,
    build_mode_scaffold,
)
from ui.tabs.shared_styles import NoWheelSlider, RecommendedMarkSlider, add_aligned_row_widget
from ui.widgets import StyledComboBox
from ui.widgets.continuous_border import BucketToggle
from ui.widgets.visual_controls import DirectionMapper, RangeSlider, TriangleMapper, ScenePathMapper, SceneVolumeMapper
from core.settings.framed_camera import spec_for_mode
from ui.tabs.media import framed_camera_editor as fce

_LABEL_WIDTH = 150


def _resolve(path: str):
    module, _, name = path.partition(":")
    return getattr(import_module(module), name)


def container_attr(mode_id: str) -> str:
    return f"_{require_mode_settings(mode_id).prefix}_settings_container"


def build_spec_mode_ui(tab, parent_layout, mode_id: str) -> None:
    """Build ``mode_id``'s body: the shared preset/advanced/technical scaffold, then each bucket
    with its controls in the spec's order."""
    spec = require_mode_settings(mode_id)
    prefix = spec.prefix
    scaffold = build_mode_scaffold(
        tab,
        parent_layout,
        mode_key=mode_id,
        settings_container_attr=f"_{prefix}_settings_container",
        preset_slider_attr=get_visualizer_mode_descriptor(mode_id).preset_slider_attr,
        normal_attr=f"_{prefix}_normal",
        advanced_host_attr=f"_{prefix}_advanced_host",
        advanced_toggle_attr=f"_{prefix}_adv_toggle",
        advanced_helper_attr=f"_{prefix}_adv_helper",
        advanced_attr=f"_{prefix}_advanced",
    )
    layouts = {}
    for bucket in spec.buckets:
        _host, layouts[bucket.key] = build_collapsible_bucket(
            tab, scaffold.advanced_layout if bucket.advanced else scaffold.normal_layout,
            mode_key=mode_id, bucket_key=bucket.key, title=bucket.title, helper_text=bucket.helper,
        )
    if spec_for_mode(mode_id) is not None:
        # Shared camera edits repaint every editor of this mode; EB's also shows its paths.
        setattr(tab, f"_{prefix}_camera_refresh",
                _refresh_eb_volume if mode_id == "extruded_bubble" else None)
    if mode_id == "extruded_bubble":
        # EB's many controls are *sectionally* lazy, on top of the existing lazy mode host.
        # Closed buckets allocate neither controls nor signal hookups. Authoritative values
        # live in the latest hydrated config until a bucket is opened, so Save/Custom/preset
        # changes cannot overwrite closed buckets with UI defaults.
        if any(isinstance(entry, Custom) for entry in spec.entries):
            raise ValueError("Section-lazy EB needs an explicit Custom-control hydration contract")
        cache_attr = f"_{prefix}_lazy_values"
        built_attr = f"_{prefix}_lazy_built"
        values = {entry.key: entry.admit(tab._widget_default("spotify_visualizer", entry.key),
                                        tab._widget_default("spotify_visualizer", entry.key))
                  for entry in spec.entries if entry.bucket}
        setattr(tab, cache_attr, values)
        setattr(tab, built_attr, set())
        # A mode body may be rebuilt on the same tab. Its former connection set
        # referenced previous widgets and must not suppress new subscriptions.
        setattr(tab, f"_{prefix}_condition_connected", set())
        rows: dict = {}
        setattr(tab, f"_{prefix}_rows", rows)
        bucket_entries = {bucket.key: [entry for entry in spec.entries if entry.bucket == bucket.key]
                          for bucket in spec.buckets}

        def build_bucket(key: str) -> None:
            built = getattr(tab, built_attr)
            if key in built:
                return
            # Existing open buckets may contain more recent unsaved UI values than
            # the last preset hydration. Never re-load their old cache on expansion.
            getattr(tab, cache_attr).update(collect_spec_mode_settings(tab, mode_id))
            # Mark only after successful creation/hydration; avoid phantom built state.
            new_rows = {}
            grouped = {}
            for entry in bucket_entries[key]:
                if isinstance(entry, Toggle) and entry.row_group:
                    group = entry.row_group
                    if group not in grouped:
                        grouped[group] = _row(layouts[key], entry.label)
                    else:
                        grouped[group][1].addSpacing(16)
                    new_rows[entry.key] = _build_control(tab, layouts[key], entry, grouped[group],
                                                         auto_switch=spec.auto_switch)
                else:
                    new_rows[entry.key] = _build_control(tab, layouts[key], entry,
                                                         auto_switch=spec.auto_switch)
            for _widget, content in grouped.values():
                content.addStretch()
            rows.update(new_rows)
            built.add(key)
            # Load the latest hydrated values, never a stale instance's controls.
            load_spec_mode_settings(tab, mode_id, dict(getattr(tab, cache_attr)),
                                    only_buckets=frozenset((key,)))
            # Rebind conditions against ALL constructed rows, including conditions
            # whose source lives in a different bucket (e.g. water -> light type).
            _bind_conditions(tab, spec, rows)
            _refresh_eb_volume(tab)

        for bucket in spec.buckets:
            host = next(candidate for region in (scaffold.normal_widget, scaffold.advanced_host)
                        for candidate in region.findChildren(QWidget)
                        if candidate.objectName() == f"{mode_id}_bucket_{bucket.key}")
            toggle = host.findChild(BucketToggle)
            if toggle is None:
                raise RuntimeError(f"Missing accordion toggle for {mode_id}/{bucket.key}")
            toggle.toggled.connect(lambda checked, key=bucket.key: build_bucket(key) if checked else None)
            if toggle.isChecked():
                build_bucket(bucket.key)
        return

    rows = {}
    toggle_groups = {}
    for entry in spec.entries:
        if not entry.bucket:
            continue          # set elsewhere (live orbit), not from the body
        layout = layouts[entry.bucket]
        if isinstance(entry, Custom):
            _resolve(entry.build)(tab, layout)
        else:
            if isinstance(entry, Toggle) and entry.row_group:
                group = (entry.bucket, entry.row_group)
                if group not in toggle_groups:
                    toggle_groups[group] = _row(layout, entry.label)
                else:
                    toggle_groups[group][1].addSpacing(16)
                rows[entry.key] = _build_control(tab, layout, entry, toggle_groups[group], auto_switch=spec.auto_switch)
            else:
                rows[entry.key] = _build_control(tab, layout, entry, auto_switch=spec.auto_switch)
    for _row_widget, content in toggle_groups.values():
        content.addStretch()
    setattr(tab, f"_{prefix}_rows", rows)
    _bind_conditions(tab, spec, rows)


def _bind_conditions(tab, spec: ModeSettings, rows) -> None:
    """Apply spec conditions to currently constructed rows, including cross-bucket references.

    For section-lazy EB, a condition source may still be unbuilt. Read its canonical
    hydrated value and subscribe ONCE when that source's bucket is eventually opened.
    On a new bucket the one current predicate is replaced, not stacked.
    """
    def terms(condition):
        return (condition,) if isinstance(condition[0], str) else condition

    conditional = [(rows[control.key], terms(control.when)) for control in spec.controls
                   if control.when and control.key in rows]
    enabled = [(getattr(tab, f"{control.key}_btn" if isinstance(control, Colour) else control.key), control)
               for control in spec.controls if getattr(control, "enabled_when", ())
               and control.key in rows]
    if not conditional and not enabled:
        return

    def matches(key, value):
        control = spec.control(key)
        if not hasattr(tab, key):
            current = getattr(tab, f"_{spec.prefix}_lazy_values", {}).get(key,
                       tab._widget_default("spotify_visualizer", key))
        else:
            current = _current_value(tab, control)
        return current in value if isinstance(value, tuple) else current == value

    def apply(*_args) -> None:
        for row, conditions in conditional:
            row.setVisible(all(matches(key, value) for key, value in conditions))
        for widget, control in enabled:
            available = not control.availability or bool(_resolve(control.availability[0]))
            widget.setEnabled(available and all(matches(key, value) for key, value in terms(control.enabled_when)))

    condition_attr = f"_{spec.prefix}_apply_conditions"
    setattr(tab, condition_attr, apply)
    condition_keys = {key for _row, conditions in conditional for key, _value in conditions}
    condition_keys.update(key for _widget, control in enabled for key, _value in terms(control.enabled_when))
    connections_attr = f"_{spec.prefix}_condition_connected"
    connected = getattr(tab, connections_attr, None)
    if connected is None:
        connected = set()
        setattr(tab, connections_attr, connected)
    for key in condition_keys:
        if key in connected or not hasattr(tab, key):
            continue
        control = spec.control(key)
        widget = getattr(tab, control.key)
        signal = (widget.toggled if isinstance(control, Toggle) else widget.valueChanged
                  if isinstance(control, (Slider, *VISUAL_CONTROLS)) else widget.currentIndexChanged)
        signal.connect(lambda *_args, name=condition_attr: getattr(tab, name)())
        connected.add(key)
    apply()


def _current_value(tab, control):
    widget = getattr(tab, control.key)
    if isinstance(control, Toggle):
        return widget.isChecked()
    if isinstance(control, Slider):
        return control.admit(widget.value() / control.scale, control.low)
    if isinstance(control, Range):
        low, high = widget.value()
        return control.admit((low / control.scale, high / control.scale), (control.low, control.high))
    if isinstance(control, (Triangle, Direction)):
        return control.admit(widget.value(), widget.value())
    if control.indexed:
        return widget.currentIndex()
    return widget.currentData() if control.labels else widget.currentText()


def _row(layout, label: str):
    widget, content, _ = add_aligned_row_widget(layout, label, label_width=_LABEL_WIDTH)
    return widget, content


def _control_tooltip(control):
    """Bound EB tooltips to readable rows instead of one very wide Qt popup.

    Qt rich-text tooltips need explicit line boundaries on some Windows themes;
    the source Settings text is still the sole authority. Other modes unchanged.
    """
    if not control.key.startswith("extruded_bubble_") or not control.tooltip:
        return control.tooltip
    import html
    import textwrap
    lines = textwrap.wrap(control.tooltip, width=59, break_long_words=False,
                          break_on_hyphens=False)
    return "<html><div style=\"white-space:normal;\">" + "<br/>".join(html.escape(line) for line in lines) + "</div></html>"


def _build_control(tab, layout, control, shared_row=None, *, auto_switch=True):
    """Build one control's row; returns the row widget (hidden with the control)."""
    default = tab._widget_default("spotify_visualizer", control.key)
    if isinstance(control, Colour):
        if control.swatch_row:
            row, content, _label = add_builder_swatch_row(layout, control.label, label_width=_LABEL_WIDTH)
        else:
            row, content = _row(layout, control.label)
        colour = QColor(*control.admit(default, default))
        setattr(tab, f"_{control.key}", colour)
        button = ColorSwatchButton(title=control.title, show_alpha=control.alpha)
        button.setToolTip(_control_tooltip(control))
        if control.key.startswith("extruded_bubble_"):
            row.setToolTip(_control_tooltip(control))  # Label/row hover, even for swatches.
        _apply_availability(button, control)
        bind_color_button(tab, button, f"_{control.key}", auto_switch=auto_switch, initial_color=colour)
        setattr(tab, f"{control.key}_btn", button)
        content.addWidget(button)
        content.addStretch()
        return row
    if isinstance(control, VISUAL_CONTROLS):
        return _build_visual_control(tab, layout, control, default, auto_switch=auto_switch)
    if shared_row is not None:
        row, content = shared_row
    elif isinstance(control, Toggle) and not control.label:
        row = widget = QCheckBox(control.text)       # stands alone across the bucket
        layout.addWidget(widget)
    else:
        row, content = _row(layout, control.label)
    if isinstance(control, Slider):
        widget = (NoWheelSlider(Qt.Orientation.Horizontal) if control.recommended is None
                  else RecommendedMarkSlider(Qt.Orientation.Horizontal))
        widget.setRange(round(control.low * control.scale), round(control.high * control.scale))
        widget.setValue(control.position(control.admit(default, default)))
        if control.recommended is not None:
            widget.set_recommended_value(control.position(control.recommended))
        if control.tick:
            widget.setTickPosition(QSlider.TickPosition.TicksBelow)
            widget.setTickInterval(control.tick)
        value = QLabel()
        value.setText(control.text(widget.value()))
        setattr(tab, f"{control.key}_label", value)
        widget.valueChanged.connect(lambda position, c=control, label=value: label.setText(c.text(position)))
        framed = fce.framed_mode_of(control.key)
        if framed is not None and control.key == spec_for_mode(framed).key('camera_fov'):
            widget.valueChanged.connect(lambda *_, m=framed: fce.refresh_editors(tab, m))
        bind_setting_signal(tab, widget.valueChanged, auto_switch=auto_switch)
        content.addWidget(widget)
        content.addWidget(value)
    elif isinstance(control, Toggle):
        if control.label or shared_row is not None:
            widget = QCheckBox(control.text)
            content.addWidget(widget)
            if shared_row is None:
                content.addStretch()
        widget.setProperty("circleIndicator", True)
        widget.setChecked(control.admit(default, default))
        bind_setting_signal(tab, widget.toggled, auto_switch=auto_switch)
    else:
        widget = StyledComboBox(size_variant=control.size_variant or ("compact" if control.compact else "regular"))
        if control.labels:
            if len(control.labels) != len(control.choices):
                raise ValueError(f"{control.key} choice labels must match its values")
            for label, value in zip(control.labels, control.choices):
                widget.addItem(label, value)
        else:
            widget.addItems(list(control.choices))
        if control.indexed:
            widget.setCurrentIndex(control.admit(default, default))
            bind_setting_signal(tab, widget.currentIndexChanged, auto_switch=auto_switch)
        elif control.labels:
            widget.setCurrentIndex(widget.findData(control.admit(default, default)))
            bind_setting_signal(tab, widget.currentIndexChanged, auto_switch=auto_switch)
        else:
            widget.setCurrentText(control.admit(default, default))
            if control.key in ('extruded_bubble_light_type', 'extruded_bubble_emission_geometry',
                               'extruded_bubble_lighting_coverage'):
                widget.currentTextChanged.connect(lambda *_: _refresh_eb_volume(tab))
            bind_setting_signal(tab, widget.currentTextChanged, auto_switch=auto_switch)
        content.addWidget(widget)
        content.addStretch()
    widget.setToolTip(_control_tooltip(control))
    if control.key.startswith("extruded_bubble_"):
        row.setToolTip(_control_tooltip(control))  # Tooltip remains discoverable over the label.
    if isinstance(control, Slider) and control.bottom_padding:
        margins = row.layout().contentsMargins()
        row.layout().setContentsMargins(margins.left(), margins.top(), margins.right(),
                                       margins.bottom() + control.bottom_padding)
    _apply_availability(widget, control)
    setattr(tab, control.key, widget)
    return row


def _build_visual_control(tab, layout, control, default, *, auto_switch=True):
    """A range slider, triangle mapper or direction mapper with its value label. The value label follows
    every move; the setting saves once per gesture or keyboard step (``valueCommitted``)."""
    row, content = _row(layout, control.label)
    value = control.admit(default, default)
    # EB-R32: formatter is unconditional, including every current/future visual
    # subtype. A branch-local `describe` previously blocked EB Settings entirely.
    describe = control.text
    if isinstance(control, Range):
        widget = RangeSlider(round(control.low * control.scale), round(control.high * control.scale))
        widget.setValue(control.positions(value))
    elif isinstance(control, Triangle):
        widget = TriangleMapper(control.corners)
        widget.setValue(value)
    elif isinstance(control, (SceneVolumePath, SceneCameraPosition)):
        widget = SceneVolumeMapper(camera_only=isinstance(control, SceneCameraPosition))
        widget.setValue(value)
    elif isinstance(control, ScenePath):
        widget = ScenePathMapper()
        widget.setValue(value)
    else:
        widget = DirectionMapper((control.height_low, control.height_high), centre_text=control.centre_text,
                                 marker=control.marker, midline=control.midline)
        widget.setValue(value)
    widget.setAccessibleName(control.label.rstrip(":"))
    label = QLabel(describe(widget.value()))
    if isinstance(widget, SceneVolumeMapper):
        label.hide()  # Coordinates remain in the accessible description, not duplicated next to the editor.
    setattr(tab, f"{control.key}_label", label)
    widget.valueChanged.connect(lambda current, d=describe, l=label: l.setText(d(current)))
    bind_setting_signal(tab, widget.valueCommitted,
                        auto_switch=auto_switch and not isinstance(control, SceneCameraPosition))
    if isinstance(control, (SceneVolumePath, SceneCameraPosition)):
        framed = fce.framed_mode_of(control.key)
        widget.cameraAimChanged.connect(lambda angles, m=framed: fce.set_aim(tab, m, angles, commit=False))
        widget.cameraAimCommitted.connect(lambda angles, m=framed: fce.set_aim(tab, m, angles, commit=True))
        if control.key == 'extruded_bubble_ray_path':
            widget.linkedSourceChanged.connect(lambda source: _set_eb_light_source(tab, source, commit=False))
            widget.linkedSourceCommitted.connect(lambda source: _set_eb_light_source(tab, source, commit=True))
        # Cross-path overlays are driven by the SAME saved settings and live widgets;
        # never allocate a second Settings camera or world-coordinate owner.
        widget.valueChanged.connect(lambda *_, m=framed: fce.refresh_editors(tab, m))
        if isinstance(control, SceneCameraPosition):
            # Ctrl+Z / Ctrl+Y step through the camera's last few committed gestures (in memory only).
            widget.valueCommitted.connect(lambda *_, m=framed: fce.note_committed(tab, m))
            widget.undoRequested.connect(lambda m=framed: fce.undo(tab, m))
            widget.redoRequested.connect(lambda m=framed: fce.redo(tab, m))
        if isinstance(control, SceneVolumePath):
            widget.cameraOffsetChanged.connect(lambda offset: _set_eb_camera_offset(tab, offset, commit=False))
            widget.cameraOffsetCommitted.connect(lambda offset: _set_eb_camera_offset(tab, offset, commit=True))
    content.addWidget(widget)
    content.addWidget(label)
    if not isinstance(control, Range):
        content.addStretch()            # the mappers keep their size; a range fills the row as a slider does
    widget.setToolTip(_control_tooltip(control))
    if control.key.startswith("extruded_bubble_"):
        row.setToolTip(_control_tooltip(control))  # The visual editor's entire row is descriptive.
    _apply_availability(widget, control)
    setattr(tab, control.key, widget)
    return row


def _apply_availability(widget, control) -> None:
    if control.availability:
        flag, unavailable_tooltip = control.availability
        available = bool(_resolve(flag))
        widget.setEnabled(available)
        widget.setToolTip(control.tooltip if available else unavailable_tooltip)


def load_spec_mode_settings(tab, mode_id: str, config, *, only_buckets: frozenset[str] | None = None) -> None:
    """Show ``config``'s values (canonical defaults for missing ones), repaired as the model
    repairs them. Signals are blocked so loading saves nothing and switches no preset.
    ``only_buckets`` is strictly for first construction of an EB bucket: it hydrates
    newly constructed controls from the already-current cache, without resetting
    unrelated live controls or re-admitting every closed-bucket config value.
    Real preset loads must continue to update ALL built and unbuilt buckets."""
    spec = require_mode_settings(mode_id)
    config = config if isinstance(config, dict) else {}
    lazy_built = getattr(tab, f"_{spec.prefix}_lazy_built", None) if mode_id == "extruded_bubble" else None
    if only_buckets is not None and lazy_built is None:
        raise ValueError("Partial bucket hydration is reserved for the lazy EB owner")
    if lazy_built is not None and only_buckets is None:
        cache = getattr(tab, f"_{spec.prefix}_lazy_values")
        for entry in spec.entries:
            if entry.bucket and not isinstance(entry, Custom):
                default = tab._widget_default("spotify_visualizer", entry.key)
                cache[entry.key] = entry.admit(read_control_value(entry, config.get, default), default)
    for entry in spec.entries:
        if not entry.bucket:
            continue
        if only_buckets is not None and entry.bucket not in only_buckets:
            continue
        if lazy_built is not None and entry.bucket not in lazy_built:
            continue
        if isinstance(entry, Custom):
            if entry.load:
                _resolve(entry.load)(tab, config)
            continue
        default = tab._widget_default("spotify_visualizer", entry.key)
        value = entry.admit(read_control_value(entry, config.get, default), default)
        if isinstance(entry, Colour):
            colour = QColor(*value)
            setattr(tab, f"_{entry.key}", colour)
            button = getattr(tab, f"{entry.key}_btn", None)
            if button is not None:
                button.set_color(colour)
                _apply_availability(button, entry)
            continue
        widget = getattr(tab, entry.key, None)
        if widget is None:
            continue
        previous = widget.blockSignals(True)
        try:
            if isinstance(entry, Range):
                widget.setValue(entry.positions(value))
            elif isinstance(entry, (Triangle, Direction)):
                widget.setValue(value)
            elif isinstance(entry, Slider):
                widget.setValue(entry.position(value))
            elif isinstance(entry, Toggle):
                widget.setChecked(value)
            elif entry.indexed:
                widget.setCurrentIndex(value)
            elif entry.labels:
                widget.setCurrentIndex(widget.findData(value))
            else:
                widget.setCurrentText(value)
        finally:
            widget.blockSignals(previous)
        if isinstance(entry, (Slider, *VISUAL_CONTROLS)):
            # Its value label follows valueChanged, which was blocked.
            getattr(tab, f"{entry.key}_label").setText(entry.text(widget.value()))
        _apply_availability(widget, entry)
    # Conditions follow their controls' signals, which were blocked.
    if spec_for_mode(mode_id) is not None:
        if only_buckets is None:
            fce.hydrate_pose(tab, mode_id, config)
        fce.refresh_editors(tab, mode_id)
    apply = getattr(tab, f"_{spec.prefix}_apply_conditions", None)
    if apply is not None:
        apply()


def collect_spec_mode_settings(tab, mode_id: str) -> dict[str, Any]:
    """The body's values as persisted (sliders unscaled, colours as RGBA lists)."""
    spec: ModeSettings = require_mode_settings(mode_id)
    values: dict[str, Any] = {}
    lazy_built = getattr(tab, f"_{spec.prefix}_lazy_built", None) if mode_id == "extruded_bubble" else None
    cache = getattr(tab, f"_{spec.prefix}_lazy_values", {}) if lazy_built is not None else {}
    for entry in spec.entries:
        if not entry.bucket:
            continue
        if lazy_built is not None and entry.bucket not in lazy_built:
            cached = cache[entry.key]
            values[entry.key] = list(cached) if isinstance(entry, Colour) else cached
            continue
        if isinstance(entry, Custom):
            if entry.collect:
                values.update(_resolve(entry.collect)(tab))
            continue
        if isinstance(entry, Colour):
            values[entry.key] = qcolor_to_list(getattr(tab, f"_{entry.key}", None),
                                               tab._widget_default("spotify_visualizer", entry.key))
            continue
        values[entry.key] = _current_value(tab, entry)
    if spec_for_mode(mode_id) is not None:
        values = fce.collected(tab, mode_id, values)
    return values


def _eb_live_value(tab, key):
    return fce.live_value(tab, 'extruded_bubble', key)


def _eb_base_eye(tab):
    """The shared orbit/pan baseline, before the editor's existing XYZ offset."""
    return fce.base_eye(tab, 'extruded_bubble')


def _refresh_eb_volume(tab):
    """Repaint constructed 3D controls only; never open a closed bucket."""
    if not hasattr(tab, '_extruded_bubble_lazy_values'):
        return
    camera = fce.admit_offset(tab, 'extruded_bubble', _eb_live_value(tab, 'extruded_bubble_camera_position'))
    base = fce.normalized_base(tab, 'extruded_bubble')
    keys = {'stream':'extruded_bubble_stream_direction',
            'light':'extruded_bubble_light_direction',
            'rays':'extruded_bubble_ray_path'}
    angles = fce.camera_angles(tab, 'extruded_bubble')
    deep = _eb_live_value(tab, 'extruded_bubble_light_type') == 'Deep Light'
    light = _eb_live_value(tab, 'extruded_bubble_light_direction')
    effective = {role: _eb_live_value(tab, key) for role, key in keys.items()}
    if deep:
        effective['rays'] = tuple(light[:3]) + tuple(effective['rays'][3:])
    from core.settings.visualizer_paths import direction_of
    emission_geometry = _eb_live_value(tab, 'extruded_bubble_emission_geometry')
    lighting_coverage = _eb_live_value(tab, 'extruded_bubble_lighting_coverage')
    light_guides = _eb_scene_light_guides(tab, deep, light, effective['rays'])
    for role, key in keys.items():
        widget = getattr(tab, key, None)
        if not isinstance(widget, SceneVolumeMapper):
            continue
        ghosts = {other: effective[other] for other in keys if other != role}
        if role == 'stream':
            try:
                scene_direction, scene_source = direction_of(effective[role]), effective[role][:3]
            except ValueError:
                scene_direction, scene_source = (0., 0., 0.), effective[role][:3]
        else:
            # SCENE light's actual entry faces, as the renderer admits them (none for positional Deep light).
            scene_direction, scene_source = light_guides
        widget.setSceneReferences(paths=ghosts, base_eye=base, camera_offset=camera,
                                  camera_angles=angles,
                                  linked_source=light[:3] if deep and role == 'rays' else None,
                                  coverage_geometry=emission_geometry if role == 'stream' else lighting_coverage,
                                  scene_direction=scene_direction,
                                  scene_source=scene_source,
                                  scene_range=None if role == 'stream' else _eb_scene_light_range(deep, light,
                                                                                                  effective['rays']))
    fce.refresh(tab, 'extruded_bubble', references=effective)


def _eb_scene_light_guides(tab, deep, light, rays):
    """(direction, source) for the Light/Rays editors' SCENE face guides: Surface sunlight's travel (the refracted
    sun, ``scene_light_support``) entering through the water surface; Deep light has no entry face."""
    if deep:
        return (0., 0., 0.), tuple(rays[:3])
    import math
    from core.settings.visualizer_paths import admit_path, direction_of
    from rendering.gl_programs.extruded_bubble_scene import water_sun_below_safe
    try:
        sun = tuple(-v for v in direction_of(admit_path(light, [0.0, 55.0], 'light')))
    except ValueError:
        return (0., 0., 0.), tuple(rays[:3])
    norm = math.sqrt(sum(v * v for v in sun)) or 1.0
    travel = tuple(-v for v in water_sun_below_safe(tuple(v / norm for v in sun)))
    return travel, (0., 1., 0.)


def _eb_scene_light_range(deep, light, rays):
    """Deep SCENE light's lit region for the editors: (normalized emitter, per-axis normalized range), the same
    Light Source -> Ray End range the renderer uses (``scene_light_support``); None for directional sunlight or a
    zero range (unshaped)."""
    if not deep:
        return None
    import math
    from core.settings.visualizer_paths import WORLD_HALF, world_point
    source, end = world_point(light[:3]), world_point(rays[3:])
    reach = math.dist(source, end)
    if reach <= 1e-6:
        return None
    return tuple(light[:3]), tuple(reach / h for h in WORLD_HALF)


def _admit_eb_camera_offset(tab, offset):
    return fce.admit_offset(tab, 'extruded_bubble', offset)


def _set_eb_camera_offset(tab, offset, *, commit):
    """Camera diamond gestures use the existing Settings persistence owner."""
    fce.set_offset(tab, 'extruded_bubble', offset, commit=commit)


def _set_eb_camera_aim(tab, angles, *, commit):
    """Aiming edits the existing live turn/tilt, NOT a separate FOV or camera."""
    fce.set_aim(tab, 'extruded_bubble', angles, commit=commit)


def _set_eb_light_source(tab, source, *, commit):
    """Deep rays share the actual emitter Source, with a separately authored End."""
    key='extruded_bubble_light_direction'
    old = list(_eb_live_value(tab,key))
    old[:3]=list(source)
    from core.settings.visualizer_mode_settings import require_mode_settings
    descriptor=require_mode_settings('extruded_bubble').control(key)
    updated=descriptor.admit(old,old)
    tab._extruded_bubble_lazy_values[key]=updated
    widget=getattr(tab,key,None)
    if isinstance(widget,SceneVolumeMapper):
        blocked=widget.blockSignals(True)
        try: widget.setValue(updated)
        finally: widget.blockSignals(blocked)
    _refresh_eb_volume(tab)
    if commit:
        tab._save_settings()


__all__ = ["build_spec_mode_ui", "collect_spec_mode_settings", "container_attr", "load_spec_mode_settings"]
