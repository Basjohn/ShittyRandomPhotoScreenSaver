# P2 Behavioral Gates

Unit tests are necessary but installed perception remains authoritative.

## Gate 1 — paused Spectrum perceptible idle
Real renderer/pixel evidence. No fake source authority.  
**Second-run status: GREEN.**

## Gate 2 — all five modes reveal
All modes reveal through the worker-owned logical architecture and survive switching/recreation.

## Gate 3 — logical cadence
Ordinary Bubble:
- >= 88 Hz average;
- <= 2% skipped deadlines;
- no recurring unexplained >33 ms logical holes;
- no FIFO/catch-up replay.

Average/skip portion is green; long-tail portion remains open.

## Gate 4 — worker logical code is GUI/GL-free
No QWidget/QPixmap/QPainter/GL mutation from worker-callable logical paths.

## Gate 5 — required handoffs fail loudly
Missing presentation/reveal seams cannot silently degrade.

## Gate 6 — exactly one logical visualizer clock
`VisualizerLogicalRuntime` remains sole mode-general owner.  
**GREEN.**

## Gate 7A — Pause/Play identity
Retain runtime generation, warm capture, compositor/card/GL ownership, no recreate, no debounce.  
**Identity portion GREEN; perceptual hitch still RED.**

## Gate 7B — transport command must not block GUI
With a deliberately delayed backend:
- command ingress returns before backend completion;
- GUI follow-up event executes before backend completion;
- optimistic state is immediate;
- exactly one backend command runs;
- reconciliation occurs later;
- no nested IO wait/deadlock.

Current synchronous-wait behavior must fail the negative control.

## Gate 7C — animated feedback must not run full parent paint pipeline every frame
Use real `MediaWidget` + real Qt event processing.

For one normal animated feedback event:
- visual feedback changes across multiple frames;
- parent full paint-pipeline executions attributable to feedback stay a small constant (target <= 2 unless source requires another justified constant);
- artwork/header/metadata expensive subpainters do not run every frame;
- lightweight feedback path may animate normally;
- old parent repaint path fails the negative control.

Counting monkeypatched `update()` method names is insufficient.

## Gate 8 — Bubble Temporal Fidelity
Use `Docs/Guardrails/Bubble_Temporal_Fidelity.md`. Visible stepping/flicker or recurring unexplained >33 ms holes fail.

## Gate 9 — generation zero fencing
0 valid, missing invalid, stale 0 cannot reveal into 1.  
**GREEN; retain permanently.**

## Gate 10 — known-bad negative controls
Relevant gates must fail against historical bad behavior.

## Gate 11 — shared 165 Hz presentation
Recover toward accepted low/mid-150 FPS class. Current ~136–145 FPS and ~88–92% request acceptance is RED. Do not lower target.

## Gate 12 — 60 Hz visualizer presentation tails
No rejected-class state/frame tails and no visible Bubble stepping.

## Gate 13 — Pause/Play perceptual acceptance
No visible freeze/hitch on ordinary or rapid Pause/Play. Immediate control acknowledgement. No visualizer recreate.

## Gate 14 — stale source/activation authority
Retired generation/activation data cannot become visible.

## Gate 15 — lifecycle
Settings/recreate and shutdown quiesce/join owners without orphan workers or identity leaks.

# Second-run status

Green:
- Gate 1;
- Gate 3 average/skip portion;
- Gate 6;
- Gate 7A identity;
- Gate 9.

Open/Red:
- Gate 3 tails;
- Gate 7B;
- Gate 7C;
- Gate 8;
- Gate 11;
- Gate 12;
- Gate 13.
