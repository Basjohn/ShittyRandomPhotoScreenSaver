"""Portable programs (N1.6): an OpenGL program's sources rewritten into the Vulkan GLSL ``qsb`` bakes for every target.

``portable_program(vertex, fragments, block=..., samplers=...)`` takes sources written for OpenGL (loose uniforms,
samplers given units by ``glUniform1i``, varyings matched by name, ``gl_VertexID``) and returns the same sources with
only their declarations changed:

- every loose (non-opaque) uniform of every stage becomes a member of ONE std140 block, declared identically at the
  top of every stage at ``binding`` (the pass block, ``SCENE3D_PASS_BLOCK_BINDING``); the members keep their names, so
  no function body changes, and the returned ``Scene3DBlockLayout`` is what the owner packs (``pack_block``);
- every sampler takes ``layout(binding = N)`` from ``samplers`` (its OpenGL texture unit: one namespace per program,
  so the plan must keep samplers, storage buffers and blocks apart; a sampler missing from the plan is an error);
- the vertex stage's outputs take locations in declaration order, and each fragment's inputs the location of the
  vertex output of the same name (an unlocated fragment output is location 0);
- ``gl_VertexID`` / ``gl_InstanceID`` read ``srpssVertexIndex`` / ``srpssInstanceIndex``
  (``rendering.gl_programs.conventions.SRPSS_VERTEX_INDEX_GLSL``), OpenGL's meaning on every backend.

Arithmetic is untouched, so a converted program draws the same pixels in OpenGL when its owner packs the values it used
to set with ``glUniform*`` (proved per program by ``tools/conventions_identity.py``). Pure: strings only.
"""
from __future__ import annotations

import re
from typing import Mapping, Sequence

from rendering.gl_programs.conventions import SRPSS_VERTEX_INDEX_GLSL
from rendering.gl_programs.scene3d import SCENE3D_PASS_BLOCK_BINDING, Scene3DBlockLayout, _STD140, _std140_type

_OPAQUE = r"(?:[iu]?sampler\w*|[iu]?image\w*|atomic_uint)"
_LOOSE = re.compile(rf"^[ \t]*uniform[ \t]+(?:(?:lowp|mediump|highp)\s+)?(?!{_OPAQUE}\b)(\w+)[ \t]+(\w+)[ \t]*"
                    rf"(?:\[[ \t]*(\w+)[ \t]*\])?[ \t]*;", re.M)
_SAMPLER = re.compile(rf"^([ \t]*)(?:layout\s*\([^)]*\)\s*)?uniform([ \t]+{_OPAQUE}[ \t]+)(\w+)[ \t]*;", re.M)
_VARYING = re.compile(r"^([ \t]*)(?:layout\s*\(\s*location\s*=\s*\d+\s*\)\s*)?((?:(?:flat|smooth|noperspective|centroid)"
                      r"\s+)*)(in|out)([ \t]+)(\w+)[ \t]+(\w+)[ \t]*(\[[^\]]*\])?[ \t]*;", re.M)
_COMMENTS = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
_VERSION = re.compile(r"\A[ \t]*#version[^\n]*\n")
_SLOTS = {"mat4": 4, "mat3": 3, "mat2": 2}


def _const_int(source: str, name: str) -> int:
    match = re.search(rf"\bconst\s+int\s+{name}\s*=\s*(\d+)\s*;", source)
    if match is None:
        raise ValueError(f"array size {name} is not a constant integer of the source")
    return int(match.group(1))


def _strip_comments(source: str) -> str:
    """Comments blanked to the same length (so offsets stay valid and nothing inside a comment matches)."""
    return _COMMENTS.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), source)


def _loose_uniforms(source: str) -> list[tuple[tuple[int, int], str, str]]:
    """((start, end), name, std140 type) of each loose uniform declaration."""
    found = []
    for match in _LOOSE.finditer(_strip_comments(source)):
        kind, name, size = match.groups()
        if kind not in _STD140:
            raise ValueError(f"uniform {name}: type {kind} has no std140 layout here")
        if size is not None:
            kind = f"{kind}[{size if size.isdigit() else _const_int(source, size)}]"
        found.append((match.span(), name, kind))
    return found


def _after_version(source: str, text: str) -> str:
    match = _VERSION.match(source)
    if match is None:
        raise ValueError("a portable source starts with its #version line")
    return source[:match.end()] + text + source[match.end():]


def _replace_spans(source: str, edits: list[tuple[tuple[int, int], str]]) -> str:
    for (start, end), text in sorted(edits, reverse=True):
        source = source[:start] + text + source[end:]
    return source


def _bind_samplers(source: str, samplers: Mapping[str, int]) -> str:
    edits = []
    for match in _SAMPLER.finditer(_strip_comments(source)):
        name = match.group(3)
        if name not in samplers:
            raise ValueError(f"sampler {name} has no binding in the program's plan")
        edits.append((match.span(), f"{match.group(1)}layout(binding = {int(samplers[name])}) uniform"
                                    f"{source[match.start(2):match.end(2)]}{name};"))
    return _replace_spans(source, edits)


def _slots(kind: str, array: str | None) -> int:
    count = int(array.strip("[] ")) if array else 1
    return _SLOTS.get(kind, 1) * count


def _locate(source: str, direction: str, locations: Mapping[str, int] | None) -> tuple[str, dict[str, int]]:
    """Locations for the ``direction`` ("in"/"out") varyings of ``source``: from ``locations`` by name, or assigned in
    declaration order when it is None. Returns the source and the name -> location map it used."""
    edits, assigned, cursor = [], {}, 0
    for match in _VARYING.finditer(_strip_comments(source)):
        indent, qualifiers, way, _space, kind, name, array = match.groups()
        if way != direction:
            continue
        if locations is None:
            location, cursor = cursor, cursor + _slots(kind, array)
        elif name in locations:
            location = locations[name]
        else:
            raise ValueError(f"varying {name} has no location to match")
        assigned[name] = location
        edits.append((match.span(), f"{indent}layout(location = {location}) {qualifiers}{way} {kind} {name}"
                                    f"{array or ''};"))
    return _replace_spans(source, edits), assigned


def _vertex_index(source: str) -> str:
    replaced = re.sub(r"\bgl_VertexID\b", "srpssVertexIndex", source)
    replaced = re.sub(r"\bgl_InstanceID\b", "srpssInstanceIndex", replaced)
    return source if replaced == source else _after_version(replaced, SRPSS_VERTEX_INDEX_GLSL)


def portable_program(vertex, fragments: Sequence[str], *, block: str, samplers: Mapping[str, int],
                     binding: int = SCENE3D_PASS_BLOCK_BINDING):
    """(vertex, fragments, block layout) rewritten as the module notes say. ``vertex`` may be a tuple of vertex stages
    that declare the same outputs (variants drawn with the same fragments; returned as a tuple), or None to convert
    fragments alone (their inputs then keep the locations they declare). A compute source goes in ``fragments`` with
    ``vertex`` None. One block serves every stage given: each program of the family packs the same layout."""
    if isinstance(vertex, tuple):
        vertices = list(vertex)
        converted, layout = _convert(vertices + list(fragments), len(vertices), block, samplers, binding)
        return tuple(converted[:len(vertices)]), tuple(converted[len(vertices):]), layout
    converted, layout = _convert(([vertex] if vertex is not None else []) + list(fragments),
                                 1 if vertex is not None else 0, block, samplers, binding)
    if vertex is not None:
        return converted[0], tuple(converted[1:]), layout
    return None, tuple(converted), layout


def _convert(stages: list[str], vertices: int, block: str, samplers: Mapping[str, int], binding: int):
    fields: dict[str, str] = {}
    stripped = []
    for source in stages:
        edits = []
        for span, name, kind in _loose_uniforms(source):
            if fields.setdefault(name, kind) != kind:
                raise ValueError(f"uniform {name} is {fields[name]} in one stage and {kind} in another")
            edits.append((span, ""))
        stripped.append(_replace_spans(source, edits))
    layout = Scene3DBlockLayout.of(block, tuple(fields.items()))
    declaration = layout.glsl(binding) if fields else ""
    outputs = None
    converted = []
    for index, source in enumerate(stripped):
        source = _bind_samplers(source, samplers)
        if index < vertices:
            source, located = _locate(source, "out", None)
            if outputs is not None and located != outputs:
                raise ValueError("vertex variants of one family declare different outputs")
            outputs = located
        elif "local_size_x" not in source:
            source, _ = _locate(source, "in", outputs)
            outs = [m for m in _VARYING.finditer(_strip_comments(source)) if m.group(3) == "out"]
            unlocated = [m for m in outs if "location" not in source[m.start():m.end()]]
            if unlocated and len(outs) == 1:
                source, _ = _locate(source, "out", None)
            elif unlocated:
                raise ValueError("a fragment with several outputs states their locations")
        source = _after_version(source, declaration)
        converted.append(_vertex_index(source))
    return converted, layout


_BLOCK_DECLARATION = r"layout\s*\(\s*std140\s*,\s*binding\s*=\s*(\d+)\s*\)\s*uniform\s+{name}\s*\{{(.*?)\}}\s*;"
_MEMBER = re.compile(r"^\s*(\w+)\s+(\w+)\s*(?:\[\s*(\d+)\s*\])?\s*;", re.M)


def block_declaration(source: str, name: str) -> str:
    """The text of the std140 block ``name`` as ``source`` declares it (``layout(...) uniform name { ... };``), so a
    second stage can declare the very same block."""
    match = re.search(_BLOCK_DECLARATION.format(name=re.escape(name)), source, re.S)
    if match is None:
        raise ValueError(f"the source declares no std140 block {name} with a binding")
    return match.group(0) + "\n"


def block_layout_from_glsl(declaration: str) -> Scene3DBlockLayout:
    """The ``Scene3DBlockLayout`` of one std140 block declaration (its members in order; comments ignored), so an
    owner packs exactly what a shader file declares."""
    match = re.search(r"uniform\s+(\w+)\s*\{(.*?)\}", _strip_comments(declaration), re.S)
    if match is None:
        raise ValueError("not a uniform block declaration")
    fields = tuple((member, f"{kind}[{size}]" if size else kind)
                   for kind, member, size in _MEMBER.findall(match.group(2)))
    return Scene3DBlockLayout.of(match.group(1), fields)


def _element_components(element: str) -> int:
    return _STD140[element][1] // 4


def pack_block(layout: Scene3DBlockLayout, values: Mapping[str, object]) -> bytes:
    """``layout`` packed from the values an owner used to set with ``glUniform*``: by name, keys the block does not
    hold (sampler units) ignored, a member not given zero (as a never-set uniform reads), an array given flat (as
    ``glUniform4fv`` took it) or as one item per element."""
    packed = {}
    for field, kind in layout.fields:
        value = values.get(field)
        element, count, _alignment, _stride = _std140_type(kind)
        width = _element_components(element)
        if value is None:
            zero = 0 if element in ("int", "uint") else 0.0
            item = zero if width == 1 else (zero,) * width
            value = (item,) * count if "[" in kind else item
        elif "[" in kind and len(value) == count * width and width > 1 and not isinstance(value[0], (tuple, list)):
            value = tuple(tuple(value[i * width:(i + 1) * width]) for i in range(count))
        packed[field] = value
    return layout.pack(packed)


__all__ = ["block_declaration", "block_layout_from_glsl", "pack_block", "portable_program"]
