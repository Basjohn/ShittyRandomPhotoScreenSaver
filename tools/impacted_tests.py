"""Which test files a change can affect.

Builds the project's import graph from source (every import, including the lazy ones inside
functions, which is how most render and Settings code loads), takes the changed files, and returns
every test file that imports a changed module directly or through any chain of project modules.
Changed test files and their helpers count, a changed ``tests/conftest.py`` selects everything, and a
changed non-Python file (QML, shader, JSON, Markdown) selects the tests that name it.

Used by ``tests/run_chunked.py --changed``; also a CLI that prints the selection::

    python tools/impacted_tests.py                 # against HEAD (staged, unstaged and new files)
    python tools/impacted_tests.py --base main~3   # against another revision
    python tools/impacted_tests.py --why tests/test_qt611.py

A static graph cannot see imports built from strings at run time (``importlib.import_module(name)``
with a computed name); the release-media catalogue and implementation registry load modules that
way, so a change to one transition's implementation also selects the tests that name its module.
"""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict, deque
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
_SKIP_DIRS = {".venv", "venv", ".git", "__pycache__", "build", "dist", "logs", "tests_tmp_appdata",
              "tests_tmp_localappdata", "node_modules", ".pytest_cache"}


def _python_files() -> list[Path]:
    files = []
    for path in ROOT.rglob("*.py"):
        parts = set(path.relative_to(ROOT).parts[:-1])
        if not parts & _SKIP_DIRS and not any(part.startswith(".") for part in parts):
            files.append(path)
    return files


def _module_name(path: Path) -> str:
    parts = list(path.relative_to(ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _imports(path: Path, module: str, known: set[str]) -> dict[str, bool]:
    """Project modules ``path`` imports, each marked lazy when every import of it sits inside a
    function (it loads only if that code runs)."""
    source = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    # Dotted module names written as strings are imports only where something loads them by name
    # (lazy registries, import_module, monkeypatch targets); elsewhere they are labels (logger names).
    # A registry is a deliberate dispatch table, so its names count as eager imports.
    loads_by_name = any(word in source for word in ("import_module", "__import__", "monkeypatch"))
    package = module if path.name == "__init__.py" else module.rpartition(".")[0]
    found: dict[str, bool] = {}

    def add(name: str, lazy: bool) -> None:
        # The module itself and every package on the way (their __init__ runs too).
        while name:
            if name in known and name != module:
                found[name] = found.get(name, True) and lazy
            name = name.rpartition(".")[0]

    def visit(node: ast.AST, lazy: bool) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            lazy = True
        if isinstance(node, ast.Import):
            for alias in node.names:
                add(alias.name, lazy)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".") if package else []
                base = base[: len(base) - (node.level - 1)] if node.level > 1 else base
                stem = ".".join(base + ([node.module] if node.module else []))
            else:
                stem = node.module or ""
            add(stem, lazy)
            for alias in node.names:
                add(f"{stem}.{alias.name}" if stem else alias.name, lazy)
        elif loads_by_name and isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in known:
            add(node.value, False)
        for child in ast.iter_child_nodes(node):
            visit(child, lazy)

    visit(tree, False)
    return found


class ImportGraph:
    def __init__(self) -> None:
        self.files = {_module_name(path): path for path in _python_files()}
        known = set(self.files)
        # imported module -> {importer: lazy}
        self.importers: dict[str, dict[str, bool]] = defaultdict(dict)
        for module, path in self.files.items():
            for imported, lazy in _imports(path, module, known).items():
                self.importers[imported][module] = lazy

    def module_for(self, path: Path) -> str | None:
        try:
            module = _module_name(path.resolve())
        except ValueError:
            return None
        return module if module in self.files else None

    def affected(self, modules: set[str], lazy_hops: int = 1) -> dict[str, str | None]:
        """Every module that imports one of ``modules`` through a chain using at most ``lazy_hops``
        lazy imports, with the module it came from.

        Unlimited lazy hops reach nearly everything (the bootstrap lazily imports the engine, which
        imports most of the product); one hop keeps the registries and lazy loaders a test drives
        directly while dropping chains no test runs."""
        best: dict[str, int] = {module: 0 for module in modules}
        came_from: dict[str, str | None] = {module: None for module in modules}
        queue = deque((module, 0) for module in modules)
        while queue:
            current, used = queue.popleft()
            if used > best.get(current, lazy_hops + 1):
                continue
            for importer, lazy in self.importers.get(current, {}).items():
                cost = used + (1 if lazy else 0)
                if cost <= lazy_hops and cost < best.get(importer, lazy_hops + 1):
                    best[importer] = cost
                    came_from[importer] = current
                    if lazy:
                        queue.append((importer, cost))
                    else:
                        queue.appendleft((importer, cost))
        return came_from


def _is_test_file(path: Path) -> bool:
    return path.is_relative_to(TESTS) and path.name.startswith("test_") and path.suffix == ".py"


def all_test_files() -> list[Path]:
    """Every test file, including those in subfolders such as ``tests/unit``."""
    return sorted(path for path in TESTS.rglob("test_*.py")
                  if not set(path.relative_to(TESTS).parts[:-1]) & (_SKIP_DIRS | {"fixtures", "goldens"}))


def changed_files(base: str = "HEAD") -> list[Path]:
    def git(*args: str) -> list[str]:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        return [line.strip() for line in out.splitlines() if line.strip()]

    names = set(git("diff", "--name-only", base)) | set(git("ls-files", "--others", "--exclude-standard"))
    return sorted(ROOT / name for name in names)


def impacted_tests(changed: list[Path], graph: ImportGraph | None = None, lazy_hops: int = 1) -> dict[Path, str]:
    """Test files a change can affect, each with the reason it was selected."""
    graph = graph or ImportGraph()
    tests = all_test_files()
    selected: dict[Path, str] = {}
    modules: set[str] = set()
    for path in changed:
        rel = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)
        if path.name == "conftest.py" and path.parent == TESTS:
            return {test: "tests/conftest.py changed" for test in tests}
        if _is_test_file(path):
            if path.exists():
                selected[path] = "changed"
            continue
        module = graph.module_for(path) if path.suffix == ".py" else None
        if module is not None:
            modules.add(module)
            continue
        if path.suffix == ".py" or not path.exists() and path.suffix == "":
            continue
        # A non-Python file: the tests that name it.
        for test in tests:
            if test not in selected and (path.name in test.read_text(encoding="utf-8", errors="replace")):
                selected[test] = f"names {rel}"
    came_from = graph.affected(modules, lazy_hops)
    for test in tests:
        module = graph.module_for(test)
        if module in came_from and test not in selected:
            chain = [module]
            while came_from[chain[-1]] is not None:
                chain.append(came_from[chain[-1]])
            selected[test] = "imports " + " <- ".join(reversed(chain[1:])) if len(chain) > 1 else "changed"
    return dict(sorted(selected.items()))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base", default="HEAD", help="revision to diff against (default: HEAD)")
    parser.add_argument("--why", help="explain why one test file is (or is not) selected")
    parser.add_argument("--lazy-hops", type=int, default=1,
                        help="lazy (in-function) imports a chain may use (default 1; more selects more)")
    parser.add_argument("files", nargs="*", help="changed files (default: from git)")
    args = parser.parse_args()
    changed = [ROOT / name for name in args.files] if args.files else changed_files(args.base)
    selected = impacted_tests(changed, lazy_hops=args.lazy_hops)
    if args.why:
        target = (ROOT / args.why).resolve()
        print(selected.get(target, "not selected"))
        return 0
    for test, reason in selected.items():
        print(f"{test.relative_to(ROOT).as_posix()}  # {reason}")
    print(f"{len(selected)} of {len(all_test_files())} test files", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
