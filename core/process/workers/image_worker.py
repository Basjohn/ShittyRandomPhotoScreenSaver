"""
Image Worker for decode/prescale operations.

Runs in a separate process to decode and prescale images using PIL,
avoiding blocking the UI thread. Results are returned via queue or
shared memory for large images.

Key responsibilities:
- Decode images from disk (JPEG, PNG, WebP, etc.)
- Prescale to target dimensions using Lanczos
- Apply sharpening for downscaled images
- Return RGBA data for Qt consumption
"""
from __future__ import annotations

import os
import time
import uuid
from multiprocessing import Queue
from multiprocessing.shared_memory import SharedMemory
from typing import Optional, Tuple

from core.process.types import (
    MessageType,
    WorkerMessage,
    WorkerResponse,
    WorkerType,
)
from core.process.workers.base import BaseWorker

try:
    from PIL import Image, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class ImageWorker(BaseWorker):
    """
    Worker for image decode and prescale operations.
    
    Handles:
    - IMAGE_DECODE: Decode image from path
    - IMAGE_PRESCALE: Decode and prescale to target size
    
    Returns processed RGBA bytes that can be converted to QImage
    on the UI thread. Uses shared memory for large images (>5MB)
    to avoid queue serialization overhead.
    """
    
    # Quality settings
    LANCZOS_RESAMPLE = Image.Resampling.LANCZOS if PIL_AVAILABLE else None
    SHARPEN_THRESHOLD = 0.5  # Apply sharpening when scale < 0.5
    
    # Shared memory threshold: 2MB (lowered from 5MB to catch 2560x1438 images)
    # 2560x1438 RGBA = 14.7MB, so this threshold ensures shared memory is used
    SHARED_MEMORY_THRESHOLD = 2 * 1024 * 1024
    
    def __init__(self, request_queue: Queue, response_queue: Queue):
        super().__init__(request_queue, response_queue)
        self._decode_count = 0
        self._prescale_count = 0
        self._total_decode_ms = 0.0
        self._total_prescale_ms = 0.0
        self._shared_memories: list[SharedMemory] = []  # Track for cleanup
    
    @property
    def worker_type(self) -> WorkerType:
        return WorkerType.IMAGE
    
    def handle_message(self, msg: WorkerMessage) -> Optional[WorkerResponse]:
        """Handle image processing messages."""
        if msg.msg_type == MessageType.IMAGE_DECODE:
            return self._handle_decode(msg)
        elif msg.msg_type == MessageType.IMAGE_PRESCALE:
            return self._handle_prescale(msg)
        elif msg.msg_type == MessageType.CONFIG_UPDATE:
            return self._handle_config(msg)
        else:
            return WorkerResponse(
                msg_type=MessageType.ERROR,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=False,
                error=f"Unknown message type: {msg.msg_type}",
            )
    
    def _handle_decode(self, msg: WorkerMessage) -> WorkerResponse:
        """Decode an image from disk."""
        path = msg.payload.get("path")
        if not path:
            return WorkerResponse(
                msg_type=MessageType.ERROR,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=False,
                error="Missing 'path' in payload",
            )
        
        if not os.path.exists(path):
            return WorkerResponse(
                msg_type=MessageType.IMAGE_RESULT,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=False,
                error=f"File not found: {path}",
            )
        
        start = time.time()
        try:
            img = Image.open(path)
            img.load()  # Force decode
            
            # Convert to RGBA for consistent handling
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            
            width, height = img.size
            rgba_data = img.tobytes("raw", "RGBA")
            
            decode_ms = (time.time() - start) * 1000
            self._decode_count += 1
            self._total_decode_ms += decode_ms
            
            return WorkerResponse(
                msg_type=MessageType.IMAGE_RESULT,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=True,
                payload={
                    "path": path,
                    "width": width,
                    "height": height,
                    "format": "RGBA",
                    "rgba_data": rgba_data,
                    "cache_key": path,
                },
                processing_time_ms=decode_ms,
            )
            
        except Exception as e:
            return WorkerResponse(
                msg_type=MessageType.IMAGE_RESULT,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=False,
                error=f"Decode failed: {e}",
            )
    
    def _handle_prescale(self, msg: WorkerMessage) -> WorkerResponse:
        """Decode and prescale an image."""
        path = msg.payload.get("path")
        target_width = msg.payload.get("target_width", 0)
        target_height = msg.payload.get("target_height", 0)
        mode = msg.payload.get("mode", "fill")  # fill, fit, shrink
        use_lanczos = msg.payload.get("use_lanczos", True)
        sharpen = msg.payload.get("sharpen", True)
        
        if not path:
            return WorkerResponse(
                msg_type=MessageType.ERROR,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=False,
                error="Missing 'path' in payload",
            )
        
        if not os.path.exists(path):
            return WorkerResponse(
                msg_type=MessageType.IMAGE_RESULT,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=False,
                error=f"File not found: {path}",
            )
        
        if target_width <= 0 or target_height <= 0:
            return WorkerResponse(
                msg_type=MessageType.ERROR,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=False,
                error=f"Invalid target size: {target_width}x{target_height}",
            )
        
        # Send WORKER_BUSY to prevent heartbeat timeout during long processing
        self._send_busy_notification(msg.correlation_id)
        
        start = time.time()
        try:
            # Decode
            img = Image.open(path)
            img.load()
            original_size = img.size
            
            # Convert to RGBA
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            
            # Calculate scale based on mode
            scaled_size = self._calculate_scale_size(
                original_size, (target_width, target_height), mode
            )
            
            # Prescale if needed
            if scaled_size != original_size:
                resample = self.LANCZOS_RESAMPLE if use_lanczos else Image.Resampling.BILINEAR
                img = img.resize(scaled_size, resample)
                
                # Apply sharpening for aggressive downscaling
                if sharpen and PIL_AVAILABLE:
                    scale_factor = min(
                        scaled_size[0] / original_size[0],
                        scaled_size[1] / original_size[1]
                    )
                    if scale_factor < self.SHARPEN_THRESHOLD:
                        img = img.filter(ImageFilter.UnsharpMask(
                            radius=2, percent=150, threshold=3
                        ))
                    elif scale_factor < 1.0:
                        img = img.filter(ImageFilter.SHARPEN)
            
            # Handle mode-specific cropping/padding
            final_img = self._apply_display_mode(
                img, (target_width, target_height), mode
            )
            
            width, height = final_img.size
            rgba_data = final_img.tobytes("raw", "RGBA")
            data_size = len(rgba_data)
            
            # Generate cache key
            cache_key = f"{path}|scaled:{target_width}x{target_height}"
            
            prescale_ms = (time.time() - start) * 1000
            self._prescale_count += 1
            self._total_prescale_ms += prescale_ms
            
            # Send WORKER_IDLE to resume heartbeat monitoring
            self._send_idle_notification(msg.correlation_id)
            
            # Use shared memory for large images to avoid queue serialization
            if data_size > self.SHARED_MEMORY_THRESHOLD:
                try:
                    shm_name = f"srpss_img_{uuid.uuid4().hex[:12]}"
                    shm = SharedMemory(name=shm_name, create=True, size=data_size)
                    shm.buf[:data_size] = rgba_data
                    self._shared_memories.append(shm)
                    
                    if self._logger:
                        self._logger.debug(
                            "Using shared memory for %dx%d image (%.1f MB): %s",
                            width, height, data_size / (1024 * 1024), shm_name
                        )
                    
                    return WorkerResponse(
                        msg_type=MessageType.IMAGE_RESULT,
                        seq_no=msg.seq_no,
                        correlation_id=msg.correlation_id,
                        success=True,
                        payload={
                            "path": path,
                            "original_width": original_size[0],
                            "original_height": original_size[1],
                            "width": width,
                            "height": height,
                            "format": "RGBA",
                            "shared_memory_name": shm_name,
                            "shared_memory_size": data_size,
                            "cache_key": cache_key,
                            "mode": mode,
                        },
                        processing_time_ms=prescale_ms,
                    )
                except Exception as shm_err:
                    if self._logger:
                        self._logger.warning("Shared memory failed, using queue: %s", shm_err)
                    # Fall through to queue-based transfer
            
            return WorkerResponse(
                msg_type=MessageType.IMAGE_RESULT,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=True,
                payload={
                    "path": path,
                    "original_width": original_size[0],
                    "original_height": original_size[1],
                    "width": width,
                    "height": height,
                    "format": "RGBA",
                    "rgba_data": rgba_data,
                    "cache_key": cache_key,
                    "mode": mode,
                },
                processing_time_ms=prescale_ms,
            )
            
        except Exception as e:
            # Send WORKER_IDLE even on error to resume heartbeat monitoring
            self._send_idle_notification(msg.correlation_id)
            if self._logger:
                self._logger.exception("Prescale failed: %s", e)
            return WorkerResponse(
                msg_type=MessageType.IMAGE_RESULT,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=False,
                error=f"Prescale failed: {e}",
            )
    
    def _calculate_scale_size(
        self,
        source: Tuple[int, int],
        target: Tuple[int, int],
        mode: str,
    ) -> Tuple[int, int]:
        """Calculate scaled size based on display mode."""
        src_w, src_h = source
        tgt_w, tgt_h = target
        
        if src_w == 0 or src_h == 0:
            return target
        
        src_ratio = src_w / src_h
        tgt_ratio = tgt_w / tgt_h
        
        if mode == "fill":
            # Scale to cover target completely (crop excess)
            if src_ratio > tgt_ratio:
                # Source wider - scale by height
                new_h = tgt_h
                new_w = int(new_h * src_ratio)
            else:
                # Source taller - scale by width
                new_w = tgt_w
                new_h = int(new_w / src_ratio)
            return (max(new_w, tgt_w), max(new_h, tgt_h))
        
        elif mode == "fit":
            # Scale to fit within target (may have bars)
            if src_ratio > tgt_ratio:
                new_w = tgt_w
                new_h = int(new_w / src_ratio)
            else:
                new_h = tgt_h
                new_w = int(new_h * src_ratio)
            return (new_w, new_h)
        
        elif mode == "shrink":
            # Only shrink if larger
            if src_w <= tgt_w and src_h <= tgt_h:
                return source
            # Scale down to fit
            if src_ratio > tgt_ratio:
                new_w = tgt_w
                new_h = int(new_w / src_ratio)
            else:
                new_h = tgt_h
                new_w = int(new_h * src_ratio)
            return (new_w, new_h)
        
        return source
    
    def _apply_display_mode(
        self,
        img: "Image.Image",
        target: Tuple[int, int],
        mode: str,
    ) -> "Image.Image":
        """Apply display mode (crop for fill, pad for fit/shrink)."""
        tgt_w, tgt_h = target
        img_w, img_h = img.size
        
        if mode == "fill":
            # Crop to target size (center crop)
            if img_w > tgt_w or img_h > tgt_h:
                left = (img_w - tgt_w) // 2
                top = (img_h - tgt_h) // 2
                right = left + tgt_w
                bottom = top + tgt_h
                return img.crop((left, top, right, bottom))
            return img
        
        elif mode in ("fit", "shrink"):
            # Pad with black to target size (center)
            if img_w == tgt_w and img_h == tgt_h:
                return img
            
            result = Image.new("RGBA", target, (0, 0, 0, 255))
            x = (tgt_w - img_w) // 2
            y = (tgt_h - img_h) // 2
            result.paste(img, (x, y))
            return result
        
        return img
    
    def _handle_config(self, msg: WorkerMessage) -> WorkerResponse:
        """Handle configuration update."""
        return WorkerResponse(
            msg_type=MessageType.CONFIG_UPDATE,
            seq_no=msg.seq_no,
            correlation_id=msg.correlation_id,
            success=True,
        )
    
    def _cleanup(self) -> None:
        """Log final statistics and clean up shared memory."""
        # Clean up any shared memory segments we created
        for shm in self._shared_memories:
            try:
                shm.close()
                shm.unlink()
            except Exception as e:
                logger.debug("[MISC] Exception suppressed: %s", e)
        self._shared_memories.clear()
        
        if self._logger:
            if self._decode_count > 0:
                avg_decode = self._total_decode_ms / self._decode_count
                self._logger.info(
                    "Decode stats: %d images, avg %.1fms",
                    self._decode_count, avg_decode
                )
            if self._prescale_count > 0:
                avg_prescale = self._total_prescale_ms / self._prescale_count
                self._logger.info(
                    "Prescale stats: %d images, avg %.1fms",
                    self._prescale_count, avg_prescale
                )


def image_worker_main(request_queue: Queue, response_queue: Queue) -> None:
    """Entry point for image worker process."""
    import sys
    import traceback
    
    sys.stderr.write("=== IMAGE Worker: Process started ===\n")
    sys.stderr.flush()
    
    try:
        if not PIL_AVAILABLE:
            sys.stderr.write("IMAGE Worker FATAL: PIL/Pillow not available\n")
            sys.stderr.flush()
            raise RuntimeError("PIL/Pillow is required for ImageWorker")
        
        sys.stderr.write("IMAGE Worker: Creating worker instance...\n")
        sys.stderr.flush()
        worker = ImageWorker(request_queue, response_queue)
        
        sys.stderr.write("IMAGE Worker: Starting main loop...\n")
        sys.stderr.flush()
        worker.run()
        
        sys.stderr.write("IMAGE Worker: Exiting normally\n")
        sys.stderr.flush()
    except Exception as e:
        sys.stderr.write(f"IMAGE Worker CRASHED: {e}\n")
        sys.stderr.write(f"IMAGE Worker crash traceback:\n{''.join(traceback.format_exc())}\n")
        sys.stderr.flush()
        raise
