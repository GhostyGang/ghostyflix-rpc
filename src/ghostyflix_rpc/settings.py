from __future__ import annotations

import configparser
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any


def settings_directory() -> Path:
    root = Path(os.environ.get('APPDATA') or Path.home() / '.config')
    return root / 'GhostyFlix RPC'


def settings_path() -> Path:
    return settings_directory() / 'ghostyflix_rpc.ini'


@dataclass(slots=True)
class Settings:
    jellyfin_host: str = ''
    jellyfin_api_key: str = ''
    jellyfin_username: str = ''
    jellyfin_user_id: str = ''
    jellyfin_token: str = ''
    poster_provider: str = 'Jellyfin'
    tmdb_api_key: str = ''
    omdb_api_key: str = ''
    musicbrainz_artwork: bool = False
    release_over_group: bool = False
    filter_mode: str = 'blacklist'
    filter_libraries: str = ''
    genre_limit: int = 1
    media_movies: bool = True
    media_shows: bool = True
    media_music: bool = True
    show_when_paused: bool = True
    show_progress_text: bool = True
    show_server_name: bool = False
    show_playback_badge: bool = True
    badge_color: str = '#F97316'
    polling_rate: int = 3
    seek_threshold: int = 3
    log_level: str = 'INFO'
    update_repository: str = 'GhostyGang/ghostyflix-rpc'
    automatic_updates: bool = True
    show_jellyfin_logo: bool = False
    textless_posters: bool = False
    season_over_series: bool = False
    poster_languages: str = ''
    start_minimized: bool = False
    close_to_tray: bool = False
    open_on_startup: bool = False

    @classmethod
    def load(cls) -> 'Settings':
        parser = configparser.ConfigParser()
        path = settings_path()
        if path.exists():
            parser.read(path, encoding='utf-8')
        section = parser['DEFAULT'] if parser.defaults() else {}
        raw: dict[str, Any] = {}
        bool_names = {
            'musicbrainz_artwork', 'media_movies', 'media_shows', 'media_music',
            'show_when_paused', 'show_progress_text', 'show_server_name',
            'show_playback_badge', 'automatic_updates', 'show_jellyfin_logo',
            'release_over_group', 'textless_posters', 'season_over_series',
            'start_minimized', 'close_to_tray', 'open_on_startup',
        }
        int_names = {'genre_limit', 'polling_rate', 'seek_threshold'}
        for item in fields(cls):
            value = section.get(item.name)
            if value is None:
                continue
            try:
                if item.name in bool_names:
                    raw[item.name] = str(value).strip().lower() in {'true', '1', 'yes', 'on'}
                elif item.name in int_names:
                    raw[item.name] = int(value)
                else:
                    raw[item.name] = value
            except (TypeError, ValueError):
                continue
        if 'media_types' in section:
            kinds = {part.strip().lower() for part in section.get('media_types', '').split(',')}
            raw.setdefault('media_movies', 'movies' in kinds)
            raw.setdefault('media_shows', 'shows' in kinds)
            raw.setdefault('media_music', 'music' in kinds)
        if 'always_use_musicbrainz' in section:
            raw.setdefault('musicbrainz_artwork', section.getboolean('always_use_musicbrainz', fallback=False))
        if 'always_use_tmdb' in section and 'poster_provider' not in section:
            if section.getboolean('always_use_tmdb', fallback=False):
                raw['poster_provider'] = 'TMDB'
        if 'show_jellyfin_icon' in section:
            raw['show_jellyfin_logo'] = bool(
                raw.get('show_jellyfin_logo', False)
                or section.getboolean('show_jellyfin_icon', fallback=False)
            )
        raw['polling_rate'] = min(30, max(1, int(raw.get('polling_rate', 3))))
        raw['seek_threshold'] = min(30, max(1, int(raw.get('seek_threshold', 3))))
        raw['genre_limit'] = min(3, max(0, int(raw.get('genre_limit', 1))))
        provider_names = {'jellyfin': 'Jellyfin', 'tmdb': 'TMDB', 'omdb': 'OMDb'}
        raw['poster_provider'] = provider_names.get(str(raw.get('poster_provider', 'Jellyfin')).lower(), 'Jellyfin')
        raw['filter_mode'] = str(raw.get('filter_mode', 'blacklist')).lower()
        if raw.get('filter_mode') not in {'blacklist', 'whitelist'}:
            raw['filter_mode'] = 'blacklist'
        raw['log_level'] = str(raw.get('log_level', 'INFO')).upper()
        if raw['log_level'] not in {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}:
            raw['log_level'] = 'INFO'
        if raw.get('poster_provider') not in {'Jellyfin', 'TMDB', 'OMDb'}:
            raw['poster_provider'] = 'Jellyfin'
        return cls(**raw)

    def save(self) -> None:
        directory = settings_directory()
        directory.mkdir(parents=True, exist_ok=True)
        parser = configparser.ConfigParser()
        for name, value in asdict(self).items():
            parser['DEFAULT'][name] = str(value).lower() if isinstance(value, bool) else str(value)
        parser['DEFAULT']['media_types'] = ','.join(
            name for enabled, name in (
                (self.media_movies, 'Movies'), (self.media_shows, 'Shows'),
                (self.media_music, 'Music'),
            ) if enabled
        )
        temporary = settings_path().with_suffix('.tmp')
        with temporary.open('w', encoding='utf-8', newline='') as stream:
            parser.write(stream)
        temporary.replace(settings_path())
