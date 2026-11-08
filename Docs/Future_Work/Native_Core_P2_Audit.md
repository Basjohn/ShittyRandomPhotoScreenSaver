# Native core P2: audit of work orders 1-4 and the plan for 5-6 (8 Nov 2026)

Read-only audit of `core/visualizer_engine/`, the engine changes in `beat_engine.py` / `feature_replay.py`, the
tick, the tests, the gate tool and `Native_Core_P2_Engine_Design.md`. Every finding gives the claim it contradicts,
the evidence (source line or a probe run against the working tree), a failure scenario and a fix or the proof that
would close it. Probes were throwaway scripts (deleted); their results are quoted. Focused tests run clean:
`test_visualizer_engine_packet_abi/packet_mailbox/frame_codec` 33 passed, `_snapshot` 13 passed, `_worker` +
`_import_weight` 16 passed.

Measured here (shipped clip `growing_pains`, 2 s, 182 frames, `ProductionLaneEngine`, one process, this machine):

| Mode | in-process tick p50 / p90 | main-side capture p50 | pickle p50 | snapshot size | worker tick p50 | main decode p50 | request->response round trip p50 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Spectrum | .34 / .48 ms | .25 ms | .08 ms | 5.2 KiB | .55 ms | .12 ms | 1.66 ms |
| Oscilloscope | .45 / .64 | .20 | .09 | 21.0 KiB (waveform history) | .68 | .08 | |
| Sphere | .33 / .52 | .20 | .06 | 4.9 KiB | .45 | .11 | |
| Extruded Spectrum | .35 / .50 | .24 | .08 | 5.1 KiB | .53 | .11 | |
| Neon Lake | .69 / .91 | .24 | .07 | 4.8 KiB | 1.08 | .32 | |
| Spline Curve | 1.80 / 2.38 | .22 | .07 | 4.7 KiB | 2.17 | .20 | |
| Bubble | 2.02 / 3.05 | .25 | .08 | 5.3 KiB | 2.39 | .22 | |
| Waveform Ribbon | 1.83 / 2.66 | .25 | .07 | 4.9 KiB | 2.58 | .35 | 3.90 ms |
| Extruded Bubble | 2.07 / 2.78 | .25 | .08 | 5.0 KiB | 3.60 | .54 | 4.00 ms |

Worker process RSS: 64 MiB idle (no session), 84 MiB with a Spectrum session, 129 MiB with Extruded Bubble, 103 MiB
with Waveform Ribbon (QtCore + QtGui + numpy + the mode runtimes).

## Critical

### C1. The cross-process GUI wake is lost: the display stops updating until something else reads the mailbox

- **Claim:** design doc, Risks, "The GUI wake (8 Nov, resolved)"; `packet_mailbox.py` docstring, "a GUI wake only on
  the empty -> populated edge".
- **Evidence:** `core/visualizer_engine/packet_mailbox.py:86-105` decides the wake from
  `self._writer.consumed_sequence` (shared memory, written by the reader) and `self._unread`; the reader writes
  `consumed_sequence` only in `_consume` (`:133-138`), after `read_latest` accepted the slot *and* after
  `frame_codec.decode`. In process (`role="both"`) one lock serialises publish and take, so the window does not exist;
  across processes each side has its own lock. Probe (two mailboxes on one mapping, `peek()` standing for the reader
  between accept and acknowledge): `writer.publish(1)` wakes; `reader.peek()`; `writer.publish(2)` sees
  `consumed == 0 < 2`, no wake; `reader.take()` acknowledges 2; `writer.publish(3)`, `publish(4)`: `consumed == 2 <
  4`, no wake, ever. Result: `wakes=1 (expected 2), newest unread frame waiting with no wake: True`.
- **Scenario:** the owner's wake (`quick_presentation_sync.py:206`, `sync_latest -> take()`) lands while the worker
  publishes the next frame (the decode takes .1-.5 ms; the worker publishes every 6-11 ms, so a few percent of frames
  hit the window). From then on the writer believes the slot is still unread and never sends another byte; the
  reader took its frame and waits for a wake. No poll exists by design, so the Visualizer freezes on its last frame
  while the worker keeps ticking. `test_a_worker_frame_wakes_the_owner_across_processes` cannot see it: it is
  strictly request -> response -> take, one frame at a time.
- **Fix:** do not derive the edge from a value the other process writes late. Either (a) the writer sends one byte on
  *every* publish and the reader side coalesces (the Quick emitter already coalesces queued wakes; 90-165 bytes/s is
  nothing), or (b) the reader acknowledges inside `read_latest` at accept *and* after every `take` re-checks
  `has_unread()` and runs the wake callback itself. (a) is simpler and has no ordering argument to make. Add a
  free-running test: writer at 165 Hz in a child, reader taking at 60 Hz with random 0-20 ms stalls for 10 s; assert
  every published sequence is eventually followed by a take within one reader period and no unread frame is stranded
  at the end.

### C2. The seqlock reader reads the sequence words in the writer's order, so a torn slot can be accepted

- **Claim:** `packet_abi.py` docstring, "a slot whose begin is odd, or whose begin and end differ, is torn and is
  never accepted"; design doc gate 1 (byte-identical packets).
- **Evidence:** writer store order (`packet_abi.py:141-146`): `sequence_begin` odd, payload, `sequence_begin` even,
  `sequence_end`, `latest_sequence`. Reader order (`:184-187`): `sequence_begin` (in `_SLOT_HEAD`), payload copy,
  `sequence_end`. A seqlock reader must read the word the writer writes *last* first and the word the writer writes
  *first* last; this reader does the opposite. Probe (the writer's first two stores for frame D into frame A's slot,
  with the reader having already read `begin == A`): `reader would accept torn payload: True payload: b'DDDDDDDD'`.
- **Scenario:** the main process reads `latest` and the slot head, then stalls (GIL, page fault, a long GUI frame:
  the very stalls P2 exists for). The worker publishes two more frames and starts the third into the slot being
  read: `begin` goes odd, payload bytes change; the reader resumes, copies a mix of old and new bytes, reads `end`
  (still the old even value) and accepts. The decoded frame is garbage: `frame_codec.decode` raises
  `FrameCodecError` at best (the owner drops the frame), or decodes a plausible wrong frame (a tuple length or float
  from the wrong frame) that is drawn. With 600 KiB Extruded Bubble payloads the payload copy itself is long enough
  for the window to be real. `test_a_torn_slot_is_never_accepted` tears only `sequence_end`, which this reader does
  detect.
- **Fix:** reader: load `sequence_end` first, then head + payload, then `sequence_begin`; accept iff
  `end == begin == latest` and even. Or writer: invalidate `sequence_end` (set odd) *before* writing the payload, so
  either word read after the payload reveals the write. Fix the docstring's guidance for the P3 C reader the same way
  (acquire-load `sequence_end`, copy, then `sequence_begin`). Add the interleaving to the torn test (tear `begin`
  odd + payload only, leave `end` whole) and the free-running stress of C1 with a payload whose bytes encode the
  sequence so any mixed copy is detected.

## High

### H1. P2a's main-process cost is not shown to be lower than the tick it removes; for four modes it is higher

- **Claim:** design doc, Measured: "the main process pays at most about .4 ms and one slot copy per presented frame,
  against the whole tick it stops running".
- **Evidence:** that figure is the frame *decode* only. With live inputs as engine snapshots the main process also
  steps the engine and runs `EngineSnapshotSource.capture` (21 `deepcopy`'d getters, scheduler drain, onsets,
  spectrum: .20-.25 ms p50), pickles the snapshot (.06-.09 ms; `multiprocessing.Queue` pickles in the parent's
  feeder thread, under the parent's GIL), handles the response, decodes the frame (.08-.54 ms) and copies the slot.
  That is .45-.9 ms of main-process Python per tick before transport, against in-process ticks of .33-.45 ms for
  Spectrum, Oscilloscope, Sphere and Extruded Spectrum (table above). Only Bubble, Spline Curve, Waveform Ribbon,
  Extruded Bubble (1.8-2.1 ms) and Neon Lake (.7 ms) can net a gain, and the gain is the tick minus ~.5 ms, not the
  tick. The acknowledged request -> response path adds 1.3-2 ms of wall latency per tick (round trip 1.66 ms for a
  .34 ms Spectrum tick; 4.0 ms for Extruded Bubble).
- **Scenario:** work order 5 wires production, gate 3 then shows no GIL gain (or a loss) for the cheap modes and a
  modest one for the expensive ones, after the lifecycle work has been paid for. P2b ("audio out", taken only if
  P2a's measurement says so) would delete the whole snapshot layer (`engine_snapshot.py`, the scheduler tap, the
  demands back-edge, the declared-demand agreement) because the worker would own the engine; building P2a's
  production wiring first risks shipping machinery P2b removes.
- **Fix:** measure before wiring: a per-mode gate-3-style measurement of main-process GIL time per tick, in-process
  tick vs. snapshot path (capture + pickle + decode, without the acknowledgement), on the recordings, and write the
  numbers into the design doc. Decide P2a-vs-P2b-first on them. If P2a stands, the snapshot's cost must be bounded
  per tick: capture only what the active mode reads (the read audit is per mode already), and never through an
  acknowledged queue.

### H2. The snapshot transport is a FIFO queue, which the design itself forbids for per-frame data

- **Claim:** design doc, Control: the pipe "carries only edges, never per-frame data"; the bridge rule "never a
  queue, never catch-up replay"; work order 5: "latest-wins snapshots without acknowledgements".
- **Evidence:** `VIS_INPUT {"snapshot": ...}` per tick through `ProcessSupervisor`'s `multiprocessing.Queue(64)`
  (`core/process/supervisor.py:233`, `REQUEST_QUEUE_SIZE = 64`). No latest-wins transport for snapshots exists; the
  plan names the property but not a mechanism, and a queue cannot provide it.
- **Scenario:** the worker falls behind for 200 ms (a page fault, antivirus, the cheap-mode overhead of H1). Without
  acknowledgements the main process keeps putting snapshots: the worker then ticks 20-30 stale snapshots in a burst
  (catch-up replay, frames a presentation never shows, the mailbox counts them as superseded), or the queue fills at
  64 and `put` blocks the main process's capture thread. Neither is the newest-state semantics every other handoff
  in this chain has (R-171 `TripleBuffer`, the mailbox, the ABI).
- **Fix:** a second seqlock mapping, main -> worker, one slot family for snapshots (the same `packet_abi` writer /
  reader with the roles swapped) and a wake byte to the worker; the worker ticks the newest snapshot once per wake.
  The control queue then really carries only edges. Specify this in the design before work order 5.

### H3. The identity gates run against a synchronous replay engine, a steady-state clip, and a tick whose
### failure paths are disabled; a captured-getter miss is already present and silent

- **Claims:** design doc, work order 4, "the snapshot path ticks frames identical to the in-process tick on
  production DSP for all nine modes"; Risks, "a missed one shows up as an identity failure, not silently";
  `engine_snapshot.py:142-143`, "a read no snapshot carries fails loudly".
- **Evidence:**
  1. The reference in `tests/test_visualizer_engine_snapshot.py::_reference` is `EngineSession(inputs="lanes")`,
     i.e. `ProductionLaneEngine` (`feature_replay.py:444-510`): DSP runs synchronously inside
     `accept_feature_frame`, the analysis spectrum is force-published every frame
     (`self._pre_agc_analysis_spectrum_requested = True`, `:488-489`), onsets are renumbered. The live
     `_SpotifyBeatEngine` with `SpotifyVisualizerAudioWorker` (compute pool, asynchronous commits, request-driven
     spectrum, capture-thread waveform history) is never the reference. Everything that differs between the snapshot
     path and in-process only differs under asynchrony (the spectrum back-edge H4, the scheduler tap M1, deepcopy of
     buffers the compute pool replaces) and so cannot fail these gates.
  2. No gate input contains a paused frame: shipped clip 182/182 `playing=True`; all 19 recordings, first 20 s:
     34,559 frames, 0 paused. The paused/idle paths (`_update_idle_waveform`, `_prime_idle_bars`,
     `_mark_idle_waveform_generation`), pause -> resume (ramp restart, `_capture_keepalive_deadline`, the
     `stale_source` classification) and the idle self-animating reveal are never ticked through the snapshot.
  3. `configure_offline_controller` sets `_waiting_for_fresh_engine_frame = False` and `_mode_transition_ready =
     True` (`feature_replay.py:440-442`), so the warm re-entry fence and mode transitions never run in any gate or
     in `engine_read_audit.py`. The fence reads `engine.get_authoritative_frame_commit_seq()`
     (`tick_pipeline.py:94-96`, `:1036-1041`). That getter is **not** in `CAPTURED_GETTERS`
     (`engine_snapshot.py:29-36`); on the worker `SnapshotBeatEngine.__getattr__` raises `RuntimeError`, and both
     call sites are inside `try: ... except Exception:` which set `_waiting_for_fresh_engine_frame = False` /
     `current_epoch = -1`. The fence disarms silently: on a warm recreation/resume the retained pre-re-entry frame is
     admitted, the "flash of seconds-old audio energy" the fence exists to stop. `tick_pipeline.py` has 22
     `except Exception` blocks; several wrap engine reads, so "fails loudly" does not hold for the tick as written.
  4. Both sides of every gate run under `deterministic_clock()` with the same pinned value per tick and the same
     `random.seed(1729)`, so a tick that reads the clock or RNG mid-step is proven equal to itself, not to the live
     in-process tick (where `authored_now()` advances during the tick and `random` is unseeded).
- **Scenario:** the operator pauses Spotify, the screensaver re-enters, resumes: the Visualizer flashes stale bars
  (fence disabled) and the paused idle waveform/bars differ or stall, none of which any gate can see.
- **Fix:** (a) add `get_authoritative_frame_commit_seq` to `CAPTURED_GETTERS` and make the read audit static too
  (grep every `engine.<get_|is_|peek_>` in the tick-side modules against the captured set: a test); (b) a gate clip
  with pause/resume (synthesise `playing=False` spans into a recording's head, as the recorder would), a warm
  re-entry (arm the fence, as the owner does on resume) and an in-session mode switch; (c) a gate whose reference is
  the live `_SpotifyBeatEngine` fed PCM through the real audio worker path (offline, no device: push blocks into the
  capture callback) so asynchronous commits are in play; (d) decide, per `except Exception` around an engine read in
  the tick, whether a `SnapshotBeatEngine` `RuntimeError` may be swallowed (it should propagate: re-raise it there).

### H4. The spectrum demand back-edge is one tick late and racy against the compute commit; make it a mode rule

- **Claim:** design doc, work order 4, "the one write that depends on the tick ... returns as `EngineDemands` for the
  main process to apply before its next step"; Latency risk, "at most one tick of extra control latency".
- **Evidence:** live, the tick's `get_pre_agc_analysis_spectrum()` sets the request bit at tick T
  (`beat_engine.py:1494`); the compute lane's next commit publishes (`:1094-1106`); tick T+1 reads it. With the
  worker: capture T peeks (`:1497`), the worker ticks, the demand travels back in the response, the main process
  applies `request_pre_agc_analysis_spectrum()` (`:1502`) before step T+1. Any commit that lands between
  `engine.tick()` at T and the demand's arrival sees the bit clear and publishes nothing, so capture T+1 carries the
  spectrum from T-1. The reference engine in the gates force-publishes every frame regardless of the bit
  (`feature_replay.py:488-489`), so the gate measures nothing about this edge; `test_the_ticks_spectrum_request_
  reaches_the_main_engine` checks plumbing on a fake. With H2's latest-wins transport (no response) the edge is later
  still.
- **Scenario:** Sphere's spectrum lags one commit on a random subset of ticks: a jittered, slightly delayed response
  that no digest comparison on the replay engine can reveal.
- **Fix:** the spectrum is read every tick by the modes that read it at all: declare the demand from the mode rule on
  the main side before stepping (exactly as `consumes_waveform_samples` is handled, `engine_snapshot.py:72, 114-115`)
  and delete `EngineDemands`, `take_demands`, `apply_demands` and the `demands` response field. One fewer tick ->
  engine write, no back-edge at all.

### H5. The payload is not C-readable and the ABI header fields P3 would read are never populated

- **Claim:** design doc title section, "P2 fixes the packet ABI P3 builds on"; codecs "fixed-width fields, then
  float32/u8 blocks at 16-byte alignment"; "P3's native core reads the same bytes without Python".
- **Evidence:** `frame_codec.py` is one recursive tagged tree keyed by Python class (`_TYPES`, `:28-39`) with field
  order from `dataclasses.fields()` (`:59`), `FrozenFields` entry lists, mapping proxies and dtype strings; float
  tuples are float64. A C reader would have to mirror every dataclass's field order and every nested type and would
  break on any field addition. `PacketMailbox.publish` (`:95-99`) writes `flags=0`, no `source_timestamp`,
  `payload_schema = CODEC_SCHEMA` (one number for all modes, not "per mode, versioned"); the mapping header's
  `runtime_generation / engine_generation / activation_id / mode_code` are whatever the reader passed at creation
  (`0` in every test and in `PacketMailbox(role="reader")`'s defaults) and never updated on `VIS_CONFIGURE`. The
  identity P2 actually uses travels inside the payload tuple `(generation, activation, produced, state)`.
- **Scenario:** P3 starts from the doc, finds no fixed layouts and a header that says generation 0 / mode 0, and
  either re-derives per-mode C layouts (a new ABI version, a second codec) or parses the Python tree in C.
- **Fix:** say in the design what is true: the tagged codec is P2's Python-to-Python transport; P3 gets per-mode
  fixed layouts under new `payload_schema` values with the header identity written by the writer on configure. Or
  build the fixed layouts now for the P3-first mode (Spectrum) so the claim is tested. Either way, populate the
  header identity and flags from the publication (cheap) so a C reader can at least validate what it is looking at.

### H6. The worker runs with `time.time`, `time.monotonic` and `random` monkeypatched for the session's whole life

- **Claim:** `engine_worker.py:54-56`, "the session's authored clock follows its inputs' own timestamps".
- **Evidence:** `EngineSession.__init__` enters `feature_replay.deterministic_clock()` (`feature_replay.py:385-402`),
  the *replay harness* context: it replaces `time.time` and `time.monotonic` module-wide with the frozen cell and
  seeds `random` globally, for as long as the session exists (production: always). `BaseWorker.run`
  (`core/process/workers/base.py:207-222, 237, 249`) measures `processing_time_ms` and heartbeat `uptime_s` with
  `time.time()`; `logging.LogRecord` timestamps use `time.time()`; `multiprocessing` internals and any library the
  mode runtimes import read `time.monotonic()`.
- **Scenario:** worker log lines carry perf-counter-domain timestamps (1970 dates), `processing_time_ms` is 0 and
  uptime negative in every heartbeat; a future library call that waits on `time.monotonic()` spins or never times
  out. Nothing pins the production tick to not reading `time.*`: if a mode runtime does, the pin hides a real
  live-vs-worker difference (the gates share the pin on both sides, H3.4).
- **Fix:** the worker pins only the authored clock (`core.authored_clock.pinned_authored_clock`) to the input's
  timestamp and leaves `time.*` and `random` alone; `deterministic_clock` stays a test/replay tool. Run the identity
  gates with that: if they still pass, the tick reads no wall clock (good, prove it with a `time.*` spy in
  `engine_read_audit`); if not, the failing read is a hidden clock dependency to move into the frame input.

## Medium

### M1. The scheduler tap can miss feeds, and the worker's scheduler starts empty

- **Evidence:** `EngineSnapshotSource._tap_scheduler` (`engine_snapshot.py:77-99`) replaces `feed`/`reset` on the
  *instance* returned by `get_event_scheduler()` and is called only at `capture`. The audio worker replaces the whole
  transient bus (and so the scheduler) on `set_raw_musical_signals` (`audio_worker.py:471`) and on its reset path
  (`:584`); `engine.tick()` schedules compute asynchronously, so the compute lane can feed the *new* scheduler
  before the next capture installs the tap on it: those feeds are not forwarded (the appended `_RESET` then wipes
  the worker's copy, but the missed events never arrive). At session start the live scheduler's ring and
  `_last_accepted_ts` are not carried (`initial` snapshot has `scheduler_ops=()`), so the worker's debounce starts
  from zero while the main's does not. The tap is also a monkeypatch of a live object from outside its owner (one
  owner per state). The synchronous reference engine (H3.1) never replaces its bus mid-clip.
- **Fix:** an engine-owned hook (the bus is constructed by the audio worker: give `TransientBus`/`_SpotifyBeatEngine`
  an optional feed observer set once, inherited by every replacement bus) and carry the scheduler's state in the
  initial snapshot (ring entries + per-type last accepted timestamps), or accept a documented warm-up divergence.

### M2. A tick exception leaves the session alive and ticking on half-updated state

- **Evidence:** `engine_worker.py:157-158` catches every exception, replies `success=False` and keeps `_session`;
  the next `VIS_INPUT` ticks the same controller. The declared-demand check raises mid-tick by design
  (`engine_snapshot.py:171-174`), so this path is reachable.
- **Fix:** fail closed: close the session on any tick exception, reply with the error and a `session_closed` marker;
  the owner treats it like a worker crash (bridge admission closed, fade, reconfigure once).

### M3. `produced_ts` and the scheduler's `now` change meaning in the worker

- **Evidence:** `PacketMailbox.publish` stamps `produced = authored_now()` (`:93`), which in the worker is the frozen
  snapshot timestamp (= capture time on the main side), not the time the frame was produced as in process
  (`logical_runtime.py:216`). `TransientEventScheduler.consume_next/peek_latest` use `authored_now()` for
  `max_age_s` (`transient_bus.py:658, 685`): evaluated at capture time in the worker, at consume time in process.
- **Scenario:** gate 3's "frame age before/after" compares two definitions; an event at the age boundary is
  consumed in one path and expired in the other.
- **Fix:** define frame age from the capture timestamp on both paths before gate 3 (and record it in the design); keep
  the worker's authored clock at the snapshot time (it is the right choice) but say so.

### M4. The gate report on disk does not match the claim made from it

- **Evidence:** `.artifacts/evidence/architecture/native_core_p2/20261108_worker_gate/report.json` has
  `"mismatches": 11`, 160 identical pairs and 11 Waveform Ribbon rows with `error: "ValueError: PCM reanalysis
  requires native capture history on every frame"`; the script as run exited 1. The `skipped` branch was added in
  commit `edc23420`, after the run; the report was not regenerated. The design doc states "all 160 replayable pairs
  identical" and "Waveform Ribbon is skipped", which is the current script's behaviour, not the stored evidence.
- **Fix:** re-run the gate with the current script (or annotate the report). The design doc now carries a note.

### M5. Work order 5 omits mechanisms the production owner needs

The design names the properties; the worker has three messages (`VIS_CONFIGURE` rebuilds everything, `VIS_INPUT`,
`VIS_STOP`). Missing from the plan, each with a concrete consequence if wired as is:

- **In-place mode switch.** "A mode switch is a control message inside the same worker" has no message; a
  `VIS_CONFIGURE` builds a new `EngineSession` (new controller, new tick state), so the mode-transition machinery
  (`_mode_transition_pending`, teardown/reveal edges, the deadline) that lives in the tick state is thrown away
  mid-fade. Needs a `set_mode` control applied to the existing controller at a tick boundary.
- **Settings live edits.** `config_applier.apply_logical_vis_mode_kwargs` mutates the tick state in place today;
  the worker has no message for a resolved-settings delta. A rebuild per slider step resets the mode visibly.
- **Playing state, framed view inputs, park.** Listed in the design's control section, absent from the worker.
  Parking is simple only because the worker has no cadence: the main process's capture thread is the cadence,
  which the design does not say (it says the worker owns the logical runtime).
- **Wake pipe hygiene.** The owner must close its copy of the wake sender after `VIS_CONFIGURE` (the worker test
  does) or the listener never sees EOF when the worker dies; the design's crash path relies on the supervisor's
  heartbeat (2x interval) to notice and should say what the Visualizer shows meanwhile (the last frame; "fade,
  never vanish" needs the owner to start the fade on heartbeat loss, not on the restart).
- **Label namespace persistence.** "Never repeated across sessions or restarted workers" needs a counter owned by
  the main process across the app's life (and `EngineSession` writing `extruded_bubble_drift_log._REVISIONS` is a
  module global mutated from outside its owner; in-process gates with namespace 0 reset the host process's counter).
- **Memory.** 64 MiB idle / 129 MiB Extruded Bubble, not "tens of MB"; the dormancy receipt must include the worker.
- **Frozen spawn.** `visualizer_worker_main` must be reachable from the frozen entry as the image worker is; listed
  as an operator check only.
- **Presentation-config reads.** The tick still reads presentation state (Spectrum decoration fades/colours,
  Oscilloscope/Bubble spec parameters), so the worker loads QtGui; the design says move them "before production
  wiring" and the plan lists it under 5 - keep it before, since settings deltas (above) must target the logical
  side only.

## Low

- **L1. Edge-kind mask buckets collide.** `protected_edge_mask` (`packet_mailbox.py:40-45`) maps kinds to
  `crc32 % 32`; two kinds can share a bit. P2 never reads the mask (the payload carries the edges); P3 would. Use a
  stable enum table.
- **L2. Design-doc header table was out of date.** `u8 mode_code pad` vs. the implemented `u32 mode_code`, and the
  reader-owned `u64 consumed_sequence` at offset 40 was missing. Corrected in the design doc (see edits).
- **L3. Double delivery of a protected edge across processes** when the writer coalesces the previous state's edges
  because the reader accepted but had not yet acknowledged. Harmless: `render_bridge._merge_protected_edges` keeps
  one edge per kind by token (`render_bridge.py:134-147`). Note it in the mailbox docstring.
- **L4. `_edges` grows while unacknowledged** (`packet_abi.py:124, 148-149`); bounded by the rarity of edges, but a
  reader that never acknowledges (a stalled owner) grows it one entry per edge frame. Cap it by kind.
- **L5. Diagnostics read a private attribute with a default** (`tick_pipeline.py:1255`
  `getattr(engine, "_last_playback_state_ts", 0.0)`): always 0 on the worker, so the latency log's `stale_source`
  classification is off there. Diagnostics only.
- **L6. In-process loopback encodes under the mailbox lock** (`packet_mailbox.py:86-99`, .1-.5 ms) where
  `LatestStateMailbox` holds it for nanoseconds; loopback is not the production path, so only a note.
- **L7. The worker test allows QtGui** (`test_the_worker_loads_no_gui_stack_in_a_production_spawn`) while the
  import-weight test pins QtCore only; the two pins disagree until the presentation-config reads move (M5).

## Verified sound

- Codec: exact `repr` round trip and identical re-encoding on every production frame of all nine modes; `-0.0`,
  full float64 precision, read-only `ndarray`, mapping proxies, trailing-byte and schema refusal; `__post_init__`
  on the frame dataclasses only normalises fields (no derived attributes lost by `object.__new__`).
- ABI: version/magic/shape refusal, oversized payload refusal, writer never overwrites the newest slot, re-attached
  writer continues the sequence, named mapping across processes, unlink idempotent and effective.
- Mailbox: latest-wins and superseded counts, retired-generation drop, one wake per edge *in process*; the wake
  listener thread ends on `close()` while blocked in `recv_bytes` (probe: ended in 0.00 s).
- Worker: label namespaces disjoint per session; the fresh-spawn probe loads QtCore + QtGui only; the supervisor
  plumbing (configure/input/stop, shutdown) works; identity holds for all nine modes on the operator's recordings
  *for the steady-state, playing, replay-engine case* (160 pairs, 291,024 frames).
- Beat engine: `is_reactivity_play_ramping` as a pure clock read is unchanged in process (its one reader runs a
  ramped getter first); `peek_`/`request_` split the read from the demand correctly.

## Proposed plan changes (for `Current_Plan.md` 8b, P2)

1. Before work order 5: fix C1 and C2 with the free-running stress test; re-run the recordings gate (M4).
2. Insert "4b. Live-engine and off-steady-state gates" before 5: a gate against the live `_SpotifyBeatEngine` fed
   PCM through the real worker path; clips with pause/resume, warm re-entry (fence armed) and in-session mode
   switch; `get_authoritative_frame_commit_seq` captured; the read audit made static and per path (H3).
3. Insert "4c. Main-process cost measurement" before 5: per-mode main-process GIL time per tick, in-process tick vs
   capture + pickle + decode without acknowledgement (H1). Decide on those numbers whether P2a's production wiring
   proceeds or P2b (the worker owns capture + DSP; the snapshot layer is deleted) goes first.
4. Work order 5 must specify: the main -> worker latest-wins snapshot mapping (H2); `set_mode` and settings-delta
   controls applied to the existing session; playing/framed-view/park controls; fail-closed session close on a tick
   exception (M2); wake-sender close and the heartbeat-loss fade (M5); the namespace counter's owner; the
   presentation-config move so the worker is QtCore-only; the worker's RSS in the dormancy receipt.
5. Replace the spectrum back-edge with a mode-rule declaration (H4) and the `deterministic_clock` pin with an
   authored-clock-only pin (H6) before any production wiring; both simplify work order 5.
6. Mark the Risks entries "The GUI wake" as open (done in the design doc) and add "payload is Python-only; P3 layouts
   are a separate work order" (H5) or build Spectrum's fixed layout as part of P3's first port.

## Checkpoint audit 2 (8 Nov): fixes and 4c

Scope: 051b8f9e (C1, C2), a478552e (H3a, H4, H6, M2), 4a8b4199 (4c tool, report, "P2b first"), read against the P2b
work order that landed after it (750297bc). Ran: `test_visualizer_engine_packet_abi.py` +
`test_visualizer_engine_worker.py` (25 passed), `test_visualizer_engine_snapshot.py -k "not worker_process"` (15
passed), `engine_main_cost.py --seconds 5 --modes spectrum bubble`, and three throwaway probes (a mutation of the C2
reader, a torn-read counter on the free-running test, an analysis-pass counter on `ProductionLaneEngine`). None of the
P2a code is wired into production (only tests/tools import `EngineSnapshotSource`/`VisualizerEngineWorker`), so no
finding below is a shipped behaviour change.

### High

**A2-H1. The C2 test does not pin the C2 fix: a reader without the final `sequence_begin` re-read passes it and
accepts a torn payload.**
- Evidence: `tests/test_visualizer_engine_packet_abi.py:88-96` fires its overwrite on the reader's *second* read of
  the slot. On the old reader that second read was the slot head (so the tear landed during the payload copy and the
  test failed, correctly); on the new reader (`packet_abi.py:191`) it is the `sequence_end` load, so the overwrite
  happens *before* the head read and the reader rejects it through `head != latest` (`:197`), the same check the old
  code had. Mutation probe: replace `begin = _U64.unpack_from(view, base)` (`:196`) with `begin = head` -> the test
  still PASSes; the same mutant with the overwrite injected right after the head read returns
  `FramePacket(payload=b'DDDDDDDD')` (torn, accepted).
- The free-running stress test cannot cover it either: two runs, 330 frames each, `torn_reads == 0` both times (the
  writer would have to publish twice during one copy; at 165 Hz it never does), so its "never tears" half is vacuous.
- Failure scenario: a later refactor of `read_latest` (or the P3 C reader written from this test as its spec) drops or
  reorders the trailing load; every test stays green and torn frames reach the renderer under load.
- Fix: inject the overwrite between the head/payload read and the final begin load (e.g. hook the payload slice, or
  fire on the `_SLOT_HEAD` read specifically), assert `None`, and keep the "drop the re-read" mutant as a negative
  control. Reword "never tears" in the stress test, or make it actually lap (a writer publishing in a tight loop while
  the reader copies a large payload, asserting `torn_reads > 0` so it cannot pass vacuously).

**A2-H2. 4c's DSP column double-counts analysis for the Spectrum family, so "P2b saves" is overstated there and
"P2b's gain is a floor" is unsupported.**
- Evidence: `ProductionLaneEngine.accept_feature_frame` runs `compute_bars_from_samples` twice per new audio block for
  modes with Spectrum shaping (`feature_replay.py:255` via `_replay_shaped_bars`, then `PcmReanalysis.accept`,
  `feature_replay.py:376`). Probe (3 s clip): Spectrum / Extruded Spectrum / Neon Lake 1.54 analysis passes per
  frame, Bubble / Oscilloscope 0.77; analysis .85-1.08 ms vs .40-.48 ms per frame - exactly the 1.08-1.14 vs .46-.60
  split in the report's DSP column (`main_cost.json`). Plus ~.17-.24 ms/frame of replay-only bookkeeping (recorded
  lanes, scheduler ring copy, onset renumbering, the spectrum tuple published every frame, `feature_replay.py:483-499`)
  that the live engine does not do; and only ~77% of ticks carry new audio while the live worker analyses every
  ~10 ms capture callback. The proxy is off in both directions, so it is not a floor.
- The design doc's table ("Measured and decided") states ~1.29-1.34 ms P2b savings for those three modes; with one
  analysis pass it is nearer ~.8 ms.
- The decision survives (P2a is break-even for five modes; even halved, DSP >= ~.4 ms makes P2b the larger saving for
  every mode), but these numbers must not be quoted as the expected gain or used as gate 3's baseline.
- Fix: measure DSP with one pass (time `PcmReanalysis` alone), or better the live `SpotifyVisualizerAudioWorker`
  compute path fed PCM blocks at the capture cadence (4b's harness); restate the table and drop "a floor".

**A2-H3. P2b moves the frame decode onto the render thread's sync, which 4c counts only as ordinary main-process
time.**
- Evidence: steady-state admission takes from the logical mailbox on the render thread at Quick synchronization
  (`quick_presentation_sync.py:308-311`, wired at `quick_display_visualizer_owner.py:524`), with the GUI thread
  blocked. In process that take is a reference hand-off; with `PacketMailbox` it is `read_latest` + `frame_codec.decode`
  under the mailbox lock: .07-.37 ms p50 in the report (Extruded Bubble .37/.43 p90; .18-.29 in my loaded rerun), and
  1.5 ms p50 for a 4096-element state in the stress probe.
- Failure scenario: P2b lowers total main-process GIL time but lengthens every sync for the heavy-frame modes, the
  stall budget the frame-pacing work protects.
- Fix: P2b's work order says where the decode runs (render thread at sync vs. GUI wake vs. decode-ahead on the wake
  listener thread into a decoded latest slot), and gate 3 measures sync duration per mode, not only GIL totals.

### Medium

**A2-M1. `SnapshotContractError` (a `BaseException`) kills the worker process outside VIS_INPUT, and a failed session
constructor leaks its pins.**
- Evidence: only the VIS_INPUT branch catches it (`engine_worker.py:171`). VIS_CONFIGURE builds `EngineSession` (which
  runs `configure_offline_controller` against `SnapshotBeatEngine`, `engine_worker.py:94`) under `except Exception`
  (`:180`), and `BaseWorker.run` catches only `Exception` (`core/process/workers/base.py:214, 225`) and
  `KeyboardInterrupt`: the worker loop exits with no reply and the owner sees a request timeout, not an error. A
  constructor that raises after `pinned_authored_clock` is entered (`engine_worker.py:64`) never closes its ExitStack:
  the authored clock stays pinned to the dead session's cell and the attached mapping stays open (pre-existing for
  `Exception` too).
- Fix: catch `(Exception, SnapshotContractError)` around VIS_CONFIGURE/VIS_STOP as well, and close `self._stack` on a
  constructor failure. Moot for the error type once P2b deletes the snapshot engine; the ExitStack leak applies to
  every session input.

**A2-M2. H6: the gates' `seed` re-masks what H6 asked to surface, and the per-mode gate still pins `time.*`.**
- Evidence: `_split_in_process` runs the snapshot session inside `deterministic_clock()`
  (`tests/test_visualizer_engine_snapshot.py:73`), which monkeypatches `time.time`/`time.monotonic` process-wide, so
  only the single worker-process test (1.0 s clip) ticks with real wall clocks. Both gates pass `seed=REPLAY_SEED` and
  the reference seeds the same value, so *any* new process-RNG consumer in the tick (not just Bubble's spawn,
  `bubble_simulation.py:164-259, 1497-1546`) draws identically and passes. The comment "a tick that read a wall clock
  or the RNG would fail the identity gates" (`engine_worker.py:57-59`) is false for the RNG and true for wall clocks in
  one test only.
- The `seed` input itself is honest (production passes none), but it reseeds the process-global `random`.
- Fix: give Bubble's simulation its own `random.Random` (as `bubble_ambient.py:62-63` already does) seeded from the
  control input, and stop seeding the global RNG in the gates so a stray global draw diverges; run the worker half of
  `_split_in_process` with only the authored clock pinned.

**A2-M3. The H3a static scan has blind spots that still fail silently.**
- Evidence: the scan (`tests/test_visualizer_engine_snapshot.py:233-250`) only matches `get_`/`is_`/`peek_` names of
  `_SpotifyBeatEngine`, only under `widgets/spotify_visualizer`, excluding `feature_replay.py`. Private-attribute reads
  fall through `SnapshotBeatEngine.__getattr__` as `AttributeError`, which `getattr(..., default)` swallows:
  `tick_pipeline.py:1255` reads `engine._last_playback_state_ts` with default 0.0, so on the worker the latency
  logger's pause/resume `stale_source` classification is silently off (diagnostic only; `tick_pipeline.py:1217`
  `_last_smooth_ts` is the same pattern in a fallback). `set_*`/`reconfigure_*`/`wake` are silently accepted.
  Today no engine getter is read outside the package (grep of `core/`, `rendering/`) and no read builds a getter name
  dynamically, so the scan is currently complete for public getters.
- Fix: raise `SnapshotContractError` for `_`-prefixed names in `__getattr__`, extend the scan to `core/` and
  `rendering/` - or, under P2b, drop the question with the snapshot engine.

**A2-M4. 4c methodology confounds and record mismatches.**
- The worker's tick runs in the same process between the timed pickle and take (`engine_main_cost.py:109`); its
  allocations can trigger GC inside the timed `take` and it churns caches, biasing P2a's main side up; the per-getter
  re-capture loop (`:113-116`) does the same after `take`. p50s absorb most of it, p90s do not.
- The read set behind `gain_p50_read_only_capture` is what the tick read on two default-config clips;
  settings-dependent reads (Neon Lake's reaction, `logical_frame_capture.py:359-362`; Sphere's `source_is_current`;
  paused paths) are missing, so a capture set built from it would be unsafe. Moot under P2b.
- The doc says "20 s of both shipped clips ... ~3,600 ticks per mode"; the report has 2,312 frames per mode (the clips
  are shorter than 20 s).
- Concurrency: my rerun on a busier system read +40-50% absolute (Spectrum tick .46 vs .31, Bubble 2.61 vs 1.78, DSP
  1.50 vs 1.14) with the same per-mode ordering, so the three concurrent agents did not confound the *direction*;
  absolute numbers from either run are not baselines.
- Wall time stands in for GIL time (`engine_main_cost.py:12`); NumPy FFT/ufunc work may release the GIL, so the DSP
  share of GIL time is at most the wall figure. Unverified either way.

**A2-M5. What P2b's gain omits and what the P2b work order still does not say.**
- Uncounted main-side costs: one wake byte per publish means the main process's listener thread wakes, takes the GIL
  and the mailbox lock and calls `QuickVisualizerPublicationWake.request` on every worker frame
  (`packet_mailbox.py:104-105, 176-185`; 330 wakes for 330 frames in the probe) at the worker's own cadence; control
  edges through the supervisor queue; reading back what frames must now carry (`_play_ramp_start_ts`, identities).
  Small, but gate 3 must include them.
- The work order (design doc 4P) covers capture-device ownership, Studios/replays unaffected, the control-edge
  inventory and fail-closed capture. Not yet said: (1) the cadence owner - steps 5 and 6 still say "the main
  process's capture is the cadence", "a main -> worker latest-wins snapshot mapping" and "Measurement (gate 3), then
  decide P2b", and the Staged list (~line 38) still says P2b is "taken only if P2a's measurement shows...", all stale
  against 4P; (2) Media playback truth - the main process's media state vs. the worker engine's own silence/play-ramp
  detection: which wins, and how a pause reaches the worker before the ramp misreads silence; (3) default-endpoint /
  device change and COM init on the worker's capture thread, and a capture restart without a session rebuild; (4) the
  usage sampler and dormancy receipt counting a long-lived child (the sampler's `children()` is a known GIL-held
  hitch); (5) the worker's logging/telemetry routing; (6) where the frame decode runs (A2-H3); (7) wake-pipe
  backpressure: `send_bytes` blocks the worker's tick when the pipe fills (a main process whose listener cannot get
  the GIL), so the writer should skip a wake while one is still unread rather than block.

### Low

- **A2-L1. Stale "edge only" comments after C1:** `packet_mailbox.py:61-62`, `engine_worker.py:78` and
  `QuickVisualizerPublicationWake`'s docstring (`quick_presentation_sync.py:57-64`, "Mailbox coalescing guarantees at
  most one queued wake"). The coalescing that makes per-publish wakes harmless is real (`quick_presentation_sync.py:78-
  86`: one pending queued event, cleared before delivery); the comments describe the old contract.
- **A2-L2. The P3 C-reader guidance assumes atomic 8-byte stores the Python writer does not make.** `struct` packs
  `'<Q'` through `_PyLong_AsByteArray`, which writes the target byte by byte, so a C reader can load a torn sequence
  word. The protocol tolerates it (begin's low byte always changes first because parity flips; `end`/`latest` are
  stored after begin settles), but `packet_abi.py:31-33` should say so, or the writer should store sequence words
  through an aligned `memoryview.cast("Q")` element. (From CPython source, not measured.)
- **A2-L3. H4 cost shape:** the mode rule requests the spectrum every tick for Neon Lake even with its reaction off
  (`mode_capabilities.py:59`), where in process the read, request and tuple copy happen only while enabled
  (`logical_frame_capture.py:359-362`): a small dormancy regression on the P2a path, invisible to the gates because
  `ProductionLaneEngine` publishes the spectrum every frame regardless (`feature_replay.py:489`). Moot under P2b.
- **A2-L4. Stress-test hygiene:** the first `woke.wait(5.0)` includes spawn + import (1.2 s quiet), and a failed
  assertion leaves the child to `join(30)` then unlinks its mapping without terminating it
  (`tests/test_visualizer_engine_worker.py:222, 232`).

### Verified sound

- C2 code: the reader's order (begin scan, `sequence_end`, head + payload, `sequence_begin` again;
  `packet_abi.py:185-200`) is a correct seqlock against the writer's (`:146-151`), including a writer that laps the
  slot and byte-wise torn words. C1 code: one byte per publish across processes (`packet_mailbox.py:104-105`) removes
  the acknowledgement race; the C1 unit test fails on the old rule (2 wakes vs 4), and the free-running test does
  detect stranding.
- H3a: `get_authoritative_frame_commit_seq` is captured; `SnapshotContractError` passes through the tick's
  `except Exception` blocks; no `except BaseException`/bare `except` in the tick path swallows it (`render_state.py:241`
  re-raises).
- H4: `reads_analysis_spectrum` names every current reader (`logical_frame_capture.py:362, 620`,
  `sphere_capture.py:103`); the check is one-directional (a read without the rule raises), so Neon Lake's
  settings-dependent read cannot trip it.
- M2: a raising tick closes the session and replies `session_closed`; the next input is refused.
- 4c's decision direction: P2a is break-even or worse for five modes on both runs; P2b removes more main-process work
  for every mode even after A2-H2's correction.

### Not verified

- Live DSP cost per capture callback on the real compute pool (needs 4b's harness), and its true GIL share.
- Whether NumPy's FFT path releases the GIL in this build.
- The worker-process snapshot gate (`test_the_worker_process_ticks_identical_frames_from_snapshots`) was not run.

## Checkpoint audit 3 (8 Nov): P2b slice 1 and the Vulkan section

Scope: 33d76196, 4e9fb516, bc215476, 24282839 (merged at 67ff1f42) and 3698eb67 (4V). Ran:
`test_visualizer_engine_live.py` + `test_visualizer_engine_import_weight.py` (6 passed), and throwaway probes on the
live rig (in process only): a field-by-field diff of live vs `ProductionLaneEngine` frames on whole clips, the same
with the spectrum requested before the first commit, a request/publish trace for Sphere, and the rig replayed in
production read order. The whole-clip gate and the cost tool were not re-run. Nothing in this checkpoint changes
production behaviour (see Verified sound); the findings are about what the rig and the numbers prove.

### High

**A3-H1. The rig's tick reads the commit of its own block; production's tick reads the previous one. "The live
engine is the reference from here on" names a zero-latency ordering production never has.**
- Claim: design doc 4P slice 1, "the tick reads the asynchronous commit of the block it was fed ... the frames are
  deterministic"; "Live engine vs `ProductionLaneEngine`: no lag on any mode"; "The live engine is the reference from
  here on".
- Evidence: `_tick_live` pushes, calls `engine.tick()` (submit), *waits for the settled edge*, then the logical tick
  runs and its own `engine.tick()` is a no-op (`engine_worker.py:167-191`). Production's tick calls `engine.tick()`
  (`tick_pipeline.py:991`), which only submits to the compute lane (`beat_engine.py:1386-1398`), and reads the bars
  immediately after; the lane commits later on its own thread. Probe: the same clip with the rig's read order changed
  to production's (push, logical tick, then wait for that commit before the next input) differs from the rig on
  363/364 Spectrum frames (frame 0: no commit at all, `source_timestamp` None; every later frame reads the previous
  commit).
- What the in-process vs worker gate cannot catch, since both sides run the same rig with the same waits: it proves
  the code is portable (imports, input pickling, no wall-clock reads in the frame path, same RNG draws), not how the
  engine behaves asynchronously. Never exercised: a tick reading before the commit; a source block replaced while an
  analysis is in flight (`_replace_pending_analysis_frame`, `beat_engine.py:804`: the rig never has a pending source);
  a tick reading a commit that is half written (`_commit_analysis_frame`, `:1135-1180`, stores bars, smoothed bars,
  energy and stamps one by one, unlocked against the tick thread); callbacks interleaved with the tick; and the
  latest-wins transport (every input is acknowledged before the next, so no frame is ever superseded or coalesced).
- Failure scenario: the P2b worker free-runs (no settled wait). Any later gate that compares its frames to "the
  reference" sees a one-commit offset on every mode and either fails or gets a tolerance that hides real regressions.
  Statements about lag ("no lag" vs the lanes engine) describe the rig, not the product.
- Fix: say in 4P that the rig is an idealised zero-latency order. Add a production-order rig mode (step, tick, then
  wait for the commit before the next input; still deterministic) and make *that* the P2b reference. Add a
  free-running stress run with invariants instead of digests (commit sequence never goes backwards; bars, energy and
  commit stamp read in one tick come from the same commit) to cover the asynchrony.

### Medium

**A3-M1. The live-vs-lanes differences are isolated: none of them is in the mode state that the doc names, except one
startup effect that production has too.**
- Claim: 4P, "Bubble differs on every frame and Oscilloscope from frame 1 ... Spline Curve, Extruded Bubble and
  Waveform Ribbon match for long stretches (185-882 frames per clip) and then part: in their mode state, not the
  common lanes (cause not isolated)"; "Sphere differs from frame 1 (the live engine publishes the analysis spectrum one
  commit after the tick requests it; the lanes engine every frame, H4)".
- Evidence (field-by-field diff over the whole of growing_pains, 1,148 frames):
  - Spline Curve, Extruded Bubble, Waveform Ribbon: the only field that differs is the frame's `source_timestamp`, on
    266 frames: the ticks with no new capture publication (24% of the recorded ticks repeat a serial). The live engine
    keeps the previous commit's stamp; the lanes engine stamps every frame. They differ from frame 1 on, interleaved;
    `equal_frames` (882/185/406) is a count, not a leading stretch, and the mode state never parts.
  - Bubble: `common.waveform_count` 128 vs 256 on every frame (the live engine pads its 128-sample block and reports
    128, `beat_engine.py:1366-1374`; the lanes engine serves 256 from history), plus the same `source_timestamp`. Its
    mode state is equal.
  - Sphere (tracer, sections, particle cohorts) and Oscilloscope (`tone`): with the pre-AGC spectrum requested before
    the first commit, both become equal to the lanes engine except `source_timestamp`. So their whole divergence is
    the first commit of the activation, which publishes no spectrum because nothing has requested one yet (trace:
    commit 1 `requested=False`; from commit 2 on, each tick reads its own commit's spectrum). Not a steady
    one-commit lag. The stateful integrators carry that one missed frame for the whole clip.
- Failure scenario: none for the P2b gates (both sides run the same engine). In production, every activation of
  Sphere, Oscilloscope and Neon Lake with reaction on starts one commit (about 11 ms) late on the spectrum. Small, but
  real, and the doc's "cause not isolated" invites someone to chase a mode-state bug that is not there.
- Fix: correct the 4P paragraph. Declare the spectrum demand from the mode rule (`reads_analysis_spectrum`) at
  activation, as `_start_live_engine` already does for the waveform demands (`engine_worker.py:156-158`), and in the
  production owner, so the first commit publishes. Decide whether a held tick should carry the previous commit's
  `source_timestamp` (live) or its own (lanes); the live behaviour is the honest one.

**A3-M2. The rig sets the analysis cadence by the recording's publications, not by the device's blocks, so the live
DSP per tick is about 25% low.**
- Claim: 4c "Live engine measured": ".76 per tick on the recorded cadence (~69 analyses per second): ~.4-.6 ms of
  DSP per tick, ~35-55 ms of GIL per second of audio"; "For the other six the live DSP ... matches 4c's one-pass
  column, so their 4c 'P2b saves' stand".
- Evidence: the rig pushes a whole publication's samples in one burst per input (`engine_worker.py:186-187`), so the
  engine gets at most one new block per input. In all three shipped clips 75.6-76.8% of the ticks carry a new serial
  (90.5 Hz ticks). On a device, the blocks in use (128/256/512 samples = 2.7/5.3/10.7 ms) arrive faster than the
  11 ms tick, so nearly every tick finds a new block: about 1.0 analysis per tick, not .76.
- Failure scenario: the DSP column, the GIL per second and gate 3's analysis-latency baseline are about 25% below
  production. P2b's savings are understated (the direction is safe), but the corrected ~.8 ms for Spectrum, Extruded
  Spectrum and Neon Lake and "the other six stand" come from this rig, not from production.
- Fix: in the cost tool, schedule the pushed blocks on the authored clock at `block_size / rate` intervals across
  the tick (cutting each publication's samples as a device would deliver them), or report analyses per second at the
  device cadence next to the recorded one.

**A3-M3. The cost table's "P2b saves" mixes a loaded run with a take measured against an idle writer, and leaves
out what P2b adds.**
- Evidence: the live column comes from a run the doc says read 30-60% high. The take is timed right after the
  worker acknowledges VIS_INPUT (`live_engine_cost.py:166-177`), so the writer is idle: no concurrent publish, no
  seqlock retry, no cache-line contention, all of which a free-running P2b worker brings. "The reader copies a slot
  another process just wrote" is offered as the reason the take is .13-.75 ms against 4c's .07-.37, but the same run
  was under load, so that reason is unproven. "~.8 ms stands" adds this run's DSP and take to 4c's tick: the
  cross-run mixing the paragraph itself warns against. Not subtracted: the main process's wake listener (one pipe read,
  GIL acquisition, mailbox lock and wake request per worker frame, A2-M5), the control edges, and the decode's sync
  latency on the render thread (A2-H3). The load record is two 1-s samples; `system_after` is labelled "sampled for
  1 s before the run" (`live_engine_cost.py:316-317`).
- Failure scenario: the table is quoted as "P2b saves 1.0-3.3 ms per tick" when the defensible claim is a range
  whose top end is inflated and whose cost side is incomplete.
- Fix: time the in-process and worker takes in one run, interleaved; time the take against a free-running worker;
  add the listener thread's per-frame time; fix the label; and have the table say "P2b removes" (the live total) and
  "P2b adds" (take + listener + edges) as separate columns.

**A3-M4. Vulkan: the identity the core would check is mapping-wide and outside the seqlock; P2b's in-place
mode/activation changes need it per slot.**
- Claim: 4V, "the writer filling the header identity (runtime/engine generation, activation, mode code) and flags on
  configure and per publish, so the core can validate a slot without Python".
- Evidence: `runtime_generation`, `engine_generation`, `activation_id` and `mode_code` live in the 64-byte mapping
  header (`packet_abi.py:10-13`), written once by `initialise` (`:88-97`). The seqlock covers slots only
  (`:17-22, 146-151`). The slot head has no activation or mode field (`_SLOT_HEAD "<QIIddII"`, 40 bytes, payload at
  48: 8 bytes spare). Work order 5 changes mode and activation in place at a tick boundary (no new mapping), so
  per-publish header writes would race a reader that is validating the slot it just copied.
- Failure scenario: the C core accepts a whole slot from activation N while the header already says N+1 (or the other
  way round), and uploads one frame of a different mode's payload layout, or a retiring frame shows after a switch.
- Fix: before P2b fixes the ABI for production, move `activation_id` and `mode_code` (and the engine generation if it
  can change without a remap) into the slot head inside the seqlock (the 8 spare bytes at offset 40 fit two u32), and
  keep the header for per-mapping constants only. Bump `ABI_VERSION`.

**A3-M5. 4V overstates what P2b + P3 make Python-free and what QRhi gives for compute.**
- Evidence: (1) "P2b removes the tick and DSP from the main process; P3 removes the draw": the P1 spike's Risk 1
  (`Native_Core_P1_Spike.md`, "Risks for P2 and P3", 1) lists Python on the render thread beyond the visualizer's draw:
  `updatePaintNode` of the background item, the surface backdrop and the Studio viewport during sync, the visualizer
  retirement `beforeRendering` one-shot, frame-trace hooks, and PySide's first virtual call per method. The thread is
  Python-free only when every item in the window is. The P2b decode at sync (A2-H3) is called interim, with no exit
  condition before P3. (2) "Async compute ... so Vulkan compute queues can take them": QRhi records compute passes
  into the same command buffer as the frame (no separate queue). Async compute needs native Vulkan through the RHI
  native handles, which P1 Risk 2 says breaks single-core neutrality. The Decision lists async compute as "Not our
  bottleneck" and as a trigger only (`Graphics_Backend_Decision_2026-11-05.md:37, 67`). (3) "GLSL 460 that `qsb`
  compiles to SPIR-V (port-readiness rule 5)": P1 compiled the spike's GLSL 440 shaders. No test compiles the 8
  production compute shaders to SPIR-V (no `qsb`/SPIR-V test under `tests/`), and rule 5 says reviews enforce 1-4
  until such a test exists. Rule 1 binds new programs only, so "stay QRhi-portable" is unproven for the existing ones.
- Failure scenario: P3 planning counts on a render thread that is GIL-free after the visualizer port and on async
  compute from QRhi; neither holds without more work.
- Fix: reword 4V: render-thread Python ends when every item is native (P1 Risk 1's list); async compute only through
  native handles, per the Decision's trigger 3; add the `qsb` SPIR-V compile test (rule 5) for the 8 compute shaders
  now, since `qsb.exe` already ships with PySide6.

### Low

- **A3-L1. "A device open fails the tests" holds in process only.** The fixture patches `create_audio_capture` in
  the pytest process (`tests/test_visualizer_engine_live.py:26-34`); the spawned worker is not patched, so a worker
  session that bypassed the factory would open the real loopback before failing on `_backend` None or the 30 s capture
  edge. Fix: have `_open_capture`'s backend be the only one `_tick_live` accepts (check
  `engine._audio_worker._backend is self._backend` after the open edge) and refuse `inputs="live"` without the factory.
- **A3-L2. Recorded-backend fidelity gaps that 4b will hit.** `RecordedCaptureBackend` fixes its block size at
  construction (`recorded_capture.py:79-80`); a config-epoch restart (Block Size change, `audio_worker.py:893-896`)
  keeps the old size, where device backends renegotiate at start (`utils/audio_capture.py:374, 595`). On Auto it
  reports 480 where WASAPI reports 0 (`_effective_block_size` differs). Capture health and staleness use the real
  `time.monotonic` (`audio_worker.py:975-989`) while the rig runs on the authored clock, so a resume after a long
  authored pause is never stale in the rig and 4b will not exercise `wake()`'s restart (`beat_engine.py:1935-1938`).
  Fix: rebuild the block size in `start`, mirror Auto's 0, and drive the worker's monotonic reads from the session
  clock in 4b (or a seam for them).
- **A3-L3. The GIL-share numbers are more precise than the method.** The analyses (.315/.322) and rfft n=480 (.324)
  read *below* the GIL-held calibration (.493) and are clamped to 1.0; the released calibration reads 1.17 (above
  1). The noise is about ±20% of the span. "It releases more at 1 Mi points" is contradicted by the report (.78 held
  vs .75 at 1,024). The GIL probe feeds both modes 480-sample blocks (`live_engine_cost.py:276`; Bubble's is 128).
  The conclusion (the analysis is essentially GIL-bound) is plausible. Fix: state it as a bound, not a share.
- **A3-L4. The paused refusal is acceptable for slice 1, but the reference has no idle path.** The shipped clips
  have no paused frames, so the idle waveform, idle bars, keepalive expiry and warm-grace drain
  (`beat_engine.py:1319-1334`) that a P2b worker runs at every pause are outside "the rig every P2b gate uses". 4b
  owns them; until then no gate result covers a paused worker.
- **A3-L5. Seam nits.** `self._capture_backend_factory or create_audio_capture` (`audio_worker.py:858`) falls back to
  the device for a falsy factory; use `is None`. The docstring says "installed once", but the code allows
  replacement whenever capture is idle; say "while idle".

### Verified sound

- Production is unchanged. The observer is a class attribute (None). Production pays one attribute load and an
  `is not None` per analysis, in the `finally` after the slot release (`beat_engine.py:1032-1034`).
  `has_analysis_in_flight` is evaluated only when an observer is installed, and its unlocked read then races nothing
  (the rig's tick thread is blocked in `wait`). The factory is resolved under the capture lock in each drain iteration
  as `factory or create_audio_capture` (`audio_worker.py:858, 878`), so the module global is still looked up when
  capture opens and existing monkeypatching of `audio_worker.create_audio_capture` still works (the live fixture
  relies on it). The refusal conditions are the same as `set_capture_lane`'s.
- The settled edge loses no wake. `clear` comes before the step, the commit comes before the observer, and in-flight
  is checked after the step. Callbacks pushed before adoption are admitted by `_capture_start_pending`
  (`audio_worker.py:728-730`), so the first push does not race the capture lane.
- The import fix: `utils.curve_nodes.interpolate_nodes(_mirrored)` is the function the editor re-exports
  (`ui/tabs/media/spectrum_shape_editor.py:99`).
- The gate report matches the doc (27 pairs, 31,644 frames, 0 mismatching).

### Not verified

- The whole-clip gate and `live_engine_cost.py` were not re-run. The free-running asynchronous behaviour (A3-H1) was
  reasoned from the code and one ordered probe, not measured.
- Whether any renderer reads Bubble's `common.waveform_count`. Whether `qsb` compiles the existing compute shaders.
  The Vulkan flip on a real window (P1: operator-only).

## Checkpoint audit 4 (8 Nov): P2b slice 2

Scope: d99e4fd1 and 662e159f (merged at 97c1fb01). Ran: `test_visualizer_engine_packet_abi.py`,
`test_sphere_voxel_audio_contract.py`, `test_visualizer_engine_live_off_steady.py` (89 passed, 95 s). Probes on the
live rig, in process only: (a) production order, Sphere / Oscilloscope / Neon Lake, scenarios `steady`, `pause_warm`
and `reentry` on 4 s of the shipped clip, with `set_analysis_spectrum_demand` real vs a no-op, frame digests compared;
(b) the per-commit spectrum copy timed at 32/64/128 bands; (c) `free` order on 6 s of the clip (Spectrum, Sphere),
counting pending-source replacements and commits that land inside a tick. The 21-minute gates were not re-run; the
gate reports were read. One change reaches production today: `declare_mode_engine_demands` (A4-M1). The rest is the
rig, the ABI and test seams.

### High

**A4-H1. The rig copies the owner's control sequences; it does not run them. The in-process vs worker gate cannot
see the copy drift from the owner, and work order 5 would ship the copy as production code.**
- Claim: 4P slice 2, "Every control edge mirrors the production owner's engine calls on the logical side"; the
  switch is "the owner's `_activate_pending_mode` with its `_apply_configuration` on the existing controller and
  engine".
- Evidence: `feature_replay.switch_offline_controller_mode` (`feature_replay.py:424-474`) is a hand-written second
  sequence of the owner's logical activation (`quick_display_visualizer_owner.py:1545-1725`, `_apply_configuration`
  `:328-450`). `EngineSession._set_playing` / `set_display_power` / `_start_playback` (`engine_worker.py:230-286`)
  are second copies of `set_playing` (`:561-620`), `set_display_power` (`:224-285`) and `start` (`:1761-1807`).
  Today they agree step for step on the engine and logical side (checked: wake, playback state, fence on resume;
  release / acquire / ensure_started / fence / rebase; transaction, defaults, kwargs, technical config, mode state,
  fence, cancel/reset, pending identity, render activation). Differences that are harmless now but show the copy is
  not the code: the switch resolves one dict for both the logical and presentation kwargs where the owner takes
  `pending["logical_kwargs"]` / `pending["presentation_kwargs"]`; unpark always re-acquires and rebases where the
  owner does so only when it released for display power / the runtime is parked; the owner's
  `controller.stop_logical_runtime()` and `set_logical_parked` have no counterpart. Both sides of every gate run
  `EngineSession`, so a change to the owner's sequence (new reset, reordered fence, new kwarg) passes every P2b gate.
- Failure scenario: someone fixes an activation bug in `_activate_pending_mode` (the area has R-series history:
  CHK10 phantom slot, Edit profile rollback); the rig keeps the old order, the gates stay green, and work order 5
  wires the worker's `VIS_SET_MODE` to `feature_replay.switch_offline_controller_mode`: a replay module becomes the
  product's activation path, and the main process and worker have two owners of one transition.
- Fix: before work order 5, extract the logical-side activation commit (the part of `_activate_pending_mode` from
  `begin()` through the pending identity, and `_apply_configuration`'s logical half) and the engine edges of
  `set_playing` / `set_display_power` / `start` into one module both the owner and `EngineSession` call (the owner
  keeps Edit profile, backdrop, render bridge, crossfade). Delete `switch_offline_controller_mode`. Add a test that
  drives the owner's methods and the session's on two engines through the same edge script and compares the engine
  call log, so drift fails.

### Medium

**A4-M1. `declare_mode_engine_demands` changes Sphere's production frames for the whole session, not one commit; it
does not change Oscilloscope or Neon Lake in production order; and it costs Neon Lake with its reaction off a copy
per commit for nothing.**
- Claim: commit message and 4P, "so the first commit after an activation publishes one"; docstring
  (`tick_pipeline.py:957-976`), "The spectrum-reading modes (Sphere, Oscilloscope, Neon Lake) demand the analysis
  spectrum at every commit, so the first commit after an activation ... publishes one instead of leaving a
  commit-long gap"; the control test runs in `settled` order only
  (`test_visualizer_engine_live_off_steady.py:283-308`).
- Evidence: production calls it every tick (`tick_pipeline.py:1000`), so `_publish_pre_agc_analysis_spectrum_if_requested`
  (`beat_engine.py:1145`) copies `_freq_values` on every commit while a reader mode is active. Probe (a), production
  order, demand real vs no-op: Sphere differs on 359/364 (`steady`), 542/547 (`pause_warm`), 268/273 (`reentry`)
  frames, from frame 5 to the end (its integrators carry the one earlier spectrum); Oscilloscope and Neon Lake
  (shipped settings) 0 differing frames in all three. Why: Sphere reads the spectrum only while its source is current
  (`sphere_capture.py:79, 103`), so after an activation, and after any re-entry where the source is not yet current,
  nothing requested the next commit's spectrum; Oscilloscope reads it every tick unconditionally
  (`logical_frame_capture.py:620`), which already requested the commit that lands after the tick. Neon Lake reads it
  only while its terrain reaction is enabled (`logical_frame_capture.py:351-362`), and the shipped default is off
  (`default_settings.py:5887`); the mode rule demands it regardless, so every commit copies a spectrum nobody reads.
  Probe (b): 4.0 us (32 bands), 8.9 us (64), 14.5 us (128) per commit, GIL-held on the compute lane, ~70-90 commits
  per second: ~0.3-1.3 ms of GIL per second in the main process today, for a mode that is otherwise dormant there
  (`mode_capabilities.py:56-59` itself says "while enabled"). No golden or test sees any of this: the Studio and
  replay engines answer the spectrum themselves (`feature_replay.py:332`), so only the live `_SpotifyBeatEngine`
  is affected, and the slice's own gate compares two sides that both carry the change. Checkpoint audit 3's A3-M1
  was itself wrong about Oscilloscope and Neon Lake in production order (it reasoned from the settled rig).
  The race case is also changed, unmeasured: live, a commit can land before the same tick's spectrum read, and the
  request bit then skipped every other commit; with the demand every commit publishes.
- Failure scenario: Sphere, an accepted mode, ships a different (probably better: no first-tick gap, no stale
  pre-pause spectrum on re-entry) trajectory in production with no visual or reactivity check and a record that says
  "one commit". Neon Lake with its reaction off pays a per-commit allocation the dormancy rule forbids.
- Fix: correct 4P and the docstring (Sphere: whole session; Oscilloscope / Neon Lake: no change in production order,
  only the race). Make the demand follow the setting that gates the read (Neon Lake: reaction enabled, strength > 0,
  any part > 0, the same predicate `logical_frame_capture` uses), declared from the resolved logical config. Render
  Sphere before/after on a shipped clip (production order) and record it; add a production-order variant of the
  activation test for Sphere.

**A4-M2. `production` order is live's nominal case, not "as live"; the reference has no intra-tick commit and no
pending-source replacement, and the `free` stress run does not supply them either.**
- Claim: 4P, "the tick reads the previous commit, as live"; "`free` (no hold, no wait) is the stress order";
  "stress ... 27/27 clean, every frame taken, 0 torn".
- Evidence: the hold (`engine_worker.py:195-198, 354-369`) forces each analysis to commit strictly after the tick
  that submitted it and strictly before the next input. Live, the analysis (~0.4-0.8 ms) runs during the rest of the
  tick: when it lands after the bars read (`consume_engine_bars`) but before the later energy / onset / spectrum
  reads in the capture, one frame mixes two commits; when the lane is slow (GIL load) the next step finds the slot
  busy and replaces the pending source (`beat_engine.py:1130-1134`). Probe (c), `free` order, 546 ticks each:
  Spectrum and Sphere 0 pending-source replacements, 1 commit inside a tick. The gate report: every stress
  run took `ticks == taken` (1,148 / 1,164 / 1,204 of each), so the reader never missed a frame: no coalescing, no
  writer lapping the reader, no torn read possible. `stress_in_worker` (`live_engine_gate.py:202-249`) runs `steady`
  only; its `ok` checks revisions advancing and the last one taken, not A3-H1's invariants (commit sequence never
  backwards; bars, energy and commit stamp of one tick from one commit).
- Failure scenario: work order 5's free-running worker hits intra-tick mixes and pending replacements on most busy
  frames; no gate has ever run them, and "stress 27/27 clean" is read as evidence that it did.
- Fix: say in 4P that `production` order is the nominal one-tick-latency schedule. Make the stress run asynchronous
  for real: feed inputs from a producer thread on the authored cadence (or batch several VIS_INPUTs per round trip),
  hold the compute lane at random points with the admission gate (a seeded jitter schedule), and assert the A3-H1
  invariants plus counters (pending replacements > 0, intra-tick commits > 0, frames coalesced > 0) so the run
  proves it exercised what it claims. Run it on the off-steady scenarios too.

**A4-M3. `VIS_SET_MODE` for the current mode silently drops its preset and settings.**
- Evidence: `_apply_pending_mode` returns when `mode == self.mode` (`engine_worker.py:308-309`), but the message
  carries `preset` / `settings` and is acknowledged as success (`:471-475`). The owner has a same-mode `kind ==
  "preset"` activation (`quick_display_visualizer_owner.py:1611-1625, 1641-1650`): new settings, technical config,
  view motion re-arm, compute/smoothing/floor reset and a new activation.
- Failure scenario: work order 5 sends a preset change as `VIS_SET_MODE`; the worker replies success and keeps the
  old settings.
- Fix: apply a same-mode request when preset or settings are given (the owner's preset kind), or refuse it with an
  error; test both.

**A4-M4. The ABI's protected-edge mask crosses activations, so a slot labelled with the new identity can carry the
old activation's edges.**
- Evidence: `FramePacketWriter.publish` ORs every unacknowledged edge into the new slot regardless of identity
  (`packet_abi.py:184-189`); the Python payload only coalesces within one generation and activation
  (`packet_mailbox.py:104-107`). Before ABI 2 the mapping held one activation; slice 2's in-place switch makes the
  crossing reachable (switch while the reader has not consumed an edge-bearing frame).
- Failure scenario: P3's native reader validates the slot identity (activation N+1) and acts on a protected edge
  produced under activation N.
- Fix: keep the identity with each pending edge entry and drop entries whose identity differs from the slot being
  published (or reset `_edges` when the identity changes); test with a switch between an edge and its consume.

**A4-M5. The slice's gate evidence is not where the doc says, and lives only in an unremoved worktree.**
- Evidence: `.artifacts/evidence/architecture/native_core_p2/20261108_live_gate_slice2{,_settled}/` do not exist in
  the repo's evidence store (`.artifacts/evidence` -> `D:\Temp\Scratch\SRPSS\evidence`; only `20261108_live_cost`,
  `_live_gate`, `_main_cost`, `_worker_gate`). The two reports exist only at
  `.claude/worktrees/agent-a30304d24c8bff822/.artifacts/evidence/...` (a real directory inside the slice's worktree,
  which was not removed after the merge). Their content matches the doc's numbers.
- Failure scenario: the worktree is cleaned up (the standing rule) and the 21-minute and 15-minute results cited as
  the slice's proof are gone.
- Fix: copy both reports into the evidence store at the cited paths, then remove the worktree.

### Low

- **A4-L1. The slot head's odd `sequence_begin` is not stored before the identity.** The writer packs the odd begin
  and the identity in one `_SLOT_HEAD.pack_into` (`packet_abi.py:194-196`, "in the same store as the slot head").
  CPython's `pack_into` zero-fills the target struct before packing the fields (from CPython's `_struct.c`
  `s_pack_internal`; not verified on this build), and the zero-fill's store order is the C runtime's `memset`'s, so
  the identity bytes can become visible before `sequence_begin` changes. A reader that loads `sequence_end`, the head
  (old begin, new or zeroed identity) and then the old begin again, while the writer is preempted inside that store,
  accepts a slot whose identity is not its frame's. It needs the writer to lap the reader twice (three slots) and be
  descheduled inside one C call: rare, and the same holds for every head field since ABI 1. Fix: store the odd begin
  with its own `_U64.pack_into`, then pack the rest of the head from offset 8; document the store order the P3 C
  reader relies on.
- **A4-L2. `MODE_CODES` append-only is not enforced.** `test_every_registered_mode_has_one_stable_header_code`
  (`test_visualizer_engine_packet_abi.py:222-232`) checks coverage, uniqueness and non-zero; renumbering or reordering
  the dict passes. These are ABI constants (not user-editable values), so pin the table literally in the test and fail
  on any change to an existing entry.
- **A4-L3. The device refusal is a process-global swap with nested-lifetime hazards.** `_devices_refused`
  (`engine_worker.py:415-427`) saves and restores `audio_worker.create_audio_capture`. Two live sessions in one process
  that close out of order (A then B open, A closes first) leave the refusal installed for good, and any production
  owner in that process cannot open its device while a session is open. The worker hosts one session at a time, so
  only in-process tools and tests are exposed. Fix: a refcounted refusal, or refuse inside the session's own factory
  path (A3-L1's `_backend is self._backend` check) instead of patching the module global. A3-L5 (`or` instead of
  `is None`, `audio_worker.py:872`) is still open.
- **A4-L4. "Wake's wall-clock restart is proven frame-neutral" is a rig property.** The test forces
  `is_capture_stale` both ways on Oscilloscope only (`test_visualizer_engine_live_off_steady.py:336-349`); it is
  neutral because the recorded backend loses no audio across a restart and the next push comes after it. A device
  restart drops real audio for its reopen latency. The worker's restart count is not reported, so the gate cannot
  say whether its two sides took the same path. Fix: say "frame-neutral in the rig"; report the worker's restarts.
- **A4-L5. The pause clips assume capture delivers nothing while Media is paused.** `synthesise_pause` gives every
  paused tick the last playing history; `_on_audio_samples` (`audio_worker.py:737-800`) appends to the history
  whenever capture runs, playing or not, and while warm (6 s grace) a loopback device keeps delivering whatever else
  the system plays (or silence, depending on the backend). The gate covers the silent-device case only. Fix: a paused
  variant that pushes silent blocks (and one with other audio) through the warm grace.
- **A4-L6. Doc leftovers.** 4V still says "with the writer filling the header identity and flags per publish"
  (design doc, 4V "Zero-Python uploads") and work order 6's P3 note says "the header identity written on configure"
  as the validation source; ABI 2 made the slot the identity and the header configure-time only. The production-order
  admission failure (`_admission_failed`) is checked only after the tick has published its frame
  (`engine_worker.py:363-368`): fail-closed, but one frame from an unheld order reaches the mailbox first.

### Verified sound

- Production cost of the seams: `set_analysis_admission_gate` costs one attribute read and an `is not None` per
  analysis (`beat_engine.py:901-903`), checked before the gate token / activation test so a held analysis that
  outlives a switch is still rejected. `fence_capture_transactions` has no production caller. No deadlock path: the
  hold blocks only the engine's own serial analysis lane, nothing in `logical_tick` waits on that lane, the hold is
  released in `finally` and bounded (30 s), and switches, display power and close run with the gate open.
- The production order does read the previous commit (the adversarial 50 ms test, mutation-checked per the doc); the
  gate report's best lag against the lanes engine is 1 tick, as expected.
- The seqlock read order and acceptance (`packet_abi.py:249-261`): `sequence_end`, head, payload, `sequence_begin`;
  the identity is read inside that window. No reader decides a slot from the header identity
  (`FramePacketReader.identity` / `mode_code` are set at attach and unused; the Python reader decodes the payload's
  own identity). An ABI 1 mapping is refused by `_validate` on both sides (`PacketAbiError`), and the worker's
  configure reports it as a failure. `-1` round-trips as `0xFFFFFFFF`.
- The control sequences match the owner's engine calls today (see A4-H1 for why that is not enough): `set_playing`'s
  wake-before-playback-state and the fence on resume, `set_display_power`'s release / acquire / ensure_started /
  fence / rebase, `start`'s acquire, same-state playback commit and cold `ensure_started`.
- The gate reports match the doc (126 pairs, 170,622 frames, 0 mismatching, 27/27 stress; settled 99 pairs, 138,978
  frames), read from the worktree copy (A4-M5).

### Not verified

- The CPython `pack_into` zero-fill on this build and the C runtime's `memset` store order (A4-L1: from source
  knowledge). Whether Sphere's whole-session divergence (A4-M1) is visible; it was measured as digests, not rendered.
- How a real loopback device behaves through a Media pause (A4-L5), and whether Oscilloscope's history after a
  display-power re-entry matches production (the rig's stream continues the recording across the park; a device
  reopens on fresh audio).
- The `free` order in the worker process (probe (c) ran in process; the worker's IPC round trip makes races rarer
  still). The whole-clip gates were not re-run.
