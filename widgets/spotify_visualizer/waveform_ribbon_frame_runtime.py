"""Activation-fenced ribbon state on the sole Visualizer logical capture clock."""
from __future__ import annotations
import math
from collections.abc import Mapping
from core.waveform_ribbon_dynamics import WaveformDynamics, HybridControls
from widgets.spotify_visualizer.frame_runtime_lifecycle import RetirableFrameRuntime, retirement_fenced
from widgets.spotify_visualizer.transient_bus import musical_weight


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
        self._settings_values = self._configuration = None

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
                body_bands, intensity, loudness, presence):
        now = float(now_ts)
        if not math.isfinite(now):
            raise ValueError('Waveform capture time must be finite')
        token = (tuple(identity),tuple(source_identity))
        if token != self._identity or (self._last_ts is not None and now < self._last_ts):
            self._last_ts = None
            self._onset_serial = 0
            self._identity = token
            self._model = WaveformDynamics(controls)
        dt = 0. if self._last_ts is None else min(.1,max(0.,now-self._last_ts))
        self._last_ts = now
        live = bool(playing) and tuple(source_identity)==tuple(identity)[1:] and all(v>=0 for v in identity)
        weight = musical_weight(loudness,presence) if live else 0.
        hit = 0.
        for onset in onsets:
            if onset.serial <= self._onset_serial:
                continue
            self._onset_serial = onset.serial
            if live and self._model.ready:
                hit = max(hit,float(onset.strength)*musical_weight(onset.loudness,onset.presence))
        return self._model.advance(dt,bands=body_bands if live else (0.,0.,0.),
                                   intensity=intensity if live else 0.,presence=weight,hit=hit,controls=controls)
