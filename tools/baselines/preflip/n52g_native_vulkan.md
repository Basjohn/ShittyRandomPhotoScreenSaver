### Pre-flip reference pack: n52g_native_vulkan (4e0d5909b, native-vulkan)

Recorded 2026-11-22T16:46:35 to 2026-11-22T16:49:15; load none (idle); clip `anything_mixed2.jsonl`; wallpaper `D:\Temp\Scratch\SRPSS\wallpaper_usu`. Invisible saver, recorded music, `--noupdates`. Compare within a session and control-relative (the control row below).

- Control 2160p (NVIDIA GeForce RTX 4090/PCIe/SSE2): offscreen Crossfade control 0.0212 ms quiet GPU, admitted 3/3.
- First row's conditions: displays on; GPU clock 2790.0 MHz, P0, 47.96 C; busiest other processes by CPU [{'pid': 0, 'name': 'System Idle Process', 'cpu_core_pct': 1654.5}, {'pid': 22588, 'name': "Fortune's Eden.exe", 'cpu_core_pct': 306.4}, {'pid': 23748, 'name': 'python.exe', 'cpu_core_pct': 103.8}, {'pid': 25152, 'name': 'python.exe', 'cpu_core_pct': 95.2}, {'pid': 21020, 'name': 'python.exe', 'cpu_core_pct': 89.4}].

| Row | fps | render med / p90 ms | swap gap med / p90 ms | late % | hitches/min | CPU % core | GPU ms/frame | RSS / private MB | first 2 s frames |
|---|---|---|---|---|---|---|---|---|---|
| `transition/capillary_bloom/2160p/idle` | 164.0 | 1.5 / 2.0 | 6.0 / 6.8 | 0.1 | 0.00 | 66.5 | 0.652 | 923 / 1328 | n/a |
| `transition/edge_bloom/2160p/idle` | 163.7 | 1.4 / 1.9 | 6.0 / 6.7 | 0.1 | 0.00 | 70.7 | 0.558 | 896 / 1401 | n/a |

Transition runs' hitch figures (the render thread's frame gaps inside the run; handover and reveal outside it; the first frame from the run's start):

| Row | gap med / p90 / max ms | first frame ms | gaps over limit | verdict |
|---|---|---|---|---|
| `transition/capillary_bloom/2160p/idle` | 6.0 / 6.8 / 40.8 | 5.7 | 1 (> 33.0 ms) | fail: 1 gap(s) over 33 ms ([40.83]) |
| `transition/edge_bloom/2160p/idle` | 6.0 / 6.7 / 39.4 | 5.0 | 1 (> 33.0 ms) | fail: 1 gap(s) over 33 ms ([39.4]) |
