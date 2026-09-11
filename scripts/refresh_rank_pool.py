#!/usr/bin/env python3
"""Refresh Board Game Wall from a buffered BGG candidate pool.

If data/rank-candidates.json exists, the script refreshes live XML API2 ranks
for that pool, adds BGG Hot items, retains the best 1000 candidates, and
publishes the live Top 250. If the candidate file has not been seeded yet, it
simply refreshes the games already in data/games.json so the current site keeps
working until an official rank CSV is supplied once.
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import fetch_bgg as bgg

CANDIDATE_FILE = Path("data/rank-candidates.json")
POOL_TARGET = int(os.environ.get("BGG_POOL_N", "1000"))
PUBLISH_TARGET = int(os.environ.get("BGG_TOP_N", "250"))


def live_rank(item, fallback=999999):
    for rank_node in item.findall("./statistics/ratings/ranks/rank"):
        if rank_node.attrib.get("name") == "boardgame":
            rank = bgg.parse_int(rank_node.attrib.get("value"), fallback)
            return rank if rank > 0 else fallback
    return fallback


def hot_ids():
    try:
        root = bgg.request_xml("https://boardgamegeek.com/xmlapi2/hot?type=boardgame")
        ids = []
        for item in root.findall("item"):
            game_id = bgg.parse_int(item.attrib.get("id"))
            if game_id:
                ids.append(game_id)
        print(f"Loaded {len(ids)} current BGG Hot IDs.")
        return ids
    except Exception as exc:
        print(f"Warning: could not load BGG Hot list: {exc}")
        return []


def current_site_ids():
    payload = json.loads(bgg.DATA_FILE.read_text(encoding="utf-8"))
    return [bgg.parse_int(game.get("id")) for game in payload.get("games", []) if bgg.parse_int(game.get("id"))]


def candidate_ids():
    if not CANDIDATE_FILE.exists():
        ids = current_site_ids()
        print(
            f"No seeded candidate pool yet; refreshing the existing {len(ids)} site games only."
        )
        return ids, False

    payload = json.loads(CANDIDATE_FILE.read_text(encoding="utf-8"))
    ids = [bgg.parse_int(value) for value in payload.get("ids", [])]
    ids = [value for value in ids if value]
    if not ids:
        raise RuntimeError("data/rank-candidates.json exists but contains no usable IDs.")

    seen = set(ids)
    for game_id in hot_ids():
        if game_id not in seen:
            ids.append(game_id)
            seen.add(game_id)

    print(f"Refreshing {len(ids)} buffered ranking candidates.")
    return ids, True


def fetch_live_games(ids):
    games = []
    total = len(ids)

    for start in range(0, total, 20):
        batch = ids[start : start + 20]
        print(f"Refreshing candidates {start + 1}-{min(start + 20, total)} of {total}...")
        root = bgg.request_xml(
            "https://boardgamegeek.com/xmlapi2/thing?id="
            + ",".join(str(value) for value in batch)
            + "&type=boardgame&stats=1"
        )

        for item in root.findall("item"):
            game_id = bgg.parse_int(item.attrib.get("id"))
            rank = live_rank(item)
            categories = [
                link.attrib.get("value")
                for link in item.findall("link")
                if link.attrib.get("type") == "boardgamecategory" and link.attrib.get("value")
            ]

            games.append(
                {
                    "id": game_id,
                    "name": bgg.primary_name(item),
                    "year": bgg.int_value(item, "yearpublished"),
                    "rank": rank,
                    "rating": bgg.float_value(item, "./statistics/ratings/average"),
                    "minPlayers": bgg.int_value(item, "minplayers", 1),
                    "maxPlayers": bgg.int_value(item, "maxplayers", 1),
                    "minAge": bgg.int_value(item, "minage", 0),
                    "minPlayTime": bgg.int_value(item, "minplaytime", 0),
                    "maxPlayTime": bgg.int_value(item, "maxplaytime", 0),
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

        if start + 20 < total:
            time.sleep(6)

    return games


def record_pool_history(games):
    history = bgg.load_history()
    now = datetime.now(timezone.utc)
    for game in games:
        if 0 < game["rank"] < 999999:
            bgg.record_snapshot(history, game["id"], game["rank"], now)
    bgg.HISTORY_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")


def write_next_candidate_pool(games, hot):
    ranked = [game for game in games if 0 < game["rank"] < 999999]
    ranked.sort(key=lambda game: game["rank"])
    next_ids = [game["id"] for game in ranked[:POOL_TARGET]]

    seen = set(next_ids)
    for game_id in hot:
        if game_id not in seen:
            next_ids.append(game_id)
            seen.add(game_id)

    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    CANDIDATE_FILE.write_text(
        json.dumps(
            {
                "updated": now,
                "source": "Official BGG seed + live XML API2 ranks + BGG Hot",
                "poolTarget": POOL_TARGET,
                "ids": next_ids,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Retained {len(next_ids)} candidates for the next refresh.")


def main():
    ids, seeded = candidate_ids()
    if not ids:
        raise RuntimeError("No game IDs are available to refresh.")

    # Capture Hot separately for persistence when a seeded pool is active.
    current_hot = hot_ids() if seeded else []
    if seeded:
        existing = set(ids)
        for game_id in current_hot:
            if game_id not in existing:
                ids.append(game_id)
                existing.add(game_id)

    games = fetch_live_games(ids)
    ranked = [game for game in games if 0 < game["rank"] < 999999]
    ranked.sort(key=lambda game: game["rank"])

    if seeded:
        if len(ranked) < PUBLISH_TARGET:
            raise RuntimeError(
                f"Only {len(ranked)} ranked candidates were returned; need at least {PUBLISH_TARGET}."
            )
        record_pool_history(ranked)
        published = ranked[:PUBLISH_TARGET]
        write_next_candidate_pool(ranked, current_hot)
        bgg.TOP_N = PUBLISH_TARGET
        bgg.save(published, "Buffered BGG XML API2 live ranks")
        print(f"Published live BGG Top {len(published)} from the buffered candidate pool.")
    else:
        # Preserve the existing wall size until an official CSV seed is supplied.
        existing_ids = set(current_site_ids())
        published = [game for game in ranked if game["id"] in existing_ids]
        bgg.TOP_N = len(published)
        bgg.save(published, "BGG XML API2 existing set")
        print(f"Refreshed {len(published)} existing wall games while awaiting a rank seed.")


if __name__ == "__main__":
    main()
