#!/usr/bin/env python3
"""Refresh Board Game Wall from BGG's official rank CSV and XML API2.

BoardGameGeek's current XML API terms allow an approved application's bearer
Application Token to authorize the all-games rank CSV. The same token is also
used by fetch_bgg.py for XML API2 enrichment. No BGG username/password is
required by this script.
"""

import gzip
import sys
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Import shared XML enrichment/history code without running its __main__.
import fetch_bgg as bgg

RANK_PAGE = "https://boardgamegeek.com/data_dumps/bg_ranks"

HEADERS = {
    "Authorization": f"Bearer {bgg.TOKEN}",
    "User-Agent": bgg.USER_AGENT,
    # BGG may return the dump directly or an HTML page containing its signed URL.
    "Accept": "text/csv,application/zip,application/octet-stream,text/html;q=0.9,*/*;q=0.8",
}


def looks_like_csv(payload: bytes) -> bool:
    sample = payload[:2048].decode("utf-8-sig", errors="replace").lower()
    first_line = sample.splitlines()[0] if sample.splitlines() else ""
    return (
        "id" in first_line
        and "name" in first_line
        and "rank" in first_line
        and "," in first_line
    )


def extract_signed_zip_url(html: str, base_url: str):
    soup = BeautifulSoup(html, "html.parser")
    candidates = []

    for link in soup.find_all("a", href=True):
        href = urljoin(base_url, link["href"])
        text = link.get_text(" ", strip=True).lower()
        parsed = urlparse(href)
        path = parsed.path.lower()

        if path.endswith(".zip"):
            candidates.append(href)
            if (
                "click to download" in text
                or "geek-export-stats" in parsed.netloc.lower()
                or "boardgames_ranks" in path
            ):
                return href

    return candidates[0] if candidates else None


def download_official_rank_csv():
    print("Downloading BGG's official rank dump with the approved application token...")
    response = requests.get(
        RANK_PAGE,
        headers=HEADERS,
        timeout=120,
        allow_redirects=True,
    )
    response.raise_for_status()

    payload = response.content
    content_type = response.headers.get("content-type", "").lower()
    print(
        f"Rank source response: HTTP {response.status_code}; "
        f"content-type={content_type or 'unknown'}; bytes={len(payload)}"
    )

    # Direct ZIP response.
    if payload.startswith(b"PK"):
        return bgg.extract_csv_bytes(payload, response.url)

    # Some download paths may return a gzip stream rather than a ZIP.
    if payload.startswith(b"\x1f\x8b"):
        unzipped = gzip.decompress(payload)
        if looks_like_csv(unzipped):
            return unzipped

    # BGG can return the CSV directly from /data_dumps/bg_ranks even when the
    # content type is generic, so detect the CSV by its header instead of
    # depending on Content-Type.
    if looks_like_csv(payload):
        return payload

    # Some BGG responses are an authorized HTML page containing a short-lived,
    # signed S3 ZIP URL. Follow that URL if present.
    text = response.text
    signed_url = extract_signed_zip_url(text, response.url)
    if signed_url:
        print("BGG returned a signed rank-dump URL; downloading ZIP...")
        download_headers = {
            "User-Agent": bgg.USER_AGENT,
            "Referer": RANK_PAGE,
        }
        # Keep the bearer token only on BGG-owned URLs. Signed S3 URLs already
        # contain their authorization in the query string.
        if (urlparse(signed_url).hostname or "").lower().endswith("boardgamegeek.com"):
            download_headers["Authorization"] = f"Bearer {bgg.TOKEN}"

        download = requests.get(
            signed_url,
            headers=download_headers,
            timeout=180,
            allow_redirects=True,
        )
        download.raise_for_status()
        if download.content.startswith(b"PK"):
            return bgg.extract_csv_bytes(download.content, download.url)
        if looks_like_csv(download.content):
            return download.content
        raise RuntimeError(
            "BGG's signed rank download did not contain a ZIP or CSV. "
            f"content-type={download.headers.get('content-type', 'unknown')}"
        )

    preview = text[:160].replace("\n", " ").replace("\r", " ")
    raise RuntimeError(
        "The approved BGG application token reached the rank-dump endpoint, "
        "but BGG returned neither CSV data nor a signed ZIP link. "
        f"content-type={content_type or 'unknown'}; response starts: {preview!r}"
    )


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
    if not bgg.TOKEN:
        raise SystemExit("BGG_TOKEN is required.")

    csv_bytes = download_official_rank_csv()
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
