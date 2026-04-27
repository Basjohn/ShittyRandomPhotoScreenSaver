# Gmail Widget — Full Implementation Plan

Version: 2.0 | Date: 2026-04-27 | Status: Phases 0–5 Complete, Phase 6 Active
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

## 2. Completed Phases (Summarised)

Phases 0–5 are fully implemented and deployed. Below is a concise summary; full detail is in git history.

### Phase 0 — Pre-Flight & Repository Hardening
- [x] `.gitignore` guards for `client_secrets.json`, `gmail_token*`, `gmail_credentials*`, `*.pickle`.
- [x] Icon assets created (`gmail-envelope.png`, `gmail-read.png`, `gmail-spam.png`, `gmail-trash.png`).
- [x] `PySide6.QtMultimedia` and `requests` verified available.

### Phase 1 — Foundation: Core Module Relocation & Hardening
- [x] `core/gmail/gmail_oauth.py` — DPAPI-encrypted token storage, ephemeral-port OAuth server, CSRF state, `requests`-based PKCE flow.
- [x] `core/gmail/gmail_imap.py` — `imaplib.IMAP4_SSL` client to `imap.gmail.com:993`, DPAPI-encrypted App Password storage.
- [x] `core/gmail/gmail_backend.py` — Unified singleton facade (`GmailBackend`) switching between IMAP (default) and OAuth modes; backend mode persisted to `gmail_backend.json` in `%APPDATA%`.
- [x] `core/gmail/gmail_client.py` — `threading.Lock()` around all API calls, frozen `EmailMetadata`, defensive timeouts.
- [x] `core/windows/dpapi.py` — Windows `CryptProtectData` + non-Windows plain fallback.
- [x] `core/windows/secure_url_launcher.py` — Generic URL bridge for `.scr` secure-desktop mode.
- [x] `core/gmail/__init__.py` — Public API re-exports.

### Phase 2 — Widget Adaptation & Integration
- [x] `widgets/gmail_widget.py` — PNG-only assets, envelope icon, three-dot action menu, title-case conversion, separator lines, timestamp display, empty/error state painting.
- [x] `widgets/gmail_components.py` — `GmailPosition`, `_format_relative_time`, `_smart_title_case`, cache serialize/deserialize.
- [x] Email cache (`gmail_cache.json` in `%APPDATA%`) for instant startup paint.
- [x] Logo desaturation when no unread emails.

### Phase 3 — Settings Architecture & Persistence
- [x] Gmail settings stored as flat dict under `'gmail'` key in `default_settings.py` (following Reddit/Weather raw-dict pattern; **no dataclass exists in `models.py`**).
- [x] `GmailWidget.apply_settings()` parses flat dict via `_apply_settings_dict()`.
- [x] Gmail defaults in `core/settings/default_settings.py`.
- [x] `ui/tabs/widgets_tab_gmail.py` — Full settings UI with `style_group_box`, `add_aligned_row`, color swatches, backend selector (IMAP / OAuth), IMAP credential panel, auth status/sign-out row.
- [x] Registered in `ui/tabs/widgets_tab.py` at all integration points.

### Phase 4 — Dev Gating & Lifecycle Registration
- [x] `core/dev_gates.py` — `is_gmail_enabled()` reads `--devgmail` from `sys.argv`.
- [x] `--devgmail` added to `main.py` filtered args.
- [x] `WidgetFactoryRegistry` — `GmailWidgetFactory` registered.
- [x] `rendering/widget_setup_all.py` — Gmail block gated by `is_gmail_enabled()`.
- [x] `compute_expected_overlays()` includes Gmail (gated).

### Phase 5 — Notification Sound System (OGG)
- [x] `core/audio/notification_sound.py` — Singleton `NotificationSoundPlayer` via `QMediaPlayer` + `QAudioOutput`.
- [x] New-mail detection: `_seen_message_ids` set; sound only for mail arriving **after** session start.
- [x] Volume + file path settings wired through UI.

---

## 3. Phase 6 — Testing, Validation & Sign-Off

### 3.1 Unit Tests

- [ ] **P6.1** `tests/test_gmail_oauth.py` — mock Google token endpoint, verify PKCE params, verify DPAPI encrypt/decrypt roundtrip.
- [ ] **P6.2** `tests/test_gmail_client.py` — mock `requests.get` / `requests.post` (or `responses` library), verify `list_messages()`, `mark_as_read()`, `archive_message()` return correct `EmailMetadata`.
- [ ] **P6.3** `tests/test_gmail_widget.py` — instantiate widget with mock settings, verify `paintEvent` does not crash with empty email list, verify `handle_click` returns False for miss.
- [ ] **P6.4** `tests/test_gmail_components.py` — verify `GmailPosition` enum values.

### 3.2 Integration Tests

- [ ] **P6.5** `tests/test_gmail_settings_roundtrip.py` — construct a flat settings dict with all new Phase 6 keys, pass through `GmailWidget.apply_settings()`, assert all attributes match. Also verify `save_gmail_settings()` in the UI tab produces a dict containing the same keys.
- [ ] **P6.6** `tests/test_gmail_dev_gate.py` — verify widget is only instantiated when `--devgmail` is in `sys.argv` (or `force_gate(gmail=True)`).

### 3.3 Secure Desktop Tests

- [ ] **P6.7** Manual test: Run as `.scr` preview, click Gmail header → browser opens via helper bridge.
- [ ] **P6.8** Manual test: Run as `.scr` preview, click email row → specific email opens via helper bridge.
- [ ] **P6.9** Manual test: Verify `webbrowser.open()` fallback does not crash in preview mode (it will work in normal mode, fail silently in SYSTEM mode — acceptable if bridge works).

### 3.4 Memory & Resource Tests

- [ ] **P6.10** Run widget through 50 start/stop cycles in test harness; verify no refresh `QTimer` or `QMenu` leaks via `shiboken6.getAll()` (if available) or manual audit.
- [ ] **P6.11** Verify `cleanup()` stops all timers and deletes `QMenu` references.

### 3.5 Performance Tests

- [ ] **P6.12** Profile `paintEvent` with 10 emails: ensure < 5ms per frame on 1080p. Follow iterative cycling: run for 15s, read all logs, fix, repeat.
- [ ] **P6.13** Verify envelope pixmap cache is effective (no per-frame `QPixmap::scaled`).

### 3.6 Sign-Off Checklist

- [ ] **P6.14** No `client_secrets.json` in git (verify `git status`).
- [ ] **P6.15** No `gmail_token*.pickle` or `*.enc` in git.
- [ ] **P6.16** All new code passes `ruff check --fix`.
- [ ] **P6.17** All tests pass.
- [ ] **P6.18** `Index.md` updated with new files/classes.
- [ ] **P6.19** `Docs/Guardrails.md` updated with Gmail-specific security notes (if any new patterns).
- [ ] **P6.20** Archive directory `archive/gmail_feature/` marked deprecated (add `README.md` noting "Superseded by widgets/gmail_widget.py and core/gmail/ — kept for historical reference only"). Do not delete; archive is valuable for reference.

---

## 4. Phase 7 — Widget Polish & Settings UI Reorganisation

**Goal:** Fix all reported UI/UX and customisation issues. Add per-element font and colour controls, width and padding options, header framing, separator customisation, and reorganise the settings UI into styled collapsible buckets. Ensure widget positioning matches other overlays and minimum width is comparable.

**Investigation Order:** Structural issues first (position, width, padding), then visual polish (header border, envelope alignment, separators), then granular customisation (fonts, colours, truncation), then settings UI reorganisation.

**Settings Key Convention:** All new settings follow the flat-dict pattern used in `default_settings.py` and `widgets_tab_gmail.py` — keys are prefixed with `gmail.` (e.g. `gmail.min_width`, `gmail.content_padding_left`, `gmail.header_font_family`). `apply_settings()` reads `settings.get("gmail.min_width", default)` and `widgets_tab_gmail.py` uses `tab._default_int("gmail", "min_width", default)`.

---

### 4.1 Positioning — "Top Center" and "Center" Draw in Top-Left

**Root Cause:** `GmailPosition` enum (`widgets/gmail_components.py`) only defines four corner values (`TOP_LEFT`, `TOP_RIGHT`, `BOTTOM_LEFT`, `BOTTOM_RIGHT`). The settings UI (`widgets_tab_gmail.py`) offers nine positions (including `Top Center`, `Center`, `Middle Left`, etc.). When `GmailPosition.from_string("top_center")` is called, it raises `ValueError` and falls back to `TOP_LEFT`. Additionally, `GmailWidget.__init__` does `OverlayPosition(position.value)` which will also fail for non-corner values, causing the widget to default to `TOP_LEFT`.

**Implementation Detail:**
- [ ] **P7.1.1** Expand `GmailPosition` enum to all nine standard `OverlayPosition` values:
  - `TOP_LEFT`, `TOP_CENTER`, `TOP_RIGHT`
  - `MIDDLE_LEFT`, `CENTER`, `MIDDLE_RIGHT`
  - `BOTTOM_LEFT`, `BOTTOM_CENTER`, `BOTTOM_RIGHT`
- [ ] **P7.1.2** Update `GmailPosition.from_string()` to recognise all nine values (accept both `top_center` and `center` aliases for the middle row).
- [ ] **P7.1.3** Update `GmailWidget.__init__` mapping so every `GmailPosition` value maps directly to the corresponding `OverlayPosition`.
- [ ] **P7.1.4** Add `_update_position()` override in `GmailWidget` (following `RedditWidget` / `WeatherWidget` pattern) that maps `GmailPosition` → `OverlayPosition` and calls `super()._update_position()`.
- [ ] **P7.1.5** Ensure `set_visual_padding()` is used (if background is disabled) so content does not hug the screen edge when positioned in the centre.
- [ ] **P7.1.6** Verify that `adjustSize()` is called before `_update_position()` in all resize/refresh paths so centre positioning uses the correct widget dimensions.

---

### 4.2 Widget Width — Minimum Width Too Small, No Customisation

**Problem:** The Gmail widget's implicit width is driven entirely by `adjustSize()` based on paint content. The current `__init__` calls `self.setMinimumWidth(400)`, yet in the screenshot the widget is clearly much narrower than Reddit and Weather widgets, suggesting the minimum width is being ignored or overridden (likely by `adjustSize()` called after paint, or by DPI scaling not being applied). Other widgets (Reddit, Imgur, Weather) either have a `setMinimumWidth()` call that actually sticks, or width is derived from card-size settings.

**Implementation Detail:**
- [ ] **P7.2.1** Investigate why `setMinimumWidth(400)` is not taking effect — check if `adjustSize()` overrides it, if DPI scaling is not being applied to the minimum, or if `resize()` is being called elsewhere with a smaller size. Also verify whether `self.setMinimumWidth()` is called before or after `BaseOverlayWidget` parent logic.
- [ ] **P7.2.2** Add `min_width: int` setting (default **320**, matching Reddit widget default). The widget's base width should match other widgets (Reddit, Weather, Media) when set to the same minimum.
- [ ] **P7.2.3** Add `max_width: int` setting (default **600**, preventing absurdly wide cards on ultrawide monitors).
- [ ] **P7.2.4** In `GmailWidget.apply_settings()`, call `self.setMinimumWidth(min_width)` and `self.setMaximumWidth(max_width)`. Ensure `adjustSize()` respects these bounds (may need to override `minimumSizeHint()` or clamp the result of `adjustSize()` rather than trusting it blindly).
- [ ] **P7.2.5** In `_paint_emails()`, respect the max width: `available_width = min(self.width() - left - margins.right() - 10, self._max_width - left - margins.right() - 10)` if max_width is set.
- [ ] **P7.2.6** **Width distribution logic for positioning:**
  - If widget is **centered** (`TOP_CENTER`, `CENTER`, `BOTTOM_CENTER`): extra width beyond content-natural-width is divided equally between left and right. `self.move(center_x - self.width() / 2, y)`.
  - If widget is **left-positioned** (`TOP_LEFT`, `MIDDLE_LEFT`, `BOTTOM_LEFT`): extra width goes to the right. The left edge stays anchored.
  - If widget is **right-positioned** (`TOP_RIGHT`, `MIDDLE_RIGHT`, `BOTTOM_RIGHT`): extra width goes to the left. The right edge stays anchored.
  - This ensures the widget grows outward from its logical anchor point, matching how Reddit/Weather behave.
- [ ] **P7.2.7** In `widgets_tab_gmail.py`, add a "Size" bucket row with `min_width` and `max_width` spinners (range 200–800, step 10).

---

### 4.3 Padding / Content Alignment — Header, Posts, Envelopes Hug Left Edge

**Problem:** `_paint_header()`, `_paint_emails()`, and empty/error states all start their drawing at `margins.left()` with zero additional padding. Other widgets add explicit horizontal padding (e.g. Reddit header starts at `margins.left() - 4` with `pad_x = 8` inside the frame; Imgur uses `rect.left() + 15`).

**Implementation Detail:**
- [ ] **P7.3.1** Add `content_padding_left: int` setting (default **12**, matching Reddit/Imgur).
- [ ] **P7.3.2** Add `content_padding_right: int` setting (default **12**).
- [ ] **P7.3.3** Add `content_padding_top: int` setting (default **8**).
- [ ] **P7.3.4** In `_paint_header()`: replace `left = margins.left()` with `left = margins.left() + self._content_padding_left`.
- [ ] **P7.3.5** In `_paint_emails()`: replace `left = margins.left()` with `left = margins.left() + self._content_padding_left`.
- [ ] **P7.3.6** In `_paint_empty_state()` and `_paint_error_state()`: apply the same left padding via `rect.adjusted(content_padding_left, 0, -content_padding_right, 0)`.
- [ ] **P7.3.7** In `widgets_tab_gmail.py`, add a "Layout" bucket row with left/right/top padding spinners (range 0–40, step 2).

---

### 4.4 Header Border / Frame — Missing Around Logo + Header Text

**Reference:** Reddit widget uses `_paint_header_frame()` (`widgets/reddit_widget.py:1445`) which calls `draw_rounded_rect_with_shadow()`. Imgur widget mirrors the same pattern (`widgets/imgur/widget.py:967–1046`).

**Implementation Detail:**
- [ ] **P7.4.1** Add `show_header_border: bool` setting (default **True**, matching other widgets).
- [ ] **P7.4.2** Copy/adapt `_paint_header_frame()` from `RedditWidget` into `GmailWidget` (respect existing shadow profile, corner radius, border width, and border colour).
- [ ] **P7.4.3** The frame must compute its rect from: logo size + logo margin + header text width + `pad_x*2` / `pad_y*2`.
- [ ] **P7.4.4** The frame should use `self._bg_border_color` and `self._bg_border_width` so it inherits the widget’s theme automatically.
- [ ] **P7.4.5** In `widgets_tab_gmail.py`, add a "Header" bucket row with `show_header_border` checkbox.

---

### 4.5 Envelope Vertical Alignment — Not Centre-Matched to Text

**Problem:** In `_paint_emails()` (`widgets/gmail_widget.py:~574–585`), the envelope pixmap is drawn at `env_x = left` and a fixed vertical offset. It is not vertically centred to the text baseline/height, causing it to sit too high or too low relative to the sender/subject line.

**Implementation Detail:**
- [ ] **P7.5.1** Compute `line_centre = row_y + (line_height / 2)`.
- [ ] **P7.5.2** Compute `env_y = int(line_centre - (envelope_pixmap.height() / 2))`.
- [ ] **P7.5.3** Clamp `env_y` so it never sits above `row_y` or below `row_y + line_height - envelope_pixmap.height()`.
- [ ] **P7.5.4** Use the same pattern as Imgur logo vertical alignment (`widgets/imgur/widget.py:1010–1016`): `line_height = header_metrics.height(); line_centre = header_top + (line_height * 0.6); icon_half = float(logo_size) / 2.0; y_logo = int(line_centre - icon_half)`.

---

### 4.6 Separator Customisation — No Colour, Thickness, or Style Controls

**Problem:** Separators are hard-coded in `_paint_emails()`:
- Row separators: `QColor(200, 200, 200, 30)`
- Unread→read boundary: `QColor(180, 180, 180, 60)`
There is no user control.

**Implementation Detail:**
- [ ] **P7.6.1** Add `separator_color: QColor` setting (default `rgba(200,200,200,40)`).
- [ ] **P7.6.2** Add `separator_thickness: int` setting (default **1**, range 1–4).
- [ ] **P7.6.3** Add `boundary_separator_color: QColor` setting (default `rgba(180,180,180,80)`) — the thicker separator between unread and read groups.
- [ ] **P7.6.4** Add `boundary_separator_thickness: int` setting (default **2**, range 1–6).
- [ ] **P7.6.5** In `_paint_emails()`, replace hard-coded pens with `QPen(separator_color, separator_thickness)` and `QPen(boundary_color, boundary_thickness)`.
- [ ] **P7.6.6** In `widgets_tab_gmail.py`, add a "Separators" bucket with two colour swatches + two thickness spinners.

---

### 4.7 Per-Element Font Controls — Header, Subject, Time, Sender Should Be Independent

**Problem:** The widget currently uses a single `self._font_family` + `self._font_size` for everything. Header uses `self._header_font_pt` but still the same family. Subject, sender, and time all share the same base font.

**Implementation Detail:**
- [ ] **P7.7.1** Add `header_font_family: str` setting (default inherits widget font family).
- [ ] **P7.7.2** Add `header_font_size: int` setting (already partially exists as `self._header_font_pt`; promote to full setting).
- [ ] **P7.7.3** Add `header_font_weight: str` setting (default `"Bold"`, choices: `Light`, `Normal`, `Bold`, `Black`).
- [ ] **P7.7.4** Add `subject_font_family: str` setting (default inherits widget font family).
- [ ] **P7.7.5** Add `subject_font_size: int` setting (default = widget font size).
- [ ] **P7.7.6** Add `subject_font_weight: str` setting (default `"Normal"`, choices: `Light`, `Normal`, `Bold`, `Black`).
- [ ] **P7.7.7** Add `sender_font_family: str` setting (default inherits widget font family).
- [ ] **P7.7.8** Add `sender_font_size: int` setting (default = widget font size − 1).
- [ ] **P7.7.9** Add `sender_font_weight: str` setting (default `"Normal"`, choices: `Light`, `Normal`, `Bold`, `Black`).
- [ ] **P7.7.10** Add `time_font_family: str` setting (default inherits widget font family).
- [ ] **P7.7.11** Add `time_font_size: int` setting (default = widget font size − 2).
- [ ] **P7.7.12** Add `time_font_weight: str` setting (default `"Normal"`, choices: `Light`, `Normal`, `Bold`, `Black`).
- [ ] **P7.7.13** Update `GmailWidget.__init__` / `apply_settings()` to read all new font keys.
- [ ] **P7.7.14** Update `_paint_header()` to use `QFont(self._header_font_family, self._header_font_size, header_weight)`.
- [ ] **P7.7.15** Update `_paint_emails()` subject line to use `QFont(self._subject_font_family, self._subject_font_size, subject_weight)`.
- [ ] **P7.7.16** Update `_paint_emails()` sender line to use `QFont(self._sender_font_family, self._sender_font_size, sender_weight)`.
- [ ] **P7.7.17** Update `_paint_emails()` time stamp to use `QFont(self._time_font_family, self._time_font_size, time_weight)`.
- [ ] **P7.7.18** In `widgets_tab_gmail.py`, add a "Fonts" bucket with family dropdowns + size spinners + weight combo boxes for Header, Subject, Sender, and Time.

---

### 4.8 Per-Element Colour Controls — Unread vs Read, Date, Header, Subject, Sender, Time

**Problem:** Only a single `self._text_color` exists. Unread emails are distinguished by `QFont.Weight.Bold` only — there is no colour differentiation. Date/time uses the same colour as everything else.

**Implementation Detail:**
- [ ] **P7.8.1** Add `header_text_color: QColor` setting (default inherits `self._text_color`).
- [ ] **P7.8.2** Add `subject_color_unread: QColor` setting (default `self._text_color` — bright).
- [ ] **P7.8.3** Add `subject_color_read: QColor` setting (default `self._text_color.darker(140)` — dimmed).
- [ ] **P7.8.4** Add `sender_color_unread: QColor` setting (default inherits `subject_color_unread`).
- [ ] **P7.8.5** Add `sender_color_read: QColor` setting (default inherits `subject_color_read`).
- [ ] **P7.8.6** Add `time_color: QColor` setting (default `self._text_color.darker(120)`).
- [ ] **P7.8.7** In `_paint_header()`, use `header_text_color` for "Gmail (N)" text.
- [ ] **P7.8.8** In `_paint_emails()`, set subject pen to `subject_color_unread` if `email.is_unread`, else `subject_color_read`.
- [ ] **P7.8.9** In `_paint_emails()`, set sender pen to `sender_color_unread` if `email.is_unread`, else `sender_color_read`.
- [ ] **P7.8.10** In `_paint_emails()`, set time pen to `time_color`.
- [ ] **P7.8.11** In `widgets_tab_gmail.py`, add a "Colours" bucket with swatches for Header, Unread Subject, Read Subject, Unread Sender, Read Sender, and Time.

---

### 4.9 Text Truncation Limits — Maximum Sender Length and Maximum Subject Length

**Problem:** Sender and subject elision widths are hard-coded (sender `max(150, available_width // 3)`; subject `available_width - time_width - sender_width - env_width - 30`). The user wants explicit max-length controls.

**Implementation Detail:**
- [ ] **P7.9.1** Add `max_sender_chars: int` setting (default **24**, range 10–60).
- [ ] **P7.9.2** Add `max_subject_chars: int` setting (default **48**, range 20–120).
- [ ] **P7.9.3** Replace hard-coded `max_sender_width` logic with `sender_fm.horizontalAdvance("W" * max_sender_chars)` as the cap, or use `QFontMetrics.elidedText()` with a pixel limit derived from `max_sender_chars`.
- [ ] **P7.9.4** Replace hard-coded `subject_max_width` logic with `subject_fm.horizontalAdvance("W" * max_subject_chars)` as the cap, then clamp by available layout width.
- [ ] **P7.9.5** In `widgets_tab_gmail.py`, add a "Truncation" bucket row with two spinners.

---

### 4.10 Settings UI Reorganisation — Styled Collapsible Buckets

**Reference:** The visualiser builder tabs use nested `QGroupBox` containers created via `style_group_box()` (`ui/tabs/shared_styles.py`), each with a title, vertical layout, and `setCheckable(True)` for collapsibility. Examples in `widgets_tab_media.py:509–628` ("Visualizers" group containing "Beat Visualizer" sub-group) and `widgets_tab.py` (visualiser technical buckets with persisted expand/collapse state).

**Implementation Detail:**
- [ ] **P7.10.1** Import `QGroupBox` in `widgets_tab_gmail.py` (already present).
- [ ] **P7.10.2** Create top-level `QGroupBox("Gmail Widget")` already exists — keep it as the outer shell.
- [ ] **P7.10.3** Inside the outer group, create collapsible sub-buckets (each is a `QGroupBox` with `style_group_box()` applied):
  - **"Backend & Auth"** — backend combo (IMAP vs OAuth), IMAP email/password + Save & Test, OAuth info label + Authorise button, shared Account status + Sign Out button.
  - **"Position & Size"** — position dropdown, min width, max width, content padding left/right/top spinners.
  - **"Visibility"** — show sender, show subject, show envelope, show timestamp, show separators, show three-dot menu, show unread count in header, auto title-case, desaturate when no unread.
  - **"Header"** — show header border checkbox, header font family/size/weight, header text colour swatch.
  - **"Fonts"** — per-element font controls (Subject, Sender, Time) with family/size/weight rows. Header font can be grouped here or in Header bucket.
  - **"Colours"** — unread/read subject colour, unread/read sender colour, time colour.
  - **"Separators"** — separator colour + thickness, boundary colour + thickness.
  - **"Truncation"** — max sender chars, max subject chars.
  - **"Sound"** — enable sound, volume slider, file path + test button.
- [ ] **P7.10.4** Each bucket must use `style_group_box(bucket)` from `shared_styles.py` for consistent dark theming, rounded corners, and title styling.
- [ ] **P7.10.5** Add `setCheckable(True)` and `setChecked(True)` on each bucket so users can collapse sections they do not need.
- [ ] **P7.10.6** Persist bucket collapse states via `SettingsManager` (following visualiser bucket state pattern in `widgets_tab.py` lines 197–198, 307–336).
- [ ] **P7.10.7** Ensure tab layout uses `QVBoxLayout` with `setSpacing(12)` between buckets — matching visualiser tab density.
- [ ] **P7.10.8** Move all existing flat rows (position, limit, refresh, filter, show_* toggles, colours) into their respective buckets. Do not duplicate controls.
- [ ] **P7.10.9** The backend selector (IMAP vs OAuth) and auth buttons must remain prominent at the top of the tab even when buckets are collapsed — place the "Backend & Auth" bucket first and default it to expanded.

---

## 5. Security Anti-Leak Policy & Credential Hygiene

**Goal:** Ensure zero credential material ever enters the repository, build artifacts, or logs.

### 5.1 Repository-Level Guards

- [ ] **S1.1** `.gitignore` must contain `**/client_secrets.json`, `**/gmail_token*`, `**/gmail_credentials*`, `**/*.pickle` (catch all pickle, not just Gmail).
- [ ] **S1.2** *(Optional / future)* Add a `pre-commit` guard that greps for `"client_id"` / `"client_secret"` patterns in non-archive Python files. The repository currently has no pre-commit infrastructure; implement only if CI is added later.
- [ ] **S1.3** `client_secrets.json` path must be runtime-resolved only; no `pathlib.Path(__file__).parent / "client_secrets.json"` patterns that could be committed.
- [ ] **S1.4** Add `GmailConfigError` string + Gmail credential file patterns to `Docs/Guardrails.md` under "Mandatory — Every Commit" section (credential leakage prevention).
- [ ] **S1.4b** Add `gmail_cache.json` and all files under `%APPDATA%/SRPSS/cache/` to `.gitignore` (if not already covered by broader `cache/` patterns). Ensure email cache is never committed.

### 5.2 Runtime Leak Prevention

- [ ] **S1.5** `GmailOAuthManager` must never log the `client_secret` value, even at `DEBUG`. Log only that credentials were loaded, not their content.
- [ ] **S1.6** *(Optional)* Token file may have `FILE_ATTRIBUTE_HIDDEN` on Windows. DPAPI encryption is the primary protection; ACL/Hidden flags are defense-in-depth and not required for MVP.
- [ ] **S1.7** On widget/auth failure, the error status text / UI message must never display the `client_id`, `redirect_uri`, or token file path to the user (paths can leak machine info). Use generic messages: "Gmail credentials missing. See log." No tooltips — they are banned in this project (overpaint, performance).
- [ ] **S1.8** `EmailMetadata` must never include `body` or `snippet` fields — metadata-only by design. Add a dataclass `__post_init__` assert if needed.
- [ ] **S1.9** `gmail_client.py` request logging must sanitize `message_id` from URLs? No — message IDs are not sensitive. But ensure no `body` / `raw` params are ever in the URL or logged.
- [ ] **S1.10** If token refresh fails with `invalid_grant`, the manager must auto-clear local credentials (encrypted token deleted) and require re-auth. Do not retry indefinitely with a stale refresh token.

### 5.3 Build / Distribution Safety

- [ ] **S1.11** Build script (PyInstaller / cx_Freeze) must verify `client_secrets.json` is **not** bundled into the executable unless explicitly injected at build time. If it is bundled, it is exposed to binary extraction.
- [ ] **S1.12** Document in `README.md` that `client_secrets.json` is a runtime dependency placed by the user (or build script) into `%APPDATA%/SRPSS/`.
- [ ] **S1.13** If distributing, consider using a backend proxy for token exchange instead of Desktop app client secret. This is the only way to keep the secret truly secret. Mark as **Phase 2 / future work**.

---

## 6. Paint & Performance Guardrails

**Goal:** Prevent the Gmail widget from becoming a CPU/GPU hog via unnecessary paint events, per-frame allocations, or unbounded email list growth.

### 6.1 Paint Event Discipline

- [ ] **PG1.1** `paintEvent()` must be pure — no network calls, no file I/O, no token refresh. All data must be pre-fetched and stored in widget attributes before `update()` is called.
- [ ] **PG1.2** Email list must be capped at `limit` (default 5, max 10) **at fetch time**, not at paint time. Never paint more rows than configured.
- [ ] **PG1.3** `QPainter` state changes (font, pen, brush) must be minimized. Set font once at start of email section, not per-row.
- ~~**PG1.4**~~ *Removed — premature optimization for 5-10 rows. Per-row state changes are negligible. Current per-row painting is readable and correct.*
- [ ] **PG1.5** Envelope pixmap must be **cached at scale** once when `limit` or widget geometry changes, not in `paintEvent`. Cache key = `(envelope_path, target_width, target_height)`.
- [ ] **PG1.6** Gmail logo pixmap must be cached identically. Reload only on explicit `reload_assets()` call or widget resize.
- [ ] **PG1.7** Use `QStyleHints` / `QFontMetrics.horizontalAdvance()` once and cache results; do not re-measure strings per frame.
- [ ] **PG1.8** Hit rects (`_email_hit_rects`, `_action_hit_rects`) must be recomputed only on data change or resize, not per `paintEvent`.
- [ ] **PG1.9** `update()` must not be called from `paintEvent` (infinite recursion trap). Use `QTimer.singleShot(0, self.update)` only if absolutely necessary.

### 6.2 Geometry & Visibility Guards

- [ ] **PG1.10** If widget `isHidden()` or parent `DisplayWidget` is not in overlay-visible state, `paintEvent` should early-return after logging a single WARNING (not spam).
- [ ] **PG1.11** Email fetch timer must be stopped when widget is hidden (power saving). Resume on show.
- [ ] **PG1.12** `QMenu` created in `_show_action_menu()` should be created per-click (standard Qt pattern), parented to the widget, and all references cleared in `cleanup()` to avoid dangling pointers. Avoid singleton menus with dynamically swapped actions — they are harder to reason about and more error-prone.

### 6.3 Memory Pressure

- [ ] **PG1.13** `EmailMetadata` objects must not hold references to `GmailClient` or `QPixmap`. Keep them plain dataclasses.
- [ ] **PG1.14** If email list fetch returns > `limit`, truncate immediately. Do not store unbounded lists.

---

## 7. Transition Deferral & ThreadManager Integration

**Goal:** Prevent email refresh/network I/O from stalling the UI thread during screen transitions (photo crossfades, visualizer mode switches, etc.).

### 7.1 Fetch Timing Policy

- [ ] **TD1.1** Email refresh must use `ThreadManager.submit_io_task()`, never the UI thread.
- [ ] **TD1.2** Results must be applied via `ThreadManager.invoke_in_ui_thread(lambda: self._apply_fetched_emails(data))`.
- ~~**TD1.3-TD1.4**~~ *Simplified — `invoke_in_ui_thread()` already queues safely on the Qt event loop. No transition-aware buffering needed; `update()` from an overlay widget during a transition is normal and lightweight.*
- ~~**TD1.5**~~ *Removed — ±10% jitter for a 5-minute timer is not worth the complexity. Single widget, no thundering herd.*
- [ ] **TD1.6** If a fetch is already in-flight when the timer fires again, skip the new fetch. Use an `atomic bool` or `threading.Lock()` to guard `_fetch_in_progress`.
- [ ] **TD1.7** On widget `stop()` / `cleanup()`, cancel any in-flight future (if `ThreadManager` supports it) or at least set `_cancelled = True` so the callback ignores stale results.

### 7.2 OAuth Flow Timing

- [ ] **TD1.8** The initial OAuth browser-launch + local server callback should use `ThreadManager.submit_io_task()` for the server. The URL open (`webbrowser.open()` / `open_url()` / bridge enqueue) is thread-safe and can be called directly from the IO task — no need to bounce through UI thread invoke.
- [ ] **TD1.9** Local server timeout (5 min) must be a `threading.Timer` or `socket.settimeout()`, not a busy-wait. Shutdown the server socket immediately upon receiving the callback to free the port.

---

## 8. AV False Positive Avoidance

**Goal:** Prevent Windows Defender or other AV from flagging the screensaver due to Gmail-specific behavior patterns.

### 8.1 Behavioral Patterns to Avoid

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

### 8.2 Build Artifact Hygiene

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
- [x] OAuth scope is `gmail.metadata` (RESTRICTED — requires CASA audit for public apps; stays in Testing mode). ALL Gmail read scopes are Restricted; `gmail.metadata` is the lightest option for sender/subject extraction. IMAP path requires no scopes or Google Cloud project.
- [ ] No message body content ever logged or stored.
- [ ] URL launching goes through secure-desktop bridge in `.scr` mode.
- [ ] `GmailConfigError` raised early if credentials missing (fail-closed).
- [ ] `clear_local_credentials()` available for user-initiated revocation.

## Appendix D: OAuth Consent Screen & Verification Notes

Because `gmail.metadata` is a **restricted scope**, Google requires CASA audit for public use. The IMAP backend requires no Google Cloud project at all.

- **Testing mode:** Works indefinitely for up to 100 test users. Refresh tokens expire every 7 days. **Sufficient for a dev-gated personal feature.**
- **Publish mode:** Requires privacy policy, Terms of Service, and a YouTube video demonstrating scope usage. Refresh tokens do not expire. Only needed if distributing to non-developer users.
- **Recommendation:** Stay in Testing mode. Document this limitation in `README.md` or `Docs/Gmail_Widget.md`.

---

## Appendix E: Threading & Concurrency Audit Findings

**Date:** 2026-04-27
**Audited files:** `gmail_oauth.py`, `gmail_imap.py`, `gmail_client.py`, `gmail_backend.py`, `gmail_widget.py`, `widgets_tab_gmail.py`
**Goal:** Identify race conditions, memory leaks, raw threading, and UI-thread blocking.

### E.1 Executive Summary

**7 Critical, 5 High, 6 Medium, 4 Low.** Raw `threading.Lock()` / `threading.Thread()` and `QTimer` usage is pervasive. The widget spawns raw background threads that touch Qt state without `run_on_ui_thread()`. DPAPI encryption and IMAP network calls happen on the UI thread, causing hangs.

---

### E.2 Critical Issues — Must Fix Before Release

| # | File | Line (approx) | Issue | Fix |
|---|------|---------------|-------|-----|
| 1 | `gmail_widget.py` | 60–61 | Raw `QTimer` for refresh timer. | Replace with `ThreadManager` periodic scheduling or register `QTimer` via `ResourceManager`. |
| 2 | `gmail_widget.py` | 457 | `threading.Thread(target=self._fetch_thread).start()` — raw thread. | Use `ThreadManager.submit_io_task()` for background fetch. |
| 3 | `gmail_widget.py` | 457 | `_fetch_thread` calls `self.update()` and `self._request_fade_in()` from non-UI thread without `ThreadManager.run_on_ui_thread()`. | Wrap all Qt calls in `run_on_ui_thread()`. |
| 4 | `gmail_widget.py` | 457 | `_fetch_thread` sets `_emails`, `_unread_count`, `_has_displayed_valid_data` from background thread; `paintEvent` reads them from UI thread — data race on plain attributes. | Update shared state via `run_on_ui_thread()` or use `queue.SimpleQueue` for results. |
| 5 | `gmail_oauth.py` | 48 | `self._lock = threading.Lock()` — raw lock. | Replace with `ThreadManager` lock abstraction or queue-based coordination. |
| 6 | `gmail_oauth.py` | 94 | `threading.Thread(target=self._wait_for_auth).start()` — raw thread for OAuth callback server. No cancel/kill path if user closes settings. | Use `ThreadManager.submit_io_task()`; add `threading.Event` for cancellation and `server.shutdown()` cleanup. |
| 7 | `gmail_backend.py` | 28–29 | `_instance_lock = threading.Lock()`, `_init_lock = threading.Lock()` — raw locks in singleton. | Replace with `ThreadManager` lock or `threading.Lock` only if no Qt dependency. |
| 8 | `gmail_client.py` | 56 | `self._lock = threading.Lock()` — raw lock (same pattern as oauth/imap). | Same fix as #5. |

---

### E.3 High Issues — Should Fix Before Release

| # | File | Line (approx) | Issue | Fix |
|---|------|---------------|-------|-----|
| 9 | `gmail_oauth.py` | 130–131 | `HTTPServer` runs on raw thread with no `server_timeout`, no `shutdown()` call, no cleanup path. Thread leaks every auth attempt. | Add `socketserver.ThreadingHTTPServer` with explicit `server.shutdown()` + `server.server_close()` in finally block. Track server instance for cleanup. |
| 10 | `gmail_widget.py` | 457 | `_fetch_thread` catches exceptions but only logs — no UI notification. Widget stays in "loading" state forever on failure. | On exception, call `run_on_ui_thread(self._on_fetch_error, exc)`. |
| 11 | `gmail_imap.py` | 153 | `import re` inside `_fetch_message_metadata()` — re-imported on every message fetch. | Move `import re` to top of file. |
| 12 | `gmail_backend.py` | 205 | `_last_error` set in `_on_error()` without lock. `last_error` property (line 73) reads without lock. | Wrap `_last_error` access in `ThreadManager` lock or use `threading.Lock`. |
| 13 | `gmail_backend.py` | 179 | `_last_unread_count` set in `_update_unread_count()` without lock. `unread_count` property (line 83) reads without lock. | Same fix as #12. |

---

### E.4 Medium Issues — Fix Before Stable

| # | File | Line (approx) | Issue | Fix |
|---|------|---------------|-------|-----|
| 14 | `gmail_backend.py` | 117–120 | `_backend_mode`, `_imap_client`, `_oauth_client` swapped without lock. A concurrent `refresh()` could read `_backend_mode='imap'` but `_imap_client=None` briefly. | Use a single `threading.Lock` around backend swap, or use atomic reference assignment if possible. |
| 15 | `gmail_backend.py` | 167 | `_refresh()` spawns raw `threading.Thread` for IMAP `get_unread_count()` / `list_messages()`. | Use `ThreadManager.submit_io_task()`. |
| 16 | `widgets_tab_gmail.py` | ~840 | `save_gmail_settings()` encrypts password with DPAPI on UI thread. Blocks settings dialog. | Offload `encrypt_data()` to `ThreadManager.submit_io_task()`. Update status label via `run_on_ui_thread()`. |
| 17 | `widgets_tab_gmail.py` | ~700 | `_test_gmail_connection()` calls `imap_client.test_connection()` directly on UI thread — network I/O blocks dialog. | Offload to `ThreadManager.submit_io_task()`. Update result label via `run_on_ui_thread()`. |
| 18 | `widgets_tab_gmail.py` | ~630 | `_save_and_test_credentials()` does encrypt + IMAP login on UI thread. | Same fix as #16 + #17. |
| 19 | `gmail_widget.py` | ~545 | `QMenu` created in `__init__` but only deleted in `cleanup()`. If widget destroyed without `cleanup()`, `QMenu` leaks. | Register `QMenu` with `ResourceManager`, or connect `destroyed` signal to `cleanup()`. |

---

### E.5 Low Issues — Polish

| # | File | Line (approx) | Issue | Fix |
|---|------|---------------|-------|-----|
| 20 | `gmail_oauth.py` | 62 | `self._password` stores decrypted App Password as plain string instance variable. | Clear string after use if possible (defence in depth). |
| 21 | `gmail_imap.py` | 62 | Same as #20 — plain string password in memory. | Same fix. |
| 22 | `gmail_oauth.py` | ~200 | `_token` dict accessed without lock in `is_authenticated` property. | Wrap in `_lock` if lock is kept, or use `ThreadManager` atomic. |
| 23 | `gmail_widget.py` | ~180 | `_current_hover_index` is plain int, written in `mouseMoveEvent` and read in `paintEvent` — both UI thread, safe, but brittle if refactored. | Document thread assumption or use `threading.local()` if refactored to multi-thread. |
| 24 | `gmail_widget.py` | ~60 | `_sound_player` instantiated but never explicitly stopped/disconnected in `cleanup()`. | Stop player and disconnect signals in `cleanup()`. |

---

### E.6 Implementation Plan — Fix Order

- [ ] **gmail_widget.py** — Replace raw `QTimer` + `threading.Thread` with `ThreadManager`.
         - Use `ThreadManager.submit_io_task()` for `_fetch_thread`.
         - Use `ThreadManager.run_on_ui_thread()` for `update()`, `_request_fade_in()`, `_set_emails()`, `_set_error()`.
         - Register `_refresh_timer` with `ResourceManager` or use `ThreadManager` periodic scheduling.

- [ ] **gmail_oauth.py** — Replace raw `threading.Lock` + `threading.Thread` with `ThreadManager`.
         - Replace `_lock` with `ThreadManager` lock abstraction or queue-based coordination.
         - Use `ThreadManager.submit_io_task()` for OAuth callback server.
         - Add `threading.Event` for cancellation and `server.shutdown()` cleanup.

- [ ] **gmail_backend.py** — Replace raw locks and threads with `ThreadManager`.
         - Use `ThreadManager` lock for `_instance_lock` / `_init_lock` (or keep `threading.Lock` if no Qt dependency).
         - Wrap `_backend_mode` / `_imap_client` / `_oauth_client` swap in lock.
         - Use `ThreadManager.submit_io_task()` for `_refresh()`.
         - Use lock for `_last_error` and `_last_unread_count` access.

- [ ] **gmail_client.py** — Replace raw `threading.Lock` with `ThreadManager` lock.
         - Same pattern as `gmail_oauth.py`.

- [ ] **gmail_imap.py** — Move `import re` to top of file.
         - Ensure thread safety of `_password` access (defence in depth).

- [ ] **widgets_tab_gmail.py** — Offload DPAPI + network to `ThreadManager`.
         - `save_gmail_settings()`: offload `encrypt_data()`.
         - `_test_gmail_connection()`: offload `test_connection()`.
         - `_save_and_test_credentials()`: offload encrypt + login.
         - All UI updates via `run_on_ui_thread()`.

- [ ] **gmail_widget.py** — Resource cleanup.
         - Register `QMenu` with `ResourceManager` or connect `destroyed` signal.
         - Stop `_sound_player` and disconnect signals in `cleanup()`.

---
