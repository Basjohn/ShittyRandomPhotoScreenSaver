"""Product code never reads an ``SRPSS_*`` environment variable.

The project bans environment-variable flags: diagnostics are opt-in CLI admissions parsed once
at startup (``core/diagnostics/experiment_flags.py``), and everything else is a setting. This
guard fails when any ``os.getenv`` / ``os.environ`` access with an ``SRPSS_`` key reappears in
product code. Tests and tools may still set child-process environments for isolation, so
``tests/``, ``tools/`` and ``scripts/`` are outside the scan.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_EXCLUDED_TOP_LEVEL = {
    ".git", ".venv", ".claude", "tests", "tools", "scripts", "build", "dist", "tmp", "logs",
    "node_modules", "__pycache__", "Docs", "assets",
}
_ENV_FUNCTIONS = {"getenv", "putenv", "unsetenv"}
_ENV_METHODS = {"get", "pop", "setdefault", "__getitem__", "__setitem__", "__contains__"}


def _is_os_environ(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    ) or (isinstance(node, ast.Name) and node.id == "environ")


def _srpss_literals(node: ast.AST) -> list[str]:
    return [
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant)
        and isinstance(child.value, str)
        and child.value.startswith("SRPSS_")
    ]


def srpss_environment_reads(source: str) -> list[tuple[int, str]]:
    """Return ``(line, key)`` for every SRPSS_ key used with an environment access."""

    hits: list[tuple[int, str]] = []
    for node in ast.walk(ast.parse(source)):
        keys: list[str] = []
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and (
                (func.attr in _ENV_FUNCTIONS and isinstance(func.value, ast.Name) and func.value.id == "os")
                or (func.attr in _ENV_METHODS and _is_os_environ(func.value))
            ):
                for arg in node.args:
                    keys.extend(_srpss_literals(arg))
            elif isinstance(func, ast.Name) and func.id in _ENV_FUNCTIONS:
                for arg in node.args:
                    keys.extend(_srpss_literals(arg))
        elif isinstance(node, ast.Subscript) and _is_os_environ(node.value):
            keys.extend(_srpss_literals(node.slice))
        elif isinstance(node, ast.Compare) and any(_is_os_environ(item) for item in node.comparators):
            keys.extend(_srpss_literals(node.left))
        hits.extend((getattr(node, "lineno", 0), key) for key in keys)
    return hits


def _product_sources():
    for path in sorted(ROOT.rglob("*.py")):
        relative = path.relative_to(ROOT)
        if relative.parts[0] in _EXCLUDED_TOP_LEVEL or "__pycache__" in relative.parts:
            continue
        yield path, relative


def test_product_code_reads_no_srpss_environment_variable():
    offenders = []
    for path, relative in _product_sources():
        try:
            source = path.read_text(encoding="utf-8")
            hits = srpss_environment_reads(source)
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        for line, key in hits:
            offenders.append(f"{relative.as_posix()}:{line} reads {key}")
    assert not offenders, (
        "SRPSS_* environment reads are banned in product code; use a CLI admission "
        "(core/diagnostics/experiment_flags.py), a setting, or delete the gate:\n"
        + "\n".join(offenders)
    )


def test_scan_sees_product_code():
    names = {relative.as_posix() for _, relative in _product_sources()}
    assert {"main.py", "core/logging/logger.py", "engine/display_manager.py"} <= names


def test_negative_control_the_scanner_flags_every_read_shape():
    shapes = [
        'import os\nos.getenv("SRPSS_A")',
        'import os\nos.getenv("SRPSS_A", "0")',
        'import os\nos.environ.get("SRPSS_A", "")',
        'import os\nos.environ["SRPSS_A"]',
        'import os\nos.environ["SRPSS_A"] = "1"',
        'import os\nx = "SRPSS_A" in os.environ',
        'import os\nos.environ.pop("SRPSS_A", None)',
        'from os import environ\nenviron.get("SRPSS_A")',
        'import os\nos.getenv("SRPSS_" + "A")',
    ]
    for source in shapes:
        assert srpss_environment_reads(source), source


def test_negative_control_the_scanner_ignores_unrelated_strings_and_variables():
    clean = [
        'import os\nos.getenv("APPDATA")',
        'import os\nos.environ.get("PROGRAMDATA")',
        'NAME = "SRPSS_MC"',
        'import os\nos.environ["OPENBLAS_NUM_THREADS"] = "1"',
    ]
    for source in clean:
        assert not srpss_environment_reads(source), source
