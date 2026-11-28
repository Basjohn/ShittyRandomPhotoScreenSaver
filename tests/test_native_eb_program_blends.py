"""Extruded Bubble's native program never leaves one attachment unblended beside a blended one in a pass.

On OpenGL, a pass whose colour attachment had blending off ("replace") beside a blended emission attachment drew its
colour blended with the funcs a previous pipeline left (the specks' and glints' light blend, alpha ZERO, ONE): the
backdrop's colour came through but its alpha stayed the cleared 0, so the scene composed as glass over nothing
(28 Nov readback: scene alpha 0.0 after the backdrop, 1.0 with the emission masked or the colour's replace declared
as an enabled ONE, ZERO blend). Every written attachment of a multi-attachment pass therefore blends explicitly.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from rendering.native import extruded_bubble_program as ebp


def _resolved(blend):
    return "replace" if blend == "replace" else blend


def _mixed_passes(module, variant) -> list[str]:
    """The passes writing an attachment with blending off beside one with blending on."""
    mixed = []
    for entry in module.program(variant)["passes"]:
        outputs = getattr(entry, "outputs", ()) or ()
        if len(outputs) < 2:
            continue
        written = [output.blend if output.blend is not None else entry.blend for output in outputs if output.write]
        off = [blend for blend in written if _resolved(blend) == "replace"]
        if off and len(off) != len(written):
            mixed.append(entry.name)
    return mixed


def _control_module():
    """The program with its backdrop colour declared plain "replace" again (the pre-fix declaration)."""
    source = Path(ebp.__file__).read_text(encoding="utf-8")
    old = 'outputs=(PassOutput(True, replace), PassOutput(True, "additive"))'
    assert source.count(old) == 1
    copy = types.ModuleType(ebp.__name__ + "_control")
    copy.__file__ = ebp.__file__
    sys.modules[copy.__name__] = copy
    try:
        exec(compile(source.replace(old, 'outputs=(PassOutput(True, "replace"), PassOutput(True, "additive"))'),
                     ebp.__file__, "exec"), copy.__dict__)
    finally:
        sys.modules.pop(copy.__name__, None)
    return copy


@pytest.mark.parametrize("samples", (1, 4))
def test_no_pass_mixes_an_unblended_attachment_with_a_blended_one(samples):
    assert _mixed_passes(ebp, (samples,)) == []


def test_control_the_plain_replace_backdrop_is_seen():
    assert _mixed_passes(_control_module(), (4,)) == ["backdrop"]
