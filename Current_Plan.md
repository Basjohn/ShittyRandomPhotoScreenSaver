# Current Plan — P2 Recovery After Second Installed Acceptance Failure

Last updated: 2026-08-19  
Branch: `main`  
Installed source anchor: `ccb63542348fec5993a688142bc2e364f8149f6a`  
Accepted rollback/fidelity baseline: **4.7.2 / `42033c84eabbdf25ccd34bb0e83f9e553f2f8f11`**  
Architecture epoch: **single-surface OpenGL QRhi compositor + compositor-owned visualizer presentation + dedicated mode-general logical runtime**

This file owns unfinished P2 work. Exact installed behavior and current source override commit messages, test counts, and claims that a slice is “done.”

---

# 0. Executive truth

## P2 is still open

Second installed acceptance:

### Fixed and retained
- valid generation `0` stays `0`;
- paused Spectrum idle bars are visibly present;
- `VisualizerLogicalRuntime` remains the sole mode-general logical clock;
- logical cadence is back in the ~89.9 Hz class with very low skipped-deadline rate;
- single physical compositor surface per display;
- visualizer remains a compositor layer;
- no playback debounce;
- no cold visualizer/card/GL recreation on Pause/Play.

### Still failing
1. Pause/Play visibly hitches.
2. General hitching remains.
3. 165 Hz transition delivery is still materially below the accepted class.
4. 60 Hz presentation still contains long gaps.
5. Bubble average cadence is healthy but BTF long-tail/perceptual acceptance is not.
6. Slice H reduced dirty raster area but did not remove frame-count-scale real `MediaWidget.paintEvent` work.

Do not call P2 complete.

## Explicitly out of scope for the next work

Do not:
- replace or redesign `AdaptiveTimerStrategy`;
- restore vsync;
- run a QRhi/native-loop architecture experiment;
- redesign worker-to-GUI visualizer handoff;
- tune Bubble;
- add audio/source smoothing;
- reduce logical cadence;
- reintroduce playback debounce;
- optimize individual transitions;
- begin another generic probe/telemetry campaign.

Two source-owned defects are already strong enough to correct deterministically.

---

# 1. Second-run facts

## Generation zero — GREEN

Observed:

```text
[SPOTIFY_VIS][LOGICAL] Runtime started (generation=0 interval_ms=11.11)
```

Retain permanent generation-zero fences/tests.

## Spectrum idle — GREEN

Observed real renderer snapshot:

```text
count=35
min=0.0738
max=0.4192
```

Operator confirms visible resting bars. Retain the real-renderer gate and `presentation_ready != reactive_source_ready`.

## Dedicated logical runtime average — GREEN

Observed:

```text
generation=0 steps=12488 skipped_deadlines=11 slow_steps=2 failures=0
generation=1 steps=5065  skipped_deadlines=5  slow_steps=2 failures=0
```

The old ~64 Hz / ~29% skipped-deadline collapse remains fixed.

The worker stays.

## BTF tails — RED

The installed run still contains >33 ms logical/presentation holes and visible hitching. Healthy averages do not override BTF perception.

---

# 2. Pause/Play: strongest bounded edge defect

The operator's distinction matters:

- fade-in start does not hitch;
- Pause and Play do;
- historically the Pause/Play edge was clean.

Current `MediaWidget.play_pause()` calls the media controller synchronously. The Windows GSMTC controller sends WinRT work to IO, but `_run_coroutine()` waits on a `threading.Event` for completion before returning to its caller.

Therefore WinRT may run off-thread while the GUI caller is still blocked waiting for it.

This is a much better edge-specific match than visualizer fade mechanics:
- Pause executes the transport command;
- Play executes it;
- fade-in does not.

Historical qualification:
`core/media/media_controller.py` is byte-identical at baseline `42033c84...` and current source. This is a real latency-sensitive GUI ownership defect and the first edge target, but it must not be falsely described as the sole cause of the whole current-vs-baseline regression.

---

# 3. Slice K — non-blocking media transport command

Goal: **user transport ingress returns control to the GUI immediately.**

Required:
- current command deduplication remains;
- optimistic playback state remains immediate;
- actual GSMTC command executes on the correct IO owner;
- GUI does not wait for WinRT completion;
- no nested IO submit/wait deadlock;
- normal refresh later reconciles optimistic state with reality;
- failures remain soft and bounded;
- Next/Previous use the same ownership rule if they share the same synchronous controller path.

Prefer one explicit non-blocking command owner/API over detached ad-hoc threads.

## Slice K automated gate

Use a deliberately delayed fake/controlled transport backend (for example 250–500 ms).

Prove:
- Pause/Play command ingress returns before backend completion;
- GUI/event-loop work queued immediately afterward executes before backend completion;
- optimistic state/feedback is available immediately;
- exactly one backend action runs;
- eventual completion/reconciliation still occurs.

The current synchronous-wait behavior must fail the negative control.

Do not use an installed probe to prove this.

One semantic commit.

---

# 4. Slice H was only partial

Slice H changed repeated feedback repaint requests from full-card `update()` to `update(controls_rect)`. This narrows raster damage but does not by itself remove Python paint work.

Installed feedback still reports frame-count-scale paint requests:

```text
40 50 62 36 46 55 44 23 45 75 44 36 55 48
```

During rapid Pause/Play, real `media.paint` telemetry repeatedly hits 50-call windows:

```text
19:07:50 calls=50 avg_ms=3.87
19:07:51 calls=50 avg_ms=2.62
19:07:52 calls=50 avg_ms=1.87
19:07:54 calls=50 avg_ms=2.85
19:07:56 calls=50 avg_ms=3.45
19:07:59 calls=50 avg_ms=2.46
```

Card area remains:

```text
170400 px
```

Current `MediaWidget.paintEvent()` still enters the normal paint dispatcher. Current `widgets/media/painting.py::paint_contents()` does not select a feedback-only path from `event.region()`; the ordinary base-card/header/metadata/artwork/logo/progress/controls sequence still executes.

So Slice H reduced clipped drawing area but did not prove removal of repeated expensive parent paint logic.

Also: feedback event metadata tracks `full_card_paint_requests`, but the structured `[PERF][MEDIA_FEEDBACK]` logger does not emit that field. Do not claim the installed run verified `full_card_paint_requests ~= 1`.

---

# 5. Slice L — real lightweight feedback paint ownership

Goal: **preserve the animated feedback visual while removing frame-count-scale full parent paint-pipeline work.**

Allowed shapes:
- lightweight child/overlay owns animated feedback pixels; or
- a safely distinguishable feedback-only parent paint path executes only the minimum cached background/control-row work.

A mere `update(rect)` with the ordinary parent paint dispatcher is insufficient.

Do not:
- lower feedback FPS to pass;
- remove feedback;
- make ordinary feedback static;
- re-run artwork/header/metadata expensive paint logic every feedback frame.

## Slice L automated gate

Use a real `MediaWidget` and real Qt event processing.

For one ordinary animated event:
- feedback changes across multiple frames;
- parent `MediaWidget.paintEvent` / full parent-pipeline executions attributable to feedback remain a small constant (target <= 2 unless exact source requires another explicitly justified constant);
- expensive artwork/header/metadata subpainters do not run once per feedback frame;
- the lightweight feedback path may repaint at authored cadence;
- forcing the historical parent repaint path fails the bound.

Do not monkeypatch the repaint calls into no-ops and count method names. Exercise the real paint ownership seam.

One semantic commit.

---

# 6. Shared transition evidence

## 165 Hz display still fails

Completed screen-0 Blockspin windows:

```text
140.7
144.8
140.0
138.1
136.3
136.5
141.3 FPS
```

Target:

```text
165 Hz
```

Request acceptance:

```text
90.01%
92.38%
89.42%
87.78%
90.20%
87.95%
88.50%
```

This is still materially outside the accepted low/mid-150 class.

## Current loss stage is GUI dispatch, not timer deadline precision

Representative 165 Hz delivery:
- adaptive wake lateness p95 generally ~1–2 ms;
- `paint_pending_skips=0`;
- substantial `dispatch_pending_skips`;
- dispatch-skip p95 in the tens of milliseconds;
- GUI dispatch maxima around ~90–136 ms.

Approximate chain:

```text
adaptive timer wakes
    ->
requests GUI update
    ->
previous queued GUI dispatch has not run
    ->
new deadline cannot be admitted
```

Do not alter timer precision from this run.

GPU timing remains low/sub-millisecond relative to the failures. Do not begin transition/shader tuning.

---

# 7. Pause/Play visibly collapses Bubble presentation

Before rapid toggles:

```text
19:07:40 set_state=816 update_requests=816 elapsed_ms=10000
```

During toggles:

```text
19:07:50 set_state=688 update_requests=688 elapsed_ms=10016
19:08:00 set_state=560 update_requests=560 elapsed_ms=10000
```

After toggles stop:

```text
19:08:10 set_state=831 update_requests=831 elapsed_ms=10000
```

Approximate state-handoff class:

```text
before   ~81.6/s
during   ~68.7/s -> ~56.0/s
after    ~83.1/s
```

The logical runtime remains ~89.9 Hz.

Therefore simulation can stay healthy while GUI consumption/presentation collapses.

Do not treat a good surviving-frame `state_to_paint_p95` as proof of good visible cadence; latest-wins publication can discard intermediate states.

---

# 8. Execution order

## Slice K
Non-blocking media transport command + deterministic negative-control gate.

## Slice L
Real lightweight animated feedback ownership + deterministic negative-control gate.

## Slice M
ONE installed acceptance run after K/L:

```text
.\main.py --debug --perf --gpu-timing --viz --usage --life --set --geo --fresh
```

Exercise:
1. startup both displays;
2. Bubble long enough to judge continuous motion/reactivity;
3. rapid Pause/Play toggles;
4. ordinary 165 Hz transitions;
5. all visualizer mode switches;
6. paused Spectrum idle;
7. Settings/recreate;
8. clean shutdown.

Hard fail:
- visible Pause/Play hitch;
- Bubble stepping/flicker;
- recurring unexplained >33 ms holes;
- Spectrum idle missing;
- 165 Hz transition delivery still materially below accepted class;
- lifecycle/shutdown regression.

If Slice M fails, do not start another generic probing phase. Use existing `DELIVERY_STAGE`, `FRAME_GAP_OWNER`, widget telemetry, and source diff against `42033c84...` to name one bounded owner before another production change.
