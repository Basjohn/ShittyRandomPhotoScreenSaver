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

## TX-02 — Random selection writes user settings every rotation and clobbers authored directions · P1 · R2 · Risk Medium

**Evidence (source + measurement).** With `random_always=True` (the canonical default), every rotation runs
`_prepare_random_transition_if_needed()` (`screensaver_engine.py:1546-1641`), which:

- calls `settings_manager.set()` 2–6 times — `transitions.random_choice`, `transitions.last_random_choice`, and for
  Slide/Wipe **`transitions.slide.direction` / `transitions.wipe.direction`** plus their `last_direction` — then
  `save()`;
- each `set()` deep-copies the *entire* settings store for the ordered writer (`json_store.py:217-255`) and fans
  `settings_changed` out synchronously; the store is ≈2,600 objects for the operator's profile. Measured on a copy
  of that profile: **≈1.9 ms per rotation (idle)** on the GUI thread, plus one full settings-file rewrite per rotation;
- the Quick request resolver then reads `random_choice` back from Settings (`request_resolution.py:176-190`): the
  persisted store is being used as in-process IPC between the engine and DisplayManager.

**Correctness defect.** `transitions.slide.direction` (canonical default `'Random'`) and `transitions.wipe.direction`
(canonical default `'Bottom to Top'`) are **user-authored product settings**. The resolver already randomizes a
`'Random'` direction per request (`request_resolution.py:118-131, 243-261`), so the engine's pre-selection is
redundant, overrides an explicitly authored fixed direction while Random is on, and permanently replaces the user's
value with the last random pick. Turning Random off afterwards leaves Slide/Wipe on a direction the user never chose.
This violates the Defaults_Canonical_Schema_Dedup invariant "one persisted product setting has one canonical path"
(engine-managed history such as `random_choice`/`last_*` is acknowledged there as session state; the authored
`direction` keys are not).

**Proposal.**

1. Stop writing `transitions.slide.direction` / `transitions.wipe.direction` from the engine. Directions resolve in
   the request resolver from the user's authored value (which may be `'Random'`).
2. Carry the chosen Random transition id in memory through the existing batch spec
   (`DisplayManager._resolve_quick_transition_batch_spec`, `display_manager.py:3733-3743` already shares one spec
   across displays) instead of round-tripping through persistence.
3. Keep anti-repeat memory (`last_random_choice`, per-transition `last_direction`) in memory; persist it at most once
   per session/teardown if the operator wants cross-session anti-repeat (decision below).
4. Keep fail-closed semantics: empty effective pool → no transition this rotation (R-65: destination withheld, loud).

**Operator decision.** Should Random mode honour an explicitly authored fixed Slide/Wipe direction, or always
randomize direction? (Current code always randomizes in Random mode; the fix above honours the authored value and
randomizes only when it is `'Random'`.)

**Existing-profile repair.** Profiles already clobbered cannot be distinguished from a user choice; do **not**
auto-rewrite them. Note it in release notes instead.

- [ ] Decision recorded.
- [ ] Focused: transition request resolution tests, `tests/test_settings_manager.py`, defaults-authority tests; new bar
      that a Random rotation performs zero `set()` on authored transition keys.
- [ ] Physical: Random rotation across two displays still shares one choice per batch; manual transition cycle and
      context-menu transition selection unchanged.

---

## TX-03 — Stale stagger rationale and constant drift · P3 · R1 · Risk Low

`image_pipeline.py:1483-1485` says "Stagger transition starts by 100ms per display to avoid simultaneous transition
completions which cause 100+ms UI blocks"; the constant is `TRANSITION_STAGGER_MS = 200` (`core/constants/timing.py:60`)
and the "UI block" rationale is QWidget-era. The stagger is now authored visible behaviour, so keep it; fix the
comment and, only if the operator wants simultaneous starts, treat that as a product change with its own review.

- [ ] Comment corrected (docs-only change).

---

## Cross-reference

- PR-04 (transition-end native re-copy/re-upload) lives in 01 because its owner is the retained background node.
