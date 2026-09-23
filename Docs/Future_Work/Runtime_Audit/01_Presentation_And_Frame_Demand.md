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
- Second step (memoizing `_resolve_current_presentation`): **parked**, see below.

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

**Resolve memo — Park (operator 2026-09-23).** The remaining ≈47.6 µs resolve (≈4.3 ms/s) is spread over tiny
publications. No second geometry/presentation cache; the retained item stays the comparison authority. Reopen only if
GUI publication latency profiling points back here. Soak evidence (08): publication ≈89.91 Hz vs GUI admission
≈88.26 Hz, i.e. small latest-wins coalescing and no cadence collapse. `viz_geometry_mismatches` went 0 → 1 once, at
10:38:32, with no QML message, fault or hang: the fail-closed stale-presentation guard was exercised. Preserve that
guard in any presentation work.

**Acceptance.**

- [x] Focused: `test_qtquick_scene_controller.py::test_steady_equal_visualizer_publication_performs_no_projection_writes`
      (fails without the fix; covers changed fade, reactivation, externally moved loader), scene/owner/render-bridge/
      presentation suites green; CUSTOM-owner reds are the pre-existing 24.
- [ ] `--frame-trace` D1-heavy: `GUI_SNAPSHOT_PUBLISH → GUI_PRESENTATION_COMMIT_READY` collapses; publication→draw
      neutral-or-better vs CHK26.
- [ ] Physical: activation fade, mode crossfade, CUSTOM resize/Save/Cancel, display hop, startup reveal.

---

## PR-02 — Per-frame queued `frameSwapped` readiness callback in ordinary runtime · P2 · R1 · Risk Low–Medium · Parked

**Evidence.** `scene_controller.py:597-600` connects `frameSwapped → _on_frame_swapped` (queued) for every display,
always. `_on_frame_swapped` (`:2296-2320`) snapshots telemetry and `dataclasses.replace`s `QuickSceneReadiness`
every swap even when nothing changed. It is exactly the "dormant per-frame Python on `frameSwapped`" shape Guardrails
§Qt Quick forbids (DC-04). Measured 5.6 µs per swap: ≈1.8 ms/s at 165 Hz on two displays, ≈0.5 ms/s in the soak
(≈89.4 swaps/s on the traced Visualizer display).

**Decision (operator 2026-09-23): Park.** The saving is real but small, and startup/reveal/no-black-flash behaviour is
historically fragile. Do not touch R-63 first-show ordering to collect it. Reopen only when the readiness/reveal
machinery is already being changed, or new profiling shows the callback has become material. DC-04 stays documented.

**If reopened.** Keep the queued observer connected only while it can change something: until `ready_for_reveal`,
while `_surface_probe_frames_remaining > 0`, while the HUD is enabled, and for a bounded number of frames after edges
that can change readiness (image publication, scene-graph init/invalidate, render error via a one-shot notification
from `RenderNodeTelemetry.note_error`). Must remain true: R-63 first show/reveal ordering (do **not** defer first
show); the startup reveal coordinator still receives readiness (R-07); surface probes around activation/menu stay.
Bars: readiness reaches `ready_for_reveal` on cold start, replacement generation and after a render error; no per-swap
Python after readiness settles; physical cold start crossfade, Settings round-trip, context menu open/close.

---

## PR-03 — Background telemetry `replace()` on every transition frame · P2 · R1–R2 · Risk Low · `[~]`

**Evidence.** `RenderNodeTelemetry` (`render/telemetry.py`) `replace()`s a **44-field** frozen dataclass under a lock
in every `note_*`. During transitions the custom node calls `note_sync` (`background_node.py:223`),
`note_transition_sample` (`:268`), `note_transition_drawn` (`:471`) and `note_render` (`:488`) per frame, plus
three `wants_*` lock checks. **Measured ≈9.8 µs per `replace()`** → ≈40 µs of GIL-held render-thread Python per
transition frame per display (≈6.6 ms/s at 165 Hz). The visualizer telemetry was already converted to cheap field
mutation (`visualizer/telemetry.py` docstring) — this is the same fix, not a new design.

**Proposal.** Mirror `VisualizerRenderNodeTelemetry`: plain fields mutated under the lock, `snapshot()` builds
the immutable `RenderNodeSnapshot` on demand. Keep the pixel-capture/probe paths byte-identical (harness oracles).

**Implemented.** `RenderNodeTelemetry` keeps plain fields; `snapshot()` rebuilds the unchanged `RenderNodeSnapshot`
only when read after a change (the GUI `_on_frame_swapped` path reads it per swap, so build-on-every-read would only
have moved the cost). Idle measurement: sync+render+draw notes per transition frame 29.6 → 2.2 µs on the render
thread; one note + GUI read 9.4 → 5.4 µs.

- [x] Bars: `tests/test_render_node_telemetry.py` (notes never compose snapshots; identity changes only on change) plus
      the retained-background, render-node and transition suites unchanged (only the pre-existing Melt red).
- [ ] `--frame-trace`: `BACKGROUND_RENDER_BEGIN → BACKGROUND_RENDER_READY` transition frames neutral-or-better.

---

## PR-04 — Transition finalization re-copies and re-uploads the destination image · P1 · R3 · Risk Medium

**Mechanism.** At transition start the custom node uploads the destination with `glTexImage2D`
(`render/image_textures.py:171-243`). At finalization the destination becomes the base image and the native branch
builds a **deep copy** `QImage(bytes…).copy()` (`render/background_image_node.py:169-175`) — 33 MB at 3840×2160 —
inside `updatePaintNode`, i.e. while the GUI thread is blocked in the threaded render loop's sync, then
`createTextureFromImage` uploads the same pixels again, labelled straight-alpha `Format_RGBA8888`.

**Evidence (details and the format probe table in 08).**

- Operator `--frame-trace` 2026-09-23 08:06–08:09, first Quick render cycle after each transition end vs that screen's
  median:

  | Screen | Steady cycle (median) | First cycle after transition end | Of which sync (`QImage.copy`) | Of which render pass (re-upload) |
  | --- | ---: | ---: | ---: | ---: |
  | 1 — 3840×2160, Visualizer | 2.8 ms | **24.7–24.8 ms** (×3) | 4.3–4.9 ms | 13.5–14.1 ms |
  | 0 — 2560×1440 | 1.1 ms | 6.9–8.4 ms (×3) | 2.5–3.3 ms | ≈0.1 ms |

- D1 soak: all ten retained transition endings cost 26.62–90.58 ms (median ≈58.9 ms; sync 4.58–21.52 ms,
  render/upload 21.88–68.99 ms), 5.5–9.9× the following 60 cycles; ≈26.6 and 34.7 ms after external load eased.
- Idle probe: Qt converts the straight-alpha image to premultiplied on the render thread before upload — blocking
  prepare 8.12 ms with `Format_RGBA8888`, 0.15 ms with `Format_RGBA8888_Premultiplied`.

**Decision (operator 2026-09-23).**

- **Stage A — Do with care (partial mitigation).** Guarantee opaque background pixels at the narrowest processing
  boundary (FILL's perfect-fit return in `rendering/image_processor_async.py` is the only branch that can leak alpha;
  every other branch paints onto black), with one documented rule: transparent sources composite over black. Do not
  blanket-convert in the generic `capture_qimage`. Then label the native `QImage` `Format_RGBA8888_Premultiplied`;
  never label non-opaque pixels premultiplied. Render/upload stays the larger cost under load, so PR-04 remains open
  until a post-change frame trace measures the whole transition-end cycle.
- **Stage B — Gated.** Drop `.copy()` (≈3–4.5 ms sync) only after a real Qt/PySide lifetime test proves the immutable
  `PresentationImage.rgba8` storage stays valid for as long as QSG/texture creation may reference it. Do not infer
  synchronous consumption.
- **Rejected:** moving the upload earlier (relocates the stall into the transition). **Blocked:** zero re-upload
  handoff — `QSGOpenGLTexture::fromNative`, `QRhiTexture.createFrom` and `QRhiTexture.nativeTexture` are not bound in
  PySide 6.9.1.

**Must remain true.** R-60 texture identity (one DPR owner, no rekey), R-50 byte-bounded retention and
release-on-owner-context, R-63 no black flash, CHK21 steady native ownership; ordinary opaque images render
identically.

- [x] Stage A implemented. Source finding: the ImageWorker prescale (the only foreground processor) leaked alpha in
      **every** display mode — FILL returned the crop unchanged and FIT/SHRINK `paste()`d without a mask — not only
      the in-process FILL perfect-fit branch. Both owners now composite source transparency over opaque black (worker:
      right after decode when `has_transparency_data`, so scaling/sharpening/padding see opaque pixels; in-process:
      perfect fit draws onto a black canvas like its other branches). The native branch labels the `QImage`
      `Format_RGBA8888_Premultiplied` (the texture was already `TextureIsOpaque`); `.copy()` is unchanged (Stage B).
      Rule: `Docs/Guardrails.md` §Wallpaper pixel opacity. The unused `IMAGE_DECODE` worker handler is not a wallpaper
      path and is unchanged.
- [x] Bars: `tests/test_wallpaper_opaque_pixels.py` — transparent source through every in-process and worker mode
      yields alpha 255 composited over black (7 of 11 fail without the fix); opaque perfect-fit sources pass through
      untouched; the processed route captures opaque pixels; the native branch hands Qt a premultiplied `QImage` with
      byte-identical opaque pixels. Image pipeline/worker/cache-accounting, retained-background, texture, render-node
      and transition-geometry suites green per file.
- [x] Post-Stage-A `--frame-trace` (2026-09-23 17:05 session; one transition end per display survives): on the
      3840×2160 Visualizer display the handoff spans two Quick cycles — 4.6 ms sync (the `.copy()`) in the first,
      16.2 ms render/upload in the next (≈21 ms), against a 3.2 ms median cycle. The 2560×1440 display: 3.7 ms first
      cycle. Stage A is a partial mitigation; the full native re-upload remains structurally visible.
- [x] Physical (2026-09-23): no black flash at transition end on both displays; ordinary wallpaper unchanged. The
      transparent-PNG case is owned by the automated contract (operator waived a physical check: SRPSS shows
      photographs).
- [ ] Remaining: Stage B lifetime test; then quantify the remaining handoff before choosing a native helper or a
      PySide upgrade for the zero-re-upload route.
- [ ] Stage B prerequisite: Qt/PySide buffer-lifetime test, then the same bars.

---

## PR-07 — Eager compile of every family QML component at startup · P3 · R1 · Risk Low · Parked

`QuickSceneFactory.__init__` (`scene_controller.py:219-234`) compiles all 12 registered family components.
Measured dev-source compile: DisplayScene 178 ms, OverlayWidget 38 ms, families ≈290 ms (total ≈517 ms); a 2026-09-23
re-measure of the first `QuickSceneFactory` was ≈210 ms. Frozen builds with a warm QML disk cache will be cheaper;
inactive families still cost compile + memory.

**Decision (operator 2026-09-23): Park** — startup-only. Reopen only if startup-to-reveal becomes a target. If
reopened: compile a family component on its first `create_ordinary_widget_family` call (still one process-level cache,
still before the owning window is shown), measure cold-start-to-reveal on an installed build before/after, and keep the
import dormancy rules (Spec §Import dormancy) and R-07 startup reveal ordering.
