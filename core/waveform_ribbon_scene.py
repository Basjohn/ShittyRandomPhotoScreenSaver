"""Plain waveform scene inputs. No Qt, GL resources, clocks or preset store."""
from __future__ import annotations
from dataclasses import dataclass, field
import math
from core.ribbon_style import RibbonMaterial, RibbonSparks, RibbonStrays
from core.settings import framed_camera as fc
from core.settings.waveform_ribbon_camera import GROUNDED_ORBIT, YAW_SPAN, FOV_RANGE
from rendering.gl_programs.mist import mist_uniforms

SPEC = fc.FramedCameraSpec(
    prefix='waveform_ribbon_', pivot=(0., 2., 0.), orbit_distance=80., pitch_base_degrees=-15.,
    pitch_span_degrees=60., yaw_span=YAW_SPAN, tilt_range=(-.5, .5), eye_center=(0., 8., 0.), eye_half=(120., 8., 120.),
    clearance=.4, offset_scale=(120., 8., 120.), travel_speed=16.,
    floor_hook='core.settings.waveform_ribbon_camera:floor',grounded_orbit=GROUNDED_ORBIT,fov_range=FOV_RANGE)

PALETTE = (((0., .52, 1.), (0., .22, 1.)),    # cyan -> electric blue
           ((.03, .08, 1.), (.24, .025, 1.)),  # blue -> violet
           ((.38, .006, 1.), (1., .012, .62))) # violet -> magenta

@dataclass(frozen=True)
class Environment:
    backdrop: tuple = (.015, .025, .045)
    # Explicit Off for shared primitive APIs. Waveform has exactly one volume atmosphere when enabled.
    mist: dict = field(default_factory=lambda: mist_uniforms(falloff=0.))


@dataclass(frozen=True)
class Fog:
    """One smooth night medium displaced by the actual rolled, cambered, floor-colliding cloth."""
    density: float = .022
    height: float = 1.1
    clearance: float = .3
    softness: float = .9
    ambient: tuple = (.035, .05, .085)
    light: float = .6
    # Local light compresses toward this radiance (linear, luminance) and keeps this share of the source hue.
    light_ceiling: float = .25
    light_tint: float = .5
    noise: float = .2
    noise_scale: float = .16
    drift: float = .1
    field_span: tuple = (-80., 80., 1024)
    depth_range: tuple = (.3, 300.)
    cell: int = 24
    slices: int = 128
    reflection_cell: int = 32
    reflection_slices: int = 96


@dataclass(frozen=True)
class Floor:
    """Wet concrete: a legible dark base lit by the mist's light field, and reflected light drawn out into columns.

    At grazing angles a micro-surface tilt toward or away from the viewer moves the reflection a long way vertically
    and a sideways tilt hardly at all: a wet floor shows each light as a long column along the view, broken into
    horizontal bands by the relief, never a blurred mirror. Light near the floor keeps a strong column; light high
    above it spreads over far more floor and stays faint (``column_height``)."""
    albedo: str = 'assets/textures/waveform_floor/concrete_albedo.png'
    roughness: str = 'assets/textures/waveform_floor/concrete_roughness.png'
    height: str = 'assets/textures/waveform_floor/wet_surface_height.png'
    tile: float = 12.               # concrete colour and broad relief patch (world units)
    micro_tile: float = 1.6         # micro relief patch (world units); the same smooth height data, finer
    albedo_gain: float = 1.        # wet concrete is dark
    tint: tuple = (1.,1.,1.)       # linear surface tint, independently of reflection strength
    albedo_bias: float = .5        # preserve filtered material variation at grazing angles
    ambient: tuple = (.4, .4, .45)
    reflection: float = 6.         # reflection strength before Fresnel (look gain)
    f0: float = .02                 # water film
    relief: tuple = (.03, .4)       # height amplitude of the broad and micro relief (world units)
    # Reflection offset per unit slope (uv): broad wobble, micro offset across and along the view.
    ripple: tuple = (.25, 0., 0.)
    # Micro facets are many per pixel at this grazing view: their average is a vertical streak (the receiver's
    # roughness footprint), never per-pixel offsets, which aliased into horizontal scanlines. Streak half-length
    # (canonical aperture share; projected from a fixed world length) and the roughness range across the surface (from the broad relief's slope).
    streak: tuple = (.5, .8, 1.)
    # Column width: reflection mip across the column (min/max over roughness). Broad on purpose: a column a few
    # reflection texels wide flickered at its edges as the sheets moved; a wide one is smooth smeared colour mass.
    lod: tuple = (3.5, 3.5)
    resolution: float = .5          # reflection target scale
    resolution_max_height: int = 360  # reflection target height cap (pixels)
    specular_max_height: int = 1080  # the reflection term is evaluated at most this tall, then read back
    # Column fade toward the camera and its far level; a sparkle threshold above 0 adds wet-film grain (rejected:
    # it read as the mottled wet/dry floor).
    column: tuple = (6., .6, 0.)
    pool: float = 2.5              # restrained source light, so the ground is not a continuous blown-white strip
    # Full strength at this multiple of the mean reflected light; wet-film breakup (0: none, a smooth column; the
    # film is sub-pixel grain at this grazing view and shimmered as light moved under it); power.
    hot: tuple = (2., 0., 1.5)
    # Reflected chroma about its luminance (1 as reflected): the sheets' own hue as coloured mass, not pastel.
    hue: float = 2.4
    # Material legibility at the grazing camera (reflection Off included): albedo variation around its exact mean,
    # and zero-mean shading by the broad relief, so the concrete reads without changing the floor's level.
    contrast: float = 3.
    shading: float = .35
    elongation: float = 3.          # material laid out this many times longer along world z (grazing camera)
    relief_bias: float = .5        # mip bias of the relief read by shading and breakup: broad facets, no hairlines
    # Reflection breakup by the same relief (0 off): facets tilted along the view send the column's light toward or
    # away from the eye, the long horizontal breaks of a grazing wet floor; zero-mean, so the mass keeps its strength.
    breakup: float = .2            # restrained: smooth coloured mass over crisp bands that flicker as light moves
    streak_length: float = 150.     # optical streak half-length (world units) at Streak Length 1
    column_height: float = 10.       # reflected light this high (world) keeps a quarter of its column's strength
    # The sheets' local light on the ground, with its depth falloff spread this many times and its peak lowered by
    # the square root: the grazing view otherwise compresses it into one bright seam across the image.
    pool_spread: float = 4.
    # Reflected light compresses smoothly toward this linear luminance (saturating, hue kept): strong preset light
    # reads as coloured mass under the sheets, never a flooded plane.
    glow_limit: float = .5
    # Surface light falls off toward the camera from the sheets' plane over this many world units, to this share far
    # away: dark wet ground in a wide view, legible concrete under the light.
    light_reach: float = 35.
    light_far: float = .5
    # Floor give (0 off: the rigid plane, drawn exactly as before). Where a ribbon's lower edge comes down onto the
    # floor, the wet floor yields in a soft dent instead of the floor-contact map flattening the sheet along a plane:
    # this share of the edge's reach below the contact level is taken by the floor, never deeper than give_depth
    # (soft-capped, all dents together). The dent is reduced once per frame from the published cloth: per world x
    # (give_span) and per ribbon, a Gaussian across z centred under the contact (give_radius plus the contact's own
    # spread), blurred along x (give_blur, Gaussian sigma), so it is as smooth in time as the ribbons themselves.
    give: float = 0.
    give_depth: float = .9
    give_radius: float = .9
    give_blur: float = .7
    give_softness: float = .08      # the reach below the contact level eases in over this (softplus): no threshold
    give_span: tuple = (-80., 80., 1024)
    # Reflection through the dent: reflected light is sought this far (world) along the ray mirrored by the dented
    # surface, so the wet film bends the reflected column into the dent instead of drawing a flat mirror over it.
    give_reach: float = 3.


@dataclass(frozen=True)
class Flow:  # Lab Plan section 4A: history enters at the head (world +x) and drifts toward the tail
    speed: float = 1.6
    head_hz: float = .33
    phase: float = 4.2             # explicit synthetic start phase, not a second clock
    phase_swell: float = .35       # broad smooth compression/expansion of neighbouring folds
    amplitude_swell: float = .3
    depth_sway: float = 1.
    knot_hz: float = 6.
    shape_tau: float = .45          # per smoothing stage of history-carried shape controls
    head_x: float = 34.
    fade_in: float = 2.5            # seconds of age over which the head fades in
    fade_out: float = 5.            # seconds of age over which the tail fades out
    # Travel direction, the history's one sign: +1 travels toward -x (enters at the right), -1 is its mirror image
    # (enters at the left). Every history computation works on the history axis (head at +head_x, travelling toward
    # -axis), so packets are identical either way; the axis -> world map (world x = direction * axis) is applied once,
    # at the world boundary of the history's consumers (WaveformScene and the Studio's projection).
    direction: float = 1.


def hue_between(a, b) -> tuple:
    """The colour halfway between two in hue (the short way round), at their mean saturation and value, so a
    cyan -> magenta gradient passes through blue, not lavender."""
    import colorsys
    (h0, s0, v0), (h1, s1, v1) = colorsys.rgb_to_hsv(*a), colorsys.rgb_to_hsv(*b)
    if abs(h1 - h0) > .5:
        h1 += -1. if h1 > h0 else 1.
    return colorsys.hsv_to_rgb(((h0 + h1)/2) % 1., (s0 + s1)/2, (v0 + v1)/2)


@dataclass(frozen=True)
class Shaping:
    """Shape and reactivity tuner (Lab Plan section 0, the WR-08 tuner control's model): which energy shapes which
    ribbon property, and how far. A tuner, not a shape builder: the head oscillator (musical history) still draws the
    waves; every target is a smooth function of band-limited history (two smoothing stages of at least
    ``Flow.shape_tau``), so no setting can make a sharp or jagged ribbon."""
    # target -> (quiet, loud): the range its source's 0..1 level sweeps.
    ranges: dict = field(default_factory=lambda: dict(
        width=(.40, .78), width_swell=(.08, .28), twist=(.85, 1.85), emission=(.7, .85), spread=(.32, 1.25),
        amplitude=(.5, 1.2), lift=(-.35, .2), sparkle=(.18, .85), deformation=(.15, .3), arc=(0., 0.),
        tint=(0., 0.)))
    # target -> source (SOURCES); targets not named follow loudness.
    drive: dict = field(default_factory=dict)
    # The bass arc: wave height grows by up to ``arc`` (a target above) where the bass source swells, so a bass
    # passage draws one taller arc that flows along the history (the preset-range board's dominant peak).
    # Synthetic bass timing: (every, length, offset) seconds; a raised cosine, the length about one wave.
    bass: tuple = (12., 3., 0.)
    # ``tint`` is how far each knot takes its ribbon's loud colours (Recipe.ribbon_colours): colour reactivity that
    # flows along the history like the shape does.
    # Per-ribbon character (amplitude, width, wave frequency, phase, light): identical sheets on even phases braid
    # into a regular lattice and sum to white; the mock's sheets differ and cross irregularly.
    characters: tuple = ((1., 1., 1., 0., 1.), (.85, 1.1, .96, 1.1, 1.5), (.72, .75, 1.07, .55, .65))


@dataclass(frozen=True)
class Recipe:
    environment: Environment = field(default_factory=Environment)
    fog: Fog | None = field(default_factory=Fog)
    floor: Floor = field(default_factory=Floor)
    flow: Flow = field(default_factory=Flow)
    shaping: Shaping = field(default_factory=Shaping)
    # Each ribbon's own colours, (centre, edge) per ribbon: quiet (the ribbon's base) and loud (taken per knot by
    # the tuner's tint target). A look coloured by ribbon (bass, mid, high) rather than by the world grade sets the
    # grade's sheet share near 0.
    ribbon_colours: dict = field(default_factory=lambda: dict(low=PALETTE, high=PALETTE))
    # Mock-directed look (WR-04): saturated darker body, thin near-white irregular strands and rims, visible glints.
    material: RibbonMaterial = field(default_factory=lambda: RibbonMaterial(
        strands=40., strand_half_width=.018, strand_light=1.5, strand_white=.04, strand_jitter=.35, strand_warp=.18,
        strand_variation=.9, cross_curve=.35, warp_frequency=.2, rim_light=2.9, rim_white=.08, rim_half_width=.009,
        fill_light=.12, fill_centre=.3, rim_glow_light=.35,
        rim_glow_width=.04, body_alpha=.025, body_tint=.4, glint_density=1.4, glint_chance=.12, glint_light=3.,
        glint_radius=.25, glint_min_pixels=.8))
    sparks: RibbonSparks | None = field(default_factory=lambda: RibbonSparks(per_knot=16, lifetime=4.5, drift=1.2, rise=.4,
                                                                       smallest=1.6, largest=5., light=16., white=.25))
    strays: RibbonStrays | None = None  # free liquid strands peeling off the sheets (the alternate board)
    # World colour grade (preset look): the mock's cyan left, blue-violet middle, magenta right across the view,
    # taking this share of each ribbon's own colour so identities still read. History tint carries reactivity.
    # (left, mid, right, world x range, ribbon share, mist share): mixing a magenta sheet far toward cyan passes
    # through grey, so the sheets take a small share and keep their identities; the mist takes most of it.
    # Preset colour data: a low-reactivity and a high-reactivity colour pair (left, right across the view). The
    # middle stop is derived by hue, so cyan -> magenta passes through blue, not lavender. Reactivity blends the
    # pairs (the lab's synthetic states are react 0 and 1). Settings (WR-08) edits these as gradient nodes.
    # Nodes are (position 0..1 across grade_range, rgb): the WR-08 gradient editor's circles. Up to six positions
    # across both pairs together; reactivity blends the two gradients position by position.
    palette: dict = field(default_factory=lambda: dict(
        low=((0., (0., .85, 1.)), (.5, hue_between((0., .85, 1.), (1., .1, .85))), (1., (1., .1, .85))),
        high=((0., (0., .85, 1.)), (.5, hue_between((0., .85, 1.), (1., .1, .85))), (1., (1., .1, .85)))))
    # World x range of the pair, the sheets' share (small: identities hold), the mist's share.
    grade_range: tuple = (-6., 6.)
    grade_share: tuple = (.3, .75)
    bloom: float = .14
    exposure: float = 1.
    # Pulse Rim: the rims (crisp line and rim glow) brighten by 1 + pulse_rim x the published pulse appearance field
    # where the pulse is (light pass only). 0 draws exactly the rims without it.
    pulse_rim: float = 0.


FLOOR_CONTACT = (0., .03, .15)
VIEW_SLOPE = math.tan(math.radians(-SPEC.pitch_base_degrees))
