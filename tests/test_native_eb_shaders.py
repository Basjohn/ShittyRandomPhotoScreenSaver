"""N5.6: Extruded Bubble's native packs are the Python renderer's texts, each program's members named for it
(``rendering/native/extruded_bubble_shaders.py``, ``tools/eb_native_shaders.py``).

Each check has its control: the Python text as it is (shared member names, unlocated varyings) fails it.
"""
from __future__ import annotations

import re

import pytest


def _defines(text: str) -> dict[str, str]:
    return dict(re.findall(r"^#define (\w+) (\w+)$", text, re.M))


def test_every_program_names_each_block_member_for_itself_and_keeps_the_core_members():
    from rendering.native.extruded_bubble_shaders import PROGRAMS, block_members, member_name, shader_files
    from rendering.native.mode import MODE_CORE_MEMBERS

    files = shader_files()
    owners: dict[str, str] = {}
    for program in PROGRAMS:
        for stage in ("vert", "frag"):
            renamed = {k: v for k, v in _defines(files[f"eb_{program}.{stage}"]).items() if k in block_members(program)}
            expected = {m: member_name(program, m) for m in block_members(program) if m not in MODE_CORE_MEMBERS}
            assert renamed == expected
        for member in block_members(program):
            name = member_name(program, member)
            if member in MODE_CORE_MEMBERS:
                assert name == member
            else:
                assert owners.setdefault(name, program) == program     # no other program fills this name
    # Control: without the prefixes two programs would share a name the core fills from one source.
    assert member_name("shells", "uTime") != member_name("near", "uTime")
    from rendering.gl_programs.extruded_bubble_program import BUBBLE_FRAGMENT
    assert not set(_defines(BUBBLE_FRAGMENT)) & set(block_members("shells"))


def test_the_texts_are_the_python_texts_apart_from_the_names_and_the_core_variants():
    from rendering.gl_programs import extruded_bubble_program as p
    from rendering.native.extruded_bubble_shaders import shader_files, sorted_text

    files = shader_files()
    body = files["eb_backdrop.frag"].split("\n", 1)[1]
    body = "\n".join(line for line in body.splitlines() if not line.startswith(("#define u", "// Extruded Bubble")))
    assert body.strip() == p.BACKDROP_FRAGMENT.split("\n", 1)[1].strip()
    assert "SceneColour" in files["eb_shells_sorted.frag"] and "SceneAccum" not in files["eb_shells_sorted.frag"]
    assert "layout(location=1) out vec4 Emission;" in files["eb_shells_sorted.frag"]
    # The probe's proxies keep their emission as a plain variable (one cube attachment).
    assert "out vec4 Emission" not in files["eb_proxies.frag"] and "out vec4 Emission" in files["eb_specks.frag"]
    with pytest.raises(ValueError):
        sorted_text(p.PARTICLE_FRAGMENT)      # control: an opaque fragment has no order-independent outputs


def test_every_varying_is_located_and_paired_by_name():
    from rendering.gl_programs import extruded_bubble_program as p
    from rendering.native.extruded_bubble_shaders import PROGRAMS, shader_files

    unlocated = re.compile(r"^(?:flat\s+)?(?:in|out)\s+\w+\s+\w+", re.M)
    files = shader_files()
    for program in PROGRAMS:
        vertex, fragment = files[f"eb_{program}.vert"], files[f"eb_{program}.frag"]
        assert not unlocated.search(vertex) and not unlocated.search(fragment), program
        outs = dict((n, l) for l, n in re.findall(r"location=(\d+)\)\s*(?:flat\s+)?out\s+\w+\s+(\w+)", vertex))
        ins = dict((n, l) for l, n in re.findall(r"location=(\d+)\)\s*(?:flat\s+)?in\s+\w+\s+(\w+)", fragment))
        assert all(outs[name] == location for name, location in ins.items()), program
    # Controls: an unlocated declaration is found, and a fragment input its vertex stage never writes is refused.
    from rendering.native.extruded_bubble_shaders import _located

    assert unlocated.search("#version 460 core\nin vec2 vNdc;\n")
    with pytest.raises(ValueError):
        _located(p.FULL_VERTEX, "#version 460 core\nin vec2 vMissing;\n")


def test_the_committed_packs_are_what_the_texts_bake_to():
    pytest.importorskip("PySide6")
    from tools.eb_native_shaders import statuses

    found = statuses(bake=False)
    assert found and all(current for _name, current, _reason in found), [f for f in found if not f[1]]
