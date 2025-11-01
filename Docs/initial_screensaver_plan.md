# Comprehensive Development Plan: Multi-Feature Photo Screensaver

## PyQt6 vs PySide6 Decision

### **PyQt6**
**Pros:**
- More mature documentation and community resources
- Historically better performance (marginal)
- Larger ecosystem of tutorials and examples
- Better Stack Overflow support

**Cons:**
- **Commercial license required** for commercial applications (GPL otherwise)
- Riverbank Computing's licensing can be restrictive
- Must comply with GPL if not paying for commercial license

### **PySide6 (Recommended)**
**Pros:**
- **LGPL license** - more permissive, can use in commercial/proprietary apps
- Official Qt Company bindings
- Free for commercial use without restrictions
- Better alignment with Qt's long-term roadmap
- Increasingly better documentation
- Same API as PyQt6 (mostly identical)

**Cons:**
- Slightly smaller community (but growing rapidly)
- Some niche features may lag behind PyQt6

### **Recommendation: PySide6**
For a screensaver you might distribute or sell, PySide6's LGPL license is safer and more flexible. The API is 95% identical to PyQt6, so switching later is trivial. Unless you need a specific PyQt6-only feature (rare), go with **PySide6**.

---

## Phase 0: Foundation & Architecture Review
**Priority: Critical - Do First**

### 1. Audit /ReusableModules
- Review custom thread manager implementation
- Examine resource manager capabilities (image caching, memory limits)
- Assess event manager for event-driven architecture
- Identify theme system for UI consistency
- Check for existing image processing utilities
- Look for configuration/settings management
- Identify logging/error handling systems

### 2. Architecture Design
```
ScreensaverApp/
├── main.py (entry point, command-line handling)
├── core/
│   ├── screensaver_engine.py (main controller)
│   ├── display_manager.py (multi-monitor handling)
│   ├── image_provider.py (abstract base for sources)
│   └── settings_manager.py (wraps QSettings + custom)
├── sources/
│   ├── folder_source.py (local folder scanning)
│   ├── rss_source.py (RSS feed parsing)
│   └── weather_source.py (weather widget data)
├── rendering/
│   ├── image_renderer.py (display modes: fill/fit/shrink)
│   ├── transition_engine.py (transition effects)
│   ├── pan_scan_animator.py (pan & scan logic)
│   └── widget_overlay.py (clock, weather widgets)
├── transitions/
│   ├── crossfade.py
│   ├── slide.py
│   ├── diffuse.py
│   └── block_puzzle_flip.py
├── ui/
│   ├── config_dialog.py (settings UI)
│   └── preview_window.py (preview mode)
└── utils/
    ├── image_processor.py (scaling, cropping)
    └── multi_monitor.py (screen geometry utilities)
```

### 3. Leverage Existing Modules
- **Custom Thread Manager**: Use for background image loading, RSS fetching, weather updates
- **Resource Manager**: Implement image caching, preloading, memory-aware cleanup
- **Event Manager**: Coordinate between image sources, transitions, and display updates
- **Themes**: Apply to configuration dialog

---

## Phase 1: Core Infrastructure

### 1.1 Display Manager (Multi-Monitor Support)
- Detect all connected monitors using `QApplication.screens()`
- Store screen geometries, DPI scaling factors
- Create fullscreen QWidget/QMainWindow per monitor
- Handle monitor hotplug events (connect/disconnect)
- Settings: Allow per-monitor image selection or synchronized display

### 1.2 Settings Manager
- Wrap QSettings for persistent storage
- Integrate with /ReusableModules config system if available
- Settings structure:
```python
{
    'sources': {
        'folders': [list of paths],
        'rss_feeds': [list of URLs],
        'weather_enabled': bool,
        'weather_api_key': str,
        'weather_location': str
    },
    'display': {
        'mode': 'fill' | 'fit' | 'shrink',
        'pan_scan_enabled': bool,
        'pan_scan_speed': float,
        'pan_scan_zoom': float (1.2 = 20% zoom)
    },
    'transitions': {
        'type': 'crossfade' | 'slide' | 'diffuse' | 'block_puzzle',
        'duration': float (seconds),
        'block_puzzle_grid': tuple (rows, cols),
        'block_puzzle_speed': float
    },
    'widgets': {
        'clock_enabled': bool,
        'clock_position': tuple (x, y),
        'clock_format': '12h' | '24h',
        'weather_enabled': bool,
        'weather_position': tuple (x, y)
    },
    'timing': {
        'image_duration': float (seconds),
        'slideshow_interval': float
    },
    'multi_monitor': {
        'mode': 'same' | 'different' | 'per_monitor_config',
        'monitors': {monitor_id: specific_settings}
    }
}
```

### 1.3 Command-Line Handler
```python
def parse_screensaver_args():
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg == '/s':
            return 'run'
        elif arg == '/c':
            return 'config'
        elif arg.startswith('/p'):
            hwnd = int(sys.argv[2]) if len(sys.argv) > 2 else None
            return ('preview', hwnd)
    return 'run'  # Default to run if no args
```

---

## Phase 2: Image Sources & Providers

### 2.1 Abstract Image Provider
```python
from abc import ABC, abstractmethod
from typing import List
from dataclasses import dataclass

@dataclass
class ImageMetadata:
    path: str
    width: int
    height: int
    aspect_ratio: float
    file_size: int
    modified_time: float

class ImageProvider(ABC):
    @abstractmethod
    async def get_images(self) -> List[ImageMetadata]:
        """Return list of available images"""
        pass
    
    @abstractmethod
    async def load_image(self, metadata: ImageMetadata) -> QPixmap:
        """Load actual image data"""
        pass
```

### 2.2 Folder Source
- Recursively scan designated folders
- Support image formats: JPG, PNG, BMP, GIF, WebP
- Use custom thread manager for background scanning
- Cache file paths, modification times
- Watch for folder changes (optional: QFileSystemWatcher)
- Metadata: path, dimensions, EXIF data, aspect ratio

### 2.3 RSS Feed Source
- Parse RSS/Atom feeds for image enclosures
- Support common feed formats (Media RSS)
- Use QNetworkAccessManager for async fetching
- Cache downloaded images using resource manager
- Handle feed errors gracefully
- Update interval: configurable (default: 1 hour)

### 2.4 Weather Widget Source
- Integrate OpenWeatherMap API (free tier) or wttr.in
- Fetch current conditions, temperature, icon
- Cache weather data (update every 30 minutes)
- Fallback gracefully if API unavailable
- Thread-safe updates via event manager

---

## Phase 3: Image Processing & Display Modes

### 3.1 Image Processor Utility

#### Fill Mode (Primary Focus - No Letterboxing/Pillarboxing)
```python
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap

def fill_image(pixmap: QPixmap, target_size: QSize) -> QPixmap:
    """
    Crop and scale to fill entire screen without distortion.
    Maintains aspect ratio, crops excess.
    """
    img_ratio = pixmap.width() / pixmap.height()
    screen_ratio = target_size.width() / target_size.height()
    
    if img_ratio > screen_ratio:
        # Image is wider - crop sides
        new_height = pixmap.height()
        new_width = int(new_height * screen_ratio)
        x_offset = (pixmap.width() - new_width) // 2
        cropped = pixmap.copy(x_offset, 0, new_width, new_height)
    else:
        # Image is taller - crop top/bottom
        new_width = pixmap.width()
        new_height = int(new_width / screen_ratio)
        y_offset = (pixmap.height() - new_height) // 2
        cropped = pixmap.copy(0, y_offset, new_width, new_height)
    
    return cropped.scaled(target_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
```

#### Fit Mode
- Scale to fit within screen bounds
- Maintain aspect ratio
- Center on screen
- Background: black or configurable color

#### Shrink Mode
- Only scale down if larger than screen
- Never upscale
- Center on screen

### 3.2 Pan & Scan Animator
```python
from PySide6.QtCore import QTimer, QPoint, QSize, QRect

class PanScanAnimator:
    def __init__(self, image: QPixmap, screen_size: QSize, settings):
        self.zoom_level = settings['pan_scan_zoom']  # e.g., 1.3 for 30% zoom
        self.speed = settings['pan_scan_speed']
        self.screen_size = screen_size
        self.zoomed_size = QSize(
            int(screen_size.width() * self.zoom_level),
            int(screen_size.height() * self.zoom_level)
        )
        self.zoomed_image = image.scaled(
            self.zoomed_size, 
            Qt.KeepAspectRatio, 
            Qt.SmoothTransformation
        )
        
        # Calculate pan range
        self.max_x = self.zoomed_size.width() - screen_size.width()
        self.max_y = self.zoomed_size.height() - screen_size.height()
        
        # Animation state
        self.current_offset = QPoint(0, 0)
        self.animation_timer = QTimer()
        self.start_time = 0
        self.total_duration = 10.0  # seconds
    
    def update_position(self, elapsed_time: float):
        """Smooth pan movement (linear, ease-in-out, or wave pattern)"""
        # Example: Diagonal sweep
        progress = (elapsed_time / self.total_duration) % 1.0
        self.current_offset.setX(int(self.max_x * progress))
        self.current_offset.setY(int(self.max_y * progress))
    
    def get_visible_region(self) -> QRect:
        return QRect(self.current_offset, self.screen_size)
```

---

## Phase 4: Transition Effects

### 4.1 Transition Engine
```python
class TransitionEngine:
    def __init__(self, resource_manager, event_manager):
        self.transitions = {
            'crossfade': CrossfadeTransition(),
            'slide': SlideTransition(),
            'diffuse': DiffuseTransition(),
            'block_puzzle': BlockPuzzleFlipTransition()
        }
    
    def execute(self, old_image, new_image, transition_type, duration, callback):
        transition = self.transitions[transition_type]
        transition.start(old_image, new_image, duration, callback)
```

### 4.2 Crossfade Transition
- Use QGraphicsOpacityEffect or manual alpha blending
- Interpolate opacity from 0.0 → 1.0 over duration
- 60 FPS for smoothness

### 4.3 Slide Transition
- Directions: left, right, up, down
- Use QPropertyAnimation on widget position
- Easing curves: QEasingCurve.InOutCubic

### 4.4 Diffuse Transition
- Random pixel/block reveal
- Create mask, progressively reveal new image
- Use QPainter with composition modes

### 4.5 Block Puzzle Flip Transition ⭐
```python
import random
from PySide6.QtCore import QTimer, QRect
from PySide6.QtGui import QPixmap

class BlockPuzzleFlipTransition:
    def __init__(self, grid_size=(6, 6), speed='medium'):
        self.rows, self.cols = grid_size
        self.total_blocks = self.rows * self.cols
        self.flip_order = self._generate_flip_order()
        self.flip_duration = self._calculate_flip_duration(speed)
    
    def _generate_flip_order(self):
        """Random order or pattern (wave, spiral, random)"""
        blocks = list(range(self.total_blocks))
        random.shuffle(blocks)
        return blocks
    
    def _calculate_flip_duration(self, speed):
        """Calculate time per block flip"""
        speed_map = {'slow': 3.0, 'medium': 2.0, 'fast': 1.0}
        return speed_map.get(speed, 2.0)
    
    def start_transition(self, old_pixmap, new_pixmap, screen_size):
        self.blocks = []
        block_width = screen_size.width() // self.cols
        block_height = screen_size.height() // self.rows
        
        for i in range(self.total_blocks):
            row = i // self.cols
            col = i % self.cols
            x = col * block_width
            y = row * block_height
            
            old_region = old_pixmap.copy(x, y, block_width, block_height)
            new_region = new_pixmap.copy(x, y, block_width, block_height)
            
            block = FlipBlock(
                QRect(x, y, block_width, block_height),
                old_region, 
                new_region
            )
            self.blocks.append(block)
        
        # Animate each block with staggered timing
        for idx, block_num in enumerate(self.flip_order):
            delay = idx * (self.flip_duration / self.total_blocks)
            QTimer.singleShot(
                int(delay * 1000), 
                lambda b=self.blocks[block_num]: b.flip()
            )

class FlipBlock:
    def __init__(self, rect, old_pixmap, new_pixmap):
        self.rect = rect
        self.old_pixmap = old_pixmap
        self.new_pixmap = new_pixmap
        self.angle = 0
    
    def flip(self):
        """Animate 3D rotation effect"""
        # Use QPropertyAnimation on custom transform
        # Or QPainter with perspective transform
        # Rotate 180° around vertical axis
        pass
```

**Implementation Details:**
- Use QGraphicsView with QGraphicsPixmapItem per block
- Apply QGraphicsRotation3D for realistic flip
- Progressive reveal: old image → flip → new image
- Configurable grid: 24 blocks (4×6) to 36 blocks (6×6)
- Speed presets: slow (3s), medium (2s), fast (1s)

---

## Phase 5: Widget Overlays

### 5.1 Clock Widget
```python
from PySide6.QtWidgets import QLabel
from PySide6.QtCore import QTimer
from datetime import datetime

class ClockWidget(QLabel):
    def __init__(self, position, format_24h=False):
        super().__init__()
        self.format = '%H:%M:%S' if format_24h else '%I:%M:%S %p'
        self.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 48px;
                font-weight: bold;
                background: rgba(0, 0, 0, 0.5);
                border-radius: 10px;
                padding: 10px;
            }
        """)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        self.move(position)
    
    def update_time(self):
        self.setText(datetime.now().strftime(self.format))
```

### 5.2 Weather Widget
```python
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout

class WeatherWidget(QWidget):
    def __init__(self, position, weather_source):
        super().__init__()
        # Display: icon, temperature, condition
        # Update every 30 minutes via weather_source
        # Fade in/out with image transitions
        # Position: corner or custom coordinates
        self.setup_ui()
        self.weather_source = weather_source
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_weather)
        self.update_timer.start(1800000)  # 30 minutes
    
    def setup_ui(self):
        layout = QVBoxLayout()
        self.temp_label = QLabel()
        self.condition_label = QLabel()
        self.icon_label = QLabel()
        layout.addWidget(self.icon_label)
        layout.addWidget(self.temp_label)
        layout.addWidget(self.condition_label)
        self.setLayout(layout)
        self.setStyleSheet("""
            QWidget {
                background: rgba(0, 0, 0, 0.5);
                border-radius: 10px;
                padding: 10px;
                color: white;
            }
        """)
    
    def update_weather(self):
        data = self.weather_source.get_current_weather()
        self.temp_label.setText(f"{data['temp']}°")
        self.condition_label.setText(data['condition'])
        # Update icon
```

---

## Phase 6: Multi-Monitor Coordination

### 6.1 Monitor Display Modes

**Same Image Mode:**
- Single image source
- Synchronized transitions across all monitors
- Shared pan/scan state

**Different Image Mode:**
- Separate image queues per monitor
- Independent transitions (can be offset or synchronized)
- Unique pan/scan states

**Per-Monitor Configuration:**
- Different folders per monitor
- Different transition types
- Independent timing

### 6.2 Implementation
```python
from PySide6.QtWidgets import QApplication

class MultiMonitorController:
    def __init__(self, settings, image_providers):
        self.screens = QApplication.screens()
        self.display_widgets = []
        
        for idx, screen in enumerate(self.screens):
            geometry = screen.geometry()
            widget = ScreensaverDisplay(geometry, screen)
            widget.showFullScreen()
            
            if settings['multi_monitor']['mode'] == 'same':
                # Share image source and sync transitions
                widget.set_image_source(image_providers[0])
            else:
                # Independent sources
                widget.set_image_source(image_providers[idx])
            
            self.display_widgets.append(widget)
    
    def sync_transition(self):
        """Trigger simultaneous transitions on all monitors"""
        for widget in self.display_widgets:
            widget.trigger_transition()
```

---

## Phase 7: Resource Management & Thread Safety

### 7.1 Image Caching Strategy
- Use custom resource manager from /ReusableModules
- LRU cache: Keep 10-20 images in memory (configurable)
- Preload next 3-5 images in queue using thread manager
- Monitor memory usage, evict if exceeds threshold
- Disk cache for RSS images (with expiration)

### 7.2 Thread Safety
- **Image Loading Thread**: Background loading via custom thread manager
- **RSS Fetching Thread**: Periodic feed updates
- **Weather Update Thread**: API calls every 30 minutes
- **Main Thread**: UI updates only
- Use event manager for cross-thread communication
- Qt signals/slots for thread-safe UI updates

```python
class ImageLoader:
    def __init__(self, thread_manager, resource_manager, event_manager):
        self.thread_manager = thread_manager
        self.resource_manager = resource_manager
        self.event_manager = event_manager
        
        # Subscribe to image request events
        self.event_manager.subscribe('image.request', self.load_image)
    
    def load_image(self, image_path):
        def _load():
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                self.resource_manager.cache_image(image_path, pixmap)
                self.event_manager.emit('image.loaded', pixmap)
        
        self.thread_manager.run_async(_load)
```

### 7.3 Resource Cleanup
```python
class ScreensaverEngine:
    def cleanup(self):
        # Stop all timers
        for timer in self.timers:
            timer.stop()
        
        # Clear image cache
        self.resource_manager.clear_cache()
        
        # Shutdown threads
        self.thread_manager.shutdown()
        
        # Close network connections
        self.network_manager.disconnect()
        
        # Release pixmaps
        for widget in self.display_widgets:
            widget.clear_image()
```

---

## Phase 8: Configuration UI

### 8.1 Settings Dialog
- Use existing theme system from /ReusableModules
- Tabbed interface:
  - **Sources Tab**: Folder selection, RSS feeds, weather setup
  - **Display Tab**: Fill/Fit/Shrink, pan & scan settings
  - **Transitions Tab**: Type, duration, block puzzle grid
  - **Widgets Tab**: Clock, weather widget configuration
  - **Multi-Monitor Tab**: Per-monitor settings
  - **Advanced Tab**: Cache size, thread limits, logging

### 8.2 Preview Mode
- Embedded preview in settings dialog
- Handle `/p <hwnd>` argument
- Render miniature screensaver in provided window handle
- Use QWindow.fromWinId(hwnd) on Windows

---

## Phase 9: Testing & Optimization

### 9.1 Testing Checklist
- [ ] Single monitor operation
- [ ] Multi-monitor with same images
- [ ] Multi-monitor with different images
- [ ] All transition types smooth at 60 FPS
- [ ] Pan & scan without stuttering
- [ ] RSS feed error handling
- [ ] Weather API fallback
- [ ] Memory leak testing (long-duration runs)
- [ ] Thread deadlock testing
- [ ] Settings persistence
- [ ] Preview mode in Windows settings
- [ ] Monitor hotplug handling

### 9.2 Performance Optimization
- Profile with cProfile, memory_profiler
- Optimize block puzzle flip (GPU acceleration if needed)
- Reduce QPixmap conversions
- Use QPixmapCache for small elements (icons, weather)
- Implement lazy loading for large image folders
- Debounce RSS/weather updates
- Use Qt's graphics hardware acceleration

---

## Phase 10: Packaging & Deployment

### 10.1 PyInstaller Configuration
```python
# screensaver.spec
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('ReusableModules', 'ReusableModules'),
        ('config', 'config'),
        ('assets', 'assets')  # Icons, fonts, etc.
    ],
    hiddenimports=[
        'PySide6.QtNetwork',
        'PIL._imaging',  # If using Pillow
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PhotoScreensaver',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    icon='icon.ico'
)
```

### 10.2 Installation
```batch
# Build script
pyinstaller --clean screensaver.spec
rename dist\PhotoScreensaver.exe PhotoScreensaver.scr
copy PhotoScreensaver.scr %SYSTEMROOT%\System32\
```

---

## Phase 11: Modularity Considerations

### Modularity works excellently with screensavers

**Benefits:**
- ✅ Easier testing of individual components
- ✅ Reusable transition effects
- ✅ Swappable image sources
- ✅ Clean separation of concerns
- ✅ Easier to extend (new transitions, sources)

**Best Practices:**
- Keep core engine independent of specific sources
- Use dependency injection for providers
- Abstract interfaces for all major components
- Plugin architecture for transitions (load dynamically)

**Example Plugin System:**
```python
from abc import ABC, abstractmethod
import os
import importlib

class TransitionPlugin(ABC):
    @property
    def name(self) -> str:
        pass
    
    @abstractmethod
    def execute(self, old, new, duration, callback):
        pass

# Auto-discover transitions
def load_transitions(transitions_dir):
    plugins = {}
    for file in os.listdir(transitions_dir):
        if file.endswith('.py') and not file.startswith('__'):
            module = importlib.import_module(f'transitions.{file[:-3]}')
            for item in dir(module):
                obj = getattr(module, item)
                if isinstance(obj, type) and issubclass(obj, TransitionPlugin):
                    instance = obj()
                    plugins[instance.name] = instance
    return plugins
```

---

## Recommended Development Order

1. ✅ **Audit /ReusableModules** (Day 1)
2. **Core infrastructure + single monitor** (Week 1)
3. **Folder source + basic display modes** (Week 1)
4. **Simple transitions (crossfade, slide)** (Week 2)
5. **Multi-monitor support** (Week 2)
6. **Pan & scan animator** (Week 3)
7. **Block puzzle flip transition** (Week 3-4)
8. **RSS source + weather widget** (Week 4)
9. **Configuration UI** (Week 5)
10. **Testing & optimization** (Week 6)
11. **Packaging & deployment** (Week 6)

---

## Additional Implementation Notes

### Error Handling Strategy
- Graceful degradation for missing images
- Fallback images for failed loads
- Log errors without crashing screensaver
- User-friendly error messages in config UI

### Performance Targets
- 60 FPS transitions on 1080p displays
- < 500MB memory usage for typical operation
- < 2 second startup time
- Smooth operation on dual 4K monitors

### Accessibility Considerations
- High contrast clock/weather widgets
- Configurable font sizes
- Keyboard shortcuts in config UI
- Screen reader support for settings

---

## Future Enhancement Ideas

- **Video support**: MP4, WebM playback
- **Live photo support**: Animated HEIC/Motion Photos
- **Social media integration**: Instagram, Flickr feeds
- **AI features**: Auto-categorization, smart cropping
- **Music visualization**: Audio-reactive transitions
- **3D effects**: Parallax, depth mapping
- **Remote control**: Mobile app for configuration
- **Cloud sync**: Settings across devices

---

This comprehensive plan provides a complete roadmap for building a professional, feature-rich photo screensaver with all requested capabilities while maintaining modularity and leveraging your existing systems.