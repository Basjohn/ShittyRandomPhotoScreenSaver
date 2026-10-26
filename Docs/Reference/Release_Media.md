# Release / README animated media

`tools/release_media.py` owns release-only animated WebP generation. Output never enters product QRCs, persisted Settings,
the normal GODZIP, or runtime asset trees. Use a dedicated ignored `logs/<directory>` or an external release directory.

```powershell
python tools/release_media.py --list
python tools/release_media.py --kind transition --id jigsaw      # -> assets/webp/trans (the default for transitions)
python tools/release_media.py --kind visualizer --clip logs/visualizer_recordings/balanced.jsonl --start-seconds 5 --output-dir logs/release_media
```

Filter deliberately with `--kind`, `--id` and `--variant` using values returned by `--list`. `--duration-seconds` overrides
the capture interval (maximum 30 seconds); absent that override, transitions use their canonical authored duration and
Visualizer motion uses four seconds. Transitions add a 100 ms before/after endpoint hold, recorded separately from motion
duration and included in the manifest's total animation duration. No window, microphone/loopback device, product run, environment override, timer or realtime
cadence starts. The existing deterministic replay clock owns recorded-feature timing.

Transition identities come from `rendering.transition_registry`; unavailable identities are excluded. Frames go through
`tools.transition_contact_sheet.TransitionCapture`, production request parameter resolution and `QuickTransitionRenderHost`.
The same authored seed and deterministic fixture images are reused; lossless endpoint captures must exactly match those
photographs. There is currently no separate curated transition
preset catalogue. Canonical appearance is captured for every identity; Blinds' authored styles and Block Spins' edge-glass
options are additionally enumerated from their canonical option owners. This does not claim exhaustive surface-control
combinations or physical appearance approval.

**Transition showcase contract:** the implemented tool loads the genuine four Windows-local originals
`assets/usu/scenes/UsuScene1.png` through `UsuScene4.png`. Missing originals fail loudly; fixtures are never substituted
for published artwork. Each regeneration picks and records a scene pair and seeds, crops to 16:9 without stretching,
and captures A→B, a 700 ms rest, then B→A with a changed direction/order. Both loop ends hold A for 350 ms.
Capture at twice publication size; publish at **480×270, 24 fps, authored speed**, quality 92, encoder method 4 with
keyframes every 150 frames. About 10 MB is comfortable, not a cap; do not squeeze a good showcase to meet that number.
An explicit `--max-bytes` request admits the tool's bounded quality reduction and loud failure below its quality floor.
Scene pairs/seeds remain stable in the manifest for unchanged entries; random choice does not itself stale a capture.

Transition outputs default to ignored `assets/webp/trans/` and Visualizer outputs to `assets/webp/viz/` (operator layout 2026-10-17), both excluded from normal Godzips. Every new or reworked transition or Visualizer gets one rendered showcase WebP there (operator policy 2026-10-17). The agent reviews every new or
visually changed transition's WebP before closing that implementation. The accepted catalogue exclusions are Warp
Dissolve, Particle and Blinds Flat until the operator changes them; `catalogue()` filters these release-only cases
before listing or capture, without changing runtime availability. Landed transitions are accepted; catalogue generation
and capture endpoint proof do not reopen general product visual acceptance. Remaining execution lives in Current_Plan §3.
These transition publication rules do not change Visualizer capture/encoding rules below.

Visualizer identities come from the active canonical mode registry and each mode's actual curated preset catalogue;
Custom is excluded. The filename-derived variant survives sparse authored slots. The tool accepts only non-archived,
schema-2 operator recordings under `logs/visualizer_recordings`; synthetic fixtures and archived takes are rejected.
It replays the passage's pre-roll through the existing `ReplayBeatEngine`, production logical ticks, immutable capture,
mailbox and `QuickVisualizerPresentationSync`, then renders published snapshots through `QuickVisualizerRenderHost`.
The authored preset stays intact. The capture pins Scene3D High quality, draws on a plain dark grey
(`VISUALIZER_BACKGROUND`, operator 2026-10-17; no photograph behind the card), supplies the fixture photograph to
reflection-capable modes, and places the canonical presentation extent in a centered stage with room for 3D overflow.
The frames are then cropped to the union over the run of every pixel the mode drew (`content_box`, a 1% margin, even
dimensions), so no showcase carries empty space around its content and nothing a frame drew is cut.
This is a production-renderer showcase, not a full-desktop or mixed-refresh acceptance test.

Capture defaults to lossless 1280×720 PNG frames at 30 fps. WebPs start at 960×540, quality 92, loop forever, and carry no
EXIF/ICC/XMP metadata. The explicit encoding policy reduces fps and dimensions while retaining quality; each attempted
combination is recorded. A still image or an asset that exceeds the configured budget fails loudly without substituting
a renderer or lowering image quality. Temporary lossless frames are removed after encoding. Default budget is 10 MiB;
`--max-bytes` can choose a smaller review budget. GitHub currently allows at most 1000 assets per release, each under
2 GiB. The tool enforces the per-file ceiling and manifest asset count; publishing and admission alongside existing release
assets remain separate operations.
[GitHub release limits](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).

`release_media.json` maps `kind/identity/variant` to filename, curated source file, clip/hash/start, duration, dimensions,
fps, encoding attempts, asset hash and pre-capture Git revision/status/source-tree digest. The source digest includes JSON
settings/presets. Regeneration occurs only when capture inputs/source bytes differ or the output is missing/corrupt;
a commit alone does not stale unchanged source bytes. A source change conservatively stales the catalogue rather than
guessing dependency ownership. Source hashes are checked before each case and after capture/encoding; changes against
the catalogue's initial source or during capture fail loudly and discard the new artifact. Recorded input bytes are checked
again before publication too. Rerun at a stable checkpoint; there is no mixed-source fallback. Existing files without manifest ownership are refused. Successful entries are persisted
after each case; failures are printed and saved to `release_media_failures.json`, and the command exits nonzero.

Focused regression authority is `tests/test_release_media.py` and `tests/test_release_media_transition_loop.py`
(scene pairs stable and varied, 480 px wide at the composition's aspect, missing scenes refused, the loop's frame count, exact ends and rest): canonical enumeration, real WebP loop/duration/metadata,
quality-preserving size reduction, stale/corrupt output admission, recorded-clip restrictions and Extruded Spectrum's
registered production replay/snapshot path, endpoint-hold duration and discarding media when source changes. A bounded local offscreen sample proves artifact generation on the current
GPU; full selected release catalogue and visual review remain separate gates. In particular, promotion/authoring work can
change the active modes/presets after an earlier sample, so regenerate stale entries before release review.
