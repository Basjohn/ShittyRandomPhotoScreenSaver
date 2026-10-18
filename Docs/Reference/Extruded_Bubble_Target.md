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

## 2. Reactivity (concept foundation: original Bubble)

The original Bubble simulation (`widgets/spotify_visualizer/bubble_simulation.py`, ticked by
`bubble_frame_runtime.py`) owns spawn, drift, swirl, stream direction, big/small lanes, collision pops, pulse and
trail smear; it is the reactivity authority and BTF binds it. Extruded Bubble **reads** its logical snapshot (positions,
radii, pulse, lane, trail) and derives only presentation from it: a deterministic per-bubble depth from its identity,
3D placement inside the framed volume, defocus, and the shell's response to the bubble's pulse. No second clock,
capture, DSP, floor or renderer-owned simulation. Improvements to reactivity go through the original Bubble with its
replay audit (`tools/visualizer_replay/mode_audit --modes bubble`), never into the 3D renderer.

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
- **Reactivity:** light shafts react to the music (intensity, spread or flicker), alongside bubble breathing, speed
  and drift, all through the original Bubble's logical reactivity (BTF), never a second clock or DSP.
- **Sizes:** strong variation with a slight bias to small bubbles, authored by on-screen size bands.
- **Camera down:** a darker abyss below, not an ocean floor (operator 2026-10-17); the seabed primitive stays
  in the library unused by Extruded Bubble.
- **Highlights and colour (operator 2026-10-17):** highlights sit toward the light and inset from the rim, never
  merging with the edge; glints read as light on glass, not stars; bubble colour follows the scene's water and light.
- **Look:** parity with all six mocks, judged side by side at full resolution with crops
  (`tools/labs/extruded_bubble_lab.py` renders one variant per mock against it).

- **Presets (operator 2026-10-18):** each mock must eventually be an easily achievable preset.

## 9. Preset surface (EB2 draft, 2026-10-18)

Every look the lab renders is a preset of a small control surface. The lab already stores scenes in its three layers
(`ENGINE` constants, `MODES` surface/deep, lean per-scene values; `effective()` merges them, proven pixel-identical
to the flat settings). EB2 turns this into the typed Settings spec; the lab scenes are the reference presets, and the
spec is accepted only when each of them can be authored from these controls alone. Amounts use the EB5a range slider
(quiet..loud). Buckets follow the existing Settings pattern (nested, closed by default, short Title Case names).

| Bucket | Control | Lab knobs it sets |
| --- | --- | --- |
| Light | Light Type: Sunlit Surface / Deep Light | `mode` (and everything in `MODES`) |
| Light | Light Direction (around, height) | `sun`, `light_view`, `spec_view` (highlight direction derived from it) |
| Light | Light Colour | `light`, `shaft`, `sky` tint, default `speck_warm` |
| Light | Light Strength | `glint_power`, `light_power`, `surface_gain`, `glow` |
| Light | Light Rays (range) | `rays` |
| Light | Ray Softness | `fan_contrast`, `fan_march`, `fan_rays` (deep: `ray_focus`) |
| Water | Water Colour, Depth Colour | `water`, `deep`; `absorb` derived from them |
| Water | Haze | `mist` |
| Water | Light Veils | `veils` |
| Glass | Clarity | `face_reflect` |
| Glass | Rim Glow | `probe_fill`, `proxy_power` |
| Glass | Iridescence | `film`, `film_range` |
| Glass | Softness | `rough`, `inner_blur` |
| Glass | Sparkle | `sparkle`, `speck_glow`, `glint_sharp` |
| Bubbles | Large Bubbles, Small Bubbles, Bead Chains (ranges) | `mid_count`, `small_count` + `fizz`, `chains` |
| Bubbles | Flow Direction, Drift, Sway | `travel` + `streak`, `drift`, `sway` |
| Bubbles | Collision (Fuse / Pop / Bounce triangle, §8) | not in the lab yet |
| Particles | Amount (range), Size | `specks`, `speck_size` |
| Particles | Warmth, Glow | `warm_share` + `speck_warm`, `speck_bloom` + `dust` |
| Particles | Bands | `banded`, `band_freq`, `cloud_contrast`, `cloud_floor`, `cloud_glow` |
| Lens | Focus, Aperture | `focus`, `aperture` + `near_coc` |
| Lens | Exposure | `exposure`, `hdr_exposure` |

Not controls: `ENGINE` (`shell`, `iors`, `lens`); mode-implied values (`near_lens`, `near_reflect`, `shaft_scale`,
`shaft_soft`, `ray_cut`, `fan_reach`, `surface_sky`, `crisp`, scene geometry `surface`/`shaft_y`); `columns` (a
population layout the abyss uses, to become a Bubbles choice if a second scene wants it). Camera `pitch` is the view
pose of the shared framed camera (FC), persisted outside art; a preset may suggest a starting pose only if FC admits
it. Remaining folds to settle at EB2: mock 1's `ray_cut` 0.08 (mode 0.1), camera-down's `glint_sharp` 600 (300
elsewhere) and `rough` 0.03 / mock 6's 0.1 (mode 0.05) are kept as per-scene values until Sparkle and Softness exist.
