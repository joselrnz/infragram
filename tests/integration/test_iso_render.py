"""A spec renders for real: headless Chromium, a measured, cached SVG."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from infragram.iso3d import cache
from infragram.iso3d.api import build_spec, render_cached

pytestmark = pytest.mark.skipif(
    os.environ.get("INFRAGRAM_RUN_BROWSER_TESTS") != "1",
    reason="set INFRAGRAM_RUN_BROWSER_TESTS=1 to run Chromium render checks",
)


def test_a_spec_renders_measures_and_caches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("INFRAGRAM_CACHE", str(tmp_path))
    spec = build_spec("server", family="storage", glyph="database", units=3, drivesN=12)
    svg, entry, digest = render_cached(spec)
    assert svg.startswith("<svg") and "data:image/png;base64," in svg
    assert entry["edges"] and len(entry["edges"].split("|")) == 4
    assert cache.svg_path(digest).is_file() and cache.ink_path(digest).is_file()
    # the second call is the cache, byte for byte
    assert render_cached(spec)[0] == svg
