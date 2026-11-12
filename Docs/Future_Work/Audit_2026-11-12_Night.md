# Audit, 12 Nov 2026 night: today's merges, today's answers, the plan's order

The gate the operator set on 12 Nov evening: new work starts only once "the current lot of work, documents and
answers has passed" and "the plans are in logical order and worries have been solved". Scope: every first-parent
merge on `main` after 9b29dfa3 (R-199, the doc sweep, N2.3's Python half, N1.6's next groups with the lead's three
conflict resolutions, `Docs/Reference/Primitives.md`, N2.1, R-200) at 43b511a6; the four answers given to the
operator today; `Current_Plan.md` in full, `Native_Core_P3_Decisions.md` and the `Docs/Future_Work/` plans it cites.
Opus 5.5 High, audit slot. No build was started (N2.1's product round runs under the lead); no window was shown.

Counts: **2 must fix before new work, 10 fix soon, 9 lows.** Fixed in place by this audit: 25 stale or broken plan
and document passages in 7 files, one restored historical-bug entry (listed at the end), and one missing guard with
its negative control (N2.3). Line numbers are after this audit's
commits.

## Verdict on the merged work

Every merge passed its focused tests on this branch (R-199: 59; N2.3: 258 across 14 caller files, plus 10 new; N1.6:
196 changed files, 146 render-node and host callers, 307 transition files; N2.1: 147 passed, 4 skipped for the
unbuilt module, Build Runner 30; R-200: 57). No environment flag, no new product timer or polling, no preset named,
listed or counted, the protected clip commits untouched, nothing per frame at rest that was not there before (two
small per-frame allocations in Spectrum's renderer, low 7). The lead's three N1.6 conflict resolutions are correct:
`background_node.py` and `surface_backdrop.py` take R-198's `delete_program` together with N1.6's pass blocks (the
blocks' `release()` kept), and `fullscreen_pass.py` is N1.6's rewrite, which already deletes through
`delete_program`; no raw `glDeleteProgram` is left outside `gl_resources.py`. R-200's lifetime rule is sound (the
bridge leaves `_RETIRING` on the engine's own `destroyed`, after its bindings are gone) but makes 1D.0's first box
more pressing (fix soon 4).

## Must fix before new work

### 1. The operator was told the large gains arrive "with the native core on OpenGL at N2 onward"; for async jobs that is wrong, and for the Python-free render thread it is early

- **Where:** today's answer "Gains outside Vulkan" (chat, not in a document). Against it:
  `Docs/Future_Work/Native_Core_P3_Decisions.md:532-535` (D9 point 5: the job body runs "on the graphics queue in the
  frame: on the OpenGL fallback, and on Vulkan devices without a second queue"), `:646-651` (D10 point 4: modes
  switch on OpenGL one at a time; the background family switches as one unit at its last transition's parity), and
  `Current_Plan.md` N5.7a (`:475-479`: "production on OpenGL keeps the Python presenter until N5.2h").
- **What is wrong:** (a) On OpenGL there is no second queue and D9 runs every job in the frame, so async GPU jobs
  (D8 plus 3, "no hitch at an image change") are a Vulkan gain only, reaching users at the flip (NF). Only the job
  body's shared code exists on OpenGL. (b) A window's render thread is free of Python and the GIL only when every
  render node it draws is native: a ported mode beside the Python background node (`BackgroundRenderNode.render` is
  Python, called every rendered frame) still takes the GIL each frame. On OpenGL that is after N5.2h for any window
  that shows the wallpaper, per mode as each ports; "N2 onward" is where it starts for one mode in hidden hosts, not
  where the operator sees it. (c) Smaller: "a few percent fewer GL calls" understates N1.6 (Waveform 687 to 468,
  32 %; Spectrum 151 to 121, 20 %; Beam 99 to 74).
- **Evidence:** the three passages above; `rendering/quick/render/background_node.py` (a `QSGRenderNode` in Python).
- **Fix:** one correction to the operator before new work: on OpenGL the native core removes Python from the render
  thread per window once that window's mode and the background family are ported (N5.2h); async jobs are Vulkan's
  (OpenGL runs the same jobs in the frame by design, D9 point 5); the GL-call cut was 20-32 % on the converted
  modes. Nothing in the plan changes.

### 2. Section 1's strict order does not place 1C or 1D, so the next dispatches have no written order

- **Where:** `Current_Plan.md:35-43` ("Order of work (strict)": item 0 is 1B, then items 1 to 9); `:931` (1C: "ahead
  of everything in 1B that is not already in flight"); `:1167` (1D: "after the current agents pass audit");
  `:1063` (1C.10 "one Opus High agent when a slot is free"); item 8b's own "Order" (`:212-217`: "N0 and N1 now").
- **What is wrong:** four sources each claim the next High slot (1C.10 Neon Lake round 3, 1D.2 display styles, the
  native ladder's N0.3 scenes and N2.2 to N2.4, the open 1C.2 Save stall), and two the Medium slot (1D.1, 1B.10
  presets), with no line saying which goes first. The handbook (section 1) runs "one high-end task, one medium task
  and one audit" at once, so the order is the gate the operator named ("plans in logical order").
- **Evidence:** the lines above; none of 1C.10, 1D.1, 1D.2 or N0.3 is named under "Now (in flight)".
- **Fix (the lead's decision; a proposal is the last section):** one line under "Now (in flight)" naming the High
  queue, the Medium queue and the docs queue by plan item, in order, and 1C/1D's headings pointing at it.

## Fix soon

### 3. N4.f is scheduled after the port that needs it

- **Where:** `Current_Plan.md:537-541` (N4.f, "After N5.6, before Expanded Visualizer M6"), `:569-571` (N5.4
  Waveform Ribbon needs "N4.f's fog volume"), `:574` ("N4.f for both, then ... M6"); D8 row 4 and its placement line
  (decisions `:483`, `:495-498`: "4 after Waveform Ribbon and Extruded Bubble are native").
- **What is wrong:** N4.f joins two different things: the port of the existing Python fog volume (Waveform draws it
  today, so N5.4 cannot reach parity without it) and P4's new mixed-resolution layers (the D8 plus that belongs after
  N5.6). As written, N5.4 depends on an item scheduled after N5.6.
- **Fix:** split N4.f: N4.f1 the fog volume port, "just before its first consumer" like every N4 item (with N5.4);
  N4.f2 the reduced-resolution layers and depth-aware upsampling, after N5.6 and before M6, as D8 places them. No
  decision changes.

### 4. R-200 keeps the retiring Studio bridge alive and still connected to the controller

- **Where:** `ui/studio/surface.py` `release_engine` (the bridge now lives until its engine is destroyed);
  `ui/studio/controller.py:1583` (`bridge.closeRequested` connected to `_on_bridge_close`), `:144` (`self._c`);
  plan 1D.0 first box (`Current_Plan.md:1171`).
- **What is wrong:** before R-200 the old bridge died at the switch (with 148 TypeErrors); now it outlives the switch
  by design, so its slots (`requestClose` from the retiring shell's Close button or Esc, `select_preset`, the store
  actions) reach the new mode's session through `self._c` for as long as the retiring window and engine wait for the
  event loop. The window is hidden on a queued call, so the window is short, but the path exists.
- **Fix:** 1D.0's first box as written, before 1D.1 (it is small and in the files R-200 just touched): disconnect the
  old bridge from the controller at retirement and null its controller reference; the test calls a slot on the old
  bridge after `request_mode_switch` and sees no effect (negative control: today's code).

### 5. N2's internal order: N2.5's "done" needs N2.6, N2.7 and N2.8, which come after it

- **Where:** `Current_Plan.md:449-460`; the port rule (e) GPU time per pass and (f) one bounded Vulkan rehearsal
  (`:176-182`).
- **What is wrong:** N2.5 (Spectrum at parity, Python renderer retired) is listed before the timer (N2.6), the backend
  owner and rehearsal path (N2.7) and the first rehearsal (N2.8) that its own rule requires; the N2.5 text allows
  "whole-frame time, say so" for (e) but nothing for (f).
- **Fix:** order N2 as N2.1 to N2.4, N2.6, N2.7, N2.5 (built), N2.8 (the rehearsal that closes N2.5's rule f), or say
  in N2.5 that its retirement waits for N2.8.

### 6. The Qt 6.12 re-baseline is filed under a 7 Nov "not admitted" heading, and today's merges were not measured against a 6.12 baseline

- **Where:** `Current_Plan.md:1594` ("Found while building Expanded Visualizer M3 (7 Nov night; recorded, not yet
  admitted)") holding `:1607-1609` (Re-baseline after Qt 6.12.0, doc sweep 12 Nov); `Docs/Reference/Benchmarks.md`
  (the dated note).
- **What is wrong:** the box is admitted work (the doc sweep's decision 9) and a prerequisite of every overhead
  comparison, but it sits in a "not admitted" list. Meanwhile N2.3 changed Spectrum's per-frame reads (low 7) and
  N1.6 claims GL-call cuts, all measured on branches without a 6.12 baseline.
- **Fix:** move the box to item 6 (Hygiene) or 8b's P2 remainders, run `tools/overhead_baseline.py` on main once
  (lead or Medium slot; no load), and compare Spectrum against it.

### 7. N3.8's box omits two things D9 hands it

- **Where:** `Current_Plan.md:473-474` (N3.8); decisions `:518-523` (D9 point 2: consumers (a) photo and transition
  preparation, (b) warm-up), `:612-613` ("N3.8 re-measures it as D8 row 3 states: image changes with a Visualizer
  running").
- **What is wrong:** the box names only "a photo's upload and mips". The contention measurement under a heavy
  Visualizer frame (the one limit of N0.7's proof) and the warm-up class have no box anywhere; transition
  preparation is N5.2g's.
- **Fix:** add under N3.8: "D8 row 3's gate: p99 frame time and late frames across image changes with a Visualizer
  running, async against in-frame (Vulkan only; OpenGL runs in-frame)"; and one line placing class (b) warm-up jobs
  (with N3.6's gradual warm-up).

### 8. Builds and installers: the handbook still contradicts itself after the doc sweep's decision 2

- **Where:** `Docs/Guides/Orchestrator_Handbook.md:122` (section 7: builds "never on this machine's resources";
  "local installers ... stay the operator's own") against `:142-143` (section 8: "Frozen products and the lead's
  installers go through GitHub"); `Docs/Guides/GitHub_Remote_Build.md:224` and `.github/workflows/windows-build.yml:9`
  ("No installer is compiled here: installers are compiled locally by Build Runner").
- **What is wrong:** no installer is compiled on GitHub, so "the lead's installers go through GitHub" cannot be done
  as written, and the lead's Inno step runs on this machine, which section 7 reserves for the operator.
- **Fix (lead's one sentence, then the two lines follow):** either the lead may run Build Runner's local Inno step
  over GitHub payloads (section 7 then names that exception), or installers are the operator's alone (section 8 and
  `GitHub_Remote_Build.md:224` drop "the lead's installers").

### 9. The native core's MSVC runtime check runs after the module is imported

**Resolved 12 Nov:** the file's PE imports and linker version are checked before import; the post-import check stays.

- **Where:** `rendering/native/loader.py:148-159` (`load`: `_import_module` executes `PyInit`, then `checked` runs
  `runtime_check.check_module`); `rendering/native/runtime_check.py:236-243`.
- **What is wrong:** the check exists for an arrangement that "fails in ways no test sees" (an STL import bound to
  shiboken6's older `msvcp140`); a module's static initialisers run during the import, before the check can refuse
  it. The workflow's import check catches it on GitHub, so nothing ships wrong today; the product's own load (N2.2
  onward) would crash rather than refuse.
- **Fix:** run rule 1 (no `msvcp140*` import) and the `vcruntime140*` presence and export part from the file before
  `exec_module` (`read_imports` needs only the path); keep the toolset comparison after `runtime_info()`. Test: a
  stand-in PE importing `msvcp140` is refused without being loaded.

### 10. Plan prose still carries landed narratives and old sections' boxes without a proof line

- **Where:** `Current_Plan.md` 1B.8 (`:727-752`, M1, M2, M2b, side defects and follow-ups landed), 1C.2 (`:939-956`),
  1C.4 (`:990-1003`), 1C.5, 1C.6, 1B.10 (`:799-806`), section 7.1 (many `[~]` reviews with narrative), section 3's
  "Found while ..." blocks; item 6's staleness box (`:127-142`) already owns this.
- **Fix:** item 6's box, Sonnet slot, as the docs task after 1D.2's note (last section). Older boxes without a proof
  line (for example 1D.1's UX audit box, section 3's 7 Nov side findings) get one when they are next touched.

### 11. Primitives.md cites `Current_Plan.md` by line number

- **Where:** `Docs/Reference/Primitives.md` throughout (`:46-80`, every "Native:" line); 30+ `Current_Plan.md:NNN`
  citations, already off by 80 lines at 2177/2259 before this audit.
- **Fix:** replace line numbers with item ids (N4.d, 1D.3, ...) in one pass; this audit added a note that they are 12
  Nov afternoon pointers.

### 12. The N1.6 remainder sits under N2b while N1's list also lists it

- **Where:** `Current_Plan.md:464-469` (N2b's "N1.6 remainder" box) and N1's list (`:361-371`, now pointing at it).
- **What is wrong:** the remainder's first consumers are N5.2d (motion and trails), N5.2e and N5.4's fog, all after
  N3; N2b needs none of it (its seven transitions and hosts are merged). Filed under N2b it reads as N2b work.
- **Fix:** keep it as N1 work ("can start now", Python only) and leave N2b's box a pointer, or the reverse; one home.

## Lows

1. `tools/d1_run.py:686` hands `screen.grabWindow(0)`, a `QPixmap`, to the writer thread (`_save_frame`, `zoom_crop`).
   Windows' platform reports threaded pixmaps, so it works here; convert with `.toImage()` on the GUI thread (a copy
   of one frame) so the tool does not depend on it.
2. `rendering/native/loader.py:12-14` says a frozen build carries the module in the package; the product build
   places it beside the product in `release/native_module` (the frozen probe alone copies it into the package).
   Record, at N2.2, how the product's own Nuitka build will carry it.
3. The main checkout's ignored `release/native_module/` still holds the spike (`_srpss_native_spike.pyd`, from before
   the target rename); the first `native_module` round replaces it. The loader ignores it (it looks for
   `_srpss_native_core*.pyd`).
4. `Current_Plan.md:300-314`: two boxes under N0.7 (the first frozen GitHub build on Qt 6.12, the handoff probe's
   inherited-state control) are Qt 6.12 checks, not D9's. The N2.1 product round running now is a frozen GitHub build
   after 655b04bf: its artifact can close the first one with 1B.14's frozen checks.
5. The memory index's agent roster (2 Opus High, 2 Opus Medium, 1 Sonnet) predates the handbook's 12 Nov evening
   roster (one Opus High complex, one Opus High audit, one Opus Medium, one Sonnet); the plan's section 3 said the
   same and is fixed. Memory is the lead's to update.
6. Answer 2 (the second queue) agrees with D9 and the plan; the plan's N3.8 box is narrower than the answer (fix
   soon 7).
7. `rendering/quick/visualizer/implementations/spectrum.py`: every frame now builds two dicts
   (`read_style` loops the whole 39-entry declaration; `_read_per_frame_parameters` zips 11 names). Small, but at the
   renderer's rate; precompute the style entries at import and measure against the 6.12 baseline (fix soon 6).
8. `spectrum_native_schema` stores an enum as its position in `SPECTRUM_PATTERNS` (append-only by its own rule); an
   appended pattern changes no layout fingerprint, so an older reader refuses the new value as "record" rather than
   "version". Fine while writer and reader ship together; say so beside `VERSION` when a C++ reader exists.
9. The brief's "handbook section 7, the audit pattern": section 7 is the hard limits; the audit checklist is section
   4. No document change.

## What the four answers were checked against

1. **D5's retrofit wording** (decisions `:162-168`, commit 54215c5e): agrees. The expensive part is adding the rules
   to a core after the modes exist; built in, each new mode only declares passes and resources.
2. **The second queue** (proved in N0.7, not live, N3.8; photos and transition preparation first, then warm-up;
   simulations in the frame): agrees with D9 points 2 and 5 and its accepted verdict (`:518-523`, `:571-615`) and
   with the plan (N3.8 in N2b, N5.2g's fields the first transition job). Gap: fix soon 7.
3. **Gains outside Vulkan:** must fix 1.
4. **Primitive timing** (N4 just before its first consumer; N6 on the primitives track after N3, never holding the
   flip): agrees with the N4 heading (`:518-519`), the 8b "Order" (`:212-217`), handbook section 8 and
   `Primitives.md` section 2. Exception: N4.f (fix soon 3).

## 1D, checked

- 1D.0: R-200 merged; its three side-defect boxes are valid (the controller lines exist at `:144`, `:1583`); raise the
  first (fix soon 4).
- 1D.1: the JMIT Pools cause is confirmed: `ui/onboarding/basic_pages.py:121,168,185` read and write
  `sources.rss_feeds` only, while the count uses `online_source_count` (`:13`, `:138`). Complete as written; the UX
  audit box wants a proof line (what "fixed" is shown by).
- 1D.2: complete (design note first, retarget not rebuild, guards, tests with negative controls, the lead's D1 run);
  its setting owner `core/settings/fullscreen_overlays.py` holds `expanded_display_requested` as stated.
- 1D.3: every item verified and closed by this audit (below).
- Placement: must fix 2.

## Fixed in place by this audit (commits on this branch)

- `tests/test_visualizer_engine_native_schema.py`: `test_the_codec_reader_admits_a_codec_slot_of_every_registered_mode`.
  N2.3's tests proved refusals but nothing proved the product's codec stream admits every real mode code; a false
  refusal fails the stream for the whole session. Negative control in the test: the same head refused with the code
  removed from the reader's known set.
- `Current_Plan.md`: the 8b state line (N1.6, N2.1, N2.3 merged); N0.7's parent box made a note (its verdict is in
  D9); N1's N1.6 list without the five landed groups; N1.4's note that Spectrum's group merged without the
  `gl_FragCoord` move; N2.5's stale "on the readiness ratchet"; a numbering note under N3 (N3.5 became N2.6, N3.8 is
  in N2b); section 7.1's "first consumer of S3D-1/S3D-5"; the standing rule's note now in `Primitives.md`; section 3's
  roster and its dead "What can start now" reference; section 4's empty "Frozen builds could not open a Studio"
  heading (its check is 1B.14's frozen box, which now names the contract); 1D.3 deleted (all eight closed).
- `Native_Core_P3_Decisions.md`: the status paragraph (`native/core/` exists since N2.1), D4's "Still open: D4.4 to
  D4.8", D5's heading (N0.5 accepted), D8 row 6 (N4.d's wet-surface masks, the class the plan writes at N4.d), D5.6's
  "six services" (five since 12 Nov).
- `Scene3D_Resources.md:20-22`: Waveform Ribbon named as the third framed-camera consumer.
- `Index.md:150`: item 8b and `Primitives.md` instead of the §6 stub.
- `Docs/Historical_Bugs/R-94_Melt_Float_Hash_Cut_The_Photo_Into_Rectangles.md` and its index row: restored from
  `d3353bd5^` (the 5.0.7 RC consolidation deleted them; seven shaders and two documents cite R-94).
- `Primitives.md`: E1 (the item quad moved to `rendering/gl_programs/item_quad.py`), the status paragraph, and which
  of its contradictions are settled.

## Order of work after this audit

Precondition: must fix 1 sent to the operator, and must fix 2 written as the line below under "Now (in flight)".
The N2.1 product round under the lead finishes first (its artifact also serves low 4).

- **Next High: 8b N0.3, the three test scenes.** It is the native core's critical path: N2.2 and N2.4 wait for it
  (`:206-209`), N1.4's matrix correction and winding rule are proved on OpenGL only until it runs, and every later port's
  Vulkan record depends on its conventions. It is harness work in `native/spike_p1`'s pattern, built through the
  GitHub workflow by the lead, with no product risk and no operator dependency. 1D.2 follows on the same slot as soon
  as its design note is approved; 1C.10 after that (its repairs first, as written).
- **Next Medium: 1D.0's two code boxes, then 1D.1.** 1D.0's bridge disconnect is small, in the files R-200 just
  changed, and closes the path fix soon 4 describes; 1D.1 is an operator request sized for one Medium agent, with its
  cause already confirmed here. Fix soon 9 (the import-order check) fits the same slot afterwards, before N2.2 loads
  the module in a product process.
- **Next docs task (Sonnet): the 1D.2 design note in plan 01 M3c,** drafted for the lead's approval (geometry,
  coverage and clip per style, glyphs, Now Playing, Edit, R-63/R-192 overscan), so that the High slot can build 1D.2
  without waiting on design; then item 6's staleness box (fix soon 10), then `Primitives.md`'s line numbers (fix soon
  11).
- **The lead, between dispatches:** fix soon 3, 5, 7 and 12 are plan edits of a few lines; fix soon 6's baseline is a
  short no-load run; fix soon 8 is one sentence.
