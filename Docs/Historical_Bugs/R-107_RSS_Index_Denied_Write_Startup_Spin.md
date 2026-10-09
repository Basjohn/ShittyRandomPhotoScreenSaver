# R-107 | RSS index denied-write startup spin

**STRONG RETENTION VALUE DOCUMENT**

Status: **FIXED IN CODE**

The MC process could consume a core before RUN started when its profile cache was not writable. `RSSCache._write_state`
used Windows `tempfile.NamedTemporaryFile`: its underlying helper retries `PermissionError` while the directory exists
and `os.access` reports write access. A sandbox denial can disagree with that ACL check. On the observed Python 3.11
installation the retry limit was 2,147,483,647, so neither the failure log nor the product's post-start `--exit-after`
timer could be reached.

A read-only stack of the affected child confirmed `_mkstemp_inner -> NamedTemporaryFile -> RSSCache._write_state ->
load_from_disk -> warm_cache -> ScreensaverEngine._build_image_queue`. The preserved matrix under
`logs/run_matrix/mc_capture_checkpoint_20261007/` is an aborted startup, not RUN or shutdown acceptance evidence.

The canonical cache owner now performs one unique exclusive temporary-file creation in the same state directory and
atomically replaces `pool.json`. Failure logs immediately, preserves the last-good index and removes any temporary file
this write actually created. There is no retry loop, alternate cache path or startup/shutdown timeout workaround.

`tests/test_rss_cache_atomic_write.py` protects single-attempt denial, last-good preservation, owned-file cleanup after
replacement failure and successful canonical payload round-trip. Normal MC acceptance remains in `Current_Plan.md`.
