# Wallpaper image quality

Display → Image Quality offers one resampling choice. **Smooth** is the default fast Qt scaler;
**Hamming** is a lighter Pillow filter useful for downscaling detail; **Lanczos** retains fine detail with
a wider, more expensive filter. Sharpening is independent and only applies while downscaling.
HQ2x is a pixel-art enlargement algorithm, not a general photograph resampler, and is not offered here.

`display.resample_filter` is the sole current choice (`smooth`, `hamming`, `lanczos`). Existing profiles and SST
imports translate `display.use_lanczos=true` to `lanczos` and `false` to `smooth`, then remove the old key.
An explicit current choice wins. Defaults, UI, export, cache identity and worker payloads use only the new key.
The one-way bridge is `core/settings/resample_filter_input_compat.py`.

## Processing and ownership

- Smooth without sharpening uses the same QImage path in foreground and speculative workers. Cache hits must not
  change the image's appearance. Hamming, Lanczos and sharpened requests use shared Pillow mechanics in
  `rendering/image_quality.py`; the QImage quality adapter also calls those mechanics.
- Opaque wallpaper sources resize as RGB, avoiding RGBA premultiply/unpremultiply passes. Authored transparency
  composites over black once before resampling; only the display-sized result becomes opaque RGBA for transport.
- FILL computes the original virtual scale and integer centre crop, but samples only the visible destination.
  A small halo preserves sharpening support. A tall portrait no longer allocates a full offscreen enlarged canvas.
- Large reductions use Pillow's integer reduction stage followed by the chosen filter (`reducing_gap=3.0`). This
  is a quality-preserving approximation, not a promise of bit identity to a full direct Lanczos convolution.
  Tests bound detail differences and ROI rounding, including sharpening and extreme aspects.
- The existing lower-priority speculative worker decodes once per source batch for all requested display sizes.
  All filters and sharpening participate. A batch has one resolved quality choice; mixed-quality batches reject
  before decode. Cache keys and response manifests include filter and sharpen identity.
- Existing count/byte bounds, foreground queue isolation, generation cancellation, native-copy ownership and
  shutdown retirement remain authoritative in `Docs/Contracts.md`. No new cache, worker role, timer or fallback
  is introduced. A failed selected filter is an error, never an implicit switch to Smooth.

## Bounded processing measurements

Measured on the development machine with installed Pillow, three samples per case, median wall time, source
decode + scale + final RGBA bytes. Baseline is `c13f1745`'s foreground implementation; these measurements exclude
prefetch/cache benefit, process startup, IPC and GUI publication. Concurrent operator work and small sample counts
make them indicative, not latency guarantees.

| Source / FILL target | Previous Lanczos | Optimized Lanczos | Hamming |
| --- | ---: | ---: | ---: |
| Reported 4014×2258 PNG → 3840×2160 | 291 ms | 255 ms | 194 ms |
| Same PNG → 2560×1440 | 282 ms | 194 ms | 153 ms |
| Same PNG → 512×288 | 224 ms | 151 ms | 139 ms |
| Synthetic 1200×4000 portrait JPEG → 1920×1080 | 239 ms | 68 ms | — |

The portrait previously resized 1920×6400 pixels before discarding most of them. The optimized path resizes the
visible 1920×1080 region. RGB resampling and bounded FILL work address processing cost separately from restoring
lookahead. Ordinary-use transition freshness still needs observation; these numbers do not establish loaded-desktop tails.

## Regression routes

`test_image_quality.py` compares visible FILL sampling to full-resize/crop, bounds severe-reduction detail error,
checks opaque decoding/file retirement and catches offscreen-sized allocations. `test_image_worker_prefetch_batch.py`
compares spawned batch bytes to foreground for all filters/sharpen combinations and checks one decode/batch bounds.
Transport tests reject mismatched quality manifests and reclaim mappings; pipeline tests isolate all six cache
identities. `test_resample_filter_settings.py` and `test_display_tab.py` cover migration and UI round trips.
The maintained image-worker lifecycle harness accepts explicit filter/sharpen and read-only source arguments;
commands live in `Docs/Reference/Harness_Index.md`. The reported source passed the real speculative-worker/parent
consumer path at 3840×2160 and 2560×1440 with Lanczos+sharpen and Hamming, including in-flight shutdown retirement.

Pillow's [filter comparison](https://pillow.readthedocs.io/en/stable/handbook/concepts.html#filters) explains the
quality/cost tradeoffs; its [resize API](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.resize)
documents the reduction stage. [scalepix](https://morgan3d.github.io/quadplay/tools/scalepix.html) documents HQ2x's
pixel-art use case.
