# Current Plan — Active Work

Last updated: 2026-09-16

Outside of Codex Work Began: `886e6fa419ff130ff2a9aedf5091ae6162d1e958`

The Qt Quick migration is closed and operator-accepted. This file contains **active work only**; completed migration,
Sphere polish, widget resize/Edit lifetime, bucket normalization and other accepted closeout items are intentionally absent.

---

## 0. R-87 emergency continuation checkpoint — FrameTrace / Qt Quick demand / runtime purity

**Status: [~] OPEN — SIGNIFICANTLY IMPROVED ON INSTALLED CHECKPOINT 3, NOT SOLVED. Current source is newer than that physical run and still requires installed validation.**

This checkpoint preserves the in-progress architectural cut made after the single-display D1 R-87 run still showed visible hitching/crawling under medium and heavy workstation load. The operator marked degradation near **10:52**, at least two more episodes near **10:54**, reduced load near **10:57**, light browser-only load by **10:59**, and UE5 heavy load beginning about **11:06**. Bubble remained near its authored ~90 logical revisions/s; the below-normal speculative image lane behaved as designed, so image-topology cycling is no longer the primary investigation.

Immediate priorities now in-tree:

- **Dedicated `--frame-trace`:** independent fixed-record binary trace of logical publish -> GUI snapshot -> Quick sync -> render draw -> frame swap. No standard Python logging on the hot path; opt-in only; not diagnostic-all.
- **Qt Quick-native presentation demand:** the Python display-refresh `QTimer` pacer is gone. Logical visualizer state is latest-wins/coalesced and requests `QQuickItem.update()` only when fresh state exists; ordinary QML `NumberAnimation`/`SequentialAnimation` cadence is left entirely to Qt Quick's animation driver. **Current post-CHK9 source** also removes the transition `frameSwapped -> requestUpdate()` feedback loop proven to overdrive D0: `FrameAnimation` supplies Qt-owned animation ticks and a per-display QML gate invokes the retained `BackgroundRenderItem.update()` C++ slot at most at that display's nominal refresh interval, with no Python per-frame callback and no catch-up burst.
- **Runtime image/presentation purity:** normal rotation must remain detached `QImage`/`PresentationImage` -> Quick texture. Generic synchronous/QPixmap fallbacks are forbidden. The unavoidable `QScreen.grabWindow()` QPixmap is isolated to a named startup-desktop capture helper and immediately detached to QImage/PresentationImage.
- **Bounded C++/QRhi spike:** active follow-up only if the Python/PyOpenGL `QSGRenderNode` hot boundary can move to a small C++ bridge without changing visualizer mode/state contracts, extensibility, reactivity, copies or latency. Stop if it becomes a broad migration.

**Continuation checkpoint 1 (2026-09-15):** the exact interrupted QPixmap-removal seam has been repaired without restoring any generic pixmap API. The neutral display-index lookup accidentally removed with the old DisplayManager pixmap block is restored; the obsolete generic QPixmap pool and orphaned overlay pixmap sanitizer are removed. ImageWorker infrastructure failure remains typed through async completion and cannot masquerade as a bad wallpaper/retry candidate. Visualizer mailbox admission is event-driven/coalesced and the bind-before-start wake edge is retired cleanly. Frame trace now preserves real per-window identity through GUI admission, drops on ring-lock contention, and its report keeps cross-screen latency/repeat evidence separate. All 42 changed/new Python files compile; the six source-only purity contracts and six frame-trace contracts pass directly in the PySide-less environment.

**Checkpoint warning:** this is still WIP, not the installed test build. Old Qt/PySide tests that encoded the retired timer/QPixmap contracts still require complete reconciliation, and actual Windows/PySide6 lifecycle/render validation remains mandatory. Do not delete/rollback R-80 -> R-86 correctness work to make this easier.

**Continuation checkpoint 2 (2026-09-15):** the worker-authority taxonomy is now complete enough to preserve: `None` means only an authoritatively rejected media candidate, while worker/transport/contract failure is `ImageProcessingInfrastructureError` and retired-runtime cancellation remains `ImageProcessingStaleRuntimeError`; both inherit `ImageProcessingAbortError` and end the admitted transaction without invalidating or retrying the candidate. The foreground display candidate contains no parent `AsyncImageProcessor.process_qimage()` fallback. Direct parent-side image work that remains is deliberate background/speculative QImage prefetch or unrelated widget/tool asset preparation, not foreground wallpaper authority. Frame trace now drops rather than waits on both the binary ring lock and last-draw telemetry contention, and its reporter includes repeated draws as latency samples instead of only the first draw per revision. The latest-wins mailbox direct contract proves one wake for a burst, newest state consumption, re-arm after drain, clean detach, and one unread slot under concurrent publishers. Versus R-87 this continuation is 6 new / 41 modified / 1 deliberate deletion; all 43 changed/new Python files compile, the six source-only runtime-purity contracts pass, and all seven source-executable frame-trace contracts pass.

**Continuation checkpoint 3 (2026-09-15):** steady-state screensaver runtime imports are now free of `PySide6.QtWidgets`: lifecycle/audio owners use `QCoreApplication`, and the intentionally QWidget-based Settings dialog is lazy-resolved only after the retired Quick generation crosses its destruction barrier. `main.py` remains the QApplication/app-shell owner so Settings can exist in-process; it is not a runtime presenter. Continuous transition/widget-animation demand now uses `QWindow.requestUpdate()` after `frameSwapped`, preserving one-pending Qt-coalesced admission instead of forcing an unconditional `QQuickWindow.update()` repaint; visualizer freshness remains its separate publication -> `QQuickItem.update()` edge. Frame-trace logical publication is now screen-scoped and follows CUSTOM cross-display transfer, closing the same-generation/same-revision D0/D1 collision that could otherwise fabricate latency. The report keys by `(screen, runtime_generation, revision)`, refuses to guess for old unscoped WIP records, and the deterministic collision fixture proves distinct D0/D1 latency. GODZIP Foundry discovers `--frame-trace`, exposes it as opt-in, and does not include it in defaults/diagnostic-all. Runtime-purity source gates are **8/8 GREEN**, frame-trace source-executable gates are **7/7 GREEN**, the older post-Phase-I QWidget cleanup source gates are GREEN, and all 19 files changed since checkpoint 2 compile. PySide/Windows execution remains mandatory before R-87 can close.

**Continuation checkpoint 4 (2026-09-15):** the post-checkpoint runtime-purity sweep removes the remaining stale compatibility residue around shared widget cadence and neutral descriptors. Weather and Media no longer mirror ThreadManager-owned recurring timers through raw `QTimer` attributes; they retain only `OverlayTimerHandle`, and missing shared scheduler ownership remains a loud error rather than a local cadence fallback. `widgets/service_widget_runtime.py` is now Qt-free policy only; dead local-QTimer construction/teardown helpers are gone and their QWidget test harness has been replaced by source-executable scheduler-authority/startup-policy contracts. Settings-only section-button construction moved out of runtime-reachable `rendering/widget_descriptors.py` into `ui/tabs/widgets_tab.py`, leaving the neutral descriptor module free of QtWidgets types/imports. Foreground image-outage telemetry is renamed from the obsolete `worker_fallbacks` label to `worker_authority_failures`, matching the enforced no-parent-fallback architecture. Frame-trace reporting now surfaces correlation incompleteness per screen/stage (`publications`, matched downstream occurrences, unmatched downstream records, and publications missing the stage) instead of silently omitting those gaps. Runtime-purity gates are **9/9 GREEN**, frame-trace source-executable gates **8/8 GREEN**, service-authority/startup-policy gates **6/6 GREEN**, and the rebuilt boundary compiles cleanly. This remains source/static evidence only; installed PySide/Windows frame-trace results are still required.

**Continuation checkpoint 5 (2026-09-15):** process/runtime purity and Quick demand ownership are tightened again. Normal `/s` startup no longer eagerly imports Settings, system-tray or QWidget-heavy shared styles; bundled font registration moved to QtGui-only `ui/font_registration.py`, leaving `main.py` with only the deliberate `QApplication` shell exception needed because Settings can later be created in-process. Quick startup tests use `QGuiApplication`. `QuickFramePacer` now starts paused when its `QQuickWindow` is hidden, preventing a pre-show update from stranding the one-pending admission bit before first reveal. Research across Qt scene-graph documentation/source behavior and independent Qt material confirmed that ordinary QML property animations already belong to Qt Quick's animation driver, including Qt's transparent timer fallback when multiple windows are visible or `swapInterval=0`; every SRPSS `widgetFrameDemand` caller was a stock `NumberAnimation`/`SequentialAnimation`. The redundant widget-animation frame-demand bridge/context/QML hooks are therefore removed completely. The custom pacer now has exactly one reason: wall-time wallpaper transitions sampled by the render node. Its continuation remains `frameSwapped -> QWindow.requestUpdate()` with one pending request; the transition controller's `QTimer` is a single-shot completion deadline, not frame pacing. Source gates are **11/11 runtime purity + 8/8 frame trace + 6/6 service authority = 25/25 GREEN**, and the whole Python tree compiles. This is still not installed/physical proof that R-87 is fixed.

**Installed Checkpoint-3 D1 light -> heavy evidence (2026-09-15): SIGNIFICANT DIRECTIONAL WIN, R-87 STILL OPEN.** The operator reported light load as seemingly perfect, a visible crawl while the heavy external application was actively loading, and settled heavy-background behavior as much better with roughly 90 FPS / 16-20 ms displayed-state age and about half or less of the previous crawl. The binary `--frame-trace` is internally healthy: **284,830 records, 0 dropped, 0 write errors**. Using the external-focus loss at ~16:07:42 plus the usage sampler's system-load climb only as phase boundaries (not as operator annotations): light steady publication->draw was **8.14 ms median / 14.21 ms p95 / 15.37 ms p99**; active heavy loading was **13.20 / 22.61 / 47.93 ms**; settled heavy load was **14.03 / 16.92 / 23.10 ms**. The key architectural result is where the settled-load penalty lives: publication->GUI wake remains excellent (**0.42 ms median / 1.70 ms p95**), publication->Quick sync remains controlled (**5.93 / 7.66 ms**), while **Quick sync->draw rises from 2.81 ms median / 6.63 ms p95 in light load to 7.89 / 9.98 ms under settled heavy load**. During active application loading, tails spread across snapshot->sync and draw->swap as well. Therefore do **not** roll back event-driven latest-wins admission or restart image-topology experiments. The next trace revision adds `QUICK_SYNC_READY` and `RENDER_BEGIN` to split the remaining post-sync cost into SRPSS sync work, Qt sync->render scheduling, and actual Python/OpenGL render duration. Checkpoint 4/5 improvements remain forward work; this physical run was Checkpoint 3 and does not test them.

**2026-09-15 two-run assessment lock — preserve before more implementation.** The Checkpoint-3 binary plus the operator-observed Checkpoint-5 dual-display heavy -> light run now establish the working direction strongly enough that this investigation must not drift back to raw-FPS tuning or speculative image-topology shuffling. Checkpoint 3 quantified the remaining steady-heavy delay downstream of Quick sync; Checkpoint 5 is reported substantially smoother on both displays, including D0/165 Hz, despite the visualizer's authored logical producer remaining ~90 revisions/s. That is expected under the new ownership model, not evidence of a new 90 Hz display cap: `_DEFAULT_MAX_FPS = 90` is the logical simulation cadence, while idle visualizer presentation is now publication-driven and therefore normally draws only when a fresh revision exists. Wallpaper transitions own an independent whole-window continuous-demand chain, so they may cause the visualizer render node to execute far above 90 draws/s while `viz_revision_hz` remains ~90. With `swapInterval=0`, `scene_fps` / `frameSwapped` / `viz_draw_fps` are render/queued-frame diagnostics and may exceed physical panel refresh; they are not measurements of photons displayed. The Checkpoint-3 HUD confirms the distinction: light median draw/revision were **90.06 / 89.98 Hz** with **10.54 ms** median age; settled-heavy **90.05 / 89.96 Hz** with **17.86 ms** median age. During settled-heavy transition-active seconds, median visualizer draw rose to **99.84/s** while revisions stayed **89.94/s** and median age was **18.65 ms**, versus **90.00/s / 89.96/s / 17.81 ms** while transition-idle. Extra scene draws therefore are not themselves the steady-heavy freshness repair target.

**Evidence discipline for the next step:** preserve the rare two-display Checkpoint-5 run; do not ask the operator to repeat dual-display testing merely to exercise the new fine-grained trace markers. The raw Checkpoint-5 archive became visible only after this assessment was written. **Checkpoint 6 intentionally preserves the pre-ingestion assessment first**; the archive must be ingested immediately after CHK6 and the quantified findings reconciled into this section rather than guessed. The next routine physical trace can be D1-only and should use current `QUICK_SYNC_READY` + `RENDER_BEGIN` events to split the already-localized Checkpoint-3 `QUICK_SYNC_CONSUME -> RENDER_DRAW` delta into (a) SRPSS sync work, (b) post-sync/pre-render-callback render-entry time (not a pure scheduler wait), and (c) Python/OpenGL render-body time. A C++/QRhi bridge remains conditional: only pursue it if `RENDER_BEGIN -> RENDER_DRAW` is the dominant heavy-load delta; if `QUICK_SYNC_READY -> RENDER_BEGIN` dominates, optimize the scheduling/render-loop boundary instead. Heavy-application startup crawl is secondary unless evidence shows SRPSS amplifies it; settled-heavy behavior remains the primary acceptance target.

**Checkpoint-5 dual-display binary ingestion (2026-09-15): RAW TRACE NOW QUANTIFIED; PLAN UPDATED.** The archive `59ea94b8-0a66-403e-8998-b098b0132466.zip` is healthy: **301,730 frame-trace records, 0 dropped, 0 write errors**, with screen-scoped generations surviving visualizer transfers/settings generations. System CPU sat roughly **44.5-50.8%** for the heavy interval until the post-Settings light tail. Clean heavy D1 (16:19:54-16:22:10) stays at ~89.9 logical publications/s with publish->draw **13.18 ms median / 16.72 p95** and HUD age **17.23 ms median**. After the visualizer moves to D0, clean heavy D0 (16:22:30-16:25:30) remains ~89.9 publications/s but is much fresher at **7.32 ms median** publish->draw / **10.58 ms median HUD age**, while retaining a fat **26.32 ms p95** tail. That exactly matches the operator's “tremendously smoother, occasional crawl” report. The tail is strongly transition-dependent on D0: heavy D0 transition-idle publish->draw is **6.94 ms median** versus **24.15 ms transition-active**; publish->GUI wake rises **0.35 -> 4.09 ms**, publish->Quick-sync **2.14 -> 13.91 ms**, and sync->draw **4.78 -> 9.95 ms**. Under light load the same effect becomes visually obvious: D0 transition-active HUD draw rate is **~286.9/s median** while revisions remain **~89.9/s**, with publish->draw **12.40 ms** versus **4.13 ms idle**. The current `frameSwapped -> requestUpdate()` transition continuation is therefore not a benign “Qt-native cap”: with `swapInterval=0` it behaves as an **as-fast-as-the-window-can-render feedback loop**, especially on the cheaper 2560x1440 D0 path, generating duplicate visualizer draws and measurable freshness pressure. D1 is much less sensitive: heavy transition active vs idle publish->draw is **14.62 vs 12.89 ms**, and light **7.81 vs 7.34 ms**. Keep Bubble's ~90 Hz logical cadence; the next production architecture task is to move wall-time transition frame opportunity ownership onto Qt's animation driver / another properly paced Qt Quick retained mechanism, not a Python refresh timer and not an uncapped swap feedback chain. Research this against Qt source/docs plus independent Qt material before implementation; installed logs remain final authority.

**Continuation checkpoint 8 (2026-09-15): `FRAME_SWAP` evidence semantics repaired before transition-driver work.** CHK5 exposed that whole-window swaps were reusing the last-ever visualizer revision even when no visualizer draw occurred in that frame or after the visualizer moved away, fabricating multi-second publish->swap tails. `VisualizerRenderNodeTelemetry` now publishes a dedicated lock-free **render-thread draw sequence + logical identity latch**, with the sequence committed last. `QuickSceneController` records `FRAME_SWAP` only when that sequence advanced since the previous swap and consumes the sequence **before** attempting the bounded trace-ring write, so a dropped diagnostic record cannot be resurrected on a later unrelated scene swap. This adds no product cadence and no cross-thread wait. Direct source contracts prove the sequence advances once per actual visualizer draw and repeated reads/swaps manufacture nothing. Post-repair source validation is **29/29 directly runnable contracts GREEN** across runtime purity/frame trace/service authority, and **all 896 Python files compile** in the PySide-less checkpoint environment. Installed Windows/PySide proof remains required.



**Continuation checkpoint 9 (2026-09-15): evidence-only D1 control checkpoint before transition-driver changes.** The additional CHK5 D1-only light->heavy binary is ingested and supports the architecture while narrowing expected benefit from transition-driver repair: D1 light publication->draw **8.36/14.50 ms median/p95**, heavy-loading **13.24/24.50 ms**, settled-heavy **14.06/19.61 ms**; trace health **220,402 records, 0 dropped, 0 write errors**. Heavy transition-active D1 is **12.92/15.37 ms**, versus idle **14.34/22.98 ms**, so the dual-display D0 transition overdrive remains real but high-refresh scoped. CHK9 intentionally changes evidence/docs only; production remains CHK8. Next production task remains replacing the D0-uncapped transition `frameSwapped -> requestUpdate()` feedback loop with a Qt-owned paced mechanism, while retaining fine-grained markers for D1 residual diagnosis.

**Additional installed Checkpoint-5 D1-only light -> heavy control (2026-09-15): SUPPORTS THE ARCHITECTURE, NARROWS THE TRANSITION FIX.** The second CHK5 trace is healthy (**220,402 records, 0 dropped, 0 write errors; writer demoted to Windows below-normal/no-boost**). Using the usage sampler's system-load rise to split clean phases, light publication->draw is **8.36 ms median / 14.50 ms p95**, active heavy-loading is **13.24 / 24.50 ms** with p99 **47.66 ms**, and settled-heavy is **14.06 / 19.61 ms**. Bubble remains at ~90 logical revisions/s throughout. This independently reproduces the CHK3 result: event-driven publication/GUI admission remains healthy while settled-heavy age persists downstream. Crucially, on this D1-only run wallpaper transitions are **not** the dominant settled-heavy penalty: heavy transition-active publication->draw is **12.92 / 15.37 ms** versus idle **14.34 / 22.98 ms**, and HUD draw rate rises only modestly (heavy active median ~**92/s** vs ~**90/s** idle). Therefore the CHK5 dual-display transition overdrive diagnosis remains valid but is **display/high-refresh scoped**: removing the uncapped swap-feedback loop is expected to reduce D0 waste/fat tails and occasional crawl, not to close D1 heavy-load freshness by itself. Keep `QUICK_SYNC_READY` + `RENDER_BEGIN` as the D1 residual-crawl probe after the transition repair.

**Updated next evidence order after CHK5 ingestion:** (1) **DONE in CHK8:** repair `FRAME_SWAP` draw-to-swap identity semantics; (2) research and replace the uncapped transition swap-feedback driver with a Qt animation-driver-owned/paced retained mechanism while preserving monotonic transition progress and zero Python polling; (3) keep the already-added `QUICK_SYNC_READY` + `RENDER_BEGIN` markers; (4) next physical run may be D1-only unless a new cross-display-specific question appears. Do **not** request another dual-display run merely to validate these markers—the existing CHK5 run has already answered the cross-display cadence/transition question.

**Continuation checkpoint 10 (PACKAGED 2026-09-15): Qt-owned, per-display transition frame gate implemented.** Multi-source research before implementation used Qt's public `FrameAnimation` documentation, Qt's `QQuickFrameAnimation` source, Qt's threaded scene-graph render-loop source, Qt's animation-driver source, and independent KDAB scene-graph/render-thread material. The source confirms the installed CHK5 mechanism: with `swapInterval=0`, Qt deliberately uses its system animation timer rather than treating buffer swap as the animation clock; that timer is based on the primary-screen animation-driver interval. A bare `FrameAnimation` was therefore **not** accepted because on mixed 165/60 Hz it would be a global animation tick and could make a 60 Hz window follow the primary screen's faster cadence. The implemented shape is bounded per display: Python `QuickFramePacer` is now lifecycle/demand coordination only and owns no frame clock, no `frameSwapped` connection and no `requestUpdate()` loop. `DisplayScene.qml` owns `FrameAnimation`; each native tick advances a no-debt per-display due-time gate and invokes the inherited C++ `BackgroundRenderItem.update()` slot only when that display's nominal refresh interval is due. The render node still samples immutable `TransitionRun` monotonic time, so transition duration/progress is unchanged and missed opportunities are skipped rather than replayed. Python only publishes `{active,target_hz}` on transition/visibility/display-retarget/lifecycle edges. **29/29 source-executable preservation contracts are GREEN and all 896 Python files compile.** Installed acceptance is deliberately split: D0/high-refresh must show transition-active draw rate collapsing from ~287/s toward the display opportunity without harming transition duration/smoothness; D1 heavy-load freshness is still judged by `QUICK_SYNC_READY -> RENDER_BEGIN -> RENDER_DRAW`, because the independent D1 CHK5 control proved transitions were not its primary residual. Known public-API limitation: Qt's animation-driver fallback cannot tick a high-refresh secondary faster than the primary-screen interval when `swapInterval=0`; do not hide that limitation or add another Python clock to compensate without installed evidence.


**Continuation checkpoint 11 (PACKAGED 2026-09-15): native transition-driver lifecycle hardening + handoff authority repair.** Post-CHK10 audit confirmed remaining `frameSwapped` connections are observation/trace/smoke boundaries, not frame-driving feedback. The QML gate now explicitly `reset()`s `FrameAnimation` when native demand starts, clears `transitionFrameNextDueS` when the target display Hz changes, and still issues at most one `BackgroundRenderItem.update()` per native tick with no catch-up burst. Python `QuickFramePacer.stop()` now clears transition demand without clearing `_paused`; visibility remains the sole pause/resume authority, so a hidden runtime cannot be made eligible for later transition demand by a generic stop. Qt/PySide public docs support `FrameAnimation.reset()` and `QQuickItem.update()` semantics, but installed QML loading/render remains required. Direct source authority gates remain **29/29 GREEN** and all **896 Python files compile**. This checkpoint also rewrites `.godzip/CHECKPOINT_HANDOFF.md` around the current CHK10/CHK11 architecture because its old top section still described the retired swap-feedback loop; future agents must treat the rewritten handoff as the first recovery authority.





### CHK10 installed regression evidence — visualizer hotswap can poison live audio source (2026-09-15)

**Status: [!] OPEN REGRESSION — separate from the pacing improvement; do not roll back the successful Quick admission work.**

A D0-light validation run of CHK10 could not proceed to heavy load because an in-place visualizer hotswap failed beginning at **Spectrum -> Oscilloscope around 17:38:23**. Operator symptom: the UI/menu reported Oscilloscope but the visualizer card was blank; later modes could remain blank or show only authored idle behavior, with Settings/full runtime reconstruction temporarily restoring life.

Installed log evidence is unusually specific:

- `spectrum -> oscilloscope` cleanly requests and commits engine **generation/activation 4/4** and restarts the logical runtime.
- That mode switch also changes authored audio block size **128 -> 256**, causing a live `PyAudioWPatch` capture restart. The backend reports the new 256 stream as running.
- Immediately after reveal, Oscilloscope reports `ready=True source=4/4` but all live energies remain exactly zero and `source_age_ms=-1.0` for the remainder of that runtime. The logical runtime itself continues stepping; this is not a stopped render loop.
- The line-mode readiness fence currently accepts matching `latest_generation_with_waveform` as source-ready. A raw/empty callback can advance waveform generation before a post-activation authoritative analysis frame exists. Therefore one zero/empty restart callback can falsely reveal the new line mode even though live reactive authority never recovered.
- A full Settings teardown/reconstruction creates a fresh capture backend and partially restores non-zero line-mode source state, matching the operator observation that Settings could recover behavior when context/double-click hotswap could not.

Working diagnosis has **two coupled seams**:

1. **live capture restart reliability:** per-mode block-size changes restart the active WASAPI loopback stream; repeated hot restarts can report success without subsequently delivering useful live source frames;
2. **too-weak reveal authority:** Oscilloscope/Sine may reveal from waveform-generation identity alone instead of requiring post-activation authoritative live-source evidence while playback is active.

Repair order after CHK11 preservation:

1. Strengthen playing line-mode reveal/source-ready so a matching waveform generation is insufficient without a post-activation authoritative live frame/capture timestamp.
2. Audit whether mode-specific block-size behavior can be preserved without restarting the live capture stream. Prefer stable capture ownership plus analysis-side adaptation if semantics can remain identical. If a restart is truly required, it must expose first-callback/recovery authority and hotswap must remain fenced until that authority arrives; a backend `start()` return value is not enough.
3. Add a deterministic hotswap contract covering `spectrum -> oscilloscope -> sine -> bubble` while playing and proving generation advance cannot reveal zero-authority line state.
4. Do **not** restore the old Python display-refresh pacer, QWidget/QPixmap fallback, or synchronous presentation fallback to work around this. The CHK3/CHK5 pacing gains remain independently proven.

## 1. Steam Friend Pulse — public implementation complete, awaiting live/installed acceptance

Execution authority: `Docs/Future_Work/Steam_Friend_Pulse.md`.

The retained implementation is complete through F6. It is a full friend-roster card with a default dynamically centred
**Avatar Grid** and selectable compact **Activity Rows** view. Online friends lead the model and offline friends fill the
remaining configured viewport; every accepted friend remains scroll-reachable. Both views use one stable virtualized
presentation model and fixed capacity-owned geometry, so roster size never owns card height and privacy changes do not
create a second source/model.

- [x] Pin pre-feature HEAD `e0314691` and preserve the maintained Steam request/cache/privacy fixtures.
- [x] Add immutable normalized Friend Pulse source/cache state. Validated Steam IDs may remain in the user's
  account-private cache and owner-only runtime action map; presentation snapshots/QML roles/logs receive no ID or full
  action URL and QML emits only a current row index.
- [x] Add cache-first FriendList + bounded PlayerSummaries preparation through existing Steam locks, request
  coordination, backoff and redaction. The only cadence setting remains canonical `widgets.steam.refresh_minutes`.
- [x] Add one runtime-generation shared source/avatar owner with per-display leases. Steam family activation,
  `widgets.steam.enabled`, member enable and a real presentation consumer all precede work; last release
  stops cadence, clears comparison/avatar state and fences source/avatar completions.
- [x] Add Strict/Balanced/Rich projection, online-first/offline-fill roster ordering, honest private/connect/empty/stale/
  failure states, per-friend presence/game details, Rich-only current-viewport local-avatar hydration, and no Strict
  identity leak.
- [x] Add retained virtualized Quick Grid/Rows presentation, dynamically spaced and centred avatar tiles, incomplete-row
  centring, optional centred names with bounded font size, branded/theme roles, finite theme-colored change glow,
  `ordinary_uniform`, global CUSTOM/40% floor, ordinary stacking/auto-fit, lazy transactional Settings and
  generated-default authority.
- [x] Add generation-fenced semantic clicks and one retained Gmail-style three-dot popup per card. Direct avatar actions
  request Steam chat with public-profile fallback; menu actions offer Profile, Chat, Copy Steam ID and Store when
  a current AppID exists. Friend game labels and Achievement/Abandonment artwork open the Store. MC/diagnostic tries the
  Steam client; normal screensaver routes HTTPS through the existing secure helper and exits once after accepted handoff.
  Join Game is deliberately absent because the admitted summaries prove only an AppID, not a joinable lobby/server token.
- [x] Focused source/runtime/privacy/cache/request/Settings/QML/binder/cardinality/normalization/action tests are GREEN;
  the real threaded-OpenGL DPR 1.5 roster/menu/Strict/Rows/40% capture is warning-free and proves the finite event glow.
- [x] Remove Friend Pulse's temporary product gate across Steam Settings, runtime/preview descriptors and retained
  binder admission. It is now always visible inside the Steam family; `--devsteam` owns only unfinished Games You Follow.
- [x] **Implemented recovery/polish (2026-09-13, e31 authority; awaiting validation):** land Friend Pulse ALL-CAPS status/game chrome, offline-avatar desaturation, hard avatar clipping, remove the redundant lower-right presence circle (and update presentation-test expectations), strengthen family-local linework, keep Title Case/bold/two-line name fitting, and add a real hover-only multi-pin/favourite affordance with account-private persistence.
- [x] **Implemented Restore Size (awaiting validation):** add an edit-mode bottom-left `↶` glyph styled like Close. Restore only the selected widget's authored non-CUSTOM size/shape while preserving current X/Y + display and staying in CUSTOM. Do not call `restore_baseline`, stacking, ordinary auto-fit, or ordinary shrink. Uniform reduction is allowed only when authored size itself physically exceeds the owning display.
- [x] **Unread-message experiment removed (2026-09-13 operator decision):** remove the experimental FriendMessages source IDs/endpoints/parser/cache/runtime request path, unread avatar hydration, message model/menu/glow, tests and backoff traffic. Do **not** add QR auth, a second Steam login/session or any credential expansion. Existing Friend Pulse friend-chat/profile actions remain unchanged.
- [x] **Friend Pulse wide-grid reflow:** remove the old 900 px CUSTOM width clamp and six-column ceiling. The 2026-09-13 installed log/visual check exposed one remaining accidental ceiling: `visible_row_capacity` still capped CUSTOM horizontal columns, so a baseline capacity of 4 could never expand beyond four columns. Authored/non-CUSTOM layout still respects the configured visible capacity, but once a CUSTOM horizontal `content_extent` exists the logical width owns the readable column count up to the project-wide 24-friend ceiling. Vertical capacity/scroll behavior remains intact.
- [x] **Friend Pulse dropped-message hotfix (2026-09-13):** after removing the unread-message experiment, one stale `_rebuild_message_rows()` call remained in `FriendPulsePresentationModel.on_friend_pulse_runtime_snapshot()` and raised on delivered roster snapshots. Remove that dead call/branch; source regression coverage now forbids `_rebuild_message_rows` / `message_rows_changed` from returning.
- [?] **Friend Pulse hotfix installed validation:** run a normal Friend Pulse refresh/lease delivery and confirm no UI-invoker `AttributeError`, roster/state updates continue, and the dropped unread-message path produces no source/backoff work.
- [x] **Optional online-count summary:** add canonical `widgets.friend_pulse.show_online_count = true`, expose a themed Settings checkbox, and project the already-owned Steam snapshot count as ALL-CAPS `X FRIEND(S) ONLINE` in the top-right summary area. This adds no source work/cadence and is blank until a ready/stale roster exists.
- [x] **Focused non-Qt recovery gates:** Friend Pulse visual/pin/Restore Size + dropped-message absence + wide-grid/online-count source contracts pass directly in the PySide-less environment; Steam backend core checks also pass. PySide runtime/QML execution remains a separate installed gate.
- [?] **Recovery/Restore Qt test execution:** run the Friend Pulse runtime/QML and CUSTOM session/overlay/owner tests in the project PySide6 environment. Confirm hover-only pins, removed status circles, offline desaturation/clipping, ALL-CAPS status/game chrome, `X FRIEND(S) ONLINE`, wide-grid expansion beyond four/six columns, `↶` Restore Size routing and exact X/Y/display preservation. Specifically side-resize Friend Pulse/System Stats, then Restore Size and prove the target is the canonical authored size rather than the just-committed CUSTOM `content_extent`.
- [x] **Restore Size authored-geometry authority repaired after 2026-09-13 log:** the log proved routing beyond Friend Pulse/Visualizer (Friend Pulse, System Stats, Weather, Media and Visualizer all received Restore Size with exact X/Y preserved and `emergency_fit=1.0000`), but it also exposed that `DisplayPresenter._base_geometries` could be overwritten by an effective committed CUSTOM rectangle/content extent. Geometry binding now publishes a separate committed-rect-free authored projection, and the presenter admits the canonical pre-CUSTOM preferred geometry once then freezes authored-cache updates while CUSTOM/edit owns layout. CUSTOM `content_extent` churn therefore cannot redefine the Restore Size target. Restore still clears `content_extent`, preserves display/X/Y, stays in CUSTOM, performs no stacking/ordinary auto-fit/shrink, and only emergency-fits when the authored rectangle itself exceeds the display.
- [?] **Awaiting Validation:** use a real connected Steam account to inspect long names/game names, Rich avatar-cache
  hydration, Strict/Balanced reprojection, private/unavailable/stale wording, manual refresh behavior, friend chat/profile
  routing, game Store routing, rounded avatar/tile borders, hover-only multi-pin behavior, finite friend-change glow,
  wide-grid expansion, and the optional top-right online-count summary against real themes.
- [?] **Awaiting Validation:** installed two-display/DPI/theme/CUSTOM/stacking soak must confirm one shared source owner,
  no refresh multiplication and clean last-card/family-deactivation retirement.

---

## 2. System Stats — public CPU/Memory/Uptime/Network implementation complete, awaiting installed soak

Execution authority: `Docs/Future_Work/System_Stats_Widget.md`.

The dedicated product source remains isolated from diagnostic `--usage`. The family is normally visible/activated while
the member remains disabled by default, so no sampler exists until the user enables System Stats and a retained card
consumer is admitted.

- [x] Preserve the admitted whole-system CPU/RAM source and extend that **same** sample pulse with system uptime plus
  aggregate network receive/transmit counters. Uptime captures boot time once and derives elapsed time on the existing
  pulse; Network derives rates from cumulative OS counters and therefore needs the same two-observation cadence as CPU.
  No process/core enumeration, network request, driver, second sampler or second timer was added.
- [x] Keep exactly one low-priority sampler owner per runtime generation. Display leases share one immutable snapshot;
  sampling is fixed-delay from completion, one-in-flight, generation fenced, and final lease release closes/clears source
  ownership with no recurring work left alive.
- [x] Promote the former hard-coded 10-second interval into canonical `widgets.system_stats.sample_interval_seconds`.
  Settings exposes one **Sample Interval** control with a hard 10-second minimum/default and slower values allowed up to
  one hour. It reuses the existing owner rather than introducing another cadence.
- [x] Expand the retained card from two to four fixed metrics: CPU LOAD, MEMORY, UPTIME and NETWORK ↓/↑. Fixed-capacity
  geometry remains value-independent; canonical capacity is 4 and preferred/authored height is 430 px. Uptime/Network
  do not invent meaningless percentage tracks.
- [x] Remove implementation/rejection commentary from the user interface. Settings no longer exposes implementation/rejection commentary, and the card no longer carries architecture/cadence filler.
- [x] Preserve canonical family/default/descriptor ownership, lazy Settings construction, generated JSON/SST defaults,
  ordinary stacking/global-CUSTOM/40% contracts and the existing packaged header asset/theme semantics.
- [x] **System Stats Settings/pill polish (2026-09-13):** Widgets-page section pills now reserve the real label width plus authored padding, fixing `System Stats` clipping at the shared descriptor button factory rather than with a one-off width. Add canonical CPU / Memory / Uptime / Network toggles under a lazy Metrics bucket; all four default on. Disabled metrics are skipped inside the existing shared source pulse (CPU/RAM/uptime/network reads are not performed for hidden metrics), while the single shared owner/cadence remains unchanged—selection creates no alternate timer/source owner.
- [x] **System Stats two-axis CUSTOM content extent:** opt System Stats into the existing shared `content_extent_axes=(horizontal, vertical)` contract. Side-resize reflows instead of uniformly scaling: extra horizontal room widens detail/value lanes; extra vertical room redistributes enabled metric panels and spacing/padding. The CUSTOM payload is presentation-only and never mutates real widget settings. Corners/wheel keep the ordinary uniform path and Restore Size clears back to authored geometry through the existing authority.
- [x] **System Stats metric-section border balance (2026-09-13):** increase only the per-metric section outline from the shared 1.0 px baseline to `scaleAwareStrokeWidth(1.25)`. The 5 px accent block on the left stays unchanged; this is a +0.25 px family-local balance tweak, not a new border/theme authority.
- [x] Canonical default artifacts regenerated from `default_settings.py`; generated JSON + both SST files pass regeneration check, and the broader defaults-authority audit is GREEN. The audit also removed three pre-existing Friend Pulse runtime literal defaults in favour of canonical default-contract reads without changing behaviour.
- [?] **System Stats installed/PySide validation:** confirm the wider `System Stats` pill no longer clips, all four metric toggles round-trip, hidden metrics immediately disappear and their disabled OS reads stay skipped without sampler multiplication, the +0.25 px metric-section outline visually merges better with the 5 px accent block without looking heavy, horizontal/vertical side handles reflow cleanly at small/large extents, and Restore Size returns the canonical non-CUSTOM authored family rectangle when no emergency display fit is required.
- [x] **Generic Widgets Settings family-retirement hotfix (2026-09-13 log):** deactivating System Stats correctly destroyed its lazy Settings section, but a delayed coalesced Widgets-tab save retained the section's CUSTOM-resize notice `QLabel` and called `setVisible()` after Qt had deleted the C++ object. Repair the shared retirement seam for every retireable family: invalidate any pending pre-retirement save token, drop family-owned notice side references before `deleteLater()`, clear both built/building ownership, reject invalid Shiboken wrappers during lock-state refresh, and let the post-retirement activation save arm a fresh token. This is not a System Stats exception.
- [x] **Retirement regression coverage:** pure source/lifetime contracts pass **2/2** and a PySide parameterized retire → delete processing → save → rebuild test now covers every CUSTOM-resize-lock family section (Clocks, Weather, Media, Reddit, Gmail, Steam, System Stats).
- [?] **All-widget load/unload installed validation:** repeatedly deactivate/reactivate every widget family, including while a coalesced Settings save is pending, and confirm no `Internal C++ object ... already deleted`, no stale-control mutation, no rejected UI callback, clean lazy rebuild, and unchanged persisted per-family configuration.

- [?] **Awaiting Validation:** installed minimum-interval off-vs-on Visualizer contention run must confirm no meaningful
  freshness/reactivity or event-loop/presentation-tail regression with CPU/Memory/Uptime/Network enabled.
- [?] **Awaiting Validation:** repeated enable/disable, interval changes, runtime recreation and two-display soak must
  confirm one shared owner, no refresh multiplication and clean final retirement.

---

## 4. Steam Games You Follow — dev-gated feasibility-first future slice

Execution authority: `Docs/Future_Work/Steam_Games_You_Follow.md`.

This replaces the unfinished Steam Progress / Steam Journey scaffold while retaining `steam_progress` as its
compatibility id. It is a bounded retained card for news from explicitly followed games, not a personalised Steam or
whole-library news feed. It stays behind `--devsteam` until its source/follow-list and source-article URL boundaries
are proven.

- [ ] Complete G0 before implementation: prove the follow-set authority (or obtain explicit approval for a local
  validated-AppID list), APP_NEWS field/response budget, and safe source-article URL/helper policy. Do not infer
  follows from ownership/recent play or add a fallback source.
- [ ] Then implement only through the documented G1-G5 sequence: feature-owned cache/model, one shared
  generation owner, retained Quick rows, canonical Settings/default migration and ordinary/CUSTOM acceptance. The
  first retained implementation must already consume shared horizontal + vertical `content_extent`; side handles reflow
  at constant uniform scale, corners/wheel remain whole-card uniform, both row variants have authored preferred geometry,
  Restore Size/slot replay/cross-display DPR transfer use the shared geometry owner, and no family-local resize system is
  permitted.

---

## 4A. Settings slider commit / crash hardening — additional active work

This is additive and must not displace the Friend Pulse/Restore Size acceptance work above. A 2026-09-13
older-checkpoint crash log ends during an extreme Accessibility slider save storm: each slider increment re-saved all four
Accessibility values and published four `settings.changed` events. `SettingsManager.set()` correctly treats every semantic
mutation as a persistence revision, so slider drag batching belongs at the shared UI-control/connection seam, not inside
SettingsManager and not behind a new polling/debounce owner.

- [x] **Diagnosed:** Accessibility slider drag currently calls `_save_settings()` on every `valueChanged`, re-emitting
  `dimming.enabled`, `dimming.opacity`, `pixel_shift.enabled`, and `pixel_shift.rate` for every increment. The supplied
  log terminates mid-storm at 17:51:19. This is strong correlation with the crash but not proof of native crash cause;
  `native_faults.log` contains no captured fault record.
- [x] Add one shared `NoWheelSlider` commit signal: live `valueChanged` remains available for labels/previews, while
  persistence-capable tabs bind save work to the release/commit boundary. Keyboard/programmatic discrete changes remain
  discrete commits; no timer/poller is introduced.
- [x] Migrate immediate-persistence slider paths (Accessibility, Display glow sliders, Sources ratio, Transitions sliders)
  to release-time commit and add focused tests. Accessibility additionally persists only the setting that actually changed,
  reducing the reproduced 46-save/186-event storm to one semantic mutation per committed slider interaction. Preserve
  existing Widgets/Visualizer coalescing authority; audit those slider bindings for redundant callback churn without
  layering a second debounce/persistence owner. Pure source/SSOT contract checks pass 3/3 in the PySide-less environment.
- [?] Installed Settings validation: drag each affected slider aggressively, confirm labels/previews remain live while
  persistence/settings events occur once per drag commit, then repeat the crash reproduction and inspect writer/event logs.

## 4B. Friend Pulse directional-shadow audit + dynamic artwork crossfade polish

- [x] **Audit started:** Friend Pulse already gives the BrandedHeader a directional card shadow and text uses the shared
  text-shadow roles. Row/grid tile surfaces, avatar frames, pin/menu controls, separators and the empty-state icon do not
  currently own equivalent directional surface shadows.
- [x] **Shadow prescription:** add, if visual validation agrees, subtle same-direction shadows to row/grid tile surfaces.
  Avatar frames should not use a filled rectangular shadow: shadow the border-ring alpha itself (or an equivalent
  outline-only source) so the empty/transparent interior stays empty, using the existing global card shadow direction/color
  with lower alpha/blur. The empty-state icon may take a very light same-direction shadow. Leave thin separators, pin
  glyphs/buttons and three-dot affordances unshadowed by default; they are too small and become muddy fast. Do not invent a
  Friend Pulse-only direction authority.
- [x] Improve dynamic Media/Steam artwork changes through the shared event-driven `ArtworkFadeImage` SSOT. Keep the current
  readiness-gated two-buffer/no-flash contract and frame-demand ownership; make replacement transitions gentler for every
  existing Media/Achievement/Abandonment artwork consumer without per-widget timers or duplicate transition machinery.
  Shared replacement fade is now 520 ms with `InOutSine`; empty-source fade is 280 ms. The Abandonment-local 340 ms override
  was removed so the shared primitive is authoritative. Pure artwork/slider contract checks pass 9/9 combined.
- [?] Visual validation across Media + Steam artwork surfaces: rapid source churn, missing->ready, ready->missing, same-source
  withdrawal, DPR/theme changes, and no retained second texture after transition idle.

---


## 4C. 2026-09-14 overnight soak — performance/lifetime findings

Authority/evidence: the 03:34–13:54 diagnostic soak with `--usage`/cache/perf sidecars and the 2026-09-14 source trace. The
run began on two displays; Windows removed the MSI panel from the logical topology at ~03:53 while displays were off, so
most of the overnight interval is a one-logical-display process/service soak. The 13:46 wake sequence is still valuable
monitor-loss/reconstitution evidence. Diagnose first, tests second, production fixes only after the tests encode the real
ownership/lifetime invariant. Do not add instrumentation unless end-to-end tracing remains below ~80% confidence; any new
high-volume diagnostic belongs in a dedicated sidecar rather than already-busy `--perf`.

- [x] **Scaled-prefetch queue root cause proven (>95% confidence).** `ImagePrefetcher.register_scaled_requests()` may admit a
  derivative while its raw parent is resident or owns an active/pending producer. `_submit_load()` then treats a returning
  `ImageCache.put(raw)` call as proof of residency even though the hard 256 MiB LRU is allowed to evict the inserted raw
  immediately; `_pump_scaled_prefetch()` dispatches only resident parents and has no orphan-reclamation path once the parent
  has neither residency nor a producer. The stranded derivative therefore keeps both `_pending_scaled_keys` and logical-byte
  budget forever. Soak proof: all 11 scaled-prefetch completions occurred by 03:37:01; the dead queue then stabilized at
  exactly **125,337,600 bytes** = `2×3840×2160×4 + 4×2560×1440×4`, **93.4%** of the 128 MiB pending-byte cap, while later
  registrations were repeatedly rejected. At shutdown: **4,675** scaled-prefetch intents, **11** scaled completions,
  **2,600** completed raw-prefetch IO tasks, only **9** scaled cache hits vs **962** scaled misses. The bounds prevented a
  memory leak but the pipeline spent most of ~10 h decoding speculative raw inputs with almost no derivative payoff.
- [x] **Prefetch regression authored before fix (2026-09-14; PySide run still required):** `test_image_prefetcher.py` now
  models the exact hard-cache case where raw `put()` succeeds but the inserted parent is immediately nonresident. Coverage
  requires orphan key+byte reclamation, immediate budget reuse by newer valid work, six repeated self-eviction cycles with
  zero pending drift, and the inverse invariant that a derivative remains owned while its raw parent is still queued/inflight.
  These are owner/lifetime regressions rather than stale list-shape assertions. `test_image_pipeline` remains separately
  classified for broader current-owner fixture reconciliation; do not make its old internal shape the new contract.
- [x] **Prefetch production repair landed after regression gate (2026-09-14):** raw completion now verifies actual
  post-`put()` cache residency; a bounded ownership sweep releases pending derivatives that are stale/already satisfied or
  whose raw parent has neither residency nor queued/inflight producer ownership. Cleanup runs before admission and before
  scaled dispatch, including during the post-transition compute cooldown, and raw-submit failure also triggers cleanup. The
  inverse producer-owned case is retained. No cache/backlog/concurrency/render/Visualizer limit changed. On the soak state this
  would release **125,337,600 bytes / 119.53 MiB** of dead logical budget, increasing usable admission headroom from
  **8.47 MiB to 128 MiB** (default queue: up to eight 2560×1440 derivatives by count, or four 3840×2160 by byte cap).
  Runtime cost is an O(pending) ownership scan over the already-bounded derivative queue (normally <=8 at concurrency 2),
  only cheap cache-membership/set checks; no image processing or new task/timer is introduced. Isolated A/B state-machine
  smoke against the tests-only checkpoint proves old=`1 pending / 16 MiB charged`, repaired=`0 / 0` for self-eviction.
- [x] **R-82 installed soak closure (2026-09-14, 58 min): PASS.** Under sustained scaled-cache churn the repaired
  pipeline stayed live: **93 scaled-prefetch requests / 91 completions**, **85 scaled evictions / 2.642 GiB evicted**,
  **45/45 deferred resume schedules/runs**, and **91** raw-prefetch sources released after their final derivative. Final
  cache state was bounded at **6 scaled items / 189.8 MiB** with **45 scaled hits / 0 misses / 0 worker requests**. The old
  stranded-derivative signature did not recur; admission recovered after bounded pressure rather than pinning near 128 MiB.
  Treat R-82 as closed unless a future regression reproduces orphaned pending bytes or scaled-prefetch death under eviction.

- [x] **Reddit zero-delay due-loop root cause proven (>95% confidence).** The blocked-cooldown path converts a positive
  floating remainder with `int(... * 1000)`. A positive sub-millisecond remainder becomes `0`; `_schedule_timer()` handles
  `delay <= 0` by synchronously calling `_on_periodic_due()`, which re-enters `fetch()`, sees the cooldown still positive,
  re-authors another zero delay and recursively repeats until wall time advances. The soak contains **854** due-arm records,
  **763** blocked-cooldown arms and **721 zero-delay blocked-cooldown arms** across 27 second-buckets; worst observed burst is
  **84 synchronous arms in one second**. Network rate limiting still prevented Reddit request multiplication, so the cost is
  avoidable UI-thread/log churn and recursion risk rather than remote hammering.
- [x] **Reddit regression authored before fix (2026-09-14; PySide run still required):** drive a controlled positive
  `0.4 ms` blocked cooldown through the real `fetch()` -> due-authoring -> timer seam and require exactly one deferred
  `>=1 ms` one-shot with no synchronous `_on_periodic_due()` entry. A second regression pins preserved positive sub-ms
  monotonic deadlines so they cannot truncate to zero before they are actually due.
- [x] **Reddit production repair landed after regression gate (2026-09-14):** all positive second remainders now preserve
  a positive integer delay via ceiling/minimum-one-ms conversion, including preserved monotonic dues and blocked fetches;
  `_schedule_timer()` always routes even a due-now edge through the existing one-shot instead of synchronously re-entering
  `_on_periodic_due()`. No timer/poller/cadence owner was added. Against the soak this removes the **721** observed zero-delay
  blocked-cooldown arms (worst 84/s recursive burst) and replaces each boundary with one deferred edge; the only timing cost
  is roughly 1–2 ms at an otherwise due-now boundary, negligible beside the 15-minute Reddit cadence. Isolated A/B smoke
  proves old=`1 synchronous due / 0 shots`, repaired=`0 synchronous / 1 positive shot`.
- [x] **R-83 installed soak closure (2026-09-14, 58 min): PASS.** The run contained two blocked-cooldown
  boundaries whose formatted remaining delay reached `0.0`, but neither produced the old synchronous re-arm storm. Each
  boundary advanced into one legitimate due fetch/fallback chain and then authored the normal ~900 s next edge. No same-second
  recursive burst or request multiplication returned; cooldown-gated manual refresh remained rejected normally. Treat R-83 as
  closed unless zero-delay recursive scheduling reappears.

- [?] **R-84 narrowed by handle-class attribution — stable runtime is flat; one replacement-generation baseline step remains.**
  The 2026-09-14 follow-up soak ran ~56.5 minutes with **226/226 `--usage` samples** and 57 independent
  `screensaver_handles.log` snapshots. During the long settled generation-0 interval (~18:13–18:40), the five-sample
  `handles_main` median moved only about **1812 -> 1814** and the persistent object classes were effectively flat
  (`type_56` ~236/237, `Key` 66, `Section` 390, `File` 419, `Semaphore` roughly 259–263). The old straight-line
  “+handles/hour” interpretation therefore did **not** reproduce as a continuous steady-generation leak. At the explicit
  Settings runtime replacement (~18:42), however, the settled generation-1 baseline stepped upward by a persistent bundle
  of approximately **type_56 +10, Semaphore +10, Key +6, Section +3, File +2**. Later ordinary mode/transition activity did
  not staircase those classes again. Remaining question: is that one-time native/lazy generation-1 initialization or does
  **each full runtime replacement** retain another bundle?
- [x] **R-84 attribution sidecar validated:** the out-of-process 60 s handle classifier ran for the whole soak, its PID stayed
  excluded from app aggregates, and its object-type history was sufficient to reject the continuous-leak hypothesis above.
  Do not add another handle probe or broaden cadence. If the final churn test staircases, investigate the already-identified
  generation retirement/constructor owners directly; if it plateaus after the first replacement, close R-84.
- [x] **`--usage` Toolhelp observer-effect repair validated (2026-09-14):** after startup, the two-minute topology refresh fell
  from the previous ~80–144 ms psutil/GIL-heavy samples to roughly **26–59 ms** (median ~47 ms) using `topology_source=toolhelp`,
  with zero skipped 15 s samples. The previous regular two-minute visualizer/frame hitch signature disappeared; refresh-period
  frame/event-loop tails are now broadly comparable with ordinary samples. Keep the psutil fallback only for Toolhelp failure/
  non-Windows continuity; do not restore the GIL-held Windows recursive `children()` + per-process `num_threads()` owner.
- [x] **Handle attribution is explicit again.** The smooth control used `--usage` without the later handle-enumeration child. `--usage` therefore starts only the low-cadence usage sampler; `--handle-attribution` explicitly admits the Windows sidecar and implies `--usage`. Diagnostic-all does not admit it. This prevents deep observer work from silently changing process topology.

- [x] **Settings 300–500 ms stalls classified by code ownership, not handwaved:** `on_settings_requested()` first performs the
  explicit full `engine.stop(exit_app=False, reason="settings")` and runtime destruction barrier; the ~335 ms Settings-dialog
  construction and later replacement `_initialize_display()`/`start()` occur while there is **no live display runtime**. The
  same full-replacement path is intentionally used only for Settings, committed CUSTOM edit reload, monitor-topology replacement,
  startup and teardown. Ordinary Visualizer mode/preset changes use the retained owner and do **not** rebuild DisplayManager.
  Therefore those several-hundred-ms stalls are admissible lifecycle/reconfiguration cost under the current policy. **Any
  comparable stall observed outside those explicit boundaries is a first-class performance bug and must not be excused as
  lifecycle noise.**
- [?] **Normal-runtime image-rotation GUI hitch — owner found and repair authored; Windows proof required.** The soak repeatedly
  shows ordinary 3840x2160 rotations spending roughly **28–53 ms** in UI-thread `present_processed_image`, often matching the
  50–72 ms event-loop tail in the same 15 s period. Code trace found a redundant Quick cutover seam: the compute task already
  owns the processed `QImage`, but the UI callback converts it to `QPixmap`, then `QuickDisplayUnit.capture_image()` converts
  it back to `QImage`, RGBA8888 and a ~33 MB Python `bytes` snapshot. Repair now captures the immutable `PresentationImage`
  directly from the processed `QImage` **inside the existing compute task** and publishes that detached value through a new
  DisplayManager contract. Startup/legacy QPixmap seeding remains intact. Same-transform multi-monitor reuse still shares one
  immutable detached value; current/previous-image paths both use the detached seam. Required Windows proof: normal rotations
  must show no `qimage_to_qpixmap` UI stage and `present_detached_image` must collapse toward low-single-digit UI time without
  changing image pixels/DPR/identity, transition source/destination truth, history/accounting, stale-generation rejection or
  scaled-cache behavior.
  **Known remaining copy boundary:** `PresentationImage` still owns a tightly packed Python `bytes` RGBA payload. Moving its
  capture into the compute task removes the proven GUI-thread QPixmap/QImage bounce, but the ~33 MiB bytes materialization
  can still briefly hold the GIL. Do not declare the whole image path solved merely because UI publication becomes cheap.
  The same FINAL churn/acceptance run must verify ordinary image changes no longer create meaningful Python/Visualizer cadence
  spikes. If a residual image-change spike survives while `present_detached_image` is cheap, the next repair is a **Qt-native
  detached image/buffer presentation contract through render-thread texture upload**, not another probe and not retuning the
  Visualizer.
- [?] **Normal-runtime Context Menu hitch — retained-model invalidation owner found and repair authored; Windows proof required.**
  Repeated 75–94 ms event-loop periods align with ordinary context-menu open/hide. The Python `open_at()` path itself is tiny;
  the architectural bug was that `entries`, `menuVisible`, `anchorX` and `anchorY` all used the same `stateChanged` notify.
  Every open/hide therefore notified the QML `Repeater` that `entries` changed, and the getter returns a fresh list-of-dicts,
  allowing the retained menu/submenus to be rebuilt even when only visibility/anchor changed. Notifications are now split into
  `entriesChanged`, `anchorChanged` and `visibilityChanged`; entry delegates invalidate only when the actual immutable entry set
  changes. Keep the aggregate `stateChanged` signal only as non-QML compatibility telemetry. Required Windows proof: repeated
  right-click/open/dismiss should no longer create 50+ ms event-loop tails; menu admission, click-outside swallow, submenu hover
  grace, single-owner policy and theme/shadow appearance must remain identical.
- [x] **R-87 — Qt Quick high-refresh freshness/scheduler regression is OPEN / SIGNIFICANTLY IMPROVED ON CHECKPOINT 3, NOT SOLVED.** The durable incident record is `Docs/Historical_Bugs/R-87_QtQuick_HighRefresh_Freshness_And_Scheduler_Regression.md`; it embeds the critical readings so future work does not depend on log archives surviving. Smooth-control D0 Bubble was ~164.6 FPS / 0% median skip / ~10.1 ms drawn-state age at ~90 logical revisions/s; SettingsLifetime shifted to ~155.7 / ~3% / ~17.8 ms with the producer and pacer/render bridge materially unchanged. The long supervisor soak proves the current architecture can still reach ~166 FPS / ~9–10 ms age when Windows is quiet but collapses under UE5-class pressure to ~121 FPS / ~19% skip / ~22 ms age. The one-process shared-COMPUTE A/B recovered comparable-pressure D0 to ~134 FPS and cut app threads from ~113 to ~97, but did not close freshness. D1 is decisive against a naive 90-FPS bandage: under pressure Edit already rendered ~102–111 FPS while drawn Bubble state remained ~28–30 ms old; a later low-pressure Edit observation reached ~256.5 FPS. The smooth control could feel good around 60–61 D1 FPS with ~7–15 ms age. Judge the chain `produce -> publish -> Quick sync -> draw`, not FPS alone.
- [~] **Scaled speculation execution policy — third topology authored, installed proof required.** Preserve the supervisor-owned response-listener infrastructure, but do not keep a speculative child alive merely to use it. The second process was a real headroom tax (~20–30 extra native threads and ~800 MiB extra child private commit). The shared-COMPUTE A/B removed that tax but exposed another false assumption: `TaskPriority.LOW` is passive metadata on a FIFO executor, so 4K `QImage.scaled()` still ran at ordinary OS priority. Current source keeps all R-82 correctness/liveness, single-flight, bounded/latest-useful backlog, byte cap, generation fencing, raw release, QImage-only worker work and foreground authority for Lanczos/sharpen, but routes the derivative through one **lazy ThreadManager-owned serial background CPU thread**. On Windows it requests `THREAD_PRIORITY_BELOW_NORMAL` and disables dynamic wake-up priority boosts before executing best-effort work; if demotion cannot be installed the speculation fails closed rather than silently competing at normal priority. No timer/cadence, no second process, no IPC/shared memory, no generic COMPUTE worker occupancy. This is not closure until low/high-pressure mixed-refresh Windows evidence improves operator-visible smoothness/freshness without reviving R-80→R-86 defects.
- [~] **Gmail/Reddit hidden Repeater delegate forest removed / awaiting installed Qt validation.** Post-hotfix CUSTOM-resize support kept the full data buffer directly in each QML row model. Because Qt Quick `Repeater` instantiates every model entry, the dual run meant Gmail retained 18 rows for a visible limit of 10 and the two Reddit feeds retained 25/24 for visible limits of 20 — roughly **17 unnecessary hidden delegate trees** on Display 0. The larger accepted buffer now stays Python-owned; normal runtime materializes only the authored visible limit into the stable QAbstractListModel, while a CUSTOM vertical content extent conservatively projects additional buffered rows on demand and clearing CUSTOM returns to the exact limit. Fetch/cache capacity, instant CUSTOM expansion, settings SSOT and source cadence are unchanged. This is a documented secondary scene/sync-pressure repair, **not** a claim that 17 delegates explain the whole regression.
- [x] **R-86 forced Quick VSync hypothesis REJECTED / ROLLED BACK.** Source research correctly found that the generic ``swapInterval=0`` policy predates Qt Quick, but the production experiment that forced Quick to ``swapInterval=1`` was physically worse on the operator's two-display mixed-refresh setup: poorer pacing, poorer FPS/headroom, and higher apparent cost for ordinary interactions such as context-menu/Edit entry. This disproves the proposed repair for SRPSS even though the Qt documentation made it theoretically plausible. The Quick bootstrap is restored to the known-good release-era ``QUICK_SWAP_INTERVAL = 0`` contract. Do not reintroduce interval 1 as a generic Quick fix. Multi-window/mixed-refresh Qt scheduling must be treated as its own installed architecture problem; any future surface/pacer change needs an A/B against the known-good 5.0.0/5.0.1 Quick baseline and must improve operator-visible pacing on both 60 Hz and high-refresh windows without reducing Visualizer freshness/reactivity. ``QuickFramePacer`` remains architecture debt worth reviewing, but because it is unchanged from 5.0.1 it is not the primary fresh-regression suspect and must not be retuned blindly.
- [x] **CUSTOM Edit Save teardown regression — second exact cause repaired / INSTALLED VALIDATION GREEN.** The earlier call-signature `TypeError` masking bug remains repaired and typed. The fresh two-display run exposed a different deterministic combination: the Visualizer had coherently hopped **LG -> MSI**, System Stats was disabled in the same Edit transaction, and Save classified the ordinary retirement as `family_presence_changed`, queued `save_continue`, and tore down **1037 Qt objects** even though each operation is independently retained-safe. Root cause: `_presence_change_live_commit_is_coherent()` rejected display/monitor changes on *unrelated* session items before checking whether that item's presence changed. It now scopes route stability to the family being retired; the independent Visualizer transfer still must pass `_cross_display_transfer_is_coherent()` before live promotion. A regression test pins `System Stats disable + unrelated Visualizer transfer => display_transfer`, not `family_presence_changed`, so Save can execute both retained mutations without generation replacement. The SettingsLifetime follow-up logs then proved System Stats and Friend Pulse disable/save both live-retired without generation reconciliation, and multiple two-display Visualizer hops committed live.
- [x] **Settings critical exit after live family disable — Python ownership leak repaired / INSTALLED FOLLOW-UP GREEN.** At 22:53:28 Settings teardown destroyed all **846 Qt objects** and drained resources/work, but after 8 s the barrier still saw exactly one `QuickDisplayPresenter`, then correctly failed closed. The survivor came from the successful earlier Friend Pulse live disable: `retire_live_custom_layout_item()` removed its `OverlayGeometryBinding` from presenter ownership without calling `binding.retire()`. That orphan retains a preferred-size callback self-cycle, and its geometry sink closures capture the presenter; the barrier intentionally does not call cyclic GC to hide ownership mistakes. Mid-generation retirement now resolves the exact binding, retires/disconnects it first, then drops it from presenter records. A Qt regression test pins signal/callback/sink severance. The follow-up runs contain repeated Settings/Edit activity with no recurrence; final dual-display application retirement drained **1001 Qt objects / 4 Python presenter-unit owners in 469 ms**. Do **not** raise the barrier timeout or add `gc.collect()`; explicit ownership release is the contract.
- [~] **System Stats presentation invalidation narrowed; Windows/operator validation pending.** The shared 10 s source remains one low-priority event-driven/reconciliation owner and is not multiplied or sped up. A sample previously emitted broad `stateChanged`, causing QML to reconsider layout/style/config properties on every CPU/RAM/uptime/network update. Dynamic metrics now notify through dedicated `sampleChanged`; structural/config geometry remains on `stateChanged`. This is a direct fan-out reduction, not a slower poll or disabled functionality. Keep awaiting validation until normal runtime evidence/operator feel confirms benefit.
- [~] **Media first Play/Pause click duplicate — symptom contained, originating duplicate edge still under validation.** The torture log proved one initial interaction admitted `operation=play` followed immediately by `operation=toggle_play_pause`, undoing itself. Transport remains event-driven: one semantic command is submitted asynchronously and native GSMTC events/reconciliation update truth; do not convert Play/Pause/Next/Previous to polling. The shared Media owner now coalesces only a second Play/Pause semantic edge inside the same 200 ms input burst, arms only after provider admission succeeds, and logs the suppression. Failed first admission never blocks retry; Next/Previous are untouched. Treat this as `[~]` until the operator/log confirms the first-click double-action is gone and continue to prefer eliminating the duplicate at its originating admission seam over expanding the heuristic.
- [~] **CUSTOM Edit Save no longer treats disable as generation topology where retained owners can retire safely.** Disabling an already-retained ordinary widget now retires that exact presentation and neutral service group in-generation. Disabling the Visualizer now routes through the existing manager-owned Visualizer retirement/failover seam, fencing stale failover work and retiring the single controller/logical/GL owner without replacing DisplayManager. Live saves also advance `DisplayManager._widgets_config_snapshot` to the just-persisted map so an unrelated later topology event cannot resurrect stale enabled state. Incoherent ownership still fails closed to the existing reconstruction path. New admissions/enables remain a separate construction problem; do not generalize them by silently rebuilding unless the retained construction seam is proven impossible.

- [?] **FINAL R-84 diagnostic churn run — no more handle-discovery soaks after this.** Once the image/menu repairs above are in
  the local tree, run one deliberately bounded Windows acceptance session: keep one mode/preset stable; perform **3–5 explicit
  Settings open/close cycles**, allowing ~60–90 s of settled runtime after each, and exercise a few ordinary image rotations and
  context-menu opens between/after cycles. Use `--debug --fresh --usage --perf --life` only; no `--verbose` and no `--gpu-timing`.
  Decision is binary: (A) settled persistent handle classes staircase by ~20–30 each replacement -> treat as a real generation-
  retirement leak and repair those owners directly from existing lifecycle/type evidence, **without asking for another broad
  diagnostic soak**; or (B) only the first replacement steps and later cycles plateau -> close R-84 as one-time lazy/native
  initialization. The same final run is also the acceptance proof for Toolhelp, detached image publication and Context Menu
  notification isolation so the user is not asked for a separate performance soak afterward.
- [ ] **Quick-native startup/legacy image-boundary follow-up — do only after the normal-runtime detached path is proven.**
  There is real architectural value in extending the same ownership rule, but the paths are not equivalent. Startup desktop
  seeding originates from `QScreen.grabWindow(0)`, which necessarily yields a GUI-thread `QPixmap` and is already confined to
  startup/replacement-generation staging; optimize it only if startup profiling justifies the risk. The synchronous legacy
  `load_and_display_image()` / `show_image()` path still publishes QPixmaps and is reachable as a submission/failure fallback;
  after the normal async path is accepted, audit whether that fallback can consume/produce detached `QImage`/presentation state
  directly or be retired. Goal: one Quick-native presentation boundary, with QPixmap confined to genuinely GUI-native capture
  sources. Do **not** widen the current runtime-hitch repair until its Windows acceptance is known.

- [x] **Monitor wake double rebuild explained; no production optimization admitted yet.** Existing display detection already
  coalesces Qt topology/metric/application edges for 250 ms. On wake Windows exposed a genuinely different MSI-only topology
  at 13:46:11 and did not expose the final MSI+LG topology until ~13:46:14, roughly three seconds later. Each generation
  retired cleanly (destruction barriers ~344 ms and ~610 ms). A longer generic debounce would delay real hotplug/removal and
  still cannot reliably distinguish a seconds-long transient wake topology from a genuine one-screen state.
- [x] **Monitor regression/decision gate strengthened (2026-09-14; PySide run still required):** existing tests retain
  same-burst metric/resume coalescing and same-signature resume revalidation; a new two-stage wake test proves MSI-only can
  settle/reconcile first and a later genuinely distinct MSI+LG signature intentionally schedules/reconciles again. This
  explicitly protects against “fixing” the soak with a generic multi-second debounce. Do not add sleep/poll/debounce unless
  later evidence provides a reliable wake-specific settling signal; correctness currently outranks hiding this rare hitch.

- [x] **Previous generic 30–60 minute closure-soak request superseded.** The handle sidecar has already answered the broad
  attribution question; use only the bounded **FINAL R-84 diagnostic churn run** above. Do not ask the user for another hour-long
  discovery soak for this seam.


---

## 4D. Defaults/test authority hygiene — 2026-09-14 audit

The broad §0.18 “value-drift goldens” bucket was too coarse. Ordinary product defaults are intentionally mutable policy,
so tests must validate canonical ownership/parity rather than freeze today’s literal values. This audit is test/docs only:
production defaults and runtime behavior are not changed merely to satisfy assertions.

- [x] Audit the previously classified value-drift files plus a wider defaults/settings sweep. Mutable default expectations
  now derive from `core/settings/default_settings.py` through the canonical read seam or generated authority. Behavioral
  fixture inputs remain explicit test inputs rather than being coupled to product defaults. Exact literals are retained only
  when the literal itself is contractual and carry an adjacent `EXACT-VALUE INVARIANT:` rationale.
- [x] Defuse the Steam cadence trap: Abandonment/Achievement timer tests deliberately use their own short fixture cadence
  (`_FIXTURE_REFRESH_MINUTES`) and derive expected delays from that fixture. The current six-minute Steam product default may
  change without making those behavior tests red; separate authority/parity coverage owns the product default.
- [x] Reconcile non-default fossils misclassified as value drift: remove the retired transition-worker latency cell; align
  policy-compliance coverage with the explicitly permitted generation-owned Visualizer cadence lifetime; update installer
  reset-policy coverage to current installer behavior rather than the retired 5.0.0 migration default.
- [x] Canonical defaults audit and derived-artifact checks remain GREEN after the test rewrite: `check_defaults_authority.py`,
  `regenerate_defaults_artifacts.py --check`, and `regenerate_sst_defaults.py --check`. All 39 edited test modules compile.
  Full pytest execution still requires the intended Windows/PySide6 environment because project `tests/conftest.py` imports
  PySide6 unconditionally.
- [x] **Visualizer transient fallback/default duplication resolved without changing preset technical authority (2026-09-14).**
  End-to-end tracing confirmed the supported Quick lifecycle is configure -> apply complete technical mapping -> bind -> start;
  mode/preset changes stop/join the sole logical runtime before rebuilding/reapplying technical state and restarting it. Curated
  presets remain authoritative for every technical key they author, while Custom remains pass-through user-authored state; only a
  genuinely missing field reaches the model's canonical default. `tick_pipeline.py` therefore no longer invents `1.0/1.5` or
  Bubble `0.75/0.25` tuning, and Spectrum's FFT express lane no longer invents `kick_lane_gain=1.0` /
  `spectrum_lane_transient_mix=0.65`; those consumers require the already-resolved values and expose an ordering/ownership defect
  instead of silently substituting another tuning table. `visualizer_settings_contract.py` now names the old shared/global
  `1.5`-era values explicitly as **legacy migration baselines only**; special per-mode missing values fall through canonical
  authority rather than hard-coded compatibility literals. Pre/post semantic fingerprints across every shipped curated Bubble,
  Spectrum, Sine, Oscilloscope and Dev Curve preset plus arbitrary Custom technical values are byte-equivalent at the resolved
  value layer (SHA-256 `9a17f78e136f57be2e51b317692f0b4282c82b3fe17a61e089188c49f4eaac39`). Regression
  coverage now explicitly proves curated presets may author transient technical controls, Custom preserves them, and downstream
  Bubble/Spectrum consumers cannot regain numeric technical fallbacks. This changes no Bubble/Spectrum equations, tuning, preset
  payload or canonical product default. Retired global values remain untouched as compatibility signatures.
- [?] **Production/schema smell — retired transition worker default:** canonical settings still contain
  `workers.transition.enabled=True` although the supervised transition worker was retired when transitions became GPU/Quick-owned.
  Claude's production grep found **zero current production consumers** across core/engine/rendering/widgets. The remaining gate
  is therefore compatibility only: trace persisted-profile/import/migration handling, then remove the key through canonical
  schema + generated-artifact regeneration if no supported compatibility owner remains. Do not preserve dead schema because
  historical tests once referenced it.
- [x] **Windows/PySide6 mutable-default audit run completed (Claude, commit `f9343b53` preserved):** all **39 changed test
  modules** were executed. Initial result **760 passed / 9 failed**; two failures were defects introduced by the audit rewrite
  itself and were repaired test-only (symmetric nested `collect_diff()` handling plus the missing
  `require_canonical_default` import). Rerun result: **762 passed / 7 failed** with no production/default/artifact change.
  The seven survivors are now classified instead of being called generic value drift: four stale tests
  (`visualizer_bucket_toggles...`, Spectrum bucket order, retired Abandonment no-callers, fake rainbow visibility binding) and
  three real behavior/integration investigations (Spectrum preset-slider/custom index, audio-worker gain-one fixture requiring
  resolved technical config, MC interaction-mode profile behavior). None is a BTF/real-GL case in this set.
- [?] **Small positive-coverage gap from that audit:** Achievement runtime uses the same independent five-minute test fixture
  pattern as Abandonment, but lacks Abandonment's symmetric test proving its runtime default follows canonical
  `widgets.steam.refresh_minutes`. Runtime currently reads the same canonical Steam defaults, so this is coverage debt rather
  than a product defect; add the positive authority test when that test family is next touched.


---

## 4E. CUSTOM Visualizer quarter-turn orientation — feasibility accepted, implementation deferred

Feature request: while CUSTOM Edit mode is active, eligible Visualizers gain a small turn/flip glyph. Each click advances the
content orientation by one clockwise quarter-turn: `0° -> 90° -> 180° -> 270° -> 0°`. Example: a tall Spectrum whose bars
currently travel upward can be turned so the same authored/reactive visualizer behaves as a wide logical viewport rotated into
the tall physical card, with bars travelling right, then down, then left on successive clicks.

This is feasible, but it is **not** a finished-pixel/QML `rotation` feature. Viewport shape is semantic input to Bubble,
Spectrum, Sine, Oscilloscope and Dev Curve; rotating only the final pixels/vertices would bypass existing wide/tall shape
profiles and can break reaction amplitude, density, clipping, line thickness, Bubble tails/specular/gradient behaviour and
other viewport-derived invariants. The feature therefore belongs at the shared Visualizer presentation/layout seam.

- [ ] **Initial scope: carded accepted modes only.** Admit Spectrum, Oscilloscope, Sine Waves, Bubble and Dev Curve. Exclude
  frameless modes and specifically Voxel Sphere initially. Sphere has experimental unclipped overflow, 3-D lighting/shadow and
  its own coordinate semantics; do not make this feature a reason to couple Sphere back into accepted-mode architecture.
- [ ] Add one CUSTOM-layout-owned quarter-turn token, preferably `content_rotation_quarters` constrained to `{0,1,2,3}`.
  It is **layout/presentation state, not a Visualizer setting or preset technical setting**. Persist it inside the Visualizer's
  existing CUSTOM `size_payload`; old entries with no token resolve to `0`. Do not add a second settings authority or mutate
  authored preset payloads.
- [ ] Keep the physical saved geometry authoritative and unchanged. The committed `rect`, monitor route, uniform scale and
  `viewport_extent` remain exactly what the user edited. For `90°/270°`, resolve an **effective logical content viewport** with
  width/height swapped, run the existing mode shape/reactivity logic against that logical domain, then apply one shared
  logical-to-physical quarter-turn transform back into the unchanged card/content clip. `0°/180°` keep the logical axes;
  `180°` changes direction only. This is the critical distinction that lets a tall card behave like a wide visualizer without
  rewriting its stored geometry.
- [ ] Implement the transform once in the common Quick Visualizer render/presentation contract, not separately in five mode
  renderers. Mode-specific code may need only narrowly proven direction-vector adaptation where a shader currently consumes a
  screen-space direction directly (for example Bubble gradient/specular direction); prefer deriving those vectors through the
  common orientation transform rather than adding per-mode orientation settings.
- [ ] Edit UI: add one themed circular turn glyph to `CustomLayoutOverlay.qml`, visible only for the active Visualizer when the
  current descriptor admits quarter-turn orientation. It must not steal drag/resize/display-hop input zones and must remain
  scale/header aligned with existing edit chrome. Clicking changes working session state immediately; Cancel restores the
  admission value, Save commits it, Restore Size must **not** silently reset orientation unless product UX explicitly decides
  that Restore Size owns orientation too.
- [ ] Save/load/slot contract: existing layout slots already capture the whole `custom_layout` root, so orientation must round
  trip through ordinary CUSTOM save/load and slot Save/Load without a parallel slot schema. Cross-display hop must preserve the
  token. Legacy layouts/slots with no token must load identically to today (`0`). Version-bump only if the normalizer cannot
  safely treat the optional size-payload field as backward compatible; do not bump merely because a new optional payload key
  exists.
- [ ] **Golden behavioural proof before merge:** with orientation `0`, resolved presentation/render state must be semantically
  identical to pre-feature behaviour for every accepted mode and curated/Custom preset. Prove quarter-turn does not alter
  audio/reactivity values, preset technical authority, AGC/floor state, authored mode settings, uniform scale or stored extent.
  Add pure transform tests for four-click identity, `90+270 == 0`, axis swap only on odd quarters, Save/Cancel/slot round trips,
  cross-display preservation and legacy-no-token replay. Then run the existing visualizer geometry/reactivity suites plus
  installed eyes-on checks for extreme wide/tall Bubble, Spectrum, Oscilloscope, Sine and Dev Curve. Bubble's current reaction
  amplitude/freshness contract remains golden: no compensation that reduces reaction is acceptable.
- [ ] Performance/lifetime: quarter-turn is event-driven only. No timer, polling, alternate cadence, retained duplicate
  renderer or per-frame settings lookup. Changing orientation may publish/rebuild the normal immutable presentation snapshot,
  but must not reconstruct the Visualizer runtime or create a second logical state owner.

**Risk decision:** medium/high implementation risk but architecturally bounded. Keep in Current Plan because the persistence and
owner seams already exist and the safe shape is clear; do not implement opportunistically during unrelated Visualizer work.
If the common logical-to-physical transform cannot be made mode-neutral without mode-specific geometry forks, stop and move the
feature to `Future_Work.md` rather than compromising the existing viewport/preset/reactivity contracts.

## 5. Test / debris reconciliation

Detailed ownership lives in `Future_Cleanup.md` and `Docs/TestSuite.md`; this active plan carries sequencing only.

- [x] Reconcile the known broad-suite fossil assertions against current owners without changing production authority.
  Completed at the test boundary on 2026-09-13: `test_widget_visual_roles.py` **16/16 PASS**; five touched Widget Theme
  state-machine cases PASS; `test_capability_activation.py` **33/33 PASS**; the four reproduced
  `test_widget_descriptors.py` fossils **6/6 PASS**; and the two GODZIP/AppData persistence fossils **2/2 PASS**. The
  repaired assertions now follow strict schema-v3 I/O, explicit canonical Theme state/defaults, current descriptor/lazy
  dependency ownership, shared Clock authored-position routing, retired Growth semantics, and repo-local Foundry settings
  without banning legitimate LocalAppData-based Git Bash discovery. No production defaults/fallbacks, retired QWidget
  paths, compositor owners, timers or pollers were restored to satisfy tests.
- [x] 2026-09-13 follow-up pure/source contracts: Friend Pulse recovery/dropped-message absence + Restore Size authored-cache separation + System Stats metric-selection/content-extent/pill-width/source skipping execute directly without PySide. Latest focused direct runs: **9/9 System Stats source**, **4/4 System Stats reflow/selection**, **4/4 Friend Pulse/Restore**. Python compilation is clean for all touched Python modules.
- [x] Maintained `destination` profile executed on Windows/PySide6 6.9.1: **132/132 GREEN** (2026-09-14, see
  `Docs/TestSuite.md` §0.17). Every previously deferred red and destination-target NEEDS RUN was reconciled at the
  test boundary against current production; no production owner/default/fallback was changed.
- [x] Broad full-tree fossil-hygiene + reconciliation pass (2026-09-14, see `Docs/TestSuite.md` §0.18). `collect_ignore`
  confirmed empty (no fossil graveyard), 0 collection errors, module count 368→364. Four whole-file fossils deleted and
  fossil cells trimmed/rehomed from ~8 files; a large batch of stale current-owner tests reconciled. Broad per-file
  failures 58→32 files. No production behaviour/default/schema changed; destination profile still 132/132 GREEN.
- [?] Continue the remaining broad-tree reconciliation using `Docs/TestSuite.md` §0.21 as the current classification.
  The old §0.18 “value-drift goldens” bucket has been audited/superseded: mutable-default copies were rewritten to authority,
  several stale policy/migration cells were reconciled, and literal behavioral fixtures were explicitly preserved as test
  inputs. Outstanding reds are now to be treated individually as behavioral/integration work, BTF/real-GL acceptance, true
  documented exact-value invariants, or newly discovered stale tests. Do not preserve a red merely because §0.18 once listed it.
- [ ] Retire the temporary Visualizer `enabled_modes` compatibility migration only after automated persisted-profile/import
  coverage proves supported profiles no longer rely on it. Current runtime/default/UI state remains the canonical
  `widgets.spotify_visualizer.mode_activation` boolean map.
- [ ] Complete caller-proven READY deletion rows in `Future_Cleanup.md` only after their exact caller/test prerequisites are
  satisfied; dormant compatibility-horizon rows remain dormant.

---

## 6. Content-extent resize rollout (in progress, added 2026-09-13)

The chosen model is one **uniform CUSTOM-scoped presentation override** (no settings
mutation): the extent overrides the *effective* count / padding / separator / truncation
while in CUSTOM; the widget's real settings (`limit`, separator/word-count) stay the SSOT
default. One authority per context (setting = default, extent = CUSTOM override), persisted
via CUSTOM `size_payload` + slots, no teardown. Reusable stack lives in
`custom_layout_session` / `custom_layout_owner` / `custom_layout_overlay` /
`CustomLayoutOverlay.qml`, gated by the descriptor `content_extent_axes` field; a family
opts in by declaring axes + consuming `content_extent` in its payload handler + reflowing.

- [x] **Friend Pulse** — both axes; operator-validated.
- [x] **Reddit (reddit + reddit2)** — vertical count ± (buffer up to 25, `limit` = SSOT
  default) then row/separator spread; horizontal = free width-elide. Tested.
- [x] **Gmail** — vertical count ± (buffer up to cap, `limit` = SSOT default) then
  row/boundary-separator spread; horizontal = free width-elide + preferred-width widen.
  Tested.
- [x] **Media — CUSTOM presentation-only horizontal/vertical reflow implemented (2026-09-13).** Media now declares both shared content-extent axes and a family-owned **logical** direct-axis floor of `520×210`. The floor is consumed only by side gestures (projected through the current uniform transform); it does **not** replace the ordinary uniform corner/wheel shrink contract. No Media source owner, cadence or artwork transition owner is added. The only new real setting is `Allow Landscape Artwork`, canonical default OFF; it controls only the artwork aspect cap during CUSTOM horizontal reflow.
- [x] **Media side-handle `QSize` hotfix (2026-09-13):** `CUSTOM_LAYOUT_MIN_WIDGET_SIZE` is a `QSize`; the first Media content-extent floor incorrectly passed that object directly to scalar `max(...)`, producing repeated `TypeError: '<' not supported between instances of 'PySide6.QtCore.QSize' and 'int'` during side drags. The direct-axis floor now derives scalar generic minima via `quick_custom_minimum_size(item).width()/height()` before applying the family logical floor. No QML/layout policy change.
- [x] **Media metadata left-anchor hotfix (2026-09-13):** vertical compaction previously scaled the metadata column around `Item.Center`, so title/artist could visually drift right during CUSTOM reflow even while layout anchors remained correct. Metadata compaction now scales around `Item.Left`; no content-extent geometry, artwork, crossfade, controls, volume or Settings contract changed.
- [?] Installed visual validation: repeatedly horizontal/vertical resize Media through compaction/expansion and confirm Title/Artist stay visually pinned to the intended left edge at all extents/DPRs while artwork, seek/control alignment and volume behavior remain correct.
- [?] **Media side-handle hotfix installed validation:** drag all four direct side handles repeatedly at normal and uniformly scaled Media sizes; confirm no QML/Python exceptions, family floor enforcement remains axis-correct, and corner/wheel uniform resize is unchanged.
  - **Horizontal side resize:** changes only the logical content width at constant uniform scale. Seek track and control bar grow/shrink with the card while retaining alignments; metadata receives the added/removed lane; artwork consumes 35% of extra width while preserving a metadata lane. With canonical-default-OFF `Allow Landscape Artwork`, it is capped at `width <= height` so square is the maximum; enabling the checkbox removes only that shape cap and permits landscape artwork without changing the growth rate, metadata reserve, clipping, crossfade or shadow contracts. The external app-volume accessory keeps its authored horizontal width and does **not** widen from horizontal-only content extent.
  - **Vertical side resize:** changes only logical content height. Section/metadata spacing grows/shrinks with the box, artwork may extend into portrait while retaining the existing inset/mask/clipping/shadow/crossfade contracts, and the top/bottom-anchored volume track becomes longer/shorter with Media height.
  - **Uniform corner/wheel resize:** keeps the one whole-presentation uniform transform, including the external volume child. A side-reflowed logical box keeps its aspect/reflow while the entire result scales.
  - **Direct-axis shrink floors:** side handles no longer collapse Media to the generic 40 px floor. Vertical compaction hides Album first below 255 logical px, then playback-state chrome below 225, before the 210 px floor; Title + Artist and enabled seek/transport remain. Horizontal compaction stops at the 520 px logical outer floor. These are CUSTOM presentation policies, not Settings defaults.
  - **SSOT/guardrails:** `ArtworkFadeImage` remains the sole artwork swap primitive; existing clipping/mask/directional artwork shadow remain untouched. Restore Size clears Media `content_extent` back to canonical authored geometry while preserving CUSTOM X/Y/display. Focused no-PySide Media content-extent/landscape contracts pass **7/7**, Media external-volume/source contracts pass **6/6** (excluding the unrelated absent Steam-logo asset assertion), generated defaults/SST `--check` is GREEN, defaults-authority audit is GREEN, and touched Python compiles.
- [?] **Media installed/PySide validation:** exercise horizontal-only, vertical-only, then corner/wheel resize with and without the app-volume accessory. Confirm seek/control widths and metadata room respond horizontally; with `Allow Landscape Artwork` OFF artwork can reach square but not landscape, then toggle it ON and confirm only the square cap disappears; vertical growth creates portrait artwork + more spacing + a longer volume track; horizontal-only never widens the volume child; direct shrink hides Album then playback state at sane points; Restore Size clears the extent; clipping, rounded mask, directional artwork shadow and shared 520 ms crossfade remain clean across DPR/two displays.
- [ ] **Games You Follow** (future) must ship with both shared content-extent axes in its first retained implementation;
  horizontal/vertical side reflow, corner/wheel uniform scale, row-variant authored geometry, Restore Size, slot replay
  and mixed-DPI transfer are admission requirements rather than follow-up polish.
- Note: padding/separator/truncation are **not** promoted to real settings (Reddit had none;
  promoting would add per-widget schema + migration and risk SSOT). Kept CUSTOM-scoped.

## Standing guardrails

- **Voxel Sphere golden preservation:** current accepted Sphere reactivity/motion/preset behaviour is golden. Keep the mode architecturally isolated; do not retune or migrate it into permanent/shared Visualizer owners unless the operator explicitly requests that work.
- **Visualizer fidelity / scaling (R-69, binding):** extreme CUSTOM geometry must
  never be solved by globally reducing head radius, authored reaction amplitude,
  motion, Ghost/history displacement, or by adding a second viewport/domain
  compensation that makes wide/tall modes less reactive. Bubble is the golden
  reference; tall-Spectrum response protection is equally binding.
- **Live CUSTOM ownership:** CUSTOM outer geometry is Python/session-owned; QML
  reports gesture intent only. One operation publishes one coherent
  rectangle/extent/scale. Visualizer sides = one-axis viewport extent; corners =
  independent X/Y extent; wheel = uniform whole-Visualizer scale. **Save is not a
  teardown boundary.**
- **CUSTOM is global layout mode:** the first widget entering CUSTOM disables authored
  stacking/adjacency globally, including number-key saved-layout load. Visualizer
  preset `Custom` is a separate concept.
- **Media ownership:** GSMTC/event ownership is primary; no fast Media polling or
  process-probe fallbacks. Visualizer consumes Media admission but never acquires a
  second Media owner.
- **Performance admission:** the operator-visible Qt Quick smoothness regression is ACTIVE. Bubble is a canary only. Preserve logical freshness/reactivity; compare like-for-like settled frame/presentation-age tails and prefer fewer/event-owned mechanisms over polling. See `Docs/Guardrails/Performance_Optimization_Contract.md`.
- **Defaults SSOT:** `core/settings/default_settings.py` is the sole authority;
  `.json`/`.sst` are derived and audit-gated. Never add a second default authority.
- **Settings styling authority (dark.qss retired 2026-09-14):** `themes/dark.qss`
  is physically deleted and the retirement is operator-accepted. Settings/tray
  styling draws structure from narrow permanent renderers and semantic values
  from `SettingsThemeSpec`. Never reintroduce a monolithic Settings QSS file or a
  fallback stylesheet loader, even when the asset is absent.
- **Visualizer preset ownership:** per-mode preset files are user-authored state. Users may add arbitrary counts, delete down to one, and leave sparse authored numbers. Runtime compacts them into slider positions without renaming/deleting files. A shipped preset manifest is packaging/reconciliation metadata, never runtime authority over user-authored presets.
- **No fallback architecture:** failures should remain explicit and diagnosable; do
  not solve closeout work by adding silent fallback ownership, timers, or pollers.

## Authority order

```text
exact current source + current reconciled test tree
-> Current_Plan.md (this file: active work + order)
-> Spec.md
-> FWPlan.md (future / non-blocking implementation)
-> Future_Cleanup.md / Docs/TestSuite.md (cleanup + test truth)
-> Index.md + focused/decomposition docs
```

## Durable references

- `Index.md` — routing map to current owners.
- `Docs/TestSuite.md`
- `Future_Cleanup.md`
- `FWPlan.md`
- `Docs/Future_Work/Steam_Friend_Pulse.md`
- `Docs/Future_Work/System_Stats_Widget.md`
- `Docs/Future_Work/Settings_Dark_QSS_Retirement.md`


**Continuation checkpoint 12 candidate (2026-09-15):** the CHK10 Oscilloscope blank-card regression is now rooted in the serial FFT lane rather than Quick presentation or WASAPI restart success. Installed evidence showed raw waveform identity reaching activation 4/4 while `[AUDIO_LANE]` counters froze at 8456 accepted / 8456 completed / 8455 published and the logical visualizer kept ticking ~90 Hz. The prior boolean/same-activation release heuristic could orphan `_compute_task_active=True` when the final old FFT completed inside a stopped-runtime activation transaction after the compute gate changed but before the activation id committed. Analysis submissions now carry unique slot tokens; callbacks may release only the token they actually own. Busy `lane.submit()` rejection restores the previous real owner instead of letting a rejected token steal it, and stopping a lane clears token + active + pending-source state because stopped lanes suppress callback delivery. Oscilloscope/Sine while playing now require a matching authoritative analysis timestamp as well as generation identity; paused authored idle remains allowed. Direct real-engine race checks prove both sides of ownership (old callback cannot release a newer token; old owner can release itself and hand off to a fresh activation), busy-rejection ownership, and stop cleanup. Runtime-purity/frame-trace/service authority remain **29/29 GREEN** and all **896 Python files compile**. This repair deliberately leaves audio block-size/capture semantics unchanged so it does not mix a proven compute-owner fix with a speculative capture rewrite. After CHK12 packaging, return immediately to performance validation: D0 native transition-driver validation, then D1 `QUICK_SYNC_READY -> RENDER_BEGIN -> RENDER_DRAW` localization.


**Continuation checkpoint 13 packaged (2026-09-15):** after CHK12 isolated the hotswap/FFT-slot repair, performance-tooling work resumed without changing renderer behavior. `tools/frame_trace_report.py` now reports per-window **n + median + p95** for `QUICK_SYNC_CONSUME -> QUICK_SYNC_READY` (sync work), `QUICK_SYNC_READY -> RENDER_BEGIN` (post-sync/pre-render-callback render-entry interval; not a pure scheduler wait), and `RENDER_BEGIN -> RENDER_DRAW` (Python/OpenGL render body), so the next routine D1 trace can decide the C++/QRhi question from evidence instead of averages. The closed visualizer-switch A/B/C harness no longer treats `pacer_skip_pct` as causal: CHK10 deleted the Python deadline pacer, so that legacy field is informational only and cannot trigger a verdict; 20 direct harness tests pass. `--perf` now emits legacy `pacer_skip_pct=-1` plus `pacer_native_tick_hz` and `pacer_update_request_hz` sampled once per HUD window from the QML driver counters, giving D0 installed validation a direct measure of native tick opportunities versus actual transition update requests with no Python per-frame callback. Historical R-87 wording has been corrected so the old `frameSwapped -> requestUpdate()` loop is unmistakably historical/superseded.


**Continuation checkpoint 14 packaged (2026-09-15): render-body localization before another installed run.** CHK13 is the current safe packaged authority. No renderer/pacing behavior has been optimized in this slice. The live `QuickFramePacer.describe()` contract no longer carries permanent-zero ghosts from the deleted Python deadline/swap pacer (`skipped_deadlines`, `frame_swaps`, `update_pending`); historical PERF log parsing remains backward-compatible through `pacer_skip_pct=-1`. `--frame-trace` keeps binary format/version 1 but adds optional render-only events: `RENDER_PREP_READY`, `RENDER_HOST_BEGIN`, `RENDER_GL_STATE_READY`, `RENDER_MODE_BEGIN`, `RENDER_MODE_READY`, `RENDER_HOST_READY`. With tracing absent these create no worker/file/cadence and no trace records. With tracing enabled, one ordinary D1 light -> heavy run can now split the existing `RENDER_BEGIN -> RENDER_DRAW` interval into node preparation, clip admission, render-host/state capture, GL state setup, actual mode renderer, state restore, and post-host bookkeeping. The offline reporter prints full-run sub-stage distributions and timeline n/median/p95 for render preparation, host total, mode draw, and post-host work. Direct source validation is **51/51 GREEN** (12 runtime purity + 13 frame trace + 6 scheduler/service + 20 retained A/B/C harness); all **896 Python files compile**.

**Continuation checkpoint 15 assessment (2026-09-15): the CHK14 installed D1 torture run is analyzed/frozen as the CHK15 evidence checkpoint; CHK15 itself adds no new runtime trace or production optimization.** Evidence archive: `cfdabe39-1d4c-4682-8335-56e5f1964c7d.zip` (runtime source head `22dd8d4d4c5290e5a82f6bcea9f6555e9fd8ae78`). The operator intentionally withheld subjective smoothness while this assessment was formed. Trace health is excellent: **1,710,531 records, 0 dropped, 0 write errors**. System-load telemetry gives a clean light control before ~18:54:44 and sustained heavy external CPU pressure near ~40% afterward. Clean Bubble light settled (`18:46:50–18:54:20`) is **8.64 ms median / 13.25 ms p95 publication→draw**; clean heavy settled after the torture (`19:02:45–19:06:50`) is **13.28 / 17.02 ms**. Crucially, the heavy delta is not dominated by Python sync or the visualizer renderer: `QUICK_SYNC_CONSUME→READY` is only **0.030→0.065 ms median**, while `GUI_SNAPSHOT→QUICK_SYNC` p95 grows **5.86→8.08 ms** and `QUICK_SYNC_READY→RENDER_BEGIN` p95 grows **1.53→7.09 ms**. `RENDER_BEGIN→DRAW` is **2.39/5.51 ms light vs 1.66/6.78 ms heavy** (median/p95); actual mode draw is secondary (**0.31/2.53 vs 0.25/4.31 ms**), and inherited GL-state capture is specifically **not** implicated (**0.21/0.43 vs 0.13/0.29 ms**). Therefore the bounded C++/QRhi seam and GL-state-fence removal are **shelved, not next actions**. The primary R-87 target is now Qt/render-thread scheduling/admission under external CPU contention, especially snapshot→sync and sync-ready→render-begin tails. The GUI wake remains comparatively small (**0.10/0.66 ms light vs 0.43/2.49 ms heavy**).

Installed torture validation also materially closes two side questions. CHK12 hotswap ownership survived **24 mode activations / four complete Bubble→DevCurve→Sphere→Spectrum→Oscilloscope→Sine→Bubble cycles**, including Settings reconstruction; all eight Oscilloscope/Sine activations acquired finite live source age (~8–10 ms), fresh authoritative frames continued, and the audio analysis lane advanced continuously with zero busy/stopped/cancelled submissions. CHK10's mixed-refresh transition gate is physically healthy on D1: during transition-active samples the Qt animation driver ticks near the primary-screen ~166 Hz, but the D1 retained-background update-request rate stays near **60 Hz**, Bubble revisions remain ~90/s, and visualizer draw rate rises only ~90→93/s instead of reproducing the old unbounded feedback loop. D0 high-refresh overdrive removal still requires a D0-only installed confirmation; do not request another dual-display run.

The torture itself leaves **no persistent degradation signature**: heavy pre-torture publication→draw was **13.72/16.90 ms**, heavy settled after the mode/shape/Settings churn is **13.28/17.02 ms**, and after the second Settings teardown/rebuild it is **13.97/16.91 ms**. All runtime destruction barriers complete, QML capture records zero messages/warnings/errors, native-fault capture is empty, frame trace loses zero records, and the async log writer reports zero dropped records/write errors. Treat Settings/widget/mode churn as validated lifecycle stress for this run, while retaining normal caution that logs cannot certify every visual detail.

**CHK15 next-order lock:** (1) package this evidence-only checkpoint before production work; (2) research/attribute Qt render-thread scheduling under CPU contention using the existing render-thread identity and low-rate Windows telemetry—do not add another hot-path logger; (3) prefer native scheduler evidence (Ready/Waiting/Running, context-switch/readied-by and priority evidence) before changing scheduling policy; (4) keep C++/QRhi and GL-state-fence changes inactive unless a future trace reverses this run's stage attribution; (5) D0-only eventually confirms native transition update-request rate on the 165 Hz display; (6) the **first scheduler-attribution capture may be D1 pure-heavy only** because CHK14 already provides the light control; use light again when validating a production candidate, not merely to rediscover the baseline; (7) subjective operator feel may be collected only after this blind assessment is preserved.**

Research lock for this candidate: Qt 6 `QSGRenderNode` documentation says render nodes must assume arbitrary incoming native graphics state, `QQuickWindow` says external-command boundary handling is implicit for `QSGRenderNode`, and Qt 6 says `changedStates()` is effectively relevant only for viewport/scissor under the QRhi renderer. SRPSS currently performs a full `_InheritedGlState.capture()`/restore with multiple `glGet*` calls on every visualizer draw. That is now a **measured candidate, not an attribution**. Do not delete the fence merely because documentation makes it look redundant; the next trace must show whether render-host/state work actually dominates. Likewise, a bounded C++/QRhi seam remains conditional: activate it only if installed evidence shows render-host/mode-render cost is the heavy-load delta, not merely because Python virtual rendering crosses the PySide/Shiboken boundary.

**Secondary CHK15 anomaly — rotation-timer gap oracle:** `screensaver_perf.log` reports two very large `_on_rotation_timer` gaps (~172,987 ms around 18:55:22 and ~152,734 ms around 19:05:29), classified as `unknown_ui_thread_stall`. These occur amid manual/image-transition/reset activity and are not mirrored by the visualizer freshness/lifecycle evidence, so **do not attribute them to R-87 or call them real UI stalls yet**. Audit the rotation-timer gap oracle/reset semantics separately after the scheduling investigation; determine whether manual rotation / timer re-arm legitimately invalidates its expected-period baseline. Preserve as a secondary diagnostic smell, not a reason to alter the working Quick architecture.

## 19. Performance baseline history — CHK15 -> CHK23 -> CHK26 current GOLDEN

**Baseline decision (operator-confirmed 2026-09-15): CHK15 is now the performance baseline to defend.**
The blind telemetry assessment was completed before subjective feedback. Afterward the operator reported that the mixed-refresh
heavy run felt **great on both displays at all times**, with **no noticed crawl**, and that slide transitions — historically the
strongest heavy-load canary — were **almost perfectly smooth**. D0 also remained visually smooth even though Bubble's fresh logical
cadence correctly stayed near its authored ~90 Hz on the 164.835 Hz panel.

This changes the remaining R-87 work from "rescue visible smoothness" to **increase scheduling headroom without sacrificing any
of the performance/freshness already achieved**.

### 19.1 Neutral-or-better admission rule — binding
Any scheduling-starvation experiment must be **neutral or better** against CHK15 on both objective and operator-visible behavior.
A patch is rejected if it improves one internal metric while worsening freshness, latency, visual smoothness, hotswap/lifecycle
stability, transition smoothness, or mixed-refresh behavior.

Golden installed evidence to preserve on like-for-like runs:
- D1 single-display heavy settled Bubble: publication→draw roughly **13.3 ms median / 17.1 ms p95**;
- D1 mixed-refresh heavy Bubble: roughly **12.6 / 16.9 ms**;
- D0 mixed-refresh heavy Bubble: roughly **7.5 ms median / 25.4 ms p95** — low median with bursty scheduling tails, but **no
  operator-visible crawl in the accepted CHK15 run**;
- Bubble logical cadence remains authored at roughly **90 revisions/s**; do not raise or lower it to game presentation metrics;
- D1 transition update requests stay near its physical opportunity (~60 Hz) despite the global Qt animation driver ticking near
  the high-refresh display; D0 must not regress toward the historical ~287 draw/request runaway;
- trace/log writers remain lossless in acceptance evidence (**CHK14 D1 torture trace adopted/frozen by CHK15:** 1,710,531 trace records, 0 dropped, 0 write errors);
- CHK12 slot-token hotswap ownership remains intact: repeated mode swaps, Oscilloscope/Sine live readiness, Settings teardown/
  rebuild, widget disable/re-enable and shape changes must not strand the audio/visualizer runtime;
- **slides/transitions and ordinary visualizer motion must remain at least as smooth as CHK15 to the operator.** A statistically
  cleaner trace that looks worse is a regression.

### 19.2 Primary remaining target — render-entry ownership/GIL headroom
The one-off CHK16 Windows scheduler-attribution run has now answered the first fork. **Ordinary Windows runnable starvation is not
the primary residual in the captured D1-heavy condition.** The CHK15 golden baseline remains healthy; this is headroom attribution,
not rescue work.

Installed scheduler evidence from the 60.101 s D1-heavy capture (render TID `14044`):
- render thread **Waiting 63.920% / Running 35.050% / Ready 1.004%** of wall time;
- Ready->Running latency **0.0026 ms median / 0.0049 ms p95 / 0.0732 ms p99**;
- `QUICK_SYNC_READY -> RENDER_BEGIN` **1.9918 / 5.5349 ms median/p95** in that capture;
- in that render-entry interval, all samples were ~**76.9% Running / 22.3% Waiting / 0.7% Ready**; the p95 tail was
  ~**42.8% Running / 55.3% Waiting / 1.9% Ready**.

Therefore:
1. **Retire blind render-thread-priority escalation.** The thread is almost never sitting runnable and denied CPU long enough for
   priority to explain these tails. Do not spend an A/B on priority unless later evidence materially reverses this result.
2. Stop calling `QUICK_SYNC_READY -> RENDER_BEGIN` a pure "scheduler wait". It spans Qt scenegraph work after the Python sync
   callback plus the eventual Qt->Python `QSGRenderNode.render()` callback entry. Running and Waiting time inside it can therefore
   reflect Qt work, resource/event waits, and Python callback/GIL admission.
3. The wait-ending threads during that interval are mostly SRPSS threads sharing a **CPython-created thread bootstrap** with a
   known worker (~86.7% of Waiting time overall; ~81.1% in the p95 tail). This is a concrete Python/GIL-contention hypothesis,
   **not proof of a specific pool**: a shared Windows start routine does not identify `io_pool`, audio analysis, or another worker.
4. The next smallest diagnostic seam is frame-trace-only: correlate render-entry tails against the existing visualizer analysis
   compute lane and, separately, its pure-Python smoothing section. No WPR/ETL repeat is planned.
5. C++/QRhi remains shelved. This trace does not make `QSGRenderNode.render()` body cost dominant and does not justify moving the
   renderer merely because Python participates in the callback.

### 19.2A CHK16 scheduler-attribution lane — CLOSED after one physical run
CHK16 added the external WPR lane and it has served its purpose. The one expensive raw ETL was successfully reduced locally;
**do not request another raw ETL upload or include one in a GODZIP.** `tools/scheduler_trace_reduce.py` emits the small
`scheduler_attribution.json/.txt` handoff evidence. `tools/scheduler_trace_capture.py` now treats a raw ETL as local-only,
automatically reduces it when SRPSS logs are supplied, and deletes it after successful reduction unless `--keep-etl` is explicitly
requested for local WPA/deep-dive work.

The reducer independently reproduced the installed attribution above and classified ordinary OS runnable starvation as
`not_supported_by_trace`. The old priority-boost decision branch is therefore closed for this evidence set.

### 19.2B CHK17 trace-only render-entry/Python-overlap seam
CHK17 adds four **explicit-`--frame-trace`-only** events; ordinary runtime still receives `current_frame_trace() is None` and gains
no timer, thread, pacer or polling authority:
- `AUDIO_ANALYSIS_BEGIN/READY` brackets `compute_bars_from_samples(...)`;
- `AUDIO_SMOOTH_BEGIN/READY` brackets `_smooth_analysis_bars(...)`, the deliberately useful pure-Python section.

`tools/frame_trace_report.py` reports both durations and overlap with `QUICK_SYNC_READY -> RENDER_BEGIN`, for all gaps and the
p95 tail. The CHK17 physical D1-heavy run has now been completed, so this seam is **evidence, not pending work**:
- trace health: **299,893 records / 3 dropped / 0 write errors**; no WPR/ETL was involved;
- this run was under materially stronger external CPU pressure than the CHK14 golden-heavy window (system CPU roughly **55%** for
  much of the settled run versus roughly **40%** in CHK14), so its absolute freshness numbers are not a like-for-like baseline
  replacement;
- settled CHK17 render-entry remained around **5.32 / 8.89 ms median/p95**, while `RENDER_BEGIN -> RENDER_DRAW` remained secondary
  at roughly **1.94 / 7.40 ms**; the full-run reporter gives render-entry **5.310 / 8.934 ms**;
- `_smooth_analysis_bars(...)` is effectively exonerated: **0.036 / 0.067 ms median/p95** and only **0.26% of all render-entry gap
  time / 0.42% of p95-tail gap time**;
- whole analysis is associated with longer gaps but cannot explain most of them: analysis itself is **1.899 / 3.264 ms**, overlaps
  **12.77% of all gap time / 21.49% of p95-tail gap time**, and analysis-overlapping gaps are **6.664 ms median** versus **2.875 ms**
  when no analysis interval overlaps;
- render entry does **not** cluster immediately after analysis/smoothing completion strongly enough to claim that either measured
  function directly gates the callback.

Therefore do **not** optimize smoothing, lower analysis cadence, lower Bubble cadence/reactivity, or alter authored visual behavior.
The useful new clue is the stable ~**5.3 ms** render-entry median under the stronger load, close to CPython's ordinary ~5 ms thread
switch interval and consistent with the pre-existing GIL-contention harness/history. That is correlation, not proof, so CHK18 uses
one bounded, reversible installed A/B rather than making an interpreter-policy change permanent.

### 19.2C CHK18 bounded CPython-timeslice A/B — PHYSICAL RESULT: REJECTED
The requested D1-heavy B run completed with `--gil-switch-1ms`, and startup confirmed the process changed from **5.000 ms -> 1.000 ms**.
This experiment is **rejected** and the flag is removed again in CHK19; it must not become interpreter policy.

Targeted comparison against CHK17:
- render-entry `QUICK_SYNC_READY -> RENDER_BEGIN`: **5.310 / 8.934 ms** default versus **5.592 / 8.905 ms** at 1 ms — median
  slightly worse, p95 effectively unchanged; the ~5 ms plateau did **not** collapse;
- audio analysis: **1.899 / 3.264 ms** -> **3.724 / 5.519 ms**, materially worse; smoothing stayed ~**0.036 / 0.066 ms**;
- audio-lane telemetry near the end of the runs shows the mechanism: handoff mean improved ~**3.30 -> 1.40 ms**, while execution
  mean worsened ~**2.07 -> 3.78 ms**. The shorter global switch interval mostly redistributes wait into more frequent Python execution
  preemption rather than producing headroom;
- publication->draw median moved only **15.331 -> 15.086 ms**, while p95 worsened **18.902 -> 22.771 ms**; this cannot qualify
  as a neutral-or-better optimization;
- trace loss rose from **3 -> 95 dropped records** (still a tiny fraction, but directionally negative);
- Bubble logical cadence remained near authored ~90 Hz.

Conclusion: the stable ~5 ms render-entry floor is **not explained by CPython's global switch quantum alone**. Do not reduce Bubble/analysis
cadence, do not optimize smoothing, and do not revisit a permanent `sys.setswitchinterval()` policy.

The detailed result is frozen at `.godzip/CHK18_GIL_SWITCH_AB_RESULT.md`.

### 19.2D CHK19 native Qt timing — PHYSICAL RESULT / observer retired
The requested CHK19 D1-heavy run completed. The operator also ran one manual **Burn** transition; it is cleanly identifiable from
**22:38:27 -> 22:38:36** (~8.535 s) and is kept separate from steady-state attribution rather than averaged into it.

Qt's native threaded-render-loop output reports, across the full capture, roughly **10 / 17 ms median/p95 total**, split into
**0 / 4 ms sync**, **9 / 14 ms render**, and **0 / 4 ms swap**. Component-time share is approximately **88.3% render**,
**5.3% sync**, **6.4% swap**. The transition behaves like a genuine render stressor rather than changing scheduling ownership:
- steady pre-transition native render: ~**7.96 ms mean / 13 ms p95**;
- Burn transition: ~**9.77 ms mean / 17 ms p95**;
- steady post-transition: ~**7.83 ms mean / 12 ms p95**;
- native sync/swap barely move across those slices.

This does **not** authorize treating the absolute Qt numbers as a new baseline. `QSG_RENDER_TIMING` emitted **26,791** high-rate
`qt.scenegraph.time.*` DEBUG records during the run (roughly five messages per rendered frame). SRPSS's Qt-message capture writes/flushes
those records synchronously and CHK19 also echoed them to the terminal. The observer therefore perturbed the very render threads being
measured. CHK20 retires the in-app `--qsg-render-timing` admission; the old token remains parser-filtered as a compatibility no-op,
`tools/qsg_render_timing_report.py` remains only to preserve/reduce the historical CHK19 evidence, and externally enabled scenegraph-time
DEBUG chatter is no longer echoed to the terminal. Do **not** request another CHK19-style run.

The phase attribution is still useful because it is qualitative and agrees with the prior ETW evidence: the residual is in Qt's native
**render phase**, not ordinary Windows Ready starvation and not predominantly native sync/swap. More importantly, this corrects the old
label on `QUICK_SYNC_READY -> RENDER_BEGIN`: that interval begins after the visualizer item's `updatePaintNode()` finishes, but
`VisualizerRenderNode.render()` is reached only later while Qt is already traversing/rendering the scene. It therefore contains native
scene rendering **before the visualizer node**, not a pure scheduler/callback wait.

The internal visualizer trace remains broadly CHK17-shaped despite the noisy Qt observer: CHK17 vs CHK19
`RENDER_PREP_READY -> RENDER_HOST_BEGIN` is ~**0.657 / 5.798 ms** vs **0.549 / 5.638 ms**, and actual mode draw is
~**0.298 / 3.162 ms** vs **0.318 / 3.911 ms** median/p95. Bubble itself did not suddenly become an ~8 ms renderer.

### 19.2E CHK20 predecessor-render attribution — trace-only, no dedicated A/B required
The next attribution is folded into the already explicit binary `--frame-trace`; it is **not** another timing logger and does not require
a dedicated physical run immediately. Five events bracket the earlier full-screen `BackgroundRenderNode`, which is z=0 and therefore
renders before the visualizer presentation subtree:
- `BACKGROUND_RENDER_BEGIN`;
- `BACKGROUND_TEXTURE_READY`;
- `BACKGROUND_DRAW_BEGIN`;
- `BACKGROUND_DRAW_READY`;
- `BACKGROUND_RENDER_READY`.

The markers use a node-local render sequence for pairing and put the transition run id in `auxiliary` (`0` = steady background).
`tools/frame_trace_report.py` reports background total/texture/setup/draw/post stages, splits steady versus transition frames, and measures
how much of `QUICK_SYNC_READY -> RENDER_BEGIN` overlaps predecessor background rendering. They exist only when `--frame-trace` was
explicitly admitted; ordinary runtime retains no sink and no per-frame record calls.

This is the first target because scene ordering proves the background node precedes the visualizer and its steady base path performs
Python/OpenGL work, including inherited GL-state queries/restoration. **Do not optimize/remove those state fences merely because they
look expensive or because Qt documentation permits fewer declared states.** Measure first; correctness of retained Quick/GL state remains
a golden constraint. The visualizer clip/stencil setup also retains a reproducible p95 tail and remains a secondary measured seam after
predecessor attribution.

The operator **did run CHK20 immediately**, so the predecessor fork is now answered. The D1-heavy trace contains **221,756 records / 7 drops / 0 write errors**. Steady background rendering is **0.460 / 5.672 ms median/p95**; transition background rendering is **0.802 / 6.633 ms**. Background rendering overlaps **100%** of measured `QUICK_SYNC_READY -> RENDER_BEGIN` intervals and consumes **24.91% of all interval time / 43.59% of p95-tail interval time**. Transition-owned background work accounts for only **2.46% / 5.37%** of those durations, so the large predecessor tail exists in ordinary steady frames and must not be "fixed" by weakening transitions. The dominant background stage is its Python/OpenGL draw path (**0.314 / 5.498 ms steady**). Detailed evidence is frozen at `.godzip/CHK20_BACKGROUND_PREDECESSOR_RESULT.md`.

### 19.2F CHK21 retained-background candidate — remove avoidable steady Python redraw
CHK20 justifies a production candidate rather than another micro-instrumentation A/B. An unchanged wallpaper is retained content, yet the old steady path re-entered Python/PyOpenGL through `BackgroundRenderNode.render()` on every visualizer-driven scene render. CHK21 changes **only steady background ownership**:
- steady presentation uses a Qt-native retained `QSGImageNode` created/synchronized on the render thread from the same immutable `PresentationImage` authority;
- a persistent custom `BackgroundRenderNode` remains in a sibling `QSGOpacityNode` branch for authored transitions, proof rendering and pixel-oracle harnesses;
- opacity 0 blocks the inactive subtree, so steady frames do not invoke the custom Python render callback while transition frames preserve the old renderer exactly;
- the custom node is not destroyed at every transition edge; its programs/VAO stay warm and only duplicated custom presentation textures are released when returning to steady native presentation;
- reveal/readiness still becomes eligible only through the existing frame-swapped readiness path; native texture admission alone does not add a show/update feedback loop.

This candidate does **not** alter Bubble cadence/reactivity, visualizer rendering, transition duration/progress, per-display transition gating, `_InheritedGlState`, QWidget/QPixmap fallback policy, or image-processing authority. It is specifically the removal of measured avoidable steady predecessor work. Qt documents `updatePaintNode()`/QSG ownership as render-thread scenegraph work, `QSGImageNode` as the native textured-content primitive, and zero accumulated opacity as a blocked subtree that is not rendered.

**Installed acceptance run is now the active next action, not optional idle work.** Use routine D1 heavy + `--frame-trace`, include at least one ordinary image change/transition and one Settings teardown/rebuild in the same run. Expected proof: steady frames have no `BACKGROUND_*` custom render records while visualizer records continue; `BACKGROUND_*` appears only while the transition/proof branch is active; there are no black flashes, transition regressions, lifecycle/resource errors or stale images; publication/freshness is neutral-or-better; and operator smoothness is neutral-or-better. A numerical improvement that feels worse is rejected.

At the CHK21-candidate stage, CHK15 / `0abc479c52` remained the golden rollback/bisect baseline until installed validation passed.

### 19.2G CHK21 installed single + mixed-refresh acceptance pair — PERFORMANCE WIN, HISTORICAL HOLD LATER LIFTED BY CHK23
The operator completed both a heavy D1 single-display run and a heavy mixed-refresh D0/D1 run, including a live visualizer display hop during custom-layout edit. **No black flash occurred.** The retained-background signature is physically correct: steady visualizer frames contain no custom `BACKGROUND_*` rendering; those records exist only while the authored transition/custom branch is active. Bubble stays ~89–90 logical revisions/s.

Compared with the immediately preceding CHK20 D1-heavy settled window, CHK21 materially improves the targeted path:
- publication->draw **15.284 / 18.916 -> 14.144 / 16.497 ms** median/p95;
- publication->swap **16.045 / 22.415 -> 14.827 / 17.272 ms**;
- `QUICK_SYNC_READY -> RENDER_BEGIN` **5.633 / 8.936 -> 4.412 / 6.647 ms**;
- main-process CPU falls from roughly ~105–108% to ~98% in comparable settled heavy sampling.

Mixed-refresh behavior also survives. D0 transition-excluded steady publication->draw is about **7.048 / 24.126 ms**, effectively neutral/better versus CHK15's ~7.5 / 25.4 ms reference. After the live hop to D1 and edit save, the settled D1 window is about **13.642 / 16.160 ms** publication->draw. The hop/save, transitions and final lifecycle barriers are clean; there is no fallback/resource/QObject/render error.

**Do not promote CHK21 over CHK15 yet.** The operator reports context menu and entering/leaving/using edit mode felt *slightly less responsive*, although all remained functional. Objective event-loop timing does not corroborate a broad GUI regression (CHK21 D1 steady p95 commonly ~2.5–3.0 ms versus CHK20 ~4.1–4.7 ms), and CHK20->CHK21 does not change context-menu/custom-layout logic, so the causal link is unproven. Under the neutral-or-better rule the subjective signal remains an acceptance hold rather than being overruled by metrics.

The supplied pair also does not show a post-startup Settings teardown/rebuild generation, so do not claim that one specific CHK21 seam was re-proven here. Detailed frozen evidence: `.godzip/CHK21_ACCEPTANCE_RESULT.md`.

Historical posture at the CHK23 promotion point: **CHK23 promoted the CHK21 retained-background architecture to the then-current GOLDEN forward baseline.** The slight context-menu/edit softness was reported mainly in the intentionally brutal dual-display heavy run, was not present in the single-display run, was not corroborated by event-loop telemetry, and is explicitly accepted by the operator as a likely timing/load-sensitive subjective note rather than a baseline blocker. Preserve the note, but do **not** reopen or roll back the retained-background architecture unless it reproducibly recurs. CHK15 / repository commit `0abc479c52` remains the older immutable rollback/bisect landmark. Detailed promotion evidence is frozen at `.godzip/CHK23_GOLDEN_ACCEPTANCE.md`.

### 19.2H CHK23 GOLDEN acceptance and next headroom seam
CHK23 is a documentation/baseline-promotion checkpoint over the physically validated CHK21 production bytes. No new production behavior is introduced by the CHK23 promotion itself. The accepted D1-heavy retained-background result is approximately **14.144 / 16.497 ms publication->draw**, **14.827 / 17.272 ms publication->swap**, **5.391 / 8.035 ms GUI snapshot->Quick sync**, **4.412 / 6.647 ms Quick-sync-ready->render-begin**, and **2.699 / 7.538 ms render-begin->draw** median/p95, with Bubble still authored at roughly **89–90 logical revisions/s**. The mixed-refresh acceptance also remained healthy: D0 transition-excluded steady publication->draw ~**7.048 / 24.126 ms**, and after the live D0->D1 visualizer hop the settled D1 window ~**13.642 / 16.160 ms**. No black flash, stale presentation, fallback, device-loss, QObject/lifecycle leak or high-refresh transition runaway was observed.

There is still meaningful headroom; do not declare performance work finished merely because CHK23 is golden. The next preferred seam is the **visualizer clip/stencil begin path**, because accepted D1-heavy evidence shows `RENDER_PREP_READY -> RENDER_HOST_BEGIN` at roughly **1.095 / 6.064 ms median/p95**. Source ownership maps that interval directly to `VisualizerClipHost.begin()`. That method performs `_InheritedClipState.capture()` with many synchronous OpenGL state queries, resolves incoming scissor/stencil ownership, and executes the first rounded-clip mask draw; `_draw_mask()` itself captures additional GL state before drawing. This is a large enough p95 tail to justify continued work.

The next agent should **attribute before mutating**: add explicit-`--frame-trace`-only submarkers around clip inherited-state capture, clip/stencil setup, first mask state capture/draw, and clip-end restore where useful; extend `tools/frame_trace_report.py`; then use one routine D1-heavy trace. Do not request dual display unless a candidate actually touches display routing/mixed-refresh/transition ownership. If state-query capture is proven dominant, prefer eliminating genuinely duplicate/locally-owned queries or retaining known state through a bounded clip-host contract. Do **not** delete `_InheritedGlState`, inherited stencil/scissor restoration, or correctness fences solely because Qt documentation says some `changedStates()` flags have limited effect. The accepted rounded clipping and scenegraph state restoration are golden behavior.

If the clip path proves too small or unsafe after attribution, the next larger residual is GUI snapshot->Quick sync (~**5.4 / 8.0–8.6 ms** in accepted heavy evidence), but that is a higher-risk Qt admission/scene scheduling seam and should come **after** the clip host because the clip host has concrete Python/OpenGL ownership and a much smaller blast radius. Mode-render micro-optimization is also secondary unless per-mode traces prove it dominant; never compress authored Bubble amplitude/cadence/reactivity to improve tails.

### 19.2I CHK24 clip-host attribution instrumentation — PHYSICAL RESULT; seam real, first split still too coarse
CHK24 remained **instrumentation only** over the accepted CHK23 production architecture. It did not remove or weaken any clip/state fence, alter Bubble cadence/reactivity, change display pacing, change transitions, or add an ordinary-runtime timer/logger/pacer. The untraced clipped path still calls `VisualizerClipHost.begin(frame, state)` / `end(run)` without constructing a trace context or taking any new timestamps.

The installed D1-heavy evidence (`7c5d8052-e616-416c-8b01-29371d0a8c54.zip`, SHA-256 `5a31d37d7fc77f3b27271785f2858e1fd6344acd5383501e47376571c5b1c755`) validates both the observer design and the target seam. In a clean settled pre-edit heavy window, `RENDER_PREP_READY -> RENDER_HOST_BEGIN` is **1.127 / 6.123 / 7.135 ms median/p95/p99**, essentially the accepted CHK23 **1.095 / 6.064 ms** parent interval. Clean 15 s publication->draw windows are also neutral-to-slightly-better versus CHK23: **13.969 / 15.883**, **13.940 / 16.080**, **13.904 / 16.006 ms** median/p95 versus CHK23 **14.211 / 16.108**, **14.255 / 16.427**, **14.172 / 16.254**. Do not claim a production performance win from those small run-to-run differences; the important result is that the explicit heavy trace did not manufacture the ~6 ms tail.

The user deliberately exercised CUSTOM edit/resize, including a transition that overlapped the start of editing, then later opened Settings to prove teardown/rebuild. Edit ran approximately **00:40:02–00:40:39**. The clip resource guard stayed negligible during edit at about **0.021 / 0.044 ms**, and clip-begin itself was **0.767 / 5.865 ms** across the edit period; excluding the overlapping transition it was **0.924 / 5.984 ms**. Therefore changing viewport geometry does **not** cause stencil-resource reallocation/thrash and is not the owner of the steady tail. The edit/transition period does perturb broader publication freshness/event-loop timing, so it remains intentionally excluded from settled-GOLDEN percentile comparisons.

On the clean pre-edit steady window, CHK24's first split attributes the clip-begin parent approximately as follows: resource guard **0.020 / 0.040 ms**, inherited state capture **0.259 / 2.283 ms**, scissor/stencil setup **0.048 / 1.127 ms**, mask-local state capture **0.101 / 1.467 ms**, the broad first-mask submission bucket **0.124 / 3.795 ms**, mask-local restore **0.017 / 0.486 ms**, and final admission **0.009 / 0.027 ms** median/p95. Inside the actual parent p95 tail, the broad first-mask submission bucket contributes about **39%**, inherited+mask state capture together about **43%**, setup about **11%**, and restoration/finalization the small remainder. There is therefore no single proven trivial owner yet.

Crucially, CHK24's event labelled `mask_draw` was broader than the literal `glDrawArrays()` call: it also contained GL state programming/binding and four uniform uploads. Likewise inherited state capture grouped scissor plus front/back stencil queries, and mask-state capture grouped binding queries with blend/cull/depth/mask queries. That is insufficient evidence for a safe production optimization. Do **not** turn this into a speculative state-fence deletion.

Lifecycle evidence is healthy. The Settings request tears generation 0 down through its lifecycle barrier, generation 1 is reconstructed and returns Bubble to ~90 logical revisions/s, QML capture reports **0 messages / 0 warnings / 0 errors / 0 criticals**, native-fault capture is clean, final application teardown completes, and the frame-trace writer closes at **435,677 records / 4 dropped / 0 write errors**. The user's Settings/reinit seam check therefore found no new ownership regression.

### 19.2J CHK25 clip attribution refinement — trace-only; isolate literal GL query/program/uniform/draw ownership
Preserve CHK24's useful sidecar instrumentation. Explicit `--frame-trace` is intentionally a heavyweight diagnostic lane; markers that remain strictly opt-in, deferred from the measured parent interval, and zero-work in ordinary runtime are durable diagnostic authority and should **not** be stripped merely because the immediate seam later closes.

CHK25 refines the existing trace without changing production behavior or binary trace format. `_InheritedClipState.capture()` is split into **scissor capture**, **front-stencil capture**, and **back-stencil capture** while retaining the exact query order. `_draw_mask()` is split into **binding-state queries** (viewport/program/VAO/array buffer), **flag/mask-state queries** (blend/cull/depth/depth-write/color-mask), **GL state programming/binds**, **uniform upload**, the literal **`glDrawArrays()` call**, and **local restoration**. The same refinement exists for the clip-end mask path. The old aggregate CHK24 stage report remains intact for backward comparison; refined lines appear only when CHK25 events exist.

Source/static authority after this refinement is **58/58 GREEN** (12 runtime purity + 20 frame trace + 6 service/scheduler + 20 retained A/B/C harness), and all **902/902 Python files compile**. Re-running the CHK24 installed binary trace through the CHK25 reporter is byte-for-byte identical because CHK24 has no refined events. Re-running the accepted CHK23 trace with its original 15 s timeline options is likewise byte-for-byte identical.

**Next evidence is one ordinary settled D1-heavy run with explicit `--frame-trace`; edit/resize is no longer required.** A transition or normal interaction is harmless, but obtain at least ~60–90 s of settled heavy evidence. The purpose is now exact: determine whether the persistent ~6 ms p95 clip-begin tail is owned primarily by synchronous inherited-state `glGet*`, mask binding/flag queries, GL state submission, uniform upload, or the literal draw call. Only after that result should CHK26 make a bounded production candidate. If no locally controllable substage dominates enough to justify the correctness risk, stop forcing the clip path and move to the larger GUI snapshot -> Quick sync residual.

### 19.2K CHK25 physical result -> CHK26 bounded shared-GL-state production candidate
The installed CHK25 evidence archive `8aa0507c-fd60-40a0-8770-061c1cf8f3ca.zip` (SHA-256 `5592fb6f95f39b70ca8e4c8cc40c3fab9f9fcfb9ff10c053104561fb2793179a`) closes the attribution-only phase. The trace contains **578,316 records / 2 dropped / 0 write errors**, QML capture reports **0 messages**, native-fault capture is clean, and final lifecycle teardown completes. The run includes both active and later-idle Bubble content; Bubble publication remains in the expected ~89–90 logical-revision/s class.

Whole-run CHK25 `RENDER_PREP_READY -> RENDER_HOST_BEGIN` is **0.805 / 4.929 / 6.079 ms median/p95/p99**. Do not treat the lower median/p95 versus CHK23/CHK24 as a production win because workload/content differs; the important result is the refined ownership. Clean early 15 s publication->draw windows remain healthy at **12.592 / 14.239**, **12.649 / 14.601**, and **12.881 / 14.991 ms median/p95**. `GUI_SNAPSHOT -> QUICK_SYNC` remains a larger independent residual at **5.367 / 6.953 / 10.052 ms** whole-run median/p95/p99.

The literal mask `glDrawArrays()` is **not** the dominant owner. In the full refined begin split its literal draw interval is only **0.018 / 0.108 / 2.609 ms** median/p95/p99. For frames already in the parent p95 tail (threshold ~**4.929 ms**, **855** frames), the largest single dominant-stage owner is GL state programming at **224/855 = 26.2%** of tail frames; inherited scissor capture is **186/855 = 21.8%**; setup is **107/855 = 12.5%**. The synchronous query families collectively remain the largest safe architectural smell: inherited scissor/front/back plus mask binding/flag query stages contribute about **48.5%** of aggregate p95-tail time. The literal draw call dominates only **41/855 = 4.8%** of p95-tail frames. Therefore do **not** rewrite the rounded mask or jump to shader/draw micro-optimization.

Source review reveals a narrower, provably duplicate query pattern around every ordinary clipped render: the first rounded-mask draw captures non-stencil viewport/program/VAO/buffer + blend/cull/depth/color-mask state; `QuickVisualizerRenderHost` then re-queries most of that surrounding state plus blend function/equation state; the teardown mask then re-queries the first mask state again. Stencil/scissor ownership is separate and must remain untouched. The mode host restores the same inherited state before teardown, and visualizer renderers do not own `glColorMask`, so the mask/mode/mask sequence can safely carry one immutable non-stencil inherited-state snapshot through the locally owned operation.

**CHK26 is the first production candidate after attribution.** It introduces `rendering/quick/visualizer/gl_state.py` and moves the former render-host inherited non-stencil fence there. On the ordinary rounded-clipped path, the union of mask + render-host non-stencil inherited state is captured once at the first mask boundary and carried through clip begin -> mode render -> clip end. The first mask still restores exactly as before; the render host still applies/restores exactly the same blend/cull/depth/viewport contract; the teardown mask still restores exactly as before. The optimization removes only duplicate synchronous state reads. `_InheritedClipState`, incoming Quick scissor/stencil handling, stencil nesting/restoration, rounded clipping, mask geometry, uniforms, literal draws, mode renderer behavior, Bubble cadence/reactivity, scheduling and retained-background ownership are unchanged. The experimental overflow/unclipped branch retains the legacy standalone render-host capture path.

CHK26 intentionally preserves all useful CHK24/CHK25 sidecar instrumentation and adds one explicit-`--frame-trace` boundary for the blend-function/equation state newly carried into the shared snapshot. Old CHK25 traces report byte-for-byte identically under the CHK26 reporter; new traces can distinguish the moved unique capture from the duplicate query batches that should collapse. Because some unique render-host queries move earlier into clip begin, **success must be judged on the whole render body and freshness chain, not by demanding that the old clip-begin parent alone shrink**. Expected evidence is collapse of `RENDER_HOST_BEGIN -> RENDER_GL_STATE_READY` and clip-end mask query intervals, with neutral-or-better `RENDER_BEGIN -> DRAW`, publication->draw and subjective smoothness.

Source authority for CHK26 is **60/60 GREEN** (12 runtime-purity + 22 frame-trace/ownership + 6 service/scheduler + 20 retained A/B/C), and all **903/903 Python files compile**. Installed real-Qt/OpenGL proof remains required before promotion. Request one D1-heavy explicit-`--frame-trace` acceptance run with a long settled Bubble window, then a short rounded-clip geometry resize and one normal mode hotswap, followed by Settings teardown/rebuild and a returned settled window. No dual-display run is required because CHK26 does not touch display routing, transition scheduling, geometry ownership or retained-background ownership. Reject immediately for clip bleed, stencil corruption, mode-state leakage, lifecycle breakage, Bubble/reactivity change, or worse visible smoothness even if a metric improves.

### 19.2L CHK26 pre-acceptance repair — missing lazy-quad helper + soak-safe frame-trace retention
The first packaged CHK26 candidate **never reached physical acceptance**. On startup the render host failed every frame in `_ensure_quad()` with `NameError: name '_int_state' is not defined`. Root cause is exact: the CHK26 state-fence refactor moved the reusable per-frame inherited-state helpers into `gl_state.py` but accidentally removed the render-host-local `_int_state()` still required by the **lazy shared-quad allocator** for its one-time VAO/VBO binding preservation. This is not a GL-state-sharing failure and must not be papered over by suppressing `_ensure_quad()`. The corrected CHK26 restores that small local helper and keeps the production candidate otherwise unchanged. A source regression contract now requires the helper to exist beside both lazy-quad binding reads.

The same pre-test review exposed a diagnostic-storage bug: `--frame-trace` had a bounded in-memory producer ring but drained into an **unbounded on-disk file**. With the refined CHK24/25/26 event density, a normal short run is already ~20 MB and a multi-hour soak could reach gigabytes. Do **not** strip or thin the useful sidecar markers. The corrected trace writer instead retains a **rolling four-segment window of 32 MiB each (128 MiB hard ceiling)**. `screensaver_frame_trace.bin` is always the newest valid v1 segment; `.1.bin`, `.2.bin`, `.3.bin` are progressively older. Rotation is writer-thread-only, never a producer responsibility. `tools/frame_trace_report.py` and the legacy scheduler reducer transparently reconstruct retained segments oldest -> newest, while single-segment historical traces still report byte-for-byte identically. This deliberately trades unlimited historical high-resolution retention for a bounded recent high-resolution window during long soaks; ordinary PERF/usage/lifecycle logs remain the long-horizon evidence.

Corrected source validation: **65/65 directly runnable contracts PASS** (12 runtime-purity + 25 frame-trace/ownership/retention + 20 retained A/B/C + 8 scheduler-trace tooling), and **903/903 Python files compile**. The CHK25 installed binary still produces byte-for-byte identical reporter output when no rolling segments exist. Physical CHK26 acceptance is therefore still outstanding and should use the same D1-heavy sequence described above.

### 19.2M CHK26 physical result -> CHK27 GUI snapshot-to-Quick-sync attribution
The corrected CHK26 candidate has now completed its installed D1-heavy acceptance run. The candidate does what the refined CHK25 trace predicted: it removes duplicated synchronous non-stencil GL-state reads without removing the inherited clip/stencil correctness fences or merely shifting the whole cost into a new unmeasured render-host stage.

Use the clean **15–60 s settled** lane for CHK25 -> CHK26 candidate attribution. At the time of that comparison CHK23 was the accepted GOLDEN reference, while CHK25 was the closest instrumentation-equivalent predecessor for proving the local production delta:

- `RENDER_HOST_BEGIN -> RENDER_GL_STATE_READY`: CHK25 ~**0.153 / 0.319 ms** -> CHK26 ~**0.016 / 0.030 ms** median/p95;
- clip-end duplicate binding/flag reads fall from roughly **0.084 ms combined median** to roughly **0.002 ms**;
- `RENDER_BEGIN -> DRAW`: CHK25 ~**1.884 / 5.831 ms** -> CHK26 ~**1.541 / 5.645 ms**;
- publication -> draw: CHK25 ~**12.683 / 14.545 ms** -> CHK26 ~**12.522 / 14.535 ms**.

The whole-frame result is therefore **real but modest**: about **0.34 ms median** recovered inside the render body, with a small publication->draw median improvement and essentially flat p95. Do not inflate this into a larger claim. The unique shared capture moved earlier exactly as designed, so the old clip-parent interval itself is not expected to collapse. The important result is that duplicate reads vanished and the whole render did not get worse.

The installed correctness sweep is also clean in the evidence logs: CUSTOM edit/resize completed and saved; normal hotswaps ran through Dev Curve, Sphere, Spectrum, Oscilloscope, Sine and back to Bubble; Settings tore generation 0 down and rebuilt generation 1; Bubble returned to the expected ~89–90 logical revisions/s; QML capture contains **0 messages/warnings/errors/criticals**; native-fault capture is clean; final lifecycle teardown completes. The frame trace contains **664,399 records / 4 dropped / 0 write errors** and did not need to rotate during this short run. The rolling trace cap remains the soak-safe contract.

This is sufficient objective evidence to **stop optimizing the clip seam**. Do not keep shaving rounded-mask state handling just because some tail remains: the literal draw was already exonerated, the proven duplicate query set is now removed, and further work approaches correctness-sensitive Qt/OpenGL ownership for diminishing return. **CHK26 is now the formal operator-accepted GOLDEN.** The operator explicitly reported the corrected CHK26 run as **neutral or better** subjectively and pushed repository commit `a0bf70932c` as the GOLDEN landmark. CHK23 is now the immediately prior GOLDEN rollback/bisect landmark; CHK15 / `0abc479c52` remains the older baseline landmark. The promotion is intentionally based on the combination of bounded objective improvement, preserved clipping/hotswap/Settings/lifecycle correctness, and neutral-or-better physical smoothness—not on the size of the numerical win alone.

The next larger residual is the long-standing **GUI snapshot -> Quick sync** interval, still about **5.4 ms median** in clean heavy evidence. CHK27 is **attribution-only** and changes no scheduling/admission policy. It extends the retained explicit `--frame-trace` sidecar with four markers:

1. `GUI_PRESENTATION_COMMIT_READY` immediately after the published presentation has been committed;
2. `GUI_PRESENT_REQUEST_READY` immediately after retained `QQuickItem.update()` presentation has been requested;
3. `QUICK_SYNC_ITEM_ENTRY` timestamped at the very start of `VisualizerRenderItem.updatePaintNode()`;
4. `QUICK_SYNC_SNAPSHOT_ACQUIRED` immediately after the render bridge returns the snapshot that this sync consumes.

The existing `GUI_SNAPSHOT_PUBLISH`, `QUICK_SYNC_CONSUME`, and `QUICK_SYNC_READY` markers remain untouched. The reporter can therefore split the old aggregate `GUI_SNAPSHOT_PUBLISH -> QUICK_SYNC_CONSUME` seam into:

`publish -> presentation commit` -> `commit -> update request returned` -> **`request returned -> updatePaintNode entry`** -> `item entry -> bridge snapshot acquired` -> `snapshot acquired -> legacy QUICK_SYNC_CONSUME`.

The bold interval is the key Qt-admission candidate. The final pre-consume interval isolates the existing local diagnostics/pre-sync work that the legacy marker intentionally sat after. `updatePaintNode()` captures its entry timestamp only when an explicit frame-trace sink exists, and the entry record is emitted only after a real snapshot has been acquired, so ordinary runtime receives **zero new timestamp/record work** and empty/stale sync callbacks do not manufacture correlation records. Binary format remains v1 and the rolling 128 MiB disk ceiling remains unchanged.

Do **not** optimize scheduling yet. If the physical CHK27 trace proves the bulk is `GUI_PRESENT_REQUEST_READY -> QUICK_SYNC_ITEM_ENTRY`, first research/inspect the Qt-native admission/dirty-item ownership before changing update scheduling. If GUI commit/request work or post-acquisition diagnostics own a material part instead, prefer that locally owned seam. Do not add a Python pacer/timer, polling wake, `frameSwapped -> requestUpdate()` loop, or reduce Bubble cadence/reactivity.

CHK27 source/tooling authority is **67/67 PASS** (12 runtime-purity + 27 frame-trace/ownership/retention/attribution + 8 scheduler-trace tooling + 20 retained A/B/C harness), and **903/903 Python files compile**. CHK25 and CHK26 historical binary traces produce byte-for-byte identical report text under the CHK27 reporter because events 44–47 are absent.

The next physical evidence is deliberately cheap: **one settled D1-heavy explicit-`--frame-trace` run, roughly 60–90 seconds**. No edit/resize, hotswap, Settings cycle, transition, D0 or dual-display work is required for this attribution-only checkpoint; CHK26 already exercised the correctness seams and CHK27 does not change them.

### 19.2N CHK26 GOLDEN low-usage mixed-display soak addendum
A separate ~**26m38s** low-usage dual-display soak strengthens CHK26 without replacing the heavy acceptance lane. Both Quick display surfaces remained active through repeated authored transitions. The Visualizer was also live-hopped from the LG/60 Hz display to the MSI/high-refresh display at ~**01:58:17**, then the CUSTOM transfer was saved at ~**01:58:31**; the remainder of the soak stayed healthy on the high-refresh owner.

Long-run authority remained clean:
- Bubble cumulative tick accounting ended at **131,529 requested / 131,529 integrated**, integration ratio **1.000**, with cumulative average **90.0 FPS** over ~**1,461.9 s** of active tick accounting.
- QML capture ended with **0 messages** and **0 write errors**; native-fault capture is empty; final ProcessSupervisor/ThreadManager/cache shutdown is clean.
- The rolling explicit `--frame-trace` sink wrote **6,557,771 records**, **0 dropped**, **0 write errors**, and performed **7 rotations**. At exit the retained four-file window occupied ~**97 MiB** and covered ~**679.4 s (~11m19s)**, directly proving the 4 × 32 MiB / 128 MiB soak-safe retention contract prevents unbounded trace growth.
- In the retained low-contention window, `RENDER_BEGIN -> DRAW` is ~**0.550 / 0.841 ms median/p95**, `RENDER_HOST_BEGIN -> RENDER_GL_STATE_READY` is ~**0.0076 / 0.0105 ms**, `GUI_SNAPSHOT_PUBLISH -> QUICK_SYNC_CONSUME` is ~**0.960 / 2.030 ms**, and publication -> **first** draw is ~**2.774 / 4.239 ms**. These are resilience numbers only; do not compare them directly against the heavy GOLDEN lane as if workload were equivalent.
- Settled event-loop late-p95 is generally ~2 ms-class late in the soak; the final larger spike occurs during shutdown and is not steady-state evidence.

The hop exposed one **telemetry-only trap** worth preserving for future analysis: after Visualizer ownership moves away from a display, that old display's `PERF_HUD` can continue printing a stale `viz_mode=bubble` label with `viz_draw_fps=0`, `viz_revision_hz=0` and ever-growing `viz_age_ms`. The binary trace shows no active Visualizer render events on that old display after transfer. Treat this as stale diagnostic presentation, **not** as evidence of a duplicate live Visualizer owner.

**Clip-path false trails are now closed and must stay documented:** viewport resizing did not cause stencil-resource churn; the literal rounded-mask `glDrawArrays()` was not the p95 owner; wholesale removal of inherited scissor/stencil/GL restoration fences remains rejected; and after CHK26 removed the proven duplicate non-stencil query set, routine clip micro-optimization is exhausted. Further freshness work belongs at the independently measured GUI snapshot -> Quick sync/admission seam, not by reopening the clip-mask investigation.

### 19.2O CHK27 physical result -> CHK28 Qt-native render-loop phase attribution
CHK27's installed D1-heavy trace decisively narrows the old ~5.4 ms `GUI_SNAPSHOT_PUBLISH -> QUICK_SYNC_CONSUME` residual. Use the clean **15–60 s** settled lane before the automatic transition tail:

- publication -> draw: ~**12.970 / 14.871 ms median/p95**;
- GUI snapshot -> Quick sync: ~**5.452 / 6.890 ms**;
- snapshot -> presentation commit: ~**0.141 / 0.263 ms**;
- presentation commit -> retained `QQuickItem.update()` request returned: ~**0.030 / 0.060 ms**;
- **update request returned -> `updatePaintNode()` entry: ~5.118 / 6.487 ms**;
- item entry -> bridge snapshot acquired: ~**0.051 / 0.115 ms**;
- snapshot acquired -> legacy Quick-sync consume marker: ~**0.072 / 0.142 ms**;
- Quick-sync consume -> sync-ready: ~**0.081 / 0.193 ms**;
- sync-ready -> visualizer render begin: ~**4.630 / 6.405 ms**;
- visualizer render begin -> draw: ~**1.714 / 6.062 ms**.

The result **exonerates SRPSS GUI follow-up and render-bridge work as owners of the ~5.4 ms aggregate**. Roughly 5.1 ms is spent after the retained update request has returned but before Qt enters `VisualizerRenderItem.updatePaintNode()`. This is Qt Quick dirty-item/render-loop admission latency, not 5 ms of local Python work. Do not attack presentation commit, bridge acquisition or pre-sync diagnostics on the basis of this residual. Do not resurrect a Python refresh timer, polling wake, `frameSwapped -> requestUpdate()` feedback loop, or continuous repeated visualizer drawing merely to shorten the admission interval.

Qt's documented threaded scenegraph order explains why this boundary exists: a `QQuickItem.update()` schedules `updatePaintNode()` for the scenegraph synchronization stage; the render thread emits `beforeSynchronizing`, synchronizes dirty items through `updatePaintNode()`, then continues through the rendering stage. The measured wait is therefore a **phase/admission boundary** until proven otherwise, not a CPU hotspot.

CHK27 itself is healthy: the trace closes at **801,200 records / 5 dropped / 0 write errors / 0 rotations**; QML capture ends with **0 messages**; native-fault capture is clean; final lifecycle teardown completes. The automatic transition late in the run is excluded from the clean 15–60 s attribution window and does not invalidate it. CHK26 / `a0bf70932c` remains GOLDEN; CHK27 changes no product scheduling.

The adjacent `QUICK_SYNC_READY -> RENDER_BEGIN` interval remains ~**4.63 / 6.41 ms** in that clean window. Historical CHK16 already proved this must **not** be called pure Windows scheduler starvation; it contains Qt/scenegraph work after SRPSS sync and before the visualizer `QSGRenderNode.render()` callback. CHK28 therefore remains **attribution-only** and adds explicit-`--frame-trace` direct `QQuickWindow` phase markers:

1. `beforeFrameBegin`;
2. `beforeSynchronizing`;
3. `afterSynchronizing`;
4. `beforeRendering`;
5. `beforeRenderPassRecording`;
6. `afterRenderPassRecording`;
7. `afterRendering`.

They use a separate per-window render-cycle sequence so Qt-native frame identities cannot collide with visualizer logical revisions. The reporter keeps all CHK23–CHK27 output byte-for-byte unchanged when these events are absent, and when present it splits both the request->`updatePaintNode()` admission path and the sync-ready->render-begin path across Qt's native frame phases. All connections exist only when explicit `--frame-trace` is active and are `Qt.DirectConnection` render-thread observers; they add no scheduling request, timer, polling owner or ordinary-runtime work.

Interpret CHK28 conservatively. If request->item-entry is mostly request->`beforeFrameBegin`, that confirms ordinary next-frame admission and closes the 5.4 ms seam as non-actionable without pacing architecture changes. If meaningful time appears after `beforeSynchronizing`, identify the concrete scene synchronization owner before changing anything. For the post-sync interval, distinguish remaining synchronization, Qt handoff, render-pass setup, and scenegraph work before the visualizer node. Only a locally controllable stage with meaningful payoff may become a production candidate.

Available-container changed authority is **49/49 PASS** (12 runtime-purity + 29 frame-trace/ownership/retention/phase-attribution + 8 scheduler-trace tooling), and **903/903 Python files compile**. The project-wide PySide suite remains unavailable in this container because PySide6 is not installed; do not misreport that environmental boundary as a full-suite pass. The CHK27 installed binary produces byte-for-byte identical report text under the CHK28 reporter because events 48–54 are absent.

The next physical evidence is one **D1-heavy explicit-`--frame-trace` settled run, ~60–90 seconds**. No edit, hotswap, Settings, D0 or dual-display work is required. An automatic transition can be excluded from the settled attribution window as usual.

### 19.3 Regression gates before any scheduling change can become the new baseline
For every candidate change:
- compare settled candidate windows primarily against **CHK26 GOLDEN / `a0bf70932c`**, not whole-run averages; retain CHK23 as the immediately prior GOLDEN rollback/bisect landmark and CHK15 as the older pre-retained-background archaeology reference;
- compare publication→wake, snapshot→sync, sync-ready→render-begin, render-body, publication→draw, revision cadence, source age,
  transition request rate and event-loop tails;
- exercise at least one mode hotswap and one Settings teardown/rebuild; broader torture is optional unless the change touches
  lifetime/ownership;
- reject if trace freshness improves by compressing/removing authored visualizer reaction, lowering Bubble cadence, increasing
  stale/repeated frames, or changing presets/geometry semantics;
- reject if the operator reports new crawl/choppiness even when numerical percentiles look better;
- do not require another dual-display run for every iteration. D1 is the routine scheduling lane; D0-only is enough for
  high-refresh transition checks. Use the already-collected CHK23 mixed-refresh acceptance plus the CHK26 low-usage hop/soak evidence as expensive cross-display references; routine candidates still use D1 unless they touch mixed-refresh/display ownership. Retain CHK15 only for older rollback/bisect archaeology.

### 19.4 Golden baseline / rollback rule
**CHK26 / repository commit `a0bf70932c` is the current operator-accepted GOLDEN performance/freshness baseline and forward comparison authority.** It retains the CHK23 retained-background architecture and additionally removes the physically proven duplicate non-stencil GL-state queries through the bounded shared inherited-state contract. Its promotion is backed by D1-heavy objective improvement, clean rounded clipping/edit/hotswap/Settings/lifecycle evidence, and operator-reported neutral-or-better smoothness. Preserve CHK26 as the primary forward rollback/recovery point.

**CHK23 is the immediately prior GOLDEN rollback/bisect landmark** and remains the expensive mixed-refresh/retained-background acceptance reference. The repository CHK15 commit **`0abc479c52`** (marked `BASELINE`) remains the older immutable pre-retained-background rollback/bisect landmark. Do not rewrite or discard either. If a later candidate regresses, compare first against CHK26, then use CHK23 and CHK15 to determine which architectural era introduced the regression. Any future GOLDEN promotion still requires installed evidence and neutral-or-better visible behavior; numerical improvement never overrides visible regressions.

