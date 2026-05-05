# Gmail Widget Plan

Version: 5.2
Date: 2026-04-30
Status: Functional and suitable for iterative runtime testing. Remaining work is validation, release packaging, display polish, and a small number of bounded research items. Do not let completed phase history grow back into the active plan.

## 1. Contract

Gmail is a normal widget feature. IMAP with an app password is the primary supported backend. OAuth/REST remains optional/advanced until Google verification and release policy are settled.

Rules:
- Keep Gmail settings in the flat `widgets.gmail` dict.
- New user-facing settings need canonical defaults, settings UI load/save, widget apply logic, and focused tests in the same pass.
- Keep `paintEvent()` render-only: no network, file I/O, pixmap scaling, credential checks, token refresh, cache writes, sound setup, or layout mutation from paint.
- UI widgets, menus, labels, timers, sounds, and pixmaps are UI-thread only.
- IMAP/OAuth/network/DPAPI work must not block settings dialog construction or overlay UI.
- Runtime behavior beats tests. Keep runtime-validation items open until normal/MC builds or harnesses prove them.
- Archive is hidden for IMAP. The retained Archive code path is for OAuth/future diagnostics, not a currently advertised IMAP action.
- Settings flicker guardrail: do not pre-polish hidden Gmail bucket bodies by temporarily showing them during settings construction. R-18 established constructor-time visibility calls as a ghost-window/flicker hazard.
- Qt shadow/effect guardrail: Gmail content caching must not mutate graphics effects, hide/show widgets, reparent, resize, or call overlay-effect invalidation.
- Painted-shadow guardrail: Gmail must use the shared runtime painted-card, text-shadow, and header-shadow paths. It must not install runtime `QGraphicsDropShadowEffect` instances or carry widget-local shadow tuning.

## 2. Canonical Files

| Area | File | Notes |
|---|---|---|
| Backend facade | `core/gmail/gmail_backend.py` | Routes IMAP vs OAuth/REST and owns credential state. |
| IMAP backend | `core/gmail/gmail_imap.py` | Primary backend; metadata, Gmail IMAP ids, UID actions. |
| OAuth manager | `core/gmail/gmail_oauth.py` | Optional OAuth path; PKCE + DPAPI token storage. |
| REST client | `core/gmail/gmail_client.py` | Optional metadata/action path. |
| Deep links | `core/gmail/gmail_deeplinks.py` | Gmail web URLs; decimal `X-GM-THRID` to hex. |
| Widget helpers | `widgets/gmail_components.py` | Position enum, date/text cleanup, cache serialization. |
| Overlay widget | `widgets/gmail_widget.py` | Paint/layout, row clicks, action menu, refresh, cache. |
| Settings UI | `ui/tabs/widgets_tab_gmail.py` | Backend/auth controls and Gmail widget settings. |
| Defaults | `core/settings/default_settings.py` | Canonical Gmail default values. |
| Build scripts | `scripts/build_nuitka.ps1`, `scripts/build_nuitka_mc_onedir.ps1` | Must include Gmail image assets and notification sound support. |

Security invariants:
- Store OAuth tokens/app passwords with DPAPI where available.
- Display/store metadata only: sender, subject, date, unread state, and ids needed for links/actions.
- Never log credentials, tokens, message bodies, snippets, raw headers, or full IMAP fetch payloads.
- Gmail normal/SCR URL clicks use the helper/task-scheduler bridge; MC URL clicks use the direct Qt/browser route.
- Build scripts must not bundle ignored local OAuth files such as `client_secrets.json`.

## 3. Active Targets

### A. Runtime Refresh And Paint Validation

Current implementation:
- Gmail uses DPR-aware stable-content caching for header/rows/state.
- Refresh start/result apply defer while the parent display is pending/starting/running a transition.
- Refreshes already in flight suspend live spinner repainting when a transition is requested.
- Unchanged refresh results skip cache writes and repaints.
- Cache writes go through IO when `ThreadManager` is available.
- `perf_widgets.log` includes `gmail.paint`, `gmail.refresh.dispatch`, `gmail.fetch.apply`, `gmail.fetch.error_apply`, `gmail.cache.write`, and `gmail.cache.regen`.

Tasks:
- [ ] Runtime-validate fresh logs for manual transition during an already-running Gmail refresh: spinner repaint should stop and fetched result/cache/sound/UI apply should wait until transition idle.
- [ ] Runtime-profile Gmail with 8-10 rows and confirm idle `gmail.paint` stays comfortably below 5ms on a normal 1080p desktop.
- [ ] Watch for Qt shadow/effect corruption around Gmail after repeated refreshes, fades, transitions, settings reloads, and monitor changes.
- [ ] Runtime-validate Gmail/Weather/Reddit/Media/Visualizer in the MC multi-monitor focus-loss sequence with runtime painted card/text/header shadows enabled.
- [ ] Tune `shadowtuning.json` sections (`card`, `text`, `header`) for softness/darkness/offset parity if runtime visuals need adjustment.

### B. Build And Release Validation

Current implementation:
- Gmail image/action assets are source-tested.
- Normal/MC Nuitka scripts include Gmail images.
- Standard build Gmail logo lookup no longer depends only on cwd.
- Gmail brand logo and notification sound assets have been runtime-validated by the user after the build fixes.
- Installers ship `tutuogg.ogg` to `%ProgramData%\SRPSS\sounds`.
- Frozen default sound resolution prefers ProgramData and falls back to `resources/tutuogg.ogg` in script/dev mode.
- Build scripts include only the default OGG, not the whole `resources` folder.

Tasks:
- [ ] Regression-check final normal/MC artifacts for Gmail brand logo and notification sound packaging when build scripts next change.
- [ ] Build or inspect final normal/MC artifacts and verify envelope, Spam, Trash, Mark Read/Unread, and refresh visuals appear.
- [ ] Re-run credential hygiene check before release: no Gmail address, app password, token, `.enc`, `.pickle`, OAuth client secret JSON, or cache artifact is tracked or bundled.

### C. Display Polish Validation

Tasks:
- [ ] Runtime screenshot Gmail beside Media/Spotify/Reddit at the same scale and verify header/logo/text/border parity.
- [ ] Runtime-validate unread/read envelope distinction at 16px in normal and MC builds.
- [ ] Validate `relative`, `numeric`, and `words` date modes at default and narrow practical widths.
- [ ] Validate sender/subject columns remain aligned when sender word limits change.
- [ ] Validate title casing on real sender/subject samples:
  - contractions stay correct (`You've`, not `You'Ve`)
  - domains/addresses get conservative starting capitalization only where intended
  - established tokens stay intact (`PayPal`, `ChatGPT`, `FNB`, `AI`)

### D. Defaults Audit

Tasks:
- [ ] Ensure every user-facing Gmail default comes from `core/settings/default_settings.py`.
- [ ] Continue removing hardcoded default drift in widget apply logic where values are user-facing rather than private drawing constants.
- [ ] Keep private drawing constants local when they are not user-facing settings.

## 4. Bounded Research / Deferred Work

### Archive

Runtime state:
- Mark Read/Unread, Spam, Delete, and link opening work in normal and MC builds.
- Archive repeatedly fails and is isolated from the rest of the action menu.
- Current implementation already tries Gmail IMAP label removal (`-X-GM-LABELS (\Inbox)`) before any hard-named All Mail MOVE fallback.
- Archive is now hidden whenever the active Gmail backend is IMAP, even if row metadata reports Gmail extension support as `provider="gmail"`, so users are not offered an action that repeatedly failed under runtime testing.

Position:
- Treat Archive as unavailable through Gmail IMAP unless proven otherwise. Do not keep guessing locally.
- The retained code path is deliberately kept for OAuth/future diagnostics if a later task changes the backend assumptions.

Tasks:
- [ ] Build a one-shot Archive diagnostic harness only if Archive becomes important again.
- [ ] Preserve working Mark Read/Unread, Spam, and Delete semantics.

### Thread Grouping

Runtime state:
- `gmail.group_threads` defaults to `False`.
- Naive grouping mismatched Gmail, especially when conversation senders swap.

Tasks:
- [ ] Research Gmail conversation/thread display semantics with IMAP metadata.
- [ ] Prefer `X-GM-THRID` when present, but split read/unread buckets.
- [ ] Decide collapsed-row action semantics before implementation.
- [ ] Keep `gmail.group_threads = False` until behavior matches Gmail well enough.

### Shared Link Placement Stretch

- [ ] Investigate opening Gmail/Reddit links on the browser window/process on monitor index `0`, with safe fallback and no continuous polling.

## 5. Completed Ledger

Do not reimplement these unless a defect is found:
- Dev gate removed; Gmail is ordinary feature plumbing.
- Foundation exists: backend facade, IMAP/OAuth/REST modules, defaults, settings UI, widget factory, notification sound support, and focused tests.
- Layout exists: nine positions, single `gmail.width`, Media-style margins, measured header frame, header logo px adjustment, two-row Text Limits grid, default-open Backend bucket.
- Settings stability fixes exist: canonical Gmail signal-block list, hidden-parent backend visibility, deferred credential/auth refresh, deferred combo popup-view creation, settings-dialog cached defaults merge/invalidation, and guarded bucket visibility.
- IMAP Save & Test is non-blocking and saves credentials only after successful supplied-credential testing.
- Link routing works: normal/main helper/task-scheduler bridge and MC direct URL path.
- Row/action interaction works: row `open_url`, vertical action menu, action-menu hit priority, live `QMenu` ownership, MC focus restoration delay.
- Text cleanup exists: contraction-safe title case, sender cleanup/casing, punctuation-aware sender/subject word limits, subject char limit, stable sender/subject columns.
- Date modes exist: `relative`, `numeric`, and `words`.
- Cache/backend order was restored to selected-mailbox order; over-fetch/date-sort and unread-first cache ordering were removed after runtime mismatch.
- Grouping is guarded by `gmail.group_threads` and defaulted off.
- Assets exist: clean read/unread envelope PNGs, Gmail logo lookup is build-safe, action icons have fallback coverage.
- Notification sound packaging guardrails exist for normal and MC builds.
- Gmail refresh spiral is optional and default-on through canonical defaults/settings UI/widget apply logic.
- IMAP Archive is hidden from the action menu while the backend code remains documented for OAuth/future diagnostics.
- Gmail participates in shared runtime painted shadows and avoids runtime drop-shadow effects.
- Gmail no-auth/no-cache startup stays hidden instead of fading in an empty/auth placeholder.
- Paint/resource first pass exists: stable-content cache, no-op setter guards, transition-aware refresh deferral, in-flight spinner suspension, async cache writes, and perf buckets.
- Runtime painted-card shadows now live in `BaseOverlayWidget` for framed cards, with cached DPR-aware frame output and shared tuning constants.

## 6. Failure Guardrails

- Do not use over-fetch/date-sort to “fix” Inbox ordering; it caused a worse Gmail Inbox mismatch.
- Do not default thread grouping on until it matches Gmail behavior well enough.
- Do not mix normal-helper URL routing with MC direct URL routing.
- Do not call settings flicker fixed from unit tests alone if the user still sees a runtime ghost/tiny window.
- Do not reintroduce constructor-time `setVisible(True)` for hidden Gmail bucket bodies.
- Do not let Gmail settings load fire save handlers repeatedly.
- Do not mutate graphics effects or overlay invalidation from Gmail content-cache regeneration.
