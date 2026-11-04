"""The 3D renderer's worker thread never holds a caller for good.

A browser that never came up used to be cached as the worker after a
90-second wait, and every later render then blocked on a future nothing
would complete. Both waits are bounded by the render budget now, a dead
worker is never cached, and a stuck one is discarded so the next call
starts afresh. No browser is involved: the Renderer is replaced with one
that never becomes ready, or one whose job never answers.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from infragram.iso3d import api


@pytest.fixture
def no_cached_worker(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(api, "_worker", None)
    release = threading.Event()
    yield release
    # let whichever stand-in renderer the test left blocked run to its end
    release.set()
    monkeypatch.setattr(api, "_worker", None)


def _never_ready(release: threading.Event):
    class Stuck:
        def __enter__(self):
            release.wait()
            raise RuntimeError("released by the test")

        def __exit__(self, *exc) -> bool:
            return False

    return Stuck


def _ready_but_deaf():
    class Ready:
        def __enter__(self):
            return self

        def __exit__(self, *exc) -> bool:
            return False

    return Ready


def test_a_renderer_that_never_becomes_ready_is_refused_and_not_cached(
    monkeypatch: pytest.MonkeyPatch,
    no_cached_worker: threading.Event,
) -> None:
    monkeypatch.setattr(api, "Renderer", _never_ready(no_cached_worker))
    started = time.monotonic()
    with pytest.raises(RuntimeError, match="did not start within the render budget"):
        api._renderer_thread(timeout=0.2)
    assert time.monotonic() - started < 5, "the wait is the timeout given, not 90 s"
    assert api._worker is None, "a dead worker is never cached"


def test_a_renderer_that_failed_to_start_says_why(
    monkeypatch: pytest.MonkeyPatch,
    no_cached_worker: threading.Event,
) -> None:
    class Broken:
        def __enter__(self):
            raise RuntimeError("scene.js did not load")

        def __exit__(self, *exc) -> bool:
            return False

    monkeypatch.setattr(api, "Renderer", Broken)
    with pytest.raises(RuntimeError, match="did not start: scene.js did not load"):
        api._renderer_thread(timeout=5)
    assert api._worker is None


def test_a_render_that_never_answers_is_bounded_and_the_worker_discarded(
    monkeypatch: pytest.MonkeyPatch,
    no_cached_worker: threading.Event,
) -> None:
    monkeypatch.setattr(api, "Renderer", _ready_but_deaf())
    worker = api._renderer_thread(timeout=5)
    assert api._worker is worker
    started = time.monotonic()
    with pytest.raises(RuntimeError, match="did not answer within the render budget"):
        worker.submit(lambda renderer: no_cached_worker.wait(), timeout=0.2)
    assert time.monotonic() - started < 5
    assert api._worker is None, "the next render starts a fresh worker"


def test_the_budget_reaches_the_node_through_the_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    no_cached_worker: threading.Event,
) -> None:
    """``Iso(...)`` takes no timeout of its own; the exporter's variable is the knob."""
    from infragram.nodes.iso import Iso

    monkeypatch.setenv("INFRAGRAM_CACHE", str(tmp_path))
    monkeypatch.setenv("INFRAGRAM_RENDER_TIMEOUT_MS", "1000")  # the floor is one second
    monkeypatch.setattr(api, "Renderer", _never_ready(no_cached_worker))
    started = time.monotonic()
    with pytest.raises(RuntimeError, match="render budget"):
        Iso("DB-01", recipe="server", family="storage", units=1)
    assert time.monotonic() - started < 10
    assert api._worker is None


def test_render_cached_takes_an_explicit_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    no_cached_worker: threading.Event,
) -> None:
    monkeypatch.setenv("INFRAGRAM_CACHE", str(tmp_path))
    monkeypatch.setattr(api, "Renderer", _never_ready(no_cached_worker))
    spec = api.build_spec("server", units=1)
    with pytest.raises(RuntimeError, match="render budget"):
        api.render_cached(spec, timeout=0.2)
