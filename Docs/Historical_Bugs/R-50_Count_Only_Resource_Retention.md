# R-50 — Count-Only Image/Texture Retention And Unbounded Prefetch Backlog

Date: 2026-07-28  
Status: Resolved

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [ ] AWAITING VALIDATION
- [x] SOLVED

## Observed Failure Family

Normal image rotation retained decoded/scaled image, display pixmap, texture, and PBO representations without one complete byte-budget story. The CPU cache evicted by an RGBA approximation despite already recording exact Qt bytes; pending prefetch work was unbounded; textures were count-only; historical PBO sizes accumulated; and several transition terminal paths retained active texture pins.

## Root Causes

Ownership stopped at object counts, prefetch concurrency was mistaken for backlog containment, GUI-affine QPixmap materialization escaped into a worker, the active display path deep-copied implicit-shared QImages and created redundant original pixmaps, identical display transforms were processed independently, and display-owned Qt backing stores were absent from passive snapshots.

## Fix

Exact logical bytes now drive CPU LRU eviction under clamped settings; concurrency, pending count, and future scaled bytes are independently capped; workers publish QImage only; source changes invalidate old raw/scaled callback generations; exact source/size/mode/DPR/quality transforms share immutable backing in both normal and previous-image paths without cross-DPR scaled-cache collapse; GUI-captured QPixmap sidecars deduplicate aliases and displays; each compositor has byte/count texture and idle-PBO caps; all transition completion/cancellation families release pins and obsolete state on the owner context.

## Bars

The focused cache/prefetch/pipeline/texture/PBO/accounting regressions pass. `tools/phase4_resource_harness.py` runs 45 alternating-resolution transition cycles (30 virtual minutes), two-display aliasing, pressure budgets, and full-owner resets with all budget/plateau criteria true; the latest follow-up had 4 KiB repeated-resolution RSS drift and an 8 KiB final tail high-water range. Real driver VRAM is explicitly not inferred from the offscreen/fake-delete seam and remains a platform gate.

## Guardrail

Never treat item count or concurrency alone as memory containment, create QPixmap in workers, sample live Qt display objects off-thread, share differing transform/DPR outputs, retain terminal transition pins, or raise cache/PBO budgets to hide unexplained growth.

## Evidence

- `Docs/phase_reports/P04_MEMORY_VRAM_CONTAINMENT.md`
- `Docs/phase_reports/P04_RESOURCE_LIFETIME_MAP.md`
- `Docs/phase_reports/artifacts/P04/resource_plateau_report.json`

## Migration Record

This file is the standalone detailed record copied from the original `R-50` entry in `Docs/Historical_Bugs.md`. The monolithic source entry remains unchanged during the copy-first migration and will be replaced by a compact index summary only after the historical-bug set has been migrated and mechanically checked.
