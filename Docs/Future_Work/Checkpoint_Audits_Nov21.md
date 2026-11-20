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
  copy with one hash changed at input 200, CHANGED at exactly [200] and exit 1 (`_r5_control_one_hash`).
