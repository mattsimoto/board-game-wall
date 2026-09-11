# Board Game Wall

A visual market-style dashboard for the current BoardGameGeek Top 250. Higher-ranked games occupy more space, while filters and movement views make it easy to explore games by category, player count, age, play time, and recent rank change.

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

## Features

- Automatically discovers the current BoardGameGeek Top 250
- Dense, responsive wall of board-game box covers
- Tile size based on current BGG overall rank
- Views for Overall, Climbers, Fallers, and Hot Now
- Selectable 1-day, 7-day, and 30-day rank movement
- Filters for category, players, minimum age, and play time
- Game detail modal with all three movement periods, rating, metadata, and BGG link
- Daily historical rank snapshots
- Server-side BGG refresh through GitHub Actions
- Static cached JSON for fast GitHub Pages delivery
- BGG thumbnails for the wall and full-size artwork for game details
- No application server and no front-end build step
- Responsive desktop, tablet, and mobile layouts

## How it works

```text
Logged-in BoardGameGeek session
        ↓
Official BGG rank CSV
        ↓
Current Top 250 IDs + ranks
        ↓
BoardGameGeek XML API2 + Application Token
        ↓
Metadata enrichment in batches of 20
        ↓
GitHub Actions
        ↓
data/games.json
        +
data/rank-history.json
        ↓
GitHub Pages
        ↓
Browser renders wall + 1D / 7D / 30D movement
```

BoardGameGeek identifies its rank CSV as the preferred source for retrieving game names and ranks at scale. The rank-dump download is available to logged-in BGG users, so Board Game Wall creates a short-lived authenticated web session inside GitHub Actions to obtain the official CSV. It then uses an approved BGG Application Token for XML API2 enrichment.

BGG login credentials, the application token, and session cookies never appear in the public site. Login credentials and the token are supplied to the workflow through GitHub Actions secrets, and the web-session cookies exist only in memory during a refresh run.

## Run your own copy

### 1. Fork or clone the repository

```bash
git clone https://github.com/mattsimoto/board-game-wall.git
cd board-game-wall
```

The front end is plain HTML, CSS, and JavaScript, so you can run it locally with any simple static web server.

```bash
python3 -m http.server 8000
```

Then open `http://localhost:8000`.

### 2. Register a BoardGameGeek application

BoardGameGeek requires an approved application and Application Token for XML API access.

1. Sign in to BoardGameGeek.
2. Visit the BGG Applications page.
3. Register your application under the appropriate use type.
4. After approval, create an Application Token.

Do not commit the token or BGG login credentials to the repository.

### 3. Add GitHub Actions secrets

In your repository, open:

**Settings → Secrets and variables → Actions → New repository secret**

Create these three repository secrets:

```text
BGG_TOKEN
BGG_USERNAME
BGG_PASSWORD
```

- `BGG_TOKEN` is the approved BoardGameGeek Application Token used for XML API2 requests.
- `BGG_USERNAME` and `BGG_PASSWORD` are used only to establish the logged-in BGG session required to download the official rank CSV.

For a public fork, you may prefer to use a dedicated BoardGameGeek account for the rank-dump session rather than storing credentials for your primary BGG account. In either case, keep all three values in GitHub Actions secrets and never commit them to source control.

### 4. Run the data refresh

Open:

**Actions → Update BoardGameGeek data → Run workflow**

The workflow signs in to BGG, downloads the official current rank CSV, selects the Top 250 non-expansion games, enriches them through XML API2, records daily rank snapshots, calculates movement, and commits the resulting JSON back to the repository.

The workflow also runs automatically once per day. `BGG_TOP_N` is set to `250` in the workflow and can be changed if a fork wants a different wall size.

## Publish with GitHub Pages

This project is designed to publish directly from the repository root.

1. Open **Settings → Pages**.
2. Set **Source** to **Deploy from a branch**.
3. Select `main`.
4. Select `/ (root)`.
5. Save.

For this repository, the expected Pages URL is:

`https://mattsimoto.github.io/board-game-wall/`

Forks will use the corresponding GitHub username and repository name.

## Rank movement

Board Game Wall stores one rank snapshot per game per UTC calendar day in `data/rank-history.json`.

Each refresh calculates:

- `rankChange1` — change from approximately one day ago
- `rankChange7` — change from approximately seven days ago
- `rankChange30` — change from approximately thirty days ago

A positive number means the game moved **up** the ranking. A negative number means it moved **down**.

A period remains unavailable until enough history exists for that game. The interface displays an em dash rather than falsely reporting `0` while history is still being collected. This matters especially when a title first enters the Top 250.

The historical file retains roughly 45 days of snapshots, including games that leave the current Top 250, so a title that later re-enters can retain useful recent history.

## Top 250 discovery

The candidate pool is rebuilt from BGG's official rank CSV on every refresh rather than using a fixed list of game IDs. This means titles can automatically:

- enter the Top 250
- leave the Top 250
- change rank
- appear in Climbers and Fallers as history accumulates

The rank CSV determines membership and overall rank. XML API2 supplies the richer fields used by the wall, including box images, categories, player counts, age, play time, and ratings.

To reduce API load, XML enrichment is performed sequentially in batches of at most 20 games with a pause between requests.

## Project structure

```text
index.html                         Page structure
styles.css                         Wall design and responsive layout
movement.css                       Movement-period control styles
app.js                             Rendering, movement, sorting, filtering, modal behavior
assets/poweredbyBGGsm.webp         Official BGG attribution artwork
assets/poweredbyBGG.webp           Alternate BGG attribution artwork
assets/box-placeholder.svg         Fallback artwork
scripts/refresh_top250.py          Logged-in official rank CSV download + refresh orchestration
scripts/fetch_bgg.py               XML enrichment and rank-history helpers
data/games.json                    Cached current Top 250 consumed by the website
data/rank-history.json             Historical daily rank snapshots
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

Issues and pull requests are welcome. Useful areas for future work include:

- new-entry badges and Top 250 entry dates
- all-time-high rank tracking
- longer historical views
- search
- additional filters and sorting options
- accessibility improvements
- performance improvements for larger datasets

When contributing, do not commit BoardGameGeek API tokens, account credentials, or other secrets.
