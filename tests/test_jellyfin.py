import unittest
from unittest.mock import Mock

import requests

from ghostyflix_rpc.jellyfin import JellyfinClient


class JellyfinQuickConnectTests(unittest.TestCase):
    def test_session_sends_current_and_legacy_authorization_headers_with_device_id(self) -> None:
        client = JellyfinClient('https://media.example.com', 'api-token', device_id='device-123')

        self.assertEqual(
            client.http.headers['Authorization'],
            'MediaBrowser Client="GhostyFlix RPC", Device="Desktop", DeviceId="device-123", '
            'Version="2.0.0", Token="api-token"',
        )
        self.assertEqual(client.http.headers['X-Emby-Authorization'], client.http.headers['Authorization'])
        self.assertEqual(client.http.headers['X-Emby-Token'], 'api-token')

    def test_current_playback_uses_configured_server_name(self) -> None:
        client = JellyfinClient('https://media.example.com')
        sessions = Mock()
        sessions.raise_for_status.return_value = None
        sessions.json.return_value = [{
            'UserId': 'user-1',
            'NowPlayingItem': {'Id': 'movie-1', 'Type': 'Movie', 'Name': 'Example'},
            'PlayState': {},
            'ServerName': 'Jellyfin',
        }]
        server_info = Mock()
        server_info.raise_for_status.return_value = None
        server_info.json.return_value = {'ServerName': 'GhostyFlix'}
        client.http.get = Mock(side_effect=[sessions, server_info])

        media = client.current_playback('user-1')

        self.assertIsNotNone(media)
        self.assertEqual(media.server_name, 'GhostyFlix')
        client.http.get.assert_any_call('https://media.example.com/System/Info/Public', timeout=8)

    def test_initiate_posts_json_without_unsupported_timeout_parameter(self) -> None:
        client = JellyfinClient('https://media.example.com/jellyfin')
        response = Mock()
        response.status_code = 200
        response.json.return_value = {'Code': 'ABC123', 'Secret': 'secret-value'}
        client.http.post = Mock(return_value=response)

        result = client.initiate_quick_connect()

        self.assertEqual(result['Code'], 'ABC123')
        client.http.post.assert_called_once_with(
            'https://media.example.com/jellyfin/QuickConnect/Initiate', json={}, timeout=10
        )

    def test_initiate_explains_bad_request(self) -> None:
        client = JellyfinClient('https://media.example.com')
        response = Mock()
        response.status_code = 400
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
        client.http.post = Mock(return_value=response)

        with self.assertRaisesRegex(RuntimeError, 'server address is the Jellyfin base URL'):
            client.initiate_quick_connect()

    def test_initiate_explains_quick_connect_disabled(self) -> None:
        client = JellyfinClient('https://media.example.com')
        response = Mock()
        response.status_code = 401
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
        client.http.post = Mock(return_value=response)

        with self.assertRaisesRegex(RuntimeError, 'disabled in the server dashboard'):
            client.initiate_quick_connect()

    def test_initiate_includes_server_message_when_available(self) -> None:
        client = JellyfinClient('https://media.example.com')
        response = Mock()
        response.status_code = 400
        response.json.return_value = {'Message': 'DeviceId is required'}
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
        client.http.post = Mock(return_value=response)

        with self.assertRaisesRegex(RuntimeError, 'DeviceId is required'):
            client.initiate_quick_connect()


if __name__ == '__main__':
    unittest.main()
