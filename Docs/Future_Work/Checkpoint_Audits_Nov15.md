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
