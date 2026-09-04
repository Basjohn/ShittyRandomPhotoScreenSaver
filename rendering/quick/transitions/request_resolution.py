"""Resolve one Settings-authored transition spec per accepted image batch."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import random
from typing import Any, Protocol

from core.settings.capability_activation import (
    get_effective_random_pool,
    is_transition_activated,
    resolve_manual_transition_selection,
)
from core.settings.defaults import get_default_settings
from core.settings.settings_manager import SettingsManager
from rendering.transition_registry import (
    canonicalize_transition_name,
    get_transition_descriptor,
    is_transition_available_for_hw,
)

from ..image_state import PresentationImage
from .parameter_resolution import resolve_parameterized_phase_c_inputs
from .state import (
    TransitionParameters,
    TransitionRequest,
    freeze_transition_parameters,
)


class _RandomSource(Protocol):
    def choice(self, values): ...
    def randint(self, a: int, b: int) -> int: ...
    def random(self) -> float: ...


@dataclass(frozen=True, slots=True)
class ResolvedQuickTransitionSpec:
    """Display-independent transition intent shared by one image batch."""

    transition_id: str
    requested_name: str
    selected_from_random: bool
    duration_ms: int
    direction: object
    parameters: TransitionParameters

    def build_request(
        self,
        *,
        runtime_generation: int,
        source_image: PresentationImage,
        destination_image: PresentationImage,
    ) -> TransitionRequest:
        return TransitionRequest(
            runtime_generation=int(runtime_generation),
            transition_id=self.transition_id,
            requested_name=self.requested_name,
            selected_from_random=self.selected_from_random,
            duration_ms=self.duration_ms,
            direction=self.direction,
            parameters=self.parameters,
            source_image=source_image,
            destination_image=destination_image,
        )


_DIRECTION_MAP = {
    "Left to Right": "left",
    "Right to Left": "right",
    "Top to Bottom": "down",
    "Bottom to Top": "up",
    "Diagonal TL-BR": "diag_tl_br",
    "Diagonal TR-BL": "diag_tr_bl",
    "Diagonal TL to BR": "diag_tl_br",
    "Diagonal TR to BL": "diag_tr_bl",
}
_WIPE_DIRECTION_MAP = {
    "Left to Right": "left_to_right",
    "Right to Left": "right_to_left",
    "Top to Bottom": "top_to_bottom",
    "Bottom to Top": "bottom_to_top",
    "Diagonal TL-BR": "diag_tl_br",
    "Diagonal TR-BL": "diag_tr_bl",
}
_SLIDE_MOTION_STYLES = frozenset({"Linear", "Elastic", "Wobble", "Flex"})


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _section(
    transitions: Mapping[str, Any],
    defaults: Mapping[str, Any],
    name: str,
) -> dict[str, Any]:
    merged = dict(_mapping(defaults.get(name)))
    merged.update(_mapping(transitions.get(name)))
    return merged


def _resolve_direction(
    raw: object,
    *,
    choices: tuple[str, ...],
    mapping: Mapping[str, str],
    rng: _RandomSource,
) -> str:
    text = str(raw or "Random")
    if text == "Random":
        return str(rng.choice(choices))
    resolved = mapping.get(text)
    if resolved is None:
        raise ValueError(f"unknown transition direction: {raw!r}")
    return resolved


def resolve_quick_transition_spec(
    settings_manager: object | None,
    *,
    random_source: _RandomSource | None = None,
) -> ResolvedQuickTransitionSpec | None:
    """Resolve the canonical current transition once for all selected displays.

    A Random choice must already have been admitted by the engine for this image
    batch. Stale, deactivated, out-of-pool or hardware-invalid choices fail
    closed; this resolver never silently broadens the saved pool.
    """

    rng = random_source if random_source is not None else random
    defaults = _mapping(get_default_settings().get("transitions", {}))
    raw = (
        settings_manager.get("transitions", {})
        if settings_manager is not None
        else {}
    )
    transitions = _mapping(raw)
    requested_name = canonicalize_transition_name(
        transitions.get("type") or defaults.get("type") or "Crossfade",
        fallback="Crossfade",
    )
    random_enabled = SettingsManager.to_bool(
        transitions.get("random_always", defaults.get("random_always", False)),
        False,
    )
    if random_enabled:
        choice = transitions.get("random_choice")
        selected_name = canonicalize_transition_name(choice, fallback="")
        if not selected_name:
            return None
        hw_enabled = SettingsManager.to_bool(
            settings_manager.get("display.hw_accel", False)
            if settings_manager is not None
            else False,
            False,
        )
        if (
            selected_name not in get_effective_random_pool(transitions)
            or not is_transition_activated(transitions, selected_name)
            or not is_transition_available_for_hw(selected_name, hw_enabled)
        ):
            return None
    else:
        selected_name = resolve_manual_transition_selection(
            transitions,
            requested_name,
        )

    descriptor = get_transition_descriptor(selected_name)
    if descriptor is None:
        raise ValueError(f"unknown resolved transition: {selected_name!r}")
    duration_raw = _mapping(transitions.get("durations")).get(
        descriptor.setting_name,
        _mapping(defaults.get("durations")).get(
            descriptor.setting_name,
            transitions.get("duration_ms", defaults.get("duration_ms", 1300)),
        ),
    )
    duration_ms = int(duration_raw)
    if duration_ms <= 0:
        raise ValueError("resolved transition duration must be positive")

    transition_id = descriptor.stable_id
    direction: object = None
    parameters: Mapping[str, object] = {}
    if transition_id in {
        "blinds",
        "diffuse",
        "ripple",
        "crumble",
        "particle",
        "burn",
    }:
        resolved = resolve_parameterized_phase_c_inputs(
            transition_id,
            transitions,
            random_source=rng,
        )
        direction = resolved.direction
        parameters = resolved.parameter_dict()
    elif transition_id == "slide":
        cfg = _section(transitions, defaults, "slide")
        direction = _resolve_direction(
            cfg.get("direction"),
            choices=("left", "right", "down", "up"),
            mapping=_DIRECTION_MAP,
            rng=rng,
        )
        motion_style = cfg.get("motion_style", "Linear")
        if not isinstance(motion_style, str) or motion_style not in _SLIDE_MOTION_STYLES:
            raise ValueError(f"unknown Slide motion style: {motion_style!r}")
        parameters = {"motion_style": motion_style}
    elif transition_id == "wipe":
        cfg = _section(transitions, defaults, "wipe")
        direction = _resolve_direction(
            cfg.get("direction"),
            choices=tuple(_WIPE_DIRECTION_MAP.values()),
            mapping=_WIPE_DIRECTION_MAP,
            rng=rng,
        )
    elif transition_id in {"block_flip", "block_spins"}:
        section_name = "block_flip" if transition_id == "block_flip" else "blockspin"
        cfg = _section(transitions, defaults, section_name)
        direction = _resolve_direction(
            cfg.get("direction"),
            choices=(
                "left",
                "right",
                "down",
                "up",
                "diag_tl_br",
                "diag_tr_bl",
            ),
            mapping=_DIRECTION_MAP,
            rng=rng,
        )
        if transition_id == "block_flip":
            parameters = {
                "cols": int(cfg.get("cols", 24)),
                "rows": int(cfg.get("rows", 24)),
            }

    return ResolvedQuickTransitionSpec(
        transition_id=transition_id,
        requested_name=requested_name,
        selected_from_random=random_enabled,
        duration_ms=duration_ms,
        direction=direction,
        parameters=freeze_transition_parameters(parameters),
    )


__all__ = ["ResolvedQuickTransitionSpec", "resolve_quick_transition_spec"]
