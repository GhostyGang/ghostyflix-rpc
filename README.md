<p align="center">
  <img src="assets/ghostyflix-hero.png" alt="GhostyFlix RPC — Jellyfin Rich Presence" width="100%">
</p>

<h1 align="center">GhostyFlix RPC</h1>

<p align="center"><strong>Your Jellyfin. Your Discord. One clean little link.</strong></p>

<p align="center">A Windows companion that turns Jellyfin playback into a polished Discord Rich Presence.</p>

<p align="center">
  <a href="https://github.com/emoacid1-cmd/ghostyflix-rpc/releases/latest"><img alt="Latest stable release" src="https://img.shields.io/github/v/release/emoacid1-cmd/ghostyflix-rpc?label=stable%20release&color=ff7628"></a>
  <a href="https://github.com/emoacid1-cmd/ghostyflix-rpc/actions/workflows/windows-release.yml"><img alt="Windows build" src="https://github.com/emoacid1-cmd/ghostyflix-rpc/actions/workflows/windows-release.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="MIT license" src="https://img.shields.io/badge/license-MIT-17191E.svg"></a>
</p>

<p align="center">
  <a href="https://github.com/emoacid1-cmd/ghostyflix-rpc/releases/latest">Download</a> ·
  <a href="https://github.com/emoacid1-cmd/ghostyflix-rpc/releases/tag/v2.0.16-browser-test.2">Optional 3.0 Test build</a> ·
  <a href="docs/USER_GUIDE.md">Setup guide</a> ·
  <a href="CHANGELOG.md">Release notes</a> ·
  <a href="docs/BROWSER_COMPANION.md">Browser companion</a>
</p>

GhostyFlix connects to your Jellyfin account, watches for playback, and shares the title, artwork, and progress through Discord’s desktop client. Your Jellyfin connection and preferences stay on your computer.

## The good stuff

- Sign in with Jellyfin Quick Connect or an API key.
- Share movies, episodes, and music with poster art and playback progress.
- Show movie year, genres, paused state, elapsed time, and time remaining.
- Add compact IMDb and trailer buttons to movie and episode activities.
- Choose Jellyfin, TMDB, or OMDb for posters; use MusicBrainz and Cover Art Archive for album art.
- Filter which Jellyfin libraries and media types can appear.
- Preview the activity inside the app, tune the orange play/pause badge, and keep GhostyFlix in the system tray.
- Update from public GitHub stable releases without replacing the app by hand.

Discord controls the exact card layout. GhostyFlix supplies the activity text, timing, images, and buttons.

### Example activity

```text
Watching Jellyfin
The Last Star (2025)
2025 · Sci-Fi
01:21 ━━━━━━━━━━━ 02:08
Paused · 64% watched · 47 min left
```

The artwork and progress bar are rendered by Discord; the exact layout can vary by client and screen size.

## Get connected

1. Download and open the latest **stable** Windows build from [Releases](https://github.com/emoacid1-cmd/ghostyflix-rpc/releases/latest).
2. Enter your Jellyfin server’s base address, such as `http://192.168.1.20:8096` (leave off `/web`).
3. Choose **Get a Quick Connect code**. On a signed-in Jellyfin device, open the user menu → **Quick Connect**, enter the code, and approve it.
4. Leave GhostyFlix and Discord desktop running, then play something in Jellyfin.

Quick Connect codes expire after five minutes. If your server does not offer Quick Connect, use the API key sign-in option. The [setup guide](docs/USER_GUIDE.md) has screenshots-free, step-by-step instructions and troubleshooting.

## Optional browser companion — early test

The browser companion can show **Browsing Home**, **Browsing Movies**, **Browsing Playlists**, and other Jellyfin sections when playback is idle. Collections may be labelled **Box Sets** in Jellyfin.

> **Experimental:** this companion is an early preview. Jellyfin Web routes and browser extension rules can change, so some views or browser versions may not be detected consistently. Playback Rich Presence remains the primary feature.

The extension supports Chrome, Brave, Opera GX, and Firefox. Local installation requires a few manual steps: Chromium browsers use **Load unpacked**; Firefox loads it temporarily unless Mozilla signs the add-on. A store listing is needed for direct install buttons. Read the [browser companion guide](docs/BROWSER_COMPANION.md) before installing.

The companion only reads the Jellyfin site you approve, sends activity to GhostyFlix over a local connection, and does not read browser history. Playback always takes priority.

For the optional preview, get the [3.0 Test pre-release](https://github.com/emoacid1-cmd/ghostyflix-rpc/releases/tag/v2.0.16-browser-test.2) and follow its included setup sheet. This is a separate test build, not an in-app update. Close the stable app before opening the test build because both use the same local settings and Discord connection.

## Artwork keys

Jellyfin artwork works without an extra key. TMDB and OMDb keys are optional and saved locally.

- [Create a TMDB API key](https://www.themoviedb.org/settings/api)
- [Get an OMDb API key](https://www.omdbapi.com/apikey.aspx)

For OMDb, enter the key itself or a complete request URL, such as `https://www.omdbapi.com/?i=tt3896198&apikey=YOUR_KEY`. MusicBrainz and Cover Art Archive artwork does not require an API key.

GhostyFlix includes TMDB’s approved logo and attribution in artwork settings. This product uses the TMDB API but is not endorsed or certified by TMDB. See [TMDB attribution requirements](https://www.themoviedb.org/about/logos-attribution).

## Stable updates and test builds

The in-app updater checks the latest full GitHub release, verifies the SHA-256 digest, then installs the stable Windows build. Browser companion test builds are published separately as **pre-releases** and are not offered by the normal updater. A pre-release can be installed manually without replacing the current stable release.

## Privacy

- Jellyfin address, sign-in token, and optional provider keys are stored in `%APPDATA%\GhostyFlix RPC\ghostyflix_rpc.ini`. This file is plain text; do not share it.
- Playback is read from Jellyfin and sent to Discord’s local desktop client. Your Discord privacy settings decide who can see it.
- Discord needs to reach the selected poster URL. If Jellyfin is only available on your home network, use an external artwork provider for images that Discord cannot load.
- Logs may include connection details. Redact personal information before sharing them.

## Build from source

Use Windows, Python 3.12 or newer, and [uv](https://docs.astral.sh/uv/):

```powershell
uv sync --locked --extra gui --no-dev
uv run pyinstaller --noconfirm main.spec
```

The executable is written to `dist/GhostyFlix RPC.exe`. To run the app from source, use `uv run python -m ghostyflix_rpc`.

## Contributing

Bug reports and focused improvements are welcome. Remove server addresses, usernames, tokens, Quick Connect codes, and API keys from logs and screenshots before posting. See [CONTRIBUTING.md](CONTRIBUTING.md).
