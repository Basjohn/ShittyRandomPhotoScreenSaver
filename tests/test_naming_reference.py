"""The generated naming reference (``Docs/Reference/Naming.md``) stays current and its hand-written claims stay true.

The reference maps every product name to its persisted id and to the other spellings in code (audit
``Docs/Audits/Semantic_Naming_Audit_2026-11-07.md`` recommendation 1). It is generated from the registries by
``tools/naming_reference.py``; these tests fail when the checked-in file drifts from a fresh generation, when a
hand-written claim no longer holds in the source, and when the read-first routes stop pointing at it.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NAMING = ROOT / "Docs" / "Reference" / "Naming.md"


def test_naming_reference_matches_a_fresh_generation(qt_app):
    from tools.naming_reference import generate

    assert NAMING.is_file(), "Docs/Reference/Naming.md is missing: run tools/naming_reference.py --write"
    current = NAMING.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert current == generate(), "Docs/Reference/Naming.md is stale: run tools/naming_reference.py --write"


def test_a_claim_the_source_no_longer_supports_stops_generation(qt_app, monkeypatch):
    from tools import naming_reference as nr

    real = "rendering/transition_registry.py"
    with pytest.raises(nr.StaleClaim):
        nr.verify(nr.Claim("gone file", (nr.Proof("rendering/no_such_module_for_naming.py"),)))
    with pytest.raises(nr.StaleClaim):
        nr.verify(nr.Claim("stale pattern", (nr.Proof(real, r"GLCompositorRainDropsTransition"),)))
    with pytest.raises(nr.StaleClaim):
        nr.verify(nr.Claim("must be absent", (nr.Proof(real, r"stable_id=", absent=True),)))
    nr.verify(nr.Claim("holds", (nr.Proof(real, r'stable_id="ripple"'),)))

    # A registered mode without a hand-written row stops generation, so a new mode is mapped when it lands.
    spellings = dict(nr.MODE_SPELLINGS)
    spellings.pop("devcurve")
    monkeypatch.setattr(nr, "MODE_SPELLINGS", spellings)
    with pytest.raises(nr.StaleClaim, match="devcurve"):
        nr.generate()


@pytest.mark.parametrize("router", ["Index.md", "Docs/Guides/Visualizer_Change_Checklist.md"])
def test_read_first_routes_point_at_the_naming_reference(router):
    assert "Docs/Reference/Naming.md" in (ROOT / router).read_text(encoding="utf-8")
