"""Scrape estate sale posts from public Instagram profiles."""
import os
import re
from datetime import date, datetime, timedelta, timezone

import instaloader

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

_DATE_RE = re.compile(
    rf"\b({_MON_PATTERN})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s*(\d{{4}}))?",
    re.IGNORECASE,
)

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
    if (end - start).days > 7:
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
    zip_code = m.group(6) or ""
    street = f"{num} {name} {stype}".strip()
    address = f"{street}, {city}, {state} {zip_code}".strip(", ") if city else street
    return street, city, state, zip_code, address


def _build_loader() -> instaloader.Instaloader:
    loader = instaloader.Instaloader(
        quiet=True,
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
    )
    username = os.environ.get("INSTAGRAM_USERNAME", "").strip()
    password = os.environ.get("INSTAGRAM_PASSWORD", "").strip()
    if username and password:
        try:
            loader.login(username, password)
            print(f"  [instagram] Logged in as {username}")
        except instaloader.exceptions.BadCredentialsException:
            print("  [instagram] Login failed (bad credentials); continuing without login")
        except instaloader.exceptions.TwoFactorAuthRequiredException:
            print("  [instagram] Login failed (2FA required); continuing without login")
        except Exception as e:
            print(f"  [instagram] Login failed ({e}); continuing without login")
    else:
        print("  [instagram] No credentials set; fetching without login")
    return loader


def scrape(profiles: list[str]) -> list[dict]:
    if not profiles:
        return []

    loader = _build_loader()
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=CUTOFF_DAYS)
    results = []

    for username in profiles:
        try:
            profile = instaloader.Profile.from_username(loader.context, username)
        except instaloader.exceptions.ProfileNotExistsException:
            print(f"  [instagram] Profile not found: {username}")
            continue
        except Exception as e:
            print(f"  [instagram] Could not load profile {username}: {e}")
            continue

        count = 0
        try:
            for post in profile.get_posts():
                if post.date_utc < cutoff.replace(tzinfo=None):
                    break
                caption = post.caption or ""
                post_year = post.date_utc.year
                dates = _parse_dates(caption, post_year)
                if not dates:
                    continue
                street, city, state, zip_code, address = _parse_address(caption)
                title = caption.split("\n")[0][:120].strip() or f"{username} sale"
                results.append({
                    "id": f"instagram-{post.shortcode}",
                    "source": "instagram",
                    "title": title,
                    "company": profile.full_name or username,
                    "address": address,
                    "street": street,
                    "city": city,
                    "state": state,
                    "zip": zip_code,
                    "dates": dates,
                    "url": f"https://www.instagram.com/p/{post.shortcode}/",
                    "lat": None,
                    "lng": None,
                })
                count += 1
        except Exception as e:
            print(f"  [instagram] Error reading posts for {username}: {e}")

        print(f"  [instagram] {username}: {count} sale post(s) found")

    return results
