# SMP | Existing P2 worker and future P3 native-core integration seams

**Status:** implementation-facing supplement to `02_ShittyMusicPlayer_Implementation_Plan.md`, 9 Nov 2026; source baseline `9872ca18140c`. **No SMP `PlaybackService`, library workspace, decoded PCM source or `core/smp.py` product gate exists yet.** These are contracts and future integration points, not completed SMP functionality.

## 1. What already exists, and what must stay independent

- [x] The Windows Visualizer worker now owns **WASAPI loopback input**, DSP, simulation and logical cadence (`EngineSession` and `_SpotifyBeatEngine`), with device-staleness recovery. Its loopback mechanism does **not** decode audio files, own system-audio output, or provide exclusive WASAPI playback.
- [x] `core/application_services.py` establishes a process-level application service owner separate from display generations; it is designed to hold future library/queue/player services through Settings teardown. The actual SMP services and lease plumbing remain future work.
- [x] One canonical Visualizer/host binding exists. A second renderer or copied BeatEngine for the standalone player is prohibited.
- [x] `SpotifyVisualizerAudioWorker.set_capture_backend_factory()` and `RecordedCaptureBackend` demonstrate a pre-open PCM/capture seam. This factory **rejects replacing an active source**. It is not yet a production source-arbitration transaction and is not proof of gapless playback or latency accuracy.
- [ ] A real player, library repository, playback queue, decoder and output backend are still absent. The SMP milestone ladder in plan 02 remains applicable.

## 2. PCM analysis source seam (admit and implement with SMP M3)

- [ ] Define one `AudioAnalysisSource`/source descriptor at the existing capture/BeatEngine input boundary, with identity `(source_kind, source_generation, stream_identity)`, PCM format, timestamp domain, discontinuity/seek marker, playback/ramp state and monotonic sample position. Distinguish `external_system_loopback` from `internal_smp_decoded_pcm`; avoid metadata-only or arbitrary-payload selectors.
- [ ] One analysis source is selected at a time. SMP feeds its **already decoded** PCM directly to the Visualizer worker via a bounded newest-valid handoff; do not loop back SMP's speaker output and do not create a second FFT/BeatEngine/clock. External Media/Spotify remains independently selectable and can continue to use the existing loopback path.
- [ ] A change of source, player device, track or PCM generation is a **sequenced source transaction** at an engine boundary, not a new unsynchronised factory swap in an active audio capture lane. Stop/drain the old source, fence its callbacks and in-flight samples, reset the right floor/ramp/freshness state once and activate the new generation without stale frames crossing. Preserve modes/presets and authoring controls.
- [ ] The analysis worker and audio renderer must be able to park/retire independently of the player. Turning the Visualizer off cannot terminate a playing SMP track; opening Settings or moving/pop-out Visualizer cannot rewind or restart playback.
- [ ] Timestamp decoded PCM against **audible output**, not merely decode completion. Calibrate output latency and seek/discontinuity for visual accuracy. Maintain deterministic recorded-PCM parity with loopback where equivalent and a genuine audible-device check when an output backend exists.
- [ ] Maintain no per-frame Python GUI bridge, no second per-song FFT, no unbounded PCM buffering, no environment-flag selector and no duplicate app output capture. Cross-process message protocol must be CPython/OS-validated and not introduce descriptor leaks.

**When to exploit:** P2 C3 should preserve and document this seam now; P3 fixed native packet layouts should include source generation/clock metadata without tying schema to WASAPI. **Implement actual source selection and SMP PCM injection only alongside M3 playback** after the library and service authority exist. No placeholder playback engine today.

## 3. Playback output is a separate responsibility

- [ ] Begin SMP's actual player with the 02 plan's measured Qt Multimedia/FFmpeg trial; retain a backend abstraction if source formats, output quality, gapless behaviour or timing require native FFmpeg + dedicated WASAPI output.
- [ ] WASAPI **shared and exclusive output** is a distinct audio-output implementation from SRPSS's PyAudioWPatch **capture**. Do not infer bit-perfect exclusive playback, codec coverage or sample-accurate seeking from the loopback worker.
- [ ] One application-owned `PlaybackService` and `QueueController` live above display/Settings generations; output and queue survive disabling the Visualizer, selecting another external Media provider, and closing/moving the Library and Playlist panes.
- [ ] Internal SMP provider is typed separately from external GSMTC sessions. Outbound Windows SMTC publishing is not the existing inbound GSMTC reader, and SMP must never discover/control its own external session through a loop.
- [ ] Keep library indexing, audio decode, GUI/render thread, audio output and Visualizer simulation in deliberate owners; no high-priority audio callback blocking on Qt rendering or cross-process replies.

## 4. Native core and compositor seam

- [ ] SMP docked and pop-out Visualizers reuse the **one** native QRhi render core and packet ABI after P3, with one active rendering host, shared mode catalogue and one logical worker. The core is a general SRPSS custom-renderer, not owned by the screensaver product entry point.
- [ ] P3 additionally ports **transitions, image presenter and background custom nodes**, not just modes. This permits the MC/Standard display composer to run one QRhi backend and keeps SMP free to use its own native desktop host without a duplicate GL/Vulkan renderer.
- [ ] One Qt Quick backend per window; no raw-GL Visualizer in a Vulkan window. OpenGL remains a selectable QRhi backend after pixel-parity migration. Keep full UI material/Qt Quick controls on their existing owners; they are not reimplemented as custom draw calls.
- [ ] Keep a clean render-admission lifecycle for independent SMP desktop host and SRPSS/MC display windows: mapping quiescence before unmap, native reader ownership, no two frame acknowledgers, no second DSP clock. Closing the SMP pop-out must never retire application-owned playback.

## 5. Milestone/acceptance insertion into plan 02

- **M1/M2:** UI panes and indexed offline Library/Playlists first. Do not conflate existence of the app service tier with completed library leases/storage.
- **M3:** player output and queue; implement source descriptor/transaction and decoded PCM adapter at the *same time*; validate latency and device recovery with one active source and Visualizer-off playback. Source switching is not postponed to a later cosmetic phase.
- **M5:** typed internal Media adapter plus outbound SMTC, with independent external GSMTC selection and no self-feedback.
- **M7:** profile/desktop host reuses P3 QRhi core, native packet/renderer lifetime and SMP-owned service, avoiding an SMP-specific render pipeline.
- **M8/M9:** live Settings persistence, teardown and multi-process DB lifecycle; physical audio and frozen builds; no false completion from mocks.

**Acceptance:** recorded PCM produces the same logical state on the canonical mode as an equivalent reference stream, without duplicated analysis; the user hears uninterrupted playback through Settings/Visualizer shutdown, and UI state is truthful about selected source and output device. Every source-switch failure has a bounded, visible/logged outcome and does not steal Media keys from an external application.
