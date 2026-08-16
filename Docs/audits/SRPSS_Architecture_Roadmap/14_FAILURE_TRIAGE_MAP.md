# 14 — Failure Triage Map

Last reconciled: 2026-08-16

Use this map to find owners, not symptom patches. Current accepted delivery evidence:
`Docs/phase_reports/P05_PRESENTATION_DELIVERY_ATTRIBUTION.md`.

## Frame gap / missed high-refresh deadlines

First split:

1. adaptive wake lateness;
2. queued GUI dispatch wait / dispatch-pending skips;
3. already-dispatched paint-pending wait / paint-pending skips;
4. paint duration.

Do not treat total request age as one undifferentiated timer problem.

## Visualizer enabled: 165 Hz under-delivery and sibling-display slowdown

Check logical publication, overlay handoff, auxiliary update requests and paint rates.

If logical publications and `SpotifyBarsGLOverlay.update()` requests remain effectively
one-for-one at ~85–95 Hz, this is **bad smell 1**. The 2026-08-16 A/B/A evidence already
proves that stream is a shared-GUI amplifier.

Fix presentation-request ownership; do not lower visualizer cadence.

## Visualizer requests suppressed but no-visualizer control is still better

This is **bad smell 1b**.

Do not immediately blame all of `set_state()`. Split producer/state build, pure-data
render preparation, Qt overlay commit, presentation request and paint. Move only proven
thread-safe immutable preparation.

## Visualizer disabled from startup but 165 Hz still misses deadlines

This is **bad smell 2**.

If dispatch-pending skips dominate paint-pending skips while wake lateness is healthy,
inspect concrete queued GUI callbacks/commits. Do not change adaptive timer frequency or
add repaint rescue.

## Visualizer paint/update rate exceeds display refresh

Logical publication above refresh is allowed. The problem is a measured one-to-one
presentation request stream that starves delivery.

Do not use:

- source/event decimation;
- display-FPS logical cap;
- pending-until-paint admission;
- paint acknowledgement;
- producer elapsed-time gates.

## High GPU busy / suspected visualizer shader cost

Use sampled owner-context GPU timing. In the accepted Spectrum checkpoint, visualizer
shader duration is tiny relative to delivery loss. Do not infer shader ownership from
process GPU busy alone.

## Separate visualizer GL surface suspected

Compare a live request-suppressed state against a live hidden-surface state.

Current accepted evidence shows only a modest incremental C-over-B gain. Do not begin a
one-surface-per-display rewrite unless post-P2/P3 evidence changes that conclusion.

## Window activation correlation

Treat activation/foreground state as a correlate unless same-process evidence proves it
is necessary. The dual-display A/B/C evidence reproduces the important delivery problem
without requiring the earlier single-display activation explanation.

## Bubble looks delayed/flat

Check shared GUI delivery/source age first. Do not change Bubble physics, authored cadence,
source sampling, one-in-flight semantics or executor ownership without direct mode-owned
evidence. `666624d4` remains a negative control.

## Spectrum less smooth

Check logical/presentation separation, second clocks, paint-local state and delivery
pressure. `ebfec397` remains the negative control.

## `generic_pair_warm` / transition-start stall

Current→old identity and ordinary redundant upload-copy defects are closed. Reopen only
if exact cache/upload evidence contradicts the current contract.

## Settings mutation or provider callback hitch

Follow Prepare → Commit → Persist. Move only proven I/O/pure-data preparation off GUI;
keep required Qt commit ownership.

## Temporary A/B/C diagnostic code encountered

It is P0 removal debt. Do not build production behaviour on the monkeypatch, CLI gate or
hotkey. Keep passive delivery-stage metrics.

## Historical Settings/Edit deleted-wrapper failures

Solved regression reference only. Consult historical records if the same shape actually
reappears; do not reopen during delivery work.

## Memory flat but excessive

Separate RSS/private commit, mappings/stacks, child processes, tracked CPU/GL bytes and
VRAM. Flat is not automatically acceptable; do not trim/recycle/GC to beautify graphs.
