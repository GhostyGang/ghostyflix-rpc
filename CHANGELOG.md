# Changelog

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

