# R-31 — 2026-07-10 — Worker-Rejected Display Image Masqueraded As Multi-Monitor Compositor Loss (Resolved In Code, Runtime Validation Pending)

## Classification

- [ ] COMPLETELY FUCKED
- [ ] PARTIAL
- [x] AWAITING VALIDATION
- [ ] SOLVED

- **Observed failure pattern:** after one CUSTOM edit/reinitialization, Display 0 returned but Display 1 stayed blank, resembling the older missing-compositor or stale-geometry family. Many surrounding edits succeeded.
- **Evidence:** at `14:00:26`, both display widgets, render surfaces, shared compositors, and GL contexts initialized. Display 1's selected RSS image was then rejected by ImageWorker because `222972620` decoded pixels exceeded Pillow's `178956970` decompression-bomb limit. The pipeline logged `ImageWorker failed for display 1, skipping image`; Display 0 committed its first frame, while Display 1 never did. Before and after this cycle, both displays repeatedly committed first frames successfully.
- **Root cause:** image-worker failure was terminal only for that display. The queue already had replacement candidates, but the multi-display compute pass returned a partial result, leaving a healthy compositor with no first image.
- **Fix:** rejected/missing candidates now use a bounded worker-side replacement loop. Different-image mode replaces only the failed display and records the actual selected metadata. Same-image mode retries one common candidate atomically across all displays so the shared-image contract cannot split. No repaint retry, display rebuild, rescue timer, or extra UI pressure was added.
- **Bars:** `tests/test_image_pipeline.py` models the exact Display 1 rejection/replacement path, duplicate rejected-candidate skipping, same-image atomic replacement, existing cache/prefetch behavior, and the no-direct-`QTimer.singleShot` rule.
- **Runtime validation target:** a future invalid/oversized image should log a recovered replacement and still reach `First frame committed` on every active display. Exhaustion remains loud and bounded.

## Record Provenance

This standalone file preserves the complete former inline `R-31` record from `Docs/Historical_Bugs.md`. The chronology and technical claims are retained from that source; only heading normalization, standalone-link retargeting, and removal of monolith-only section dividers were applied during extraction.
