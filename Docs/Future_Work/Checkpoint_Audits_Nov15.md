# Checkpoint audits, 15 Nov 2026

## Checkpoint audit 1: de68ede75 (N5.2b), b77e7ce0a (R-221), ae9397e97 (1D.12 and R-222)

Medium effort, on `main` at 98c376b5c. Nothing was fixed. Every finding below has a failure scenario and the way
it was proved.

Focused runs on the merge state passed: 41 passed, 1 skipped (`test_fullscreen_visualizer_edges`,
`test_native_background_layer`, `test_hover_glyph_dwell_fade`, `test_visualizer_control_hint_once_per_mode`,
`test_visualizers_fullscreen_mode_pill`, `test_widget_position_follows_layout_writes`). The transition sweep also
passed: 120 passed (`test_qtquick_vhs`, `_surface_tension`, `_organic_transition_renderers`, `_melt_surface`,
`_melt_shader_contract`, `_liquid_lens`, `_future_transition_gl`, `_chromatic_shear`, `test_transition_registry`).

The auditor reran each negative control on its own worktree, breaking the fix and then restoring the file each time:

| Merge | Fix disabled | Result |
| --- | --- | --- |
| R-221 | `held = False` in `scene_controller._apply_visualizer_presentation_items` | `test_fullscreen_hide_borders_draws_no_frame_pixel_on_any_edge` fails: wallpaper on the left, top, right and bottom edges at a shift of (1, 1) |
| N5.2b | `_flat` made the identity in `native_background.py` | `test_an_item_quad_transition_gives_the_core_its_own_values_arrays_flat...` fails: 20 pool entries instead of 80 numbers |
| R-222 | `_reload_widgets_tab_after_layout_write` returns at once | 3 of the 5 tests in `test_widget_position_follows_layout_writes.py` fail; the built page shows "Top Left" after the Arrange move |
| 1D.12 C | `if (controlHintShown) return` disabled in `VisualizerPresentation.qml` | 2 of the 4 tests fail; the second visit peaks at 0.9 |
| 1D.12 B | `HoverGlyphReveal._show()` returns at once | 3 of the 4 tests fail; the glyphs never dwell out |

### Critical

None.

### High

**H1. A Corner chosen in Settings wipes all of a Fullscreen overlay's Fullscreen Edit placement.** It does so
irreversibly, unlike ordinary widgets, and the previously tested behaviour changed without a record.

- **Where:** `ui/tabs/visualizers_fullscreen_page.py:213-229` (`_set_corner`) and
  `core/settings/fullscreen_overlays.py:386` (`clear_overlay_placement`), from ae9397e97.
- **Failure scenario:**
  1. In Fullscreen Edit, the operator makes Now Playing larger (`scale` 1.25) and resizes its artwork
     (`child_geometry.artwork.width_scale` 1.5) without moving it. `overlay_placement_moved` is then true, and the
     Corner choice reads Custom.
  2. In Settings, the operator picks another corner, or even the same stored corner.
  3. `_set_corner` calls `clear_overlay_placement`, which returns every `PLACEMENT_KEYS` member to its canonical
     default: the offset, scale, text box, `base_width` and the child records. The page saves, and the CUSTOM entry
     is disabled, so the authored size and layout cannot be selected back.
- **Contradictions:**
  - Before this merge, `test_visualizers_fullscreen_mode_pill.py` asserted that a corner change kept `scale == 1.25`
    and the artwork's `width_scale == 1.5`, and only rebased the offset. The merge rewrote that assertion to expect
    the placement cleared.
  - The plan's box for A says "Choosing a named position afterwards still leaves custom geometry the way other
    widgets do", and the ordinary-widget test in the same merge asserts exactly that
    (`tests/test_widget_position_follows_layout_writes.py:107-117`: a named position keeps the saved custom geometry
    and CUSTOM stays enabled). The new docstrings claim to copy the ordinary widget ("as an ordinary widget leaves its
    CUSTOM geometry for a named position"), but the code does the opposite.
  - No "Changed on" note was added for the reversed behaviour.
  - `rebase_offset_for_corner` can now be reached only when every placement member is at its default, which means a
    zero offset. The module docstring's rule, "changing it rebases the offset", is therefore dead for any moved
    overlay.
- **Proof:** read from the diff of ae9397e97 (the old and new assertions in
  `tests/test_visualizers_fullscreen_mode_pill.py`). The new test
  `test_an_overlay_moved_in_fullscreen_edit_reads_custom_until_a_corner_clears_it` picks the seeded, unchanged corner
  and asserts that every placement key returns to canonical.

### Medium

**M1. A display move back to a display whose Visualizer shell already exists replays the 3D control hint (1D.12
C).** The plan's box "display moves ... do not reset the set" does not hold.

- **Where:**
  - `rendering/quick/scene_controller.py:2549-2634`: `transfer_visualizer_to` and `_adopt_visualizer_transfer` reuse
    the retained shell (the comment at 2594-2599: "a later hop reuses this one inactive shell").
  - `rendering/quick/scene_controller.py:3247`: `_project_visualizer_control_hint_shown` runs only when the root is
    created, in `set_visualizer_control_hint_memory`, and in the controller's own reveal handler.
  - `widgets/spotify_visualizer/visualizer_host_binding.py:601-674` (`transfer`) and
    `engine/display_manager.py:4057-4071` (`_transfer_quick_visualizer_unit`): neither runs
    `_configure_quick_visualizer_input_admission`.
- **Failure scenario:**
  1. The Visualizer starts on Display 1 in framed mode A; hovering there plays A's hint.
  2. The operator moves it to Display 2. Display 2's root is built and correctly reads "shown".
  3. The operator switches to mode B. The mode edge projects B as not shown to both displays.
  4. Hovering on Display 2 plays B's hint and adds B to the session set. Only Display 2's root is re-projected.
  5. The operator moves the Visualizer back to Display 1, which reuses its retained root, still showing
     `controlHintShown == false`. The next hover there plays B's hint a second time.
- **Proof:** the probe `.artifacts/evidence/visualizers/shared/checkpoint_audit1/20261115_hint_return_hop/probe_hint_return_hop.py`
  ran two hidden production hosts with the real `transfer_visualizer_to`. It printed:
  `after the return hop: display 1 root reused = True controlHintShown = False (the set holds the mode: True)`.
  The replay that follows from `controlHintShown == false` is what the merge's own negative control shows: 0.9 peak
  on a later visit.
- **Masked by:** `tests/test_visualizer_control_hint_once_per_mode.py:110-116`. That test says a display move
  rebuilds the root and stands in for it with `_admit()`, which calls `set_visualizer_control_hint_memory`. A real
  transfer neither rebuilds the root nor makes that call.

### Low

**L1. The N5.2b tie budget limits only the number of pixels, not how far they are off, so a regression confined to
those few pixels passes.**

- **Where:** `native/core/python/transition_route_check.py:66, 246, 311-318, 341-345`.
- **Failure scenario:** for the five `NativeFragmentPass` transitions, rule (a) and rule (b) both pass while
  `_over(..., VULKAN_TOLERANCE) <= TIE_PIXELS` (8 pixels in a frame). The levels of those pixels are not bounded. A
  hash or threshold regression that flips one slice edge of Chromatic Shear to the wrong picture over 8 pixels a
  frame, at 255 levels, still passes.
- **N5.2a's seven are not exposed:**
  - Rule (a) still requires `equal` for keys outside `N52B_VARIANTS`.
  - Rule (b) still requires `max_level <= VULKAN_TOLERANCE`.
  - The key parsing (`v.split("_", 1)[1]` on `dpr<r>_<variant>`) keeps every one of the seven on the strict branch.
  - The references for all variants now come from `product_capture` at the run's dpr, but equality is still
    required, so nothing is hidden.
- **Proof:** read from the code. A cap on the level of the tie pixels (for example, the measured worst of 2 levels)
  would close it.

**L2. The test for the DisplayManager's part of 1D.12 C uses hand-built stubs and compiles methods out of the
source.**

- **Where:** `tests/test_visualizer_control_hint_once_per_mode.py:133-188`. It pulls
  `_configure_quick_visualizer_input_admission` out of `display_manager.py` through `ast` and `exec`, and drives
  `SimpleNamespace` stubs for scenes and inputs.
- **Failure scenario:** if the method moves to a helper or starts reading another manager attribute, the test fails
  for that reason alone, or is silently bypassed. It is also contrary to Agent_Worktree_Rules: new tests use
  `tests/_display_manager_doubles.py`.
- **Proof:** read from the test.

### Checked, no finding

- **N5.2b, OpenGL path.**
  - Each of the five `render` methods now packs `block_values`. For the names `bind_frame` also writes (`uMatrix`,
    `uItemSize`), the values are the same.
  - `u_target_px` is `frame.item_pixels`, as in N5.2a.
  - `uShow` reaches GL only as 0: values 1 and 2 still go to `draw_image`.
  - Surface Tension's padding with zeros is safe: the fragment reads only `uPoolCount` entries (`surface_tension_program.py:99`).
  - The integer hashes take only whole-number arguments (`k` from `floor`, `kf = k + 2`).
  - VHS's integer row equals `floor(uv.y * L)` except at exact ties.
  - `analog_signal`'s `uint(int(x))` changes only grain keys for x below 0. Edge Bloom includes that GLSL but never
    calls `signalDropout`.
  - Liquid Lens now computes `lens_state` on the plain-picture frames too; it clamps progress and is safe there.
- **N5.2b, `uShow`.** Each `_shown` rule is the old early-return condition moved verbatim. Melt Drip has no `uShow`:
  its fragment draws the picture at each end of the run itself, on both backends. The native renderer is resolved
  once per run (`native_background.py:261`), not per frame.
- **R-221.**
  - The overlays are shifted once. The layer's +S, the loader's -S and the overlay loader's +held add up to +S
    exactly when the card is held, and to the layer's +S alone otherwise.
  - Default to Hide Borders: the flag is set before `set_presentation`, so no frame is drawn shifted.
  - Exit to the ordinary card: covered by the edges test.
  - Pixel shift turned off mid-shift: the held value derives from the same `Translate`, so the card stays put and
    the overlays return to 0.
  - Display move: `_adopt_visualizer_transfer` re-applies the record, and `presentationActive` false defeats the
    early return, so the target's flag is recomputed. The source's flag stays true, but only on an inactive shell.
  - `mapToScene` (native route `_host_window_origin`) includes item `transform` lists, so a held card maps to the
    display origin whatever the shift.
  - No geometry animation (`Behavior on x/width`) exists that could jump at the flag flip.
- **R-222.**
  - `self.__dict__.get("widgets_tab")` never constructs a dormant tab.
  - Arrange emits `applied` only when it wrote. Reset emits only when it restored.
  - Nothing else reloads the Widgets tab on a `widgets` write, so there is no double reload.
  - Save slot merges onto fresh `settings.get("widgets")`, so its slot payload survives a later Widgets save.
  - The one way to lose an edit is a 200 ms coalesced Widgets edit still pending when a Layout write lands. Reaching
    a Layout write takes several clicks, so this is not practical.
- **1D.12 B.**
  - `HoverGlyphReveal` runs one finite `SequentialAnimation`, started on an edge, and nothing at rest.
  - The dwell multiplies `glyphRow`'s or `actions`' opacity, never a member's own `opacity` or `enabled`, so a faded
    glyph's hit area stays live. Its test brings the set back by hovering a faded glyph.
  - With Show Glyphs off, the reveal is never hovered and the members' own opacity is 0.
- **1D.12 C, lifecycle.** The set is the engine's own plain set, handed over before any display binds
  (`screensaver_engine.py:1160`). It is referenced by the manager and the scene controllers; nothing persists it and
  nothing leaks across generations. `controlHintRevealed` connects once per root to a plain method, not a
  `@Slot(result=...)`.
- **Rules.** No env flags, no timers or polling, nothing that vanishes, the R-63 window untouched, and no preset
  names in any of the three diffs.

### Not verified

- R-221 on Vulkan with the native route in the product. The edges test is a GL hidden host. Whether a pixel-shift
  step at rest re-cards a non-held (Default) native card before the next frame is a property that predates R-221
  and was not measured.
- 1D.12 A's "live after an Edit Save while Settings is open": only Layout tab writes reload the Widgets page.
- The N5.2b route check itself was not rerun; it is a native-module run.

## Checkpoint audit 2 (N3.1, High)

Branch `worktree-agent-a72f37a9dc96d7c05` at 27c3e0b1 against `main` (scene targets, C++ at ABI 17, D14 points 1 to
13), High effort. Nothing was fixed. The auditor merged the branch into its own worktree to run the branch's code, and
used the branch's GitHub-built module (`release/native_module`, manifest commit 27c3e0b1). No build was started.
Evidence is in the auditor's worktree under `.artifacts/evidence/native_core/n3_1/20261115_audit2_*`.

**Verdict: do not merge as is.** The single-sampled gate is sound and reproduces on both backends. Two things block
the merge:

- **H1:** the multisampled path has an unsynchronised write on Vulkan in every steady frame. The plan box and D14's
  "as built" claim validation is clean there. They are clean only because the gate never draws consecutive
  multisampled frames with the validation layer loaded.
- **M2:** the branch turns a native test red.

**Reruns on the copied module:**

| Rounds | APIs | Result | Negative controls |
| --- | --- | --- | --- |
| parity, msaa | OpenGL, Vulkan | PASS (rule (a) 5 exact, rule (b) 16 exact) | Sample-0 control wrong on exactly 6720 band pixels. Clamp control: 8 removed draws as 4, and the state reports 4. |
| rest, resize, retire | both | PASS. Rest: thread probe 2 syncs, 0 with a Python thread state. Resize: 5 reallocations against the control's 7. Retire: every count back to 0. | |
| prime_control | Vulkan | PASS | 7 `SYNC-HAZARD-READ-AFTER-WRITE` (Qt defect C) with the prime skipped, 0 with it |
| cost | both | **FAIL** | OpenGL: GPU-time sample counts too low (M1). Vulkan: unexcused synchronisation hazard (H1). |

The 4K 4x-minus-1x figures reproduce: OpenGL 0.45 ms, Vulkan 0.56 ms (D14 points 11 and 13).

**Focused tests:**

- `test_native_scene_targets`, `_core_loader`, `test_scene3d_target`, `_foundation`,
  `test_oscilloscope_instanced_beam_contract` and `test_waveform_floor_give`: 108 passed.
- The native sweep (`test_native_*` except `_sdk_fetch` and `_spike_n03`, `test_visualizer_owner_render_parity` and
  `_prepared_reveal`): 334 passed, 1 failed (M2).

### Critical

None.

### High

**H1. Every steady multisampled frame on Vulkan writes a scene target's colour resolve without synchronisation.**
Synchronisation validation reports a write-after-write hazard (Qt 6.12.0's defect B). The project's rule excuses
defect B only in `discard` phases. D14's "as built", and the plan's retirement box ("Vulkan validation with
synchronisation validation clean through create, resize, capture, multisample and teardown"), say validation is clean,
but it is not.

- **Where:**
  - `native/core/src/scene_targets.cpp:683-684`: a read multisampled attachment gets a QRhi resolve texture.
  - `native/core/src/mode_content.cpp:2940-2943`: rule C primes only the multisampled colour (`loadedColour`) and the
    depth before `beginPass`. Nothing primes or orders the resolve textures.
- **Cause:** QRhi's offscreen render pass gives a resolve attachment `initialLayout UNDEFINED` with no
  `VK_SUBPASS_EXTERNAL` dependency (defect B in `native/core/python/vk_validation.py`). The run's begin therefore
  transitions the resolve with no ordering against the previous frame's resolve store.
- **Failure scenario:**
  1. A scene target at 4x has a colour that is read. Extruded Bubble's shape: a capture between two runs, which is
     what N5.6 will draw.
  2. The run after the capture resolves `scene.colour` again, and nothing reads it before the next frame.
  3. The next frame's first run begins with an unordered layout transition on that resolve.
  4. On a driver that overlaps frames, this is a race on the resolve's memory.
- **Proof:**
  - `scene_target_check.py --rounds cost --require-validation` (`20261115_audit2_cost`) gives 10
    `SYNC-HAZARD-WRITE-AFTER-WRITE` on `VkImage[srpss core scene target scene.colour resolve]`, unexcused (the
    validation layer stops counting at 10).
  - The probe `20261115_audit2_probes/probe_targets.py` draws the ordinary harness scene for 40 consecutive records,
    each with a setting change: 10 hazards at 4x, 0 at 1x (the control).
- **Why the gate did not see it:**
  - The parity and msaa rounds draw a few records with readbacks between them, and the readbacks order the resolve.
  - The branch's `20261115_final_gate` left out the cost round.
  - Its cost evidence (`20261115_round3_quiet_cost`) ran without the layer (`layer_loaded: false`).
- **Round 2 saw the same hazard** on resolves no pass samples. It was settled by not creating those resolves, which
  hides the cause rather than fixing it.

### Medium

**M1. The cost round cannot pass on OpenGL, and the gate that passed left it out.**

- **Where:** `native/core/python/scene_target_check.py:95-96`. A fixed `COST_FRAMES = 240` must yield
  `COST_MIN_SAMPLES = 30` GPU times per count, but Qt's OpenGL backend reports a time only for frames whose query was
  ready.
- **Failure scenario:**
  - The documented gate command (default rounds include `cost`) prints `N31 VERDICT FAIL` on a quiet GPU.
  - On a quiet GPU (nvidia-smi 0 %), the auditor's run got 24 samples at 2560x1440 4x, and 16 and 10 at 4K.
  - The branch's own `20261115_round3_quiet_cost` and `_round3_cost` also failed `3840x2160_timed`.
  - So the "Cost and threads" box rests on runs whose verdict was FAIL, and the passing gate did not include it.
  - This is the N2.8 flake class that this branch fixed in `generic_mode_check.py` (draw until the times arrive), but
    not here.
- **Proof:** `20261115_audit2_cost/summary.json`: `opengl cost: 2560x1440_timed, 3840x2160_timed`.

**M2. The branch turns a native test red.**

- **Where:**
  - `native/core/src/scene_targets.cpp:129`: `return textureBytesPerSample(targetRhiFormat(format));`.
  - It matches the vexing-parse lint in
    `tests/test_native_core_host.py::test_no_core_source_declares_a_function_where_it_meant_a_sized_object`.
- **Failure scenario:** the merge lands a failing test in the native suite. Either the lint's return-statement
  exclusion or the line has to change. The line is a false positive.
- **Proof:** `pytest tests/test_native_core_host.py` on the merge gives `1 failed`, with the line above as the only
  hit. Main has no `scene_targets.cpp`.

**M3. A new program's explicit target size is silently overridden by an earlier `target_size`.**

- **Where:** `native/core/src/mode_content.cpp:1557-1590` (`setTargetSize` appends to `m_targetSizes`) and `:1642-1648`
  (`sync` applies it to every later program's targets with that name). `setProgram` (`:1376-1405`) never clears it.
- **Failure scenario:**
  1. An owner sizes Bubble's ambient target with `NativeMode.target_size`.
  2. The owner later sends a program (a rebuild, or another mode on the same item) that declares the target at a new
     explicit size.
  3. The old size is still drawn, and `u_target_px` follows it, so nothing reports a problem.
- **Proof:** `probe_targets.py`, on OpenGL and on Vulkan:
  - `target_size("ambient", (400, 220))`, then a program declaring `(500, 280)`: the state reports content
    `[400, 220]`, allocation `[448, 256]`.
  - The same probe shows that `target_size` itself is correct: `layout_generation` is unchanged (the pipelines are
    kept), and every texture equals a fresh item's at 400 x 220.
  - No harness round or test calls `target_size`. This build addition, which the lead accepted, had no proof before
    this probe.

**M4. A program may sample a target before any pass in the same record drew it, and the result depends on the sample
count.**

- **Where:**
  - `native/core/src/mode_content.cpp:646` (`checkTargetSampler` refuses only the pass's own target) and `:971-990` (an
    ordering check exists for captures only).
  - `:2844-2862` (`recordNearest` looks only forward from the run) and `:2868` (a readback forces every nearest
    resolve).
- **Failure scenario:**
  - Take the program `[a surface pass sampling "scene.depth", then the passes on "scene"]`. Admission accepts it.
  - **1x:** the surface pass reads the previous frame's depth. On the first frame the depth is a texture no pass has
    written yet.
  - **4x:** the nearest resolve is never recorded, because no later pass reads it. `depthNearest` is never written, so
    the pass reads undefined memory in every frame.
  - A target that is declared and read but never drawn behaves the same.
  - The harness cannot see this: its readback forces the nearest resolves (`readback && !laterRun`), so `scene.depth`
    in a readback is not what such a pass samples.
- **Proof:** read from the code. No consumer declares such a program yet; N5.6 is the first.

**M5. N3.1 adds heap work to every drawn frame on the render thread.**

- **Where:**
  - `mode_content.cpp:3096-3097`: `noteTargets(m_targets.stateJson(rhi))` on every record of a content with targets.
    It builds a JSON object per target, takes `removedMutex`, copies its list and then takes `m_textureReportMutex`.
  - `scene_targets.cpp:532` and `:409-423`: `sync` rebuilds `supportedSampleCounts` (QRhi's list by value, plus the
    control's list under a mutex) on every record.
  - `mode_content.cpp:2940`: `loadedColour` returns a new `QList` per run.
  - `mode_content.cpp:2338`: `passTargetSizes` returns a new `QList` per pack, even for N2.9 programs without
    targets.
- **Failure scenario:** for a 3D mode animating at 60 fps, dozens of allocations a frame on the render thread, two of
    them under mutexes the GUI thread also takes (`state()`). This goes against the brief's "nothing allocated per
    frame". Nothing happens at rest, which the rest round confirms.
- **Proof:** read from the code. `pack()` already built `m_facts` JSON per frame before N3.1, so N3.1 adds to an
  existing habit rather than starting one. The cost was not measured.

### Low

**L1. A grow re-buckets the other axis downward with no hysteresis.**

- **Where:** `native/core/src/scene_targets.cpp:326-329` (a grow returns `bucketed` on both axes).
- **Failure scenario:** on a diagonal resize, one axis grows while the other dips by one bucket. The allocation
  shrinks on that axis at once and grows back on the next small move. That is one extra reallocation per dip.
- **Proof:** `alloc_probe.py` through the module's GPU-free entry, needed sizes (1000, 1000), (1030, 950), (1030, 970):
  allocation (1024, 1024), then grown to (1088, 960), then grown again to (1088, 1024).
- **Possible fix:** a grow to the larger of the current and needed bucket per axis.

**L2. The content viewport function is not where D14 point 2 and the plan put it, and there is no scissor.**

- **Where:** D14 point 2 and the plan's `conventions.h` box. The function is `contentViewport` in `scene_targets.h:110`
  and `.cpp:340`, and no pass sets a scissor.
- **Failure scenario:** a full-screen triangle is clipped to the viewport, so nothing is wrong today. N3.2's points,
  lines or a guard-band rasteriser could write into the slack, which a linear read past the content's edge then
  samples.
- **Proof:** read from the code. Both backends' answers are tested GPU-free in
  `test_the_content_lies_at_the_images_bottom_rows_on_both_backends`.

**L3. Harness controls the plan names are missing or weaker.**

- **Where:** `scene_target_check.py:91`, and the parity round.
- **What is missing:**
  - Rule (a)'s negative control ("the content placed at the image top: the edge reads differ") is not built.
    Placement is still discriminated by the `slack_holds_the_far_plane` analytic check and by the comparison with the
    Python oracle.
  - There is no bucket-aligned size: 480x270 and 720x405 are both unaligned.
  - The drag steps 2 px, not 1 px.
  - The resize control re-buckets at every change instead of using a 1 px bucket.
  - The "item destroyed mid-allocation between steps" and "scene graph invalidated" retirements are not exercised.
    Every step runs in one record, and `release()` covers both paths by construction.
- **Proof:** read from the harness.

**L4. The documents disagree with the code.**

- `Docs/Reference/Scene3D_Resources.md:222`:
  - It says "rgba8 or rgba16f", but r16f and r32f are also admitted.
  - It says "always one sampled D32F depth texture", but depth is optional.
- `native/core/shaders/scene_capture.frag:5-6` still says the depth is "its resolve: one sample's depth, D14 point
  8". It is the nearest resolve (D14 point 10).
- D14 point 3 has the counts "join composite_live and the destruction barrier's reading". The barrier reads only
  in-flight jobs (`loader.py:308`, audit N38 M3), so the counts reach `composite_live` only.
- The plan's sampling-owner box cites `tools/conventions_identity.py`. The branch's before and after compare as
  "ALL IDENTICAL" (rerun by the auditor), but that tool forces every `SceneTarget` to one sample
  (`owner_render_parity.single_sample_scene_targets`), so it cannot see a sample request.
  - The real proof of "no pixel moves" is the GPU-free `test_every_visualizer_request_is_its_former_expression`.
  - That test does not call `shockwave_quality`, whose `scene_samples(detail)` is correct by reading.

**L5. If a resize step fails, the target's render-pass descriptors are destroyed before the pipelines built over
them.**

- **Where:** `scene_targets.cpp:611-613` (`releaseTarget` on a failed step), with the pipelines released only
  afterwards at `mode_content.cpp:2813-2817`.
- **Failure scenario:** a `create()` failure during a same-layout resize (`newLayout` false). This inverts the order
  that `scene_targets.h:22` states. On Qt 6.12's OpenGL and Vulkan backends, a pipeline's `destroy()` does not touch
  its descriptor, so nothing goes wrong today.
- **Proof:** read from the code.

### Checked, no finding

- **Ownership and retirement:**
  - `SceneTargets` is owned by `ModeContent` and released in `release()` after `releasePipelines()`.
  - A new layout releases the pipelines before `allocateStep` drops the old descriptors (`syncTargets`).
  - Counts return to zero after a no-target program and after the item's destruction, on both backends with
    validation.
  - Readbacks QRhi may still write into are kept until done.
  - Every QRhi `create()` result is checked: textures, render targets, the nearest resolves' and the capture's
    targets, and every pipeline, SRB and buffer through `created()`.
  - A failed allocation is latched, so it is not retried per frame.
- **Bounds:**
  - `results[kMaxSceneTargets * 7]` covers 4 colour, the depth's nearest resolve and the 2 captures per target.
  - `seen`, `drawn`, `captured`, `cleared`, `targetClears` and `nearest[][]` are all indexed below `kMaxSceneTargets`
    or `kMaxTargetColour`.
  - `kMaxModePasses = 16` is the only pass limit, in C++ and Python.
- **Bucket and hysteresis:** grow at once and shrink two buckets below match D14 (beyond L1). The drag reproduces 5
  reallocations against 7.
- **Per-backend viewport:** `isYUpInFramebuffer` gives y = H - h on OpenGL and 0 elsewhere. Placement is proved by rule
  (a) exact against the Python GL bottom-left and by the slack check.
- **`primeDepthForLoad`:**
  - It records only outside a render pass.
  - Its barrier covers DS read and write at both fragment-test stages.
  - It updates QRhi's layout.
  - Its control is real: 7 RAW hazards without it, 0 with it.
- **`scene_nearest.frag`:**
  - `fragTexel` is `gl_FragCoord` on core targets (fragment flip 0, F1), so source and destination texels match.
  - `uSamples` is the clamped count passed to `newTexture`.
  - The analytic nearest is within 8.7e-8 at 2x, 4x and 8x. The sample-0 control is wrong only in the first band.
- **The clamp:** the largest supported count not above the request. The count created is the count reported (8
  removed gives 4).
- **The additive blend:** ONE, ONE on every channel. The ambient light is exact against Python's added light (rule
  (a)).
- **Size change without a new program:** works, with the pipelines kept (M3's probe). Only its interaction with a new
  program is wrong.
- **Threads:**
  - Explicit sizes and read requests cross under `m_mutex`, and the readback and state under
    `m_textureReportMutex`.
  - The thread probe shows zero calls with a Python thread state.
- **ABI 17:** `abi.h`, `EXPECTED_ABI`, `test_native_core_build` and `_loader` agree. No ABI-16 assumption is left.
- **`scene_samples` reroute:** the six callers equal their former expressions:
  - Extruded Bubble and Sphere: `max(1, overlay)`.
  - Extruded Spectrum: `overlay * (2 if smooth)`.
  - Neon Lake: `overlay`.
  - Waveform: a fixed 4.
  - Oscilloscope: a fixed 1, in both `warm` and `scope`.
- **Rules:** no env flags, timers or polling, no preset names, and the protected clip commits are untouched.

### Not verified

- **`cost_parts` and `python_cost`** were not rerun. The 4K figures match D14 point 13 without them.
- **Real windows:** only hidden hosts were used, and no Display 1 rehearsal.
- **Whether H1 corrupts pixels on this GPU:** not tested. The proof is the validation layer's.
- **The fix for H1** (a pre-pass barrier for the resolve textures, as rule C does for colour) was not tried.

## Checkpoint audit 3: 0382665e6 (N5.1 Spline Curve) and 6a54f5415 (1D.14), Medium

The audit ran on the 3c13c76ed tree (unchanged since 0382665e6 in every N5.1 file it read) with the ABI 17 module
copied from the main checkout, and nothing was built. It found no critical or high finding, one medium and two lows,
all in N5.1. 1D.14 has no finding. The probes are in
`.artifacts/evidence/native_core/checkpoint_audit_3/20261115_probes/` (run from the repository root).

### Critical

None.

### High

None.

### Medium

**M1. `rule_a_verdict` lets through errors the per-pixel proof does not explain**
(`tools/visualizer_replay/owner_render_parity.py:357-370`).
- **The gap:** any pixel 1 level off counts as "fill", with no limit on how many there are or where they sit, and
  any pixel 2 or 3 levels off counts as "edge", whether or not it is on an edge. The proof (D12, "As built: Spline
  Curve") explains a 1-level error only on translucent pixels (`0 < a8 < 255`). On opaque pixels, transparent ones and
  the card's dark fill, the premultiplied rounding is exact, so a difference there is a real regression. It also
  explains edge pixels only at the boundary between the core's triangle and the Python quad.
- **Failure scenario:** a native regression that moves every pixel by 1 level passes rule (a). Examples are a
  `u_fade` packed as 254/255, a hue offset rounded differently, or a colour converted twice. So does a fixed 10-pixel
  artefact of 3 levels inside the card in every frame. `tests/test_native_devcurve.py:294` already accepts 17,000
  pixels at 1 level in one frame.
- **Proof:** `rule_a_probe.py` sends synthetic runs through the tool's own `frame_differences`:
  - A +1 shift on all 20,000 pixels of 60 frames (opaque fill, opaque bar and background) gives `pass: True`.
  - The fixed 10-pixel, 3-level interior artefact in every frame gives `pass: True`.
  - The control, one pixel at 4 levels, gives `pass: False`.
- **Suggested direction (not built):** allow the fill level only where the Python reference's alpha is strictly
  between 0 and 255, require exact pixels elsewhere, and keep edge pixels within a pixel or two of a lit/unlit
  boundary. The reference frames already carry alpha.

### Low

**L1. The by-value array test does not scan every product shader**
(`tests/test_native_devcurve.py:188-202`).
- **The gap:**
  - It scans only the `.frag`, `.vert`, `.comp` and `.glsl` files in three folders. It misses the 12 fullscreen
    transition fragments, which are Python strings baked to SPIR-V packs in
    `rendering/quick/qml/shaders/transitions/` and drawn on Vulkan by the core (N5.2a). These are burn,
    chromatic_shear, crossfade, liquid_lens, melt_drip, particle, ripple, slide, surface_tension, vhs,
    warp_dissolve and wipe.
  - Its pattern misses a size that is not a literal (`float c[N]`), the `float[96] c` form, and an indented
    definition.
- **Failure scenario:** a transition, or a mode shader that sizes its curves with a `#define`, takes back the
  by-value copy that cost Spline Curve 1.97 ms on Vulkan, and the test stays green.
- **Proof:** `by_value_probe.py` lists the 12 unscanned transition sources (none has the pattern today, by a broader
  regex) and shows that the test's regex misses the three forms, which a broader one catches.
- **The negative control holds:** the test fails on the first parent's `devcurve.frag`, which this audit ran itself.

**L2. A generic program the core refuses is tried again at every update**
(`rendering/quick/visualizer/native_route.py:670-688`).
- **The cause:** `_ModeContent.bind` defers the real `program` and `bind` to the first `settings` call, inside
  `_sync`'s frame stage. A `ValueError` from `NativeMode.program`, such as settings that do not fit (D12 point 4),
  therefore becomes a `_FrameFailure`. The route retries every frame failure at the next update. Before N5.1, the
  Spectrum program loaded in `bind`, which is the setup stage, and stayed latched until an input changed. The route's
  own docstring (`sync`) still says the program is a setup input.
- **Failure scenario:** a Spline Curve activation whose settings the core refuses. Each new frame repeats the
  program JSON, the pack hand-over and the refusal on the GUI thread for the whole activation. The item stays faded
  out and the failure is logged once, so nothing visible is wrong, but the cost repeats on every frame.
- **Proof:** `route_probe.py` runs the route on the test doubles with a `program` that raises. Over 30 updates with
  one identity and unchanged inputs, `program()` was called 30 times, with `failures` at 1 and the stage `frame`.

### Checked, no finding

- **The OpenGL product pixels are unchanged against the merge's first parent.**
  - `tools/conventions_identity.py record --part modes --only devcurve --offers` was recorded on the merge tree and
    again with the first parent's `devcurve.py`, `devcurve.frag` and `devcurve.frag.qsb` checked out.
  - `compare` reports ALL IDENTICAL on 5 runs × 549 frames (variants a and b and the three audio-block-size offers),
    with the same GL call counts.
  - Evidence: `.artifacts/evidence/native_core/checkpoint_audit_3/20261115_python_gl_identity/`.
  - The extracted functions match the inline code they replace member for member. The three unwritten members
    written as 0 equal the zero-at-link block.
- **One generic item beside Spectrum's:** `_content_of` makes one item per kind, and `prepare` makes both.
  `route_probe.py` switches Spectrum → Spline Curve → Spectrum → Spline Curve and finds the following:
  - Each unbind hides the outgoing item at fade 0 and then unbinds it.
  - The generic program loads once. The second Spline Curve activation sends settings, then bind, and no program.
  - Spectrum's program also loads once.
  - Each first frame is placed at fade 0, and `close` destroys both items.
  - The core drops the frame a previous stream left (`stream_source.cpp:182`), so a new binding never draws a stale
    frame.
- **`_admission_flags`:**
  - `FLAG_SOURCE_CURRENT` is read only by the core's admission (`stream_source.cpp:171-172`).
  - Setting it for a mode where `requires_authoritative_first_source` is false gives exactly
    `render_contract.snapshot_is_render_admissible`: that rule also needs `present_frame`, and the core still
    checks it.
  - Stale or foreign frames are still refused by the reader's identity check (generation, activation and mode code
    in `expect`).
  - Spectrum keeps the frame's own bit, which the test control checks.
- **Tests:**
  - `test_native_devcurve.py` (10, with the module), `test_native_visualizer_route.py`,
    `test_native_core_spectrum.py`, `test_shader_derivatives.py`, `test_native_packet_reader_sources.py`,
    `test_quick_backend_owner.py` and `test_visualizer_viewport_scaling_contracts.py` all pass: 105 tests.
- **1D.14, no save loses a placement.** `placement_probe.py` runs the owner and Fullscreen Edit's own `draft_value`,
  for both overlays:
  - A corner chosen from a moved overlay keeps `{corner, offset}` as `custom_position` and keeps the scale.
  - A Fullscreen Edit that only resizes keeps the record. CUSTOM then restores the old position with the new scale.
  - A Fullscreen Edit move at the new corner reads CUSTOM. The next corner choice keeps the newest position.
  - A save while CUSTOM shows keeps the placement members (`test_every_control_writes…`, lines 130-137).
- **Fullscreen Edit never writes `custom_position`:** `PARTS`' keys equal `PLACEMENT_KEYS` (asserted at
  `fullscreen_overlay_edit.py:110`), which do not include it. `draft_value` only passes through the value it loaded at
  the session's start.
- **Defaults and old values:**
  - The canonical default is `{}` for `preset` and `now_playing`.
  - A value stored before the change has no key and loads `{}`, with a moved overlay still reading CUSTOM.
  - A stored record that is not a mapping, has an unknown corner, or has non-numeric or zero offsets loads as `{}`.
    Out-of-range offsets are clamped to the overlay's own bounds.
  - The two-argument callers of `overlay_placement_moved` and the removed `clear_overlay_placement` have no callers
    left.
- **1D.14 tests:**
  - The test file fails to collect on the first parent's owner (no `CUSTOM_POSITION_KEY`). Its scale assertion is
    the opposite of the first parent's clearing.
  - 176 tests pass in `test_visualizers_fullscreen_mode_pill.py`, `test_visualizer_expansion_overlay_settings.py`
    and `test_visualizer_expansion_fullscreen_edit.py`.
  - The other seven files naming `fullscreen_overlays` pass too (897 tests): the `expanded_display_style*` files,
    `two_display_edit`, `expansion_overlays`, `fullscreen_visualizer_edges` and `card_clip_contract`.
- **Rules:**
  - Neither merge adds env flags, timers, polling or a QML signal to `@Slot(result=...)`. The only env read is
    `devcurve_check.py`'s validation-environment record.
  - Nothing new runs at rest: the generic item is hidden and unbound until a native mode binds.
  - No test pins preset values or wording.

### Not verified

- **Native pixels:** none were rendered (no `--native` parity run, no Vulkan, no Display 1). M1 is proved on
  synthetic runs through the tool's own code.
- **Settings dialog and Fullscreen Edit open at once:** not checked. Fullscreen Edit's save writes the whole value
  from its session-start copy, and the Visualizers tab writes the whole page value, so a concurrent write by the
  other would be overwritten. That pattern predates 1D.14 (the corner already behaved so).

## Checkpoint audit 4 (N3.2, High)

Branch `worktree-agent-a7f0682cd8743d5f4` at 5c7699ef1 against `main` (meshes and buffers, C++ at ABI 18, D15), High
effort. Nothing was fixed. The auditor merged the branch into its own worktree and ran the branch's GitHub-built module
(`release/native_module`, manifest commit e95d93063; the two commits after it change only the decisions doc and the
research file). No build was started. Line numbers are the branch's. Evidence is in the auditor's worktree under
`.artifacts/evidence/native_core/` (`n3_2/20261115_audit4_gate`, `n3_2/20261115_audit4_probes`,
`n3_1/20261115_audit4_gate`, `n3_1/20261115_audit4_prime_control`, `n2_9/20261115_audit4_generic`,
`n4_a/20261115_audit4_fullscreen`). The probe scripts are kept beside their results in `20261115_audit4_probes`. Run
`probe_n32.py` first, because it bakes the packs the other probes read.

**Verdict: do not merge as is.** The harness proof reproduces, and the arena migration is bit-identical. Two
findings block the merge:

- **H1:** a stream bound again under a new schema keeps pointers into the old schema. This is a use-after-free on
  the render thread, and the product's generic route does exactly this on a rebind.
- **H2:** the contract that "bytes past the used length keep what an earlier record wrote" is false for instance
  streams on Vulkan. Proved by pixels: the two backends differ on 94,698 pixels.

Neither has a consumer yet. Both are in the contract that N5's ports will build on.

**Reruns on the copied module** (the GPU was 42 % busy before the first run and 16 % after it):

| Proof | APIs | Result | Negative controls seen failing |
| --- | --- | --- | --- |
| `mesh_buffer_check` parity, forms, used, rest, steady, retire (`--require-validation`) | OpenGL, Vulkan, reference | PASS. Rule (a): 4 of 10 exact, the worst `streaks` at dpr 1.5 with 132 pixels past 0, 1 past 1, max 2. Rule (b): 8 of 10 exact. | Out-of-step instance stream: 124,808 and 226,170 pixels differ. First offset for every batch: 29,040. Wrong front face, y-up sprite and uncull: differ. `hide_draw_parameters`: the loop form recorded (indirect 0). `firstInstance` 3: ignored on OpenGL, 70 pixels moved on Vulkan. Used past its rule: refused, 0 writes. Recreated streams: 600 buffers in 600 records. Skipped release: 1 mesh, 864 bytes left. |
| the same: steady | both | No buffer created in 158,647 (OpenGL) and 102,343 (Vulkan) sprite records, nor in the box, beam, cells and indirect streaks runs. Vulkan validation, synchronisation included, clean through every round: 10 defect-A errors only, excused by id. | |
| `scene_target_check` gate (default rounds) and `--rounds prime_control` (Vulkan) | both | PASS. Rule (a) 5 exact, rule (b) 16 exact. prime_control PASS. | |
| `generic_mode_check` blocks, reader, draw, framebuffer, uv, attached | both | PASS. Vulkan against OpenGL: 8 compared, max level 0. | |
| `fullscreen_pass_check` (default rounds) | both | PASS. Vulkan against OpenGL: 256 compared, max level 1, uv bits identical. | |

**Choice C (the arena migration) is bit-identical.** Each sheet the three regression proofs wrote is pixel-identical
to main's last evidence in the main checkout: `n3_1/20261115_r223b_gate` (both APIs), `n2_9/20261115_r223_generic_mode`
(rings and uv probe, both APIs) and `n4_a/20261115_n4a_fullscreen_pass` (both APIs). `compare_sheets.py` gives
`identical=True max=0` for all eight pairs.

**Focused tests:** the native sweep (every `tests/test_native_*.py` except `_sdk_fetch` and `_spike_n03`) gives 436
passed.

### Critical

None.

### High

**H1. A stream bound again under a new schema keeps reading the old schema's fields: a use-after-free on the render
thread, and wrong data with no refusal.**

- **Where:**
  - `native/core/src/mesh_buffers.h:273-274`: `Stream::field` and `usedField` are raw `const frame_abi::Field *`
    pointers into the drawn `RuntimeSchema`.
  - `mesh_buffers.cpp:676-702`: they are taken once, at `ModeStreams::build`.
  - `mode_content.cpp:2125-2129`: `acceptStream` bumps only `m_buildGeneration`.
  - `mode_content.cpp:2467`: `ModeSource::sync` replaces `m_drawnSchema`, so the old schema can be freed.
  - `mode_content.cpp:3287-3298`: `ensure()` rebuilds on a new rhi, pass, program generation, scene layout, mesh
    objects or texture objects, but never on a new schema.
  - `mesh_buffers.cpp:766-776`: `ModeStreams::write` then reads `s->usedField->offset`, `s->field->offset` and
    `s->decl.capacity` from the old build.
- **Failure scenario:**
  1. A geometry mode is drawn from a stream with streams declared.
  2. The stream is bound again with its program kept. Worker replacement and capacity commit both do this (D1 point
     3), and so does the product route: `rendering/quick/visualizer/native_route.py:676-687` calls `item.bind(...,
     schema_for_mode(mode_id))` and only `settings()` when `_program_mode == mode_id`.
  3. Each bind parses a new `RuntimeSchema`, and the old one goes once the retired reader and `m_drawnSchema` release
     it.
  4. Every later record dereferences freed memory. Even with an identical schema the pointers dangle.
  5. With a changed schema (another offset or count), the stream keeps its old capacity, reads its bytes at the old
     offsets, and the state reports nothing.
- **Proof:** `probe_n32.py` P2, on both APIs (`probe_opengl.json`, `probe_vulkan.json`).
  - The sprites scene is bound, unbound, and bound again under a schema with `point_rows` at 576 floats and the used
    length moved from offset 4628 to 2324.
  - After the rebind, the state's stream capacity is still 4608 bytes. A fresh item on the new schema has 2304.
  - The rebound frame differs from the fresh item's: 52,870 pixels on OpenGL and 56,801 on Vulkan. The old used
    offset lies past the new record, so nothing was written and the stale instances were drawn.
  - `last_reason` is empty: no refusal.
  - The use-after-free itself is read from the code. No sanitizer build exists.

**H2. An instance stream drawn past its used length reads another frame slot's bytes on Vulkan, and the backends
differ.** D15's "as built" (`Native_Core_P3_Decisions.md:1447`) and the plan's f32 box (`Current_Plan.md:651`) promise
"bytes past the used length keep what an earlier record wrote", and the instance count is a separate name from the
used length. That holds only for storage streams.

- **Where:** `mesh_buffers.cpp:778-793` writes only `used` bytes of a `Dynamic` vertex buffer through
  `beginFullDynamicBufferUpdateForCurrentFrame`.
  - **Vulkan:** one buffer per frame slot (research Q6), so the bytes past `used` are those of the record two frames
    back. They are uninitialised memory in a slot not yet written.
  - **OpenGL:** QRhi maps with `GL_MAP_INVALIDATE_BUFFER_BIT` (research Q6), so the bytes past `used` are undefined.
    NVIDIA happened to keep them in this run.
  - Qt documents the fast path as a whole-buffer update.
- **Failure scenario:**
  1. A port, for example Bubble's points or Extruded Spectrum's bars in the instance form, sends a record whose used
     length is shorter than its instance count.
  2. D15 says the remaining instances keep the earlier record's data.
  3. On Vulkan they alternate between the records of the two slots (flicker), or are garbage on the first frames.
  4. On OpenGL they are whatever the driver's orphaned storage holds.
  5. Rule (b) fails, and pixels change between frames with no new data.
- **Proof:** `probe_n32.py` P1. The sprites scene draws record A (120 sprites), then three records B with 40 used and
  the count kept at 120. They are compared with the composite record, B's 40 followed by A's 80.
  - **OpenGL:** all three B frames equal the composite exactly.
  - **Vulkan:**
    - The first and third B frames differ on 94,698 pixels past 1 level, with 49,154 lit against 122,152.
    - The second B frame (the slot A wrote) equals the composite.
  - The harness's `used` round (`mesh_buffer_check.py:429-447`) proves the property for the storage beam only, so it
    could not see this.

### Medium

**M1. Draw counts are bounded by nothing, so a draw can fetch past its buffers with `robustBufferAccess` off.**

- **Where:**
  - `mode_content.cpp:1822-1834`: a draw's name must only be a u32 scalar, with no `at_most` rule required and no bound
    against what it indexes.
  - `mode_content.cpp:3513-3530`: `resolveCount` takes the record value or any setting below 2^32.
  - `mode_content.cpp:3752-3757`: the instance count is not clamped to the instance stream's or mesh's records, nor
    the vertex count to the mesh's.
  - `mesh_buffers.cpp:780-793`, with `mode_content.cpp:3742-3749`: record-written indirect commands are uploaded
    verbatim (vertex count, instance count, first vertex and `firstInstance`). Only the command count is clamped.
  - `vulkan_context.cpp:690`: the core's device has `robustBufferAccess` off.
- **Failure scenario:**
  - An owner bug, such as a count field without a rule or a setting of 1e6 instances, makes the GPU fetch per-instance
    attributes past the end of a `VertexBuffer`. That is undefined on both backends, and on some drivers a device loss
    or a TDR on the screensaver.
  - A record command with `firstInstance` 3 moves the instance index on both of this machine's backends. That breaks
    D15's "`firstInstance` is always 0", which the core enforces only for its own draws.
  - Research Q5's "the core never sets it" (`Native_Core_QRhi_Research_N3.md:574`) does not hold for record commands.
- **Proof:** `probe_n32.py`.
  - **P3:** a sprites schema whose `point_count` has no rule is admitted. A record with 400 instances draws from a
    192-record stream (`last_reason` empty, 1 record, a lit frame) on both APIs, and validation reports nothing.
  - **P4:** `streaks_indirect` with command `(4, 900, 0, 3)` is admitted and differs from `(4, 900, 0, 0)` on 70
    pixels on OpenGL and on Vulkan.

**M2. The tie budget of rules (a) and (b) admits regressions it does not explain** (the class of audit 3's M1, in a
second place).

- **Where:** `native/core/python/mesh_buffer_check.py:87,695,710`. A frame passes when `past1 <= TIE_PIXELS` (8),
  with no bound on how many pixels are 1 level off and none on how far the 8 may be off. It matches the lead's
  wording in D15 ("at most 8 pixels past 1 level", `Native_Core_P3_Decisions.md:1416`). D15 also says "a port's own
  data is judged under the same budget", so every geometry port inherits the gap.
- **Failure scenario:** a native regression that moves every pixel by one level passes, for example a fade packed as
  254/255 or an sRGB step applied twice. So do 8 pixels inverted in every frame.
- **Proof:** `probe_tie_budget.py` sends synthetic opaque frames through the harness's own `_compare` and predicate:
  - +1 on all 129,600 pixels: `passes_rule: true`.
  - 8 pixels off by up to 207 levels: `true`.
  - The control, 9 pixels black: `false`.

### Low

**L1. A batched pass's draw-parameters pack is never checked.** `checkGeometryPass` (`mode_content.cpp:744-751`) checks
only its stage. Its blocks, storage, samplers, inputs and outputs are not compared with the plain pack's, yet form 3
builds it over the plain pack's bindings and vertex input layout (`:3631-3632`). The two packs are meant to come from
one source, so this is only a gap. A pack that differs reaches the device as a pipeline whose layout does not match
its shader, instead of a refusal with a reason. Proof: read from the code.

**L2. A mesh replaced by one of the same layout tears down and rebuilds the whole content.**

- **Where:** `mesh_buffers.cpp:584` (`++m_objects`), `mode_content.cpp:3289,3294` (`meshObjects` forces
  `releasePipelines`) and `:2751` (which releases the streams and the arena too).
- **What happens:** every pipeline and SRB is built again inside a visible record. New stream and arena buffers are
  made, and the storage streams' bytes past their used length are lost.
- **Why it matters:** the standing rule is no teardown and rebuild where a live owner can be retargeted. The vertex
  buffers are given per draw, so only a layout change needs new pipelines.
- **Proof:** `probe_replace.py`, the box replaced by its own bytes and layout: 3 buffers created (the mesh, the
  `bars` stream and the arena), and the streams' build generation goes from 1 to 2.

**L3. The core allocates per record, contrary to D15's "by construction"** (`Native_Core_P3_Decisions.md:1473-1474`).

- **Where:** `record()` calls `meshesReady()` every record (`mode_content.cpp:4257`). That calls
  `ModeProgram::drawnMeshes()` (`:3494`, `:1651-1668`), which builds a new `QList` for any program that draws a mesh.
- **Why the proof missed it:** the steady proof cannot see heap allocations. The counting allocator and QRhi's
  resource counts, both in the plan's box, were not built. The proof counts only `QRhiBuffer`s the core makes.
- **Proof:** read from the code. `pack()`'s per-record `m_facts` JSON predates N3.2 (audit 2, M5).

**L4. D15's limits are declared but not enforced.**

- `kMaxDynamicOffsetBlocks` (`mesh_buffers.h:54`) is used nowhere. It holds today by construction: at most two
  dynamic blocks a draw.
- No block is checked against `MaxUniformBufferRange` (D15 point 3).
- An indirect-stream pass is recorded with `drawIndirect` on any device (`mode_content.cpp:3742-3749`), with no
  `QRhi::DrawIndirect` check or refusal.
- `batchCapacity` silently caps a batch table at 64 pairs (`:3489`), so batches past 64 are not drawn and nothing is
  reported.

Proof: read from the code. All of them are unreachable on this machine's devices and data.

**L5. A failed mesh upload leaves the old mesh drawn while the mesh is reported lost.**

- **Where:** `mesh_buffers.cpp:561-564` returns before the old buffer is released, so the slot keeps the old
  generation and vertices.
- **What happens:** at the next record `take()` returns null (the image was moved) and the mesh is listed lost, yet
  `find()` (`:509`) still returns the old buffer. `meshesReady()` is true and the old mesh is drawn, possibly with its
  old layout under the new declaration.
- **Proof:** read from the code. A `create()` failure was not provoked.

**L6. Three tests are weaker than their plan boxes.**

- `test_umatrix_follows_the_cards_rotation_and_window_map` (`tests/test_native_mesh_buffers.py:220-243,305-317`)
  compares the core with `_item_clip`, which copies `itemClipMatrix`'s formula, not the Python renderer's `uMatrix`.
  The plan asks for the Python renderer's. By reading, the rotation is the inverse of the Oscilloscope's
  `physicalPoint` (`oscilloscope_program.py:263-269`) and `item_from_window` is oriented (`spectrum.py:140-141`), so it
  is correct.
- `test_the_core_arena_rule_is_the_mirror_s` (`:51-57`) matches source text instead of calling the module's
  `mesh_buffer_arena_layout`.
- No test compares the C++ reader's decode of an f32 field with Python's. `probe_f32_reader.py` shows they agree
  (fields equal, bytes round-trip including inf, -0 and a denormal).

**L7. The documents disagree with the code.**

- The plan's device-facts box asks for the facts "into the host state", and D15 point 3 says they are logged "in the
  host state". They are in a separate map read by `vulkan_device_facts` (`vulkan_context.cpp:730-746`). QRhi's
  per-backend facts (`ubufAlignment()`, `BaseInstance`, `DrawIndirect`, `DrawIndirectMulti`, `ShaderDrawParameters`,
  `MaxUniformBufferRange`) are recorded nowhere. D15's "QRhi reports ... on both backends" is inferred from form 3
  being recorded.
- `native/core/shaders/srpss_geometry.glsl` is not spliced by the core's own bake (`cmake/compose_shader.cmake:8`
  replaces only `//@srpss_conventions`). The README's `//@srpss_geometry` works only through the Python composer.
- "A program without it holds no mesh" (D15 "as built") is true only for a content that never drew the quad. The quad
  slot is outside `ModeMeshes::sync`'s retire loop (`mesh_buffers.h:325`) and stays until the content goes.
- `ModeMeshes::sync`'s comment says "a drawn mesh with a new generation is uploaded". It uploads every mesh the item
  holds (`mesh_buffers.h:335-358`), and reports an undrawn one lost on a content made again.

### Checked, no finding

- **Ownership and retirement:**
  - Meshes, streams, the arena and the batched commands are owned by `ModeContent`. They are released by `release()`
    (streams with the pipelines), and the counts reach zero after a mode switch, a program without geometry,
    destruction, and destruction before a first draw.
  - A released `QRhiBuffer` goes through QRhi's deferred release. A mesh is released only at a record's start, before
    any draw that names it.
  - Every new `create()` is checked: meshes, the quad, streams, the arena, the batched commands, bindings and both
    front-face pipelines.
- **Arena and offsets:**
  - Offsets come from `rhi->ubufAlignment()` (64 on the RTX 4090's Vulkan, 1 on OpenGL).
  - A batched pass's copies sit one aligned stride apart.
  - Every `memcpy` into the arena and the command shadow is bounds-checked.
  - At most two dynamic offsets go to one `setShaderResources`, inside OpenGL's 8 and the device's 15.
  - The arena, instance, indirect and command buffers are written only by the fast path, never mixed with a batch
    update.
  - Sixteen draws at sixteen offsets equal sixteen passes bit for bit.
- **Streams:**
  - `write` bounds the used length by the capacity and the record.
  - A record past its `at_most` rule is refused by the reader before any write.
  - The storage route's `fromRawData` view over the kept `staging` is safe on both backends: Vulkan copies it at the
    batch, and OpenGL's deferred `glBufferSubData` runs at this frame's end, before the next record writes `staging`.
- **`firstInstance`:** 0 on every draw the core makes: direct, form 2, and form 3's commands
  (`mode_content.cpp:3572`, `:3736`, `:3757` under the harness control). `gl_DrawID` reads the batch and
  `gl_BaseInstance` 0 on both backends.
- **Synchronisation (the N3.1 H1 class):**
  - Storage streams re-uploaded every record, read in the vertex stage, give no hazard over 16,157 to 102,343
    consecutive records per scene under synchronisation validation. That covers the box with depth on a scene target,
    the storage beam, two storage streams in the cells pass, the instance sprites and the indirect streaks.
  - Mesh replacement and removal are validated in the retire round.
  - Storage is bound read-only (`bufferLoad`), so passes sharing a stream only read it.
- **Threads:** zero calls with a Python thread state (the rest round). The mesh state is noted only when objects
  change, under `m_textureReportMutex`, and read under it. No per-record JSON is added by N3.2.
- **`uMatrix` and the clip correction:**
  - `itemClipMatrix` composes the item pixel through the oriented coordinate to the target's clip space, and the
    correction is applied once.
  - The core's triangle keeps zeros, which the bit-identical regressions confirm.
  - `clipTopDown` is derived from `targetCorrection`.
  - `mode_blocks`' optional correction uses the limited API's `PySequence_*` functions, with its reference released
    and the error checked.
- **The f32 kind:** consistent across `native_schema.py` (2 MiB records, 262,144 elements), `mode_schema.cpp`, the
  generated header, `program_blocks.cpp` (it fills no block member), the module's decode, and the reader's rule (a
  range rule on a u32 scalar only).
- **The built-in quad:** `(0,0) (1,0) (0,1) (1,1)` as `aPosition`, equal to `render_host.py:524-533`.
- **ABI 18:** `abi.h`, `EXPECTED_ABI`, the build and loader tests and the module entries agree, and nothing assumes
  ABI 17.
- **Rules:** no environment flags, timers or polling in product code; no preset names; the protected clip commits
  untouched. D5's ownership table is amended for choice A.

### Not verified

- **Rounds not rerun:** `mesh_buffer_check`'s `cost` and `stream_ring` rounds, so neither D5.3's stream-ring figures
  nor the GPU times. Also `background_layer_check`, `backdrop_pyramid_check`, `transition_route_check` and
  `devcurve_check`, which the plan lists but the brief did not.
- **What the probes did not cover:**
  - H1's use-after-free as a crash (no sanitizer build).
  - M1's out-of-bounds fetch as a fault (only its admission).
  - A device without `DrawIndirect`, `DrawIndirectMulti` or `ShaderDrawParameters`.
- **Real windows:** hidden hosts only, and no Display 1 rehearsal.

## Checkpoint audit 5 (N3.3, High)

Branch `worktree-agent-a2e216858330ebb7e` at ae2bf6b0b against `main` (compute passes, C++ at ABI 19, D16), High
effort. Nothing was fixed. The branch fast-forwarded onto the auditor's worktree (main had nothing the branch lacked), so
line numbers are the branch's. The auditor ran the branch's GitHub-built module (`release/native_module`, manifest
commit 686ae09cf, run 43682663623). `git diff --stat 686ae09cf ae2bf6b0b` touches only documents and
`devcurve_check.py`, so the module is the code under audit. No build was started. Evidence is in the auditor's worktree
under `.artifacts/evidence/native_core/`: `n3_3/20261115_audit5_compute`, `n3_3/20261115_audit5_probes` (the probe
script `probe_audit5.py` is kept beside its `probe_opengl.json` and `probe_vulkan.json`), `n3_2/20261115_audit5_used_forms`
and `n3_1/20261115_audit5_gate`. The GPU was not quiet: before the first run nvidia-smi read 46 to 49 %, P5 (an SRPSS
process the auditor did not start), and 16 % after it. Hidden hosts only.

**Verdict: the branch can merge as it is.** There is no critical or high finding. The proof reproduces on both
backends. Each negative control fails without its rule, and synchronisation validation with the shader-access checks is
clean outside the control phases. Three medium findings are contract defects in the code that N5.4 and N5.6 will build
on. Each is a small fix in `compute_passes.cpp` or `mode_content.cpp` and should be a box before the first consumer uses
compute:

- **M1:** a program without storage never releases the storage buffers of the program before it.
- **M2:** `fresh` is set for every entry by a new program or by any one resource made again, so a stateful entry
  restarts its history while its buffer is kept.
- **M3:** one buffer bound twice with two accesses in one entry is admitted. QRhi then derives a wrong barrier, and the
  layer reports the hazard.

M4 is three harness boxes of the plan that were not built, and the as-built does not say so.

**Reruns on the copied module** (each once):

| Proof | APIs | Result | Negative controls seen failing |
| --- | --- | --- | --- |
| `compute_pass_check`, every round (facts, parity, trigger, war, copy, rest, steady, retire, barriers, cost) with `--require-validation`; shader-access checks on (`synchronisation_shader_accesses` true) | OpenGL, Vulkan, reference | **N33 VERDICT PASS.** Rule (a) and rule (b) exact on every resource of field, chain, volume and population (and `population_direct`), with the pixels exact. Vulkan validation: 10 errors, all Qt defect A (excused by id); 0 unexplained. | `write_as_read`: `SYNC-HAZARD-READ-AFTER-WRITE` (and WAW), 20 errors. `single_pass`: `SYNC-HAZARD-WRITE-AFTER-READ`, 10. `trigger_every_record`: 400 dispatches, row 0 `[201, 100, 100, 200]` against the reference `[100, 100, 99, 99]`. Skipped release: 2 buffers (2,048 bytes) left, then 0 after the next sync. Rest control: 180 dispatches in 60 records. |
| the same: trigger, copy, rest | both | 20 dispatches in 20 records. 15 re-records (fade, settings, readback) gave 0 dispatches and 15 skips. Made again: `on_state_lost` once with `["out", "state"]` and row 0 `[1, 100, 0, 1000]`. Resize 256 to 512 rows: 2 copies, 2 clears, 0 dispatches, the prefix exact, zero past it. | |
| the same: cost (GPU busy, see above) | both | GPU median of the whole record at 2560x1440 and 4K, in ms. Vulkan: field 0.036 and 0.071, waveform 0.044 and 0.083, drift 0.137 and 0.150, population 0.118 and 0.131. OpenGL: field 0.064 and 0.128, waveform 0.099 and 0.136, drift 0.178 and 0.155, population 0.165 and 0.211. These are within a few hundredths of D16's figures. | |
| `mesh_buffer_check --rounds used forms --require-validation` | both | N32 VERDICT PASS. Vulkan: 10 defect-A errors only. | |
| `scene_target_check` gate (default rounds, cost included) with `--require-validation` | both, reference | N31 VERDICT PASS. Rule (a) 5 exact, rule (b) 16 exact. Vulkan: 10 defect-A errors only. | |

**Focused tests:** `pytest -k test_native_` over `tests/` (without `_sdk_fetch` and `_spike_n03`) gives 508 passed.

### Critical

None.

### High

None.

### Medium

**M1. A program without storage keeps the storage buffers of the program before it until the item is destroyed.**

- **Where:**
  - `native/core/src/compute_passes.h:235`: `empty()` looks at `m_buffers` and `m_images` only, never at `m_retiring`.
  - `compute_passes.cpp:746-749`: the first sync under the new program moves every buffer into `m_retiring`.
  - `compute_passes.cpp:595-597`: `m_retiring` is released only at the start of a later `sync`.
  - `mode_content.cpp:4645-4646`: from the second record on, `syncStorage` returns before `sync`, because the program
    declares nothing and `m_storage.empty()` is true.
  - The kernels stay too: `compute_passes.cpp:793-794` releases them only when `m_retiring` is empty.
  - Images are released at once (`compute_passes.cpp:787-790`), so only buffers are affected.
- **Failure scenario:**
  1. The generic route sends another mode's program to the same item (`_program_mode` changes).
  2. That program declares no storage, for example a switch from Extruded Bubble's drift to an ordinary mode.
  3. Every storage buffer, up to 8 of 256 MiB each, stays resident with the core's four kernel objects until the item
     goes.
  4. `composite_live`'s `compute_buffers` stays above zero.
  5. D16's "as built" (`Native_Core_P3_Decisions.md:1682`: "retirement to zero after ... a program without storage") and
     the plan's retirement box say otherwise.
- **Why the proof missed it:** `round_retire`'s case (`compute_pass_check.py:868-879`) uses the field scene. That scene
  holds one image and no buffer (`held: compute_buffers 0, compute_images 1`).
- **Proof:** `probe_audit5.py` P1, on both APIs. The population scene holds 5 buffers (82,064 bytes). After a program
  of one plain pass, it still holds 5 buffers and 82,064 bytes after 3 frames and after 33. They go to 0 only when the
  item is destroyed.

**M2. `fresh` is per content, not per resource, and a new program sets it. A stateful entry restarts over storage that
was kept.**

- **Where:**
  - `mode_content.cpp:4639-4644`: a new program generation resets every `ComputeTrack`, so `!t.dispatched` makes the
    next dispatch fresh (`:4710`) and `u_srpss_compute.y` 0.
  - `mode_content.cpp:4656-4657` with `compute_passes.cpp:741,784`: any one buffer made without a prefix, or any image
    made again, raises one `m_freshGeneration`. Every entry then dispatches fresh, including those whose buffers were
    kept. An image is made again by Python's `image_size`, which is Waveform's fog grid following its surface.
- **Why it matters:** D16 point 7 (`:1593-1595`) says `fresh` is 1 "at the first dispatch after the state was created".
  `compute_passes.h:16-17` and `mode_content.h:127` say the storage "survives a pipeline rebuild and a new program that
  declares it the same way". Choice C rejects "restarting a family's state at every resize (a visible jump at a Settings
  edge)". The bytes survive, but the shader is told to throw them away, and D16 makes the drift's "restart from zero
  when fresh" the shader's own rule.
- **Failure scenario:**
  1. Extruded Bubble's drift (N5.6) is re-sent its program at a Settings edge with the same storage. A variant change
     does this, or a worker rebind that sends the program again.
  2. Alternatively, a mode with a stateful buffer and a surface-sized image is resized.
  3. The drift state restarts from zero: the visible jump that choice C rejected.
- **Proof:** `probe_audit5.py` P2, on both APIs.
  - The state scene is stepped 6 times, giving row 0 `[6, 6, 5, 5]`.
  - The same program is then sent again with the same buffers. No object is created and no clear runs: the storage is
    kept.
  - One more step gives `[1, 7, 0, 1000]` (fresh, last trigger 0) instead of `[7, 7, 6, 6]`.
  - The image path is read from the code and was not run.

**M3. One storage resource bound twice in one compute entry, with two accesses, is admitted, and QRhi then derives a
wrong barrier.**

- **Where:**
  - `mode_content.cpp:1134`: the duplicate check compares the shader's names only.
  - `mode_content.cpp:1188` (`claim`) checks the binding numbers. Nothing checks that two bindings name different
    resources.
  - QRhi's pass tracker keeps the first access of a buffer registered twice in one pass and ignores the second
    (research Q7 gap (b), `Native_Core_QRhi_Research_N3.md:277-279`), so D16 point 3's "barriers derived from access
    types" silently loses the write.
  - By reading, the same class reaches draws. One render pass may read a storage buffer as `storage` and as
    `instance_from` in two draws of one run, or in one draw. That is two access types, and `mode_content.cpp:1836-1860`
    admits it.
- **Failure scenario:**
  - A port binds `In` (readonly) and `Out` (writeonly) to one ping-pong buffer, or a readonly and a read-write view of
    the drift state.
  - The program is admitted with no reason.
  - The write is untracked, so the next pass reads it with no barrier on Vulkan. That is a race on the GPU.
- **Proof:** `probe_audit5.py` P3 (Vulkan, validation with shader-access checks).
  - The entry `war_read.comp` with `X` (read) and `Y` (write) both on buffer `x`, followed by an entry reading `x`, is
    admitted (`last_reason` empty). Over 12 records the layer reports `SYNC-HAZARD-WRITE-AFTER-WRITE` in that phase.
  - The control, the same two entries with `Y` on a third buffer, reports no hazard. Its phase holds one defect-A
    error only.
  - The probe looked for Qt's "used with different accesses" warning in the child's stderr and found none.

**M4. Three harness boxes of the plan were not built, and the as-built does not say so.**

- **Where:** `Current_Plan.md`, the N3.3 harness box.
- **What is missing:**
  - **Rule (b):** "D4's pair-check kernel (`PROGRAMS[2]`) through `qsb` exact on both backends (`precise` survives the
    bake)" (`:812-813`). No scene or round uses it: `compute_pass_check.py` and `compute_passes/` have no pair-check
    kernel and no `precise`.
  - **Write-after-read, ping-pong form:** "in both forms the research names (two passes, the default; two buffers, a
    ping-pong)" (`:825-826`). Only the two-pass form (`war`) is built.
  - **OpenGL's barriers:** "the barrier calls per record counted against Python's" (`:829-830`). They are not counted.
    D16's as-built judges OpenGL by GPU time instead, which is choice H's criterion, but the box still asks for the
    count.
- **Why it matters:** the first is D4's guard against a compiler that drops `precise`, which choice G keeps the product
  readback for. Its bake through the core's own path is unproved.
- **Proof:** read from the harness; Grep for `precise`, `PROGRAMS` and `ping` over `compute_pass_check.py` and
  `compute_passes/` finds nothing.

### Low

**L1. The core allocates on the render thread at every record of a content with storage.**

- **Where:**
  - `compute_passes.cpp:611,628`: `ModeStorage::sync` runs every record and builds `QList<quint32> sizes`.
  - `:714,726`: it builds `next`.
  - `:751,762`: it builds `nextImages`. These are heap allocations even when everything is kept.
  - `:590-591`: `releaseLeftBehind` takes the process-wide `g_leftBehindMutex` at every record, for the harness
    control's sake.
- **Why the proof missed it:** the steady round counts QRhi objects (`compute_objects_created`), not heap allocations:
  audit 4 L3's class.
- **Proof:** read from the code.

**L2. A trigger is consumed by a record that dispatches nothing.**

- **Where:** `decideDispatches` advances `lastTrigger`, `dispatches` and `freshSeen` (`mode_content.cpp:4693-4732`)
  before `recordCompute` decides. `recordCompute` then may not dispatch:
  - groups past the device's limit (`:4744-4757`);
  - a group count of 0 (`:4758-4759`);
  - no pipeline (`:4739`).
- **Failure scenario:**
  - A field-triggered stateful entry whose group count is 0 for one record (a named count, for example an empty
    population) loses that record's steps for good. The next dispatch sees `y` = the skipped value.
  - If that record was the first after the storage was made, `fresh` is consumed with no dispatch.
  - This is D16 point 7's "a stateful pass is never integrated twice" turned into "sometimes not at all".
- **Proof:** read from the code. Nothing provoked it: no scene has a zero group count.

**L3. Storage refusals rest on facts the core records but does not use.**

- **The format check:** D16 point 6 (`Native_Core_P3_Decisions.md:1586-1588`) says a missing storage-image format
  (Vulkan's R16F needs the extended formats) refuses the program, "read once at device creation". The core asks
  `rhi->isTextureFormatSupported(format, UsedWithLoadStore)` at every sync instead (`compute_passes.cpp:631-632`).
  - The Vulkan facts it records for exactly this, `storage_image_formats` and `shader_storage_image_extended_formats`
    (`vulkan_context.cpp:786-804`), are never consulted.
  - Whether Qt 6.12's backends honour `UsedWithLoadStore` in that query was not verified: there is no Qt source on
    this machine, and every format is supported here.
- **Group limits:** the pack's reflected local size (`mode_content.cpp:1330-1332`) is never checked against
  `MaxThreadGroupX/Y/Z` or `MaxThreadsPerThreadGroup`. Only the group counts are checked.
- **Dispatch totals:** the product of three admitted group counts is unbounded: three record counts under at_most
  65535 is 2.8e14 groups, a TDR on the screensaver from an owner bug (audit 4 M1's class).
- **Proof:** read from the code.

**L4. Image storage has no byte bound, and its zeroing is a host allocation of a whole slice.**

- **Where:**
  - Buffers are capped at 256 MiB (`compute_passes.h:50`). An image is bounded only per side, up to 16384 square in
    2D and 2048 cubed in 3D (`:51-52`).
  - Its zeros are one `QByteArray` of a whole slice, made on the render thread (`compute_passes.cpp:768-772`): 4 GiB for
    a 16384-square RGBA32F image.
  - Every storage image carries `UsedAsTransferSource`, which only the harness's readback needs (`:690-692`).
- **Proof:** read from the code.

**L5. Exception G is a closed list, but it is looser than D16 in three places.**

- **Where:** `Docs/Guardrails/Performance_Optimization_Contract.md:450-456`. It cannot become a general licence: it
  names one readback and requires "its own line here and in D16" for any other.
- **Where it is looser:**
  - It says "once per device", where D16 says "once per solver" (`Native_Core_P3_Decisions.md:1534-1535`) and choice
    G says "once, at its warm-up edge". A device loss or a display move would legitimately repeat it.
  - It bounds neither the bytes read (the pair's few words) nor what the result may do ("logged" does not say "and
    nothing else").
  - It pre-excuses the OpenGL synchronous read as lifecycle and "never counted as a steady-state hitch", without
    defining the warm-up edge. A warm-up at a mode switch mid-show is a visible frame, which the warm-up rule
    (gradual, ~14 ms at an image change) treats as steady state.
- **Not enforced:** the harness readback entries reach the product's Python face (`NativeMode.read_storage`,
  `storage_data`, `rendering/native/mode.py:712-719`, as N3.1's `read_targets`). No test keeps product code from
  calling them. Grep finds no caller in `rendering/`, `widgets/`, `core/` or `ui/` today.
- **Proof:** read from the documents.

**L6. The documents disagree with the code.**

- D16 "as built" `:1682`: "retirement to zero after ... a program without storage" holds for images only (M1).
- `compute_passes.h:16-17` and `mode_content.h:127`: the storage "survives ... a new program", but its entries restart
  (M2).
- D16 point 6 says compute support is "read once at device creation". The code reads `QRhi::Compute` at every build
  (`mode_content.cpp` `build`) and in `ensureKernels`, and the formats at every sync (L3).
- `compute_passes.h:265`: `m_zeros` is "kept for the uploads at an edge" but is never written. The zeros are a local
  at `compute_passes.cpp:769`.
- `tests/test_native_mesh_buffers.py:6`: the docstring still says "ABI 18". The assertions are correct (`>= 18`, and
  `test_native_compute_passes.py:101-102` pins 19).

### Checked, no finding

- **Lifetime:**
  - A resized buffer's predecessor is held in `m_retiring` and released at the next record's sync, never inside the
    record whose copy reads it (`compute_passes.cpp:592-597`).
  - The edge kernels are recorded in the same `syncStorage` call as the sync that queued them (`mode_content.cpp`
    `syncStorage` then `recordEdges`), so `Op`'s raw pointers never outlive their buffers.
  - `kMaxStorageEdgeOps` (16) equals 8 buffers by 2 operations.
  - Phase 1 makes every object before anything changes, and a failure is latched (`m_latch.failed`).
  - The bindings over the storage are made again through `m_textureObjects` before any pass, and compute passes are
    included in `rebindTextures`. Vertex input and `drawIndirect` take the current buffer at draw time.
  - A content made again finds the storage zeroed, dispatches fresh and tells the owner once, the lost names prefixed
    `state:` and split in `NativeMode._lost`.
  - Retirement reaches zero after a destroy, a destroy mid-resize, and the skipped-release control's next sync (rerun).
- **Kernels:**
  - The std140 block (dst, src, words, value, stride) matches the C++ words at offsets 0 to 16 in a 32-byte stride
    aligned by `ubufAligned`.
  - Groups are capped at 65535 and each invocation strides by groups x 256, so a 256 MiB buffer is covered in 4 passes
    of the loop with no 32-bit overflow.
  - The clear and the copy into one buffer are two QRhi passes (WAW barriered).
  - The prefix is bit-exact, rerun.
- **3D storage images:** made with `ThreeDimensional`, zeroed slice by slice, read back per layer, and sampled by
  `sampler3D` with no mips. Rule (a) and rule (b) are exact on the volume's RGBA16F and R16F images (rerun).
- **Counts (N3.2's narrowed rules):**
  - Instances from a storage buffer are checked against bytes over stride, and indirect commands against bytes over
    16, both refused with the reason made at the edge (`mode_content.cpp` `drawPass`).
  - The commands a compute entry writes are the lead's trusted exception, documented in D16.
  - Record group counts need an at_most rule of at most 65535, and groups past the device's limit are not dispatched.
  - A record field cannot size a buffer, and a setting cannot be a trigger.
- **Synchronisation:**
  - Every compute entry is its own QRhi compute pass (`recordCompute` ends it unless the harness's `single_pass`
    control is on), as is every kernel operation.
  - Accesses map one to one to `bufferLoad`/`Store`/`LoadStore` and `imageLoad`/`Store`/`LoadStore`, and are checked
    against `qsb`'s qualifiers (the facts round's eight refusals, rerun).
  - The core issues no barrier of its own for compute.
- **Shader-access validation is harness-only:**
  - `VK_EXT_layer_settings` is chained only when the caller asks for it, with validation and synchronisation validation
    loaded (`vulkan_context.cpp:389-394`).
  - The product's only caller, `rendering/quick/bootstrap.py:669`, calls `core.vulkan_instance()` with the defaults
    (no validation, no shader accesses).
  - No environment variable is involved.
- **Triggers:** a re-recorded frame never re-dispatches: the frame trigger reads `StreamSource::m_frameSerial`, bumped
  only when a new record is accepted (`stream_source.cpp:179`). The field trigger reads the record's u32. The proof's
  15 re-records gave 0 dispatches (rerun).
- **Nothing per record at rest:** the rest round's minute gave 0 compute passes, dispatches and objects (rerun).
- **The limited Python API:** the four new entries use `PyArg_ParseTuple`, `PyList_*`, `PyDict_New`,
  `PyBytes_FromStringAndSize`, `Py_BuildValue` and `PyErr_*` only, with their references released on every error path.
- **ABI 19:** `abi.h:110`, `EXPECTED_ABI` (`loader.py:49`) and `test_native_compute_passes.py:101-102` agree, and
  `abi.h`'s comment lists the new entries and state keys the code has.
- **`tools/regen_qrc.py`:** `.comp` joins the baked suffixes. No product folder holds a `.comp` today, so no pack
  changes.
- **Rules:** no environment flags, timers or polling in product code, and no preset names. The protected clip commits
  are untouched.

### Not verified

- **Rounds not rerun:** `generic_mode_check`, `fullscreen_pass_check`, `background_layer_check`,
  `backdrop_pyramid_check`, `transition_route_check` and `devcurve_check` (the brief named only the three above).
  `mesh_buffer_check`'s parity, rest, steady, retire, cost and stream_ring rounds were not rerun either.
- **Cost on a quiet GPU:** not possible. The GPU was 46 to 49 % busy before the run.
- **What the probes did not cover:**
  - M2's image path (a fresh image restarting a kept buffer's entry): read from the code.
  - M3's draw-side form (a storage buffer read two ways in one render pass): read from the code.
  - L2 and L3 were not provoked.
- **Real windows:** hidden hosts only, and no Display 1 rehearsal.
