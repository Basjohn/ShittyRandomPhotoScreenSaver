# Gmail Widget Plan

Version: 5.0
Date: 2026-04-29
Status: Gmail is functional enough for iterative runtime testing, but not shippable. This plan is intentionally pruned: completed phase minutiae have been historicalised into a compact ledger, while open work stays detailed enough to implement safely. Do not remove unresolved runtime items just because unit tests pass. The settings flicker regression remains open.

## 1. Current Contract

Gmail is a normal widget feature. IMAP with an app password is the primary supported backend. OAuth/REST remains optional/dev/advanced until Google verification and release policy are settled.

Core rules:

- Keep Gmail settings in the flat `widgets.gmail` dict.
- New user-facing settings need defaults, settings UI load/save, widget apply logic, and focused tests in the same pass.
- Keep `paintEvent()` render-only: no network, file I/O, pixmap scaling, credential checks, token refresh, or layout mutation from paint.
- UI widgets, menus, labels, timers, sounds, and pixmaps are UI-thread only.
- IMAP/OAuth/network/DPAPI work must not block the settings dialog or overlay UI.
- Runtime behavior beats tests. Keep runtime-validation items open until normal/MC builds or harnesses prove them.
- Authored visualizer presets are content, not exact-value test contracts. Tests may validate schema/index/repair behavior, but must not require specific authored preset names, slots, or creative numeric values.

## 2. Canonical Files

| Area | File | Notes |
|---|---|---|
| Backend facade | `core/gmail/gmail_backend.py` | Routes IMAP vs OAuth/REST and owns credential state. |
| IMAP backend | `core/gmail/gmail_imap.py` | Primary backend; fetches metadata and Gmail IMAP ids. |
| OAuth manager | `core/gmail/gmail_oauth.py` | Optional OAuth path; PKCE + DPAPI token storage. |
| REST client | `core/gmail/gmail_client.py` | Optional metadata/action path. |
| Deep links | `core/gmail/gmail_deeplinks.py` | Gmail web URLs; decimal `X-GM-THRID` to hex. |
| Widget helpers | `widgets/gmail_components.py` | Position enum, date/text cleanup, cache serialization. |
| Overlay widget | `widgets/gmail_widget.py` | Paint/layout, row clicks, action menu, refresh, cache. |
| Settings UI | `ui/tabs/widgets_tab_gmail.py` | Backend/auth controls and Gmail widget settings. |
| Defaults | `core/settings/default_settings.py` | Canonical Gmail default values. |
| Build scripts | `scripts/build_nuitka.ps1`, `scripts/build_nuitka_mc_onedir.ps1` | Must include Gmail image assets. |

Security invariants:

- Store OAuth tokens/app passwords with DPAPI where available.
- Display/store metadata only: sender, subject, date, unread state, and ids needed for links/actions.
- Never log credentials, tokens, message bodies, snippets, raw headers, or full IMAP fetch payloads.
- Gmail normal/SCR URL clicks use the helper/task-scheduler bridge; MC URL clicks use the direct Qt/browser route.

## 3. Completed Ledger

Do not reimplement these unless a defect is found:

- Gmail dev gating has been removed; backend modules, settings UI, defaults, notification sound, and focused tests exist.
- Nine-position support, single `gmail.width`, Media-style margins, measured header frame, and layout cleanup are implemented.
- IMAP deep links, account slot, decimal thread-id conversion, row `open_url`, row/action hit separation, vertical action menu, and MC menu popup ownership are implemented and runtime-confirmed in normal and MC builds except Archive.
- Normal/main URL queueing wakes the helper bridge; MC row/header URL routing is patched.
- Sender/subject cleanup exists: contraction-safe title case, sender cleanup/casing, sender word limit, subject word/char limits, fixed row columns, and adjustable sender-column width.
- Refresh control exists: top-right spiral, click-to-refresh, blank-space double-click refresh, fetch-in-progress guard, and spinner idleness logic.
- Date display modes exist: `relative`, `numeric`, `words`.
- Cache/backend order was restored to selected-mailbox order; over-fetch/date-sort and unread-first cache ordering were removed after runtime mismatch.
- Thread grouping is guarded by `gmail.group_threads`, default `False`.
- Mark as Read/Unread, Spam, Delete, and link opening work in runtime reports; Archive remains the only unresolved action.
- Gmail asset guard exists: required images are tested, Archive icon asset exists, both Nuitka scripts include `images=images`, and the widget resolves Gmail assets relative to the executable/module rather than only the process cwd for standard SCR launches.
- Settings dialog creation flicker is runtime-confirmed fixed; bucket-open visual oddness remains under watch. Gmail load signal blocking is canonicalized, redundant `setVisible(...)` calls are reduced, styled combo popup-view creation is deferred until popup open, Gmail backend/auth refresh is deferred until after settings construction, and the failed hidden-bucket pre-polish approach has been removed.
- IMAP Save & Test is non-blocking: supplied credentials are tested on an IO task, then saved only after success.
- Backend-specific settings visibility now uses explicit hidden state, so OAuth text/Authorize controls stay hidden for IMAP even when settings are opened fresh.
- Gmail settings UI has a canonical default accessor for user-facing fallback values; missing Gmail defaults fail loudly instead of silently introducing hardcoded drift.
- Settings-dialog cached widget defaults now merge with fresh canonical defaults and invalidate when `default_settings.py` changes, so stale cache data cannot hide newly added Gmail defaults.
- Gmail bucket toggles now avoid redundant state writes; shared bucket visibility updates skip no-op body show/hide without suppressing the whole settings dialog; Gmail buckets defer the initial collapse until after their child controls are built; Backend content lives in a default-open Backend bucket. Runtime validation is still required for the reported Gmail-only bucket oddness.
- Header parity pass started: Gmail header font/logo sizing now follows Media's `font * 1.2` and `header * 1.3` relationship, has a `header_logo_px_adjust` setting, and uses Media-style inner header border thickness.
- Failed flicker attempt retained as a guardrail: do not pre-polish hidden Gmail bucket contents by temporarily showing them during settings construction. R-18 proved constructor-time visibility calls can create settings ghost/flicker behavior.
- Gmail Text Limits settings are split into a compact two-row aligned grid: sender word/column controls on the first row, subject word/character controls on the second row.
- Gmail envelope/read PNG sources were regenerated as clean 64px transparent black-and-white assets, with tests preventing a return to tiny/jagged source icons.
- Gmail unread rows now use the white/unread envelope asset while read rows use the black/read asset.
- Gmail sender/subject word limiting ignores punctuation-only separators such as `|`, `-`, `•`, and `/`.
- Gmail notification sound release support has source guardrails: both Nuitka builds include only `resources/tutuogg.ogg`, Qt multimedia support is declared, installers ship `tutuogg.ogg` to ProgramData, and the default sound resolver prefers ProgramData with script-mode fallback.
- Gmail stays hidden when there is no authenticated account and no usable cache; it should not join the startup fade wave just to show an auth/empty placeholder.
- Build scripts include only `resources/tutuogg.ogg`, not the whole `resources` folder, so local ignored OAuth files such as `client_secrets.json` are not bundled.
- Gmail widget setters now skip no-op `update()` calls for repeated same-value settings, header desaturation is precomputed with the loaded brand pixmap instead of being generated lazily from `paintEvent()`, refresh start/result apply defer while the parent display is actively transitioning, unchanged refresh results skip cache writes/repaints, cache writes are dispatched to IO when ThreadManager is available, and Gmail emits widget perf metrics for paint, refresh dispatch, result apply/error apply, and cache writes.

## 4. Active Priorities

Work in this order unless the user reports a worse runtime failure:

1. Validate or finish settings stability: flicker, backend-specific panel visibility, Save & Test responsiveness.
2. Runtime interaction correctness: normal/main URL opening, MC URL opening, action menu effects, Archive research.
3. Visual parity and display quality: header parity, envelope assets, date styles, text columns, fonts/colours.
4. Release/resource hygiene: packaged assets, defaults audit, paint/update waste audit.

## 5. Open Implementation Tasks

### A. Settings Stability

#### A1. Settings flicker regression

Problem:

The user reports the settings flicker/ghost-window regression has returned. R-18 says a redundant visibility call in settings construction previously caused the taskbar/titlebar ghost. Gmail has received mitigations, but this is not closed.

Tasks:

- [x] Re-read `Docs/Historical_Bugs.md` R-18 before touching settings visibility.
- [x] Use one canonical Gmail load signal-block list: `GMAIL_SIGNAL_BLOCK_ATTRS`.
- [x] Ensure `WidgetsTab._load_settings()` imports that list instead of duplicating stale Gmail control names.
- [x] Avoid redundant Gmail panel/button `setVisible(...)` calls.
- [x] Fix hidden-parent backend visibility by comparing against explicit hidden state instead of `isVisible()`.
- [x] Fix stale settings-dialog cache/default merging that caused Gmail defaults to look missing at dialog construction.
- [x] Reduce Gmail bucket toggle churn by avoiding redundant visibility/state updates.
- [x] Audit Gmail buckets against R-18 and remove the failed hidden-bucket pre-polish path that temporarily called `setVisible(True)` during settings construction.
- [x] Add source guard coverage preventing Gmail bucket priming from reintroducing constructor-time `setVisible(True)`.
- [x] Defer Gmail backend/auth refresh until after settings construction so IMAP/OAuth credential checks do not run on the dialog-construction path.
- [x] Defer styled combo popup-view styling until the popup is opened, avoiding constructor-time `view()` calls that can create `QComboBoxPrivateContainer` helper frames.
- [x] Defer Gmail bucket initial collapse until after bucket child controls are built, then apply the final collapsed/expanded state once.
- [x] Run `tools/flicker_test.py` with winprobe against Widgets-initial and full main-setup settings paths (`v34`, `v17`; last gated run before gate removal): only the SettingsDialog HWND appeared; no tiny caption/helper window or foreground churn was observed.
- [x] Runtime/user validation: settings dialog creation flicker is fixed.
- [x] Runtime/manual validation: extra Backend bucket resolved the Gmail-only bucket oddness.
- [ ] If a new root cause is proven, add a short entry to `Docs/Historical_Bugs.md` with the exact forbidden pattern.

Failure conditions:

- Calling the flicker fixed from unit tests alone.
- Reintroducing explicit `setVisible(True)` during construction for controls that are already visible by default.
- Loading Gmail settings fires save handlers repeatedly.

#### A2. Backend-specific auth UI

Problem:

When returning to settings, OAuth explanatory text and Authorize controls appeared even when IMAP was selected. Flipping the backend combo corrected it because the change handler explicitly hid the wrong panel.

Tasks:

- [x] Apply backend panel/button visibility during fresh settings construction and load.
- [x] Use explicit hidden state so hidden children stay hidden after their parent becomes visible.
- [x] Test the hidden-parent case.
- [x] When backend is temporarily unavailable during settings open, route panel visibility from backend-combo selection so only one backend panel is shown.
- [ ] Runtime-validate: close settings on IMAP, reopen settings, and confirm OAuth testing text and Authorize button are absent until OAuth is selected.

#### A3. IMAP Save & Test

Problem:

Save & Test previously tested IMAP login synchronously and saved credentials before proving they worked.

Tasks:

- [x] Add `GmailBackend.test_imap_credentials(email, password)` without saving.
- [x] Run supplied-credential test on a `ThreadManager` IO task.
- [x] Save DPAPI credentials only after test success.
- [x] Restore button state and update labels/popups on the UI thread.
- [ ] Runtime-validate that settings remains responsive during slow/failed IMAP login.

### B. Runtime Interaction

#### B1. Link opening

Known runtime state:

- Main/normal build: Gmail links now navigate correctly in runtime testing.
- MC build: Gmail links now navigate correctly in runtime testing.
- Gmail normal/main must keep using the same helper/task-scheduler path as Reddit.
- Gmail MC must keep using the same direct MC URL path as Reddit MC, not the helper bridge.

Tasks:

- [x] Runtime-validate normal/main Gmail row and header clicks after the helper wake patch.
- [x] Runtime-validate MC Gmail row and header clicks after central routing.
- [x] Use `/logs` when failures are reported; keep logs sanitized.
- [ ] Low-priority shared stretch: investigate opening Gmail/Reddit links on the browser window/process on monitor index `0`, with safe fallback and no continuous polling.

#### B2. Action menu effects

Known runtime state:

- MC dot menu now opens and is clickable.
- Main dot menu opens and clicks register.
- Mark as Unread works in both builds.
- Spam and Delete work.
- Archive still fails in runtime, isolated from the rest of the menu actions.
- Online source check: Gmail's current IMAP extension docs show labels are exposed through `X-GM-LABELS` and include `\Inbox`; implementation now removes `\Inbox` first and keeps hard-named All Mail MOVE only as fallback.

Tasks:

- [x] Keep Archive isolated instead of reopening working link/menu behavior.
- [x] Research Gmail IMAP Archive semantics with primary/current sources before changing more code:
  - Gmail special-use mailbox discovery
  - `[Gmail]/All Mail` localization/namespace behavior
  - UID validity after selected label views
  - difference between removing `\Inbox`, category labels, and moving to All Mail
- [ ] Runtime-validate Archive after the `-X-GM-LABELS (\Inbox)` first-pass change.
- [ ] Add a diagnostic harness only if Archive still fails after runtime validation.
- [ ] Preserve working Mark Read/Unread, Spam, and Delete semantics.

### C. Display Quality

#### C1. Header parity

Problem:

The Gmail header/logo still needs visual parity with Media/Spotify/Reddit: logo scale, border thickness, border radius, and top padding.

Tasks:

- [ ] Runtime screenshot Gmail beside Media at the same scale.
- [x] Measure implementation against Media formulas rather than screenshot constants.
- [x] Adjust Gmail header font/logo relationship and header border thickness to match Media.
- [ ] Runtime-validate the default size visually; use `gmail.header_logo_px_adjust` only for final px nudging.
- [ ] Keep click hit rect aligned with the painted header frame.

#### C2. Envelope and action assets

Problem:

Current envelope PNGs are distorted/jagged. Archive now has an SVG, but read/unread envelope assets still need a polish pass.

Tasks:

- [x] Replace read/unread envelope PNGs with clean black-and-white assets.
- [x] Keep unread/read distinction visually clear in widget code by selecting the unread PNG for unread mail and the read PNG for read mail.
- [ ] Runtime-validate unread/read distinction visually at 16px in normal and MC builds.
- [ ] Verify assets appear in final packaged builds.
- [ ] Keep fallback drawing for missing optional icons.

#### C3. Row/date/text runtime validation

Tasks:

- [x] Split Text Limits into two aligned settings rows so four spinboxes no longer compete on one line.
- [x] Re-align Text Limits as a two-row grid matching the desired Sender words/Sender column and Subject words/Subject chars layout.
- [x] Ensure punctuation-only separator tokens do not count as subject/sender words.
- [ ] Validate `relative`, `numeric`, and `words` date modes at default and narrow practical widths.
- [ ] Validate sender/subject columns remain aligned when sender word limits change.
- [ ] Validate title casing on real sender/subject samples:
  - contractions stay correct (`You've`, not `You'Ve`)
  - domains/addresses get conservative starting capitalization only where intended
  - established tokens stay intact (`PayPal`, `ChatGPT`, `FNB`, `AI`)

#### C4. Thread grouping

Problem:

Grouping was defaulted off because naive grouping mismatched Gmail, especially when conversation senders swap. It should be researched and validated but remain an optional setting.

Tasks:

- [ ] Later online research: Gmail conversation/thread display semantics with IMAP metadata.
- [ ] Prefer `X-GM-THRID` when present, but split read and unread buckets.
- [ ] Decide collapsed-row action semantics before implementation.
- [ ] Keep `gmail.group_threads = False` until runtime behavior matches Gmail well enough.

### D. Release And Resource Hygiene

#### D1. Defaults audit

Tasks:

- [~] Ensure every user-facing Gmail default comes from `core/settings/default_settings.py`.
- [x] Add a canonical Gmail settings UI default accessor and use it for load/save fallback values.
- [ ] Continue removing hardcoded default drift in widget apply logic where values are still user-facing rather than private drawing constants.
- [ ] Keep private drawing constants local when they are not user-facing settings.
- [x] Default notification sound path now resolves to `%ProgramData%\SRPSS\sounds\tutuogg.ogg` when installed, with `resources/tutuogg.ogg` as the script/dev fallback.

#### D2. Paint/update/resource audit

Tasks:

- [x] Source-audit Gmail paint path: no network, credential checks, cache writes, or sound setup are performed from `paintEvent()`.
- [x] Confirm refresh spinner/timers run only while refreshing and stop on cleanup.
- [x] Precompute header desaturation during asset loading so no pixmap conversion is triggered by paint.
- [x] Prevent refresh-start and fetch-completion UI churn during active/pending transitions: spinner start, network submission, visible result apply, cache write, layout height recompute, repaint, unread signal, and sound detection now wait until the parent transition is idle. This includes the image-load/pre-start window after a transition request is accepted but before GL animation reports as running.
- [x] Skip cache writes and repaint when a refresh returns the same visible email list and unread count.
- [x] Dispatch Gmail cache writes through the IO thread pool when ThreadManager is available; fall back to synchronous write only when the thread manager is unavailable.
- [x] Add Gmail to `perf_widgets.log` instrumentation:
  - `gmail.paint`
  - `gmail.refresh.dispatch`
  - `gmail.fetch.apply`
  - `gmail.fetch.error_apply`
  - `gmail.cache.write`
- [x] Add a DPR-aware stable-content paint cache for Gmail so idle paints blit cached header/rows/state while the refresh spiral remains live and uncached.
- [x] Keep Gmail cache regeneration shadow-safe: no graphics-effect mutation, hide/show, reparenting, resize, or overlay-effect invalidation occurs in the cache path; source guard coverage exists for this.
- [~] Confirm not causing/contributing to UI Thread choking; remaining risk is normal idle-time sound setup/play and live perf metrics from the newly added Gmail buckets.
- [~] Confirm Gmail does not repaint every frame/tick when data and animation state are unchanged; first-pass setter no-op guards and stable-content caching are implemented.
- [ ] Runtime-profile `gmail.paint` with 10 rows from `perf_widgets.log`; target under 5ms on a normal 1080p desktop.

#### D3. Build/package validation

Tasks:

- [x] Remove Devgate from Gmail and make it a normal feature.
- [x] Source-level tests verify Gmail assets exist and normal/MC Nuitka scripts include `images=images`.
- [x] Fix standard build Gmail logo lookup: widget asset loading no longer depends only on cwd, which can be System32 for `.scr` launches.
- [x] Source-level tests verify normal/MC Nuitka scripts include notification sound resource packaging, Qt multimedia support, and installer ProgramData sound shipping.
- [x] Corrected source-level build guard: normal/MC Nuitka scripts include only `resources/tutuogg.ogg`, not the entire `resources` directory.
- [x] Build runner preflight fails clearly if `resources/tutuogg.ogg` is missing.
- [x] Confirmed tracked files do not contain the user's Gmail address, app password, Gmail credential `.enc`, or OAuth client secret JSON.
- [ ] Rebuild/inspect final normal artifact and verify the Gmail brand logo now appears; MC/script already validated.
- [ ] Build or inspect final normal/MC artifacts and verify envelope, Archive, Spam, Trash, Mark Read/Unread, and refresh visuals appear.
- [ ] Build or inspect final normal/MC artifacts and verify notification sound playback works from ProgramData.
- [ ] Continue ensuring no `client_secrets.json`, token, app password, `.enc`, `.pickle`, cache, or raw credential artifacts are tracked or bundled by accident.

## 6. Research Items

- Archive semantics in Gmail IMAP: source research completed; runtime validation still required for the label-removal first pass.
- Thread grouping/conversation semantics in Gmail IMAP: online research required.
- [DEFERRED] OAuth production readiness: Google restricted-scope verification, release policy, and public-build credential policy.
- Browser monitor placement for Gmail/Reddit links: shared low-priority stretch.
