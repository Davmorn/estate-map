// ─── Helpers ──────────────────────────────────────────────────────────────────

function canonicalUrl(url) {
  try {
    const u = new URL(url);
    return (u.origin + u.pathname).replace(/\/$/, '');
  } catch { return url; }
}

function urlMatchesPage(tabUrl, pageUrl) {
  const base = canonicalUrl(pageUrl);
  const tab  = canonicalUrl(tabUrl);
  return tab === base || tab.startsWith(base + '/');
}

function isSameISOWeek(dateStr) {
  if (!dateStr) return false;
  const mondayOf = (dt) => {
    const d = new Date(typeof dt === 'string' ? dt + 'T00:00:00' : dt);
    d.setHours(0, 0, 0, 0);
    const day = d.getDay();
    d.setDate(d.getDate() - (day === 0 ? 6 : day - 1));
    return d.getTime();
  };
  return mondayOf(dateStr) === mondayOf(new Date());
}

function today() { return new Date().toISOString().slice(0, 10); }

function fmtDate(dateStr) {
  if (!dateStr) return '';
  const d = new Date(dateStr + 'T00:00:00');
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

// ─── Storage ──────────────────────────────────────────────────────────────────

const getSettings    = () => chrome.storage.sync.get(['pat', 'owner', 'repo']);
const getScanHistory = async () => (await chrome.storage.local.get('scanHistory')).scanHistory ?? {};
const getSession     = async () => (await chrome.storage.local.get('session')).session ?? null;
const setSession     = (s) => chrome.storage.local.set({ session: s });
const clearSession   = () => chrome.storage.local.remove('session');

async function markScanned(url) {
  const h = await getScanHistory();
  h[canonicalUrl(url)] = today();
  await chrome.storage.local.set({ scanHistory: h });
}

// ─── GitHub ───────────────────────────────────────────────────────────────────

function ghHeaders(pat) {
  return {
    Authorization: `Bearer ${pat}`,
    Accept: 'application/vnd.github+json',
    'Content-Type': 'application/json',
  };
}

async function ghGet(path, { pat, owner, repo }) {
  const res = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/contents/${path}`,
    { headers: ghHeaders(pat) },
  );
  if (!res.ok) {
    const b = await res.json().catch(() => ({}));
    throw Object.assign(new Error(b.message || res.statusText), { status: res.status });
  }
  const d = await res.json();
  return { content: JSON.parse(atob(d.content.replace(/\n/g, ''))), sha: d.sha };
}

async function ghPut(path, content, sha, message, { pat, owner, repo }) {
  const res = await fetch(
    `https://api.github.com/repos/${owner}/${repo}/contents/${path}`,
    {
      method: 'PUT',
      headers: ghHeaders(pat),
      body: JSON.stringify({
        message,
        content: btoa(unescape(encodeURIComponent(JSON.stringify(content, null, 2)))),
        sha,
      }),
    },
  );
  if (!res.ok) {
    const b = await res.json().catch(() => ({}));
    throw Object.assign(new Error(b.message || res.statusText), { status: res.status });
  }
}

async function loadPagesList(settings) {
  if (!settings.pat) return [];
  try {
    const { content } = await ghGet('data/facebook_pages.json', settings);
    return Array.isArray(content) ? content : [];
  } catch { return []; }
}

// Fire-and-forget: add page to facebook_pages.json if not already there.
async function ensurePageInList(name, url, settings) {
  if (!settings.pat) return;
  const canonical = canonicalUrl(url);
  try {
    const { content: pages, sha } = await ghGet('data/facebook_pages.json', settings);
    if (pages.some(p => canonicalUrl(p.url) === canonical)) return;
    pages.push({ name, url: canonical });
    await ghPut('data/facebook_pages.json', pages, sha, `Add ${name} to Facebook pages list`, settings);
  } catch { /* non-critical */ }
}

async function pushPosts(entries, sourceUrl, settings, retrying = false) {
  const { content: existing, sha } = await ghGet('data/potential_sales.json', settings);
  const existingTexts = new Set(existing.map(e => e.raw_text));
  const company = entries[0]?.company || '';

  const newEntries = entries
    .filter(e => !existingTexts.has(e.raw_text))
    .map(e => ({ source: sourceUrl, company: e.company, raw_text: e.raw_text, scraped_at: today() }));

  if (newEntries.length === 0) return 0;

  try {
    await ghPut(
      'data/potential_sales.json',
      [...existing, ...newEntries],
      sha,
      `Add Facebook potential sales from ${company}`,
      settings,
    );
  } catch (err) {
    if (err.status === 409 && !retrying) return pushPosts(entries, sourceUrl, settings, true);
    throw err;
  }
  return newEntries.length;
}

// ─── UI helpers ───────────────────────────────────────────────────────────────

const $ = id => document.getElementById(id);

function showView(name) {
  for (const v of ['home', 'scan', 'open'])
    $(`view-${v}`).style.display = v === name ? '' : 'none';
}

function setStatus(id, msg, cls = '') {
  const el = $(id);
  el.textContent = msg;
  el.className = 'status ' + cls;
}

function errMsg(err) {
  return err.status === 401 ? 'Auth failed — check PAT in Settings' : `Error: ${err.message}`;
}

// ─── Rendering ────────────────────────────────────────────────────────────────

function renderPageList(pages, scanHistory) {
  const list = $('home-list');
  if (pages.length === 0) {
    list.innerHTML = '<div class="empty">No pages tracked yet — scan any Facebook page to add it.</div>';
    return;
  }

  const sorted = [...pages].sort((a, b) => {
    const ad = isSameISOWeek(scanHistory[canonicalUrl(a.url)]);
    const bd = isSameISOWeek(scanHistory[canonicalUrl(b.url)]);
    if (ad !== bd) return ad ? 1 : -1;
    return a.name.localeCompare(b.name);
  });

  list.innerHTML = '';
  for (const page of sorted) {
    const last = scanHistory[canonicalUrl(page.url)];
    const done = isSameISOWeek(last);
    const row  = document.createElement('div');
    row.className = 'page-row';

    const nameEl = document.createElement('span');
    nameEl.className = 'page-name';
    nameEl.textContent = page.name;
    nameEl.title = page.url;

    const meta = document.createElement('span');
    meta.className = 'page-meta ' + (done ? 'done' : 'due');
    meta.textContent = last ? `${fmtDate(last)} ${done ? '✓' : '⚠'}` : '⚠';

    row.appendChild(nameEl);
    row.appendChild(meta);
    list.appendChild(row);
  }
}

function updateStartBtn(pages, scanHistory) {
  const due = pages.filter(p => !isSameISOWeek(scanHistory[canonicalUrl(p.url)])).length;
  const btn = $('start-btn');
  if (due > 0) {
    btn.disabled = false;
    btn.textContent = `Start (${due} due)`;
  } else {
    btn.disabled = true;
    btn.textContent = pages.length > 0 ? 'All caught up this week!' : 'Start';
  }
  return due;
}

// ─── Home view ────────────────────────────────────────────────────────────────

async function showHomeView(settings, statusMsg = '', statusCls = '') {
  showView('home');
  setStatus('home-status', statusMsg, statusCls);

  if (!settings.pat) {
    $('home-list').innerHTML = '<div class="empty">Open Settings to enter your GitHub PAT.</div>';
    $('start-btn').disabled = true;
    return;
  }

  const [pages, scanHistory] = await Promise.all([loadPagesList(settings), getScanHistory()]);

  renderPageList(pages, scanHistory);
  const due = updateStartBtn(pages, scanHistory);

  if (due > 0) {
    $('start-btn').onclick = () => startSession(pages, scanHistory, settings);
  }

  // Ad-hoc section: if currently on a Facebook page
  const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (activeTab?.url?.startsWith('https://www.facebook.com/')) {
    try {
      const r = await chrome.scripting.executeScript({
        target: { tabId: activeTab.id },
        func: () => document.querySelector('h1')?.innerText?.trim() || '',
      });
      const name = r?.[0]?.result || activeTab.url.split('/')[3] || 'This page';
      $('adhoc-name').textContent = name;
      $('adhoc-section').style.display = '';
      $('adhoc-btn').onclick = () => doAdhocScan(activeTab, name, settings, pages, scanHistory);
    } catch { /* page not ready */ }
  }
}

// ─── Ad-hoc scan ──────────────────────────────────────────────────────────────

async function doAdhocScan(activeTab, detectedName, settings, pages, scanHistory) {
  $('adhoc-btn').disabled = true;
  setStatus('adhoc-status', 'Scanning…');

  try {
    const r     = await chrome.scripting.executeScript({ target: { tabId: activeTab.id }, files: ['content.js'] });
    const posts = r?.[0]?.result ?? [];

    if (posts.length === 0) {
      setStatus('adhoc-status', 'No posts found — scroll to load more.', 'error');
      $('adhoc-btn').disabled = false;
      return;
    }

    const company = posts[0]?.company || detectedName;
    setStatus('adhoc-status', `Sending ${posts.length} posts…`);
    const added = await pushPosts(posts, activeTab.url, settings);
    await markScanned(activeTab.url);
    ensurePageInList(company, activeTab.url, settings);

    setStatus('adhoc-status', `✓ ${added} new post(s) added`, 'success');

    const newHistory = await getScanHistory();
    renderPageList(pages, newHistory);
    updateStartBtn(pages, newHistory);
  } catch (err) {
    setStatus('adhoc-status', errMsg(err), 'error');
    $('adhoc-btn').disabled = false;
  }
}

// ─── Session: start ───────────────────────────────────────────────────────────

async function startSession(pages, scanHistory, settings) {
  const queue = pages
    .filter(p => !isSameISOWeek(scanHistory[canonicalUrl(p.url)]))
    .map(p => canonicalUrl(p.url));
  if (queue.length === 0) return;

  const tab = await chrome.tabs.create({ url: queue[0] });
  await setSession({ queue, currentIndex: 0, tabId: tab.id });
  window.close();
}

// ─── Session: show ────────────────────────────────────────────────────────────

async function showSessionView(session, settings) {
  const { queue, currentIndex, tabId } = session;
  const currentUrl = queue[currentIndex];
  const progress   = `${currentIndex + 1} of ${queue.length}`;

  const pages    = await loadPagesList(settings);
  const entry    = pages.find(p => canonicalUrl(p.url) === canonicalUrl(currentUrl));
  const pageName = entry?.name || currentUrl;

  const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const onTarget = activeTab?.id === tabId && urlMatchesPage(activeTab.url ?? '', currentUrl);

  if (onTarget) {
    showView('scan');
    $('scan-name').textContent     = pageName;
    $('scan-progress').textContent = progress;
    setStatus('scan-status', '');
    $('scan-btn').disabled = false;
    $('skip-btn').disabled = false;
    $('scan-btn').onclick = () => doSessionScan(session, pageName, activeTab, settings);
    $('skip-btn').onclick = () => advance(session, settings);
  } else {
    showView('open');
    $('open-name').textContent     = pageName;
    $('open-progress').textContent = progress;
    $('open-btn').onclick = async () => {
      await chrome.tabs.update(tabId, { url: currentUrl, active: true });
      window.close();
    };
    $('open-skip-btn').onclick = () => advance(session, settings);
  }
}

// ─── Session: scan ────────────────────────────────────────────────────────────

async function doSessionScan(session, pageName, activeTab, settings) {
  $('scan-btn').disabled = true;
  $('skip-btn').disabled = true;
  setStatus('scan-status', 'Scanning…');

  try {
    const r     = await chrome.scripting.executeScript({ target: { tabId: activeTab.id }, files: ['content.js'] });
    const posts = r?.[0]?.result ?? [];

    if (posts.length === 0) {
      setStatus('scan-status', 'No posts found — scroll to load more, then try again.', 'error');
      $('scan-btn').disabled = false;
      $('skip-btn').disabled = false;
      return;
    }

    const company = posts[0]?.company || pageName;
    setStatus('scan-status', `Sending ${posts.length} posts…`);
    const added = await pushPosts(posts, activeTab.url, settings);
    await markScanned(session.queue[session.currentIndex]);
    ensurePageInList(company, session.queue[session.currentIndex], settings);

    setStatus('scan-status', `✓ ${added} new post(s) added`, 'success');
    await new Promise(r => setTimeout(r, 900));
    await advance(session, settings);
  } catch (err) {
    setStatus('scan-status', errMsg(err), 'error');
    $('scan-btn').disabled = false;
    $('skip-btn').disabled = false;
  }
}

// ─── Session: advance / finish ────────────────────────────────────────────────

async function advance(session, settings) {
  const nextIndex = session.currentIndex + 1;

  if (nextIndex >= session.queue.length) {
    await clearSession();
    await showHomeView(settings, 'All caught up this week!', 'success');
    return;
  }

  await setSession({ ...session, currentIndex: nextIndex });
  await chrome.tabs.update(session.tabId, { url: session.queue[nextIndex], active: true });
  window.close();
}

// ─── Init ─────────────────────────────────────────────────────────────────────

async function init() {
  for (const id of ['sl-home', 'sl-scan', 'sl-open'])
    $(id).addEventListener('click', () => chrome.runtime.openOptionsPage());

  const settings = await getSettings();
  const session  = await getSession();

  if (session) {
    let tabExists = false;
    try { await chrome.tabs.get(session.tabId); tabExists = true; } catch {}
    if (tabExists) { await showSessionView(session, settings); return; }
    await clearSession();
  }

  await showHomeView(settings);
}

init();
