# Changelog

## 2.0.16 — 2026-11-01

- Enlarge the centered black play triangle while keeping the selected-color badge and existing pause mark.

## 2.0.15 — 2026-11-01

- Keep the larger play triangle within Discord's image URL limit and report badge publish status accurately.

## 2.0.14 — 2026-11-01

- Make the play badge triangle slightly larger while preserving its selected-color background.

## 2.0.13 — 2026-11-01

- Restore the earlier Montserrat badge rendering, with a centered black play mark or two-bar pause mark on the selected color.

## 2.0.12 — 2026-11-01

- Restore the earlier smooth, centered play/pause badge with black symbols and a user-selectable circular background color.

## 2.0.11 — 2026-11-01

- Refresh Discord's cached playback badge so the black play/pause mark and user-selected orange circle render correctly.

## 2.0.10 — 2026-11-01

- Log Discord IPC and activity update failures so connection problems are diagnosable.

## 2.0.9 — 2026-11-01

- Keep Discord badge images below the 300-character limit with bold custom play/pause artwork.
- Avoid treating the stable position of paused media as a seek.

## 2.0.8 — 2026-11-01

- Keep the Discord activity live if the custom playback badge image is rejected.
- Log Discord publish failures so connection problems are visible during troubleshooting.

## 2.0.7 — 2026-11-01

- Replace font-based playback marks with bold, custom-rendered black play and pause symbols.
- Clarify that Discord hides Rich Presence buttons from the account viewing its own activity.

## 2.0.6 — 2026-11-01

- Add optional IMDb and trailer buttons to movie and episode Discord activities.
- Keep links out of the activity text and cache provider lookups per title.

## 2.0.5 — 2026-11-01

- Retain Ken Sible's MIT copyright notice alongside GhostyGang's.
- Include the license notices in the Windows app and as a release download.
- Add a Settings shortcut for viewing the license notices.

## 2.0.4 — 2026-11-01

- Restore bold play and pause glyphs in the Discord artwork badge.

## 2.0.3 — 2026-11-01

- Minimize to the system tray when the window closes by default, with a clear preference to change the behavior.
- Use the configured Jellyfin server name in the Discord headline and remove the redundant server suffix after the genre.
- Improve the visibility of the play/pause badge in Discord.
- Refine the orange-and-charcoal interface and fix a CustomTkinter startup crash.

## 2.0.2 — 2026-11-01

- Fix a startup crash caused by an unsupported CustomTkinter label option.

## 2.0.1 — 2026-11-01

- Preserve saved Jellyfin sign-in sessions when upgrading from an earlier GhostyFlix release.
- Keep existing poster, library filter, playback, and badge preferences when loading the saved settings file.
- Restore diagnostic detail controls and quick links to the local settings and activity log.
- Align the Windows release filename with its SHA-256 manifest entry.

## 2.0.0 — 2026-11-01

- Reworked the application architecture, Jellyfin connection flow, playback service, and release updater.
- Refreshed the desktop interface with clearer connection steps, a live activity preview, and grouped settings.
- Added safer in-app update downloads with SHA-256 verification and a restart helper for Windows.
- Kept playback polling and seek refresh intervals adjustable, with a three-second default.
- Updated setup, privacy, artwork, and build documentation.

