"""Run the canonical frozen Linux smoke harness from the workflow tooling directory."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools import evidence_media  # noqa: E402
from tools.linux_smoke_dist import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(evidence_media.finish(main(sys.argv[1:])))
