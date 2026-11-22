### Pre-flip reference pack: n52g_native_vulkan_3 (4e0d5909b, native-vulkan)

Recorded 2026-11-22T16:55:15 to 2026-11-22T16:57:32; load none (idle); clip `anything_mixed2.jsonl`; wallpaper `D:\Temp\Scratch\SRPSS\wallpaper_usu`. Invisible saver, recorded music, `--noupdates`. Compare within a session and control-relative (the control row below).

- Control 2160p (NVIDIA GeForce RTX 4090/PCIe/SSE2): offscreen Crossfade control 0.0212 ms quiet GPU, admitted 3/3.
- First row's conditions: displays on; GPU clock 1935.0 MHz, P0, 57.67 C; busiest other processes by CPU [{'pid': 0, 'name': 'System Idle Process', 'cpu_core_pct': 1916.0}, {'pid': 22588, 'name': "Fortune's Eden.exe", 'cpu_core_pct': 296.0}, {'pid': 23748, 'name': 'python.exe', 'cpu_core_pct': 100.0}, {'pid': 4, 'name': 'System', 'cpu_core_pct': 18.8}, {'pid': 1508, 'name': 'dwm.exe', 'cpu_core_pct': 10.0}].

| Row | fps | render med / p90 ms | swap gap med / p90 ms | late % | hitches/min | CPU % core | GPU ms/frame | RSS / private MB | first 2 s frames |
|---|---|---|---|---|---|---|---|---|---|
| `transition/capillary_bloom/2160p/idle` | 165.0 | 1.6 / 2.1 | 6.0 / 6.8 | 0.0 | 0.00 | 62.2 | 0.504 | 895 / 1310 | n/a |
| `transition/edge_bloom/2160p/idle` | 164.9 | 1.1 / 1.4 | 6.0 / 6.5 | 0.0 | 0.00 | 54.2 | 0.845 | 855 / 1343 | n/a |

Transition runs' hitch figures (the render thread's frame gaps inside the run; handover and reveal outside it; the first frame from the run's start):

| Row | gap med / p90 / max ms | first frame ms | gaps over limit | verdict |
|---|---|---|---|---|
| `transition/capillary_bloom/2160p/idle` | 6.0 / 6.8 / 12.0 | 4.2 | 0 (> 33.0 ms) | pass |
| `transition/edge_bloom/2160p/idle` | 6.0 / 6.5 / 11.2 | 5.2 | 0 (> 33.0 ms) | pass |
