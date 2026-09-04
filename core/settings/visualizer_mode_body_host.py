"""Lazy Settings-body ownership for Visualizer modes (pre-V5/V6 gate item 4).

Canonical owner of per-mode Settings *body* lifecycle for the future top-level
Visualizers tab. Deliberately Qt-agnostic: a "body" is an opaque object produced
by an injected ``body_factory`` (in production a thin adapter that runs the
existing mode builder via the descriptor's lazy Settings-builder wiring — see
``load_mode_settings_builder`` — through one shared host; in tests a counting
fake). The host owns *when* bodies exist, never the authored state itself:
mode-local settings / presets / preset index / Custom / colours / floors /
technical values live solely in the settings/model authority, so retiring a body
loses nothing and reselecting a mode reconstructs its body from that preserved
state.

Ownership contract (gate item 4):

- nothing is constructed at host creation;
- a body is constructed only when its mode is *selected* (its pill becomes
  active), so both disabled and enabled-but-unselected modes stay dormant until
  actually needed;
- disabling a mode whose body exists retires that body immediately (never a
  hidden active owner) without touching its persisted state;
- reselecting a re-enabled mode reconstructs its body from the preserved state;
- there is one state authority — the host never becomes a second one;
- no timers, pollers, workers or cadence are used for any of this.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from core.settings.visualizer_mode_registry import (
    get_visualizer_mode_descriptor,
    resolve_effective_enabled_modes,
)

SETUP_PILL_ID = "SETUP"


def visualizer_pill_model(enabled_modes: object) -> tuple[tuple[str, str], ...]:
    """Return ordered ``(pill_id, label)`` pairs for the Visualizers tab.

    Always leads with the SETUP pill, then one pill per *effective enabled* mode
    in canonical descriptor order (never activation order). A disabled mode
    contributes no pill. Pure — no construction, no Qt.
    """
    pills: list[tuple[str, str]] = [(SETUP_PILL_ID, "Setup")]
    for mode_id in resolve_effective_enabled_modes(enabled_modes):
        pills.append((mode_id, get_visualizer_mode_descriptor(mode_id).display_name))
    return tuple(pills)


class VisualizerModeBodyHost:
    """Own lazy construction/retirement of per-mode Settings bodies."""

    def __init__(
        self,
        *,
        body_factory: Callable[[str], Any],
        retire_body: Optional[Callable[[str, Any], None]] = None,
        enabled_modes: object = None,
    ) -> None:
        self._factory = body_factory
        self._retire = retire_body
        self._enabled: tuple[str, ...] = resolve_effective_enabled_modes(enabled_modes)
        self._bodies: dict[str, Any] = {}
        self._selected: Optional[str] = None

    @property
    def enabled_modes(self) -> tuple[str, ...]:
        return self._enabled

    @property
    def selected_mode(self) -> Optional[str]:
        return self._selected

    def constructed_modes(self) -> frozenset[str]:
        return frozenset(self._bodies)

    def is_constructed(self, mode_id: str) -> bool:
        return self._norm(mode_id) in self._bodies

    def body(self, mode_id: str) -> Optional[Any]:
        return self._bodies.get(self._norm(mode_id))

    @staticmethod
    def _norm(mode_id: str) -> str:
        return str(mode_id or "").strip().lower()

    def select(self, mode_id: str) -> Any:
        """Select a mode's pill, constructing its body lazily on first need.

        Returns the body. Rejects a mode outside the effective enabled set (a
        disabled mode has no pill and no body); callers resolve a disabled/stale
        request through the effective-mode resolver *before* selecting.
        """
        target = self._norm(mode_id)
        if target not in self._enabled:
            raise ValueError(f"Cannot select disabled visualizer mode {mode_id!r}")
        body = self._bodies.get(target)
        if body is None:
            body = self._factory(target)
            self._bodies[target] = body
        self._selected = target
        return body

    def set_enabled_modes(self, enabled_modes: object) -> tuple[str, ...]:
        """Apply a new enabled set, retiring bodies for now-disabled modes.

        Returns the retired mode ids in canonical order. A retired body's
        persisted state is untouched — the host never owned it. If the selected
        mode was disabled, selection is cleared and the caller reselects an
        enabled mode through the effective-mode resolver.
        """
        new_enabled = resolve_effective_enabled_modes(enabled_modes)
        retired = tuple(
            mode_id for mode_id in self._enabled
            if mode_id in self._bodies and mode_id not in new_enabled
        )
        for mode_id in retired:
            body = self._bodies.pop(mode_id)
            if self._retire is not None:
                self._retire(mode_id, body)
        self._enabled = new_enabled
        if self._selected is not None and self._selected not in new_enabled:
            self._selected = None
        return retired

    def retire_all(self) -> None:
        """Retire every constructed body (e.g. on Settings-dialog teardown)."""
        for mode_id, body in list(self._bodies.items()):
            if self._retire is not None:
                self._retire(mode_id, body)
        self._bodies.clear()
        self._selected = None
