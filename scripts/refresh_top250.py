#!/usr/bin/env python3
"""Refresh Board Game Wall from BGG's official rank CSV and XML API2.

The rank CSV is licensed with the XML API but its download page requires a
logged-in BGG web session. Credentials are read only from environment variables
and are exchanged for session cookies in memory for the duration of this run.
"""

import os
import sys
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Import the shared XML enrichment/history code without running its __main__.
import fetch_bgg as bgg

BGG_USERNAME = os.environ.get("BGG_USERNAME", "").strip()
BGG_PASSWORD = os.environ.get("BGG_PASSWORD", "")
LOGIN_URL = "https://boardgamegeek.com/login/api/v1"
RANK_PAGE = "https://boardgamegeek.com/data_dumps/bg_ranks"

BROWSER_HEADERS = {
    "User-Agent": bgg.USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def require_credentials():
    missing = []
    if not BGG_USERNAME:
        missing.append("BGG_USERNAME")
    if not BGG_PASSWORD:
        missing.append("BGG_PASSWORD")
    if missing:
        names = ", ".join(missing)
        raise SystemExit(
            f"Missing GitHub Actions secret(s): {names}. "
            "The BGG rank CSV requires a logged-in BGG web session."
        )


def login():
    session = requests.Session()
    session.headers.update(BROWSER_HEADERS)

    response = session.post(
        LOGIN_URL,
        json={
            "credentials": {
                "username": BGG_USERNAME,
                "password": BGG_PASSWORD,
            }
        },
        headers={**BROWSER_HEADERS, "Content-Type": "application/json"},
        timeout=45,
    )

    if response.status_code in (400, 401, 403):
        raise RuntimeError(
            f"BGG login failed with HTTP {response.status_code}. "
            "Check BGG_USERNAME/BGG_PASSWORD and whether BGG requires an "
            "interactive verification for this account."
        )
    response.raise_for_status()

    cookie_names = set(session.cookies.keys())
    if not cookie_names.intersection({"SessionID", "bggusername", "bgg_username"}):
        print(
            "Warning: login returned no familiar BGG cookie name; "
            "continuing because BGG cookie names can change."
        )

    return session


def rank_download_url(session):
    response = session.get(RANK_PAGE, timeout=60)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # BGG currently labels the signed download link "Click to Download".
    for link in soup.find_all("a", href=True):
        text = link.get_text(" ", strip=True).lower()
        href = urljoin(response.url, link["href"])
        path = urlparse(href).path.lower()
        if "click to download" in text:
            return href
        if "boardgames_ranks" in path and path.endswith(".zip"):
            return href

    raise RuntimeError(
        "Logged in to BGG, but no rank-dump download link was found. "
        "BGG may have changed the data-dump page markup."
    )


def download_rank_csv(session, url):
    response = session.get(url, timeout=180, allow_redirects=True)
    response.raise_for_status()
    csv_bytes = bgg.extract_csv_bytes(response.content, response.url)
    if len(csv_bytes) < 1000:
        raise RuntimeError("Downloaded BGG rank CSV was unexpectedly small.")
    return csv_bytes


def current_top(csv_bytes):
    ranked = bgg.parse_rank_csv(csv_bytes)
    ranked.sort(key=lambda item: item["rank"])
    top = ranked[: bgg.TOP_N]
    if len(top) < bgg.TOP_N:
        raise RuntimeError(
            f"Official BGG CSV returned only {len(top)} usable ranked games; "
            f"expected at least {bgg.TOP_N}."
        )
    return top


def main():
    require_credentials()
    print("Opening authenticated BGG session for the official rank CSV...")
    session = login()
    time.sleep(2)

    print("Locating BGG's current rank dump...")
    download_url = rank_download_url(session)

    print("Downloading official BGG rank CSV...")
    csv_bytes = download_rank_csv(session, download_url)
    top = current_top(csv_bytes)
    print(f"Discovered current BGG Top {len(top)} from the official rank CSV.")

    games = bgg.enrich(top)
    bgg.save(games, "BoardGameGeek rank CSV")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"BGG Top 250 refresh failed: {exc}", file=sys.stderr)
        raise
