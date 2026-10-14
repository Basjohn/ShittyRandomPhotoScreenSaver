# Neon Lake Basin

Neon Lake Basin replaces the flat Shockwave Grid picture. The stable mode ID, settings prefix and layout profile remain
`shockwave_grid`, `shockwave_grid_*` and `3d:shockwave_grid`. Visual fidelity and musical acceptance remain live work in
`Current_Plan.md` §2A V4A. The supplied low/high mock in
`Docs/Future_Work/Additional_Future_Transitions_Package.zip` remains the visual target.

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

General-purpose mesh-edge wires are retired in the Settings surface selector. The lake shoreline is separately composited; a revised skyline pass now uses shifted copies of the actual land triangles against the landscape depth buffer instead of guessed highest points in projected columns. Retired surface-style strings are converted only during forward input/preset migration; the typed live spec/runtime admits **Vertices, Glass, Glass + Vertices** and nothing else. Only the curated Preset 1 remains shipped; Presets 2/3 are explicit GODZIP debris, not alternate future art targets.

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

The existing Scene3D bendable mesh samples an opt-in positive cubic B-spline surface. The wire paths are continuous
curved surface coordinates and height contours, not the tessellation's straight triangle edges. Cubic smoothing cannot
overshoot its local control-height range; authored bilinear zero remains the water-classification authority.
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

## Glass, celestial body and light

Glass uses the shared Scene3D GGX/Fresnel material helpers. Vertex normals are central derivatives of the same
`basinSurface` displacement (cubic land, static detail, growth, old waves and bank taper), interpolated across the
surface. Four extra evaluations occur only for nonzero Glass strength/tint alpha on direct surface triangles;
ordinary wires, point markers and mirrored wire passes do not evaluate them. Five bounded reflected directions
sample the authored sky and actual ray-hit Sun/Moon; roughness widens them. This is a procedural scene-environment
approximation, not photo capture, refraction or a new reflection target. Neon environment radiance supplies restrained
grazing highlights; optional body lighting uses the same material and coarse heightfield occlusion.

The existing `sun_enabled` key gates the selected Sun or Moon independently from sky intensity. Sun keeps vibrant
bands; Moon adds authored phase and restrained procedural craters. Both have separate RGBA. XYZ and radius are art:
X is in basin half-widths and Y/Z/radius in scene units. Optional orbit is off by default, analytic on the existing logical
animation time around `(0, 0, -1.2)`; speed is revolutions/second. It does not affect the five camera keys or outer geometry.
The complete landscape establishes depth **before** sky colour or celestial body. The sky background draws only at the far depth wherever terrain did not write nearer depth, so stars cannot bleed through translucent/glass terrain. Surface colour then uses the same prepass depth and continues to retain its translucent material appearance. Sun/Moon draw **after** surface colour with LEQUAL and actual ray-sphere hit depth; only the camera-front visible fragments pass, and bodies behind terrain are occluded. The old GREATER rear-body transmission path is retired. No additional depth target, authority, or timer is created. Reflected body hits still use authored land-volume approximation; direct on-card visibility is determined by the real overscanned landscape depth. When orbit brings the camera inside or extremely close to the analytic ray-sphere body, its *camera-visible draw* smoothly fades out before it becomes a screen-filling disc. The world position, orbit, material/environment reflection queries, and illumination are unchanged. No new sphere mesh or timer is introduced. The distant continuation is a visual surface, not a second authored occlusion volume.

Optional rays use `heightfield_volume_glsl.py` single scattering over the same world-space basin and authored body.
The existing sky program/quad and SceneTarget are reused after geometry; no volume texture, timer or simulation is
created. Admission requires an enabled body, enabled rays and positive strength. Disabled rays issue no volume draw.
World-height density is strongest near water/lower slopes; four light taps perform coarse terrain occlusion per view
step. High/Balanced/Performance/KAK use 12/8/6/4 view steps (at most 60 height samples per fragment). This bounded
approximation may miss thin ridges between taps and uses a bilinear land-height bound rather than exact shadow maps.
Those limitations are explicit; no hidden high-tap or screen-space fallback is installed.

The protected curated Preset 1 remains independently editable, with its file preserved byte-for-byte through this repair. Presets 2/3 are retired with explicit GODZIP debris records; future artistic presets are operator work and never frozen into test goldens. View pose is separate from artistic presets. Custom remains available.

Focused regression inventory lives in `Docs/TestSuite.md`. The pre-replacement render-cost baseline is
`tools/baselines/overhead/2026-10-13_000e222e.json`; current comparative cost and visual acceptance remain in the live plan.


## Continuous sky, depth-mask fade and optional glow (2026-10-14)

The sky paints continuously across the whole card before terrain depth admission. The depth-only terrain pass subtracts the existing sky/emission by the same `basinDistanceFade` coverage used for the surface. This keeps the wallpaper/sky alpha transition smooth at extended terrain, while near fully covered terrain erases remote stars and body light. It does not create a second target, control mesh, timer or opacity authority. Sun/Moon pass later against the actual shared depth and the existing camera-proximity culling; the accepted depth-tested terrain skyline remains a distinct physical silhouette. A faint extra rear-terrain contribution is provisional until visible GPU proof.

The advanced Glow bucket owns existing **Surface Glow** (emission), **Ridge Light Response** (musical ridge lighting), **Celestial Halo** with Intensity/Reactivity, **Light Rays** with Ray Strength/Colour, and **Starscape Beat** with Star Glow Intensity/Reactivity. These are a UX regrouping of existing keys, not new presentation, DSP, default or preset authorities. Sky owns atmospheric and base star colour; Celestial owns body appearance, pose and orbit; Render owns water reflectivity; Waves owns Water Detail and Water Flow. The timing-only advanced `terrain_motion` bucket is labelled **Growth Timing** without changing its canonical key. When Sky or the celestial body is disabled, their dependent Glow rows hide; switching them back on exposes the exact retained values. The generic spec `when` condition evaluator now accepts conjunctions of declared controls and evaluates them on load as well as live. The Glow bucket stays closed by default. Celestial halo is enabled by default; Starscape Beat remains opt-in. The halo draws from the same analytic sphere (not a second disc) and responds moderately to already captured midband presence and onset envelopes; it is **not isolated vocal detection**. Beat-star positions come from the established panorama cells, select up to three spaced stars per admitted event, decay on the same logical frame clock and use no extra audio or render owners. Star halo evaluation is spatially culled when possible. The initial .85 strong-beat filter was too restrictive; after the operator accepted the actual star glows, the admitted onset threshold was reduced from .35 by 20% to **.28**. This only changes admission: three star positions, their gentle fade and existing ring timing remain unchanged.

The celestial orbit-speed authored slider now admits 0..0.025 revolutions/s, not the old 0..0.15. Existing saved out-of-range settings are admitted through the one canonical typed spec; curated Preset 1 is unchanged. Nothing about glow values is a fixed golden preset target. Physical GPU validation remains required to ensure the sky seam is gone, the horizon detail is tasteful and the glow is visible without flare or dual-display regression.

## Landscape camera and skyline correction (2026-10-13, awaiting operator validation)

The Shockwave view keys retain the sole presentation-spec authority, but this framed landscape now
admits turn -0.20..0.20 (roughly +/-36 degrees) and tilt 0.17..0.58 (roughly 15..52 degrees).
WASD and Alt+left-drag saturate at those limits rather than wrapping; other Scene3D modes keep
their original orbit behavior. Internal pan is admitted jointly with scene scale through the
existing presentation configuration path, so gesture, zoom and reload apply the same bounds;
its current conservative basin reference is (0.5, 0.68) in scene-interior fractions, kept
inside the central 0.08..0.92 view. This bound needs operator verification for extreme
custom terrain/zoom, and may be refined without adding competing geometry/preset authorities.
The card and authored terrain are unchanged.

**Overscan near-plane correction:** the broad continuation necessarily contains lattice
vertices at/behind the viewer at some permitted poses. Its vertex shader must emit a true
homogeneous perspective position, with the camera-distance numerator never divided before
hardware clipping. `basinClip` uses the same field/fit/pan/scale mapping as the unchanged
inner-scene projection while supplying `clip.w=(camera-viewZ)/camera` and a coherent
near/far depth. Moon/Sun body depth uses the same mapping so the existing body depth prepass
and transparent scene composition remain coherent. Geometry/Glass/Vertices share the same
position and depth; there is no second renderer or mesh. The front continuation now also
fades before the camera-side skirt endpoint so the near-clipped ground cannot hide the
lake. A real Windows GPU check is REQUIRED after the reported catastrophic diagonal sheets
in the previous 2026-10-13 handoff. A GLSL compilation or static test is not visual proof.

The land-facing fragment now includes an optional-on-existing-controls, thin grazing-angle
contour on visible raised terrain, tinted from `shockwave_grid_crest_color` and gently driven
by the existing ridge audio energy and `shockwave_grid_glow` emission. This is a projected
silhouette approximation, not a guaranteed one-pixel binary sky/terrain mask; whether it
traces all desired far hills without internal highlight clutter requires real rendered review.
The original lake shoreline remains independent.

**Operator direction:** Preset 1 is the only useful current visual starting point. Do not
regenerate or retune it. Additional simplification of Surface Style/other controls, possibly
retiring interior wire edges in favour of the lake and skyline contours, is a separate future
slice and is NOT implemented by this correction. No GPU parity or 3D Detail cost claim is
made until Windows GL/dual-display tests run.


## Operator check: 2026-10-13 second photographic pass

The operator confirmed the original catastrophic perspective sheeting was repaired and the
main endless landscape and bounded camera now work, subject to a narrow corner coverage gap
at an oblique angle. A follow-up source slice increases left/front overscan, moves the front
visibility fade outward, and makes remote continuation relax towards rolling terrain instead
of indefinitely copying tall border hills. Same GPU mesh/point lattice and renderer owner.

The operator requested a few degrees more flattening/upward look: the canonical Neon-only
minimum tilt is now 0.17 (15.3 degrees), with existing maximum, turn and pan unchanged.
This is a bounded camera range, **not** an assertion that every card scale or edited
terrain can never expose sky at its boundary. Physical verification remains required.

The skyline from the first slice barely appeared. The follow-up strengthens the high-land
view-grazing response but it remains a shader-side **rim approximation**, not an exact
screen-space terrain-versus-sky contour. Do not mark the final clean single-stroke skyline
accepted or retire this requirement without operator inspection. Do not respond by adding
mesh-triangle edges or a new setting category.

Shader compilation/link errors are already raised by the GL program owner. A proposed
future `--shaders` diagnostic mode should be opt-in, context-local, event-driven (compile/
link, GPU API debug messages, program labels/admission and once-per-transition state),
with bounded sidecar output and no GL polling/readback or per-frame debug overhead. It
cannot discover an artistically incorrect, successfully compiled shader from logs alone.

## 2026-10-13 follow-up, awaiting operator render proof

- The **projected-column skyline attempt was physically rejected** on `image(20261013-215744).png`: its maximum-per-column logic produced disconnected magenta horizontal boxes unrelated to the actual terrain/sky silhouette. Superseding repair draws the same terrain triangles as a thin screen-space upward offset (1.8 physical pixels), biased behind the real surface in the original depth buffer. Water is excluded by its existing authored-zero classification. There are no scan columns, extra mesh, or mesh-triangle edge lines. This new edge is still **operator-unvalidated** at multiple angles and must not be marked accepted simply because the shader compiles.
- Distant land now descends from the authored boundary over a shorter UV transition into low procedurally varied terrain, reducing the visibly repeated border hills. The 0..1 authored heights and water ownership remain untouched.
- Sun/Moon receives a small analytic exterior halo in its existing depth-tested sky/body pass, with a modest response to the already captured spectrum midband (not a new voice detector). Position, lighting, scene reflections and near-camera body visibility culling keep one authority.
- Primary controls retain the real land-growth strength; Rise/Settle timers live under Advanced Growth Timing (unchanged `terrain_motion` bucket key). Wire Density is now Surface Detail, Terrain Lines is Shoreline Colour, Surface Fill is Base Opacity. Distinct DSP and colour owners remain independent. The seven surface style combinations and generalized mesh wires are retired; old values are rewritten only by canonical persisted-input/preset forward migration, not by a permanent runtime Choice normalizer.
- **Preset 1 is the only protected and shipped curated Neon Lake preset.** Slots 2 and 3 are retired explicitly by manifest debris instructions. The Custom slot remains supported; a previous selection index 1 is indistinguishable from the newly compacted Custom index 1 without version metadata, so older selections should be manually reselected if necessary. No old authored preset values are frozen into tests.

## 2026-10-13 late follow-up: sky occlusion, star accents and editor brush (awaiting operator pixels)

- **Settings crash from `logs6a63dcda0b6.zip`:** the advanced `terrain_motion` bucket was added to the spec but missing from canonical `ui.visualizer_bucket_states`; this produced `KeyError: 'shockwave_grid:terrain_motion'`. Add the closed-by-default key to the sole UI defaults authority, not a fallback that hides future declaration mistakes. Focused test now checks that all declared Neon buckets exist in canonical defaults.
- **Thick-glass terrain occlusion:** sky is now drawn against a depth-only prepass of the same landscape in all sky/body-enabled cases; no Sun/Moon or stars through hills. The prior GREATER pass drew distant body behind foreground geometry, so it was removed. The optional halo remains the existing analytic body effect, subject to the same depth.
- **Skyline:** the previous max-projection line strip is removed. A land-only screen-space silhouette uses the same displaced surface mesh with depth test; the lake has its independent shoreline. This is a physical rewrite, NOT operator acceptance.
- **Starscape Beat:** one opt-in checkbox under Glow (moved from Sky in the 2026-10-14 UX regrouping) (default OFF, preserving Preset 1). The existing Shockwave onset ring selects three spread-out panoramic stars per admitted powerful event, at most two concurrent hits, with smooth decay over about 1.75 seconds; no new DSP, clock, timer, burst owner, or global consumer work. Glow uses the sky emission attachment, not a screen-positioned particle. Appearance on real music must be checked by the operator.
- **Terrain brush:** the painted falloff and cursor preview now share a circle measured against the shorter physical canvas dimension. The saved N×N heightfield representation, Undo/Redo and Save/Cancel remain unchanged.
- **Retired Edges values:** forward migration runs on persisted settings and saved preset ingestion; the canonical live Surface Style Choice accepts only the three supported styles. Legacy strings are not read by the live mode shader or Setting spec. No other mode gets migration logic.
- **Verification:** pure-Python tests, shader compile/link and uniform checks performed without environment-variable mutation. Windows GL pixel proof and workload/dual-display acceptance remain outstanding.

## 2026-10-14 diagnostic lifecycle, visible beat stars and horizon (pending Windows validation)

The Settings dialog is built only after Quick display retirement. Diagnostic log
`logs6a63dcda0b9.zip` establishes two very different outcomes: the initial
Settings handoff completed before the 45-second RUN `gc.freeze()`, while the
second one failed after the frozen live generation had activated Neon Lake.
The existing RUN GC policy's frozen cycles could not be collected before the
strict destruction barrier; the previous policy stop/unfreeze was too late (at
application exit). The same GC-policy owner now thaws on stop, and authorizes
**one collection after every Qt/GL/thread root is gone** if outstanding Python
owners survive. This is not per-frame GC, not a barrier bypass, and not a second
retirement authority. A later Settings transition cannot re-freeze the newly
constructed generation; the startup 45-second shot is gated on actual RUN state.
Physical repeated pause/activate/return testing remains mandatory.

The opt-in beat-star cells now sample exact world rays from the existing framed
view matrix's CPU-equivalent scalar parameters (fit, orbit, internal scale/pan,
card aspect). Three spatially separated visible sky sectors select nearby bright
stars from the unchanged panorama. They remain true panoramic stars, retaining
existing onset-ring animation; no extra buffers, analysis owners or timers. The
initial diagnostic Settings snapshot had Starscape Beat disabled; later edits
might have changed it, so this log alone is **not** proof either way about the
activated mode's enable gate. To validate on Windows, activate the
checkbox under Glow and compare at strength/reactivity 1.0 against strong real
onsets from the existing operator recordings.

The earlier latitude-dependent sky-alpha band was physically rejected: it created
an independent, ruler-straight wallpaper-opacity boundary. Sky coverage is now
uniform across its own scene; only its *colour* has a dusk gradient. Terrain
coverage/fade remains the one geometry authority. The distant skyline must no
longer override that fade by inventing emissive geometry after terrain vanishes.
Three extremely thin cloud-latitude strokes are also replaced with broken,
undulating wisps, without additional noise textures or timers. The accepted
foreground mountain contour is unchanged; the authored 0..1 terrain remains
unmodified. The complete horizon remains **unaccepted pending actual render-image
inspection by an agent or the operator**.

## 2026-10-14 latest operator checkpoint (two open items only)

Operator confirms the frozen-runtime Settings crash no longer reproduces, the
Starscape Beat glows are visually good, and the main terrain silhouette is accepted.
Beat entry floor is lowered 20% (.35 → .28) without changing emission/decay or the
underlying shared onset stream. The sky's latitude-alpha transition and the
artificial far-outline radiance floor, both capable of constructing false or
partial horizon lines, were removed. Narrow unbroken cloud bands are now broken
up along their authored sky coordinates. These are source repairs **not visual
proof**: rendered horizon acceptance remains open. The only other open Neon Lake
item is the terrain-reactivity redesign, with real-music recordings and the
mode-owned DSP boundaries preserved. See `Current_Plan.md` §2A for the two active
checks and the archived historical checklist for all earlier work.
