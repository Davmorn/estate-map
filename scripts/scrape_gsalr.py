"""Scrape estate sales from gsalr.com for a given city/state."""
import re
import time

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# Months for date parsing
_MONTHS = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
    "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
}

_DATE_RE = re.compile(
    r"(\w{3}),\s+(\w{3})\s+(\d{1,2}),\s+(\d{4})"
    r"(?:\s*[–-]+\s*(?:\w{3},\s+)?(\w{3})\s+(\d{1,2}),\s+(\d{4}))?"
)


def _parse_date_range(text: str) -> list[str]:
    """Return list of YYYY-MM-DD strings for start..end (inclusive, daily)."""
    text = text.replace("\U0001f4c5", "").strip()  # strip calendar emoji
    m = _DATE_RE.search(text)
    if not m:
        return []
    _, s_mon, s_day, s_yr, e_mon, e_day, e_yr = m.groups()
    if not e_mon:
        e_mon, e_day, e_yr = s_mon, s_day, s_yr

    from datetime import date, timedelta
    start = date(int(s_yr), int(_MONTHS[s_mon]), int(s_day))
    end = date(int(e_yr), int(_MONTHS[e_mon]), int(e_day))
    days = []
    cur = start
    while cur <= end:
        days.append(str(cur))
        cur += timedelta(days=1)
    return days


def scrape(state: str, primary_city: str) -> list[dict]:
    city_slug = primary_city.lower().replace(" ", "-")
    state_slug = state.lower()
    url = f"https://gsalr.com/garage-sales-{city_slug}-{state_slug}.html"

    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"  [gsalr] Failed {url}: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    listings = soup.find_all("div", class_="l-data")

    results = []
    for listing in listings:
        sale_id = listing.get("data-id", "")
        lat_str = listing.get("data-lat", "")
        lon_str = listing.get("data-lon", "")

        try:
            lat = float(lat_str) if lat_str else None
            lng = float(lon_str) if lon_str else None
        except ValueError:
            lat = lng = None

        title_a = listing.select_one(".title a.sale-title")
        title = title_a.get_text(strip=True) if title_a else ""
        sale_url = title_a.get("href", "") if title_a else ""

        city_el = listing.select_one("[itemprop=addressLocality]")
        state_el = listing.select_one("[itemprop=addressRegion]")
        zip_el = listing.select_one("[itemprop=postalCode]")
        street_el = listing.select_one("[itemprop=streetAddress]")

        city_name = city_el.get_text(strip=True) if city_el else ""
        state_code = state_el.get_text(strip=True) if state_el else state.upper()
        zip_code = zip_el.get_text(strip=True) if zip_el else ""
        # Remove ss-icon spans (private-use Unicode icons) before extracting text
        if street_el:
            for icon in street_el.find_all(class_="ss-icon"):
                icon.decompose()
        street = street_el.get_text(strip=True) if street_el else ""

        address = (
            f"{street}, {city_name}, {state_code} {zip_code}".strip(", ")
            if street
            else f"{city_name}, {state_code} {zip_code}".strip()
        )

        # Find date text in location paragraphs
        dates: list[str] = []
        loc_div = listing.select_one(".location")
        if loc_div:
            for p in loc_div.find_all("p"):
                txt = p.get_text(strip=True)
                if any(mon in txt for mon in _MONTHS):
                    dates = _parse_date_range(txt)
                    break

        if not sale_id or not title:
            continue

        results.append(
            {
                "id": f"gsalr-{sale_id}",
                "source": "gsalr",
                "title": title,
                "company": "",
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

    print(f"  [gsalr] Found {len(results)} sales from {url}")
    return results
