#!/usr/bin/env bash
# SRPSS Linux development environment setup.
#
# Creates the Linux virtual environment (default: <repo>/.venv-linux, so a checkout
# shared with Windows, e.g. through WSL /mnt/c, never touches the Windows .venv),
# installs the single pinned requirements.txt (Windows-only distributions are
# skipped by their PEP 508 markers) and compiles the Qt resource packs.
#
# Usage:
#   scripts/linux/setup.sh [--python /path/to/python3.14] [--venv DIR]
#                          [--system-deps] [--headless] [--build]
#
#   --system-deps  install the Qt/OpenGL/audio runtime libraries with apt-get (sudo)
#   --headless     also install Xvfb/xrandr/Mesa tools for tools/linux_run_headless.py
#   --build        also install the toolchain for scripts/linux/build.sh (patchelf, gcc)
#
# Python: SRPSS pins CPython 3.14 (64-bit, standard GIL). Without --python the
# script uses python3.14 from PATH, else asks uv for a managed 3.14 if uv exists.
# Docs: Docs/Guides/Linux_Guide.md; rules: Docs/Guardrails/Linux_Compatibility.md
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON=""
VENV="$REPO/.venv-linux"
SYSTEM_DEPS=0
HEADLESS=0
BUILD=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --python) PYTHON="$2"; shift 2 ;;
    --venv) VENV="$2"; shift 2 ;;
    --system-deps) SYSTEM_DEPS=1; shift ;;
    --headless) HEADLESS=1; SYSTEM_DEPS=1; shift ;;
    --build) BUILD=1; SYSTEM_DEPS=1; shift ;;
    -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
    *) echo "[SETUP] unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "[SETUP] Linux only (use the Windows .venv workflow on Windows)." >&2
  exit 2
fi

# Runtime libraries PySide6 (xcb + OpenGL), PortAudio (sounddevice) and D-Bus need.
APT_RUNTIME=(libegl1 libgl1 libopengl0 libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1
  libxcb-shape0 libxcb-xinerama0 libxcb-randr0 libxcb-render-util0 libxcb-image0 libxcb-xkb1
  libfontconfig1 libdbus-1-3 libportaudio2 libglib2.0-0 pulseaudio-utils)
APT_HEADLESS=(xvfb x11-xserver-utils mesa-utils libgl1-mesa-dri)
APT_BUILD=(patchelf gcc ccache)

if [[ $SYSTEM_DEPS -eq 1 ]]; then
  if ! command -v apt-get >/dev/null; then
    echo "[SETUP] --system-deps needs apt-get (Debian/Ubuntu). Install the equivalents of:" >&2
    echo "        ${APT_RUNTIME[*]}" >&2
    exit 2
  fi
  packages=("${APT_RUNTIME[@]}")
  [[ $HEADLESS -eq 1 ]] && packages+=("${APT_HEADLESS[@]}")
  [[ $BUILD -eq 1 ]] && packages+=("${APT_BUILD[@]}")
  SUDO=""; [[ $(id -u) -ne 0 ]] && SUDO="sudo"
  echo "[SETUP] apt-get install ${packages[*]}"
  $SUDO apt-get update -q
  $SUDO apt-get install -y -q "${packages[@]}"
fi

if [[ -z "$PYTHON" ]]; then
  if command -v python3.14 >/dev/null; then
    PYTHON="$(command -v python3.14)"
  elif command -v uv >/dev/null; then
    uv python install 3.14
    PYTHON="$(uv python find 3.14)"
  else
    echo "[SETUP] CPython 3.14 not found. Install python3.14 (e.g. deadsnakes PPA) or uv, or pass --python." >&2
    exit 2
  fi
fi

"$PYTHON" - <<'EOF'
import struct, sys
if sys.version_info[:2] != (3, 14) or struct.calcsize("P") != 8 or not sys._is_gil_enabled():
    raise SystemExit(f"[SETUP] SRPSS requires 64-bit, GIL-enabled CPython 3.14; got {sys.version}")
EOF

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "[SETUP] creating venv $VENV"
  "$PYTHON" -m venv "$VENV"
fi
VPY="$VENV/bin/python"
"$VPY" -m pip install -q --upgrade pip
echo "[SETUP] installing requirements.txt"
"$VPY" -m pip install -q -r "$REPO/requirements.txt"
"$VPY" -m pip check

echo "[SETUP] compiling Qt resource packs"
"$VPY" "$REPO/tools/regen_qrc.py" --python "$VPY"

cat <<EOF
[SETUP] Ready.
  Settings:   $VPY $REPO/main.py /c
  Saver:      $VPY $REPO/main.py /s
  Headless:   $VPY $REPO/tools/linux_run_headless.py --shots 6,14
  Tests:      $VPY -m pytest -q tests/test_platform_paths.py
EOF
