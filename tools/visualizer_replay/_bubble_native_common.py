"""CPU-only bookkeeping for the bounded native Bubble diagnostic recipes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


SCOPE = "5.5-second variant-a/display synthetic owner fixture; 549 ordinary inputs"
FROZEN_FADE_SHA256 = "15c71ef5d5b40e3945379d6ec3a87101ac2870766481b231543e43e65fa04690"
ORIGINS = {
    "replay": ".artifacts/evidence/native_core/n5_1_bubble/20261116_current_rule_a_c53e3fe27/reproduce_owner_baseline_used.py",
    "fade": ".artifacts/evidence/native_core/n5_1_bubble/20261116_fade_composition_review/capture_fade_inputs.py",
    "components": ".artifacts/evidence/native_core/n5_1_bubble/20261116_fade_composition_review/capture_components_346_v2.py",
}
ORIGIN_SHA256 = {
    "replay": "132a9cd12d8e410da1b4848c38c4e5be6b2c52bbafb7e86be38d0c04ddbf9a87",
    "fade": FROZEN_FADE_SHA256,
    "components": "c51229632448025a048dc4e1f510146476164ac16f3888ce6f7ff82b4d26b32a",
}
LIVE_KEYS = (
    "handles", "items", "surfaces", "surface_resources", "mode_sources", "mode_resources",
    "scene_targets", "scene_target_bytes", "scene_target_textures", "mesh_buffers_arenas",
    "mesh_buffers_streams", "mesh_buffers_stream_bytes", "mode_textures", "mode_texture_bytes",
)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def wire(value):
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {key: wire(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [wire(item) for item in value]
    return value


def json_bytes(value):
    return json.dumps(wire(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def resolve_input(root, path):
    return (root / path).resolve()


def fresh_output(label):
    from tools import artifact_paths

    out = artifact_paths.evidence_dir("native_core", "n5_1_bubble", label)
    if out.exists():
        raise FileExistsError("choose a fresh --label; retained evidence will not be overwritten")
    return out


def provenance(recipe):
    folder = Path(__file__).parent
    names = ("bubble_native_diagnostics.py", "_bubble_native_common.py", f"_bubble_native_{recipe}.py")
    return {
        "recipe": recipe,
        "scope": SCOPE,
        "promoted_from": ORIGINS[recipe],
        "frozen_original_sha256": ORIGIN_SHA256[recipe],
        "source_sha256": {name: sha((folder / name).read_bytes()) for name in names},
        "limitations": "Diagnostic integrity and owner pixel parity are separate verdicts. This fixture does not replace BTF section 24 recorded-music logical parity, GPU cost, or live/operator validation.",
    }


def passive_helper_matches(receipt):
    """Keep the frozen receipt usable; new receipts must name this exact tool bundle."""
    helper = receipt.get("helper_sha256")
    if helper == FROZEN_FADE_SHA256:
        return receipt.get("quad_control_requested") is False
    current = provenance("fade")
    return (helper == current["source_sha256"]["_bubble_native_fade.py"]
            and receipt.get("diagnostic_tool") == current
            and receipt.get("quad_control_requested") is False)


def replay_helper_matches(receipt):
    """Recognize the frozen origin, or an integrity-passing exact promoted replay.

    The owner pixel verdict may fail; it is intentionally not an integrity check.
    Callers additionally verify settings/source/module/manifest and full frame counts.
    """
    helper = receipt.get("helper_sha256")
    if helper == ORIGIN_SHA256["replay"]:
        return True
    current = provenance("replay")
    checks = receipt.get("checks")
    return (helper == current["source_sha256"]["_bubble_native_replay.py"]
            and receipt.get("diagnostic_tool") == current
            and receipt.get("passive_guards_pass") is True
            and isinstance(checks, dict) and bool(checks)
            and all(value is True for value in checks.values()))
