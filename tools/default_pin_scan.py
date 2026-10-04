"""Flag test asserts that pin a canonical default's current value: python tools/default_pin_scan.py

Heuristic for Current_Plan N2 (tests must not depend on values the operator edits): an assert that names a
canonical settings key and compares against a literal equal to that key's current default. Expect false
positives (a test that sets a value and checks it round-trips); review each file before changing it.
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.settings.default_settings import DEFAULT_SETTINGS  # noqa: E402


def flatten(node, out):
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, dict):
                flatten(v, out)
            else:
                out.setdefault(str(k), []).append(v)
    return out


defaults = flatten(DEFAULT_SETTINGS, {})
hits = []
for path in sorted((ROOT / "tests").glob("test_*.py")):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        continue
    lines = path.read_text(encoding="utf-8").splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        consts = [n.value for n in ast.walk(node.test) if isinstance(n, ast.Constant)]
        keys = [c for c in consts if isinstance(c, str) and c in defaults]
        literals = [c for c in consts if not (isinstance(c, str) and c in defaults)]
        for key in keys:
            for value in defaults[key]:
                if isinstance(value, bool) or value in (None, "", 0, 0.0, 1, 1.0):
                    continue          # too generic to call a pin
                if value in literals or (isinstance(value, list) and any(isinstance(l, (list, tuple)) for l in literals)):
                    hits.append((path.name, node.lineno, key, value, lines[node.lineno - 1].strip()[:110]))
hits = sorted(set(hits))
by_file = {}
for hit in hits:
    by_file[hit[0]] = by_file.get(hit[0], 0) + 1
if "--summary" in sys.argv:
    for name, count in sorted(by_file.items(), key=lambda item: -item[1]):
        print(f"{count:4d}  {name}")
else:
    for hit in hits:
        print(*hit, sep=" | ")
print(len(hits), "candidate pins in", len(by_file), "files")
