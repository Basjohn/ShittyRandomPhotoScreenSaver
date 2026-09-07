# Architecture Comparison — 2026-08-19 22:49 SAST

This record compares three SRPSS visualizer/presentation architecture states under broadly comparable
heavy reported system-load conditions.

The baseline pack was explicitly identified by the operator as the newer baseline checkout established
earlier. The raw baseline logs do **not** embed a Git SHA. Do not invent one.

## Raw provenance

### Operator-identified baseline

```text
7199cda2-0cfa-4d4e-8b17-05514f0b993a.zip
SHA-256: f5774f7857051aca48b1dfc51f92539e800c077eafe0bd8dc0ca07e3c11a256b
SOURCE_HEAD: not embedded
```

Architecture evidence:
- no `VisualizerLogicalRuntime` start/stop record;
- GUI-owned `SpotifyVisualizerWidget._on_tick` timer remains active;
- low ThreadManager UI queued count.

### Dedicated worker + push presentation

```text
13490052-c96e-4501-b4cf-a29ba3370aca.zip
SHA-256: 16f532c43154de207d9ede734b01946a262285de21c12d6b8c88a3fbfb18890c
[SOURCE_HEAD] 8ac2421e2bc0a7153942fc33eb9f348b505cde9d
```

Architecture:
- dedicated ~90 Hz logical worker;
- latest mailbox;
- steady logical publication marshals GUI presentation callbacks.

### Dedicated worker + pull presentation

```text
ff47b10b-b0f7-4a16-9cef-6154c6e392c4.zip
SHA-256: 402aa1dd0a3a1706ffab86655aa69f21415924fed10c62f5054ddac79b657e4d
[SOURCE_HEAD] 8ac2421e2bc0a7153942fc33eb9f348b505cde9d
```

The pull conversion was uncommitted working-tree code on top of that commit.

---

# 1. Load context

Steady non-zero `cpu_system_pct` median:

```text
baseline             ~47.2%
worker + push        ~41.3%
worker + pull        ~43.5%
```

These are not byte-for-byte identical machine conditions, but they are the same broad heavy-load class.

Median app CPU:

```text
baseline             ~116.9%
worker + push        ~104.4%
worker + pull        ~112.0%
```

Median process GPU busy:

```text
baseline             ~4.8%
worker + push        ~4.4%
worker + pull        ~4.6%
```

GPU saturation is not the explanation for any state.

---

# 2. Logical visualizer service

Long-window visualizer logical/tick service:

```text
baseline GUI-driven tick:
median ~74.65 Hz
range  ~62.0 .. 90.2 Hz
median recorded dt-max ~91.5 ms

worker + push:
median ~89.7 Hz
range  ~89.4 .. 89.7 Hz
recorded dt-max ~54 ms class

worker + pull:
median ~89.6 Hz
range  ~89.2 .. 89.7 Hz
recorded dt-max ~58 ms class
```

Conclusion:

**The dedicated logical worker is a real improvement under load.**

It isolates authored visualizer simulation cadence from much of the GUI starvation that crushes the
baseline GUI-owned tick.

Do not broadly revert the dedicated worker.

---

# 3. 165 Hz physical transition delivery

Completed Blockspin medians:

```text
baseline             72.1 FPS
worker + push       111.35 FPS
worker + pull        94.2 FPS
```

Ranges:

```text
baseline          64.4 .. 102.5
worker + push     64.5 .. 132.8
worker + pull     77.5 .. 123.0
```

Median request acceptance:

```text
baseline             68.99%
worker + push        75.575%
worker + pull        66.40%
```

Conclusion:

**Worker + push is the best of these three loaded architecture states.**

The pull conversion does not improve loaded physical delivery relative to push.

The baseline is substantially worse than both later worker states.

---

# 4. 60 Hz physical delivery

Completed Blockspin medians:

```text
baseline             47.7 FPS
worker + push        52.4 FPS
worker + pull        49.3 FPS
```

Again:

```text
worker + push > worker + pull > baseline
```

All three remain unacceptable.

---

# 5. Delivery-stage signature

165 Hz Blockspin median delivery-stage values:

```text
                         baseline      worker+push      worker+pull
wake lateness p95         ~3.04 ms       ~2.63 ms         ~3.17 ms
dispatch skip age p95    ~66.54 ms      ~74.01 ms       ~114.99 ms
dispatch-pending skips      467            367.5            497
paint-pending skips           0              0                0
```

The shared historical pattern survives every architecture:

```text
deadline source wakes reasonably near target
    ->
GUI dispatch remains pending
    ->
physical delivery misses later opportunities
```

This bottleneck predates the dedicated worker and predates pull.

The pull implementation makes the dispatch-age tail materially worse in this loaded comparison.

---

# 6. Frame-gap tails

Raw `FRAME_GAP_OWNER` statistics:

```text
baseline:
300 events over ~145 s
median gap ~48.0 ms
p95 ~112.8 ms
32 gaps >=100 ms
max ~171.2 ms

worker + push:
303 events over ~156 s
median gap ~52.6 ms
p95 ~128.2 ms
39 gaps >=100 ms
max ~242.6 ms

worker + pull:
257 events over ~131 s
median gap ~65.0 ms
p95 ~145.2 ms
45 gaps >=100 ms
max ~317.7 ms
```

Do not interpret the `last_ui` field as the causal owner merely because it changes by architecture.
It mostly names whichever UI callback happened to complete last.

The useful signal is the worsening tail severity, especially in pull.

---

# 7. GUI callback count is NOT a performance oracle

Latest ThreadManager `ui.queued` totals:

```text
baseline             ~80
worker + push     ~10,427
worker + pull         ~91
```

Yet physical 165 Hz performance is:

```text
72.1
111.35
94.2 FPS
```

in the same order.

Therefore:

> fewer queued GUI callbacks does not imply better SRPSS performance.

The callback-per-logical-publication stream is architecturally noisy, but its count was never proven to
be the dominant bottleneck.

Removing it produced a cleaner counter and a worse loaded product.

This directly falsifies any optimization strategy that treats UI callback count itself as the target.

---

# 8. Media/widget paint

Weighted `media.paint` average:

```text
baseline             ~4.92 ms
worker + push        ~5.37 ms
worker + pull        ~6.03 ms
```

Median window-average:

```text
baseline             ~4.62 ms
worker + push        ~5.85 ms
worker + pull        ~6.79 ms
```

Media paint remains a real shared-GUI cost and has not improved through the architecture sequence.

It is not sufficient by itself to explain the entire transition collapse.

---

# 9. Playback flapping predates worker and pull

The baseline raw log already contains playback-state wobble:

```text
Deferring paused media state for 700ms to absorb playback-state wobble
Keeping audio capture warm for 6.0s after playback pause
Play resumed while capture stayed warm
```

with repeated pause/resume transitions around transport edges.

The operator also reports the baseline has:
- start/stop hitching;
- playback flapping;
- very responsive transport ingress.

Therefore:

**playback-state reconciliation is an inherited baseline defect.**

K and pull did not create the fundamental state-flap problem.

The correct fix remains authoritative state-generation/freshness ownership, not another blind debounce.

---

# 10. Sporadic visualizer spawn is pull-specific

The baseline overlay continuously records hundreds of physical paints per ordinary ten-second window.

There is no equivalent baseline evidence of:

```text
logical runtime active
+
overlay paint=0 for ~10–30 seconds
```

The pull runs do contain that failure.

Therefore:

**the lost-wakeup / sporadic-spawn regression belongs to the pull presentation design as currently implemented.**

Do not attribute it to the older baseline.

---

# 11. Cumulative architecture judgement

## Dedicated worker

**RETAIN.**

Evidence:
- much stronger logical cadence under load;
- better 165 Hz physical delivery than baseline;
- better 60 Hz delivery than baseline;
- lower app CPU than baseline in this comparison.

## Callback-per-publication push

Architecturally noisy, but currently:

**BEST KNOWN LOADED DELIVERY STATE.**

It is not the final desired design, but it is the strongest known working state among these three.

## Pull presentation

**DO NOT TREAT AS RETAINED.**

It:
- removes callback volume;
- provides no demonstrated low-load product improvement;
- performs worse than push under comparable load;
- worsens dispatch-age/frame-gap tails;
- introduces a unique physical-liveness/spawn regression.

The pull seam must either:
1. earn a decisive improvement through a very bounded corrected design and integrated benchmark; or
2. be removed in favor of the known worker+push state.

Do not carry it merely because its internal queue counter looks cleaner.

---

# 12. Broader system conclusion

The common unresolved disease is older than both worker and pull:

```text
shared GUI physical presentation loses service badly under CPU contention
while
adaptive deadline wakes remain comparatively timely
and
GPU remains lightly loaded
```

The dedicated worker successfully removes logical simulation from much of this starvation.

The remaining long-term architecture question is therefore increasingly about **physical presentation
and shared GUI-thread availability**, not visualizer simulation cadence.

That question should be investigated from the worker+push known-good architecture state, using the
integrated dual-display benchmark rather than another chain of local probes.
