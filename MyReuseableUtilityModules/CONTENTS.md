# Spinoff Package Contents

This directory contains generalized, reusable components extracted from SPQDocker for use in future Qt/Python projects.

## Directory Structure

```
spinoff/
├── README.md                      # Overview and quick start
├── CONTENTS.md                    # This file
├── GENERALIZATION_NOTES.md        # Detailed extraction notes
├── QUICK_REFERENCE.md            # Fast reference card
├── SPINOFF_SUMMARY.md            # Creation summary
│
├── core/                          # Core framework modules (INCLUDED!)
│   ├── __init__.py
│   ├── threading/
│   │   ├── __init__.py
│   │   └── manager.py            # ThreadManager (37 KB)
│   ├── resources/
│   │   ├── __init__.py
│   │   ├── manager.py            # ResourceManager (57 KB)
│   │   └── types.py              # Resource types
│   ├── events/
│   │   ├── __init__.py
│   │   ├── event_system.py       # EventSystem (16 KB)
│   │   └── event_types.py        # Event classes
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── settings_manager.py   # SettingsManager (42 KB)
│   │   └── types.py              # Settings types
│   ├── interfaces/
│   │   └── __init__.py           # Core interfaces
│   └── logging/
│       └── __init__.py           # Logging utilities
│
├── utils/                         # Utility modules
│   ├── __init__.py
│   └── lockfree/                 # Lock-free data structures
│       ├── __init__.py
│       ├── spsc_queue.py         # Single-producer-single-consumer queue
│       └── triple_buffer.py      # Lock-free triple buffer
│
├── docs/                          # Comprehensive documentation
│   ├── CORE_MODULES.md           # Module documentation (25 KB)
│   ├── THEME_GUIDE.md            # Theme guide (15 KB)
│   └── OVERLAY_GUIDE.md          # Overlay patterns (22 KB)
│
└── themes/                        # Production-ready QSS themes
    ├── dark.qss                  # Modern dark theme (33 KB)
    └── light.qss                 # Modern light theme (31 KB)
```

## What's Ready to Use

### ✅ **ALL MODULES INCLUDED** - Ready to Use

**Themes (`themes/`)**
- `dark.qss` (32.8 KB) - Complete dark theme with overlay support
- `light.qss` (30.7 KB) - Complete light theme with overlay support

**Core Modules (`core/`)**
- **ThreadManager** (`core/threading/manager.py`, 37.2 KB) - Lock-free threading with specialized pools
- **ResourceManager** (`core/resources/manager.py`, 57.2 KB) - Deterministic resource cleanup
- **EventSystem** (`core/events/event_system.py`, 16.0 KB) - Publish-subscribe event bus
- **SettingsManager** (`core/settings/settings_manager.py`, 42.3 KB) - Type-safe configuration

**Utilities (`utils/`)**
- **Lock-Free Data Structures** (`utils/lockfree/`) - SPSC Queue and Triple Buffer

**Total: 28 Python files, ~330 KB of production-ready code**

All imports have been fixed to be self-contained within this package. Just copy the `spinoff/` directory to your project and start using!

## Documentation Contents

### CORE_MODULES.md (29 KB)
Comprehensive guide covering:
- **ThreadManager**: Lock-free threading with specialized pools
- **ResourceManager**: Deterministic resource cleanup
- **EventSystem**: Publish-subscribe event bus
- **SettingsManager**: Type-safe configuration management
- **Integration Patterns**: Full examples and best practices

### THEME_GUIDE.md (24 KB)
Complete theme documentation:
- Applying themes to applications
- Theme structure and organization
- Color palettes (dark and light)
- Customization techniques
- Component styles (buttons, menus, overlays)
- Advanced styling patterns
- Troubleshooting

### OVERLAY_GUIDE.md (18 KB)
Overlay window patterns:
- Basic overlay windows
- Titled overlays with drag support
- Resizable overlays
- Aspect ratio locking
- Opacity and fade effects
- Real-world examples (toasts, PiP, screen capture)
- Best practices

## Quick Start Examples

### Just Themes

```python
from PySide6.QtWidgets import QApplication
import sys

app = QApplication(sys.argv)

# Load theme
with open("spinoff/themes/dark.qss", "r") as f:
    app.setStyleSheet(f.read())

# Your app code...
sys.exit(app.exec())
```

### Full Framework (After Copying Modules)

```python
from core.threading import ThreadManager, ThreadPoolType
from core.resources import ResourceManager, ResourceType
from core.events import EventSystem
from core.settings import SettingsManager

# Initialize core systems
resource_manager = ResourceManager()
thread_manager = ThreadManager(resource_manager=resource_manager)
event_system = EventSystem()
settings = SettingsManager()

# Load theme
with open("themes/dark.qss", "r") as f:
    app.setStyleSheet(f.read())

# Your application code...

# Cleanup (automatic with ResourceManager)
resource_manager.shutdown()
```

## What's NOT Included

These SPQDocker-specific components were not included:

- Window management (MRU tracking, focus tracking)
- Docking overlay system
- Hotkey system
- DWM thumbnail integration
- Media control system
- Screen capture backends

These are too application-specific. The patterns exist in the main SPQDocker codebase if needed.

## Testing Before Use

Before using in a new project, test with:

```python
# Load themes in a simple Qt app
# Verify buttons, menus, dialogs render correctly
# Test both dark and light themes
# Check high DPI displays if applicable
```

If copying core modules:

```python
# Test ThreadManager with simple tasks
# Test ResourceManager cleanup ordering
# Test EventSystem pub-sub
# Test SettingsManager persistence
# Ensure all imports resolve
```

## Version Info

**Extracted**: 2025-10-13
**Source**: SPQDocker v2.1.0
**Production Use**: 18+ months
**Qt Version**: PySide6 (Qt 6.x)
**Python**: 3.9+

## Files Created

This spinoff extraction created:

1. **README.md** - Overview and introduction
2. **CONTENTS.md** - This file
3. **GENERALIZATION_NOTES.md** - Detailed extraction guide
4. **docs/CORE_MODULES.md** - Module documentation (71 KB)
5. **docs/THEME_GUIDE.md** - Theme guide (51 KB)
6. **docs/OVERLAY_GUIDE.md** - Overlay patterns (39 KB)
7. **themes/dark.qss** - Dark theme (copied)
8. **themes/light.qss** - Light theme (copied)

**Total Documentation**: ~161 KB of comprehensive guides and examples

## Next Steps

1. **Read**: Start with README.md for overview
2. **Choose**: Decide what you need (themes only vs full framework)
3. **Copy**: If using core modules, copy from locations in GENERALIZATION_NOTES.md
4. **Adapt**: Update import paths and dependencies
5. **Test**: Run smoke tests before integrating
6. **Integrate**: Follow migration path in GENERALIZATION_NOTES.md
7. **Customize**: Adapt themes and modules to your needs

## Attribution

These components were extracted from **SPQDocker**, a window overlay management application developed over 18 months with extensive production use and refinement.

The framework embodies hard-won architectural principles:
- Lock-free concurrency
- Deterministic resource cleanup
- Single source of truth
- No silent fallbacks
- Qt-aware thread safety

Use freely in your projects. Attribution appreciated but not required.

---

**Note**: The core module source files are NOT included in this spinoff directory. They remain in the main SPQDocker codebase at their original locations. See `GENERALIZATION_NOTES.md` for exact file paths to copy.

Only the themes (QSS files) and documentation are included as standalone files.
