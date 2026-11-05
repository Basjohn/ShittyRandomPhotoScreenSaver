"""Activation-fenced ribbon state on the sole Visualizer logical capture clock."""
from __future__ import annotations
import math
from collections.abc import Mapping
from core.waveform_ribbon_dynamics import WaveformDynamics, HybridControls
from widgets.spotify_visualizer.frame_runtime_lifecycle import RetirableFrameRuntime, retirement_fenced
from widgets.spotify_visualizer.transient_bus import musical_weight,musical_emphasis,passage_ramp
from core.logging.logger import get_logger,is_viz_diagnostics_enabled

logger=get_logger(__name__)

_IMPULSES={'kick':(1.,.2,.15),'snare':(.15,1.,.35),'vocal_swell':(.4,.45,.9),'onset':(.6,.6,.6)}


def _configuration_token(value):
    if isinstance(value,Mapping):return {key:_configuration_token(item) for key,item in value.items()}
    if isinstance(value,list):return [_configuration_token(item) for item in value]
    if isinstance(value,tuple):return tuple(_configuration_token(item) for item in value)
    return value


class WaveformRibbonFrameRuntime(RetirableFrameRuntime):
    def __init__(self):
        super().__init__()
        self.reset()

    def reset(self):
        self._model = None
        self._identity = self._last_ts = None
        self._onset_serial = 0
        self._accent_mean = {}
        self._accent_time = None
        self._settings_values = self._configuration = None
        self._diagnostic_ts = -math.inf

    @retirement_fenced
    def configure(self,values):
        if self._settings_values != values:
            from widgets.spotify_visualizer.waveform_ribbon_parameters import CompiledWaveformSettings
            self._configuration = CompiledWaveformSettings(values)
            self._settings_values = _configuration_token(values)
        return self._configuration

    @property
    def onset_serial(self):
        return self._onset_serial

    @retirement_fenced
    def advance(self, *, onsets, now_ts, playing, identity, source_identity, controls: HybridControls,
                body_bands, intensity, loudness, presence, dynamic_zoom=False, zoom_hold=False):
        now = float(now_ts)
        if not math.isfinite(now):
            raise ValueError('Waveform capture time must be finite')
        token = tuple(identity)
        if self._model is None or token[0] != self._identity[0]:
            self._last_ts = None
            self._model = WaveformDynamics(controls)
        if token!=self._identity:
            self._onset_serial=0
            self._accent_mean={}
            self._accent_time=None
        self._identity=token
        dt = 0. if self._last_ts is None else min(.1,max(0.,now-self._last_ts))
        self._last_ts = now
        live = bool(playing) and tuple(source_identity)==tuple(identity)[1:] and all(v>=0 for v in identity)
        weight = musical_weight(loudness,presence) if live else 0.
        hit = accent = 0.
        components=[0.,0.,0.]
        for onset in onsets:
            if onset.serial <= self._onset_serial:
                continue
            self._onset_serial = onset.serial
            if live and self._model.ready:
                support=musical_weight(onset.loudness,onset.presence)
                magnitude=max(0.,float(onset.magnitude))
                if self._accent_time is not None and now-self._accent_time>1.5:
                    self._accent_mean.clear()
                mean=self._accent_mean.get(onset.kind,0.)
                contrast=max(0.,magnitude-mean)
                self._accent_mean[onset.kind]=mean+.18*(magnitude-mean)
                self._accent_time=now
                # Contrast survives the bus's clipped confidence. Reward follows the fixed real-music scale and
                # shared passage ramp after admission; silence and serial identity remain separate permissions.
                reward=min(1.,contrast/(1.+magnitude)*musical_emphasis(onset.loudness)
                           *passage_ramp(intensity,.35)*support)
                # Admission asks whether this supported event stands out; visual force also follows loudness.
                # Reusing the latter as a confidence threshold killed every accent in ordinary quiet playback.
                accent=max(accent,contrast/(1.+magnitude)*support)
                if onset.kind not in _IMPULSES:raise ValueError('Unknown waveform onset kind: '+str(onset.kind))
                hit=max(hit,reward)
                components=[max(value,reward*share) for value,share in zip(components,_IMPULSES[onset.kind])]
        snapshot=self._model.advance(dt,bands=body_bands if live else (0.,0.,0.),
                                   intensity=intensity if live else 0.,presence=weight,hit=hit,
                                   hit_components=tuple(components),accent=accent,controls=controls,
                                   dynamic_zoom=dynamic_zoom,zoom_hold=zoom_hold)
        if is_viz_diagnostics_enabled() and now-self._diagnostic_ts>=1.:
            self._diagnostic_ts=now
            drives=dict(snapshot.drives)
            logger.info('[WAVEFORM_SIGNAL] playing=%s admitted=%s ready=%s identity=%s source=%s '
                'bands=%.3f/%.3f/%.3f intensity=%.3f loudness=%.3f presence=%.3f weight=%.3f '
                'hit=%.3f accent=%.3f height=%.3f bend=%.3f light=%.3f bursts=%s',
                playing,live,snapshot.ready,token,source_identity,*body_bands,intensity,loudness,presence,weight,
                hit,accent,drives.get('height',0.),drives.get('bend',0.),drives.get('light',0.),snapshot.particle_serial)
        return snapshot
