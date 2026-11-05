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
from core.ribbon_bursts import MAX_BURST, RibbonAccentControls, RibbonBursts
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
PULSE_ORIGIN = 3.5          # world x of the edge origins, well inside the authored view so a hit is seen at once
PULSE_RISE = .08             # seconds: a beat lands quickly (DevCurve: fast rise, gentle settle), never a one-tick pop
PULSE_DIFFUSION = .35        # world units^2 per second: packets widen gently as they travel
PULSE_SATURATION = 1.2       # soft bound of the sampled swell
# Surge along the curve (operator, 5 Nov): where a swell passes, each point moves along its OWN local direction,
# toward the swell's travel: up-left on a curve rising to the left, down-left on one falling, left on a crest.
PULSE_SURGE = .6             # world units of along-curve travel per unit of Pulse Strength x swell
# Injection calibrated on recorded PCM (5 Nov probe): typed hits reach ~0.2-0.4, body-energy rises ~0.15-0.25
# for ~0.15 s on beats; these gains give a beat a swell near 1 at its origin and leave quiet passages nearly flat.
PULSE_HIT_GAIN, PULSE_RISE_GAIN, PULSE_RISE_FLOOR = 2., 45., .14
# Swell-carried particles (operator, 5 Nov: the pulse should increase saturation, particle density and strands).
# Injected energy buys births once; they are released over the swell's first journey and placed on it.
PULSE_BIRTHS = 20.          # births per unit of injected energy at Pulse Particles 1 (a full beat injects 2)
PULSE_BIRTH_TAU = .8        # seconds over which a swell's births are released while it travels
PULSE_GREY = .12            # colours below this saturation are treated as neutral: the swell never invents a hue
PULSE_GLOW = 2.5           # light a full swell adds where it is (the narrow authored band: the eye tracks it)
# Legibility (operator, 5 Nov: "I can't really see the pulse"). On real music the travelling energy piles to 3-5
# raw near the origin, so a tanh(1.2) look was a flat plateau over half the view. The look keeps contrast over the
# whole real range (1-exp(-raw/APP_SCALE)) and is led by FRESH energy: a copy of the field that fades over
# FRESH_FADE marks the swells launched in the last moments, so each beat's band is brightest as it travels and the
# older pile settles to APP_BASE of that look. Geometry never uses this (it stays broad and bounded).
APP_SCALE, APP_BASE, FRESH_FADE = 1.5, .85, .7
# Twitch (operator, 5 Nov: "just twitching"): the rim light used to flash with the raw 120 ms hit decay, the
# strongest beat-rate flicker in the trace. It now swells like the pulse: quick rise, gentle settle.
HIT_GLOW, HIT_GLOW_RISE, HIT_GLOW_SETTLE = 3., .04, .65

# Flow rule (operator, 5 Nov): a swell may only deepen the curvature the waveform already has, never reverse it.
# For y = c(x)g(x): y'' = c''g + 2c'g' + cg''. The geometric gain g is therefore a separate, broad envelope:
# the authored-width field blurred to a full width of at least GEOM_WAVES carrier wavelengths (derived from flow
# speed / wave rate / card rate, never a constant), and then bounded at the owner so |g'|/g <= GEOM_SLOPE*k and
# |g''|/g <= GEOM_CURVE*k^2 (k = carrier wavenumber). At a crest the cg'' term then stays below 30% of c''g; near a
# carrier zero crossing the 2c'g' term can only move the waveform's OWN inflection by at most 2*GEOM_SLOPE/k
# (about 6% of a wavelength): it never adds an inflection, an inward dent or a flattened kink.
GEOM_WAVES = 1.5
GEOM_SLOPE, GEOM_CURVE = .2, .3
GEOM_MAX_WAVELENGTH = 48.   # a stationary carrier (rate 0) bounds the envelope by the field's own span
# The along-curve surge slides knots ALONG their own curve (exact resampling of the unsurged body), so it moves the
# cloth's material with the swell without changing the curve itself. Bounded compression and rate of change.
SURGE_MAX_COMPRESSION = .3  # knot spacing may shrink by at most 30% locally
SURGE_RATE = 1.             # swell units per second: the surge can never lurch on a beat's fast rise

# Selectable reaction modes (operator, 5 Nov). All share the injection and the couplings above.
REACTION_MODES = ('Travelling Pulse', 'Frozen Past', 'Whole Swell', 'Group Wave')
# Frozen Past: per-cell passage peak held on the cloth (the grid is advected with the history flow, so the memory
# travels with the cloth). A passage starts at a cell when the travelling swell there begins to rise above
# FROZEN_PRESENT (a new swell reaching it, even over an older swell's tail) and its peak is the highest value
# reached while it keeps rising. Memory rises toward a higher passage peak within FROZEN_RISE at any time; a lower
# peak waits until that crest has passed the cell and then smoothly replaces the memory within FROZEN_REPLACE.
# Where no swell is present, memory and peak decay over FROZEN_DECAY: held state persists in silence and fades,
# never vanishes. FROZEN_RISING is the relative hysteresis that tells a real rise from interpolation noise.
FROZEN_PRESENT, FROZEN_RISE, FROZEN_REPLACE, FROZEN_DECAY, FROZEN_RISING = .05, .06, .5, 45., .003
# Whole Swell: one global level (DevCurve). Rise = PULSE_RISE (80 ms); settle = Pulse Fade/4 within these bounds.
WHOLE_SETTLE = (.65, 1.5)
# Group Wave: each swell arrives as a SET. Its envelope spans GROUP_WAVES carrier wavelengths, so several consecutive
# crests lift together and the light covers the whole set; the crests rise more toward the set's leading edge (smooth
# tanh lead weight) and the cloth under it surges a little further along its own curve. A wider envelope has a
# gentler slope, so the flow rule holds with more margin; the shared SURGE_RATE bounds the surge's change. (5 Nov
# 8 s strips: a 1.5-wavelength group with a .5 lean was indistinguishable from Travelling Pulse.)
GROUP_WAVES, GROUP_LEAD, GROUP_SURGE = 3.5, .8, 1.4


def pulse_sources(direction):
    if direction == 'Head To Tail':return ((PULSE_ORIGIN,-1.),)
    if direction == 'Tail To Head':return ((-PULSE_ORIGIN,1.),)
    if direction == 'Centre Out':return ((0.,-1.),(0.,1.))
    raise ValueError('Unknown waveform pulse direction: '+str(direction))


@dataclass(frozen=True)
class PulseControls:
    direction: str = 'Head To Tail'
    width: float = 2.5           # full width at half height of the travelling light/colour band (geometry uses its own broad envelope)
    speed: float = 6.            # world units per second along the scene axis: successive beats stay separate bands
    colour: float = .6           # share of the peak colour the pulse carries
    fade: float = 4.             # seconds for the travelling energy to fall to 1/e
    saturation: float = 0.       # share of the remaining saturation a full swell adds (hue and value unchanged)
    particles: float = 0.        # swell-carried births and the lean of accent births toward the swell
    strands: float = 0.          # restrained lean/chance/glow of accent strands near the swell
    mode: str = 'Travelling Pulse'  # REACTION_MODES; Whole Swell ignores direction, width and speed

    def __post_init__(self):
        pulse_sources(self.direction)
        if self.mode not in REACTION_MODES:
            raise ValueError('Unknown waveform reaction mode: '+str(self.mode))
        if not (math.isfinite(self.width) and .5<=self.width<=24. and math.isfinite(self.speed) and 0.<=self.speed<=30.
                and math.isfinite(self.colour) and 0.<=self.colour<=1. and math.isfinite(self.fade) and .2<=self.fade<=20.):
            raise ValueError('Waveform pulse needs width 0.5..24, speed 0..30, colour 0..1 and fade 0.2..20')
        if not (math.isfinite(self.saturation) and 0.<=self.saturation<=1. and math.isfinite(self.particles)
                and 0.<=self.particles<=2. and math.isfinite(self.strands) and 0.<=self.strands<=1.):
            raise ValueError('Waveform pulse needs saturation 0..1, particles 0..2 and strands 0..1')


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


def carrier_wavelength(controls):
    """Longest local carrier wavelength (world units) of the active cards: y = sin(.7p), p advancing at
    rate*2pi*head_hz (slowed by up to .31*phase_swell), carried by the history at flow speed."""
    flow = controls.scene.flow
    rates = [abs(float(card['rate'])) for card in controls.cards[:max(1,controls.count)]]
    slowest = min(rates)*.7*flow.head_hz*(1.-.31*min(1.,abs(flow.phase_swell)))
    if slowest <= 0.:
        return GEOM_MAX_WAVELENGTH
    return min(GEOM_MAX_WAVELENGTH,flow.speed/slowest)


def soft(value):
    return PULSE_SATURATION*np.tanh(value/PULSE_SATURATION)


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
        self._glow = 0.  # swell-shaped light response to hits (rise HIT_GLOW_RISE, settle HIT_GLOW_SETTLE)
        self._pulse = np.zeros((2,PULSE_GRID.size))  # travelling toward -x, toward +x
        self._fresh = np.zeros((2,PULSE_GRID.size))  # the same transport with a short fade: recently launched swells
        self._pulse_pending = 0.
        self._held = np.zeros((4,PULSE_GRID.size))  # Frozen Past on the cloth: memory, peak, previous swell, rising
        self._whole = self._whole_fresh = 0.         # Whole Swell global raw level and its short-fade copy
        self._drift = np.zeros(PULSE_GRID.size)      # rate-limited signed surge field (swell units)
        self._level = np.zeros(PULSE_GRID.size)      # published appearance swell (authored width)
        self._focus = np.zeros(PULSE_GRID.size)      # where swell-carried particles/strands gather
        self._geom = np.zeros(PULSE_GRID.size)       # broad geometric swell (pre owner bound)
        self._kernel = (None,None)
        self._pulse_credit = self._pulse_births = 0.  # births bought by injected energy / released and due
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
        self._glow = follower(self._glow,self._hit,dt,HIT_GLOW_RISE,HIT_GLOW_SETTLE)
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
        released = self._advance_pulse(dt,hit,energy_shaped)
        self._advance_pulse_births(dt,released)
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
        elif accent>=.08 or self._pulse_births>=1. or self._bursts is not None:
            if self._bursts is None:self._bursts=RibbonBursts()
            self._bursts.admit(snapshot,c.accents,accent,swell=self.pulse_focus,density=c.pulse.particles,
                               extra=int(self._pulse_births))
            self._pulse_births -= self._bursts.consumed
            self._snapshot=replace(snapshot,particles=self._bursts.visible_payload(snapshot.time),particle_origin=self._bursts.origin,
                                   particle_serial=self._bursts.serial)
        if c.strands is None:
            self._strand_cohorts=None
        else:
            if self._strand_cohorts is None:self._strand_cohorts=RibbonStrandCohorts(snapshot.packet.instances)
            payload=self._strand_cohorts.update(snapshot,c.strands,accent,history=self._base_packet,knot_hz=c.scene.flow.knot_hz,
                                                swell=self.pulse_focus,gather=c.pulse.strands)
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
        decays = (math.exp(-dt/p.fade),math.exp(-dt/min(p.fade,FRESH_FADE)))
        travelling = p.mode!='Whole Swell'
        for fields,decay in zip((self._pulse,self._fresh),decays):
            for index,sign in enumerate((-1.,1.)):
                field = fields[index]
                if not field.any() and not (travelling and release):
                    continue
                if shift:
                    field[:] = np.interp(PULSE_GRID-sign*shift,PULSE_GRID,field,left=0.,right=0.)
                if blur:
                    field[1:-1] += blur*(field[:-2]-2.*field[1:-1]+field[2:])
                field *= decay
                for origin,direction in sources:
                    if travelling and direction==sign and release:
                        field += release/len(sources)*np.exp(-.5*((PULSE_GRID-origin)/sigma)**2)
                field[field<1e-9] = 0.  # after injection, so a zero-length step changes nothing
        # Whole Swell: nothing travels; one level rises with the shared release and settles gently.
        settle = min(WHOLE_SETTLE[1],max(WHOLE_SETTLE[0],.25*p.fade))
        self._whole = self._whole*math.exp(-dt/settle)+(0. if travelling else release)
        self._whole_fresh = self._whole_fresh*math.exp(-dt/min(settle,FRESH_FADE))+(0. if travelling else release)
        self._advance_frozen(dt,p.mode=='Frozen Past')
        self._publish_fields(dt)
        return release

    def _advance_frozen(self,dt,active):
        """Per-cell passage peak held on the cloth; bounded fixed grid advected with the history flow."""
        held,peak,previous,rising = self._held
        flow = self.controls.scene.flow.speed*dt
        if not active:
            if self._held.any():
                # Leaving the mode fades the memory instead of dropping it.
                held *= math.exp(-dt/FROZEN_REPLACE)
                held[held<1e-6] = 0.
                peak[:] = previous[:] = rising[:] = 0.
            return
        if flow:
            for row in self._held:
                row[:] = np.interp(PULSE_GRID+flow,PULSE_GRID,row,left=0.,right=0.)
        now = self._pulse[0]+self._pulse[1]
        present = now>FROZEN_PRESENT
        up_now = present & (now>previous*(1.+FROZEN_RISING)+1e-4)
        start = up_now & (rising<.5)
        peak[:] = np.where(start,now,np.where(up_now,np.maximum(peak,now),peak))
        rise = 1.-math.exp(-dt/FROZEN_RISE)
        settle = 1.-math.exp(-dt/FROZEN_REPLACE)
        held[:] = np.where(peak>held,held+(peak-held)*rise,np.where(up_now,held,held+(peak-held)*settle))
        fade = math.exp(-dt/FROZEN_DECAY)
        held[~present] *= fade
        peak[~present] *= fade
        previous[:] = now
        rising[:] = up_now

    def _blur_kernel(self,waves=GEOM_WAVES):
        """Gaussian that widens the authored-width field to the geometric envelope (>= ``waves`` wavelengths)."""
        sigma_w = self.controls.pulse.width/2.3548
        sigma_g = max(sigma_w,waves*carrier_wavelength(self.controls)/2.3548)
        extra = math.sqrt(max(0.,sigma_g*sigma_g-sigma_w*sigma_w))
        key = (round(extra,9),round(sigma_g/sigma_w,9))
        if self._kernel[0]!=key:
            if extra<PULSE_DX*.25:
                kernel = np.ones(1)
            else:
                taps = int(math.ceil(4.*extra/PULSE_DX))
                kernel = np.exp(-.5*(np.arange(-taps,taps+1)*PULSE_DX/extra)**2)
                kernel /= kernel.sum()
            # An isolated swell keeps its peak: the envelope gets broader, not weaker.
            self._kernel = (key,kernel*(sigma_g/sigma_w))
        return self._kernel[1],sigma_g

    def _publish_fields(self,dt):
        """Derive the published appearance level, particle focus, broad geometry and rate-limited surge fields."""
        p = self.controls.pulse
        kernel,sigma_g = self._blur_kernel(GROUP_WAVES if p.mode=='Group Wave' else GEOM_WAVES)
        def broad(field):
            if kernel.size==1:
                return field*kernel[0]
            offset = (kernel.size-1)//2
            return np.convolve(field,kernel)[offset:offset+field.size]
        travelling = self._pulse[0]+self._pulse[1]
        body = 1.-np.exp(-travelling/APP_SCALE)
        fresh = np.clip((self._fresh[0]+self._fresh[1])/(travelling+1e-9),0.,1.)
        look = body*(APP_BASE+(1.-APP_BASE)*fresh)
        drift_target = np.zeros(PULSE_GRID.size)
        if p.mode=='Whole Swell':
            # The same fresh-led look as a travelling band, applied to the whole body at once: a hit glows, a
            # sustained level settles to the base look instead of washing the whole waveform out.
            share = min(1.,self._whole_fresh/(self._whole+1e-9))
            self._level = np.full(PULSE_GRID.size,(1.-math.exp(-self._whole/APP_SCALE))*(APP_BASE+(1.-APP_BASE)*share))
            self._focus = self._level
            self._geom = np.full(PULSE_GRID.size,float(soft(self._whole)))
        elif p.mode=='Frozen Past':
            memory = np.maximum(travelling,self._held[0])
            # Held cloth keeps the settled look of its passage; the travelling band stays brighter over it.
            self._level = np.maximum(look,APP_BASE*(1.-np.exp(-self._held[0]/APP_SCALE)))
            self._focus = look
            self._geom = soft(broad(memory))
            drift_target = soft(broad(self._pulse[1]))-soft(broad(self._pulse[0]))
        elif p.mode=='Group Wave':
            # The light covers the set: the look spread over the group envelope (unit-sum, so it never brightens).
            self._level = np.minimum(1.,broad(look)*(p.width/2.3548)/sigma_g)
            self._focus = self._level
            total = np.zeros(PULSE_GRID.size)
            for index,sign in enumerate((-1.,1.)):
                wide = broad(self._pulse[index])
                lead = -sign*sigma_g*np.gradient(wide,PULSE_DX)/(wide+1e-6)
                weighted = wide*(1.+GROUP_LEAD*np.tanh(lead))
                total += weighted
                drift_target += sign*GROUP_SURGE*soft(weighted)
            self._geom = soft(total)
        else:
            self._level = look
            self._focus = look
            self._geom = soft(broad(travelling))
            drift_target = soft(broad(self._pulse[1]))-soft(broad(self._pulse[0]))
        step = SURGE_RATE*dt
        self._drift = self._drift+np.clip(drift_target-self._drift,-step,step)

    def _advance_pulse_births(self,dt,released):
        """Injected energy buys a bounded number of swell-carried births, released over the swell's journey and
        consumed once by burst admission. Silence buys none; without sparks or the control nothing is banked."""
        c = self.controls
        if c.accents is None or c.pulse.particles<=0.:
            self._pulse_credit = self._pulse_births = 0.
            return
        self._pulse_credit = min(4.*MAX_BURST,self._pulse_credit+PULSE_BIRTHS*c.pulse.particles*released)
        moved = self._pulse_credit*(1.-math.exp(-dt/PULSE_BIRTH_TAU))
        self._pulse_credit -= moved
        self._pulse_births = min(float(MAX_BURST),self._pulse_births+moved)

    def pulse_at(self,x):
        """Published appearance swell at scene x: the authored-width band (plus held memory in Frozen Past,
        the uniform level in Whole Swell). Pure; no state change."""
        return np.interp(x,PULSE_GRID,self._level)

    def pulse_focus(self,x):
        """Where swell-carried particles and strands gather (the travelling swell; uniform in Whole Swell)."""
        return np.interp(x,PULSE_GRID,self._focus)

    def pulse_drift(self,x):
        """Signed, rate-limited surge: positive where energy travels toward +x, negative toward -x (pure)."""
        return np.interp(x,PULSE_GRID,self._drift)

    def geometric_gain(self,strength):
        """Gain envelope on the pulse grid, bounded at the owner by the flow rule (see GEOM_SLOPE/GEOM_CURVE)."""
        swell = .7*strength*self._geom
        if not np.any(swell):
            return np.ones(PULSE_GRID.size)
        k = 2.*math.pi/carrier_wavelength(self.controls)
        def excess(share):
            g = 1.+share*swell
            first = np.gradient(g,PULSE_DX)
            second = np.gradient(first,PULSE_DX)
            return max(np.abs(first/g).max()/(GEOM_SLOPE*k),np.abs(second/g).max()/(GEOM_CURVE*k*k))
        share = 1.
        if excess(1.)>1.:
            low,high = 0.,1.
            for _ in range(20):
                share = .5*(low+high)
                low,high = (share,high) if excess(share)<=1. else (low,share)
            share = low
        return 1.+share*swell

    def _surge(self,data,x,y,z,amount):
        """Slide each knot ALONG its own curve by the signed swell: the body is resampled at the shifted positions
        (cubic Hermite through the unsurged knots), so the curve itself never changes, only its cloth moves."""
        drift = self.pulse_drift(x)*amount
        if not np.any(drift):
            return x,y,z
        x,y,z = x.copy(),y.copy(),z.copy()
        for index,path in enumerate(data):
            count,start,capacity = int(path[0,0]),int(path[1,1]),int(path[1,2])
            if count<4:
                continue
            order = (start+np.arange(count))%capacity
            xs,ds = x[index,order],drift[index,order].copy()
            if not np.any(ds):
                continue
            # The ends never slide: a smooth taper long enough to respect the compression bound.
            ramp = max(1e-6,np.abs(ds).max()/(.9*SURGE_MAX_COMPRESSION))
            edge = np.clip(np.minimum(xs-xs[0],xs[-1]-xs)/ramp,0.,1.)
            ds *= edge*edge*(3.-2.*edge)
            squeeze = np.diff(ds)/np.diff(xs)
            if squeeze.min() < -SURGE_MAX_COMPRESSION:
                ds *= SURGE_MAX_COMPRESSION/-squeeze.min()
            target = xs+ds
            cell = np.clip(np.searchsorted(xs,target)-1,0,count-2)
            h = xs[cell+1]-xs[cell]
            t = (target-xs[cell])/h
            h00,h10,h01,h11 = 2*t**3-3*t*t+1,t**3-2*t*t+t,-2*t**3+3*t*t,t**3-t*t
            for values in (y,z):
                vs = values[index,order]
                slope = np.gradient(vs,xs)
                values[index,order] = (h00*vs[cell]+h10*h*slope[cell]+h01*vs[cell+1]+h11*h*slope[cell+1])
            x[index,order] = target
        return x,y,z

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
        # No time-varying axial scaling: horizontal motion is only the steady flow (DevCurve's rule). The former
        # elastic stretch scaled x about the centre on every kick and read as sideways bursts (operator, 5 Nov).
        # The axial roll turns the carrier (its helix and the bundle's separation) like a skewer. Height scales
        # both transverse carrier components, so a turn changes the visible phase, never the visible amplitude.
        separation = .65*(owner-1.)
        depth_wave = rows[:,:,2]+raw.world_origin[2]-separation
        # The travelling pulse swells the carrier's own crests and troughs where it is: always WITH the shape.
        # Appearance follows the authored-width band (legible, travelling); geometry follows the broad bounded
        # envelope so whole waves swell together and the curvature keeps its own sign (flow rule).
        swell = self.pulse_at(x)
        # Beyond the field the published edge value continues (a Whole Swell never ends at the grid edge).
        broad = np.interp(x,PULSE_GRID,self.geometric_gain(values['bend']))
        geometric = np.interp(x,PULSE_GRID,self._geom)
        gain = broad
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
        x,y,z = self._surge(data,x,y,z,PULSE_SURGE*values['bend'])
        rows[:,:,0] = x-raw.world_origin[0]-self.controls.scene.flow.head_x+self.travel
        # One common smooth bounding domain prevents floor-crossing/clamp kinks at extreme editor values. Peaks
        # are meant to rise high: the framing makes room for them, the body is never capped to fit a frame.
        rows[:,:,1] = 5.*np.tanh(y/5.)+values['lift']
        rows[:,:,2] = 5.*np.tanh(z/5.)
        rows[:,:,3] = 3.5*np.tanh(rows[:,:,3]*values['width']*(1.+.35*geometric)/3.5)
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
            data[index,7::KNOT_ROWS,3] *= (1.+HIT_GLOW*self._glow*(.25+.75*crest))*(1.+PULSE_GLOW*swell[index])
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
            # The swell deepens colour where it is: saturation rises toward 1 (never toward white), hue and value
            # keep their own logic, and a neutral colour stays neutral rather than gaining an invented hue.
            vivid = self.controls.pulse.saturation*np.clip(swell[index],0.,1.)*np.clip(saturation/PULSE_GREY,0.,1.)
            saturation = saturation+(1.-saturation)*vivid
            share = np.maximum(share,vivid)
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
