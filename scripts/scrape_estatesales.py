"""Scrape estate sales from estatesales.net using embedded NgRx state JSON."""
import json
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}
BASE_URL = "https://www.estatesales.net"


def _parse_dt(dt_obj: dict | None) -> str | None:
    if not dt_obj:
        return None
    return dt_obj.get("_value")  # ISO string in UTC


def _extract_ngrx_sales(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script"):
        txt = script.string or ""
        if "NGRX_STATE" not in txt:
            continue
        start = txt.find('{"NGRX_STATE":{')
        if start < 0:
            continue
        data = json.loads(txt[start:].rstrip(";"))
        return data["NGRX_STATE"]["ui"]["sales"]["saleRows"]
    return {}


def scrape(state: str, cities: list[str]) -> list[dict]:
    seen_ids: set[int] = set()
    results: list[dict] = []

    for city in cities:
        url = f"{BASE_URL}/{state}/{city}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"  [estatesales] Failed {url}: {e}")
            time.sleep(1)
            continue

        sale_rows = _extract_ngrx_sales(r.text)
        for sale_id_str, sale in sale_rows.items():
            sale_id = int(sale_id_str)
            if sale_id in seen_ids:
                continue
            seen_ids.add(sale_id)

            city_name = sale.get("cityName", "")
            zip_code = sale.get("postalCodeNumber", "")
            state_code = sale.get("stateCode", state)
            street = sale.get("address", "").strip()
            address = (
                f"{street}, {city_name}, {state_code} {zip_code}".strip(", ")
                if street
                else f"{city_name}, {state_code} {zip_code}".strip()
            )

            dates = sorted(
                {
                    d["localStartDate"]["_value"][:10]
                    for d in sale.get("dates", [])
                    if d.get("localStartDate")
                }
            )

            lat = sale.get("latitude")
            lng = sale.get("longitude")

            sale_url = (
                f"{BASE_URL}/{state_code}/{city_name}/{zip_code}/{sale_id}"
            )

            results.append(
                {
                    "id": f"es-{sale_id}",
                    "source": "estatesales",
                    "title": sale.get("name", ""),
                    "company": sale.get("orgName", ""),
                    "address": address,
                    "street": street,
                    "city": city_name,
                    "state": state_code,
                    "zip": zip_code,
                    "dates": dates,
                    "url": sale_url,
                    "lat": lat,
                    "lng": lng,
                }
            )

        time.sleep(0.5)

    print(f"  [estatesales] Found {len(results)} sales across {len(cities)} cities")
    return results
