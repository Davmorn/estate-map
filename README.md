# Estate Sale Map

**[View the map →](https://davmorn.github.io/estate-map)**

Weekend estate sales in the Boise Metro area, updated every Thursday evening.

## How it works

A GitHub Actions workflow runs weekly and:
1. Scrapes [EstateSales.net](https://www.estatesales.net) and [GSALR](https://gsalr.com) for upcoming sales in the Boise Metro
2. Deduplicates listings that appear on both sites
3. Generates a [Leaflet](https://leafletjs.com) map and commits it to this repo
4. GitHub Pages serves the map from the `docs/` folder

Sale data lives in `data/sales.json` and is cleaned up automatically — entries older than 30 days are removed each run.

## Configuration

Edit `config.json` to change the region or cities searched:

```json
{
  "region": {
    "name": "Boise Metro",
    "estatesales_state": "ID",
    "estatesales_cities": ["Boise", "Meridian", "Nampa", "Caldwell", "Eagle", "Garden-City"],
    "gsalr_primary_city": "Boise"
  }
}
```

## Running locally

```bash
uv run python scripts/main.py
```

## Chrome Extension — Facebook Collector

Some local estate sale companies post only on Facebook and don't appear on the aggregator sites. The extension lets you manually collect those posts and feed them into the weekly pipeline.

### Installation

1. Open `chrome://extensions` in Chrome
2. Enable **Developer mode** (toggle in the top-right)
3. Click **Load unpacked** and select the `extension/` folder in this repo
4. Click the extension icon and choose **Settings** (or right-click → Options)
5. Enter your **GitHub Personal Access Token** (needs `Contents: Read and write` on this repo), your GitHub username, and the repo name (`estate-map`)

### Weekly usage

The extension keeps a list of Facebook company pages you've previously scanned. Each week:

1. Click the extension icon — pages not yet scanned this week show an ⚠ indicator
2. Click **Start (N due)** — a new tab opens on the first page
3. Scroll down on the Facebook page to load posts
4. Click the extension icon again — popup shows the page name and a **Scan** button
5. Click **Scan** — posts are pushed to `data/potential_sales.json` and the tab automatically navigates to the next page
6. Repeat until the popup shows "All caught up this week!"

Use **Skip** to skip a page without scanning.

### Adding a new page

Navigate to any Facebook company page and click the extension icon. The popup will show a **Grab Posts** button under the detected page name. Scanning it once adds it permanently to your weekly list.

### How it connects to the pipeline

Posts collected by the extension are stored in `data/potential_sales.json`. The Thursday GitHub Actions run picks these up, uses Claude Haiku to extract structured sale details, and merges them into the map alongside the aggregator results. `potential_sales.json` is cleared after each run.

The list of tracked Facebook pages is stored in `data/facebook_pages.json` — edit this file directly to add or remove pages, or to share your list with someone else running the extension.

## Future ideas

- Email digest sent Thursday evening with the sale list and map link
