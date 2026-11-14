"""A mode's fragment shader takes every derivative in uniform control flow, before any lane can leave (N2.5 rule (b);
R-210).

A derivative after a non-uniform discard or return, or inside a branch the quad's lanes may take differently, is
undefined in GLSL: the quad's other lanes may be gone or elsewhere. OpenGL keeps a discarded lane running as a helper;
Vulkan's discard (SPIR-V OpKill) ends it, so Spectrum's rim feather, taken after its corner discards, differed by up to
15 levels beside every discarded pixel. The rule binds every 2D mode's shader (``_ALL_SHADER_FILES``: the native
route's ports take them as they are); the check itself takes any fragment source.

Textual and conservative. A *derivative* is ``fwidth``/``dFdx``/``dFdy`` in any precision, an implicit-LOD ``texture``
call, or a call to a function that takes one (transitively). An *exit* is a ``discard`` or ``return`` whose enclosing
conditions are not all uniform, or a call to a function that discards (transitively). A condition is uniform when it
reads only uniform-block members, loose uniforms, ``const`` names, literals, GLSL builtins, locals assigned once from
such an expression, and calls to functions computed from their arguments and uniforms alone; parameters, varyings, loop counters and anything else are not. In every function: no
derivative after its first exit, none inside a non-uniform ``if``/``else``/``while``/``switch`` body, none in any
``for``/``do`` body, none in a ``?:`` operand; and a function that takes a derivative never discards.
"""
from __future__ import annotations

import re

import pytest

_PRIMITIVE = re.compile(r"\b(?:(?:fwidth|dFdx|dFdy)(?:Fine|Coarse)?|texture(?:Offset|Proj|ProjOffset)?)\s*\(")
_DISCARD = re.compile(r"\bdiscard\b")
_EXIT_WORD = re.compile(r"\b(?:discard|return)\b")
_FUNCTION = re.compile(r"^[ \t]*[A-Za-z_]\w*[ \t]+([A-Za-z_]\w*)\s*\(([^;{)]*)\)\s*\{", re.MULTILINE)
_CONTROL = re.compile(r"\b(if|for|while|switch)\s*\(")
_IDENT = re.compile(r"(?<![.\w])[A-Za-z_]\w*")
_LOCAL = re.compile(r"\b(?:const\s+)?(?:float|int|uint|bool|[biu]?vec[234]|mat[234])\s+([A-Za-z_]\w*)\s*=(?!=)([^;]*);")
_DECLARED = re.compile(r"\b(?:float|int|uint|bool|[biu]?vec[234]|mat[234])\s+([A-Za-z_]\w*)")
_KEYWORDS = frozenset({"if", "for", "while", "switch", "return", "else", "do"})
# Statement words a uniform-pure function's body may hold besides its names.
_SYNTAX = frozenset({"if", "else", "for", "while", "return", "break", "continue", "const"})
# Builtins and constructors a uniform condition may use: they compute from their arguments alone.
_BUILTINS = frozenset({
    "true", "false", "abs", "sign", "floor", "ceil", "round", "trunc", "fract", "mod", "min", "max", "clamp", "mix",
    "step", "smoothstep", "sqrt", "inversesqrt", "pow", "exp", "exp2", "log", "log2", "sin", "cos", "tan", "length",
    "dot", "normalize", "any", "all", "not", "float", "int", "uint", "bool", "vec2", "vec3", "vec4", "ivec2", "ivec3",
    "ivec4", "uvec2", "uvec3", "uvec4", "bvec2", "bvec3", "bvec4", "mat2", "mat3", "mat4",
})


def _without_comments(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), source, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", source)


def _matching(text: str, index: int) -> int:
    """The index of the bracket closing the one at ``index`` (``(``, ``[`` or ``{``)."""
    opening = text[index]
    closing = {"(": ")", "[": "]", "{": "}"}[opening]
    depth = 0
    for position in range(index, len(text)):
        if text[position] == opening:
            depth += 1
        elif text[position] == closing:
            depth -= 1
            if depth == 0:
                return position
    return len(text) - 1


def _skip_space(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _word_at(text: str, index: int, word: str) -> bool:
    end = index + len(word)
    return text.startswith(word, index) and (end >= len(text) or not (text[end].isalnum() or text[end] == "_"))


def _statement_end(text: str, index: int) -> int:
    """The index just past the statement starting at ``index`` (a block, a control statement or a plain one)."""
    index = _skip_space(text, index)
    if index >= len(text):
        return len(text)
    if text[index] == "{":
        return _matching(text, index) + 1
    control = _CONTROL.match(text, index)
    if control is not None:
        end = _statement_end(text, _matching(text, control.end() - 1) + 1)
        follow = _skip_space(text, end)
        if control.group(1) == "if" and _word_at(text, follow, "else"):
            end = _statement_end(text, follow + 4)
        return end
    if _word_at(text, index, "do"):
        end = _statement_end(text, index + 2)
        return text.find(";", end) + 1 or len(text)
    depth = 0
    for position in range(index, len(text)):
        char = text[position]
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == ";" and depth == 0:
            return position + 1
    return len(text)


def _regions(body: str, uniform) -> list[tuple[int, int, bool]]:
    """(start, end, uniform) of every controlled body: an ``if``'s and its ``else``'s, a loop's, a ``switch``'s."""
    regions = []
    for control in _CONTROL.finditer(body):
        close = _matching(body, control.end() - 1)
        header = body[control.end():close]
        is_uniform = control.group(1) != "for" and uniform(header)
        end = _statement_end(body, close + 1)
        regions.append((close + 1, end, is_uniform))
        follow = _skip_space(body, end)
        if control.group(1) == "if" and _word_at(body, follow, "else"):
            regions.append((follow + 4, _statement_end(body, follow + 4), is_uniform))
    for loop in re.finditer(r"\bdo\b", body):
        regions.append((loop.end(), _statement_end(body, loop.end()), False))
    return regions


def _in_conditional_operand(body: str, position: int) -> bool:
    """Whether ``position`` lies in a ``?:`` operand of its statement."""
    start = max(body.rfind(";", 0, position), body.rfind("{", 0, position), body.rfind("}", 0, position)) + 1
    depth, open_ternaries = 0, []
    for char in body[start:position]:
        if char in "([":
            depth += 1
        elif char in ")]":
            depth -= 1
            open_ternaries = [level for level in open_ternaries if level <= depth]
        elif char == ",":
            open_ternaries = [level for level in open_ternaries if level < depth]
        elif char == "?":
            open_ternaries.append(depth)
    return bool(open_ternaries)


def _call_arguments(body: str, open_paren: int) -> list[str]:
    close = _matching(body, open_paren)
    arguments, depth, start = [], 0, open_paren + 1
    for position in range(open_paren + 1, close):
        char = body[position]
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth -= 1
        elif char == "," and depth == 0:
            arguments.append(body[start:position].strip())
            start = position + 1
    arguments.append(body[start:close].strip())
    return arguments


def _uniform_names(source: str) -> set[str]:
    names: set[str] = set()
    for block in re.finditer(r"\buniform\s+\w+\s*\{([^}]*)\}", source):
        names.update(re.findall(r"([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*;", block.group(1)))
    names.update(re.findall(r"\buniform\s+\w+\s+([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*;", source))
    names.update(re.findall(r"\bconst\s+\w+\s+([A-Za-z_]\w*)\s*(?:\[[^\]]*\])?\s*=", source))
    return names


def _pure_functions(bodies: dict[str, str], parameters: dict[str, str], uniform_names: set[str],
                    out_functions: set[str]) -> set[str]:
    """Functions whose result depends on their arguments and uniforms alone: their bodies name only their parameters,
    their own locals, uniforms, builtins and other such functions (no varying, no global variable, no derivative or
    texture read, no ``out`` parameter). A call to one with uniform arguments is uniform."""
    pure: set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, body in bodies.items():
            if name == "main" or name in pure or name in out_functions:
                continue
            own = set(_DECLARED.findall(parameters[name])) | set(_DECLARED.findall(body))
            if set(_IDENT.findall(body)) <= uniform_names | _BUILTINS | _SYNTAX | own | pure:
                pure.add(name)
                changed = True
    return pure


def _out_positions(parameters: dict[str, str]) -> dict[str, set[int]]:
    """Each function with ``out``/``inout`` parameters: their argument positions."""
    positions = {}
    for name, params in parameters.items():
        found = {index for index, param in enumerate(params.split(",")) if re.search(r"\b(?:out|inout)\b", param)}
        if found:
            positions[name] = found
    return positions


def _uniform_locals(body: str, uniform_names: set[str], out_positions: dict[str, set[int]]) -> set[str]:
    """Locals every assignment of which is a declaration from a uniform expression (never reassigned, incremented or
    passed to a function's ``out``/``inout`` parameter)."""
    declarations: dict[str, list[str]] = {}
    for match in _LOCAL.finditer(body):
        declarations.setdefault(match.group(1), []).append(match.group(2))
    candidates = {}
    for name, values in declarations.items():
        assignments = re.findall(rf"\b{name}\b(?:\s*(?:\.\w+|\[[^\]]*\]))*\s*(?:[-+*/%&|^]|<<|>>)?=(?!=)", body)
        stepped = re.search(rf"(?:\+\+|--)\s*\b{name}\b|\b{name}\b\s*(?:\+\+|--)", body)
        passed_out = any(
            re.match(rf"{name}\b", argument)
            for callee, positions in out_positions.items() for call in re.finditer(rf"\b{callee}\s*\(", body)
            for index, argument in enumerate(_call_arguments(body, call.end() - 1)) if index in positions)
        if len(assignments) == len(values) and stepped is None and not passed_out:
            candidates[name] = values
    uniform_locals: set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, values in candidates.items():
            if name in uniform_locals:
                continue
            known = uniform_names | uniform_locals | _BUILTINS
            if all(set(_IDENT.findall(value)) <= known for value in values):
                uniform_locals.add(name)
                changed = True
    return uniform_locals


def _functions(source: str) -> tuple[dict[str, str], dict[str, str]]:
    """Each function's body (between its braces) and its parameter list, by name."""
    bodies: dict[str, str] = {}
    parameters: dict[str, str] = {}
    for match in _FUNCTION.finditer(source):
        if match.group(1) in _KEYWORDS:
            continue
        start = match.end() - 1
        bodies[match.group(1)] = source[start + 1:_matching(source, start)]
        parameters[match.group(1)] = match.group(2)
    return bodies, parameters


def _closure(bodies: dict[str, str], seed: set[str]) -> set[str]:
    """``seed`` and every function that calls one of them, transitively."""
    found = set(seed)
    while True:
        callers = {name for name, body in bodies.items() if name not in found
                   and any(re.search(rf"\b{callee}\s*\(", body) for callee in found)}
        if not callers:
            return found
        found |= callers


def late_derivatives(source: str) -> list[str]:
    """Where ``source`` takes a derivative after an exit or in non-uniform control flow (empty when it never does)."""
    source = _without_comments(source)
    bodies, parameters = _functions(source)
    if "main" not in bodies:
        raise ValueError("no main() in the fragment source")
    helpers = {name: body for name, body in bodies.items() if name != "main"}
    deriving = _closure(helpers, {name for name, body in helpers.items() if _PRIMITIVE.search(body)})
    discarding = _closure(helpers, {name for name, body in helpers.items() if _DISCARD.search(body)})
    out_positions = _out_positions(parameters)
    uniform_names = _uniform_names(source)
    uniform_names |= _pure_functions(bodies, parameters, uniform_names, set(out_positions))
    problems = [f"{name}() takes a derivative and discards" for name in sorted(deriving & discarding)]
    for name in ["main", *sorted(deriving - discarding)]:
        body = bodies[name]
        known = uniform_names | _uniform_locals(body, uniform_names, out_positions) | _BUILTINS

        def uniform(expression: str, known: set[str] = known) -> bool:
            return set(_IDENT.findall(expression)) <= known

        regions = _regions(body, uniform)

        def uniform_at(position: int, body: str = body, regions=regions) -> bool:
            return (all(flag for start, end, flag in regions if start <= position < end)
                    and not _in_conditional_operand(body, position))

        exits = [(match.start(), match.group(0)) for match in _EXIT_WORD.finditer(body)
                 if not uniform_at(match.start())]
        for callee in discarding:
            exits += [(match.start(), f"{callee}() (it discards)")
                      for match in re.finditer(rf"\b{callee}\s*\(", body)]
        first_exit = min(exits) if exits else None
        calls = [match.start() for match in _PRIMITIVE.finditer(body)]
        for callee in deriving:
            calls += [match.start() for match in re.finditer(rf"\b{callee}\s*\(", body)]
        for position in sorted(calls):
            excerpt = body[position:position + 40].splitlines()[0]
            if first_exit is not None and position > first_exit[0]:
                problems.append(f"{name}() takes a derivative after its first {first_exit[1]}: {excerpt!r}")
            elif not uniform_at(position):
                problems.append(f"{name}() takes a derivative in non-uniform control flow: {excerpt!r}")
    return problems


def _mode_sources() -> list[tuple[str, str]]:
    from pathlib import Path

    from widgets.spotify_visualizer import shaders

    folder = Path(shaders.__file__).resolve().parent
    return [(mode, shaders.compose_shader_source(folder / filename))
            for mode, filename in sorted(shaders._ALL_SHADER_FILES.items())]


@pytest.mark.parametrize("mode, source", _mode_sources(), ids=lambda value: str(value)[:20])
def test_mode_shader_takes_derivatives_in_uniform_control_flow(mode: str, source: str) -> None:
    assert late_derivatives(source) == [], mode


def test_every_native_mode_is_bound() -> None:
    from rendering.quick.visualizer.native_route import NATIVE_MODE_IDS

    assert set(NATIVE_MODE_IDS) <= {mode for mode, _source in _mode_sources()}


def test_negative_controls_are_refused() -> None:
    fine = ("float feather(float d) { return fwidth(d); }\n"
            "void main() {\n    float f = feather(1.0);\n    if (f < 0.0) { discard; }\n    out_c = vec4(f);\n}\n")
    assert late_derivatives(fine) == []
    # A builtin after a discard; a deriving helper (through another helper) after a return; a helper that discards.
    builtin = fine.replace("    out_c = vec4(f);", "    out_c = vec4(dFdxFine(f));")
    assert len(late_derivatives(builtin)) == 1
    indirect = ("float feather(float d) { return fwidth(d); }\nfloat rim(float d) { return feather(d) * 2.0; }\n"
                "void main() {\n    if (u_x > 0.0) { out_c = vec4(0.0); return; }\n    out_c = vec4(rim(1.0));\n}\n")
    assert len(late_derivatives(indirect)) == 1
    discarding = ("float feather(float d) { if (d < 0.0) discard; return fwidthCoarse(d); }\n"
                  "void main() {\n    out_c = vec4(feather(1.0));\n}\n")
    assert late_derivatives(discarding) == ["feather() takes a derivative and discards"]
    # A derivative named only in a comment after the discard is no derivative.
    commented = fine.replace("    out_c = vec4(f);", "    out_c = vec4(f); // fwidth(f) would be late here")
    assert late_derivatives(commented) == []


_BLOCK = "layout(std140, binding = 18) uniform Draw {\n    int u_on;\n    float u_fade;\n};\n"


def test_the_audits_four_shapes_are_refused() -> None:
    """Audit 14 Nov (N25) L5: four shapes the first guard admitted (each checked against it: no finding)."""
    # A helper that returns early (on a parameter) before its derivative.
    early = (_BLOCK + "float feather(float d) {\n    if (d < 0.0) return 0.0;\n    return fwidth(d);\n}\n"
             "void main() {\n    out_c = vec4(feather(v_x));\n}\n")
    assert len(late_derivatives(early)) == 1
    # A derivative inside a branch the lanes may take differently.
    branch = (_BLOCK + "void main() {\n    float f = v_x;\n    if (f > 0.5) { f = fwidth(f); }\n    out_c = vec4(f);\n}\n")
    assert len(late_derivatives(branch)) == 1
    # A helper that discards (and takes no derivative), called before main's derivative.
    clip = (_BLOCK + "void clip(float d) {\n    if (d < 0.0) discard;\n}\n"
            "void main() {\n    clip(v_x);\n    out_c = vec4(fwidth(v_x));\n}\n")
    assert len(late_derivatives(clip)) == 1
    # An implicit-LOD texture read after a discard.
    sampled = (_BLOCK + "void main() {\n    if (v_x < 0.0) discard;\n    out_c = texture(u_tex, vec2(v_x));\n}\n")
    assert len(late_derivatives(sampled)) == 1


def test_uniform_control_flow_is_admitted() -> None:
    """The guard's positive side: what stays defined is not refused (otherwise the shapes above prove nothing)."""
    # A derivative under a branch on uniforms (directly, and through a local assigned once from them).
    uniform_branch = (_BLOCK + "void main() {\n    bool on = u_on == 1 && u_fade > 0.0;\n    float f = 0.0;\n"
                      "    if (u_on == 1) { f = fwidth(v_x); }\n    if (on) { f += texture(u_tex, vec2(v_x)).r; }\n"
                      "    out_c = vec4(f);\n}\n")
    assert late_derivatives(uniform_branch) == []
    # A discard on uniforms ends every lane of the quad together; an explicit-LOD read needs no derivative.
    uniform_exit = (_BLOCK + "void main() {\n    if (u_fade <= 0.0) { discard; }\n    out_c = vec4(fwidth(v_x));\n"
                    "    if (v_x < 0.0) discard;\n    out_c += textureLod(u_tex, vec2(v_x), 0.0);\n}\n")
    assert late_derivatives(uniform_exit) == []
    # The same branch on a local that is reassigned, or passed to an ``out`` parameter, is not uniform.
    reassigned = uniform_branch.replace("    float f = 0.0;\n", "    float f = 0.0;\n    on = v_x > 0.0;\n")
    assert len(late_derivatives(reassigned)) == 1
    written = ("void touch(out bool b) { b = v_x > 0.0; }\n"
               + uniform_branch.replace("    float f = 0.0;\n", "    float f = 0.0;\n    touch(on);\n"))
    assert len(late_derivatives(written)) == 1
    # A branch on a helper computed from uniforms alone is uniform; on one that reads a varying, it is not.
    pure = ("int pick(int which) {\n    if (which == 0) return u_on;\n    return 1;\n}\n"
            + _BLOCK + "void main() {\n    float f = 0.0;\n    if (pick(u_on) != 0) { f = fwidth(v_x); }\n"
            "    out_c = vec4(f);\n}\n")
    assert late_derivatives(pure) == []
    assert len(late_derivatives(pure.replace("return 1;", "return int(v_x);"))) == 1
