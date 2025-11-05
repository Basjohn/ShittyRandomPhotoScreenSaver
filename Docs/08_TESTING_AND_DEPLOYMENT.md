# Testing and Deployment

## Testing Strategy

### Unit Tests
Test individual components in isolation using pytest.

### Test Structure
```
tests/
├── __init__.py
├── conftest.py                 # Shared fixtures
├── test_threading.py           # ThreadManager tests
├── test_resources.py           # ResourceManager tests
├── test_events.py              # EventSystem tests
├── test_settings.py            # SettingsManager tests
├── test_image_processor.py     # Image processing tests
├── test_transitions.py         # Transition tests
├── test_sources.py             # Image source tests
└── test_integration.py         # Integration tests
```

### Logging-First Testing Policy
**CRITICAL**: Terminal output is unreliable. Always use logging.

#### PowerShell Pytest Pattern
```powershell
# Start pytest with logging to file
$job = Start-Job -ScriptBlock { 
    pytest -vv --maxfail=2 --log-file=pytest.log --log-file-level=DEBUG *>&1 | Out-File -FilePath pytest_output.log -Encoding utf8 
};

# Wait for up to 30s
$null = Wait-Job -Id $job.Id -Timeout 30;

# If still running, stop it
if ($job.State -ne 'Completed') {
    Stop-Job -Id $job.Id -ErrorAction SilentlyContinue;
}

# Always remove the job object
Remove-Job -Id $job.Id -ErrorAction SilentlyContinue;

# Read the log
if (Test-Path pytest.log) {
    Get-Content pytest.log -Tail 50;
} else {
    Write-Host "pytest.log not found - test may have failed to start";
}
```

---

## Test Fixtures

### conftest.py

```python
# tests/conftest.py

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

@pytest.fixture
def qt_app():
    """Qt application fixture"""
    from PySide6.QtWidgets import QApplication
    
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    
    yield app
    
    # Cleanup
    app.processEvents()

@pytest.fixture
def settings_manager():
    """SettingsManager fixture"""
    from core.settings import SettingsManager
    
    sm = SettingsManager()
    yield sm
    
    # Cleanup
    sm.clear()

@pytest.fixture
def thread_manager():
    """ThreadManager fixture"""
    from core.threading import ThreadManager
    
    tm = ThreadManager()
    yield tm
    
    # Cleanup
    tm.shutdown()

@pytest.fixture
def resource_manager():
    """ResourceManager fixture"""
    from core.resources import ResourceManager
    
    rm = ResourceManager()
    yield rm
    
    # Cleanup
    rm.shutdown()

@pytest.fixture
def event_system():
    """EventSystem fixture"""
    from core.events import EventSystem
    
    es = EventSystem()
    yield es
    
    # Cleanup
    es.clear()

@pytest.fixture
def temp_image(tmp_path):
    """Create temporary test image"""
    from PySide6.QtGui import QPixmap
    
    img_path = tmp_path / "test.jpg"
    pixmap = QPixmap(800, 600)
    pixmap.save(str(img_path), "JPG")
    
    return str(img_path)
```

---

## Core Module Tests

### test_threading.py

```python
# tests/test_threading.py

import pytest
import time
from core.threading import ThreadManager, ThreadPoolType

def test_thread_manager_initialization(resource_manager):
    """Test ThreadManager initializes"""
    tm = ThreadManager(resource_manager=resource_manager)
    assert tm is not None
    tm.shutdown()

def test_submit_task(thread_manager):
    """Test task submission"""
    result = []
    
    def task(x):
        return x * 2
    
    def callback(task_result):
        result.append(task_result.result)
    
    thread_manager.submit_task(ThreadPoolType.COMPUTE, task, 5, callback=callback)
    
    # Wait for completion
    time.sleep(0.5)
    
    assert len(result) == 1
    assert result[0] == 10

def test_ui_thread_dispatch(thread_manager, qt_app):
    """Test UI thread dispatch"""
    result = []
    
    def ui_task():
        result.append("executed")
    
    thread_manager.run_on_ui_thread(ui_task)
    
    # Process events
    qt_app.processEvents()
    
    assert result == ["executed"]
```

### test_resources.py

```python
# tests/test_resources.py

import pytest
from core.resources import ResourceManager, ResourceType

def test_resource_registration(resource_manager):
    """Test resource registration"""
    obj = object()
    rid = resource_manager.register(obj, ResourceType.CUSTOM, "Test object")
    
    assert rid is not None
    assert resource_manager.get(rid) is obj

def test_resource_cleanup(resource_manager):
    """Test resource cleanup"""
    cleanup_called = []
    
    def cleanup(obj):
        cleanup_called.append(True)
    
    obj = object()
    resource_manager.register(obj, ResourceType.CUSTOM, "Test", cleanup_handler=cleanup)
    
    resource_manager.shutdown()
    
    assert len(cleanup_called) == 1

def test_qt_widget_registration(resource_manager, qt_app):
    """Test Qt widget registration"""
    from PySide6.QtWidgets import QLabel
    
    label = QLabel("Test")
    rid = resource_manager.register_qt(label, ResourceType.GUI_COMPONENT, "Label")
    
    assert rid is not None
```

### test_events.py

```python
# tests/test_events.py

import pytest
from core.events import EventSystem

def test_subscribe_and_publish(event_system):
    """Test event subscription and publishing"""
    received = []
    
    def handler(event):
        received.append(event.data)
    
    event_system.subscribe("test.event", handler)
    event_system.publish("test.event", data={"test": True})
    
    assert len(received) == 1
    assert received[0] == {"test": True}

def test_event_priority(event_system):
    """Test event handler priority"""
    order = []
    
    event_system.subscribe("test", lambda e: order.append(2), priority=50)
    event_system.subscribe("test", lambda e: order.append(1), priority=100)
    event_system.subscribe("test", lambda e: order.append(3), priority=10)
    
    event_system.publish("test")
    
    assert order == [1, 2, 3]

def test_unsubscribe(event_system):
    """Test unsubscribing"""
    received = []
    
    sub_id = event_system.subscribe("test", lambda e: received.append(1))
    event_system.publish("test")
    
    event_system.unsubscribe(sub_id)
    event_system.publish("test")
    
    assert len(received) == 1
```

### test_settings.py

```python
# tests/test_settings.py

import pytest
from core.settings import SettingsManager

def test_get_set(settings_manager):
    """Test get and set"""
    settings_manager.set("test.key", "value")
    assert settings_manager.get("test.key") == "value"

def test_get_with_default(settings_manager):
    """Test get with default"""
    value = settings_manager.get("nonexistent", "default")
    assert value == "default"

def test_save_load(settings_manager, tmp_path):
    """Test save and load"""
    # Set value
    settings_manager.set("test.key", "value")
    settings_manager.save()
    
    # Create new manager
    sm2 = SettingsManager()
    sm2.load()
    
    assert sm2.get("test.key") == "value"
```

---

## Image Processing Tests

### test_image_processor.py

```python
# tests/test_image_processor.py

import pytest
from PySide6.QtGui import QPixmap
from PySide6.QtCore import QSize
from rendering.image_processor import ImageProcessor
from rendering.display_modes import DisplayMode

def test_fill_mode(qt_app):
    """Test fill mode processing"""
    processor = ImageProcessor()
    
    pixmap = QPixmap(2000, 1000)
    target = QSize(1920, 1080)
    
    result = processor.process_image(pixmap, target, DisplayMode.FILL)
    
    assert result.width() == 1920
    assert result.height() == 1080

def test_fit_mode(qt_app):
    """Test fit mode processing"""
    processor = ImageProcessor()
    
    pixmap = QPixmap(1000, 2000)
    target = QSize(1920, 1080)
    
    result = processor.process_image(pixmap, target, DisplayMode.FIT)
    
    assert result.width() == 1920
    assert result.height() == 1080

def test_shrink_mode_no_upscale(qt_app):
    """Test shrink mode doesn't upscale"""
    processor = ImageProcessor()
    
    pixmap = QPixmap(800, 600)
    target = QSize(1920, 1080)
    
    result = processor.process_image(pixmap, target, DisplayMode.SHRINK)
    
    # Result should contain original size image centered
    assert result.width() == 1920
    assert result.height() == 1080
```

---

## Source Tests

### test_sources.py

```python
# tests/test_sources.py

import pytest
from pathlib import Path
from sources.folder_source import FolderSource

def test_folder_source_initialization(tmp_path):
    """Test folder source initialization"""
    source = FolderSource([str(tmp_path)], None, None)
    assert source is not None

def test_folder_scan(tmp_path, temp_image):
    """Test folder scanning"""
    source = FolderSource([str(tmp_path)], None, None)
    images = source.get_images()
    
    # Should find at least the test image
    assert len(images) >= 1

def test_supported_extensions():
    """Test supported extensions"""
    assert '.jpg' in FolderSource.SUPPORTED_EXTENSIONS
    assert '.png' in FolderSource.SUPPORTED_EXTENSIONS
    assert '.bmp' in FolderSource.SUPPORTED_EXTENSIONS
```

---

## Integration Tests

### test_integration.py

```python
# tests/test_integration.py

import pytest
import time
from engine.screensaver_engine import ScreensaverEngine

def test_engine_initialization(qt_app):
    """Test engine initializes all systems"""
    engine = ScreensaverEngine()
    
    assert engine.resource_manager is not None
    assert engine.thread_manager is not None
    assert engine.event_system is not None
    assert engine.settings_manager is not None
    
    engine.stop()

def test_full_workflow(qt_app, tmp_path, temp_image):
    """Test complete workflow"""
    # Setup settings
    from core.settings import SettingsManager
    
    settings = SettingsManager()
    settings.set('sources.folders', [str(tmp_path)])
    settings.set('sources.mode', 'folders')
    settings.set('timing.image_duration', 1.0)
    settings.save()
    
    # Create engine
    engine = ScreensaverEngine()
    
    # Start (don't actually show UI in test)
    # engine.start()  # Would show fullscreen
    
    # Verify components initialized
    assert len(engine.image_sources) > 0
    
    # Cleanup
    engine.stop()
```

---

## Running Tests

### Run All Tests
```powershell
$job = Start-Job -ScriptBlock { 
    pytest -vv --log-file=pytest.log --log-file-level=DEBUG *>&1 | Out-File pytest_output.log -Encoding utf8 
};
$null = Wait-Job -Id $job.Id -Timeout 30;
if ($job.State -ne 'Completed') { Stop-Job -Id $job.Id -ErrorAction SilentlyContinue; }
Remove-Job -Id $job.Id -ErrorAction SilentlyContinue;
Get-Content pytest.log -Tail 50;
```

### Run Specific Test File
```powershell
$job = Start-Job -ScriptBlock { 
    pytest tests/test_threading.py -vv --log-file=pytest.log *>&1 | Out-File pytest_output.log -Encoding utf8 
};
$null = Wait-Job -Id $job.Id -Timeout 20;
if ($job.State -ne 'Completed') { Stop-Job -Id $job.Id -ErrorAction SilentlyContinue; }
Remove-Job -Id $job.Id -ErrorAction SilentlyContinue;
Get-Content pytest.log -Tail 30;
```

### Run Single Test
```powershell
$job = Start-Job -ScriptBlock { 
    pytest tests/test_threading.py::test_submit_task -vv --log-file=pytest.log *>&1 | Out-File pytest_output.log -Encoding utf8 
};
$null = Wait-Job -Id $job.Id -Timeout 20;
if ($job.State -ne 'Completed') { Stop-Job -Id $job.Id -ErrorAction SilentlyContinue; }
Remove-Job -Id $job.Id -ErrorAction SilentlyContinue;
Get-Content pytest.log;
```

---

## Deployment

### Dependencies

#### requirements.txt
```txt
PySide6>=6.5.0
requests>=2.31.0
pytz>=2023.3
pytest>=7.4.0
pytest-qt>=4.2.0
```

### Building for Windows

#### PyInstaller Spec File
```python
# screensaver.spec

# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('themes/dark.qss', 'themes'),
    ],
    hiddenimports=[
        'PySide6.QtNetwork',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ShittyRandomPhotoScreenSaver',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico'  # Optional
)
```

#### Build Script
```powershell
# build.ps1

Write-Host "Building screensaver..."

# Clean previous build
if (Test-Path "dist") {
    Remove-Item -Recurse -Force "dist"
}
if (Test-Path "build") {
    Remove-Item -Recurse -Force "build"
}

# Build with PyInstaller
pyinstaller --clean screensaver.spec

if ($LASTEXITCODE -eq 0) {
    # Rename .exe to .scr
    $exePath = "dist\ShittyRandomPhotoScreenSaver.exe"
    $scrPath = "dist\ShittyRandomPhotoScreenSaver.scr"
    
    if (Test-Path $exePath) {
        Move-Item -Force $exePath $scrPath
        Write-Host "Build successful: $scrPath"
    }
} else {
    Write-Host "Build failed!"
    exit 1
}
```

### Installation

#### Manual Installation
```powershell
# Copy to System32
Copy-Item "dist\ShittyRandomPhotoScreenSaver.scr" "$env:SystemRoot\System32\"

# Or user directory
Copy-Item "dist\ShittyRandomPhotoScreenSaver.scr" "$env:USERPROFILE\ShittyRandomPhotoScreenSaver.scr"
```

#### Test Installation
```powershell
# Test run mode
.\ShittyRandomPhotoScreenSaver.scr /s

# Test config mode
.\ShittyRandomPhotoScreenSaver.scr /c

# Test preview mode (need window handle)
.\ShittyRandomPhotoScreenSaver.scr /p 12345
```

---

## Debug Mode

### Enable Debug Logging
```python
# main.py

import sys
from core.logging import setup_logging

def main():
    # Check for debug flag
    debug = '--debug' in sys.argv
    
    # Setup logging
    setup_logging(debug=debug)
    
    # ...rest of main
```

### Run with Debug
```powershell
.\ShittyRandomPhotoScreenSaver.scr /s --debug
```

---

## Performance Testing

### Memory Profiling
```python
# tests/test_performance.py

import pytest
from memory_profiler import profile

@profile
def test_memory_usage():
    """Test memory usage over time"""
    from engine.screensaver_engine import ScreensaverEngine
    
    engine = ScreensaverEngine()
    # Simulate running
    # ...
    engine.stop()
```

### Long-Duration Test
```python
def test_24_hour_stability():
    """Test 24-hour stability"""
    # This would be run manually
    import time
    
    engine = ScreensaverEngine()
    engine.start()
    
    # Run for 24 hours
    time.sleep(24 * 60 * 60)
    
    engine.stop()
```

---

**Next Document**: `09_IMPLEMENTATION_ORDER.md` - Step-by-step implementation guide
