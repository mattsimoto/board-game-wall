#!/usr/bin/env python3
"""Refresh Board Game Wall from BGG's official rank CSV and XML API2.

BGG's data-dump page is a browser application and may not expose its signed
rank ZIP URL to a plain HTTP client. This script therefore uses Chromium only
to open that official page and discover the short-lived signed ZIP URL. It
first tries the approved Application Token and, if necessary, falls back to a
normal BGG browser login using GitHub Actions secrets. The signed ZIP is then
downloaded directly and XML API2 is used for metadata enrichment.
"""

import os
import sys
from urllib.parse import urlparse

import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

# Import shared XML enrichment/history code without running its __main__.
import fetch_bgg as bgg

RANK_PAGE = "https://boardgamegeek.com/data_dumps/bg_ranks"
LOGIN_PAGE = "https://boardgamegeek.com/login"
BGG_USERNAME = os.environ.get("BGG_USERNAME", "").strip()
BGG_PASSWORD = os.environ.get("BGG_PASSWORD", "")

# Use an ordinary browser UA for the browser-only data-dump page. XML API2
# continues to use the identifying BoardGameWall user agent in fetch_bgg.py.
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)


def is_bgg_host(url):
    host = (urlparse(url).hostname or "").lower()
    return host == "boardgamegeek.com" or host.endswith(".boardgamegeek.com")


def find_zip_url(page):
    """Return the current signed rank ZIP href if the rendered page exposes it."""
    for _ in range(20):
        links = page.locator("a[href]")
        count = links.count()
        for index in range(count):
            link = links.nth(index)
            href = link.get_attribute("href") or ""
            text = (link.inner_text(timeout=1500) or "").strip().lower()
            parsed = urlparse(href)
            path = parsed.path.lower()
            if (
                ".zip" in path
                and (
                    "boardgames_ranks" in path
                    or "geek-export-stats" in parsed.netloc.lower()
                    or "click to download" in text
                )
            ):
                return href
        page.wait_for_timeout(750)
    return None


def page_challenge(page):
    try:
        text = page.locator("body").inner_text(timeout=4000).lower()
    except Exception:
        return False
    markers = (
        "verify you are human",
        "checking your browser",
        "just a moment",
        "security verification",
        "captcha",
    )
    return any(marker in text for marker in markers)


def add_bgg_token_to_requests(page):
    """Attach the app token only to BGG-hosted browser requests, never S3."""
    def handler(route):
        request = route.request
        if is_bgg_host(request.url):
            headers = dict(request.headers)
            headers["Authorization"] = f"Bearer {bgg.TOKEN}"
            route.continue_(headers=headers)
        else:
            route.continue_()

    page.route("**/*", handler)


def open_rank_page(page):
    page.goto(RANK_PAGE, wait_until="domcontentloaded", timeout=90000)
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except PlaywrightTimeoutError:
        # BGG keeps some background requests alive; the link can still be ready.
        pass
    return find_zip_url(page)


def fill_first(page, selectors, value):
    for selector in selectors:
        locator = page.locator(selector)
        if locator.count() and locator.first.is_visible():
            locator.first.fill(value)
            return True
    return False


def login_in_browser(page):
    if not BGG_USERNAME or not BGG_PASSWORD:
        return False

    print("Application-token browser session did not expose the ZIP; trying normal BGG browser login...")
    page.goto(LOGIN_PAGE, wait_until="domcontentloaded", timeout=90000)
    try:
        page.wait_for_load_state("networkidle", timeout=12000)
    except PlaywrightTimeoutError:
        pass

    if page_challenge(page):
        raise RuntimeError(
            "BGG presented an interactive browser verification to the GitHub runner."
        )

    username_ok = fill_first(
        page,
        ("#inputUsername", "input[name='username']", "input[type='text']"),
        BGG_USERNAME,
    )
    password_ok = fill_first(
        page,
        ("#inputPassword", "input[name='password']", "input[type='password']"),
        BGG_PASSWORD,
    )
    if not username_ok or not password_ok:
        raise RuntimeError("Could not find BGG's username/password fields in the rendered login page.")

    buttons = (
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Sign In')",
        "button:has-text('Log In')",
    )
    clicked = False
    for selector in buttons:
        locator = page.locator(selector)
        if locator.count() and locator.first.is_visible():
            locator.first.click()
            clicked = True
            break
    if not clicked:
        raise RuntimeError("Could not find BGG's login submit button.")

    page.wait_for_timeout(4000)
    if page_challenge(page):
        raise RuntimeError(
            "BGG requested interactive verification after login; GitHub Actions cannot complete it."
        )

    # Do not infer success from the URL alone; the rank page itself is the test.
    return True


def discover_rank_zip_url():
    print("Opening BGG rank page in Chromium...")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        context = browser.new_context(
            user_agent=BROWSER_UA,
            locale="en-US",
            viewport={"width": 1440, "height": 1000},
        )
        page = context.new_page()
        add_bgg_token_to_requests(page)

        try:
            zip_url = open_rank_page(page)
            if zip_url:
                print("Found official signed BGG rank ZIP using the application-token browser session.")
                return zip_url

            if page_challenge(page):
                print("BGG browser verification detected before login fallback.")

            if login_in_browser(page):
                zip_url = open_rank_page(page)
                if zip_url:
                    print("Found official signed BGG rank ZIP after browser login.")
                    return zip_url

            raise RuntimeError(
                "BGG rendered the data-dump page but did not expose a signed rank ZIP link. "
                "If BGG is requiring interactive verification, use a manually refreshed rank CSV instead."
            )
        finally:
            context.close()
            browser.close()


def download_rank_csv(zip_url):
    print("Downloading BGG's signed rank ZIP...")
    response = requests.get(
        zip_url,
        headers={"User-Agent": BROWSER_UA, "Referer": RANK_PAGE},
        timeout=180,
        allow_redirects=True,
    )
    response.raise_for_status()

    if not response.content.startswith(b"PK"):
        raise RuntimeError(
            "The signed BGG rank URL did not return a ZIP archive "
            f"(content-type={response.headers.get('content-type', 'unknown')})."
        )

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
    if not bgg.TOKEN:
        raise SystemExit("BGG_TOKEN is required.")

    zip_url = discover_rank_zip_url()
    csv_bytes = download_rank_csv(zip_url)
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
