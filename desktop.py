import sys
import threading
import time
from contextlib import suppress

from werkzeug.serving import make_server

from app_version import APP_NAME
import updater

import database
from app import app as flask_app


class _ServerThread(threading.Thread):
    def __init__(self, host: str, port: int):
        super().__init__(daemon=True)
        self._server = make_server(host, port, flask_app)
        self.host = host
        self.port = self._server.server_port

    def run(self) -> None:
        self._server.serve_forever()

    def shutdown(self) -> None:
        with suppress(Exception):
            self._server.shutdown()


def main() -> int:
    database.init_db()

    host = "127.0.0.1"
    port = 0  # pick a free port
    server = _ServerThread(host, port)
    server.start()

    # Give the server a moment to start and bind the port.
    time.sleep(0.1)
    url = f"http://{server.host}:{server.port}/"

    try:
        import webview  # pywebview
    except Exception:
        print("Desktop UI requires pywebview.")
        print("Install: pip install pywebview")
        print(f"Then run again. Web URL would be: {url}")
        server.shutdown()
        return 1

    try:
        # Non-blocking update check (best-effort).
        info = updater.get_update_info(timeout_s=2.0)
        if info:
            print(f"Update available: v{info.latest_version} (you have v{info.current_version})")
            print(f"Release: {info.release_url}")

        webview.create_window(APP_NAME, url, width=1200, height=800)
        webview.start(gui=None, debug=False)
    finally:
        server.shutdown()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
