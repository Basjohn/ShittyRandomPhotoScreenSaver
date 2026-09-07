"""Fail-fast headless audit for SRPSS canonical defaults ownership.

``audit_defaults_authority`` is the single guard. It reports both shadow/
fragmented defaults (a second value authority) AND derived-artifact drift --
the checked-in ``defaults_snapshot.json`` and both ``.sst`` defaults documents
must be exactly what the one builder emits from canonical ``DEFAULT_SETTINGS``.
Running it here fails the build loudly instead of letting stale artifacts ship
and surface later (foundry warning / test run) -- the "randomly pops up when I
adjust a setting" failure mode. Regenerate with
``python -m core.settings.defaults_snapshot_builder --write-all``.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.settings.defaults_authority_audit import audit_defaults_authority


def main() -> int:
    issues = audit_defaults_authority(ROOT)
    if issues:
        print(f"defaults authority audit FAILED: {len(issues)} issue(s)")
        for issue in issues:
            print(f" - {issue.render()}")
        return 1
    print("defaults authority audit OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
