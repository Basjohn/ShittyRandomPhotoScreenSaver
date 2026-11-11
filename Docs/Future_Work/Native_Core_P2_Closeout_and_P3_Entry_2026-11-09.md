# SRPSS | Native Core P2 closeout and P3 entry plan

**Status:** actionable source-verified plan, 9 November 2026. **Source baseline:** `main` `9872ca18140c490ed018c42511803005fb3d8ed4` (15:06 SAST). **Authority:** `Current_Plan.md` §1 item 8b, `Docs/Future_Work/Native_Core_P2_Phase_Boundary_Audit.md`, `Docs/Future_Work/Native_Core_P2_Engine_Design.md`, `Docs/Future_Work/Graphics_Backend_Decision_2026-11-05.md`. This plan records the accurate *built versus accepted* distinction; it does not retrospectively claim unrun load, GPU, audio-device or Linux gates.

## 0. Decision and boundaries

The **Windows production Visualizer worker is operational and default**. P2 is not an unimplemented project; its principal capture/DSP/tick migration, IPC, supervision, recovery and frozen proof exist. Finish open defects at their owners before P3 makes the IPC/mapping contract native and more expensive to repair. Maintain the explicit `--viz-in-process` comparison/fallback and `--viz-engine-worker` diagnostic choices. A capacity violation is terminal for that activation, not a silent in-process fallback. P3 is **one native QRhi rendering core for all custom rendering**, including transitions and compositor image/background surfaces, not a Visualizer-only library and not a second renderer maintained indefinitely.

A completed implementation task, a focused test, a full acceptance test, a live operator look and a native/frozen build proof are five different statuses. Close exactly what the evidence demonstrates. If implementation and tests landed before the plan was updated, mark them landed and list only the missing acceptance as open.

## 1. Reconciled P2 status on the baseline

*9 Nov baseline (`9872ca18`), kept as written: M4, M5, L2-L5 and the POSIX transfer lifetime have since merged
(`1af42104`, see §2 "11 Nov status"), and H3's Linux source flip merged on 11 Nov (`6c2039b3`).*

| Work | Source-verifiable status | Remaining distinction |
| --- | --- | --- |
| P2 ABI, frame codec, mailbox; in-process loopback | **[x] Implemented** in `core/visualizer_engine/{packet_abi,frame_codec,packet_mailbox}.py` | Preserve bitwise identity and seqlock ordering in P3; Python tagged payload is **not** yet a native per-mode payload. |
| P2b worker owns loopback capture, DSP, cadence and logical tick | **[x] Implemented** in `core/visualizer_engine/engine_worker.py` | Physical audio outputs/device changes still await operator validation. |
| Windows worker as no-token default | **[x] Merged 9 Nov**, `9362fa429753`, `core/diagnostics/experiment_flags.py` | Linux default not flipped; user-approved Linux proving waiver does not establish Linux execution. |
| H1 frame capacity | **[x] Implemented and focused-tested**, `881ba95c13c`, including high-water, non-default and schema-maximum frames and hidden activation remaps | Do not confuse capacity coverage with M4's full replay/render-parity gate. |
| H2 child diagnostics and detached STOP report | **[x] Implemented and focused-tested**, `87143243593b` | Keep frozen logging/error evidence distinct from focused tests. |
| M1 Extruded Bubble CPU/reference publication boundary | **[x] Implemented and focused-tested**, `5d8b98ff875a` | Source-free immutable geometry **still travels per frame** in P2; P3 needs separate revision-scoped geometry upload. |
| M2 first-configure bounded failure | **[x] Implemented**, `5a7f8339606d` | First-reveal latency compared with in-process under approved load remains unmeasured. |
| L1 ordered control serialization/admission, Windows transferred-handle ownership | **[x] Implemented with focused negative controls**, `9c1bd9b3384f` | Accepted-unread POSIX resource-sharer descriptor lifetime remains open. |
| Run-bounded worker recovery; stale stream reopen | **[x] Implemented** and simulated in `engine_worker_link.py`, `engine_worker.py`, `tests/test_visualizer_engine_worker_device.py` | Physical endpoint and crash timing still unproven. |
| Gates 3/4 and frozen proof | **[x] Recorded**, 8 Nov: game60 structural main occupancy gain, gate-4 lifetime and frozen QtCore-only check | 8 Nov gate 3 was **not GPU-matched**; its 'GIL share' metric is wall-time occupancy, not a direct Python GIL profiler. Next *product* frozen build acceptance remains an operator check. |
| M4 broader no-visual-change parity | **[~] Substantial fixtures landed**, `tests/test_visualizer_engine_frame_capacity.py`, owner and PCM identity gates | A recorded parity matrix varying presets and independent Settings *on both owner paths*, plus the gate-2 rendered evidence, remains open. |
| H3 Linux worker default | **[ ] Open**: `visualizer_engine_worker_platform_default()` returns `IS_WINDOWS` | Source update/tests needed; runtime forkserver/POSIX wake/Pulse capture unproven. |
| M5, L2-L5, accepted POSIX transfer lifetime | **[ ] Open or only partly instrumented** | See §2; do not close from older audit prose or adjacent repairs. |

Evidence already in design/audit: 160 replayable (recording,mode) pairs, 291,024 matching frames; default production owner identity tests; fixed capacity up to 8,063,616 bytes/slot for maximum Extruded Bubble; first-spawn speed and memory improvements; frozen engine-worker USS roughly 46–59 MB. Read their method and limitations before restating numbers.

## 2. Ordered remaining P2 work: fix debt before making native consumers

**11 Nov status (audited and merged to main with `1af42104`).** P2-C1's rendered parity and gate-2 record, P2-C2's
memory reading, P2-C3's L2-L5 and P2-C4's POSIX transfer lifetime each have their record, tests, negative controls and
what remains unverified in `Native_Core_P2_Phase_Boundary_Audit.md`, "11 Nov". Two defects were found and fixed on the
way: R-184 (the worker path kept drawing the outgoing frame after a profile-changing fade-out; found by the first
rendered comparison) and R-185 (a worker being torn down still read as running, so one worker death turned the worker
off for the run). Still open from this section after that work: P2-C1's failed high-water admission and load check;
P2-C2's lease/hold exactly-once sweep and the Studio/fallback memory readings; P2-C3's last bullet (a target that never
reveals, the framed-view control, Random Group Drift); H3 itself (in flight). No load, device, frozen or Linux run was
made.

### P2-C1. M4, actual non-default identity and rendered parity

- Landed (`af133dee`, `791b17ab`): the real production owner is gated worker-versus-in-process, independently altered
  Settings in every mode with switch/reconfigure, park/resume and the same recorded PCM
  (`tools/visualizer_replay/owner_render_parity.py`, `tests/test_visualizer_owner_render_parity.py`). The schema-max
  capacity tests are retained.
- Landed (`af133dee`, `9a4007de`): packet identity, rendered pixels (single-sampled, exact) and generation/remap identity
  are recorded separately, with negative controls that fail on a drift; gate 2 has its record. BTF checks were not rerun
  there.
- [ ] Verify failed high-water admission preserves last good frame without silently changing the worker path. Run load only after operator approval per `Current_Plan.md`.

### P2-C2. M5, memory and lifecycle

- Landed (`dd49377a`): the in-process mode-cycle reading shows a first-lap high-water in the rendering process on both
  paths with no lap-to-lap trend; the instrument now judges each mode from its second visit
  (`tools/live_check_resources.py`, `tests/test_live_check_resources.py`).
- [ ] Measure the Studios' in-process cycle and the post-failure fallback separately (RSS/private/USS, native allocations, GL and handles under a stable comparison); repair at lifetime owner, not via periodic trimming or disabled checks.
- [ ] Verify leases and holds release exactly once across Settings, mode switches, worker death, failed reload and a Visualizer-off run. Keep the bound of one worker/mapping and zero worker cost while disabled.

### P2-C3. L2-L5, observability, liveness and truthful results

- Landed (`091b9eea`): **L2** the live check names what it measures (`tick_wall_share`, `main_wall_share`, `main_cpu_share`), marks the worker's 'revisions waiting' row as vacuous and names how the audio was delivered (`tools/visualizer_live_check.py`).
- Landed (`2fbf83e3`): **L3** the `--usage` extra cost was the GIL-held working-set walk; the sampler reads USS through `core/performance/windows_working_set.py` with the GIL released (`tests/test_usage_sampler.py`).
  - [ ] L3 remainder: `collect_ms` with the displays on and under load, in an operator-approved session.
- Landed (`8117d0e6`): **L4** the wake-listener cost is measured, a blocked cadence thread fails its session closed at the worker's heartbeat, and a Qt-typed presentation input goes plain or is refused loudly (`tests/test_visualizer_engine_worker_cadence_liveness.py`, `tests/test_visualizer_owner_engine_worker_inputs.py`).
  - [ ] L4 residual: the blocked thread itself stays in the worker until it returns.
- Landed (`9a4007de`): **L5** the design doc's gate 4 worker row, writer slot choice, gate 2 record and gate 3 field names are corrected, `tests/test_visualizer_engine_import_weight.py` is in `Docs/TestSuite.md`, and the frozen wording names what still awaits the operator (the next product frozen build's ordinary acceptance).
- [ ] Bound a target that never reveals and the failed reload/reconstruction loop without endless repeated attempts. Independent framed-view negative control and Random Group Drift semantics remain explicit targeted follow-ups, not silently closed.

### P2-C4. POSIX accepted-transfer lifetime before Linux worker default

- Landed (`8c7ffa09`): no ordered control creates a resource-sharer registration any more; a sharer-backed `Connection`
  or socket is refused before registration, and the POSIX wake pipe crosses as a name the session opens itself
  (`core/visualizer_engine/wake_channel.py`, `tests/test_visualizer_wake_channel.py`,
  `tests/test_visualizer_ordered_control_delivery.py`). A worker that dies before decoding leaves nothing to cancel.
  The CPython 3.14 private-cache rollback adapter is removed; Windows' child-owned `DuplicateHandle` path is unchanged
  and keeps its tests. Linux runtime remains unverified (no FIFO, forkserver or Linux worker has run).
- [ ] **H3 Linux default after source-level POSIX closeout:** flip only the canonical `visualizer_engine_worker_platform_default` owner, its platform tests and `Linux_Plan.md` Phase 4. Maintain explicit in-process override and reasoned fallback. The operator's 8 Nov waiver means no fabricated Linux runtime acceptance; label forkserver, shared-memory tracker, wake pipe, Pulse/parec capture and real-device tests **unverified**, and retain a follow-up validation gate when a Linux machine is available.

**Priority:** P2-C1, P2-C2/C3, P2-C4 and Linux H3; then P3's four decisions and core. Independent P3 design can be drafted during C2/C3, but native reader publication/teardown must not ship against an unresolved mapping lifetime.

## 3. P3 preflight: four required architecture decisions

- [ ] **D1. Native reader versus unmap:** a render-thread native reader must pin its mapping or be fenced by explicit render admission closure and a render-thread quiescence barrier before GUI close/recover/unlink. Python `PacketMailbox.take()`'s decode lock does not protect native code. Test adversarial close-during-copy, resize/remap, retire and worker replacement. The test should crash or trip a deliberate assertion without the lifetime contract.
- [ ] **D2. One consuming reader:** the native render core alone acknowledges presented frames/edges; the GUI/main owner reads only a non-consuming slot head/identity for fades/recovery/availability. Never add a second reader that consumes, decodes whole payloads, or steals edges. Define exactly when the protected-edge state is acknowledged.
- [ ] **D3. Extruded Bubble geometry revisions:** send immutable render geometry once per `(worker namespace, engine generation, activation, geometry revision, capacity)` and small mutable per-frame state separately. Do not use bare revision as a global identity; prove retention/release on geometry changes, failed swaps, GPU upload failures and native teardown. Keep CPU-only oracle data off the wire.
- [ ] **D4. Backend capability and shader inventory:** `shaderFloat64` / D3D double precision is not universally available and Qt QRhi has no universal FP64 feature query; decide a typed capability/fallback for Extruded Bubble's FP64 drift solver before porting it. Have `tools/vulkan_shader_readiness.py` discover new compute sources instead of accepting a fixed import list. Add fixed-layout per-mode native schemas; reserve the tagged Python codec namespace and make unsupported payloads fail explicitly.

**Inputs to these decisions from the 11 Nov P2 work:**
- *D1/D2, a retained frame needs its own drop edge.* R-184: the Python render node kept drawing a frame the owner had
  discarded, because the discard reached the bridge and not the node's retained copy, and the identity had not changed
  yet. A native reader that holds its last frame (a copy, a texture, uploaded geometry) needs an explicit "drop what
  you hold" edge beside the mapping's contents and lifetime, and the non-consuming head read must not be able to
  resurrect it.
- *Parity oracles for the native substrate must be single-sampled or repeat-relative.* A multisampled scene target is
  not reproducible draw to draw on the development GPU (one 8-bit level on roughly 0.3% of a Neon Lake card's pixels
  between two draws of the same snapshot). `tools/visualizer_replay/owner_render_parity.py` is exact with one sample
  and is the ready oracle for Spectrum-first parity: point its mirror at the native item. Waveform Ribbon asks for 4
  samples whatever the tier (`rendering/quick/scene3d/waveform.py`), so a tier table alone does not single-sample it.
- *D1, liveness is per stream, not per process.* A worker whose message loop answered heartbeats while its cadence was
  blocked froze the Visualizer unseen (L4). The native reader's quiescence barrier needs the same distinction: "the
  render thread answered" is not "the reader finished its copy".
- *D3, the worker's memory steps once at the first Waveform Ribbon* (private 65-70 -> 104 MB, then flat; not
  attributed). Measure it before sizing revision-scoped geometry buffers against it.
- *Transport:* nothing may cross the ordered control channel through the stdlib resource sharer; a native core that
  needs another descriptor in the worker passes a name the worker opens (POSIX) or a handle duplicated into the exact
  process (Windows), as the wake pipe does.

### P3 rollout once these decisions are resolved

1. Native QRhi substrate: exact Qt/PySide6 ABI, frozen MSVC DLL guard, resource ownership, native packet reader, quiescence, capture/clip parity. Preserve the P1 experimental native `QQuickItem/QSGRenderNode` proof but do **not** treat `native/spike_p1` as a shipped renderer.
2. **Spectrum first**, real Qt Quick/GL pixel parity, frame trace and CPU/GIL measurements, under the same scene rather than a second compositor.
3. **Transitions' shared fullscreen pass next**: one QRhi substrate for reusable fullscreen transition shader family, then specialised Crumble/Particle/3D Block Spins. Preserve transition timing, image ownership, fullscreen/covered-display admission, protected clipping, shader identity and GPU resource accounting.
4. Waveform Ribbon, Extruded Bubble, remaining Visualizers, image presenter/background and Scene3D nodes. Retire each raw-Python GL renderer only after parity; do not strand a second permanent renderer.
5. Switch the **whole Qt Quick window's** backend when all raw GL dependencies are retired. Vulkan as target default, OpenGL via the same QRhi native core as selectable fallback (and D3D when supported). Never mix a Python OpenGL custom node inside a Vulkan window.
6. P4 mixed-resolution soft layers in the same native core; keep thin emissive lines, dots, rims, particles and UI full-resolution. No per-mode extra renderer/backend.

**SMP forward seam:** P3's renderer must be independent of the audio source and of the screensaver's lifecycle. A single logical worker produces the existing mode packets; a future app-owned `PlaybackService` injects decoded PCM through a selected analysis source, while the SMP dock/pop-out uses one canonical native renderer. Do not couple packet identity or RHI resource ownership to an external WASAPI loopback endpoint. Details in `Docs/Future_Work/ShittyMusicPlayer/03_PCM_Source_and_Native_Core_Seams_2026-11-09.md`.

## 4. Verification, reporting and closeout

- [ ] Each closed item includes the exact implementing commit(s), exact paths, test names, negative controls, acceptance evidence and remaining physical/operator gates. Source implementation and physical acceptance get separate checkboxes.
- [ ] Update `Current_Plan.md` item 8b **in the same change that accepts a milestone**; historical audit results remain in the audit doc, not as false open TODOs. Update `Linux_Plan.md` only when H3's actual code flips, not because an agent predicts it will.
- [ ] Preserve `--viz-in-process`, diagnostic logging, performance baselines, byte-parity oracles, no-env-var guidance, full source files, no unapproved build/actions/load; preserve `native/spike_p1` as evidence but not a product backend.
