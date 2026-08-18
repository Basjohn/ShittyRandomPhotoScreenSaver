# Current Plan

Last updated: 2026-08-18
Branch: `main`
Current source anchor: `099feb53` (P2-R1/R2/R3 repair landed)
Architecture epoch: **OpenGL QRhi, one accelerated presentation surface per physical display**

This file owns unfinished active work and execution order. Current source and installed evidence
override old completion claims. Phase reports and Historical_Bugs remain evidence, not current owner
maps. `Future_Cleanup.md` is deferred debt only and must not absorb active correctness work.

`versioning.py` remains user-owned unless a version change is explicitly requested.

---

## 1. Binding Architecture

### One physical presentation surface per display

Each display has one accelerated `GLCompositorWidget` / `ExternalOpenGLRhiWidget` using Qt's
OpenGL QRhi backend. SRPSS borrows Qt's QRhi/OpenGL context; it does not own the top-level context,
`swapBuffers()`, or context destruction.

The Spotify visualizer is **not** a second surface.

`SpotifyBarsGLOverlay` remains a plain never-presented QWidget used for logical visualizer state,
geometry/CUSTOM anchoring, shader/uniform state and visualizer GL-resource ownership where
applicable. Actual visualizer/card pixels are drawn by
`rendering/gl_compositor_pkg/visualizer_layer.py::CompositorVisualizerLayer` inside the display
compositor.

Do not reintroduce a QOpenGLWidget/QRhiWidget visualizer surface, CPU/QPainter substitute
visualizer, or `hw_accel=off` compatibility renderer.

### Logical cadence and physical presentation remain independent

The visualizer owns:
- audio/source sampling;
- logical tick/simulation;
- dt/events/transients;
- mode smoothing and state evolution;
- immutable/latest render-state publication.

The display compositor owns physical presentation opportunity only.

No producer waits for paint. No paint acknowledgement, pending-until-paint gate, source/display
divisor, catch-up replay, second visualizer clock or paint-local visualizer simulation.

A queued-GUI-dispatch guard may coalesce duplicate Python callbacks only until the queued callback
actually calls `QWidget.update()`. Qt may then coalesce paint delivery itself.

### Feel / fidelity contract

The visualizer lock protects user-visible behaviour, not historical implementation accidents.

Required feel:
- reaction latency should be as low as practical;
- authored reactions should almost never be missed;
- smoothing, when enabled, should look smooth rather than stepped;
- mode/preset/generation changes must not poison later state;
- Bubble/Spectrum/Sine/Oscilloscope/DevCurve retain their authored personality and fidelity.

Efficiency work should remove waste, churn, duplicate work, copies, callbacks, synchronization and
redundant rendering. Do not buy efficiency by lowering source cadence, logical cadence, target
refresh, visual fidelity or responsiveness.

Transitions are simpler: preserve authored fidelity while avoiding visible judder, stutter, stalls
or terminal-frame glitches.

---

## 2. Retained Architecture Results

The QRhi main-compositor migration remains accepted. The old no-visualizer severe transition class
collapsed from roughly 28 `>50 ms` gaps to zero in the accepted 60-Hz QRhi control.

The sibling-QRhi visualizer experiment remains rejected. A second independently dirtied
texture-backed surface was harmful even when sharing the top-level QRhi.

The single-surface visualizer architecture remains retained. Before the latest closure work it
improved the dual 165-Hz path from the historical visualizer-on ~141-143 FPS class to roughly
153.3-153.7 FPS while the 60-Hz display remained ~59.3-59.4 FPS.

The card-texture coordinate/lifecycle repair remains retained. Installed evidence after that repair
returned tracked GL/card resources to zero at exit.

Do not reopen these architecture decisions merely because the newest functional regression prevents
performance acceptance.

---

## 3. THE INVALID INSTALLED RUN — BOTH ROOT CAUSES NOW REPAIRED

Both proven defects below have been corrected in source with production-shaped bars
and negative controls. This section is retained as the causal record; the run itself
remains unusable for FPS, latency, usage or CUSTOM acceptance.

The installed run against current `090bbe4a...` cannot be used for FPS, latency, usage or CUSTOM
acceptance because the live audio path is broken.

Operator-visible result:
- startup Bubble card appears and idles;
- the one-frame pre-fade flash is fixed;
- when music starts, the visualizer never becomes live/reactive;
- context-menu mode switching leaves the visualizer dead;
- Settings can force another mode/reinit, but the visualizer card then disappears for the rest of
  that runtime;
- returning to Bubble does not recover the runtime;
- CUSTOM/Edit was deliberately not tested because Save would have persisted a bad visualizer state;
- idle Bubble appeared somewhat juddery, but that is not accepted evidence while the audio path is
  throwing continuously.

### 3.1 PROVEN ROOT CAUSE A — live audio callback throws before publishing every frame

The log begins music playback at approximately 21:52:53 and immediately records:

```text
widgets.spotify_visualizer.audio_worker
[SPOTIFY_VIS] Exception suppressed: name 'time' is not defined
```

This repeats continuously, with duplicate-suppression counts representing **tens of thousands of
callback failures** during the short run.

Exact current source explains it:

```python
self._buffer.publish(_AudioFrame(
    samples=mono.copy(),
    activation_id=getattr(self, "_activation_id", None),
    capture_ts=time.time(),
))
```

but `widgets/spotify_visualizer/audio_worker.py` does not import `time`.

Therefore:
- the callback reaches `capture_ts=time.time()`;
- raises `NameError`;
- the broad callback exception handler suppresses it;
- no `_AudioFrame` is published;
- BeatEngine receives no real live source frames;
- the newest-pending analysis work cannot operate;
- the visualizer can continue idle/logical animation while never reacting to music.

This directly explains the primary "never goes live" failure. Do not add more renderer/readiness
instrumentation before fixing this.

**REPAIRED (P2-R1).** `time` is imported; `capture_ts` semantics and clock domain are
unchanged. A capture callback that fails while the worker claims to be running is now
an ERROR on first failure and sampled after that, never per-frame, and a successful
publication re-arms the loud report. No retry or restart loop was added.
`tests/test_p2_audio_capture_callback.py` drives the callback the worker actually
registers, through a fake backend implementing the real `AudioCaptureBackend`
contract; removing the import again fails 15 of its 16 bars.

The callback failure itself also creates massive exception/logging churn, so the current tick/FPS/CPU
behaviour is contaminated and must not be optimized from this run.

### 3.2 PROVEN ROOT CAUSE B — "one activation, one generation" still does not hold

The same installed run proves the P2-ACTIVATION-FINAL claim is incomplete.

Bubble -> Spectrum:

```text
generation=1 activation=1   before switch

mode_switch:activation_payload
generation=2 activation=2

smoothing_reset
generation=3 activation=3
```

The mode teardown then reaches its 1.51-second timeout fallback waiting for target generation 3.

The same double-advance pattern repeats on later forced mode/runtime changes.

Current source explains why:

1. `mode_transition.activate_visualization_mode()` assigns:

```python
widget._vis_mode = mode
```

**before** calling `_apply_full_runtime_config_for_mode()`.

2. `activation_runtime.apply_resolved_activation_payload()` calculates:

```python
mode_changed = vm != widget._vis_mode
```

so the real cross-mode activation now looks like `mode_changed == False`.

3. The activation transaction therefore does not execute the full mode-change reset/preparation
branch under the transaction.

4. `mode_transition.prepare_engine_for_mode_reset()` later always performs:

```python
engine.cancel_pending_compute_tasks()
engine.reset_smoothing_state()
engine.reset_floor_state()
...
```

outside the already-committed activation transaction, creating the second generation.

This is not a logging ambiguity. The production mode-switch path still contains two generation
boundaries.

**REPAIRED (P2-R2).** The resolved activation payload is now the authority that commits
`_vis_mode`; `activate_visualization_mode()` assigns it only in the fallback shape where
no payload could be resolved, and owns preparation only there. Both duplicate reset
sites are gone: `activate_visualization_mode()` and `on_mode_fade_out_complete()` skip
the reset when the activation transaction already performed it, which
`activate_visualization_mode()` now reports back. The duplicate reset WORK is removed,
not a counter. A same-mode preset transition keeps its trailing reset and its
deliberately unstamped config apply.

`tests/test_p2_mode_activation_production.py` drives the real production entry points
with the real BeatEngine and counts real `reset_smoothing_state` calls. Reintroducing
the premature assignment fails 5 bars; reintroducing the duplicate trailing reset
fails 2.

### 3.3 Consequence — fresh-frame/reveal gates wait forever

After the audio callback stops publishing frames, forced Settings/mode restarts log repeated:

```text
Reveal watchdog expired while still pending
waiting_frame=True
waiting_engine=True
playing=True
```

The mode path also times out waiting for its target generation.

This is expected fallout from A + B:
- live source frames never arrive;
- fresh authoritative final-generation state never arrives;
- mode transition/reveal remains hidden or falls through timeout/fallback paths.

Do not "fix" this by weakening the normal fresh-frame contract or revealing stale old-generation
state.

**NOT WEAKENED.** The fresh-frame contract is unchanged.
`tests/test_p2_live_source_to_reveal.py` proves the gate stays closed when no source
frames arrive and when the capture callback is broken, and that a pre-replacement
frame cannot satisfy a new generation's gate.

The renderer-readiness fallback added in `090bbe4a...` is not an authorization to bypass engine/audio
freshness. It may remain a bounded loud renderer failure policy, but it must not make a broken source
path look healthy.

### 3.4 Test gap is proven

`tests/test_p2_analysis_freshness.py` directly injects `_AudioFrame(...)` into the engine buffer.
That correctly tests one-in-flight + one-latest-pending semantics, but it never executes the real
`SpotifyVisualizerAudioWorker.start()` callback that constructs `_AudioFrame(capture_ts=time.time())`.
Therefore the missing production import passed the suite.

Likewise, mode-activation tests did not reproduce the full production sequence strongly enough to
catch the real:

```text
activate_visualization_mode
-> apply activation payload
-> fade-out-complete preparation
-> real BeatEngine generation changes
```

The suite passing is not acceptance when the installed production path is dead.

**CLOSED.** Three production-shaped files now cover the seams that were bypassed: the
registered capture callback, the real mode-transition entry points, and the end-to-end
chain from capture callback to reveal gate. Each defect was reintroduced and proven to
fail its new bar.

---

## 4. P2 REGRESSION REPAIR — LANDED, AWAITING ONE INSTALLED ACCEPTANCE

```text
P2-R1  real capture callback repaired; failure is loud then bounded
P2-R2  one real cross-mode activation is one real engine generation
P2-R3  end-to-end bar: capture callback -> engine -> final generation -> reveal
```

Established by the repair, and only this:

- the real registered capture callback publishes an `_AudioFrame` with a non-zero
  `capture_ts` and preserved activation identity, with no callback exception;
- a broken capture callback is now visible: ERROR on first failure, sampled after,
  never per-frame, re-armed by recovery, and it does not restart the stream;
- one cross-mode switch advances the real BeatEngine exactly once on both the
  direct/Settings path and the crossfade path, applies the target bar count, and binds
  fresh-frame gating and mode teardown to that single final generation;
- with a live source, teardown reaches `fading_in` well inside the 1.51-second fallback
  the installed run hit;
- a same-mode preset transition still performs its own reset and config apply;
- standalone `reconfigure_bar_count()` / `reset_smoothing_state()` keep their normal
  generation semantics outside a transaction.

Not established, and still open to the acceptance run: FPS, latency, usage, fade
quality, idle smoothness, start/stop hitching, CUSTOM behaviour.

### P2-R4 — retain the confirmed flash correction; do not expand fade work yet

The operator reports the pre-fade one-frame flash is fixed.

Retain:
- card QWidget does not self-paint when a compositor visualizer layer exists;
- compositor remains visual owner;
- one scene fade authority.

The rest of fade quality, idle smoothness and start/stop hitching are **not accepted or
rejected** from the broken-audio run. Reassess them only in the acceptance run below.

### P2-R5 — CUSTOM/Edit remains landed but unvalidated

Do not alter CUSTOM merely because it was not tested. The repaired production-shaped
tests exposed no CUSTOM issue.

The compositor-owned edit snapshot architecture remains the intended contract:
- one snapshot at edit entry;
- no live GL resize per mouse movement;
- Save/Cancel use authoritative CUSTOM geometry;
- cross-display transfer changes compositor owner cleanly;
- generation-owned GL resources remain strict.

Installed validation happens in the acceptance run now that the visualizer runtime is
repaired.

## 5. TESTING STANDARD FOR THIS REPAIR

The main lesson from this round is that helper/unit bars cannot claim closure when they bypass the
actual production boundary that failed.

For P2-R1/R2/R3:
- prefer small real production objects with fake external boundaries;
- callback tests must call the callback production registers;
- activation tests must drive the production mode-transition sequence;
- use the real BeatEngine for generation assertions;
- verify a state reaches the next owner, not merely that a helper returns the intended value.

Reintroduce each repaired defect before closure and prove its new bar fails:
- remove `time` availability -> capture/publication bar fails;
- restore premature `_vis_mode` assignment or second reset -> one-generation bar fails.

Do not add more diagnostics unless a repair still fails the one installed acceptance after these
known defects are removed.

---

## 6. ONE INSTALLED ACCEPTANCE — NOW DUE

Do not request intermediary operator runs.

After the repair is pushed and focused/combined tests are green, request one:

```text
python main.py --perf --gpu-timing
```

### Functional gate first

Before interpreting performance counters, the same run must prove:

1. Bubble appears at startup without the old pre-fade flash.
2. Start music: Bubble becomes clearly live/reactive.
3. Switch Bubble -> Spectrum from context menu: Spectrum appears and reacts.
4. Switch another mode through Settings/reinit: correct card + mode reappears and reacts.
5. Return to Bubble: no dead state or poisoning.
6. Pause/stop and resume once: no dead scene.
7. No repeated audio callback exception.
8. No mode teardown timeout fallback.
9. No duplicate generation advance per cross-mode activation.

If any functional item fails, stop interpreting FPS/usage.

### Then visual/fidelity gate

- reaction feels immediate rather than materially behind the music;
- smoothing looks smooth when enabled;
- authored reactions are not routinely missed;
- no mode/preset poisoning;
- no visible startup/mode-switch/stop-resume hitch beyond unavoidable bounded work;
- Bubble/Spectrum/Sine/Oscilloscope/DevCurve retain authored fidelity.

### Then CUSTOM gate

- enter edit;
- move/resize visualizer;
- Cancel;
- enter again;
- move/resize;
- Save;
- cross-display transfer if convenient.

No whole-display snapshot, missing card, stale old-generation visualizer or geometry authority split.

### Then delivery/performance gate

Compare against the last valid pre-regression dual result:

```text
165-Hz: ~153.3-153.7 FPS, ~93.2-93.4% accepted
60-Hz:  ~59.3-59.4 FPS, ~98.9% accepted
```

The paint-acknowledged admission gate has been removed, so the 165-Hz path should materially exceed
the old ~153-154 class if that mechanism was the remaining ceiling.

Do not require mathematically perfect 165.0 FPS through every heavy transition. Low-160s with clean
tails may be a healthy practical result; exact interpretation depends on utilization and gap
distribution.

### Usage / efficiency gate

Post-migration usage must be checked again in this valid run.

Same-machine CPU/GPU utilization is important as the available proxy for ordinary weaker hardware.

Desired result:
- performance improvement comes from reduced waste/churn, not brute-force work;
- GPU utilization remains low for the rendered workload;
- CPU/main-thread utilization does not regress materially;
- no sustained callback/task/logging churn;
- no new monotonic RAM/VRAM growth;
- tracked GL resources return to baseline at teardown.

Do not add "energy efficiency" throttles, refresh caps or fidelity/cadence reductions. A discrete GPU
being awake is not itself a defect; high sustained utilization/heat-producing unnecessary work is.

If 165 Hz remains ~153-154 **after** the functional repair and paint-admission removal are proven
active, only then perform one bounded current-architecture scheduler/Qt/DWM attribution pass.

---

## 7. P5 — MONITOR TOPOLOGY / PHYSICAL SLEEP-WAKE HARDENING — MANDATORY NEXT

P5 remains mandatory even if P2 performance becomes excellent.

Observed failure class:
- both physical displays off while saver remains active;
- long idle;
- wake can leave one SRPSS display frozen and the other black;
- clock/input/Escape/context menu can become dead;
- Ctrl+Alt+Delete can be required to disturb Windows enough to recover.

### P5-A — one topology decision authority

One engine/DisplayManager-level owner decides:
- no-op;
- local re-anchor/update;
- full runtime replacement.

Native Windows, Qt screen and per-window notifications are invalidation/report inputs, not competing
mutation owners.

### P5-B — true trailing-edge settlement + immutable snapshot

Every relevant topology event restarts the quiet-period timer. A bounded maximum settlement deadline
prevents endless postponement.

Freeze one accepted topology generation/snapshot before destructive work, including:
- screen count/order/identity;
- geometry/work area as required;
- DPR;
- configured visualizer display;
- topology generation.

A later topology event queues the next transaction; it does not mutate the frozen transaction.

### P5-C — transactional replacement/readiness

```text
Notify -> Settle -> Snapshot -> Retire -> Rebuild -> Reveal
```

- stop old-runtime topology mutation;
- invalidate old generation;
- retire once;
- strict borrowed-context/owned-resource GL cleanup;
- destruction barrier proves old ownership gone;
- construct/register complete replacement from frozen snapshot;
- replay committed CUSTOM state;
- reveal only current-generation ready displays.

Do not weaken fail-closed teardown, extend timeouts, add GL retry loops, hide/reuse old runtime or
pump nested events.

### P5-D — generic CUSTOM replay

Reapply committed display-local CUSTOM geometry generically after reconstruction. Do not hard-code
the historical Media/visualizer endpoint merely because that was the last visible breadcrumb.

Prove stale pre-rebuild widget geometry cannot overwrite committed CUSTOM state.

### P5-E — sticky configured visualizer monitor

Temporary asleep/rebuilding/non-participating display is not absence.

If configured monitor remains in settled topology:
- keep ownership sticky;
- park/hide/defer presentation until ready;
- do not eagerly fallback.

Only genuine settled absence may arm one coarse generation-owned ~60-second confirmation. If still
absent at that single check, fallback may occur once.

Return-home is event-driven from later topology/readiness, not polling.

### P5-F — recovery-specific desktop capture boundary

Keep `screen.grabWindow(0)` for normal stable desktop -> screensaver cold-start anti-flash.

Do not make synchronous waking-desktop capture a prerequisite of topology recovery. Reuse retained
SRPSS image/replay state or wait for the first real frame.

### P5-G — physical acceptance

Exercise:
- both displays off -> long idle -> wake;
- simultaneous wake;
- D0 then D1;
- D1 then D0;
- temporary one-display topology before sibling stabilizes;
- genuine configured-monitor absence > grace;
- return before grace;
- return after legitimate fallback;
- overnight-equivalent idle.

Pass:
- both displays recover;
- normal input recovers;
- no Ctrl+Alt+Delete required;
- no eager visualizer migration;
- no stale old-generation owners/resources;
- no monitor polling architecture.

---

## 8. AFTER P5

Only after P5:
- long-run RAM/private-commit/VRAM slopes;
- resource/cache efficiency with quality unchanged;
- cleanup/diagnostic retirement from `Future_Cleanup.md`;
- harness/test flake cleanup;
- obsolete non-accelerated toggle/path retirement;
- unrelated provider/media work in separate causal slices.

`Future_Cleanup.md` does not need modification for the current regression round: the newly proven
audio callback and activation faults are active P2 correctness work, not deferred debt.
