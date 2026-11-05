# R-171 — Capture TripleBuffer lost fresh audio when three callbacks landed between ticks (Spectrum stutter)

**STRONG RETENTION VALUE DOCUMENT**

Date: 2026-11-05
Status: Source repair (`utils/lockfree/triple_buffer.py`); operator eyes-on pending
Evidence: worktree `.artifacts/evidence/spectrum/jerkiness_20261105/` (log archive `logsa4c1141ee62.zip`,
scripts, `PROGRESS.md`)

## Observed failure

"Spectrum is feeling very jerky in a session but I was in Waveform for a long time — visual smoothing or hot swap?
We seem to fall into this state often." Session: Waveform Ribbon 15:30–15:40, hot swap to Spectrum, 17 Spectrum
preset changes, a Settings round trip, then other modes.

## What it was not

- **Frame pacing (b):** steady Spectrum ran 90 fps / 90 revisions/s, PERF_HUD `dt_max` ~15 ms; frame trace steady
  swap median 11.0 ms, p99 16.3 ms. Spikes only at preset activations (lifecycle).
- **Stale technical/smoothing config (a):** every `[VIS_TECH_CONFIG]` after the swap is the authored Spectrum profile
  (block 128, Dynamic Floor on, AGC 0.15, smoothing 0.7 on), identical across all curated presets.
- **Hot-swap state bleed (c):** offline, real recorded PCM through production Spectrum DSP, engine smoothing, the
  logical tick and `SpectrumFrameRuntime`: 60 s of Waveform, then the owner's production activation transaction,
  then Spectrum, matched a fresh Spectrum start to 1e-13 after the play edge. Worker/engine DSP state at the two
  boundaries is identical. (The first ~1 s differs by design: a cold start is a play edge with its resume ramp, a
  warm swap is not.)

## Evidence that found it

`[AUDIO_LANE]` analyses per second against the 90 Hz logical tick, per mode, across the whole session:

| Mode (block) | analyses/s | logical ticks/s |
| --- | --- | --- |
| Waveform / Oscilloscope / DevCurve (256) | ~86 | 90 |
| Extruded Bubble (512) | ~84 | 90 |
| **Spectrum, Bubble (128)** | **~69.5** | 90 |

The frame trace (`audio_analysis_begin` against `logical_publish`) showed 22–25% of Spectrum publications carried no
new analysis, in a regular beat (analysis gaps alternating 11.1 / 22.3 ms); Waveform ~4%. A fresh capture start at
block 128 after Settings (15:42:57, not a hot swap) behaved the same: block-size dependent, not swap dependent.

A capture-only probe of the operator's device (Realtek loopback, 48 kHz, 6 channels) delivered 128-sample callbacks
in bursts of 3–4 every 10 ms, with only 0.3–0.6% of 90 Hz tick windows lacking a callback. Counting the windows whose
callback count is a multiple of three predicted the logged miss rates exactly: **22.6% at 128, 4.0% at 256**,
5.3% at 512, 0% at Auto (480).

## Root cause

`TripleBuffer` (capture frame → engine tick, and the engine's bar-result buffer) published round-robin into three
slots and judged freshness by **slot index**: `consume_latest()` returned `None` when the ready index equalled the
last-read index. Exactly 3 (or 6, …) publishes between two consumes wrap back to that index, so a tick with brand-new
audio saw "nothing new". The engine held its bars for that tick and the next analysis applied a double-length
smoothing step: a regular ~20 Hz hold-then-jump on top of correct frame pacing.

## Why this class keeps coming back

- The miss needs *callbacks-per-tick ≡ 0 (mod 3)*, which depends on block size, the device period and the beat
  between the device's 100 Hz bursts and the 90 Hz tick. Modes on 256/512 rarely hit it; Spectrum and Bubble ship at
  128 and hit it about every fourth tick. It looks like a mode or session "state".
- The symptom reads as smoothing. R-55 (paint-local smoothing), R-22 (mode-switch bar bleed) and R-76 (tall-viewport
  temporal scaling) all chased Spectrum motion in the presentation layer; none measured whether each tick had new
  source audio. The reactivity guide already says delivery holes masquerade as bad smoothing — this hole sat below
  the analysis lane, in a primitive unchanged since 2025.
- Offline replay feeds one source frame per tick at the seam above the buffer, so no replay could ever show it.

## Repair

`TripleBuffer` stores `(sequence, value)` as one reference (atomic under the GIL) and compares the publication
sequence with the last consumed one. Single producer, single consumer, no lock, no new thread, timer or cadence. No
smoothing or preset value changed.

## Guards

- `tests/test_visualizer_audio_source_freshness.py`
  - every publish count 1–7 between consumes returns the newest value (old code fails at 3 and 6);
  - the real BeatEngine fed WASAPI-shaped 128-sample bursts against 90 Hz ticks analyses the newest block on every
    tick that had new audio (old code fails);
  - Spectrum after ~10 s of Waveform and the production activation transaction moves identically to a fresh
    Spectrum after the play edge (guards the hot-swap hypothesis, which was ruled out).
- Diagnostic rule (checklist 1C): `[AUDIO_LANE]` published/s should track the logical tick rate. A regular
  11/22 ms analysis gap is source freshness, not smoothing; measure it before touching any temporal filter.

## Open

Operator eyes-on in a Spectrum session at block 128. Expect `[AUDIO_LANE]` ~86–90 published/s in Spectrum and Bubble.
