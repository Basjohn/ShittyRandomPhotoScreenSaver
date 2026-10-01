"""Phase A1 contracts for the production Qt Quick process bootstrap."""

from __future__ import annotations

import gc
import os
from pathlib import Path
import re
import subprocess
import sys
import weakref

import pytest

from rendering.quick import bootstrap


ROOT = Path(__file__).resolve().parents[1]


def test_environment_bootstrap_forces_threaded_loop_and_real_qml_root(monkeypatch):
    existing = str(ROOT / "existing-qml-import")
    monkeypatch.setenv("QSG_RENDER_LOOP", "basic")
    monkeypatch.setenv("QML_IMPORT_PATH", existing)

    qml_root = bootstrap.configure_quick_environment()

    assert os.environ["QSG_RENDER_LOOP"] == "threaded"
    assert qml_root == ROOT / "rendering" / "quick" / "qml"
    assert qml_root.is_dir()
    assert (qml_root / "qmldir").is_file()
    assert os.environ["QML_IMPORT_PATH"].split(os.pathsep) == [
        str(qml_root),
        existing,
    ]


def test_environment_bootstrap_is_idempotent(monkeypatch):
    monkeypatch.delenv("QML_IMPORT_PATH", raising=False)

    first = bootstrap.configure_quick_environment()
    second = bootstrap.configure_quick_environment()

    assert first == second
    assert os.environ["QML_IMPORT_PATH"].split(os.pathsep) == [str(first)]


def test_main_bootstraps_environment_before_qt_and_graphics_before_application():
    source = (ROOT / "main.py").read_text(encoding="utf-8")

    assert source.index("configure_quick_environment()") < source.index(
        "from PySide6.QtWidgets import QApplication"
    )
    assert source.index("configure_quick_graphics(reason=\"startup\")") < source.index(
        "app = QApplication(sys.argv)"
    )


@pytest.mark.parametrize("entrypoint", ["production", "flicker", "resize", "stack"])
def test_graphics_bootstrap_selects_proven_opengl_profile_in_clean_process(entrypoint):
    script = r'''
import json
import os
import sys
import tempfile
from pathlib import Path

from rendering.quick.bootstrap import configure_quick_graphics, quick_qml_root

if sys.argv[1] == "flicker":
    from tools.flicker_test import _apply_main_py_setup
    _apply_main_py_setup()
elif sys.argv[1] in ("resize", "stack"):
    with tempfile.TemporaryDirectory(prefix="srpss-gl46-capture-") as directory:
        output = Path(directory) / "capture"
        if sys.argv[1] == "resize":
            from tools.ordinary_widget_resize_capture import capture
            capture(output, families=("weather",))
        else:
            from tools.ordinary_widget_stack_capture import capture
            capture(output)
else:
    configure_quick_graphics(reason="a1-subprocess")

from PySide6.QtGui import QSurfaceFormat
from PySide6.QtQuick import QQuickWindow, QSGRendererInterface

fmt = QSurfaceFormat.defaultFormat()
print(json.dumps({
    "render_loop": os.environ.get("QSG_RENDER_LOOP"),
    "graphics_api": QQuickWindow.graphicsApi().name,
    "major": fmt.majorVersion(),
    "minor": fmt.minorVersion(),
    "profile": fmt.profile().name,
    "renderable": fmt.renderableType().name,
    "swap_interval": fmt.swapInterval(),
    "qml_root": str(quick_qml_root()),
}))
'''
    env = os.environ.copy()
    env["QSG_RENDER_LOOP"] = "basic"
    completed = subprocess.run(
        [sys.executable, "-c", script, entrypoint],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=45,
    )

    assert completed.returncode == 0, completed.stderr
    import json

    report = json.loads(completed.stdout.strip().splitlines()[-1])
    assert report == {
        "render_loop": "threaded",
        "graphics_api": "OpenGL",
        "major": 4,
        "minor": 6,
        "profile": "CoreProfile",
        "renderable": "OpenGL",
        "swap_interval": 0,
        "qml_root": str(ROOT / "rendering" / "quick" / "qml"),
    }


def test_empty_production_display_window_validates_its_actual_context_before_any_image_node():
    script = r'''
import json
import os
import sys

from rendering.quick.bootstrap import configure_quick_graphics
configure_quick_graphics(reason="empty-display-window-probe")

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickItem
from rendering.quick.state import QuickWindowPolicy
from rendering.quick import window as quick_window
from rendering.quick.window import QuickDisplayWindow

app = QGuiApplication(sys.argv)
screen = app.primaryScreen()
if screen is None:
    raise RuntimeError("probe has no primary screen")
state = {"scene_graph_initialized": False, "validations": []}
_canonical_validator = quick_window.validate_or_quit_current_opengl_context


def _recording_validator(**kwargs):
    info = _canonical_validator(**kwargs)
    state["validations"].append({
        "reason": kwargs["reason"],
        "actual_gl": list(info.actual_gl),
        "actual_glsl": list(info.actual_glsl),
        "capabilities": dict(info.capabilities),
    })
    return info


quick_window.validate_or_quit_current_opengl_context = _recording_validator
window = QuickDisplayWindow(
    screen_index=0,
    runtime_generation=1,
    screen=screen,
    policy=QuickWindowPolicy(),
)
# A real empty QQuickWindow has no scene work to synchronize on some Qt/driver
# pairs.  This content-free item requests the first scene graph without
# constructing an image or the retained background node under test.
scene_probe_item = QQuickItem()
scene_probe_item.setParentItem(window.contentItem())
scene_probe_item.setWidth(1.0)
scene_probe_item.setHeight(1.0)


class Completion(QObject):
    initialized = Signal()


completion = Completion()


def finish():
    # Run on the GUI event loop after every DirectConnection slot for this
    # sceneGraphInitialized emission has returned.  In particular, the window
    # validator may be connected after this test observer.
    print("PROBE " + json.dumps(state), flush=True)
    os._exit(0)

def observed():
    state["scene_graph_initialized"] = True
    completion.initialized.emit()

window.sceneGraphInitialized.connect(observed, Qt.ConnectionType.DirectConnection)
completion.initialized.connect(finish, Qt.ConnectionType.QueuedConnection)
window.setOpacity(0.0)
window.setFlag(Qt.WindowType.WindowTransparentForInput, True)
window.setFlag(Qt.WindowType.Tool, True)
# Exercise the production window's first scene graph without asserting the
# separate queued physical-placement path in this context-startup probe.
window.show()
window.requestUpdate()
QTimer.singleShot(5000, lambda: (print("PROBE " + json.dumps(state), flush=True), os._exit(2)))
app.exec()
'''
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        check=False,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    lines = [line for line in completed.stdout.splitlines() if line.startswith("PROBE ")]
    assert lines, completed.stdout + completed.stderr

    import json

    report = json.loads(lines[-1][len("PROBE "):])
    assert report["scene_graph_initialized"] is True
    assert len(report["validations"]) == 1
    validation = report["validations"][0]
    assert validation["reason"] == "quick-display-scene-graph-screen-0-generation-1"
    assert validation["actual_gl"] >= [4, 6]
    assert validation["actual_glsl"] >= [4, 60]
    assert all(validation["capabilities"].values())


class _FakeSignal:
    def __init__(self) -> None:
        self._callbacks = []

    def connect(self, callback) -> None:
        self._callbacks.append(callback)

    def emit(self) -> None:
        for callback in tuple(self._callbacks):
            callback()


class _FakeContextFormat:
    def __init__(
        self,
        version: tuple[int, int] = (4, 6),
        profile_name: str = "CoreProfile",
    ) -> None:
        self._version = version
        self._profile_name = profile_name

    def profile(self):
        return type("FakeProfile", (), {"name": self._profile_name})()

    def majorVersion(self) -> int:  # noqa: N802
        return self._version[0]

    def minorVersion(self) -> int:  # noqa: N802
        return self._version[1]


class _FakeContext:
    def __init__(
        self,
        version: tuple[int, int] = (4, 6),
        profile_name: str = "CoreProfile",
    ) -> None:
        self.destroyed = _FakeSignal()
        self._format = _FakeContextFormat(version, profile_name)

    def format(self) -> _FakeContextFormat:
        return self._format


class _FakeGl:
    GL_VERSION = 1
    GL_SHADING_LANGUAGE_VERSION = 2
    GL_VENDOR = 3
    GL_RENDERER = 4

    def __init__(self) -> None:
        self.calls = []
        self._strings = {
            self.GL_VERSION: b"4.6.0 TestGL",
            self.GL_SHADING_LANGUAGE_VERSION: b"4.60 TestGLSL",
            self.GL_VENDOR: b"Test vendor",
            self.GL_RENDERER: b"Test renderer",
        }
        for entry_points in bootstrap._REQUIRED_GL_ENTRY_POINTS.values():
            for entry_point in entry_points:
                setattr(self, entry_point, lambda: None)

    def glGetString(self, token):  # noqa: N802
        self.calls.append(token)
        return self._strings[token]


def test_actual_context_validation_logs_capabilities_once_and_revalidates_after_retirement():
    context = _FakeContext()
    gl = _FakeGl()

    first = bootstrap.validate_current_opengl_context(
        reason="test", context=context, gl_api=gl,
    )
    second = bootstrap.validate_current_opengl_context(
        reason="test", context=context, gl_api=gl,
    )

    assert first is second
    assert first.actual_gl == (4, 6)
    assert first.actual_glsl == (4, 60)
    assert dict(first.capabilities) == {
        "direct_state_access": True,
        "immutable_storage": True,
        "shader_storage_buffers": True,
        "compute": True,
        "multi_draw_indirect": True,
    }
    assert len(gl.calls) == 4  # one startup query, never a frame-time query

    context.destroyed.emit()
    bootstrap.validate_current_opengl_context(reason="test", context=context, gl_api=gl)
    assert len(gl.calls) == 8


def test_actual_context_validation_rejects_callable_but_unresolved_gl_entry_point():
    class _NullEntryPoint:
        def __call__(self):
            return None

        def __bool__(self) -> bool:
            return False

    context = _FakeContext()
    gl = _FakeGl()
    gl.glCreateBuffers = _NullEntryPoint()

    with pytest.raises(RuntimeError, match="direct_state_access"):
        bootstrap.validate_current_opengl_context(
            reason="test-null-entry", context=context, gl_api=gl,
        )


@pytest.mark.parametrize(
    ("context", "actual_gl", "expected"),
    [
        (_FakeContext(version=(4, 5)), b"4.5.0 TestGL", "context_gl=4.5"),
        (_FakeContext(profile_name="CompatibilityProfile"), b"4.6.0 TestGL", "profile=CompatibilityProfile"),
    ],
)
def test_actual_context_validation_rejects_a_lower_or_non_core_context(
    context,
    actual_gl,
    expected,
):
    gl = _FakeGl()
    gl._strings[gl.GL_VERSION] = actual_gl

    with pytest.raises(RuntimeError, match="production requirement was not met") as error:
        bootstrap.validate_current_opengl_context(
            reason="test-incompatible", context=context, gl_api=gl,
        )
    assert expected in str(error.value)


def test_actual_context_validation_evicts_a_collected_wrapper_before_qt_destruction():
    context = _FakeContext()
    gl = _FakeGl()
    context_key = id(context)
    wrapper_ref = weakref.ref(context)

    bootstrap.validate_current_opengl_context(reason="test-gc", context=context, gl_api=gl)
    assert context_key in bootstrap._validated_contexts

    del context
    gc.collect()

    assert wrapper_ref() is None
    assert context_key not in bootstrap._validated_contexts


def test_runtime_and_diagnostic_glsl_sources_have_one_460_core_contract():
    shader_paths = [
        path
        for root in (ROOT / "rendering", ROOT / "widgets", ROOT / "tools")
        for path in root.rglob("*")
        if path.suffix in {".py", ".frag", ".vert", ".geom", ".comp", ".glsl"}
    ]
    declared = []
    for path in shader_paths:
        source = path.read_text(encoding="utf-8")
        declared.extend((path, version, profile) for version, profile in re.findall(
            r"#version\s+(\d+)\s*(core)?", source,
        ))

    assert declared
    mismatches = [
        (str(path.relative_to(ROOT)), version, profile)
        for path, version, profile in declared
        if version != "460" or profile != "core"
    ]
    assert not mismatches, mismatches



def test_quick_bootstrap_keeps_installed_release_era_uncapped_policy():
    source = (ROOT / "rendering" / "quick" / "bootstrap.py").read_text(encoding="utf-8")
    generic = (ROOT / "rendering" / "gl_format.py").read_text(encoding="utf-8")

    assert "QUICK_SWAP_INTERVAL = 0" in source
    assert "surface_format.setSwapInterval(QUICK_SWAP_INTERVAL)" in source
    # Installed mixed-refresh validation rejected forcing interval 1. Quick and
    # the generic helper currently agree on interval 0; any future presentation
    # change requires installed frame-pacing/freshness evidence, not docs alone.
    assert "swap_interval = 0" in generic


def test_quick_package_contains_no_prohibited_presenter_or_fallback():
    package_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "rendering" / "quick").rglob("*.py")
    )
    for forbidden in (
        "QQuickWidget",
        "QRhiWidget",
        "DisplayWidgetCompatibilityFacade",
    ):
        assert forbidden not in package_source
