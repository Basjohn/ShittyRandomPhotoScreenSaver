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
     production engine's own order, `free`). A step that raised fails the session closed: nothing more is ticked or
     published and the failure is in the report (reporting it to the owner unprompted, the fade and the reconfigure
     are 5.5). The recorded-PCM identity gates keep `cadence="input"` (one tick per input, deterministic); a paced
     session refuses `tick`.
     - *Audio on the audio clock, without a poll:* `recorded_capture.PacedPcmSource` holds the recording's continuous
       PCM (`pcm_from_capture_histories`: the capture histories' new samples in order; the stream loops) and at each
       cadence edge hands over the whole device blocks the audio clock produced since the previous edge (elapsed
       deadline time x rate, in the negotiated block size, the remainder carried; a late edge hands over several, as a
       device's queued callbacks), through `RecordedCaptureBackend.offer` (the worker's own capture callback; a block
       offered while capture is closed is not captured). Nothing is due while capture is closed or Media is paused
       (the playhead holds), and a capture (re)open restarts the clock (the backend's `on_started`), so an unpark
       delivers no burst for the parked gap. It is not a poll and not a timer: it has no thread, never waits and wakes
       nothing; it runs only inside the cadence's own step, which the runtime wakes for anyway, and its clock is that
       step's deadline timestamp. (A feeder thread sleeping to each block's due time would be a second timer; a
       device's own clock is slice 5.3.)
     - *Gate:* `tests/test_visualizer_engine_paced.py` and `tools/visualizer_replay/live_engine_gate.py --paced`: a
       free-running session per mode, the reader taking the newest frame per wake on its own thread and then stalling
       40 ms (a slow GUI; the wake listener only sets an event, the owner's emitter): no exception or step failure, one
       frame per step at the cadence, coalescing observed (taken < published), the newest frame reached by a wake
       after the stop, revisions only advance, 0 torn reads, the audio delivered >= 97% of the paced audio time and
       the paced time >= 80% of the run. Also: the cadence parks with the display (no frame while parked, capture
       reopened, no burst), a mode switch restarts it on the new activation, a failing step publishes nothing more.
       Negative controls: a writer held by its reader (the cadence falls to the reader's rate), one block per edge (the
       audio falls behind the clock), and mutations: no cadence start, no rebase at a reopen (the park test's burst),
       the pre-C1 wake rule (the worker-process gate strands a frame). **Result (8 Nov, 3 s per mode in the
       `WorkerType.VISUALIZER` process, below-normal priority):** all nine modes OK: 270-272 frames each at 89.5-90.1
       Hz of 90, one frame per step, 0-1 skipped deadlines, the stalling reader took 65-66 (coalesced), the last frame
       taken by a wake every time, 0 torn reads, audio delivered 2.997-3.008 s of 3.000-3.011 s paced, no failure;
       32 s (`.artifacts/evidence/architecture/native_core_p2/20261108_paced_gate/paced_gate.json`).
     - *Not in 5.1:* the production owner on the worker (5.2); the wake pipe's backpressure (a reader process whose
       listener stops draining fills the pipe, and `send_bytes` would then block the cadence: 5.5's "a full wake pipe
       never blocks the tick"; the gate's listener drains continuously); a failed session reporting itself unprompted
       and parking its cadence (5.5: today its steps return at once until the owner stops it).
   - 5.2 The owner on the worker: one code path in `quick_display_visualizer_owner.py` that sends the
     `logical_edges` edges to the worker instead of running them, admitted by a code-level admission in
     `core/diagnostics/experiment_flags.py` (never an environment flag) until gate 3 accepts it; the in-process path
     stays the default and the fallback.
   - 5.3 The live device in the worker: capture opens there; Media's playback truth stays the one owner of
     "playing" (sent as an edge); audio device changes, COM initialisation on the worker's capture lane, capture
     failure reported as a crash.
   - 5.4 Settings: a resolved-settings delta applied to the existing session at a tick boundary (no rebuild per
     slider step); the presentation-config reads moved to logical config so the worker imports QtCore only, at call
     time too (checkpoint audit 5, A5-L2: today an activation loads QtGui through `config_applier.py`'s
     `_color_or_none` `QColor`s; the fresh-spawn probe asserts that and is flipped to "QtCore only after an
     activation" by this slice).
   - 5.5 Fail-closed: `session_closed` and heartbeat loss fade the Visualizer (never vanish) and reconfigure once;
     the label-namespace counter owned by the main process for the app's life; the wake sender closed after
     configure; a full wake pipe never blocks the tick.
   - 5.6 Cleanup: delete `engine_snapshot.py` and the `snapshot` input; Bubble's spawn on its own generator so no
     gate needs a process-wide seed.
   - 5.7 Dormancy and diagnostics: the worker exists only while a Visualizer is active and parks with the display;
     the usage sampler and logs include it; the frozen (Nuitka) spawn reaches `visualizer_worker_main` (operator
     check).

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
  namespace 0 keeps the in-process numbering for the identity gates. Production wiring must pass a fresh namespace on
  every `VIS_CONFIGURE` (`tests/test_visualizer_engine_worker.py`).
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
