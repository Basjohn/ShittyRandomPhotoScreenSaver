"""Every ``core.settings`` module imports cleanly as the first thing a fresh interpreter does (1C.11).

``core.settings.normalization`` imported first used to fail: it imports ``core.settings.models``, whose model
classes call the enum parser at class definition, which lived back in the half-loaded ``normalization``. A module's
import must never depend on which settings module some other code happened to import before it, so each module
is imported in its own interpreter. The module list is read from the tree, never written here.
"""
from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "core" / "settings"


def _settings_modules() -> list[str]:
    names = []
    for path in sorted(SETTINGS.rglob("*.py")):
        parts = path.relative_to(ROOT).with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        names.append(".".join(parts))
    return names


def _import_first(module: str) -> tuple[str, int, str]:
    code = f"import sys; sys.path.insert(0, {str(ROOT)!r}); import importlib; importlib.import_module({module!r})"
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    result = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), env=env, capture_output=True,
                            text=True, timeout=300)
    return module, result.returncode, result.stderr.strip()[-2000:]


def test_the_module_list_covers_the_known_cycle_participants():
    modules = _settings_modules()
    assert {"core.settings.normalization", "core.settings.models", "core.settings.models._core"} <= set(modules)


def test_every_settings_module_imports_first_in_a_fresh_interpreter():
    modules = _settings_modules()
    with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 2)) as pool:
        results = list(pool.map(_import_first, modules))
    failures = {module: stderr for module, code, stderr in results if code != 0}
    assert not failures, "\n\n".join(f"{module}:\n{stderr}" for module, stderr in failures.items())


def test_the_strict_enum_parser_loads_no_other_settings_module():
    """The parser sits below the models and ``normalization``; importing it must pull in neither."""
    code = (f"import sys; sys.path.insert(0, {str(ROOT)!r}); import core.settings.enum_parsing; "
            "print(sorted(m for m in sys.modules if m.startswith('core.settings.')))")
    result = subprocess.run([sys.executable, "-c", code], cwd=str(ROOT), capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "['core.settings.enum_parsing']"


@pytest.mark.parametrize("module", ["core.settings.normalization"])
def test_the_former_cycle_entry_point_imports_first(module):
    """The module that used to fail, named on its own so a regression reads plainly."""
    _module, code, stderr = _import_first(module)
    assert code == 0, stderr
