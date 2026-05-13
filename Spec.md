# Spec

Last updated: 2026-05-13

Canonical architecture and behavior contracts for SRPSS.

## 1. Product Intent
- Deliver a smooth, stable, multi-monitor screensaver with configurable overlays.
- Keep settings persistence deterministic and recoverable.
- Keep visualizer mode behavior isolated while sharing explicit neutral seams.

## 2. Runtime Topology
- `main.py` and `main_mc.py` bootstrap runtime variants.
- `ScreensaverEngine` owns source cycling, transition scheduling, and display lifecycle.
- `DisplayWidget` is the fullscreen rendering presenter.
- `WidgetManager` owns overlay widget lifecycle and staged startup coordination.

## 3. Centralized Ownership Contracts
- Async business work uses `ThreadManager`.
- Qt object lifecycle uses `ResourceManager`.
- Settings read/write/migration uses `SettingsManager`.
- Animations route through `AnimationManager`.
- Cross-module publish/subscribe events use `EventSystem`.
- Worker process orchestration uses `ProcessSupervisor`.

## 4. Settings Architecture

### 4.1 Storage model
- Canonical persistence file: `%APPDATA%/SRPSS/settings_v2.json` (MC: `%APPDATA%/SRPSS_MC/settings_v2.json`).
- Structured roots: `widgets`, `transitions`, `ui`.
- Dotted-key API remains available via `SettingsManager`.

### 4.2 Legacy global preset retirement
- Legacy top-level global preset keys are retired: `preset`, `custom_preset_backup`.
- Defaults and modern save paths do not emit those keys.
- Existing settings that contain them are cleaned/migrated safely.

### 4.3 Cache invalidation safety
- Section/root writes (`set('widgets', ...)`, `set('transitions', ...)`, `set_section(...)`) must invalidate descendant dotted-key cache entries.
- New settings APIs must preserve equivalent invalidation behavior.

### 4.4 Reset/import preservation
- Preserve-on-reset keys are centralized in `core/settings/defaults.py`.
- Reset/import logic must use that shared preservation contract.

### 4.5 Persisted visualizer schema migration
- Persisted visualizer-section migrations must be version-gated through settings metadata rather than rerunning full legacy normalization on every load forever.
- Legacy/global visualizer keys may still be normalized for imported or foreign payloads, but the main saved settings file should be upgraded once per schema version bump and then treated as current.

## 5. Visualizer System Contract

### 5.1 Mode identity
Source of truth: `core/settings/visualizer_mode_registry.py`.

Active ids:
- `spectrum`
- `oscilloscope`
- `sine_wave`
- `bubble`
- `blob` (gated by `-devblob`)
- `devcurve` (display label: Spline Curve)

### 5.2 Naming contract
- Internal id and key namespace remain `devcurve`.
- User-facing label is Spline Curve.
- `--devcurve` remains accepted as compatibility no-op.

### 5.3 Shared seams
- Mapping normalization: `visualizer_settings_snapshot.py`
- Technical normalization / legacy migration contract: `visualizer_settings_contract.py`
- Canonical mode/preset activation payload: `visualizer_presets.resolve_visualizer_activation_payload()`
- Runtime config application: `widgets/spotify_visualizer/config_applier.py`
- GPU state handoff: `widgets/spotify_bars_gl_overlay.py`
- Painted-card stencil-mask math: `widgets/spotify_visualizer/overlay_mask.py`
- Overlay runtime-state handoff: `widgets/spotify_visualizer/overlay_state.py`
- Runtime mode/preset resets may preserve the GL overlay object for performance, but they must still blank/hide the overlay, request a cold mode reset, and wait for the fresh activation/generation handoff before first visible bar authority returns.
- Engine config replay: `_replay_engine_config()` reads from authoritative mode config via `_get_mode_technical_config(...)`, not transient widget cache
- Live audio block-size changes are capture-rebind boundaries: when mode-owned technical config changes the preferred block size at runtime, the active audio worker must restart capture instead of waiting for a full runtime rebuild or settings-dialog restart.

### 5.4 Mode isolation
- Mode-owned behavior belongs to mode-owned code.
- Shared seams must remain neutral and explicit.
- No hidden cross-mode dependency on authored mode keys.
- Technical settings are mode-owned at runtime and in canonical persistence. Shared/global technical keys are legacy migration inputs only and must not remain in normalized settings, custom snapshots, or preset payloads.
- Preset-varying runtime visuals that affect activation or renderer state, including bar fill/border styling and legacy ghost controls, are mode-owned too. They must not travel through shared/global authored keys after normalization.
- Startup create, settings refresh, context-menu mode switch, double-click cycle, preset cycle, and forced preset activation must all consume the same resolved mode/preset payload before touching widget, engine, or overlay state.
- Live diagnostics for visualizer activation must report the resolved preset identity and the actual applied worker/widget technical state, not only raw settings payloads.

### 5.5 Runtime card/shadow contract
- Runtime overlay card shadows are painter-owned, not `QGraphicsDropShadowEffect`-owned.
- `widgets.shadows.enabled`, `widgets.shadows.text_enabled`, and `widgets.shadows.header_enabled` are the runtime shadow controls for framed widgets.
- Framed widgets that use the painted shadow path must explicitly clear transparent backing regions before repainting cached shadow output so stale shadow pixels cannot accumulate in the gutter.
- Direct `QWidget` implementations that do not inherit `BaseOverlayWidget` but need framed-card parity, such as the Spotify visualizer, must mirror the same painted-frame contract explicitly rather than assuming inheritance.

## 6. Preset Architecture Contract
- Authored curated source: `presets/visualizer_modes/`.
- Runtime shipped trees are generated artifacts.
- Repair tool must normalize schema without rewriting authored intent.
- Reindex mutates only slot filename numbering and `preset_index`.
- Tests must not require curated/authored preset files to have specific names, slots, or numeric visual values beyond schema/index/repair contracts. Authored preset content may be fixed, indexed, cleaned, or validated structurally, but exact creative values are not a runtime compatibility contract.

## 7. Startup Staging Contract
- Startup timing policy source: `rendering/overlay_startup_policy.py`.
- Spotify-related secondary-stage widgets must wait for anchor/position readiness before reveal.
- Spotify-related secondary-stage widgets must also recover cleanly if their first secondary-stage starter fires before the media anchor becomes visible; later anchor visibility sync must be allowed to release the staged reveal once the centralized manager deadline is satisfied.
- Mute button follows secondary-stage reveal contract.

## 8. Rendering and Input Contract
- GL-first rendering path with safe fallback behavior.
- Input routing is centralized; no widget-specific ad hoc global key/mouse handlers.
- Runtime interaction mode behavior must not break settings launch or shutdown paths.
- In MC builds, Interaction Mode is runtime policy, not an optional session toggle: MC startup and runtime reads treat it as enabled, and MC settings/context-menu surfaces must not offer a disable path that can strand the user outside the intended interaction model.

## 9. Build Variants
- Standard saver and MC maintain separate settings profiles.
- Frozen preset resolution converges on shared ProgramData curated root.

## 10. Gmail Widget Architecture

### 10.1 Availability
- Gmail widget is a normal feature and must not be hidden behind a dev-gate or CLI flag.
- Widget factory registration, settings UI, expected-overlay checks, and rendering paths are always available; actual overlay display is controlled only by `widgets.gmail.enabled` and monitor selection.

### 10.2 Backend routing
- Unified backend (`core/gmail/gmail_backend.py`) routes to OAuth/REST or IMAP based on config
- OAuth mode: `core/gmail/gmail_oauth.py` (PKCE flow, DPAPI token storage)
- IMAP mode: `core/gmail/gmail_imap.py` (App Password authentication)
- REST client: `core/gmail/gmail_client.py` (metadata-only API calls)
- Deep-link helpers: `core/gmail/gmail_deeplinks.py` owns Gmail web URL construction
- IMAP/Gmail row links use `X-GM-THRID` decimal ids converted to lowercase hex for `#all/<thread_hex>` routes; RFC `Message-ID` search is the fallback when thread id is unavailable

### 10.3 Widget contracts
- Overlay widget: `widgets/gmail_widget.py` (email list, actions, paint events)
- Widget components: `widgets/gmail_components.py` (nine-position GmailPosition enum, relative-time formatting, sender/subject cleanup helpers, email cache)
- Settings UI: `ui/tabs/widgets_tab_gmail.py` (backend selector, credentials, widget settings, sender/subject cleanup controls)
- Gmail settings remain a flat dict under `gmail` in `core/settings/default_settings.py`; do not add a Gmail settings dataclass unless the whole widget settings architecture is deliberately migrated
- Gmail settings UI load/reset/import code must block signals for every Gmail control while values are being populated. `GMAIL_SIGNAL_BLOCK_ATTRS` is the canonical Gmail control list and should be reused rather than duplicated.
- Gmail settings panel/button visibility updates must avoid redundant `setVisible(...)` calls during construction and load, following the historical R-18 settings flicker guardrail. When the settings parent page is hidden, backend-specific child panels must compare desired state against explicit hidden state, not transient `isVisible()`, so OAuth-only text/buttons stay hidden for IMAP on fresh settings open.
- If the Gmail backend service is temporarily unavailable during settings construction/load, backend panel visibility must fall back to the UI backend selector value instead of showing both backend panels.
- Gmail settings construction must not synchronously load backend/auth credential state. The initial backend-specific UI should be derived from the combo/defaults, with credential/auth refresh queued after construction.
- Styled combo boxes must not force popup-view creation during settings construction; popup view styling belongs on popup open, not in constructors.
- Gmail IMAP Save & Test must not block the settings UI. Test supplied credentials on the IO pool first, save credentials only after a successful test, and return all UI label/button/popup updates to the UI thread.
- Gmail OAuth code exchange must also stay off the UI thread. The callback server may acknowledge the browser request immediately, but token exchange/network work must go through a real `ThreadManager` IO task and marshal Qt signal/UI updates back to the UI thread.
- Gmail user-facing settings UI defaults must be read from canonical widget defaults; missing Gmail defaults should fail loudly in tests instead of quietly introducing new hardcoded fallback drift.
- Settings-dialog cached widget defaults must be treated as an optimization only. WidgetsTab must merge cached defaults with fresh canonical defaults, and cache invalidation must include both `defaults.py` and `default_settings.py` so new Gmail defaults are not hidden by stale cache data.
- Gmail visual settings must keep geometry and hit rects aligned: display, position, single `gmail.width`, Media-style margins, header frame, and row click targets must be derived from measured widget layout. Gmail must not expose custom per-side padding controls unless the whole widget family gains the same concept.
- Gmail header styling must maintain visual parity with peer overlay headers (Media/Spotify/Reddit): comparable logo scale, frame border weight, radius, and top inset. Default Gmail header font/logo sizing follows Media's derived relationship (`font * 1.2`, then `header * 1.3`), with `gmail.header_logo_px_adjust` reserved for final visual nudging.
- Gmail row interaction must work in normal and MC modes: full row sender/subject hit rect opens the message URL through central input URL routing, while the vertical action-menu hit rect opens the menu and must not be consumed by row click handling
- Gmail normal/main URL clicks use the same helper/task-scheduler bridge route as Reddit; MC URL clicks use the MC direct Qt/browser route. The two paths must not be mixed.
- Gmail MC action-menu popup handling must not immediately reclaim DisplayWidget focus in a way that steals input from the popup; the menu object must remain alive until it hides.
- Gmail action-menu operations must have real backend effects for the active backend. IMAP actions must use IMAP-safe identifiers such as UID, not only Gmail web/message ids.
- Gmail action menus must include Mark as Read/Unread, Spam, and Delete where the active backend can support them. Archive is hidden for IMAP because runtime testing repeatedly showed it accepts no reliable local behavior; the Archive code path may remain for OAuth/future diagnostics. Required Gmail action image assets must be present in the repo and covered by build-script asset tests; missing optional image assets must still fall back to simple generated icons rather than silently leaving important actions visually blank.
- Gmail display text cleanup is part of the widget contract: title casing must preserve contractions, sender cleanup must prefer RFC-style display names over raw addresses, subject/sender shortening must run before final pixel elision, and punctuation-only separator tokens such as `|` or `-` must not count as words
- Gmail row text columns must remain stable across visible rows: timestamp, sender, and subject slots should use shared widths so shorter senders leave blank space instead of moving the subject start position; the sender/subject boundary is user-adjustable via `gmail.sender_column_width`
- Gmail IMAP Inbox listing must preserve the active mailbox order returned from the selected label instead of over-fetching and date-sorting in the widget. Runtime evidence showed the over-fetch/date-sort mitigation mismatched Gmail's visible Inbox.
- Gmail cached mail must be stored and loaded in the same backend order used for visible display, so startup cache display does not visibly reorder a few seconds later when the live fetch completes.
- Gmail sender casing may apply conservative display capitalization for visual consistency, but must preserve established mixed/all-caps brand tokens such as `PayPal`, `ChatGPT`, `FNB`, and `AI`
- Gmail date display modes are `relative`, `numeric`, and `words`. Relative uses age labels such as `Yesterday`, `Last Week`, `Last Month`, and `Two Years Ago`; numeric uses numbered dates; words uses calendar labels such as `April 16th`.
- Gmail thread/duplicate display may collapse truly identical or Gmail-threaded entries only when `gmail.group_threads` is enabled. It defaults to off until grouping semantics match Gmail well enough in runtime, and read/unread groups must remain separate.
- Gmail IMAP Archive is considered unsupported/hidden for now. The retained code still attempts `-X-GM-LABELS` before hard-named All Mail MOVE for future diagnostics, but the IMAP menu must not present Archive as a working user action.
- Gmail may expose manual refresh through an optional, default-on quiet icon-only refresh control and blank-space double-click, but refresh must respect fetch-in-progress guards and must not animate or repaint continuously while idle. If a hand-drawn arrow reads ambiguously in runtime screenshots, prefer a neutral spiral or asset-backed icon over repeated arrow geometry tweaks.
- Gmail user-facing defaults must come from the settings/defaults system. Hardcoded Gmail values are acceptable only for private drawing constants or legacy migration fallbacks.
- Gmail settings buckets must not disable/re-enable whole-dialog updates or pre-polish hidden bucket bodies by temporarily showing them during settings construction. R-18 established constructor-time visibility calls as a settings flicker hazard, so bucket toggles should use ordinary guarded body visibility changes and keep runtime flicker validation open until proven.
- Gmail Text Limits settings should stay readable at normal settings widths: sender word and sender-column controls on one row, subject word and subject-character controls on a second aligned row/grid.
- Gmail must not do per-tick network work, pixmap scaling, lazy pixmap conversion, over-painting, or unnecessary `update()` calls when its data and animation state are unchanged.
- Gmail stable visual content may be cached in a DPR-aware transparent pixmap, but live dynamic controls such as the refresh spiral must be painted on top without invalidating the stable cache. Cache regeneration must not change widget graphics effects, hide/show widgets, reparent, resize, or call overlay-effect invalidation because Qt shadow/effect corruption is a known fragile area.
- Gmail must be included in the shared overlay-effect invalidation cadence used for peer overlay widgets. Do not attempt to detect shadow corruption by introspecting `QGraphicsEffect` state alone; the known failure is visual Qt pixmap/cache corruption and should be treated as a multi-monitor runtime validation problem.
- Runtime widget card shadows are painter-owned and controlled by `widgets.shadows.enabled`, not by Qt drop-shadow effects. Framed overlay cards use cached DPR-aware painter output and explicitly clear each transparent backing region before painting so stale shadow pixels cannot accumulate in the card gutter. `widgets.shadows.text_enabled` controls painter-drawn text shadows and `widgets.shadows.header_enabled` controls painter-drawn header-frame shadows. The Spotify visualizer GL overlay uses a rounded-rect stencil mask in `paintGL()` whenever the painted card shadow path is active; the mask inset must include the 1-px painted-frame inset (`inset=1.0 * dpr`) plus `border_width_px * 0.5 * dpr` so GL content stays inside the inner edge of the centred card pen stroke without changing visualizer content size, amplitude, curve scale, or authored mode behavior.
- Gmail refresh must avoid visible UI churn during pending or active image transitions. If any parent display in the Qt parent chain reports accepted image-change work or a running transition, refresh start should be delayed and fetched mail/error results should be held briefly and applied once idle, so spinner animation, network task submission, cache writes, card-height recompute, unread signals, sound detection, and full widget repaints do not compete with transition frames. If a transition is requested after a refresh is already in flight, Gmail must suspend live refresh-spinner repainting immediately and keep result application deferred until idle.
- Gmail refreshes that return the same visible message list and unread count must not rewrite cache or repaint. Gmail cache writes should use the IO thread pool when available; the UI thread should only perform Qt-owned painting, state application, signals, and UI/media objects that require it.
- Gmail must participate in the shared widget performance logger when perf metrics are enabled, including at least paint, refresh dispatch, fetch result/error apply, and cache write buckets so regressions appear in `perf_widgets.log`.
- Future shared URL opening work may try to prefer a browser window on the lowest-index monitor, but must fall back to current behavior and must not add brittle or always-running browser automation.
- Gmail build/release work must verify all Gmail image assets, notification sound assets, Qt multimedia dependencies, and generated/fallback asset dependencies are included in build scripts, frozen build config, resource copy steps, and installer/package outputs. Widget image lookup must not depend only on the launch cwd, because standard `.scr` launches can start outside the app directory. Frozen builds should prefer `%ProgramData%\SRPSS\sounds\tutuogg.ogg` for the default notification sound, with `resources/tutuogg.ogg` as the script/dev fallback. Build scripts must include only the default OGG, not the entire `resources` directory, so ignored local OAuth files are never bundled. Final packaged artifacts still require runtime validation.
- Gmail must not fade into view when there is no authenticated account information and no usable cache.

### 10.4 Security invariants
- OAuth tokens stored encrypted via DPAPI
- API calls are metadata-only (no body/snippet content)
- `EmailMetadata` may contain provider ids needed for links/deduping (`X-GM-THRID`, `X-GM-MSGID`, RFC `Message-ID`, IMAP UID), but must not contain bodies, snippets, or raw headers
- Secure-desktop/browser opening must use the correct runtime route: SCR/secure-desktop paths use the helper/secure launcher bridge, while MC-mode row/header URL clicks should reach central input routing and open directly via Qt rather than the Reddit helper bridge
- Reddit widget controls that consume a click without producing a URL, such as the refresh spiral, must not set the central `reddit_handled` URL flag. Only a resolved Reddit URL should request the normal-build helper/exit path.
- Reddit refresh spiral clicks must queue refresh through the existing Reddit fetch path, respect fetch-in-progress guards, and defer refresh start/result apply/cache regeneration while parent display transitions are pending or active when an existing cached pixmap can be reused. If a transition is requested after a Reddit refresh is already in flight, Reddit must suspend live refresh-spinner repainting immediately and keep result application deferred until idle.

## 11. Spline Curve (`devcurve`) Visualizer

- `devcurve` is the runtime id for the Spline Curve visualizer.
- Spline Curve foreground specular uses the existing specular alpha path for idle/play behavior: runtime activity fades the specular multiplier down while paused/idle and back up when playback resumes.
- The idle specular fade must not introduce a new shader shape mode, full-width blob chaining, or preset value enforcement. Authored preset alpha remains the base value; runtime activity only multiplies it.
- No credential leakage in tests (all mocked with fake data)

## 12. Documentation Contract
- `Index.md`: module map.
- `Current_Plan.md`: active priorities only.
- `Docs/Guardrails.md`: policy/rules.
- `Docs/Historical_Bugs.md`: historical timeline and root-cause record.
