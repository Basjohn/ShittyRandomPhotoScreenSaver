"""Operator-initiated, read-only Steam followed-games G0 feasibility probe.

Run: python -m tools.steam_followed_g0_probe --probe
The command loads only the already linked account's SteamID64. It does not
change Steam credentials, write cache, start a widget or print private IDs.
"""
from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--probe", action="store_true", help="Make one read-only followed-games request")
    mode.add_argument("--news-probe", action="store_true", help="Verify follows and sample at most two public app-news feeds")
    args = parser.parse_args(argv)
    from core.steam.credentials import SteamCredentialError, load_credentials
    from core.steam.games_followed_probe import probe_followed_games, fetch_followed_appids_for_news_probe
    from core.steam.games_followed_news_probe import probe_followed_news
    try:
        credential = load_credentials()
    except (SteamCredentialError, OSError, ValueError):
        print("G0: existing Steam credentials unavailable")
        return 2
    if credential is None:
        print("G0: existing Steam identity not configured")
        return 2
    try:
        if args.news_probe:
            status, followed_appids = fetch_followed_appids_for_news_probe(credential.profile_identifier)
            if status != "confirmed_nonempty" or not followed_appids:
                print(f"G0 NEWS: followed_set_{status}")
                return 1
            outcome = probe_followed_news(followed_appids)
            # No app IDs, SteamID, article links or payload in stdout.
            print(f"G0 NEWS: {outcome.status}, apps_checked={outcome.apps_checked}, usable_items={outcome.usable_items}")
            return 0 if outcome.status.startswith("confirmed_") else 1
        outcome = probe_followed_games(credential.profile_identifier)
    except ValueError:
        print("G0: linked SteamID64 not usable for this endpoint")
        return 2
    # No SteamID, key, app ID, raw payload or request URL in stdout.
    print(f"G0: {outcome.status}" + (f", count={outcome.count}" if outcome.count is not None else ""))
    return 0 if outcome.status.startswith("confirmed_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
