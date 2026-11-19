"""Run Script quick-action contracts, including pure script transformations.

The non-Qt tests may be run independently in constrained environments. The
integration tests use the main pytest Qt fixture on the operator's Windows venv.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tools.godzip_script_runner import ScriptRunError, add_repo_venv_to_script


def test_add_venv_updates_each_bare_powershell_command_without_touching_flow():
    source = (r"python -m pytest -q; if ($LASTEXITCODE -ne 0) { throw 'python failed' }; "
              r"python tools\regen_qrc.py --shaders")
    rewritten = add_repo_venv_to_script(source)
    assert rewritten.count(r"& .\.venv\Scripts\python.exe") == 2
    assert r"if ($LASTEXITCODE -ne 0) { throw 'python failed' }" in rewritten
    assert add_repo_venv_to_script(rewritten) == rewritten


def test_add_venv_preserves_qualified_interpreters_comments_and_quoted_arguments():
    source = (r'& .\.venv\Scripts\python.exe -m pytest; ' 
              r'Write-Output "python -m pytest"; python -V # use python in venv')
    result = add_repo_venv_to_script(source)
    assert result.count(r'.\.venv\Scripts\python.exe') == 2
    assert r'Write-Output "python -m pytest"' in result
    assert result.endswith('# use python in venv')
    assert add_repo_venv_to_script('# python -V\n' + result) == '# python -V\n' + result


def test_add_venv_supports_powershell_pytest_and_cmd_without_activation():
    ps = add_repo_venv_to_script('pytest -q && python -V')
    assert ps == (r'& .\.venv\Scripts\python.exe -m pytest -q && '
                  r'& .\.venv\Scripts\python.exe -V')
    cmd = add_repo_venv_to_script(r'python -m pytest -q && pytest tests\unit', shell='cmd')
    assert cmd == (r'.\.venv\Scripts\python.exe -m pytest -q && '
                   r'.\.venv\Scripts\python.exe -m pytest tests\unit')
    assert add_repo_venv_to_script(cmd, shell='cmd') == cmd


def test_add_venv_does_not_change_other_commands_or_strings():
    raw = 'git status; echo "python -m pytest"\n# python -m pytest\necho done'
    assert add_repo_venv_to_script(raw) == raw
    with pytest.raises(ScriptRunError):
        add_repo_venv_to_script('python -V', shell='auto')


def test_quick_actions_have_explicit_intent_and_do_not_modify_native_runtime():
    source = (Path(__file__).parents[1] / 'tools' / 'godzip_foundry.py').read_text(encoding='utf-8')
    assert 'self.script_add_venv_button = QPushButton("Add Venv")' in source
    assert 'self.script_regen_shaders_button = QPushButton("Shaders Regen")' in source
    assert 'self.script_add_venv_button.clicked.connect(self._add_script_venv)' in source
    assert 'self.script_regen_shaders_button.clicked.connect(self._regenerate_shaders)' in source
    assert 'self.script_shell.setCurrentIndex(self.script_shell.findData("powershell"))' in source
    assert 'self._run_script()' in source
    assert '--shaders --check' in source
    assert 'self.tabs.tabBar().setUsesScrollButtons(True)' in source
    assert 'self.primary_tab_bar.setUsesScrollButtons(True)' in source
    assert 'navigation_row.addWidget(right_nav, 0, Qt.AlignmentFlag.AlignRight)' in source
    assert 'self.foundries_tab_button = QPushButton("FOUNDRIES")' in source
    assert 'right_nav.setFixedWidth(right_nav_layout.sizeHint().width())' in source
