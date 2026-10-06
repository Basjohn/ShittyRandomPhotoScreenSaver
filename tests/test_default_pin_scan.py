"""Self-tests for the review-only canonical-default pin scanner."""
from __future__ import annotations

from pathlib import Path

from tools.default_pin_scan import scan_file


def _scan(tmp_path: Path, source: str):
    path = tmp_path / "test_probe.py"
    path.write_text(source, encoding="utf-8")
    return scan_file(path, {"mode": ["fill"], "position": ["Top Left"]})


def test_scan_flags_unexplained_default_literal(tmp_path: Path) -> None:
    hits = _scan(
        tmp_path,
        '''
def test_default_copy(payload):
    assert payload["mode"] == "fill"
''',
    )
    assert [(key, value) for _name, _line, key, value, _text in hits] == [("mode", "fill")]


def test_scan_ignores_test_owned_literal_mapping_round_trip(tmp_path: Path) -> None:
    hits = _scan(
        tmp_path,
        '''
def test_round_trip(save):
    authored = {"mode": "fill"}
    payload = save(authored)
    assert payload["mode"] == "fill"
''',
    )
    assert hits == []


def test_scan_keeps_unrelated_fixture_value_from_hiding_default_copy(tmp_path: Path) -> None:
    hits = _scan(
        tmp_path,
        '''
def test_default_copy(payload):
    authored = {"position": "Top Left"}
    assert payload["mode"] == "fill"
''',
    )
    assert [(key, value) for _name, _line, key, value, _text in hits] == [("mode", "fill")]


def test_scan_respects_explicit_exact_value_contract_marker(tmp_path: Path) -> None:
    hits = _scan(
        tmp_path,
        '''
def test_protocol(payload):
    # EXACT-VALUE INVARIANT: external protocol requires this spelling.
    assert payload["mode"] == "fill"
''',
    )
    assert hits == []
