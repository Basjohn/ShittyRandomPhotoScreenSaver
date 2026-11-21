### Pre-flip gain: beam_pre_port -> beam_native_vulkan

eb59ae04a (python-gl) -> 6dd9dd107 (native-vulkan). Gain is positive when better; flat within 5 %.

- Control 2160p: 0.073728 -> 0.065024 ms (x0.88).

| Row | fps | render med ms | render p90 ms | swap gap med ms | swap gap p90 ms | late % | hitches/min | saver CPU % core | GPU ms/frame | RSS MB | private MB | first 2 s frames |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `transition/beam/2160p/idle` | n/a | +58.3% | +59.3% | n/a | n/a | n/a | n/a | -66.2% | n/a | +9.6% | -6.7% | n/a |
