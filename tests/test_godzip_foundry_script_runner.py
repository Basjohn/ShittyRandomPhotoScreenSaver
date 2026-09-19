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


def test_script_runner_ui_has_review_capture_and_explicit_no_admin():
    # Pure source contract: Qt runtime interactions receive a separate Windows gate.
    source = (Path(__file__).resolve().parents[1] / 'tools' / 'godzip_foundry.py').read_text(encoding='utf-8')
    klass = source.split('class CommandTab(QWidget):', 1)[1].split('class GodzipFoundryWindow(QMainWindow):', 1)[0]
    for marker in ('normalize_script_paste(', 'if dialog.exec()', 'self._start_script(',
                   'QProcess(self)', 'setWorkingDirectory(str(self.repo_root))',
                   'COPY RESULTS', 'ZIP RUN + NEW LOGS', 'External terminal (keep open)',
                   'create_script_results_zip(', 'self._run_final_logs = snapshot_loose_logs('):
        assert marker in klass
    assert 'self.admin.isChecked()' not in klass.split('def _review_and_run', 1)[1].split('def _copy_path', 1)[0]
