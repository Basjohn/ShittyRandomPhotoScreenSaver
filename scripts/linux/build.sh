#!/usr/bin/env bash
# Build the SRPSS Linux product (Nuitka standalone folder + install.sh + tarball).
#   scripts/linux/build.sh [--output DIR] [--jobs N] [--dry-run]
# Prerequisites: scripts/linux/setup.sh --system-deps --build
# From Windows (no WSL/Hyper-V/Docker): scripts/linux/build_from_windows.ps1
# Smoke-test the result: .venv-linux/bin/python tools/linux_smoke_dist.py release/linux/SRPSS-*-linux-x86_64
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VPY="$REPO/.venv-linux/bin/python"
if [[ ! -x "$VPY" ]]; then
  echo "[LINUX-BUILD] $VPY missing: run scripts/linux/setup.sh --system-deps --build first" >&2
  exit 2
fi
exec "$VPY" "$REPO/tools/linux_build.py" "$@"
