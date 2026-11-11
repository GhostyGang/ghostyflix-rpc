# GhostyFlix RPC 3.0 Test .3 — Browser Companion

This optional pre-release adds item details to the experimental Jellyfin browser companion. It does not change the stable app or its in-app update channel.

## What's new

- On a Jellyfin movie, show, season, or episode details page, Discord can show **Looking at [title] ([year])**, a genre, and the configured artwork.
- The browser companion now recognizes both Jellyfin's compact 32-character item IDs and hyphenated UUIDs. This fixes details pages that previously fell back to a generic “Viewing GhostyFlix” activity.
- Browsing Home, Movies, Shows, Music, Search, Playlists, and Collections/Box Sets remains available while playback is idle. Active playback always takes priority.
- Browser companion version 0.2.1 is included as a Chromium/Opera ZIP and an unsigned Firefox XPI.

## How it works

The extension reads the active, approved Jellyfin Web page and sends its section and selected item ID to GhostyFlix through a loopback-only connection on the same PC. GhostyFlix validates the item ID, then uses the user's existing authenticated Jellyfin connection to fetch metadata and the primary image. The Jellyfin token never leaves the desktop app and is not sent to the extension or Discord. No browsing history is read, and no cloud activity service is used.

The app preview can display the image fetched directly from Jellyfin. Discord must be able to reach the selected artwork URL; for a private Jellyfin server, choose a public TMDB or OMDb artwork source if Discord cannot load the Jellyfin image.

## Install and test

1. Download and extract **GhostyFlix-RPC-3.0-TEST-Browser-Companion.zip**.
2. Read **TEST BUILD - READ BEFORE USE.txt**, then follow **START HERE - Browser Companion Setup.txt**.
3. If updating an unpacked extension, use the included **Browser Activity Extension** folder as its source and click **Reload** in the browser's extension manager. Refresh Jellyfin Web after reloading.
4. Keep the test app connected to the same Jellyfin server, leave playback idle, and open a movie or show details page.

This is an early optional test. Browser routes may vary by Jellyfin Web version, and Firefox's included XPI is unsigned. The test build is not offered by the normal in-app updater. Close other GhostyFlix instances before testing because they share local settings and Discord access.

The app executable, combined test bundle, extension packages, and license are accompanied by `SHA256SUMS.txt` for integrity checks.
