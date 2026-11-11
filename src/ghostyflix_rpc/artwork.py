from __future__ import annotations

import re
import threading
import time
from typing import Any
from urllib.parse import quote, quote_plus, urljoin, urlparse, urlunparse

import requests

from .jellyfin import JellyfinClient, MediaSession
from .settings import Settings


class ArtworkLookup:
    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, str, str]] = {}
        self._link_cache: dict[str, tuple[float, list[dict[str, str]]]] = {}
        self._musicbrainz_lock = threading.Lock()
        self._last_musicbrainz_request = 0.0
        self.last_source = ''
        self.http = requests.Session()
        self.http.headers.update({'User-Agent': 'GhostyFlixRPC/2.0 (https://github.com/GhostyGang/ghostyflix-rpc)'})

    def activity_links(self, media: MediaSession, settings: Settings) -> list[dict[str, str]]:
        if media.media_type not in {'Movie', 'Episode'}:
            return []
        cache_key = '|'.join((
            media.item_id, media.title, str(media.year), media.imdb_id, media.tmdb_id,
            settings.omdb_api_key, settings.tmdb_api_key,
            str(settings.show_imdb_button), str(settings.show_trailer_button),
        ))
        cached = self._link_cache.get(cache_key)
        if cached and cached[0] > time.monotonic():
            return [dict(button) for button in cached[1]]

        buttons: list[dict[str, str]] = []
        if settings.show_imdb_button:
            imdb_id = media.imdb_id or self._lookup_imdb_id(media, settings)
            if re.fullmatch(r'tt\d{5,12}', imdb_id):
                buttons.append({'label': 'IMDb', 'url': f'https://www.imdb.com/title/{imdb_id}/'})
        if settings.show_trailer_button:
            trailer_url = self._tmdb_trailer(media, settings) or self._youtube_search(media)
            label = 'Trailer' if 'youtube.com/watch?' in trailer_url else 'Trailer search'
            buttons.append({'label': label, 'url': trailer_url})

        if len(self._link_cache) > 256:
            now = time.monotonic()
            self._link_cache = {key: value for key, value in self._link_cache.items() if value[0] > now}
        self._link_cache[cache_key] = (time.monotonic() + 900, [dict(button) for button in buttons])
        return buttons

    def _lookup_imdb_id(self, media: MediaSession, settings: Settings) -> str:
        key = self._extract_omdb_key(settings.omdb_api_key)
        if not key:
            return ''
        params = {'apikey': key, 't': media.title}
        if media.year:
            params['y'] = str(media.year)
        if media.media_type == 'Episode':
            params['type'] = 'series'
        try:
            response = self.http.get('https://www.omdbapi.com/', params=params, timeout=6)
            response.raise_for_status()
            return str(response.json().get('imdbID') or '')
        except (requests.RequestException, ValueError, AttributeError):
            return ''

    def _tmdb_trailer(self, media: MediaSession, settings: Settings) -> str:
        key = settings.tmdb_api_key.strip()
        identifier = media.tmdb_id
        if not key or not identifier:
            return ''
        kind = 'tv' if media.media_type == 'Episode' else 'movie'
        try:
            response = self.http.get(
                f'https://api.themoviedb.org/3/{kind}/{quote(identifier)}/videos',
                params={'api_key': key}, timeout=6,
            )
            response.raise_for_status()
            videos = response.json().get('results') or []
        except (requests.RequestException, ValueError, AttributeError):
            return ''
        candidates = [
            row for row in videos
            if row.get('site') == 'YouTube' and row.get('type') == 'Trailer' and row.get('key')
        ]
        if not candidates:
            return ''
        candidates.sort(key=lambda row: (not bool(row.get('official')), row.get('iso_639_1') != 'en'))
        return f'https://www.youtube.com/watch?v={quote(str(candidates[0]["key"]))}'

    @staticmethod
    def _youtube_search(media: MediaSession) -> str:
        terms = [media.title, str(media.year) if media.year else '', 'official trailer']
        if media.media_type == 'Episode' and media.subtitle:
            terms.insert(1, media.subtitle)
        query = quote_plus(' '.join(value for value in terms if value))
        return f'https://www.youtube.com/results?search_query={query}'

    def poster(self, media: MediaSession, server: JellyfinClient, settings: Settings) -> str:
        cache_key = '|'.join((
            media.item_id, settings.poster_provider, settings.tmdb_api_key,
            settings.omdb_api_key, str(settings.musicbrainz_artwork),
            str(settings.release_over_group), str(settings.textless_posters),
            str(settings.season_over_series), settings.poster_languages,
        ))
        stored = self._cache.get(cache_key)
        if stored and stored[0] > time.monotonic():
            self.last_source = stored[2]
            return stored[1]
        sources = self._sources(media, server, settings)
        for source, lookup in sources:
            try:
                result = lookup()
            except (requests.RequestException, ValueError, KeyError, IndexError):
                result = ''
            if result and result.startswith(('https://', 'http://')):
                self.last_source = source
                self._cache[cache_key] = (time.monotonic() + 900, result, source)
                return result
        self.last_source = ''
        self._cache[cache_key] = (time.monotonic() + 120, '', '')
        return ''

    def _sources(self, media: MediaSession, server: JellyfinClient, settings: Settings) -> list[tuple[str, Any]]:
        available: dict[str, Any] = {
            'Jellyfin': lambda: self._jellyfin(media, server),
            'TMDB': lambda: self._tmdb(media, settings),
            'OMDb': lambda: self._omdb(media, settings),
        }
        preference = settings.poster_provider if settings.poster_provider in available else 'Jellyfin'
        ordered = [preference, *(name for name in ('TMDB', 'OMDb', 'Jellyfin') if name != preference)]
        if media.media_type == 'Music':
            if settings.musicbrainz_artwork:
                return [('MusicBrainz / Cover Art Archive', lambda: self._musicbrainz(media, settings)), ('Jellyfin', available['Jellyfin'])]
            return [('Jellyfin', available['Jellyfin']), ('MusicBrainz / Cover Art Archive', lambda: self._musicbrainz(media, settings))]
        return [(name, available[name]) for name in ordered]

    @staticmethod
    def _jellyfin(media: MediaSession, server: JellyfinClient) -> str:
        if not media.item_id:
            return ''
        return urljoin(server.base_url, f'Items/{quote(media.item_id)}/Images/Primary?maxWidth=1000&quality=90')

    def _tmdb(self, media: MediaSession, settings: Settings) -> str:
        key = settings.tmdb_api_key.strip()
        if not key:
            return ''
        kind = 'tv' if media.media_type == 'Episode' else 'movie'
        identifier = media.tmdb_id
        if not identifier:
            query = media.title
            params: dict[str, Any] = {'api_key': key, 'query': query}
            if media.year and kind == 'movie':
                params['year'] = media.year
            response = self.http.get(f'https://api.themoviedb.org/3/search/{kind}', params=params, timeout=8)
            response.raise_for_status()
            results = response.json().get('results') or []
            identifier = str(results[0].get('id') or '') if results else ''
        if not identifier:
            return ''
        if media.media_type == 'Episode' and settings.season_over_series and media.season_number is not None:
            base = f'https://api.themoviedb.org/3/tv/{identifier}/season/{media.season_number}'
        else:
            base = f'https://api.themoviedb.org/3/{kind}/{identifier}'
        language_preferences = [part.strip() for part in settings.poster_languages.split(',') if part.strip()]
        if not language_preferences:
            language_preferences = ['en']
        if settings.textless_posters:
            language_preferences = ['null', *(value for value in language_preferences if value != 'null')]
        include_languages = ','.join(dict.fromkeys((*language_preferences, 'en', 'null')))
        images_response = self.http.get(
            f'{base}/images',
            params={'api_key': key, 'include_image_language': include_languages},
            timeout=8,
        )
        images_response.raise_for_status()
        images = images_response.json().get('posters') or []
        rank = {language: index for index, language in enumerate(language_preferences)}
        images.sort(key=lambda image: (rank.get(str(image.get('iso_639_1') or 'null'), len(rank)), -float(image.get('vote_average') or 0)))
        path = images[0].get('file_path') if images else ''
        if not path:
            detail_response = self.http.get(base, params={'api_key': key, 'language': language_preferences[0]}, timeout=8)
            detail_response.raise_for_status()
            path = detail_response.json().get('poster_path')
        return f'https://image.tmdb.org/t/p/w780{path}' if path else ''

    def _omdb(self, media: MediaSession, settings: Settings) -> str:
        key = self._extract_omdb_key(settings.omdb_api_key)
        if not key:
            return ''
        params: dict[str, str] = {'apikey': key}
        if media.imdb_id:
            params['i'] = media.imdb_id
        else:
            params['t'] = media.title
            if media.year:
                params['y'] = str(media.year)
            if media.media_type == 'Episode':
                params['type'] = 'series'
        payload = self.http.get('https://www.omdbapi.com/', params=params, timeout=8).json()
        poster = str(payload.get('Poster') or '')
        return poster if poster not in {'N/A', 'null'} else ''

    @staticmethod
    def _extract_omdb_key(value: str) -> str:
        text = value.strip()
        if not text:
            return ''
        if '://' in text:
            values = dict(part.split('=', 1) for part in urlparse(text).query.split('&') if '=' in part)
            return values.get('apikey', '')
        return text

    def _musicbrainz(self, media: MediaSession, settings: Settings) -> str:
        release_id = media.musicbrainz_release_id
        group_id = media.musicbrainz_group_id
        if settings.release_over_group and release_id:
            return f'https://coverartarchive.org/release/{quote(release_id)}/front-500'
        if group_id:
            return f'https://coverartarchive.org/release-group/{quote(group_id)}/front-500'
        if release_id:
            return f'https://coverartarchive.org/release/{quote(release_id)}/front-500'
        if not media.album or not media.artist:
            return ''
        with self._musicbrainz_lock:
            pause = 1.05 - (time.monotonic() - self._last_musicbrainz_request)
            if pause > 0:
                time.sleep(pause)
            self._last_musicbrainz_request = time.monotonic()
            response = self.http.get(
                'https://musicbrainz.org/ws/2/release-group/',
                params={
                    'query': f'releasegroup:"{media.album}" AND artist:"{media.artist}"',
                    'fmt': 'json',
                    'limit': 1,
                },
                timeout=8,
            )
        response.raise_for_status()
        rows = response.json().get('release-groups') or []
        identifier = str(rows[0].get('id') or '') if rows else ''
        return f'https://coverartarchive.org/release-group/{quote(identifier)}/front-500' if identifier else ''


def select_genres(media: MediaSession, limit: int) -> str:
    if limit <= 0:
        return ''
    clean: list[str] = []
    for genre in media.genres:
        name = re.sub(r'\s+', ' ', genre).strip()
        if name and name.casefold() not in {value.casefold() for value in clean}:
            clean.append(name)
    return ' · '.join(clean[:limit])


def normalize_public_image(value: str) -> str:
    """Return a small, Discord-friendly HTTP(S) image address."""
    parsed = urlparse(value)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        return ''
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', parsed.query, ''))
