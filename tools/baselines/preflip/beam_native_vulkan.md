### Pre-flip reference pack: beam_native_vulkan (6dd9dd107, native-vulkan)

Recorded 2026-11-21T16:10:45 to 2026-11-21T19:35:48; load none (idle); clip `anything_mixed2.jsonl`; wallpaper `D:\Temp\Scratch\SRPSS\wallpaper_usu`. Invisible saver, recorded music, `--noupdates`. Compare within a session and control-relative (the control row below).

- Control 2160p (NVIDIA GeForce RTX 4090/PCIe/SSE2): offscreen Crossfade control 0.0650 ms quiet GPU, admitted 3/3.
- First row's conditions: displays on; GPU clock 210.0 MHz, P8, 44.73 C; busiest other processes by CPU [{'pid': 0, 'name': 'System Idle Process', 'cpu_core_pct': 2206.4}, {'pid': 3992, 'name': 'MsMpEng.exe', 'cpu_core_pct': 29.9}, {'pid': 4, 'name': 'System', 'cpu_core_pct': 10.8}, {'pid': 5604, 'name': 'Taskmgr.exe', 'cpu_core_pct': 5.4}, {'pid': 13236, 'name': 'python.exe', 'cpu_core_pct': 5.4}].

| Row | fps | render med / p90 ms | swap gap med / p90 ms | late % | hitches/min | CPU % core | GPU ms/frame | RSS / private MB | first 2 s frames |
|---|---|---|---|---|---|---|---|---|---|
| `transition/beam/2160p/idle` | 188.3 | 0.4 / 0.7 | 5.3 / 5.8 | 0.0 | 0.00 | 32.9 | 1.497 | 776 / 1109 | n/a |

Transition runs' hitch figures (the render thread's frame gaps inside the run; handover and reveal outside it; the first frame from the run's start):

| Row | gap med / p90 / max ms | first frame ms | gaps over limit | verdict |
|---|---|---|---|---|
| `transition/beam/2160p/idle` | 5.3 / 5.8 / 9.6 | 9.2 | 0 (> 33.0 ms) | pass |
