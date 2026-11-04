"""A candidate recipe renders in a staged scene, is measured and seat-checked, and the package is untouched."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from infragram.iso3d import recipes
from infragram.iso3d.recipes import try_recipe

pytestmark = pytest.mark.skipif(
    os.environ.get("INFRAGRAM_RUN_BROWSER_TESTS") != "1",
    reason="set INFRAGRAM_RUN_BROWSER_TESTS=1 to run Chromium render checks",
)

SOLID = """R.crate = (fam, tex, wide = false) => {
  const g = new THREE.Group(); plate7(g, 12, 10);
  g.add(boxMesh(wide ? 10 : 6, 5, 5, glossAccent(fam.colour), 0, 2.9, 0));
  badge(g, tex, 1.6, 0, 2.9, 2.54); return g;
};
"""
BROKEN = """R.spike = (fam, tex) => {
  const g = new THREE.Group();
  g.add(boxMesh(1, 30, 1, M.metal, 0, 15, 0));
  return g.nothing.here;
};
"""


def test_a_solid_candidate_seats_on_every_side(tmp_path: Path) -> None:
    before = recipes.SCENE.read_bytes()
    report = try_recipe(SOLID, out=tmp_path, args=(True,), family="storage", glyph="disc")
    assert report.ok, report.summary()
    assert report.picture.is_file() and report.icon.is_file()
    assert report.icon.read_text(encoding="utf-8").startswith("<svg") and report.edges
    assert report.seats == {"left": "ok", "right": "ok", "top": "ok"}
    assert report.spec["args"] == [True] and report.spec["colour"] == "#0f9d8a"
    assert recipes.SCENE.read_bytes() == before, (
        "trying a candidate never touches the shipped scene"
    )


def test_a_candidate_that_throws_is_reported_not_hidden(tmp_path: Path) -> None:
    with pytest.raises(Exception, match="here|undefined|nothing"):
        try_recipe(BROKEN, out=tmp_path)
