"""Fixed analysis geometry and measured Waveform anchors; no state, learned level, FFT or capture owner."""
import math

WAVEFORM_RAW_REFERENCES=(5.4,3.1,1.1)
WAVEFORM_REFERENCE_FFT=256
WAVEFORM_BLOCK_EXPONENTS=(1.,.9,.6)
# Pooled median eased raw level was 3.359 over four native 60s captures, after 3s pre-roll (2 Nov).
# Rounded fixed anchor for the existing passage follower; never learn it from the current song.
WAVEFORM_USUAL_RAW_LEVEL=3.4


def raw_at_reference_fft(raw_value,block_scale,exponent):
    if block_scale==1. or raw_value<=0.:return raw_value
    return math.log1p(math.expm1(raw_value**(1./1.2))*block_scale**exponent)**1.2
