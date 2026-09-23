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
- [ ] **Crumble control rework — admitted (operator 2026-09-23).** Crack complexity must visibly mutate the fracture shape/pattern much more (new geometry; a remap cannot deliver it) and debris must visibly change debris density/size/dispersion/flight. Design options and bars: `Docs/Future_Work/Transition_Expansion.md` §Control rework.
- [ ] **Melt gloss/detail rework — decided (operator 2026-09-23).** Keep both controls; within the Melt visual rework, first establish intended perceptible min/mid/max states, then measure inside the wet band. Same section.
- [ ] Observe both displays with active music and representative heavy external load; confirm Visualizer freshness and transition first-use behavior against the accepted baseline.
- [ ] Validate the installed/frozen build, material save/reopen/Reset and repeated switch/interrupt/retire.


## Runtime -> Settings replacement lifecycle

- [~] Restore the last Settings top-level tab plus its semantic subsection/builder on every runtime round-trip. Widgets, Visualizers, Display, Transitions and Themes persist semantic selection only; restored content is anchored at the top rather than replaying stale pixel scroll. Native round-trip validation remains open.

Transition terminalization, Visualizer owner retirement and shared Core Audio callback retirement are accepted current contracts guarded by source/tests and `Docs/Guardrails.md`; they are not active-plan tasks unless a concrete regression reopens them.

## Runtime audit 2026-09-22 | operator decisions 2026-09-23, implementation queue

`Docs/Future_Work/Runtime_Audit/` holds the register (00), item detail (01–05), structure and the considered-and-rejected list (06), historical-bug constraints (07), and the evidence and decision for every open item (08). The 2026-09-23 D1 heavy-load diagnostic soak (`logs/evidence_chest/logsb86eee25f4.zip`, diagnostics on, heavy external load) is event-correlated evidence only, never an ordinary-runtime baseline.

**Landed; each closes after its physical check.**

- [~] TX-02 — Random rotation no longer writes Settings or overwrites authored Slide/Wipe directions (session-memory pick handed to the batch resolver; visible Random behaviour unchanged). Physical: two-display Random batches still share one transition + direction; Settings shows the authored direction after a Random session.
- [~] LC-06 — canonical defaults are built once per profile (callers still get private copies); context menu, transition batches and widget routing read sections. Physical: context-menu open/close feel and Settings round-trip `[LIFECYCLE]` construction time.
- [~] TX-01 — Glass/Crumble per-run geometry is prepared on COMPUTE when the batch resolves (render thread uploads, or builds identical bytes if not ready) and packs 3× faster. Soak: retained Crumble starts no longer show the old 11–40 ms first-frame class. Still open: Glass/Tiles start on both displays with active music (`--frame-trace` first `BACKGROUND_RENDER_*` frame near steady class).
- [~] PR-01 — steady equal visualizer publications no longer rewrite the QML shell (20.4 → 4.0 µs each); `request_present()` still runs once per publication. Physical: activation fade, mode crossfade, CUSTOM resize/Save/Cancel, display hop, startup reveal.
- [~] PR-03 — background render telemetry notes are plain field updates (render thread 29.6 → 2.2 µs per transition frame); the snapshot is built only when read after a change.
- [~] PW-01 — timeline-only Media refreshes reuse the held album art for the same track (soak: `artwork_reused=1196` of 1,222 event refreshes). Physical: track change, same-album next track, podcast/video providers, artwork fade.
- [~] VZ-01 — paused idle waveform samples are synthesized only while Oscilloscope is active (other modes: paused tick 150.6 → 36.4 µs); the waveform generation still advances every tick. Physical: paused idle for all six modes; pause→play and play→pause on Sine/Osc (no flat line, snap-back or direction inversion); paused switch into Oscilloscope.
- [~] VZ-05 — render fields were frozen twice per tick; single-freeze landed (61-key record 155.8 → 65.4 µs, output identical).

**Admitted queue, in order.** Each slice is its own checkpoint with the bars in 08.

- [~] **1 · LC-05** — the product refresh now runs before `open_at()` (the runtime relays the request before opening; the model's existing tuple equality stays the only "unchanged" check). Bar: `test_context_menu_entries_are_refreshed_before_the_menu_becomes_visible`. Physical: open the menu after Next/transition/dimming changes — no visible row rebuild.
- [~] **2 · VZ-03** — with `--perf` off the logical tick builds no phase recorder (no closure, dict or `perf_counter` samples); with it on, the slow-tick breakdown is unchanged. Bar: `tests/test_visualizer_tick_phase_diagnostics.py`. No physical check beyond the next `--perf` run showing the breakdown on a slow tick.
- [~] **3 · PW-05** — `ThreadManager.single_shot` returns a `SingleShotHandle` (not a `QTimer`); Feed and Games-You-Follow deadlines now live in the generation-owned single-shot registry (their hand-rolled parentless `QTimer`s are gone). Bar: `tests/test_single_shot_handle.py`. Physical: Feed and Games-You-Follow refresh on schedule; Settings round-trip leaves no stray deadline (`scheduled_single_shots_by_generation` in `--usage`).
- [ ] **4 · PW-03 (Clock only)** — split Clock time/tick notifies from style/config as a few semantic epochs; before/after binding cost measured.
- [ ] **5 · VZ-04** — waveform samples carried only for Oscilloscope; `waveform_count`/generation unchanged; per-mode consumer bar; BTF active-music lane.
- [ ] **6 · PR-04 Stage A** — opaque background pixels at the processing boundary (FILL perfect-fit; transparent sources composite over black) plus a premultiplied native `QImage` label. A partial mitigation: PR-04 stays open until a post-change frame trace measures the whole transition-end cycle on the 4K Visualizer display.
- [ ] **7 · PW-02** — per-category IO queue-wait telemetry first, then a separate Media-only serial lane (not the WinRT observation lane, not a bigger pool, no poll), generation-owned and stopped at owner retirement.

**Gated.**

- [ ] PR-04 Stage B — drop the native `.copy()` only after a Qt/PySide lifetime test proves `PresentationImage.rgba8` outlives every QSG/texture reference.

**Watch / parked / closed (08).** Watch: PW-04 Feed model reset (trigger: FEEDS Custom 2–4 physical testing shows delegate/artwork churn) and PW-03 Media (measure one real edge after the Clock split). Parked: PR-02 (DC-04 stays documented), PR-01 resolve memo, PR-07, ST-01/ST-02, VZ-05 epoch cache, VZ-07. Closed: LC-01 (post-replacement gen-2 only), PR-05, PW-06, the prefetch double batch.

## Known failing tests and anomalies (tracked until resolved)

Pre-existing reds and runtime anomalies found while gating the runtime audit. Each stays here until fixed or explicitly retired; do not treat them as noise in a gate.

- [ ] **Crumble `crack_complexity` dead zone (product defect).** `fracture_cells` clamps site spread at `.48`, so every value above ~1.26 — including the 1.8 default (d56d7099) — renders identically up to the 2.0 maximum. Kept visible by the strict xfail `test_qtquick_crumble_volume.py::test_crack_complexity_is_live_across_its_whole_range`. Decided 2026-09-23: fixed by the Crumble control rework (new geometry), whose monotonic shape-metric bars replace the xfail.
- [ ] **Crumble debris oracle red.** `test_real_driver_each_crumble_control_changes_the_volume[debris-1.0]`: debris 0.65→1.0 at progress 0.53 moves 0.031 mean (bar 0.08), and on/off changes ≤0.22% of pixels. Decided 2026-09-23: debris must visibly change; fixed inside the same Crumble rework.
- [ ] **Melt control oracles red.** `test_qtquick_melt_surface.py::test_liquid_material_controls_affect_the_wet_front[gloss]` (gloss 0↔1 at 0.43: 0.011 whole-frame mean, bar 0.5) and `test_qtquick_future_transition_gl.py::test_authored_controls_change_rendered_pixels[melt_drip-detail-2.0]` (0.081, bar 0.1). Decided 2026-09-23: keep gloss/detail and rework them with Melt — intended min/mid/max first, then oracles inside the wet band.
- [ ] **Core Audio double release (fixed 50052050, physical check open).** `ctypes.cast` of the Activate()d endpoint shared the COM pointer without AddRef; a later GC released it again (access violation during replacement construction; also the `test_s_hotkey_workflow.py` exit segfault). Now `QueryInterface`. Supporting: the 2026-09-23 soak ran four Settings and two CUSTOM Edit round-trips with no native fault. Still open: several Settings round-trips, OSD/Media mute enable-disable and a default-output device switch on the installed build with no `native_faults.log` fault.
- [~] **Worker processes outlived a crashed UI process (fixed, physical check open).** `daemon=True` reaps workers only on a normal exit; after a native crash or forced termination they polled their request queue every 100 ms forever (19 orphans accumulated from crashing test runs). Workers now exit when `multiprocessing.parent_process()` is gone (`tests/test_worker_parent_death.py`). Physical: in the installed build, End task the main SRPSS process in Task Manager during a run; its worker processes (further instances of the same executable) must disappear within ~1 s.
- [ ] **Cross-file test abort (pre-existing at `2ba9e15d`).** `pytest tests/test_thread_manager.py::TestOverlayTimerIntegration::test_overlay_timer_uses_thread_manager_when_available tests/test_settings_dialog.py` aborts natively ("Fatal Python error: Aborted", no Qt message) inside `dialog.exec()` of `test_real_settings_dialog_delete_on_close_is_observed_before_modal_exec`. Each file passes alone (per-file isolation gate unaffected). Cause not yet traced: something the overlay-timer test leaves behind fires in the modal event loop.
- Evidence runs: 2026-09-22 22:53–22:59 — no native fault; the replacement-construction watchdog armed 13× and never fired. 2026-09-23 D1 soak 09:07–10:40 — no native fault, no QML message, watchdog armed 6× and never fired; one `viz_geometry_mismatches` increment at 10:38:32, which is the fail-closed stale-presentation guard working, not a defect.

## Handoff and regression rules

When an accepted behavior changes, select only the relevant targeted tests and physical observations; do not re-accept unrelated OSD, Media or widget systems. Keep full superseding GODZIPs with the canonical three `.godzip/` files, manifest-backed replace/delete instructions and no temporary scripts or compiled artifacts. Test commands belong in chat, not an added documentation file.
