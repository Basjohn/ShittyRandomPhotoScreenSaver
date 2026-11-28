"""Static metadata and lazy resolution for internal Quick transition renderers."""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from importlib import import_module

from rendering.transition_registry import (
    get_transition_descriptor_for_runtime_identity,
    is_transition_available,
)
from .render_contract import QuickTransitionRenderer


@dataclass(frozen=True, slots=True)
class QuickTransitionImplementationDescriptor:
    transition_id: str
    module_name: str
    factory_name: str = "create_transition_renderer"


_IMPLEMENTATIONS = (
    QuickTransitionImplementationDescriptor(
        transition_id="crossfade",
        module_name="rendering.quick.transitions.implementations.crossfade",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="slide",
        module_name="rendering.quick.transitions.implementations.slide",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="wipe",
        module_name="rendering.quick.transitions.implementations.wipe",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="warp_dissolve",
        module_name="rendering.quick.transitions.implementations.warp",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="block_spins",
        module_name="rendering.quick.transitions.implementations.block_spins",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="blinds",
        module_name="rendering.quick.transitions.implementations.blinds",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="ripple",
        module_name="rendering.quick.transitions.implementations.ripple",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="crumble",
        module_name="rendering.quick.transitions.implementations.crumble",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="particle",
        module_name="rendering.quick.transitions.implementations.particle",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="burn",
        module_name="rendering.quick.transitions.implementations.burn",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="glass_shatter",
        module_name="rendering.quick.transitions.implementations.glass_shatter",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="exploding_tiles",
        module_name="rendering.quick.transitions.implementations.exploding_tiles",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="pixel_accretion",
        module_name="rendering.quick.transitions.implementations.pixel_accretion",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="melt_drip",
        module_name="rendering.quick.transitions.implementations.melt_drip",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="beam",
        module_name="rendering.quick.transitions.implementations.beam",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="cube_turn",
        module_name="rendering.quick.transitions.implementations.cube_turn",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="disintegrate",
        module_name="rendering.quick.transitions.implementations.disintegrate",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="page_curl",
        module_name="rendering.quick.transitions.implementations.page_curl",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="jigsaw",
        module_name="rendering.quick.transitions.implementations.jigsaw",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="volumetric_dissolve",
        module_name="rendering.quick.transitions.implementations.volumetric_dissolve",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="vhs",
        module_name="rendering.quick.transitions.implementations.vhs",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="edge_bloom",
        module_name="rendering.quick.transitions.implementations.edge_bloom",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="liquid_lens",
        module_name="rendering.quick.transitions.implementations.liquid_lens",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="membrane",
        module_name="rendering.quick.transitions.implementations.membrane",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="surface_tension",
        module_name="rendering.quick.transitions.implementations.surface_tension",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="chromatic_shear",
        module_name="rendering.quick.transitions.implementations.chromatic_shear",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="depth_cascade",
        module_name="rendering.quick.transitions.implementations.depth_cascade",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="capillary_bloom",
        module_name="rendering.quick.transitions.implementations.capillary_bloom",
    ),
)
_BY_ID = {descriptor.transition_id: descriptor for descriptor in _IMPLEMENTATIONS}


def iter_quick_transition_implementations(
) -> tuple[QuickTransitionImplementationDescriptor, ...]:
    return _IMPLEMENTATIONS


def canonical_enabled_transition_ids(values: Iterable[object]) -> frozenset[str]:
    enabled: set[str] = set()
    for value in values:
        descriptor = get_transition_descriptor_for_runtime_identity(value)
        if descriptor is None:
            raise ValueError(f"unknown canonical transition: {value!r}")
        if not is_transition_available(descriptor.setting_name):
            continue
        enabled.add(descriptor.stable_id)
    return frozenset(enabled)


#: The modules the renderer classes' modules still import (shared by them, leaves first), so the idle warm-up imports
#: each at its own unit before a renderer module itself (the hitch rows, 22 Nov: one import pulled them all in one go).
#: N5.2h: the classes are value owners, so only the modules their values and scene descriptions read remain here. A
#: module missing here is still imported, with the renderer's module: a larger unit, never a wrong one. Fix 7 (28 Nov):
#: each entry is one a renderer module still imports (measured per module in a fresh process); the photo environment
#: and its box kernel are the native layer's run modules (``native_background._RUN_MODULES``), not a renderer's.
SHARED_RENDERER_MODULES = (
    "rendering.quick.gl_query",
    "rendering.quick.scene3d.stream",
    "rendering.quick.scene3d.compute",
    "rendering.quick.scene3d.passes",
    "rendering.quick.render.gl_program_cache",
    "rendering.quick.render.gl_resources",
    "rendering.quick.scene3d.uniforms",
    "rendering.quick.scene3d.resources",
    "rendering.quick.scene3d.post",
    "rendering.quick.transitions.directions",
)


def next_quick_transition_warm_unit(transition_id: object) -> Callable[[], object] | None:
    """The next GUI-thread warm-up unit of one transition's renderer module (None: none left; an unknown or
    unavailable transition has none): one shared module (``SHARED_RENDERER_MODULES``) not yet imported, else the
    module's own import, else the first of its ``WARM_PIECES`` (its shader texts, each built on first use and cached)
    not yet built. Constructs nothing and touches no GL; a run builds whatever is left itself."""
    canonical = get_transition_descriptor_for_runtime_identity(transition_id)
    if canonical is None or not is_transition_available(canonical.setting_name):
        return None
    descriptor = _BY_ID.get(canonical.stable_id)
    if descriptor is None:
        return None
    module = sys.modules.get(descriptor.module_name)
    if module is None:
        name = next((name for name in SHARED_RENDERER_MODULES if name not in sys.modules), descriptor.module_name)
        return lambda: import_module(name)
    for piece in getattr(module, "WARM_PIECES", ()):
        if piece.cache_info().currsize == 0:
            return piece
    return None


def preload_quick_transition_implementation(transition_id: object) -> None:
    """Import one transition's renderer module ahead of its first run (GUI thread), so the
    render thread's resolve is instant. Constructs nothing and touches no GL. The idle warm-up imports it in bounded
    units instead (``next_quick_transition_warm_unit``)."""
    canonical = get_transition_descriptor_for_runtime_identity(transition_id)
    if canonical is None:
        raise ValueError(f"unknown canonical transition: {transition_id!r}")
    descriptor = _BY_ID.get(canonical.stable_id)
    if descriptor is not None and is_transition_available(canonical.setting_name):
        import_module(descriptor.module_name)


def resolve_quick_transition_renderer(
    transition_id: object,
    *,
    enabled_transition_ids: frozenset[str],
) -> QuickTransitionRenderer | None:
    """Resolve one enabled implementation without importing any other renderer."""

    canonical = get_transition_descriptor_for_runtime_identity(transition_id)
    if canonical is None:
        raise ValueError(f"unknown canonical transition: {transition_id!r}")
    stable_id = canonical.stable_id
    if not is_transition_available(canonical.setting_name):
        return None
    if stable_id not in enabled_transition_ids:
        return None
    descriptor = _BY_ID.get(stable_id)
    if descriptor is None:
        return None

    module = import_module(descriptor.module_name)
    factory = getattr(module, descriptor.factory_name, None)
    if not callable(factory):
        raise RuntimeError(
            f"Quick transition factory is unavailable: {descriptor.module_name}:"
            f"{descriptor.factory_name}"
        )
    implementation = factory()
    if getattr(implementation, "transition_id", None) != stable_id:
        raise RuntimeError(
            f"Quick transition implementation identity mismatch: {stable_id}"
        )
    if not callable(getattr(implementation, "block_values", None)) and not callable(
        getattr(implementation, "scene_values", None)
    ):
        raise TypeError(
            f"Quick transition implementation violates value contract: {stable_id}"
        )
    return implementation
