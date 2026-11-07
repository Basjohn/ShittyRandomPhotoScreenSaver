"""Settings bodies of the Visualizer modes, loaded and saved from each mode's spec
(``core/settings/visualizer_mode_settings.py``).

Every mode is edited in its Studio (``ui/studio``), which has parity+ with the buckets it replaced
(``tests/test_visualizer_studio_parity.py`` proves it from the registries). A mode's Settings body is the preset row
with its OPEN STUDIO launcher, its 3D Detail row where it has one, and one sentence; no other widget is built, hidden
or not (Neon Lake's terrain is painted with the Studio's brush). The section-lazy cache (``_<prefix>_lazy_values``)
is the only owner of the body's values, the technical (audio analysis) values included, so loading, collecting,
saving, preset switching and Custom snapshots run through the unchanged owners without a QWidget value owner.
"""
from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from typing import Any

from PySide6.QtWidgets import QLabel

from core.settings.framed_camera import spec_for_mode
from core.settings.visualizer_mode_registry import get_visualizer_mode_descriptor
from core.settings.visualizer_mode_settings import Colour, Custom, read_control_value, require_mode_settings
from ui.tabs.media import framed_camera_editor as fce
from ui.tabs.media.builder_scaffold import build_mode_body
from ui.tabs.media.technical_controls import admitted_technical_values, technical_storage_keys


def _resolve(path: str):
    module, _, name = path.partition(":")
    return getattr(import_module(module), name)


def container_attr(mode_id: str) -> str:
    return f"_{require_mode_settings(mode_id).prefix}_settings_container"


def body_keys(mode_id: str) -> tuple[str, ...]:
    """Every key the mode body loads and collects, in spec order: its bucketed controls, each Custom row's keys and
    the bucketless controls a Custom row edits (Spectrum's Render Mode, Bubble's Drift, Sphere's Finish and colours).
    The live view pose (orbit turn/tilt, scene scale and pan) is not the body's: it is set by flying the view."""
    spec = require_mode_settings(mode_id)
    descriptor = get_visualizer_mode_descriptor(mode_id)
    view = set(descriptor.view_orbit_settings) | set(descriptor.scene_transform_settings)
    out: list[str] = []
    for entry in spec.entries:
        if isinstance(entry, Custom):
            out.extend(entry.keys)
        elif entry.bucket or entry.key not in view:
            out.append(entry.key)
    return tuple(out)


def technical_values(tab, mode_id: str) -> dict[str, Any]:
    """The mode's technical values as the cache holds them ({} while its body is unbuilt)."""
    cache = getattr(tab, f"_{require_mode_settings(mode_id).prefix}_lazy_values", None)
    if not isinstance(cache, dict):
        return {}
    return {key: cache[key] for key in technical_storage_keys(mode_id) if key in cache}


def _admitted(tab, spec, key: str, config) -> Any:
    """``config``'s value of one body key (the canonical default when absent), admitted as the model admits it: a
    control by its spec, a Custom row's key by the row's ``admit`` (else the stored record passes through)."""
    default = tab._widget_default("spotify_visualizer", key)
    try:
        control = spec.control(key)
    except KeyError:
        row = next((e for e in spec.entries if isinstance(e, Custom) and key in e.keys), None)
        value = config.get(key, default)
        return _resolve(row.admit)(key, value, default) if row is not None and row.admit else deepcopy(value)
    return control.admit(read_control_value(control, config.get, default), default)


def build_studio_owned_mode_ui(tab, parent_layout, mode_id: str, intro: str) -> None:
    """The mode's Settings body: the preset row (OPEN STUDIO is in it), the 3D Detail row where the mode has one,
    and one sentence. No other widget is built, hidden or not: the section-lazy cache is the only owner of every body
    and technical value, seeded with the canonical defaults until the body is hydrated."""
    spec = require_mode_settings(mode_id)
    for bucket in spec.buckets:
        tab.get_visualizer_bucket_state(mode_id, bucket.key)
    prefix = spec.prefix
    body = build_mode_body(
        tab,
        parent_layout,
        mode_key=mode_id,
        settings_container_attr=f"_{prefix}_settings_container",
        preset_slider_attr=get_visualizer_mode_descriptor(mode_id).preset_slider_attr,
    )
    cache = {key: _admitted(tab, spec, key, {}) for key in body_keys(mode_id)}
    cache.update(admitted_technical_values(tab, mode_id, {}))
    setattr(tab, f"_{prefix}_lazy_values", cache)
    text = QLabel(intro)
    text.setObjectName(f"{mode_id}_studio_intro")
    text.setWordWrap(True)
    body.layout.addWidget(text)
    _add_studio_launcher(tab, mode_id)


def _add_studio_launcher(tab, mode_id: str) -> None:
    """The mode's entry to its Studio (modes with a Studio adapter only), in the preset row where Edit
    Preset was: offered on every preset slot, and the Studio opens on the slot shown.

    The preset's camera-save checkbox stays with the preset slider, unchanged."""
    from ui.studio.registry import has_studio, studio_modes
    if not has_studio(mode_id):
        return
    from ui.widgets.outlined_button import OutlinedButton
    title = next(entry.title for entry in studio_modes() if entry.mode_id == mode_id)    # the Studio's own name
    # The preset row's own button style, in capitals and two sizes up (12 -> 14 px) so the Studio stands out in
    # the row without shouting (operator, 6 Nov).
    button = OutlinedButton("OPEN STUDIO", role="secondary", font_px=14)
    button.setObjectName(f"{mode_id}_open_studio")
    button.setToolTip(f"Edit this preset in the {title} Studio's large live preview. Settings hides while the "
                      "Studio is open and returns when it closes.")

    def open_studio() -> None:
        from ui.studio.settings_link import open_mode_studio
        open_mode_studio(tab, mode_id)

    button.clicked.connect(open_studio)
    setattr(tab, f"_{require_mode_settings(mode_id).prefix}_studio_button", button)
    slider = getattr(tab, get_visualizer_mode_descriptor(mode_id).preset_slider_attr)
    slider.set_studio_launcher(button)


def load_spec_mode_settings(tab, mode_id: str, config) -> None:
    """Hold ``config``'s values (canonical defaults for missing ones), admitted as the model admits them. Loading
    saves nothing and switches no preset."""
    spec = require_mode_settings(mode_id)
    config = config if isinstance(config, dict) else {}
    cache = getattr(tab, f"_{spec.prefix}_lazy_values")
    for key in body_keys(mode_id):
        cache[key] = _admitted(tab, spec, key, config)
    cache.update(admitted_technical_values(tab, mode_id, config))
    if spec_for_mode(mode_id) is not None:
        fce.hydrate_pose(tab, mode_id, config)
        fce.refresh_editors(tab, mode_id)


def collect_spec_mode_settings(tab, mode_id: str) -> dict[str, Any]:
    """The body's and technical values as persisted (colours as RGBA lists)."""
    spec = require_mode_settings(mode_id)
    cache = getattr(tab, f"_{spec.prefix}_lazy_values")
    values: dict[str, Any] = {}
    for key in body_keys(mode_id):
        value = cache[key]
        values[key] = list(value) if isinstance(_control(spec, key), Colour) else deepcopy(value)
    for key in technical_storage_keys(mode_id):
        values[key] = cache[key]
    if spec_for_mode(mode_id) is not None:
        values = fce.collected(tab, mode_id, values)
    return values


def _control(spec, key: str):
    try:
        return spec.control(key)
    except KeyError:
        return None


__all__ = ["body_keys", "build_studio_owned_mode_ui", "collect_spec_mode_settings", "container_attr",
           "load_spec_mode_settings", "technical_values"]
