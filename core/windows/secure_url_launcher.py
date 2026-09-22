"""Central browser launcher with an explicit secure-desktop fallback.

Normal interactive surfaces use Qt's native desktop URL route.  The existing
ProgramData helper queue is reserved for a genuine secure-desktop fallback,
where the browser cannot be opened by the current process.
"""
from __future__ import annotations

import os
import webbrowser

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from core.build_profile import is_diagnostic_build
from core.logging.logger import get_logger
from core.steam.links import SteamLinkTarget
from core.windows import reddit_helper_bridge
from core.windows import reddit_helper_runtime
from core.mc import is_mc_build

logger = get_logger(__name__)


def open_steam_target(
    target: SteamLinkTarget,
    *,
    source: str = "steam",
) -> bool:
    """Prefer a Steam-client deep link interactively, otherwise open HTTPS.

    The normal screensaver cannot reliably launch into the interactive user's
    Steam process, so it hands the validated HTTPS fallback to the existing
    helper queue. MC/diagnostic runs try Steam first and fall back to the
    browser when Qt rejects the protocol request.
    """

    if not isinstance(target, SteamLinkTarget):
        return False
    interactive = bool(is_mc_build() or is_diagnostic_build())
    if interactive:
        try:
            if QDesktopServices.openUrl(QUrl(target.steam_url)):
                logger.info(
                    "[URL-LAUNCH] Opened Steam target directly source=%s kind=%s",
                    source,
                    target.kind,
                )
                return True
            logger.warning(
                "[URL-LAUNCH] Steam target was rejected; using browser source=%s kind=%s",
                source,
                target.kind,
            )
        except Exception as exc:
            logger.warning(
                "[URL-LAUNCH] Steam target failed; using browser source=%s kind=%s error_type=%s",
                source,
                target.kind,
                type(exc).__name__,
            )
    return open_url(
        target.browser_url,
        fallback=interactive,
        prefer_direct=interactive,
        source=source,
    )


def open_url(
    url: str,
    *,
    fallback: bool = True,
    prefer_direct: bool = False,
    source: str = "gmail",
) -> bool:
    """Open *url* directly when appropriate, otherwise use secure handoff.

    Args:
        url: The URL to open.
        fallback: If True, try ``webbrowser.open()`` after other routes fail.
        prefer_direct: Request MC-style native URL launch before any queue route.
        source: Safe route label for helper diagnostics.

    Returns:
        True only after a direct user-desktop open or a queued action with an
        admitted interactive helper. A saver click fails closed when handoff
        is unavailable; it must never launch Firefox from the saver desktop.
    """
    if not url:
        return False

    diagnostic_build = is_diagnostic_build()
    mc_build = is_mc_build()
    # Winlogon/Services are not the user's browser desktop. A caller's
    # prefer_direct or fallback flag must never override that boundary.
    secure_desktop = (
        not (mc_build or diagnostic_build)
        and os.getenv("SESSIONNAME", "").strip().casefold() in {"winlogon", "services"}
    )
    direct_requested = bool(not secure_desktop and (prefer_direct or mc_build or diagnostic_build))
    if direct_requested:
        try:
            if QDesktopServices.openUrl(QUrl(url)):
                logger.info("[URL-LAUNCH] Opened directly source=%s", source)
                return True
            logger.warning("[URL-LAUNCH] Native direct URL launch was rejected source=%s", source)
        except Exception as exc:
            logger.warning(
                "[URL-LAUNCH] Native direct URL launch failed source=%s error_type=%s",
                source,
                type(exc).__name__,
            )

    # MC and the separate diagnostic product are always interactive: a failed
    # direct route must not enqueue work for the SCR helper, which neither
    # product owns or provisions.
    secure_handoff = not (mc_build or diagnostic_build)
    if secure_handoff:
        if reddit_helper_bridge.is_bridge_available():
            # Explicitly mark saver-origin queue entries; SESSIONNAME can be
            # "Console" even when the process runs on Winlogon's desktop.
            # The helper must wait for this process to disappear before opening
            # Firefox, not merely for Explorer to exist on the user desktop.
            queue_source = f"scr_click_{source}" if not prefer_direct else source
            ok = reddit_helper_bridge.enqueue_url(url, source=queue_source)
            if ok:
                try:
                    # R-02 invariant: the durable queue admission owns success.
                    # Request the existing interactive-only scheduled task, but
                    # never let helper heartbeat/readiness leak back into saver
                    # teardown. The helper waits for this saver/session boundary
                    # before opening the browser on the user's desktop.
                    woke = bool(reddit_helper_runtime.ensure_helper_runtime(
                        source=f"scr_url_handoff_{source}",
                        owner_pid=None,
                        idle_exit_seconds=60,
                        allow_system=True,
                    ))
                    if not woke:
                        logger.warning(
                            "[URL-LAUNCH] URL queued; scheduled helper wake was not confirmed "
                            "source=%s (handoff remains durable)", source,
                        )
                except Exception:
                    logger.warning(
                        "[URL-LAUNCH] URL queued; scheduled helper wake raised source=%s "
                        "(handoff remains durable)",
                        source,
                        exc_info=True,
                    )
                logger.info("[URL-LAUNCH] Queued secure-desktop URL handoff source=%s", source)
                return True
            else:
                logger.error("[URL-LAUNCH] Secure URL handoff enqueue failed source=%s", source)
        else:
            logger.error("[URL-LAUNCH] Secure URL handoff queue unavailable source=%s", source)
        if not (prefer_direct and not secure_desktop and fallback):
            # No webbrowser/QDesktopServices fallback on the secure desktop,
            # even if an older caller left fallback=True by default.
            return False

    if not fallback or secure_desktop:
        logger.error("[URL-LAUNCH] No safe URL route and fallback disabled source=%s", source)
        return False

    try:
        # new=1 forces a new browser window (not just a tab), which is
        # important for OAuth flows where the user needs to see both the
        # authorization page and the app simultaneously.
        if webbrowser.open(url, new=1):
            logger.info("[URL-LAUNCH] Opened via webbrowser source=%s", source)
            return True
        logger.warning("[URL-LAUNCH] webbrowser rejected URL source=%s", source)
        return False
    except Exception as exc:
        logger.error(
            "[URL-LAUNCH] webbrowser.open failed error_type=%s",
            type(exc).__name__,
        )
        return False
