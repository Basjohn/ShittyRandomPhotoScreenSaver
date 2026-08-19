# P2 Installed Acceptance Findings — Second Run — 2026-08-19

Tested source anchor: `ccb63542348fec5993a688142bc2e364f8149f6a`

Operator report:
- Spectrum idle fixed;
- Pause/Play hitch unchanged;
- fade-in start remains clean;
- general hitching remains;
- transition performance remains poor.

Installed behavior overrides unit-test claims of completion.

## Accepted

### Generation zero
```text
Runtime started (generation=0 interval_ms=11.11)
```

### Spectrum idle
```text
Shader bars snapshot: count=35, min=0.0738, max=0.4192
```

Operator confirms visible resting bars.

### Logical runtime average
```text
generation=0 steps=12488 skipped_deadlines=11 slow_steps=2 failures=0
generation=0 steps=1699  skipped_deadlines=3  slow_steps=0 failures=0
generation=1 steps=5065  skipped_deadlines=5  slow_steps=2 failures=0
```

The ~64 Hz historical scheduler collapse remains fixed.

## Still failing

- Pause/Play perceptual hitch.
- General hitching.
- 165 Hz transition delivery.
- BTF long tails.

## Slice H installed evidence

Feedback paint requests/event still include:

```text
40, 50, 62, 36, 46, 55, 44, 23, 45, 75, 44, 36, 55, 48
```

Real `media.paint` during rapid toggles:

```text
19:07:50 calls=50 avg_ms=3.87 max_ms=7.15
19:07:51 calls=50 avg_ms=2.62 max_ms=7.38
19:07:52 calls=50 avg_ms=1.87 max_ms=5.42
19:07:54 calls=50 avg_ms=2.85 max_ms=6.08
19:07:56 calls=50 avg_ms=3.45 max_ms=6.87
19:07:59 calls=50 avg_ms=2.46 max_ms=6.52
```

Card area:
```text
170400 px
```

Conclusion: dirty-region updates reduced raster area but did not remove frame-count-scale real parent paint execution.

`full_card_paint_requests` is tracked in metadata but is not emitted by the current structured feedback logger; the installed run cannot verify the claimed field.

## Pause/Play-specific source defect

`MediaWidget.play_pause()` synchronously calls the controller.

The Windows GSMTC controller runs WinRT through IO but waits for completion through `threading.Event`, so a GUI caller can still block.

This strongly matches:
- Pause hitch;
- Play hitch;
- fade-in being clean.

Historical qualification:
`core/media/media_controller.py` is byte-identical at accepted baseline `42033c84...` and current. Treat this as a real edge defect, not proof of the whole baseline regression.

## Bubble handoff collapse during toggles

```text
19:07:40 set_state=816 / 10s
19:07:50 set_state=688 / ~10s
19:08:00 set_state=560 / 10s
19:08:10 set_state=831 / 10s
```

Approximate:
```text
81.6/s -> 68.7/s -> 56.0/s -> 83.1/s
```

Logical runtime remains ~89.9 Hz.

## 165 Hz transition failure

Completed Blockspin:
```text
140.7, 144.8, 140.0, 138.1, 136.3, 136.5, 141.3 FPS
```

Target:
```text
165 Hz
```

Request acceptance:
```text
90.01%, 92.38%, 89.42%, 87.78%, 90.20%, 87.95%, 88.50%
```

## Delivery-stage attribution

Representative screen-0 windows:
- wake lateness p95 generally ~1–2 ms;
- `paint_pending_skips=0`;
- substantial `dispatch_pending_skips`;
- dispatch skip/GUI dispatch tails reach tens to >100 ms.

This run does not justify adaptive-timer deadline changes.

## Required next work

1. Non-blocking transport command ownership.
2. Real lightweight feedback paint ownership.
3. One installed acceptance run.

No A/B architecture experiment and no new generic probe phase before those corrections.
