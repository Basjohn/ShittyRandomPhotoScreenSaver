"""Lazy WR-02 strip primitive; caller owns target/depth/blend and context scope.

``shading='diagnostic'`` draws the WR-02a diagnostics. ``'body'`` and ``'light'`` are the filament material's two
passes (``rendering/gl_programs/ribbon.py``): the caller draws ``body`` inside ``SceneTarget.transparent_writes`` and
``light`` afterwards inside ``emission_writes`` with additive blending on colour. Both need the world view matrix,
which is rebased with the packet origin exactly as the MVP is, so no shader mixes local and absolute space.
"""
import math
import weakref
from contextlib import contextmanager

import numpy as np
from OpenGL import GL as gl
from PySide6.QtGui import QOpenGLContext

from core.ribbon_style import RibbonMaterial, RibbonSparks, RibbonStrays
from core.ribbon_packet import MAX_PACKET_BYTES, MAX_RIBBONS, RIBBON_BYTES, KNOT_ROWS, RibbonPacket
from core.ribbon_frames import MAX_STRIP_STATIONS
from rendering.gl_programs.ribbon import (RIBBON_BODY_FRAGMENT, RIBBON_FRAGMENT, RIBBON_LIGHT_FRAGMENT,
                                          RIBBON_SPARK_FRAGMENT, RIBBON_SPARK_VERTEX, RIBBON_STRAY_FRAGMENT,
                                          RIBBON_STRAY_VERTEX, RIBBON_VERTEX, RIBBON_CONTINUOUS_VERTEX)
from rendering.gl_programs.ribbon import RIBBON_COHORT_STRAY_VERTEX,RIBBON_COHORT_STRAY_FRAGMENT
from core.ribbon_strand_cohorts import COHORT_BYTES,COHORT_ROWS
from core.ribbon_geometry import MAX_PATH_SAMPLES
from rendering.gl_programs.mist import FOG_OFF
from rendering.quick import gl_query
from rendering.quick.scene3d.resources import MeshResources, warm_programs
from rendering.quick.scene3d.stream import StreamRing

_FRAGMENTS = {'diagnostic': RIBBON_FRAGMENT, 'body': RIBBON_BODY_FRAGMENT, 'light': RIBBON_LIGHT_FRAGMENT}
_MATERIAL_UNIFORMS = ('uViewZ', 'uEye', 'uStrands', 'uRim', 'uBody', 'uFill', 'uGlint', 'uAge',
                      'uMist', 'uMistShape', 'uMistOrigin', 'uTone',
                      'uViewport', 'uFogVolume', 'uFogView', 'uFogLens', 'uFogRange', 'uGradeStops', 'uGrade', 'uFloorContact', 'uGlow',
                      'uLattice', 'uLatticeTone')
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


# Texture unit of the yielding floor's field (``rendering.quick.scene3d.floor_give``); a plain constant here so the
# primitive stays free of any scene owner.
FLOOR_GIVE_UNIT = 13


def _apply_floor_give(locations, floor_give, frame):
    """``floor_give`` = (field texture, ``uFloorGive`` vec4[, history side]) from the scene's yielding floor, or None
    (off: the contact eases onto the rigid plane, exactly as without the option). The side (-1: the packet's x axis
    is mirrored into the world, Travel Direction) defaults to +1. Always written: program uniforms persist."""
    if floor_give is None:
        gl.glUniform4f(locations['uFloorGive'], 0., 0., 1., 1.)
        return
    texture, values, *side = floor_give
    gl.glBindTextureUnit(FLOOR_GIVE_UNIT, int(texture))
    gl.glUniform1i(locations['uFloorGiveField'], FLOOR_GIVE_UNIT)
    gl.glUniform4f(locations['uFloorGive'], *values)
    gl.glUniform3f(locations['uFloorGiveFrame'], float(frame[0]), float(frame[2]), float(side[0]) if side else 1.)


_FLOOR_GIVE_UNIFORMS = ('uFloorGive', 'uFloorGiveField', 'uFloorGiveFrame')

# Texture unit of the Pulse Rim field (``rendering.quick.scene3d.pulse_rim``): clear of the floor's 0-4, the mist's 8-12
# and 15, the yielding floor's 13 and the world field's 14. Bound for the light pass only and unbound after it.
PULSE_RIM_UNIT = 7
_PULSE_RIM_UNIFORMS = ('uPulseRim', 'uPulseRimField', 'uPulseRimShape')


def _apply_pulse_rim(locations, pulse_rim):
    """``pulse_rim`` = (field texture, ``uPulseRim`` vec4, ``uPulseRimShape`` vec2) from the scene's Pulse Rim field,
    or None (off: the rims exactly as without the option). Always written: program uniforms persist. Returns whether
    a texture was bound."""
    if pulse_rim is None:
        gl.glUniform4f(locations['uPulseRim'], 0., 0., 0., 0.)
        return False
    texture, values, shape = pulse_rim
    gl.glBindTextureUnit(PULSE_RIM_UNIT, int(texture))
    gl.glUniform1i(locations['uPulseRimField'], PULSE_RIM_UNIT)
    gl.glUniform4f(locations['uPulseRim'], *values)
    gl.glUniform2f(locations['uPulseRimShape'], *shape)
    return True


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


def _continuation_draw_ranges(packet, continuation, frame_x, cross_divisions):
    """Cull draw intervals only; retain original gl_VertexIDs and tessellation.

    The monotone B-spline's exact axial station boundaries can be searched from
    a few ring controls. Neither the packet nor any world-space field changes.
    Endpoint strips keep their original endpoint-anchored quadratic lattice;
    inverse lattice coordinates skip only intervals wholly outside the view.
    """
    x0,x1,budget=continuation
    if (not all(math.isfinite(v) for v in (x0,x1,frame_x)) or x1<x0
            or not isinstance(budget,int) or not 1<=budget<=2048):
        raise ValueError('Continuation needs an ordered finite span and bounded subdivisions')
    x0,x1=x0-frame_x,x1-frame_x
    rows=np.frombuffer(packet.payload,np.float32).reshape(packet.instances,-1,4)
    first_interval,last_interval=math.inf,0
    edges=[]
    for path in rows:
        count,start,capacity,subdivisions=int(path[0,0]),int(path[1,1]),int(path[1,2]),int(path[0,1])
        if not 3<=count<=capacity or not 1<=subdivisions<=8:
            raise ValueError('Continuation needs at least three monotone cloth controls')
        def axial(index):
            return float(path[4+((start+index)%capacity)*KNOT_ROWS,0])
        first,last=axial(0),axial(count-1)
        edges.append((first,last))
        if x0>last or x1<first:continue
        def boundary(index):
            if index==0:return first
            if index==count-1:return last
            return (axial(index-1)+4.*axial(index)+axial(index+1))/6.
        def lower_bound(value):
            low,high=0,count
            while low<high:
                middle=(low+high)//2
                if boundary(middle)<value:low=middle+1
                else:high=middle
            return low
        # A one-station halo covers clip-plane rounding and closed-interval boundaries.
        begin=max(0,lower_bound(x0)-2)
        end=min(count-1,lower_bound(x1)+1)
        first_interval=min(first_interval,begin*subdivisions)
        last_interval=max(last_interval,end*subdivisions)
    stride=6*cross_divisions
    body=((int(first_interval)*stride,(last_interval-int(first_interval))*stride)
          if first_interval<last_interval else (0,0))
    extensions=[]
    for side in (-1.,1.):
        extents=[(first-x0 if side<0 else x1-last) for first,last in edges]
        if max(extents)<=0.:continue
        divisions=min(budget,max(16,math.ceil(2.*max(extents)/.15)))
        starts=[]
        for (first,last),extent in zip(edges,extents):
            if extent<=0.:continue
            invisible=(first-x1 if side<0 else x0-last)
            t=math.sqrt(max(0.,invisible)/extent)
            starts.append(max(0,min(divisions-1,math.floor(t*divisions)-1)))
        begin=min(starts)
        extensions.append((side,divisions,begin*stride,(divisions-begin)*stride))
    return body,(x0,x1),extensions








class RibbonPrimitive:
    def __init__(self):
        self.resources = MeshResources('ribbon primitive')
        self.stream = None
        self._context_ref = None
        self._held_packet = self._lease = None
        self.strand_resources = self.strand_stream = None
        self._strand_bounds_payload=None
        self._strand_bounds=(0.,0.)
        # Culled draw intervals of the bound packet: every pass of a frame (body, light, reflected light) asks for the
        # same ones, so they are found once per packet payload.
        self._ranges_payload=None
        self._ranges={}
        self._material_cache=None

    @property
    def has_resources(self):
        return (self.resources.has_resources or (self.stream is not None and self.stream.has_resources)
                or (self.strand_resources is not None and self.strand_resources.has_resources)
                or (self.strand_stream is not None and self.strand_stream.has_resources))

    @property
    def stream_bytes(self):
        return self.stream.capacity if self.stream is not None and self.stream.has_resources else 0

    def prepare_programs(self, *, sparks=False, strays=False, continuation=False, strand_cohorts=False):
        """One hidden-frame compile, admitted under this primitive's owning context before allocation."""
        self._check_context(admit=True)
        vertex=RIBBON_CONTINUOUS_VERTEX if continuation else RIBBON_VERTEX
        suffix='_continuous' if continuation else ''
        programs=[(self.resources,'body'+suffix,vertex,RIBBON_BODY_FRAGMENT),
                  (self.resources,'light'+suffix,vertex,RIBBON_LIGHT_FRAGMENT)]
        if sparks:programs.append((self.resources,'sparks',RIBBON_SPARK_VERTEX,RIBBON_SPARK_FRAGMENT))
        if strays:
            resources=self._strand_resources() if strand_cohorts else self.resources
            vertex=RIBBON_COHORT_STRAY_VERTEX if strand_cohorts else RIBBON_STRAY_VERTEX
            programs.append((resources,'strays',vertex,RIBBON_COHORT_STRAY_FRAGMENT if strand_cohorts else RIBBON_STRAY_FRAGMENT))
        return warm_programs(programs)

    def _strand_resources(self):
        if self.strand_resources is None:self.strand_resources=MeshResources('ribbon strand cohorts')
        return self.strand_resources

    def _stream(self):
        if self.stream is None:
            alignment=gl_query.get_int(gl.GL_SHADER_STORAGE_BUFFER_OFFSET_ALIGNMENT)
            hold=MAX_PACKET_BYTES+alignment
            # Four frames' packets per slot: a fence (and its later wait) every fourth frame, not every frame.
            self.stream=StreamRing('ribbon knots',slots=3,slot_bytes=4*hold,hold_bytes=hold)
        return self.stream

    @contextmanager
    def packet_scope(self,packet,*,restore=True):
        """Upload once for a whole scene; every pass rebinds this fenced range after intervening consumers.
        ``restore=False``: the scene owns storage binding 0 for its frame (nothing read back; left unbound)."""
        if self._held_packet is not None:raise RuntimeError('Ribbon packet scope cannot nest')
        self._check_context(admit=True)
        if not packet.payload:
            yield
            return
        with self._stream().bound(gl.GL_SHADER_STORAGE_BUFFER,0,packet.payload,reuse=True,restore=restore) as lease:
            self._held_packet,self._lease=packet,lease
            try:yield
            finally:self._held_packet=self._lease=None

    def _draw_ranges(self,packet,continuation,frame_x,cross_divisions):
        """``_continuation_draw_ranges`` of this packet, computed once per payload and query."""
        if packet.payload is not self._ranges_payload:
            self._ranges_payload,self._ranges=packet.payload,{}
        key=(tuple(continuation),frame_x,cross_divisions)
        ranges=self._ranges.get(key)
        if ranges is None:
            ranges=self._ranges[key]=_continuation_draw_ranges(packet,continuation,frame_x,cross_divisions)
        return ranges

    @contextmanager
    def _packet_bound(self,packet):
        if self._held_packet is not None:
            if packet is not self._held_packet:raise RuntimeError('Different packet inside the active ribbon scene scope')
            self._lease.rebind()
            yield
        else:
            with self._stream().bound(gl.GL_SHADER_STORAGE_BUFFER,0,packet.payload):yield

    def draw(self, packet: RibbonPacket, mvp, *, diagnostic=0, timing_query=None, shading='diagnostic',
             view=None, material: RibbonMaterial | None = None, age_fade=None,
             mist=None, mist_frame=(0., 0., 0.), sparks: RibbonSparks | None = None, now=None, sweep_axis=None,
             grade=None, floor=None, strays: RibbonStrays | None = None, continuation=None,
             strand_births=None,strand_origin=0.,floor_give=None,pulse_rim=None,viewport=None,restore=True):
        """``age_fade`` = (absolute now, fade-in s, maximum age s, fade-out s) fades the head and tail by age.

        ``viewport`` (width, height) is the bound target's viewport when the caller knows it; otherwise it is read
        back. ``restore=False`` is for a caller that owns the GL state of its whole frame (a scene): the program, vertex
        array and storage binding are neither read back nor restored (each read is a driver round trip).

        ``pulse_rim`` = (field texture, ``uPulseRim``) brightens the light pass's rims where the pulse is; other
        shadings ignore it.

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
                                     (strays or RibbonStrays()) if shading == 'strays' else None,
                                     strand_births,strand_origin,continuation,floor_give,viewport,restore)
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
        if continuation is not None and axis!=(1.,0.,0.):
            raise ValueError('Continuation requires the monotone world-x cloth sweep')
        ranges=None
        if continuation is not None:
            frame=origin+np.asarray(mist_frame,float)
            ranges=self._draw_ranges(packet,continuation,float(frame[0]),cross_divisions)
        if shading != 'diagnostic':
            shaded = self._material(view, translate, material)
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
            shaded['uViewport'] = (tuple(float(v) for v in viewport) if viewport is not None else
                                   tuple(float(v) for v in gl_query.get_ints(gl.GL_VIEWPORT, 4)[2:4]))
        program_before = gl_query.get_int(gl.GL_CURRENT_PROGRAM) if restore else None
        vao_before = gl_query.get_int(gl.GL_VERTEX_ARRAY_BINDING) if restore else None
        rim_bound = False
        try:
            key=shading+('_continuous' if continuation is not None else '')
            vertex=RIBBON_CONTINUOUS_VERTEX if continuation is not None else RIBBON_VERTEX
            program = self.resources.program(key, vertex, _FRAGMENTS[shading])
            vao, _ = self.resources.mesh('empty', (0., 0.), (2,))
            names = ('uMvp', 'uDiagnostic', 'uSurface', 'uSweepAxis', 'uFloorContact') if shaded is None else ('uMvp', 'uSurface', 'uSweepAxis', *_MATERIAL_UNIFORMS)
            if continuation is not None:names+=('uContinuation',)
            if shading == 'light':names+=_PULSE_RIM_UNIFORMS
            # Each pass reads only part of the material, so its unused uniforms are compiled out (location -1).
            uniforms = self.resources.uniforms(key, names+_FLOOR_GIVE_UNIFORMS, required=shaded is None)
            self._stream()
            gl.glUseProgram(program)
            gl.glBindVertexArray(vao)
            gl.glUniformMatrix4fv(uniforms['uMvp'], 1, gl.GL_FALSE, matrix.flatten(order='F'))
            gl.glUniform2f(uniforms['uSurface'], material.cross_curve, float(cross_divisions))
            gl.glUniform3f(uniforms['uSweepAxis'], *axis)
            _apply_floor_give(uniforms, floor_give, origin+np.asarray(mist_frame, float))
            if shading == 'light':rim_bound = _apply_pulse_rim(uniforms, pulse_rim)
            if continuation is not None:gl.glUniform4f(uniforms['uContinuation'],0.,0.,0.,0.)
            if shaded is None:
                gl.glUniform1i(uniforms['uDiagnostic'], diagnostic)
                gl.glUniform3f(uniforms['uFloorContact'],*_floor_contact(floor,origin+np.asarray(mist_frame,float)))
            else:
                for name, value in shaded.items():
                    if name == 'uFogVolume':
                        gl.glUniform1i(uniforms[name], value)
                    elif len(value) == 16:
                        gl.glUniformMatrix4fv(uniforms[name], 1, gl.GL_FALSE, np.asarray(value, np.float32))
                    elif len(value) == 2:
                        gl.glUniform2f(uniforms[name], *value)
                    elif len(value) == 3:
                        gl.glUniform3f(uniforms[name], *value)
                    else:
                        _upload(uniforms[name], value)
            with self._packet_bound(packet):
                if timing_query is not None:
                    gl.glBeginQuery(gl.GL_TIME_ELAPSED, timing_query)
                try:
                    body,span,extensions=(ranges if ranges is not None else
                        ((0,packet.vertices*cross_divisions),None,()))
                    if body[1]:gl.glDrawArraysInstanced(gl.GL_TRIANGLES,body[0],body[1],packet.instances)
                    if ranges is not None:
                        for side,divisions,first,count in extensions:
                            gl.glUniform4f(uniforms['uContinuation'],*span,float(divisions),side)
                            gl.glDrawArraysInstanced(gl.GL_TRIANGLES,first,count,packet.instances)
                finally:
                    if timing_query is not None:
                        gl.glEndQuery(gl.GL_TIME_ELAPSED)
        finally:
            if rim_bound:gl.glBindTextureUnit(PULSE_RIM_UNIT, 0)
            if restore:
                gl.glBindVertexArray(vao_before)
                gl.glUseProgram(program_before)

    def _draw_sparks(self, packet, mvp, sparks, now, mist, mist_frame, grade, material, sweep_axis, floor=None,
                     strays=None,strand_births=None,strand_origin=0.,continuation=None,floor_give=None,viewport=None,
                     restore=True):
        """Additive point sprites, or with ``strays`` free strands, on the bound target (the caller sets blending,
        as for the light pass). Strands are triangles: program point size is left alone for them."""
        if packet.instances == 0:
            return
        cohorts=strays is not None and strand_births is not None
        if cohorts:
            if not isinstance(strand_births,bytes) or len(strand_births) not in (0,packet.instances*COHORT_BYTES):
                raise ValueError('Strand cohorts must match the packet physical knot slots')
            if not strand_births:return
            if strand_births is not self._strand_bounds_payload:
                held=np.frombuffer(strand_births,np.float32).reshape(-1,COHORT_ROWS,4)
                self._strand_bounds=(float(held[:,1,0].max()),float(held[:,1,1].max()))
                self._strand_bounds_payload=strand_births
        if now is None or not math.isfinite(float(now)):
            raise ValueError('Sparks need the absolute now of the ribbon clock')
        origin = np.asarray(packet.world_origin, dtype=float)
        matrix = np.asarray(mvp, dtype=float).reshape(4, 4, order='F').copy()
        matrix[:, 3] = matrix @ np.array((*origin, 1.))
        frame = origin + np.asarray(mist_frame, float)
        self._check_context(admit=True)
        program_before = gl_query.get_int(gl.GL_CURRENT_PROGRAM) if restore else None
        vao_before = gl_query.get_int(gl.GL_VERTEX_ARRAY_BINDING) if restore else None
        points = strays is None
        point_size_before = gl_query.is_enabled(gl.GL_PROGRAM_POINT_SIZE) if points else None
        try:
            kind = 'sparks' if strays is None else 'strays'
            resources=self._strand_resources() if cohorts else self.resources
            program = (resources.program('sparks', RIBBON_SPARK_VERTEX, RIBBON_SPARK_FRAGMENT) if strays is None
                       else resources.program('strays',RIBBON_COHORT_STRAY_VERTEX if cohorts else RIBBON_STRAY_VERTEX,RIBBON_COHORT_STRAY_FRAGMENT if cohorts else RIBBON_STRAY_FRAGMENT))
            vao, _ = self.resources.mesh('empty', (0., 0.), (2,))
            names = ('uMvp', 'uSpark', 'uSparkLook', 'uSparkClock', 'uSparkWhite', 'uMist', 'uMistShape', 'uMistOrigin',
                     'uSurface','uSweepAxis', 'uFogVolume', 'uFogView', 'uFogLens', 'uFogRange', 'uGradeStops',
                     'uGrade', 'uFloorContact', 'uStray', 'uStrayLook', 'uStrayClock', 'uViewport', 'uStrayGlow', 'uStrayAdmission','uStrayBirthNow','uStrayPulse')
            u = resources.uniforms(kind, names+_FLOOR_GIVE_UNIFORMS, required=False)
            self._stream()
            gl.glUseProgram(program)
            gl.glBindVertexArray(vao)
            if points:gl.glEnable(gl.GL_PROGRAM_POINT_SIZE)
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
                gl.glUniform1f(u['uStrayAdmission'], strays.admission_softness)
                if cohorts:
                    gl.glUniform1f(u['uStrayBirthNow'],float(now)-float(strand_origin))
                    gl.glUniform2f(u['uStrayPulse'],strays.pulse_growth,strays.pulse_glow)
                gl.glUniform2f(u['uViewport'], *(float(v) for v in viewport) if viewport is not None else
                               (float(v) for v in gl_query.get_ints(gl.GL_VIEWPORT, 4)[2:4]))
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
            _apply_floor_give(u, floor_give, frame)
            for name, value in {**GRADE_OFF, **(grade or {})}.items():
                _upload(u[name], value)
            with self._packet_bound(packet):
                if strays is None:
                    gl.glDrawArraysInstanced(gl.GL_POINTS, 0, MAX_PATH_SAMPLES*sparks.per_knot, packet.instances)
                else:
                    first,count=0,MAX_PATH_SAMPLES
                    if cohorts and continuation is not None:
                        rows=np.frombuffer(packet.payload,np.float32).reshape(packet.instances,-1,4)
                        step=0.
                        for path in rows:
                            n,start,cap=int(path[0,0]),int(path[1,1]),int(path[1,2])
                            a=path[4+start*KNOT_ROWS,0];b=path[4+((start+n-1)%cap)*KNOT_ROWS,0]
                            step=max(step,float(b-a)/max(n-1,1))
                        length,reach=self._strand_bounds
                        length*=1.+strays.pulse_growth
                        span=(continuation[0]-length*step-1.25*reach,
                              continuation[1]+1.25*reach,continuation[2])
                        body,_,_=self._draw_ranges(packet,span,float(frame[0]),1)
                        subdivisions=int(rows[0,0,1])
                        first=body[0]//(6*subdivisions)
                        count=min(MAX_PATH_SAMPLES-first,body[1]//(6*subdivisions)+1) if body[1] else 0
                    stride=strays.per_knot*STRAY_SEGMENTS*6
                    if cohorts:
                        if self.strand_stream is None:
                            alignment=gl_query.get_int(gl.GL_SHADER_STORAGE_BUFFER_OFFSET_ALIGNMENT)
                            size=MAX_RIBBONS*COHORT_BYTES+alignment
                            # Two binds a frame (direct and reflected), four per slot: a fence every second frame,
                            # and a reused slot was last read four frames ago, so no wait ties a frame to the last.
                            self.strand_stream=StreamRing('ribbon strand cohorts',slots=3,slot_bytes=4*size,hold_bytes=size)
                        with self.strand_stream.bound(gl.GL_SHADER_STORAGE_BUFFER,1,strand_births,restore=restore):
                            gl.glDrawArraysInstanced(gl.GL_TRIANGLES,first*stride,count*stride,packet.instances)
                    else:gl.glDrawArraysInstanced(gl.GL_TRIANGLES,first*stride,count*stride,packet.instances)
        finally:
            if points:(gl.glEnable if point_size_before else gl.glDisable)(gl.GL_PROGRAM_POINT_SIZE)
            if restore:
                gl.glBindVertexArray(vao_before)
                gl.glUseProgram(program_before)

    def _material(self, view, translate, material):
        """``_material_uniforms``, once per (view, origin, material): a frame's body and light passes share them."""
        key = (tuple(view) if view is not None else None, tuple(translate), material)
        cached = self._material_cache
        if cached is None or cached[0] != key:
            cached = self._material_cache = (key, self._material_uniforms(view, translate, material))
        return dict(cached[1])

    @staticmethod
    def _material_uniforms(view, translate, material):
        if view is None or len(view) != 16 or not all(math.isfinite(v) for v in view):
            raise ValueError('Material shading needs the finite world view matrix')
        rebased = np.asarray(view, dtype=float).reshape(4, 4, order='F').copy()
        rebased[:, 3] = rebased @ translate
        forward = -rebased[2, :3]
        length = float(np.linalg.norm(forward))
        if not length > 0:
            raise ValueError('View matrix has no forward axis')
        eye = np.linalg.inv(rebased) @ np.array((0., 0., 0., 1.))
        values = dict(uViewZ=tuple(rebased[2]), uEye=tuple(eye[:3]/eye[3]), **material.uniforms())
        if not all(np.isfinite(v).all() for v in values.values()):
            raise ValueError('Rebased view exceeds finite range')
        return values

    def _check_context(self, *, admit=False):
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
        errors=[]
        for release in (self.release_strands,self.resources.release_resources,
                        *((self.stream.release,) if self.stream is not None else ())):
            try:release()
            except Exception as error:errors.append(error)
        if errors:raise ExceptionGroup('Ribbon resources remain for retry',errors)
        self.stream=None;self._context_ref=None

    def release_strands(self):
        if self.strand_resources is None and self.strand_stream is None:return
        self._check_context()
        errors=[]
        for release in ((*((self.strand_stream.release,) if self.strand_stream is not None else ()),
                         *((self.strand_resources.release_resources,) if self.strand_resources is not None else ()))):
            try:release()
            except Exception as error:errors.append(error)
        if errors:raise ExceptionGroup('Strand resources remain for retry',errors)
        self.strand_resources=self.strand_stream=None
        self._strand_bounds_payload=None
        self._strand_bounds=(0.,0.)
