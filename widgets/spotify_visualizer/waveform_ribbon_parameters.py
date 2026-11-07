"""Compile canonical mode settings once; resolve ranges from the published logical drives."""
from __future__ import annotations
from dataclasses import fields, is_dataclass, replace
from types import MappingProxyType
from collections.abc import Mapping
from core.ribbon_style import RibbonMaterial, RibbonSparks, RibbonStrays
from core.waveform_ribbon_scene import Recipe, Flow
from core.waveform_ribbon_dynamics import HybridControls, PulseControls
from core.waveform_ribbon_authoring import TARGETS, admit_routing, admit_ribbons, admit_palette
from core.ribbon_bursts import RibbonAccentControls
from core.ribbon_strand_cohorts import RibbonStrandControls

PREFIX='waveform_ribbon_'


def detached(value):
    if is_dataclass(value):
        return type(value)(**{field.name:detached(getattr(value,field.name)) for field in fields(value)})
    if isinstance(value,Mapping):return MappingProxyType({key:detached(item) for key,item in value.items()})
    if isinstance(value,(list,tuple)):return tuple(detached(item) for item in value)
    return value


class CompiledWaveformSettings:
    """Configuration-owned bundle. No Settings/widget reference escapes into a mode frame."""
    def __init__(self,parameters):
        self.values=detached(dict(parameters))
        p=self.values
        def read(key):return p[PREFIX+key]
        cards=detached(admit_ribbons(read('ribbons')))
        routing=detached(admit_routing(read('routing')))
        palette=detached(admit_palette(read('palette')))
        # Unexposed values are primitive/world policy, not guessed missing product settings.
        flow=Flow(speed=float(read('flow_speed')),head_hz=float(read('wave_rate')),
                  phase_swell=float(read('wave_swell')),amplitude_swell=float(read('height_swell')),
                  fade_in=.1,fade_out=.5,direction=-1. if read('travel_direction')=='Left To Right' else 1.)
        self.base=detached(Recipe(flow=flow,palette=palette,
            ribbon_colours={'low':tuple(card['quiet'] for card in cards),'high':tuple(card['peak'] for card in cards)},
            grade_share=(float(read('gradient_share')),float(read('mist_gradient_share'))),
            pulse_rim=float(read('pulse_rim'))))
        self.controls=HybridControls(self.base,MappingProxyType({key:tuple(read(key)) for key in TARGETS}),
            routing,cards,int(read('count')),float(read('elastic_frequency')),float(read('damping')),
            float(read('impulse')),float(read('attack')),float(read('release')),bool(read('rotation_enabled')),
            float(read('rotation_attack')),float(read('rotation_release')),tuple(read('twist_speed')),
            float(read('colour_threshold')),RibbonAccentControls(MappingProxyType({key:tuple(read(key))
                for key in ('spark_count','spark_lifetime','spark_drift','spark_rise','spark_size','spark_light','spark_white','spark_glow','spark_span')}))
                if read('sparks_enabled') else None,idle_motion=float(read('idle_motion')),
            strands=RibbonStrandControls(MappingProxyType({key:tuple(read(key)) for key in
                ('strand_count','strand_chance','strand_span','strand_length','strand_reach',
                 'strand_width','strand_light','strand_beads','strand_peel','strand_halo','strand_glow','strand_eol','strand_fade')})) if read('strands_enabled') else None,
            pulse=PulseControls(str(read('pulse_direction')),float(read('pulse_width')),float(read('pulse_speed')),
                                float(read('pulse_colour')),float(read('pulse_fade')),float(read('pulse_saturation')),
                                float(read('pulse_particles')),float(read('pulse_strands')),
                                mode=str(read('reaction_mode'))),
            height_mode=str(read('height_mode')),tilt_shift=bool(read('tilt_shift')),breathing=float(read('breathing')),
            adaptive_response=bool(read('adaptive_response')),kick_accent=float(read('kick_accent')))

    def _scene_plan(self):
        """What scene() reads from the immutable settings, resolved once per compiled configuration: each driven
        value's (low, high - low) and every static value, so a tick evaluates only low + span x drive (the same
        float operations the per-tick read did)."""
        plan=self.__dict__.get('_plan')
        if plan is not None:return plan
        p=self.values
        def read(key):return p[PREFIX+key]
        def span(key):
            low,high=read(key)
            return float(low),float(high)-float(low)
        material=tuple((field.name,span('material_'+field.name),field.name.startswith('glint'))
                       if PREFIX+'material_'+field.name in p else (field.name,None,getattr(self.base.material,field.name))
                       for field in fields(RibbonMaterial))
        fog=None
        if read('mist_enabled'):
            tier=str(read('quality'))
            fog=(tuple(span(key) for key in ('fog_density','fog_clearance','fog_height','fog_softness','fog_light',
                                             'fog_variation','fog_drift')),
                 {'Low':96,'Medium':128,'High':160}[tier],{'Low':32,'Medium':24,'High':16}[tier])
        colour=tuple(float(v)/255. for v in read('floor_tint')[:3])
        floor=(tuple(span(key) for key in ('floor_reflection','floor_brightness','floor_wetness','floor_streak',
                                           'floor_column')),
               tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in colour),
               dict(glow_limit=float(read('floor_glow_limit')),hue=float(read('floor_colour')),
                    hot=(float(read('floor_contrast')),*self.base.floor.hot[1:]),
                    light_reach=float(read('floor_light_reach')),light_far=float(read('floor_light_far')),
                    give=float(read('floor_give'))))
        sparks=tuple(span(key) for key in ('spark_size','spark_lifetime','spark_drift','spark_rise','spark_light',
                                           'spark_white')) if read('sparks_enabled') else None
        strays=tuple(span(key) for key in ('strand_length','strand_reach','strand_chance','strand_count',
            'strand_width','strand_light','strand_beads','strand_peel','strand_halo','strand_glow',
            'strand_pulse_growth','strand_pulse_glow')) if read('strands_enabled') else None
        plan=self.__dict__['_plan']=(material,fog,floor,sparks,strays,span('bloom'),float(read('exposure')))
        return plan

    def scene(self,snapshot):
        material_plan,fog_plan,floor_plan,sparks_plan,strays_plan,bloom,exposure=self._scene_plan()
        drives=dict(snapshot.drives) if snapshot.ready else {key:0. for key in TARGETS}
        realized=dict(snapshot.realized) if snapshot.ready else {key:self.controls.ranges[key][0] for key in TARGETS}
        def pair(span,drive):
            low,width=span
            return low+width*max(0.,min(1.,drive))
        passage=snapshot.passage;sparkle=drives['sparkle'];highlights=drives['highlights']
        material={name:(pair(span,highlights if glint else passage) if span is not None else glint)
                  for name,span,glint in material_plan}
        for key in ('strand_light','rim_light','fill_light','rim_glow_light'):
            material[key]*=realized['light']
        material['glint_density']*=.5+realized['highlights']
        material['glint_chance']*=min(1.,realized['highlights'])
        fog=None
        if fog_plan is not None:
            (density,clearance,height,softness,light,variation,drift),slices,cell=fog_plan
            fog=replace(self.base.fog,density=pair(density,passage),clearance=pair(clearance,passage),
                height=pair(height,passage),softness=pair(softness,passage),light=pair(light,passage),
                noise=pair(variation,passage),drift=pair(drift,passage),slices=slices,cell=cell)
        (reflection,brightness,wetness,streak,column),tint,static=floor_plan
        floor=replace(self.base.floor,reflection=pair(reflection,passage),
            albedo_gain=pair(brightness,passage),tint=tint,f0=pair(wetness,passage),
            streak=(pair(streak,passage),*self.base.floor.streak[1:]),
            column=(pair(column,passage),*self.base.floor.column[1:]),**static)
        sparks=None
        if sparks_plan is not None:
            size_span,lifetime,drift,rise,light,white=sparks_plan
            size=pair(size_span,sparkle)
            sparks=RibbonSparks(per_knot=16,lifetime=pair(lifetime,sparkle),
                drift=pair(drift,sparkle),rise=pair(rise,sparkle),smallest=min(1.2,size),
                largest=size,light=pair(light,sparkle),white=pair(white,sparkle))
        strays=None
        if strays_plan is not None:
            length,reach,chance,count,width,light,beads,peel,halo,glow,growth,pulse_glow=strays_plan
            strays=RibbonStrays(per_knot=8,length=pair(length,sparkle),reach=pair(reach,sparkle),
                chance=pair(chance,sparkle)*pair(count,sparkle)/8.,
                width=pair(width,sparkle),light=pair(light,sparkle),
                beads=pair(beads,sparkle),peel_time=pair(peel,sparkle),
                halo=pair(halo,sparkle),glow=pair(glow,sparkle),admission_softness=.15,
                pulse_growth=pair(growth,sparkle),pulse_glow=pair(pulse_glow,sparkle))
        # The PUBLISHED direction (the logical owner swaps it only while the ribbons are faded out), not the request.
        direction=float(getattr(snapshot,'direction',self.base.flow.direction))
        flow=self.base.flow if direction==self.base.flow.direction else replace(self.base.flow,direction=direction)
        return replace(self.base,flow=flow,material=RibbonMaterial(**material),fog=fog,floor=floor,
            sparks=sparks,strays=strays,
            bloom=pair(bloom,passage),exposure=exposure)
