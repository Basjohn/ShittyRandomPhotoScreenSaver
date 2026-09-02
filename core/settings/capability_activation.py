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
from core.settings.widget_family_catalog import (
    get_family_id_for_widget,
    get_widget_family_descriptor,
    get_widget_family_descriptors,
)

WIDGET_FAMILY_ACTIVATION_KEY = "family_activation"
TRANSITION_ACTIVATION_KEY = "activation"
TRANSITION_POOL_KEY = "pool"
TRANSITION_RANDOM_MODE_KEY = "random_always"
TRANSITION_MANUAL_TYPE_KEY = "type"

# The deterministic transition the runtime recovers to when a persisted state is
# malformed (zero activated transitions). Reactivating it is an explicit canonical
# state repair (see ``normalize_transition_capability_state``), never a hidden
# renderer/factory bypass that runs a deactivated transition.
DEFAULT_RECOVERY_TRANSITION = "Crossfade"


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

    Widgets with no owning capability family return activated (True).
    """

    family_id = get_family_id_for_widget(widget_id)
    if family_id is None:
        return True
    return is_widget_family_activated(widgets_config, family_id)


def is_widget_family_dependency_satisfied(
    widgets_config: Mapping[str, Any] | None,
    family_id: str,
) -> bool:
    """Return whether every required family for ``family_id`` is activated."""

    descriptor = get_widget_family_descriptor(family_id)
    if descriptor is None:
        return True
    return all(
        is_widget_family_activated(widgets_config, required)
        for required in descriptor.required_family_ids
    )


def is_widget_family_effective(
    widgets_config: Mapping[str, Any] | None,
    family_id: str,
) -> bool:
    """Return whether a family is activated AND its dependencies are satisfied."""

    return (
        is_widget_family_activated(widgets_config, family_id)
        and is_widget_family_dependency_satisfied(widgets_config, family_id)
    )


def normalize_widget_capability_state(widgets_config: Dict[str, Any]) -> bool:
    """Enforce widget-family capability dependencies in-place; returns changed.

    The single neutral dependency authority: a family whose required families are
    not all activated is forced off (e.g. ``media=False`` forces
    ``visualizers=False``). Never activates a dependency implicitly. Callers
    persist when this returns True.
    """

    if not isinstance(widgets_config, dict):
        return False
    changed = False
    # Iterate to a fixed point so transitive dependencies settle.
    for _ in range(len(get_widget_family_descriptors()) + 1):
        pass_changed = False
        for descriptor in get_widget_family_descriptors():
            if not descriptor.required_family_ids:
                continue
            if not is_widget_family_activated(widgets_config, descriptor.family_id):
                continue
            if not is_widget_family_dependency_satisfied(widgets_config, descriptor.family_id):
                set_widget_family_activated(widgets_config, descriptor.family_id, False)
                pass_changed = True
                changed = True
        if not pass_changed:
            break
    return changed


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


def ensure_recovery_transition_activated(transitions_config: Dict[str, Any]) -> bool:
    """Guarantee the deterministic recovery transition (Crossfade) is activated.

    This is the explicit canonical state-repair a runtime admission seam performs
    when hardware filtering has left no activated candidate at all: rather than
    silently executing a deactivated Crossfade, the seam reactivates it in
    canonical settings state (persisting when this returns True) and then admits
    it normally. Returns True when a repair was made.
    """

    if not isinstance(transitions_config, dict):
        return False
    if is_transition_activated(transitions_config, DEFAULT_RECOVERY_TRANSITION):
        return False
    set_transition_activated(transitions_config, DEFAULT_RECOVERY_TRANSITION, True)
    return True


def normalize_transition_capability_state(transitions_config: Dict[str, Any]) -> bool:
    """Enforce the transition capability invariants on a mutable config in-place.

    This is the ONE canonical normalization authority for transition activation,
    consumed consistently by E2 SETUP, engine Random preparation, the transition
    factory admission boundary, and C-key cycling. It enforces:

    1. **At least one activated transition.** Malformed/legacy all-false state
       reactivates the deterministic recovery transition (Crossfade). This is an
       explicit, persistable state repair — callers persist when this returns
       True — not a hidden bypass that runs a deactivated transition.
    2. **Legacy ``type="Random"`` is not a second Random authority (E2.6).** The
       single random-mode authority is ``random_always``. A persisted manual
       ``type`` of ``"Random"`` is converted to ``random_always=True`` plus a
       concrete activated manual ``type``, so the runtime never treats the manual
       type string itself as a random trigger.
    3. **Random mode is never effective with an empty effective pool.** If Random
       is on but ``activated ∩ pool`` is empty, Random is turned off and a
       deterministic activated manual selection is persisted. Saved pool
       membership is preserved (never erased), so reactivating transitions
       restores the user's prior pool choice.

    Returns True when any change was made. hardware availability is intentionally
    NOT considered here (it is a rendering-side concern applied at the seams);
    this authority only reconciles activation and pool semantics.
    """

    if not isinstance(transitions_config, dict):
        return False

    changed = False

    # Invariant 1: at least one activated transition.
    if not get_activated_transition_names(transitions_config):
        set_transition_activated(transitions_config, DEFAULT_RECOVERY_TRANSITION, True)
        changed = True

    # Invariant 2 (E2.6): legacy type="Random" -> single random_always authority
    # plus a concrete activated manual type.
    manual_type = transitions_config.get(TRANSITION_MANUAL_TYPE_KEY)
    if canonicalize_transition_name(manual_type, fallback="") == "Random":
        transitions_config[TRANSITION_RANDOM_MODE_KEY] = True
        transitions_config[TRANSITION_MANUAL_TYPE_KEY] = (
            get_default_activated_transition(transitions_config)
        )
        changed = True

    # Invariant 2b: the concrete manual type must itself be activated. A manual
    # transition that was deactivated resolves to a deterministic activated
    # replacement (never left pointing at a deactivated transition).
    canonical_manual = canonicalize_transition_name(
        transitions_config.get(TRANSITION_MANUAL_TYPE_KEY), fallback=""
    )
    if (
        canonical_manual
        and canonical_manual != "Random"
        and not is_transition_activated(transitions_config, canonical_manual)
    ):
        transitions_config[TRANSITION_MANUAL_TYPE_KEY] = (
            get_default_activated_transition(transitions_config)
        )
        changed = True

    # Invariant 3: Random not effective with an empty effective pool.
    if bool(transitions_config.get(TRANSITION_RANDOM_MODE_KEY, False)):
        if not get_effective_random_pool(transitions_config):
            transitions_config[TRANSITION_RANDOM_MODE_KEY] = False
            transitions_config[TRANSITION_MANUAL_TYPE_KEY] = (
                get_default_activated_transition(transitions_config)
            )
            changed = True

    return changed


def apply_transition_menu_selection(
    transitions_config: Dict[str, Any],
    selection: str,
) -> bool:
    """Apply one admitted context-menu transition choice in-place.

    This is the presentation-neutral mutation used by the retained Quick menu.
    Unknown or deactivated concrete choices
    fail closed without changing Settings. Random remains the single
    ``random_always`` authority and never preserves a stale prepared choice.
    """

    if not isinstance(transitions_config, dict):
        return False
    selected = str(selection or "").strip()
    if selected == "Random":
        transitions_config[TRANSITION_RANDOM_MODE_KEY] = True
    else:
        canonical = canonicalize_transition_name(selected, fallback="")
        if (
            not canonical
            or canonical == "Random"
            or not is_transition_activated(transitions_config, canonical)
        ):
            return False
        transitions_config[TRANSITION_MANUAL_TYPE_KEY] = canonical
        transitions_config[TRANSITION_RANDOM_MODE_KEY] = False

    transitions_config.pop("random_choice", None)
    transitions_config.pop("last_random_choice", None)
    normalize_transition_capability_state(transitions_config)
    return True
