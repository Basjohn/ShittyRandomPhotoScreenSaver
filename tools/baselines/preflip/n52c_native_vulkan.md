### Pre-flip reference pack: n52c_native_vulkan (c806ebb30, native-vulkan)

Recorded 2026-11-21T19:08:51 to 2026-11-21T19:29:53; load none (idle); clip `anything_mixed2.jsonl`; wallpaper `D:\Temp\Scratch\SRPSS\wallpaper_usu`. Invisible saver, recorded music, `--noupdates`. Compare within a session and control-relative (the control row below).

- Control 2160p (NVIDIA GeForce RTX 4090/PCIe/SSE2): offscreen Crossfade control 0.0225 ms quiet GPU, admitted 3/4.
- First row's conditions: displays on; GPU clock 1620.0 MHz, P5, 43.82 C; busiest other processes by CPU [{'pid': 0, 'name': 'System Idle Process', 'cpu_core_pct': 2301.0}, {'pid': 10476, 'name': 'explorer.exe', 'cpu_core_pct': 76.8}, {'pid': 17240, 'name': 'Spotify.exe', 'cpu_core_pct': 9.6}, {'pid': 5604, 'name': 'Taskmgr.exe', 'cpu_core_pct': 6.9}, {'pid': 11268, 'name': 'cam_helper.exe', 'cpu_core_pct': 4.1}].

| Row | fps | render med / p90 ms | swap gap med / p90 ms | late % | hitches/min | CPU % core | GPU ms/frame | RSS / private MB | first 2 s frames |
|---|---|---|---|---|---|---|---|---|---|
| `transition/blinds/2160p/idle` | 187.9 | 0.5 / 0.7 | 5.3 / 5.9 | 0.0 | 0.00 | 29.0 | 0.240 | 823 / 1221 | n/a |
| `transition/cube_turn/2160p/idle` | 188.2 | 0.5 / 0.7 | 5.3 / 5.8 | 0.0 | 0.00 | 28.4 | 0.430 | 823 / 1445 | n/a |
| `transition/depth_cascade/2160p/idle` | 185.0 | 0.5 / 0.7 | 5.3 / 6.0 | 0.0 | 0.00 | 35.5 | 0.667 | 783 / 1405 | n/a |
| `transition/jigsaw/2160p/idle` | 183.3 | 0.4 / 0.7 | 5.4 / 6.0 | 0.0 | 0.00 | 28.6 | 1.069 | 819 / 1442 | n/a |

Transition runs' hitch figures (the render thread's frame gaps inside the run; handover and reveal outside it; the first frame from the run's start):

| Row | gap med / p90 / max ms | first frame ms | gaps over limit | verdict |
|---|---|---|---|---|
| `transition/blinds/2160p/idle` | 5.3 / 5.9 / 12.8 | 12.8 | 0 (> 33.0 ms) | pass |
| `transition/cube_turn/2160p/idle` | 5.3 / 5.8 / 15.7 | 9.1 | 0 (> 33.0 ms) | pass |
| `transition/depth_cascade/2160p/idle` | 5.3 / 6.0 / 19.9 | 19.9 | 0 (> 33.0 ms) | pass |
| `transition/jigsaw/2160p/idle` | 5.4 / 6.0 / 18.9 | 18.9 | 0 (> 33.0 ms) | pass |
