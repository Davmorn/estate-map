"""Scrape estate sales from estatesales.org."""
import re
import time

import requests
from bs4 import BeautifulSoup, NavigableString

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}
BASE_URL = "https://www.estatesales.org"

_MONTHS = {
    "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04",
    "May": "05", "Jun": "06", "Jul": "07", "Aug": "08",
    "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
}

_DATE_RE = re.compile(r"\w{3},\s+(\w{3})\s+(\d{1,2}),\s+(\d{4})")
_ID_RE = re.compile(r"-(\d+)$")
_LOC_HREF_RE = re.compile(r"^/estate-sales/\w+/[\w-]+/\d{5}$")


def _parse_date(text: str) -> str | None:
    m = _DATE_RE.search(text)
    if not m:
        return None
    mon, day, yr = m.groups()
    if mon not in _MONTHS:
        return None
    return f"{yr}-{_MONTHS[mon]}-{int(day):02d}"


def _fetch_detail(url: str) -> tuple[str, list[str]]:
    """Return (street_address, sorted_dates) from a listing detail page."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except requests.RequestException:
        return "", []

    soup = BeautifulSoup(r.text, "html.parser")

    # Dates: <li> items with "Mon, MMM DD, YYYY ..." format
    dates = set()
    for li in soup.find_all("li"):
        d = _parse_date(li.get_text())
        if d:
            dates.add(d)

    # Street address: text node immediately after <h4>Sale Address</h4>
    street = ""
    h4 = soup.find("h4", string=lambda t: t and "Sale Address" in t)
    if h4:
        for sib in h4.next_siblings:
            if isinstance(sib, NavigableString) and sib.strip():
                street = sib.strip()
                break

    return street, sorted(dates)


def scrape(state: str, cities: list[str]) -> list[dict]:
    seen_ids: set[str] = set()
    results: list[dict] = []

    for city in cities:
        city_slug = city.lower().replace(" ", "-")
        state_slug = state.lower()
        url = f"{BASE_URL}/estate-sales/{state_slug}/{city_slug}"

        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"  [estatesales_org] Failed {url}: {e}")
            time.sleep(1)
            continue

        soup = BeautifulSoup(r.text, "html.parser")

        for h3 in soup.find_all("h3"):
            a = h3.find("a", href=True)
            if not a or not a["href"].startswith("/estate-sales/"):
                continue

            href = a["href"]
            m = _ID_RE.search(href)
            if not m:
                continue
            sale_id = m.group(1)
            if sale_id in seen_ids:
                continue
            seen_ids.add(sale_id)

            title = a.get_text(strip=True)
            listing_url = BASE_URL + href

            card = h3.parent

            company = ""
            company_a = card.find(
                "a", href=lambda h: h and h.startswith("/estate-sale-companies/")
            )
            if company_a:
                company = company_a.get_text(strip=True)

            city_name, zip_code = "", ""
            loc_a = card.find("a", href=_LOC_HREF_RE.match)
            if loc_a:
                parts = loc_a["href"].rstrip("/").split("/")
                zip_code = parts[-1]
                city_name = parts[-2].replace("-", " ").strip().title()

            street, dates = _fetch_detail(listing_url)
            time.sleep(0.5)

            if not dates:
                continue

            address = (
                f"{street}, {city_name}, {state.upper()} {zip_code}".strip(", ")
                if street
                else f"{city_name}, {state.upper()} {zip_code}".strip()
            )

            results.append(
                {
                    "id": f"esorg-{sale_id}",
                    "source": "estatesales_org",
                    "title": title,
                    "company": company,
                    "address": address,
                    "street": street,
                    "city": city_name,
                    "state": state.upper(),
                    "zip": zip_code,
                    "dates": dates,
                    "url": listing_url,
                    "lat": None,
                    "lng": None,
                }
            )

        time.sleep(0.5)

    print(f"  [estatesales_org] Found {len(results)} sales across {len(cities)} cities")
    return results
