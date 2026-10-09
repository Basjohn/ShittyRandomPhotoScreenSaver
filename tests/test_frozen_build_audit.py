"""Pure source/report checks; never launch Nuitka or a frozen application."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.frozen_build_audit import included_modules, main, source_fingerprint, verify_report


REQUIRED = {
    "rendering.quick.context_menu", "core.sources.image_bans",
    "engine.display_manager", "engine.screensaver_engine", "engine.image_queue",
}


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "src"
    (root / "core" / "sources").mkdir(parents=True)
    (root / "rendering" / "quick").mkdir(parents=True)
    (root / "main.py").write_text("# entry\n", encoding="utf-8")
    (root / "rendering" / "quick" / "context_menu.py").write_text("# Ban Image\n", encoding="utf-8")
    (root / "core" / "sources" / "image_bans.py").write_text("# file\n", encoding="utf-8")
    return root


def _report(tmp_path: Path, *, missing: str = "") -> Path:
    report = tmp_path / "nuitka.xml"
    report.write_text(
        '<nuitka-compilation-report>\n' +
        ''.join(f'<module name="{name}" kind="CompiledPythonModule" />\n' for name in sorted(REQUIRED - {missing})) +
        '</nuitka-compilation-report>\n', encoding="utf-8"
    )
    return report


def test_runtime_source_fingerprint_is_stable_and_changes_on_menu_edits(tmp_path):
    root = _repo(tmp_path)
    first, count = source_fingerprint(root)
    assert len(first) == 64 and count == 3
    assert source_fingerprint(root) == (first, count)
    (root / "build").mkdir()
    (root / "build" / "output.py").write_text("ignore build output")
    assert source_fingerprint(root)[0] == first
    (root / "rendering" / "quick" / "context_menu.py").write_text("# now updated\n", encoding="utf-8")
    assert source_fingerprint(root)[0] != first


def test_report_checks_required_modules_and_source_immutability(tmp_path):
    root = _repo(tmp_path)
    fingerprint = source_fingerprint(root)[0][:20]
    report = _report(tmp_path)
    assert REQUIRED <= included_modules(report)
    assert verify_report(root, report, fingerprint)["required_compiled_modules"] == sorted(REQUIRED)
    with pytest.raises(ValueError, match="source changed"):
        verify_report(root, report, "0" * 20)
    with pytest.raises(ValueError, match="rendering.quick.context_menu"):
        verify_report(root, _report(tmp_path, missing="rendering.quick.context_menu"), fingerprint)


def test_verify_receipt_identifies_specific_compiled_file(tmp_path):
    root = _repo(tmp_path)
    report = _report(tmp_path)
    exe = tmp_path / "SRPSS.scr"
    exe.write_bytes(b"compiled sample")
    receipt = tmp_path / "receipt.json"
    result = main([
        "verify", "--root", str(root), "--report", str(report),
        "--expected", source_fingerprint(root)[0][:20],
        "--artifact", str(exe), "--receipt", str(receipt),
    ])
    assert result == 0
    saved = json.loads(receipt.read_text(encoding="utf-8"))
    assert saved["artifact_bytes"] == len(b"compiled sample")
    assert saved["artifact_path"] == str(exe.resolve())
    assert "core.sources.image_bans" in saved["required_compiled_modules"]


def test_workers_fail_closed_and_onefile_cache_does_not_reuse_stale_snapshot():
    root = Path(__file__).resolve().parents[1]
    standard = (root / "scripts/venv/build_nuitka.ps1").read_text(encoding="utf-8")
    mc = (root / "scripts/venv/build_nuitka_mc_onedir.ps1").read_text(encoding="utf-8")
    assert "$OnefileCacheName/$SourceFingerprint" in standard
    assert "--onefile-tempdir-spec={CACHE_DIR}/SRPSS/$OnefileCacheName" in standard
    for worker in (standard, mc):
        assert "frozen_build_audit.py" in worker
        assert "fingerprint --root $Root" in worker
        assert "verify --root $Root --report $NuitkaReportFile" in worker
        assert "if ($LASTEXITCODE -ne 0) { throw 'Frozen" in worker
    assert "--onefile-tempdir-spec=" not in mc


def test_menu_contract_is_real_source_not_baked_preset():
    root = Path(__file__).resolve().parents[1]
    source = (root / "rendering/quick/context_menu.py").read_text(encoding="utf-8")
    engine = (root / "engine/screensaver_engine.py").read_text(encoding="utf-8")
    manager = (root / "engine/display_manager.py").read_text(encoding="utf-8")
    assert 'QuickContextMenuEntry("ban_image",' in source
    assert 'QuickContextMenuEntry("clear_image_bans",' in source
    assert '"ban_image_requested"' in engine
    assert '"clear_image_bans_requested"' in engine
    assert 'if action == "ban_image":' in manager
    assert 'if action == "clear_image_bans":' in manager
