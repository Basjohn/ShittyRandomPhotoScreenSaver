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


# ------------------------------------------------------------------------------------------------ the anisotropy

def test_the_floor_reads_its_maps_and_the_reflection_through_the_taps():
    from rendering.gl_programs import reflection, waveform_ribbon
    from rendering.gl_programs.anisotropic import ANISOTROPIC_GLSL

    floor = waveform_ribbon.FLOOR_FRAGMENT
    assert floor.count("vec4 srpssAnisotropic(") == 1 and ANISOTROPIC_GLSL in reflection.PLANAR_REFLECTION_GLSL
    for sampler in ("uAlbedo", "uRoughness", "uSlope"):
        # Every read of a map with mips is a tapped read or an explicit level (the 1x1 mean).
        reads = re.findall(rf"(\w+)\(\s*{sampler}\b", floor)
        assert reads and set(reads) <= {"mapRead", "textureLod"}, (sampler, reads)
    column = floor.split("vec3 columnReflection(")[1].split("\n}\n")[0]
    assert "srpssAnisotropic(uReflection" in column and not re.search(r"textureGrad\(\s*uReflection", column)
    # Negative control: the former implicit read is seen.
    assert set(re.findall(r"(\w+)\(\s*uAlbedo\b", "texture(uAlbedo,uv,uHot.w)")) - {"mapRead", "textureLod"}


# ------------------------------------------------------------------------------------------------- the derivatives

def _waveform_fragments() -> dict[str, str]:
    from rendering.gl_programs import ribbon, ribbon_bursts, waveform_atmosphere, waveform_ribbon

    return {"floor": waveform_ribbon.FLOOR_FRAGMENT, "sky": waveform_atmosphere.SKY_FRAGMENT,
            "body": ribbon.RIBBON_BODY_FRAGMENT, "light": ribbon.RIBBON_LIGHT_FRAGMENT,
            "strays": ribbon.RIBBON_COHORT_STRAY_FRAGMENT, "bursts": ribbon_bursts.FRAGMENT}


def test_every_waveform_fragment_takes_its_derivatives_before_any_lane_leaves():
    from tests.test_shader_derivatives import late_derivatives

    for name, source in _waveform_fragments().items():
        assert late_derivatives(source) == [], name
    # Negative control: the floor as it was, the miss discarded before its gradients and map reads.
    floor = _waveform_fragments()["floor"]
    early = floor.replace("    bool hit=floorWorldHit(vWorldPos,groundDepth);\n",
                          "    bool hit=floorWorldHit(vWorldPos,groundDepth);\n    if(!hit)discard;\n", 1)
    assert early != floor and late_derivatives(early)


# ----------------------------------------------------------------------------------------------- the pulse field

_PULSE_PROBE = """#version 460 core
layout(local_size_x=64) in;
uniform vec4 uPulseRim;
uniform vec2 uPulseRimShape;
layout(std430,binding=3) writeonly buffer Out { float outValues[]; };
layout(std430,binding=4) readonly buffer At { float atX[]; };
%s
void main() {
    uint i=gl_GlobalInvocationID.x;
    if(i>=uint(atX.length())) return;
    outValues[i]=pulseRimField(atX[i]);
}
"""


@pytest.mark.qt
def test_the_pulse_field_is_read_linearly_with_its_edges_held(qt_app):
    from rendering.gl_error_policy import disable_per_call_gl_error_checking

    disable_per_call_gl_error_checking()
    from OpenGL import GL as gl

    from rendering.gl_programs.ribbon import PULSE_RIM_BINDING, PULSE_RIM_GLSL
    from rendering.quick.render.gl_resources import compile_compute_program, delete_program
    from rendering.quick.scene3d.pulse_rim import FIRST, LAST, SAMPLES, STEP, PulseRimField
    from tools.labs.render_target import OffscreenRenderTarget

    rng = np.random.default_rng(385)
    field = rng.random(SAMPLES).astype(np.float32)
    xs = np.concatenate((np.linspace(FIRST - 3.0, LAST + 3.0, 1001), np.asarray(FIRST + STEP * np.arange(SAMPLES))))
    xs = xs.astype(np.float32)

    def model(rim):
        """The field's clamp-to-edge linear read, three binomial taps (float64)."""
        u0 = (xs.astype(np.float64) - rim[0]) * rim[1]

        def tap(u):
            s = u * SAMPLES - 0.5
            i = np.floor(s)
            a = np.clip(i, 0, SAMPLES - 1).astype(int)
            b = np.clip(i + 1, 0, SAMPLES - 1).astype(int)
            return field[a] + (field[b] - field[a]) * (s - i)
        return 0.25 * tap(u0 - rim[3]) + 0.5 * tap(u0) + 0.25 * tap(u0 + rim[3])

    target = OffscreenRenderTarget(16, 16)
    owner = PulseRimField()
    try:
        with target.current():
            buffer, rim, _shape = owner.update(field.tobytes(), 1.0)
            source = _PULSE_PROBE % PULSE_RIM_GLSL.replace("uniform vec4 uPulseRim;", "").replace(
                "uniform vec2 uPulseRimShape;", "")
            program = compile_compute_program(source, label="pulse probe")
            names = (gl.GLuint * 2)()
            gl.glCreateBuffers(2, names)
            gl.glNamedBufferStorage(names[0], xs.nbytes, None, gl.GL_DYNAMIC_STORAGE_BIT)
            gl.glNamedBufferStorage(names[1], xs.nbytes, xs, gl.GL_DYNAMIC_STORAGE_BIT)
            gl.glUseProgram(program)
            gl.glUniform4f(gl.glGetUniformLocation(program, "uPulseRim"), *rim)
            gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, PULSE_RIM_BINDING, buffer)
            gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 3, names[0])
            gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 4, names[1])
            gl.glDispatchCompute((xs.size + 63) // 64, 1, 1)
            gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT)
            got = np.zeros(xs.size, np.float32)
            gl.glGetNamedBufferSubData(names[0], 0, got.nbytes, got.ctypes.data_as(ctypes.c_void_p))
            gl.glDeleteBuffers(2, names)
            delete_program(program)
            owner.release()
    finally:
        target.close()
    expected = model(rim)
    assert np.abs(got - expected).max() <= 1e-4    # float32 coordinates: s = u * n carries ~1e-5
    # Negative control: a read half a sample off (texel centres at i / n) is not the field's.
    shifted = model((rim[0] - 0.5 * STEP, *rim[1:]))
    assert np.abs(got - shifted).max() > 1e-2


# ------------------------------------------------------------------------------------------- the draws from vertex 0

def nonzero_first_draws(source: str) -> list[str]:
    """Every ``glDrawArraysInstanced`` call whose first vertex is not the literal 0."""
    return [call for call in re.findall(r"glDrawArraysInstanced\(([^;\n]*)\)", source)
            if call.split(",")[1].strip() != "0"]


def test_every_ribbon_draw_counts_from_vertex_zero():
    from rendering.gl_programs import ribbon

    source = _text("rendering/quick/scene3d/ribbon.py")
    assert nonzero_first_draws(source) == []
    # The body and both extensions are one draw: consecutive parts, each with its first vertex in the culled strip.
    continuous = ribbon.RIBBON_CONTINUOUS_VERTEX
    for member in ("uDrawCounts", "uDrawBases", "uContinuationBefore", "uContinuationAfter"):
        assert member in continuous, member
    assert "uContinuation;" not in continuous and continuous.count("int vertexId=drawnVertex;") == 2
    # The strays keep one draw with their first vertex in the block.
    assert "int vertexId=srpssVertexIndex+uVertexBase;" in ribbon.RIBBON_COHORT_STRAY_VERTEX
    # Negative control: the former culled draws.
    assert nonzero_first_draws("gl.glDrawArraysInstanced(gl.GL_TRIANGLES,body[0],body[1],packet.instances)")
