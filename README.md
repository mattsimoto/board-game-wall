# Board Game Wall

A visual market-style dashboard for BoardGameGeek rankings. Higher-ranked games occupy more space, while filters and movement views make it easy to explore games by category, player count, age, and play time.

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)

## Features

- Dense, responsive wall of board-game box covers
- Tile size based on BoardGameGeek overall rank
- Views for Overall, Climbers, Fallers, and Hot Now
- Filters for category, players, minimum age, and play time
- Game detail modal with rank, rating, metadata, and BGG link
- Daily rank snapshots for historical movement tracking
- Server-side BGG API refresh through GitHub Actions
- Static cached JSON for fast GitHub Pages delivery
- No application server and no front-end build step
- Responsive desktop, tablet, and mobile layouts

## How it works

```text
BoardGameGeek XML API2
        ↓
GitHub Actions
        ↓
data/games.json
        +
data/rank-history.json
        ↓
GitHub Pages
        ↓
Browser renders the wall
```

The BoardGameGeek application token is used only inside GitHub Actions. It is never included in the public site or sent to visitors' browsers.

## Run your own copy

### 1. Fork or clone the repository

```bash
git clone https://github.com/mattsimoto/board-game-wall.git
cd board-game-wall
```

The front end is plain HTML, CSS, and JavaScript, so you can open it locally with any simple static web server.

For example:

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

Do not commit the token to the repository.

### 3. Add the GitHub Actions secret

In your repository, open:

**Settings → Secrets and variables → Actions → New repository secret**

Create:

```text
BGG_TOKEN
```

Paste your BoardGameGeek Application Token as the value.

### 4. Run the data refresh

Open:

**Actions → Update BoardGameGeek data → Run workflow**

The workflow retrieves current BGG metadata, updates the cached JSON files, records the latest rank snapshot, and commits changed data back to the repository.

The workflow also runs automatically once per day.

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

BoardGameGeek provides the current rank used by the application, while Board Game Wall builds its own historical series.

Each daily refresh stores a timestamped rank in `data/rank-history.json`. Movement values become more useful as snapshots accumulate. The current interface includes a 30-day movement field and is structured to support additional periods such as 1-day and 7-day changes.

## Project structure

```text
index.html                         Page structure
styles.css                         Wall design and responsive layout
app.js                             Rendering, sorting, filtering, modal behavior
assets/poweredbyBGGsm.webp         Official BGG attribution artwork
assets/poweredbyBGG.webp           Alternate BGG attribution artwork
assets/box-placeholder.svg         Fallback artwork
scripts/fetch_bgg.py               BoardGameGeek API refresh script
data/games.json                    Cached game data
data/rank-history.json             Historical rank snapshots
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

- 1-day and 7-day movement views
- larger ranked-game discovery sets
- new-entry tracking
- all-time-high rank tracking
- additional filter and sorting options
- accessibility improvements
- performance improvements for larger datasets

When contributing, do not commit BoardGameGeek API tokens or other secrets.
