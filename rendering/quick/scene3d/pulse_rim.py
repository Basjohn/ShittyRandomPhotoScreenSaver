"""The Pulse Rim field: the logical owner's published pulse appearance, uploaded once per frame for the light pass.

The field is ``WaveformDynamics.pulse_at`` on ``PULSE_GRID`` (history-axis x), published in the snapshot as float32
bytes. It is uploaded only when its bytes object changes (one small ``glTextureSubImage2D``); nothing is evaluated
here, so the brightening lies exactly where the published pulse is, in every Reaction Mode.
"""
from OpenGL import GL as gl
from PySide6.QtGui import QOpenGLContext
import numpy as np
from core.waveform_ribbon_dynamics import PULSE_GRID

FIRST, LAST, SAMPLES = float(PULSE_GRID[0]), float(PULSE_GRID[-1]), int(PULSE_GRID.size)
STEP = (LAST-FIRST)/(SAMPLES-1)
# Spread of the shader's three binomial taps (world units along the history axis): the brightening fades softly
# along the rim, a little wider than the authored band, never ending in a hard edge.
SPREAD = .75
# Response = CEILING*tanh((field/REFERENCE)^2/CEILING). REFERENCE is a passing swell's level in the visible span on
# recorded music for a swell carrying half the injection, as each Centre Out swell does (an edge swell seen at full
# strength publishes core.waveform_ribbon_dynamics.RIM_EDGE_SHARE of its level; 5 Nov: in-view peak p90 .12), so Pulse Rim k
# lights a passing swell's rims to about 1+k times and leaves the plateau near 1+k/4; CEILING bounds a strong or
# Whole Swell (1+2k at most).
REFERENCE, CEILING = .12, 2.


class PulseRimField:
    """Caller owns the current GL context; ``update`` once per frame returns the light pass's
    (texture, uPulseRim, uPulseRimShape)."""
    def __init__(self):
        self.texture = 0
        self._payload = None
        self._context = None

    @property
    def has_resources(self):
        return bool(self.texture)

    def _check(self):
        current = QOpenGLContext.currentContext()
        if current is None:
            raise RuntimeError('Pulse rim field requires its current GL context')
        if self._context is None:
            self._context = current
        if current != self._context:
            raise RuntimeError('Pulse rim field used in a foreign GL context')

    def update(self, payload, strength):
        self._check()
        if not isinstance(payload, bytes) or len(payload) != SAMPLES*4 or not strength > 0.:
            raise ValueError('Pulse rim field needs the published pulse grid and a positive strength')
        if not self.texture:
            name = (gl.GLuint*1)()
            gl.glCreateTextures(gl.GL_TEXTURE_2D, 1, name)
            self.texture = int(name[0])
            gl.glTextureStorage2D(self.texture, 1, gl.GL_R32F, SAMPLES, 1)
            for key, value in ((gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR), (gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR),
                               (gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE), (gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)):
                gl.glTextureParameteri(self.texture, key, value)
            self._payload = None
        if payload is not self._payload:
            gl.glTextureSubImage2D(self.texture, 0, 0, 0, SAMPLES, 1, gl.GL_RED, gl.GL_FLOAT,
                                   np.frombuffer(payload, np.float32))
            self._payload = payload
        length = LAST-FIRST+STEP
        # Texel i's centre is PULSE_GRID[i]; beyond the grid the edge value continues (as ``pulse_at`` does).
        return self.texture, (FIRST-.5*STEP, 1./length, float(strength), SPREAD/length), (1./REFERENCE, CEILING)

    def release(self):
        if self.texture:
            self._check()
            gl.glDeleteTextures(1, [self.texture])
        self.texture = 0
        self._payload = None
        self._context = None
