# Audit of 12 Nov 2026, evening: the day's completed work, and next steps

One-off Fable 5.2 High audit, asked for by the operator ("an audit on the completed work and next steps"). Scope:
everything merged to `main` from `3c5632cf` (the morning audit's merge) to `6850e8c4`, about 140 commits, judged
against the code and the tests, never against the commit messages. `main` moved to `43c0edf8` while the audit ran
(the validation layer's first runs, `Docs/Reference/Tooling.md`); those commits are used as context only.

Method: the governing documents first (handbook, plan section 0 and item 8b, decisions D4 to D11 with the lead's
answers, the Qt facts, the Qt 6.12 gains, R-191 to R-197), then each landed area in source. Run here: 49 focused
tests green on HEAD (`test_conventions_include`, `test_qrhi_texture_formats`, `test_framed_view_camera`,
`test_framed_view_record`, `test_framed_view_edges`, `test_visualizer_engine_worker`; 65 s), one probe (kept, below),
a scan of every added line for the standing rules. No product code was changed, nothing was built, no window shown.

Ratings: **High** = a defect or a false claim in shipped behaviour that can hurt a user or the direction;
**Medium** = a claim weaker than stated, a silent drift, or a process gap with a real cost; **Low** = small, recorded.

## 1. Findings by area

| # | Area | Rating | Finding | Where |
|---|---|---|---|---|
| 1 | N1.4 conventions block, lifetime | **High** | The buffer registry is keyed by `id()` of a PySide wrapper that does not outlive the call on a context Qt owns. On Qt Quick's render thread: one buffer per program link, none ever released, and a context can be mistaken for another and left with nothing bound at binding 17. Full text in section 2 | `rendering/quick/render/gl_resources.py:133-190` (cefbfa2b) |
| 2 | N1.4 conventions block, holders | Medium | `_link` decides "declares the block" by the text `SrpssConventions` in the source. The mapping-only include carries that text inside an `#if` that is false, so the fog march and fog composite fragments take a hold without declaring the block, and their owner deletes them with a raw `glDeleteProgram`, which never hands it back | `gl_resources.py:117`; `rendering/gl_programs/fog_volume.py:129,255`; `rendering/quick/scene3d/fog_volume.py:248,424` |
| 3 | N1.4, what is left | Medium | The plan's N1.4 box still reads as if nothing landed. What is truly left: (a) per-pixel hash seeds on raw `gl_FragCoord` (fog march jitter and crackle, reflection streak, Extruded Bubble's jitter): the dither will differ between OpenGL and Vulkan, so the port rule's "Vulkan against native OpenGL within a tolerance" fails on noise or forces a loose tolerance; (b) projection matrices corrected at upload: not built; (c) the winding rule "tested once per backend": only its truth table and Sphere's OpenGL answer are tested; (d) Extruded Spectrum's and Sphere's backdrop uv, the four 2D shaders. The eight scene composites stay raw on purpose (D5.2 replaces them with a texture node) but nothing says so | `rendering/gl_programs/fog_volume.py:165,289`, `reflection.py:84`, `extruded_bubble_program.py:545`, `extruded_spectrum_program.py:415`, `sphere_voxel.py:658`, `scene3d/target.py:131-282` |
| 4 | N0.3 proof | Medium | The three convention scenes (checkerboard, known-depth plane, culled triangle) were to be built "in the harness with N0.6". N0.6's six rounds landed without them and no box carries them. The include's flip, the matrix correction and the winding rule are therefore proved on OpenGL only (the flip by a hand-made block in a test), on no other backend | `Native_Core_P3_Decisions.md:1354-1386`; plan N0 first bullet; no scene in `native/spike_p1/src/` |
| 5 | N0.6 | Medium | The harness passes a round with validation "owed" instead of failing closed, against D6's amendment ("failing closed when the layer is missing") and the facts file (E2). The first validated runs (on `main`, 1952bded) find synchronisation hazards in rounds recorded as PASS, and D6's heading reads "As proved". The layer is found through `VK_ADD_LAYER_PATH`, so `environment_clean` now fails by design and D6's "no environment variable is used" is no longer true as written | `native/spike_p1/python/run_n06.py:399-410,569-580,763`; `Native_Core_P3_Decisions.md:293-297,305` |
| 6 | N0.6 lifecycle check | Low | The handle check was changed to "baseline plus 3 per device created" after the measurement. The attribution is sound (Qt's own device costs the same 3), but the check now encodes one driver's number and would hide a leak of ours that is a multiple of 3 per device | `run_n06.py` lifecycle round (33440911) |
| 7 | N0.4 | Medium | "The worker's Waveform Ribbon and Extruded Bubble cameras equal the renderer's bit for bit" is true of two functions nothing in the product calls: `framed_view_camera` has no caller outside its test, the worker tick builds no camera and the packet carries none. What landed is the inputs (`VIS_SET_VIEW` v2) and `card_span`. D5.5's own tests (one owner; the resize edge with the extent stamp) are not built and not boxed. Waveform's oracle in the test restates the renderer's expression instead of calling it | `widgets/spotify_visualizer/framed_view_camera.py`; `tests/test_framed_view_camera.py:75-83`; `Native_Core_P3_Decisions.md:1475-1488` |
| 8 | N0.4, offline hosts | Medium | Since N0.4 a controller with no framed view gives `card_span` None and the pulse logic falls back to its fixed grid (before, every host got the layout extent's span). The driver, the Studio and the foundry were given a view; the Waveform audit tools and the worker gates were not, so item 2's reactivity tools now measure a pulse the product does not draw | `core/waveform_ribbon_dynamics.py:979,1057,1441`; `tools/visualizer_replay/waveform_ribbon_motion_audit.py:67`, `waveform_ribbon_signal_audit.py:39`, `waveform_ribbon_breathing_probe.py:94`, `tools/labs/waveform_ribbon_recorded_input.py:35`, `engine_worker_gate.py:45`, `live_engine_gate.py:144,419`, `live_engine_cost.py:98` (62123413) |
| 9 | N0.4 merge | Medium (process) | 438790f7 was merged with `tests/test_visualizer_engine_worker.py` red and stayed red across fifteen merges until 4a805fe6. The handbook's caller sweep (a changed shared owner: `EngineSession.set_view`) was not run on that merge. The fix itself is right: the gate now replays the owner's view as the production link does | 438790f7, 4a805fe6 |
| 10 | N1.2 | Medium | "Every compute source bakes through `qsb` for every target" holds for module-level sources only. The six composed compute programs the product actually runs (the fog inject with its medium, the population count and scatter for both transitions, the propagation seed) do not bake; N1.3 found them and put them on the ratchet. The plan's N1.2 line still states the wider claim | `tests/test_vulkan_shader_readiness.py:91-95,262,424-429` (e8a5694b, 1902e166) |
| 11 | N1.3 | solid | The ratchet lists 197 sources, shrinks only, fails both ways (a new failure, a listed source that now bakes), and cannot pass vacuously (stages, composers, hidden literals are all checked). One note for the order: Spectrum's shader and the Quick visualizer vertex sit in the "2D modes" group, seventh of nine, although Spectrum is the first port (section 3) | `tests/test_vulkan_shader_readiness.py:70-142,226-443` |
| 12 | N1.7 | solid, Low | Formats test scans `rendering/` only and by enum text; a format reached through an alias or under `widgets/` would pass. The row 13 control (non-zero unused channels) is correctly an open box | `tests/test_qrhi_texture_formats.py:17,30` |
| 13 | N0.8 | Medium | D11 as written and as decided by the lead (72dd5fb8) takes 6.12 "through the whole suite, a GitHub frozen build and the Display 1 card-edge check"; the operator then made it a plain bump. No frozen product has been built on Qt 6.12 (QML prune contract, DLL set), and the box that would do it (1B.14) does not say so. D11 still describes the checkpoint that was not taken | `Native_Core_P3_Decisions.md:598-608`; plan 1B.14 "Frozen build" |
| 14 | N0.8 follow-up test | Medium | The handoff probe's inherited-state assertion was narrowed from Qt's whole sync to the item's `updatePaintNode`, on the statement that Qt 6.12's own sync resets the array-buffer binding. No kept control shows the binding changing in a sync in which our code does nothing; the product fix (restore, not reset) landed in the same commit, so the two were never separated | `tests/test_qtquick_native_texture_handoff_gl.py:114-129` (ccc19ef0); `Qt_6_12_Gains.md:105` ("Why ... changed: unconfirmed") |
| 15 | N0.9 | solid, Low | Fetch verifies size, pinned sha256 and Qt's published sha256 before extracting anything; path escapes refused; the workflow builds only the verified SHA and never interpolates inputs into scripts; the download is validated against the built commit's pin. Low: Vulkan-Headers 1.4.341 is asserted to be "the release Qt 6.12 is built with" without a source; actions are pinned by major tag, not SHA; the workflow's source folder is hard-coded to the spike (N2.1 must lift it) | `tools/native_sdk_fetch.py:127-134,284-296`; `.github/workflows/native-module.yml:61,70-78` |
| 16 | 1C.2 display moves | solid | Retarget is real: the hop commits in place, a move ending in a reload returns False, the fence is flushed before another context waits on it, a failed fence wait releases the history once. Stages advance at publication edges, no timer | `quick_display_visualizer_owner.py:958-1029`; `extruded_bubble_drift_solver.py:403-410,519-529` |
| 17 | 1C.2, prepared neighbour | Medium | While a neighbour is prepared (pointer resting on a transfer arrow, a drag held near the seam), every published frame calls `feed_prewarm`, which calls `update()` on the other display's item for as long as the hover lasts, also after its renderer reported prepared. A display that is otherwise at rest then redraws at the Visualizer's rate with no bound | `quick_display_visualizer_owner.py:585-588`; `rendering/quick/visualizer/item.py:344-354` (1abb1472) |
| 18 | 1C.2, 0.002 opacity | Low | "Below one 8-bit level" is true for the card measured. 0.002 x 255 = 0.51, so a pure white card part over pure black computes to level 1; invisible in practice, but the claim is theme-dependent and the test pins one theme's result | `quick_display_visualizer_owner.py:102-104`; `tests/test_visualizer_display_move_gpu.py:223` |
| 19 | 1C.2 input test | Low | The wheel line of the prepared-card test is not a control, as the test says itself; only the hit test and `prepareOnly` lines are | `tests/test_visualizer_prepared_card_input.py:36-41` |
| 20 | R-191 | solid | 54 cases, three DPRs, an off-grid card, two negative controls (unsnapped card, inset clip). The comparison sheets were lost with a worktree; the handover tool now prevents that | `tests/test_visualizer_card_clip_contract.py` (7c2e226f) |
| 21 | R-192 | Medium | The second-axis overscan (62dcb78a) moves the window on the operator's own Display 0 from `(0,-3)` 2560 x 1443 to `(-2,-3)` 2562 x 1443 and has never been seen on a real display; Display 1 has no second-axis case, so the lead cannot check it without the operator's leave. R-192's "Still open" (an axis with no exterior edge keeps Qt Quick's stretch) is in the bug entry only, not in the plan | `rendering/quick/device_geometry.py:87-127`; `R-192...md:55-60` |
| 22 | R-193, R-195, R-196 | solid (read, not re-run) | Each fix is at the owner and each entry names a regression bar that exists. R-195's allocate-before-release and R-196's span were read in source; their "red before the fix" statements were not re-checked | `extruded_bubble_drift_solver.py`; `core/waveform_ribbon_view.py:57-70` |
| 23 | R-197 | solid, Low | One continuous coordinate, uploaded only when the placement changes. Low: it adds a raw `gl_FragCoord` use and two loose uniforms to the first shader that ports; the port must carry the same rule from its own target's pixel (plan N2.5) | `widgets/spotify_visualizer/shaders/spectrum.frag:506-508`; `spectrum.py:333-341` (6c483dfb) |
| 24 | Studio chrome ink | solid, Low | Correct rule, guarded by an existing test. "Every other theme byte-identical" rests on the agent's run, not on a kept test | `ui/studio/theme.py:260-265` (d473559f); `tests/test_waveform_studio_theme.py:27` |
| 25 | Plan freshness pass | Medium | Three of the twelve "duplicates" lost the wrong copy: the detailed box was deleted and the stub kept. (a) The `tmp_path` box: the report said to delete item 6's pointer; the section 3 box with the test names and numbers was deleted instead, and item 6 now points at nothing. (b) Section 4's two light-theme boxes (what to re-author, why analytic contrast is not enough) were deleted for item 5's four-word stubs. (c) 1B.9's DWM corner-preference route was deleted as a copy of 1.9's composition-host box, which does not mention it. The report's own duplicate table disagrees with its counts | 1d16c74d; `Docs/Future_Work/Plan_Freshness_2026-11-12.md:50-70` |
| 26 | Plan, item 8b | Medium | Stale or contradictory lines: "D1 to D3 owed" (decided); "Agents compile the native module in their worktree" (the handbook and the operator say GitHub only); N2.1 lists work N0.9 did; N4.c still offers "D5.3's indirect service"; five of the eight boxes under N0.8 are notes with nothing to do. Eleven "landed" paragraphs sit in N0 and N1 as prose. No in-flight item names its agent (four agent branches were unmerged when this was written) | plan item 8b; handbook section 3 step 3 |

### Rules check (every line added in scope)

- Presets named, listed or counted in tests, tools or product code: none.
- Environment-variable flags: none in the product. `run_n06.py:78` only reads the environment to record it. The
  validated runs need `VK_ADD_LAYER_PATH` in the harness process (finding 5): a loader search path for a
  development harness, not a product flag, but it contradicts D6's sentence and must be admitted by name.
- Timers or polling in product code: none. `time.sleep` appears in two GPU tests (bounded loops that follow the
  render host's spacing) and in the SDK download retry.
- Per-frame cost at rest: finding 17. Spectrum's placement cache is one tuple comparison per frame (fine).
- Teardown and rebuild where a retarget was possible: none found; 1C.2 removed the one that existed.
- A test showing a window: none added. `run_n06.py:876` shows real windows by the invisible-window pattern (lead
  only). The pre-existing visible test is a box and an agent was on it when this was written.
- A weakened assertion: finding 14.

## 2. The High finding in full

**The conventions buffer is keyed by a wrapper that does not survive the call.**
`rendering/quick/render/gl_resources.py` keeps one conventions buffer "per context" in a registry keyed by
`id(QOpenGLContext.currentContext())` (`_context_key`, `_acquire_conventions`, `_release_conventions`, lines
137-190). For a context Qt created in C++ (Qt Quick's render-thread context) PySide makes a new wrapper whenever
Python holds no reference to the last one, and connecting `aboutToBeDestroyed` does not keep it. The repository
already says so: `rendering/quick/scene3d/waveform.py:175-176` ("a weak-only wrapper can disappear between
currentContext() calls on Qt Quick's render thread"), which is why the Waveform scene stores the wrapper.

Proved on the product's own registry with a context Qt owns (the global share context, an offscreen surface, no
window): `.artifacts/evidence/native_core/n1_4_conventions/20261112_fable_audit/` (`probe_context_wrapper_identity.py
--repo .`, output in `probe_output.txt`):

    wrapper kept after its last Python reference went (signal connected): False | same id: False
    ids of 8 currentContext() wrappers of ONE context: 3 distinct
    registry entries after 3 links in one context: 3 | buffers created: [1, 2, 3] | holds: [1, 1, 1]
    registry entries after deleting all 3: 3 | buffers still alive: [1, 2, 3] | stale program holds: 3

The contract (one entry, one buffer, three holds; nothing left after the deletes) fails on every line.
`tests/test_conventions_include.py:224` passes only because its `_Context` holds the context it created, which the
product never does for Qt Quick's context.

What this means in the product:

1. Where no owner holds the wrapper (Extruded Bubble, and the 3D transitions' resolves, OIT, defocus, motion and
   trails on the background node; Waveform is spared while its scene lives), each link of a program that declares
   the block creates another buffer, registry entry and signal connection, and `delete_program` finds no hold to
   give back. A mode switch or reload links again, so it grows for the life of the process. Each buffer is 16
   bytes; the count is unbounded. `tools/gl_object_ledger.py` cannot see it (the out-parameter blind spot already
   boxed).
2. An `id()` is reused as soon as its object is freed. A wrapper for another context (the second display, the
   Studio's preview) that lands on an address already in the registry finds the other context's entry and binds
   nothing: binding 17 is unbacked there. A release that hits such an entry can delete the buffer the current
   context still uses, which unbinds it. The OpenGL specification leaves reads of an unbacked uniform block
   undefined. NVIDIA returns zeros, which are exactly OpenGL's values, so no test and no run on the development GPU
   can see it. On a driver that returns anything else, `srpssConventions.x > 0.5` flips rows in the OIT resolve,
   the background capture, the defocus gather, Extruded Bubble's backdrop, blur, glass and trails, and Waveform's
   floor and sky.
3. The claim in cefbfa2b and in the plan ("one buffer per context, written once, released with its last program")
   is untrue on the path it was written for.

Risk rating: High because it is in the default renderer of accepted modes since today, is silent on the only GPU
the project has, and N1.6 is putting more programs through the same link path. The fix is small and belongs to an
Opus Medium slot, first thing (plan box under N1, with the probe as its negative control). Contract for the fix: the
registry identifies a context by something that lives as long as the context (the wrapper held in the entry, as
`waveform.py` does, or the native pointer); the buffer is bound in every context that links a holder; the proof runs
on a context Qt owns with the wrapper dropped between calls, and on two sharing contexts.

## 3. Next steps

### Is the order still right?

Yes in its spine (N0 and N1, N2, N2b, N3, the two tracks, the flip, then SMP's foundations), with four corrections:

1. **N1.6 is being done in the wrong order for its first consumers.** It runs "in N5's order" and is in flight for
   the substrate and Waveform. The first port is Spectrum (N2.5) and the next are the seven fullscreen transitions,
   the background node and the backdrop (N2b); Spectrum's shader and the Quick visualizer vertex sit seventh of nine
   groups, the transitions eighth, the hosts ninth. N1's whole purpose ("a port is a translation") is lost for the
   first two stages unless N1.6 takes Spectrum and the 2D quad next, then the seven transitions and the hosts, and
   only then the 3D substrate's remainder. The substrate step in flight should finish and merge; Waveform's
   conversion can wait behind Spectrum.
2. **N2.1 and the Python half of N2.3 do not wait for N0.6 or N0.7.** N2.1 is build plumbing (a product module
   tree beside the spike, the workflow taking its source folder, the product workflows calling it, the frozen probe);
   most of what the box lists was done by N0.9 or already exists in the spike (the exact-Qt guard at
   `native/spike_p1/src/module.cpp:652`, the DLL-origin report). The transport rule's Python side (Spectrum's
   fixed-layout native schema and its writer; `payload_schema` validated at the slot head by the Python reader,
   which reads it nowhere today) needs no C++ at all. Both can start tomorrow.
3. **N2.2 and N2.4 do wait, on two proofs that are not finished:** N0.6 under validation (the hazards found on
   `main` must be attributed to our module, the spike's scene or Qt before a host is designed on that device), and
   N0.3's three scenes (finding 4). N0.7's gate (iv) is synchronisation validation on the same host, so its verdict
   is not trusted until N0.6's hazards are attributed.
4. **N2.6 (the per-pass timer) is listed after N2.5 (Spectrum)**, but the port rule's (e) and D8 ("with the
   substrate, so every port is measured with it") need it at Spectrum's port. Either it moves before N2.5 or
   Spectrum's record uses the whole-frame time and says so. Its form is still provisional on N0.7 (D5.6 answer 4).

### What is genuinely blocking N2.1 now

Nothing technical. One decision by the lead: where the product module lives (the spike "stays evidence, never a
shipped renderer") and that `native-module.yml` takes the source folder as an input instead of the hard-coded
`native/spike_p1` (line 61). The rest of N2 is blocked as in point 3 above.

### What should be done before N2 that was not in the plan (now boxed)

1. The conventions registry (High, finding 1) and its two satellites (finding 2; the ledger's out-parameter box,
   which would have caught it).
2. N0.3's three scenes in the harness, on OpenGL, Vulkan and D3D.
3. N0.6 fails closed without the layer, admits `VK_ADD_LAYER_PATH` by name, and its hazards are attributed; D6's
   heading says "as measured" until validation is clean.
4. The hash seeds through `fragPixel` (finding 3a), before Waveform's and Extruded Bubble's parity tolerances are
   written.
5. Spectrum's native schema and the Python reader's `payload_schema` check (N2.3's Python half).
6. A frozen GitHub build on Qt 6.12 (finding 13) and the control for the narrowed handoff assertion (finding 14).
7. Offline Waveform hosts given a framed view (finding 8), before item 2's reactivity work resumes on those tools.

### What is redundant or should be cut

- N2.1's "SDK fetch scripted per Qt version" and "the GitHub workflow building the module": done by N0.9 (reworded).
- N1.4's box as worded: replaced by its remainder.
- N4.c's "D5.3's indirect service": retired with Qt 6.12 (reworded to QRhi's `drawIndirect` against the cull).
- Under N0.8: the indirect-draw, `DrawIndirectMulti`, shader-draw-parameter and device-fault boxes were notes
  filed as work; they moved to the boxes that consume them (N4.c, the modes track's rule, N3.6). The
  `@Slot(result=...)` box had nothing to do (the guardrail is standing) and was removed.
- `Docs/Future_Work/Plan_Freshness_2026-11-12.md`: applied, internally inconsistent, its line numbers dead. Delete
  it once the three restored boxes are accepted (the lead's call; not deleted here).
- The eight scene composite fragments need no N1.6 conversion: D5.2 deletes them. The ratchet should say so, so
  nobody converts them.

### The cap for the next working day

| Slot | Work, in order | Why |
|---|---|---|
| Opus High 1 (the harness; N0.7's agent continues) | Attribute N0.6's validation hazards (same host on Qt's own device with validation, objects named), then N0.7's correctness half (ii, iii, iv), then its measurements (i, v, vi), then N0.3's three scenes | One owner for `native/spike_p1`; every later Vulkan decision stands on a clean validated host; each step needs a GitHub build round by the lead, so one agent, serial |
| Opus High 2 (N1.6's agent, after its substrate step merges) | N1.6 for Spectrum and the 2D quad vertex, then the seven fullscreen transitions and the background and backdrop hosts; the hash seeds through `fragPixel` on the way | The first two stages' consumers; pixel-identity work is this slot's strength |
| Opus Medium 1 | The conventions registry fix with its probe as control, the `_link` holder test and fog's deletes, the ledger's out-parameter creates | The High finding; bounded repair with tests |
| Opus Medium 2 | N2.3's Python half (Spectrum's native schema and writer, the `payload_schema` check, test c of the transport rule); then the framed view for offline Waveform hosts; then the prepared neighbour's feed stopping at "prepared" | No C++, exact contracts already decided, each closes inside one window |
| Sonnet Medium (documents) | Move item 8b's eleven landed paragraphs into the decisions document as "As built" (as D4 and D6 were); amend D11 ("as taken") and D6 (the layer path); draft N2.1's and N2.3's box lists for the lead from the decisions; read Qt 6.12's source for the two validation messages (an image created PREINITIALIZED with OPTIMAL tiling; the render pass begin between two submissions) to help the attribution | Documents and research only; the plan stays the lead's |
| Lead | The validated N0.6 reruns and N0.7's build rounds; the frozen GitHub build on 6.12; N2.1's decision; the caller sweep on every merge (finding 9); Display 1 runs when it is on | Verification and builds are the lead's |

## 4. Plan hygiene

- **Narrative in item 8b.** N0 holds seven landed paragraphs and N1 four. They are records, not boxes; D4's and
  D6's went to the decisions document when their boxes closed and these should follow (Sonnet, next day). Not moved
  here: the lead and four agents were editing or reading that section.
- **Boxes without steps.** N0.7 was one box for six measurements (now sub-boxes from D9); N1.6 was "one box per mode
  as it is taken" with two agents on it and no box (now groups in consumer order); N1.8 named no use (now the four
  known ones); item 5 was four stubs (detail restored).
- **No owner written at in-flight items.** By their commits: `worktree-agent-a0f3a4769ed6cc726` is N0.7,
  `worktree-agent-a71b147cbdcf8e4bc` is N1.6's substrate step, `worktree-agent-a3ad1ee1135e0a81d` is the
  invisible-window guard (1C.2's side defect). The lead writes these at the items (handbook section 3, step 3); not
  added here to keep this branch's plan edits clear of the lead's.
- **A report kept as a document.** The freshness report (above).

## 5. What this audit changed in `Current_Plan.md`

Corrections only; no open box of today was deleted except the one named.

- Item 8b header: D1 to D3 are decided. Standing rule: the module is compiled by the GitHub workflow only.
  "What can start now" names N2.1 and N2.3's Python half.
- N0: new boxes for N0.3's three scenes; N0.4's remainder (the camera in the packet, D5.5's tests) and the offline
  Waveform hosts; N0.6 failing closed, the admitted layer path and D6's heading; N0.7 split into D9's six steps
  behind N0.6's attribution; under N0.8 the frozen build on 6.12 and the handoff control. The four note-boxes under
  N0.8 moved to N4.c, N3.6 and the modes track; the `@Slot` box removed (nothing to do; the rule stands in the
  agent rules).
- N1: new boxes for the conventions registry (High) and its holders; N1.2's line corrected (module-level sources;
  six composed programs on the ratchet); N1.4 reworded to its remainder; N1.6 ordered by first consumer with one
  box per group; N1.8 lists its uses.
- N2: N2.1 reworded to what is left; N2.3 gains its Python half; N2.5 carries R-197's rule and names its N1.6
  prerequisite and the timer.
- N3.6 and N4.c: the Qt 6.12 clauses moved in; N4.c's service wording corrected.
- 1C.2: a box for the prepared neighbour's per-frame feed. 1C.4: a box for R-192's enclosed axis and the unseen
  Display 0 change.
- Item 5, item 6 and 1A 1.9: the detail the freshness pass deleted is restored (from 1d16c74d's removed lines).

## 6. Not verified

- No "red before the fix" statement was re-run on old code (R-193, R-195, R-196, the display-move tests).
- The second context in finding 1's point 2 was reasoned from the probe (wrapper addresses are reused; the registry
  is keyed by them), not reproduced with two windows: no window may be shown and no second context Qt owns exists
  without one.
- N0.6's rounds and evidence folders were read as recorded; nothing was built or run on Vulkan.
- The whole suite was not run. `main` beyond `43c0edf8` was not read.
