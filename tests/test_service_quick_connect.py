import time
import unittest
from unittest.mock import patch

from ghostyflix_rpc.service import PlaybackService
from ghostyflix_rpc.settings import Settings


class PlaybackServiceQuickConnectTests(unittest.TestCase):
    def test_quick_connect_returns_code_to_ui(self) -> None:
        service = PlaybackService(Settings())
        with patch('ghostyflix_rpc.service.JellyfinClient') as client_type:
            client_type.return_value.initiate_quick_connect.return_value = {
                'Code': 'ABC123', 'Secret': 'secret-value'
            }

            service._handle_command('quick', 'https://media.example.com')

        event = service.events.get_nowait()
        while event['type'] != 'quick_code':
            event = service.events.get_nowait()
        self.assertEqual(event['code'], 'ABC123')
        self.assertEqual(service._quick_secret, 'secret-value')

    def test_quick_connect_failures_are_reported_as_visible_quick_errors(self) -> None:
        service = PlaybackService(Settings())
        with patch('ghostyflix_rpc.service.JellyfinClient') as client_type:
            client_type.return_value.initiate_quick_connect.side_effect = RuntimeError('server rejected request')
            service.start()
            service.connect_quick('https://media.example.com')

            event = None
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                try:
                    event = service.events.get(timeout=0.1)
                except Exception:
                    continue
                if event.get('type') == 'quick_error':
                    break

            service.close()

        self.assertIsNotNone(event)
        self.assertEqual(event['type'], 'quick_error')
        self.assertEqual(event['text'], 'server rejected request')

    def test_poll_error_keeps_issued_code_available_for_copy(self) -> None:
        service = PlaybackService(Settings())
        service._quick_secret = 'secret-value'
        service._client = type('Client', (), {
            'quick_connect_approved': lambda _self, _secret: (_ for _ in ()).throw(RuntimeError('poll failed'))
        })()

        service._poll_quick_connect()

        event = service.events.get_nowait()
        self.assertEqual(event['type'], 'quick_error')
        self.assertTrue(event['preserve_code'])
        self.assertIn('poll failed', event['text'])

    def test_disconnect_clears_saved_credentials_and_notifies_ui(self) -> None:
        settings = Settings(
            jellyfin_token='session-token', jellyfin_api_key='api-key',
            jellyfin_user_id='user-id', jellyfin_username='Ghosty',
        )
        service = PlaybackService(settings)
        with patch.object(Settings, 'save') as save:
            service._handle_command('disconnect', None)

        save.assert_called_once()
        self.assertEqual(settings.jellyfin_token, '')
        self.assertEqual(settings.jellyfin_api_key, '')
        self.assertEqual(settings.jellyfin_user_id, '')
        self.assertEqual(settings.jellyfin_username, '')
        event_types = []
        while not service.events.empty():
            event_types.append(service.events.get_nowait()['type'])
        self.assertIn('disconnected', event_types)


if __name__ == '__main__':
    unittest.main()
