"""C-primary elastic ribbon with A rolling twist and independently integrated axial roll.

The caller supplies logical dt, already-admitted source evidence and configuration. One retained ring records
head history; one vectorized pure projection publishes the complete body for every scene consumer. No Qt/GL/clock.
"""
from __future__ import annotations
import colorsys
import math
from dataclasses import dataclass, replace
from collections.abc import Mapping
import numpy as np
from core.ribbon_packet import KNOT_ROWS, RibbonPacket
from core.ribbon_ring import RibbonRing
from core.waveform_ribbon_authoring import TARGETS, route
from core.waveform_ribbon_scene import Recipe
from core.ribbon_bursts import RibbonAccentControls, RibbonBursts
from core.ribbon_strand_cohorts import RibbonStrandControls,RibbonStrandCohorts


def unit(value):
    return max(0., min(1., float(value)))


def follower(value, target, dt, attack, release):
    tau = attack if target > value else release
    return target + (value-target)*math.exp(-dt/max(tau,1e-5))


def elastic(position, velocity, target, dt, frequency, damping):
    """Exact underdamped step for a constant target; no Euler instability or render-rate solver."""
    omega = 2*math.pi*frequency
    wd = omega*math.sqrt(1.-damping*damping)
    decay = math.exp(-damping*omega*dt)
    sine, cosine = math.sin(wd*dt), math.cos(wd*dt)
    offset = position-target
    x = target+decay*(offset*cosine+(velocity+damping*omega*offset)*sine/wd)
    v = decay*(velocity*cosine-(omega*omega*offset+damping*omega*velocity)*sine/wd)
    return x,v


def impulse_velocity(frequency, damping):
    """Velocity whose free underdamped response has unit peak displacement.

    The analytic unit-velocity peak is exp(-zeta*acos(zeta)/sqrt(1-zeta²))/omega.
    Frequency/damping therefore control timing without silently shrinking authored hit excursion.
    """
    root=math.sqrt(1.-damping*damping)
    return 2.*math.pi*frequency*math.exp(damping*math.acos(damping)/root)


def hue_mix(a,b,share):
    left,right = colorsys.rgb_to_hsv(*a),colorsys.rgb_to_hsv(*b)
    delta = (right[0]-left[0]+.5)%1.-.5
    return colorsys.hsv_to_rgb((left[0]+delta*share)%1.,left[1]+(right[1]-left[1])*share,
                               left[2]+(right[2]-left[2])*share)


@dataclass(frozen=True)
class HybridControls:
    scene: Recipe
    ranges: Mapping
    routing: Mapping
    cards: tuple
    count: int
    frequency: float
    damping: float
    impulse: float
    attack: float
    release: float
    rotation_enabled: bool
    rotation_attack: float
    rotation_release: float
    twist_speed: tuple
    colour_threshold: float
    accents: RibbonAccentControls | None = None
    idle_motion: float = .35
    strands: RibbonStrandControls | None = None


@dataclass(frozen=True)
class HybridSnapshot:
    packet: RibbonPacket
    time: float
    travel: float
    rotation_angle: float
    rotation_speed: float
    twist_phase: float
    drives: tuple
    realized: tuple
    ready: bool
    passage: float = 0.
    head_x: float = 0.
    particles: bytes = b''
    particle_origin: float = 0.
    particle_serial: int = 0
    strands: bytes = b''
    strand_origin: float = 0.


class WaveformDynamics:
    def __init__(self, controls: HybridControls):
        self.controls = controls
        self.ring = RibbonRing(3, colours=[(*c['quiet'][0],1.) for c in controls.cards],
                               edge_colours=[(*c['quiet'][1],1.) for c in controls.cards],period=.5)
        self.time = self.travel = self.angle = self.angular_speed = self.twist_phase = self._hit = 0.
        self.phase = controls.scene.flow.phase
        self.bands, self.power = (0.,0.,0.),0.
        self.passage = 0.
        self.spring = [[0.,0.,0.] for _ in range(3)]
        self.velocity = [[0.,0.,0.] for _ in range(3)]
        self.drive = {key:0. for key in TARGETS}
        self.count_share = [1. if index < controls.count else 0. for index in range(3)]
        self._primed = 0
        self._next_knot = 1./controls.scene.flow.knot_hz
        self._snapshot = None
        self._base_packet = self._base_array = None
        self._bursts = None
        self._strand_cohorts = None
        self._elastic_config = None
        self._elastic_frequencies = self._impulse_scales = ()

    @property
    def ready(self):
        return self._primed == self.ring.capacity

    def _append(self, when, distance, phase, bands, power, hit):
        c = self.controls
        positions,widths,twists,lights,tints,sparkle = [],[],[],[],[],[]
        for index,card in enumerate(c.cards):
            p = phase*card['rate']+card['phase']
            p += c.scene.flow.phase_swell*math.sin(.31*p+index*.6)
            y = card['height']*(1.+c.scene.flow.amplitude_swell*math.sin(.23*p+.4))*math.sin(.7*p)
            z = .65*(index-1)
            positions.append((distance,2.+y,z))
            widths.append(card['width'])
            twists.append(.6*math.sin(.3*p)+.7*math.sin(.48*p+index*1.3)+.3*math.sin(.87*p+.4))
            local = power if card['band']=='All' else bands[('Bass','Mids','Highs').index(card['band'])]
            threshold = c.colour_threshold
            hot = unit((local-threshold)/max(1e-5,1.-threshold))
            hot = hot*hot*(3.-2.*hot)*self.drive['colour']
            quiet = tuple((a+b)*.5 for a,b in zip(*card['quiet']))
            peak = tuple((a+b)*.5 for a,b in zip(*card['peak']))
            tints.append((*hue_mix(quiet,peak,hot),hot))
            lights.append(card['light']*(.6+.4*local+.5*hit))
            sparkle.append(unit(self._value('sparkle')*max(hit,.4*bands[2])))
        self.ring.append(when,positions,widths,twists,lights,sparkle=sparkle,tint=tints)

    def advance(self, dt, *, bands, intensity, presence, hit=0., hit_components=None, controls=None):
        if not math.isfinite(dt) or not 0. <= dt <= .1:
            raise ValueError('Ribbon logical dt must be finite in 0..0.1 seconds')
        if controls is not None:
            self.controls = controls
        c = self.controls
        if not 0.05 <= c.frequency <= 4. or not .1 <= c.damping <= .95:
            raise ValueError('Ribbon elastic frequency/damping is outside the stable authoring domain')
        if self._elastic_config != (c.frequency,c.damping):
            self._elastic_config=(c.frequency,c.damping)
            self._elastic_frequencies=tuple(c.frequency*share for share in (1.,1.75,2.75))
            self._impulse_scales=tuple(impulse_velocity(frequency,c.damping) for frequency in self._elastic_frequencies)
        if not self.ready:
            # A bounded activation preparation step, not replayed/catch-up audio. Remain at the initial state until
            # the idle history is complete; prepared reveal cannot expose provisional head/tail segments.
            stop = min(self.ring.capacity,self._primed+4)
            for index in range(self._primed,stop):
                when = (index-(self.ring.capacity-1))/c.scene.flow.knot_hz
                self._append(when,c.scene.flow.speed*when,c.scene.flow.phase+2*math.pi*c.scene.flow.head_hz*when,
                             (0.,0.,0.),0.,0.)
            self._primed = stop
            self._snapshot = None
            return self.snapshot()
        bands = tuple(unit(v)*unit(presence) for v in bands)
        power = unit(intensity)*unit(presence)
        self.bands, self.power = bands,power
        self.passage = follower(self.passage,power,dt,c.attack,c.release)
        # Event strength already has its own acoustic support at admission. Passage weight must not attenuate
        # an admitted kick a second time; near-silence still forbids new input.
        hit = unit(hit)*unit(presence)
        impulses=(hit,hit,hit) if hit_components is None else tuple(unit(value)*unit(presence) for value in hit_components)
        if len(impulses)!=3:raise ValueError('Waveform impulse needs bend, torsion and depth components')
        self._hit = max(hit,self._hit*math.exp(-dt/.12))
        self.time += dt
        self.travel += c.scene.flow.speed*dt
        self.phase += 2*math.pi*c.scene.flow.head_hz*dt
        sources = (*bands,power,self._hit,.5+.5*math.sin(self.phase))
        for key in TARGETS:
            target = route(c.routing[key],sources,passage=self.passage)
            self.drive[key] = follower(self.drive[key],target,dt,c.attack,c.release)
        for owner,card in enumerate(c.cards):
            support = 1. if card['band']=='All' else bands[('Bass','Mids','Highs').index(card['band'])]
            for index,target in enumerate((self.drive['bend'],self.drive['torsion'],self.drive['depth'])):
                self.velocity[owner][index] += support*impulses[index]*c.impulse*self._impulse_scales[index]
                self.spring[owner][index],self.velocity[owner][index] = elastic(
                    self.spring[owner][index],self.velocity[owner][index],target*support,dt,
                    self._elastic_frequencies[index],c.damping)
        target_speed = self._value('rotation') if c.rotation_enabled else 0.
        self.angular_speed = follower(self.angular_speed,target_speed,dt,c.rotation_attack,c.rotation_release)
        self.angle = math.remainder(self.angle+math.radians(self.angular_speed)*dt,2*math.pi)
        low,high = c.twist_speed
        self.twist_phase = math.remainder(self.twist_phase+(low+(high-low)*self.drive['twist'])*dt,2*math.pi)
        for index in range(3):
            self.count_share[index] = follower(self.count_share[index],float(index<c.count),dt,.5,.5)
            if abs(self.count_share[index]-float(index<c.count)) < 1e-4:
                self.count_share[index] = float(index<c.count)
        if self.ready:
            # The bounded logical step crosses at most one six-Hz knot; render delivery never owns admission.
            if self._next_knot <= self.time+1e-9:
                when = self._next_knot
                lag = self.time-when
                self._append(when,self.travel-c.scene.flow.speed*lag,
                             self.phase-2*math.pi*c.scene.flow.head_hz*lag,bands,power,self._hit)
                self._next_knot += 1./c.scene.flow.knot_hz
        self._snapshot = None
        snapshot=self.snapshot()
        if c.accents is None:
            self._bursts=None
        elif hit>=.08 or self._bursts is not None:
            if self._bursts is None:self._bursts=RibbonBursts()
            self._bursts.admit(snapshot,c.accents,hit)
            self._snapshot=replace(snapshot,particles=self._bursts.visible_payload(snapshot.time),particle_origin=self._bursts.origin,
                                   particle_serial=self._bursts.serial)
        if c.strands is None:
            self._strand_cohorts=None
        else:
            if self._strand_cohorts is None:self._strand_cohorts=RibbonStrandCohorts(snapshot.packet.instances)
            payload=self._strand_cohorts.update(snapshot,c.strands,hit,history=self._base_packet,knot_hz=c.scene.flow.knot_hz)
            self._snapshot=replace(self._snapshot,strands=payload,strand_origin=self._strand_cohorts.origin)
        return self._snapshot

    def _value(self,key):
        low,high = self.controls.ranges[key]
        return low+(high-low)*unit(self.drive[key])

    def snapshot(self):
        if self._snapshot is not None:
            return self._snapshot
        if not self.ready:
            self._snapshot = HybridSnapshot(RibbonPacket(b'',0,0),0.,0.,0.,0.,0.,(),(),False)
            return self._snapshot
        raw = self.ring.packet()
        if raw is not self._base_packet:
            base=np.frombuffer(raw.payload,np.float32).reshape(3,-1,4)
            # Fixed-x cloth has no transported-frame breaks. Check once per changed history packet (6 Hz),
            # before publication to the GPU reducer, rather than silently clearing a corridor across a gap.
            for path in base:
                count,start,capacity=int(path[0,0]),int(path[1,1]),int(path[1,2])
                knots=path[4:].reshape(-1,KNOT_ROWS,4)[(start+np.arange(count))%capacity]
                if count<4 or not (knots[:,1,2]>.5).all() or (knots[1:,1,3]>.5).any() or not (np.diff(knots[:,0,0])>0).all():
                    raise ValueError('Waveform cloth history must be one valid monotone axial run')
            self._base_packet,self._base_array=raw,base
        data = self._base_array.copy()
        rows = data[:,4::KNOT_ROWS]
        x = rows[:,:,0]+raw.world_origin[0]+self.controls.scene.flow.head_x-self.travel
        owner = np.arange(3)[:,None]
        b,m,h = np.tanh(self.spring).T[:,:,None]
        values = {key:self._value(key) for key in TARGETS}
        carrier = rows[:,:,1]+raw.world_origin[1]-2.
        scale = 1.+values['stretch']
        y = carrier*values['height']+values['lift']+scale*values['bend']*(.8*b*np.sin(.7*x+owner*.7)
            +.3*m*np.sin(1.5*x+owner)+.08*h*np.sin(2.6*x-owner))
        z = (rows[:,:,2]+raw.world_origin[2])*values['spread']+.4*values['depth']*m*np.cos(.65*x+owner)
        idle=self.controls.idle_motion*(1.-self.passage)
        y+=idle*.08*np.sin(.45*self.time+.6*x+owner)
        z+=idle*.05*np.cos(.33*self.time+.4*x-owner)
        # One common smooth bounding domain prevents floor-crossing/clamp kinks at extreme editor values.
        y = 2.5*np.tanh(y/2.5)
        z = 2.5*np.tanh(z/2.5)
        cosine,sine = math.cos(self.angle),math.sin(self.angle)
        rows[:,:,1],rows[:,:,2] = cosine*y-sine*z,sine*y+cosine*z
        rows[:,:,3] = 2.*np.tanh(rows[:,:,3]*values['width']/2.)
        origin_twist = (data[:,1,0,None]+math.pi)%(2*math.pi)-math.pi
        twist = data[:,5::KNOT_ROWS,1]+origin_twist
        twist = twist*values['twist']+values['torsion']*(1.6*m*np.sin(.9*x+owner)+.4*h*np.sin(1.6*x-owner))
        data[:,5::KNOT_ROWS,1] = twist+self.twist_phase+self.angle+idle*.18*np.sin(.28*self.time+.3*x+owner)
        data[:,1,0] = 0.
        # Strong local musical regions change colour immediately, even before new head history enters view.
        # The crest mask is carried by immutable carrier geometry, so coloured regions travel with the waveform.
        for index,card in enumerate(self.controls.cards):
            local = max(self.power,*self.bands) if card['band']=='All' else self.bands[('Bass','Mids','Highs').index(card['band'])]
            crest = np.clip(np.abs(carrier[index])/max(card['height'],1e-5),0.,1.)
            # Existing visible rim slots respond immediately; this eased source creates no simulation in the draw.
            data[index,6::KNOT_ROWS,3] = np.maximum(data[index,6::KNOT_ROWS,3],
                values['sparkle']*max(self._hit,.4*self.bands[2])*crest)
            data[index,7::KNOT_ROWS,3] *= 1.+2.2*self._hit*(.25+.75*crest)
            power = local*(.25+.75*crest)
            threshold = self.controls.colour_threshold
            share = np.clip((power-threshold)/max(1e-5,1.-threshold),0.,1.)
            share = share*share*(3.-2.*share)*values['colour']
            tint = data[index,8::KNOT_ROWS]
            share = np.maximum(share,tint[:,3])
            quiet = tuple((a+b)*.5 for a,b in zip(*card['quiet']))
            peak = tuple((a+b)*.5 for a,b in zip(*card['peak']))
            a,b = colorsys.rgb_to_hsv(*quiet),colorsys.rgb_to_hsv(*peak)
            hue = (a[0]+((b[0]-a[0]+.5)%1.-.5)*share)%1.
            saturation = a[1]+(b[1]-a[1])*share
            value = a[2]+(b[2]-a[2])*share
            k = (np.array((5.,3.,1.))[None,:]+hue[:,None]*6.)%6.
            tint[:,:3] = value[:,None]*(1.-saturation[:,None]*np.clip(np.minimum(k,4.-k),0.,1.))
            alpha = np.clip(share/.1,0.,1.)
            tint[:,3] = alpha*alpha*(3.-2.*alpha)
        for index,share in enumerate(self.count_share):
            data[index,2,:3] = self.controls.cards[index]['quiet'][0]
            data[index,3,:3] = self.controls.cards[index]['quiet'][1]
            rows[index,:,1:3] *= share
            rows[index,:,3] = np.maximum(1e-5,rows[index,:,3]*share)
            data[index,2:4,3] *= share
            data[index,7::KNOT_ROWS,3] *= share
            data[index,6::KNOT_ROWS,3] *= share
        packet = RibbonPacket(data.tobytes(),raw.instances,raw.vertices,(raw.world_origin[0],2.,0.),raw.coordinate_origin)
        self._snapshot = HybridSnapshot(packet,self.time,self.travel,self.angle,self.angular_speed,self.twist_phase,
            tuple(self.drive.items()),tuple(values.items()),self.ready,passage=self.passage,
            head_x=self.controls.scene.flow.head_x)
        return self._snapshot
