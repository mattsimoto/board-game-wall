# Board Game Wall

A GitHub Pages dashboard that treats BoardGameGeek rankings like a market wall: highly ranked games get more visual space, while climbers and fallers can be surfaced by recent movement.

## Current build

- Responsive dense board-game wall
- Tile size based on overall BGG rank
- Alternate views for climbers, fallers, and a momentum-style Hot Now score
- Filters for category, player count, minimum age, and play time
- Game detail modal linking back to BoardGameGeek
- Static JSON cache for fast GitHub Pages delivery
- Daily GitHub Actions refresh pipeline
- Rank history storage for 30-day movement
- Mobile layout

## Important: current data is demo data

`data/games.json` ships with a small demo dataset so the interface can be developed before BoardGameGeek API approval. Rankings in that demo file must not be treated as current BGG rankings.

The BGG refresh workflow will replace the demo fields with API values once a token is configured.

## BoardGameGeek authorization

BoardGameGeek requires registration and an Application Token for nearly all XML API use.

1. Sign into BoardGameGeek.
2. Visit `https://boardgamegeek.com/applications`.
3. Create a non-commercial application for Board Game Wall unless your intended use is commercial.
4. After approval, create an Application Token.
5. In this GitHub repository go to **Settings → Secrets and variables → Actions**.
6. Create a repository secret named `BGG_TOKEN` containing the token.
7. Open **Actions → Update BoardGameGeek data → Run workflow**.

The token stays in GitHub Actions. It is never sent to visitors' browsers.

## GitHub Pages

The app is intentionally plain HTML/CSS/JavaScript, so no build step is required.

When ready to publish:

1. Make the repository public if needed for your GitHub Pages plan.
2. Open **Settings → Pages**.
3. Under Build and deployment choose **Deploy from a branch**.
4. Select `main` and `/ (root)`.
5. Save.

The expected URL will be:

`https://mattsimoto.github.io/board-game-wall/`

## Data architecture

```text
BGG XML API2
      ↓
GitHub Actions (daily)
      ↓
data/games.json
      +
data/rank-history.json
      ↓
GitHub Pages
      ↓
Browser renders wall + filters
```

This avoids client-side API requests, keeps the BGG token secret, and minimizes API traffic.

## Rank movement

BGG returns current rank rather than the historical series this project needs. Each daily run therefore records the current rank in `data/rank-history.json`. After enough snapshots exist, `rankChange30` becomes a genuine 30-day comparison.

The wall can later expose:

- 24-hour movement
- 7-day movement
- 30-day movement
- biggest climbers
- biggest fallers
- new entries
- all-time high rank

## Scaling beyond the starter set

The current refresh script enriches the IDs already in `games.json`. This keeps request volume low during development. The next data milestone is to wire in BGG's authorized ranks CSV dump, use its top-ranked game IDs as the candidate set, and then enrich those games through XML API2 in batches of no more than 20.

## Public-launch requirement

BoardGameGeek's XML API terms require public-facing applications using the API to credit BoardGameGeek and display the official **Powered by BGG** logo linked to BoardGameGeek. Add the official logo before making the application public.

## Files

```text
index.html                     Page structure
styles.css                     Wall/grid design and responsive layout
app.js                         Filtering, sorting, modal, rendering
assets/box-placeholder.svg     Development placeholder
scripts/fetch_bgg.py           Server-side BGG XML API refresh
.github/workflows/update-bgg.yml
                               Daily refresh automation
data/games.json                Cached data consumed by the website
```

## Intended next steps

1. Register the BGG application and add `BGG_TOKEN`.
2. Run the refresh workflow once to replace placeholder art with real BGG images and current metadata.
3. Add the authorized BGG ranking CSV as the discovery source so the wall can expand to the top 100–500 games.
4. Accumulate rank snapshots.
5. Add 1-day / 7-day / 30-day movement toggles.
6. Add the official Powered by BGG logo.
7. Enable GitHub Pages and make the repository public when ready.
