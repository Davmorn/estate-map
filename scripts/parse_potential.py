"""Parse potential Facebook sales using Claude Haiku."""
import hashlib
import json
import os
import re
from pathlib import Path

import anthropic

ROOT = Path(__file__).parent.parent
POTENTIAL_PATH = ROOT / "data" / "potential_sales.json"

_SYSTEM = """\
You are a structured data extractor for estate sale announcements.
Given a Facebook post from an estate sale company, extract the following fields as JSON.
If a field cannot be determined, use null.

Output format (JSON only, no explanation):
{
  "title": "<short descriptive title, max 80 chars>",
  "dates": ["YYYY-MM-DD", ...],
  "street": "<street address only, e.g. '123 N Main St'>",
  "city": "<city name>",
  "state": "<2-letter state code>",
  "zip": "<5-digit zip or null>"
}

Rules:
- dates must be a list of individual YYYY-MM-DD strings, one per day of the sale
- If the year is not stated, assume 2026
- If a date range is given (e.g. May 29-30), expand it to individual days
- street must be the street portion only (no city/state/zip)
- Return null for any field you cannot confidently extract
- If the post is not about an estate sale or has no date/location, return all fields as null
"""


def _url_to_id(url: str) -> str:
    m = re.search(r"/(\d{10,})", url)
    if m:
        return f"facebook-{m.group(1)}"
    return f"facebook-{hashlib.md5(url.encode()).hexdigest()[:12]}"


def load_potential() -> list[dict]:
    if POTENTIAL_PATH.exists():
        return json.loads(POTENTIAL_PATH.read_text())
    return []


def clear_potential() -> None:
    POTENTIAL_PATH.write_text("[]")


def parse(potential: list[dict]) -> list[dict]:
    if not potential:
        return []

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  [facebook] ANTHROPIC_API_KEY not set; skipping")
        return []

    client = anthropic.Anthropic(api_key=api_key)
    results = []

    for entry in potential:
        raw = entry.get("raw_text", "").strip()
        if not raw:
            continue

        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
                messages=[
                    {
                        "role": "user",
                        "content": f"Company: {entry.get('company', '')}\n\nPost:\n{raw}",
                    }
                ],
            )
            text = response.content[0].text.strip()
            # Strip markdown fences if model wraps output
            text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
            parsed = json.loads(text)
        except Exception as e:
            print(f"  [facebook] Parse error ({entry.get('source', '?')}): {e}")
            continue

        dates = parsed.get("dates") or []
        street = parsed.get("street") or ""
        city = parsed.get("city") or ""

        # Require at least a date and some location signal to be useful
        if not dates or not (street or city):
            continue

        state = parsed.get("state") or "ID"
        zip_code = parsed.get("zip") or ""
        address_parts = [p for p in [street, city, f"{state} {zip_code}".strip()] if p]
        address = ", ".join(address_parts)

        results.append({
            "id": _url_to_id(entry.get("source", "")),
            "source": "facebook",
            "title": parsed.get("title") or f"{entry.get('company', 'Facebook')} sale",
            "company": entry.get("company", ""),
            "address": address,
            "street": street,
            "city": city,
            "state": state,
            "zip": zip_code,
            "dates": dates,
            "url": entry.get("source", ""),
            "lat": None,
            "lng": None,
        })

    print(f"  [facebook] {len(results)}/{len(potential)} potential sale(s) parsed successfully")
    return results
