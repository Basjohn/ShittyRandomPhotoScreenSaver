"""Diagnostic experiment admission — parsed once at startup, activated deliberately.

These flags admit *opt-in* investigation instrumentation for the Visualizer
post-switch performance investigation (``Docs/Future_Work/
Visualizer_Post_Switch_Performance.md``). They are **not** product feature gates:
``core/dev_gates.py`` deliberately does not own them, because ``--abc-drive`` and
``--viz-switch-telemetry`` are experiment/debug admissions rather than shippable
capabilities.

Two admissions:

* ``--viz-switch-telemetry`` — admit the boundary-only render-host switch/resource
  ownership telemetry (P1). Without it, Standard/MC runtime allocates no lifecycle
  telemetry object, takes no new lock, keeps no new bookkeeping, and adds no new
  logging/timer/sampler/GL query for this investigation.
* ``--abc-drive=A|B|C`` — admit the opt-in in-app A/B/C experiment driver (P4).
  Because the driver scores exactly the boundary telemetry above, ``--abc-drive``
  **implicitly** enables the switch telemetry too.

Contract:

* parse the process argv **once** during startup (:func:`parse_experiment_flags`);
* activate the parsed result **deliberately** (:func:`activate_experiment_flags`),
  never at import, never from an environment variable, never from a marker file;
* code that must consult the admission reads :func:`active_experiment_flags` (or a
  named helper), which returns a disabled default until startup activates it;
* tests/tools inject telemetry directly at the owner seam instead of depending on
  process argv; :func:`override_active_flags_for_testing` exists only for the few
  tests that must exercise the process-level admission itself.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

_VALID_CONDITIONS = frozenset({"A", "B", "C"})


@dataclass(frozen=True, slots=True)
class ExperimentFlags:
    """Immutable diagnostic experiment admission derived once from argv."""

    abc_drive: str | None = None
    viz_switch_telemetry: bool = False
    abc_layout_slot: str | None = None

    @property
    def lifecycle_telemetry_admitted(self) -> bool:
        """True when the boundary render-host telemetry must be allocated.

        ``--abc-drive`` implicitly admits the same telemetry it scores, so either
        flag turns it on; neither leaves it off (Standard/MC runtime).
        """
        return self.viz_switch_telemetry or self.abc_drive is not None


def parse_experiment_flags(argv: Sequence[str]) -> ExperimentFlags:
    """Parse the diagnostic experiment flags out of a full argv, once.

    Accepts ``--viz-switch-telemetry``, ``--abc-drive=<A|B|C>`` and the
    space-separated ``--abc-drive <A|B|C>``. An unrecognised/invalid condition
    leaves ``abc_drive`` unset rather than raising, so an ordinary launch is never
    blocked by a malformed diagnostic flag. Pure and side-effect free.
    """
    args = [str(arg) for arg in argv]
    abc_drive: str | None = None
    viz_switch_telemetry = False
    abc_layout_slot: str | None = None
    for index, arg in enumerate(args):
        if arg == "--viz-switch-telemetry":
            viz_switch_telemetry = True
            continue
        value: str | None = None
        if arg.startswith("--abc-drive="):
            value = arg.split("=", 1)[1]
        elif arg == "--abc-drive" and index + 1 < len(args):
            value = args[index + 1]
        if value is not None:
            condition = value.strip().upper()
            if condition in _VALID_CONDITIONS:
                abc_drive = condition
            continue
        slot: str | None = None
        if arg.startswith("--abc-layout-slot="):
            slot = arg.split("=", 1)[1]
        elif arg == "--abc-layout-slot" and index + 1 < len(args):
            slot = args[index + 1]
        if slot is not None:
            slot = slot.strip()
            if slot:
                abc_layout_slot = slot
    return ExperimentFlags(
        abc_drive=abc_drive,
        viz_switch_telemetry=viz_switch_telemetry,
        abc_layout_slot=abc_layout_slot,
    )


def experiment_flag_tokens(argv: Sequence[str]) -> tuple[str, ...]:
    """Return the argv tokens that belong to diagnostic experiment flags.

    Startup uses this to strip experiment admissions (and the value consumed by
    the space-separated ``--abc-drive B`` form) from the argv handed to
    screensaver mode detection, so a diagnostic flag never leaks into RUN/CONFIG
    parsing.
    """
    args = [str(arg) for arg in argv]
    tokens: list[str] = []
    for index, arg in enumerate(args):
        if (
            arg == "--viz-switch-telemetry"
            or arg.startswith("--abc-drive=")
            or arg.startswith("--abc-layout-slot=")
        ):
            tokens.append(arg)
        elif arg in ("--abc-drive", "--abc-layout-slot"):
            tokens.append(arg)
            if index + 1 < len(args):
                tokens.append(args[index + 1])
    return tuple(tokens)


# Process-level activation ---------------------------------------------------
# Set ONCE during startup by the app entrypoint. Not read from argv at import,
# not an environment variable, not a marker file.
_ACTIVE: ExperimentFlags | None = None


def activate_experiment_flags(flags: ExperimentFlags) -> ExperimentFlags:
    """Deliberately activate the parsed flags for the process. Returns them."""
    global _ACTIVE
    _ACTIVE = flags
    return flags


def active_experiment_flags() -> ExperimentFlags:
    """Return the activated flags, or a disabled default before activation."""
    return _ACTIVE if _ACTIVE is not None else ExperimentFlags()


def abc_drive_condition() -> str | None:
    """Return the opt-in visualizer-switch A/B/C experiment condition, if any."""
    return active_experiment_flags().abc_drive


def abc_layout_slot() -> str | None:
    """Return the saved-layout slot the A/B/C baseline recreation should load."""
    return active_experiment_flags().abc_layout_slot


def visualizer_switch_telemetry_admitted() -> bool:
    """True when opt-in render-host switch/resource telemetry must be allocated."""
    return active_experiment_flags().lifecycle_telemetry_admitted


def override_active_flags_for_testing(flags: ExperimentFlags | None) -> None:
    """Set/clear the process admission directly (tests of the admission only)."""
    global _ACTIVE
    _ACTIVE = flags


__all__ = [
    "ExperimentFlags",
    "parse_experiment_flags",
    "experiment_flag_tokens",
    "activate_experiment_flags",
    "active_experiment_flags",
    "abc_drive_condition",
    "abc_layout_slot",
    "visualizer_switch_telemetry_admitted",
    "override_active_flags_for_testing",
]
