# Native core P2: phase-boundary audit (8 Nov 2026)

Scope: all of P2 on `main` at `38c38862` (the gate 3 record landed during this audit; it was read). This covers the
design doc and its records, checkpoint audits 1-11, the Graphics Backend Decision with its 8 Nov addendum, the P1 spike,
R-176 to R-181, the code under `core/visualizer_engine/`, the owner, link and lifetime, `logical_edges`, the
supervisor, `spawn_child`, the Nuitka worker plugin, the frozen audit and the live check. It also covers the gate 3
and gate 4 evidence and both frozen diagnostic checks.

The change that makes the worker the default had not landed when this was written. Its worktree had no edits. So the
fallback paths are reviewed as they stand on `main`, with the admission still `--viz-engine-worker`
(`core/diagnostics/experiment_flags.py:66`, default False).

Read-only. Focused runs, all foreground with timeouts, all passed:
- `test_visualizer_engine_packet_abi`, `_packet_mailbox`, `_publish_stamp`, `_worker_lifetime`, `_frozen_spawn` and
  `_import_weight`: 78 passed.
- `test_visualizer_engine_frame_codec`, `_worker_device` and `test_visualizer_live_check`: 35 passed.
- `test_visualizer_owner_engine_worker`: 28 passed.

Four offscreen source-mode probes ran under `D:\Temp\Scratch\SRPSS\p2audit\`, with nothing shown and no device opened,
and were deleted afterwards. They measured the frame payload per mode, per preset and at the top of every Settings
control.

## Verdict

P2's mechanism holds up. The ABI and its seqlock, the cross-process wake, the asynchronous control edges, the bounded
recovery, the lease lifetime and the frozen spawn are sound. The identity, dormancy and frozen evidence is real. Gate 3
shows a large and structural gain in main's GIL share: about 0.85 down to about 0.08. The worker should not become the
default yet, because two findings make it worse than in process for real users:

1. **Fixed slot (High).** Each frame slot is fixed at 1 MiB. Extruded Bubble's default preset (Night Water, free drift
   on) exceeds it from the second frame once the Particles range is raised to its schema default `[0.1, 0.35]`. It
   reaches 17 MiB at the top. On the worker every publish then raises, the session fails closed and recovery fails
   the same way. The Visualizer stalls and fades, then runs in process for the rest of the run. In process the same
   settings work.
2. **Worker diagnostics (High).** The worker process never receives the app's diagnostic flags and has no log
   destination. With the worker as default, every tick, DSP and device exception, every `[PERF]` and reactivity record
   from the tick, and every fail-closed reason disappear from the logs. The design doc says otherwise.

Linux has never run the worker path (High, if the default applies there). With those fixed or scoped out, and the
documentation brought into the contracts, the default is justified. For P3, the ABI is a good base, but four traps
need deciding first: the mapping's lifetime against a native reader, a single consumer, per-frame immutable geometry,
and fp64 compute.

## Findings

### Critical

None.

### High

**H1. A frame bigger than the fixed 1 MiB slot fails the worker path. Extruded Bubble reaches it with one Settings
change in its default preset.**

*Claim:* The design doc's measured section (`Native_Core_P2_Engine_Design.md:148`) says "1 MiB slots (3 MiB per
generation) hold every mode". That figure came from 2 s of one clip at the default settings.

*Evidence:*
- The slot size is fixed. The link creates its reader with the default size (`engine_worker_link.py:485`, using
  `DEFAULT_SLOT_BYTES = 1 << 20` from `packet_mailbox.py:47`), and an oversized payload raises:
  `packet_abi.py:206-207` raises `ValueError` when `len(payload) > capacity`.
- `logical_tick` has no handler around `_publish_logical_state` (`tick_pipeline.py:1365`), so the step fails.
  `EngineSession._paced_step` counts it (`engine_worker.py:544-553`). After `FAILED_STEPS_BEFORE_CLOSE = 60` the
  session fails closed (`:560-571`).
- Probes, frame-codec payload on the production owner path, offscreen. Every mode at preset 0 with every body Slider
  and Range at its top: Extruded Bubble peaks at **17,864 KiB**, with 363 of 364 frames over capacity. Every other mode
  stays at or below 107 KiB, except Waveform Ribbon at 343-407 KiB.
- Extruded Bubble at preset 0 (Night Water, `extruded_bubble_drift_specks` `[0.05, 0.35]`, so free drift is on), on the
  `human` clip:

  | Particles range | Largest frame | Frames over capacity | Specks rows |
  |---|---|---|---|
  | `[0.06, 0.12]` (the preset's own) | 778 KiB | 0 (76% of capacity at most) | 2048 |
  | `[0.1, 0.35]` (the schema default) | 1,799 KiB | 1163 of 1164, from frame 1 | 16,384 |
  | `[0.3, 0.6]` | 5,719 KiB | 1163 of 1164 | 65,536 |
  | `[0.5, 1.0]` | 17,474 KiB | 1163 of 1164 | 216,000 |

  The real mailbox refuses the second frame: `ValueError: frame payload of 1117643 bytes exceeds the slot's 1048504`.
- What drives the size: the speck capacity is `min(SPECKS_FULL=216000, pow2(216000 * emission^2))`
  (`extruded_bubble_simulation.py:1273-1276`), and it only grows. Each row is shipped twice: as GPU geometry, and as
  float64 `DriftFamily.source` (see M1).

*Failure scenario:* A user on the default Extruded Bubble preset raises Particles. On the worker path:
1. The bars freeze for about 0.67 s (60 failed steps), then the held frame fades.
2. The replacement session publishes one frame and fails again. The recovery deadline (6 s) or the second strike falls
   back in process, and the worker is off for the run.
3. The main log says only "the engine worker's session ended (closed after a failure, or the process died)". The
   `ValueError` is lost (H2).

In process nothing goes wrong. No identity gate, live check or gate 4 run used a non-default Settings value for
Extruded Bubble, so none could see this.

*Fix:*
- Stop shipping `DriftFamily.source` per frame (M1). That alone brings the default to about 138 KiB.
- Bound or size the slot per mode: either from a computed worst case, or by a reconfigure that remaps when a payload
  exceeds capacity. A remap is an edge, so it is not per frame.
- Make an oversized publish its own fail-closed reason, carried to the main log.
- Add a gate that drives every mode at the top of every Settings control through the codec and asserts the payload
  fits the slot. The probe above is that gate's shape.

**H2. The worker's diagnostics and failure reasons never reach any log. The records claim otherwise.**

*Claim:*
- Design doc 5.7 (`:1262-1263`): "a session that failed closed reaches the main log as the owner's session failure
  (its reason, the step's exception, is in `VIS_STOP`'s report …) … `worker_visualizer.log` on perf runs only".
- Design doc 5.3 (`:884`): "a worker logs nowhere unless perf metrics are on".

*Evidence:*
- The worker's flags never get set. `_PERF_METRICS_ENABLED` and `_VIZ_DIAGNOSTICS_ENABLED` default to False
  (`core/logging/logger.py:47, 55`) and are set only by the logging setup in the main process (`:2828-2831`). A spawned
  worker never runs it, and since A10-M1 it skips `main.py`'s application imports too.
- So `setup_worker_logging` always installs a `NullHandler` (`core/process/workers/base.py:44`). No
  `worker_visualizer.log` exists anywhere in the repository or under `%LOCALAPPDATA%`/`%APPDATA%\SRPSS`, including the
  gate 3 worker run, which had `--perf` on.
- Session loggers (`engine_worker._log()`, `logical_runtime`'s step-failure log, the delivery watch) fall to Python's
  `lastResort`. That writes WARNING and above to the inherited stderr: a console from source (`runner.txt` caught one
  `Tick dt spike`), nothing in a frozen windowed build.
- The owner never reads `VIS_STOP`'s report (`retire` sends it without waiting). The session's end reaches the owner
  only as a closed pipe, through `listen_for_wakes` `on_closed` (`packet_mailbox.py:342`). Its reason string is fixed
  (`engine_worker_link.py:718-721`).
- `is_viz_diagnostics_enabled()` gates the tick's reactivity records (`tick_pipeline.py:344, 434, 792`). It is always
  False in the worker.

*Failure scenario:* With the worker as default, a tick exception (H1), a DSP fault, a PortAudio error or a native crash
in the worker leaves no stack and no reason in user logs. The operator's reactivity and `[PERF]` diagnostics from the
tick are silently off. Diagnosing anything on the default path means rerunning in process, which changes the very
timing being diagnosed.

*Fix:*
- Pass the diagnostic profile in `VIS_CONFIGURE`, or at spawn, and apply it in the worker.
- Give the worker a log route into the main log: forward records over the response queue, or a file the main log
  points to.
- Carry `session.failed` in the closing edge's report and log it. The pipe end can be followed by a fetch of the reason
  on the next edge's reply, or a `VIS_STOP` that the owner does await on the failure path.
- Enable `faulthandler` in the worker for diagnostic runs.
- Add an opt-out admission that forces in process, for diagnostics.
- Correct the two doc sentences.

**H3. Linux (if the default applies there): the worker path has never run.**

*Evidence:*
- Python 3.14 is the Linux build's interpreter (`.github/workflows/linux-build.yml:58`). Its default start method is
  `forkserver`.
- The wake pipe's POSIX branch (`packet_mailbox.py:87-97`: a non-blocking framed write) is never exercised. Every test
  that touches it runs on Windows, and two tests replace it.
- Passing the pipe's writer end through the `mp.Queue` uses `resource_sharer` on POSIX. That path has never been run.
- The design and audit 11 list "Linux (`utils/audio_capture_pulse.py`) is unexamined" and "the forkserver preload with
  a Nuitka binary" as not verified. `Docs/Guardrails/Linux_Compatibility.md` does not mention the worker.

*Failure scenario:* A Linux user gets an untested process path as the default: the Pulse capture, the forkserver child,
the POSIX wake and the resource tracker on the attached `SharedMemory`. A failure there would show up only as the
recovery's fades and an in-process run, with no logs (H2).

*Fix:* Make the default Windows-only until one Linux run of the gate 4 script and a paced session pass, or run the
POSIX wake under a Linux CI job. Record the decision in `Linux_Compatibility.md`.

### Medium

**M1. Extruded Bubble ships its CPU reference arrays and immutable geometry in every frame.**

*Evidence:*
- A default Extruded Bubble frame is 609 KiB. 568 KiB of it is `drift_families`, and inside that the
  `DriftFamily.source` float64 arrays are 482 KiB (`extruded_bubble_drift_log.py:41-54`: "keeps the float64 arrays
  for the CPU reference").
- Their only reader is `MaterialDriftReference` (`:220, :231`), the CPU oracle. The GPU drift solver reads `geometry`
  plus the step log (`extruded_bubble_drift_solver.py:27-30`).
- `geometry` itself changes only at a new `revision`, which is the renderer's cache key, yet it is re-sent every frame.
- Probe: without `source` the payload is 138 KiB, decode drops from 0.56 to 0.34 ms, and encode from 0.47 to 0.35 ms.
  In process both are a reference handoff at zero cost.

*Failure scenario:* About 0.5 MiB per frame at 90 Hz (roughly 45 MB/s) is encoded in the worker, copied into the slot,
copied out by `bytes(view[...])`, and copied again by `np.frombuffer(bytes(...))`. Much of that happens on the render
thread at sync (A2-H3), where the GUI thread is blocked. This churn is also what made R-179's sawtooth large. It is the
root cause of H1.

*Fix:* Drop `source` from the production frame and keep it only where the oracle runs. Ship each family's geometry once
per revision: a revision-keyed side record, or the slot only when the revision changes. Treat this as the template for
P3's Extruded Bubble layout.

**M2. The first configure's fixed 6 s bound has about 1 s of margin under load. Past it, every activation runs in
process, late.**

*Evidence:*
- The first configure's deadline is `_ACTIVATION_TRANSACTION_DEADLINE_MS = 6000`, armed when the configure is sent
  (`quick_display_visualizer_owner.py:70, 1814-1836`). It covers the spawn, which is queued on the IO pool, plus the
  imports, about 1.7 s from a bare start (A11-L1), plus the session build.
- Measured, at 1 s log resolution:

  | Run | First configure |
  |---|---|
  | Idle source | 2-3 s (gate 3 prep, PCM-receipt proof) |
  | Frozen | 1.57-1.72 s (frozen check 2: `dt_ms` 1572 and 1723) |
  | game60 | about 5 s (gate 3 on: configuring 21:12:14, configured 21:12:19) |

  The game60 configure carried 20 s of PCM, so production should be a little faster.
- The fallback is not counted (`count_for_run=False`), so the next owner retries.
- Every Settings close respawns the worker, because Settings holds nothing.

*Failure scenario:* On a slow or busy machine (an HDD, AV scanning a frozen binary, the startup IO burst of Feeds,
Gmail and images ahead of the spawn), each activation waits about 6 s hidden and then falls back in process. That is
strictly later than in process, at startup and after every Settings close, every time.

*Fix:*
- Bound the spawn and the configure separately, and extend while the worker reports progress (ready received, imports
  done), as R-180 did for render progress.
- Or count a deadline miss for the run after N, so a slow machine settles in process instead of paying 6 s per
  activation.
- Record reveal latency against in process under load.

**M3. Contracts, Spec, Guardrails and Index do not describe the engine worker or the frame ABI.**

*Evidence:* `Spec.md`, `Docs/Contracts.md`, `Docs/Guardrails.md`, `Docs/Guardrails/*` and `Index.md` have no
mention of the engine worker, `WorkerType.VISUALIZER`, `core/visualizer_engine/`, `engine_worker_link`, the packet ABI,
the lease and hold lifetime, "a full wake pipe never blocks the tick", or the bounded recovery. The only source is a
`Future_Work` design doc of 1,774 lines.

*Failure scenario:*
- The default architecture and P3's input contract have no governing contract.
- Guardrail-driven work (the srpss-guardrails skill, "check forbidden lists first") cannot find them.
- Future changes to the supervisor, its queue policy (L1) or the logical tick can break the worker path without
  tripping any written rule.

*Fix:* Before the flip, promote the stable parts into Spec and Contracts: the ABI layout and its versioning, the
single-writer and single-reader roles, the slot identity, the lifetime and recovery bounds, the not-at-rest rules and
QtCore-only. Add Index rows for the modules and a Linux guardrail note.

**M4. Evidence: the identity, live and gate 3/4 runs cover default presets only, and gate 2 has no record.**

*Evidence:*
- `owner_worker_gate`, `live_engine_gate`, `engine_worker_gate` and the live checks all use the offline request at
  preset 0, or one shipped preset (Waveform Ribbon P1). No gate drives non-default Settings through the worker. H1 is
  what that hid.
- Gate 2 ("the existing pixel oracles and BTF checks unchanged") is defined (`:116-123`) but recorded nowhere. It holds
  only by construction: identical decoded frames, plus the main-side frame completion that the view gate covers.

*Failure scenario:* Worker-only failures that depend on settings (payload size, a codec type not in `_TYPES` as
`RibbonStrays` was, a value outside the frozen domain) ship unseen.

*Fix:* Add the max-settings and every-preset codec gate from H1, over every mode and type table. Write a short gate 2
record stating the by-construction argument and the frame-level gate that backs it, or run the BTF and pixel oracles
once with the admission on.

**M5. With the worker on by default, the in-process memory growth from gate 4's control stays relevant, but hidden.**

*Evidence:*
- In process, cycling modes grows main's `private_other` by 150-250 MB a lap (`Current_Plan.md:245-254`). On the
  worker path main stays flat.
- The worker itself shows no such growth. Frozen check 2 had it at 46-59 MB USS across Waveform Ribbon, Extruded
  Bubble and presets. The gate 4 worker figures predate R-179's fix (L5). That points to something specific to main,
  not to tick allocations.

*Failure scenario:* The flip masks it for most users. The fallback (H1, M2, any failure), the Studios and Linux (if H3
is scoped out) keep it, and with nobody running in process every day, nobody sees it.

*Fix:* Attribute it before the flip, as Current_Plan already says: the map diff between two laps. Re-read the worker's
memory with R-179 fixed, at 1 s resolution, across a lap.

### Low

**L1. The supervisor's "drop oldest" queue policy is wrong for an ordered control channel.**

*Evidence:* `send_message` evicts the oldest request when the 64-slot queue is full (`supervisor.py:624-631`). A
pickling failure in `mp.Queue`'s feeder thread also drops a message silently.

*Failure scenario:* This needs a stalled worker with 64 or more messages queued. The evicted message is then an ordered
edge (a `VIS_CONFIGURE`, `VIS_STOP` or `VIS_SET_MODE`), and its correlation is never answered. A dropped
`VIS_SET_VIEW` leaves `_view_in_flight` True for the session, so Edit's orbit stops reaching the tick and no failure
fires.

*Fix:* For `CLIENT_RESTARTED_ROLES`, refuse the send instead (the link's `_NOT_SENT` failure path exists). Pickle the
control payloads synchronously so a failure is raised to the sender.

**L2. Gate 3 labels and two of its fields.**

*Evidence:*
- `tick_gil_share` and in-process `main_gil_share` are wall time per tick times the rate (`visualizer_live_check.py:
  215-238`), not GIL hold time. At 87% system CPU the in-process 11.25 ms tick includes waits.
- "Revisions waiting at sync 0 / 0" on the worker path is zero by construction, because untaken frames are never
  recorded. The record marks newest age as a lower bound but not this row.
- The worker plays `PacedPcmSource` blocks phase-locked to its own cadence (`WORKER_PCM_LOOP_S`). The in-process run
  uses a device-like loopback thread. So the worker-side numbers (6.12 ms tick, 0.55 share) are not the production
  device path's. The record names the 20 s loop but not the difference in how audio is delivered.

*Failure scenario:* None for the verdict, since the direction is structural. The numbers could be quoted beyond what
they measure.

*Fix:* Rename the fields to "occupancy". Mark the waiting row as vacuous on the worker path. Add the audio-delivery
note. Size the worker's tick on a device run when one is next approved.

**L3. The usage sampler costs about 13 ms more per 15 s sample on the worker path.**

*Evidence:* `collect_ms` is 58.2 against 45.6 under game60, 13 of the worker run's 23 hitches sit at the sampler's tick,
and the operator always runs `--usage`. This is recorded (`Current_Plan` §5).

*Fix:* Already tracked. Note that the flip makes every `--usage` run pay it.

**L4. Smaller diagnostic and robustness gaps.**
- The main-side wake listener takes the GIL on every publish (90/s), including when a wake is already pending. This was
  never measured separately.
- `presentation_inputs_snapshot` silently skips any PySide6-typed attribute (`logical_edges.py`). A capture-read
  control that held a Qt value would never be forwarded, with no error.
- There is no liveness check on the frame stream itself. A worker whose message loop answers heartbeats but whose
  cadence thread is blocked (a lock or a native call that releases the GIL) freezes the Visualizer indefinitely. This
  is parity with in process, but in process a Python-side deadlock is visible in the main log and here it is not.
- *Fix:* carry the session's revision in the heartbeat's ACK and treat a stalled count while playing and unparked as a
  failure (no timer: the heartbeat already runs). Fail loudly on a skipped Qt value.

**L5. The design doc and Current_Plan disagree with the evidence in places.**
- Gate 4's worker row ("58 MB -> 105-115 MB … then flat lap to lap", `:1451`, and `Current_Plan.md:251` "plateaus at
  ~110 MB") was taken before R-179's fix (gate 4 source `e713dd74`, fix `49203808`). R-179 itself says those readings
  sat on the sawtooth. Neither record carries the correction.
- `Current_Plan.md:221-228` still lists "a confirming GitHub Remote build … engine worker on `qt6core.dll` only … one
  Settings round trip" as next. Frozen check 2 (build `098b3f0e`, which contains `601f8feb`, `49203808` and
  `e713dd74`) already shows the engine worker with `qt6core.dll` only, USS 46-59 MB flat across modes, and a Settings
  retirement and respawn. Only the build log and audit line checks remain.
- `tests/test_visualizer_engine_import_weight.py` is not listed in `Docs/TestSuite.md`.
- The ABI text "picks the slot that is neither the newest nor being read" (`:79`) is wrong: the writer avoids only the
  newest slot (`packet_abi.py:215`) and cannot know the reader's.

## Resolution work

### M1: CPU reference data at the publication boundary

The first slice removes `DriftFamily.source` from the canonical frame at `logical_frame_capture`, before either
in-process presentation or worker encoding. The simulation keeps the float64 source for the CPU oracle; each immutable
descriptor memoizes one source-free render descriptor, sharing its exact geometry bytes. Repeated ticks do not copy
arrays or geometry. The CPU oracle consumes simulation snapshots directly, never a source-stripped published frame.
`tests/test_extruded_bubble_frame_drift_boundary.py` exercises the real owner/capture path with independent non-default
controls and all three drift families: source is absent, geometry bytes are the same object, every other descriptor
field and step byte matches, renderer digests remain identical, and codec round trips are exact and smaller. The
second test covers descriptor reuse, geometry edits, capacity growth within a revision and reference-counted release
without a cyclic-GC wait. Both tests failed before implementation. Restoring the old boundary in memory by making
`DriftFamily.render_descriptor` return `self` fails the capture test at "CPU reference arrays crossed the publication
boundary" (the negative control, exit 1).

Focused run: boundary, frame-codec (every mode) and CPU-passage-ingress tests: **20 passed**. After tightening the
projection to avoid a self-reference cache on an already source-free descriptor, the boundary tests passed again
(**2 passed**). Changed Python files compile and `git diff --check` passes. This proves transport/data parity; no native
visual, build, device or load acceptance is claimed.

Geometry still travels per frame; H1 below bounds it without adding a side record. A revision alone cannot key an
immutable side record: `DriftLog.admit` keeps
the revision when capacity grows. Any later transport must account for capacity as well as revision and session
identity. No geometry protocol, slot sizing, default admission, recovery behavior or renderer change is part of this slice.

### H1: bounded activation-time capacity and a hidden-edge remap

H1 sizes the existing parent-owned mapping before `VIS_CONFIGURE` from the activation's resolved logical
controls. Every other mode keeps the 1 MiB slot envelope. Extruded Bubble reserves that same non-geometry envelope
plus any admitted free-drift geometry: clouds are bounded by `(SPECKS_FULL + SNOW_FULL) * CLOUD_GEOMETRY_BYTES`
(6,992,000 bytes), chains by `drawable_chains(bead_chains) * CHAIN_GEOMETRY_BYTES` (at most 23,040 bytes). A nonzero
particle range can reach the full cloud cap because its musical follower can overshoot; sizing at the authored
endpoint or the first frame is unsound. The 1 MiB remainder covers the bounded 128 x 24-float64 step history
(24,576 bytes), 384 x 50-float32 live/retiring wake records (76,800 bytes), 192 x 8-float64 bubbles (12,288 bytes),
cluster records, descriptors, canonical parameter tree and publication envelope. Slot bytes include the ABI's
72-byte overhead and are rounded to 16-byte alignment. Source-free geometry and every non-geometry byte remain exact.

Capacity grows only at an explicit hidden activation. The existing `PacketMailbox` stages one larger mapping;
`VIS_SET_MODE` carries its old/new mapping identity. The production activation commit stops and joins the old logical
producer before its mailbox writer reattaches, then restarts the same cadence. The reply names the mapping it
attached; the parent validates that identity and swaps the reader under the existing decode lock before closing the
old mapping. The same mailbox object, wake pipe, listener, controller, lease and session remain owners. A smaller
activation retains the allocation until session retirement; there is no tick-time resize/retry loop. Failure,
late/mismatched replies and retirement must release staged candidates without adopting them.

Focused gates must drive each mode with independent non-default and schema-maximum controls (including offered
size-affecting choices), plus a complete maximum EB geometry/step/wake frame. They must reproduce the old overflow,
prove packet/header identity and byte parity after remap, reject stale edges, cover failed staging/commit/retirement,
and prove that reader close waits for its existing decode lock. No default flip, H2 diagnostic-file work, GPU geometry
cache, native-reader lifetime promise, load run or build belongs to this slice. P3 still owes its explicit native
read-side quiescence decision before replacing the Python lock.

The hidden-edge gate proves the old producer is joined at writer attachment; the
same mailbox and wake listener survive, the replacement header matches the committed identity, and the old mapping
is released. The maximum EB geometry/step/wake/body fixture encodes to 7,138,141 bytes under its test-owned controls:
the old 1 MiB slot refuses it; the admitted 8,063,616-byte slot round-trips every byte. Independent non-default and
schema-maximum numeric/choice/toggle controls run every mode through actual owner publication and the real packet
mailbox. Pure gates cover failed allocation, stale writer/ack identities, staging abort/retirement, and quiescence
under the reader's existing lock.

An unexpected envelope violation is an aligned u64 actual-length store at reserved header offset 48, before EOF on
the existing wake pipe (ABI 2, zero-neutral append; no existing field moved). The cadence fails closed immediately;
the owner logs actual/capacity bytes, retires the session and leaves the activation failed, retaining the last
rendered frame. It never enters ordinary worker recovery, in-process retry or reconstruction. A real oversized publish
in the never-shown recorded-PCM owner proves that path. This is not a general worker diagnostic route (H2 remains).

Negative controls: forcing admission back to the old 1 MiB envelope fails the full-geometry gate with
`7138141 > 1048504`; skipping writer attachment fails the remap gate with `100039 > 65464`; bypassing the terminal
capacity guard fails its real-owner gate. Each exits 1 as expected. Initial capacity/remap tests failed before their
implementation. Focused results so far: the capacity/maximum-mode gate **23 passed**; extended pure admission/ABI
gates **22 passed**; real hidden-activation and terminal-failure gates **2 passed**; five existing owner control,
binding, retirement and recovery regressions **5 passed**. Native IPC tests need IPC access: the restricted host's
`multiprocessing.Pipe` is denied (WinError 5); the same tests pass with native IPC access.
Final combined capacity/ABI/selected-owner run: **48 passed**. The hidden-edge proof was then extended to both a mode
change and an independently authored same-mode settings change from dormant drift to maximum controls: **2 passed**.
The expanded pure gate (including a candidate writer failing before its ack) passed again: **22 passed**. Changed
Python compiles and `git diff --check` passes.

Side defect found and repaired at initial admission: a refused wake pipe previously left an already-created mapping
and exported views unclosed. Initial configure now opens the pipe first; a mapping-allocation failure closes both
ends, and a denied pipe creates no mapping (focused regression). Normal steady-state publication gains no new work;
capacity calculation/allocation occurs only at configure/hidden activation. Active EB may reserve up to about 23 MiB
across three slots; other modes retain their original 3 MiB mapping until an EB activation needs growth. No native
performance/load, real-device, rendered-pixel, frozen or Linux validation is claimed.

#### H1 review: simultaneous retained high-water payloads

Root's read-only review and independent Terra 6.1 High audit found no actionable remap/EOF defect in their focused
source/test scope. Root requested a stronger admission gate before acceptance: the short schema-maximum replays
did not prove simultaneous retained-buffer high water. `tests/test_visualizer_engine_frame_capacity_high_water.py`
now completes the real Waveform Dynamics history preparation, admits actual cohort/burst producer records and passes
their combined snapshot through canonical capture, codec and packet mailbox. It also exercises the portable
`RibbonRing` maximum with real `append`/`packet`, `RibbonStrandCohorts.update` and `RibbonBursts.admit` outputs.
Current product Dynamics uses `RIBBON_CAPACITY = 4`; the reusable packet/ring contract admits `MAX_RIBBONS = 8`.
Those are deliberately separate cases. A first successful event already publishes the complete fixed-capacity
cohort/4096-record burst buffers; the proof measures all retained bytes together, not an impossible claim that every
burst record is simultaneously live.

| Captured frame | Combined retained bytes before metadata | Complete publication payload |
| --- | ---: | ---: |
| Waveform Dynamics, 4 ribbons x 256 knots + cohorts + bursts + pulse | 82,176 + 65,536 + 262,144 + 1,540 | 416,905 |
| Portable ring, 8 ribbons x 256 knots + cohorts + bursts + pulse | 164,352 + 131,072 + 262,144 + 1,540 | 564,617 |
| DevCurve, all four 96-sample layers, five authored nodes/layer, three specular slots | fixed layer/parameter records | 7,762 |
| Neon Lake, 257 x 257 RG32F extended terrain plus all 48 retained events | 528,392 terrain bytes + event/parameter records | 538,704 |

Every row is exact after codec round-trip through its admitted mailbox. DevCurve's actual solver retains one
previous 96-sample curve per layer; capture publishes the four current curves and no ghost/history arrays
(`devcurve_frame_runtime` explicitly preserves that visual contract). Node counts use the Studio's `node_limits`;
output samples use `DEVCURVE_SAMPLE_COUNT`. Neon uses `HEIGHTFIELD_MAX_SIZE`, canonical heightfield normalization/
packing, and `record_onsets` at its real gap/memory limits to fill `SHOCKWAVE_EVENT_RING`. No foreign byte arrays or
authored preset/default values are substituted for these producer outputs.

Other retained-payload bounds reviewed at source: Spectrum/Extruded Spectrum hold one bars/peaks/ghost array per
admitted bar (schema maximum 96), rather than a frame history; Sphere validates at most four particle cohorts;
Oscilloscope validates at most 16 traces x 384 xy float32 points (49,152 point bytes); Bubble's
`BUBBLE_RENDER_CAPACITY` is 110, with four position + four extra + nine trail floats per hero, plus at most 192
six-float ambient points and 110 four-float occluders. Bubble Ghost reuses that three-sample trail. The shared
sample-consuming frame copies the engine's 256-sample waveform, not its capture-history buffer. EB's larger
geometry/128-step/live-retiring-wake envelope is covered separately above. None of these histories grows with elapsed
playback. The 1 MiB non-EB admission remains sufficient, including the conservative eight-ribbon producer case.

High-water gate: **4 passed** (7.51 s). Its negative control cuts Waveform admission to 512 KiB and rejects the full
portable frame (`564617 > 524216`), exit 1 as expected. Root separately reran the real hidden remap/settings-change
and terminal-failure gates: **3 passed**. This is bounded data/IPC proof only; no new load, rendering, build or device
validation was run.

### H2: admitted child diagnostics and consumed retirement reports

The repair stays at the existing spawn, logging and response boundaries. The parent snapshots its canonical
resolved logging flags, active log directory and native-fault admission into the visualizer factory. The child
applies those flags before readiness and routes module/worker records through the canonical bounded queued writer
to its own rotating `worker_visualizer.log`; it never opens the main process files. Explicitly disabled logging
stays disabled. Native-fault capture reuses `crash_capture` in `worker_visualizer/` beneath the log directory so its
stable descriptor never shares or follows a rotating Python log. The main log names both worker paths.

Retirement sends the same mapping-addressed `VIS_STOP` and closes GUI resources immediately. A detached report
callback captures only immutable session metadata, consumes `report.failed`, revision and final device state, and
logs them in the parent. It owns no Qt object, mapping, lease, retry, timer or worker lifetime. The supervisor's
existing shutdown handoff formerly cancelled callbacks before it directly drained responses; the repair explicitly
retains only logging-only STOP callbacks through that bounded handoff. The final drain delivers them once, and
cleanup cancels a missing report once. Ordinary response cancellation and image-payload disposal stay unchanged.
Only one unanswered STOP callback is retained per visualizer role; a newer STOP cancels the prior completion with
an unavailable warning. Thus a reused worker cannot accumulate callbacks when replies are lost. The report carries
its actual mapping, which must belong to the immutable H1 old/new candidate tuple captured before GUI close.

`tests/test_visualizer_engine_diagnostics.py` has **11 passing focused tests**: actual spawned admitted/ordinary/
disabled profiles and a persisted module traceback; production factory snapshot; parent enabled-to-disabled
re-entry; delayed report consumption after weak-reference-proven GUI link destruction; real STOP then SHUTDOWN;
listener handoff, exactly-once cleanup and the one-report reuse bound. The callback's immutable tuple includes
the H1 old/new mapping candidates; `EngineSession.finish` reports the actual mapping for validation.

Independent Terra 6.1 High source review found one additional issue: superseded late STOP replies entered the
ordinary response buffer, risking unrelated reply eviction. A shared reserved correlation namespace now identifies
detached STOP reports; unclaimed late replies are disposed immediately with no accumulating tombstone history.
The new delayed-old-report regression failed before this correction and now passes, preserving an ordinary buffered
reply exactly. Self-review also caught the existing `--viz` family filter diverting the child-path INFO announcement
from the main log. A chronological process logger now keeps the path and final report in the main file; a real
logging/filter/production-factory subprocess regression failed before the change and now passes.

Five initial focused cases failed before implementation (missing bootstrap and callback-retention API). Two negative
controls fail independently: stripping admission from the real spawned target produces `perf=False viz=False` and
fails the requested-flags assertion; restoring listener-time STOP cancellation delivers `None` before the drain and
fails the retention assertion. Neither negative control changes production files. Focused canonical logging plus
the new tests: **39 passed**; supervisor response/shutdown subset: **12 passed**; worker lifetime/fail-close/lease
subset: **20 passed**; existing native-fault admission/ownership subset: **3 passed**. These checks open no window
or audio device. The child gains the canonical single log writer only when logging is admitted (4096-record bound,
2 MiB rotating file plus five backups); disabled profiles add neither files nor writer. Producers only enqueue;
there is no new frame payload, cadence work or steady-state response traffic. The import-weight regression also
passes (**1 passed**). No default admission, recovery policy, control-queue priority, build, load, frozen, Linux or visual
acceptance belongs to this slice. After the two review corrections the focused H2 file passes **11 tests**.
Terra's limited read-only recheck confirms that reserved-prefix disposal closes its finding and that the
chronological logger avoids the visualizer filter's name/message classification; no new actionable finding. The
independent reviewer did not run tests or native failure/shutdown scenarios.

### Windows worker-default integration

After H1/H2 acceptance, root integrated the prepared `p2/worker-default` tip `3e428413` (code `873b5387`) with current
main. Windows now chooses the engine worker without a token; `--viz-in-process` wins in either argument order, and
Linux remains in process for this slice. The current Linux/default audit order and H1 terminal-capacity exception
take precedence over stale branch prose. The live-check helper retains main's audible-PCM receipt and gate-three
caveats. H1/H2 implementation and contracts remain intact; no later audit finding is declared closed by this merge.

Root's merged-runtime gate: **18 passed, 1 skipped** (Linux-host-only test on Windows), including real default-owner
Spectrum/EB parity without devices or shown windows, H1 hidden remaps/terminal overflow and all eleven H2 cases.
Ten additional current-source platform/token combinations pass for both platform decisions. The two recorded-PCM
receipt contracts and two real main-log fallback checks pass (**4 passed**). The fallback audit found one quiet edge:
new construction after the run was disabled logged only INFO; it now logs WARNING with the mode and run-disabled
reason. Its regression failed before the fix and fails again when downgraded to INFO, because the actual
`--viz`/`--life` main-log routing contains no fallback record. Other automatic fallback edges already warn/error.
H1 capacity violations never take that fallback. Disabled logging admission and recovery policy are unchanged.

These are focused data/IPC/logging checks. No build, load, device, Linux runtime or native visual proof was added;
the remaining ordered audit and operator gates stay in `Current_Plan.md`.

### M2: one first-configure deadline miss per run

M2 retains the existing six-second first-configure bound, including queued startup/import/session work. A miss now
uses the existing disable/fallback owner to leave the worker disabled for this run; later owners/Settings reopens
run in process with a warning instead of repeating the cold wait. Normal, stale, late and retired-owner callbacks
remain fenced by the existing configured/namespace/retirement identities. A fresh process/run resets admission.
No progress protocol, new timer or recovery counter is added. Reveal-latency sizing against in process under load
remains **Awaiting Validation**; this slice makes no claim to increase the first deadline's margin.

The new real-owner regression fails before the repair at `worker_disabled_for_run()`. It now proves fallback,
late callback fencing, no configure retry by a later owner, reset admission for a new run, and stale/normal reply
fences. The negative control restores `count_for_run=False` in memory and fails at the same assertion. Together with
the existing unanswered-configure and half-retired-owner deadline cases: **5 passed**. Terra's focused read-only
review found no additional M2 defect; the reviewer did not run tests. No device/window/build/load gate was run.

### L1: ordered admission and synchronous serialization

CLIENT_RESTARTED_ROLES application sends now refuse a full queue without evicting any earlier edge, and serialize
exactly once before admission. The queue carries inert bytes; the existing visualizer worker loop decodes that
snapshot. Internal heartbeat/shutdown dictionaries and other roles keep their existing consumers/policy. A failed
serialization raises synchronously; queue refusal returns None; both reach the link's existing queued failure event.
No edge waits for a worker reply and no new transport, lifecycle owner or retry is added.

Windows pipe duplication uses the exact supervised process's open Process.sentinel handle, held under the same
supervisor lock as queue admission. The duplicate belongs to that child even if never decoded; child exit reclaims it.
Only a never-submitted duplicate is stolen back/closed through that same process handle; no PID lookup or late close
of a possibly consumed/reused handle occurs. On serialization/enqueue refusal, other Connection reductions locally
remove/close only registrations created by this serialization whose IDs have never escaped. This narrow adapter is
pinned to CPython 3.14's private resource-sharer _id, _cache, _address and registration _lock contract, checked
before registration. Unsupported shapes fail loudly. It never requests detach()/an unbounded sharer handshake,
mutates accepted entries, stops the global service, or assumes its registration lock fences _serve.

**Actionable inherited POSIX orphan finding:** after admission, POSIX Connection transfers retain supported stdlib
ownership. CPython 3.14 Queue._feed already ForkingPickler-serializes the Connection through DupFd, whose
resource-sharer registration owns an os.dup until receiver detach. A worker dying before decode can leave that
sender registration alive. Serializing once before put creates the same single registration earlier, widening the
exposure window before the old feeder would have serialized it; inert bytes create no second registration. This
slice does not resolve that orphan class. A future bounded POSIX transfer-lifetime design must handle already-pending
service requests; private accepted-entry pop is unsafe because _serve pops without the registration lock. No ACK
protocol or global service cancellation is added. Linux actual execution remains unproven on this Windows host.

The initial full-queue/unpickleable tests fail on the baseline. Focused proof covers real BaseWorker wake transfer,
unshown link failure delivery, one payload reduction through the real queue feeder, other-role dictionaries, repeated
Windows refusal rollback, accepted-unread child death with parent handle count, actual socket-sharer rollback leaving
unrelated IDs, pure adapter idempotence/address fencing, and unsupported shape refusal. Terra independently verified
the baseline/candidate source distinction and found no additional concrete defect in the final narrow delta; that
read-only review did not rerun tests. The final focused L1/supervisor/H2/M2 gate is **67 passed** (17 new L1 cases),
independently rerun by the lead with the same result.
In-memory negative controls restore baseline send (both ordered/refusal checks fail), sender-owned duplication
(worker-death handle count grows), and skipped rollback (all four refusal-cleanup checks fail). Compilation of the
four changed/new Python files and scoped whitespace checks pass. No build, load, device, render or Linux runtime
proof was run.

### 11 Nov: M4 remainder, M5, L2-L5, the POSIX transfer lifetime (and R-184, R-185 found on the way)

Branch `worktree-agent-aa1e054152572db80`. No load, device, build, installer or Linux run was made for any of it;
every live reading is the invisible saver without load on recorded music, three minutes at most. Records with the
tables: `Native_Core_P2_Engine_Design.md`, "11 Nov reconciliation".

**M4 (rendered parity on the production owner, non-default settings; gate 2's record).** `af133dee`, `791b17ab`.
`tools/visualizer_replay/owner_render_parity.py` runs the real owner (the host binding's, on an unshown runtime) on
both paths over the same recorded inputs, mirrors each presentation into the production `DisplayScene.qml` drawn into
a hidden texture, and compares the card's pixels of every drawn frame. Settings: every Slider, Range, Choice, Toggle
and colour of the mode and of its switch partner moved off the shipped defaults, in two different variants, with the
custom preset. The script: play, a warm pause, a park and resume, a mode switch through the owner's crossfade to the
mode's partner and, where the mode has them, a reflected photograph and a held-key orbit. A same-mode preset
activation is not in it (the logical gate `identity_script_view` has one; its pixels were not drawn).
- *Logical frames:* identical on both paths for all nine modes in both variants; every run stayed on the worker.
- *Pixels, scene targets single-sampled:* exact for all nine modes in both variants (549 drawn frames each; 0 frames,
  0 pixels, 0 levels differ). Controls in the same run: the in-process run repeated is exact, and a 20% nudge of the
  mode's non-integer Sliders changes 296 to 542 of the 549 frames, so the comparison sees a drift.
- *Pixels at the product's sampling:* reported beside the in-process run repeated, not judged. A multisampled scene
  target is not reproducible draw to draw on this GPU (the same retained snapshot redrawn differs by one 8-bit level on
  about 1,200 of 390,931 pixels in Neon Lake; unchanged with bloom off, shafts off and a `glFinish`; zero with one
  sample), so the two paths differ from each other by as much as one path differs from itself. Frames / largest pixel
  count / largest level, paths against repeat: Spectrum 1/1/1 against 0; Oscilloscope, Bubble, Extruded Spectrum 0
  against 0; Spline Curve 52/1543/2 against 52/1645/2; Sphere 45/20/1 against 39/35/1; Neon Lake 359/3318/2 against
  359/2571/1; Waveform Ribbon 15/55/1 against 22/49/1; Extruded Bubble 7/2/1 against 9/2/1. The stage that varies is
  the mode's own passes into the multisampled attachment; the GPU-side cause below that is not attributed.
- *The defect it found:* **R-184** (`4380d73e`), the first time the two paths' pixels were compared. Fixed; the
  per-mode test fails without the fix for the three modes whose switch changes the layout profile.
- Tests: `tests/test_visualizer_owner_render_parity.py` (per mode, single-sampled, exact),
  `tests/test_qtquick_visualizer_item.py`. Evidence: `.artifacts/evidence/native_core/20261111_m4_rendered_parity/`
  (in the agent's worktree until merged).
- *Not covered:* BTF checks were not rerun (the gate compares the same drawn frames on both paths instead); Expanded,
  full-display and mixed-DPR extents; load.

**M5 (memory over mode switches).** `dd49377a`. The premise does not hold on current source: the growth is a
first-lap high-water in the rendering process, on both paths, with no lap-to-lap trend.
- *Reading (invisible saver, nine-mode cycle, memory maps at each switch):* in process over three laps, the same
  mode's private bytes from lap 1 to lap 2: +177, +141, +144, +137, +137, +108, +61, -46, -5.5 MB; from lap 2 to lap 3:
  -5.4, +2.8, -9.5, -9.9, -9.2, -6.9, +11.0, +31.6, +3.7 MB. On the worker path main shows the same first-lap step
  (+186, +166, +160, +139, +132, +116, +25, -2, 0 MB).
- *What it is:* `private_other` (the GPU driver's VirtualAlloc, largely not resident) +90 to +117 MB, heaps +15 to
  +20 MB, arenas +14 MB, and one `heap_large` block of 26.6 MB at the first Neon Lake that stays for the run (not
  attributed, not growing). Each mode's GPU resources are created at its first visit and kept; the second visit adds
  none. An offscreen in-process cycle with no drawing is flat after its first lap, so the logical side holds nothing.
- *What was wrong:* the instrument. The series verdict judged the whole run's slope, which the first lap dominates,
  and the 8 Nov control compared only two laps. `tools/live_check_resources.py` now judges each mode from its second
  visit (`growth_by_mode`: the first step is reported, never judged). The map files were also being written to NTFS
  alternate data streams (`memory_map_switchN:mode.json`, empty on disk); fixed.
- Tests: `tests/test_live_check_resources.py`. Evidence:
  `.artifacts/evidence/architecture/native_core_p2/20261111_m5_*`.
- *The `heap_large` block at the first Neon Lake, attributed (later 11 Nov):* the Python tuple of the basin's triangle
  coordinates, `basin_mesh_vertices` (`rendering/gl_programs/neon_lake_basin_mesh.py`), which its `@lru_cache(maxsize=8)`
  (since `aec1fa40`, 14 Oct) keeps after the renderer has uploaded it: 22.57 MB for the Guided Setup preview's 189 x 126
  cells (2,958,732 floats; one default-heap block), plus `basin_mesh_points`' 1.90 MB tuple in the same cache (M5's 26.6
  MB is the same entry at that run's cells). Offscreen production render host, 1920x1080: it appears at the first draw,
  stays when Neon Lake leaves and after `release_resources()`, and a second visit adds nothing (a cache hit). New with
  `33912e5a` (1B.5): the key carries the painted `reach`, so each distinct reach caches another, larger entry (23.69 MB
  at -0.3..1.3, 30.29 MB at -0.6..1.6), up to eight kept; the plain entry is unchanged by it. The renderer already holds
  the uploaded mesh by key (`_mesh_cells`), so the cache saves nothing per frame; dropping it (or keeping one entry, or
  building a float32 array the upload takes directly) is Neon Lake terrain work, left to its owner. Evidence:
  `.artifacts/evidence/native_core/20261111_attribution/neon_main_memory_traced.json`.
- *Open:* the Studios' in-process cycle and the fallback after a worker failure were not measured separately; they use
  the same render path and the same in-process tick that the offscreen cycle showed flat.

**L2 (gate 3's labels).** `091b9eea`. `tools/visualizer_live_check.py`'s fields say what they measure:
`tick_wall_share`, `main_wall_share`, `worker_tick_wall_share`, `logical_tick_wall_share` (wall time per tick times
the rate), beside `main_cpu_share` from the step's own thread CPU time (`time.thread_time()`), which waits do not
inflate. `revisions_waiting_at_sync` is None on the worker path with a note (untaken frames are never recorded there),
and `audio_delivery` names how the audio reached the tick (the worker's paced recorded blocks against the in-process
loopback thread). The 8 Nov records keep their numbers; read "GIL share" there as wall share. No new measurement.

**L3 (`--usage` cost with the worker).** `2fbf83e3`. Cause: `psutil.Process.memory_full_info()` (USS) walks the
process's working set with the GIL held, 3.0 to 4.4 ms for the main process's ~670 MB working set, once per process per
sample; a spinning Python thread made no progress during it. `core/performance/windows_working_set.py` reads the same
value through `K32QueryWorkingSet` (the GIL released for the call, one kept buffer, cached process handles); the
values equal psutil's. Measured as the longest stall of a spinning thread inside each call: psutil's walk stalls it
for 97 to 100% of the call (2.1-2.5 ms with 256 MB more resident, 5.4-7.7 ms with 768 MB, 29-33 ms with 1.8 GB), the
reader for 0.1 to 1.7% at the same wall time. Tests: `tests/test_usage_sampler.py` (the collector never runs psutil's
walk; a thread keeps running through the read: judged by that stall share, after the first form of the test, which
judged the spinner's progress, failed in a large test process for a reason of its own). *Not verified:* `collect_ms` under
load, and with the displays on: the one live reading after the fix was taken with the operator's displays asleep
(13.5 to 21 ms for four processes, the Visualizer parked).

**L4.** `8117d0e6`.
- *Wake listener:* measured, no change. 18.7 us median (p90 31.8, p99 108) per publish at 90 Hz with an idle GUI, 2.9
  us with a wake already pending; about 0.2% of main's time.
- *Qt-typed presentation inputs:* a colour is forwarded as the `(r, g, b, a)` the in-process capture freezes it to;
  any other Qt value, top level or nested, is refused with one error per attribute, never pickled to the worker and not
  retried each presentation. No shipped control holds one today (the presentation config stores plain tuples).
- *Frame-stream liveness:* the worker's heartbeat handler asks the session; two heartbeats at least a second apart with
  the cadence running, not parked and not one step further fail the session closed (the existing path: wake pipe end,
  the owner's recovery, the reason in the stop's reply and so in the main log). The session's delivery watch could not
  host this: it runs on the cadence step, which is the thing that is blocked. No timer, thread or polling was added.
  *Residual:* the blocked thread itself stays in the worker process until it returns; a replacement session that
  blocks the same way is the second strike (in process for the run), and a message loop that blocks with it is the
  heartbeat's existing retirement.
- Tests: `tests/test_visualizer_engine_worker_cadence_liveness.py`,
  `tests/test_visualizer_owner_engine_worker_inputs.py`.

**L5 (records against evidence).** In the design doc: the gate 4 worker row now says what was re-read (below), the
writer's slot choice is stated as the code has it, gate 2 has its record, and gate 3's field names carry the L2 note.
`tests/test_visualizer_engine_import_weight.py` is listed in `Docs/TestSuite.md`.
- *Gate 4's worker memory, re-read 11 Nov with R-179 fixed (source, private bytes at each switch):* 63.5 MB with
  Spectrum, 65 to 70 MB through the first Extruded Bubble, 103.9 MB at the first Waveform Ribbon, then 101.5 to 104.7
  MB across the whole second lap (RSS 79 -> 89 to 92 MB). So the 8 Nov row's shape (a step, then flat) was not the
  codec sawtooth, and it is not growth. Frozen check 2's 46 to 59 MB is USS, a different measure.
- *The step at the first Waveform Ribbon, attributed (later 11 Nov):* the worker's tick host (`EngineSession`, live
  inputs, production order) in a fresh QtCore-only process with the product's one-thread OpenBLAS policy reproduces it:
  private 89.5 MB with Spectrum, 90.8 after Extruded Bubble, 126.4 at the first Waveform Ribbon (+35.6), then 126.4 to
  127.1 over a second lap; RSS +4.9 MB, tracemalloc +1.3 MB. The memory map names it: one new 32.0 MB `private_other`
  allocation, committed and not resident, plus numpy.random's extension images (+2.0 MB, imported by the Waveform
  runtime) and +2 MB of arenas. The 32 MB is OpenBLAS's work buffer, committed by the process's first level-3 BLAS call
  and never released (measured alone: `ddot` and `dgemv` commit nothing, the first 4x4 `@` 4x4 commits 32 MB); the first
  such call in the worker is Waveform's logical view (`core/waveform_ribbon_view.py`, `projection@view`). It is a
  one-time library buffer, not a cache and not geometry: P3's D3 should not size against it. Avoiding it would mean no
  float64 matrix-matrix product in the worker's ticks (a 4x4 product written out); not done, the commit is non-resident.
  Evidence: `.artifacts/evidence/native_core/20261111_attribution/worker_memory_by_mode.json`.
- *The frozen wording:* frozen check 2 already shows the engine worker on `qt6core.dll` only, flat USS and a Settings
  retirement and respawn. What still awaits the operator is the next product frozen build's ordinary acceptance (the
  build log and audit lines), not a new worker proof.

**The POSIX transfer lifetime (L1's inherited finding).** `8c7ffa09`. No ordered control creates a resource-sharer
registration any more: a sharer-backed `Connection` or socket is refused before anything is registered, and the
session's wake pipe on POSIX is a named pipe whose name crosses and which the session opens itself
(`core/visualizer_engine/wake_channel.py`). The link holds its reader, its own writer end and the name until the
configure's reply; its `close` gives back whatever it still holds. A worker that dies before decoding its configure
therefore leaves nothing: there is no accepted registration to cancel, no service to ask and nothing to wait for. The
CPython 3.14 private-cache rollback adapter is removed with the registrations it rolled back; Windows' child-owned
`DuplicateHandle` path is unchanged and keeps its tests. Tests: `tests/test_visualizer_wake_channel.py`,
`tests/test_visualizer_ordered_control_delivery.py`. **Linux runtime is unverified:** the POSIX branch is proved only
for ordering, rollback and ownership with its system calls injected; no FIFO, forkserver, POSIX wake or Linux worker
has run, and the listener's end-of-file behaviour on a FIFO is taken from the POSIX specification, not from a run.

**R-185 (found while running L4's focused files).** `cb9ee76a`. A killed worker still read as running for 5 to 34 ms,
the owner's recovery landed in that window, and since L1's synchronous handle transfer the replacement's configure
raised instead of being queued and resent: one worker death turned the worker off for the run. The existing
real-process test for it was red. Fixed in the supervisor (`process_has_exited`).

**Dormancy after these changes (`tools/overhead_baseline.py`, 1920x1080, against `2026-11-07_4bb2b775.json`).**
Conditions: other processes' CPU 22% median (the reference: 3.4%), GPU busy 24%, 109 of 125 passes admitted, so only
the deterministic counts are read. GL calls: no rise in any case. Python calls: 20 rows rise, +4 in each Scene3D
transition (Blinds 3D Slats 668 -> 672 and thirteen like it) and +5 to +32 in six Visualizer modes (Waveform Ribbon
6987 -> 7010, Extruded Bubble 6395 -> 6427); the node path (1216), the surfaces and every other transition and mode
are not higher. **None of it
is this work's:** of the product modules these commits change, the baseline loads three, and none adds a call on a
measured path (`rendering/quick/visualizer/item.py`: two attribute reads in `updatePaintNode`;
`widgets/spotify_visualizer/logical_runtime.py`: a property nothing here calls; `core/process/supervisor.py`:
imported, no worker runs). The rises entered between 7 Nov and this branch's base (`630a5729`) and are not attributed
to a commit here: that needs a baseline at the base, which was not taken. Evidence:
`.artifacts/evidence/native_core/20261111_overhead_baseline/`.
*Attributed later on 11 Nov* (per-function call counts at chosen commits; `4bb2b775` is `81959727`'s tree on the
rewritten history): `f6328336` (Scene3D content rotation: +4 on every Scene3D transition from the target's output
frame, +5 to +7 on the Scene3D modes), `0afc19cb` via `f23dcab1` (Extruded Bubble's per-frame optical height: +26,
with a function-level import) and `50a43e0d` (Waveform Preset 1's Left To Right travel engages the mirror path: +16,
authored content). The first two and the mirror's per-frame `np.diag` are fixed with call-counting tests; the re-recorded
baseline is `tools/baselines/overhead/2026-11-11_4658981b.json` (`Docs/Reference/Benchmarks.md`, "Recorded sessions").

### H3: the Linux worker-default source flip

The operator waived this finding's Linux proving prerequisite (8 Nov: no Linux machine), so H3's fix is the source
flip, not a Linux run. `experiment_flags.visualizer_engine_worker_platform_default()` answers the worker on every
platform (it returned `IS_WINDOWS`); `--viz-in-process` / `--viz-engine-worker` choose as before, and the in-process
fallback on a failed wake pipe, start or configure (logged at WARNING with its reason) is the safety net. The
selection is pinned by `tests/test_platform_selection.py` with the platform injected both ways (the non-Windows case
fails on the pre-flip function) and by `tests/test_linux_runtime_branches.py` on Linux;
`tests/test_visualizer_owner_production_path.py` is no longer gated to Windows. The tests that send a wake pipe
through a real supervisor use `wake_channel.open_wake_channel` (a raw pipe end is refused on POSIX).
**Linux runtime is UNVERIFIED:** no FIFO, forkserver spawn, Pulse capture in the worker or Linux worker has run;
on Linux the wake listener ends only when the worker's writer closes. Every proof here is source correctness and
Windows-run unit tests (`Linux_Plan.md`, Phase 4).

## P3 readiness

What ABI 2 already gives the native core:
- C-readable little-endian header and slot heads with 16-byte payload alignment.
- A seqlock whose store and load order is documented and tested (C2, A4-L1).
- The slot's own identity (runtime and engine generation, activation, `mode_code`) under the seqlock, so a native
  reader validates a slot without Python.
- Flags and the source and logical timestamps on one shared clock (`perf_counter`, which is QPC on Windows; checked
  that `authored_now` uses it).
- An append-only `MODE_CODES` table, version refusal, and slot size taken from the header.
- The worker and the main side already agree on everything except the payload. Under 4V the payload is P3's per-mode
  fixed layout.

Traps to decide before P3's first slice:

1. **The mapping's lifetime against a native reader (Medium for P3).** Today the GUI thread's `link.close()` releases
   and unlinks the mapping (`packet_mailbox.py:373-392`). The render thread's `take()` serialises with it only through
   the mailbox's Python lock. A native reader on the render thread takes no Python lock: a recovery or retire that closes
   the mapping mid-copy is a use-after-unmap crash. Define the quiescence: render admission closed and a render-thread
   fence passed before the unmap, or a refcount owned by the native core.
2. **Single consumer (Medium for P3).** `consumed_sequence` and `accepted` assume one reader. The owner still needs
   per-frame facts on the GUI thread: `waiting_target`'s presentable and identity check, recovery pacing, fades and
   presentation. Today it gets them by `peek` and `take`, which decode the whole frame. Once the native core consumes
   at sync, the Python side needs a head-only peek that never acknowledges. Today's `peek()` decodes and caches. Decide
   which side acknowledges, or two readers will starve each other.
3. **Per-frame immutable geometry (Medium for P3).** See M1. A fixed layout that copies Extruded Bubble's drift
   geometry each frame inherits H1's size problem. Geometry keyed by a revision belongs in a side record uploaded once
   per revision. A host-visible buffer copy per frame should carry only state that changes.
4. **"QRhi-portable compute" is more than uniform blocks (Medium for P3).**
   - Extruded Bubble's drift solver is fp64: `double` storage buffers, a uniform `double`, `shared double` and `LF`
     literals (`extruded_bubble_drift_solver.py:39-92`). On Vulkan that needs `shaderFloat64`, on D3D12 the
     double-precision option. Neither is universal: Intel Arc and most mobile and Apple GPUs lack native fp64.
   - QRhi exposes no fp64 feature query. `qsb` compiles fp64 SPIR-V happily, so the readiness ratchet cannot see this.
   - The ratchet also scans a fixed module list (`tools/vulkan_shader_readiness.py:26-32`). A new compute shader in a
     new module escapes "every other compute shader must compile". Discover sources instead, for example every module
     that imports the compute compile helper.
5. **Smaller ABI points (Low).**
   - `payload_schema` is one namespace, and today it is always `CODEC_SCHEMA` (1) for the tagged Python codec. Reserve
     1 as "Python-only, C readers refuse" and number fixed layouts per mode.
   - `publish_ns` is 0 at rest by design, so P3 must not build pacing on it unless it becomes always-on (about 100 ns
     per publish).
   - The protected-edge mask is `crc32(kind) % 32`, so collisions are silent. Use an append-only edge-code table like
     `MODE_CODES`, and carry the edges' results in the fixed layouts.
   - A header `reading_slot` written by the reader would let the writer skip the slot in use (a true triple buffer),
     so a slow native copy never tears.
   - Store order relies on x86 TSO and on CPython's native 8-byte `struct` stores. Document the target as x86-64, or
     give the Python writer explicit fences if ARM64 ever ships.
   - The main-side frame completion (the reflected wallpaper, run in Python where the frame is decoded) needs a
     non-Python route for Sphere and Extruded Spectrum: a texture from the GUI side.

## Verified sound

- **Seqlock and identity.** The writer stores the odd `sequence_begin` in its own store, then the head, payload, even
  begin, end and `latest`. The reader loads end, then the copy, then begin, and accepts only `latest`, even, with end
  equal to begin. The identity lives in the slot head, under the seqlock.
- **Wake pipe and failure delivery.** The writer sends one wake byte per publish across processes. A full pipe drops
  the byte without blocking (an overlapped write cancelled, `ERROR_OPERATION_ABORTED` tolerated). The listener drains
  while the GUI is blocked, and a closed receiver ends it quietly. Replies are matched by correlation, failures are
  always events, and the configure is resent once to a restarted worker.
- **Lifetime.** Leases and holds are fenced under one lock and serialised with starts (`_start_lock`). Recovery swaps
  links inside one GUI turn and keeps the worker. A spawn whose link closed retires the worker it started. Gate 4: one
  worker and one mapping at most, retired at every Settings open, no handle, thread or Section growth, the
  Visualizer-off run identical.
- **Recovery bounds.** Failure handling holds the last frame and fades it (never vanishing). There is one reconfigure
  per strike, at most 3 recoveries per run, and staged deadlines with their own serials (A8-M1 and A8-M2 hold). The
  fallback in process is contained. A park drops the held frame.
- **Device watch (5.3).** It is a count on the cadence step, never raises into the step, and a device failure is never
  a session failure. Tests pass, with stand-in negative controls.
- **Frozen.** A10-M1 holds: in frozen check 2 the engine worker mapped `qt6core.dll` only, and the image workers
  `qt6core` and `qt6gui`. R-179 is fixed (worker USS flat at 46-59 MB across Waveform Ribbon and Extruded Bubble). A
  Settings round trip retired and respawned the worker. The CUSTOM reload hold kept the worker. Two displays.
- **Gate 3's GIL result.** Main's per-frame Visualizer occupancy dropping 0.85 → 0.08 is structural: the tick left the
  process. CPU was matched (system CPU 87% on both, reconstructed from `--usage`). The record states its limits
  honestly (GPU state, audio content, n=1).
- **Gate 4 lifecycle.** The gate 4 record's lifecycle claims match its per-cycle tables. Reveal time after Settings
  with the worker on (total 6.65-6.90 s) is no worse than off (6.95-7.17 s).
- **Clock.** The authored clock and `publish_ns` share QPC across processes, so the view records and frame times line
  up between processes.
- **Supervisor heartbeat.** It only retires `CLIENT_RESTARTED_ROLES` and is fenced by process identity. The image
  roles' restart is fenced the same way.

## Not verified

- A real audio device in the worker under load. The live checks always refuse the device. Not checked: the
  PyAudioWPatch GIL hold in `Pa_Initialize`/`Pa_Terminate` (A11-L6), and the 5.3 physical checks.
- Linux in any form (H3): forkserver, Pulse on a sink change, the POSIX wake, the resource tracker with an attached
  `SharedMemory`. The worker is the Linux default at source level since the H3 flip; none of this has run.
- Mixed DPR. Frozen check 2 had two displays, but their DPRs are not recorded. Not checked whether any mode's payload
  grows with the extent (Expanded or full display at 4K); the probes used the default card.
- Whether payloads outside Extruded Bubble can exceed the slot through non-Slider/Range controls (Choices,
  resolution tiers). The probe set Sliders and Ranges only.
- An end-to-end worker session reproducing H1. Shown by the payload measurement, the real mailbox's refusal and the
  code path, not by a running worker.
- Renderer-side caches keyed on (engine generation, activation id) when a recovered session reuses `0/0`.
  `_bind_replacement` closes admission; no renderer cache was audited.
- The in-flight default change itself (not on `main`).
- The liveness and inputs owner suites and the whole-clip gates were not re-run here (timing and load).
