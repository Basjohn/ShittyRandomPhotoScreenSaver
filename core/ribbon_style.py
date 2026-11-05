"""Qt/GL-free ribbon appearance values shared by authoring and rendering."""
from dataclasses import astuple, dataclass
import math


@dataclass(frozen=True)
class RibbonSparks:
    """Sparks attached to the ribbon's history; per-knot sparkle (0..1, ``RibbonRing.append(sparkle=)``) gates them."""
    per_knot: int = 6
    lifetime: float = 4.            # seconds
    drift: float = .9               # world units per second at birth, slowing with age
    rise: float = .35               # upward bias of the drift direction
    smallest: float = 1.5           # point size, pixels
    largest: float = 4.5
    light: float = 6.
    twinkle: float = 1.7            # Hz
    white: float = .6

    def __post_init__(self):
        if isinstance(self.per_knot, bool) or not isinstance(self.per_knot, int) or not 1 <= self.per_knot <= 16:
            raise ValueError('Sparks per knot must be an integer in 1..16')
        values = (self.lifetime, self.drift, self.smallest, self.largest, self.light, self.twinkle, self.white)
        if (not all(math.isfinite(v) and v >= 0 for v in (*values, abs(self.rise))) or self.lifetime <= 0
                or not 0 < self.smallest <= self.largest <= 32 or self.white > 1):
            raise ValueError('Ribbon sparks need finite non-negative values, a positive lifetime and sizes in (0, 32]')



@dataclass(frozen=True)
class RibbonStrays:
    """Free strands: liquid filaments that peel off the sheets and flow with the history (``shading='strays'``);
    per-knot sparkle gates them, like sparks."""
    per_knot: int = 2
    length: float = 10.             # knots a stray spans along its sheet
    reach: float = .6               # world units it leaves the sheet by at its free tip (fully peeled)
    chance: float = .5              # share of the sparkle-gated slots alive
    width: float = 1.2              # half-width of its quad, pixels (the line's core is about a third)
    light: float = 2.
    beads: float = 5.               # droplets per stray
    peel_time: float = 2.           # seconds of knot age to peel most of the way
    halo: float = 0.                # soft glow around each filament (a fuzzy splash), relative to its core
    glow: float = 1.                # share of its light sent to the bloom
    pulse_growth: float = 0.        # repeat-event temporary length share (cohort path)
    pulse_glow: float = 0.          # repeat-event glow gain (cohort path)
    admission_softness: float = 0.  # smooth slot growth at the musical threshold; zero preserves authored lab fixtures

    def __post_init__(self):
        if isinstance(self.per_knot, bool) or not isinstance(self.per_knot, int) or not 1 <= self.per_knot <= 8:
            raise ValueError('Strays per knot must be an integer in 1..8')
        values = (self.length, self.reach, self.chance, self.width, self.light, self.beads, self.peel_time, self.halo,
                  self.glow, self.admission_softness,self.pulse_growth,self.pulse_glow)
        if (not all(math.isfinite(v) and v >= 0 for v in values) or not 1 <= self.length <= 32
                or self.chance > 1 or self.admission_softness > 1 or self.pulse_growth > 1 or not 0 < self.width <= 16 or self.peel_time <= 0):
            raise ValueError('Ribbon strays need finite non-negative values, a length in 1..32 knots, a 0..1 chance, '
                             'a width in (0, 16] pixels and a positive peel time')



@dataclass(frozen=True)
class RibbonMaterial:
    """Filament look, in units of the ribbon itself; no music, palette or scene authority."""
    strands: float = 16.            # filament lines across the width
    strand_half_width: float = .11  # of one strand spacing
    strand_light: float = 1.7
    strand_warp: float = .06        # across-width spread/gather amplitude
    warp_frequency: float = .25     # warp cycles per strand-phase unit along the path
    rim_half_width: float = .02     # of the width
    rim_light: float = 1.4
    path_cap: float = 64.           # max path-length gain 1/|N.V| where the sheet is not widened
    min_pixels: float = 2.          # edge-on flat sheets stay this wide; interior light compensates true width
    body_alpha: float = .035
    body_tint: float = .35
    fill_light: float = .12         # the sheet's own glow
    fill_centre: float = .3         # fill level at the centre line (edges are 1)
    rim_glow_width: float = .05     # of the width, exponential falloff from each edge
    rim_glow_light: float = .25
    glint_density: float = .5       # glint cells per strand per strand-phase unit
    glint_chance: float = .2
    glint_light: float = 5.
    glint_radius: float = .3        # strand spacings (at least glint_min_pixels)
    glint_min_pixels: float = .75
    strand_white: float = 0.        # strands' mix toward white (0 = the ribbon colour)
    rim_white: float = 0.
    strand_jitter: float = 0.       # irregular strand spacing, 0..0.9 (monotone)
    strand_variation: float = 0.    # energy-neutral contrast between fine and dominant filaments
    cross_curve: float = 0.         # smooth transverse bow in half-widths; 0 retains the flat strip
    glow: float = 1.                # share of the sheet's light sent to the bloom (local glow, not the mist's)
    hot: float = 0.                 # white-hot cores on the brightest strands (0..1), the rest keep their colour
    glint_reactivity: float = 0.    # additional local highlight admission from the packet's current musical emission
    # Lattice: two diagonal families of thin lines woven through the sheet in its own surface coordinates (the
    # warped across coordinate and the path phase), so the net travels and twists with the cloth.
    lattice_cells: float = 3.       # lattice spacings across the width (each family)
    lattice_along: float = 5.       # lattice spacings per strand-phase unit; whole, so phase rebases never shift it
    lattice_half_width: float = .045  # of one lattice spacing
    lattice_light: float = .25      # relative to the sheet's emission; 0 is off
    lattice_reactivity: float = 2.5  # extra lattice light from the knot's musical emission above its quiet level
    lattice_glow: float = .35       # share of the lattice's light sent to the bloom (keeps peaks from washing white)

    def __post_init__(self):
        values = astuple(self)
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0 for v in values):
            raise ValueError('Ribbon material values must be finite and non-negative')
        if (not 1 <= self.strands <= 256 or not 0 < self.strand_half_width <= .5 or not 0 < self.rim_half_width <= .5
                or not 0 < self.rim_glow_width <= .5 or self.fill_centre > 1 or self.glint_chance > 1
                or self.strand_white > 1 or self.rim_white > 1 or self.strand_jitter > .9 or self.strand_variation > 1
                or self.hot > 1):
            raise ValueError('Ribbon strands need 1..256 lines and positive half-widths up to half a spacing')
        if self.body_alpha > .95 or self.path_cap < 1 or self.min_pixels > 8 or self.cross_curve > 1:
            raise ValueError('Ribbon body alpha must stay below 0.95, path cap at least 1, minimum width at most 8 px')
        if (not 1 <= self.lattice_cells <= 128 or not 1 <= self.lattice_along <= 64
                or float(self.lattice_along) != int(self.lattice_along) or not 0 < self.lattice_half_width <= .5
                or self.lattice_glow > 1):
            raise ValueError('Ribbon lattice needs 1..128 spacings across, a whole 1..64 along, a positive half-width '
                             'up to half a spacing and a 0..1 glow share')

    def uniforms(self):
        return dict(uStrands=(self.strands, self.strand_half_width, self.strand_light, self.strand_warp),
                    uRim=(self.rim_half_width, self.rim_light, self.path_cap, self.min_pixels),
                    uBody=(self.body_alpha, self.body_tint, self.strand_variation, self.warp_frequency),
                    uFill=(self.fill_light, self.fill_centre, self.rim_glow_width, self.rim_glow_light),
                    uGlint=(self.glint_density, self.glint_chance, self.glint_light, self.glint_radius),
                    uTone=(self.strand_white, self.rim_white, self.strand_jitter, self.glint_min_pixels),
                    uGlow=(self.glow, self.hot,self.glint_reactivity),
                    uLattice=(self.lattice_cells, self.lattice_along, self.lattice_half_width, self.lattice_light),
                    uLatticeTone=(self.lattice_reactivity, self.lattice_glow))

