# Checkpoint audits, 21 Nov 2026

## Checkpoint audit 9 (fast-proof tools)

Scope: the merge 79a5d1fe7 (Current_Plan item 8b, "Audit the fast-proof merge"): `tools/pixel_tolerance.py`'s M1
groups and density, the cheaper judge's equal-verdict proof, the reference cache key, the native-only and
stream-player paths, layer L's coverage of positional members. Main at 79a5d1fe7 only; 5.5 s replays and unit tests
only (no 60 s replay). Every control below was run against a deliberately broken form or input, not reasoned.
Evidence: `.artifacts/evidence/native_core/fast_proof/20261121_audit9_*`.

### Medium

**M1. The reference cache key misses Python drawing code outside its three folders, and the harness's own mask
code.** `python_references._source_files` hashes `rendering/quick/visualizer/**/*.py`, the shader files of
`widgets/spotify_visualizer/shaders/` and the scene's `*.qml`. Not in the key: `rendering/gl_programs/conventions.py`
(its `SRPSS_CONVENTIONS_GLSL` and `SRPSS_GEOMETRY_GLSL` are spliced into every shader the Python renderer composes),
`widgets/spotify_visualizer/shaders/__init__.py` (the composer itself), `rendering/gl_programs/*` helpers,
`rendering/quick/qml/shaders/*.frag` and their `.qsb`, and the code that makes the reference's masks and frames
(`owner_render_parity.SceneMirror`, `content_backdrop`, `rule_a_masks`, `pixel_tolerance.translucent_by_backgrounds`).
The logical-digest check at use does not see any of these. Control run: one GLSL comment line added to
`SRPSS_CONVENTIONS_GLSL`: the composed `bubble.frag` digest changed (67f3d131 to feefe2ce), `renderer_source_hash`
did not (4f82b1ab both times), so a stale reference would be read. Fix at the owner: hash the composed sources of
every shader the renderer compiles (`compose_shader_source`), the modules the renderer imports (or a declared list
including `rendering/gl_programs`), and the mask and capture code; add the conventions case to
`tests/test_python_references.py` as its control.

**M2. The stale-reference path cannot finish on Windows.** When the native run's logical digests differ from a cached
reference, `native_parity` redraws and calls `python_references.store` into the same folder, whose `frames.bin` is
still open in the loaded reference's `StoredFrames` (it keeps its handle after the judge reads a frame).
`shutil.rmtree` fails with WinError 32, the run dies without a report, the stale reference and a `.partial` folder
stay, and every later run of that key takes the same path and dies again. Run end to end: a cached Bubble reference
made stale by one digest, then `owner_render_parity --native --mode bubble --runs bubble --references ...`: the
PermissionError on `frames.bin`; also reproduced in isolation (load, read one frame, store). Further, on that path the
first judge has already written the progress file with verdicts against the stale reference, and the rejudge runs
without `progress` and without `--judge-workers`. Fix: close the stored frames before re-storing (a `close()` on
`StoredFrames`, called by `native_parity`), or store into a new folder and swap; rewrite the progress file from the
rejudge; and a test that exercises the stale path.

### Low

- **L1 (adds to the open M1 remainder box of audit 8).** Besides the straight 65-pixel line split by two exact pixels,
  a one-level diagonal line of 60 split every 20 passes, and so does a regular lattice of 68 one-level pixels every
  4th pixel both ways (density 16 per window, groups of 1). Every 3rd pixel (36 per window) and two lines 2 px apart
  (32) fail. Recorded for the decision already in the plan; no bound changed.
- **L2. The equal-verdict proof does not cover alpha.** `tests/test_owner_render_parity_judge.py`'s synthetic
  frames are opaque on both sides, so `_judge_one` taking its delta over RGB only (a broken form) passes every test.
  The code as merged takes all four channels, like `levels`. Give the synthetic frames a translucent case.
- **L3. A native-only run without `--against` reports `identical: true` and `pass: true`** at the run and report
  level (`native_only`: `identical = pass = native_published > 0`). Its console says "no baseline", but the JSON
  reads as a proof. Report `identical: null` when nothing was compared.
- **L4. Layer L's positional members.** For Bubble `uMatrix` and `u_target_px` are outside L; a native block with
  `u_target_px` raised by 1.0 at input 100 passes L (run, as declared). The module's docstring says they are proved by
  "rule (a)'s mapping control and the pixels"; the mapping control exists for Spectrum only. For Bubble they are
  proved by rule (a)'s pixels on OpenGL (display and overscan placements) and by the stream player's rule (b) at the
  harness's one placement on Vulkan, so a Vulkan-only error at a fractional product placement is not covered. Say so
  in the docstring and the guide's coverage section. The other levels hold: one delivered setting raised by 0.25 at
  input 100 fails L at that input (settings level, `uGlowSpread`); one packed native block member raised by 1.0 fails
  at the block level (`u_dpr`). Neither is a standing control in `tests/test_native_record_identity.py` (only the
  record-level ulp and drop controls are); add both. Bubble's survey: native passes equal the declared three, no
  delivered setting skipped (27 compared), so the `name not in python` skip is unused today; report skipped names in
  the coverage so a future port cannot hide one.
- **L5.** `owner_render_parity.py --help` still says `--mode` draws "spectrum, devcurve".

### Held (controls run, all as expected)

- Ties joined into groups: with `joined = scatter` the split-line control in `test_native_bubble.py` fails; with the
  density reason removed, its dithered-patch control fails.
- Cheaper judge: edges read at ties only (not flips) fails the flips case of the equal-verdict test and
  `test_pixel_tolerance.py`'s flip test; wrap-around padding in `content_edges_at` fails four equal-verdict tests.
- Cache and workers: a 5.5 s Bubble run drawn and stored, then the same run read from the cache with
  `--judge-workers 2`: reports equal key for key (`20261121_audit9_r1_drawn`, `_r2_cached`).
- Native-only: against the full run's report, 549 of 549 hashes identical (`_r3_native_only_against`); against a
  copy with one hash changed at input 200, CHANGED at exactly [200] and exit 1 (`_r5_control_one_hash`); against a
  copy one frame short, CHANGED on the count and exit 1 (`_r6_control_short`); with no baseline, `identical` and
  `pass` true (`_r4_native_only_no_baseline`, L3).
- Stream player: layer L with `--deliveries` on the 5.5 s clip identical (359 compared frames,
  `_l_bubble_5s`); the player drew 359 frames on each API and rule (b) passed (6 hash-equal, `_player_5s`); with
  `--control position_nudged`, rule (b) failed on 330 of 359 frames and the Vulkan hashes changed from input 9 against
  the clean run while OpenGL's were identical, exit 1 (`_player_5s_control`).

## Checkpoint audit 10 (N5.1 Oscilloscope)

Scope: branch `worktree-agent-a652d2d5a77e690ff` before merge (`git diff main...` at 135db8abf; Opus High), core first:
`u_scene_item` (`sceneItemRect`) against Python's `item_pixel_rect`, the item-anchored bloom triangle, the three
composites' glow and dither keys, `StreamSource::syncStream`, ABI 26's `unread`; then the record and shared values,
the route's program and `oscilloscope_check.py` with its controls. Run on the branch's ABI 27 module, 5.5 s replays
and unit tests only (no 60 s replay), at most two heavy processes at once. Probes are scripts in
`n5_1_oscilloscope/20261121_audit10_scripts/` (run from the repository root; `audit10_probe.py` wraps
`oscilloscope_check.py`, choosing its probe by a keyword in `--label`). Evidence:
`.artifacts/evidence/native_core/n5_1_oscilloscope/20261121_audit10_*`.

Verdict: the merge is safe for the product (the port is unregistered, N3.4's parity passes on ABI 27), but ABI 27's
anchoring is not yet the bloom contract: the Trace display, a shipped Choice, fails owner rule (a) at 8 levels (H1),
and the harness could not see it (M1).

### High

**H1. The native target holds other light past the item's edges than Python's `SceneTarget`, and the bloom spreads it
into the item: the Trace display fails owner rule (a).** Owner smoke on ABI 27, `oscilloscope_check.py owner --offers
--runs oscilloscope:osc_display=0 --seconds 5.5 --placements display` (`_audit10_owner_trace/`): 546 of 549 inputs
differ, 429 frames fail rule (a), at most 8 levels, worst frame 822 ties and 219 flips. The difference is a glow wedge
along the card's right edge, Python brighter (`..._input53_difference_x64.png`), with dither-scale noise along the left
edge. The agent's owner smoke ran `--runs oscilloscope` only, which is Ring (variant b is Phase); Trace is the one
display whose beam runs past the item (by the reach, its round caps under the card's clip). Cause: Python draws its
target through the window's viewport with no scissor (`SceneTarget.begin`: `glViewport(vx - x, vy - y, vw, vh)`), so
the overrun right of and above the item lands in its allocation's slack (`_bucket(item) - item`, grow-only) and is
bloomed back into the item, while the overrun left of and below the item is cut at the allocation's origin. The native
target is the quad-aligned surface (the item plus 0 to 2 pixels a side): it holds a pixel or two of overrun on every
side and nothing further. ABI 27 anchors the grid's phase (correct, see Held), not what the target holds past the
item. In the harness: the offsets round over every sampled frame (`_audit10_allsamples_dump/`, its per-frame lines):
only the Trace run fails, at every placement, odd and even alike, 6 to 29 levels in the item's first and last 2 to 10
columns, rows of the trace, against its own rect and against Python; Ring and Phase stay within 2 levels.
Consequences: Python's own edge glow depends on its allocation's slack (an item a whole number of 64-pixel buckets
wide has none, and a target that once grew keeps more), so the oracle itself moves with the bucket; and D12's limit
"the levels are Python's sizes while the surface stays in the item's 64-pixel bucket" is not the real one: targets in
another bucket in either axis pass (Held), since every level of a 64-multiple allocation pairs the same pixels; what
moves the glow is the light the target holds past the item. Every bloom consumer whose passes draw past its item
inherits this. Decide one: (a) C++ (ABI 28): the target is Python's own, its origin the item's pixel and its
allocation Python's (the bucket of the item's rect, grow-only), drawn through the window's viewport so the overrun
lands where Python's does; (b) Python's `SceneTarget` scissors its passes to its rect (no overrun anywhere; changes
the frozen pictures of scene-target modes that draw past their item) and the core scissors its scene passes to
`u_scene_item`. Proof: owner rule (a) on the 5.5 s replay for every display (`--offers`), and the offsets round over
every sampled frame.

### Medium

**M1. `oscilloscope_check.py` cannot see H1.** (i) The offsets round places the first `OFFSET_SAMPLES` = 16 sampled
frames per ratio, all from variants a (Ring) and b (Phase); the Trace run is never placed. (ii) Its Python reference
is drawn through a viewport the item's size (`spectrum_check.python_references`), which cuts the overrun on all four
sides, unlike the product's `SceneTarget`, so rule (a) at an offset is judged against a picture the product never
draws. (iii) The owner smoke ran Ring alone. Fix: the offsets round over every sampled frame (or each run's first
samples); the reference drawn as the product draws it (a window larger than the item), or the round says it is not
the edge's oracle; and the box's owner smoke with `--offers` before the box closes. Control: the Trace owner run
above fails on ABI 27.

**M2. Two owners of the item's pixel rect.** `sceneItemRect` re-derives `item_pixel_rect` from the card's doubles
with a fixed 1e-3 snap and no viewport clamp; Python reads Qt's float32 matrix, snaps only within that matrix's
rounding and clamps to the viewport. They disagree when an edge lies about 1e-4 to 1e-3 of a device pixel off a whole
pixel: `snap_probe.py` (420 x 280 at dpr 1.5, origin 46 + f, 44 + f): f = +-0.0002, 0.0005 and 0.0009 all differ
(Python (2, 0, 631, 421), (2, -1, 630, 421) or (1, -1, 631, 421) against the core's (2, 0, 630, 420)); f = 0 and
0.25 agree. A one-pixel origin disagreement is the 4 to 5 level phase error ABI 27 removed. The test
`test_the_scene_item_is_the_items_own_cover_in_the_target` pins hand-computed rects, none near a whole pixel, and
derives nothing from `item_pixel_rect`. Fix at one owner: the core applies Python's snap and clamp exactly, with a
test whose every expectation comes from `item_pixel_rect` over near-integer fractions (or the rect travels in the card
from one Python computation).

**M3. Turned scenes are not anchored.** Python's turned Scene3D modes (`orient_visualizer_scene_frame`: Waveform
Ribbon, Extruded Bubble, Neon Lake, Extruded Spectrum) draw their target in the turned virtual viewport: its rect,
bloom grid, glow read and dither key are in turned coordinates, and `_ORIENTED_COMPOSITES` turn each output pixel back
(`sceneTexel`). `u_scene_item`, `bloomTriangle` and the three composite forms are physical only, and the core accepts a
bloom program on a card at quarters 1 to 3, so such a consumer would be misanchored without a refusal: pairs from
another corner when a turned side is odd, and another dither key always. The Oscilloscope is unaffected (its Python
scene is unturned; it turns at the vertex). Before the first turned bloom consumer: the composite forms and the first
downsample take the scene's turn as Python's `sceneTexel` does, or the core refuses a bloom or composite program on a
turned card until they do; proof at quarters 1 to 3 with odd item sides.

**M4. The stale-stream fix has no regression test.** `generic_mode_check`'s `a_new_stream_clears_the_frame_of_the_old_one`
binds a new stream holding nothing (the case cleared before ABI 27); nothing tests a new stream whose first frame the
admission rejects. Run directly on the ABI 27 module (`stale_stream_probe.py`): stream A drawn (sum 1,630,890); a new
stream whose first frame is not a present frame: 0, `has_frame` false, `admission_rejected` 1; a present first frame
draws again; an empty new stream 0. Make it a case of `generic_mode_check.py` (or a module test) with its negative
control seen failing, and the R number at merge.

### Low

- **L1. A 64-multiple item on its own rect.** 576 x 384 (420 x 280 at 48/35, `_audit10_edge/`): rule (a) fails 5 of
  61 frames (Trace frames, 11 to 14 ties at 2 levels), rule (b) one frame (2 ties not isolated); 384 x 256 (32/35),
  504 x 336 and 588 x 392 (1.2, 1.4; `_audit10_near/`) pass. Cause not isolated (both allocations end at the item
  there); rerun after H1.
- **L2. The record admits `u_points` below 2 with `osc_segments` above 0** (`FIELD_CHECKS` are "at most" only); the
  beam's vertex stage then divides by `u_points - 1` = 0 (undefined on the GPU, garbage, not a crash). An "at least 2"
  check, or `max(1, ...)` in the shared shader.
- **L3. `opaque_glow` now discards outside the item**, so a quad-aligned surface's margin texels keep the target's
  clear; a future opaque consumer drawn in Qt's opaque pass would show them. No consumer yet: check at its first.
- **L4. A same-mode rebind whose first frame is inadmissible** now shows nothing until an admissible frame, where it
  kept the mode's own last frame before ABI 27. If Python's node keeps its last admitted frame across activations, that
  is a vanish; check once at the owner level.
- **L5.** D12's bucket sentence (H1) is corrected with H1's fix.

### Held (controls run, all as expected)

- The agent's proof rerun on ABI 27 (`_audit10_base/`): block, item, pixels, offsets PASS on both APIs, validation
  clean, the same figures (rule (b) 126 samples, worst 103 masked, 2 ties). `--control old_origin` failed at all 8
  placements; `--control bloom_dropped` failed (124 of 126 frames).
- The composite's keys, through broken forms of the oracle (Python's overlay-glow composite changed in the OpenGL
  child, the native unchanged: the same error as in the native composite, seen from the other side): the dither key
  one pixel off (`_audit10_dither/`) fails rule (a) at every ratio and placement (2 to 3 levels); the glow read one
  pixel off in x (`_audit10_glowx/`, up to 53 levels) and in y (`_audit10_glowy/`) fail. So rule (a) on OpenGL sees a
  one-pixel error in either axis of the glow read and in the dither key (rule (b) and the against-own comparison
  cannot: the same shader on both sides).
- The bucket: targets larger by 20 to 70 pixels (into the next bucket in one or both axes) at dpr 1, 1.5, 1.2 and 1.4
  pass within 2 levels of their own rect and rule (a) (`_audit10_bucket/`, `_audit10_near/`), over the round's Ring and
  Phase frames.
- N3.4's `post_stage_check.py --rounds parity barriers` on ABI 27: PASS (`n3_4/20261121_audit10_n34_abi27/`).
  `test_native_oscilloscope.py`, `test_native_core_mode.py`, `test_native_post_stages.py`: 42 passed.
- ABI 26 `unread`: a name the record lacks and a read field named unread are refused before the per-field check; the
  per-field check skips only declared names. The route's variant switch: its one caller passes the drawn snapshot, and
  Glow crossing 0 always changes the settings (`u_hdr_exposure` only above 0), so the edge is never missed.
- `bloomTriangle` and the composite's glow read agree: the glow's uv is offset by the item's place in the source, and
  the composite reads it at the item-relative texel, which lands on the surface pixel (and the probes above hold it).

## Checkpoint audit 11 (N3.6 Lifetime)

Scope: branch `worktree-agent-ab5da4c3c451f82c5` at ebfe0944a merged into the audit worktree (Opus High), on its ABI 30
module (GitHub build of e21923f1c; ebfe0944a changes only `device_loss_check.py`). Read first: `host_adapter.cpp` (the
window record's loss slots, `HiddenHost::State::recover`), `vulkan_context.cpp` (device creation and destruction off
the GUI thread, the raw deferred queue, `faultReport`), `rhi_owned.h` and its 119 sites, `frame_driver.cpp`,
`gpu_timer.cpp`, `job_service.cpp`, `pipeline_cache.cpp`; Qt 6.12.0's own sources for what the branch relies on
(`qsgthreadedrenderloop.cpp`, `qquickrendercontrol.cpp`, `qsgrhisupport.cpp`, `qvulkaninstance.cpp`, `qrhivulkan.cpp`,
`qrhi_p.h`) and the local 6.11.2 SDK's `qquickrendercontrol_p.h`. One heavy process at a time, no visible window.
Evidence: `.artifacts/evidence/native_core/n3_6/20261121_n36_audit_rerun/` (the agent's full proof, rerun) and
`20261121_audit11_controls/` (child records and the probe scripts, run from the repository root).

Verdict: safe to merge. What the proofs claim, they show, and the controls I ran fail where they should. But every
proof is a forced loss on the hidden host, so the product's real-loss path has never run (M1). Two gaps would show only
at a user's GPU reset: a failed `vkCreateDevice` leaves the window black for good (M2), and only one scene is ever
rebuilt (M3).

### Medium

**M1. No real loss and no window host has ever run the loss path.** In every loss record, the agent's
(`20261121_n36_lifetime_final`) and my rerun's, `qrhi_lost` is false: a forced loss leaves the device alive. So these
never execute: the window record's `sceneGraphInvalidated`/`sceneGraphInitialized` slots on Qt's threaded loop (the
product's whole loss path, `host_adapter.cpp` `WindowHost::create`), `faultReport` (the `VK_EXT_device_fault` query;
`device_fault` is true on this machine, so the query would run), the `isDeviceLost()` guards (the frame driver's skipped
finish, the job teardown's skipped save), and the job service's stop on a lost device. `device_loss_check.py` lists
this under "Not proved here". Failure scenario: a defect in any of these ships unseen and fires only during a user's
TDR, the one event the box exists for. I read the window slots against Qt 6.12's `teardownGraphics`: it cleans up the
nodes, invalidates the scene graph (the signal fires with `wd->rhi` still set), releases the swapchain, destroys the
QRhi, then sets `wd->rhi = nullptr`. `ensureRhi` makes the new QRhi through `createRhi(window, ...)`, which reads the
stored device, and then emits `sceneGraphInitialized`. The slots' order matches; that is a reading, not a run. Fix: a
harness-only real loss, so Qt's own QRhi reports `isDeviceLost()`. For example, the hidden host's device-function
table answers `vkQueueSubmit` with `VK_ERROR_DEVICE_LOST` once (Qt's `QVulkanDeviceFunctions` table, GuiPrivate is
already linked), with no environment flag. Then rerun the rebuild round with `qrhi_lost` true and the fault report
present. Or the lead records the window-slot path as accepted unproven.

**M2. A failed `vkCreateDevice` at the invalidation leaves the window black until restart.** `replaceDevice`
(`host_adapter.cpp:278`) keeps the lost device when no new device can be made ("the window stays without frames"), and
nothing retries. Qt 6.12's `ensureRhi` retries `createRhi` every frame on the stored device, which is still the lost
one. If that QRhi cannot be made, no invalidation follows and the slot never runs again. If it is made and fails, the
slot runs at the next loss. Failure scenario: the first slot runs while the driver is still resetting after a TDR,
`vkCreateDevice` fails once, and that display shows nothing for the rest of the session (a vanish, against the
fade-never-vanish rule). Source reading only; cannot be run without M1's injection. Fix: retry the replacement where
Qt retries (for example, at the record's next frame edge or expose while `device_swapped` is false), with M1's
injection plus a forced create failure as its proof.

**M3. The rebuild is proven for one scene only.** The rebuild round draws N4.a's Crossfade (one pass, two job
textures). The plan says every core object is made again. These owners never cross a loss in any run: scene targets,
post stages (bloom, defocus), mode storage with its compute kernels, meshes, Spectrum, the background layer with its
backdrop pyramid, the load and probe passes, the GPU timer. The hidden host's new QRhi may take the old one's address.
Several owners decide "same QRhi, keep my objects" by pointer (`surfaces.cpp:186`, `backdrop.cpp:264`,
`post_stages.cpp:654`, `scene_targets.cpp:825`, `compute_passes.cpp:886`). They are correct only because every one is
destroyed with its node at the invalidation. An owner that outlives the node would reuse dead objects on the new QRhi,
and this round could not see it. Fix: the rebuild round also runs a mode program with storage, a scene target, bloom
and meshes (`generic_mode_check.py`'s), Spectrum, and the background layer with a backdrop. Each frame after the loss
must equal the frame before it.

### Low

- **L1. `RhiOwned` turns "a never-created resource outlives its QRhi" from safe into a use-after-free.** In Qt 6.12,
  `registerResource` runs in each backend's `create()`, not at construction (`QVkBuffer::create` ends with it), and
  `~QRhiImplementation` nulls `m_rhi` only for registered resources. `deleteLater()` calls `m_rhi->addDeleteLater`.
  So a wrapper that was never created, or whose `create()` failed (the "failed partial builds kept until retirement"),
  dereferences a freed QRhi when it is retired after that QRhi. Before, a plain `delete` was safe: `destroy()` returns
  before touching the QRhi when it holds no native object. Latent today, because owners release with their nodes.
  The holders that can outlive their QRhi are the harness's left-behind lists, matched by QRhi pointer
  (`compute_passes.cpp:601`, `post_stages.cpp:90`), and the "another QRhi" branches of M3. Fix: state the contract in
  `rhi_owned.h` (retired before its QRhi, always). Then prove it: no wrapper of a core owner is live after
  `sceneGraphInvalidated` (a count in `device_loss_check.py`).
- **L2. The job teardown's guard against saving after a loss is the job thread's own observation.** `m_deviceLost` is
  set only when a job met the loss. At rest the job thread is parked, so a window-side loss leaves it false, and
  `tearDown` (`job_service.cpp:828`) saves the lost device's `pipelineCacheData()` over the good file. Dormant: the job
  QRhi builds no pipeline, so the blob is empty. Fix: the device's destruction tells its service that the device was
  lost (`replaceDevice` knows: `reallyLost`) before `stop()`.
- **L3. The cache file's "last writer wins" is "some writer wins", and the real save path is unexercised.** In
  `pipeline_cache_self_test`, run three times (`audit11_controls/cache_selftest.py`), 31 to 41 of each writer's 60 saves
  fail (on Windows a rename over a file a reader holds open fails) and 12 to 21 reads cannot open the file. There are
  never torn reads, and the final file is always one writer's. The test requires only `saved > 0`. Meanwhile
  `job_service_check`'s `pipeline_cache_by_rule` counts `save_failed` as red, so two windows tearing down at once would
  red the harness on acceptable behaviour. No real QRhi blob has ever been written or loaded through
  `setPipelineCacheData`. Fix: treat a failed commit as a reported skip, not red, and make the plan's wording match;
  run the real-blob round trip when the first pipeline on the job QRhi or the first raw `VkPipelineCache` exists.
- **L4. The release round's stated negative control never ran.** The docstring says "Its negative control is the ABI
  29 module, whose in-frame release waited for the queue". The agent's journal says this was not run (ABI 29 has no
  in-frame detach). On Vulkan, `pool_deferred_not_destroyed` carries the round. On OpenGL, `no_wait_inside_the_frame`
  is vacuous, since OpenGL never waits. The proof itself does have teeth: Qt 6.12's `endOffscreenFrame` waits only
  when readbacks are scheduled, so the round's frames really overlap (two in flight) and validation would see a pool
  destroyed early. Fix: correct the docstring, and drop the OpenGL check or say it is informational.
- **L5. Qt-private fragility, contained.** `QQuickRenderControlPrivate::resetRhi(const QQuickGraphicsConfiguration &)`
  is the same in the 6.11.2 header and the 6.12.0 source. The build pins PySide6's Qt, and the module refuses a
  different runtime Qt (`module.cpp:3177`), so an upgrade forces a rebuild that fails to compile if the signature
  changes. `resetRhi` deletes the owned QRhi and the offscreen surface but does not clear `QQuickWindowPrivate::rhi`;
  `initialize()` reassigns it. If `initialize()` fails in `recover`, `window->rhi()` dangles. The hidden host stops
  rendering then, and its frame source reads `control->rhi()`, so this is contained. Recheck both facts against Qt
  source at each Qt upgrade (with N3.4's `beginExternal` box).
- **L6. The parent box's other parts are not on this branch.** Lazy creation, release at retirement and at a mode
  switch, pipelines built ahead and warmed gradually, and the P2 audit's working-set and GPU-memory rerun are untouched.
  The `VK_EXT_device_fault` log exists but has never executed (M1). These are plan bookkeeping, not defects.

### Held (controls run, all as expected)

- The agent's proof rerun on ABI 30 (`20261121_n36_audit_rerun/`): rebuild, control and release PASS on both APIs.
  Validation was loaded with no unexplained messages (10 errors, all the recorded Qt defect A). Both forced losses
  gave a frame equal to the frame before (0 differing pixels), and each lost device's teardown ran in order (job
  service stopped, `vkDeviceWaitIdle`, `vkDestroyDevice`, `resetDeviceFunctions`). The children's stderr was empty
  (no Qt warnings) for OpenGL and Vulkan.
- The rebuild round's power: a harness copy whose lost edge does not send the pictures again
  (`make_controls.py`, `ctl_vk.json`) fails `frame_equals_the_one_before` on both losses (230,400 pixels, up to 254
  levels) and `resent_through_the_devices_jobs`. The control round's records judged as a swap (`show_child.py ... judge`)
  fail five checks (`device_swapped`, `qrhi_rebuilt_on_new_device`, `host_reports_new_device`, `lost_device_destroyed`,
  `qrhi_before_on_old_device`). So the slot's `setGraphicsDevice` is what moves Qt's rebuild.
- Threading I checked against Qt 6.12 and found safe: `QVulkanInstance::deviceFunctions` and `resetDeviceFunctions` take
  `deviceFuncsMutex`, so devices made and destroyed on a render thread do not race other windows' or job threads'
  lookups. `setGraphicsDevice` is a plain store, read on the same render thread by `createRhi`. The raw queue's
  release, at stamp + FramesInFlight inside the frame after `beginFrame` waited for that slot, is correct, and its
  entries drain before `vkDestroyDevice`.
- Tests: `test_native_core_device_loss.py`, `test_native_core_pipeline_cache.py` (on the module),
  `test_native_core_release_timing.py`, `test_native_post_stages.py`, `test_quick_backend_owner.py`: 60 passed.
