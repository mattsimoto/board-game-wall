#!/usr/bin/env python3
import json, os, time
from datetime import datetime, timezone
from pathlib import Path
import requests
import xml.etree.ElementTree as ET

TOKEN = os.environ.get("BGG_TOKEN", "").strip()
DATA_FILE = Path("data/games.json")
HISTORY_FILE = Path("data/rank-history.json")
USER_AGENT = "BoardGameWall/1.0 (+https://github.com/mattsimoto/board-game-wall)"

if not TOKEN:
    raise SystemExit("BGG_TOKEN is required. Add it as a GitHub Actions repository secret after BGG approves your application.")

headers = {"Authorization": f"Bearer {TOKEN}", "User-Agent": USER_AGENT}


def load_seed_ids():
    # Until the approved BGG rank dump is wired in, enrich the IDs already present in games.json.
    # This keeps API traffic small and lets the project operate immediately after token setup.
    payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    return [str(g["id"]) for g in payload.get("games", [])]


def request_xml(url):
    for attempt in range(4):
        r = requests.get(url, headers=headers, timeout=45)
        if r.status_code == 200:
            return ET.fromstring(r.text)
        if r.status_code in (429, 500, 502, 503):
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
    raise RuntimeError(f"BGG request repeatedly failed: {url}")


def int_value(node, tag, default=0):
    el = node.find(tag)
    return int(float(el.attrib.get("value", default))) if el is not None else default


def float_value(node, path, default=0):
    el = node.find(path)
    try:
        return float(el.attrib.get("value", default)) if el is not None else default
    except ValueError:
        return default


def primary_name(item):
    for el in item.findall("name"):
        if el.attrib.get("type") == "primary":
            return el.attrib.get("value", "Untitled")
    return "Untitled"


def enrich(ids):
    games = []
    for start in range(0, len(ids), 20):
        batch = ids[start:start+20]
        root = request_xml("https://boardgamegeek.com/xmlapi2/thing?id=" + ",".join(batch) + "&stats=1")
        for item in root.findall("item"):
            categories = [x.attrib.get("value") for x in item.findall("link") if x.attrib.get("type") == "boardgamecategory"]
            rank = 999999
            for r in item.findall("./statistics/ratings/ranks/rank"):
                if r.attrib.get("name") == "boardgame":
                    try: rank = int(r.attrib.get("value", 999999))
                    except ValueError: pass
            games.append({
                "id": int(item.attrib["id"]),
                "name": primary_name(item),
                "year": int_value(item, "yearpublished"),
                "rank": rank,
                "rating": float_value(item, "./statistics/ratings/average"),
                "minPlayers": int_value(item, "minplayers", 1),
                "maxPlayers": int_value(item, "maxplayers", 1),
                "minAge": int_value(item, "minage", 0),
                "minPlayTime": int_value(item, "minplaytime", 0),
                "maxPlayTime": int_value(item, "maxplaytime", 0),
                "categories": categories,
                "image": (item.findtext("image") or "assets/box-placeholder.svg").strip(),
            })
        if start + 20 < len(ids):
            time.sleep(6)
    return games


def load_history():
    if not HISTORY_FILE.exists(): return {}
    return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))


def calculate_change(history, game_id, current_rank, days=30):
    entries = history.get(str(game_id), [])
    if not entries: return 0
    target = datetime.now(timezone.utc).timestamp() - days * 86400
    older = min(entries, key=lambda e: abs(datetime.fromisoformat(e["date"].replace("Z", "+00:00")).timestamp() - target))
    return int(older["rank"]) - int(current_rank)


def save(games):
    history = load_history()
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for g in games:
        g["rankChange30"] = calculate_change(history, g["id"], g["rank"], 30)
        g["hotScore"] = max(0, 100 - min(g["rank"], 100)) + max(0, g["rankChange30"] * 2)
        entries = history.setdefault(str(g["id"]), [])
        entries.append({"date": now, "rank": g["rank"]})
        history[str(g["id"])] = entries[-45:]
    games.sort(key=lambda x: x["rank"])
    DATA_FILE.write_text(json.dumps({"updated": now, "source": "BoardGameGeek XML API2", "games": games}, indent=2), encoding="utf-8")
    HISTORY_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")


if __name__ == "__main__":
    save(enrich(load_seed_ids()))
