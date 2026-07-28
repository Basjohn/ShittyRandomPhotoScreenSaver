"""Generate deterministic, feature-only visualizer replay fixtures.

This command owns input fixtures only. It never creates or updates fidelity
output goldens.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path
import random
import shutil
import sys
from typing import Iterable


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from widgets.spotify_visualizer.feature_frame import (  # noqa: E402
    BandEnergy,
    EnergyLanes,
    FeatureClip,
    FeatureFrame,
    RAW_BAR_COUNT,
    SCHEMA_VERSION,
    SUPPORTED_MODES,
    TIMESTAMP_UNIT,
    TransientEnergy,
    WAVEFORM_COUNT,
    canonical_json,
    sha256_hex,
)


GENERATOR_VERSION = 1
BASELINE_COMMIT = "00edb57a3076b845cb8ee4b6cb7f36ea83411f0c"
NO_COPYRIGHT_STATEMENT = (
    "Feature-only synthetic data; no copyrighted audio is stored."
)

BandTriple = tuple[float, float, float]


def _overall(bands: BandTriple) -> float:
    return sum(bands) / 3.0


def _scaled_lane(bands: BandTriple, scale: float = 1.0) -> BandEnergy:
    scaled = tuple(min(1.0, value * scale) for value in bands)
    return BandEnergy(*scaled, _overall(scaled))


def _frame(
    timestamp_us: int,
    bands: BandTriple,
    *,
    rng: random.Random,
    mode: str = "spectrum",
    visible: bool = True,
    control_event: str = "none",
    onset_type: str = "",
    onset_strength: float = 0.0,
) -> FeatureFrame:
    continuous = _scaled_lane(bands)
    pre_agc = _scaled_lane(bands, 0.86)
    bubble = _scaled_lane((bands[0], bands[1] * 0.82, bands[2] * 0.68))

    onset_detected = bool(onset_type)
    transient_bands = tuple(
        value * onset_strength if onset_detected else 0.0 for value in bands
    )
    transient = TransientEnergy(
        *transient_bands,
        _overall(transient_bands),
        onset_detected,
        onset_type,
        onset_strength,
    )

    if continuous.overall == 0.0:
        raw_bars = (0.0,) * RAW_BAR_COUNT
        waveform = (0.0,) * WAVEFORM_COUNT
    else:
        raw_bars = tuple(
            max(
                0.0,
                min(
                    1.0,
                    (
                        bands[0] * (1.0 - index / RAW_BAR_COUNT)
                        if index < 10
                        else bands[1]
                        if index < 22
                        else bands[2]
                    )
                    + rng.uniform(-0.01, 0.01),
                ),
            )
            for index in range(RAW_BAR_COUNT)
        )
        waveform = tuple(
            max(
                -1.0,
                min(
                    1.0,
                    continuous.overall
                    * math.sin(index * math.tau * 3 / WAVEFORM_COUNT)
                    + rng.uniform(-0.01, 0.01),
                ),
            )
            for index in range(WAVEFORM_COUNT)
        )

    return FeatureFrame(
        timestamp_us=timestamp_us,
        energy=EnergyLanes(continuous, pre_agc, bubble, transient),
        raw_bars=raw_bars,
        waveform=waveform,
        playing=True,
        visible=visible,
        mode=mode,
        control_event=control_event,
    )


def _sequence(
    name: str,
    bands: Iterable[BandTriple],
    rng: random.Random,
    *,
    beat_indices: Iterable[int] = (),
) -> FeatureClip:
    beats = frozenset(beat_indices)
    return FeatureClip(
        name=name,
        frames=tuple(
            _frame(
                index * 20_000,
                band_values,
                rng=rng,
                onset_type="bass" if index in beats else "",
                onset_strength=1.0 if index in beats else 0.0,
            )
            for index, band_values in enumerate(bands)
        ),
    )


def _beat_clip(
    name: str,
    frame_count: int,
    frames_per_beat: int,
    rng: random.Random,
) -> FeatureClip:
    bands = [
        (0.9, 0.55, 0.3)
        if index % frames_per_beat == 0
        else (0.08, 0.06, 0.04)
        for index in range(frame_count)
    ]
    return _sequence(
        name,
        bands,
        rng,
        beat_indices=range(0, frame_count, frames_per_beat),
    )


def build_fixtures(seed: int) -> dict[str, FeatureClip]:
    rng = random.Random(seed)

    silence = [(0.0, 0.0, 0.0)] * 24
    isolated_impulse = (
        [(0.0, 0.0, 0.0)] * 8
        + [(1.0, 0.55, 0.2)]
        + [(0.0, 0.0, 0.0)] * 15
    )
    representative_phrase = [
        (
            0.18 + 0.62 * max(0.0, math.sin(index * 0.52)),
            0.12 + 0.44 * max(0.0, math.sin(index * 0.52 + 0.8)),
            0.08 + 0.31 * max(0.0, math.sin(index * 0.52 + 1.6)),
        )
        for index in range(72)
    ]

    fixtures = {
        "silence": _sequence("silence", silence, rng),
        "isolated_impulse": _sequence(
            "isolated_impulse",
            isolated_impulse,
            rng,
            beat_indices=(8,),
        ),
        "beats_60_bpm": _beat_clip("beats_60_bpm", 101, 50, rng),
        "beats_120_bpm": _beat_clip("beats_120_bpm", 101, 25, rng),
        "beats_180_bpm": _beat_clip("beats_180_bpm", 101, 17, rng),
        "sustained_bass": _sequence(
            "sustained_bass",
            [(0.95, 0.34, 0.12)] * 36,
            rng,
        ),
        "sustained_treble": _sequence(
            "sustained_treble",
            [(0.12, 0.34, 0.95)] * 36,
            rng,
        ),
        "broadband_noise": _sequence(
            "broadband_noise",
            [(rng.random(), rng.random(), rng.random()) for _ in range(48)],
            rng,
        ),
        "gradual_ramp": _sequence(
            "gradual_ramp",
            [
                (index / 47 * 0.9, index / 47 * 0.62, index / 47 * 0.4)
                for index in range(48)
            ],
            rng,
        ),
        "sudden_volume_step": _sequence(
            "sudden_volume_step",
            [(0.08, 0.05, 0.03)] * 20 + [(0.88, 0.66, 0.44)] * 28,
            rng,
        ),
        "representative_music_features": _sequence(
            "representative_music_features",
            representative_phrase,
            rng,
            beat_indices=range(0, 72, 12),
        ),
    }

    timestamp_us = 0
    irregular_frames = []
    for index, delta_us in enumerate((11_000, 37_000, 19_000, 52_000, 24_000) * 10):
        timestamp_us += delta_us
        irregular_frames.append(
            _frame(
                timestamp_us,
                (
                    0.2 + (index % 5) * 0.12,
                    0.15 + (index % 5) * 0.09,
                    0.1 + (index % 5) * 0.06,
                ),
                rng=rng,
            )
        )
    fixtures["irregular_input_cadence"] = FeatureClip(
        "irregular_input_cadence",
        tuple(irregular_frames),
    )

    fixtures["mode_visibility_switch"] = FeatureClip(
        "mode_visibility_switch",
        (
            _frame(10_000, (0.2, 0.12, 0.08), rng=rng),
            _frame(
                30_000,
                (0.7, 0.42, 0.25),
                rng=rng,
                mode="bubble",
                control_event="mode_switch",
            ),
            _frame(
                50_000,
                (0.7, 0.42, 0.25),
                rng=rng,
                mode="bubble",
                visible=False,
                control_event="visibility_toggle",
            ),
            _frame(
                70_000,
                (0.35, 0.25, 0.18),
                rng=rng,
                mode="spectrum",
                visible=True,
                control_event="mode_switch",
            ),
        ),
    )
    return fixtures


def generate_fixtures(
    output_dir: str | Path,
    *,
    seed: int = 7376,
    overwrite: bool = False,
) -> dict:
    destination = Path(output_dir)
    if destination.exists() and any(destination.iterdir()):
        if not overwrite:
            raise FileExistsError(
                f"refusing to overwrite non-empty fixture directory: {destination}"
            )
        shutil.rmtree(destination)

    destination.mkdir(parents=True, exist_ok=True)
    entries = []
    for name, clip in sorted(build_fixtures(seed).items()):
        data = clip.to_jsonl_bytes()
        path = destination / f"{name}.jsonl"
        path.write_bytes(data)
        entries.append(
            {
                "name": name,
                "file": path.name,
                "frames": len(clip.frames),
                "sha256": sha256_hex(data),
            }
        )

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generator": "generate_visualizer_replay_fixtures",
        "generator_version": GENERATOR_VERSION,
        "seed": seed,
        "timestamp_unit": TIMESTAMP_UNIT,
        "raw_bar_count": RAW_BAR_COUNT,
        "waveform_count": WAVEFORM_COUNT,
        "supported_modes": sorted(SUPPORTED_MODES),
        "baseline_commit": BASELINE_COMMIT,
        "no_copyright_statement": NO_COPYRIGHT_STATEMENT,
        "presentation_stall_schedule_ms": [100, 250, 500],
        "fixtures": entries,
    }
    (destination / "manifest.json").write_bytes(canonical_json(manifest) + b"\n")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output_dir",
        type=Path,
        help="directory for feature-only JSONL fixtures",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=7376,
        help="deterministic synthetic-data seed",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace an existing non-empty output directory",
    )
    arguments = parser.parse_args(argv)
    generate_fixtures(
        arguments.output_dir,
        seed=arguments.seed,
        overwrite=arguments.overwrite,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())