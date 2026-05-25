"""Generate a self-contained Leaflet.js map HTML file from sales data."""
import json
from pathlib import Path

DOCS_PATH = Path(__file__).parent.parent / "docs"


def generate(sales: list[dict], region_name: str) -> None:
    DOCS_PATH.mkdir(exist_ok=True)
    output = DOCS_PATH / "index.html"

    # Only include sales with coordinates
    mappable = [s for s in sales if s.get("lat") and s.get("lng")]

    sales_json = json.dumps(mappable, indent=2)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Estate Sales — {region_name}</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: system-ui, sans-serif; }}
    #map {{ height: 100vh; width: 100%; }}
    #info-bar {{
      position: fixed; top: 10px; left: 50%; transform: translateX(-50%);
      z-index: 1000; background: rgba(255,255,255,0.95);
      padding: 8px 16px; border-radius: 20px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.2);
      font-size: 14px; white-space: nowrap;
    }}
    .popup-title {{ font-weight: 600; font-size: 14px; margin-bottom: 4px; }}
    .popup-company {{ color: #666; font-size: 12px; margin-bottom: 4px; }}
    .popup-address {{ font-size: 13px; margin-bottom: 4px; }}
    .popup-dates {{ font-size: 12px; color: #444; margin-bottom: 6px; }}
    .popup-link {{ font-size: 12px; }}
    .popup-link a {{ color: #0066cc; text-decoration: none; }}
    .popup-link a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <div id="info-bar">Estate Sales — {region_name} &nbsp;|&nbsp; <span id="count"></span></div>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const sales = {sales_json};

    const map = L.map('map').setView([43.6150, -116.2023], 11);

    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19,
    }}).addTo(map);

    document.getElementById('count').textContent =
      sales.length + ' sale' + (sales.length !== 1 ? 's' : '');

    function formatDates(dates) {{
      if (!dates || !dates.length) return '';
      const fmt = d => {{
        const [yr, mo, dy] = d.split('-');
        const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
        return months[parseInt(mo)-1] + ' ' + parseInt(dy);
      }};
      if (dates.length === 1) return fmt(dates[0]);
      const first = fmt(dates[0]);
      const last = fmt(dates[dates.length-1]);
      return first === last ? first : first + ' – ' + last;
    }}

    sales.forEach(sale => {{
      const marker = L.marker([sale.lat, sale.lng]).addTo(map);
      const dateStr = formatDates(sale.dates);
      const companyLine = sale.company
        ? `<div class="popup-company">🏢 ${{sale.company}}</div>` : '';
      const addressLine = sale.address
        ? `<div class="popup-address">📍 ${{sale.address}}</div>` : '';
      marker.bindPopup(`
        <div class="popup-title">${{sale.title}}</div>
        ${{companyLine}}
        ${{addressLine}}
        <div class="popup-dates">📅 ${{dateStr}}</div>
        <div class="popup-link"><a href="${{sale.url}}" target="_blank">View listing →</a></div>
      `, {{ maxWidth: 280 }});
    }});
  </script>
</body>
</html>
"""

    output.write_text(html)
    print(f"  [map] Wrote {len(mappable)} markers to {output}")
