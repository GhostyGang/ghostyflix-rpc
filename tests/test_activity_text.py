import unittest
from unittest.mock import Mock

from ghostyflix_rpc.jellyfin import MediaSession
from ghostyflix_rpc.settings import Settings
from ghostyflix_rpc.service import PlaybackService


def make_movie(*, paused: bool = False) -> MediaSession:
    return MediaSession(
        item_id='movie-1',
        media_type='Movie',
        title='Example Feature',
        subtitle='',
        year=2026,
        genres=['Drama', 'Mystery'],
        position_seconds=4608,
        duration_seconds=7200,
        paused=paused,
        server_name='GhostyFlix',
    )


class ActivityTextTests(unittest.TestCase):
    def test_progress_and_remaining_time_are_in_discord_state(self) -> None:
        service = PlaybackService(Settings(show_progress_text=True, genre_limit=1))

        details, state, _ = service._activity_text(make_movie())

        self.assertEqual(details, 'Watching Example Feature (2026)')
        self.assertTrue(state.startswith('64% watched · 43 min left · Drama'))

    def test_progress_stays_visible_when_paused_and_metadata_is_long(self) -> None:
        service = PlaybackService(Settings(show_progress_text=True, show_server_name=True))
        media = make_movie(paused=True)
        media.subtitle = 'A long metadata description ' * 12

        _, state, _ = service._activity_text(media)
        discord_state = state[:128]

        self.assertTrue(discord_state.startswith('Paused · 64% watched · 43 min left'))

    def test_disabling_discord_progress_hides_it_from_activity_state(self) -> None:
        service = PlaybackService(Settings(show_progress_text=False))

        _, state, _ = service._activity_text(make_movie())

        self.assertNotIn('watched', state)
        self.assertNotIn('left', state)

    def test_server_name_is_not_appended_after_genres(self) -> None:
        service = PlaybackService(Settings(show_progress_text=True, show_server_name=True))

        _, state, _ = service._activity_text(make_movie())

        self.assertTrue(state.endswith('Drama'))
        self.assertNotIn('GhostyFlix', state)

    def test_enabled_server_name_is_used_as_discord_activity_headline(self) -> None:
        service = PlaybackService(Settings(show_server_name=True))
        service._rpc = Mock()
        service._ensure_rpc = lambda: True

        service._publish(make_movie(), '')

        self.assertEqual(service._rpc.update.call_args.kwargs['name'], 'GhostyFlix')

    def test_playback_badges_use_black_ascii_marks_and_roboto(self) -> None:
        playing = PlaybackService._badge_url(paused=False, color='#FF7628')
        paused = PlaybackService._badge_url(paused=True, color='#FF7628')

        self.assertIn('/FF7628/111111.png', playing)
        self.assertIn('text=%3E&font=roboto', playing)
        self.assertIn('text=%7C%7C&font=roboto', paused)


if __name__ == '__main__':
    unittest.main()
