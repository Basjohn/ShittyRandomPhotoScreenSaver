# Gmail Widget — Full Implementation Plan

Version: 1.3 | Date: 2026-04-27 | Status: Phase 2 Complete (Widget Core)
Decision: Adapt archive code; do not rewrite.
Scope: Bring archive/gmail_feature/ into production as a dev-gated overlay widget.

---

## 1. Executive Summary

The archived Gmail widget already uses BaseOverlayWidget, ThreadManager, ShadowFadeProfile, and standard OAuth 2.0 PKCE flows implemented via `requests` (no `google-auth-oauthlib`). The work is integration and hardening, not reconstruction.

### Target Architecture

core/gmail/              # Relocated + hardened oauth + client
core/windows/dpapi.py    # NEW: Windows token encryption
core/windows/secure_url_launcher.py  # REFACTOR: generic bridge
core/audio/              # NEW: QtMultimedia OGG player
widgets/gmail_widget.py  # Relocated + adapted
widgets/gmail_components.py
ui/tabs/widgets_tab_gmail.py
core/settings/models.py   # APPEND: GmailWidgetSettings
core/settings/default_settings.py # APPEND: Gmail defaults (canonical dict)
core/settings/defaults.py      # APPEND: PRESERVE_ON_RESET keys if any
core/dev_gates.py         # APPEND: is_gmail_enabled()
images/google-gmail.png   # EXISTING (PNG only — no SVG)
images/gmail-envelope.png # NEW (32x32, unread indicator)
images/gmail-read.png     # NEW (16x16, mark-as-read action icon)
images/gmail-spam.png     # NEW (16x16, spam action icon)
images/gmail-trash.png    # NEW (16x16, trash action icon)

---

## 2. Phase 0 — Pre-Flight & Repository Hardening

**Goal:** Prevent credential leakage before any Gmail code enters the active tree.

- [x] **P0.1** Add `**/client_secrets.json` to `.gitignore`.
- [x] **P0.2** Add `**/gmail_token*.pickle` and `**/gmail_token*.enc` to `.gitignore`.
- [x] **P0.3** Create `core/gmail/` directory with `__init__.py` exporting public API.
- [x] **P0.4** Verify `images/google-gmail.png` exists (21.7 KB — slightly over 10KB target but acceptable; no action needed).
- [x] **P0.5** Source/create icon assets:
  - `images/gmail-envelope.png` (32x32, unread indicator) — created from `images/gmail-envelope.svg` via `tools/convert_svg_to_png.py`
  - `images/gmail-read.png` (16x16, mark-as-read action) — created from `images/gmail-read.svg` via `tools/convert_svg_to_png.py`
  - `images/gmail-spam.png` (16x16, spam action) — created from `images/gmail-spam.svg` via `tools/convert_svg_to_png.py`
  - `images/gmail-trash.png` (16x16, trash action) — created from `images/gmail-trash.svg` via `tools/convert_svg_to_png.py`
  - *(Source SVGs created inline; generic converter `tools/convert_svg_to_png.py` refactored from `convert_weather_svgs.py`.)*
- [x] **P0.6** Verify `resources/tutuogg.ogg` exists (confirmed).
- [x] **P0.7** Verified `requests` is available in `requirements.txt`. Removed unused `google-auth-oauthlib`, `google-auth`, `google-api-python-client` — hardened code uses `requests` directly.
- [x] **P0.8** Verify `PySide6.QtMultimedia` is available (confirmed via import test).

---

## 3. Phase 1 — Foundation: Core Module Relocation & Hardening

**Goal:** Move OAuth and client into `core/gmail/`. Harden paths, encrypt tokens, fix secure-desktop URL launching. Must be standalone testable before widget is imported.

### 3.1 Relocation

- [x] **P1.1** Copy `archive/gmail_feature/gmail_oauth.py` → `core/gmail/gmail_oauth.py` (hardened with DPAPI, requests, ephemeral ports, state CSRF).
- [x] **P1.2** Copy `archive/gmail_feature/gmail_client.py` → `core/gmail/gmail_client.py` (hardened with requests, threading.Lock, no body/snippet access).
- [x] **P1.3** Create `core/gmail/__init__.py` re-exporting public API.

### 3.2 Path Hardening

**Problem:** Archive hardcodes `../../client_secrets.json`. This breaks when moved to `core/gmail/`.

- [x] **P1.4-P1.10** Path hardening complete: `get_app_data_dir()` used; `credentials_path`/`token_path` params accepted with canonical defaults; missing file logged at ERROR with actionable message.

### 3.3 Token Encryption (DPAPI)

**Reasoning:** Token pickle is unencrypted in `%APPDATA%`. Windows DPAPI encrypts to user+machine without key management.

- [x] **P1.11-P1.14** DPAPI module created at `core/windows/dpapi.py` with Windows `CryptProtectData` and non-Windows plain fallback. Integrated into `GmailOAuthManager` with legacy JSON migration path. DPAPI ciphertext is safe to commit accidentally (bound to user+machine), but `.gitignore` still excludes token files as defense-in-depth.
- [x] **P1.15** DPAPI roundtrip covered by `tests/test_gmail_backend_smoke.py` (test_dpapi_roundtrip).

### 3.4 Secure Desktop URL Launching

**Problem:** `webbrowser.open()` fails in `.scr` SYSTEM/secure-desktop mode. Reddit solves this via a helper bridge.

- [x] **P1.16-P1.18** Bridge audit complete: `reddit_helper_bridge.py` is URL-agnostic. Created thin wrapper `core/windows/secure_url_launcher.py` with generic `open_url(url)`.
- [x] **P1.19** Update `GmailClient.open_message_in_browser()` to use `open_url()`.
- [x] **P1.20** Update `GmailWidget.handle_click()` header click to use `open_url()`.
- [ ] **P1.21** Update `RedditWidget` to generic launcher only if trivial.
- [x] **P1.22** Created `tests/test_secure_url_launcher.py` with bridge + fallback coverage.

### 3.5 GmailClient Thread Safety & Resilience

`google-api-python-client` `Resource` objects are **not thread-safe**.

- [x] **P1.23-P1.28** Thread safety & resilience complete: replaced `google-api-python-client` with `requests`; `threading.Lock()` around all API calls; `EmailMetadata` is frozen with `tuple` labels; defensive `(5,30)` timeouts; retry loop with `DEBUG` logging.

### 3.6 GmailOAuthManager Hardening

- [x] **P1.29-P1.34** OAuth hardening complete: `revoke_credentials()` calls Google revoke endpoint; `clear_local_credentials()` deletes token and resets state; ephemeral port scan 8080-8099; server timeout `SERVER_TIMEOUT_SECONDS = 300`; `state` CSRF parameter used; `redirect_uri` uses `/callback` path matching Google Console registration.

---

## 4. Phase 2 — Widget Adaptation & Integration

**Goal:** Relocate widget to `widgets/gmail_widget.py`, fix imports, align with current `BaseOverlayWidget` API, replace SVG with PNG, add envelope icon.

### 4.0 Email Data Cache (New)

**Requirement:** Keep last-known email list on disk so the widget can paint immediately on startup without waiting for the first network fetch. Cache is non-sensitive (metadata only — no body/snippet).
- **Reasoning:** Eliminates blank-widget flash on screensaver startup. Cache is refreshed in background; UI paints cached data immediately, then swaps to fresh data when fetch completes.

- [x] **P2.0a** Add `email_cache_path: Path` defaulting to `get_app_data_dir() / "gmail_cache.json"`.
- [x] **P2.0b** On successful fetch, serialize `List[EmailMetadata]` as JSON (message_id, sender, subject, labels, timestamp, unread flag) to `email_cache_path`.
- [x] **P2.0c** On widget initialization / `start()`, if `email_cache_path` exists and is < 24h old, load and paint immediately. Fire background fetch immediately after.
- [x] **P2.0d** On background fetch completion, write new cache and `update()` the widget.
- [x] **P2.0e** Cache file must be stored in `%APPDATA%/SRPSS/cache/` (same directory as other caches), **never in the git repo**, and must contain **no credential or token data**.
- [x] **P2.0f** If cache is > 24h old, treat as stale: paint error/empty state while fetching.
- [x] **P2.0g** Use atomic write (write to temp, rename) to prevent corruption if screensaver exits mid-write.

### 4.1 Relocation & Import Fix

- [x] **P2.1** Copy `archive/gmail_feature/gmail_widget.py` → `widgets/gmail_widget.py`.
- [x] **P2.2** Update imports to new locations (`core.gmail`, `core.windows.secure_url_launcher`).
- [x] **P2.3** Create `widgets/gmail_components.py` with `GmailPosition` enum (mirror `reddit_components.py` pattern).

### 4.2 BaseOverlayWidget API Alignment

- [x] **P2.4** Read `widgets/base_overlay_widget.py` and compare `__init__` signature against archive usage.
- [x] **P2.5** Verify `overlay_name="gmail"` is accepted.
- [x] **P2.6** Verify `_shadow_config` attribute exists.
- [x] **P2.7** Verify `_apply_base_styling()` still exists.
- [x] **P2.8** Verify `_update_content()` is the correct refresh hook. *(Note: not used — widget uses timer-based fetch cycle instead.)*
- [x] **P2.9** Document any API drift and adjust widget code.

### 4.3 Asset Loading: PNG Only, No SVG

**Reasoning:** User explicitly stated SVG causes engine slowdown. Archive tries SVG first then PNG fallback. We will use PNG exclusively.

- [x] **P2.10** Rewrite `_load_brand_pixmap()` to load `images/google-gmail.png` **only**.
- [x] **P2.11** Delete SVG fallback code entirely (remove dead code).
- [x] **P2.12** If PNG missing, log WARNING and draw text "Gmail" fallback instead of crashing.
- [x] **P2.13** Implement `_load_envelope_pixmap()` for `images/gmail-envelope.png`.
- [x] **P2.14** If envelope PNG missing, log WARNING and continue gracefully. *(QPainterPath fallback deferred — text header is sufficient.)*

### 4.4 Envelope Icon & Timestamp Paint Logic

**Requirement:** Envelope icon next to unread emails; read emails show dim/no icon. Envelope is optional but defaults **ON**.

- [x] **P2.15** Add `show_envelope_icon: bool` setting (default **True**).
- [x] **P2.16** In `_paint_emails()`, add envelope column before sender/time when enabled.
- [x] **P2.17** Unread: envelope icon at full color.
- [x] **P2.18** Read: envelope icon grayscale-dimmed.
- [x] **P2.19** Adjust column widths: envelope 16px + 6px margin.
- [x] **P2.20** Cache scaled envelope QPixmap to avoid per-frame re-scale.

### 4.4b Logo Desaturation (New)

**Requirement:** When no unread emails exist, desaturate the Gmail logo/header to indicate "all clear".
- **Reasoning:** Visual feedback at a glance. Matches `desaturate_when_no_unread` setting already in settings model.

- [x] **P2.20b** Wire existing `desaturate_when_no_unread` setting (already in `GmailWidgetSettings`, default **True**) into `_paint_header()` logic.
- [x] **P2.20c** In `_paint_header()`, if `desaturate_when_no_unread` is True and zero unread messages in current list, draw grayscale logo via `QImage.convertToFormat(Format_Grayscale8)`.
- [x] **P2.20d** Desaturation cached: `_ensure_desaturated_brand()` computes once and stores `_brand_pixmap_desaturated`.

### 4.5 Secure URL Integration in Widget

- [x] **P2.21** Replace `import webbrowser` and `webbrowser.open(...)` in `handle_click()` with `open_url(...)`.
- [x] **P2.22** Header click opens `https://mail.google.com` via `open_url()`.
- [x] **P2.22b** **Unread count badge**: parentheses count "Gmail (N)" in header text. Shown only when unread > 0.
- [x] **P2.23** Row click opens message via `GmailClient.open_message_in_browser()` which uses `open_url()`.
- [x] **P2.24** Use `open_url()` from `core/windows/secure_url_launcher`.

### 4.5b Click Behavior & Hit Rects (New)

**Requirement:** Clear separation of click targets so row click, three-dot button click, and header click never conflict.

- [x] **P2.24b** Hit rects computed in `paintEvent` (acceptable — rect computation is trivial; pure geometry, no alloc).
- [x] **P2.24c** Row split: action hit rects checked first (three-dot 24px zone), then row body. No overlap.
- [x] **P2.24d** Header hit rect opens `https://mail.google.com` via `open_url()`.
- [x] **P2.24e** Error/auth states: entire widget body is single click target (auth → OAuth, other → retry fetch).
- [x] **P2.24f** Click handling uses `local_pos` from `handle_click()`. No global math.

### 4.6 Per-Row Three-Dot Action Menu

**Requirement:** Every message row has a visible three-dot (vertical ellipsis or "...") button on the far right. Clicking it opens a compact `QMenu` with icon-labelled actions. All callbacks run on the UI thread.
- **Reasoning:** Hover-reveal and tooltips are banned in this project (overpaint, performance cost, interaction fragility). The button is always visible when the feature is enabled.

- [x] **P2.25** Add `show_three_dot_menu: bool` setting (default **True**).
- [x] **P2.26** Three-dot rendered as 3 `drawEllipse` dots (painter) at right edge of each row. 24px zone.
- [x] **P2.27** Button always visible when enabled. No hover, no tooltip.
- [x] **P2.27b** *(Changed)* Rendered via `QPainter.drawEllipse()` × 3 instead of drawText — visually cleaner.
- [x] **P2.28** QMenu with Mark As Read (conditional on unread), Archive, Spam, Trash. Icons via `QIcon(QPixmap)`.
- [x] **P2.29** *(Corrected)* Action HTTP calls dispatch to IO thread via `ThreadManager.submit_io_task()`. UI refresh via `invoke_in_ui_thread(self._fetch_emails)`.
- [x] **P2.30** `shiboken6.isValid()` guard in `_dispatch_action()` before invoking action function.
- [x] **P2.31** QMenu uses inline dark stylesheet (neutral palette, no theme conflict).
- [x] **P2.32** QMenu created per-click with `WA_DeleteOnClose`, parented to widget. No singleton menu.

### 4.7 Title Case Conversion (New)

**Requirement:** Sender and subject text can be automatically converted to Title Case. Optional but defaults **ON**.

- [x] **P2.33** Add `auto_title_case: bool` setting (default **True**).
- [x] **P2.34** In `_paint_emails()`, apply `_smart_title_case()` to subject when enabled. *(Sender left as-is — name casing from Gmail API is usually correct.)*
- [x] **P2.35** Original casing preserved in `EmailMetadata`; transformation at paint time only.

### 4.8 Separator Lines (New)

**Requirement:** Horizontal separator lines between message rows, mirroring Reddit widget's `show_separators`. Optional but defaults **ON**. The separator between the *unread* group and the *read* group is 50% thicker than regular row separators.

- [x] **P2.36** Add `show_separators: bool` setting (default **True**).
- [x] **P2.37** In `_paint_emails()`, 1px separator after each row + thicker separator at unread→read boundary.
- [x] **P2.38** Emails sorted unread-first (newest within each group) in `_on_emails_fetched()`. Separator drawn at boundary.
- [x] **P2.39** Separator colors: row separators `rgba(200,200,200,30)`, unread/read boundary `rgba(180,180,180,60)`.

### 4.9 Time Received Display (New)

**Requirement:** Show email received time. Optional but defaults **ON**. Placement adapts based on envelope icon visibility.
- **Reasoning:** Timestamp placement changes based on envelope visibility to avoid column collision and keep the widget compact.


- [x] **P2.40** Add `show_timestamp: bool` setting (default **True**).
- [x] **P2.41–P2.43** *(Simplified)* Timestamp always inline on the same row, in smaller font, placed after envelope column. No separate below-subject line — keeps row height uniform.
- [x] **P2.44** Timestamp format: `_format_relative_time()` in `gmail_components.py` — "Xm", "Xh", "Yesterday", "Mon 14:32", "Apr 12".
- [x] **P2.45** Empty/failed timestamp gracefully omitted.

### 4.10 Empty & Error States (New)

**Requirement:** The widget must never crash or show raw Python tracebacks. Graceful degradation for all edge cases.

- [x] **P2.46** Empty inbox: centered "No unread emails" text, dimmed color. Header still painted.
- [x] **P2.47** Auth failure: "Gmail not connected. Tap to authenticate." Full widget click triggers OAuth.
- [x] **P2.48** Network failure: "Gmail unavailable. Tap to retry." Full widget click retries fetch.
- [x] **P2.49** All error states are pure paint — no popups.
- [x] **P2.50** Error text uses `_text_color.darker(120)` — adapts to theme.

---

## 5. Phase 3 — Settings Architecture & Persistence

**Goal:** Integrate Gmail widget with `SettingsManager`, models, defaults, and UI tab.

### 5.1 Settings Model

- [x] **P3.1** Read `core/settings/models.py` to understand dataclass pattern (e.g., `ClockWidgetSettings`). Note: Reddit uses raw dict access, not a dataclass.
- [x] **P3.2** Create `GmailWidgetSettings` dataclass:
  - `enabled: bool = False`
  - `position: str = "top_left"`
  - `limit: int = 5`
  - `refresh_minutes: int = 5`
  - `filter_label: str = "INBOX"`
  - `show_sender: bool = True`
  - `show_subject: bool = True`
  - `show_envelope_icon: bool = True`
  - `show_three_dot_menu: bool = True`
  - `show_unread_count_in_header: bool = True`
  - `auto_title_case: bool = True`
  - `show_separators: bool = True`
  - `show_timestamp: bool = True`
  - `desaturate_when_no_unread: bool = True`
  - `play_sound_on_new_mail: bool = False`
  - `sound_volume_percent: int = 50`
  - `sound_file_path: str = "resources/tutuogg.ogg"`
- [x] **P3.3** Add `from_settings()` and `to_dict()` methods following existing pattern.
- ~~**P3.4**~~ *Removed — no top-level `AppSettings` dataclass exists. Flat dict convention is used.*

### 5.2 Defaults

- [x] **P3.5** Add Gmail defaults to `core/settings/default_settings.py` (the canonical flat `DEFAULT_SETTINGS` dict). If any values must survive reset, add their dotted keys to `PRESERVE_ON_RESET` in `core/settings/defaults.py`.

### 5.3 Widget Settings Integration

- ~~**P3.6-P3.7**~~ *Already done — constructor accepts `settings: Optional[Any]` and calls `apply_settings()` if provided.*
- [x] **P3.8** `apply_settings()` method already exists. **Correction:** Update attr names to match config dict keys (e.g. `enabled` not `gmail_enabled`).
- ~~**P3.9**~~ *Removed — individual setters should NOT persist to SettingsManager. The UI tab save function handles persistence. Setters only update widget runtime state.*
- ~~**P3.10**~~ *Removed — unnecessary. Existing pattern: UI tab saves → SettingsManager → widget manager applies. No widget-level signal needed.*

### 5.4 Settings UI Tab

- [x] **P3.11** Read `ui/tabs/widgets_tab_reddit.py` as reference for layout and styling.
- [x] **P3.12** Create `ui/tabs/widgets_tab_gmail.py` using **only** `ui/tabs/shared_styles.py` helpers:
  - `style_group_box()` for the outer `QGroupBox`.
  - `add_aligned_row()` for every label+control row.
  - `add_swatch_label()` + `ColorSwatchButton` for color rows.
  - `StyledComboBox`, `NoWheelSlider` for dropdowns/sliders.
  - `setProperty("circleIndicator", True)` on all `QCheckBox` instances.
  - `INFO_LABEL_STYLE` / `STATUS_LABEL_STYLE` for helper/status text.
  - No inline `setStyleSheet()` strings for form elements.
  Controls to build:
  - Enable checkbox (gated by dev flag — if dev gate off, show "Enable (requires --devgmail)" disabled).
  - Position dropdown (top_left, top_right, bottom_left, bottom_right).
  - Limit spinner (5–10).
  - Refresh interval spinner (1–60 minutes).
  - Filter label line edit (INBOX, CATEGORY_PRIMARY, etc.).
  - Show sender / show subject checkboxes.
  - Show envelope icon checkbox.
  - Show three-dot action menu checkbox.
  - Show unread count in header checkbox.
  - Show separator lines checkbox.
  - Show time received checkbox.
  - Auto title case checkbox.
  - Desaturate logo when no unread checkbox.
  - *(If dev gate off: all controls visible but greyed out; info label reads "Enable via --devgmail flag.")*
  - Text / background / border color swatches (follow Reddit color row pattern).
  - *Sound controls deferred to Phase 5 — only add UI after `NotificationSoundPlayer` exists.*
- [x] **P3.13** Implement `build_gmail_ui(tab, layout)`, `load_gmail_settings(tab, widgets)`, and `save_gmail_settings(tab) -> dict`.
- [x] **P3.14** Register Gmail in `ui/tabs/widgets_tab.py` at every integration point:
  1. Import `build_gmail_ui`, `load_gmail_settings`, `save_gmail_settings`.
  2. Add `self._btn_gmail = QPushButton("Gmail")` in button list.
  3. Append `self._gmail_container` to `_subtab_containers`.
  4. Call `build_gmail_ui(self, layout)` in `_setup_ui()`.
  5. Add Gmail color defaults in `__init__` (`self._gmail_color`, `self._gmail_bg_color`, `self._gmail_border_color`).
  6. Add Gmail widget attrs to the `_widget_attrs` signal-block list in `_load_settings()`.
  7. Call `load_gmail_settings(self, widgets)` in `_load_settings()`.
  8. Call `save_gmail_settings(self)` in `_save_settings_now()`.
  9. Merge returned config into `existing_widgets['gmail']`.
- ~~**P3.15**~~ *Removed — `Docs/Defaults_Guide.md` does not exist.*

---

## 6. Phase 4 — Dev Gating & Lifecycle Registration

**Goal:** Hide Gmail widget behind `--devgmail` CLI flag. Register in overlay lifecycle.

### 6.1 Dev Gate

- [x] **P4.1** Read `core/dev_gates.py` to understand `is_blob_enabled()`, `is_goo_enabled()` pattern.
- [x] **P4.2** Add `is_gmail_enabled() -> bool` reading `--devgmail` from `sys.argv`.
- [x] **P4.3** Add gmail kwarg to `force_gate()` for tests (mirrors existing `force_gate()` pattern; `force_gmail_gate` not needed as separate fn).
- [x] **P4.4** Add `--devgmail` to `main.py` filtered args set.

### 6.2 Widget Lifecycle Registration

- [x] **P4.5** Located in `rendering/widget_setup_all.py::setup_all_widgets()` (factory-driven).
- [x] **P4.6** Added Gmail block after Imgur, gated by `is_gmail_enabled()`.
- [x] **P4.7** `WidgetType.GMAIL` registered in `ui/widget_stack_predictor.py`; collisions surfaced via `gmail_stack_status` label.
- [x] **P4.8** Added Gmail to `compute_expected_overlays()` (gated) + `add_expected_overlay("gmail")` in setup.
- [x] **P4.9** Cleanup automatic via `BaseOverlayWidget` lifecycle + `ResourceManager.register_qt()` in `WidgetManager.register_widget()`.
- ~~**P4.10**~~ *Merged into P3.12 — dev gate check is part of the UI tab build, not a separate step.*

### 6.3 Widget Factory (if applicable)

- [x] **P4.11** Confirmed factory pattern exists in `rendering/widget_factories.py`.
- [x] **P4.12** Added `GmailWidgetFactory` and registered it in `WidgetFactoryRegistry._register_default_factories()`.
- ~~**P4.13**~~ *Stale — factories receive raw config dict, not `AppSettings`. `GmailWidget(parent, position, settings=config)` passes the dict; `apply_settings()` handles dict/dataclass.*

---

## 7. Phase 5 — Notification Sound System (OGG)

**Goal:** Play OGG sound when new unread emails arrive **after** session start. Volume adjustable. Default `resources/tutuogg.ogg`.

### 7.1 Audio Infrastructure

- [ ] **P5.1** Verify `PySide6.QtMultimedia` is importable: `from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput`.
- [ ] **P5.2** If `QtMultimedia` unavailable, evaluate `pygame.mixer` or `sounddevice` + `soundfile` as fallback. **Preference:** `QtMultimedia` (bundled with PySide6, no extra dependency).
- [ ] **P5.3** Create `core/audio/__init__.py`.
- [ ] **P5.4** Create `core/audio/notification_sound.py`:
  ```python
  class NotificationSoundPlayer:
      def __init__(self, file_path: str, volume_percent: int = 50) -> None: ...
      def play(self) -> None: ...
      def set_volume(self, percent: int) -> None: ...
      def set_file_path(self, path: str) -> None: ...
  ```
- [ ] **P5.5** Use `QMediaPlayer` + `QAudioOutput`. Set `audioOutput.setVolume(volume_percent / 100.0)`.
- [ ] **P5.6** Handle OGG via `QMediaPlayer` (QtMultimedia supports OGG via built-in plugins).
- [ ] **P5.7** Parent `QMediaPlayer` to `QApplication.instance()` (or a dedicated long-lived QObject singleton) — **NOT** the widget itself. If the widget is destroyed during playback (e.g., screensaver exit), a widget-parented player will cut off audio. Use a singleton `NotificationSoundPlayer` that outlives individual widget instances.
- [ ] **P5.8** Add error handling: if file missing or format unsupported, log WARNING and disable sound for the session.
- [ ] **P5.9** Add test `tests/test_notification_sound.py` with a mock/stub.

### 7.2 New-Mail Detection

**Requirement:** Sound only for mail that arrives **after** the session starts. Not a startup blast for pre-existing unread.

- [ ] **P5.10** In `GmailWidget`, maintain `self._seen_message_ids: set[str]`.
- [ ] **P5.11** On first fetch after `start()`, populate `_seen_message_ids` with all returned message IDs. **Do not play sound.**
- [ ] **P5.12** On subsequent fetches, compute `new_ids = returned_ids - _seen_message_ids`.
- [ ] **P5.13** If `new_ids` non-empty and `play_sound_on_new_mail` is True, call `NotificationSoundPlayer.play()`.
- [ ] **P5.14** Add `_seen_message_ids` to `cleanup()` reset (clear on stop/start cycle).
- [ ] **P5.15** Ensure sound plays on UI thread (QtMultimedia `QMediaPlayer` is thread-safe for `play()`, but initialization should be on UI thread).

### 7.3 Volume & File Settings Wiring

- [ ] **P5.16** In `GmailWidget.apply_settings()`, pass `sound_file_path` and `sound_volume_percent` to `NotificationSoundPlayer`.
- [ ] **P5.17** Ensure volume changes apply immediately (no restart required).
- [ ] **P5.18** Ensure file path changes apply on next `play()` call (no reload required).

---

## 8. Phase 6 — Testing, Validation & Sign-Off

### 8.1 Unit Tests

- [ ] **P6.1** `tests/test_gmail_oauth.py` — mock Google token endpoint, verify PKCE params, verify DPAPI encrypt/decrypt roundtrip.
- [ ] **P6.2** `tests/test_gmail_client.py` — mock `requests.get` / `requests.post` (or `responses` library), verify `list_messages()`, `mark_as_read()`, `archive_message()` return correct `EmailMetadata`.
- [ ] **P6.3** `tests/test_gmail_widget.py` — instantiate widget with mock settings, verify `paintEvent` does not crash with empty email list, verify `handle_click` returns False for miss.
- [ ] **P6.4** `tests/test_gmail_components.py` — verify `GmailPosition` enum values.

### 8.2 Integration Tests

- [ ] **P6.5** `tests/test_gmail_settings_roundtrip.py` — create `GmailWidgetSettings`, serialize via `to_dict()`, deserialize via `from_settings()`, assert equality.
- [ ] **P6.6** `tests/test_gmail_dev_gate.py` — verify widget is only instantiated when `--devgmail` is in `sys.argv` (or `force_gate(gmail=True)`).

### 8.3 Secure Desktop Tests

- [ ] **P6.7** Manual test: Run as `.scr` preview, click Gmail header → browser opens via helper bridge.
- [ ] **P6.8** Manual test: Run as `.scr` preview, click email row → specific email opens via helper bridge.
- [ ] **P6.9** Manual test: Verify `webbrowser.open()` fallback does not crash in preview mode (it will work in normal mode, fail silently in SYSTEM mode — acceptable if bridge works).

### 8.4 Memory & Resource Tests

- [ ] **P6.10** Run widget through 50 start/stop cycles in test harness; verify no refresh `QTimer` or `QMenu` leaks via `shiboken6.getAll()` (if available) or manual audit.
- [ ] **P6.11** Verify `cleanup()` stops all timers and deletes `QMenu` references.

### 8.5 Performance Tests

- [ ] **P6.12** Profile `paintEvent` with 10 emails: ensure < 5ms per frame on 1080p. Follow iterative cycling: run for 15s, read all logs, fix, repeat.
- [ ] **P6.13** Verify envelope pixmap cache is effective (no per-frame `QPixmap::scaled`).

### 8.6 Sign-Off Checklist

- [ ] **P6.14** No `client_secrets.json` in git (verify `git status`).
- [ ] **P6.15** No `gmail_token*.pickle` or `*.enc` in git.
- [ ] **P6.16** All new code passes `ruff check --fix`.
- [ ] **P6.17** All tests pass.
- [ ] **P6.18** `Index.md` updated with new files/classes.
- [ ] **P6.19** `Docs/Guardrails.md` updated with Gmail-specific security notes (if any new patterns).
- [ ] **P6.20** Archive directory `archive/gmail_feature/` marked deprecated (add `README.md` noting "Superseded by widgets/gmail_widget.py and core/gmail/ — kept for historical reference only"). Do not delete; archive is valuable for reference.

---

## 9. Security Anti-Leak Policy & Credential Hygiene

**Goal:** Ensure zero credential material ever enters the repository, build artifacts, or logs.

### 9.1 Repository-Level Guards

- [ ] **S1.1** `.gitignore` must contain `**/client_secrets.json`, `**/gmail_token*`, `**/gmail_credentials*`, `**/*.pickle` (catch all pickle, not just Gmail).
- [ ] **S1.2** *(Optional / future)* Add a `pre-commit` guard that greps for `"client_id"` / `"client_secret"` patterns in non-archive Python files. The repository currently has no pre-commit infrastructure; implement only if CI is added later.
- [ ] **S1.3** `client_secrets.json` path must be runtime-resolved only; no `pathlib.Path(__file__).parent / "client_secrets.json"` patterns that could be committed.
- [ ] **S1.4** Add `GmailConfigError` string to `Docs/Guardrails.md` under "Never commit" section.
- [ ] **S1.4b** Add `gmail_cache.json` and all files under `%APPDATA%/SRPSS/cache/` to `.gitignore` (if not already covered by broader `cache/` patterns). Ensure email cache is never committed.

### 9.2 Runtime Leak Prevention

- [ ] **S1.5** `GmailOAuthManager` must never log the `client_secret` value, even at `DEBUG`. Log only that credentials were loaded, not their content.
- [ ] **S1.6** *(Optional)* Token file may have `FILE_ATTRIBUTE_HIDDEN` on Windows. DPAPI encryption is the primary protection; ACL/Hidden flags are defense-in-depth and not required for MVP.
- [ ] **S1.7** On widget/auth failure, the error status text / UI message must never display the `client_id`, `redirect_uri`, or token file path to the user (paths can leak machine info). Use generic messages: "Gmail credentials missing. See log." No tooltips — they are banned in this project (overpaint, performance).
- [ ] **S1.8** `EmailMetadata` must never include `body` or `snippet` fields — metadata-only by design. Add a dataclass `__post_init__` assert if needed.
- [ ] **S1.9** `gmail_client.py` request logging must sanitize `message_id` from URLs? No — message IDs are not sensitive. But ensure no `body` / `raw` params are ever in the URL or logged.
- [ ] **S1.10** If token refresh fails with `invalid_grant`, the manager must auto-clear local credentials (encrypted token deleted) and require re-auth. Do not retry indefinitely with a stale refresh token.

### 9.3 Build / Distribution Safety

- [ ] **S1.11** Build script (PyInstaller / cx_Freeze) must verify `client_secrets.json` is **not** bundled into the executable unless explicitly injected at build time. If it is bundled, it is exposed to binary extraction.
- [ ] **S1.12** Document in `README.md` that `client_secrets.json` is a runtime dependency placed by the user (or build script) into `%APPDATA%/SRPSS/`.
- [ ] **S1.13** If distributing, consider using a backend proxy for token exchange instead of Desktop app client secret. This is the only way to keep the secret truly secret. Mark as **Phase 2 / future work**.

---

## 10. Paint & Performance Guardrails

**Goal:** Prevent the Gmail widget from becoming a CPU/GPU hog via unnecessary paint events, per-frame allocations, or unbounded email list growth.

### 10.1 Paint Event Discipline

- [ ] **PG1.1** `paintEvent()` must be pure — no network calls, no file I/O, no token refresh. All data must be pre-fetched and stored in widget attributes before `update()` is called.
- [ ] **PG1.2** Email list must be capped at `limit` (default 5, max 10) **at fetch time**, not at paint time. Never paint more rows than configured.
- [ ] **PG1.3** `QPainter` state changes (font, pen, brush) must be minimized. Set font once at start of email section, not per-row.
- ~~**PG1.4**~~ *Removed — premature optimization for 5-10 rows. Per-row state changes are negligible. Current per-row painting is readable and correct.*
- [ ] **PG1.5** Envelope pixmap must be **cached at scale** once when `limit` or widget geometry changes, not in `paintEvent`. Cache key = `(envelope_path, target_width, target_height)`.
- [ ] **PG1.6** Gmail logo pixmap must be cached identically. Reload only on explicit `reload_assets()` call or widget resize.
- [ ] **PG1.7** Use `QStyleHints` / `QFontMetrics.horizontalAdvance()` once and cache results; do not re-measure strings per frame.
- [ ] **PG1.8** Hit rects (`_email_hit_rects`, `_action_hit_rects`) must be recomputed only on data change or resize, not per `paintEvent`.
- [ ] **PG1.9** `update()` must not be called from `paintEvent` (infinite recursion trap). Use `QTimer.singleShot(0, self.update)` only if absolutely necessary.

### 10.2 Geometry & Visibility Guards

- [ ] **PG1.10** If widget `isHidden()` or parent `DisplayWidget` is not in overlay-visible state, `paintEvent` should early-return after logging a single WARNING (not spam).
- [ ] **PG1.11** Email fetch timer must be stopped when widget is hidden (power saving). Resume on show.
- [ ] **PG1.12** `QMenu` created in `_show_action_menu()` should be created per-click (standard Qt pattern), parented to the widget, and all references cleared in `cleanup()` to avoid dangling pointers. Avoid singleton menus with dynamically swapped actions — they are harder to reason about and more error-prone.

### 10.3 Memory Pressure

- [ ] **PG1.13** `EmailMetadata` objects must not hold references to `GmailClient` or `QPixmap`. Keep them plain dataclasses.
- [ ] **PG1.14** If email list fetch returns > `limit`, truncate immediately. Do not store unbounded lists.

---

## 11. Transition Deferral & ThreadManager Integration

**Goal:** Prevent email refresh/network I/O from stalling the UI thread during screen transitions (photo crossfades, visualizer mode switches, etc.).

### 11.1 Fetch Timing Policy

- [ ] **TD1.1** Email refresh must use `ThreadManager.submit_io_task()`, never the UI thread.
- [ ] **TD1.2** Results must be applied via `ThreadManager.invoke_in_ui_thread(lambda: self._apply_fetched_emails(data))`.
- ~~**TD1.3-TD1.4**~~ *Simplified — `invoke_in_ui_thread()` already queues safely on the Qt event loop. No transition-aware buffering needed; `update()` from an overlay widget during a transition is normal and lightweight.*
- ~~**TD1.5**~~ *Removed — ±10% jitter for a 5-minute timer is not worth the complexity. Single widget, no thundering herd.*
- [ ] **TD1.6** If a fetch is already in-flight when the timer fires again, skip the new fetch. Use an `atomic bool` or `threading.Lock()` to guard `_fetch_in_progress`.
- [ ] **TD1.7** On widget `stop()` / `cleanup()`, cancel any in-flight future (if `ThreadManager` supports it) or at least set `_cancelled = True` so the callback ignores stale results.

### 11.2 OAuth Flow Timing

- [ ] **TD1.8** The initial OAuth browser-launch + local server callback should use `ThreadManager.submit_io_task()` for the server. The URL open (`webbrowser.open()` / `open_url()` / bridge enqueue) is thread-safe and can be called directly from the IO task — no need to bounce through UI thread invoke.
- [ ] **TD1.9** Local server timeout (5 min) must be a `threading.Timer` or `socket.settimeout()`, not a busy-wait. Shutdown the server socket immediately upon receiving the callback to free the port.

---

## 12. AV False Positive Avoidance

**Goal:** Prevent Windows Defender or other AV from flagging the screensaver due to Gmail-specific behavior patterns.

### 12.1 Behavioral Patterns to Avoid

- [ ] **AV1.1** Do **not** spawn a hidden/`pythonw.exe` subprocess for OAuth callback server. Use an in-thread `HTTPServer` (already in archive). Subprocess spawning from a `.scr` is a common AV heuristic for trojans.
- [ ] **AV1.2** Do **not** write `.bat`, `.vbs`, `.ps1`, or `.exe` files to disk at runtime for URL launching. Use the existing helper bridge process (already present for Reddit) or `QDesktopServices.openUrl()`.
- [ ] **AV1.3** Do **not** use `ctypes.windll.shell32.ShellExecuteA` with `runas` or hidden window flags for URL opening. This triggers UAC/AV heuristics.
- [ ] **AV1.4** The DPAPI `ctypes` calls are safe (standard Windows API), but ensure we only import `ctypes.wintypes` inside the Windows branch, not at module top-level on Linux.
- [ ] **AV1.5** Avoid creating files in unusual locations. All Gmail files must go to `%APPDATA%/SRPSS/` (standard user-local path).
- [ ] **AV1.6** Do **not** use `urllib.request` with a custom `SSLContext` that disables certificate verification. The archive may do this for local testing — verify and remove if present.
- [ ] **AV1.7** Do **not** download executable content (`.exe`, `.dll`) from the internet as part of Gmail auth. The archive only fetches JSON from Google — verify no dynamic download behavior exists.
- [ ] **AV1.8** The in-thread `HTTPServer` on localhost may trigger a Windows Defender firewall prompt on first run. Document this in user-facing docs.
- [ ] **AV1.9** All new `.py` files should have standard docstrings and no obfuscated/encoded strings. AV flags encoded payload patterns.
- [ ] **AV1.10** Do **not** use `eval()`, `exec()`, `compile()`, or `__import__` dynamically for Gmail module loading. Use standard imports.

### 12.2 Build Artifact Hygiene

- [ ] **AV1.11** Ensure `core/windows/dpapi.py` is not flagged as ransomware-like by AV due to `CryptProtectData` usage. This is rare but can happen with overly aggressive heuristics. If flagged, add the `.scr` to AV exclusions (document for users) or use `keyring` library as alternative.
- [ ] **AV1.12** *(Stale — no longer applicable)* The `google-api-python-client` package was removed from dependencies. Hardened code uses `requests` directly. No generated discovery documents are present.

---

---

## Appendix A: Complete File Mapping

| New / Moved File | Source | Purpose |
|---|---|---|
| `core/gmail/__init__.py` | NEW | Re-exports |
| `core/gmail/gmail_oauth.py` | `archive/gmail_feature/gmail_oauth.py` | OAuth manager |
| `core/gmail/gmail_client.py` | `archive/gmail_feature/gmail_client.py` | API client |
| `core/windows/dpapi.py` | NEW | DPAPI encrypt/decrypt |
| `core/windows/secure_url_launcher.py` | REFACTOR from `reddit_helper_bridge.py` | Generic URL bridge |
| `core/audio/__init__.py` | NEW | Audio re-exports |
| `core/audio/notification_sound.py` | NEW | OGG player |
| `core/settings/storage_paths.py` | REUSE | Already exists; add Gmail token/credentials helpers if needed |
| `widgets/gmail_widget.py` | `archive/gmail_feature/gmail_widget.py` | Overlay widget |
| `widgets/gmail_components.py` | NEW | Position enum, re-exports |
| `ui/tabs/widgets_tab_gmail.py` | NEW | Settings dialog tab |
| `core/settings/models.py` | APPEND | `GmailWidgetSettings` dataclass |
| `core/settings/defaults.py` | APPEND | Gmail defaults |
| `core/dev_gates.py` | APPEND | `is_gmail_enabled()` |
| `images/gmail-envelope.png` | NEW | Envelope icon asset (32×32) |
| `images/gmail-read.png`     | NEW | Mark-as-read action icon (16×16) |
| `images/gmail-spam.png`     | NEW | Spam action icon (16×16) |
| `images/gmail-trash.png`    | NEW | Trash action icon (16×16) |

## Appendix B: Dependency Audit

| Package | Version | Purpose | Already Present? |
|---|---|---|---|
| `requests` | (existing) | Gmail REST API + OAuth token exchange | Yes |
| `PySide6.QtMultimedia` | (bundled with PySide6) | OGG notification sound | Verify sub-module importable |

## Appendix C: Security Checklist

- [ ] `client_secrets.json` never committed.
- [ ] Token file encrypted at rest (DPAPI or fallback).
- [ ] Token file path is user-local (`%APPDATA%`), not repo-local.
- [ ] OAuth `state` parameter used for CSRF protection.
- [ ] Local OAuth server uses random port + timeout.
- [ ] Scopes minimized (`gmail.readonly` + `gmail.modify`). `gmail.metadata` alone is insufficient for header-based sender/subject extraction; `gmail.readonly` is the minimal scope for our metadata-only use case.
- [ ] No message body content ever logged or stored.
- [ ] URL launching goes through secure-desktop bridge in `.scr` mode.
- [ ] `GmailConfigError` raised early if credentials missing (fail-closed).
- [ ] `clear_local_credentials()` available for user-initiated revocation.

## Appendix D: OAuth Consent Screen & Verification Notes

Because `gmail.modify` is a **sensitive scope**, Google requires verification for public use.

- **Testing mode:** Works indefinitely for up to 100 test users. Refresh tokens expire every 7 days. **Sufficient for a dev-gated personal feature.**
- **Publish mode:** Requires privacy policy, Terms of Service, and a YouTube video demonstrating scope usage. Refresh tokens do not expire. Only needed if distributing to non-developer users.
- **Recommendation:** Stay in Testing mode. Document this limitation in `README.md` or `Docs/Gmail_Widget.md`.
