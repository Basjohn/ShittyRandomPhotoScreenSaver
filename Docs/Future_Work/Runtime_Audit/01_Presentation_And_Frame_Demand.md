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

## PR-04 — Transition finalization re-uploads the destination image · P1 · R3 · Risk Medium

**Mechanism (after Stages A and B).** At transition start the custom node uploads the destination with
`glTexImage2D` (`render/image_textures.py`). When the run finalizes, the destination becomes the retained base image
and the native branch (`render/background_image_node.py`) wraps the same `PresentationImage` bytes in a `QImage` (no
copy since Stage B) and `createTextureFromImage` uploads those pixels a second time.

**Evidence — 2026-09-23 19:29–19:35 `--frame-trace`, 16 transition endings per display over three runtime
generations**, pairing each run's last custom render with the next Quick render cycle on the same screen:

| Screen | Median cycle | First cycle after an end | Sync | Render pass |
| --- | ---: | ---: | ---: | ---: |
| 1 — 3840×2160, Visualizer | 7.0 ms | 13.5–24.8 ms (median 19.3) | 0.33–1.53 ms | median 15.3 ms (6.2 normal), max 21.1 |
| 0 — 2560×1440 | 2.1 ms | 1.7–7.6 ms (median 3.3) | median 0.69 ms | ≈0.1 ms; +1.2 ms before the pass |

Stage B removed the ≈4.6 ms deep copy from sync. The 33 MB re-upload remains; on the Visualizer display its stall
materialises inside the render pass (≈9–13 ms above a normal cycle). Earlier evidence: 24.7–24.8 ms before Stage A;
26.6–90.6 ms in the D1 soak under external GPU load (not directly comparable).

**Stages A and B are accepted** (00 §Accepted).

**Native zero-re-upload handoff — admitted 2026-09-23 as a bounded investigation and prototype.** Goal: the retained
background adopts the transition's destination GL texture instead of uploading the same pixels again. Gates, in order:
API feasibility on the pinned Qt/PySide stack (PySide 6.9.1 binds none of `QSGOpenGLTexture::fromNative`,
`QRhiTexture.createFrom`, `QRhiTexture.nativeTexture`); one authoritative ownership transfer inside the existing
texture host (no second deletion registry); pixel/geometry parity with Stage B; GL state and context legality (CHK26
and R-87 untouched); packaging durability in the Nuitka build; measured removal of the duplicate upload. Stage B stays
the reference and the attributed fallback until the native route passes all gates; if it cannot demonstrate safe
ownership, substantial benefit and durable packaging, PR-04 parks at Stage B.

**Must remain true.** R-60 texture identity (one DPR owner, no rekey), R-50 byte-bounded retention and
release-on-owner-context, R-63 no black flash, CHK21 steady native ownership, CHK26 inherited-state optimization;
ordinary opaque images render identically.

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
