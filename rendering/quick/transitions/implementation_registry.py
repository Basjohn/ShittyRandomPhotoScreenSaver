"""Static metadata and lazy resolution for internal Quick transition renderers."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from importlib import import_module

from rendering.transition_registry import (
    get_transition_descriptor_for_runtime_identity,
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
        module_name=(
            "rendering.quick.transitions.implementations.crossfade"
        ),
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="slide",
        module_name="rendering.quick.transitions.implementations.slide",
    ),
    QuickTransitionImplementationDescriptor(
        transition_id="wipe",
        module_name="rendering.quick.transitions.implementations.wipe",
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
        enabled.add(descriptor.stable_id)
    return frozenset(enabled)


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
    if not callable(getattr(implementation, "render", None)) or not callable(
        getattr(implementation, "release_resources", None)
    ):
        raise TypeError(
            f"Quick transition implementation violates render contract: {stable_id}"
        )
    return implementation
