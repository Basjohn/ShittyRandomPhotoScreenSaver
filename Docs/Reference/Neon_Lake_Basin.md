# Neon Lake Basin

Neon Lake Basin replaces the flat Shockwave Grid picture. The stable mode ID, settings prefix and layout profile remain
`shockwave_grid`, `shockwave_grid_*` and `3d:shockwave_grid`. Visual fidelity and musical acceptance remain live work in
`Current_Plan.md` §2A V4A. The supplied low/high mock in
`Docs/Future_Work/Additional_Future_Transitions_Package.zip` is concept provenance, **not** the
accepted artistic reference. The **operator's current** Preset 1 is the working visual comparison,
not a frozen baseline; the operator may change it whenever desired.

Neon Lake is the **reference implementation** for a reusable **framed 3D internal-camera** contract,
not a permit to copy its special-case view code into each future mode. The shared opt-in capability is a
§4A prerequisite for Extruded Bubble and other framed 3D visualizers. Preserve this mode's authored
landscape angles, existing Settings/presentation pose and card/CUSTOM behavior when promoting the common
input/bounds/projection ownership; other modes supply their own bounds and visual target. Current acceptance
and experimental preset closure are tracked only in `Current_Plan.md` §2A; the existing Preset 1 remains the
working visual reference while six new experimental presets are temporary and may all be rejected.
Every preset remains operator-editable, including Preset 1 and all six experiments. Audio reactivity
review includes deterministic and operator real-music recordings and precedes mode closure.

## Card, scene pose and input

The descriptor declares CARD / CARD_INTERIOR with independent freeform-3D CUSTOM stage geometry. The saved outer card
rectangle and logical viewport remain their existing authorities; shell policy supplies ordinary card chrome and the
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

Edit selection remains the fixed card rectangle. The internal eight-point guide and pivot use the same `basin_fit` /
`basin_item_point` projection as rendering and clamp to the card interior. They remain paint, never geometry authorities.

## Authoring and migration

`core/settings/visualizer_mode_settings.py` owns typed controls, ranges, defaults admission, UI buckets, conditions and
presentation/source projections. `core/settings/default_settings.py` owns default values. Primary Terrain contains the
bespoke lazy editor; Appearance and Waves contain the distinct material/reaction controls. Advanced Frequency Response
preserves the consumed old nodes, notches, lanes and smoothing; those audio coordinates are never relabelled as terrain.
Advanced Render supplies surface style, reflectivity and opacity; Waves owns water surface detail and flow. Sky, Celestial and Glow are separate advanced buckets.
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

The canonical terrain record is `{version: 1, size: N, heights: [N*N floats]}`, with `N` within 2..65 and finite heights
within 0..1. Rows run near/front to far/back. Explicit malformed records raise; missing old terrain receives the canonical
basin seed. Positive values below the normal float32 minimum are rejected so packing cannot silently turn authored land
into water. `rendering/gl_programs/heightfield.py` owns admission, float32 packing and the bilinear CPU sampler. Water is
exactly an authored sampled height of zero, independent of waves, view pose and land height scale.

The terrain editor supports Raise, Lower, Flatten and exact Water, a physically circular brush on non-square canvases, bounded brush radius/strength/falloff, per-stroke Undo/Redo,
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
terrain editor or an infinitely repeating tile; it never creates an additional authored lake. Distant
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
slow rise and fall) — the **shaper**, **Motion Speed**, **Rise** and **Settle**. The shaper is the shared shape editor
laid along the land's height, shoreline (left) to the authored summit (right): its curve is how strongly each
elevation deforms (it biases all three amounts), its notches split that axis into five frequency lanes (Bass ..
Treble: which part of the spectrum moves which elevation) and its arrows weight each lane. It is stored as one record
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
material appearance while **opaque terrain coverage** blocks the sky behind it. Sun/Moon draw **after** surface colour as celestial background with LEQUAL at far depth, so the same terrain depth clips both body and halo at the horizon. Their analytic sphere retains authored apparent pose, phase, orbit, reflection and illumination; direct presentation no longer places an astronomical body in front of distant land merely because its artistic XYZ is nearby. No additional depth target, mask or timer is created. Reflected body hits retain the authored land-volume approximation. Near-camera visible-body attenuation still prevents an enormous disc without changing world lighting or orbit.

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

The advanced Glow bucket owns **Surface Glow** (with **Water Line Glow** colour and strength), **Ridge
Light Response**, **Celestial Halo** with Intensity/Reactivity, **Light Rays** with Ray Strength/Colour,
and **Starscape Beat** with Star Glow Intensity/Reactivity/Colour. Both glow colours mix in by their
alpha, so alpha 0 is the earlier look: the water lines' emission moves from their ripple palette toward
Water Line Glow, scaled by its strength (1 is the shared Surface Glow, and nothing glows while Surface Glow
is zero); beat stars move from the Stars colour toward Star Glow Colour, in the sky and in their emission,
with their brightness still from Star Glow Intensity. Sky owns atmosphere/base stars; Celestial owns the body appearance,
pose and orbit; Render owns water reflection; Waves owns Water Detail and Flow; Terrain Reaction owns the land's
musical reshaping and its timing. Spec-owned conditional controls remain
hidden when their prerequisites are disabled, retain their saved value while hidden, and
reappear on re-enablement. The Glow bucket is closed by default. The passive celestial halo
is enabled by default, while Starscape Beat is opt-in. The optional Celestial Rim
Vertices experiment is default OFF and uses sparse antialiased marks on the lit
outer rim only. Fixed angular slots fade additional marks smoothly during resize;
there is no second mesh, surface lattice, phase or glow owner.

Beat-star admissions use the existing onset ring, sample panoramic stars within the **actual
projected framed sky**, select three spaced star cells per admitted event, and decay on the
single logical frame clock. The current onset floor is **0.224** (another 20% easier than the prior 0.28 floor; canonical source authority).
Selection spans upper, middle and lower sky bands with event-driven horizontal/vertical
strata, rather than a shallow row near the card's top. Two recent events retain at
most six cells. Release uses the existing curve at 60% of its former fade rate
(`1.75/0.6` seconds). Up to three candidates per star prefer clear sky around the
visible body and authored terrain; coarse terrain checks are bounded and cached by
star/view/terrain, independent of event age. This admission preference creates no depth readback.
Canonical camera/fit inputs are required; there is no alternate
tilt-only projection. Terrain and solid celestial coverage still mask hidden stars.
The terrain coverage pass erases both sky colour and star emission, so transparent
terrain materials cannot leave hidden stars feeding bloom.
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
avoid per-frame mesh rebuilds or unrelated-mode costs. `Current_Plan.md` §2A contains
mutable operator-provided size examples and hands-on GPU visual acceptance criteria.
The exact changes and audio/visual acceptance gates remain in `Current_Plan.md` §2A.

## Landscape camera, clipping and terrain skyline

The framed landscape admits canonical turn **-0.20..0.20** (roughly ±36°) and tilt
**0.17..0.58** (roughly 15°..52°). WASD and Alt+left-drag saturate rather than wrap;
Alt+right pan is bounded against scale. Horizontal movement retains the central basin reference;
the downward-looking limit retains the basin's `y=.68` reference at the top margin `.08`.
The upward-looking limit instead retains upper sky's `y=.12` reference at the bottom
margin `.92`, allowing the lake below the card when framing the Sun/sky. These are
composition bounds inside the unchanged `-2..2` pan admission; turn/tilt limits and
homogeneous/card clipping remain independent protections. Alt+wheel scales
only the inner scene, preserving the outer bordered card and Edit/CUSTOM authority.
These **landscape-specific values are not reusable defaults**. §4A FC must share the
underlying bounded-camera capability for future framed 3D modes, with per-mode declared
limits and composition targets. The live camera remains separately owned; preset starting metadata is only a seed.

The overscanned surface can cross the camera near plane under admitted views. Its shader
emits a homogeneous clip position and relies on hardware clipping rather than dividing
before clipping. Surface triangles, glass normals, point markers, skyline and celestial
apparent position must agree with the same projection/scene pose, including extreme zoom/aspect.
Foreground continuation fades before near-camera cutoffs; no second mesh or renderer is
permitted to hide holes.

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
Settings-timer or a bypass for the display owner. See `Docs/TestSuite.md` for the maintained
proof inventory and `Docs/Audits/Neon_Lake_Settings_And_Settings_Handoff_2026-10-13.md`
for diagnostic history.

Neon Lake completion requires image/physical review of actual distant horizon, size/DPR,
large-card glow/beat response and meaningful terrain reactivity; deterministic replay and
operator real-music recordings must show appropriate transient, vocal/midband and sustained
behavior with no bass washout. The operator's recordings are at
`F:\Programming\Apps\ShittyRandomPhotoScreenSaver\logs\visualizer_recordings`.
A local agent may run real-music replays and compare before/after clips. Six new experimental
editable presets must be delivered without silently replacing the operator's current Preset 1 edits; their eventual aesthetic
rejection does not invalidate verified implementation contracts. The live checklists and
closure criteria live **only** in `Current_Plan.md` §2A, not a second checklist here.
Rejected attempts and old checkpoint evidence belong in
`Docs/Audits/Neon_Lake_V4A_Historical_Checkpoints_2026-10-14.md` and Historical Bugs,
not in this live behavior reference.
