const patEl = document.getElementById('pat');
const ownerEl = document.getElementById('owner');
const repoEl = document.getElementById('repo');
const saveBtn = document.getElementById('save-btn');
const statusEl = document.getElementById('status');

chrome.storage.sync.get(['pat', 'owner', 'repo'], ({ pat, owner, repo }) => {
  if (pat) patEl.value = pat;
  if (owner) ownerEl.value = owner;
  if (repo) repoEl.value = repo;
});

saveBtn.addEventListener('click', () => {
  const pat = patEl.value.trim();
  const owner = ownerEl.value.trim();
  const repo = repoEl.value.trim();

  if (!pat || !owner || !repo) {
    statusEl.textContent = 'All three fields are required.';
    statusEl.className = 'error';
    return;
  }

  chrome.storage.sync.set({ pat, owner, repo }, () => {
    statusEl.textContent = 'Saved.';
    statusEl.className = 'success';
  });
});
