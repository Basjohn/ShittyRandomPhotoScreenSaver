"""Build the SRPSS Linux screensaver or MC product: Nuitka standalone folder, installer and tarball.

Linux only. Entry point: ``scripts/linux/build.sh`` (or this file directly with the
``.venv-linux`` interpreter). From Windows: ``scripts/linux/build_from_windows.ps1``.

Single source of truth: the portable Nuitka declarations (data trees, packages, Qt
plugins/modules, resource packs, strict no-include mode) and the Qt/QML size
exclusions are **read from the Windows build scripts** (``scripts/venv/build_nuitka.ps1``
and ``tools/build_layout.ps1``) and filtered to what exists on Linux. A new include
added for Windows therefore reaches Linux automatically; ``tests/test_build_linux_declarations.py``
(which runs on Windows too, where these scripts are edited) fails if the extraction stops finding them.

Linux differences, all deliberate:

* standalone folder (``srpss`` for screensaver, ``srpss-mc`` for MC), not onefile;
* no Windows-only payload (WinRT, PyAudioWPatch, ``.scr``, Reddit secure-desktop helper);
* the curated trees the Windows installer places in ``%ProgramData%\\SRPSS`` are installed by
  the bundled ``install.sh`` into ``~/.local/share/SRPSS`` (``core/platform_paths.py``),
  with the same whole-tree replacement for presets and themes.

Output (default ``release/linux``): ``SRPSS-<version>-linux-x86_64`` for the default screensaver,
or ``SRPSS-<version>-linux-mc-x86_64`` with ``--profile mc``, each with a matching ``.tar.gz``.
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
PROFILES = {
    "screensaver": ("main.py", "srpss", ""),
    "mc": ("main_mc.py", "srpss-mc", "-mc"),
}
APP_NAME = "srpss"  # original screensaver name, retained for integrations


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


def nuitka_arguments(output_dir: Path, jobs: int, profile: str = "screensaver") -> list[str]:
    entrypoint, binary, _suffix = PROFILES[profile]
    return [
        "-m", "nuitka",
        "--standalone",
        f"--jobs={jobs}",
        "--assume-yes-for-downloads",
        f"--output-dir={output_dir}",
        f"--output-filename={binary}",
        *portable_windows_arguments(),
        *qt_prune_arguments(),
        entrypoint,
    ]


def _app_version() -> str:
    namespace: dict = {}
    exec((REPO / "versioning.py").read_text(encoding="utf-8"), namespace)  # noqa: S102 - repo-owned constant file
    return str(namespace["APP_VERSION"])


INSTALL_SH = r"""#!/usr/bin/env bash
# Install this SRPSS Linux build for the current user.
#   ./install.sh            install to ~/.local/opt/<profile>, create CLI links and menu entries
#   ./install.sh --uninstall
# Curated presets/themes/sounds go to ~/.local/share/SRPSS (whole-tree replacement, like the
# Windows installer's ProgramData step). Screensaver/MC have distinct settings profiles.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA="${XDG_DATA_HOME:-$HOME/.local/share}"
APP="__APP_BINARY__"
APP_LABEL="__APP_LABEL__"
PREFIX="$HOME/.local/opt/$APP"
BIN="$HOME/.local/bin"
APPS="$DATA/applications"
PEER="srpss-mc"
[[ "$APP" == "srpss-mc" ]] && PEER="srpss"
if [[ "${1:-}" == "--uninstall" ]]; then
  rm -rf "$PREFIX" "$BIN/$APP" "$APPS/$APP.desktop" "$APPS/$APP-settings.desktop"
  if [[ ! -d "$HOME/.local/opt/$PEER" ]]; then
    rm -rf "$DATA/SRPSS/presets/visualizer_modes" "$DATA/SRPSS/themes" "$DATA/SRPSS/sounds"
  fi
  echo "[INSTALL] $APP removed (settings in ~/.config/SRPSS kept)."
  exit 0
fi
mkdir -p "$PREFIX" "$BIN" "$APPS" "$DATA/SRPSS/presets" "$DATA/SRPSS/sounds"
rm -rf "$PREFIX" && cp -a "$HERE" "$PREFIX"
ln -sf "$PREFIX/$APP" "$BIN/$APP"
rm -rf "$DATA/SRPSS/presets/visualizer_modes" "$DATA/SRPSS/themes"
cp -a "$HERE/presets/visualizer_modes" "$DATA/SRPSS/presets/visualizer_modes"
cp -a "$HERE/themes" "$DATA/SRPSS/themes"
cp -a "$HERE/resources/tutuogg.ogg" "$HERE/resources/jedimodeyall.mp3" "$DATA/SRPSS/sounds/"
for entry in "$APP:$APP_LABEL:__RUN_MODE__" "$APP-settings:$APP_LABEL Settings:/c"; do
  IFS=: read -r id name mode <<<"$entry"
  cat >"$APPS/$id.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=$name
Exec=$PREFIX/$APP $mode
Icon=$PREFIX/srpss.png
Categories=Graphics;Settings;
Terminal=false
EOF
done
echo "[INSTALL] Installed $APP to $PREFIX; run '$APP /c' for Settings or '$APP /s' for the main window."
if [[ "$APP" == "srpss" ]]; then
  echo '[INSTALL] Screensaver idle launch: configure xss-lock (X11) or an idle manager (Wayland).'
fi
"""


def install_script(profile: str = "screensaver") -> str:
    _entrypoint, binary, _suffix = PROFILES[profile]
    label = "SRPSS Media Center" if profile == "mc" else "SRPSS Screensaver"
    return (INSTALL_SH.replace("__APP_BINARY__", binary)
            .replace("__APP_LABEL__", label)
            .replace("__RUN_MODE__", "/s"))


def _write_payload_extras(dist: Path, profile: str = "screensaver") -> None:
    from PIL import Image

    (dist / "install.sh").write_text(install_script(profile), encoding="utf-8")
    (dist / "install.sh").chmod(0o755)
    with Image.open(REPO / "SRPSS.ico") as icon:
        icon.save(dist / "srpss.png")


def build(output: Path, jobs: int, dry_run: bool, profile: str = "screensaver") -> Path:
    entrypoint, binary, suffix = PROFILES[profile]
    version = _app_version()
    build_dir = output / "build" / profile
    dist = output / f"SRPSS-{version}-linux{suffix}-x86_64"
    args = nuitka_arguments(build_dir, jobs, profile)
    print("[LINUX-BUILD] " + " ".join([sys.executable, *args]), flush=True)
    if dry_run:
        return dist
    subprocess.run([sys.executable, str(REPO / "tools" / "regen_qrc.py"), "--python", sys.executable], cwd=REPO, check=True)
    subprocess.run([sys.executable, *args], cwd=REPO, check=True)
    # Nuitka's standalone folder follows the source entrypoint (main/main_mc), not necessarily --output-filename.
    candidates = [folder for folder in build_dir.glob("*.dist") if (folder / binary).is_file()]
    if len(candidates) != 1:
        raise SystemExit(f"[LINUX-BUILD] Expected exactly one {binary} standalone dist in {build_dir}, got {candidates}")
    produced = candidates[0]
    if dist.exists():
        shutil.rmtree(dist)
    produced.rename(dist)
    _write_payload_extras(dist, profile)
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
    parser.add_argument("--profile", choices=tuple(PROFILES), default="screensaver",
                        help="screensaver (default) or interactive Media Center")
    args = parser.parse_args()
    build(args.output.resolve(), args.jobs, args.dry_run, args.profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
