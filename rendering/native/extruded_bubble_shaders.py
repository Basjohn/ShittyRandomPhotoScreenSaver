"""Extruded Bubble's native shader texts (Current_Plan.md N5.6, "Native record and route"; Native_Port_Playbook.md
checklist 16: the native core draws the Python renderer's own texts).

The Python renderer (``rendering.quick.visualizer.implementations.extruded_bubble``) draws twelve programs from four
portable families (``rendering.gl_programs.extruded_bubble_program``: one std140 pass block a family), each program
holding its own values of its family's block. The core fills a block member by name from one source for every pass
that declares it (``native/core/src/mode_content.cpp``), so each program's texts here name its members for it
(``uTime`` -> ``shells_u_time``, the core's own members kept: ``member_name``), as Waveform's pass files do
(``rendering.gl_programs.waveform_shader_files``): the arithmetic is the Python text's, only the names differ, and the
Python renderer packs by its layouts' offsets, which the renames leave as they are.

The texts are made here in memory and baked by ``tools/eb_native_shaders.py`` into
``widgets/spotify_visualizer/shaders/extruded_bubble`` (a subfolder: the Python references' key hashes the shader
folder's own files, which these never are). Variants the core needs and OpenGL does not:

- ``sorted``: a transparent program's pack for a device the order-independent gate refuses (D17 choice D):
  ``SCENE_OIT_GLSL`` replaced by ``SORTED_GLSL``, its emission moved to the owner's location 1;
- the glint proxies draw into the probe's cube (one attachment), so their emission is a plain variable (OpenGL drops
  an unattached output; the core requires a program to write exactly its target's attachments);
- an input or output without a location gets the location its stage pairs it with (SPIR-V requires one);
- every anonymous block gets an instance name, the same in every stage (``_instanced``: OpenGL links the translated
  uniforms by name across stages).
"""
from __future__ import annotations

import re

_VERSION = "#version 460 core\n"


def _texts() -> dict[str, tuple[str, str, object]]:
    """Each Python program key -> (vertex text, fragment text, its family's block layout), in the renderer's order."""
    from rendering.gl_programs import extruded_bubble_program as p

    return {
        "backdrop": (p.FULL_VERTEX, p.BACKDROP_FRAGMENT, p.FULLSCREEN_BLOCK),
        "probe_backdrop": (p.FULL_VERTEX, p.PROBE_BACKDROP_FRAGMENT, p.FULLSCREEN_BLOCK),
        "shafts": (p.FULL_VERTEX, p.SHAFT_FRAGMENT, p.FULLSCREEN_BLOCK),
        "blur": (p.FULL_VERTEX, p.BLUR_FRAGMENT, p.FULLSCREEN_BLOCK),
        "shells": (p.BUBBLE_VERTEX, p.BUBBLE_FRAGMENT, p.GLASS_BLOCK),
        "clusters": (p.CLUSTER_VERTEX, p.CLUSTER_FRAGMENT, p.GLASS_BLOCK),
        "beads": (p.BEAD_VERTEX, p.BUBBLE_FRAGMENT, p.GLASS_BLOCK),
        "near": (p.BUBBLE_VERTEX, p.NEAR_FRAGMENT, p.GLASS_BLOCK),
        "near_clusters": (p.CLUSTER_VERTEX, p.NEAR_CLUSTER_FRAGMENT, p.GLASS_BLOCK),
        "proxies": (p.PARTICLE_VERTEX, p.PARTICLE_FRAGMENT, p.PARTICLE_BLOCK),
        "specks": (p.SPECK_VERTEX, p.PARTICLE_FRAGMENT, p.PARTICLE_BLOCK),
        "trails": (p.TRAIL_VERTEX, p.TRAIL_FRAGMENT, p.TRAIL_BLOCK),
    }


#: The Python program keys, in the renderer's order (``extruded_bubble._PROGRAMS``).
PROGRAMS = ("backdrop", "probe_backdrop", "shafts", "blur", "shells", "clusters", "beads", "near", "near_clusters",
            "proxies", "specks", "trails")
#: The programs drawn into the transparency target (each ships a sorted pack).
TRANSPARENT = ("shells", "clusters", "beads", "trails")
#: The programs drawn into the probe's cube (one attachment: no emission output).
CUBE = ("probe_backdrop", "proxies")


def member_name(program: str, member: str) -> str:
    """A block member's name in a program's native text, the record or settings field that fills it: its program's
    prefix in the core's field-name form, lower case words joined by ``_`` (``member_name("shells", "uTime")`` ->
    ``shells_u_time``, Waveform's rule: ``waveform_native_names.member_name``), a core member keeping its own
    (``rendering.native.mode.MODE_CORE_MEMBERS``: the core fills it per pass)."""
    from rendering.native.mode import MODE_CORE_MEMBERS

    if member in MODE_CORE_MEMBERS:
        return member
    return f"{program}_{re.sub(r'(?<!^)(?=[A-Z])', '_', member).lower()}"


def block_layout(program: str):
    """The program's family block layout (``portable_family``'s)."""
    return _texts()[program][2]


def block_members(program: str) -> tuple[str, ...]:
    """The program's block members (unprefixed), in block order."""
    return tuple(name for name, _kind in block_layout(program).fields)


_SORTED_GLSL = """
layout(location = 0) out vec4 SceneColour;
void sceneTransparent(vec3 premultiplied, float alpha, float viewDepth) {
    SceneColour = vec4(premultiplied, alpha);
}
"""
_IN_OUT = re.compile(r"^((?:flat\s+|smooth\s+|noperspective\s+)?)(in|out)(\s+\w+\s+\w+(?:\s*\[\s*\d+\s*\])?\s*;)", re.M)


def _varyings(text: str, direction: str) -> list[str]:
    """The names of a stage's ``direction`` (``in``/``out``) variables in declaration order (attributes and
    fragment outputs included), with or without a location."""
    found = []
    for line in text.splitlines():
        match = re.match(r"^\s*(?:layout\s*\([^)]*\)\s*)?(?:flat\s+|smooth\s+|noperspective\s+)?(in|out)\s+\w+\s+(\w+)",
                         line)
        if match and match.group(1) == direction:
            found.append(match.group(2))
    return found


def _located(vertex: str, fragment: str) -> tuple[str, str]:
    """Both stages with every varying located: a vertex output keeps its location or takes the next free one, and
    the fragment input of that name takes the same; a fragment output without one is location 0 (each program here
    writes one such output)."""
    taken: dict[str, int] = {}
    for match in re.finditer(r"layout\s*\(\s*location\s*=\s*(\d+)\s*\)\s*(?:flat\s+|smooth\s+|noperspective\s+)?out"
                             r"\s+\w+\s+(\w+)", vertex):
        taken[match.group(2)] = int(match.group(1))
    following = max(taken.values(), default=-1) + 1

    def locate_out(match: re.Match) -> str:
        nonlocal following
        name = re.search(r"(\w+)\s*(?:\[\s*\d+\s*\])?\s*;", match.group(3)).group(1)
        if name not in taken:
            taken[name] = following
            following += 1 + (int(re.search(r"\[\s*(\d+)\s*\]", match.group(3)).group(1)) - 1
                              if "[" in match.group(3) else 0)
        return f"layout(location={taken[name]}) {match.group(1)}out{match.group(3)}"

    def located_vertex() -> str:
        return _IN_OUT.sub(lambda m: locate_out(m) if m.group(2) == "out" else m.group(0), vertex)

    vertex = located_vertex()

    def locate_in(match: re.Match) -> str:
        if match.group(2) == "out":
            return f"layout(location=0) {match.group(1)}out{match.group(3)}"
        name = re.search(r"(\w+)\s*(?:\[\s*\d+\s*\])?\s*;", match.group(3)).group(1)
        if name not in taken:
            raise ValueError(f"the fragment reads {name!r}, which its vertex stage does not write")
        return f"layout(location={taken[name]}) {match.group(1)}in{match.group(3)}"

    return vertex, _IN_OUT.sub(locate_in, fragment)


def _renamed(text: str, program: str) -> str:
    """The text with its program's member names: the version line, a ``#define`` per renamed member, the rest."""
    if not text.startswith(_VERSION):
        raise ValueError("an Extruded Bubble program's text starts with its version line")
    lines = [f"// Extruded Bubble (rendering/native/extruded_bubble_shaders.py): the {program} program, its block's "
             "members named for it (the arithmetic the Python text's)"]
    lines += [f"#define {member} {member_name(program, member)}" for member in block_members(program)
              if member_name(program, member) != member]
    return _VERSION + "\n".join(lines) + "\n" + text[len(_VERSION):]


#: An anonymous uniform or storage block (its declaration up to the members; the members; the closing brace).
_ANONYMOUS_BLOCK = re.compile(r"(layout\s*\([^)]*\)\s*(?:(?:readonly|writeonly|coherent|restrict)\s+)*"
                              r"(?:uniform|buffer)\s+(\w+)\s*\{)([^{}]*)\}\s*;")
_BLOCK_MEMBER = re.compile(r"(\w+)\s*(?:\[[^\]]*\])?\s*;")


def instance_name(block: str) -> str:
    """The instance name every native text gives ``block`` (the same in every stage)."""
    return f"blk_{block}"


def _instanced(text: str, program: str) -> str:
    """Every anonymous block of a native text given an instance name (``instance_name``), each member read through it.

    Qt's OpenGL translation flattens a uniform block to one uniform of the block's struct type and names an anonymous
    block's uniform by its SPIR-V id (``_449``). OpenGL links uniforms by name across the stages, so a vertex block and
    a fragment block of different types that happen to share an id fail to link: the trails program's pipeline could
    not be created (its vertex ``EbTrails`` and its fragment's ``SrpssConventions`` were both ``_449``, 28 Nov). A
    named instance is translated under its own name, the same in both stages. The core reads blocks by their block and
    member names, never the instance's (``mode_content.cpp``), and SPIR-V's arithmetic is unchanged.

    Each member is defined to its instance's member after the declaration (``#define trails_u_time
    blk_EbTrails.trails_u_time``): the declaration itself keeps the plain name, and ``_renamed``'s own define (``uTime``
    to ``trails_u_time``) still applies first, the preprocessor expanding the result once more."""
    own = set(block_members(program))

    def named(match: re.Match) -> str:
        head, block, body = match.group(1), match.group(2), match.group(3)
        instance = instance_name(block)
        defines = []
        for member in _BLOCK_MEMBER.findall(body):
            final = member_name(program, member) if member in own else member
            defines.append(f"#define {final} {instance}.{final}")
        return f"{head}{body}}} {instance};\n" + "\n".join(defines)

    return _ANONYMOUS_BLOCK.sub(named, text)


def sorted_text(fragment: str) -> str:
    """A transparent fragment's sorted pack text: ``SCENE_OIT_GLSL`` replaced by ``_SORTED_GLSL``, its emission moved
    to location 1 and its sphere depth (``gl_FragDepth``) left out, nothing else changed. The core's sorted pass never
    writes depth; the depth test it keeps decides nothing either way, since nothing before the glass writes the scene's
    depth (the backdrop and the specks draw with it off, as ``extruded_bubble_program`` declares), so every fragment in
    the frustum passes against the cleared far plane whichever depth it carries."""
    from rendering.quick.scene3d.target import SCENE_OIT_GLSL

    emission = "layout(location=2) out vec4 Emission;"
    if fragment.count(SCENE_OIT_GLSL) != 1 or fragment.count(emission) != 1:
        raise ValueError("a transparent program's fragment holds SCENE_OIT_GLSL once and its emission at location 2")
    text = fragment.replace(SCENE_OIT_GLSL, _SORTED_GLSL).replace(emission, "layout(location=1) out vec4 Emission;")
    return _FRAG_DEPTH.sub("", text)


#: A sphere depth write (one statement on its own line), left out of the sorted packs.
_FRAG_DEPTH = re.compile(r"^[ \t]*gl_FragDepth = [^;\n]*;[ \t]*\n", re.M)


def unemitted_text(fragment: str) -> str:
    """A fragment drawn into one attachment: its emission output a plain variable (written, never stored)."""
    emission = "layout(location=1) out vec4 Emission;"
    if fragment.count(emission) != 1:
        raise ValueError("the fragment declares its emission at location 1 once")
    return fragment.replace(emission, "vec4 Emission;")


def shader_files() -> dict[str, str]:
    """Every native pack's source name (``eb_<program>.vert`` / ``.frag``, ``eb_<program>_sorted.frag``) and text."""
    files: dict[str, str] = {}
    for program, (vertex, fragment, _layout) in _texts().items():
        if program in CUBE and "layout(location=1) out vec4 Emission;" in fragment:
            fragment = unemitted_text(fragment)
        vertex, located = _located(vertex, fragment)
        files[f"eb_{program}.vert"] = _instanced(_renamed(vertex, program), program)
        files[f"eb_{program}.frag"] = _instanced(_renamed(located, program), program)
        if program in TRANSPARENT:
            files[f"eb_{program}_sorted.frag"] = _instanced(
                _renamed(_located(vertex, sorted_text(fragment))[1], program), program)
    from rendering.native.extruded_bubble_drift import compute_texts

    files.update(compute_texts())       # the drift entries (eb_drift_*.comp)
    return files


#: Where the packs are committed (beside nothing: baked from ``shader_files``' texts).
PACK_FOLDER = ("widgets", "spotify_visualizer", "shaders", "extruded_bubble")


def pack(name: str) -> bytes:
    """A baked pack (``<source name>.qsb``) of ``PACK_FOLDER``; ``tools/eb_native_shaders.py --write`` bakes them."""
    from pathlib import Path

    path = Path(__file__).resolve().parents[2].joinpath(*PACK_FOLDER, f"{name}.qsb")
    if not path.is_file():
        raise FileNotFoundError(f"{path.name} is missing: run tools/eb_native_shaders.py --write")
    return path.read_bytes()


__all__ = ["CUBE", "PACK_FOLDER", "PROGRAMS", "TRANSPARENT", "block_layout", "block_members", "instance_name",
           "member_name", "pack", "shader_files", "sorted_text", "unemitted_text"]
