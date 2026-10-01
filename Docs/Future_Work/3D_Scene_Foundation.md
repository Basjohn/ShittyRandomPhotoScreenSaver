# 3D Scene Foundation — decomposition (live checklist)

Promoted by the operator on 2026-09-29 ("I agree with all of these … safer sooner … go ahead") and expanded on
2026-09-30 into a deliberate **PySide 6.11.2 + OpenGL 4.6 + modern GPU foundation** program, including normalisation
of Voxel Sphere onto the shared 3D substrate and active lightning/particle/smoke work. `Current_Plan.md` owns the
order; this file owns the technical decomposition. Delete it when the program closes, leaving durable contracts in
`Docs/Reference/Transitions.md`, `Docs/Reference/Visualizer_Reference.md` and `Docs/Reference/Sphere_Visualizer.md`.

**Rollback / comparison HEAD:** `3185645a` (Exploding Tiles on the first foundation, accepted and closed).

## Goal

One shared, high-fidelity 3D GPU substrate whose meaningful cost is zero when no consumer uses it. Every 3D transition
and 3D Visualizer may reuse it; effects keep their own authored motion, reaction, look and state. The 2026-09-30 program
raises the production floor directly to OpenGL 4.6, then adds DSA, immutable/persistent storage, SSBOs, compute/image
load-store/atomics, indirect draws and richer active-only scene targets before building vertical high-fidelity effects.
Voxel Sphere is promoted onto this substrate without genericising or retuning its behavioural model.

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
- **Sphere:** its behavioural golden remains private and binding, but the 2026-09-30 operator direction explicitly
  activates promotion onto the shared low-level scene3d substrate. Share resource/material/post/compute plumbing; never
  use Sphere as a base class and never rewrite its reaction/cohort/Settings semantics merely to fit shared helpers.

## Slices, in order

Each slice: reward, risks, performance hazards to avoid, acceptance bars. Commit and push per slice.

### S1 — GLSL self-test harness (regression net first) — LANDED
- [x] Test-only helper that runs library functions on the GPU for a table of inputs (float render target, readback)
  and compares them with the CPU mirrors: impulse, departure travel, projection, cast-on-plane, rotation, hash
  determinism and uniformity. Never imported by production.
- **Reward:** the library can grow (S3–S9) without mirrors and shaders drifting apart; catches GPU precision faults.
- **Risks:** float32 vs Python doubles need explicit tolerances; RGBA32F targets are required and available in the 4.6 Core baseline.
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
  MRT resolve of colour and motion. `sceneVelocity` plus `scene3d_velocity` mirror, `SCENE3D_SHUTTER_SECONDS` (1/120 s at first; 1/60 s since the operator found it weak)
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

### S9 — Photo reflections — LANDED
- [x] Per run, copy the source and destination into small renderer-owned mipmapped textures (never the shared
  presentation textures: PR-04 lends the destination to the native branch); a library function samples them as a
  blurred planar environment by roughness. Opt-in per effect; adopting it in Tiles or Glass is a look decision.
  **Landed:** `PhotoEnvironment` (a 512 px box-filtered copy with its own mipmaps, once per run and role; 4K photo
  ~0.07 ms GPU / ~0.2 ms CPU; dropped at park), plus `sceneEnvironment` (roughness 0 sharp, 1 at mip 7),
  `sceneReflectionUv` (the photo as a mirror ball, by the reflected ray) and `sceneEnvironmentLight`
  (Fresnel-weighted). The operator chose adoption (2026-09-29) where it improves on the existing look: Block Spins
  Edge Glass (which also fixes dark, flat early diagonal spins), Glass Shatter's Fresnel reflection and released
  Exploding Tiles. Bars: lent textures untouched (pixels, no mip level), one copy per run, roughness blurs, edge
  reflections alike in both halves of every spin (a screen-position lookup fails all four directions), the Tiles
  wall exact until release, and Glass reflection-free at sheen zero.
- **Reward:** glossy pieces reflect the picture's colours.
- **Hazards:** touching lent textures (forbidden); the copy is once per run (~0.1 ms), never per frame.
- **Bars:** shared textures unchanged (no mip levels added); endpoints exact.

### S10 — Cheaper High
- [x] **Landed early (2026-09-29, from the 3D Block Spins before/after check):** the target's `glBlitFramebuffer`
  resolve cost ~0.5 ms at 1440p on drawn content, 1 or 4 samples alike. The colour attachment is now a texture
  (multisampled when anti-aliased) that the composite averages itself; bloom resolves the allocation in one shader
  pass first. GPU median per frame at 2560x1440, RTX 4090, blit -> shader: 3D Block Spins 4x 0.310 -> 0.120 ms,
  Exploding Tiles 4x 0.227 -> 0.071 ms, 4x with bloom 0.538 -> 0.129 ms, bloom without anti-aliasing 0.579 ->
  0.102 ms, Glass Shatter 4x 0.232 -> 0.078 ms. Output matches the blit within one level for multisampled targets;
  a single-sample target now reproduces a direct draw exactly (the old 1-sample renderbuffer did not).
- [x] **Per-run textures allocated ahead (2026-09-29, operator-chosen over holding them between runs).** The
  two-display `--perf` run showed one 10-29 ms render-thread frame at the start of every 3D run on each display:
  the driver allocating the run's multisampled target, motion, resolve, bloom and trails textures at its first
  frame. The S11 warm-up now allocates them ahead, one unit per spaced step, at the render size the node's last
  render saw (else the largest its logical size can round from): `SceneTarget.warm`, `MotionBlur.warm`,
  `BloomChain.warm`, `MotionTrails.warm`, which the run's first use shares. `park()` still releases everything
  after each run, so only the *next* transition's textures are ever held, and only from its warm-up to its end.
  - **Measured** (offscreen, 3840x2160, operator settings, programs warm; start frame = worst of the first three):
    Block Spins 9.1-9.5 -> 2.5-3.8 ms, Exploding Tiles 11.1-11.9 -> 3.0-4.0, Glass Shatter 8.6-10.5 -> 3.0-3.5,
    Crumble 12.2-12.7 -> 2.2-2.8, Pixel Accretion 10.8-11.0 -> 1.1-1.5. A warm step costs 0.2-2.7 ms of render-
    thread CPU (the GPU side of zeroing a 4K multisampled target, up to ~6 ms, overlaps other frames).
  - **Memory** (driver-reported, 4K + 1440p displays, operator settings): Block Spins 289 + 136 MB, Exploding
    Tiles 312 + 146, Glass Shatter 264 + 119, Crumble 488 + 222, Pixel Accretion 480 + 219. Peak use is unchanged
    (each run allocated the same); it is now also held while that transition is next.

### S11 — Gradual warm-up of the next transition
- [x] **Landed (2026-09-29, operator: "a no-brainer" if it prevents a hitch).** Before, the first run of a 3D
  transition in a session compiled its programs, imported its renderer module and built its fracture geometry on
  the render thread at its first frame; an image change resolves its transition only ~14 ms before that frame
  (`[PERF][IMAGE_CHANGE]`, prefetched image), too late to prepare anything.
  - **When:** as soon as the displays go idle (the last display's transition completed, or the startup reveal
    completed), the engine reserves the next Random pick (`RandomTransitionHistory.reserve`, taken by the next
    rotation while it stays in the pool, so the distribution and no-repeat rule are unchanged) and
    `DisplayManager.prepare_next_transition` resolves its spec from a batch seed kept for the next batch. The
    batch resolves the identical spec unless Settings changed meanwhile.
  - **What:** its run geometry is built on COMPUTE (existing `prepare_run_geometry`), its renderer module is
    imported on the GUI thread, and every display compiles its programs gradually: one program per step, steps at
    least 0.2 s apart, run on `beforeRendering` of frames the window renders anyway (bracketed by
    `begin/endExternalCommands`). Each renderer lists its programs in `warm(parameters)`; the background node's
    own quad program is the first step.
  - **Never:** at startup, in bursts, on a timer, on a thread, by polling, or by forcing frames. A window that
    renders nothing warms nothing, and a run always prepares whatever is left itself. The driver's parallel
    compile (`KHR_parallel_shader_compile`) was tried and removed: it adds driver threads and needs polling.
  - **Measured** (hidden `QQuickRenderControl` scene, real `BackgroundRenderItem`, 1280x720, RTX 4090, warm
    driver shader cache, first two run frames together, with `glFinish`): cold -> warmed Glass Shatter 63-88 ->
    12-17 ms, Exploding Tiles 36-44 -> 8-30 ms, Crumble 40-51 -> 12-20 ms, Pixel Accretion 28 -> 10 ms. Warmed
    runs compile nothing. What remained was per-run work: the destination upload, the environment copy and the
    scene textures (now allocated ahead, S10).

### S12 — Runtime floor: PySide 6.11.2 + OpenGL 4.6 Core
Implemented and regression-validated. `Spec.md` → Accepted runtime presentation owns the strict 4.6 Core / GLSL 460
contract and actual-context rejection. Maintained diagnostics and shared scene3d fixtures use the same floor.
Ordinary-use physical validation and operator builds remain non-blocking checklists in `Current_Plan.md`.

### S13 — DSA, immutable storage and multi-bind
Migrate the existing context-local owners in three reviewable slices. Allocation-time DSA is not automatically a
steady-frame speedup: identify removed calls and measure the actual consumer before claiming a performance gain.

#### S13a — Shared static meshes and source/destination texture binding
- [x] In `scene3d/resources.py`, allocate static mesh VAOs/VBOs with named DSA setup and immutable buffer storage.
  The existing mesh record retains handle ownership, partial-failure cleanup and retry; introduce no parallel pool.
- [x] Replace repeated source/destination texture-unit selection and binds with one multi-bind operation. Assign
  sampler units once per linked program through its existing program/uniform cache; texture IDs still bind every draw.
  No texture-state cache may assume Qt left a binding intact. Zero texture IDs must preserve inherited target semantics.
- [x] Admit every newly called GL entry point through the current-context bootstrap gate. No import-time probing,
  extension fallback or repeated capability query in render frames.
- [x] Prove real mesh pixels, unchanged generic VAO/array-buffer bindings during construction, immutable storage,
  exact sampler routing and untouched active/unrelated texture units. Retain allocation-failure/release-retry tests.
- [x] Compare all five affected 3D transitions before/after, warm first frames, parked resources and outer state fence.
  Measure warm submission calls and time separately from one-time mesh construction.

Durable contracts and the measured submission scope: `Docs/Reference/Scene3D_Resources.md`.

#### S13b — PhotoEnvironment texture and framebuffer construction
- [ ] In `scene3d/environment.py`, allocate the known-size environment texture with immutable storage for its complete
  mip chain. Use named texture parameters/mipmap generation and named framebuffer attachment/status operations.
- [ ] Keep the existing destination-photo copy owner, one copy per run, sampler look and `park()` retirement.
  Raster work still binds its drawing framebuffer and restores inherited framebuffer, viewport and scissor state.
- [ ] Prove reflection pixels, mip levels, lent-photo immutability, allocation reuse, failure cleanup and park retirement.
  Record construction-call savings; do not advertise an unmeasured steady-frame benefit.

#### S13c — Fixed-size scene and post-process allocations
- [ ] Migrate `scene3d/target.py`, `post.py` and `motion.py` separately behind their current real-pixel tests: immutable
  textures and named framebuffer construction only where allocation size/sample count is already fixed.
- [ ] Preserve attachment formats, sample counts, size buckets, bloom/velocity writes, exact endpoints and dormant cost.
  Retain draw-time state restoration; only remove queries made unnecessary by named construction operations.
- [ ] For each owner, prove repeated size reuse, explicit resize retirement, exception restoration, disabled-feature
  resource absence and unchanged rendered pixels before proceeding to the next owner.

Changing UBO streams remain under S14: `UniformBlock.bound()` deliberately orphans mutable storage, so immutable
storage is not a drop-in replacement. Multi-buffer binding is deferred until a real consumer uses multiple points.
Effect-private dynamic/instanced buffers require their own measured migration; static shared meshes do not authorise
changing their update policy. DSA never removes Qt's inherited-state contract or creates another render owner.

### S14 — Persistent mapped stream + SSBO foundation
- [ ] Add one bounded context-local persistent/coherent (or explicitly flushed) mapped ring for small changing frame
  payloads. Fence/reuse segments safely; no map/unmap/allocation per frame and no busy polling.
- [ ] Add schema-owned SSBO helpers for structured instance, event, history, material and compact work data. Reflection/
  layout tests compare Python packing with driver-reported/std430 layout where applicable.
- [ ] Migrate only data that benefits: large structured arrays, many instances/events or data shared across passes.
  Tiny fixed frame values may remain uniforms/UBOs if cheaper.
- **Reward:** removes texture-table contortions and repeated Python uniform calls, enables compute/indirect consumers.
- **Hazards:** overwrite-in-flight stalls, alignment/stride drift, runaway capacities. Rings/capacities are fixed/bounded.
- **Bars:** no GPU sync stall in steady traces, exact retirement, no per-frame allocation, CPU submit before/after.

### S15 — Compute, image load/store and atomic primitives
- [ ] Shared compute program/resource helpers with explicit dispatch dimensions, barriers and deterministic GPU test
  harnesses. Add image load/store and atomic/atomic-counter wrappers only as concrete consumers need them.
- [ ] Compute may prepare/compact/evaluate GPU work but may **not** become a second simulation clock. Transition compute
  derives from run progress/real authored seconds. Visualizer compute consumes logical revision/time and bounded snapshot
  history; repeated renders of one logical revision cannot advance state again.
- [ ] Useful first jobs: particle evaluation/compaction, procedural bolt/branch tables, volume injection/advection,
  post-processing kernels, light/cluster lists, active-piece masks and GPU-generated indirect counts.
- **Reward:** moves genuinely parallel work away from Python without introducing render-rate semantics.
- **Hazards:** missing barriers, hidden persistent state, dispatch overprovisioning, readback. No ordinary CPU readbacks.
- **Bars:** CPU mirror/negative controls where feasible, logical-revision replay determinism, measured dispatch/GPU cost.

### S16 — Indirect/multi-draw and GPU compaction
- [ ] Allow compute/CPU-once prepared work to produce bounded indirect draw commands and compacted active-instance lists.
  Use `glMultiDraw*Indirect` only when it replaces material Python submit/draw loops.
- [ ] Stable instance IDs/seeds survive compaction so authored randomness does not shimmer when population changes.
- [ ] No CPU readback of the generated count in the ordinary path; the GPU consumes its own bounded command buffer.
- **Reward:** thousands of active particles/pieces can remain one/few Python submissions.
- **Bars:** same deterministic population/placement as reference; no overrun beyond allocated command/instance capacity.

### S17 — Active-only high-fidelity scene buffers, lighting and materials
- [ ] Extend `SceneTarget` with opt-in RGBA16F HDR and optional normal/material/depth/history attachments. Allocation key
  includes only requested capabilities; ordinary/cheap effects keep the existing minimal target or direct draw.
- [ ] Shared material/light block: energy-conserving GGX/Cook-Torrance BRDF, roughness, metalness/specular, emissive,
  bounded directional/point/spot lights, BRDF LUT and photo/environment image-based lighting.
- [ ] Shared real 3D shadow option: depth map(s), bounded PCF/PCSS-style softness/contact treatment. Keep planar shadows
  where they are both cheaper and visually appropriate. Optional GTAO/contact AO is active-only.
- [ ] Shared transparent path: depth-aware soft particles and weighted blended OIT for smoke/spark/glass-heavy consumers.
- [ ] Shared glass path: thickness/depth-aware screen-space refraction, Fresnel reflection, rough transmission and
  restrained optional dispersion, using owned scene/environment textures rather than mutating lent presentation images.
- **Reward:** coherent high-end materials/light interaction rather than bespoke approximations per effect.
- **Hazards:** full-screen attachment bandwidth/memory. Every attachment/pass has an explicit requesting feature/tier.
- **Bars:** disabled/cheap path allocates none of the new buffers; exact endpoints and existing looks stay untouched.

### S18 — GPU particles, lightning, smoke/fire and volumetrics
- [ ] **Particles:** bounded SSBO pool, deterministic seeded spawn, compute evaluation/compaction, indirect instanced draw,
  soft sprites/streaks/ribbons, optional simple analytic/SDF collision, depth fade and OIT. No CPU object per particle.
- [ ] **Lightning:** stable seeded branching topology per admitted event, travelling intensity/forks, hot emissive core,
  bloom, secondary arcs, short afterglow and optional local-light injection into geometry/smoke. Never rerandomise the
  entire bolt at render cadence.
- [ ] **Smoke/fog/fire:** active-only half/quarter-resolution density/temperature volume or procedural field; bounded curl
  noise/advection/vorticity, event injection, depth-aware raymarch, temporal reprojection, absorption/scattering and
  emissive fire/embers. Quality tiers own volume resolution, ray steps and light samples.
- [ ] **Energy/field effects:** compute/image-driven shockwaves, plasma/nebula, reaction-diffusion surfaces, heat haze and
  force fields with deterministic event/history input.
- **Reward:** the foundation starts producing effects that were awkward or CPU-hostile on the old 4.1-era architecture.
- **Hazards:** volume memory, temporal ghosting, accidental render-rate simulation. Dormant means no allocation/dispatch.
- **Bars:** fixed logical replay gives fixed frames, resource retirement to zero, frame/GPU budget measured by tier.

### S19 — Voxel Sphere promotion onto scene3d
- [ ] Run the existing Sphere promotion golden **before** refactoring: Glass Current + Voxel Bloom persisted snapshots,
  hidden technical profile, deterministic FeatureFrame replay (silence/flat/vocal/kick/sustained), logical outputs,
  representative captures and extreme CUSTOM geometry.
- [ ] Preserve Sphere's descriptor, `sphere_*` state, Settings/presets, logical runtime, section drives, tracer/cohort
  semantics, authored projection and reactivity. Sphere is not a generic 3D base class.
- [ ] Replace only duplicate low-level GPU plumbing with scene3d equivalents: resource lifetime/fences, frame/target,
  DSA buffers, SSBO/instance transport, shared material/light/post pieces and particle/shadow helpers when parity proves
  they are mathematically/visually identical.
- [ ] Sphere becomes an ordinary shared-foundation 3D Visualizer consumer with the standard 3D capability/tier lifecycle.
  Non-selected Sphere remains dormant. After parity, delete superseded Sphere-local low-level infrastructure.
- [ ] New fidelity options (HDR emissive lighting, better shadow interaction, compute particles, smoke/electric coupling)
  come **after** the migration golden and are explicit look changes, never smuggled into the refactor.
- **Bars:** promotion gate in `Docs/Reference/Sphere_Visualizer.md`; zero material change without operator approval.

### S20 — Vertical consumers: make the foundation earn its complexity
- [ ] Page Curl and Blinds → 3D Slats: adaptive surface/material/shadow proofs.
- [ ] Extruded Spectrum: first ordinary 3D Visualizer, SSBO instancing + common material/light proof.
- [ ] Shockwave Grid: displaced grid + bounded event SSBO + emissive/HDR/bloom proof.
- [ ] Reactive Particle Field: compute/compaction/indirect/OIT proof.
- [ ] Spectrum Terrain/Skyline/Tunnel, Waveform Ribbon, Deformable Blob Sphere, Accordion Fold, Relief Rise, Cube Turn.
- [ ] Bubble Depth Field only under Bubble Temporal Fidelity/R-69; depth cannot damp or retime authored response.
- [ ] Once primitives are individually accepted, combine them deliberately: electrical storm terrain, smoke-lit voxel
  fracture, ember/dust destruction, refractive glass lit by bolts, volumetric shockwaves and photo-colour IBL.
- **Rule:** a vertical feature may request foundation extraction, but speculative generic engine layers remain forbidden.

## Cross-cutting performance hazards

Binding lessons from the landed slices (measuring, rendering, motion, settings) live in
`Docs/Reference/Transitions.md` ("3D foundation lessons"); every slice adds what it learned there.


- Render-thread Python GL calls hold the GIL (R-87 freshness, Visualizer hitch evidence): count calls per frame and
  measure CPU submit for every slice that adds a pass.
- No allocation, compile or texture copy per frame; per run or per size bucket only.
- Memory: a transition's scene textures are per display and held from its warm-up (it is the next transition)
  until `park()` after its run; a Visualizer mode's while it is active. Never hold textures for transitions that
  are not next. Every new attachment is measured and justified.
- State: every GL state the foundation touches is fence-restored (framebuffers, blend, uniform-buffer binding).
- Endpoints: every post effect is exactly zero at progress 0 and 1 and at the near-endpoint checks.
- Time: real seconds only for real-time rates; Visualizers only logical time.
- R-63: nothing may expose uncovered frame edges.

## Physical acceptance (after material slices)

- High / Balanced / Performance on both displays with active Visualizers: freshness/frame-spacing tails, first-use and
  warm-run cost, parked memory and transition-end behaviour.
- New lighting/material/particle/volume features on real photos and representative music, including extreme CUSTOM card
  shapes for Visualizers. Disabled features must be visually and materially cost-neutral.
- Voxel Sphere migration gets a dedicated before/after golden pass before any new Sphere look option is judged.

## Landed / remaining

- Landed: S1–S12, Motion Trails with per-variant invariant setup, and the high-fidelity shared foundation above.
- Remaining/active: S13–S20 under the 2026-09-30 operator promotion.
