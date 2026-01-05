"""
Worker implementations for process isolation.

Each worker runs in a separate process and communicates via queues.
Workers handle heavy computation without blocking the UI thread.
"""
from .base import BaseWorker
from .image_worker import ImageWorker, image_worker_main
from .rss_worker import RSSWorker, rss_worker_main
from .fft_worker import FFTWorker, FFTConfig, fft_worker_main
from .transition_worker import TransitionWorker, TransitionPrecomputeConfig, transition_worker_main

__all__ = [
    "BaseWorker",
    "ImageWorker",
    "image_worker_main",
    "RSSWorker",
    "rss_worker_main",
    "FFTWorker",
    "FFTConfig",
    "fft_worker_main",
    "TransitionWorker",
    "TransitionPrecomputeConfig",
    "transition_worker_main",
]
