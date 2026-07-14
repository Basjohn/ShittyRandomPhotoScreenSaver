# SRPSS Steam Widget Family — Architecture-Safe Implementation Plan

**Status:** Achievement Pulse and Abandonment Issues promoted; Steam Journey and Friend Pulse remain dev-gated
**Date:** 2026-07-14
**Scope:** Four independently enabled Steam overlay cards: **Steam Journey**, **Achievement Pulse**, **Abandonment Issues**, and **Friend Pulse**.
**Repository target:** `Basjohn/ShittyRandomPhotoScreenSaver`  
**Supersedes:** Draft 0.1 Steam Subwidgets proposal

---

## 1. Executive decision record

This keeps the original product goal: four attractive, independently configurable Steam cards that share data and assets without becoming one oversized “Steam widget.”

The implementation must, however, be built as an ordinary SRPSS widget family:

- four **separate descriptor-backed overlay widgets**;
- one shared, narrowly scoped **Steam provider/cache layer**;
- one lazily built **Steam** Settings section containing a bordered family shell, a true family master, and four card groups with nested Layout/Appearance/Content buckets where applicable;
- normal SRPSS factory, lifecycle, Custom-layout, input, cache, diagnostics, and settings contracts;
- no private timer manager, thread pool, event loop, widget registry, layout system, or browser launcher.

The four cards remain:

| Stable widget key | Runtime card | Header label | Job |
|---|---|---|---|
| `steam_progress` | Steam Journey | Steam logo + `Steam Journey` | Curate material changes across the user's library journey. The stable key remains unchanged for compatibility. |
| `achievement_pulse` | Achievement Pulse | Steam logo + `Achievement Pulse` | Present one tracked game’s achievement progress as a visual object. |
| `abandonment_issues` | Abandonment Issues | Steam logo + `Abandonment Issues` | Re-surface genuinely lapsed games without inventing history. |
| `friend_pulse` | Friend Pulse | Steam logo + `Friend Pulse` | Show a restrained, privacy-aware view of observable friend activity. |

### 1.1 Corrections made to the initial proposal

| Draft assumption | Revised decision |
|---|---|
| “Genericify the existing OAuth functionality.” | Do **not** generalise Gmail OAuth. The proposed Steam data path is a narrowly scoped Steam credential path built around the user Web API key plus linked SteamID. OpenID is only the browser identity-linking step, and any Steam OAuth use is a separate future discovery item only if Valve documents the exact needed scope. |
| One shared layer can own its own worker/timer machinery. | The shared Steam layer may own normalized data, in-flight request coalescing, cache records, and request policy. `ThreadManager`, `ResourceManager`, `SettingsManager`, `EventSystem`, `AnimationManager`, and existing service-widget helpers remain the owners of work, lifecycle, events, timing, and UI deferral. |
| All cards can simply carry their own “local selection history.” | Semantic selection, cooldowns, dismissals, and rotations are **profile-level family state**, shared across displays. A runtime overlay instance owns only geometry, DPR-specific paint cache, and current applied view state. This prevents duplicate fetches and monitor-by-monitor drift. |
| A fifth enabled field always creates a second rail. | Authored card layout decides whether enabled fields use a first rail, second rail, or compact authored presentation. `Custom` geometry only scales/moves the already-authored card and its elements; it must not decide how many enabled fields are shown, hide lower-priority content, or take outer-size authority back. |
| Every label/value pair must fit one capsule. | Compact capsules remain the default, but the shared visual grammar may measure a value before layout. When enabled and the compact value region would elide, the field reserves the same column on the next whole rail for a fitted full-width value capsule. |
| Artwork shape is a fixed visual preset. | Artwork variants have authored alignment rails and safe user bounds. Achievement Pulse offers Wide, Square, and default Portrait art. Compact art shares the wide/header top-right rails, allows 140-190 authored pixels in width, and grows only the authored vertical envelope so size changes cannot clip or reflow upper content. |
| A polished mock is enough to define the remaining cards. | Achievement Pulse is now the engineering baseline, not a family-wide skin. Future cards inherit settings, painter safety, measurement, cache-first, multi-display, and validation lessons while deliberately establishing different silhouettes and content primitives. |
| Steam Journey can promise a general owned-library update feed. | It ships only after a documented, supported data source is proven against a real test account. No authenticated Store scraping, personalised Calendar dependency, cookies, or undocumented feed may become a fallback. |
| Abandonment Issues can infer absence from playtime or Recent Games. | Smart selection now uses only a valid positive non-future `GetOwnedGames.rtime_last_played` row with explicit verified provenance. Playtime and Recent Games are eligibility/filter inputs, never timestamp substitutes. Unknown remains a real excluded state. |
| Offline friends can always be shown desaturated. | Offline avatars are only meaningful in the explicit presentation/filter modes that include them. The default card remains “currently playing / observed game-change” content and does not silently turn unavailable friend data into an offline roster. |

---

## 2. Non-goals and hard safety boundaries

These are product boundaries, not merely implementation preferences.

- No dependency on Steam’s personalised Calendar.
- No authenticated Store scraping, session cookies, browser automation, Steam password handling, Steam Guard handling, or undocumented private endpoints.
- No globally bundled or developer-shared Steam API key.
- No Steam credential, account identifier, friend directory, visible card history, or cache content in the repository, release package, screenshots, test fixtures, logs, normal settings export, or SST export.
- No per-frame polling, provider calls, image decode, pixmap conversion, cache scanning, or asset scaling in `paintEvent`.
- No whole-library news or achievement scan on every refresh.
- No local Steam-client database scraping until a dedicated discovery gate proves a stable, permitted, user-local source and its privacy implications.
- No “everyone is offline” conclusion from private, unauthorized, timed-out, malformed, or rate-limited friend responses.
- No fabricated last-played, session-start, rarity, ownership, completion, or event time claims.
- No private threads, queues, `QTimer` ownership pattern, global input hooks, or replacement widget setup route.
- No new `QGraphicsDropShadowEffect` layer for Steam cards. Card, text, and header shadows remain painter-owned through the existing overlay/shadow path.
- No runtime fallback that quietly changes data source, cache scope, geometry owner, profile, or display target. Any such fallback is a `WARNING` or higher through the relevant existing diagnostic family.

---

## 3. SRPSS architecture mapping

### 3.1 Existing seams that Steam must use

| Concern | SRPSS owner / path | Steam requirement |
|---|---|---|
| Background work | `core/threading/manager.py` | Every network, disk-heavy cache, image validation, and library-index job enters through the app-shared `ThreadManager`. |
| Qt resource lifecycle | `core/resources/manager.py` | Overlay timers, disposable Qt resources, and cleanup attach through the ordinary resource path. |
| Settings and migrations | `core/settings/settings_manager.py`, `core/settings/default_settings.py`, `core/settings/defaults.py` | Canonical defaults, normalisation, reset/import preservation, and dotted-key invalidation remain single-source. |
| Per-user persistent path | `core/settings/storage_paths.py` | Steam credentials, caches, and assets use the canonical profile path resolver, never cwd or ProgramData. |
| Settings persistence | `core/settings/json_store.py` | Settings writes remain atomic through the existing settings store. Steam caches use a similarly atomic cache-write contract, but are not folded into `settings_v2.json`. |
| Widget factory identity | `rendering/widget_factories.py`, `rendering/widget_descriptors.py` | Each of the four cards is a normal factory-backed descriptor. |
| Creation/startup | `rendering/widget_setup_all.py` | Descriptor-driven setup only; no new manual Steam branches for ordinary cards. |
| Lifecycle/fades/live setting routing | `rendering/widget_manager.py` | Cards participate in the standard lifecycle, fade coordination, visibility rules, stack planning, and descriptor-owned live-refresh routing. |
| Positioning and Custom | `rendering/widget_positioner.py`, `rendering/custom_layout_contract.py`, `rendering/custom_layout_manager.py` | Positions, Custom availability, committed rectangles, reset, bounds, DPR, and monitor transfer all use the shared contract. |
| Runtime input/opening | `rendering/input_handler.py`, existing secure URL launcher seam | Steam click actions use central routing and a validated app URL only. No card creates its own browser helper. |
| Shared service mechanics | `widgets/service_widget_runtime.py` | Use transition-aware deferral, fetch guards, manual-refresh flow, spinner suspension, visible-fallback preservation, startup freshness policy, and cleanup helpers where they fit. |
| Framed-card rendering | `widgets/base_overlay_widget.py` | Use the standard framed-card base and painter-owned shadows. |
| Service data notification | `core/events/event_system.py` | Publish narrowly scoped, generation/profile-aware data-ready events rather than calling arbitrary widget objects across modules. |
| Diagnostics | `--perf`, `--cache`, `--set`, `--geo`, `--life`, `--steam` log families | Use `--steam` for Steam-family provider/cache/widget traces. Keep cross-cutting perf/cache/settings/geometry/lifecycle evidence in the existing sidecars. Do not introduce always-on Steam log chatter or environment-variable diagnostics. |

### 3.2 Classify the family correctly

Each Steam card is simultaneously:

1. a framed overlay card;
2. a service-backed card;
3. a Custom-participating card;
4. a factory/descriptor-backed card; and
5. a multi-display participant.

Those concerns must remain visible in the design. They must not be merged into a vague `SteamWidgetManager` or a magical all-purpose base class.

### 3.3 Proposed file map

New paths are suggestions, not permission to bypass existing seams.

```text
core/steam/
    __init__.py
    credentials.py          # strict encrypted credential/profile store
    backend.py              # supported request transport, timeouts, redaction, result model
    models.py               # frozen normalized records and result/status types
    achievement_pulse.py    # pure selected-app and achievement-progress resolver
    cache.py                # versioned atomic family cache and migration
    assets.py               # safe artwork/avatar fetch, validation, eviction, local references
    errors.py               # public error classification / safe messages
    profile_state.py        # profile-level rotation, cooldown, dismissal and cache state

widgets/
    steam_components.py     # small shared paint/layout/value-format helpers only
    steam_runtime.py        # narrow common service/lifecycle bridge only where justified
    steam_progress_widget.py
    achievement_pulse_widget.py
    abandonment_issues_widget.py
    friend_pulse_widget.py

ui/tabs/
    widgets_tab_steam.py    # one lazily built Steam family section

tests/
    fixtures/steam/         # synthetic, non-secret, non-live payloads only
    test_steam_credentials.py
    test_steam_backend.py
    test_steam_cache.py
    test_steam_assets.py
    test_steam_widget_models.py
    test_steam_progress_widget.py
    test_achievement_pulse_widget.py
    test_abandonment_issues_widget.py
    test_friend_pulse_widget.py
    test_steam_settings.py
```

Expected existing files touched:

```text
core/settings/default_settings.py
core/settings/defaults.py
core/settings/storage_paths.py                  # only if a new canonical Steam path helper is required
core/windows/dpapi.py                            # strict-encryption extension only, without weakening Gmail
rendering/widget_factories.py
rendering/widget_descriptors.py
rendering/widget_setup_all.py                    # only descriptor-consumption / injection extension
rendering/widget_manager.py                      # only descriptor-owned live routing / shared stacking integration
ui/tabs/widgets_tab.py
ui/settings_dialog_cache.py                      # only if defaults-cache dependency registration needs it
Docs/Contracts.md
Docs/10_WIDGET_GUIDELINES.md                     # only if new reusable Steam/service convention is adopted
Spec.md
Index.md
Docs/TestSuite.md
.gitignore
```

### 3.4 Descriptor plan

Add four `FactoryWidgetDescriptor` entries, each with a stable widget key and its own runtime attribute. The Steam family must not be represented as one descriptor that internally spawns four independently movable cards.

Suggested keys and attributes:

| Key | Runtime attribute | Factory route |
|---|---|---|
| `steam_progress` | `steam_progress_widget` | `steam_progress` |
| `achievement_pulse` | `achievement_pulse_widget` | `achievement_pulse` |
| `abandonment_issues` | `abandonment_issues_widget` | `abandonment_issues` |
| `friend_pulse` | `friend_pulse_widget` | `friend_pulse` |

All four should receive the existing base/shadow config through descriptor/factory injection rather than reconstructing shared card styling in individual call sites.

Add one `WidgetSettingsSectionDescriptor`:

```text
section_id: "steam"
button_label: "Steam"
builder: ui.tabs.widgets_tab_steam.build_steam_ui
loader:  ui.tabs.widgets_tab_steam.load_steam_settings
saver:   ui.tabs.widgets_tab_steam.save_steam_settings
persisted_widget_keys:
    ("steam_progress", "achievement_pulse", "abandonment_issues", "friend_pulse")
```

That is one ordinary lazily built WidgetsTab section, not a second settings router. The section uses the standard collapsible widget-settings bucket pattern: **Connection & Privacy**, then one bucket for each card.

Add descriptor-owned Custom metadata for **every** Steam card:

- `WidgetCustomPositionOptionDescriptor` for each position combo;
- one Steam `WidgetCustomResizeLockDescriptor` covering all four cards;
- preview/settings-composition metadata for card-specific field toggles and authored preferred geometry;
- explicit descriptor-owned service-runtime contract metadata.

The current bare word `service_backed` is too coarse for this family. Extend the descriptor model with a small explicit service contract or equivalent metadata that can state, for example:

```text
cache_first = true
startup_freshness_policy = "shared_service_window"
defer_during_parent_transition = true
defer_result_apply_during_transition = true
preserve_visible_fallback = true
supports_manual_refresh = true
requires_valid_content_before_fade = true
```

This prevents runtime code from inferring Steam behavior through arbitrary `startswith("widgets.steam")` checks.

---

## 4. Security, privacy, secrets, and export contract

### 4.1 Credential decision

Steam credentials are **not** ordinary widget settings.

The finished connection state has two required parts:

- `SteamID64`, captured through the `Connect ID` browser/OpenID flow.
- User Web API key, captured through the `Connect API KEY` browser/key form plus explicit `Paste Key` action.

Both parts must validate together before Steam account data is considered available. One completed part is a setup-in-progress state, not a partial runtime access state.

The Steam API key and the account/profile identifier used with it live in an encrypted, per-user credential payload. The UI may retain non-sensitive card preferences in `settings_v2.json`, but it must never write the key into:

- `settings_v2.json`;
- default settings;
- generated default snapshots;
- `widgets.*` configuration;
- cache keys or cache file names;
- UI state snapshots;
- SST/settings export;
- logs, exception strings, URL debug output, screenshots, or tests;
- repository files, examples, installers, build artifacts, or resources.

Use the existing Windows DPAPI seam, but add a **strict Steam path**. The current shared DPAPI helper has an intentional non-Windows plaintext fallback for existing consumers. Steam credential storage must not silently use that fallback.

Required rule:

```text
Steam credentials may be persisted only when the payload is DPAPI-protected.
If strict encryption is unavailable or fails:
    do not write a credential file;
    keep the integration disconnected;
    show a clear settings status;
    log the failure without the secret.
```

Do not alter Gmail’s existing compatibility behavior opportunistically. Add either:

- a narrow strict helper in `core/windows/dpapi.py`, such as a `require_encryption=True` path; or
- a Steam-local wrapper that verifies Windows + a `dpapi::` result before atomic write.

The implementation must reject `plain::` for Steam credentials.

### 4.2 Credential file shape

Use the profile-aware storage path from `core/settings/storage_paths.py`, not a hard-coded path. Conceptual layout:

```text
%APPDATA%/SRPSS/
    steam/
        credentials.bin              # DPAPI blob; per profile/runtime
        credential_meta.json         # no secret; schema + safe state only, optional
        cache/
            <opaque-profile-hash>/
                catalog-v1.json
                achievements/
                friend-state.json
                progress-ledger.json
                family-state.json
                assets/
                asset-index.json
```

The MC profile uses its own canonical SRPSS_MC root through the same resolver.

Rules:

- The folder remains inside the current Windows user profile, never ProgramData.
- Do not use raw Steam ID, persona name, or API key in a path. Derive an opaque profile cache key from a one-way hash of the resolved profile identifier, with a schema/version namespace.
- Encrypt the credential payload as one compact structured value: schema version, API key, profile identifier, optional safe provider mode, creation/update timestamps.
- Atomically write encrypted files: write an encrypted temporary file in the same directory, flush if the existing storage contract supports it, then replace. Never create a plaintext staging file.
- Credential decryption is late and short-lived. Settings construction never fills a secret textbox from storage.
- The UI shows only a connection state and an intentionally non-reversible masked fingerprint, never the original key.
- “Clear Steam credentials” deletes the encrypted credential file. “Disconnect Steam” additionally clears account-bound Steam cache, friend directory, event ledger, asset index, and profile state after confirmation.
- A standard widget reset must **not** delete credentials or private Steam cache. Disconnect is the explicit destructive action.
- Existing profile cache must be discarded or isolated when the encrypted profile identifier changes.

### 4.3 Settings import/export and SST

Steam must participate in the existing shared preservation and normalization contract rather than building a private import/export exception.

Default export rule:

| Data category | Standard export / SST | Import behavior |
|---|---|---|
| Card appearance, enabled state, monitor, position, field toggles, thresholds | Include | Apply normally through widget-map normalization. |
| Custom tracked game app ID, watched app IDs, Never Show app IDs | Include only if existing export policy permits ordinary widget preferences | Validate type/range; do not trigger network. |
| Steam API key, profile identifier, token-like material, credential fingerprint | **Never include** | Ignore if present; log a safe warning that secrets were stripped. |
| Friend IDs, favourite/selected friend lists, friend directory, presence history | Exclude by default as account-private state | Preserve local state; do not overwrite from import. |
| Event ledger, selection cooldowns, achievement snapshots, artwork/avatar cache | Never include | Preserve local cache or rebuild later. |
| Credentials on reset/import | Preserve existing local encrypted state | Never replace or clear unless user explicitly disconnects. |

Add explicit redaction coverage to every export path. A simple “we did not put the key in defaults” test is insufficient: assert that a sentinel API key cannot appear anywhere in serialized settings/SST output or in diagnostic output.

### 4.4 Repository and build hygiene

Update `.gitignore` with narrow paths/patterns such as:

```gitignore
# Local Steam development credentials and local cache only
steam_credentials.local.json
steam_secrets.local.json
steam_api_key.local.txt
.env.steam
steam_cache/
tests/fixtures/steam/private/
```

Use exact names, not a broad `*.json` exclusion that could hide useful project files.

Also:

- Commit a deliberately blank `.example` file only when it contains obvious placeholders, never a working key.
- Add a test or CI grep guard that rejects known Steam secret key names in tracked fixture/config text.
- Do not bundle local credentials, cache directories, `.env` files, or sample provider payloads containing real account/friend data in Nuitka/PyInstaller scripts or installer manifests.
- Packaging tests must launch from a non-repository working directory and prove Steam paths resolve through the canonical storage resolver.
- Logs must redact query parameters and headers before formatting. Never log an entire request URL when a key might be represented in a query string.

### 4.5 Privacy and disclosure

Friend Pulse is a private-data feature even when the underlying Steam visibility is public.

The settings section should explain, in one restrained line, that it stores the selected account’s observable friend persona/status/current-game data locally to support cache-first display, cooldowns, and “newly observed” events.

Defaults:

- Friend Pulse is disabled by default until the Steam connection is configured.
- `Include Online Idle Friends` is off.
- Favourite/selected friend IDs are account-private profile state, not portable widget settings.
- A “started playing” label means **first observed by SRPSS**, never Steam’s true session-start time.
- A private or unavailable friend directory causes no active runtime card to appear when no valid cache exists. It does not create an “offline” panel.

---

## 5. Shared Steam data contract

### 5.1 Data boundary

Use a typed backend/cache boundary. The cards must receive immutable normalized records and safe result status, never raw endpoint JSON or a client object they can call in `paintEvent`.

Suggested result envelope:

```python
SteamResult[T]:
    status: SteamResultStatus
    payload: T | None
    fetched_at: datetime | None
    source: str
    authoritative: bool
    cache_age: timedelta | None
    public_message: str | None
    diagnostic_code: str | None
```

Suggested statuses:

```text
FRESH
STALE_USABLE
NO_DATA
PRIVATE_OR_UNAVAILABLE
UNAUTHENTICATED
INVALID_CREDENTIALS
RATE_LIMITED
NETWORK_ERROR
MALFORMED_RESPONSE
UNSUPPORTED_SOURCE
CANCELLED_STALE_GENERATION
```

A result is authoritative only when the provider response and normalizer prove it is safe to replace the relevant cache record. A network error, private response, truncated payload, empty malformed payload, or rate-limit response must never freshen a cache timestamp or erase valid visible content.

### 5.2 Normalized records

Keep records frozen/plain-Python and cache-serializable.

```text
SteamProfile
    profile_ref / opaque cache key
    display_name
    avatar_ref
    source visibility summary
    verified_at

OwnedGame
    appid
    canonical_title
    normalized_title
    playtime_minutes
    last_played_at
    last_played_confidence
    ownership_source
    artwork_refs

RecentGame
    appid
    title
    playtime_minutes
    observed_at

AchievementSnapshot
    appid
    total_count
    unlocked_count
    achievements
    latest_unlock
    rarity_data_status
    fetched_at

SteamNewsCandidate
    appid
    source_id
    title
    summary
    event_time
    source_url
    category
    source_confidence
    raw_fingerprint

FriendPresence
    friend_id
    persona_name
    persona_state
    current_appid
    current_game_title
    avatar_ref
    observed_at
    visibility_status
```

The provider may add source-specific raw data internally, but raw provider JSON must not flow into card paint/layout code.

### 5.3 Profile-scoped cache and semantic state

Separate **data cache** from **family policy state**.

| Category | Scope | Examples |
|---|---|---|
| Shared normalized cache | Profile-level | library index, recent games, achievement snapshot, friend snapshot, artwork references |
| Profile policy state | Profile-level | watched app IDs, dismissals, card exposure history, cooldowns, pinned app, selected friends, semantic rotation cursor |
| Card settings | Settings profile | enabled, monitor, authored position, field toggles, style, thresholds, source mode |
| Display runtime view | Per overlay instance | committed Custom rect, DPR-specific pixmap, current applied immutable view model, fade/lifecycle flags |

This avoids both bad extremes: a global mutable Steam blob that paints widgets directly, and four display/widget instances refetching the same account.

### 5.4 In-flight work and stale results

The backend must coalesce in-flight requests by a key such as:

```text
(profile_cache_key, category, appid-or-scope, requested_generation)
```

Requirements:

- A second enabled card requesting the same category attaches to the in-flight result instead of submitting duplicate work.
- Profile change, disconnect, widget teardown, and settings restart invalidate the old generation.
- A late result from an old profile/generation is dropped before cache write and before `EventSystem` publication.
- Results are applied only on the UI owner thread.
- A valid result freshens its source cache timestamp once, then is compared to the existing resolved visible model. Identical visible data means no prepared-asset invalidation or unnecessary repaint.
- Manual refresh may bypass ordinary freshness suppression but must still deduplicate with an already active fetch.

### 5.5 Refresh policy

The existing service helper already defines a cache-first startup policy and honors the global automatic-update policy. Steam must adopt that rule instead of inventing a competing startup timer.

Initial category defaults, all canonical settings/defaults rather than UI literals:

| Data category | Nominal cadence when needed | Eligibility |
|---|---:|---|
| Account/library index | 24 hours | At least one enabled Steam card needs library/title resolution. |
| Recent games | Shared Steam window: 10-minute default, 5-minute minimum | Achievement Pulse dynamic mode, Steam Journey focus pool, or Abandonment exclusion needs it. |
| Up to five candidate achievement snapshots plus selected schema | Shared Steam window: 10-minute default, 5-minute minimum | Achievement Pulse dynamic selection uses recent-play rows as a bounded candidate set; Custom needs only its literal app snapshot/schema. |
| Friend snapshot | Shared Steam window: 10-minute default, 5-minute minimum | Friend Pulse is enabled and configured. |
| Journey candidate feed | 6 hours | Steam Journey is enabled and a validated supported source exists. |
| Artwork/avatar | On demand | Referenced item is selected/visible and valid local asset is absent or stale. |

Additional policy:

- `--noupdates` disables automatic Steam retrieval. Cached content remains eligible to display. Manual refresh remains a deliberate route, following the shared service contract.
- Per-category cache reuse may suppress an unnecessary source call, but it must not raise the user-visible shared Steam freshness control above its 5-minute minimum/10-minute default contract.
- No enabled Steam card means no automatic Steam fetch.
- The first valid cache paints immediately; a fresh cache suppresses startup traffic according to the shared freshness window.
- When a parent display reports pending/running transition work, defer refresh dispatch and result application through `widgets/service_widget_runtime.py`.
- A spinner, if enabled later, is suspended during transition work through the shared helper. Do not add a bespoke Steam spinner scheduler.
- Backoff is category/profile scoped and bounded. Use retries only for transient failures; do not retry private, invalid credential, malformed, or unsupported results as though they were network outages.
- A status message shown in Settings must distinguish “cache available but refresh failed” from “no valid data exists.”

### 5.6 Event publication

Use a narrow `EventSystem` publication after a valid normalized cache commit:

```text
steam.data_updated
    profile_cache_key
    category
    appid (optional)
    generation
    changed_fields
    fetched_at
```

Cards subscribe only to categories they need. The payload carries no API key, full raw response, or mutable provider object.

Cards resolve their own display model from the updated cache. The backend does not know how an Achievement summary, Journey event strip, dusty cover treatment, or friend constellation is painted.

---

## 6. Cache, asset, and rendering discipline

### 6.1 Cache contract

Steam cache files are versioned, atomic, bounded, and disposable.

- Use a small schema version for each cache family. Invalid, unsupported, or corrupt cache files are quarantined/cleared safely and logged through `--cache`; do not crash startup.
- Cache records include `fetched_at`, source, source confidence, profile cache key, schema version, and authority status.
- No failure result updates a success timestamp.
- Use bounded ledgers: event fingerprints, dismissals, cooldowns, friend transitions, selection history, and achievement snapshots have maximum records/age.
- Delete expired artifacts and unreachable asset references on a bounded maintenance path, never during paint.
- Cache writes run off the UI path when the existing IO path is available. The UI thread only applies models and owns Qt paint objects.
- Provide Settings actions: **Refresh Steam Data**, **Refresh Steam Library**, **Clear Steam Cache**, and **Disconnect Steam**. Each action has distinct semantics and confirmation only where destructive.

### 6.2 Asset pipeline

Artwork and avatars are part of the widget experience; they must also be treated as untrusted network content.

1. Card resolves an `AssetRef`, not a URL string.
2. Backend/assets layer validates app ID/source/path policy and checks local cache index.
3. Download work uses normal timeouts, TLS verification, bounded redirects, bounded byte size, and a safe content policy.
4. Validate bytes before decode: file signature/mime sanity, dimensions, pixel count, and decompression-bomb limits.
5. Decode/resize to a `QImage` or safe byte representation away from paint.
6. On the Qt-owned apply path, prepare any needed DPR-aware `QPixmap` variant before the next paint.
7. `paintEvent` uses only already prepared assets and painter operations.
8. Write asset atomically, update index atomically, and evict through LRU/size budget.
9. A failed asset may fall back to a local neutral Steam/game placeholder; it must not turn into a repeated download loop.

Asset rules:

- Filenames derive from validated IDs and hashes, not game titles or remote URLs.
- Store dimensions, content hash, source, validation time, and last-used time in the asset index.
- Never trust remote path extensions.
- Never allow a source URL to dictate a filesystem path.
- Keep artwork/avatars out of the frozen package unless they are deliberate generic bundled placeholders.
- Do not scale source images in the paint path.

### 6.3 Stable paint model

Each card should have:

- an immutable `SteamCardViewModel`;
- a view-model fingerprint;
- an optional DPR-aware stable-content paint cache;
- a separate lightweight live layer only where necessary;
- `update()` only after a meaningful model, geometry, theme, fade, or animation state change.

Never:

- fetch a provider;
- inspect a cache directory;
- decode an image;
- create lazy pixmaps;
- mutate selection state;
- schedule refresh;
- calculate a new network candidate;
- re-run a full layout scan merely because Qt asked for a paint.

Use the shared painter-owned card/text/header shadow contract. Do not hide rendering regressions by removing art, gradients, fades, or shadows.

---

## 7. Shared visual and layout contract

### 7.1 Common visual language

All cards inherit SRPSS’s existing card controls for:

- border/background/shadow behavior;
- font family, base size, margin, opacity, monitor, and normal position;
- global shadow tuning;
- shared painter-owned card/header/text shadows;
- position/Custom routing;
- standard dark-card visual language.
- the shared header composition: customizable header styling with the bundled `images/Steam_Logo.png` mark followed by the card name, e.g. `Steam logo + Achievement Pulse`.

Steam-specific settings should be limited to actual Steam presentation choices:

- artwork treatment/variant;
- capsule fill and border RGBA colours;
- progress-ring colour;
- highlight mode;
- friend presentation mode;
- Guilt Desaturater;
- optional display fields;
- content threshold/filter choices.

Do not duplicate a large QSS block or introduce default-looking Qt controls in the runtime overlay.

### 7.2 `steam_components.py`

A small component module is useful, provided it stays a helper module rather than a new widget framework. Appropriate shared utilities:

- header/logo render constants;
- rounded artwork-well painter;
- dark gradient overlay painter;
- safe text elision/wrapping;
- age/duration formatting;
- field rail packing;
- stable `AssetRef` rendering;
- progress ring painter;
- avatar-stack painter;
- visual-model fingerprint helpers;
- state badges such as `Pinned`, `In Your Library`, `Observed locally`.

It must not own provider calls, timers, settings writes, global mutable state, or widget lifecycle.

### 7.3 Responsive optional fields

The user-facing rule stays simple:

- core content is structurally stable;
- supporting fields are individually toggleable;
- fields have a curated priority order;
- disabled fields leave no holes;
- authored cards may gain a second aligned rail for additional enabled fields;
- Custom cards uniformly scale their authored card/elements within the committed rectangle.

Implement the mechanism as an authored field-layout budget rather than a rigid “always show eight fields” promise. The budget is owned by card settings and authored presentation rules, not by a committed `Custom` rectangle.

For each card, define:

```text
Core slots:
    required visual/title/primary metric

Supporting fields:
    id
    priority
    min-width / min-height contribution
    allowed rail(s)
    authored truncate/ellipsis policy
    authored visibility rule
```

Rules:

- Authored field rules decide which enabled fields appear and whether fields 1–4 use a first rail while fields 5–8 use a second aligned rail or another compact authored presentation.
- Under narrow or short Custom geometry, the committed rectangle remains authoritative as a uniform visual scale/placement contract. The card scales the authored slots and text together; it must not ellipsize more aggressively, reduce visible-field count, hide lower-priority enabled fields, or switch content policy because the Custom rect is smaller.
- A card must not silently resize itself, alter its saved Custom rectangle, or initiate a second geometry authority because its content is verbose.
- Under non-Custom authored positions, a preferred content size may change only through the ordinary widget lifecycle/stack planner. It must participate in shared authored stacking rather than privately shoving neighbouring cards.
- Tiny impossible Custom sizes should still use the same authored content contract and scale safely inside the card, not clip painter output outside the card or remove enabled fields.
- Settings preview uses deterministic mock view models; it never needs Steam data to prove layout.

### 7.4 Custom-layout rules

For every Steam card:

- Default/authored position remains the fallback.
- `Custom` is available only after the shared Custom-layout system has a real committed payload.
- Live card geometry comes from the committed shared rectangle and must survive settings close, restart, display recreation, monitor transfer, and DPI changes.
- The card receives committed geometry and updates only internal layout/paint cache.
- Settings-side size-like controls that would conflict with the committed outer size are disabled via descriptor-owned lock metadata. Supporting-field toggles remain authored content controls; Custom may scale their presentation but must not change whether enabled content is shown.
- The regular “Disable Custom Mode” / authored-layout revert affordance must exist.
- All monitor/display bounds and cross-display transfer logic remains in the shared Custom-layout contract.
- There is no separate Steam raw-pixel geometry persistence.

---

## 8. Connection and Settings UX

### 8.1 One Steam Settings section

The Steam section is lazy-built once through the descriptor registry. Opening the general Settings dialog must not:

- construct Steam runtime overlays;
- decrypt credentials;
- contact Steam;
- index the library;
- scan Steam cache/assets;
- start a worker;
- read the friend directory;
- start a refresh timer;
- change an enabled card’s lifecycle.

First visit builds the UI controls from canonical defaults and saved non-secret settings. The top-level Steam family shell includes a family-level enable/configured toggle, then the standard Connection & Privacy bucket and card buckets. It shows a neutral “Connection not checked this session” status until the user explicitly tests, refreshes, saves a key, or opens an already-running runtime status view through an existing safe notification path.

### 8.1.1 Enabled-card connection state

This section uses “connection” as the current implementation word for the pre-auth seam. `Connect ID` uses Steam OpenID as the browser identity step; it yields SteamID64 only. `Connect API KEY` opens Steam's Web API key page and captures the user Web API key through an explicit paste action. The player-data APIs used by this family need both SteamID64 and the user Web API key. OAuth is a separate Steamworks path for specific partner APIs and is only used if Valve documents it for the exact needed scope. Users should not be forced to re-authenticate unless Steam or the user explicitly invalidates the credential.

- A disabled Steam card remains hidden.
- An enabled Steam card with valid live data or valid cache paints that content.
- An enabled Steam card with no saved Steam connection and no usable cache paints the normal card shell plus a centered prompt: `Connect With Steam To Use`. This state must not paint mock-art wells, fixture field rails, accent underlines, or other content-only placeholders.
- Only the word `Connect` is underlined/click-targeted. Activating it must open Settings directly to the Steam connection section through the shared settings/navigation seam, not through a widget-local browser helper.
- This prompt does not contradict “valid cache paints first”: cache remains authoritative when present, even if the current connection is unavailable.
- If the saved connection/token is expired or otherwise unauthorised but cache is still usable, the card keeps painting cache and may show a small orange `i` info affordance beside the header. The info affordance is optional, enabled by default, and should be general enough for future Gmail/IMAP stale-connection use.
- The info affordance must not be eager. It appears only when the displayed cache is at least `1 day` stale and the connection state needs user attention. Clicking it uses the same Settings target as the `Connect` prompt.
- The info icon is diagnostic/user-guidance UI, not a fetch trigger, retry loop, or fallback success state.

### 8.2 Connection & Privacy group

Controls:

- Steam integration status: Not configured / Not checked / Connected / Cache only / Private or unavailable / Error.
- `Connect ID` button:
  - shows a styled popup before opening the browser;
  - popup copy: `This allows the app to know who you are on Steam`;
  - popup action opens the Steam OpenID sign-in/identity flow;
  - success renders a small green check beside the button.
- `Connect API KEY` button:
  - shows a styled popup before opening the browser;
  - popup first line: `This allows the app to read Achievement/Friend/Library Data`;
  - popup second line: `Use the form to get your API Key and click the paste button here once you have it.`;
  - if Steam's form asks for a domain label, the popup should also say: `Use 'localhost' as the domain on the form`;
  - popup action opens `https://steamcommunity.com/dev/apikey`;
  - popup includes an explicit `Paste Key` action that reads the clipboard only after the user clicks it;
  - success renders a small green check beside the button.
- Small orange setup text: `Please Connect Both For Access` until both connection parts have green checks.
- Manual fallback profile identifier and API-key fields may exist behind an advanced/repair affordance, but the main user path is `Connect ID` plus `Connect API KEY`.
- **Test & Save**:
  - tests submitted credentials in background first;
  - persists them in strict DPAPI storage only after success;
  - returns UI updates to the UI thread;
  - never blocks the dialog.
- **Test Existing Connection**.
- **Refresh Steam Library**.
- **Refresh Steam Data**.
- **Clear Steam Cache**.
- **Disconnect Steam** (confirmation, deletes credentials and account-private state).
- **Show stale connection info icon** (default on).
- compact privacy note for Friend Pulse.
- no key reveal button.

### 8.2.1 Family shell contract

- `widgets.steam.enabled` is the runtime and settings-visibility master for the complete family.
- When it is off, every Steam descriptor/factory/expected-overlay/stack-preview path resolves disabled and all subordinate Settings controls are hidden.
- Individual card enablement remains persisted while the family is off; re-enabling the family restores those authored choices rather than rewriting them.
- The shell should read like the other family settings sections: bordered container, main family toggle, then Connection & Privacy plus per-card buckets.

Controls must be signal-blocked while settings load/reset/import populates them. Any dynamic panel visibility change must avoid redundant `setVisible()` churn during construction.

### 8.3 Per-card settings groups

Every card gets:

- enabled;
- monitor;
- normal position and Custom support;
- shared font/card/margin controls only where consistent with current widget conventions;
- relevant card-specific settings;
- visible-field check controls;
- manual category refresh action;
- clear unavailable-state explanation in Settings only;
- `Reset this card to defaults` routed through the canonical defaults/reset contract.

No individual Steam card should create another family master. Runtime card availability requires the family master, the card's own enabled value, monitor eligibility, and a valid cache/connect-required presentation state; credential state determines data access, not whether the family master is obeyed.

---

## 9. Card specifications

## 9.1 Steam Journey

### Product statement

Steam Journey answers:

> What changed in games I own that is material enough to be worth seeing?

It is an editorial card, not an announcement firehose.

### Verified-source gate

Do not begin final UI implementation until the discovery pass proves a supported, stable source for game news/update candidates.

The technical note must record:

- exact supported source;
- fields actually returned;
- public/private behavior;
- rate and batch constraints;
- stable identity/fingerprint;
- source URL safety;
- what counts as a trustworthy event date;
- known missing categories;
- fallback behaviour.

If the source cannot support a credible update feed, Steam Journey is deferred. Do not replace it with Store scraping, Calendar scraping, or an invented “update” label.

### Candidate pool

Default **Focus Library** candidate pool:

1. recently played owned games;
2. high-playtime owned games, capped by a canonical default;
3. watched games;
4. recent Steam Journey winners retained only long enough to avoid disappearing before display.

Rules:

- Deduplicate by `appid`.
- Hard cap the candidate pool. Start with a configurable default in the 30–50 range, then tune from actual rate/budget evidence.
- Broad Library is optional, off by default, and rotates small batches only after the source is proven.
- A card may use cached candidates; rotation alone never causes a semantic/provider fetch. A production card may hydrate only the selected app's missing allowlisted public artwork through its existing IO preparation job when automatic updates are allowed.

### Classification and scoring

Keep scoring in the Steam Journey widget/model layer, not in generic provider transport.

Suggested score inputs:

| Signal | Effect |
|---|---|
| Major content/update category proven by source | Strong positive |
| Expansion, 1.0, new chapter/region/class, major event | Strong positive |
| Meaningful DLC or significant update in a played game | Moderate positive |
| Routine patch, cosmetic post, maintenance, minor hotfix | Low or excluded by default |
| Duplicate source fingerprint or already displayed event | Exclude |
| Recent play, total playtime, watched state | Relationship boost |
| Event age | Recency boost with a cap; does not defeat major relevance |
| Dismissal / cooldown | Strong negative |
| Unknown/weak source classification | Exclude from default “Balanced” mode |

A source event must carry:

- source fingerprint;
- app ID;
- source date with confidence;
- classification;
- normalized score;
- display/dismissal state;
- cache expiry.

### Display

Default composition:

- Steam header;
- large clipped artwork;
- game title;
- strong event label;
- one-line headline;
- newness label only when source date is trustworthy.

Optional fields:

- event date/age;
- category;
- one-line summary;
- total playtime;
- reliable last played;
- watched marker;
- source/newness marker;
- queued count.

Maximum visible items: `1`, `2`, or `3`, default `1`. Multi-item mode is a restrained compact strip layout, not another Reddit-style list.

### Settings

- content scope: Focus Library / Broad Library / Watched Games Only;
- visible item count;
- significance threshold: Major Only / Balanced / Include Patches;
- allowed categories;
- watched-game editor from local library index;
- display fields;
- artwork treatment;
- capsule fill and border RGBA colours;
- manual refresh;
- optional app click action through central input/opening route.

### Acceptance conditions

- Default mode filters routine noise.
- Same source event does not recur after every cache refresh.
- Candidate scan is bounded and profiles its request count.
- Source unavailable means no invented card. Valid cached result remains usable.

---

## 9.2 Achievement Pulse

### Product statement

Achievement Pulse follows one game at a time. It makes progress legible and satisfying without pretending to know what achievement the user “should” pursue next.

### Selection contract

| Mode | Persisted authority | Resolution |
|---|---|---|
| Most Recent | mode only | Candidate with the newest known positive achievement unlock timestamp |
| Recent #2–#5 | mode + ordinal | Live ordinal in the same achievement-recency-ranked candidate snapshot |
| Custom | `appid` | Exact selected owned app, retained after it leaves recent games |

`Custom` persists an app ID, never a temporary title string or ordinal snapshot.

Steam does not expose an account-wide achievement activity feed to this client path. Dynamic modes therefore use at most the first five recent-play rows as a bounded candidate source, read/fetch their exact per-app achievement records through the existing cache/coalescing/backoff worker path, and rank candidates with positive unlock timestamps newest-first. Candidates with missing or zero timestamp evidence remain in stable recent-play order behind timestamped candidates rather than being invented as newer. After resolution, only the selected app's schema is required. This is a bounded candidate probe, not a library-wide achievement scan.

### Library autocomplete

Use the local normalized library index:

- search canonical and normalized titles;
- show title and small cached art/icon where available;
- commit `appid` and canonical title for display;
- no online store search;
- no provider request just because the dropdown or settings panel opens;
- first-time absent index shows an explicit “Refresh Steam Library” action;
- an old valid Custom app remains resolvable from cache where possible.

### Eligibility

Dynamic modes default to `Skip games with unavailable achievements = on`.

- If no eligible current recent game exists, the card keeps valid cached content where appropriate or stays hidden with no fade.
- Custom remains literal. A Custom game with unavailable achievement data shows a concise Settings status / runtime unavailable view only if it has valid title/art context; it must not silently substitute another game.
- Achievement snapshots are per literal Custom app or the five bounded dynamic candidates only. There is no library-wide achievement sweep.

### Display

The promoted card is a typographic progress summary rather than the earlier ring-and-single-tile mock. Its default composition is:

- Steam logo + `Achievement Pulse` in the shared framed header;
- game title as the strongest text outside the header;
- one to five latest unlock names, with no `Latest:` prefix and no rendered numbering;
- optional Wide, Square, or Portrait game artwork;
- `Unlocked: X/Y` centred directly below the artwork;
- supporting capsules for `Total`, `Playtime`, `Previous`, `Source`, and `Selected`.

`Previous` means the second entry in the current achievement-recency-ranked candidate snapshot. It is useful context, not a second selected game. `Source` is optional and off by default because a healthy cache-first system should not make routine cache reuse look exceptional.

Future achievement-specific extensions such as a progress ring, rarity, unlock dates, or a featured achievement tile remain optional discovery work. They are not part of the family baseline and must not displace or destabilize the promoted composition merely to match an old mock.

### Settings

- tracking mode;
- Custom local-library picker;
- skip-unavailable dynamic mode;
- artwork visibility;
- artwork shape: Wide / Square / Portrait;
- bounded Square/Portrait artwork width;
- latest-unlock visibility and count from 1 through 5;
- widget-family font and base size;
- supporting field visibility;
- default-on `Enable Double Capsules` for every visible supporting field;
- independent capsule font size;
- capsule fill RGBA and border RGBA;
- standard card background, border, text colour, position, monitor, and Custom controls;
- manual refresh.

### Achievement Pulse baseline standard for future Steam cards

Achievement Pulse is the current engineering and customization standard for this family, not a visual identity template. Future cards begin from the same authored-layout, settings, rendering, cache, and validation contracts, while a distinct default silhouette and content hierarchy are requirements rather than exceptions.

#### Authored canvas and scaling

| Mode | Base authored canvas | Rule |
|---|---:|---|
| Artwork hidden or Wide | `540 x 290` | Uses the compact card envelope. |
| Square artwork | `540 x 318` | Reserves the portrait art + `Unlocked` envelope without pushing the card into a top-to-bottom composition. |
| Portrait artwork, 140 default | `540 x 334` | Uses a 1.4 height ratio (`140 x 196`) and preserves a measured gap from `Unlocked` to the first capsule rail. |
| Portrait artwork, larger width | measured from art height + `Unlocked` + capsule block | Grows vertically only; title/latest/art anchors and capsule columns do not rearrange. |
| Additional capsule rail | measured capsule height + gap | Grows by whole authored rails; larger capsule fonts increase both capsule and authored-card height without moving upper content. |

The painter lays out in authored coordinates and then applies one uniform scale into the target rectangle. `Custom` may move and scale the completed card, but it may not alter field count, artwork shape, rail assignment, typography hierarchy, or visibility according to incidental target dimensions. Extra target space is letterboxed/centred by the standard layout rather than used as a reflow trigger.

#### Artwork contract

- Wide art is `180 x 86`, aligned to the header's top rail at authored `y = 14` and the common right rail at `x = 522`. Its artwork border uses the header's stroke weight so the visible top silhouette does not sit one pixel low at scaled sizes.
- Square art is user-adjustable from `140` through `190` authored pixels, default `140`.
- Portrait art uses the same adjustable width and Steam portrait-library source, with a fixed 1.4 authored height ratio. Portrait at `140 x 196` is the fresh-install default.
- Every Square/Portrait size keeps the same header-aligned top and right rails. The title width is derived from the selected art's left edge; Portrait grows the authored height from its actual art/metric/capsule occupancy instead of reserving a clipped or rearranged fixed box.
- `Unlocked` stays centred directly below the artwork with a six-pixel authored gap. Artwork sizing may not move it beside the image, place it over a capsule, or trigger a top-to-bottom card rearrangement.
- Artwork uses a cover crop inside the rounded well rather than a distorted stretch or an unfilled letterbox. Square and Portrait use the validated portrait-library source and reuse the same cached asset URL.
- Prepared artwork is cached by source identity, target dimensions, and DPR. A size or DPR change must not reuse a lower-resolution prepared pixmap.
- Disabling artwork releases the full title/content width without leaving an invisible artwork reservation.
- Artwork, artwork well, card frame, header, capsules, and text use painter-owned shadows. Steam cards do not add widget-level `QGraphicsDropShadowEffect` instances.

Future cards may add avatars, event thumbnails, strips, or grids, but each visual asset needs equivalent bounded rails, source-aspect policy, prepared-size/DPR caching, missing-art behavior, and collision tests.

#### Typography contract

- The family font selector and base point-size control are real runtime inputs; no Steam card hard-codes a platform-default font path around them.
- The header remains the card identity anchor. The game title is the strongest content text and is currently base size `+5` with a bold weight.
- The first latest-unlock line is base size `+2` and demibold. Unlocks 2 through 5 render beneath it at approximately half size so the first item remains the focal point.
- Unlock names never render list numbers or a redundant `Latest:` label.
- Capsule labels and values are uppercase and colon-free. Labels align left and values align right in compact mode; doubled headings and values centre independently.
- Text fitting may reduce only the affected detail/value text down to an explicit readable floor before final elision. It may not globally shrink the card or silently reduce unrelated labels.
- All high-contrast text uses the established painter-owned text shadow treatment and remains readable against transparent card backgrounds.

#### Capsule contract

Achievement Pulse uses a three-column capsule grid:

- each capsule is `159 x 26` authored pixels at the baseline capsule font and grows vertically from measured font metrics;
- columns have a nine-pixel gap;
- rails use capsule height plus a measured gap, never less than six authored pixels;
- rounding follows the shared header/card visual language rather than oversized pill geometry;
- fill and border are separate alpha-capable colour swatches;
- the capsule shadow is exterior-only, primarily bottom-right, and must not show through the translucent top-left interior.

Compact mode measures a label and value region, keeps `LABEL` left and the result right, and elides only when the value cannot fit. When `Enable Double Capsules` is on, every visible supporting field follows the same two-rail contract regardless of value length:

1. The label keeps its original capsule and column, becomes a centred heading, and remains colon-free. Previous changes to the more cohesive heading `PREVIOUSLY`; other fields retain their ordinary wording.
2. The value reserves the same column on the immediately following whole rail.
3. The detail capsule contains the full uppercase value, centred and progressively fitted to the available width.
4. Occupancy planning places up to three headings on one rail and their three matching values directly below; later fields begin another complete heading/value pair of rails.
5. If occupancy or capsule typography extends beyond the baseline envelope, the authored canvas grows by whole measured rails instead of overlapping, clipping, or rearranging upper content.

Turning the option off restores compact label/value capsules without changing field order or other layout rules. The capsule font is independent from the family base font; increasing it grows the shell/rail/card envelope, while long lower values may still fit down to the explicit readable floor before final elision.

#### Current defaults

| Preference | Achievement Pulse default |
|---|---|
| Artwork | On |
| Artwork shape | Portrait |
| Square/Portrait artwork width | `140` |
| Latest unlocks | On, `5` |
| Font | `Inter`, `15 pt` base |
| Total | On |
| Playtime | On |
| Previous | On |
| Source | Off |
| Selected mode | Off |
| Double Capsules | On |
| Capsule font | `12 pt` |
| Capsule fill | `[199, 213, 224, 38]` RGBA |
| Capsule border | `[227, 243, 255, 200]` RGBA |
| Authored preferred size | Portrait `540 x 334`; Wide/art-off uses `540 x 290`, Square uses `540 x 318` |

Defaults must remain single-source through the base mapping, Normal/MC profile overlays, `defaults.py`, generated snapshots, descriptor signal blocking, settings load/save, factory construction, and runtime widget state. A control is not complete until all of those seams and their round-trip tests agree.

#### Data, cache, and lifecycle contract

- Paint only consumes an immutable view model and already prepared assets.
- A valid cache model is applied before an online refresh is requested. Connection-status probing must not blank, disconnect, or replace valid content.
- Steam refresh cadence has a five-minute minimum and ten-minute default unless a source-specific policy is deliberately slower.
- Successful same-payload refreshes freshen the authoritative source timestamp once, but do not invalidate prepared artwork or repaint unchanged visible models. Immediate cross-display/card followers reuse the fresh source record.
- Profile data and semantic rotation are shared across displays; geometry, DPR paint caches, and the current applied view remain instance-local.
- A refresh generation, selected app ID, field visibility, artwork variant/size, DPR, colours, family/capsule font inputs, and double-capsule mode all participate in the relevant model/paint cache authority.
- Constructors, Settings preview, and `paintEvent` perform no credential access, provider request, cache scan, image decode, or source artwork scaling.
- Opening the Steam section may submit exact-path shared-IO reads for one recent-games cache record and up to five corresponding achievement records so Most Recent / Recent #2-#5 labels can include names in achievement-recency order. It may not enumerate cache directories, contact Steam, or change the persisted mode value while decorating labels.

#### Required inheritance for future Steam cards

Steam Journey and Friend Pulse must reuse or extend the production baseline established by Achievement Pulse and Abandonment Issues rather than recreating it:

- shared Steam header/logo treatment and painter-owned frame/shadows;
- family font and text-colour controls;
- artwork visibility, bounded shape/size semantics where artwork exists, cover crop, and DPR-aware prepared assets;
- alpha-capable capsule fill/border controls, compact/all-field-double modes, and measured capsule-font growth where capsules exist;
- authored-layout ownership followed by uniform `Custom` scaling;
- descriptor/defaults/settings/factory/runtime parity;
- cache-first startup, unchanged-model suppression, source-key refresh coordination, shared refresh policy, and generation safety;
- central input/secure URL routing;
- deterministic fixture view models and runtime-shaped geometry/render tests.

Card-specific data should produce a different content primitive. Friend Pulse may use avatar constellations or a bounded social grid; Steam Journey should use a chronological/event-strip language; Abandonment Issues should use a tactile archival/age treatment. Those additions still need authored bounds, measurable occupancy, explicit empty/private states, prepared assets, and the same settings/lifecycle ownership.

#### Required visual identity separation

The shared baseline is a chassis, not a template. Each promoted card must be recognizable with its title hidden:

- Achievement Pulse remains a typographic achievement ledger: dominant game title, latest-unlock hierarchy, artwork + Unlocked pairing, and compact supporting capsules.
- Steam Journey should read as forward movement through a library: chronological ribbon, route/timeline, event cards, or directional progression. Its event strip must not default to Achievement Pulse's three-column statistic grid.
- Abandonment Issues should feel archival and rediscovered: tactile cover treatment, age stamp/calendar cue, shelf/file-card structure, and a restrained warm or weathered accent. It must not read as an achievement ledger with different copy.
- Friend Pulse should feel social and live: avatars, presence relationships, constellation/orbit or bounded social-grid structure, and event emphasis. It must not reduce friends to the same title/artwork/capsule hierarchy as a game card.
- Each card owns a distinct accent palette, dominant shape, information rhythm, and at most a few meaningful motion cues. Shared Steam logo/header DNA, shadows, font controls, alpha swatches, prepared assets, and `Custom` scaling do not erase those differences.
- Reusing an Achievement Pulse component is encouraged; reusing its complete composition requires explicit evidence that the new card's data genuinely has the same hierarchy.

#### Baseline anti-patterns

Do not:

- copy the old ring/tile mock into every card as visual decoration;
- clone Achievement Pulse's full title/artwork/three-column capsule composition for cards with different semantics;
- make cache provenance a default capsule when cache reuse is normal;
- key user-visible strings from provider IDs such as `BG3_Quest12` when a localized display name is available;
- force every label/value into one capsule and accept avoidable truncation;
- let artwork size push `Unlocked` beside the image or reflow the whole card;
- derive visibility or rail count from current `Custom` dimensions;
- decode, scale, fetch, inspect credentials, or scan caches during paint;
- create card-private timers, browser launchers, settings stores, or semantic histories;
- use translucent shadows that bleed through the capsule interior;
- add a settings control without defaults, descriptor blocking, factory plumbing, runtime fingerprinting, and tests.

#### Promotion checklist for each future Steam card

- [ ] Its data fields and user-facing claims have documented source provenance.
- [ ] Private, unavailable, empty, stale, malformed, and rate-limited states are distinct and honest.
- [ ] Normal, longest realistic text, missing-art, and maximum-field fixture renders are captured and inspected.
- [ ] Every artwork/thumbnail/avatar variant has min/max bounds, source-aspect behavior, DPR preparation, and collision tests.
- [ ] If the card uses capsules, compact and all-field-double modes plus independent capsule typography are measured; truncation and authored growth are intentional and tested.
- [ ] All field combinations remain inside authored bounds with no pairwise overlap.
- [ ] `Custom` move/scale preserves authored composition and committed geometry.
- [ ] Multi-display instances share provider data but not geometry/DPR pixmaps.
- [ ] Settings opening remains lazy/provider-inert and load/reset/import signal-safe.
- [ ] Cache-first startup has no connect-required flash when valid content exists.
- [ ] Same-model refresh freshens each successful source record only once and causes no unnecessary repaint or prepared-asset churn.
- [ ] Credential, SteamID, friend/private cache, URLs with secret queries, and real account data are absent from fixtures, screenshots, logs, exports, and Git.
- [ ] Focused model, geometry, raster, descriptor, settings, lifecycle, and security tests pass before the dev gate is removed.

### Achievement-specific cache rules

- Cache selected app ID/title, source mode, normalized achievement set, latest unlock, rarity availability, and resolved highlighted tile.
- Store icons/assets through the shared Steam asset index.
- Compare unlock sets and visible model fingerprints before writing/repainting.
- A new unlock may produce one bounded local pulse state. It must not create a permanent animation loop or high-frequency repaint timer.

### Acceptance conditions

- Default is Most Recent.
- Custom selection persists by app ID.
- Custom remains selected when absent from current recents.
- Wide and every allowed Square/Portrait artwork width remain top/right aligned to the header rail.
- Square and Portrait artwork remain cover-filled; Portrait is the `140 x 196` default, and `Unlocked` stays below either compact mode without capsule overlap.
- One through five unlock names remain unnumbered and preserve the intended type hierarchy.
- Capsule labels/results remain readable, uppercase, colon-free, and oppositely aligned in compact mode.
- With Double Capsules enabled, every visible field uses a centred same-column heading/detail pair regardless of value length; Previous reads `PREVIOUSLY`. Compact mode remains available when the option is off.
- Recent selection labels may include cached game names in parentheses without changing their stable mode data or submitting provider work.
- Capsule fill/border alpha, font family/size, artwork visibility/shape/size, and field choices round-trip through Settings.
- Cache-first startup does not flash a false disconnected state or require reauthorization on every run.
- Checking a saved connection never clears a valid linked Steam ID or cached card model.
- Unavailable data never becomes a different game.

---

## 9.3 Abandonment Issues

### Product statement

Abandonment Issues deliberately re-surfaces a game that received a real start and has been untouched long enough to feel forgotten, not a one-minute accidental launch or a likely completed favourite.

The voice should feel affectionate or wry, never punitive.

### Last-played provenance gate

Smart selection is conditional on verified per-game last-played provenance. A 2026-07-12 redacted controlled-account capability probe found `GetOwnedGames.rtime_last_played` on every returned owned row and a positive timestamp on every played row. Valve's method documentation does not enumerate that response field, so the implementation validates every row rather than treating the probe as an unconditional API guarantee.

The completed discovery pass checked:

- source field;
- coverage across owned games;
- timestamp unit/timezone behavior;
- privacy/absence behavior;
- freshness;
- whether a null/missing date means unknown rather than never played.

Every normalized last-played value carries one of two explicit confidence markers:

```text
verified
unknown
```

Only `verified` values may be used for an age sentence or smart inactivity score. A successful source cache preserves that provenance across offline starts; missing, zero, non-numeric, and future values normalize to `unknown`.

If the source cannot cover a row responsibly, the card shows neither a guessed date nor a substitute game. Explicitly pinned unknown rows use the unqualified “Previous play history unavailable” state.

### Candidate selection

Default eligibility:

- owned game;
- non-empty display title;
- playtime above the canonical accidental-launch floor, initially 15 minutes;
- reliable last-played value;
- last played beyond canonical default, initially 12 weeks;
- absent from current recent-game source;
- outside card cooldown;
- not `Never Show`.

Ranking tiers, before within-tier inactivity/playtime score:

1. at least 26 weeks inactive, under 2 hours played, and 0-2 unlocked achievements in an existing cache snapshot;
2. at least 26 weeks inactive and under 2 hours played with unknown achievement count;
3. remaining 26-week candidates ordered through higher-unlock, higher-playtime, and finally all-cached-achievements-unlocked bands;
4. equivalent 12-26-week bands only after the older pool;
5. exposure cooldown and Never Show continue to control repetition/exclusion.

Higher playtime and higher unlock counts are deprioritized, not forbidden. “All cached achievements unlocked” is a ranking hint only and cannot be displayed or documented as proof that the game was completed. Probe at most 12 exact Achievement Pulse cache paths on worker IO, prioritizing current/pinned identity before the shortlist; unknown remains neutral. Do not enumerate achievement caches or trigger achievement scans.

### Rotation

- Smart rotation advances from existing qualified cache candidates only.
- Default visual rotation is 30 minutes (5-minute configurable minimum); it must not send an owned/recent/achievement request merely because the card changes. The one selected allowlisted public-art asset may fill a cache miss on the existing worker job when automatic updates are allowed; `--noupdates` forbids that automatic asset fetch.
- Semantic rotation cursor is profile-level so `monitor: ALL` does not show different games on different monitors by accident.
- Selection is not archive-index traversal. Each due interval advances a persisted profile/policy draw counter, chooses a preference tier with fixed weights independent of tier population, then chooses a game within that tier. Every tier remains reachable and the current App ID is excluded whenever an alternative exists.
- The optional `ARCHIVE N/M` shelf displays preference rank within the current candidate set. It is diagnostic context, not a sequential rotation index; runtime rotation diagnostics must include selected identity and archive rank so this distinction is testable from logs.
- Persisted `changed_at` is cadence authority across widget/settings/display rebuilds. Recreated widgets rotate immediately when overdue or arm one shortened first interval for only the remaining duration, then return to the single configured recurring interval.
- Explicit widget refresh forces one non-repeating cache-backed semantic draw after refreshing eligible sources and restarts the full configured cadence. Seeing owned/recent cache writes is not itself evidence that the selected game changed.
- If the low-frequency expiry lands during a parent image transition, it remains pending and retries once per second through the shared transition-deferral/`ThreadManager.single_shot` path. The interval is not discarded and no second recurring timer is created.
- A ranking-policy setting/version change reselects once immediately; ordinary cache reloads retain the current game and cooldowns prevent preference evidence from snapping back to a recently shown title.
- Pinning disables smart selection for that card, but does not mutate the shared library index.

### Display

Implemented default composition:

- Steam header;
- large artwork;
- title;
- reliable last-played age;
- optional stable rediscovery message;
- warm archive tab and double-line `LAST VISIT` stamp;
- bottom ledger rows rather than Achievement Pulse capsules;
- default-on `PLAYED`, `ACHIEVEMENTS`, `LAST UNLOCK`, `LAST PLAYED`, and `ARCHIVE CLASS` shelves.

At the default 140-pixel Portrait artwork width, that five-shelf composition is authored at `560 x 331`; legacy `420 x 180` / `560 x 300` default-sized cards migrate to the current measured envelope, while genuinely custom geometry continues to scale the composition uniformly.

Rediscovery-message contract:

- default on, with a dedicated Content toggle that removes the line without hiding functional unavailable/connect messaging;
- deterministic from stable game identity so repaints, settings rebuilds, and `monitor: ALL` cannot change the wording for the same game;
- exact 100-bucket weighting: `Long Forgotten` owns 60 buckets, while each of ten authored title-case alternatives owns four buckets;
- copy selection is pure model work and adds no timer, repaint loop, provider work, or UI-thread cadence pressure;
- long alternatives fit the existing authored subtitle rail by shrinking within the established font floor rather than moving artwork, title, age stamp, or ledger rows.

Optional fields:

- total playtime;
- achievement count as `unlocked / total`, only from a successful cached per-app snapshot;
- latest unlock age, or `NO UNLOCKS` only when that same snapshot proves zero unlocks;
- exact `DD/MM/YYYY` UTC last-played date, only from the selected row's verified positive non-future `rtime_last_played`;
- derived engagement-depth archive class (`BARELY STARTED`, `SHORT START`, or `DEEP ARCHIVE`) without completion semantics;
- queue position, cache source label, and selection/pinned mode as default-off diagnostics.

The first five fields above form the default user ledger. Unknown/private achievement evidence removes only the affected achievement shelf, and unknown last-played provenance removes the exact-date shelf. Enabled shelves are not capped at four: the authored two-column ledger grows by complete rows, preserving the existing art/title/stamp scale and adding no provider request, timer, image work, or paint-time data derivation.

### Guilt Desaturater

`Guilt Desaturater` is retained with this strict contract:

- default off;
- affects artwork saturation only;
- based only on a reliable inactivity value;
- smooth capped curve;
- no percentage, guilt counter, punishment score, or hidden shame label;
- full colour when off;
- art transform prepared outside paint where feasible, with cache keyed by asset/version/desaturation bucket; never resample the original artwork every frame.

### Settings

- selection mode: Smart Rotation / Pinned Game;
- accidental-launch floor in minutes;
- preferred playtime ceiling;
- preferred maximum cached unlock count;
- minimum and preferred inactivity thresholds;
- rotation interval;
- Guilt Desaturater;
- Never Show editor;
- local-library pin picker;
- artwork visibility, portrait/wide shape, bounded portrait size, and alpha-capable warm accent;
- display fields;
- explicit manual Steam-library refresh.

### Acceptance conditions

- Sessions below 15 minutes fail default eligibility; 15-119-minute starts are preferred rather than excluded.
- Six-month-old candidates outrank 12-26-week candidates when available; Steam purchase date is not inferred.
- Cached 0-2-unlock evidence may improve rank and all-unlocked evidence may demote, but unknown stays neutral and no achievement request/sweep is added.
- No age appears without reliable source provenance.
- Missing source/data does not turn into a false date.
- Guilt Desaturater is off by default and changes only artwork saturation.
- Owned-library automatic refresh is capped at once per 24 hours; recent-game freshness follows the shared 10-minute default/5-minute minimum. Explicit manual refresh may bypass both without bypassing in-flight coordination/backoff.
- Live game/title/art changes fade out, commit together while hidden, and fade in through the shared `AnimationManager`; the stable header/chrome does not move and no private high-frequency timer or graphics effect is introduced.

---

## 9.4 Friend Pulse

### Product statement

Friend Pulse gives a small sense of activity without becoming a surveillance-heavy status list.

Default focus:

- friend currently playing;
- friend newly observed beginning/changing a game;
- friend playing something in the user’s owned library;
- optionally a selected favourite returning online or to a game.

### Privacy and source contract

The backend must represent these branches independently:

- friend list unavailable/private;
- player summary unavailable;
- friend visible but no current game;
- game artwork absent;
- initial run with no prior valid snapshot;
- partial/truncated friend response;
- cached friend state older than its permissible display age.

None of these mean “offline.”

### Event ledger

On an authoritative friend snapshot:

1. normalize visible identities/status/game state;
2. compare against the prior valid snapshot for the same profile;
3. produce local events only for meaningful observed changes;
4. apply per-friend/per-game cooldown;
5. retain bounded event expiry/history.

Example wording:

```text
Mira started playing Hades II
Alex is playing Baldur’s Gate 3
Jon returned to a game in your library
Three friends are playing now
```

Use `observed` language where a time is shown:

```text
Observed 12 minutes ago
```

Do not call it “started 12 minutes ago” unless the provider genuinely supplies a trustworthy session-start time and that capability has been separately proven.

### Presentation modes

| Mode | Default? | Behaviour |
|---|---|---|
| Single Rotating | Yes | One friend/game hero card. Rotation is cache-only and slow; default target is 15 minutes. |
| Adaptive Grid | No | Internal grid of active friend avatars/game context, packed inside the authored card layout. It has a hard authored visible cap; Custom scales the presentation without changing that cap. |
| List | No | Compact rows with avatar, friend, and game. Reuses card field/ellipsis rules, not a new generic list-widget policy. |

Offline avatars are desaturated only in an explicit mode/filter that admits offline/idle context. Default Single Rotating does not show an offline directory.

### Display

Default Single Rotating composition:

- Steam header;
- wide clipped game artwork;
- overlapping circular avatar;
- friend name;
- short game status;
- `In Your Library` marker only after known app-ID overlap;
- optional secondary active-avatar stack.

Optional fields:

- avatar;
- friend name;
- game title;
- shared-library marker;
- observed age;
- count of other active friends;
- persona/status;
- secondary avatar stack;
- event type.

### Settings

- scope: All Friends / Favourites / Selected Friends;
- content filter: Currently Playing / New Game Pulse / Shared-Library Priority;
- presentation mode: Single Rotating / Adaptive Grid / List;
- visible friend cap;
- rotation interval;
- per-friend/per-game cooldown;
- `Include Online Idle Friends` default off;
- favourites/selected editor populated only from cached friend directory;
- artwork treatment;
- fields;
- manual refresh.

### Friend-specific cache rules

Persist:

- normalized friend directory only as profile-private cache;
- avatar references;
- prior observed game/status;
- bounded local event ledger and expiry;
- favourite/selected IDs;
- cooldowns;
- last valid refresh, source visibility state, and safe error class.

The standard export excludes this data.

### Acceptance conditions

- Uses avatar plus game art for genuine game-state cards.
- Does not convert private/unavailable into an offline roster.
- “Started playing” remains a local observed transition unless proven otherwise.
- Grid/list obey committed Custom geometry.
- A single friend cannot dominate forever because cooldown/rotation is tested.

---

## 10. Discovery gate and data proof matrix

Before production widget code, create a short checked-in technical note:

```text
Docs/Steam_Data_Feasibility.md
```

It records evidence from controlled, non-secret test runs and becomes the authority for what data is actually shipped.

### 10.1 Required discovery tasks

- [x] Confirm the intended Steam identity + user-key credential configuration without copying Gmail OAuth code or publisher-key assumptions.
- [x] Verify strict DPAPI storage and failure behavior.
- [ ] Capture sanitized, local fixture payloads for:
  - [x] owned library;
  - [x] recent games;
  - [x] achievement-rich selected game;
  - [ ] global rarity response, if available;
  - [ ] friend list and batched player/current-game state;
  - [ ] proposed Progress/news source.
- [ ] Verify privacy and no-data branches for every source.
- [x] Prove last-played source coverage before Abandonment Issues is enabled.
- [x] Verify production-card artwork sources, dimensions, cache semantics, and malformed-image protections; friend avatars remain Phase 8 work.
- [ ] Measure request batch limits, practical latency, and rate-limit behavior.
- [ ] Validate cache-first startup from a real frozen or script launch without repository cwd dependence.
- [x] Confirm that data fields are labelled `confirmed`, `conditional`, `unavailable`, or `excluded`.

### 10.2 Proof matrix template

| Capability | Source proven? | Fields proven | Privacy/empty behavior | Cache TTL | Feature decision |
|---|---|---|---|---:|---|
| Owned library | Conditional; controlled-account probe complete | `appid`, title, playtime, `rtime_last_played` with per-row provenance | Private/unavailable stays unavailable | 24 h | Production foundation |
| Recent games | Conditional; fixture/live path complete | ordered recent app IDs, playtime | Empty/private stays literal | Shared 10-minute default, 5-minute minimum | Production Achievement selection and Abandonment exclusion |
| Per-app achievements | Conditional; fixture/live path complete | counts, schema names/icons, unlocks, dates | Per-app empty/unavailable stays literal | Shared 10-minute default, 5-minute minimum | Production Achievement Pulse |
| Global rarity | Not promoted | none required by current card | Absence is not zero rarity | n/a | Optional future field only |
| Friends | Conditional endpoint only | identity/status/current game | Private response must not become offline | Pending | Required for Friend Pulse |
| Per-game last played | Conditional; controlled-account probe complete | positive non-future Unix timestamp + verified/unknown confidence | Missing/zero/malformed/future is unknown | Owned-library 24 h | Production smart Abandonment |
| News/update events | Transport/schema proven; classifier pending | stable item id, date, title/body, feed/tags/url | Public app-specific only, not personalized | Pending bounded policy | Steam Journey implementation gate |
| Artwork/avatar | Production game/achievement art proven; friend avatars pending | validated allowlisted HTTPS assets, signatures, local prepared variants | Missing/invalid removes art only | on demand | Shared visual asset path |

Nothing in the product documentation should move from “conditional” to “available” without this evidence.

---

## 11. Implementation sequence

Each phase ends with a gate. Do not begin a later user-facing card merely because its mock UI looks good.

## Phase 0A — Local architecture gate and diagnostics

- [x] Read current `Spec.md`, `Index.md`, `Current_Plan.md`, `Docs/Guardrails.md`, `Docs/TestSuite.md`, `Docs/Harness_Index.md`, and descriptor/service-widget contracts before edits.
- [x] Keep this Steam plan aligned with the current descriptor/settings/service-widget architecture.
- [x] Implement a central named `--devsteam` visibility gate, initially for the full family and now retained only for the unfinished Steam Journey and Friend Pulse prototypes after Achievement Pulse and Abandonment Issues promotion.
- [x] Extend descriptor activation with a central named dev-gate seam so Steam does not use environment-variable activation.
- [x] Implement `--steam` as the Steam sidecar diagnostics flag, routed to `screensaver_steam.log`.
- [x] Ensure `--devsteam` and `--steam` are ignored by screensaver mode parsing.
- [x] Add bars proving Steam sidecar routing, central named-gate behavior, and parser filtering.

**Gate:** Complete and narrowed after promotion. Steam Settings, Achievement Pulse, and Abandonment Issues are public; no unfinished Steam Journey or Friend Pulse descriptor, settings bucket, factory, or runtime card appears without `--devsteam`.

## Phase 0B — Source discovery and evidence gate

- [x] Add `Docs/Steam_Data_Feasibility.md`.
- [x] Confirm no existing Steam integration in source and document any discovered collision.
- [x] Decide exact supported provider endpoints/source contracts through official-source evidence and fixture-safe code metadata.
- [x] Produce synthetic, sanitized fixtures before real UI coding.
- [x] Decide source confidence/no-data matrix.
- [x] Prove `GetOwnedGames.rtime_last_played` coverage in a redacted controlled-account capability probe and retain strict per-row unknown handling.
- [x] Prove Steam Journey's bounded public app-news transport/schema viability while keeping editorial classification and whole-library request policy gated.

**Gate:** Foundation source contract is explicit. Achievement Pulse and Abandonment Issues have source-proven production paths. Steam Journey has a proven transport/schema but remains gated on classifier/noise/request-budget evidence; Friend Pulse remains gated on privacy fixtures and policy.

## Phase 1 — Security and storage foundation

- [x] Add `core/steam/credentials.py`.
- [x] Add strict encrypted-storage path using DPAPI with no plaintext fallback.
- [x] Use canonical user profile storage path.
- [x] Add atomic encrypted credential write/read/delete.
- [x] Add key/profile redaction helpers.
- [x] Add cache profile key derivation without exposing Steam ID.
- [x] Add `.gitignore` entries and secret-leak tests.
- [x] Define settings/SST redaction and preserve-on-import behavior.
- [x] Add disconnect/cache-clear semantics.
- [x] Add UI-safe credential test/save state machine.

**Gate:** A sentinel key cannot be found in settings, defaults, snapshots, cache names, exports, logs, fixtures, or packaged resources. Strict encryption failure leaves no credential file.

## Phase 2 — Typed backend, cache, and assets

- [x] Add normalized frozen models/result statuses.
- [x] Add backend transport with timeouts, TLS verification, response size limits, redaction, and safe error classification.
- [x] Add profile/category/app-id keyed in-flight coalescing.
- [x] Add generation cancellation/drop rules.
- [x] Add versioned, atomic shared cache.
- [x] Add bounded backoff and authoritative-cache update rules beyond the current "failed result cannot freshen cache" foundation.
- [x] Add profile-level policy state store for rotation/cooldowns/dismissals.
- [x] Add safe asset fetch/validation/index/eviction path.
- [x] Publish narrow `EventSystem` data updates.
- [x] Add mock backend injection for all card tests.

**Gate:** Complete. Backend can run from fixtures without Qt widgets, cache-first behavior is deterministic, stale-generation results are dropped, active backoff is explicit, and no invalid/error response overwrites valid cache.

## Phase 3 — Descriptor, factory, defaults, and Steam Settings skeleton

- [x] Add four factory descriptors.
- [x] Add explicit descriptor-owned Steam service-runtime contract metadata.
- [x] Add one lazy Steam Settings section descriptor.
- [x] Add four Custom-position descriptors and Steam Custom lock metadata.
- [x] Add canonical defaults for all four cards and shared Steam preferences.
- [x] Update defaults normalization, snapshots, and import/reset coverage.
- [x] Wire factories through the standard registry/setup route.
- [x] Add lazy `widgets_tab_steam.py` shell with Connection & Privacy group and all card groups.
- [x] Block all signals during load/reset/import through descriptor-owned signal-block attrs.
- [x] Confirm no network/decryption/cache scan during general Settings opening.
- [x] Confirm no hidden second setup branch exists in `widget_setup_all.py`.

**Gate:** Complete. Four disabled mock cards can be created/reused/removed through normal descriptors, can enter Custom mode independently, and settings save/load works without provider access.

## Phase 4 — Shared mock visual system

- [x] Add `widgets/steam_components.py`.
- [x] Implement painter-owned header/artwell/gradient/ring/avatar helpers.
- [x] Define immutable card view models and fingerprints.
- [x] Build deterministic mock-data render harness for:
  - [x] normal content;
  - [x] long title/headline;
  - [x] missing artwork / placeholder-art rendering;
  - [x] unavailable/private status;
  - [x] first/second optional field rail;
  - [x] tight Custom geometry with unchanged authored visible-field count;
  - [x] DPR variants.
- [x] Integrate stable paint fingerprint rules for future paint-cache ownership.
- [x] Add visual/pixmap safety tests.
- [x] Prove no provider/asset work occurs in constructors, `paintEvent`, or Settings preview.
- [x] Promote Achievement Pulse's header, typography, artwork rails, capsules, alpha swatches, and authored scaling as the current family engineering baseline while requiring distinct future-card identities.
- [x] Add bounded header-aligned Square and default 1.4-ratio Portrait artwork sizing (`140-190` width, default Portrait `140 x 196`) with cover crop, prepared-size/DPR cache keys, measured authored-card growth, matched header/artwork stroke, and fixed-below-art `Unlocked` geometry.
- [x] Add compact versus default-on all-field double capsules, whole-row occupancy, and independent capsule-font-driven rail/card growth without field-specific geometry exceptions.

**Gate:** All four cards render from fixture view models with normal, narrow, and Custom geometry without clipping outside their card or changing committed rectangle.

## Phase 5 — Achievement Pulse cache/fixture slice

- [x] Implement Most Recent and Recent #2–#5 from the newest positive achievement unlock across at most five recent-play candidates, with stable recent-play fallback for missing evidence, plus literal Custom app-ID selection.
- [x] Implement selected-app achievement progress view-model mapping.
- [x] Preserve private/unavailable/no-achievement as literal card states with no substitute game.
- [x] Add shared Steam logo + card-name header composition.
- [x] Add enabled-card no-connection/no-cache prompt and stale-cache info affordance.
- [x] Add cache-first fixture bars before live provider hookup.

**Gate:** A Custom game persists by app ID in the pure resolver; dynamic selection remains safe when a recent game lacks achievements; card state can render cache/fixture, connect-required, and stale-connection affordance paths without provider/cache/credential work in constructors or paint.

## Phase 5.5 — Steam family shell and connection prelude

- [x] Add the bordered family shell and true family master around the Steam settings buckets.
- [x] Keep the Connection & Privacy bucket as the first inner bucket and keep the user-facing connection affordance explicit before live data work.
- [x] Gate factory creation, expected-overlay truth, stack preview/status, and subordinate Settings visibility from the family master while preserving individual card choices.

**Gate:** Steam settings read like a single family section, the connection seam is explicit before live data work begins, and master-off is authoritative across settings/runtime/preview seams.

## Phase 5.6 — Steam identity, user-key, and connection flow

- [x] Implement `Connect ID` as the browser/OpenID identity-linking path so the app can capture SteamID64 without password handling.
- [x] Implement `Connect API KEY` as the user-key path: styled popup, browser open to `https://steamcommunity.com/dev/apikey`, `localhost` domain guidance, explicit user-clicked `Paste Key`, redacted validation, and no silent clipboard reads.
- [x] Render per-button green checks and the small orange `Please Connect Both For Access` state until SteamID64 and user Web API key validate together.
- [x] Store the user Web API key encrypted and never in repo/defaults/logs; store only safe non-secret connection status/fingerprints in normal settings/UI state.
- [x] Keep OAuth as an explicit future option only if Valve documents the exact required scope for a later Steamworks endpoint.
- [x] Add the settings-side auth controls and status states needed for connecting, disconnecting, and reusing a persisted credential without exposing the secret.
- [x] Preserve the centered connect-required card state while making the new auth state explicit and testable.
- [x] Keep auth work off paint and constructors, and keep it on the shared thread/service ownership seams.
- [x] Keep connection readiness separate from the family master: credentials govern data access while the master governs family participation.

**Gate:** Steam has an explicit user-facing identity + credential flow that can be tested before live data hookup.

## Phase 6 — Achievement Pulse real data hookup

- [x] Connect the pure resolver to versioned Steam cache records.
- [x] Implement bounded up-to-five candidate achievement cache refresh through shared service-widget/ThreadManager scheduling only, followed by selected-app-only schema refresh.
- [ ] Implement local library index/autocomplete if the Custom app-ID control proves too brittle for users.
- [ ] Re-evaluate painter-drawn ring, rarity, date, and tile-highlight extensions only after the promoted typographic card has real-runtime evidence; they are not baseline requirements.
- [x] Implement card fields/settings/manual refresh without cache churn for unchanged visible models.
- [x] Implement one-to-five latest unlocks, artwork visibility plus Wide/Square/default Portrait shape and bounded compact width, family typography, supporting field choices, alpha capsule swatches, compact/default-on-all-field double capsules, and independent capsule typography.
- [x] Decorate Most Recent / Recent #2-#5 Settings choices with achievement-recency-ordered names from one recent record plus at most five exact cached achievement records on bounded cache-only IO.
- [x] Implement cache-first/fade/transition deferral integration.
- [ ] Add real-account manual validation after fixture coverage.

**Gate:** Achievement Pulse can paint real cache first, refresh without private timers or UI pressure, and preserve unavailable/private states without blank flashes or substitute games.

## Phase 7 — Abandonment Issues, after timestamp proof

- [x] Implement last-played confidence/provenance handling.
- [x] Implement candidate eligibility/score/cooldowns/pin/Never Show.
- [x] Prefer old short starts with bounded cache-only achievement evidence and policy-aware reranking without completion claims.
- [x] Implement cache-only rotation shared by profile rather than display.
- [x] Replace archive-order traversal with profile-seeded preference-biased random draws, persisted draw counters, immediate-repeat exclusion, and due-boundary tolerance.
- [x] Preserve a rotation expiry that collides with a parent transition through the shared deferred single-shot path rather than dropping it or adding a recurring timer.
- [x] Preserve rotation age across widget/settings/display rebuilds by arming only the remaining first interval or rotating immediately when overdue.
- [x] Make explicit widget refresh force one non-repeating cache-backed draw and restart the configured cadence after source refresh.
- [x] Fill a selected game's missing allowlisted public artwork on the existing rotation IO job when automatic updates are allowed, while preserving strict artwork-cache-only behavior under `--noupdates`.
- [x] Implement Guilt Desaturater via bucketed worker-prepared art assets.
- [x] Implement settings, cache-only library picker, display fields, deterministic 60/40 optional rediscovery copy, and distinct archival visual composition.
- [x] Add evidence-gated achievement count/latest unlock/exact last-played/archive-class shelves, default the user-facing set on, and grow the authored ledger for every enabled field without provider or UI-thread work.
- [x] Validate unavailable/invalid/future timestamp branches remain honest.
- [x] Add sparse manager-owned fade-out/commit/fade-in for live game/title/art changes, with stable header/chrome and no private timer or effect.
- [ ] Complete compiled multi-display, frozen-build, long-idle, transition, `--noupdates`, and Custom-geometry runtime validation.

**Gate:** Automated implementation gate complete and card promoted disabled-by-default. Smart Abandonment cannot display an inferred date and resolves an honest unavailable state if reliable timestamp rows are absent. Remaining compiled/manual bars are release validation, not permission to weaken provenance.

## Phase 8 — Friend Pulse

- [ ] Implement profile-private friend snapshots and delta ledger.
- [ ] Implement first-snapshot/no-history policy.
- [ ] Implement private/unavailable/partial response handling.
- [ ] Implement Single Rotating first.
- [ ] Add Adaptive Grid and List only after Single Rotating geometry/perf is solid.
- [ ] Implement favourites/selected scope and account-private state.
- [ ] Implement shared-library marker from known app-ID intersection.
- [ ] Add disclosure/settings/status and cache clear/disconnect checks.
- [ ] Validate real privacy settings and partial data manually.

**Gate:** private/unavailable does not masquerade as offline; first observation is labelled accurately; grid/list have a hard cap and obey Custom.

## Phase 9 — Steam Journey, only after event source proof

- [x] Prove the public app-news transport/schema and stable event identity/date/url/feed fields with a bounded redacted capability probe.
- [ ] Implement source adapter and source-provenance/fingerprint model.
- [ ] Implement Focus Library candidate pool.
- [ ] Implement source classification/filter/scoring/history/dismissal.
- [ ] Implement one-item card first.
- [ ] Add multi-item strips only after visual/perf proof.
- [ ] Implement Broad Library round-robin as optional, bounded coverage.
- [ ] Add watched-game editor/manual refresh and click route.
- [ ] Validate source failure and stale cache state.

**Gate:** default card only presents source-proven meaningful events and cannot become a noisy patch ticker.

## Phase 10 — Full integration, docs, packaging, and release bar

- [ ] Run full suite.
- [ ] Run focused Steam tests.
- [ ] Run descriptor/custom-layout/service-runtime/settings regression families.
- [ ] Run frozen `.scr` and MC smoke tests.
- [ ] Verify non-repository cwd / packaged asset resolution.
- [ ] Verify DPAPI storage, disconnect, import/export redaction, and cache purge manually.
- [ ] Run multi-monitor Custom/edit-mode/stacking passes.
- [ ] Run the Achievement Pulse and Abandonment Issues long idle/perf pass with `--steam --perf --cache --set --geo --life`; add `--devsteam` only for a separate Steam Journey/Friend Pulse prototype pass.
- [ ] Update `Spec.md`, `Index.md`, `Docs/TestSuite.md`, `Docs/Contracts.md`, and this plan only where the implemented contract differs from the proposal.
- [ ] Add a concise Current Plan entry only when work is actually selected; do not turn Current Plan into a historical changelog.

**Gate:** Full manual validation and diagnostic evidence support the visual/timing-sensitive paths. Tests are necessary but not sufficient.

---

## 12. Suggested automated test plan

### 12.1 Security and persistence

`tests/test_steam_credentials.py`

- [ ] strict DPAPI path writes `dpapi::` only on Windows;
- [ ] plaintext fallback is rejected for Steam credentials;
- [ ] encryption/decryption errors leave no partial credential file;
- [ ] atomic replace behavior;
- [ ] clear/disconnect removes credentials and account-private state;
- [ ] secret is absent from normal settings, defaults, default snapshots, exports, SST, logs, cache path, and error formatting;
- [ ] imports preserve local credentials and reject injected credential fields;
- [ ] account change isolates old profile cache;
- [ ] Settings UI never repopulates API-key textbox with stored value.

### 12.2 Backend, cache, and source policy

`tests/test_steam_backend.py`, `tests/test_steam_cache.py`

- [ ] normalized result-status branches;
- [ ] malformed/partial payload rejection;
- [ ] provider response size/timeouts/redirect policy;
- [ ] in-flight coalescing;
- [ ] stale-generation late result rejection;
- [ ] no error/empty response freshens success timestamp;
- [ ] cache version migration/corrupt cache recovery;
- [ ] bounded ledger eviction;
- [ ] retry/backoff policy;
- [ ] `--noupdates` startup suppression;
- [ ] manual refresh bypasses freshness but not in-flight dedupe;
- [ ] cache-first startup decision uses the shared service runtime contract.

### 12.3 Asset safety

`tests/test_steam_assets.py`

- [ ] cache path cannot escape asset root;
- [ ] invalid remote reference rejected;
- [ ] byte/pixel/dimension limits;
- [ ] malformed image leaves placeholder state;
- [ ] no repeated failed download loop;
- [ ] atomic asset write and index update;
- [ ] DPR prepared asset selection;
- [ ] eviction respects active references;
- [ ] no image decode/pixmap creation on paint path.

### 12.4 Descriptor, settings, lifecycle, and Custom

Extend or add coverage alongside:

- `tests/test_widget_descriptors.py`;
- `tests/test_widget_manager_refresh.py`;
- `tests/test_widgets_tab.py`;
- `tests/test_custom_layout_contract.py`;
- `tests/test_custom_layout_manager.py`;
- `tests/test_widget_visual_padding.py`;
- `tests/test_service_widget_runtime.py`.

Required bars:

- [ ] four factory descriptors, one Steam Settings section, correct persisted keys;
- [ ] descriptor-owned service-runtime metadata is explicit;
- [ ] no handwritten Steam setup route bypasses descriptor/factory setup;
- [ ] lazy Settings build does not submit provider/cache/auth work;
- [ ] load/reset/import signal blocking covers every Steam control;
- [ ] card field save/load retains unvisited lazy Steam section values;
- [ ] each card enables/disables independently;
- [ ] each card accepts normal position and independent Custom geometry;
- [ ] no Custom card modifies its committed outer rectangle after data/title/field change;
- [ ] non-Custom size/content change enters shared authored stacking path;
- [ ] cached valid content fades while no-valid-content state does not;
- [ ] result application/refresh dispatch defers under parent transition;
- [ ] visible fallback survives empty/error/private/non-authoritative response;
- [ ] no-op visible result produces no cache write/repaint;
- [ ] cleanup stops resources through normal ownership paths.

### 12.5 Product logic

`tests/test_steam_achievement_pulse.py`, `tests/test_steam_phase3_settings_descriptors.py`, `tests/test_steam_phase4_mock_visuals.py`

- [x] Most Recent / Recent #2–#5 rank up to five recent-play candidates by newest positive unlock timestamp, with stable fallback for missing evidence; Custom remains literal;
- [x] Custom persisted app ID survives recents changes;
- [x] unavailable dynamic entries do not cause unsafe substitution;
- [x] literal Custom unavailable state;
- [x] schema display names replace internal achievement IDs;
- [x] one-to-five newest unlock ordering and unprefixed presentation;
- [x] Previous and cached Settings labels derive from the same achievement-recency-ranked candidate order;
- [x] unchanged successful payload freshens source timestamps while retaining the visible fingerprint and suppressing repaint;
- [x] unauthorized refresh preserves valid cache and marks connection attention;
- [x] Settings/defaults/factory/runtime parity for artwork, font, fields, capsule alpha, and double-capsule controls;
- [x] bounded Square/default Portrait artwork and fixed-below-art `Unlocked` geometry at minimum/default/maximum width, including portrait-driven authored-card growth;
- [x] compact mode and default-on all-field double mode use collision-free whole rows, with `PREVIOUSLY`, independent capsule font sizing, and measured authored-card growth;
- [ ] local index autocomplete never calls network, if autocomplete is promoted beyond direct Custom app ID;
- [ ] any future ring/rarity/date/tile mode has its own deterministic model, settings, geometry, and render bars before implementation.

`tests/test_steam_abandonment_issues.py`

- [x] missing/zero/future timestamp exclusion;
- [x] verified timestamp eligibility;
- [x] 15-minute eligibility plus 2-hour/2-unlock/26-week ranking tiers and likely-complete demotion;
- [x] cooldown/pin/Never Show and profile-shared selection;
- [x] cache-only profile-shared weighted-random semantic rotation with persisted draw count, non-sequential archive-position coverage, immediate-repeat exclusion, due-boundary tolerance, selected-art worker hydration, and transition-collision deferral;
- [x] rebuilds preserve remaining rotation cadence and widget-level manual refresh forces one non-repeating cache-backed draw;
- [x] Guilt Desaturater bucket/clamp and worker-prepared asset behavior;
- [x] owned/recent refresh preservation and shared-source reuse with Achievement Pulse;
- [x] authored large-art layout, deterministic render, cache-before-first-fade, and sparse transition updates;
- [x] no achievement sweep side effect.

`tests/test_friend_pulse_widget.py`

- [ ] initial snapshot creates no false “started playing” event;
- [ ] observed change event generation;
- [ ] per friend/game cooldown;
- [ ] privacy/unavailable/partial state is not offline;
- [ ] shared library marker only from known app-ID intersection;
- [ ] Single/Grid/List authored caps survive Custom scaling;
- [ ] private selection/favourites excluded from export.

`tests/test_steam_progress_widget.py`

- [ ] source fingerprint dedupe;
- [ ] event classification/scoring deterministic against fixed clock;
- [ ] default noise filters;
- [ ] dismissal/cooldown;
- [ ] Focus Library cap;
- [ ] Broad Library bounded round-robin;
- [ ] unsupported source hides/defer card instead of substituting scraping.

### 12.6 Mock render / visual bars

Use fixture view models and offscreen rendering at:

```text
DPR: 1.0, 1.25, 1.5, 2.0
Geometry: authored default, wide, narrow, short Custom, tall Custom
Content: long localized title, missing art, error/cache state, maximum fields
```

Assert:

- no overflow outside rounded card;
- no blank flash from valid cache;
- no hidden text rail overlap;
- Wide and Square art remain clipped to a rounded cover-filled well without stretching;
- Square size clamps to safe bounds and keeps the shared header/right rails;
- `Unlocked` remains directly below Square art with authored padding and no capsule intersection;
- compact capsule labels/results remain colon-free, left/right aligned, and un-clipped at supported defaults;
- all-field double capsules centre their upper headings and lower values, remain same-column, use whole measured rails, grow with capsule font size, and fit the full value before final elision;
- capsule fill/border alpha does not expose shadow through the translucent top-left interior;
- one-to-five unlock names remain unnumbered, unprefixed, and vertically separated;
- friend avatar overlap remains within card;
- Custom scaling does not change enabled-field count or authored caps;
- no geometry mutation on dynamic content.

### 12.7 Manual runtime matrix

| Scenario | Expected result |
|---|---|
| Enabled card, no connection and no usable cache | Card shell remains visible with centered `Connect With Steam To Use`; no mock-art/content placeholders appear; only `Connect` is underlined/clickable and routes through the shared Settings request path toward Steam connection settings. |
| Valid credential, empty cache | Cache initializes after ordinary background request; no UI freeze. |
| Valid cached data, network offline | Cached card remains visible; no timestamp is falsely freshened. |
| Expired/unauthorized connection with cache at least 1 day stale | Cached card remains visible; optional default-on orange info affordance appears beside the header and routes through the same Settings request path. |
| Private friend/library data | No “offline everyone” interpretation; Settings shows safe availability state. |
| Invalid API key | Cache preserved; safe error, no secret logging. |
| `--noupdates` | No automatic provider or public-art requests; cache can still display; manual refresh follows deliberate route. |
| Parent image transition during refresh | Fetch/result apply/spinner respects deferred service helper contract. |
| Parent image transition at Abandonment rotation expiry | The cache-only semantic expiry remains pending, retries through one low-frequency shared single-shot, prepares any permitted selected-art cache miss on worker IO, then commits one weighted-random non-repeating draw through the sparse fade. |
| Settings open/close without Steam tab visit | No Steam auth/cache/provider activity. |
| Steam family master off | No Steam card is created, expected by fade coordination, or included in stack preview/status; subordinate settings are hidden and saved card choices remain intact for re-enable. |
| Steam tab open | Controls build once, rehydrate non-secret encrypted-storage availability, and read at most one recent-games cache record on shared IO for bracketed selection names; no credential decrypt, directory scan, provider request, or full library refresh. |
| Check Saved Connection | UI remains responsive; success/failure feedback is gentle; a failed check does not erase the linked Steam ID or valid cached card. |
| Square/Portrait artwork width 140 / 180 / 190 | Art remains header/right aligned and cover-filled; Portrait grows only the authored height; title, latest unlocks, `Unlocked`, capsules, shadows, and card bounds do not overlap, clip, or rearrange. |
| Double capsules on | Every visible field receives a centred upper heading and fitted lower value; `Previous` uses `PREVIOUSLY`; complete heading/value row pairs grow downward without overlap. |
| Double capsules off | Every field uses the compact colon-free left-label/right-value composition and elides only its own value. |
| Capsule font minimum/default/maximum | Capsule height, rail pitch, widget minimum, and authored card height grow as required while title/art/Unlocked remain fixed and `Custom` remains a uniform scale. |
| Capsule alpha extremes | Fill and border reflect selected RGBA independently; shadow remains exterior-only and text remains legible. |
| Normal monitor position | Card participates in shared stacking with other authored cards. |
| Custom on one/multiple displays | Committed rect survives long title, field toggles, restart, and monitor/DPR change. |
| `monitor: ALL` | Same semantic card state across displays; paint assets are instance/DPR safe. |
| Friend Grid/List | Bounded, readable, no unbounded list growth. |
| Frozen `.scr` / MC build | Storage and generic placeholders resolve without cwd; no credentials/cache shipped in installer. |

### 12.8 Performance and diagnostic validation

Use existing diagnostic flags rather than always-on logging:

Use `--devsteam` only when the pass intentionally includes Steam Journey or Friend Pulse.

```text
--steam
--perf
--cache
--set
--geo
--life
```

Look for:

- no per-frame service work;
- no repaint/update rescue loop;
- no duplicate request submission across cards/displays;
- one source-record freshness write per successful provider response, with no unchanged-model repaint or prepared-art invalidation;
- no transition-time spinner churn;
- bounded asset/cache work;
- card paint budget comparable to other framed overlay cards;
- clean teardown with no pending Steam tasks/timers/resource leaks;
- loud warnings for actual fallback/source/profile/geometry failures.

---

## 13. Family-wide acceptance criteria

### Architecture

- [ ] Four independently enabled cards are descriptor-backed, factory-created, and lifecycle-managed through normal SRPSS paths.
- [ ] Steam has one shared typed provider/cache boundary, but no giant widget, second manager, or second settings truth.
- [ ] Shared work deduplicates across widgets and displays.
- [ ] Each card owns presentation and card-specific scoring, not generic backend code.
- [ ] `EventSystem` notifications are generation/profile aware.
- [ ] Existing managers retain their ownership domains.

### Settings and Custom

- [ ] Defaults are canonical, documented, snapshot-regenerated, and tested.
- [ ] Reset/import/export uses shared normalization/preservation path.
- [ ] Secrets and account-private cache never export.
- [ ] All controls signal-block during loading.
- [ ] General Settings opening and untouched Steam section do no Steam work.
- [ ] Custom geometry is authoritative and recoverable for every card.
- [ ] Non-Custom dynamic footprint uses shared authored stacking, not private geometry moves.

### Visual/runtime

- [ ] Cards use shared painter-owned shadow/card language and strong clipped art.
- [ ] No provider/cache/image work occurs in paint or constructors.
- [ ] Valid cache paints first without blank flash.
- [ ] Disabled cards stay hidden; enabled cards with no connection and no usable cache show the centered Steam connection prompt instead of a dead panel.
- [ ] Transition-aware deferral and visible-fallback rules use the shared service helpers.
- [ ] Identical resolved visible models do not produce cache churn or repaint churn.
- [ ] Assets are DPR-aware and prepared outside paint.
- [ ] There is no new global input path or private browser helper.

### Security/privacy

- [ ] Steam API key/profile payload is strictly DPAPI encrypted at rest.
- [ ] Steam never uses plaintext credential fallback.
- [ ] Key/friend/account data is absent from repo, package, logs, export, normal settings, cache path, and fixtures.
- [ ] Disconnect performs the requested destructive wipe, while ordinary reset/import preserves local credentials.
- [ ] Private/unavailable friend data is never converted into a false offline state.

### Product

- [ ] Achievement Pulse is useful first and has literal Custom selection.
- [x] Abandonment Issues refuses to invent last-played history.
- [ ] Friend Pulse is social but bounded and privacy-aware.
- [ ] Steam Journey stays a curated, source-proven library journey rather than a patch ticker.
- [ ] Every card can be disabled, positioned, Custom-positioned, reset, and tested independently.

---

## 14. Documentation and change-management checklist

Before merge:

- [ ] Update `Spec.md` with the durable Steam architecture, security, service-runtime, and Custom contracts that are actually implemented.
- [ ] Update `Index.md` with every new Steam module and its responsibility.
- [ ] Update `Docs/Contracts.md` with source-of-truth links for credentials, cache, data model, and card routes.
- [ ] Update `Docs/TestSuite.md` with Steam regression files and runtime validation commands.
- [ ] Update `Docs/Defaults_Guide.md` only if the default/export/preservation contract grows.
- [ ] Update `Current_Plan.md` only while this work is active; prune completed tasks afterward.
- [ ] Add a dated item to `Docs/Historical_Bugs.md` only when a real Steam regression teaches a reusable rule.
- [ ] Verify every new helper has at least one production caller and no dead “future route” implementation.
- [ ] Review generated/default snapshot artifacts instead of hand-editing them.
- [ ] Make a small, reviewable sequence of commits. Security/storage foundation should not be buried inside a visual card commit.

---

## 15. Recommended next implementation slices

Achievement Pulse and Abandonment Issues now prove the secure cache-first, dynamic Custom-card, source-provenance, shared-profile rotation, and sparse live-content-transition contracts. The remaining sequence is:

1. complete Abandonment Issues frozen-build, Custom geometry, transition, long-idle, and multi-display runtime validation;
2. build Steam Journey's bounded app-news adapter plus deterministic source/failure fixtures;
3. prove its editorial classifier rejects routine/noisy patch-ticker material before adding the one-item chronological card;
4. add watched/focus-library history, dismissal, and request-budget policy before optional broader coverage;
5. implement Friend Pulse only after private/partial friend fixtures and first-observation semantics are locked;
6. retain `--devsteam` for Steam Journey and Friend Pulse until each card independently passes source, privacy, visual, Custom, lifecycle, and perf gates.

This order uses the now-proven public app-news transport without treating transport success as product-quality classification, and it keeps the privacy-heavier social card behind its own evidence gate.
