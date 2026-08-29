"""Single-owner visualizer display admission for the Quick runtime (H Finding D).

The product admits exactly one visualizer instance. Its requested monitor may be
unavailable or not yet participating, so ownership is resolved from the actual
participating Quick display units - never constructed on every unit. This is the
presentation-neutral Quick equivalent of the legacy
``rendering/spotify_display_participation.py`` selection, expressed over Quick
participants instead of legacy ``_widget_manager`` probes.

Preference order (identical product semantics):

1. the requested display if it is participating;
2. otherwise, if the requested display exists but is not participating yet, hold
   ownership on it (cautious - do not freelance onto arbitrary geometry);
3. otherwise fall back to the first participating unit in stable screen-index
   order.

The caller constructs a ``QuickDisplayVisualizerOwner`` only on the chosen unit;
non-owning units construct no duplicate controller/logical runtime/source owner.
See ``Docs/Historical_Bugs/R-26_Visualizer_Custom_Display_Participation.md``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence


def _screen_index(unit: Any) -> int:
    try:
        return int(getattr(unit, "screen_index"))
    except Exception:
        return -1


def _is_participating(unit: Any) -> bool:
    """A unit participates when it can host the visualizer now.

    Accepts either a boolean ``participating`` attribute or a callable
    ``is_visualizer_participant()``; defaults to False when neither is present so
    a half-constructed unit is never mistaken for a live owner.
    """

    flag = getattr(unit, "participating", None)
    if isinstance(flag, bool):
        return flag
    probe = getattr(unit, "is_visualizer_participant", None)
    if callable(probe):
        try:
            return bool(probe())
        except Exception:
            return False
    return False


@dataclass(frozen=True)
class QuickVisualizerAdmission:
    """Resolved single-owner admission for a requested-monitor visualizer."""

    requested_screen_index: int
    chosen: Any | None
    requested: Any | None
    fallback: Any | None
    requested_is_participating: bool

    @property
    def has_owner(self) -> bool:
        return self.chosen is not None

    def is_owner(self, unit: Any) -> bool:
        """True only for the single admitted owning unit (identity match)."""

        return self.chosen is not None and unit is self.chosen


def resolve_quick_visualizer_admission(
    requested_screen_index: int,
    participants: Sequence[Any],
) -> QuickVisualizerAdmission:
    """Resolve exactly one admitted visualizer display owner (or none)."""

    requested_index = int(requested_screen_index)
    units = list(participants)
    live = sorted(
        (unit for unit in units if _is_participating(unit)),
        key=_screen_index,
    )
    requested = next(
        (unit for unit in units if _screen_index(unit) == requested_index),
        None,
    )

    # 1. Requested display participating -> it owns.
    for unit in live:
        if _screen_index(unit) == requested_index:
            return QuickVisualizerAdmission(
                requested_screen_index=requested_index,
                chosen=unit,
                requested=unit,
                fallback=None,
                requested_is_participating=True,
            )

    fallback = live[0] if live else None

    # 2. Requested display exists but is not participating yet -> hold on it.
    if requested is not None:
        return QuickVisualizerAdmission(
            requested_screen_index=requested_index,
            chosen=requested,
            requested=requested,
            fallback=fallback,
            requested_is_participating=False,
        )

    # 3. Fall back to the first participating unit in stable screen-index order.
    return QuickVisualizerAdmission(
        requested_screen_index=requested_index,
        chosen=fallback,
        requested=None,
        fallback=fallback,
        requested_is_participating=False,
    )


def resolve_quick_visualizer_owner_unit(
    requested_screen_index: int,
    participants: Sequence[Any],
) -> Any | None:
    """Return the single Quick unit that should own the visualizer, or None."""

    return resolve_quick_visualizer_admission(
        requested_screen_index, participants
    ).chosen


__all__ = [
    "QuickVisualizerAdmission",
    "resolve_quick_visualizer_admission",
    "resolve_quick_visualizer_owner_unit",
]
