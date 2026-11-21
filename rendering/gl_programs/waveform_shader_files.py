"""Waveform Ribbon's shader files, one text for both renderers (Current_Plan.md N5.4; Native_Port_Playbook.md checklist
16: the Python renderer draws these texts, the native core draws the same files).

Why it exists: the Python renderer composes its programs from Python texts (``rendering.gl_programs.ribbon``,
``waveform_ribbon``, ``waveform_atmosphere``, ``ribbon_bursts``, ``fog_volume``, ``waveform_floor_give``), converted
portable (N1.6: one std140 pass block a program); the native core loads ``.qsb`` packs baked from the shader folder
(``widgets/spotify_visualizer/shaders``, ``tools/regen_qrc.py --shaders``). Each program's converted text is written
there as a body (``waveform_*.glsl``, its version line left to the pass file) and a test holds every file equal to its
text (``tests/test_waveform_shader_files.py``), so the two renderers draw one source.

The pass files: the core fills a block member by its name, from one source for every pass that declares it
(``native/core/src/mode_content.cpp``), while Waveform's programs share member names that hold other values in other
passes (``uMvp`` is the ribbons' rebased clip matrix, the floor's world one and the sparks' history one; the mirrored
camera's passes and the floor's reduced pre-pass draw a program with other values again). So each pass file is
``#version``, a ``#define`` per member of its block giving it its pass's prefix (``uMvp`` -> ``ribbon_uMvp``), and
the body's ``#include``: the arithmetic is the body's, only the names differ, and each pass's values reach its own
members (``member_name``). The Python renderer packs by its layout's offsets, which the renames leave as they are.

``waveform_shader_files()`` gives every file's name and text; ``tools/waveform_shader_files.py`` writes them.
"""
from __future__ import annotations

import re

_VERSION = "#version 460 core\n"


def member_name(pass_id: str, member: str) -> str:
    """A block member's name in a pass file: its pass's prefix (``member_name("ribbon", "uMvp")`` -> ``ribbon_uMvp``),
    the name the native record or settings fill."""
    return f"{pass_id}_{member}"


#: The sorted pack's transparent write (D17 choice D: on a device the order-independent gate does not admit, the core
#: draws a transparent pass premultiplied over its owner): ``SCENE_OIT_GLSL``'s function, writing the owner's colour.
SORTED_GLSL = """
layout(location = 0) out vec4 SceneColour;
void sceneTransparent(vec3 premultiplied, float alpha, float viewDepth) {
    SceneColour = vec4(premultiplied, alpha);
}
"""


def sorted_body(body: str) -> str:
    """The ribbon body's sorted pack text: its order-independent outputs replaced by ``SORTED_GLSL`` and its emission
    moved to location 1 (the owner's emission attachment), nothing else changed. The Python renderer always draws the
    order-independent form; the native core draws this only where its gate refuses order independence."""
    from rendering.quick.scene3d.target import SCENE_OIT_GLSL

    if body.count(SCENE_OIT_GLSL) != 1 or body.count("layout(location=2) out vec4 Emission;") != 1:
        raise ValueError("the ribbon body holds SCENE_OIT_GLSL once and its emission at location 2")
    return body.replace(SCENE_OIT_GLSL, SORTED_GLSL).replace("layout(location=2) out vec4 Emission;",
                                                             "layout(location=1) out vec4 Emission;")


def _bodies() -> dict[str, str]:
    """Body name -> the converted text the Python renderer compiles (its version line first)."""
    from rendering.gl_programs import ribbon, ribbon_bursts, waveform_atmosphere, waveform_floor_give, waveform_ribbon
    from rendering.gl_programs.fog_volume import FOG_INTEGRATE_COMPUTE

    return {
        "waveform_ribbon_vertex": ribbon.RIBBON_CONTINUOUS_VERTEX,
        "waveform_ribbon_body": ribbon.RIBBON_BODY_FRAGMENT,
        "waveform_ribbon_body_sorted": sorted_body(ribbon.RIBBON_BODY_FRAGMENT),
        "waveform_ribbon_light": ribbon.RIBBON_LIGHT_FRAGMENT,
        "waveform_strays_vertex": ribbon.RIBBON_COHORT_STRAY_VERTEX,
        "waveform_strays_fragment": ribbon.RIBBON_COHORT_STRAY_FRAGMENT,
        "waveform_bursts_vertex": ribbon_bursts.VERTEX,
        "waveform_bursts_fragment": ribbon_bursts.FRAGMENT,
        "waveform_floor_vertex": waveform_ribbon.FLOOR_VERTEX,
        "waveform_floor_fragment": waveform_ribbon.FLOOR_FRAGMENT,
        "waveform_sky_vertex": waveform_atmosphere.SKY_VERTEX,
        "waveform_sky_fragment": waveform_atmosphere.SKY_FRAGMENT,
        "waveform_field": waveform_atmosphere.FIELD_COMPUTE,
        "waveform_medium": waveform_atmosphere.MEDIUM_INJECT_SOURCE,
        "waveform_fog_integrate": FOG_INTEGRATE_COMPUTE,
        "waveform_give_section": waveform_floor_give.FLOOR_GIVE_SECTION_COMPUTE,
        "waveform_give_blur": waveform_floor_give.FLOOR_GIVE_BLUR_COMPUTE,
    }


#: Each pass file: (file, body, pass id). The ribbon's body and both continuation extensions are one draw (its vertex
#: stage decodes the part); its body and light passes share their values (one prefix).
PASS_FILES = (
    ("waveform_ribbon.vert", "waveform_ribbon_vertex", "ribbon"),
    ("waveform_ribbon_mirror.vert", "waveform_ribbon_vertex", "ribbon_mirror"),
    ("waveform_ribbon_body.frag", "waveform_ribbon_body", "ribbon"),
    ("waveform_ribbon_body_sorted.frag", "waveform_ribbon_body_sorted", "ribbon"),
    ("waveform_ribbon_light.frag", "waveform_ribbon_light", "ribbon"),
    ("waveform_ribbon_light_mirror.frag", "waveform_ribbon_light", "ribbon_mirror"),
    ("waveform_strays.vert", "waveform_strays_vertex", "strays"),
    ("waveform_strays_mirror.vert", "waveform_strays_vertex", "strays_mirror"),
    ("waveform_strays.frag", "waveform_strays_fragment", "strays"),
    ("waveform_strays_mirror.frag", "waveform_strays_fragment", "strays_mirror"),
    ("waveform_bursts.vert", "waveform_bursts_vertex", "bursts"),
    ("waveform_bursts_mirror.vert", "waveform_bursts_vertex", "bursts_mirror"),
    ("waveform_bursts.frag", "waveform_bursts_fragment", "bursts"),
    ("waveform_bursts_mirror.frag", "waveform_bursts_fragment", "bursts_mirror"),
    ("waveform_floor.vert", "waveform_floor_vertex", "floor"),
    ("waveform_floor_prepass.vert", "waveform_floor_vertex", "floor_prepass"),
    ("waveform_floor.frag", "waveform_floor_fragment", "floor"),
    ("waveform_floor_prepass.frag", "waveform_floor_fragment", "floor_prepass"),
    ("waveform_sky.vert", "waveform_sky_vertex", "sky"),
    ("waveform_sky_mirror.vert", "waveform_sky_vertex", "sky_mirror"),
    ("waveform_sky.frag", "waveform_sky_fragment", "sky"),
    ("waveform_sky_mirror.frag", "waveform_sky_fragment", "sky_mirror"),
    ("waveform_field.comp", "waveform_field", "field"),
    ("waveform_medium.comp", "waveform_medium", "medium"),
    ("waveform_medium_mirror.comp", "waveform_medium", "medium_mirror"),
    ("waveform_fog_integrate.comp", "waveform_fog_integrate", "integrate"),
    ("waveform_fog_integrate_mirror.comp", "waveform_fog_integrate", "integrate_mirror"),
    ("waveform_give_section.comp", "waveform_give_section", "give_section"),
    ("waveform_give_blur.comp", "waveform_give_blur", "give_blur"),
)

_BLOCK = re.compile(r"layout\s*\(\s*std140\s*,\s*binding\s*=\s*\d+\s*\)\s*uniform\s+(\w+)\s*\{(.*?)\}\s*;", re.S)
_MEMBER = re.compile(r"^\s*(\w+)\s+(\w+)\s*(?:\[\s*(\d+)\s*\])?\s*;", re.M)
#: Numbers a member type takes (a std140 block's scalar, vector and matrix types the Waveform programs declare).
_COMPONENTS = {"float": 1, "int": 1, "uint": 1, "bool": 1, "vec2": 2, "ivec2": 2, "vec3": 3, "ivec3": 3, "vec4": 4,
               "ivec4": 4, "mat3": 9, "mat4": 16}


def _own_block(text: str) -> str:
    stripped = re.sub(r"//[^\n]*", "", text)
    blocks = [block for block in _BLOCK.findall(stripped) if block[0] != "SrpssConventions"]
    if len(blocks) != 1:
        raise ValueError(f"a Waveform program declares one block of its own, not {len(blocks)}")
    return blocks[0][1]


def block_members(text: str) -> tuple[str, ...]:
    """The members of the one std140 block a body declares as its own, in order (comments ignored; the conventions
    block, ``SrpssConventions``, is the core's)."""
    return tuple(name for _kind, name, _size in _MEMBER.findall(_own_block(text)))


def block_numbers(text: str) -> dict[str, int]:
    """Each member of the body's own block and how many numbers it takes (its components times its elements)."""
    return {name: _COMPONENTS[kind] * (int(size) if size else 1) for kind, name, size in _MEMBER.findall(_own_block(text))}


def pass_numbers() -> dict[str, dict[str, int]]:
    """Each pass id's members (unprefixed) and their numbers, in block order."""
    bodies = _bodies()
    return {pass_id: block_numbers(bodies[body]) for _name, body, pass_id in PASS_FILES}


def body_text(text: str) -> str:
    """A converted text as its body file holds it: without its version line (the pass file's first line)."""
    if not text.startswith(_VERSION):
        raise ValueError("a Waveform program's text starts with its version line")
    return text[len(_VERSION):]


def wrapper_text(body: str, pass_id: str, members: tuple[str, ...]) -> str:
    """A pass file: the version line, the pass's member names and the body's include."""
    lines = [_VERSION.rstrip("\n"),
             f"// Waveform Ribbon (rendering/gl_programs/waveform_shader_files.py): {body} for the {pass_id} pass, its "
             "block's members named for it (the arithmetic the body's)"]
    lines += [f"#define {member} {member_name(pass_id, member)}" for member in members]
    lines.append(f'#include "{body}.glsl"')
    return "\n".join(lines) + "\n"


def pass_members() -> dict[str, tuple[str, ...]]:
    """Each pass id's block members (unprefixed), in order."""
    bodies = _bodies()
    found: dict[str, tuple[str, ...]] = {}
    for _name, body, pass_id in PASS_FILES:
        members = block_members(bodies[body])
        if found.setdefault(pass_id, members) != members:
            raise ValueError(f"the {pass_id} pass's stages declare different blocks")
    return found


#: The native schema's table of the pass files' members (``core/visualizer_engine/waveform_native_members.py``):
#: written from ``pass_numbers`` so the schema needs no renderer import (the engine worker loads every runtime schema).
MEMBERS_MODULE = "core/visualizer_engine/waveform_native_members.py"


def members_module_text() -> str:
    """The text of ``MEMBERS_MODULE``: every pass's block members and their numbers, in pass and block order."""
    lines = ['"""Waveform Ribbon\'s pass members for its native schema (``core.visualizer_engine.waveform_native_schema``):',
             "each pass file's block members (unprefixed) and how many numbers each takes, in pass and block order.",
             "",
             "Written by ``tools/waveform_shader_files.py --write`` from ``rendering.gl_programs.waveform_shader_files``",
             '(``pass_numbers``); ``tests/test_waveform_shader_files.py`` holds it equal. Never edit by hand."""',
             "",
             "PASS_MEMBERS = ("]
    for pass_id, members in pass_numbers().items():
        lines.append(f"    ({pass_id!r}, (")
        lines += [f"        ({member!r}, {numbers}),"for member, numbers in members.items()]
        lines.append("    )),")
    lines.append(")")
    return "\n".join(lines) + "\n"


def waveform_shader_files() -> dict[str, str]:
    """Every Waveform shader file's name and text: the bodies (``.glsl``) and the pass files."""
    bodies = _bodies()
    files = {f"{name}.glsl": body_text(text) for name, text in bodies.items()}
    files.update({name: wrapper_text(body, pass_id, block_members(bodies[body])) for name, body, pass_id in PASS_FILES})
    return files


__all__ = ["PASS_FILES", "block_members", "body_text", "member_name", "pass_members", "waveform_shader_files",
           "wrapper_text"]
