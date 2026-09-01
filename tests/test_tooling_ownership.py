"""Permanent tooling-ownership contracts.

Analysis/diagnostic tools are operator-side consumers. They must never become a
production runtime owner or force retired migration architecture back into the
application merely so an old harness can run.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _imports_tools_or_scripts(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    bad: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "tools" or alias.name.startswith("tools.") or alias.name == "scripts" or alias.name.startswith("scripts."):
                    bad.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "tools" or node.module.startswith("tools.") or node.module == "scripts" or node.module.startswith("scripts."):
                bad.append(node.module)
    return bad


def test_production_python_never_imports_operator_analysis_tools():
    violations: list[str] = []
    excluded_roots = {"tests", "tools"}
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        if rel.parts and rel.parts[0] in excluded_roots:
            continue
        imports = _imports_tools_or_scripts(path)
        if imports:
            violations.append(f"{rel}: {sorted(set(imports))}")
    assert violations == []


def test_test_convenience_wrapper_delegates_to_canonical_runner():
    source = (ROOT / "tools" / "run_tests.py").read_text(encoding="utf-8")
    assert 'RUNNER = ROOT / "tests" / "run_chunked.py"' in source
    assert 'choices=("destination", "all")' in source
    assert 'command.extend(("--profile", "destination"))' in source
    assert "TEST_SUITES" not in source


def test_external_resource_sampler_cannot_terminate_attached_pid():
    source = (ROOT / "tools" / "perf_measure.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    # The only call to the destructive helper must remain guarded by the child
    # process handle created by --launch. Attached --pid observation is passive.
    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_stop_launched"
    ]
    assert len(calls) == 1
    call = calls[0]
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    ancestor = parents.get(call)
    while ancestor is not None and not isinstance(ancestor, ast.If):
        ancestor = parents.get(ancestor)
    assert isinstance(ancestor, ast.If)
    assert "launched is not None" in ast.unparse(ancestor.test)


def test_current_imageworker_shm_harness_uses_current_owner_not_legacy_presenter():
    source = (ROOT / "tools" / "image_worker_shm_lifecycle_harness.py").read_text(encoding="utf-8")
    assert "core.process.workers.image_worker" in source
    assert "engine.image_pipeline" in source
    assert "spotify_visualizer_widget" not in source
    assert "gl_compositor" not in source.lower()
