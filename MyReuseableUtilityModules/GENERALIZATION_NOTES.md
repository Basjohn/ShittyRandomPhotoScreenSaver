# Generalization Notes

This document explains what was generalized from the SPQDocker codebase and how to use these components in new projects.

## ✅ **ALL MODULES ARE NOW INCLUDED**

**The spinoff package is complete and self-contained.** All core modules, utilities, and themes have been copied and their imports fixed to work standalone.

## What's Included

### Complete Modules (Ready to Use)

All these modules are **already in the spinoff directory** - no copying needed!

#### 1. **Themes** (`themes/`)
- `dark.qss` (32.8 KB) - Production-ready dark theme
- `light.qss` (30.7 KB) - Production-ready light theme

**Changes**: None - these are pure QSS and work universally with any Qt application.

**Usage**: Simply load and apply:
```python
with open("themes/dark.qss", "r") as f:
    app.setStyleSheet(f.read())
```

#### 2. **Core Modules** (`core/`)

All core modules are **included and ready to use**:

- **ThreadManager** (`core/threading/manager.py`, 37 KB)
- **ResourceManager** (`core/resources/manager.py`, 57 KB)
- **EventSystem** (`core/events/event_system.py`, 16 KB)
- **SettingsManager** (`core/settings/settings_manager.py`, 42 KB)

**Changes Made**: Import paths fixed to be self-contained within spinoff package.

**Usage**:
```python
from core.threading import ThreadManager, ThreadPoolType
from core.resources import ResourceManager, ResourceType
from core.events import EventSystem
from core.settings import SettingsManager
```

#### 3. **Lock-Free Data Structures** (`utils/lockfree/`)

**Included** in the package:
- `SPSCQueue` - Single producer, single consumer queue
- `TripleBuffer` - Lock-free triple buffering for graphics

**Changes**: None needed - these are generic data structures.

**Usage**: See CORE_MODULES.md for examples.

### Import Path Changes (Already Applied)

All imports have been updated to be self-contained within the spinoff package:

- ✅ `from core.logging import get_logger` - Uses spinoff's simple logger
- ✅ `from core.resources import ResourceManager, ResourceType` - Self-contained
- ✅ `from utils.lockfree import SPSCQueue, TripleBuffer` - Included
- ✅ All cross-module imports fixed

**No additional changes needed** - the package is ready to use as-is!

### Dependencies

The spinoff package requires:

- **Python 3.9+** (uses modern type hints)
- **PySide6** (Qt6 for GUI framework)

That's it! No other external dependencies.

## Quick Integration Guide

### Step 1: Copy the Spinoff Directory

```bash
# Copy the entire spinoff directory to your project
cp -r /path/to/SPQDocker/spinoff /path/to/your/project/
```

### Step 2: Use It!

#### Just Themes

```python
from PySide6.QtWidgets import QApplication
import sys

app = QApplication(sys.argv)

# Load theme from spinoff directory
with open("spinoff/themes/dark.qss", "r") as f:
    app.setStyleSheet(f.read())

# Your application code...
sys.exit(app.exec())
```

#### With Core Modules

```python
import sys
# Add spinoff to Python path
sys.path.insert(0, 'spinoff')

from PySide6.QtWidgets import QApplication
from core.threading import ThreadManager, ThreadPoolType
from core.resources import ResourceManager, ResourceType
from core.events import EventSystem
from core.settings import SettingsManager

app = QApplication(sys.argv)

# Load theme
with open("spinoff/themes/dark.qss", "r") as f:
    app.setStyleSheet(f.read())

# Initialize core systems
resource_manager = ResourceManager()
thread_manager = ThreadManager(resource_manager=resource_manager)
event_system = EventSystem()
settings = SettingsManager()

# Use thread manager
thread_manager.submit_task(
    ThreadPoolType.IO,
    my_io_function,
    arg1, arg2
)

# Your application code...

# Cleanup on shutdown
resource_manager.shutdown()

sys.exit(app.exec())
```

That's it! The spinoff package is completely self-contained and ready to use.

## Removed SPQ-Specific Code

These components were NOT included as they're too application-specific:

1. **Window Management** (`core/windows/`)
   - MRU (Most Recently Used) window tracking
   - Focus tracking
   - Foreground autoswitch

2. **Docking System** (`core/graphics/docking/`)
   - Multi-overlay positioning
   - Screen-aware placement
   - DWM thumbnail integration

3. **Hotkey System** (`core/hotkeys/`)
   - Global hotkey registration
   - Quickswitch controller
   - Opacity controls

4. **Media Control** (`core/media/`)
   - Media key passthrough
   - Audio session management
   - Keep-alive system

5. **Graphics Backends** (`core/graphics/backends/`)
   - DWM thumbnail system
   - Monitor capture
   - Overlay host management

**Why removed**: These are deeply integrated with SPQDocker's specific use case (window overlay management). The patterns are documented in the original codebase if you need similar functionality.

## Architecture Principles Preserved

The generalized modules maintain these key architectural principles from SPQDocker:

### 1. Lock-Free Where Possible
- UI thread dispatch instead of mutexes
- Atomic operations
- Single-producer-single-consumer queues
- Message passing patterns

### 2. Deterministic Resource Cleanup
- Weak references allow garbage collection
- Ordered cleanup (Qt → Network → OpenGL → Files)
- Custom cleanup handlers
- ResourceManager integration

### 3. UI Thread Affinity (Qt-Aware)
- All Qt operations on UI thread
- Safe cross-thread communication
- QTimer integration
- Signal/slot patterns

### 4. No Fallbacks, Explicit Failure
- Operations fail explicitly with clear logging
- No silent fallbacks that hide bugs
- Validation at boundaries
- Type-safe operations

### 5. Single Source of Truth
- One manager per concern (threads, resources, events, settings)
- No duplicate systems
- Clear ownership
- Deterministic behavior

## Testing the Generalized Modules

Basic smoke test:

```python
# test_generalized.py
from core.threading import ThreadManager, ThreadPoolType
from core.resources import ResourceManager, ResourceType
from core.events import EventSystem
from core.settings import SettingsManager
import time

def test_basic_integration():
    # Initialize
    resource_manager = ResourceManager()
    thread_manager = ThreadManager(resource_manager=resource_manager)
    event_system = EventSystem()
    settings = SettingsManager()
    
    # Test threading
    result = []
    def task():
        time.sleep(0.1)
        result.append("done")
    
    thread_manager.submit_task(ThreadPoolType.COMPUTE, task)
    time.sleep(0.2)
    assert result == ["done"]
    
    # Test events
    events_received = []
    def handler(event):
        events_received.append(event.data)
    
    event_system.subscribe("test.event", handler)
    event_system.publish("test.event", data="hello")
    assert events_received == ["hello"]
    
    # Test settings
    settings.set("test.value", 42)
    assert settings.get("test.value") == 42
    
    # Cleanup
    settings.save()
    event_system.shutdown()
    thread_manager.shutdown()
    resource_manager.shutdown()
    
    print("✅ All tests passed!")

if __name__ == "__main__":
    test_basic_integration()
```

## Migration Path

For existing projects migrating to this framework:

### Step 1: Themes First
- Replace your existing stylesheets with the provided themes
- Test all dialogs and widgets
- Customize colors if needed

### Step 2: Add ResourceManager
- Replace manual cleanup with ResourceManager registration
- Focus on Qt widgets first (use `register_qt()`)
- Then file handles, then custom resources

### Step 3: Add ThreadManager
- Identify background work
- Replace raw threads with ThreadManager pools
- Replace raw timers with ThreadManager timers
- Use UI thread dispatch for Qt updates

### Step 4: Add EventSystem
- Identify cross-module communication
- Replace direct calls with events
- Add subscribers for reactive behavior
- Remove tight coupling

### Step 5: Add SettingsManager
- Move configuration to JSON file
- Replace scattered settings with centralized manager
- Add change notifications for live updates

## Support and Contributions

This is a one-time spinoff extraction. However, the patterns and architecture are well-documented in:

- `docs/CORE_MODULES.md` - Detailed module documentation
- `docs/THEME_GUIDE.md` - Theme customization
- `docs/OVERLAY_GUIDE.md` - Overlay window patterns

For the latest SPQDocker source (where these modules originated):
- Repository: (Your repo location)
- Issues: (Your issue tracker)

## Version History

**v1.0** (2025-10-13) - Initial spinoff extraction
- ThreadManager with specialized pools
- ResourceManager with deterministic cleanup
- EventSystem with pub-sub pattern
- SettingsManager with JSON persistence
- Dark and light themes
- Complete documentation

Extracted from SPQDocker v2.1.0 after 18 months of production use and refinement.
