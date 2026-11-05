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
            grade_share=(float(read('gradient_share')),float(read('mist_gradient_share')))))
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
            height_mode=str(read('height_mode')),tilt_shift=bool(read('tilt_shift')))

    def scene(self,snapshot):
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
        # The PUBLISHED direction (the logical owner swaps it only while the ribbons are faded out), not the request.
        direction=float(getattr(snapshot,'direction',self.base.flow.direction))
        flow=self.base.flow if direction==self.base.flow.direction else replace(self.base.flow,direction=direction)
        return replace(self.base,flow=flow,material=RibbonMaterial(**material),fog=fog,floor=floor,
            sparks=sparks,strays=strays,
            bloom=pair('bloom',passage),exposure=float(read('exposure')))
