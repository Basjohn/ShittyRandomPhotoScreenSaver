### Pre-flip reference pack: et_stall_ab_steam_off (83915122c, native-vulkan)

Recorded 2026-11-22T13:33:50 to 2026-11-22T13:36:33; load none (idle); clip `anything_mixed2.jsonl`; wallpaper `D:\Temp\Scratch\SRPSS\wallpaper_usu`. Invisible saver, recorded music, `--noupdates`. Compare within a session and control-relative (the control row below).

- First row's conditions: displays on; GPU clock 615.0 MHz, P3, 50.73 C; busiest other processes by CPU [{'pid': 0, 'name': 'System Idle Process', 'cpu_core_pct': 2030.8}, {'pid': 19352, 'name': 'Spotify.exe', 'cpu_core_pct': 104.3}, {'pid': 14884, 'name': 'python.exe', 'cpu_core_pct': 100.4}, {'pid': 17044, 'name': 'cam_helper.exe', 'cpu_core_pct': 77.3}, {'pid': 2632, 'name': 'NVDisplay.Container.exe', 'cpu_core_pct': 15.4}].

| Row | fps | render med / p90 ms | swap gap med / p90 ms | late % | hitches/min | CPU % core | GPU ms/frame | RSS / private MB | first 2 s frames |
|---|---|---|---|---|---|---|---|---|---|
| `transition/exploding_tiles/2160p/idle` | 162.1 | 0.8 / 1.2 | 5.3 / 6.1 | 0.2 | 16.07 | 15.6 | 0.101 | 879 / 1458 | n/a |

Transition runs' hitch figures (the render thread's frame gaps inside the run; handover and reveal outside it; the first frame from the run's start):

| Row | gap med / p90 / max ms | first frame ms | gaps over limit | verdict |
|---|---|---|---|---|
| `transition/exploding_tiles/2160p/idle` | 5.3 / 6.1 / 4252.0 | 4252.0 | 2 (> 33.0 ms) | fail: 2 gap(s) over 33 ms ([4251.98, 439.21]) |
