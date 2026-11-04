"""Items rendered by spec: the spec is checked against the builder, the render
is cached by its hash, and the element carries what every renderer needs.

These tests seed the cache instead of rendering, so they need no browser;
``tests/integration/test_iso_render.py`` renders for real.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from infragram.author import Diagram
from infragram.builders.architecture import display_of, icon_for
from infragram.catalog import ink
from infragram.iso3d import cache
from infragram.iso3d.api import SpecError, build_spec
from infragram.iso3d.render import spec_hash, wrap
from infragram.iso3d.vocabulary import FAMILY_COLOURS, recipes
from infragram.projects import CloudProject

# a 1x1 transparent PNG, enough to stand in for a render
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
EDGES = "|".join("A" * 33 for _ in range(4)).replace("A", "K", 1)


def test_the_spec_is_the_builders_own_signature() -> None:
    spec = build_spec("server", family="storage", glyph="database", units=3, drivesN=12)
    assert (
        spec["recipe"] == "server"
        and spec["args"] == [3, 12]
        and spec["colour"] == FAMILY_COLOURS["storage"]
    )
    assert spec["glyph"].startswith("M")
    # trailing defaults are dropped so the same look hashes the same
    assert build_spec("server", units=2)["args"] == []
    assert build_spec("server", badge=False)["glyph"] == ""
    assert build_spec("reactor", family="energy", kind="smr")["args"] == ["smr"]
    assert "server" in recipes() and ("units", 2) in recipes()["server"]


@pytest.mark.parametrize(
    "bad",
    [
        dict(recipe="no-such-thing"),
        dict(recipe="server", bays=4),
        dict(recipe="server", family="lava"),
        dict(recipe="server", colour="red"),
        dict(recipe="server", glyph="no-such-glyph"),
    ],
)
def test_a_spec_the_builder_cannot_build_is_refused(bad: dict) -> None:
    with pytest.raises(SpecError):
        build_spec(**bad)


def _seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, spec: dict) -> str:
    monkeypatch.setenv("INFRAGRAM_CACHE", str(tmp_path))
    digest = spec_hash(spec)
    cache.svg_path(digest).write_text(wrap(PNG), encoding="utf-8")
    cache.write_ink(digest, {"profile": [0.1, 0.1, 0.2, 0.2], "edges": EDGES})
    return digest


def test_a_cached_render_needs_no_browser_and_travels_with_the_element(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from infragram.nodes.iso import Iso

    spec = build_spec("server", family="storage", glyph="database", units=3, drivesN=12)
    digest = _seed(tmp_path, monkeypatch, spec)
    with Diagram("Spec", "one rendered item", slug="spec-test", providers=("onprem",)) as diagram:
        node = Iso(
            "DB-01",
            "PostgreSQL",
            recipe="server",
            family="storage",
            glyph="database",
            units=3,
            drivesN=12,
        )
    project = diagram.to_project()
    element = next(e for e in project.topology.walk() if e.name == "DB-01")
    assert element.component is not None and element.component.icon_ref == "infragram:custom-3d"
    assert element.attributes["iso"] == spec and element.attributes["iso_hash"] == digest
    assert (
        element.attributes["iso_artwork"].startswith("<svg")
        and "data:image/png;base64," in element.attributes["iso_artwork"]
    )
    assert element.attributes["iso_ink"]["edges"] == EDGES
    assert node.id  # the node exists in the authoring tree
    # the static resolver draws the carried artwork and seats on its measurement
    icon = icon_for(element)
    assert (
        icon is not None
        and icon.markup == element.attributes["iso_artwork"]
        and icon.slug.startswith("iso3d-")
    )
    assert display_of(element, icon=icon) == "icon"
    assert ink.edges(icon.markup.encode("utf-8")) == EDGES
    # the document round-trips with everything in it
    again = CloudProject.model_validate(json.loads(project.model_dump_json()))
    assert (
        next(e for e in again.topology.walk() if e.name == "DB-01").attributes["iso_hash"] == digest
    )


def test_the_export_carries_the_render_not_the_palette_plate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from infragram.exports import render_project_html
    from infragram.nodes.iso import Iso

    spec = build_spec("switch", colour="#0f766e", glyph="arrows", count=48)
    _seed(tmp_path, monkeypatch, spec)
    with Diagram("Spec", "one rendered item", slug="spec-export", providers=("onprem",)) as diagram:
        Iso("Core", "48 ports", recipe="switch", colour="#0f766e", glyph="arrows", count=48)
    html = render_project_html(diagram.to_project())
    import re

    state = json.loads(
        re.search(r'id="infragram-editor-state"[^>]*>(.*?)</script>', html, re.S).group(1)
    )
    node = next(n for n in state["nodes"] if n["name"] == "Core")
    assert node["iconUri"].startswith(
        "data:image/svg+xml;charset=utf-8,"
    ) and "image%2Fpng" in node["iconUri"].replace("/", "%2F")
    assert node["displayMode"] == "icon" and node["inkEdges"] == EDGES
    assert node["attributes"]["iso_artwork"].startswith("<svg")
