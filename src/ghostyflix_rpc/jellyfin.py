from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import requests

TICKS_PER_SECOND = 10_000_000


@dataclass(slots=True)
class MediaSession:
    item_id: str
    media_type: str
    title: str
    subtitle: str
    year: int | None
    genres: list[str]
    position_seconds: int
    duration_seconds: int
    paused: bool
    server_name: str
    imdb_id: str = ''
    tmdb_id: str = ''
    musicbrainz_release_id: str = ''
    musicbrainz_group_id: str = ''
    artist: str = ''
    album: str = ''
    library_ids: tuple[str, ...] = ()
    season_number: int | None = None

    @property
    def remaining_seconds(self) -> int:
        return max(0, self.duration_seconds - self.position_seconds)

    @property
    def progress(self) -> float:
        if self.duration_seconds <= 0:
            return 0.0
        return min(1.0, max(0.0, self.position_seconds / self.duration_seconds))


class JellyfinClient:
    def __init__(self, address: str, token: str = '', device_id: str | None = None) -> None:
        self.base_url = address.strip().rstrip('/') + '/'
        self.device_id = device_id or str(uuid.uuid4())
        self.token = token
        self.http = requests.Session()
        self.http.headers.update({
            'X-Emby-Authorization': self._authorization(token),
            'X-Emby-Token': token,
            'Accept': 'application/json',
            'User-Agent': 'GhostyFlixRPC/2.0',
        })

    def _authorization(self, token: str = '') -> str:
        value = (
            'MediaBrowser Client="GhostyFlix RPC", Device="Desktop", '
            f'DeviceId="{self.device_id}", Version="2.0.0"'
        )
        return f'{value}, Token="{token}"' if token else value

    def endpoint(self, path: str) -> str:
        return urljoin(self.base_url, path.lstrip('/'))

    def initiate_quick_connect(self) -> dict[str, Any]:
        response = self.http.post(self.endpoint('/QuickConnect/Initiate'), params={'timeout': 300}, timeout=10)
        response.raise_for_status()
        body = response.json()
        if not body.get('Secret') or not body.get('Code'):
            raise RuntimeError('The server did not return a Quick Connect code. Check that Quick Connect is enabled.')
        return body

    def quick_connect_approved(self, secret: str) -> bool:
        response = self.http.get(self.endpoint('/QuickConnect/Connect'), params={'secret': secret}, timeout=10)
        response.raise_for_status()
        return bool(response.json().get('Authenticated'))

    def exchange_quick_connect(self, secret: str) -> tuple[str, str, str]:
        response = self.http.post(
            self.endpoint('/Users/AuthenticateWithQuickConnect'),
            json={'Secret': secret},
            timeout=15,
        )
        response.raise_for_status()
        body = response.json()
        user = body.get('User') or {}
        token = str(body.get('AccessToken') or '')
        if not token or not user.get('Id'):
            raise RuntimeError('Jellyfin approved the code but did not return a user session.')
        self.set_token(token)
        return token, str(user['Id']), str(user.get('Name') or '')

    def authenticate_api_key(self, token: str, username: str) -> tuple[str, str, str]:
        self.set_token(token)
        response = self.http.get(self.endpoint('/Users'), timeout=15)
        response.raise_for_status()
        target = username.strip().casefold()
        for user in response.json():
            if str(user.get('Name', '')).casefold() == target:
                return token, str(user['Id']), str(user.get('Name') or '')
        raise RuntimeError(f'No Jellyfin user named “{username}” was found for this API key.')

    def set_token(self, token: str) -> None:
        self.token = token
        self.http.headers['X-Emby-Token'] = token
        self.http.headers['X-Emby-Authorization'] = self._authorization(token)

    def list_libraries(self, user_id: str) -> list[dict[str, str]]:
        response = self.http.get(self.endpoint(f'/Users/{user_id}/Views'), timeout=15)
        response.raise_for_status()
        return [
            {'id': str(row.get('Id') or ''), 'name': str(row.get('Name') or 'Library')}
            for row in response.json().get('Items', [])
        ]

    def item_libraries(self, user_id: str, item_id: str) -> tuple[str, ...]:
        response = self.http.get(
            self.endpoint(f'/Users/{user_id}/Items/{item_id}'),
            params={'Fields': 'AncestorIds'},
            timeout=12,
        )
        response.raise_for_status()
        return tuple(str(value) for value in response.json().get('AncestorIds', []))

    def item_image(self, item_id: str) -> bytes:
        response = self.http.get(
            self.endpoint(f'/Items/{item_id}/Images/Primary'),
            params={'maxWidth': 1000, 'quality': 90},
            timeout=15,
        )
        response.raise_for_status()
        return response.content

    def current_playback(self, user_id: str) -> MediaSession | None:
        response = self.http.get(
            self.endpoint('/Sessions'),
            params={'activeWithinSeconds': 90},
            timeout=15,
        )
        response.raise_for_status()
        sessions = response.json()
        selected: dict[str, Any] | None = None
        for candidate in sessions:
            if str(candidate.get('UserId') or '') != user_id:
                continue
            if candidate.get('NowPlayingItem'):
                selected = candidate
                break
        if selected is None:
            return None
        item = selected['NowPlayingItem']
        play_state = selected.get('PlayState') or {}
        provider_ids = item.get('ProviderIds') or {}
        series_provider_ids = item.get('SeriesProviderIds') or {}
        media_type = str(item.get('Type') or '')
        is_music = media_type == 'Audio'
        is_episode = media_type == 'Episode'
        artists = item.get('Artists') or []
        artist = ', '.join(str(name) for name in artists[:3])
        album = str(item.get('Album') or '')
        if is_episode:
            series = str(item.get('SeriesName') or item.get('Name') or 'TV episode')
            season = item.get('ParentIndexNumber')
            episode = item.get('IndexNumber')
            code = f'S{int(season):02d} · E{int(episode):02d}' if season is not None and episode is not None else 'Episode'
            subtitle = f'{code} · {item.get("Name") or ""}'.strip(' ·')
            title = series
        elif is_music:
            title = str(item.get('Name') or 'Unknown track')
            subtitle = ' · '.join(part for part in (artist, album) if part)
        else:
            title = str(item.get('Name') or 'Unknown title')
            subtitle = ''
        runtime = int(item.get('RunTimeTicks') or 0) // TICKS_PER_SECOND
        position = int(play_state.get('PositionTicks') or 0) // TICKS_PER_SECOND
        musicbrainz = item.get('ProviderIds') or {}
        return MediaSession(
            item_id=str(item.get('Id') or ''),
            media_type='Music' if is_music else ('Episode' if is_episode else 'Movie'),
            title=title,
            subtitle=subtitle,
            year=int(item['ProductionYear']) if item.get('ProductionYear') else None,
            genres=[str(value) for value in (item.get('Genres') or [])],
            position_seconds=position,
            duration_seconds=runtime,
            paused=bool(play_state.get('IsPaused')),
            server_name=str(selected.get('ServerName') or 'Jellyfin'),
            imdb_id=str(provider_ids.get('Imdb') or provider_ids.get('IMDb') or series_provider_ids.get('Imdb') or series_provider_ids.get('IMDb') or ''),
            tmdb_id=str(provider_ids.get('Tmdb') or series_provider_ids.get('Tmdb') or ''),
            musicbrainz_release_id=str(musicbrainz.get('MusicBrainzAlbum') or ''),
            musicbrainz_group_id=str(musicbrainz.get('MusicBrainzReleaseGroup') or ''),
            artist=artist,
            album=album,
            season_number=int(item['ParentIndexNumber']) if item.get('ParentIndexNumber') is not None else None,
        )
