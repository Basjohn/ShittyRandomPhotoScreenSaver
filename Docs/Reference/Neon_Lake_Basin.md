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

Tint, strength and roughness rows appear for Glass choices. Roughness is authored within .05.. .5, respecting the
shared material's .045 numerical floor. Plain vertices expose main/accent RGBA; glass vertices expose outline RGBA.
Terrain fill, crests, water, sky, stars, clouds, horizon, Sun, Moon and rays retain separate RGBA controls.
Compound spec conditions drive row visibility/enablement without a second UI or model table. Vertices are
unique points on the actual displaced surface lattice, about ten percent denser than the prior point presentation.
Quality and Surface Detail bound that lattice; points and triangles always share it to avoid hiding points beneath a different approximation. Glass alone creates no point mesh and retires an existing one. Glass + Vertices uses smaller outlined markers to keep the combined picture readable. Reflected marks draw before depth-writing water, direct marks after it; point-size and
depth-function state restore even when drawing fails.

The canonical terrain record is `{version: 1, size: N, heights: [N*N floats]}`, with `N` within 2..65 and finite heights
within 0..1. Rows run near/front to far/back. Explicit malformed records raise; missing old terrain receives the canonical
basin seed. Positive values below the normal float32 minimum are rejected so packing cannot silently turn authored land
into water. `rendering/gl_programs/heightfield.py` owns admission, float32 packing and the bilinear CPU sampler. Water is
exactly an authored sampled height of zero, independent of waves, view pose and land height scale.

The terrain editor supports Raise, Lower, Flatten and exact Water, a physically circular brush on non-square canvases, bounded brush radius/strength, per-stroke Undo/Redo,
reset and an explicit blue water preview. Loading is silent; one completed stroke saves once through the existing Custom
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
band so a crest meets the solid shore continuously. The texture uploads only changed authored data and fences
unpack/texture/sampler state. Allocation/deletion failures stay loud and owned for retry.
It creates no clock or global texture cache.

The existing Scene3D bendable mesh samples an opt-in positive cubic B-spline surface, and its
height/vertex coordinates are shared across triangles and points. The three present-day surface
styles do not enable general-purpose wire edges. Cubic smoothing cannot overshoot its local
control-height range; authored bilinear zero remains the water-classification authority.
The mode-owned terrain lattice now overscans all four authored edges, with geometrically growing
cell width away from the authored 0..1 sub-lattice. `neon_lake_basin_mesh.py` generates both triangles and actual
point markers from exactly the same axis coordinates, keeping the edited interior topology untouched. A
shader-side, deterministic land continuation joins the authored boundary, lets steep near-edge ridges settle toward subdued distant rolling ground rather than extruding indefinitely, and fades diffuse, emission,
reflection and vertices into the sky before the finite outer edge. Off-editor continuation is not another
terrain editor or an infinitely repeating tile; it never creates an additional authored lake. Distant
coverage and performance, including unusual zoom/card aspects, remain operator/GPU acceptance items.
An authored tier change replaces the one active mesh; ordinary frames allocate/rebuild nothing. Authored patch
bounds are derived once per terrain change; static conservative fitting changes only with authored terrain/view/aspect.
Audio cannot pump the fit, resize the target or move the water boundary.

The preserved Shockwave onset ring admits each serial once, spaces events by passage intensity, caps capacity and ages
on the existing logical clock. Water uses travelling crests and echo rings, with bounded displacement even when events
overlap. Land has eight separate mode-owned growth envelopes with authored rise/settle times, static surface detail
and frequency-driven lighting. Its targets use the existing passage ramp and musical level/presence gate, independently
of water-onset admission and unchanged Spectrum bars. Silence releases growth even if source bars remain retained.
Growth=0 freezes land geometry while its light can still react. The renderer consumes
immutable growth values; it does not simulate them. Disabled movement discards envelope work; re-enabling starts from
zero on the existing capture clock. Sky, celestial body and bloom remain optional. All context-local resources retire
through the normal mode owner; unchanged shared consumers acquire no heightfield work.

Active terrain growth also consumes eight mode-local spectral contrast factors. Verified
audio commit derives shaped-bar-weighted soft raw-magnitude contrast before its private
FFT storage is reused; an activation-owned lock publishes the preallocated slots together.
Logical capture applies them to its existing region targets. Authored zero/mirrored shape,
passage/presence gating and envelope timing remain authoritative. There is no extra FFT,
full raw-spectrum tuple publication or per-frame container, and other modes do not enable
this consumer. A failed input leaves the preceding committed factors intact and fails loudly.

## Glass, celestial body and light

Glass uses the shared Scene3D GGX/Fresnel material helpers. Vertex normals are central derivatives of the same
`basinSurface` displacement (cubic land, static detail, growth, old waves and bank taper), interpolated across the
surface. Four extra evaluations occur only for nonzero Glass strength/tint alpha on direct surface triangles;
ordinary point markers and mirrored passes do not evaluate them. Five bounded reflected directions
sample the authored sky and actual ray-hit Sun/Moon; roughness widens them. This is a procedural scene-environment
approximation, not photo capture, refraction or a new reflection target. Neon environment radiance supplies restrained
grazing highlights; optional body lighting uses the same material and coarse heightfield occlusion.

The existing `sun_enabled` key gates the selected Sun or Moon independently from sky intensity. Sun keeps vibrant
bands; Moon uses authored phase and a deterministic 3-D spherical lunar surface with
large basaltic maria, granular highlands and sparse crater bowls/rims. The 3-D sampling
must not introduce longitude seams, rectangular stamp repetition or camera-dependent
surface drift. The shadowed face may remain very faintly visible as earthshine, but
contributes no Moon bloom. The Moon Phase slider (0..1) is operator-authored art, not real-world ephemeris,
local clock, calendar date, or orbital position. Its direction is resolved relative
to the viewing basis, so moving the scene or camera does not silently change a
selected waxing/waning crescent into another phase. 0/1 is New, .125 waxing
crescent, .25 first quarter, .5 Full, .75 last quarter and .875 waning crescent.
The Moon's 3-D crater/maria albedo remains sampled in world space and is never
an alternate phase owner. Optional orbital motion moves only the body, not the phase.

The illuminated disc is **ordinary albedo colour**, not blanket glow emission.
A very narrow illuminated *inner outer-limb* band and an analytic exterior halo
supply the rim emission, both gated by that one phase terminator. The centre of
even a Full Moon produces no Moon bloom; the dark face can retain faint,
non-emissive earthshine and the unlit limb emits nothing. Thin waxing and waning
crescents must each remain visible and glow solely along their lit arc, not as
an indiscriminate circular aura. GPU tests must distinguish face colour from
emission and cover New, thin/wide crescents both ways, quarters, gibbous and Full.
Neither effect changes orbit timing, reflection/light sampling, the shared
celestial body, Sun presentation, or authored controls.
Both bodies have separate RGBA. XYZ and radius are art:
X is in basin half-widths and Y/Z/radius in scene units. Optional orbit is off by default, analytic on the existing logical
animation time around `(0, 0, -1.2)`; speed is revolutions/second. It does not affect the five camera keys or outer geometry.
The sky background is drawn continuously first, then the terrain's **real depth-only pass** erases
sky colour/emission in proportion to the same surface coverage/fade. Subsequent surface/sky-body
passes use that terrain depth, so distant stars or Moon/Sun are occluded by foreground land
without creating a separate card-wide alpha band. The translucent/glass surface retains its
material appearance while **opaque terrain coverage** blocks the sky behind it. Sun/Moon draw **after** surface colour with LEQUAL and actual ray-sphere hit depth; only the camera-front visible fragments pass, and bodies behind terrain are occluded. The old GREATER rear-body transmission path is retired. No additional depth target, authority, or timer is created. Reflected body hits still use authored land-volume approximation; direct on-card visibility is determined by the real overscanned landscape depth. When orbit brings the camera inside or extremely close to the analytic ray-sphere body, its *camera-visible draw* smoothly fades out before it becomes a screen-filling disc. The world position, orbit, material/environment reflection queries, and illumination are unchanged. No new sphere mesh or timer is introduced. The distant continuation is a visual surface, not a second authored occlusion volume.

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

The advanced Glow bucket owns **Surface Glow**, **Ridge Light Response**, **Celestial Halo** with
Intensity/Reactivity, **Light Rays** with Ray Strength/Colour, and **Starscape Beat** with Star
Glow Intensity/Reactivity. Sky owns atmosphere/base stars; Celestial owns the body appearance,
pose and orbit; Render owns water reflection; Waves owns Water Detail and Flow; Growth Timing
(`terrain_motion`) owns the existing timing rows. Spec-owned conditional controls remain
hidden when their prerequisites are disabled, retain their saved value while hidden, and
reappear on re-enablement. The Glow bucket is closed by default. The passive celestial halo
is enabled by default, while Starscape Beat is opt-in. A potential sparse celestial
rim-vertex overlay is only an operator-review candidate, not an existing control or
an accepted reason to add surface-wide lattice/microrelief costs.

Beat-star admissions use the existing onset ring, sample panoramic stars within the **actual
projected framed sky**, select three spaced star cells per admitted event, and decay on the
single logical frame clock. The current onset floor is **0.224** (another 20% easier than the prior 0.28 floor; canonical source authority).
Moon/Sun halo reactivity consumes already captured midband/onset signals rather than
introducing a new vocal detector. Beat stars and their bloom are suppressed behind the
Moon/Sun disc so the body fully owns its coverage, and the Moon's lit-face lift remains a
small same-colour feather near the illuminated rim rather than whole-disc emission. The orbit-speed setting admits 0..0.025 revolutions/s.
Nothing about these authored settings creates new per-frame Settings polling or new DSP.
At **large** cards only star-peak brightness/shape and Moon/Sun **reactive modulation**
need greater expressiveness: passive Moon halo and unrelated terrain/shoreline glow must
remain at their existing strength. At **small** cards crowded vertices/overlapping bloom
need physical viewport/DPR-aware effective bloom footprint, antialiased point size, spacing
and effective LOD, **never a blanket glow increase or edits to authored preset values**.
The viewport-scaling behavior must derive from the actual card/render-target dimensions
within the existing SceneTarget and mode-owned presentation path, maintain continuous
results across resize/zoom/aspect, preserve canonical glow/density input authority and
avoid per-frame mesh rebuilds or unrelated-mode costs. `Current_Plan.md` §2A contains
mutable operator-provided size examples and hands-on GPU visual acceptance criteria.
The exact changes and audio/visual acceptance gates remain in `Current_Plan.md` §2A.
The live checklist now treats Moon idle integration, Moon/Sun beat presence, celestial
star-occlusion and Starscape Beat visibility as separate **Awaiting Validation** acceptance
items. A separate experimental candidate also remains open: a **default-OFF Celestial Rim
Vertices** toggle may place sparse glowing points only on the illuminated outer rim of Moon
and Sun, but must never replace the ordinary Moon body/halo or create a second celestial
authority.

## Landscape camera, clipping and terrain skyline

The framed landscape admits canonical turn **-0.20..0.20** (roughly ±36°) and tilt
**0.17..0.58** (roughly 15°..52°). WASD and Alt+left-drag saturate rather than wrap;
Alt+right pan is bounded against scale to retain a composed portion of the basin (current
reference anchor `(0.5, 0.68)` within central `0.08..0.92` fractions). Alt+wheel scales
only the inner scene, preserving the outer bordered card and Edit/CUSTOM authority.
These **landscape-specific values are not reusable defaults**. §4A FC must share the
underlying bounded-camera capability for future framed 3D modes, with per-mode declared
limits and composition targets. Framed camera pose remains independent of art presets.

The overscanned surface can cross the camera near plane under admitted views. Its shader
emits a homogeneous clip position and relies on hardware clipping rather than dividing
before clipping. Surface triangles, glass normals, point markers, skyline and celestial
hit-depth must agree with the same projection/scene pose, including extreme zoom/aspect.
Foreground continuation fades before near-camera cutoffs; no second mesh or renderer is
permitted to hide holes.

The **main mountain skyline** uses depth-tested land geometry offset narrowly in
screen space against the real surface depth; water is excluded and its **lake shoreline**
is independent. Do not reintroduce projected highest-column scans, grazing-angle paint,
general wire edges, billboard strips or a separate remote rim. The **distant** horizon
must be derived from *visible* far terrain/surface and fade out with it. A detached
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
