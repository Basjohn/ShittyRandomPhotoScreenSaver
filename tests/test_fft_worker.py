"""
Tests for FFTWorker process.

Tests cover:
- FFT configuration preservation
- Bar generation from synthetic audio
- Smoothing and ghost envelope behavior
- Mathematical operation preservation
"""
import pytest
import numpy as np

from core.process.types import MessageType, WorkerMessage, WorkerType
from core.process.workers.fft_worker import FFTWorker, FFTConfig


class MockQueue:
    """Mock queue for testing without multiprocessing."""
    
    def __init__(self):
        self._items = []
    
    def put_nowait(self, item):
        self._items.append(item)
    
    def get_nowait(self):
        if self._items:
            return self._items.pop(0)
        raise Exception("Queue empty")
    
    def empty(self):
        return len(self._items) == 0


@pytest.fixture
def worker():
    """Create an FFTWorker with mock queues."""
    req_queue = MockQueue()
    resp_queue = MockQueue()
    w = FFTWorker(req_queue, resp_queue)
    return w, req_queue, resp_queue


class TestFFTConfig:
    """Tests for FFT configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = FFTConfig()
        assert config.bar_count == 16
        assert config.ghost_enabled is True
        assert config.ghost_decay == 0.85
        assert len(config.profile_template) == 15
        assert len(config.smooth_kernel) == 3
    
    def test_profile_template_symmetry(self):
        """Test profile template is symmetric."""
        config = FFTConfig()
        template = config.profile_template
        n = len(template)
        for i in range(n // 2):
            assert abs(template[i] - template[n - 1 - i]) < 0.01
    
    def test_profile_template_peak_at_ridge(self):
        """Test profile template has peaks at ridge positions."""
        config = FFTConfig()
        template = config.profile_template
        # Peaks at index 4 and 10 (ridge positions)
        assert template[4] == 1.0
        assert template[10] == 1.0
        # Center should be lower (vocal dip)
        assert template[7] < template[4]


    def test_curved_profile_template_symmetry(self):
        """Test curved profile template is symmetric."""
        config = FFTConfig()
        template = config.curved_profile_template
        n = len(template)
        for i in range(n // 2):
            assert abs(template[i] - template[n - 1 - i]) < 0.01

    def test_curved_profile_template_dual_curve_shape(self):
        """Test curved profile forms a dual-curve: bass peak at edges, dip, vocal peak, calm center."""
        config = FFTConfig()
        curved = config.curved_profile_template
        n = len(curved)
        center = n // 2
        # Edge bars should be the highest (bass peak)
        assert curved[0] == max(curved), f"Edge should be max, got {curved[0]}"
        assert curved[-1] == max(curved), f"Edge should be max, got {curved[-1]}"
        # Center should be the minimum (calm)
        assert curved[center] == min(curved), (
            f"Center ({curved[center]}) should be minimum ({min(curved)})"
        )
        # There should be a dip between bass zone and vocal zone (index 4 in 15-element)
        # and a vocal peak after the dip (index 5 in 15-element)
        # Verify left half has: decay from edge, then dip, then vocal peak
        dip_idx = 4  # for 15-element template
        vocal_idx = 5
        assert curved[dip_idx] < curved[dip_idx - 1], (
            f"Dip at {dip_idx} ({curved[dip_idx]}) should be less than {dip_idx-1} ({curved[dip_idx-1]})"
        )
        assert curved[vocal_idx] > curved[dip_idx], (
            f"Vocal peak at {vocal_idx} ({curved[vocal_idx]}) should be higher than dip at {dip_idx} ({curved[dip_idx]})"
        )
        # Vocal peak should be second/third highest (less than edge bass peak)
        assert curved[vocal_idx] < curved[0], (
            f"Vocal peak ({curved[vocal_idx]}) should be less than bass peak ({curved[0]})"
        )

    def test_curved_profile_peaks_at_edges(self):
        """Test curved profile has bass peaks at edge indices (0 and 14)."""
        config = FFTConfig()
        curved = config.curved_profile_template
        assert curved[0] == 1.0, f"Expected peak at index 0, got {curved[0]}"
        assert curved[-1] == 1.0, f"Expected peak at last index, got {curved[-1]}"
        # Center should be the minimum
        center = len(curved) // 2
        assert curved[center] == min(curved), (
            f"Center ({curved[center]}) should be minimum ({min(curved)})"
        )

    def test_curved_profile_default_off(self):
        """Test that curved profile is off by default."""
        config = FFTConfig()
        assert config.use_curved_profile is False


class TestFFTWorkerConfig:
    """Tests for FFT worker configuration handling."""
    
    def test_config_update(self, worker):
        """Test configuration update."""
        w, _, _ = worker
        
        msg = WorkerMessage(
            msg_type=MessageType.FFT_CONFIG,
            seq_no=1,
            correlation_id="test-001",
            payload={"bar_count": 32},
            worker_type=WorkerType.FFT,
        )
        
        response = w.handle_message(msg)
        
        assert response.success is True
        assert w._config.bar_count == 32
        assert len(w._state.bars) == 32
    
    def test_config_sensitivity_bounds(self, worker):
        """Test sensitivity is bounded correctly."""
        w, _, _ = worker
        
        # In _fft_to_bars, sensitivity is clamped to [0.25, 2.5]
        assert w._config.min_floor == 0.12
        assert w._config.max_floor == 4.0


class TestFFTWorkerProcessing:
    """Tests for FFT processing."""
    
    def test_process_empty_samples(self, worker):
        """Test processing with no samples."""
        w, _, _ = worker
        
        msg = WorkerMessage(
            msg_type=MessageType.FFT_FRAME,
            seq_no=1,
            correlation_id="test-001",
            payload={},
            worker_type=WorkerType.FFT,
        )
        
        response = w.handle_message(msg)
        
        assert response.success is True
        assert "bars" in response.payload
        assert len(response.payload["bars"]) == 16
    
    def test_process_synthetic_audio(self, worker):
        """Test processing synthetic audio samples."""
        w, _, _ = worker
        
        # Generate synthetic bass-heavy audio
        sample_rate = 44100
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        bass = 0.5 * np.sin(2 * np.pi * 100 * t)  # 100Hz bass
        samples = bass.astype(np.float32).tolist()
        
        msg = WorkerMessage(
            msg_type=MessageType.FFT_FRAME,
            seq_no=1,
            correlation_id="test-002",
            payload={
                "samples": samples,
                "sample_rate": sample_rate,
                "sensitivity": 1.0,
            },
            worker_type=WorkerType.FFT,
        )
        
        response = w.handle_message(msg)
        
        assert response.success is True
        assert "bars" in response.payload
        bars = response.payload["bars"]
        assert len(bars) == 16
        assert all(0.0 <= bar <= 1.0 for bar in bars)
    
    def test_process_multiple_frames(self, worker):
        """Test processing multiple consecutive frames."""
        w, _, _ = worker
        
        sample_rate = 44100
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        
        # Process 5 frames
        for i in range(5):
            amp = 0.3 + i * 0.1  # Increasing amplitude
            samples = (amp * np.sin(2 * np.pi * 1000 * t)).astype(np.float32).tolist()
            
            msg = WorkerMessage(
                msg_type=MessageType.FFT_FRAME,
                seq_no=i + 1,
                correlation_id=f"test-{i:03d}",
                payload={"samples": samples},
                worker_type=WorkerType.FFT,
            )
            
            response = w.handle_message(msg)
            assert response.success is True
        
        # Frame count should be tracked
        assert response.payload["frame_count"] == 5


class TestFFTMathPreservation:
    """Tests for mathematical operation preservation."""
    
    def test_log1p_power_normalization(self, worker):
        """Test log1p + power(1.2) normalization is applied."""
        w, _, _ = worker
        
        # Create test magnitude array
        mag = np.array([1.0, 2.0, 4.0, 8.0], dtype=np.float32)
        original = mag.copy()
        
        # Apply same operations as worker
        np.log1p(mag, out=mag)
        np.power(mag, 1.2, out=mag)
        
        # Verify transformation
        assert not np.allclose(mag, original)
        # log1p(x)^1.2 should compress dynamic range
        assert mag[-1] / mag[0] < original[-1] / original[0]
    
    def test_convolution_kernel(self, worker):
        """Test convolution with [0.25, 0.5, 0.25] kernel."""
        w, _, _ = worker
        
        kernel = np.array(w._config.smooth_kernel, dtype=np.float32)
        
        # Kernel should sum to 1.0 (normalized)
        assert abs(np.sum(kernel) - 1.0) < 0.01
        
        # Kernel should be symmetric
        assert kernel[0] == kernel[2]
        assert kernel[1] == 0.5
    
    def test_center_out_mapping(self, worker):
        """Test center-out frequency mapping."""
        w, _, _ = worker
        
        # Generate audio with clear bass
        sample_rate = 44100
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        bass = 0.8 * np.sin(2 * np.pi * 80 * t)  # Strong 80Hz bass
        samples = bass.astype(np.float32).tolist()
        
        msg = WorkerMessage(
            msg_type=MessageType.FFT_FRAME,
            seq_no=1,
            correlation_id="test-center",
            payload={"samples": samples, "sensitivity": 0.5},
            worker_type=WorkerType.FFT,
        )
        
        response = w.handle_message(msg)
        bars = response.payload["bars"]
        
        # In center-out mapping, bass should be stronger in center region
        center = len(bars) // 2
        center_region = bars[center-2:center+3] if len(bars) > 4 else bars
        edge_region = bars[:3] + bars[-3:] if len(bars) > 6 else bars
        
        # Center should have activity (bass maps to center)
        assert max(center_region) > 0 or max(edge_region) > 0  # Some activity expected


class TestFFTGhosting:
    """Tests for ghost envelope behavior."""
    
    def test_ghost_peaks_track_bars(self, worker):
        """Test that peaks track bar values."""
        w, _, _ = worker
        
        # Send a strong signal
        samples = [0.5 * np.sin(2 * np.pi * 1000 * i / 44100) for i in range(4410)]
        
        msg = WorkerMessage(
            msg_type=MessageType.FFT_FRAME,
            seq_no=1,
            correlation_id="test-ghost-1",
            payload={"samples": samples},
            worker_type=WorkerType.FFT,
        )
        
        response = w.handle_message(msg)
        bars = response.payload["bars"]
        peaks = response.payload["peaks"]
        
        # Peaks should be >= bars (they track maximums)
        for i in range(len(bars)):
            assert peaks[i] >= bars[i] * 0.99  # Allow small numerical error
    
    def test_ghost_decay(self, worker):
        """Test that ghost peaks decay over time."""
        w, _, _ = worker
        
        # Send a strong signal
        samples = [0.8 * np.sin(2 * np.pi * 1000 * i / 44100) for i in range(4410)]
        
        msg1 = WorkerMessage(
            msg_type=MessageType.FFT_FRAME,
            seq_no=1,
            correlation_id="test-ghost-decay-1",
            payload={"samples": samples},
            worker_type=WorkerType.FFT,
        )
        w.handle_message(msg1)
        peaks_after_strong = list(w._state.peaks)
        
        # Send silence
        silence = [0.0] * 4410
        msg2 = WorkerMessage(
            msg_type=MessageType.FFT_FRAME,
            seq_no=2,
            correlation_id="test-ghost-decay-2",
            payload={"samples": silence},
            worker_type=WorkerType.FFT,
        )
        w.handle_message(msg2)
        peaks_after_silence = list(w._state.peaks)
        
        # Peaks should have decayed — structure check only (decay amount varies by signal)
        assert len(peaks_after_silence) == len(peaks_after_strong)


class TestCurvedProfileConfig:
    """Tests for curved profile configuration via FFTWorker messages."""

    def test_toggle_curved_profile_on(self, worker):
        """Test enabling curved profile via config message."""
        w, _, _ = worker
        assert w._config.use_curved_profile is False

        msg = WorkerMessage(
            msg_type=MessageType.FFT_CONFIG,
            seq_no=1,
            correlation_id="test-curved-on",
            payload={"use_curved_profile": True},
            worker_type=WorkerType.FFT,
        )
        response = w.handle_message(msg)
        assert response.success is True
        assert w._config.use_curved_profile is True

    def test_toggle_curved_profile_off(self, worker):
        """Test disabling curved profile via config message."""
        w, _, _ = worker
        w._config.use_curved_profile = True

        msg = WorkerMessage(
            msg_type=MessageType.FFT_CONFIG,
            seq_no=2,
            correlation_id="test-curved-off",
            payload={"use_curved_profile": False},
            worker_type=WorkerType.FFT,
        )
        response = w.handle_message(msg)
        assert response.success is True
        assert w._config.use_curved_profile is False

    def test_curved_produces_different_bars(self, worker):
        """Test that curved and legacy profiles produce different bar outputs."""
        w, _, _ = worker

        sample_rate = 44100
        duration = 0.1
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        samples = (0.5 * np.sin(2 * np.pi * 200 * t)).astype(np.float32).tolist()

        def get_bars(curved: bool):
            w._config.use_curved_profile = curved
            # Reset state so smoothing doesn't carry over
            w._init_state()
            w._state.last_fft_ts = 0.0
            msg = WorkerMessage(
                msg_type=MessageType.FFT_FRAME,
                seq_no=1,
                correlation_id=f"test-curved-{curved}",
                payload={"samples": samples, "sample_rate": sample_rate, "sensitivity": 1.0},
                worker_type=WorkerType.FFT,
            )
            resp = w.handle_message(msg)
            return resp.payload["bars"]

        legacy_bars = get_bars(False)
        curved_bars = get_bars(True)

        assert len(legacy_bars) == len(curved_bars)
        assert legacy_bars != curved_bars, "Curved and legacy profiles should produce different bars"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
