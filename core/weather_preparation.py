"""Qt-free Weather cache loading, result preparation, and persistence.

The Weather widget owns visible Qt state.  This module owns detached cache and
serialization work that is safe to run on the shared I/O pool.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
from typing import Any, Mapping

from core.logging.logger import get_logger
from core.logging.tags import LOG_FAMILY_CACHE
from core.settings.storage_paths import (
    get_weather_cache_file,
    get_weather_widget_cache_file,
)


logger = get_logger(__name__, families=LOG_FAMILY_CACHE)

_CACHE_LOCKS_GUARD = threading.Lock()
_CACHE_LOCKS: dict[str, threading.RLock] = {}


def normalize_weather_location_key(value: Any) -> str:
    """Return the persisted-cache identity used by the Weather widget."""

    return " ".join(str(value or "").split()).casefold()


def _normalized_path_key(path: Path) -> str:
    return os.path.normcase(os.path.abspath(str(path)))


def _cache_lock(path: Path) -> threading.RLock:
    key = _normalized_path_key(path)
    with _CACHE_LOCKS_GUARD:
        lock = _CACHE_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _CACHE_LOCKS[key] = lock
        return lock


def resolve_weather_widget_cache_path(path_override: Path | None = None) -> Path:
    """Resolve the widget cache path on the calling (I/O-owner) thread."""

    if path_override is not None:
        return Path(path_override)
    return get_weather_widget_cache_file()


def resolve_weather_provider_cache_path(path_override: Path | None = None) -> Path:
    """Resolve the provider cache path on the calling (I/O-owner) thread."""

    if path_override is not None:
        return Path(path_override)
    return get_weather_cache_file()


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _age_seconds(timestamp: datetime) -> float:
    try:
        now = datetime.now(timestamp.tzinfo) if timestamp.tzinfo is not None else datetime.now()
        return max(0.0, (now - timestamp).total_seconds())
    except Exception:
        return -1.0


@dataclass(frozen=True)
class PreparedWeatherSample:
    """Immutable ordinary-Python Weather sample shared across threads."""

    location: str
    temperature: float | None
    condition: str | None
    humidity: float | None
    precipitation_probability: float | None
    windspeed: float | None
    forecast: str | None
    is_day: int
    weather_code: int | None
    observed_at: datetime

    def to_display_dict(self) -> dict[str, Any]:
        """Create the mutable dict owned by the GUI after publication."""

        return {
            "temperature": self.temperature,
            "condition": self.condition,
            "location": self.location,
            "humidity": self.humidity,
            "precipitation_probability": self.precipitation_probability,
            "windspeed": self.windspeed,
            "forecast": self.forecast,
            "is_day": self.is_day,
            "weather_code": self.weather_code,
        }

    def to_cache_payload(self) -> dict[str, Any] | None:
        """Return the stable on-disk widget schema, or None if incomplete."""

        if self.temperature is None or self.condition is None:
            return None
        payload: dict[str, Any] = {
            "location": self.location,
            "temperature": float(self.temperature),
            "condition": str(self.condition),
            "timestamp": self.observed_at.isoformat(),
        }
        if self.humidity is not None:
            payload["humidity"] = float(self.humidity)
        if self.precipitation_probability is not None:
            payload["precipitation_probability"] = float(self.precipitation_probability)
        if self.windspeed is not None:
            payload["windspeed"] = float(self.windspeed)
        if self.forecast:
            payload["forecast"] = str(self.forecast)
        payload["is_day"] = int(self.is_day)
        if self.weather_code is not None:
            payload["weather_code"] = int(self.weather_code)
        return payload


@dataclass(frozen=True)
class PreparedWeatherStartup:
    """One detached startup-cache decision returned by the I/O worker."""

    sample: PreparedWeatherSample | None
    cache_time: datetime | None
    source: str | None
    stale: bool = False


@dataclass(frozen=True)
class PreparedWeatherFetch:
    """Provider result plus the detached durability decision for GUI acceptance."""

    sample: PreparedWeatherSample
    persist_provider: bool


def prepare_weather_sample(
    raw: Mapping[str, Any],
    *,
    fallback_location: str,
    observed_at: datetime | None = None,
) -> PreparedWeatherSample:
    """Normalize provider/widget dictionaries into one immutable sample."""

    data = dict(raw)
    main = data.get("main") if isinstance(data.get("main"), Mapping) else {}
    wind = data.get("wind") if isinstance(data.get("wind"), Mapping) else {}

    temperature = data.get("temperature")
    if temperature is None:
        temperature = main.get("temp")

    condition = data.get("condition")
    if condition is None:
        weather_rows = data.get("weather")
        if isinstance(weather_rows, (list, tuple)) and weather_rows:
            first = weather_rows[0]
            if isinstance(first, Mapping):
                condition = first.get("main") or first.get("description")

    humidity = data.get("humidity")
    if humidity is None:
        humidity = main.get("humidity")
    precipitation = data.get("precipitation_probability")
    windspeed = data.get("windspeed")
    if windspeed is None:
        windspeed = wind.get("speed")

    location = str(
        data.get("location") or data.get("name") or fallback_location or ""
    ).strip()
    forecast_value = data.get("forecast")
    condition_value = str(condition).strip() if condition is not None else None
    if condition_value == "":
        condition_value = None

    is_day = _optional_int(data.get("is_day"))
    return PreparedWeatherSample(
        location=location,
        temperature=_optional_float(temperature),
        condition=condition_value,
        humidity=_optional_float(humidity),
        precipitation_probability=_optional_float(precipitation),
        windspeed=_optional_float(windspeed),
        forecast=str(forecast_value) if forecast_value else None,
        is_day=1 if is_day is None else is_day,
        weather_code=_optional_int(data.get("weather_code")),
        observed_at=observed_at or datetime.now(),
    )


def _read_json_mapping(path: Path) -> Mapping[str, Any] | None:
    try:
        with _cache_lock(path):
            if not path.exists():
                return None
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        return payload if isinstance(payload, Mapping) else None
    except Exception:
        logger.warning("[CACHE][WEATHER] Failed to load cache: %s", path, exc_info=True)
        return None


def read_weather_provider_cache(
    path_override: Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Load the provider cache under the shared per-path transaction lock."""

    path = resolve_weather_provider_cache_path(path_override)
    payload = _read_json_mapping(path)
    if not payload:
        return {}
    return {
        str(city): dict(sample)
        for city, sample in payload.items()
        if isinstance(sample, Mapping)
    }


def _migrate_legacy_widget_cache(legacy_path: Path, widget_path: Path) -> bool:
    """Atomically migrate a legacy cache without racing current persistence."""

    temp_path: Path | None = None
    try:
        with _cache_lock(widget_path):
            if not legacy_path.exists() or widget_path.exists():
                return False
            widget_path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=widget_path.parent,
                prefix=f".{widget_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                with legacy_path.open("rb") as source:
                    shutil.copyfileobj(source, handle)
                handle.flush()
            os.replace(temp_path, widget_path)
            temp_path = None
        logger.info("[STORAGE] Migrated file: %s -> %s", legacy_path, widget_path)
        return True
    except Exception:
        logger.warning(
            "[CACHE][WEATHER] Legacy widget-cache migration failed %s -> %s",
            legacy_path,
            widget_path,
            exc_info=True,
        )
        return False
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                logger.debug(
                    "[CACHE][WEATHER] Failed to remove migration temp file: %s",
                    temp_path,
                    exc_info=True,
                )


def _widget_cache_sample(
    payload: Mapping[str, Any] | None,
    *,
    location: str,
) -> PreparedWeatherSample | None:
    if not payload:
        return None
    cached_location = payload.get("location")
    timestamp = payload.get("timestamp")
    if not cached_location or not timestamp:
        logger.warning(
            "[CACHE][WEATHER] Ignoring persisted widget cache with missing location/timestamp"
        )
        return None
    try:
        observed_at = datetime.fromisoformat(str(timestamp))
    except Exception as exc:
        logger.warning(
            "[CACHE][WEATHER] Ignoring persisted widget cache with invalid timestamp: %s",
            exc,
        )
        return None
    if normalize_weather_location_key(cached_location) != normalize_weather_location_key(location):
        logger.info(
            "[CACHE][WEATHER] Ignoring persisted widget cache for location=%s while active_location=%s",
            cached_location,
            location,
        )
        return None
    sample = prepare_weather_sample(
        payload,
        fallback_location=location,
        observed_at=observed_at,
    )
    if sample.temperature is None or sample.condition is None:
        logger.warning(
            "[CACHE][WEATHER] Ignoring persisted widget cache with missing temperature/condition"
        )
        return None
    return sample


def _provider_cache_sample(
    payload: Mapping[str, Any] | None,
    *,
    location: str,
) -> tuple[PreparedWeatherSample | None, bool]:
    if not payload:
        return None, False
    cached = payload.get(location)
    if not isinstance(cached, Mapping):
        return None, False
    cached_at_raw = cached.get("_cached_at")
    try:
        cache_time = (
            datetime.fromtimestamp(float(cached_at_raw))
            if cached_at_raw
            else datetime.now()
        )
    except Exception:
        cache_time = datetime.now()
    stale = bool(cached.get("_stale", False))
    if cached_at_raw:
        try:
            stale = stale or (datetime.now() - cache_time).total_seconds() >= 1800.0
        except Exception:
            pass
    visible = {key: value for key, value in cached.items() if not str(key).startswith("_")}
    sample = prepare_weather_sample(
        visible,
        fallback_location=location,
        observed_at=cache_time,
    )
    if sample.temperature is None or sample.condition is None:
        return None, stale
    return sample, stale


def load_weather_startup_snapshot(
    location: str,
    *,
    widget_cache_path_override: Path | None = None,
    provider_cache_path_override: Path | None = None,
    legacy_widget_cache_path: Path | None = None,
) -> PreparedWeatherStartup:
    """Load widget-first/provider-fallback startup state on an I/O thread."""

    active_location = str(location or "").strip()
    if not active_location:
        return PreparedWeatherStartup(None, None, None)

    widget_path = resolve_weather_widget_cache_path(widget_cache_path_override)
    if legacy_widget_cache_path is not None:
        _migrate_legacy_widget_cache(Path(legacy_widget_cache_path), widget_path)
    widget_sample = _widget_cache_sample(
        _read_json_mapping(widget_path),
        location=active_location,
    )
    if widget_sample is not None:
        logger.info(
            "[CACHE][WEATHER] Loaded persisted widget cache for location=%s age_s=%.1f",
            widget_sample.location,
            _age_seconds(widget_sample.observed_at),
        )
        return PreparedWeatherStartup(
            sample=widget_sample,
            cache_time=widget_sample.observed_at,
            source="widget",
        )

    provider_path = resolve_weather_provider_cache_path(provider_cache_path_override)
    provider_sample, stale = _provider_cache_sample(
        _read_json_mapping(provider_path),
        location=active_location,
    )
    if provider_sample is not None:
        logger.info(
            "[CACHE][WEATHER] Loaded provider %sstartup cache for location=%s age_s=%.1f",
            "stale " if stale else "",
            active_location,
            _age_seconds(provider_sample.observed_at),
        )
        return PreparedWeatherStartup(
            sample=provider_sample,
            cache_time=provider_sample.observed_at,
            source="provider",
            stale=stale,
        )
    return PreparedWeatherStartup(None, None, None)


def write_weather_widget_cache(
    sample: PreparedWeatherSample,
    *,
    cache_path_override: Path | None = None,
) -> bool:
    """Atomically persist one accepted sample, rejecting older late writers."""

    payload = sample.to_cache_payload()
    if payload is None:
        return False
    path = resolve_weather_widget_cache_path(cache_path_override)
    temp_path: Path | None = None
    try:
        with _cache_lock(path):
            existing = _read_json_mapping(path)
            if existing:
                existing_timestamp = existing.get("timestamp")
                try:
                    if existing_timestamp and datetime.fromisoformat(str(existing_timestamp)) > sample.observed_at:
                        logger.info(
                            "[CACHE][WEATHER] Skipped older widget cache write for location=%s",
                            sample.location,
                        )
                        return False
                except Exception:
                    pass

            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                json.dump(payload, handle)
                handle.flush()
            os.replace(temp_path, path)
            temp_path = None
        logger.info(
            "[CACHE][WEATHER] Persisted widget cache for location=%s",
            sample.location,
        )
        return True
    except Exception:
        logger.warning("[CACHE][WEATHER] Failed to persist widget cache", exc_info=True)
        return False
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                logger.debug(
                    "[CACHE][WEATHER] Failed to remove cache temp file: %s",
                    temp_path,
                    exc_info=True,
                )


def write_weather_provider_cache(
    sample: PreparedWeatherSample,
    *,
    cache_path_override: Path | None = None,
) -> bool:
    """Atomically merge one accepted network sample into the provider cache."""

    if not sample.location:
        return False
    path = resolve_weather_provider_cache_path(cache_path_override)
    temp_path: Path | None = None
    try:
        with _cache_lock(path):
            existing = _read_json_mapping(path)
            merged: dict[str, Any] = dict(existing or {})
            prior = merged.get(sample.location)
            if isinstance(prior, Mapping):
                try:
                    prior_timestamp = float(prior.get("_cached_at") or 0.0)
                    if prior_timestamp > sample.observed_at.timestamp():
                        logger.info(
                            "[CACHE][WEATHER] Skipped older provider cache write for location=%s",
                            sample.location,
                        )
                        return False
                except Exception:
                    pass

            record = sample.to_display_dict()
            record["_cached_at"] = sample.observed_at.timestamp()
            merged[sample.location] = record
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                json.dump(merged, handle, indent=2)
                handle.flush()
            os.replace(temp_path, path)
            temp_path = None
        logger.debug(
            "[CACHE][WEATHER] Persisted provider cache for location=%s entries=%d",
            sample.location,
            len(merged),
        )
        return True
    except Exception:
        logger.warning("[CACHE][WEATHER] Failed to persist provider cache", exc_info=True)
        return False
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                logger.debug(
                    "[CACHE][WEATHER] Failed to remove provider cache temp file: %s",
                    temp_path,
                    exc_info=True,
                )


__all__ = [
    "PreparedWeatherSample",
    "PreparedWeatherFetch",
    "PreparedWeatherStartup",
    "load_weather_startup_snapshot",
    "normalize_weather_location_key",
    "prepare_weather_sample",
    "read_weather_provider_cache",
    "resolve_weather_provider_cache_path",
    "resolve_weather_widget_cache_path",
    "write_weather_widget_cache",
    "write_weather_provider_cache",
]
