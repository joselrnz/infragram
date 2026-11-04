"""``compose --watch``: draw again on every save, and tell the page.

The watcher polls the diagram file, composes each change in a fresh process
and serves one page on 127.0.0.1 that reloads when a compose succeeds and
lays the error over the last good picture when one fails.
"""

from __future__ import annotations

import contextlib
import http.client
import os
import queue
import threading
import time
from pathlib import Path

from infragram.cli.user.watch import Watcher, serve


def test_a_save_draws_again_and_a_failure_is_reported(tmp_path: Path) -> None:
    spec = tmp_path / "diagram.py"
    spec.write_text("# one\n", encoding="utf-8")
    calls: list[list[str]] = []

    def compose(arguments: list[str]) -> tuple[bool, str]:
        calls.append(arguments)
        text = spec.read_text(encoding="utf-8")
        if "broken" in text:
            return False, "ERROR: diagram.py, line 1: name 'broken' is not defined"
        (tmp_path / "out").mkdir(exist_ok=True)
        (tmp_path / "out" / "diagram.html").write_text("<html>drawn</html>", encoding="utf-8")
        return True, ""

    watcher = Watcher(spec, tmp_path / "out", ["--libraries", "drawn"], compose=compose)
    events: queue.Queue = queue.Queue()
    watcher.listeners.append(events)
    assert watcher.draw() and watcher.page == "diagram.html" and watcher.version == 1
    assert calls[0][:3] == [str(spec.resolve()), "--formats", "html"]

    stop = threading.Event()
    thread = threading.Thread(target=watcher.run, args=(stop, 0.05), daemon=True)
    thread.start()
    try:
        time.sleep(0.2)
        spec.write_text("# two, a bit longer\n", encoding="utf-8")
        os.utime(spec, (time.time() + 5, time.time() + 5))
        deadline = time.time() + 5
        while watcher.version < 2 and time.time() < deadline:
            time.sleep(0.05)
        assert watcher.version == 2, "a save draws again"
        spec.write_text("broken\n", encoding="utf-8")
        os.utime(spec, (time.time() + 10, time.time() + 10))
        seen = []
        deadline = time.time() + 5
        while "failed" not in seen and time.time() < deadline:
            with contextlib.suppress(queue.Empty):
                seen.append(events.get(timeout=0.1)[0])
        assert "failed" in seen and watcher.version == 2, "the last good picture stays"
    finally:
        stop.set()
        thread.join(timeout=2)


def test_the_page_is_served_on_loopback_only(tmp_path: Path) -> None:
    (tmp_path / "diagram.html").write_text("<html>drawn</html>", encoding="utf-8")
    watcher = Watcher(tmp_path / "diagram.py", tmp_path, [], compose=lambda _args: (True, ""))
    watcher.page, watcher.version = "diagram.html", 3
    server = serve(watcher)
    try:
        host, port = server.server_address[:2]
        assert host == "127.0.0.1"
        connection = http.client.HTTPConnection(host, port, timeout=5)
        connection.request("GET", "/")
        page = connection.getresponse().read().decode("utf-8")
        assert 'src="diagram.html?fresh=watch-3"' in page and "new EventSource('/events')" in page
        connection.request("GET", "/diagram.html")
        assert connection.getresponse().read() == b"<html>drawn</html>"
    finally:
        server.shutdown()
