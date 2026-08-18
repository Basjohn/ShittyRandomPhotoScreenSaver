"""
Audio capture utilities for system loopback audio.

Provides a unified interface for capturing system audio output using
either PyAudioWPatch (preferred on Windows) or sounddevice as fallback.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Any
import os
import platform
import time

from core.logging.logger import get_logger, is_verbose_logging

logger = get_logger(__name__)


@dataclass
class AudioDeviceInfo:
    """Information about an audio device."""
    index: int
    name: str
    channels: int
    sample_rate: int
    is_loopback: bool = False


class CaptureState(Enum):
    """Explicit capture lifecycle state.

    ``STARTING`` exists because a stream that has just been opened has not
    necessarily delivered its first callback yet. Classifying that window as
    unhealthy caused an immediate self-restart at startup.
    """

    STOPPED = "stopped"
    STARTING = "starting"
    HEALTHY = "healthy"
    STALE = "stale"
    FAILED = "failed"


# Allowance for the first callback after a stream reports a successful start.
CAPTURE_FIRST_CALLBACK_GRACE_S = 1.0
# Existing health threshold, applied only once callbacks have actually been seen.
CAPTURE_STALE_AFTER_S = 0.5


@dataclass
class AudioCaptureConfig:
    """Configuration for audio capture."""
    sample_rate: int = 48000
    channels: int = 2
    block_size: int = 1024
    dtype: str = "float32"


class AudioCaptureBackend(ABC):
    """Abstract base class for audio capture backends."""
    
    @abstractmethod
    def start(self, callback: Callable[[Any], None]) -> bool:
        """Start audio capture with the given callback.
        
        Args:
            callback: Function called with audio samples (numpy array)
            
        Returns:
            True if capture started successfully
        """
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """Stop audio capture and release resources."""
        pass
    
    @abstractmethod
    def is_running(self) -> bool:
        """Check if capture is currently running."""
        pass
    
    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """Get the actual sample rate being used."""
        pass
    
    @property
    @abstractmethod
    def channels(self) -> int:
        """Get the number of channels being captured."""
        pass

    # ------------------------------------------------------------------
    # Capture health lifecycle (shared by every backend)
    # ------------------------------------------------------------------
    # These are class-level defaults so a backend that has never started still
    # answers the state query safely.
    _capture_state: CaptureState = CaptureState.STOPPED
    _capture_started_ts: float = 0.0
    _last_callback_ts: float = 0.0

    def _note_capture_starting(self) -> None:
        """Record a stream that opened successfully but has no callback yet."""
        self._capture_started_ts = time.monotonic()
        self._last_callback_ts = 0.0
        self._capture_state = CaptureState.STARTING

    def _note_capture_callback(self) -> None:
        """Record one delivered audio callback (audio thread)."""
        self._last_callback_ts = time.monotonic()
        if self._capture_state is not CaptureState.HEALTHY:
            self._capture_state = CaptureState.HEALTHY

    def _note_capture_stopped(self) -> None:
        self._capture_state = CaptureState.STOPPED
        self._capture_started_ts = 0.0
        self._last_callback_ts = 0.0

    def _note_capture_failed(self) -> None:
        self._capture_state = CaptureState.FAILED
        self._capture_started_ts = 0.0
        self._last_callback_ts = 0.0

    def capture_state(self) -> CaptureState:
        """Return the current derived capture state.

        Pure observation: it never mutates state, so a late first callback can
        still promote a ``STARTING`` stream to ``HEALTHY``.
        """
        state = self._capture_state
        if state is CaptureState.STARTING:
            started = float(self._capture_started_ts or 0.0)
            if started > 0.0 and (time.monotonic() - started) >= CAPTURE_FIRST_CALLBACK_GRACE_S:
                return CaptureState.STALE
            return CaptureState.STARTING
        if state is CaptureState.HEALTHY:
            last = float(self._last_callback_ts or 0.0)
            if last <= 0.0 or (time.monotonic() - last) >= CAPTURE_STALE_AFTER_S:
                return CaptureState.STALE
            return CaptureState.HEALTHY
        return state

    def is_healthy(self) -> bool:
        """True only while callbacks are actually flowing."""
        return self.capture_state() is CaptureState.HEALTHY

    def is_capture_starting(self) -> bool:
        """True while a successfully started stream still awaits its first callback."""
        return self.capture_state() is CaptureState.STARTING

    def is_capture_stale(self) -> bool:
        """True only for a stream that ran (or should have) and then went quiet.

        This is the sole restart authority. A just-started capture is never
        stale, so an immediate wake cannot bounce it.
        """
        return self.capture_state() is CaptureState.STALE

    @abstractmethod
    def restart(self) -> bool:
        """Restart the capture stream.

        Returns:
            True if restarted successfully
        """
        pass


def _build_block_size_candidates(preferred: int) -> list[int]:
    """Return the prioritized block size list honoring user preference."""

    ordered = [128, 256, 512, 1024]
    if preferred and preferred in ordered:
        return [preferred] + [size for size in ordered if size != preferred]
    return ordered


class PyAudioWPatchBackend(AudioCaptureBackend):
    """Audio capture using PyAudioWPatch WASAPI loopback (Windows only)."""
    
    def __init__(self, config: AudioCaptureConfig = None):
        self._config = config or AudioCaptureConfig()
        self._stream = None
        self._pa = None
        self._running = False
        self._sample_rate = self._config.sample_rate
        self._channels = self._config.channels
        self._negotiated_block_size: int = 0
        self._np = None
        self._last_callback_ts: float = 0.0
        self._callback: Optional[Callable[[Any], None]] = None
    
    def _find_loopback_device(self, pa) -> Optional[dict]:
        """Find the best loopback device for WASAPI capture."""
        try:
            import pyaudiowpatch as pyaudio
            wasapi_info = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
        except OSError:
            return None
        
        if wasapi_info is None:
            return None
            
        # Get default output device
        try:
            default_speakers = pa.get_device_info_by_index(
                wasapi_info["defaultOutputDevice"]
            )
        except Exception as e:
            logger.debug("[AUDIO] Exception suppressed: %s", e)
            return None
        
        if default_speakers is None:
            return None
            
        # If already a loopback device, use it directly
        if default_speakers.get("isLoopbackDevice"):
            return default_speakers
        
        # Find matching loopback device
        try:
            base_name = str(default_speakers.get("name", ""))
            chosen = None
            for loopback in pa.get_loopback_device_info_generator():
                loop_name = str(loopback.get("name", ""))
                if chosen is None:
                    chosen = loopback
                if base_name and base_name in loop_name:
                    chosen = loopback
                    break
            return chosen
        except Exception as e:
            logger.debug("[AUDIO] Exception suppressed: %s", e)
            return None
    
    def start(self, callback: Callable[[Any], None]) -> bool:
        if self._running:
            return True
        started = self._start_stream(callback)
        if not started:
            self._note_capture_failed()
        return started

    def _start_stream(self, callback: Callable[[Any], None]) -> bool:
        # Check platform
        if not platform.system().lower().startswith("win"):
            logger.debug("[AUDIO] PyAudioWPatch only available on Windows")
            return False
        
        # Import numpy
        try:
            import numpy as np
            self._np = np
        except ImportError:
            logger.debug("[AUDIO] numpy not available")
            return False
        
        # Import pyaudiowpatch
        try:
            import pyaudiowpatch as pyaudio
        except ImportError:
            logger.debug("[AUDIO] PyAudioWPatch not available")
            return False
        
        # Initialize PyAudio
        try:
            self._pa = pyaudio.PyAudio()
        except Exception as e:
            logger.debug("[AUDIO] Failed to initialize PyAudio: %s", e)
            return False
        
        # Find loopback device
        device = self._find_loopback_device(self._pa)
        if device is None:
            if is_verbose_logging():
                logger.debug("[AUDIO] No WASAPI loopback device found; aborting PyAudioWPatch start")
            self._cleanup_pa()
            return False
        
        # Get device parameters
        try:
            self._channels = int(device.get("maxInputChannels", 0) or 0)
            self._sample_rate = int(device.get("defaultSampleRate", 48000) or 48000)
        except Exception as e:
            logger.debug("[AUDIO] Exception suppressed: %s", e)
            self._channels = 2
            self._sample_rate = 48000
        
        if is_verbose_logging():
            logger.debug(
                "[AUDIO] PyAudioWPatch selected device=%s (index=%s, channels=%s, sample_rate=%s)",
                device.get("name", "<unknown>"),
                device.get("index"),
                self._channels,
                self._sample_rate,
            )
        
        if self._channels <= 0 or self._sample_rate <= 0:
            self._cleanup_pa()
            return False
        
        # Create stream callback
        self._callback = callback  # Store for restart
        
        def stream_callback(in_data, frame_count, time_info, status):
            try:
                self._note_capture_callback()
                samples = self._np.frombuffer(in_data, dtype=self._np.float32)
                try:
                    ch = int(self._channels) if self._channels else 1
                except Exception as e:
                    logger.debug("[AUDIO] Exception suppressed: %s", e)
                    ch = 1
                if ch > 1:
                    try:
                        frames = int(samples.size // ch)
                        if frames > 0 and (frames * ch) == int(samples.size):
                            samples = samples.reshape(frames, ch)
                    except Exception as e:
                        logger.debug("[AUDIO] Exception suppressed: %s", e)
                callback(samples)
            except Exception as e:
                logger.debug("[AUDIO] Exception suppressed: %s", e)
            return (None, pyaudio.paContinue)
        
        # Build priority-ordered block size list: user preference first, then fallbacks
        preferred = self._config.block_size if self._config.block_size > 0 else 0
        block_candidates = _build_block_size_candidates(preferred)

        for block_size in block_candidates:
            try:
                self._stream = self._pa.open(
                    format=pyaudio.paFloat32,
                    channels=self._channels,
                    rate=self._sample_rate,
                    input=True,
                    input_device_index=device["index"],
                    frames_per_buffer=block_size,
                    stream_callback=stream_callback,
                )
                self._stream.start_stream()
                self._running = True
                self._note_capture_starting()
                self._negotiated_block_size = int(block_size)
                logger.info(
                    "[AUDIO] PyAudioWPatch stream running (device=%s, negotiated_block=%d, preferred=%d)",
                    device.get("name", "<unknown>"),
                    block_size,
                    preferred,
                )
                return True
            except Exception as e:
                if self._stream:
                    try:
                        self._stream.stop_stream()
                        self._stream.close()
                    except Exception as e2:
                        logger.debug("[AUDIO] Exception suppressed: %s", e2)
                    self._stream = None
                if is_verbose_logging():
                    logger.debug("[AUDIO] Block size %d failed: %s", block_size, e)
        
        self._cleanup_pa()
        return False
    
    def restart(self) -> bool:
        """Restart the capture stream."""
        self.stop()
        if self._callback is not None:
            return self.start(self._callback)
        return False

    def _cleanup_pa(self) -> None:
        """Clean up PyAudio resources."""
        if self._pa:
            try:
                self._pa.terminate()
            except Exception as e:
                logger.debug("[AUDIO] Exception suppressed: %s", e)
            self._pa = None
    
    def stop(self) -> None:
        self._running = False
        self._note_capture_stopped()
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception as e:
                logger.debug("[AUDIO] Exception suppressed: %s", e)
            self._stream = None
        self._negotiated_block_size = 0
        self._cleanup_pa()
    
    def is_running(self) -> bool:
        return self._running
    
    @property
    def sample_rate(self) -> int:
        return self._sample_rate
    
    @property
    def channels(self) -> int:
        return self._channels


class SounddeviceBackend(AudioCaptureBackend):
    """Audio capture using sounddevice (cross-platform fallback)."""
    
    def __init__(self, config: AudioCaptureConfig = None):
        self._config = config or AudioCaptureConfig()
        self._stream = None
        self._sd = None
        self._running = False
        self._sample_rate = self._config.sample_rate
        self._channels = self._config.channels
        self._negotiated_block_size: int = 0
        self._np = None
        self._last_callback_ts: float = 0.0
        self._callback: Optional[Callable[[Any], None]] = None

    def _find_wasapi_loopback_device(self) -> Optional[dict]:
        """Find WASAPI loopback device via sounddevice."""
        if not platform.system().lower().startswith("win"):
            return None

        try:
            hostapis = self._sd.query_hostapis()
            wasapi_idx = None
            for i, api in enumerate(hostapis):
                if "wasapi" in api.get("name", "").lower():
                    wasapi_idx = i
                    break
            
            if wasapi_idx is None:
                return None
            
            wasapi = hostapis[wasapi_idx]
            
            # Try host API's default output device
            default_out_idx = wasapi.get("default_output_device")
            if default_out_idx is not None and default_out_idx >= 0:
                try:
                    dev = self._sd.query_devices(default_out_idx)
                    if dev.get("max_input_channels", 0) > 0:
                        return dev
                except Exception as e:
                    logger.debug("[AUDIO] Exception suppressed: %s", e)
            
            # Fallback to global default output if it's WASAPI
            try:
                global_out = self._sd.query_devices(kind="output")
                if global_out.get("hostapi") == wasapi_idx:
                    if global_out.get("max_input_channels", 0) > 0:
                        return global_out
            except Exception as e:
                logger.debug("[AUDIO] Exception suppressed: %s", e)
                
        except Exception as e:
            logger.debug("[AUDIO] Exception suppressed: %s", e)
        
        return None
    
    def _find_any_input_device(self) -> Optional[dict]:
        """Find any usable input device."""
        try:
            devices = self._sd.query_devices()
            candidates = []
            
            for i, dev in enumerate(devices):
                if dev.get("max_input_channels", 0) > 0:
                    # Prefer devices with loopback-like names
                    name = dev.get("name", "").lower()
                    priority = 0
                    if "loopback" in name or "stereo mix" in name or "what u hear" in name:
                        priority = 2
                    elif "output" in name:
                        priority = 1
                    candidates.append((priority, i, dev))
            
            if candidates:
                candidates.sort(key=lambda x: -x[0])
                return candidates[0][2]
        except Exception as e:
            logger.debug("[AUDIO] Exception suppressed: %s", e)
        
        return None
    
    def start(self, callback: Callable[[Any], None]) -> bool:
        if self._running:
            return True
        started = self._start_stream(callback)
        if not started:
            self._note_capture_failed()
        return started

    def _start_stream(self, callback: Callable[[Any], None]) -> bool:
        # Import numpy
        try:
            import numpy as np
            self._np = np
        except ImportError:
            logger.debug("[AUDIO] numpy not available")
            return False
        
        # Import sounddevice
        try:
            import sounddevice as sd
            self._sd = sd
        except ImportError:
            logger.debug("[AUDIO] sounddevice not available")
            return False
        
        # Try WASAPI loopback first
        device = self._find_wasapi_loopback_device()
        if device is None:
            device = self._find_any_input_device()
        
        if device is None:
            logger.debug("[AUDIO] No suitable input device found")
            return False
        
        # Get device parameters
        try:
            self._channels = min(2, int(device.get("max_input_channels", 2)))
            self._sample_rate = int(device.get("default_samplerate", 48000))
        except Exception as e:
            logger.debug("[AUDIO] Exception suppressed: %s", e)
            self._channels = 2
            self._sample_rate = 48000
        
        # Create callback wrapper
        self._callback = callback  # Store for restart

        def stream_callback(indata, frames, time_info, status):
            try:
                self._note_capture_callback()
                # Mix to mono if stereo
                if indata.shape[1] > 1:
                    samples = indata.mean(axis=1).astype(self._np.float32)
                else:
                    samples = indata[:, 0].astype(self._np.float32)
                callback(samples)
            except Exception as e:
                logger.debug("[AUDIO] Exception suppressed: %s", e)
        
        # Open stream
        try:
            device_idx = device.get("index") if isinstance(device, dict) else None
            self._stream = self._sd.InputStream(
                device=device_idx,
                channels=self._channels,
                samplerate=self._sample_rate,
                blocksize=self._config.block_size,
                dtype="float32",
                callback=stream_callback,
            )
            self._stream.start()
            self._running = True
            self._note_capture_starting()
            self._negotiated_block_size = int(self._config.block_size or 0)
            logger.info(
                "[AUDIO] sounddevice started (device=%s, negotiated_block=%d, preferred=%d, rate=%dHz, channels=%d)",
                device.get("name", "<unknown>") if isinstance(device, dict) else "<default>",
                self._negotiated_block_size,
                self._config.block_size,
                self._sample_rate,
                self._channels,
            )
            return True
        except Exception as e:
            logger.debug("[AUDIO] sounddevice stream failed: %s", e)
            return False
    
    def stop(self) -> None:
        self._running = False
        self._note_capture_stopped()
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.debug("[AUDIO] Exception suppressed: %s", e)
            self._stream = None
        self._negotiated_block_size = 0
    
    def is_running(self) -> bool:
        return self._running
    
    @property
    def sample_rate(self) -> int:
        return self._sample_rate
    
    @property
    def channels(self) -> int:
        return self._channels

    def restart(self) -> bool:
        """Restart the capture stream."""
        self.stop()
        if self._callback is not None:
            return self.start(self._callback)
        return False


def create_audio_capture(config: AudioCaptureConfig = None) -> Optional[AudioCaptureBackend]:
    """Create the best available audio capture backend.
    
    Tries PyAudioWPatch first on Windows, then falls back to sounddevice.
    
    Args:
        config: Optional capture configuration
        
    Returns:
        AudioCaptureBackend instance or None if no backend available
    """
    force_sounddevice = os.environ.get("SRPSS_FORCE_SOUNDDEVICE", "").lower() in ("1", "true", "yes")
    
    if platform.system().lower().startswith("win") and not force_sounddevice:
        backend = PyAudioWPatchBackend(config)
        # We don't start here - just return the backend
        return backend
    
    return SounddeviceBackend(config)
