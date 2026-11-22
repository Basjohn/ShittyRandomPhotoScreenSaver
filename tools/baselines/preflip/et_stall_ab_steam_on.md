### Pre-flip reference pack: et_stall_ab_steam_on (83915122c, native-vulkan)

Recorded 2026-11-22T13:29:20 to 2026-11-22T13:33:22; load none (idle); clip `anything_mixed2.jsonl`; wallpaper `D:\Temp\Scratch\SRPSS\wallpaper_usu`. Invisible saver, recorded music, `--noupdates`. Compare within a session and control-relative (the control row below).

- First row's conditions: displays on; GPU clock 555.0 MHz, P3, 47.19 C; busiest other processes by CPU [{'pid': 0, 'name': 'System Idle Process', 'cpu_core_pct': 2051.8}, {'pid': 19352, 'name': 'Spotify.exe', 'cpu_core_pct': 105.0}, {'pid': 27636, 'name': 'python.exe', 'cpu_core_pct': 100.2}, {'pid': 20548, 'name': 'firefox.exe', 'cpu_core_pct': 16.3}, {'pid': 17044, 'name': 'cam_helper.exe', 'cpu_core_pct': 12.5}].

| Row | fps | render med / p90 ms | swap gap med / p90 ms | late % | hitches/min | CPU % core | GPU ms/frame | RSS / private MB | first 2 s frames |
|---|---|---|---|---|---|---|---|---|---|
| `transition/exploding_tiles/2160p/idle` | 184.4 | 1.0 / 1.5 | 5.3 / 6.2 | 0.1 | 0.00 | 59.7 | 1.371 | 898 / 1744 | n/a |

Transition runs' hitch figures (the render thread's frame gaps inside the run; handover and reveal outside it; the first frame from the run's start):

| Row | gap med / p90 / max ms | first frame ms | gaps over limit | verdict |
|---|---|---|---|---|
| `transition/exploding_tiles/2160p/idle` | 5.3 / 6.2 / 45.9 | 11.8 | 1 (> 33.0 ms) | fail: 1 gap(s) over 33 ms ([45.86]) |
