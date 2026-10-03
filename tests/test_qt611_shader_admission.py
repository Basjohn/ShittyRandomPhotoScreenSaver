"""Bounded driver admission of the registered Quick renderers, without providers or cadence."""
import json
from pathlib import Path
import subprocess
import sys

import pytest


def test_registered_transition_and_visualizer_shaders_compile_and_retire():
    source = '''
import json
from importlib import import_module
from OpenGL import GL as gl
from rendering.quick.bootstrap import configure_quick_graphics
configure_quick_graphics(reason="qt611-shader-admission")
from tools.transition_contact_sheet import TransitionCapture
from rendering.quick.transitions.implementation_registry import iter_quick_transition_implementations
from rendering.quick.visualizer.implementation_registry import iter_quick_visualizer_implementations
capture = TransitionCapture(64, 64)
assert tuple(map(int, gl.glGetString(gl.GL_VERSION).decode().split()[0].split(".")[:2])) >= (4, 6)
transitions, visualizers = [], []
try:
    for descriptor in iter_quick_transition_implementations():
        renderer = getattr(import_module(descriptor.module_name), descriptor.factory_name)()
        try:
            if callable(getattr(renderer, "_initialize", None)):
                renderer._initialize()
            if callable(getattr(renderer, "warm", None)):
                section = "blockspin" if descriptor.transition_id == "block_spins" else descriptor.transition_id
                setups = ({}, {"scene3d_detail": "High", section: {"antialiasing": "4x", "motion_blur": "On",
                           "motion_trails": "On", "bloom": "On", "edge_glass": "Both"}})
                for setup in setups:
                    run = capture.run(descriptor.transition_id, settings=setup)
                    for step in range(100):
                        if renderer.warm(run.request.parameter_dict()):
                            break
                    else:
                        raise AssertionError("shader warming never completed: " + descriptor.transition_id)
            elif not callable(getattr(renderer, "_initialize", None)):
                # These two renderers compile on their first draw, through the same mesh owner.
                run = capture.run(descriptor.transition_id)
                gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, capture.fbo)
                gl.glViewport(0, 0, capture.width, capture.height)
                renderer.render(capture.frame(run, .5))
            assert renderer.has_resources, descriptor.transition_id
            transitions.append(descriptor.transition_id)
        finally:
            renderer.release_resources()
        assert not renderer.has_resources, descriptor.transition_id
    for descriptor in iter_quick_visualizer_implementations():
        renderer = getattr(import_module(descriptor.module_name), descriptor.factory_name)()
        try:
            renderer._initialize()
            assert renderer.has_resources, descriptor.mode_id
            visualizers.append(descriptor.mode_id)
        finally:
            renderer.release_resources()
        assert not renderer.has_resources, descriptor.mode_id
    assert gl.glGetError() == gl.GL_NO_ERROR
finally:
    capture.close()
print(json.dumps({"transitions": transitions, "visualizers": visualizers}))
'''
    result = subprocess.run([sys.executable, "-c", source], cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout)
    from rendering.quick.transitions.implementation_registry import iter_quick_transition_implementations
    from rendering.quick.visualizer.implementation_registry import iter_quick_visualizer_implementations
    assert report["transitions"] == [item.transition_id for item in iter_quick_transition_implementations()]
    assert report["visualizers"] == [item.mode_id for item in iter_quick_visualizer_implementations()]


@pytest.mark.skipif(sys.platform != "win32", reason="Spectrum preview uses the Windows QPA")
def test_spectrum_preview_uses_the_production_opengl_floor(tmp_path):
    source = '''
import sys
from pathlib import Path
from PIL import Image
from tools.onboarding_preview_foundry import _render_spectrum_preview
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
