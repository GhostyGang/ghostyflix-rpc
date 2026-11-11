const BRIDGE_URL = 'http://127.0.0.1:47861/v1/activity';
const SCRIPT_ID = 'ghostyflix-jellyfin-page-monitor';

async function registerForOrigin(origin) {
  try { await chrome.scripting.unregisterContentScripts({ ids: [SCRIPT_ID] }); } catch (_) {}
  if (!origin) return;
  await chrome.scripting.registerContentScripts([{
    id: SCRIPT_ID,
    matches: [`${origin}/*`],
    js: ['content.js'],
    runAt: 'document_idle',
    allFrames: false,
    persistAcrossSessions: true
  }]);
}

chrome.runtime.onInstalled.addListener(async () => {
  const { jellyfinOrigin } = await chrome.storage.local.get('jellyfinOrigin');
  if (jellyfinOrigin) await registerForOrigin(jellyfinOrigin);
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === 'configure-origin') {
    registerForOrigin(message.origin).then(() => sendResponse({ ok: true }))
      .catch(error => sendResponse({ ok: false, error: String(error) }));
    return true;
  }
  if (message?.type === 'jellyfin-activity') {
    if (!sender.tab?.active || message.server !== message.expectedOrigin) return;
    fetch(BRIDGE_URL, {
      method: 'POST',
      // text/plain avoids an unnecessary CORS preflight; the loopback bridge
      // still parses and validates the JSON body.
      headers: { 'Content-Type': 'text/plain;charset=UTF-8' },
      body: JSON.stringify({
        page: message.page,
        title: message.title,
        item_id: message.itemId,
        server: message.server
      }),
      cache: 'no-store'
    }).catch(() => {});
  }
});
