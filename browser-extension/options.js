const input = document.querySelector('#server');
const status = document.querySelector('#status');

chrome.storage.local.get('jellyfinUrl').then(({ jellyfinUrl }) => { input.value = jellyfinUrl || ''; });

document.querySelector('#save').addEventListener('click', async () => {
  status.textContent = '';
  let url;
  try {
    url = new URL(input.value.trim());
    if (!['http:', 'https:'].includes(url.protocol)) throw new Error();
  } catch (_) {
    status.textContent = 'Enter a valid http:// or https:// Jellyfin Web address.';
    return;
  }
  const origin = url.origin;
  const granted = await chrome.permissions.request({ origins: [`${origin}/*`] });
  if (!granted) {
    status.textContent = 'Site permission was not granted. You can change this in the extension settings.';
    return;
  }
  await chrome.storage.local.set({ jellyfinUrl: input.value.trim(), jellyfinOrigin: origin });
  const result = await chrome.runtime.sendMessage({ type: 'configure-origin', origin });
  status.textContent = result?.ok ? 'Connected. Open or refresh Jellyfin Web to start sharing its page.' : `Could not configure page tracking: ${result?.error || 'unknown error'}`;
});
