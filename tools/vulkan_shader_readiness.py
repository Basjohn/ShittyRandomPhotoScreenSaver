"""Vulkan port readiness (port-readiness rule 5): does every GLSL compute shader compile with Qt's ``qsb`` for every
backend it targets?

The native render core (P3) runs on Qt's RHI, where shaders must be Vulkan GLSL (no loose uniforms outside a block,
explicit set/binding) that ``qsb`` turns into SPIR-V and, through SPIRV-Cross, GLSL (430 and 310 es), HLSL (SM 5.0)
and MSL (1.2). Today's compute shaders are OpenGL GLSL 460 strings in Python modules. This tool discovers every
product module whose text holds a compute shader (``local_size_x``; never a fixed list), takes each module-level
string that is one (``#version`` + ``local_size_x``), compiles it with PySide6's ``qsb`` for all those targets, and
reports which compile and the first error of each that does not. Read-only: writes only to ``--out``, inside the
evidence layout (``tools/artifact_paths.py``).

    python tools/vulkan_shader_readiness.py --out .artifacts/evidence/architecture/vulkan_readiness/<YYYYMMDD>_<label>
"""
from __future__ import annotations

import argparse
import functools
import importlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import artifact_paths  # noqa: E402

# Where product shader sources live (tools, tests and labs are not the product).
SOURCE_PACKAGES = ("core", "engine", "rendering", "ui", "widgets")
# Every backend qsb bakes a compute shader for: SPIR-V always, then GLSL 430 / ES 3.1, HLSL SM 5.0 and MSL 1.2.
QSB_TARGETS = ("--glsl", "430,310 es", "--hlsl", "50", "--msl", "12")


@functools.lru_cache(maxsize=1)
def compute_modules() -> tuple[str, ...]:
    """Every product module whose source text holds a compute shader, discovered by scanning, never listed."""
    found = []
    for package in SOURCE_PACKAGES:
        for path in sorted((ROOT / package).rglob("*.py")):
            if "local_size_x" in path.read_text(encoding="utf-8", errors="ignore"):
                found.append(".".join(path.relative_to(ROOT).with_suffix("").parts))
    return tuple(found)


def qsb_command(qsb: Path, source: Path, output: Path) -> list[str]:
    return [str(qsb), *QSB_TARGETS, str(source), "-o", str(output)]


def _qsb() -> Path:
    import PySide6
    return Path(PySide6.__file__).parent / "qsb.exe"


def _compute_sources(module_name: str) -> dict[str, str]:
    module = importlib.import_module(module_name)
    found = {}
    for name, value in vars(module).items():
        if isinstance(value, str) and "#version" in value and "local_size_x" in value:
            found[name] = value
    return found


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=artifact_paths.evidence_arg, required=True)
    args = parser.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    qsb = _qsb()
    rows = []
    for module_name in compute_modules():
        for name, source in sorted(_compute_sources(module_name).items()):
            ok, first_error = compile_source(qsb, source, out / f"{module_name.rsplit('.', 1)[-1]}__{name}.comp")
            rows.append({"module": module_name, "shader": name, "compiles": ok, "error": first_error})
            print(f"{'OK  ' if ok else 'FAIL'} {module_name}.{name}  {first_error}", flush=True)
    (out / "vulkan_shader_readiness.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"{sum(r['compiles'] for r in rows)}/{len(rows)} compute shaders compile for every qsb target", flush=True)
    return 0


def compile_source(qsb: Path, source: str, path: Path) -> tuple[bool, str]:
    """Bake ``source`` (written to ``path``, a .comp) for every target; (ok, the first error line when not)."""
    path.write_text(source, encoding="utf-8")
    output = path.with_suffix(".comp.qsb")
    result = subprocess.run(qsb_command(qsb, path, output), capture_output=True, text=True, timeout=120)
    text = (result.stdout + result.stderr).strip()
    ok = result.returncode == 0 and output.exists() and "failed" not in text.lower()
    lines = text.splitlines()
    first = next((line for line in lines if "ERROR" in line or "failed" in line.lower()), lines[0] if lines else "")
    return ok, "" if ok else first


if __name__ == "__main__":
    raise SystemExit(main())
