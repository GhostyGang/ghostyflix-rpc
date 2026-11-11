from __future__ import annotations

import queue
import logging
import threading
import time
import uuid
from typing import Any
from urllib.parse import quote

from pypresence import Presence
from pypresence.types import ActivityType

from .artwork import ArtworkLookup, normalize_public_image, select_genres
from .browser_bridge import BrowserActivityBridge, normalized_origin
from .jellyfin import JellyfinClient, MediaSession
from .settings import Settings
from . import DISCORD_APPLICATION_ID


def format_clock(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f'{hours} hr {minutes} min'
    if minutes:
        return f'{minutes} min'
    return f'{seconds} sec'


class PlaybackService:
    """Owns Jellyfin polling and the local Discord IPC connection."""

    def __init__(self, settings: Settings) -> None:
        self.events: queue.Queue[dict[str, Any]] = queue.Queue()
        self.commands: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._settings = settings
        self._thread: threading.Thread | None = None
        self._closed = threading.Event()
        self._client: JellyfinClient | None = None
        self._user_id = settings.jellyfin_user_id
        self._user_name = settings.jellyfin_username
        self._rpc: Presence | None = None
        self._artwork = ArtworkLookup()
        self._quick_secret = ''
        self._quick_deadline = 0.0
        self._last_quick_poll = 0.0
        self._last_playback: MediaSession | None = None
        self._last_published: tuple[Any, ...] | None = None
        self._last_position = 0
        self._last_update_time = 0.0
        self._last_status = ''
        self._library_cache: dict[str, tuple[str, ...]] = {}
        self._preview_art_cache: dict[str, bytes] = {}
        self._last_artwork_source = ''
        self._last_artwork_item = ''
        self._browser_activity: tuple[str, str, str, float] | None = None
        self._browser_signature: tuple[Any, ...] | None = None
        self._browser_item_cache: dict[str, tuple[MediaSession, bytes | None]] = {}
        self._browser_lookup_pending: set[str] = set()
        self._browser_lookup_retry: dict[str, float] = {}
        self._browser_bridge = BrowserActivityBridge(lambda payload: self.commands.put(('browser_activity', payload)))

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._browser_bridge.start()
        self._thread = threading.Thread(target=self._run, name='GhostyFlix playback', daemon=True)
        self._thread.start()
        if self._settings.jellyfin_host and (self._settings.jellyfin_token or self._settings.jellyfin_api_key):
            self.commands.put(('resume', None))

    def close(self) -> None:
        self._closed.set()
        self.commands.put(('close', None))
        self._browser_bridge.close()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def connect_quick(self, server: str) -> None:
        self.commands.put(('quick', server))

    def connect_api_key(self, server: str, username: str, api_key: str) -> None:
        self.commands.put(('api', (server, username, api_key)))

    def disconnect(self) -> None:
        self.commands.put(('disconnect', None))

    def update_settings(self, settings: Settings) -> None:
        self.commands.put(('settings', settings))

    def list_libraries(self) -> None:
        self.commands.put(('libraries', None))

    def _emit(self, kind: str, **values: Any) -> None:
        self.events.put({'type': kind, **values})

    def _status(self, text: str) -> None:
        if text != self._last_status:
            self._last_status = text
            self._emit('status', text=text)

    def _run(self) -> None:
        next_poll = 0.0
        while not self._closed.is_set():
            try:
                name, payload = self.commands.get(timeout=0.2)
            except queue.Empty:
                name = ''
            if name:
                try:
                    self._handle_command(name, payload)
                except Exception as exc:
                    self._emit('quick_error' if name == 'quick' else 'error', text=str(exc))
            now = time.monotonic()
            if self._quick_secret and now >= self._quick_deadline:
                self._quick_secret = ''
                self._emit('quick_error', text='This Quick Connect code expired. Request a new one to continue.')
            elif self._quick_secret and now - self._last_quick_poll >= 2.0:
                self._poll_quick_connect()
            interval = max(1, self._settings.polling_rate)
            if self._client and self._user_id and now >= next_poll:
                self._poll_playback()
                next_poll = now + interval
        self._close_rpc()

    def _handle_command(self, name: str, payload: Any) -> None:
        if name == 'close':
            return
        if name == 'browser_activity':
            if not self._client or not self._settings.jellyfin_host:
                return
            page = str(payload.get('page') or '')[:20]
            title = ' '.join(str(payload.get('title') or '').split())[:100]
            item_id = str(payload.get('item_id') or '').strip()
            server = normalized_origin(str(payload.get('server') or ''))
            configured = normalized_origin(self._settings.jellyfin_host)
            if not server or server != configured:
                return
            if page == 'idle':
                self._browser_activity = None
                self._browser_signature = None
            elif page in {'home', 'movies', 'shows', 'music', 'search', 'playlists', 'collections', 'details'}:
                if page != 'details' or not self._valid_item_id(item_id):
                    item_id = ''
                previous = self._browser_activity
                self._browser_activity = (page, title, item_id, time.monotonic() + 12)
                if not previous or previous[:3] != (page, title, item_id):
                    self._browser_signature = None
                if (
                    item_id
                    and item_id not in self._browser_item_cache
                    and item_id not in self._browser_lookup_pending
                    and self._browser_lookup_retry.get(item_id, 0) <= time.monotonic()
                ):
                    self._start_browser_item_lookup(item_id, server)
                self._emit('browser_activity', page=page, title=title)
            return
        if name == 'browser_item_details':
            item_id = str(payload.get('item_id') or '')
            server = normalized_origin(str(payload.get('server') or ''))
            if (
                not self._valid_item_id(item_id)
                or server != normalized_origin(self._settings.jellyfin_host)
                or str(payload.get('user_id') or '') != self._user_id
            ):
                self._browser_lookup_pending.discard(item_id)
                return
            self._browser_lookup_pending.discard(item_id)
            media = payload.get('media')
            if isinstance(media, MediaSession):
                self._browser_lookup_retry.pop(item_id, None)
                self._browser_item_cache[item_id] = (media, payload.get('image'))
                if len(self._browser_item_cache) > 64:
                    self._browser_item_cache.pop(next(iter(self._browser_item_cache)))
                if self._browser_activity and self._browser_activity[2] == item_id:
                    self._browser_signature = None
            else:
                self._browser_lookup_retry[item_id] = time.monotonic() + 30
            return
        if name == 'settings':
            self._settings = payload
            return
        if name == 'quick':
            server = str(payload).strip()
            self._quick_secret = ''
            self._status('Contacting Jellyfin…')
            self._client = JellyfinClient(server)
            body = self._client.initiate_quick_connect()
            self._quick_secret = str(body['Secret'])
            self._quick_deadline = time.monotonic() + 300
            self._last_quick_poll = 0
            self._status('Approve the code in Jellyfin to finish connecting.')
            self._emit('quick_code', code=str(body['Code']))
            return
        if name == 'api':
            server, username, key = payload
            self._status('Checking your Jellyfin sign-in…')
            client = JellyfinClient(server, key)
            token, user_id, user_name = client.authenticate_api_key(key, username)
            self._complete_connection(client, token, user_id, user_name, server)
            return
        if name == 'resume':
            settings = self._settings
            token = settings.jellyfin_token or settings.jellyfin_api_key
            if settings.jellyfin_host and token:
                client = JellyfinClient(settings.jellyfin_host, token)
                user_id = settings.jellyfin_user_id
                user_name = settings.jellyfin_username
                if not user_id:
                    token, user_id, user_name = client.authenticate_api_key(token, user_name)
                    settings.jellyfin_token = token
                    settings.jellyfin_api_key = ''
                    settings.jellyfin_user_id = user_id
                    settings.jellyfin_username = user_name
                    settings.save()
                self._client = client
                self._user_id = user_id
                self._user_name = user_name
                self._status(f'Connected as {self._user_name or "Jellyfin user"}. Waiting for playback…')
                self._emit('connected', name=self._user_name, server=settings.jellyfin_host)
            return
        if name == 'disconnect':
            self._client = None
            self._quick_secret = ''
            self._last_playback = None
            self._last_published = None
            self._user_id = ''
            self._user_name = ''
            self._browser_activity = None
            self._browser_item_cache.clear()
            self._browser_lookup_pending.clear()
            self._browser_lookup_retry.clear()
            self._settings.jellyfin_token = ''
            self._settings.jellyfin_api_key = ''
            self._settings.jellyfin_user_id = ''
            self._settings.jellyfin_username = ''
            self._settings.save()
            self._clear_presence()
            self._status('Disconnected')
            self._emit('playback', media=None)
            self._emit('disconnected')
            return
        if name == 'libraries':
            if not self._client or not self._user_id:
                raise RuntimeError('Connect to Jellyfin before loading libraries.')
            self._emit('libraries', items=self._client.list_libraries(self._user_id))

    def _poll_quick_connect(self) -> None:
        self._last_quick_poll = time.monotonic()
        try:
            if self._client and self._client.quick_connect_approved(self._quick_secret):
                token, user_id, user_name = self._client.exchange_quick_connect(self._quick_secret)
                self._quick_secret = ''
                self._complete_connection(self._client, token, user_id, user_name, self._client.base_url.rstrip('/'))
        except Exception as exc:
            self._quick_secret = ''
            self._emit(
                'quick_error',
                text=f'Could not check Quick Connect approval: {exc}',
                preserve_code=True,
            )

    def _complete_connection(self, client: JellyfinClient, token: str, user_id: str, name: str, server: str) -> None:
        settings = self._settings
        settings.jellyfin_host = server.rstrip('/')
        settings.jellyfin_token = token
        settings.jellyfin_user_id = user_id
        settings.jellyfin_username = name
        settings.jellyfin_api_key = ''
        settings.save()
        self._client = client
        self._user_id = user_id
        self._user_name = name
        self._library_cache.clear()
        self._preview_art_cache.clear()
        self._browser_item_cache.clear()
        self._browser_lookup_pending.clear()
        self._browser_lookup_retry.clear()
        self._last_published = None
        self._status(f'Connected as {name}. Waiting for playback…')
        self._emit('connected', name=name, server=settings.jellyfin_host)

    @staticmethod
    def _valid_item_id(value: str) -> bool:
        try:
            parsed = uuid.UUID(value)
            return value.lower() in {str(parsed), parsed.hex}
        except (ValueError, AttributeError):
            return False

    def _start_browser_item_lookup(self, item_id: str, server: str) -> None:
        client = self._client
        user_id = self._user_id
        if not client or not user_id:
            return
        token = client.token
        device_id = client.device_id
        host = self._settings.jellyfin_host
        self._browser_lookup_pending.add(item_id)

        def lookup() -> None:
            media: MediaSession | None = None
            image: bytes | None = None
            lookup_client: JellyfinClient | None = None
            try:
                lookup_client = JellyfinClient(host, token, device_id=device_id)
                media = lookup_client.item_metadata(user_id, item_id)
                try:
                    image = lookup_client.item_image(item_id)
                except Exception:
                    image = None
            except Exception as exc:
                logging.debug('Browser item metadata lookup failed: %s', str(exc)[:180])
            finally:
                if lookup_client:
                    lookup_client.http.close()
            self.commands.put((
                'browser_item_details',
                {'item_id': item_id, 'server': server, 'user_id': user_id, 'media': media, 'image': image},
            ))

        threading.Thread(target=lookup, name='GhostyFlix browser item lookup', daemon=True).start()

    def _poll_playback(self) -> None:
        if not self._client:
            return
        try:
            media = self._client.current_playback(self._user_id)
        except Exception as exc:
            self._status(f'Jellyfin connection paused: {exc}')
            return
        if media is None or not self._media_enabled(media):
            if media is not None:
                self._browser_signature = None
            self._last_playback = None
            self._last_published = None
            if media is None and self._publish_browser_activity():
                self._status(f'Browsing Jellyfin · {self._browser_activity[0]}')
                server_name = self._client.server_name if self._settings.show_server_name else 'Jellyfin'
                page, title, item_id, _expires = self._browser_activity
                cached = self._browser_item_cache.get(item_id) if item_id else None
                browser_media, browser_preview_art = cached if cached else (None, None)
                browser_poster = (
                    self._artwork.poster(browser_media, self._client, self._settings)
                    if browser_media else ''
                )
                self._emit(
                    'playback', media=None, browser=(page, title, item_id), server_name=server_name,
                    browser_media=browser_media, browser_poster=browser_poster,
                    browser_preview_art=browser_preview_art,
                )
                return
            self._clear_presence()
            self._status(f'Connected as {self._user_name}. Waiting for playback…')
            self._emit('playback', media=None)
            return
        media.library_ids = self._library_cache.get(media.item_id, ())
        if media.item_id not in self._library_cache:
            try:
                media.library_ids = self._client.item_libraries(self._user_id, media.item_id)
                self._library_cache[media.item_id] = media.library_ids
            except Exception:
                pass
        selected_libraries = {value for value in self._settings.filter_libraries.split(',') if value}
        if selected_libraries:
            overlaps = bool(selected_libraries.intersection(media.library_ids))
            excluded = overlaps if self._settings.filter_mode == 'blacklist' else not overlaps
            if excluded:
                self._last_playback = None
                self._last_published = None
                self._clear_presence()
                self._emit('playback', media=None)
                return
        if media.paused and not self._settings.show_when_paused:
            self._last_playback = media
            self._last_published = None
            self._clear_presence()
            self._emit('playback', media=media)
            self._status(f'Paused: {media.title}')
            return
        poster = self._artwork.poster(media, self._client, self._settings)
        if self._artwork.last_source and (
            self._artwork.last_source != self._last_artwork_source
            or media.item_id != self._last_artwork_item
        ):
            self._last_artwork_source = self._artwork.last_source
            self._last_artwork_item = media.item_id
            logging.info('Artwork source selected: %s', self._last_artwork_source)
        preview_art: bytes | None = None
        if media.item_id in self._preview_art_cache:
            preview_art = self._preview_art_cache[media.item_id]
        elif poster.startswith(self._client.base_url):
            try:
                preview_art = self._client.item_image(media.item_id)
                self._preview_art_cache[media.item_id] = preview_art
            except Exception:
                pass
        self._emit('playback', media=media, poster=poster, preview_art=preview_art)
        self._publish(media, poster)
        self._status(('Paused' if media.paused else 'Watching') + f' · {media.title}')

    def _media_enabled(self, media: MediaSession) -> bool:
        return {
            'Movie': self._settings.media_movies,
            'Episode': self._settings.media_shows,
            'Music': self._settings.media_music,
        }.get(media.media_type, False)

    def _publish_browser_activity(self) -> bool:
        activity = self._browser_activity
        if not activity:
            return False
        page, title, item_id, expires = activity
        if time.monotonic() >= expires:
            self._browser_activity = None
            self._browser_signature = None
            return False
        cached = self._browser_item_cache.get(item_id) if item_id else None
        media = cached[0] if cached else None
        poster = (
            self._artwork.poster(media, self._client, self._settings)
            if media and self._client else ''
        )
        signature = (
            page, title, item_id,
            media.title if media else '', media.year if media else None,
            tuple(media.genres) if media else (), poster,
            self._settings.genre_limit, self._settings.show_server_name,
        )
        if signature == self._browser_signature and self._rpc:
            return True
        if not self._ensure_rpc():
            return True
        labels = {
            'home': 'Home', 'movies': 'Movies', 'shows': 'Shows',
            'music': 'Music', 'search': 'Search', 'playlists': 'Playlists',
            'collections': 'Collections',
        }
        if media:
            display_title = media.title + (f' ({media.year})' if media.year else '')
            details = f'Looking at {display_title}'
            state = select_genres(media, self._settings.genre_limit)
        else:
            details = f'Viewing {title}' if title else f'Browsing {labels.get(page, "Jellyfin")}'
            state = ''
        server_name = self._client.server_name if self._settings.show_server_name else 'Jellyfin'
        try:
            self._rpc.update(
                activity_type=ActivityType.WATCHING,
                name=server_name[:128],
                details=details[:128],
                state=state[:128] if state else None,
                large_image=(normalize_public_image(poster) if poster else '') or (
                    'https://raw.githubusercontent.com/GhostyGang/ghostyflix-rpc/main/assets/icon.png'
                ),
                large_text=(
                    f'{media.title} · GhostyFlix RPC'
                    if media else 'GhostyFlix RPC · Browser activity'
                )[:128],
            )
            self._browser_signature = signature
            self._last_published = None
            self._emit('presence', active=True)
        except Exception as exc:
            self._close_rpc()
            logging.warning('Browser activity update failed: %s', str(exc)[:300])
        return True

    def _publish(self, media: MediaSession, poster: str) -> None:
        now_mono = time.monotonic()
        if not self._ensure_rpc():
            return
        playback_changed = self._last_playback is None or self._last_playback.item_id != media.item_id
        state_changed = self._last_playback is None or self._last_playback.paused != media.paused
        elapsed_since_update = max(0, now_mono - self._last_update_time)
        expected_position = self._last_position + int(elapsed_since_update)
        sought = (
            not media.paused
            and self._last_published is not None
            and abs(media.position_seconds - expected_position) >= self._settings.seek_threshold
        )
        refresh_progress = self._settings.show_progress_text and now_mono - self._last_update_time >= 60
        buttons = self._artwork.activity_links(media, self._settings)
        signature = (
            media.item_id, media.paused, poster, self._settings.show_playback_badge,
            self._settings.badge_color, self._settings.show_progress_text,
            self._settings.show_server_name, self._settings.genre_limit,
            self._settings.show_jellyfin_logo, tuple((button['label'], button['url']) for button in buttons),
        )
        if not (playback_changed or state_changed or sought or refresh_progress or signature != self._last_published):
            self._last_playback = media
            return
        details, state, activity_type = self._activity_text(media)
        badge = self._badge_url(media.paused, self._settings.badge_color)
        badge_published = self._settings.show_playback_badge
        start: int | None = None
        end: int | None = None
        if not media.paused and media.duration_seconds:
            now_epoch = int(time.time())
            start = now_epoch - media.position_seconds
            end = now_epoch + media.remaining_seconds
        try:
            logo_url = 'https://raw.githubusercontent.com/GhostyGang/ghostyflix-rpc/main/assets/icon.png'
            small_image = badge if self._settings.show_playback_badge else (
                logo_url if self._settings.show_jellyfin_logo else None
            )
            small_text = (
                ('Paused' if media.paused else 'Playing') + ' · GhostyFlix RPC'
                if self._settings.show_playback_badge else
                ('GhostyFlix RPC' if self._settings.show_jellyfin_logo else None)
            )
            activity = dict(
                activity_type=activity_type,
                name=(media.server_name if self._settings.show_server_name else 'Jellyfin')[:128],
                details=details[:128],
                state=state[:128] if state else None,
                large_image=normalize_public_image(poster) or 'https://raw.githubusercontent.com/GhostyGang/ghostyflix-rpc/main/assets/icon.png',
                large_text=f'{media.title} · GhostyFlix RPC'[:128],
                small_image=small_image,
                small_text=small_text,
                buttons=buttons or None,
                start=start,
                end=end,
            )
            try:
                self._rpc.update(**activity)
            except Exception as first_error:
                logging.warning('Discord rejected the full presence payload: %s', str(first_error)[:300])
                if not self._settings.show_playback_badge:
                    raise
                # A custom badge image must never prevent the movie activity
                # itself from reaching Discord. Retry without the small image.
                activity['small_image'] = None
                activity['small_text'] = None
                try:
                    self._rpc.update(**activity)
                except Exception as fallback_error:
                    logging.warning('Discord also rejected presence without the badge: %s', str(fallback_error)[:300])
                    raise fallback_error from first_error
                logging.warning('Discord activity is live without its playback badge.')
                badge_published = False
            self._last_position = media.position_seconds
            self._last_update_time = now_mono
            self._last_published = signature
            self._last_playback = media
            if badge_published:
                logging.info('Discord activity published with playback badge.')
            self._emit('presence', active=True)
        except Exception as exc:
            self._close_rpc()
            logging.warning('Discord presence update failed: %s', str(exc)[:300])
            self._status(f'Discord presence could not be updated: {exc}')

    def _activity_text(self, media: MediaSession) -> tuple[str, str, ActivityType]:
        if media.media_type == 'Music':
            details = f'Listening to {media.title}'
            state = ' · '.join(value for value in (media.artist, media.album) if value)
            activity_type = ActivityType.LISTENING
        elif media.media_type == 'Episode':
            details = f'Watching {media.title}'
            state = media.subtitle
            activity_type = ActivityType.WATCHING
        else:
            year = f' ({media.year})' if media.year else ''
            details = f'Watching {media.title}{year}'
            state = select_genres(media, self._settings.genre_limit)
            activity_type = ActivityType.WATCHING
        extras: list[str] = []
        if self._settings.show_progress_text and media.duration_seconds:
            percent = int(media.progress * 100)
            verb = 'listened' if media.media_type == 'Music' else 'watched'
            extras.extend((f'{percent}% {verb}', f'{format_clock(media.remaining_seconds)} left'))
        if media.paused:
            extras.insert(0, 'Paused')
        if state:
            extras.append(state)
        state = ' · '.join(extras)
        return details, state, activity_type

    @staticmethod
    def _badge_url(paused: bool, color: str) -> str:
        candidate = color.lstrip('#')
        safe = candidate if len(candidate) == 6 and all(char in '0123456789abcdefABCDEF' for char in candidate) else 'FF7628'
        symbol = 'II' if paused else '▶'
        font = 'montserrat' if paused else 'source-sans-pro'
        url = f'https://placehold.co/128x128/{safe}/000000.png?text={quote(symbol, safe="")}&font={font}'
        if len(url) > 300:
            raise ValueError('Playback badge URL exceeds Discord’s 300-character image limit.')
        return url

    def _ensure_rpc(self) -> bool:
        if self._rpc:
            return True
        try:
            self._rpc = Presence(DISCORD_APPLICATION_ID)
            self._rpc.connect()
            self._emit('discord', connected=True)
            return True
        except Exception as exc:
            self._rpc = None
            logging.warning('Discord RPC connection failed: %s', str(exc)[:300])
            if time.monotonic() - self._last_update_time > 10:
                self._status(f'Open Discord desktop to publish your activity ({type(exc).__name__}).')
                self._last_update_time = time.monotonic()
            return False

    def _clear_presence(self) -> None:
        if self._rpc:
            try:
                self._rpc.clear()
            except Exception:
                self._close_rpc()
        self._browser_signature = None
        self._emit('presence', active=False)

    def _close_rpc(self) -> None:
        rpc, self._rpc = self._rpc, None
        if rpc:
            try:
                rpc.clear()
            except Exception:
                pass
            try:
                rpc.close()
            except Exception:
                pass
