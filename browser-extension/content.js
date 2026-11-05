(() => {
  const KEY = '__ghostyflixBrowserActivity';
  if (window[KEY]) return;
  window[KEY] = true;

  function classify() {
    const path = `${location.pathname}${location.hash}`.toLowerCase();
    if (/details\.html|\/details\/|details\?id=/.test(path)) return 'details';
    if (/search/.test(path)) return 'search';
    if (/playlists?|playlistview/.test(path)) return 'playlists';
    if (/collections?|boxsets?|boxsetview/.test(path)) return 'collections';
    if (/music|albums|artists/.test(path)) return 'music';
    if (/movies/.test(path)) return 'movies';
    if (/tv|series|shows/.test(path)) return 'shows';
    return 'home';
  }

  function titleForPage() {
    const title = (document.title || '').replace(/\s*[-|·]\s*jellyfin.*$/i, '').trim();
    if (!title || /^jellyfin$/i.test(title)) return '';
    return title.slice(0, 100);
  }

  function report() {
    if (document.visibilityState !== 'visible') return;
    const page = classify();
    const title = ['details', 'playlists', 'collections'].includes(page) ? titleForPage() : '';
    chrome.runtime.sendMessage({
      type: 'jellyfin-activity', page, title,
      server: location.origin,
      expectedOrigin: location.origin
    });
  }

  report();
  setInterval(report, 2500);
  window.addEventListener('hashchange', report);
  window.addEventListener('popstate', report);
  document.addEventListener('visibilitychange', report);
})();
