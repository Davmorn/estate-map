"""Nominatim geocoding fallback for sales missing lat/lng."""
import json
import time
from pathlib import Path

import requests

CACHE_PATH = Path(__file__).parent.parent / "data" / "geocache.json"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "estate-map/1.0 (personal project)"}


def _load_cache() -> dict:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.write_text(json.dumps(cache, indent=2))


def geocode_missing(sales: list[dict]) -> list[dict]:
    """Fill lat/lng for any sale that is missing both. Returns updated list."""
    cache = _load_cache()
    updated = False

    for sale in sales:
        if sale.get("lat") and sale.get("lng"):
            continue
        address = sale.get("address", "")
        if not address:
            continue

        if address in cache:
            sale["lat"], sale["lng"] = cache[address]["lat"], cache[address]["lng"]
            continue

        # Rate-limit: Nominatim requires max 1 req/sec
        time.sleep(1)
        try:
            r = requests.get(
                NOMINATIM_URL,
                params={"q": address, "format": "json", "limit": 1},
                headers=HEADERS,
                timeout=10,
            )
            r.raise_for_status()
            results = r.json()
            if results:
                lat = float(results[0]["lat"])
                lng = float(results[0]["lon"])
                sale["lat"] = lat
                sale["lng"] = lng
                cache[address] = {"lat": lat, "lng": lng}
                updated = True
                print(f"  [geocode] {address} -> ({lat:.4f}, {lng:.4f})")
            else:
                print(f"  [geocode] No result for: {address}")
        except Exception as e:
            print(f"  [geocode] Error for {address}: {e}")

    if updated:
        _save_cache(cache)

    return sales
