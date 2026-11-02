"""Compile canonical mode settings once; resolve ranges from the published logical drives."""
from __future__ import annotations
from dataclasses import fields, is_dataclass, replace
from types import MappingProxyType
from collections.abc import Mapping
from core.ribbon_style import RibbonMaterial, RibbonSparks, RibbonStrays
from core.waveform_ribbon_scene import Recipe, Flow
from core.waveform_ribbon_dynamics import HybridControls
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
                  head_x=16.,fade_in=.1,fade_out=.5)
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
                 'strand_width','strand_light','strand_beads','strand_peel','strand_halo','strand_glow')})) if read('strands_enabled') else None)

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
        mist=dict(self.base.environment.mist)
        shape=mist['uMistShape']
        thickness=pair('floor_mist_thickness',passage) if read('floor_mist_enabled') else 0.
        mist['uMistShape']=(shape[0]/max(thickness,1e-5) if thickness else 0.,*shape[1:])
        fog=None
        if read('mist_enabled'):
            tier=str(read('quality'));scale={'Low':.33,'Medium':.5,'High':.7}[tier]
            original=self.base.fog
            fog=replace(original,density=pair('fog_density',passage),tube=pair('fog_clearance',passage),
                noise=pair('fog_billows',passage),rim=pair('fog_fringe',passage),
                crackle=(pair('fog_edge',passage),*original.crackle[1:]),
                fringe_smoothing=pair('fog_smoothing',passage),haze=pair('fog_haze',passage),
                sides=(pair('fog_sides',passage),pair('fog_sides',passage)+5.),march_scale=scale,
                steps={'Low':64,'Medium':96,'High':128}[tier])
        colour=tuple(float(v)/255. for v in read('floor_tint')[:3])
        tint=tuple(v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in colour)
        floor=replace(self.base.floor,reflection=pair('floor_reflection',passage),
            albedo_gain=pair('floor_brightness',passage),tint=tint,f0=pair('floor_wetness',passage),
            streak=(pair('floor_streak',passage),*self.base.floor.streak[1:]),
            column=(pair('floor_column',passage),*self.base.floor.column[1:]),
            mist_reflection=pair('floor_mist_reflection',passage))
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
        return replace(self.base,material=RibbonMaterial(**material),fog=fog,floor=floor,
            environment=replace(self.base.environment,mist=detached(mist)),sparks=sparks,strays=strays,
            bloom=pair('bloom',passage),exposure=float(read('exposure')))
