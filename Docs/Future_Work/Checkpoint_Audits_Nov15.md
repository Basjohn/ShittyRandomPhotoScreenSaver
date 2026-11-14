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
