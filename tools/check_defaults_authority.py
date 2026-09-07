"""Fail-fast headless audit for SRPSS canonical defaults ownership.

Two independent guards, both gated here so the build fails loudly (never
silently ships drift):

1. authority audit -- no shadow/fragmented defaults (a second value authority);
2. derived-artifact byte-sync -- the checked-in ``defaults_snapshot.json`` and
   both ``.sst`` defaults documents must be exactly what the single builder
   emits from canonical ``DEFAULT_SETTINGS``. Without (2) an edit to
   ``default_settings.py`` without regenerating would ship stale artifacts and
   the drift would only surface later (foundry warning / test run) -- the
   "randomly pops up when I adjust a setting" failure mode.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.settings.defaults_authority_audit import audit_defaults_authority
from core.settings.defaults_snapshot_builder import (
    defaults_snapshot_matches,
    sst_defaults_documents_match,
)

_REGEN_HINT = "run: python -m core.settings.defaults_snapshot_builder --write-all"


def main() -> int:
    failed = False

    issues = audit_defaults_authority(ROOT)
    if issues:
        print(f"defaults authority audit FAILED: {len(issues)} issue(s)")
        for issue in issues:
            print(f" - {issue.render()}")
        failed = True
    else:
        print("defaults authority audit OK")

    if defaults_snapshot_matches():
        print("derived defaults snapshot OK")
    else:
        print(f"derived defaults snapshot STALE ({_REGEN_HINT})")
        failed = True

    if sst_defaults_documents_match():
        print("SST defaults documents OK")
    else:
        print(f"SST defaults documents STALE ({_REGEN_HINT})")
        failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
