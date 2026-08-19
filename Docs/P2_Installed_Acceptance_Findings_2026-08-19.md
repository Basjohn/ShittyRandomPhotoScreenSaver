# P2 Installed Acceptance Findings — 2026-08-19

Reviewed source anchor: `80c8ed35f2f027522b00dcbe9795eb95b42076f4`  
Run logs: fresh installed run supplied after Slices A–E  
Status: **P2 acceptance failed; several landed slices remain valid**

This document records evidence from the installed run so future agents do not reconstruct the round from commit messages.

---

# 1. Actual run command

`screensaver_verbose.log` records:

```text
Command-line arguments:
['.\\main.py', '--debug', '--perf', '--gpu-timing', '--viz',
 '--usage', '--viz', '--life', '--set', '--geo', '--fresh']
```

The run DID include `--viz`.

There are no `[SPOTIFY_VIS][LATENCY]` warning lines in `screensaver_spotify_vis.log`.

Interpretation:

- visualizer diagnostics were enabled;
- the existing thresholded latency logger did not emit a warning;
- do not claim diagnostics were absent;
- do not invent an unlogged latency value.

---

# 2. Installed operator report

Operator-visible failures:

```text
Pause/Play hitch remains essentially unchanged.
Paused Spectrum card appears, but no idle bars are perceptibly visible.
Overall performance remains unimpressive.
```

These are acceptance failures.

---

# 3. Logical runtime result

Long run:

```text
17:05:47  Runtime started generation=-1 interval_ms=11.11
17:09:59  Runtime stopped
           steps=22636
           skipped_deadlines=38
           slow_steps=4
           failures=0
           joined=True
```

The logical tick metrics stay approximately 89.7–89.9 Hz over the long run.

This is a decisive improvement over the previous ~64 Hz / ~29% skipped-deadline failure.

Post-Settings run:

```text
17:10:24  new runtime
17:10:42  stopped
           generation=1
           steps=1621
           skipped_deadlines=1
           slow_steps=0
           failures=0
           joined=True
```

Conclusion:

- scheduler repair is real;
- worker ownership is production-functional;
- broad revert is not justified.

---

# 4. Remaining logical-tail alarms

Bubble logged:

```text
17:07:28 Tick dt spike_ms=49.83
17:07:43 Tick dt spike_ms=42.27
```

The long runtime counted four slow steps.

Conclusion:

- average logical cadence is repaired;
- long-tail logical service still violates the current BTF alarm contract;
- Bubble smoothness cannot be accepted from the average alone.

---

# 5. Bubble compute lane

Final long-run cadence snapshot:

```text
offered=11328
submitted_tasks=11324
publish_ratio=1.000
worker_busy_deferrals=4
result_waiting_deferrals=0
submission_failures=0
stale_results=0
```

Conclusion:

Bubble compute admission/publication is not the obvious owner of the remaining shared performance loss.

Do not compensate with Bubble-specific cadence reduction or extra smoothing.

---

# 6. Bubble state-to-paint

Representative Bubble overlay windows include:

```text
p95  9.173 ms   max 33.015 ms
p95 11.498 ms   max 32.993 ms
p95  9.002 ms   max 36.143 ms
p95  9.362 ms   max 48.887 ms
p95 11.727 ms   max 71.797 ms
p95 11.677 ms   max 61.977 ms
p95 10.820 ms   max 39.426 ms
```

Across 13 measured Bubble windows:

```text
median p95   9.737 ms
worst p95   11.727 ms
worst max   71.797 ms
```

Conclusion:

- better than catastrophic cadence collapse;
- not back in the historical healthy ~5–9 ms p95 class;
- long tails remain strong BTF warnings/failures.

---

# 7. Spectrum idle evidence

Real renderer debug:

```text
17:05:49
Shader bars snapshot: count=35, min=0.0100, max=0.0300
```

Current idle baseline source:

```text
_IDLE_BASELINE_MIN = 0.010
_IDLE_BASELINE_MAX = 0.030
```

Current Spectrum upload:

```python
buf[i] = float(bars[i]) * 0.55
```

Therefore the GL uniform bar values begin around:

```text
0.0055 .. 0.0165
```

before the shader's remaining height math.

The installed operator sees no bars.

Conclusion:

- old first-frame/source-authority blocker is fixed;
- current failure is visual magnitude / renderer contract;
- current Gate 1 is invalid as a visible-pixel oracle.

---

# 8. Why Gate 1 missed Spectrum

`tests/test_p2_gate1_spectrum_paused_visible.py` uses a `_RecordingParent(QWidget)`.

Its presentation method:

```python
def push_spotify_visualizer_frame(self, **kwargs):
    self.frames.append(dict(kwargs))
    return True
```

It does not run the real compositor or Spectrum shader.

The key bar assertion only requires non-zero float data.

Conclusion:

A test can say “visible” while never producing pixels.

Replace with actual GL/pixel output or deterministic renderer-aware pixel-height math.

---

# 9. Generation-zero defect

The live visualizer initially inherits runtime generation `0`.

Current logical runtime construction includes:

```python
generation=int(getattr(widget, "_runtime_generation", -1) or -1)
```

Valid `0` therefore becomes `-1`.

Fresh log:

```text
initial runtime   generation=-1
replacement       generation=1
```

Presentation-side code uses the same style of coercion in generation comparisons.

Conclusion:

Current generation-fencing tests do not fully protect the initial runtime.

Gate 9 must explicitly exercise generation 0.

---

# 10. Pause/Play Media feedback evidence

Current feedback architecture:

- ordinary feedback uses `AnimationManager`;
- each update calls `_request_feedback_paint()`;
- that calls `widget._safe_update()`;
- static feedback is already used during transitions specifically to avoid full-card repaint starvation.

Fresh completed Play events:

```text
paint_requests:
43, 38, 46, 66, 46, 51, 46, 42, 36, 43, 36, 41, 42, 35, 44

range: 35 .. 66
mean:  ~43.7
nominal duration: 1350 ms
```

Feedback animation telemetry observed:

```text
minimum avg_fps class    ~24.8
maximum avg_fps class    ~46.8
max dt                   ~77.23 ms
```

MediaWidget paint telemetry during active periods commonly shows:

```text
area_px       170400
avg paint     ~4–5 ms
max paint     often ~7–9 ms
```

Conclusion:

This is the strongest bounded first target for the unchanged Pause/Play hitch.

It is not yet proof of sole causality.

Fix the full-card-per-feedback-frame ownership first, then reassess before editing BeatEngine wake/source handoff.

---

# 11. 165 Hz non-visualizer display

Completed GL paint windows on screen 0:

```text
Particle      152.2 FPS
Blockspin     147.3 FPS
Warp          147.3 FPS
Wipe          131.6 FPS
Warp          103.8 FPS
Blockspin     128.0 FPS
Blockspin     143.0 FPS
Blockspin     121.1 FPS
Blockspin     129.9 FPS
```

Summary:

```text
min        103.8 FPS
max        152.2 FPS
median     131.6 FPS
target     165 Hz
```

The same screen has no visualizer ownership.

Conclusion:

The remaining performance problem is shared/system-level.

Do not blame Bubble or create per-mode optimization.

---

# 12. 60 Hz visualizer display

Representative completed GL paint:

```text
Particle      ~59.6 FPS
Blockspin     ~58.7 FPS
Wipe          ~57.6 FPS
Warp          ~52.7 FPS
```

Some windows include:

```text
dt p95 above ~24–32 ms
dt p99 ~45–79 ms
max gaps ~57–108 ms
```

Conclusion:

The physical presentation path still contains large holes capable of making continuous visual motion feel bad even though logical cadence has been decoupled.

---

# 13. Event-loop evidence

After startup settles, ordinary summaries commonly sit around:

```text
p95  ~14–19 ms
p99  ~30–38 ms
```

After Settings/recreation the retained window degrades to approximately:

```text
p95  20.47–21.54 ms
p99  50.00–54.41 ms
```

Larger lifecycle outliers are also present.

Conclusion:

Logical decoupling removed GUI starvation from the simulation clock.

It did not remove GUI starvation from physical presentation or other widgets.

---

# 14. Source findings to retain

## `widgets/spotify_visualizer/logical_runtime.py`

Good:

- `perf_counter()` deadline clock;
- bounded `time.sleep()` wait;
- no catch-up;
- non-daemon joined runtime.

Minor mismatch:

- `wake()` sets `_wake_event`;
- `_wait_until()` does not inspect `_wake_event`;
- only `_stop_event` interrupts bounded sleep slices.

This is not currently a plausible 40–80 ms hitch owner because sleep slices are capped at 4 ms, but the contract should be made truthful without restoring `Event.wait(timeout)`.

## `widgets/spotify_visualizer/tick_pipeline.py`

Good:

- logical/present split;
- plain-data reveal intent;
- presentation-owned idle source-authority separation.

Needs:

- generation-zero-safe identity coercion.

## `widgets/spotify_visualizer/spectrum_presentation_smoothing.py`

Current resting baseline:

```text
1–3% full scale
```

Installed result: visually absent.

Needs an intentional visual/pixel contract.

## `widgets/spotify_visualizer/renderers/spectrum.py`

Bar upload scales source values by `0.55`.

Gate 1 must include this real render math.

## `widgets/media/feedback.py`

Ordinary feedback uses full MediaWidget update per animation step.

The same file already recognizes full-card feedback repaint as starvation risk during transitions and switches to a static path there.

This makes ordinary Pause/Play feedback a high-confidence bounded optimization candidate.

---

# 15. Accepted status of Slices A–E

```text
A  presentation/source readiness split     KEEP
   installed idle visibility               FAIL; next bounded fix

B  logical readiness / GUI reveal split    KEEP

C  scheduler repair                        KEEP

D  one logical runtime owner               KEEP

E  Pause/Play identity preservation        KEEP narrowly
   perceptual hitch closure                 FAIL / never actually achieved
```

No broad rollback.

---

# 16. Next execution order

```text
F  generation-zero identity/fencing
G  real Spectrum idle visible-pixel contract
H  Pause/Play Media feedback repaint isolation
I  shared GUI/compositor delivery closure
J  one final installed acceptance
```

See `Current_Plan.md` and `Docs/P2_Behavioral_Gates.md`.
