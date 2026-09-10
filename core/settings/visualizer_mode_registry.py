"""Shared visualizer mode contract metadata.

This module centralizes the stable mode identifiers and the UI/runtime wiring
metadata that had been duplicated across presets, WidgetsTab plumbing, and
tests. It is intentionally small: the goal is one source of truth for mode
identity and preset ownership without rebuilding the whole visualizer stack
around a giant generic schema.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class VisualizerShellPolicy(str, Enum):
    """Retained chrome owned by the visualizer presentation root."""

    CARD = "card"
    FRAMELESS = "frameless"


class VisualizerClipPolicy(str, Enum):
    """Content clip resolved before a frame reaches the render thread."""

    CARD_INTERIOR = "card_interior"
    VIEWPORT_RECT = "viewport_rect"


@dataclass(frozen=True, slots=True)
class VisualizerModePresentationPolicy:
    shell_policy: VisualizerShellPolicy
    clip_policy: VisualizerClipPolicy
    viewport_resize_capable: bool


_REFLOWING_CARDED_POLICY = VisualizerModePresentationPolicy(
    shell_policy=VisualizerShellPolicy.CARD,
    clip_policy=VisualizerClipPolicy.CARD_INTERIOR,
    # All five current modes recompute their domain from committed geometry
    # (Bubble via its baseline-relative logical domain), so every mode is
    # viewport-resize-capable. The deterministic G4 implementation is complete;
    # installed eyes-on acceptance is deferred until Quick is production
    # authoritative after H.
    viewport_resize_capable=True,
)

@dataclass(frozen=True)
class VisualizerModeDescriptor:
    mode_id: str
    display_name: str
    preset_slider_attr: str
    setting_prefixes: tuple[str, ...]
    presentation_policy: VisualizerModePresentationPolicy
    # Lazy wiring identity: import-path/name strings only. Holding these as
    # strings keeps this metadata module free of Qt/renderer/runtime imports;
    # the actual module is imported on demand by the owning caller
    # (quick_display_visualizer_owner for the frame runtime, the Quick renderer
    # implementation_registry for the renderer). This is the single source of
    # per-mode runtime/renderer wiring; the previous duplicate five-way tables
    # now derive from here.
    frame_runtime_module: str
    frame_runtime_class: str
    renderer_module: str
    renderer_factory: str = "create_visualizer_renderer"
    # Lazy Settings-body wiring (V5): import-path/name strings only, same
    # discipline as the frame-runtime/renderer identity above. The mode's Qt
    # Settings builder is imported on demand only when its body is actually
    # constructed (enabled + selected), so importing this registry — or building
    # a disabled/unselected mode's settings — never imports its builder.
    settings_builder_module: str = ""
    settings_builder_factory: str = ""
    # Capture is lazy for the same reason as render/runtime wiring: importing a
    # disabled experiment must not instantiate or import its solver.
    capture_module: str = ""
    capture_factory: str = ""
    technical_controls: bool = True
    # Whether this mode participates in the shared per-mode Rainbow settings
    # contract. Experimental modes may deliberately omit that product surface;
    # callers must consult the descriptor rather than assume every mode owns
    # rainbow_enabled/rainbow_speed persisted keys.
    rainbow_controls: bool = True
    # Whether this mode owns the canonical per-mode shared bar appearance keys
    # (bar_fill_color / bar_border_color / bar_border_opacity). This is capability
    # metadata only: it never supplies values. Canonical defaults remain the sole
    # authority for persisted product values, and tests require descriptor/key
    # ownership to agree exactly.
    shared_bar_appearance: bool = True
    # Modes that do not own shared bar-appearance settings may explicitly
    # consume another canonical mode's persisted profile for internal runtime
    # mirrors. This is routing metadata only; it never supplies values.
    shared_bar_profile_mode: str = ""
    # Modes without their own technical controls may explicitly borrow one
    # canonical technical profile. Empty means the mode owns its own profile.
    technical_profile_mode: str = ""
    # Optional renderer-only overflow wiring. Empty means the mode can never
    # bypass the canonical local visualizer clip. This is capability/routing
    # metadata only; the boolean value itself remains a canonical persisted
    # product setting carried in the mode's immutable parameter snapshot.
    renderer_overflow_setting: str = ""

    @property
    def preset_key(self) -> str:
        return f"preset_{self.mode_id}"


_ALL_DESCRIPTORS: tuple[VisualizerModeDescriptor, ...] = (
    VisualizerModeDescriptor(
        "spectrum",
        "Spectrum",
        "_spectrum_preset_slider",
        ("spectrum_",),
        _REFLOWING_CARDED_POLICY,
        frame_runtime_module="widgets.spotify_visualizer.spectrum_frame_runtime",
        frame_runtime_class="SpectrumFrameRuntime",
        renderer_module="rendering.quick.visualizer.implementations.spectrum",
        settings_builder_module="ui.tabs.media.spectrum_builder",
        settings_builder_factory="build_spectrum_ui",
    ),
    VisualizerModeDescriptor(
        "oscilloscope",
        "Oscilloscope",
        "_osc_preset_slider",
        ("osc_", "oscilloscope_"),
        _REFLOWING_CARDED_POLICY,
        frame_runtime_module="widgets.spotify_visualizer.oscilloscope_frame_runtime",
        frame_runtime_class="OscilloscopeFrameRuntime",
        renderer_module="rendering.quick.visualizer.implementations.oscilloscope",
        settings_builder_module="ui.tabs.media.oscilloscope_builder",
        settings_builder_factory="build_oscilloscope_ui",
    ),
    VisualizerModeDescriptor(
        "sine_wave",
        "Sine Waves",
        "_sine_preset_slider",
        ("sine_", "sine_wave_", "sinewave_"),
        _REFLOWING_CARDED_POLICY,
        frame_runtime_module="widgets.spotify_visualizer.sine_frame_runtime",
        frame_runtime_class="SineFrameRuntime",
        renderer_module="rendering.quick.visualizer.implementations.sine_wave",
        settings_builder_module="ui.tabs.media.sine_wave_builder",
        settings_builder_factory="build_sine_wave_ui",
    ),
    VisualizerModeDescriptor(
        "bubble",
        "Bubble",
        "_bubble_preset_slider",
        ("bubble_",),
        _REFLOWING_CARDED_POLICY,
        frame_runtime_module="widgets.spotify_visualizer.bubble_frame_runtime",
        frame_runtime_class="BubbleFrameRuntime",
        renderer_module="rendering.quick.visualizer.implementations.bubble",
        settings_builder_module="ui.tabs.media.bubble_builder",
        settings_builder_factory="build_bubble_ui",
    ),
    VisualizerModeDescriptor(
        "devcurve",
        "Spline Curve",
        "_devcurve_preset_slider",
        ("devcurve_",),
        _REFLOWING_CARDED_POLICY,
        frame_runtime_module="widgets.spotify_visualizer.devcurve_frame_runtime",
        frame_runtime_class="DevCurveFrameRuntime",
        renderer_module="rendering.quick.visualizer.implementations.devcurve",
        settings_builder_module="ui.tabs.media.devcurve_builder",
        settings_builder_factory="build_devcurve_ui",
    ),
    VisualizerModeDescriptor(
        "sphere",
        "Voxel Sphere (Experimental)",
        "_sphere_preset_slider",
        ("sphere_",),
        VisualizerModePresentationPolicy(
            shell_policy=VisualizerShellPolicy.FRAMELESS,
            clip_policy=VisualizerClipPolicy.VIEWPORT_RECT,
            viewport_resize_capable=True,
        ),
        frame_runtime_module="widgets.spotify_visualizer.sphere_frame_runtime",
        frame_runtime_class="SphereFrameRuntime",
        renderer_module="rendering.quick.visualizer.implementations.sphere_voxel",
        settings_builder_module="ui.tabs.media.sphere_builder",
        settings_builder_factory="build_sphere_ui",
        capture_module="widgets.spotify_visualizer.sphere_capture",
        capture_factory="capture_sphere",
        technical_controls=False,
        rainbow_controls=False,
        shared_bar_appearance=False,
        shared_bar_profile_mode="spectrum",
        technical_profile_mode="spectrum",
        renderer_overflow_setting="sphere_allow_overflow",
    ),
)

_GATED_MODES: dict[str, callable] = {}

def _active_descriptors() -> tuple[VisualizerModeDescriptor, ...]:
    return tuple(d for d in _ALL_DESCRIPTORS if d.mode_id not in _GATED_MODES or _GATED_MODES[d.mode_id]())


VISUALIZER_MODE_IDS: tuple[str, ...] = tuple(d.mode_id for d in _ALL_DESCRIPTORS)


def iter_visualizer_mode_descriptors() -> tuple[VisualizerModeDescriptor, ...]:
    """Return only the currently active (non-gated) mode descriptors."""
    return _active_descriptors()


def iter_all_visualizer_mode_descriptors() -> tuple[VisualizerModeDescriptor, ...]:
    """Return every registered canonical mode descriptor, gated or not.

    Schema/default/renderer-registration authority uses this (every canonical
    mode has a renderer/runtime regardless of enable-state); runtime *selection*
    and cycling use :func:`iter_visualizer_mode_descriptors` instead.
    """
    return _ALL_DESCRIPTORS


def get_visualizer_mode_descriptor(mode_id: str) -> VisualizerModeDescriptor:
    """Look up by mode_id.  Searches ALL modes (including gated) so
    settings plumbing never crashes on a stored gated-off mode."""
    for descriptor in _ALL_DESCRIPTORS:
        if descriptor.mode_id == mode_id:
            return descriptor
    raise KeyError(f"Unknown visualizer mode: {mode_id}")


def load_mode_settings_builder(mode_id: str):
    """Lazily import and return a mode's Settings-body builder callable.

    Mirrors the frame-runtime/renderer lazy-wiring pattern: the descriptor holds
    only import-path strings, so importing this registry never imports any mode's
    Qt Settings builder. The builder module is imported on demand — only when a
    mode's Settings body is actually constructed (enabled + selected) — which is
    what keeps disabled/unselected mode bodies dormant.
    """
    from importlib import import_module

    descriptor = get_visualizer_mode_descriptor(mode_id)
    if not descriptor.settings_builder_module or not descriptor.settings_builder_factory:
        raise KeyError(f"Mode {mode_id!r} has no Settings builder wiring")
    module = import_module(descriptor.settings_builder_module)
    return getattr(module, descriptor.settings_builder_factory)



def get_technical_profile_mode(mode_id: str) -> str:
    """Return the canonical technical/DSP profile backing ``mode_id``.

    Experimental/presentation modes may intentionally expose no technical
    controls while still requiring a deterministic BeatEngine profile.  The
    descriptor owns that relationship so runtime/settings callers never add a
    mode-specific fallback branch.
    """

    descriptor = get_visualizer_mode_descriptor(mode_id)
    profile = str(descriptor.technical_profile_mode or descriptor.mode_id).strip().lower()
    if not profile:
        raise ValueError(f"visualizer mode {mode_id!r} has no technical profile")
    return profile




_MODE_SETTING_FAMILY_SUFFIXES: dict[str, tuple[str, ...]] = {
    "rainbow": ("rainbow_enabled", "rainbow_speed"),
    "shared_bar": ("bar_fill_color", "bar_border_color", "bar_border_opacity"),
}


def mode_owns_setting_family(mode_id: str, family: str) -> bool:
    """Return whether ``mode_id`` owns persisted keys for ``family``.

    This is capability metadata only. Persisted values remain owned by the
    canonical defaults/schema/SettingsManager authority.
    """

    descriptor = get_visualizer_mode_descriptor(mode_id)
    if family == "rainbow":
        return bool(descriptor.rainbow_controls)
    if family == "shared_bar":
        return bool(descriptor.shared_bar_appearance)
    raise KeyError(f"Unknown visualizer setting family: {family!r}")


def get_owned_mode_setting_keys(mode_id: str, family: str) -> dict[str, str]:
    """Return canonical persisted keys owned directly by ``mode_id``.

    Non-owning modes return an empty mapping. Generic callers should use this
    rather than manufacturing ``{mode}_{suffix}`` keys independently.
    """

    suffixes = _MODE_SETTING_FAMILY_SUFFIXES.get(family)
    if suffixes is None:
        raise KeyError(f"Unknown visualizer setting family: {family!r}")
    if not mode_owns_setting_family(mode_id, family):
        return {}
    normalized = get_visualizer_mode_descriptor(mode_id).mode_id
    return {suffix: f"{normalized}_{suffix}" for suffix in suffixes}


def get_resolved_mode_setting_profile(mode_id: str, family: str) -> str | None:
    """Resolve the canonical persisted profile consumed by ``mode_id``.

    Owning modes resolve to themselves. Shared-bar non-owners may explicitly
    consume a descriptor-declared profile for non-persisted runtime mirrors.
    Rainbow has no inherited profile: a mode that does not own Rainbow simply
    does not participate in that product surface.
    """

    descriptor = get_visualizer_mode_descriptor(mode_id)
    if mode_owns_setting_family(mode_id, family):
        return descriptor.mode_id
    if family == "rainbow":
        return None
    if family != "shared_bar":
        raise KeyError(f"Unknown visualizer setting family: {family!r}")
    profile = str(descriptor.shared_bar_profile_mode).strip().lower()
    if not profile:
        raise ValueError(
            f"visualizer mode {mode_id!r} owns no shared-bar settings and declares no shared-bar profile"
        )
    if not mode_owns_setting_family(profile, "shared_bar"):
        raise ValueError(
            f"visualizer shared-bar profile {profile!r} for mode {mode_id!r} does not own canonical shared-bar settings"
        )
    return profile


def get_resolved_mode_setting_keys(mode_id: str, family: str) -> dict[str, str]:
    """Return canonical persisted keys backing ``mode_id`` for ``family``.

    This function resolves only key ownership/routing; callers must still read
    values from canonical defaults/SettingsManager.
    """

    profile = get_resolved_mode_setting_profile(mode_id, family)
    if profile is None:
        return {}
    keys = get_owned_mode_setting_keys(profile, family)
    if not keys:
        raise ValueError(
            f"visualizer setting profile {profile!r} for {family!r} exposes no canonical keys"
        )
    return keys

def mode_has_rainbow_controls(mode_id: str) -> bool:
    """Return whether ``mode_id`` owns canonical per-mode Rainbow settings."""

    return mode_owns_setting_family(mode_id, "rainbow")


def mode_has_shared_bar_appearance(mode_id: str) -> bool:
    """Return whether ``mode_id`` owns canonical shared bar-appearance keys.

    This is a capability query, not a defaults authority. Callers that need a
    value must still resolve it from canonical Settings/defaults.
    """

    return mode_owns_setting_family(mode_id, "shared_bar")

def get_default_visualizer_mode_id() -> str:
    """Return the canonical default active mode id.

    The persisted product baseline is owned by ``default_settings`` through the
    lightweight default contract. A missing/invalid schema value is an
    authority error, not an invitation to invent a second mode default here.
    """
    from core.settings.default_contract import require_canonical_default

    configured = str(
        require_canonical_default("widgets.spotify_visualizer.mode")
    ).strip().lower()
    if configured not in VISUALIZER_MODE_IDS:
        raise ValueError(f"invalid canonical visualizer mode default: {configured!r}")
    if not is_mode_active(configured):
        raise ValueError(
            f"canonical visualizer mode default is not active: {configured!r}"
        )
    return configured


def get_preset_slider_attr(mode_id: str) -> str:
    return get_visualizer_mode_descriptor(mode_id).preset_slider_attr


def get_preset_key(mode_id: str) -> str:
    return get_visualizer_mode_descriptor(mode_id).preset_key


def get_setting_prefixes(mode_id: str) -> tuple[str, ...]:
    return get_visualizer_mode_descriptor(mode_id).setting_prefixes


def get_visualizer_presentation_policy(
    mode_id: str,
) -> VisualizerModePresentationPolicy:
    return get_visualizer_mode_descriptor(mode_id).presentation_policy


def is_mode_active(mode_id: str) -> bool:
    """True if *mode_id* is not behind a closed dev gate."""
    gate = _GATED_MODES.get(mode_id)
    return gate is None or gate()


def coerce_visualizer_mode_id(mode_id: str | None) -> str:
    """Return canonical mode id when known, else fallback to default active mode.

    Unknown values fall back to the first active mode.
    """
    raw = str(mode_id or "").strip().lower()
    if raw in VISUALIZER_MODE_IDS:
        return raw
    return get_default_visualizer_mode_id()


def resolve_effective_enabled_modes(
    requested: object,
) -> tuple[str, ...]:
    """Normalize a persisted enabled-mode selection into canonical order.

    Keeps only canonical mode ids, de-duplicates, and preserves canonical
    ``VISUALIZER_MODE_IDS`` order regardless of stored order. Enforces the V2
    invariant that a live Visualizer family has at least one enabled mode: an
    absent, empty, or fully-invalid selection resolves to the canonical
    ``widgets.spotify_visualizer.enabled_modes`` product setting. Capability
    descriptors deliberately do not own enable-state defaults.

    This is intentionally about the *registered* canonical set, not dev gates:
    enable-state is persisted product configuration, separate from ``is_mode_active``.
    """

    from core.settings.default_contract import require_canonical_default

    configured_defaults = require_canonical_default(
        "widgets.spotify_visualizer.enabled_modes"
    )
    if not isinstance(configured_defaults, (list, tuple, set, frozenset)):
        raise TypeError(
            "canonical visualizer enabled_modes must be a sequence of mode ids"
        )
    configured_set = {
        str(item or "").strip().lower() for item in configured_defaults
    }
    unknown_defaults = configured_set.difference(VISUALIZER_MODE_IDS)
    if unknown_defaults:
        raise ValueError(
            "canonical visualizer enabled_modes contains unknown mode ids: "
            + ", ".join(sorted(unknown_defaults))
        )
    default_modes = tuple(
        mode_id for mode_id in VISUALIZER_MODE_IDS if mode_id in configured_set
    )
    if not default_modes:
        raise ValueError("canonical visualizer enabled_modes must not be empty")
    if requested is None:
        return default_modes

    if isinstance(requested, str):
        raw_items: tuple[object, ...] = (requested,)
    elif isinstance(requested, (list, tuple, set, frozenset)):
        raw_items = tuple(requested)
    else:
        return default_modes

    selected = {
        str(item or "").strip().lower()
        for item in raw_items
    }
    ordered = tuple(
        mode_id for mode_id in VISUALIZER_MODE_IDS if mode_id in selected
    )
    if not ordered:
        # Never let a stale/garbage selection disable the whole family.
        return default_modes
    return ordered


def resolve_admissible_enabled_modes(enabled_modes: object) -> tuple[str, ...]:
    """Return effective enabled modes intersected with dev-active descriptors.

    UI pill/body admission must never expose or construct a currently dev-gated
    inactive mode, even if persisted ``enabled_modes`` still lists it. Persisted
    canonical enable-state is preserved untouched — this is a read-only
    admission view, not a mutation. With all gates open (today) it equals
    :func:`resolve_effective_enabled_modes`.
    """
    return tuple(
        mode_id
        for mode_id in resolve_effective_enabled_modes(enabled_modes)
        if is_mode_active(mode_id)
    )


def can_disable_visualizer_mode(enabled_modes: object, mode_id: str) -> bool:
    """Whether *mode_id* may be toggled off while the family stays ON.

    The family invariant is at least one enabled mode. Disabling the final
    enabled mode is rejected here so a UI toggle can be blocked *before* it
    produces an empty set — which :func:`resolve_effective_enabled_modes` would
    otherwise widen back to all modes. Turning the whole family OFF is a
    separate control, not this path.
    """
    effective = resolve_effective_enabled_modes(enabled_modes)
    target = str(mode_id or "").strip().lower()
    if target not in effective:
        return False
    return len(effective) > 1


def apply_visualizer_mode_disable(enabled_modes: object, mode_id: str) -> tuple[str, ...]:
    """Return the enabled set with *mode_id* removed, or unchanged if it is last.

    Never returns an empty set while the family is ON: if *mode_id* is the sole
    enabled mode the current effective set is returned unchanged (the caller
    should also disable the toggle via :func:`can_disable_visualizer_mode`). The
    result is always the canonical-ordered effective set, never widened to all.
    """
    effective = resolve_effective_enabled_modes(enabled_modes)
    if not can_disable_visualizer_mode(enabled_modes, mode_id):
        return effective
    target = str(mode_id or "").strip().lower()
    return tuple(mode for mode in effective if mode != target)


def resolve_effective_mode(
    requested_mode: object,
    enabled_modes: object,
) -> tuple[str, bool]:
    """Resolve a requested mode against the effective enabled-mode set.

    Returns ``(mode_id, substituted)``:

    - requested is enabled            -> (requested, False)
    - requested is canonical, disabled -> deterministic enabled substitute
      (the next enabled mode in canonical order, wrapping once), True
    - requested is unknown/retired     -> the configured default when enabled,
      else the first enabled canonical mode, True

    A stale/disabled selection is never silently re-enabled: the substitute is
    always drawn from ``enabled_modes``. Callers own persisting/logging the
    substitution; this function is pure.
    """

    enabled = resolve_effective_enabled_modes(enabled_modes)
    requested = str(requested_mode or "").strip().lower()

    if requested in enabled:
        return requested, False

    if requested in VISUALIZER_MODE_IDS:
        # Canonical but disabled: walk canonical order from just after the
        # requested mode, wrapping once, and pick the first enabled mode.
        start = VISUALIZER_MODE_IDS.index(requested)
        count = len(VISUALIZER_MODE_IDS)
        for step in range(1, count + 1):
            candidate = VISUALIZER_MODE_IDS[(start + step) % count]
            if candidate in enabled:
                return candidate, True

    # Unknown/retired: prefer the configured default if it is enabled.
    default_mode = get_default_visualizer_mode_id()
    if default_mode in enabled:
        return default_mode, True
    return enabled[0], True


def resolve_effective_visualizer_section(
    section: object,
) -> tuple[dict, bool, str, str]:
    """Return a section whose ``mode`` is the effective enabled mode.

    Resolves a disabled/stale persisted mode to an enabled substitute **before**
    the activation/model payload is resolved from the section, so mode-A
    activation/preset state is never field-patched onto mode B. Pure: the input
    section is not mutated; on substitution a shallow copy with the effective
    mode is returned.

    Returns ``(effective_section, substituted, requested_mode, effective_mode)``.
    A non-mapping input yields an empty section and the default mode.
    """

    if not hasattr(section, "get"):
        default_mode = get_default_visualizer_mode_id()
        return {}, False, "", default_mode

    requested_mode = str(section.get("mode") or "").strip().lower()
    effective_mode, substituted = resolve_effective_mode(
        requested_mode, section.get("enabled_modes")
    )
    if not substituted:
        return dict(section), False, requested_mode, effective_mode
    effective_section = {**section, "mode": effective_mode}
    return effective_section, True, requested_mode, effective_mode
