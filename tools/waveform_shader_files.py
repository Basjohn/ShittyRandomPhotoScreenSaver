"""Write (or check) Waveform Ribbon's shader files from the Python renderer's texts (N5.4; checklist 16).

    .venv/Scripts/python tools/waveform_shader_files.py --check     # exit 1 when a file differs from its text
    .venv/Scripts/python tools/waveform_shader_files.py --write     # write every file, then bake: regen_qrc --shaders

The texts and the variants are ``rendering.gl_programs.waveform_shader_files``'s; the files live in the Visualizer
modes' shader folder (``widgets/spotify_visualizer/shaders``), where ``tools/regen_qrc.py --shaders`` bakes each pass
file into the ``.qsb`` the native core loads.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def shader_folder() -> Path:
    from widgets.spotify_visualizer import shaders

    return Path(shaders.__file__).resolve().parent


def differences() -> list[str]:
    """The file names whose text on disk is not their text (missing ones included). Line endings aside: a checkout may
    hold these files with CRLF (``.gitattributes`` leaves them to ``text=auto``)."""
    from rendering.gl_programs.waveform_shader_files import waveform_shader_files

    from rendering.gl_programs.waveform_shader_files import MEMBERS_MODULE, members_module_text

    folder = shader_folder()
    stale = [name for name, text in waveform_shader_files().items()
             if not (folder / name).is_file() or (folder / name).read_text(encoding="utf-8") != text]
    table = ROOT / MEMBERS_MODULE
    if not table.is_file() or table.read_text(encoding="utf-8") != members_module_text():
        stale.append(MEMBERS_MODULE)
    return stale


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true", help="report the files that differ from their texts")
    action.add_argument("--write", action="store_true", help="write every file from its text")
    args = parser.parse_args(argv)
    if args.write:
        from rendering.gl_programs.waveform_shader_files import (MEMBERS_MODULE, members_module_text,
                                                                 waveform_shader_files)

        folder = shader_folder()
        for name, text in waveform_shader_files().items():
            (folder / name).write_bytes(text.encode("utf-8"))
        (ROOT / MEMBERS_MODULE).write_bytes(members_module_text().encode("utf-8"))
        print(f"wrote {len(waveform_shader_files())} files to {folder} and {MEMBERS_MODULE}")
        return 0
    stale = differences()
    for name in stale:
        print("differs:", name)
    print("current" if not stale else f"{len(stale)} files differ: run --write, then tools/regen_qrc.py --shaders")
    return 1 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
