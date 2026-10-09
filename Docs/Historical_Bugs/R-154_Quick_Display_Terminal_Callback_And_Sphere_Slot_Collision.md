# R-154 | Retired QuickDisplayUnit signal retention and Sphere slot-1 conflict

**STRONG RETENTION VALUE DOCUMENT**

**Evidence:** October 9, 2026 diagnostic sessions (05:58–06:01, 06:03–14:00, 14:05–14:08), then source from the operator's `836e3aa7f5` Godzip, including R153.

## 1. Retired display Python owners survive terminal-barrier timeout

The lifecycle log records three destruction-barrier timeouts (two `monitor_topology`, one `application_exit`), all with `qobjects={}`, no generation resources, thread work, or global subscriptions, and only 1–2 `QuickDisplayUnit` Python owners outstanding. The bounded referrer diagnostic reported the single direct owner referrer as `QuickDisplayUnit._release_terminal_generation_references` (`builtins.compiled_method`). This is a **specific Python-owner signal-retention** problem, not evidence of a persistent renderer or GPU resource leak during the eight-hour single-display session.

### Source cause and correction

`QuickDisplayUnit.retire()` connected the runtime's `retirement_completed` Qt signal directly to `self._release_terminal_generation_references`. PySide's Python-callable signal bookkeeping could retain that bound method, which strongly references the Python-only display unit after the terminal QObject roots had drained. This defeats the destruction barrier's plain-Python weak-owner release check.

The signal now connects to a one-shot callback holding **only** `weakref.ref(unit)`. `DisplayManager._retiring_quick_units` remains the strong owner until `retirement_completed` fires, and the callback still executes the existing strict generation match and drops `_runtime` and `_presenter` **only on successful runtime completion**. No Qt barrier timeout, C++ deletion order, generational fail-closed semantics, render authority, GC policy or scheduling has changed. A new real-Qt regression test keeps the Python runtime wrapper alive after QObject teardown while freezing GC, then verifies the display unit is reclaimable by reference counting alone.

**Acceptance:** correction is implemented, but the Windows Qt regression and any physical monitor-topology acceptance remain pending. Do not claim the pre-existing lifetime incident cured without those results. Do not rerun the overnight diagnostic merely to close it.

## 2. Sphere preset-slot collision is external to shipped curated tree

Overnight runtime logs report:

```
[VIS_PRESETS] Duplicate curated slot for sphere preset 1: preset_1_mirror_ball.json overrides preset_1_glass_current.json
```

The handed-off source tree contains `sphere/preset_1_mirror_ball.json` **and** `sphere/preset_5_glass_current.json`, with matching filename/zero-based JSON `preset_index` values. It contains **no** `sphere/preset_1_glass_current.json`. The collision is therefore associated with a runtime preset root not contained in this Godzip (for example a diagnostic onefile extracted tree or shared ProgramData curated directory). The actual content of the extra file is **not supplied**, so its internal index and intended replacement slot cannot be asserted.

The curated loader intentionally prefers the **filename** slot over an embedded `preset_index`, and currently resolves multiple files for a slot by alphabetically sorted last-wins ordering. Filename vs payload schema disagreement alone doesn't manufacture a second file; an actual extra `preset_1_*.json` exists in the runtime directory. An earlier authoring/replacement or retained extraction asset is possible, not proven.

**R155 resolution (2026-10-09):** The overnight diagnostic was reading curated presets from its onefile extraction directory, where the extra `preset_1_glass_current.json` existed. This diagnostic-only root was contrary to the operator's intended shared preset authority. Frozen Diagnostic now resolves both curated presets and explicit overrides through the same ProgramData roots as Standard and Media Center. The temporary R154 read-only audit script and its test file were removed; no migration, deletion, forced reindex or authored-preset rewrite is performed. The old extraction assets are no longer consulted. This collision does not establish corruption of the active shared catalogue.

**Acceptance:** shared directory contract is implemented, awaiting focused Windows path verification; actual ProgramData authored JSON remains untouched.

## Scope exclusions

The reported 90 Hz versus 60 Hz observation is explicitly **off limits**. Do not change pacing/simulation or add investigations. Future transition/3D development is reserved for the operator's local-capable agent. No agents run Nuitka, Build Runner, installers or frozen products; the operator supplies their reports.
