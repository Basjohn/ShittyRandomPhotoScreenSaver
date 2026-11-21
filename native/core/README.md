# The native core: `_srpss_native_core`

The product's native module (`Current_Plan.md` item 8b, N2; decision D5.7 in
`Docs/Future_Work/Native_Core_P3_Decisions.md`). `native/spike_p1/` beside it remains historical evidence with no
build selection; current host and composite proof lives here.

- `CMakeLists.txt`, `build.cmd`: the build. Compiled only by `.github/workflows/native-module.yml` on GitHub (its
  default source); never on this machine. `build.cmd` is the workflow's one CMake invocation.
- `src/`: the C++ module. `abi.h` holds the ABI that `rendering/native/loader.py` speaks (`EXPECTED_ABI`).
  - `host_adapter.*`: the host adapter (D5.1): the Qt Quick window host and the hidden host (a render control on the
    core's own render thread) behind one interface.
  - `frame_driver.*`: the frame driver (D5.2), connected in C++ to each window's `beforeRendering` with a direct
    connection; it records the core's work for the frame there and releases on the render thread.
  - `conventions.*`: N0.3's decided conventions (F1 to F3): the upload correction of a core-owned target, the matrix
    corrected exactly once, the front-face rule on the corrected matrix, the target's conventions block.
  - `targets.*`: the core's render targets and Qt 6.12.0's rules for them (preserving, primed on Vulkan).
  - `probe_pass.*`: the trivial core pass a harness switches on (the frame edge, the correction and the readback
    orientation end to end); nothing creates it otherwise.
  - `composite.*` (N2.4, D5.2): what the core draws reaches the window as a scene-graph texture node with a material of
    ours: texels one to one (texelFetch at the item's integer device pixel), the card's coverage (the clip path Python
    resolves, tested at each texel's centre; skipped only for an admitted overflow), the quarter turn, Qt's opacity.
    Its geometry comes from `rendering/native/composite.py`.
  - `surfaces.*`: the composite's target (owned by its node, on the render thread) and the per-window registry the
    frame driver records from; a surface records only when its content changed (nothing at rest).
  - `gpu_timer.*` (N2.6, D8 plus 2): the per-pass GPU timer in the frame driver: each pass bracketed whole, outside
    any render pass, through `beginExternal` (raw timestamps on Vulkan, `GL_TIME_ELAPSED` on OpenGL), QRhi's
    whole-frame figure where the host's QRhi has timestamps (the only figure on D3D11 and D3D12); results read latched,
    never waited for. Off, the driver holds no timer and no query object. `rendering/native/gpu_timing.py` writes the
    figures into the frame trace.
  - `load_pass.*`: the timer's known-cost pass (N full-target draws of a fixed fragment loop), a harness's only.
  - `packet_reader.*` (N2.3, D1 and D2): the core's one consuming reader of a Visualizer frame stream, on its own view
    of the named mapping (retire never waits; the last pin unmaps), the accept-edge acknowledgement, the non-consuming
    head read, the drop edge's watermark, the transport rule's refusal at the slot head. `frame_abi_generated.h` is its
    layout, mode codes and record tables, generated from `core/visualizer_engine/packet_abi.py` and `native_schema.py`
    by `tools/native_frame_abi_header.py` (never edited by hand). Its first consumer is N2.5's Spectrum, at the item's
    sync on the render thread; `pause_in_copy` is D1's "close during copy" hook (a harness's only).
  - `program_blocks.*` (N2.5 round 4, **the standing port rule for every mode**): a runtime shader's uniform block,
    reflected by name (`BlockLayout::reflect`) and packed generically (`BlockValues`): `set(name, numbers)` from any
    name -> value source (a Python settings dict through `setJson` now; a record's named fields later, N2.9), at the
    member's reflected offset, type and array stride (std140: a scalar array's stride is 16 when the reflection says 0),
    ints as int32 (uints and bools as uint32), floats as float32 rounded to nearest. An unknown name, a wrong size, a
    value without a defined conversion (not finite, beyond its int type) or a write past the block is refused with a
    reason and writes nothing; `unfilled()` names every member nobody set, and always a member it cannot pack (mat2,
    mat3, a struct, a multi-dimensional array: audit 14 Nov, L2). `packRecordField` packs a frame record's field into
    the member of the same name (N2.9). A port therefore writes:
    (A new mode skips the port entirely: "How a new mode is built" below.)
    1. its fragment shader once, in `widgets/spotify_visualizer/shaders/` (the Python renderer and the core draw the same
       file), baked by `tools/regen_qrc.py --shaders` into `<file>.qsb` beside it (the conventions splice included; the
       same staleness check as the Qt Quick packs) and handed to the core as bytes at run time
       (`rendering/native/program_values.py` `mode_fragment_pack`): **no module build for a shader change**;
    2. one Python function giving every Settings- and card-derived member by name, from the spec and the card, with the
       Python renderer's own arithmetic (Spectrum: `spectrum_settings_values`), sent when it changes (nothing per frame at
       rest);
    3. C++ only for the per-frame or simulation arithmetic, setting its members by name through the same `BlockValues`
       (Spectrum: `kSpectrumFrameMembers`).
    A new Settings-only uniform is a shader line, a spec entry, a line in step 2 and a bake: no C++, no build round.
  - `spectrum.*` (N2.5): Spectrum on a composite's surface, the first port under that rule. Its program
    (`SpectrumProgram`) is the product's `spectrum.frag` pack handed over at run time (`composite_spectrum_program`; the
    module's compiled-in copy remains only as the harness's negative control) and its Settings-derived members by name
    (`composite_spectrum_settings`); the C++ fills the per-frame members from the record (bars, peaks, the bar layout that
    follows the bar count, the clock's hues, the play state), ported line for line from the Python renderer
    (`spectrum_block`, GPU-free, for the byte-for-byte test). The stream is bound by its mapping name from the GUI thread,
    read at the item's sync on the render thread, and a retired stream is released there (the render-thread retire job,
    also at the node's deletion). Python face: `rendering/native/spectrum.py`; the product route:
    `rendering/quick/visualizer/native_route.py`. Its settings are packed once when they change and kept across a new
    program (refused when they do not fit it).
  - `mode_schema.*` (N2.9): a mode's frame schema handed over at run time (`RuntimeSchema`): the Python table in the
    compiled table's row shape (`rendering/native/mode.py` `schema_table_entry`), validated (a native id, aligned and
    non-overlapping fields inside the record, range rules on u32 scalars only), its fingerprint recomputed, never
    replacing a compiled schema. The packet reader admits it beside `frame_abi_generated.h`'s table, which keeps only
    the schemas a hand-written consumer reads.
  - `mode_content.*` (N2.9, widened by N4.a): **generic mode content**, a mode or a fullscreen pass drawn from data
    alone, in the product fullscreen shaders' shape. `ModeProgram`: one to eight full-target passes, each a fragment
    pack, a blend (replace, alpha, premultiplied, add) and its samplers, drawn in order after a clearing draw with the
    core's triangle (`shaders/mode.vert`). A pass declares one std140 block of its own (any name, any binding but 17),
    optionally the conventions block, a vec2 at location 0 named `v_uv` (the Visualizer quad's uv, y down: the ITEM's
    oriented uv, from the card's `window_from_target` and `item_from_window` rows per vertex, so the product 2D shaders'
    `fc = v_uv * u_resolution` is the Python renderer's at any origin, ratio, rotation and backend; the target's uv only
    with no card: audit N29 round 2, M6) or `vUv` (the item quad's, y up, over the target: the fullscreen transitions),
    and `sampler2D`s, each bound by name to one of the item's textures (N4.a, "Samplers and textures" below); anything
    else is refused. One rule fills the block by member name from exactly one of three sources: the core's conventions
    (`kModeCoreMembers`, mirrored as `MODE_CORE_MEMBERS`: what the Python renderers take from the card per frame, read
    from the item's card and the target, each row with its own values: round 2, L6), the settings, and the record's
    fields.
  - `stream_source.*` (N2.9 round 2): what every mode item shares. `StreamSource`: the bound stream (bind, retire,
    the render-thread retire job, the accept edge with the admission rule, the state report) under `SpectrumSource` and
    `ModeSource`. `ContentLatch`: a content whose pipelines fail to build fails closed for the same key (recorded once,
    nothing created again) and is tried again when the key changes (the QRhi, the target's generation, the program,
    the settings and the stream; not the card, which no pipeline reads) or, bounded, after a run of held records
    (round 2, L4). A target the content never wrote is cleared to transparent by the surface (never undefined texels);
    a frame it did draw stays through a failure, for the route's fade (round 2, M4). A refused frame (a value with no
    defined conversion) never blanks the card: the last drawn frame stays and the refusal is counted with its reason.
    An unbound stream keeps its last frame for the fade; a new stream clears it (round 2, L3). The status
    (`composite_content_status`: draws, failures, the run of refused frames, failing) is the route's failure edge
    (M4, M5); the reader's state is copied, never built as JSON, on the render thread (L2).
  - The product modes on it: Spline Curve (`devcurve`, N5.1; its record `core/visualizer_engine/devcurve_native_schema.py`,
    its settings `devcurve_settings_values`), drawn through the Visualizer's route (`native_route.py`
    `GENERIC_MODE_SETTINGS`: one generic item per Visualizer item, its program retargeted by mode).
  - Python faces: `rendering/native/mode.py` (`NativeMode`), `rendering/native/spectrum.py`; a composite item hides
    and shows by a fade (`fade_ms`) and reports its window's framebuffer from Qt's own swapchain or redirect target
    (`window_pixels`), as its own synchronisation read it on the render thread: nothing before it, nothing while the
    window has been resized since (round 2, L1 and M3; the route waits on the window's `afterSynchronizing`).
  - `vulkan_context.*`: D6, the process's Vulkan instance and one device per window, given to Qt Quick; since N3.8 the
    device's second queue of Qt's graphics family and its job service, stopped first by the device's destruction.
    N3.6, the device loss: Qt's recovery re-adopts the device it was given, so the host's `sceneGraphInvalidated` slot
    (the render thread, the lost QRhi still alive) logs the lost device's `VK_EXT_device_fault` detail once, makes a new
    device and gives it to the window (`giveDeviceTo`, `setGraphicsDevice`) before Qt's next QRhi; the lost one is
    destroyed once Qt's QRhi on it is gone (a window: its next `sceneGraphInitialized`; the hidden host: in its own lost
    path, `HiddenHost::State::recover`, which also rebuilds Qt's QRhi through `QQuickRenderControlPrivate::resetRhi`).
    Every core object is made again by its owner (the items' nodes and their streams' last records, textures and
    meshes through the lost edges). The proof: `python/device_loss_check.py` through the harness-only forced loss.
  - `job_service.*` (N3.8, D9 "As built (N3.8)"): the async job service, one per Vulkan device: a thread and a QRhi on
    the job queue made at the first job, parked on a wait condition at rest; upload jobs that own their pixels; the
    ticket latch (published by compare-and-set, then a queued frame request to the item); cancellation; outputs released
    by the job thread once Qt's frames that sampled them completed (`surfaces.*`' window retire list, stamped with frame
    edges); teardown abandoning the job in flight. A scripted backend runs it GPU-free (`job_service_self_test`).
  - `item_notifier.*` (N3.8): how the render and job threads reach an item on the GUI thread (a queued `update()`, the
    owner's lost-texture edge) without ever touching a deleted item.
  - `backdrop.*` (N5.7b, D7 points 2 to 6 "As built (N5.7b)"): the card-material backdrop pyramid, level for level the
    Python pyramid's (`rendering/quick/render/surface_backdrop.py`), built from the window's background layer by the frame
    driver right after the layer, only in the frame the layer drew a new frame (the surface's drawn generation) and only
    while its item is not parked; its item is the texture provider `MaterialSurface` samples unchanged.
  - `scene_targets.*` (N3.1, decision D14): the scene targets a program declares as data, owned by its content: a
    surface-sized or explicit-size target of 1 to 4 colour attachments (RGBA8, RGBA16F, R16F, R32F) and an optional
    D32F depth, allocated in 64 px buckets (grown at once, shrunk only two buckets below, at the size edge), the content
    at the allocation's image rows `[H-h, H)` (the Python renderer's GL bottom-left; `contentViewport` gives QRhi's
    viewport per backend), cleared by a draw, primed for the load on Vulkan (rule C for colour and depth), the capture
    step (Python's `SceneTarget.background()`), the sample request clamped to the device's list (the count reported
    is the count created), multisampled colour resolved by QRhi (only what is read) and a read multisampled depth by
    the core's nearest resolve (D14 point 10), released with the content. Counted in `composite_live`
    (`scene_targets*`, `scene_target_nearest_resolves`).
  - `mesh_buffers.*` (N3.2, decision D15): a program's geometry as data, owned by its content: meshes (interleaved f32
    vertices with an optional per-instance stream, `Immutable`, uploaded once at the first record that draws them,
    never again at rest; the built-in `quad` only for a program that draws it), streams from record `f32` fields
    (instance: a `Dynamic` vertex buffer by the fast path; storage: a `Static` buffer by `uploadStaticBuffer` from a
    `QByteArray` kept across records; indirect: `Dynamic` commands), the block arena (every block of the content in one
    `Dynamic` uniform buffer at `ubufAligned` offsets, written whole once a record by the fast path, bound with dynamic
    offsets), batched draws (one multi-draw with `gl_DrawID` where the device reports the features, else one draw a
    batch at its dynamic offset) and the harness controls. Counted in `composite_live` (`mesh_buffers_*`, the record's
    render-thread time among them).
  - `compute_passes.*` (N3.3, decision D16): a program's compute entries and storage, owned by its content
    (`ModeStorage`): storage buffers (`Static`, usage storage plus vertex or indirect where a draw reads them so) and
    storage images (2D and 3D, RGBA8, RGBA16F, RGBA32F, R16F, R32F), created zeroed (a buffer by the core's clear kernel
    `shaders/storage_clear.comp`, an image by one upload of zeros), a resized buffer keeping its prefix through the copy
    kernel `shaders/storage_copy.comp` (QRhi has neither a buffer clear nor a buffer copy), kept across pipeline rebuilds
    and programs that declare them the same way; each compute entry recorded as its own QRhi compute pass only when its
    trigger has new work (`frame`, or a record `u32` field), `u_srpss_compute` telling the shader (trigger, last trigger,
    fresh, dispatches); every barrier QRhi's, from each binding's declared access, checked against the pack's
    qualifiers. The harness readback and controls (`compute_control`). Counted in `composite_live` (`compute_*`).
  - `post_stages.*` (N3.4, decision D17): transparency and post-processing as stages of a program, each absent unless
    declared: the device gate (`transparencyGate`, from the core's own device facts; N3.1's per-attachment check reads
    them too, `perTargetBlendReal`), the bloom chains (four RGBA16F textures, one a level, never `generateMips`), the
    defocus steps (the read level's texture; the layer's mips by QRhi's `generateMips`, the read level capped by
    `defocusReadLevelCap`), the core's stage shaders (`scene_oit_resolve*`, `bloom_*`, `composite_*`, `defocus_*`, each
    held to its Python source by `tests/test_native_post_stages.py`), the counts (`composite_live`'s `stage_*`, the
    record's render-thread time among them) and the harness controls (`stage_control`). `stage_pipelines` aggregates
    owned pipeline, sampler and binding wrappers, including failed partial builds until retirement; textures/storage
    have their separate counts. The transparency targets and
    the mipped layer live in `scene_targets.*`, the steps in `mode_content.*`'s record.
  - `thread_probe.*`, `process_counters.*`: the D5.4 probe and the lifecycle counters.
  - No STL container, lock or function wrapper: their code is in `msvcp140.dll`, which the module never imports (the
    loader's runtime rule); Qt's types instead.
- `shaders/`: GLSL 440 sources (`.vert`, `.frag`, `.comp`), each baked by PySide6's `qsb` for every shipped backend
  and embedded in the module; the workflow's staging requires one `.qsb` per source. `srpss_conventions.glsl` is the
  production conventions include (`rendering/gl_programs/conventions.py`), spliced in at `//@srpss_conventions` by
  `cmake/compose_shader.cmake` before the bake.
- `python/import_check.py`: the GPU-free check the workflow runs after the compile, through `rendering.native`.
- `python/frozen_probe.py`: N2.1's frozen probe, the entry of a separate Nuitka build
  (`scripts/venv/build_native_core_probe.ps1`) that loads the module the way the frozen product will.
- `python/host_check.py`: N2.2's proof (hosts, frame driver, probe, lifecycle, validation; `probe_analysis.py`,
  `vk_validation.py`). `Docs/Reference/Harness_Index.md` has the command.
- `python/composite_check.py`: N2.4's proof (texels one to one, plan 1C.4's clip contract on the native item in every
  display style, overflow held to the display rect, the window round, validation; `composite_analysis.py` and
  `tools/card_clip_contract.py`, the contract's one reading).
- `python/packet_reader_check.py`: N2.3's proof (bit-for-bit parity with the reference decoder on the shipped clip,
  the adversarial table with each case's negative controls, the in-place race, D1 and D2; GPU-free).
- `python/spectrum_check.py`: N2.5's proof of the native Spectrum item (uniform parity with the Python renderer at the
  widened run set, the item's contract with D1's close during copy, pixels against the Python renderer on OpenGL and
  against native OpenGL on Vulkan).
- `python/generic_mode_check.py`: N2.9's proof on the harness-only mode `python/probe_rings/` (blocks from the three
  sources against an independent packer with every refusal, the product's Oscilloscope and Spline Curve packs admitted
  and Bubble refused for its samplers alone, the reader by the runtime schema, the draw on OpenGL and Vulkan at dpr 1
  and 1.5 with shader, spec and simulation changes and no rebuild, a refused frame keeping the card, the content
  latch, the fade, nothing at rest, GPU time per pass, the framebuffer at 2560x1440 at 150 %; round 2: the item's
  v_uv at an odd origin in four rotations at dpr 1.5, the surface's clear of an unwritten target, a failing program
  keeping the frame, a run of refusals, an unbind keeping the frame, the fade's pixels).
- `python/devcurve_check.py`: N5.1's proof of Spline Curve (`devcurve`), the first product mode on the generic mode
  content (the module's blocks against the Python renderer's over the widened run set, byte for byte; the item's
  contract with nothing at rest and no Python thread state on the render thread; Settings and record changes on the
  same program; pixels against the Python renderer on OpenGL at dpr 1 and 1.5 and Vulkan against native OpenGL).
- `python/fullscreen_pass_check.py`: N4.a's proof of the fullscreen pass and image sampling (Crossfade's and Burn's own
  fragments between two real photos against the production GL host at nine progress values, Vulkan against native
  OpenGL, the seven transitions' and Bubble's packs bound and unbound, every sampler refusal, the textures' lifetime,
  the pass's GPU time at 2560x1440, nothing at rest).
- `python/job_service_check.py`: N3.8's proof of the job service (real 4K photos swapped while drawing in the hidden
  host; the job route against the in-frame control on Vulkan, frames identical, the hand-over keeping the previous
  photo, the render thread's cost per image change both ways, a superseded image cancelled, nothing at rest, the lost
  edge, teardown with jobs in flight, the job thread's probe, validation).
- `python/background_layer_check.py`: N5.7a's proof of the display's background layer (the photo drawn as a still by
  the fullscreen pass, through the product's route `rendering/quick/render/native_background.py`: OpenGL native equal to
  the Python presenter's frames on real photos at dpr 1 and 1.5 under the overscan placement, Vulkan within 1 level,
  photo changes through jobs with no pass at the hand-over, nothing at rest, the cost at rest against the protected
  retained-background path, the lost edge and teardown in flight) and of the N3.8 audit's M1 and M2 on a real render.
- `python/backdrop_pyramid_check.py`: N5.7b's proof of the backdrop pyramid (every level against the Python pyramid on
  OpenGL and Vulkan against OpenGL, on a dark and a bright photo at the overscan and the product's R-63 placement; each
  material's card stills against today's; the build's GPU time against D7's budgets at 2560x1440 and 4K; nothing at
  rest, one build per photo or dimming change, demand 0 building nothing; the owner's route; teardown).
- `python/scene_target_check.py`: N3.1's proof of the scene targets on the harness scene `python/scene_targets/` (the
  targets' readbacks against the Python owners driving the same fragments, rule (a), and Vulkan against OpenGL, rule
  (b); the captured depth and the depth loaded across the capture split; the second attachment and its clear; MSAA with
  the clamp; nothing at rest; the resize drag across bucket boundaries both ways; retirement; cost and the thread probe;
  `--rounds prime_control` on Vulkan alone: rule C for depth's negative control under synchronisation validation).
  `NativeMode.target_pixels()` returns every readable attachment/mip with its `level`, allocation `size` and nominal
  `content`. At nonzero mips, content is the base normalized rectangle projected outward to that level, bottom
  anchored and in bounds; filtering may blend across that nominal boundary. Readback callback storage is allocated
  once before enqueueing, retained by the existing shared readback lifetime, and never moved while pending.
- `python/mesh_buffer_check.py`: N3.2's proof on the harness scenes `python/mesh_buffers/` (a box mesh instanced over
  storage records with depth and the per-record front face, a static instance stream, sprites as instanced quads from a
  per-record instance stream, a vertex-pulled strip with blend MAX, 900 streaks over the built-in quad; rule (a) against
  the Python owners and rule (b) at dpr 1 and 1.5 within the tie budget; the sprites against `gl_PointSize`; the batched
  forms, sixteen passes and the indirect draw equal; firstInstance's control; nothing at rest; no allocation over a
  steady minute; retirement; validation; cost; `--rounds retarget`: fresh geometry, retained tails, compatible-layout
  allocation/generation guards, lost/recreated meshes and compute mesh/texture rebinding through the same child
  and validation owner (`mesh_retarget_check.py`, no separate CLI); `--rounds stream_ring`: QRhi's routes against the pair's floor, D15
  point 7). Optional `--rounds uniform_vectors` proves exact full-range uvec2/3/4 record uploads, actual last-component
  mutations and restoration using the existing readback/retirement owners (`uniform_vector_check.py`, no separate CLI).
- `python/compute_pass_check.py`: N3.3's proof on the harness scenes `python/compute_passes/` (Waveform's field, floor
  give chain and fog volume shapes, the drift's stateful buffer, the product's compacted population with its indirect
  draw, a write-after-read pair): every storage resource read back, rule (a) against the Python owners' compute calls
  and rule (b), exact; the qualifiers and their admission refusals; the triggers (no dispatch for a card, settings or
  readback re-record; the state against a CPU reference; the fresh dispatch and the lost edge of a node made again);
  copy and clear; nothing at rest; no object in steady records; retirement; synchronisation validation over consecutive
  records with the two controls' hazards in their own phases; cost against the Python path).
- `python/post_stage_check.py`: N3.4's proof on the harness scenes `python/post_stages/` (Extruded Bubble's shape:
  opaque with emission, a capture, three transparent discs, the resolve, a near layer and its defocus, bloom, the HDR
  composite; the Oscilloscope's: MAX blends and glow; an opaque scene with glow; a one-attachment owner for the sorted
  fallback): rule (a) against the Python stages (`SceneTarget`, `BloomChain`, `DefocusLayer`) under the shared pixel
  tolerance and rule (b), the defocus layer's every mip level; the analytic checks (inverted coverage, two draw orders,
  light past 1, no glow without emission, the per-sample resolve and its first-sample control); the gate's fallbacks by
  control and the defocus read level's cap; nothing at rest; a steady minute; retirement; synchronisation validation
  with each control in its own phase; cost against the Python stages; `--rounds defocus_cost python_defocus_cost`: the
  defocus step's cost split; `--rounds showcase`: the primitive's WebP).
- `python/timer_check.py`: N2.6's proof (off is free by count, a known-cost pass scaled N times and its empty-bracket
  control, QRhi's frame figure, latched reads in a real window with the waiting read as control, the frame trace and
  its report, the two forms against each other, validation; `timer_analysis.py`).

## How a new mode is built (N2.9; decision D12 in `Native_Core_P3_Decisions.md`)

No C++ and no module build while the mode is iterated to its mock and reactivity goals. `python/probe_rings/` is the
worked example (harness-only); a product mode does the same in the product's places:

1. **Its code.** Append the mode id to `core/visualizer_engine/packet_abi.py` `MODE_CODES` (append-only; run
   `tools/native_frame_abi_header.py`). A module built before keeps working: it reads the mode by its runtime schema
   and the face tolerates codes appended after it (`schema_table_differences`).
2. **Its simulation and record.** A Python simulation in the engine worker publishing one fixed-layout record per frame
   (`native_schema.NativeLayout.build` of `(name, kind, count)`; kinds u32, f64, f64x4, and N3.2's f32 arrays for streams; range rules on u32 fields).
   Its `NativeSchema` goes in the runtime registry (`native_schema._RUNTIME_SCHEMA_MODULES`): the Python transport
   knows it and the core receives it at bind (`NativeMode.bind(mapping, schema)`), so it never makes a built module's
   table differ. `_SCHEMA_MODULES` is for the schemas the module compiles (a hand-written consumer's); a mode is in one
   registry only.
3. **Its passes.** One fragment shader per pass in the product fullscreen shaders' shape (GLSL 440; `in vec2 v_uv`, or
   `in vec2 vUv` for the item quad's convention, and/or `#define SRPSS_CONVENTIONS_FRAGMENT` with `//@srpss_conventions`
   and the pixel from `fragPixel`; `sampler2D`s bound by name to the item's textures, step 4b), each declaring one
   std140 block of its own (any name, any binding but 17). Its members are filled by name: the core's conventions
   (`MODE_CORE_MEMBERS`: `uMatrix`, `uItemSize`, `uContentRotationQuarters`, `u_resolution`, `u_dpr`,
   `u_viewport_origin_px`, `u_quick_item_coords`, `u_fade`, `u_border_width`, `u_item_from_frag*`,
   `u_window_from_target*`, `u_target_px`, `u_scene_item`: the item's cover in the target, where Python's
   `SceneTarget` starts, read by the composite step, `u_scene_from_target*`: the target's pixel to Python's scene
   texel, the window's frame under a turned card whose composite declares `"scene_frame": "window"`), every record field named exactly as the field (an f64 a float, an f64x4 a
   vec4, a u32 an int or float under a range rule that fits it, a uint or a bool, an array the same length), and the
   settings. Baked by `tools/regen_qrc.py --shaders` beside the source (the harness bakes with the same baker at run
   time), handed over as bytes with the pass's blend (`ModePass`).
4. **Its spec, settings and card.** The controls in its spec (`core/settings/visualizer_mode_settings.py`) and one
   Python function giving every other member by name from the spec, sent with the program
   (`NativeMode.program(passes, settings)`) and again when Settings change (`NativeMode.settings`); the item as shown
   (`NativeMode.card(mode_card(...))`) whenever it changes.
4b. **Its textures** (N4.a, when a pass samples an image): see "Samplers and textures" below.
4c. **Its scene targets** (N3.1, when it draws into intermediates: depth, an HDR colour, a second attachment, a capture):
   `ModeTarget`s given with the program (`NativeMode.program(passes, settings, targets=...)`); a pass names its
   `target`, one `PassOutput` (write mask, blend) per attachment and its depth test and write; a `CapturePass` copies a
   target's colour and nearest window depth for later passes; a sampler reads `"<target>.<attachment>"`,
   `"<target>.depth"` or `"<target>.capture_colour|capture_depth"`. The sample request comes from
   `rendering.gl_programs.scene3d.scene_samples`; an explicit size follows its card through `NativeMode.target_size`.
   Read a target by its own pixel or by a uv over its allocation (`textureSize`): the content sits at the allocation's
   bottom rows, columns from 0. A multisampled target's read depth is the core's nearest resolve (D14 point 10:
   `shaders/scene_nearest.frag`, the minimum over the samples); an R32F attachment may declare `"resolve": "nearest"`.
4d. **Its vertex stage, meshes and streams** (N3.2, decision D15, when a pass draws geometry rather than a full-card
   fragment): a `PassGeometry` on the `ModePass` (its `.vert` pack baked like a fragment; topology `triangles` or
   `triangle_strip`; vertex and instance counts as numbers, `"mesh"`, or a record `u32` field or setting by name; its
   `mesh`, its `instance_from` (a mesh's instance stream or an instance stream), its storage blocks bound by name to
   streams, `cull` and `front_face` (`ccw`, `cw`, or a name choosing per record: N0.3 rule 4 on the matrix as the core
   uploads it, `conventions.front_face_clockwise`), an `indirect` stream with its `draw_count`, or a batched draw's
   `batches`/`batch_count` with an optional draw-parameters pack (SPIR-V and GLSL only)). Meshes by
   `NativeMode.mesh(name, vertices, RecordLayout, instances=, instance_layout=)`; streams (`ModeStream`) from the
   record's `f32` fields (the std430 bytes the Python renderer packs, verbatim). Only a storage stream keeps the bytes
   past its used length from an earlier record; an instance stream is drawn exactly its used records (its pass's
   instance count is the stream's used records, and any other count refuses the draw: checkpoint audit 4, H2). Every
   vertex, instance, indirect command and batch count is checked at the record against the buffer it reads, and a
   count past it refuses that pass's draw with its reason; a record's indirect commands are uploaded with their
   `firstInstance` written as 0 (audit 4, M1). The block's `uMatrix` is item pixels to the drawn target's clip space,
   corrected once; `srpssVertexIndex`/`srpssInstanceIndex` read the same numbers on both backends (`firstInstance` is
   always 0). Sprites are instanced quads (`//@srpss_geometry` after `//@srpss_conventions`: `srpssSpriteCorner`,
   `srpssSpriteClip`, `srpssSpriteCulled`; the sprite coordinate has `gl_PointCoord`'s orientation; the geometry marker
   is spliced by the Python composer, `rendering/gl_programs/conventions.py`, only: the core's own bake,
   `cmake/compose_shader.cmake`, replaces `//@srpss_conventions` alone), converted first in the Python renderer and
   judged against that conversion. Every
   block lives in the content's arena; a blend may be a full `BlendState` (`max`, `min` included). A record field fills
   exactly one of a block member, a draw count or selector, and a stream (a batched draw's table is read both ways).
4e. **Its compute** (N3.3, decision D16, when a step runs on the GPU: a field, a volume, a simulation, a population):
   `StorageBuffer`s and `StorageImage`s given with the program (`NativeMode.program(..., buffers=, images=)`) and
   `ComputePass` entries in the pass list at their place (each one compute pack, `.comp` baked like a fragment; its
   `bindings` by the shader's names, each with its access `read`, `write` or `read_write`, matching the shader's
   `readonly`/`writeonly`; its `groups` three counts or `over` a resource; its `trigger`, `"frame"` or a record `u32`
   field for a stateful step, which must never integrate twice). A draw reads a buffer as storage, `instance_from` (a
   buffer with a `layout`) or `indirect` (a buffer with `indirect=True`), and an image through a sampler (`sampler3D`
   for a 3D one). A stateful shader reads `u_srpss_compute` (a `uvec4`: trigger, last trigger, fresh, dispatches) and
   restarts its history when fresh; the owner hears of a lost state through `NativeMode.on_state_lost`. Images follow
   their surface through `NativeMode.image_size`. Nothing is read back in the product (the drift's pair self-check is
   the one named exception, D16 choice G).
4f. **Its transparency and post-processing** (N3.4, decision D17, when it draws order-independent transparency, glow,
   an HDR tone map or a defocused near layer): stages in the program, each absent unless declared. A
   `TransparencyTarget(name, of, borrow)` over a surface-sized scene target with depth; its passes write
   `SCENE_OIT_GLSL`'s accumulation and coverage at locations 0 and 1 and a borrowed attachment at 2 on (the core fixes
   the first two blends and depth tests against the owner's depth, never writing it), and each ships its `sorted_pack`
   (the same bindings, premultiplied colour at location 0 and the borrowed attachments after it, no `gl_FragDepth`): what
   a device the gate does not admit draws into the owner. A `TransparencyResolve` follows the target's passes, before
   anything samples the owner. A `BloomStep(name, "<target>.<attachment>")` makes `"<name>.glow"`; a
   `CompositeStep(name, form, scene, glow)` draws the surface with the core's composite (`overlay`, `overlay_glow` with
   `u_bloom_strength` and `u_hdr_exposure`, `opaque_glow`); a mipped `ModeTarget(..., mips=True)` with a colour and a
   circle (both RGBA16F, drawn premultiplied over and MAX) and a `DefocusStep(name, layer, onto)` with
   `u_defocus_radius`, `u_defocus_highlight` and `u_defocus_level` (Python resolves the level, `defocus.py`
   `_read_size`; the core refuses one past `defocusReadLevelCap`). Members are settings or record fields by the one
   rule; a stage is turned on or off by the program, never per record. On a device without `independentBlend` a pass
   writing its attachments with differing states is refused: the mode is not offered on that backend (logged once by
   Python).
5. **What is refused, with its reason:** a setting or a record field no pass declares (unknown); a member no source
   fills (unfilled); a name with two owners (a setting or a field naming a core member, a setting naming a field); a
   value of the wrong size or without a defined conversion (a refused frame keeps the last drawn one); a sampler the
   shader declares that the program binds to no texture (unbound), one the program binds that the shader does not
   declare (unknown), one bound twice or sharing a binding (doubly bound), one at binding 17 or at its block's binding,
   one that is not a `sampler2D`, a mip sampler over a texture set without mips; a pass that declares a separate
   texture or sampler, storage, a push constant, a second block of its own, a block at binding 17 or an input other
   than `v_uv` or `vUv` (a pass with its own vertex stage, step 4d, may read storage blocks bound to streams and take
   its vertex stage's outputs); a schema that is not a valid fixed layout or names a compiled mode. A program that does not
   take the current settings or textures is refused and the drawn one stays.
6. **Its route** (a product mode, N5.1): its settings function in `rendering/quick/visualizer/native_route.py`
   `GENERIC_MODE_SETTINGS` (`(snapshot, card) -> members`) and `"vulkan"` in its descriptor's `renderer_backends`; the
   route encodes its record by its runtime schema and admits its frames by the Python node's rule (`_admission_flags`).
   A mode with more than its one fragment pass (targets, streams, its own vertex stages: Bubble) also names its program
   in `GENERIC_MODE_PROGRAMS` (`(fragment pack, target sizes) -> {"passes", "targets", "streams"}`) and its
   explicit-size targets in `GENERIC_MODE_TARGET_SIZES` (`(snapshot, settings) -> {target: size}`): the route sends the
   program with the first settings, then each size through `NativeMode.target_size` only when it changes (never per
   frame), and its stream slot is whole 4096-byte steps of its record (`_slot_bytes`). Its harness is
   `native/core/python/devcurve_check.py`'s rounds with the mode's own pieces (`use_mode`; `bubble_check.py`).
   A mode whose stages a Setting turns on or off (the Oscilloscope's Glow: D17 choice E) names its program variants in
   `GENERIC_MODE_PROGRAM_VARIANTS` (`(the variant of a snapshot, variant -> {"passes", "targets", "streams",
   "unread"?})`): the route builds the variant's program at the bind and again only at the Settings edge that changes
   it. One record serves every variant: a variant that leaves a stage out names the record fields only that stage reads
   in `"unread"` (ABI 26; any other record field no pass reads is still refused). Its harness is
   `oscilloscope_check.py`; until its registration, its owner rule (a) runs through `oscilloscope_check.py owner`, the
   route's registration process-local.

### Samplers and textures (N4.a; decision D13 in `Native_Core_P3_Decisions.md`)

How a pass declares its samplers: in the program's declaration, beside its name and blend,
`"samplers": [{"name": <the shader's sampler2D>, "texture": <the item's texture>, "filter": nearest|linear,
"wrap": clamp|repeat|mirror, "mips": none|nearest|linear}]` (`rendering/native/mode.py` `PassSampler` on a `ModePass`).
Every `sampler2D` of the pack is bound exactly once; its binding is the pack's own (reflected), so the product shader
is unchanged. The fullscreen transitions bind `uOldTex` to `old` and `uNewTex` to `new` (linear, clamp, no mips: the
Python renderer's state); Bubble binds `u_ambient_texture` and `u_ambient_light`.

How a texture's lifetime runs (`ModeSource` holds the item's textures, `ModeContent` their QRhi objects):
1. **Sent** (GUI thread): `NativeMode.texture(name, pixels, (w, h), mips=False)`: RGBA8, rows top first, tight, at
   most 8 an item and 16384 a side. The core copies the pixels once (a new generation) and asks for a frame; a pixel
   copy not yet uploaded is counted (`composite_live`'s `mode_texture_images`).
2. **Taken** (render thread, at the item's sync): the copy moves to the render thread; the GUI side keeps none.
3. **Uploaded** (from the next record, before the passes): in the frame into the content's QRhiTexture (created at the
   first image; the same object for an image of the same size and mips; recreated, and the bindings that name it made
   again, for another size or mips), mips generated on the GPU when the texture asks for them; then the core's copy is
   dropped. N3.8 (D9): on a Vulkan device with a job service the render thread only hands the copy to an upload job
   (the job thread uploads it and its mips on the job queue into a texture of its own and drops the copy); once the job
   is published the content imports its output (`createFrom`) and the passes' bindings are made again over it (the
   pipelines kept). An item's changed textures commit together, when every one's job is done or failed (a failed job's
   copy is uploaded in the frame); until then the textures held are drawn. `in_frame=True` is the harness control of
   the in-frame form. Nothing is uploaded again until a new image (`texture_uploads`, `texture_jobs` and
   `image_changes` in the state; `mode_textures` and `mode_texture_bytes`, every level counted, in `composite_live`;
   `job_counts` for the jobs).
3b. **A still** (N5.7a, `NativeMode.still()`): an item with no stream (the background layer's photo). Its frame is its
   textures, settings and card; its program is checked against an empty schema (every member the core's or a setting);
   it records only when what it draws changed, so the record that hands a new image to its job keeps the target
   (`still_kept`; no pass) and the commit's record draws the new picture once.
4. **Retired** (render thread): a removed texture (`NativeMode.remove_texture`) is released at the next record, and the
   pipelines that bound it are rebuilt; a pass whose texture is missing is not drawn (the state's `last_reason` names
   it) and the target is cleared. Every texture goes with the content when Qt deletes the item's node (the render
   thread, the QRhi alive), so an item destroyed with its textures leaves no QRhi object, byte or copy behind.
5. **Lost**: a node made again (another QRhi, or the item at no size) has no copy to upload from; the owner's
   `NativeMode.on_textures_lost` callback is called once on the GUI thread with the names (N3.8: the edge; the state's
   `textures_lost` keeps the list), the item draws nothing, and its owner sends the images again. The product owner of
   a texture (N5.7a's presenter, N5.2a's transitions) keeps its pixels for that. A replaced or removed job output goes
   to the window's retire list and back to its job thread once Qt's frames that sampled it completed; the list asks its
   window for those frames itself (audit N38 M2), and the window's frame edges are counted once per frame whatever
   number of drivers sees it (M1). The destruction barrier waits for work in flight only
   (`NativeCore.pending_native_work`, `IN_FLIGHT_WORK`, M3): what live items hold is proved released by each item's own
   destruction.

A new GPU technique (sampling an earlier pass, depth, more targets, compute, a new resource) is a primitive with its own
C++ and harness, then used by every mode as data (sampling an image is that primitive since N4.a). Hand-written C++ for
a mode's simulation is admitted only after its goals are met and a measurement shows the hot path (Transitions.md,
"Where a mode's work lives on the native core").

The guards: CMake refuses a Qt SDK other than `requirements.txt`'s PySide6 pin; the module refuses to import under
any Qt but the one it was compiled for; `rendering.native` refuses a module whose Qt, ABI or MSVC runtime arrangement
does not match this process (`rendering/native/runtime_check.py`: no `msvcp140` import, the loaded `vcruntime140` at
least as new as the compiler), the MSVC runtime rule read from the module file before it is imported. Tests:
`tests/test_native_core_*.py`.

Build and fetch it (the lead; agents never build):

```
.venv\Scripts\python.exe tools\build_runner.py --mode github --run --select native_module
```

The module lands in `release\native_module\` of the checkout the command runs from; `rendering.native.load(Path(
"release/native_module"))` loads it from there. `Docs/Guides/GitHub_Remote_Build.md`, "The native core module", has the
rest.
