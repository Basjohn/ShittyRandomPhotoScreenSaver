# Gmail Widget Plan

Version: 3.9
Date: 2026-04-29
Status: Gmail is functional enough for iterative runtime testing, but not shippable. Completed work is now kept brief; remaining work is focused on validating the latest runtime link/menu/action fixes, restored Inbox ordering, optional/default-off thread grouping, settings flicker regression, date display modes, header parity validation, refresh controls, settings/defaults audit, resource-use audit, settings UI cleanup, and release hygiene.

## 1. Current Intent

The Gmail widget is a dev-gated overlay (`--devgmail`) that displays Gmail/IMAP metadata in the screensaver without storing or rendering message bodies. IMAP is the primary production backend. OAuth/REST remains optional and dev/advanced unless Google verification is completed.

The next work should focus on making the existing widget shippable, not rewriting it. The visible widget layout foundation, IMAP/Gmail deep-link foundation, sender/subject cleanup controls, fixed sender/subject columns, and adjustable sender-column width are implemented. The latest layout cleanup removes the exposed min/max width and padding controls: Gmail now has one `gmail.width` value, defaulting to the same 600px width used by the Media widget, and uses Media-style content margins instead of user-facing padding. Runtime interaction patches are in place but still need validation: normal/main mode queues Gmail URLs to the ProgramData helper bridge and now explicitly wakes the helper runtime after queueing; MC mode subject links work, and the action-menu path now keeps a live menu reference and suppresses immediate MC focus reclaim so the popup can receive clicks. The latest ordering/action patch restores backend/Inbox order instead of over-fetching and date-sorting, keeps cached rows in that same backend order, adds optional/default-off thread grouping, switches Archive to Gmail IMAP `MOVE` to All Mail with label-removal fallback, and preserves the working Mark as Unread, Spam, and Delete paths.

## 2. Current Architecture

Canonical files:

| Area | File | Notes |
|---|---|---|
| Dev gate | `core/dev_gates.py` | `is_gmail_enabled()` reads `--devgmail` / forced gate state. |
| Unified backend | `core/gmail/gmail_backend.py` | Routes between IMAP and OAuth/REST modes. |
| IMAP backend | `core/gmail/gmail_imap.py` | Primary backend. Fetches Gmail IMAP extension fields and attaches Gmail row `open_url` values when available. |
| OAuth manager | `core/gmail/gmail_oauth.py` | Optional/dev path. Uses PKCE and DPAPI token storage. |
| REST client | `core/gmail/gmail_client.py` | Optional OAuth/Gmail API path. Metadata-only. |
| Gmail deep links | `core/gmail/gmail_deeplinks.py` | Pure helpers for Gmail inbox/thread/search URLs. Converts `X-GM-THRID` decimal IDs to lowercase hex. |
| Secure URL bridge | `core/windows/secure_url_launcher.py` | Required for browser opening from `.scr` / secure-desktop paths. |
| Notification audio | `core/audio/notification_sound.py` | OGG playback for new mail. |
| Widget data/helpers | `widgets/gmail_components.py` | Position enum, formatting helpers, cache serialization. |
| Overlay widget | `widgets/gmail_widget.py` | Paints header, rows, menus, sounds, and click handling. |
| Settings UI | `ui/tabs/widgets_tab_gmail.py` | Gmail settings controls, bucket UI, backend/auth panel. |
| Defaults | `core/settings/default_settings.py` | Flat Gmail settings dict. Do not add a Gmail settings dataclass unless the project explicitly migrates away from flat widget settings. |

Security contract:

- Store OAuth tokens/App Passwords with DPAPI where available.
- Display/store metadata only: sender, subject, date, unread state, provider IDs needed for linking.
- Never log credentials, tokens, message bodies, raw headers, snippets, or full IMAP fetch payloads.
- Use the runtime-appropriate browser path: `.scr` / secure-desktop paths use `core/windows/secure_url_launcher.py`, while MC-mode row/header clicks should be handed to central input URL routing so they open directly through Qt and do not call the Reddit helper bridge.

## 3. Completed Work - Minimal Record

These are already done and should not be reimplemented unless code review finds a defect:

- Archive Gmail code has been adapted into production modules under `core/gmail/`, `widgets/`, and `ui/tabs/`.
- Gmail is registered as a dev-gated widget behind `--devgmail`.
- IMAP and OAuth/REST backends exist, with IMAP as the preferred supported path.
- Flat Gmail defaults exist in `core/settings/default_settings.py`.
- Gmail settings UI exists and is wired into the widgets tab.
- Notification sound support exists.
- Basic unit/integration tests exist for OAuth, REST client, widget smoke behavior, settings round-trip, components, and dev gating.
- Separator color/thickness controls and painting are already present.
- Some collapsible/bucket UI work already exists in `widgets_tab_gmail.py`.
- Phase A structural fixes are implemented: nine-position support, one Gmail width setting, Media-style widget margins, and measured header frame.
- Phase B deep-link helpers are implemented: `gmail_deeplinks.py`, IMAP metadata `open_url`, account slot setting, and focused tests.
- Phase C has a first safety pass: stale async widget fetch results are ignored after cleanup/settings generation changes; `gmail_imap.py` no longer imports `re` per fetched message.
- Screenshot-driven text cleanup is implemented: contraction-safe subject title casing, sender cleanup, max sender words, max subject words/chars, UI controls, defaults, and focused tests.
- Row/action dispatch foundation is implemented: row clicks prefer `EmailMetadata.open_url`, action menu clicks have priority over row clicks, and the action indicator is vertical.
- Runtime interaction hardening is partially implemented: normal/main URL queueing now wakes the helper runtime, and Gmail action-menu clicks now keep the QMenu alive and defer MC focus restoration instead of immediately stealing focus back from the popup.
- IMAP Inbox list ordering has been restored to the previous safer behavior after runtime mismatch: fetch the latest mailbox UIDs requested by the active label, reverse them for newest-first display, and do not over-fetch/date-sort them in the widget.
- Email cache display stability is partially implemented: fetched and cached mail now preserve the same backend order before writing or loading cache, reducing startup row jumps without inventing unread-first ordering.
- Fixed row-column layout is implemented: visible rows share timestamp, sender, and subject start/stop columns so short senders leave blank space instead of shifting subjects.
- Sender alignment is now an explicit setting: `gmail.sender_column_width` controls where the subject column starts. `gmail.max_sender_words` only changes sender text content and should not be expected to move the subject column.

## 4. Agent Rules For Remaining Work

Use these rules for every task below:

- Keep settings in the flat Gmail dict pattern. A new user-facing setting needs all three pieces in one change: default in `core/settings/default_settings.py`, read/apply logic in `GmailWidget`, and a control in `widgets_tab_gmail.py`.
- Keep `paintEvent()` render-only. No network, file I/O, token refresh, credential checks, pixmap scaling, `adjustSize()`, or `update()` from paint.
- Use measured layout: `QFontMetrics`, pixmap dimensions, Media-style margins, widget bounds, and existing helper APIs. Do not hardcode visual offsets from screenshots.
- Qt objects, labels, menus, timers, pixmaps, settings controls, and sounds must be touched only on the UI thread.
- Backend IMAP/OAuth/network/DPAPI work must run off the UI thread.
- Plain `threading.Lock` is acceptable for short non-Qt data critical sections. The real problems are unmanaged threads, locks held during I/O, background updates to Qt state, and stale callbacks after cleanup.
- Reference Reddit/Imgur/Weather widgets as patterns, not copy-paste sources. Map coordinates, margins, fonts, hit rects, and lifecycle behavior to Gmail before adapting code.
- Each implementation slice needs a compile/test check plus at least one visible/manual validation note.

## 5. Recommended Execution Order

Work in this order:

1. Runtime interaction correctness: normal/main URL helper handoff, MC direct URL path, action menu popup, and IMAP menu effects.
2. Settings stability: flicker regression, non-blocking Save & Test, and UI bucket cleanup.
3. Message display quality: date display modes, thread collapse, header parity, envelope asset polish, and remaining typography/colour settings.
4. Secure-desktop/manual validation, performance checks, and release hygiene.

This order fixes user-visible failures first, then prevents deeper lifecycle regressions before final sign-off.

## 6. Phase A - Structural UI Fixes

### A1. Positioning: center and edge positions fall back to top-left

Problem:

`widgets/gmail_components.py` currently defines only four corner positions. The UI offers nine positions. Values such as `top_center`, `middle_left`, `center`, and `bottom_center` can fall back to `TOP_LEFT`. `GmailWidget.__init__` also maps via `OverlayPosition(position.value)`, which only works if every Gmail enum value exactly matches an `OverlayPosition` value.

Files:

- `widgets/gmail_components.py`
- `widgets/gmail_widget.py`
- `tests/test_gmail_components.py`
- `tests/test_gmail_widget.py` if positioning behavior is testable there

Tasks:

- [x] **A1.1** Expand `GmailPosition` to all nine standard overlay positions:
  - `TOP_LEFT`, `TOP_CENTER`, `TOP_RIGHT`
  - `MIDDLE_LEFT`, `CENTER`, `MIDDLE_RIGHT`
  - `BOTTOM_LEFT`, `BOTTOM_CENTER`, `BOTTOM_RIGHT`
- [x] **A1.2** Update `GmailPosition.from_string()` to accept exact values and display-style strings with spaces.
- [x] **A1.3** Keep `center` as the true middle position, not an alias for `top_center`.
- [x] **A1.4** Update `GmailWidget.__init__` so every `GmailPosition` maps safely to the corresponding `OverlayPosition`.
- [x] **A1.5** Add a Gmail `_update_position()` override only if needed by the local `BaseOverlayWidget` pattern; otherwise rely on the base class after mapping correctly.
- [x] **A1.6** Ensure repositioning happens after the widget has its final size when width/height settings change.
- [x] **A1.7** Add/extend tests for all nine string values and fallback behavior.

Failure conditions:

- Any UI-offered position still lands at top-left unless explicitly configured that way.
- Center positions drift after changing width.
- New enum labels exist without matching persisted values.

### A2. Width: single Media-parity width

Problem:

The previous min/max width controls made the settings UI noisy and encouraged misalignment. Gmail should behave like the peer widgets: expose one width setting, default it from the same practical width Media uses (`600`), and keep anchor positioning stable when that width changes.

Files:

- `widgets/gmail_widget.py`
- `ui/tabs/widgets_tab_gmail.py`
- `core/settings/default_settings.py`
- `tests/test_gmail_settings_roundtrip.py`
- `tests/test_gmail_widget.py`

Tasks:

- [x] **A2.1** Trace every width-changing path in `GmailWidget`: constructor, settings application, content height/size updates, base overlay behavior, and refresh/fade paths.
- [x] **A2.2** Replace exposed `gmail.min_width` / `gmail.max_width` with one `gmail.width` setting. Default: `600`.
- [x] **A2.3** Keep backward-compatible loading from old `min_width` / `max_width` values, but do not save those keys anymore.
- [x] **A2.4** Clamp invalid `width` values to `200-1200`.
- [x] **A2.5** Apply `setMinimumWidth(width)` and `setMaximumWidth(width)` after base styling and after settings load.
- [x] **A2.6** If `adjustSize()` or a size hint ignores bounds, override `sizeHint()` / `minimumSizeHint()` or clamp resize results in the existing size update path.
- [x] **A2.7** Ensure email row paint width uses actual widget geometry and respects content padding. Do not paint text wider than the widget.
- [x] **A2.8** Add a single Width control in the Layout bucket, range `200-1200`, step `10`.
- [ ] **A2.9** Verify left, center, and right anchors stay stable when width changes. Automated state checks exist; this still needs visual/manual confirmation.

Failure conditions:

- Width is changed only visually while the widget hit rect/geometry stays narrow.
- Right/center positioned widgets drift after width changes.
- Old min/max keys continue to be saved from the settings UI.

### A3. Media-style margins and content alignment

Problem:

The previous Gmail-only padding controls did not match other widgets and could create header/row misalignment. Gmail should use the same content-margin approach as Media instead of exposing per-side padding in the settings UI.

Files:

- `widgets/gmail_widget.py`
- `ui/tabs/widgets_tab_gmail.py`
- `core/settings/default_settings.py`
- `tests/test_gmail_settings_roundtrip.py`

Tasks:

- [x] **A3.1** Remove exposed `gmail.content_padding_left`, `gmail.content_padding_right`, and `gmail.content_padding_top` controls/defaults.
- [x] **A3.2** Apply Media-style widget margins: left `29`, top `12`, right `12`, bottom `12`.
- [x] **A3.3** Keep old padding setters as no-op compatibility shims that reset internal custom padding to `0`.
- [x] **A3.4** Use the same padded content rect for header, email rows, separators, empty state, error state, and hit rects.
- [x] **A3.5** Avoid double-applying margins plus padding; custom Gmail padding is now `0`.
- [x] **A3.6** Remove padding controls from Layout.
- [x] **A3.7** Update row/action/header hit rects to match the painted locations.

Failure conditions:

- Text moves but click targets remain in old positions.
- Empty/error states ignore the shared content margins.
- Separators start at a different x-coordinate from row content unless deliberately full-width.

### A4. Header border/frame around Gmail logo and header text

Problem:

The Gmail header lacks the framed visual treatment used by comparable overlay widgets. This should be implemented as a measured layout helper, not screenshot math.

Files:

- `widgets/gmail_widget.py`
- `ui/tabs/widgets_tab_gmail.py`
- `core/settings/default_settings.py`
- `tests/test_gmail_widget.py`

Tasks:

- [x] **A4.1** Add `gmail.show_header_border`. Default: `True`.
- [x] **A4.2** Read it into `self._show_header_border`.
- [x] **A4.3** Add a small header layout helper that returns:
  - frame rect
  - logo rect
  - text x
  - text baseline y
  - total header content size
  - header hit rect
- [x] **A4.4** Compute frame geometry from live content:
  - header text (`Gmail (N)` or existing header builder)
  - header font metrics
  - scaled/cached logo pixmap size
  - logo margin
  - frame padding x/y
  - content padding and widget bounds
- [x] **A4.5** Draw in this order: frame, logo, text.
- [x] **A4.6** Use existing rounded-rect/shadow/border helpers where available. Use existing background border color/width rather than adding new border color settings.
- [x] **A4.7** Vertically center logo and text using one shared center:
  - `logo_y = center_y - logo_height / 2`
  - `text_baseline_y = center_y - font_height / 2 + fm.ascent()`
- [x] **A4.8** Header height and first row y-position must include the frame height and list gap.
- [x] **A4.9** Add a Header bucket checkbox for `show_header_border`.
- [x] **A4.10** Add/extend a smoke test rendering with the border enabled and disabled.

Failure conditions:

- Frame clips text or logo at any configured font size.
- Frame jitters when unread count changes.
- Frame appears when disabled.
- Paint starts scaling pixmaps or calling `update()`.

## 7. Phase B - IMAP/Gmail Deep Links

### B1. Exact row opening for Gmail IMAP

Problem:

Plain IMAP does not provide a generic webmail URL. Gmail IMAP exposes `X-GM-THRID`; Gmail web links require that decimal thread id converted to lowercase hex. Current code fetches Gmail IDs but still has stale `#inbox/{message_id}` style opening paths, which is wrong for IMAP row links.

Files:

- `core/gmail/gmail_imap.py`
- `core/gmail/gmail_client.py`
- `core/gmail/gmail_deeplinks.py` (new)
- `widgets/gmail_widget.py`
- `tests/test_gmail_client.py`
- `tests/test_gmail_components.py` or a new focused Gmail deeplink test file

Tasks:

- [x] **B1.1** Add `core/gmail/gmail_deeplinks.py` with pure helper functions:
  - `gmail_thread_url(thread_id_decimal: str, account_slot: str = "0", mailbox: str = "all") -> str`
  - `gmail_message_id_search_url(rfc822_message_id: str, account_slot: str = "0") -> str`
  - `build_open_url(meta: EmailMetadata, account_slot: str = "0") -> str | None`
- [x] **B1.2** Convert `X-GM-THRID` decimal to lowercase hex with `format(int(thread_id_decimal), "x")`.
- [x] **B1.3** Prefer `https://mail.google.com/mail/u/<slot>/#all/<thread_hex>` because messages may be archived, labelled, spam, or moved out of Inbox.
- [x] **B1.4** If `X-GM-THRID` is absent but RFC `Message-ID` exists, fall back to `https://mail.google.com/mail/u/<slot>/#search/rfc822msgid:<encoded-message-id>`.
- [x] **B1.5** Strip angle brackets from RFC `Message-ID` before encoding.
- [x] **B1.6** For non-Gmail IMAP providers, leave `open_url = None` unless a provider-specific module is added later.
- [x] **B1.7** Extend `EmailMetadata` only with metadata/link fields:
  - `provider: str = "imap"`
  - `account_email: str | None = None`
  - `imap_uid: str | None = None`
  - `rfc822_message_id: str | None = None`
  - `gmail_thread_id: str | None = None`
  - `gmail_message_id: str | None = None`
  - `open_url: str | None = None`
- [x] **B1.8** Do not add `body`, `snippet`, or raw header fields.
- [x] **B1.9** In IMAP fetch, include RFC `Message-ID` in header fields.
- [x] **B1.10** Detect Gmail extension support using `X-GM-EXT-1` capabilities after login. Use Gmail-specific fetch fields only when supported or degrade gracefully if unavailable.
- [x] **B1.11** Build `open_url` during metadata conversion, not in `paintEvent()`.
- [x] **B1.12** Add `gmail.account_slot` setting. Default: `"0"`. Keep it in an advanced/linking area, because wrong slot opens the wrong signed-in Google account.
- [x] **B1.13** Header click should open `https://mail.google.com/mail/u/<slot>/#inbox` for Gmail accounts when possible.
- [x] **B1.14** Row click should open `email.open_url` when present, otherwise fall back to the header/inbox URL or no-op with a quiet sanitized log.
- [x] **B1.15** Route browser opens through the appropriate runtime path: widget-local fallback uses `core/windows/secure_url_launcher.py`, while central MC input routing receives URLs from `resolve_click_target(...)` and opens through Qt.
- [x] **B1.22** Restore IMAP Inbox listing to the pre-regression newest-UID mailbox order. The over-fetch/date-sort mitigation created a worse mismatch with Gmail's visible Inbox and must not be reintroduced without a default-off setting and runtime proof.
- [ ] **B1.23** Runtime-validate that `gmail.label_filter = INBOX` shows the same top visible messages as Gmail Primary/Inbox after manual refresh. If mismatch remains, inspect Gmail category labels, thread grouping, and cache freshness before changing display cleanup code.

Tests:

- [x] **B1.16** Unit test decimal-to-hex conversion with a known value.
- [x] **B1.17** Unit test `gmail_thread_url("1372213338078123456")` returns `#all/<hex>`, not a decimal route.
- [x] **B1.18** Unit test RFC `Message-ID` search fallback strips brackets and URL-encodes safely.
- [x] **B1.19** Unit test IMAP parsing with Gmail extension fields.
- [x] **B1.20** Unit test IMAP parsing without Gmail extension fields does not create fake `open_url`s.
- [ ] **B1.21** Manual test with two Google accounts signed into the browser and `gmail.account_slot` set to both `0` and `1`.

Failure conditions:

- Decimal `X-GM-THRID` appears raw in the Gmail URL.
- Non-Gmail IMAP messages get invented Gmail links.
- URL-building logs subjects, senders, raw headers, or credentials.
- Secure-desktop paths call `webbrowser.open()` directly instead of the bridge.

### B2. Row, sender/subject, and action-menu clicks must work in MC mode

Problem:

Screenshot/manual review reports that clicking sender text, subject text, and the three-dot menu currently does nothing, at least in MC mode. The row/header URL side was partly caused by Gmail calling its widget-local URL opener, which can reach the Reddit helper bridge even though the helper is for normal/SCR paths and MC mode should open via the central direct `QDesktopServices` path. The action-menu symptom is separate: the menu freezes briefly without appearing, so treat it as an unresolved popup/focus/runtime issue until `/logs` or instrumentation show the exact stall.

Current log evidence from `/logs`:

- Normal/main script run at 2026-04-28 22:44:07: Gmail row URL was built and queued as `https://mail.google.com/mail/u/0/#all/...`; the central path logged URL copy and `reddit_helper_bridge` queued `open_url`, but the user's observed browser navigation still failed after screensaver exit. This points at helper/task-scheduler/process handoff, not URL construction.
- Earlier normal/main action-menu tests logged `archive_message not supported via IMAP` and `trash_message not supported via IMAP`. The menu can accept clicks, but IMAP action methods currently return no-op failures.
- MC-mode user report: subject links work, but the vertical dot menu does not open and briefly freezes cursor input. Treat popup/focus behavior as separate from URL opening.

Files:

- `widgets/gmail_widget.py`
- `rendering/input_handler.py`
- `rendering/display_input.py` / `rendering/display_widget.py` only if central URL routing evidence points there
- `tests/test_gmail_widget.py`
- Existing MC/input harnesses if available

Tasks:

- [ ] **B2.1** Instrument or test that central input routing reaches Gmail in normal mode and MC mode for:
  - sender text area,
  - subject text area,
  - row whitespace inside the row rect,
  - action menu icon rect.
- [x] **B2.2** Keep one row hit rect that covers the full painted sender/subject/time row. Do not require clicking only the subject glyphs.
- [x] **B2.3** Ensure row click opens `email.open_url` if present and falls back through the existing safe URL path.
- [x] **B2.4** Ensure action menu hit rect is above or separate from the row hit rect so menu clicks do not get consumed as row opens.
- [x] **B2.5** Change the action menu indicator from horizontal dots to a vertical ellipsis. Draw dots vertically in a stable 24px-wide action rect aligned to the row center.
- [x] **B2.6** Add a focused test that clicks the row rect and action rect directly on `GmailWidget` and verifies the expected dispatch path is selected with mocked `open_url` / `_show_action_menu`.
- [x] **B2.7** Add `GmailWidget.resolve_click_target(local_pos)` so row/header URL clicks can be handed to central URL routing without opening inside the widget.
- [x] **B2.8** Update `rendering/input_handler.py` so Gmail row/header URLs set the existing central URL return values. This intentionally reuses the current Reddit/Imgur tuple until that path is renamed/generalized.
- [ ] **B2.9** Run an MC-mode manual or harness check after implementation. Expected result: header/row clicks open through MC direct browser opening, not through `reddit_helper_bridge`.
- [x] **B2.10** Diagnose and patch the action-menu freeze separately from URL clicks. Current fix: `GmailWidget` keeps a live `_active_action_menu` reference, closes any previous menu before opening a new one, makes the popup topmost, and `InputHandler` marks Gmail action-menu clicks so `display_input` does not immediately run MC focus restoration against the popup.
- [x] **B2.11** Patch normal/main helper handoff using the same task-scheduler/helper runtime path that Reddit uses. Current fix: after a ProgramData bridge queue succeeds, refresh the helper session ticket and call `ensure_helper_runtime(source="run_session_click", allow_system=True)` so secure-desktop/SYSTEM runs can ask Task Scheduler to wake the user-session helper.
- [ ] **B2.12** Verify the menu contains Archive in both normal/main and MC mode. Code intends to add it; user observation says it is missing in at least one runtime, so do not close this without runtime evidence.
- [ ] **B2.13** Runtime-validate the B2.10 action-menu patch in MC mode. Expected result: vertical action menu opens without cursor freeze, stays clickable, and menu actions can be selected.
- [ ] **B2.14** Runtime-validate the B2.11 helper wake patch in normal/main mode. Expected result: Gmail row/header links exit the screensaver and open the queued Gmail URL in the browser. If still failing, inspect ProgramData queue leftovers, helper heartbeat, scheduled-task acceptance, and helper logs before changing URL construction.

Failure conditions:

- Sender/subject text paints in one location but hit rects remain elsewhere.
- Action menu dots are horizontal.
- Action menu click opens the message instead of the menu.
- Normal mode works but MC mode still swallows clicks.
- Gmail URL clicks in MC invoke the Reddit helper bridge instead of direct MC browser opening.
- The action-menu path is marked done from widget unit tests only; runtime menu popup must be verified.

### B3. IMAP action menu effects

Problem:

The normal/main action menu opens and its buttons are clickable, but actions do not actually change messages. This is expected from current IMAP code: `mark_as_read`, `archive_message`, `spam_message`, and `trash_message` log unsupported warnings and return `False`. REST/OAuth actions exist separately, but IMAP is the primary backend and must be implemented safely.

Files:

- `core/gmail/gmail_imap.py`
- `core/gmail/gmail_backend.py`
- `widgets/gmail_widget.py`
- `tests/test_gmail_widget.py`
- focused IMAP action tests with mocked `imaplib`

Tasks:

- [x] **B3.1** Preserve enough metadata to perform actions: widget action dispatch should be able to pass `imap_uid` for IMAP actions and Gmail message id for REST actions. Do not assume the displayed `email.id` is an IMAP UID.
- [ ] **B3.2** Add a backend-level action helper that maps a widget email id to the backend-specific identifier when possible, or stores a small id map from the latest fetched metadata.
- [x] **B3.3** Implement Mark Read for IMAP with `STORE +FLAGS (\\Seen)` against the correct selected mailbox/UID, then refresh the widget row state.
- [x] **B3.4** Implement Trash/Spam with Gmail IMAP label operations and no broad expunge. Folder discovery remains a future hardening item if label operations fail in real Gmail runtime.
- [x] **B3.5** Implement Archive for Gmail IMAP by moving the UID to `[Gmail]/All Mail` with `UID MOVE`, falling back to `-X-GM-LABELS (\\Inbox)` only if MOVE is unavailable. Avoid expunging unrelated messages.
- [x] **B3.6** After successful action, trigger an immediate refresh so the user sees the result. Runtime validation remains open because logs show Archive success while the user still observed no visible Gmail change.
- [x] **B3.7** On action failure, log a sanitized reason and keep the menu/UI responsive. Do not log subjects, credentials, raw headers, or server banners.
- [ ] **B3.8** Runtime-validate these IMAP actions against a real Gmail account. If Gmail rejects `\\Spam` / `\\Trash` / `\\Inbox` label names in this context, add label discovery or provider-specific fallback before closing B3.
- [x] **B3.9** Add Mark as Unread for REST and IMAP as a safer runtime tester action and useful menu command.
- [x] **B3.10** Runtime finding: Mark as Unread works in both normal/main and MC builds; Spam and Delete also work. Archive failure is isolated to archive semantics, not menu dispatch or UID dispatch.
- [ ] **B3.10a** Runtime-validate the new Archive implementation. Expected result: Archive removes the row from Inbox in both builds. If it still fails, add Gmail folder discovery for the All Mail special-use mailbox before changing menu code.
- [ ] **B3.11** If action effects are still inconsistent, add post-action verification for IMAP in debug/runtime builds: after UID STORE success, refetch flags/labels for the UID or refresh the list and log only sanitized action/id/state summaries.

Failure conditions:

- Menu buttons report success while messages remain unchanged.
- IMAP actions use Gmail message id where an IMAP UID/sequence is required.
- Archive/trash/spam expunges the wrong message or every deleted message in the mailbox.
- OAuth/REST behavior regresses while adding IMAP support.

### B4. Date/age display mode

Problem:

Gmail rows need a user-selectable date display style. Some users prefer compact numeric dates; others prefer human words.

Tasks:

- [ ] **B4.1** Add `gmail.date_display_mode` with allowed values `words` and `numeric`. Default should preserve the current relative/words style unless visual review says otherwise.
- [ ] **B4.2** For `words`, use concise intelligent labels: `Today`, `Yesterday`, `Last Week`, `Last Year`, and existing hour/day phrasing where it reads better.
- [ ] **B4.3** For `numeric`, format current-year dates as `DD/MM` and older/different-year dates as `DD/MM/YYYY`.
- [ ] **B4.4** Add the setting to defaults, widget apply logic, settings UI, round-trip tests, and row formatting tests.
- [ ] **B4.5** Recompute timestamp column width from the selected mode so sender/subject columns stay aligned.

### B5. Thread collapse / duplicate conversation display

Problem:

Mail that Gmail would show as one thread can appear as multiple IMAP entries. The widget should make this more palatable without pretending different read states are the same.

Preferred behavior:

- Collapse truly identical/thread-related entries and show a count suffix such as `(3)`.
- Split read and unread groups, even if they share the same Gmail thread id, so unread mail remains visually actionable.
- Grouping must be optional and defaulted off (`gmail.group_threads = False`) until the Inbox mismatch and action semantics are proven in runtime.

Tasks:

- [ ] **B5.1** Prefer Gmail `X-GM-THRID` as the grouping key when present.
- [ ] **B5.2** Split groups by unread/read state: grouping key should include `is_unread`.
- [ ] **B5.3** Fallback only to conservative exact grouping when Gmail thread id is missing: normalized sender + normalized subject + same mailbox/date window. Do not over-collapse unrelated messages.
- [ ] **B5.4** Render a count suffix such as `(3)` on sender or subject without breaking subject shortening rules.
- [ ] **B5.5** Decide and document action semantics for a collapsed row before implementation: open should go to the thread URL; mark read/archive/trash should apply to all grouped entries only if every entry has an actionable backend id, otherwise apply to the newest entry and log the limitation.
- [ ] **B5.6** Add tests for read/unread split groups, Gmail thread-id grouping, fallback exact grouping, and count rendering.
- [ ] **B5.7** Validate against the PayPal duplicate case: two same-sender/same-subject rows in the same read/unread bucket should collapse with a visible count, while a read PayPal and unread PayPal should remain separate.
- [x] **B5.8** Add `gmail.group_threads` defaulted to `False` and a settings checkbox. Current runtime should leave grouping off.

## 8. Phase C - Threading, Lifecycle, and Resource Safety

### C1. Widget fetch lifecycle

Current state:

`GmailWidget` imports `ThreadManager` and has an async fetch path, but it still has fallback `QTimer` behavior, shared state guarded by a plain lock, and stale-result risks to verify.

Files:

- `widgets/gmail_widget.py`
- `widgets/overlay_timers.py` if needed
- `core/threading/manager.py` for canonical API confirmation
- `tests/test_gmail_widget.py`

Tasks:

- [x] **C1.1** Confirm the canonical UI-thread helper name in `ThreadManager` and use only that helper. Canonical helper is `ThreadManager.run_on_ui_thread(...)`.
- [x] **C1.2** Ensure all updates to `_emails`, `_unread_count`, `_last_error`, `_has_displayed_valid_data`, sounds, visibility, fade, and `update()` happen on the UI thread.
- [x] **C1.3** Keep `_fetch_in_progress` guarded so overlapping refreshes are skipped.
- [x] **C1.4** Add a generation/cancel token so a fetch result is ignored after `cleanup()` or after backend settings change.
- [ ] **C1.5** Prefer `create_overlay_timer()` / project timer registration. If `QTimer` fallback remains, document why and ensure it is parented/stopped/deleted.
- [ ] **C1.6** Stop timers on hide/cleanup; resume on show/activate if widget lifecycle expects that.
- [ ] **C1.7** Ensure `_sound_player` usage is cleaned up or delegated safely to the singleton without dangling signal connections.
- [ ] **C1.8** Create `QMenu` per click or register/parent/clear it so cleanup cannot leave stale menus.

Failure conditions:

- Background task calls Qt methods directly.
- Fetch result mutates widget after cleanup.
- Timer continues firing when widget is hidden or destroyed.

### C2. Backend, OAuth, and settings UI blocking

Current state:

Some backend locks may be fine, but network/DPAPI work must not block the settings dialog or overlay UI. This is now the highest-risk remaining implementation area because it mixes Qt widgets, DPAPI file writes, IMAP network login, OAuth callback server lifetime, and user-visible status messages.

Files:

- `core/gmail/gmail_backend.py`
- `core/gmail/gmail_oauth.py`
- `core/gmail/gmail_imap.py`
- `core/gmail/gmail_client.py`
- `ui/tabs/widgets_tab_gmail.py`

Tasks:

- [x] **C2.1** Move `import re` to module top in `gmail_imap.py`.
- [ ] **C2.2** In `gmail_backend.py`, avoid raw refresh threads. Use `ThreadManager.submit_io_task()` for network refresh paths.
- [ ] **C2.3** Protect `_last_error`, `_last_unread_count`, and backend client/mode swaps with a short lock or UI-thread ownership. Do not hold locks during network I/O.
- [ ] **C2.4** In `gmail_oauth.py`, run the OAuth callback server via managed background work and provide cancellation/timeout cleanup.
- [ ] **C2.5** Ensure local OAuth server calls `shutdown()` and `server_close()` in a `finally` path.
- [ ] **C2.6** In `widgets_tab_gmail.py`, offload IMAP connection tests from the UI thread.
- [ ] **C2.7** In `widgets_tab_gmail.py`, offload DPAPI encryption/save-and-test work from the UI thread.
- [ ] **C2.8** Apply settings dialog result labels via the UI-thread helper only.
- [ ] **C2.9** Review `gmail_client.py` lock scope. It may keep a plain lock for short token/client state coordination, but it should not hold a lock across long network requests unless truly necessary.

Failure conditions:

- Settings dialog freezes during Save & Test.
- OAuth local server thread cannot be stopped.
- Backend state can briefly point to `mode='imap'` while the IMAP client is `None`.

Implementation detail for the next pass:

- `widgets_tab_gmail.py` currently runs `backend.save_imap_credentials(...)` and `backend.test_imap_connection()` synchronously from `_on_gmail_imap_save(...)`. This can block the dialog on DPAPI writes and network login. Move the full save-and-test body into an IO task.
- Do not read Qt fields from the worker after dispatch. Capture `email_addr` and `app_pw` on the UI thread first, then pass plain strings into the IO function.
- Disable the Save & Test button while the IO task runs. Re-enable it only from `ThreadManager.run_on_ui_thread(...)`.
- The worker should return a small result object/dict such as `{success: bool, email: str, error_kind: str}`. Do not return raw exceptions containing paths, passwords, server banners, or tracebacks to the UI.
- UI result handling should set `gmail_auth_status`, show `StyledPopup` success/warning, and call `_refresh_gmail_auth_state(tab)` only on the UI thread.
- If save succeeds but test fails, keep credentials only if that is deliberate. Preferred behavior for stable UX: save after successful login, or clear failed credentials after warning. Pick one behavior and document it in this plan/spec before implementation.
- `gmail_backend.py` should expose a helper that tests supplied credentials without mutating persistent state, e.g. `test_imap_credentials(email, app_password) -> bool`, so settings UI can avoid saving bad credentials. Then `save_imap_credentials(...)` should run only after a successful test.
- Keep backend locks short. Do not hold a backend lock while `GmailImapClient.test_connection()` performs network I/O.
- Add tests around the helper behavior using fake credentials/mocked `GmailImapClient`, including "test fails -> no credential file write".

OAuth callback server assessment:

- `gmail_oauth.py` still owns a raw daemon `threading.Thread` for `HTTPServer.serve_forever`. This is not immediately breaking focused tests, but it is not release-ready.
- The next OAuth pass should track an auth attempt id, server instance, timeout, and cancellation event. Starting a new auth flow must stop any previous server before binding another port.
- `_stop_callback_server()` must call both `shutdown()` and `server_close()` and clear `_auth_server` / `_auth_thread` references in a finally path.
- Token exchange POST is currently synchronous in the callback path. If it can run on the server thread without touching Qt directly, that is acceptable; any signals/UI effects must be queued safely.

### C3. Settings flicker regression

Problem:

The settings flicker/ghost-window bug has reappeared after Gmail settings work. Historical bug R-18 documented a similar issue caused by redundant explicit visibility changes during settings UI construction. The user suspects one of the Gmail comboboxes or sliders.

Files:

- `ui/tabs/widgets_tab_gmail.py`
- `ui/tabs/widgets_tab.py`
- `Docs/Historical_Bugs.md`
- `tools/flicker_test.py`
- `tools/winprobe_observer.py`

Tasks:

- [ ] **C3.1** Re-read `Docs/Historical_Bugs.md` R-18 before changing the settings UI further.
- [ ] **C3.2** Audit Gmail settings construction for `setVisible(True)`, popup widgets, combobox/sliders created before parent/layout ownership is stable, and signal emissions during load.
- [ ] **C3.3** Ensure load/reset/import paths block signals while setting Gmail combo/spin/slider values, especially backend, display monitor, position, opacity, border opacity, and sound volume.
- [ ] **C3.4** Run `tools/flicker_test.py` and/or `tools/winprobe_observer.py` before closing the bug.
- [ ] **C3.5** Add a note to `Docs/Historical_Bugs.md` if a new root cause is found, including the exact forbidden pattern.

Failure conditions:

- Flicker is dismissed because unit tests pass.
- A Gmail settings control calls explicit visibility toggles during construction without a runtime reason.
- Load/save handlers fire repeatedly while settings values are being populated.

## 9. Phase D - Remaining Visual Customisation

### D0. Header parity with Media/Spotify/Reddit widgets

Problem:

Screenshot review shows the Gmail header frame exists but does not have parity with the other overlay headers. The Gmail logo is too small, the header border/frame thickness and padding feel lighter than Media/Spotify/Reddit, and the top offset inside the outer card is not aligned with the visual language used elsewhere.

Files:

- `widgets/gmail_widget.py`
- `ui/tabs/widgets_tab_gmail.py` only if settings are needed
- `core/settings/default_settings.py` only if settings are needed
- `tests/test_gmail_widget.py`

Tasks:

- [ ] **D0.1** Compare Gmail header geometry against Media/Spotify/Reddit header values in code, not just by eye:
  - logo size,
  - frame padding x/y,
  - frame border width,
  - frame radius,
  - top inset from outer card,
  - text baseline and font weight.
- [x] **D0.2** Tune Gmail defaults to match the established header family. Prefer constants/private attributes over user settings unless the value is genuinely user-facing.
- [x] **D0.3** Increase Gmail logo size if needed so it visually matches the Spotify/Reddit header icon scale.
- [ ] **D0.4** Match frame border thickness and radius to the project header-frame helper style. Do not create a second border style just for Gmail.
- [ ] **D0.5** Reduce or adjust top padding so the Gmail header sits with similar top breathing room to Media/Spotify/Reddit.
- [ ] **D0.6** Add a screenshot/manual validation note after implementation comparing Gmail next to at least Reddit and Spotify/Media.

Failure conditions:

- Header frame technically exists but still reads as visually unrelated to other widgets.
- Logo is visibly smaller than peer widget icons.
- Header frame top padding makes Gmail look vertically misaligned inside its card.

### D1. Envelope vertical alignment

Current state:

The plan previously marked this done. Verify visually before spending more time. The target behavior is that envelope icons align with the text row center using actual row font metrics and cached pixmap size.

Tasks:

- [x] **D1.1** Compute line center from row y and line height.
- [x] **D1.2** Compute envelope y from pixmap height.
- [x] **D1.3** Clamp y inside the row.
- [ ] **D1.4** Manual visual check at default font size and at one larger font size.
- [ ] **D1.5** Replace current unread/read envelope PNGs with cleaner black-and-white assets. Current icons are visibly jagged/distorted at row size; create/export at the target pixel size or a high-resolution source that scales cleanly.

### D2. Separator controls

Current state:

Separator color/thickness and boundary separator color/thickness appear implemented in `widgets/gmail_widget.py`, `widgets_tab_gmail.py`, and defaults. Treat this as verification unless a bug is found.

Tasks:

- [x] **D2.1** Add row separator color setting.
- [x] **D2.2** Add row separator thickness setting.
- [x] **D2.3** Add unread/read boundary separator color setting.
- [x] **D2.4** Add unread/read boundary separator thickness setting.
- [x] **D2.5** Paint using configured pens.
- [x] **D2.6** Add settings UI controls.
- [ ] **D2.7** Verify settings round-trip includes all four values.

### D3. Per-element fonts

Problem:

The widget still largely uses one family/size and a header size. Header, subject, sender, and time need independent controls.

Files:

- `widgets/gmail_widget.py`
- `ui/tabs/widgets_tab_gmail.py`
- `core/settings/default_settings.py`
- `tests/test_gmail_settings_roundtrip.py`

Tasks:

- [ ] **D3.1** Add header font family/size/weight settings.
- [ ] **D3.2** Add subject font family/size/weight settings.
- [ ] **D3.3** Add sender font family/size/weight settings.
- [ ] **D3.4** Add time font family/size/weight settings.
- [ ] **D3.5** Add a safe string-to-`QFont.Weight` helper with fallback.
- [ ] **D3.6** Recompute header height, row height, elision widths, and hit rects after font changes.
- [ ] **D3.7** Add settings UI controls in Fonts/Header buckets.
- [ ] **D3.8** Extend settings round-trip tests.

Failure conditions:

- Changing font size clips rows or leaves hit rects stale.
- Header still uses the base widget font family after dedicated header settings are applied.

Implementation detail:

- Keep the existing `font_family` / `font_size` as the global fallback. New per-element keys should default to the global values rather than duplicating unrelated defaults:
  - `header_font_family`, `header_font_size`, `header_font_weight`
  - `subject_font_family`, `subject_font_size`, `subject_font_weight`
  - `sender_font_family`, `sender_font_size`, `sender_font_weight`
  - `time_font_family`, `time_font_size`, `time_font_weight`
- Add small helpers in `widgets/gmail_widget.py`:
  - `_font_weight_from_string(value: str, default: QFont.Weight) -> QFont.Weight`
  - `_make_font(family: str, size: int, weight: str, fallback_size: int) -> QFont`
  - `_row_metrics() -> dict` if repeated row sizing math grows.
- Do not compute row height from only the subject font after this change. Row height must use `max(subject_fm.height(), sender_fm.height(), time_fm.height(), envelope_height) + vertical padding`.
- Header layout must use the header font helper. Email rows must use subject/sender/time font helpers.
- After applying any font setting, call `_update_card_height_from_content(...)`, update position, and repaint.
- Settings UI should group header font controls in Header, and subject/sender/time controls in Fonts. Use compact rows; avoid duplicating the old global Font control until the new controls fully cover it.

### D4. Per-element colors

Problem:

The widget needs independent colors for header, unread/read subject, unread/read sender, and time. Do not mutate shared `self._text_color` to derive read colors.

Tasks:

- [ ] **D4.1** Add `gmail.header_text_color`.
- [ ] **D4.2** Add `gmail.subject_color_unread`.
- [ ] **D4.3** Add `gmail.subject_color_read`.
- [ ] **D4.4** Add `gmail.sender_color_unread`.
- [ ] **D4.5** Add `gmail.sender_color_read`.
- [ ] **D4.6** Add `gmail.time_color`.
- [ ] **D4.7** Apply colors per row from `email.is_unread`.
- [ ] **D4.8** Add color swatches to the existing Colours bucket.
- [ ] **D4.9** Preserve alpha values through load/save.

Failure conditions:

- Read/unread colors are chosen by row position instead of `email.is_unread`.
- One color setting mutates another stored `QColor`.

Implementation detail:

- Add a color parsing helper that accepts `QColor`, `[r,g,b,a]`, `[r,g,b]`, and falls back safely.
- Store independent `QColor` copies for every setting. Never assign `self._subject_color_read = self._text_color` by reference.
- Default read colors can be derived once during initialization/settings fallback, but should not be recomputed every paint.
- Paint order should set pens locally for header/time/sender/subject and should not rely on painter pen state from a previous row.
- Extend cache serialization only if new color data is ever stored with cached emails, which should not be necessary.

### D5. Sender and subject cleanup, title case, and shortening controls

Problem:

Sender and subject display text is currently too literal and too noisy. Screenshot examples include sender values such as `PayPal <service...`, quoted senders, no-reply style addresses, and long payment/account subjects. The current title-case logic also breaks contractions (`You've` -> `You'Ve`), which should never happen.

Reference notes:

- RFC 5322 models address display as an optional `display-name` plus an address in angle brackets; use that structure rather than ad hoc `<...>` chopping as the first step.
- Python's `email.utils.parseaddr(...)` is the local standard helper for splitting a header address into real-name and email-address parts. Use it before custom cleanup rules.
- There is no universal, proven display-cleanup algorithm for sender/subject strings beyond standards-compliant header decoding/parsing. Keep the standard parse step as the foundation, then apply small, test-backed UI heuristics only when they improve this widget's display.

Tasks:

- [x] **D5.1** Replace `_smart_title_case(...)` with a contraction-safe title-casing helper.
- [x] **D5.2** Preserve apostrophe contractions and possessives as a single word. Examples:
  - `you've` -> `You've`
  - `you'll` -> `You'll`
  - `it's` -> `It's`
  - `customer's` -> `Customer's`
- [x] **D5.3** Preserve all-caps acronyms and mixed technical tokens where reasonable (`AI`, `NASA`, `2FA`, `COGNOSPHER...`).
- [x] **D5.4** Add `gmail.max_subject_words`. Default: `4`. `0` or blank disables the word limit.
- [x] **D5.5** Add `gmail.max_subject_chars`. Default: blank/`0`. `0` or blank disables the character limit.
- [x] **D5.6** Implement subject shortening before pixel elision:
  - If only word limit is set, keep up to that many words and append `...` when text was shortened.
  - If only character limit is set, keep up to that many characters without splitting surrogate/combining sequences if practical, trim trailing whitespace/punctuation, and append `...` when shortened.
  - If both are set, follow the screenshot-requested examples: character limit is a hard cap when it would be shorter than the word-limited phrase, but a short subject may exceed the word limit when it still fits under the character limit. In practice: build both candidates, choose the longer candidate that does not exceed the character cap, then append `...` only if the original was shortened.
- [x] **D5.7** Add `gmail.clean_sender_names`. Default: `True`.
- [x] **D5.8** Implement sender cleanup in this order:
  1. Decode MIME header value as already done.
  2. Use `email.utils.parseaddr(...)` to split display name and address.
  3. Prefer display name if present; otherwise derive from address local/domain in a conservative way.
  4. Remove surrounding quotes if they enclose the whole name.
  5. Remove content from the first `<` onward unless doing so leaves an empty name.
  6. Remove content from the first ` - ` / ` – ` / ` — ` onward unless doing so leaves an empty name.
  7. Do not apply destructive cleanup when the candidate sender is 3 characters or fewer.
  8. Collapse whitespace and strip trailing punctuation.
- [x] **D5.9** Add conservative extra sender cleanup patterns:
  - Strip `via ...` suffixes when a real display name remains.
  - Convert bare `no-reply`, `noreply`, `notification`, or `alerts` local parts into a domain/org label only when no display name exists.
  - Preserve personal names with non-ASCII letters (e.g. `Rene van Heerd...`) and do not title-case sender names by force.
- [x] **D5.10** Add `gmail.max_sender_words`. Default: `3`. `0` or blank disables sender word shortening.
- [x] **D5.11** Apply sender cleanup and subject shortening before `QFontMetrics.elidedText(...)`; pixel elision remains the final guard against overlap.
- [x] **D5.12** Add controls to the existing Appearance/Truncation area without duplicating old controls:
  - Clean Up Sender Names checkbox,
  - Maximum Sender Words,
  - Maximum Subject Words,
  - Maximum Subject Characters.
- [x] **D5.13** Add tests for:
  - `You've` not becoming `You'Ve`,
  - `PayPal <service@paypal.com>` -> `PayPal`,
  - quoted sender names,
  - `takealot.com <info@...>` -> `takealot.com` or equivalent non-noisy display,
  - subject word/character interactions using the examples above,
  - blank/zero values disabling their respective limit.
- [x] **D5.14** Title-case sender display enough to avoid visually weak lowercase starts while preserving brand/mixed casing:
  - `takealot.com` -> `Takealot.com`
  - `alerts@talkwalker.com` -> `Alerts@talkwalker.com` when raw address display is used
  - preserve `PayPal`, `ChatGPT`, `FNB`, `AI`.
- [x] **D5.15** Fix row columns so all visible subjects start at the same x position and all visible senders end at the same column. Short senders should leave blank space, not pull subjects left.
- [x] **D5.16** Add `gmail.sender_column_width`. Default: `180` px. This is the user-adjustable alignment control for the sender/subject boundary; max sender words only controls content cleanup and must not shift columns row-by-row.

Failure conditions:

- Title case splits contractions after apostrophes.
- Sender cleanup removes the whole sender or damages short names.
- Subject word/character controls contradict the examples in this section.
- Sender cleanup exposes raw email addresses when a reasonable display name exists.
- Character/word shortening replaces pixel elision.
- Unicode text is sliced in a way that corrupts display.
- Time/menu areas overlap subject text.

Implementation detail:

- Put reusable pure helpers in `widgets/gmail_components.py` so they can be tested without a Qt app:
  - `clean_sender_name(raw: str, enabled: bool = True, max_words: int = 3) -> str`
  - `smart_title_case_subject(raw: str) -> str`
  - `shorten_subject(raw: str, max_words: int = 4, max_chars: int = 0) -> str`
- Use `email.utils.parseaddr(...)` inside sender cleanup. On older Python versions where strict parsing behavior differs, fail soft and fall back to the raw decoded string.
- Use character/word settings to prepare display strings. Final display should always go through `QFontMetrics.elidedText(...)`.
- Suggested helper remains useful for final pixel caps: `_pixel_cap_for_chars(fm: QFontMetrics, chars: int) -> int`, using `horizontalAdvance("W" * chars)` as an upper bound.
- Compute available row width in this order:
  1. content width after margins/padding,
  2. subtract envelope width,
  3. subtract action menu width,
  4. subtract timestamp width,
  5. reserve minimal gaps,
  6. split remaining space between sender and subject caps.
- If sender is hidden, subject may use the sender allocation. If subject is hidden, sender may use the subject allocation.
- Add tests that subject/sender cleanup alters display strings without allowing negative paint widths.

### D6. Settings UI reorganisation

Current state:

Some bucket work already exists. Do not duplicate controls. Finish by aligning buckets with the final setting groups and keeping backend/auth prominent.

Files:

- `ui/tabs/widgets_tab_gmail.py`

Target buckets:

- Backend & Auth: backend combo, IMAP email/password, Save & Test, OAuth info/authorize, account status, sign out.
- Layout: display, position, single width, max emails, refresh, label filter, account slot.
- Visibility: sender, subject, envelope, timestamp, separators, menu, unread count, title case, desaturate.
- Header: header border, header font controls, header text color.
- Fonts: subject/sender/time font controls.
- Colours: unread/read subject, unread/read sender, time.
- Separators: separator colors/thicknesses.
- Text Cleanup: clean sender names, max sender words, sender column width, max subject words, max subject characters.
- Sound: enable sound, volume, file path, test.

Tasks:

- [ ] **D6.1** Keep backend/auth controls visible near the top. They may be in the first expanded bucket, but they must not be buried.
- [ ] **D6.2** Use the project's existing bucket/collapsible pattern; do not introduce a second style.
- [ ] **D6.3** Remove old flat-row duplicates after moving controls.
- [ ] **D6.4** Persist bucket collapse state only through the existing settings pattern.
- [ ] **D6.5** Ensure every control still participates in save/load/import/reset.
- [ ] **D6.6** Smoke-test opening the settings dialog with Gmail enabled and disabled.

Implementation detail:

- Current UI already has Layout, Appearance, Separators, and Notification Sound buckets. The next pass should evolve those rather than rebuilding from scratch.
- Recommended near-term shape:
  - Keep Enable + backend/auth controls outside collapsed polish buckets.
  - Keep Layout as the compact geometry/routing bucket: Display above Position, then Width, Max Emails, Refresh, Label Filter, Account Slot.
  - Split Appearance into Visibility, Header, Fonts, Colours, and Text Cleanup when doing the bucket reorganisation pass. The text-cleanup controls currently live in Appearance and must be moved without duplication.
  - Keep Separators and Sound as existing buckets.
- When moving controls, search for every control in `load_gmail_settings(...)` and `save_gmail_settings(...)` in the same patch. A moved control that still saves correctly is fine; a moved control with duplicate old/new widgets is not.
- Persisted bucket state keys must remain stable once introduced. Prefer `gmail_bucket_header`, `gmail_bucket_fonts`, etc. only if the existing helper expects that shape.

### D7. Manual refresh affordances

Problem:

Gmail needs the same quick manual refresh ergonomics users already expect from Reddit widgets, plus a visible flat refresh button for discoverability.

Tasks:

- [x] **D7.1** Add a flat icon-only grey refresh button in the Gmail widget top-right. It should be visually quiet and not introduce a large text/control surface.
- [x] **D7.1a** Replace the failed circular-arrow attempts with an arrowless spiral glyph after runtime screenshot review showed the arrow direction remained ambiguous/backwards.
- [x] **D7.2** The refresh icon should spin or animate while a forced refresh is in progress, then stop on success, failure, or cancellation.
- [x] **D7.3** Clicking the refresh icon forces an email refresh immediately, respecting the existing fetch-in-progress guard so repeated clicks do not spawn overlapping network work.
- [x] **D7.4** Double-clicking blank space inside the Gmail widget should force a refresh, matching the existing Reddit widget behavior. Do not let row double-clicks both open a link and refresh.
- [x] **D7.5** Add hit rect tests for refresh button vs row/menu/header areas.
- [ ] **D7.6** Runtime-validate that refresh animation does not tick continuously when idle.
- [ ] **D7.7** Runtime-validate the spiral glyph visually. If the spiral still reads poorly, replace it with a small PNG/icon asset rather than another hand-drawn arrow attempt.

Failure conditions:

- Refresh click starts overlapping IMAP/REST fetches.
- Spinner keeps animating after cleanup or after fetch completes.
- Blank-space double-click refresh steals row/menu/header clicks.

### D8. Defaults and hardcoded-value audit

Problem:

Gmail has grown quickly and now needs a pass to make sure implementation constants are either true private visual constants or are backed by the settings/defaults system. User-facing defaults must not be hardcoded only in the widget or settings UI.

Tasks:

- [ ] **D8.1** Search Gmail files for duplicated default literals in `widgets/gmail_widget.py`, `ui/tabs/widgets_tab_gmail.py`, `core/gmail/*`, and tests.
- [ ] **D8.2** For every user-facing setting, ensure the default exists in `core/settings/default_settings.py`, loads through `widgets_tab_gmail.py`, applies in `GmailWidget`, and is covered by settings round-trip tests.
- [ ] **D8.3** Keep true private drawing constants private when they are not user-facing, but document why they are constants if they affect cross-widget parity.
- [ ] **D8.4** Remove stale compatibility defaults once migration behavior is deliberately retired. Until then, compatibility fallbacks should be clearly marked as legacy input, not canonical defaults.
- [ ] **D8.5** Update `Spec.md` if the audit changes what counts as a canonical Gmail setting.

Failure conditions:

- The same user-facing default exists in three places with different values.
- Settings UI default differs from runtime widget default.
- Tests assert hardcoded values that are not canonical defaults.

## 10. Phase E - Validation and Release Hygiene

### E1. Automated validation

- [x] **E1.1** Run focused Gmail tests:
  - `tests/test_gmail_oauth.py`
  - `tests/test_gmail_client.py`
  - `tests/test_gmail_components.py`
  - `tests/test_gmail_dev_gate.py`
  - `tests/test_gmail_settings_roundtrip.py`
  - `tests/test_gmail_widget.py`
- [x] **E1.2** Add focused tests for `core/gmail/gmail_deeplinks.py`.
- [ ] **E1.3** Run broader widget/settings tests touched by the changes.
- [x] **E1.4** Run compile check for touched Python files.
- [ ] **E1.5** Run lint/format checks using the repo's established command if available.

### E2. Manual / visual validation

- [ ] **E2.1** Run with `--devgmail` in normal mode. Verify widget appears only when enabled.
- [ ] **E2.2** Validate all nine positions on at least one 1080p display.
- [ ] **E2.3** Validate single `gmail.width` at left, center, and right anchors.
- [ ] **E2.4** Validate Media-style margins keep header, rows, empty state, error state, separators, and clicks aligned.
- [ ] **E2.5** Validate header border enabled/disabled.
- [ ] **E2.6** Validate Gmail header parity beside Media/Spotify/Reddit: logo scale, border thickness, radius, and top padding.
- [ ] **E2.7** Validate title case and cleanup with real noisy Gmail sender/subject samples.
- [ ] **E2.8** Validate row click opens exact Gmail conversation when `open_url` exists.
- [ ] **E2.9** Validate vertical action menu click opens the menu, not the message.
- [ ] **E2.10** Validate header click opens Gmail inbox for the configured account slot.
- [ ] **E2.11** Validate settings dialog remains responsive during IMAP Save & Test.
- [ ] **E2.12** Validate new-mail sound only fires after the initial fetch.
- [ ] **E2.13** Validate `.scr` preview URL opening through the secure URL bridge.

### E3. Secure desktop checks

- [ ] **E3.1** `.scr` preview: click Gmail header -> browser opens via bridge.
- [ ] **E3.2** `.scr` preview: click email row -> exact Gmail conversation opens via bridge when URL is available.
- [ ] **E3.3** `.scr` preview: fallback URL opening does not crash even if secure-desktop browser launch is blocked.
- [ ] **E3.4** Logs remain sanitized during auth failures, IMAP failures, and URL opening failures.

### E4. Performance and resource checks

- [ ] **E4.1** Profile `paintEvent()` with 10 emails. Target: under 5 ms per frame on 1080p.
- [ ] **E4.2** Confirm no pixmap scaling happens in `paintEvent()`.
- [ ] **E4.3** Confirm email list is capped at fetch time.
- [ ] **E4.4** Run 50 start/stop cycles or a practical equivalent. Verify no timer/menu leaks.
- [ ] **E4.5** Confirm cleanup stops timers and ignores in-flight results.
- [ ] **E4.6** Audit Gmail for over-painting, over-updating, or per-tick waste. The Gmail widget should not repaint every frame/tick when emails and visual state are unchanged.
- [ ] **E4.7** Verify refresh spinner/timers are active only while refreshing and stop on cleanup.

### E6. Browser placement stretch goal

Low-priority stretch goal:

- [ ] **E6.1** Investigate whether Gmail and Reddit URL opening can prefer the browser process/window on the lowest-index monitor, usually monitor `0`.
- [ ] **E6.2** Keep fallback behavior unchanged if browser/window placement cannot be controlled reliably or would require brittle browser-specific automation.
- [ ] **E6.3** Do not add always-running monitor/window polling just for this. Any placement attempt must be bounded, optional, and resource-light.
- [ ] **E6.4** Keep this shared between Gmail and Reddit URL paths rather than creating a Gmail-only browser-placement hack.

### E5. Repository and docs hygiene

- [ ] **E5.1** Verify no `client_secrets.json` is tracked.
- [ ] **E5.2** Verify no Gmail token, credential, `.enc`, `.pickle`, or cache files are tracked.
- [ ] **E5.3** Ensure `.gitignore` covers Gmail credential/cache artifacts.
- [x] **E5.4** Update `Index.md` if new files such as `core/gmail/gmail_deeplinks.py` are added.
- [x] **E5.5** Update `Spec.md` only if the canonical Gmail contract changes.
- [ ] **E5.6** Add `archive/gmail_feature/README.md` noting it is superseded by the production Gmail modules and retained for history.
- [ ] **E5.7** Add Gmail credential/logging guardrails to `Docs/Guardrails.md` if new patterns are introduced.

## 11. Security and AV Guardrails

Do this throughout implementation, not at the end:

- [ ] **S1** Do not log secrets, tokens, app passwords, OAuth responses, raw headers, message bodies, or snippets.
- [ ] **S2** Keep all Gmail user data under `%APPDATA%/SRPSS/` or the existing app data path helpers.
- [ ] **S3** Do not create runtime `.bat`, `.vbs`, `.ps1`, `.exe`, or hidden subprocess helpers for Gmail.
- [ ] **S4** Do not disable TLS verification or use custom SSL contexts that weaken certificate checks.
- [ ] **S5** Do not dynamically import/eval Gmail code.
- [ ] **S6** If OAuth `invalid_grant` occurs, clear local token state and require re-auth rather than retrying indefinitely.
- [ ] **S7** Document that OAuth uses restricted Gmail scopes and remains optional/dev/advanced unless verification is completed.
- [ ] **S8** Document that IMAP is the recommended backend for normal use.

## 12. Dependency / Distribution Notes

- `requests` is used for OAuth/REST calls and already exists in the project requirements.
- `PySide6.QtMultimedia` is used for OGG notification playback; verify importability in the target frozen build.
- `client_secrets.json` must not be bundled into public builds unless that is an explicit documented release decision.
- A backend proxy would be required to truly hide an OAuth client secret in a distributed public app. This is future work, not required for the IMAP-first dev-gated widget.

## 13. Known Stale/Mistaken Ideas Removed From Earlier Plans

- Do not add `GmailWidgetSettings` to `core/settings/models.py` for this work. Gmail currently follows the flat widget settings dict pattern.
- Do not replace every `threading.Lock` by policy. Replace unmanaged threads and UI-thread blocking; keep short non-Qt locks where appropriate.
- Do not build generic IMAP webmail URLs. Exact row links are Gmail-specific and require Gmail IMAP extension metadata or RFC `Message-ID` search fallback.
- Do not use decimal `X-GM-THRID` directly in Gmail web URLs. Convert to lowercase hex.
- Do not treat separator controls as future work unless validation finds defects; they are already substantially implemented.
