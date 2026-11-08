"""Build the SRPSS Linux product: Nuitka standalone folder, installer script and tarball.

Linux only. Entry point: ``scripts/linux/build.sh`` (or this file directly with the
``.venv-linux`` interpreter). From Windows: ``scripts/linux/build_from_windows.ps1``.

Single source of truth: the portable Nuitka declarations (data trees, packages, Qt
plugins/modules, resource packs, strict no-include mode) and the Qt/QML size
exclusions are **read from the Windows build scripts** (``scripts/venv/build_nuitka.ps1``
and ``tools/build_layout.ps1``) and filtered to what exists on Linux. A new include
added for Windows therefore reaches Linux automatically; ``tests/test_build_linux_declarations.py``
(which runs on Windows too, where these scripts are edited) fails if the extraction stops finding them.

Linux differences, all deliberate:

* standalone folder (``srpss`` + libraries), not onefile: no per-launch extraction;
* no Windows-only payload (WinRT, PyAudioWPatch, ``.scr``, Reddit secure-desktop helper);
* the curated trees the Windows installer places in ``%ProgramData%\\SRPSS`` are installed by
  the bundled ``install.sh`` into ``~/.local/share/SRPSS`` (``core/platform_paths.py``),
  with the same whole-tree replacement for presets and themes.

Output (default ``release/linux``): ``SRPSS-<version>-linux-x86_64/`` and its ``.tar.gz``.
glibc compatibility follows the build machine: a binary built on glibc 2.39 needs >= 2.39.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WINDOWS_BUILD_SCRIPT = REPO / "scripts" / "venv" / "build_nuitka.ps1"
WINDOWS_LAYOUT_SCRIPT = REPO / "tools" / "build_layout.ps1"
APP_NAME = "srpss"

# Windows-only payload or options that have no Linux meaning.
_WINDOWS_ONLY_MARKERS = ("winrt", "pyaudiowpatch", "--msvc", "--onefile", "--windows-", "--remove-output")
# Set by the Linux driver itself.
_DRIVER_OWNED = ("--jobs=", "--standalone")


_HERE_STRING_OPENER = re.compile(r"[ \t]*\r?\n")


def _strip_ps1_comments(text: str) -> str:
    """PowerShell source without its comments (``<# ... #>`` blocks and ``#`` to the end of a line), outside strings.

    The quoted-value extraction below pairs quotes, so an apostrophe or quote inside a comment (``Nuitka's``) would
    shift every later pair and silently drop every declaration after it (8 Nov 2026: 0 of the Windows declarations
    reached the Linux build, presets included, and its install.sh failed).

    Strings are read as PowerShell reads them (checkpoint audit 11, A11-L8), so nothing inside one starts a comment
    or ends the string early: single-quoted (``''`` is an escaped quote), double-quoted (a backtick escapes the next
    character, ``""`` is an escaped quote), and here-strings (``@'`` / ``@"`` ending a line, to ``'@`` / ``"@`` at the
    start of a line), which are kept verbatim. Outside strings a backtick escapes the next character (`` `# `` starts
    no comment). Not modelled: a double quote inside a ``$( )`` subexpression of a double-quoted string, and a ``#``
    inside an unquoted bareword (``a#b`` is no comment in PowerShell, but is cut here); the declarations are quoted,
    and ``tests/test_build_linux_declarations.py``'s every-literal check is the guard for anything else."""
    out: list[str] = []
    index, length = 0, len(text)
    while index < length:
        char = text[index]
        if text.startswith("<#", index):
            end = text.find("#>", index + 2)
            index = length if end < 0 else end + 2
            continue
        if char == "#":
            end = text.find("\n", index)
            index = length if end < 0 else end            # the line break stays
            continue
        if char == "`":
            out.append(text[index:index + 2])
            index += 2
            continue
        if char == "@" and text[index + 1:index + 2] in ("'", '"'):
            opener = _HERE_STRING_OPENER.match(text, index + 2)
            if opener is not None:
                closer = re.compile("^" + re.escape(text[index + 1]) + "@", re.MULTILINE).search(text, opener.end())
                end = length if closer is None else closer.end()
                out.append(text[index:end])
                index = end
                continue
        if char in ("'", '"'):
            end = index + 1
            while end < length:
                inner = text[end]
                if char == '"' and inner == "`":
                    end += 2
                    continue
                if inner == char:
                    if text[end + 1:end + 2] == char:     # doubled: an escaped quote
                        end += 2
                        continue
                    end += 1
                    break
                end += 1
            out.append(text[index:end])
            index = end
            continue
        out.append(char)
        index += 1
    return "".join(out)


def _ps1_quoted(block: str) -> list[str]:
    return re.findall(r"""['"]([^'"]*)['"]""", block)


def _ps1_array(text: str, opener: str) -> str:
    start = text.index(opener) + len(opener)
    depth, index = 1, start
    while depth:
        char = text[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        index += 1
    return text[start:index - 1]


def portable_windows_arguments(script: Path = WINDOWS_BUILD_SCRIPT) -> list[str]:
    """Return the Windows Nuitka declarations that also apply on Linux."""

    block = _ps1_array(_strip_ps1_comments(script.read_text(encoding="utf-8")), "$argsList = @(")
    arguments = []
    for value in _ps1_quoted(block):
        if not value.startswith("--") or "$" in value:
            continue
        if any(marker in value.lower() for marker in _WINDOWS_ONLY_MARKERS):
            continue
        if value.startswith(_DRIVER_OWNED):
            continue
        arguments.append(value)
    return arguments


def qt_prune_arguments(script: Path = WINDOWS_LAYOUT_SCRIPT) -> list[str]:
    """Return the Windows Qt/QML size exclusions translated to Linux shared objects."""

    text = _strip_ps1_comments(script.read_text(encoding="utf-8"))
    function = text[text.index("function Get-SRPSSNuitkaQmlPruneArguments"):]
    function = function[:function.index("\nfunction ")]
    families = _ps1_quoted(_ps1_array(function, "$unusedQmlFamilies = @("))
    dll_patterns = _ps1_quoted(_ps1_array(function, "foreach ($dllPattern in @("))
    arguments: list[str] = []
    for family in families:
        arguments += [f"--noinclude-data-files=PySide6/qml/{family}/**", f"--noinclude-dlls=PySide6/qml/{family}/**"]
    for pattern in dll_patterns:
        if pattern.endswith(".dll"):
            arguments.append(f"--noinclude-dlls={pattern[:-4]}.so*")
    for literal in re.findall(r"\$arguments\.Add\('([^']+)'\)", function):
        if not literal.endswith(".dll"):
            arguments.append(literal)
    return arguments


def nuitka_arguments(output_dir: Path, jobs: int) -> list[str]:
    return [
        "-m", "nuitka",
        "--standalone",
        f"--jobs={jobs}",
        "--assume-yes-for-downloads",
        f"--output-dir={output_dir}",
        f"--output-filename={APP_NAME}",
        *portable_windows_arguments(),
        *qt_prune_arguments(),
        "main.py",
    ]


def _app_version() -> str:
    namespace: dict = {}
    exec((REPO / "versioning.py").read_text(encoding="utf-8"), namespace)  # noqa: S102 - repo-owned constant file
    return str(namespace["APP_VERSION"])


INSTALL_SH = r"""#!/usr/bin/env bash
# Install this SRPSS Linux build for the current user.
#   ./install.sh            install to ~/.local/opt/srpss, link ~/.local/bin/srpss, add a menu entry
#   ./install.sh --uninstall
# Curated presets/themes/sounds go to ~/.local/share/SRPSS (whole-tree replacement, like the
# Windows installer's ProgramData step). Settings live in ~/.config/SRPSS and are never touched.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
PREFIX="$HOME/.local/opt/srpss"
BIN="$HOME/.local/bin"
APPS="$DATA/applications"
if [[ "${1:-}" == "--uninstall" ]]; then
  rm -rf "$PREFIX" "$BIN/srpss" "$APPS/srpss.desktop" "$APPS/srpss-settings.desktop"
  rm -rf "$DATA/SRPSS/presets/visualizer_modes" "$DATA/SRPSS/themes" "$DATA/SRPSS/sounds"
  echo "[INSTALL] SRPSS removed (settings in ~/.config/SRPSS kept)."
  exit 0
fi
mkdir -p "$PREFIX" "$BIN" "$APPS" "$DATA/SRPSS/presets" "$DATA/SRPSS/sounds"
rm -rf "$PREFIX" && cp -a "$HERE" "$PREFIX"
ln -sf "$PREFIX/srpss" "$BIN/srpss"
rm -rf "$DATA/SRPSS/presets/visualizer_modes" "$DATA/SRPSS/themes"
cp -a "$HERE/presets/visualizer_modes" "$DATA/SRPSS/presets/visualizer_modes"
cp -a "$HERE/themes" "$DATA/SRPSS/themes"
cp -a "$HERE/resources/tutuogg.ogg" "$HERE/resources/jedimodeyall.mp3" "$DATA/SRPSS/sounds/"
for entry in "srpss:SRPSS Screensaver:/s" "srpss-settings:SRPSS Settings:/c"; do
  IFS=: read -r id name mode <<<"$entry"
  cat >"$APPS/$id.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$name
Exec=$PREFIX/srpss $mode
Icon=$PREFIX/srpss.png
Categories=Graphics;Settings;
Terminal=false
EOF
done
echo "[INSTALL] Installed to $PREFIX; run 'srpss /c' for Settings or 'srpss /s' for the saver."
echo "[INSTALL] As a screensaver: X11 'xss-lock -- srpss /s', Wayland 'swayidle -w timeout 600 \"srpss /s\"'."
"""


def _write_payload_extras(dist: Path) -> None:
    from PIL import Image

    (dist / "install.sh").write_text(INSTALL_SH, encoding="utf-8")
    (dist / "install.sh").chmod(0o755)
    with Image.open(REPO / "SRPSS.ico") as icon:
        icon.save(dist / "srpss.png")


def build(output: Path, jobs: int, dry_run: bool) -> Path:
    version = _app_version()
    build_dir = output / "build"
    dist = output / f"SRPSS-{version}-linux-x86_64"
    args = nuitka_arguments(build_dir, jobs)
    print("[LINUX-BUILD] " + " ".join([sys.executable, *args]), flush=True)
    if dry_run:
        return dist
    subprocess.run([sys.executable, str(REPO / "tools" / "regen_qrc.py"), "--python", sys.executable], cwd=REPO, check=True)
    subprocess.run([sys.executable, *args], cwd=REPO, check=True)
    produced = build_dir / "main.dist"
    if not (produced / APP_NAME).is_file():
        raise SystemExit(f"[LINUX-BUILD] Nuitka finished without {produced / APP_NAME}")
    if dist.exists():
        shutil.rmtree(dist)
    produced.rename(dist)
    _write_payload_extras(dist)
    archive = dist.with_name(dist.name + ".tar.gz")
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(dist, arcname=dist.name)
    print(f"[LINUX-BUILD] product: {dist}\n[LINUX-BUILD] archive: {archive}", flush=True)
    return dist


def main() -> int:
    if not sys.platform.startswith("linux"):
        raise SystemExit("Linux only (from Windows use scripts/linux/build_from_windows.ps1)")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=REPO / "release" / "linux")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 2)
    parser.add_argument("--dry-run", action="store_true", help="print the Nuitka command only")
    args = parser.parse_args()
    build(args.output.resolve(), args.jobs, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
