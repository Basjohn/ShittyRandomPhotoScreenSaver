"""Lab adapter over the existing recorded PCM/replay authority; no new capture, FFT or audio clock."""
from bisect import bisect_right
import hashlib
from pathlib import Path

import numpy as np

from tools.labs.waveform_ribbon_reactivity import Signal, clamp


class RecordedRibbonInput:
    def __init__(self, path: Path, *, start: float):
        from widgets.spotify_visualizer.feature_frame import load_jsonl
        from widgets.spotify_visualizer.beat_engine import _SpotifyBeatEngine
        from widgets.spotify_visualizer.transient_bus import musical_weight, musical_emphasis
        from tools.visualizer_replay.engine import ReplayBeatEngine
        from tools.visualizer_replay.pcm_reanalysis import PcmReanalysis
        from tools.visualizer_replay.driver import deterministic_clock,_configure
        from widgets.spotify_visualizer.runtime_controller import VisualizerRuntimeController
        from PySide6.QtGui import QGuiApplication
        from tools.visualizer_replay.live_audio import _new_samples
        self.path, self.start = Path(path).resolve(), float(start)
        self._app=QGuiApplication.instance() or QGuiApplication([])
        clip=load_jsonl(self.path)
        if any(frame.capture_history is None or frame.real is None for frame in clip.frames):
            raise ValueError('Recorded ribbon comparison requires native PCM and real-scale lanes on every frame')
        origin=clip.frames[0].timestamp_us
        self.times=[]; self.signals=[]; self.events=[]; source_events=[]
        onset_serial=0; last_accent=-float('inf'); raw_onsets=0
        reanalysis=PcmReanalysis()
        previous=None;pcm_serial=None;pcm_last_us=None;cumulative=0;first_count=0
        drift=[];anchors=[]
        with deterministic_clock() as clock:
            engine=ReplayBeatEngine(32)
            controller=VisualizerRuntimeController(runtime_generation=0,initial_mode='bubble',engine_factory=lambda _count:engine)
            controller.engine=engine
            _configure(controller,'bubble',settings={})
            try:
                for frame in clip.frames:
                    clock[0]=frame.timestamp_us/1e6
                    engine.accept_feature_frame(frame)
                    reanalysis.accept(engine,frame)
                    # Reuse the production floor-independent fixed-scale mapping, not clipped recorded live bands.
                    # This is an explicit lab reference feed; final Waveform scale calibration remains WR-07 work.
                    bands=_SpotifyBeatEngine.get_extruded_bubble_body_bands(engine)
                    level,presence=engine.get_musical_level()
                    weight=musical_weight(level,presence) if frame.playing else 0.
                    bass,mids,highs=(float(value)*weight for value in (bands.bass,bands.mid,bands.high))
                    intensity=engine.get_musical_intensity()*weight
                    native=np.frombuffer(frame.capture_history.pcm_f32le,dtype='<f4')[-480:]
                    rms=float(np.sqrt(np.mean(native*native)))
                    rms=rms/(rms+.08)
                    history=frame.capture_history
                    if history.capture_serial!=pcm_serial:
                        samples=np.frombuffer(history.pcm_f32le,dtype='<f4')
                        if previous is None:
                            cumulative=first_count=len(samples)
                        else:
                            expected=round((frame.timestamp_us-pcm_last_us)*history.sample_rate/1e6)
                            cumulative+=_new_samples(previous,samples,expected)
                        previous=samples;pcm_serial=history.capture_serial;pcm_last_us=frame.timestamp_us
                    elapsed=(cumulative-first_count)/history.sample_rate
                    original_elapsed=(frame.timestamp_us-origin)/1e6
                    drift.append(elapsed-original_elapsed)
                    if not anchors or original_elapsed-anchors[-1]['feature_time']>=2.:
                        anchors.append(dict(feature_time=original_elapsed,audio_time=elapsed,serial=history.capture_serial))
                    t=elapsed-self.start
                    self.times.append(t)
                    self.signals.append(Signal(bass,mids,highs,intensity,
                                               max(-1.,min(1.,highs-.5*(bass+mids))),rms))
                    for onset in engine.get_onset_events(onset_serial):
                        onset_serial=max(onset_serial,onset.serial); raw_onsets+=1
                        strength=clamp(onset.strength*musical_weight(onset.loudness,onset.presence)
                                       *min(1.,musical_emphasis(onset.loudness)))
                        # One common accent admission, before the four models: explicit strength + refractory
                        # bounds the 2.4s head-envelope population to seven, without truncating active packets.
                        if strength<.35 or t-last_accent<.35:
                            continue
                        last_accent=t
                        self.events.append((t,'bass' if onset.kind=='kick' else 'onset',strength))
                        source_events.append(dict(time=t,serial=onset.serial,kind=onset.kind,strength=strength))
            finally:
                controller.close_render_admission()
                engine.force_stop()
                engine.deleteLater()
        values=np.array([[s.bass,s.mids,s.highs,s.loudness,s.detail,s.rms] for s in self.signals])
        self.metadata=dict(path=str(self.path),sha256=hashlib.sha256(self.path.read_bytes()).hexdigest(),
                           start=self.start,duration=(clip.frames[-1].timestamp_us-origin)/1e6,
                           source='ReplayBeatEngine + PcmReanalysis + production floor-independent raw-band reference',
                           normalization='fixed production reference; no per-track normalization; passage from real loudness',
                           raw_onsets=raw_onsets,admitted_accents=source_events,
                           accent_admission=dict(minimum_strength=.35,refractory_seconds=.35),
                           p10_p50_p90=np.percentile(values,[10,50,90],axis=0).tolist(),
                           channels=['bass','mids','highs','loudness','signed_band_detail','captured_pcm_rms_envelope'],
                           audio_alignment='feature windows use cumulative captured PCM sample time; same existing _new_samples alignment as recorded_pcm',
                           original_feature_time_drift_seconds=dict(min=min(drift),max=max(drift),final=drift[-1]),
                           audio_alignment_anchors=anchors,analysis_notches='canonical Bubble source reference, no preset reads',
                           first_history_seconds=len(clip.frames[0].capture_history.pcm_f32le)/4/clip.frames[0].capture_history.sample_rate)

    def sample(self,t):
        if t<self.times[0] or t>self.times[-1]:
            return Signal()  # explicit pre-recording/end silence, never held or fabricated musical events
        return self.signals[bisect_right(self.times,t)-1]
