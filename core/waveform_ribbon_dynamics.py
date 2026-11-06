"""Waveform ribbon body: a travelling energy pulse (four Reaction Modes) that swells the carrier's own crests and
troughs under the flow rule, with A's rolling twist and an independently integrated axial roll.

The caller supplies logical dt, already-admitted source evidence and configuration. One retained ring records
head history; one vectorized pure projection publishes the complete body for every scene consumer. No Qt/GL/clock.
"""
from __future__ import annotations
import colorsys
import functools
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
PULSE_ORIGIN = 44.          # world x of the edge origins: just beyond the view (~±30), so a swell slides in already formed (born at 3.5, mid-view, it popped into existence)
# Born where the camera sees it (Travelling Pulse, Head To Tail / Tail To Head; operator, 6 Nov). The capture supplies the
# scene-axis span the framed camera really shows (about +-16 at a 1282x1005 card: the edge-resize aperture times the
# long lens, not the +-30 PULSE_ORIGIN assumed). An edge swell is then born VIEW_MARGIN geometric-envelope sigmas beyond
# that edge (its tail there is a few percent, so it slides in already formed; never farther out than PULSE_ORIGIN) and
# ages only once seen: both fields keep their strength until they reach the edge (the fade ramps in over one envelope
# sigma), then fade over Pulse Fade / FRESH_FADE while they cross, as a Centre Out swell does from its birth. Born at
# 44 a swell reached a +-16 view ~2 s after its beat with 5% of its fresh strength. Centre Out (born in view) and the
# other modes (wider envelopes that already reach the view) are untouched; without a supplied span nothing changes.
VIEW_MARGIN = 2.5
# Pulse Rim reads the published field against one reference level (rendering/quick/scene3d/pulse_rim.REFERENCE), set
# where a swell carries HALF the injected energy, as each Centre Out swell does (pulse_sources splits a release between
# its sources). An edge swell carries all of it, and once seen at full strength its in-view field is twice Centre Out's
# (6 Nov, recorded continuous play at +-16: peak p50 .42 vs .21, median .19 vs .10), which lit the rims at their ceiling
# over 43% of the view. Such a swell publishes RIM_EDGE_SHARE of its level for the rim (peak .21, median .09: the same
# response as Centre Out's). Centre Out and every swell still born at PULSE_ORIGIN publish the level itself.
RIM_EDGE_SHARE = .5
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
# The travelling swell's geometry follows the fresh field (5 Nov: the long-fade field overlapped into a uniform inflation
# of the whole view, median/max .87); this gain gives a fresh beat the strength the pile used to have.
PULSE_FRESH_GAIN = 2.4
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
GEOM_WAVES = .8
GEOM_SLOPE, GEOM_CURVE = .2, .3
GEOM_SHARE_RISE = 1.5  # per second: the flow-rule share relaxes upward smoothly (never a whole-field pop)
GEOM_MAX_WAVELENGTH = 48.   # a stationary carrier (rate 0) bounds the envelope by the field's own span
# The along-curve surge slides knots ALONG their own curve (exact resampling of the unsurged body), so it moves the
# cloth's material with the swell without changing the curve itself. Bounded compression and rate of change.
SURGE_MAX_COMPRESSION = .3  # knot spacing may shrink by at most 30% locally
SURGE_EASE = .15            # seconds per easing stage of the surge (velocity-continuous sideways motion)
SURGE_TAPER, SURGE_BOUND_RISE = 20., 1.5  # fixed end-taper length (world units); compression bound relaxation per second
SURGE_RATE = 1.             # swell units per second: the surge can never lurch on a beat's fast rise

# Geometry drives (shape, sway, twist, lift, rotation) follow their routed bands through two cascaded followers with at
# least GEOMETRY_ATTACK each: a quick but velocity-continuous rise (~0.2 s to 90%) instead of a 45 ms snap. Light,
# colour, sparkle and highlights keep the authored attack: a flash of light is not a twitch of the body.
IMPULSE_SPREAD = .06  # seconds over which a hit's kick to the sway/torsion springs is delivered
SMOOTH_TARGETS = frozenset(('height','width','bend','torsion','twist','stretch','lift','spread','depth'))
GEOMETRY_ATTACK = .06
# The whole body's size (height, lift, width) follows the passage, not each beat (operator, 5 Nov: "no reactivity besides
# the twitch"; space-time maps showed the whole view pumping in unison on every beat, drowning the travelling pulse).
# Beats belong to the travelling pulse, which makes the biggest reaction where it is.
# Adaptive response gain (see advance): geometry drives use each song's own recent peak over the full
# authored Quiet->Peak ramp. Light, colour and sparkle (particles, strands) keep their calibrated mapping.
RESPONSE_REACH, RESPONSE_MEMORY, RESPONSE_PEAK_FLOOR, RESPONSE_TOP = .5, 30., .45, .85
RESPONSE_TARGETS = frozenset(('height','width','bend','torsion','twist','stretch','lift','spread','depth'))
GLOBAL_TARGETS = frozenset(('height','lift','width'))
GLOBAL_ATTACK = .35
# Breathing (operator, 5 Nov: soft passages "look sustained instead of feeling their big changes"). Two causes, measured
# on continuous play: Decay is the release of BOTH cascaded stages of every geometry drive, so the body let go of a swell
# over about twice the authored Decay and the dips between a soft passage's phrases filled in; and a soft passage's drives
# move little around their own level. Softness is how far the published passage sits below BREATHING_LOUD (0 at or above
# it), times Breathing. A soft passage then (1) releases faster, by up to BREATHING_REACH of Decay, and (2) widens each
# geometry drive's swings about its own phrase-scale mean (a BREATHING_BASE-second follower of the drive's target) by up
# to BREATHING_CONTRAST: it swells AND lets go without being lifted as a whole. Loud passages keep their authored Decay,
# their targets and their reach. Attack, both follower stages and the rate limits are unchanged (no twitch).
BREATHING_REACH, BREATHING_CONTRAST, BREATHING_LOUD, BREATHING_BASE = .75, 1.5, .8, 3.
# Breathing also keeps a quieter PASSAGE quiet (see advance). The gain memory is held only while the slow sustained
# level (the published passage held over seconds, ZOOM_SUSTAIN_ATTACK/RELEASE: it never dips between beats) sits
# clearly below the loud level the remembered peaks were set at: from HOLD_BELOW[0] of it (no hold) to HOLD_BELOW[1]
# (full hold), the memory relaxes over up to RESPONSE_MEMORY x (1 + Breathing x (RESPONSE_HOLD - 1)). That loud level
# rises with the sustained level at once and relaxes with the memory, so a song that stays softer is re-normalised
# over minutes. Sustained music, and Breathing 0, keep RESPONSE_MEMORY exactly.
RESPONSE_HOLD, HOLD_BELOW = 6., (.8, .7)
# Silence must not teach a running level (guide 2A). Breathing's phrase-scale mean learns at the rate of BREATHING_HEARD,
# which drops to 0 with the musical weight at once and returns over BREATHING_HEARD_RETURN seconds: through a break and
# the passage's own return (the shared passage level climbs back over about a second) the mean holds, so the music's
# return is not swelled against a mean that fell with the silence.
BREATHING_HEARD_RETURN = 1.5
# Fixed response (Adaptive Response off, operator 6 Nov: "Adaptive is a very problematic approach"; guide 2A: never
# learn a level from the track). Each geometry drive's routed target is already on the fixed real-music scale (BAND_SPAN,
# PASSAGE_SPAN, ENERGY_SPAN); its drive target is gain x target^curve, eased above RESPONSE_FIXED_KNEE toward 1, the same
# for every song, and the Ranges map it to size. Nothing is remembered, so a break, a loud chorus or a quiet intro never
# re-scales what follows. Fitted to the remembered-peak gain's VISIBLE behaviour, not hotter (lead review 6 Nov: a hotter
# curve pinned Pulse Strength, flattened passages and pushed crests out of the card): on seven long recordings back to
# back (chain7) the quantiles of the adaptive output paired with the routed target's are gain x t^curve within .005-.014
# rms; height and lift (the body's size) fit 1.17-1.20 x t^.75-.82, every other drive 1.24-1.32 x t^.86-.91. Above
# RESPONSE_FIXED_KNEE the drive eases toward RESPONSE_FIXED_CEILING, as the remembered peak landed a sustained loud
# passage at .85: with an easing toward 1 the crests of loud passages topped the card on 2-6% of frames where main did
# on .8-2.9% (lead review captures, 640x560).
FIXED_RESPONSE = {'height':(1.2,.75),'lift':(1.2,.82)}
FIXED_RESPONSE_DEFAULT, RESPONSE_FIXED_KNEE, RESPONSE_FIXED_CEILING = (1.12,.86), .8, .92
# The remembered peak's fast reach (.5 s) and slow release (30 s) also widened every phrase: a swell overshot before the
# peak caught up and the moments after it were scaled down. A static curve fitted to its levels kept 85-91% of its 3 s
# contrast; the fixed response widens a phrase about Breathing's 3 s mean of the drive (which learns only from heard
# music) by PHRASE_DIP below it and PHRASE_RISE above it, eased again under RESPONSE_FIXED_CEILING. With the fitted
# gain (1.25) and a rise of 1.5 Pulse Strength sat high in the knee through sustained loud passages (its 3 s contrast
# 92% of main's, Preset 7's view contrast 99.5%); the other drives' gain sits at 1.12 (still on the fitted curve's
# shape) and phrases rise by 2 (chain7: 3 s view contrast 103-105% of main on Presets 1/3/4/7 at both card sizes,
# Pulse Strength contrast 98% / 105% (Preset 4), above .9 in loud passages 8% against main's 10-15%).
PHRASE_DIP, PHRASE_RISE = 1., 2.
# The phrase mean holds through a break (it learns only from heard music), so music that came back louder than it left
# was widened upward against the mean the silence left behind (spliced 2-5 s breaks in recorded music: the following
# 10 s 2-17% larger than the unbroken clip; without the widening 0-4%). After real silence (the musical weight under
# PHRASE_SILENCE; `_settled` falls over PHRASE_SETTLE_DROP and comes back over PHRASE_SETTLE) the mean RISES up to
# 1/PHRASE_SETTLE_MIN times faster, so it catches up with the louder music, and it still falls at BREATHING_BASE, so
# the passage's own quieter return is not learnt (6 Nov: the following 10 s -7..+9% of the unbroken clip on Presets
# 1/7 against main's +4..+10%, -5..+5% on Preset 4). Continuous music keeps settled at 1 (BREATHING_BASE exactly).
PHRASE_SETTLE, PHRASE_SETTLE_DROP, PHRASE_SILENCE, PHRASE_SETTLE_MIN = 8., .5, .1, .1
# Kick Accent (operator 6 Nov: "many sustained kicks ignored (consider maybe increasing particle count at the sustained
# points or rotation speed? Something for a sense of them?)"). In a sustained loud passage the geometry has little
# headroom: the bend drive (it sets Pulse Strength) sits near its top, so a kick's swell barely rises above the swells
# already in view (rise above the pre-kick view on recorded continuous play: P7 .05-.17 against a peak of 2.4-3.0). The
# share of an admitted kick the geometry cannot show goes to channels that do not fight the shape: an eased roll-speed
# nudge (KICK_ROLL degrees per second per unit, in the roll's own direction; two stages, KICK_SENSE_ATTACK /
# KICK_SENSE_RELEASE, so the roll's speed stays continuous) bounded at KICK_ROLL_SHARE of the roll's own speed, so dense
# kicks never add up to a faster spin (lead review 6 Nov: unbounded it averaged 2x the roll in loud songs), and up to
# KICK_BIRTHS sparks born on the swell. The share is
# the kick's strength on the fixed reward scale (1 - exp(-reward / KICK_SENSE_REF): granular, never a clamped
# confidence; the reward already carries the onset's musical weight, so silence buys none) x how far bend sits above
# KICK_SENSE_KNEE x Kick Accent. A passage with headroom is unchanged.
KICK_SENSE_KNEE, KICK_SENSE_REF, KICK_ROLL, KICK_BIRTHS, KICK_ROLL_SHARE = .55, .15, 45., 4., .15
KICK_SENSE_HOLD, KICK_SENSE_ATTACK, KICK_SENSE_RELEASE = .05, .07, .25

# Floor clearance (operator, 5 Nov; see WaveformDynamics._floor_room): the packet origin sits PACKET_FLOOR_HEIGHT above
# the world floor; a ribbon whose lower edge would come within TROUGH_CLEARANCE of it lifts as a whole (never reshaped),
# by up to TROUGH_LIFT_MAX, easing up over TROUGH_ATTACK and down over TROUGH_RELEASE per stage (two stages).
PACKET_FLOOR_HEIGHT, TROUGH_CLEARANCE, TROUGH_ROOM_MIN, TROUGH_LIFT_MAX = 2., .3, .4, 1.5
# The limit stays 1.5 (lead review 6 Nov): with swells at the adaptive gain's visible size a limit of 2 or 3 cleared the
# floor (contact 7% -> .3% on Preset 4) but lifted crests toward the card's top (top edge p99 +.4 to +1.3 world units);
# the operator ranks reactivity over floor avoidance, and a clipped crest over brief floor contact.
TROUGH_ATTACK, TROUGH_RELEASE, TROUGH_VIEW = .15, 1.2, 32.  # TROUGH_VIEW: the fallback view without a card span
# Top edge first, floor second (lead review 6 Nov: crests out of the card's top are worse than brief floor contact).
# With the card's top edge supplied (core.waveform_ribbon_view.card_span) the floor lift stops TOP_CLEARANCE below it.
TOP_CLEARANCE = .3
# With the card's visible span the floor lift reads only what the camera shows, plus TROUGH_LOOKAHEAD geometric-envelope
# sigmas beyond each edge (see _trough_view), never wider than +-TROUGH_VIEW: a trough entering the view (or a swell
# deepening one on its way in) is already lifted for. 6 Nov sweep on recorded continuous play: at 2.5 sigmas the lift
# moved more and visible floor contact rose by up to .9 points (Preset 7); at 5 of the mode's own envelope sigmas (a
# Group Wave set is 3.5 carrier wavelengths wide) it equals the fixed view's on every preset at a 1282x1005 card.
TROUGH_LOOKAHEAD = 5.
# Height Shift options (operator, 5 Nov). Static Height holds every ribbon at the highest safe point: the top of the shift
# (TROUGH_LIFT_MAX), constant through every passage.
# Tilt Shift: while the lift moves, the side the history travels toward leads by TILT_LEAD seconds of lift velocity
# (bounded softly to TILT_MAX world units each side), so it rises first and settles first. History travels toward -x.
HEIGHT_MODES = ('Dynamic Height Shift', 'Static Height')
# A Travel Direction change fades every ribbon, spark and strand out over DIRECTION_FADE seconds (smoothstep, as a count
# change shrinks and dims a ribbon), swaps the published direction while they are gone, then fades them back in over
# the same time: never a mirrored pop. The history itself is untouched (it lives on its own axis).
DIRECTION_FADE = .6
TILT_LEAD, TILT_MAX, TILT_SIDE, TILT_EASE = .35, .6, -1., .3   # the lead eases over TILT_EASE seconds (no tick steps)

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
    speed: float = 12.           # world units per second along the scene axis: successive beats stay separate bands
    colour: float = .6           # share of the peak colour the pulse carries
    fade: float = 2.5            # seconds for the travelling energy to fall to 1/e
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


def ease_top(value):
    """Above RESPONSE_FIXED_KNEE an exponential approach to RESPONSE_FIXED_CEILING that never flattens on it."""
    if value > RESPONSE_FIXED_KNEE:
        room = RESPONSE_FIXED_CEILING-RESPONSE_FIXED_KNEE
        value = RESPONSE_FIXED_KNEE+room*(1.-math.exp(-(value-RESPONSE_FIXED_KNEE)/room))
    return value


def fixed_response(target, key):
    """A routed geometry target on the fixed scale -> drive target: gain x target^curve (FIXED_RESPONSE per drive) to
    RESPONSE_FIXED_KNEE, then an exponential approach to RESPONSE_FIXED_CEILING that never flattens on it."""
    gain,curve = FIXED_RESPONSE.get(key,FIXED_RESPONSE_DEFAULT)
    return unit(ease_top(gain*max(0.,target)**curve))


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


@functools.lru_cache(maxsize=64)   # a pure function of the spring; a new dynamics (activation, Studio replay) reuses it
def spread_impulse_velocity(frequency, damping):
    """Momentum whose kick, delivered over IMPULSE_SPREAD, gives the spring a unit peak displacement (the spread kick
    peaks lower than an instantaneous one; this keeps the authored hit excursion). Integrated finely once per spring
    configuration with the exact spring step."""
    step, push, x, v, peak = 1./4000., 1., 0., 0., 0.
    keep = math.exp(-step/IMPULSE_SPREAD)
    for _ in range(int(4000*max(1.,2./frequency))):
        delivered = push*(1.-keep)
        push -= delivered
        x,v = elastic(x,v+delivered,0.,step,frequency,damping)
        peak = max(peak,x)
    return 1./peak


def carrier_wavelength(controls):
    """Longest local carrier wavelength (world units) of the active cards: y = sin(.7p), p advancing at
    rate*2pi*head_hz (slowed by up to .31*phase_swell), carried by the history at flow speed."""
    flow = controls.scene.flow
    rates = [abs(float(card['rate'])) for card in controls.cards[:max(1,controls.count)]]
    slowest = min(rates)*.7*flow.head_hz*(1.-.31*min(1.,abs(flow.phase_swell)))
    if slowest <= 0.:
        return GEOM_MAX_WAVELENGTH
    return min(GEOM_MAX_WAVELENGTH,flow.speed/slowest)


def row_gradient(f,xs):
    """``np.gradient(f[i],xs[i])`` for every row i at once, with NumPy's exact arithmetic (edge order 1, and the
    uniform-spacing formula for a row whose spacing is exactly constant), so results are bit-identical."""
    return apply_row_gradient(f,row_gradient_coefficients(xs))


def row_gradient_coefficients(xs):
    """The spacing-only part of ``row_gradient``: shared by every field sampled at the same rows of ``xs``."""
    dx = np.diff(xs,axis=1)
    dx1,dx2 = dx[:,:-1],dx[:,1:]
    return (dx,-(dx2)/(dx1*(dx1+dx2)),(dx2-dx1)/(dx1*dx2),dx1/(dx2*(dx1+dx2)),(dx==dx[:,:1]).all(axis=1))


def apply_row_gradient(f,coefficients):
    """``f`` is (rows, knots), or (fields, rows, knots) for several fields sampled at the same rows."""
    dx,a,b,c,uniform = coefficients
    out = np.empty_like(f)
    interior = a*f[...,:-2]+b*f[...,1:-1]+c*f[...,2:]
    if uniform.any():
        interior[...,uniform,:] = ((f[...,2:]-f[...,:-2])/(2.*dx[:,:1]))[...,uniform,:]
    out[...,1:-1] = interior
    out[...,0] = (f[...,1]-f[...,0])/dx[:,0]
    out[...,-1] = (f[...,-1]-f[...,-2])/dx[:,-1]
    return out


def uniform_gradient(f,spacing):
    """``np.gradient(f,spacing)`` for a 1D field and scalar spacing, with NumPy's exact arithmetic (edge order 1),
    without its general-purpose setup (it ran twice a tick on the pulse grid)."""
    out = np.empty_like(f)
    out[1:-1] = (f[2:]-f[:-2])/(2.*spacing)
    out[0] = (f[1]-f[0])/spacing
    out[-1] = (f[-1]-f[-2])/spacing
    return out


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
    height_mode: str = 'Dynamic Height Shift'
    tilt_shift: bool = False
    breathing: float = 0.
    adaptive_response: bool = False   # True: the remembered-peak gain (pre-6 Nov); False: FIXED_RESPONSE
    kick_accent: float = 0.           # share of a sustained kick the geometry cannot show sent to roll and sparks


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
    direction: float = 1.           # published Travel Direction (Flow.direction): history axis -> world x sign
    pulse: bytes = b''              # published pulse appearance field (pulse_at) on PULSE_GRID, float32, history x


class WaveformDynamics:
    def __init__(self, controls: HybridControls):
        self.controls = controls
        self.ring = RibbonRing(RIBBON_CAPACITY, colours=[(*c['quiet'][0],1.) for c in controls.cards],
                               edge_colours=[(*c['quiet'][1],1.) for c in controls.cards],period=.5)
        self.time = self.travel = self.angle = self.angular_speed = self.twist_phase = self._hit = 0.
        self._kick_impulse = self._kick_stage = self.kick_sense = 0.   # Kick Accent: held share, eased stages
        self._heard = 1.   # how fully Breathing's mean may learn (BREATHING_HEARD_RETURN)
        self._settled = 1. # 1 in continuous music; 0 just after real silence (the phrase mean's catch-up, PHRASE_SETTLE)
        self.phase = controls.scene.flow.phase
        self.bands, self.power = (0.,0.,0.),0.
        self.passage = self.phrase = 0.
        self.zoom, self._sustain = 1., 0.
        self._loud_level = 0.  # the sustained level the remembered peaks were set at (Breathing's quieter-passage hold)
        self._glow = 0.  # swell-shaped light response to hits (rise HIT_GLOW_RISE, settle HIT_GLOW_SETTLE)
        self._pulse = np.zeros((2,PULSE_GRID.size))  # travelling toward -x, toward +x
        self._fresh = np.zeros((2,PULSE_GRID.size))  # the same transport with a short fade: recently launched swells
        self._pulse_pending = 0.
        self._view_world = None  # (low, high) world x of the scene axis the framed camera shows (capture-supplied)
        self._view_top = None    # world y of the card's top edge above the scene axis (capture-supplied), or None
        self._seen = (None,None)  # cached (key, per-direction seen weights) for the age-once-seen fade
        self._rim_share = 1.      # share of the appearance level published for Pulse Rim (RIM_EDGE_SHARE once seen)
        self._trough_stage,self._trough_lift,self._trough_time = np.zeros((RIBBON_CAPACITY,1)),np.zeros((RIBBON_CAPACITY,1)),None
        self._tilt_lead,self._tilt_time = np.zeros((RIBBON_CAPACITY,1)),None
        # Frozen Past on the cloth: memory, peak, previous swell, rising, and the Pulse Strength the passage was shaped with
        # (passage) and that the memory carries (carried), so a held shape keeps its size when the music later softens.
        self._held = np.zeros((6,PULSE_GRID.size))
        self._frozen_swell = None   # Frozen Past: (live travelling envelope, held swell in strength units) for the gain
        self._whole = self._whole_fresh = 0.         # Whole Swell global raw level and its short-fade copy
        self._drift_stage = np.zeros(PULSE_GRID.size)  # first stage of the surge's easing
        self._drift = np.zeros(PULSE_GRID.size)      # rate-limited signed surge field (swell units)
        self._level = np.zeros(PULSE_GRID.size)      # published appearance swell (authored width)
        self._focus = np.zeros(PULSE_GRID.size)      # where swell-carried particles/strands gather
        self._geom = np.zeros(PULSE_GRID.size)       # broad geometric swell (pre owner bound)
        self._kernel = (None,None)
        self._geom_share = (1.,None)
        self._surge_bound = {}  # per ribbon: compression bound last applied and its logical time  # flow-rule share last applied and its logical time (rises smoothly)
        self._pulse_credit = self._pulse_births = 0.  # births bought by injected energy / released and due
        self._flux_fast = self._flux_slow = 0.
        self._shape_input = np.zeros((2,5),np.float64)  # two stages: bass/mid/high, power, hit
        self.spring = [[0.,0.,0.] for _ in range(RIBBON_CAPACITY)]
        self.velocity = [[0.,0.,0.] for _ in range(RIBBON_CAPACITY)]
        self._push = [[0.,0.,0.] for _ in range(RIBBON_CAPACITY)]  # undelivered kick momentum (IMPULSE_SPREAD)
        self.drive = {key:0. for key in TARGETS}
        self._drive_stage = {key:0. for key in SMOOTH_TARGETS}
        self._breath_base = {key:0. for key in RESPONSE_TARGETS}  # phrase-scale mean of each drive's target (Breathing)
        self._response_peak = {key:RESPONSE_PEAK_FLOOR for key in RESPONSE_TARGETS}  # recent peak per drive (gain)  # first stage of the geometry drives' smoothing
        self.count_share = [1. if index < controls.count else 0. for index in range(RIBBON_CAPACITY)]
        self.direction = controls.scene.flow.direction
        self._direction_phase = self.direction_share = 1.   # linear fade phase and its smoothstep share
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
                dynamic_zoom=False, zoom_hold=False, view_span=None):
        """``view_span``: (low, high) world x of the scene axis the framed camera shows (configuration from the
        capture; ``core.waveform_ribbon_view.visible_span``), optionally with the world y of the card's top edge above
        that axis (``card_span``; the floor lift never lifts a crest through it). None keeps the last one supplied
        (initially none)."""
        if not math.isfinite(dt) or not 0. <= dt <= .1:
            raise ValueError('Ribbon logical dt must be finite in 0..0.1 seconds')
        if view_span is not None:
            low,high,*top = (float(v) for v in view_span)
            if not (math.isfinite(low) and math.isfinite(high) and high > low) or len(top) > 1 or \
                    not all(math.isfinite(v) for v in top):
                raise ValueError('Waveform view span must be a finite (low, high[, top]) interval')
            self._view_world = (low,high)
            self._view_top = top[0] if top else None
        if controls is not None:
            self.controls = controls
        c = self.controls
        if not 0.05 <= c.frequency <= 4. or not .1 <= c.damping <= .95:
            raise ValueError('Ribbon elastic frequency/damping is outside the stable authoring domain')
        if self._elastic_config != (c.frequency,c.damping):
            self._elastic_config=(c.frequency,c.damping)
            self._elastic_frequencies=tuple(c.frequency*share for share in (1.,1.75,2.75))
            self._impulse_scales=tuple(spread_impulse_velocity(frequency,c.damping) for frequency in self._elastic_frequencies)
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
        hold = unit(c.breathing)
        softness = hold*unit((BREATHING_LOUD-self.passage)/BREATHING_LOUD)
        quieter = unit((HOLD_BELOW[0]-self._sustain/max(self._loud_level,1e-6))/(HOLD_BELOW[0]-HOLD_BELOW[1]))
        memory = RESPONSE_MEMORY*(1.+hold*quieter*(RESPONSE_HOLD-1.)) if hold and quieter else RESPONSE_MEMORY
        self._loud_level = max(self._sustain,follower(self._loud_level,self._sustain,dt,0.,memory))
        geometry_release = c.release*(1.-BREATHING_REACH*softness)
        learn = self._learn_rate(dt,presence)
        # Breathing's phrase mean re-learns the music fast after a break (PHRASE_SETTLE), so a phrase is not widened
        # against a mean the silence left stale; the remembered-peak path keeps BREATHING_BASE.
        mean_tau = BREATHING_BASE if c.adaptive_response else BREATHING_BASE*max(PHRASE_SETTLE_MIN,self._settled)
        for key in TARGETS:
            target = route(c.routing[key],sources,passage=gate)
            if key in RESPONSE_TARGETS:
                # Every song uses the whole authored Quiet->Peak ramp (operator, 5 Nov: "reactivity needs much more
                # granularity and to actually hit that granularity"; no geometry drive ever passed .79 and a fixed
                # span over-drove soft songs while heavy ones stayed low). Gain only: each drive is divided by a
                # memory of its own recent peak (reached in RESPONSE_REACH seconds, relaxing over RESPONSE_MEMORY,
                # never below RESPONSE_PEAK_FLOOR), so a song's loudest moments reach Peak while a quiet passage after
                # a loud one stays quiet (an offset window re-expanded quiet intros to full size). The remembered
                # peak lands at RESPONSE_TOP, so a sustained loud passage keeps headroom for its accents instead of
                # pinning at Peak (operator: sustained passages need the most judgement).
                # Breathing holds the memory only through a quieter PASSAGE (``memory`` above): the passage-scale 30 s
                # memory re-normalised a passage at 70% of the loud input back up to loud reach (Pulse Strength .73 ->
                # .88, above the loud passage's .87) within 25 s. Keyed to the drive's own dips it held every song
                # (the drive sits below its peak between almost every pair of beats). Rises still reach in RESPONSE_REACH.
                if c.adaptive_response:
                    # The remembered peak learns only from heard music (``learn``): a break can no longer lower it
                    # and size the music's return up (spliced 5 s break, Rag Doll's loud end: +5-9% for 10 s).
                    self._response_peak[key] = max(RESPONSE_PEAK_FLOOR,follower(
                        self._response_peak[key],target,dt*learn,RESPONSE_REACH,memory))
                    target = unit(RESPONSE_TOP*target/self._response_peak[key])
                else:
                    target = fixed_response(target,key)
                # Breathing's phrase-scale mean learns only from heard music (BREATHING_HEARD_RETURN): it fell with a
                # break, so the music's return swelled against it (spliced 2-5 s breaks on recorded music: +4..11%
                # height for 10 s on every Breathing preset, 0..1% with Breathing 0).
                base = self._breath_base[key] = follower(self._breath_base[key],target,dt*learn,mean_tau,BREATHING_BASE)
                if softness:  # Breathing 0 (or a loud passage) keeps the exact unwidened target
                    # A passage returning from a break is not widened while it returns (its deficit against the held
                    # mean is the silence, not a phrase): the contrast comes back with the learning rate.
                    target = unit(base+(target-base)*(1.+BREATHING_CONTRAST*softness*learn))
                if not c.adaptive_response and (target<base or PHRASE_RISE):
                    # The fixed response widens a phrase about its mean (PHRASE_DIP below it, PHRASE_RISE above it,
                    # eased again under the ceiling), as the remembered peak's fast reach and slow release did.
                    widen = PHRASE_DIP if target<base else PHRASE_RISE
                    target = base+(target-base)*(1.+widen*learn)
                    target = unit(ease_top(target) if target>base else target)
            if key in SMOOTH_TARGETS:
                # Geometry never snaps (operator, 5 Nov: "twitch"): two cascaded followers, so the drive's VELOCITY
                # is continuous. A single 45 ms first-order attack made lift/bend/width/twist jump on every transient
                # (vertical acceleration spiked >4x its median on 18% of ticks on recorded music).
                attack = max(c.attack,GLOBAL_ATTACK if key in GLOBAL_TARGETS else GEOMETRY_ATTACK)
                self._drive_stage[key] = follower(self._drive_stage[key],target,dt,attack,geometry_release)
                self.drive[key] = follower(self.drive[key],self._drive_stage[key],dt,attack,geometry_release)
            else:
                self.drive[key] = follower(self.drive[key],target,dt,c.attack,c.release)
        if c.kick_accent>0. or self.kick_sense>0.:
            lack = unit((self.drive['bend']-KICK_SENSE_KNEE)/(1.-KICK_SENSE_KNEE))*unit(c.kick_accent)
            share = (1.-math.exp(-hit/KICK_SENSE_REF))*lack
            self._kick_impulse = max(share,self._kick_impulse*math.exp(-dt/KICK_SENSE_HOLD))
            self._kick_stage = follower(self._kick_stage,self._kick_impulse,dt,KICK_SENSE_ATTACK,KICK_SENSE_RELEASE)
            self.kick_sense = min(follower(self.kick_sense,self._kick_stage,dt,KICK_SENSE_ATTACK,KICK_SENSE_RELEASE),
                                  KICK_ROLL_SHARE*abs(self.angular_speed)/KICK_ROLL)
            if self.kick_sense<1e-6 and not self._kick_impulse:
                self.kick_sense = self._kick_stage = 0.
            if share>0. and c.accents is not None:   # sparks on the swell, admitted once (as pulse births are)
                self._pulse_births = min(float(MAX_BURST),self._pulse_births+KICK_BIRTHS*share)
        released = self._advance_pulse(dt,hit,energy_shaped)
        self._advance_pulse_births(dt,released)
        for owner,card in enumerate(c.cards):
            support = 1. if card['band']=='All' else bands[('Bass','Mids','Highs').index(card['band'])]
            for index,target in enumerate((self.drive['bend'],self.drive['torsion'],self.drive['depth'])):
                # A kick is delivered as a short force (IMPULSE_SPREAD), not an instantaneous velocity jump: the same
                # momentum, but the sway/torsion velocity stays continuous (operator, 5 Nov: the lattice twitched
                # left and right in every mode on each hit).
                self._push[owner][index] += support*impulses[index]*c.impulse*self._impulse_scales[index]
                delivered = self._push[owner][index]*(1.-math.exp(-dt/IMPULSE_SPREAD))
                self._push[owner][index] -= delivered
                self.velocity[owner][index] += delivered
                self.spring[owner][index],self.velocity[owner][index] = elastic(
                    self.spring[owner][index],self.velocity[owner][index],target*support,dt,
                    self._elastic_frequencies[index],c.damping)
        target_speed = self._value('rotation') if c.rotation_enabled else 0.
        self.angular_speed = follower(self.angular_speed,target_speed,dt,c.rotation_attack,c.rotation_release)
        roll = self.angular_speed+(math.copysign(KICK_ROLL*self.kick_sense,target_speed) if c.rotation_enabled else 0.)
        self.angle = math.remainder(self.angle+math.radians(roll)*dt,2*math.pi)
        low,high = c.twist_speed
        self.twist_phase = math.remainder(self.twist_phase+(low+(high-low)*self.drive['twist'])*dt,2*math.pi)
        for index in range(RIBBON_CAPACITY):
            self.count_share[index] = follower(self.count_share[index],float(index<c.count),dt,.5,.5)
            if abs(self.count_share[index]-float(index<c.count)) < 1e-4:
                self.count_share[index] = float(index<c.count)
        if c.scene.flow.direction != self.direction or self._direction_phase < 1.:
            out = c.scene.flow.direction != self.direction
            self._direction_phase = min(1.,max(0.,self._direction_phase+(-dt if out else dt)/DIRECTION_FADE))
            if out and self._direction_phase == 0.:
                self.direction = c.scene.flow.direction
            phase = self._direction_phase
            self.direction_share = phase*phase*(3.-2.*phase)
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
        if self.direction_share < 1.:
            self._snapshot = self._direction_faded(self._snapshot,self.direction_share)
        return self._snapshot

    @staticmethod
    def _direction_faded(snapshot,share):
        """Sparks and strands dim with their ribbons through a Travel Direction change (light only; their births,
        lifetimes and identities are untouched, so they reappear where they are)."""
        particles,strands = snapshot.particles,snapshot.strands
        if particles:
            births = np.frombuffer(particles,np.float32).reshape(-1,16).copy()
            births[:,12] *= share                                   # spark light
            particles = births.tobytes()
        if strands:
            from core.ribbon_strand_cohorts import COHORT_ROWS
            records = np.frombuffer(strands,np.float32).reshape(-1,COHORT_ROWS,4).copy()
            records[:,1,3] *= share                                 # strand light
            strands = records.tobytes()
        return replace(snapshot,particles=particles,strands=strands)

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
        sources,seen = self._view_sources(p)
        self._rim_share = 1. if seen is None else RIM_EDGE_SHARE
        shift = p.speed*dt
        blur = min(.24,PULSE_DIFFUSION*dt/(PULSE_DX*PULSE_DX))
        fades = (p.fade,min(p.fade,FRESH_FADE))
        decays = tuple(math.exp(-dt/fade) for fade in fades)
        if seen is not None:
            decays = tuple(np.exp((-dt/fade)*seen) for fade in fades)  # per direction: ages only once seen
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
                field *= decay if seen is None else decay[index]
                for origin,direction in sources:
                    if travelling and direction==sign and release:
                        field += release/len(sources)*np.exp(-.5*((PULSE_GRID-origin)/sigma)**2)
                field[field<1e-9] = 0.  # after injection, so a zero-length step changes nothing
        # Whole Swell: nothing travels; one level rises with the shared release and settles gently.
        settle = min(WHOLE_SETTLE[1],max(WHOLE_SETTLE[0],.25*p.fade))
        self._whole = self._whole*math.exp(-dt/settle)+(0. if travelling else release)
        self._whole_fresh = self._whole_fresh*math.exp(-dt/min(settle,FRESH_FADE))+(0. if travelling else release)
        self._advance_frozen(dt,p.mode=='Frozen Past',self._value('bend'))
        self._publish_fields(dt)
        return release

    def _view_sources(self,p):
        """Pulse sources and, when the camera's span is known and Travelling Pulse travels in from an edge, the
        per-direction seen weights (0 beyond the entry edge, 1 inside it; see VIEW_MARGIN). Otherwise (sources, None)."""
        if self._view_world is None or p.mode!='Travelling Pulse' or p.direction=='Centre Out':
            return pulse_sources(p.direction),None
        low,high = self._view_world
        if self.direction < 0.:   # the history axis is mirrored into the world (Travel Direction)
            low,high = -high,-low
        ramp = self._blur_kernel(GEOM_WAVES)[1]
        key = (low,high,ramp,p.direction)
        if self._seen[0]!=key:
            entering = np.clip((high+ramp-PULSE_GRID)/ramp,0.,1.), np.clip((PULSE_GRID-low+ramp)/ramp,0.,1.)
            weights = np.stack([w*w*(3.-2.*w) for w in entering])   # toward -x enters at high, toward +x at low
            margin = VIEW_MARGIN*ramp
            origin = (min(PULSE_ORIGIN,high+margin),-1.) if p.direction=='Head To Tail' else (max(-PULSE_ORIGIN,low-margin),1.)
            self._seen = (key,(weights,(origin,)))
        weights,sources = self._seen[1]
        return sources,weights

    def _advance_frozen(self,dt,active,strength=0.):
        """Per-cell passage peak held on the cloth; bounded fixed grid advected with the history flow."""
        held,peak,previous,rising,passage,carried = self._held
        flow = self.controls.scene.flow.speed*dt
        if not active:
            if self._held.any():
                # Leaving the mode fades the memory instead of dropping it.
                held *= math.exp(-dt/FROZEN_REPLACE)
                held[held<1e-6] = 0.
                peak[:] = previous[:] = rising[:] = passage[:] = 0.
            return
        if flow:
            for row in self._held:
                row[:] = np.interp(PULSE_GRID+flow,PULSE_GRID,row,left=0.,right=0.)
        now = self._pulse[0]+self._pulse[1]
        present = now>FROZEN_PRESENT
        up_now = present & (now>previous*(1.+FROZEN_RISING)+1e-4)
        start = up_now & (rising<.5)
        peak[:] = np.where(start,now,np.where(up_now,np.maximum(peak,now),peak))
        # The passage's Pulse Strength: the strongest reached while its swell rose here. The memory carries it with the
        # same rules as the held level, so a held shape stays the size it was shaped at (operator, 5 Nov: re-scaling
        # the memory by today's strength made the frozen trail vanish as soon as the music softened).
        passage[:] = np.where(start,strength,np.where(up_now,np.maximum(passage,strength),passage))
        rise = 1.-math.exp(-dt/FROZEN_RISE)
        settle = 1.-math.exp(-dt/FROZEN_REPLACE)
        grow = peak>held
        carried[:] = np.where(grow,carried+(passage-carried)*rise,np.where(up_now,carried,carried+(passage-carried)*settle))
        held[:] = np.where(grow,held+(peak-held)*rise,np.where(up_now,held,held+(peak-held)*settle))
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
        self._frozen_swell = None
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
            # The gain uses the live swell at today's strength and the held memory at the strength it was shaped with
            # (strength-weighted local average, so a held shape's edges keep its own strength).
            held = self._held[0]
            shaped = broad(held*self._held[5])/np.maximum(broad(held),1e-9)
            self._frozen_swell = (soft(broad(travelling)),.7*soft(broad(held))*shaped)
            drift_target = soft(broad(self._pulse[1]))-soft(broad(self._pulse[0]))
        elif p.mode=='Group Wave':
            # The light covers the set: the look spread over the group envelope (unit-sum, so it never brightens).
            self._level = np.minimum(1.,broad(look)*(p.width/2.3548)/sigma_g)
            self._focus = self._level
            total = np.zeros(PULSE_GRID.size)
            for index,sign in enumerate((-1.,1.)):
                # The set's geometry and surge follow the FRESH energy, as Travelling Pulse's do (operator, 5 Nov,
                # Preset 7 on Rag Doll: no decay in soft passages, sustained passages flat). Built from the long-fade
                # field, the peak-keeping set envelope (sigma_g/sigma_w, x7.4 on Preset 7) piled every beat of the last
                # Pulse Fade seconds into one bound: the swell sat at PULSE_SATURATION over 67% of the view (median/max
                # .98), so the whole body inflated at once with the Pulse Strength drive and never let go.
                wide = PULSE_FRESH_GAIN*broad(self._fresh[index])
                lead = -sign*sigma_g*np.gradient(wide,PULSE_DX)/(wide+1e-6)
                weighted = wide*(1.+GROUP_LEAD*np.tanh(lead))
                total += weighted
                drift_target += sign*GROUP_SURGE*soft(weighted)
            self._geom = soft(total)
        else:
            self._level = look
            self._focus = look
            # Geometry and surge follow the FRESH energy (the same transport with a short fade): each beat is a
            # travelling bump with calmer waveform around it. Driven by the long-fade field the swells overlapped
            # into one uniform inflation of the whole view (5 Nov: median/max .98 over the visible span), so the
            # operator could not see a pulse at all. Light keeps its own fresh-led look above.
            self._geom = soft(PULSE_FRESH_GAIN*broad(self._fresh[0]+self._fresh[1]))
            drift_target = soft(PULSE_FRESH_GAIN*broad(self._fresh[1]))-soft(PULSE_FRESH_GAIN*broad(self._fresh[0]))
        # The surge eases (two cascaded followers, SURGE_EASE each) so the cloth's sideways velocity is continuous; the
        # old clipped step had piecewise-constant velocity, a sideways jolt at every change (operator, 5 Nov: lattice
        # twitching left and right). SURGE_RATE still bounds the change per second.
        ease = 1.-math.exp(-dt/SURGE_EASE) if dt>0. else 0.
        self._drift_stage = self._drift_stage+(drift_target-self._drift_stage)*ease
        step = SURGE_RATE*dt
        self._drift = self._drift+np.clip((self._drift_stage-self._drift)*ease,-step,step)

    def _learn_rate(self,dt,presence):
        """Share of real time Breathing's phrase-scale mean learns this tick: 0 with the musical weight, back over
        BREATHING_HEARD_RETURN seconds (see BREATHING_HEARD_RETURN)."""
        self._heard = follower(self._heard,unit(presence),dt,BREATHING_HEARD_RETURN,0.)
        self._settled = follower(self._settled,1. if presence>PHRASE_SILENCE else 0.,dt,PHRASE_SETTLE,PHRASE_SETTLE_DROP)
        return self._heard

    def _advance_pulse_births(self,dt,released):
        """Injected energy buys a bounded number of swell-carried births, released over the swell's journey and
        consumed once by burst admission. Silence buys none; without sparks or the control nothing is banked."""
        c = self.controls
        if c.accents is None:
            self._pulse_credit = self._pulse_births = 0.
            return
        if c.pulse.particles<=0.:   # births a kick banked (Kick Accent) stay due; the pulse buys none
            self._pulse_credit = 0.
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
        if self._frozen_swell is None:
            swell = .7*strength*self._geom
        else:
            live,held = self._frozen_swell
            swell = np.maximum(.7*strength*live,held)
        if not np.any(swell):
            self._geom_share = (1.,self.time)
            return np.ones(PULSE_GRID.size)
        k = 2.*math.pi/carrier_wavelength(self.controls)
        # The largest share in [0, 1] with |g'|/g <= GEOM_SLOPE*k and |g''|/g <= GEOM_CURVE*k^2 for g = 1 + share*swell.
        # The gradient is linear, so g' = share*swell' and g'' = share*swell''; each ratio share*a/(1 + share*swell)
        # rises monotonically with share, so the bound share*(a - limit*swell) <= limit is exact per grid point.
        # (Formerly a 20-step bisection with two np.gradient calls per step: ~40 gradients a tick.)
        first = uniform_gradient(swell,PULSE_DX)
        second = uniform_gradient(first,PULSE_DX)
        share = 1.
        for slope,limit in ((np.abs(first),GEOM_SLOPE*k),(np.abs(second),GEOM_CURVE*k*k)):
            over = slope-limit*swell
            binding = over>limit        # only these can bring the share below 1 (smaller ones would also overflow)
            if binding.any():
                share = min(share,float((limit/over[binding]).min()))
        # One share bounds the whole field, so when the binding constraint somewhere lets go every swell on screen grew
        # at once (5 Nov: the gain jumped 2.39 -> 2.89 in one tick, a vertical pop). The share may fall at once (that
        # is the flow-rule safety) but rises at most GEOM_SHARE_RISE per second; a smaller share is always safe.
        previous,when = self._geom_share
        if when is not None and self.time>=when:
            share = min(share,previous+GEOM_SHARE_RISE*(self.time-when))
        self._geom_share = (share,self.time)
        return 1.+share*swell

    def _surge(self,data,x,y,z,amount):
        """Slide each knot ALONG its own curve by the signed swell: the body is resampled at the shifted positions
        (cubic Hermite through the unsurged knots), so the curve itself never changes, only its cloth moves.

        Ribbons sharing one history window (count, start, capacity) are resampled together as rows: the same
        element-wise arithmetic as one ribbon at a time (``row_gradient`` reproduces ``np.gradient``), so the
        published packet is byte-identical, at a fraction of the per-ribbon NumPy dispatch (5 Nov profile)."""
        drift = self.pulse_drift(x)*amount
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
            # The ends never slide: a smooth taper of fixed length (a taper sized from the current drift changed length
            # every tick and jittered the knots near the head; 5 Nov per-tick acceleration probe).
            edge = np.clip(np.minimum(xs-xs[:,:1],xs[:,-1:]-xs)/SURGE_TAPER,0.,1.)
            ds = ds*(edge*edge*(3.-2.*edge))
            squeeze = (np.diff(ds,axis=1)/np.diff(xs,axis=1)).min(axis=1,keepdims=True)
            limited = squeeze < -SURGE_MAX_COMPRESSION
            bound = np.where(limited,SURGE_MAX_COMPRESSION/np.where(limited,-squeeze,1.),1.)
            # The compression bound scales a whole ribbon's surge: it may tighten at once but relaxes at most
            # SURGE_BOUND_RISE per second, so a constraint letting go never jolts the whole ribbon sideways.
            for row,member in enumerate(rows[:,0]):
                previous,when = self._surge_bound.get(int(member),(1.,None))
                if when is not None and self.time>=when:
                    bound[row,0] = min(bound[row,0],previous+SURGE_BOUND_RISE*(self.time-when))
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
            # y and z resampled together as one (2, rows, knots) stack: the same element-wise arithmetic in one pass.
            vs = np.stack((y[rows,order],z[rows,order]))
            slope = apply_row_gradient(vs,row_gradient_coefficients(xs))
            pick = lambda field,at: np.take_along_axis(field,at[None],2)
            resampled = (h00*pick(vs,cell)+h10*h*pick(slope,cell)+h01*pick(vs,cell+1)+h11*h*pick(slope,cell+1))
            y[rows,order],z[rows,order] = resampled[0],resampled[1]
            x[rows,order] = target
        return x,y,z

    def _floor_room(self,height,hang,room,visible,static=None,soft=None,headroom=None):
        """Per ribbon: how far to lift the whole ribbon so its lower edge stays TROUGH_CLEARANCE above the floor (see
        snapshot). Two cascaded followers (TROUGH_ATTACK up, TROUGH_RELEASE down, on the logical clock), so the lift's
        velocity is continuous: a one-stage follower jumped on every new trough, which was itself a twitch.
        Top edge first, floor second (lead review 6 Nov): with the card's top supplied (``headroom``: room above the
        rest line for the published crest ``soft`` plus its sheet hang, TOP_CLEARANCE below the edge) the lift never
        raises a crest the floor lift considers through it; the floor may then be grazed. A lift the top lowers eases
        down at TROUGH_ATTACK, as fast as it rose, so a crest climbing toward the edge is not lifted past it."""
        capped = None
        if static is None:
            sinking = np.where(visible,hang-height,-np.inf)                 # depth of the lower edge below rest
            target = np.clip(sinking.max(axis=1,keepdims=True)-room,0.,TROUGH_LIFT_MAX)
            if headroom is not None:
                top = np.maximum(headroom-np.where(visible,soft+hang,-np.inf).max(axis=1,keepdims=True),0.)
                capped = top<target
                target = np.minimum(target,top)
        else:
            target = np.full((RIBBON_CAPACITY,1),static)                    # Static Height (a live switch eases)
        if self._trough_time is None:
            self._trough_stage = self._trough_lift = target
        elif self.time>self._trough_time:
            dt = self.time-self._trough_time
            for name,goal in (('_trough_stage',target),('_trough_lift',None)):
                goal = self._trough_stage if goal is None else goal
                current = getattr(self,name)
                fast = goal>current if capped is None else (goal>current)|capped
                tau = np.where(fast,TROUGH_ATTACK,TROUGH_RELEASE)
                setattr(self,name,current+(goal-current)*(1.-np.exp(-dt/tau)))
        self._trough_time = self.time
        return self._trough_lift

    def _trough_view(self,x):
        """(knots the floor lift considers, the view's centre and half extent for Tilt Shift). With the card's visible
        span (``view_span``) only what the camera shows, plus a lookahead of TROUGH_LOOKAHEAD geometric-envelope sigmas
        beyond each edge so a trough (or a swell deepening one) entering the view is already lifted for, within the
        former fixed +-TROUGH_VIEW (a large card's view reaches it); without a span exactly that fixed view."""
        if self._view_world is None:
            return np.abs(x)<TROUGH_VIEW,0.,TROUGH_VIEW
        key = (self._view_world,self.direction)
        cached = getattr(self,'_trough_span',None)
        # One solve per controls (by identity: they are frozen and replaced on change) / span / direction change.
        if cached is None or cached[0] is not self.controls or cached[1]!=key:
            low,high = self._view_world
            if self.direction < 0.:   # history axis -> world x is mirrored (Travel Direction)
                low,high = -high,-low
            waves = GROUP_WAVES if self.controls.pulse.mode=='Group Wave' else GEOM_WAVES   # the mode's own envelope
            margin = TROUGH_LOOKAHEAD*self._blur_kernel(waves)[1]
            cached = self._trough_span = (self.controls,key,(max(-TROUGH_VIEW,low-margin),min(TROUGH_VIEW,high+margin)))
        low,high = cached[2]
        return (x>low)&(x<high),.5*(low+high),.5*(high-low)

    def _height_shift(self,height,hang,room,x,soft=None,headroom=None):
        """Per ribbon (and, with Tilt Shift, per knot) vertical offset that keeps lower edges off the floor, never
        lifting a crest through the card's top edge (``headroom``: see _floor_room)."""
        static = TROUGH_LIFT_MAX if self.controls.height_mode=='Static Height' else None
        visible,centre,half = self._trough_view(x)
        lift = self._floor_room(height,hang,room,visible,static,soft,headroom)
        # Tilt Shift: the lift's velocity (its second stage follows the first, so it is continuous) sets a lead that
        # eases once more, so the tilt is smooth in velocity too. Switched off (or Static Height) the lead eases back to
        # zero rather than vanishing; a ribbon that never tilted keeps an exact zero lead (byte-identical body).
        goal = 0.
        if static is None and self.controls.tilt_shift:
            gap = self._trough_stage-lift
            goal = TILT_MAX*np.tanh(TILT_LEAD*gap/np.where(gap>0.,TROUGH_ATTACK,TROUGH_RELEASE)/TILT_MAX)
        if self._tilt_time is not None and self.time>self._tilt_time:
            self._tilt_lead = self._tilt_lead+(goal-self._tilt_lead)*(1.-math.exp(-(self.time-self._tilt_time)/TILT_EASE))
        self._tilt_time = self.time
        if not self._tilt_lead.any():
            return lift
        return lift+self._tilt_lead*np.clip(TILT_SIDE*(x-centre)/half,-1.,1.)

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
        rows[:,:,3] = 3.5*np.tanh(rows[:,:,3]*values['width']*(1.+.35*geometric)/3.5)
        rows[:,:,2] = 5.*np.tanh(z/5.)
        origin_twist = (data[:,1,0,None]+math.pi)%(2*math.pi)-math.pi
        twist = data[:,5::KNOT_ROWS,1]+origin_twist
        twist = twist*values['twist']+values['torsion']*(1.6*m*np.sin(.45*u+owner)+.12*h*np.sin(.7*u-owner))
        data[:,5::KNOT_ROWS,1] = twist+self.twist_phase+self.angle+idle*.18*np.sin(.28*self.time+.3*u+owner)
        data[:,1,0] = 0.
        # Admission phase of the history ring in [0, 1) (header extra.w): the renderer anchors the visible ends inside
        # the history and continues from there, so admitting/evicting a knot never steps the ends (core.ribbon_continuation).
        data[:,1,3] = unit((self.time-(self._next_knot-1./self.controls.scene.flow.knot_hz))*self.controls.scene.flow.knot_hz)
        # The floor is never hit and the shape never changes (operator, 5 Nov: "we collide with the floor a lot";
        # then: per-knot trough limits made boxy flat-bottomed troughs "instead of FLOWING"). When a ribbon's lower
        # edge (the cloth sweep's side is cos(twist)*Y + sin(twist)*Z, so the sheet hangs width*|cos(twist)| below its
        # centre) would come within TROUGH_CLEARANCE of the floor, the WHOLE ribbon rises (up to TROUGH_LIFT_MAX): an
        # offset is the only bound that preserves the shape exactly, so nothing is ever bent against its shape. The lift
        # eases through two stages on the logical clock (see _floor_room); a deeper trough than the cap may still graze.
        hang = np.abs(rows[:,:,3]*np.cos(data[:,5::KNOT_ROWS,1]))
        room = max(TROUGH_ROOM_MIN,PACKET_FLOOR_HEIGHT+values['lift']-TROUGH_CLEARANCE)
        soft_y = 5.*np.tanh(y/5.)
        # The card's top above the packet's rest line, scaled with Dynamic Zoom (the long lens is all but orthographic).
        headroom = None if self._view_top is None else \
            (self._view_top-PACKET_FLOOR_HEIGHT)*self.zoom-TOP_CLEARANCE-values['lift']
        rise = self._height_shift(y,hang,room,x,soft_y,headroom)
        rows[:,:,1] = soft_y+values['lift']+rise
        # Strong local musical regions change colour immediately, even before new head history enters view.
        # The crest mask is carried by immutable carrier geometry, so coloured regions travel with the waveform.
        # All cards at once as rows; each card's Python scalars become a column in exactly the dtype NumPy would
        # have cast them to against that operand (``column``), so the packet is byte-identical to a per-card loop.
        n = len(self.controls.cards)
        if n:
            cards = self.controls.cards
            def column(values,like):
                return np.asarray(values,dtype=np.result_type(like.dtype,np.float32))[:,None]
            locals_ = [max(self.power,*self.bands) if card['band']=='All' else
                       self.bands[('Bass','Mids','Highs').index(card['band'])] for card in cards]
            magnitude = np.abs(carrier[:n])
            crest = np.clip(magnitude/column([max(1.5*card['height'],1e-5) for card in cards],magnitude),0.,1.)
            # Existing visible rim slots respond immediately; this eased source creates no simulation in the draw.
            data[:n,6::KNOT_ROWS,3] = np.maximum(data[:n,6::KNOT_ROWS,3],
                values['sparkle']*max(self._hit,.4*self.bands[2])*crest)
            data[:n,7::KNOT_ROWS,3] *= (1.+HIT_GLOW*self._glow*(.25+.75*crest))*(1.+PULSE_GLOW*swell[:n])
            weight = .25+.75*crest
            power = column(locals_,weight)*weight
            threshold = self.controls.colour_threshold
            share = np.clip((power-threshold)/max(1e-5,1.-threshold),0.,1.)
            share = share*share*(3.-2.*share)*values['colour']
            tint = data[:n,8::KNOT_ROWS]
            swelling = np.clip(swell[:n],0.,1.)
            share = np.maximum(np.maximum(share,tint[:,:,3]),self.controls.pulse.colour*swelling)
            # The cards' quiet/peak HSV depends only on the cards: converted once per card set, not every tick.
            cached = getattr(self,'_card_hsv',None)
            if cached is None or cached[0] is not cards:
                hsv = []
                for card in cards:
                    quiet = tuple((a+b)*.5 for a,b in zip(*card['quiet']))
                    peak = tuple((a+b)*.5 for a,b in zip(*card['peak']))
                    a,b = colorsys.rgb_to_hsv(*quiet),colorsys.rgb_to_hsv(*peak)
                    hsv.append((a[0],(b[0]-a[0]+.5)%1.-.5,a[1],b[1]-a[1],a[2],b[2]-a[2]))
                self._card_hsv = cached = (cards,hsv)
            hsv = cached[1]
            hue_a,hue_d,sat_a,sat_d,val_a,val_d = (column(field,share) for field in zip(*hsv))
            hue = (hue_a+hue_d*share)%1.
            saturation = sat_a+sat_d*share
            value = val_a+val_d*share
            # The swell deepens colour where it is: saturation rises toward 1 (never toward white), hue and value
            # keep their own logic, and a neutral colour stays neutral rather than gaining an invented hue.
            vivid = self.controls.pulse.saturation*swelling*np.clip(saturation/PULSE_GREY,0.,1.)
            saturation = saturation+(1.-saturation)*vivid
            share = np.maximum(share,vivid)
            k = (np.array((5.,3.,1.))+hue[:,:,None]*6.)%6.
            tint[:,:,:3] = value[:,:,None]*(1.-saturation[:,:,None]*np.clip(np.minimum(k,4.-k),0.,1.))
            alpha = np.clip(share/.1,0.,1.)
            tint[:,:,3] = alpha*alpha*(3.-2.*alpha)
        for index,share in enumerate(self.count_share):
            share = share*self.direction_share
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
            head_x=self.controls.scene.flow.head_x,zoom=self.zoom,direction=self.direction,
            pulse=(self._level if self._rim_share==1. else self._level*self._rim_share).astype(np.float32).tobytes())
        return self._snapshot
