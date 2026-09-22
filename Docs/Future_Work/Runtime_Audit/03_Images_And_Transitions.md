# 03 — Images and Transitions

Owners audited: `engine/{screensaver_engine,image_pipeline,display_manager}.py`,
`rendering/quick/transitions/{controller,request_resolution,parameter_resolution,mesh_support,fracture_geometry}.py`,
`rendering/quick/transitions/implementations/*`, `rendering/quick/render/{background_node,image_textures}.py`,
`core/settings/{settings_manager,json_store}.py`.

**Binding:** Transitions.md, Transition_Change_Checklist.md, R-65 (admission before mutation), R-63, R-60, R-50,
R-51 (per-context GL ownership), Defaults_Canonical_Schema_Dedup (one canonical path per product setting).

## What is already healthy (do not re-audit)

- Image-change admission is transactional before queue/history mutation (`screensaver_engine.py:1452-1504`, R-65).
- Processing runs on COMPUTE through the ImageWorker; results publish detached `PresentationImage` state with
  generation fencing (`image_pipeline.py:1221-1580`); no GUI QPixmap round trip (R-84 repair).
- Transition runs are one-shot, monotonic, deadline-finalized by a single-shot QTimer (`transitions/controller.py`).
- Transition programs/VAOs are retained per render node and survive between runs (CHK21).

---

## TX-01 — 3D transitions build run geometry on the render thread at the first frame · P1 · R3 · Risk Low

**Evidence (measured on the audited tree).** Geometry is keyed by `run_id` and built lazily inside `render()`:
Glass Shatter (`implementations/glass_shatter.py:35-40`), Crumble (`implementations/crumble.py:144-147`,
`_rebuild_geometry` `:157-186`), and every `MeshResources.mesh()` upload (`mesh_support.py:81-104`). All of it is
pure Python on the Qt render thread, holding the GIL, before the first transition frame can be drawn:

| Transition (default settings) | Python geometry | `(ctypes.c_float * n)(*values)` pack | Total first frame |
| --- | ---: | ---: | ---: |
| Glass Shatter, 95 shards | 11.9 ms | 13.0 ms (153,504 floats) | **≈25 ms** |
| Crumble, 35 pieces + debris | ≈9 ms | ≈2 ms | **≈11 ms** |
| Crumble, 128 pieces (user-raisable) | 23.4 ms | 16.6 ms | **≈40 ms** |

Seeds are per-request random (`parameter_resolution.py:589-591`), so geometry cannot be reused across runs. On a
two-display setup both render threads do this at the same moment, contending for the GIL with each other, the GUI
thread and the visualizer logical thread; the visualizer frame on that display is also late because it renders in
the same scene frame. This lands exactly on the open `Current_Plan.md` item "confirm Visualizer freshness and
transition first-use behavior".

**What disappears.** 11–40 ms render-thread stalls at every 3D transition start (per display).

**Proposal (two independent steps).**

1. **Pack without star-unpacking:** build `array('f', values)` (or NumPy) and pass its buffer to `glBufferData`.
   Measured 13.0 → 3.9 ms for Glass. Byte-identical vertex data; no semantic change. Apply in `mesh_support.mesh()`
   and Crumble debris.
2. **Move geometry off the render thread:** the seed and parameters are fixed when the request is built
   (`spec.build_request`, `display_manager.py:3843-3848`); aspect is known from the display identity. Build the
   packed vertex bytes on COMPUTE when the batch spec resolves (image processing already takes tens of ms, so the
   work overlaps), attach them as immutable bytes to the per-display request, and let the render thread only upload.
   Fallback when bytes are missing is **not** allowed to silently differ: build synchronously exactly as today and
   log once (the current path is the reference implementation).

**Must remain true.** Identical fracture/mesh output per seed (existing pixel/geometry oracles in
`tests/test_qtquick_future_transition_gl.py`); GL objects created/destroyed only on the owning context (R-51);
transition timing still sampled from `TransitionRun` wall time; no new clock; transitions stay deactivated by default
per Transitions.md.

- [ ] Step 1 implemented + byte-identity test on packed buffers.
- [ ] Step 2 implemented; request immutability and per-display aspect keyed correctly.
- [ ] `--frame-trace`: first `BACKGROUND_RENDER_*` frame of Glass/Crumble/Tiles drops to steady-frame class;
      publication→draw during transition start neutral-or-better.
- [ ] Physical: Glass/Crumble/Tiles on both displays with active music (open Current_Plan acceptance item).

---

## TX-02 — Random selection wrote user settings every rotation and clobbered authored directions · P1 · R2 · Risk Medium

**Was:** every Random rotation made 2–6 `settings_manager.set()` calls (each deep-copying the whole store and fanning
out `settings_changed`) plus `save()` (≈1.9 ms idle + a file rewrite), used persisted `random_choice` as engine →
DisplayManager IPC, and overwrote the user-authored `transitions.slide.direction` / `transitions.wipe.direction` with
the last random pick.

**Now (implemented):** the engine keeps `RandomTransitionHistory` (current pick, anti-repeat choice and per-transition
direction) in session memory and hands a `RandomTransitionSelection` to `DisplayManager.set_random_transition_selection`;
`resolve_quick_transition_spec(random_selection=...)` resolves one batch spec from it and ignores any persisted
`random_choice`. Visible Random behaviour is unchanged: a random Slide/Wipe direction with anti-repeat, shared by every
display of the batch; Previous reuses the current pick. Only the first pick of a session no longer avoids the previous
session's last pick. Normalization repair writes (rare) are unchanged; existing profiles are not auto-repaired.

- [x] Focused: `test_transition_distribution.py` (400 rotations → zero `set()`/`save()`, authored directions intact,
      choice + direction anti-repeat), `test_qtquick_transition_request_resolution.py` (stale persisted `random_choice`
      ignored; direction override leaves authored value), `test_qtquick_h_cutover.py` (DisplayManager seam, Previous
      reuse), activation-admission tests.
- [ ] Operator decision: should Random honour an explicitly authored fixed Slide/Wipe direction? (Today: always
      random, as before. Honouring it is a one-line change in the engine's direction pick.)
- [ ] Physical: Random rotation across two displays still shares one transition + direction per batch; manual cycle
      (C) and context-menu transition selection unchanged; Settings shows the authored Slide/Wipe direction after a
      Random session.

---

## Cross-reference

- PR-04 (transition-end native re-copy/re-upload) lives in 01 because its owner is the retained background node.
