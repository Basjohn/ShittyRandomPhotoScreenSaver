"""N5.2h, the switch's delete sub-box: the Python presenter, its texture bridge, the blit backdrop and the Python
transition host are gone, and nothing in the product, the tools, the native checks or the tests imports them or the
availability answer that chose them (``background_family_available_on_backend``) again.

Read from the source text (no import): a module that came back, or an importer of one, fails by name."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DELETED = (
    "rendering.quick.render.background_image_node", "rendering.quick.render.background_node",
    "rendering.quick.render.image_textures", "rendering.quick.render.native_texture_bridge",
    "rendering.quick.render.surface_backdrop", "rendering.quick.transitions.render_host",
)
NAMES = ("background_family_available_on_backend", "BACKGROUND_FAMILY_BACKENDS", "_publishes_frame_presented")
#: Names deleted from modules that stay: the Python transition host's GL capture (now ``NativeTransitionCapture``).
DELETED_NAMES = {"tools.transition_contact_sheet": ("TransitionCapture",)}
RECORD_ONLY = "# record mode only"
SCANNED = ("rendering", "core", "ui", "widgets", "tools", "native/core/python", "tests")


def _sources():
    for top in SCANNED:
        for path in (ROOT / top).rglob("*.py"):
            if path.resolve() != Path(__file__).resolve():
                yield path


def _patterns(dotted: str):
    package, module = dotted.rsplit(".", 1)
    return (re.compile(rf"\b{re.escape(dotted)}\b"),
            re.compile(rf"from\s+{re.escape(package)}\s+import\s+[^\n]*\b{module}\b"),
            re.compile(rf"from\s+\.+\s*import\s+[^\n]*\b{module}\b(?!_)"),
            re.compile(rf"from\s+\.+{module}\s+import"))


def _importers(dotted: str) -> list[str]:
    hits = []
    for path in _sources():
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(ROOT).as_posix()
        if relative.startswith("native/core/python/"):
            # A reference check records its Python references live only with --python-references record, on a
            # checkout that still holds the Python route (transition_references.py): those imports carry the marker.
            text = "\n".join(line for line in text.split("\n") if not line.endswith(RECORD_ONLY))
        # Docstrings and comments name the deleted modules' history: only code lines count.
        text = "\n".join(line for line in text.split("\n") if re.match(r"\s*(from|import)\s", line))
        if dotted.endswith(".render_host") and relative.startswith("rendering/quick/visualizer/"):
            # The Visualizer's own render_host (rendering.quick.visualizer.render_host) is another module.
            text = re.sub(r"from\s+\.render_host\s+import", "", text)
        if any(pattern.search(text) for pattern in _patterns(dotted)):
            hits.append(relative)
    return hits


def test_the_deleted_python_route_modules_are_gone():
    present = [dotted for dotted in DELETED if (ROOT / Path(*dotted.split("."))).with_suffix(".py").exists()]
    assert present == []


def test_nothing_imports_a_deleted_python_route_module():
    found = {dotted: _importers(dotted) for dotted in DELETED}
    assert {dotted: hits for dotted, hits in found.items() if hits} == {}


def _name_importers(module: str, name: str) -> list[str]:
    """Code lines importing ``name`` from ``module`` (a line ending in the record-only marker excepted), and the
    module still defining it."""
    pattern = re.compile(rf"from\s+{re.escape(module)}\s+import\s+[^\n#]*\b{name}\b")
    hits = []
    for path in _sources():
        lines = path.read_text(encoding="utf-8", errors="replace").split("\n")
        if any(pattern.search(line) and not line.rstrip().endswith(RECORD_ONLY) for line in lines):
            hits.append(path.relative_to(ROOT).as_posix())
    owner = (ROOT / Path(*module.split("."))).with_suffix(".py")
    if re.search(rf"^(class|def)\s+{name}\b|^{name}\s*=", owner.read_text(encoding="utf-8"), re.MULTILINE):
        hits.append(f"{owner.relative_to(ROOT).as_posix()} (defines it)")
    return hits


def test_nothing_imports_a_deleted_python_route_name():
    found = {f"{module}.{name}": _name_importers(module, name)
             for module, names in DELETED_NAMES.items() for name in names}
    assert {name: hits for name, hits in found.items() if hits} == {}


def test_nothing_names_the_python_route_selectors():
    found = {name: sorted(path.relative_to(ROOT).as_posix() for path in _sources()
                          if name in path.read_text(encoding="utf-8", errors="replace")) for name in NAMES}
    assert {name: hits for name, hits in found.items() if hits} == {}


def test_the_render_package_exports_none_of_the_python_route():
    import rendering.quick.render as render

    gone = ("BackgroundRenderNode", "SlideProofState", "PresentationTextureBinding", "PresentationTextureHost")
    assert [name for name in gone if hasattr(render, name) or name in getattr(render, "__all__", ())] == []
