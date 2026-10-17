# Extruded Bubble: target contract and shared-primitive inventory (§4A G0)

Status: **G0 target contract** (2026-10-17). `Current_Plan.md` §4A/§4B own sequencing; `Scene3D_Resources.md` owns the
shared resource contracts; `Docs/Guardrails/Bubble_Temporal_Fidelity.md` (BTF) binds the reactivity. This file records
what the operator's mocks demand, what the shared Scene3D layer already provides, and which primitives must be proved
(in order) before an Extruded Bubble renderer exists. It is not an implementation of Extruded Bubble.

## 1. Visual target (operator mocks, `tmp/Bubbleexamples`, 2026-10-17)

Six frames: three looking up toward a sunlit surface (bright, mid, dark water), one with wake tendrils, one into the
abyss, one down onto a caustic-lit seabed. Every element below is visible in at least two of them.

| # | Element | What it must look like | Measurable goal |
| --- | --- | --- | --- |
| T1 | Bubble shell | Thin clear film: dark-ish interior that shows the water behind it slightly bent, a bright Fresnel rim, one or two sharp specular glints, faint iridescent (thin-film) fringes toward the rim | Rim brighter than centre at every size; transmission bends the background (not a flat alpha disc); iridescence varies with view angle and film thickness |
| T2 | Silhouette and size range | Perfect circles from a few pixels to a third of the card; touching doublets/triplets | Exact sphere silhouettes at any size (no tessellation facets), depth-correct intersections where two bubbles touch |
| T3 | Overlap | Bubbles in front of and behind each other, each still visible through the others | Order-independent: the same picture whatever the draw order (G3A) |
| T4 | Depth and focus | Near bubbles large, soft and bokeh-like; far ones small and crisp; a few hundred micro-bubbles in columns | Per-bubble defocus by depth; thousands of micro-bubbles within the tier budget |
| T5 | Water above | Bright Snell's-window surface with moving ripples and refracted sunlight at the top of frame | Animated surface normals, total internal reflection outside the window, brightness falling off with depth |
| T6 | Light shafts | God rays from the surface fanning down, broken by the surface ripples | Reuse the shared `LightShafts` (landed 2026-10-17) with a surface-pattern source |
| T7 | Caustics | Shimmering caustic network on the seabed (camera down) and faint caustic light on bubbles | Animated analytic caustics; no texture asset |
| T8 | Wakes (one mock) | Curling translucent trails behind larger bubbles | Optional; demands G4 ribbons only if accepted (§4A says demand-driven) |
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
