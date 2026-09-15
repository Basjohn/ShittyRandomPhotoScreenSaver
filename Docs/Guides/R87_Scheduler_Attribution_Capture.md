# R-87 Scheduler Attribution — CHK16 Result / Local-Only Capture Guardrail

CHK15 remains the golden performance/freshness baseline. The planned CHK16 scheduler capture has been completed once; this guide now
records the result and prevents the raw-trace handoff mistake from recurring.

## Result

The D1 pure-heavy capture lasted 60.101 s with no WPR event loss reported. Quick render TID `14044` spent approximately:
- **63.920% Waiting**;
- **35.050% Running**;
- **1.004% Ready**.

Ready->Running latency was **0.002600 ms median / 0.004900 ms p95 / 0.073238 ms p99**. Ordinary Windows runnable starvation is
therefore **not supported** for this captured condition. Do not use R-87 as justification for blind render-thread priority boosting.

`QUICK_SYNC_READY -> RENDER_BEGIN` must also not be called a pure scheduler wait. It is the post-sync/pre-render-callback
**render-entry interval** and contains Qt scenegraph/callback-boundary work. In this capture its p95 tail was mostly Waiting + Running,
not Ready.

## Raw ETL guardrail

A WPR ETL is a **local-only temporary artifact**. It is not a GODZIP/chat handoff artifact. Do not ask the operator to upload one.
The one physical ETL already collected is sufficient for the current scheduler conclusion.

`tools/scheduler_trace_reduce.py` reduces a local capture to:
- `scheduler_attribution.json`;
- `scheduler_attribution.txt`.

Those small files, plus ordinary SRPSS logs/frame trace if needed, are the handoff evidence. `tools/scheduler_trace_capture.py` now
automatically runs the reducer when `--srpss-log-dir` is supplied and deletes the raw ETL after successful reduction.
`--keep-etl` exists only for an explicit **local** WPA/deep-dive need. If reduction fails, the ETL is retained locally rather than
destroyed, and the tool prints `DO NOT ATTACH`.

## If this lane is ever deliberately repeated

There is currently **no planned repeat**. If later evidence materially reopens OS-scheduler attribution, use D1 pure-heavy only and:

```powershell
py tools\scheduler_trace_capture.py capture --duration-s 60 --srpss-log-dir .\logs
```

The output expected for handoff is the tiny reducer report, not `srpss_scheduler.etl`. Do not use D0/dual-display merely to repeat
this question.

## Current next seam

CHK18's global 1 ms CPython switch-interval A/B is complete and **rejected**, including operator feedback that the 1 ms run **felt worse**. Do not retain or repeat `sys.setswitchinterval()` as an R-87 policy.

CHK19's one native Qt timing run is also complete. It placed the residual primarily in Qt's native **render** phase, not sync/swap, and a manual Burn transition cleanly increased render cost without changing that steady-state result. However, `QSG_RENDER_TIMING` emitted tens of thousands of synchronous Qt DEBUG messages and the CHK19 message handler echoed them to the terminal, making it too intrusive for routine performance work. The in-app `--qsg-render-timing` admission is retired in CHK20; do **not** ask for another run. `tools/qsg_render_timing_report.py` is retained for the historical capture only.

The corrected interpretation is that `QUICK_SYNC_READY -> RENDER_BEGIN` contains native scene rendering **before Qt reaches the visualizer render node**. CHK20 therefore adds binary `--frame-trace` markers around the predecessor full-screen background render node and reports steady/transition stage time plus overlap with that render-entry interval. No additional WPR/ETL or text timing logger is involved.

There is **no dedicated physical run requested for CHK20**. Collect the new markers on the next otherwise-useful D1 `--frame-trace` run. If background rendering explains a large part of the interval, optimize only a measured safe sub-seam; if it does not, continue through other predecessor scene content. Preserve all CHK15 visual/freshness/lifecycle guardrails.
