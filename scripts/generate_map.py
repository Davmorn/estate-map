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
    body {{ font-family: system-ui, sans-serif; height: 100vh; display: flex; flex-direction: column; }}
    #header {{
      background: #fff; border-bottom: 1px solid #e0e0e0;
      padding: 10px 16px; font-size: 14px; font-weight: 600;
      display: flex; align-items: center; gap: 12px; flex-shrink: 0;
    }}
    #header span {{ font-weight: 400; color: #666; }}
    #weekend-select {{
      font-size: 13px; padding: 3px 8px; border: 1px solid #ccc;
      border-radius: 4px; cursor: pointer; background: #fff; color: #333;
      margin-left: auto;
    }}
    #body {{ display: flex; flex: 1; overflow: hidden; }}
    #map {{ flex: 1; }}
    #list-panel {{
      width: 320px; flex-shrink: 0; overflow-y: auto;
      border-left: 1px solid #e0e0e0; background: #fafafa;
    }}
    .list-item {{
      padding: 12px 14px; border-bottom: 1px solid #e8e8e8;
      cursor: pointer; transition: background 0.15s;
    }}
    .list-item:hover {{ background: #f0f4ff; }}
    .list-item.active {{ background: #e8eeff; border-left: 3px solid #3366cc; }}
    .list-title {{ font-weight: 600; font-size: 13px; margin-bottom: 3px; line-height: 1.3; }}
    .list-dates {{ font-size: 12px; color: #c0392b; margin-bottom: 2px; }}
    .list-location {{ font-size: 12px; color: #555; margin-bottom: 4px; }}
    .list-company {{ font-size: 11px; color: #888; }}
    .list-link {{ font-size: 11px; margin-top: 4px; }}
    .list-link a {{ color: #0066cc; text-decoration: none; }}
    .list-link a:hover {{ text-decoration: underline; }}
    .popup-title {{ font-weight: 600; font-size: 14px; margin-bottom: 4px; }}
    .popup-company {{ color: #666; font-size: 12px; margin-bottom: 4px; }}
    .popup-address {{ font-size: 13px; margin-bottom: 4px; }}
    .popup-dates {{ font-size: 12px; color: #444; margin-bottom: 6px; }}
    .popup-link {{ font-size: 12px; }}
    .popup-link a {{ color: #0066cc; text-decoration: none; }}
    .popup-link a:hover {{ text-decoration: underline; }}
    .no-sales {{ padding: 24px 14px; color: #999; font-size: 13px; text-align: center; }}
  </style>
</head>
<body>
  <div id="header">
    Estate Sales — {region_name}
    <span id="count"></span>
    <select id="weekend-select"></select>
  </div>
  <div id="body">
    <div id="map"></div>
    <div id="list-panel"></div>
  </div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const sales = {sales_json};

    const map = L.map('map').setView([43.6150, -116.2023], 11);

    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      maxZoom: 19,
    }}).addTo(map);

    // Weekend selector — options: 1 past + current + 2 future Saturdays
    const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

    function addDays(dateStr, n) {{
      const d = new Date(dateStr + 'T12:00:00');
      d.setDate(d.getDate() + n);
      return d.toISOString().slice(0, 10);
    }}

    function thisSaturday() {{
      const d = new Date();
      d.setHours(12, 0, 0, 0);
      const day = d.getDay();
      if (day === 0) d.setDate(d.getDate() - 1);
      else d.setDate(d.getDate() + (6 - day));
      return d.toISOString().slice(0, 10);
    }}

    function weekendLabel(satStr) {{
      const [, mo, dy] = satStr.split('-');
      return MONTHS[parseInt(mo) - 1] + ' ' + parseInt(dy);
    }}

    const currentSat = thisSaturday();
    const sel = document.getElementById('weekend-select');
    [-1, 0, 1, 2].forEach((offset, i) => {{
      const satStr = addDays(currentSat, offset * 7);
      const opt = document.createElement('option');
      opt.value = satStr;
      opt.textContent = weekendLabel(satStr);
      if (i === 1) opt.selected = true;
      sel.appendChild(opt);
    }});

    function formatDates(dates) {{
      if (!dates || !dates.length) return '';
      const fmt = d => {{
        const [, mo, dy] = d.split('-');
        return MONTHS[parseInt(mo)-1] + ' ' + parseInt(dy);
      }};
      if (dates.length === 1) return fmt(dates[0]);
      const first = fmt(dates[0]);
      const last = fmt(dates[dates.length-1]);
      return first === last ? first : first + ' – ' + last;
    }}

    const markers = {{}};
    const listItems = {{}};
    let activeId = null;

    function setActive(id) {{
      if (activeId && listItems[activeId]) listItems[activeId].classList.remove('active');
      activeId = id;
      if (listItems[id]) listItems[id].classList.add('active');
    }}

    // Build all markers and list items; markers start off-map (added by filterWeekend)
    sales.forEach(sale => {{
      const marker = L.marker([sale.lat, sale.lng]);
      markers[sale.id] = marker;
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
      marker.on('click', () => setActive(sale.id));

      const item = document.createElement('div');
      item.className = 'list-item';
      item.innerHTML = `
        <div class="list-title">${{sale.title}}</div>
        <div class="list-dates">📅 ${{dateStr}}</div>
        <div class="list-location">📍 ${{sale.city || sale.address}}</div>
        ${{sale.company ? `<div class="list-company">${{sale.company}}</div>` : ''}}
        <div class="list-link"><a href="${{sale.url}}" target="_blank" onclick="event.stopPropagation()">View listing →</a></div>
      `;
      item.addEventListener('click', () => {{
        map.setView([sale.lat, sale.lng], 14);
        marker.openPopup();
        setActive(sale.id);
      }});
      listItems[sale.id] = item;
      document.getElementById('list-panel').appendChild(item);
    }});

    function filterWeekend(satStr) {{
      // Show sales with any date in [Thu, Sun] of the selected Saturday's weekend
      const from = addDays(satStr, -2);
      const to   = addDays(satStr, 1);
      let count = 0;

      sales.forEach(sale => {{
        const visible = sale.dates && sale.dates.some(d => d >= from && d <= to);
        if (visible) {{
          if (!map.hasLayer(markers[sale.id])) markers[sale.id].addTo(map);
          listItems[sale.id].style.display = '';
          count++;
        }} else {{
          if (map.hasLayer(markers[sale.id])) map.removeLayer(markers[sale.id]);
          listItems[sale.id].style.display = 'none';
        }}
      }});

      const panel = document.getElementById('list-panel');
      let msg = panel.querySelector('.no-sales');
      if (count === 0) {{
        if (!msg) {{ msg = document.createElement('div'); msg.className = 'no-sales'; panel.appendChild(msg); }}
        msg.textContent = 'No sales found for this weekend.';
      }} else if (msg) {{
        msg.remove();
      }}

      document.getElementById('count').textContent = count + ' sale' + (count !== 1 ? 's' : '');
    }}

    sel.addEventListener('change', () => {{ map.closePopup(); filterWeekend(sel.value); }});
    filterWeekend(sel.value);
  </script>
</body>
</html>
"""

    output.write_text(html)
    print(f"  [map] Wrote {len(mappable)} markers to {output}")
