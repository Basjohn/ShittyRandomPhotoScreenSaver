"""One canonical answer to what each visualizer mode can do while idle.

Three genuinely different capabilities were previously encoded as ad-hoc sets in
three owners that disagreed with each other:

- `startup_staging.mode_allows_idle_reveal()` decided whether the card may show;
- `tick_pipeline` reused one set for both idle animation and source authority;
- `media_bridge.seed_playback_state_from_anchor()` had a third hard-coded set
  listing only bubble/sine_wave/devcurve, so a provisional paused media seed
  could block an Oscilloscope or Spectrum startup that the other two owners
  considered perfectly legal.

Keeping them apart matters, because they are not the same question:

    mode          idle reveal   idle self-animation   presentation-owned    fresh source
                                                      idle scene            for playback
    bubble            yes              yes                  no                  no
    sine_wave         yes              yes                  no                  no
    oscilloscope      yes              yes                  no                  no
    devcurve          yes              yes                  no                  no
    spectrum          yes              no                   yes                 yes

Spectrum is the case that forced the split. Its card may exist while paused, but
its idle scene comes from presentation rather than from engine ticks, and every
bar it shows during playback is purely source-derived - so it must keep proving
its first reactive frame came from the current activation.
"""

from __future__ import annotations

from typing import Any


# Every authored mode may present while playback is idle.
_IDLE_REVEAL = frozenset(
    {"bubble", "spectrum", "sine_wave", "oscilloscope", "devcurve"}
)

# Modes whose paused motion is generated from engine ticks, so a paused tick may
# stop waiting for a fresh engine frame.
_IDLE_SELF_ANIMATING = frozenset(
    {"bubble", "sine_wave", "oscilloscope", "devcurve"}
)

# Modes whose idle scene is produced entirely by presentation and needs no
# source frame at all.
_PRESENTATION_OWNED_IDLE = frozenset({"spectrum"})


def mode_key(mode: Any) -> str:
    """Normalize a mode name or mode-carrying widget attribute to its key."""

    return str(mode or "").strip().lower()


def allows_idle_reveal(mode: Any) -> bool:
    """True when the card/visualizer may be revealed while playback is idle."""

    return mode_key(mode) in _IDLE_REVEAL


def is_idle_self_animating(mode: Any) -> bool:
    """True when paused motion comes from engine ticks rather than presentation."""

    return mode_key(mode) in _IDLE_SELF_ANIMATING


def has_presentation_owned_idle_scene(mode: Any) -> bool:
    """True when the idle scene is built by presentation with no source frame.

    Such a mode must still be allowed to publish while paused even though it is
    holding a fresh-source wait open for later reactive authority.
    """

    return mode_key(mode) in _PRESENTATION_OWNED_IDLE


def requires_authoritative_first_source(mode: Any) -> bool:
    """True when first visible reactive output must come from tracked source.

    Deliberately keyed on self-animation rather than on idle reveal: a mode with
    no idle motion of its own has nothing legitimate to show from stale or
    absent source data during playback.
    """

    return not is_idle_self_animating(mode)


def widget_mode_key(widget: Any) -> str:
    """Convenience for the many call sites holding a widget rather than a name."""

    return mode_key(getattr(widget, "_vis_mode_str", ""))
