"""Bounded driver admission of the registered Quick renderers, without providers or cadence."""
import json
from pathlib import Path
import subprocess
import sys

import pytest


def test_registered_visualizer_shaders_compile_and_retire():
    source = '''
import json
from importlib import import_module
from OpenGL import GL as gl
from rendering.quick.bootstrap import configure_quick_graphics
configure_quick_graphics(reason="qt611-shader-admission")
from tools.labs.render_target import OffscreenRenderTarget
from rendering.quick.visualizer.implementation_registry import iter_quick_visualizer_implementations
capture = OffscreenRenderTarget(64, 64)
assert tuple(map(int, gl.glGetString(gl.GL_VERSION).decode().split()[0].split(".")[:2])) >= (4, 6)
visualizers = []
try:
    for descriptor in iter_quick_visualizer_implementations():
        renderer = getattr(import_module(descriptor.module_name), descriptor.factory_name)()
        try:
            if callable(getattr(renderer, "_initialize", None)):
                renderer._initialize()
            else:
                # Renderers without an eager initialization API admit shaders
                # through their actual first production draw.
                from rendering.quick.visualizer.render_contract import QuickVisualizerRenderFrame
                from tools.onboarding_preview_foundry import _build_spectrum_preview_snapshot
                from tests._visualizer_frozen_settings import frozen_visualizer_settings
                snapshot = _build_spectrum_preview_snapshot(width=64, height=64, mode=descriptor.mode_id,
                    settings=frozen_visualizer_settings(descriptor.mode_id))
                matrix = (2/64,0,0,0, 0,-2/64,0,0, 0,0,1,0, -1,1,0,1)
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
                gl.glViewport(0,0,64,64)
                frame = QuickVisualizerRenderFrame(snapshot,(0,0,64,64),(64.,64.),matrix,capture.vao)
                if not getattr(snapshot.logical.mode_state, "ready", True):
                    # A mode whose frame is not ready without live PCM (Waveform) draws
                    # nothing; it admits its shaders through its production warm-up
                    # steps, which compile every program before readiness is checked.
                    # Bounded: once every program is warm a step returns at the
                    # readiness check without further GL work.
                    for _step in range(256):
                        renderer.prepare_step(frame)
                renderer.render(frame)
            assert renderer.has_resources, descriptor.mode_id
            visualizers.append(descriptor.mode_id)
        finally:
            gl.glUseProgram(0)
            renderer.release_resources()
        assert not renderer.has_resources, descriptor.mode_id
    assert gl.glGetError() == gl.GL_NO_ERROR
finally:
    capture.close()
print(json.dumps({"visualizers": visualizers}))
'''
    result = subprocess.run([sys.executable, "-c", source], cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    from rendering.quick.visualizer.implementation_registry import iter_quick_visualizer_implementations
    assert report["visualizers"] == [item.mode_id for item in iter_quick_visualizer_implementations()]


@pytest.mark.skipif(sys.platform != "win32", reason="Spectrum preview uses the Windows QPA")
def test_spectrum_preview_uses_the_production_opengl_floor(tmp_path):
    source = '''
import sys
from pathlib import Path
from PIL import Image
from tools import onboarding_preview_foundry as foundry
from tools.onboarding_preview_foundry import _render_spectrum_preview
from tests._visualizer_frozen_settings import frozen_visualizer_settings
# Test-owned frozen settings, never the mutable curated preset, decide the drawn bars' alpha.
production_build = foundry._build_spectrum_preview_snapshot
foundry._build_spectrum_preview_snapshot = lambda **kw: production_build(
    **kw, settings=frozen_visualizer_settings(kw.get("mode", "spectrum")))
path = Path(sys.argv[1])
_render_spectrum_preview(path, width=192, height=80)
image = Image.open(path)
assert image.mode == "RGBA" and image.size == (192, 80)
alpha = image.getchannel("A")
assert alpha.getextrema() == (0, 255)
assert alpha.histogram()[255] > 50
'''
    result = subprocess.run([sys.executable, "-c", source, str(tmp_path / "spectrum.png")],
                            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
