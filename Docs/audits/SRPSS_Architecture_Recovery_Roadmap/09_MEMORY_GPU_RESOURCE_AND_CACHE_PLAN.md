# 09 — RAM, VRAM, GPU Resource, and Cache Plan

## Evidence

The baseline can climb toward approximately:

- 1.5–1.8 GB RSS;
- 4–5 GB private commit;
- 1.8–1.9 GB dedicated VRAM.

The donor branch often keeps VRAM closer to a bounded region, but still uses hundreds of megabytes and does not solve CPU/presentation behavior.

A dual-2560×1440 setup does not inherently justify gigabytes of application-owned live texture data.

## Resource accounting first

Every application-owned representation must be tracked.

### CPU representations

- encoded file bytes, if cached;
- decoded source image;
- orientation-corrected image;
- crop/scale result;
- upload buffer;
- thumbnails/previews;
- metadata artwork;
- retained `QImage`;
- `QPixmap`.

### GPU representations

- base texture;
- transition source texture;
- transition destination texture;
- visualizer FBO(s);
- intermediate transition FBO;
- PBO/upload staging buffer;
- overlay texture;
- shader/program buffers;
- retained fallback frame.

For each resource record:

```text
id
kind
owner
source identity
transform identity
display/share group
runtime generation
context generation
width
height
format
byte size
lease count
created_at
last_used_at
deletion_reason
```

## Byte formulas

For uncompressed RGBA8:

```text
bytes = width × height × 4
```

A 2560×1440 RGBA8 buffer is approximately 14.06 MiB.

Two displays with source and destination textures require approximately:

```text
2 displays × 2 textures × 14.06 MiB ≈ 56.25 MiB
```

Additional FBOs, staging, driver overhead, and caches increase this, but application-owned live resources should remain explainable.

## Initial resource budgets

These are provisional engineering gates, not immutable product limits.

### Dedicated VRAM

For two 2560×1440 displays:

- preferred steady-state application contribution: **under 300 MiB**;
- warning threshold: **400 MiB**;
- hard investigation gate: **500 MiB**;
- absolutely no monotonic growth across image cycles.

Higher-resolution or unusual effects must use formula-driven adjusted budgets.

### Process RAM

- preferred steady-state RSS after warmup: **under 600 MiB**;
- warning threshold: **750 MiB**;
- hard investigation gate: **900 MiB**;
- no multi-gigabyte private commit without an explained mapped/reserved source;
- no monotonic growth across image cycles or lifecycle cycles.

These targets may be revised only with evidence and a decision record.

## CPU image cache

Use a byte-budgeted cache, not count-only limits.

Cache key should include:

- canonical source identity;
- modification stamp/size or content version;
- transform/crop parameters;
- target dimensions;
- color/quality version.

Cache entries must be:

- immutable;
- byte-accounted;
- evictable when unpinned;
- free of GUI-only objects on worker-owned paths.

Avoid retaining all of:

- original decoded image;
- multiple scale variants;
- raw upload bytes;
- QPixmap;
- per-display duplicates;

unless each has measured benefit.

## GPU resource store

The registry/store must be metadata-first.

Responsibilities:

- lookup by explicit resource key and share group;
- lease acquisition/release;
- byte accounting;
- LRU eligibility;
- context-generation invalidation;
- scheduling deletion.

Non-responsibilities:

- making GL calls while locked;
- owning scene or transition state;
- image sequencing;
- retry loops;
- fallback presentation.

## Texture identity

Use stable metadata:

```text
source_id
source_version
transform_id
target_size
pixel_format
pipeline_version
```

Do not hash every decoded/upload byte by default.

Optional content hashing may be used:

- offline;
- for diagnostics;
- for uncertain external sources;
- after evidence proves cost acceptable.

## Upload path

Target one unavoidable upload-ready representation.

Avoid:

1. decode;
2. copy to bytes;
3. hash entire bytes;
4. copy into another payload;
5. copy into PBO;
6. upload.

Prefer ownership transfer or a single contiguous backing buffer where safe.

## Prefetch

Prefetch must be bounded by bytes and outstanding request count.

Rules:

- no unbounded future queue;
- cancel stale prefetch after sequence/settings change;
- do not decode many full-size images merely because workers are idle;
- reserve memory for active transition and current image;
- deprioritize or stop prefetch under memory pressure.

## Transition resources

At most the needed source and destination resources should remain leased for a normal transition.

After completion:

- destination becomes base;
- source transition lease releases;
- temporary FBO/PBO releases;
- no retained “just in case” frame without a documented bounded policy.

## Visualizer resources

Use only the buffers actually required.

Question every:

- double buffer;
- retained frame;
- prewarm FBO;
- fallback FBO;
- per-display duplicate.

If double buffering is necessary, account for it explicitly and prove why.

## Context recreation

On a new context generation:

- old handles are invalid;
- registry entries are removed or marked dead;
- deletion occurs before context destruction where possible;
- no old texture ID is reused by metadata alone;
- resource byte counters return to zero for the old generation.

## Memory tests

### Plateau test

- warm up;
- cycle images for 30 minutes;
- record tracked/untracked RAM and VRAM;
- require stable oscillation, not growth.

### Churn test

- alternate unusually large and small images;
- vary aspect ratios;
- force transitions;
- verify old sizes release.

### Lifecycle test

- 50 Settings/Edit cycles;
- verify return to same plateau.

### Pressure test

- apply conservative cache budget;
- verify eviction correctness;
- verify no decode storm or visualizer degradation.

## Leak triage

When process usage exceeds tracked bytes:

1. compare Qt image/pixmap caches;
2. inspect Python allocations;
3. inspect native allocations;
4. inspect driver-reported VRAM;
5. inspect deleted-but-pending GL resources;
6. inspect worker queues and retained futures;
7. inspect log buffers;
8. inspect thread stacks and object graphs.

Do not increase budgets to conceal unexplained memory.
