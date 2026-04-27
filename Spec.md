# Spec

Last updated: 2026-04-27

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
- Baseline/fallback contract: `visualizer_settings_contract.py`
- Runtime config application: `widgets/spotify_visualizer/config_applier.py`
- GPU state handoff: `widgets/spotify_bars_gl_overlay.py`

### 5.4 Mode isolation
- Mode-owned behavior belongs to mode-owned code.
- Shared seams must remain neutral and explicit.
- No hidden cross-mode dependency on authored mode keys.

## 6. Preset Architecture Contract
- Authored curated source: `presets/visualizer_modes/`.
- Runtime shipped trees are generated artifacts.
- Repair tool must normalize schema without rewriting authored intent.
- Reindex mutates only slot filename numbering and `preset_index`.

## 7. Startup Staging Contract
- Startup timing policy source: `rendering/overlay_startup_policy.py`.
- Spotify-related secondary-stage widgets must wait for anchor/position readiness before reveal.
- Mute button follows secondary-stage reveal contract.

## 8. Rendering and Input Contract
- GL-first rendering path with safe fallback behavior.
- Input routing is centralized; no widget-specific ad hoc global key/mouse handlers.
- Runtime interaction mode behavior must not break settings launch or shutdown paths.

## 9. Build Variants
- Standard saver and MC maintain separate settings profiles.
- Frozen preset resolution converges on shared ProgramData curated root.

## 11. Gmail Widget Architecture

### 11.1 Dev gating
- Gmail widget is gated by `--devgmail` CLI flag
- Gate state managed by `core/dev_gates.py`: `is_gmail_enabled()`, `force_gate(gmail=...)`
- Widget factory registration and rendering are gated by the flag

### 11.2 Backend routing
- Unified backend (`core/gmail/gmail_backend.py`) routes to OAuth/REST or IMAP based on config
- OAuth mode: `core/gmail/gmail_oauth.py` (PKCE flow, DPAPI token storage)
- IMAP mode: `core/gmail/gmail_imap.py` (App Password authentication)
- REST client: `core/gmail/gmail_client.py` (metadata-only API calls)

### 11.3 Widget contracts
- Overlay widget: `widgets/gmail_widget.py` (email list, actions, paint events)
- Widget components: `widgets/gmail_components.py` (GmailPosition enum, formatting, email cache)
- Settings UI: `ui/tabs/widgets_tab_gmail.py` (backend selector, credentials, widget settings)

### 11.4 Security invariants
- OAuth tokens stored encrypted via DPAPI
- API calls are metadata-only (no body/snippet content)
- No credential leakage in tests (all mocked with fake data)

## 12. Documentation Contract
- `Index.md`: module map.
- `Current_Plan.md`: active priorities only.
- `Docs/Guardrails.md`: policy/rules.
- `Docs/Historical_Bugs.md`: historical timeline and root-cause record.
