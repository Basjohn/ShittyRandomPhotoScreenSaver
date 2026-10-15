"""CPU and real-GL contracts for Neon Lake Basin's celestial helper."""
from __future__ import annotations

import math

import numpy as np
import pytest
from OpenGL import GL as gl

from rendering.gl_programs.neon_celestial import (
    NEON_CELESTIAL_GLSL,
    basin_body_position,
)
from tools.transition_contact_sheet import TransitionCapture


pytestmark = pytest.mark.qt

_VERTEX = """#version 460 core
void main() {
    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
"""


def _probe_fragment() -> str:
    return f"""#version 460 core
out vec4 FragColor;
uniform vec3 uEye;
uniform vec3 uWorldRay;
uniform int uProbeMode;
{NEON_CELESTIAL_GLSL}
void main() {{
    vec3 ray = uWorldRay;
    if (uProbeMode == 4) {{
        vec2 uv = gl_FragCoord.xy / vec2(64.0, 48.0) * 2.0 - 1.0;
        ray = normalize(vec3(uv.x * 0.75, uv.y * 0.60, -1.0));
    }} else if (uProbeMode == 5) {{
        vec2 uv = gl_FragCoord.xy / vec2(64.0, 64.0) * 2.0 - 1.0;
        ray = normalize(vec3(uv.x * 0.14, uv.y * 0.14, -1.0));
    }}
    vec3 hitPoint;
    vec4 body = basinCelestial(uEye, ray, hitPoint);
    float starVisibility=1.0-basinCelestialSkyMask(uEye,normalize(ray));
    vec4 sky = basinSkyBackground(ray,starVisibility);
    vec3 radiance = basinCompositeSkyBody(sky, body);
    if (uProbeMode == 0) FragColor = body;
    else if (uProbeMode == 1) FragColor = sky;
    else if (uProbeMode == 2) FragColor = vec4(radiance, 1.0);
    else if (uProbeMode == 4) FragColor = sky;
    else if (uProbeMode == 5) FragColor = body;
    else if (uProbeMode == 6) {{
        float rim=basinMoonRimIllumination(uEye,normalize(ray));
        FragColor=vec4(rim,rim,rim,1.0);
    }}
    else if (uProbeMode == 7) {{
        FragColor=vec4(vec3(basinMoonAlbedo(normalize(ray))),1.0);
    }}
    else if (uProbeMode == 8) {{
        // Exact production inner-rim component; whole-surface emission is
        // separately covered through the production host's MRT attachment.
        float inner=body.a>0.0001 ? basinMoonInnerRimEmission(uEye,hitPoint) : 0.0;
        FragColor=vec4(inner,inner,inner,1.0);
    }}
    else if (uProbeMode == 9) {{
        // Moon/Sun coverage is shared by ordinary and beat stars in sky.
        float masked=basinCelestialSkyMask(uEye,normalize(ray));
        FragColor=vec4(vec3(masked),1.0);
    }}
    else FragColor = vec4(hitPoint, body.a);
}}
"""


def test_body_position_uses_authored_point_or_one_logical_clock_orbit():
    authored = basin_body_position(1.05, 0.8, -3.2, 2.0, 0.0, False, 0.03)
    assert authored == (2.1, 0.8, -3.2)
    assert basin_body_position(1.05, 0.8, -3.2, 2.0, 50.0, False, 0.03) == authored
    # With orbit disabled, there is no hidden clock read or second motion policy.
    assert basin_body_position(1.05, 0.8, -3.2, 2.0, math.nan, False, math.inf) == authored

    quarter = basin_body_position(1.05, 0.8, -3.2, 2.0, 0.25, True, 1.0)
    assert quarter == pytest.approx((-2.0, 0.8, -3.3), abs=1e-12)
    initial_offset = (authored[0], authored[2] + 1.2)
    quarter_offset = (quarter[0], quarter[2] + 1.2)
    assert math.hypot(*quarter_offset) == pytest.approx(math.hypot(*initial_offset), abs=1e-12)

    full_turn = basin_body_position(1.05, 0.8, -3.2, 2.0, 1.0, True, 1.0)
    assert full_turn == pytest.approx(authored, abs=1e-12)
    default_speed_turn = basin_body_position(1.05, 0.8, -3.2, 2.0, 1.0 / 0.03, True, 0.03)
    assert default_speed_turn == pytest.approx(authored, abs=1e-12)
    default_speed_step = basin_body_position(1.05, 0.8, -3.2, 2.0, 1.0, True, 0.03)
    angle = 0.03 * math.tau
    assert default_speed_step == pytest.approx((
        authored[0] * math.cos(angle) + (authored[2] + 1.2) * math.sin(angle),
        authored[1],
        -1.2 - authored[0] * math.sin(angle) + (authored[2] + 1.2) * math.cos(angle),
    ), abs=1e-12)


def test_body_position_rejects_invalid_authored_or_active_orbit_values():
    with pytest.raises(ValueError, match="half-width"):
        basin_body_position(1.0, 0.0, -3.0, 0.0, 0.0, False, 0.0)
    with pytest.raises(ValueError, match="finite"):
        basin_body_position(math.inf, 0.0, -3.0, 1.0, 0.0, False, 0.0)
    with pytest.raises(ValueError, match="time and speed"):
        basin_body_position(1.0, 0.0, -3.0, 1.0, math.nan, True, 0.03)


def test_gl_body_sphere_alpha_sun_gate_moon_phase_and_independent_sky(qt_app):
    capture = TransitionCapture(16, 16)
    from rendering.quick.render.gl_resources import compile_program

    program = compile_program(_VERTEX, _probe_fragment(), label="Neon Lake celestial probe")
    vao = int(gl.glGenVertexArrays(1))
    colour = int(gl.glGenTextures(1))
    fbo = int(gl.glGenFramebuffers(1))

    eye = (0.0, 0.0, 0.0)
    body_position = (0.0, 0.0, -3.2)
    sun_colour = (1.0, 0.22, 0.06, 0.82)
    moon_colour = (0.72, 0.78, 0.90, 0.65)
    sky_colour = (0.018, 0.028, 0.16, 0.8)
    star_colour = (0.6, 0.78, 1.0, 0.85)
    cloud_colour = (0.25, 0.035, 0.34, 0.7)
    horizon_colour = (0.75, 0.11, 0.30, 0.75)

    def draw(*, mode, kind=0, sun_enabled=1, phase=0.5, sky_enabled=0,
             sky_strength=0.75, ray=(0.0, 0.0, -1.0), size=(1, 1),
             star_alpha=None, cloud_alpha=None, horizon_alpha=None, eye_override=None,
             star_count=0, body_alpha=None):
        gl.glUseProgram(program)
        gl.glUniform3f(gl.glGetUniformLocation(program, "uEye"), *(eye if eye_override is None else eye_override))
        gl.glUniform3f(gl.glGetUniformLocation(program, "uWorldRay"), *ray)
        gl.glUniform3f(gl.glGetUniformLocation(program, "uBodyPosition"), *body_position)
        gl.glUniform1f(gl.glGetUniformLocation(program, "uBodySize"), 0.45)
        gl.glUniform1i(gl.glGetUniformLocation(program, "uBodyKind"), kind)
        gl.glUniform1i(gl.glGetUniformLocation(program, "uSunEnabled"), sun_enabled)
        gl.glUniform4f(gl.glGetUniformLocation(program, "uSunColor"), *sun_colour)
        gl.glUniform4f(gl.glGetUniformLocation(program, "uMoonColor"),
                       *moon_colour[:3],moon_colour[3] if body_alpha is None else body_alpha)
        gl.glUniform1i(gl.glGetUniformLocation(program, "uBeatStarCount"), star_count)
        gl.glUniform2f(gl.glGetUniformLocation(program, "uStarGlow"), 2.0, 2.0)
        gl.glUniform4fv(gl.glGetUniformLocation(program, "uBeatStarCells[0]"), 1,
                        np.array([-0.5,-0.5,1.0,0.0], dtype=np.float32))
        gl.glUniform1f(gl.glGetUniformLocation(program, "uMoonPhase"), phase)
        gl.glUniform1i(gl.glGetUniformLocation(program, "uSkyEnabled"), sky_enabled)
        gl.glUniform4f(gl.glGetUniformLocation(program, "uSkyColor"), *sky_colour)
        gl.glUniform1f(gl.glGetUniformLocation(program, "uSkyStrength"), sky_strength)
        gl.glUniform4f(gl.glGetUniformLocation(program, "uStarColor"), *star_colour[:3],
                       star_colour[3] if star_alpha is None else star_alpha)
        gl.glUniform4f(gl.glGetUniformLocation(program, "uCloudColor"), *cloud_colour[:3],
                       cloud_colour[3] if cloud_alpha is None else cloud_alpha)
        gl.glUniform4f(gl.glGetUniformLocation(program, "uHorizonColor"), *horizon_colour[:3],
                       horizon_colour[3] if horizon_alpha is None else horizon_alpha)
        gl.glUniform1i(gl.glGetUniformLocation(program, "uProbeMode"), mode)
        gl.glBindVertexArray(vao)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, 3)
        raw = gl.glReadPixels(0, 0, *size, gl.GL_RGBA, gl.GL_FLOAT)
        return np.frombuffer(bytes(raw), dtype=np.float32).copy()

    try:
        gl.glBindTexture(gl.GL_TEXTURE_2D, colour)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, 1, 1, 0,
                        gl.GL_RGBA, gl.GL_FLOAT, None)
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, fbo)
        gl.glFramebufferTexture2D(gl.GL_FRAMEBUFFER, gl.GL_COLOR_ATTACHMENT0,
                                  gl.GL_TEXTURE_2D, colour, 0)
        assert gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER) == gl.GL_FRAMEBUFFER_COMPLETE
        gl.glViewport(0, 0, 1, 1)
        gl.glDisable(gl.GL_DEPTH_TEST)
        gl.glDisable(gl.GL_BLEND)

        sun = draw(mode=0)
        hit = draw(mode=3)
        assert np.isfinite(sun).all()
        assert sun[3] == pytest.approx(sun_colour[3], abs=2e-6)
        assert np.all(sun[:3] > 0.0)
        assert sun[1] / sun[0] == pytest.approx(sun_colour[1] / sun_colour[0], abs=2e-6)
        assert hit[:3] == pytest.approx((0.0, 0.0, -2.75), abs=2e-5)
        assert hit[3] == pytest.approx(sun_colour[3], abs=2e-6)
        assert np.allclose(draw(mode=0, ray=(1.0, 0.0, 0.0)), np.zeros(4), atol=0.0)
        upper_sun = [draw(mode=0, ray=(0.0, float(y), -1.0))
                     for y in np.linspace(0.005, 0.13, 17)]
        assert all(sample[3] == pytest.approx(sun_colour[3], abs=2e-6)
                   for sample in upper_sun)
        lower_rays = [(0.0, float(y), -1.0) for y in np.linspace(-0.13, -0.005, 61)]
        lower_sun = [draw(mode=0, ray=ray) for ray in lower_rays]
        assert max(sample[0] for sample in lower_sun) - min(
            sample[0] for sample in lower_sun
        ) > 0.05
        clear_gaps = [index for index, sample in enumerate(lower_sun) if sample[3] <= 1e-5]
        assert len(clear_gaps) >= 5
        gap_index = clear_gaps[len(clear_gaps) // 2]
        gap_ray = lower_rays[gap_index]
        gap_sky = draw(mode=1, sky_enabled=1, ray=gap_ray)
        gap_reflection = draw(mode=2, sky_enabled=1, ray=gap_ray)
        assert gap_reflection[:3] == pytest.approx(gap_sky[:3] * gap_sky[3], abs=3e-6)

        # The body gate does not alter sky, and a disabled sky does not hide the Sun.
        assert np.allclose(draw(mode=1), np.zeros(4), atol=0.0)
        assert np.allclose(draw(mode=0, sun_enabled=0), np.zeros(4), atol=0.0)
        disabled_sky = draw(mode=1, sun_enabled=0, sky_enabled=1)
        assert disabled_sky[3] == pytest.approx(sky_colour[3] * 0.75, abs=2e-6)
        assert np.isfinite(disabled_sky).all() and np.all(disabled_sky[:3] >= 0.0)
        assert np.allclose(draw(mode=1, sky_enabled=1, sky_strength=0.0), np.zeros(4), atol=0.0)

        # Moon illumination follows phase while its authored RGBA alpha remains independent.
        moon_hidden = draw(mode=0, kind=1, sun_enabled=0, phase=0.5)
        moon_hidden_reflection = draw(mode=2, kind=1, sun_enabled=0, phase=0.5)
        moon_hidden_sky = draw(mode=1, kind=1, sun_enabled=0, phase=0.5, sky_enabled=1)
        moon_hidden_sky_reflection = draw(
            mode=2, kind=1, sun_enabled=0, phase=0.5, sky_enabled=1)
        assert np.allclose(moon_hidden, np.zeros(4), atol=0.0)
        assert np.allclose(moon_hidden_reflection[:3], np.zeros(3), atol=0.0)
        assert moon_hidden_sky_reflection[:3] == pytest.approx(
            moon_hidden_sky[:3] * moon_hidden_sky[3], abs=3e-6)
        # The solid Moon, including its dim shaded hemisphere, blocks stars.
        moon_mask=draw(mode=9,kind=1,phase=0.5)
        moon_mask_transparent=draw(mode=9,kind=1,phase=0.25,body_alpha=0.0)
        moon_mask_disabled=draw(mode=9,kind=1,phase=0.25,sun_enabled=0)
        moon_mask_miss=draw(mode=9,kind=1,phase=0.25,ray=(1.0,0.0,-1.0))
        assert moon_mask[0] == pytest.approx(moon_colour[3],abs=2e-6)
        assert moon_mask_transparent[0] == 0.0
        assert moon_mask_disabled[0] == 0.0
        assert moon_mask_miss[0] == 0.0
        assert draw(mode=9,kind=1,phase=0.0)[0] == pytest.approx(moon_colour[3],abs=2e-6)
        assert draw(mode=9,kind=1,phase=0.25,ray=(.10,0.,-1.))[0] == pytest.approx(moon_colour[3],abs=2e-6)
        assert draw(mode=9,kind=1,phase=0.25,ray=(-.10,0.,-1.))[0] == pytest.approx(moon_colour[3],abs=2e-6)
        moon_sky_baseline=draw(mode=1,kind=1,phase=0.5,sky_enabled=1,star_count=0)
        moon_sky_beat=draw(mode=1,kind=1,phase=0.5,sky_enabled=1,star_count=1)
        clear_sky_beat=draw(mode=1,kind=1,phase=0.25,sky_enabled=1,
                            star_count=1,sun_enabled=0)
        clear_sky_baseline=draw(mode=1,kind=1,phase=0.25,sky_enabled=1,
                                star_count=0,sun_enabled=0)
        assert clear_sky_beat[:3].mean()>clear_sky_baseline[:3].mean()+0.1
        assert moon_sky_beat[:3]-moon_sky_baseline[:3] == pytest.approx(
            (clear_sky_beat[:3]-clear_sky_baseline[:3])*(1.-moon_colour[3]),abs=2e-5)
        moon_new = draw(mode=0, kind=1, sun_enabled=1, phase=0.0)
        moon_full = draw(mode=0, kind=1, sun_enabled=1, phase=0.5)
        assert moon_new[3] == pytest.approx(moon_colour[3],abs=2e-6)
        assert moon_full[3] == pytest.approx(moon_colour[3], abs=2e-6)
        assert moon_full[:3].mean() > moon_new[:3].mean()*4.
        assert moon_full[1] / moon_full[0] == pytest.approx(
            moon_colour[1] / moon_colour[0], abs=2e-6)
        assert np.isfinite(moon_new).all() and np.isfinite(moon_full).all()
        # Manual phase remains the selected appearance when the Moon passes
        # round the basin and the observer moves relative to it. Orbit speed
        # and calendar time have no authority over this slider.
        side_eye=(2.0,0.0,0.0)
        side_ray=(-2.0,0.0,-3.2)
        moon_new_side=draw(mode=0,kind=1,phase=0.0,ray=side_ray,eye_override=side_eye)
        moon_full_side=draw(mode=0,kind=1,phase=0.5,ray=side_ray,eye_override=side_eye)
        assert moon_full_side[:3].mean()*moon_full_side[3]>moon_new_side[:3].mean()*moon_new_side[3]

        moon_size = (64, 64)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, *moon_size, 0,
                        gl.GL_RGBA, gl.GL_FLOAT, None)
        gl.glViewport(0, 0, *moon_size)
        moon_surface = draw(mode=5, kind=1, phase=0.5, size=moon_size)
        moon_surface = moon_surface.reshape(moon_size[1], moon_size[0], 4)
        axis = (np.arange(64, dtype=np.float32) + 0.5) * (2.0 / 64.0) - 1.0
        nx, ny = np.meshgrid(axis, axis)
        moon_core = nx * nx + ny * ny < 0.62 * 0.62
        crater_values = moon_surface[..., 0][moon_core] / moon_colour[0]
        assert np.isfinite(crater_values).all()
        # The accepted clean bright Moon has only restrained relief. Do not
        # demand the rejected contour map or pin an artistic contrast level.
        assert np.all((crater_values>=0.) & (crater_values<=1.))
        relief = [draw(mode=7,kind=1,ray=(u,v,-1.))[0]
                  for u in (-.8,-.4,0.,.4,.8) for v in (-.5,0.,.5)]
        assert 1e-4 < float(np.ptp(relief)) < .25

        # Rim lighting shares the surface phase direction, so a waxing Moon
        # lights the lit limb only; new Moon has no rim glow and full Moon has
        # illuminated rim in both directions. Test the GPU function directly.
        right = (0.18, 0.0, -1.0)
        left = (-0.18, 0.0, -1.0)
        new_right = draw(mode=6, kind=1, phase=0.0, ray=right)
        new_left = draw(mode=6, kind=1, phase=0.0, ray=left)
        waxing_right = draw(mode=6, kind=1, phase=0.25, ray=right)
        waxing_left = draw(mode=6, kind=1, phase=0.25, ray=left)
        full_right = draw(mode=6, kind=1, phase=0.5, ray=right)
        full_left = draw(mode=6, kind=1, phase=0.5, ray=left)
        assert new_right[0] < 0.01 and new_left[0] < 0.01
        assert waxing_right[0] > 0.85 and waxing_left[0] < 0.15
        assert full_right[0] > 0.5 and full_left[0] == pytest.approx(full_right[0],abs=2e-6)

        # Actual crescents (not just quarters) and opposite phase orientation.
        # The brightness/halo may change artistically, but the direction of
        # illumination must not become ambiguous or dependent on raster size.
        thin_waxing_right = draw(mode=0, kind=1, phase=0.075, ray=(0.139,0.0,-1.0))
        thin_waxing_left = draw(mode=0, kind=1, phase=0.075, ray=(-0.139,0.0,-1.0))
        thin_waning_left = draw(mode=0, kind=1, phase=0.925, ray=(-0.139,0.0,-1.0))
        thin_waning_right = draw(mode=0, kind=1, phase=0.925, ray=(0.139,0.0,-1.0))
        assert thin_waxing_right[:3].mean() > thin_waxing_left[:3].mean()*2.
        assert thin_waning_left[:3].mean() > thin_waning_right[:3].mean()*2.

        # The inner-rim component stays at the illuminated edge. The total
        # production Moon also emits across its surface; this helper isolates
        # the subordinate rim so it cannot spread into a second face layer.
        core = draw(mode=8, kind=1, phase=0.5, ray=(0.0,0.0,-1.0))
        full_inner_edge = draw(mode=8, kind=1, phase=0.5, ray=(0.141,0.0,-1.0))
        dark_inner_edge = draw(mode=8, kind=1, phase=0.0, ray=(0.141,0.0,-1.0))
        assert core[0] < 1e-5
        assert 0.1 < full_inner_edge[0] <= 1.0
        assert dark_inner_edge[0] < 0.01

        # Spherical 3-D material sampling is seamless across the old longitude
        # wrap and is stable at high latitudes. Avoid a 2-D crater UV authority.
        seam_a = draw(mode=7, kind=1, ray=(0.00001, 0.3, -1.0))
        seam_b = draw(mode=7, kind=1, ray=(-0.00001, 0.3, -1.0))
        assert seam_a[:3] == pytest.approx(seam_b[:3], abs=0.01)

        sky = draw(mode=1, sky_enabled=1)
        body = draw(mode=0, sky_enabled=1)
        reflected = draw(mode=2, sky_enabled=1)
        expected = body[:3] * body[3] + sky[:3] * sky[3] * (1.0 - body[3])
        assert reflected[:3] == pytest.approx(expected, abs=3e-6)
        assert reflected[0] > sky[0] * sky[3]
        body_only_reflection = draw(mode=2, sky_enabled=0)
        assert body_only_reflection[:3] == pytest.approx(body[:3] * body[3], abs=3e-6)

        # Sweep real directional rays so the sparse, antialiased stars and broken
        # cloud bands cannot regress into a flat horizon-coloured block.
        sweep_size = (64, 48)
        gl.glTexImage2D(gl.GL_TEXTURE_2D, 0, gl.GL_RGBA32F, *sweep_size, 0,
                        gl.GL_RGBA, gl.GL_FLOAT, None)
        gl.glViewport(0, 0, *sweep_size)
        star_sweep = draw(mode=4, sky_enabled=1, size=sweep_size,
                          cloud_alpha=0.0, horizon_alpha=0.0, star_alpha=star_colour[3])
        no_star_sweep = draw(mode=4, sky_enabled=1, size=sweep_size,
                             cloud_alpha=0.0, horizon_alpha=0.0, star_alpha=0.0)
        star_pixels = np.linalg.norm(
            (star_sweep - no_star_sweep).reshape(sweep_size[1], sweep_size[0], 4)[..., :3],
            axis=2,
        )
        assert np.count_nonzero(star_pixels > 0.15) >= 5

        cloud_sweep = draw(mode=4, sky_enabled=1, size=sweep_size,
                           cloud_alpha=cloud_colour[3], horizon_alpha=0.0, star_alpha=0.0)
        assert np.abs(cloud_sweep - no_star_sweep).sum() > 0.5
    finally:
        gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
        gl.glDeleteFramebuffers(1, [fbo])
        gl.glDeleteTextures([colour])
        gl.glDeleteVertexArrays(1, [vao])
        gl.glDeleteProgram(program)
        capture.close()
