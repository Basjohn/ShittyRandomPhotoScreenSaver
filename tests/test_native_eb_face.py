"""N5.6: the mode face speaks ABI 42's keys (``rendering/native/mode.py``), GPU-free.

``native/core/python/eb_core_check.py`` proved each key on the built module through hand-written declarations (its
``Raw`` and ``_with``); the face's classes must declare exactly those forms, so Extruded Bubble's program is written
in the face. Each check has its control: the form the face would declare without the key.
"""
from __future__ import annotations

import pytest


def test_a_cube_target_declares_the_probe_cube_eb_core_check_drew():
    from rendering.native.mode import ModeTarget, TargetAttachment

    cube = ModeTarget("probe", (TargetAttachment("colour", "rgba16f"),), size=(64, 64), allocation="exact", cube=True)
    # eb_core_check._probe_program's Raw declaration of its cube.
    assert cube.declaration() == {"name": "probe", "size": [64, 64], "colour": [{"name": "colour", "format": "rgba16f"}],
                                  "cube": True, "allocation": "exact"}
    # Control: the same target without the key is a plain 2D target.
    assert "cube" not in ModeTarget("probe", (TargetAttachment("colour", "rgba16f"),), size=(64, 64),
                                    allocation="exact").declaration()


@pytest.mark.parametrize("change", [dict(size=(64, 32)), dict(allocation="bucket"), dict(samples=4), dict(size=None),
                                    dict(colour=("rgba8",))])
def test_a_cube_target_refuses_what_the_core_refuses(change):
    from rendering.native.mode import ModeTarget, TargetAttachment

    keys = dict(size=(64, 64), allocation="exact", samples=1, colour=("rgba16f",))
    keys.update(change)
    colour = tuple(TargetAttachment("colour", fmt) for fmt in keys.pop("colour"))
    with pytest.raises(ValueError):
        ModeTarget("probe", colour, cube=True, **keys)
    # Control: the same keys on a 2D target are admitted.
    ModeTarget("probe", colour, **keys)


def test_a_face_pass_and_a_prefilter_declare_what_eb_core_check_drew():
    from rendering.native.mode import ModePass, PrefilterStep, program_json

    face = ModePass("face2", b"pack", "replace", target="probe", face=2)
    assert face.declaration() == {"name": "face2", "blend": "replace", "target": "probe", "face": 2}
    assert PrefilterStep("filter", "probe").declaration() == {"name": "filter", "prefilter": "probe"}
    # A prefilter is a step: its pack is empty (the core's filter).
    _program, packs = program_json([face, PrefilterStep("filter", "probe")])
    assert packs == [b"pack", b""]
    with pytest.raises(ValueError):
        ModePass("face6", b"", "replace", target="probe", face=6)
    # Control: a pass without a face declares none.
    assert "face" not in ModePass("look", b"", "replace", target="probe").declaration()


def test_when_is_declared_on_a_draw_pass_and_a_defocus_step():
    from rendering.native.mode import DefocusStep, ModePass

    assert ModePass("near", b"", when="w").declaration()["when"] == "w"
    assert DefocusStep("defocus", "near", "scene", when="w").declaration() == {
        "name": "defocus", "defocus": "near", "onto": "scene", "when": "w"}
    # Control: without it the step's declaration is ABI 33's.
    assert DefocusStep("defocus", "near", "scene").declaration() == {"name": "defocus", "defocus": "near",
                                                                     "onto": "scene"}


def test_a_once_entry_declares_its_readback_and_a_geometry_buffer_its_key():
    from rendering.native.mode import COMPUTE_TRIGGERS, ComputeBinding, ComputePass, GeometryBuffer

    assert "once" in COMPUTE_TRIGGERS
    check = ComputePass("check", b"", (ComputeBinding("Out", "results", access="write"),), groups=(1, 1, 1),
                        trigger="once", readback="results")
    declared = check.declaration()
    assert declared["trigger"] == "once" and declared["readback"] == "results"
    with pytest.raises(ValueError):
        ComputePass("check", b"", groups=(1, 1, 1), readback="results")
    # eb_core_check.drift_compute_program's Raw geometry buffer.
    assert GeometryBuffer("chains_geometry", 0, "chains_key").declaration() == {
        "name": "chains_geometry", "geometry": {"family": 0, "key": "chains_key"}}
    assert ComputeBinding("OldGeometry", "chains_geometry@previous").declaration()["buffer"] == "chains_geometry@previous"
    with pytest.raises(ValueError):
        GeometryBuffer("g", 8, "k")
    # Control: a frame entry declares no readback.
    assert "readback" not in ComputePass("c", b"", groups=(1, 1, 1)).declaration()
