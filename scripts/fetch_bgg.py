#!/usr/bin/env python3
import csv
import io
import json
import os
import time
import zipfile
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET

TOKEN = os.environ.get("BGG_TOKEN", "").strip()
DATA_FILE = Path("data/games.json")
HISTORY_FILE = Path("data/rank-history.json")
TOP_N = int(os.environ.get("BGG_TOP_N", "250"))
USER_AGENT = "BoardGameWall/2.0 (+https://github.com/mattsimoto/board-game-wall)"
RANK_DUMP_PAGE = "https://boardgamegeek.com/data_dumps/bg_ranks"
BGG_HOSTS = {"boardgamegeek.com", "www.boardgamegeek.com"}

if not TOKEN:
    raise SystemExit(
        "BGG_TOKEN is required. Add it as a GitHub Actions repository secret."
    )

AUTH_HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "User-Agent": USER_AGENT,
}
PUBLIC_HEADERS = {"User-Agent": USER_AGENT}


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href)


def headers_for(url):
    host = (urlparse(url).hostname or "").lower()
    return AUTH_HEADERS if host in BGG_HOSTS else PUBLIC_HEADERS


def request_bytes(url, *, timeout=90, use_auth=True):
    last_error = None
    for attempt in range(5):
        try:
            response = requests.get(
                url,
                headers=headers_for(url) if use_auth else PUBLIC_HEADERS,
                timeout=timeout,
                allow_redirects=True,
            )
            if response.status_code == 200:
                return response
            if response.status_code in (429, 500, 502, 503, 504):
                time.sleep(10 * (attempt + 1))
                continue
            response.raise_for_status()
        except requests.RequestException as exc:
            last_error = exc
            if attempt == 4:
                raise
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"BGG request repeatedly failed: {url}") from last_error


def request_xml(url):
    response = request_bytes(url, timeout=60)
    return ET.fromstring(response.content)


def download_rank_dump():
    response = request_bytes(RANK_DUMP_PAGE)

    content_type = response.headers.get("content-type", "").lower()
    if (
        response.content.startswith(b"PK")
        or "text/csv" in content_type
        or response.url.lower().endswith((".csv", ".zip"))
    ):
        return response.content, response.url

    parser = LinkParser()
    parser.feed(response.text)

    candidates = []
    for href in parser.links:
        absolute = urljoin(response.url, href)
        path = urlparse(absolute).path.lower()
        if (
            ("boardgames_ranks" in path or "bg_ranks" in path)
            and path.endswith((".zip", ".csv"))
        ):
            candidates.append(absolute)

    if not candidates:
        raise RuntimeError(
            "Could not find the BoardGameGeek rank dump download link. "
            "The application token may not have access to the data-dump page."
        )

    download_url = sorted(set(candidates))[-1]
    download = request_bytes(download_url, timeout=120)
    return download.content, download.url


def extract_csv_bytes(payload, source_url):
    if payload.startswith(b"PK") or source_url.lower().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            csv_names = [
                name
                for name in archive.namelist()
                if name.lower().endswith(".csv")
                and ("boardgames_ranks" in name.lower() or "bg_ranks" in name.lower())
            ]
            if not csv_names:
                csv_names = [
                    name for name in archive.namelist() if name.lower().endswith(".csv")
                ]
            if not csv_names:
                raise RuntimeError("The BGG rank dump ZIP did not contain a CSV file.")
            return archive.read(sorted(csv_names)[-1])
    return payload


def parse_int(value, default=0):
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def parse_float(value, default=0.0):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def parse_rank_csv(csv_bytes):
    text = csv_bytes.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    ranked = []
    for row in reader:
        game_id = parse_int(row.get("id"))
        rank = parse_int(row.get("rank"))
        is_expansion = str(row.get("is_expansion", "0")).strip().lower()

        if not game_id or rank <= 0:
            continue
        if is_expansion not in ("", "0", "false", "no", "n"):
            continue

        ranked.append(
            {
                "id": game_id,
                "rank": rank,
                "csvName": row.get("name", "").strip(),
                "csvRating": parse_float(row.get("average")),
            }
        )
    return ranked


def load_top_from_browse():
    ranked = []
    seen = set()
    page = 1

    while len(ranked) < TOP_N:
        url = (
            f"https://boardgamegeek.com/browse/boardgame/page/{page}"
            "?sort=rank&sortdir=asc"
        )
        response = request_bytes(url, timeout=60, use_auth=False)
        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.find_all("tr", id="row_")
        if not rows:
            raise RuntimeError(f"No ranked game rows found on BGG browse page {page}.")

        for row in rows:
            name_cell = row.select_one(".collection_objectname")
            rank_cell = row.select_one(".collection_rank")
            if not name_cell or not rank_cell:
                continue

            link = name_cell.select_one("a.primary") or name_cell.select_one(
                "a[href*='/boardgame/']"
            )
            if not link:
                continue

            href = link.get("href", "")
            href_parts = href.split("/")
            try:
                boardgame_index = href_parts.index("boardgame")
                game_id = int(href_parts[boardgame_index + 1])
            except (ValueError, IndexError):
                continue

            rank_text = rank_cell.get_text(" ", strip=True)
            rank_digits = "".join(ch if ch.isdigit() else " " for ch in rank_text).split()
            if not rank_digits:
                continue
            rank = int(rank_digits[0])

            if game_id in seen or rank <= 0:
                continue

            seen.add(game_id)
            ranked.append(
                {
                    "id": game_id,
                    "rank": rank,
                    "csvName": link.get_text(" ", strip=True),
                    "csvRating": 0.0,
                }
            )

        page += 1
        if len(ranked) < TOP_N:
            time.sleep(5)
        if page > 10:
            raise RuntimeError("Unable to discover enough ranked games from BGG browse pages.")

    ranked.sort(key=lambda item: item["rank"])
    top = ranked[:TOP_N]
    print(f"Discovered current BGG Top {len(top)} from browse ranking pages.")
    return top


def load_top_ranked_games():
    try:
        payload, source_url = download_rank_dump()
        csv_bytes = extract_csv_bytes(payload, source_url)
        ranked = parse_rank_csv(csv_bytes)
        ranked.sort(key=lambda item: item["rank"])
        top = ranked[:TOP_N]
        if len(top) < TOP_N:
            raise RuntimeError(
                f"BGG rank dump contained only {len(top)} usable ranked games; "
                f"expected at least {TOP_N}."
            )
        print(f"Discovered current BGG Top {len(top)} from rank dump.")
        return top, "BoardGameGeek rank CSV"
    except Exception as exc:
        print(f"Rank CSV unavailable ({exc}). Falling back to BGG browse ranking pages.")
        return load_top_from_browse(), "BoardGameGeek browse ranking"


def int_value(node, tag, default=0):
    el = node.find(tag)
    return parse_int(el.attrib.get("value")) if el is not None else default


def float_value(node, path, default=0.0):
    el = node.find(path)
    return parse_float(el.attrib.get("value")) if el is not None else default


def primary_name(item):
    for el in item.findall("name"):
        if el.attrib.get("type") == "primary":
            return el.attrib.get("value", "Untitled")
    return "Untitled"


def enrich(ranked_games):
    rank_by_id = {item["id"]: item for item in ranked_games}
    ids = [str(item["id"]) for item in ranked_games]
    games = []

    for start in range(0, len(ids), 20):
        batch = ids[start : start + 20]
        print(
            f"Enriching games {start + 1}-{min(start + 20, len(ids))} "
            f"of {len(ids)}..."
        )
        root = request_xml(
            "https://boardgamegeek.com/xmlapi2/thing?id="
            + ",".join(batch)
            + "&type=boardgame&stats=1"
        )

        returned_ids = set()
        for item in root.findall("item"):
            game_id = int(item.attrib["id"])
            returned_ids.add(game_id)
            seed = rank_by_id.get(game_id)
            if not seed:
                continue

            categories = [
                link.attrib.get("value")
                for link in item.findall("link")
                if link.attrib.get("type") == "boardgamecategory"
                and link.attrib.get("value")
            ]

            games.append(
                {
                    "id": game_id,
                    "name": primary_name(item) or seed["csvName"],
                    "year": int_value(item, "yearpublished"),
                    "rank": seed["rank"],
                    "rating": float_value(
                        item, "./statistics/ratings/average", seed["csvRating"]
                    ),
                    "minPlayers": int_value(item, "minplayers", 1),
                    "maxPlayers": int_value(item, "maxplayers", 1),
                    "minAge": int_value(item, "minage", 0),
                    "minPlayTime": int_value(item, "minplaytime", 0),
                    "maxPlayTime": int_value(item, "maxplaytime", 0),
                    "categories": categories,
                    "thumbnail": (
                        item.findtext("thumbnail")
                        or item.findtext("image")
                        or "assets/box-placeholder.svg"
                    ).strip(),
                    "image": (
                        item.findtext("image") or "assets/box-placeholder.svg"
                    ).strip(),
                }
            )

        missing = [game_id for game_id in map(int, batch) if game_id not in returned_ids]
        if missing:
            print(f"Warning: XML API did not return {len(missing)} game(s): {missing}")

        if start + 20 < len(ids):
            time.sleep(6)

    if len(games) < int(TOP_N * 0.95):
        raise RuntimeError(
            f"Only {len(games)} of {TOP_N} ranked games were enriched; "
            "aborting rather than publishing a partial wall."
        )

    return games


def load_history():
    if not HISTORY_FILE.exists():
        return {}
    try:
        payload = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except json.JSONDecodeError:
        return {}


def parse_entry_time(entry):
    try:
        return datetime.fromisoformat(entry["date"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        return None


def calculate_change(history, game_id, current_rank, days, now):
    entries = history.get(str(game_id), [])
    target_date = (now - timedelta(days=days)).date()

    candidates = []
    for entry in entries:
        entry_time = parse_entry_time(entry)
        if entry_time and entry_time.date() <= target_date:
            candidates.append((entry_time, entry))

    if not candidates:
        return None

    _, older = max(candidates, key=lambda pair: pair[0])
    older_rank = parse_int(older.get("rank"))
    if older_rank <= 0:
        return None
    return older_rank - int(current_rank)


def record_snapshot(history, game_id, rank, now):
    key = str(game_id)
    entries = history.setdefault(key, [])
    today = now.date()

    cleaned = []
    replaced_today = False
    for entry in entries:
        entry_time = parse_entry_time(entry)
        if not entry_time:
            continue
        if entry_time.date() == today:
            if not replaced_today:
                cleaned.append(
                    {
                        "date": now.isoformat().replace("+00:00", "Z"),
                        "rank": int(rank),
                    }
                )
                replaced_today = True
        else:
            cleaned.append(entry)

    if not replaced_today:
        cleaned.append(
            {
                "date": now.isoformat().replace("+00:00", "Z"),
                "rank": int(rank),
            }
        )

    cutoff = now - timedelta(days=45)
    kept = []
    for entry in cleaned:
        entry_time = parse_entry_time(entry)
        if entry_time and entry_time >= cutoff:
            kept.append(entry)

    kept.sort(key=lambda entry: parse_entry_time(entry))
    history[key] = kept


def save(games, rank_source):
    history = load_history()
    now = datetime.now(timezone.utc)

    for game in games:
        game["rankChange1"] = calculate_change(
            history, game["id"], game["rank"], 1, now
        )
        game["rankChange7"] = calculate_change(
            history, game["id"], game["rank"], 7, now
        )
        game["rankChange30"] = calculate_change(
            history, game["id"], game["rank"], 30, now
        )

        momentum = (
            game["rankChange7"]
            if game["rankChange7"] is not None
            else game["rankChange1"]
        )
        momentum = momentum or 0
        game["hotScore"] = max(0, 100 - min(game["rank"], 100)) + max(
            0, momentum * 2
        )

        record_snapshot(history, game["id"], game["rank"], now)

    games.sort(key=lambda item: item["rank"])
    timestamp = now.isoformat().replace("+00:00", "Z")

    DATA_FILE.write_text(
        json.dumps(
            {
                "updated": timestamp,
                "source": f"{rank_source} + XML API2",
                "rankSource": rank_source,
                "topN": TOP_N,
                "movementPeriods": [1, 7, 30],
                "games": games,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    HISTORY_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")
    print(f"Published {len(games)} games with 1D / 7D / 30D movement fields.")


if __name__ == "__main__":
    ranked_games, rank_source = load_top_ranked_games()
    save(enrich(ranked_games), rank_source)
