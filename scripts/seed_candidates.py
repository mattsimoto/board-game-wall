#!/usr/bin/env python3
"""Build Board Game Wall's buffered candidate pool from an official BGG rank dump.

Usage:
    python scripts/seed_candidates.py /path/to/boardgames_ranks.csv
    python scripts/seed_candidates.py /path/to/boardgames_ranks_YYYY-MM-DD.zip

The output intentionally stores only BGG IDs, not a copy of the full dump.
"""

import csv
import io
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

OUTPUT = Path("data/rank-candidates.json")
POOL_SIZE = 1000


def parse_int(value, default=0):
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def csv_bytes_from(path):
    raw = path.read_bytes()
    if raw.startswith(b"PK") or path.suffix.lower() == ".zip":
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if not csv_names:
                raise RuntimeError("The ZIP archive contains no CSV file.")
            preferred = [name for name in csv_names if "boardgames_ranks" in name.lower()]
            return archive.read((preferred or csv_names)[0])
    return raw


def build_pool(csv_bytes):
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
        ranked.append((rank, game_id))

    ranked.sort()
    ids = []
    seen = set()
    for _, game_id in ranked:
        if game_id in seen:
            continue
        seen.add(game_id)
        ids.append(game_id)
        if len(ids) >= POOL_SIZE:
            break

    if len(ids) < POOL_SIZE:
        raise RuntimeError(f"Only {len(ids)} ranked non-expansion games were found.")
    return ids


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python scripts/seed_candidates.py <boardgames_ranks.csv|zip>")

    source = Path(sys.argv[1])
    if not source.exists():
        raise SystemExit(f"File not found: {source}")

    ids = build_pool(csv_bytes_from(source))
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(
            {
                "seeded": now,
                "source": "Official BoardGameGeek rank CSV",
                "poolTarget": POOL_SIZE,
                "ids": ids,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {len(ids)} candidate IDs to {OUTPUT}.")


if __name__ == "__main__":
    main()
