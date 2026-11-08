"""The straightforward forms of Waveform's logical-tick hot paths before the 6 Nov 2026 tick cut (main a30dae99).
(Group Wave's lead gradient, formerly ``np.gradient``, is checked by patching ``uniform_gradient`` with it.)

They are the oracle of ``tests/test_waveform_logical_tick_exactness.py``: each is patched over its production
counterpart and the published frames must stay byte-identical. Keep them as written (operation order included);
they are not production code and must never be imported by it.
"""
from __future__ import annotations

from dataclasses import astuple, fields, replace
import math

import numpy as np

import core.waveform_ribbon_dynamics as dyn
from core.ribbon_packet import KNOT_ROWS
from core.ribbon_style import RibbonMaterial, RibbonSparks, RibbonStrays
from core.waveform_ribbon_authoring import TARGETS


def elastic(position, velocity, target, dt, frequency, damping):
    omega = 2*math.pi*frequency
    wd = omega*math.sqrt(1.-damping*damping)
    decay = math.exp(-damping*omega*dt)
    sine, cosine = math.sin(wd*dt), math.cos(wd*dt)
    offset = position-target
    x = target+decay*(offset*cosine+(velocity+damping*omega*offset)*sine/wd)
    v = decay*(velocity*cosine-(omega*omega*offset+damping*omega*velocity)*sine/wd)
    return x,v


def advance_springs(self, dt, bands, impulses):
    c = self.controls
    for owner,card in enumerate(c.cards):
        support = 1. if card['band']=='All' else bands[('Bass','Mids','Highs').index(card['band'])]
        for index,target in enumerate((self.drive['bend'],self.drive['torsion'],self.drive['depth'])):
            self._push[owner][index] += support*impulses[index]*c.impulse*self._impulse_scales[index]
            delivered = self._push[owner][index]*(1.-math.exp(-dt/dyn.IMPULSE_SPREAD))
            self._push[owner][index] -= delivered
            self.velocity[owner][index] += delivered
            self.spring[owner][index],self.velocity[owner][index] = elastic(
                self.spring[owner][index],self.velocity[owner][index],target*support,dt,
                self._elastic_frequencies[index],c.damping)


def carry_fields(self, decays, seen, sources, sigma, shift, blur, release, travelling):
    grid = dyn.PULSE_GRID
    for fields_,decay in zip((self._pulse,self._fresh),decays):
        for index,sign in enumerate((-1.,1.)):
            field = fields_[index]
            if not field.any() and not (travelling and release):
                continue
            if shift:
                field[:] = np.interp(grid-sign*shift,grid,field,left=0.,right=0.)
            if blur:
                field[1:-1] += blur*(field[:-2]-2.*field[1:-1]+field[2:])
            field *= decay if seen is None else decay[index]
            for origin,direction in sources:
                if travelling and direction==sign and release:
                    field += release/len(sources)*np.exp(-.5*((grid-origin)/sigma)**2)
            field[field<1e-9] = 0.


def surge(self, data, x, y, z, amount, drift=None):
    drift = self.pulse_drift(x)*amount if drift is None else drift
    if not np.any(drift):
        return x,y,z
    x,y,z = x.copy(),y.copy(),z.copy()
    windows = {}
    for index,path in enumerate(data):
        count,start,capacity = int(path[0,0]),int(path[1,1]),int(path[1,2])
        if count>=4:
            windows.setdefault((count,start,capacity),[]).append(index)
    for (count,start,capacity),members in windows.items():
        order = (start+np.arange(count))%capacity
        rows = np.asarray(members)[:,None]
        xs,ds = x[rows,order],drift[rows,order]
        moving = ds.any(axis=1)
        if not moving.any():
            continue
        rows,xs,ds = rows[moving],xs[moving],ds[moving]
        edge = np.clip(np.minimum(xs-xs[:,:1],xs[:,-1:]-xs)/dyn.SURGE_TAPER,0.,1.)
        ds = ds*(edge*edge*(3.-2.*edge))
        squeeze = (np.diff(ds,axis=1)/np.diff(xs,axis=1)).min(axis=1,keepdims=True)
        limited = squeeze < -dyn.SURGE_MAX_COMPRESSION
        bound = np.where(limited,dyn.SURGE_MAX_COMPRESSION/np.where(limited,-squeeze,1.),1.)
        for row,member in enumerate(rows[:,0]):
            previous,when = self._surge_bound.get(int(member),(1.,None))
            if when is not None and self.time>=when:
                bound[row,0] = min(bound[row,0],previous+dyn.SURGE_BOUND_RISE*(self.time-when))
            self._surge_bound[int(member)] = (float(bound[row,0]),self.time)
        ds = ds*bound
        target = xs+ds
        cell = np.stack([np.searchsorted(row,goal) for row,goal in zip(xs,target)])
        cell = np.clip(cell-1,0,count-2)
        left,right = np.take_along_axis(xs,cell,1),np.take_along_axis(xs,cell+1,1)
        h = right-left
        t = (target-left)/h
        cube = t**3
        h00,h10,h01,h11 = 2*cube-3*t*t+1,cube-2*t*t+t,-2*cube+3*t*t,cube-t*t
        vs = np.stack((y[rows,order],z[rows,order]))
        slope = dyn.apply_row_gradient(vs,dyn.row_gradient_coefficients(xs))
        pick = lambda field,at: np.take_along_axis(field,at[None],2)
        resampled = (h00*pick(vs,cell)+h10*h*pick(slope,cell)+h01*pick(vs,cell+1)+h11*h*pick(slope,cell+1))
        y[rows,order],z[rows,order] = resampled[0],resampled[1]
        x[rows,order] = target
    return x,y,z


def fade_ribbons(self, data, rows):
    for index,share in enumerate(self.count_share):
        share = share*self.direction_share
        data[index,2,:3] = self.controls.cards[index]['quiet'][0]
        data[index,3,:3] = self.controls.cards[index]['quiet'][1]
        rows[index,:,1:3] *= share
        rows[index,:,3] = np.maximum(1e-5,rows[index,:,3]*share)
        data[index,2:4,3] *= share
        data[index,7::KNOT_ROWS,3] *= share
        data[index,6::KNOT_ROWS,3] *= share


def material_values(material):
    """The values RibbonMaterial.__post_init__ checked as written (astuple)."""
    return astuple(material)


def capture_values(widget, pres, spec):
    """capture_waveform_ribbon's per-tick reads as written: all values, the configuration and the camera."""
    from core.settings.visualizer_mode_settings import control_runtime_attr
    from widgets.spotify_visualizer.waveform_ribbon_capture import _CAMERA_KEYS
    values = {control.key:getattr(widget if control.logical else pres,control_runtime_attr(control))
              for control in spec.body_controls}
    configuration = {key:value for key,value in values.items() if key not in _CAMERA_KEYS}
    camera = {key:value for key,value in values.items() if key.startswith('waveform_ribbon_camera_')
              or key in ('waveform_ribbon_turn','waveform_ribbon_tilt','waveform_ribbon_scene_scale',
                         'waveform_ribbon_scene_pan_x','waveform_ribbon_scene_pan_y')}
    return values, configuration, camera


def scene(self, snapshot):
    PREFIX = 'waveform_ribbon_'
    p=self.values
    drives=dict(snapshot.drives) if snapshot.ready else {key:0. for key in TARGETS}
    realized=dict(snapshot.realized) if snapshot.ready else {key:self.controls.ranges[key][0] for key in TARGETS}
    def read(key):return p[PREFIX+key]
    def pair(key,drive):
        low,high=read(key)
        return float(low)+(float(high)-float(low))*max(0.,min(1.,drive))
    passage=snapshot.passage;sparkle=drives['sparkle'];highlights=drives['highlights']
    material={}
    for field in fields(RibbonMaterial):
        key='material_'+field.name
        material[field.name]=(pair(key,highlights if field.name.startswith('glint') else passage)
                              if PREFIX+key in p else getattr(self.base.material,field.name))
    for key in ('strand_light','rim_light','fill_light','rim_glow_light'):
        material[key]*=realized['light']
    material['glint_density']*=.5+realized['highlights']
    material['glint_chance']*=min(1.,realized['highlights'])
    fog=None
    if read('mist_enabled'):
        tier=str(read('quality'))
        fog=replace(self.base.fog,density=pair('fog_density',passage),clearance=pair('fog_clearance',passage),
            height=pair('fog_height',passage),softness=pair('fog_softness',passage),light=pair('fog_light',passage),
            noise=pair('fog_variation',passage),drift=pair('fog_drift',passage),
            slices={'Low':96,'Medium':128,'High':160}[tier],cell={'Low':32,'Medium':24,'High':16}[tier])
    colour=tuple(float(v)/255. for v in read('floor_tint')[:3])
    tint=tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in colour)
    floor=replace(self.base.floor,reflection=pair('floor_reflection',passage),
        albedo_gain=pair('floor_brightness',passage),tint=tint,f0=pair('floor_wetness',passage),
        streak=(pair('floor_streak',passage),*self.base.floor.streak[1:]),
        column=(pair('floor_column',passage),*self.base.floor.column[1:]),
        glow_limit=float(read('floor_glow_limit')),hue=float(read('floor_colour')),
        hot=(float(read('floor_contrast')),*self.base.floor.hot[1:]),
        light_reach=float(read('floor_light_reach')),light_far=float(read('floor_light_far')),
        give=float(read('floor_give')))
    sparks=None
    if read('sparks_enabled'):
        size=pair('spark_size',sparkle)
        sparks=RibbonSparks(per_knot=16,lifetime=pair('spark_lifetime',sparkle),
            drift=pair('spark_drift',sparkle),rise=pair('spark_rise',sparkle),smallest=min(1.2,size),
            largest=size,light=pair('spark_light',sparkle),white=pair('spark_white',sparkle))
    strays=None
    if read('strands_enabled'):
        strays=RibbonStrays(per_knot=8,length=pair('strand_length',sparkle),reach=pair('strand_reach',sparkle),
            chance=pair('strand_chance',sparkle)*pair('strand_count',sparkle)/8.,
            width=pair('strand_width',sparkle),light=pair('strand_light',sparkle),
            beads=pair('strand_beads',sparkle),peel_time=pair('strand_peel',sparkle),
            halo=pair('strand_halo',sparkle),glow=pair('strand_glow',sparkle),admission_softness=.15,
            pulse_growth=pair('strand_pulse_growth',sparkle),pulse_glow=pair('strand_pulse_glow',sparkle))
    direction=float(getattr(snapshot,'direction',self.base.flow.direction))
    flow=self.base.flow if direction==self.base.flow.direction else replace(self.base.flow,direction=direction)
    return replace(self.base,flow=flow,material=RibbonMaterial(**material),fog=fog,floor=floor,
        sparks=sparks,strays=strays,
        bloom=pair('bloom',passage),exposure=float(read('exposure')))
