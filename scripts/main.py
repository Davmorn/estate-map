"""Orchestrate scraping, deduplication, persistence, and map generation."""
import json
from datetime import date, timedelta
from pathlib import Path

import geocode
import generate_map
import scrape_estatesales
import scrape_estatesales_org
import scrape_facebook
import scrape_gsalr

ROOT = Path(__file__).parent.parent
SALES_PATH = ROOT / "data" / "sales.json"
CONFIG_PATH = ROOT / "config.json"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def load_sales() -> list[dict]:
    if SALES_PATH.exists():
        return json.loads(SALES_PATH.read_text())
    return []


def save_sales(sales: list[dict]) -> None:
    SALES_PATH.write_text(json.dumps(sales, indent=2))


def merge(existing: list[dict], new_sales: list[dict]) -> list[dict]:
    """Merge new_sales into existing, keyed by id. Prefer estatesales source."""
    by_id: dict[str, dict] = {s["id"]: s for s in existing}

    for sale in new_sales:
        sid = sale["id"]
        if sid not in by_id:
            by_id[sid] = sale
        else:
            # Keep whichever record has more info (street address wins)
            existing_sale = by_id[sid]
            if sale.get("street") and not existing_sale.get("street"):
                by_id[sid] = sale
            elif sale.get("company") and not existing_sale.get("company"):
                existing_sale["company"] = sale["company"]

    return list(by_id.values())


def deduplicate_cross_source(sales: list[dict]) -> list[dict]:
    """Remove duplicate entries across sources.

    Priority: estatesales > estatesales_org > gsalr.
    Match by: close coordinates OR same normalized title, both with overlapping dates.
    """
    import re

    def overlaps(a: list[str], b: list[str]) -> bool:
        return bool(set(a) & set(b))

    def close(s1: dict, s2: dict) -> bool:
        if not (s1.get("lat") and s2.get("lat")):
            return False
        return (
            abs(s1["lat"] - s2["lat"]) < 0.001
            and abs(s1["lng"] - s2["lng"]) < 0.001
        )

    def normalize_title(t: str) -> str:
        t = re.split(r"\s*[—]\s*|\s+-\s+", t)[0]
        return t.lower().strip()

    def is_duplicate(candidate: dict, reference_list: list[dict]) -> bool:
        c_title = normalize_title(candidate["title"])
        return any(
            overlaps(candidate["dates"], r["dates"])
            and (close(candidate, r) or normalize_title(r["title"]) == c_title)
            for r in reference_list
        )

    es_sales = [s for s in sales if s["source"] == "estatesales"]
    esorg_sales = [s for s in sales if s["source"] == "estatesales_org"]
    fb_sales = [s for s in sales if s["source"] == "facebook"]
    gsalr_sales = [s for s in sales if s["source"] == "gsalr"]

    unique_esorg = [s for s in esorg_sales if not is_duplicate(s, es_sales)]
    primary = es_sales + unique_esorg
    unique_fb = [s for s in fb_sales if not is_duplicate(s, primary)]
    primary = primary + unique_fb
    unique_gsalr = [s for s in gsalr_sales if not is_duplicate(s, primary)]

    return primary + unique_gsalr


def cleanup(sales: list[dict]) -> list[dict]:
    """Remove sales whose last date was more than 30 days ago."""
    cutoff = str(date.today() - timedelta(days=30))
    kept = []
    removed = 0
    for sale in sales:
        last_date = max(sale["dates"]) if sale.get("dates") else ""
        if last_date >= cutoff:
            kept.append(sale)
        else:
            removed += 1
    if removed:
        print(f"  [cleanup] Removed {removed} expired sale(s)")
    return kept


def main() -> None:
    config = load_config()
    region = config["region"]
    state = region["estatesales_state"]
    cities = region["estatesales_cities"]
    gsalr_city = region.get("gsalr_primary_city", cities[0])
    region_name = region["name"]
    fb_pages = region.get("facebook_pages", [])

    print("Scraping EstateSales.net...")
    es_sales = scrape_estatesales.scrape(state, cities)

    print("Scraping EstateSales.org...")
    esorg_sales = scrape_estatesales_org.scrape(state, cities)

    print("Scraping GSALR...")
    gsalr_sales = scrape_gsalr.scrape(state, gsalr_city)

    print("Scraping Facebook...")
    fb_sales = scrape_facebook.scrape(fb_pages)

    print("Geocoding missing coordinates...")
    all_new = geocode.geocode_missing(es_sales + esorg_sales + gsalr_sales + fb_sales)

    print("Loading existing sales...")
    existing = load_sales()

    print("Merging...")
    merged = merge(existing, all_new)
    merged = deduplicate_cross_source(merged)
    merged = cleanup(merged)

    print(f"  Total unique sales: {len(merged)}")
    save_sales(merged)

    print("Generating map...")
    generate_map.generate(merged, region_name)

    print("Done.")


if __name__ == "__main__":
    main()
