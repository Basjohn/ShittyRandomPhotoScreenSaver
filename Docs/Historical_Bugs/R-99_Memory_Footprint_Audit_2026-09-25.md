# R-99 — Memory Footprint Audit (2026-09-25)

Date: 2026-09-25  
Status: PARTIAL / AWAITING VALIDATION. Four owners are fixed and measured on the real app (Linux, 4K); the Windows effect is confirmed through the built check's Phase 3. The lookahead depth awaits an operator decision.

## Classification

- [ ] COMPLETELY FUCKED
- [x] PARTIAL
- [ ] AWAITING VALIDATION
- [ ] SOLVED

## Scope And Method

The operator asked for a lower justified footprint with bounded long-term use and no performance cost. The historical ~500 MB was context, not a rollback target. The approach was an owner-by-owner audit of source plus the existing Windows evidence (the 2026-09-22..25 `--usage` and `--cache` logs), with targeted in-process measurements of the unmodified app on Linux/Xvfb: one 3840×2160 display, 5 s rotation, same 48 images, 5 minutes per run.

Two measurement traps to avoid next time:
- `gc.freeze()` (applied at 45 s) moves startup objects into the permanent generation, and `gc.get_referrers()` does not scan it. Holders created at startup (controllers, items, nodes) are therefore invisible after 45 s. Attribution runs must disable the freeze.
- Counting frames at arbitrary times mixes in transitions that are in flight. Retention must be sampled at a fixed phase, e.g. 1.5 s after each transition finalizes.

Linux private memory is inflated by glibc free-list retention and by Mesa's *software* GL, whose textures live in system RAM. Compare live `malloc` in-use and owner bytes, not Linux private.

## Waste Found And Fixed

### 1. Consumed derivatives lingered in the image cache (`d40a8949`)

After a display captured a scaled derivative into its `PresentationImage`, the cached `QImage` stayed at the LRU's most-recent end: the same frame twice. That entry then pushed out the nearer lookahead derivatives, which had to be decoded and scaled again. ImageWorker results were also cached for a reuse that almost never came.

In the Windows cache log:
- 1,167 of 2,377 prefetched 4K derivatives (49%) were evicted without use, and 1,196 of those images were shown later anyway;
- cached worker results were reused 1 time in 53.

The fix removes a derivative after capture and no longer caches worker results. Exact reuse is per batch.

Linux 4K, before → after:
- derivatives built: 67 → 36 for 33 → 31 consumed;
- evicted unused: 31 → 0; evictions: 61 → 0;
- cache: 190–221 → 158–190 MB (the lookahead only);
- live malloc: ~510–575 → ~480–520 MB.

About half of all speculative decode/scale work, the GIL-holding kind, disappears.

### 2. The parked transition node pinned the finished run (`fd7327e9`)

`RetainedBackgroundSceneNode` keeps its custom `BackgroundRenderNode` alive between transitions so the GL programs stay warm. Parking it did not drop `_transition_run` / `_presentation_image`, so the previous wallpaper (33 MB at 4K) stayed alive on every display until the next transition. After the fix, phase-locked sampling shows one frame per display.

### 3. numpy's OpenBLAS thread pool (`d350a379`)

At numpy import, OpenBLAS starts one worker thread per logical CPU. On Windows each thread commits its own buffer (32–64 MB, `VirtualAlloc(MEM_COMMIT)`) whether or not BLAS is used. The operator's CPU has 24 logical cores, so ≈ 23 threads and ≈ 700 MB of untouched commit per process.

The Windows evidence fits in both processes:
- **ImageWorker:** flat all night at ~816 MB private against ~155 MB resident. It imports numpy because `spawn` re-runs `main.py`'s top-level import graph.
- **Main process:** about 1.2 GB of its ~1.9 GB warm private commit is not resident.

The app's only BLAS use is tiny vector math in Glass shatter physics, which OpenBLAS never parallelizes; one thread measured faster there (median 18.0 → 14.5 ms). OpenBLAS reads its pool size only at load, from the environment, so `core/native_threads.py` sets it at the top of `main.py` and spawned workers inherit it. The bar asks the loaded OpenBLAS directly: 4 → 1 in the app process and in a spawn child on a 4-CPU box.

Expected on Windows (not yet observed):
- `private_children_mb` ~816 → ≲ 200;
- main warm private roughly −700 MB;
- ~46 fewer threads in `threads_app`.

### 4. A reference cycle on every settings read (`0958a277`)

`SettingsManager.get` defined a recursive closure per call (150 cycles per 150 reads) for the cyclic GC. It now uses the existing `_to_plain_value`.

## Legitimate And Kept

- The lookahead cache: bounded, and now lookahead only.
- One presentation frame per display.
- Transition textures while a transition runs.
- Prepared transition geometry: 6 entries, ~9 MB, bounded.
- ~35 MB of module code objects.
- The PyOpenGL wrapper tables (~6 MB).
- Qt Quick scenes per display.

## Open

- **Lookahead depth: decided 4 (operator, 2026-09-25).** On Windows (40 s median rotation) a consumed derivative was built a median 0.8 rotations ahead: 87% within two rotations and 97% within four. The canonical default moved 5 → 4 so the lookahead stays even across two displays instead of carrying one odd derivative that is likely to be wasted. It trims bounded cache, not the R-97 slope. Existing profiles keep their persisted value.
- **The ImageWorker imports the whole app** (~1,060 modules: engine, UI, Visualizer, Qt Quick) because `spawn` re-imports `main.py`'s top level. Its resident set could drop by ~100 MB with a lean worker entry. This needs Nuitka multiprocessing validation, so it is not changed blind.
- **The remaining non-resident main-process commit** is the NVIDIA OpenGL driver (2026-09-26 native maps, `tools/win_memory_map.py`): a write-combined upload pool that fills to a bounded ~360–480 MB on one 4K display, plus the driver's own heap. The heap's growth was R-97's slope, caused by thread churn and now fixed.
- The steady private-commit slope is still R-97.
- Small items (closed 2026-09-26):
  - The prefetch-resume callback re-armed itself from inside its own closure, leaving one garbage cycle per rotation. It is now a module-level function bound with `functools.partial`.
  - ctypes array types accumulated (~20 per 140 rotations on the Linux soak; 22 over 132 offscreen runs): Glass and Crumble mesh uploads built `c_float * n` for a per-run size, and ctypes caches one type per length forever. Uploads now pass plain `bytes` (0 new types over the same runs).
  - `linecache` holds ~5 MB of source text after traceback formatting. Not changed: each file is cached once, so the cost is fixed and bounded by the source size (not growth), and it is zero in the shipped Nuitka build, which contains no `.py` sources. Clearing it would mean touching every traceback formatter for a source-run-only 5 MB.

## Regression Coverage

- `tests/test_image_pipeline.py`: consumed derivatives leave the cache; worker results are not cached; each DPR consumes its own entry.
- `tests/test_qtquick_native_texture_handoff.py::test_parked_transition_node_pins_neither_frame`
- `tests/test_native_thread_pools.py`
- `tests/test_settings_manager.py::test_settings_reads_leave_no_reference_cycles`
- `tests/test_image_pipeline.py::test_prefetch_resume_leaves_no_reference_cycle_per_rotation`
- `tests/test_transition_upload_types.py`
