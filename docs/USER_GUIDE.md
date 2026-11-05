# GhostyFlix RPC · Quick setup and user guide

Start with the quick setup below. The later sections explain artwork, preferences, browser activity, and troubleshooting.

## Requirements

- Windows for the published executable.
- A Jellyfin server reachable from the computer running GhostyFlix.
- Discord desktop open on that same computer. Browser and mobile Discord do not provide the local Rich Presence connection used by the app.
- Activity sharing enabled in Discord's privacy settings.

## Quick setup

1. Download the latest **stable** Windows app from [GitHub Releases](https://github.com/emoacid1-cmd/ghostyflix-rpc/releases/latest) and open it.
2. In **Connect**, enter your Jellyfin server’s base address, such as `http://192.168.1.20:8096`. Leave off `/web`.
3. Choose **Get a Quick Connect code**.
4. On a device already signed into Jellyfin, open the user menu → **Quick Connect**, enter the displayed code, and approve it.
5. Leave GhostyFlix and Discord desktop running, then play media using the connected Jellyfin account.

The code expires after five minutes. Request a fresh one if it expires. Quick Connect must be enabled in the Jellyfin server settings.

Use the server's base address, such as `http://192.168.1.20:8096`; do not add `/web`. If GhostyFlix cannot request a code, the Connect panel now displays the server error and the most likely fix. Check **Dashboard → General → Enable Quick Connect**. If the server is behind a reverse proxy, confirm the `/QuickConnect` API route is forwarded to Jellyfin.

When upgrading from an earlier GhostyFlix RPC release, the app reuses the Jellyfin sign-in and preferences already saved on this PC. It may ask you to sign in again if the saved session has expired or the server no longer accepts it.

If Quick Connect is unavailable, choose **API key**, enter your Jellyfin username, and paste a key created from the Jellyfin Dashboard's **API Keys** page. API keys can grant broad access to a server; use one only on a trusted computer. GhostyFlix saves the resulting sign-in token locally so the connection can resume on the next launch.

## Choose libraries

Connect to Jellyfin, then use **Choose libraries** to set a blacklist or whitelist:

- **Blacklist** includes every library except the checked ones.
- **Whitelist** includes only the checked libraries.
- Leave the selection empty to include all libraries.

## Artwork and activity

Open **Artwork & Activity** to choose what appears in Discord.

### Movie and show posters

Choose Jellyfin, TMDB, or OMDb as the preferred source. GhostyFlix tries that source first and then uses the other available sources as fallbacks. Jellyfin artwork requires no separate key. Discord must be able to reach a Jellyfin poster URL; a server available only on a private network may work in the local preview but not in Discord.

- **TMDB:** Create a key in [TMDB account API settings](https://www.themoviedb.org/settings/api), then paste it into GhostyFlix. TMDB supplies posters for movies and shows.
- **OMDb:** Get a key from the [OMDb API key page](https://www.omdbapi.com/apikey.aspx). Enter the key itself or the complete request URL, such as `https://www.omdbapi.com/?i=tt3896198&apikey=YOUR_KEY`. GhostyFlix extracts the key, looks up Jellyfin's IMDb ID when available, and otherwise searches by title and year.

TMDB preferences include textless artwork, season posters for episodes, and a comma-separated poster language order such as `en, fr`. Leave the language field blank to use English-first matching. These options apply when TMDB is selected; results depend on the images TMDB has for that title.

The OMDb API returns its poster as an image URL; GhostyFlix sends that returned URL to Discord. Provider availability and title matching depend on the metadata returned by each service.

GhostyFlix includes TMDB's approved logo and required notice in the artwork settings. This product uses the TMDB API but is not endorsed or certified by TMDB. See [TMDB's attribution requirements](https://www.themoviedb.org/about/logos-attribution).

### Music art

Jellyfin album artwork is the default. Turn on **Prefer MusicBrainz album artwork** to use MusicBrainz IDs supplied by Jellyfin, or search by artist and album and use the Cover Art Archive. **Prefer a specific album release cover** favors a particular release over the broader release-group cover. No API key is needed. MusicBrainz results depend on its community catalog and the availability of cover images. GhostyFlix identifies its requests and spaces searches in line with [MusicBrainz API guidance](https://musicbrainz.org/doc/MusicBrainz_API/Rate_Limiting).

### Activity details

- Choose zero to three movie genres. One is the default.
- Enable or disable movies, TV shows and episodes, and music independently.
- Choose whether the activity stays visible while playback is paused.
- Include watched or listened percentage and estimated time remaining in the Discord status. The local preview always shows these values when Jellyfin provides a duration.
- Optionally show your Jellyfin server name.
- Show or hide the play/pause poster badge. Orange is the default badge color; enter a hex color or choose one from the color picker.
- The custom badge uses the selected color as its background, with a centered black play/pause mark. Discord displays it as a circle. The image URL contains only the selected color and playback state.
- Use the GhostyFlix mark as the small Discord activity image when the playback badge is hidden.
- In **Settings → Discord Activity Links**, choose whether movie and episode cards include compact IMDb and trailer buttons. IMDb uses the ID from Jellyfin or OMDb. A direct trailer uses TMDB when its ID and API key are available; otherwise the button opens a YouTube trailer search.

The **Now Playing** tab previews the current title, artwork, playback status, progress, and remaining time locally in GhostyFlix.

### Optional browser companion · early test

The companion can report Jellyfin Web sections such as Movies, Playlists, and Collections/Box Sets while playback is idle. It is **experimental**: Jellyfin routes and browser policies change, so some pages or browser versions may not be detected reliably. Playback activity remains the primary feature.

In **Settings → Optional Browser Companion**, choose **Setup guide** for browser-specific steps or **Extension folder** to open the files. Chrome, Brave, and Opera GX use **Load unpacked** for local testing. Firefox uses **Load Temporary Add-on**; it removes the add-on when Firefox closes. Mozilla signing is required for persistent Firefox installs. See the [full browser companion guide](BROWSER_COMPANION.md).

The optional [3.0 Test browser companion build](https://github.com/emoacid1-cmd/ghostyflix-rpc/releases/tag/v2.0.16-browser-test.2) is a separate pre-release. Close the stable app before using it; both builds share local settings and Discord access. It is not installed through the normal updater.

Activity is sent from the approved Jellyfin site to GhostyFlix through a local connection. The extension does not read browser history or use a remote activity service. Browsers require a user confirmation to install extensions; a store listing is needed for a direct install button.

## Preferences

- **Playback check interval** controls how often GhostyFlix checks Jellyfin. It starts at three seconds.
- **Seek refresh sensitivity** controls how large a position jump must be before Discord's timestamps refresh. It also starts at three seconds.
- **Start minimized** opens GhostyFlix without showing the main window.
- **Minimize to system tray when the window closes** is enabled by default. Use **Exit** from the tray menu to fully close GhostyFlix.
- **Open GhostyFlix when Windows starts** adds or removes its entry in your Windows user startup list.
- **Online updates** checks the selected public GitHub repository for a release and offers to install a verified Windows executable.
- **Diagnostic detail** controls the local log level. Use **Open activity log** to review provider and connection messages or **Open settings folder** to locate the saved INI file.

## What Discord displays

Movies appear as **Watching** with the title and year. Episodes use the series title with season, episode, and episode name. Music appears as **Listening** with the track and artist or album. When Jellyfin provides a duration, GhostyFlix sends timestamps for Discord's native timer and progress bar. The optional activity text adds a percentage and estimated time remaining.

Discord controls the card's exact layout, bar design, image availability, and visibility to other people. GhostyFlix cannot customize Discord's native progress bar or card layout.
IMDb and trailer links appear as buttons below the activity, not as extra title or status text. Buttons are omitted for music and can be disabled individually in Settings. Discord hides these buttons from the account viewing its own activity; ask a friend or use a second account to confirm they appear to other viewers.

## Online updates

The updater checks the public repository's latest stable release, validates the executable against its SHA-256 checksum, and downloads it to a temporary folder. When you choose **Install & restart**, GhostyFlix starts a small Windows helper, exits, then the helper replaces the executable and opens the updated app. Test pre-releases are optional and are not offered by the normal updater. If Windows blocks replacement, install the executable manually from [Releases](https://github.com/emoacid1-cmd/ghostyflix-rpc/releases/latest).

## Local data and privacy

Settings and logs are stored in:

```text
%APPDATA%\GhostyFlix RPC\
```

The settings INI stores your Jellyfin server address and sign-in token, plus any TMDB or OMDb key you entered. It is plain text and is not encrypted. The activity log can contain connection or account details; review and redact it before sharing.

GhostyFlix communicates directly with Jellyfin, the local Discord desktop client, and enabled artwork services. Discord receives the activity details and poster URL. The play/pause badge image is served by Placehold.co; its request includes the badge color and symbol, not your title or server credentials.

## Troubleshooting

### No activity appears in Discord

- Open Discord desktop on the same computer and allow activity sharing in Discord's privacy settings.
- Confirm GhostyFlix is connected to the account that is playing media.
- Check that the media type is enabled and the library is included by your filter.
- Disconnect and reconnect if the saved Jellyfin session has expired.

### Quick Connect does not finish

- Check that Quick Connect is enabled in Jellyfin's server settings.
- Approve the displayed code from a device already signed into the server.
- Request a new code if the current one has expired.
- Use the API key option if Quick Connect is not available.

### The local preview has no artwork

- Confirm the selected provider has any required key.
- Jellyfin art is fetched through the authenticated server connection for the local preview. Check the activity log if the server rejects the image request.
- OMDb requires a valid key; a full API URL is accepted.
- TMDB and OMDb fallback artwork may not match if metadata is missing or ambiguous.

### Discord does not show the poster

Discord needs to fetch an image URL it can reach. A private address such as `192.168.x.x`, a localhost URL, or an HTTP-only home server usually cannot be reached by Discord. Choose TMDB or OMDb artwork when available.

### An update is not offered or will not install

- Confirm the repository field contains a public repository in `owner/name` form.
- The release must include a Windows `.exe` and a valid `SHA256SUMS.txt` file or GitHub SHA-256 digest.
- Keep the executable in a folder where your Windows user can replace files, or download the new build manually.

For help, open a [GitHub issue](https://github.com/emoacid1-cmd/ghostyflix-rpc/issues) with the Windows version, steps to reproduce, and relevant redacted log lines. Do not attach credentials, API keys, Quick Connect codes, or your settings file.

## Acknowledgements

GhostyFlix RPC's early build was based on [Jellyfin RPC](https://github.com/kennethsible/jellyfin-rpc), which informed the original connection flow and playback features. GhostyFlix v2 has since been rewritten as a separate implementation. See the [full acknowledgements](../ACKNOWLEDGEMENTS.md).
