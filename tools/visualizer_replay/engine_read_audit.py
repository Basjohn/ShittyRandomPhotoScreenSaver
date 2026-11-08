"""Native core P2: which beat-engine attributes the logical tick reads, per mode (the live-input surface).

    python tools/visualizer_replay/engine_read_audit.py
"""
import collections
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2]))
from PySide6.QtCore import QCoreApplication  # noqa: E402

app = QCoreApplication.instance() or QCoreApplication([])
import tools.expanded_visualizer_evidence as evidence  # noqa: E402
from core.settings.visualizer_mode_registry import iter_all_visualizer_mode_descriptors, get_visualizer_mode_descriptor  # noqa: E402
from widgets.spotify_visualizer.feature_replay import (  # noqa: E402
    PcmReanalysis, ReplayBeatEngine, configure_offline_controller, deterministic_clock,
)
from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController  # noqa: E402
from widgets.spotify_visualizer.tick_pipeline import logical_tick  # noqa: E402

reads = collections.defaultdict(set)
clip = evidence.shipped_clip(1.0)
for descriptor in iter_all_visualizer_mode_descriptors():
    mode = descriptor.mode_id
    with deterministic_clock() as clock:
        engine = ReplayBeatEngine(32)
        controller = VisualizerRuntimeController(runtime_generation=1, initial_mode=mode, engine_factory=lambda _c: engine)
        controller.engine = engine
        configure_offline_controller(controller, mode)
        reanalysis = PcmReanalysis() if get_visualizer_mode_descriptor(mode).raw_musical_signals else None
        original = type(engine).__getattribute__
        recording = [False]

        def spy(self, name, _original=original, _mode=mode):
            if recording[0] and not name.startswith("__"):
                reads[_mode].add(name)
            return _original(self, name)

        type(engine).__getattribute__ = spy
        try:
            for feature in clip.frames:
                clock[0] = feature.timestamp_us / 1e6
                controller.playing = feature.playing
                engine.set_playback_state(feature.playing)
                engine.accept_feature_frame(feature)
                if reanalysis is not None:
                    reanalysis.accept(engine, feature)
                recording[0] = True
                logical_tick(controller.logical_tick_state)
                recording[0] = False
        finally:
            type(engine).__getattribute__ = original

union = set().union(*reads.values())
for name in sorted(union):
    modes = sorted(m for m in reads if name in reads[m])
    print(f"{name:40s} {'ALL' if len(modes) == len(reads) else ','.join(modes)}")
