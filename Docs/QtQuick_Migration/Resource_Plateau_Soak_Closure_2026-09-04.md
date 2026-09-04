# Resource-Plateau Long-Soak Closure — 2026-09-04

Evidence: `logs/evidence_chest/09_04_soak/` (main + sidecar rotations preserved).
Status: resource plateau **proven and closed** for RAM / private commit / VRAM /
threads / tracked resources / GL / shm / task lanes / logging. One bounded,
unattributed signal remains: a slow Windows **handle** drift, held open as
**AWAITING NEW SOAK** (no new soak expected today).

## Soak shape

- Total runtime ~7h53m (started ~03:49, clean exit ~11:43). No native fault, no
  hang (`native_faults.log`/`hang_stacks.log` clean).
- Second display disappeared ~04:31, returned ~11:39 → ~7h08m in one-display
  topology; screens physically off for much of the single-display period.
- ~149 random transitions; some music playback; Bubble the dominant mode.
- Only trivial image/QML warnings (ICC / truncated-JPEG class).

## Proven non-accumulation (closed)

Retained single-display window (~6.7h of `screensaver_usage.log*`, 1602 samples):

| Signal | Result |
|---|---|
| RSS (app) | plateau, med ~612 MB; large reclamations incl. ~238 MB (not monotonic heap growth) |
| USS (app) | plateau, med ~489 MB |
| Private commit | plateau, med ~2.526 GB |
| VRAM dedicated | flat ~310.2 MB across the single-display period |
| Threads | oscillating band ~78–90, no drift |
| `tracked_resources` | ~24–25, no drift; `rm_resources` flat at 18; `gl_resources` 0 |
| shm segments live | 0 (created 3, consumed 3, 0 unlink failures) |
| Audio-analysis lane | accepted == completed == published == 36,482; 0 rejected-busy, 0 rejected-publication |
| Async logging | ~165k messages, 0 dropped, 0 emergency writes; tiny caller overhead |
| gen2 GC | ~12.6–12.8 ms, real garbage, 0 uncollectable |
| Scene FPS / logical rev | med ~61.98 / ~89.96 Hz; geometry-mismatch count = 0 |
| Topology retire/recreate | one destruction barrier ~359 ms; later restoration ~453 ms; CUSTOM missing-monitor grace behaved (no generation-thrash) |
| Media refresh submissions | flat for hours while idle, resumed only on real activity → event-driven Media migration is not secretly polling |

No progressive frame-delivery degradation. This closes the delivery-quality and
J-optimization "Resource plateau" items for everything the runtime **owns and
accounts**.

## Open: Windows handle drift — AWAITING NEW SOAK

`handles_app` drifts ~2071 → ~2120 across the stable ~6h single-display window
(~+8–9 handles/hour). The final rise to ~2237 is the legitimate second-display
restoration (a second QQuickWindow/context), not drift.

This is **not** accompanied by growth in RSS, USS, private commit, VRAM,
threads, GL/tracked resources, shm, or task counts — every owned accounting
signal is flat. Treat it as a bounded possible handle-owner accumulation, **not**
proof of a general leak.

### Source-first attribution (inconclusive → do not guess)

Periodic native-handle touchers on recurring paths were inspected:

- **psutil sampling** (`ProcessUsageCollector`): process handles are cached on
  long-lived `psutil.Process` objects (`self._processes`), reused every sample
  and pruned on child death → no per-sample handle churn. Not the owner.
- **PDH GPU/VRAM collector** (`WindowsGpuUsageCollector`): `_rebuild` balances
  `OpenQuery`/`CloseQuery`; rebuilds fire every `refresh_seconds=300`. The soak
  shows exactly **80 `gpu_status=warming`** samples = 80 rebuilds. Handle drift
  of ~+49 over ~6h ÷ ~72 rebuilds ≈ **0.68 handle/rebuild** — correlated in
  cadence but not a clean 1:1, more consistent with OS perflib/PDH provider
  handle behaviour than an app-owned leaked handle we forgot to close.
- **Topology / transitions / providers**: `processes=2 children=1` for all 1602
  samples (only the image worker is a child; transitions are not separate
  processes). Media submissions flat while idle. No child-process churn.

The drift (~+9/hr) is far below per-sample handle noise (±20–30), so it cannot be
attributed to a specific per-event owner from this single soak. Per project
guardrails, **no lifetime architecture was changed and no owner was guessed.**

### Next-soak discriminators (no new runtime cadence required)

1. **main vs image-worker** — the sampler now emits `handles_main` alongside
   `handles_app` (this change). The next soak localizes the drift to the main
   process or the image-worker child without new work; the per-process
   `num_handles()` call already existed.
2. **PDH self-attribution** — run a soak with `--usage` **off** (or GPU/VRAM
   sampling disabled). If the drift disappears, it is diagnostic-induced
   Windows perflib/PDH handle behaviour, not a product owner.
3. **rebuild correlation** — correlate `handles_app` deltas against existing
   `gpu_status=warming` samples (already logged; no code needed).

Only if 1–3 still implicate a real product owner should a bounded owner-specific
fix be designed. Do **not** add timers, polling, periodic cleanup, or fallback
owners to chase this.

## Diagnostic corrections made this pass (diagnostics only, no runtime change)

- **Paused-source latency semantics** (`widgets/spotify_visualizer/tick_pipeline.py`):
  on pause→resume, `get_latest_authoritative_frame` returns the pre-pause frame
  until the first fresh frame lands, so `now − source_ts` measured the entire
  paused gap and was logged as `severity=high` latency (soak: `lag_ms=26,120,276`
  ≈ 7.26 h). A frame whose timestamp predates the current playback epoch
  (`engine._last_playback_state_ts`) is now classified `severity=stale_source`
  and kept at DEBUG. Real post-resume latency rides a fresh frame (source_ts
  after the epoch) and still WARNs. Tests: `tests/test_tick_pipeline_latency.py`.
- **Handle owner-specificity** (`core/performance/usage_sampler.py`): added
  `handles_main` to `ProcessUsageSnapshot`, the `[USAGE]` sample line, and the
  lifecycle snapshot, mirroring the existing `rss_main`/`rss_app` split. Tests:
  `tests/test_usage_sampler.py`.

## Epistemic notes

- Direct log facts: the plateau table and the handle series are read from
  `screensaver_usage.log*`.
- Inference (<90% confidence): PDH/perflib as the handle contributor is a
  cadence correlation, not proof — hence AWAITING NEW SOAK, not attributed.
- One mixed-load run identifies owner correlations but is not a controlled A/B;
  discriminator 2 above is the controlled test.
