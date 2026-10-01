"""
Image Worker for decode/prescale operations.

Runs in a separate process to decode and prescale images using PIL,
avoiding blocking the UI thread. Results are returned via queue or
shared memory for large images.

Key responsibilities:
- Decode images from disk (JPEG, PNG, WebP, etc.)
- Prescale to target dimensions using the resolved resample filter
- Apply sharpening for downscaled images
- Return RGBA data for Qt consumption
"""
from __future__ import annotations

import os
import time
import uuid
from multiprocessing import Queue
from multiprocessing.shared_memory import SharedMemory
from typing import Any, Optional, Tuple

from core.process.types import (
    MessageType,
    WorkerMessage,
    WorkerResponse,
    WorkerType,
)
from core.process.shared_memory_transport import (
    SharedMemoryDescriptor,
    close_producer_shared_memory,
    create_image_shared_memory,
    wait_for_shared_memory_attachment,
)
from core.process.workers.base import BaseWorker
from rendering.image_quality import RESAMPLE_FILTERS, decode_image, process_image

try:
    from PIL import Image
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
    
    # Shared memory threshold: 2MB (lowered from 5MB to catch 2560x1438 images)
    # 2560x1438 RGBA = 14.7MB, so this threshold ensures shared memory is used
    SHARED_MEMORY_THRESHOLD = 2 * 1024 * 1024
    PREFETCH_BATCH_MAX_DERIVATIVES = 16
    PREFETCH_BATCH_MAX_LOGICAL_BYTES = 128 * 1024 * 1024
    
    def __init__(self, request_queue: Queue, response_queue: Queue):
        super().__init__(request_queue, response_queue)
        self._decode_count = 0
        self._prescale_count = 0
        self._total_decode_ms = 0.0
        self._total_prescale_ms = 0.0
        # The worker is sequential, so at most one published transfer awaits a
        # parent attachment.  This is a bounded handoff, not a lifetime cache.
        self._pending_shared_transfers: dict[
            str, tuple[SharedMemory, SharedMemoryDescriptor]
        ] = {}
    
    @property
    def worker_type(self) -> WorkerType:
        return WorkerType.IMAGE
    
    def handle_message(self, msg: WorkerMessage) -> Optional[WorkerResponse]:
        """Handle image processing messages."""
        if msg.msg_type == MessageType.IMAGE_DECODE:
            return self._handle_decode(msg)
        elif msg.msg_type == MessageType.IMAGE_PRESCALE:
            return self._handle_prescale(msg)
        elif msg.msg_type == MessageType.IMAGE_PREFETCH_BATCH:
            return self._handle_prefetch_batch(msg)
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
        try:
            target_width = int(msg.payload["target_width"])
            target_height = int(msg.payload["target_height"])
            mode = str(msg.payload["mode"])
            resample_filter = msg.payload["resample_filter"]
            sharpen = msg.payload["sharpen"]
        except (KeyError, TypeError, ValueError) as exc:
            return WorkerResponse(
                msg_type=MessageType.ERROR,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=False,
                error=f"Incomplete IMAGE_PRESCALE payload: {exc}",
            )
        if (
            not isinstance(resample_filter, str)
            or resample_filter not in RESAMPLE_FILTERS
            or not isinstance(sharpen, bool)
        ):
            return WorkerResponse(
                msg_type=MessageType.ERROR,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=False,
                error="IMAGE_PRESCALE requires a resolved resample filter and sharpen boolean",
            )
        if mode not in {"fill", "fit", "shrink"}:
            return WorkerResponse(
                msg_type=MessageType.ERROR,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=False,
                error=f"Unknown IMAGE_PRESCALE display mode: {mode!r}",
            )
        if target_width <= 0 or target_height <= 0:
            return WorkerResponse(
                msg_type=MessageType.ERROR,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=False,
                error=f"Invalid IMAGE_PRESCALE target: {target_width}x{target_height}",
            )
        
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
            rgba_data, width, height, original_size = self._prescale_rgba(
                path, target_width, target_height, mode, resample_filter, sharpen
            )
            data_size = len(rgba_data)

            # Generate cache key
            cache_key = f"{path}|scaled:{target_width}x{target_height}"

            prescale_ms = (time.time() - start) * 1000
            self._prescale_count += 1
            self._total_prescale_ms += prescale_ms

            # Use shared memory for large images to avoid queue serialization
            if data_size > self.SHARED_MEMORY_THRESHOLD:
                try:
                    shm_name = f"srpss_img_{uuid.uuid4().hex[:12]}"
                    shm, descriptor = create_image_shared_memory(
                        rgba_data,
                        name=shm_name,
                    )
                    self._pending_shared_transfers[msg.correlation_id] = (
                        shm,
                        descriptor,
                    )
                    
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
                            **descriptor.payload_fields(),
                            "cache_key": cache_key,
                            "mode": mode,
                        },
                        processing_time_ms=prescale_ms,
                    )
                except Exception as shm_err:
                    if self._logger:
                        self._logger.warning("Shared memory failed, using queue: %s", shm_err)
                    # Fall through to queue-based transfer

            self._send_idle_notification(msg.correlation_id)
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

    @staticmethod
    def _packed_rgba8888(qimage: Any) -> tuple[bytes, int, int]:
        """Copy a QImage into tightly packed RGBA8888 bytes for transport."""
        from PySide6.QtGui import QImage

        rgba = qimage.convertToFormat(QImage.Format.Format_RGBA8888)
        width, height = int(rgba.width()), int(rgba.height())
        if width <= 0 or height <= 0:
            raise ValueError("Qt derivative has invalid dimensions")
        packed_stride = width * 4
        stride = int(rgba.bytesPerLine())
        data = rgba.constBits().tobytes()
        if stride == packed_stride:
            return data[: packed_stride * height], width, height
        return (
            b"".join(
                data[row * stride: row * stride + packed_stride]
                for row in range(height)
            ),
            width,
            height,
        )

    @staticmethod
    def _decode_qimage(path: str) -> Any:
        """Decode one batch-local source without creating a GUI application."""
        from PySide6.QtGui import QImage

        return QImage(path)

    def _prefetch_batch_error(
        self,
        msg: WorkerMessage,
        error: str,
    ) -> WorkerResponse:
        return WorkerResponse(
            msg_type=MessageType.ERROR,
            seq_no=msg.seq_no,
            correlation_id=msg.correlation_id,
            success=False,
            error=error,
        )

    def _validated_prefetch_batch(
        self,
        msg: WorkerMessage,
    ) -> tuple[str, int, list[dict[str, Any]]] | WorkerResponse:
        """Validate the whole request before it can acquire a source decode."""
        payload = msg.payload
        path = payload.get("path")
        generation = payload.get("generation")
        derivatives = payload.get("derivatives")
        if not isinstance(path, str) or not path:
            return self._prefetch_batch_error(msg, "IMAGE_PREFETCH_BATCH requires a path")
        if not isinstance(generation, int) or isinstance(generation, bool):
            return self._prefetch_batch_error(msg, "IMAGE_PREFETCH_BATCH generation must be an integer")
        if not isinstance(derivatives, list) or not derivatives:
            return self._prefetch_batch_error(
                msg,
                "IMAGE_PREFETCH_BATCH requires one or more derivatives",
            )
        if len(derivatives) > self.PREFETCH_BATCH_MAX_DERIVATIVES:
            return self._prefetch_batch_error(
                msg,
                f"IMAGE_PREFETCH_BATCH permits at most {self.PREFETCH_BATCH_MAX_DERIVATIVES} derivatives",
            )

        normalized: list[dict[str, Any]] = []
        logical_bytes = 0
        for index, derivative in enumerate(derivatives):
            if not isinstance(derivative, dict):
                return self._prefetch_batch_error(
                    msg,
                    f"IMAGE_PREFETCH_BATCH derivative {index} must be a mapping",
                )
            cache_key = derivative.get("cache_key")
            width = derivative.get("width")
            height = derivative.get("height")
            mode = derivative.get("mode")
            resample_filter = derivative.get("resample_filter")
            sharpen = derivative.get("sharpen")
            if not isinstance(cache_key, str) or not cache_key:
                return self._prefetch_batch_error(
                    msg,
                    f"IMAGE_PREFETCH_BATCH derivative {index} requires a cache_key",
                )
            if (
                not isinstance(width, int)
                or isinstance(width, bool)
                or not isinstance(height, int)
                or isinstance(height, bool)
                or width <= 0
                or height <= 0
            ):
                return self._prefetch_batch_error(
                    msg,
                    f"IMAGE_PREFETCH_BATCH derivative {index} has invalid dimensions",
                )
            if mode not in {"fill", "fit", "shrink"}:
                return self._prefetch_batch_error(
                    msg,
                    f"IMAGE_PREFETCH_BATCH derivative {index} has unknown mode: {mode!r}",
                )
            if (
                not isinstance(resample_filter, str)
                or resample_filter not in RESAMPLE_FILTERS
                or not isinstance(sharpen, bool)
            ):
                return self._prefetch_batch_error(
                    msg,
                    "IMAGE_PREFETCH_BATCH derivative "
                    f"{index} requires a resolved resample filter and sharpen boolean",
                )
            logical_bytes += width * height * 4
            if logical_bytes > self.PREFETCH_BATCH_MAX_LOGICAL_BYTES:
                return self._prefetch_batch_error(
                    msg,
                    "IMAGE_PREFETCH_BATCH logical RGBA bytes exceed 128 MiB",
                )
            normalized.append(
                {
                    "cache_key": cache_key,
                    "width": width,
                    "height": height,
                    "mode": mode,
                    "resample_filter": resample_filter,
                    "sharpen": sharpen,
                }
            )
        quality_signatures = {
            (derivative["resample_filter"], derivative["sharpen"])
            for derivative in normalized
        }
        if len(quality_signatures) != 1:
            return self._prefetch_batch_error(
                msg,
                "IMAGE_PREFETCH_BATCH derivatives must share one resolved resample filter and sharpen value",
            )
        return path, generation, normalized

    def _handle_prefetch_batch(self, msg: WorkerMessage) -> WorkerResponse:
        """Decode one speculative source once and return its resolved derivatives together."""
        validated = self._validated_prefetch_batch(msg)
        if isinstance(validated, WorkerResponse):
            return validated
        path, generation, requested_derivatives = validated
        if not os.path.exists(path):
            return WorkerResponse(
                msg_type=MessageType.IMAGE_RESULT,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=False,
                error=f"File not found: {path}",
            )

        self._send_busy_notification(msg.correlation_id)
        start = time.time()
        try:
            decode_started_ns = time.perf_counter_ns()
            quality_batch = (
                requested_derivatives[0]["resample_filter"] != "smooth"
                or requested_derivatives[0]["sharpen"]
            )
            if quality_batch:
                source = decode_image(path)
            else:
                source = self._decode_qimage(path)
            decode_finished_ns = time.perf_counter_ns()
            if not quality_batch and source.isNull():
                return WorkerResponse(
                    msg_type=MessageType.IMAGE_RESULT,
                    seq_no=msg.seq_no,
                    correlation_id=msg.correlation_id,
                    success=False,
                    error=f"Qt could not decode {path}",
                )
            self._decode_count += 1

            packed = bytearray()
            response_derivatives: list[dict[str, Any]] = []
            scale_started_ns = time.perf_counter_ns()
            for derivative in requested_derivatives:
                if quality_batch:
                    result = process_image(
                        source,
                        (derivative["width"], derivative["height"]),
                        derivative["mode"],
                        derivative["resample_filter"],
                        derivative["sharpen"],
                    )
                    rgba_data = result.convert("RGBA").tobytes("raw", "RGBA")
                    width, height = result.size
                else:
                    from PySide6.QtCore import QSize

                    from rendering.display_modes import DisplayMode
                    from rendering.image_processor_async import AsyncImageProcessor

                    result = AsyncImageProcessor.process_qimage(
                        source,
                        QSize(derivative["width"], derivative["height"]),
                        DisplayMode.from_string(derivative["mode"]),
                        resample_filter="smooth",
                        sharpen=False,
                    )
                    rgba_data, width, height = self._packed_rgba8888(result)
                offset = len(packed)
                packed.extend(rgba_data)
                response_derivatives.append(
                    {
                        "cache_key": derivative["cache_key"],
                        "width": width,
                        "height": height,
                        "mode": derivative["mode"],
                        "resample_filter": derivative["resample_filter"],
                        "sharpen": derivative["sharpen"],
                        "offset": offset,
                        "size": len(rgba_data),
                    }
                )
                self._prescale_count += 1
            scale_finished_ns = time.perf_counter_ns()

            data = bytes(packed)
            try:
                shm_name = f"srpss_img_{uuid.uuid4().hex[:12]}"
                shm, descriptor = create_image_shared_memory(data, name=shm_name)
            except Exception as shm_error:
                if self._logger:
                    self._logger.error(
                        "IMAGE_PREFETCH_BATCH shared-memory publication failed: %s",
                        shm_error,
                    )
                return self._prefetch_batch_error(
                    msg,
                    f"IMAGE_PREFETCH_BATCH shared-memory publication failed: {shm_error}",
                )

            self._pending_shared_transfers[msg.correlation_id] = (shm, descriptor)
            elapsed_ms = (time.time() - start) * 1000
            self._total_decode_ms += elapsed_ms
            self._total_prescale_ms += elapsed_ms
            return WorkerResponse(
                msg_type=MessageType.IMAGE_RESULT,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=True,
                payload={
                    "path": path,
                    "generation": generation,
                    "decode_count": 1,
                    "worker_pid": os.getpid(),
                    "decode_started_ns": decode_started_ns,
                    "decode_finished_ns": decode_finished_ns,
                    "scale_started_ns": scale_started_ns,
                    "scale_finished_ns": scale_finished_ns,
                    "format": "RGBA",
                    "derivatives": response_derivatives,
                    **descriptor.payload_fields(),
                },
                processing_time_ms=elapsed_ms,
            )
        except Exception as exc:
            if self._logger:
                self._logger.exception("IMAGE_PREFETCH_BATCH failed: %s", exc)
            return WorkerResponse(
                msg_type=MessageType.IMAGE_RESULT,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=False,
                error=f"IMAGE_PREFETCH_BATCH failed: {exc}",
            )
        finally:
            # This source is deliberately batch-local; the worker owns no image cache.
            try:
                del source
            except UnboundLocalError:
                pass
            if msg.correlation_id not in self._pending_shared_transfers:
                self._send_idle_notification(msg.correlation_id)

    def _prescale_rgba(
        self,
        path: str,
        target_width: int,
        target_height: int,
        mode: str,
        resample_filter: str,
        sharpen: bool,
    ) -> Tuple[bytes, int, int, Tuple[int, int]]:
        """Foreground derivative through the matching Qt or Pillow branch."""
        if resample_filter == "smooth" and not sharpen:
            from PySide6.QtCore import QSize

            from rendering.display_modes import DisplayMode
            from rendering.image_processor_async import AsyncImageProcessor

            source = self._decode_qimage(path)
            if source.isNull():
                raise ValueError(f"Qt could not decode {path}")
            result = AsyncImageProcessor.process_qimage(
                source,
                QSize(target_width, target_height),
                DisplayMode.from_string(mode),
                resample_filter="smooth",
                sharpen=False,
            )
            rgba_data, width, height = self._packed_rgba8888(result)
            return rgba_data, width, height, (source.width(), source.height())

        source = decode_image(path)
        original_size = source.size
        final_image = process_image(
            source,
            (target_width, target_height),
            mode,
            resample_filter,
            sharpen,
        )
        width, height = final_image.size
        return final_image.convert("RGBA").tobytes("raw", "RGBA"), width, height, original_size
    
    def _handle_config(self, msg: WorkerMessage) -> WorkerResponse:
        """Handle configuration update."""
        return WorkerResponse(
            msg_type=MessageType.CONFIG_UPDATE,
            seq_no=msg.seq_no,
            correlation_id=msg.correlation_id,
            success=True,
        )
    
    def _after_response_sent(
        self,
        response: WorkerResponse,
        *,
        delivered: bool,
    ) -> None:
        """Close the producer mapping as soon as parent attachment is proven."""
        transfer = self._pending_shared_transfers.pop(
            response.correlation_id,
            None,
        )
        if transfer is None:
            return

        shm, descriptor = transfer
        attached = False
        try:
            if delivered:
                attached = wait_for_shared_memory_attachment(
                    shm,
                    descriptor,
                    timeout_s=1.0,
                )
        finally:
            close_producer_shared_memory(shm, attached=attached)
            self._send_idle_notification(response.correlation_id)

    def _cleanup(self) -> None:
        """Log final statistics and reclaim only unpublished/in-flight handoffs."""
        for shm, _descriptor in self._pending_shared_transfers.values():
            close_producer_shared_memory(shm, attached=False)
        self._pending_shared_transfers.clear()
        
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


class SpeculativeImageWorker(ImageWorker):
    """Dedicated low-criticality image worker for speculative derivatives.

    It intentionally shares the proven decode/prescale implementation with the
    foreground ImageWorker while owning a distinct process, queue, health state,
    and log identity.  Foreground image requests are never routed here.
    """

    @property
    def worker_type(self) -> WorkerType:
        return WorkerType.IMAGE_PREFETCH


def _run_image_worker(
    worker_cls,
    request_queue: Queue,
    response_queue: Queue,
    *,
    label: str,
) -> None:
    """Run one image-worker role with a role-specific process identity."""
    import sys
    import traceback

    sys.stderr.write(f"=== {label} Worker: Process started ===\n")
    sys.stderr.flush()

    try:
        if not PIL_AVAILABLE:
            sys.stderr.write(f"{label} Worker FATAL: PIL/Pillow not available\n")
            sys.stderr.flush()
            raise RuntimeError("PIL/Pillow is required for image workers")

        sys.stderr.write(f"{label} Worker: Creating worker instance...\n")
        sys.stderr.flush()
        worker = worker_cls(request_queue, response_queue)

        sys.stderr.write(f"{label} Worker: Starting main loop...\n")
        sys.stderr.flush()
        worker.run()

        sys.stderr.write(f"{label} Worker: Exiting normally\n")
        sys.stderr.flush()
    except Exception as e:
        sys.stderr.write(f"{label} Worker CRASHED: {e}\n")
        sys.stderr.write(
            f"{label} Worker crash traceback:\n{''.join(traceback.format_exc())}\n"
        )
        sys.stderr.flush()
        raise


def image_worker_main(request_queue: Queue, response_queue: Queue) -> None:
    """Entry point for latency-sensitive foreground image work."""
    _run_image_worker(
        ImageWorker,
        request_queue,
        response_queue,
        label="IMAGE",
    )


def speculative_image_worker_main(
    request_queue: Queue,
    response_queue: Queue,
) -> None:
    """Entry point for isolated speculative scaled-derivative work."""
    _run_image_worker(
        SpeculativeImageWorker,
        request_queue,
        response_queue,
        label="IMAGE_PREFETCH",
    )
