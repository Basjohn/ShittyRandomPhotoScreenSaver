"""Regenerate repo-local shipped visualizer preset artifacts from source presets."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.visualizer_preset_manifest import regenerate_repo_shipped_visualizer_preset_artifacts  # noqa: E402


def main() -> int:
    artifacts = regenerate_repo_shipped_visualizer_preset_artifacts(REPO_ROOT)
    print(
        "Regenerated shipped visualizer preset artifacts: "
        f"{artifacts['entry_count']} curated files mirrored into "
        f"{artifacts['release_root']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
