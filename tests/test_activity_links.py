import unittest
from unittest.mock import Mock

from ghostyflix_rpc.artwork import ArtworkLookup
from ghostyflix_rpc.jellyfin import MediaSession
from ghostyflix_rpc.settings import Settings
from ghostyflix_rpc.service import PlaybackService


def make_movie() -> MediaSession:
    return MediaSession(
        item_id='movie-1', media_type='Movie', title='Example Feature', subtitle='',
        year=2026, genres=['Drama'], position_seconds=120, duration_seconds=7200,
        paused=False, server_name='GhostyFlix', imdb_id='tt1234567', tmdb_id='42',
    )


class ActivityLinksTests(unittest.TestCase):
    def test_links_are_two_compact_buttons_and_prefer_official_english_trailer(self) -> None:
        lookup = ArtworkLookup()
        response = Mock()
        response.json.return_value = {'results': [
            {'site': 'YouTube', 'type': 'Trailer', 'key': 'unofficial', 'official': False, 'iso_639_1': 'en'},
            {'site': 'YouTube', 'type': 'Trailer', 'key': 'official', 'official': True, 'iso_639_1': 'en'},
            {'site': 'Vimeo', 'type': 'Trailer', 'key': 'other'},
        ]}
        lookup.http.get = Mock(return_value=response)
        settings = Settings(tmdb_api_key='test-key')

        buttons = lookup.activity_links(make_movie(), settings)

        self.assertEqual(buttons, [
            {'label': 'IMDb', 'url': 'https://www.imdb.com/title/tt1234567/'},
            {'label': 'Trailer', 'url': 'https://www.youtube.com/watch?v=official'},
        ])
        self.assertEqual(len(buttons), 2)

    def test_missing_tmdb_video_uses_clearly_labeled_search(self) -> None:
        lookup = ArtworkLookup()
        buttons = lookup.activity_links(make_movie(), Settings(tmdb_api_key=''))

        self.assertEqual(buttons[1]['label'], 'Trailer search')
        self.assertIn('youtube.com/results?search_query=', buttons[1]['url'])

    def test_link_metadata_is_cached_per_playing_item(self) -> None:
        lookup = ArtworkLookup()
        response = Mock()
        response.json.return_value = {'results': []}
        lookup.http.get = Mock(return_value=response)
        settings = Settings(tmdb_api_key='test-key')

        first = lookup.activity_links(make_movie(), settings)
        second = lookup.activity_links(make_movie(), settings)

        self.assertEqual(first, second)
        self.assertEqual(lookup.http.get.call_count, 1)

    def test_disabled_links_and_music_do_not_add_buttons(self) -> None:
        lookup = ArtworkLookup()
        self.assertEqual(lookup.activity_links(make_movie(), Settings(show_imdb_button=False, show_trailer_button=False)), [])
        music = make_movie()
        music.media_type = 'Music'
        self.assertEqual(lookup.activity_links(music, Settings()), [])

    def test_activity_text_stays_compact_when_buttons_are_enabled(self) -> None:
        settings = Settings(show_imdb_button=True, show_trailer_button=True)
        service = PlaybackService(settings)
        service._rpc = Mock()
        service._ensure_rpc = lambda: True
        service._artwork.activity_links = Mock(return_value=[
            {'label': 'IMDb', 'url': 'https://www.imdb.com/title/tt1234567/'},
            {'label': 'Trailer', 'url': 'https://www.youtube.com/watch?v=official'},
        ])

        service._publish(make_movie(), '')

        call = service._rpc.update.call_args.kwargs
        self.assertEqual(call['buttons'][0]['label'], 'IMDb')
        self.assertEqual(len(call['buttons']), 2)
        self.assertNotIn('IMDb', call['details'])
        self.assertNotIn('Trailer', call['state'])


if __name__ == '__main__':
    unittest.main()
