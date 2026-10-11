"""Oscilloscope's Settings choices.

Import-safe for the Settings spec, the model and the frame runtime: the shader module
(``oscilloscope_program``) loads only when Oscilloscope runs.
"""

from __future__ import annotations

# How the audio is drawn. Trace: the triggered waveform across the screen, as a scope shows it.
# Ring: the same trace wrapped around a circle. Phase: the signal against itself a moment later,
# the swirling figures of an X/Y scope.
OSC_DISPLAYS = ("Trace", "Ring", "Phase")
# The screen's faint scale: off, the classic 10 x 8 grid, or only the centre axes.
OSC_GRATICULES = ("Off", "Grid", "Crosshair")
