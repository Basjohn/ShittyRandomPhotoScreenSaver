"""Automatic fallback reasons stay WARNING+ in the real main log with sidecars enabled."""
from __future__ import annotations

import subprocess
import sys

import pytest


@pytest.mark.parametrize('disabled_for_run', (False, True), ids=('no_supervisor', 'run_disabled'))
def test_initial_automatic_fallback_reaches_main_log_at_warning(tmp_path, disabled_for_run):
    script = f'''
from pathlib import Path
from types import SimpleNamespace
import logging
import core.logging.logger as log
from widgets.spotify_visualizer import engine_worker_link
from widgets.spotify_visualizer.quick_display_visualizer_owner import QuickDisplayVisualizerOwner

log.set_forced_log_dir(Path({str(tmp_path)!r}))
log.setup_logging(viz=True, lifecycle=True)
seen = []
class Capture(logging.Handler):
    def emit(self, record):
        if 'mode=fallback-probe' in record.getMessage():
            seen.append(record.levelno)
logging.getLogger().addHandler(Capture())
engine_worker_link.reset_run_state_for_testing()
if {disabled_for_run!r}:
    engine_worker_link.disable_worker_for_run('an earlier session failed')
owner = QuickDisplayVisualizerOwner.__new__(QuickDisplayVisualizerOwner)
owner._controller = SimpleNamespace(mode_id='fallback-probe')
owner._configure_services = {{'process_supervisor': None}}
assert owner._configure_on_engine_worker({{}}, playing=False) is False
log.flush_and_close_logging()
text = (Path({str(tmp_path)!r})/'screensaver.log').read_text(encoding='utf-8')
lines = [line for line in text.splitlines() if 'mode=fallback-probe' in line]
assert len(lines) == 1, text
assert seen == [logging.WARNING] and 'runs in process' in lines[0], text
assert ('disabled for this run' if {disabled_for_run!r} else 'no process supervisor') in lines[0], text
'''
    result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
