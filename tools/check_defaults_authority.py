"""Fail-fast headless audit for SRPSS canonical defaults ownership.

Two guards, run by the build (``tools/build_layout.ps1``) and after every
Defaults Foundry save (in a fresh interpreter, so the just-written
``default_settings.py`` is what gets imported):

- ``audit_defaults_authority`` reports shadow/fragmented defaults (a second
  value authority) and any revived checked-in copy of the defaults;
- every profile's projection of the canonical defaults must carry no
  private/credential fields.

Nothing is generated: the canonical defaults are the only defaults artifact.
"""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.settings.defaults_authority_audit import audit_defaults_authority


def private_field_issues() -> list[str]:
    """Credential-shaped keys in any profile's canonical defaults projection."""

    from core.settings.default_contract import MC_PROFILE, NORMAL_PROFILE
    from core.settings.defaults_snapshot_builder import build_sst_defaults_snapshot
    from tools.defaults_foundry_core import validate_no_private_fields

    issues = []
    for profile in (NORMAL_PROFILE, MC_PROFILE):
        try:
            validate_no_private_fields(build_sst_defaults_snapshot(profile), label=f"{profile} canonical defaults")
        except ValueError as exc:
            issues.append(str(exc))
    return issues


def main() -> int:
    issues = [issue.render() for issue in audit_defaults_authority(ROOT)] + private_field_issues()
    if issues:
        print(f"defaults authority audit FAILED: {len(issues)} issue(s)")
        for issue in issues:
            print(f" - {issue}")
        return 1
    print("defaults authority audit OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
