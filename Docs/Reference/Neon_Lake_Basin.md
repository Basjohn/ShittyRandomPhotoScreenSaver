# Neon Lake

**Accepted 7 Nov 2026 (operator):** "In general the neon lake fidelity is much improved and I would say accepted, it
also gives us a much nicer starting line for water deformation later." The seventh pass (Water Reaction, the skyline
sheet fix; evidence `.artifacts/evidence/visualizers/shockwave_grid/fidelity/20261106_fidelity/pass7/`) is the accepted look. The remaining
gaps it recorded against the goal mocks (whole-scene high-react look, net hue, dot field, far-shore line) are future
enhancements, not acceptance failures. Water deformation (Current_Plan §6, S3D-4 dynamic surface field) starts from
this baseline. The camera step on real music stays open in `Current_Plan.md` §5.

**23 October addendum (not yet visually accepted):** the [operator reconciliation](2026-10-23_Operator_EB_Neon_Settings_Reconciliation.md) requires camera/control-hint parity with Extruded Bubble (while preventing entry into terrain and allowing almost flat horizon views), a square editor preserving existing heightmap/brush results with desirable angled pseudo-3D preview, layered water/water glow, and improved relevant shared 3D controls. Only presets 1–4 are currently useful artistic study cases; all presets remain mutable. Existing baseline acceptance is not a claim these additions have been implemented or visually accepted. [Current Plan](../../Current_Plan.md) owns status.

Neon Lake replaces the flat Shockwave Grid picture. The stable mode ID and settings prefix remain
`shockwave_grid` and `shockwave_grid_*`; as a framed 3D Visualizer its CUSTOM layout profile is the same shared `planar`
profile used by framed 2D modes. The operator accepted the existing mode and its existing graphics/behavior baseline;
it is an accepted baseline in `Current_Plan.md` §0 with no live tasks. Its future water/brush/glow extensions below are **not**
retroactive acceptance failures. The supplied low/high mock in
`Docs/Future_Work/Additional_Future_Transitions_Package.zip` (removed from the tree on 5 November; source control
keeps it) is concept provenance, **not** the
accepted artistic reference. The **operator's current** Preset 1 is the working visual comparison,
not a frozen baseline; the operator may change it whenever desired.

Neon Lake is the **reference implementation** for a reusable **framed 3D internal-camera** contract,
not a permit to copy its special-case view code into each future mode. The shared opt-in capability is the current camera owner for framed 3D visualizers. Preserve this mode's authored
landscape angles, existing Settings/presentation pose and card/CUSTOM behavior while other modes supply their own
bounds and visual target. Current acceptance
is the accepted baseline (`Current_Plan.md` §0); the existing Preset 1 remains the
working visual reference while six new experimental presets are temporary and may all be rejected.
Every preset remains operator-editable, including Preset 1 and all six experiments. The historical
audio-reactivity acceptance gate included deterministic and operator real-music recordings; future additions
retain those evidence requirements but do not reopen the accepted baseline.

## Card, scene pose and input

The descriptor declares CARD / CARD_INTERIOR with the same shared `planar` CUSTOM stage geometry as framed 2D
Visualizers. The saved outer card rectangle and logical viewport remain the sole geometry authorities across framed-mode swaps;
internal camera pose never creates a mode-specific layout profile. Shell policy supplies ordinary card chrome and the
rounded interior stencil. Every rendered pose remains clipped, including Edit and extreme zoom/pan. The old overflow
key is forward-retired by the canonical settings and preset filters.

| Existing 3D input | Framed scene result |
| --- | --- |
| WASD | Internal turn/tilt on the existing logical capture clock |
| Alt+left-drag | Internal turn/tilt |
| Alt+right-drag | Internal pan, expressed as fractions of the card interior |
| Alt+scroll, on either Qt wheel axis | Internal scale about the interior centre |

These operations never move or resize the card or change its viewport. Plain CUSTOM geometry controls retain their
ordinary Edit behavior. Native Alt input during framed Edit is intercepted before QML wheel delivery; the filter exists
only while that capability and Edit are active. Descriptor admission and runtime generation fence all gestures.

The descriptor's `view_orbit_settings` and optional `scene_transform_settings` supply the complete five-key view pose.
The existing view owner settles and persists it once through canonical Settings, independently from curated art presets,
Custom art snapshots, layout Save/Cancel and SST geometry. A pan gesture uses a press-time baseline; scaling rebases
that baseline. Scene settlement does not cancel held WASD. Dormant input does not poll Settings.
Framed presets can additionally supply optional `starting_view` metadata to seed these same live keys on explicit
preset selection. Save Preset As captures it by default, outside the artwork snapshot; ordinary reloads and restarts
retain the adjusted live view. Validation/selection/repair behavior is owned by the Visualizer reference's
**Framed preset starting views** contract. Existing art files are not rewritten automatically.

Edit selection remains the fixed card rectangle. The internal eight-point guide and pivot use the same `basin_view`
(`item_point`) projection as rendering and clamp to the card interior. They remain paint, never geometry authorities.

## Authoring and migration

`core/settings/visualizer_mode_settings.py` owns typed controls, ranges, defaults admission, UI buckets, conditions and
presentation/source projections. `core/settings/default_settings.py` owns default values. The body is grouped by what
each control touches (2026-10-16): **Terrain** (the bespoke lazy editor, Height, Detail, Terrain Fill), **Water** (the
lake's water/ripple/crest colours, musical waves, detail, flow, idle swell and reflection) and **Terrain Reaction**,
then advanced **Surface** (style, glass, vertex colours, density, base opacity, horizon line), **Sky** (atmosphere,
clouds, stars and Starscape Beat with its star glow), **Sun & Moon** (body, placement, orbit, halo, rim vertices,
light rays), **Glow** (Surface Glow, Ridge Light Response, Water Line Glow) and **Frequency Response** last, which
preserves the consumed old nodes, notches, lanes and smoothing; those audio coordinates are never relabelled as
terrain. Keys never moved with the regrouping.
The five view fields have no Settings body rows. Surface Style admits only three present-day choices through the one typed spec and preset projection; `neon_lake_basin_options.py` owns their immutable choice/bit domain:

| Style | Surface presentation |
| --- | --- |
| Vertices (default) | Lit vertices on shared displaced lattice |
| Glass | Reflective continuous terrain and water |
| Glass + Vertices | Glass with outlined surface markers |

General-purpose mesh-edge wires are retired in the Settings surface selector. The lake shoreline is separately composited; a revised skyline pass now uses shifted copies of the actual land triangles against the landscape depth buffer instead of guessed highest points in projected columns. Retired surface-style strings are converted only during forward input/preset migration; the typed live spec/runtime admits **Vertices, Glass, Glass + Vertices** and nothing else. Retired Presets 2/3 remain explicit GODZIP debris; new experimental files use later authored ordinals rather than replacing those files.

Shoreline highlights are admitted only within the authored 0..1 terrain domain;
positive continued land cannot become a second lake by crossing a smoothed height
band. Point/edge pixel mapping uses Quick's actual item matrix and render viewport,
never whole-window width divided by card width. Embedding a card in a larger window
must not inflate its points or water-detail strokes.
Every visible authored lattice point retains its opacity and emission; viewport size,
perspective or DPR must not randomly thin the population. Point diameter follows the
actual item's pixel scale, preserving apparent size across DPR. Glass + Vertices fills
tiny marker cores and smoothly admits an interior hole only at 3..5 physical pixels,
where an outlined marker has enough samples to remain visible. This changes coverage
within a mark, never its lattice membership or authored density.

Tint, strength and roughness rows appear for Glass choices. Roughness is authored within .05.. .5, respecting the
shared material's .045 numerical floor. Plain vertices expose main/accent RGBA; glass vertices expose outline RGBA.
Terrain fill, crests, water, sky, stars, clouds, horizon, Sun, Moon and rays retain separate RGBA controls.
Appearance's **Ripple / Shore Colour** authors the water lines' base colour and alpha;
crests blend toward **Wave / Ridge Glow**. **Water Colour** owns the underlying fill.
Compound spec conditions drive row visibility/enablement without a second UI or model table. Vertices are
unique points on the actual displaced surface lattice, about ten percent denser than the prior point presentation.
Quality and Surface Detail bound that lattice; points and triangles always share it to avoid hiding points beneath a different approximation. Glass alone creates no point mesh and retires an existing one. Glass + Vertices uses smaller outlined markers to keep the combined picture readable. Reflected marks draw before depth-writing water, direct marks after it; point-size and
depth-function state restore even when drawing fails.

The canonical terrain record is `{version: 1, size: N, heights: [N*N floats]}`, with `N` within 2..257 and finite heights
within 0..1, plus two optional squares of whole cells (each the whole grid when absent): `basin` (where the scene's
basin sits in a grid that reaches past it) and `origin` (the grid the terrain brush grew it from: "Terrain brush"). Rows run near/front to far/back. Explicit malformed records raise; missing old terrain receives the canonical
basin seed. Positive values below the normal float32 minimum are rejected so packing cannot silently turn authored land
into water. `rendering/gl_programs/heightfield.py` owns admission, float32 packing and the bilinear CPU sampler. Water is
exactly an authored sampled height of zero, independent of waves, view pose and land height scale.

The terrain editor authors on a **square** field (2026-10-24: one heightmap cell is square on screen, centred, up to 440 px,
the canvas growing its height with its width), so the brush is round in the terrain's own cells whatever the panel's
shape; stored heights are never resampled. Before, the field stretched to the panel and a dab's footprint in cells
depended on the panel's width. It supports Raise, Lower, Flatten and exact Water, a circular brush, bounded brush radius/strength/falloff, per-stroke Undo/Redo,
reset and an explicit blue water preview. Brush effect depends on the stroke's path, never on pointer speed: dabs fall every 0.15 radii of physical distance (the remainder carries between pointer events) and each stands for that much stroke; a press that never moves applies a quarter radius once. Strength is quadratic (Raise/Lower add up to 0.5 height per radius of stroke at 100%, barely anything at 1%). The profile is flat in a core of (1 - Falloff) radius and eases with a cosine skirt out to 1 + Falloff/2 radii; the cursor shows both circles. Flatten approaches its height exponentially with that weight and snaps the core only at 100%. Lower stops at a small positive land height and leaves water alone, so only Water authors exact zero (inside the brush's half-weight contour). Loading is silent; one completed stroke saves once through the existing Custom
spec hook. Escape/hide cancels an unfinished stroke. Brush/history state is ephemeral; closed Settings has no terrain
timer, scene renderer or simulation.

Old source profiles and Custom snapshots retain their consumed musical intent. Input/model serialization, Settings,
preset application and repair all use canonical admission. Shipped presets explicitly own the current art/source keys,
exclude view pose, and remain operator-editable; their artistic numbers are not regression goldens.

## Shared rendering and lifecycle

`rendering/quick/visualizer/implementations/shockwave_grid.py` remains the lazy mode renderer. It reuses MeshResources,
StreamRing, SceneTarget and optional emission bloom. `rendering/gl_programs/neon_lake_basin_program.py` owns the new
projection and distinct terrain/water shaders. The retired flat shaders and their overflow/fit implementation are removed.

Only active Neon Settings configuration packs terrain into immutable FrozenFields; other modes and unknown hosts
perform no terrain normalization/packing. Equal full configurations reuse the frozen payload; changed grids derive
their bytes once at configuration. Captures retain that same payload by identity;
they do not copy or pack the control grid. A shared lazy `HeightfieldTexture` supports R32F heights or explicit RG32F
height/bank-distance storage; Neon uses the latter as one representation. The distance transform is derived once at
configuration, leaving exact authored-zero water ownership unchanged. Water displacement tapers over a narrow bank
band so a crest meets the solid shore continuously. The mode binds a half-cell
bank band (`0.5/min(cells)`): nearby water retains attack/release motion and is fully
reactive by the next mesh cell. Conservative zero-distance junctions are refined
locally against the real bilinear-positive support rather than leaving whole water cells flat.
The rendered shoreline follows the existing cubic `.018` contour, beyond the square
zero-height control cells: the same water waves and detail fade through that already
water-coloured shallow fringe, reaching zero at the visible contour. Authored height data
and exact-zero membership are unchanged; dry land and its growth behavior are unchanged.
A broad multi-cell attenuation strip is not part of the shoreline contract.
The texture uploads only changed authored data and fences
unpack/texture/sampler state. Allocation/deletion failures stay loud and owned for retry.
It creates no clock or global texture cache.

The existing Scene3D bendable mesh samples an opt-in positive cubic B-spline surface, and its
height/vertex coordinates are shared across triangles and points. The three present-day surface
styles do not enable general-purpose wire edges. Cubic smoothing cannot overshoot its local
control-height range; authored bilinear zero remains the water-classification authority.
The mode-owned terrain lattice now overscans all four authored edges, with geometrically growing
cell width away from the authored 0..1 sub-lattice. `neon_lake_basin_mesh.py` generates both triangles and actual
point markers from exactly the same axis coordinates, keeping the edited interior topology untouched. A
shader-side, deterministic land continuation joins the authored boundary, lets steep near-edge ridges settle into a shallow convex distant world rather than extruding indefinitely, and fades detail/emission/vertices while retaining
opaque land/depth up to its real terrain/sky tangency. The finite outer mesh edge stays behind nearer land, not a painted horizon. Off-editor continuation is not another
terrain editor or an infinitely repeating tile; it never invents a lake, but water the user painted to the grid's
edge keeps flowing outward as a stream or coast to the horizon (2026-10-24, operator: a stream out of the scene).
**Terrain reach:** the authored grid may extend past the basin (`basin: [column, row, cells]` in the heightfield
record; default the whole grid). The editor's **Extend Toward Horizon** grows it back and to the sides by whole cells
(basin cells kept exactly, new cells seeded from the continuation, max 257 a side); the shaders keep every distance in
basin uv and convert only heightfield reads (`basinGrid`, `uTerrainGrid`), and the mesh's fine lattice spans the whole
grid. CPU mirrors: `neon_terrain_extent.basin_continuation`, the camera floor and beat-star terrain checks. Distant
coverage and performance, including unusual zoom/card aspects, remain operator/GPU acceptance items.
An authored tier change replaces the one active mesh; ordinary frames allocate/rebuild nothing. Authored patch
bounds are derived once per terrain change; static conservative fitting changes only with authored terrain/view/aspect.
Audio cannot pump the fit, resize the target or move the water boundary.

The preserved Shockwave onset ring admits each serial once, spaces events by passage intensity, caps capacity and ages
on the existing logical clock. Water uses travelling crests and echo rings, with bounded displacement even when events
overlap. Dry land keeps static surface detail and frequency-driven lighting, and optionally reshapes with the
music (Terrain Reaction, below). Sky, celestial body and bloom remain optional. All context-local resources retire
through the normal mode owner; unchanged shared consumers acquire no heightfield work.

### Terrain Reaction (2026-10-16; replaces Growth and its eight-region contrast consumer)

Its own **Terrain Reaction** bucket: **React to Music** (off by default; presets choose), **Strength** (a share of
Terrain Height), three amounts — **Pulses** (each admitted onset sends a broad ground roll through the land from its
origin, heave then softer sink, `tanh`-bounded when hits overlap), **Peaks** (landforms answer their lane of the
spectrum with signed patterns, so some places rise and others sink and the land changes shape) and **Swell** (a broad
slow rise and fall) — the **shaper**, **Motion Speed**, **Rise** and **Settle**. The shaper is the Studio's shared
shape instrument (**Reaction Shaper**, `Docs/Reference/Visualizer_Studio.md` §3 "Shape instrument")
laid along the land's height, shoreline (left) to the authored summit (right): its curve is how strongly each
elevation deforms (it biases all three amounts), its lane boundaries split that axis into five frequency lanes (Bass ..
Treble: which part of the spectrum moves which elevation) and each lane's strength marker weights it. It is stored as one record
(`shockwave_grid_terrain_shaper`: nodes, notches, lanes; admitted part by part in
`rendering/gl_programs/neon_terrain_reaction.py`) and baked once per change into 32-sample elevation tables.

Logically, the analysis spectrum (log-spaced, low to high, already published for other consumers) splits into five
lane energies by equal stretches. Each lane's drive is mostly how far it rises above its own recent level (a 4 s
follower; a relative envelope, not a noise floor) and a little its capped share of the whole, times the existing
passage-ramp x musical-weight gate; Rise/Settle ease it on the capture clock. A sustained wall of bass settles to a
modest share and a rising lane over it takes the lead, so no band pins or drowns the land. The landforms' wander phase
advances only with the music's drive (Motion Speed sets its rate): silence holds the land still. Disabled, nothing is
read or kept and re-enabling starts from rest; generation/source/clock changes and retirement reset it.

The deformation lives in the single height owner (`basinLandHeight`), so vertices, glass normals (central
differences), flat-shaded normals, the skyline pass, the depth prepass and body visibility all follow it; the
skyline is given the event count it needs for Pulses. It is zero on water and fades in over the shore band, so the
water boundary never moves; it fades with the distant continuation's detail; land never sinks below 30% of its
authored height and never rises more than the bounded lift. The light-ray volume's land bound is fixed by the
settings (never pumped by audio). The renderer only uploads amounts, five drives, the phase and the baked tables.

### Smooth reshaping, Growth and Indents (2026-11-11, 1B.6)

Operator: "true smooth (no tearing/jagged edges) deformation ... optional growth of spires, mounds and land that
doesn't visibly exist at low reactivity and indents of land that does."

**The tearing and its cause.** Driven hard, the land tore into terraces and cliffs along elevation contours and
ridge lines broke into kinked segments (`.artifacts/evidence/visualizers/shockwave_grid/20261111_land/`:
`tearing_before_p1_staged_full_drive.png`, `tearing_before_p1.webp` on heavy1). `basinReaction` looked the lane up
by elevation in a table and switched lane at each boundary within one table step (1/31 of the height): two different
signed patterns met along that contour. The elevation was the bilinear cell height, creased along every cell line,
and the floor was a hard `max`. It is the height function, not the mesh (High tier lattice 189x126, the near band
split 2x): the same mesh draws the smooth version.

**Smooth at every drive.** Lanes cross-fade along the height (`lane_membership`: `REACTION_LANE_BLEND` 0.06 either
side of a boundary, shares summing to 1); the baked tables are per lane (`lanes`, 5 x 32) and are read through the
land's own cubic filter; the elevation is the smooth cubic land; downward change eases onto the floor share
(`-room * tanh`) instead of stopping on it; the reshaping comes in up a bank over the smooth land's rise
(`smoothstep(shore, 0.10, curved)` beside the old cell-height term) so it no longer stands as a wall along a
shore. At rest the picture is unchanged (Preset 1, drives zero: the run-to-run floor, max 1/255); under music the
same patterns move the land without the tears, a little less on banks and land under a tenth of the height scale.

**Growth and Indents** (Terrain Reaction bucket, both 0 by default and in every shipped preset; Strength scales
them like the other amounts):
- **Growth** raises landforms that do not exist at rest: one site per cell of a fixed lattice of the land
  (`basinSites`, an integer hash, world units), a smooth compact bump with zero height and slope at its rim.
  **Growth Shape** runs from broad low mounds (0: cell 1.05, up to 0.30 of Terrain Height) to slender tall spires
  (1: cell 0.70, up to 0.72, profile power 2.6). Each site wakes at its own level of the drive, so louder music
  raises more of them and each eases in and out. They stand back from the eye (`GROWTH_EYE_CLEAR` 0.8..2.0 world
  units) instead of raising the camera floor, so turning Growth on never lifts an authored low view.
- **Indents** press visible land toward its floor share in the same kind of sites (cell 0.85): hollows that open
  with the passage and deepen on hits, never below 30% of the authored height, never moving the water's edge.
- Both are terms of the one height owner (`basinLandHeight`): vertices, normals, skyline, depth and reflections
  follow; zero on water, faded at the shore and with distance like the rest of the reaction.

**Their drives** are the terrain reaction owner's own (`ShockwaveGridFrameRuntime._advance_forms`, capture clock,
`ShockwaveGridFrame.terrain_forms`), on the fixed real-music scale only: the passage's intensity through an S-curve
(`forms_level`: nothing below 0.10, `FORMS_CEILING` 0.92 from 0.90), eased by Rise / Settle, with each onset's hit
on top (`forms_hit`: `audible` x `musical_emphasis`, in over 0.07 s, out over 0.30 s; 30% of Growth's drive, 45%
of Indents'). No learned level, no presence ratio, no spectrum: with only these on the capture reads nothing but
the intensity it already had. Measured on recordings (production runtime, every recorded frame): growth p50
0.45-0.67, p95 0.66-0.79, max 0.85, never at 0.9; 0.09 at the 5th percentile of quiet_intro; a wave's birth lifts it
a median 6-10% early, mid and late in heavy1 alike. Off (amount 0 or React to Music off) nothing is collected,
kept or computed. A frame nothing drives tells the shader the reaction is off.

Cost (RTX 4090, 1300x750, PairedBench medians, separate sessions, GPU 31-37% busy): with React to Music on, GPU
0.93 -> 0.98 ms (Preset 1), 0.86 -> 0.97 (Preset 2), 1.80 -> 1.96 (Preset 3), about the same driven; Growth spires
driven 1.09 ms, Growth + Indents 1.21 ms. CPU thread unchanged (2.3 ms), Python calls per frame 5781 -> 5315 (the
tables are packed once per bake), GL calls 359 -> 361 (two uniforms). Contracts:
`tests/test_neon_terrain_smooth.py` (GPU, with a control that takes the cross-fade away),
`tests/test_neon_terrain_forms.py`, `tests/test_neon_terrain_reaction.py`.

## Glass, celestial body and light

Glass uses the shared Scene3D GGX/Fresnel material helpers. Vertex normals are central derivatives of the same
`basinSurface` displacement (cubic land, static detail, growth, old waves and bank taper), interpolated across the
surface. Four extra evaluations occur only for nonzero Glass strength/tint alpha on direct surface triangles;
ordinary point markers and mirrored passes do not evaluate them. Five bounded reflected directions
sample the authored sky and actual ray-hit Sun/Moon; roughness widens them. This is a procedural scene-environment
approximation, not photo capture, refraction or a new reflection target. Neon environment radiance supplies restrained
grazing highlights; optional body lighting uses the same material and coarse heightfield occlusion.
Zero-area raster normals use a finite zero-direction limit. Bare `normalize(0)`
can introduce one NaN emission texel that expands into a black bloom rectangle;
normalizing the geometric area safely prevents contamination at its source.

The existing `sun_enabled` key gates the selected Sun or Moon independently from sky intensity. Sun keeps vibrant
bands; Moon uses authored phase and a deterministic 3-D spherical lunar surface with
subtle lunar flecks and restrained crater relief on a bright smooth face. The 3-D sampling
must not introduce longitude seams, rectangular stamp repetition or camera-dependent
surface drift. The solid shaded hemisphere retains faint earthshine for
3-D form; the rejected contour-map presentation is not an alternate runtime style.
The Moon Phase slider (0..1) is operator-authored art, not real-world ephemeris,
local clock, calendar date, or orbital position. Its direction is resolved relative
to the viewing basis, so moving the scene or camera does not silently change a
selected waxing/waning crescent into another phase. 0/1 is New, .125 waxing
crescent, .25 first quarter, .5 Full, .75 last quarter and .875 waning crescent.
The Moon's 3-D crater/maria albedo remains sampled in world space and is never
an alternate phase owner. Optional orbital motion moves only the body, not the phase.

The whole Moon surface supplies soft emission following its actual lit/shaded
albedo: strong on the bright face and faint on the shaded hemisphere. Rim-only
emission was explicitly rejected as tube-like. A subordinate inner feather and
analytic exterior halo blend that broad source into the surrounding scene.
The ordinary exterior halo surrounds the full silhouette at every phase, including
the shaded limb and New Moon. Phase only gates the lunar surface lighting, the
subordinate illuminated inner feather and optional illuminated rim vertices; it must
not cut away any part of the ordinary surrounding corona.
Celestial Halo gates this emission, while its Intensity/Reactivity remain the
single glow authority. Preserve face/shadow contrast and subtle detail rather
than replacing the body with a uniform light blob. A bounded surface gain retains
headroom through maximum reactive bloom; the exterior halo keeps its musical response.
GPU tests distinguish colour
and emission, require positive surface emission, and cover New, thin/wide
crescents both ways, quarters, gibbous and Full.
Neither effect changes orbit timing, reflection/light sampling, the shared
celestial body, Sun presentation, or authored controls.
Both bodies have separate RGBA. XYZ and radius are art:
X is in basin half-widths and Y/Z/radius in scene units. Optional orbit is off by default, analytic on the existing logical
animation time around `(0, 0, -1.2)`; speed is revolutions/second. It does not affect the five camera keys or outer geometry.
The sky background is drawn continuously first, then the terrain's **real depth-only pass** erases
sky colour/emission in proportion to the same surface coverage/fade. Subsequent surface/sky-body
passes use that terrain depth, so distant stars or Moon/Sun are occluded by foreground land
without creating a separate card-wide alpha band. The translucent/glass surface retains its
material appearance while **opaque terrain coverage** blocks the sky behind it. Sun/Moon draw **after** surface colour as celestial background with LEQUAL at far depth, so the same terrain depth clips both body and halo at the horizon. Their analytic sphere retains authored apparent pose, phase, orbit, reflection and illumination; direct presentation no longer places an astronomical body in front of distant land merely because its artistic XYZ is nearby. No additional depth target, mask or timer is created. **At infinity (2026-10-24, operator: bodies must not change with the
camera):** Position X/Y/Z is where the body appears from the fixed reference viewpoint `CELESTIAL_REFERENCE`
(0, 1, 2) in front of the basin; that gives its direction and, with Size, its apparent size. Each frame
`celestial_placement` puts it `CELESTIAL_DISTANCE` (40) from the real eye along that direction with a radius keeping
its angular size, so flying, dollying or panning never moves, grows or re-phases it and its light on the land is
effectively directional (the basis for scene lighting). Presets 1-4 were converted to keep the direction and size
seen from their start views. Reflected body hits retain the authored land-volume approximation. Near-camera visible-body attenuation still prevents an enormous disc without changing world lighting or orbit.

Optional rays use `heightfield_volume_glsl.py` single scattering over the same world-space basin and authored body.
The existing sky program/quad and SceneTarget are reused after geometry; no volume texture, timer or simulation is
created. Admission requires an enabled body, enabled rays and positive strength. Disabled rays issue no volume draw.
World-height density is strongest near water/lower slopes; four light taps perform coarse terrain occlusion per view
step. High/Balanced/Performance/KAK use 12/8/6/4 view steps (at most 60 height samples per fragment). This bounded
approximation may miss thin ridges between taps and uses a bilinear land-height bound rather than exact shadow maps.
Those limitations are explicit; no hidden high-tap or screen-space fallback is installed.

Every curated preset is operator-authored, independently editable and mutable without restriction,
including Preset 1 and all experiments. The current Preset 1 serves as the present visual
comparison **only**, never a locked baseline or a golden sequence of colours, heights, values, images
or bytes. Six disposable experimental candidates explore distinct terrain, colour, surface and response
balances in authored files 4–9. The active authored directory owns the catalog; the source shipping
manifest lists packaging assets without overriding user additions or deletions. Runtime
positions compact those sparse authored ordinals, with Custom always trailing. Schema 12 moves the
historical schema-11 Custom index 1 to the current trailing Custom before default/lender/preset
resolution; older retired nonzero selections also retain live art as Custom. The independent Custom
snapshot and current authored values survive. No runtime heuristic reinterprets a new experiment as
historical Custom. Preset creation never overwrites another slot; an explicitly authorized schema
migration may update files while retaining current artistic intent. Camera pose remains excluded from art presets. Behavioral
and visual regression tests use independent, test-owned settings, never mutable curated art.

Focused regression inventory lives in `Docs/TestSuite.md`. The pre-replacement render-cost baseline is
`tools/baselines/overhead/2026-10-13_000e222e.json`; current comparative cost and visual acceptance remain in the live plan.


## Continuous sky, terrain visibility and conditional Glow Settings

The sky paints continuously across the framed card. The depth-only terrain prepass subtracts
sky/emission according to `basinDistanceFade` coverage, and body visibility is tested against
the **same** actual terrain depth. The landscape, vertices, glass, sky and celestial body must
share one opacity/depth truth. A detached horizontal alpha strip, background wallpaper showing
through opaque mountains or far geometry glowing after its surface faded is a regression.
No second render target, geometry authority, body mesh, timer or opacity control is admitted.

Glow controls sit beside what they light: **Surface Glow**, **Ridge Light Response** and **Water Line Glow**
(colour and strength) under Glow; **Celestial Halo** (Intensity/Reactivity) and **Light Rays** (Strength/Colour)
under Sun & Moon; **Starscape Beat** with Star Glow Intensity/Reactivity/Colour under Sky. Both glow colours mix in by their
alpha, so alpha 0 is the earlier look: the water lines' emission moves from their ripple palette toward
Water Line Glow, scaled by its strength (1 is the shared Surface Glow, and nothing glows while Surface Glow
is zero); beat stars move from the Stars colour toward Star Glow Colour, in the sky and in their emission,
with their brightness still from Star Glow Intensity. Spec-owned conditional controls remain
hidden when their prerequisites are disabled, retain their saved value while hidden, and
reappear on re-enablement. The Glow bucket is closed by default. The passive celestial halo
is enabled by default, while Starscape Beat is opt-in. The optional Celestial Rim
Vertices experiment is default OFF and uses sparse antialiased marks on the lit
outer rim only. Fixed angular slots fade additional marks smoothly during resize;
there is no second mesh, surface lattice, phase or glow owner.

### Clouds and nebula (2026-10-17)

Both are optional, non-reactive and live in the Sky bucket under the sky toggle; with the sky off they draw nothing.
They come from the shared sky library `rendering/gl_programs/scene3d_sky.py` (lattice noise and octave sums on the
Scene3D integer hash, `skyClouds`, `skyNebula`, each with a CPU mirror proved equal on the GPU), so another 3D mode can
take the same sky without copying it. **Volumetric Clouds** replace the flat cloud bands while on: Coverage, Softness,
Scale, Opacity and Drift, shaded from the Cloud colour toward the Sun/Moon side with a cheap look-ahead toward the
light. **Nebula** (rebuilt 2026-10-17 after operator reference photographs: the Bubble and Veil nebulae, a
cyan-cored nebula with red filaments, soft violet star clouds) is emission gas in regions with dark space between
them, gathered toward the sky the card faces above the far shore: warped, billowing gas that burns from **Nebula Rim
Colour** to **Nebula Core Colour** and toward white at its densest, ridged bright **Filaments** (soft gas at 0, thin
strands at 1), and **Dust** lanes that absorb the stars and sky behind them. Intensity, Detail, **Position** (where
around the sky it sits) and Drift complete it. Highlights roll off rather than clip, and the octave sums turn each
octave against the last so the lattice never shows as blocks. Inside a nebula the ordinary star field crowds (up to
three times as many stars) and takes on the nebula's colours. Drift is the shared animation clock only: cloud drift
slides the cloud plane, nebula drift turns the nebula about the vertical; at zero the sky is still, and no drift asks
for frames on its own. The visible sky takes the full detail; reflections, which glass samples five times per
fragment and roughness blurs, take two-octave clouds and only the nebula's broad gas and colour
(`basinSkyBackground(eye, ray, visibility, detail)`). Measured at 684×418 with GL_TIME_ELAPSED, flushed per frame
(GPU 74-98% busy with other work, 2760 MHz): plain 0.262 ms, clouds 0.294, nebula 0.361, both 0.405 ms median; the
nebula with full reflections had cost 0.858 ms. No new render target, pass, timer or texture is admitted.

**Light Rays** (2026-10-17; the invisible heightfield-volume haze pass retired from Neon, the shared primitive
stays dormant with its own tests) are screen-space light shafts from the shared `rendering/quick/scene3d/shafts.py`.
With rays admitted (body on, Light Rays on, Ray Strength above 0) the target opens with `shafts=True`; after the body
pass a sky pass (`uSkyPass==3`) draws the light's source (the disc and a soft glow round it widened by **Ray Spread**,
dimmed by volumetric clouds in front) into the shaft-source attachment at the far plane, so terrain and water left
in front leave it out. `_shaft_light` places the body on the card through `basin_item_point` (no light while it is
behind the camera) and hands the target a `ShaftLight`: reach from **Ray Length** (short beams to the whole card),
colour from **Ray Colour** times its alpha, Ray Strength and `RAY_GAIN`. The shared pass resolves, gathers twice
toward the light and the composite adds the rays only where the scene drew. Rays off draw the original programs;
turning them off again returns the identical picture. Measured at 684×418 (GPU 69-72% busy with other work):
+0.02-0.2 ms median over two runs.

**Beat stars** peak as diamond starbursts rather than dots: a sharp diamond point, four spikes that taper to nothing
inside a faint sheath, a soft halo and, toward the top of **Star Size**, four shorter diagonals. Star Size sets how far
the spikes reach at the peak (a small diamond at 0, about 36 px spikes at 1), and the burst draws back in as the star
fades. Each star swells in over `STARSCAPE_BEAT_ATTACK` (0.2 s) instead of switching on, so one beat's stars rise while
the last beat's fade. A burst shows by the lesser of its own star's and the pixel's clearance of the solid Sun/Moon, so
a hidden star's spikes never reach out past the limb and a visible star's spikes still pass behind the disc.

Beat-star admissions use the existing onset ring, sample panoramic stars within the **actual
projected framed sky**, select three spaced star cells per admitted event, and decay on the
single logical frame clock. The current onset floor is **0.224** (another 20% easier than the prior 0.28 floor; canonical source authority).
Selection spans upper, middle and lower sky bands with event-driven horizontal/vertical
strata, rather than a shallow row near the card's top. Up to four recent beats keep their
three stars (twelve cells); once three newer beats have theirs, an older beat's stars fade over 0.6 s instead of
vanishing. Release uses the original curve at a third of its first fade rate (`1.75/0.3` seconds, halved again
2026-10-17). The onset ring remembers events for `SHOCKWAVE_EVENT_MEMORY` (6 s, up to 48) so the stars' tail is
never cut; the water still draws only its newest 16 events younger than `SHOCKWAVE_LIFETIME`. Up to three candidates per star prefer clear sky around the
visible body and authored terrain; coarse terrain checks are bounded and cached by
star/view/terrain, independent of event age. This admission preference creates no depth readback.
Canonical camera/fit inputs are required; there is no alternate
tilt-only projection. Terrain and solid celestial coverage still mask hidden stars.
The terrain coverage pass erases both sky colour and star emission, so transparent
terrain materials cannot leave hidden stars feeding bloom.
Sun/Moon are also celestial background: the same depth coverage hides them behind land and water regardless
of material alpha. Their authored analytic spheres still govern apparent pose, phase, reflection and lighting;
they must not be composited as foreground lake objects or revealed through zero-alpha/glass surfaces.
Moon/Sun halo reactivity consumes already captured midband/onset signals rather than
introducing a new vocal detector. A smooth bounded drive retains pulse contrast at
high Reactivity instead of pinning most musical frames at a hard gain ceiling.
Beat stars and their bloom are suppressed behind the solid Sun/Moon disc, including
the Moon's shaded hemisphere, using its same analytic limb coverage. Hidden/transparent
bodies do not carve starless holes. Whole-surface Moon emission follows its
lit/shaded albedo, with a subordinate same-colour rim feather. The orbit-speed setting admits 0..0.025 revolutions/s.
Nothing about these authored settings creates new per-frame Settings polling or new DSP.
At **large** cards star-peak brightness/shape and Moon/Sun **reactive modulation**
need clear presence without amplifying unrelated terrain/shoreline glow.
At **small** cards crowded vertices/overlapping bloom
need physical viewport/DPR-aware antialiased point coverage and readable glow,
**never random population thinning, a blanket glow increase or edits to authored preset values**.
The viewport-scaling behavior must derive from the actual card/render-target dimensions
within the existing SceneTarget and mode-owned presentation path, maintain continuous
results across resize/zoom/aspect, preserve canonical glow/density input authority and
avoid per-frame mesh rebuilds or unrelated-mode costs. Any reopening is admitted as a new
`Current_Plan.md` item with its own size examples and hands-on GPU visual acceptance criteria.

## Landscape camera, clipping and terrain skyline

**Since 2026-10-24 Neon Lake uses the shared framed physical camera** (`core/settings/framed_camera.py`, spec
`core/settings/neon_lake_camera.py`; operator: EB's camera controls are the standard for framed 3D). A real eye
orbits the basin centre `(0, 0, -1.2)` at 3.6 (Scene Scale dollies it), pans by translating, flies with W/A/S/D
(Q/E yaw, Shift+W/S pitch), moves by Camera Position and resets with R. Turn spans **-0.75..0.75** (saturating,
never wrapping); tilt **-0.15..0.70**: 0 is a level horizon, negative looks slightly up (both loosened 2026-11-05,
`TURN_RANGE` / `TILT_RANGE` in `core/constants/neon_lake_world.py`; the eye box grew to ±14 / 0..6 round the basin).
What keeps the eye out of the scene is collision, not a pose clamp: the floor under the eye is the highest drawable
surface within `_COLLISION_RADIUS` (0.08, twice the 0.04 near plane) of it, so no near-plane corner can dip under a
slope beside the eye (`tests/test_neon_lake_camera_limits.py`: 27 extreme poses pushed down over a spiky test
terrain; with radius 0 it fails). Camera Field of View
(20°..62°, default 30°, Camera bucket) is the lens; Auto Rotate (same bucket, off by default) sweeps the view back
and forth across the turn range, easing to a stop at each end; Camera Position (same bucket) is the shared
editor, with the basin's water-level outline drawn in its eye box. The eye, not the pose, is bounded: inside a box around the basin
and at least 0.05 above the land or water under it — the heightfield cell maximum times Terrain Height with detail,
the music's actual Terrain Reaction lift, the lake's ripple crest, and the continuation from the basin edge down to
the rolling ground. Settings and flight bound with the nominal 16:9 width; the renderer re-bounds over the card's
exact width. Pan keeps only a loose composition envelope. Presets 1-4 and the canonical default were converted from
the old screen-space fit by least squares over visible terrain points and the Sun/Moon (14-26 px RMS at 1672 px; the
default also weights far-horizon points); saved live poses are reinterpreted, not migrated (R returns to the preset's
start). The live camera remains separately owned; preset starting metadata is only a seed.

The overscanned surface can cross the camera near plane under admitted views. Its shader
emits a homogeneous clip position and relies on hardware clipping rather than dividing
before clipping. Surface triangles, glass normals, point markers, skyline and celestial
apparent position must agree with the same projection/scene pose, including extreme zoom/aspect.
No second mesh or renderer is permitted to hide holes.

**Terrain to the horizon (2026-11-05).** The land no longer ends: past the authored grid's continuation it settles
into broad far hills (`FAR_HILLS`) and the whole distant world curves away gently (`DISTANT_CURVATURE` 0.22 per basin
uv squared past `DISTANT_FLAT`, was 0.38), so the horizon line is still a real terrain/sky tangency in every
direction while land reaches tens of units out. The overscan mesh reaches `FAR_OVERSCAN` (12/12/8/20 basin uv
left/right/front/back) with cells growing with distance (about 13.7k vertices), the far plane is `FAR_PLANE` (120);
coverage never fades (the camera-facing skirt fade left land floating over sky once the eye could roam), only detail
and glow settle into the haze (`basinDetailFade`). The CPU mirrors (`neon_terrain_extent.far_hills`, the Studio brush's
`neon_terrain_surface`) share the constants. Past the grid, glass takes one environment sample and land is lit
unshadowed (that far land is most of the screen). Extreme-pose renders:
`.artifacts/webp/visualizers/shockwave_grid/fidelity/20261105_fidelity_camera_extremes_final_contact.webp` (worktree evidence).

The **main mountain skyline** uses depth-tested land geometry offset narrowly in
screen space against the real surface depth; water is excluded and its **lake shoreline**
is independent. Do not reintroduce projected highest-column scans, grazing-angle paint,
general wire edges, billboard strips or a separate remote rim. The **distant** horizon
is the tangency of the same convex distant terrain. Its highlight inherits the
editable Ridge/Shore Colour and has a physical-pixel Horizon Thickness control;
zero hides the highlight while retaining land/body occlusion. Detail and emission
fade before the finite outer edge, but distant coverage/depth remain. A detached
magenta/blue ring, floating oval, flattened extension, wallpaper-alpha seam or remote
geometry edge is not an acceptable skyline. Compare physical GPU frames from multiple
camera angles, zoom scales, card aspect ratios and Glass+Vertices surfaces. Maintain the
accepted mountain and lake contours while repairing the far-right horizon. Compilation
alone cannot establish visual correctness; approval requires agent review of rendered
pixels or operator acceptance.

## Runtime lifetime, tests and acceptance

Settings opens only after the active Qt Quick display generation retires. The RUN GC policy
must thaw an active frozen generation at the stop boundary and only permit a GC sweep after
Qt, GL and thread roots have drained, while keeping the strict Python-owner destruction
barrier. A Settings -> Neon Lake activation -> Settings sequence must retire cleanly,
including after the generation would have been frozen; do not introduce a mode-specific
Settings-timer or a bypass for the display owner. See `Docs/TestSuite.md` for the maintained proof inventory; older
settings-handoff forensics are source-control history rather than a live documentation dependency.

The original Neon Lake acceptance required image/physical review of actual distant horizon, size/DPR,
large-card glow/beat response and meaningful terrain reactivity; deterministic replay and
operator real-music recordings were the required evidence for transient, vocal/midband and sustained
behavior with no bass washout. **The operator subsequently accepted Neon Lake**; these are preserved
regression/extension proof standards, not an unclosed launch gate. The operator's recordings are at
`F:\Programming\Apps\ShittyRandomPhotoScreenSaver\logs\visualizer_recordings`.
A local agent may run real-music replays and compare before/after clips. Six new experimental
editable presets must be delivered without silently replacing the operator's current Preset 1 edits; their eventual aesthetic
rejection does not invalidate verified implementation contracts. Any concrete Neon regression or admitted extension gets
a working checklist **only** in `Current_Plan.md`; this reference does not maintain a second queue. Rejected attempts and
old checkpoint evidence belong in source control / Historical Bugs, not in this live behavior reference.


## Terrain brush (2026-11-06)

The authored heightfield is painted on the Studio's live preview with the shared brush instrument
(`ui/studio/brush.py`; `Docs/Reference/Visualizer_Studio.md` §3). Settings' own terrain editor (its Top map, the
Angled / 3/4 view with the draggable Sun / Moon, `ui/tabs/media/terrain_editor.py` and `terrain_angled_view.py`) was
retired with it: the Sun / Moon is placed with its Position X / Y / Z in the Studio's Sky & Light workspace. How a
stroke paints is one owner, `rendering/gl_programs/heightfield_brush.py` (Raise, Lower, Flatten, Water; radius in grid
uv, strength, falloff, flatten height; dabs every 0.15 radii along the path, so pointer speed never changes a stroke;
exact-zero water only from the Water mode). A pointer is picked on the drawn ground through the frame's production
framed camera: the ray from the eye meets the CPU mirror of the drawn land (`rendering/gl_programs/
neon_terrain_surface.py: scene_surface`, the mirror of `basinCurve` / `basinLandHeight`: the smooth cubic land at the
scene's Terrain Height, without the music's reaction or fine detail), so a hill hides what is behind it. During a
stroke points are picked on the ground as it was when the stroke began, or a raised ridge would catch every next
point on its face and climb toward the camera.

**All visible land is paintable (2026-11-11, 1B.5).** Land the scene draws past the stored grid (the continuation and
far hills: on presets 1/2 dollied back 13-20% of the land on screen, on preset 3 26% at its start view and 87% dollied
back) had no cells to paint. A stroke there grows the grid under it through the extend owner
(`neon_terrain_extent.grow_heightfield`; whole `GROW_STEP` = 16 cells, square, toward the brush, the axis that needs
less padded toward the horizon; `MAX_GRID_SIZE` 257). On the shipped presets every land point on screen at those
views is within the cap's reach (at most 89 of 192 / 144 spare cells). The growth is **invisible**:

- The record keeps its **authored origin** (`origin: [column, row, cells]`, `heightfield.heightfield_origin`; the
  whole grid by default, so every shipped terrain loads exactly as stored). The generated landscape belongs to the
  origin: the continuation, far hills, distant curvature (`basinDistantDrop`), the fade of detail and glow, the
  waves' and ridge energy's reach, the shoreline's domain and the mark lattice are all measured from the origin's
  edge and read only the origin's own cells (`uTerrainOrigin`, `basinOriginHeight` / `basinOriginCurve`).
- Cells past the origin are an **overlay** on that landscape. A grown cell stores the height the scene drew at its
  point (zero where it drew water); the scene adds only the cell's delta (stored minus generated,
  `neon_terrain_surface.terrain_delta`, a second R32F texture `uTerrainDelta` that exists only for a grown grid),
  smoothed by the land's own cubic. An unpainted growth therefore draws the generated landscape itself. A cubic
  through seeded samples cannot: the generated land has creases along every edge cell's extrusion, and a first
  attempt that stored seeds and drew their cubic softened them visibly (12-38% of pixels changed).
- Past the grid's edge the edge's delta eases out over `CONTINUATION_DESCENT`, so paint never ends in a wall.
- The triangles split finer (to the tier's own cell) only under the **painted bounds** (`overlay_fields`'
  `painted`, stepped out to 16 cells): a finer mesh draws the generated land's creases more exactly, which is a
  visible change, so an unpainted growth keeps the very same mesh. The split is crack-free (shared edges take the
  finer side's steps; `neon_lake_basin_mesh._grown_mesh_vertices`) and the marks never move.
- The camera floor is the generated bound exactly as before; only painted cells can raise it. The authored summit
  (`maximum`, the Reaction shaper's right edge) ignores unpainted cells.

Measured (RTX 4090, 1300x750, Preset 3 grown from 65 to 257 with nothing painted, four views): against a
run-to-run floor of 0.2-0.6% of pixels differing by 1/255, the growth leaves 0.3-0.6% differing, 4-113 pixels by
more than 2/255 and 2-20 by more than 8 (single pixels inside the basin: the filtered read of a larger texture
rounds its 8-bit weights differently); the authored Extend by the same cells changes 12-38%. Every preset is held
to that in `tests/test_neon_terrain_growth.py` (mean change within 0.02/255 of the floor, under 0.02% of pixels by
more than 8, the Extend control at least 20 times more). Cost (same machine, PairedBench medians, GPU 31-57% busy
with other work, 2775 MHz): Preset 3 1.95 ms; grown to 257 unpainted 2.18 ms (the generated land plus its overlay
read for the ring's vertices and fragments; the mesh is the same 345 GL calls); painted all over the 257 grid 5.65
ms (the worst case: the triangles under the painted bounds split to the tier's cell, about seven times the
vertices). Textures: 529 KB + 264 KB (overlay) at 257 against 34 KB at 65. A brush preview on the largest grid
configures in about 75 ms (the bank-distance transform went from 128 ms to 16 ms in array form, same bytes).
Land painted past the origin is far land: it keeps the continuation's
simpler look (no shoreline line or wet fringe, detail and glow fading with distance); **Extend Toward Horizon**
still turns the whole grid into ordinary authored land (and so moves the generated landscape's start). Past the
largest grid's reach the brush refuses out loud (`Visualizer_Studio.md`, Brush).

## Layered water (2026-10-24)

Water is a layer of its own, whatever the land's surface style. **Water Shine** (Waves bucket, 0..1) mixes a tinted
body under a rippled mirror of the real visible sky into the water fill (Fresnel: dark looking down, bright at grazing
angles, so the Sun/Moon at infinity glint in it) and adds that mirror to emission. Its ripple normal scales with Water
Detail (0 = a still mirror; nothing else moves with the clock). Vertex marks belong to land: on water they fade out by
Shine 0.6, the resting water curves fade (event crests stay whole), mirrored land marks thin, and a passing crest
lifts the body itself in its palette. Waves keep travelling along
water that leaves the grid as a stream (`basinSurface`), easing out toward the horizon, so a channel painted to the
edge reads as flowing water rather than a flat dotted plain.

**Splashes were retired (2026-11-05):** the operator rejected the droplet bursts as out of place and uniform; the
lake's gentle movement is the wanted water motion. The key `shockwave_grid_splashes` is forward-retired
(`core/settings/visualizer_retired_modes.py`); no program, slot buffer or control remains. Stage onsets for stills
with `tools/neon_lake_capture.py --event`.
Item 1 below is partly delivered: the soft crest cap raised from 0.18 to `WATER_PEAK` 0.36
(`core/constants/neon_lake_world.py`; the camera floor's ripple allowance follows it), so full-height authored waves
no longer flatten to one crest.

### Reactivity calibration (2026-10-24)

Measured on five recorded songs through the real runtime (preset 4): 140-250 waves a minute, but median strength
only 0.25-0.64 because a hit counted fully only at onset magnitude 3 while the recorded p90 is 0.85-1.04.
`SHOCKWAVE_HIT_MAGNITUDE` is now 1.0 (medians 0.32-0.79, p90 0.72-1.48); Oscilloscope keeps its own accepted scale.
Beat stars keep the newest `STARSCAPE_BEAT_HELD` (6) beats lit, up to 8 fading (24 sky slots): with 1-4 admitted
beats a second, three held beats displaced every star within about a second. Their brightness runs from a visible
floor at the admission strength to full at strength 1.2, so a big hit stands out. The admission threshold (operator-
tuned easier twice) is unchanged. Strength stays volume-dependent by design (the fixed loudness scale).

## Goal-mock fidelity pass (2026-11-05; Presets 1 and 3, not yet operator-accepted)

The operator's goal mocks `references/NeonLakeGoalPreset1.png` (portrait, low/high react) and
`references/NeonLakeGoalPreset3.png` (landscape, low/high react) are the targets for Presets 1 and 3. Compare with
`tools/neon_lake_capture.py` at the mock's panel size (722x1086 for Preset 1, 1419x548 for Preset 3; the
capture's framed aperture grows with card height, so compare at the same size). Three controls were added, each
off at 0 (the earlier picture, at the renderer's run-to-run noise floor):

- **Depth Scale** (Surface, 0..1): vertex marks and ridge (skyline) lines grow toward the camera, from their
  authored physical-pixel size at `BASIN_DEPTH_REFERENCE` (2.4) scene units to at most `BASIN_DEPTH_GROWTH_MAX` (3x)
  nearer. Farther marks keep their size; lattice membership never changes.
- **Shore Glow** + **Shore Glow Colour** (Glow): item 3 below, the water-edge glow. Light along the visible
  shoreline in screen pixels (bilinear cached bank distance over open water, the .018 contour on land), a short
  lip up the bank, swelling with ridge energy; colour mixes in by alpha over the shoreline palette; its bloom
  follows Surface Glow. Tall/raised water does not exist yet, so only flat water is covered.
- **Sun / Moon Path** (Water, 0..1): an artistic glitter column on the water under the body on screen (it does not
  need the mirror angle), fading toward the viewer, streaks antialiased by their own derivative, brightened by
  the halo's existing musical drive (`basinCelestialHaloGain`). Water only, nothing without a body.

Shared fixes made on the way: Water Shine and the path cover the **wet fringe** below the visible shoreline and
vertex marks fade there as on water (a shining lake stopped in a staircase of square control cells; Presets 2/3
lakes now reach their shorelines); the skyline copy lies at least 2% of the view distance behind its surface and
fades within one unit of the eye (near land painted a ridge bar over its own face); the GPU heightfield texture
admits every canonical grid (`HEIGHTFIELD_MAX_SIZE` 257: one Extend on a 65-cell basin raised mid-frame); the
camera floor unpacks the frozen terrain payload once per payload (1.57 ms a frame on a 121-cell grid).
Preset 1's terrain is an extended grid (basin `[28, 56, 64]` of 121) whose front rows are authored dunes: the
camera stands over authored land, so its foreground crests are real silhouettes. Contracts:
`tests/test_neon_fidelity_controls.py`.

**Second pass (2026-11-05, operator: "fidelity and reactivity are not even close").** Shared, every preset:
- *Nebula* (`skyNebula`): the gas crowds along one meandering great circle (a galactic band rising diagonally from
  the horizon) and streams along it, with sparse patches elsewhere; Nebula Position turns the band round the sky.
- *Stars*: per-star magnitudes and a sparse bright layer; reflections leave stars out (rippled water smeared them
  into sparks).
- *Water*: small view-aligned ripple trains tilt the mirror and break the Sun/Moon path into thin sharp streaks a
  few pixels apart; the mirror shows the land and its glowing skyline (`basinMirrorLand`, a 30-step horizon-profile
  march); the wavelet network is broad enough to draw instead of fading; the mirror never drops below a floor
  looking down (a neon lake is a dark mirror).
- *Shoreline*: sampled per fragment from a cell-wide box over the cubic contour (vertex interpolation beaded the
  line into a chain of arcs; the raw cubic on painted cells scalloped once per cell); water within the cubic's reach
  draws its share of the line and the glow eases from the cached bank distance into the same contour, and the wet
  fringe takes water's fill and alpha, so no square cell shows as a block beside an island or cove.
- *Marks* light with the land's relief toward the authored Sun/Moon direction (bright facing slopes, dark troughs).
Presets 1 and 3 were re-authored toward their mocks (Preset 1: new extended-grid terrain with dune crests, Moon
above the far hills, dark navy ground with small pale marks and Depth Scale 0, opaque sky, band nebula; Preset 3:
nebula turned into the upper right, gentler waves 0.15). Remaining gaps are listed in `Current_Plan.md`.

**Third pass (2026-11-05; operator: only Presets 1-3 matter, Preset 2 is Preset 1 with less lattice and more
glass, goal parity is the bar).** Shared:
- **Contour Lines** (Surface, 0..1, default 0): level lines (`LAND_CONTOUR_SPACING` 0.035 world height apart) over
  the high land's real slopes, fading where they would crowd, in the palette leaning slightly to the ridge colour
  and brightening with the spectrum. Crests themselves are the skyline pass's silhouettes, whose glow now swells
  with the midband.
- **Lake**: rings lapping out from every shore (concentric round islands) from the cached bank distance; the
  wave-line network is drawn down to about 5 px apart and runs on its own slow clock (not carried by Scroll);
  water clocks run at about a third of their old pace; the mirror leans only 15% with the mesh's facets (their
  tilting triangles made the reflection jump in blotches); the Sun/Moon path is narrower and brighter and only
  mildly pulsed by the halo's music drive.
- **Horizon glow** rises from the land's real horizon (`basinHorizonElevation`, a short march over the distant
  land; programs without the land keep the old fixed horizon): with terrain reaching the horizon the old band
  sat entirely under the land.
- **Halo**: a wide soft glow spreading about a body diameter past the corona (depth-tested, scaled by Halo
  Intensity).
- **Continuation**: the grid edge settles into rolling ground within `CONTINUATION_DESCENT` (0.02..0.30 basin uv;
  it was 0.04..0.68), so edge ridges no longer extrude into long straight bands. All mirrors share the constant.
- **Beat stars** are chosen once per beat (in the view that first sees it) and stay fixed sky directions; before,
  they were re-chosen from every frame's view and so travelled with the camera.
- Glass takes its four rough environment taps only above roughness 0.12.
Motion: per moving pixel, water and land change no more per frame than the accepted baseline (Preset 3 3.2 vs
3.35/255, Preset 1 4.2 vs 4.6); Preset 1's frame mean is at the baseline (1.08 vs 1.11), Preset 3's is higher only
because its lake now covers about five times the screen.

**Fourth pass (2026-11-05).** Contour Lines became the range's **wireframe**: rows of constant depth
(`LAND_CONTOUR_SPACING` 0.03) draped over the raised land beyond the basin's near edge
(`basinContourRegion`: base 0.15..0.3 and up, basin uv y > 0), so every ridge and foothill shows its profile slice
as the mock's ranges do; the vertex marks give way to them there, leaving the dots on the dunes. Their colour
leans to the line colour, toward the palette on the peaks. Glass gains **glossy rims**: grazing glass the Sun/Moon
can see, on surfaces facing its side, catches its light along every crest (a Fresnel sheen). Water is calmer:
ripple tilt and swell lean the mirror 60% less, a passing crest lights the curves and washes the body far more
gently (they flashed in busy patches). Preset 1: four large meandering dunes (`terrain/k1.json`), glow 0.4,
ridge colour softened, shore glow 1.0; Preset 2 follows it (`scripts/sync_p2.py`); Preset 3: contour 0.8,
reflection 1.0, dimmer horizon, gentler reaction (0.12), waves 0.03, detail 0.06.

**Fifth pass (2026-11-05; operator: "a far cry, especially on stars, nebulas, the moon, line smoothness").** Shared:
- *Stars*: most fine stars sit near the threshold of sight (magnitude 0.035 + 0.965 r^6) and take only 30% of the
  nebula's tint (the mocks' blue-white dusting); a fainter fine layer; the bright layer gathers each star from the
  3x3 coarse cells (grid/16) round the pixel and ends its glow within one cell's reach, so no glow is cut square at a
  cell edge; about 5% of coarse cells hold one, a little wider and brighter. Beat stars glow a few pixels wide
  (halo 2 + 40 size^2) instead of a white blob.
- *Nebula*: the gas's fill gathers round its filaments (rope = 0.25 + 0.75 strand^4) with dark lanes between them;
  fainter veil; the hot core follows the ropes.
- *Moon*: the shaded side is a lavender grey (earthshine 0.15..0.19 of the face, still under a quarter of the lit
  face) and the halo pass adds a phase-free **limb light** inside the silhouette, rising toward the edge and ending
  in a fine rim line, screen-blended into the body colour so the face never clips (the mock's luminous crescent);
  the corona falls off exponentially over a quarter radius and saturates softly (1 - exp); the wide bloom is a
  third as strong; the lit inner rim a quarter; the silhouette is antialiased over 1.5 px (the sphere's own limb
  feather is far under a pixel and stair-stepped once the glow no longer hid it); softer terminator.
- *Line smoothness*: the surface triangles in front of the basin (basin v -0.8..0, `BASIN_MESH_FINE_ROWS`) split
  each mark-lattice cell 2x2 (`BASIN_MESH_SUBDIVISION`); the coarse rows either side fan to the extra vertices (no
  T-junction cracks) and every mark stays a vertex, so the marks are unchanged. Near dune lines no longer kink at
  lattice vertices. The mesh lattice is the Scene3D tier's (not the authored grid), so a finer authored terrain does
  not help. A whole-mesh split cost +0.5 ms at 1300x750 (vertex-bound); the band costs about +0.13 ms there.
- *Water*: short broken horizontal glints in the ridges' colours across the whole mirror, drifting slowly, brighter
  toward grazing angles and with the music, fading before their rows come under ~5 px apart (the mock's violet
  ripple strokes); two longer ripple trains survive at the lake's distance; the mirror leans more with the ripples
  on detailed water only (Water Detail above ~0.15); a passing crest lifts the body far more gently (0.18).
Preset 1: nebula turned into the upper sky (position 0.97), smaller Moon (0.175) set lower behind the hills
(y 0.88); Preset 2 follows. GPU (RTX 4090, PairedBench median): Preset 1 0.69 -> 0.83 ms at 1300x750 and
1.45 -> 1.66 ms at 2560x1440; Preset 3 0.86 -> 0.91 and 1.75 -> 1.91 ms (mostly the near band's vertices).
Motion on real music (4 s from 30 s): Preset 1 1.17 -> 1.30 /255 per frame (the glints drift), Preset 3 0.29 -> 0.28.

**Sixth pass (2026-11-06; the gaps pass 5 left: lake, Preset 1 sky, Moon, near ridges, Preset 3).** Shared:
- *Mirror land* (`basinMirrorLand`): water cells are skipped in the horizon-profile march. It counted the water's
  rest level as land, so a fragment in a swell trough (below rest level) mirrored "land" all round it: Preset 3's
  dark blob mid-lake (gone with Water Reflection 0, unchanged with Shine 0 or Glass off). GPU test with a negative
  control in `tests/test_neon_water_layers.py`.
- *Lake*: a dark mirror. Attribution showed the wash was mostly bloom from crest-coloured lines plus the water's own
  glow (crest alpha 0 put the lake at the mock's navy). Mirror floor 0.22 -> 0.12 and a darker body; the water's own
  glow a third; the ripple network faint at rest (0.06, still lit by crests and energy); the mirror leans 0.08 (was
  0.15) with the mesh's facets and a passing crest lifts the body 0.07 (was 0.18), so swells no longer wash it; the
  Sun/Moon column is broader and reaches farther toward the viewer; the glints are thinner and drift slower.
- *Ridges*: on the authored land each skyline ridge swells and thins along its length (width 0.45..1.45;
  alpha 0.3..1 where it thins), a smooth function of land position so it stays on the ground; near ridges are a
  35% softer core whose bloom carries them and breathe half as much with the midband. The distant horizon keeps its
  authored thickness. **The lift is never more than 1.45x:** it is a screen shift of the whole land, and an extra
  near-ridge widening (to 2.35x) exposed the lifted copy over a near dune's own face as a solid molten lobe in
  Preset 3's foreground (lead review); `tests/test_neon_ridge_shape.py` bounds every column's ridge band (the
  widening fails it at 42 px). At extreme settings (Depth Scale 1, thickness 3, a grazing view over dunes) the
  same exposure exists from before this pass; see `Current_Plan.md`.
- *Nebula*: streams drawn out along (0.84, 0.54) (was 45 degrees) and the band's great circle flatter, so the band
  rises at about the mocks' diagonal.
- *Moon*: an even luminous face (0.90 + 0.10 lambert, was 0.82 + 0.18); phase, emission headroom, halo and limb
  contracts unchanged.
- *Fine band*: extending the 2x near band to basin v 0.25 changed 217 pixels and left the crest's curvature measure
  unchanged (15.7 -> 15.5); not taken. The kink before the lake is where one dune's ridge ends, and the far shore's
  sawtooth is the bank's own triangle silhouette (it survives Shore Glow 0 and a wider per-fragment contour).
Preset 1: navy sky [5,7,34] and horizon [14,18,66], bluer nebula core (the soft blue stream upper left), whiter Moon
[228,228,252] with a tighter halo (1.4), brighter column (0.8), gentler waves (0.06); Preset 2 follows. Preset 3:
cooler sky/horizon, smaller halo (1.1) and rays (0.45), stronger and softer wisps, darker water, calmer water lights
(path 0.85, shore glow 0.45, halo reactivity 1.5, waves 0.025). GPU (RTX 4090, PairedBench, control-relative
unchanged: P1 293.6 -> 293.5 cf at 1300x750, 192.2 -> 191.7 at 2560x1440; P3 323.1 -> 322.5, 219.8 -> 220.3).
Per-frame calls unchanged (353 GL). Motion (4 s from 30 s, 60 fps): Preset 1 1.30 -> 1.095 /255, Preset 3 0.28 ->
0.232. Evidence `.artifacts/evidence/visualizers/shockwave_grid/fidelity/20261105_fidelity/pass6/`.

**Seventh pass (2026-11-06; the high-react look on real music, the skyline sheet).** Music vs response
(`tools/visualizer_replay/neon_lake_music_response.py`: the shared `music` step, then the lake's mean light, its
line-mesh contrast, the island and the shore per rendered frame over the song's own envelope):
- *Why loud music did not reach it.* Every continuous lake term (the ripple network, shore line and glow, contour
  energy, the ridges' breath) reads the display bars, post-AGC and Height Scale shaped: the midband sat at >= 0.95
  for 72-75% of every song (p50 0.98) and only moved in breaks, so loud and usual passages drew the same lake
  (Preset 1, 1985_loud1: lake light p5-p95 62.6-69.8 /255; loud vs quiet quartile line contrast 4.99 vs 4.82). The
  only fixed-scale drive, the waves, lit just the lines a crest crossed. And 1985_loud1 is the quietest capture on
  the fixed scale (PCM RMS p50 -22 dBFS against -16..-19 for the others, bus loudness p50 6.4 against 8.0-10.3), so
  its waves are the weakest (strength p50 0.31 against 0.72-0.96): the fixed scale rightly reacts less to it, but it
  must still visibly react.
- **Water Reaction** (Waves, 0..1, default 0, no work at 0): the music drive is read from the admitted waves
  themselves (`shockwave_music_drive`), whose strengths already carry the fixed scale (passage share, musical weight
  and emphasis): their summed strength over the last ~3 s on a compressive fixed scale (each wave eases in over
  0.25 s and out before the ring can drop it), swung 40% by the newest waves' light (rise 0.08 s, settle 0.35 s).
  On six recordings its p50 runs 0.29 (1985_loud1) to 0.71, p95 <= 0.84, never above 0.9, at most 0.045 a 60 Hz
  frame. It drives a glowing net of two crossing, warped ripple families over the water (the ripple colour leaning a
  third to the crest colour, the crest colour, whitening where they cross; convex in the drive, so quiet passages
  stay faint), a slight lift of the water body, the shoreline, shore glow, shore rings and the Sun/Moon path, and
  the ridges breathe with it instead of the pinned midband (exactly the midband at 0). Result on Preset 1: lake light
  p5-p95 71.9-99.0 on 1985_loud1 (range x4), 82.7-118.4 on anything_mixed2, 54.4-120.6 on nightsolong; at rest
  (one weak wave) the lake's p35 is [24,34,68] against the mock's [17,28,69] (was [27,35,71]: the near ridge
  bloomed at its loud strength in every passage). Contracts: `tests/test_neon_water_reaction.py`.
- *Skyline sheet* (Depth Scale 1, thickness 3, grazing over dunes): the lifted copy is pushed behind the depth its
  own face reaches over the lift wherever the face climbs on past the lift (three quarters of a cell ahead, away
  from the eye); crests within the lift keep their copy in front of the land beyond. The test's ridge band falls from
  95 px to 26; `tests/test_neon_ridge_shape.py` now covers that corner. It also trims near ridges seen grazing in
  Presets 1, 3 and 4 (239 px changed in Preset 4).
- *Far-shore sawtooth*: not the skyline (per-fragment bank classification there changed nothing) but the shoreline
  line itself (crest alpha 0 removes it, Shore Glow 0 does not); a grazing-derivative fade did not remove it either.
  Still open, see `Current_Plan.md`.
Presets: Water Reaction 1.0 on Presets 1 and 2, 0.25 on Preset 3 (its mock's high-react lake is lit swells, not a
net) with Water Detail 0.06 -> 0.03, so its motion stays at pass 6's (0.231 against 0.232 /255 on heavy1); Presets 4
and 5 at 0 (pixel-identical apart from the skyline fix). GPU (RTX 4090, PairedBench, pass 6 and pass 7 alternated in one session, control-relative): P1 291.5 -> 294.2 cf
at 1300x750, 188.6 -> 191.2 at 2560x1440; P3 318.5 -> 325.8, 220.1 -> 220.5; CPU thread unchanged (1.49 / 1.46 ms).
Overhead baseline against 9897d4f8 (visualizers): only Neon Lake moves (+1 GL call, the uniform; +51 Python calls,
the drive); Extruded Bubble's +51 Python calls come from main's EB work, every other mode unchanged. Evidence
`.artifacts/evidence/visualizers/shockwave_grid/fidelity/20261106_fidelity/pass7/`.

## Operator-authorized future water improvements (2026-10-18; deferred, baseline accepted)

These are three **new capabilities**, not permission to reopen the accepted Neon Lake graphics, change authored
Preset 1, or reinterpret existing controls. Track their admission in `Future_Work.md`; all art presets remain
operator-editable. Use one basin surface/heightfield and the existing canonical Settings/presentation authorities.

1. **Much greater water peak height plus splash.** `basinSurface()` currently computes
   `ripple = 0.18 * tanh(wave.x / 0.18) + ...`, strongly capping physical vertical water displacement
   regardless of source wave energy. The `crest = min(wave.y, 2.5)` path caps a *visual crest signal*, not
   a liquid spray or physical peak. Offer an intentionally higher, tier-bounded physical water reach and a
   connected crest/splash behavior when water climbs or breaks at the top, compatible with actual scene depth,
   reflections, shore taper, orbit and water reactivity. Avoid bright-line-only faux splashes or a global gain
   that destroys low settings. Verify very tall peaks in silhouette with impact/spray/falloff across card sizes
   and musical attack/sustain/release, and benchmark GPU cost at maximum authored settings.

2. **A heightful Water brush with falloff (volcano/fountain shaping).** Today's terrain editor treats the Water
   tool as a hard authoring of **exact zero** at its half-weight contour, while positive values are land; the
   persisted `heightfield` only stores `heights` in 0..1 and `sceneHeightfieldWater` classifies exactly zero.
   This is why raising a water region using Water is structurally impossible, rather than a missing knob.
   Extend the existing editor with a falloff-weighted water-height authoring concept that can form raised cones,
   basins, fountains and volcanic water peaks while preserving a distinct wet/dry classification: **never**
   make raised water masquerade as positive land or casually reinterpret version-1 heights as two meanings.
   An explicit migrated single-owner water elevation/mask representation (design before implementation) must
   remain deterministic, stroke/path-speed invariant and Undo/Redo/Custom/preset compatible. Edge height and
   falloff must join the existing water/shore geometry continuously, without moving ordinary dry land.

3. **Water-edge glow strength AND colour.** Existing `Water Line Glow` and its RGBA colour own moving ripple/
   water-line emission; `Surface Glow` is a shared emission multiplier, and shoreline light is a distinct
   composition term. A new independently authorable **water/shore *edge*** glow/colour is required: it must trace
   the actual wet/dry/raised-water contour (including curved or tall sculpted water), not simply tint all moving
   water lines or duplicate general Surface Glow. Keep the existing Water Line Glow's values, migration and
   consumer intact, use the canonical typed spec/default/preset path for the new controls, and test the edge with
   ordinary flat water, tall cones, distant shores, reflection and zero glow.

**Gate:** design classification and height representation first; then add editor authoring, high-reach surface
and coherent splash, and water-edge lighting as separate measurable slices. Actual operator-side physical
comparison is required before checking any item complete. No changes to production behavior are implied by
this deferred contract.
