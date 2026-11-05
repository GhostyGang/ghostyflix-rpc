from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Any, Callable
from urllib.parse import urlsplit


class BrowserActivityBridge:
    """Small loopback-only endpoint for the optional browser companion."""

    def __init__(self, receive: Callable[[dict[str, Any]], None], port: int = 47861) -> None:
        self._receive = receive
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None
        self._port = port

    def start(self) -> None:
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format: str, *_args: Any) -> None:
                return

            def _reply(self, status: int, origin: str = '') -> None:
                self.send_response(status)
                if origin.startswith(('chrome-extension://', 'moz-extension://', 'safari-web-extension://')):
                    self.send_header('Access-Control-Allow-Origin', origin)
                    self.send_header('Vary', 'Origin')
                    self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
                    self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                    # Chromium may treat an extension request to loopback as a
                    # private-network request and require this preflight header.
                    self.send_header('Access-Control-Allow-Private-Network', 'true')
                self.send_header('Content-Length', '0')
                self.end_headers()

            def do_OPTIONS(self) -> None:
                origin = self.headers.get('Origin', '')
                if self.path == '/v1/activity' and origin.startswith(('chrome-extension://', 'moz-extension://', 'safari-web-extension://')):
                    self._reply(204, origin)
                else:
                    self._reply(403)

            def do_POST(self) -> None:
                origin = self.headers.get('Origin', '')
                host = self.headers.get('Host', '')
                if host not in {f'127.0.0.1:{bridge._port}', f'localhost:{bridge._port}'}:
                    self._reply(403)
                    return
                if self.path != '/v1/activity' or not origin.startswith(('chrome-extension://', 'moz-extension://', 'safari-web-extension://')):
                    self._reply(403)
                    return
                try:
                    length = min(4096, max(0, int(self.headers.get('Content-Length', '0'))))
                    body = json.loads(self.rfile.read(length))
                    if not isinstance(body, dict):
                        raise ValueError('Expected an object')
                    bridge._receive(body)
                except (ValueError, TypeError, json.JSONDecodeError):
                    self._reply(400, origin)
                    return
                self._reply(202, origin)

        try:
            self._server = ThreadingHTTPServer(('127.0.0.1', self._port), Handler)
            self._server.daemon_threads = True
        except OSError as exc:
            logging.warning('Browser activity bridge could not start: %s', exc)
            return
        self._thread = Thread(target=self._server.serve_forever, name='GhostyFlix browser bridge', daemon=True)
        self._thread.start()

    def close(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1)
        self._thread = None


def normalized_origin(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        return ''
    return f'{parsed.scheme}://{parsed.netloc}'.lower()
