# QTimer Policy

## When to Use QTimer (UI-thread only)

QTimer is acceptable **only** for UI-thread-bound work that must synchronize with Qt's event loop:

- **Debounce timers** in settings dialogs (`QTimer.singleShot(300, ...)` for save delay)
- **Deferred widget updates** (`QTimer.singleShot(0, ...)` to defer to next event loop iteration)
- **Frame-rate animation ticks** in `core/animation/animator.py` (vsync-coupled, must stay on UI thread)
- **Overlay fade timers** in `widgets/overlay_timers.py` (centralized, UI-thread by design)

## When to Use ThreadManager Instead

All background/async work **must** go through `core/threading/manager.py`:

- **Periodic polling** (system mute state, API refresh, health checks)
- **Compute tasks** (FFT processing, image loading, bar smoothing)
- **IO tasks** (file reads, network requests, cache operations)
- **Delayed non-UI work** (use `submit_io_task` with sleep, not QTimer)

## Intentional UI-Thread QTimer Locations

| File | Count | Purpose |
|------|------:|---------|
| `ui/settings_dialog.py` | 3 | Save debounce, deferred layout updates |
| `ui/styled_popup.py` | 1 | Auto-dismiss timeout |
| `ui/system_tray.py` | 1 | Deferred tray icon update |
| `ui/tabs/widgets_tab.py` | 1 | Deferred visibility update |
| `core/animation/animator.py` | 8 | Frame-rate animation ticks (vsync-coupled) |
| `widgets/overlay_timers.py` | 6 | Centralized overlay fade/show timers |
| `engine/screensaver_engine.py` | 7 | Engine lifecycle (startup, shutdown, transition scheduling) |
| `rendering/widget_manager.py` | 7 | Widget refresh coordination |
| `widgets/media_widget.py` | 5 | Progress bar, animation timing |

## Rules

1. **Never** use `QTimer` for background work — use `ThreadManager.submit_io_task()` or `submit_compute_task()`
2. **Never** use raw `threading.Thread()` or `ThreadPoolExecutor()` for business logic
3. `QTimer.singleShot(0, fn)` is acceptable for deferring UI work to the next event loop tick
4. All new QTimer usage must be documented with `# UI-thread timer (intentional)` comment
5. Recurring QTimers should be registered with `ResourceManager` for deterministic cleanup
