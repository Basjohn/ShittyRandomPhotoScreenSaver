"""Entry point for the operator's Nuitka probe of the P1 spike.

Agents never build frozen (Guardrails: no local frozen builds); the operator
builds and runs this with the commands in native/spike_p1/README.md. It runs
one part per invocation, offscreen, and writes JSON and PNGs to --out.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import PySide6.QtQuick  # noqa: F401  Qt's DLLs are loaded before the native module binds to them

import _srpss_native_spike as native
import run_spike


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--part", required=True, choices=("rhi", "hybrid", "quick"))
    parser.add_argument("--backend", choices=run_spike.BACKENDS, default="d3d11")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    info = native.runtime_info()
    if args.part == "rhi":
        from PySide6.QtGui import QGuiApplication

        app = QGuiApplication([sys.argv[0]])  # no window is created
        result = {"rhi": run_spike.run_rhi(native, args.out), "gil": run_spike.run_gil(native)}
        del app
        name = "frozen_rhi.json"
    else:
        result = run_spike.child_quick(native, args.part, args.backend, args.out)
        name = f"frozen_{args.part}_{args.backend}.json"
    result["runtime"] = info
    result["frozen"] = "__compiled__" in globals()
    (args.out / name).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
