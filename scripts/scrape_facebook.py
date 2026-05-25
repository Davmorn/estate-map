"""Scrape estate sale posts from public Facebook pages."""
import re
from datetime import date, datetime, timedelta
from pathlib import Path

try:
    from facebook_scraper import get_posts
    _HAS_LIB = True
except ImportError:
    _HAS_LIB = False

_COOKIES_FILE = Path(__file__).parent.parent / "facebook_cookies.txt"

CUTOFF_DAYS = 30

_MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}

_MON_PATTERN = "|".join(sorted(_MONTHS, key=len, reverse=True))

# "May 30", "May 30th", "May 30, 2025"
_DATE_RE = re.compile(
    rf"\b({_MON_PATTERN})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s*(\d{{4}}))?",
    re.IGNORECASE,
)

# Street address with optional city/state/zip
_ADDR_RE = re.compile(
    r"\b(\d{1,5})\s+"
    r"(?:[NSEW](?:orth|outh|ast|est)?\.?\s+)?"
    r"([A-Za-z0-9][A-Za-z0-9\s]{1,30}?)\s+"
    r"(St(?:reet)?|Ave(?:nue)?|Rd|Road|Dr(?:ive)?|Blvd|Boulevard|"
    r"Ln|Lane|Way|Ct|Court|Pl(?:ace)?|Cir(?:cle)?|Pkwy|Parkway|"
    r"Ter(?:race)?|Hwy|Highway)\.?"
    r"(?:,?\s*([A-Za-z][A-Za-z\s]{1,20}?),?\s*(ID|Idaho)\s*(\d{5}(?:-\d{4})?))?",
    re.IGNORECASE,
)


def _parse_dates(text: str, post_year: int) -> list[str]:
    matches = list(_DATE_RE.finditer(text))
    parsed = []
    for m in matches:
        mon = _MONTHS.get(m.group(1).lower())
        if not mon:
            continue
        day = int(m.group(2))
        yr = int(m.group(3)) if m.group(3) else post_year
        try:
            parsed.append(date(yr, int(mon), day))
        except ValueError:
            continue
    if not parsed:
        return []
    start, end = min(parsed), max(parsed)
    if (end - start).days > 7:  # >7 days span is likely a bad parse; cap at 3
        end = start + timedelta(days=2)
    result = []
    cur = start
    while cur <= end:
        result.append(str(cur))
        cur += timedelta(days=1)
    return result


def _parse_address(text: str) -> tuple[str, str, str, str, str]:
    m = _ADDR_RE.search(text)
    if not m:
        return "", "", "", "", ""
    num = m.group(1)
    name = m.group(2).strip()
    stype = m.group(3)
    city = (m.group(4) or "").strip().title()
    state = "ID" if m.group(5) else ""
    zip_code = (m.group(6) or "").strip()
    street = f"{num} {name} {stype}".strip()
    parts = [street]
    if city:
        parts.append(city)
    if state:
        parts.append(state)
    if zip_code:
        parts.append(zip_code)
    return ", ".join(parts), street, city, state, zip_code


def _page_name(url: str) -> str:
    return url.rstrip("/").split("/")[-1]


def scrape(page_urls: list[str]) -> list[dict]:
    if not _HAS_LIB:
        print("  [facebook] facebook-scraper not installed, skipping")
        return []
    if not page_urls:
        return []

    cookies = str(_COOKIES_FILE) if _COOKIES_FILE.exists() else None
    if not cookies:
        print(
            "  [facebook] No facebook_cookies.txt found — Facebook requires login to "
            "read page posts. Export cookies from a logged-in browser session "
            "(e.g. with the 'Get cookies.txt LOCALLY' extension) and save as "
            "facebook_cookies.txt in the project root (it is gitignored). "
            "In GitHub Actions, set a FB_COOKIES secret (base64-encoded) and add a "
            "step to decode it: "
            "echo \"$FB_COOKIES\" | base64 -d > facebook_cookies.txt"
        )
        return []

    cutoff = date.today() - timedelta(days=CUTOFF_DAYS)
    results = []

    for url in page_urls:
        name = _page_name(url)
        print(f"  [facebook] Scraping {name}...")
        try:
            kwargs: dict = {"pages": 5, "timeout": 30, "cookies": cookies}
            count = 0
            for post in get_posts(name, **kwargs):
                post_time = post.get("time")
                if post_time is None:
                    continue
                post_date = post_time.date() if isinstance(post_time, (datetime, date)) and hasattr(post_time, "date") else date.today()

                if post_date < cutoff:
                    break

                text = (post.get("text") or post.get("post_text") or "").strip()
                if not text:
                    continue
                if not re.search(r"\bestate\s+sale\b|\byard\s+sale\b|\bmoving\s+sale\b", text, re.IGNORECASE):
                    continue

                dates = _parse_dates(text, post_date.year)
                if not dates:
                    continue

                address, street, city, state, zip_code = _parse_address(text)
                post_id = post.get("post_id") or ""
                company = post.get("username") or name

                results.append({
                    "id": f"fb-{post_id}",
                    "source": "facebook",
                    "title": f"Estate Sale — {city or name}",
                    "company": company,
                    "address": address,
                    "street": street,
                    "city": city,
                    "state": state or "ID",
                    "zip": zip_code,
                    "dates": dates,
                    "url": post.get("post_url") or url,
                    "lat": None,
                    "lng": None,
                })
                count += 1

            print(f"  [facebook] Found {count} sale posts from {name}")
        except Exception as e:
            print(f"  [facebook] Error scraping {name}: {e}")

    return results
