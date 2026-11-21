"""The Pulse Rim field: the logical owner's published pulse appearance, uploaded once per frame for the light pass.

The field is ``WaveformDynamics.pulse_at`` on ``PULSE_GRID`` (history-axis x), published in the snapshot as float32
bytes. It is uploaded only when its bytes object changes (one small ``glNamedBufferSubData``); nothing is evaluated
here, so the brightening lies exactly where the published pulse is, in every Reaction Mode. It is a storage buffer
the light pass reads linearly (``PULSE_RIM_GLSL``, N5.4: the native core's form, a storage stream, not a float texture).
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
    (buffer, uPulseRim, uPulseRimShape)."""
    def __init__(self):
        self.buffer = 0
        self._payload = None
        self._context = None

    @property
    def has_resources(self):
        return bool(self.buffer)

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
        if not self.buffer:
            name = (gl.GLuint*1)()
            gl.glCreateBuffers(1, name)
            self.buffer = int(name[0])
            gl.glNamedBufferStorage(self.buffer, SAMPLES*4, None, gl.GL_DYNAMIC_STORAGE_BIT)
            self._payload = None
        if payload is not self._payload:
            gl.glNamedBufferSubData(self.buffer, 0, SAMPLES*4, np.frombuffer(payload, np.float32))
            self._payload = payload
        length = LAST-FIRST+STEP
        # Sample i's centre is PULSE_GRID[i]; beyond the grid the edge value continues (as ``pulse_at`` does).
        return self.buffer, (FIRST-.5*STEP, 1./length, float(strength), SPREAD/length), (1./REFERENCE, CEILING)

    def release(self):
        if self.buffer:
            self._check()
            gl.glDeleteBuffers(1, [self.buffer])
        self.buffer = 0
        self._payload = None
        self._context = None
