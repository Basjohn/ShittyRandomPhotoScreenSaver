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
   **Live inputs: the lossless engine snapshot (built 8 Nov):** `FeatureFrame` is the replay contract, not the live
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
     the replay seed, production none. A tick that raised closes its session (`session_closed`, audit M2).
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
     process-wide seed (A2-M2); the main-process listener thread's wake cost counted in gate 3.
   - **Deleted when P2b lands:** `core/visualizer_engine/engine_snapshot.py`, the `snapshot` session input and its
     tests and tools (`engine_main_cost.py` stays as the record of the decision).
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
       application, the main-side mailbox clear on park, fail-closed fades), and Bubble's own generator (A2-M2).
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
   session input are deleted when P2b lands.
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
     **Left:** audio device changes (a default-device switch or an unplugged device mid-session: today the audio
     worker's wake-driven restart on resume, nothing reported to the owner), a device that opens and then goes silent
     or stale (not a failure today), and the physical check on a real device (operator).
   - 5.4 Settings: a resolved-settings delta applied to the existing session at a tick boundary (no rebuild per
     slider step); the presentation-config reads moved to logical config so the worker imports QtCore only, at call
     time too (checkpoint audit 5, A5-L2: today an activation loads QtGui through `config_applier.py`'s
     `_color_or_none` `QColor`s; the fresh-spawn probe asserts that and is flipped to "QtCore only after an
     activation" by this slice). From 5.2: replace the interim whole re-activation per preset/settings change with the
     delta; inventory the remaining view inputs the tick reads from the main side (Edit orbit and framed flight on the
     presentation state, Waveform's view span/top, Expanded Visualizer) and forward them as `VIS_SET_VIEW` does the
     layout metrics; Fullscreen Edit's content envelope reads the tick state's Sphere parameters, which the main side
     no longer has on the worker path.
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
       outbox, in order. Found on the way: a session killed between the heartbeat's passes leaves the supervisor's
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
       armed while the displays are off: the unpark arms it), again at its reveal. First expiry, still on the worker:
       fall back in process once (counted for the run); the in-process runtime's publications pace the held frame's
       fade and the reveal, under a second deadline. Second expiry: a reveal that never came leaves the Visualizer faded
       out, logged, and requests admitted (a later crossfade fades out from the drawn fade, `_fade_out_from`: 1.0 in
       process, so in-process frames are unchanged); a held frame nothing paces any more escalates to the
       generation-fenced reconstruction. The fallback is contained (`_fall_back_in_process` catches and escalates once;
       nothing reaches Media's or display power's handlers).
     - *Lows.* A7-L1: the failure path never resets the drawn fade (the hold takes the fade actually drawn: 0 after a
       completed fade-out). A7-L3: no frame is held while the displays are off, and a park during a recovery drops its
       held frame, so the replacement reveals from hidden at the unpark. A7-L4: a device that does not open is a device
       failure, not a worker failure: the session keeps running (idle frames, as in process), logs it once per run of
       failures, reports `capture_failed` in its replies, and the next edge that opens capture retries the device; a
       later open clears it. A7-L5: Media's play edge on the worker records its `[VIS_PLAYBACK_EDGE]` T1 (sent) and T2
       (the reply) under the reactivity diagnostics; "parked"/"resumed" is logged on the reply. A7-L6: a paused switch
       (Oscilloscope -> Bubble, Spectrum -> Sphere) reveals on the same frame with identical frames on both paths
       (`owner_worker_gate.identity_script_paused_switch`; the rig records the phase and fade of every publication).
       A closed reader mailbox now reads as empty (a retire after a failed fallback raised on its released view).
     - *GUI-thread stall, measured (`D:` probe on the real owner and process, below-normal priority; evidence
       `.artifacts/evidence/architecture/native_core_p2/20261108_p2b_55_gui_stall/`):* before -> after, the worst single
       GUI-thread call: the first configure 1,780 ms -> 86 ms (38 ms link setup with the cold import of the worker
       modules, 47 ms the presentation side; the 0.5 s spawn and 1-2 s session build moved off the thread); the
       configure's reply 161-209 ms (the render-source bind, which in process is `bind`'s 229 ms); Media's play edge
       0.6 -> 0.1 ms; display power 1.7 -> 0.15 ms; a view drag step 1.3 -> 0.1 ms; the mode commit 27 ms (inside
       `sync_present`) -> 0.9 ms plus the reply's 7.5-13 ms presentation configure; a killed worker mid-edge 2,639 ms
       (the edge) + 1,715 ms (the reconfigure) -> 0.1 ms + 3 ms; a hung worker 21,873 ms (the edge, until the
       heartbeat's restart released it) -> 0.2 ms for three edges, the failure path reached 16.8 s later by the
       heartbeat (production interval). Gate: no control edge over one frame (1/60 s); held in
       `tests/test_visualizer_owner_engine_worker_liveness.py` against a suspended worker.
     - *Tests* (`tests/test_visualizer_owner_engine_worker_liveness.py`, each with its negative control shown): the
       full wake pipe (the blocking send never returns); edges against a hung worker (the waiting edge stalls 30 s) and
       the heartbeat ending it, recovered on a fresh worker; a killed worker (without the configure's resend the
       replacement fails and the owner ends in process); a replacement that never publishes (no deadline: frozen in
       `recovering`); a fallback that raises (unguarded: it escapes Media's play edge); a stale crossfade deadline (no
       fence: `deadline:recovering`); A7-L1 (the reset fade flashes), A7-L2 (synchronous failure delivery without the
       guard ends `failed`), A7-L3 (the old hold re-presents the pre-park frame), A7-L5 (logging before the reply logs
       a failed park), A7-L6 (a reveal predicate that waits for a playing frame differs). A7-L4:
       `tests/test_visualizer_owner_engine_worker.py` (the old report closes the pipe).
     - **Left for 5.6-5.7:** the supervisor starts a dead role without retiring its stale response listener (the link
       stops it first; the supervisor itself is unchanged); a heartbeat restart racing the link's own restart can still
       kill the fresh worker (the resend covers one; a second is a failure, fail closed); the hung-worker bound is the
       production heartbeat's (~17 s measured) with the held frame frozen meanwhile; a session whose steps keep failing
       (the runtime retries, A6-M3) still publishes nothing and is not detected; device changes (5.3).
   - 5.6 Cleanup: delete `engine_snapshot.py` and the `snapshot` input; Bubble's spawn on its own generator so no
     gate needs a process-wide seed.
   - 5.7 Dormancy and diagnostics: the worker exists only while a Visualizer is active and parks with the display;
     the usage sampler and logs include it; the frozen (Nuitka) spawn reaches `visualizer_worker_main` (operator
     check). From 5.2: the worker process stays up after the owner retires (its session closed) until the supervisor
     shuts down; the production supervisor reaches the display manager after the displays initialise, so an owner
     built before it runs in process (logged once).

6. Measurement (gate 3), then decide P2b. P3 note (audit H5): the tagged codec is P2's Python-to-Python transport,
   not a C layout; P3 gets per-mode fixed layouts under new `payload_schema` values, and the native reader validates
   each slot's own identity (ABI 2: per slot, under the slot's seqlock); the header holds the configure-time identity
   and decides nothing.

## Risks

- **Import weight in the worker:** the tick modules import Qt (`QObject` in the beat engine, settings helpers). The
  worker must import QtCore at most; P2a keeps the beat engine in the main process, so the first worker imports only the
  tick and mode runtimes. Measured 8 Nov: the logical runtime, the tick pipeline, render state, the ABI, the codec and
  all eight mode frame runtimes import QtCore only (no QtGui/QtQml/QtQuick); about 0.9-1.1 s cold and ~350 modules
  each. `tests/test_visualizer_engine_import_weight.py` pins it.
- **The tick still reads presentation config (8 Nov):** the logical capture reads Spectrum's decoration fades and
  colours and the Oscilloscope/Bubble spec parameters from the presentation state, so the worker configures both
  sides and loads QtGui for `QColor` at the first activation (never Quick, QML or Widgets; the fresh-spawn test reports
  the modules at spawn and after the first activation, A5-L2). Move those reads into the logical config (work order 5
  slice 5.4), so the worker imports QtCore only.
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
