# Visualizer replay reactivity floor

The current headless harness is `tools/visualizer_replay/`; its permanent regression
suite is `tests/test_visualizer_replay.py`. Live sequencing belongs to `Current_Plan.md`.

## Boundary

Immutable post-DSP fixtures enter the real BeatEngine analysis-frame admission seam,
then the current controller-owned logical tick, mode runtime, immutable logical frame,
latest-state mailbox and Quick presentation synchronization. No window, renderer,
audio capture, production thread or runtime timer is started. This measures authored
logical/snapshot response, not pixels, live FFT quality or physical latency.

There are 66 v1 case files plus one manifest, spanning 13 fixtures and five established
modes, including a separate mode/visibility control case. Fixture bytes are verified
against the existing immutable fixture manifest before replay. Existing v1 frame/digest
files remain historical reference; they are not exact-match acceptance targets.

## Minimum bar

`tests/goldens/visualizer_replay/reactivity_floor.json` records current authored preset-zero
measurements and fixed response floors at 50% of measurable healthy reference values.
The 32 recovered quantitative metrics retain their definitions. Additional mode-output
flux uses actual immutable bars/peaks, line reaction parameters/waveform, Bubble positions,
and DevCurve curves. Input beat counts alone are not proof of downstream reactivity.

Silence checks audio lanes only: Bubble/DevCurve authored idle motion is allowed.
A steady fixture may settle immediately, so only measured positive responses receive
floors; every pulsed fixture must have measurable mode-output flux. DevCurve travel
has a separate response and +/-10% cruise-envelope bar. Bass/treble fixtures preserve
lane ordering. No upper response ceiling or pixel equality is imposed.

Sparse presentation must leave the complete authored logical series unchanged. Negative
controls zero the engine consumer and freeze the real DevCurve runtime, proving the
respective output floors fail. No production module imports the harness.

## Commands

```powershell
python -m pytest tests/test_visualizer_replay.py -q
python -m tools.visualizer_replay
python -m tools.visualizer_replay --report new-response-report.html
python -m tools.visualizer_replay --candidate new-reference-candidate.json
```

The optional HTML report is diagnostic and off by default. Candidate generation and
report writing refuse existing paths. Normal verification only reads fixed thresholds;
never update a floor merely to bless an unexplained response loss. A candidate needs
review against current healthy behavior before replacing the checked-in reference.
