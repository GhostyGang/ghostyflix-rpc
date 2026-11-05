# GhostyFlix RPC Browser Companion

This optional extension reports the current Jellyfin Web section, and a page title when available, to GhostyFlix on the same PC. Playback takes priority. Supported sections include Home, Movies, Shows, Music, Search, Playlists, and Collections/Box Sets. It does not read browser history or contact a cloud service.

## Chrome, Brave, and Opera GX

1. Open the browser’s extension manager: `chrome://extensions`, `brave://extensions`, or `opera://extensions`.
2. Turn on **Developer mode**.
3. Choose **Load unpacked** and select this `Browser Activity Extension` folder.
4. Open the extension’s options, enter the Jellyfin Web address, and approve access to that site.
5. Keep GhostyFlix open and connected to the same Jellyfin server, then refresh the Jellyfin tab.

## Firefox

For a local test, open `about:debugging#/runtime/this-firefox`, choose **Load Temporary Add-on**, and select this folder’s `manifest.json`. Open the extension’s options and connect the Jellyfin Web address. A temporary add-on is removed when Firefox closes.

For a persistent Firefox install, the add-on must be signed by Mozilla. The included cross-browser manifest has an add-on ID and can be submitted to [addons.mozilla.org](https://addons.mozilla.org/developers/) for signing. A signed XPI can then be offered as an install link; Firefox will still ask the user to confirm.

## Why there is no silent one-click install

Browsers deliberately require approval before adding extensions. For Chrome and Brave, a Chrome Web Store listing gives users a direct install page; Opera can use an Opera Add-ons listing; Firefox can use a signed AMO listing or signed XPI. Until those listings are approved, loading the local folder is a short manual step. GhostyFlix can open this guide and the extension folder from Settings.

The bridge is loopback-only and accepts activity from browser-extension origins. It validates the Jellyfin origin against the server configured in GhostyFlix.
