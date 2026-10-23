"""Repository-level guard against accidental test-suite authority duplication."""
from __future__ import annotations

from pathlib import Path

from tools.test_durability_audit import (
    _TRANSITION_CATALOG_TOKENS, audit_test_file, audit_tests,
)


def _rules(tmp_path: Path, source: str) -> set[str]:
    path = tmp_path / "test_probe.py"
    path.write_text(source, encoding="utf-8")
    return {finding.rule for finding in audit_test_file(path)}


def test_test_suite_has_no_blocking_authority_copy_smells() -> None:
    findings = audit_tests()
    assert not findings, "\n" + "\n".join(item.render() for item in findings)


def test_audit_detects_copied_canonical_default_literal(tmp_path: Path) -> None:
    rules = _rules(
        tmp_path,
        '''\nfrom core.settings.default_contract import require_canonical_default\n\ndef test_bad():\n    assert require_canonical_default("widgets.clock.position") == "Top Right"\n''',
    )
    assert "canonical-default-literal" in rules


def test_audit_detects_large_extensible_catalog_copies(tmp_path: Path) -> None:
    # Eight current transition names copied into a literal, as a hand-copied catalog would be.
    copied = ", ".join(repr(name) for name in sorted(_TRANSITION_CATALOG_TOKENS)[:8])
    rules = _rules(
        tmp_path,
        '''\ndef test_bad_catalogs():\n    modes = {\n        "spectrum": 1, "oscilloscope": 2, "sine_wave": 3,\n        "bubble": 4, "devcurve": 5,\n    }\n'''
        f"    transitions = [{copied}]\n    assert modes and transitions\n",
    )
    assert "visualizer-catalog-literal" in rules
    assert "transition-catalog-literal" in rules


def test_audit_allows_semantic_subsets_and_fixture_literals(tmp_path: Path) -> None:
    rules = _rules(
        tmp_path,
        '''\ndef test_fixture():\n    payload = {"position": "Top Right", "monitor": "2"}\n    assert payload["position"] == "Top Right"\n    modes_under_test = ("bubble", "spectrum")\n    assert "bubble" in modes_under_test\n''',
    )
    assert not rules


def test_exact_value_marker_documents_intentional_catalog_pin(tmp_path: Path) -> None:
    rules = _rules(
        tmp_path,
        '''\ndef test_protocol_catalog():\n    # EXACT-VALUE INVARIANT: frozen compatibility protocol enumerates these legacy ids.\n    legacy = ("spectrum", "oscilloscope", "sine_wave", "bubble", "devcurve")\n    assert legacy\n''',
    )
    assert "visualizer-catalog-literal" not in rules


def test_audit_rejects_documentation_prose_as_runtime_oracle(tmp_path: Path) -> None:
    rules = _rules(
        tmp_path,
        '''\nfrom pathlib import Path\nROOT = Path(__file__).parent\n\ndef test_bad_doc_oracle():\n    text = (ROOT / "Docs" / "Guardrails" / "Policy.md").read_text(encoding="utf-8")\n    assert "runtime must do the thing" in text\n''',
    )
    assert "documentation-prose-oracle" in rules


def test_audit_does_not_confuse_markdown_path_inputs_with_prose_oracles(tmp_path: Path) -> None:
    rules = _rules(
        tmp_path,
        '''\ndef test_path_semantics():\n    assert workflow_default_selected("Docs/Current_Plan.md") is True\n''',
    )
    assert "documentation-prose-oracle" not in rules


def test_generated_document_content_can_be_an_explicit_product_invariant(tmp_path: Path) -> None:
    rules = _rules(
        tmp_path,
        '''\nfrom pathlib import Path\nROOT = Path(__file__).parent\n\ndef test_generated_doc():\n    text = (ROOT / "Docs" / "Generated.md").read_text(encoding="utf-8")\n    # DOCUMENT-CONTENT INVARIANT: generated API table is itself a shipped artifact.\n    assert "Generated API" in text\n''',
    )
    assert "documentation-prose-oracle" not in rules


def test_audit_follows_transitive_canonical_snapshot_aliases(tmp_path: Path) -> None:
    rules = _rules(
        tmp_path,
        '''\nfrom core.settings.defaults_snapshot_builder import build_defaults_snapshot\n\ndef test_bad_alias():\n    payload = build_defaults_snapshot()\n    widgets = payload["widgets"]\n    media = widgets["media"]\n    assert media["spotify_volume_track_color"] == [35, 35, 35, 255]\n''',
    )
    assert "canonical-snapshot-literal" in rules


def test_audit_rejects_raw_canonical_defaults_pinned_to_artistic_literal(tmp_path: Path) -> None:
    rules = _rules(tmp_path, '''
from core.settings.default_contract import get_raw_default_settings

def test_bad():
    defaults = get_raw_default_settings()
    visualizer = defaults['widgets']['spotify_visualizer']
    assert visualizer['sphere_spin_direction'] == 'Default'
''')
    assert 'canonical-snapshot-literal' in rules


def test_audit_rejects_named_curated_theme_artistic_value_golden(tmp_path: Path) -> None:
    rules = _rules(tmp_path, '''
from pathlib import Path
import json
ROOT = Path(__file__).resolve().parent

def test_bad_theme():
    theme = json.loads((ROOT / 'themes' / 'Named Art.srtheme').read_text())
    assert theme['colors']['card.border'] == [15, 20, 30, 255]
''')
    assert 'named-shipped-theme-art-oracle' in rules


def test_audit_allows_test_owned_theme_round_trip(tmp_path: Path) -> None:
    rules = _rules(tmp_path, '''
def test_theme(tmp_path):
    spec = {'colors': {'card.border': [15, 20, 30, 255]}}
    theme = tmp_path / 'Synthetic.srtheme'
    theme.write_text(serialize(spec))
    assert deserialize(theme.read_text()) == spec
''')
    assert not rules
