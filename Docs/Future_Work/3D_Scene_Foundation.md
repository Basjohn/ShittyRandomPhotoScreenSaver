# 3D Scene Foundation — decomposition (live checklist)

Promoted by the operator on 2026-09-29 ("I agree with all of these … safer sooner … go ahead"). `Current_Plan.md`
owns the order; this file owns the detail. Delete it when the last slice closes, leaving the durable contract in
`Docs/Reference/Transitions.md` (and a Visualizer reference note for the shared option).

**Rollback / comparison HEAD:** `3185645a` (Exploding Tiles on the first foundation, accepted and closed).

## Goal

One shared, high-fidelity 3D foundation whose cost is always adjustable, used by every 3D transition and available as
an **option** to Visualizer modes (none has to use it). Fidelity features live in the foundation, each behind the 3D
Detail tiers; effects keep their own authored motion, look and state.

## Current inventory (at the rollback HEAD)

| Piece | Where | Consumers | Tests |
| --- | --- | --- | --- |
| GLSL library + CPU mirrors (hash, camera, impulse, departure solver, lighting, ember, planar shadows, streaks, tier table) | `rendering/gl_programs/scene3d.py` | Exploding Tiles | `tests/test_scene3d_foundation.py` |
| Blend scopes, multisampled `SceneTarget` | `rendering/quick/scene3d/` (was `transitions/scene3d_support.py`) | Exploding Tiles | same |
| Programs/meshes/underlay/depth clear (`MeshResources`) | `rendering/quick/scene3d/resources.py` (was `transitions/mesh_support.py`) | Glass, Crumble, Tiles, Accretion, Ink, Melt | transition GL suites |
| Park after every run; fence restores framebuffer + blend | `rendering/quick/transitions/render_host.py`, `render/background_node.py` | all transitions | `test_qtquick_transition_state_fence.py`, foundation tests |
| 3D Detail setting | `transitions.detail_3d`, Transitions → SETUP | Exploding Tiles | parameter-resolution and tab tests |

Other 3D effects, each with its own authored camera: Glass Shatter (pinhole, distance 3.0, `clamp(-z/5)` depth),
Directional Pixel Accretion (pinhole, 3.0, `fract(sin())` hash), Crumble (`fract(sin())` hash), 3D Block Spins
(orthographic by design). Visualizers: one `QSGRenderNode` per display, viewport = the whole render target, card clip
by `VisualizerClipHost` (SDF/stencil), fence `rendering/quick/visualizer/gl_state.py` (restores blend, not
framebuffers); Voxel Sphere is isolated and golden.

Measured (2560x1440, RTX 4090, Exploding Tiles, warm): GPU mean High 0.98 ms / Balanced 0.038 / Performance 0.016;
CPU submit 0.8–1.7 ms per frame (about 40 Python GL calls); cold first frame 80–150 ms (four program compiles);
High target ~133 MB per display during a run.

## Ownership rules (every slice)

- **State:** analytic from inputs; no per-frame CPU simulation, no uploads of evolving arrays. Per-run work is solved
  once (request resolution, COMPUTE preparation, or a once-per-run renderer cache).
- **Time:** transitions use run progress, plus real seconds (`progress x duration`) only for real-time rates
  (rumble, shake, shutter). Visualizer modes use **only** the logical time in their snapshot: one authored clock,
  R-69 and Bubble Temporal Fidelity are binding. No new clock, timer or cadence anywhere.
- **Settings:** canonical defaults and resolution before admission; renderers never read Settings. A Visualizer tier
  setting arrives with the first Visualizer consumer (no control without a consumer).
- **GPU resources:** context-local, owned by the consuming renderer; per-run targets dropped at `park()`
  (transitions) or on mode retirement (Visualizers); failed deletions keep handles for retry; no allocation per
  frame; the fences restore every piece of GL state the foundation touches.
- **Sphere:** never migrated or used as a base; its promotion gate stands.

## Slices, in order

Each slice: reward, risks, performance hazards to avoid, acceptance bars. Commit and push per slice.

### S1 — GLSL self-test harness (regression net first) — LANDED
- [x] Test-only helper that runs library functions on the GPU for a table of inputs (float render target, readback)
  and compares them with the CPU mirrors: impulse, departure travel, projection, cast-on-plane, rotation, hash
  determinism and uniformity. Never imported by production.
- **Reward:** the library can grow (S3–S9) without mirrors and shaders drifting apart; catches GPU precision faults.
- **Risks:** float32 vs Python doubles need explicit tolerances; RGBA32F targets are required (GL 4.1 has them).
- **Hazards:** none in production.
- **Bars:** every function within tolerance; a deliberately perturbed mirror fails (negative control).
- **Landed:** `tests/test_scene3d_glsl_mirrors.py` (every library function, including hash, rotation, shading,
  point light, ember, soft rect, clip depth and streaks, against mirrors in `scene3d.py`; hash uniformity; drifted
  mirror caught).

### S2 — Shared home and the Visualizer option (sharability, done early) — LANDED
- [x] Move the GL helpers (`MeshResources`, `SceneTarget`, blend scopes) into a neutral package
  `rendering/quick/scene3d/`; update the transition importers; no compatibility shim.
- [x] `SceneTarget` covers any pixel rect of the render target (offset viewport inside the target, composite by
  `gl_FragCoord - rect`), with size buckets (round up to 64 px) so a CUSTOM resize drag does not reallocate per frame;
  the inherited scissor is suspended inside the target and restored for the composite.
- [x] ~~Visualizer fence restores draw/read framebuffer bindings~~ Superseded on inspection: that fence runs on every
  Visualizer frame (CHK26-protected); `SceneTarget.scope` restores framebuffers, viewport and scissor itself, even
  on exceptions, so modes that do not use a target pay nothing.
- [x] Document the Visualizer opt-in: include `SCENE3D_GLSL`, logical time only, target sized to the card rect and
  composited inside the clip host's begin/end, target released on mode retirement, tier setting with the first
  consumer. No Visualizer mode changes.
- **Reward:** the foundation stays one owner as it grows; Visualizers can adopt it without a second copy.
- **Risks:** import churn across seven transition modules (pure move, caught by the suites); a sub-rect target must
  reproduce a direct draw exactly (clip and scissor coordinates).
- **Hazards:** reallocation thrash during resize (bucketed); a target sized to the whole window for a small card
  (rect-sized now); a card composite outside the clip (composite inside the clip host's begin/end).
- **Bars:** sub-rect target equals a direct draw (single-sample flat scene, exact pixels); shrinking inside a bucket
  does not reallocate; state handed back after a mid-scene failure; all transition suites green.
- **Landed:** `rendering/quick/scene3d/` (`frame.py` item quad + `SceneFrame` + `item_pixel_rect`, `resources.py`,
  `target.py`, `passes.py`); `mesh_support.py` and `scene3d_support.py` removed, importers updated;
  `tests/test_scene3d_target.py` (offset card equals a direct draw at 1 and 4 samples, inherited scissor honoured,
  bucket reuse, state handed back after a mid-scene failure); Visualizer reference §16.

### S3 — Per-frame uniform blocks — LANDED
- [x] One std140 uniform block per effect frame, laid out from a single Python field list (shared packing helper),
  updated with one buffer write per frame and bound for every pass; Exploding Tiles first.
- **Reward:** ~40 GL calls per frame to a handful; the render-thread CPU cost Visualizers need to afford 3D.
- **Risks:** std140 alignment (vec3 padding) — verified on the GPU through S1; binding-point collisions with Qt's RHI,
  which also uses uniform buffers.
- **Hazards:** GPU sync stalls from rewriting a buffer in flight (orphan with `glBufferData(NULL)` or a small ring);
  leaking the uniform-buffer binding (the fences capture and restore the indexed binding the foundation uses).
- **Bars:** identical pixels before/after for Exploding Tiles at every tier; CPU submit measured lower; fence test
  covers the uniform-buffer binding.
- **Finding (measured):** uniforms were not the main per-frame cost. The block removed 19 of 165 GL calls with no
  measurable gain; ~40 of the rest were the transition fence's state captures, and PyOpenGL's checked getters cost
  ~13 us each (they build an output array) against ~2.7 us for the raw entry points into a small ctypes buffer.
- **Landed:** `Scene3DBlockLayout` (pure std140 layout, GLSL and packing from one field list) in
  `rendering/gl_programs/scene3d.py`; `rendering/quick/scene3d/uniforms.py` (`UniformBlock`: orphaned upload each
  frame, binding point 15, `bound()` hands back the previous range and generic binding); `rendering/quick/gl_query.py`
  (raw state queries) used by the transition fence, the depth clear, `SceneTarget` and `UniformBlock`; Exploding
  Tiles on one `ExplodingTilesFrame` block. Pixel-identical at every tier. Warm CPU submit per frame (steady
  min-of-medians, 320x180): High 1.23 -> 0.90 ms, Balanced 1.18 -> 0.86 ms (~27% less). The fence speed-up applies
  to every transition. The Visualizer fence (CHK26-protected) still uses checked getters; switching it is an
  operator decision. Tests: `tests/test_scene3d_uniforms.py` (driver-reported offsets equal the layout, values
  arrive, binding restored).

### S4 — Camera — LANDED
- [x] `sceneProject` takes a camera (distance per effect, plus offset, tilt and shake) from the frame block; at rest it
  maps z = 0 exactly onto the item (photo fills the view).
- **Reward:** existing effects keep their authored distance (Glass/Accretion 3.0, Tiles 3.4); enables camera shake,
  Cube Turn's pull-back, Page Curl/Relief Rise tilt, Visualizer parallax.
- **Risks:** any camera motion moves the photograph plane too.
- **Hazards:** exposing the frame edges (R-63: black = 0) — a moving camera must overscan (zoom in by at least the
  shake/tilt amplitude) or move only the pieces; shake at real-time rates; camera at rest at both endpoints.
- **Bars:** at rest, projection mirrors match S1 and endpoints stay exact; a shaken camera never shows uncovered
  pixels at any aspect (edge-pixel test).
- **Landed:** `sceneProjectAt` (resting camera at any distance; `sceneProject` = 3.4), `sceneCameraSpace` /
  `sceneProjectCamera` (a = distance, zoom, offset; b = tilt), CPU mirrors, `scene3d_camera_overscan` (least zoom that
  keeps the photograph plane covering the view) and `scene3d_camera_shake` (deterministic, 3-7 Hz real time,
  bounded); `MeshResources.draw_camera_plane` draws the photograph through the camera. At rest the camera is bit-exact
  with `sceneProjectAt` and the plane equals `draw_image`. No effect moves its camera yet (a look decision per
  effect). Tests: `tests/test_scene3d_camera.py` (overscan is least and sufficient over 300 random cameras and four
  aspects; no uncovered pixel with it, uncovered pixels without it), GPU mirrors in
  `tests/test_scene3d_glsl_mirrors.py`.

### S5 — Existing 3D transitions onto the library and 3D Detail — LANDED
- [x] Glass Shatter: shared camera at 3.0, `SceneTarget` on High, park lifecycle. It keeps its authored linear depth:
  the library's near-plane depth has coarser precision at Glass's depth and flipped a few coplanar bevel pixels.
- [x] Directional Pixel Accretion: shared camera at 3.0 (authored linear depth kept), integer hash, `SceneTarget` on High.
- [x] Crumble: integer hash for its stone lattice, crack variation and debris grain, `SceneTarget` on High. Its own
  camera (3.15 with an authored magnification clamp) is kept.
- [x] 3D Block Spins: stays orthographic by design; `SceneTarget` on High only.
- [x] Exit guarantees: each effect already has its authored departure (Glass ray-exit, Crumble fall, Accretion is an
  arrival); the solver is not substituted where it would change accepted trajectories.
- **Reward:** smooth edges on High for every 3D transition; one camera and one hash family; hashes identical on every
  GPU (R-94 class).
- **Risks:** accepted looks (Glass and Melt are operator-accepted). Camera and depth changes must be pixel-identical at
  Balanced; the hash swap changes which pattern a seed produces (same statistics, different realisation) for Crumble
  and Accretion — reviewed on stills.
- **Hazards:** High adds ~1 ms GPU per frame to each effect at 1440p; the depth mapping change must not reorder
  visible pieces.
- **Bars:** Balanced frames equal the pre-migration captures (Glass exact; Crumble/Accretion statistics and endpoints);
  every existing GL/endpoint/departure suite green; High vs Balanced differs only at edges.
- **Landed:** every 3D transition request carries `detail` (`resolve_scene_detail`; a request built without it draws
  directly, `scene3d_request_detail`). Against pre-migration captures at Balanced: 3D Block Spins exact, Glass Shatter
  max 1-2 levels (float rounding), Crumble and Accretion differ only in which random pattern a seed gives (stills
  reviewed: same style). Tests: `test_every_3d_transition_honours_the_tiers_and_parks` (every tier: exact near
  endpoints, framebuffer restored, High differs only at edges, park drops the target) and
  `test_every_3d_transition_request_carries_the_3d_detail_tier`.

### S6 — Bloom (then HDR, decided on measurement) — LANDED (bloom; HDR not needed yet)
- [x] A bright-pass and downsample/upsample chain (1/2 to 1/16) over the resolved target, added back in the
  composite. Glow comes only from **emissive** content, which effects write into the target's alpha (the photograph
  writes 0), so the pictures themselves never bloom and endpoints stay exact.
- [x] HDR deferred: the emitted-brightness alpha and RGBA16F bloom levels give smooth glows without an HDR scene
  target; revisit only if additive light visibly clips.
- **Operator direction (2026-09-29):** post effects and anti-aliasing are per-transition settings on each transition's
  page, authoritative over the global tier; "Auto" follows the tier. `resolve_scene_quality` is the single place they
  combine (no second source of truth). Motion Blur (S7) follows the same pattern.
- **Landed:** `rendering/quick/scene3d/post.py` (`BloomChain`), `SceneTarget.scope(..., bloom=)`, emitted-brightness
  alpha (Exploding Tiles: sparks, hot cracks, embers, flash), Anti-aliasing choices on every 3D page and Bloom/Bloom
  Strength on Exploding Tiles, tier flag `post_effects` (High, Balanced). Tests: bloom glows emitted light only (bright
  non-emissive field unchanged), photographs never bloom late in the run, Auto/On/Off precedence over each tier,
  anti-aliasing choice decides the scene target for every 3D transition, Settings round trip. Cost: +0.28 ms GPU
  over 4x at 1440p (RTX 4090) as first measured; the blit resolve behind the rest was removed under S10.
- **Reward:** real glow on sparks, embers, hot cracks, glints and highlights.
- **Risks:** bloom leaking from bright photo areas (prevented by the emissive mask); a changed composite on High.
- **Hazards:** extra full-screen passes (downsampled chain, ~0.2–0.4 ms target); per-run allocation only; no
  allocation per frame.
- **Bars:** endpoints exact on High; a photo with a bright sky does not glow at 0.0001; bloom measured and parked.

### S7 — Analytic motion blur — LANDED (every 3D transition)
- [x] A per-transition Motion Blur choice (Auto, Off, On), Auto following the tier's post effects. Every piece's
  motion is analytic, so its screen velocity comes from evaluating it at `t` and `t - shutter` (shutter in real
  seconds); a bounded-sample blur along velocity. Chosen: a velocity attachment with a McGuire-style reconstruction.
  Geometric stretching would need translucency, and so sorting, on opaque depth-tested pieces.
- **Landed:** `rendering/quick/scene3d/motion.py` (`MotionBlur`: separable tile max, neighbour max, 16-tap gather),
  `SceneTarget.scope(..., motion_blur=)` with a write-protected RG16F attachment opened by `velocity_writes()`, and an
  MRT resolve of colour and motion. `sceneVelocity` plus `scene3d_velocity` mirror, `SCENE3D_SHUTTER_SECONDS` (1/120 s)
  and `scene3d_shutter_progress`. Exploding Tiles: `tileAtTime` and the slabs write motion; Motion Blur on its page.
  Motion Blur Off is pixel-identical to before (54 frames, all tiers). Cost at 1440p (RTX 4090): +0.08 ms GPU at 4x,
  ~+0.25 ms CPU submit, ~105 MB VRAM per display at 4x during a run.
- **Findings:** the one-pass 24x24 tile max cost 0.118 ms (separable: 0.019, identical). Full-tap white-noise jitter
  speckled the blur's edges, so it is a quarter tap with 16 taps.
- [x] **S7b** The other 3D transitions write their motion (Glass Shatter shards, Crumble chunks and debris,
  Directional Pixel Accretion tiles, 3D Block Spins' slab) and get the Motion Blur choice. Rather than hand-editing
  four shaders, `scene3d_motion_vertex` / `scene3d_motion_fragment` derive a motion variant from each effect's own
  sources: the vertex `main` becomes a function of the run's time input and runs at t - shutter and at t (so the
  Crumble motion table is sampled at both times for free), and the fragment adds the motion output.
  `motion.motion_program` picks the variant, so Off draws the original program: 105 frames pixel-identical to HEAD.
  Cost at 1440p (4x): +0.12-0.28 ms GPU per frame, most for Block Spins, whose moving slab fills the screen (gather
  0.087 ms). Tap counts adapted to the blur length saved 0.04 ms but stippled fast blurs, so the gather keeps 16.
- **Reward:** fast debris reads as fast; smoother motion at any refresh rate.
- **Risks:** multisampled velocity resolve; blur crossing depth edges (bleeding).
- **Hazards:** memory of another attachment; sample count (bounded, 8–12); must be zero at rest and at endpoints.
- **Bars:** endpoints exact; a still scene is unchanged; cost measured.

### S8 — Shared building blocks — LANDED
- [x] Particles: the Exploding Tiles spark emitter becomes library functions plus a shared instanced pass (emit, drag,
  gravity, life, streak or soft sprite, additive); Tiles consumes it with identical pixels. **Landed:**
  `sceneParticleAt` / `sceneParticleStreak` (a streak with no trail is a soft sprite) with CPU mirrors, and
  `rendering/quick/scene3d/particles.py` (`draw_particles`: additive, depth untouched, alpha accumulated for the
  bloom; `particle_budget` by tier). Each effect keeps its own emitter (birth, heading, speed, life, colour). Tiles
  is pixel-identical: 189 frames, every tier, three directions, with and without bloom, motion blur and 4x.
- [x] Planar soft shadows: the Tiles shadow pass becomes a shared pass for any instanced rigid piece; Tiles identical.
  Glass/Crumble shadows are a look change and wait for the operator. **Landed:** `ScenePiece` / `scenePiecePoint`
  (a unit box scaled per axis, turned by a tilt and then a spin) and `scenePieceShadow` (face grown by thickness
  and a height-dependent penumbra, cast along the key light; returns clip, uv, soft-rect inputs and the on-screen
  and height fades) with CPU mirrors, plus `rendering/quick/scene3d/shadows.py` (`draw_planar_shadows`, MIN
  blended). Tiles builds its piece with `tilePiece` and keeps its own strength and end fade: 189 frames
  pixel-identical to HEAD.
- [x] Bendable grid surface: a static subdivided grid (density by tier) and a displacement-hook convention for Page
  Curl, Accordion, Relief Rise, Spectrum Terrain, Shockwave Grid and Waveform Ribbon; unit-tested now, first real
  consumer with the first of those. **Landed:** the tier's `grid_cells` along the photograph's longer side (High
  192, Balanced 128, Performance 64) and `scene3d_grid_size` (square cells, either orientation), plus
  `scene3d_grid_vertices`, a closed, consistently wound triangle list built once per size (~5 ms at 192x108, then
  cached). `scene3d_grid_vertex_source` wraps an effect's `vec3 sceneDisplace(vec2 uv)` into the vertex shader,
  with normals from central differences of the displacement and `scenePlanePoint` for the rest pose.
  `rendering/quick/scene3d/grid.py` has `draw_grid`. Tests: topology (one winding, exact coverage, closed with only
  the outline open), density by tier and aspect, a flat grid draws the photograph within one level, and normals
  face the viewer at rest and follow a bend (a flipped normal fails).
- **Reward:** the next transitions and 3D modes start from working parts.
- **Risks:** refactors must not change Tiles' pixels.
- **Hazards:** grid density is the main cost lever (tier-controlled); particle counts scale with the tier.
- **Bars:** Tiles pixel-identical per tier; grid topology and displacement tests.

### S9 — Photo reflections
- [ ] Per run, copy the source and destination into small renderer-owned mipmapped textures (never the shared
  presentation textures: PR-04 lends the destination to the native branch); a library function samples them as a
  blurred planar environment by roughness. Opt-in per effect; adopting it in Tiles or Glass is a look decision.
- **Reward:** glossy pieces reflect the picture's colours.
- **Hazards:** touching lent textures (forbidden); the copy is once per run (~0.1 ms), never per frame.
- **Bars:** shared textures unchanged (no mip levels added); endpoints exact.

### S10 — Cheaper High (conditional)
- [x] **Landed early (2026-09-29, from the 3D Block Spins before/after check):** the target's `glBlitFramebuffer`
  resolve cost ~0.5 ms at 1440p on drawn content, 1 or 4 samples alike. The colour attachment is now a texture
  (multisampled when anti-aliased) that the composite averages itself; bloom resolves the allocation in one shader
  pass first. GPU median per frame at 2560x1440, RTX 4090, blit -> shader: 3D Block Spins 4x 0.310 -> 0.120 ms,
  Exploding Tiles 4x 0.227 -> 0.071 ms, 4x with bloom 0.538 -> 0.129 ms, bloom without anti-aliasing 0.579 ->
  0.102 ms, Glass Shatter 4x 0.232 -> 0.078 ms. Output matches the blit within one level for multisampled targets;
  a single-sample target now reproduces a direct draw exactly (the old 1-sample renderbuffer did not).
- [ ] Anything further only if physical testing shows High's cost matters: 2x samples, multisampling only the mesh
  pass, or a measured alternative. Decide from `--perf` evidence on the installed build.

### S11 — First-frame program compile (conditional)
- [ ] The first run of a 3D transition compiles its programs on the render thread (80–150 ms for Exploding Tiles).
  If the frame trace shows that hitch on the installed build, warm programs off the first frame (for example on
  enable) without adding a timer or a worker; otherwise record the measurement and close.

## Cross-cutting performance hazards

Binding lessons from the landed slices (measuring, rendering, motion, settings) live in
`Docs/Reference/Transitions.md` ("3D foundation lessons"); every slice adds what it learned there.


- Render-thread Python GL calls hold the GIL (R-87 freshness, Visualizer hitch evidence): count calls per frame and
  measure CPU submit for every slice that adds a pass.
- No allocation, compile or texture copy per frame; per run or per size bucket only.
- Memory: the High target is per display and held only during a run (transitions) or while a mode is active
  (Visualizers); every new attachment is measured and justified.
- State: every GL state the foundation touches is fence-restored (framebuffers, blend, uniform-buffer binding).
- Endpoints: every post effect is exactly zero at progress 0 and 1 and at the near-endpoint checks.
- Time: real seconds only for real-time rates; Visualizers only logical time.
- R-63: nothing may expose uncovered frame edges.

## Physical acceptance (after the slices land)

- High / Balanced / Performance on both displays with active Visualizers: freshness and frame-spacing tails;
  first-use hitch of each 3D transition.
- Looks of migrated transitions (S5) and bloom/motion blur (S6–S7) on real photos.

## Landed / remaining

- Landed: S1, S2, S3, S4, S5, S6, S7 (with S7b), S8.
- Remaining: S9 (opt-in photo reflections), then S10 and S11 (both conditional on physical evidence).
