# SRPSS | Current Plan

## FEEDS | Custom 1 closure and bounded family expansion (ACTIVE)

**Authority:** `Docs/Reference/Feeds.md` owns implemented architecture. `Docs/Future_Work/Feeds.md` owns the still-pending expansion/deferred work. Continue to audit **durability, content adaptability and performance neutrality** before multiplying sources or widget identities.

### Accepted current-tree evidence

- [x] `feeds_custom_1` is the only admitted FEEDS runtime widget. It uses the shared bounded RSS/Atom transport/parser/cache/source/runtime path, retained List/Grid/Compact QML, HTTP/S-only external actions, event-admitted local artwork and the ordinary shared Edit/CUSTOM owner.
- [x] The requested consolidated Windows regression gate is green on the current tree. Do not retain older focused pass counts as current acceptance evidence.
- [x] Physical Custom 1 artwork editing is accepted for free X/Y/width/height adjustment, with Grid text/content reflow following the changed artwork geometry rather than preserving a fixed landscape slot.
- [x] Physical source adaptability has exercised an image-sparse Hacker News feed plus image-bearing GitHub and Ars feeds. Image absence is a valid feed/content state, and tested story links reached the correct external destinations.
- [x] Product-wide clickable highlighting is physically accepted on the current tree: semantic colour is the resting/state language and an admitted active click target uses bright white where the shared contract calls for a border/separator/emphasized text cue. Text-dense row surfaces remain borderless where specified; Media retains its no-hover-border exception.
- [x] The secure Winlogon handoff remains the external-link authority: saver-side queue admission is the success boundary, helper wake is best-effort, and helper readiness never gates normal saver exit. Reddit/Reddit2, Gmail, FEEDS and Steam-family actions stay behind the same product-action/session boundary rather than calling direct browser APIs from retained runtime code.

### Remaining Custom 1 acceptance

- [ ] Exercise a full Edit transaction on the current tree: widget-wide alignment flip, parent resize before save, child move/resize, Reset, bounded Ctrl-Z, child lock, Save, leave/re-enter Edit and fresh runtime recreation. Verify the header, refresh rail, Grid/List content rails and overflow retain one semantic orientation without mirroring pixels or snapping back.
- [ ] Verify the per-feed **Show Feed Subtitle** setting off/on and Save/reopen behavior, including the separate below-pill subtitle and retained header geometry.
- [ ] Prove last-good behavior through a fresh offline restart, then restore connectivity and verify ordinary conditional refresh without blanking or endpoint cross-contamination.
- [ ] Disable/replace Custom 1 while source/artwork work is queued or in flight; verify callbacks retire cleanly, no stale completion republishes, no transport/provider work survives the final active lease and no native fault appears.

### Multi-CUSTOM expansion gate

Custom 2–4 remain dormant until the same shared codepath is proven with more than one active source. Do **not** clone providers, QML, editor state, schedulers or persistence owners.

- [ ] Exercise two simultaneous independent endpoints through refresh, cancellation, one-source retirement and reactivation. Retiring A must not cancel, delay or publish into B; identical endpoints must continue to share one source transaction where privacy/cache identity permits it.
- [ ] Prove artwork eviction/current-generation protection with simultaneous sources, including a stalled/cancelled source and source retirement during bounded image work.
- [ ] Exercise native DNS/connect stall retirement and confirm the existing bounded cancellation/lifetime rules are sufficient before multiplying runtime leases.
- [ ] Add deterministic Custom 2–4 monogram collision ordinals through the existing cached vector-monogram path, then admit the remaining fixed IDs through the same descriptor/runtime/QML component.

### Independent Games You Follow verification

- [ ] When a newly refreshed syndicated Steam article actually contains its validated original article URL, verify that exact article opens that destination. Older cached records without that URL correctly fall back to the app news hub. This check must not trigger a whole followed-set sweep and does not block FEEDS work.

## Voxel Sphere | isolated energy-floor controls

The independent fragment and particle minimum-energy settings are implemented with curated/default and user-authored preset protection. Focused pure-Python settings/preset gates were previously reported green. The remaining Sphere-specific operator gate is the native Windows settings/preset run and active-music observation of independent floor effects, Reset and Custom Save/reopen. Do not retune authored values on the operator's behalf; promote a reproduced defect here if one appears.

## Future Work transitions | correction and removal

`Docs/Future_Work/Transition_Expansion.md` owns the detailed work; `Docs/Reference/Transitions.md` owns current behavior and controls.

- [~] Crumble's separate crack-formation stage is implemented on real fracture borders before chunk/debris motion; retain solid depth and wall debris. Operator visual acceptance remains open.
- [~] Melt remains explicitly WIP and is labelled `Melt Drip (WIP - VERY SHITTY)` in Settings while the stable transition ID stays `Melt Drip`. The rejected detached-ball/ray-marched volume has been replaced by a shallow cohesive screen-space liquid front: irregular attached fingers/rivulets, a wet meniscus, local-only refraction/streaking and highlights. Pixels well behind the wet front remain the unwarped source image so horizontal Melt cannot shred the whole photograph into slabs. Operator visual acceptance remains open.
- [~] Awaiting operator visual acceptance of Glass, Tiles, Ink and corrected Crumble at authored durations.
- [ ] Observe both displays with active music and representative heavy external load; confirm Visualizer freshness and transition first-use behavior against the accepted baseline.
- [ ] Validate the installed/frozen build, material save/reopen/Reset and repeated switch/interrupt/retire.


## Runtime -> Settings replacement lifecycle

- [~] Restore the last Settings top-level tab plus its semantic subsection/builder on every runtime round-trip. Widgets, Visualizers, Display, Transitions and Themes persist semantic selection only; restored content is anchored at the top rather than replaying stale pixel scroll. Native round-trip validation remains open.

Transition terminalization, Visualizer owner retirement and shared Core Audio callback retirement are accepted current contracts guarded by source/tests and `Docs/Guardrails.md`; they are not active-plan tasks unless a concrete regression reopens them.

## Runtime audit 2026-09-22 | Waves A–B landed, physical validation pending

`Docs/Future_Work/Runtime_Audit/00_Index.md` holds the prioritized, source-cited candidate register, its per-item acceptance bars and the historical-bug cross-audit. Wave A (zero-behaviour hygiene) and Wave B (below) are implemented, test-gated and pushed; each `[~]` item needs its physical check before it closes. Waves C/D stay candidates until promoted here.

- [~] TX-02 — Random rotation no longer writes Settings or overwrites authored Slide/Wipe directions (session-memory pick handed to the batch resolver; visible Random behaviour unchanged). Physical: two-display Random batches still share one transition + direction; Settings shows the authored direction after a Random session.
- [~] LC-06 — canonical defaults are built once per profile (callers still get private copies); context menu, transition batches and widget routing read sections. Physical: context-menu open/close feel and Settings round-trip `[LIFECYCLE]` construction time.
- [~] TX-01 — Glass/Crumble per-run geometry is prepared on COMPUTE when the batch resolves (render thread uploads, or builds identical bytes if not ready) and packs 3× faster. Physical: Glass/Crumble/Tiles start on both displays with active music (`--frame-trace` first `BACKGROUND_RENDER_*` frame near steady class).
- [~] PR-01 — steady equal visualizer publications no longer rewrite the QML shell (20.4 → 4.0 µs each); `request_present()` still runs once per publication. Physical: activation fade, mode crossfade, CUSTOM resize/Save/Cancel, display hop, startup reveal.
- [~] PR-03 — background render telemetry notes are plain field updates (render thread 29.6 → 2.2 µs per transition frame); the snapshot is built only when read after a change.
- [~] PW-01 — timeline-only Media refreshes reuse the held album art for the same track instead of re-reading the WinRT thumbnail (refresh count unchanged; `artwork_reused` in `[MEDIA_EVENT] summary`). Physical: track change, same-album next track, podcast/video providers, artwork fade.
- [~] VZ-01 — paused idle waveform samples are synthesized only while Oscilloscope is active (other modes: paused tick 150.6 → 36.4 µs); the waveform generation still advances every tick. Physical: paused idle for all six modes; pause→play and play→pause on Sine/Osc (no flat line, snap-back or direction inversion); paused switch into Oscilloscope.
- [ ] LC-01 (GC freeze covers generation 0 only): the 2026-09-23 run ended 18 s after its Settings replacement, before any gen-2 pass (≈15 min cadence). Needs ≥20 min of runtime after a Settings round-trip with `--perf`; the pending R-84 3–5-cycle run can carry it if it runs that long. Grep `[PERF][GC_POLICY] generation=2 duration_ms=`.

**Wave C (evidence first) — 2026-09-23 results.** Wave D stays a candidate.

- [ ] **PW-02 confirmed** (`tests/test_media_io_starvation.py`, strict xfails): four stalled network tasks keep a Media transport command and the activation refresh (the Visualizer's play/pause truth) queued past 0.42 s. Operator: approve a Media-only serial lane (one lazy event-driven worker owned by the shared Media runtime). The audit's original idea — reuse the WinRT observation worker — is rejected because observation teardown waits only 2 s on that worker.
- [ ] **PR-04 confirmed** (operator `--frame-trace`): every transition end costs ≈24.8 ms on the 3840×2160 Visualizer display (4.5 ms `QImage.copy` + 13.5 ms re-upload) vs 2.8 ms steady — 1–2 Visualizer frames per image change. Zero-re-upload handoff is blocked on PySide 6.9.1 bindings (no `fromNative`/`createFrom`/`nativeTexture`). Operator: accept a small native helper / wait for bindings, or approve only the `.copy()` removal (saves the 4.5 ms part; needs a Qt lifetime test first).
- [~] **VZ-05** — render fields were frozen twice per tick; single-freeze landed (61-key record 155.8 → 65.4 µs, output identical). Epoch cache parked.

## Known failing tests and anomalies (tracked until resolved)

Pre-existing reds and runtime anomalies found while gating the runtime audit. Each stays here until fixed or explicitly retired; do not treat them as noise in a gate.

- [ ] **Crumble `crack_complexity` dead zone (product defect).** `fracture_cells` clamps site spread at `.48`, so every value above ~1.26 — including the 1.8 default (d56d7099) — renders identically up to the 2.0 maximum; half the slider does nothing. Kept visible by the strict xfail `test_qtquick_crumble_volume.py::test_crack_complexity_is_live_across_its_whole_range`. Operator decision: remap spread across the full 0.5–2.0 range (changes the default look) or narrow the range/default.
- [ ] **Crumble debris oracle red.** `test_real_driver_each_crumble_control_changes_the_volume[debris-1.0]`: debris 0.65→1.0 at progress 0.53 moves 0.031 mean (bar 0.08) even on the pinned calibrated baseline, after the debris rework (db4d5b80/1c6cf165). Operator: is subtler mid-range debris intended? If yes, re-express the oracle as debris on/off; if not, strengthen debris.
- [ ] **Melt control oracles red.** `test_qtquick_melt_surface.py::test_liquid_material_controls_affect_the_wet_front[gloss]` (gloss 0↔1 at 0.43: 0.011 whole-frame mean, bar 0.5) and `test_qtquick_future_transition_gl.py::test_authored_controls_change_rendered_pixels[melt_drip-detail-2.0]` (0.081, bar 0.1). The 5.0.4 RC++ rework (1c6cf165) confines shading to a narrow moving front, so whole-frame means were calibrated for the rejected volume design. Decide the intended gloss/detail strength with Melt's open visual acceptance, then re-measure inside the wet-front band.
- [ ] **Core Audio double release (fixed 50052050, physical check open).** `ctypes.cast` of the Activate()d endpoint shared the COM pointer without AddRef; a later GC released it again (access violation during replacement construction; also the `test_s_hotkey_workflow.py` exit segfault). Now `QueryInterface`. Physical: several Settings round-trips, OSD/Media mute enable-disable and a default-output device switch on the installed build with no `native_faults.log` fault.
- [~] **Worker processes outlived a crashed UI process (fixed, physical check open).** `daemon=True` reaps workers only on a normal exit; after a native crash or forced termination they polled their request queue every 100 ms forever (19 orphans accumulated from crashing test runs). Workers now exit when `multiprocessing.parent_process()` is gone (`tests/test_worker_parent_death.py`). Physical: in the installed build, End task the main SRPSS process in Task Manager during a run; its worker processes (further instances of the same executable) must disappear within ~1 s.
- [ ] **Prefetch double batch.** At 22:58:31 (operator run 2026-09-22) four `FILL(QImage)` lines landed together 11 s after a rotation instead of the usual pair; benign so far, classify when prefetch is next examined.
- Operator run 2026-09-22 22:53–22:59: `native_faults.log` recorded no fault; `hang_stacks.log` shows the replacement-construction watchdog armed 13× (22:55–23:19) and never fired.

## Handoff and regression rules

When an accepted behavior changes, select only the relevant targeted tests and physical observations; do not re-accept unrelated OSD, Media or widget systems. Keep full superseding GODZIPs with the canonical three `.godzip/` files, manifest-backed replace/delete instructions and no temporary scripts or compiled artifacts. Test commands belong in chat, not an added documentation file.
