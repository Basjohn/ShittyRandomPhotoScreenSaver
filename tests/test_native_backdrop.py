"""N5.7b, the card-material backdrop pyramid on the native core (Current_Plan.md section N2b; D7 points 2 to 6), GPU-free:

- the core's passes are the Python pyramid's chain and arithmetic (``native/core/src/backdrop.cpp``'s pass table against
  ``surface_backdrop.py``'s constants; ``backdrop_down.frag``/``backdrop_up.frag`` against its ``_DOWN``/``_UP``), so
  each level the core builds is the level the Python pyramid builds (the GPU proof is
  ``native/core/python/backdrop_pyramid_check.py``);
- the route: ``SurfaceBackdropOwner`` takes the native source on the native background's backend and the Python one
  elsewhere, and maps the owner's edges onto the core's item (dimming handed over once per change, park and wake, no
  rate, retire destroys it).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "native" / "core"


# --------------------------------------------------------------------------- the passes are the Python pyramid's


def _python_chain() -> list[tuple[str, str, str]]:
    """The Python pyramid's passes as (kind, source, destination) by level name, from its own constants."""
    from rendering.quick.render import surface_backdrop as sb

    names = ["half", "quarter", "eighth", "sixteenth", "thirty_second"][: sb._LEVELS]
    chain = [("seed", "layer", names[0])]
    chain += [("down", a, b) for a, b in zip(names, names[1:])]
    chain.append(("up", names[sb._LIGHT_FROM - 1], "light"))
    scratch = ["scratch" for _index in range(sb._HEAVY_FROM - 2, 2, -1)]
    source = names[sb._HEAVY_FROM - 1]
    for name in scratch:
        chain.append(("up", source, name))
        source = name
    chain.append(("up", source, "heavy"))
    return chain


def _core_chain(text: str) -> list[tuple[str, str, str]]:
    table = re.search(r"constexpr PassSpec kPasses\[\] = \{(.*?)\};", text, re.S).group(1)
    names = {"kSourceLayer": "layer", "0": "half", "1": "quarter", "2": "eighth", "3": "sixteenth",
             "4": "thirty_second", "kScratch": "scratch", "kOutputLight": "light", "kOutputHeavy": "heavy"}
    rows = re.findall(r"\{\s*PassKind::(\w+),\s*(\w+),\s*(\w+)\s*\}", table)
    return [(kind.lower(), names[source], names[destination]) for kind, source, destination in rows]


def test_the_core_builds_the_python_pyramids_chain() -> None:
    text = (CORE / "src" / "backdrop.cpp").read_text(encoding="utf-8")
    assert _core_chain(text) == _python_chain()
    # Negative control: the light output read from another level is caught.
    altered = text.replace("{ PassKind::Up, 2, kOutputLight }", "{ PassKind::Up, 3, kOutputLight }")
    assert altered != text and _core_chain(altered) != _python_chain()


def _arithmetic(source: str) -> list[str]:
    """main()'s statements, with the half pixel named h (the Python passes read uHalfPixel itself or through h)."""
    body = re.search(r"void main\(\)\s*\{(.*)\}", source, re.S).group(1)
    statements = [re.sub(r"\s+", " ", s).strip() for s in body.split(";")]
    statements = [s for s in statements if s and not re.match(r"vec2 h = uHalfPixel(\.xy)?$", s)]
    return [s.replace("uHalfPixel", "h") for s in statements]


@pytest.mark.parametrize("python_name, core_file", [("_DOWN", "backdrop_down.frag"), ("_UP", "backdrop_up.frag")])
def test_the_core_passes_are_the_python_passes_term_for_term(python_name: str, core_file: str) -> None:
    from rendering.quick.render import surface_backdrop as sb

    python = _arithmetic(getattr(sb, python_name))
    core = _arithmetic((CORE / "shaders" / core_file).read_text(encoding="utf-8"))
    assert core == python
    # Negative control: one weight changed is caught.
    assert _arithmetic((CORE / "shaders" / core_file).read_text(encoding="utf-8").replace("/ 8.0", "/ 7.0")
                       .replace("/ 12.0", "/ 11.0")) != python


def test_every_core_shader_has_its_pack_staged_by_the_glob() -> None:
    cmake = (CORE / "CMakeLists.txt").read_text(encoding="utf-8")
    assert '"${CMAKE_CURRENT_SOURCE_DIR}/shaders/*.frag"' in cmake and "src/backdrop.cpp" in cmake
    for name in ("backdrop.vert", "backdrop_seed.frag", "backdrop_down.frag", "backdrop_up.frag", "clear.frag"):
        assert (CORE / "shaders" / name).is_file(), name
    text = (CORE / "src" / "backdrop.cpp").read_text(encoding="utf-8")
    for symbol in ("backdrop_vert_qsb", "backdrop_seed_frag_qsb", "backdrop_down_frag_qsb", "backdrop_up_frag_qsb"):
        assert symbol in text


def test_the_frame_driver_records_the_pyramid_after_the_background_layer_and_nothing_at_rest() -> None:
    driver = (CORE / "src" / "frame_driver.cpp").read_text(encoding="utf-8")
    edge = driver[driver.index("void FrameDriver::onBeforeRendering()"):driver.index("bool FrameDriver::recordBackdrop")]
    # At rest: the early return also needs the backdrop's one atomic to be clear.
    assert "if (!pass && !load && surfaces.isEmpty() && !backdropWanted)" in edge
    # The pyramids are recorded before the first surface that is not the background layer's.
    loop = edge[edge.index("for (const std::shared_ptr<Surface> &surface : surfaces)"):]
    assert loop.index("if (!background && !backdropsDone)") < loop.index("surface->record(")


# --------------------------------------------------------------------------- the route


class _FakeBackdrop:
    def __init__(self) -> None:
        from PySide6.QtQuick import QQuickItem

        self.item = QQuickItem()
        self.calls: list[tuple] = []
        self.destroyed = False

    def set_dimming(self, opacity: float) -> None:
        self.calls.append(("dimming", opacity))

    def set_parked(self, parked: bool) -> None:
        self.calls.append(("parked", parked))

    def state(self) -> dict:
        return {}

    def destroy(self) -> bool:
        self.destroyed = True
        self.calls.append(("destroy",))
        return True


class _FakeCore:
    def __init__(self) -> None:
        self.made: list[_FakeBackdrop] = []

    def backdrop(self, parent):
        backdrop = _FakeBackdrop()
        backdrop.item.setParentItem(parent)
        self.made.append(backdrop)
        return backdrop


def _root(dimming_enabled: bool, dimming: float):
    from PySide6.QtCore import QUrl
    from PySide6.QtQml import QQmlComponent, QQmlEngine

    engine = QQmlEngine()
    component = QQmlComponent(engine)
    component.setData(b"import QtQuick\nItem { width: 400; height: 300; property bool dimmingEnabled: false;"
                      b" property real dimmingOpacity: 0.0 }", QUrl())
    root = component.create()
    QQmlEngine.setObjectOwnership(root, QQmlEngine.ObjectOwnership.CppOwnership)
    root.setProperty("dimmingEnabled", dimming_enabled)
    root.setProperty("dimmingOpacity", dimming)
    return (engine, component), root


def test_the_owner_takes_the_core_backdrop_on_the_native_background_backend(qt_app, monkeypatch) -> None:
    from rendering.quick.render import native_surface_backdrop as nsb
    from rendering.quick.surface_backdrop_owner import BACKDROP_Z, SurfaceBackdropOwner

    core = _FakeCore()
    monkeypatch.setattr(nsb, "native_backdrop_core", lambda: core)
    engine, root = _root(True, 0.3)
    try:
        owner = SurfaceBackdropOwner(root, screen_index=0)
        assert owner.native is True and len(core.made) == 1
        backdrop = core.made[0]
        assert owner.item is backdrop.item and owner.item.z() == BACKDROP_Z
        assert owner.item.objectName() == "surfaceBackdropSource" and owner.item.width() == 400
        # The dimming over the wallpaper is handed over once, and again only when it changes.
        assert backdrop.calls == [("dimming", 0.3)]
        owner.note_background_changed()
        root.setWidth(500)                                   # geometry: the core follows the window itself
        owner.set_transition_active(True)                    # no rate on the native core
        owner.set_transition_active(False)
        assert backdrop.calls == [("dimming", 0.3)]
        root.setProperty("dimmingOpacity", 0.5)
        owner.note_background_changed()
        assert backdrop.calls[-1] == ("dimming", 0.5)
        # Demand 0 parks the core's item (every QRhi object goes); a wake hands the dimming over again.
        owner.park()
        assert owner.parked is True and backdrop.calls[-1] == ("parked", True)
        owner.note_background_changed()
        assert backdrop.calls[-1] == ("parked", True)
        owner.wake()
        assert owner.parked is False and backdrop.calls[-2:] == [("parked", False), ("dimming", 0.5)]
        # Retire: the native item is destroyed now (its consumers were unbound first by the controller).
        owner.retire()
        assert backdrop.destroyed is True and owner.retired is True
    finally:
        root.deleteLater()
        qt_app.processEvents()
        del engine


def test_without_a_core_there_is_no_backdrop_and_never_a_python_one(qt_app, monkeypatch) -> None:
    # N5.2h: one route per API; the degraded display (no core) keeps the cards' Normal fill, never the Python blit.
    from PySide6.QtQuick import QQuickItem

    from rendering.quick.render import native_surface_backdrop as nsb
    from rendering.quick.surface_backdrop_owner import SurfaceBackdropOwner, backdrop_available

    monkeypatch.setattr(nsb, "native_backdrop_core", lambda: None)
    engine, root = _root(False, 0.0)
    try:
        assert backdrop_available() is False
        with pytest.raises(RuntimeError, match="native core"):
            SurfaceBackdropOwner(root, screen_index=0)
        assert [child for child in root.childItems() if isinstance(child, QQuickItem)] == []
        monkeypatch.setattr(nsb, "native_backdrop_core", lambda: _FakeCore())                # control
        assert backdrop_available() is True
    finally:
        root.deleteLater()
        qt_app.processEvents()
        del engine


def test_the_native_backdrop_core_follows_the_native_background_backend(monkeypatch) -> None:
    from rendering.quick import bootstrap
    from rendering.quick.render import native_background, native_surface_backdrop as nsb

    sentinel = object()
    monkeypatch.setattr(bootstrap, "native_core", lambda: sentinel)
    monkeypatch.setattr(native_background, "native_background_wanted", lambda backend=None: True)
    assert nsb.native_backdrop_core() is sentinel
    monkeypatch.setattr(native_background, "native_background_wanted", lambda backend=None: False)
    assert nsb.native_backdrop_core() is None


def test_dimming_is_read_as_the_scene_computes_it(qt_app) -> None:
    from rendering.quick.render.native_surface_backdrop import dimming_opacity

    engine, root = _root(True, 1.7)
    try:
        assert dimming_opacity(root) == 1.0
        root.setProperty("dimmingEnabled", False)
        assert dimming_opacity(root) == 0.0
    finally:
        root.deleteLater()
        qt_app.processEvents()
        del engine
    from PySide6.QtQuick import QQuickItem

    plain = QQuickItem()
    assert dimming_opacity(plain) == 0.0


def test_the_native_backdrop_has_no_timer_or_frame_request_of_its_own() -> None:
    text = (ROOT / "rendering" / "quick" / "render" / "native_surface_backdrop.py").read_text(encoding="utf-8")
    for forbidden in ("QTimer", "FrameAnimation", "singleShot", "requestUpdate", "os.environ"):
        assert forbidden not in text
    core = (CORE / "src" / "backdrop.cpp").read_text(encoding="utf-8")
    for forbidden in ("QTimer", "startTimer", "qgetenv", "getenv"):
        assert forbidden not in core
