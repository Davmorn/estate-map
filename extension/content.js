// Injected on demand — reads DOM, makes no network calls.
(function () {
  const company = document.querySelector('h1')?.innerText?.trim() || '';
  const articles = document.querySelectorAll('[role="article"]');
  const posts = [];

  for (const article of articles) {
    const text = article.innerText?.trim() || '';
    if (text.length < 40) continue;
    if (!/\d/.test(text)) continue;
    posts.push({ raw_text: text, company });
  }

  return posts;
})();
