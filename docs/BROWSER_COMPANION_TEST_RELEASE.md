GhostyFlix RPC 3.0 Test is an optional preview of the Jellyfin browser companion.

## What's included

- Browsing activity for Jellyfin Home, Movies, Shows, Music, Search, Playlists, and Collections/Box Sets when playback is idle.
- A combined test bundle with the Windows app, browser extension folder, and setup guide.
- Separate Chromium-compatible ZIP and unsigned Firefox XPI packages.

## Start here

Download **GhostyFlix-RPC-3.0-TEST-Browser-Companion.zip**, extract it, open `TEST BUILD - READ BEFORE USE.txt`, then follow `START HERE - Browser Companion Setup.txt`.

This is an early optional test, not a stable release. Browser route detection and extension behavior can vary by Jellyfin and browser version. Use the stable release for the established playback experience. This test build is not offered by GhostyFlix's in-app updater. Close any other GhostyFlix window before launching it, since both builds share local settings and Discord access.

The extension only reports activity from the Jellyfin site you approve to the GhostyFlix app on the same computer. It does not read browser history or use a remote activity service. Firefox's included XPI is unsigned; use **Load Temporary Add-on** for local testing, or submit it to Mozilla for signing before persistent distribution.

The app executable, combined test bundle, extension packages, and license are accompanied by `SHA256SUMS.txt` for integrity checks.
