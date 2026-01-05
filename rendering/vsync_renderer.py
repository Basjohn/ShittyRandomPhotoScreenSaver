"""True VSync-driven renderer with dedicated GL context on render thread.

This module implements a proper VSync rendering system that:
1. Uses Qt's threaded QOpenGLWidget pattern with context migration
2. Render thread grabs context, renders, calls swapBuffers (blocks on VSync)
3. Uses QOpenGLWidget's aboutToCompose/frameSwapped signals for sync
4. Achieves true VSync timing by blocking on swapBuffers

The key insight is that QOpenGLWidget already supports threaded rendering
via its aboutToCompose/frameSwapped signals - we just need to use them
correctly and call swapBuffers on the render thread.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Callable

from PySide6.QtCore import (
    QObject, QThread, QMutex, QMutexLocker, QWaitCondition,
    Signal, Slot, QMetaObject, Qt as QtCore,
)
from PySide6.QtGui import QGuiApplication
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from core.logging.logger import get_logger, is_perf_metrics_enabled

if TYPE_CHECKING:
    from rendering.gl_compositor import GLCompositorWidget

logger = get_logger(__name__)


@dataclass
class VSyncMetrics:
    """Metrics for VSync renderer performance."""
    frame_count: int = 0
    start_ts: float = field(default_factory=time.time)
    min_dt_ms: float = 0.0
    max_dt_ms: float = 0.0
    last_frame_ts: float = 0.0
    swap_count: int = 0
    missed_frames: int = 0
    
    def record_frame(self) -> float:
        """Record a frame and return dt in ms."""
        now = time.time()
        dt_ms = 0.0
        if self.last_frame_ts > 0:
            dt_ms = (now - self.last_frame_ts) * 1000.0
            if self.min_dt_ms == 0.0 or dt_ms < self.min_dt_ms:
                self.min_dt_ms = dt_ms
            if dt_ms > self.max_dt_ms:
                self.max_dt_ms = dt_ms
        self.last_frame_ts = now
        self.frame_count += 1
        return dt_ms
    
    def get_avg_fps(self) -> float:
        """Get average FPS."""
        elapsed = time.time() - self.start_ts
        if elapsed > 0:
            return self.frame_count / elapsed
        return 0.0


class VSyncRenderThread(QObject):
    """Render thread worker that owns the GL context and performs VSync rendering.
    
    This implements Qt's recommended threaded OpenGL pattern:
    1. Widget signals when composition is about to begin (lock renderer)
    2. Widget signals when frame is swapped (unlock, request next frame)
    3. Render thread grabs context, renders, releases context
    4. swapBuffers() blocks until VSync for precise timing
    """
    
    # Signal to request context from main thread
    context_wanted = Signal()
    # Signal when render is complete
    render_complete = Signal()
    
    def __init__(self, widget: QOpenGLWidget, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._widget = widget
        self._exiting = False
        self._inited = False
        
        # Synchronization primitives
        self._render_mutex = QMutex()
        self._grab_mutex = QMutex()
        self._grab_condition = QWaitCondition()
        
        # Metrics
        self._metrics = VSyncMetrics()
        
        # Render callback - called each frame with progress
        self._render_callback: Optional[Callable[[], None]] = None
        
        # Target FPS for frame skip detection
        self._target_fps: int = 60
        self._target_frame_time: float = 1.0 / 60.0
    
    def set_render_callback(self, callback: Optional[Callable[[], None]]) -> None:
        """Set the callback to invoke for each render frame."""
        self._render_callback = callback
    
    def set_target_fps(self, fps: int) -> None:
        """Set target FPS for metrics."""
        self._target_fps = max(1, fps)
        self._target_frame_time = 1.0 / self._target_fps
    
    def lock_renderer(self) -> None:
        """Lock the renderer (called from GUI thread before composition)."""
        self._render_mutex.lock()
    
    def unlock_renderer(self) -> None:
        """Unlock the renderer (called from GUI thread after composition)."""
        self._render_mutex.unlock()
    
    def grab_mutex(self) -> QMutex:
        """Get the grab mutex for context transfer."""
        return self._grab_mutex
    
    def grab_condition(self) -> QWaitCondition:
        """Get the grab condition for context transfer."""
        return self._grab_condition
    
    def prepare_exit(self) -> None:
        """Signal the render thread to exit."""
        self._exiting = True
        # Wake up any waiting threads
        with QMutexLocker(self._grab_mutex):
            self._grab_condition.wakeAll()
    
    def get_metrics(self) -> VSyncMetrics:
        """Get current metrics."""
        return self._metrics
    
    @Slot()
    def render(self) -> None:
        """Main render slot - called when a frame is requested.
        
        This implements the Qt threaded rendering pattern:
        1. Request context from GUI thread
        2. Wait for context to be transferred
        3. Make context current, call render callback, swap buffers
        4. Release context back to GUI thread
        
        The swapBuffers call BLOCKS until VSync - this is the key to
        achieving true VSync timing.
        """
        if self._exiting:
            return
        
        ctx = self._widget.context()
        if not ctx:
            logger.debug("[VSYNC] No context available")
            return
        
        # Request context from GUI thread
        self._grab_mutex.lock()
        self.context_wanted.emit()
        
        # Wait for context with timeout to prevent deadlock
        if not self._grab_condition.wait(self._grab_mutex, 100):  # 100ms timeout
            self._grab_mutex.unlock()
            logger.debug("[VSYNC] Context grab timeout")
            return
        
        with QMutexLocker(self._render_mutex):
            self._grab_mutex.unlock()
            
            if self._exiting:
                return
            
            # Verify context is on this thread
            current_thread = QThread.currentThread()
            if ctx.thread() != current_thread:
                logger.warning("[VSYNC] Context not on render thread (ctx=%s, current=%s)",
                              ctx.thread(), current_thread)
                return
            
            try:
                # Make context current - this binds the widget's FBO
                if not self._widget.makeCurrent():
                    logger.warning("[VSYNC] makeCurrent failed")
                    return
                
                # Initialize on first frame
                if not self._inited:
                    self._inited = True
                    self._metrics = VSyncMetrics()
                    logger.info("[VSYNC] Render thread initialized on thread %s", current_thread)
                
                # Record frame timing
                dt_ms = self._metrics.record_frame()
                
                # Check for missed frames (>1.5x target frame time)
                if dt_ms > self._target_frame_time * 1000.0 * 1.5:
                    self._metrics.missed_frames += 1
                
                # Call the render callback if set - this does the actual GL rendering
                # The callback should do the GL rendering directly, not call update()
                if self._render_callback is not None:
                    try:
                        self._render_callback()
                    except Exception as e:
                        logger.error("[VSYNC] Render callback error: %s", e)
                        import traceback
                        logger.error("[VSYNC] Traceback: %s", traceback.format_exc())
                
                # Swap buffers - THIS BLOCKS ON VSYNC
                # This is the key to true VSync - swapBuffers waits for vertical blank
                surface = ctx.surface()
                if surface is not None:
                    ctx.swapBuffers(surface)
                    self._metrics.swap_count += 1
                
                # Release context
                self._widget.doneCurrent()
                
            except Exception as e:
                logger.error("[VSYNC] Render error: %s", e)
                try:
                    self._widget.doneCurrent()
                except Exception:
                    pass
            
            # Move context back to GUI thread
            try:
                gui_thread = QGuiApplication.instance().thread()
                ctx.moveToThread(gui_thread)
            except Exception as e:
                logger.error("[VSYNC] Failed to move context back: %s", e)
        
        # Signal render complete
        self.render_complete.emit()


class VSyncGLWidget(QOpenGLWidget):
    """OpenGL widget with true VSync rendering on a dedicated thread.
    
    This widget overrides the standard QOpenGLWidget to perform rendering
    on a dedicated thread that owns the GL context. The render thread
    calls swapBuffers() directly, which blocks on VSync for precise timing.
    
    Usage:
        widget = VSyncGLWidget()
        widget.set_render_callback(my_render_function)
        widget.start_vsync_rendering()
    """
    
    # Signal to request a render frame
    render_requested = Signal()
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        
        self._thread: Optional[QThread] = None
        self._renderer: Optional[VSyncRenderThread] = None
        self._vsync_active = False
        self._render_callback: Optional[Callable[[], None]] = None
        self._target_fps: int = 60
    
    def set_render_callback(self, callback: Optional[Callable[[], None]]) -> None:
        """Set the callback to invoke for each render frame."""
        self._render_callback = callback
        if self._renderer is not None:
            self._renderer.set_render_callback(callback)
    
    def set_target_fps(self, fps: int) -> None:
        """Set target FPS."""
        self._target_fps = fps
        if self._renderer is not None:
            self._renderer.set_target_fps(fps)
    
    def start_vsync_rendering(self) -> bool:
        """Start VSync-driven rendering on dedicated thread.
        
        Returns:
            True if started successfully, False otherwise
        """
        if self._vsync_active:
            return True
        
        if self.context() is None:
            logger.warning("[VSYNC] Cannot start - no GL context")
            return False
        
        try:
            # Connect widget signals for synchronization
            self.aboutToCompose.connect(self._on_about_to_compose)
            self.frameSwapped.connect(self._on_frame_swapped)
            self.aboutToResize.connect(self._on_about_to_resize)
            self.resized.connect(self._on_resized)
            
            # Create render thread and worker
            self._thread = QThread()
            self._renderer = VSyncRenderThread(self)
            self._renderer.set_render_callback(self._render_callback)
            self._renderer.set_target_fps(self._target_fps)
            self._renderer.moveToThread(self._thread)
            
            # Connect signals
            self._thread.finished.connect(self._renderer.deleteLater)
            self.render_requested.connect(self._renderer.render)
            self._renderer.context_wanted.connect(self._grab_context)
            
            # Start thread
            self._thread.start()
            self._vsync_active = True
            
            logger.info("[VSYNC] Render thread started (target=%dHz)", self._target_fps)
            
            # Request first frame
            self.render_requested.emit()
            
            return True
            
        except Exception as e:
            logger.error("[VSYNC] Failed to start render thread: %s", e)
            self._cleanup_thread()
            return False
    
    def stop_vsync_rendering(self) -> None:
        """Stop VSync rendering and cleanup thread."""
        if not self._vsync_active:
            return
        
        self._vsync_active = False
        
        # Log final metrics
        if self._renderer is not None and is_perf_metrics_enabled():
            m = self._renderer.get_metrics()
            logger.info(
                "[PERF] [VSYNC] Stopped: frames=%d, avg_fps=%.1f, "
                "dt_min=%.1fms, dt_max=%.1fms, swaps=%d, missed=%d",
                m.frame_count, m.get_avg_fps(), m.min_dt_ms, m.max_dt_ms,
                m.swap_count, m.missed_frames
            )
        
        self._cleanup_thread()
        
        # Disconnect signals
        try:
            self.aboutToCompose.disconnect(self._on_about_to_compose)
            self.frameSwapped.disconnect(self._on_frame_swapped)
            self.aboutToResize.disconnect(self._on_about_to_resize)
            self.resized.disconnect(self._on_resized)
        except Exception:
            pass
        
        logger.info("[VSYNC] Render thread stopped")
    
    def is_vsync_active(self) -> bool:
        """Check if VSync rendering is active."""
        return self._vsync_active
    
    def get_vsync_metrics(self) -> Optional[VSyncMetrics]:
        """Get VSync metrics if active."""
        if self._renderer is not None:
            return self._renderer.get_metrics()
        return None
    
    def _cleanup_thread(self) -> None:
        """Cleanup render thread."""
        if self._renderer is not None:
            self._renderer.prepare_exit()
        
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(1000)  # Wait up to 1 second
            self._thread = None
        
        self._renderer = None
    
    def paintEvent(self, event) -> None:
        """Override paintEvent - do nothing when VSync is active.
        
        When VSync rendering is active, all rendering is done on the
        render thread. The GUI thread should not paint.
        """
        if self._vsync_active:
            return  # Render thread handles painting
        super().paintEvent(event)
    
    @Slot()
    def _on_about_to_compose(self) -> None:
        """Called when composition is about to begin - lock renderer."""
        if self._renderer is not None:
            self._renderer.lock_renderer()
    
    @Slot()
    def _on_frame_swapped(self) -> None:
        """Called when frame is swapped - unlock and request next frame."""
        if self._renderer is not None:
            self._renderer.unlock_renderer()
        
        # Request next frame - this drives the animation via VSync
        if self._vsync_active:
            self.render_requested.emit()
    
    @Slot()
    def _on_about_to_resize(self) -> None:
        """Called before resize - lock renderer."""
        if self._renderer is not None:
            self._renderer.lock_renderer()
    
    @Slot()
    def _on_resized(self) -> None:
        """Called after resize - unlock renderer."""
        if self._renderer is not None:
            self._renderer.unlock_renderer()
    
    @Slot()
    def _grab_context(self) -> None:
        """Transfer GL context to render thread."""
        if self._renderer is None:
            return
        
        self._renderer.lock_renderer()
        with QMutexLocker(self._renderer.grab_mutex()):
            # Move context to render thread
            self.context().moveToThread(self._thread)
            # Wake up render thread
            self._renderer.grab_condition().wakeAll()
        self._renderer.unlock_renderer()
    
    def closeEvent(self, event) -> None:
        """Handle close - stop rendering first."""
        self.stop_vsync_rendering()
        super().closeEvent(event)


class TrueVSyncRenderer:
    """Manager for true VSync rendering on GLCompositorWidget.
    
    This class integrates the VSyncRenderThread pattern with the existing
    GLCompositorWidget, enabling true VSync-driven rendering without
    replacing the entire widget hierarchy.
    """
    
    def __init__(self, compositor: "GLCompositorWidget"):
        self._compositor = compositor
        self._thread: Optional[QThread] = None
        self._renderer: Optional[VSyncRenderThread] = None
        self._active = False
        self._target_fps: int = 60
        
        # Render callback for the compositor
        self._render_callback: Optional[Callable[[], None]] = None
    
    def set_render_callback(self, callback: Optional[Callable[[], None]]) -> None:
        """Set the callback to invoke for each render frame."""
        self._render_callback = callback
        if self._renderer is not None:
            self._renderer.set_render_callback(callback)
    
    def set_target_fps(self, fps: int) -> None:
        """Set target FPS."""
        self._target_fps = max(1, fps)
        if self._renderer is not None:
            self._renderer.set_target_fps(self._target_fps)
    
    def start(self) -> bool:
        """Start true VSync rendering.
        
        Returns:
            True if started successfully, False otherwise
        """
        if self._active:
            return True
        
        if self._compositor.context() is None:
            logger.warning("[VSYNC] Cannot start - compositor has no GL context")
            return False
        
        try:
            # Connect compositor signals for synchronization
            self._compositor.aboutToCompose.connect(self._on_about_to_compose)
            self._compositor.frameSwapped.connect(self._on_frame_swapped)
            self._compositor.aboutToResize.connect(self._on_about_to_resize)
            self._compositor.resized.connect(self._on_resized)
            
            # Create render thread and worker
            self._thread = QThread()
            self._renderer = VSyncRenderThread(self._compositor)
            self._renderer.set_render_callback(self._render_callback)
            self._renderer.set_target_fps(self._target_fps)
            self._renderer.moveToThread(self._thread)
            
            # Connect signals
            self._thread.finished.connect(self._renderer.deleteLater)
            self._renderer.context_wanted.connect(self._grab_context)
            
            # Start thread
            self._thread.start()
            self._active = True
            
            logger.info("[VSYNC] True VSync renderer started (target=%dHz)", self._target_fps)
            
            return True
            
        except Exception as e:
            logger.error("[VSYNC] Failed to start true VSync renderer: %s", e)
            self._cleanup()
            return False
    
    def stop(self) -> None:
        """Stop VSync rendering."""
        if not self._active:
            return
        
        self._active = False
        
        # Log final metrics
        if self._renderer is not None and is_perf_metrics_enabled():
            m = self._renderer.get_metrics()
            logger.info(
                "[PERF] [VSYNC] True VSync stopped: frames=%d, avg_fps=%.1f, "
                "dt_min=%.1fms, dt_max=%.1fms, swaps=%d, missed=%d",
                m.frame_count, m.get_avg_fps(), m.min_dt_ms, m.max_dt_ms,
                m.swap_count, m.missed_frames
            )
        
        self._cleanup()
        
        # Disconnect signals
        try:
            self._compositor.aboutToCompose.disconnect(self._on_about_to_compose)
            self._compositor.frameSwapped.disconnect(self._on_frame_swapped)
            self._compositor.aboutToResize.disconnect(self._on_about_to_resize)
            self._compositor.resized.disconnect(self._on_resized)
        except Exception:
            pass
        
        logger.info("[VSYNC] True VSync renderer stopped")
    
    def request_frame(self) -> None:
        """Request a render frame."""
        if self._active and self._renderer is not None:
            # Invoke render on render thread
            QMetaObject.invokeMethod(
                self._renderer,
                "render",
                QtCore.ConnectionType.QueuedConnection,
            )
    
    def is_active(self) -> bool:
        """Check if VSync rendering is active."""
        return self._active
    
    def get_metrics(self) -> Optional[VSyncMetrics]:
        """Get VSync metrics if active."""
        if self._renderer is not None:
            return self._renderer.get_metrics()
        return None
    
    def _cleanup(self) -> None:
        """Cleanup render thread."""
        if self._renderer is not None:
            self._renderer.prepare_exit()
        
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(1000)
            self._thread = None
        
        self._renderer = None
    
    @Slot()
    def _on_about_to_compose(self) -> None:
        """Called when composition is about to begin."""
        if self._renderer is not None:
            self._renderer.lock_renderer()
    
    @Slot()
    def _on_frame_swapped(self) -> None:
        """Called when frame is swapped - request next frame."""
        if self._renderer is not None:
            self._renderer.unlock_renderer()
        
        # Request next frame - VSync drives the animation
        if self._active:
            self.request_frame()
    
    @Slot()
    def _on_about_to_resize(self) -> None:
        """Called before resize."""
        if self._renderer is not None:
            self._renderer.lock_renderer()
    
    @Slot()
    def _on_resized(self) -> None:
        """Called after resize."""
        if self._renderer is not None:
            self._renderer.unlock_renderer()
    
    @Slot()
    def _grab_context(self) -> None:
        """Transfer GL context to render thread."""
        if self._renderer is None or self._thread is None:
            return
        
        self._renderer.lock_renderer()
        with QMutexLocker(self._renderer.grab_mutex()):
            # Move context to render thread
            self._compositor.context().moveToThread(self._thread)
            # Wake up render thread
            self._renderer.grab_condition().wakeAll()
        self._renderer.unlock_renderer()
