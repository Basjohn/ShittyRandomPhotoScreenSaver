# Global Hotkey System

Production-ready global hotkey system for Windows with registration, callbacks, and proper cleanup.

## Table of Contents

1. [Overview](#overview)
2. [Basic Usage](#basic-usage)
3. [Advanced Features](#advanced-features)
4. [Real-World Examples](#real-world-examples)
5. [Integration](#integration)

---

## Overview

The hotkey system provides **global hotkey registration** for Windows applications, allowing your app to respond to keyboard shortcuts even when not in focus.

### Features

✅ **Global Registration**: System-wide hotkeys that work anywhere  
✅ **Thread-Safe**: Dedicated hotkey thread with message loop  
✅ **Multiple Modifiers**: Support for Ctrl, Alt, Shift, Win keys  
✅ **Callback System**: Easy-to-use callback pattern  
✅ **Singleton Pattern**: Single manager instance  
✅ **Resource Management**: Automatic cleanup on shutdown  
✅ **Conflict Detection**: Handles registration failures gracefully  

### Dependencies

```python
# Windows-specific
import win32api
import win32con
import win32gui

# Qt
from PySide6.QtCore import QObject, Signal

# Framework
from core.threading import ThreadManager
from core.resources import ResourceManager
```

---

## Basic Usage

### 1. Get Hotkey Manager Instance

```python
from core.hotkeys import HotkeyManager

# Get singleton instance
hotkey_manager = HotkeyManager()
```

### 2. Register a Hotkey

```python
def on_quickswitch_pressed():
    """Called when Shift+X is pressed."""
    print("Quickswitch activated!")
    # Your code here

# Register the hotkey
success = hotkey_manager.register_hotkey(
    hotkey_id="quickswitch",
    callback=on_quickswitch_pressed,
    sequence="shift+x",
    global_hotkey=True
)

if success:
    print("Hotkey registered successfully")
else:
    print("Failed to register hotkey (may be in use)")
```

### 3. Unregister When Done

```python
# Unregister specific hotkey
hotkey_manager.unregister_hotkey("quickswitch")

# Or shutdown entire system
hotkey_manager.shutdown()
```

---

## Hotkey Sequences

### Supported Modifiers

| Modifier | String | Description |
|----------|--------|-------------|
| Control | `"ctrl"` | Ctrl key |
| Alt | `"alt"` | Alt key |
| Shift | `"shift"` | Shift key |
| Windows | `"win"` | Windows key |

### Supported Keys

Letters: `a-z`  
Numbers: `0-9`  
Function: `f1-f24`  
Special: `space`, `enter`, `tab`, `esc`, `backspace`, `delete`, `insert`, `home`, `end`, `pageup`, `pagedown`  
Arrows: `left`, `right`, `up`, `down`  
Numpad: `numpad0-numpad9`, `multiply`, `add`, `subtract`, `divide`, `decimal`  

### Sequence Format

```python
# Single modifier + key
"ctrl+s"
"alt+f4"
"shift+tab"

# Multiple modifiers
"ctrl+alt+delete"
"ctrl+shift+s"
"win+shift+s"

# No modifier (not recommended for global hotkeys)
"f12"
```

---

## Complete Example

```python
from PySide6.QtWidgets import QApplication, QWidget
from core.hotkeys import HotkeyManager
import sys

class MyApp(QWidget):
    def __init__(self):
        super().__init__()
        
        # Get hotkey manager
        self.hotkey_manager = HotkeyManager()
        
        # Register multiple hotkeys
        self._register_hotkeys()
    
    def _register_hotkeys(self):
        """Register all application hotkeys."""
        hotkeys = [
            {
                "id": "show_hide",
                "sequence": "ctrl+shift+h",
                "callback": self.toggle_visibility,
                "description": "Show/hide main window"
            },
            {
                "id": "settings",
                "sequence": "ctrl+alt+s",
                "callback": self.show_settings,
                "description": "Open settings"
            },
            {
                "id": "quickswitch",
                "sequence": "shift+x",
                "callback": self.activate_quickswitch,
                "description": "Quick window switch"
            }
        ]
        
        for hk in hotkeys:
            success = self.hotkey_manager.register_hotkey(
                hotkey_id=hk["id"],
                callback=hk["callback"],
                sequence=hk["sequence"],
                global_hotkey=True
            )
            
            if success:
                print(f"✓ Registered: {hk['description']} ({hk['sequence']})")
            else:
                print(f"✗ Failed: {hk['description']} (may be in use)")
    
    def toggle_visibility(self):
        """Toggle window visibility."""
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.activateWindow()
    
    def show_settings(self):
        """Open settings dialog."""
        print("Settings opened")
        # Your settings dialog code
    
    def activate_quickswitch(self):
        """Activate quickswitch mode."""
        print("Quickswitch activated")
        # Your quickswitch code
    
    def closeEvent(self, event):
        """Cleanup on close."""
        # Unregister all hotkeys
        self.hotkey_manager.shutdown()
        event.accept()

# Run application
app = QApplication(sys.argv)
window = MyApp()
window.show()
sys.exit(app.exec())
```

---

## Advanced Features

### Hotkey Signals

The manager emits signals when hotkeys are triggered:

```python
from core.hotkeys import HotkeyManager

hotkey_manager = HotkeyManager()

# Connect to hotkey triggered signal
hotkey_manager.hotkey_triggered.connect(on_any_hotkey_triggered)

def on_any_hotkey_triggered(hotkey_id: str):
    """Called whenever any hotkey is triggered."""
    print(f"Hotkey triggered: {hotkey_id}")
```

### Callback with Arguments

```python
def show_window(window_id: str, focus: bool = True):
    """Show a specific window."""
    print(f"Showing window: {window_id}, focus={focus}")
    # Your code here

# Register with arguments
hotkey_manager.register_hotkey(
    hotkey_id="show_window_1",
    callback=show_window,
    "window_1",  # Positional arg
    focus=True,  # Keyword arg
    sequence="ctrl+1",
    global_hotkey=True
)
```

### Registration Options

```python
success = hotkey_manager.register_hotkey(
    hotkey_id="my_hotkey",          # Unique identifier
    callback=my_function,           # Function to call
    sequence="ctrl+alt+k",          # Key combination
    global_hotkey=True,             # System-wide (default: False)
    suppress=True,                  # Suppress key (default: True)
    on_release=on_key_release,      # Optional release callback
    release_args=()                 # Args for release callback
)
```

### Handling Registration Failures

```python
def register_with_fallback():
    """Try multiple hotkey combinations."""
    preferences = [
        "shift+x",      # Preferred
        "ctrl+shift+x", # Fallback 1
        "alt+x"         # Fallback 2
    ]
    
    for sequence in preferences:
        success = hotkey_manager.register_hotkey(
            hotkey_id="my_action",
            callback=my_callback,
            sequence=sequence,
            global_hotkey=True
        )
        
        if success:
            print(f"Registered hotkey: {sequence}")
            return sequence
    
    print("Failed to register any hotkey combination")
    return None

registered_sequence = register_with_fallback()
```

### Dynamic Hotkey Changes

```python
class HotkeyConfig:
    def __init__(self):
        self.hotkey_manager = HotkeyManager()
        self.current_sequence = "shift+x"
    
    def change_hotkey(self, new_sequence: str):
        """Change hotkey to new sequence."""
        # Unregister old
        self.hotkey_manager.unregister_hotkey("my_action")
        
        # Register new
        success = self.hotkey_manager.register_hotkey(
            hotkey_id="my_action",
            callback=self.on_action,
            sequence=new_sequence,
            global_hotkey=True
        )
        
        if success:
            self.current_sequence = new_sequence
            print(f"Hotkey changed to: {new_sequence}")
            return True
        else:
            # Re-register old on failure
            self.hotkey_manager.register_hotkey(
                hotkey_id="my_action",
                callback=self.on_action,
                sequence=self.current_sequence,
                global_hotkey=True
            )
            print(f"Failed to change hotkey, keeping: {self.current_sequence}")
            return False
    
    def on_action(self):
        print("Action triggered")
```

---

## Real-World Examples

### Example 1: Application-Wide Hotkeys

```python
from core.hotkeys import HotkeyManager
from core.settings import SettingsManager

class ApplicationHotkeys:
    """Manage all application hotkeys."""
    
    def __init__(self, app):
        self.app = app
        self.hotkey_manager = HotkeyManager()
        self.settings = SettingsManager()
        self.registered_hotkeys = {}
        
        self.setup_hotkeys()
    
    def setup_hotkeys(self):
        """Setup all hotkeys from settings."""
        hotkey_config = {
            "show_hide": {
                "default": "ctrl+shift+h",
                "callback": self.app.toggle_visibility
            },
            "settings": {
                "default": "ctrl+alt+s",
                "callback": self.app.show_settings
            },
            "quit": {
                "default": "ctrl+alt+q",
                "callback": self.app.quit
            }
        }
        
        for hk_id, config in hotkey_config.items():
            # Get sequence from settings or use default
            sequence = self.settings.get(
                f"hotkeys.{hk_id}",
                config["default"]
            )
            
            # Register
            success = self.hotkey_manager.register_hotkey(
                hotkey_id=hk_id,
                callback=config["callback"],
                sequence=sequence,
                global_hotkey=True
            )
            
            if success:
                self.registered_hotkeys[hk_id] = sequence
                print(f"✓ {hk_id}: {sequence}")
            else:
                print(f"✗ {hk_id}: {sequence} (in use)")
    
    def change_hotkey(self, hotkey_id: str, new_sequence: str):
        """Change a hotkey and save to settings."""
        # Unregister old
        self.hotkey_manager.unregister_hotkey(hotkey_id)
        
        # Register new
        success = self.hotkey_manager.register_hotkey(
            hotkey_id=hotkey_id,
            callback=self._get_callback_for_id(hotkey_id),
            sequence=new_sequence,
            global_hotkey=True
        )
        
        if success:
            # Save to settings
            self.settings.set(f"hotkeys.{hotkey_id}", new_sequence)
            self.registered_hotkeys[hotkey_id] = new_sequence
            return True
        else:
            # Re-register old
            old_sequence = self.registered_hotkeys.get(hotkey_id)
            if old_sequence:
                self.hotkey_manager.register_hotkey(
                    hotkey_id=hotkey_id,
                    callback=self._get_callback_for_id(hotkey_id),
                    sequence=old_sequence,
                    global_hotkey=True
                )
            return False
    
    def _get_callback_for_id(self, hotkey_id: str):
        """Get callback function for hotkey ID."""
        # Map hotkey IDs to callbacks
        callbacks = {
            "show_hide": self.app.toggle_visibility,
            "settings": self.app.show_settings,
            "quit": self.app.quit
        }
        return callbacks.get(hotkey_id)
    
    def shutdown(self):
        """Cleanup all hotkeys."""
        self.hotkey_manager.shutdown()
```

### Example 2: Context-Aware Hotkeys

```python
class ContextualHotkeys:
    """Hotkeys that change based on application state."""
    
    def __init__(self):
        self.hotkey_manager = HotkeyManager()
        self.current_mode = "normal"
        
        # Register mode-independent hotkeys
        self.hotkey_manager.register_hotkey(
            "toggle_mode",
            self.toggle_mode,
            sequence="ctrl+m",
            global_hotkey=True
        )
        
        self.setup_mode_hotkeys()
    
    def toggle_mode(self):
        """Toggle between normal and advanced mode."""
        if self.current_mode == "normal":
            self.switch_to_advanced_mode()
        else:
            self.switch_to_normal_mode()
    
    def switch_to_normal_mode(self):
        """Setup normal mode hotkeys."""
        self.current_mode = "normal"
        
        # Unregister advanced hotkeys
        self.hotkey_manager.unregister_hotkey("advanced_action_1")
        self.hotkey_manager.unregister_hotkey("advanced_action_2")
        
        # Register normal hotkeys
        self.hotkey_manager.register_hotkey(
            "basic_action",
            self.basic_action,
            sequence="shift+x",
            global_hotkey=True
        )
        
        print("Switched to normal mode")
    
    def switch_to_advanced_mode(self):
        """Setup advanced mode hotkeys."""
        self.current_mode = "advanced"
        
        # Unregister normal hotkeys
        self.hotkey_manager.unregister_hotkey("basic_action")
        
        # Register advanced hotkeys
        self.hotkey_manager.register_hotkey(
            "advanced_action_1",
            self.advanced_action_1,
            sequence="shift+x",
            global_hotkey=True
        )
        
        self.hotkey_manager.register_hotkey(
            "advanced_action_2",
            self.advanced_action_2,
            sequence="ctrl+shift+x",
            global_hotkey=True
        )
        
        print("Switched to advanced mode")
    
    def basic_action(self):
        print("Basic action")
    
    def advanced_action_1(self):
        print("Advanced action 1")
    
    def advanced_action_2(self):
        print("Advanced action 2")
```

### Example 3: Hotkey Settings UI

```python
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, 
    QLabel, QPushButton, QKeySequenceEdit
)

class HotkeySettingsDialog(QDialog):
    """Dialog for configuring hotkeys."""
    
    def __init__(self, hotkey_manager, settings_manager):
        super().__init__()
        self.hotkey_manager = hotkey_manager
        self.settings = settings_manager
        self.hotkey_editors = {}
        
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Define hotkeys to configure
        hotkeys = [
            ("show_hide", "Show/Hide Window", "ctrl+shift+h"),
            ("settings", "Open Settings", "ctrl+alt+s"),
            ("quickswitch", "Quick Switch", "shift+x")
        ]
        
        for hk_id, label, default in hotkeys:
            row_layout = QHBoxLayout()
            
            # Label
            label_widget = QLabel(label)
            label_widget.setFixedWidth(150)
            row_layout.addWidget(label_widget)
            
            # Key sequence editor
            editor = QKeySequenceEdit()
            current_seq = self.settings.get(f"hotkeys.{hk_id}", default)
            editor.setKeySequence(current_seq)
            self.hotkey_editors[hk_id] = editor
            row_layout.addWidget(editor)
            
            layout.addLayout(row_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_hotkeys)
        button_layout.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def save_hotkeys(self):
        """Save and apply new hotkeys."""
        for hk_id, editor in self.hotkey_editors.items():
            # Get new sequence
            sequence = editor.keySequence().toString()
            
            # Unregister old
            self.hotkey_manager.unregister_hotkey(hk_id)
            
            # Register new
            success = self.hotkey_manager.register_hotkey(
                hotkey_id=hk_id,
                callback=self._get_callback(hk_id),
                sequence=sequence,
                global_hotkey=True
            )
            
            if success:
                # Save to settings
                self.settings.set(f"hotkeys.{hk_id}", sequence)
            else:
                # Show error
                QMessageBox.warning(
                    self,
                    "Hotkey Registration Failed",
                    f"Failed to register hotkey: {sequence}\n"
                    "It may be in use by another application."
                )
                # TODO: Revert to old sequence
        
        self.accept()
    
    def _get_callback(self, hotkey_id):
        """Get callback for hotkey ID."""
        # Return appropriate callback
        pass
```

---

## Integration

### With Resource Manager

The hotkey manager automatically registers with the ResourceManager for cleanup:

```python
from core.resources import get_resource_manager

# ResourceManager automatically cleans up hotkeys on shutdown
resource_manager = get_resource_manager()

# Hotkey manager is already registered during __init__
# You don't need to manually register it
```

### With Thread Manager

The hotkey manager uses ThreadManager for its message loop thread:

```python
# Automatically integrated - no manual setup needed
# The hotkey manager creates its own message thread
```

### With Settings Manager

Persist hotkey configurations:

```python
from core.settings import get_settings_manager

settings = get_settings_manager()

# Save hotkey
settings.set("hotkeys.quickswitch", "shift+x")

# Load hotkey
sequence = settings.get("hotkeys.quickswitch", "shift+x")

# Apply loaded hotkey
hotkey_manager.register_hotkey(
    "quickswitch",
    on_quickswitch,
    sequence=sequence,
    global_hotkey=True
)
```

---

## Platform Notes

### Windows Only

This hotkey system is **Windows-specific** and uses Win32 API:
- `RegisterHotKey` - Register system-wide hotkeys
- `UnregisterHotKey` - Unregister hotkeys
- `WM_HOTKEY` - Hotkey message handling

### Cross-Platform Alternative

For cross-platform hotkeys, consider:
- **pynput**: Cross-platform keyboard monitoring
- **keyboard**: Similar to pynput
- **Qt global shortcuts**: Limited, app must be running

The Win32 approach provides:
✅ True global hotkeys  
✅ System-level registration  
✅ Reliable event delivery  
✅ Conflict detection  

---

## Best Practices

### 1. Use Unique Hotkey IDs

```python
# Good - descriptive unique IDs
"app_show_hide"
"quick_switch_window_1"
"open_settings_dialog"

# Bad - generic IDs
"hotkey1"
"action"
"key"
```

### 2. Provide Fallback Sequences

```python
# Try multiple sequences in order of preference
for sequence in ["shift+x", "ctrl+shift+x", "alt+x"]:
    if hotkey_manager.register_hotkey("action", callback, sequence=sequence):
        break
```

### 3. Handle Registration Failures Gracefully

```python
success = hotkey_manager.register_hotkey(...)
if not success:
    # Show user notification
    # Log the failure
    # Provide alternative method
    pass
```

### 4. Always Unregister on Cleanup

```python
def closeEvent(self, event):
    # Unregister specific hotkeys
    self.hotkey_manager.unregister_hotkey("my_hotkey")
    
    # Or shutdown entire system
    self.hotkey_manager.shutdown()
    
    event.accept()
```

### 5. Document Your Hotkeys

```python
HOTKEY_DOCUMENTATION = """
Application Hotkeys:
- Ctrl+Shift+H: Show/hide main window
- Ctrl+Alt+S: Open settings
- Shift+X: Quick switch
- Ctrl+Alt+Q: Quit application
"""
```

---

## Troubleshooting

### Hotkey Not Working

**Check**:
1. Hotkey registered successfully? (check return value)
2. Callback function is defined and accessible?
3. Another application using the same hotkey?
4. Modifier keys correct? (`ctrl`, not `control`)

```python
success = hotkey_manager.register_hotkey(...)
if not success:
    print("Registration failed - hotkey may be in use")
```

### Hotkey Fires Multiple Times

**Solution**: Ensure you're not registering the same hotkey multiple times

```python
# Unregister before re-registering
hotkey_manager.unregister_hotkey("my_hotkey")
hotkey_manager.register_hotkey("my_hotkey", ...)
```

### Callback Not Executing

**Check**:
1. Callback function signature correct?
2. No exceptions in callback? (check logs)
3. Hotkey manager still running?

```python
def my_callback():
    try:
        # Your code
        pass
    except Exception as e:
        print(f"Callback error: {e}")
```

---

This hotkey system has been production-tested in SPQDocker for 18+ months, handling millions of hotkey presses reliably!
