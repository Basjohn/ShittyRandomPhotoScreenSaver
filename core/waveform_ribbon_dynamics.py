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
from core.waveform_ribbon_authoring import TARGETS, RIBBON_CAPACITY, clamp_sources, route_clamped
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
# Phrase-scale body energy: rises within a bar, settles within about a beat and a half. Beats articulate through the
# band sources. RELEASE THAT LETS GO (lead audit, 7 Nov; guide §13A/§13D "Soft passages must breathe"): the body's size
# was the sum of a cascade, bus intensity (1.2 s fall), this phrase energy (1.5 s), the passage follower and two drive
# stages (the authored Decay, .65 s, EACH), so a dip shorter than ~3 s never showed and the next loud moment had nothing
# to rise from. Each stage of a cascade now takes CASCADE_SHARE of the authored Attack/Decay (two stages: the visible
# release is about the Decay itself), the phrase energy settles over .6 s and the body's attack floor is per stage.
# On eight recordings back to back (chain8, PCM RMS steps of 3 dB or more): the height drive's change per dB 1.5 s after
# a step .019 -> .034 (rises) / .036 (falls), 1 s correlation with the song's RMS +.42 -> +.54; a linear response curve
# instead lost range (rejected).
PHRASE_ATTACK, PHRASE_RELEASE = .35, .6
CASCADE_SHARE = .5
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
# response as Centre Out's). Since 7 Nov night every band (Travelling Pulse, Frozen Past) carries a full release, Centre
# Out's two as well, so every band publishes RIM_EDGE_SHARE of its light; Group Wave and Whole Swell publish the level.
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
RESPONSE_TARGETS = frozenset(('height','width','bend','torsion','twist','stretch','lift','spread','depth'))
GLOBAL_TARGETS = frozenset(('height','lift','width'))
GLOBAL_ATTACK = .175   # per stage (two stages: about .35 s to the passage's size)
# Breathing (operator, 5 Nov: soft passages "look sustained instead of feeling their big changes"). Softness is how far
# the published passage sits below BREATHING_LOUD (0 at or above it), times Breathing: a soft passage releases faster,
# by up to BREATHING_REACH of Decay. A function of the current level only; loud passages keep their authored Decay. (Its
# former second half widened each drive about a learned 3 s mean of itself: removed 7 Nov, see MEMORYLESS.)
BREATHING_REACH, BREATHING_LOUD = .75, .8
# Fixed response (operator 6 Nov: "Adaptive is a very problematic approach"; guide 2A: never
# learn a level from the track). Each geometry drive's routed target is already on the fixed real-music scale (BAND_SPAN,
# PASSAGE_SPAN, ENERGY_SPAN); its drive target is gain x target^curve, eased above RESPONSE_FIXED_KNEE toward 1, the same
# for every song, and the Ranges map it to size. Nothing is remembered, so a break, a loud chorus or a quiet intro never
# re-scales what follows. Fitted to the remembered-peak gain's VISIBLE behaviour, not hotter (lead review 6 Nov: a hotter
# curve pinned Pulse Strength, flattened passages and pushed crests out of the card): on seven long recordings back to
# back (chain7) the quantiles of the adaptive output paired with the routed target's are gain x t^curve within .005-.014
# rms; height and lift (the body's size) fit 1.17-1.20 x t^.75-.82, every other drive 1.24-1.32 x t^.86-.91. Above
# RESPONSE_FIXED_KNEE the drive eases toward RESPONSE_FIXED_CEILING, as the remembered peak landed a sustained loud
# passage at .85: with an easing toward 1 the crests of loud passages topped the card on 2-6% of frames where main did
# on .8-2.9% (lead review captures, 640x560). Nothing is widened about a running mean (MEMORYLESS below).
FIXED_RESPONSE = {'height':(1.2,.75),'lift':(1.2,.82)}
FIXED_RESPONSE_DEFAULT, RESPONSE_FIXED_KNEE, RESPONSE_FIXED_CEILING = (1.12,.86), .8, .92
# MEMORYLESS (operator, 7 Nov: "Adaptivity is the enemy"; guide §2A). The fixed response is a pure function of the
# current routed target: the same music draws the same body at any time in a song, after any break, louder or softer
# passage. Removed 7 Nov after a lead audit on eight recordings played back to back (chain8): a 3 s phrase mean widened
# each drive's swings (PHRASE_DIP/PHRASE_RISE) at a learn rate that fell to 0 at every dip of the presence ratio and came
# back over 1.5 s, so it was below .5 on 39% of music ticks. The same soft->loud step drew x1.0 to x3.4 the memoryless
# rise depending on that gate (Anything: none for 30 s; Growing Pains, 1985: x2.7-3.4), and the widened swell sank back
# over 3 s as the mean caught up, so a loud passage started big and shrank: the behaviour change through a song the
# operator saw in live play. Breathing's contrast about the same mean went with it; Breathing keeps its faster release.
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
# A kick the PULSES cannot show is the same case (operator, 7 Nov night: "You can also twist, particle flair, strand and
# rotate when capped"): in Travelling Pulse and Frozen Past a kick that cannot launch its own pulse (Pulse Count full,
# or the newest too close) strengthens the newest, which shows it only below the knee of its strength (KICK_SENSE_KNEE,
# as the bend drive's headroom). How far the newest sits above that knee feeds the same Kick Accent, which also nudges
# the twist phase (KICK_TWIST radians per second per unit, bounded at KICK_ROLL_SHARE of the twist's own speed, then
# eased like the roll) and leans free strands toward the pulse (Pulse Strands x (1 + KICK_STRAND_LEAN x the eased share)).
KICK_TWIST, KICK_STRAND_LEAN = .6, 1.5

# Floor clearance (operator, 5 Nov; see WaveformDynamics._floor_room): the packet origin sits PACKET_FLOOR_HEIGHT above
# the world floor; a ribbon whose lower edge would come within TROUGH_CLEARANCE of it lifts as a whole (never reshaped),
# by up to TROUGH_LIFT_MAX, easing up over TROUGH_ATTACK and down over TROUGH_RELEASE per stage (two stages).
PACKET_FLOOR_HEIGHT, TROUGH_CLEARANCE, TROUGH_ROOM_MIN, TROUGH_LIFT_MAX = 2., .3, .4, 3.
# Floor first (operator 7 Nov: "I've noticed some of the presets clipping through the floor ... We'd rather it goes a
# bit higher when it has to than clips"; supersedes 6 Nov's "top edge first"). At a limit of 1.5 the visible lower edge
# went through the floor on 7-72% of music ticks (recorded continuous play, both card sizes); the lift is a pure offset,
# so a higher limit changes nothing but height. Floor Give (a floor that yields to the ribbon) keeps the former limit.
FLOOR_GIVE_LIFT_MAX = 1.5
TROUGH_ATTACK, TROUGH_RELEASE, TROUGH_VIEW = .15, 1.2, 32.  # TROUGH_VIEW: the fallback view without a card span
# The card's top edge (core.waveform_ribbon_view.card_span) still bounds the lift, but may take back at most
# TOP_GIVE_BACK of what the floor asks for: the crest keeps TOP_CLEARANCE below the top whenever the floor allows it, and
# otherwise both edges share the shortfall. 7 Nov sweep on recorded continuous play (chain7, 640x560 card; floor contact /
# crest above the top, visible ribbon): give-back .3 cleared the floor (P1/3/4/7 0-1.3%) but put crests above the top on
# 4-11% of ticks; 1.0 kept both at 0-3.2% logically (main, top edge first: floor 2-21%, top 0-.1%) but rendered crests
# clipped by the top on up to 6.7% of frames (main .4%); 1.5: floor .2-5%, top .2-1.1%. At a 1282x1005 card every
# preset clears both with any give-back. Presets 5 and 6 are taller than a 640x560 card holds (any setting: floor or top
# on a quarter or more of their ticks); that is authoring, not placement.
TOP_CLEARANCE = .3
TOP_GIVE_BACK = 1.5
# With the card's visible span the floor lift reads only what the camera shows, plus TROUGH_LOOKAHEAD geometric-envelope
# sigmas beyond each edge (see _trough_view), never wider than +-TROUGH_VIEW: a trough entering the view (or a swell
# deepening one on its way in) is already lifted for. 6 Nov sweep on recorded continuous play: at 2.5 sigmas the lift
# moved more and visible floor contact rose by up to .9 points (Preset 7); at 5 of the mode's own envelope sigmas (a
# Group Wave set is 3.5 carrier wavelengths wide) it equals the fixed view's on every preset at a 1282x1005 card.
TROUGH_LOOKAHEAD = 5.
# Height Shift options (operator, 5 Nov). Static Height holds every ribbon at a constant STATIC_HEIGHT_LIFT through every
# passage (the former top of the shift; unchanged when the dynamic limit rose).
STATIC_HEIGHT_LIFT = 1.5
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
# The frozen body (operator, 7 Nov: "frozen pulse does not freeze the parts it is not touching defeating the entire point
# of the freeze"). The held swell kept its gain, but the whole ribbon was still scaled by the LIVE height, width, spread,
# depth, twist and torsion drives (Preset 5: height .45-2.1, width .6-1.8), so every untouched part pumped with the music.
# In Frozen Past each cloth cell holds those drives as a swell last shaped it: a cell takes the live drive only while a
# swell rises over it (FROZEN_RISE), holds it otherwise, follows it over FROZEN_DECAY where no swell is present (fades in
# silence, never vanishes), and new cloth enters at the live drive. Leaving the mode blends the held body into the live
# one over FROZEN_BODY_RELEASE (smoothstep: never a pop). Lift (.8-1.2) stays whole-body: a per-cell offset would bend
# the shape.
FROZEN_BODY = ('height','width','spread','depth','twist','torsion')
FROZEN_BODY_RELEASE = 1.5
# DISCRETE PULSE BANDS (operator, 7 Nov night: "The pulse is a relatively small horizontal width and the full vertical
# width (except center out where it is 2x). each part stays frozen until the pulse reaches it, then it moves to match the
# current values low or high and freezes again when the pulse leaves"). The former transport summed every beat into one
# energy field and diffused it: on recorded music (Human, Preset 5) it sat above the presence threshold over 100% of the
# view at every instant, so the "pulse" was a whole-view inflation in Travelling Pulse and Frozen Past updated everything.
# Each musical event (an admitted hit, or a rise of body energy) now launches a BAND per source: Pulse Width across (a
# Gaussian of the authored width), travelling at Pulse Speed from the edge the camera sees, its strength rising with the
# release (PULSE_RISE) and fading over Pulse Fade once in view. Onsets come 7-9.5 a second on recorded music (kicks
# ~3.5), so a band per onset tiles the view: a band launches on an admitted onset only while fewer than Pulse Count
# pulses are still to come or in view (operator, 7 Nov night: "editable 1-3 or so at once") and once the newest has
# travelled BAND_SPACING Pulse Widths plus its falloff at both sides; the release in between strengthens the newest band.
# A band covers its Pulse Width (a flat core) and fades out over Pulse Falloff at each side (smoothstep): that window is
# its light and, in Frozen Past, where the cloth follows the music. Its swell is a Gaussian of the width. Bands combine by MAXIMUM,
# never by sum, so they are never a pile. Centre Out launches two bands from the centre, one each way, each a full
# pulse: splitting a release between them conserved nothing (bands are not summed) and halved Preset 4's swell. Travelling
# Pulse and Frozen Past travel as bands; Group Wave keeps the summed transport (its sets need their own pass).
BAND_SPACING, MAX_BANDS, BAND_PRESENT = 2., 24, .05
# A band holds at most one full hit's energy (BAND_STRENGTH_MAX = PULSE_HIT_GAIN): accumulating every release between
# launches drove the swell into its soft bound across the band, a flat-topped, boxy plateau (7 Nov frames, Preset 5 on
# Human 27.5 s). Its swell is BAND_GEOM_GAIN x the band: .6 is the knee measured on Human (7 Nov) for Presets 1/4/5. Above
# it the swell barely grows (a Pulse Width band meets the flow-rule bound) while band peaks sit near the soft bound (.7:
# Preset 4 within 15% of it 17% of the time, boxy tops); at .6 4.6%, and Presets 1/5 never.
BAND_STRENGTH_MAX, BAND_GEOM_GAIN = 2., .6
# Frozen Past: a cell follows the current values within FROZEN_FOLLOW while a band covers it (the band's own Gaussian,
# for bands of at least BAND_PRESENT strength) and holds them once it leaves: the body drives, Pulse Strength, the swell,
# the kick springs, the axial roll, the twist phase and the idle motion (its clock), so nothing outside a band moves but
# the history flow itself.
FROZEN_FOLLOW = .1
# What is SHOWN of the held state is the held state low-passed over the flow rule's envelope (the geometric kernel, unit
# sum): a band updates exactly its Pulse Width, but the held amplitude changes there while its neighbour stays, and shown
# raw that step drew flat-topped boxes with vertical sides (7 Nov frames, Preset 5 on Human 27.6 s).
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
    count: int = 2               # Travelling Pulse / Frozen Past: pulses still to come or in view at once (a Centre Out pair is one)
    falloff: float = 1.          # world units over which a band fades out at each side of its Pulse Width core
    deflate: float = 0.          # Frozen Past: seconds over which held cloth eases back toward the current body (0: never)

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
        if not (isinstance(self.count,int) and 1<=self.count<=3 and math.isfinite(self.falloff) and .25<=self.falloff<=12.
                and math.isfinite(self.deflate) and 0.<=self.deflate<=120.):
            raise ValueError('Waveform pulse needs count 1..3, falloff 0.25..12 and deflate 0..120')


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
    return elastic_step(position, velocity, target, elastic_terms(dt, frequency, damping))


def elastic_terms(dt, frequency, damping):
    """The step's terms that depend only on dt and the spring (shared by every ribbon on that spring this tick)."""
    omega = 2*math.pi*frequency
    wd = omega*math.sqrt(1.-damping*damping)
    decay = math.exp(-damping*omega*dt)
    return omega, wd, decay, math.sin(wd*dt), math.cos(wd*dt), damping*omega


def elastic_step(position, velocity, target, terms):
    """``elastic`` with its ``elastic_terms``: the same operations in the same order."""
    omega, wd, decay, sine, cosine, dw = terms
    offset = position-target
    x = target+decay*(offset*cosine+(velocity+dw*offset)*sine/wd)
    v = decay*(velocity*cosine-(omega*omega*offset+dw*velocity)*sine/wd)
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


def _limit_fold(values,free,limit):
    """Keep ``values`` (on PULSE_GRID spacing) from falling faster than ``limit`` per unit x, moving only the ``free``
    cells: each run of free cells is raised from its left neighbour, then lowered from its right one. (On the
    tilted values v + limit*x the rule is "never decreasing": a running maximum, then a running minimum.)"""
    ramp = limit*PULSE_DX*np.arange(values.size)
    tilted = values+ramp
    edges = np.flatnonzero(np.diff(np.concatenate(([0],free.astype(np.int8),[0]))))
    for start,end in zip(edges[::2],edges[1::2]):
        low,high = max(start-1,0),min(end+1,values.size)
        tilted[low:end] = np.maximum.accumulate(tilted[low:end])
        tilted[start:high] = np.minimum.accumulate(tilted[start:high][::-1])[::-1]
        values[start:end] = tilted[start:end]-ramp[start:end]


def _roll(rows,cells,fill):
    """Roll ``rows`` (last axis: the held cells) ``cells`` toward index 0 in place; the cells entering at the head take
    ``fill`` (one value per row, or a scalar for one row)."""
    if cells<=0:
        return
    fill = np.asarray(fill,dtype=float)
    fill = fill[...,None] if fill.ndim else fill
    if cells>=rows.shape[-1]:
        rows[...] = fill
        return
    rows[...,:-cells] = rows[...,cells:]
    rows[...,-cells:] = fill


def unit_remainder(value):
    """``value % 1.`` (``np.remainder``) of a float array, bit for bit, without its per-element divmod (the slowest
    operation of the colour pass). NumPy's remainder is ``fmod(v, 1)``, plus 1 when that is negative, and +0.0 when it
    is zero. ``fmod(v, 1)`` is ``v - trunc(v)``: the fractional part of a float is representable, so the subtraction
    is exact, and it gives +0.0 exactly where fmod gives a zero of either sign. NaN and infinity give NaN, as there."""
    part = value-np.trunc(value)
    np.add(part,1.,out=part,where=part<0.)
    return part


def sector_remainder(value):
    """``value % 6.`` (``np.remainder``) of a float array with every element in [0, 12) (or NaN), bit for bit: below 6
    it is the value itself, and from 6 on ``fmod`` is ``value - 6``, exact there (Sterbenz) and +0.0 at 6, as NumPy's
    remainder gives. The HSV sectors (offsets 1, 3, 5 plus 6 x a hue in [0, 1]) never leave that range."""
    np.subtract(value,6.,out=value,where=value>=6.)
    return value


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
    kick_accent: float = 0.           # share of a sustained kick the geometry cannot show sent to roll and sparks
    floor_give: float = 0.            # Floor Give (the floor yields): the lift keeps FLOOR_GIVE_LIFT_MAX


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


def _frozen(array):
    array.flags.writeable = False
    return array


_OWNER = _frozen(np.arange(RIBBON_CAPACITY)[:,None])   # each ribbon's index (a column)
_SEPARATION = _frozen(.65*(_OWNER-1.))                # the bundle's rest separation in depth
_HSV_OFFSETS = _frozen(np.array((5.,3.,1.)))           # HSV -> RGB sector offsets


class _PacketTerms:
    """The snapshot's terms that depend only on one history packet (a new packet arrives at the knot rate, ~6 Hz, the
    snapshot runs every logical tick): computed once per packet by exactly the expressions the snapshot evaluated, so
    every published value is unchanged. The arrays are read only; the snapshot always derives new arrays from them."""

    __slots__ = ('u','carrier','depth_wave','depth_sway','idle_y','idle_z','idle_twist','twist','torsion_a','torsion_b',
                 'windows','_crest')

    def __init__(self, raw, base):
        rows = base[:,4::KNOT_ROWS]
        u = rows[:,:,0]+raw.world_origin[0]
        self.u = u                                                            # cloth coordinate
        self.carrier = rows[:,:,1]+raw.world_origin[1]-2.
        self.depth_wave = rows[:,:,2]+raw.world_origin[2]-_SEPARATION
        self.depth_sway = np.cos(.65*u+_OWNER)
        self.idle_y,self.idle_z,self.idle_twist = .6*u,.4*u,.3*u             # the idle motion's spatial phases
        origin_twist = (base[:,1,0,None]+math.pi)%(2*math.pi)-math.pi
        self.twist = base[:,5::KNOT_ROWS,1]+origin_twist
        self.torsion_a,self.torsion_b = np.sin(.45*u+_OWNER),np.sin(.7*u-_OWNER)
        for name in ('u','carrier','depth_wave','depth_sway','idle_y','idle_z','idle_twist','twist','torsion_a','torsion_b'):
            getattr(self,name).flags.writeable = False
        self._crest = None
        # The surge's history windows: ribbons sharing one (count, start, capacity) run, in first-member order, as
        # (count, member ribbons, flat indices of their knots in a (ribbons, slots) field, oldest knot first).
        windows = {}
        for index,path in enumerate(base):
            count,start,capacity = int(path[0,0]),int(path[1,1]),int(path[1,2])
            if count>=4:
                windows.setdefault((count,start,capacity),[]).append(index)
        slots = rows.shape[1]
        self.windows = tuple((count,_frozen(np.asarray(members)),
                              _frozen(np.asarray(members)[:,None]*slots+(start+np.arange(count))%capacity))
                             for (count,start,capacity),members in windows.items())

    def crest(self, cards, n):
        """(crest, .25+.75*crest) of the first ``n`` carriers against the cards' heights, per card set."""
        cached = self._crest
        if cached is None or cached[0] is not cards or cached[1] != n:
            magnitude = np.abs(self.carrier[:n])
            heights = np.asarray([max(1.5*card['height'],1e-5) for card in cards],
                                 dtype=np.result_type(magnitude.dtype,np.float32))[:,None]
            crest = np.clip(magnitude/heights,0.,1.)
            weight = .25+.75*crest
            crest.flags.writeable = weight.flags.writeable = False
            cached = self._crest = (cards,n,crest,weight)
        return cached[2],cached[3]


class WaveformDynamics:
    def __init__(self, controls: HybridControls):
        self.controls = controls
        self.ring = RibbonRing(RIBBON_CAPACITY, colours=[(*c['quiet'][0],1.) for c in controls.cards],
                               edge_colours=[(*c['quiet'][1],1.) for c in controls.cards],period=.5)
        self.time = self.travel = self.angle = self.angular_speed = self.twist_phase = self._hit = 0.
        self._kick_impulse = self._kick_stage = self.kick_sense = 0.   # Kick Accent: held share, eased stages
        self._pulse_lack = 0.     # how far a kick is beyond what the pulses can show (Kick Accent; 0 while one can launch)
        self._kick_twist = 0.     # Kick Accent's eased twist nudge (radians per second)
        self.phase = controls.scene.flow.phase
        self.bands, self.power = (0.,0.,0.),0.
        self.passage = self.phrase = 0.
        self.zoom, self._sustain = 1., 0.
        self._glow = 0.  # swell-shaped light response to hits (rise HIT_GLOW_RISE, settle HIT_GLOW_SETTLE)
        self._pulse = np.zeros((2,PULSE_GRID.size))  # travelling toward -x, toward +x
        self._fresh = np.zeros((2,PULSE_GRID.size))  # the same transport with a short fade: recently launched swells
        self._pulse_pending = 0.
        self._source_shapes = {}  # (origin, sigma) -> injected Gaussian on PULSE_GRID (see _source_shape)
        self._view_world = None  # (low, high) world x of the scene axis the framed camera shows (capture-supplied)
        self._view_top = None    # world y of the card's top edge above the scene axis (capture-supplied), or None
        self._seen = (None,None)  # cached (key, per-direction seen weights) for the age-once-seen fade
        self._rim_share = 1.      # share of the appearance level published for Pulse Rim (RIM_EDGE_SHARE for bands)
        self._trough_stage,self._trough_lift,self._trough_time = np.zeros((RIBBON_CAPACITY,1)),np.zeros((RIBBON_CAPACITY,1)),None
        self._tilt_lead,self._tilt_time = np.zeros((RIBBON_CAPACITY,1)),None
        self._frozen_swell = None   # Frozen Past: (live band envelope under presence, held swell) for the response tools
        self._frozen_body_on = False   # the held body is applied (in Frozen Past, and while blending out of it)
        self._frozen_body_share = 1.   # 1 in Frozen Past; falls to 0 over FROZEN_BODY_RELEASE after leaving it
        self._bands = []               # discrete pulse bands: [position, direction sign, strength, target, age]
        self._band_presence = np.zeros(PULSE_GRID.size)   # where a band of BAND_PRESENT strength covers (0..1)
        self._band_light = np.zeros(PULSE_GRID.size)      # the bands' light: each band's Pulse Width, by its strength
        self._angle_total = self._twist_total = 0.   # unwrapped roll and twist phase (Frozen Past holds them per cell)
        self._frozen_state = None      # Frozen Past per-cell scalars (rows: _frozen_rows) on the cloth-fixed grid
        self._frozen_geom = np.zeros(PULSE_GRID.size)     # Frozen Past per-cell swell (geometric units), cloth-fixed
        self._frozen_geom_shown = np.zeros(PULSE_GRID.size)   # ... resampled on PULSE_GRID for publication
        # The held grid is fixed to the cloth: cell k sits at scene x PULSE_GRID[k] - _frozen_shift (0 <= shift < PULSE_DX);
        # whole cells roll toward -x as the history flows (_frozen_rolled counts them), so nothing is re-interpolated.
        self._frozen_shift = 0.
        self._frozen_rolled = 0
        self._frozen_gain_cells = None   # the shown final gain on the held cells (blended into the live gain while leaving)
        self._frozen_offset_rolled = 0
        self._frozen_surge = None        # Frozen Past: surge displacement (PULSE_SURGE x Pulse Strength x drift) held per cell
        self._frozen_surge_rolled = 0
        self._frozen_gain = None       # Frozen Past per-cell final gain (after the flow-rule bound), and as shown
        self._frozen_gain_shown = None
        self._frozen_offset = None     # Frozen Past per-ribbon, per-cell vertical offset (lift + floor lift)
        self._frozen_offset_time = None
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
        self.count_share = [1. if index < controls.count else 0. for index in range(RIBBON_CAPACITY)]
        self.direction = controls.scene.flow.direction
        self._direction_phase = self.direction_share = 1.   # linear fade phase and its smoothstep share
        self._primed = 0
        self._next_knot = 1./controls.scene.flow.knot_hz
        self._snapshot = None
        self._base_packet = self._base_array = None
        self._packet_terms = None   # _PacketTerms of _base_packet
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
        self.passage = follower(self.passage,power,dt,c.attack,CASCADE_SHARE*c.release)
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
        # Breathing's softness is a function of the published passage (the current level on the fixed scale): a soft
        # passage lets go faster. Nothing here remembers anything.
        softness = hold*unit((BREATHING_LOUD-self.passage)/BREATHING_LOUD)
        geometry_release = CASCADE_SHARE*c.release*(1.-BREATHING_REACH*softness)   # per stage of two
        clamped = clamp_sources(sources)   # once for every target (route clamped them per target)
        for key in TARGETS:
            target = route_clamped(c.routing[key],clamped,passage=gate)
            if key in RESPONSE_TARGETS:
                # Fixed response: gain x target^curve on the real-music scale, eased under the ceiling. A pure function
                # of now: no mean, no peak, no learn rate (see MEMORYLESS above).
                target = fixed_response(target,key)
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
            lack = max(unit((self.drive['bend']-KICK_SENSE_KNEE)/(1.-KICK_SENSE_KNEE)),self._pulse_lack)*unit(c.kick_accent)
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
        self._advance_springs(dt,bands,impulses)
        target_speed = self._value('rotation') if c.rotation_enabled else 0.
        self.angular_speed = follower(self.angular_speed,target_speed,dt,c.rotation_attack,c.rotation_release)
        roll = self.angular_speed+(math.copysign(KICK_ROLL*self.kick_sense,target_speed) if c.rotation_enabled else 0.)
        self.angle = math.remainder(self.angle+math.radians(roll)*dt,2*math.pi)
        self._angle_total += math.radians(roll)*dt
        low,high = c.twist_speed
        twist_speed = low+(high-low)*self.drive['twist']
        if self._kick_stage>0. or self._kick_twist>0.:
            # Kick Accent's twist nudge, as the roll's: a second eased stage toward the share, bounded by the twist's own
            # speed (bounded first, then eased, so the twist's speed never steps), in the twist's own direction.
            goal = min(KICK_TWIST*self._kick_stage,KICK_ROLL_SHARE*abs(twist_speed))
            self._kick_twist = follower(self._kick_twist,goal,dt,KICK_SENSE_ATTACK,KICK_SENSE_RELEASE)
            if self._kick_twist<1e-9 and not goal:
                self._kick_twist = 0.
            twist_speed += math.copysign(self._kick_twist,twist_speed)
        self.twist_phase = math.remainder(self.twist_phase+twist_speed*dt,2*math.pi)
        self._twist_total += twist_speed*dt
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
                                                swell=self.pulse_focus,
                                                gather=c.pulse.strands*(1.+KICK_STRAND_LEAN*self._kick_stage))
            self._snapshot=replace(self._snapshot,strands=payload,strand_origin=self._strand_cohorts.origin)
        if self.direction_share < 1.:
            self._snapshot = self._direction_faded(self._snapshot,self.direction_share)
        return self._snapshot

    def _advance_springs(self,dt,bands,impulses):
        """Each ribbon's bend/torsion/depth springs. A kick is delivered as a short force (IMPULSE_SPREAD), not an
        instantaneous velocity jump: the same momentum, but the sway/torsion velocity stays continuous (operator,
        5 Nov: the lattice twitched left and right in every mode on each hit). The step's dt-and-spring terms are
        shared by every ribbon on that spring (elastic_terms; the same operations as ``elastic`` per ribbon)."""
        c = self.controls
        springs = tuple(elastic_terms(dt,frequency,c.damping) for frequency in self._elastic_frequencies)
        spread = 1.-math.exp(-dt/IMPULSE_SPREAD)
        targets = (self.drive['bend'],self.drive['torsion'],self.drive['depth'])
        for owner,card in enumerate(c.cards):
            support = 1. if card['band']=='All' else bands[('Bass','Mids','Highs').index(card['band'])]
            push,velocity,spring = self._push[owner],self.velocity[owner],self.spring[owner]
            for index,target in enumerate(targets):
                push[index] += support*impulses[index]*c.impulse*self._impulse_scales[index]
                delivered = push[index]*spread
                push[index] -= delivered
                velocity[index] += delivered
                spring[index],velocity[index] = elastic_step(spring[index],velocity[index],target*support,
                                                             springs[index])

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
        self._rim_share = RIM_EDGE_SHARE if p.mode in ('Travelling Pulse','Frozen Past') else 1.
        shift = p.speed*dt
        blur = min(.24,PULSE_DIFFUSION*dt/(PULSE_DX*PULSE_DX))
        fades = (p.fade,min(p.fade,FRESH_FADE))
        decays = tuple(math.exp(-dt/fade) for fade in fades)
        if seen is not None:
            decays = tuple(np.exp((-dt/fade)*seen) for fade in fades)  # per direction: ages only once seen
        travelling = p.mode!='Whole Swell'
        if p.mode not in ('Travelling Pulse','Frozen Past'):
            self._pulse_lack = 0.
        if p.mode in ('Travelling Pulse','Frozen Past'):
            self._advance_bands(dt,release,p,sources,sigma,hit>0.)
        else:
            self._carry_fields(decays,seen,sources,sigma,shift,blur,release,travelling)
        # Whole Swell: nothing travels; one level rises with the shared release and settles gently.
        settle = min(WHOLE_SETTLE[1],max(WHOLE_SETTLE[0],.25*p.fade))
        self._whole = self._whole*math.exp(-dt/settle)+(0. if travelling else release)
        self._whole_fresh = self._whole_fresh*math.exp(-dt/min(settle,FRESH_FADE))+(0. if travelling else release)
        self._advance_frozen(dt,p.mode=='Frozen Past',self._value('bend'))
        self._publish_fields(dt)
        return release

    def _carry_fields(self,decays,seen,sources,sigma,shift,blur,release,travelling):
        """Carry, spread and fade both pulse fields (long fade and fresh) in both directions, then inject the
        release at the sources. The shifted grid is shared by both fields of a direction and each source's Gaussian
        is reused until its origin or width changes (_source_shape): the same values as recomputing them."""
        shifted = [None,None]   # PULSE_GRID-sign*shift per direction, shared by both fields
        for fields,decay in zip((self._pulse,self._fresh),decays):
            for index,sign in enumerate((-1.,1.)):
                field = fields[index]
                if not field.any() and not (travelling and release):
                    continue
                if shift:
                    if shifted[index] is None:
                        shifted[index] = PULSE_GRID-sign*shift
                    field[:] = np.interp(shifted[index],PULSE_GRID,field,left=0.,right=0.)
                if blur:
                    field[1:-1] += blur*(field[:-2]-2.*field[1:-1]+field[2:])
                field *= decay if seen is None else decay[index]
                for origin,direction in sources:
                    if travelling and direction==sign and release:
                        field += release/len(sources)*self._source_shape(origin,sigma)
                field[field<1e-9] = 0.  # after injection, so a zero-length step changes nothing

    def _advance_bands(self,dt,release,p,sources,sigma,onset=False):
        """Launch, strengthen, carry and fade the discrete pulse bands; publish them (maximum, never a sum) into the long
        and fresh fields and the band presence (see DISCRETE PULSE BANDS)."""
        view = self._view_world
        if view is not None and self.direction < 0.:
            view = (-view[1],-view[0])
        reach = .5*p.width+p.falloff   # half a band's window: its Pulse Width core and the falloff at one side
        low,high = view if view is not None else (PULSE_GRID[0],PULSE_GRID[-1])

        def live_pulses():
            """Bands still to come or in view: present, and not yet past the far edge (a Centre Out pair is one pulse)."""
            live = [band for band in self._bands if band[3] >= BAND_PRESENT
                    and (band[0]-reach <= high if band[1] > 0. else band[0]+reach >= low)]
            return live,min((band[4] for band in live),default=None)

        if release > 0.:
            live,age = live_pulses()
            newest = [band for band in live if band[4] == age]
            # A band launches on a musical onset while fewer than Pulse Count pulses are live, once the newest has
            # travelled BAND_SPACING widths plus its falloff at both sides; the release in between (the rest of a hit,
            # rises of body energy) strengthens the newest band.
            if len({band[4] for band in live}) < p.count and (
                    not newest or (onset and age*p.speed >= BAND_SPACING*p.width+2.*p.falloff)):
                for origin,sign in sources:
                    self._bands.append([origin,sign,0.,min(BAND_STRENGTH_MAX,release),0.])
            else:
                for band in newest:
                    band[3] = min(BAND_STRENGTH_MAX,band[3]+release)
        # The next kick's case for Kick Accent: it cannot launch its own pulse (every place taken, or the newest too
        # close), so it strengthens the newest, which shows it only below the knee of its strength (as the bend drive's
        # headroom: KICK_SENSE_KNEE).
        live,age = live_pulses()
        launch = len({band[4] for band in live}) < p.count and (
            age is None or age*p.speed >= BAND_SPACING*p.width+2.*p.falloff)
        strength = max((band[3] for band in live if band[4] == age),default=0.)
        self._pulse_lack = 0. if launch else unit((strength/BAND_STRENGTH_MAX-KICK_SENSE_KNEE)/(1.-KICK_SENSE_KNEE))
        rise = 1.-math.exp(-dt/PULSE_RISE)
        fade = math.exp(-dt/max(p.fade,1e-5))
        kept = []
        for band in self._bands:
            band[0] += band[1]*p.speed*dt
            band[4] += dt
            band[2] += (band[3]-band[2])*rise
            # An edge-born band ages only once seen (it is born just beyond the edge); a Centre Out band from its birth.
            if view is None or p.direction=='Centre Out' or view[0]-sigma <= band[0] <= view[1]+sigma:
                band[2] *= fade
                band[3] *= fade
            if abs(band[0]) <= PULSE_GRID[-1]+4.*sigma and band[3] > 1e-4:
                kept.append(band)
        self._bands = kept[-MAX_BANDS:]
        long = np.zeros((2,PULSE_GRID.size))
        fresh = np.zeros((2,PULSE_GRID.size))
        presence = np.zeros(PULSE_GRID.size)
        light = np.zeros(PULSE_GRID.size)
        for position,sign,strength,target,age in self._bands:
            window = np.exp(-.5*((PULSE_GRID-position)/sigma)**2)
            index = 0 if sign < 0. else 1
            np.maximum(long[index],strength*window,out=long[index])
            np.maximum(fresh[index],strength*math.exp(-age/FRESH_FADE)*window,out=fresh[index])
            edge = np.clip((reach-np.abs(PULSE_GRID-position))/p.falloff,0.,1.)   # core, then Pulse Falloff
            edge = edge*edge*(3.-2.*edge)
            np.maximum(light,(1.-math.exp(-strength/APP_SCALE))*edge,out=light)   # the band itself: Pulse Width wide
            if target >= BAND_PRESENT:
                np.maximum(presence,edge,out=presence)
        long[long<1e-9] = 0.
        fresh[fresh<1e-9] = 0.
        self._pulse[:] = long
        self._fresh[:] = fresh
        self._band_presence = presence
        self._band_light = light

    def _source_shape(self,origin,sigma):
        """The injected Gaussian of a source on PULSE_GRID; recomputed only when its origin or width changes."""
        key = (origin,sigma)
        shape = self._source_shapes.get(key)
        if shape is None:
            if len(self._source_shapes) >= 4:
                self._source_shapes.clear()
            shape = self._source_shapes[key] = np.exp(-.5*((PULSE_GRID-origin)/sigma)**2)
            shape.flags.writeable = False
        return shape

    def _view_sources(self,p):
        """Pulse sources and, when the camera's span is known and Travelling Pulse travels in from an edge, the
        per-direction seen weights (0 beyond the entry edge, 1 inside it; see VIEW_MARGIN). Otherwise (sources, None)."""
        if self._view_world is None or p.mode not in ('Travelling Pulse','Frozen Past') or p.direction=='Centre Out':
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

    def _frozen_rows(self):
        """The live per-cell scalars Frozen Past holds: the body drives and Pulse Strength (drive units), each ribbon's
        two shape springs (m, h), the logical clock, the unwrapped roll and twist phase, and the passage (idle motion)."""
        springs = (3.*np.tanh(np.asarray(self.spring)/3.))[:,1:]
        return np.concatenate((
            [unit(self.drive[key]) for key in FROZEN_BODY], [unit(self.drive['bend'])], springs.reshape(-1),
            [self.time,self._angle_total,self._twist_total,self.passage]))[:,None]

    def _frozen_advect(self,flow):
        """Move the cloth-fixed held grid with the history by ``flow``: whole cells roll toward -x (exact), the sub-cell
        remainder only moves where the grid sits. Returns the cells rolled."""
        self._frozen_shift += flow
        cells = int(self._frozen_shift//PULSE_DX)
        self._frozen_shift -= cells*PULSE_DX
        self._frozen_rolled += cells
        return cells

    def _frozen_cells(self):
        """Scene x of each held cell."""
        return PULSE_GRID-self._frozen_shift

    def _frozen_follow(self,dt,presence):
        """Per held cell, the share of the way to the live value this tick: FROZEN_FOLLOW under a band (``presence``),
        and with Freeze Deflate everywhere over that many seconds (0: held cloth never moves outside a band)."""
        follow = (1.-math.exp(-dt/FROZEN_FOLLOW))*presence
        deflate = self.controls.pulse.deflate
        if deflate>0.:
            settle = 1.-math.exp(-dt/deflate)
            follow = follow+(1.-follow)*settle
        return follow

    def _advance_frozen(self,dt,active,strength=0.):
        """Frozen Past (operator, 7 Nov night): each cell stays frozen until a pulse band reaches it, then follows the
        current values (low or high) and freezes again when the band leaves. The held grid is fixed to the cloth (whole
        cells roll with the history, never re-interpolated: a held shape never melts) and new cloth enters at the
        current values. Leaving the mode blends the held state into the live one over FROZEN_BODY_RELEASE (smoothstep:
        never a pop), the held grid still travelling with the cloth."""
        flow = self.controls.scene.flow.speed*dt
        live = self._frozen_rows()
        kernel,_ = self._blur_kernel(GEOM_WAVES)
        fresh = self._pulse[0]+self._pulse[1]
        if kernel.size==1:
            wide = fresh*kernel[0]
        else:
            offset = (kernel.size-1)//2
            wide = np.convolve(fresh,kernel)[offset:offset+fresh.size]
        geom_live = soft(BAND_GEOM_GAIN*wide)
        if not active:
            if self._frozen_body_on:
                self._frozen_body_share = max(0.,self._frozen_body_share-dt/FROZEN_BODY_RELEASE)
                if not self._frozen_body_share:
                    self._frozen_body_on = False
                    self._frozen_state = self._frozen_gain = self._frozen_gain_shown = self._frozen_offset = None
                    self._frozen_gain_cells = self._frozen_offset_time = self._frozen_surge = None
                    self._frozen_shift,self._frozen_rolled,self._frozen_offset_rolled = 0.,0,0
                    self._frozen_surge_rolled = 0
                elif self._frozen_state is not None:
                    cells = self._frozen_advect(flow)
                    _roll(self._frozen_state,cells,live[:,0])
                    share = self._frozen_body_share
                    share = share*share*(3.-2.*share)
                    live_gain = self._bounded_gain(.7*self._value('bend')*self._geom)
                    if self._frozen_gain is not None:
                        _roll(self._frozen_gain,cells,live_gain[-1])
                        here = np.interp(self._frozen_cells(),PULSE_GRID,live_gain)
                        self._frozen_gain_cells = here+(self._frozen_gain-here)*share
                        self._frozen_gain_shown = np.interp(PULSE_GRID,self._frozen_cells(),self._frozen_gain_cells)
            return
        state = self._frozen_state
        if not self._frozen_body_on or state is None or state.shape[0]!=live.shape[0]:
            state = self._frozen_state = np.repeat(live,PULSE_GRID.size,axis=1)
            self._frozen_geom = geom_live.copy()
            self._frozen_gain = self._frozen_surge = None
            self._frozen_shift,self._frozen_rolled,self._frozen_offset_rolled = 0.,0,0
            self._frozen_surge_rolled = 0
            self._frozen_body_on = True
        elif self._frozen_body_share<1.:
            # Back while still blending out: the cloth holds the state it shows now, so nothing jumps.
            share = self._frozen_body_share
            share = share*share*(3.-2.*share)
            state[:] = live+(state-live)*share
            self._frozen_geom[:] = geom_live+(self._frozen_geom-geom_live)*share
        self._frozen_body_share = 1.
        cells = self._frozen_advect(flow)
        _roll(state,cells,live[:,0])                       # new cloth enters at the live state
        _roll(self._frozen_geom,cells,geom_live[-1])
        where = self._frozen_cells()
        follow = self._frozen_follow(dt,np.interp(where,PULSE_GRID,self._band_presence))
        state += (live-state)*follow
        self._frozen_geom += (np.interp(where,PULSE_GRID,geom_live)-self._frozen_geom)*follow
        self._frozen_geom_shown = np.interp(PULSE_GRID,where,self._frozen_geom)
        self._frozen_swell = (geom_live*self._band_presence,self._frozen_geom_shown)
        # The final gain after the flow-rule bound: one share bounds the whole field, so a band anywhere would rescale
        # every held swell; each cell holds the gain it had when its band left.
        live_gain = self._bounded_gain(.7*self._value('bend')*geom_live)
        here = np.interp(where,PULSE_GRID,live_gain)
        if self._frozen_gain is None:
            self._frozen_gain = here.copy()
        else:
            _roll(self._frozen_gain,cells,live_gain[-1])
            self._frozen_gain += (here-self._frozen_gain)*follow
        # Shown as held: smoothing it (the geometric kernel, +-3 sigma) carried every band's update into the gaps
        # between bands (7 Nov: Preset 5 moved as much outside its bands as inside). Pulse Falloff softens the edges.
        self._frozen_gain_cells = self._frozen_gain
        self._frozen_gain_shown = np.interp(PULSE_GRID,where,self._frozen_gain)

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
            # The light is the bands (the pulse is where it is); the geometry is the held swell, which follows the live
            # swell only under a band (_advance_frozen); the surge moves only under a band too (below).
            self._level = self._band_light
            self._focus = self._band_light
            self._geom = self._frozen_geom_shown
            self._frozen_swell = (soft(BAND_GEOM_GAIN*broad(travelling))*self._band_presence,self._frozen_geom_shown)
            drift_target = (soft(BAND_GEOM_GAIN*broad(self._pulse[1]))-soft(BAND_GEOM_GAIN*broad(self._pulse[0])))\
                *self._band_presence
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
                lead = -sign*sigma_g*uniform_gradient(wide,PULSE_DX)/(wide+1e-6)
                weighted = wide*(1.+GROUP_LEAD*np.tanh(lead))
                total += weighted
                drift_target += sign*GROUP_SURGE*soft(weighted)
            self._geom = soft(total)
        else:
            # Travelling Pulse: each band swells the waveform where it is, for its whole journey (fading with Pulse
            # Fade), and its light is the band itself. The bands never pile (they combine by maximum), so the calmer
            # waveform between them stays calm (5 Nov: the summed field was a uniform inflation, median/max .98).
            self._level = self._band_light
            self._focus = self._band_light
            self._geom = soft(BAND_GEOM_GAIN*broad(self._pulse[0]+self._pulse[1]))
            drift_target = soft(BAND_GEOM_GAIN*broad(self._pulse[1]))-soft(BAND_GEOM_GAIN*broad(self._pulse[0]))
        # The surge eases (two cascaded followers, SURGE_EASE each) so the cloth's sideways velocity is continuous; the
        # old clipped step had piecewise-constant velocity, a sideways jolt at every change (operator, 5 Nov: lattice
        # twitching left and right). SURGE_RATE still bounds the change per second.
        ease = 1.-math.exp(-dt/SURGE_EASE) if dt>0. else 0.
        if p.mode=='Frozen Past':
            ease = ease*self._band_presence   # outside a band the surge holds where it is
        self._drift_stage = self._drift_stage+(drift_target-self._drift_stage)*ease
        step = SURGE_RATE*dt
        self._drift = self._drift+np.clip((self._drift_stage-self._drift)*ease,-step,step)
        if self._frozen_body_on and self._frozen_state is not None:
            self._hold_frozen_surge(dt,p.mode=='Frozen Past')

    def _hold_frozen_surge(self,dt,follow):
        """Frozen Past: the surge displacement held on the cloth cells, following the live one only under a band, so a
        stretch of cloth a band slid stays slid as it flows (rolled with the cells; while leaving the mode it only rolls)."""
        where = self._frozen_cells()
        live = np.interp(where,PULSE_GRID,PULSE_SURGE*self._value('bend')*self._drift)
        held = self._frozen_surge
        if held is None:
            held = live.copy()
        else:
            _roll(held,self._frozen_rolled-self._frozen_surge_rolled,live[-1])
            if follow:
                presence = np.interp(where,PULSE_GRID,self._band_presence)
                follow = self._frozen_follow(dt,presence)
                held += (live-held)*follow
                # The fold guard, locally: where a band changed the held surge, its compression stays within
                # SURGE_MAX_COMPRESSION, so _surge's per-ribbon guard (a whole-ribbon scale) never moves held cloth.
                _limit_fold(held,follow>0.,.98*SURGE_MAX_COMPRESSION)
        self._frozen_surge,self._frozen_surge_rolled = held,self._frozen_rolled

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
        """Gain envelope on the pulse grid, bounded at the owner by the flow rule (see GEOM_SLOPE/GEOM_CURVE). Frozen Past
        returns the gain held on each cell (_advance_frozen), which follows the live bounded gain only under a band."""
        if self._frozen_body_on and self._frozen_gain_shown is not None:
            return self._frozen_gain_shown
        return self._bounded_gain(.7*strength*self._geom)

    def _bounded_gain(self,swell):
        """1 + share x swell, with the largest share the flow rule admits (rising at most GEOM_SHARE_RISE per second)."""
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

    def _surge(self,data,x,y,z,amount,drift=None):
        """Slide each knot ALONG its own curve by the signed swell: the body is resampled at the shifted positions
        (cubic Hermite through the unsurged knots), so the curve itself never changes, only its cloth moves.

        Ribbons sharing one history window (count, start, capacity) are resampled together as rows: the same
        element-wise arithmetic as one ribbon at a time (``row_gradient`` reproduces ``np.gradient``), so the
        published packet is byte-identical, at a fraction of the per-ribbon NumPy dispatch (5 Nov profile)."""
        drift = self.pulse_drift(x)*amount if drift is None else drift
        if not np.any(drift):
            return x,y,z
        x,y,z = x.copy(),y.copy(),z.copy()
        # ``data`` is this snapshot's copy of the current packet, so its windows are the packet's (headers unchanged).
        windows = self._packet_terms.windows
        # Every gather and scatter below goes through flat indices (``take``/``put``): the same elements as the former
        # (rows, order) and (line, cell) fancy indexing, without its broadcast index machinery.
        for count,rows,flat in windows:
            xs,ds = x.take(flat),drift.take(flat)
            moving = ds.any(axis=1)
            if not moving.any():
                continue
            rows,flat,xs,ds = rows[moving],flat[moving],xs[moving],ds[moving]
            line = np.arange(len(rows))[:,None]*count   # each row's first flat index in the (rows, count) gathers
            # The ends never slide: a smooth taper of fixed length (a taper sized from the current drift changed length
            # every tick and jittered the knots near the head; 5 Nov per-tick acceleration probe).
            edge = np.clip(np.minimum(xs-xs[:,:1],xs[:,-1:]-xs)/SURGE_TAPER,0.,1.)
            ds = ds*(edge*edge*(3.-2.*edge))
            squeeze = (np.diff(ds,axis=1)/np.diff(xs,axis=1)).min(axis=1,keepdims=True)
            limited = squeeze < -SURGE_MAX_COMPRESSION
            bound = np.where(limited,SURGE_MAX_COMPRESSION/np.where(limited,-squeeze,1.),1.)
            # The compression bound scales a whole ribbon's surge: it may tighten at once but relaxes at most
            # SURGE_BOUND_RISE per second, so a constraint letting go never jolts the whole ribbon sideways.
            for row,member in enumerate(rows):
                previous,when = self._surge_bound.get(int(member),(1.,None))
                if when is not None and self.time>=when:
                    bound[row,0] = min(bound[row,0],previous+SURGE_BOUND_RISE*(self.time-when))
                self._surge_bound[int(member)] = (float(bound[row,0]),self.time)
            ds = ds*bound
            target = xs+ds
            cell = np.stack([np.searchsorted(row,goal) for row,goal in zip(xs,target)])
            cell = np.clip(cell-1,0,count-2)
            at = line+cell        # flat (row, cell) and (row, cell + 1) indices
            after = at+1
            left,right = xs.take(at),xs.take(after)
            h = right-left
            t = (target-left)/h
            cube = t**3
            h00,h10,h01,h11 = 2*cube-3*t*t+1,cube-2*t*t+t,-2*cube+3*t*t,cube-t*t
            # y and z resampled together as one (2, rows, knots) stack: the same element-wise arithmetic in one pass.
            vs = np.stack((y.take(flat),z.take(flat)))
            slope = apply_row_gradient(vs,row_gradient_coefficients(xs))
            values,slopes = vs.reshape(2,-1),slope.reshape(2,-1)
            resampled = (h00*values.take(at,axis=1)+h10*h*slopes.take(at,axis=1)+h01*values.take(after,axis=1)
                         +h11*h*slopes.take(after,axis=1))
            np.put(y,flat,resampled[0])
            np.put(z,flat,resampled[1])
            np.put(x,flat,target)
        return x,y,z

    def _floor_room(self,height,hang,room,visible,static=None,soft=None,headroom=None):
        """Per ribbon: how far to lift the whole ribbon so its lower edge stays TROUGH_CLEARANCE above the floor (see
        snapshot). Two cascaded followers (TROUGH_ATTACK up, TROUGH_RELEASE down, on the logical clock), so the lift's
        velocity is continuous: a one-stage follower jumped on every new trough, which was itself a twitch.
        Floor first (operator 7 Nov): with the card's top supplied (``headroom``: room above the rest line for the
        published crest ``soft`` plus its sheet hang, TOP_CLEARANCE below the edge) the top may lower the lift only by
        the clearance, so the lower edge at most grazes the floor and a crest leaves the card only when the floor needs
        it. A lift the top lowers eases down at TROUGH_ATTACK, as fast as it rose. Floor Give keeps FLOOR_GIVE_LIFT_MAX."""
        capped = None
        if static is None:
            limit = FLOOR_GIVE_LIFT_MAX if self.controls.floor_give>0. else TROUGH_LIFT_MAX
            sinking = np.where(visible,hang-height,-np.inf)                 # depth of the lower edge below rest
            target = np.clip(sinking.max(axis=1,keepdims=True)-room,0.,limit)
            if headroom is not None:
                top = np.maximum(headroom-np.where(visible,soft+hang,-np.inf).max(axis=1,keepdims=True),0.)
                floor_first = np.maximum(top,target-TOP_GIVE_BACK)
                capped = floor_first<target
                target = np.minimum(target,floor_first)
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

    def _frozen_vertical(self,x,live):
        """Frozen Past: each ribbon's vertical offset (lift + floor lift) held per cell, following the live offset only
        under a band (the lift moved the whole ribbon at once); on the cloth-fixed held cells, updated once per logical
        time."""
        live = np.broadcast_to(live,x.shape)
        where = self._frozen_cells()
        grid_live = np.stack([np.interp(where,x[ribbon],live[ribbon]) for ribbon in range(x.shape[0])])
        held = self._frozen_offset
        if held is None or held.shape != grid_live.shape:
            held = grid_live.copy()
        elif self._frozen_offset_time is not None and self.time > self._frozen_offset_time:
            dt = self.time-self._frozen_offset_time
            _roll(held,self._frozen_rolled-self._frozen_offset_rolled,grid_live[:,-1])
            presence = np.interp(where,PULSE_GRID,self._band_presence)
            held += (grid_live-held)*self._frozen_follow(dt,presence)
        self._frozen_offset,self._frozen_offset_time,self._frozen_offset_rolled = held,self.time,self._frozen_rolled
        shown = np.stack([np.interp(x[ribbon],where,held[ribbon]) for ribbon in range(x.shape[0])])
        share = self._frozen_body_share
        if share >= 1.:
            return shown
        blend = share*share*(3.-2.*share)
        return live+(shown-live)*blend

    def _height_shift(self,height,hang,room,x,soft=None,headroom=None):
        """Per ribbon (and, with Tilt Shift, per knot) vertical offset that keeps lower edges off the floor, never
        lifting a crest through the card's top edge (``headroom``: see _floor_room)."""
        static = STATIC_HEIGHT_LIFT if self.controls.height_mode=='Static Height' else None
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

    def _fade_ribbons(self,data,rows):
        """Each ribbon's header colours and its count/direction fade (light, width, transverse offsets), all ribbons
        at once: each Python share is cast to the packet's float32 before it multiplies (NumPy's scalar rule), so a
        float32 column reproduces the former per-ribbon loop exactly."""
        shares = np.asarray([share*self.direction_share for share in self.count_share],np.float32)
        cached = getattr(self,'_quiet_header',None)   # the cards' quiet header colours, per card set
        if cached is None or cached[0] is not self.controls.cards:
            cached = self._quiet_header = (self.controls.cards,
                np.asarray([card['quiet'][0] for card in self.controls.cards],np.float32),
                np.asarray([card['quiet'][1] for card in self.controls.cards],np.float32))
        data[:,2,:3] = cached[1]
        data[:,3,:3] = cached[2]
        rows[:,:,1:3] *= shares[:,None,None]
        rows[:,:,3] = np.maximum(1e-5,rows[:,:,3]*shares[:,None])
        data[:,2:4,3] *= shares[:,None]
        data[:,7::KNOT_ROWS,3] *= shares[:,None]
        data[:,6::KNOT_ROWS,3] *= shares[:,None]

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
            self._packet_terms = _PacketTerms(raw,base)
        terms = self._packet_terms
        data = self._base_array.copy()
        rows = data[:,4::KNOT_ROWS]
        # Cloth coordinate: fixed to the travelling history, so musical bends are sweeps carried by the ribbon
        # rather than a stationary lump field the cloth slides through.
        u = terms.u
        x = u+self.controls.scene.flow.head_x-self.travel
        # Keep elastic excursions legible above ordinary sustained input; the old unit tanh compressed hits twice.
        b,m,h = (3.*np.tanh(np.asarray(self.spring)/3.)).T[:,:,None]
        values = {key:self._value(key) for key in TARGETS}
        carrier = terms.carrier
        # No time-varying axial scaling: horizontal motion is only the steady flow (DevCurve's rule). The former
        # elastic stretch scaled x about the centre on every kick and read as sideways bursts (operator, 5 Nov).
        # The axial roll turns the carrier (its helix and the bundle's separation) like a skewer. Height scales
        # both transverse carrier components, so a turn changes the visible phase, never the visible amplitude.
        separation = _SEPARATION
        depth_wave = terms.depth_wave
        # The travelling pulse swells the carrier's own crests and troughs where it is: always WITH the shape.
        # Appearance follows the authored-width band (legible, travelling); geometry follows the broad bounded
        # envelope so whole waves swell together and the curvature keeps its own sign (flow rule).
        swell = self.pulse_at(x)
        # Beyond the field the published edge value continues (a Whole Swell never ends at the grid edge).
        frozen = self._frozen_body_on and self._frozen_state is not None
        if frozen and self._frozen_gain_cells is not None:
            broad = np.interp(x,self._frozen_cells(),self._frozen_gain_cells)
        else:
            broad = np.interp(x,PULSE_GRID,self.geometric_gain(values['bend']))
        geometric = np.interp(x,PULSE_GRID,self._geom)
        gain = broad
        shape = values
        clock,angle,twist_phase,passage = self.time,self.angle,self.twist_phase,self.passage
        if frozen:
            # Frozen Past: every knot reads the state held on its cloth cell (blended into the live state while leaving).
            share = self._frozen_body_share
            blend = share*share*(3.-2.*share)
            state,live,where = self._frozen_state,self._frozen_rows()[:,0],self._frozen_cells()
            def cell(index):
                held = np.interp(x,where,state[index])
                return held if share>=1. else live[index]+(held-live[index])*blend
            shape = dict(values)
            for index,key in enumerate(FROZEN_BODY):
                low,high = self.controls.ranges[key]
                shape[key] = low+(high-low)*cell(index)
            base = len(FROZEN_BODY)+1
            m = np.stack([cell(base+2*ribbon)[ribbon] for ribbon in range(RIBBON_CAPACITY)])
            h = np.stack([cell(base+2*ribbon+1)[ribbon] for ribbon in range(RIBBON_CAPACITY)])
            base += 2*RIBBON_CAPACITY
            clock,angle,twist_phase,passage = cell(base),cell(base+1),cell(base+2),cell(base+3)
        cy = carrier*shape['height']*gain
        cz = depth_wave*shape['height']*gain+separation*shape['spread']
        cosine,sine = (math.cos(self.angle),math.sin(self.angle)) if angle is self.angle else (np.cos(angle),np.sin(angle))
        y,z = cosine*cy-sine*cz,sine*cy+cosine*cz
        # Depth sway acts in world space after the roll and travels with the cloth. The former standing bend
        # (a fixed spatial sine the ribbon slid through) is replaced by the travelling pulse above.
        z = z+.4*shape['depth']*m*terms.depth_sway
        idle=self.controls.idle_motion*(1.-passage)
        y+=idle*.08*np.sin(.45*clock+terms.idle_y+_OWNER)
        z+=idle*.05*np.cos(.33*clock+terms.idle_z-_OWNER)
        if frozen and self._frozen_surge is not None:
            held = np.interp(x,where,self._frozen_surge)
            if share<1.:
                live_drift = self.pulse_drift(x)*(PULSE_SURGE*values['bend'])
                held = live_drift+(held-live_drift)*blend
            x,y,z = self._surge(data,x,y,z,None,held)
        else:
            x,y,z = self._surge(data,x,y,z,PULSE_SURGE*values['bend'])
        rows[:,:,0] = x-raw.world_origin[0]-self.controls.scene.flow.head_x+self.travel
        # One common smooth bounding domain prevents floor-crossing/clamp kinks at extreme editor values. Peaks
        # are meant to rise high: the framing makes room for them, the body is never capped to fit a frame.
        rows[:,:,3] = 3.5*np.tanh(rows[:,:,3]*shape['width']*(1.+.35*geometric)/3.5)
        rows[:,:,2] = 5.*np.tanh(z/5.)
        twist = terms.twist*shape['twist']+shape['torsion']*(1.6*m*terms.torsion_a+.12*h*terms.torsion_b)
        data[:,5::KNOT_ROWS,1] = twist+twist_phase+angle+idle*.18*np.sin(.28*clock+terms.idle_twist+_OWNER)
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
        offset = values['lift']+rise
        if frozen:
            offset = self._frozen_vertical(x,offset)
        rows[:,:,1] = soft_y+offset
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
            crest,weight = terms.crest(cards,n)
            # Existing visible rim slots respond immediately; this eased source creates no simulation in the draw.
            data[:n,6::KNOT_ROWS,3] = np.maximum(data[:n,6::KNOT_ROWS,3],
                values['sparkle']*max(self._hit,.4*self.bands[2])*crest)
            data[:n,7::KNOT_ROWS,3] *= (1.+HIT_GLOW*self._glow*weight)*(1.+PULSE_GLOW*swell[:n])
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
                self._card_hsv = cached = (cards,hsv,{})
            # The six HSV columns, per card set and share dtype (``column`` of the same values every tick). Keyed by the
            # dtype's string: plain step state, as the Studio's checkpoints copy it.
            columns = cached[2].get(share.dtype.str)
            if columns is None:
                columns = cached[2][share.dtype.str] = tuple(column(field,share) for field in zip(*cached[1]))
                for array in columns:
                    array.flags.writeable = False
            hue_a,hue_d,sat_a,sat_d,val_a,val_d = columns
            hue = unit_remainder(hue_a+hue_d*share)
            saturation = sat_a+sat_d*share
            value = val_a+val_d*share
            # The swell deepens colour where it is: saturation rises toward 1 (never toward white), hue and value
            # keep their own logic, and a neutral colour stays neutral rather than gaining an invented hue.
            vivid = self.controls.pulse.saturation*swelling*np.clip(saturation/PULSE_GREY,0.,1.)
            saturation = saturation+(1.-saturation)*vivid
            share = np.maximum(share,vivid)
            k = sector_remainder(_HSV_OFFSETS+hue[:,:,None]*6.)
            tint[:,:,:3] = value[:,:,None]*(1.-saturation[:,:,None]*np.clip(np.minimum(k,4.-k),0.,1.))
            alpha = np.clip(share/.1,0.,1.)
            tint[:,:,3] = alpha*alpha*(3.-2.*alpha)
        self._fade_ribbons(data,rows)
        packet = RibbonPacket(data.tobytes(),raw.instances,raw.vertices,(raw.world_origin[0],2.,0.),raw.coordinate_origin)
        self._snapshot = HybridSnapshot(packet,self.time,self.travel,self.angle,self.angular_speed,self.twist_phase,
            tuple(self.drive.items()),tuple(values.items()),self.ready,passage=self.passage,
            head_x=self.controls.scene.flow.head_x,zoom=self.zoom,direction=self.direction,
            pulse=(self._level if self._rim_share==1. else self._level*self._rim_share).astype(np.float32).tobytes())
        return self._snapshot
