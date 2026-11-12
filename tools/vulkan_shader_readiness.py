"""Vulkan port readiness (port-readiness rule 5): does every GLSL shader the product renders with compile with Qt's
``qsb`` for every backend it targets?

The native render core (P3) runs on Qt's RHI, where shaders must be Vulkan GLSL (no loose uniforms outside a block,
explicit set/binding and in/out locations) that ``qsb`` turns into SPIR-V and, through SPIRV-Cross, GLSL 430, HLSL
(SM 5.0) and MSL (1.2): the shipped backends' targets (lead's decision, 12 Nov 2026). GLSL ES is not baked: no backend
we ship loads it.

Every source is discovered, never listed (N1.3):

- shader files (``.vert``, ``.frag``, ``.geom``, ``.comp``) under the product packages, local ``#include`` lines
  expanded the way the 2D modes' loader expands them;
- every module-level string of a product module that is a whole shader (starts with ``#version`` and has a
  ``main``), also inside module-level tuples, lists and dicts, attributed to the module that assigns it (an imported
  name is its owner's);
- class attributes and properties of classes that hold one (the transition program classes' ``vertex_source`` /
  ``fragment_source``), read on a bare instance;
- composed sources: a *composer* is a module-level function that builds a shader (a ``#version`` literal, a
  module-level whole or partial shader it reads, or another composer it calls). Every call of a composer outside
  module level and outside another composer is resolved from the caller's names (a constant, a module-level name, a
  parameter's default) and evaluated, so the population count/scatter sources, the composed fog medium program and the
  fog march are checked with the product's own hooks. A call whose arguments cannot be resolved is reported (and
  fails the test); a call forwarding its caller's parameters is the caller's composition and is resolved at the
  caller's own call sites.

Each source's stage comes from its text (compute: ``local_size_x``; geometry: ``EmitVertex``; vertex: writes
``gl_Position``; otherwise fragment), and the source is baked by ``qsb`` for all targets. The report lists pass or
fail per source with its first error, every error line, and a cause. Read-only: writes only to ``--out``, inside the
evidence layout (``tools/artifact_paths.py``).

    python tools/vulkan_shader_readiness.py --out .artifacts/evidence/native_core/<topic>/<YYYYMMDD>_<label>
"""
from __future__ import annotations

import argparse
import ast
import functools
import importlib
import inspect
import itertools
import json
import re
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import artifact_paths  # noqa: E402

# Where product shader sources live (tools, tests and labs are not the product).
SOURCE_PACKAGES = ("core", "engine", "rendering", "ui", "widgets")
# The shipped backends' targets: SPIR-V always (Vulkan), then GLSL 430 (OpenGL), HLSL SM 5.0 (D3D) and MSL 1.2
# (Metal). GLSL ES is left out on purpose: nothing loads it.
QSB_TARGETS = ("--glsl", "430", "--hlsl", "50", "--msl", "12")
SHADER_SUFFIXES = (".vert", ".frag", ".geom", ".comp")

_MAIN = re.compile(r"\bvoid\s+main\s*\(")
_WRITES_POSITION = re.compile(r"\bgl_Position\b(?:\.\w+)?\s*=")
_EMITS = re.compile(r"\bEmitVertex\s*\(")


@dataclass(frozen=True)
class ShaderSource:
    key: str      # stable identity: "<module>.<NAME>", "<module>.<Class>.<attr>", "<module>.<composer>(<args>)", a path
    stage: str    # "vert", "frag", "geom" or "comp"
    text: str
    module: str   # the owning module (dotted) or the file's repository path


def qsb_targets(*, glsl: str = "430") -> tuple[str, ...]:
    """The required target arguments with another ``--glsl`` list (only tests use it, to show a target that would
    reject a construct is detected)."""
    return ("--glsl", glsl, *QSB_TARGETS[2:])


def stage_of(text: str) -> str:
    if "local_size_x" in text:
        return "comp"
    if _EMITS.search(text):
        return "geom"
    if _WRITES_POSITION.search(text):
        return "vert"
    return "frag"


def is_whole_shader(value: object) -> bool:
    return isinstance(value, str) and value.lstrip().startswith("#version") and bool(_MAIN.search(value))


def _is_shader_text(value: object) -> bool:
    return isinstance(value, str) and "#version" in value


# ---- discovery -----------------------------------------------------------------------------------------------------

def _python_files() -> list[Path]:
    files = []
    for package in SOURCE_PACKAGES:
        files.extend(sorted((ROOT / package).rglob("*.py")))
    return files


def _module_name(path: Path) -> str:
    parts = path.relative_to(ROOT).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


@functools.lru_cache(maxsize=1)
def _candidate_modules() -> tuple[tuple[str, Path], ...]:
    """Modules that can hold or compose a shader: their text has a ``#version`` or a GLSL ``main`` or calls a name
    that a composer may have (resolved later); every module of ``rendering`` is a candidate so a module that only
    composes imported pieces is not missed."""
    found = []
    for path in _python_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if path.relative_to(ROOT).parts[0] == "rendering" or "#version" in text or _MAIN.search(text):
            found.append((_module_name(path), path))
    return tuple(found)


@functools.lru_cache(maxsize=None)
def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _top_level_names(tree: ast.Module) -> set[str]:
    names = set()
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(
            node, (ast.AnnAssign, ast.AugAssign)) else []
        for target in targets:
            for leaf in ast.walk(target):
                if isinstance(leaf, ast.Name):
                    names.add(leaf.id)
    return names


def _import(module_name: str):
    return importlib.import_module(module_name)


def _nested(prefix: str, value, depth: int = 0):
    """(key, text) for every whole shader in ``value`` (a string, or a tuple/list/dict holding them)."""
    if is_whole_shader(value):
        yield prefix, value
    elif depth < 3 and isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            if (isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str)
                    and is_whole_shader(item[1])):
                yield f"{prefix}[{item[0]}]", item[1]
            else:
                yield from _nested(f"{prefix}[{index}]", item, depth + 1)
    elif depth < 3 and isinstance(value, dict):
        for index, (name, item) in enumerate(value.items()):
            label = name if isinstance(name, (str, int)) and len(str(name)) <= 48 and "\n" not in str(name) else index
            yield from _nested(f"{prefix}[{label}]", item, depth + 1)


def _file_sources() -> list[ShaderSource]:
    from widgets.spotify_visualizer.shaders import _load_shader_source
    found = []
    for package in SOURCE_PACKAGES:
        for path in sorted((ROOT / package).rglob("*")):
            if path.suffix not in SHADER_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8")
            if "#include" in text and path.parent.name == "shaders":
                text = _load_shader_source(path)
            relative = path.relative_to(ROOT).as_posix()
            found.append(ShaderSource(relative, path.suffix[1:], text, relative))
    return found


def _module_sources(module_name: str, path: Path) -> list[ShaderSource]:
    module = _import(module_name)
    owned = _top_level_names(_tree(path))
    found = []
    for name, value in vars(module).items():
        if name in owned:
            for key, text in _nested(f"{module_name}.{name}", value):
                found.append(ShaderSource(key, stage_of(text), text, module_name))
        if isinstance(value, type) and value.__module__ == module_name:
            found.extend(_class_sources(module_name, value))
    return found


def _class_sources(module_name: str, cls: type) -> list[ShaderSource]:
    found = []
    for name, value in vars(cls).items():
        if isinstance(value, property):
            try:
                value = value.fget(cls.__new__(cls))
            except Exception:
                continue
        for key, text in _nested(f"{module_name}.{cls.__name__}.{name}", value):
            found.append(ShaderSource(key, stage_of(text), text, module_name))
    return found


@dataclass(frozen=True)
class CallSite:
    caller: str        # "<module>:<line>"
    composer: str      # "<module>.<function>"
    arguments: str     # the call's argument text
    status: str        # "resolved", "forwarded" or "unresolved: <why>"


def _composers() -> dict[object, str]:
    """{function object: "<module>.<name>"} for every module-level function that builds a shader."""
    functions = {}
    reads = {}
    for module_name, path in _candidate_modules():
        module = _import(module_name)
        for node in _tree(path).body:
            if not isinstance(node, ast.FunctionDef):
                continue
            function = getattr(module, node.name, None)
            if not callable(function):
                continue
            literal, names = False, set()
            for leaf in ast.walk(node):
                if isinstance(leaf, ast.Constant) and _is_shader_text(leaf.value):
                    literal = True
                elif isinstance(leaf, ast.Name):
                    names.add(leaf.id)
            builds = literal or any(_is_shader_text(getattr(module, name, None)) for name in names)
            functions[function] = f"{module_name}.{node.name}"
            reads[function] = (builds, [value for value in (getattr(module, name, None) for name in names)
                                        if callable(value)])
    composers = {function for function, (builds, _) in reads.items() if builds}
    changed = True
    while changed:
        changed = False
        for function, (_, called) in reads.items():
            if function not in composers and any(_hashable(callee) and callee in composers for callee in called):
                composers.add(function)
                changed = True
    return {function: functions[function] for function in composers}


def _hashable(value) -> bool:
    try:
        hash(value)
    except TypeError:
        return False
    return True


_UNRESOLVED = object()
_FORWARDED = object()


def _resolve(node: ast.AST, module, scope: ast.FunctionDef | None):
    """The value of a call argument from the caller's names, ``_UNRESOLVED``, or ``_FORWARDED`` (a parameter of the
    caller without a default)."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if scope is not None:
            arguments = scope.args
            positional = arguments.posonlyargs + arguments.args
            defaults = dict(zip([a.arg for a in positional][len(positional) - len(arguments.defaults):],
                                arguments.defaults))
            defaults.update({a.arg: d for a, d in zip(arguments.kwonlyargs, arguments.kw_defaults) if d is not None})
            parameters = {a.arg for a in positional + arguments.kwonlyargs}
            if node.id in parameters:
                return _resolve(defaults[node.id], module, None) if node.id in defaults else _FORWARDED
            for leaf in ast.walk(scope):    # a local assigned in the caller is not a module-level name
                if isinstance(leaf, ast.Name) and isinstance(leaf.ctx, ast.Store) and leaf.id == node.id:
                    return _UNRESOLVED
        return getattr(module, node.id, _UNRESOLVED)
    if isinstance(node, ast.Attribute):
        owner = _resolve(node.value, module, scope)
        if owner is _UNRESOLVED or owner is _FORWARDED:
            return owner
        return getattr(owner, node.attr, _UNRESOLVED)
    return _UNRESOLVED


def _call_text(node: ast.Call) -> str:
    return ", ".join([ast.unparse(a) for a in node.args]
                     + [f"{k.arg}={ast.unparse(k.value)}" for k in node.keywords if k.arg])


def _sweepable(function) -> bool:
    """A composer whose parameters are all flags and counts (``bool``/``int``): it selects among sources, so an
    unresolved call is covered by evaluating it over its whole small domain."""
    try:
        parameters = inspect.signature(function).parameters.values()
    except (TypeError, ValueError):
        return False
    return bool(parameters) and all(p.annotation in ("bool", "int", bool, int) for p in parameters)


def _sweep(function) -> list:
    parameters = list(inspect.signature(function).parameters.values())
    domains = [(False, True) if p.annotation in ("bool", bool) else (0, 1, 4) for p in parameters]
    results = []
    for values in itertools.product(*domains):
        try:
            results.append(function(**{p.name: v for p, v in zip(parameters, values)}))
        except Exception:
            continue    # a combination the composer refuses is not a program it draws with
    return results


def _bind(scope: ast.FunctionDef, call: ast.Call, module, caller_scope) -> dict | None:
    """``__init__``'s parameters (without self) bound from a constructor call, or None when one cannot be resolved."""
    arguments = scope.args
    names = [a.arg for a in (arguments.posonlyargs + arguments.args)[1:]]
    bound = {}
    defaults = dict(zip(names[len(names) - len(arguments.defaults):], arguments.defaults))
    for name, node in zip(names, call.args):
        bound[name] = _resolve(node, module, caller_scope)
    for keyword in call.keywords:
        if keyword.arg:
            bound[keyword.arg] = _resolve(keyword.value, module, caller_scope)
    for name in names:
        if name not in bound and name in defaults:
            bound[name] = ast.literal_eval(defaults[name])
    if any(value is _UNRESOLVED or value is _FORWARDED for value in bound.values()):
        return None
    return bound


def _composed_sources() -> tuple[list[ShaderSource], list[CallSite]]:
    composers = _composers()
    found, sites = [], []
    forwarded_constructors = []    # (class, __init__ node, composer, composer call node, module, owner name)

    def emit(prefix, result):
        owner = prefix.split("(", 1)[0].rsplit(".", 1)[0]
        for key, source in _nested(prefix, result):
            found.append(ShaderSource(key, stage_of(source), source, owner))

    for module_name, path in _candidate_modules():
        module = _import(module_name)
        tree = _tree(path)
        scopes, classes = {}, {}
        for top in tree.body:
            if isinstance(top, ast.ClassDef):
                for member in top.body:
                    if isinstance(member, ast.FunctionDef):
                        classes[member] = top
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for leaf in ast.walk(node):
                    if isinstance(leaf, ast.Call):
                        scopes.setdefault(leaf, node)    # walk order: the outermost function first
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            scope = scopes.get(node)
            if scope is None:
                continue     # a module-level composition: its result is a module-level name, found above
            function = _resolve(node.func, module, None)
            if not _hashable(function) or function not in composers:
                continue
            outer = getattr(module, scope.name, None)
            if _hashable(outer) and outer in composers:
                continue     # composed inside another composer: checked through that composer's call sites
            values = [_resolve(argument, module, scope) for argument in node.args]
            keywords = {k.arg: _resolve(k.value, module, scope) for k in node.keywords if k.arg}
            text = _call_text(node)
            caller, name = f"{module_name}:{node.lineno}", composers[function]
            every = values + list(keywords.values())
            complete = len(keywords) == len(node.keywords)
            if (not complete or any(value is _FORWARDED or value is _UNRESOLVED for value in every)) \
                    and _sweepable(function):
                sites.append(CallSite(caller, name, text, "swept"))
                emit(f"{name}(*)", _sweep(function))
                continue
            if any(value is _FORWARDED for value in every):
                owner_class = classes.get(scope)
                if scope.name == "__init__" and owner_class is not None:
                    forwarded_constructors.append((getattr(module, owner_class.name), scope, function, node, module,
                                                   name, f"{module_name}.{owner_class.name}"))
                    sites.append(CallSite(caller, name, text, f"forwarded: {owner_class.name}(...)"))
                else:
                    sites.append(CallSite(caller, name, text, "forwarded"))
                continue
            if any(value is _UNRESOLVED for value in every) or not complete:
                sites.append(CallSite(caller, name, text, "unresolved: an argument is not a constant, a module-level "
                                                          "name or a parameter default"))
                continue
            sites.append(CallSite(caller, name, text, "resolved"))
            emit(f"{name}({text})", function(*values, **keywords))

    # A composition forwarded from a constructor's parameters is resolved at the constructor's own call sites.
    for cls, init, function, call, defining, name, class_name in forwarded_constructors:
        for module_name, path in _candidate_modules():
            module = _import(module_name)
            tree = _tree(path)
            enclosing = {}
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for leaf in ast.walk(node):
                        if isinstance(leaf, ast.Call):
                            enclosing.setdefault(leaf, node)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or _resolve(node.func, module, None) is not cls:
                    continue
                caller = f"{module_name}:{node.lineno}"
                bound = _bind(init, node, module, enclosing.get(node))
                if bound is None:
                    sites.append(CallSite(caller, class_name, _call_text(node),
                                          "unresolved: a constructor argument cannot be resolved"))
                    continue
                values = [bound[a.id] if isinstance(a, ast.Name) and a.id in bound else _resolve(a, defining, None)
                          for a in call.args]
                sites.append(CallSite(caller, class_name, _call_text(node), "resolved"))
                emit(f"{class_name}({_call_text(node)})", function(*values))
    return found, sites


@functools.lru_cache(maxsize=1)
def discover() -> tuple[tuple[ShaderSource, ...], tuple[CallSite, ...]]:
    """Every distinct shader source (first identity wins for an identical text) and every composer call site."""
    sources = _file_sources()
    for module_name, path in _candidate_modules():
        sources.extend(_module_sources(module_name, path))
    composed, sites = _composed_sources()
    sources.extend(composed)
    unique, seen = [], set()
    for source in sources:
        if source.text not in seen:
            seen.add(source.text)
            unique.append(source)
    return tuple(unique), tuple(sites)


def discover_sources() -> tuple[ShaderSource, ...]:
    return discover()[0]


# ---- the N1 compute rule's original API (compute sources only) -------------------------------------------------------

@functools.lru_cache(maxsize=1)
def compute_modules() -> tuple[str, ...]:
    """Every product module that holds a compute source (discovered by scanning, never listed)."""
    return tuple(sorted({source.module for source in discover_sources()
                         if source.stage == "comp" and "/" not in source.module}))


def _compute_sources(module_name: str) -> dict[str, str]:
    return {source.key.rsplit(".", 1)[-1] if source.key.startswith(module_name + ".") else source.key: source.text
            for source in discover_sources() if source.stage == "comp" and source.module == module_name}


# ---- compiling -----------------------------------------------------------------------------------------------------

def qsb_command(qsb: Path, source: Path, output: Path, targets: tuple[str, ...] = QSB_TARGETS) -> list[str]:
    return [str(qsb), *targets, str(source), "-o", str(output)]


def _qsb() -> Path:
    import PySide6
    return Path(PySide6.__file__).parent / "qsb.exe"


def bake(qsb: Path, source: str, path: Path, targets: tuple[str, ...] = QSB_TARGETS) -> tuple[bool, list[str]]:
    """Bake ``source`` (written to ``path``, whose suffix is the stage) for every target; (ok, its error lines)."""
    path.write_text(source, encoding="utf-8")
    output = path.with_name(path.name + ".qsb")
    result = subprocess.run(qsb_command(qsb, path, output, targets), capture_output=True, text=True, timeout=120)
    text = (result.stdout + result.stderr).strip()
    ok = result.returncode == 0 and output.exists() and "failed" not in text.lower()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    errors = [line for line in lines if "ERROR" in line or "failed" in line.lower() or "error" in line.lower()]
    return ok, ([] if ok else (errors or lines or ["qsb produced no output and no shader pack"]))


def compile_source(qsb: Path, source: str, path: Path,
                   targets: tuple[str, ...] = QSB_TARGETS) -> tuple[bool, str]:
    """Bake ``source`` for every target; (ok, the first error line when not)."""
    ok, errors = bake(qsb, source, path, targets)
    first = next((line for line in errors if "ERROR" in line), errors[0] if errors else "")
    return ok, "" if ok else first


# ---- the census --------------------------------------------------------------------------------------------------
# glslang stops at a source's first error, so the bake names one cause per failing source. The census also reads
# every source's text for each cause it holds (a source usually holds several), so the work left is counted whole.

# The first error's cause, from its text.
CAUSES = (
    ("loose uniforms", re.compile(r"non-opaque uniforms outside a block")),
    ("in/out location missing", re.compile(r"SPIR-V requires location for user input/output")),
    ("binding missing", re.compile(r"requires? layout\(binding")),
    ("OpenGL-only built-ins", re.compile(r"gl_(VertexID|InstanceID)|undeclared identifier.*Did you mean gl_|"
                                         r"not supported (for|with) (Vulkan|Metal|HLSL)", re.I)),
)


def cause_of(errors: list[str]) -> str:
    for line in errors:
        for name, pattern in CAUSES:
            if pattern.search(line):
                return name
    return "other"


_COMMENTS = re.compile(r"//[^\n]*|/\*.*?\*/", re.S)
_OPAQUE = r"(?:[iu]?sampler\w*|[iu]?image\w*|[iu]?texture\w*|atomic_uint)"
_LOOSE_UNIFORM = re.compile(rf"^\s*(?:layout\s*\([^)]*\)\s*)?uniform\s+(?:(?:lowp|mediump|highp)\s+)?"
                            rf"(?!{_OPAQUE}\b)\w+\s+\w+\s*(?:\[[^\]]*\]\s*)?[;=]", re.M)
_OPAQUE_UNIFORM = re.compile(rf"^\s*(layout\s*\([^)]*\)\s*)?(?:(?:readonly|writeonly|restrict|coherent|volatile)\s+)*"
                             rf"uniform\s+(?:(?:lowp|mediump|highp)\s+)?{_OPAQUE}\s+\w+", re.M)
_BLOCK = re.compile(r"^\s*(layout\s*\([^)]*\)\s*)?(?:readonly\s+|writeonly\s+|restrict\s+|coherent\s+)*"
                    r"(uniform|buffer)\s+\w+\s*\{", re.M)
_VARYING = re.compile(r"^\s*(layout\s*\([^)]*\)\s*)?(?:(?:flat|smooth|noperspective|centroid|sample)\s+)*"
                      r"(in|out)\s+\w+\s+\w+\s*(?:\[[^\]]*\]\s*)?;", re.M)
_BINDING = re.compile(r"\bbinding\s*=\s*(\d+)")
_GL_ONLY = re.compile(r"\bgl_(VertexID|InstanceID)\b")


def static_causes(text: str, stage: str) -> dict[str, int]:
    """What the text holds that Vulkan GLSL refuses or that depends on OpenGL's conventions, counted per cause.

    ``gl_FragCoord`` does not fail a bake: it is counted because N0.3 rule 2 changes what it means off OpenGL.
    A binding collision is two resources at one binding number: legal in OpenGL (samplers, uniform blocks, storage
    blocks and images each number their own bindings), one descriptor set slot in Vulkan."""
    code = _COMMENTS.sub("", text)
    found = {}
    loose = len(_LOOSE_UNIFORM.findall(code))
    if loose:
        found["loose uniforms"] = loose
    missing = [m for m in _OPAQUE_UNIFORM.finditer(code) if not m.group(1) or "binding" not in m.group(1)]
    missing += [m for m in _BLOCK.finditer(code) if not m.group(1) or "binding" not in m.group(1)]
    if missing:
        found["binding missing"] = len(missing)
    if stage in ("vert", "frag", "geom"):
        varyings = [m for m in _VARYING.finditer(code) if not m.group(1) or "location" not in m.group(1)]
        if varyings:
            found["in/out location missing"] = len(varyings)
    builtins = len(_GL_ONLY.findall(code)) + (1 if stage == "geom" else 0)
    if builtins:
        found["OpenGL-only built-ins"] = builtins
    numbers = [int(n) for declaration in (*_OPAQUE_UNIFORM.finditer(code), *_BLOCK.finditer(code))
               if declaration.group(1) for n in _BINDING.findall(declaration.group(1))]
    collisions = sum(count - 1 for count in _counts(numbers).values() if count > 1)
    if collisions:
        found["binding collisions"] = collisions
    fragcoord = len(re.findall(r"\bgl_FragCoord\b", code))
    if fragcoord:
        found["gl_FragCoord conventions"] = fragcoord
    return found


def _counts(values) -> dict:
    counts = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


# The groups of the ratchet, in N5's porting order: the scene substrate ports with N3 before the first mode, then the
# 3D modes, the 2D modes, the transitions, and the Quick hosts and materials. A module is assigned by the first rule
# whose prefix it starts with (dotted module names; shader files by their repository path).
GROUPS = (
    ("Shared scene substrate", ("rendering.gl_programs.scene3d", "rendering.quick.scene3d.target",
                                "rendering.quick.scene3d.post", "rendering.quick.scene3d.resources",
                                "rendering.quick.scene3d.frame", "rendering.quick.scene3d.environment")),
    ("Waveform Ribbon", ("rendering.gl_programs.waveform", "rendering.gl_programs.ribbon", "rendering.gl_programs.mist",
                         "rendering.gl_programs.fog_volume", "rendering.quick.scene3d.waveform",
                         "rendering.quick.scene3d.ribbon", "rendering.quick.scene3d.fog_volume",
                         "rendering.quick.scene3d.floor_give",
                         "rendering.quick.visualizer.implementations.waveform_ribbon")),
    ("Extruded Bubble", ("rendering.gl_programs.extruded_bubble", "rendering.gl_programs.scene3d_water",
                         "rendering.quick.scene3d.defocus", "rendering.quick.scene3d.probe",
                         "rendering.quick.visualizer.implementations.extruded_bubble")),
    ("Neon Lake", ("rendering.gl_programs.neon_lake", "rendering.gl_programs.shockwave_grid",
                   "rendering.quick.scene3d.shafts", "rendering.quick.visualizer.implementations.shockwave_grid")),
    ("Extruded Spectrum", ("rendering.gl_programs.extruded_spectrum",
                           "rendering.quick.visualizer.implementations.extruded_spectrum")),
    ("Sphere", ("rendering.quick.visualizer.implementations.sphere",)),
    ("2D modes", ("widgets/spotify_visualizer/", "widgets.spotify_visualizer",
                  "rendering.quick.visualizer.render_contract", "rendering.gl_programs.oscilloscope",
                  "rendering.quick.visualizer.implementations.")),
    ("Transitions", ("rendering.gl_programs.", "rendering.quick.transitions.", "rendering.quick.scene3d.")),
    ("Quick hosts and materials", ("rendering/quick/qml/", "rendering.quick.render.",
                                   "rendering.quick.visualizer.clip_host")),
)


def group_of(module: str) -> str:
    for name, prefixes in GROUPS:
        if module.startswith(prefixes):
            return name
    return "unassigned"


def check(sources, workdir: Path | None = None, qsb: Path | None = None, workers: int = 8) -> list[dict]:
    """Bake every source; one row per source (key, module, group, stage, compiles, error, errors, cause, holds)."""
    qsb = qsb or _qsb()
    if workdir is None:
        with tempfile.TemporaryDirectory(prefix="srpss_qsb_") as directory:
            return check(sources, Path(directory), qsb, workers)
    workdir.mkdir(parents=True, exist_ok=True)

    def one(indexed):
        index, source = indexed
        name = re.sub(r"[^A-Za-z0-9_]+", "_", source.key)[-80:]
        ok, errors = bake(qsb, source.text, workdir / f"{index:04d}_{name}.{source.stage}")
        first = next((line for line in errors if "ERROR" in line), errors[0] if errors else "")
        return {"key": source.key, "module": source.module, "group": group_of(source.module), "stage": source.stage,
                "compiles": ok, "error": "" if ok else first, "errors": errors[:12],
                "cause": "" if ok else cause_of(errors), "holds": static_causes(source.text, source.stage)}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, enumerate(sources)))


def census(rows: list[dict]) -> dict:
    """The counts the plan quotes: sources, passes, first-error causes, and sources holding each cause."""
    failing = [row for row in rows if not row["compiles"]]
    first = _counts(row["cause"] for row in failing)
    holding = {}
    for row in rows:
        for cause in row["holds"]:
            holding[cause] = holding.get(cause, 0) + 1
    groups = {}
    for row in failing:
        groups[row["group"]] = groups.get(row["group"], 0) + 1
    stages = {}
    for row in rows:
        passed, total = stages.get(row["stage"], (0, 0))
        stages[row["stage"]] = (passed + int(row["compiles"]), total + 1)
    return {"sources": len(rows), "pass": len(rows) - len(failing), "fail": len(failing),
            "first_error_cause": first, "sources_holding": holding, "failing_by_group": groups,
            "stages_pass_total": stages}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=artifact_paths.evidence_arg, required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sources, sites = discover()
    rows = check(sources)    # baked in a temporary folder: the packs are not evidence
    for row in rows:
        print(f"{'OK  ' if row['compiles'] else 'FAIL'} {row['stage']} {row['key']}  {row['error']}", flush=True)
    for site in sites:
        if site.status != "resolved":
            print(f"CALL {site.status}: {site.composer}({site.arguments}) at {site.caller}", flush=True)
    summary = census(rows)
    report = {"census": summary, "sources": rows, "call_sites": [asdict(site) for site in sites]}
    (out / "vulkan_shader_readiness.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
