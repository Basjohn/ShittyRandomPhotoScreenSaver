# SRPSS | Native Core P2 closeout and P3 entry plan

**Status:** actionable source-verified plan, 9 November 2026. **Source baseline:** `main` `9872ca18140c490ed018c42511803005fb3d8ed4` (15:06 SAST). **Authority:** `Current_Plan.md` §1 item 8b, `Docs/Future_Work/Native_Core_P2_Phase_Boundary_Audit.md`, `Docs/Future_Work/Native_Core_P2_Engine_Design.md`, `Docs/Future_Work/Graphics_Backend_Decision_2026-11-05.md`. This plan records the accurate *built versus accepted* distinction; it does not retrospectively claim unrun load, GPU, audio-device or Linux gates.

## 0. Decision and boundaries

The **Windows production Visualizer worker is operational and default**. P2 is not an unimplemented project; its principal capture/DSP/tick migration, IPC, supervision, recovery and frozen proof exist. Finish open defects at their owners before P3 makes the IPC/mapping contract native and more expensive to repair. Maintain the explicit `--viz-in-process` comparison/fallback and `--viz-engine-worker` diagnostic choices. A capacity violation is terminal for that activation, not a silent in-process fallback. P3 is **one native QRhi rendering core for all custom rendering**, including transitions and compositor image/background surfaces, not a Visualizer-only library and not a second renderer maintained indefinitely.

A completed implementation task, a focused test, a full acceptance test, a live operator look and a native/frozen build proof are five different statuses. Close exactly what the evidence demonstrates. If implementation and tests landed before the plan was updated, mark them landed and list only the missing acceptance as open.

## 1. Reconciled P2 status on the baseline

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

### P2-C1. M4, actual non-default identity and rendered parity

- [ ] Extend the **real production owner worker-versus-in-process** gates to at least independently altered Settings/presets in Spectrum, Waveform Ribbon, Extruded Bubble and each remaining supported mode, including switch/reconfigure, park/resume and the same live PCM. Retain existing schema-max capacity tests; do not rewrite them as if missing.
- [ ] Record packet identity (logical frames), rendered pixels/clip/BTF (gate 2) and generation/remap identity separately. A compressed-recording test must not stand in for real rendered pixels. Include negative controls that genuinely fail with one mode/Settings drift.
- [ ] Verify failed high-water admission preserves last good frame without silently changing the worker path. Run load only after operator approval per `Current_Plan.md`.

### P2-C2. M5, memory and lifecycle

- [ ] Reproduce the *remaining in-process mode-cycle* memory slope through the fallback and through Studio, isolating it from the fixed worker codec cycles (R-179), Settings retired-generation cycles (R-175) and the separate native Settings/Studio residual. Record RSS/private/USS, native allocations, GL and handles under a stable comparison; repair at lifetime owner, not via periodic trimming or disabled checks.
- [ ] Verify leases and holds release exactly once across Settings, mode switches, worker death, failed reload and a Visualizer-off run. Keep the bound of one worker/mapping and zero worker cost while disabled.

### P2-C3. L2-L5, observability, liveness and truthful results

- [ ] **L2** Rename/derive the 'GIL share' statistic so it reports what is *actually measured* (main frame occupancy/wall time), and use a real direct profiler for any new true GIL-hold claim. Pair equivalent PCM/audio contents. State GPU-clock/load conditions for FPS/age conclusions. Do not leave worker 'revisions waiting 0/0' masquerading as a throughput comparison.
- [ ] **L3** Attribute the `--usage` ~13 ms extra per 15 s sample to the additional worker; reduce the topology/sample hitch at the existing sampler, without adding per-frame sampling or changing cadence.
- [ ] **L4** Measure the Python wake-listener cost; make blocked *tick* progress detectable even if the process still responds to heartbeat. Audit Qt-bearing presentation inputs against the worker's pure/QtCore-only boundary; never silently discard an input.
- [ ] **L5** Correct historical claims made before R-179/frozen check 2. Status must identify which exact product frozen-run gate still awaits operator validation.
- [ ] Bound a target that never reveals and the failed reload/reconstruction loop without endless repeated attempts. Independent framed-view negative control and Random Group Drift semantics remain explicit targeted follow-ups, not silently closed.

### P2-C4. POSIX accepted-transfer lifetime before Linux worker default

- [ ] Design bounded ownership for an **accepted `multiprocessing.Connection` never deserialized because its POSIX child dies**. The stdlib `resource_sharer` may retain a sender `os.dup` descriptor. Serialization before admission widens, but does not duplicate, this already-existing window.
- [ ] Avoid popping **accepted** private cache entries, a global service shutdown, a blocking GUI/IO handshake or an unfenced late close. Prefer supported lifecycle ownership with clear maximum time/descriptor budget and race-safe cancellation or a different transport that requires no sharer; prove child-death-before-decode, blocked/late service requests, normal delivery, failed enqueue and repeated generation recovery.
- [ ] Keep Windows' child-owned `DuplicateHandle` path unchanged and independently regression-protected. If CPython 3.14 internal reduction adapters remain, pin and fail clearly on unsupported versions and keep version-upgrade tests. A POSIX bug is not a reason to change the already tested Windows transport.
- [ ] **H3 Linux default after source-level POSIX closeout:** flip only the canonical `visualizer_engine_worker_platform_default` owner, its platform tests and `Linux_Plan.md` Phase 4. Maintain explicit in-process override and reasoned fallback. The operator's 8 Nov waiver means no fabricated Linux runtime acceptance; label forkserver, shared-memory tracker, wake pipe, Pulse/parec capture and real-device tests **unverified**, and retain a follow-up validation gate when a Linux machine is available.

**Priority:** P2-C1, P2-C2/C3, P2-C4 and Linux H3; then P3's four decisions and core. Independent P3 design can be drafted during C2/C3, but native reader publication/teardown must not ship against an unresolved mapping lifetime.

## 3. P3 preflight: four required architecture decisions

- [ ] **D1. Native reader versus unmap:** a render-thread native reader must pin its mapping or be fenced by explicit render admission closure and a render-thread quiescence barrier before GUI close/recover/unlink. Python `PacketMailbox.take()`'s decode lock does not protect native code. Test adversarial close-during-copy, resize/remap, retire and worker replacement. The test should crash or trip a deliberate assertion without the lifetime contract.
- [ ] **D2. One consuming reader:** the native render core alone acknowledges presented frames/edges; the GUI/main owner reads only a non-consuming slot head/identity for fades/recovery/availability. Never add a second reader that consumes, decodes whole payloads, or steals edges. Define exactly when the protected-edge state is acknowledged.
- [ ] **D3. Extruded Bubble geometry revisions:** send immutable render geometry once per `(worker namespace, engine generation, activation, geometry revision, capacity)` and small mutable per-frame state separately. Do not use bare revision as a global identity; prove retention/release on geometry changes, failed swaps, GPU upload failures and native teardown. Keep CPU-only oracle data off the wire.
- [ ] **D4. Backend capability and shader inventory:** `shaderFloat64` / D3D double precision is not universally available and Qt QRhi has no universal FP64 feature query; decide a typed capability/fallback for Extruded Bubble's FP64 drift solver before porting it. Have `tools/vulkan_shader_readiness.py` discover new compute sources instead of accepting a fixed import list. Add fixed-layout per-mode native schemas; reserve the tagged Python codec namespace and make unsupported payloads fail explicitly.

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
