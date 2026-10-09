# R-151 | Same-destination Steam cache publication collision on Windows

**STRONG RETENTION VALUE DOCUMENT**

Date: 2026-10-09  
Status: **SOURCE REPAIR IMPLEMENTED / FOCUSED WINDOWS ACCEPTANCE PENDING**

## Evidence

Operator supplied `GODZIP_RUN_RESULTS_20261009_023049_20261009_041416_1fd2e5ab.zip`, covering a Python 3.14.8 R149 full test run before R150 was applied. Collection passed; chunks 1, 2 and 3 passed; chunk 4 finished **1 failed / 1,758 passed / 1 skipped**. The sole failed test was `tests/test_steam_cache.py::test_concurrent_cache_writers_use_distinct_owned_temp_files`, with `PermissionError: [WinError 5] Access is denied` at `core/steam/cache.py:99` when replacing the final `games_you_follow_news.json`. Chunk 3 independently reported **1,761 passed**. This is a same-destination Windows atomic-publish collision, distinct from the R149 fixed-name-temp-file bug. Other chunks' individual pass counts were not included in the operator's ZIP; do not invent them.

R150's targeted audio isolation suite independently passed **96 tests** on Windows, with three Python 3.14 `datetime.utcnow()` deprecation warnings. Those warnings are unrelated to the Steam error. The logs also include `comtypes` private-ctypes deprecations from a third-party dependency and the previously tracked Qt point-size warning. They are not fixed in this slice.

## Failure mechanism

R149 correctly gave each writer a unique, exclusively created `.json.*.tmp` file and retained the last-good final cache record on publication failure. On Windows, independently owned temporaries **do not** guarantee that two threads can safely invoke `Path.replace()` against the **same final destination concurrently**; the publication operations themselves need per-destination coordination. A Windows-denied destination held by another process (or by a reader without deletion sharing) is still a separate potential cause of `WinError 5/32` and is **not** claimed solved by an in-process mutex.

## R151 repair

- Keep staging each temporary file exclusively and concurrently.
- Serialize **only final `Path.replace()`** for the same normalized absolute destination in the same process; different destinations remain independent.
- Use one weak-value registry of publication locks, protected only while looking up/creating an entry. An unowned lock is collectable, avoiding permanent per-profile lock-map growth. No timer, retry, worker, global disk lock or new cache authority.
- On genuine denied publication, still log, clean only the calling writer's temporary and re-raise; last-good destination bytes remain unchanged. Do not weaken a denied-write failure to a false success.
- Add an instrumented Windows-style collision regression and a distinct-target progress test; keep R149's simultaneous distinct temp test and denied-publication test. Prove registry entries do not retain unused locks.
- Replace deprecated Settings `datetime.utcnow()` calls with aware UTC instants but preserve persisted `Z` suffix and legacy timestamp filename syntax; no migration-format change.

## Validation and acceptance

Local standalone Steam cache pytest (without PySide6) passes; Python files compile. The operator must run only the focused Windows tests `test_steam_cache.py`, `test_steam_games_followed_source.py`, `test_steam_followed_inline_news_artwork.py`, `test_settings_manager.py` and `test_settings_profile_separation.py`. **Do not request the full four-chunk suite again yet.** Once focused acceptance is clean, proceed to the already-planned MSVC/Nuitka frozen-product gate and physical Sphere/Shockwave audio observation. Full-suite acceptance of R151 is not asserted.
