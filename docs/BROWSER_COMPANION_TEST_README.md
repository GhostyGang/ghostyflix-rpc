GHOSTYFLIX RPC 3.0 TEST · BROWSER COMPANION

This is an optional early test build. It adds Jellyfin Web browsing activity and selected-item details while playback is idle. On a movie, show, season, or episode details page, GhostyFlix can show “Looking at [title] ([year])”, a genre, and artwork. Jellyfin compact 32-character and hyphenated item IDs are supported. Playback sharing remains the established feature.

GET STARTED

1. Close any other GhostyFlix window before opening this test build. Both versions use the same local Discord connection and settings folder.
2. Extract this ZIP to a normal folder you can write to. Keep the app and setup file together.
3. Open GhostyFlix RPC.exe, connect to Jellyfin, and leave Discord desktop running.
4. Follow START HERE - Browser Companion Setup.txt for your browser. The extension folder is named Browser Activity Extension.
5. When asked, approve access only for the Jellyfin Web address you use. Refresh that Jellyfin tab.

This test build is separate from the stable release. It is not delivered through the in-app updater. To return to stable, close the test build and reopen your stable GhostyFlix app.

PRIVACY AND LIMITS

The companion reads the active Jellyfin Web page you explicitly connect and sends its section plus the selected item ID over a loopback-only connection on this PC. GhostyFlix uses its existing authenticated Jellyfin connection to fetch metadata and the primary image. The Jellyfin token stays inside the app and never goes to the extension or Discord. The extension does not read browsing history or use a hosted activity service. Playback activity takes priority over browsing activity.

The app preview loads cover art directly from Jellyfin. Discord needs a reachable poster URL; for private Jellyfin servers, choose public TMDB or OMDb artwork in GhostyFlix if Discord cannot access the Jellyfin image.

Discord and browser behavior are outside GhostyFlix's control. The feature may miss some Jellyfin routes, and Firefox's temporary install is removed when Firefox closes. Please report the browser name/version, Jellyfin version, and steps to reproduce. Remove server addresses and account details from screenshots and logs.
