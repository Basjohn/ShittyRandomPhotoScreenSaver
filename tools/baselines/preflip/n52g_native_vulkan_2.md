### Pre-flip reference pack: n52g_native_vulkan_2 (4e0d5909b, native-vulkan)

Recorded 2026-11-22T16:52:07 to 2026-11-22T16:54:32; load none (idle); clip `anything_mixed2.jsonl`; wallpaper `D:\Temp\Scratch\SRPSS\wallpaper_usu`. Invisible saver, recorded music, `--noupdates`. Compare within a session and control-relative (the control row below).

- Control 2160p (NVIDIA GeForce RTX 4090/PCIe/SSE2): offscreen Crossfade control 0.0214 ms quiet GPU, admitted 3/3.
- First row's conditions: displays on; GPU clock 2520.0 MHz, P0, 55.76 C; busiest other processes by CPU [{'pid': 0, 'name': 'System Idle Process', 'cpu_core_pct': 1564.7}, {'pid': 22588, 'name': "Fortune's Eden.exe", 'cpu_core_pct': 291.4}, {'pid': 12900, 'name': 'python.exe', 'cpu_core_pct': 109.4}, {'pid': 23748, 'name': 'python.exe', 'cpu_core_pct': 98.6}, {'pid': 21020, 'name': 'python.exe', 'cpu_core_pct': 96.4}].

| Row | fps | render med / p90 ms | swap gap med / p90 ms | late % | hitches/min | CPU % core | GPU ms/frame | RSS / private MB | first 2 s frames |
|---|---|---|---|---|---|---|---|---|---|
| `transition/capillary_bloom/2160p/idle` | 164.7 | 1.3 / 1.6 | 6.0 / 6.5 | 0.0 | 0.00 | 69.0 | 0.767 | 893 / 1310 | n/a |
| `transition/edge_bloom/2160p/idle` | 164.6 | 1.3 / 1.6 | 6.0 / 6.5 | 0.0 | 0.00 | 52.2 | 0.798 | 887 / 1364 | n/a |

Transition runs' hitch figures (the render thread's frame gaps inside the run; handover and reveal outside it; the first frame from the run's start):

| Row | gap med / p90 / max ms | first frame ms | gaps over limit | verdict |
|---|---|---|---|---|
| `transition/capillary_bloom/2160p/idle` | 6.0 / 6.5 / 18.3 | 5.0 | 0 (> 33.0 ms) | pass |
| `transition/edge_bloom/2160p/idle` | 6.0 / 6.5 / 15.9 | 4.9 | 0 (> 33.0 ms) | pass |
