"""Studio step-state snapshots (`ui/studio/replay_engine.StepState`) take every plain value a production controller
may hold.

7 Nov: field-only controller state held a `WindowsPath`, and every engine-answer Studio (Spectrum, Oscilloscope,
DevCurve, Neon Lake, Sphere, Extruded Spectrum) failed to start with "Step state holds an uncopyable WindowsPath".
The tests ran on default profiles that never put a path there, so nothing caught it.
"""
from __future__ import annotations

import pathlib

import pytest

from ui.studio.replay_engine import StepState


class _Owner:
    pass


def _controller(**attrs):
    controller, tick, presentation = _Owner(), _Owner(), _Owner()
    controller.logical_tick_state = tick
    controller.presentation_state = presentation
    for name, value in attrs.items():
        setattr(presentation, name, value)
    return controller


def test_a_path_in_step_state_is_kept_and_restored():
    path = pathlib.Path("themes") / "widgets" / "Default Dark.srwtheme"
    controller = _controller(theme_path=path, level=0.5)
    state = StepState(controller)
    controller.presentation_state.theme_path = pathlib.Path("elsewhere")
    controller.presentation_state.level = 0.9
    state.restore()
    assert controller.presentation_state.theme_path == path
    assert controller.presentation_state.level == 0.5


def test_an_uncopyable_value_names_the_attribute_that_holds_it_negative_control():
    """Unknown types still refuse loudly (a silent shallow share could leak per-tick state between replays), and the
    error names the owner attribute so a field-only failure identifies itself."""

    class Opaque:
        __slots__ = ()

    controller = _controller(handle=Opaque())
    with pytest.raises(TypeError, match=r"uncopyable \S*Opaque \(in _Owner\.handle\)"):
        StepState(controller)
