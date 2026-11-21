"""Waveform's checklist-16 conversion (Current_Plan.md N5.4; Native_Port_Playbook.md checklist 16): the Python renderer
draws the forms the native core draws, so parity is judged against this conversion.

- Every level chain a sampler reads is the box kernel (``rendering.gl_programs.mip_chain``): the planar reflection's
  and the floor maps', never ``glGenerateTextureMipmap`` (the lead's decision, 21 Nov).
- The floor's and the reflection's anisotropy is the shader's taps (``rendering.gl_programs.anisotropic``), the
  samplers at 1x (QRhi's sampler has none).
- Every fragment takes its derivatives before any lane can leave (Vulkan's discard ends the lane, R-210).
- The Pulse Rim field is a storage buffer read linearly in the shader (the core uploads no float texture per frame).
- Every ribbon and stray draw counts from vertex 0, its moving first vertex a block member (``uVertexBase``): the
  core's draw is a count (D15 point 6).
"""
from __future__ import annotations

import ctypes
import re
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _box(level, axis: int):
    """mip_box.comp's separable step along ``axis`` (numpy, float64; ``test_native_waveform_port_core``'s model)."""
    level = np.moveaxis(np.asarray(level, float), axis, 0)
    s = level.shape[0]
    if s == 1:
        out = level.copy()
    elif s % 2 == 0:
        out = 0.5 * level[0::2] + 0.5 * level[1::2]
    else:
        d = s // 2
        i = np.arange(d).reshape((-1,) + (1,) * (level.ndim - 1))
        out = ((d - i) * level[0:2 * d:2] + (i + 1) * level[2:2 * d + 1:2]) / s + d * level[1:2 * d:2] / s
    return np.moveaxis(out, 0, axis)


# ------------------------------------------------------------------------------------------------- the box chains

def driver_chains(source: str) -> int:
    """How many driver chains a source makes (``glGenerateTextureMipmap`` / ``glGenerateMipmap``)."""
    return len(re.findall(r"\bglGenerate(?:Texture)?Mipmap\b", source))


def test_the_reflection_and_the_floor_maps_take_the_box_kernel():
    for relative in ("rendering/quick/scene3d/reflection.py", "rendering/quick/scene3d/waveform.py"):
        source = _text(relative)
        assert driver_chains(source) == 0, relative
        assert "dispatch_mip_chain" in source, relative
        # No hardware anisotropy left on either (the taps are the shader's).
        assert "MAX_ANISOTROPY" not in source and "0x84FE" not in source, relative
    # Negative control: the former forms are seen.
    assert driver_chains("    gl.glGenerateTextureMipmap(self._colour)\n") == 1


@pytest.mark.qt
def test_the_reflection_chain_is_the_box_model_at_odd_sizes(qt_app):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking

    disable_per_call_gl_error_checking()
    from OpenGL import GL as gl

    from rendering.quick.scene3d.reflection import PlanarReflection
    from tools.labs.render_target import OffscreenRenderTarget

    width, height = 37, 23
    rng = np.random.default_rng(16)
    picture = rng.random((height, width, 4)).astype(np.float16)
    target = OffscreenRenderTarget(64, 64)
    reflection = PlanarReflection("conversion test")
    try:
        with target.current():
            reflection.begin(width, height)
            gl.glTextureSubImage2D(reflection.texture, 0, 0, 0, width, height, gl.GL_RGBA, gl.GL_HALF_FLOAT, picture)
            reflection.end()
            levels = []
            for level in range(1, max(width, height).bit_length()):
                w, h = max(1, width >> level), max(1, height >> level)
                out = np.zeros((h, w, 4), np.float32)
                gl.glGetTextureImage(reflection.texture, level, gl.GL_RGBA, gl.GL_FLOAT, out.nbytes,
                                     out.ctypes.data_as(ctypes.c_void_p))
                levels.append(out)
            # The driver's chain of the same picture (the negative control: it is not the box at these sizes).
            name = (gl.GLuint * 1)()
            gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, name)
            gl.glTextureStorage2D(name[0], max(width, height).bit_length(), gl.GL_RGBA16F, width, height)
            gl.glTextureSubImage2D(name[0], 0, 0, 0, width, height, gl.GL_RGBA, gl.GL_HALF_FLOAT, picture)
            gl.glGenerateTextureMipmap(name[0])
            driver = []
            for level in range(1, max(width, height).bit_length()):
                w, h = max(1, width >> level), max(1, height >> level)
                out = np.zeros((h, w, 4), np.float32)
                gl.glGetTextureImage(name[0], level, gl.GL_RGBA, gl.GL_FLOAT, out.nbytes,
                                     out.ctypes.data_as(ctypes.c_void_p))
                driver.append(out)
            gl.glDeleteTextures(1, name)
            reflection.release()
    finally:
        target.close()

    def box_steps(chain):
        """Whether every level of ``chain`` is the box of the level above it as stored (within one half-float step:
        the kernel sums in float and stores half)."""
        above = picture.astype(np.float64)
        for got in chain:
            model = _box(_box(above, 0), 1)
            ulp = np.spacing(np.abs(model).astype(np.float16)).astype(np.float64)
            if got.shape != model.shape or not (np.abs(got - model) <= ulp).all():
                return False
            above = got.astype(np.float64)
        return True

    assert len(levels) == 5 and box_steps(levels)
    # Negative control: the driver's chain (Python's former) is not the box at these sizes.
    assert not box_steps(driver)
