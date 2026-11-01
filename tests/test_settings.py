import unittest
from pathlib import Path
from unittest.mock import patch

from ghostyflix_rpc.settings import Settings


class SettingsTests(unittest.TestCase):
    def test_new_settings_minimize_to_tray_on_close_by_default(self) -> None:
        self.assertTrue(Settings().close_to_tray)

    def test_saved_close_behavior_is_respected(self) -> None:
        config = Path.cwd() / '.test-ghostyflix-settings.ini'
        try:
            config.write_text('[DEFAULT]\nclose_to_tray = false\n', encoding='utf-8')
            with patch('ghostyflix_rpc.settings.settings_path', return_value=config):
                self.assertFalse(Settings.load().close_to_tray)
        finally:
            config.unlink(missing_ok=True)


if __name__ == '__main__':
    unittest.main()
