# 01 — Presentation, GUI↔Render Sync and Frame Demand

Owners audited: `rendering/quick/{runtime,window,frame_pacer,bootstrap,scene_controller}.py`,
`rendering/quick/render/*`, `rendering/quick/visualizer/{item,node,telemetry}.py`,
`widgets/spotify_visualizer/{quick_presentation_sync,quick_display_visualizer_owner,runtime_controller,render_bridge}.py`,
`rendering/quick/qml/DisplayScene.qml`.

## What is already healthy (do not re-audit)

- Visualizer presentation is publication-driven: mailbox empty→populated wake → one queued Qt signal →
  `sync_latest()` → one `QQuickItem.update()` (`quick_presentation_sync.py:56-117`). No Python pacer.
- Transition frame demand is Qt-owned (`DisplayScene.qml:61-94` `FrameAnimation` + per-display due gate); the
  Python `QuickFramePacer` publishes state edges only (`frame_pacer.py`).
- Steady wallpaper is a native retained `QSGImageNode`; the custom GL node is opacity-blocked outside
  transitions (`render/background_image_node.py:118-133`) — CHK21/CHK23 architecture intact.
- `VisualizerRenderNodeTelemetry` already mutates cheap fields per frame and builds its snapshot on demand
  (`visualizer/telemetry.py:1-14`).
- Pointer motion: native cursor timestamp only; the input controller skips passive routing in interaction mode
  (`window.py:304-324`, `cursor_controller.py:140-160`).
- The CUSTOM overlay is `visible: editActive` with model-driven Repeaters; dormant outside Edit.

---

## PR-01 — Per-publication presentation re-resolve and ~25 no-op property writes · P1 · R2 · Risk Low · `[~]`

**Evidence (source).** Every logical publication (~90 Hz) runs on the GUI thread:

1. `QuickVisualizerPresentationSync.sync_latest()` → `resolve_presentation()`
   (`quick_presentation_sync.py:189`) → `QuickDisplayVisualizerOwner._resolve_current_presentation()`
   (`quick_display_visualizer_owner.py:639-692`) — a full `resolve_visualizer_presentation(...)` plus a
   `dataclasses.replace` when a resolver is injected. **Measured ≈49 µs** per call (idle machine).
2. `VisualizerRuntimeController.publish_render_snapshot()` commits viewport metrics
   (`runtime_controller.py:639-640`).
3. `_apply_resolved_presentation()` (`quick_display_visualizer_owner.py:694-716`) →
   `QuickSceneController.apply_visualizer_presentation()` (`scene_controller.py:1707-1724`) →
   `_apply_visualizer_presentation_items()` (`:1726-1794`): 4 loader geometry setters, 4 root geometry setters and
   **~21 `root.setProperty()` calls plus 3 `QColor` constructions, unconditionally**, then
   `_sync_custom_layout_visualizer()` (`:1281-1296`) which, with no CUSTOM session, calls the viewport sink
   (`controller.set_custom_viewport_override(None, {})`, lock + import statement) and writes
   `customLayoutWorkingVisible=True` again.
4. `_apply_resolved_presentation()` then commits viewport metrics **a second time** (`:711-712`).

CHK27 measured the commit alone at **0.141 / 0.263 ms median/p95** in D1-heavy (R-87). In steady state (no fade,
no mode transition, no CUSTOM) the resolved record is equal every frame; an equality check costs **0.7 µs**.

**What disappears.** Steady-state resolve + ~25 Qt meta-property writes + one duplicate metric commit + one
override reset per publication: on the order of 15–20 ms/s of GUI-thread Python holding the GIL under heavy load
(*estimate* from CHK27 + measured resolve), competing with the render thread's Python render callbacks
(the R-87 CHK17 concurrent-GIL hypothesis).

**Proposal (single owner, no cache that can outlive the item).**

- In `_apply_visualizer_presentation_items`, early-return when `presentation == item.presentation` **and**
  `bool(root.property("presentationActive")) == active` — the retained item's own record is the only
  "last applied" value (no parallel cache; U-09/R-68 single-geometry-authority rule). Leave
  `item.set_presentation` semantics unchanged.
- Call `_sync_custom_layout_visualizer()` only when a CUSTOM session is bound or presentation actually
  changed; the "no session" branch is already committed truth.
- Delete the duplicate `commit_presentation_metrics` (keep the one owner in `publish_render_snapshot`, which is
  already gated on `has_custom_viewport_override`).
- Optional second step: memoize `_resolve_current_presentation` on its inputs (fades, committed rect/extent,
  origin, display identity geometry/DPR, policy, rotation) — only if the frame-trace shows resolve still matters.

**Must remain true.** `request_present()` still runs for every accepted publication (R-62: never delay/coalesce
visible state); snapshot and item commit still use the *same* resolved record (Visualizer_Presentation §4);
fades/mode-transition frames still project every frame (their record differs); CUSTOM rebase path unchanged
(R-68).

**Implemented (step 1).** `_apply_visualizer_presentation_items` returns early when the retained item's record is
equal **and** the live loader/root geometry and `presentationActive` already match (read back, not cached: CUSTOM sync
moves the loader and retire/transfer paths clear `presentationActive` without changing the record). Measured on the real
QML shell (idle): steady equal publication 20.4 → 4.0 µs; changing records unchanged (≈22 µs). `request_present()` and
snapshot composition are untouched. Deliberately **kept**: the owner's second `commit_presentation_metrics` (≈3 µs) —
it runs after the scene's CUSTOM sync and observes the post-sync override state, so removing it is not worth that edge.
**Open:** the ≈49 µs resolve is now the dominant per-publication cost; memoize only if `--frame-trace` shows it matters.

**Acceptance.**

- [x] Focused: `test_qtquick_scene_controller.py::test_steady_equal_visualizer_publication_performs_no_projection_writes`
      (fails without the fix; covers changed fade, reactivation, externally moved loader), scene/owner/render-bridge/
      presentation suites green; CUSTOM-owner reds are the pre-existing 24.
- [ ] `--frame-trace` D1-heavy: `GUI_SNAPSHOT_PUBLISH → GUI_PRESENTATION_COMMIT_READY` collapses; publication→draw
      neutral-or-better vs CHK26.
- [ ] Physical: activation fade, mode crossfade, CUSTOM resize/Save/Cancel, display hop, startup reveal.

---

## PR-02 — Per-frame queued `frameSwapped` readiness callback in ordinary runtime · P2 · R1 · Risk Low–Medium

**Evidence.** `scene_controller.py:597-600` connects `frameSwapped → _on_frame_swapped` (queued) for every display,
always. `_on_frame_swapped` (`:2296-2320`) snapshots telemetry and `dataclasses.replace`s `QuickSceneReadiness`
every swap even when nothing changed. Measured Python cost ≈3 µs + queued dispatch ≈0.3 µs, i.e. small CPU, but it
posts one GUI event per swap per display (≈90–330 wakeups/s on a 60+165 Hz pair) and is exactly the "dormant
per-frame Python on `frameSwapped`" shape Guardrails §Qt Quick forbids.

**Proposal.** Keep the queued observer connected only while it can change something: until
`ready_for_reveal`, while `_surface_probe_frames_remaining > 0`, while the HUD is enabled, and for a bounded number
of frames after edges that can change readiness (image publication, scene-graph init/invalidate, render error via
a one-shot notification from `RenderNodeTelemetry.note_error`). Re-arm on those edges; disconnect otherwise.

**Must remain true.** R-63: first show/reveal ordering unchanged (do **not** defer first show — R-63 proved it makes
startup worse); startup reveal coordinator still receives readiness (R-07); surface probes around
activation/menu stay (bounded diagnostics used by R-63).

- [ ] Bars: readiness reaches `ready_for_reveal` on cold start, replacement generation, and after a render error;
      steady runtime has no per-swap Python after readiness settles.
- [ ] Physical: cold start crossfade, Settings round-trip, context menu open/close (no black flash).

---

## PR-03 — Background telemetry `replace()` on every transition frame · P2 · R1–R2 · Risk Low

**Evidence.** `RenderNodeTelemetry` (`render/telemetry.py`) `replace()`s a **44-field** frozen dataclass under a lock
in every `note_*`. During transitions the custom node calls `note_sync` (`background_node.py:223`),
`note_transition_sample` (`:268`), `note_transition_drawn` (`:471`) and `note_render` (`:488`) per frame, plus
three `wants_*` lock checks. **Measured ≈9.8 µs per `replace()`** → ≈40 µs of GIL-held render-thread Python per
transition frame per display (≈6.6 ms/s at 165 Hz). The visualizer telemetry was already converted to cheap field
mutation (`visualizer/telemetry.py` docstring) — this is the same fix, not a new design.

**Proposal.** Mirror `VisualizerRenderNodeTelemetry`: plain fields mutated under the lock, `snapshot()` builds
the immutable `RenderNodeSnapshot` on demand. Keep the pixel-capture/probe paths byte-identical (harness oracles).

- [ ] Bars: existing transition pixel-oracle and retained-background contract tests
      (`tests/test_qtquick_retained_background_contract.py`, `tests/test_qtquick_future_transition_gl.py`) unchanged.
- [ ] `--frame-trace`: `BACKGROUND_RENDER_BEGIN → BACKGROUND_RENDER_READY` transition frames neutral-or-better.

---

## PR-04 — Transition finalization re-copies and re-uploads the destination image · P2 · R2 (estimate) · Risk Medium

**Evidence.** At transition start the custom node uploads the destination with `glTexImage2D`
(`render/image_textures.py:171-243`). At finalization the destination becomes the base image and the native branch
builds a **deep copy** `QImage(bytes…).copy()` (`render/background_image_node.py:169-175`) — 33 MB at 3840×2160 —
inside `updatePaintNode`, i.e. while the GUI thread is blocked in the threaded render loop's sync, then
`createTextureFromImage` uploads the same pixels again. Two uploads and one 33 MB memcpy+allocation per display per
image change, landing on the first steady frame after the transition (when a visualizer frame is also due).

**Not yet proven to be visible.** R-84 already flagged the residual "Python bytes RGBA payload" seam and named a
Qt-native detached buffer through texture upload as the next architecture step if a residual spike survives.

**Evidence step first.** One D1-heavy `--frame-trace` run with 3–4 transitions: compare `QUICK_SYNC_*`/`RENDER_*`
for the first 3 frames after each `transition_finalized` against steady frames.

**If confirmed, candidate repairs (pick one, measure, keep one):**

1. Drop `.copy()` by keeping the `PresentationImage` referenced by the node until the native texture has been
   committed (the `bytes` buffer then backs the `QImage`); verify PySide buffer-lifetime semantics with a real Qt
   test first.
2. Pre-create the native texture for the destination during the transition (spread across the run) so
   finalization only swaps nodes.

**Must remain true.** R-60 texture identity (one DPR owner, no rekey), R-50 byte-bounded retention and
release-on-owner-context, R-63 no black flash, CHK21 steady native ownership.

- [ ] Evidence captured and classified (keep / fix).
- [ ] If fixed: `tests/test_qtquick_retained_background_contract.py` + VRAM/texture accounting bars; physical
      transition end on both displays.

---

## PR-05 — Unrelated scene frames force the Python visualizer render callback · P3 · Reward unknown · Risk High (architecture)

**Evidence.** Qt Quick re-renders the whole scene whenever anything is dirty, so every frame caused by a QML
animation (artwork fade, Friend Pulse 5 s row glow, metadata crossfade, menu, hover glow) or a transition re-runs
`VisualizerRenderNode.render()` (Python + GL state fences) with an unchanged snapshot. Local 2026-09-22 dev log
(`logs/screensaver_perf.log`): transition-idle windows at 21:34:10 and 21:39:32 show `viz_draw_fps` 110–117 vs
`viz_revision_hz` ≈90, i.e. 20–27 redundant Python renders/s; transitions on a 165 Hz display raise this to the
panel rate (R-87 CHK5/CHK10).

**Why P3/operator-only.** The only removal is to cache the visualizer in an offscreen texture and composite it
natively on non-revision frames. `Compositor_Architecture.md §6` selected inline `QSGRenderNode` precisely to avoid
"an extra offscreen texture/composite pass", and only one custom-render primitive may exist. Changing that is an
architecture decision with installed A/B, not an optimization.

- [ ] Operator decision: record `draw − revision` per second in a normal installed run; if persistently large under
      load, open an architecture spike; otherwise close as accepted cost.

---

## PR-07 — Eager compile of every family QML component at startup · P3 · R1 · Risk Low

`QuickSceneFactory.__init__` (`scene_controller.py:219-234`) compiles all 12 registered family components.
Measured dev-source compile: DisplayScene 178 ms, OverlayWidget 38 ms, families ≈290 ms (total ≈517 ms). Frozen
builds with a warm QML disk cache will be cheaper; inactive families still cost compile + memory.

- [ ] Compile a family component on its first `create_ordinary_widget_family` call (still one process-level cache,
      still before the owning window is shown). Measure cold-start-to-reveal on an installed build before/after.
- [ ] Must keep: import dormancy rules (Spec §Import dormancy), R-07/startup reveal ordering.
