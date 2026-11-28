"""Bake (or check) Extruded Bubble's native packs from the Python renderer's texts (N5.6; checklist 16).

    .venv/Scripts/python tools/eb_native_shaders.py --check     # exit 1 when a pack is not what its text bakes to
    .venv/Scripts/python tools/eb_native_shaders.py --write     # bake every stale pack

The texts are ``rendering.native.extruded_bubble_shaders.shader_files``' (made in memory from the Python programs);
the packs live in ``widgets/spotify_visualizer/shaders/extruded_bubble`` and are baked with the product's qsb and
targets (``tools/regen_qrc.py``'s, as the native transitions' are).
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pack_folder() -> Path:
    from rendering.native.extruded_bubble_shaders import PACK_FOLDER

    return ROOT.joinpath(*PACK_FOLDER)


def statuses(*, bake: bool, only: tuple[str, ...] = ()) -> list[tuple[str, bool, str]]:
    """(source name, current, reason) of every pack; ``bake``: a stale one is replaced by its fresh bake."""
    import subprocess

    from rendering.native.extruded_bubble_shaders import shader_files
    from tools.regen_qrc import _bake_quick_shader, quick_shader_baker, quick_shader_targets

    qsb, targets = quick_shader_baker(sys.executable), quick_shader_targets()
    folder = pack_folder()
    found = []
    with tempfile.TemporaryDirectory(prefix="srpss_eb_qsb_") as work:
        for name, text in sorted(shader_files().items()):
            if only and name not in only:
                continue
            source = Path(work) / name
            source.write_bytes(text.encode("utf-8"))
            fresh = Path(work) / f"{name}.qsb"
            try:
                _bake_quick_shader(qsb, source, fresh, targets, subprocess.run)
            except Exception as exc:  # the bake's own reason, reported per pack
                found.append((name, False, f"bake failed: {exc}"))
                continue
            pack = folder / f"{name}.qsb"
            current = pack.is_file() and pack.read_bytes() == fresh.read_bytes()
            if not current and bake:
                folder.mkdir(parents=True, exist_ok=True)
                pack.write_bytes(fresh.read_bytes())
                current = True
            found.append((name, current, "current" if current else ("missing" if not pack.is_file() else "stale")))
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true", help="report the packs that are not what their texts bake to")
    action.add_argument("--write", action="store_true", help="bake every stale pack")
    parser.add_argument("--only", nargs="*", default=(), help="these source names only")
    args = parser.parse_args(argv)
    found = statuses(bake=args.write, only=tuple(args.only))
    bad = [(name, reason) for name, current, reason in found if not current]
    for name, reason in bad:
        print(f"{name}: {reason}")
    print(f"{len(found) - len(bad)} of {len(found)} packs current in {pack_folder()}")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
