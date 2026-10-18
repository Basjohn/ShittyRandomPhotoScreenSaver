# Extruded Bubble: target contract and shared-primitive inventory (§4A G0)

Status: **G0 target contract** (2026-10-17). `Current_Plan.md` §4A/§4B own sequencing; `Scene3D_Resources.md` owns the
shared resource contracts; `Docs/Guardrails/Bubble_Temporal_Fidelity.md` (BTF) binds the reactivity. This file records
what the operator's mocks demand, what the shared Scene3D layer already provides, and which primitives must be proved
(in order) before an Extruded Bubble renderer exists. It is not an implementation of Extruded Bubble.

## 1. Visual target (operator mocks, `tmp/Bubbleexamples`, 2026-10-17; informational mocks 2026-10-18)

Seven frames in `tmp/Bubbleexamples` (three looking up toward a sunlit surface, one with wake tendrils, the abyss, camera
down, the diagonal orange stream) plus two annotated **informational mocks** (`tmp/Informational mock.png`,
`tmp/Informational mock 2.png`, blue and copper) whose detail panels name each material requirement: broad specular
from the light with inset peaks, real front/back double rims with Fresnel and colour separation, spherical volume with
refracted background, merged bubbles with continuous surfaces, wide soft shafts, and dense micro-bubble trails
("no ribbon/sperm lines"). Where a mock shows a seabed or ribbons, the operator's later rulings below win.

| # | Element | What it must look like | Measurable goal |
| --- | --- | --- | --- |
| T1 | Bubble shell | Thin clear film: dark-ish interior that shows the water behind it slightly bent, a bright Fresnel rim, one or two sharp specular glints, faint iridescent (thin-film) fringes toward the rim | Rim brighter than centre at every size; transmission bends the background (not a flat alpha disc); iridescence varies with view angle and film thickness |
| T2 | Silhouette and size range | Perfect circles from a few pixels to a third of the card; touching doublets/triplets | Exact sphere silhouettes at any size (no tessellation facets), depth-correct intersections where two bubbles touch |
| T3 | Overlap | Bubbles in front of and behind each other, each still visible through the others | Order-independent: the same picture whatever the draw order (G3A) |
| T4 | Depth and focus | Near bubbles large, soft and bokeh-like; far ones small and crisp; a few hundred micro-bubbles in columns | Per-bubble defocus by depth; thousands of micro-bubbles within the tier budget |
| T5 | Water above | Bright Snell's-window surface with moving ripples and refracted sunlight at the top of frame | Animated surface normals, total internal reflection outside the window, brightness falling off with depth |
| T6 | Light shafts | God rays from the surface fanning down, broken by the surface ripples | Reuse the shared `LightShafts` (landed 2026-10-17) with a surface-pattern source |
| T7 | Below | **A palette-coherent murky abyss, not a seabed** (operator 2026-10-17, supersedes caustic seabed) | Darker with depth; the seabed primitive stays unused by Extruded Bubble |
| T8 | Trails | **Discrete tiny-bead trails and rising chains** (operator: "no ribbon/sperm lines", supersedes wake ribbons) | Individual micro-bubbles; G4 ribbons are not demanded |
| T9 | Water volume | Blue absorption and in-scattering with distance; darker abyss | Distance fog in the medium's colour, deeper = darker |
| T10 | Camera | Framed internal camera that can look up, level or down | Shared FC capability with Bubble-specific bounds |

Not in the target: hard cast shadows (no receiver shows one; the seabed's light is caustic, not shadowed), GTAO,
volumetric smoke/fire, screen-space reflections.

## 2. Reactivity: its own simulation (operator 2026-10-18, supersedes "reads original Bubble")

Extruded Bubble is a real mode with its **own** logical simulation: a 3D population (large/mid bubbles, small
bubbles, bead chains, fizz, particulate) with its own spawn, streams, drift and sway, collisions (Fuse / Pop /
Bounce), breathing and reactivity, advanced by its own frame runtime from a logical tick hook on the **sole Visualizer
clock**. It reads the existing audio feeds (fixed loudness, energy bands, transients, the event scheduler) and adds no
clock, capture, DSP, floor or renderer-owned simulation. Original Bubble is only a guideline, for gradients, drift,
breathing motion and visual smoothing, nothing more: never shared code, settings or a projection, and Extruded Bubble
is free to be better and unique (operator 2026-10-18). Original Bubble stays untouched and its replay unchanged. The renderer draws the simulation's immutable frame snapshot.

## 3. Inventory: what the shared layer already has

*Superseded 2026-10-18 by the G0 gate status in `Scene3D_Resources.md` (depth texture, OIT, probe, traced shells,
defocus and HDR now exist). Kept as the 2026-10-17 starting point.*

| Need | Existing owner | Gap for the target |
| --- | --- | --- |
| Multisampled overlay target, emission, bloom | `SceneTarget`, `BloomChain` | Depth is a renderbuffer: nothing can sample scene depth (T3 compositing, T4 defocus, soft intersections) |
| God rays | `LightShafts` + `SceneTarget.shaft_writes` | None (a water-surface source is the consumer's) |
| Per-frame instance data | `StreamRing`, `UniformBlock`, std430 `Scene3DStorageLayout` | None |
| Large populations | `CompactedPopulation`, compute seam | None for thousands of micro-bubbles |
| Camera-facing sprites/streaks | `particles.py` (additive, no depth) | Additive light only: cannot draw depth-correct transparent shells |
| Materials | GGX/Smith/Schlick, environment BRDF (`scene3d.py`); thin-layer refraction/dispersion (`refraction.py`, `spectral.py`) | No sphere-shell thin-film interference; refraction samples a photograph, not the rendered scene behind |
| Environment light | `BackdropEnvironment` (photo copy) | No procedural underwater environment (surface, window, caustics, depth falloff) |
| Noise | `scene3d_sky.py` lattice noise/fbm on the integer hash | Reusable for ripples/caustics |
| Framed camera | Neon Lake view orbit/fit/pose (mode-local) | §4A FC: promote to one shared opt-in capability |
| Shadows | Planar/directional silhouette primitives | Not demanded by the target (see §1) |

## 4. Primitive order (each proved on its own harness, dormant when unused)

1. **G1a: sampleable scene depth.** Optional depth *texture* attachment on `SceneTarget` (multisampled when the
   target is), resolved on demand to a linear-depth texture; renderbuffer path unchanged for every consumer that does
   not ask. Enables G3A, per-pixel thickness/soft intersections and post defocus.
2. **G1b: background copy for refraction.** The resolved opaque scene (and depth) captured once between the opaque and
   transparent passes, so transparent shells sample what is actually behind them.
3. **FC: shared framed camera** (plan item), with Neon Lake unchanged pixel-for-pixel.
4. **G3A: weighted-blended OIT** inside `SceneTarget` (accumulation RGBA16F + revealage R16F, one resolve into the
   composite), emission/bloom coherent, opposite draw orders identical.
5. **Sphere impostors:** instanced, ray-traced spheres in the fragment shader with exact depth (`gl_FragDepth`),
   exact silhouettes at any size and analytic normals, for shells and micro-bubbles alike; a defocus term per
   instance (radius grows by its circle of confusion, the shell softens) for T4.
6. **G3B: shell optics.** Thin-film interference (spectral, angle- and thickness-dependent), Fresnel, rough
   transmission and refraction through the shell from the G1b copy; dispersion only if the target needs it.
7. **Underwater environment library** (`scene3d_water.py`, import-safe GLSL + CPU mirrors): surface ripples, Snell's
   window, caustics, absorption/in-scatter by distance; the shafts' source pattern.
8. **G2 shadows:** not demanded; recorded as deferred unless EB1 finds a receiver.
9. **G4 ribbons:** only if the wake tendrils (T8) are accepted.

Each step ends with real-driver pixel tests, resize/retirement and dormant-zero-cost proof, an overhead baseline
comparison (`tools/overhead_baseline.py`) and its lessons appended to `Transitions.md` "3D foundation lessons".

## 5. Baselines

Recorded before any of the steps above: `tools/baselines/overhead/2026-10-17_13f65941.json` (after the light-shafts
commit 61d73602; other processes' CPU 54%, GPU 72% busy, 2775 MHz, all passes admitted). Compared with the 2026-10-11
baseline (which predates control-relative timing), transitions moved only by +2 Python calls per frame; Neon Lake's
preview rose from 0.135 to 1.52 ms GPU and 146 to 338 GL calls with the week's sky, reaction and ray features, and
Oscilloscope's GL calls from 17 to 110 with its rework. Later steps compare against the 2026-10-17 file.

## 6. Progress

- G1a/G1b (sampleable depth, background capture): landed 2026-10-17 (`SceneTarget(depth_texture=...)`,
  `background()`); see `Scene3D_Resources.md`.
- Sphere impostors: landed 2026-10-17 (`scene3d_spheres.py`).
- G3B optics (`scene3d_optics.py`) and the underwater environment library (`scene3d_water.py`): landed 2026-10-17.
- Composition lab (scratch, 2026-10-17): every primitive above composed into one underwater scene matched the mocks'
  structure (round translucent bubbles with rims, highlights and clear interiors; soft near bubbles; micro-bubble
  columns; streaky god rays from a glowing rippled window) at 0.125 ms GPU (960x540, 4x MSAA, 1,081 bubbles). Its
  lessons are in `Transitions.md` "3D foundation lessons"; `waterWindow`, `waterSunBelow` and `sceneDefocusRadius`
  were promoted from it. Remaining before EB2/EB3: FC (shared framed camera).
- G3A (weighted-blended OIT): landed 2026-10-17 (`SceneTarget(oit=True)`, `transparent_writes()`,
  `SCENE_OIT_GLSL`).
- Lab bubble look (2026-10-17): one layered model (interior through the lens, glass wall, rim, highlights, wall
  reflections, defocus) tuned on `--card` (mock 2's bubbles at measured positions and sizes) against the mock at full
  zoom; rising bead chains; scene-derived colour; screen-space highlights and soft sparkles. Not at parity yet:
  the abyss and camera-down views (crisp giants with violet rims, sparkle-dense water), wake ribbons, merged doublets
  as the mocks show them, and chains that vary like the mocks'.

- Lab shading rebuilt on real optics (2026-10-17): bubbles traced through a hollow glass shell
  (`sceneHollowSphereTrace`), every path looked up in a `SceneProbe` of the scene and the captured frame; HDR scene
  (`hdr=`), near giants in a `DefocusLayer`, 3D particulate drawn into frame and probe, spheres round on screen.
  Cost: the lab captures a 512 px probe every frame (~6 ms GPU at 1672x941 in total); a renderer would capture it
  smaller or every few frames. Still far from parity on every mock: shells lack the mocks' busy reflected detail and
  crisp starburst sparkles, wakes do not read as water traces, mid bubbles are too sparse and too regular.

## 7. Recovery status (2026-10-18; governing brief `Docs/SRPSS_Extruded_Bubble_Local_Source_Recovery_REVISED_2026-10-17.zip`)

The brief's audit (C01–C11) of the local lab `tools/labs/extruded_bubble_lab.py` is the work list. Status is recorded
here and updated per stage; nothing below is parity.

**Accepted, preserve (no population/surface retuning while fixing glass):** bubble density and size bands, rising bead
chains, tiny-bead trails, ember particulate/dust in the copper scene, the rippled sunlit surface.

**Failed (operator, four blockers in order):**
1. Specular: shells read matte or carry one edge tick; mocks have broad curved highlights toward the light with inset
   hot peaks and smaller wall glints.
2. Double rim: uniform concentric hoops; mocks have distinct front/back wall events whose width and brightness vary
   with the light, with Fresnel and colour separation.
3. Roundness: flat tinted interiors, vertical streaks, flat giants, merged pairs shaded as separate spheres.
4. Shafts: thin separated pencil beams; mocks have broad soft volumetric cones.

**Source defects (proven from code) and remedies:**
- C01 `uEdgeSoft` spread the eight rim sub-rays over `1 + 0.06·pixels` pixels (12× at 190 px): a size-scaled smear,
  not anti-aliasing. Remedy: A/B against 0, then pixel-bounded filtering only.
- C02 dedicated glint pass compiled but gated off in every variant; probe sun term not traced to the pixel. Remedy:
  analytic finite-area light lobes on every shell interface (broad + narrow), traced by diagnostic modes.
- C03 reversed-edge `smoothstep(0.85, 0.2, c)` (undefined in GLSL). Remedy: explicit monotone inverse.
- C04 film hue at a fixed 0.75 incidence. Remedy: angle-dependent film with footprint-limited variation.
- C05 cluster normal computed then discarded (a member sphere shaded instead). Remedy: shade the union surface point
  with its SDF normal.
- C06 no `gl_FragDepth`: quads depth-test at their plane. Remedy: GL occluder tests, then correct-depth writes that
  keep transparent depth-write rules.
- C07 glass-over-glass refracts only the opaque capture. Characterise before any architecture change.
- C08 eight full shell traces × 32-tap gathers on rims. Remedy: measured per-pass timing, bounded footprints.
- C09 blanket `uInnerBlur` (0.6 of the radius) flattens interiors; inward rim-ray clamp may draw a band. Remedy:
  separate lens displacement from defocus; test the clamp.
- C10 bubble proxy glints in the probe may outshine real lights. Remedy: rank real sources first.
- C11 the lab is a static frame (`uTime=4`); dynamic fidelity is proved only at integration (original Bubble snapshots,
  real-music recordings in `logs/visualizer_recordings`), behind the §4A/V5 gates.

**Stages:** P0 baseline captures and timings → P1 correctness (C03, C01, C05, C06) with diagnostic views → P2 specular
→ P3 double rim and curvature → P4 shafts alone → P5 all-scene validation and performance. One variable family per
checkpoint; every stage compares mock | previous | candidate on all seven scenes plus 1:1 glass crops.

**Stage results (2026-10-18; evidence `tmp/release_media/recovery/`, mock | baseline `e2b12cd3` | candidate):**
- P1 correctness, landed: C01 rim spread removed (the same-scene A/B showed stippled bands; no cost saving), C03, C04,
  C05 (clusters shade the union surface; normal diagnostic continuous through the neck), C06 depth writes. Diagnostic
  views `--diag=1..5`, per-pass GPU timestamps, `--set` same-scene overrides, `--yaw` orbit.
- Blocker 1 specular: **improved, not accepted.** Analytic finite-area light lobes (core + shoulder, footprint-widened,
  energy kept) on every mirrored path, world-fixed per scene, inset from grazing; the probe filtered by the tangential
  footprint (the radial one averaged the hemisphere into the rims). Bubbles now carry highlights toward the light and a
  second on the far wall; operator called the card sweep "an exceptional step". Still missing: the mocks' many smaller
  reflected highlights and busy reflected detail inside the wall.
- Blocker 2 double rim: **partly improved.** Rims vary with the light round the bubble; they are still concentric and
  too regular; a single interface for small bubbles was tried and rejected (striped marbles).
- Blocker 3 roundness: **improved.** View-through blur 0.6 → 0.25 radius gives dark, clear interiors with curved light;
  clusters use the union normal. Giants remain soft; interiors lack the mocks' refracted scene detail.
- Blocker 4 shafts: **improved for mocks 1–4** (broad soft cones from a lower-frequency source, soft threshold, slow
  variation); deep scenes keep their beams. The upper frame is hazier than the mocks.
- Cost (1672x941, 4x MSAA, RTX 4090 at varying clocks): shells 1.2–4.0 ms, clusters 0.2–0.8, near defocus 0.4–1.4,
  shafts 0.1–0.5. The probe's 6–10 ms timestamp is the lab's Python GL submission (8.3 ms CPU vs 0.18 ms GPU drain);
  a renderer with cached state would not pay it. The equirect environment pass was dead and is gone.

**Second pass (2026-10-18, operator checkpoint "a long way"; evidence `tmp/release_media/recovery/p6/`, mock | session
start | now):**
- Shafts (mocks 1–4): the depth march over a surface pattern averaged many columns along each ray, leaving narrow,
  separate pencils (operator: "narrow/disconnected"). Now one fan from the sun: many fine and medium rays by azimuth
  round the world sun axis (fixed in the world through orbit), soft contrast, hanging below the sun, fading by about
  two thirds down, over a faint march. A first version with a few solid wedges was further from the mocks (operator)
  and was replaced. The haze between beams was the water surface: ripple flecks far outside Snell's window; the bright
  surface is now confined to the window (the mocks' bright band ends at its edge, ~41° elevation).
- Luminous glass (mocks 1–4): measured on the mock 2 card, the mock's rim and inner zones are 2–3x and 1.1–1.9x the
  water beside them; ours were 1.6x / 1.0x. Reflection fill 0.5 → 2, neighbour glints 2.5 → 10.
- Face reflection per scene: an air bubble's face mirrors ~2%; the lab's wall index made deep-scene faces milky
  ("glowing pearls"). Deep scenes and mock 6 now 0.2–0.3, with the light's own reflection kept whole (a faint mirror of
  a very bright source is still a bright highlight). Mock 6's amber fill was the probe sun's broad secondary lobe.
- Abyss: caustic veils (the shared caustic cell edges on three depth sheets, drawn out along the stream) and teal
  water lifted below (open-water colour measured per ninth of the frame). Camera-down gets no veils: its mock's net is
  the seabed caustic the operator excluded.
- Mock 6: the smooth backdrop dust glow was the muddy band smear; the bands are now glittering ember streams.
- Near giants: the defocus layer's fixed taps turned highlights into striped blocks; highlights now become round bokeh
  discs (shared `DefocusLayer`, regression bar in `test_scene3d_defocus.py`).
- Codex audit: requested by the operator; the bridge is pinned to a Codex executable an app update removed
  (`bridge.json` `codex_executable`), so the audit was done here.
- Still unsolved: mock 3's near giants read as bright crescents, not full soft discs with bead bokeh; the mocks' crisp
  thin white rim outline (ours a softer band); mocks 1–4 carry denser uniform micro-bead "rain" than the mocks; mock 4's
  caustic streams and luminous giants; mock 6's embers want a smoky glow beneath them and diagonal strands; mock 1's
  softer, broader light. No scene is near 1:1 yet.

## 8. Product requirements recorded from the operator (2026-10-17)

- **Collision behaviour (operator 2026-10-17, supersedes the two-way ratio):** a triangle control with **Fuse**,
  **Pop** and **Bounce** at its corners; the node the user places by mouse inside it sets the three ratios
  (barycentric). Bounce is a gentle elastic push apart. Checkboxes choose whether it applies to **Big**, **Small** or
  **All** bubbles; bubbles it does not apply to pass through each other freely. Earlier note: a settable ratio of **merge** (touching bubbles join with a neck, `sceneClusterRay`) versus **pop**
  (a very gentle fade out) when bubbles collide; merges must vary (sizes, neck width, orientation, two to four
  members), never one uniform shape.
- **Trails:** dense wakes of tiny bubbles behind mid and large bubbles that follow the drift.
- **Reactivity priorities (operator 2026-10-18):** breathing; drift rising and falling with intensity; stream speed
  rising through saturated passages; particle emission (specks, dust, trails), especially in 3D. Quick attack and slow
  decay on all of them, the stream above all: never a stutter, judder or sudden stop. Each is a range-slider (EB5a)
  candidate. A light idle energy in silence (original Bubble does this well). Fixed-scale drivers only (passage
  intensity, onsets by musical weight): no dynamic floors; room to optimise rather than Bubble's specific simulation.
  **Sustained loud passages** need their own response (drift, stream speed and especially the small bubbles reacting
  through sustained loudness, not only hits); always check them on the real recordings in `logs/visualizer_recordings`.
- **Reactivity:** light shafts react to the music (intensity, spread or flicker), alongside bubble breathing, speed
  and drift, all through Extruded Bubble's own logical simulation on the sole clock, never a second clock or DSP.
- **Sizes:** strong variation with a slight bias to small bubbles, authored by on-screen size bands.
- **Camera down:** a darker abyss below, not an ocean floor (operator 2026-10-17); the seabed primitive stays
  in the library unused by Extruded Bubble.
- **Highlights and colour (operator 2026-10-17):** highlights sit toward the light and inset from the rim, never
  merging with the edge; glints read as light on glass, not stars; bubble colour follows the scene's water and light.
- **Look:** parity with all six mocks, judged side by side at full resolution with crops
  (`tools/labs/extruded_bubble_lab.py` renders one variant per mock against it).

- **Presets (operator 2026-10-18):** each mock must eventually be an easily achievable preset.

## 9. Settings and presets (EB2 design, operator 2026-10-18)

**Principles.** Extruded Bubble has its own control set (original Bubble's is a guideline only). Controls are
extensive but friendly: nested buckets closed by default (one open per level), short
Title Case names, one-sentence intros with detail in tooltips, and heavy use of `when` conditionals so only what the
current choices use is shown. Spatial and proportional choices use **visual controls**, not number pairs. Every
amount that music can move is an **EB5a range slider** (quiet..loud). **Presets are authored through these controls
alone:** after construction the agent rebuilds every lab scene (`VARIANTS` in `tools/labs/extruded_bubble_lab.py`,
layered as `ENGINE` / `MODES` / scene) as a preset using only the Settings UI and its saved values; a scene that
cannot be reached means a missing or wrong control, fixed in the spec, never by a hidden value.

**New shared controls (one owner each, reusable by any mode; follow the shared slider's look, keyboard and
accessibility):**
- **Range slider** (EB5a): two handles on one bar.
- **Triangle mapper**: a node dragged inside a triangle sets three shares (barycentric); used by Collision.
- **Direction mapper**: a small disc/hemisphere the user drags a point on to set a direction (around + height),
  with a live arrow; used by Stream Direction and Light Direction.

**Buckets** (controls shown only when their condition holds):

| Bucket | Controls | Shown when |
| --- | --- | --- |
| Light | Light Type (Sunlit Surface / Deep Light); Light Direction (direction mapper); Light Colour; Light Strength | always |
| Light → Rays | Light Rays (range); Ray Style (Fan / Beams); Ray Softness; Ray Reach; Ray Reaction (intensity, spread, flicker) | Light Rays on; Fan options only for Sunlit Surface |
| Light → Surface | Surface Brightness; Ripples | Light Type = Sunlit Surface |
| Water | Water Colour; Depth Colour; Haze; Light Veils (amount, threads) | Veils' detail only when Veils on |
| Glass | Clarity; Rim Glow; Iridescence (amount, colour band); Softness; Sparkle | Iridescence band only when Iridescence on |
| Bubbles → Population | Large Bubbles, Small Bubbles, Bead Chains (ranges); Size Variety; Bead Columns | always |
| Bubbles → Motion | Stream Direction (direction mapper); Stream Speed (range); Drift; Sway; Swirl (with its direction) | Swirl replaces Stream Direction while on |
| Bubbles → Reaction | Breathing (range); Small Bubble Pulse (range); Stream Reactivity; Contraction | always |
| Bubbles → Collision | Collision triangle (Fuse / Pop / Bounce); applies to Big / Small / All; Fuse Variety (neck width, members) | Fuse Variety only when Fuse share > 0 |
| Particles | Amount (range); Size; Warmth; Glow; Bands (frequency, contrast) | Bands' detail only when Bands on |
| Lens | Focus; Aperture; Exposure | always |
| Camera | Auto Rotate After (Off / seconds); Auto Rotate Speed | Speed only when Auto Rotate is on |

**Camera: Auto Rotate.** When enabled, the camera starts a gentle full-circle swivel (turn only; pitch, zoom and pan
untouched) after the set time with no camera input. Completion of a full startup or of a mode/preset swap counts as
an immediate trigger. Any orbit input stops it and restarts the wait. Driven by the logical frame clock (idle =
frame time since the last camera input), never a timer or polling; part of the shared framed camera (FC), so any
framed 3D mode can opt in (declared as `view_auto_rotate_settings`, implemented 2026-10-18). Orbit is rotation of the
view (turn/tilt); pan and zoom are separate. **Starting views as Neon Lake does:** each preset carries its camera
through the established `starting_view` metadata (Save Preset As with **Include current camera view when saving**,
applied once on a preset selection; Custom keeps the live view), so every rebuilt lab scene saves its framing with
it; Auto Rotate then starts from that view. Auto Rotate After/Speed are presentation settings.

**Lab knob mapping** (what each control sets in the lab; `ENGINE` values and mode defaults are not controls):
Light Type → `mode`; Light Direction → `sun`, `light_view`, `spec_view`; Light Colour → `light`, `shaft`, `sky`
tint, default `speck_warm`; Light Strength → `glint_power`, `light_power`, `surface_gain`, `glow`; Light Rays →
`rays`; Ray Softness → `fan_contrast`, `fan_march`, `fan_rays`; Ray Reach → `fan_reach`; Beams' focus →
`ray_focus`; Water/Depth Colour → `water`, `deep` (`absorb` derived); Haze → `mist`; Light Veils → `veils`; Clarity →
`face_reflect`; Rim Glow → `probe_fill`, `proxy_power`; Iridescence → `film`, `film_range`; Softness → `rough`,
`inner_blur`; Sparkle → `sparkle`, `speck_glow`, `glint_sharp`; Large/Small Bubbles, Bead Chains → `mid_count`,
`small_count` + `fizz`, `chains`; Bead Columns → `columns`; Stream Direction → `travel`, `streak`; Drift, Sway →
`drift`, `sway`; Particles → `specks`, `speck_size`, `warm_share` + `speck_warm`, `speck_bloom` + `dust`, `banded`,
`band_freq`, `cloud_*`; Lens → `focus`, `aperture` + `near_coc`, `exposure` + `hdr_exposure`. Breathing, pulse,
stream reactivity, contraction and collision have no lab knobs yet. **Extruded Bubble's controls are its own:**
original Bubble's control set is only a guideline (operator 2026-10-18); nothing is copied or shared from its Settings
body, and each control here is designed for this mode.
Values still kept per scene until their control exists: mock 1's `ray_cut`, camera-down's `glint_sharp` and the
`rough` differences.

## 10. Architecture (EB2/EB3, 2026-10-18)

**Mode.** Descriptor `extruded_bubble` ("Extruded Bubble"): card shell with card-interior clipping, viewport-resizable,
`freeform_3d` with its own `layout_profile` ("3d:extruded_bubble"); framed camera declared on the descriptor (turn/tilt
orbit wrapping a full circle, `view_auto_rotate_settings`, scene scale/pan with a `scene_pan_envelope`), prepared
reveal. Registered behind a closed code gate (`_GATED_MODES`: not selectable, not offered in Guided Setup, no
runtime work) until EB5 acceptance flips it in code; never an environment flag.

**Simulation (CPU, logical clock).** `widgets/spotify_visualizer/extruded_bubble_frame_runtime.py` owns an
`ExtrudedBubbleSimulation` advanced in the mode's logical capture (as Neon Lake's runtime is), with dt from the sole
logical clock and the existing audio feeds (fixed loudness, bands, transient onsets, event scheduler). It owns only
what music and collisions move: the large and mid bubbles (bounded, about 200): identity, position in the framed
volume (normalised, depth included), velocity, radius, breathing, fuse-cluster membership and pop fade. Streams are
emitters with a direction (Stream Direction), rate and speed (EB5a ranges across loudness); drift and sway are
deterministic noise of (identity, logical time). Collisions use a spatial hash on that small set and resolve to Fuse
(a cluster record with neck and members), Pop (a soft fade) or Bounce (an elastic push) by the Triangle shares and the
Big/Small/All admission. The capture freezes an immutable snapshot (packed float32 bubble records, cluster records,
scene scalars such as loudness envelope and beat flash). Nothing in it touches Qt or GL; it is deterministic for a
recorded clip, so replay audits work as for other modes.

**Procedural on the GPU.** Bead chains, fizz, tiny bubbles and particulate are generated in the vertex stage from
fixed seeds, the logical time and the snapshot's scalars (stream direction, speed, density range): tens of
thousands of instances with no per-bead CPU work and no GIL-held numpy on the logical thread.

**Renderer (EB3).** `rendering/quick/visualizer/implementations/extruded_bubble.py` ports the lab's proven passes onto
the shared owners: `SceneTarget` (depth texture, OIT, HDR, bloom), `SceneProbe`, sphere impostors shaded by
`sceneHollowSphereTrace`, the cluster pass, `DefocusLayer` for near giants, the light (sun fan / deep beams), the water
backdrop (Snell's window or the abyss), veils and particulate bloom. Detail tiers (`scene3d_detail`) bound probe size,
rim sub-rays, bead density and defocus taps; the small-bead model (G0) is the main budget lever.

**Slices.** S1 simulation + frame runtime + capture, pure and tested (determinism, bounds, collisions, cadence on
the logical clock, dormancy) → S2 descriptor behind its gate, Settings spec (§9), defaults, builder, parameters →
S3 renderer port pass by pass, each compared with the lab at full resolution → S4 controls drive reactivity, every lab
scene rebuilt as a preset through the Settings UI alone → S5 physical acceptance with real recordings, gate opened.

**S1 landed (2026-10-18).** `extruded_bubble_simulation.py` (pure, deterministic; 1.3 ms a step at 190 bubbles) and
`extruded_bubble_frame_runtime.py` (activation/source fences, onsets taken once by serial, steps capped at 0.1 s,
retirement). Tests: `tests/test_extruded_bubble_simulation.py` (determinism, population across quiet..loud, stream
direction, breathing and smoothing, each collision outcome alone, Off and scope, idle, reset, runtime fences). Not yet
wired: no descriptor, capture or renderer reads it (S2).

**S1 on real music (2026-10-18).** `tools/visualizer_replay/extruded_bubble_traces.py` drives the simulation with real
recordings through the BeatEngine replay seam. On four recordings the stream's largest frame step is 0.6-1.0% of its loud
speed (no stutter), it rises within about a second into loud sections and decays over several, sustain builds through
held loud passages, and the mid bubbles pulse on snares. Emission had pinned at its maximum (a flat onset bump); it is
now a share of its own span. Passage intensity is the track's level on the fixed scale: the "acoustic soft" recording
measures as loud as the heavy ones (median 7.7), so its high sustain is correct.
