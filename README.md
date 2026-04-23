# ShittyRandomPhotoScreenSaver (SRPSS)

Last updated: 2026-04-23

SRPSS is a Windows screensaver and media-center runtime focused on image rotation, GPU transitions, and overlay widgets.

## Highlights
- Multi-source image rotation (folders + RSS/JSON feeds).
- Multi-monitor rendering with GL-first transitions.
- Overlay widgets (clock, weather, media, Reddit, visualizer).
- Settings dialog with live apply and JSON persistence.
- Separate screensaver and media-center runtime profiles.

## Runtime Entrypoints
- `main.py` -> screensaver runtime.
- `main_mc.py` -> media-center runtime.

## Settings
- Canonical settings store: `%APPDATA%/SRPSS/settings_v2.json`.
- MC profile: `%APPDATA%/SRPSS_MC/settings_v2.json`.
- Settings API is provided by `core/settings/settings_manager.py`.

## Visualizer Notes
- Mode registry is centralized in `core/settings/visualizer_mode_registry.py`.
- Spline Curve is the user-facing name for internal id `devcurve`.
- Blob remains behind `-devblob`.

## Useful CLI Flags
- `--debug`, `-d`
- `--viz`
- `--viz-diagnostics`, `--viz-diag`
- `--fresh`
- `-devblob`
- `--devcurve` (compatibility no-op)

## Useful Environment Variables
- `SRPSS_ENABLE_DEV`
- `SRPSS_VIZ_DIAGNOSTICS`
- `SRPSS_PERF_METRICS`
- `SRPSS_FORCE_SOUNDDEVICE`
- `SRPSS_DISABLE_LOGGING`
- `SRPSS_FORCE_LOG_DIR`

## Development
- Canonical architecture: `Spec.md`
- Code map: `Index.md`
- Policies: `Docs/Guardrails.md`
- Defaults: `Docs/Defaults_Guide.md`
- Tests: `Docs/TestSuite.md`
- Visualizer contracts: `Docs/Visualizer_Reference.md`

## Packaging
- Installer scripts: `scripts/SRPSS_Installer.iss`, `scripts/SRPSS_MediaCenter_Installer.iss`.
- Version source: `versioning.py`.
