"""Pure source/report checks; never launch Nuitka or a frozen application."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.frozen_build_audit import (
    included_modules, main, qt_gui_imports_on_qtcore_import, source_fingerprint, verify_report,
)


REQUIRED = {
    "rendering.quick.context_menu", "core.sources.image_bans",
    "engine.display_manager", "engine.screensaver_engine", "engine.image_queue",
    # The engine worker's spawn target, imported by name in the frozen child (native core P2b slice 5.7).
    "core.visualizer_engine.engine_worker",
}


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "src"
    (root / "core" / "sources").mkdir(parents=True)
    (root / "rendering" / "quick").mkdir(parents=True)
    (root / "main.py").write_text("# entry\n", encoding="utf-8")
    (root / "rendering" / "quick" / "context_menu.py").write_text("# Ban Image\n", encoding="utf-8")
    (root / "core" / "sources" / "image_bans.py").write_text("# file\n", encoding="utf-8")
    return root


#: ``PySide6-postLoad`` as the 8 Nov GitHub build's report records it (Nuitka 4.2, an executable icon): the package
#: configuration's ``Signal.connect`` protection imports QtCore, the PySide6 plugin's icon hook QtWidgets and QtGui.
_POST_LOAD_WITH_ICON_HOOK = (
    '<module name="PySide6-postLoad" kind="CompiledPythonModule" usage="plugins" reason="According to Yaml '
    '\'post-import-code\' configuration. Loading Qt application icon from Windows resources.">\n'
    '  <module_usages>\n'
    '    <module_usage name="PySide6" finding="absolute" line="32" />\n'
    '    <module_usage name="PySide6.QtCore" finding="relative" line="32" />\n'
    '    <module_usage name="sys" finding="absolute" line="47" />\n'
    '    <module_usage name="PySide6.QtWidgets" finding="absolute" line="48" />\n'
    '    <module_usage name="PySide6.QtGui" finding="absolute" line="51" />\n'
    '  </module_usages>\n'
    '</module>\n'
)
#: The same trigger with the hook removed (``tools/nuitka_worker_qt_plugin.py``), and QtCore's own trigger.
_POST_LOAD_QTCORE_ONLY = (
    '<module name="PySide6-postLoad" kind="CompiledPythonModule" usage="plugins">\n'
    '  <module_usages>\n'
    '    <module_usage name="PySide6" finding="absolute" line="32" />\n'
    '    <module_usage name="PySide6.QtCore" finding="relative" line="32" />\n'
    '  </module_usages>\n'
    '</module>\n'
    '<module name="PySide6.QtCore-postLoad" kind="CompiledPythonModule" usage="plugins">\n'
    '  <module_usages>\n'
    '    <module_usage name="PySide6.QtCore" finding="absolute" line="3" />\n'
    '    <module_usage name="os" finding="absolute" line="4" />\n'
    '  </module_usages>\n'
    '</module>\n'
    # A GUI import outside the QtCore-import triggers (the application's own modules) is not this check's business.
    '<module name="rendering.quick.context_menu_view" kind="CompiledPythonModule">\n'
    '  <module_usages><module_usage name="PySide6.QtGui" finding="absolute" line="9" /></module_usages>\n'
    '</module>\n'
)


def _report(tmp_path: Path, *, missing: str = "", triggers: str = _POST_LOAD_QTCORE_ONLY) -> Path:
    report = tmp_path / "nuitka.xml"
    report.write_text(
        '<nuitka-compilation-report>\n' +
        ''.join(f'<module name="{name}" kind="CompiledPythonModule" />\n' for name in sorted(REQUIRED - {missing})) +
        triggers +
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


def test_publication_is_refused_when_a_qtcore_import_would_load_the_qt_gui_stack(tmp_path):
    # R-176's frozen half: in the 8 Nov build every compiled process importing PySide6.QtCore also loaded QtWidgets and
    # QtGui through ``PySide6-postLoad`` (the engine worker and the image workers mapped Qt6Gui.dll and Qt6Widgets.dll).
    # Negative control: that build's trigger, as its report records it, is refused, naming what it imports; the same
    # report with the hook removed passes and the receipt lists the triggers it checked.
    root = _repo(tmp_path)
    fingerprint = source_fingerprint(root)[0][:20]
    present, gui = qt_gui_imports_on_qtcore_import(_report(tmp_path, triggers=_POST_LOAD_WITH_ICON_HOOK))
    assert present == {"PySide6-postLoad"} and gui == {"PySide6-postLoad": ["PySide6.QtWidgets", "PySide6.QtGui"]}
    with pytest.raises(ValueError, match=r"PySide6-postLoad imports PySide6\.QtGui, PySide6\.QtWidgets"):
        verify_report(root, _report(tmp_path, triggers=_POST_LOAD_WITH_ICON_HOOK), fingerprint)
    proof = verify_report(root, _report(tmp_path), fingerprint)
    assert proof["qtcore_import_triggers_without_gui"] == ["PySide6-postLoad", "PySide6.QtCore-postLoad"]


def test_a_report_without_any_qtcore_import_trigger_cannot_pass_the_qt_weight_check(tmp_path):
    # Nuitka renaming its trigger modules must not turn the check into a silent pass.
    root = _repo(tmp_path)
    with pytest.raises(ValueError, match="no PySide6/QtCore load trigger"):
        verify_report(root, _report(tmp_path, triggers=""), source_fingerprint(root)[0][:20])


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
