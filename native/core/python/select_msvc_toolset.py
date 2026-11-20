"""Pick the MSVC toolset the module may be compiled with, for build.cmd.

The module must never be linked by a toolset newer than the VC runtime of the Python that loads it: the runtime
check (`rendering/native/runtime_check.py`, `toolset_problems`) refuses that, because a newer compiler may import
runtime symbols an older runtime lacks. GitHub's runner image can move its default toolset ahead of the runner's
Python (21 Nov 2026: toolset 14.52 against Python 3.14's VCRUNTIME140 14.51). So build.cmd asks this script which
installed toolset to select: the newest one in `<VS root>\\VC\\Tools\\MSVC` whose major.minor does not exceed the
target Python's `vcruntime140.dll`.

    python select_msvc_toolset.py <VS root> <repo .venv dir>

Prints the toolset's full version (for `vcvars64.bat -vcvars_ver=`) and exits 0; prints the reason to stderr and exits
1 when no installed toolset is old enough.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from rendering.native.runtime_check import file_version  # noqa: E402


def python_runtime(venv: Path) -> Path:
    """The vcruntime140.dll the venv's interpreter loads: the one beside its base installation."""
    base = subprocess.run([str(venv / "Scripts" / "python.exe"), "-c", "import sys; print(sys.base_prefix)"],
                          capture_output=True, text=True, check=True).stdout.strip()
    return Path(base) / "vcruntime140.dll"


def installed_toolsets(vs_root: Path) -> list[tuple[tuple[int, ...], str]]:
    root = vs_root / "VC" / "Tools" / "MSVC"
    found = []
    for entry in root.iterdir() if root.is_dir() else ():
        try:
            found.append((tuple(int(part) for part in entry.name.split(".")), entry.name))
        except ValueError:
            continue
    return sorted(found)


def choose(toolsets: list[tuple[tuple[int, ...], str]], runtime: tuple[int, int]) -> str | None:
    """The newest toolset whose (major, minor) is at most the runtime's."""
    usable = [name for version, name in toolsets if version[:2] <= runtime]
    return usable[-1] if usable else None


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: select_msvc_toolset.py <VS root> <repo .venv dir>", file=sys.stderr)
        return 2
    vs_root, venv = Path(argv[0]), Path(argv[1])
    runtime_path = python_runtime(venv)
    version = file_version(runtime_path)
    if version is None:
        print(f"cannot read the version of {runtime_path}", file=sys.stderr)
        return 1
    toolsets = installed_toolsets(vs_root)
    chosen = choose(toolsets, version[:2])
    if chosen is None:
        names = ", ".join(name for _, name in toolsets) or "none"
        print(f"no installed MSVC toolset is at most the runtime {version[0]}.{version[1]} of {runtime_path} "
              f"(installed: {names}); install that toolset's build tools component", file=sys.stderr)
        return 1
    print(chosen)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
