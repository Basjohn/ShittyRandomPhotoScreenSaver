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
from core.waveform_ribbon_authoring import TARGETS, route, RIBBON_CAPACITY
from core.waveform_ribbon_scene import Recipe
from core.ribbon_bursts import RibbonAccentControls, RibbonBursts
from core.ribbon_strand_cohorts import RibbonStrandControls,RibbonStrandCohorts


def unit(value):
    return max(0., min(1., float(value)))


# Fixed musical anchors (never learned from the current song). Pooled p05..p95 of the fixed-reference body lanes,
# published passage and weighted body energy over four recorded 50 s windows (ragdoll, human_heavy, nightsolong,
# anything_mixed; 5 Nov audit). Real music otherwise uses about a fifth of every authored quiet->peak range.
BAND_SPAN = ((.25, .85), (.10, .82), (.02, .80))
PASSAGE_SPAN = (.45, .80)
ENERGY_SPAN = (.25, .75)
ENERGY_WEIGHTS = (.5, .35, .15)
# Phrase-scale body energy: rises within a bar, settles over a phrase. Beats articulate through the band sources.
PHRASE_ATTACK, PHRASE_RELEASE = .35, 1.5
# Optional Dynamic Zoom (operator, 5 Nov): the view extent widens up to 20% quickly in heavy sustained passages and
# narrows up to 20% slowly in soft or idle ones. Sustain is the published level held over seconds, so single hits
# never pump the camera; the zoom itself is a smooth logical state, frozen while the user operates the camera.
ZOOM_SPAN = .2
ZOOM_SUSTAIN_ATTACK, ZOOM_SUSTAIN_RELEASE = 2.5, 4.
ZOOM_OUT_SECONDS, ZOOM_IN_SECONDS = 1.2, 7.

# Travelling energy pulse (operator, 5 Nov: "reactions should feel like water waves, always WITH the waveform").
# Music injects energy at an origin; the energy travels along the scene axis at its own speed, spreads gently and
# fades, and wherever it is it swells the waveform's OWN crests and troughs (and widens/brightens/recolours them).
# One bounded 1D field per travel direction on the sole logical clock; the projection only samples it.
PULSE_GRID = np.linspace(-48., 48., 385)
PULSE_DX = float(PULSE_GRID[1]-PULSE_GRID[0])
PULSE_DIRECTIONS = ('Head To Tail', 'Tail To Head', 'Centre Out')
PULSE_ORIGIN = 7.            # world x of the edge origins, inside the authored view so a hit is seen at once
PULSE_RISE = .09             # seconds: an injected hit swells smoothly instead of popping in one tick
PULSE_DIFFUSION = .35        # world units^2 per second: packets widen gently as they travel
PULSE_SATURATION = 1.2       # soft bound of the sampled swell
# Injection calibrated on recorded PCM (5 Nov probe): typed hits reach ~0.2-0.4, body-energy rises ~0.15-0.25
# for ~0.15 s on beats; these gains give a beat a swell near 1 at its origin and leave quiet passages nearly flat.
PULSE_HIT_GAIN, PULSE_RISE_GAIN, PULSE_RISE_FLOOR = 2., 45., .08


def pulse_sources(direction):
    if direction == 'Head To Tail':return ((PULSE_ORIGIN,-1.),)
    if direction == 'Tail To Head':return ((-PULSE_ORIGIN,1.),)
    if direction == 'Centre Out':return ((0.,-1.),(0.,1.))
    raise ValueError('Unknown waveform pulse direction: '+str(direction))


@dataclass(frozen=True)
class PulseControls:
    direction: str = 'Head To Tail'
    width: float = 3.5           # full width at half height, world units
    speed: float = 9.            # world units per second along the scene axis
    colour: float = .6           # share of the peak colour the pulse carries
    fade: float = 2.             # seconds for the travelling energy to fall to 1/e

    def __post_init__(self):
        pulse_sources(self.direction)
        if not (math.isfinite(self.width) and .5<=self.width<=24. and math.isfinite(self.speed) and 0.<=self.speed<=30.
                and math.isfinite(self.colour) and 0.<=self.colour<=1. and math.isfinite(self.fade) and .2<=self.fade<=20.):
            raise ValueError('Waveform pulse needs width 0.5..24, speed 0..30, colour 0..1 and fade 0.2..20')


def span(value, low, high):
    """Place a lane on its real-music span. Above 0.8 the approach to 1 is exponential and never flattens, so a hot
    passage keeps moving instead of pinning its drivers (the body lanes' own knee, beat_engine._lane)."""
    position = max(0., (float(value)-low)/(high-low))
    if position > .8:
        position = .8+.2*(1.-math.exp(-(position-.8)/.2))
    return position


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
    pulse: PulseControls = PulseControls()


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
    zoom: float = 1.


class WaveformDynamics:
    def __init__(self, controls: HybridControls):
        self.controls = controls
        self.ring = RibbonRing(RIBBON_CAPACITY, colours=[(*c['quiet'][0],1.) for c in controls.cards],
                               edge_colours=[(*c['quiet'][1],1.) for c in controls.cards],period=.5)
        self.time = self.travel = self.angle = self.angular_speed = self.twist_phase = self._hit = 0.
        self.phase = controls.scene.flow.phase
        self.bands, self.power = (0.,0.,0.),0.
        self.passage = self.phrase = 0.
        self.zoom, self._sustain = 1., 0.
        self._pulse = np.zeros((2,PULSE_GRID.size))  # travelling toward -x, toward +x
        self._pulse_pending = 0.
        self._flux_fast = self._flux_slow = 0.
        self._shape_input = np.zeros((2,5),np.float64)  # two stages: bass/mid/high, power, hit
        self.spring = [[0.,0.,0.] for _ in range(RIBBON_CAPACITY)]
        self.velocity = [[0.,0.,0.] for _ in range(RIBBON_CAPACITY)]
        self.drive = {key:0. for key in TARGETS}
        self.count_share = [1. if index < controls.count else 0. for index in range(RIBBON_CAPACITY)]
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

    def _append(self, when, distance, phase, bands, power, hit, shape=None):
        c = self.controls
        shape_bands,shape_power,shape_hit = (bands,power,hit) if shape is None else (shape[:3],shape[3],shape[4])
        positions,widths,twists,lights,tints,sparkle = [],[],[],[],[],[]
        for index,card in enumerate(c.cards):
            p = phase*card['rate']+card['phase']
            p += c.scene.flow.phase_swell*math.sin(.31*p+index*.6)
            local = power if card['band']=='All' else bands[('Bass','Mids','Highs').index(card['band'])]
            shape_local = shape_power if card['band']=='All' else shape_bands[('Bass','Mids','Highs').index(card['band'])]
            envelope=(.65+.5*shape_power+.25*shape_local)*(1.+c.scene.flow.amplitude_swell*math.sin(.23*p+.4))
            y = card['height']*envelope*math.sin(.7*p)
            # A spatial carrier must have depth before axial roll: rotating a planar wave made quarter-turns flat.
            z = .65*(index-1)+.85*card['height']*envelope*math.cos(.7*p)
            positions.append((distance,2.+y,z))
            widths.append(card['width'])
            twists.append(.35*math.sin(.25*p)+.25*math.sin(.36*p+index*1.3)+.05*math.sin(.57*p+.4)
                          +.35*shape_local*math.sin(.8*p+index)+.2*shape_hit*math.sin(p))
            threshold = c.colour_threshold
            hot = unit((local-threshold)/max(1e-5,1.-threshold))
            hot = hot*hot*(3.-2.*hot)*self.drive['colour']
            quiet = tuple((a+b)*.5 for a,b in zip(*card['quiet']))
            peak = tuple((a+b)*.5 for a,b in zip(*card['peak']))
            tints.append((*hue_mix(quiet,peak,hot),hot))
            lights.append(card['light']*(.6+.4*local+.5*hit))
            sparkle.append(unit(self._value('sparkle')*max(hit,.4*bands[2])))
        self.ring.append(when,positions,widths,twists,lights,sparkle=sparkle,tint=tints)

    def advance(self, dt, *, bands, intensity, presence, hit=0., hit_components=None, accent=None, controls=None,
                dynamic_zoom=False, zoom_hold=False):
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
        raw = tuple(unit(v)*unit(presence) for v in bands)
        # Calibrated sources: each fixed-scale lane spread over its real-music span, so authored quiet->peak ranges
        # are actually traversed. The published level places every range; it blends the slow fixed-scale passage
        # with phrase-scale body energy so a lift within a song is visible, not only a change of playback volume.
        bands = tuple(span(value,*limits) for value,limits in zip(raw,BAND_SPAN))
        energy = sum(weight*value for weight,value in zip(ENERGY_WEIGHTS,raw))
        self.phrase = follower(self.phrase,energy,dt,PHRASE_ATTACK,PHRASE_RELEASE)
        power = unit(.5*span(unit(intensity)*unit(presence),*PASSAGE_SPAN)+.5*span(self.phrase,*ENERGY_SPAN))
        self.bands, self.power = bands,power
        self.passage = follower(self.passage,power,dt,c.attack,c.release)
        # Event strength already has its own acoustic support at admission. Passage weight must not attenuate
        # an admitted kick a second time; near-silence still forbids new input.
        hit = unit(hit)*unit(presence)
        accent = hit if accent is None else unit(accent)*unit(presence)
        impulses=(hit,hit,hit) if hit_components is None else tuple(unit(value)*unit(presence) for value in hit_components)
        if len(impulses)!=3:raise ValueError('Waveform impulse needs bend, torsion and depth components')
        self._hit = max(hit,self._hit*math.exp(-dt/.12))
        # Only the travelling carrier needs broad, smooth audio history. The C impulses, light and accents below
        # retain their immediate input. Exact cascade step avoids writing six-Hz amplitude/twist dents into the cloth.
        shape_target=np.asarray((*bands,power,self._hit))
        shape_step=dt/max(c.scene.flow.shape_tau,1e-5)
        shape_decay=math.exp(-shape_step)
        old_first=self._shape_input[0].copy()
        self._shape_input[1]=shape_target+shape_decay*(self._shape_input[1]-shape_target+(old_first-shape_target)*shape_step)
        self._shape_input[0]=shape_target+(old_first-shape_target)*shape_decay
        self._advance_zoom(dt,bool(dynamic_zoom),bool(zoom_hold))
        self.time += dt
        self.travel += c.scene.flow.speed*dt
        self.phase += 2*math.pi*c.scene.flow.head_hz*dt
        sources = (*bands,power,self._hit,.5+.5*math.sin(self.phase))
        # Fast bands articulate inside the level; a quiet passage still shows its beats, only smaller.
        gate = .35+.65*self.passage
        energy_shaped = sum(weight*value for weight,value in zip(ENERGY_WEIGHTS,bands))
        for key in TARGETS:
            target = route(c.routing[key],sources,passage=gate)
            self.drive[key] = follower(self.drive[key],target,dt,c.attack,c.release)
        self._advance_pulse(dt,hit,energy_shaped)
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
        for index in range(RIBBON_CAPACITY):
            self.count_share[index] = follower(self.count_share[index],float(index<c.count),dt,.5,.5)
            if abs(self.count_share[index]-float(index<c.count)) < 1e-4:
                self.count_share[index] = float(index<c.count)
        if self.ready:
            # The bounded logical step crosses at most one six-Hz knot; render delivery never owns admission.
            if self._next_knot <= self.time+1e-9:
                when = self._next_knot
                lag = self.time-when
                self._append(when,self.travel-c.scene.flow.speed*lag,
                             self.phase-2*math.pi*c.scene.flow.head_hz*lag,bands,power,self._hit,self._shape_input[1])
                self._next_knot += 1./c.scene.flow.knot_hz
        self._snapshot = None
        snapshot=self.snapshot()
        if c.accents is None:
            self._bursts=None
        elif accent>=.08 or self._bursts is not None:
            if self._bursts is None:self._bursts=RibbonBursts()
            self._bursts.admit(snapshot,c.accents,accent)
            self._snapshot=replace(snapshot,particles=self._bursts.visible_payload(snapshot.time),particle_origin=self._bursts.origin,
                                   particle_serial=self._bursts.serial)
        if c.strands is None:
            self._strand_cohorts=None
        else:
            if self._strand_cohorts is None:self._strand_cohorts=RibbonStrandCohorts(snapshot.packet.instances)
            payload=self._strand_cohorts.update(snapshot,c.strands,accent,history=self._base_packet,knot_hz=c.scene.flow.knot_hz)
            self._snapshot=replace(self._snapshot,strands=payload,strand_origin=self._strand_cohorts.origin)
        return self._snapshot

    def _advance_pulse(self,dt,hit,energy):
        """Inject, carry, spread and fade the travelling energy. Silence injects nothing; energy already
        travelling finishes its journey and fades (never vanishes)."""
        p = self.controls.pulse
        # Energy enters only on beats: typed hits (consumed once upstream) and rises of body energy above its recent
        # level (beats the onset bus may miss). A steady baseline would merge successive swells into one bulge;
        # sustained loudness is already carried by the level and the Pulse Strength range.
        self._flux_fast = follower(self._flux_fast,energy,dt,.03,.15)
        self._flux_slow = follower(self._flux_slow,energy,dt,.35,.6)
        rise = max(0.,self._flux_fast-self._flux_slow-PULSE_RISE_FLOOR)
        self._pulse_pending += PULSE_HIT_GAIN*unit(hit)+PULSE_RISE_GAIN*rise*dt
        release = self._pulse_pending*(1.-math.exp(-dt/PULSE_RISE))
        self._pulse_pending -= release
        sigma = p.width/2.3548
        sources = pulse_sources(p.direction)
        shift = p.speed*dt
        blur = min(.24,PULSE_DIFFUSION*dt/(PULSE_DX*PULSE_DX))
        decay = math.exp(-dt/p.fade)
        for index,sign in enumerate((-1.,1.)):
            field = self._pulse[index]
            if shift:
                field[:] = np.interp(PULSE_GRID-sign*shift,PULSE_GRID,field,left=0.,right=0.)
            if blur:
                field[1:-1] += blur*(field[:-2]-2.*field[1:-1]+field[2:])
            field *= decay
            for origin,direction in sources:
                if direction==sign and release:
                    field += release/len(sources)*np.exp(-.5*((PULSE_GRID-origin)/sigma)**2)

    def pulse_at(self,x):
        """Soft-bounded travelling swell sampled at scene x (pure; no state change)."""
        value = np.interp(x,PULSE_GRID,self._pulse[0],left=0.,right=0.)+np.interp(x,PULSE_GRID,self._pulse[1],left=0.,right=0.)
        return PULSE_SATURATION*np.tanh(value/PULSE_SATURATION)

    def _advance_zoom(self,dt,enabled,hold):
        self._sustain = follower(self._sustain,self.passage,dt,ZOOM_SUSTAIN_ATTACK,ZOOM_SUSTAIN_RELEASE)
        if hold:
            return
        if enabled:
            share = unit((self._sustain-.25)/.5)
            target = 1.+ZOOM_SPAN*(2.*share*share*(3.-2.*share)-1.)
        else:
            target = 1.  # switching off eases back to the authored framing; it never jumps
        self.zoom = follower(self.zoom,target,dt,ZOOM_OUT_SECONDS,ZOOM_IN_SECONDS)

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
            base=np.frombuffer(raw.payload,np.float32).reshape(RIBBON_CAPACITY,-1,4)
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
        # Cloth coordinate: fixed to the travelling history, so musical bends are sweeps carried by the ribbon
        # rather than a stationary lump field the cloth slides through.
        u = rows[:,:,0]+raw.world_origin[0]
        x = u+self.controls.scene.flow.head_x-self.travel
        owner = np.arange(RIBBON_CAPACITY)[:,None]
        # Keep elastic excursions legible above ordinary sustained input; the old unit tanh compressed hits twice.
        b,m,h = (3.*np.tanh(np.asarray(self.spring)/3.)).T[:,:,None]
        values = {key:self._value(key) for key in TARGETS}
        carrier = rows[:,:,1]+raw.world_origin[1]-2.
        axial_scale=np.exp(.6*values['stretch']*np.tanh(np.asarray(self.spring)[:,0,None]))
        rows[:,:,0]=x*axial_scale-raw.world_origin[0]-self.controls.scene.flow.head_x+self.travel
        # The axial roll turns the carrier (its helix and the bundle's separation) like a skewer. Height scales
        # both transverse carrier components, so a turn changes the visible phase, never the visible amplitude.
        separation = .65*(owner-1.)
        depth_wave = rows[:,:,2]+raw.world_origin[2]-separation
        # The travelling pulse swells the carrier's own crests and troughs where it is: always WITH the shape.
        swell = self.pulse_at(x)
        gain = 1.+.4*values['bend']*swell
        cy = carrier*values['height']*gain
        cz = depth_wave*values['height']*gain+separation*values['spread']
        cosine,sine = math.cos(self.angle),math.sin(self.angle)
        y,z = cosine*cy-sine*cz,sine*cy+cosine*cz
        # Depth sway acts in world space after the roll and travels with the cloth. The former standing bend
        # (a fixed spatial sine the ribbon slid through) is replaced by the travelling pulse above.
        z = z+.4*values['depth']*m*np.cos(.65*u+owner)
        idle=self.controls.idle_motion*(1.-self.passage)
        y+=idle*.08*np.sin(.45*self.time+.6*u+owner)
        z+=idle*.05*np.cos(.33*self.time+.4*u-owner)
        # One common smooth bounding domain prevents floor-crossing/clamp kinks at extreme editor values. Peaks
        # are meant to rise high: the framing makes room for them, the body is never capped to fit a frame.
        rows[:,:,1] = 5.*np.tanh(y/5.)+values['lift']
        rows[:,:,2] = 5.*np.tanh(z/5.)
        rows[:,:,3] = 3.5*np.tanh(rows[:,:,3]*values['width']*(1.+.35*swell)/3.5)
        origin_twist = (data[:,1,0,None]+math.pi)%(2*math.pi)-math.pi
        twist = data[:,5::KNOT_ROWS,1]+origin_twist
        twist = twist*values['twist']+values['torsion']*(1.6*m*np.sin(.45*u+owner)+.12*h*np.sin(.7*u-owner))
        data[:,5::KNOT_ROWS,1] = twist+self.twist_phase+self.angle+idle*.18*np.sin(.28*self.time+.3*u+owner)
        data[:,1,0] = 0.
        # Strong local musical regions change colour immediately, even before new head history enters view.
        # The crest mask is carried by immutable carrier geometry, so coloured regions travel with the waveform.
        for index,card in enumerate(self.controls.cards):
            local = max(self.power,*self.bands) if card['band']=='All' else self.bands[('Bass','Mids','Highs').index(card['band'])]
            crest = np.clip(np.abs(carrier[index])/max(1.5*card['height'],1e-5),0.,1.)
            # Existing visible rim slots respond immediately; this eased source creates no simulation in the draw.
            data[index,6::KNOT_ROWS,3] = np.maximum(data[index,6::KNOT_ROWS,3],
                values['sparkle']*max(self._hit,.4*self.bands[2])*crest)
            data[index,7::KNOT_ROWS,3] *= (1.+2.2*self._hit*(.25+.75*crest))*(1.+.45*swell[index])
            power = local*(.25+.75*crest)
            threshold = self.controls.colour_threshold
            share = np.clip((power-threshold)/max(1e-5,1.-threshold),0.,1.)
            share = share*share*(3.-2.*share)*values['colour']
            tint = data[index,8::KNOT_ROWS]
            share = np.maximum(np.maximum(share,tint[:,3]),self.controls.pulse.colour*np.clip(swell[index],0.,1.))
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
            head_x=self.controls.scene.flow.head_x,zoom=self.zoom)
        return self._snapshot
