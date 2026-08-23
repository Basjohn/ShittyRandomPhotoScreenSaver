"""Presentation-neutral widget family capability catalog (Phase E foundation).

Phase E introduces an application-level *capability activation* authority that is
distinct from a widget instance's ordinary ``enabled`` checkbox. Settings (E2)
lists one activation row per canonical widget *family*, and the runtime (E1
``WidgetRuntimeManager``) resolves families generically. Both need one cheap
catalog mapping a stable ``family_id`` to its member runtime widget ids.

This module is the single source of truth for family membership. It imports no
QWidget/Quick/provider/renderer code — only ``os`` and the neutral
``core.dev_gates`` authority — so ``core.settings.capability_activation``,
Settings SETUP, and the runtime can consult it without dragging in presentation
or family-implementation modules.

Membership vs availability:

- *Membership* (which widget ids belong to which family) lives here and is
  environment-independent.
- Family-level *availability* (e.g. Imgur is dev-only) is expressed here via the
  neutral ``core.dev_gates`` / env authority.
- Member-level runtime availability (e.g. the ``--devsteam``-only Steam members)
  is a runtime concern resolved from the runtime widget descriptors, so
  ``rendering.widget_descriptors.get_active_member_widget_ids`` — not this module —
  owns it. This keeps one dev-gate authority (``core.dev_gates``) without
  duplicating per-member gate bindings here.

The Spotify visualizer participates in application-level capability activation
through this catalog (family ``visualizers``, which *requires* the ``media``
family). Its runtime/render ownership remains the special Phase-D visualizer
subsystem — it does NOT become an ordinary Phase-F widget presentation family and
does NOT move under ``WidgetRuntimeManager`` merely because it is catalogued here.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os

from core.dev_gates import gate_signature, is_named_gate_enabled


def _family_env_signature() -> tuple[tuple[str, str | None], ...]:
    """Return the neutral environment signature for family availability."""

    env_names = ("SRPSS_ENABLE_DEV",)
    signature: list[tuple[str, str | None]] = [
        (name, os.getenv(name)) for name in env_names
    ]
    signature.extend(
        (f"gate:{name}", "true" if enabled else "false")
        for name, enabled in gate_signature()
    )
    return tuple(signature)


@dataclass(frozen=True)
class WidgetFamilyDescriptor:
    """Canonical application-level capability descriptor for a widget family."""

    family_id: str
    label: str
    member_widget_ids: tuple[str, ...]
    settings_section_id: str
    description: str = ""
    # Other capability families that must be activated for this one to be usable.
    # This is the single neutral dependency authority (e.g. Visualizers requires
    # Media); do not scatter per-family ``if family_id == ...`` checks elsewhere.
    required_family_ids: tuple[str, ...] = ()
    dev_feature_env: str | None = None
    dev_feature_gate: str | None = None

    def is_enabled_in_environment(self) -> bool:
        if self.dev_feature_gate:
            return is_named_gate_enabled(self.dev_feature_gate)
        if not self.dev_feature_env:
            return True
        return os.getenv(self.dev_feature_env, "false").lower() == "true"


WIDGET_FAMILY_DESCRIPTORS: tuple[WidgetFamilyDescriptor, ...] = (
    WidgetFamilyDescriptor(
        family_id="clocks",
        label="Clocks",
        member_widget_ids=("clock", "clock2", "clock3"),
        settings_section_id="clock",
        description="Up to three digital or analog clocks with calendar, timezone and day/date.",
    ),
    WidgetFamilyDescriptor(
        family_id="weather",
        label="Weather",
        member_widget_ids=("weather",),
        settings_section_id="weather",
        description="Current conditions and forecast for a chosen location.",
    ),
    WidgetFamilyDescriptor(
        family_id="media",
        label="Media",
        member_widget_ids=("media", "spotify_volume", "mute_button"),
        settings_section_id="media",
        description="Now-playing card with artwork, playback controls, volume and progress.",
    ),
    WidgetFamilyDescriptor(
        family_id="visualizers",
        label="Visualizers",
        member_widget_ids=("spotify_visualizer",),
        settings_section_id="visualizers",
        description="Audio-reactive visualizer modes. Requires Media.",
        required_family_ids=("media",),
    ),
    WidgetFamilyDescriptor(
        family_id="reddit",
        label="Reddit",
        member_widget_ids=("reddit", "reddit2"),
        settings_section_id="reddit",
        description="Subreddit post feeds, with two independently configured instances.",
    ),
    WidgetFamilyDescriptor(
        family_id="gmail",
        label="Gmail",
        member_widget_ids=("gmail",),
        settings_section_id="gmail",
        description="Unread inbox summary with sender, subject and timestamps.",
    ),
    WidgetFamilyDescriptor(
        family_id="imgur",
        label="Imgur",
        member_widget_ids=("imgur",),
        settings_section_id="imgur",
        description="Imgur image grid (deprecated).",
        dev_feature_env="SRPSS_ENABLE_DEV",
    ),
    WidgetFamilyDescriptor(
        family_id="steam",
        label="Steam",
        member_widget_ids=(
            "steam_progress",
            "achievement_pulse",
            "abandonment_issues",
            "friend_pulse",
        ),
        settings_section_id="steam",
        description="Steam progress, achievement pulse, abandonment and friend cards.",
    ),
)


def get_widget_family_catalog() -> tuple[WidgetFamilyDescriptor, ...]:
    """Return the full static family catalog, ignoring environment gating."""

    return WIDGET_FAMILY_DESCRIPTORS


def get_widget_family_descriptors() -> tuple[WidgetFamilyDescriptor, ...]:
    """Return widget family capabilities available in this environment.

    A family is available when it is environment-enabled at the family level
    (e.g. Imgur requires the dev env). Member-level runtime gating is resolved
    separately by the runtime descriptors.
    """

    return _get_active_widget_family_descriptors(_family_env_signature())


@lru_cache(maxsize=1)
def _get_active_widget_family_descriptors(
    _env_signature: tuple[tuple[str, str | None], ...],
) -> tuple[WidgetFamilyDescriptor, ...]:
    return tuple(
        family
        for family in WIDGET_FAMILY_DESCRIPTORS
        if family.is_enabled_in_environment()
    )


def get_widget_family_descriptor(family_id: str) -> WidgetFamilyDescriptor | None:
    """Return one environment-available widget family descriptor by id."""

    if not isinstance(family_id, str) or not family_id:
        return None
    return _get_widget_family_descriptor_map(_family_env_signature()).get(family_id)


@lru_cache(maxsize=1)
def _get_widget_family_descriptor_map(
    _env_signature: tuple[tuple[str, str | None], ...],
) -> dict[str, WidgetFamilyDescriptor]:
    return {
        family.family_id: family
        for family in get_widget_family_descriptors()
    }


def get_family_id_for_widget(widget_id: str) -> str | None:
    """Return the stable family id that owns a runtime widget id, if any.

    The visualizer and any other widget not assigned to a capability family
    return ``None``.
    """

    if not isinstance(widget_id, str) or not widget_id:
        return None
    return _get_widget_id_to_family_map(_family_env_signature()).get(widget_id)


@lru_cache(maxsize=1)
def _get_widget_id_to_family_map(
    _env_signature: tuple[tuple[str, str | None], ...],
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for family in get_widget_family_descriptors():
        for widget_id in family.member_widget_ids:
            mapping[widget_id] = family.family_id
    return mapping
