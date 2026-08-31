# Logging Guide

Last updated: 2026-08-31

## Purpose

Keep logs readable, attributable and cheap enough that diagnostics do not become the
workload they are measuring.

The human console may be fancy. The diagnostic record must remain boringly trustworthy.

## Main Contract

`screensaver.log` contains:

- high-level runtime narrative useful to an operator;
- **every WARNING, ERROR and CRITICAL from every family**;
- only routine INFO that genuinely belongs in the general sequence.

The main file is human-readable and may use aligned columns or framed severity cards.
That presentation layer must preserve the record's timestamp, logger, message payload,
visible tags and `key=value` content.

When a dedicated family sidecar is enabled, routine family INFO/DEBUG belongs in that
sidecar and should not duplicate into main. Sidecars retain the compact canonical
machine-oriented format.

`screensaver_verbose.log` remains the broad debug fallback, not the place agents should
read first when a dedicated sidecar exists.

## Debug Console Contract

Script/debug console output is an operator view, not an evidence authority.

Current console formatting may:

- adapt once to terminal width;
- align fixed time/level/source/message columns;
- align structured `key = value` tables;
- promote long values to full-width rows;
- use heavier WARNING/ERROR/CRITICAL cards;
- apply ANSI colour when the terminal supports it.

It may not:

- mutate the underlying `LogRecord`;
- change family routing;
- remove fields to look cleaner;
- become the only copy of a record;
- delay persistent file handling for the current dequeued record.

Raw `print()`/stdout written outside Python logging is outside this formatter contract.

## Always-On Qt / QML Diagnostic Plane

Qt/QML messages do **not** originate in the ordinary Python logging pipeline. A clean `screensaver.log` is therefore not sufficient Quick-runtime evidence.

`core/logging/qt_message_capture.py` installs one process-scoped Qt message handler before `QApplication` / `QQmlEngine` creation and writes a direct, bounded `screensaver_qml.log`. The capture remains alive through final Qt teardown.

The sidecar is always on, even when no optional logging flags are enabled. A successful install eagerly creates the file and writes `session_start`; final atexit writes `session_end` plus severity/category counts. This deliberately distinguishes a clean Qt/QML run from a failed/missing capture.

The Qt/QML sidecar records milliseconds, severity, PID, thread, sequence, category, source file/line/function when available, and message. It is synchronous/direct rather than routed through `SRPSSLogWriter`, because the channel exists specifically to retain Qt/QML diagnostics that may occur during queue saturation/closing/native failure.

For source-mode/installed Quick acceptance, inspect `screensaver.log` and `screensaver_qml.log` together. Unexpected migration-relevant QML binding/component/provider/signal/slot/scene warnings are first-class evidence.

Permanent capture tests: `tests/test_qt_message_capture_contract.py` (fake-handler contract) and `tests/test_qt_message_capture_qml_runtime.py` (real QQmlEngine warning path; requires PySide runtime).

The capture is **not** a process-level stderr redirect. Raw non-Qt native fd-2 writes remain outside ordinary release-file capture; Diagnostic `faulthandler` is a separate direct fatal plane. See `Docs/Qt_QML_Observability.md` before adding an OS-level stderr tee.

## Dedicated Families

Existing sidecars remain the first destinations for their domains:

- `--perf` → `screensaver_perf.log`, `perf_widgets.log`
- `--gpu-timing` → sampled owner-context GL timing in `screensaver_perf.log` and implies `--perf`
- `--usage` → `screensaver_usage.log`
- `--viz` → `screensaver_spotify_vis.log`, `screensaver_spotify_vol.log`
- `--geo` → `screensaver_geometry.log`
- `--set` → `screensaver_settings.log`
- `--life` → `screensaver_lifecycle.log`
- `--cache` → `screensaver_cache.log`
- `--steam` → `screensaver_steam.log`

Do not create a new sidecar merely because one logger is noisy. Add a family only when a
distinct high-volume domain has a coherent correlation workflow.

`[VIS_ROUTING]` is a bounded main-sequence INFO record emitted once when a `DisplayManager`
generation attempts to admit the single Visualizer. It records the persisted Visualizer/Media route,
CUSTOM decision, canonical effective monitor, requested screen, participant/binding-loss
set, current failover state, chosen unit and construction result/reject reason. It is not a
per-frame stream. A pending-grace result describes that initial decision; correlate it with
the existing `[VIS_FAILOVER]` lifecycle messages for later fallback/reclaim outcomes.

Ordinary `--perf` is the comparable CPU/frame/delivery profile. The heavier
`--gpu-timing` route is separate because GL query polling and begin/end calls can alter
paint cost. It samples one paint in eight and records coverage; use it only for an
owner-GPU causal question, never as an unnamed baseline.

## Rotation and Retention

Rotating runtime logs use **2 MiB chunks**.

Current intended retention profile:

| Log family | Ordinary retention | Diagnostic retention |
|---|---:|---:|
| `screensaver.log` | active + 7 backups ≈ 16 MiB | active + 11 backups ≈ 24 MiB |
| `screensaver_qml.log` | active + 3 backups ≈ 8 MiB | same; always-on direct Qt/QML plane |
| most enabled sidecars | active + 5 backups ≈ 12 MiB | normally the same unless listed below |
| `screensaver_usage.log` | active + 5 backups ≈ 12 MiB | active + 11 backups ≈ 24 MiB |
| `screensaver_lifecycle.log` | active + 5 backups ≈ 12 MiB | active + 11 backups ≈ 24 MiB |
| `screensaver_verbose.log` | active + 3 backups ≈ 8 MiB | same chunk/backup shape |

The purpose of extra Diagnostic retention is long soak/frozen-runtime reconstruction,
not performance comparison.

If a future capture loses useful history, prefer increasing the affected family's backup
count over making every individual rotation huge.

`diagnostic_crash.log` is a separate bounded direct crash channel and is not part of the
ordinary queued retention table.

## Cache Routing

The GL program-cache producer declares structured `cache` ownership. Its visible
`[GL CACHE]` text remains for people and parsers, but no longer controls routing.

Routine `[GL CACHE]` INFO belongs in `screensaver_cache.log` and is absent from main when
that sidecar is active. `[GL CACHE]` WARNING+ remains visible in both.

Unmigrated cache producers retain compatible token/name fallback. Do not regress them by
lowering useful records to DEBUG or deleting evidence.

## Execution Architecture

Normal logging uses one bounded process-owned queue/writer:

```text
caller thread
   -> cheap detached LogRecord enqueue
   -> SRPSSLogWriter
      -> family routing
      -> persistent main/sidecar formatting + dedup + rotation/write
      -> optional human console formatting/output
```

Persistent file handlers are serviced **before** the console handler for each dequeued
record. A slow terminal therefore cannot postpone the main/sidecar write for that record.

Requirements:

- caller path is small and normally non-blocking;
- bounded queue with high-water/drop telemetry and explicit overload policy;
- original timestamp plus monotonic/correlation ordering metadata survives;
- one writer owns normal file rotation/writes;
- shutdown exposes a bounded flush/close contract;
- fatal/native crash breadcrumbs and faulthandler output remain direct and independent of the queue.

Current implementation details:

- the root logger exposes one producer-facing ingress; real handlers and filters are writer-owned;
- `SRPSSLogWriter` survives Settings/Edit runtime-generation retirement and is not a `ThreadManager` task;
- queue capacity is 4096 records;
- DEBUG/INFO may drop only on saturation/closing and are counted by level;
- WARNING+ saturation uses the serialized direct-main emergency path and is never silently dropped;
- shutdown replaces queue ingress with a warning-only closing sink while writer finalization completes;
- persistent handlers are attempted before optional console output;
- `flush_logging()` is the bounded visibility barrier used before the exit PERF parser;
- `flush_and_close_logging()` is the supported ordinary-logging shutdown/reconfiguration API and runs before diagnostic crash-capture close;
- direct `logging.shutdown()` is not a substitute for the controller-aware drain/close contract.

### Final queue telemetry

The final `[LOG_QUEUE]` record reports:

- enqueue/dequeue counts;
- drops by priority;
- high-water and capacity;
- caller enqueue average/max;
- writer queue-lag average/max;
- file-commit lag average/max;
- console emit average/max;
- emergency/reentry fallback counts;
- snapshot/writer errors;
- bounded flush duration.

Interpretation:

- `writer_lag_*` measures time waiting for the writer to start the record;
- `file_commit_lag_*` measures time from enqueue until persistent outputs have been serviced;
- `console_emit_*` isolates human-terminal presentation cost.

These are passive diagnostics, not scheduling inputs.

## Crash and Abrupt-Failure Safety

Asynchronous normal logging cannot guarantee persistence of records still waiting in the
queue when the process is killed instantly.

The safety contract is therefore layered:

1. caller path remains cheap and bounded;
2. WARNING+ saturation has a serialized direct-main emergency path;
3. once the writer dequeues a record, persistent sinks are serviced before console output;
4. shutdown uses the bounded controller-aware drain/close contract;
5. Qt/QML messages are captured directly in `screensaver_qml.log`, independent of the normal queue;
6. Diagnostic fatal/native crash breadcrumbs and faulthandler output are direct and independent of both normal logging and the Qt/QML sidecar.

Do not "solve" abrupt-crash uncertainty by moving normal file I/O back onto render/UI
callers.

## Structured Family Metadata

SRPSS records may carry `srpss_log_families`, an immutable tuple because one record can
intentionally belong to multiple destinations such as `("perf", "cache")`.

Canonical families live in `core/logging/tags.py`. Bind them with
`get_logger(name, families=(...))`.

Valid explicit metadata is authoritative over logger-name and visible-token heuristics.
Absent or wholly unknown metadata falls back to existing name/tag routing so third-party
and unmigrated records remain compatible.

Human-readable tags such as `[PERF]`, `[CACHE]` and `[GL CACHE]` remain useful for people
and existing parsers, but newly migrated producers must not depend on them for delivery.

Late Phase 7 should migrate high-volume families systematically and simplify filters so
routing no longer depends on token quirks.

## Evidence Parser Compatibility

The main log's human presentation is allowed to evolve, but evidence parsing must remain
backward compatible.

The canonical parser contract is:

- old canonical main-log lines remain readable;
- framed WARNING/ERROR/CRITICAL cards normalize back to one logical record;
- presentation-only borders/rules do not pollute unknown-line output;
- family sidecars keep their canonical compact format and remain the primary structured evidence;
- rotation order and exact source/time-range semantics are preserved;
- parser changes are read-only and must pass focused parser tests before official evidence use.

Do not change sidecar schemas merely to make the main log prettier.

## Diagnostic Runtime

Diagnostic remains an opt-in frozen-runtime attribution product. It may enable all
families automatically and retain longer bounded usage/lifecycle/main history.

It is not a performance baseline, and ordinary work must not trigger a Diagnostic rebuild
unless a specific frozen-only failure requires it.

## Correlation Workflow

1. Read `screensaver.log` for the Python/runtime sequence and all ordinary WARNING+.
2. Read `screensaver_qml.log` over the same range for Qt/QML evidence.
3. Follow the owning family sidecar for routine domain detail.
4. Use shared timestamps/correlation ids to cross-reference perf/usage/lifecycle/cache/viz.
5. Use verbose only when the general + dedicated sidecars are insufficient.
6. For long captures, include the rotations that overlap the interval being claimed.

The main log is the spine. The sidecars are the detailed forensic payload. And the spine must stay sexy.

## Guardrails

- no per-frame routine INFO stream;
- no logging-driven repaint/cadence/control flow;
- no UI-thread normal file/rotation work;
- only the explicit saturated WARNING+ emergency path may write synchronously;
- no hiding WARNING+ from main;
- no performance claim achieved by deleting evidence instead of routing it cheaply;
- no unbounded logging queue;
- no console formatting that becomes a persistence dependency;
- no Quick/QML physical acceptance based only on the Python log;
- no OS-level stderr tee without explicit crash/subprocess/console semantics.
