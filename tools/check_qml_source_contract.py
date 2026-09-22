"""Headless build preflight for duplicate direct QML property assignments."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.build_qml_contract import audit_qml_source_contract


def main() -> int:
    issues = audit_qml_source_contract(ROOT)
    if issues:
        print(f"QML source contract FAILED: {len(issues)} issue(s)")
        for issue in issues:
            print(f" - {issue.render(ROOT)}")
        return 1
    print("QML source contract OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
