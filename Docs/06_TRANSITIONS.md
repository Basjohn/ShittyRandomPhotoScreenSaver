# Transition Effects Implementation

**CRITICAL**: All transitions MUST use the centralized `AnimationManager` from `core/animation/`.  
Do NOT use raw `QPropertyAnimation`, `QTimer`, or manual animation loops.

## Base Transition

### Purpose
Abstract base class for all transition effects.  
**Uses**: `AnimationManager` for all animations.

### Implementation

```python
# transitions/base_transition.py

from abc import ABC, abstractmethod
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPixmap
from core.animation.animator import AnimationManager
from core.events import EventSystem

class BaseTransition(QObject, ABC):
    """Abstract base class for transitions - uses AnimationManager"""
    
    finished = Signal()
    progress = Signal(float)  # 0.0 to 1.0
    
    def __init__(self, target_widget, old_pixmap: QPixmap, new_pixmap: QPixmap, 
                 duration: float, animation_manager: AnimationManager):
        super().__init__()
        
        self.target_widget = target_widget
        self.old_pixmap = old_pixmap
        self.new_pixmap = new_pixmap
        self.duration = duration  # seconds
        self.animation_manager = animation_manager  # CENTRALIZED
        
        self.elapsed = 0.0
        self.is_running = False
        self._animation_id = None
    
    @abstractmethod
    def start(self):
        """Start the transition using AnimationManager"""
        pass
    
    @abstractmethod
    def stop(self):
        """Stop the transition"""
        if self._animation_id:
            self.animation_manager.cancel_animation(self._animation_id)
    
    def _on_animation_update(self, progress: float):
        """Called by AnimationManager on each frame"""
        self.elapsed = progress * self.duration
        self.progress.emit(progress)
    
    def _on_animation_complete(self):
        """Called by AnimationManager when animation completes"""
        self.is_running = False
        self.finished.emit()
```

---

## Crossfade Transition

### Purpose
Smooth opacity transition between images using AnimationManager.

### Implementation

```python
# transitions/crossfade.py

from PySide6.QtWidgets import QLabel, QGraphicsOpacityEffect
from PySide6.QtGui import QPixmap
from transitions.base_transition import BaseTransition
from core.animation.animator import AnimationManager
from core.animation.types import EasingCurve
from core.logging.logger import get_logger

logger = get_logger(__name__)

class CrossfadeTransition(BaseTransition):
    """Crossfade transition using centralized AnimationManager"""
    
    def __init__(self, target_widget, old_pixmap: QPixmap, new_pixmap: QPixmap, 
                 duration: float, animation_manager: AnimationManager):
        super().__init__(target_widget, old_pixmap, new_pixmap, duration, animation_manager)
        
        # Create overlay label for new image
        self.overlay_label = QLabel(target_widget)
        self.overlay_label.setGeometry(target_widget.geometry())
        self.overlay_label.setPixmap(new_pixmap)
        
        # Setup opacity effect
        self.opacity_effect = QGraphicsOpacityEffect()
        self.overlay_label.setGraphicsEffect(self.opacity_effect)
        self.opacity_effect.setOpacity(0.0)
        
        logger.debug(f"Crossfade transition created: {duration}s")
    
    def start(self):
        """Start crossfade using AnimationManager"""
        logger.debug("Crossfade started")
        self.is_running = True
        self.overlay_label.show()
        
        # Use centralized AnimationManager instead of raw QPropertyAnimation
        self._animation_id = self.animation_manager.animate_property(
            target=self.opacity_effect,
            property_name='opacity',
            start_value=0.0,
            end_value=1.0,
            duration=self.duration,
            easing=EasingCurve.IN_OUT_QUAD,
            on_update=self._on_animation_update,
            on_complete=self._on_animation_complete
        )
        self.animation.start()
    
    def stop(self):
        """Stop crossfade"""
        if self.is_running:
            self.animation.stop()
            self._cleanup()
    
    def update(self, delta_time: float):
        """Update (not needed for Qt animation)"""
        pass
    
    def _on_finished(self):
        """Animation finished"""
        logger.debug("Crossfade complete")
        
        # Set final image
        self.target_widget.setPixmap(self.new_pixmap)
        
        # Cleanup
        self._cleanup()
        
        self.is_running = False
        self.finished.emit()
    
    def _cleanup(self):
        """Cleanup overlay"""
        if self.overlay_label:
            self.overlay_label.deleteLater()
            self.overlay_label = None
```

---

## Slide Transition

### Purpose
Slide new image from a direction.

### Implementation

```python
# transitions/slide.py

from PySide6.QtCore import QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QPixmap
from transitions.base_transition import BaseTransition
import logging

logger = logging.getLogger("screensaver.transition.slide")

class SlideTransition(BaseTransition):
    """Slide transition"""
    
    DIRECTIONS = ['left', 'right', 'up', 'down']
    
    def __init__(self, target_widget, old_pixmap: QPixmap, new_pixmap: QPixmap, 
                 duration: float, direction: str = 'left'):
        super().__init__(target_widget, old_pixmap, new_pixmap, duration)
        
        self.direction = direction if direction in self.DIRECTIONS else 'left'
        
        # Create sliding label
        self.slide_label = QLabel(target_widget.parent())
        self.slide_label.setGeometry(target_widget.geometry())
        self.slide_label.setPixmap(new_pixmap)
        
        # Calculate start and end positions
        self.start_pos, self.end_pos = self._calculate_positions()
        self.slide_label.move(self.start_pos)
        
        # Animation
        self.animation = QPropertyAnimation(self.slide_label, b"pos")
        self.animation.setDuration(int(duration * 1000))
        self.animation.setStartValue(self.start_pos)
        self.animation.setEndValue(self.end_pos)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)
        self.animation.finished.connect(self._on_finished)
        
        logger.debug(f"Slide transition created: {direction}, {duration}s")
    
    def _calculate_positions(self):
        """Calculate start and end positions based on direction"""
        rect = self.target_widget.geometry()
        widget_pos = self.target_widget.pos()
        
        if self.direction == 'left':
            start = QPoint(rect.width(), widget_pos.y())
            end = widget_pos
        elif self.direction == 'right':
            start = QPoint(-rect.width(), widget_pos.y())
            end = widget_pos
        elif self.direction == 'up':
            start = QPoint(widget_pos.x(), rect.height())
            end = widget_pos
        else:  # down
            start = QPoint(widget_pos.x(), -rect.height())
            end = widget_pos
        
        return start, end
    
    def start(self):
        """Start slide"""
        logger.debug(f"Slide started: {self.direction}")
        self.is_running = True
        self.slide_label.show()
        self.slide_label.raise_()
        self.animation.start()
    
    def stop(self):
        """Stop slide"""
        if self.is_running:
            self.animation.stop()
            self._cleanup()
    
    def update(self, delta_time: float):
        """Update (not needed for Qt animation)"""
        pass
    
    def _on_finished(self):
        """Animation finished"""
        logger.debug("Slide complete")
        
        # Set final image
        self.target_widget.setPixmap(self.new_pixmap)
        
        # Cleanup
        self._cleanup()
        
        self.is_running = False
        self.finished.emit()
    
    def _cleanup(self):
        """Cleanup slide label"""
        if self.slide_label:
            self.slide_label.deleteLater()
            self.slide_label = None
```

---

## Diffuse Transition

### Purpose
Random pixel/block reveal.

### Implementation

```python
# transitions/diffuse.py

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel
from PySide6.QtGui import QPixmap, QPainter, QBitmap
from transitions.base_transition import BaseTransition
import random
import logging

logger = logging.getLogger("screensaver.transition.diffuse")

class DiffuseTransition(BaseTransition):
    """Diffuse transition with random reveal"""
    
    def __init__(self, target_widget, old_pixmap: QPixmap, new_pixmap: QPixmap, 
                 duration: float, block_size: int = 10):
        super().__init__(target_widget, old_pixmap, new_pixmap, duration)
        
        self.block_size = block_size
        
        # Calculate blocks
        width = new_pixmap.width()
        height = new_pixmap.height()
        
        self.blocks_x = width // block_size
        self.blocks_y = height // block_size
        self.total_blocks = self.blocks_x * self.blocks_y
        
        # Random order
        self.block_order = list(range(self.total_blocks))
        random.shuffle(self.block_order)
        
        self.blocks_revealed = 0
        
        # Create composite pixmap
        self.composite = QPixmap(old_pixmap)
        
        # Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self._reveal_blocks)
        
        # Calculate interval
        self.blocks_per_frame = max(1, self.total_blocks // int(duration * 60))
        self.interval = 16  # ~60 FPS
        
        logger.debug(f"Diffuse transition: {self.total_blocks} blocks, {self.blocks_per_frame} per frame")
    
    def start(self):
        """Start diffuse"""
        logger.debug("Diffuse started")
        self.is_running = True
        self.timer.start(self.interval)
    
    def stop(self):
        """Stop diffuse"""
        if self.is_running:
            self.timer.stop()
            self._cleanup()
    
    def update(self, delta_time: float):
        """Update (handled by timer)"""
        pass
    
    def _reveal_blocks(self):
        """Reveal next batch of blocks"""
        painter = QPainter(self.composite)
        
        blocks_to_reveal = min(self.blocks_per_frame, self.total_blocks - self.blocks_revealed)
        
        for _ in range(blocks_to_reveal):
            if self.blocks_revealed >= self.total_blocks:
                break
            
            block_idx = self.block_order[self.blocks_revealed]
            bx = block_idx % self.blocks_x
            by = block_idx // self.blocks_x
            
            x = bx * self.block_size
            y = by * self.block_size
            
            # Draw block from new image
            painter.drawPixmap(
                x, y,
                self.new_pixmap,
                x, y,
                self.block_size, self.block_size
            )
            
            self.blocks_revealed += 1
        
        painter.end()
        
        # Update display
        self.target_widget.setPixmap(self.composite)
        
        # Check completion
        if self.blocks_revealed >= self.total_blocks:
            self._on_finished()
        
        # Emit progress
        progress = self.blocks_revealed / self.total_blocks
        self.progress.emit(progress)
    
    def _on_finished(self):
        """Transition finished"""
        logger.debug("Diffuse complete")
        self.timer.stop()
        
        # Set final image
        self.target_widget.setPixmap(self.new_pixmap)
        
        self.is_running = False
        self.finished.emit()
    
    def _cleanup(self):
        """Cleanup"""
        pass
```

---

## Block Puzzle Flip Transition ⭐

### Purpose
3D flip effect with configurable grid (star feature).

### Implementation

```python
# transitions/block_puzzle_flip.py

from PySide6.QtCore import QTimer, QPropertyAnimation, QEasingCurve, Qt, QRect
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtGui import QPixmap, QTransform
from transitions.base_transition import BaseTransition
import random
import logging

logger = logging.getLogger("screensaver.transition.blockpuzzle")

class BlockPuzzleFlipTransition(BaseTransition):
    """Block puzzle flip transition with 3D effect"""
    
    def __init__(self, target_widget, old_pixmap: QPixmap, new_pixmap: QPixmap, 
                 duration: float, grid: tuple = (6, 6)):
        super().__init__(target_widget, old_pixmap, new_pixmap, duration)
        
        self.rows, self.cols = grid
        self.total_blocks = self.rows * self.cols
        
        # Create graphics scene
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene, target_widget.parent())
        self.view.setGeometry(target_widget.geometry())
        self.view.setStyleSheet("background: black; border: none;")
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Calculate block size
        self.block_width = old_pixmap.width() // self.cols
        self.block_height = old_pixmap.height() // self.rows
        
        # Create blocks
        self.blocks = []
        self._create_blocks()
        
        # Random flip order
        self.flip_order = list(range(self.total_blocks))
        random.shuffle(self.flip_order)
        
        # Timing
        self.block_duration = (duration * 1000) / self.total_blocks
        self.animations = []
        
        logger.debug(f"Block puzzle: {self.rows}x{self.cols} = {self.total_blocks} blocks")
    
    def _create_blocks(self):
        """Create block items"""
        for row in range(self.rows):
            for col in range(self.cols):
                x = col * self.block_width
                y = row * self.block_height
                
                # Extract block from old image
                old_block = self.old_pixmap.copy(
                    x, y,
                    self.block_width, self.block_height
                )
                
                # Extract block from new image
                new_block = self.new_pixmap.copy(
                    x, y,
                    self.block_width, self.block_height
                )
                
                # Create graphics item
                item = QGraphicsPixmapItem(old_block)
                item.setPos(x, y)
                self.scene.addItem(item)
                
                # Store block data
                self.blocks.append({
                    'item': item,
                    'old_pixmap': old_block,
                    'new_pixmap': new_block,
                    'flipped': False
                })
    
    def start(self):
        """Start block puzzle flip"""
        logger.debug("Block puzzle flip started")
        self.is_running = True
        self.view.show()
        self.view.raise_()
        
        # Schedule flips
        for idx, block_num in enumerate(self.flip_order):
            delay = int(idx * self.block_duration)
            QTimer.singleShot(delay, lambda b=block_num: self._flip_block(b))
    
    def stop(self):
        """Stop transition"""
        if self.is_running:
            for anim in self.animations:
                anim.stop()
            self._cleanup()
    
    def update(self, delta_time: float):
        """Update (handled by timers)"""
        pass
    
    def _flip_block(self, block_num: int):
        """Flip a single block"""
        if not self.is_running or block_num >= len(self.blocks):
            return
        
        block = self.blocks[block_num]
        if block['flipped']:
            return
        
        item = block['item']
        
        # Create flip animation using scale transform
        # Scale to 0 on X axis, then back to 1 with new pixmap
        
        # Phase 1: Scale down
        anim1 = QPropertyAnimation(item, b"scale")
        anim1.setDuration(int(self.block_duration * 0.5))
        anim1.setStartValue(1.0)
        anim1.setEndValue(0.0)
        anim1.setEasingCurve(QEasingCurve.InQuad)
        
        def on_halfway():
            # Swap pixmap at halfway point
            item.setPixmap(block['new_pixmap'])
        
        anim1.finished.connect(on_halfway)
        
        # Phase 2: Scale up
        anim2 = QPropertyAnimation(item, b"scale")
        anim2.setDuration(int(self.block_duration * 0.5))
        anim2.setStartValue(0.0)
        anim2.setEndValue(1.0)
        anim2.setEasingCurve(QEasingCurve.OutQuad)
        
        # Chain animations
        anim1.finished.connect(anim2.start)
        
        # Track completion
        def on_complete():
            block['flipped'] = True
            self._check_completion()
        
        anim2.finished.connect(on_complete)
        
        # Start
        anim1.start()
        self.animations.extend([anim1, anim2])
    
    def _check_completion(self):
        """Check if all blocks flipped"""
        if all(block['flipped'] for block in self.blocks):
            self._on_finished()
    
    def _on_finished(self):
        """Transition finished"""
        logger.debug("Block puzzle flip complete")
        
        # Set final image
        self.target_widget.setPixmap(self.new_pixmap)
        
        # Cleanup
        self._cleanup()
        
        self.is_running = False
        self.finished.emit()
    
    def _cleanup(self):
        """Cleanup graphics scene"""
        if self.view:
            self.view.deleteLater()
            self.view = None
        if self.scene:
            self.scene.deleteLater()
            self.scene = None
```

---

## Transition Factory

### Purpose
Create transition instances based on settings.

### Implementation

```python
# transitions/__init__.py

from transitions.crossfade import CrossfadeTransition
from transitions.slide import SlideTransition
from transitions.diffuse import DiffuseTransition
from transitions.block_puzzle_flip import BlockPuzzleFlipTransition

TRANSITION_TYPES = {
    'crossfade': CrossfadeTransition,
    'slide': SlideTransition,
    'diffuse': DiffuseTransition,
    'block_puzzle': BlockPuzzleFlipTransition,
}

def create_transition(transition_type: str, target_widget, old_pixmap, new_pixmap, settings):
    """
    Create transition instance.
    
    Args:
        transition_type: Type of transition
        target_widget: Widget to apply transition to
        old_pixmap: Previous image
        new_pixmap: New image
        settings: Settings dict with duration and options
        
    Returns:
        Transition instance
    """
    duration = settings.get('duration', 1.0)
    
    if transition_type == 'crossfade':
        return CrossfadeTransition(target_widget, old_pixmap, new_pixmap, duration)
    
    elif transition_type == 'slide':
        direction = settings.get('direction', 'left')
        return SlideTransition(target_widget, old_pixmap, new_pixmap, duration, direction)
    
    elif transition_type == 'diffuse':
        block_size = settings.get('block_size', 10)
        return DiffuseTransition(target_widget, old_pixmap, new_pixmap, duration, block_size)
    
    elif transition_type == 'block_puzzle':
        grid = settings.get('grid', (6, 6))
        return BlockPuzzleFlipTransition(target_widget, old_pixmap, new_pixmap, duration, grid)
    
    else:
        # Default to crossfade
        return CrossfadeTransition(target_widget, old_pixmap, new_pixmap, duration)
```

---

## Testing

```python
# tests/test_transitions.py

import pytest
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtGui import QPixmap
from transitions.crossfade import CrossfadeTransition
from transitions.slide import SlideTransition

@pytest.fixture
def app():
    """Qt application fixture"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app

def test_crossfade_creation(app):
    """Test crossfade transition creates correctly"""
    label = QLabel()
    old_pixmap = QPixmap(100, 100)
    new_pixmap = QPixmap(100, 100)
    
    transition = CrossfadeTransition(label, old_pixmap, new_pixmap, 1.0)
    
    assert transition is not None
    assert transition.duration == 1.0

def test_slide_creation(app):
    """Test slide transition creates correctly"""
    label = QLabel()
    old_pixmap = QPixmap(100, 100)
    new_pixmap = QPixmap(100, 100)
    
    transition = SlideTransition(label, old_pixmap, new_pixmap, 1.0, 'left')
    
    assert transition is not None
    assert transition.direction == 'left'
```

---

**Next Document**: `07_WIDGETS_AND_UI.md` - Overlay widgets and configuration UI
