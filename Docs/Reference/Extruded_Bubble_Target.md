# Extruded Bubble: target contract and shared-primitive inventory (§4A G0)

Status: **implemented but operator-rejected on physical fidelity** (2026-10-18); §10 records the first live review
(D → B → C → A), and §11 records additional operator failures and their source audit. The G0 requirements and historical
primitive inventory below are preserved as the design provenance, **not** as a claim that no renderer exists.
`Current_Plan.md` §4A/§4B own sequencing; `Scene3D_Resources.md` owns the shared resource contracts;
`Docs/Guardrails/Bubble_Temporal_Fidelity.md` (BTF) binds the reactivity. Original Bubble remains accepted and separate.
Visual acceptance cannot be inferred from the lab, green unit tests or authored preset parity.

## 1. Visual target (operator mocks, `tmp/Bubbleexamples`, 2026-10-17; informational mocks 2026-10-18)

Seven frames in `tmp/Bubbleexamples` (three looking up toward a sunlit surface, one with wake tendrils, the abyss, camera
down, the diagonal orange stream) plus two annotated **informational mocks** (`tmp/Bubbleexamples/Informational mock.png`,
`tmp/Bubbleexamples/Informational mock 2.png`, blue and copper) whose detail panels name each material requirement: broad specular
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

Not in the target: hard cast shadows without a demonstrated receiver, GTAO or screen-space reflections without
an actual target need. **Operator clarification 2026-10-20:** the fiery example's debris/gas/smoky appearance,
proper stream source points and useful EB camera control/centring are in scope. Add whatever bounded runtime/shared
architecture reproducing the examples requires; the older blanket exclusion of volumetric smoke/fire must not
exclude needed gas/wisp/volume behavior. EB's open volume need not inherit Neon Lake's camera restrictions.
`tools/labs/extruded_bubble_lab.py` and its `ExBubble1`–`ExBubble6Diagonal` variants are comparison assets;
matching a lab still does not establish production emitter/lifetime/reactivity or physical camera correctness.
Healthy reactivity is the immediate priority; required scene architecture remains subsequent active EB recovery.

## 2. Reactivity: its own simulation (operator 2026-10-18, supersedes "reads original Bubble")

**Operator clarification, 2026-10-20:** accepted 2D Bubble sets the minimum *response scale*, especially the
immediate strong changes in `anything_mixed2.jsonl`. In idle EB must slowly settle into a collapsed resting state
across size, drift/sway, stream, beads/wakes, rays, emission and ambient/surface motion. Nothing remotely fast;
no autonomous idle size oscillator. Earlier "light idle energy/breathing" notes are subordinate to this requirement.
Native measurements, reproduced control failures and the candidate transfer are in the dedicated Extruded Bubble failure ledger §6–7;
`Current_Plan.md` §4B owns the current actionable recovery order. Candidate source and tooling do not constitute physical acceptance.

The simulation's current reaction strength spans contracted rest and musical expansion; nominal size is not a
lower bound. Normal Breathing/Small Pulse strengths permit a resting radius near 0.13× nominal; zero strength
disables size reaction. Minimum size and maximum excursion are separate acceptance measures. Compare mature,
nonpopping stable identities against accepted 2D, including the big population and projected/visible size at fixed
depth. Do not count entry fade, pop shrinkage, changed perspective or a departing identity as musical contraction.

Ray Softness must reach both the angular sun fan and the marched Deep Light shaft pattern. The Light Rays
Range is resolved once at the simulation's continuous ray driver, with resting light activity reduced to 3%
at zero drive and full authored strength at drive 1. This lets strong quiet-music authoring coexist with dim
silence. Shimmer/phase still comes from the logical simulation, with gentle release rather than a pause reset.
Broad shaft appearance and reaction remain native/physical acceptance questions, not shader-link assertions.

Free and attached bead bubbles have at most roughly −10%/+10% musical size variation. A changing parent's
radius moves the wake attachment, while nominal parent size seeds bead dimensions and trail extent. Every
visible attached bead remains strictly smaller than its current parent, including the half-pixel raster limit;
fade/hide a bead if a tiny/fading parent cannot support that bound. Keep nominal size through retirement rather
than rebinding to a compacted slot. Slow idle must remain visibly alive: motion and emission need separate
resting activity because particle density squares the emission value. Zero authored amounts remain zero.

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

**Historical 2026-10-18 lab acceptance (no blanket retuning while fixing glass):** bubble density and size bands, rising bead
chains, tiny-bead trails, ember particulate/dust in the copper scene, the rippled sunlit surface. **Later operator
review in §11 rejects bead-chain fade/curvature/width and idle surface/chain speed; that later evidence prevails.**

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
  Avoid pinning almost everywhere: big bubbles may hold large through sustained loud passages (better than flickering)
  while small bubbles and motion compensate with their breathing and movement; real-music volume decides it.
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
| Bubbles → Population | Large Bubbles, Small Bubbles, Bead Chains (ranges); Size Variety; Columns | always |
| Bubbles → Motion | Stream Direction (direction mapper); Stream Speed (range); Drift; Sway; Swirl (with its direction) | Swirl replaces Stream Direction while on |
| Bubbles → Reaction | Breathing (range); Small Bubble Pulse (range); Stream Reactivity; Contraction | always |
| Bubbles → Collision | Collision triangle (Fuse / Pop / Bounce); applies to Big / Small / All; Fuse Variety (neck width, members) | Fuse Variety only when Fuse share > 0 |
| Particles | Amount (range); Size; Warmth; Glow; Bands (frequency, contrast) | Bands' detail only when Bands on |
| Lens | Focus; Aperture; Exposure | always |
| Camera | Auto Rotate After (Off / seconds); Auto Rotate Speed | Speed only when Auto Rotate is on |

**Light and gradients (operator 2026-10-18).** Light Direction is the same direction mapper as Stream Direction
(a light with rays falling toward the scene instead of an arrow); the shafts follow it, so one control sets both. No
separate gradient control: the water's gradient is Water Colour (surface) to Depth Colour (below) shaped by the
light's direction, colour and haze.

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
`rays`; Ray Softness → `shaft_soft`, `fan_contrast`, `fan_march`, `fan_rays`; Ray Reach → `fan_reach`; Beams' focus →
`ray_focus`; Water/Depth Colour → `water`, `deep` (`absorb` derived); Haze → `mist`; Light Veils → `veils`; Clarity →
`face_reflect`; Rim Glow → `probe_fill`, `proxy_power`; Iridescence → `film`, `film_range`; Softness → `rough`,
`inner_blur`; Sparkle → `sparkle`, `speck_glow`, `glint_sharp`; Large/Small Bubbles, Bead Chains → `mid_count`,
`small_count` + `fizz`, `chains`; Columns → `columns`; Stream Direction → `travel`, `streak`; Drift, Sway →
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
reveal. Offered since 2026-10-18 (operator): selectable, cycled, in Guided Setup (its preview rendered by the
onboarding foundry from preset 1) and the 3D tab, so its physical acceptance (EB5) runs on real displays. It sat
behind the `_GATED_MODES` code gate from S2 until then.

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

**S2 landed (2026-10-18).** `extruded_bubble` is registered behind its closed code gate (`_GATED_MODES`: not
selectable, cycled, offered in Guided Setup or listed in the 3D tab). Its own Settings spec (§9: Light, Light Rays,
Bubbles, Motion, Reaction, Collision, Camera; advanced Water, Glass, Particles, Lens) uses the direction mappers,
the collision triangle and range sliders with `when` conditionals; its analysis profile owns Oscilloscope's
technical subset (floors default off; its reactivity reads only fixed-scale intensity and onsets). The capture
advances its own simulation on the logical clock (`controls_from_parameters` maps Settings units to the
simulation's), Auto Rotate is declared with its enable toggle, and a starter preset equal to the defaults stands in
until S4 rebuilds the lab scenes through these controls. The renderer admits its frame and draws nothing until S3.
Tests: the generic spec suite (model repair, real body build/save/reload incl. the visual controls, conditionals,
with the gate opened for the test), the all-mode runtime lifecycle, geometry profiles, presets.

**S3a landed (2026-10-18).** The renderer draws the lab's scene through the production host. Programs:
`rendering/gl_programs/extruded_bubble_program.py` (moved from the lab; the lab imports them). Scene mapping (no GL):
`rendering/gl_programs/extruded_bubble_scene.py`: `ENGINE`/`MODES` (the lab imports them), `scene_knobs` (Settings to
knobs, as section 9), `ray_strength` (Light Rays read at the level), `camera` (pitch 16 + 90 x tilt, yaw pi x turn,
Scene Scale as zoom), the simulation's volume to world (depth 6..32, radii as shares of the half view height),
cluster records, view-anchored near giants (three, slow drift) and glint proxies. Each frame: probe capture (water and
light all round plus each bubble's glint), half-resolution shafts and blur (two owned R16F targets), then through the
card's `SceneTarget` (overlay, HDR, bloom 0.55, depth texture, background, OIT): water and shafts, shells and clusters
over the captured background, near giants through `DefocusLayer`. Instance data in fixed-capacity buffers
(`glNamedBufferSubData`); uniforms sent only when they change (`glProgramUniform*`). `prepare_step` warms every program
(the target's list now covers background, OIT and HDR), the buffers, shaft targets, probe (size per tier: 256 / 256 /
128 / 64) and near layer (with its read level), one unit a hidden frame. Harness: `tools/extruded_bubble_capture.py`
(real recording through `replay_clip` and the production host; frames, contact sheet, GPU ms). First capture at
1672x941, 4x MSAA: 3-4 ms GPU (the lab's mock 2 scene, with its tens of thousands of beads, 11.6 ms). Defect found and
fixed in the shared owner: `DefocusLayer` inherited the scene target's masked draw buffer 1 (outside
`emission_writes()`), dropping every circle so near giants drew sharp; it now sets and restores its own colour masks.
Tests: `tests/test_extruded_bubble_renderer.py` (camera, volume mapping, clusters, giants, proxies, knobs per light
type, rays; a prepared renderer draws turned and repeated frames compiling and allocating nothing, releases everything),
prepared reveal for the mode, defocus under a masked index, target warm list = what an HDR/OIT/background scope compiles.

**S3c (first part) landed (2026-10-18).** GPU-procedural small bubbles through the same traced-shell fragment:
`BEAD_VERTEX` (the bubble vertex stage with its attributes generated from the instance index) draws bead chains
(Bead Chains range read at the emission follower, 12 chains a step, 160 beads a chain, scaled by the tier's particle
share), marine snow (2500 motes x share) and fizz wakes (64 motes behind each simulated bubble, read from the shell
instances bound as a storage buffer; fuller behind larger bubbles). Beads climb and snow drifts by the simulation's
new `travel` (the stream speed integrated on the logical clock, in the snapshot and frame) plus a constant
buoyancy, so a change of speed never makes them jump; no renderer-owned state. At 1672x941, 4x MSAA: 6.2 ms GPU with
the default range at loud, 7.2 ms with the lab's mock 2 density (Bead Chains 10; the lab's scene 11.6 ms).

**S3b landed (2026-10-18), stateless in the renderer.** The eye only rotates, so a world-fixed field needs no
simulation change: the volume is placed by the camera at turn 0 and the current tilt, then each point turns about the
world vertical by whole periods to stay within half a period of the camera's heading. A point's period is twice the
azimuth where its elevation meets the volume's side plane, a closed form (a quadratic in the plane's vertical tangent;
the whole circle where the plane never reaches that elevation): every visible point of that elevation lies inside
it, also near the top of a pitched view. A turn keeps elevation and distance, so periods never change and a bubble
leaving one side returns on the far side unseen. Clusters and bead chains turn as one (by their lead member / centre);
beads and snow run the same wrap in GLSL. Tilt stays view-relative (a tilted preset frames the bubbles as authored).
Tested: world-fixed under small turns; a full turn at four aspects/tilts never wraps a bubble on screen (largest
on-screen step is the rotation itself). Near giants stay at the lens.

**Scene Pan landed (2026-10-18).** An off-axis frustum (`lens_shift`: the card-fraction pan, y down, as an NDC
shift in the projection and in the full-screen passes' rays; none in the probe): water, light, bubbles and beads
move alike, nothing turns. Deep Light renders through the product (teal abyss, light in the water, veils); its
look is preset work (S4).

**S3c particulate landed (2026-10-18).** `SPECK_VERTEX` (the particle vertex stage with generated attributes): specks
all round the eye in clouds stretched along the stream (the lab's `particulate`; Particle Bands sharpens them into
the sixth mock's bands), flowing by `travel`, world-placed (fixed under the turn), added as light before the
background capture. `speck_amount`: the Particles range at the emission follower; density grows with its square and
brightness with it, 1.0 = the lab's heaviest scene (216,000 specks x the tier's particle share). The default range
became light dust (0.1..0.35; the starter preset follows the defaults until S4). A mock-6-like scene authored from
Settings alone (Deep Light, orange light, banded warm particles, diagonal stream) already streams like the mock; its
ember glow and light colour are S4 preset work.

**Bead budget landed (2026-10-18).** Measured per pass first (`tools/extruded_bubble_capture.py --passes`): at the
lab's mock 2 density the beads were 2.4 ms of 6.4, then shells 0.8, near giants 0.6 (+0.5 their defocus), probe
prefilter 0.6, backdrop 0.5, shafts 0.4. Two cuts in the shared fragment, no look change (side-by-side crops: only
rim sparkle on beads differs): a bead of a pixel or less, which the speck light replaces whole, no longer traces;
rim pixels under 10 px radius average four sub-rays instead of eight. Instances of no size (generated ones left out,
faded ones, specks outside their clouds) draw no quad: the vertex stages' half-pixel floor had shaded each as a dot
(tested; fails without the cull). Interleaved A/B, three rounds at 1672x941 4x MSAA: mock 2 density median
4.7-4.9 -> 3.5-4.3 ms, defaults 3.5-4.8 -> 2.8-3.7 ms (beads pass 2.4 -> 1.1 ms). Occlusion culling does not
apply: nothing in the scene is opaque (beads behind glass show through it), and off-screen quads cost only their
four vertices (the rasterizer clips them).

**S4 ray reactivity landed (2026-10-18).** `level` is `PassageIntensity`, which clamps at 1.0 through loud passages
by design (half of "dontyouseemetrying" reads above 0.995), so nothing reads it linearly any more. The simulation
owns a ray driver: 0.65 x level + 0.05 x sustain + 0.3 x a lift that follows the onset flash (0.1 s rise, 0.4 s x
smoothing fall), eased below the top (`_soft_top`, knee 0.9); and a shimmer phase that advances at 0.5 + 2.5 x the
lift (an integral, like `travel`). Both ride the snapshot and frame. Light Rays (range) read the driver; Ray Flicker
(a Settings control nothing had read) brightens and dims each fan ray and each beam cell on the shimmer, deeper as
the driver rises (x 0.3..1.0); the fan reaches 0.85..1.15 x further with sustain. On seven real recordings the driver
never exceeds 0.93, still swings about 0.09 through 2 s windows where the level holds at 1, and moves at most 0.05
in one 60 fps step. Tests: never pinned and moving through a saturated passage, quick rise and slow fall, no jump;
the shimmer runs faster on hits; the picture is identical at level 0 and 1 and changes with the driver.

**S4 presets landed (2026-10-18).** Every lab scene is a curated preset authored from Settings values alone:
1 Sunlit Surface, 2 Deep Blue, 3 Night Water, 4 Soft Rays, 5 Abyss, 6 Looking Down, 7 Ember Drift (mocks 1-4, 5
Abyss, 5 Cameradown, 6). `tools/visualizer_preset_author.py` writes each one: every value must come back unchanged
from its Settings control's `admit` (reachable in the UI), the payload passes the normalisers the Settings save uses,
the view pose becomes `starting_view`, and the file is read back through the activation path. Rendered through
`tools/extruded_bubble_capture.py --preset N` (the real activation, starting view included) each preset draws the
same picture as its authored scene (max difference 1/255). Two scenes could not be reached, so the Settings
changed, never a hidden value:
- **Columns** (section 9's "Bead Columns", built now): a share of the bubbles spawn in lanes along the stream (the
  across-stream position snaps to a lane 0.26 apart), as the Abyss mock lines them up. Simulation-owned, tested.
- **Deep Light colour:** a light inside the water now carries its colour into the sky and shaft tints (0.85 toward
  the light; a sunlit surface stays 0.6 / 0.45), so an orange light gives orange beams, glow and veils (mock 6).
Conversions used: the lab's deep `light_view` is a view-space direction at the authored pitch, rotated to the world
for Light Direction; the lab's `travel` (across, up, into) maps to Stream Direction's around/height; pitch to tilt
as (pitch - 16) / 90 (Looking Down's -32 degrees clamps at the tilt limit, -29). Remaining differences from the mocks
are the renderer's, not the presets': mock 4's curved trails and caustic floor, mock 6's smoky ember texture (specks
read as points), Looking Down's seafloor (dropped by design) and generally fewer, smaller bubbles than the mocks
paint. Each preset is authored content: the operator retunes them at will.

**Gate opened (2026-10-18, operator).** `_GATED_MODES` is empty and the descriptor is offered in Guided Setup;
its Guided Setup preview (`visualizer_extruded_bubble.png`) is rendered by the onboarding foundry
(`_RENDERED_VISUALIZER_PREVIEWS`), registered in the onboarding resource pack with its locked hash.

**Operator review on a real display (2026-10-18, 19:23-19:25 run: preset 1 for ~50 s with music, then presets 2-7).
Four defects, in the operator's order of importance: D, B, C, A. Not yet fixed; this records what is wrong and why.**
The mode logs none of its own state, so the evidence below is the same simulation replayed on the real recordings
(`replay_clip`, presets 1 and 7, past the first 5 s), with pixels at 1080p (a volume unit is half the view height).

**D. Breathing is near zero, also on big bubbles; I reported it as working.** Measured large-bubble swell (share of
radius): heavy1 median 0.039 / p90 0.058, 1985_loud1 0.031 / 0.049; through the sustained passages of
dontyouseemetrying and nightsolong it sits flat at 0.16-0.18 (held, not breathing). Mid bubbles: 0.015-0.04. A large
bubble's radius changes by a median 0.2-0.4 px per second. Causes:
- Three sub-1 factors multiply: the Breathing range x `BREATHING_FULL` 0.35 (default 0.05..0.21 of radius) x the
  passage level x the breath follower (median 0.2, p90 0.4-0.5): typically 0.01-0.04.
- The breath follower is kicks only (onset weight, decaying in ~0.45 s); kicks are sparse or weak on many tracks.
- Through a sustained passage `hold` replaces breathing with a constant size: the "big bubbles may hold large"
  allowance became the whole response, with nothing moving on top.
- Process: S1's tests and survey checked follower timing (attack, decay, no jumps), never visible amplitude in
  pixels, and S1's notes claimed the response ("mid bubbles pulse on snares") from those curves.
Direction: author the response in visible units (a big bubble's breath a clear share of its size on every kick, a
continuous breathing motion whose depth and rate rise through loud and sustained passages instead of freezing,
driven by its own quick-attack/slow-decay energy, not by kicks alone); accept it by pixel amplitude on the real
recordings, saturated windows included.

**B. Three static near giants in every preset and scene.** `near_giants()` (scene module) draws three huge
defocused bubbles at fixed screen positions (left-bottom, right-bottom, left-top), anchored to the camera: they turn
with it, drift +-0.04 of the view over about two minutes, are never replaced, ignore the stream and the music, and
no Setting reaches them. Cause: the mocks' blurred foreground bubbles were ported from the lab as lens decorations,
because the simulation's volume starts at depth 6 (`DEPTH_NEAR`) and no simulated bubble can come near the lens.
Direction: retire the fixed giants; extend the volume toward the lens so real bubbles pass close (spawned, carried by
the stream, leaving and replaced like the rest, world-fixed, defocused by the near layer as they come close), with
their number on a Setting.

**C. Big bubble streams have little speed and almost no energy.** Large bubbles move a median 96 px/s (heavy1) and
125 px/s (dontyouseemetrying); the stream speed moves only about +-10% within a track (heavy1 0.163..0.193,
dontyouseemetrying 0.227..0.252 volume units/s, p10..p90). Causes:
- Positions and speeds are in view fractions, so every bubble moves at the same screen speed at any depth: no
  parallax; a near big bubble drifts like a far one.
- The Stream Speed range tops out at `STREAM_SPEED_FULL` 0.25 (8 s to cross the view at its maximum), and the
  reaction terms (flash, sustain) add little on top of a level that is already near its top in music.
- Drift and sway amplitudes are 0.015-0.06 volume units/s (invisible); big bubbles get only 10-35% more speed than
  small ones and no wobble of their own.
Direction: motion in world units (near bubbles cross faster), a full scale and reactive span that visibly surge on
hits and run fast through loud passages (quick attack, slow decay), big bubbles rising faster with size and
swaying/zigzagging as large real bubbles do; accept by px/s on the recordings.

**A. Mock details the renderer cannot draw.** "Remaining differences are the renderer's" was an excuse; each was a
choice not to build or port:
- Curved trails (mock 4): the lab's ribbon wakes (`RIBBON_VERTEX` / `RIBBON_FRAGMENT`, `wakes` in its population)
  were never ported; only fizz motes were. Section 8's "Trails" requirement is unmet.
- Smoky ember texture (mock 6) and wisps: the shared backdrop already has `uDust` and `uWisps` (the lab's Diagonal
  scene uses dust 0.4), but the product hardwires both to 0.0 in `_common` and no Setting maps them.
- The bright caustic floor (mock 4, mock 5 Cameradown): section 8 records "a darker abyss below, not an ocean floor"
  (operator 2026-10-17; the seabed primitive stays in the library). **Operator decision needed:** supersede that for
  these mocks, or keep the abyss.
- Bubble density and size: the presets draw fewer and smaller bubbles than the mocks paint.

**Also missing:** opt-in runtime evidence. A live session leaves nothing about the mode's own state (level, breath,
swell, speed), so a real-display review cannot be measured afterwards. Needs an admitted diagnostic summary (zero
work at rest, `core/diagnostics/experiment_flags.py`).

**Next.** Fix D, B, C, A in that order, each accepted by visible amplitude (px, px/s) on the real recordings and
reviewed in motion (GIFs), not stills; then physical acceptance (S5).


## 11. Additional operator findings and source audit (2026-10-18; open, not visually accepted)

**These five failures ADD to, and do not supersede, the §10 live-review blockers D → B → C → A.**
They are operator-observed defects, not aesthetic suggestions. Do not rewrite the approved presets to conceal a
renderer/simulation defect; every preset is mutable authored content, and Preset 7 is an especially important reproduction.
The audit below separates observed behavior, **source-proven mechanism**, and **unverified visual hypothesis**.
No physical render or live Settings lifecycle was tested as part of this documentation reconciliation.

1. **Bead chains: birth/death fade, curved drift, width.** Chains pop on and off instead of fading in/out; their
   drift reads as abrupt/straight rather than a flowing curve; **make the trail/chain breadth 15% wider than its
   present appearance** (not 15% fewer beads or smaller bead radii). In
   `rendering/quick/visualizer/implementations/extruded_bubble.py`, `_procedural_counts()` rounds the current
   emission-follower amount into a whole chain count; `BEAD_VERTEX` in
   `rendering/gl_programs/extruded_bubble_program.py` instantiates exactly that many beads. The shader's `ends`
   term fades *individual positions* near either end of a repeating chain; it is **not** a chain-lifetime opacity
   ramp. The lateral path is a very narrow fixed sine wave plus independent per-bead jitter, with a fixed
   `uTime * 0.6` phase. No chain identity, age, appearance envelope, retirement envelope or path-curvature
   control exists. Design requirement: deterministic stable chain identities; fade each newly admitted/retiring
   **whole chain** smoothly, in both directions, even when music causes counts to cross an integer; world-fixed
   coherent curved advection without snap/straight kinks, retain separate beads (no ribbon/sperm lines); widen
   the across-stream shape by ~15% while retaining the total population budget. Use the existing logical frame
   and immutable snapshot, not a new GPU-owned clock or a second renderer-population authority. Test animated
   chain birth/death, stream turns and idle→loud→idle at different viewport sizes, not just still frames.

2. **Clear large bubble roundness, conspicuous in Preset 7 and elsewhere.** The operator sees edge-on coin/condom
   silhouettes rather than volumetric spherical glass. T1/T2/T4 and §7's incomplete roundness remain binding.
   Source supplies analytic sphere intersections in `BUBBLE_FRAGMENT`, but the wall/interior optics intentionally
   reduce the near-face reflection (`scene_knobs`' `face_reflect`, `uReflect`) and heavily soften the transmitted
   frame (`uInnerBlur`, `uFrameShare`); near giants have a separate lens, reflectance and defocus composite.
   Preset 7 currently authors high Clarity (0.88), low Softness (0.2), low Rim Glow (0.5), plus Deep Light:
   these values can expose an edge-dominant look, but **there is not yet evidence of one proven root cause**.
   Inspect *which* objects read flat (regular bubbles, merged clusters, camera-fixed giants or all three) and
   compare normal, reflected, transmitted, alpha, defocus and depth diagnostic views at multiple orientations.
   Correct physically round interior/refraction/double-wall cues across sizes and presets **without** hiding
   coin silhouettes behind high blur, painting an opaque disc, distorting actual sphere geometry, or retuning
   curated authored values as a substitute. Acceptance is moving camera orbit plus clear full-resolution crops.

3. **Light rays: no visible musical/transient response.** §8 requires clearly energy-responsive rays. The wiring
   exists but is **not a passed outcome**: `ExtrudedBubbleSimulation.advance()` computes `rays` and `shimmer`
   from the smoothed level/flash, the renderer passes these to `ray_strength()` and `ray_motion()`, and the
   shaft shader receives `uRays`, `uFlicker`, `uShimmer`. In
   `rendering/gl_programs/extruded_bubble_scene.py`, `ray_motion()` retains a 30% base flicker even for zero
   driver, while fan shape/spread is largely static. Preset 7 authors a very tight Ray Strength interval
   [0.1, 0.2] and Ray Flicker 0.3: this may mask response, but cannot explain an all-presets report without
   instrumented on/off comparisons. Trace audible onset→snapshot→uniforms→visible per-pixel ray strength,
   reach/spread and shimmer across quiet, transient and sustained-loud passages. Ray movement may remain
   smooth, but meaningful amplitude must be visible at the authored range extremes; retain the light's
   world-space position and fan cohesion, and avoid flicker-as-random-shimmer disconnected from music.

4. **Idle overactivity / incorrect energy ownership (system-wide within this mode).** In silence the operator sees
   excess motion in multiple elements. **2026-10-18 live retest: the earlier partial idle-speed fix did not work;
   the animations actually appear FASTER in idle than during music playback.** Preserve the original greater-than-2×
   idle-speed complaint and the absent perceptible music acceleration as independent acceptance failures. The water surface and bead chains in particular move **more than twice
   the desired idle speed**, with no perceptible acceleration for playback. Source mechanisms are direct:
   `uBeadTravel = 30.0 * state.travel + 1.2 * state.time` (fixed upward buoyancy), and the bead shader adds
   lateral `sin(... + uTime * 0.6)` independent of music. The surface normal uses `rippleNormal(hit, uTime, ...)`
   and background/probe noise also advance on `uTime`; those channels have no mode-owned surface reactivity
   mapping. The simulation still carries `state.travel` from a **nonzero quiet-end Stream Speed range**, so
   even the energy-driven path has motion in silence. These are strong source explanations for the symptom;
   exact blame/ratios require live measured clips. Restore a gentle true idle, at least halve the operator-
   identified idle water/chain **apparent speed** as an acceptance target, then show a materially stronger and
   *smoothly varying* music-driven tempo. Treat motion speed, sway, waves, density, particle spawning, ray
   brightness and breathing as distinct consumers: choose appropriate existing energy/transient/sustain
   followers and spec-owned ranges, don't make all channels identical or retune original Bubble. In particular,
   scaling `uTime` by the **current** energy each frame is forbidden because it causes phase jumps; integrate
   motion phase/distance on the sole logical clock. Preserve quick attack, slow decay and continuous motion.

5. **Settings entry sporadically times out at the strict lifecycle barrier.** Reproduction: active Extruded Bubble
   → request Settings → retiring Quick generation sometimes reaches the fail-closed destruction barrier timeout
   during/around lazy Extruded Bubble Settings body creation. **Not established** that the builder itself retains
   the resource/owner: `ui/tabs/media/extruded_bubble_builder.py` only forwards to
   `build_spec_mode_ui()` and creates no distinct timer, and the renderer's multiple GL allocations/near layer
   have their own context `release()` path. The earlier Neon Settings audit
   (`Docs/Audits/Neon_Lake_Settings_And_Settings_Handoff_2026-10-13.md`) documented a *separate* strong-signal
   reference path to `QuickDisplayUnit` and remaining `QuickDisplayVisualizerOwner` uncertainty; its existence
   is a useful investigation pattern **not evidence of the same current cause**. Collect the existing
   `[LIFECYCLE_BARRIER][PYTHON_OWNER_REFS]` diagnostic on a failing handoff and identify the surviving Python
   owner, GL resources and generation, then prove the exact reference path. Also time first lazy spec-body build
   separately from Quick retirement; slow UI assembly and retention are different failures. Never relax the
   barrier, add a timeout retry, call `gc.collect()` routinely, poll, or suppress the exit error.

**Shared DirectionMapper visual request (same Settings episode):** make its central horizontal **X-axis guide**
visibly thicker than the other faint spokes, as a quiet midline/surface/horizon cue when semantically applicable.
This is an *axis stroke*, **not** a drawn letter X and not a new angle/height authority. Current
`ui/widgets/visual_controls.py::DirectionMapper.paintEvent()` draws all eight spokes with the same 1px pen;
there is no differentiated midpoint. Add a reusable, opt-in visual treatment controlled by the typed `Direction`
spec and test actual painting/palette/DPR plus unchanged drag, save and accessibility behavior. Do not imply every
angle dial has a water surface; the shared control must allow modes to omit this cue.

**Acceptance and ordering:** retain §10 D → B → C → A as the primary physical parity recovery sequence; resolve
unsafe lifecycle/Settings retirement independently as a correctness blocker, then test the new motion/opacity,
ray-response and roundness findings alongside the corresponding simulation/optics slices. Record side-by-side
operator video or GIF evidence for *silence → first onset → sustained music → return to silence*, Presets 1 and 7
minimum, plus all seven before claiming mode acceptance. Synthetic fixtures alone and instantaneous shader
screenshots cannot validate these temporal complaints. Local real-music evidence remains
`F:\Programming\Apps\ShittyRandomPhotoScreenSaver\logs\visualizer_recordings`; no acceptance claims are made
from that path unless a local agent actually runs its contents.

### 11A. Live recovery checklist (all partial or operator-confirmed failed; no accepted reactivity)

**Operator 2026-10-19 verdict, reconfirmed after full-dynamic-band retest (`logs3a0d4fa1176.zip`):** Every attempted Extruded Bubble **reactivity** repair failed on real display, across breathing, idle/playing contrast, streams, rays and particle response. The current full-dynamic rewire **also failed**. Large and small bubbles remain visually static at ordinary settings; maximum Sensitivity or Dynamic Floor can provoke only a small rapid, regular, non-musical pulse. This is **not partial breathing**, and no reactive feature is accepted. The source-side numerical motion improvements do not contradict this observation. Those entries remain `[~] COMPLETELY FUCKED`, not accepted or implied source success. The discontinued synthetic foreground cohort is removed and that absence was positively verified. For per-attempt failure history and current candidate boundaries see [`../Historical_Bugs/Extruded_Bubble_Physical_Reactivity_And_Wake_2026-10-19.md`](../Historical_Bugs/Extruded_Bubble_Physical_Reactivity_And_Wake_2026-10-19.md).

The full operator failure descriptions and source findings in §§10–11 remain binding. The details of the earlier
source attempt below are **retained as failure evidence**, not as the presently running implementation. Do not
convert this list to a chronological change log, delete an item, lose its measurements, or mark `[x]` without
explicit operator acceptance. The operator confirmed the earlier shader hotfix renders and 26 focused tests passed
in 5.90 s on Windows, but **rejected** the synthetic near bubbles and the apparent idle-motion result.

- [~] **COMPLETELY FUCKED · D · Large-bubble breathing: source changes operator-confirmed ineffective.** Uses the *existing* Breathing range and musical
  intensity, kick accent and sustained follower. A continuous, integrated phase now varies the radius through
  quiet, first onset and saturated music instead of replacing breathing with a static loud-size hold. Kick
  contribution has a short visual attack. The dependency-free simulation test proves a multi-pixel equivalent
  excursion at 1080p, not actual visible pixels or per-track envelope parity. Retain §10 D's original 0.2–0.4
  px/s, 3–4% swell, missing-kicks and sustained-plateau evidence and D acceptance unchanged until reviewed.
- [~] **B · Foreground near bubbles: synthetic cohort DISABLED.** The three camera-locked lab giants were
  removed in the previous candidate, but the subsequently generated extra *simulation-owned* near-field shells
  were visually rejected: overwhelmingly distracting and initially in focus. They are now **not spawned,
  captured, converted or rendered**, and no hidden large-bubble allocation remains. Only normal authored Large
  Bubbles are drawn. A regular unfused bubble enters the *same shared DefocusLayer* only if its actual
  camera-space front surface is inside the configured focus region with a circle of confusion above 1.5 px.
  To permit ordinary bubbles actually to approach focus, the volume's nearest depth is now **2.8** (formerly
  6), and the span **29.2** (formerly 26), retaining its far depth 32; no fake size/position is introduced.
  Camera turn, Scene Scale, Focus and Aperture still need video proof of appropriate close passes and blur;
  some camera/focus combinations will legitimately show **no near blur at all**. Fused clusters are not yet routed through this near pass. Retain §10 B's near-field
  volume/parallax/independent density target and original camera-locked failure in full, marked partial only.
- [~] **COMPLETELY FUCKED · Idle/playing inversion: both candidate source recoveries failed visually.** The prior `12 * travel` bead and `8 * travel` surface
  retiming **failed on the operator's display**. The source still admitted time-only (`uTime`) sky/cloud/veils,
  particulate and shaft animation. The simulation now integrates a distinct `motion_phase` from the existing
  musical level, transient flash, sustain and Idle control on its **sole logical clock**. Backdrop/probe,
  surface normals, caustics and shafts read that phase instead of elapsed time. Beads keep the existing
  integrated stream distance (not a separate wall clock), with phase scale reduced from 12 to 5. In the
  authored-range example (quiet stream 0.0625, loud 0.2), settled source rates were water/ambient ~0.24
  phase/s idle vs ~1.72 phase/s loud and bead ~0.25 vs ~0.86 phase/s; **not optical-flow or pixel-speed
  results**. Require real-music footage to prove quiet is visibly gentler and playing is faster, without
  shimmer reversals or abrupt transitions. Retain §11.4's full report, including the newly observed inversion.
- [~] **PARTIAL (BARELY) · Bead fades, curvature and 15% width:** retain §11.1 and this section's detailed source attempt; no
  visual acceptance yet. **Ray/music response, rounded clear glass, big-bubble depth/speed, missing mock work,
  and the Settings lifecycle timeout:** all remain OPEN with their original instructions and evidence.
- [~] **PARTIAL (BARELY) · Source-attached wake retirement and shimmer recovery:** live fizz/wake beads previously read the **compacted current shell buffer**, and a source popping/fusing/exiting could cause its trail to detach, fall or jump to a different owner. Candidate moves emitter identity and bounded tombstone lifetime into the existing logical simulation, carries 8-float `wakes` records through immutable capture, uploads one wake-only SSBO, and directionally fades from the stream-facing end backwards instead of stranding particles. Free bead chains are unparented and unaffected by bubble exit. Micro-bead fragment shading now samples filtered scene probe + the water behind, retaining environment lighting and transparency without radius-threshold stochastic reflection. No music-reactivity change or acceptance is claimed. Operator playback and native OpenGL shader/context tests still required; see dedicated bug ledger.
- [~] **PARTIAL (BARELY) · Emission Range mapping audit:** `extruded_bubble_particles` is an actual shared `Range` driving `ExtrudedBubbleControls.emission` and the simulated `state.emission`, but `speck_amount` **reapplies the same Range** to that result and squares density. Bead Chains has its own Range interpolated at the emission follower, while wake source count follows live bubble count (and 3D detail tier). These code connections do **not** establish perceptible sound-driven emission; operator reports all reactivity fails. Trace, do not simply assert it works or replace the user's range controls.
- [~] **PARTIAL (BARELY) · Fused-cluster near DoF explicitly OPEN:** regular shells enter the shared near defocus based on front-depth. `CLUSTER_VERTEX`/cluster rendering do not share that depth decision yet; fused silhouettes near the lens can remain too sharp. Maintain a separate actionable near-defocus gate, including orbit/Focus/Aperture, fused union, no double rendering and zero competing pass authority.
- [~] **Opt-in Direction midline:** source landed but current native paint/palette/DPR and operator acceptance
  have not been provided. Shader program admission: native 26-test/render recovery is real, but all-preset
  warm/cold shader/context retirement still needs evidence before acceptance.

**Previously attempted mechanisms retained for diagnosis (not authoritative current state):**

- **Near foreground (B, source candidate):** the three `near_giants()` decorations have been removed. The existing
  logical `ExtrudedBubbleSimulation.advance()` now advances up to three separate close-passing near-field bubble
  identities, with the *same* stream/smoothing followers, deterministic spawn, birth/exit fades and no new clock.
  The snapshot carries `near_bubbles` records, which `near_instances()` maps from depth 2.5–8 into world-fixed
  geometry under the same orbit/wrap as the main field. The existing defocus pass draws kind-3 near shells, no
  replacement renderer/lifecycle. The number is currently **derived from Large Bubbles** (max three), not independently
  editable, so §10's independent near-count authoring remains to be resolved if demanded. Validate all presets for
  genuinely visible close passes, camera-turn parallax, the near-field density budget and blur/fading quality. Fixed
  GPU shell capacity still covers the whole near cohort including retiring bubbles. This does **not** make the rest
  of the far field parallax-correct by itself.
- **Bead chain fade/curvature/width (source candidate):** chain population is read continuously from the existing
  Bead Chains range and emission follower. `ceil()` allocates only the final fractional chain (same approximate
  instance budget), while shader opacity fades both its population share and a seed-stable whole-chain lifetime.
  A slow coherent curving path replaces the independent rapid lateral-time sine and most per-bead scatter; its
  authored lateral amplitude receives a 1.15 width multiplier. It remains **separate beads**, not ribbons.
  Opacity is carried in the existing bubble pass as an additional flat varying and is 1.0 for normal shells.
  Check the actual GPU shader link and OIT fading on Windows; neither has been claimed here.
- **Water/chain idle energy ownership (source candidate):** `uBeadTravel` is now only `12.0 * state.travel` and
  no longer contains the fixed `1.2 * state.time` buoyancy. Bead lateral advection also uses that accumulated
  travel. The surface ripple normal and visible caustic phase use `uSurfaceTravel = 8.0 * state.travel` instead of
  independent wall time, so the authored quiet-speed example 0.05 maps to phase rate 0.4 (formerly 1.0), while
  music-loud 0.16 maps to 1.28. **These are phase-rate examples, not observed visual-speed measurements.** Other
  ambient and shaft patterns may still use wall time; §11's all-elements idle failure stays open until a real
  silence → transient → sustained → silence capture proves the contrast without aesthetic damage.
- **DirectionMapper X-axis:** the typed `Direction` spec has an optional `midline` paint flag; both Extruded Bubble
  light and stream discs request a thicker horizontal 2px guide. Unrelated full discs and collapsed angle dials do
  not inherit a false horizon or a new value. No persistence or directional mapping changes.

- [~] **Shader-program admission gate (must pass before judging appearance).** During the operator's Windows
  run, the `clusters` vertex shader failed to compile with `undefined variable "vOpacity"`; the particulate
  vertex shader also had the undeclared assignment. The bead fade's `vOpacity` belongs only in the regular
  bubble/bead vertex and compatible glass fragment shader. Candidate correction removes those two stray writes
  without altering cluster shading, particles, bead lifetime fades, optics or presets. New isolated source guard
  checks vertex output declarations (`tests/test_extruded_bubble_shader_contract.py`); all nine production pairs
  compile/link in an offscreen Mesa GLSL 450 compatibility diagnostic, **not** a native NVIDIA GLSL 460 check.
  Acceptance: actual OpenGL 4.6 cold/warm rendering of Presets 1 and 7 and the remaining five, including OIT,
  bead fading, near defocus and clean retirement, with zero shader errors. Until that happens this is **[~]**, not
  `[x]`; none of §10/§11's existing failures, physical criteria or failure details are retired.

The earlier near-field population was subsequently disabled by the `[~]` decision above. Its historical
synthetic test and buffer-capacity observations are preserved here to explain why it existed; they are **not**
acceptance evidence. The current source's targeted regression tests are
`tests/test_extruded_bubble_motion_contract.py`, `tests/test_extruded_bubble_simulation.py`,
`tests/test_extruded_bubble_renderer.py` and `tests/test_extruded_bubble_shader_contract.py`.

Full Qt/GL collection and actual audio/visual acceptance require the operator's Windows environment. Retain
§10 and §11 in full until explicitly accepted. In particular *not accepted here*: lifetime barrier,
lens-coin optical roundness, inadequate visible rays, breathing, depth-reactive large-stream speeds, plausible
near-camera population/DoF, and unported mock details.

## 12. Additional operator failures: physical camera, bubble entry fades and coherent flow (2026-10-19; all open)

**This is an additive live checklist**, not acceptance of §10, §11 or §11A. Operator evidence: in a captured frame many free bead chains seem to travel along two different directions; large and mid bubbles do not visibly grow or shrink to the music at all; when rotating to odd angles some bubbles suddenly enter the view instead of gently fading; the operator rejects any scheme that moves existing objects to follow the camera. Their physical-display testimony overrides misleading source-only green tests.

- [~] **COMPLETELY FUCKED | A genuine orbit camera must observe a stable world, not reassemble it.** `rendering/gl_programs/extruded_bubble_scene.py::_wrapped_turn()` calculates a per-point azimuthal periodic turn **from the current camera heading**. It is called in `bubble_instances`, `wake_instances` and `cluster_instances`. `rendering/gl_programs/extruded_bubble_program.py::_BEAD_GLSL::wrapTurn()` repeats that behavior in the GPU for free bead chains and marine snow. A CPU source probe of 361 camera yaw positions reports a *single already-live bubble* changing world position by up to **29.49 scene units**, including a **28.95-unit one-pose-step jump** at a wrapping seam. These diagnostic numbers are not measured pixels, but prove camera-dependent relocation. The earlier §10 S3b assertion of "world-fixed"/"offscreen-only" and `tests/test_extruded_bubble_renderer.py::test_turning_a_full_circle_never_wraps_a_bubble_on_screen` are **insufficient and superseded as acceptance claims**. No future camera-relative spatial replication, rehoming, synthetic giant overlay or visual cover-up. **Required:** define a stable, genuinely world-space scene population and orientation-independent lifetime, with finite/continuous meaningful coverage for the full 360° orbit, tilt, zoom and pan. Camera rotates *only* view/projection; stream/wake positions do not teleport. Record stable identities and actual world positions over stationary scene/full camera orbit. Never simply delete wrapping without first proving there is adequate field coverage across the full orbit; a now-empty view is not acceptance.
- [~] **COMPLETELY FUCKED | Bead chains must follow the same actual stream direction.** The screenshot shows simultaneous discordant headings. Each chain's path is generated along `uStreamView` in turn-zero camera space, then its *entire line* is turned about world vertical according to the chain's **own** camera-dependent wrap; ordinary bubbles/wakes use separately wrapped centres. Even if a free chain is not parented to a bubble, its current heading can disagree with the world stream after the wrap. Preserve gentle curved drift and +15% width, but only **transverse variation** around the same coherent world stream. Test zero/mid/steep direction control, full camera orbit and automatic turn; compare world-space displacement of bubble identities, free chains, fizz/wakes and particle clouds. Curvature cannot disguise contradictory axes.
- [~] **COMPLETELY FUCKED | Bubble entry/exit must fade, not pop in at oblique orbit angles.** `ExtrudedBubbleSimulation` has `_FADE_IN=0.6 s`, `_FADE_OUT=0.9 s` and a logical `alpha`. Yet `bubble_instances()` **does not carry alpha to the shell fragment**: it scales geometry by `sqrt(alpha)` and drops the bubble below an alpha threshold. New background spawn may even start at `alpha=1` (`anywhere=True`), and camera-dependent wrap can insert fully opaque bubbles directly into view. Fused clusters have their own rendering path and do not apply an equivalent birth/death material opacity. Distinguish logical admission/retirement fade, material opacity, frustum crossing and camera reveal. The physical sphere radius must not shrink just to simulate transparency. Require smooth film/reflection/transmission fade for normal shells **and fused clusters**, coherence with real DoF/bloom, and no sudden appearance at any tilt/aspect/zoom while orbiting. When a camera naturally swings toward a previously existing world bubble, an ordinary geometric edge crossing is not itself a lifetime birth: smooth only the view-entry/exit presentation without moving the object or breaking scene continuity.
- [~] **COMPLETELY FUCKED | Bubble size/depth/visible breathing remain absent.** `bubble_instances()` currently calculates `r_world = r_snapshot * tanY * depth * sqrt(alpha)`. Projection divides by depth, so the `depth` cancels: the same normalised bubble has **identical projected radius** at distance 2.8 and 32 in the source probe (0.1000 vs 0.1000 for a sample radius 0.1). This contradicts §1 T4's near-large/far-small requirement and flattens volumetric perspective. Camera relative pose/tilt also affects this mapping. The existing `test_a_bubble_keeps_its_share_of_the_view_at_any_depth_and_fades_by_shrinking` explicitly **endorses** the rejected behavior; rewrite the oracle when correcting geometry instead of claiming it proves physical perspective. Restore a bounded *physical world radius* whose projected diameter varies naturally with true distance and whose `breathing` variations survive all the way to the captured pixels. Do not change authored ranges or original Bubble as a workaround. Preserve the separately open near-cluster shared DoF gap.
- [~] **COMPLETELY FUCKED | End-to-end music reactivity and emission are not accepted.** `logical_frame_capture._capture_extruded_bubble` reads `BeatEngine.get_musical_intensity()` and onset events; `extruded_bubble_frame_runtime` gates source identities and passes `MusicInput` to simulation; its snapshot exports radius/swell, phase, speed, rays and emission; renderer reads those. That establishes a *code path*, **not perceptible reactivity**. `controls_from_parameters()` correctly uses the typed Range for breathing, speed, bubble counts and Particles; `speck_amount()` then re-applies the Particles Range to the already-ranged `state.emission`, squaring the speck share. Example Particles low/high `(0.2, 0.8)`: follower endpoints 0.2/0.8, second mapping 0.32/0.68, squared GPU shares **0.1024 / 0.4624**, not the expected authored 0.2/0.8. Bead Chains has a *separate* typed Range with the same emission follower; a set of independent emitters do not constitute separate audio-owned fizz birth. Find first loss of response by tracing the **actual feature clip**, input/serial/playing, each Range once, logical snapshot, GPU uniforms, then *stable object pixel radius/position*, rays and emissions. A 4-pixel theoretical-swell unit test can pass while the screen remains entirely unchanged. No DSP/clocks added to make a plot look healthier.
- [~] **PARTIAL (BARELY) | Micro-glass quality and performance remain unmeasured.** The bead/wake-only shader now uses a filtered scene probe/background and Fresnel instead of the unstable stochastic sparkle threshold. It still samples physical scene lighting; do **not** remove it simply to reduce cost. A visual/offscreen-capable agent must compare the candidate to the preceding Godzip at **identical** real-music feature frames, Settings/curated or current mutable preset values, size/DPR and warmed GL context, with per-pass `beads`, total GPU median/p90 and frame/call counts. Check at least 1672×941 and 2560×1440 with dense Bead Chains, Presets 1 and 7, near/far Focus changes and turning; ensure no glitter/shimmer alias and no large GPU regression. `tools/extruded_bubble_capture.py --passes` already supports offscreen images and GPU pass attribution; `Docs/Reference/Benchmarks.md` defines stable measurement practice. Source claims of cheaper shaders do not establish performance.
- [~] **Visual acceptance authority for *every* point above and §§10–11A:** only an operator observing the real display **or** an agent with visual capability, access to a compatible offscreen OpenGL renderer, full-resolution captured frames/sequences and meaningful audio-driving clips may assert a visual improvement. For camera and breathing, capture constant logical state at several camera angles, then constant camera at quiet→onset→sustained→silence; include physical/pixel location and radius changes for *the same bubble IDs*, not a raw average or a stationary screenshot. When the result is uncertain, keep `[~]`; all reactivity stays operator-confirmed failed. `tools/extruded_bubble_source_audit.py` is a **read-only, non-GL negative diagnostic** that exposes current camera, perspective, opacity and Particles Range faults, not a passing product test. An agent must measure micro-glass GPU costs before acceptance.

### 12A. End-to-end signal custody (source read; visual outcome still COMPLETELY FUCKED)

| Input and typed Range owner | Mode-owned logical state | Renderer / physical output | Observed source gap; mandatory captured evidence |
| --- | --- | --- | --- |
| `get_musical_intensity()` + eligible weighted onset serials (`logical_frame_capture` → `extruded_bubble_frame_runtime`) | `MusicInput.playing/intensity/onsets`; source generation and activation fenced; `_level`, `_breath`, `_flash`, `_sustain` | `ExtrudedBubbleFrame` snapshot's matching fields | Source continuity and exact values in a **real** clip not yet compared against **visible pixels**. Playback-edge logs may report near-zero intensity at some transitions but cannot prove entire-track failure. |
| **Breathing** Range, `BREATHING_FULL=0.35`, plus `small_pulse` Range with `SMALL_PULSE_FULL=0.15` | `_snapshot` computes `swell` in each 8-float bubble record and multiplies its base radius | `bubble_instances` maps that radius, but also multiplies by depth and `sqrt(alpha)`; glass vertex uses projected sphere | Software radius may change while screenshot size remains stationary. Measure projected and *captured* radius for same stable IDs, small and large, across quiet→attack→sustain. |
| **Large Bubbles** / **Mid Bubbles** Ranges | `_lerp(count, level)` yields integer targets, birth `alpha`, leaving and pop | Compacted ordinary shell buffer / fused-cluster buffer, camera-dependent wrap | Integer admission; opaque-on-start `anywhere=True`; geometry fade instead of material fade, plus camera wrap. Count, identity, opacity and on-screen entry/exit must be captured separately. |
| **Stream Speed**, **Drift** Ranges and Sway control; **Stream Direction** typed Direction | `_speed`, `_drift`, `_travel` + raw `self._time` sine for wander and sway | Motion to shell world positions; `uBeadTravel`/`uSnowDrift`; free chains independently transform their stream under camera wrap | Direction and speed must be compared in **world coordinates for the same IDs**, then converted to pixels. Movement ownership is currently split; no visually accepted stream speed or correct chain axis. |
| **Particles** Range, `ExtrudedBubbleControls.emission` | `state.emission` already ranged and followed | Historically `speck_amount()` **repeated the Range** and squared density; the single-Range source candidate now removed the second interpolation but **failed operator visual retest**; `uSpecks` also influences brightness | Historic double-Range violation and current perceptual emission failure both remain open; measure actual speck count/brightness, not just the follower. Fizz density additionally follows the emitter population rather than an independent sound response. |
| **Bead Chains** Range | Evaluated with the already-ranged `state.emission` follower | `_chain_fill` → fractional chain opacity and `ceil()` GPU instance count → `BEAD_VERTEX` | Range exists but count changes can remove instances instantly; stable lifetime and fade must be captured. Do not apply the Particles Range again to this independent authored amount. |
| **Light Rays** Range and Ray Flicker | `_rays`, `_shimmer`, `_sustain` | `ray_strength()` sets `uRays` in backdrop; `ray_motion()` sets `uFlicker`/fan reach and shaft shimmer; `SHAFT_FRAGMENT` generates shafts without directly reading `uRays`, then backdrop scales sampled texture | Energy path is technically connected, but meaningful changed **ray pixels** and transient reaction are unproved and operator-rejected. Capture same-scene image difference in ray-only region (avoid confusing global surface/lens changes). |
| **Idle Energy** and Smoothing | `_motion_rate/_motion_phase`, `_travel`, independent raw `self._time` inputs remain for bubble wander and other shader layers | Water/shafts/ambient sample integrated phase; beads read travel | Operator sees idle movement faster than playing and no live contrast. Logical phase units do not measure visible optical flow. Capture repeated quiet/music sequences with identical camera and interval. |

**Required trace order:** retained feature-frame timestamps, current playback/activation authority, `get_musical_intensity()` and exact onset events → typed low/high Range once → immutable snapshot values **and stable bubble IDs** → mapped instance world position/radius/alpha → final shader uniforms → offscreen captured images and per-object pixel motion/opacity (with a visual agent) or physical operator evidence. Existing helpers: `tools/visualizer_replay/extruded_bubble_traces.py` (logical *only*), `tools/extruded_bubble_capture.py` (offscreen pixels/contact/video and GPU timing), `tools/extruded_bubble_source_audit.py` (negative CPU geometry diagnostic). None alone demonstrates the full chain. Do not add continuously running instrumentation to the product just to perform this investigation.

**Nonnegotiable:** no relaxing the existing Settings retirement barrier, inventing another render/simulation clock, modifying accepted original Bubble or Neon Lake, changing any of the seven mutable presets to disguise renderer failures, or deleting/closing any earlier checklist item without explicit operator instruction. The source correction to the endless-wrap scheme must be a physically convincing world architecture, not another camera-coupled trick.



## 13. Live reactivity, all-angle world and Settings ownership | operator evidence 2026-10-19 (EVERY ITEM OPEN)

**Admission:** `[~]` indicates a failed/unverified/at-most-partial item, never acceptance. Retain ALL prior §§10–12, including every historical failed mechanism, failed attempts and acceptance detail. Neither a passing numeric test nor a GL link discharges physical evidence. Do not silently convert this to a changelog. Original Bubble and Neon Lake acceptance remain intact. All seven operator-authored presets remain freely editable, never immutable test goldens.

- [~] **COMPLETELY FUCKED | Scalar reactivity cannot represent full musical changes.** The latest `logs3a0d4fa1175.zip` contains an Extruded Bubble playback edge on 2026-10-19 01:11:33 explicitly reporting `energy_level=1.000`, while bars/waveform were zero *at that recreation edge*. A prior explanation blaming the entire failure on a persistently near-zero energy meter was **wrong**. The scalar in `logical_frame_capture._capture_extruded_bubble` previously fed every level-driven control, while 2D Bubble explicitly consumes `BeatEngine.get_bubble_energy_bands()` to survive flattened post-AGC/control lanes. Operator observed **no visible big or small size changes**; Dynamic Floor produced only a small **rapid non-musical oscillator**. Requiring a Dynamic Floor is not an acceptable solution. No new dynamic/manual floor, DSP, peak normalization, polling or cadence is authorized.
- [~] **COMPLETELY FUCKED | Existing full-dynamic Bubble band feed candidate, operator-retested and FAILED (2026-10-19).** The latest real-display run with this candidate still produces **no music-correlated size changes in large or small bubbles**, nor useful reactivity elsewhere. Only maximum Sensitivity or Dynamic Floor can produce a *small, rapid, essentially constant* pulse, not a response to the track. Source-connected band values and passing negative-control tests therefore **do not establish anything visible**. **Retain implementation detail for future falsification:** current production capture now reads the **same** `get_bubble_energy_bands()` bass/mid/high feature snapshot as 2D Bubble (falling back to the existing pre-AGC feed only if the method is absent). It feeds an optional band tuple through the *existing* `ExtrudedBubbleFrameRuntime` → `MusicInput`, with generation/activation admission preserved. During playback, continuous level used for Stream Speed, Drift, Rays, population and Emission is derived from that band tuple rather than saturated all-mode intensity. Big radius responds primarily to bass plus vocal/body support; small/mid radius to mid/high plus bounded bass. Each follows a separate slow baseline/positive body delta and asymmetric attack/release. Production no longer uses the repetitive idle/sustained sine as actual big/small radius input; kicks add a bounded smooth accent. **This source-side attempt is now CONFIRMED UNSUCCESSFUL in real display testing**, even if the underlying band read/mapping code is present. Check precisely what values 2D's source publishes for quiet, transients, held energy, and clipped/saturated segments. Measure per-ID radius in pixels across real recorded music; preserve each authored Breathing/Small Pulse Range. A source-only test that varies bands while holding scalar at 1.000 is a **negative-control regression test, not acceptance**. Old scalar-only fixtures preserve their old oscillator for historical test comparison; they must not be mistaken for production reactivity tests.
- [~] **COMPLETELY FUCKED | Music-driven emission, rays and idle ownership still physically rejected, including latest full-dynamic-band candidate.** `extruded_bubble_particles` was previously consumed **twice**: once via the smoothed simulation follower and again by the renderer's `speck_amount`. In this candidate, `speck_amount` now consumes the already ranged `state.emission` **once**, preserving its intended nonlinear density/brightness shaping. The quiet/loud authored endpoints therefore no longer get compressed toward the middle by second mapping. **Operator-confirmed FAILED again, not simply pending first acceptance:** the squared speck count may be visually weak; particle birth, bead chains and wake fizz remain distinct systems; light ray brightness/shimmer and motion contrast are not proven; idle appeared faster than music. Use captured source features, snapshot fields, GPU counts/uniforms and matched pixels to locate the first response loss. Do not infer `emission` is fixed because a value or count changes in code.
- [~] **COMPLETELY FUCKED | Real world-space orbit, wrap, true perspective, material-opacity fade.** The explicit per-camera wrapping, GPU free-chain turning, coincident apparent sizes across depth, and radius-as-alpha entrance remain unchanged by this candidate. Do not claim progress from the band fix. The user wants the camera *inside the coverage*, free to inspect a fixed simulation-owned world in any direction. Design **physical all-around coverage** without copies, camera-bound relocations or scene-empty angles. Replace old seam-only/size-cancelling tests with same-ID world coordinates and rendered pixel projections across yaw, tilt, pan and zoom; ordinary and fused bubble DoF and coherent stream direction must be validated together. Bubbles appearing abruptly on camera orbit are a failed fade/lifetime issue, not a camera fix. Maintain the independent fused-cluster near-DoF item from §11A.
- [~] **COMPLETELY FUCKED | Extruded Bubble → Settings ownership timeout.** In the supplied log, Settings requested/admitted at **01:11:35**, the Quick retirement barrier armed with **941 QObjects and three Python owners**, and at **01:11:43** failed with `qobjects={}`, `python_owners={'QuickDisplayVisualizerOwner': 1}`, `resources=[]`, `thread_work=[]`, `global_subscriptions=[]`. **Do not weaken, lengthen or bypass the strict barrier.** The mode-specific Settings failure is real. `ui/tabs/media/extruded_bubble_builder.py` delegates to `build_spec_mode_ui`; source inspection alone does not prove which Python root retains the retired visualizer. Prior Neon Lake failure involved an independent cycle in display Qt-signal closures, but that former cause is not proof for this recurrence. Need diagnostic referrer attribution of the particular retired `QuickDisplayVisualizerOwner`: run the existing diagnostic build's **failure-only** `[LIFECYCLE_BARRIER][PYTHON_OWNER_REFS]` path and identify the exact strong reference (signal, closure, presenter, logical runner, pending activation, Settings body), then sever it at the authentic owner. Confirm return to Settings without orphan owners across repeated cold/warm Extruded Builder openings and changed presets. If this is builder-owned, fix its lifetime, not the barrier. No speculative always-on scans or instrumentation.
- [~] **CAPTURE/PERF AUTHORITY:** each item still requires either explicit operator real-display validation or a visually capable agent with full-resolution offscreen OpenGL capture, identical source-clip driving and per-bubble identity/pixel tracking. Run at least silence → changing bass → vocal/mid/high → held loud → silence, with Dynamic Floor disabled and enabled as a **diagnostic comparison**, never as a required crutch. Capture `logs/visualizer_recordings`, show the actual band tuple versus scalar 1.000 and snapshot → final pixels. Agent must also benchmark the micro-glass bead shader, band-read cost and separate pass median/p90 at 1672×941/2560×1440. Any uncertain result remains `[~]`.

## 14. Live diagnostic gate: `logs3a0d4fa1177.zip` frame trace, Settings stress, missing value evidence (2026-10-19; EVERYTHING OPEN)

**This is a live checklist and source-to-evidence gate, NOT a progress/change log.** Keep §§10–13 and the dedicated historical ledger verbatim in meaning and detail; `[~]` always means failed or at most partial and does not constitute acceptance. **Operator verdict remains `[~] COMPLETELY FUCKED` for ALL Extruded Bubble reactivity**: big/small bubbles visually do not grow/shrink with the music; high/max Sensitivity or Dynamic Floor causes only slight *rapid, repetitive, non-musical* motion; idle water and chains can seem faster than playback; rays, particle emission, stream speed and drift show no accepted musical changes. No test or source wiring supersedes the observed screen. This log archive adds evidence and narrows the next investigation; it is NOT a passing retest.

- [~] **COMPLETELY FUCKED | New operator-controlled settings sweep still produces no useful response.** `logs3a0d4fa1177.zip` → `screensaver_spotify_vis.log` has 55 `[VIS_TECH_CONFIG] mode=extruded_bubble` records across retained historical logs; their configured Sensitivity values include `0.400, 0.530, 0.770, 0.910, 0.990, 1.800, 2.070, 2.160`, with Dynamic Floor `True` and `False`, block sizes `256` and `512`, and adaptive `True`/`False`. Within the **02:25–02:30** test window specifically, `quick_owner_configure` includes Sensitivity `2.160` at `02:25:05`, `0.910` at `02:25:45`, `0.770` at `02:26:36`, `2.070` at `02:29:09`, and `2.070` with `dynamic_floor=True` at `02:30:40`. This proves varied technical configurations were logged by the active visualizer owner, **not** that any particular authored Extruded Bubble Range, band tuple or GPU uniform changed. Preserve these concrete times and differentiate global technical Sensitivity from mode-owned Breathing/Small Pulse/Emission/Rays Ranges. The operator independently confirms many `--set` changes without any useful perceived effect. Do not blame insufficient Sensitivity or mandate Dynamic Floor.
- [~] **PARTIAL (BARELY) | Binary frame trace rules out a globally stopped pipeline, NOT static visual inputs.** The archive contains `screensaver_frame_trace.bin` (22,117,120 bytes). The repository's `tools/frame_trace_report.py` decodes **614,364 records**, spanning **348.70 s** of trace timestamps: **15,012 logical publications**, **13,807 GUI snapshot publications**, **12,693 Quick sync consumes**, **12,245 renderer draws** and **12,245 frame swaps**, with **11,572 audio-analysis begin/ready pairs**. For screen 1, the built-in lifecycle-aware *steady* swap report gives median **11.503 ms**, p99 **19.202 ms**, **23 gaps >25 ms** (5 >50 ms, 1 >100 ms, max **124.832 ms**) after excluding lifecycle windows and >=1 s not-rendering intervals; there are **11 lifecycle starts and 10 ends**, totaling 227 s classified as lifecycle windows. Do not equate the full 348.70-s timestamp span, the report's filtered steady span or minute-bucket event totals with continuous gameplay time or average FPS; trace windows can straddle Settings/restarts and the monotonic timestamps are not independently tied to wall-clock Settings changes. Presentation is alive repeatedly; **this record format contains neither actual bass/mid/high tuples nor same-ID bubble radii, actual projected pixels, opacity, bead travel speed, or rendered ray intensity**. Occasional stalls are a separate performance/lifecycle question, not evidence that the entire reactivity mode was frozen.
- [~] **COMPLETELY FUCKED | An `energy_level` log value alone cannot settle input quality.** The archive's `screensaver_spotify_vis.log` has `[VIS_PLAYBACK_EDGE]` values near `0.045` at playback admission (02:34:53 in the retained logs) and `1.000` at subsequent **recreation edges** (02:34:59 onward, with `playing=True` and bars/waveform edge levels zero). These are edge samples with different contexts, **not** a continuous energy or Bubble-band graph. Previous explanations asserting either “always low” or “all playback saturated at 1.0” are unsupported. Record actual timestamped `get_bubble_energy_bands()` bass/mid/high and `get_musical_intensity()` during the **same admitted live steps** as the bubble snapshots, with playback/generation identity and onset serial; capture offline/explicitly only, not a permanent hot-path observer.
- [~] **COMPLETELY FUCKED | Production breathing still has a specific unproven transfer function.** `logical_frame_capture._capture_extruded_bubble` asks `get_bubble_energy_bands()` only while playing, supplies a zero tuple otherwise, then `ExtrudedBubbleFrameRuntime.advance` carries it into `MusicInput`. In `ExtrudedBubbleSimulation.advance`, a big/small body lane targets `min(1, body*0.38 + max(0, body - average - 0.015)*2.7)`, with smoothing before application. In `_snapshot`, the production radius uses `base_radius * (1 + swell + pop_expansion)` where `swell` is a nonnegative big/small envelope times the existing typed Range. **This only swells relative to base radius; there is no normal below-base contraction.** A steady band can hold an enlarged radius and smoothing/Range attenuation can erase meaningful excursions. These are credible *candidate causes*, not proven dominant until actual band → envelope → stable-ID radius → projected pixel displacement is measured. Note: `snapshot.breath` exposes the kick/breath follower, **not** the production big/small per-object `swell`; trace records at `BUBBLE_STRIDE=8` contain `[x,y,z,radius,alpha,swell,id,cluster]`. For comparison, original 2D Bubble's accepted body feature/render behavior is the reference contract; do not modify 2D Bubble to make this candidate pass.
- [~] **PARTIAL (BARELY) | Existing logical trace plotting can exercise the wrong branch.** `tools/visualizer_replay/extruded_bubble_traces.py` calls `ExtrudedBubbleFrameRuntime.advance(... intensity=..., controls=...)` **without** `body_bands`. The runtime substitutes `(0,0,0)` before calling the simulation, so this plot cannot validate the live production band's effect; its `breath` graph is the wrong output for actual big/small swell. `tools/extruded_bubble_capture.py` goes through `replay_clip` and `logical_frame_capture` instead, but its current `capture.json` records global scalars/counts and GPU timings **without the band tuple or stable-ID radius/pixel series**. It can yield images, which a visual agent can inspect, but is **not yet an end-to-end causal value trace**. Before trusting replays, assert that they exercise the same source, Settings, playback/generation and per-object radius branch as live capture. Do not retrofit always-on polling/logging.
- [~] **COMPLETELY FUCKED | Per-ID visibility and world ownership still contaminate measurements.** The source audit independently established camera-dependent `_wrapped_turn()`/GPU `wrapTurn()`, 29.49-unit world relocations, true-depth perspective cancellation, `sqrt(alpha)` geometry shrinking instead of material opacity and divergent bead headings. Any apparent radius/breathing measurement from an onscreen object must track **the same simulation identity**, world position, actual rendered/projection radius, camera pose and front-surface DoF across samples. A jump in a compacted slot, a rotating fake world, a cluster membership change or a pop is not musical breathing. The camera should be placed *inside genuine 360° physical coverage* and allowed to look freely; the world must not chase it. Do not quietly turn off wrapping and accept vacant viewing angles.
- [~] **COMPLETELY FUCKED | All other reactivity requires the same value-to-pixel chain.** With an identical recorded quiet→onset→changing music→held loud→release sequence, record the actual **one-time** author-owned low/high Range values, measured band tuple, smoothed logical value, immutable snapshot fields and draw-side driver/uniform and actual affected image region: (a) large-bubble and small-bubble `swell` plus screen radius; (b) stream speed + stable-ID position deltas; (c) bead count/visibility/heading and source-attached wake lifetime; (d) water/surface optical-flow speed quiet versus playing; (e) ray strength/flicker/fan and ray-only pixel-difference or shaft area; (f) emitted speck count/brightness and fizz/wake behavior. Include idle playback gaps. Changing control labels or downstream scalars without matched output does **not** demonstrate correction.
- [~] **Required next agent capture (no source changes made in this documentation pass).** On the local Windows/OpenGL 4.6 environment, use the existing `logs/visualizer_recordings` (absolute operator path `F:\Programming\Apps\ShittyRandomPhotoScreenSaver\logs\visualizer_recordings`), the tested native `--frame-trace`, and `tools/extruded_bubble_capture.py` with the unchanged operator-authored presets, plus explicit **opt-in, bounded capture-only** band→Range→snapshot→instance→pixel instrumentation where the existing tool lacks fields. Compare Dynamic Floor **off by default** with on only as a negative-control; normal and extreme Sensitivity; same clip/interval/preset/fixed camera; real original 2D Bubble as a positive visual response comparator. Export a synchronized table/JSONL with generation/activation, timestamps, settings version, full band tuple, onsets, big/small per-ID base radius/swell/alpha, logical and instance radius, projection depth/screen radius, cluster membership, and specific ray/emission/stream scalars, plus full-resolution frame sequence/contact/motion and ROI/per-ID pixel measurements. Record first point where correlation/dynamic range vanishes, not another speculative multiplier. Only the operator or a visually capable agent with working **offscreen renderer and capture** can validate the art. Native timing/perf counters (micro-glass bead-pass GPU median/p90 at 1672×941 and 2560×1440, with fixed density and warmed frames) remain an independent mandatory `[~]` gate. Do not modify the strict Settings lifecycle barrier, accepted Bubble/Neon Lake or mutable presets.

**Decision tree for the next source agent:** if musical bands are flat/zero, investigate live `BeatEngine` publication, feature identity, playback admission and technical config **before** tuning geometry. If bands vary but mapped envelope/swell does not, inspect the response equation/smoothing and authored Range reach. If logical stable-ID radii vary but instance/projection pixels do not, diagnose view-depth cancellation, instance/opacity representation, clipping/DoF or shader routing. If those pixels vary but operator cannot perceive changes, fix **measured scale/timing/contrast against the 2D Bubble reference**, not the DSP by assumption. Apply the same stepwise method to rays, idle, beads, movement and emission. Keep every status `[~]` until explicit operator acceptance.
