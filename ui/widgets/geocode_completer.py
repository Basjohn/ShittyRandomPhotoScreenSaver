"""Live geocode autocomplete completer using Open-Meteo geocoding API.

Queries the Open-Meteo geocoding endpoint as the user types a city name,
with debouncing to avoid excessive API calls. Falls back to a static city
list when the network is unavailable.
"""
from __future__ import annotations

import threading
import requests
from typing import List

from PySide6.QtCore import Qt, QStringListModel, QObject, Signal
from PySide6.QtWidgets import QCompleter, QLineEdit

from core.logging.logger import get_logger
from core.threading.manager import ThreadManager

logger = get_logger(__name__)

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
_MIN_QUERY_LEN = 2
_DEBOUNCE_MS = 400
_MAX_RESULTS = 8

# Fallback static list for offline / error situations
_FALLBACK_CITIES = sorted([
    "London", "New York", "Tokyo", "Paris", "Berlin", "Sydney", "Toronto",
    "Los Angeles", "Chicago", "Houston", "Mumbai", "Delhi", "Shanghai",
    "Beijing", "Seoul", "Bangkok", "Singapore", "Hong Kong", "Dubai",
    "Istanbul", "Moscow", "Cairo", "Lagos", "Cape Town", "Buenos Aires",
    "São Paulo", "Mexico City", "Amsterdam", "Barcelona", "Vienna",
    "Munich", "Rome", "Madrid", "Warsaw", "Prague", "Stockholm",
    "Copenhagen", "Helsinki", "Oslo", "Dublin", "Brussels", "Lisbon",
    "Athens", "Budapest", "Bucharest", "Kyiv", "Seattle", "Denver",
    "Miami", "Atlanta", "Boston", "San Francisco", "Portland",
])


class _GeocodeWorkerSignals(QObject):
    """Signals emitted by the geocode background worker."""
    results_ready = Signal(list)


class GeocodeCompleter(QCompleter):
    """QCompleter that fetches city suggestions from Open-Meteo geocoding API.

    Attaches to a QLineEdit. When the user types ≥2 characters and pauses
    for 400ms, a background request fetches matching city names and updates
    the completion popup.
    """

    def __init__(self, line_edit: QLineEdit, parent: QObject | None = None) -> None:
        self._model = QStringListModel(_FALLBACK_CITIES)
        super().__init__(self._model, parent or line_edit)
        self.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterMode(Qt.MatchFlag.MatchContains)

        self._line_edit = line_edit
        self._pending_query: str = ""
        self._lock = threading.Lock()
        self._threads = ThreadManager()
        self._signals = _GeocodeWorkerSignals()
        self._signals.results_ready.connect(self._on_results)

        line_edit.textEdited.connect(self._on_text_edited)
        line_edit.setCompleter(self)

    # ------------------------------------------------------------------
    def _on_text_edited(self, text: str) -> None:
        """Called every keystroke. Debounces via single_shot then fires IO task."""
        text = text.strip()
        if len(text) < _MIN_QUERY_LEN:
            return

        with self._lock:
            self._pending_query = text

        # Debounce: schedule a UI-thread callback after delay.
        # If the user types again before it fires, the pending_query
        # will have changed and the stale callback is a no-op.
        ThreadManager.single_shot(_DEBOUNCE_MS, self._fire_fetch, text)

    # ------------------------------------------------------------------
    def _fire_fetch(self, query: str) -> None:
        """Called on UI thread after debounce. Submits IO task if query is still current."""
        with self._lock:
            if query != self._pending_query:
                return
        self._threads.submit_io_task(self._do_fetch, query)

    # ------------------------------------------------------------------
    def _do_fetch(self, query: str) -> None:
        """Runs on IO thread. Fetches geocode results and emits signal."""
        with self._lock:
            if query != self._pending_query:
                return
        results = self._fetch_cities(query)
        if results:
            self._signals.results_ready.emit(results)

    # ------------------------------------------------------------------
    @staticmethod
    def _fetch_cities(query: str) -> List[str]:
        """Query Open-Meteo geocoding API and return city display strings."""
        try:
            resp = requests.get(
                GEOCODING_URL,
                params={"name": query, "count": _MAX_RESULTS, "language": "en", "format": "json"},
                timeout=3,
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if not results:
                return []

            cities: List[str] = []
            seen: set = set()
            for r in results:
                name = r.get("name", "")
                country = r.get("country", "")
                display = f"{name}, {country}" if country else name
                key = display.lower()
                if key not in seen:
                    seen.add(key)
                    cities.append(display)
            return cities
        except Exception as exc:
            logger.debug("[GEOCODE_COMPLETER] Fetch failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    def _on_results(self, cities: List[str]) -> None:
        """Slot called on UI thread when geocode results arrive."""
        if not cities:
            return
        self._model.setStringList(cities)
        # Re-trigger completion popup with new data
        self.complete()
