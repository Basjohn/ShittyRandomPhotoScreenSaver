"""Lazy WR-02 strip primitive; caller owns target/depth/blend and context scope.

``shading='diagnostic'`` draws the WR-02a diagnostics. ``'body'`` and ``'light'`` are the filament material's two
passes (``rendering/gl_programs/ribbon.py``): the caller draws ``body`` inside ``SceneTarget.transparent_writes`` and
``light`` afterwards inside ``emission_writes`` with additive blending on colour. Both need the world view matrix,
which is rebased with the packet origin exactly as the MVP is, so no shader mixes local and absolute space.
"""
from dataclasses import astuple, dataclass
import math
import weakref

import numpy as np
from OpenGL import GL as gl

from core.ribbon_packet import MAX_PACKET_BYTES, MAX_RIBBONS, RIBBON_BYTES, RibbonPacket
from core.ribbon_frames import MAX_STRIP_STATIONS
from rendering.gl_programs.ribbon import (RIBBON_BODY_FRAGMENT, RIBBON_FRAGMENT, RIBBON_LIGHT_FRAGMENT,
                                          RIBBON_SPARK_FRAGMENT, RIBBON_SPARK_VERTEX, RIBBON_STRAY_FRAGMENT,
                                          RIBBON_STRAY_VERTEX, RIBBON_VERTEX)
from core.ribbon_geometry import MAX_PATH_SAMPLES
from rendering.gl_programs.mist import FOG_OFF
from rendering.quick import gl_query
from rendering.quick.scene3d.resources import MeshResources
from rendering.quick.scene3d.stream import StreamRing

_FRAGMENTS = {'diagnostic': RIBBON_FRAGMENT, 'body': RIBBON_BODY_FRAGMENT, 'light': RIBBON_LIGHT_FRAGMENT}
_MATERIAL_UNIFORMS = ('uViewZ', 'uEye', 'uForward', 'uOrthographic', 'uStrands', 'uRim', 'uBody', 'uFill', 'uGlint', 'uAge',
                      'uMist', 'uMistShape', 'uMistOrigin', 'uTone',
                      'uViewport', 'uFogVolume', 'uFogView', 'uFogLens', 'uFogRange', 'uGradeStops', 'uGrade', 'uFloorContact', 'uGlow')
GRADE_STOPS = 6
STRAY_SEGMENTS = 24  # matches RIBBON_STRAY_VERTEX
GRADE_OFF = dict(uGradeStops=(0.,)*(4*GRADE_STOPS), uGrade=(0., 1., 0., 1.))


def ribbon_grade(stops, x_range, share):
    """World colour grade uniforms: 1..GRADE_STOPS ``(position, (r, g, b))`` nodes at strictly ascending positions
    in 0..1 across a world-x range, taking ``share`` of each ribbon's own colour."""
    nodes = [(float(position), tuple(float(v) for v in colour)) for position, colour in stops]
    x0, x1 = (float(v) for v in x_range)
    positions = [position for position, _ in nodes]
    if (not 1 <= len(nodes) <= GRADE_STOPS
            or any(len(c) != 3 or not all(math.isfinite(v) and 0 <= v <= 1 for v in c) for _, c in nodes)
            or not all(math.isfinite(p) and 0 <= p <= 1 for p in positions)
            or any(b <= a for a, b in zip(positions, positions[1:]))
            or not (math.isfinite(x0) and math.isfinite(x1) and x0 < x1) or not 0 <= float(share) <= 1):
        raise ValueError('A ribbon grade needs 1-6 normalized colour nodes at ascending 0..1 positions, '
                         'an ordered finite range and a 0..1 share')
    flat = [v for position, colour in nodes for v in (*colour, position)]
    flat += flat[-4:]*(GRADE_STOPS - len(nodes))
    return dict(uGradeStops=tuple(flat), uGrade=(x0, x1, float(share), float(len(nodes))))


def _floor_contact(floor, frame):
    """``floor`` = (world floor height, gap, softness) as packet-local uniform values; None is off."""
    if floor is None:
        return (0., 0., 0.)
    height, gap, softness = (float(v) for v in floor)
    if not all(math.isfinite(v) for v in (height, gap, softness)) or gap < 0 or softness <= 0:
        raise ValueError('Floor contact needs a finite floor height, a non-negative gap and a positive softness')
    return (height - float(frame[1]), gap, softness)


def _upload(location, value):
    """A vec4 uniform, or the grade's vec4 array."""
    if len(value) == 4*GRADE_STOPS:
        gl.glUniform4fv(location, GRADE_STOPS, np.asarray(value, np.float32))
    else:
        gl.glUniform4f(location, *value)


def _sweep_axis(value):
    if value is None:
        return (0.,0.,0.)
    if len(value) != 3 or not all(math.isfinite(v) for v in value):
        raise ValueError('A supplied sweep axis must be a finite non-zero world vector')
    scale = max(abs(v) for v in value)
    if scale < 1e-8:
        raise ValueError('A supplied sweep axis must be a finite non-zero world vector')
    scaled = tuple(v/scale for v in value)
    length = math.hypot(*scaled)
    return tuple(v/length for v in scaled)


@dataclass(frozen=True)
class RibbonSparks:
    """Sparks attached to the ribbon's history; per-knot sparkle (0..1, ``RibbonRing.append(sparkle=)``) gates them."""
    per_knot: int = 6
    lifetime: float = 4.            # seconds
    drift: float = .9               # world units per second at birth, slowing with age
    rise: float = .35               # upward bias of the drift direction
    smallest: float = 1.5           # point size, pixels
    largest: float = 4.5
    light: float = 6.
    twinkle: float = 1.7            # Hz
    white: float = .6

    def __post_init__(self):
        if isinstance(self.per_knot, bool) or not isinstance(self.per_knot, int) or not 1 <= self.per_knot <= 16:
            raise ValueError('Sparks per knot must be an integer in 1..16')
        values = (self.lifetime, self.drift, self.smallest, self.largest, self.light, self.twinkle, self.white)
        if (not all(math.isfinite(v) and v >= 0 for v in (*values, abs(self.rise))) or self.lifetime <= 0
                or not 0 < self.smallest <= self.largest <= 32 or self.white > 1):
            raise ValueError('Ribbon sparks need finite non-negative values, a positive lifetime and sizes in (0, 32]')


@dataclass(frozen=True)
class RibbonStrays:
    """Free strands: liquid filaments that peel off the sheets and flow with the history (``shading='strays'``);
    per-knot sparkle gates them, like sparks."""
    per_knot: int = 2
    length: float = 10.             # knots a stray spans along its sheet
    reach: float = .6               # world units it leaves the sheet by at its free tip (fully peeled)
    chance: float = .5              # share of the sparkle-gated slots alive
    width: float = 1.2              # half-width of its quad, pixels (the line's core is about a third)
    light: float = 2.
    beads: float = 5.               # droplets per stray
    peel_time: float = 2.           # seconds of knot age to peel most of the way
    halo: float = 0.                # soft glow around each filament (a fuzzy splash), relative to its core
    glow: float = 1.                # share of its light sent to the bloom

    def __post_init__(self):
        if isinstance(self.per_knot, bool) or not isinstance(self.per_knot, int) or not 1 <= self.per_knot <= 8:
            raise ValueError('Strays per knot must be an integer in 1..8')
        values = (self.length, self.reach, self.chance, self.width, self.light, self.beads, self.peel_time, self.halo,
                  self.glow)
        if (not all(math.isfinite(v) and v >= 0 for v in values) or not 1 <= self.length <= 32
                or self.chance > 1 or not 0 < self.width <= 16 or self.peel_time <= 0):
            raise ValueError('Ribbon strays need finite non-negative values, a length in 1..32 knots, a 0..1 chance, '
                             'a width in (0, 16] pixels and a positive peel time')


@dataclass(frozen=True)
class RibbonMaterial:
    """Filament look, in units of the ribbon itself; no music, palette or scene authority."""
    strands: float = 16.            # filament lines across the width
    strand_half_width: float = .11  # of one strand spacing
    strand_light: float = 1.7
    strand_warp: float = .06        # across-width spread/gather amplitude
    warp_frequency: float = .25     # warp cycles per strand-phase unit along the path
    rim_half_width: float = .02     # of the width
    rim_light: float = 1.4
    path_cap: float = 64.           # max path-length gain 1/|N.V| where the sheet is not widened
    min_pixels: float = 2.          # edge-on flat sheets stay this wide; interior light compensates true width
    body_alpha: float = .035
    body_tint: float = .35
    fill_light: float = .12         # the sheet's own glow
    fill_centre: float = .3         # fill level at the centre line (edges are 1)
    rim_glow_width: float = .05     # of the width, exponential falloff from each edge
    rim_glow_light: float = .25
    glint_density: float = .5       # glint cells per strand per strand-phase unit
    glint_chance: float = .2
    glint_light: float = 5.
    glint_radius: float = .3        # strand spacings (at least glint_min_pixels)
    glint_min_pixels: float = .75
    strand_white: float = 0.        # strands' mix toward white (0 = the ribbon colour)
    rim_white: float = 0.
    strand_jitter: float = 0.       # irregular strand spacing, 0..0.9 (monotone)
    strand_variation: float = 0.    # energy-neutral contrast between fine and dominant filaments
    cross_curve: float = 0.         # smooth transverse bow in half-widths; 0 retains the flat strip
    glow: float = 1.                # share of the sheet's light sent to the bloom (local glow, not the mist's)
    hot: float = 0.                 # white-hot cores on the brightest strands (0..1), the rest keep their colour

    def __post_init__(self):
        values = astuple(self)
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0 for v in values):
            raise ValueError('Ribbon material values must be finite and non-negative')
        if (not 1 <= self.strands <= 256 or not 0 < self.strand_half_width <= .5 or not 0 < self.rim_half_width <= .5
                or not 0 < self.rim_glow_width <= .5 or self.fill_centre > 1 or self.glint_chance > 1
                or self.strand_white > 1 or self.rim_white > 1 or self.strand_jitter > .9 or self.strand_variation > 1
                or self.hot > 1):
            raise ValueError('Ribbon strands need 1..256 lines and positive half-widths up to half a spacing')
        if self.body_alpha > .95 or self.path_cap < 1 or self.min_pixels > 8 or self.cross_curve > 1:
            raise ValueError('Ribbon body alpha must stay below 0.95, path cap at least 1, minimum width at most 8 px')

    def uniforms(self):
        return dict(uStrands=(self.strands, self.strand_half_width, self.strand_light, self.strand_warp),
                    uRim=(self.rim_half_width, self.rim_light, self.path_cap, self.min_pixels),
                    uBody=(self.body_alpha, self.body_tint, self.strand_variation, self.warp_frequency),
                    uFill=(self.fill_light, self.fill_centre, self.rim_glow_width, self.rim_glow_light),
                    uGlint=(self.glint_density, self.glint_chance, self.glint_light, self.glint_radius),
                    uTone=(self.strand_white, self.rim_white, self.strand_jitter, self.glint_min_pixels),
                    uGlow=(self.glow, self.hot))


class RibbonPrimitive:
    def __init__(self):
        self.resources = MeshResources('ribbon primitive')
        self.stream = None
        self._context_ref = None

    @property
    def has_resources(self):
        return self.resources.has_resources or (self.stream is not None and self.stream.has_resources)

    @property
    def stream_bytes(self):
        return self.stream.capacity if self.stream is not None and self.stream.has_resources else 0

    def draw(self, packet: RibbonPacket, mvp, *, diagnostic=0, timing_query=None, shading='diagnostic',
             view=None, orthographic=True, material: RibbonMaterial | None = None, age_fade=None,
             mist=None, mist_frame=(0., 0., 0.), sparks: RibbonSparks | None = None, now=None, sweep_axis=None,
             grade=None, floor=None, strays: RibbonStrays | None = None):
        """``age_fade`` = (absolute now, fade-in s, maximum age s, fade-out s) fades the head and tail by age.

        ``mist`` (``rendering.gl_programs.mist.mist_uniforms``) dims light and coverage by the scene's world mist;
        ``mist_frame`` translates the packet's frame into the mist's world (a flowing consumer's scroll).
        ``sweep_axis`` admits a monotonic world axis: cross sections remain perpendicular to it, and history knots
        become cubic B-spline controls for position/side/width/twist, with continuous slope and curvature. General
        paths without a monotonic axis retain transported strips. ``cross_curve`` adds transverse camber.
        """
        if not 0 <= packet.instances <= MAX_RIBBONS or len(packet.payload) != packet.instances*RIBBON_BYTES:
            raise ValueError('Invalid ribbon packet shape')
        if shading in ('sparks', 'strays'):
            return self._draw_sparks(packet, mvp, sparks or RibbonSparks(), now, mist, mist_frame, grade,
                                     material or RibbonMaterial(), _sweep_axis(sweep_axis), floor,
                                     (strays or RibbonStrays()) if shading == 'strays' else None)
        if shading not in _FRAGMENTS:
            raise ValueError(f'Unknown ribbon shading: {shading}')
        if packet.instances == 0:
            if packet.vertices != 0:
                raise ValueError('Empty packet cannot draw vertices')
            return
        if packet.vertices % 6 or not 0 < packet.vertices <= (MAX_STRIP_STATIONS-1)*6:
            raise ValueError('Ribbon draw exceeds vertex capacity')
        if len(mvp) != 16 or not all(math.isfinite(v) for v in mvp) or diagnostic not in (0, 1, 2):
            raise ValueError('Finite MVP and admitted diagnostic required')
        origin = np.asarray(packet.world_origin, dtype=float)
        if origin.shape != (3,) or not np.isfinite(origin).all():
            raise ValueError('Finite packet world origin required')
        translate = np.array((*origin, 1.))
        matrix = np.asarray(mvp, dtype=float).reshape(4, 4, order='F').copy()
        matrix[:, 3] = matrix @ translate
        matrix = matrix.astype(np.float32)
        if not np.isfinite(matrix).all():
            raise ValueError('Rebased MVP exceeds float32 range')
        shaded = None
        material = material or RibbonMaterial()
        cross_divisions = 8 if material.cross_curve > 0 else 1
        axis = _sweep_axis(sweep_axis)
        if shading != 'diagnostic':
            shaded = self._material_uniforms(view, translate, bool(orthographic), material)
            shaded['uAge'] = (0., 0., 0., 0.)
            shaded.update({'uMist': (0., 0., 1., 1.), 'uMistShape': (0., 0., 0., 0.), **FOG_OFF, **GRADE_OFF, **(grade or {})})
            if mist is not None:
                shaded.update(mist)
            frame = np.asarray(packet.world_origin, float) + np.asarray(mist_frame, float)
            if frame.shape != (3,) or not np.isfinite(frame).all():
                raise ValueError('Finite mist frame required')
            shaded['uMistOrigin'] = tuple(frame.tolist())
            shaded['uFloorContact'] = _floor_contact(floor, frame)
            if age_fade is not None:
                now, fade_in, max_age, fade_out = (float(v) for v in age_fade)
                if not all(math.isfinite(v) for v in (now, fade_in, max_age, fade_out)) or min(fade_in, max_age, fade_out) < 0:
                    raise ValueError('Ribbon age fade needs finite non-negative times')
                shaded['uAge'] = (now - float(packet.coordinate_origin), fade_in, max_age, fade_out)
        self._check_context(admit=True)
        if shaded is not None:
            # Edge-on widening works in pixels: the caller's current viewport is the scene target's.
            shaded['uViewport'] = tuple(float(v) for v in np.asarray(gl.glGetIntegerv(gl.GL_VIEWPORT)).reshape(-1)[2:4])
        program_before = gl_query.get_int(gl.GL_CURRENT_PROGRAM)
        vao_before = gl_query.get_int(gl.GL_VERTEX_ARRAY_BINDING)
        try:
            program = self.resources.program(shading, RIBBON_VERTEX, _FRAGMENTS[shading])
            vao, _ = self.resources.mesh('empty', (0., 0.), (2,))
            names = ('uMvp', 'uDiagnostic', 'uSurface', 'uSweepAxis') if shaded is None else ('uMvp', 'uSurface', 'uSweepAxis', *_MATERIAL_UNIFORMS)
            # Each pass reads only part of the material, so its unused uniforms are compiled out (location -1).
            uniforms = self.resources.uniforms(shading, names, required=shaded is None)
            if self.stream is None:
                alignment = gl_query.get_int(gl.GL_SHADER_STORAGE_BUFFER_OFFSET_ALIGNMENT)
                hold = MAX_PACKET_BYTES+alignment
                self.stream = StreamRing('ribbon knots', slots=3, slot_bytes=hold, hold_bytes=hold)
            gl.glUseProgram(program)
            gl.glBindVertexArray(vao)
            gl.glUniformMatrix4fv(uniforms['uMvp'], 1, gl.GL_FALSE, matrix.flatten(order='F'))
            gl.glUniform2f(uniforms['uSurface'], material.cross_curve, float(cross_divisions))
            gl.glUniform3f(uniforms['uSweepAxis'], *axis)
            if shaded is None:
                gl.glUniform1i(uniforms['uDiagnostic'], diagnostic)
            else:
                for name, value in shaded.items():
                    if name in ('uOrthographic', 'uFogVolume'):
                        gl.glUniform1i(uniforms[name], value)
                    elif len(value) == 16:
                        gl.glUniformMatrix4fv(uniforms[name], 1, gl.GL_FALSE, np.asarray(value, np.float32))
                    elif len(value) == 2:
                        gl.glUniform2f(uniforms[name], *value)
                    elif len(value) == 3:
                        gl.glUniform3f(uniforms[name], *value)
                    else:
                        _upload(uniforms[name], value)
            with self.stream.bound(gl.GL_SHADER_STORAGE_BUFFER, 0, packet.payload):
                if timing_query is not None:
                    gl.glBeginQuery(gl.GL_TIME_ELAPSED, timing_query)
                try:
                    gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, packet.vertices*cross_divisions, packet.instances)
                finally:
                    if timing_query is not None:
                        gl.glEndQuery(gl.GL_TIME_ELAPSED)
        finally:
            gl.glBindVertexArray(vao_before)
            gl.glUseProgram(program_before)

    def _draw_sparks(self, packet, mvp, sparks, now, mist, mist_frame, grade, material, sweep_axis, floor=None,
                     strays=None):
        """Additive point sprites, or with ``strays`` free strands, on the bound target (the caller sets blending,
        as for the light pass)."""
        if packet.instances == 0:
            return
        if now is None or not math.isfinite(float(now)):
            raise ValueError('Sparks need the absolute now of the ribbon clock')
        origin = np.asarray(packet.world_origin, dtype=float)
        matrix = np.asarray(mvp, dtype=float).reshape(4, 4, order='F').copy()
        matrix[:, 3] = matrix @ np.array((*origin, 1.))
        frame = origin + np.asarray(mist_frame, float)
        self._check_context(admit=True)
        program_before = gl_query.get_int(gl.GL_CURRENT_PROGRAM)
        vao_before = gl_query.get_int(gl.GL_VERTEX_ARRAY_BINDING)
        point_size_before = gl_query.is_enabled(gl.GL_PROGRAM_POINT_SIZE)
        try:
            kind = 'sparks' if strays is None else 'strays'
            program = (self.resources.program('sparks', RIBBON_SPARK_VERTEX, RIBBON_SPARK_FRAGMENT) if strays is None
                       else self.resources.program('strays', RIBBON_STRAY_VERTEX, RIBBON_STRAY_FRAGMENT))
            vao, _ = self.resources.mesh('empty', (0., 0.), (2,))
            names = ('uMvp', 'uSpark', 'uSparkLook', 'uSparkClock', 'uSparkWhite', 'uMist', 'uMistShape', 'uMistOrigin',
                     'uSurface','uSweepAxis', 'uFogVolume', 'uFogView', 'uFogLens', 'uFogRange', 'uGradeStops',
                     'uGrade', 'uFloorContact', 'uStray', 'uStrayLook', 'uStrayClock', 'uViewport', 'uStrayGlow')
            u = self.resources.uniforms(kind, names, required=False)
            if self.stream is None:
                alignment = gl_query.get_int(gl.GL_SHADER_STORAGE_BUFFER_OFFSET_ALIGNMENT)
                hold = MAX_PACKET_BYTES+alignment
                self.stream = StreamRing('ribbon knots', slots=3, slot_bytes=hold, hold_bytes=hold)
            gl.glUseProgram(program)
            gl.glBindVertexArray(vao)
            gl.glEnable(gl.GL_PROGRAM_POINT_SIZE)
            gl.glUniformMatrix4fv(u['uMvp'], 1, gl.GL_FALSE, matrix.astype(np.float32).flatten(order='F'))
            gl.glUniform3f(u['uSweepAxis'],*sweep_axis)
            gl.glUniform2f(u['uSurface'],material.cross_curve,1.)
            clock = (float(now) - float(packet.coordinate_origin), float(packet.coordinate_origin) % 1000.)
            if strays is None:
                gl.glUniform4f(u['uSpark'], float(sparks.per_knot), sparks.lifetime, sparks.drift, sparks.rise)
                gl.glUniform4f(u['uSparkLook'], sparks.smallest, sparks.largest, sparks.light, sparks.twinkle)
                gl.glUniform2f(u['uSparkClock'], *clock)
                gl.glUniform1f(u['uSparkWhite'], sparks.white)
            else:
                gl.glUniform4f(u['uStray'], float(strays.per_knot), strays.length, strays.reach, strays.chance)
                gl.glUniform4f(u['uStrayLook'], strays.width, strays.light, strays.beads, strays.peel_time)
                gl.glUniform2f(u['uStrayClock'], *clock)
                gl.glUniform2f(u['uStrayGlow'], strays.halo, strays.glow)
                gl.glUniform2f(u['uViewport'], *(float(v) for v in
                                                 np.asarray(gl.glGetIntegerv(gl.GL_VIEWPORT)).reshape(-1)[2:4]))
            mist_values = {'uMist': (0., 0., 1., 1.), 'uMistShape': (0., 0., 0., 0.), **FOG_OFF, **(mist or {})}
            gl.glUniform4f(u['uMist'], *mist_values['uMist'])
            gl.glUniform4f(u['uMistShape'], *mist_values['uMistShape'])
            gl.glUniform1i(u['uFogVolume'], mist_values['uFogVolume'])
            gl.glUniform4f(u['uFogRange'], *mist_values['uFogRange'])
            if 'uFogView' in mist_values:
                gl.glUniformMatrix4fv(u['uFogView'], 1, gl.GL_FALSE, np.asarray(mist_values['uFogView'], np.float32))
                gl.glUniform4f(u['uFogLens'], *mist_values['uFogLens'])
            gl.glUniform3f(u['uMistOrigin'], *frame)
            gl.glUniform3f(u['uFloorContact'], *_floor_contact(floor, frame))
            for name, value in {**GRADE_OFF, **(grade or {})}.items():
                _upload(u[name], value)
            with self.stream.bound(gl.GL_SHADER_STORAGE_BUFFER, 0, packet.payload):
                if strays is None:
                    gl.glDrawArraysInstanced(gl.GL_POINTS, 0, MAX_PATH_SAMPLES*sparks.per_knot, packet.instances)
                else:
                    gl.glDrawArraysInstanced(gl.GL_TRIANGLES, 0, MAX_PATH_SAMPLES*strays.per_knot*STRAY_SEGMENTS*6,
                                             packet.instances)
        finally:
            (gl.glEnable if point_size_before else gl.glDisable)(gl.GL_PROGRAM_POINT_SIZE)
            gl.glBindVertexArray(vao_before)
            gl.glUseProgram(program_before)

    @staticmethod
    def _material_uniforms(view, translate, orthographic, material):
        if view is None or len(view) != 16 or not all(math.isfinite(v) for v in view):
            raise ValueError('Material shading needs the finite world view matrix')
        rebased = np.asarray(view, dtype=float).reshape(4, 4, order='F').copy()
        rebased[:, 3] = rebased @ translate
        forward = -rebased[2, :3]
        length = float(np.linalg.norm(forward))
        if not length > 0:
            raise ValueError('View matrix has no forward axis')
        eye = np.linalg.inv(rebased) @ np.array((0., 0., 0., 1.))
        values = dict(uViewZ=tuple(rebased[2]), uEye=tuple(eye[:3]/eye[3]), uForward=tuple(forward/length),
                      uOrthographic=int(orthographic), **material.uniforms())
        if not all(np.isfinite(v).all() for k, v in values.items() if k != 'uOrthographic'):
            raise ValueError('Rebased view exceeds finite range')
        return values

    def _check_context(self, *, admit=False):
        from PySide6.QtGui import QOpenGLContext
        current = QOpenGLContext.currentContext()
        if current is None:
            raise RuntimeError('Ribbon GL work requires its owning current context')
        if self._context_ref is None and admit:
            self._context_ref = weakref.ref(current)
        if self._context_ref is None or self._context_ref() != current:
            raise RuntimeError('Ribbon primitive used in a foreign context')

    def release(self):
        if self.has_resources:
            self._check_context()
        if self.stream is not None:
            self.stream.release()
        self.resources.release_resources()
        self.stream = None
        self._context_ref = None
