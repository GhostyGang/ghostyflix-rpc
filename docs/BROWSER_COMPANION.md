# GhostyFlix RPC Browser Companion

The browser companion is optional. It reports the active Jellyfin Web area and, on a selected item's details page, its Jellyfin item ID. GhostyFlix uses the signed-in app connection to fetch that item's title, year, genres, and cover art, then can show **Looking at [title] ([year])** while playback is idle. Other sections show a concise browsing label. It does not read browsing history, and playback takes priority.

The extension sends the item ID only to GhostyFlix on the same computer through a loopback-only connection. Jellyfin credentials stay inside the desktop app and are never sent to the extension or Discord.

Supported areas: Home, Movies, Shows, Music, Search, Playlists, and Collections (Box Sets).

## Local install for testing

Install the app first, connect the same Jellyfin server in GhostyFlix and in your browser, and keep Discord desktop running.

### Chrome, Brave, and Opera GX

1. Open the browser extension manager: `chrome://extensions`, `brave://extensions`, or `opera://extensions`.
2. Enable **Developer mode**.
3. Choose **Load unpacked** and select the `Browser Activity Extension` folder.
4. Open the extension’s options, enter your Jellyfin Web address, and grant access to that site.
5. Refresh Jellyfin Web and keep its tab active.

### Firefox

1. Open `about:debugging#/runtime/this-firefox`.
2. Choose **Load Temporary Add-on** and select `manifest.json` in the `Browser Activity Extension` folder.
3. Open the extension’s options, enter your Jellyfin Web address, and grant access to that site.
4. Refresh Jellyfin Web and keep its tab active.

Firefox removes temporary add-ons when the browser closes. A persistent Firefox install requires Mozilla to sign the add-on. The manifest already includes a Gecko add-on ID and Firefox-compatible background scripts.

## Making install easier for the community

Local development installs require the steps above. Browsers intentionally require a confirmation for extension installs; a local `.bat`, `.zip`, or app button cannot silently install an unpacked extension into an ordinary user profile.

For a polished public install:

- Publish a Chrome Web Store listing for Chrome and Brave.
- Submit a separate listing to Opera Add-ons, or direct Opera users through Opera’s documented Chrome Web Store flow.
- Submit the Firefox package to AMO for signing. A signed XPI can be installed from a direct link with a browser confirmation; an AMO listing also provides update delivery.
- Add browser-specific **Install** buttons in GhostyFlix after store listings are approved. Until then, the Settings tab opens this guide and the local extension folder.

Official distribution references: [Chrome extension distribution](https://developer.chrome.com/docs/extensions/how-to/distribute), [Mozilla self-distribution and signing](https://extensionworkshop.com/documentation/publish/self-distribution/), [Opera extension help](https://help.opera.com/en/latest/customization/), and [Brave extension installation](https://support.brave.app/hc/en-us/articles/360017909112-How-can-I-add-extensions-to-Brave).
