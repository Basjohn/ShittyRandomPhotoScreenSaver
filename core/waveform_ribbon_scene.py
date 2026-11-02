"""Plain waveform scene inputs. No Qt, GL resources, clocks or preset store."""
from __future__ import annotations
from dataclasses import dataclass, field
import math
from core.ribbon_style import RibbonMaterial, RibbonSparks, RibbonStrays
from core.settings import framed_camera as fc
from core.settings.waveform_ribbon_camera import GROUNDED_ORBIT, YAW_SPAN
from rendering.gl_programs.mist import mist_uniforms

SPEC = fc.FramedCameraSpec(
    prefix='waveform_ribbon_', pivot=(0., 2., 0.), orbit_distance=12., pitch_base_degrees=-15.,
    pitch_span_degrees=60., yaw_span=YAW_SPAN, tilt_range=(-.5, .5), eye_center=(0., 8., 0.), eye_half=(60., 8., 60.),
    clearance=.4, offset_scale=(60., 8., 60.), travel_speed=4.,
    floor_hook='core.settings.waveform_ribbon_camera:floor',grounded_orbit=GROUNDED_ORBIT)
ORTHO_REFERENCE_FOV = 45.

PALETTE = (((0., .52, 1.), (0., .22, 1.)),    # cyan -> electric blue
           ((.03, .08, 1.), (.24, .025, 1.)),  # blue -> violet
           ((.38, .006, 1.), (1., .012, .62))) # violet -> magenta

@dataclass(frozen=True)
class Environment:
    backdrop: tuple = (.05, .055, .07)  # the cheap floor mist: barely tinted, dark
    # Floor mist (analytic, cheap): clear around the waveform, thickening toward the camera-side floor edges, the
    # extreme sides and most of all into the distance, where it is thick dark grey and hides the horizon.
    mist: dict = field(default_factory=lambda: mist_uniforms(centre_xz=(0., -1.), radii_xz=(9., 7.5), falloff=1.6,
                                    floor_thickening=1., thickening_height=1.5, low_glow=0.))


@dataclass(frozen=True)
class Fog:
    """S3D-7 volume mist shaped by the waveform: thick everywhere behind the sheets except a clear band that hugs their
    exact lower/upper envelope along x (reduced per frame from the admitted history). The band's rim glows in the
    colour of the nearest sheet edge and darkens into the mass; a detail march adds the billows."""
    density: float = 1.6            # extinction per world unit inside the mist
    margin: float = .1              # clear air beyond the envelope (world units)
    tube: float = .3                # true 3D clearance around every sheet (world units)
    clearance: tuple = (.3, .25)    # push of the whole field from the envelope; the mist never enters within
    ends: float = 6.                # the mist comes this far forward where the sheets fade (world units)
    # |world x| where the clear band and the sheets' clearance start to close, and where they are closed: beyond the
    # framed view the ribbons run into mist (the off-screen edge mist), so no view along them sees a clear corridor.
    sides: tuple = (8., 13.)
    floor: tuple = (0., 5.5, 2.5)   # floor bank height, forward reach at the sides, |x| where the sides begin
    interior: tuple = (.25, .22, 1.5)   # unlit body lumps: floor, frequency; rim fall per unit of billow push
    floor_light: tuple = (0., 2., .08)  # floor mist light share, its reach from the sheets; wall-behind light
    softness: float = 1.5           # depth over which coarse coverage rises: the detail march erodes within it
    noise_scale: float = .35        # lobe frequency of the band's edge (per world unit)
    noise: float = 1.8              # lobe displacement of the edge (world units)
    start_z: float = -1.7           # the mist begins behind this world z (just behind the sheets)
    band_depth: float = 1.          # the clear band reaches this far behind start_z; the far wall closes it
    sheets_z: tuple = (-1.7, 1.7)   # depth range of the sheets, for the rim light's distance
    ambient: tuple = (.08, .09, .15)  # radiance of unlit mist: the distant cloud bodies, dark grey not black
    rim: float = 120.               # rim light gain on the nearest sheet edge colour
    reach: float = .35              # e-folding distance of the rim light from the envelope (world units)
    light_decay: float = 2.         # its extinction per world unit of depth into the mist
    haze: float = 0.                # faint haze in the clear band behind the sheets (never eroded)
    envelope_range: tuple = (-40., 40., 640)  # world x span and samples of the envelope reduction
    envelope_smoothing: float = .25 # Gaussian along x (world units)
    edge_evening: float = 4.        # world-x width over which the fringe's brightness is evened
    envelope_width: float = .5      # share of a sheet's half-width counted as its vertical extent (twisted sheets)
    depth_range: tuple = (.3, 90.)
    cell: int = 16                  # viewport pixels per coarse cell (light and coverage only)
    slices: int = 64
    reflection_cell: int = 24
    reflection_slices: int = 32
    # Detail march (per pixel at a reduced scale): bound on adaptive steps and their lengths in and out of the mist,
    # erosion by the tiling noise and its frequency (per world unit), self-shadow reach (world) and strength, and
    # the in-scatter's share of bloom.
    march_scale: float = .5
    reflection_march_scale: float = .25
    # Height caps (pixels) of the reduced-resolution targets: they leave the 718-pixel lab untouched and keep 1440p
    # and 4K at the approved look's detail per screen fraction instead of quadrupling the cost.
    march_max_height: int = 540
    reflection_march_max_height: int = 270
    # Shape bake box (world min, max) and cell size: the march reads the shape from it; outside, exact.
    bake_box: tuple = ((-30., 0., -12.), (30., 12., 4.))
    bake_cell: float = .2
    steps: int = 96
    step: tuple = (.15, 1.)
    erosion: float = .75
    detail_frequency: float = .8
    shadow: tuple = (.6, 4.)
    shadow_floor: float = .3
    crackle: tuple = (2.4, .08, 4., 4.)  # silhouette line: brightness, filament frequency (per px), sharpness, width
    crackle_glow: float = 3.      # the line's bloom share
    fringe_smoothing: float = 1.  # wider existing filter taps; preserve billows without march-jitter sand
    edge_glow: float = 3.          # extra light on thin eroded wisps (curl rims)
    glow: float = .3


@dataclass(frozen=True)
class Floor:
    """Smooth wet concrete: dark base lit by the mist's light field, and one crisp reflection broken by the surface.

    At grazing angles a micro-surface tilt toward or away from the viewer moves the reflection a long way vertically
    and a sideways tilt hardly at all: the wet-floor columns come from that offset, not from blurring a mirror.
    Reflections stay crisp at the contact and soften with the height of what they reflect (contact hardening)."""
    albedo: str = 'assets/textures/waveform_floor/concrete_albedo.png'
    roughness: str = 'assets/textures/waveform_floor/concrete_roughness.png'
    height: str = 'assets/textures/waveform_floor/wet_surface_height.png'
    tile: float = 12.               # concrete colour and broad relief patch (world units)
    micro_tile: float = 1.6         # micro relief patch (world units); the same smooth height data, finer
    albedo_gain: float = 1.        # wet concrete is dark
    tint: tuple = (1.,1.,1.)       # linear surface tint, independently of reflection strength
    albedo_bias: float = 2.5        # mip bias of the colour scan (grazing aliasing)
    ambient: tuple = (.03, .035, .05)
    diffuse: float = 0.             # gain on the mist's coarse light field (off: its depth slices band the floor)
    reflection: float = 6.         # reflection strength before Fresnel (look gain)
    f0: float = .02                 # water film
    relief: tuple = (.03, .4)       # height amplitude of the broad and micro relief (world units)
    # Reflection offset per unit slope (uv): broad wobble, micro offset across and along the view.
    ripple: tuple = (.25, 0., 0.)
    # Micro facets are many per pixel at this grazing view: their average is a vertical streak (the receiver's
    # roughness footprint), never per-pixel offsets, which aliased into horizontal scanlines. Streak half-length
    # (canonical aperture share; projected from a fixed world length) and the roughness range across the surface (from the broad relief's slope).
    streak: tuple = (.5, .8, 1.)
    lod: tuple = (1., 1.)           # reflection mip (half-resolution target: already soft)
    contact: tuple = (.002, 6., 6.)  # spread (uv) per unit of reflected height; along/across; probe mip
    resolution: float = .5          # reflection target scale
    resolution_max_height: int = 360  # reflection target height cap (pixels)
    specular_max_height: int = 1080  # the reflection term is evaluated at most this tall, then read back
    blur: float = 0.               # horizontal Gaussian across each column (receiver pixels)
    # Column fade toward the camera and its far level; a sparkle threshold above 0 adds wet-film grain (rejected:
    # it read as the mottled wet/dry floor).
    column: tuple = (6., .6, 0.)
    pool: tuple = (14., 1., 1.5, 1.5)  # waveform light on the concrete: gain, height, depth falloffs behind/front
    hot: tuple = (3., .7, 1.5)       # full strength at this multiple of the mean reflected light; wet-film breakup; power
    mist_reflection: float = .35   # share of the mist the floor mirrors: the mock's floor mirrors the hot light


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


FLOOR_CONTACT = (0., .03, .15)
VIEW_SLOPE = math.tan(math.radians(-SPEC.pitch_base_degrees))
