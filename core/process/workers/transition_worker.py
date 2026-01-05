"""
Transition Precompute Worker for CPU-bound transition preparation.

Runs in a separate process to precompute transition data without
blocking the UI thread.

Key responsibilities:
- Precompute block patterns for Diffuse/BlockFlip transitions
- Generate lookup tables for warp/distortion effects
- Prepare particle system initial states
- Cache computed data for reuse
"""
from __future__ import annotations

import hashlib
import random
import time
from dataclasses import dataclass, field
from multiprocessing import Queue
from typing import Any, Dict, Optional

from core.process.types import (
    MessageType,
    WorkerMessage,
    WorkerResponse,
    WorkerType,
)
from core.process.workers.base import BaseWorker

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


@dataclass
class TransitionPrecomputeConfig:
    """Configuration for transition precomputation."""
    # Diffuse transition
    diffuse_block_size: int = 16
    diffuse_shape: str = "Rectangle"  # Rectangle, Circle, Triangle
    
    # Block transitions
    block_cols: int = 8
    block_rows: int = 6
    
    # Particle transition
    particle_count: int = 1000
    
    # Warp transition
    warp_grid_size: int = 32
    
    # Common
    screen_width: int = 1920
    screen_height: int = 1080
    seed: Optional[int] = None


@dataclass
class PrecomputeResult:
    """Result of a precomputation operation."""
    transition_type: str
    cache_key: str
    data: Dict[str, Any] = field(default_factory=dict)
    compute_time_ms: float = 0.0


class TransitionWorker(BaseWorker):
    """
    Worker for transition precomputation.
    
    Handles:
    - TRANSITION_PRECOMPUTE: Compute transition data (block indices, patterns, etc.)
    - CONFIG_UPDATE: Update precomputation configuration
    
    Precomputed data is returned via queue and can be cached by the UI process.
    """
    
    def __init__(self, request_queue: Queue, response_queue: Queue):
        super().__init__(request_queue, response_queue)
        self._config = TransitionPrecomputeConfig()
        self._precompute_count = 0
        self._cache: Dict[str, PrecomputeResult] = {}
    
    @property
    def worker_type(self) -> WorkerType:
        return WorkerType.TRANSITION
    
    def handle_message(self, msg: WorkerMessage) -> Optional[WorkerResponse]:
        """Handle transition precompute messages."""
        if msg.msg_type == MessageType.TRANSITION_PRECOMPUTE:
            return self._handle_precompute(msg)
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
    
    def _handle_precompute(self, msg: WorkerMessage) -> WorkerResponse:
        """Precompute transition data."""
        transition_type = msg.payload.get("transition_type", "Diffuse")
        params = msg.payload.get("params", {})
        use_cache = msg.payload.get("use_cache", True)
        
        # Update config from params
        if "screen_width" in params:
            self._config.screen_width = params["screen_width"]
        if "screen_height" in params:
            self._config.screen_height = params["screen_height"]
        if "block_size" in params:
            self._config.diffuse_block_size = params["block_size"]
        if "seed" in params:
            self._config.seed = params["seed"]
        
        # Generate cache key
        cache_key = self._generate_cache_key(transition_type, params)
        
        # Check cache
        if use_cache and cache_key in self._cache:
            cached = self._cache[cache_key]
            return WorkerResponse(
                msg_type=MessageType.TRANSITION_RESULT,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=True,
                payload={
                    "transition_type": transition_type,
                    "cache_key": cache_key,
                    "data": cached.data,
                    "cached": True,
                },
                processing_time_ms=0.0,
            )
        
        start = time.time()
        try:
            # Precompute based on transition type
            data = self._precompute(transition_type, params)
            
            compute_time_ms = (time.time() - start) * 1000
            self._precompute_count += 1
            
            # Cache result
            result = PrecomputeResult(
                transition_type=transition_type,
                cache_key=cache_key,
                data=data,
                compute_time_ms=compute_time_ms,
            )
            self._cache[cache_key] = result
            
            return WorkerResponse(
                msg_type=MessageType.TRANSITION_RESULT,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=True,
                payload={
                    "transition_type": transition_type,
                    "cache_key": cache_key,
                    "data": data,
                    "cached": False,
                },
                processing_time_ms=compute_time_ms,
            )
            
        except Exception as e:
            if self._logger:
                self._logger.exception("Precompute failed: %s", e)
            return WorkerResponse(
                msg_type=MessageType.ERROR,
                seq_no=msg.seq_no,
                correlation_id=msg.correlation_id,
                success=False,
                error=f"Precompute failed: {e}",
            )
    
    def _precompute(self, transition_type: str, params: Dict) -> Dict[str, Any]:
        """Perform precomputation for a transition type."""
        t = transition_type.lower()
        
        if t == "diffuse":
            return self._precompute_diffuse(params)
        elif t in ("blockflip", "blockspin", "blockpuzzle"):
            return self._precompute_blocks(params)
        elif t == "warp":
            return self._precompute_warp(params)
        elif t == "particle":
            return self._precompute_particles(params)
        elif t == "raindrops":
            return self._precompute_raindrops(params)
        elif t == "crumble":
            return self._precompute_crumble(params)
        else:
            # No precomputation needed for simple transitions
            return {"precomputed": False}
    
    def _precompute_diffuse(self, params: Dict) -> Dict[str, Any]:
        """Precompute block dissolution pattern for Diffuse transition."""
        block_size = params.get("block_size", self._config.diffuse_block_size)
        width = params.get("screen_width", self._config.screen_width)
        height = params.get("screen_height", self._config.screen_height)
        seed = params.get("seed", self._config.seed)
        
        if seed is not None:
            random.seed(seed)
        
        # Calculate grid
        cols = (width + block_size - 1) // block_size
        rows = (height + block_size - 1) // block_size
        total_blocks = cols * rows
        
        # Generate random dissolution order
        indices = list(range(total_blocks))
        random.shuffle(indices)
        
        # Generate block positions
        blocks = []
        for idx in indices:
            row = idx // cols
            col = idx % cols
            x = col * block_size
            y = row * block_size
            w = min(block_size, width - x)
            h = min(block_size, height - y)
            blocks.append({
                "x": x, "y": y, "w": w, "h": h,
                "order": indices.index(idx),
            })
        
        return {
            "precomputed": True,
            "block_size": block_size,
            "cols": cols,
            "rows": rows,
            "total_blocks": total_blocks,
            "dissolution_order": indices,
            "blocks": blocks,
        }
    
    def _precompute_blocks(self, params: Dict) -> Dict[str, Any]:
        """Precompute block grid for BlockFlip/BlockSpin transitions."""
        cols = params.get("cols", self._config.block_cols)
        rows = params.get("rows", self._config.block_rows)
        width = params.get("screen_width", self._config.screen_width)
        height = params.get("screen_height", self._config.screen_height)
        seed = params.get("seed", self._config.seed)
        
        if seed is not None:
            random.seed(seed)
        
        block_w = width // cols
        block_h = height // rows
        total_blocks = cols * rows
        
        # Generate random flip order
        indices = list(range(total_blocks))
        random.shuffle(indices)
        
        # Generate block data
        blocks = []
        for idx in range(total_blocks):
            row = idx // cols
            col = idx % cols
            x = col * block_w
            y = row * block_h
            
            # Staggered timing based on distance from center
            cx, cy = cols // 2, rows // 2
            dist = abs(col - cx) + abs(row - cy)
            
            blocks.append({
                "x": x, "y": y,
                "w": block_w, "h": block_h,
                "order": indices.index(idx),
                "distance": dist,
                "flip_axis": random.choice(["x", "y"]),
            })
        
        return {
            "precomputed": True,
            "cols": cols,
            "rows": rows,
            "block_w": block_w,
            "block_h": block_h,
            "total_blocks": total_blocks,
            "flip_order": indices,
            "blocks": blocks,
        }
    
    def _precompute_warp(self, params: Dict) -> Dict[str, Any]:
        """Precompute warp distortion lookup table."""
        if not NUMPY_AVAILABLE:
            return {"precomputed": False, "error": "NumPy required"}
        
        grid_size = params.get("grid_size", self._config.warp_grid_size)
        # Screen dimensions available for future scaling
        _ = params.get("screen_width", self._config.screen_width)
        _ = params.get("screen_height", self._config.screen_height)
        
        # Generate normalized coordinates grid
        u = np.linspace(0, 1, grid_size)
        v = np.linspace(0, 1, grid_size)
        uu, vv = np.meshgrid(u, v)
        
        # Compute center distance for radial warp
        cx, cy = 0.5, 0.5
        dist = np.sqrt((uu - cx) ** 2 + (vv - cy) ** 2)
        angle = np.arctan2(vv - cy, uu - cx)
        
        return {
            "precomputed": True,
            "grid_size": grid_size,
            "u_coords": uu.tolist(),
            "v_coords": vv.tolist(),
            "center_dist": dist.tolist(),
            "angle": angle.tolist(),
        }
    
    def _precompute_particles(self, params: Dict) -> Dict[str, Any]:
        """Precompute particle initial states."""
        count = params.get("particle_count", self._config.particle_count)
        width = params.get("screen_width", self._config.screen_width)
        height = params.get("screen_height", self._config.screen_height)
        seed = params.get("seed", self._config.seed)
        
        if seed is not None:
            random.seed(seed)
        
        particles = []
        for _ in range(count):
            particles.append({
                "x": random.uniform(0, width),
                "y": random.uniform(0, height),
                "vx": random.uniform(-2, 2),
                "vy": random.uniform(-2, 2),
                "size": random.uniform(2, 8),
                "alpha": random.uniform(0.3, 1.0),
                "rotation": random.uniform(0, 360),
            })
        
        return {
            "precomputed": True,
            "particle_count": count,
            "particles": particles,
        }
    
    def _precompute_raindrops(self, params: Dict) -> Dict[str, Any]:
        """Precompute raindrop positions and sizes."""
        count = params.get("drop_count", 50)
        width = params.get("screen_width", self._config.screen_width)
        height = params.get("screen_height", self._config.screen_height)
        seed = params.get("seed", self._config.seed)
        
        if seed is not None:
            random.seed(seed)
        
        drops = []
        for i in range(count):
            # Staggered timing for natural effect
            delay = i / count * 0.6
            drops.append({
                "x": random.uniform(0, width),
                "y": random.uniform(0, height),
                "radius": random.uniform(20, 100),
                "delay": delay,
                "duration": random.uniform(0.3, 0.6),
            })
        
        return {
            "precomputed": True,
            "drop_count": count,
            "drops": drops,
        }
    
    def _precompute_crumble(self, params: Dict) -> Dict[str, Any]:
        """Precompute crumble fragment positions."""
        cols = params.get("cols", 12)
        rows = params.get("rows", 8)
        width = params.get("screen_width", self._config.screen_width)
        height = params.get("screen_height", self._config.screen_height)
        seed = params.get("seed", self._config.seed)
        
        if seed is not None:
            random.seed(seed)
        
        frag_w = width / cols
        frag_h = height / rows
        
        fragments = []
        for row in range(rows):
            for col in range(cols):
                x = col * frag_w
                y = row * frag_h
                
                # Random fall parameters
                fall_delay = random.uniform(0, 0.5)
                fall_rotation = random.uniform(-180, 180)
                fall_offset_x = random.uniform(-50, 50)
                
                fragments.append({
                    "x": x, "y": y,
                    "w": frag_w, "h": frag_h,
                    "fall_delay": fall_delay,
                    "fall_rotation": fall_rotation,
                    "fall_offset_x": fall_offset_x,
                })
        
        return {
            "precomputed": True,
            "cols": cols,
            "rows": rows,
            "fragments": fragments,
        }
    
    def _generate_cache_key(self, transition_type: str, params: Dict) -> str:
        """Generate a cache key for the precomputation."""
        key_data = f"{transition_type}:{sorted(params.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()[:16]
    
    def _handle_config(self, msg: WorkerMessage) -> WorkerResponse:
        """Handle configuration update."""
        payload = msg.payload
        
        for key in ["screen_width", "screen_height", "diffuse_block_size",
                    "block_cols", "block_rows", "particle_count", "warp_grid_size"]:
            if key in payload:
                setattr(self._config, key, payload[key])
        
        # Clear cache on config change
        if msg.payload.get("clear_cache", True):
            self._cache.clear()
        
        return WorkerResponse(
            msg_type=MessageType.CONFIG_UPDATE,
            seq_no=msg.seq_no,
            correlation_id=msg.correlation_id,
            success=True,
        )
    
    def _cleanup(self) -> None:
        """Log final statistics."""
        if self._logger:
            self._logger.info(
                "Transition stats: %d precomputes, %d cached",
                self._precompute_count,
                len(self._cache),
            )


def transition_worker_main(request_queue: Queue, response_queue: Queue) -> None:
    """Entry point for transition worker process."""
    import sys
    import traceback
    
    sys.stderr.write("=== TRANSITION Worker: Process started ===\n")
    sys.stderr.flush()
    
    try:
        sys.stderr.write("TRANSITION Worker: Creating worker instance...\n")
        sys.stderr.flush()
        worker = TransitionWorker(request_queue, response_queue)
        
        sys.stderr.write("TRANSITION Worker: Starting main loop...\n")
        sys.stderr.flush()
        worker.run()
        
        sys.stderr.write("TRANSITION Worker: Exiting normally\n")
        sys.stderr.flush()
    except Exception as e:
        sys.stderr.write(f"TRANSITION Worker CRASHED: {e}\n")
        sys.stderr.write(f"TRANSITION Worker crash traceback:\n{''.join(traceback.format_exc())}\n")
        sys.stderr.flush()
        raise
