"""A mode's fragment shader takes every derivative before its first discard or return (N2.5 rule (b); R-210).

A derivative after a non-uniform discard or return is undefined in GLSL: the quad's other lanes may be gone. OpenGL
keeps a discarded lane running as a helper; Vulkan's discard (SPIR-V OpKill) ends it, so Spectrum's rim feather,
taken after its corner discards, differed by up to 15 levels beside every discarded pixel. The rule binds every mode
the native route draws (``NATIVE_MODE_IDS``: a port admits a mode only once its shader passes); the check itself takes
any fragment source.

Textual and conservative: in ``main``, no derivative (``fwidth``/``dFdx``/``dFdy`` in any precision, or a call to a
function that takes one, transitively) after the first ``discard`` or ``return``; a function that takes one never
discards.
"""
from __future__ import annotations

import re

import pytest

_DERIVATIVE = re.compile(r"\b(?:fwidth|dFdx|dFdy)(?:Fine|Coarse)?\s*\(")
_EXIT = re.compile(r"\b(?:discard|return)\b")
_DISCARD = re.compile(r"\bdiscard\b")
_FUNCTION = re.compile(r"^[ \t]*[A-Za-z_]\w*[ \t]+([A-Za-z_]\w*)\s*\([^;{)]*\)\s*\{", re.MULTILINE)


def _without_comments(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), source, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", source)


def _functions(source: str) -> dict[str, str]:
    """Each function's body (between its braces), by name."""
    bodies: dict[str, str] = {}
    for match in _FUNCTION.finditer(source):
        depth, start = 0, match.end() - 1
        for index in range(start, len(source)):
            if source[index] == "{":
                depth += 1
            elif source[index] == "}":
                depth -= 1
                if depth == 0:
                    bodies[match.group(1)] = source[start + 1:index]
                    break
    return bodies


def late_derivatives(source: str) -> list[str]:
    """Where ``source`` takes a derivative after a discard or a return (empty when it never does)."""
    bodies = _functions(_without_comments(source))
    if "main" not in bodies:
        raise ValueError("no main() in the fragment source")
    deriving = {name for name, body in bodies.items() if name != "main" and _DERIVATIVE.search(body)}
    while True:
        callers = {name for name, body in bodies.items() if name != "main" and name not in deriving
                   and any(re.search(rf"\b{callee}\s*\(", body) for callee in deriving)}
        if not callers:
            break
        deriving |= callers
    problems = [f"{name}() takes a derivative and discards" for name in sorted(deriving)
                if _DISCARD.search(bodies[name])]
    main = bodies["main"]
    first_exit = _EXIT.search(main)
    if first_exit is not None:
        calls = [match.start() for match in _DERIVATIVE.finditer(main)]
        for name in deriving:
            calls += [match.start() for match in re.finditer(rf"\b{name}\s*\(", main)]
        late = sorted(position for position in calls if position > first_exit.start())
        problems += [f"main() takes a derivative after its first {first_exit.group(0)}: "
                     f"{main[position:position + 40].splitlines()[0]!r}" for position in late]
    return problems


def _native_mode_sources() -> list[tuple[str, str]]:
    from pathlib import Path

    from rendering.quick.visualizer.native_route import NATIVE_MODE_IDS
    from widgets.spotify_visualizer import shaders

    folder = Path(shaders.__file__).resolve().parent
    return [(mode, shaders.compose_shader_source(folder / shaders._ALL_SHADER_FILES[mode]))
            for mode in sorted(NATIVE_MODE_IDS)]


@pytest.mark.parametrize("mode, source", _native_mode_sources(), ids=lambda value: str(value)[:20])
def test_native_mode_shader_takes_derivatives_before_any_discard(mode: str, source: str) -> None:
    assert late_derivatives(source) == [], mode


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
