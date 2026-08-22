"""Application-level capability activation (Phase E).

"Activated" is a distinct authority from a widget instance's ordinary
``enabled`` checkbox or a transition's random-pool membership. It answers a
coarser question: *may this capability's implementation resolve/run at all?*

The canonical persisted schema lives in ``core/settings/default_settings.py``:

- ``widgets.family_activation.<family_id>`` — per widget family;
- ``transitions.activation.<setting_name>`` — per canonical transition.

This module is the presentation-neutral read/write authority over that schema.
It imports no QWidget/Quick/provider/renderer code, so Settings and the runtime
can consult activation cheaply. A missing key means *activated* (True): the
schema opts capabilities out explicitly, never in, so a fresh install and any
pre-Quick settings behave exactly as before this authority existed. H0 resets
these keys to their final canonical Quick-era defaults.

See ``Docs/QtQuick_Migration/07_Settings_Capability_Activation.md``.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

from rendering.transition_registry import (
    canonicalize_transition_name,
    get_transition_setting_names,
)
from rendering.widget_descriptors import (
    get_family_id_for_widget,
    get_widget_family_descriptor,
)

WIDGET_FAMILY_ACTIVATION_KEY = "family_activation"
TRANSITION_ACTIVATION_KEY = "activation"
TRANSITION_POOL_KEY = "pool"
TRANSITION_RANDOM_MODE_KEY = "random_always"


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


# --- Widget families -------------------------------------------------------


def is_widget_family_activated(
    widgets_config: Mapping[str, Any] | None,
    family_id: str,
) -> bool:
    """Return whether a widget family capability is activated.

    Unknown/absent state resolves to activated (True).
    """

    if not isinstance(family_id, str) or not family_id:
        return True
    activation = _as_mapping(_as_mapping(widgets_config).get(WIDGET_FAMILY_ACTIVATION_KEY))
    value = activation.get(family_id, True)
    return bool(value)


def is_widget_activated(
    widgets_config: Mapping[str, Any] | None,
    widget_id: str,
) -> bool:
    """Return whether the family that owns ``widget_id`` is activated.

    Widgets with no owning capability family (e.g. the visualizer) are always
    considered activated because family activation does not gate them.
    """

    family_id = get_family_id_for_widget(widget_id)
    if family_id is None:
        return True
    return is_widget_family_activated(widgets_config, family_id)


def set_widget_family_activated(
    widgets_config: Dict[str, Any],
    family_id: str,
    activated: bool,
) -> Dict[str, Any]:
    """Persist one widget family activation flag in-place; returns the config."""

    if get_widget_family_descriptor(family_id) is None:
        return widgets_config
    activation = widgets_config.get(WIDGET_FAMILY_ACTIVATION_KEY)
    if not isinstance(activation, dict):
        activation = {}
        widgets_config[WIDGET_FAMILY_ACTIVATION_KEY] = activation
    activation[family_id] = bool(activated)
    return widgets_config


# --- Transitions -----------------------------------------------------------


def is_transition_activated(
    transitions_config: Mapping[str, Any] | None,
    transition_name: str,
) -> bool:
    """Return whether a transition capability is activated.

    Accepts canonical setting names, stable ids, and legacy aliases. Unknown or
    absent state resolves to activated (True).
    """

    canonical = canonicalize_transition_name(transition_name, fallback="")
    if not canonical or canonical == "Random":
        return True
    activation = _as_mapping(_as_mapping(transitions_config).get(TRANSITION_ACTIVATION_KEY))
    return bool(activation.get(canonical, True))


def set_transition_activated(
    transitions_config: Dict[str, Any],
    transition_name: str,
    activated: bool,
) -> Dict[str, Any]:
    """Persist one transition activation flag in-place; returns the config."""

    canonical = canonicalize_transition_name(transition_name, fallback="")
    if not canonical or canonical == "Random":
        return transitions_config
    activation = transitions_config.get(TRANSITION_ACTIVATION_KEY)
    if not isinstance(activation, dict):
        activation = {}
        transitions_config[TRANSITION_ACTIVATION_KEY] = activation
    activation[canonical] = bool(activated)
    return transitions_config


def get_activated_transition_names(
    transitions_config: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    """Return canonical transition names that are currently activated."""

    return tuple(
        name
        for name in get_transition_setting_names()
        if is_transition_activated(transitions_config, name)
    )


def get_default_activated_transition(
    transitions_config: Mapping[str, Any] | None,
) -> str:
    """Return a deterministic activated transition to fall back to.

    Prefers Crossfade when activated (the historical safe default), else the
    first activated transition in canonical registry order, else Crossfade as a
    last resort so callers always receive a concrete name.
    """

    if is_transition_activated(transitions_config, "Crossfade"):
        return "Crossfade"
    for name in get_activated_transition_names(transitions_config):
        return name
    return "Crossfade"


def resolve_manual_transition_selection(
    transitions_config: Mapping[str, Any] | None,
    requested: str,
) -> str:
    """Return the canonical manual transition to use, honoring activation.

    A deactivated transition is excluded from explicit runtime selection, so a
    request for one resolves to the deterministic activated fallback. A request
    for an activated transition is returned canonicalized unchanged.
    """

    canonical = canonicalize_transition_name(requested, fallback="")
    if not canonical or canonical == "Random":
        return canonical or "Random"
    if is_transition_activated(transitions_config, canonical):
        return canonical
    return get_default_activated_transition(transitions_config)


def get_effective_random_pool(
    transitions_config: Mapping[str, Any] | None,
) -> tuple[str, ...]:
    """Return the effective random pool: activated ids ∩ saved pool members.

    Pool membership preference is preserved for deactivated transitions (so a
    later reactivation restores the user's choice), but the effective pool a
    runtime may draw from always filters by activation.
    """

    pool = _as_mapping(_as_mapping(transitions_config).get(TRANSITION_POOL_KEY))
    return tuple(
        name
        for name in get_activated_transition_names(transitions_config)
        if bool(pool.get(name, False))
    )


def is_random_mode_effective(
    transitions_config: Mapping[str, Any] | None,
) -> bool:
    """Return whether random mode is on AND has a non-empty effective pool.

    Random mode must not silently run with an empty effective pool; callers use
    this to detect and resolve that state explicitly rather than falling back to
    a renderer default.
    """

    config = _as_mapping(transitions_config)
    if not bool(config.get(TRANSITION_RANDOM_MODE_KEY, False)):
        return False
    return len(get_effective_random_pool(transitions_config)) > 0
