"""Activation-fenced ribbon state on the sole Visualizer logical capture clock."""
from __future__ import annotations
import math
from collections.abc import Mapping
from core.waveform_ribbon_dynamics import WaveformDynamics, HybridControls
from widgets.spotify_visualizer.frame_runtime_lifecycle import RetirableFrameRuntime, retirement_fenced
from widgets.spotify_visualizer.transient_bus import audible,musical_emphasis,passage_ramp
from widgets.spotify_visualizer.render_state import FrozenFieldsMemo
from widgets.spotify_visualizer.view_orbit import CameraAdmissionMemo
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
        # The capture's camera, admitted and frozen on the logical thread: an unchanged camera is neither re-solved
        # nor refrozen (the same results; only the repeated work disappears).
        self.camera_admission = CameraAdmissionMemo()
        self.parameter_fields = FrozenFieldsMemo()

    def reset(self):
        self._model = None
        self._identity = self._last_ts = None
        self._onset_serial = 0
        self._accent_mean = {}
        self._accent_time = None
        self._settings_values = self._configuration = None
        self._diagnostic_ts = -math.inf

    @retirement_fenced
    def rebase_clock(self):
        """Display power resumed after a park: the next step integrates no parked gap (state stays warm)."""
        self._last_ts = None
        self._accent_time = None

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
                body_bands, intensity, loudness, presence, dynamic_zoom=False, zoom_hold=False, view_span=None):
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
        # Absolute audibility only (operator, 7 Nov: "Adaptivity is the enemy"). The bus's presence (loudness over its
        # own 6 s running level) gated the body and every kick, so a quieter passage after a loud one drew less until
        # the running level caught up, then more: the same music, a different body. Its dips (below .5 on 4% of music
        # ticks of recorded continuous play) also reset the former learn rate. Near-silence still reads 0.
        weight = audible(loudness) if live else 0.
        hit = accent = 0.
        components=[0.,0.,0.]
        for onset in onsets:
            if onset.serial <= self._onset_serial:
                continue
            self._onset_serial = onset.serial
            if live and self._model.ready:
                support=audible(onset.loudness)   # near-silence buys nothing; a quieter passage is not gated
                magnitude=max(0.,float(onset.magnitude))
                if self._accent_time is not None and now-self._accent_time>1.5:
                    self._accent_mean.clear()
                mean=self._accent_mean.get(onset.kind,0.)
                contrast=max(0.,magnitude-mean)
                self._accent_mean[onset.kind]=mean+.18*(magnitude-mean)
                self._accent_time=now
                # The body's force follows the onset's own unclipped magnitude (already measured against the bus's
                # adaptive flux threshold), the fixed real-music scale and the shared passage ramp; silence and
                # serial identity remain separate permissions. It is never judged against this kind's running mean:
                # that second adaptation zeroed every routine kick of a sustained passage (5 Nov, continuous play:
                # 2/3 of kicks earned nothing and a steady beat faded to <1% of its first kick, so the start of a song
                # looked reactive and its middle muted). A bigger hit still lands bigger (magnitude is unclipped).
                reward=min(1.,magnitude/(1.+magnitude)*musical_emphasis(onset.loudness)
                           *passage_ramp(intensity,.35)*support)
                # Accent admission (sparks, strands) still asks whether this supported event stands out from the
                # routine. Reusing loudness as a confidence threshold killed every accent in ordinary quiet playback.
                accent=max(accent,contrast/(1.+magnitude)*support)
                if onset.kind not in _IMPULSES:raise ValueError('Unknown waveform onset kind: '+str(onset.kind))
                hit=max(hit,reward)
                components=[max(value,reward*share) for value,share in zip(components,_IMPULSES[onset.kind])]
        snapshot=self._model.advance(dt,bands=body_bands if live else (0.,0.,0.),
                                   intensity=intensity if live else 0.,presence=weight,hit=hit,
                                   hit_components=tuple(components),accent=accent,controls=controls,
                                   dynamic_zoom=dynamic_zoom,zoom_hold=zoom_hold,view_span=view_span)
        if is_viz_diagnostics_enabled() and now-self._diagnostic_ts>=1.:
            self._diagnostic_ts=now
            drives=dict(snapshot.drives)
            logger.info('[WAVEFORM_SIGNAL] playing=%s admitted=%s ready=%s identity=%s source=%s '
                'bands=%.3f/%.3f/%.3f intensity=%.3f loudness=%.3f presence=%.3f weight=%.3f '
                'hit=%.3f accent=%.3f height=%.3f bend=%.3f light=%.3f bursts=%s',
                playing,live,snapshot.ready,token,source_identity,*body_bands,intensity,loudness,presence,weight,
                hit,accent,drives.get('height',0.),drives.get('bend',0.),drives.get('light',0.),snapshot.particle_serial)
        return snapshot
