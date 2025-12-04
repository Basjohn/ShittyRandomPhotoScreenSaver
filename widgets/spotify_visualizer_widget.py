from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import os
import platform
import time
import math

from PySide6.QtCore import QObject, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget
from shiboken6 import Shiboken

from core.logging.logger import get_logger, is_verbose_logging, is_perf_metrics_enabled
from core.threading.manager import ThreadManager
from utils.lockfree import TripleBuffer
from widgets.shadow_utils import apply_widget_shadow, ShadowFadeProfile
from utils.profiler import profile

logger = get_logger(__name__)

try:
    _DEBUG_CONST_BARS = float(os.environ.get("SRPSS_SPOTIFY_VIS_DEBUG_CONST", "0.0"))
except Exception:
    _DEBUG_CONST_BARS = 0.0


@dataclass
class _AudioFrame:
    samples: object


class SpotifyVisualizerAudioWorker(QObject):
    """Background audio worker for Spotify Beat Visualizer.

    Captures loopback audio via sounddevice and publishes FFT-derived
    bar magnitudes into a lock-free TripleBuffer for UI consumption.
    """

    def __init__(self, bar_count: int, buffer: TripleBuffer[_AudioFrame], parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._bar_count = max(1, int(bar_count))
        self._buffer = buffer
        self._running: bool = False
        self._stream = None
        self._sd = None
        self._np = None
        self._pa = None
        self._band_cache_key = None
        self._band_log_idx = None
        self._band_bins = None
        self._weight_bands = None
        self._weight_factors = None

    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return

        # NumPy is required for FFT regardless of backend.
        try:
            import numpy as np  # type: ignore[import]
        except Exception as exc:  # pragma: no cover - optional dependency
            logger.info("[SPOTIFY_VIS] numpy not available: %s", exc)
            return

        self._np = np

        # 1) Try PyAudioWPatch WASAPI loopback on Windows.
        if platform.system().lower().startswith("win"):
            try:
                import pyaudiowpatch as pyaudio  # type: ignore[import]
            except Exception as exc:  # pragma: no cover - optional dependency
                if is_verbose_logging():
                    logger.info(
                        "[SPOTIFY_VIS] PyAudioWPatch not available, falling back to sounddevice: %s",
                        exc,
                    )
                pyaudio = None  # type: ignore[assignment]

            if pyaudio is not None:
                try:
                    pa = pyaudio.PyAudio()
                except Exception:
                    pa = None
                if pa is not None:
                    try:
                        wasapi_info = pa.get_host_api_info_by_type(pyaudio.paWASAPI)
                    except OSError:
                        wasapi_info = None

                    default_speakers = None
                    if wasapi_info is not None:
                        try:
                            default_speakers = pa.get_device_info_by_index(
                                wasapi_info["defaultOutputDevice"]
                            )
                        except Exception:
                            default_speakers = None

                    if default_speakers is not None and not default_speakers.get("isLoopbackDevice"):
                        try:
                            try:
                                base_name = str(default_speakers.get("name", ""))
                            except Exception:
                                base_name = ""
                            chosen = None
                            for loopback in pa.get_loopback_device_info_generator():
                                try:
                                    loop_name = str(loopback.get("name", ""))
                                except Exception:
                                    loop_name = ""
                                if chosen is None:
                                    chosen = loopback
                                if base_name and base_name in loop_name:
                                    chosen = loopback
                                    break
                            default_speakers = chosen
                        except Exception:
                            default_speakers = None

                    if default_speakers is not None:
                        try:
                            channels = int(default_speakers.get("maxInputChannels", 0) or 0)
                        except Exception:
                            channels = 0
                        try:
                            samplerate = int(default_speakers.get("defaultSampleRate", 48000) or 48000)
                        except Exception:
                            samplerate = 48000

                        if channels > 0 and samplerate > 0:
                            # Prefer smaller audio blocks for lower latency where
                            # supported, with a slightly larger fallback size if
                            # the host API rejects 512-sample buffers.

                            def _pa_callback(in_data, frame_count, time_info, status_flags):
                                try:
                                    if not in_data:
                                        return (in_data, pyaudio.paContinue)
                                    np_mod = self._np
                                    data = np_mod.frombuffer(in_data, dtype=np_mod.int16)
                                    if data.size <= 0:
                                        return (in_data, pyaudio.paContinue)
                                    try:
                                        data = data.reshape(-1, channels)
                                    except Exception:
                                        data = data.reshape(-1, 1)
                                    mono = data.mean(axis=1).astype(np_mod.float32) / 32768.0
                                    peak = 0.0
                                    if is_verbose_logging():
                                        try:
                                            peak = float(np_mod.max(np_mod.abs(mono))) if mono.size else 0.0
                                        except Exception:
                                            peak = 0.0
                                    if mono.size > 2048:
                                        mono = mono[-2048:]
                                    mono = mono.astype(np_mod.float32, copy=False)
                                    self._buffer.publish(_AudioFrame(samples=mono.copy()))
                                    if is_verbose_logging():
                                        try:
                                            logger.debug(
                                                "[SPOTIFY_VIS] Audio callback frame (PyAudioWPatch): frames=%s peak=%.6f",
                                                frame_count,
                                                peak,
                                            )
                                        except Exception:
                                            pass
                                except Exception:
                                    if is_verbose_logging():
                                        logger.debug(
                                            "[SPOTIFY_VIS] Audio callback failed (PyAudioWPatch)",
                                            exc_info=True,
                                        )
                                return (in_data, pyaudio.paContinue)

                            stream = None
                            try:
                                # Try lower-latency 512-sample blocks first,
                                # then fall back to 1024-sample blocks if the
                                # host rejects the smaller size.
                                for chunk_size in (512, 1024):
                                    try:
                                        stream = pa.open(
                                            format=pyaudio.paInt16,
                                            channels=channels,
                                            rate=samplerate,
                                            frames_per_buffer=chunk_size,
                                            input=True,
                                            input_device_index=default_speakers["index"],
                                            stream_callback=_pa_callback,
                                        )
                                        stream.start_stream()
                                        self._pa = pa
                                        self._stream = stream
                                        self._running = True
                                        logger.info(
                                            "[SPOTIFY_VIS] Audio worker started via PyAudioWPatch (device=%s, name=%r, channels=%s, sr=%s, block=%s)",
                                            default_speakers.get("index"),
                                            default_speakers.get("name"),
                                            channels,
                                            samplerate,
                                            chunk_size,
                                        )
                                        return
                                    except Exception:
                                        # Clean up this attempt and try the
                                        # next block size.
                                        try:
                                            if stream is not None:
                                                try:
                                                    stream.stop_stream()
                                                except Exception:
                                                    pass
                                                try:
                                                    stream.close()
                                                except Exception:
                                                    pass
                                        except Exception:
                                            pass
                                        stream = None
                                # If we reach here, both block sizes failed;
                                # raise to trigger the outer teardown and
                                # sounddevice fallback.
                                raise
                            except Exception:
                                if is_verbose_logging():
                                    logger.error(
                                        "[SPOTIFY_VIS] Failed to open PyAudioWPatch WASAPI loopback",
                                        exc_info=True,
                                    )
                                try:
                                    if stream is not None:
                                        try:
                                            stream.stop_stream()
                                        except Exception:
                                            pass
                                        try:
                                            stream.close()
                                        except Exception:
                                            pass
                                except Exception:
                                    pass
                                try:
                                    pa.terminate()
                                except Exception:
                                    pass
                                self._pa = None
                                self._stream = None
                                self._running = False

        # 2) Fallback: existing sounddevice-based implementation.
        try:
            import sounddevice as sd  # type: ignore[import]
        except Exception as exc:  # pragma: no cover - optional dependency
            logger.info("[SPOTIFY_VIS] sounddevice not available: %s", exc)
            return

        self._sd = sd

        # First, try to capture using WASAPI loopback on the default output
        # device. This targets actual speaker/headphone output instead of a
        # potentially silent microphone input. If this fails for any reason,
        # we fall back to the generic input-device search below.
        WasapiSettings = getattr(sd, "WasapiSettings", None)
        if WasapiSettings is not None:
            try:
                hostapis = sd.query_hostapis()
            except Exception:
                hostapis = []

            wasapi_index: Optional[int] = None
            for idx, api in enumerate(hostapis or []):
                try:
                    name = str(api.get("name", "")).lower()
                except Exception:
                    name = ""
                if "wasapi" in name:
                    wasapi_index = idx
                    break

            if wasapi_index is not None:
                default_output = -1
                # Prefer host API's own default output device.
                try:
                    api_info = hostapis[wasapi_index]
                    default_output = int(api_info.get("default_output_device", -1))
                except Exception:
                    default_output = -1

                # Fallback: use sounddevice's global default output device,
                # but only if it belongs to the WASAPI host API.
                if default_output < 0:
                    try:
                        dev = sd.default.device
                        cand = -1
                        if isinstance(dev, (list, tuple)) and len(dev) >= 2:
                            cand = int(dev[1])
                        elif isinstance(dev, dict):
                            cand = int(dev.get("output", -1))
                        elif isinstance(dev, int):
                            cand = int(dev)
                        if cand >= 0:
                            info = sd.query_devices(cand)
                            if int(info.get("hostapi", -1)) == wasapi_index:
                                default_output = cand
                    except Exception:
                        default_output = -1

                if default_output >= 0:
                    # Derive a sensible samplerate/channels from the output
                    # side; WASAPI loopback mirrors the playback format.
                    try:
                        info = sd.query_devices(default_output, "output")
                        samplerate = float(info.get("default_samplerate", 48000.0)) or 48000.0
                        try:
                            max_out = int(info.get("max_output_channels", 0) or 0)
                        except Exception:
                            max_out = 0
                        channels = 2 if max_out >= 2 else 1 if max_out == 1 else 0
                    except Exception:
                        samplerate = 48000.0
                        channels = 2

                    if channels > 0:
                        # Prefer smaller blocks for lower latency on WASAPI
                        # loopback; sounddevice falls back internally when
                        # needed.
                        blocksize = 512

                        def _loopback_callback(indata, frames, time_info, status):  # type: ignore[override]
                            # This runs on the audio thread. Keep work minimal
                            # and lock-free.
                            try:
                                if indata is None or frames <= 0:
                                    return
                                mono = indata.mean(axis=1)
                                np = self._np
                                peak = 0.0
                                if is_verbose_logging():
                                    try:
                                        peak = float(np.max(np.abs(mono))) if mono.size else 0.0
                                    except Exception:
                                        peak = 0.0
                                if mono.size > 2048:
                                    mono = mono[-2048:]
                                mono = mono.astype("float32", copy=False)
                                self._buffer.publish(_AudioFrame(samples=mono.copy()))
                                if is_verbose_logging():
                                    try:
                                        logger.debug(
                                            "[SPOTIFY_VIS] Audio callback frame: frames=%s peak=%.6f",
                                            frames,
                                            peak,
                                        )
                                    except Exception:
                                        pass
                            except Exception:
                                if is_verbose_logging():
                                    logger.debug("[SPOTIFY_VIS] Audio callback failed", exc_info=True)

                        try:
                            ws = WasapiSettings(loopback=True)
                            stream = sd.InputStream(
                                samplerate=int(samplerate),
                                blocksize=blocksize,
                                channels=channels,
                                dtype="float32",
                                device=default_output,
                                callback=_loopback_callback,
                                extra_settings=ws,
                            )
                            stream.start()
                            self._stream = stream
                            self._running = True
                            logger.info(
                                "[SPOTIFY_VIS] Audio worker started (device=%s, channels=%s, sr=%s, block=%s, mode=wasapi_loopback)",
                                default_output,
                                channels,
                                samplerate,
                                blocksize,
                            )
                            return
                        except Exception:
                            if is_verbose_logging():
                                logger.error(
                                    "[SPOTIFY_VIS] Failed to open WASAPI loopback on device %s",
                                    default_output,
                                    exc_info=True,
                                )
                            # Fall through to generic input-device search.

        # Build an ordered list of candidate input devices. We bias
        # towards devices that are most likely to represent system
        # playback (default output loopback / stereo mix style) while
        # still falling back to any input-capable device that PortAudio
        # accepts.
        candidates: List[int] = []
        primary_idx: Optional[int]
        try:
            primary_idx = self._select_loopback_device()
        except Exception:
            primary_idx = None

        if primary_idx is not None:
            candidates.append(primary_idx)

        try:
            devices = sd.query_devices()
        except Exception:
            devices = []

        # Try to infer which input devices are tied to the default
        # output by name/keywords so we can try those first.
        default_output_name = ""
        try:
            out_info = sd.query_devices(None, "output")
            default_output_name = str(out_info.get("name", ""))
        except Exception:
            default_output_name = ""
        low_out = default_output_name.lower()

        by_name: List[int] = []
        by_keyword: List[int] = []
        others: List[int] = []

        if isinstance(devices, list):
            for idx, dev in enumerate(devices):
                if idx in candidates:
                    continue
                try:
                    max_in = int(dev.get("max_input_channels", 0) or 0)
                except Exception:
                    continue
                if max_in <= 0:
                    continue

                name = str(dev.get("name", ""))
                lname = name.lower()
                if low_out and low_out in lname:
                    by_name.append(idx)
                elif "loopback" in lname or "stereo mix" in lname or "what u hear" in lname:
                    by_keyword.append(idx)
                else:
                    others.append(idx)

        candidates.extend(by_name)
        candidates.extend(by_keyword)
        candidates.extend(others)

        if not candidates:
            logger.info("[SPOTIFY_VIS] No input-capable audio devices found; disabling visualizer")
            return

        chosen_device: Optional[int] = None
        chosen_samplerate = 48000.0
        chosen_channels = 2
        valid_candidates: List[tuple[int, float, int]] = []

        for idx in candidates:
            samplerate = 48000.0
            channels = 2
            try:
                info = sd.query_devices(idx, "input")
                samplerate = float(info.get("default_samplerate", samplerate)) or samplerate
                try:
                    max_in = int(info.get("max_input_channels", 0) or 0)
                except Exception:
                    max_in = 0
                if max_in >= 2:
                    channels = 2
                elif max_in == 1:
                    channels = 1
                else:
                    channels = 0
            except Exception:
                # Fall back to conservative defaults; check_input_settings
                # below will validate whether this device is usable.
                samplerate = 48000.0
                channels = 1

            if channels <= 0:
                continue

            # Validate with sounddevice/PortAudio before creating the
            # stream to avoid PortAudioError: Invalid device
            # [PaErrorCode -9996].
            try:
                checker = getattr(sd, "check_input_settings", None)
                if checker is not None:
                    checker(
                        device=idx,
                        samplerate=int(samplerate),
                        channels=channels,
                        dtype="float32",
                    )
            except Exception:
                if is_verbose_logging():
                    logger.info(
                        "[SPOTIFY_VIS] Rejecting candidate input device %s",
                        idx,
                        exc_info=True,
                    )
                continue

            valid_candidates.append((idx, samplerate, channels))

        if not valid_candidates:
            logger.info("[SPOTIFY_VIS] No valid input device after validation; disabling visualizer")
            return

        blocksize = 1024

        def _callback(indata, frames, time_info, status):  # type: ignore[override]
            # This runs on the audio thread. Keep work minimal and lock-free.
            try:
                if indata is None or frames <= 0:
                    return
                # Mix down to mono (average of channels) for stability.
                mono = indata.mean(axis=1)
                np = self._np
                peak = 0.0
                if is_verbose_logging():
                    try:
                        peak = float(np.max(np.abs(mono))) if mono.size else 0.0
                    except Exception:
                        peak = 0.0
                if mono.size > 2048:
                    mono = mono[-2048:]
                mono = mono.astype("float32", copy=False)
                self._buffer.publish(_AudioFrame(samples=mono.copy()))
                # Only log if verbose so the callback stays cheap.
                if is_verbose_logging():
                    try:
                        logger.debug(
                            "[SPOTIFY_VIS] Audio callback frame: frames=%s peak=%.6f",
                            frames,
                            peak,
                        )
                    except Exception:
                        pass
            except Exception:
                if is_verbose_logging():
                    logger.debug("[SPOTIFY_VIS] Audio callback failed", exc_info=True)
        stream = None

        for idx, samplerate, channels in valid_candidates:
            try:
                stream = sd.InputStream(
                    samplerate=int(samplerate),
                    blocksize=blocksize,
                    channels=channels,
                    dtype="float32",
                    device=idx,
                    callback=_callback,
                )
                stream.start()
            except Exception:
                if is_verbose_logging():
                    logger.error(
                        "[SPOTIFY_VIS] Failed to open candidate input device %s",
                        idx,
                        exc_info=True,
                    )
                stream = None
                continue

            chosen_device = idx
            chosen_samplerate = samplerate
            chosen_channels = channels
            break

        if stream is None or chosen_device is None:
            logger.info("[SPOTIFY_VIS] No input device could be opened; disabling visualizer")
            return

        self._stream = stream
        self._running = True
        logger.info(
            "[SPOTIFY_VIS] Audio worker started (device=%s, channels=%s, sr=%s, block=%s)",
            chosen_device,
            chosen_channels,
            chosen_samplerate,
            blocksize,
        )

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        try:
            if self._stream is not None:
                try:
                    stop_fn = getattr(self._stream, "stop", None)
                    if callable(stop_fn):
                        stop_fn()
                    else:
                        stop_stream = getattr(self._stream, "stop_stream", None)
                        if callable(stop_stream):
                            stop_stream()
                except Exception:
                    pass
                try:
                    close_fn = getattr(self._stream, "close", None)
                    if callable(close_fn):
                        close_fn()
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            self._stream = None
            try:
                pa = getattr(self, "_pa", None)
                if pa is not None:
                    try:
                        pa.terminate()
                    except Exception:
                        pass
                    self._pa = None
            except Exception:
                pass
            logger.info("[SPOTIFY_VIS] Audio worker stopped")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _select_loopback_device(self) -> Optional[int]:
        """Best-effort selection of a WASAPI loopback device on Windows.

        Prefers the default output device's loopback when available.
        Falls back to the default input device when loopback is not
        exposed so the widget still functions, albeit not strictly
        output-only.
        """

        sd = self._sd
        try:
            hostapis = sd.query_hostapis()
        except Exception:
            hostapis = []

        wasapi_index = None
        for idx, api in enumerate(hostapis or []):
            name = str(api.get("name", "")).lower()
            if "wasapi" in name:
                wasapi_index = idx
                break

        loopback_candidates: List[int] = []
        try:
            devices = sd.query_devices()
        except Exception:
            devices = []

        for idx, dev in enumerate(devices or []):
            host = dev.get("hostapi")
            if wasapi_index is not None and host != wasapi_index:
                continue
            name = str(dev.get("name", "")).lower()
            # Heuristic: WASAPI loopback devices often contain "loopback".
            if "loopback" in name:
                loopback_candidates.append(idx)

        if loopback_candidates:
            return loopback_candidates[0]

        # Fallback: pick the first device with input channels if available.
        for idx, dev in enumerate(devices or []):
            try:
                if int(dev.get("max_input_channels", 0)) > 0:
                    return idx
            except Exception:
                continue

        # Final fallback: default input device, but never return a negative
        # index – sounddevice/PortAudio treats -1 as an invalid device.
        try:
            default_dev = sd.default.device
            candidate = -1
            if isinstance(default_dev, (list, tuple)):
                candidate = int(default_dev[0])
            elif isinstance(default_dev, dict):
                candidate = int(default_dev.get("input", -1))
            else:
                candidate = int(default_dev)
            if candidate >= 0:
                return candidate
        except Exception:
            pass
        return None

    def _fft_to_bars(self, fft) -> List[float]:
        np = self._np
        if fft is None:
            return [0.0] * self._bar_count

        try:
            mag = fft[1:]
            if mag.size == 0:
                return [0.0] * self._bar_count
            if np.iscomplexobj(mag):
                mag = np.abs(mag)
            mag = mag.astype("float32", copy=False)
        except Exception:
            return [0.0] * self._bar_count

        n = int(mag.size)
        if n <= 0:
            return [0.0] * self._bar_count

        bands = int(self._bar_count)
        if bands <= 0:
            return []

        try:
            mag = np.log1p(mag)
            try:
                mag = mag ** 1.2
            except Exception:
                pass

            if n > 4:
                try:
                    kernel = np.array([0.25, 0.5, 0.25], dtype="float32")
                    mag = np.convolve(mag, kernel, mode="same")
                except Exception:
                    pass

            # Older versions applied an extra emphasis to the lowest ~10%% of
            # FFT bins here. With the current band weighting this leads to an
            # overly left-leaning visual, so we rely on the later spatial
            # weighting instead.
        except Exception:
            return [0.0] * bands

        cache_key = (n, bands)
        try:
            if getattr(self, "_band_cache_key", None) != cache_key:
                idx = np.arange(n, dtype="float32")
                log_idx = np.log1p(idx + 1.0)
                start = float(log_idx[0])
                end = float(log_idx[-1])
                edges = np.linspace(start, end, bands + 1, dtype="float32")
                bins = edges[1:-1]
                self._band_cache_key = cache_key
                self._band_log_idx = log_idx
                self._band_bins = bins
            log_idx = self._band_log_idx
            bins = self._band_bins
            if log_idx is None or bins is None:
                return [0.0] * bands
            band_idx = np.digitize(log_idx, bins, right=False)
            sums = np.bincount(band_idx, weights=mag, minlength=bands)
            counts = np.bincount(band_idx, minlength=bands)
            bars_arr = np.divide(
                sums,
                counts,
                out=np.zeros_like(sums, dtype="float32"),
                where=counts > 0,
            )
        except Exception:
            return [0.0] * bands

        arr = bars_arr.astype("float32", copy=False)
        peak = float(arr.max()) if arr.size else 0.0
        if peak <= 1e-6:
            return [0.0] * bands
        arr = arr / peak

        try:
            if getattr(self, "_weight_bands", None) != bands:
                positions = np.linspace(-1.0, 1.0, bands, dtype="float32")
                band_idx_f = np.arange(bands, dtype="float32")
                t = band_idx_f / max(1.0, float(bands - 1))

                # Keep a visual "hill" in the centre, but shift it slightly
                # to the right and narrow it so fewer bars sit at the same
                # height. This preserves the appealing centre focus while
                # avoiding a flat plateau and helping right-hand bands.
                tilt = 0.45 + 0.6 * t
                sigma = 0.60
                center_shift = 0.18
                center_profile = np.exp(-0.5 * ((positions - center_shift) / sigma) ** 2).astype(
                    "float32"
                )
                peak_profile = float(center_profile.max()) if center_profile.size else 0.0
                if peak_profile > 1e-6:
                    center_profile = center_profile / peak_profile

                center_weight = 0.40
                base_weights = (1.0 - center_weight) + center_weight * center_profile

                # Slightly stronger right bias so the main energy cluster is
                # at least one bar further right on average, without making
                # highs dominate.
                bias_strength = 0.75
                right_bias = 1.0 + bias_strength * positions
                right_bias = np.clip(
                    right_bias,
                    1.0 - bias_strength,
                    1.0 + bias_strength,
                )

                # Gently attenuate the lowest bands so they do not visually
                # swamp the spectrum even on bass-heavy tracks, without
                # flattening the overall curve.
                bass_atten = 1.0 - 0.16 * (1.0 - t) * (1.0 - t)
                total_weights = base_weights * tilt * right_bias * bass_atten
                self._weight_bands = bands
                self._weight_factors = total_weights.astype("float32", copy=False)
            weights = self._weight_factors
            if weights is not None and weights.size == arr.size:
                arr *= weights
        except Exception:
            pass

        try:
            if bands >= 3:
                left0 = float(arr[0])
                left1 = float(arr[1])
                right1 = float(arr[-2])
                edge_leak_left = 0.30
                right_trail_factor = 0.80
                arr[0] = left0 * (1.0 - edge_leak_left) + left1 * edge_leak_left
                forced_right = right1 * right_trail_factor
                if bands >= 2 and forced_right > float(arr[-1]):
                    arr[-1] = forced_right
        except Exception:
            pass

        peak2 = float(arr.max()) if arr.size else 0.0
        if peak2 > 1e-6:
            arr = arr / peak2
        arr = np.clip(arr, 0.0, 1.0)
        return [float(x) for x in arr.tolist()]

    def compute_bars_from_samples(self, samples) -> Optional[List[float]]:
        np_mod = self._np
        if np_mod is None or samples is None:
            return None
        try:
            mono = samples
            if hasattr(mono, "ndim") and mono.ndim > 1:
                try:
                    mono = mono.reshape(-1)
                except Exception:
                    return None
            try:
                mono = mono.astype("float32", copy=False)
            except Exception:
                pass
            size = getattr(mono, "size", 0)
            if size <= 0:
                return None
            if size > 2048:
                mono = mono[-2048:]
            # Treat very low overall amplitude as silence and return zeros so
            # we don't amplify numerical noise into full-height bars when
            # audio stops.
            try:
                peak_raw = float(np_mod.max(np_mod.abs(mono))) if getattr(mono, "size", 0) else 0.0
            except Exception:
                peak_raw = 0.0
            if peak_raw < 1e-3:
                target = int(self._bar_count)
                if target <= 0:
                    return None
                return [0.0] * target

            fft = np_mod.abs(np_mod.fft.rfft(mono))
            bars = self._fft_to_bars(fft)
            if not isinstance(bars, list):
                return None
            target = int(self._bar_count)
            if target <= 0:
                return None
            if len(bars) != target:
                if len(bars) < target:
                    bars = bars + [0.0] * (target - len(bars))
                else:
                    bars = bars[:target]
            return [max(0.0, min(1.0, float(v))) for v in bars]
        except Exception:
            if is_verbose_logging():
                logger.debug("[SPOTIFY_VIS] compute_bars_from_samples failed", exc_info=True)
            return None


class _SpotifyBeatEngine(QObject):
    def __init__(self, bar_count: int) -> None:
        super().__init__()
        self._bar_count = max(1, int(bar_count))
        self._audio_buffer: TripleBuffer[_AudioFrame] = TripleBuffer()
        self._audio_worker = SpotifyVisualizerAudioWorker(self._bar_count, self._audio_buffer, parent=self)
        self._bars_result_buffer: TripleBuffer[List[float]] = TripleBuffer()
        self._compute_task_active: bool = False
        self._thread_manager: Optional[ThreadManager] = None
        self._ref_count: int = 0
        self._latest_bars: Optional[List[float]] = None
        self._last_audio_ts: float = 0.0

    def set_thread_manager(self, thread_manager: Optional[ThreadManager]) -> None:
        self._thread_manager = thread_manager

    def acquire(self) -> None:
        self._ref_count += 1

    def release(self) -> None:
        if self._ref_count > 0:
            self._ref_count -= 1
        if self._ref_count == 0:
            self._stop_worker()

    def ensure_started(self) -> None:
        try:
            if not self._audio_worker.is_running():
                self._audio_worker.start()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to start audio worker in shared engine", exc_info=True)

    def _stop_worker(self) -> None:
        try:
            self._audio_worker.stop()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to stop audio worker in shared engine", exc_info=True)

    def _schedule_compute_bars_task(self, samples: object) -> None:
        tm = self._thread_manager
        if tm is None:
            return

        self._compute_task_active = True

        def _job(local_samples=samples):
            return self._audio_worker.compute_bars_from_samples(local_samples)

        def _on_result(result) -> None:
            try:
                self._compute_task_active = False
                success = getattr(result, "success", True)
                bars = getattr(result, "result", None)
                if not success:
                    return
                if isinstance(bars, list):
                    self._bars_result_buffer.publish(bars)
                    self._latest_bars = bars
                    try:
                        self._last_audio_ts = time.time()
                    except Exception:
                        pass
            except Exception:
                logger.debug("[SPOTIFY_VIS] compute task callback failed", exc_info=True)

        try:
            tm.submit_compute_task(_job, callback=_on_result)
        except Exception:
            self._compute_task_active = False

    def tick(self) -> Optional[List[float]]:
        tm = self._thread_manager

        now_ts = time.time()
        frame = self._audio_buffer.consume_latest()
        if frame is not None:
            samples = getattr(frame, "samples", None)
            if samples is not None:
                try:
                    self._last_audio_ts = now_ts
                except Exception:
                    pass
                if tm is not None:
                    if not self._compute_task_active:
                        self._schedule_compute_bars_task(samples)
                else:
                    bars_inline = self._audio_worker.compute_bars_from_samples(samples)
                    if isinstance(bars_inline, list):
                        try:
                            self._bars_result_buffer.publish(bars_inline)
                        except Exception:
                            pass
                        self._latest_bars = bars_inline

        # If we have not seen any audio for a short window, treat this as
        # silence and force the shared bars to zero so all widgets decay
        # together instead of holding stale peaks.
        try:
            last_ts = float(self._last_audio_ts)
        except Exception:
            last_ts = 0.0
        if last_ts > 0.0:
            try:
                silence_timeout = 0.4
                if (now_ts - last_ts) >= silence_timeout:
                    if isinstance(self._latest_bars, list) and self._bar_count > 0:
                        if any(b > 0.0 for b in self._latest_bars):
                            self._latest_bars = [0.0] * self._bar_count
            except Exception:
                pass

        return self._latest_bars


_global_beat_engine: Optional[_SpotifyBeatEngine] = None


def get_shared_spotify_beat_engine(bar_count: int) -> _SpotifyBeatEngine:
    global _global_beat_engine
    if _global_beat_engine is None:
        _global_beat_engine = _SpotifyBeatEngine(bar_count)
    else:
        try:
            existing = int(getattr(_global_beat_engine, "_bar_count", bar_count))
        except Exception:
            existing = bar_count
        if existing != int(bar_count):
            try:
                logger.debug(
                    "[SPOTIFY_VIS] Shared beat engine already initialised with bar_count=%s (requested=%s)",
                    existing,
                    bar_count,
                )
            except Exception:
                pass
    return _global_beat_engine


class SpotifyVisualizerWidget(QWidget):
    """Thin bar visualizer card paired with the Spotify media widget.

    The widget draws a rounded-rect card that inherits Spotify/Media
    styling from DisplayWidget and renders a row of vertical bars whose
    heights are driven by FFT magnitudes published by
    SpotifyVisualizerAudioWorker.
    """

    def __init__(self, parent: Optional[QWidget] = None, bar_count: int = 32) -> None:
        super().__init__(parent)

        self._bar_count = max(1, int(bar_count))
        self._display_bars: List[float] = [0.0] * self._bar_count
        self._target_bars: List[float] = [0.0] * self._bar_count
        self._per_bar_energy: List[float] = [0.0] * self._bar_count
        # Base smoothing time constant in seconds; actual per-tick blend
        # factor is derived from this and the real dt between ticks so that
        # behaviour stays consistent even if tick rate changes. Slightly
        # reduced from earlier values to make bar attacks feel less "late"
        # without removing the pleasant decay tail.
        self._smoothing: float = 0.18

        self._thread_manager: Optional[ThreadManager] = None
        self._bars_timer = None
        self._shadow_config = None
        self._show_background: bool = True
        self._animation_manager = None
        self._anim_listener_id: Optional[int] = None

        # Card style (mirrors Spotify/Media widget)
        self._bg_color = QColor(16, 16, 16, 255)
        self._bg_opacity: float = 0.7
        self._card_border_color = QColor(255, 255, 255, 230)
        self._border_width: int = 2

        # Bar styling
        self._bar_fill_color = QColor(200, 200, 200, 230)
        self._bar_border_color = QColor(255, 255, 255, 255)
        self._bar_segments: int = 16
        self._ghosting_enabled: bool = True
        self._ghost_alpha: float = 0.4
        self._ghost_decay_rate: float = 0.4

        # Behavioural gating
        self._spotify_playing: bool = False
        self._anchor_media: Optional[QWidget] = None
        self._has_seen_media: bool = False

        # Shared beat engine (single audio worker per process). We keep
        # aliases for _audio_worker/_bars_buffer/_bars_result_buffer so
        # existing tests and diagnostics continue to function, but all
        # heavy work is centralised in the engine.
        self._engine: Optional[_SpotifyBeatEngine] = get_shared_spotify_beat_engine(self._bar_count)
        try:
            engine = self._engine
            if engine is not None:
                # Canonical bar_count is driven by the shared engine.
                try:
                    engine_bar_count = int(getattr(engine, "_bar_count", self._bar_count))
                except Exception:
                    engine_bar_count = self._bar_count
                if engine_bar_count > 0 and engine_bar_count != self._bar_count:
                    self._bar_count = engine_bar_count
                    self._display_bars = [0.0] * self._bar_count
                    self._target_bars = [0.0] * self._bar_count
                    self._per_bar_energy = [0.0] * self._bar_count
                # Test/diagnostic aliases – these reference shared state.
                self._bars_buffer = engine._audio_buffer  # type: ignore[attr-defined]
                self._audio_worker = engine._audio_worker  # type: ignore[attr-defined]
                self._bars_result_buffer = engine._bars_result_buffer  # type: ignore[attr-defined]
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to attach shared beat engine", exc_info=True)

        self._enabled: bool = False
        self._paint_debug_logged: bool = False

        # Lightweight PERF profiling state for widget activity so we can
        # correlate Spotify playing state with Transition/FPS behaviour.
        self._perf_tick_start_ts: Optional[float] = None
        self._perf_tick_last_ts: Optional[float] = None
        self._perf_tick_frame_count: int = 0
        self._perf_tick_min_dt: float = 0.0
        self._perf_tick_max_dt: float = 0.0

        self._perf_paint_start_ts: Optional[float] = None
        self._perf_paint_last_ts: Optional[float] = None
        self._perf_paint_frame_count: int = 0
        self._perf_paint_min_dt: float = 0.0
        self._perf_paint_max_dt: float = 0.0

        # Lightweight view of capture→bars latency derived from the shared
        # beat engine's last-audio timestamp. Logged alongside Tick/Paint
        # metrics but kept in a separate line so existing schemas remain
        # stable for tools.
        self._perf_audio_lag_last_ms: float = 0.0
        self._perf_audio_lag_min_ms: float = 0.0
        self._perf_audio_lag_max_ms: float = 0.0

        # Last time we emitted a PERF snapshot while running. This allows us
        # to log Spotify visualiser activity periodically even if the widget
        # is never explicitly stopped/cleaned up (for example, if the
        # screensaver exits abruptly), so logs still capture its effective
        # update/paint rate alongside compositor and animation metrics.
        self._perf_last_log_ts: Optional[float] = None

        # Geometry cache for paintEvent to avoid per-frame recomputation of
        # bar/segment layout. Rebuilt on resize or when bar_count/segments
        # change.
        self._geom_cache_rect: Optional[QRect] = None
        self._geom_cache_bar_count: int = self._bar_count
        self._geom_cache_segments: int = self._bar_segments
        self._geom_bar_x: List[int] = []
        self._geom_seg_y: List[int] = []
        self._geom_bar_width: int = 0
        self._geom_seg_height: int = 0

        self._last_update_ts: float = 0.0
        self._last_smooth_ts: float = 0.0
        self._has_pushed_first_frame: bool = False
        # Base paint FPS caps for the visualiser; slightly higher than
        # before now that compositor/GL transitions are cheaper, while
        # still low enough that the visualiser cannot dominate the UI
        # event loop.
        self._base_max_fps: float = 90.0
        self._transition_max_fps: float = 90.0
        self._last_gpu_fade_sent: float = -1.0

        # When GPU overlay rendering is available, we disable the
        # widget's own bar drawing and instead push frames up to the
        # DisplayWidget, which owns a small QOpenGLWidget overlay.
        self._cpu_bars_enabled: bool = True
        # User-configurable switch controlling whether the legacy software
        # visualiser is allowed to draw bars when GPU rendering is
        # unavailable or disabled. Defaults to False so the GPU overlay
        # remains the primary path in OpenGL mode.
        self._software_visualizer_enabled: bool = False

        self._setup_ui()

    # ------------------------------------------------------------------
    # Public configuration
    # ------------------------------------------------------------------

    def set_thread_manager(self, thread_manager: ThreadManager) -> None:
        self._thread_manager = thread_manager
        try:
            engine = get_shared_spotify_beat_engine(self._bar_count)
            self._engine = engine
            engine.set_thread_manager(thread_manager)
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to propagate ThreadManager to shared beat engine", exc_info=True)

    def set_software_visualizer_enabled(self, enabled: bool) -> None:
        """Enable or disable the QWidget-based software visualiser path.

        When ``enabled`` is True, the widget is allowed to render bars via
        its own ``paintEvent`` when GPU rendering is unavailable (for
        example in software renderer mode). When False, the widget only
        exposes smoothed bar data to the GPU overlay and does not draw
        bars itself unless explicitly re-enabled.
        """

        try:
            self._software_visualizer_enabled = bool(enabled)
        except Exception:
            self._software_visualizer_enabled = bool(enabled)

    def attach_to_animation_manager(self, animation_manager) -> None:
        # Detach from any previous manager first to avoid stacking listeners.
        if self._animation_manager is not None and self._anim_listener_id is not None:
            try:
                if hasattr(self._animation_manager, "remove_tick_listener"):
                    self._animation_manager.remove_tick_listener(self._anim_listener_id)
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to remove previous AnimationManager listener", exc_info=True)

        self._animation_manager = animation_manager
        self._anim_listener_id = None

        try:
            def _tick_listener(dt: float) -> None:
                try:
                    # When a ThreadManager-driven timer is active, it is the
                    # authoritative tick source for the visualiser. In that
                    # case the AnimationManager should not also call
                    # `_on_tick`, otherwise the widget may be driven at a
                    # much higher effective rate than intended.
                    if not getattr(self, "_enabled", False):
                        return
                    if getattr(self, "_bars_timer", None) is not None:
                        return
                    self._on_tick()
                except Exception:
                    logger.debug("[SPOTIFY_VIS] AnimationManager-driven tick failed", exc_info=True)

            listener_id = animation_manager.add_tick_listener(_tick_listener)
            self._anim_listener_id = listener_id
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to attach to AnimationManager", exc_info=True)

    def detach_from_animation_manager(self) -> None:
        am = self._animation_manager
        listener_id = self._anim_listener_id
        if am is not None and listener_id is not None and hasattr(am, "remove_tick_listener"):
            try:
                am.remove_tick_listener(listener_id)
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to detach from AnimationManager", exc_info=True)
        self._animation_manager = None
        self._anim_listener_id = None

    def set_shadow_config(self, config) -> None:
        self._shadow_config = config

    def _update_card_style(self) -> None:
        if self._show_background:
            bg = QColor(self._bg_color)
            alpha = int(255 * max(0.0, min(1.0, self._bg_opacity)))
            bg.setAlpha(alpha)
            self.setStyleSheet(
                f"""
                QWidget {{
                    background-color: rgba({bg.red()}, {bg.green()}, {bg.blue()}, {bg.alpha()});
                    border: {self._border_width}px solid rgba({self._card_border_color.red()}, {self._card_border_color.green()}, {self._card_border_color.blue()}, {self._card_border_color.alpha()});
                    border-radius: 8px;
                }}
                """
            )
        else:
            self.setStyleSheet(
                """
                QWidget {
                    background-color: transparent;
                    border: 0px solid transparent;
                    border-radius: 8px;
                }
                """
            )

    def set_bar_style(self, *, bg_color: QColor, bg_opacity: float, border_color: QColor, border_width: int = 2,
                      show_background: bool = True) -> None:
        self._bg_color = QColor(bg_color)
        self._bg_opacity = max(0.0, min(1.0, float(bg_opacity)))
        self._card_border_color = QColor(border_color)
        self._border_width = max(0, int(border_width))
        self._show_background = bool(show_background)
        self._update_card_style()
        self.update()

    def set_bar_colors(self, fill_color: QColor, border_color: QColor) -> None:
        # Fill colour is applied per-bar; border colour controls the bar
        # outline tint. Card border remains driven by set_bar_style.
        self._bar_fill_color = QColor(fill_color)
        self._bar_border_color = QColor(border_color)
        self.update()

    def set_ghost_config(self, enabled: bool, alpha: float, decay: float) -> None:
        """Configure ghost trailing behaviour for the GPU bar overlay.

        ``enabled`` toggles whether ghost bars are drawn at all. ``alpha``
        controls their base opacity relative to the main bar border colour,
        and ``decay`` feeds into the overlay's peak-envelope decay so that
        higher values shorten the trail while lower values keep it visible
        for longer.
        """

        try:
            self._ghosting_enabled = bool(enabled)
        except Exception:
            self._ghosting_enabled = True

        try:
            ga = float(alpha)
        except Exception:
            ga = 0.4
        if ga < 0.0:
            ga = 0.0
        if ga > 1.0:
            ga = 1.0
        self._ghost_alpha = ga

        try:
            gd = float(decay)
        except Exception:
            gd = 0.4
        if gd < 0.0:
            gd = 0.0
        self._ghost_decay_rate = gd

    def set_anchor_media_widget(self, widget: QWidget) -> None:
        self._anchor_media = widget

    def handle_media_update(self, payload: dict) -> None:
        """Receive Spotify media state from MediaWidget.

        Expects payload from MediaWidget.media_updated with a ``state``
        field of "playing"/"paused"/"stopped". When not playing, the
        visualizer decays to idle even if other apps are producing audio.
        """

        try:
            state = str(payload.get("state", "")).lower()
        except Exception:
            state = ""
        prev = self._spotify_playing
        self._spotify_playing = state == "playing"

        first_media = not self._has_seen_media
        if first_media:
            self._has_seen_media = True
            parent = self.parent()

            def _starter() -> None:
                self._start_widget_fade_in(1500)

            if parent is not None and hasattr(parent, "request_overlay_fade_sync"):
                try:
                    parent.request_overlay_fade_sync("spotify_visualizer", _starter)
                except Exception:
                    _starter()
            else:
                _starter()

        if is_verbose_logging():
            try:
                logger.debug(
                    "[SPOTIFY_VIS] handle_media_update: state=%r (prev_playing=%s, now_playing=%s)",
                    state,
                    prev,
                    self._spotify_playing,
                )
            except Exception:
                pass
        if not self._spotify_playing:
            # Drive target bars to zero; smoothing path will fade them out.
            self._target_bars = [0.0] * self._bar_count

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._enabled:
            return
        self._enabled = True

        try:
            self.hide()
        except Exception:
            pass

        # Start audio capture via the shared beat engine so the buffer can
        # begin filling. Each widget acquires a reference so the engine can
        # stop cleanly once the last visualiser stops.
        try:
            engine = get_shared_spotify_beat_engine(self._bar_count)
            self._engine = engine
            if self._thread_manager is not None:
                engine.set_thread_manager(self._thread_manager)
            engine.acquire()
            engine.ensure_started()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to start shared beat engine", exc_info=True)

        # Schedule a recurring UI tick via ThreadManager; AnimationManager
        # tick listeners (when attached) act as a secondary timing source
        # but do not replace this fallback.
        if (
            self._thread_manager is not None
            and self._bars_timer is None
        ):
            try:
                # Tighter tick cadence (~16ms) so bar updates can track audio
                # more closely and approach high-refresh display rates while
                # still remaining well below the GL compositor's peak FPS.
                self._bars_timer = self._thread_manager.schedule_recurring(16, self._on_tick)
            except Exception:
                self._bars_timer = None

    def stop(self) -> None:
        if not self._enabled:
            return
        self._enabled = False

        try:
            engine = self._engine or get_shared_spotify_beat_engine(self._bar_count)
        except Exception:
            engine = None
        if engine is not None:
            try:
                engine.release()
            except Exception:
                logger.debug("[SPOTIFY_VIS] Failed to release shared beat engine", exc_info=True)

        try:
            self.detach_from_animation_manager()
        except Exception:
            logger.debug("[SPOTIFY_VIS] Failed to detach from AnimationManager on stop", exc_info=True)

        try:
            if self._bars_timer is not None:
                self._bars_timer.stop()
        except Exception:
            pass
        self._bars_timer = None

        # Emit a concise PERF summary for this widget's activity during the
        # last enabled period so we can see its effective update/paint rate
        # and dt jitter alongside compositor and animation metrics.
        self._log_perf_snapshot(reset=True)

        try:
            self.hide()
        except Exception:
            pass

    def cleanup(self) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # UI and painting
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        try:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        except Exception:
            pass
        # Slightly taller default so bars and card border have breathing
        # room and match the visual weight of other widgets.
        self.setMinimumHeight(78)
        self._update_card_style()

    def _start_widget_fade_in(self, duration_ms: int = 1500) -> None:
        if duration_ms <= 0:
            try:
                self.show()
            except Exception:
                pass
            try:
                ShadowFadeProfile.attach_shadow(
                    self,
                    self._shadow_config,
                    has_background_frame=self._show_background,
                )
            except Exception:
                logger.debug(
                    "[SPOTIFY_VIS] Failed to attach shadow in no-fade path",
                    exc_info=True,
                )
            return

        try:
            ShadowFadeProfile.start_fade_in(
                self,
                self._shadow_config,
                has_background_frame=self._show_background,
            )
        except Exception:
            logger.debug(
                "[SPOTIFY_VIS] _start_widget_fade_in fallback path triggered",
                exc_info=True,
            )
            try:
                self.show()
            except Exception:
                pass
            if self._shadow_config is not None:
                try:
                    apply_widget_shadow(
                        self,
                        self._shadow_config,
                        has_background_frame=self._show_background,
                    )
                except Exception:
                    logger.debug(
                        "[SPOTIFY_VIS] Failed to apply widget shadow in fallback path",
                        exc_info=True,
                    )

    def _get_gpu_fade_factor(self, now_ts: float) -> float:
        """Return fade factor for GPU bars based on ShadowFadeProfile.

        We prefer the shared ShadowFadeProfile progress when available so that
        the GL overlay tracks the exact same curve. When no progress is
        present we fall back to 1.0 while the widget is visible.
        """

        try:
            prog = getattr(self, "_shadowfade_progress", None)
        except Exception:
            prog = None

        if isinstance(prog, (float, int)):
            p = float(prog)
            if p <= 0.0:
                return 0.0
            if p >= 1.0:
                return 1.0

            # Clamp first, then apply a small delay so bars fade in slightly
            # after the card/shadow begin fading. This keeps practical sync
            # with ShadowFadeProfile while avoiding bars appearing "ready"
            # before the rest of the widget.
            p = max(0.0, min(1.0, p))
            delay = 0.15
            if p <= delay:
                return 0.0
            t = (p - delay) / (1.0 - delay)
            # Gentle ease-in so the bar opacity builds up smoothly.
            t = t * t
            return max(0.0, min(1.0, t))

        # Fallback: treat widget visibility as a coarse fade proxy.
        try:
            return 1.0 if self.isVisible() else 0.0
        except Exception:
            return 1.0

    def _rebuild_geometry_cache(self, rect: QRect) -> None:
        """Recompute cached bar/segment layout for the current geometry."""

        count = self._bar_count
        segments = max(1, getattr(self, "_bar_segments", 16))
        if rect.width() <= 0 or rect.height() <= 0 or count <= 0:
            self._geom_cache_rect = QRect()
            self._geom_cache_bar_count = count
            self._geom_cache_segments = segments
            self._geom_bar_x = []
            self._geom_seg_y = []
            self._geom_bar_width = 0
            self._geom_seg_height = 0
            return

        margin_x = 8
        margin_y = 6
        inner = rect.adjusted(margin_x, margin_y, -margin_x, -margin_y)
        if inner.width() <= 0 or inner.height() <= 0:
            self._geom_cache_rect = inner
            self._geom_cache_bar_count = count
            self._geom_cache_segments = segments
            self._geom_bar_x = []
            self._geom_seg_y = []
            self._geom_bar_width = 0
            self._geom_seg_height = 0
            return

        gap = 2
        total_gap = gap * (count - 1) if count > 1 else 0
        bar_width = max(1, int((inner.width() - total_gap) / max(1, count)))
        # Small horizontal offset so the bar field aligns visually with the
        # card frame and matches the GL overlay geometry.
        x0 = inner.left() + 5
        bar_x = [x0 + i * (bar_width + gap) for i in range(count)]

        seg_gap = 1
        total_seg_gap = seg_gap * max(0, segments - 1)
        seg_height = max(1, int((inner.height() - total_seg_gap) / max(1, segments)))
        base_bottom = inner.bottom()
        seg_y = [base_bottom - s * (seg_height + seg_gap) - seg_height + 1 for s in range(segments)]

        self._geom_cache_rect = inner
        self._geom_cache_bar_count = count
        self._geom_cache_segments = segments
        self._geom_bar_x = bar_x
        self._geom_seg_y = seg_y
        self._geom_bar_width = bar_width
        self._geom_seg_height = seg_height

    def _on_tick(self) -> None:
        """Periodic UI tick scheduled via ThreadManager.

        Consumes the latest bar frame from the TripleBuffer and smoothly
        interpolates towards it for visual stability.
        """
        try:
            if not Shiboken.isValid(self):
                try:
                    if self._bars_timer is not None:
                        self._bars_timer.stop()
                except Exception:
                    pass
                self._bars_timer = None
                self._enabled = False
                return
        except Exception:
            return

        if not self._enabled:
            return

        now_ts = time.time()

        if is_perf_metrics_enabled():
            try:
                if self._perf_tick_start_ts is None:
                    self._perf_tick_start_ts = now_ts
                if self._perf_tick_last_ts is not None:
                    dt = now_ts - self._perf_tick_last_ts
                    if dt > 0.0:
                        if self._perf_tick_min_dt == 0.0 or dt < self._perf_tick_min_dt:
                            self._perf_tick_min_dt = dt
                        if dt > self._perf_tick_max_dt:
                            self._perf_tick_max_dt = dt
                self._perf_tick_last_ts = now_ts
                self._perf_tick_frame_count += 1

                # Periodically emit a PERF snapshot while running so that
                # logs capture the visualiser's effective tick/paint rate
                # even if the widget is never explicitly stopped.
                if self._perf_last_log_ts is None or (now_ts - self._perf_last_log_ts) >= 5.0:
                    self._log_perf_snapshot(reset=False)
                    self._perf_last_log_ts = now_ts
            except Exception:
                logger.debug("[SPOTIFY_VIS] Tick PERF accounting failed", exc_info=True)

        with profile("SPOTIFY_VIS_TICK", threshold_ms=5.0, log_level="DEBUG"):
            bars = None
            try:
                engine = self._engine or get_shared_spotify_beat_engine(self._bar_count)
                self._engine = engine
                if engine is not None:
                    bars = engine.tick()
                    # Track capture→bars latency so PERF logs can report how
                    # far behind the latest audio frame the visualiser is.
                    try:
                        last_audio_ts = float(getattr(engine, "_last_audio_ts", 0.0))
                    except Exception:
                        last_audio_ts = 0.0
                    if last_audio_ts > 0.0:
                        try:
                            lag_ms = max(0.0, (now_ts - last_audio_ts) * 1000.0)
                        except Exception:
                            lag_ms = 0.0
                        try:
                            self._perf_audio_lag_last_ms = lag_ms
                            if self._perf_audio_lag_min_ms == 0.0 or lag_ms < self._perf_audio_lag_min_ms:
                                self._perf_audio_lag_min_ms = lag_ms
                            if lag_ms > self._perf_audio_lag_max_ms:
                                self._perf_audio_lag_max_ms = lag_ms
                        except Exception:
                            pass
            except Exception:
                logger.debug("[SPOTIFY_VIS] Shared beat engine tick failed", exc_info=True)
                bars = None

            if isinstance(bars, list):
                # Use the spectral shape produced by _fft_to_bars and the
                # static weighting directly, only clamping into [0, 1]. This
                # avoids over-flattening from aggressive per-bar
                # normalisation while still allowing the smoothing logic
                # below to control rise/decay.
                try:
                    count = self._bar_count
                    if count <= 0:
                        self._target_bars = []
                    else:
                        clamped: List[float] = []  # type: ignore[valid-type]
                        for i in range(count):
                            try:
                                v = float(bars[i])
                            except Exception:
                                v = 0.0
                            if v < 0.0:
                                v = 0.0
                            if v > 1.0:
                                v = 1.0
                            clamped.append(v)
                        self._target_bars = clamped
                except Exception:
                    try:
                        self._target_bars = [
                            0.0 if v is None else max(0.0, min(1.0, float(v))) for v in (bars or [])
                        ]
                    except Exception:
                        self._target_bars = [0.0] * self._bar_count

                # Optional debug path: when SRPSS_SPOTIFY_VIS_DEBUG_CONST is
                # set to a value in (0, 1], override all target bars with a
                # constant so GPU geometry artefacts can be isolated from
                # audio data.
                if _DEBUG_CONST_BARS > 0.0:
                    const_val = _DEBUG_CONST_BARS
                    if const_val > 1.0:
                        const_val = 1.0
                    self._target_bars = [const_val] * self._bar_count

                if is_verbose_logging():
                    try:
                        logger.debug(
                            "[SPOTIFY_VIS] _on_tick: received bars (min=%.4f, max=%.4f)",
                            min(self._target_bars) if self._target_bars else 0.0,
                            max(self._target_bars) if self._target_bars else 0.0,
                        )
                    except Exception:
                        pass

            if not self._spotify_playing:
                self._target_bars = [0.0] * self._bar_count

            # When debug constant-bar mode is enabled, bypass the smoothing
            # path entirely so that any visible artefacts are guaranteed to
            # come from geometry/compositing rather than timing or per-bar
            # state. This is controlled via the SRPSS_SPOTIFY_VIS_DEBUG_CONST
            # environment variable.
            if _DEBUG_CONST_BARS > 0.0:
                const_val = _DEBUG_CONST_BARS
                if const_val > 1.0:
                    const_val = 1.0
                if const_val < 0.0:
                    const_val = 0.0
                self._display_bars = [const_val] * self._bar_count
                changed = True
            else:
                changed = False

                # Convert the fixed smoothing constant into a time-based
                # blend factor so behaviour remains consistent across
                # different tick rates (ThreadManager vs
                # AnimationManager-driven). We use the per-tick delta since
                # the last smoothing step rather than time since the last
                # repaint so smoothing is independent of paint throttling.
                dt_smooth = 0.0
                try:
                    last_smooth = self._last_smooth_ts
                    if last_smooth >= 0.0:
                        dt_smooth = max(0.0, now_ts - last_smooth)
                except Exception:
                    dt_smooth = 0.0
                try:
                    self._last_smooth_ts = now_ts
                except Exception:
                    pass
                base_tau = max(0.05, float(self._smoothing))
                if dt_smooth <= 0.0:
                    alpha_rise = 0.0
                    alpha_decay = 0.0
                else:
                    try:
                        # Make rises more responsive (shorter attack) while
                        # giving decay a much longer tail so motion leaves
                        # a clearly visible trace at higher tick rates.
                        tau_rise = base_tau * 0.35
                        tau_decay = base_tau * 3.0
                        alpha_rise = 1.0 - math.exp(-dt_smooth / tau_rise)
                        alpha_decay = 1.0 - math.exp(-dt_smooth / tau_decay)
                    except Exception:
                        linear = min(1.0, dt_smooth / base_tau)
                        alpha_rise = linear
                        alpha_decay = linear
                alpha_rise = max(0.0, min(1.0, alpha_rise))
                alpha_decay = max(0.0, min(1.0, alpha_decay))
                for i in range(self._bar_count):
                    cur = self._display_bars[i]
                    try:
                        tgt = self._target_bars[i]
                    except Exception:
                        tgt = 0.0
                    alpha = alpha_rise if tgt >= cur else alpha_decay
                    nxt = cur + (tgt - cur) * alpha
                    # Snap extremely small residuals to zero so ghost
                    # envelopes can fully collapse back to the 1-bar floor.
                    if abs(nxt) < 1e-3:
                        nxt = 0.0
                    if abs(nxt - cur) > 1e-3:
                        changed = True
                    self._display_bars[i] = nxt

            # Always push at least one frame so the visualiser baseline is
            # visible as soon as the widget fades in, even before audio
            # arrives.
            if not getattr(self, "_has_pushed_first_frame", False):
                changed = True

            if changed:
                max_fps = self._base_max_fps
                try:
                    parent = self.parent()
                    if parent is not None and hasattr(parent, "has_running_transition"):
                        if bool(parent.has_running_transition()):
                            max_fps = self._transition_max_fps
                except Exception:
                    pass

                min_dt = 0.0
                try:
                    if max_fps > 0.0:
                        min_dt = 1.0 / max_fps
                except Exception:
                    min_dt = 0.0

                last = self._last_update_ts
                if last <= 0.0 or (now_ts - last) >= min_dt:
                    self._last_update_ts = now_ts

                    used_gpu = False
                    need_card_update = False
                    parent = self.parent()
                    # When DisplayWidget exposes a GPU overlay path, prefer
                    # that and disable CPU bar drawing once it succeeds.
                    if parent is not None and hasattr(parent, "push_spotify_visualizer_frame"):
                        try:
                            fade = self._get_gpu_fade_factor(now_ts)
                        except Exception:
                            fade = 1.0
                        try:
                            prev_fade = getattr(self, "_last_gpu_fade_sent", -1.0)
                        except Exception:
                            prev_fade = -1.0
                        try:
                            self._last_gpu_fade_sent = float(fade)
                        except Exception:
                            pass
                        try:
                            if prev_fade < 0.0 or abs(fade - prev_fade) >= 0.01:
                                need_card_update = True
                        except Exception:
                            need_card_update = True
                        try:
                            used_gpu = bool(parent.push_spotify_visualizer_frame(
                                bars=list(self._display_bars),
                                bar_count=self._bar_count,
                                segments=getattr(self, "_bar_segments", 16),
                                fill_color=self._bar_fill_color,
                                border_color=self._bar_border_color,
                                fade=fade,
                                playing=self._spotify_playing,
                                ghosting_enabled=getattr(self, "_ghosting_enabled", True),
                                ghost_alpha=getattr(self, "_ghost_alpha", 0.4),
                                ghost_decay=getattr(self, "_ghost_decay_rate", 0.4),
                            ))
                        except Exception:
                            used_gpu = False

                    if used_gpu:
                        try:
                            self._has_pushed_first_frame = True
                        except Exception:
                            pass
                        try:
                            self._cpu_bars_enabled = False
                        except Exception:
                            pass
                        # Card/background/shadow still repaint via stylesheet
                        # and ShadowFadeProfile; we do not need to redraw bars
                        # when GPU overlay is active.
                        if need_card_update:
                            try:
                                self.update()
                            except Exception:
                                pass
                    else:
                        # Fallback: when there is no DisplayWidget/GPU bridge
                        # (for example in tests or standalone widget usage),
                        # always allow the QWidget-based bar renderer so
                        # behaviour matches the historical implementation.
                        parent = self.parent()
                        has_gpu_parent = parent is not None and hasattr(parent, "push_spotify_visualizer_frame")
                        if not has_gpu_parent or getattr(self, "_software_visualizer_enabled", False):
                            try:
                                self._cpu_bars_enabled = True
                            except Exception:
                                pass
                            try:
                                self.update()
                                try:
                                    self._has_pushed_first_frame = True
                                except Exception:
                                    pass
                            except Exception:
                                pass

    def paintEvent(self, event: QPaintEvent) -> None:  # type: ignore[override]
        super().paintEvent(event)

        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        except Exception:
            pass

        rect = self.rect()
        if is_verbose_logging() and not getattr(self, "_paint_debug_logged", False):
            try:
                anchor = self._anchor_media
                anchor_geom_ok = bool(anchor and anchor.width() > 0 and anchor.height() > 0)
                logger.debug(
                    "[SPOTIFY_VIS] paintEvent: geom=(%s,%s,%s,%s) rect=(%s,%s,%s,%s) enabled=%s visible=%s spotify_playing=%s show_bg=%s anchor_geom_ok=%s",
                    self.x(),
                    self.y(),
                    self.width(),
                    self.height(),
                    rect.x(),
                    rect.y(),
                    rect.width(),
                    rect.height(),
                    self._enabled,
                    self.isVisible(),
                    self._spotify_playing,
                    self._show_background,
                    anchor_geom_ok,
                )
            except Exception:
                pass
            try:
                self._paint_debug_logged = True
            except Exception:
                pass
        if rect.width() <= 0 or rect.height() <= 0:
            painter.end()
            return

        # When GPU overlay rendering is active for this widget instance, the
        # card/fade/shadow are still drawn via stylesheets and
        # ShadowFadeProfile, but the bar geometry itself is rendered by the
        # GL overlay. In that mode we skip the CPU bar drawing entirely.
        if not getattr(self, "_cpu_bars_enabled", True):
            painter.end()
            return

        if is_perf_metrics_enabled():
            try:
                now = time.time()
                if self._perf_paint_start_ts is None:
                    self._perf_paint_start_ts = now
                if self._perf_paint_last_ts is not None:
                    dt = now - self._perf_paint_last_ts
                    if dt > 0.0:
                        if self._perf_paint_min_dt == 0.0 or dt < self._perf_paint_min_dt:
                            self._perf_paint_min_dt = dt
                        if dt > self._perf_paint_max_dt:
                            self._perf_paint_max_dt = dt
                self._perf_paint_last_ts = now
                self._perf_paint_frame_count += 1
            except Exception:
                logger.debug("[SPOTIFY_VIS] Paint PERF accounting failed", exc_info=True)

        # Note: paintEvent itself does not trigger PERF snapshots; these are
        # driven from the tick path so that tick/paint metrics share a common
        # time window and appear as a paired summary in logs.

        with profile("SPOTIFY_VIS_PAINT", threshold_ms=5.0, log_level="DEBUG"):
            # Card background is handled by the stylesheet; painting focuses on
            # the bar geometry only. Use a cached layout to avoid recomputing
            # per-frame integer geometry.

            segments = max(1, getattr(self, "_bar_segments", 16))
            if (
                self._geom_cache_rect is None
                or self._geom_cache_rect.width() != rect.width()
                or self._geom_cache_rect.height() != rect.height()
                or self._geom_cache_bar_count != self._bar_count
                or self._geom_cache_segments != segments
            ):
                self._rebuild_geometry_cache(rect)

            inner = self._geom_cache_rect
            bar_x = self._geom_bar_x
            seg_y = self._geom_seg_y
            bar_width = self._geom_bar_width
            seg_height = self._geom_seg_height
            if (
                inner is None
                or inner.width() <= 0
                or inner.height() <= 0
                or not bar_x
                or not seg_y
                or bar_width <= 0
                or seg_height <= 0
            ):
                painter.end()
                return

            count = self._bar_count
            count = min(count, len(bar_x))

            fill = QColor(self._bar_fill_color)
            border = QColor(self._bar_border_color)
            max_segments = min(segments, len(seg_y))

            painter.setBrush(fill)
            painter.setPen(border)

            for i in range(count):
                x = bar_x[i]
                value = max(0.0, min(1.0, self._display_bars[i]))
                if value <= 0.0:
                    continue
                boosted = value * 1.2
                if boosted > 1.0:
                    boosted = 1.0
                active = int(round(boosted * segments))
                if active <= 0:
                    if self._spotify_playing and value > 0.0:
                        active = 1
                    else:
                        continue
                active = min(active, max_segments)
                for s in range(active):
                    y = seg_y[s]
                    bar_rect = QRect(x, y, bar_width, seg_height)
                    painter.drawRect(bar_rect)

            painter.end()

    def _log_perf_snapshot(self, reset: bool = False) -> None:
        """Emit a PERF metrics snapshot for the current tick/paint window.

        When ``reset`` is True, internal counters are cleared afterwards so
        subsequent snapshots start a fresh window (used on widget stop).
        When ``reset`` is False, counters are left intact so that periodic
        logging during runtime does not disturb the measurement window.
        """

        if not is_perf_metrics_enabled():
            return

        try:
            if (
                self._perf_tick_start_ts is not None
                and self._perf_tick_last_ts is not None
                and self._perf_tick_frame_count > 0
            ):
                elapsed = max(0.0, self._perf_tick_last_ts - self._perf_tick_start_ts)
                if elapsed > 0.0:
                    duration_ms = elapsed * 1000.0
                    avg_fps = self._perf_tick_frame_count / elapsed
                    min_dt_ms = self._perf_tick_min_dt * 1000.0 if self._perf_tick_min_dt > 0.0 else 0.0
                    max_dt_ms = self._perf_tick_max_dt * 1000.0 if self._perf_tick_max_dt > 0.0 else 0.0
                    logger.info(
                        "[PERF] [SPOTIFY_VIS] Tick metrics: duration=%.1fms, frames=%d, avg_fps=%.1f, "
                        "dt_min=%.2fms, dt_max=%.2fms, bar_count=%d",
                        duration_ms,
                        self._perf_tick_frame_count,
                        avg_fps,
                        min_dt_ms,
                        max_dt_ms,
                        self._bar_count,
                    )

            if (
                self._perf_paint_start_ts is not None
                and self._perf_paint_last_ts is not None
                and self._perf_paint_frame_count > 0
            ):
                elapsed_p = max(0.0, self._perf_paint_last_ts - self._perf_paint_start_ts)
                if elapsed_p > 0.0:
                    duration_ms_p = elapsed_p * 1000.0
                    avg_fps_p = self._perf_paint_frame_count / elapsed_p
                    min_dt_ms_p = self._perf_paint_min_dt * 1000.0 if self._perf_paint_min_dt > 0.0 else 0.0
                    max_dt_ms_p = self._perf_paint_max_dt * 1000.0 if self._perf_paint_max_dt > 0.0 else 0.0
                    logger.info(
                        "[PERF] [SPOTIFY_VIS] Paint metrics: duration=%.1fms, frames=%d, avg_fps=%.1f, "
                        "dt_min=%.2fms, dt_max=%.2fms, bar_count=%d",
                        duration_ms_p,
                        self._perf_paint_frame_count,
                        avg_fps_p,
                        min_dt_ms_p,
                        max_dt_ms_p,
                        self._bar_count,
                    )
            # Emit a separate AudioLag metrics line so tools that parse
            # Tick/Paint summaries remain compatible.
            try:
                if self._perf_audio_lag_last_ms > 0.0:
                    logger.info(
                        "[PERF] [SPOTIFY_VIS] AudioLag metrics: last=%.2fms, min=%.2fms, max=%.2fms",
                        self._perf_audio_lag_last_ms,
                        self._perf_audio_lag_min_ms,
                        self._perf_audio_lag_max_ms,
                    )
            except Exception:
                logger.debug("[SPOTIFY_VIS] AudioLag PERF metrics logging failed", exc_info=True)
        except Exception:
            logger.debug("[SPOTIFY_VIS] PERF metrics logging failed", exc_info=True)
        finally:
            if reset:
                self._perf_tick_start_ts = None
                self._perf_tick_last_ts = None
                self._perf_tick_frame_count = 0
                self._perf_tick_min_dt = 0.0
                self._perf_tick_max_dt = 0.0
                self._perf_paint_start_ts = None
                self._perf_paint_last_ts = None
                self._perf_paint_frame_count = 0
                self._perf_paint_min_dt = 0.0
                self._perf_paint_max_dt = 0.0
                self._perf_audio_lag_last_ms = 0.0
                self._perf_audio_lag_min_ms = 0.0
                self._perf_audio_lag_max_ms = 0.0

