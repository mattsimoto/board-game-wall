# Board Game Wall

A visual market-style dashboard for BoardGameGeek rankings. Higher-ranked games occupy more space, while filters and movement views make it easy to explore games by category, player count, age, play time, and recent rank change.

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

## Features

- Dense, responsive wall of board-game box covers
- Target display of the live BGG Top 250
- Buffered Top 1000 candidate pool for rank discovery
- Daily BGG XML API2 rank and metadata refresh
- BGG Hot items folded into the candidate pool to catch newly surging games
- Tile size based on current overall rank
- Overall, Climbers, Fallers, and Hot Now views
- Selectable 1-day, 7-day, and 30-day rank movement
- Filters for category, players, minimum age, and play time
- Game detail modal with rank, movement, rating, metadata, and BGG link
- Static cached JSON for fast GitHub Pages delivery
- No application server or front-end build step
- Responsive desktop, tablet, and mobile layouts

## How it works

BoardGameGeek publishes an official rank CSV containing game IDs and ranks and identifies it as the preferred bulk ranking source. The current BGG site may require an interactive logged-in browser session to retrieve that file, which makes unattended downloads from hosted CI runners unreliable.

Board Game Wall therefore uses the official CSV as a **one-time candidate seed**, not as a daily dependency.

```text
Official BGG rank CSV (one-time seed)
        ↓
Top 1000 candidate IDs
        ↓
data/rank-candidates.json
        ↓
Daily BGG XML API2 refresh + BGG Hot IDs
        ↓
Current live ranks for buffered candidate pool
        ↓
Publish best 250
        ↓
data/games.json + data/rank-history.json
        ↓
GitHub Pages
```

The buffer means the site does not need to hit BGG's protected rank-download page every day. A game can move into or out of the displayed Top 250 based on its live XML API2 rank, while the BGG Hot list adds emerging titles to the candidate pool automatically.

## Run your own copy

### 1. Fork or clone the repository

```bash
git clone https://github.com/mattsimoto/board-game-wall.git
cd board-game-wall
```

Run the front end locally with any static server:

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000`.

### 2. Register a BoardGameGeek application

BoardGameGeek requires an approved Application Token for XML API use.

1. Sign in to BoardGameGeek.
2. Visit the BGG Applications page.
3. Register the application under the appropriate use type.
4. After approval, create an Application Token.

Never commit the token to source control.

### 3. Add the GitHub Actions secret

Open:

**Settings → Secrets and variables → Actions → New repository secret**

Create one secret:

```text
BGG_TOKEN
```

The token is used only by GitHub Actions and is never sent to site visitors.

### 4. Seed the ranking candidate pool once

While logged into BoardGameGeek, download the official rank dump from:

`https://boardgamegeek.com/data_dumps/bg_ranks`

Then run either form locally:

```bash
python scripts/seed_candidates.py /path/to/boardgames_ranks.csv
```

or:

```bash
python scripts/seed_candidates.py /path/to/boardgames_ranks_YYYY-MM-DD.zip
```

This writes only the best 1,000 non-expansion BGG IDs to:

```text
data/rank-candidates.json
```

Commit that compact candidate file. The full BGG dump does not need to live in the repository.

If no candidate file exists yet, the scheduled workflow safely refreshes only the games already present in `data/games.json` rather than failing the public site.

### 5. Run the refresh

Open:

**Actions → Update BoardGameGeek data → Run workflow**

Once the candidate pool is seeded, each run:

1. Loads the buffered candidate IDs.
2. Adds current BGG Hot game IDs.
3. Retrieves live XML API2 stats in batches of at most 20.
4. Sorts candidates by their current BGG overall rank.
5. Publishes the best 250 to `data/games.json`.
6. Retains the best 1,000 candidates plus Hot items for the next run.
7. Records rank snapshots for movement calculations.

The workflow also runs automatically once per day.

## Publish with GitHub Pages

1. Open **Settings → Pages**.
2. Set **Source** to **Deploy from a branch**.
3. Select `main`.
4. Select `/ (root)`.
5. Save.

For this repository:

`https://mattsimoto.github.io/board-game-wall/`

## Rank movement

Board Game Wall stores daily rank snapshots in `data/rank-history.json` and calculates:

- `rankChange1` — approximately 1 day
- `rankChange7` — approximately 7 days
- `rankChange30` — approximately 30 days

A positive number means the game climbed the rankings. A negative number means it fell.

When there is not enough history for a period, the interface displays an em dash rather than falsely reporting zero movement. The buffered pool records rank history before a game reaches the displayed Top 250, so future entrants can often arrive with useful movement history already available.

## Candidate-pool tradeoff

The buffered approach avoids bypassing BGG's browser-verification layer and greatly reduces dependence on the protected bulk-download page. It is intentionally conservative about API traffic.

A title outside the candidate pool can still be discovered when it appears in BGG Hot. For maximum coverage, refresh the Top 1000 seed from a newly downloaded official rank CSV occasionally. The daily wall itself continues to use live XML API2 ranks between seed refreshes.

## Project structure

```text
index.html                         Page structure
styles.css                         Wall design and responsive layout
movement.css                       Movement-period controls
app.js                             Rendering, movement, sorting, filtering, modal
assets/poweredbyBGGsm.webp         Official BGG attribution artwork
assets/poweredbyBGG.webp           Alternate BGG attribution artwork
assets/box-placeholder.svg         Fallback artwork
scripts/fetch_bgg.py               Shared BGG XML/history helpers
scripts/refresh_rank_pool.py       Daily buffered ranking refresh
scripts/seed_candidates.py         One-time official CSV/ZIP seed utility
data/games.json                    Cached games consumed by the website
data/rank-history.json             Historical daily rank snapshots
data/rank-candidates.json          Buffered candidate IDs, once seeded
.github/workflows/update-bgg.yml   Scheduled/manual refresh workflow
.nojekyll                          Disables Jekyll processing on GitHub Pages
```

## BoardGameGeek attribution

Board Game Wall uses data supplied by BoardGameGeek and displays the required **Powered by BGG** attribution linked to BoardGameGeek.

BoardGameGeek, BGG, the Powered by BGG logo, game metadata, game images, and other BoardGameGeek-provided content are owned by their respective rights holders and are **not** licensed under this repository's MIT License.

If you fork or redistribute this project while continuing to use the BoardGameGeek API, you are responsible for complying with the current BoardGameGeek API terms, branding requirements, rate limits, and application-registration requirements.

This project is not affiliated with or endorsed by BoardGameGeek.

## License

The original source code in this repository is released under the [MIT License](LICENSE).

The MIT License applies to the project's original HTML, CSS, JavaScript, Python, workflow configuration, and documentation. It does not grant rights to third-party trademarks, logos, game artwork, BoardGameGeek content, or data supplied by external services.

## Contributing

Issues and pull requests are welcome. Useful areas include new-entry badges, all-time-high rank tracking, longer history, search, additional filters, accessibility, and performance improvements.

Do not commit BoardGameGeek Application Tokens, account credentials, session cookies, or other secrets.
