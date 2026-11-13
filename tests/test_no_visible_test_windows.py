"""No test shows a window on the operator's screen (a visible test window froze it once).

Every place a test shows a window (``show()``, ``showNormal()``, ``showFullScreen()``, ``showMaximized()``,
``showMinimized()``, ``showPopup()``, ``show_on_screen()``, or ``setVisible(True)`` on a window-like receiver) must make
that window invisible first, by a route ``tests/_invisible_windows.py`` names. What is accepted is derived from that
module, never from a list of test files:

- one of its public helpers applied to the receiver (``keep_off_screen(window)`` then ``window.show()``, or
  ``keep_off_screen(window).show()``), to the receiver's top-level (``keep_off_screen(widget.window())``) or, for
  ``combo.showPopup()``, to the popup window (``combo.view().window()``), in the same
  function, an enclosing function, or (for ``self.`` receivers) the same class;
- the inline copy of ``keep_off_screen``: the zero-argument opacity call it makes, on the receiver;
- the ``NEVER_ON_SCREEN_ATTRIBUTE`` widget attribute set on the receiver;
- a subprocess script (a string that imports PySide6) that runs on ``OFFSCREEN_PLATFORM``.

Tk top-levels (``tk.Tk()``, ``Toplevel(...)``) are mapped as soon as they are constructed, so every construction needs
one of the module's helpers (``keep_tk_off_screen``) applied to the new window in an enclosing scope.

Tools that tests run as ``python -m tools.<name>`` must import and call one of the helpers when they show windows.
Static and conservative: ``setVisible(True)`` on a scene item is not a window, so only window-like receiver names
count for it.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
PATTERN_MODULE = TESTS / "_invisible_windows.py"
SHOW_METHODS = frozenset({"show", "showNormal", "showFullScreen", "showMaximized", "showMinimized", "showPopup",
                          "show_on_screen"})
_WINDOW_LIKE = re.compile(r"(window|dialog|host|widget|view|popup|tab|editor|parent)$", re.IGNORECASE)


@dataclass(frozen=True)
class Pattern:
    helpers: frozenset[str]
    opacity_calls: frozenset[str]
    never_on_screen_attribute: str
    offscreen_platform: str


def load_pattern(path: Path = PATTERN_MODULE) -> Pattern:
    """What ``tests/_invisible_windows.py`` allows, read from its source."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    helpers = [node for node in tree.body if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")]
    constants = {
        target.id: node.value.value
        for node in tree.body if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
        for target in node.targets if isinstance(target, ast.Name)
    }
    opacity_calls = {
        call.func.attr
        for helper in helpers for call in ast.walk(helper)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
        and any(isinstance(arg, ast.Constant) and arg.value == 0 and not isinstance(arg.value, bool)
                for arg in call.args)
    }
    return Pattern(frozenset(helper.name for helper in helpers), frozenset(opacity_calls),
                   constants["NEVER_ON_SCREEN_ATTRIBUTE"], constants["OFFSCREEN_PLATFORM"])


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}


def _is_show(call: ast.Call) -> bool:
    if not isinstance(call.func, ast.Attribute):
        return False
    if call.func.attr in SHOW_METHODS:
        return True
    return (call.func.attr == "setVisible" and len(call.args) == 1 and isinstance(call.args[0], ast.Constant)
            and call.args[0].value is True and bool(_WINDOW_LIKE.search(ast.unparse(call.func.value))))


def _protects(node: ast.AST, receiver: str, pattern: Pattern, method: str) -> bool:
    # The window the call shows: the receiver, its top-level, or for a combo's showPopup its popup window.
    targets = {receiver, f"{receiver}.window()"}
    if method == "showPopup":
        targets.add(f"{receiver}.view().window()")
    for call in ast.walk(node):
        if not isinstance(call, ast.Call):
            continue
        func = call.func
        if isinstance(func, ast.Name) and func.id in pattern.helpers and call.args:
            if ast.unparse(call.args[0]) in targets:
                return True
        if isinstance(func, ast.Attribute) and ast.unparse(func.value) in targets:
            if func.attr in pattern.opacity_calls and any(
                    isinstance(arg, ast.Constant) and arg.value == 0 for arg in call.args):
                return True
            if func.attr == "setAttribute" and any(
                    isinstance(arg, ast.Attribute) and arg.attr == pattern.never_on_screen_attribute
                    for arg in call.args):
                return True
    return False


def _runs_offscreen(tree: ast.AST, pattern: Pattern) -> bool:
    return any(isinstance(node, ast.Constant) and node.value == pattern.offscreen_platform for node in ast.walk(tree))


def _visible_shows(tree: ast.Module, pattern: Pattern, *, script: bool) -> list[tuple[int, str]]:
    if script and _runs_offscreen(tree, pattern):
        return []
    parents = _parents(tree)
    found = []
    for call in ast.walk(tree):
        if not (isinstance(call, ast.Call) and _is_show(call)):
            continue
        receiver_node = call.func.value
        if isinstance(receiver_node, ast.Call) and isinstance(receiver_node.func, ast.Name) \
                and receiver_node.func.id in pattern.helpers:
            continue
        receiver = ast.unparse(receiver_node)
        scopes, node = [], call
        while node in parents:
            node = parents[node]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scopes.append(node)
            elif isinstance(node, ast.ClassDef) and receiver.startswith("self."):
                scopes.append(node)
        if not any(isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)) for scope in scopes):
            scopes.append(tree)                      # module-level script code
        if not any(_protects(scope, receiver, pattern, call.func.attr) for scope in scopes):
            found.append((call.lineno, ast.unparse(call)))
    return found


_TK_TOPLEVELS = frozenset({"Tk", "Toplevel"})


def _is_tk_toplevel(call: ast.Call) -> bool:
    """``tk.Tk()``, ``tkinter.Toplevel(...)``, a bare ``Tk()``: a Tk window, mapped as soon as it exists."""
    func = call.func
    name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else None
    return name in _TK_TOPLEVELS


def _visible_tk_windows(tree: ast.Module, pattern: Pattern) -> list[tuple[int, str]]:
    """Every Tk top-level whose receiver no helper of the pattern is applied to, in an enclosing scope."""
    parents = _parents(tree)
    found = []
    for call in ast.walk(tree):
        if not (isinstance(call, ast.Call) and _is_tk_toplevel(call)):
            continue
        parent = parents.get(call)
        if isinstance(parent, ast.Call) and isinstance(parent.func, ast.Name) and parent.func.id in pattern.helpers:
            continue                                  # keep_tk_off_screen(tk.Tk())
        receiver = None
        if isinstance(parent, ast.Assign) and len(parent.targets) == 1:
            receiver = ast.unparse(parent.targets[0])
        scopes, node = [], call
        while node in parents:
            node = parents[node]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                scopes.append(node)
        scopes.append(tree)
        protected = receiver is not None and any(
            isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name) and inner.func.id in pattern.helpers
            and inner.args and ast.unparse(inner.args[0]) == receiver
            for scope in scopes for inner in ast.walk(scope)
        )
        if not protected:
            found.append((call.lineno, ast.unparse(call)))
    return found


def _scripts(tree: ast.Module):
    """Subprocess scripts embedded as strings: (line of the string, parsed script)."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and "PySide6" in node.value:
            try:
                yield node.lineno, ast.parse(node.value)
            except SyntaxError:
                continue


def visible_shows_in_source(source: str, pattern: Pattern | None = None) -> list[tuple[int, str]]:
    """Every show of a window in this test source that no invisible route covers: (line, call)."""
    pattern = pattern or load_pattern()
    tree = ast.parse(source)
    found = _visible_shows(tree, pattern, script=False) + _visible_tk_windows(tree, pattern)
    for line, script in _scripts(tree):
        found += [(line + inner - 1, text) for inner, text in _visible_shows(script, pattern, script=True)]
    return sorted(found)


def _test_sources():
    for path in sorted(TESTS.rglob("*.py")):
        if path == PATTERN_MODULE or path == Path(__file__).resolve():
            continue
        yield path, path.read_text(encoding="utf-8")


def test_the_pattern_module_names_its_routes():
    pattern = load_pattern()
    assert "keep_off_screen" in pattern.helpers
    assert pattern.opacity_calls and pattern.never_on_screen_attribute and pattern.offscreen_platform


def test_no_test_shows_a_window_outside_the_invisible_pattern():
    pattern = load_pattern()
    offenders = [f"{path.relative_to(ROOT)}:{line}: {text}"
                 for path, source in _test_sources() for line, text in visible_shows_in_source(source, pattern)]
    assert not offenders, "windows shown without tests/_invisible_windows.py:\n" + "\n".join(offenders)


def test_tools_run_by_tests_keep_their_windows_off_screen():
    pattern = load_pattern()
    run = {match.group(1) for _path, source in _test_sources()
           for match in re.finditer(r"""["']tools\.(\w+)["']""", source)}
    offenders = []
    for name in sorted(run):
        path = ROOT / "tools" / f"{name}.py"
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        shows = [call for call in ast.walk(tree) if isinstance(call, ast.Call) and _is_show(call)]
        helper_calls = [call for call in ast.walk(tree) if isinstance(call, ast.Call)
                        and isinstance(call.func, ast.Name) and call.func.id in pattern.helpers]
        if shows and not helper_calls:
            offenders.append(f"tools/{name}.py:{shows[0].lineno}")
    assert not offenders, "tools run by tests show windows without an invisible helper: " + ", ".join(offenders)


# ---------------------------------------------------------------------------------------------------- negative controls
def test_a_direct_show_is_reported():
    source = "def test_window():\n    window = QQuickWindow()\n    window.show()\n"
    assert visible_shows_in_source(source) == [(3, "window.show()")]


def test_each_route_of_the_pattern_is_accepted_and_only_for_its_own_receiver():
    pattern = load_pattern()
    helper = sorted(pattern.helpers)[0]
    opacity = sorted(pattern.opacity_calls)[0]
    accepted = [
        f"def test_a():\n    window = make()\n    {helper}(window)\n    window.show()\n",
        f"def test_b():\n    {helper}(make()).show()\n",
        f"def test_c():\n    window = make()\n    window.{opacity}(0.0)\n    window.show()\n",
        f"def test_d():\n    w = make()\n    w.setAttribute(Qt.WidgetAttribute.{pattern.never_on_screen_attribute}, True)\n"
        "    w.show()\n",
        f"def test_e():\n    control = make()\n    {helper}(control.window())\n    control.show()\n",
    ]
    for source in accepted:
        assert visible_shows_in_source(source, pattern) == [], source
    other = f"def test_f():\n    a, b = make(), make()\n    {helper}(a)\n    b.show()\n"
    assert visible_shows_in_source(other, pattern) == [(4, "b.show()")]
    elsewhere = (f"def test_g():\n    window = make()\n    {helper}(window)\n\n"
                 "def test_h():\n    window = make()\n    window.show()\n")
    assert visible_shows_in_source(elsewhere, pattern) == [(7, "window.show()")]


def test_subprocess_scripts_are_scanned_and_offscreen_ones_accepted():
    pattern = load_pattern()
    script = "from PySide6.QtWidgets import QWidget\nhost = QWidget()\nhost.show()\n"
    visible = f"SCRIPT = '''\n{script}'''\n"
    assert [text for _line, text in visible_shows_in_source(visible, pattern)] == ["host.show()"]
    offscreen = f"SCRIPT = '''\nimport os\nos.environ['QT_QPA_PLATFORM'] = '{pattern.offscreen_platform}'\n{script}'''\n"
    assert visible_shows_in_source(offscreen, pattern) == []


def test_tk_windows_need_the_tk_helper_on_their_own_receiver():
    pattern = load_pattern()
    assert "keep_tk_off_screen" in pattern.helpers
    bare = "import tkinter as tk\ndef test_a():\n    root = tk.Tk()\n    root.withdraw()\n"
    assert visible_shows_in_source(bare, pattern) == [(3, "tk.Tk()")]
    toplevel = "def test_b():\n    top = tkinter.Toplevel(master)\n"
    assert visible_shows_in_source(toplevel, pattern) == [(2, "tkinter.Toplevel(master)")]
    accepted = [
        "def test_c():\n    root = tk.Tk()\n    keep_tk_off_screen(root)\n",
        "def test_d():\n    root = keep_tk_off_screen(tk.Tk())\n",
    ]
    for source in accepted:
        assert visible_shows_in_source(source, pattern) == [], source
    other = "def test_e():\n    a = tk.Tk()\n    b = tk.Tk()\n    keep_tk_off_screen(a)\n"
    assert visible_shows_in_source(other, pattern) == [(3, "tk.Tk()")]


def test_set_visible_counts_on_windows_not_on_scene_items():
    source = ("def test_a():\n    item = QQuickItem()\n    item.setVisible(True)\n"
              "    dialog = QDialog()\n    dialog.setVisible(True)\n")
    assert visible_shows_in_source(source) == [(5, "dialog.setVisible(True)")]
