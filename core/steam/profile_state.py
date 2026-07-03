"""Versioned profile-level Steam policy state store."""
from __future__ import annotations

import json
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.logging.logger import get_logger

logger = get_logger(__name__)

STEAM_PROFILE_STATE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SteamProfilePolicyState:
    """Account-private card policy state shared across Steam card instances."""

    schema_version: int = STEAM_PROFILE_STATE_SCHEMA_VERSION
    rotations: Mapping[str, Any] = field(default_factory=dict)
    cooldowns: Mapping[str, float] = field(default_factory=dict)
    dismissals: Mapping[str, Any] = field(default_factory=dict)
    updated_at: float = 0.0

    def to_json_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "rotations": dict(self.rotations),
            "cooldowns": dict(self.cooldowns),
            "dismissals": dict(self.dismissals),
            "updated_at": float(self.updated_at or time.time()),
        }


def read_profile_state(path: Path) -> SteamProfilePolicyState:
    if not path.exists():
        return SteamProfilePolicyState()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ValueError("not an object")
        if raw.get("schema_version") != STEAM_PROFILE_STATE_SCHEMA_VERSION:
            raise ValueError("unsupported schema")
        rotations = raw.get("rotations") if isinstance(raw.get("rotations"), Mapping) else {}
        cooldowns_raw = raw.get("cooldowns") if isinstance(raw.get("cooldowns"), Mapping) else {}
        dismissals = raw.get("dismissals") if isinstance(raw.get("dismissals"), Mapping) else {}
        cooldowns: dict[str, float] = {}
        for key, value in cooldowns_raw.items():
            try:
                cooldowns[str(key)] = float(value)
            except Exception:
                continue
        return SteamProfilePolicyState(
            rotations=dict(rotations),
            cooldowns=cooldowns,
            dismissals=dict(dismissals),
            updated_at=_float_or_zero(raw.get("updated_at")),
        )
    except Exception as exc:
        corrupt_path = path.with_name(f"{path.name}.corrupt")
        try:
            if path.exists():
                path.replace(corrupt_path)
        except Exception:
            pass
        logger.warning("[STEAM][FALLBACK] Corrupt Steam profile state moved path=%s error=%s", path, exc)
        return SteamProfilePolicyState()


def write_profile_state(path: Path, state: SteamProfilePolicyState) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    try:
        tmp_path.write_text(
            json.dumps(state.to_json_payload(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        tmp_path.replace(path)
        return path
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        logger.exception("[STEAM] Failed to write profile policy state path=%s", path)
        raise


def _float_or_zero(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0
