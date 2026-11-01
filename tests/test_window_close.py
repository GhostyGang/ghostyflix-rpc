import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from ghostyflix_rpc.app import GhostyFlixApp
from ghostyflix_rpc.settings import Settings


class WindowCloseTests(unittest.TestCase):
    def test_close_hides_to_tray_when_enabled(self) -> None:
        app = SimpleNamespace(
            settings=Settings(close_to_tray=True),
            _hide_to_tray=Mock(),
            _exit_app=Mock(),
        )

        GhostyFlixApp._on_close(app)

        app._hide_to_tray.assert_called_once_with()
        app._exit_app.assert_not_called()

    def test_close_exits_when_tray_behavior_is_disabled(self) -> None:
        app = SimpleNamespace(
            settings=Settings(close_to_tray=False),
            _hide_to_tray=Mock(),
            _exit_app=Mock(),
        )

        GhostyFlixApp._on_close(app)

        app._exit_app.assert_called_once_with()
        app._hide_to_tray.assert_not_called()


if __name__ == '__main__':
    unittest.main()
