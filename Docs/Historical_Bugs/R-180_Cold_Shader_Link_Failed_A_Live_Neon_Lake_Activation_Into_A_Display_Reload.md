# R-180 | A cold driver link of Neon Lake's basin program held the GUI thread past the 6 s activation deadline, which reloaded every display for a target that was alive

**Status:** the reload fixed 8 Nov 2026; the freeze itself remains (see "Left open"). The activation deadline now tells
a slow-but-alive target from a silent one by the render thread's preparation progress for the committed target
(`QuickVisualizerRenderHost.preparation_progress`, read through the item), extending at most
`_SLOW_TARGET_DEADLINE_EXTENSIONS` (4) times; the prepared reveal's 1.5 s bound now runs from the last completed
preparation unit. Regression bars in `tests/test_visualizer_prepared_reveal.py`:
`test_a_slow_but_alive_target_extends_the_activation_deadline_instead_of_reloading` (before the fix:
`['deadline:waiting_target']`, the reload), `test_slow_target_extensions_are_bounded`,
`test_an_uncommitted_worker_target_is_never_counted_alive`,
`test_a_long_preparation_unit_does_not_reveal_the_target_into_its_remaining_compiles` (before: `fading_in`),
`test_each_preparation_unit_and_the_first_draw_are_counted_for_their_activation`. Found in the operator's second
frozen check (`Docs/Future_Work/Native_Core_P2_Engine_Design.md`, step 6). Not specific to the engine worker: the
in-process path failed the same way.

## Symptom

The GitHub-built diagnostic saver (`098b3f0e`, `--viz-engine-worker`, two displays): at 19:46:14 a double-click switch
extruded_spectrum -> Neon Lake committed on the worker. Both displays then froze for about 7 s (`Large gap for
GlobalClockTicker: 7621.46ms`, the event loop's `late_max_ms=6887.70`, `PERF_HUD screen=1 dt_max_ms=6946.31`). At
19:46:21 `[MODE_ACTIVATION_FAIL] reason=deadline:waiting_target` forced a full CUSTOM display reload
(`kind=visualizer_activation_failed`); after it Neon Lake ran normally. Screen 0's `scene_fps=2.08 dt_max_ms=1000`
just before the switch is not part of it: that display has no Visualizer and renders only when something changes
(the clock's second), as it does all run; its 7348 ms frame gap at 19:46:22 is the same GUI freeze.

## Cause

1. **The stall's owner is one driver call.** Neon Lake's first preparation unit compiles and links its basin program
   (vertex 21 KB + fragment 116 KB of GLSL; the fragment inlines the sky radiance up to six times). With the driver's
   shader cache cold, `glLinkProgram` alone takes 5.1-6.4 s on an RTX 4090 (driver 617.42; warm: 39 ms for the whole
   unit). NVIDIA keeps its GL cache per executable (`%LOCALAPPDATA%\NVIDIA\GLCache\...\<per-app>.bin/.toc`, read
   only: a separate pair was last written during the frozen run, beside `python.exe`'s), and a onefile build extracts
   to a new folder per build, so the first run of every new build is cold; so is every edited shader from source.
2. **The GUI thread waits for it.** The link runs on the render thread inside the frame (`prepare_step`, one unit per
   spaced hidden frame), and Qt's threaded render loop holds the GUI thread in its next `polishAndSync` until that
   frame ends. Every display stops, timers included.
3. **The deadline cannot tell slow from silent.** `_ACTIVATION_TRANSACTION_DEADLINE_MS` (6 s) is a GUI single-shot
   armed at the request. It was overdue when the link returned and ran before the queued publication that would have
   moved the target on, so the owner saw `waiting_target` and signalled the failure: one fenced reconstruction, a full
   display reload, for a target whose render thread had just finished its longest unit.
4. **The prepared reveal had the same blind spot.** Its 1.5 s bound ran from the commit only, so after any long unit
   the target was revealed at once and its remaining programs (sky 0.4 s cold, skyline 0.1 s) compiled on visible
   frames of the fade-in.

## Reproduction from source

A measurement-only nonce comment appended to every shader source in `gl_resources._link` (never committed) makes
the driver's cache miss in a source run. With it, `tools/visualizer_live_check.py --mode extruded_spectrum
--mode-switch 20` (invisible, recorded music) reproduced the frozen run exactly: basin link 6089 ms, `deadline:
waiting_target`, CUSTOM reload, clock gap 7056 ms with `--app-arg=--viz-engine-worker`; basin 6396 ms, the same
failure and reload in process (clock gap 7252 ms). The offline probe (`TransitionCapture` context, the frozen Neon
Lake settings) split the cost: vertex compile 47 ms, fragment compile 18 ms, link 5120 ms.

## Fix

- The render host counts the preparation units it completes per (mode, activation) and the first draw of an
  activation (`_note_preparation`, only on those edges: steady frames do nothing new), exposed as
  `preparation_progress` and read on the GUI side through `VisualizerItem.renderer_preparation_progress`.
- `_on_transition_deadline`, in `waiting_target` or `fading_in`, re-arms the same request's deadline when the
  committed target's count advanced since the previous deadline (`_slow_target_alive`), at most 4 times, and logs
  `Activation slow but alive`. A target the engine worker has not committed yet (`_worker_commit` pending) never
  counts. With no progress in a whole window the failure and reconstruction are unchanged. The outgoing mode has
  already faded out by then; the target stays at fade 0 until it is ready and then fades in.
- `_target_renderer_preparing` measures its 1.5 s from the later of the commit and the last progress it saw.

After the fix, the same cold runs: the Neon Lake switch completed in 8.5 s on the worker and 8.0 s in process with one
`slow but alive` extension and no reload; Extruded Bubble and Waveform Ribbon (cold units 0.35-0.54 s and ~1.0 s)
completed in 4.5 / 4.2 s (worker) and 4.5 / 3.9 s (in process). Warm: 1.55 / 1.85 / 1.77 s (worker) and 1.56 / 1.94 /
1.78 s (in process), no extension.

## Left open

The GUI freeze of a cold link (about 6 s for Neon Lake, once per build per machine) is still there: compiling on a
driver thread or a shared context is excluded by the warm-up rules, and a dynamic-count loop for the glass taps did
not shorten the link (5.7 s; removing the four extra taps outright: 3.4 s). Current_Plan carries the follow-up (an
app-owned program binary cache keyed by source and driver, or a smaller basin program).

## Why it hid

- Every from-source run uses `python.exe`, whose NVIDIA cache is warm from thousands of earlier runs; the "cold"
  139 ms once recorded for Shockwave Grid's first frame was nowhere near a cold link. Only a new executable path (a
  frozen build) or an edited shader shows the real link.
- The deadline's tests modelled silence (a target that never publishes), never a GUI thread held past the deadline by
  the target's own progress.
- The reload recovers by itself and the next activation is warm, so the symptom reads as a one-off glitch.

## Lessons

1. A GUI-thread deadline over render-thread work must read the render thread's progress before failing: a stalled
   event loop makes every single-shot overdue at once.
2. Measure first use with the driver's cache defeated (a nonce in the source), not "the first run today".
3. A freeze while a target is hidden is bad; turning it into a full display reload is worse. Fade, never vanish.
