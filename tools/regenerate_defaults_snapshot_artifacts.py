"""Regenerate derived defaults snapshot artifacts from canonical defaults."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.settings.defaults_snapshot_builder import build_defaults_snapshot

SNAPSHOT_JSON_PATH = REPO_ROOT / "core" / "settings" / "defaults_snapshot.json"


def regenerate_defaults_snapshot_json(output_path: Path = SNAPSHOT_JSON_PATH) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(build_defaults_snapshot(), indent=4, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regenerate derived defaults snapshot artifacts")
    parser.add_argument(
        "--json-path",
        default=str(SNAPSHOT_JSON_PATH),
        help="Path for defaults_snapshot.json output",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    json_path = regenerate_defaults_snapshot_json(Path(args.json_path))
    print(f"[DEFAULTS] Wrote {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
