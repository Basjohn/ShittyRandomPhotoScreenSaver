# Rendering primitives and shared services (catalogue)

Written 12 Nov 2026 from `Current_Plan.md` item 8b (cited below by item and box name, never by line), the decisions
document `Docs/Future_Work/Native_Core_P3_Decisions.md` ("Decisions"), `Docs/Reference/Scene3D_Resources.md`
("Resources"), `Docs/Reference/Transitions.md` ("Lessons" = its section "3D foundation lessons", line 149) and the
code. Anything not checked against code or a document is marked **unverified**. This file is the catalogue and the
"what is it for, who uses it, what must you know" view; `Scene3D_Resources.md` keeps the resource-level detail
(allocation sizes, state restoration, measured figures) and is not repeated here. Existing operator-authored preset identities/values are not catalogued here; the six planned **new demonstration names** below are unpinned artistic intents, not file names, slot contracts or test inputs. The rules a native port obeys, and the traps and proof of each native primitive, are in `Docs/Guides/Native_Port_Playbook.md`; this file stays the catalogue.

## 1. What counts as a primitive, and the rules that bind them

A **primitive** here is a reusable GPU building block or service that has its own proof harness (an off-screen scene,
a test with a CPU mirror, or a lab) and that more than one mode or transition can take, or could. A **mode's own
code** is what a single Visualizer mode or transition draws with its own shaders and state: its program sources
(`rendering/gl_programs/<mode>_program.py`), its renderer (`rendering/quick/visualizer/implementations/`,
`rendering/quick/transitions/implementations/`) and anything in `scene3d/` that only one mode imports. The
borderline cases are listed in section 3, entry E26.

Rules (all from item 8b's "Standing rules of this item"):

1. **Proved on its own off-screen harness** (item 8b, standing rules): GPU time median and p90, lazy creation, no work when
   dormant, clean retirement. A primitive never becomes a second renderer, clock or camera. Read the Lessons before a
   3D slice and append after it.
2. **High potential is built without a consumer; low potential only when a consumer is admitted** (item 8b, standing rules;
   operator, 12 Nov: "High potential primitives should be built regardless, low potential only when a consumer. We
   can always improve."). The lead classifies and writes the class at each item. The class is given below where the
   plan gives it; where it gives none the entry says "no class stated".
3. **No new 3D primitive in the Python OpenGL renderer** unless an open defect needs it; new modes are built on the
   native core only (item 8b, standing rules).
4. **The principal artistic delivery is an optional real visualizer integration, not a mandatory
   standalone showcase WebP** (operator, 23 Nov). The primitive's own independent harness, median/p90 GPU
   cost, validation, resource/dormancy and retirement evidence remain absolute. When an existing accepted
   mode is suitable, integrate the primitive as a separately enabled and meaningfully MUSIC-REACTIVE
   feature with full canonical Studio appearance and response controls, then author a **new mutable
   demonstration preset** through the real Studio save path. All six approved concepts are specified
   in `Current_Plan.md` N4/N6 demonstration box and mapped below. A standalone WebP is optional
   *supplementary human-viewable* evidence; it proves neither music response nor production admission.
   `Docs/Reference/Primitives.md` holds the "what this makes possible" note, with resource details
   in `Docs/Reference/Scene3D_Resources.md`.
   **NEVER TEST AGAINST A PRESET:** no shipped/operator-authored preset may be read, loaded, pinned,
   hashed, compared, snapshot-tested or treated as a schema/parity/artistic oracle in automated tests.
   Use entirely synthetic, test-owned configuration and ephemeral preset-shaped files for schema/IO
   cases. Actual presets are demonstration art with no frozen values, slot numbers or test fixtures.
   This applies equally to brand-new demonstration presets. Port and native Studio flip remain
   independent of all six post-parity artistic integrations.
5. **Dormancy at rest**: nothing allocates before a consumer warms it, nothing costs per frame at rest, everything is
   released at `park()` or retirement (Lessons line 207; `Scene3D_Resources.md` "Fixed-size scene and post-process
   allocations"). Diagnostic instrumentation is opt-in (memory: no recurring work at rest).
6. **A port is done** only with single-sampled pixel parity against the Python renderer, the Vulkan result within a stated tolerance (D12's shared pixel tolerance), trace figures, GPU time per pass and a bounded rehearsal, and then the Python renderer is
   deleted in the same change (item 8b, standing rules, first bullet). Never two permanent renderers.
7. **D5.3's mandatory OpenGL twin is for original existing-mode port parity** (item 8b,
   D5.3's 23 Nov supersession). Additional optional Vulkan-only fidelity features
   may sit on an already accepted mode without cloning the extra effect for OpenGL;
   original mode appearance and its OpenGL fallback stay intact. No such optional
   integration is a blocker for native N5.8 Studio migration or NF.
8. **Ids**: the old `S3D-n` ids map to N-ids as in section 5's table (item 8b, standing rules).

## 2. When primitive work happens

The native ladder (`Current_Plan.md` item 8b, "Order" paragraph): **N0** (decisions, contracts, proofs) and **N1** (every shader
portable, in the existing OpenGL renderer, no C++) now; then **N2** (the 2D half and Spectrum), **N2b** (the
background layer and the first full rehearsal), **N3** (the 3D substrate core, harness scenes, no mode yet). From
there three tracks, one High slot each:

- the **modes track** (N5.1, N5.4, N5.6, N5.5, N5.3; item 8b, the N5.1, N5.4, N5.6, N5.5 and N5.3 boxes);
- the **background track** (N5.2 a to h, N5.9; item 8b, the N5.2 and N5.9 boxes);
- the **primitives track** (N4's unconsumed items and N6) "whenever a High slot is free and never holds the flip"
  (item 8b, "Order" paragraph).

Then **NF** (the flip, item 8b, NF), followed by native-only **Melt Pool then Concrete Rain** (item 9 / §7) and
substantial QoL work. SMP foundations remain deferred in `Future_Work.md` §2.5 until explicit operator readmission.

**N4 items are ported just before their first consumer** (item 8b, the heading above the N4 boxes: "each ported just before its first
consumer below (the unconsumed ones on the primitives track)"). An N4 item whose consumer is on the modes or the
background track therefore moves with that consumer; an unconsumed one (the N4.c, N4.h, N4.m high-potential items,
and N4.d's wet-surface masks) runs on the primitives track. N6 runs only on the primitives track, native only.

Current state and remaining gates are maintained in `Current_Plan.md` item 8b. The native core provides the host, composite, targets, mesh and buffer, compute and post-stage substrate; see `native/core/README.md` for its current services. Spectrum, Spline Curve and Bubble use native routes (Bubble registered and offered on Vulkan since 17 Nov; its live run and long-take proofs remain, item 8b N5.1). N3.4's source audit and native repair proofs are complete; the remaining OpenGL defocus investigation is non-blocking (operator, 16 Nov 2026; D17/R-232). Each consumer proves its own parity, lifecycle and measured cost. `native/spike_p1` is evidence, never a shipped renderer.

Step by step:

| Step | State (see item 8b for live gates) | Primitive relevance |
|---|---|---|
| N0.3 conventions, three scenes | proved 12 Nov on Vulkan, OpenGL, D3D11 and D3D12 (Metal on the Watchlist) | the conventions include is proved on every backend we ship |
| N0.4 camera | decided (D5.5); remainder built with N5.4 then N5.6 (N0.4's remainder box) | one camera owner, see section 7 |
| N0.6 Vulkan device | proved; validation clean apart from Qt 6.12.0 defects A, B, D (N0.6's box) | the device the core runs on |
| N0.7 async jobs | proved; verdict "jobs for compute on this vendor, and uploads" (Decisions line 569-612) | D9 service; AMD and Intel unmeasured (N0.7's box) |
| N1 portable shaders | in flight: D4 landed; N1.6 at ratchet 24 (the 3D modes left); N1.4 include remainder and N1.8 resolve-first open (the N1 boxes) | what makes existing primitives bakeable |
| N2.1 to N2.8 | N2 services and Spectrum built; remaining work and rehearsals in the N2 boxes | host adapter, frame driver, packet reader, composite, timer, rehearsal path |
| N2b: N4.a, N3.8 jobs, N5.7a/b/c | N4.a (D13), N5.7a and N5.7b (D7) built and proved 14 Nov; N3.8 jobs built (section 4); N5.7c leftovers open | fullscreen pass, job service, background layer, backdrop pyramid |
| N3.1 to N3.9 | N3.1 to N3.3 proved (D14 to D16); N3.4 audited/proved, remaining investigation non-blocking (D17); N3.6, N3.7 and N3.9 open; there is no N3.5 in the plan (numbering skips from N3.4 to N3.6) | targets, meshes, compute, post stages, lifetime, orientation, display move |
| N4.b to N4.m | open (the N4 boxes) | ported with first consumer, or on the primitives track |
| N6.1 to N6.6 | open (the N6 boxes) | never built, native only |

## 3. Existing primitives (Python OpenGL renderer today)

Every entry: module; what it does; consumers (grepped imports, 12 Nov; modes and transitions by display name, never
by preset); harness or test; native-ladder id and potential class; notes. All are context-local, lazy, released at
`park()` or retirement, and require the validated OpenGL 4.6 context (`Scene3D_Resources.md:3-5`). Constructing one
costs nothing; the first warm or use allocates.

<a id="e1"></a>
### E1. Scene frame and item quad
`rendering/quick/scene3d/frame.py` (pure, no GL). The frame protocol a render node supplies (viewport, logical size,
Qt's item matrix, unit quad), `item_pixel_rect` and the quarter-turn orientation helpers (`orient_visualizer_scene_frame`,
`scene_output_frame`). The item-quad vertex stage moved to `rendering/gl_programs/item_quad.py` with N1.6 (12 Nov:
`item_quad_vertex_source(block)` and `item_quad_program`, each program declaring the quad's values in its own pass
block; the loose `ITEM_QUAD_VERTEX_SOURCE` and `QUICK_TRANSITION_VERTEX_SOURCE` are gone). Consumers: nearly every
transition and Visualizer scene (`transitions/fullscreen_pass.py`, `visualizer/framed_view.py`, Beam, Blinds, Cube Turn, Disintegrate, Edge
Bloom, Capillary Bloom, Chromatic Shear, Liquid Lens, Oscilloscope, Neon Lake, Extruded Bubble, Extruded Spectrum,
Sphere, Waveform Ribbon, Page Curl, Surface Tension, VHS, Volumetric Dissolve and others). Tests:
`test_scene3d_item_pixel_rect.py`, `test_scene3d_content_orientation.py`. Native: replaced by D5.2's texture-node
composite and N3.7's orientation contract (N3.7's box). Notes: the item quad keeps "the bottom-up convention the
transition fragments were authored in" (`gl_programs/item_quad.py`); the N0.3 rule 2 (core targets top-left, Y down) puts one
flip at the substrate boundary (Decisions line 1353-1357).
Native status: built for the composite (D5.2, N2.4); the orientation contract N3.7 and warm-up N3.6 are open. Port rules and proof: [playbook](../Guides/Native_Port_Playbook.md#pb-e1).

<a id="e2"></a>
### E2. Program, mesh and image-binding resources
`rendering/quick/scene3d/resources.py` (`MeshResources`, `warm_programs`, `bind_frame`, `ProgramUnavailable`,
`warm_pass_blocks`). Named programs, uniform locations, immutable DSA meshes, the image underlay and camera plane,
one `glBindTextures` per frame bind, compute programs through `compile_compute_program`, gradual warm-up entries.
Consumers: every scene3d user (also `offscreen_target.py:107`). Test: `test_scene3d_resources.py`,
`test_transition_warmup.py` (counts warm-up units). Native: N3.2 (D15, `native/core/src/mesh_buffers.*`, ABI 18:
meshes as program data uploaded once and content-owned, instance, storage and indirect streams from record `f32`
fields, every block in one arena at dynamic offsets, a pass's own vertex stage with per-record front face, instanced
quads in place of point sprites, indirect and batched draws; proved on both backends by `mesh_buffer_check.py`) and
N3.6 (lifetime, warm-up). Notes: a failed program is cached and re-raised, never recompiled until
release (`resources.py:23-26`); no texture-binding cache because Qt changes inherited state (`Scene3D_Resources.md:60-64`);
`MeshResources.uniforms` caches the first uniform-name list per program (Lessons line 322).
Native status: built (D15, N3.2, ABI 18). Port rules and proof: [playbook](../Guides/Native_Port_Playbook.md#pb-e2).

<a id="e3"></a>
### E3. Scene target (colour, depth, post-process attachments)
`rendering/quick/scene3d/target.py` (`SceneTarget`; 51 definitions). A multisampled colour and depth target for any
pixel rect, composited back through the item quad with no resolve blit. Opt-in attachments: RG16F velocity (motion
blur), overlay scope with emission for bloom, depth texture plus mid-scope `background()` capture, weighted-blended
OIT, HDR with an ACES tone map, and a shaft-source attachment. Consumers: Blinds, Block Spins, Crumble, Cube Turn,
Depth Cascade, Disintegrate, Exploding Tiles, Glass Shatter, Jigsaw, Membrane, Page Curl, Pixel Accretion, Volumetric
Dissolve (transitions); Oscilloscope, Neon Lake, Extruded Bubble, Extruded Spectrum, Sphere, Waveform Ribbon (modes).
Native consumer: Bubble (N5.1), its ambient target (RGBA8 coverage plus RGBA16F light, an explicit size that follows
its content, held at the smallest bucket while the ambience is off) sampled by its card pass; the Oscilloscope (N5.1,
registered and offered on Vulkan 21 Nov), N3.4's first consumer: a surface-sized single-sample overlay target (RGBA8 colour, with Glow an
RGBA16F emission) drawn by an instanced beam over a storage stream, then the bloom and the glow composite, or at Glow
0 the plain overlay composite (a program variant chosen at the Settings edge; D12 "As built: Oscilloscope"). Tests: `test_scene3d_target.py` (G1, G3A, shafts, scale, lifetime), `test_scene3d_dsa_targets.py`. Native: N3.1
(D14, `native/core/src/scene_targets.*`, ABI 17: targets as program data, sampled D32F depth, the capture step, MRT with
per-attachment blends, one sampling request owner `scene3d.scene_samples` and the core's clamp; proved single-sampled
on both backends by `scene_target_check.py`, multisampled through the core's nearest resolve, D14 point 10) and N3.4
(D17, `native/core/src/post_stages.*`: the transparency target and its per-sample resolve, the composite step
with the HDR tone map and dither, the device gate with the sorted fallback; proved by `post_stage_check.py`; what this
makes possible: order-independent transparency, glow and the HDR look for any native mode as program data, the Python
owners' pictures on both backends; showcase `native_core/n3_4/20261115_n34_showcase_4c0ee9b7/showcase_post_stages_vulkan.webp`);
the eight composites in `target.py:125-286` keep raw `gl_FragCoord` and are never converted (D5.2 replaces them;
item 8b, N1.4's remainder). Notes: allocation rounds to 64 px; no `glBlitFramebuffer` resolves (about 0.5 ms at 1440p; Lessons line
176-177); per-sample reads (`sampler2DMS`, `gl_SampleID`) are the N1.8 resolve-first set; QRhi's own depth resolve is wrong on both backends, so the core's nearest pass reads every sample, and `texelFetch` on a multisampled D32F works on both (D14 point 10, proved at N3.1 round 3); the multisampled velocity attachment is the only listed use of D5.3's formats service and natively it is two R16F attachments (`Current_Plan.md` item 8b, formats box; Research section 14); Waveform's 4 samples and the Oscilloscope's 1 are declared fixed requests of `scene3d.scene_samples` (D14 point 7); a 1-sample multisampled renderbuffer does not rasterise like a direct draw (Lessons line 178-179).
Native status: targets are built (D14, N3.1); OIT, bloom and HDR are built and audited (N3.4, D17). The remaining defocus investigation is non-blocking; consumer-specific proof remains required. Port rules and proof: [playbook](../Guides/Native_Port_Playbook.md#pb-e3).

<a id="e4"></a>
### E4. Bloom chain
`rendering/quick/scene3d/post.py` (`BloomChain`, `FULLSCREEN_VERTEX_SOURCE`, `BLOOM_PROGRAMS`). Four halvings of
emitted light then tent upsamples, RGBA16F, about a third of a full-screen pass; only emitted light glows (alpha in a
bloom target). Consumers: through `SceneTarget` (every bloom-enabled consumer in E3). The full-screen vertex source is
also used by Environment, Motion, Shafts and Trails: it is the Python seed of **N4.a** (the fullscreen pass and image
sampling, `Current_Plan.md` item 8b, N4.a's box). Test: `test_scene3d_dsa_targets.py:97`, `test_transition_warmup.py:54`. Native: N3.4
(a bloom step: four RGBA16F textures, one a level, the core's 13-tap and tent shaders held to `post.py` by
`tests/test_native_post_stages.py`; exact against Python with its source sampled LINEAR/CLAMP; Python's own source
sampler, NEAREST with REPEAT, is a recorded defect, D17).
Notes: photographs write 0 emitted light so endpoints stay exact (Lessons line 180-181).
Native status: built and audited (N3.4, D17); remaining investigation non-blocking, with consumer-specific proof required. Port rules and proof: [playbook](../Guides/Native_Port_Playbook.md#pb-e4).

<a id="e5"></a>
### E5. Motion blur (velocity plus tile max)
`rendering/quick/scene3d/motion.py` (`MotionBlur`, `motion_program`). Analytic screen velocity over a shutter, a
compute tile max (one workgroup per K x K tile, K = target height / 40) and a bounded 3 x 3 neighbourhood gather;
Off compiles and dispatches nothing. Consumers: Block Spins, Crumble, Glass Shatter, Pixel Accretion (all import
`scene3d.motion` directly); Exploding Tiles also measured with it (`Scene3D_Resources.md:323-325`; no direct import). Tests: `test_scene3d_compute.py`, `test_scene3d_target.py`,
`tools/compute_pass_identity.py`. Native: **N4.i** ("five transitions", N4.i's box), N5.2d. Notes: it was the first
compute consumer because it removed passes (Scene3D_Resources "Compute seam", tile max: -14 GL calls per frame with
motion blur, byte-identical output); the barrier order is tested, not pixels (NVIDIA hid a missing barrier,
Lessons line 232-233); a target needing tiles over about 10,000 px high is a loud error.
Native status: decided, not built (N4.i). Port rules and proof: [playbook](../Guides/Native_Port_Playbook.md#pb-e5).

<a id="e6"></a>
### E6. Motion trails
`rendering/quick/scene3d/trails.py` (`MotionTrails`, `trail_program`). Ghost silhouettes at earlier moments, edge
filtered into fading light lines laid under the pieces. Consumers: Block Spins, Crumble, Exploding Tiles, Glass
Shatter, Pixel Accretion. Test: `test_scene3d_trails.py`. Native: **N4.i**. Notes: a ghost decides from its own motion
whether to draw (Lessons line 190-192).
Native status: decided, not built (N4.i). Port rules and proof: [playbook](../Guides/Native_Port_Playbook.md#pb-e5).

<a id="e7"></a>
### E7. Photo and backdrop environments
`rendering/quick/scene3d/environment.py` (`PhotoEnvironment`, `BackdropEnvironment`). A per-run, renderer-owned,
mipmapped copy of a photograph (the lent presentation texture is never modified) for blurred reflections via
`sceneEnvironment` at `sceneReflectionUv`; `BackdropEnvironment` is the Visualizer's equivalent of the displayed
photograph, once per image change. Consumers: `PhotoEnvironment`: Blinds, Block Spins, Cube Turn, Depth Cascade,
Exploding Tiles, Glass Shatter, Jigsaw, Membrane, Page Curl, Volumetric Dissolve (ten, as the plan says);
`BackdropEnvironment`: Extruded Spectrum, Sphere. Tests: `test_scene3d_environment.py`. Native: **N4.j**; N5.2c, N5.3.
Notes: look up a reflection by the reflected ray, never by screen position (Lessons line 193-195); named construction
allocates the complete mip chain; allocation or copy failure invalidates the cache identity.
Native status: not built (N4.j); no decided design beyond the plan's box.

<a id="e8"></a>
### E8. Stream ring (persistently mapped)
`rendering/quick/scene3d/stream.py` (`StreamRing`). One immutable persistently mapped, fenced buffer; a payload is one
`memmove` and one `glBindBuffersRange`. Defaults: 4 slots, 16,384 bytes a slot, 4,096 held per outermost `bound`
(`stream.py:62`); a slot is reused only after its fence, never rotated inside a scope; over-capacity is a loud error.
Consumers: Extruded Spectrum, Extruded Bubble's drift solver, Oscilloscope, Neon Lake, Sphere, the ribbon primitive and
bursts, Disintegrate, Exploding Tiles, Volumetric Dissolve, and every `UniformBlock` / `PassBlocks` (E9). Test:
`test_scene3d_stream.py`. Native: one of D5.3's services ("Stream ring"), built **only if** it beats QRhi dynamic
buffers by 0.05 ms at the product's ring sizes; **measured 15 Nov (N3.2) and not built**: every QRhi route from 4 KiB
to 288 KiB is within 0.05 ms of the pair's floor on both axes and both backends (D5.3's row has the figures; the
native core's streams are QRhi `Dynamic` and `Static` buffers, D15 point 4). Notes: a new transport earns its
place by removed calls, not by being modern (Lessons line 221-222); never rewrite bytes a submitted draw may still
read (line 220); `restore=False` is for scenes that own their whole frame's state (`Scene3D_Resources.md:269-282`).
Native status: measured 15 Nov and not built (D15 point 7). Port rules and proof: [playbook](../Guides/Native_Port_Playbook.md#pb-e8).

<a id="e9"></a>
### E9. Uniform blocks, pass blocks and layouts
`rendering/quick/scene3d/uniforms.py` (`UniformBlock`, `PassBlocks`, `SCENE3D_UNIFORM_BINDING = 15`) with the pure
layouts in `rendering/gl_programs/scene3d.py` (`Scene3DBlockLayout` at line 1070 per Decisions, `Scene3DStorageLayout`).
std140 and std430 declarations plus packers (and numpy dtypes). Consumers: Spectrum, Sphere (the shared
`SphereFrameBlock`), Disintegrate, Exploding Tiles, Volumetric Dissolve, and every program converted in N1.6.
Tests: `test_scene3d_uniforms.py`, `test_scene3d_stream.py`, `tools/conventions_identity.py`. Native: the Python
packer is the oracle the C++ packer is first tested against (Decisions line 1385); N1.2 and N1.3, N1.6. Notes: block
bindings 16 (compute), 17 (conventions), 18 (pass block) are reserved, 15 is the per-frame uniform block (section 7).
Native status: built as the block arena (D15 point 3). Port rules and proof: [playbook](../Guides/Native_Port_Playbook.md#pb-e9).

<a id="e10"></a>
### E10. Compute seam and blend scopes
`rendering/quick/scene3d/compute.py` (`dispatch(groups, barriers)`, `bound_image`, `DispatchBlocks`,
`COMPUTE_BLOCK_BINDING = 16`) and `scene3d/passes.py` (`blend_scope`). The writer issues the barrier its reader needs;
image units are scoped and handed back; no queue, scheduler, worker, readback or polling. Consumers: Edge Field, Fog
Volume, Floor Give and Waveform Field, Motion, Population, Propagation Field, the drift solver. Tests:
`test_scene3d_compute.py`, `tools/compute_pass_identity.py` (`record`, `compare`, `paired`). Native: **N3.3**
(D16, `native/core/src/compute_passes.*`, ABI 19: compute entries in a program's pass list, each its own QRhi compute
pass under a `frame` or record-field trigger; storage buffers and 2D/3D images shared with draws; barriers from the
bindings' declared access, checked against `qsb`'s reflection; no product readback but D4's pair self-check) and D9
where a job is admitted. Notes: compute earns a stage only where it removes passes, targets or calls (Lessons lines 225-227);
storage-image formats are the shipped backends' (SPIR-V, GLSL 430, HLSL 5.0, MSL 1.2: a scalar half-float image is
`r16f`); `blend_scope` is used by Bloom, Trails, Particles, Shadows, Disintegrate, Jigsaw and Volumetric Dissolve.
Native status: built (D16, N3.3, ABI 19). Port rules and proof: [playbook](../Guides/Native_Port_Playbook.md#pb-e10).

<a id="e11"></a>
### E11. Compacted populations
`rendering/quick/scene3d/population.py` (`CompactedPopulation`). Three dispatches (count, scan, scatter) and one
`glDrawArraysIndirect`; no readback; slots follow id order (prefix sum, not atomic append), so blending order is
stable; fixed capacity, five immutable buffers. Consumers: **Disintegrate and Volumetric Dissolve only**. Test:
`test_scene3d_population.py` (exact against a CPU reference from 1 to 300,000 members). Native: **N4.c, high
potential, built without a consumer** (N4.c's box): both transitions port 1:1 on QRhi's own `drawIndirect` (Qt 6.12);
"draw the maximum, cull in the vertex shader" only for a backend without `QRhi::DrawIndirect`; the harness runs at one
million sprites (Decisions D8 row 7). Notes: measured against per-vertex evaluation, compaction saved 29 to 49 percent
GPU at a fixed cost of about 0.1 ms CPU submit (about 20 calls); the two paths are close in total on the development
GPU (`Scene3D_Resources.md` "Compacted GPU populations", 4 sizes); compact only when the pool is large (Lessons lines
318-319); a population's state is one `vec4` (line 335).
Native status: decided, not built (N4.c). Port rules and proof: [playbook](../Guides/Native_Port_Playbook.md#pb-e11).

<a id="e12"></a>
### E12. Ribbon, strip and event sparks
`rendering/quick/scene3d/ribbon.py` (`RibbonPrimitive`, `ribbon_grade`), `ribbon_bursts.py` (`RibbonBurstRenderer`),
with `core/ribbon_geometry.py`, `core/ribbon_frames.py`, `core/ribbon_packet.py` (bounded absolute-coordinate history,
centripetal interpolation, camera-facing width) and the GLSL in `rendering/gl_programs/ribbon.py`. An oriented SSBO
strip with a body pass (inside `transparent_writes`) and a light pass (inside `emission_writes`), strays, cohorts and
sparks. Consumer: Waveform Ribbon (through `scene3d/waveform.py`). Tests: `test_ribbon_gpu.py`,
`test_ribbon_material.py`, `test_ribbon_bursts.py`, `test_ribbon_continuation*.py`, `tools/labs/ribbon_material_probe.py`.
Native: **N4.b** (S3D-1; N4.b's box), ported with Waveform Ribbon (N5.4). No class stated. Notes: OIT, defocus,
broader normal and precision proof and scene composition "remain open" in `Scene3D_Resources.md:611-619`; history
carried shape needs band-limiting and monotone-cubic knot interpolation (Lessons lines 264-268); thin emissive sheets
scale light by path length and widen sub-pixel stretches (lines 271-275); clamp interpolants before `exp` (lines
261-263); hash per-object constants only through `flat` varyings (lines 276-278). Path reference:
`Docs/Reference/Ribbon_Path.md`.
Native status: not built (N4.b); the topology rule is decided. Port rules and proof: [playbook](../Guides/Native_Port_Playbook.md#pb-e12).

<a id="e13"></a>
### E13. Planar reflection and rough receivers
`rendering/quick/scene3d/reflection.py` (`PlanarReflection`) with `rendering/gl_programs/reflection.py`
(`mirror_view`, anisotropic receiver sampling, contact hardening). One lazily allocated mipmapped RGBA16F target and
depth renderbuffer; the receiver integrates a roughness footprint (long streaks split into up to eight abutting
Gaussian-weighted segments); emitters opt in by writing luminance times world height into alpha. Consumer: Waveform
Ribbon (floor). Test: `test_scene3d_reflection.py`. Native: **N4.d, planar reflections and rough receivers, wet-surface
masks (the plan calls the item "high potential", N4.d's box)**. Notes: the primitive does **not** yet clip geometry
crossing the plane; it is "a bounded directional filter, not a full microfacet ray-traced reflection"; the lab
measured 0.162 to 0.222 ms median for the wet floor draw at 820 x 718 on an RTX 4090 with an unexplained spiky p90;
consumer inclusion, clipping, resize, failure-path and whole-scene cost remain open in the Waveform lab plan
(`Scene3D_Resources.md:197-205`). Neon Lake's water reflection is analytic in its own basin shader and needs none of
this (N4.d's box).
Native status: decided, not built (N4.d). Port rules and proof: [playbook](../Guides/Native_Port_Playbook.md#pb-e13).

<a id="e14"></a>
### E14. Scene probe
`rendering/quick/scene3d/probe.py` (`SceneProbe`). One RGBA16F cube with a full mip chain, rendered in six faces and
pre-filtered over a Gaussian cone (32 taps, across face edges); GLSL `sceneProbe(probe, direction, blur, levels)`.
Consumer: Extruded Bubble. Test: `test_scene3d_probe.py`. Native: **N4.d** ("the scene probe (Extruded Bubble)");
the six-face draw is one geometry-shader `gl_Layer` draw today, which QRhi marks experimental, so the core draws six
draws per level (Decisions D5.6 row 18). Notes: probe cost was 0.18 ms GPU in the EB lab; nothing allocates after the
first capture; `warm()` allocates on a hidden frame.
Native status: decided, not built (N4.d). Port rules and proof: [playbook](../Guides/Native_Port_Playbook.md#pb-e13).

<a id="e15"></a>
### E15. Fog volume and fog march
`rendering/quick/scene3d/fog_volume.py` (`FogVolume`, `FogMarch`) with `rendering/gl_programs/fog_volume.py` and
`mist.py`. `FogVolume`: a camera's coarse froxel grid evaluated from a consumer's `fogMedium` compute source into an
RGBA16F 3D texture (plus an R16F steady share) that the mist functions sample. `FogMarch`: a reduced-resolution
detail march that erodes the non-steady coverage with a baked 3D noise. Consumers: `FogVolume`: Waveform Ribbon;
**`FogMarch` has no production consumer** (only `tools/compute_pass_identity.py:484`, `tests/test_scene3d_fog_volume.py`
use it), as the plan says (N4.f2's box). Test: `test_scene3d_fog_volume.py`. Native: **N4.f1** (the fog volume port, before N5.4) and **N4.f2** (reduced-resolution
volumes and mixed-resolution soft layers, "after N5.6, before Expanded Visualizer M6"; N4.f1 and N4.f2's boxes) and the base of
**N6.3**. Notes: the march is "too costly at full size in the Python path" (0.4 to 1.2 ms main march, 0.2 to 0.7 ms
mirrored, at 820 x 718 on an RTX 4090; `Scene3D_Resources.md:167-173`); it has open lifecycle defects in the plan
(raw `glDeleteProgram` that never hands back a conventions hold, `scene3d/fog_volume.py:424`, `Current_Plan.md` item 8b, N1.4's remainder);
the steady share must never be eroded; Lessons "Volume mist" (lines 290-301).
Native status: decided, not built (N4.f1, N4.f2). Port rules and proof: [playbook](../Guides/Native_Port_Playbook.md#pb-e15).

<a id="e16"></a>
### E16. Edge field
`rendering/quick/scene3d/edge_field.py` (`EdgeField` plus CPU mirrors `edge_field_reference`). Per run and photograph:
luma copy, binomial blurs, Sobel ridges with non-maximum suppression, jump flooding, resolve; a distance-and-strength
field; seven dispatches plus one per flood step; six textures at 768 px on the longer side (about 14.6 MiB at 16:9).
Consumer: Edge Bloom only (`edge_bloom.py:16`). Tests: `test_qtquick_edge_bloom.py`, `tools/compute_pass_identity.py`.
Native: **N4.g** (Edge Bloom and Capillary Bloom only), N5.2g, and the heavy job of D9's proof (the 4K build is 20 to
31 ms on Qt's queue in the frame, 0 late frames as a job; Decisions lines 578-584). No class stated. Notes: seeded
differently it could serve organic fills (`Scene3D_Resources.md:391-392`); the flood buffers were widened from RG32F
to RGBA32F by N1.7 (bit-identical; QRhi lacks RG formats).
Native status: built 22 Nov at ABI 43 (N5.2g): a field recipe the core runs as an async job on Vulkan and in the frame
on OpenGL (`native_fields.py` `edge_field_recipe`; playbook [E16 and E17](../Guides/Native_Port_Playbook.md#pb-e16)).

<a id="e17"></a>
### E17. Propagation field
`rendering/quick/scene3d/propagation_field.py` (`PropagationField`, `propagation_reference`). Cheapest cost-weighted
arrival from a few sources over a consumer's `propagationCost`; 192 in-place relaxation passes on a 16-neighbour
stencil and a reduction; three R32F textures at 256 px. Consumer: Capillary Bloom only. Test:
`test_propagation_field.py`. Native: **N4.g**, N5.2g (the first transition preparation run as an async job, D9
consumer class a, N5.2g's box). No class stated. Notes: fingering needs the true cheapest way, a geodesic arrival map,
not a point or line average (Lessons lines 366-368).
Native status: built 22 Nov at ABI 43 (N5.2g): the same field recipe form, two R32F item textures (the arrival and its
extent), no input picture (`native_fields.py` `propagation_recipe`; playbook
[E16 and E17](../Guides/Native_Port_Playbook.md#pb-e16)).

<a id="e18"></a>
### E18. Sphere impostors, optics and water
`rendering/gl_programs/scene3d_spheres.py`, `scene3d_optics.py`, `scene3d_water.py`, `scene3d_sky.py` (import-safe
GLSL plus CPU mirrors, no resources). Exact sphere silhouettes from one quad per instance with true surface depth;
exact Fresnel, thin film, sphere refraction and hollow-sphere light-path tracing (up to eight paths); deep-water
waves, caustics, Snell's window and medium absorption. Consumers: Extruded Bubble (`extruded_bubble_program.py:13-15`,
`extruded_bubble_scene.py:33`); the sky functions by Neon Lake (`neon_celestial.py:11`). Tests:
`test_scene3d_spheres.py`, `test_scene3d_spheres_mirrors.py`, `test_scene3d_optics_water.py`, `test_scene3d_sky.py`,
`test_scene3d_glsl_mirrors.py`. Native: **N4.g** ("sphere impostors, shared optics and underwater light (Extruded
Bubble)"). No class stated. Notes: rough transmission and dispersion were evaluated and recorded unnecessary for the
target (`Scene3D_Resources.md:511`); `scene3d_spheres.py:197` assumes OpenGL's -1..1 depth and is an open side defect
(`Current_Plan.md` item 8b, N1.4's remainder); the vertex-stage variant compiles out the `fwidth` coverage overload because strict
compilers reject derivatives in a vertex shader.
Native status: not built (N4.g).

<a id="e19"></a>
### E19. Defocus layer
`rendering/quick/scene3d/defocus.py` (`DefocusLayer`). Depth of field for objects near the lens: an RGBA16F colour
plus alpha-weighted circle of confusion, a 64-tap golden-angle gather (light conserved) and an optional highlight
split into instanced discs. Consumer: Extruded Bubble. Test: `test_scene3d_defocus.py`. Native: N3.4 ("the defocus
layer": a mipped target and a defocus step, mips by QRhi's `generateMips`, every level equal to Python's on OpenGL, the
read level capped where levels come from odd sizes; D17) and N5.6. No class stated. Notes: the EB abyss near defocus measured 3.3 ms of its GPU budget (largely the
near shells drawn into the layer; `Scene3D_Resources.md:529-533`); masks are per draw-buffer index (a masked emission
index once dropped every circle); the RG16F circle storage was widened by N1.7.
Native status: built and audited (N3.4, D17); remaining investigation non-blocking, with consumer-specific proof required. Port rules and proof: [playbook](../Guides/Native_Port_Playbook.md#pb-e4).

<a id="e20"></a>
### E20. Light shafts
`rendering/quick/scene3d/shafts.py` (`LightShafts`, `ShaftLight`) through `SceneTarget(shafts=True)`: a half-size
R16F downsample and two 16-tap radial gathers (256 effective taps). Consumer: Neon Lake. Test:
`test_scene3d_target.py` (shafts). Native: **N4.k, high potential, "ported with Extruded Bubble, then used by Neon
Lake"** (N4.k's box): Extruded Bubble has its **own second implementation** of shafts that the item merges onto one
owner. Notes: the shaft source downsample reads `sampler2DMS` (an N1.8 resolve-first use, `Current_Plan.md` item 8b, N1.8's box).
Native status: decided, not built (N4.k). Port rules and proof: [playbook](../Guides/Native_Port_Playbook.md#pb-e15).

<a id="e21"></a>
### E21. Shadows (planar and directional silhouettes)
`rendering/quick/scene3d/shadows.py` (`draw_planar_shadows`, `directional_shadow_vector`, `directional_shadow_pass`,
`extruded_shadow_length`). The photograph-darkening MIN-blended planar shadow of the 3D transitions and the target-free
directional silhouette of the Extruded Spectrum. Consumers: Exploding Tiles (planar), Extruded Spectrum (directional);
Sphere has its own projected-shadow pass in its program and renderer. Tests: `test_extruded_shadow_reach.py`,
`test_qtquick_extruded_spectrum.py`. Native: **N4.l** (silhouette shadows as one shared primitive, distinct from N4.h)
and **N4.h** (a real fitted shadow map, **high potential: built without a consumer**, "not a revival of the rejected
Extruded cast shadows, and no mode turns it on without its own review"; N4.h's box). Notes: the E8-era Extruded cast
shadow receiver is rejected and stays disabled (R-119 to R-128:
`Docs/Historical_Bugs/R-125_to_R-128_Extruded_Cast_Shadow_Failure.md`; `Scene3D_Resources.md:12-14`); G2 "none" in the
capability inventory, no fitted depth-map foundation exists (N4.h's box).
Native status: decided, not built (N4.h, N4.l). Port rules and proof: [playbook](../Guides/Native_Port_Playbook.md#pb-e21).

<a id="e22"></a>
### E22. Bendable grid
`rendering/quick/scene3d/grid.py` (`draw_grid`) with `scene3d_grid_vertex_source`, `scene3d_grid_vertices` in
`gl_programs/scene3d.py`. A bendable grid surface drawn around an effect's displacement. Consumers: Membrane, Page
Curl; Neon Lake draws its own lattice from `scene3d_grid_vertices`. Test: `test_scene3d_grid.py`. Native: **N4.l**
("the bendable grid (Membrane, Page Curl)"); N4.e's heightfield mesh is "the grid a dynamic surface field will share".
Native status: not built (N4.l).

<a id="e23"></a>
### E23. Shared particle pass
`rendering/quick/scene3d/particles.py` (`draw_particles`, `particle_budget`). One instanced camera-facing streak or
soft-sprite pass added as light, depth untouched, with the per-tier budget. Consumers: Exploding Tiles' sparks;
`RibbonBurstRenderer` (E12) draws Waveform's event sparks through it. Native: part of N4.l (Exploding Tiles'
particles) and of N3.2 (instanced quads in place of `gl_PointSize`). Notes: point sprites are a restructured draw, not
a missing feature (Decisions D5.6 row 11).
Native status: built as instanced quads (D15 point 5); the pass itself is N4.l, not built. First product consumer of
the instanced quads: Bubble (N5.1), its ambient points and hero-circle mask as two instance streams from its record
(`native_route.bubble_program`); the second: the Oscilloscope's beam, one instanced quad a segment over a storage
stream of the traces' points (`native_route.oscilloscope_program`; D12 "As built: Oscilloscope"). Port rules and proof: [playbook](../Guides/Native_Port_Playbook.md#pb-e2).

<a id="e24"></a>
### E24. Heightfields and terrain sampling
`rendering/quick/scene3d/heightfield.py` (`HeightfieldTexture`: one lazy immutable R32F or two-component texture,
upload on change) with `rendering/gl_programs/heightfield.py`, `heightfield_glsl.py`, `heightfield_volume_glsl.py`
(cubic B-spline surface sampling, curved wire coordinates, bounded single-scattering volume over the same sampler:
12, 8, 6 or 4 world-ray steps). Consumer: Neon Lake (`shockwave_grid.py:38,104,112`; the volume in
`neon_lake_basin_program.py:23`). Test: `test_scene3d_heightfield.py`. Native: **N4.e** (the authored heightfield
resource; Neon Lake's tile-refined basin; the grid a dynamic surface field shares). No class stated. Notes: no shared
simulation, clock or global texture cache; the volume is "not a shadow map or a fluid simulation" and may miss thin
ridges between taps (`Scene3D_Resources.md:118-123`); Neon Lake's driver memory at its first draw (about +280 MB
committed) is unattributed (`Current_Plan.md` item 8b, P2 remainders, a P2 remainder).
Native status: decided, not built (N4.e). Port rules and proof: [playbook](../Guides/Native_Port_Playbook.md#pb-e24).

<a id="e25"></a>
### E25. Soft-light array
`rendering/gl_programs/lighting.py` (`MAX_SOFT_LIGHTS = 96`, `SOFT_LIGHT_GLSL`). Bounded unshadowed soft-source
irradiance from caller-supplied positions, radii and flux, no resources. Consumers: **none in production** (the only
importers are `tools/labs/ribbon_lighting.py:11` and `tests/test_scene3d_lighting.py:8`), matching the plan ("written,
tested, used by a lab only"). Test: `test_scene3d_lighting.py`, `test_ribbon_lighting.py`. Native: **N4.m, high
potential, built without a consumer** (N4.m's box). Notes: it uses loose `uLightCount` / `uLightPosition[96]` /
`uLightFlux[96]` uniforms, so it needs an N1.6 conversion into a block before it can be baked (**unverified** whether
the conversion is scheduled; N1.6's group list item 8b, N1.6 does not name it); it is "a low-frequency lighting
approximation, not area-light visibility or specular reflection".
Native status: not built (N4.m).

<a id="e26"></a>
### E26. Waveform's own fields (borderline: mode code in a shared folder)
`scene3d/waveform.py` (`WaveformScene`), `waveform_field.py` (`WaveformField`), `floor_give.py` (`FloorGiveField`),
`pulse_rim.py` (`PulseRimField`). Each is imported only by the Waveform scene, with fixed-world compute fields reduced
once per frame without readback. They are Waveform Ribbon's own code (N5.4's "its five compute passes and three
rings, floor and pulse-rim textures"), not primitives for other modes. Listed so nobody mistakes them for shared
ones. The Lessons' "Wet reflective floors" and "Volume mist" blocks (lines 279-301) record what they taught.
Native status: mode code, not a primitive.

<a id="e27"></a>
### E27. Program binary cache and the one link function
`rendering/quick/render/gl_resources.py` (`_link`, `compile_program`, `compile_compute_program`, `delete_program`) and
`gl_program_cache.py` (`ProgramBinaryCache`). Every custom GL program links through one function; a stored binary
keyed by SHA-256 of schema, driver strings and sources is loaded with `glProgramBinary`; a cold link is paid once per
machine and driver (R-180: Neon Lake's basin ~6 s cold, ~30 ms loaded). Store in `<LOCALAPPDATA>/SRPSS/gl_program_cache`,
bounded to 64 MB. Test: `tests/test_gl_program_cache.py`. Native: replaced by Qt's pipeline cache and `qsb` bakes
(D5.6 row 5); N3.6 owns warm-up. Notes: the conventions buffer registry here is keyed by the native context pointer
(`gl_resources.py:147-196`, R-198, `Docs/Historical_Bugs/R-198_*.md`); see contradiction list in section 7 for the
plan box that still shows it open.
Native status: replaced by Qt's pipeline cache; warm-up N3.6 decided, not built. Port rules and proof: [playbook](../Guides/Native_Port_Playbook.md#pb-e1).

<a id="e28"></a>
### E28. Backdrop pyramid (card surface materials)
`rendering/quick/render/surface_backdrop.py` (`BackdropPipeline`). One shared blurred backdrop per display, built by a
blit of the window target into half, quarter, eighth, sixteenth and thirty-second levels with up passes into a
two-mip RGBA8 output; armed one-shot or continuously during a transition; absent while every surface is Normal.
Design: `Docs/Architecture/Card_Surface_Materials.md`. Native: **N5.7b** (D7: built from the core's own background layer
texture, only when changed and only while demand is above zero; budgets 0.3 ms at 2560 x 1440 and 0.6 ms at 4K,
Decisions D5.6 row 10), and N5.9 (true glass). Notes: the blit and its eight dirtied states are Python-OpenGL-only
(`surface_backdrop.py:236-283,419-423`); the protected clip and background commits (ce07b991, 07486d83, 985b9d53) are
not retuned.
Native status: built (D7, N5.7b, 14 Nov). Port rules and proof: [playbook](../Guides/Native_Port_Playbook.md#pb-e28).

<a id="e29"></a>
### E29. Presentation textures and the wrapped-texture bridge
`rendering/quick/render/image_textures.py` (`PresentationTextureHost`), `native_texture_bridge.py`,
`background_node.py`. The only owner and deleter of presentation GL textures; PR-04 lends a transition's destination
texture to the retained background; the bridge adopts a GL name as a scene-graph texture and refuses when the API is
not OpenGL (`native_texture_bridge.py:111-114`). Native: **N5.7a** (the core's background layer owns images as QRhi
textures; D9's job form is the async upload) and N5.2h (the bridge is deleted with the Python presenter). Notes: the
bridge is a GL-only seam that cannot survive the flip.
Native status: built (N5.7a, 14 Nov); the GL-only bridge dies at N5.2h. Port rules and proof: [playbook](../Guides/Native_Port_Playbook.md#pb-e28).

## 4. Shared services of the native core

"Decided" means the decisions document fixes the design, "proved" means a harness round (`native/spike_p1`, or the
product module's `native/core/python/*_check.py` on a GitHub build) verified it; `native/core/README.md` lists what
the product module holds today.

| Service | Source | Status (14 Nov) | What it enables |
|---|---|---|---|
| **Host adapter** (D5.1) | Decisions line 168-176 | built and proved in N2.2 (`native/core/src/host_adapter.*`, `host_check.py`) | the core never names Qt Quick's frame; a second window kind or a Qt upgrade changes one small file. Hosts: the Qt Quick window, the hidden host, a reserved swapchain-owning host |
| **Frame driver** (D5.2) | Decisions line 178-204 | built and proved in N2.2 (`frame_driver.*`) | all core work recorded in dependency order on `beforeRendering` through a C++ connection (no Python slot) |
| **Texture-node composite** (D5.2) | line 185-199; N2.4 | built and proved 13 Nov (`composite.*`, `composite_check.py`: texels one to one, the 1C.4 clip contract) | each surface reaches the window as a texture provider a `ShaderEffect` can sample at no cost; Qt applies clip, opacity, batching |
| **Packet reader** (D1, D2, transport rule) | Decisions "D1, D2, D3 and the transport rule"; N2.3 | built and proved 14 Nov (`packet_reader.*`, `frame_abi_generated.h`, `packet_reader_check.py`; module ABI 5); its first user is N2.5 | the core reads a Visualizer stream on its own view of the mapping, refuses an unknown payload at the slot head, and is its one consumer |
| **No Python on the core's threads** (D5.4) | line 232-234 | decided; rechecked at every port | frame pacing independent of the GIL (D8 plus 1) |
| **Module location** (D5.7) | line 236-238 | built: `native/core/`, module `_srpss_native_core` (N2.1) | exact-Qt import guard, one Python importer (`rendering/native/`) |
| **GPU timer per pass** (D5.3 row 1) | line 217; N2.6 | built and proved 13 Nov (`native/core/src/gpu_timer.*`, `rendering/native/gpu_timing.py`, `timer_check.py`) | per-pass figures in the frame trace; off means no query objects; every later port measured per pass |
| **Stream ring service** (D5.3 row 2) | line 218; N3.2 | **measured 15 Nov, not built**: QRhi's routes within 0.05 ms of the pair's floor at 4 KiB to 288 KiB on both backends (`mesh_buffer_check.py --rounds stream_ring`; D5.3's row) | larger histories and denser strands at one copy per frame, through QRhi's own buffers |
| **Meshes, streams and the block arena** (D15, N3.2) | Decisions D15; `native/core/src/mesh_buffers.*` | built and proved 15 Nov (ABI 18; `mesh_buffer_check.py`: rules (a) and (b) within the shared pixel tolerance (D12), nothing at rest, no allocation per record, retirement, validation) | a mode's geometry as data with no per-mode C++: meshes, instanced and vertex-pulled draws, per-record front face, full blend declarations (`max`, `min`), instanced quads for point sprites (`srpss_geometry.glsl`), indirect draws from record commands, batched draws (one multi-draw with `gl_DrawID` where reported, else one draw a batch). Class: high potential (the lead, choice G: built with no consumer) |
| **Compute passes and storage** (D16, N3.3) | Decisions D16; `native/core/src/compute_passes.*` | built and proved 15 Nov (ABI 19; `compute_pass_check.py`: rules (a) and (b) exact on every resource, dispatch only on new work, nothing at rest, retirement, synchronisation validation with shader-access checks and two negative controls) | a mode's compute as data with no per-mode C++: compute entries under triggers with `fresh`, storage buffers and 2D/3D storage images read by draws (storage, vertex input, `drawIndirect`, `sampler3D`), prefix-keeping resizes. Consumers: Waveform Ribbon's five passes, Extruded Bubble's drift, the compacted populations (N5) |
| **Indirect and count draws** (D5.3 row 3) | line 219 | **retired 12 Nov**: QRhi 6.12 has `drawIndirect` and `DrawIndirectMulti`; N4.c queries support at runtime (N4.c's box) | GPU-driven populations of 10^5 to 10^6 without a raw service |
| **Per-sample reads** (D5.3 row 4) | line 220; N1.8; D14 point 10 | **decided 15 Nov** (the lead, after N3.1's build round 2: QRhi's depth resolve gave wrong values on both backends): the scene target's nearest resolve, a QRhi pass reading every sample (`scene_nearest.frag`), built and proved in N3.1's round 3 on both backends (the multisampled D32F sampled directly; an R32F attachment declared "nearest" beside it) | Extruded Bubble's nearest-depth `background()` (N1.8's A/B settled: the nearest depth, as Python) |
| **Formats service** (D5.3 row 5) | line 221; N1.7 widened first | one listed use, the multisampled velocity attachment (N1.7's box); natively two R16F, since QRhi has no RG16F (Plan, formats box; Research section 14) | RG16F, RG32F, R11G11B10F without doubling memory |
| **Async GPU jobs** (D9, row 6) | line 498-622; N3.8 (N3.8's box) | **proved N0.7** (second QRhi on our VkDevice, queue index 1 of family 0; latched publication; in-frame form always exists); built in N3.8; ABI 43 (N5.2g, consumer class a): field recipes as jobs, a core-owned deadline falling back to the in-frame form, and the `on_textures_ready` edge (`field_check.py`) | no late frame at an image change or a transition's preparation while a Visualizer runs (4K edge-field build in frame: 40 late of 1200, as a job: 0 late) |
| **Vulkan device ownership** (D6) | line 240+ | **proved N0.6** (our instance and device host Qt Quick pixel-identical; teardown, resize, second queue) | one device per window; Vulkan by default at NF |
| **Backdrop pyramid** (D7) | line 383+; N5.7b | built 14 Nov (N5.7b; D7 "as built"; `backdrop_pyramid_check.py`) | materials that follow a transition frame; true glass over the Visualizer (N5.9) |
| **Conventions include** `srpss_conventions.glsl` (N0.3) | `rendering/gl_programs/conventions.py`; Decisions line 1358-1371 | built in Python (N1.4: OpenGL values make it an identity); the three backend scenes proved 12 Nov (Vulkan, OpenGL, D3D11, D3D12; Metal on the Watchlist) | the only place a shader learns a backend convention: `fragPixel/fragTexel/fragUv`, `ndcToUv/uvToNdc`, `viewDepthFromDepthTexture`; `SrpssConventions` block at binding 17, written once per context |
| **Portable programs / pass blocks** (N1.6) | `rendering/gl_programs/portable.py`; `scene3d/uniforms.py` `PassBlocks` | built, converting group by group; `LEGACY_GL_ONLY` was 16 after D4 (N1.6's box) | loose uniforms become one std140 block at binding 18, samplers get `binding = unit`, varyings get locations; arithmetic untouched so OpenGL pixels are identical (`tools/conventions_identity.py`) |
| **Shader readiness ratchet** | `tests/test_vulkan_shader_readiness.py`; `qsb` bakes | active; "discovers compute sources and bakes every target" (N1.6's box) | no non-bakeable shader can be added silently |
| **Pipeline and warm-up policy** (N3.6) | N3.6's box | decided; unbuilt | every state combination is a pre-built pipeline warmed gradually; `VK_EXT_device_fault` logged once |
| **Rehearsal path** (D10, N2.7) | D10 "As built"; the N2.7 leftovers box | built 13-14 Nov (`rendering/quick/bootstrap.py`, `--graphics-backend=vulkan`; reveal on the first presented frame; Settings greys unported modes); N2.8's lead runs on Display 1 | a diagnostic switch for Vulkan on Display 1 before the flip; unported modes not offered |
| **Framed camera** (D5.5, N0.4) | `core/settings/framed_camera.py`; Decisions line 1466+ | decided; the worker publishes the finished camera, built with N5.4 then N5.6 (N0.4's remainder box) | one camera for every framed 3D mode (section 7) |

Quick-side services that stay as they are until the native presenter replaces them: the program cache (E27), the
background item (`background_item.py`, the owner of the core's background layer, `native_background.py`, and of the
degraded display's image, `degraded_background.py`; N5.2h deleted the Python background and image nodes) and the GL
query helpers (`rendering/quick/gl_query.py`, raw getters for CPU-cheap reads; Lessons line 168-171).

## 5. Planned primitives (never built)

### The old id map (`Current_Plan.md` item 8b, standing rules)

| Old | New | Meaning |
|---|---|---|
| S3D-1 | N4.b | ribbon and strip |
| S3D-2 | N4.c | compacted populations (sprites, streaks) |
| S3D-3 | N6.2 | static scene geometry and materials (photo shells: N6.4) |
| S3D-4 | N6.1 | dynamic surface field |
| S3D-5 | N4.d | planar reflections, rough receivers, scene probe, wet-surface masks |
| S3D-6 | N4.h | shared shadows |
| S3D-7 | N4.f1, N4.f2 | reduced-resolution volumes; its smoke is N6.3, its lightning N6.6 |

### Six approved real-mode demonstrations (23 Nov 2026, artistic use AFTER native/Studio flip)

These six are an **approved eventual integration backlog**, not candidate-only or immediate
pre-flip requirements. Original-mode ports, Studio N5.8 and NF finish first; independent
high-potential primitive harnesses can proceed on the non-blocking track. Every integration
adds an optional mode feature, comprehensive canonical Studio appearance AND music-response
controls, and a **NEW freely mutable demonstration preset**. The preset is human-authorable
evidence, NOT a test input or golden; tests are built exclusively from synthetic data.
The complete rendered-fidelity, reactivity, control and rejection contract for each is in
`Current_Plan.md` N4/N6 artistic integrations. No new mode renderer, camera, clock, audio
analysis lane or backend parity gate.

| Approved demonstration | Host mode | Primary shared primitives | What becomes possible |
|---|---|---|---|
| **Kelp Cathedral** | Extruded Bubble | N6.7 mesh shaders where useful; N6.2, N4.h | Rooted underwater curved stalks and attached independently lagging leaves with depth, lighting and phrase-responsive current/flutter. Optional Vulkan-only kelp is permitted; original EB remains OpenGL-capable. |
| **Smoke Signals** | Waveform Ribbon | N6.3, N4.f2 | Real 3D smoke emitted by moving ribbons, advected and dissipated with musical phrases and transients, preserving source history. |
| **Rainfall Echo** | Neon Lake (`shockwave_grid`) | N6.1, N4.d, optional N4.c | Music-driven local water impacts, interfering physical ripples and reflection-normal response without replacing the accepted basin. |
| **Shadow Theatre** | Waveform Ribbon | N4.h | True shadow-casting ribbons and stable soft floor contact, driven principally by the existing reactive geometry. |
| **Abyssal Lanterns** | Extruded Bubble | N4.m, optional N4.c | Travelling locally illuminating bioluminescent clusters, lighting real nearby bubbles rather than drawing fake glows. |
| **Rain-Slick Floor** | Waveform Ribbon | N4.d | Anchored irregular wetness, differentiated roughness and moving ribbon reflections, with optional subtle music-driven water micro-disturbance. |

**Art and reactivity acceptance:** no single Enable switch or generic intensity scalar suffices;
each group exposes independently useful geometry/material/placement, motion, response ranges
and temporal behaviour in the existing production Studio. Test the capability against
synthetic fixtures, including off/on/quality extremes, visual change and temporal continuity;
never test real presets even for schema or storage behaviour. Displaying a capture is not
proof of reactivity. Operator signs off live music response and editable authored look.

### N6 (primitives track, native only; `Current_Plan.md` item 8b, the N6 boxes)

| Id | What it is | Class | What it makes possible (the plan's words) | Dependencies | Candidate consumers |
|---|---|---|---|---|---|
| **N6.1** | Dynamic surface field: a bounded GPU height-and-velocity grid with impulse injection and damping, a displaced mesh with true normals, reflection distortion driven by it | **High** | "water, ripples, pools, melt, any reactive surface" | N4.d (reflection distortion), N4.e (the grid it shares), N3.3 compute, N3.2 meshes | Reactive Liquid / Melt Pool (S3D-4, plan section 7.2), Concrete Rain (ripples, section 7.3), Neon Lake's water (named by the plan, but its reflection is analytic today), SMP surfaces |
| **N6.2** | Static scene geometry and materials, built once and kept (floors, walls, wells, simple skyline and tunnel slices; roughness, bevel, contact shading) | **High** | "what turns a mode into a place" | N3.2 meshes, N4.d | Melt Pool's chamber (section 7.2), Concrete Rain's street (section 7.3), SMP surfaces |
| **N6.3** | Advected smoke and haze on the volume primitive | **High** | "atmosphere for every 3D scene" | N4.f2 (shares its reduced-resolution path; the fog detail march is its base), N3.3 | every 3D mode, Waveform's atmosphere, Melt Pool, Concrete Rain |
| **N6.4** | Photo-textured shells and planes with real depth | **Low until a consumer** | none stated; "a transition or a mode built round the user's photos" | N3.1 targets, N4.j environments | none admitted |
| **N6.5** | The opt-in deformable sheet | **Low until a consumer** | none stated | N4.l's bendable grid, N4.e | none admitted |
| **N6.6** | Lightning: procedural bolt geometry and its light | **Low until a consumer** | "one effect" | N4.f2 (S3D-7's lightning), N3.4 bloom | none admitted |

### Unbuilt N4 items (ported with their consumer, or on the primitives track)

Existing in Python (section 3) but not yet native: N4.b (E12), N4.c (E11), N4.d (E13, E14), N4.e (E24), N4.f1 and N4.f2 (E15),
N4.g's E18 (E16 and E17 built at ABI 43, N5.2g), N4.h/N4.l (E21, E22, E23), N4.i (E5, E6), N4.j (E7), N4.k (E20), N4.m (E25). Class as stated by
the plan: high potential for N4.c, N4.d's wet-surface masks, N4.h, N4.k, N4.m (D8 row 6 lists N4.c, N4.h, N4.k, N4.m,
N6.1 to N6.3, so it omits N4.d; see contradictions).

Never built in any form:
- **N4.a, the fullscreen pass and image sampling as a primitive** (N4.a's box, in N2b). Seeds exist as
  `FULLSCREEN_VERTEX_SOURCE` (E4) and the core's background layer, not as one primitive (the Python background
  node it grew from was deleted in N5.2h). Consumers: the seven fullscreen
  transitions of N5.2a (Crossfade, Burn, Particle, Ripple, Slide, Warp, Wipe) and the background layer (N5.7a). No
  class stated.
- **Mixed-resolution soft layers with depth-aware upsampling** (N4.f2, D8 plus 4): bloom, reflection blur, wide glows
  and fog at reduced resolution; "lines, dots, rims, particles and UI stay at full resolution"; never whole-frame
  upscaling. Gate: stills reviewed by the lead and GPU time before and after; halos at depth edges are the risk.
- **Instanced screen-space quads in place of `gl_PointSize`** (N3.2, N3.2's box): Bubble ambient, Neon Lake's marks and
  Waveform's sparks use point sprites today; the Oscilloscope already draws instanced quads (Decisions D5.6 row 11).
  QRhi's `VertexShaderPointSize` is not portable (D3D has none).
- **Single draw with `ShaderDrawParameters`** (`gl_DrawID`, `gl_BaseInstance`, `gl_BaseVertex`) for a mode's small
  batches (plan note at item 8b, N3.2's box); D3D11 support is not stated.
- **Not yet built/admitted to production** (D8 rows 9, 10, 10a): HDR output, per-pass temporal upscaling,
  descriptor indexing, mesh shaders, ray tracing. Mesh shaders are now N6.7's **planned** Vulkan-native fidelity
  route, not an admitted runtime capability: existing-port parity retains its OpenGL twin, while newly authored
  post-flip Melt Pool and Concrete Rain may explicitly require Vulkan + `VK_EXT_mesh_shader` without one (operator,
  23 Nov; see D5.3 supersession and `Current_Plan.md` N6.7). The other low-potential candidates still need admission.

### Candidate consumers beyond today's modes (item 9; SMP deferred)

New modes (`Current_Plan.md` item 9) are built on the native core only: Reactive Liquid / Melt Pool (section 7.2,
S3D-3, S3D-4, S3D-5, S3D-2: N6.2, N6.1, N4.d, N4.c), Concrete Rain (section 7.3, same four), Usu Moonscape (section 7.4,
"plus S3D-6", i.e. N4.h, with character and world foundations S19 to S27 that are not primitives of this catalogue).
Expanded Visualizer M6 (4K acceptance) waits on N4.f2 for Waveform Ribbon and Extruded Bubble (item 8b, N4.f2's box).
**Future-only SMP consumers** (not current item 9): host-agnostic native rendering remains a retained contract,
and N6.1 might eventually serve SMP surfaces. There is no admitted SMP consumer, shader, renderer or deadline;
its source/host contract stays in Future_Work §2.5 and SMP plan 02.

## 6. How to read an entry's numbers

Costs in sections 3 and 5 are from `Scene3D_Resources.md` and the Decisions; they are RTX 4090 figures at the sizes
stated, unless an entry says otherwise. Per the Lessons (lines 155-173): GPU cost is `GL_TIME_ELAPSED` over at least 90
frames reported as median and p90 with a flush after every frame; before and after are loaded side by side in one
process, never across sessions; differences of tens of microseconds between processes are GPU clock state.
Per-pass attribution on the native side needs the N2.6 timer.

## 7. Important to note

### Cross-cutting lessons (binding; Lessons section line 149 onward)
- **Measure the right thing**: production runs PyOpenGL with error checking off (`rendering/gl_error_policy.py`);
  harnesses default to on. Count GL calls per frame; every PyOpenGL call also runs `glGetError` (about 4 microseconds).
  A raw setter costs the same as a checked one; cut calls instead.
- **No `glBlitFramebuffer` resolves**; render into texture attachments and resolve in the reading shader.
- **State fences**: the transition host restores texture units 0 to 2 only; a renderer using unit 3 or above hands it
  back (Lessons lines 311-312). Image units go through `bound_image`. `restore=False` only for scenes that own their
  whole frame.
- **Compute needs its barrier tested** by order and bits (NVIDIA hid a missing one); the writer issues it.
- **Determinism**: GLSL randomness is the integer hash with a CPU mirror checked on the GPU (**R-94**; float
  `fract(sin())` hashes seam). The index entry `R-94` is cited in `Transitions.md:142,205` but has no file in
  `Docs/Historical_Bugs/` (checked by glob, 12 Nov): treat as **unverified**.
- **64-bit**: no shader uses a 64-bit float (D4; Vulkan's `shaderFloat64` is optional): decisions of record are made
  once on the logical side in fp64 and published; ever-growing per-member quotients are rebuilt from float pairs with an
  exact two-product (Veltkamp halves, `precise`, never `fma` because `qsb`'s HLSL turns it into `mad`); check every
  target's baked source (Lessons lines 242-252; `tests/test_extruded_bubble_drift_precision.py`).
- **Look-first**: judge at native-pixel zoom beside the reference; stochastic jitter needs real photos; a population
  sized by a continuous count fades its edge across a band of members and is a rate-capped follower, never a beat
  follower (Lessons lines 210-213, 269-270).
- **Reality vs lab**: offline speed is not live speed; the logical tick's GIL-held Python stalled the render thread
  (Lessons lines 256-260). Judge a mode under `tools/visualizer_live_check.py --load game60` (lead only, ten minutes
  at most, only after the operator's yes). Viz hitches come from single GIL-holding C calls (memory "Viz hitch = GIL-held
  C calls").
- **Directions**: a direction label names where motion starts and the way it travels; `test_transition_direction_labels.py`
  renders every labelled direction (Lessons lines 324-333).
- **Shadows**: the rejected Extruded cast shadows stay rejected; do not reuse a translated top cap as a cast
  (`Scene3D_Resources.md:14`; R-125 to R-128).

### Portability (what a primitive must satisfy to bake)
- **Bake targets**: SPIR-V, GLSL 430, HLSL 5.0, MSL 1.2 (`Scene3D_Resources.md:300-301`; `Current_Plan.md` item 8b, N1's boxes).
  GLSL ES is **not** a target (removed by N1.7, 12 Nov). `.qsb` bakes for every backend, not `--glsl 460` only
  (item 8b, N1's boxes). A scalar half-float storage image is `r16f`.
- **No 64-bit types** in any shader on any backend (D4).
- **Reserved block bindings**: 16 `SCENE3D_COMPUTE_BLOCK_BINDING`, 17 `SCENE3D_CONVENTIONS_BLOCK_BINDING`, 18
  `SCENE3D_PASS_BLOCK_BINDING` (`rendering/gl_programs/scene3d.py:1035,1040,1046`); the per-frame uniform block sits
  on 15 (`scene3d/uniforms.py:30`). Samplers, images, storage and blocks share one binding namespace on Vulkan; in
  OpenGL a texture or image unit is that number (`Scene3D_Resources.md:296-299`).
- **No loose uniforms** in a portable program: one std140 block per program (N1.6); C++ packs from reflected offsets,
  never hand-computed ones (N0.3 rule 5); `vec3` aligns to 16, scalar arrays have a 16-byte stride.
- **Conventions**: core-owned targets are top-left, Y down on every backend; matrices stay in OpenGL form from one
  owner (`core/settings/framed_camera.py:286-289`) and are corrected once at upload with `clipSpaceCorrMatrix()` (N0.3
  rule 1); front face is one function of handedness and `isYUpInNDC()`; no hand-written `gl_FragCoord` arithmetic, no
  `ndc * 0.5 + 0.5`; `gl_VertexID` and `gl_InstanceID` read `srpssVertexIndex` and `srpssInstanceIndex`
  (`rendering/gl_programs/conventions.py:58-70`).
- **Formats**: no `RG16F`, `RG32F`, `R11G11B10F` in QRhi's list; widen to RGBA16F/RGBA32F (costs 2 times the bytes per
  texel) unless a target's measured cost justifies D5.3's formats service (Decisions D5.6 row 13). RGB10A2 is unorm and
  never a substitute. The native velocity is two R16F attachments (Plan, formats box).
- **Point sprites and geometry shaders**: use instanced quads and per-face draws (E14, E23).
- **Pipeline state is data**: no state setters in a mode; each state combination is a pre-built pipeline (D5.6 row 16).
- **Depth**: window depth in [0, 1] after the correction; reverse-Z is not proposed (Decisions line 1461).

### The framed camera standard
`core/settings/framed_camera.py` is **the standard physical camera for framed 3D Visualizer modes** (its docstring:
operator 2026-10-24; Extruded Bubble's camera is the standard). A mode declares a `FramedCameraSpec` (pivot, orbit
distance, pitch and yaw mapping, admitted eye box, optional floor or ceiling) and shares everything else: orbit axes,
the orbit, pan and dolly baseline, bounds, flight, reset, and the GLSL projection. Specs live in
`core/settings/neon_lake_camera.py`, `core/settings/extruded_bubble_camera.py` and `core/waveform_ribbon_scene.py`,
registered in `core/settings/visualizer_mode_registry.py:400,441,473`. Perspective is the only projection (Orthographic
removed 5 Nov 2026). The horizontal view is capped at 90 degrees by reducing the vertical view, never stretching edge
content (`framed_camera.py:32`). No per-mode cameras and no copied controllers (memory "Framed camera standard";
`Scene3D_Resources.md:16-25`). The native core takes one camera owner: the worker publishes the finished camera and
the renderer builds none (D5.5; N0.4's remainder box; test "no perspective or tangent construction in the native
sources").

### Stale text still open

The contradictions this catalogue found on 12 Nov were settled by the night audit of 12 Nov (closed 20 Nov; in git
history); the catalogue cites the plan by item and box name (line numbers
drift). One stays open until the flip:
- `Scene3D_Resources.md:3-5` ("All admitted operations require the validated OpenGL 4.6 context") and the opening
  "retained Quick transition and visualizer hosts remain their scenes' render owners" describe the Python path
  only; the native core's host adapter (D5.1) changes that, so the sentence needs a "today" qualifier at the
  flip.

### Unverified in this catalogue
- Whether every "consumer" list is complete: it comes from import greps of `rendering/` (12 Nov); consumers through
  dynamic registries (transition discovery) could be missed.
- Test names beyond those grepped or globbed; test coverage of N4.g's edge field is by `test_qtquick_edge_bloom.py`
  only (no dedicated `test_scene3d_edge_field*` file exists in `tests/`).
- Whether `rendering/gl_programs/lighting.py` is scheduled into an N1.6 group (it carries loose uniforms).
- SMP consumers of any primitive; the plan names only N6.1's "SMP surfaces".
- Every figure copied from `Scene3D_Resources.md` and the Decisions was not re-measured.
