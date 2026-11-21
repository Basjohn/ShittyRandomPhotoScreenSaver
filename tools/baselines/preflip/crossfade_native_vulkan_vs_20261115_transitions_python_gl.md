### Pre-flip gain: 20261115_transitions_python_gl -> crossfade_native_vulkan

1a6ce8680 (python-opengl) -> f6a815dea (native-vulkan). Gain is positive when better; flat within 5 %.


| Row | fps | render med ms | render p90 ms | swap gap med ms | swap gap p90 ms | late % | hitches/min | saver CPU % core | GPU ms/frame | RSS MB | private MB | first 2 s frames |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `transition/crossfade/2160p/idle` | -100.0% | +67.9% | +65.0% | n/a | n/a | n/a | n/a | +2.0% | n/a | +11.2% | +17.7% | n/a |

removed: `transition/crossfade/2160p/loaded`, `transition/disintegrate/2160p/idle`, `transition/disintegrate/2160p/loaded`, `transition/exploding_tiles/2160p/idle`, `transition/exploding_tiles/2160p/loaded`, `transition/jigsaw/2160p/idle`, `transition/jigsaw/2160p/loaded`, `transition/volumetric_dissolve/2160p/idle`, `transition/volumetric_dissolve/2160p/loaded`
