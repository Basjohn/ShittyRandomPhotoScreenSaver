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
