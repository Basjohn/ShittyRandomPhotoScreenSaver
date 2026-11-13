"""The Qt Quick shader packs are baked for every target and draw on both backends (Current_Plan.md item 8b, N2.7
leftovers: the bake before N2.8).

Every ``.vert``/``.frag`` under ``rendering/quick/qml/shaders`` is discovered (never listed) and its committed pack must
be exactly what ``tools/regen_qrc.py --shaders`` bakes from it: SPIR-V (Vulkan), the product's OpenGL GLSL and the
shipped targets. The drawing proof renders the product's own QML (MaterialSurface, WidgetInteractionGlow,
TextLegibilityPlate) in the native core's hidden host (never shown) on Vulkan and on OpenGL; the negative control is
the same scene with SPIR-V erased from the packs, which draws nothing on Vulkan.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from rendering.native import loader
from tools import regen_qrc

ROOT = Path(__file__).resolve().parents[1]
QML = ROOT / "rendering" / "quick" / "qml"
MODULE_DIR = ROOT / "release" / "native_module"
BUILT = os.name == "nt" and (MODULE_DIR / f"{loader.MODULE_NAME}.pyd").is_file()


def _qsb() -> Path:
    try:
        return regen_qrc.quick_shader_baker(sys.executable)
    except regen_qrc.QrcRegenerationError as exc:
        pytest.skip(f"no pinned PySide6 qsb here: {exc}")


def _target_names(targets: tuple[str, ...]) -> set[str]:
    """``("--glsl", "460,430", "--hlsl", "50")`` -> {"GLSL 460", "GLSL 430", "HLSL 50"}, as ``qsb -d`` names them."""
    return {f"{flag[2:].upper()} {version.strip()}"
            for flag, versions in zip(targets[0::2], targets[1::2]) for version in versions.split(",")}


def test_every_quick_shader_pack_is_current_and_holds_every_target():
    qsb = _qsb()
    sources = regen_qrc.quick_shader_sources()
    assert sources, "no Qt Quick shader source was found"
    stale = [f"{status.pack.name}: {status.reason}" for status in regen_qrc.quick_shader_status(qsb=qsb)
             if not status.current]
    assert not stale, "run tools/regen_qrc.py --shaders:\n" + "\n".join(stale)
    wanted = _target_names(regen_qrc.quick_shader_targets()) | {"SPIR-V 100"}
    for source in sources:
        dump = subprocess.run([str(qsb), "-d", str(source.with_name(source.name + ".qsb"))], capture_output=True,
                              text=True, timeout=120).stdout
        held = {line.split(":", 1)[1].split("[", 1)[0].strip() for line in dump.splitlines()
                if line.startswith("  Shader ")}
        assert wanted <= held, f"{source.name}: missing {sorted(wanted - held)}"


def test_the_product_opengl_glsl_comes_first_and_the_shipped_targets_follow():
    from rendering.quick.bootstrap import QUICK_GLSL_VERSION
    from tools.vulkan_shader_readiness import QSB_TARGETS

    targets = regen_qrc.quick_shader_targets()
    glsl = targets[targets.index("--glsl") + 1].split(",")
    assert glsl[0] == f"{QUICK_GLSL_VERSION[0]}{QUICK_GLSL_VERSION[1]:02d}"   # the variant OpenGL keeps drawing with
    assert _target_names(QSB_TARGETS) <= _target_names(targets)


def test_a_source_changed_without_a_bake_is_stale_until_baked(tmp_path):
    qsb = _qsb()
    source = regen_qrc.quick_shader_sources()[0]
    copy = tmp_path / source.name
    copy.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    pack = copy.with_name(copy.name + ".qsb")
    shutil.copyfile(source.with_name(source.name + ".qsb"), pack)
    assert [s.current for s in regen_qrc.quick_shader_status(qsb=qsb, shader_dir=tmp_path)] == [True]
    # A changed constant in main (the first float literal there) changes what the source bakes to.
    text = copy.read_text(encoding="utf-8")
    start = text.index("void main()")
    literal = re.search(r"\b\d+\.\d+\b", text[start:])
    assert literal is not None
    at = start + literal.start()
    copy.write_text(text[:at] + f"{float(literal.group(0)) + 0.25:.4f}" + text[start + literal.end():],
                    encoding="utf-8")
    before = pack.read_bytes()
    assert [s.current for s in regen_qrc.quick_shader_status(qsb=qsb, shader_dir=tmp_path)] == [False]
    assert [s.current for s in regen_qrc.bake_quick_shaders(qsb=qsb, shader_dir=tmp_path)] == [True]
    assert pack.read_bytes() != before


# ------------------------------------------------------------------------------------- the drawing proof, subprocesses

_CARDS = r'''
import json
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtQml import QQmlComponent, QQmlEngine
from rendering.quick import bootstrap

backend, state_dir, qml_dir = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
bootstrap.configure_quick_graphics(reason="quick-shader-packs", backend=backend, start_state_dir=state_dir)
app = QGuiApplication(sys.argv[:1])
chosen = bootstrap.start_quick_backend()
host = bootstrap.native_hidden_host(240, 120)          # the core's hidden host: never shown
SCENE = """
import QtQuick
Item {
    width: 240; height: 120
    Rectangle { anchors.fill: parent; color: "#203040" }
    Rectangle { id: backdrop; width: 240; height: 120; color: "#e0d8c8"; layer.enabled: true; layer.mipmap: true
                visible: false }
    MaterialSurface { x: 10; y: 10; width: 60; height: 60; backdrop: backdrop; material: "acrylic"; cornerRadius: 8
                      normalColor: "#ff101010"; tintColor: "#b3101010"; textColor: "#ffffffff" }
    WidgetInteractionGlow { x: 100; y: 24; width: 32; height: 32; glowColor: "#ffff4020"; cornerRadius: 6
                            hoverLevel: 0.8; intensityScale: 1.0 }
    Item {
        id: card
        x: 160; y: 10; width: 70; height: 60
        property var surfaceBackdrop: backdrop
        property color backgroundColor: "#00101010"
        property color surfaceTextColor: "#ffffffff"
        property real cornerRadius: 8
        property real padding: 8
        property real borderWidth: 0
        property var surfaceMaterialParameters: [Qt.vector4d(0, 0, 0, 1), Qt.vector4d(0, 0, 0, 0), Qt.vector4d(0, 0, 0, 1)]
        property real surfaceOpacityAdjust: 0.0
        property vector4d surfaceMaterialLimits: Qt.vector4d(0, 1, 1, 1)
        property real surfaceMaterialCeiling: 1.0
        TextLegibilityPlate { x: 6; y: 20; width: 58; height: 20; card: card; cardOrigin: Qt.point(6, 20)
                              runColor: "#ffffffff"; runPixelSize: 14 }
    }
}
"""
REGIONS = {"background": (90, 80, 140, 110), "material": (25, 25, 55, 55), "glow": (88, 18, 98, 62),
           "plate": (172, 33, 218, 47)}
engine = QQmlEngine()
component = QQmlComponent(engine)
component.setData(SCENE.encode("utf-8"), QUrl.fromLocalFile(str(qml_dir / "QuickShaderPacksProbe.qml")))
item = component.create()
assert item is not None, [error.toString() for error in component.errors()]
host.set_content(item)
host.frames(3)
frame = host.read()
image = QImage(frame.rgba, frame.width, frame.height, frame.width * 4, QImage.Format.Format_RGBA8888).copy()
if frame.y_up_in_framebuffer:
    from PySide6.QtCore import Qt
    image = image.flipped(Qt.Orientation.Vertical)
means = {}
for name, (x0, y0, x1, y1) in REGIONS.items():
    pixels = [image.pixelColor(x, y) for y in range(y0, y1) for x in range(x0, x1)]
    means[name] = [sum(getattr(c, channel)() for c in pixels) / len(pixels) for channel in ("red", "green", "blue")]
report = {"backend": chosen.api, "api": host.state().get("graphics_api"), "means": means}
host.set_content(None)
item.deleteLater()
QTimer.singleShot(0, app.quit)
app.exec()                           # the clean quit: the owner closes the kept hidden host
print("PROBE " + json.dumps(report), flush=True)
'''


def _render(backend: str, state_dir: Path, qml_dir: Path) -> dict:
    completed = subprocess.run([sys.executable, "-c", _CARDS, backend, str(state_dir), str(qml_dir)], cwd=ROOT,
                               env=os.environ.copy(), text=True, capture_output=True, check=False, timeout=120)
    lines = [line for line in completed.stdout.splitlines() if line.startswith("PROBE ")]
    assert completed.returncode == 0 and lines, completed.stdout + completed.stderr
    report = json.loads(lines[-1][len("PROBE "):])
    assert report["backend"] == report["api"] == backend
    return report["means"]


def _distance(a, b) -> float:
    return max(abs(x - y) for x, y in zip(a, b))


@pytest.mark.skipif(not BUILT, reason="the native core is not built in this checkout: no release/native_module/"
                                      f"{loader.MODULE_NAME}.pyd (only GitHub builds it)")
def test_the_cards_draw_on_vulkan_as_on_opengl_and_not_without_spirv(tmp_path):
    qsb = _qsb()
    on_opengl = _render("opengl", tmp_path / "state_gl", QML)
    on_vulkan = _render("vulkan", tmp_path / "state_vk", QML)
    for name in ("material", "glow", "plate"):
        assert _distance(on_opengl[name], on_opengl["background"]) > 8.0, name     # each element draws (OpenGL)
        assert _distance(on_vulkan[name], on_vulkan["background"]) > 8.0, name     # ... and on Vulkan
        # The same pixels within the static grain, whose gl_FragCoord origin differs between the backends.
        assert _distance(on_vulkan[name], on_opengl[name]) < 1.0, name

    # Negative control: the same QML with SPIR-V erased from its packs draws none of them on Vulkan.
    stripped = tmp_path / "qml"
    (stripped / "shaders").mkdir(parents=True)
    for name in ("MaterialSurface.qml", "SurfaceContrast.js", "WidgetInteractionGlow.qml", "TextLegibilityPlate.qml"):
        shutil.copyfile(QML / name, stripped / name)
    for pack in (QML / "shaders").glob("*.qsb"):
        erased = stripped / "shaders" / pack.name
        shutil.copyfile(pack, erased)          # qsb's erase mode rewrites its input in place: only ever the copy
        subprocess.run([str(qsb), "-e", "spirv,100", str(erased), "-o", str(erased)], check=True,
                       capture_output=True, timeout=120)
    assert all(b"SPIR-V" in subprocess.run([str(qsb), "-d", str(pack)], capture_output=True, timeout=120).stdout
               for pack in (QML / "shaders").glob("*.qsb")), "the product's packs were changed"
    without_spirv = _render("vulkan", tmp_path / "state_vk_control", stripped)
    for name in ("material", "glow", "plate"):
        assert _distance(without_spirv[name], without_spirv["background"]) < 1.0, name
