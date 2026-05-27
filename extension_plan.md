# Chrome Extension Plan: Facebook Estate Sale Collector

## Purpose

A Chrome extension that lets the user navigate to a Facebook company page for a local estate sale business, click a button, and automatically send the visible posts to `data/potential_sales.json` in the estate-map GitHub repo. The downstream pipeline (`scripts/parse_potential.py` + Claude Haiku) handles structured extraction on the next Thursday run.

---

## User Flow

1. User navigates to a Facebook company page (e.g. `https://www.facebook.com/BoiseEstateSales`)
2. User scrolls down to load as many posts as desired
3. User clicks the extension popup icon
4. Popup shows the detected company name and a "Grab Posts" button
5. User clicks "Grab Posts"
6. Extension extracts all visible post texts, filters lightly, sends to GitHub
7. Popup shows a success message: "Sent 6 posts to potential_sales.json"

---

## Architecture

```
extension/
├── manifest.json          # MV3 manifest
├── popup.html             # Extension popup UI
├── popup.js               # Popup logic — calls content script, calls GitHub
├── content.js             # Injected into facebook.com — reads the DOM
└── settings.html          # One-time settings page for GitHub PAT + repo
└── settings.js
```

No build step required. Plain JS, no frameworks, no bundler.

---

## Component Details

### `manifest.json`

- Manifest V3
- `permissions`: `activeTab`, `storage`, `scripting`
- `host_permissions`: `https://www.facebook.com/*`, `https://api.github.com/*`
- `action`: popup is `popup.html`
- `options_page`: `settings.html`
- Content script (`content.js`) is NOT auto-injected — it is injected on demand via `chrome.scripting.executeScript` from `popup.js` so it only runs when the user clicks the button

### `popup.html` / `popup.js`

Displays:
- Detected page name (read from content script result)
- "Grab Posts" button (disabled if not on a Facebook page)
- Status message area

On button click:
1. Calls `chrome.scripting.executeScript` to run `content.js` in the active tab
2. Receives array of `{ raw_text, company }` objects back
3. Loads GitHub PAT + repo settings from `chrome.storage.sync`
4. Calls `pushToGitHub(posts, company, sourceUrl)`
5. Shows success/error message

### `content.js`

Injected into the active Facebook tab. Responsibilities:
- Detect company name from the page (see DOM notes below)
- Find all post containers currently rendered in the DOM
- Extract text content from each post
- Return array of `{ raw_text: string, company: string }` to the popup

Does NOT make any network calls. Pure DOM read.

**Facebook DOM strategy:**

Facebook's DOM is React-rendered and unstable. Use a layered approach:
1. Primary: `document.querySelectorAll('[role="article"]')` — Facebook uses this ARIA role on post containers
2. For each article, grab `innerText` of the full element (captures all nested text)
3. Company name: grab `document.querySelector('h1')?.innerText` (page header)
4. Filter out articles shorter than 40 characters (likely UI chrome, not posts)

This will over-collect — that is fine. The downstream Haiku parser discards non-sale posts.

### `popup.js` — GitHub API logic

Function `pushToGitHub(entries, sourceUrl)`:

1. **GET** `https://api.github.com/repos/{owner}/{repo}/contents/data/potential_sales.json`
   - Auth header: `Authorization: Bearer {PAT}`
   - Response contains `content` (base64) and `sha`
2. Decode base64 → parse JSON → existing array
3. Build new entries:
   ```json
   {
     "source": "{sourceUrl}",
     "company": "{company name from page}",
     "raw_text": "{post text}",
     "scraped_at": "{YYYY-MM-DD today}"
   }
   ```
4. Deduplicate: skip entries whose `raw_text` already exists in the current file (exact match)
5. Append new entries to existing array
6. **PUT** back:
   ```json
   {
     "message": "Add Facebook potential sales from {company}",
     "content": "{base64-encoded updated JSON}",
     "sha": "{sha from GET}"
   }
   ```
7. On success: display count of new entries added
8. On 409 conflict (someone else updated the file): retry once with a fresh GET

### `settings.html` / `settings.js`

Simple form with three fields saved to `chrome.storage.sync`:
- **GitHub PAT** — token with `contents: write` scope on the estate-map repo
- **Repo owner** — e.g. `davmorn`
- **Repo name** — e.g. `estate-map`

Accessible via right-click → "Options" or a settings link in the popup.

---

## Data Written to GitHub

Each entry appended to `data/potential_sales.json`:

```json
{
  "source": "https://www.facebook.com/BoiseEstateSales",
  "company": "Boise Estate Sales",
  "raw_text": "🏡 ESTATE SALE ALERT! Join us this weekend at 4215 W Overland...",
  "scraped_at": "2026-05-26"
}
```

The `source` field is the company page URL (not a specific post URL), since the extension runs at the page level, not per-post.

---

## Light Pre-filter in `content.js`

Before returning posts to the popup, skip any article whose text does not contain at least one digit (eliminates pure-text announcements with no date or address signal). This reduces noise without needing real parsing in the extension.

---

## Error Handling

| Situation | Behavior |
|-----------|----------|
| Not on facebook.com | "Grab Posts" button is disabled with a note |
| PAT not set | Popup shows "Configure settings first" with a link |
| GitHub API 401 | "Authentication failed — check your PAT in Settings" |
| GitHub API 409 | Retry once with fresh GET/PUT |
| GitHub API other error | Show status code + raw message |
| Zero posts found after filter | "No posts found — try scrolling to load more" |

---

## Installation (Development)

1. Open `chrome://extensions`
2. Enable "Developer mode"
3. Click "Load unpacked" → select the `extension/` folder
4. Click the extension icon → open Settings → enter PAT, owner, repo name
5. Navigate to a Facebook company page and click "Grab Posts"

---

## What This Extension Does NOT Do

- No login to Facebook — runs entirely within the user's existing authenticated browser session
- No Claude / AI calls — extraction is pure DOM reading
- No per-post URLs — source is always the company page URL
- No scheduling — fully manual, user-triggered
- No Firefox support (MV3 content script injection approach is Chrome-specific here)

---

## Dependencies on the Pipeline

- `data/potential_sales.json` must exist in the repo (even as `[]`) before first use
- `scripts/parse_potential.py` reads and clears this file during the Thursday GitHub Actions run
- `ANTHROPIC_API_KEY` must be set as a GitHub Actions secret for the Haiku parsing step
