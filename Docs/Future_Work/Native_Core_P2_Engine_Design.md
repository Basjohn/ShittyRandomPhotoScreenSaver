# Native core P2: the out-of-process visualizer engine (design, 7 Nov 2026)

P2 of the [Graphics Backend Decision](Graphics_Backend_Decision_2026-11-05.md) addendum (option A): the Visualizer's
logical tick leaves the main process, so the GUI and render threads stop competing with it for the GIL. P1 (the native
toolchain) is [GO with conditions](Native_Core_P1_Spike.md); P2 needs none of P1's downloads and does not wait for them.
P3 (the native render core) reads P2's packets straight from shared memory, so P2 fixes the packet ABI P3 builds on.
Audited 8 Nov: [Native_Core_P2_Audit.md](Native_Core_P2_Audit.md) (two open critical findings in the cross-process
wake and the seqlock reader, the gates' coverage, the main-process cost of the snapshot path, work order 5's gaps).

## What runs where today (source audit, main e885f896 + 7 Nov)

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
  u32 slot_count (3)   u32 slot_bytes   u32 mode_code
  u64 latest_sequence (writer)   u64 consumed_sequence (reader-owned acknowledgement)   pad to 64
slot[i] (slot_bytes each):
  u64 sequence_begin   (seqlock: odd while the writer fills the slot)
  u32 payload_bytes    u32 payload_schema (per mode, versioned)
  f64 logical_timestamp   f64 source_timestamp (NaN = none)
  u32 flags (changed, present_frame, mode_reveal_ready, playing)
  u32 protected_edge_mask   (coalesced edge kinds since the last sync consume)
  u32 runtime_generation   u32 engine_generation   u32 activation_id   u32 mode_code   (ABI 2: the slot's identity)
  payload ...  (at 64: fixed-width fields, then float32/u8 blocks at 16-byte alignment)
  u64 sequence_end     (equal to sequence_begin when the slot is whole)
```

**ABI 2 (P2b slice 2, 8 Nov; audits H5 and A3-M4):** an in-place mode switch changes engine generation, activation
and mode while the mapping stays, and the header is not under any seqlock, so each slot carries its frame's identity
in its head (covered by the slot's seqlock; payload moved from 48 to 64) and a native reader validates every slot it
accepts without Python. The header's identity fields are the configure-time identity (written once by the session
before any frame) and never decide a slot. `mode_code` is `packet_abi.MODE_CODES` (append-only, 0 = none). The
writer fills `flags` and `source_timestamp` from the publication on every publish.

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
   over 20 Settings open/close and 20 mode switches; worker retired with its generation. **Passed 8 Nov** (the Gate 4
   record under work order 6; it found and fixed R-178 first).

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

So the main process pays at most about .4 ms and one slot copy per presented frame for the *frame read*; with live
inputs as engine snapshots it also pays the capture (.20-.25 ms p50) and pickle (.06-.09 ms) per tick, which for
Spectrum, Oscilloscope, Sphere and Extruded Spectrum (ticks of .33-.45 ms) is more than the tick it stops running
(audit, H1: measure per mode before work order 5). 1 MiB slots (3 MiB per generation) hold every mode, so a mode
switch never remaps.

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
   priority; report under `.artifacts/evidence/architecture/native_core_p2/`). **Result (8 Nov, 20 s per recording):**
   all 160 replayable (recording, mode) pairs identical, 291,024 frames, 19 recordings x 9 modes; Waveform Ribbon is
   skipped on the 11 recordings without native PCM (it replays only from PCM, in process too). Report:
   `.artifacts/evidence/architecture/native_core_p2/20261108_worker_gate/report_rerun.json` (re-run after the audit's
   C1/C2 fixes with the current script: 160 pairs, 291,024 frames, 0 mismatching, exit 0, 34 min at below-normal
   priority). The first `report.json` predates the skip and records the 11 rows as errors (audit M4).
   **Live inputs: the lossless engine snapshot (built 8 Nov; deleted in work order 5 slice 5.6, when P2b's live input,
   the worker owning capture, DSP and the tick, had replaced it; kept here as the record):** `FeatureFrame` is the replay contract, not the live
   one: the recorder's capture (`tools/visualizer_replay/record.py` `_frame`) clamps lanes to 0..1, resamples bars and
   waveform to fixed counts and consumes scheduler events. `core/visualizer_engine/engine_snapshot.py` instead:
   - The main process keeps the beat engine. Per tick, `EngineSnapshotSource.capture` steps it (`engine.tick()`, which
     the tick itself calls first) and captures every value the tick can read, unclamped and unresampled
     (`CAPTURED_GETTERS`, the read surface `tools/visualizer_replay/engine_read_audit.py` measured: every mode calls the
     generation/activation ids, energy bands, smoothed bars, transient bands, floor snapshot, waveform count, latest
     authoritative frame and generation-with-frame/-waveform; per mode the pre-AGC / bubble / EB body / Waveform body /
     live bands, musical level and intensity, onsets, analysis spectrum, scheduler, waveform, capture history and its
     rate, the ramp flag), plus every onset and, in order, every feed to and reset of the engine's event scheduler
     since the previous snapshot (tapped from the compute pool under a lock).
   - The worker's `SnapshotBeatEngine` answers from the newest snapshot and replays the feeds into its own scheduler.
     The scheduler's debounce depends only on what it was fed, so the tick consumes the same events from it,
     consume-once, as in process. DSP configuration is the main process's: the worker's setters are no-ops; a read or
     write outside the contract raises `SnapshotContractError`, a `BaseException`, so the tick's defensive
     `except Exception` blocks can never turn a missing capture into a silent fallback (audit H3). A static scan of the
     Visualizer package pins every engine read against `CAPTURED_GETTERS` (it found the fence's
     `get_authoritative_frame_commit_seq`, now captured).
   - Capture is side-effect free. `is_reactivity_play_ramping` is a pure read of the ramp clock (the latch a ramped
     getter clears on expiry no longer decides it; its one reader, Extruded Bubble, reads a ramped getter first, so in
     process nothing changes). The analysis spectrum is peeked (`peek_pre_agc_analysis_spectrum`).
   - No tick -> engine write crosses back. The waveform history and idle waveform demands
     (`consumes_waveform_samples`) and the spectrum request (`reads_analysis_spectrum`: Sphere, Oscilloscope, Neon
     Lake) are rules of the mode; the main process applies them before each step (`request_pre_agc_analysis_spectrum`
     before `engine.tick()`), and the worker's tick must agree (a disagreement raises). The first design returned the
     spectrum request as a back-edge, one tick late and racy against the compute commit (audit H4).
   - Live sessions pin only the authored clock to the snapshot's timestamp; `time.*` and `random` stay the worker's
     own (audit H6). Bubble's spawn draws from the process RNG by design, so `seed` is a control input: the gates pass
     the replay seed, production none (since 5.6 the seed reaches Bubble's own generator, never the process RNG). A
     tick that raised closes its session (`session_closed`, audit M2; on the live input since 5.6).
   - `EngineSession(inputs="snapshot", initial_snapshot=...)` ticks snapshots (`tick_snapshot` -> revision;
     `VIS_INPUT {"snapshot": ...}` across processes); `inputs="lanes"` is the in-process reference on production DSP
     (`ProductionLaneEngine`).
   Gate (`tests/test_visualizer_engine_snapshot.py`): the snapshot path ticks frames identical to the in-process tick
   on production DSP for all nine modes, in process and in a `WorkerType.VISUALIZER` process. Mutations caught: no
   scheduler replay (Bubble), no onsets (Extruded Bubble), no spectrum (Sphere), the main side declaring no samples
   (Oscilloscope).
   **Independent audit (8 Nov, `Native_Core_P2_Audit.md`):** fixed the same day: C1 (wake: one byte per publish across
   processes; a free-running writer stranded the reader after frame 7 on the old edge rule), C2 (seqlock read order:
   `sequence_end` first, `sequence_begin` last; an interleaved overwrite was accepted torn), H3a, H4, H6, M2. Open:
   4b, 4c and 5 below.
4P. **P2b (decided 8 Nov, 4c): the worker owns audio capture, DSP and the tick.** The main process keeps no beat
   engine on the product path; it sends control edges and takes frames.
   - **Worker side:** `WorkerType.VISUALIZER` hosts the production `_SpotifyBeatEngine` with its
     `SpotifyVisualizerAudioWorker` (loopback capture through `utils/audio_capture.py`: pyaudiowpatch WASAPI on
     Windows, sounddevice / Pulse monitor elsewhere), its own `ThreadManager` (the capture lane and the compute pool
     the engine requires, `beat_engine.py:252-272`), and the logical runtime's cadence (the worker paces its own
     ticks; the main process no longer drives them). Frames go out through the existing `PacketMailbox` writer and
     wake; everything below the engine (ABI, codec, mailbox, wake, `EngineSession`'s controller and mode runtimes) is
     reused unchanged.
   - **Control edges (main -> worker), from the owner's engine calls today** (`quick_display_visualizer_owner.py`):
     display power (`acquire` / `ensure_started` / `release`, `set_display_power` ~251), playing (`set_playback_state`
     and `wake`, `set_playing` ~594; it also reads the private `_play_ramp_start_ts`, which becomes a field of the
     frame or the reply), mode activation (`begin_activation_transaction` / `end_activation_transaction`,
     `_activate_pending_mode` ~1578), start/retire (`set_runtime_generation`, `acquire` / `release`, `start` ~1766,
     `retire` ~1845), configuration (`_apply_configuration` ~389: the DSP technical config and the logical config,
     as a resolved-settings delta applied at a tick boundary, never a rebuild), plus the framed view inputs and park.
     `visualizer_host_binding.py:468` reads the engine's generation/activation at bind: they come back in the
     configure reply and in every frame.
   - **What the main process still needs from the engine:** only what frames carry (identities, playing,
     readiness). Anything else the owner or Settings reads from the live engine today must be found and turned into
     a frame field or a reply (inventory first, as 4's read audit did).
   - **Not affected:** the Studios and offline replays keep their in-process replay engines
     (`ui/studio/*`, `feature_replay`); only the product path moves.
   - **Capture device ownership:** one process owns the loopback device; the worker opens it after `VIS_CONFIGURE`
     and closes it on park/retire/stop, so a restarted worker never collides with a dying one (the supervisor waits
     for the old process's exit before starting capture in the new one). A capture failure is reported like a crash
     (fail closed, fade, reconfigure once).
   - **Gates:** (1) identity: the worker's production DSP on recorded PCM (`inputs="lanes"`, already built) equals the
     in-process owner; (2) 4b's live-engine gate: `_SpotifyBeatEngine` with the real audio worker fed PCM blocks
     offline through the capture callback, in process vs in the worker; (3) gate 3 with the main process's GIL time
     before/after.
   - **Also required (checkpoint audit 2, A2-M5):** Media's playback truth against the worker's own silence/ramp
     detection (one owner of "playing"); audio device changes and COM initialisation on the worker's capture
     thread; the usage sampler counting a long-lived child; worker logging into the app's log; where the frame
     decode runs (render-thread latency above); wake-pipe backpressure (a full pipe must never block the worker's
     tick: drop the byte, the reader coalesces anyway); Bubble's spawn on its own generator, so the gates need no
     process-wide seed (A2-M2; done in 5.6); the main-process listener thread's wake cost counted in gate 3.
   - **Deleted when P2b lands (done in work order 5 slice 5.6):** `core/visualizer_engine/engine_snapshot.py`, the
     `snapshot` session input and its tests and tools (`engine_main_cost.py` stays as the record of the decision: its
     in-process half still runs; the snapshot half is reproducible at 4df640b7).
   - **Slice 1 built (8 Nov): the live engine on recorded PCM, in process and in the worker** (the rig every P2b gate
     uses; gate (2)'s steady-state half). `EngineSession(inputs="live")` builds the production `_SpotifyBeatEngine`
     with its real `SpotifyVisualizerAudioWorker` on the session's own `ThreadManager` (the capture affinity lane and
     the compute lane: QtCore only), configured as every session is, then as the owner's `start` does: thread
     manager, `acquire`, the mode's sample demands (mode rules, declared before the first block); capture opens at
     the first input's play edge (`set_playback_state(True)` + `ensure_started`, the ramp starts on that input's clock).
     - *Source seam:* `SpotifyVisualizerAudioWorker.set_capture_backend_factory` (`audio_worker.py:364`; delegated
       by `_SpotifyBeatEngine.set_capture_backend_factory`): None (production) opens the device through
       `create_audio_capture`, looked up when capture opens; a factory is installed once, before capture opens
       (refused while capture is active). The capture lane's drain calls it (`audio_worker.py:858, 878`).
       `core/visualizer_engine/recorded_capture.py`: `RecordedCaptureBackend` (no device, no thread; `start` keeps
       the worker's callback, `push(block)` delivers one block through it as identical stereo channels) and
       `CaptureHistoryStream` (each `FeatureFrame`'s capture history back into the samples its publication added,
       by exact alignment, cut into device blocks of the negotiated size, the newest whole). The live-audio tool
       shares its alignment helper.
     - *Commit edge:* `_SpotifyBeatEngine.set_analysis_settled_observer` (None in production: one attribute read per
       analysis) is called on the compute lane at the end of `_accept_analysis_lane_result` (`beat_engine.py:1032`)
       once the result is committed or rejected and the slot is free with nothing pending
       (`has_analysis_in_flight`). Per input the session pushes the new blocks, steps the engine (it consumes the
       newest block and submits it to the compute lane), waits on that edge (bounded, fail closed; never a sleep or
       poll), then ticks: the asynchronous commit path runs on its own thread and the frames are deterministic. The
       tick's own `engine.tick()` then finds no new block (a no-op step on the same clock).
     - *Not yet (slice 1):* a paused input raised (slice 2 adds pause/resume with its capture-lane edge); the rig pins
       the authored clock and passes the replay seed as the other gates do (A2-M2).
     - *Found and fixed:* the Spectrum DSP (`bar_computation.fft_to_bars`) imported its curve helper from the Settings
       shape editor, loading QtWidgets into any process that analyses (now `utils/curve_nodes`; the fresh-spawn probe
       ticks one live input per mode and pins QtCore/QtGui).
     - *Gate:* `tests/test_visualizer_engine_live.py` (every mode, 1 s of the shipped clip, in process == worker; the
       recorded stream rebuilds every history; each tick reads the commit of its own block, committed off-thread; a
       device open fails the tests). Whole clips: `tools/visualizer_replay/live_engine_gate.py`. **Result (8 Nov):**
       all three shipped clips whole x nine modes, 27 pairs, 31,644 frames, 0 mismatching, 5 min at below-normal
       priority (`.artifacts/evidence/architecture/native_core_p2/20261108_live_gate/live_gate.json`).
     - *Live engine vs `ProductionLaneEngine` (reported, not gated; same report):* no lag on any mode (the overall
       energy aligns best at 0 ticks) and means within .002. Spectrum, Extruded Spectrum and Neon Lake differ from
       the first frame (bars .006-.009 mean absolute): the lanes engine analyses each new block twice for shaped modes
       (A2-H2) and serves the recorded raw bars elsewhere. Sphere differs from frame 1 (the live engine publishes the
       analysis spectrum one commit after the tick requests it; the lanes engine every frame, H4). Bubble differs on
       every frame and Oscilloscope from frame 1 with identical or near-identical common energy, and Spline Curve,
       Extruded Bubble and Waveform Ribbon match for long stretches (185-882 frames per clip) and then part: in their
       mode state, not the common lanes (cause not isolated; the lanes engine's renumbered onsets, its replayed
       scheduler and recorded waveform are the known differences). The live engine is the reference from here on;
       the lanes engine stays the Studios' replay.
     - *Cost:* 4c, "Live engine measured".
   - **Slice 2 built (8 Nov): off the steady state, and checkpoint audit 3's rig items** (4b, audit H3; A3-M4, A3-H1,
     A3-M1, A3-L1, A3-L2). Every control edge runs the production owner's engine calls on the logical side (as built,
     hand copies of them; the owner's own code since the follow-ups below, A4-H1) and ends on a real completion edge
     (never a sleep or poll):
     - *Capture-lane completion edge:* `SpotifyVisualizerAudioWorker.fence_capture_transactions(callback)` (delegated
       by the engine; nothing in production calls it) submits `callback` behind every capture start/stop/restart
       admitted so far on the serial capture lane; `EngineSession._settle_capture` waits on it after every edge and
       fails closed if capture is not open when it should be. `RecordedCaptureBackend` re-negotiates on restart.
     - *Pause/resume:* paused inputs tick the engine's paused path (`_update_idle_waveform` /
       `_mark_idle_waveform_generation`, `_prime_idle_bars`, the warm-capture grace and its expiry, which stops
       capture on the authored clock; the idle self-animating reveal in the tick). The play edge is the owner's
       `set_playing` (~594-617): `wake` (restarts a stale capture, starts a stopped one), `set_playback_state` (ramp
       restart unless capture stayed warm; pause schedules the keepalive stop), and on resume
       `arm_reentry_fresh_frame_fence` on the engine's commit sequence; the first input runs the owner's `start`
       (~1774-1783). A paused input carrying a new capture publication fails closed. Gate clips:
       `recorded_capture.synthesise_pause` (paused ticks and two resume ticks carry the last playing frame's capture
       history, as the recorder would record them; the rest of the clip follows shifted: playback resumes where it
       paused).
     - *Warm re-entry:* resume (above) and display power, `EngineSession.set_display_power` / `VIS_SET_DISPLAY_POWER`
       (the owner's `set_display_power` ~239-285 on the logical side: park releases the capture reference and no
       input ticks while parked; unpark re-acquires, reopens capture when playing, arms the fence and rebases the
       logical clocks; the owner's reader-side mailbox clear stays the main process's). The re-entry ticks that carry
       no new capture are held (`present_frame` false, the watermark the retained frame's commit sequence); the tick
       after the first post-re-entry commit is presented; with the arm disabled the retained frame is presented at
       once (`tests/test_visualizer_engine_live_off_steady.py`).
     - *In-session mode switch:* `EngineSession.request_mode` / `VIS_SET_MODE` (`{"mode", "preset"?, "settings"?}`,
       validated on receipt, applied at the next tick boundary, the newest request wins): the owner's activation
       commit on the existing controller and engine (one activation transaction around mode, settings, technical
       config, engine kwargs, the target's logical mode state, the fence, the compute / smoothing / floor reset; then
       the fresh-frame fence on the committed generation and activation and render admission). Same engine, capture
       source and mailbox; a block-size change restarts capture on its lane first. (Built as a hand copy,
       `feature_replay.switch_offline_controller_mode`; since the slice 2 follow-ups below it is the owner's own code,
       `logical_edges.commit_logical_activation`.)
     - *Production commit order (A3-H1):* `EngineSession(order=...)`. `production` (default; the reference for these
       gates): the tick's own engine step consumes the newest block and submits its analysis, and the tick reads the
       previous commit, as live; the analysis is held at `_SpotifyBeatEngine.set_analysis_admission_gate` (called on
       the compute lane before each analysis; None in production, one attribute read) until the tick returns, then
       the session waits for it to settle. An adversarial schedule (each step gives its analysis 50 ms to commit
       before the read) fails without the gate. `settled` (slice 1) stays the portability gate; `free` (no hold, no
       wait) is the stress order.
     - *Slot identity and flags, ABI 2 (H5, A3-M4):* see "The frame packet ABI" above; read back with plain `struct`
       in the tests (header, every slot's flags and identity equal to the frame it holds, changing across a switch,
       the header staying the configure-time identity).
     - *Spectrum at activation (A3-M1): withdrawn (8 Nov).* A mode-rule spectrum demand closed the commit-long gap
       after an activation, but changed Sphere's production frames for the whole session (audit 4 A4-M1 as a
       standing demand; audit 5 A5-M1 still 359/364 frames as a one-shot request: the first spectrum stays in Sphere's
       integrators). Sphere is accepted, so production keeps its pre-slice-2 behaviour exactly: the tick's own read
       requests each publication; `declare_mode_engine_demands` declares only the waveform demands.
     - *Device refusal in any process (A3-L1):* a recorded-PCM session refuses the device for its life; the worker's
       configure reply reports `device_refused` and every gate asserts it. (Built as a process-wide swap of
       `audio_worker.create_audio_capture`; per engine since the follow-ups below, A4-L3.)
     - *Block size and the stale restart (A3-L2):* the recorded backend reports 0 on Auto, as pyaudiowpatch and
       sounddevice do (it delivers a 10 ms period). `wake`'s stale check reads the wall clock (0.5 s), so whether a
       warm resume restarts capture depends on how long the rig took: the gate's warm resumes restarted in 9 of 27
       runs in process. Forced both ways on Oscilloscope (history-drawing) the restart runs on the lane before the
       next block and the frames are identical (test), so the gate does not depend on it; it does not make every
       warm resume take the restart path.
     - *Gate:* `tests/test_visualizer_engine_live_off_steady.py` (mutation-checked: removing the paused path, either
       fence arm, the switch, the slot identity, the flags, the device refusal, the admission hold, the paused-input
       check, the play edges or the capture-lane wait each fails its test). Whole clips:
       `tools/visualizer_replay/live_engine_gate.py` (scenarios `steady`, `pause_warm` 2 s, `pause_cold` 7 s past the
       6 s grace, `reentry` 1 s park, `switch` per pair with a paused switch-back; `--stress`). **Result (8 Nov,
       production order):** all three shipped clips whole, 126 pairs (steady, both pauses and re-entry x nine modes;
       switch x six pairs incl. Spectrum <-> Extruded Bubble both ways), 170,622 frames, frames and slot heads
       0 mismatching; stress (free order, reader on its wake thread) 27/27 clean, every frame taken, 0 torn; 21 min at
       below-normal priority (`.artifacts/evidence/architecture/native_core_p2/20261108_live_gate_slice2/
       live_gate.json`). Portability (settled order, the four off-steady scenarios): 99 pairs, 138,978 frames,
       0 mismatching, 15 min (`.../20261108_live_gate_slice2_settled/live_gate.json`). The stress run is synchronous
       per input (the worker does not pace itself until work order 5).
     - *Left for work order 5:* production wiring of these controls (the worker's own cadence, latest-wins
       application, the main-side mailbox clear on park, fail-closed fades), and Bubble's own generator (A2-M2; done in
       5.6).
   - **Slice 2 follow-ups (8 Nov): checkpoint audit 4's open findings** (`Native_Core_P2_Audit.md`, "Checkpoint audit
     4"; A4-M1 landed first on main, e66644c1; A4-M5's evidence copied to the cited paths):
     - *A4-H1, one owner for activation and the engine edges:* `widgets/spotify_visualizer/logical_edges.py` (QtCore at
       most at import time, in the import-weight probe; a configuration loads QtGui at call time, A5-L2 below) holds the sequences once and both hosts call them:
       `apply_logical_configuration` (the owner's `_apply_configuration`, its backdrop passed in as the presentation
       step), `commit_logical_activation` (the owner's `_activate_pending_mode` from the outgoing runtime's stop through
       the engine transaction, a preset's view motion and the reset to the pending identity; the owner passes its Edit
       profile switch, its own configure entry and its failure recovery, which runs inside the failed transaction as
       before), `apply_playback_edge` (`set_playing`), `prepare_engine_start` / `admit_engine_start` (`start`),
       `release_engine_for_park` / `resume_engine_after_park` (`set_display_power`). The owner keeps its Edit profile,
       backdrop, scene binding, crossfade, cadence park and reader-side mailbox; the session keeps its capture-lane
       completion edge. `feature_replay.switch_offline_controller_mode` is deleted (`offline_activation_request` builds
       only the activation's inputs) and the session's `_start_playback`, `_set_playing`, `set_display_power` and
       mode switch are calls into the module. What the copy had diverged on now follows the owner: the activation stops
       the outgoing runtime (`stop_logical_runtime`: render admission closed, the writer's unread record and every
       logical mode state dropped, so a switch back starts the mode fresh, as production; `PacketMailbox.clear` is
       writer-safe), unpark re-acquires only what park released, `start`'s engine reference and `ThreadManager` binding
       are taken at the first input (the owner's `start`), separate logical / presentation kwargs. A test-side copy of
       the activation (`test_visualizer_audio_source_freshness._production_hot_swap`) now calls the commit too.
       Gate: `tests/test_visualizer_logical_edges_parity.py` drives two edge scripts (start, pause/resume, park/unpark
       playing and paused, mode switch, same-mode preset, switch back; parked before start, started paused) through the
       owner's methods and the session's on two recording engines and controllers configured alike and compares the
       engine and controller call logs and the fence state step by step; negative controls: the pre-change session
       fails it (`set_thread_manager` / `acquire` at the first input, `stop_logical_runtime` at a switch) and a
       drifted hand copy of the session's play edge fails it.
     - *A4-M3:* a `VIS_SET_MODE` for the current mode is the owner's same-mode preset activation (new settings and
       engine activation; never acknowledged and dropped). Test in `test_visualizer_engine_live_off_steady.py` (the
       pre-change session fails it: activation unchanged).
     - *A4-M4:* `FramePacketWriter` keeps each pending edge's slot identity and carries it only into later slots of the
       same identity, so a new activation's slot never carries an old activation's edge. Test with a switch between an
       edge and its consume, control within one activation (`test_visualizer_engine_packet_abi.py`; the pre-change
       writer fails it).
     - *A4-L1:* the odd `sequence_begin` is its own aligned 8-byte store before the rest of the slot head (identity
       included); the module docstring states the store order the P3 C reader relies on. Store-order test (the
       pre-change single pack fails it); the C2 interleaving tests stay green.
     - *A4-L2:* `MODE_CODES` append-only is enforced: the table as of ABI 2 is a pinned prefix in the test (an ABI
       constant), later codes only appended above it (renumbered, removed, reordered or reused codes fail it).
     - *A4-L3 and A3-L5:* the device refusal is per engine (`SpotifyVisualizerAudioWorker.refuse_devices`, delegated as
       `_SpotifyBeatEngine.refuse_capture_devices`: with no capture factory installed the worker's device path raises)
       instead of swapping `audio_worker.create_audio_capture`, so sessions closing in any order leave the module and
       every other worker untouched; the capture factory lookup is `is None`, never `or` (a falsy source object is
       used). Tests: two sessions closed out of order, the module untouched and a non-session worker keeping the
       device path (the pre-change swap fails it); a falsy installed source.
     - *A4-L6:* the doc leftovers (4V and work order 6's P3 note) now name the per-slot identity. A production-order
       admission failure refuses the tick's frame before it reaches the mapping (`PacketMailbox.set_publish_guard`,
       writer side, None outside a session); test with the failure recorded mid-tick (the pre-change session publishes
       the frame first).
     - Ran: the parity test, the owner's focused tests (35 files, 668 passed; `test_defaults_schema_authority`'s
       source-text check of the configuration seed now reads `logical_edges.py`), `test_visualizer_engine_*` (live,
       live off-steady, worker, packet ABI / mailbox, snapshot, codec, import weight). Not re-run: the whole-clip
       gates (the activation now drops logical mode states as production does, so a switch-back's frames differ from
       the slice 2 report; both sides of the in-process vs worker comparison run the same code).
   - **Checkpoint audit 5 follow-ups (8 Nov)** (`Native_Core_P2_Audit.md`, "Checkpoint audit 5"; A5-M1 landed first on
     main, b1baa58c: the spectrum demand withdrawn):
     - *A5-M2, the configure edge is the owner's:* `logical_edges.configure_logical_controller` is the owner's
       `configure` (the activation's resolved inputs recorded by `record_activation_inputs`, the one recording step the
       activation commit uses too, then `apply_logical_configuration` with separate logical / presentation kwargs, the
       technical config, the mode's logical state and the warm re-entry fence; Media's `playing` as the host binding
       passes it, False). `visualizer_host_binding` hands the owner the activation's inputs (`configure(activation=...)`)
       instead of writing them onto the controller itself. `EngineSession._configure` calls the same function and then
       the owner's bind step (render admission for the configured identity); the session's start is the host
       binding's (`set_playing` with Media's state, then `start`, including `start`'s release when the displays are
       off). `feature_replay.configure_offline_controller` stays the offline replays' configure (Studios, replay tools,
       the evidence owner replay: no owner, bind or start, so playing from the first frame and admission open at once)
       and nothing on the product path calls it. The session's frames are unchanged for the feature and snapshot inputs
       (the worker and snapshot identity tests still equal the owner replay for all nine modes); on the live rig the
       fence test's control now disables the arm as the cold path does (the configure arms it too). The parity test
       configures each host through its own path (the owner's `configure` + bind as the host binding drives them; the
       session's `_configure`) and compares the call logs and the logical state from the configure on (primitive tick
       state, settings model, technical cache, resolved activation); negative control: the session configured with the
       replay copy fails it.
     - *A5-L1, the parity test's blind spots:* scripts on warm and cold engines; start while the displays are off (the
       owner's tail release is `logical_edges.release_engine_started_parked`, the session runs it too); the owner's
       Edit-profile and backdrop steps logged and placed (the profile discard and commit inside the transaction before
       the mode changes, planar -> 3D only); the park order with a running logical runtime pinned (the cadence park and
       unpark are `park_logical_side` / `unpark_logical_side`, the session's too: park, release; re-acquire, capture,
       rebase while parked, unpark), with a negative control unparking before the resume inside the shared module (both
       hosts lose the rebase; the parity comparison alone cannot see it); the owner's activation failures per stage
       pinned (profile discard, profile commit, `set_mode`, the reset after `set_mode`: the step logged, the outgoing
       mode restored inside the transaction or `failed`, the transaction always ended); a failed preset and an unjoined
       runtime on both hosts (same logs; nothing begun).
     - *A5-L2:* "QtCore only" is import time only; the first activation loads QtGui (`config_applier._color_or_none`,
       `QColor`s for the presentation config the tick reads). The fresh-spawn probe now reports the worker's Qt modules
       at spawn (QtCore at most) and after its first activation (QtCore and QtGui, asserted as today's state); the real
       fix is work order 5 slice 5.4, which flips that assertion.
     - *A5-L3:* the writer-side `PacketMailbox.clear` now also drops the writer's pending edges
       (`FramePacketWriter.drop_pending_edges`), so the next publication carries none in the frame or the slot's edge
       mask, whatever its identity (before, a same-identity clear kept them in the mask; only the identity filter
       dropped them across a switch). The newest slot already published stays: it is the reader's (test with a
       control: without the clear the edge is carried).
     - *A5-L5:* the owner sets the `activate_committed_profile` step after its render-bridge discard, so a discard
       failure logs `begin_engine_transaction` again, as before the shared module (test; the pre-fix module fails it).
     - *A5-L6:* the device refusal is per engine and acts only while no capture factory is installed (the session
       always installs one), so it is defence in depth for the session's own engine; another engine in the worker
       process is not refused (the old global swap did). Acceptable while the worker hosts one engine (docstrings of
       `refuse_devices` and the session).
     - Ran: the parity test (18), the owner's focused tests (35 files + the defaults authority and source freshness
       tests: 661 passed, 2 skipped), `test_visualizer_engine_*` (worker, snapshot, live, live off-steady, packet ABI /
       mailbox, import weight). Mutations each failing their test: the A5-L5 label, the session without the
       start-while-parked release, without the play edge before start, without the cadence park, the writer clear
       without dropping edges.
4V. **Built for the Vulkan core (operator, 8 Nov: "make sure you're still making the native core with Vulkan and
   what it brings us in mind").** P3 is a C++ render core behind the existing `QSGRenderNode`, on Qt Quick's Vulkan RHI
   (`Graphics_Backend_Decision_2026-11-05.md`; P1 proved QRhi on Vulkan in and outside Quick's frame). What it brings,
   and what every P2b slice must keep possible:
   - **A render thread that never runs Python** (the measured live problem: render-thread starvation behind
     GIL-held Python). P2b removes the tick and DSP from the main process; P3 removes the Visualizer's draw. A render
     thread with no Python at all also needs the background, backdrop and Studio items native (P1 spike, Risk 1;
     audit A3-M5): P3's Visualizer port alone leaves them. Nothing P2b adds may put Python back on the render thread
     for good: today's decode at sync (audit A2-H3) is P2's interim cost and disappears when the core reads packets
     itself.
   - **Zero-Python uploads:** the core copies a frame slot from shared memory straight into a host-visible Vulkan /
     QRhi buffer (std430-compatible blocks, 16-byte aligned: the ABI already aligns payloads). So the P3-facing
     payload is per mode and fixed-layout (`payload_schema` per mode, audit H5), with the writer filling each slot's
     own identity and flags per publish, so the core can validate a slot without Python. The per-frame identity
     (activation, mode code) lives in each slot's head under the slot's seqlock, not only in the mapping header,
     which the seqlock does not cover (audit A3-M4: with an in-place mode switch a header read could pair a frame with
     the wrong identity). **Built (slice 2, ABI 2):** the identity is per slot under its seqlock, flags and source
     timestamp per publish, the header the configure-time identity. The tagged codec stays the Python-to-Python transport until a mode's core
     port lands; Spectrum (P3's first port) gets its fixed layout first, defined from its `SpectrumFrame` fields, as
     part of P3's first slice, never as a second codec for the same consumer.
   - **The 8 GLSL compute shaders:** shaders stay QRhi-portable (GLSL 460 that `qsb` compiles to SPIR-V), so the
     core can run them through QRhi's compute passes; no new GL-only extension use in modes the core will port.
     QRhi exposes no separate async compute queue (the core would need raw Vulkan through the native handles for
     that), and the 5 Nov decision rates async compute "not our bottleneck" (audit A3-M5). Port-readiness rule 5,
     measured 8 Nov (`tools/vulkan_shader_readiness.py`): **0 of 18** compute shader sources compile to SPIR-V, all
     for one reason: loose `uniform`s outside a block ("non-opaque uniforms outside a block ... not allowed when using
     GLSL for Vulkan"). The fix is mechanical and works on both backends (GL 4.6 takes std140 uniform blocks too):
     move each program's uniforms into one block and upload it as a UBO instead of `glUniform*`. It touches accepted
     modes' uniform code, so it is done per mode as P3 ports it (Spectrum first), each with that mode's pixel gates.
     From now on, new compute shaders declare their uniforms in a block (Vulkan-ready from the start).
   - **DLSS / FSR (Streamline / FidelityFX) integrate at the core's Vulkan device**, per mode and only where the content
     survives temporal upscaling (the 5 Nov decision's caveats stand); nothing to build in P2.
   - **The Vulkan flip** needs a `QVulkanInstance` PySide6 cannot create: the native module attaches it (P1). The worker
     process (P2b) never touches the GPU, so the flip is purely the main process's render side.
4b. Live-engine and off-steady-state gates (audit H3): a gate whose reference is the live `_SpotifyBeatEngine` fed
   PCM through the real audio worker (offline, blocks pushed into the capture callback, so asynchronous commits are in
   play); gate clips with pause/resume, a warm re-entry (fence armed) and an in-session mode switch; the read audit
   run on those paths. Scheduler state at session start and an engine-owned feed observer instead of the tap (M1).
   **Status (8 Nov):** [x] live-engine reference (P2b slice 1); [x] pause/resume, [x] warm re-entry (fence armed on
   resume and on display-power unpark), [x] in-session mode switch (P2b slice 2, 4P). Not done, and moot once P2b
   lands (the snapshot layer is deleted with them): the snapshot read audit on those paths and M1's scheduler tap.
4c. Main-process cost (audit H1), before 5: per mode, the main process's GIL time per tick in process vs. the
   snapshot path (step + capture + pickle + decode, no acknowledgement). The audit measured capture .20-.25 ms, pickle
   .07 and decode .08-.54 per tick, against in-process ticks of .33-.45 ms for Spectrum, Oscilloscope, Sphere and
   Extruded Spectrum: P2a only gains for Bubble, Spline Curve, Waveform Ribbon, Extruded Bubble and Neon Lake. Decide
   on these numbers whether P2a's production wiring proceeds (capturing only what the mode reads) or P2b (the worker
   owns capture and DSP; the snapshot layer is deleted) goes first.
   **Measured and decided (8 Nov): P2b first.** `tools/visualizer_replay/engine_main_cost.py` (every mode, 20 s of both
   shipped clips through production DSP, 2,312 ticks per mode; report
   `.artifacts/evidence/architecture/native_core_p2/20261108_main_cost/main_cost.json`; three agents ran focused work
   at the same time, so absolute numbers carry noise, the per-mode comparison does not). p50 per tick, ms:

   | Mode | in-process tick | P2a main side (capture + pickle + take) | P2a saves | DSP | P2b saves (tick + DSP - take) |
   |---|---|---|---|---|---|
   | Spectrum | .31 | .40 | -.09 | 1.14 | ~1.34 |
   | Oscilloscope | .42 | .38 | +.04 | .46 | ~.81 |
   | Bubble | 1.78 | .46 | +1.32 | .60 | ~2.20 |
   | Spline Curve | 1.69 | .46 | +1.23 | .51 | ~2.03 |
   | Sphere | .30 | .41 | -.12 | .50 | ~.68 |
   | Extruded Spectrum | .30 | .38 | -.08 | 1.08 | ~1.29 |
   | Neon Lake | .48 | .54 | -.07 | 1.08 | ~1.30 |
   | Extruded Bubble | 1.79 | .66 | +1.13 | .46 | ~1.88 |
   | Waveform Ribbon | 1.59 | .56 | +1.03 | .48 | ~1.79 |

   Capture is ~.21 ms whatever the mode (22 deep-copied getters); a per-mode capture set (only what the tick read, 10-15
   values) would recover ~.1 ms, so the five cheap modes stay at break-even under P2a. DSP here is one analysis block
   per frame; live it runs per capture callback on the compute pool (same GIL), so P2b's gain is a floor. P2b removes
   the whole snapshot layer (capture, scheduler tap, the main side of the mode rules) and with it audit H1, H2 and M1;
   the main process keeps only control edges and the frame take. P2a's built pieces stay until P2b's worker owns the
   engine: the ABI, codec, mailbox, wake and worker session are P2b's too; `engine_snapshot.py` and the `snapshot`
   session input are deleted when P2b lands (done, 5.6).
   **Corrections (checkpoint audit 2, 8 Nov):** the DSP column double-counts for Spectrum, Extruded Spectrum and Neon
   Lake: `ProductionLaneEngine` analyses each new block twice for them (`feature_replay.py:255` and `:376`, 1.54
   passes per frame against .77) plus ~.2 ms of replay-only bookkeeping, so P2b saves ~.8 ms for those three, not
   ~1.3; and "a floor" is unproven (live DSP per callback, and how much of NumPy's FFT holds the GIL, are unmeasured:
   the live-engine rig, P2b slice 1, measures them). The worker tick ran in the measuring process, so its garbage
   collection can land inside the timed take; the per-mode capture set came from two clips at default settings. Under
   P2b the frame take's decode (.07-.37 ms) runs on the render thread while the GUI thread waits
   (`quick_presentation_sync.py:308-311`): it is added sync latency, not only main-process time. The decision stands:
   P2b removes more main-process work than P2a for every mode after the corrections.
   **Live engine measured (8 Nov, P2b slice 1):** `tools/visualizer_replay/live_engine_cost.py` on the live-engine rig
   (4P, slice 1): the production engine fed both shipped clips whole (2,310 ticks per mode) through the capture
   callback, every piece timed in process: the callbacks of the tick (mono mix, history, publish), the engine step, the
   compute lane's own execution + commit-callback time per analysis (its diagnostics), the tick. The P2b take is timed
   in the main process with the session in a real `WorkerType.VISUALIZER` process, so no worker tick or its garbage
   runs in the timed process (A2-M4). Report: `.artifacts/evidence/architecture/native_core_p2/20261108_live_cost/
   live_cost.json`, at below-normal priority, system CPU 7% before and 20% after (other agents' work); ticks read
   ~30-60% above 4c's run (Spectrum .41 vs .31, Bubble 2.79 vs 1.78), so compare within a column. p50, ms:

   | Mode | callbacks/tick x per callback | step | analysis (.76 per tick) | tick | live total p50 (p90) | P2b take (worker process) | P2b saves |
   |---|---|---|---|---|---|---|---|
   | Spectrum | 4.12 x .019 | .027 | .63 | .41 | 1.17 (1.46) | .15 | ~1.02 |
   | Oscilloscope | 2.20 x .042 | .035 | .51 | .68 | 1.33 (1.62) | .13 | ~1.20 |
   | Bubble | 4.12 x .026 | .029 | .64 | 2.79 | 3.16 (4.07) | .25 | ~2.91 |
   | Spline Curve | 2.20 x .034 | .032 | .55 | 2.51 | 2.98 (3.71) | .21 | ~2.77 |
   | Sphere | 1.12 x .042 | .031 | .54 | .48 | 1.09 (1.35) | .17 | ~.92 |
   | Extruded Spectrum | 4.12 x .029 | .034 | .77 | .57 | 1.44 (1.81) | .13 | ~1.31 |
   | Neon Lake | 2.20 x .033 | .030 | .69 | .86 | 1.58 (2.16) | .43 | ~1.15 |
   | Extruded Bubble | 1.12 x .045 | .039 | .56 | 3.52 | 4.01 (4.98) | .75 | ~3.26 |
   | Waveform Ribbon | 2.20 x .037 | .040 | .63 | 2.97 | 3.66 (4.63) | .53 | ~3.13 |

   - **DSP per capture callback:** a callback costs .02-.045 ms (blocks per tick follow the mode's resolved Block
     Size, about 128 / 256 / 512 samples here); the analysis runs once per *consumed* block, not per callback (the capture triple buffer
     keeps the newest block; the 90 Hz tick consumes it), .51-.77 ms each, at .76 per tick on the recorded cadence
     (~69 analyses per second): ~.4-.6 ms of DSP per tick, ~35-55 ms of GIL per second of audio. With one analysis
     per new block the live DSP per tick (callbacks + step + .76 analyses) is .58 (Spectrum), .74 (Extruded Spectrum)
     and .63 (Neon Lake); on 4c's tick and take that is P2b ~.74 / ~.91 / ~.68 ms, so the corrected ~.8 ms stands
     (this run's busier ticks give 1.0-1.3). For the other six the live DSP (.47-.60) matches 4c's one-pass column
     (.46-.60), so their 4c "P2b saves" stand.
   - **GIL share:** the production analysis (`compute_bars_from_samples`, Spectrum and Bubble configurations) holds the
     GIL for essentially all its wall time: against a pure-Python counter at a fine switch interval it leaves the
     counter the same share a pure-Python loop does (calibrated against a sleep). NumPy's `rfft` at capture sizes
     (480: never releases; 1,024 / 2,048: ~75% held) releases the GIL only around the kernel, which is small next to
     the Python-side work; it releases more at 1 Mi points. So DSP wall time is GIL time: neither a floor nor an
     overstatement. At the default 5 ms switch interval there is a convoy: the Spectrum analysis (brief releases) runs
     at 11-16% of its solo rate against one CPU-bound Python thread (each release costs up to an interval to win the
     GIL back), while Bubble's (no release) starves the other thread. In process today the analysis therefore waits on
     the GUI, render and tick threads; under P2b it contends with the worker's tick only. Gate 3 measures analysis
     latency (capture to commit) alongside GIL time.
   - **GC overlap:** 1-24 of 2,310 ticks per mode overlapped a collection; p50 without them is the same within .01 ms;
     Extruded Bubble's collections total 282 ms (its p90 carries them).
   - **The take with the worker out of process** is .13-.75 ms p50 (Extruded Bubble .75, Waveform Ribbon .53, Neon Lake
     .43), above 4c's in-process take (.07-.37): the reader copies a slot another process just wrote. Under P2b this
     runs at sync on the render thread (A2-H3), so where the decode runs is part of work order 5.
5. Production wiring and lifecycle. Must specify (audit H2, M5): a main -> worker latest-wins snapshot mapping (the
   ABI with roles swapped, a wake byte to the worker; the supervisor's FIFO request queue carries edges only); an
   in-place `set_mode` (built at the session, P2b slice 2: `VIS_SET_MODE`) and a resolved-settings delta applied to
   the existing session at a tick boundary (a rebuild per slider step would reset the mode); playing / framed-view / park controls (the main process's capture is the
   cadence); fail-closed handling of `session_closed` and of heartbeat loss, with a fade; the owner closing its wake
   sender after configure; the label-namespace counter's owner; the presentation-config reads moved to logical config
   (QtCore only); the worker in the dormancy receipt; frozen spawn (operator); frame age defined from the capture
   timestamp on both paths (M3).
   **Work order 5 slices (lead, 8 Nov; in order, each audited before the next):** under P2b the main process sends
   only control edges (no per-frame inputs), so audit H2's latest-wins input mapping is not needed: the control
   queue carries edges, frames come back through the ABI and the wake.
   - 5.1 Worker-paced ticks: the worker runs the logical runtime's cadence itself (the in-process cadence owner,
     moved, not copied); frames reach the owner through the existing mailbox reader and wake; a stalled owner never
     blocks the worker (latest wins in the ABI already).
     **Built (8 Nov).** The cadence owner is `VisualizerLogicalRuntime` (`logical_runtime.py:316`: one non-Qt thread,
     a monotonic `perf_counter` deadline sequence, missed deadlines skipped, parked with no wake cadence), started
     through the controller (`runtime_controller.start_logical_runtime`, `:760`; a runtime started while parked starts
     parked). The owner's start of it moved into `logical_edges.start_logical_cadence` (the import warm, the authored
     interval `DEFAULT_LOGICAL_HZ`, the default step `logical_tick`); the owner's `_start_logical_runtime` and the
     session both call it, and the cadence park / unpark are the shared `park_logical_side` / `unpark_logical_side`
     (audit 5 follow-ups above). `EngineSession(inputs="live", order="free", cadence="worker", pcm=..., pcm_rate=...)`
     is started explicitly (`start` / `VIS_START`: the host binding's play edge and the owner's `start`, which starts
     the cadence with the session's step); Media's play edges are `set_playing` / `VIS_SET_PLAYING`; display power
     parks and unparks the cadence; a mode or preset request applies at once as the owner's activation does (it stops
     the runtime, which is the tick boundary, commits, binds and restarts it); `finish` (`VIS_STOP`) stops the cadence
     and reports the frames published, the cadence's accounting and the paced audio. The authored clock is the
     process's own (no pin). Every step: the audio due, then the tick (its own engine step consumes the newest block
     and submits the analysis, which commits on the compute lane while the tick reads the previous commit: the
     production engine's own order, `free`). A step that raised is the cadence owner's, exactly as in process
     (checkpoint audit 6, A6-M3, decided by the lead): `VisualizerLogicalRuntime` logs it (once per run of failures),
     counts it (`step_failures`) and the next step retries; nothing in the session catches it. In process there is no
     fail-closed bound on repeated step failures either, so none is added: a session whose steps keep failing publishes
     nothing new, which the owner's heartbeat and fade (5.5) handle. The recorded-PCM identity gates keep
     `cadence="input"` (one tick per input, deterministic); a paced session refuses `tick`.
     - *Audio on the audio clock, without a poll:* `recorded_capture.PacedPcmSource` holds the recording's continuous
       PCM (`pcm_from_capture_histories`: the capture histories' new samples in order; the stream loops) and at each
       cadence edge hands over the whole device blocks the audio clock produced since the previous edge (the time
       between the steps' wake times x rate, in the negotiated block size, the remainder carried; a late edge hands over
       several, at most a device's buffer, `MAX_BACKLOG_S` = 0.1 s: older audio overflowed, the playhead moves past it,
       A6-L1), through `RecordedCaptureBackend.offer` (the worker's own capture callback; a block offered while capture
       is closed is not captured). The blocks are phase-locked to the tick (delivered on the cadence thread just before
       it, never concurrently with it as a real device's own thread would be: A6-L2; the device's own phase and the
       callback/tick lock interaction are slice 5.3's). Nothing is due while capture is closed or Media is paused (the
       playhead holds), and a capture (re)open restarts the clock (the backend's `on_started`, which runs before the
       stream's callback is installed, A6-L1), so an unpark delivers no burst for the parked gap. It is not a poll and
       not a timer: it has no thread, never waits and wakes nothing; it runs only inside the cadence's own step, which
       the runtime wakes for anyway, and its clock is that step's wake time (the `perf_counter` the runtime reads just
       before the step, not its deadline: a late step really gets the late audio; A6-L3). (A feeder thread sleeping to
       each block's due time would be a second timer; a device's own clock is slice 5.3.)
     - *Gate:* `tests/test_visualizer_engine_paced.py` and `tools/visualizer_replay/live_engine_gate.py --paced`: a
       free-running session per mode, the reader taking the newest frame per wake on its own thread and then stalling
       40 ms (a slow GUI; the wake listener only sets an event, the owner's emitter): no exception or step failure, one
       frame per step, the cadence's own rate (its steps over its run time, less parked time) within 5% of the
       authored rate, coalescing (taken < published) and latest wins (every take after a stall is the newest frame
       the header named before it; A6-L6), the newest frame reached by a wake after the stop, revisions only advance,
       0 torn reads, and the audio reached the engine (A6-M1): the source delivered >= 97% of the paced audio time,
       the paced time >= 80% of the run, the audio worker's capture callback published every offered block into the
       engine's audio buffer (`engine.capture_publications`, >= 97% of the paced time), the engine committed an
       analysis on >= 80% of the steps and >= 50% of the frames taken carry energy. Also: the cadence parks with the
       display (no frame while parked, capture reopened, no burst, its rate after the unpark), a mode switch restarts
       it on the new activation (its rate after the switch), a step that raises once is logged and the next one
       publishes (in the owner's cadence and the session's), a failed paced switch and a failed stop close the
       session.
       Negative controls: a writer held by its reader (the cadence falls to the reader's rate), an ~11% slow cadence
       (passed the old 60% floor), a FIFO reader (stale takes), one block per edge (the audio falls behind the clock),
       an `offer` that never calls the capture callback (the source's own arithmetic still says delivered; the engine
       got nothing), the pre-fix catch-and-freeze step, and mutations: no cadence start, no rebase at a reopen (the
       park test's burst), the pre-C1 wake rule (the worker-process gate strands a frame). **Result (8 Nov, after
       audit 6; 3 s per mode in the `WorkerType.VISUALIZER` process, below-normal priority):** all nine modes OK:
       270-272 frames each, the cadence at 89.88-90.23 Hz of 90, one frame per step, 0-1 skipped deadlines, no step
       failure, the stalling reader took 65-66 with 64-65 latest-wins checks and no stale take, the last frame taken
       by a wake every time, 0 torn reads, audio paced 3.000-3.012 s, delivered and published into the engine
       2.997-3.011 s, 269-271 analysis commits, 95-98% of the frames taken with energy; 32 s
       (`.artifacts/evidence/architecture/native_core_p2/20261108_a6_paced_gate/paced_gate.json`; the pre-audit run:
       `20261108_paced_gate/`).
     - *Not in 5.1:* the production owner on the worker (5.2); the wake pipe's backpressure (a reader process whose
       listener stops draining fills the pipe, and `send_bytes` would then block the cadence: 5.5's "a full wake pipe
       never blocks the tick"; the gate's listener drains continuously); the owner noticing a session whose steps
       keep failing (5.5's heartbeat and fade: the runtime keeps stepping and logs each run of failures once, as in
       process).
     - **Checkpoint audit 6 follow-ups (8 Nov; all closed before 5.2):**
       - *A6-M1 (the paced audio check read only the source's arithmetic):* the session counts the blocks the audio
         worker's capture callback published into the engine's audio buffer (`_SpotifyBeatEngine.capture_publications`,
         `TripleBuffer.published`: reads for rigs, nothing per frame) and the engine's analysis commits since the
         cadence started, and reports them (`finish()["engine"]`); the gate gates on them and on frames with energy.
         The audit's dropping stub now fails (`delivered_over_paced` 0.999 as before, `accepted_over_paced` 0).
       - *A6-M2 (a failed paced switch stayed open):* `VIS_SET_MODE` validates first (a refused request leaves the
         session as it was, the input-paced contract), then an apply that raised closes the session with
         `session_closed` (capture, compute lane and mapping released), as `VIS_INPUT` does.
       - *A6-M3 (a failed step froze the session silently):* the retry contract above; the session's step catches
         nothing. Test: one injected failure is logged once and the next step publishes, in the owner's cadence
         (`_start_logical_runtime`) and the session's; the pre-fix step fails it.
       - *A6-L1 (unpark burst):* `RecordedCaptureBackend.start` restarts the paced clock before installing the
         callback, and one edge hands over at most `MAX_BACKLOG_S`. Tests: an edge landing anywhere inside `start`
         after a 60 s park delivers nothing; a 60 s open gap delivers at most a device's buffer; each fails with its
         fix reverted.
       - *A6-L2, A6-L3 (wording):* "phase-locked to the tick" and "the step's wake time", above and in
         `recorded_capture.py` / `engine_worker.py`.
       - *A6-L4 (the parity test's owner side was a hand copy):* it is now built by `VisualizerHostBinding.construct`
         (activation resolved from the Settings section, configure, bind, Media's edge, display power, start), and
         both hosts' cadence starts are recorded at start and after every activation (worker-paced and input-paced
         sessions). `test_visualizer_host_binding.py` pins that the binding passes `activation=` (dropping it fails
         that test and the parity). `activation` stays optional on the owner's `configure` (about twenty focused
         owner tests configure without one; the binding test is the guard). The parity compares the park raised
         before a start (built while the displays are off) by count, not position: the binding raises it after
         Media's play edge, the session before its start; neither reads the other.
       - *A6-L5 (no production-path frame check):* `tools/visualizer_replay/owner_production_replay.py` replays a
         shipped clip through the product's own path (the binding's `construct` builds the real owner on an unshown
         runtime with the production presentation kwargs; the recorded engine at the binding's bar count; the owner's
         installed cadence step once per frame, no thread). The same replay at `32f28d4f^` (b1baa58c, a temporary
         archive checkout, deleted) and at this tree gave **identical digests for all nine modes** (137 frames each;
         `.artifacts/evidence/architecture/native_core_p2/20261108_a6_l5_owner_path/`): the configure refactor left
         production frames unchanged. `tests/test_visualizer_owner_production_path.py` keeps the real path equal to
         the offline replay (`owner_replay`, built at the mode's bar count: its default 32 re-applies the bar count at
         configure and advances the engine identity, the only difference, in six modes) for every mode; dropping the
         logical, engine or presentation kwargs from the configure fails it. Frame-neutral steps (the activation
         record, a cold engine's fence, Media's edge before start) are the parity and binding tests'.
       - *A6-L6 (loose gate):* the rate within 5% of the cadence (park and switch tests: after the event) and the
         latest-wins check, above.
       - *A6-L7 (`VIS_STOP` left the session open):* the session closes even when `finish` raises (`session_closed` in
         the reply).
       - *A6-L8 (the worker keeps the pre-park unread frame):* a 5.2 obligation, recorded in 5.2 below.
   - 5.2 The owner on the worker: one code path in `quick_display_visualizer_owner.py` that sends the
     `logical_edges` edges to the worker instead of running them, admitted by a code-level admission in
     `core/diagnostics/experiment_flags.py` (never an environment flag) until gate 3 accepts it; the in-process path
     stays the default and the fallback. Obligations from checkpoint audit 6: the owner clears its reader after the
     `VIS_SET_DISPLAY_POWER(off)` reply (after the worker's last pre-park publish), never before it, so the pre-park
     unread frame and its protected edges are dropped as in process (A6-L8: the worker's park keeps them); the worker
     receives the binding's own activation inputs and `presentation_kwargs` (with `scene3d_detail`), not an offline
     request (A6-L4); the owner's wake callback never blocks (a queued signal), and a stalled GUI leaves the listener
     draining (the wake-pipe backpressure note); a worker step failure is the runtime's retry, as in process (A6-M3).
     **Built (8 Nov), with the core of 5.3:**
     - *Admission:* `experiment_flags.visualizer_engine_worker_admitted` (argv `--viz-engine-worker`, default off, never
       an environment variable), read once per owner construction (`QuickDisplayVisualizerOwner.__init__`). Off: no
       link, no worker process, no worker-path import (`engine_worker_link` is imported only on the worker path); every
       edge runs in process as before (owner, binding and sync suites and the production-path frame test green; the
       one off-path additions are per-edge `self._worker is not None` checks, the binding reading
       `owner.engine_identity()` (the same two engine reads in process), and the controller's layout-metrics observer
       slot, one attribute read per metrics write).
     - *The main-process side:* `widgets/spotify_visualizer/engine_worker_link.py`. One `EngineWorkerLink` per
       session: the control edges (each waits for its reply, bounded) and the reader side of the session's mapping
       (created, held and unlinked by the main process). The owner keeps no beat engine and runs no tick (test: no
       engine factory call, no `logical_tick` in the main process, no logical runtime). Edges: configure
       (`VIS_CONFIGURE` with the binding's own activation inputs and `presentation_kwargs`, A6-L4; the main side
       configures only presentation: `configure_presentation_side`), start (`VIS_START` with Media's state), Media's
       play edges (`VIS_SET_PLAYING`; Media stays the one owner of "playing"; before start the start carries it, as
       the binding's play edge before `start`), display power (`VIS_SET_DISPLAY_POWER`; the reader is cleared after
       the park reply, never before it: A6-L8), mode and preset activations (the owner's crossfade unchanged; its hidden
       commit is `VIS_SET_MODE` applied at once in the session, replying with the committed identity, which the owner
       binds), stop/retire (`VIS_STOP`, then the reader closes and the mapping is unlinked). A step failure stays the
       worker runtime's retry (A6-M3). The engine identity the binding binds comes from the configure reply
       (`owner.engine_identity()`). `waiting_target` on the worker reads the target's newest frame (a current-identity,
       presentable frame) instead of the in-process tick state's flag.
     - *Frames to presentation:* the worker's wake byte per publish -> `listen_for_wakes` (one daemon thread blocked on
       the pipe) -> the owner's `QuickVisualizerPublicationWake.request` (a queued Qt signal: never blocks, coalesces)
       -> `sync_present` on the GUI thread -> `QuickVisualizerPresentationSync.sync_latest` takes the newest whole
       frame from the mapping (decoded on the GUI thread; at render-thread sync admission when a window renders). The
       listener drains while the GUI is blocked (test: ~90 frames published during a 1 s GUI block, one wake pending).
     - *The framed view (found here):* the tick reads the controller's layout metrics (committed extent and per-mode
       rotations, the live CUSTOM override), which on the worker path live on the main controller. The controller has a
       layout-metrics observer (None in process); on the worker the owner forwards changes as `VIS_SET_VIEW` (inside a
       presentation once at its end, before the next step; at a hidden activation before `VIS_SET_MODE`). With the
       default layout they never change (the identity gate cannot see them), so a test drives an override and a
       rotation map. Edit orbit, Waveform's view and Expanded Visualizer's view inputs are still to inventory (5.4).
     - *The label-namespace counter:* `engine_worker_link.next_label_namespace`, one process-wide counter owned by that
       module for the app's life; every `VIS_CONFIGURE` takes a fresh value (test).
     - *The device (5.3's core):* in production the session (worker-paced, no `pcm`) installs no capture factory and
       refuses nothing, so its engine opens the loopback device through the audio worker's normal path
       (`create_audio_capture`) on its own capture lane, where COM initialisation stays (test: the device constructor
       runs on `affinity_io_lane:audio_capture`, no factory installed). The session never waits on the device (as in
       process); a check queued behind every capture transaction on the lane reports an open that failed (since 5.5,
       A7-L4: a device failure that keeps the session and is retried at the next capture edge, no longer the session's
       end; test). Tests
       never open a device: `recorded_capture_for_testing` adds a recorded-PCM source (and its cadence) to the
       configure, and the session refuses the device for its life.
     - *Failure (interim, 5.5 completes it):* a worker that fails to configure (no supervisor, no process, a failed
       reply) or to start leaves that activation in process, logged once. A session that ends later (a failed reply,
       `session_closed`, its wake pipe ending: the worker died, or its device failed) holds the last presented frame,
       fades it out from the fade it was drawn at, paced by the replacement's own publications (taken, not shown;
       re-presented held frame with a falling content fade: never vanishes), then reveals the replacement as an
       activation does (hidden until a presentable frame, then faded in); the first failure reconfigures the worker once
       (a fresh session and namespace), a second keeps the owner in process for the rest of the run
       (`worker_disabled_for_run`; later owners start in process). Left for 5.5: heartbeat loss without a pipe end (a
       hung worker reaches the failure path only through an edge's timeout), a fade with no replacement frames to pace
       it (the held frame stays, frozen, until one comes), a failure during an uncommitted crossfade drops the request.
     - *Settings (interim, 5.4 replaces it):* a preset or settings change while on the worker is a whole re-activation
       of the session (the owner's same-mode preset activation, `VIS_SET_MODE` with its own inputs), not a delta at a
       tick boundary.
     - *Found and fixed on the way:* the frame codec refused Waveform Ribbon's `RibbonStrays` (a strays style reached by
       a switch into Waveform Ribbon): the worker's publish raised. Appended to the type table (test).
     - *Gate:* `tests/test_visualizer_owner_engine_worker.py` and `tools/visualizer_replay/owner_worker_gate.py` (the
       REAL owner through the binding's `construct` on an unshown runtime; a real `WorkerType.VISUALIZER` process on
       the shipped clip's PCM). **Result (8 Nov, below-normal priority, 187 s;
       `.artifacts/evidence/architecture/native_core_p2/20261108_owner_worker_gate/owner_worker_gate.json`):**
       identity: all nine modes identical, 549 frames each, through configure/start, play, a warm pause, park/unpark and
       a switch through the owner's crossfade (Spectrum -> Extruded Bubble, Oscilloscope -> Bubble, Bubble ->
       Oscilloscope, Spline Curve -> Neon Lake, Sphere -> Waveform Ribbon, Extruded Spectrum -> Oscilloscope, Neon Lake
       -> Spline Curve, Extruded Bubble -> Spectrum, Waveform Ribbon -> Sphere), never leaving the worker (the worker
       side input-paced, production read order; the in-process side the owner on the live engine). Real time (3 s per
       mode, worker-paced, the GUI stalling 40 ms per presentation): all nine OK, the cadence 90.01-90.26 Hz, one frame
       per step, 62-66 of 280-283 presented, latest wins on every take (0 stale), the newest presented after the stop,
       0 torn, the audio in the engine (Spectrum: 99.9% of the paced audio accepted, every frame with energy).
     - *Main-process cost, the first gate-3 data point (3 s per mode, no stall; process CPU over cadence steps; psutil
       times tick at 15.6 ms on Windows, so per-thread values are coarse):* in process (the owner's cadence thread, the
       live engine on paced PCM: callbacks, DSP and tick here) vs on the worker (this process only takes and presents),
       ms per step:

       | Mode | in process | on the worker | GUI `sync_present` p50 / p90, in process | on the worker |
       |---|---|---|---|---|
       | Spectrum | 2.31 | .90 | .19 / .27 | .50 / .62 |
       | Oscilloscope | 2.36 | .73 | .20 / .28 | .35 / .52 |
       | Bubble | 4.25 | .84 | .24 / .32 | .65 / .82 |
       | Spline Curve | 3.81 | .89 | .19 / .30 | .43 / .64 |
       | Sphere | 1.67 | 1.06 | .21 / .30 | .47 / .63 |
       | Extruded Spectrum | 2.30 | .67 | .20 / .27 | .48 / .63 |
       | Neon Lake | 2.64 | 1.01 | .19 / .29 | .86 / 1.04 |
       | Extruded Bubble | 4.55 | 1.18 | .19 / .28 | .85 / 1.19 |
       | Waveform Ribbon | 4.95 | 1.23 | .21 / .30 | .75 / 1.07 |

       So the main process saves .6-3.7 ms of CPU (GIL) per step, and the GUI thread pays the take's decode instead
       (.15-.65 ms more per presentation: the GUI thread itself goes from .40-.69 to .61-1.29 ms per step). No render
       thread runs here (no window): the render thread's sync-time take is unmeasured, and gate 3's game60 run remains
       the operator's.
   - 5.3 The live device in the worker: capture opens there; Media's playback truth stays the one owner of
     "playing" (sent as an edge); audio device changes, COM initialisation on the worker's capture lane, capture
     failure reported as a crash. **Core built with 5.2 (above):** capture opens in the worker through the normal
     path on its capture lane (COM there), Media's state is an edge, a failed open ends the session for the owner.
     **Left (then):** audio device changes (a default-device switch or an unplugged device mid-session: today the audio
     worker's wake-driven restart on resume, nothing reported to the owner), a device that opens and then goes silent
     or stale (not a failure today), and the physical check on a real device (operator).
     **Built (8 Nov), the rest:**
     - *In process today (read, the parity reference):* nothing follows device changes on the Visualizer's behalf. The
       loopback stream (`PyAudioWPatchBackend`) stays bound to the endpoint it opened on. A WASAPI loopback stream
       delivers nothing while nothing renders to its endpoint, and an invalidated (unplugged) stream's thread ends
       without the audio worker hearing of it (`is_running` stays True; nothing raises into Python). So a
       default-output switch the player follows, an unplugged device and a stale stream all look the same: no
       callbacks. The engine's silence decay takes the bars to rest (frames go on), and capture moves only at the
       next capture edge: Media's pause -> play (`apply_playback_edge`'s `wake` restarts a capture the audio worker
       calls stale; `restart` terminates and re-initialises PortAudio and opens the current default), a pause longer
       than the 6 s warm grace (capture stopped; the next play opens the current default), display park/unpark, or an
       activation whose block size differs. Mid-song, without one of those, the Visualizer stays at rest. The worker
       path did exactly this (it shares `apply_playback_edge` and the audio worker), and was worse in one respect:
       `capture_failed` (A7-L4) covers only a stream that did not open, so a dead stream was reported as healthy.
     - *Decided: follow the audio, on the cadence's own edge, in the worker.* The one IMMNotificationClient in the
       codebase (`core/media/core_audio_callback_probe.py`) belongs to the Media/OSD system-audio owner: the main
       process's GUI COM apartment, registered only while a Media or OSD consumer is active. Following the default is
       also not the goal. A player pinned to the old output keeps rendering there, and moving capture to the new
       default would lose the music (test). What the picture needs is capture where the audio is, and one signal for
       "the audio is not here" covers the switch, the unplug and the stale stream when the player is the endpoint's
       only renderer: no capture publication while Media says playing (its limits, checkpoint audit 11's A11-L6, are
       under *Known limits* below). `EngineSession._watch_device_delivery` (device sessions only) compares the engine's capture
       publications (`capture_publications`, one counter read) with the previous step's on every cadence step. After
       `SILENT_CAPTURE_STEPS_BEFORE_REOPEN = 180` consecutive playing steps with none (about 2 s at 90 Hz), it reopens
       the stream once through `_SpotifyBeatEngine.restart_stale_capture`. That is new, and nothing in process calls
       it. 180 steps is twice the stream's own first-callback grace, so a stream that is still opening, or a player
       still buffering after its play edge, is not bounced. `restart_stale_capture` is the audio worker's own
       stale-capture restart, the one `wake` makes: gated by `is_capture_stale`, restarted on the capture lane, and the
       smoothing clock restarted as `wake` restarts it, so the first analysis after the gap is smoothed, not snapped.
       - *Why in the worker, not the owner's recovery:* the capture lane is the device's one owner, and a reopen costs
         one restart there (20 ms on the stand-in), invisible beyond the gap. The owner's recovery would fade,
         reconfigure a whole session onto the same device path, and count a strike.
       - *Not a timer, poll or retry loop:* it is a count on the cadence step that runs anyway (as 5.7's 60 failed
         steps). There is one reopen per silent run, re-armed only by the device publishing again (logged as resumed)
         or by a capture edge (start, Media's play edge, display power, an activation). A reopened stream that stays
         silent is left until one of those, as in process.
       - *What never counts:* digital silence (a playing silent passage renders zeros, which are published) and a
         pause (Media is the one owner of "playing"). Two guards hold it: the publication count, and the stale gate,
         which refuses a stream that is publishing (negative control below).
       - The watch never raises into the step. A device problem is never a step failure, so it never feeds
         `FAILED_STEPS_BEFORE_CLOSE` (A10-L4's "a step-failure run during an audio device change": none here, measured
         below, including a switch to another rate and channel count).
     - *A device failure stays a device failure (A7-L4).* A reopen that fails (no output left) leaves capture closed.
       The check queued behind it on the lane reports `capture_failed` (logged once). The session keeps running (idle
       frames, as in process), and the next capture edge retries the device through the normal path (test: an output
       plugged in meanwhile opens at Media's next play edge). No step fails, the session does not fail closed and its
       wake pipe stays open, so the owner sees no session end and nothing counts towards the two-strike rule.
     - *Reported to the owner.* Every reply that carried `capture_failed` now carries the session's device report
       (`EngineSession.device_report`: `capture_failed`, `capture_reopens`, `capture_resumed`), and `VIS_STOP`'s report
       carries it nested under `report["engine"]`. The worker process's own log lines never reach the main log: a
       worker logs nowhere unless perf metrics are on, and the session's module loggers not even then. So the link logs
       the device state in the main log when a reply changes it (`EngineWorkerLink._note_device_report`, reached from
       either shape by `_note_device_state_in` since checkpoint audit 11, A11-L5). A reopen between two edges reaches
       the main log at the next edge's reply (Media's pause or play, display power, a mode or preset change, a view
       change). **A reopen after the session's last edge never reaches it** (Media plays on until the Visualizer is
       turned off, a display reload or the exit): the owner's `retire` sends `VIS_STOP` without awaiting it and closes
       the link at once, so the stop's report is read only where a stop is awaited (`EngineWorkerLink.stop`: tests and
       tools). For a long uninterrupted play the reopen line appears at the next pause. The owner does nothing else
       with it: as in process, the Visualizer shows the engine's idle frames until the audio comes back (fade, never
       vanish: the bars go down through the existing silence decay, and the frames never stop).
     - *Measured* (evidence `.artifacts/evidence/architecture/native_core_p2/20261108_p2b_53_devices/
       device_reopen_probe.json`). Setup: the production count, the session's own 90 Hz cadence in process, a loopback
       stand-in with its own delivery thread (no device), three runs per scenario.
       - A default switch the player follows (the new output at 44.1 kHz with six channels), a stream whose thread
         ends, and a stream whose packets fail in the capture callback: reopened 1.99-2.02 s after the event, and
         publishing again 20 ms later. 273-275 frames over ~3.04 s (the cadence never paused). The bars went down to
         0 in the gap and back to 0.99 after. 0 step failures, no session end.
       - The only output unplugged: reopened at 2.0 s, `capture_failed`, 181 frames over the 2.0 s, 0 step failures,
         no session end.
       - The watch's own cost (isolated, the real method on a stand-in engine): 0.41 us per step while the device
         publishes, 0.50 us while it is silent. The first draft looked its logger up on every step (`logging
         .getLogger` takes the logging lock; ~2.5 us). It now looks it up only where it writes.
     - *Tests* (`tests/test_visualizer_engine_worker_device.py`). The production session runs in process on the
       loopback stand-in (its own delivery thread: a device's clock, concurrent with the tick, which the paced source
       is not, A6-L2), with no device. The four device-change cases run with the watch and, as their negative control,
       without it (the count out of reach: the pre-5.3 session).
       - A default switch mid-song is followed by one reopen, on the audio worker's own restart. Without the watch,
         capture stays on the silent output until Media's play edge, which then follows (the in-process trigger,
         shared).
       - A player pinned to the old output: no reopen.
       - A device that raises mid-stream (every packet fails in the capture callback): reopened. Without the watch,
         silent for good and reported healthy.
       - A device whose callbacks stop: reopened once. There is no second reopen while it stays silent; it publishing
         again re-arms the watch, and a later stop is reopened again.
       - The only output unplugged: a device failure (`capture_failed` in the replies), never a worker failure (no
         failed step, no session end), retried at the next capture edge. Without the watch the replies say all is
         well.
       - Digital silence and a pause never reopen; the same quiet output while Media says playing does (positive
         control).
       - The link logs each change of the device state once.
       - Negative controls (`negative_controls.txt` in the evidence directory): with the watch's call removed from the
         step, the five watch cases fail. A watch keyed on the analysis energy that restarts without the stale gate
         reopens on digital silence and fails the silence test. The pre-5.3 link (store, no log) fails the logging
         test.
     - *Off the admission:* unchanged. `restart_stale_capture` has no in-process caller, and the remaining changes are
       on the worker path or are docstrings (`capture_publications`, `TripleBuffer.published`). Production-path frames
       and the owner contract and audio suites pass unchanged. In process keeps today's behaviour (above). Whether to
       wire the same watch into the owner's in-process cadence step is recorded in `Current_Plan.md` (not done here:
       it changes the default path's capture behaviour, which needs this slice's physical check first).
     - *Operator checks* (physical, a real device; run with `--viz-engine-worker`, Media playing, a Visualizer
       showing; main log lines below):
       1. *Default switch:* switch the Windows default output (sound settings or the taskbar's output picker) to
          another device the player follows. Expected: the bars rest for about 2 s, then react on the new output with
          no fade. At the next Media pause the main log shows `[SPOTIFY_VIS][ENGINE_WORKER] The engine worker reopened
          its loopback device after it stopped delivering while playing: 1 reopen(s) this session, 1 delivering
          again`. There is no `Session failed` line and no `Running in process` line.
       2. *Player pinned to the old output* (a player set to a specific device): switch the Windows default. Expected:
          the bars keep reacting throughout, and no reopen line at the next pause.
       3. *Unplug a USB or Bluetooth output that is the default while playing,* with another output left: Windows
          moves the default and the player follows. Expected: as in check 1. Also, no `Session failed` line at the
          next pause or play. A native close failure on an invalidated stream would show there as a session failure
          naming "native release failure"; by reading, PyAudio tolerates a stopped stream, but this is unverified.
       4. *Unplug the only output while playing* (if the player keeps playing): the bars rest. At the next pause:
          `... 1 reopen(s) this session, 0 delivering again` and `[SPOTIFY_VIS][ENGINE_WORKER] The engine worker's
          loopback device is not open; the session keeps running and retries it at the next capture edge`. Plug it
          back in and press play: `... loopback device is open again`, and the bars react. If the player pauses
          itself on the unplug, the watch never counts (Media says paused), and the play after replugging opens the
          device as in process.
       5. *Control, in process* (without `--viz-engine-worker`): check 1 leaves the bars at rest until Media's next
          pause and play (today's in-process behaviour).
       6. *Media playing, nothing rendered here* (checkpoint audit 11, A11-L6): Spotify Connect or casting to another
          device, a player set to a non-default output from the session's start, or a stream still buffering on the
          network. Expected: the bars rest (as in process); about 2 s after each play edge, and once per silent run,
          the worker reopens the loopback device once (one PortAudio terminate and re-initialise, then the default
          opened). Watch for a visible stall in the bars or the Media card at those moments; at the next pause the
          reopen line counts them, with `0 delivering again`.
       7. *A second app on the old default* (a voice chat, a system sound loop) while the player follows a default
          switch. Expected limit: the old endpoint keeps publishing, so the watch never fires and the bars stay on
          the other app's audio until Media's next pause and play (as in process).
     - *Known limits (A11-L6):* "no publication while Media says playing" means "the audio is not here" only when the
       player is the endpoint's only renderer. With nothing rendered locally (check 6) it costs one reopen per silent
       run and one more per capture edge (play, park, activation), each harmless by design (the bars are at rest).
       With another renderer on the old endpoint (check 7) a switch is hidden. The reopen's cost on a real device is
       unmeasured: 20 ms is the stand-in's, while `Pa_Terminate` / `Pa_Initialize` enumerate every WASAPI endpoint
       (Bluetooth included), and whether PyAudioWPatch holds the GIL there (stalling the worker's cadence for that
       time) is unverified.
     - **Left for step 6:** the operator checks above. A real-device reopen timed in the worker, with the cadence's
       step dt across it (A11-L6). The worker's own log lines are still invisible: the main log learns of a reopen
       only at the next edge's reply, and never of one after the session's last edge (A11-L5, above), because there
       is no worker -> main event channel for diagnostics (an unsolicited response or the heartbeat's acknowledgement
       would be one; the supervisor is not changed here). In-process parity (`Current_Plan.md`). Linux
       (`utils/audio_capture_pulse.py`) is unexamined: the watch is backend-neutral, but whether a Pulse monitor
       stream goes quiet or keeps delivering on a sink change was not read.
   - 5.4 Settings: a resolved-settings delta applied to the existing session at a tick boundary (no rebuild per
     slider step); the presentation-config reads moved to logical config so the worker imports QtCore only, at call
     time too (checkpoint audit 5, A5-L2: today an activation loads QtGui through `config_applier.py`'s
     `_color_or_none` `QColor`s; the fresh-spawn probe asserts that and is flipped to "QtCore only after an
     activation" by this slice). From 5.2: replace the interim whole re-activation per preset/settings change with the
     delta; inventory the remaining view inputs the tick reads from the main side (Edit orbit and framed flight on the
     presentation state, Waveform's view span/top, Expanded Visualizer) and forward them as `VIS_SET_VIEW` does the
     layout metrics; Fullscreen Edit's content envelope reads the tick state's Sphere parameters, which the main side
     no longer has on the worker path.
     **Built (8 Nov, with checkpoint audit 7's A7-M1 and A7-M2):**
     - *Inventory (what the worker's capture read from a presentation state it never received):* the view records
       (held-key orbit, framed flight, drag inertia, Auto Rotate: `view_orbit`), the mode's presentation-only controls
       (turn and tilt, framed camera position and lens, scene transform, mirror, finish...; written at runtime by Edit's
       orbit and drag, the camera keys, Home and a preset's activation), the 3D Detail tier, and the reflected wallpaper.
       Waveform Ribbon's camera, `zoom_hold` and `view_span` derive from those (its camera keys are presentation-only
       controls, and the view span from the forwarded layout metrics). Expanded Visualizer: nothing; the display-wide
       route is presentation only and the controller keeps the ordinary metrics the tick reads (already forwarded).
     - *One forwarding path for the view inputs (A7-M2):* `VIS_SET_VIEW` carries, with the layout metrics, the
       presentation inputs that changed since the last send (`logical_edges.presentation_inputs_snapshot`: the records
       and the mode's presentation-only controls, plain data only; `apply_presentation_inputs` on the worker refuses any
       other attribute). Latest wins, at most one in flight, sent at the end of every presentation (so an orbit edge
       reaches the session within one frame; the records are time-parameterised, so the pose at each later step is
       exact) and at once by `QuickDisplayVisualizerOwner.forward_presentation_inputs` (a rig's scripted edge). A
       preset's immediate Auto Rotate is armed once, by the session's commit (as the in-process commit arms it); the
       commit's reply carries the session's view records and the main side adopts them, nothing sent back (checkpoint
       audit 8, A8-L2: it used to arm again at the reply, stepping the turn back by the reply's latency). The values
       are compared with the last send by value (A8-L6: what was sent is held as a detached copy, so an in-place edit
       of a nested list or dict is forwarded; only a changed value is copied). The Fullscreen
       Edit envelopes: Sphere's reads the newest frame's resolved parameters when the main tick state has none (the
       worker path), and the main controller's bar count follows the session's (the configure and commit replies carry
       it), so Extruded Spectrum's envelope and a reconfigure use the target's count.
     - *The reflected wallpaper (A7-M1), decided: the main side completes the frame.* The wallpaper is presentation data
       the owner makes on the GUI thread from the displayed photograph; shipping its pixels to the worker only to have
       them shipped back in the frame would be the wrong owner, so the worker never sees it. The reader mailbox runs a
       frame completion (`PacketMailbox.set_frame_completion`, set by the owner): `backdrop.FrameBackdropCompletion` puts
       the owner's wallpaper (frozen once per wallpaper) and its crossfade into a reflecting frame's parameters (Sphere,
       Extruded Spectrum), exactly where the in-process capture puts them; frames with no wallpaper are untouched (no
       work). With a wallpaper (the common case for these modes) it replaces the two entries only and rebuilds the
       frame around them without re-validation, as the codec builds a decoded frame (A8-L1: it used to re-freeze the
       whole parameter map and re-validate both frames on every frame, 132 / 104 us median, Sphere / Extruded
       Spectrum; now 17 / 15 us, evidence `20261108_audit8_l1_l6_timings/`). One per owner session, released on retire
       and on the fallback (the module-level cache that kept the last wallpaper for the process's life is gone).
     - *Settings deltas, decided:* in process a preset or settings change is an activation (`commit_logical_activation
       (kind="preset")`: the runtime stop, the engine's resets, the crossfade), and the worker path does the same
       (`VIS_SET_MODE` for the current mode); a logical delta that kept the engine's state would differ from in process,
       so none is added. What changes at runtime without an activation is the presentation state (the inventory
       above), and it now reaches the session as a delta between two steps: no `VIS_SET_MODE`, no rebuild, the mode's
       runtime the same object (test). There is no runtime per-slider logical path in process to match (Settings
       changes reach a running display through an activation or a rebuild).
     - *QtCore-only worker (A5-L2):* the presentation colours the capture reads (the shared bar fill and border) are
       held Qt-free, as the (r, g, b, a) a `QColor` froze to in the frame (`config_applier._color_or_none`; the border
       opacity through Qt's 16-bit alpha rounding, `_with_alpha_f`; both checked against `QColor` for every channel
       value and 20,001 opacities). Nothing else in the tick or the presentation config builds a Qt GUI type, so every
       mode's activation in the worker loads QtCore only; the fresh-spawn probe is flipped to "QtCore only after an
       activation" (restoring the `QColor`s fails it). Frames unchanged (the production-path frame test, the identity
       gates).
     - *Gates* (`tests/test_visualizer_owner_engine_worker_inputs.py`): the view gate per 3D mode (Sphere, Extruded
       Spectrum, Extruded Bubble, Neon Lake, Waveform Ribbon) on a real worker process vs in process, frame for frame,
       with the inputs exercised (`owner_worker_gate.identity_script_view`: a reflecting photograph on the rig's unshown
       scene for Sphere and Extruded Spectrum, a held-key orbit, a preset's Auto Rotate, a second orbit): all identical
       (419 frames each); without the forwarded inputs all five differ from frame 73 (the orbit), without the frame
       completion Sphere and Extruded Spectrum differ from frame 0. Also: the wallpaper on the worker's frames (none
       without the completion), a presentation setting step reaching the session without a rebuild (not without the
       forwarding), the Fullscreen Edit envelopes (none for Sphere and a stale bar count with the pre-fix reads), the
       Qt-free colours.
     - **Left for 5.6-5.7:** a GUI-thread edge between two presentations reaches the worker at the next presentation's
       end (at most one frame; frames ticked before it show the previous view, as a tick that ran just before the edge
       would in process); presentation inputs are compared every presentation on the worker path (measured with
       audit 8's fixes: the snapshot and the comparison with the last send together 1.3-20 us for 5-105 attributes,
       Spline Curve to Neon Lake; nothing in process); the frame completion runs where the frame is decoded (on the
       render thread at sync admission: 15-17 us median per reflecting frame with a wallpaper, measured on an unshown
       rig, not with a real window).
   - 5.5 Fail-closed: `session_closed` and heartbeat loss fade the Visualizer (never vanish) and reconfigure once;
     the label-namespace counter owned by the main process for the app's life; the wake sender closed after
     configure; a full wake pipe never blocks the tick. **Done in 5.2:** the namespace counter's owner
     (`engine_worker_link`), the main side's wake sender closed after configure (its end is the session's end),
     `session_closed` / the pipe's end -> hold, fade, reconfigure once, then in process for the run.
     **Built (8 Nov, with checkpoint audit 7's failure items A7-M3, A7-M4, A7-L1..L6):**
     - *No GUI-thread wait (A7-M4).* Every control edge is sent and never awaited (`engine_worker_link`): the link
       registers each correlation with the supervisor's one blocking response listener (`register_response_callback`:
       no poll, no per-request thread) and the reply comes back as a queued Qt signal, applied on the GUI thread; a
       request that could not be sent, a failed reply, or a correlation the supervisor cancels (it retired the worker)
       is a failure, always delivered as an event, never inside the edge that caused it (no re-entrant failure path:
       A7-L2, plus a guard after the replacement's adopt). Edges that need a reply's identity proceed on its event: the
       configure's reply binds render admission (`bind` defers only that part; `sync_present` and the render-thread
       admission present nothing until it), the hidden activation's `VIS_SET_MODE` reply binds the target and
       configures its presentation (the target stays hidden in `waiting_target` meanwhile; a failure while it is in
       flight restores the outgoing Edit and layout profiles and is the session's failure). The first configure never
       waits for the spawn: a worker that is not running is (re)started on a `ThreadManager` IO task (a dead one is
       stopped first, which retires its stale response listener), the requests sent meanwhile wait in the link's
       outbox, in order. The first configure is bounded by the same one-shot deadline as a recovery (A8-L5: fenced by
       its session's label namespace; unanswered, the activation runs in process, not counted for the run), not by
       the heartbeat. Replies are matched by correlation, so a late event for one the link abandoned never answers its
       resend (A8-L4). Found on the way: a session killed between the heartbeat's passes leaves the supervisor's
       worker "running" for a moment, so the replacement's configure can be queued to the dead process and then
       cancelled by the heartbeat's restart; the link sends an unanswered configure (and everything queued behind it)
       once more to the restarted worker (the probe's kill showed it, and the killed-worker test fails without it).
       `VIS_SET_VIEW` is latest-wins state: writes inside one GUI turn coalesce into one queued send, at most one is in
       flight, and the newest view follows its reply (a hidden activation sends it at once, before `VIS_SET_MODE`).
       The owner's stop is sent, never awaited (`retire`), addressed to its session's mapping so a stop that lands
       after another session was configured is a no-op there. `stop` and `feed_for_testing` still wait (tests, tools).
     - *Liveness.* A dead worker is seen by an event: the session's wake pipe ends (the worker held the only writer
       end) and the supervisor cancels the outstanding correlations when it retires the process. A hung-but-alive worker
       is the supervisor's heartbeat's (reused, nothing new): missed heartbeats restart it (bounded:
       `MISSED_HEARTBEAT_THRESHOLD` intervals, then the stop's graceful bound and termination), which ends the pipe and
       cancels the correlations; nothing on the GUI thread waits meanwhile.
     - *A full wake pipe never blocks the tick:* `packet_mailbox.send_wake_byte_without_blocking` (Windows: one
       overlapped write, cancelled when it would wait; POSIX: a non-blocking framed write), the byte dropped and counted
       (`wakes_dropped`): a full pipe means the reader already has wakes pending (it coalesces; latest wins). A pipe
       holds 65,536 one-byte wakes; `send_bytes` blocked the writer there (the test's negative control).
     - *Bounded recovery (A7-M3).* A recovery always enters `recovering` at the failure (the held frame, or nothing
       held, waiting for the replacement's identity), bumps the request serial (a crossfade deadline armed earlier is
       inert in it) and arms the transaction deadline's one-shot (`_on_recovery_deadline`, generation-fenced; never
       armed while the displays are off: the unpark arms it). The reveal gets a deadline of its own: the serial moves
       on again there, so the failure's shot is inert (checkpoint audit 8, A8-M1: until then both shots carried the
       same serial and a healthy replacement slower than the failure's window was retired, the worker off for the run;
       the record's "again at its reveal" did not hold). First expiry, still on the worker: fall back in process once
       (counted for the run); the in-process runtime's publications pace the held frame's fade and the reveal, under a
       second deadline. Second expiry (in process): a reveal that never came, or a held frame nothing paces any more,
       escalates to the generation-fenced reconstruction, exactly as an in-process activation's `waiting_target`
       deadline does (A8-M2: it used to leave the Visualizer faded out for the session with its in-process runtime
       running; the display's reload retires the owner and the rebuilt one fades in). The fallback is contained
       (`_fall_back_in_process` catches and escalates once; nothing reaches Media's or display power's handlers).
     - *Lows.* A7-L1: the failure path never resets the drawn fade (the hold takes the fade actually drawn: 0 after a
       completed fade-out). A7-L3: no frame is held while the displays are off, and a park during a recovery drops its
       held frame, so the replacement reveals from hidden at the unpark. A7-L4: a device that does not open is a device
       failure, not a worker failure: the session keeps running (idle frames, as in process), logs it once per run of
       failures, reports `capture_failed` in its replies, and the next edge that opens capture retries the device; a
       later open clears it. A7-L5: Media's play edge on the worker records its `[VIS_PLAYBACK_EDGE]` T1 (sent) and T2
       (the reply) under the reactivity diagnostics; "parked"/"resumed" is logged on the reply, and only the newest
       display-power edge's reply acts (A8-L3: after OFF then ON, the OFF reply no longer clears the reader with the
       displays back on). A7-L6: a paused switch
       (Oscilloscope -> Bubble, Spectrum -> Sphere) reveals on the same frame with identical frames on both paths
       (`owner_worker_gate.identity_script_paused_switch`; the rig records the phase and fade of every publication).
       A closed reader mailbox now reads as empty (a retire after a failed fallback raised on its released view).
     - *GUI-thread stall, measured (`D:` probe on the real owner and process, below-normal priority; evidence
       `.artifacts/evidence/architecture/native_core_p2/20261108_p2b_55_gui_stall/`):* before -> after, per GUI-thread
       call: the first configure's edge 1,780 ms -> 86 ms (38 ms link setup with the cold import of the worker
       modules, 47 ms the presentation side; the 0.5 s spawn and 1-2 s session build moved off the thread). That is
       not the worst stall after the change (A8-L7): the configure's reply handler costs 161-209 ms on the GUI thread
       (the render-source bind, which in process is `bind`'s 229 ms), so the worst single GUI-thread call of a first
       activation on the worker is about 0.16-0.21 s, not 86 ms. Media's play edge
       0.6 -> 0.1 ms; display power 1.7 -> 0.15 ms; a view drag step 1.3 -> 0.1 ms; the mode commit 27 ms (inside
       `sync_present`) -> 0.9 ms plus the reply's 7.5-13 ms presentation configure; a killed worker mid-edge 2,639 ms
       (the edge) + 1,715 ms (the reconfigure) -> 0.1 ms + 3 ms; a hung worker 21,873 ms (the edge, until the
       heartbeat's restart released it) -> 0.2 ms for three edges, the failure path reached 16.8 s later by the
       heartbeat (production interval). Gate: no control edge over one frame (1/60 s); held in
       `tests/test_visualizer_owner_engine_worker_liveness.py` against a suspended worker. The gate covers the edges
       only, not the reply handlers (the configure's reply above, the commit's presentation configure).
     - *Tests* (`tests/test_visualizer_owner_engine_worker_liveness.py`, each with its negative control shown): the
       full wake pipe (the blocking send never returns); edges against a hung worker (the waiting edge stalls 30 s) and
       the heartbeat ending it, recovered on a fresh worker (shown only with the test's 0.25 s heartbeat, A8-L7: in the
       evidence probe at the production heartbeat the hung case was the probe's second failure, so it ended in
       process; recovery onto a fresh worker after a production-timed hang, ~17 s detection and a restart racing the
       link's own spawn, is unmeasured); a killed worker (without the configure's resend the
       replacement fails and the owner ends in process); a replacement that never publishes (no deadline: frozen in
       `recovering`); a fallback that raises (unguarded: it escapes Media's play edge); a stale crossfade deadline (no
       fence: `deadline:recovering`); A7-L1 (the reset fade flashes), A7-L2 (synchronous failure delivery without the
       guard ends `failed`), A7-L3 (the old hold re-presents the pre-park frame), A7-L5 (logging before the reply logs
       a failed park), A7-L6 (a reveal predicate that waits for a playing frame differs). A7-L4:
       `tests/test_visualizer_owner_engine_worker.py` (the old report closes the pipe). Checkpoint audit 8 (each with
       its pre-fix variant): a slow but healthy replacement gets its own reveal deadline (A8-M1), a recovery that never
       reveals escalates to the reconstruction (A8-M2), a park reply that lands after the unpark never clears the reader
       (A8-L3), a late reply for an abandoned correlation never answers its resend (A8-L4), a first configure that is
       never answered is bounded (A8-L5); in `tests/test_visualizer_owner_engine_worker_inputs.py`: the frame completion
       refreezes nothing per frame and leaves with its owner (A8-L1), a preset's Auto Rotate is armed once by the
       session (A8-L2), an in-place edit of a nested presentation input is forwarded (A8-L6).
     - **Left for 5.6-5.7:** the supervisor starts a dead role without retiring its stale response listener (the link
       stops it first; the supervisor itself is unchanged); a heartbeat restart racing the link's own restart can still
       kill the fresh worker (the resend covers one; a second is a failure, fail closed); the hung-worker bound of an
       established session is the production heartbeat's (~17 s measured) with the held frame frozen meanwhile (the
       first configure is bounded by the 6 s deadline since audit 8); recovery onto a fresh worker after a
       production-timed hang is unmeasured (A8-L7); the reply handlers are outside the one-frame gate (the configure's
       reply 161-209 ms on the GUI thread, the render-source bind); a session whose steps keep failing (the runtime
       retries, A6-M3) still publishes nothing and is not detected; device changes (5.3).
   - 5.6 Cleanup: delete `engine_snapshot.py` and the `snapshot` input; Bubble's spawn on its own generator so no
     gate needs a process-wide seed.
     **Built (8 Nov):**
     - *The snapshot layer, deleted:* `core/visualizer_engine/engine_snapshot.py` and
       `tests/test_visualizer_engine_snapshot.py`; `EngineSession.INPUTS` is `feature`, `lanes`, `live` (no
       `initial_snapshot`, `tick_snapshot` or `VIS_INPUT {"snapshot"}`; the worker's handlers catch `Exception`, as
       `SnapshotContractError` was their only `BaseException`). The surface only the snapshot used went with it:
       `_SpotifyBeatEngine.peek_pre_agc_analysis_spectrum` / `request_pre_agc_analysis_spectrum`, the replay engine's
       peek and `mode_capabilities.reads_analysis_spectrum` (the main side's spectrum rule). Of its gates, "a tick that
       raises closes its session" (audit M2) still guards the live input and is ported
       (`test_visualizer_engine_live.py`); the rest guarded the snapshot itself (the scheduler tap's replay, the
       main side's mode-rule agreement, the contract-miss `BaseException`, the static getter scan against
       `CAPTURED_GETTERS`) and went with it; the live input's identity gates (in process == worker, every mode, off
       the steady state, owner on the worker) are the live path's. `engine_main_cost.py` keeps its in-process
       tick/DSP half (runnable); its snapshot half is reproducible at 4df640b7 and its report stays the 4c record.
       `engine_read_audit.py` (the tick's engine read surface per mode) does not depend on the snapshot and stays.
     - *Bubble's own generator (A2-M2):* `BubbleSimulation(seed=None)` owns a `random.Random` (None: OS entropy, as the
       process RNG seeds at import); every draw, 57 call sites (15 in the spawn helpers, which now take the caller's
       generator, 42 in the simulation), keeps its call, arguments and order and reads it instead of the module
       (Bubble Temporal Fidelity: only the generator's source changed). `seed_generator` re-seeds it (a reset keeps
       the stream). `BubbleFrameRuntime(seed=...)` / `seed_generator` carry the seed to the simulation it builds, and
       `VisualizerRuntimeController.seed_mode_generators(seed)` seeds the mode states built before and after it, per
       controller (only Bubble's runtime draws at random from a live generator: Extruded Bubble's simulation is
       seeded by its runtime, and Bubble's ambient layers and Extruded Bubble's wake use fixed-seed generators). Production never calls it (test: the owner, host binding and worker
       link never seed). The session's `seed` control input seeds its controller (live: the gates pass
       `REPLAY_SEED`, production none; recorded-input sessions default to `REPLAY_SEED`, as every offline replay);
       `deterministic_clock` no longer seeds or restores the process RNG; `configure_offline_controller(seed=
       REPLAY_SEED)` seeds the replay's controller. The gates and replays seed their own controllers: the owner gate's
       in-process owner (after its build, before any tick), `owner_production_replay`, the Bubble Studio evaluator
       (which no longer swaps the app's process-RNG state around its steps) and its recorded-input extract. Bubble's
       tests seed the simulation (`BubbleSimulation(seed=N)`, `sim.seed_generator(N)`) instead of `random.seed(N)`.
     - *Proof (evidence `.artifacts/evidence/architecture/native_core_p2/20261108_p2b_56_bubble_generator/`):* the
       4df640b7 simulation seeded through the process RNG and this one seeded alike: 144 configurations (every stream
       x drift direction, Group Drift on and off, bounce and the three pop modes, 720 ticks of a passage with a hot
       stretch and a silent gap), 103,680 frames identical and the generator states equal at the end (the same draws
       in the same order; `sim_equivalence.json`). Through the session paths, 4df640b7 (an archive copy, deleted) and
       this tree give identical Bubble digests: live sessions in settled and production order, feature and lanes
       sessions (273 frames each), the Studio's recorded-input extract (273) and evaluator (40 instants)
       (`session_paths_digests.json`). Same seed in process and on the worker: `owner_worker_gate` identity Bubble ->
       Oscilloscope and Oscilloscope -> Bubble, 549 frames each, identical (`owner_worker_gate.json`);
       `live_engine_gate --modes bubble oscilloscope`, every scenario on the three shipped clips whole, 27 pairs,
       36,561 frames, 0 mismatching (`live_gate/live_gate.json`). Production: an unseeded `random.Random()` is the
       module's own generator type seeded the way the module seeds itself, and the draws are the same calls in the
       same order, so the distribution is unchanged; each Bubble activation now has its own stream instead of sharing
       the process's with other threads. Negative control (A2-M2): Bubble handed the process RNG (`random` itself)
       makes two seeded sessions diverge (`test_visualizer_engine_live.py`); with the old process-wide seed they were
       equal.
     - *Found:* `test_bubble_reactivity.py::test_group_drift_aligns_non_swirl_bubble_motion[random-x]` holds for
       ~61% of draws (2,000 seeds; Diagonal for all): unseeded, it had passed on the process-RNG state the file's
       earlier seeded tests left behind. Seeded now (seed 2) and recorded in `Current_Plan.md` (not a 5.6 change: what
       Random Group Drift should guarantee is Bubble's owner's call).
     - Ran: `test_visualizer_engine_live.py`, `_live_off_steady`, `_worker`, `_paced`, `_import_weight`,
       `test_visualizer_owner_engine_worker.py`, `_inputs`, `test_visualizer_owner_production_path.py`,
       `test_visualizer_logical_edges_parity.py`, `test_visualizer_audio_source_freshness.py`,
       `test_visualizer_authored_clock.py`, `test_bubble_own_generator.py`, the Bubble suites (reactivity, viewport
       reflow, shape invariance, normal drift, BTF coalescing, ambient, Studio, lifecycle fades, render judder,
       viewport scaling contracts; six repeated runs, no flake), `test_studio_clip_loop.py`,
       `test_waveform_ribbon_source_policy.py`, `test_display_power.py`, `test_sphere_voxel_audio_contract.py`,
       `test_qtquick_visualizer_reactivity_config_parity.py`.
     - **Left for 5.7:** nothing from 5.6.
   - 5.7 Dormancy and diagnostics: the worker exists only while a Visualizer is active and parks with the display;
     the usage sampler and logs include it; the frozen (Nuitka) spawn reaches `visualizer_worker_main` (operator
     check). From 5.2: the worker process stays up after the owner retires (its session closed) until the supervisor
     shuts down; the production supervisor reaches the display manager after the displays initialise, so an owner
     built before it runs in process (logged once).
     **Built (8 Nov, with checkpoint audit 9's A9-L1..L3):**
     - *Lifetime (dormancy), decided: leases, and a hold across display reloads.* The worker was already spawned
       lazily (the first link that finds it not running starts it on an IO task; off the admission nothing imports or
       spawns it). New, `widgets/spotify_visualizer/engine_worker_lifetime.py`: every link holds a lease from its
       configure to its close; when the last one goes the worker is retired at the end of that GUI turn (one queued
       settle event; the retirement is an IO task: `supervisor.stop`, behind the session's queued `VIS_STOP`, then the
       graceful `SHUTDOWN` and the reaping). A link replaced inside one turn keeps the worker (a recovery retires the
       failed link and opens its replacement in the same call); mode and preset activations never touch the link. A
       display reload rebuilds the owner several turns later (teardown, destruction barrier, replacement), so a CUSTOM
       layout commit or a monitor topology change holds the worker from `engine_lifecycle.stop` (reasons
       `custom_edit`, `monitor_topology`) until `_construct_and_start_replacement_runtime` has built the replacement
       (its owner leases the running worker synchronously inside `initialize_displays`); a replacement with no owner on
       the worker ends the hold and retires it. Settings holds nothing: its dialog can stay open for minutes with no
       Visualizer, so the worker is retired with its owner and respawned at the close, off the GUI thread (spawn
       to ready, idle: 0.29 s from the production entry since checkpoint audit 10's A10-M1, 1.6 s before it; the
       first configure now imports what the old preload had loaded, 1.69-1.72 s against 1.03-1.16 s, so ready plus
       configure is about 0.7 s faster, not 1.3 s: A11-L1; the Visualizer shows after that, the configure, the
       session's build, its first presentable frame and its fade; the first configure's deadline bounds it). Why this policy: it is event-driven (no idle timer),
       it never thrashes on the frequent edges (mode/preset changes are in-session; a recovery swaps links within a
       turn; reloads are held) and it leaves no worker where no Visualizer runs. The retirement is fenced: the task
       re-checks under the lifetime lock that no lease or hold arrived and marks the role retiring; a link that
       configures meanwhile spawns afresh, and its start (`serialised_start`) waits for the retirement's stop (one lock
       orders the two IO tasks). A hold that is never ended (a replacement that was never constructed) keeps the
       worker until the next hold ends or the supervisor shuts down; a newer reload replaces an older hold; the exit
       ends it. Off the admission the engine's two calls are a flag read per reload and nothing is imported.
     - *Park (verified, measured):* the existing park covers capture (the engine reference released) and cadence (the
       runtime parked with no wake). A real worker, Spectrum on recorded PCM (evidence
       `.artifacts/evidence/architecture/native_core_p2/20261108_p2b_57_dormancy/dormancy_probe.json`): running 12% of
       a core, ~570 context switches/s; parked 0-15.6 ms of CPU over 10 s (one psutil tick), ~10.6 switches/s, which is
       the idle worker's own: `BaseWorker`'s 100 ms request-queue wait (its parent-death watch, shared with the image
       workers, left as is). 33 threads while a session exists, 29 after it (numpy's and the runtime's pools), flat
       over three more sessions. These figures are from a bare entry (no `main.py` module level, no
       `configure_native_thread_pools` of its own); until A10-M1 the production entry's worker was a different process
       (112 MB RSS idle, the Qt GUI stack loaded), since then it is the same as the bare one at ready (32 MB). In a
       session the bare entry's worker held about 71 MB, so the in-session saving is about 40 MB, not the 80 MB of the
       idle figures (A11-L1). The production worker inside a session (RSS, threads with `OPENBLAS_NUM_THREADS=1`) is
       not measured here.
     - *Diagnostics:* `ProcessSupervisor.get_visualizer_worker_usage_snapshot()` names the worker's PID from supervisor
       state (no OS query); `main.py`'s `--usage` resource provider adds it, and the sampler logs
       `visualizer_worker_pid`, `_cpu_pct`, `_rss_mb` and `_threads` from its own per-process pass (the values it
       already reads for every process in the tree; threads from the heavy refresh's Toolhelp map, carried forward like
       `threads_app`). A named PID the cached tree does not know yet makes that sample a topology refresh (one Toolhelp
       snapshot, ctypes, GIL released) instead of waiting up to eight samples; with no worker (at rest) nothing changes:
       no per-tick psutil call, no new cadence. The logs: the supervisor's start/stop lines carry the PID, the
       lifetime logs every retirement with it, and a session that failed closed reaches the main log as the owner's
       session failure (its reason, the step's exception, is in `VIS_STOP`'s report; the worker process's own logging
       stays as every worker's: `worker_visualizer.log` on perf runs only).
     - *Supervisor (3a): a start retires what a dead role left.* `ProcessSupervisor.start` runs `_retire_dead_role`
       under the role's lifecycle lock: a registered process that died, or a listener with no process, has its
       response listener stopped (its callbacks cancelled with None: the link resends an unanswered configure once) and
       its entry cleaned before `_start_role` replaces the queues. The link no longer stops the role before its start.
     - *Supervisor (3b): one owner of restart decisions for the role.* `CLIENT_RESTARTED_ROLES = {VISUALIZER}`: the
       heartbeat retires a dead or hung engine worker (hung: `MISSED_HEARTBEAT_THRESHOLD` misses, no restart-window
       limit, since a retirement is not a restart) and never starts it; the link starts it on its owner's demand (the
       owner's reconfigure, through its next link). Every heartbeat action is fenced by the judged process's identity
       (`_stop_if_current`, checked and stopped under the lifecycle lock), so a fresh worker started meanwhile is left
       alone; the image roles keep their restart, now fenced the same way (`restart(..., judged=process)`).
     - *Session (3c, A6-M3's open half): a session whose steps keep failing fails closed.* `EngineSession
       .FAILED_STEPS_BEFORE_CLOSE = 60` consecutive failed steps (a count: about 0.67 s at 90 Hz; a successful step
       resets it; a shorter run of failures stays the runtime's retry, as in process. A longer one, which in process
       recovers silently, is a visible recovery here: fade out, reconfigure, fade in. Corrected by checkpoint audit 10,
       A10-L4, which also stopped it counting toward the owner's two strikes for life: a recovery whose reveal
       completes starts the count again; bounded by checkpoint audit 11, A11-M1: at most
       `engine_worker_link.MAX_RECOVERIES_PER_RUN = 3` recoveries per run, and the failure after them keeps the
       Visualizer in process for the run): the session records why, requests a
       park from inside its own step (`VisualizerLogicalRuntime.request_park`, the non-waiting half of `park`) and closes
       its wake sender, so the owner's listener sees the session's end (the existing recovery: hold, fade, reconfigure
       once); a later edge closes it and replies `session_closed`, and `VIS_STOP`'s report carries `failed`.
     - *Wiring order:* `ScreensaverEngine._initialize_display` wires the supervisor into the display manager before
       `initialize_displays` (the Visualizer owner is admitted synchronously inside it and reads the supervisor at its
       configure). For both paths: in process the controller only stores the supervisor, so nothing else changes.
     - *Frozen spawn:* Nuitka's always-on multiprocessing plugin runs the child (`--multiprocessing-fork`) as
       `__parents_main__`, `main.py`'s module code plus a freeze-support call into `multiprocessing.spawn.spawn_main`,
       which unpickles the supervisor's `Process` and calls `core.visualizer_engine.engine_worker
       .visualizer_worker_main` by name. That package was reached only through a function-level import; every build
       family now compiles it explicitly (`--include-package=core.visualizer_engine` in `scripts/venv/build_nuitka.ps1`,
       `build_nuitka_mc_onedir.ps1`, `tools/build_layout.ps1`) and the post-build audit requires
       `core.visualizer_engine.engine_worker` (`tools/frozen_build_audit.py`). The source-run equivalent is tested
       (`tests/test_visualizer_engine_frozen_spawn.py`: a parent whose `__main__` is `main.py`; the child reaches the
       target's loop, ready in 1.45 s). **Found:** that child executes `main.py`'s whole module level first, so the
       production worker process loads QtGui, QtWidgets, QtQuick, QtQml, QtNetwork and QtOpenGL (and the engine's import
       graph) before its target, frozen or not, as the image workers do: the "QtCore only" property holds for the
       worker's own imports, not for its process. **Fixed (checkpoint audit 10, A10-M1):** `main.py` and
       `main_mc.py` skip their application imports while a worker re-executes them
       (`core.spawn_child.importing_parents_main`: the spawn name `__mp_main__` / `__parents_main__`, a frozen
       `__parents_main__` being imported, or multiprocessing's own inheriting marker; stdlib only); the parent runs the
       same module-level statements in the same order. From the production entry, three runs each, an idle,
       unconfigured worker (ready, and memory 1 s after it; evidence
       `.artifacts/evidence/architecture/native_core_p2/20261108_audit10_spawn_cost/`, probe scripts kept there):

       | Worker, parent | Ready | RSS | USS | Private | Qt in the child |
       |---|---|---|---|---|---|
       | engine, `main.py` before | 1.62 s | 112 MB | 83 MB | 91 MB | 7 PySide6 modules, 10 Qt6 DLLs |
       | engine, `main.py` after | 0.29 s | 32 MB | 19 MB | 22 MB | none |
       | image, `main.py` before | 1.56 s | 112 MB | 83 MB | 92 MB | 10 Qt6 DLLs |
       | image, `main.py` after | 0.29 s | 32 MB | 19 MB | 22 MB | none |
       | engine / image, bare parent (reference) | 0.30 / 0.29 s | 31 MB | 18 MB | 21 MB | none |

       The `main_mc.py` parent measures the same as `main.py` after the fix. Medians of three; the ranges are within
       0.06 s and 1 MB except the first engine run before the fix (1.73 s). **In use (checkpoint audit 11, A11-L1):**
       the engine worker's first configure imports its session's graph itself now, 1.69-1.72 s from a bare start
       against 1.03-1.16 s after the old preload, so about 0.6 s of the 1.33 s moved into the first configure; and a
       configured worker in a session holds about 71 MB (bare entry), so the in-session saving is about 40 MB. The
       image workers keep nearly all of it: their target imports no Qt at module level, and the first decode on the
       default Qt path adds `PySide6.QtCore` and `PySide6.QtGui` (`QImage`) with `rendering.image_processor_async`
       (about 0.1 s and 12 MB in a bare interpreter), never QtWidgets, QtQuick, QtQml, the engine or Settings; the
       Pillow path adds nothing. **Operator check:** a frozen build with `--viz-engine-worker` (the Visualizer on the
       worker, its frames shown) and the cold spawn's time to the first configure's reply against the 6 s bound
       (audit 9, A9-L2; ready plus the first configure, which now includes the configure-time imports), plus the
       worker's RSS in `--usage` inside a session. Done 8 Nov (step 6, "Frozen check"): 1.62 s; it found R-176's
       frozen half (Nuitka's icon hook loaded QtGui and QtWidgets) and R-179.
     - *Audit 9:* A9-L1, the first configure's deadline is inert once `retire()` began (`_retiring`, set first: a retire
       whose logical join failed returns before `_retired`). A9-L2, the spawn task belongs to its link: it stops nothing
       (the link no longer stops the role), starts nothing once its link closed, and a worker it started for a link that
       closed meanwhile is retired at once when no lease claims it (`engine_worker_lifetime.retire_if_unused`). A9-L3,
       the recovery's docstring: the reconstruction is as in process, neither capped nor guaranteed (a refused reload
       leaves the owner `failed` at fade 0 with its runtime running; an activation that never reveals reloads about
       every 6 s); recorded in `Current_Plan.md` as a general follow-up, not changed here (the same loop exists in
       process, and no worker failure loops on its own).
     - *Off the admission:* unchanged, except where intended for both paths: the wiring order (above), the
       supervisor's start retiring a dead role's listener and the heartbeat's identity-fenced restart of the image
       roles (both only act on a dead or replaced process), `retire()` setting `_retiring`, the `--usage` line's four
       new fields (`na` at rest) and the build families compiling `core.visualizer_engine`. The production-path frame
       test and the owner contract suites pass unchanged.
     - *Checkpoint audit 10 (8 Nov), fixed:* A10-M1, every worker role skips `main.py`'s (and `main_mc.py`'s)
       application imports (the frozen-spawn record above). A10-L1, a lease is released on every exit path: the link's
       `close()` takes it out first and releases it in a `finally`; the owner's `retire()` retires the link (its
       `VIS_STOP` sent, never awaited) and releases the frame completion before the logical join. A10-L2, under
       `--usage` a named PID the topology refresh cannot find (a dead worker still registered) forces one refresh, not
       one per sample, and a process the sample's own refresh added reports `na` CPU and stays out of `cpu_app_pct`.
       A10-L3, the heartbeat's restart of an image worker checks the judged process's identity, charges the restart
       budget and stops it under the role's lifecycle lock (`_restart_judged`): a role replaced meanwhile is left alone
       and the skip costs no restart. A10-L4, a recovery whose replacement completes its reveal on the worker resets
       the owner's failure count: the second strike is a failure before a recovery completed, not any second failure
       in the owner's life (smallest correct fix: one reset at an existing event; not counting a step-failure
       fail-close would need the reason sent over the pipe and would loop a deterministic step failure until the
       recovery deadline). A recovery that never reveals still falls back at its deadline (counted). The reset had no
       bound until audit 11 (A11-M1, below). A10-L5 (test only):
       an engine-level CUSTOM reload hands the held worker to the replacement's owner. Audit 9 correction: the engine's
       IO pool has four workers (`ThreadManager`'s default), not two (A9-L2's premise; `create_helper_manager` defaults
       to two).
     - *Audit 10, with `--viz-engine-worker` off:* the startup import order is unchanged in the parent (one stdlib
       module, `core.spawn_child`, is imported before the GL error policy); every worker process (the image workers)
       no longer runs the application's imports, from source or frozen. The owner's `retire()` order change touches
       nothing in process (no link, no frame completion: two no-ops move before the join), and the strike reset never
       runs (no worker). Under `--usage` only: one refresh per unseen named PID (none is named at rest) and a newly
       added child's first CPU reads `na` (an image worker's first sample). The supervisor's heartbeat restart of an
       image worker charges a restart only when it restarts.
     - *Checkpoint audit 11 (8 Nov), fixed:* A11-M1, the engine worker's recoveries are bounded per run: each recovery
       takes one of `engine_worker_link.MAX_RECOVERIES_PER_RUN = 3` (`claim_recovery_for_run`, beside the run's
       failure record), and the failure after the last one keeps the Visualizer in process for the run, through the
       second strike's fallback (the held frame fades out, the in-process activation is revealed). A count, not a span:
       a "the replacement ran N frames" threshold bounds only failures that recur faster than it, and a failure
       minutes after each reveal (a fixed point in a song, a device path that fails closed at each reopen) outlives any
       such threshold; a count needs no timer. Three still lets isolated failures recover on the worker a few times a
       run. A genuinely recovered session still starts the two strikes again (A10-L4). A11-L1, the A10-M1 figures are
       an idle worker's (the frozen-spawn record above). A11-L5 and A11-L6 are in the 5.3 record. Off the admission:
       nothing changes (the count is taken only on the worker path).
     - *Tests:* `tests/test_visualizer_engine_worker_lifetime.py`, `tests/test_visualizer_engine_frozen_spawn.py`,
       `tests/test_usage_sampler.py` (two new), `tests/test_frozen_build_audit.py`,
       `tests/test_build_closeout_contract.py` (TestSuite lists each, with its negative control).
     - Ran: the new files, `test_visualizer_engine_paced.py`, `_worker`, `test_visualizer_owner_engine_worker.py`,
       `_liveness`, `_inputs`, `test_visualizer_owner_production_path.py`, the owner contract, edge and retirement
       suites, `test_p2_logical_runtime.py`, `test_engine_lifecycle.py`, `test_runtime_destruction.py`,
       `test_visualizer_logical_edges_parity.py`, `test_display_power.py`, `test_visualizer_engine_import_weight.py`,
       `test_process_supervisor.py`, `_availability`, `test_usage_sampler.py`, `test_worker_parent_death.py`,
       `test_optional_worker_startup.py`, the build/frozen-audit/layout suites and the engine replacement suites
       (Settings round trips, display selection, replacement hang window, S hotkey, no display shown).
     - **Left for step 6 / gate 3:** gate 3's game60 run (lead, operator's yes); the operator's frozen check above
       (now also confirming the frozen worker loads no Qt GUI stack: A10-M1 is proven on the source spawn path and
       on the entry module run as `__parents_main__`, not on a build; timed as ready plus the first configure, A11-L1;
       done 8 Nov, with a confirming build left: step 6's "Frozen check");
       the production worker's RSS and threads inside a session (from source: the Gate 4 record under 6); 5.3's
       operator device checks, the real-device reopen
       timing and what its record leaves (5.3 above, A11-L5/L6); the reply handlers outside the one-frame gate (the configure's reply,
       161-209 ms); the render-thread decode and completion cost with a real window; gate 4's 20 Settings open/close
       and 20 mode switches (done 8 Nov: the Gate 4 record under 6, which found and fixed R-178); `BaseWorker`'s
       100 ms queue wait (10 wakes/s in an idle or parked worker, every role). Carried from 5.5: an established session's hung-worker bound is the production heartbeat's (~17 s, the
       held frame frozen meanwhile), and recovery onto a fresh worker after a production-timed hang is unmeasured (since
       5.7 the heartbeat retires and the owner's next link starts the fresh worker, so the race the 5.5 record named is
       gone, but the timing is not measured).

6. Measurement (gate 3), then decide P2b. P3 note (audit H5): the tagged codec is P2's Python-to-Python transport,
   not a C layout; P3 gets per-mode fixed layouts under new `payload_schema` values, and the native reader validates
   each slot's own identity (ABI 2: per slot, under the slot's seqlock); the header holds the configure-time identity
   and decides nothing.
   - **Gate 4 record (8 Nov): passed** (dormancy and lifecycle; source `e713dd74`, the fix below). Every scenario ran
     with the engine-worker admission on and the same procedure off as the control.
     - *Method:* the invisible MC saver (`tools/visualizer_live_check.py`: recorded music `anything_mixed2`,
       `--load none`, `--usage` as always), Spectrum P1 for the Settings and Visualizer-off runs, the production cycle
       gesture through all nine enabled modes for the switch runs. Added for this gate (`tests/test_live_check_resources.py`):
       `--app-arg=--viz-engine-worker` (the worker plays the clip's first 20 s, looped, on its own audio clock through
       the link's recorded-capture control, never the device), `--mode-switch` (`tools/live_check_mode_switch.py`: the
       double-click cycle, one switch at a time, completion where production persists it) and `--resource-readings`
       (`tools/live_check_resources.py`: read from the parent, never inside the saver: psutil per process, handles by
       object type, pagefile-backed section views, the session's named `srpss_viz_` mappings; every second, and 5 s
       after each reveal or completed switch, so a lifecycle spike is never a reading; slope per cycle and a growth
       verdict). `--roundtrip-memory` now also classifies at each completed switch. Conditions: other processes used
       ~20-27% of the CPU (median) and the GPU was ~40-50% busy throughout (other sessions); every comparison is
       ON against OFF under the same conditions.
     - *Found first and fixed (R-178, `e713dd74`):* with the admission on, the first Settings round trip timed the
       destruction barrier out (8.3 s) and the saver exited (code 1): `retire()` left the controller's layout-metrics
       observer, a bound method of the owner, so owner -> controller -> observer -> owner kept the owner alive. Any
       display reload under the admission (Settings, a CUSTOM commit, a monitor change) did the same. Every earlier
       worker-path test retired the owner through a rig, never the engine's barrier.
     - *20 Settings round trips (every 22 s, readings 1-20; per-cycle tables in the evidence):*

       | Reading | Admission on | Off (control) |
       |---|---|---|
       | Processes (main + the supervisor's workers) | 4 at every reading | 3 at every reading |
       | Engine worker | exactly 1 per reading, 20 distinct PIDs; never 2 at any 1 s sample | none |
       | Named `srpss_viz_` mappings | 1 at every reading, never 2 at any sample | 0 |
       | Frame-sized views, main / worker | 1 / 1 | 0 |
       | Section handles, main / worker | 383 / 1, flat | 382, flat |
       | Handles, main | 1500-1523, +0.17 ± 0.26 a trip (flat) | 1499-1537, +0.51 ± 0.33 (flat) |
       | Handles, worker | 200-202 | - |
       | Threads, main / worker | 46-52 (-0.07 a trip) / 10 | 49-55 (0.00) |
       | RSS / private, main | +4.2 ± 0.5 / +7.0 ± 0.3 MB a trip | +3.2 ± 0.5 / +6.1 ± 0.2 MB a trip |
       | RSS / private, worker | 74.2-75.3 / 58.1-59.5 MB, flat | - |

       All 20 round trips completed on both (`settings` barriers 404-484 ms on, 404-699 ms off; every reveal
       re-frozen, 21 GC freezes for 21 reveals).
     - *20 mode switches (every 12 s; the cycle of all nine modes, two laps and two):*

       | Reading | Admission on | Off (control) |
       |---|---|---|
       | Processes | 4 | 3 |
       | Engine worker | one PID through all 20 switches | none |
       | Named mappings / frame-sized views | 1 / 1 (the session's own; a switch never remaps) | 0 |
       | Section handles, main / worker | 383 / 1, flat | 382, flat |
       | Handles, main | 1522-1535: File +21 on each mode's first visit (lap 1, 418 -> 439), then flat; one pool thread's Event, IoCompletion and Thread later | 1507-1531: File +21 the same way (412 -> 433), then flat |
       | Handles / threads, worker | 201-203 / 10, then 7 from Extruded Spectrum on | - |
       | Private, main (same mode, first -> last lap) | median -37 MB (flat) | median +371 MB (in process; below) |
       | RSS, main (same mode, first -> last lap) | median +78 MB | median +42.5 MB |
       | Private, worker | 58 MB -> 105-115 MB after the first Extruded Bubble / Waveform Ribbon, then flat lap to lap (Oscilloscope 112.4 -> 113.8, Bubble 107.5 -> 107.3) | - |

       Main RSS (the working set) rises over the laps on both paths while the worker path's main private bytes stay
       flat: no commit grows on the worker path. Every switch completed, in 0.85-2.1 s on both.
     - *The worker is retired with its generation:* in all 20 round trips the supervisor's `Stopped visualizer worker`
       and the lifetime's `Engine worker retired ... (pid=N)` come before `Entering settings dialog exec`, and the next
       PID's start after `Settings dialog destroyed` (Settings open retires it; Settings close respawns it; the
       Visualizer is configured on the fresh worker 3-4 s after the dialog closes, 1 s log stamps). The 1 s samples
       show 1.2-2.5 s with no engine worker per round trip and a retired PID never again. The retired session's mapping
       is gone in each gap (three samples show the next session's mapping, created at its configure just before its
       spawn); main's Section handles stay 383, so nothing of an old session is held. A mode switch touches neither the
       process nor the mapping. The worker stops with the image workers at exit.
     - *Visualizer off (Settings round trips at 30, 55, 80 s):* identical. On / off: processes 3 / 3 at every reading,
       no engine worker and no mapping on either (no `[ENGINE_WORKER]` or visualizer-worker log line with the admission
       on), main handles 1474, 1501, 1490, 1492 / 1471, 1506, 1489, 1491, threads 48, 49, 45, 45 / 48, 50, 45, 45,
       Section handles 382 / 382; `--usage` medians: processes 3 / 3, threads 51 / 49, handles 1988.5 / 1984.
     - *Overhead baseline (`tools/overhead_baseline.py`, 1920x1080, ON = the admission activated in the measuring
       process):* ON vs OFF, all 38 cases have identical GL and Python call counts, control-relative GPU within 1.5%
       (median) / 5.4% (p90), "no regressions". Against the 7 Nov pre-P2 reference (`2026-11-07_4bb2b775.json`) with the
       Visualizer off (transitions, surfaces, node path): no rise (Burn 420 -> 407 Python calls, 0b3048b6). Visualizer
       cases: Waveform Ribbon +16 Python calls (6987 -> 7003, Waveform feature work, already open in `Current_Plan.md`)
       and GPU flags for Extruded Bubble and Neon Lake under very different conditions (other processes 3% -> 21%).
     - *Memory, classified as R-175:* the Settings slope is R-175's open shared-path residual, not the worker. With the
       admission on, a census at each reveal (`--roundtrip-memory census,collect`, 8 round trips) finds no worker-path
       object accumulating (no `EngineWorkerLink`, `PacketMailbox`, `SharedMemory`, `mmap` or pipe `Connection` in the
       per-trip type deltas), no retired display-generation object alive, and a collection that frees 62 objects and
       0 MB; each trip adds ~1,710 tuples and ~1,710 weakrefs to the tracked heap, as R-175's own in-process census after
       its fix (~1,790 each). The on/off slope gap (+0.9 MB private, +1.0 MB RSS a trip) is inside the run-to-run spread
       R-175 recorded for the same mode (Spectrum P1 +6.5 / +9.1 MB a trip).
     - *Not the worker's, found by the control (recorded in `Current_Plan.md`):* in process, cycling modes grows main's
       private bytes about 150-250 MB a lap of nine switches and keeps growing lap to lap. Classified: not Python (a
       collection at each switch frees under 1 MB; tracked objects plateau after the first lap), not the heaps (heap,
       heap_large and arenas +30 / +45 / +17 MB over a lap); `private_other` (VirtualAlloc outside the heaps, mostly not
       resident) 629 -> 1376 MB by Waveform Ribbon and 940 MB back at Bubble on lap 2 (601 on lap 1). On the worker path
       main's private bytes stay flat and the worker plateaus.
     - Evidence: `.artifacts/evidence/architecture/native_core_p2/20261108_gate4_dormancy/` (`per_cycle_tables.md`, one
       folder per run with `resource_readings.json`, `resource_samples.jsonl`, `resource_summary.json`, the drivers'
       state and the saver's logs; `console/`; `overhead_flag_off.json` / `_on.json`; frame traces deleted, profile
       copies deleted by the tool).
     - **Left for gate 3:** the game60 run (lead, operator's yes). Before it, the live check's age chain on the worker
       path: the main process's frame trace has no publish events for worker frames (revisions/s 0, publish -> swap and
       the logical tick's GIL share empty), so gate 3's frame-age comparison needs the worker's publish time in the trace
       (each slot carries its frame's produced time). The production worker in a session, from source: 74-75 MB RSS,
       58-59 MB private and 10 threads with Spectrum, 90-130 MB RSS and 7-10 threads across the modes (the frozen
       build's figures: the frozen check below). Everything 5.7 left above except gate 4.
   - **Frozen check (8 Nov, lead; the operator check of step 6): the worker path runs frozen; two defects found and
     fixed, a confirming build is next.** The GitHub Remote build of `5fb8dab7` (A10-M1 included, R-178 not), the
     compiled diagnostic `release/diagnostic/SRPSS_Diagnostic.scr --viz-engine-worker`, a visible saver run of 90 s
     ended by a key press, its process tree sampled from outside every ~1.2 s (psutil: RSS, USS, threads, mapped Qt
     DLLs). The log's `entrypoint=main_diagnostic` is the flavour chosen by the published file's name; the binary's root
     module is `main.py` (the report compiles `__main__` and `__parents_main__` from it; `main_diagnostic.py` is not in
     the build).
     - *Cold start:* the first configure took 1.62 s (T1 -> T2), inside its 6 s bound (A9-L2). A switch to Waveform
       Ribbon committed on the worker; no fallback to in process.
     - *A10-M1 holds frozen:* no worker mapped Qt6Quick, Qml, Network or OpenGL; the engine worker had no Qt at all at
       its first sample, before its configure (97.9 MB RSS, 33.3 MB USS, 6 threads).
     - *Engine worker in a session:* Spectrum 140.7-142.1 MB RSS, 57.1-58.4 MB USS, 11-14 threads; after the switch to
       Waveform Ribbon a sawtooth of 158-265 MB RSS / 70-177 MB USS every ~3.6 s, 12 threads (`--usage`: 81.0 MB at
       spawn, 142.1 with Spectrum, 286.2 and 276.9 with Waveform Ribbon; its 6 threads are the sampler's heavy refresh
       at spawn, carried forward by design). The RSS is not comparable with the source figures: a frozen child with no
       Qt and no work holds 78-95 MB RSS but only 15-21 MB USS (two other spawn children of the run, most likely the
       feed parser's pool), the compiled executable's own shared pages. USS is: 57-58 MB frozen against 54-55 MB from
       source with Spectrum (the worker's handler in a fresh interpreter, recorded PCM).
     - *Found 1, Qt GUI DLLs in every worker that imports Qt (R-176's frozen half, fixed `601f8feb`):* the engine
       worker mapped `Qt6Core.dll`, `Qt6Gui.dll` and `Qt6Widgets.dll` from its first configure on (QtCore only from
       source), the image and prefetch workers the same three from their first Qt-path decode (QtCore and QtGui from
       source). Not our code: Nuitka's PySide6 plugin, given the executable icon, appends `import PySide6.QtWidgets`
       and `from PySide6.QtGui import QIcon, QPixmap, QImage` (a `QApplication` icon wrapper) to the `PySide6`
       package's post-load trigger, which runs on the first PySide6 import of every compiled process
       (`nuitka/plugins/standard/PySidePyQtPlugin.py`, `createPostModuleLoadCode`; the build report's
       `PySide6-postLoad` uses `PySide6.QtWidgets` and `PySide6.QtGui`). The other candidates are ruled out from
       source: the engine graph and a Waveform Ribbon activation import `PySide6.QtCore` only (first through
       `widgets/spotify_visualizer/__init__.py` -> `beat_engine`), and every mode's pickled activation unpickles with no
       Qt module at all. Nuitka 4.2 has no option for the hook, and `main.py` sets its own icon from `SRPSS.ico`; a
       user plugin both Windows build workers pass with the icon (`tools/nuitka_worker_qt_plugin.py`) removes every Qt
       GUI import from that trigger, and the frozen audit refuses a report whose PySide6/QtCore load triggers import
       one (the 8 Nov reports are refused). Measured from source, the hook's imports add ~5.5 MB RSS and ~2 MB USS to a
       QtCore-only process: a contract breach, a small cost; most of the frozen RSS above is the executable's pages.
     - *Found 2, the Waveform Ribbon sawtooth (R-179, fixed `49203808`):* the frame codec's recursive closures left one
       reference cycle per frame holding its buffers until the next cyclic collection; the same sawtooth reproduces
       from source (84-155 MB RSS) and is flat after the fix (85 MB RSS / 60 MB USS; Extruded Bubble 57-58 MB USS).
     - *Not exercised:* Settings (the build predates R-178, so every Settings round trip on the worker would have exited
       the saver).
     - *Next build (lead, GitHub Remote of a commit with both fixes and R-178):* the build log names the removal
       (`srpss-worker-qt: Removed from 'PySide6' post-load ...: Loading Qt application icon from Windows resources.`, no
       "nothing imported" warning) for both families; the frozen audit prints `PySide6/QtCore load triggers import no
       Qt GUI module` and the report's `PySide6-postLoad` uses `PySide6` and `PySide6.QtCore` only; the same sampled run
       shows the engine worker with `qt6core.dll` only, the image workers with `qt6core.dll` and `qt6gui.dll` only, and
       the engine worker's RSS/USS flat across Waveform Ribbon; the app's window icon (taskbar, Settings) and the
       `.scr`'s Explorer icon unchanged; then one Settings round trip on the worker.
     - Evidence: `.artifacts/evidence/architecture/native_core_p2/20261108_frozen_diagnostic_check/`
       (`process_samples.json`, `usage_samples.log`, `worker_log_lines.log`, the sampling script).
   - **Frozen check 2 (8 Nov, operator; build of `098b3f0e`, 5 min, two displays, switches, Settings, the Studio,
     presets): found 3, R-180, the reload fixed.** At 19:46:14 a switch to Neon Lake committed on the worker; the
     render thread's first preparation unit, the basin program's link with the new build's cold NVIDIA cache (the cache
     is per executable path), held the GUI thread ~7 s in Qt's sync (clock gap 7621 ms, every display), and the 6 s
     activation deadline, overdue, fired the moment it returned: `deadline:waiting_target`, a full CUSTOM reload for a
     live target. Screen 0's `scene_fps=2.08 dt_max_ms=1000` beforehand is normal (no Visualizer there: it renders only
     on change). Not the worker path: from source with a nonce forcing the cache miss the basin link took 6.1 s (worker)
     and 6.4 s (in process) and both reloaded the same way; warm it is 39 ms. Fixed by the activation deadline reading
     the committed target's render progress (extended while it advances, at most 4 times; silent targets still fail)
     and the prepared reveal's bound running from the last completed unit. Cold after the fix: Neon Lake completed in
     8.5 s (worker) / 8.0 s (in process) with one extension and no reload; Extruded Bubble 4.6 / 4.5 s, Waveform
     Ribbon 4.2 / 3.9 s; warm 1.55-1.94 s for all three either way. The ~6 s freeze itself is now paid once per
     machine and driver, not per build: the app-owned program binary cache (R-180 "Follow-up: the freeze").
     - *Next frozen run should show:* either the first Neon Lake switch logs `[GL_PROGRAM_CACHE] Neon Lake basin
       linked cold ... saved` with `Activation slow but alive ... deadline extended (1/4)` and a clock gap of about
       6-7 s (the cache had no entry for these sources and this driver), or neither line and no gap (it had one, a
       source run's included); never `MODE_ACTIVATION_FAIL` or a `visualizer_activation_failed` reload; the switch
       completes with a fade-in, and a second run of the same build links nothing cold.
     - Evidence: `.artifacts/evidence/architecture/native_core_p2/20261108_frozen_diagnostic_check2/` (the operator's
       logs and `process_samples.json`); the source reproduction's numbers are in R-180.

## Risks

- **Import weight in the worker:** the tick modules import Qt (`QObject` in the beat engine, settings helpers). The
  worker must import QtCore at most; P2a keeps the beat engine in the main process, so the first worker imports only the
  tick and mode runtimes. Measured 8 Nov: the logical runtime, the tick pipeline, render state, the ABI, the codec and
  all eight mode frame runtimes import QtCore only (no QtGui/QtQml/QtQuick); about 0.9-1.1 s cold and ~350 modules
  each. `tests/test_visualizer_engine_import_weight.py` pins it. A frozen build adds what the compiler injects: Nuitka's
  PySide6 plugin appended QtWidgets and QtGui imports to the first PySide6 import of every compiled process (R-176's
  frozen half); `tools/nuitka_worker_qt_plugin.py` removes them and the frozen audit refuses a build that has them.
- **The tick still reads presentation config (8 Nov; the QtGui part resolved by 5.4):** the logical capture reads
  Spectrum's decoration fades and colours, the Oscilloscope/Bubble spec parameters and the 3D modes' view from the
  presentation state, so the worker configures a presentation state of its own: a copy the main side owns (configured
  from the same activation's `presentation_kwargs`, then kept current by `VIS_SET_VIEW`'s forwarded presentation
  inputs, latest wins), with the wallpaper completed on the main side. 5.4 kept the reads where they are and made the
  presentation config Qt-free instead of moving them into the logical config (the colours the capture reads are the
  tuples a `QColor` froze to): every activation in the worker loads QtCore only (the fresh-spawn test), frames
  unchanged. Moving the reads into the logical config remains the cleaner long-term shape (one copy); it is not
  needed for P2's gates.
- **Process-unique labels across worker generations (8 Nov, resolved):** Extruded Bubble numbers its drift families
  from a process-wide counter that the renderer uses as a geometry cache identity. Every `EngineSession` takes a
  `label_namespace` from the main process (>= 1 in production, a monotonic counter never repeated across sessions or
  restarted workers) and numbers from `namespace << 32`; the main process's own counter stays far below, and
  namespace 0 keeps the in-process numbering for the identity gates. Production wiring passes a fresh namespace on
  every `VIS_CONFIGURE` (`tests/test_visualizer_engine_worker.py`; since 5.2 the counter is
  `engine_worker_link.next_label_namespace`, owned by that module for the app's life).
- **The GUI wake (8 Nov; audit C1 fixed the same day):** in process the mailbox wakes the GUI on its
  empty -> populated edge (one lock serialises publish and take). Across processes an edge cannot be derived from the
  reader's acknowledgement, which lands only after decoding (a publish in between was mistaken for unread and never
  woken again), so the writer sends one byte per publish down a `multiprocessing.Pipe` (handed to the worker in
  `VIS_CONFIGURE` as `wake`); the reader's `listen_for_wakes` thread blocks on the pipe and runs the owner's wake
  emitter, which coalesces. Never a poll; closing the mailbox ends the thread (`tests/test_visualizer_engine_worker.py`:
  one byte per publish; a free-running writer at ~165 Hz against a stalling reader never strands or tears a frame).
- **Hidden GUI-thread reads inside the tick:** every attribute the tick reads from the owner/widget must become a
  control input. The audit for step 4 lists them from `logical_tick`'s reads; a missed one shows up as an identity
  failure only where the tick lets the read's error propagate. Engine reads now fail with `SnapshotContractError`
  (never swallowed) and a static scan pins them; the fence's read was the one miss (audit H3, fixed). Owner/widget
  reads and the paused, resume, re-entry and mode-switch paths still need the 4b gates.
- **Two copies of state during a switch:** the main process must never keep a stale tick-side copy; one owner of each
  piece of state, the worker for logical state.
- **Memory:** a second Python with numpy, QtCore and (until the presentation-config reads move) QtGui: measured 8 Nov
  64 MiB RSS idle, 84 MiB with a Spectrum session, 129 MiB with Extruded Bubble; recorded in the dormancy/usage
  receipts.
- **Latency:** at most one tick of extra control latency (applied at the next boundary) and one memcpy per frame on the
  read; frame age is measured at gate 3.
