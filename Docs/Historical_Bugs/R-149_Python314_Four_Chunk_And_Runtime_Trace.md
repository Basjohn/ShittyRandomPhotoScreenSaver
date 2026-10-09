# R-149 | Python 3.14 four-chunk and Windows runtime trace

Date: 2026-10-09  
Status: **SOURCE REPAIRS PREPARED / FULL WINDOWS FOUR-CHUNK AND FROZEN GATES NOT YET ACCEPTED**

## Evidence and scope

Operator supplied `GODZIP_RUN_RESULTS_20261009_015418_20261009_031659_395e4431.zip` and `logsbaa9d5ed9f.zip` from the freshly installed standard-GIL Python 3.14.8 / NumPy 2 / PySide6 6.11.2 environment. The earlier focused migration/source-contract gate independently reported **47 passed**. Full collection succeeded. The four approximately 700-second test chunks reported:

| Chunk | Passed | Failed | Errors | Skipped |
| --- | ---: | ---: | ---: | ---: |
| 1 | 1,755 | 6 | 0 | 0 |
| 2 | 1,750 | 10 | 14 | 0 |
| 3 | 1,755 | 5 | 14 | 0 |
| 4 | 1,754 | 5 | 0 | 1 |
| **Total** | **7,014** | **26** | **28** | **1** |

Error counts must not be reported as additional unique failures: the logging break cascaded into teardown. None of the source repairs below is a Windows regression pass. Preserve the distinction between an observed operator result, a local source-contract test, and an unrun physical gate.

## Genuine Python/native migration failure

- `core/logging/logger.py` depended on removed **private** `logging._acquireLock()` / `_releaseLock()` during closing-WARNING handoff. Under 3.14 the private names do not exist. R149 performs an atomic root-handler-list publication under the existing SRPSS logging-controller lock, preserving late WARNING+ delivery, queue shutdown bounds and the final sink. No new timer/thread/poller. Reinitializing `setup_logging()` now **explicitly resets each sidecar family enable flag** instead of accidentally preserving an earlier diagnostic session's flags. These are production changes, not assertions deleted to make tests green.
- NumPy 2's vendor-prefixed OpenBLAS binary exports invalidated the fixed-name DLL function probe. R149 uses `threadpoolctl` to inspect the **loaded** BLAS library's actual `num_threads`, including a spawned child. This preserves the one-thread/no-huge-stack-budget invariant instead of silently passing an unmeasurable probe. `threadpoolctl==3.6.0` is an explicit test/dev dependency; install with the normal requirements update, **not another destructive venv cutover**.

## Stale tests, corrected to reflect existing accepted behavior

- Nuitka wrapper scripts are now delegators. Packaging flags are asserted against their canonical `scripts/venv/` build workers; wrappers are separately required to delegate properly. Gmail, Qt Quick QML and Reddit Helper checks previously inspected the wrong file.
- R144 foreground-safe noop prefetch registration records a single empty registration to prune/resume pending intents; no work gets admitted. The image-pipeline test now asserts the empty call and zero prefetch jobs.
- R146 ordinary two-display timing is **400 ms**, not the former 800 ms. In the observed Qt Quick test, primary duration 275 ms yields secondary compensated duration **675 ms**.
- Freeform-3D native Alt-wheel resize is physically accepted **center anchored**. Its tests now protect horizontal **and vertical center**, not the obsolete top-edge anchor.
- CUSTOM target profile is resolved in the canonical visualizer failover lifecycle, not through the removed `DisplayManager.resolve_quick_custom_entry` monkeypatch. The dead injection was removed; real routing assertions remain.

Never pin operator-authored visualizer presets, regenerate historical image goldens from current authored values, or soften an actual rendering contract to satisfy a stale assertion.

## Separate real runtime error: Steam followed-game cache atomic write

At **03:50:02 local**, `core.steam.cache.write_cache_record()` failed a `Path.replace()` with **Windows error 32** while publishing `games_you_follow_news.json.tmp` to `games_you_follow_news.json`. The exception propagated from `games_followed_source.refresh()` to its `steam_games_followed` IO task. This is real production behavior, not a pytest failure.

The cache writer used **one fixed `.json.tmp` path for every concurrent write to the same cache key**. That makes one writer vulnerable to another writer creating, truncating or renaming its temporary file. R149 allocates one **UUID-named exclusively created temp file per write**, publishes with the same atomic replacement, and cleans up only that writer's own file. It does **not** add retry loops, cache schedulers, extra cache authorities or overwrite semantics. A failing Windows `replace()` still raises and preserves the prior record; an unrelated Windows process could still prevent final target replacement. Regression tests cover simultaneous temp-file ownership, complete valid final records, and last-good preservation/owned temp cleanup on denied rename.

## Runtime trace findings not to suppress

- `screensaver_spotify_vis.log` contains **189** suppressed `KeyError('Treble')` messages. In the Sphere session the Spectrum shaper receives Sphere analysis notch labels `Bass / Mid / Treble / End`, but the normal Spectrum strength profile doesn't necessarily own the `Treble` label. This is a **real latent Sphere/source-shaper configuration mismatch**, not an artistic preset problem. R149 does not rewrite operator-authored notch positions or invent fallback node strengths; investigate separately with mode-scoped, non-mutating DSP tests. The source of this issue is independent of the logging shutdown and Python wheel upgrade.
- `screensaver_qml.log` has **one** `QFont::setPointSize(-1)` warning; identify the caller before changing font/style contracts.
- Reddit `r/Games` RSS requests received intermittent HTTP **429**, with the old-HTML fallback reporting an empty listing. Treat as a provider/network response, not automatically as a Python migration regression.
- `native_faults.log` records capture start and clean end; there is no native fault captured in the supplied run.
- The independent Windows handle sidecar contains **36 samples across 35 minutes**. Startup: **1,535** handles; after the first two minutes the count stayed between **1,620 and 1,655** and ended at **1,653**. Thread handles after warm-up varied **82–88**, ending **85**; file handles **428–444**, ending **441**; section handles **385–386**, ending **385**. No continued accumulating handle or thread slope in this session. This does **not** certify unattended/overnight memory or lifetime behavior.

## Remaining acceptance

1. Apply the R149 full Godzip. Update the **existing** Python 3.14 `.venv` in place with `python -m pip install -r requirements.txt`; do not rerun `cutover_python314.ps1` or reinstall Python 3.11.
2. Re-run the focused logging, Steam cache, migration packaging/Qt Quick, prefetch and OpenBLAS probe tests, then the **complete four chunks** on Windows. Save failing logs verbatim. Do not weaken tests or freeze mutable operator presets.
3. Probe the Sphere/source-shaper `Treble` warning in a targeted synthetic, test-owned configuration, without changing operator-authored profiles. Close only when runtime trace is clean and normal modes retain their authored DSP semantics.
4. Run MSVC/Nuitka Standard, Diagnostic, Media Center and Reddit helper frozen product gates and a physical two-display/audio/close check; only then promote this Python 3.14 source cutover to accepted baseline.

**R150 follow-up:** The Sphere-only shaper invocation is corrected in `R-150_Sphere_Analysis_Only_Shockwave_Shaper_Audit.md`; full Windows acceptance remains pending. Shockwave is a legitimate Spectrum-shaper consumer for its authored horizon and is not disabled.
