from __future__ import annotations

import numpy as np

from widgets.spotify_visualizer.audio_worker import _prepare_mono_audio_frame


def test_multichannel_downmix_preserves_strongest_two_channel_policy():
    frames = 128
    samples = np.zeros((frames, 6), dtype=np.float32)
    samples[:, 0] = np.linspace(-0.1, 0.1, frames, dtype=np.float32)
    samples[:, 2] = np.linspace(-0.8, 0.8, frames, dtype=np.float32)
    samples[:, 4] = np.linspace(0.6, -0.6, frames, dtype=np.float32)
    samples[:, 5] = 0.05

    energy = np.sum(samples * samples, axis=0)
    top_idx = np.argsort(energy)[-2:]
    expected = np.mean(samples[:, top_idx], axis=1, dtype=np.float32)

    actual = _prepare_mono_audio_frame(np, samples)

    np.testing.assert_allclose(actual, expected, rtol=1e-6, atol=1e-7)
    assert actual.dtype == np.float32
    assert actual.flags.owndata


def test_downmix_publishes_owned_samples_and_keeps_trailing_window():
    samples = np.arange(5000, dtype=np.float32).reshape(2500, 2)
    expected = np.mean(samples, axis=1, dtype=np.float32)[-2048:].copy()

    actual = _prepare_mono_audio_frame(np, samples)
    samples.fill(-1.0)

    np.testing.assert_allclose(actual, expected, rtol=0.0, atol=0.0)
    assert actual.shape == (2048,)
    assert actual.flags.owndata


def test_int16_mono_input_is_normalized_and_detached():
    samples = np.array([-32768, -16384, 0, 16384, 32767], dtype=np.int16)

    actual = _prepare_mono_audio_frame(np, samples)
    samples.fill(0)

    np.testing.assert_allclose(
        actual,
        np.array([-1.0, -0.5, 0.0, 0.5, 32767 / 32768], dtype=np.float32),
        rtol=0.0,
        atol=1e-7,
    )
    assert actual.flags.owndata
