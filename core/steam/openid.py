"""Verified local Steam OpenID identity-linking support.

The Steam card family only needs OpenID to establish a SteamID64.  This
module deliberately does not handle passwords, cookies, or API keys.  The
short-lived loopback listener is started only after an explicit user action;
its blocking wait belongs on the shared ThreadManager IO pool.
"""
from __future__ import annotations

import re
import secrets
import threading
import time
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

from core.logging.logger import get_logger
from core.steam.credentials import safe_fingerprint

logger = get_logger(__name__)

STEAM_OPENID_ENDPOINT = "https://steamcommunity.com/openid/login"
STEAM_OPENID_NAMESPACE = "http://specs.openid.net/auth/2.0"
STEAM_OPENID_IDENTIFIER_SELECT = f"{STEAM_OPENID_NAMESPACE}/identifier_select"
DEFAULT_CALLBACK_TIMEOUT_SECONDS = 300.0
_CLAIMED_ID_RE = re.compile(r"^https?://steamcommunity\.com/openid/id/(\d{17})/?$")


class SteamOpenIdError(RuntimeError):
    """Raised when Steam OpenID identity linking cannot complete safely."""


@dataclass(frozen=True)
class SteamOpenIdResult:
    """Safe result of a Steam OpenID assertion or loopback session."""

    steam_id64: str | None
    message: str

    @property
    def success(self) -> bool:
        return self.steam_id64 is not None


def build_login_url(return_to: str) -> str:
    """Build Steam's OpenID setup URL for a fixed loopback callback URL."""
    parsed = urllib.parse.urlparse(return_to)
    if parsed.scheme != "http" or not parsed.hostname:
        raise SteamOpenIdError("Steam OpenID requires a valid local HTTP callback URL")
    realm = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, "/", "", "", ""))
    params = {
        "openid.ns": STEAM_OPENID_NAMESPACE,
        "openid.mode": "checkid_setup",
        "openid.return_to": return_to,
        "openid.realm": realm,
        "openid.identity": STEAM_OPENID_IDENTIFIER_SELECT,
        "openid.claimed_id": STEAM_OPENID_IDENTIFIER_SELECT,
    }
    return f"{STEAM_OPENID_ENDPOINT}?{urllib.parse.urlencode(params)}"


def extract_steam_id64(claimed_id: str | None) -> str | None:
    """Return the SteamID64 from Steam's documented claimed-ID format."""
    if not isinstance(claimed_id, str):
        return None
    match = _CLAIMED_ID_RE.fullmatch(claimed_id.strip())
    return match.group(1) if match else None


def validate_assertion(
    params: Mapping[str, str],
    *,
    expected_return_to: str,
    opener: Callable[[urllib.request.Request, float], Any] | None = None,
    timeout_seconds: float = 12.0,
) -> SteamOpenIdResult:
    """Verify a Steam OpenID callback before accepting the claimed SteamID64."""
    if params.get("openid.mode") != "id_res":
        return SteamOpenIdResult(None, "Steam did not return a successful identity assertion.")
    if params.get("openid.return_to") != expected_return_to:
        return SteamOpenIdResult(None, "Steam identity callback did not match this connection attempt.")
    if _normalize_endpoint(params.get("openid.op_endpoint")) != STEAM_OPENID_ENDPOINT:
        return SteamOpenIdResult(None, "Steam identity callback came from an unexpected endpoint.")
    claimed_id = params.get("openid.claimed_id")
    steam_id64 = extract_steam_id64(claimed_id)
    if steam_id64 is None or params.get("openid.identity") != claimed_id:
        return SteamOpenIdResult(None, "Steam identity callback did not contain a valid SteamID64.")
    signed = {part.strip() for part in params.get("openid.signed", "").split(",") if part.strip()}
    required_signed = {"op_endpoint", "claimed_id", "identity", "return_to"}
    if not required_signed.issubset(signed):
        return SteamOpenIdResult(None, "Steam identity callback omitted required signed fields.")

    verification_params = {
        key: value for key, value in params.items() if key.startswith("openid.")
    }
    verification_params["openid.mode"] = "check_authentication"
    request = urllib.request.Request(
        STEAM_OPENID_ENDPOINT,
        data=urllib.parse.urlencode(verification_params).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        response = (opener or _default_open)(request, timeout_seconds)
        payload = response.read(8_192).decode("utf-8", errors="replace")
    except Exception as exc:
        logger.warning("[STEAM] OpenID assertion verification failed: %s", exc)
        return SteamOpenIdResult(None, "Steam could not verify the identity assertion. Please try again.")

    fields = _parse_openid_response(payload)
    if fields.get("is_valid", "").strip().lower() != "true":
        return SteamOpenIdResult(None, "Steam did not validate the identity assertion. Please try again.")
    logger.info("[STEAM] Verified OpenID identity profile=%s", safe_fingerprint(steam_id64))
    return SteamOpenIdResult(steam_id64, "Steam identity linked. Add your Web API key to finish connecting.")


class SteamOpenIdLinkSession:
    """One explicit, short-lived Steam OpenID loopback connection attempt."""

    def __init__(
        self,
        *,
        callback_host: str = "127.0.0.1",
        timeout_seconds: float = DEFAULT_CALLBACK_TIMEOUT_SECONDS,
        opener: Callable[[urllib.request.Request, float], Any] | None = None,
    ) -> None:
        self._callback_host = callback_host
        self._timeout_seconds = max(1.0, float(timeout_seconds))
        self._opener = opener
        self._state = secrets.token_urlsafe(32)
        self._server: HTTPServer | None = None
        self._result: SteamOpenIdResult | None = None
        self._result_ready = threading.Event()
        self._result_lock = threading.Lock()
        self.callback_url: str | None = None
        self.login_url: str | None = None

    def start(self) -> str:
        """Bind the local listener and return the browser URL for this attempt."""
        if self._server is not None:
            raise SteamOpenIdError("Steam identity linking is already active")
        session = self

        class CallbackHandler(BaseHTTPRequestHandler):
            def log_message(self, _format: str, *_args: Any) -> None:
                return

            def do_GET(self) -> None:  # noqa: N802
                session._handle_callback(self)

        try:
            self._server = HTTPServer((self._callback_host, 0), CallbackHandler)
        except OSError as exc:
            raise SteamOpenIdError("Could not start the local Steam identity listener") from exc
        port = int(self._server.server_port)
        state = urllib.parse.quote(self._state, safe="")
        self.callback_url = f"http://{self._callback_host}:{port}/steam/openid?state={state}"
        self.login_url = build_login_url(self.callback_url)
        return self.login_url

    def wait_for_result(self) -> SteamOpenIdResult:
        """Serve the callback until it verifies or the explicit attempt expires."""
        server = self._server
        if server is None or self.callback_url is None:
            raise SteamOpenIdError("Steam identity listener has not been started")
        server.timeout = 0.5
        deadline = time.monotonic() + self._timeout_seconds
        try:
            while not self._result_ready.is_set() and time.monotonic() < deadline:
                server.handle_request()
        finally:
            self.close()
        if self._result is not None:
            return self._result
        return SteamOpenIdResult(None, "Steam identity connection timed out. Please try again.")

    def close(self) -> None:
        """Close the loopback listener; safe to call more than once."""
        server = self._server
        self._server = None
        if server is not None:
            try:
                server.server_close()
            except Exception:
                logger.debug("[STEAM] Suppressed Steam OpenID listener cleanup failure", exc_info=True)

    def _handle_callback(self, handler: BaseHTTPRequestHandler) -> None:
        parsed = urllib.parse.urlparse(handler.path)
        if parsed.path != "/steam/openid":
            handler.send_error(404)
            return
        query = {key: values[-1] for key, values in urllib.parse.parse_qs(parsed.query).items() if values}
        if not secrets.compare_digest(query.get("state", ""), self._state):
            self._write_response(handler, 400, "Steam connection failed", "This Steam identity callback does not match the active connection attempt.")
            return
        result = validate_assertion(
            query,
            expected_return_to=self.callback_url or "",
            opener=self._opener,
        )
        self._set_result(result)
        title = "SRPSS Steam identity linked" if result.success else "SRPSS Steam connection failed"
        self._write_response(handler, 200 if result.success else 400, title, result.message)

    def _set_result(self, result: SteamOpenIdResult) -> None:
        with self._result_lock:
            if self._result is None:
                self._result = result
                self._result_ready.set()

    @staticmethod
    def _write_response(handler: BaseHTTPRequestHandler, status: int, title: str, message: str) -> None:
        body = (
            "<html><body style='font-family:sans-serif;text-align:center;padding:48px;'>"
            f"<h1>{title}</h1><p>{message}</p><p>You can close this page and return to SRPSS.</p>"
            "</body></html>"
        ).encode("utf-8")
        handler.send_response(status)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)


def _default_open(request: urllib.request.Request, timeout_seconds: float) -> Any:
    return urllib.request.urlopen(request, timeout=timeout_seconds)


def _normalize_endpoint(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().rstrip("/")


def _parse_openid_response(payload: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in payload.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            fields[key.strip()] = value.strip()
    return fields
