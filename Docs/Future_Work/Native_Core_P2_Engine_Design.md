# Native core P2: the out-of-process visualizer engine (design, 7 Nov 2026)

P2 of the [Graphics Backend Decision](Graphics_Backend_Decision_2026-11-05.md) addendum (option A): the Visualizer's
logical tick leaves the main process, so the GUI and render threads stop competing with it for the GIL. P1 (the native
toolchain) is [GO with conditions](Native_Core_P1_Spike.md); P2 needs none of P1's downloads and does not wait for them.
P3 (the native render core) reads P2's packets straight from shared memory, so P2 fixes the packet ABI P3 builds on.

## What runs where today (source audit, main c960d511 + 7 Nov)

| Stage | Owner (exact source) | Thread / process | GIL |
| --- | --- | --- | --- |
| Loopback capture + inline FFT | `widgets/spotify_visualizer/audio_worker.py` `SpotifyVisualizerAudioWorker` (`utils/audio_capture`) | capture callback thread, main process | callback and FFT bookkeeping take it; numpy releases it inside kernels |
| Capture -> DSP handoff | `utils/lockfree.TripleBuffer` (R-171: the freshest slot, never a queue) | in-process | none (index swap) |
| DSP, transient bus, energy bands | `widgets/spotify_visualizer/beat_engine.py` `_SpotifyBeatEngine` (a `QObject`; compute pool via `ThreadManager`), shared through `BeatEngineRegistry` | compute pool, main process | yes |
| Logical tick | `widgets/spotify_visualizer/logical_runtime.py` `VisualizerLogicalRuntime` (one non-Qt thread, authored cadence, parking) -> `tick_pipeline.logical_tick` -> per-mode frame runtimes (`*_frame_runtime.py`, `waveform_ribbon_dynamics`, `extruded_bubble_simulation`, ...) | logical thread, main process | **yes, the whole tick is pure Python**: the cost P2 moves |
| Frame | `render_state.VisualizerLogicalFrame` (immutable: identities, common state, one canonical mode frame, protected edges) -> render snapshot | logical thread | yes |
| Handoff to render | `render_bridge.VisualizerSnapshotBridge` (newest state replaces older unread state; protected edges coalesced by kind until the next sync consume) | publish on the logical thread, `take_for_render` at sync | yes |
| Draw | Quick render thread: Python `QSGRenderNode`s / raw GL per mode | render thread | yes (P3 removes it) |
| Workers | `core/process/supervisor.ProcessSupervisor` (mp queues, heartbeat, restart backoff, shared-memory accounting); the image worker hands RGBA through named shared memory with a one-byte attach ack (`core/process/shared_memory_transport.py`, the parent owns and unlinks every mapping) | separate processes | separate |

Consumers of the beat engine: the Visualizer owner and `engine/engine_lifecycle.py` only. Nothing else in the main
process needs the audio features, so the whole audio-to-frame chain can move.

## The cut: capture, DSP and tick in one engine worker; the main process only reads frames

One `WorkerType.VISUALIZER` process per runtime generation (only one Visualizer runs at a time) owns: loopback
capture, the triple buffer, the beat engine's DSP, the logical runtime and the mode frame runtimes. The main process
keeps the Visualizer owner, the takeover/activation state machine, the bridge, presentation and drawing.

Staged so each step is measurable and reversible:
1. **P2a, tick out, audio stays.** The main process keeps capture + DSP and forwards each post-DSP input to the
   worker; the worker runs the tick. The input already has a deterministic schema for six modes
   (`feature_frame.py`, schema 1/2, the replay format); Waveform Ribbon and Extruded Bubble get the same treatment from
   their recorded-input shapes (`ui/studio/*_recorded_inputs.py`, `logs/visualizer_recordings` JSONL). This moves the
   costly part (the pure-Python tick) and leaves the capture path, the most timing-sensitive code, untouched.
2. **P2b, audio out.** Capture and DSP move into the worker; the main process forwards only control (below). Taken
   only if P2a's measurement shows the capture/DSP share of the main process's GIL still matters.

## The frame packet ABI (shared memory; C-readable for P3)

One named mapping per generation, created and owned by the main process (the image worker's ownership rule: the parent
creates, holds and unlinks; Windows drops a mapping with its last handle), opened by the worker by name.

```
header (64 bytes, little-endian, fixed):
  u32 magic 'SRVZ'   u16 abi_version   u16 header_bytes
  u32 runtime_generation   u32 engine_generation   u32 activation_id
  u32 slot_count (3)   u32 slot_bytes   u64 latest_sequence   u8 mode_code   pad
slot[i] (slot_bytes each):
  u64 sequence_begin   (seqlock: odd while the writer fills the slot)
  u32 payload_bytes    u32 payload_schema (per mode, versioned)
  f64 logical_timestamp   f64 source_timestamp (NaN = none)
  u32 flags (changed, present_frame, mode_reveal_ready, playing)
  u32 protected_edge_mask   (coalesced edge kinds since the last sync consume)
  payload ...           (fixed-width fields, then float32/u8 blocks at 16-byte alignment)
  u64 sequence_end     (equal to sequence_begin when the slot is whole)
```

- **Writer (worker):** picks the slot that is neither the newest nor being read, bumps `sequence_begin` to odd,
  writes, sets `sequence_end`, publishes `latest_sequence`. Never blocks on the reader.
- **Reader (main, at sync):** reads `latest_sequence`, copies the slot, accepts it only if `sequence_begin ==
  sequence_end ==` an even value at or after the last accepted one; otherwise keeps the previous frame (newest-state
  semantics, the bridge's own: never a queue, never catch-up replay).
- **Protected edges** (`VisualizerProtectedEdge`) must survive a skipped frame: the writer ORs edge kinds into the
  next slot until the reader acknowledges a sequence through a small reader-owned field (`u64 consumed_sequence`).
- **Per-mode payload codecs** live next to each canonical mode frame in `render_state.py`: `encode(frame) -> bytes`
  and `decode(bytes) -> frame`, with `decode(encode(f)) == f` exactly (floats stored at the width the frame holds;
  Waveform's `RibbonPacket` is already bytes). The main process decodes back to today's dataclasses, so presentation
  and drawing do not change in P2; P3's native core reads the same bytes without Python.
- `abi_version` bumps on any layout change; reader and writer refuse a mismatch (fail closed, logged once).

## Control: main -> worker (rare, latest wins, sequenced)

A duplex pipe (the supervisor's message queue) carries only edges, never per-frame data: versioned Settings snapshots
(the canonical spec systems' resolved values, `visualizer_mode_settings` / mode parameters), mode/preset activation
(with `activation_id`), playing state (Media's playback gate), display power park/unpark, the framed view inputs the
tick reads (Waveform's `view_span`/`view_top`, expanded display, edit orbit), and stop. Each message carries the
generation and a sequence; the worker applies the newest of each kind at its next tick boundary. A tick that today reads
a GUI-thread attribute directly reads the last applied control value instead: the replay identity tests already feed
those values per tick, so they define the equivalence.

## Lifecycle

- The worker starts with its runtime generation (the owner's `start`) and is joined at `retire`; parking stops its
  cadence, as `VisualizerLogicalRuntime` parks today (no wake cadence while parked).
- One Visualizer at a time: a mode switch is a control message inside the same worker, never a new process.
- A worker crash is fail-closed: the bridge closes admission, the Visualizer fades (never vanishes), the supervisor
  restarts it once with the current Settings snapshot and activation; repeated crashes leave the Visualizer faded and
  logged, never a black or frozen display.
- Dormancy (binding): with the Visualizer disabled no worker exists; `tools/overhead_baseline.py` stays identical.
- Frozen builds: the image worker already runs under Nuitka through `ProcessSupervisor`; the engine worker uses the same
  spawn path (its imports must not pull QtGui/QtQuick: QtCore only, or none).

## Gates (from the Decision; nothing ships without them)

1. **Identity:** byte-identical packets on all recordings x all modes, worker against in-process (the existing replay
   paths: feature replay for the six feature-frame modes, `waveform_fidelity_frames` / the Studio recorded inputs for
   Waveform Ribbon and Extruded Bubble). The codec round-trip test runs per mode on every canonical frame type.
2. **No visual change:** the existing pixel oracles and BTF checks unchanged (P2 changes no drawing).
3. **Gain:** GIL share and frame age before/after in ONE game60 run of at most 10 minutes, only after the operator's
   yes (lead only); `--usage`/PERF instrumentation, compared against the stored baselines.
4. **Dormancy and lifecycle:** overhead baseline identical with the Visualizer off; no process, mapping or handle growth
   over 20 Settings open/close and 20 mode switches; worker retired with its generation.

## Measured (8 Nov, work orders 1-2 landed)

`core/visualizer_engine/packet_abi.py` (the ABI above) and `core/visualizer_engine/frame_codec.py`: one exact tagged
codec for the whole canonical frame tree (the render-state frames plus Waveform's `RibbonPacket`/scene `Recipe`/ribbon
style and Extruded Bubble's `DriftFamily`, with numpy arrays and read-only mappings), a stable versioned type table,
packed float64 tuples, and decode without re-validation. Every frame the production owner publishes for every mode on a
shipped clip round-trips to the identical `repr` and re-encodes to the identical bytes
(`tests/test_visualizer_engine_frame_codec.py`). Payload and cost per frame (2 s of `growing_pains`, p50):

| Mode | payload | encode (worker) | decode (main) |
| --- | --- | --- | --- |
| Spectrum / Extruded Spectrum / Sphere | 2.5-2.9 KiB | .07-.10 ms | .09-.14 ms |
| Spline Curve / Bubble | 7-17 KiB | .19-.22 ms | .16-.26 ms |
| Oscilloscope / Neon Lake | 49-107 KiB | .08-.25 ms | .07-.25 ms (p90 .39) |
| Waveform Ribbon | 342 KiB | .34 ms | .26 ms (p90 .34) |
| Extruded Bubble | 610-617 KiB | .50 ms | .34 ms (p90 .39) |

So the main process pays at most about .4 ms and one slot copy per presented frame, against the whole tick it stops
running; 1 MiB slots (3 MiB per generation) hold every mode, so a mode switch never remaps.

## Work order

1. ABI module (`core/visualizer_engine/packet_abi.py`): header, slots, seqlock writer/reader, edge mask; pure tests
   (torn-write detection, newest-state, edge survival across skipped frames, version refusal).
2. Per-mode codecs with round-trip tests on every canonical frame (all seven mode frames).
3. In-process loopback: the current logical thread publishes through the ABI and the owner reads it back (no worker
   yet), proving the codecs and the reader on live code with identical replay digests. **Done 8 Nov:**
   `core/visualizer_engine/packet_mailbox.py` `PacketMailbox`, a drop-in for `LatestStateMailbox` (the controller's
   `replace_logical_mailbox` seam) whose slot is the ABI's newest whole frame: frames are encoded with
   (generation, activation, produced time) into the writer, read, decoded and acknowledged by the reader; protected
   edges carry into the newest unread frame until acknowledged (`FramePacketWriter.consumed_sequence`); one wake per
   empty -> populated edge. With it the production owner hands the renderer the identical frames for all modes on a
   shipped clip (digests of the snapshots it publishes to the bridge; a 1 ns change to a decoded frame fails it).
   Production still uses the in-process mailbox; the worker (4) takes the writer side out of the process.
4. The worker (`WorkerType.VISUALIZER`): tick + mode runtimes behind the control channel, fed post-DSP inputs (P2a);
   identity gate on all recordings x all modes. **First slice done 8 Nov:** `core/visualizer_engine/engine_worker.py`.
   `EngineSession` hosts one activation (the runtime controller and tick state configured from Settings, a post-DSP
   input engine, the mailbox's writer side attached to the main process's mapping by name); `VisualizerEngineWorker`
   runs it as `WorkerType.VISUALIZER` under `ProcessSupervisor` (`VIS_CONFIGURE` / `VIS_INPUT` / `VIS_STOP`). Fed the
   recorded post-DSP inputs (`FeatureFrame`, the live engine's own recording schema), the worker ticks frames
   identical to the production owner's in-process tick for all nine modes, in process and across processes
   (`tests/test_visualizer_engine_worker.py`; a different runtime generation fails it). Found and fixed on the way:
   Spline Curve's logical colours were `QColor`s (now the `(r, g, b, a)` tuple the frame always froze them to) and
   Neon Lake's terrain baker imported a Settings widget for a pure helper (now `utils/curve_nodes.py`). The runtime
   generation is a control input (every frame carries it). Gate on every recording: `tools/visualizer_replay/
   engine_worker_gate.py` (each recording's first seconds x every mode, in-process vs worker, at below-normal
   priority; report under `.artifacts/evidence/architecture/native_core_p2/`).
   **Live inputs (decided 8 Nov, not built):** `FeatureFrame` is the replay contract, not the live one. The recorder's
   capture (`tools/visualizer_replay/record.py` `_frame`) clamps lanes to 0..1, resamples bars and waveform to fixed
   counts and consumes scheduler events, so a forwarded `FeatureFrame` would not reproduce the in-process live tick.
   P2a forwards a lossless engine snapshot instead: per tick, exactly the values the tick reads from the beat engine
   (the getters `ReplayBeatEngine` overrides: pre-AGC / bubble / EB body / Waveform body / transient / live bands,
   musical level, intensity, onset events after a serial, analysis spectrum, typed scheduler events, waveform and
   capture history when demanded, playback state), unclamped and unresampled, with the worker's engine answering
   from it. Its gate: the live engine's getter values equal the worker engine's for the same snapshot, then the
   frames equal the in-process tick on recorded PCM through production DSP (`ProductionLaneEngine`).
5. Lifecycle: generation start/retire, park, crash fail-closed, frozen spawn check (operator), dormancy baseline.
6. Measurement (gate 3), then decide P2b.

## Risks

- **Import weight in the worker:** the tick modules import Qt (`QObject` in the beat engine, settings helpers). The
  worker must import QtCore at most; P2a keeps the beat engine in the main process, so the first worker imports only the
  tick and mode runtimes. Measured 8 Nov: the logical runtime, the tick pipeline, render state, the ABI, the codec and
  all eight mode frame runtimes import QtCore only (no QtGui/QtQml/QtQuick); about 0.9-1.1 s cold and ~350 modules
  each. `tests/test_visualizer_engine_import_weight.py` pins it.
- **The tick still reads presentation config (8 Nov):** the logical capture reads Spectrum's decoration fades and
  colours and the Oscilloscope/Bubble spec parameters from the presentation state, so the worker configures both
  sides and loads QtGui for `QColor` (never Quick, QML or Widgets; pinned by a fresh-spawn test). Move those reads into
  the logical config before production wiring, so the worker imports QtCore only.
- **Process-unique labels across worker generations (8 Nov, resolved):** Extruded Bubble numbers its drift families
  from a process-wide counter that the renderer uses as a geometry cache identity. Every `EngineSession` takes a
  `label_namespace` from the main process (>= 1 in production, a monotonic counter never repeated across sessions or
  restarted workers) and numbers from `namespace << 32`; the main process's own counter stays far below, and
  namespace 0 keeps the in-process numbering for the identity gates. Production wiring must pass a fresh namespace on
  every `VIS_CONFIGURE` (`tests/test_visualizer_engine_worker.py`).
- **The GUI wake (8 Nov, resolved):** in process the mailbox wakes the GUI on its empty -> populated edge. Across
  processes the writer sends one byte down a `multiprocessing.Pipe` on exactly that edge (handed to the worker in
  `VIS_CONFIGURE` as `wake`); the reader's `listen_for_wakes` thread blocks on the pipe and runs the same wake callback
  (the owner's thread-safe emitter). Never a poll; closing the mailbox ends the thread
  (`tests/test_visualizer_engine_worker.py`: one byte per edge; three worker frames taken by wake across processes).
- **Hidden GUI-thread reads inside the tick:** every attribute the tick reads from the owner/widget must become a
  control input. The audit for step 4 lists them from `logical_tick`'s reads; a missed one shows up as an identity
  failure, not silently.
- **Two copies of state during a switch:** the main process must never keep a stale tick-side copy; one owner of each
  piece of state, the worker for logical state.
- **Memory:** a second Python with numpy (tens of MB); recorded in the dormancy/usage receipts.
- **Latency:** at most one tick of extra control latency (applied at the next boundary) and one memcpy per frame on the
  read; frame age is measured at gate 3.
