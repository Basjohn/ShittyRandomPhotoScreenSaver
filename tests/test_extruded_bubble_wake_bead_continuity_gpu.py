"""Wake beads stay where their water is from frame to frame (the idle wake teleport, N5.6), on native GL.

The production fizz stage (``beadInstance``) places each trailed bead from the logical wake records the simulation's
``WakeField`` builds. A bubble whose course turns slowly through every direction, as idle drift does, lays new
points and sweeps its trail through every orientation: every visible bead must move by no more than its water and
its bubble do in one tick. Two placements broke that: the spline neighbour before the bubble's own segment (a mirrored
phantom, so the curve through the same water changed whenever a point was laid) and a side axis crossed with a fixed
reference that ran parallel to the trail on a cone of directions (every bead flipped across the trail at once).
Test-owned motion and sizes; no preset values.
"""
from __future__ import annotations

import math

import numpy as np

_TICK = 1 / 30
_SECONDS = 70.0
_PER = 24


def _records():
    """Per tick: one live trailed emitter's wake record, as the simulation packs it, from a test-owned course."""
    from widgets.spotify_visualizer.extruded_bubble_wake import WakeField
    radius, ident = 1.0, 41
    field = WakeField(2)
    head = np.zeros(3)
    field.add(ident, radius, tuple(head))
    out = []
    for k in range(int(_SECONDS / _TICK)):
        t = k * _TICK
        a, b = 0.23 * t, 0.37 * math.sin(0.05 * t) * math.pi
        head = head + 0.25 * _TICK * np.array((math.sin(a) * math.cos(b), math.sin(b), math.cos(a) * math.cos(b)))
        field.flow(_TICK, 0.3 * t)
        field.follow(ident, tuple(head), radius, _TICK, max(4.0 * radius, 0.9))
        out.append(np.array((*head, radius, ident, -1.0, 1.0, radius, 1.0, *field.record(ident, tuple(head))),
                            dtype=np.float32))
    return out


def test_trailed_beads_never_jump_as_points_are_laid_and_the_trail_turns(qt_app):
    from OpenGL import GL as gl
    from rendering.gl_programs.extruded_bubble_program import BEAD_VERTEX
    from rendering.quick.render.gl_resources import compile_program, delete_program
    from tools.labs.render_target import OffscreenRenderTarget
    prefix = BEAD_VERTEX.split('void main() {\n    vOpacity = 1.0;\n')[0]
    vertex = prefix + '''
layout(std430, binding = 5) buffer FizzResults { vec4 fizzResults[]; };
void main() {
    vOpacity = 1.0; beadInstance();
    fizzResults[2 * gl_InstanceID] = aSphere;
    fizzResults[2 * gl_InstanceID + 1] = vec4(vOpacity, 0.0, 0.0, 0.0);
    gl_Position = vec4(0.0, 0.0, 0.0, 1.0);
}
'''
    records = _records()
    target = OffscreenRenderTarget(64, 64)
    program, buffers = 0, []
    try:
        program = compile_program(vertex, '#version 460 core\nout vec4 colour;\nvoid main(){colour=vec4(0);}',
                                  label='wake bead continuity')
        gl.glUseProgram(program)
        names = np.empty(2, dtype='u4'); gl.glCreateBuffers(2, names); buffers = list(map(int, names))
        result, wakes = buffers
        gl.glNamedBufferData(result, _PER * 32, None, gl.GL_DYNAMIC_READ)
        gl.glNamedBufferData(wakes, records[0].nbytes, None, gl.GL_DYNAMIC_DRAW)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 5, result)
        gl.glBindBufferBase(gl.GL_SHADER_STORAGE_BUFFER, 7, wakes)
        ints = {'uBeadCount': 0, 'uSnowCount': 0, 'uFizzPer': _PER, 'uWakeCount': 1, 'uBeadsPerChain': 160,
                'uSceneEmission': 0}
        floats = {'uFizzFill': float(_PER), 'uTrailFizz': float(_PER), 'uBeadSize': 1.0, 'uBeadTravel': 0.0,
                  'uPixel': 1e-4, 'uTrails': 1.0, 'uParticleSpread': 1.0}
        for key, value in ints.items():
            gl.glUniform1i(gl.glGetUniformLocation(program, key), value)
        for key, value in floats.items():
            gl.glUniform1f(gl.glGetUniformLocation(program, key), value)
        for key, value in (('uStreamSource', (0, -8, 0)), ('uStreamEnd', (0, 8, 0)), ('uStreamWorld', (0, 1, 0)),
                           ('uStreamAcross', (1, 0, 0)), ('uStreamDepth', (0, 0, -1)), ('uWorldHalf', (18, 8, 18)),
                           ('uEye', (0, 0, 400))):
            gl.glUniform3f(gl.glGetUniformLocation(program, key), *value)
        gl.glUniformMatrix3fv(gl.glGetUniformLocation(program, 'uWorldToView'), 1, gl.GL_FALSE,
                              np.eye(3, dtype='f4'))
        gl.glBindVertexArray(target.vao); gl.glEnable(gl.GL_RASTERIZER_DISCARD)
        previous, steps = None, []
        for record in records:
            gl.glNamedBufferSubData(wakes, 0, record.nbytes, record)
            gl.glDrawArraysInstanced(gl.GL_POINTS, 0, 1, _PER)
            gl.glMemoryBarrier(gl.GL_BUFFER_UPDATE_BARRIER_BIT | gl.GL_SHADER_STORAGE_BARRIER_BIT)
            rows = np.empty((_PER, 2, 4), dtype='f4'); gl.glGetNamedBufferSubData(result, 0, rows.nbytes, rows)
            if previous is not None:
                shown = (rows[:, 1, 0] > 0.05) & (previous[:, 1, 0] > 0.05)
                steps.extend(np.linalg.norm(rows[shown, 0, :3] - previous[shown, 0, :3], axis=1).tolist())
            previous = rows
        assert gl.glGetError() == gl.GL_NO_ERROR
    finally:
        gl.glDisable(gl.GL_RASTERIZER_DISCARD)
        if buffers:
            gl.glDeleteBuffers(len(buffers), buffers)
        if program:
            delete_program(program)
        target.close()
    steps = np.asarray(steps)
    laid = sum(1 for a, b in zip(records, records[1:]) if b[11] > a[11] and b[12] < a[12])
    assert laid >= 8 and len(steps) > 5000
    # The bubble moves 0.25 world units a second (0.008 of its radius a tick); its water drags and swirls slower.
    # Allow ten times that, far below the 0.2-0.8 radius jumps either placement fault made.
    assert steps.max() < 0.08, (steps.max(), np.percentile(steps, 99))
