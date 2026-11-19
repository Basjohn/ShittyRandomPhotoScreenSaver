from pathlib import Path
import zipfile
import pytest
from tools.godzip_script_runner import normalize_script_paste,ScriptRunError,snapshot_loose_logs,create_script_results_zip

def test_prompt_joins_as_script_without_dropping_semicolons():
    pasted='''PS F:\\Programming\\Apps\\ShittyRandomPhotoScreenSaver> python -m pytest tests\\test_a.py -q; if ($LASTEXITCODE -eq 0) { python tests\\run_chunked.py --chunks 4 --log }'''
    x=normalize_script_paste(pasted)
    assert x.shell=='powershell' and x.script.startswith('python -m pytest')
    assert '; if ($LASTEXITCODE -eq 0)' in x.script

def test_fences_and_continuations():
    x=normalize_script_paste('''```powershell id="z999"
PS F:\\repo> $focused = @(
>>   "tests\\a.py"
>> );
>> python -m pytest $focused -q;
```''')
    assert x.script.startswith('$focused = @(')
    assert '"tests\\a.py"' in x.script and '>>' not in x.script
    assert x.changes

def test_ambiguous_and_results_are_not_run():
    for value in ('```powershell\npython -m pytest','PS F:\\repo> python -m pytest -q\n512 passed in 47s','PS F:\\repo> python -m pytest -q\n============== FAILURES ============'):
        with pytest.raises(ScriptRunError): normalize_script_paste(value)

def test_lone_python_line_keeps_powershell_default():
    x=normalize_script_paste('python -m pytest tests\\test_a.py -q; if ($LASTEXITCODE -eq 0) { python tests\\run_chunked.py --log }')
    assert x.shell=='powershell' and x.script.count(';')==1

def test_changed_logs_only_and_bounded_zip(tmp_path):
    repo=tmp_path/'repo';(repo/'.godzip_foundry'/'runs'/'case1').mkdir(parents=True)
    run=repo/'.godzip_foundry'/'runs'/'case1';logs=repo/'logs';logs.mkdir()
    (logs/'before.log').write_text('old')
    first=snapshot_loose_logs(repo)
    (logs/'after.log').write_text('new')
    (run/'command.txt').write_text('python -m pytest -q')
    (run/'output.txt').write_text('512 passed')
    (run/'result.json').write_text('{"exit_code": 0}')
    z, members=create_script_results_zip(repo,run,initial_logs=first,output_dir=tmp_path/'out')
    assert 'logs/after.log' in members and 'logs/before.log' not in members
    with zipfile.ZipFile(z) as archive:
        assert archive.testzip() is None and 'run/output.txt' in archive.namelist()


def test_fails_closed_for_unsafe_wrappers_and_mixed_shells():
    for pasted in (
        '```powershell id="xx"\npython -m pytest -q',
        'PS F:\\repo> python -m pytest -q\nC:\\repo> python -V',
        'PS F:\\repo> python -m pytest -q\n========== FAILURES ==========',
        'PS F:\\repo> python -m pytest -q\n10 failed, 502 passed in 48s',
    ):
        with pytest.raises(ScriptRunError):
            normalize_script_paste(pasted)


def test_explicit_cmd_and_mismatched_prompt():
    cmd = normalize_script_paste('C:\\repo> python -m pytest -q && echo PASS', shell='auto')
    assert cmd.shell == 'cmd' and cmd.script == 'python -m pytest -q && echo PASS'
    with pytest.raises(ScriptRunError):
        normalize_script_paste('PS F:\\repo> python -V', shell='cmd')


def test_captured_log_bundle_is_scoped_to_run_completion(tmp_path):
    repo = tmp_path / 'repo'
    run = repo / '.godzip_foundry' / 'runs' / 'case2'
    run.mkdir(parents=True)
    logs = repo / 'logs'
    logs.mkdir()
    before = snapshot_loose_logs(repo)
    (logs / 'during.log').write_text('during run')
    finished = snapshot_loose_logs(repo)
    (logs / 'after.log').write_text('later unrelated run')
    (run / 'command.txt').write_text('python -m pytest -q')
    (run / 'output.txt').write_text('pytest completed')
    (run / 'result.json').write_text('{"exit_code": 0}')
    out, members = create_script_results_zip(repo, run, initial_logs=before,
                                             final_logs=finished, output_dir=tmp_path / 'out')
    assert 'logs/during.log' in members and 'logs/after.log' not in members
    with zipfile.ZipFile(out) as archive:
        assert archive.testzip() is None


def test_logzip_rejects_outside_run_directory(tmp_path):
    repo = tmp_path / 'repo'
    repo.mkdir()
    fake = tmp_path / 'external'
    fake.mkdir()
    with pytest.raises(ScriptRunError):
        create_script_results_zip(repo, fake, initial_logs={}, output_dir=tmp_path / 'out')


@pytest.fixture
def command_tab(qt_app, monkeypatch, tmp_path):
    """The real Run Script tab of a real Foundry window over a throwaway repository."""
    from tests.test_foundry_widget_ownership import _git_repo
    from tools import godzip_foundry

    monkeypatch.setattr(godzip_foundry, 'collect_repo_files', lambda _root: [])
    window = godzip_foundry.GodzipFoundryWindow(_git_repo(tmp_path))
    thread = window._task_thread
    if thread is not None:
        thread.join(timeout=60)
    qt_app.processEvents()
    try:
        yield window.command_tab, godzip_foundry
    finally:
        window.close()
        window.deleteLater()
        qt_app.processEvents()


def test_run_script_shows_the_reviewed_command_and_launches_exactly_it(command_tab):
    """Run Script normalises the paste in the editor itself (the reviewed command), refuses ambiguous input
    without launching, and launches the normalised script with the chosen shell and capture mode, never
    reading the elevation checkbox."""
    tab, _module = command_tab
    launched = []
    tab._start_script = lambda shell, script, *, external: launched.append((shell, script, external))
    pasted = 'PS F:\\repo> python -m pytest tests\\test_a.py -q;'
    expected = normalize_script_paste(pasted, shell='auto')
    tab.admin.setChecked(True)  # explicit elevation belongs to the terminal launcher, not to Run Script

    tab.script_input.setPlainText(pasted)
    tab.script_run_button.click()
    assert launched == [(expected.shell, expected.script, False)]
    assert tab.script_input.toPlainText() == expected.script, 'the editor must show the command that runs'

    launched.clear()
    tab.script_input.setPlainText('```powershell\npython -m pytest')  # ambiguous: fails closed
    tab.script_run_button.click()
    assert launched == []

    tab.script_input.setPlainText(pasted)
    tab.script_external.setChecked(True)
    tab.script_run_button.click()
    assert launched and launched[0][2] is True


def test_run_script_captures_a_real_run_in_the_repository_and_enables_results(command_tab, qt_app):
    """A captured run executes from the repository root, records the transcript and result, and only then
    enables copying, opening and zipping the results."""
    import json

    tab, _module = command_tab
    assert not (tab.script_copy.isEnabled() or tab.script_show_results.isEnabled() or tab.script_zip.isEnabled())
    tab.script_input.setPlainText('cd')
    tab.script_shell.setCurrentIndex(tab.script_shell.findData('cmd'))
    tab.script_run_button.click()
    process = tab._process
    assert process is not None and tab._running
    assert not tab.script_run_button.isEnabled() and tab.script_stop_button.isEnabled()
    assert process.workingDirectory() == str(tab.repo_root)
    assert process.waitForFinished(60000)
    qt_app.processEvents()
    assert not tab._running
    run_dir = tab._run_dir
    assert str(tab.repo_root).lower() in (run_dir / 'output.txt').read_text(encoding='utf-8', errors='replace').lower()
    assert json.loads((run_dir / 'result.json').read_text(encoding='utf-8'))['exit_code'] == 0
    assert tab.script_copy.isEnabled() and tab.script_show_results.isEnabled() and tab.script_zip.isEnabled()
    assert tab.script_run_button.isEnabled() and not tab.script_stop_button.isEnabled()


def test_run_script_zip_bundles_the_run_and_only_logs_it_changed(command_tab, qt_app, monkeypatch, tmp_path):
    tab, module = command_tab
    logs = tab.repo_root / 'logs'
    logs.mkdir()
    (logs / 'before.log').write_text('old')
    tab.script_input.setPlainText('echo done')
    tab.script_shell.setCurrentIndex(tab.script_shell.findData('cmd'))
    # The log appears during the run: the process is started, then the file is written before it finishes.
    tab.script_run_button.click()
    (logs / 'during.log').write_text('new')
    assert tab._process.waitForFinished(60000)
    qt_app.processEvents()
    made = []
    real = module.create_script_results_zip
    monkeypatch.setattr(module, 'create_script_results_zip',
                        lambda *args, **kwargs: made.append(real(*args, **kwargs)) or made[-1])
    tab.script_zip.click()
    thread = tab.window._task_thread
    assert thread is not None
    thread.join(timeout=60)
    assert not thread.is_alive()
    qt_app.processEvents()
    assert made, 'the Zip button must build the results archive'
    archive, members = made[0]
    assert Path(archive).is_file()
    assert 'logs/during.log' in members and 'logs/before.log' not in members


def test_script_quick_actions_preserve_editor_truth_and_use_captured_runner(command_tab):
    """Editor-only Add Venv; Shaders Regen uses the existing script capture path."""
    tab, module = command_tab
    launched = []
    tab._start_script = lambda shell, script, *, external: launched.append((shell, script, external))
    tab.script_input.setPlainText('python -m pytest -q')
    tab.script_add_venv_button.click()
    assert tab.script_input.toPlainText() == r'& .\.venv\Scripts\python.exe -m pytest -q'
    tab.script_add_venv_button.click()
    assert tab.script_input.toPlainText() == r'& .\.venv\Scripts\python.exe -m pytest -q'
    assert not launched

    tab.script_external.setChecked(True)
    tab.script_regen_shaders_button.click()
    assert tab.script_input.toPlainText() == module.SHADER_REGEN_COMMAND
    assert launched == [('powershell', module.SHADER_REGEN_COMMAND, False)]
    assert not tab.script_external.isChecked()


def test_godzip_explicit_navigation_preserves_all_three_buttons(command_tab, qt_app):
    """Right navigation reserves its own width and left tabs can scroll independently."""
    tab, module = command_tab
    window = tab.window
    window.show()
    qt_app.processEvents()
    nav = window.right_nav
    assert window.tabs.cornerWidget(module.Qt.Corner.TopRightCorner) is None
    assert window.primary_tab_bar.usesScrollButtons()
    assert not window.tabs.tabBar().isVisible()
    buttons = (window.run_tab_button, window.cmd_tab_button, window.foundries_tab_button)
    assert [button.text() for button in buttons] == ["RUN", "CMD", "FOUNDRIES"]
    assert nav.width() >= sum(button.width() for button in buttons) + 2 * 5
    for button in buttons:
        assert button.parentWidget() is nav
        assert button.geometry().right() <= nav.width()
        assert button.geometry().bottom() <= nav.height()
    assert nav.geometry().right() <= window.tabs.geometry().right()
    window.foundries_tab_button.click()
    qt_app.processEvents()
    assert window.tabs.currentWidget() is window.foundries_tab
    window.primary_tab_bar.setCurrentIndex(2)
    qt_app.processEvents()
    assert window.tabs.currentWidget() is window.diff_tab
