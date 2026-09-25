# R-96 — Double Wake Froze The Replacement Runtime

Date: 2026-09-25  
Status: FIXED IN CODE / AWAITING VALIDATION — Windows dual-monitor built check (`Current_Plan.md`)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [x] AWAITING VALIDATION
- [ ] SOLVED

## Observed Failure

After an overnight single-display run (`SRPSS_Diagnostic.exe`, started 02:17), the operator switched the second
display on at 07:53. The runtime rebuilt three times in 82 s: generation 1 at 07:53:39 (screen added, 1 → 2),
generation 2 at 07:54:56 (Quick binding loss, 2 → 1) and generation 3 at 07:55:01 (screen added again). Generations 1
and 2 revealed. Generation 3 logged its startup first-image retry at 07:55:03 and then nothing at all on any thread:
both screens stayed blank, and the process died when the operator interacted with it. No native fault was
recorded and no stack dump was written.

## Root Cause

Several compounding defects were on the replacement path. No single delay explains the freeze, and none of them
needed a longer timeout.

1. **Two first images per replacement.** A monitor-topology rebuild replays the current image into the fresh
   generation, but the replay never claimed the image-change owner. `start()` also scheduled the 180 ms startup
   first-image retry, which saw no loading work, advanced the queue twice and admitted a second foreground batch.
   Every rebuild in the evidence logged `Startup first-image retry succeeded` beside the replay, so two
   presentation batches were in flight while the first frames of a new generation were still pending.
2. **No stack dump where it wedged.** The Settings/CUSTOM replacement armed the all-thread stack dump
   (`hang_watchdog`) only around construction and disarmed it as soon as construction returned. The
   monitor-topology path had its own copy of replacement construction that never armed it. The process froze
   after construction and before reveal, so no stack was captured.
3. **A synchronous quit deadlocks against a render thread running Python.** `QCoreApplication.quit()` sends
   `QEvent::Quit` synchronously, and `QGuiApplication` closes every window inside that call. PySide 6.9.1 holds the
   GIL for the whole call, while the threaded render loop runs Python (`updatePaintNode`, the retained background
   node) and needs the GIL to finish the stop that the close waits for. Every Python thread wedges. The tray exit,
   the replacement failure paths and the destruction-barrier failure path all called `quit()` directly. This was
   reproduced 3/3 with the production background node on Linux/Xvfb threaded GL
   (`tests/test_quit_request_render_thread_gil.py`).
4. **A healthy display was held blank by its sibling.** The coordinated reveal waited without bound for every
   selected display. If one display's Quick readiness failed, or it never produced a first frame (the monitor still
   waking), the widgets on the healthy display stayed at opacity 0 indefinitely.
5. **Work-area edges rebuilt everything.** The monitor signature included `availableGeometry`, so a taskbar or
   app-bar settling after wake counted as a topology change and rebuilt the whole generation. Each window already
   re-applies its bound screen geometry on that edge.

The exact frame that wedged at 07:55:03 is not recoverable from this evidence (defect 2). Of the mechanisms found,
only defect 3 wedges every thread at once, which is the evidence's signature. It is reachable from the failure
paths that a wedged replacement triggers, and from the interaction that followed.

## Why It Was Hard To Find

- Every rebuild still "worked" until one did not: the second batch was hidden behind the first, and the retry's
  success line read like a recovery.
- The hang window closed exactly where the freeze started.
- The GIL deadlock needs a render thread that is executing Python at the moment of the close, so a synchronous
  quit usually looks harmless.
- Mocked lifecycle tests could not show any of these. The regression bars drive the real engine admission code,
  the real Qt timer and animation loop, and a real threaded-GL window.

## Fix

- The monitor replay claims the shared image-change owner (`_admit_monitor_replay_image`), and
  `start(show_first_image=False)` schedules no parallel retry. A rejected replay hands the first image to the
  bounded retry, loudly (`[DISPLAY][FALLBACK]`).
- All replacements share `engine_handlers._construct_and_start_replacement_runtime`. Its hang window
  (`replacement_to_reveal:<event>:generation=<n>`, 20 s) stays armed until the coordinated reveal completes.
  It is closed by that reveal, by generation retirement, by construction failure, when the queue has no image, or
  when the retry is exhausted. A label-checked disarm stops a stale edge from closing a newer window.
- `engine.runtime_destruction.request_application_quit(reason)` queues the native `quit()` slot. Every product quit
  now uses it, and tray exit relies on the terminal stop, which quits after Quick retirement drains.
- Failed readiness stops gating the reveal and first-frame signals immediately. A stalled sibling is bounded by one
  generation-fenced 6 s one-shot (`[STARTUP_REVEAL][FALLBACK]`). The shared 1,800 ms fade then drives only the
  displays that were ready when it started. A stalled display keeps its widgets at opacity 0 until its own first
  wallpaper and Quick readiness complete, then gets its own one-shot reveal (operator follow-up, 2026-09-25).
- The monitor signature no longer includes the work area.

## Investigated And Rejected

- **Adding a monitor without rebuilding the healthy display's runtime.** Screen indices shift on add (the existing
  display moved from index 0 to 1 in the evidence), and routing, Visualizer ownership and CUSTOM layout are
  generation-wide. An incremental add would need a second topology authority. The rebuild stays whole-generation.
  Its cost is bounded by the fixes above, not by skipping it.
- **Longer debounce, delays or retries.** None of the mechanisms is timing-dependent in a way a delay would remove.

## Side Findings Fixed In The Same Investigation

- `core.mc.is_mc_build()` constructed a full `SettingsManager` (migrations, repair, synchronous durability flush)
  for every per-window, menu and interaction query. That was 21 managers on MainThread for one cold start plus one
  rebuild. It now reads the side-effect-free entry-point profile.

## Regression Coverage

- `tests/test_monitor_replay_admission.py`: one admission per replacement; a rejected replay hands off to the
  retry; the replay is refused while another batch owns the generation.
- `tests/test_replacement_hang_window.py`: the window stays armed until reveal; it closes on retirement and on
  failure; a stale label cannot close it; the monitor path uses the shared construction.
- `tests/test_quit_request_render_thread_gil.py`: a subprocess with a real threaded-GL window and the production
  node. The queued quit exits; `MODE=synchronous` reproduces the wedge.
- `tests/test_startup_reveal_stalled_display.py`: failed and stalled siblings, plus the two-monitor late-recovery
  opacity bar at the real 1,800 ms.
- `tests/test_qtquick_monitor_wake_reconcile.py::test_work_area_only_change_does_not_rebuild_healthy_displays`
- `tests/test_mc_entrypoint_contract.py::test_mc_identity_is_resolved_without_constructing_settings`
- `tools/linux_xvfb_hotplug_churn.py` drives the unmodified app through real Qt screen add/remove on Xvfb. It is
  Linux development evidence, not Windows evidence.

## Guardrail

Never make Python on the GUI thread wait for a Quick render thread (`Docs/Guardrails.md` § Lifecycle). A replacement
generation has one first-image admission owner, and its hang window covers construction through reveal
(`Docs/Contracts.md` § Runtime replacement and monitor topology).
