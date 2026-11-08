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

## Checkpoint audit 5 (8 Nov): the shared logical_edges module and follow-ups

Scope: e66644c1, b24d6e28, df394784, 3dea34cb. Diffed the old owner (`git show df394784^:...owner.py`) against the
new owner plus `logical_edges.py` method by method. Ran: the parity test, `test_visualizer_engine_packet_abi.py`,
`test_beat_engine_spectrum_demand.py`, `test_sphere_voxel_audio_contract.py`, `test_visualizer_camera_activation.py`,
`test_visualizer_custom_geometry_profiles.py`, `test_visualizer_engine_import_weight.py`,
`test_visualizer_mode_dormancy.py` (146 passed, 21 s). Probes, in process (live `EngineSession`, production order,
shipped clip 4 s; digests of every frame): (a) the current rising-edge demand vs a no-op demand (pre-slice-2) vs the
slice 2 standing demand, Sphere `steady` / `reentry` / `pause_warm`, with a real-vs-real control; (b) spectrum copies
per commit, Neon Lake / Oscilloscope (`switch`) and Sphere (`steady`); (c) what Qt modules the shared edges load at
call time (an import hook). Whole-clip gates not run. Probe scripts deleted.

### Medium

**A5-M1. e66644c1 does not restore Sphere's production frames. The rising edge gives frames byte-identical to the
slice 2 standing demand. They still differ from pre-slice-2 for the whole session.**
- Claim: e66644c1, "Slice 2's standing demand changed Sphere's production frames for the whole session ... Now the
  mode rule's declaration requests only the first commit after an activation ... afterwards the tick's own reads
  request publications exactly as before"; `beat_engine.py:1566-1571`.
- Evidence: probe (a), production order. Rising edge vs no-op: Sphere differs on 359/364 frames (`steady`), 268/273
  (`reentry`) and 542/547 (`pause_warm`), from frame 5 to the end. These are the numbers A4-M1 measured for the
  standing demand. Rising edge vs standing demand: 0/364 differ. Real vs real: 0. Probe (b): Sphere makes 282 copies
  with the edge and 281 without, so there really is only one extra copy per activation. But that first spectrum flows
  into Sphere's integrators and changes the rest of the session. Neon Lake and Oscilloscope match pre-slice-2 (175/282
  copies either way, 0/547 frames differ in `pause_warm`), so the per-commit cost A4-M1 raised is fixed. Stale
  docstrings: `tick_pipeline.py:957-967` ("demand the analysis spectrum at every commit") and the class comment at
  `beat_engine.py:141` ("every commit publishes it").
- Failure scenario: the record reads as if the Sphere change was reverted. In fact Sphere still ships a different
  trajectory, with no visual check. A4-M1 asked for a before/after render and a production-order Sphere test, and
  neither was done.
- Fix: say in the design doc that Sphere's whole-session trajectory change is the intended result of the first-commit
  spectrum, and that only Neon Lake's cost was undone. Render Sphere before/after (showcase WebP, production engine)
  and keep the result or drop the demand. Correct the two docstrings. Add a production-order variant of
  `test_spectrum_readers_publish_on_the_first_commit_after_activation` (it runs `settled` only, `:347`).

**A5-M2. The configure edge is still a hand copy, and the parity test hides it by configuring both hosts the same
way.**
- Claim: design doc, Slice 2 follow-ups, "`apply_logical_configuration` (the owner's `_apply_configuration` ...) ...
  both hosts call them"; `logical_edges.py:9-11` ("or the owner's `configure`").
- Evidence: the session's initial configuration is `configure_offline_controller` (`feature_replay.py:441-467`, called
  at `engine_worker.py:150`), not `apply_logical_configuration`. It differs from the owner's `configure`
  (`quick_display_visualizer_owner.py:279-300` -> `_apply_configuration`) in several ways:
  - no `resolve_logical_mode_state`
  - no warm re-entry fence
  - `playing = True` is forced (`:460`)
  - `_waiting_for_fresh_engine_frame = False` (`:467`)
  - one kwargs dict serves as both logical and presentation kwargs
  - render activation begins immediately
  The parity test sets up both hosts with `configure_offline_controller` (`test_visualizer_logical_edges_parity.py:84`),
  so the owner's configure is never compared. The activation path is now shared; the configure path is not.
- Failure scenario: work order 5 wires the worker's configure to `configure_offline_controller`, so a replay helper
  becomes the product's first activation. A configure fix in the owner (new reset, new fence) never reaches the worker,
  and every gate stays green.
- Fix: give the session's configure `apply_logical_configuration`, with the owner's inputs (separate logical and
  presentation kwargs, technical cache, Media's `playing`). In the parity test, configure each host through its own
  configure path and compare that step too.

### Low

- **A5-L1. The parity test cannot see several owner branches.** In both hosts `logical_runtime` is None (the owner's
  `_start_logical_runtime` is stubbed, `:108`), so `resume_engine_after_park` always takes the rebase branch. Moving
  the owner's `set_logical_parked(False)` before the resume would go unnoticed, and so would the unparked-runtime
  error branch. Also never exercised:
  - `start` while the displays are off (owner `:1583-1591`, the tail release)
  - every failure path (`LogicalRuntimeNotJoined`, `recover`, begin/end missing, the bind stage)
  - the cold-engine fence (the recording engine is always warm)
  - the layout-profile callback (owner only, and not recorded)
  - diagnostics-on branches
  By construction it cannot catch a change inside `logical_edges` either: both sides follow it. The owner's own
  regression tests carry that. The negative control covers session-side drift only. Fix: add a script with a stub
  logical runtime whose `is_parked` and `set_logical_parked` are recorded, a start-while-off script, and one failing
  activation per stage on the owner (comparing the owner's log against a pinned sequence, not against the session).
- **A5-L2. "QtCore at most" holds at import time only.** Probe (c): `commit_logical_activation` ->
  `apply_logical_configuration` (`logical_edges.py:94`) -> `apply_presentation_vis_mode_kwargs`
  (`config_applier.py:188`) -> `_color_or_none` imports `PySide6.QtGui` (`config_applier.py:32`) on the first call.
  This predates the slice (`configure_offline_controller` does the same; the comment at `engine_worker.py:146-148`
  admits it). But `logical_edges.py:18` and the design doc ("QtCore at most; in the import-weight probe") overclaim,
  and the import-weight test checks only import time. Its lazy function-level imports are covered only because other
  probed modules happen to import them. Fix: reword. When work order 5 removes the QColor reads, add a call-time
  probe: one configure plus one activation in a fresh interpreter, then assert on `sys.modules`.
- **A5-L3. The writer-side `PacketMailbox.clear` drops only the Python unread record.** `FramePacketWriter._edges`
  and the mapping's newest slot stay (`packet_mailbox.py:232-239`). Its docstring says "the next publication
  coalesces none of its edges", but the slot-level mask still carries edges of the same identity. Today every writer
  clear (`stop_logical_runtime` at a session activation) comes before an identity change, so b24d6e28's filter drops
  them. A future same-identity clear (`reset_logical_handoff`, a park) would not. No production caller: the main
  process never builds a `PacketMailbox`, and the publish guard is set only by a production-order session. Fix: clear
  the writer's `_edges` in the same branch, or document that the identity filter carries the guarantee.
- **A5-L4. The rising edge's reset coverage is asserted by hand.** `test_beat_engine_spectrum_demand.py:38-39` assigns
  the two fields instead of calling `reset_smoothing_state` / `reconfigure_bar_count` / `force_stop`, so a reset that
  forgets the declaration still passes. Today all three clear both fields (`beat_engine.py:540-541, 557-558, 795-796`),
  and only the publication clears the request alone (`:1169`). A path that activates with no reset: a new owner on the
  warm shared engine. `force_stop` runs only at shutdown (`beat_engine.py:2050`), so Sphere's declaration stays True,
  no edge rises, and the first-commit gap A3-M1 targeted is still there on warm owner recreation. That matches
  pre-slice-2 (not a regression), but "the first commit after an activation" does not cover it. Fix: call the real
  resets in the test, and say where the guarantee stops.
- **A5-L5. Only owner-visible change: one failure-log label.** If `render_bridge.discard_pending()` raises, the log
  now names `step=activate_committed_profile` (it was `begin_engine_transaction`), because `progress.step` is set
  before the callback (`logical_edges.py:228-229`). Harmless.
- **A5-L6. The device refusal now covers one engine, not the process.** It also only matters when no capture factory
  is installed (`audio_worker.py:_capture_factory`), and the session always installs one (`engine_worker.py:179`). So
  it is defence in depth for the session's own engine. Any other engine in the worker process is no longer refused,
  which the old global swap did refuse. Acceptable while the worker hosts one engine; worth saying in 4P.

### Verified sound

- **The owner refactor preserves production behaviour.**
  - `set_playing`, `start` and `set_display_power` make the same calls in the same order, under the same conditions
    (`_started` for wake; `_engine_acquired` for release; `_engine_released_for_display_power` and
    `controller.playing` for acquire/ensure_started; the runtime-parked condition for rebase).
  - The host flags are set at the same points: after acquire on start and on reacquire; only when a release happened
    on park.
  - `_apply_configuration` keeps the same sequence, with the backdrop refresh in the same place.
  - `_activate_pending_mode` handles each stage as before:
    - `ensure_engine` and the stop raising: re-raised with no phase change.
    - A non-joined stop: Edit profile reverted, `failed`, a `RuntimeError` subclass with the same message.
    - Missing or raising begin/end: `failed`, no log.
    - A failure inside the transaction: `recover` runs inside the `except`, before `end()` in `finally`, as before. It
      logs once, restores and restarts the outgoing runtime inside the transaction, and returns before bind.
    - Bind failures: same log and `failed`.
    - An `end()` that raises after success or recovery: propagates as before.
  - The new unknown-kind `ValueError` cannot be reached from the owner (`_request_visualizer_activation` admits only
    mode/preset).
  - The session's divergences (switch stops the outgoing runtime, resume re-acquires only what park released, engine
    binding at first input) are all session-side; none reaches the owner.
  - The production capture path is unchanged: no factory and not refused resolves to `create_audio_capture`, looked
    up at call time, so test monkeypatches still apply.
- **The parity test compares real paths.** It runs the owner's real methods and the session's real methods on two
  controllers, recording engine and controller calls. It fails if either host adds, drops or reorders a recorded call
  outside the shared module: the session-drift control is proven, and owner-side drift is caught symmetrically.
- **The edge-identity filter matches in-process semantics.** In process, an edge is also lost across a switch:
  `stop_logical_runtime` clears the mailbox, the render bridge clears its edges, and
  `_coalesce_protected_state` refuses to coalesce across a mode or engine generation. Within one activation the state's
  `engine_generation` is the engine's current one, so the filter does not drop same-activation edges.
- **Begin-first stores stay compatible with the reader.** The reader (`packet_abi.py:258-267`) still accepts only
  `end == head begin == final begin == latest`, even. The writer now makes begin odd before any other head byte.
- **The `MODE_CODES` prefix ratchet fails** on renumbering, reordering, removal or reuse.
- **The publish guard costs one attribute read per publish**, has no production caller, and is installed before any
  tick.
- **All three resets clear both the request and the declaration**, and no path clears only one.

### Not verified

- Whether Sphere's whole-session divergence (A5-M1) is visible: measured as digests, not rendered.
- Cross-process behaviour of the writer clear and the identity filter against a real main-process reader, since no
  production reader exists yet.
- The owner's 35 focused files (668) cited by the slice; only the 8 files above were re-run. The whole-clip gates.

## Checkpoint audit 6 (8 Nov): configure shared, worker-paced ticks (5.1)

Scope: 32f28d4f (audit-5 follow-ups) and d056e8b5 (work order 5 slice 5.1). Diffed the owner, the host binding and
`logical_edges.py` against `32f28d4f^` line by line; read `engine_worker.py`, `recorded_capture.py`,
`logical_runtime.py`, `packet_mailbox.py` / `packet_abi.py`, the parity and paced tests and the `--paced` gate. Ran:
the parity test, `test_visualizer_engine_paced.py` and `test_visualizer_engine_packet_mailbox.py` (42 passed, 46 s);
`live_engine_gate.py --paced --paced-seconds 2 --modes spectrum bubble` (both OK: 181/182 frames at 89.9/90.1 Hz, 0
skipped, taken 44/45, 0 torn, audio 2.000/2.000 and 2.011/2.011 s). Probes (deleted): (a) `PacedPcmSource` with a
cadence step landing inside `RecordedCaptureBackend.start` between the callback install and `on_started`; (b) the
in-process paced gate with `RecordedCaptureBackend.offer` replaced by a stub that never calls the capture callback.

### Medium

**A6-M1. The paced gate's "audio on the clock" check is the source's own arithmetic. It passes with no audio reaching
the engine.**
- Claim: the 5.1 record says "the audio delivered >= 97% of the paced audio time"; gate docstring "the audio delivered
  is the audio clock's".
- Evidence: `live_engine_gate.py:345` compares `delivered_s` with `paced_s`, and both come from
  `PacedPcmSource.describe()`. `delivered_samples` counts what `due()` handed out (`recorded_capture.py:208-212`).
  `_paced_step` ignores `offer()`'s return value (`engine_worker.py:367-368`), so blocks offered while capture is
  closed still count as delivered. Probe (b): with `offer` stubbed to drop every block (562 offers, none reached the
  callback), `paced_in_process(..., "spectrum")` returned `paced_ok=True`, `delivered_over_paced=0.9988`. Nothing in
  the verdict reads the engine side: no capture-callback count, no analysis commits, no non-silent bars.
- Failure scenario: a broken capture path in the worker (wrong channel layout, a callback that drops blocks, capture
  never reopening after a switch) passes the paced gate on every mode. The gate shows the frames arrive on time, not
  that they react to the audio.
- Fix: count the blocks `offer` actually delivered and gate on that. Also gate on engine-side evidence: the audio
  worker's callback count or the analysis commit count over the run, plus non-zero energy in a reasonable share of
  frames. Add a negative control that drops every offer.

**A6-M2. A paced mode switch that fails is not fail-closed.**
- Claim: 5.1 record, "a mode or preset request applies at once as the owner's activation does"; and the worker's rule
  that an edge which may have half-applied closes the session (`engine_worker.py:621, 634`).
- Evidence: for a paced session `request_mode` calls `_apply_pending_mode()` synchronously (`engine_worker.py:444-447`),
  so the commit, bind, cadence restart and `_settle_capture` all run inside the `VIS_SET_MODE` handler. That handler
  has no try/close (`engine_worker.py:625-629`). An exception reaches the generic handler (`:643`), which replies with
  an error but no `session_closed` and leaves the session open. In input-paced sessions the same apply ran inside
  `VIS_INPUT`'s try, which does close the session (`:606`). `_paced_failure` stays None, so `finish` reports no failure.
- Failure scenario: an activation that raises after `commit_logical_activation` has stopped the runtime (any
  transaction step, `LogicalRuntimeNotJoined`, the capture settle timing out) leaves a session with no cadence and the
  engine reference still held (capture open), which still claims to be live. The main process has no `session_closed`
  to act on (5.5's fade/reconfigure will key off it), and `VIS_START` refuses because `_live_started` is True.
- Fix: give `VIS_SET_MODE` the same try/`_close_session`/`session_closed` as `VIS_START` / `VIS_SET_PLAYING` /
  display power. Add a paced test that makes a switch's transaction raise and asserts `session_closed`.

**A6-M3. A failed paced step freezes the session for good, with no log. In process the cadence keeps stepping.**
- Claim: 5.1 record, "a step that raised fails the session closed ... reporting it to the owner unprompted ... are
  5.5".
- Evidence: `_paced_step` catches the exception itself (`engine_worker.py:369-372`), so `VisualizerLogicalRuntime`'s
  own failure path (log once, count, keep stepping, `logical_runtime.py:583-593`) never sees it. The step only sets
  `_paced_failure`, without logging. `_paced_failed` (an Event) is set but nothing reads it. The test pins
  `step_failures == 0` (`test_visualizer_engine_paced.py`, failing-step test). In process, the owner's step uses the
  runtime's default handling, so one transient tick exception is logged and the next step retries.
- Failure scenario: under 5.2's admission, a single transient tick exception in the worker leaves the Visualizer on
  its last frame indefinitely. Nothing is logged in either process, and the failure only surfaces in `VIS_STOP`'s
  reply. The worker also keeps waking at 90 Hz to return at once (the second deferred item).
- Assessment for 5.5 vs 5.2: the full fade and reconfigure can wait for 5.5, since 5.2 is behind a code-level admission
  with in-process as the default. But 5.2 changes what the product does on a step failure, so before 5.2 decide and
  document one of two contracts: (i) the worker retries like the in-process runtime, or (ii) the session closes and
  says so. Under (ii), add at least a `logger.exception` in the worker and an unprompted notice (or a reply field the
  owner polls at its next edge; not a timer). Also stop the cadence: request a park without waiting, since `park()`
  from inside the step would wait out its own timeout. Then 5.2 never ships a silent freeze, even behind its admission.

### Low

- **A6-L1. Unpark can burst the whole parked gap (a narrow race with no cap).** `RecordedCaptureBackend.start` installs
  `_callback` before calling `on_started` (`recorded_capture.py:105-108`). `unpark_logical_side` unparks the cadence
  right after re-acquiring the engine, while capture reopens on its own lane. A first unparked step that lands between
  those two statements sees `is_running()` True and `_rebase` still False, so `due` hands over `elapsed = now - _last`
  where `_last` is the last pre-park edge. Probe (a): a 60 s park gave 2,812 blocks (59.99 s) in one edge. `due` has no
  upper bound: an overnight park would allocate gigabytes on the cadence thread. The park test passes because the lane
  usually wins the race. Fix: call `on_started` before installing the callback (or have `rebase` take effect when
  `running` turns True), and cap the catch-up at a device's queue depth (a few blocks). Gate-rig code only, but it is
  the source every 5.x paced gate uses.
- **A6-L2. The paced source models an ideal device phase.** Blocks are delivered synchronously on the cadence thread
  just before each tick (`engine_worker.py:367-369`). So the tick always sees the freshest block, the capture callback
  never runs concurrently with the tick, and its cost is charged to the step. The live product has a device thread on
  its own 10 ms period, with jitter between device and tick and callback/tick lock interaction. The gate cannot see
  any of that. This is acceptable for 5.1 (5.3 brings the real device), but the record should say "phase-locked to the
  tick", not "as a device's queued callbacks".
- **A6-L3. "Deadline timestamp" is the wake time.** The runtime passes `now` (the `perf_counter` read before the
  step), not `next_deadline` (`logical_runtime.py:566, 584`). That is the better choice for an audio clock, since a late
  step really gets the late audio. But `PacedPcmSource`'s docstring, the module docstring and the 5.1 record all say
  "the step's deadline timestamp", which is wrong. Fix the wording.
- **A6-L4. The parity test's owner side is a hand copy of the host binding's composition.** `_OwnerHost.configure`
  (`test_visualizer_logical_edges_parity.py:173-187`) builds the `activation=` dict itself, binds through
  `bind_visualizer_render_source` instead of `owner.bind`, and runs `set_playing` then `start` by hand.
  `test_visualizer_host_binding.py:53` swallows the `configure` kwargs. No test checks that the binding passes
  `activation=` with its model, activation and cache. `configure_logical_controller`'s `activation=None` default
  ("keeps what the controller holds") would turn dropping it into a silent production regression: the controller keeps
  `settings_model=None` and an empty technical cache, while the parity test stays green. Also outside the comparison:
  the binding's real inputs. Production `presentation_kwargs` add `scene3d_detail` (`display_manager.py:2079`), while
  the session gets `offline_activation_request`'s copy of the model values (`feature_replay.py:438`). The owner's
  `_start_logical_runtime` is stubbed and the session runs with `_paced=False` (`:159, :216`), so 5.1's
  `start_logical_cadence` placement (start and post-switch restart) is not compared either. Fix: make `activation`
  required on the owner's `configure`, and assert the binding passes it (record kwargs in the fake owner). Add a paced
  variant of the session host with a recording `start_logical_runtime`, and let the owner host record its real
  `_start_logical_runtime` through `start_logical_cadence`. For 5.2, the worker must receive the binding's
  `presentation_kwargs`, not an offline request.
- **A6-L5. No test compares production frames before and after 32f28d4f.** The identity gate
  (`test_visualizer_engine_worker.py:23`) compares the session, which uses `configure_logical_controller`, against
  `owner_replay`. `owner_replay` configures with `configure_offline_controller` (`expanded_visualizer_evidence.py:154`)
  and never calls `owner.configure`, so neither side is the product's configure-and-start path. "Frames unchanged" for
  the product rests on reading the code, not on a digest. The reading holds (see below), so this is a proof gap, not a
  regression. The `configure_offline_controller` docstring ("the frames it ticks equal the owner's") overstates what
  that test shows.
- **A6-L6. The paced gate's thresholds are loose, and its checks are partly implied by its setup.** The rate check
  accepts 54 Hz (`rate_hz >= 0.6 * authored_hz`, `live_engine_gate.py:343`), so a cadence regression to 60 Hz passes;
  the evidence shows 89.5-90.1. "Coalescing observed" (`taken < published`) is guaranteed by the reader's own 40 ms
  stall whenever the writer is not blocked, so it is the rate check restated. It does not show latest-wins (that each
  take got the newest slot). The park and switch tests do not assert the cadence rate after the event, and `steps`
  counts only the last runtime, so `published == steps` cannot hold after a switch.
- **A6-L7. `VIS_STOP` leaves the session open if `finish` raises.** `finish()` runs before `_close_session()` inside
  the generic try (`engine_worker.py:638-643`). An unjoined cadence ("did not join") replies with an error and keeps
  the session, with capture and the compute lane, until the next configure or worker cleanup. Fix: close in a
  `finally`.
- **A6-L8. The worker's park keeps the pre-park unread frame and its edges (a 5.2 obligation).** In process the
  owner's park clears its reader mailbox, so the unread frame and its protected edges are dropped
  (`park_logical_side(clear_reader=...)`). The session parks with no clear, by design ("the reader-side clear stays the
  main process's"). Until a reader acknowledges, the newest slot stays readable and the writer keeps re-carrying its
  edges, so after unpark the first slot carries pre-park Bubble edges. 5.2 must clear the reader after the
  `VIS_SET_DISPLAY_POWER(off)` reply (after the worker's last pre-park publish), never before it, or a frame published
  in between survives. The 5.1 park test reads none of this.

### Deferred items (question 4)

- **Wake-pipe backpressure: safe until 5.5.** `send_bytes` runs outside the mailbox lock (`packet_mailbox.py:133-137,
  155-158`), and the reader's listener is its own daemon thread that only runs the wake callback. A stalled GUI does
  not stop it draining. The pipe fills only if the main process is suspended or the callback blocks. Condition for 5.2:
  the owner's wake callback must not block (a queued signal, never a blocking cross-thread call), and 5.2 should test
  that a stalled GUI thread leaves the listener draining. If it does block, the cadence thread stalls inside a step:
  park (2 s timeout) logs and proceeds, and `VIS_STOP` fails to join (A6-L7).
- **The failed session stepping no-ops at 90 Hz: not safe to leave unaddressed into 5.2** (A6-M3). The wake cost is
  minor. The problem is the silent, permanent freeze and the divergence from in-process retry.

### Question 5 (writer-side clear)

No protected edge is lost that in-process would deliver. The writer clear runs only from `stop_logical_runtime` and
`reset_logical_handoff` (`runtime_controller.py:755, 824, 836, 843`). In process those same calls drop the unread
publication, and its edges with it. In the worker the newest slot stays readable with its own mask, so the worker
delivers at least what in-process does. The only edges carried are Bubble's drift and spawn edges and the capture
edge (`bubble_frame_runtime.py:405`, `logical_frame_capture.py:982`); reveal and teardown are not protected edges. The
one asymmetry is park (A6-L8), and it goes the other way: the worker keeps edges in-process drops.

### Verified sound

- **32f28d4f changes no in-process behaviour.**
  - `park_logical_side` / `unpark_logical_side` make the same calls in the same order: park, error log, reader clear,
    release; resume, then unpark. The flags are set under the same conditions. The error log now comes from the
    `logical_edges` logger, with the same text.
  - `release_engine_started_parked` keeps the old condition, and the flags are set even when `release` is not
    callable, as before.
  - `start_logical_cadence` is the old `_start_logical_runtime` body: the same import warm, the same interval formula,
    and a step bound to the state at start time.
  - `configure` now records the activation's inputs inside the owner, after the binding has evaluated its arguments.
    None of those arguments read the controller (`display_manager.py:2071-2079`).
  - The technical cache is now `dict(...)` rather than the same object. The binding never mutates it afterwards, and
    `technical_config` is passed explicitly.
  - The `activate_committed_profile` label is back after `discard_pending` (`quick_display_visualizer_owner.py:1433-1434`),
    as before the shared module.
  - The activation path still configures through `_apply_configuration`.
- **The cadence owner is shared, not copied.** Both hosts start `VisualizerLogicalRuntime` through
  `start_logical_cadence`. Only the step differs: the session's adds the audio due and its own failure capture
  (A6-M3).
- **`PacedPcmSource` has no thread, timer or poll.** It runs only inside the runtime's step. Late steps do get several
  blocks (the evidence shows `most_blocks_per_edge` of 2-10). Nothing is delivered while capture is closed or Media is
  paused, and the playhead holds. A warm-capture resume gets one interval.
- **The cross-process run is genuine.** The gate's reader is in another process (`WorkerType.VISUALIZER`), wakes on
  the pipe and stalls on its own thread. `perf_counter` (QPC) is system-wide, so comparing the elapsed time with the
  paced seconds is valid. Reproduced: 2 modes OK.
- **The writer-side clear** matches in-process (question 5).

### Not verified

- Whether A6-M2's half-applied paced switch can arise from the shipped modes: the probe did not inject a switch
  failure.
- How often A6-L1's race fires in real runs; shown only by forcing the interleaving.
- The 9-mode paced worker test and the whole gate (only 2 modes, 2 s, were run); the wider owner focused files.
- The Windows pipe buffer capacity behind the backpressure estimate.

## Checkpoint audit 7 (8 Nov): the owner on the worker (5.2)

Scope: e948c937, c92722f7, fabd7c2c, f16ae4f6, 0ea1c2b3, f5d01ea8, 772a9a6e (work order 5 slice 5.2 and 5.3's core:
the production owner on the engine worker behind `--viz-engine-worker`, default off). Read: the diffs; the 5.2 record
and what is left (design doc); `quick_display_visualizer_owner.py` (worker path, recovery, the in-process commit for
comparison), `engine_worker_link.py`, `visualizer_host_binding.py`, `runtime_controller.py` (layout-metrics observer),
`engine_worker.py` (production session, device check, `VIS_SET_VIEW`), `packet_mailbox.py`, `supervisor.py`
(`_is_worker_enabled`, `await_response`), `frame_codec.py`, the captures that read presentation state
(`sphere_capture.py`, `waveform_ribbon_capture.py`, `config_applier.py`, `logical_frame_capture.py`),
`edit_content_envelope.py`, the tests, `owner_worker_gate.py` and its evidence JSON. Ran: the owner-worker and
frame-codec test files without the two 9-mode parametrised gates (27 passed, 27 s). Probes (in
`D:\Temp\Scratch\SRPSS\native_audit7`, deleted): (a) import the owner, binding and runtime controller and list
worker modules in `sys.modules`; (b) a real `WorkerType.VISUALIZER` worker killed 0.5 s into an `await_response` on
an unanswered correlation id.

### Medium

**A7-M1. The reflected wallpaper never reaches the worker. Sphere's Mirror Cubes and Extruded Spectrum's face
mirror lose their reflection with the flag on. This is not in the 5.4 inventory, and the gate cannot see it.**
- Claim: 5.2 record, "the main side configures only presentation"; 5.4's list of view inputs to forward (Edit orbit,
  Waveform view, Expanded, Sphere parameters).
- Evidence: the owner makes the backdrop on the main controller's presentation state only
  (`quick_display_visualizer_owner.py:376-406`). The logical capture, which runs in the tick (on the worker), puts the
  worker's own `pres._backdrop` into the frame: `sphere_capture.py:15-27`, `config_applier.py:327-328` via
  `logical_frame_capture.py:319`. Nothing sends an image to the session, and the codec has no backdrop type
  (`frame_codec.py` `_TYPES`). The modes that reflect are `visualizer_mode_registry.py:316` (Sphere, `sphere_mirror`)
  and `:363` (Extruded Spectrum, `extruded_spectrum_face_mirror`). The gate's host has no photograph
  (`owner_production_replay._Host`), so `_backdrop` is None on both sides and the identity gate is blind to it.
- Failure scenario: with a mirror setting above zero on a reflections tier, the worker path draws Sphere and Extruded
  Spectrum with no wallpaper in the reflection, and the crossfade to each new photograph is lost. The identity gate
  stays green.
- Fix: add the backdrop to 5.4's inventory. Either move the backdrop into presentation (the renderer reads it from
  the presentation record, not the logical frame), or pass it by reference (photo identity plus a shared-memory
  image), never through the frame codec. Gate it with a rig host that has a photograph and a reflecting preset.

**A7-M2. With the flag on, the user sees a 3D view that ignores Edit orbit and auto-rotate on a preset, and broken
Fullscreen Edit envelopes. These are the documented 5.4 items, and some of the envelope breakage is wider than
recorded.**
- Evidence: the captures evaluate the view orbit against the worker's presentation state. Sphere's turn and tilt come
  from `sphere_capture.py:18-19`. Extruded Spectrum, Extruded Bubble and Neon Lake use `apply_view_orbit_motion` in
  `config_applier.py`. Waveform Ribbon's camera, `zoom_hold` and `view_span` come from `waveform_ribbon_capture.py:52-60`.
  The owner arms auto-rotate and rebases orbit motion on the main presentation state only
  (`quick_display_visualizer_owner.py:1838-1841`). Fullscreen Edit's Sphere envelope reads the main tick state's
  `_sphere_parameters` (`edit_content_envelope.py:394`), which never exists on the worker path, so it returns None.
  Not recorded: Extruded Spectrum's envelope reads `controller.bar_count` (`edit_content_envelope.py:384`), and the
  worker path never updates the main controller's `bar_count` after the first configure. A mode switch's technical
  config changes it only in the session.
- Failure scenario: in Edit, dragging or key-orbiting a 3D mode does not move the drawn pose (the frame carries the
  worker's pose). A preset's immediate auto-rotate arms on the wrong state. Waveform Ribbon's zoom hold under an
  operated camera does not engage. The Sphere and Extruded Spectrum Fullscreen Edit envelopes are missing or sized
  for the wrong bar count.
- Fix (5.4): forward the presentation-owned view state as `VIS_SET_VIEW` does the layout metrics (latest wins), or
  move pose evaluation out of the logical capture into presentation. Keep the main controller's `bar_count` (or have
  the envelope read the frame's `common.bar_count`). Add an identity-gate variant that orbits during the run.

**A7-M3. The recovery has no bound. "Fade, never vanish" holds only while the replacement publishes.**
- Claim: 5.2 record, "holds the last presented frame, fades it out ... paced by the replacement's own publications";
  left for 5.5: "a fade with no replacement frames to pace it (the held frame stays, frozen)".
- Evidence:
  - No deadline is armed for `recovering`. Only `_request_visualizer_activation` arms one
    (`quick_display_visualizer_owner.py:1442`). `_sync_recovery` returns at once when nothing is published (`:2007-2009`).
  - The reveal after recovery (`_bind_replacement(reveal=True)`) enters `waiting_target` with no deadline either.
    Mode and preset requests are refused while the phase is not idle (`:1426`).
  - `_fall_back_in_process` (`:1910-1963`) is not guarded. An exception from `configure_logical_controller`, the start
    or the park escapes from `_worker_edge`'s except clause into whoever called the edge: Media's `set_playing`,
    `set_display_power`, or the queued `_SessionEnd` slot. The owner is then left with no worker, an empty fresh
    `LatestStateMailbox`, the phase unchanged, and no recovery begun.
  - A deadline already armed by a crossfade in flight (6 s, same serial) can fire while the phase is `recovering` or
    in the recovery's `waiting_target`. It then signals `deadline:recovering` and a full reconstruction. Not exercised
    by any test.
- Failure scenario:
  - (i) The worker reconfigures but its device never delivers and the session is parked or stalled, so nothing paces
    the fade. The last frame stays frozen at full opacity indefinitely, and Settings cannot switch mode or preset.
  - (ii) The second failure falls back in process with a dead device. The fade completes on idle publications, then
    `waiting_target` waits for a fresh engine frame that never comes. The Visualizer stays hidden for good and is
    never reconstructed. It faded rather than vanished, but it is gone permanently with no bounded recovery, which is
    worse than in process, where the activation deadline reconstructs.
  - (iii) The fallback raises: the frame freezes and the exception lands in Media's handler.
- Fix: arm the generation-fenced transaction deadline (`ThreadManager.single_shot`, the existing pattern) at
  `_begin_worker_recovery` and at `_bind_replacement(reveal=True)`. On expiry, fade the held frame out by the
  transition clock and signal `_signal_transition_failure("deadline:recovering")`. Wrap the fallback in try/except
  and route a failure to `_signal_transition_failure`. Bump `_transition_request_serial` when a recovery begins, so a
  stale crossfade deadline cannot fire into it. Add tests: a replacement that never publishes, a fallback that raises,
  and a failure during `waiting_target`.

**A7-M4. Every control edge blocks the GUI thread. A hung worker freezes the GUI for tens of seconds, and a chain of
failures for minutes. Acceptable only while the flag is off by default.**
- Evidence:
  - The bounds are `CONFIGURE_TIMEOUT_MS = 60_000`, `EDGE_TIMEOUT_MS = 30_000` and `STOP_TIMEOUT_MS = 10_000`
    (`engine_worker_link.py:49-53`). `await_response` sleeps on a condition (`supervisor.py:670-682`).
  - The first build also waits for the spawn and its ready signal (`WORKER_READY_TIMEOUT_S = 10`, `supervisor.py:68`).
  - Probe (b): a worker killed mid-wait releases the waiter at the supervisor's next health pass (killed at 0.5 s,
    `await_response` returned None at 3.05 s). So a death costs about 3 s, not the full timeout.
  - A worker that is alive but not answering holds the GUI until the edge timeout, or until the heartbeat restart
    (5 missed at 3 s each, so 15 s or more; inferred, not measured).
  - Failure chain: the edge (30 s), stop (2 s), reconfigure (spawn up to 10 s plus configure up to 60 s), then
    `set_view`, display power and start (30 s each), stop (2 s). That is 2-3 minutes in the worst case. Retirement
    adds `link.stop()` (10 s).
  - `VIS_SET_VIEW` is sent synchronously whenever the layout metrics change, which during a CUSTOM edge drag means
    one round trip per pointer event (`set_custom_viewport_override` -> observer -> `_forward_view`, `:1730-1747`).
- Assessment: acceptable behind the off-by-default code-level admission. It must not become the default until 5.5
  lands.
- 5.5 must:
  - Make edges asynchronous: send and continue, with the reply delivered through a queued signal. Playing, view and
    display power should be latest-wins state edges that are never awaited.
  - Detect a dead worker from the process sentinel or the wake pipe's end, not from a reply timeout.
  - Never block the GUI on configure or reconfigure: keep the card hidden or holding while the session builds.
  - Use sub-second bounds for any wait that remains.
  - Gate the GUI hitch per edge, including the first build and a recovery, with a hung-worker and a killed-worker
    test.

### Low

- **A7-L1. A failed worker-path mode commit pops the outgoing frame back to full opacity.** The failure branch sets
  `_mode_transition_fade = 1.0` (`quick_display_visualizer_owner.py:1829`) before calling `_on_engine_worker_failed`
  (`:1831`). That function's `_hold_for_recovery` records `fade_from` from that field (`:1908`), so the outgoing frame,
  already faded to 0 by the completed fade-out, is re-presented at 1.0 and then fades out again: a visible flash.
  Fix: take the hold before resetting the fade, or hold at the fade actually drawn (0, so the recovery goes straight
  to the hidden reveal).
- **A7-L2. A failure re-entered during a reconfigure can bind the dead session's identity.**
  `_adopt_engine_worker_session` ends in `_forward_view` (`:1728`). If the replacement's `VIS_SET_VIEW` fails, a
  nested `_on_engine_worker_failed` counts the second failure and falls back in process, binding the in-process
  identity. The outer frame (`:1891-1896`) then continues. When the owner is not started, `_begin_worker_recovery`
  receives the dead replacement's `identity`: it either overwrites `recovery["identity"]` (`:1973-1975`) or rebinds at
  once, so the in-process frames fail render admission and the card stays hidden. The window is narrow (a failure
  before `start`). Fix: after the adopt, `if self._worker is not replacement: return` (and likewise after each edge).
- **A7-L3. A failure while parked re-presents a pre-park frame at unpark.** The held frame is the last one taken
  before the park. The replacement is parked (`:1892`) and publishes nothing until unpark, and the first publication
  after that paces a re-presentation of the hours-old held frame from `fade_from`. This weakens A6-L8 (it fades, but
  it is shown). Fix: when the displays are off, drop the held frame and bind the replacement hidden.
- **A7-L4. A capture device that fails to open counts as a worker failure.** Two such failures (each a visible fade
  cycle) disable the worker for the run (`engine_worker.py:302-327`, then `disable_worker_for_run`). The in-process
  fallback opens the same device. A transient unavailability, such as the endpoint not ready at startup, ends the
  worker for the run. Fix (5.3/5.5): report a capture failure as its own state that keeps the session, and retry on a
  device change or resume rather than counting it towards disabling the run.
- **A7-L5. Diagnostics on the worker path.** `set_playing` skips the `VIS_PLAYBACK_EDGE` T1/T2 records (`:494-500`).
  `_set_display_power_on_worker` logs "parked" or "resumed" even when the edge failed (`:1764-1769`). Fold into 5.7.
- **A7-L6. The paused-switch reveal predicate is substituted but not proven.** On the worker, `waiting_target` uses
  `present_frame` on a current-identity frame (`:1771-1782`). In process it uses the tick's
  `_waiting_for_fresh_engine_frame`, a different predicate. The identity script switches only while playing
  (`owner_worker_gate.py:75-93`), so the paused case (a non-Spectrum target revealing paused idle) is unproven: it
  could reveal earlier or later than in process. Fix: add a paused switch to the identity script.
- **A7-L7. The flaky-test fix has no established root cause.** 772a9a6e widens the wait from 1 s to a bound of 15 s
  with `until`. A multi-second presentation stall of the wake path would now pass. The other evidence shows no
  starvation: the realtime run presented 62-66 of 280-283 against a 40 ms stall, about the 1/(40 ms + sync) ceiling,
  and the no-stall cost run presented 269-271 of 271-279. So suite backlog is the likely cause. Fix: record the time
  from the first publication to 30 presentations, assert it is below about 1 s, and print it on failure.
- **A7-L8. The cost table compares relocation, not saving.**
  - Only the main process is counted. `worker_pid` is recorded, but the worker's CPU (tick, DSP, encode) is not
    reported, so "saves .6-3.7 ms" is work moved to another process, not removed.
  - Process and thread CPU on Windows are quantised at 15.625 ms. Every `main_cpu_s` is an exact multiple (0.625 =
    40, 0.25 = 16, 0.2031 = 13 quanta). Over about 275 steps that is about ±0.06 ms per step per active thread, so the
    worker-side values (0.67-1.23 ms) carry roughly ±10-20%, from one 3 s run per mode.
  - The work differs: in process the run counts the paced feeder, the capture callbacks, DSP, the tick and
    presentation. On the worker it counts presentation and the wake listener only. The in-process cadence also ran at
    88.75-89.25 Hz against 90.0-90.3 Hz on the worker.
  - The rise in `sync_present` is not pure decode. Each worker-path presentation also takes `layout_metrics_snapshot`
    (lock plus dict copies) in `sync_present`'s `finally`, and in `waiting_target` a `peek()` decode precedes the
    `take()` decode.
  - Fix for gate 3: system-wide CPU (both processes), three or more repeats with spread, and a profile split of
    `sync_present` (decode, snapshot, commit).
  - The Vulkan core's zero-Python read would remove the decode part only.

### Identity gate (question 5)

The reference is the same real owner, built by the binding's `construct`, on the live `_SpotifyBeatEngine` with the
same recorded PCM. The worker side crosses a process boundary and the codec, so equality is not by construction. Its
in-process side is not the owner's own cadence: the rig steps the owner's installed step in the session's production
order, re-implemented in the tool (`owner_worker_gate.py:319-334`). It uses engine seams that production leaves None
(`beat_engine.py:139-140`). Both sides also seed the RNG and the namespace counter alike (documented, 5.6). That is
the right comparison for a deterministic gate, but it proves code-path identity under the session's order, not
equality with the in-process app's free-running timing. It only digests logical frames, so presentation-state inputs
are outside it (A7-M1, A7-M2). The flaky-test fix hides no starvation the evidence shows (A7-L7).

### Verified sound

- **Admission off means production is unchanged.**
  - Probe (a): importing the owner, binding and runtime controller loads none of `engine_worker_link`,
    `engine_worker`, `packet_mailbox` or `frame_codec`. So the codec change cannot affect the off path.
  - The off-path additions are: `self._worker is not None` checks; `engine_identity()`, which makes the same two engine
    reads the binding made; `_layout_metrics_written` (one attribute read, observer None); the `recovering` branch,
    unreachable off; and a try/finally flag in `sync_present`, set only on the worker. The admission read is one
    import per construction.
  - The supervisor's `VISUALIZER` enable bypass matters only when a factory is registered, which only the link does.
- **Media stays the one owner of "playing".** The main controller's `playing` is set by Media's edge and forwarded
  once started (`:494-500`). `start` carries it, and the recovery's start and the fallback's `apply_playback_edge` carry
  the current value.
- The layout metrics are written only on the GUI thread. The render-thread admission does not commit metrics, so
  the observer's blocking `VIS_SET_VIEW` never runs on the render thread.
- The park reader clear follows the reply (test with negative controls). The label namespace counter is one
  process-wide counter. The main side's wake sender is closed after configure.
- The device check is fenced behind the capture lane's drain loop, so an open still in flight is not misreported as a
  failure.
- `RibbonStrays` was appended at the end of the codec's type table and round-trips (test).

### Not verified

- The two 9-mode parametrised gates (identity and realtime) and the full gate tool; the evidence JSON was read, not
  reproduced.
- How long a hung-but-alive worker blocks the GUI (heartbeat restart timing), and whether the restart releases a
  waiter as a death does.
- The render thread's sync-time take and decode cost with a window; physical device behaviour; device changes.
- Whether an armed crossfade deadline actually fires into a recovery in practice (A7-M3), and the paused-switch
  predicate (A7-L6).

## Checkpoint audit 8 (8 Nov): asynchronous edges and inputs (5.5, 5.4)

Scope: fe9e2487 (5.5: asynchronous control edges, bounded recovery, A7 lows) and 4df640b7 (5.4: presentation inputs on
`VIS_SET_VIEW`, wallpaper frame completion, Sphere envelope fallback, Qt-free colours), behind `--viz-engine-worker`
(default off). Read: both diffs; the 5.4 and 5.5 records and what is left (design doc); audit 7; the current
`engine_worker_link.py`, the owner's worker path and recovery, `logical_edges.py` (presentation inputs),
`backdrop.py`, `config_applier.py`, `edit_content_envelope.py`, `packet_mailbox.py`, the supervisor's
start/stop/restart, heartbeat and response-callback code, `view_orbit.py`, `screensaver_engine._on_settings_changed`
and the display manager's activation edges; the three test files; the evidence directory
`20261108_p2b_55_gui_stall/`. Ran (foreground): `test_visualizer_owner_engine_worker_inputs.py` (12 passed, 44 s);
`test_visualizer_owner_engine_worker_liveness.py`, `test_visualizer_owner_production_path.py` and
`test_qtquick_visualizer_owner_contract.py` (31 passed, 91 s). Probes (in `D:\Temp\Scratch\SRPSS\native_audit8`,
deleted; in-process stand-in supervisor, recorded PCM, no device, no window): (a) recording every recovery-deadline
arm; (b) timing `complete_frame_backdrop` and `presentation_inputs_snapshot` per frame with a reflecting photograph;
(c) the snapshot's value types and worker-vs-main parity for all nine modes; (d) the runtime-written view keys
(Home pose, framed lens, scene transform, orbit, Auto Rotate) against `presentation_input_attrs`.

### Medium

**A8-M1. The recovery's reveal is not given its own deadline. The shot armed at the failure stays live, so a slow
replacement is abandoned and the worker is turned off for the run even when the replacement is healthy.**
- Claim: 5.5 record, "arms the transaction deadline's one-shot ... again at its reveal"; the code comment says "the
  reveal is bounded too" (`quick_display_visualizer_owner.py:2188`).
- Evidence: `_begin_worker_recovery` bumps the request serial and arms (`:2178-2180`). `_finish_worker_recovery`
  arms again (`:2188`) without bumping it, so both shots carry the same serial and the first one is not fenced.
  Probe (a), a session closed behind the owner's back: `arms = [(6000, serial 1, 'recovering', stage 1),
  (6000, serial 1, 'waiting_target', stage 1)]`, final serial 1. `_on_recovery_deadline` (`:2265-2283`) takes the
  first expiry in `waiting_target` at stage 1 with a live worker as "the replacement did not come back" and calls
  `_fall_back_in_process(...)`, which counts for the run.
- Failure scenario: the failure is detected at t0. The replacement's spawn, session build and paced fade-out finish
  at t0 + 5 s. The evidence measured `build_with_spawn_ms` 3,988, and a prepared-reveal mode waits for its warm
  frames. Then the replacement has about 1 s to produce a presentable frame instead of 6 s. When the shot fires, a
  healthy replacement is retired, the activation falls back in process, and `worker_disabled_for_run` turns the
  engine worker off for every later owner.
- Fix: in `_finish_worker_recovery` (reveal branch), do `self._transition_request_serial += 1` before
  `_arm_recovery_deadline()`. Do the same at any other re-arm that is meant to start a new window. Test: drive the
  finish past half the deadline with a short `_ACTIVATION_TRANSACTION_DEADLINE_MS` and assert there is no fallback.
  For the negative control, use today's code.

**A8-M2. If the recovered Visualizer never reveals, it stays invisible for the rest of the session while its runtime
keeps running. In process, the same `waiting_target` expiry rebuilds.**
- Claim: 5.5 record, second expiry: "leaves the Visualizer faded out, logged, and requests admitted (it reappears
  with the next activation)".
- Evidence: `_on_recovery_deadline` (`:2284-2292`) sets the phase to `idle` with fade 0.0 and returns. The in-process
  activation runtime started by the stage-1 fallback keeps ticking and publishing. Each frame is presented at content
  fade 0. Nothing re-arms, and no retry is scheduled. In process, a `waiting_target` expiry goes to
  `_signal_transition_failure("deadline:" + phase)` (`:1210-1232`), which reconstructs the committed runtime. In a
  screensaver session the "next activation" depends on the user. Nothing else causes one: `_on_settings_changed`
  (`screensaver_engine.py:2486`) has no Visualizer path, and the only activation edges are the display manager's mode
  and preset requests (`display_manager.py:1949`, `:2050`).
- Failure scenario: a capture or tick that never marks a frame presentable after the fallback, for example a
  reveal predicate that waits on source frames that never come. The card fades out and stays gone until the saver
  exits. The engine, capture lane and tick run at full cadence the whole time with nothing visible. This is "fade"
  but not "never vanish", with no path back.
- Fix: escalate the stage-2 `waiting_target` expiry to the generation-fenced reconstruction, as in process (or at
  least stop or park the invisible runtime). If invisible-until-next-activation really is the wanted terminal state,
  record it as an operator decision and stop the runtime.

### Low

**A8-L1. With a wallpaper, the frame completion re-freezes every reflecting frame's whole parameter map on the render
thread. It never takes the "nothing differs" early-out.**
- Evidence: the worker's frames always carry `backdrop` None, because the worker never has a wallpaper. So the
  identity check in `backdrop.py:70-86` always differs once the owner holds one, and `freeze_render_fields` over all
  the parameters plus two `dataclasses.replace` calls run on every decode (`:91-92`). Only the wallpaper's own freeze
  is cached. Probe (b): Sphere median 117 us, max 309 us (137 frames); Extruded Spectrum median 78 us, max 128 us. The
  decode happens at sync admission, where the GUI thread is blocked in Qt Quick's threaded loop. The 5.4 record gives
  the snapshot's cost but not this one, and says frames without a wallpaper do no work, which is true but not the
  common case for these modes. The module-global `_FROZEN_WALLPAPER` (`:95`) also keeps the last wallpaper alive after
  the owner retires.
- Fix: cache the completed `FrozenFields` keyed by the identity of the parameters object plus the wallpaper and
  blend, or have the worker carry a sentinel the main side swaps in without re-freezing. Keep the cache per owner,
  cleared on retire.

**A8-L2. After a preset activation, Auto Rotate is armed twice, at two times, and the main side's later record
replaces the worker's.**
- Evidence: the worker's `commit_logical_activation(kind="preset")` arms on its own state at `view_now`
  (`logical_edges.py:320-322`). The main side arms again at the reply event, at `now` (`:1946`), and forwards it
  because the record differs from the last one sent. `AutoRotate` turns from its start time, so at the swap the turn
  steps back by `speed × (reply latency + GUI queue delay)`. The view gate pins the clock
  (`identity_script_view`), so it cannot see this.
- Failure scenario: a small backward hitch in the swivel during the preset's fade-in. It is larger when the GUI
  thread is busy at the reply.
- Fix: arm on one side only. Either the main side arms and forwards with the commit (and the worker skips it on
  `VIS_SET_MODE`), or the commit reply carries the worker's record and the main side adopts it instead of re-arming.

**A8-L3. The park reply clears the reader even when the displays are already back on.**
- Evidence: `_set_display_power_on_worker.applied` (`:1835-1841`) checks only `_link is self._worker` before
  `controller.logical_mailbox.clear()`. Replies are in order, but the GUI can send OFF then ON before it processes the
  OFF reply. By then the worker may already have published post-unpark frames.
- Failure scenario: a fresh post-unpark frame is dropped (one tick late). If that frame was the target's first
  presentable frame, the reveal is a tick late. "Parked" is logged after the display is already on.
- Fix: in `applied`, also require `not self._display_power_on` (or a park sequence number matching the newest edge).

**A8-L4. Replies are keyed by link token, not by correlation. After a resend, a late event for the abandoned
correlation would complete the new one.**
- Evidence: `replied` emits `(token, response)` (`engine_worker_link.py:341-342`). `_respawn_unconfigured`
  (`:296-311`) keeps the tokens and re-dispatches them with new correlations, and `_deliver_reply` (`:354`) looks
  only at the token. Today the old correlations' cancellations are emitted before the spawn's event, so they find no
  pending entry. That ordering is a timing argument, not a guarantee: an `_invoke_response_callback` already running
  on the listener when `abandon_response` runs would still emit.
- Fix: carry the correlation in the event and drop it when it no longer matches the pending entry's.

**A8-L5. The first configure has no deadline of its own.**
- Evidence: `bind` defers render admission until the configure's reply, and `sync_present` presents nothing
  meanwhile. Only a recovery arms `_on_recovery_deadline`. A configure that hangs inside the worker (a device open, a
  stuck build) is ended only by the heartbeat: about 17 s measured, twice because of the one resend, before the
  in-process fallback. A spawn task waiting behind a busy IO pool is not bounded at all.
- Failure scenario: on a stall, the Visualizer first appears roughly 35-45 s late. It does not vanish, because it
  was never shown.
- Fix: arm the same one-shot from the first configure (fall back in process, not counted for the run, on expiry).

**A8-L6. The presentation-input diff compares by reference for nested mutables.**
- Evidence: `presentation_inputs_snapshot` copies only top-level lists (`logical_edges.py:590`). Probe (c) found
  `_waveform_ribbon_palette` is a `dict` held by reference in `_presentation_sent`, and lists of lists are copied
  shallowly. An in-place mutation on the main side would compare equal to "sent" and never be forwarded. No writer
  mutates in place today (every write goes through `apply_presentation_vis_mode_kwargs`, which replaces the value),
  so this is latent.
- Fix: deep-copy or freeze the snapshot's values (`freeze_render_value`), or assert that the values are immutable in
  the snapshot.

**A8-L7. Records overstate a few things.**
- The commit message's "GUI worst stall ... first configure 1.78 s -> 86 ms" is not the worst stall after the
  change. The configure's reply handler costs 161-209 ms on the GUI thread (the render-source bind; evidence
  `configured_reply` 161 ms). The design record says this, but the summary and the gate do not: the one-frame gate
  covers the edges only, not the reply handlers.
- "Again at its reveal" (A8-M1).
- "Recovered on a fresh worker" after a hung worker is shown only with a 0.25 s test heartbeat. In the evidence probe
  at production heartbeat, the hung case was the probe's second failure (after the kill scenario), so
  `after_hung.on_worker` is false. Recovery to a fresh worker after a production-timed hang (about 17 s detection,
  then a restart that races the link's own spawn) is unmeasured.

### Verified sound

- **With admission off, production is unchanged.**
  - The colours are now `(r, g, b, a)` tuples. Their only reader is `logical_frame_capture._common_style`
    (`logical_frame_capture.py:837`), which puts them into the frame's style, and the frame freezes a `QColor` to the
    same tuple. Search across `*.py`/`*.qml`: no renderer, QML binding, Studio adapter (they use offline
    controllers and frames), Settings preview or Edit route reads `_bar_fill_color` / `_bar_border_color`. The
    production-path frame test and the owner contract test pass.
  - `_color_or_none` now refuses out-of-range or over-long values, which validated settings never produce.
  - `complete_frame_backdrop` and `presentation_inputs_snapshot` are wired only in `_adopt_engine_worker_session`
    (worker path).
  - The Sphere envelope fallback reads `logical_mailbox.last_taken`. Only `PacketMailbox` has that attribute;
    `LatestStateMailbox` does not, so in process `getattr` gives None and the behaviour is unchanged.
  - `_forward_view` runs only when `on_worker`. `engine_identity`, `bind`, `admit_latest_at_sync` and
    `set_display_power` add only `_worker` / `_recovery_stage` checks.
  - `_fade_out_from` is 1.0 in process: requests are admitted only from `idle`, and every in-process path to `idle`
    leaves fade 1.0.
- **"No logical settings delta" is correct.** In process there is no per-slider runtime path. `_on_settings_changed`
  handles only interval, display mode, shuffle and sources. A running Visualizer changes only through mode and preset
  activations or a rebuild, and the worker path matches with `VIS_SET_MODE`.
- **The forwarded set covers what changes at runtime.**
  - Probe (d): for all nine modes, every runtime-written key is in `presentation_input_attrs`: the Home pose and
    framed lens, scene transform, orbit and Auto Rotate keys, the view records and the tier.
  - The captures read the view records only (`apply_view_orbit_motion` is read-only), so the worker never diverges
    by writing them.
  - Probe (c): after the settle, the worker's and main's forwarded attributes are equal in all nine modes. No Qt
    values are skipped.
  - `apply_presentation_inputs` refuses anything outside the union.
  - The tick publishes every step (`tick_pipeline.py:1474-1497`), so forwarding at each presentation's end never
    starves.
- **Delivery is on the GUI thread.**
  - Every cross-thread delivery (reply, cancel, not-sent, pipe end, spawn, view flush) is a `QueuedConnection` signal
    on a `QObject` created on the GUI thread. That includes a buffered reply that `register_response_callback`
    invokes synchronously on the caller.
  - Events are disarmed and dropped on close. The owner fences every callback by link and commit identity.
  - A stop is addressed to its mapping. The old link's queued edges precede its stop and the new configure on the
    one request queue.
  - A resend goes to fresh queues, so it does not duplicate a session.
- **The ThreadManager spawn.**
  - `submit_task` raises after shutdown, so the configure fails and falls back.
  - `supervisor.start` is serialised per role and retires a child started during shutdown.
  - A link retired mid-spawn leaves an idle worker, owned by the supervisor until shutdown (already recorded for 5.7),
    not an orphan.
- **The recovery's fences.** The deadline is a one-shot and never polled, fenced by the serial and display power.
  The unpark re-arms it. The fallback is contained. A park during recovery drops the hold.

### Not verified

- The two 9-mode gates' realtime variant and the full gate tool; the evidence JSON was read, not reproduced.
- Recovery onto a fresh worker after a hang at production heartbeat timing (A8-L7). The heartbeat restart racing the
  link's own `stop` + `start` in the IO task (the record notes it; not exercised here).
- The render-thread decode and completion cost with a real window (probe (b) is an unshown rig).
- `send_wake_byte_without_blocking`'s Windows cancel race (a byte written and still counted as dropped). Harmless by
  reading, not tested.

### Audit 8 resolution (8 Nov)

Each fix has a regression test with its negative control (a pre-fix variant inside the test, and the test's fixed
variant failing with the source change reverted). Liveness tests: `tests/test_visualizer_owner_engine_worker_liveness.py`;
input tests: `tests/test_visualizer_owner_engine_worker_inputs.py`.

- **A8-M1** fixed by 4f77e5bf: `_finish_worker_recovery` moves the request serial on before re-arming, so the reveal
  has its own deadline and the failure's shot is inert. Test: `test_a_slow_but_healthy_replacement_gets_its_own_reveal_deadline`
  (pre-fix: the replacement is retired and the worker is off for the run).
- **A8-M2** fixed by 4f77e5bf: the second expiry in `waiting_target` escalates to the generation-fenced reconstruction,
  as an in-process activation's deadline does (the display's reload retires the owner and its hidden runtime; the
  rebuilt owner fades in). Test: `test_a_recovery_that_never_reveals_escalates_to_the_reconstruction_as_in_process`
  (pre-fix: idle at fade 0, invisible frames still published).
- **A8-L1** fixed by 873b8d0f: `backdrop.FrameBackdropCompletion` (per owner session) replaces the two entries only and
  rebuilds the frame without re-validation; the per-frame whole-map freeze and both frames' `__post_init__` are gone.
  Sphere 132 -> 17 us median, Extruded Spectrum 104 -> 15 us (stand-in rig, evidence
  `.artifacts/evidence/architecture/native_core_p2/20261108_audit8_l1_l6_timings/`). The module-level cache is gone; the
  owner releases the completion on retire and on the fallback. Test:
  `test_the_frame_completion_refreezes_nothing_per_frame_and_leaves_with_its_owner` (Sphere, Extruded Spectrum; reverted:
  one map frozen per frame).
- **A8-L2** fixed by 43ddcc58: the session's commit is the one arming owner; the `VIS_SET_MODE` reply carries its view
  records, the main side adopts them (a record the GUI replaced after the send is kept) and records them as sent.
  Test: `test_a_presets_auto_rotate_is_armed_once_by_the_session` (pre-fix: two armings, the session's record replaced).
- **A8-L3** fixed by 864e95c6: display-power edges are numbered; only the newest edge's reply clears the reader and
  logs. Test: `test_a_park_reply_that_lands_after_the_unpark_never_clears_the_reader` (pre-fix: a clear with the
  displays on).
- **A8-L4** fixed by 1d3ee5e5: the reply event carries its correlation and `_deliver_reply` drops one that no longer
  matches. Test: `test_a_late_reply_for_an_abandoned_correlation_never_answers_its_resend` (pre-fix: the stale answer
  configures the link, the real one is dropped).
- **A8-L5** fixed by 864e95c6: the first configure arms the recovery's one-shot (fenced by its label namespace);
  unanswered, the activation runs in process, not counted for the run. Test:
  `test_a_first_configure_that_is_never_answered_is_bounded` (unbounded: still on the worker, render binding deferred).
- **A8-L6** fixed by c2d7c262: the link compares the state's values with detached copies of what it sent
  (`logical_edges.detach_presentation_value`, applied to changed values only; the snapshot no longer copies lists per
  frame). Snapshot plus comparison 1.4-25.0 us -> 1.3-20.0 us median (Spline Curve to Neon Lake). Test:
  `test_an_in_place_edit_of_a_nested_presentation_input_is_forwarded` (by reference: never forwarded).
- **A8-L7** corrected in the design doc (5.5 record): the configure's reply handler (161-209 ms) is the worst GUI-thread
  call of a first activation on the worker, and the one-frame gate covers edges only; "again at its reveal" now holds
  (A8-M1); recovery onto a fresh worker after a hang is shown only at the test's 0.25 s heartbeat, the production-timed
  case is listed as unmeasured.

Focused runs after the fixes: the three engine-worker owner files 69 passed; the production path, the owner contract,
edge, retirement and logical-ownership suites, the logical-edges parity, engine-worker and packet-mailbox suites 92
passed. With `--viz-engine-worker` off nothing on these paths runs (all changes are on the worker path or its
link), and the production-path frame test is unchanged.

## Checkpoint audit 9 (8 Nov): audit 8 fixes and 5.6

Scope: 8584a653 (audit 8 fixes: A8-M1, A8-M2, A8-L1 to A8-L6) and 8f364264 (5.6: the snapshot layer deleted, Bubble's
own generator), read as `git diff 4df640b7..8f364264` (code hunks; doc hunks only to check claims). Read: the audit 8
section and its resolution, the 5.6 record and "Left for 5.6-5.7" (design doc), `Current_Plan.md`'s 5.6 side finding,
`TestSuite.md` and the change checklist's RNG lines; the current owner recovery and first-configure code, the link,
`backdrop.py`, `logical_edges.py`, `bubble_simulation.py`, `bubble_frame_runtime.py`, `runtime_controller.py`,
`engine_worker.py`, the Studio adapter and recorded-input extract, the replay tools, the reload handler
(`engine_handlers.on_custom_layout_reload_requested`) and the generation teardown. Ran (foreground):
`test_bubble_own_generator.py`, `test_bubble_reactivity.py`, `test_bubble_studio.py`, `test_bubble_viewport_reflow.py`
(138 passed, 18 s); `test_visualizer_owner_engine_worker_liveness.py`, `test_visualizer_owner_engine_worker_inputs.py`
(43 passed, 147 s); `engine_main_cost --help` (loads). Probes (`D:\Temp\Scratch\SRPSS\native_audit9`, deleted; no
window, no device): (a) the 4df640b7 `bubble_simulation.py` seeded through the process RNG against this one seeded
alike, 9 stream x 9 drift directions x the three pop modes, Group Drift on (off for drift "none"), bounce 50/50, 40
small and 8 big bubbles, 400 ticks with a periodic hot bass: 243 configurations, 0 divergent snapshots; (b) the Group
Drift alignment case over seeds 0-1999.

No high or medium findings.

### Low

**A9-L1. The first configure's deadline is fenced by the session's namespace and `_retired`, but not by the request
serial that `retire()` moves first. A retire whose logical join fails leaves the deadline live on a half-retired
owner.**
- Evidence: `_on_first_configure_deadline` (`quick_display_visualizer_owner.py:1756-1765`) checks `_retired`,
  `link.configured` and the namespace. `retire()` (`:2366`) bumps `_transition_request_serial` to disarm "any queued
  one-shot", then returns False before `_retired = True` when `stop_logical_runtime()` does not join (`:2393-2395`).
  The wake callback, sync admission and publication wake are already detached, and `_worker` and `_started` are still
  set. Every other owner deadline (`_on_transition_deadline`, `_on_recovery_deadline`) is fenced by that serial, so
  this is the only one that survives the early return. The generation teardown cancels the generation's single-shots
  (`engine_lifecycle.py:174-186`), so the deadline survives only a retire outside a generation teardown (Visualizer
  off, or an owner rebuilt within the same generation) whose join failed.
- Failure scenario: the configure is still unanswered when the retire's join fails. At 6 s the deadline runs
  `_fall_back_in_process`. That configures the controller and starts a logical runtime (`_started` is still True) on
  an owner whose routes were detached.
- Fix: also fence on the serial (pass `(namespace, self._transition_request_serial)` and compare both), or check a
  retiring flag that `retire()` sets first. Test: a retire whose join fails, with the configure unanswered. Advance
  past the deadline and assert no fallback or logical start. For the negative control, use today's fence.

**A9-L2. L5 turns every slow cold spawn into a link retired mid-spawn. That case was already recorded for 5.7, but
it now happens deterministically past 6 s.**
- Evidence: when the deadline fires while `_outbox is not None` (the spawn has not reported yet), `link.retire()`
  (`engine_worker_link.py:585`) sends no `VIS_STOP` because there is no session. `close()` disarms the events. The IO
  task still runs `supervisor.stop` + `supervisor.start` (`:280-288`) and leaves an idle worker process (audit 8
  verified-sound item, "owned by the supervisor until shutdown"). The IO pool has two workers
  (`core/threading/manager.py:633`). A later link's spawn could therefore run in parallel with this stale task, and the
  stale task's unconditional `supervisor.stop` could kill the later link's freshly started worker. That later link
  then pays its one resend (`_respawn_unconfigured`). This needs a new owner within the stale task's window, so it is
  rare. When the configure was dispatched (`_outbox is None`), the stray session is handled correctly: the stop is
  queued behind the configure, addressed to its mapping, and the late reply's correlation is abandoned and its events
  disarmed (`_on_worker_configured` also fences by link).
- Is 6 s safe? The measured spawn plus build is 0.5-4 s on the dev box (`build_with_spawn_ms` 3,988). Six seconds
  leaves 1.5x on that measured maximum. A frozen (Nuitka) cold boot with on-access scanning is unmeasured (5.7's
  operator check). Overrunning the deadline is graceful: this activation runs in process, it is not counted for the
  run, and the next owner retries the worker. So the bound is safe in outcome. Whether it is right in frequency is
  not known until the frozen spawn is timed.
- Fix (5.7): give the stale spawn task an identity. Skip `stop`/`start` when its link is closed, or have the
  supervisor's stop compare a start token. Time the frozen cold spawn against 6 s and record it.

**A9-L3. A8-M2 can now enter an unbounded 6 s reload cycle. That matches in-process behaviour, but neither record says
so.**
- Evidence: the second expiry goes to `_signal_transition_failure` (`:2352-2358`). Every path to it, except one,
  disables the worker for the run first: stage 1 with a live worker falls back counted (`:2343-2347`), and a recovery
  that began in a counted fallback (second failure, failed reconfigure) is disabled too. The one exception is
  `_on_worker_start_failed` (`:2066-2070`, `count_for_run=False`): it begins a bound recovery in process. If that
  in-process activation never reveals, the reconstruction's new owner tries the worker again, its start fails again,
  and so on, with one reload about every 6 s. The same loop already exists purely in process (`_on_transition_deadline`
  has no retry cap, and nor does `on_custom_layout_reload_requested`). So this is not worker-specific, and no worker
  failure loops on its own. Separately, the reload request is ignored while Settings owns runtime recreation, while a
  recreation is pending, or when the request is stale (`engine_handlers.py:785-800`). The owner then sits in `failed`
  at fade 0 with its runtime running, which is the A8-M2 state the new docstring (`:2337`) rules out ("Never left
  hidden with its runtime running").
- Fix: soften the docstring and the resolution line to "as in process". Record the uncapped reconstruction as a
  general follow-up, not a P2b item: a per-run reconstruction cap, or a `failed` owner that stops its logical runtime
  when its reload is refused.

**A9-L4. The seeded Group Drift case now pins one passing draw. It is a snapshot, not an invariant.**
- Evidence: probe (b): Random Group Drift on the x axis satisfies the case's assertion for 61.3% of seeds 0-1999, and
  Diagonal for 100%. That reproduces the record's ~61%. Seed 2 is one passing draw
  (`test_bubble_reactivity.py:1302`). The record and `Current_Plan.md` state this and leave the guarantee to Bubble's
  owner, so the seeding is honest. Still, the `[random-x]` case asserts nothing about Random drift that holds in
  production.
- Fix: as recorded. Decide what Random Group Drift guarantees and assert that. Until then, add a comment in the test
  saying the `random` case is a regression snapshot.

### Question 1 (Bubble, production behaviour)

- Every draw moved. No module-RNG draw is left in Bubble's code paths: a search of `widgets/spotify_visualizer` and
  `core/visualizer_engine` for `random.<draw>(` / `np.random` finds none. `bubble_ambient.py` and Extruded Bubble's
  wake/simulation use their own fixed-seed or runtime-seeded `random.Random`. 57 call sites are confirmed: 15 `rng.`
  in the spawn helpers and 42 `self._rng.`, against 57 module draws at 4df640b7. Probe (a): 243 configurations, every
  snapshot equal over 400 ticks, so no draw was added, dropped or reordered on those paths. The record's 144x720 run
  covers Group Drift off too.
- Production seeding: `random.Random(None)` seeds from `os.urandom` (not time), exactly like the module's own
  instance, so two simulations built in the same instant do not share a stream. Gates seed every state with the same
  value, which is intended. `BubbleFrameRuntime.reset` rebuilding with a stored seed restarts the stream only when a
  gate set one.
- Nothing else depended on Bubble consuming the module RNG. The remaining product draws from the module RNG (image
  selection, transitions' auxiliary picks, RSS shuffle, feed jitter, batch seed) are unseeded in production. Their
  distribution does not depend on how many draws Bubble interleaved. No tool or test pins a digest that depended on
  `deterministic_clock` seeding the process RNG: every Bubble replay tool goes through `driver._configure` =
  `configure_offline_controller(seed=REPLAY_SEED)`. `gc_gen2_attribution_harness.py` builds an unseeded
  `BubbleFrameRuntime`, but it is a profiler and needs no reproducibility. The Studio evaluator's seeding moved from
  `_reset_history` to `_start`. Every rewind path (`select`, extent change, seek back, signature change) goes through
  `_start`, so replays stay exact.

### Question 2 (deleted surface)

No caller remains. Searching `*.py` outside `.venv`/`release`/`.artifacts`/`logs` for `engine_snapshot`,
`EngineSnapshot`, `peek_pre_agc_analysis_spectrum`, `request_pre_agc_analysis_spectrum`, `reads_analysis_spectrum`,
`_ANALYSIS_SPECTRUM_READERS`, `tick_snapshot`, `initial_snapshot` and `inputs="snapshot"` finds only Docs. Tools,
tests, Studio and QML have none. `EngineSession.INPUTS` is `("feature", "lanes", "live")`, and an unknown input raises.
The worker's handlers catching `Exception` lose nothing, since `SnapshotContractError` was the only `BaseException`.

### Verified sound

- **A8-M1.** `_finish_worker_recovery` bumps the serial before re-arming (`:2253`). The failure's shot is inert. A
  stage-1 expiry that falls back and then finishes arms twice, and the first is fenced by the second bump (`:2349`).
  This is harmless.
- **A8-M2, the loop question.** No worker-specific loop exists (A9-L3 covers the general one). The worker is disabled
  before the reconstruction on every counted path. The `failed` phase presents nothing (`:1266-1269`), so the card
  stays faded at 0. It fades out and later fades in, and never vanishes.
- **A8-L1.** `FrameBackdropCompletion` builds frames equal to a full freeze. `FrozenFields` keeps sorted names, the
  two replaced entries keep their positions, and the values are `freeze_render_value` of the same inputs. No frame or
  mode-state `__post_init__` derives a field (they only normalise and validate), so `_with_field` copying the decoded
  fields is faithful. The release is reached on retire (`:2401`), on fallback (`:2156`) and on a replaced session
  (`:1801`). The one path that skips it, `_on_engine_worker_failed` returning in `failed` (`:2087-2088`), keeps the
  wallpaper only until that owner's retire.
- **A8-L2.** The view records are frozen dataclasses (`view_orbit.py:51-125`), so the identity test
  `current[attr] is before[attr]` reliably detects a GUI replacement. Both processes' clocks are `time.perf_counter`
  (QPC, system-wide), so the worker's arming time is valid on the main side. An unadopted (GUI-newer) record still
  differs from `_presentation_sent` and is forwarded.
- **A8-L3.** Only the newest edge's reply clears and logs. OFF, ON, OFF clears on the last reply. A reply from an
  older link is fenced by the link.
- **A8-L4.** Every emit carries its correlation, including the not-sent case and the spawn-error path (`""`
  registered and delivered alike). A respawned token's stale correlation finds a mismatching entry and is dropped.
- **A8-L5.** The deadline is generation-tagged (bound method). It is inert after an answer, a replacement link or a
  retire, except A9-L1. A late reply after the fallback is dropped: the link is closed and its events disarmed, and
  `_on_worker_configured` fences by link. A dispatched configure's session is stopped by the queued `VIS_STOP`.
- **A8-L6.** Only changed values are detached, and both the send and `sent` hold copies. The state's objects never
  cross into the (asynchronously pickling) send.
- **5.6 records.** "57 call sites", "Extruded Bubble seeded by its runtime, ambient and wake fixed-seed", "production
  never seeds" (`test_the_product_path_never_seeds`), the ~61% figure and the `engine_main_cost` half-deletion all
  check out.

### Records overstated

- The A8-M2 docstring and resolution say "never left hidden with its runtime running". That is true only when the
  reload is admitted (A9-L3).
- A8-L5 says "fenced by its label namespace". It is not fenced by the retire serial (A9-L1).
- `Visualizer_Change_Checklist.md:133`, "a process-RNG draw on the tick ... fails them": only the gates that compare
  two runs fail, and only when the draw reaches a frame. Single-run tests do not.

### Not verified

- A frozen (Nuitka) cold spawn against the 6 s first-configure bound (5.7, operator).
- The stale spawn task racing a later link's spawn on the two-worker IO pool (A9-L2). This is by reading, not
  exercised.
- The record's session-path digests and live gate (evidence JSON not reproduced). Probe (a) covers only the
  simulation.
- Behaviour of the first-configure timer across system sleep.

### Audit 9 resolution (8 Nov, with slice 5.7)

The checkpoint audit 9 section itself is on main (3d856690). Fixed in 5.7 (design doc, "5.7 record"); tests in
`tests/test_visualizer_engine_worker_lifetime.py`, each with its negative control.

- **A9-L1** fixed: `retire()` sets `_retiring` first, and `_on_first_configure_deadline` is inert once it is set, joined
  or not. Test: `test_the_first_configure_deadline_is_inert_on_a_half_retired_owner` (the pre-fix fence falls back and
  starts a logical runtime on the half-retired owner).
- **A9-L2** fixed: the spawn task belongs to its link. It no longer stops the role (the supervisor's start retires a
  dead role's leftovers itself), starts nothing once its link closed, and retires a worker it started for a link that
  closed meanwhile when no lease claims it (`engine_worker_lifetime.retire_if_unused`). Tests:
  `test_a_stale_spawn_task_never_touches_a_later_links_worker` (the pre-5.7 stop-then-start stops the later link's
  worker), `test_a_spawn_that_finishes_after_its_link_closed_retires_the_worker_it_started`. The frozen cold spawn
  against the 6 s bound is recorded as the operator's check (the source-run spawn from `main.py`'s entry: ready in
  1.45 s on the dev box).
- **A9-L3** settled: the owner's recovery docstring now says the reconstruction is as in process, neither capped nor
  guaranteed (a refused reload leaves the owner `failed` at fade 0 with its runtime running). No cap added here: the
  same uncapped loop exists in process and no worker failure loops on its own; the general follow-up (a per-run
  reconstruction cap, or a `failed` owner that stops its runtime when its reload is refused) is in `Current_Plan.md`.
- **A9-L4** is Bubble's owner's (not 5.7).

## Checkpoint audit 10 (8 Nov): slice 5.7

Scope: `git diff 3d856690 794d64db` (code hunks; the doc hunks only to check claims). Read: the design doc's 5.7 record,
audit 9 and its resolution, `Current_Plan.md`'s 5.7 lines, `TestSuite.md`'s 5.7 entries, the dormancy evidence JSON;
the current supervisor (start, stop, restart, the listener, the heartbeat, shutdown), `engine_worker_lifetime.py`, the
link, the owner's worker paths (configure, loss, recovery, fallback, retire), `engine_lifecycle.stop`, the replacement
construction and both reload flows, `DisplayManager.set_process_supervisor` and every reader of the controller's
supervisor, the usage collector and its Toolhelp provider, `main.py`'s module level, and `frame_codec`'s dynamic
imports. Ran (foreground): `test_visualizer_engine_worker_lifetime.py`, `test_usage_sampler.py`,
`test_process_supervisor.py` (71 passed, 19 s). Probes (`D:\Temp\Scratch\SRPSS\native_audit10`, deleted; no window, no
device): (a) a real `visualizer_worker_main` spawn from a parent whose `__main__` is `main.py`, against the same spawn
from a bare parent, three runs each: time to ready, and RSS/USS/private/threads one second after ready; (b) the image
role's heartbeat restart of a dead worker and the fenced skip (`restart(judged=)`), on the lifetime test's stand-in
processes; (c) the Toolhelp topology refresh, timed 20 times.

No high findings.

### Medium

**A10-M1. `main.py`'s module level costs the production worker about 1.1 s and 80 MB per spawn. Since 5.7 that cost is
paid on every Settings round trip. The records give no figures for it.**
- Evidence: probe (a), three runs each, on a warm source tree:

  | Parent `__main__` | Ready | RSS | USS | Private | Qt modules |
  |---|---|---|---|---|---|
  | `main.py` (production) | 1.33-1.34 s | 112 MB | 83 MB | 92 MB | 7 |
  | Bare | 0.23 s | 32 MB | 18.5 MB | 21 MB | 0 |

  Idle threads are 6 in both. Since 5.7 the lifetime retires the worker at every Settings open (`RELOAD_REASONS`
  excludes "settings", `engine_worker_lifetime.py:46`) and spawns it again at the close. The record's "about 1.5 s off
  the GUI thread" is mostly this overhead. The record files the import graph under "Left for step 6" with no numbers.
  The dormancy evidence's RSS figures (31 MB idle, 71 MB in a session) come from a bare entry, so they are not
  production's: the production idle worker is about 112 MB.
- Failure scenario: every Settings close shows the Visualizer at least 1.1 s later than a bare entry would, and spends
  an extra ~1.1 s of the 6 s first-configure bound before the session build starts. The record measured the build plus
  spawn at up to ~4 s (A9-L2). The frozen cold spawn is unmeasured. If it pushes the total past 6 s, that activation
  runs in process. Separately, both image workers carry the same ~65 MB USS each for the whole run (this predates
  5.7).
- Fix: keep `main.py`'s module level to what a child needs (stdlib, `configure_native_thread_pools`, the flavour). Move
  the Qt, engine and settings imports into `main()` or the `__main__` block. The spawned child (`__mp_main__` from
  source, `__parents_main__` when frozen) then reaches its target without the GUI stack. Then measure the source spawn
  again (expect about 0.25 s and 32 MB) and the frozen one. This touches every worker role, so it needs its own slice.
  Until then, record the figures above in the 5.7 record and in the operator's frozen check.

### Low

**A10-L1. A worker lease is not exception-safe on two exit paths. A lease that is never released keeps the worker,
and possibly a live session, running until the supervisor shuts down.**
- Evidence: `EngineWorkerLink.close()` releases the lease last (`engine_worker_link.py:641-645`). That comes after
  `self._events.disarm()`, `mailbox.close()` (whose `SharedMemory.close()` can raise `BufferError` while a view is
  exported, `packet_mailbox.py:361`) and `deleteLater()`. `_closed` is already True at that point, so a retry releases
  nothing. `QuickDisplayVisualizerOwner.retire()` returns at `:2403` when the join fails, and propagates when
  `stop_logical_runtime()` raises. Both happen before `link.retire()` at `:2406-2409`.
- Failure scenario: a close that raises, or a retire whose join fails with a worker link set, leaves the lease held.
  In the retire case `VIS_STOP` is never sent either, so the worker's session keeps its 90 Hz cadence and the loopback
  capture until the supervisor's shutdown (about 12% of a core, from the dormancy evidence). On the worker path the
  owner's controller normally has no logical runtime, so the join cannot fail. Reachability is low, which is why this
  is Low. The 5.7 claim "it leaves no worker where no Visualizer runs" still does not hold on these paths.
- Fix: in `close()`, take the lease out first and release it in a `finally` around the rest. In `retire()`, retire
  the link before the logical join, or in a `finally`; the link's retire never waits. Test: a mailbox close that
  raises, then assert `describe()["leases"] == 0`. For the negative control, use today's order.

**A10-L2. Under `--usage`, a dead but registered engine worker forces a topology refresh on every sample. The first
labelled CPU value after a spawn is not a measurement.**
- Evidence: `get_visualizer_worker_usage_snapshot` (`supervisor.py:961-968`) names the PID without checking
  `is_alive()`. `expect_pids` (`usage_sampler.py:154-165`) forces a heavy sample for any PID not in the cached tree, and
  a dead process is never in the Toolhelp snapshot. Probe (c): one refresh takes 9.96 ms (median of 20), mostly a
  GIL-held Python loop over every process on the system (`windows_process_snapshot.py:83-93`). The refresh that first
  adds the worker also primes its `cpu_percent` (`_prime_cpu`) in the same sample that reads it, so that sample's
  `visualizer_worker_cpu_pct` covers microseconds.
- Failure scenario: between the worker's death and the heartbeat's retirement (up to one heartbeat interval, or
  longer when nothing runs the heartbeat), every usage sample pays about 10 ms of GIL-heavy enumeration. That is the
  hitch class the usage sampler is known for. This only happens with `--usage` and is bounded, which is why it is Low.
  Nothing new happens at rest: with no worker the PID is None and `expect_pids` is never called.
- Fix: report the PID only while `process.is_alive()`. Report `na` for the CPU of a process first seen in this sample.

**A10-L3. The image roles' identity-fenced heartbeat restart has no test. A skipped restart still charges the restart
budget.**
- Evidence: no test calls `_heartbeat_check` or `restart(judged=)` for `IMAGE` or `IMAGE_PREFETCH`. The only test
  hits are the VISUALIZER retirement tests (`test_visualizer_engine_worker_lifetime.py:145-190`). Probe (b): a dead
  image worker is restarted correctly (backoff sleep 2.0 s, one start, `restart_count` 1, state RUNNING). When the
  role is replaced between the unlocked pre-check (`supervisor.py:501-509`) and `_stop_if_current` (`:535`),
  `restart()` returns True without starting anything. That is correct, but `record_restart()` (`:521`) has already
  counted a restart against `MAX_RESTARTS_PER_WINDOW`.
- Failure scenario: a dead image worker that a foreground `start(IMAGE)` replaces in that window still uses one of
  the five restarts in the window. This is negligible on its own, but it is untested production behaviour on the
  default path (the record's "Off the admission").
- Fix: a test with a dead image worker (heartbeat → one start after backoff), and one where the role is replaced
  before the stop (no stop of the fresh worker, no start). Do the identity check under the lifecycle lock before
  `record_restart`, or accept the charge and say so in the docstring.

**A10-L4. A transient run of 60 failed steps now costs a visible recovery and counts toward the owner's two-strike
rule, which is never reset. In process the same run recovers silently.**
- Evidence: `FAILED_STEPS_BEFORE_CLOSE = 60` (`engine_worker.py:81`) ends the session. The owner's loss path adds one
  to `_worker_failures` (`quick_display_visualizer_owner.py:2090`), which is reset only in `__init__` (`:248`). The
  second loss in an owner's life falls back in process and disables the worker for the run (`:2113`). The record says
  "a transient failure stays the runtime's retry, as in process", which holds only for runs shorter than 60 steps
  (0.67 s).
- On the question asked: the count resets correctly. A success sets it to 0 (`engine_worker.py:465`), and failures are counted only
  while the step raises. A legitimate slow start cannot trip it: a device open, the first build and the live-edge waits
  publish nothing, but they do not raise, and those waits are bounded separately (`LIVE_EDGE_TIMEOUT_S`). Successes
  do not cross a park, so failures before a park and after the unpark add up. That is by design ("a count of steps").
- Failure scenario: a step-failure run longer than 0.67 s (for example during an audio device change, which is still
  open as 5.3's rest) fades the Visualizer out and back in. If any second loss follows in the same owner (a crash, a
  hang retirement, another fail-closed), the run goes in process for good.
- Fix: decide whether one successful recovery resets `_worker_failures` (for example on the replacement's reveal).
  Otherwise, reword the record: transient runs of 60 steps or more are now recoveries that count toward the
  two-strike rule.

**A10-L5. The reload hold is proven on the lifetime module alone. No test drives the real reload into the
replacement's lease.**
- Evidence: `test_a_reload_hold_keeps_the_worker_across_turns_until_the_replacement_is_built` calls
  `lease`/`hold_for_reload`/`end_hold` by hand. `test_a_display_reload_holds_the_worker_and_settings_or_the_exit_never_do`
  checks only that `stop` takes the hold. By reading, the chain holds today: `_construct_and_start_replacement_runtime`
  → `_initialize_display` → `VisualizerHostBinding` → `owner.configure` (`visualizer_host_binding.py:448`) →
  `_configure_on_engine_worker` → `link.configure` → `lease`, all synchronous and before the `finally` that ends the
  hold (`engine_handlers.py:774-777`).
- Failure scenario: a later change that defers the owner's configure (to the reveal, or to a queued turn) turns every
  CUSTOM commit and monitor change into a retirement and a 1.3 s+ respawn (A10-M1), and no test fails.
- Fix: one engine-level test with a stub supervisor. Run CUSTOM commit → teardown → barrier → replacement, and assert
  no worker stop and one lease after the turn settles. For the negative control, configure the owner on a later turn.

### Questions answered

- **1. Off the admission.**
  - Image restart: correct (probe (b)). Backoff, the restart limit and the ERROR → RESTARTING → STARTING → RUNNING
    states are unchanged apart from A10-L3's budget charge. The fence improves on the old behaviour: before 5.7 the
    heartbeat could stop a worker that a foreground start had just replaced.
  - `_retire_dead_role` on a first start, or with a live process and a live listener: a no-op. With no process and a
    leftover listener (a listener stop that timed out earlier), it adds the listener's 2 s join to that start. For
    `IMAGE` that start is on the GUI thread. This is rare, and the record's "only act on a dead or replaced process"
    misses this branch.
  - Wiring before displays: `DisplayManager.set_process_supervisor` only stores the supervisor and sets the owner's
    controller. In process, the controller only stores it. No beat-engine or media consumer reads it:
    `BeatEngine.set_process_supervisor` has no caller and calls a method `AudioWorker` does not have (dead code,
    caught). The image pipeline reads the engine's own supervisor. With `display_count == 0` it is now wired with
    nothing to receive it, which is harmless.
  - Usage sampler at rest: no new OS call. It reorders `_resource_snapshot` and builds a small per-process dict per
    sample. A10-L2 covers the case with a worker.
- **2. Lifetime.**
  - Leaks: the configure's exception path releases its lease (`close()` in its `except BaseException`).
    `_construct_and_start_replacement_runtime`'s discard and `finally` end the hold, and the exit ends it. The leak
    paths are A10-L1's. A hold left by a raise before the `try` (`collect_retired_generations`, the watchdog arm) lasts
    until the next stop or the supervisor's shutdown, as the record says.
  - Thrash: none on mode or preset changes (no link change), display power (the lease is kept), a recovery (the
    replacement link is opened in the same call, `:2101`) or a CUSTOM commit (held). By reading, a
    `visualizer_activation_failed` reconstruction releases the lease at the failure and takes the hold at its later
    stop, so it may retire and respawn once. That is acceptable on a failure path.
  - Event-driven: one queued signal per release, the retirement is a one-off IO task, and there is no `QTimer`.
  - Stop against start: one lock (`_start_lock`) serialises them, and the lease and `_retiring` are read and written
    under `_lock`, which closes the window. The wait happens on IO threads, never on the GUI thread, except the
    bare-rig branch with no thread manager.
  - The engine's IO pool has four workers (`core/threading/manager.py:664`). Audit 9 said two (`:633` is the helper
    manager's default), so A9-L2's "two-worker pool" premise was wrong. A retirement plus a waiting spawn occupies two
    of the four.
- **3.** See A10-L4.
- **4. Lock order.** Lifecycle lock → `_lock` everywhere, and `_start_lock` → lifecycle lock. Nothing takes them in
  reverse. Callbacks cancelled under the lifecycle lock (`_stop_if_current`, `_retire_dead_role`) only emit queued
  events (the link) or complete a prefetch future, and take no lifecycle lock. The heartbeat skips `_transitioning`
  roles and fences by identity. A spawn that finds a dead role cleans it itself. No remaining race found.
- **5. Frozen.** See A10-M1. The codec's string imports (`core.ribbon_packet`, `core.waveform_ribbon_scene`,
  `core.ribbon_style`, `widgets.spotify_visualizer.extruded_bubble_drift_log`) are reachable from static imports in
  the main graph, so Nuitka includes them.

### Records overstated

- "Parked ~0 CPU" and "thread count flat": both are measured on a bare-entry worker with recorded PCM. That entry
  does not run `configure_native_thread_pools` (`OPENBLAS_NUM_THREADS=1`) at its own module level, and its RSS (31/71
  MB) is not production's (A10-M1). The probe script was not kept, so the figures cannot be reproduced. "Flat" is
  within one worker across three sessions. Under 5.7 the churn that matters is a fresh process at every Settings round
  trip (handles, mappings), and that is unmeasured. Gate 4 covers it, so this is about wording, not a gap.
- "Respawned at the close (about 1.5 s)": that figure is spawn-to-ready only. The Visualizer shows after the
  configure, the build, the first presentable frame and its fade.
- "Off the admission ... both only act on a dead or replaced process": see `_retire_dead_role`'s orphaned-listener
  branch above.

### Not verified

- The frozen build: the cold spawn against 6 s, and the worker's RSS there (the operator's check).
- The production-entry worker inside a session: RSS and threads with `OPENBLAS_NUM_THREADS=1`, and park with a real
  loopback device.
- The Settings round trip's time to a visible Visualizer, and process, handle and mapping growth over repeated round
  trips (gate 4).
- Whether display sleep on DisplayPort monitors produces `monitor_topology` reloads whose replacement has no
  Visualizer. In that case the worker would be retired and respawned at every sleep and wake.
- Whether `SharedMemory.close()` can actually raise in `PacketMailbox.close()`: that depends on whether a held
  publication keeps a view into the mapping. A10-L1 is filed by reading.

### Audit 10 resolution (8 Nov)

Each fix has a regression test that fails with the fix reverted (the source hunk restored from the audited commit
and the test run; the failures are quoted in each commit message). Tests: `tests/test_visualizer_engine_frozen_spawn.py`
(A10-M1), `tests/test_visualizer_engine_worker_lifetime.py` (A10-L1, L3, L5), `tests/test_usage_sampler.py` (A10-L2),
`tests/test_visualizer_owner_engine_worker.py` (A10-L4).

- **A10-M1** fixed by 22af1f00: `main.py` (and `main_mc.py`) skip their application imports while a worker process
  re-executes them (`core.spawn_child.importing_parents_main`: the spawn name, a frozen `__parents_main__` being
  imported, or multiprocessing's own inheriting marker). The parent runs the same module-level statements in the
  same order. From a `main.py` parent, three runs each: the engine worker is ready in 0.29 s with 32 MB RSS / 19 MB
  USS and no Qt module (was 1.62 s, 112 / 83 MB, the Qt GUI stack); an image worker the same (was 1.56 s, 112 / 83 MB);
  a `main_mc.py` parent the same. Evidence and probe scripts:
  `.artifacts/evidence/architecture/native_core_p2/20261108_audit10_spawn_cost/`. Tests: the production-entry spawn
  loads no QtGui/QtWidgets/QtQuick/QtQml (engine worker by `sys.modules` and mapped DLLs, image worker from `main.py`
  and `main_mc.py` by mapped DLLs), and the entry modules run as `__parents_main__` import no Qt, engine or Settings
  (under any other name they import all of it). Reverted: 5 fail. No build change: imports in a module-level `if`
  are still followed by Nuitka, and the frozen audit and closeout contracts pass. The frozen cold spawn stays the
  operator's check.
- **A10-L1** fixed by d0ddce94: `EngineWorkerLink.close()` takes the lease out first and releases it in a `finally`;
  `QuickDisplayVisualizerOwner.retire()` retires the link (its `VIS_STOP` sent) and releases the frame completion
  before the logical join. Tests: `test_a_link_close_that_raises_still_releases_its_lease` (mailbox and `deleteLater`
  raising), `test_a_retire_whose_logical_join_fails_still_stops_the_session_and_releases_its_lease` (join fails or
  raises); A9-L1's test follows the new order (its negative control now also puts the link back). Reverted: 6 fail.
- **A10-L2** fixed by 04eab34d: `expect_pids` forces one refresh per distinct named PID and forgets a PID once it is
  no longer named (the service tells it once); a process added by the sample's own refresh reports `na` CPU and stays
  out of `cpu_app_pct`. The supervisor still names the PID from its state with no OS query. Tests: a dead named PID
  refreshed once (six times before), the first CPU `na` then measured, a 5000 % first read left out, the service's
  one forget call. Reverted: 4 fail.
- **A10-L3** fixed by d9727528: `restart(judged=)` checks the identity, charges the budget and stops the judged process
  under the role's lifecycle lock (`_restart_judged`); a skipped restart charges nothing. Tests:
  `test_the_heartbeat_restarts_a_dead_image_worker_once_after_its_backoff` (IMAGE, IMAGE_PREFETCH),
  `test_a_heartbeat_restart_of_an_image_worker_replaced_meanwhile_does_nothing_and_charges_nothing` (the foreground
  start holds the lifecycle lock while the restart waits on it). Reverted: `restart_count` 1.
- **A10-L4** fixed by 0e8967fd: a recovery whose replacement completes its reveal on the worker resets
  `_worker_failures`; the second strike is now a failure before a recovery completed. Chosen over "do not count a
  step-failure fail-close": that needs the reason sent over the pipe, and a deterministic step failure would then
  reconfigure about every 0.7 s until the recovery deadline. The record's "as in process" is corrected (design doc,
  5.7 "Session (3c)"). Test: the lost-session test (a later loss after a completed recovery recovers; a loss before
  the replacement's reveal goes in process with reason "second failure"); the A7-L1 flash test reads the reset.
  Reverted: 3 fail.
- **A10-L5** tested by 071635e1: `test_a_custom_reload_hands_the_running_worker_to_the_replacements_owner` drives a real
  `ScreensaverEngine` through the CUSTOM commit (real `engine_lifecycle.stop`, teardown, destruction barrier,
  `_construct_and_start_replacement_runtime` and `_initialize_display`) to the replacement's REAL owner, admitted by
  a display-manager stand-in's `initialize_displays` through the host binding: no stop, no start, one lease. Negative
  controls: configured on a later turn, the worker is stopped and started again; and, run by hand, the stop without
  its hold gives `['stop', 'start']`.
- **Audit 9 correction:** the engine's IO pool has four workers (`ThreadManager`'s default `ThreadPoolType.IO: 4`),
  not two: A9-L2's "two-worker IO pool" read `create_helper_manager`'s default. The A9-L2 fix does not depend on it
  (the race needs only two IO threads; the stale task stops nothing). The lifetime test's comment is corrected.

Off the admission (`--viz-engine-worker` off): the parent's startup imports run in the same order (one stdlib module,
`core.spawn_child`, comes first); every worker process (the image workers) skips the application imports, from
source or frozen; the image roles' heartbeat restart charges a restart only when it restarts; under `--usage` a newly
added child's first CPU reads `na` and is left out of that sample's total. The owner's `retire()` order and the strike
reset change nothing in process (no link, no frame completion, no worker).

Focused runs after the fixes: the production path, the owner contract, edge, retirement, logical-ownership and
five-owner-chain suites, `test_process_supervisor.py` and `_availability`, `test_engine_lifecycle.py`,
`test_usage_sampler.py`, the lifetime and frozen-spawn files, the frozen-audit and closeout contracts,
`test_visualizer_engine_worker.py`, `_import_weight`, the worker parent-death and optional-startup suites and the
engine replacement suites (hang window, Settings round trips, S hotkey, runtime destruction, display power): 251
passed, 3 skipped. `main.py`'s own and startup suites (exit-after, fatal backstop, fresh-start logging, diagnostic
build, CLI admissions, the Reddit helper preload, Linux branches, run lifetime, Guided Setup, onboarding resume, the MC
entry, frame trace, native thread pools, runtime purity, environment reads, the bootstrap order, defaults authority,
expansion capability's import graph, GUI stall sampler, ownership trace, experiment flags, switch telemetry): 226
passed, 7 skipped. The four owner-on-the-worker files: 77 passed and one failure of a pre-existing negative control
(`test_the_framed_view_the_worker_tick_reads_follows_the_owners_controller`, its `run(False)` half) that passed alone
and in its own file (26 passed); recorded in `Current_Plan.md` as a side finding.
