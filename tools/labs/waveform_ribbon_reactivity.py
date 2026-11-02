"""WR-07 lab-only deterministic sources and incremental head dynamics. No GL, audio analysis or scheduler.

All candidates sample bounded head state into the existing immutable RibbonRing. Explicit fixture time drives a
fixed integration lattice, independent of render delivery. The comparison runner supplies the admitted look/flow;
this module is not a production mode, Settings schema or preset/default owner.
"""
from __future__ import annotations

from dataclasses import dataclass
import colorsys
import math
from time import perf_counter_ns

import numpy as np
from core.ribbon_packet import KNOT_ROWS,RibbonPacket
from core.ribbon_ring import RibbonRing

CANDIDATES = ('A', 'B', 'C', 'D')
EVENTS = ((1.25, 'bass', .5), (1.9, 'bass', .9), (5.1, 'onset', .35),
          (5.7, 'onset', .65), (6.3, 'onset', 1.), (7.2, 'onset', .8))
INTEGRATION_HZ = 120
PRE_ROLL = 42.5


def envelope(a: float, b: float, t: float) -> float:
    return math.sin(math.pi*(t-a)/(b-a))**2 if a < t < b else 0.


@dataclass(frozen=True)
class Signal:
    bass: float = 0.
    mids: float = 0.
    highs: float = 0.
    loudness: float = 0.
    detail: float = 0.
    rms: float = 0.


def signal(t: float, fixture: str = 'main') -> Signal:
    if fixture == 'detail':
        value=.8*envelope(1.,5.,t)
        return Signal(highs=value,loudness=.6,detail=value*math.sin(2*math.pi*1.5*t))
    if fixture in ('bass', 'mids', 'highs', 'band_baseline'):
        value = .8*envelope(1., 5., t)
        return Signal(**({fixture: value} if fixture != 'band_baseline' else {}), loudness=.6)
    if fixture == 'loudness':
        return Signal(loudness=.8*envelope(1., 5., t))
    if fixture in ('idle', 'event'):
        return Signal()
    if fixture != 'main':
        raise ValueError(f'Unknown synthetic fixture: {fixture}')
    if 1. <= t < 2.5:
        value = .9*envelope(1., 2.5, t)
        return Signal(bass=value, loudness=value)
    if 2.5 <= t < 4.:
        value = .8*envelope(2.5, 4., t)*(.75+.25*math.sin(2*math.pi*(t-2.5)))
        return Signal(mids=value, loudness=value)
    if 4. <= t < 5.:
        value = .8*envelope(4., 5., t)
        return Signal(highs=value, loudness=value, detail=value*math.sin(2*math.pi*1.5*t))
    if 6.5 <= t < 8.:
        return Signal(.8, .65, .5, 1., .5*math.sin(2*math.pi*1.5*t))
    return Signal()


def clamp(value: float) -> float:
    return min(max(value, 0.), 1.)


def flowing_colour(quiet,hot,amount):
    """Keep saturation while head-written colour changes travel; RGB cyan/orange blends went grey."""
    a,b=colorsys.rgb_to_hsv(*quiet),colorsys.rgb_to_hsv(*hot)
    delta=(b[0]-a[0]+.5)%1.-.5
    return colorsys.hsv_to_rgb((a[0]+delta*amount)%1.,a[1]+(b[1]-a[1])*amount,a[2]+(b[2]-a[2])*amount)


@dataclass(frozen=True)
class HistorySnapshot:
    value: RibbonPacket
    capacity: int

    def packet(self):
        return self.value


class HeadHistory:
    """One retained lab producer. `advance` owns state; snapshots/renders are read-only consumers."""

    def __init__(self, candidate, recipe, *, fixture='main', trace=False, input_source=None, accents=False,
                 body_envelope=False):
        if candidate not in CANDIDATES:
            raise ValueError('Unknown core-reactivity candidate')
        self.candidate, self.fixture = candidate, fixture
        self.input_source, self.accents = input_source, accents
        self.body_envelope=body_envelope
        self.body_level=0.;self.fast_hit=0.
        self.slow_passage=[0.,0.]
        self.roll_phase=0.
        self.travel_packets=[]
        self.last_travel_packet=-float('inf')
        self.rms_mean=0.;self.wave_detail=0.
        self.appearance = dict(bass=0.,mids=0.,highs=0.,loudness=0.,hit=0.)
        self.flow, self.shaping = recipe.flow, recipe.shaping
        knot_steps = INTEGRATION_HZ/self.flow.knot_hz
        if knot_steps < 1 or not knot_steps.is_integer() or self.flow.shape_tau < .45:
            raise ValueError('Comparison needs an integral knot lattice and at least 0.45 s shape stages')
        self.knot_steps = int(knot_steps)
        self.dt = 1/INTEGRATION_HZ
        self.tick = -1
        self.seen_events = set()
        self.event_log = []
        self.packets = []
        self.spring = [0., 0., 0.]
        self.velocity = [0., 0., 0.]
        self.hit = 0.
        self.levels = None
        self.trace = [] if trace else None
        self.cost_ns = []
        self.append_ns = []
        self.last_targets = {}
        quiet = recipe.ribbon_colours['low']
        self.quiet_colours=[tuple((a+b)/2 for a,b in zip(centre,edge)) for centre,edge in quiet]
        self.loud_colours = ([tuple((a+b)/2 for a,b in zip(centre,edge))
                              for centre,edge in recipe.ribbon_colours['high']] if accents else [])
        self.ring = RibbonRing(len(self.shaping.characters),
                               colours=[(*a, 1.) for a, _ in quiet],
                               edge_colours=[(*b, 1.) for _, b in quiet], period=.5)
        self.records = [] if trace else None

    def advance(self, now: float):
        if not math.isfinite(now) or not 0 <= now <= 120.:
            raise ValueError('Explicit fixture time must be finite in 0..120 s')
        last = math.floor(now*INTEGRATION_HZ+1e-7)
        if last < self.tick:
            raise ValueError('Fixture time cannot run backwards')
        while self.tick < last:
            self.tick += 1
            started = perf_counter_ns()
            self._step(self.tick/INTEGRATION_HZ)
            if self.tick/INTEGRATION_HZ >= PRE_ROLL:
                self.cost_ns.append(perf_counter_ns()-started)
        return self.ring

    def snapshot(self, *, body_level=None):
        """Publish one pure body-envelope projection; admitted normalized knots stay byte-identical."""
        packet=self.ring.packet()
        if not self.body_envelope:
            return HistorySnapshot(packet,self.ring.capacity)
        level=self.body_level if body_level is None else float(body_level)
        if not math.isfinite(level) or not 0<=level<=1:
            raise ValueError('Body envelope must be finite in 0..1')
        def at(key):
            lo,hi=self.shaping.ranges[key]
            return lo+(hi-lo)*level
        data=np.frombuffer(packet.payload,np.float32).copy().reshape(packet.instances,-1,4)
        rows=data[:,4::KNOT_ROWS]
        q=data[:,5::KNOT_ROWS,0]+packet.coordinate_origin
        ribbon=np.arange(packet.instances)[:,None]
        swell=.5+.5*np.sin(2*math.pi*.3*q+ribbon*2.)
        characters=np.asarray(self.shaping.characters,float)
        amp,character_width,frequency,offset=characters[:,:4].T
        phase=2*math.pi*self.flow.head_hz*frequency[:,None]*q+offset[:,None]+self.flow.phase
        phase+=self.flow.phase_swell*np.sin(.31*phase+ribbon*.6)
        variation=1.+self.flow.amplitude_swell*np.sin(.23*phase+.4)
        k=ribbon-(packet.instances-1)/2
        now=self.tick/INTEGRATION_HZ
        x=rows[:,:,0]+packet.world_origin[0]+self.flow.head_x-self.flow.speed*now
        def ranged(key,value):
            lo,hi=self.shaping.ranges[key]
            return lo+(hi-lo)*clamp(value)
        if self.candidate=='A':
            # Direct band-to-body: flowing carrier, bass width/bend, visibly rolling mid-driven torsion.
            y=2.+at('lift')+(rows[:,:,1]+packet.world_origin[1]-2.)*at('amplitude')
            z=rows[:,:,2]+packet.world_origin[2]+.4*self.appearance['mids']*np.sin(.5*phase+self.roll_phase)
            width_drive=level if body_level is not None else self.appearance['bass']
            twist_drive=level if body_level is not None else self.appearance['mids']
            width=rows[:,:,3]*(ranged('width',width_drive)+at('width_swell')*swell)
            twist=ranged('twist',twist_drive)*(.7*np.sin(.48*phase+ribbon*1.3)
                    +.3*np.sin(.87*phase+.4))+self.roll_phase
        elif self.candidate=='B':
            # Individual bends/width bulges/twist packets travel across the visible hall. No shared whole-body pulse.
            y=2.+at('lift')+at('amplitude')*amp[:,None]*np.sin(.55*phase)+.25*k*np.cos(.2*phase)
            z=.65*k+.45*np.cos(.3*phase+ribbon)
            width=character_width[:,None]*(at('width')+at('width_swell')*swell)*(1.+.12*np.sin(phase))
            twist=.65*np.sin(.35*phase+ribbon)
            bend=np.zeros_like(x);bulge=np.zeros_like(x);torsion=np.zeros_like(x)
            for born,strength,kind in self.travel_packets:
                age=now-born
                centre=self.flow.head_x-self.flow.speed*age
                dx=(x-centre)/1.45
                fade=clamp((age-4.)/2.)
                fade=1.-fade*fade*(3.-2.*fade)
                kernel=np.exp(-2.*dx*dx)*strength*math.exp(-age/5.)*fade
                shape=kernel if kind=='bass' else dx*kernel*1.5
                bend+=.9*shape*(1.+.18*ribbon)
                bulge+=kernel
                torsion+=2.5*dx*kernel
                tone=np.array((1.,.14,.025) if kind=='bass' else (.7,.035,1.))
                share=np.clip(kernel*.9,0.,.9)
                tint=data[:,8::KNOT_ROWS]
                tint[:,:,:3]=tint[:,:,:3]*(1.-share[:,:,None])+tone*share[:,:,None]
                tint[:,:,3]=np.maximum(tint[:,:,3],share)
            y+=1.1*np.tanh(bend)
            width*=1.+.9*np.tanh(bulge)
            twist+=torsion
            data[:,7::KNOT_ROWS,3]*=1.+1.5*np.tanh(bulge)
        elif self.candidate=='C':
            # A damped modal body: low bending, lateral pull and torsion are independent elastic degrees of freedom.
            b,m,h=(float(np.tanh(value)) for value in self.spring)
            if body_level is not None:b,m,h=level,level,.5*level
            y=2.+self.shaping.ranges['lift'][0]+self.shaping.ranges['amplitude'][0]*amp[:,None]*np.sin(.7*phase)
            y+=.8*b*np.sin(.7*x+ribbon*.7)+.3*m*np.sin(1.5*x+ribbon)+.08*h*np.sin(2.6*x-ribbon)
            z=.65*k+.4*m*np.cos(.65*x+ribbon)
            width=character_width[:,None]*(ranged('width',max(b,0.))+.08*swell)*(1.+.12*np.sin(phase))
            twist=.6*np.sin(.3*phase)+1.6*m*np.sin(.9*x+ribbon)+.4*h*np.sin(1.6*x-ribbon)
        else:
            # Broad authored macro-flow with a captured PCM-envelope detail field, not a rescaled version of A.
            detail=rows[:,:,1]+packet.world_origin[1]-2.
            y=2.+at('lift')+at('amplitude')*amp[:,None]*variation*np.sin(.5*phase)+.10*detail
            z=.65*k+.65*np.cos(.24*phase+ribbon)+.06*detail
            width=character_width[:,None]*(at('width')+.1*swell)*(1.+.12*np.abs(detail))
            twist=at('twist')*.6*np.sin(.25*phase+ribbon)+.22*detail+self.roll_phase
        # One common bounded domain, not output normalization to make a candidate win.
        y=2.+2.5*np.tanh((y-2.)/2.5)
        z=2.5*np.tanh(z/2.5)
        width=2.*np.tanh(width/2.)
        rows[:,:,1]=y-2.;rows[:,:,2]=z;rows[:,:,3]=width
        data[:,5::KNOT_ROWS,1]=twist
        data[:,1,0]=0.
        world=(packet.world_origin[0],2.,0.)
        projected=RibbonPacket(data.tobytes(),packet.instances,packet.vertices,tuple(world),packet.coordinate_origin)
        return HistorySnapshot(projected,self.ring.capacity)

    def _step(self, now):
        t = now-PRE_ROLL
        source = self.input_source.sample(t) if self.input_source is not None else signal(t, self.fixture)
        events = []
        if self.input_source is not None or self.fixture in ('main', 'event'):
            events_program = (self.input_source.events if self.input_source is not None else
                              EVENTS if self.fixture == 'main' else ((1., 'onset', 1.),))
            for sequence, (when, kind, strength) in enumerate(events_program):
                if when <= t+1e-9 and sequence not in self.seen_events:
                    self.seen_events.add(sequence)
                    events.append((sequence, kind, strength))
                    self.event_log.append(dict(epoch=0, sequence=sequence, kind=kind, strength=strength, time=t))
                    self.packets.append((now, strength))
                    self.hit = max(self.hit, strength)
                    self.fast_hit=max(self.fast_hit,strength)
                    if now-self.last_travel_packet>=.8:
                        self.travel_packets.append((now,strength,kind))
                        self.last_travel_packet=now
        self.packets = [(born, strength) for born, strength in self.packets if now-born <= 2.4]
        self.travel_packets=[packet for packet in self.travel_packets if now-packet[0]<=6.]
        if len(self.travel_packets)>8:raise ValueError('Traveling-packet capacity exceeded')
        if len(self.packets) > 8:
            raise ValueError('Head packet cap exceeded')
        self.hit *= math.exp(-self.dt/.65)
        self.fast_hit*=math.exp(-self.dt/.12)
        target=clamp(source.loudness**1.3*(.12+.88*max(clamp(self.fast_hit/.6),source.bass**2)))
        slow_alpha=1-math.exp(-self.dt/.6)
        self.slow_passage[0]+=(source.loudness-self.slow_passage[0])*slow_alpha
        self.slow_passage[1]+=(self.slow_passage[0]-self.slow_passage[1])*slow_alpha
        if self.candidate=='A':
            tau=.045 if target>self.body_level else .22
            self.body_level+=(target-self.body_level)*(1-math.exp(-self.dt/tau))
        else:self.body_level=clamp(self.slow_passage[1]**1.3)
        self.roll_phase=(self.roll_phase+self.dt*((.05+2.*source.mids) if self.candidate=='A'
                         else (.02+.15*source.mids) if self.candidate=='D' else 0.))%(2*math.pi)
        self.rms_mean+=(source.rms-self.rms_mean)*(1-math.exp(-self.dt/.35))
        detail_target=math.tanh((source.rms-self.rms_mean)*6.)
        self.wave_detail+=(detail_target-self.wave_detail)*(1-math.exp(-self.dt/.12))
        for key,value in dict(bass=source.bass,mids=source.mids,highs=source.highs,
                              loudness=source.loudness,hit=self.fast_hit).items():
            tau=.045 if value>self.appearance[key] else .25
            self.appearance[key]+=(value-self.appearance[key])*(1-math.exp(-self.dt/tau))
        bass, mids, highs, loud = source.bass, source.mids, source.highs, source.loudness
        fine = source.detail
        if self.candidate == 'A':
            drive = dict(width=bass, amplitude=.7*bass+.3*loud, twist=mids, spread=.5*bass+.5*mids,
                         lift=.6*bass, deformation=.5*highs+.5*self.hit, width_swell=bass)
        elif self.candidate == 'B':
            packet = clamp(sum(strength*envelope(0., 2.4, now-born) for born, strength in self.packets))
            drive = dict(width=.35*bass+.65*packet, amplitude=.25*bass+.75*packet,
                         twist=.35*mids+.65*packet*mids, spread=.4*mids+.6*packet,
                         lift=.2*bass+.8*packet, deformation=.3*highs+.7*packet, width_swell=packet)
        elif self.candidate == 'C':
            for index, target in enumerate((bass, mids, highs)):
                impulse = sum(event[2] for event in events)*(2.2,4.,1.)[index]
                self.velocity[index] += impulse
                omega = (4.,7.,11.)[index]+2.*target
                self.velocity[index] += (omega*omega*(target-self.spring[index])
                                         -2*.65*omega*self.velocity[index])*self.dt
                self.spring[index] += self.velocity[index]*self.dt
                if not -1. <= self.spring[index] <= 2. or abs(self.velocity[index]) > 20.:
                    raise ValueError('Elastic head state escaped its admitted bound')
            b, m, h = map(clamp, self.spring)
            drive = dict(width=b, amplitude=.75*b+.25*loud, twist=m, spread=.4*b+.6*m,
                         lift=b, deformation=h, width_swell=b)
        else:
            drive = dict(width=.65*bass, amplitude=.35*bass+.3*loud, twist=.55*mids,
                         spread=.3*bass+.3*mids, lift=.3*bass, deformation=.25*highs+.15*self.hit,
                         width_swell=.4*bass)
        drive['detail'] = fine if self.candidate == 'D' else 0.
        alpha = 1-math.exp(-self.dt/self.flow.shape_tau)
        if self.levels is None:
            self.levels = {key: [value, value] for key, value in drive.items()}
        for key, value in drive.items():
            if key != 'detail':
                value = clamp(value)
            self.levels[key][0] += (value-self.levels[key][0])*alpha
            self.levels[key][1] += (self.levels[key][0]-self.levels[key][1])*alpha
        targets = {key: a+(b-a)*self.levels[key][1] for key, (a,b) in self.shaping.ranges.items()
                   if key in drive}
        self.last_targets = targets
        if self.trace is not None and self.tick % self.knot_steps == 0 and t >= 0:
            self.trace.append(dict(time=t, source=source.__dict__, targets=targets.copy(),
                                   body_level=self.body_level,
                                   roll_phase=self.roll_phase,travel_packet_count=len(self.travel_packets),
                                   waveform_rms_detail=self.wave_detail,
                                   events=events, event_count=len(self.seen_events),
                                   packet_count=len(self.packets), spring=self.spring.copy()))
        if self.tick % self.knot_steps:
            return
        flow = self.flow
        positions, widths, twists, light = [], [], [], []
        for r, (amplitude, width, frequency, offset, brightness) in enumerate(self.shaping.characters):
            k = r-(len(self.shaping.characters)-1)/2
            phase = 2*math.pi*flow.head_hz*frequency*now+offset+flow.phase
            phase += flow.phase_swell*math.sin(.31*phase+r*.6)
            swell = .5+.5*math.sin(2*math.pi*.3*now+r*2.)
            variation = 1.+flow.amplitude_swell*math.sin(.23*phase+.4)
            deformation = targets['deformation']*(.24*math.sin(2*phase+.7)+.18*math.sin(.61*phase+offset))
            # Fine sound detail is subordinate to the common macro silhouette and has the same two-stage filter.
            detail = .40*self.levels['detail'][1]
            y = 2.+targets['lift']+targets['amplitude']*amplitude*variation*(math.sin(phase)+deformation)+detail
            y += .5*k*targets['spread']*math.cos(.37*phase)
            z = .65*k+flow.depth_sway*math.cos(.55*phase+r)+.15*self.levels['twist'][1]*math.sin(phase)
            positions.append((flow.speed*now, y, z))
            widths.append(width*(targets['width']+targets['width_swell']*swell)*(1.+.2*math.sin(phase)))
            twists.append(targets['twist']*(.7*math.sin(.48*phase+r*1.3)+.3*math.sin(.87*phase+.4)))
            if self.body_envelope:
                # Unit carrier carries local musical character; the current logical range envelope owns full-body form.
                positions[-1]=(flow.speed*now,2.+(1.+.25*self.levels['amplitude'][1])*amplitude*variation
                               *(math.sin(phase)+deformation)+.4*k*math.cos(.37*phase)+detail,z)
                widths[-1]=width*(1.+.15*self.levels['width'][1])*(1.+.2*math.sin(phase))
                twists[-1]=(1.+.2*self.levels['twist'][1])*(.7*math.sin(.48*phase+r*1.3)+.3*math.sin(.87*phase+.4))
                if self.candidate=='D':positions[-1]=(flow.speed*now,2.+self.wave_detail,.65*k)
            light.append(brightness*(.6+.25*source.loudness+.2*self.fast_hit) if self.accents else brightness*.75)
        started = perf_counter_ns()
        sparkle=clamp(.1*source.loudness+.6*source.highs+.8*self.fast_hit) if self.accents else 0.
        colour_share=clamp(source.loudness*(.1+.9*clamp(self.appearance['hit']/.6)))
        tints=[(*flowing_colour(quiet,hot,colour_share),1.) for quiet,hot in
               zip(self.quiet_colours,self.loud_colours)] if self.accents else 0.
        self.ring.append(now, positions, widths, twists, light, sparkle=sparkle, tint=tints)
        if t >= 0:
            self.append_ns.append(perf_counter_ns()-started)
        if self.records is not None:
            self.records.append(dict(time=now, positions=positions, widths=widths, twists=twists))
