"""Vulkan port readiness (port-readiness rule 5): does every GLSL compute shader compile to SPIR-V with Qt's ``qsb``?

The native render core (P3) runs on Qt Quick's Vulkan RHI, where shaders must be Vulkan GLSL (no loose uniforms
outside a block, explicit set/binding). Today's compute shaders are OpenGL GLSL 460 strings in Python modules. This
tool finds every module-level string that is a compute shader (``#version`` + ``local_size_x``), compiles each with
PySide6's ``qsb`` (SPIR-V), and reports which compile and the first error of each that does not. Read-only: writes
only to ``--out``, inside the evidence layout (``tools/artifact_paths.py``).

    python tools/vulkan_shader_readiness.py --out .artifacts/evidence/architecture/vulkan_readiness/<YYYYMMDD>_<label>
"""
from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import artifact_paths  # noqa: E402

MODULES = (
    "rendering.gl_programs.fog_volume", "rendering.gl_programs.waveform_atmosphere",
    "rendering.gl_programs.waveform_floor_give", "rendering.quick.scene3d.edge_field",
    "rendering.quick.scene3d.motion", "rendering.quick.scene3d.population",
    "rendering.quick.scene3d.propagation_field",
    "rendering.quick.visualizer.implementations.extruded_bubble_drift_solver",
)


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
    for module_name in MODULES:
        for name, source in sorted(_compute_sources(module_name).items()):
            path = out / f"{module_name.rsplit('.', 1)[-1]}__{name}.comp"
            path.write_text(source, encoding="utf-8")
            result = subprocess.run([str(qsb), str(path), "-o", str(path) + ".qsb"], capture_output=True, text=True,
                                    timeout=120)
            text = (result.stdout + result.stderr).strip()
            ok = (path.with_suffix(".comp.qsb")).exists() and "failed" not in text.lower()
            first_error = next((line for line in text.splitlines() if "ERROR" in line), "") if not ok else ""
            rows.append({"module": module_name, "shader": name, "spirv": ok, "error": first_error})
            print(f"{'OK  ' if ok else 'FAIL'} {module_name}.{name}  {first_error}", flush=True)
    (out / "vulkan_shader_readiness.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"{sum(r['spirv'] for r in rows)}/{len(rows)} compute shaders compile to SPIR-V", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
