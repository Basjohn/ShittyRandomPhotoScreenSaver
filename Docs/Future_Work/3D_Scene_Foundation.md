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
| Blend scopes, multisampled `SceneTarget` | `rendering/quick/transitions/scene3d_support.py` | Exploding Tiles | same |
| Programs/meshes/underlay/depth clear (`MeshResources`) | `rendering/quick/transitions/mesh_support.py` | Glass, Crumble, Tiles, Accretion, Ink, Melt | transition GL suites |
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

### S1 — GLSL self-test harness (regression net first)
- [ ] Test-only helper that runs library functions on the GPU for a table of inputs (float render target, readback)
  and compares them with the CPU mirrors: impulse, departure travel, projection, cast-on-plane, rotation, hash
  determinism and uniformity. Never imported by production.
- **Reward:** the library can grow (S3–S9) without mirrors and shaders drifting apart; catches GPU precision faults.
- **Risks:** float32 vs Python doubles need explicit tolerances; RGBA32F targets are required (GL 4.1 has them).
- **Hazards:** none in production.
- **Bars:** every function within tolerance; a deliberately perturbed mirror fails (negative control).

### S2 — Shared home and the Visualizer option (sharability, done early)
- [ ] Move the GL helpers (`MeshResources`, `SceneTarget`, blend scopes) into a neutral package
  `rendering/quick/scene3d/`; update the transition importers; no compatibility shim.
- [ ] `SceneTarget` covers any pixel rect of the render target (offset viewport inside the target, composite by
  `gl_FragCoord - rect`), with size buckets (round up to 64 px) so a CUSTOM resize drag does not reallocate per frame;
  the inherited scissor is suspended inside the target and restored for the composite.
- [ ] Visualizer fence restores draw/read framebuffer bindings (it already restores blend).
- [ ] Document the Visualizer opt-in: include `SCENE3D_GLSL`, logical time only, target sized to the card rect and
  composited inside the clip host's begin/end, target released on mode retirement, tier setting with the first
  consumer. No Visualizer mode changes.
- **Reward:** the foundation stays one owner as it grows; Visualizers can adopt it without a second copy.
- **Risks:** import churn across seven transition modules (pure move, caught by the suites); a sub-rect target must
  reproduce a direct draw exactly (clip and scissor coordinates).
- **Hazards:** reallocation thrash during resize (bucketed); a target sized to the whole window for a small card
  (rect-sized now); a card composite outside the clip (composite inside the clip host's begin/end).
- **Bars:** sub-rect target equals a direct draw (single-sample flat scene, exact pixels); shrinking inside a bucket
  does not reallocate; Visualizer fence restores framebuffers (fake-GL fence test with a negative control); all
  transition suites green.

### S3 — Per-frame uniform blocks
- [ ] One std140 uniform block per effect frame, laid out from a single Python field list (shared packing helper),
  updated with one buffer write per frame and bound for every pass; Exploding Tiles first.
- **Reward:** ~40 GL calls per frame to a handful; the render-thread CPU cost Visualizers need to afford 3D.
- **Risks:** std140 alignment (vec3 padding) — verified on the GPU through S1; binding-point collisions with Qt's RHI,
  which also uses uniform buffers.
- **Hazards:** GPU sync stalls from rewriting a buffer in flight (orphan with `glBufferData(NULL)` or a small ring);
  leaking the uniform-buffer binding (the fences capture and restore the indexed binding the foundation uses).
- **Bars:** identical pixels before/after for Exploding Tiles at every tier; CPU submit measured lower; fence test
  covers the uniform-buffer binding.

### S4 — Camera
- [ ] `sceneProject` takes a camera (distance per effect, plus offset, tilt and shake) from the frame block; at rest it
  maps z = 0 exactly onto the item (photo fills the view).
- **Reward:** existing effects keep their authored distance (Glass/Accretion 3.0, Tiles 3.4); enables camera shake,
  Cube Turn's pull-back, Page Curl/Relief Rise tilt, Visualizer parallax.
- **Risks:** any camera motion moves the photograph plane too.
- **Hazards:** exposing the frame edges (R-63: black = 0) — a moving camera must overscan (zoom in by at least the
  shake/tilt amplitude) or move only the pieces; shake at real-time rates; camera at rest at both endpoints.
- **Bars:** at rest, projection mirrors match S1 and endpoints stay exact; a shaken camera never shows uncovered
  pixels at any aspect (edge-pixel test).

### S5 — Existing 3D transitions onto the library and 3D Detail
- [ ] Glass Shatter: shared camera at 3.0 and near-plane depth, `SceneTarget` on High, park lifecycle.
- [ ] Directional Pixel Accretion: shared camera at 3.0, integer hash, `SceneTarget` on High.
- [ ] Crumble: integer hash for its noise, `SceneTarget` on High.
- [ ] 3D Block Spins: stays orthographic by design; `SceneTarget` on High only.
- [ ] Exit guarantees: each effect already has its authored departure (Glass ray-exit, Crumble fall, Accretion is an
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

### S6 — Bloom (then HDR, decided on measurement)
- [ ] High only: a bright-pass and downsample/upsample chain (1/2 to 1/16) over the resolved target, added back in the
  composite. Glow comes only from **emissive** content, which effects write into the target's alpha (the photograph
  writes 0), so the pictures themselves never bloom and endpoints stay exact.
- [ ] HDR (RGBA16F target + tone map) only if measurements justify doubling the colour memory (~118 MB more per display
  at 1440p with 4x samples).
- **Reward:** real glow on sparks, embers, hot cracks, glints and highlights.
- **Risks:** bloom leaking from bright photo areas (prevented by the emissive mask); a changed composite on High.
- **Hazards:** extra full-screen passes (downsampled chain, ~0.2–0.4 ms target); per-run allocation only; no
  allocation per frame.
- **Bars:** endpoints exact on High; a photo with a bright sky does not glow at 0.0001; bloom measured and parked.

### S7 — Analytic motion blur
- [ ] High only. Every piece's motion is analytic, so its screen velocity comes from evaluating it at `t` and
  `t - shutter` (shutter in real seconds); a bounded-sample blur along velocity. Choose between a velocity attachment
  and geometric stretching after S6's measurements.
- **Reward:** fast debris reads as fast; smoother motion at any refresh rate.
- **Risks:** multisampled velocity resolve; blur crossing depth edges (bleeding).
- **Hazards:** memory of another attachment; sample count (bounded, 8–12); must be zero at rest and at endpoints.
- **Bars:** endpoints exact; a still scene is unchanged; cost measured.

### S8 — Shared building blocks
- [ ] Particles: the Exploding Tiles spark emitter becomes library functions plus a shared instanced pass (emit, drag,
  gravity, life, streak or soft sprite, additive); Tiles consumes it with identical pixels.
- [ ] Planar soft shadows: the Tiles shadow pass becomes a shared pass for any instanced rigid piece; Tiles identical.
  Glass/Crumble shadows are a look change and wait for the operator.
- [ ] Bendable grid surface: a static subdivided grid (density by tier) and a displacement-hook convention for Page
  Curl, Accordion, Relief Rise, Spectrum Terrain, Shockwave Grid and Waveform Ribbon; unit-tested now, first real
  consumer with the first of those.
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
- [ ] Only if physical testing shows High's cost matters: 2x samples, multisampling only the mesh pass, or a
  measured alternative. Decide from `--perf` evidence on the installed build.

### S11 — First-frame program compile (conditional)
- [ ] The first run of a 3D transition compiles its programs on the render thread (80–150 ms for Exploding Tiles).
  If the frame trace shows that hitch on the installed build, warm programs off the first frame (for example on
  enable) without adding a timer or a worker; otherwise record the measurement and close.

## Cross-cutting performance hazards

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

- Landed: nothing yet (rollback HEAD above).
- Remaining: S1–S11 in order.
