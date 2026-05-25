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

## Future ideas

- Email digest sent Thursday evening with the sale list and map link
- Facebook scraping fallback for local companies not listed on the aggregator sites
