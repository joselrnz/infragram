"""Artwork too dark for a dark ground is drawn light, in both renderers.

The built-in line icons are painted in a near-black ink and many vendor
marks are black artwork: on a dark canvas a router, a firewall or a brand
mark all but vanished. The editor measures each icon in the page; the static
renderer cannot rasterise anything, so it reads the measurement the ink table
carries (``tones``, written by ``scripts/tools/ink-profiles.py`` and checked
in CI by the same tool) and draws those icons through the same filter.

Both renderers answer from one measurement, so a picture and the canvas it
was drawn on cannot disagree about which artwork needed the treatment.
"""

from __future__ import annotations

import importlib

import pytest

from infragram.builders.architecture import load_theme
from infragram.catalog import ink
from infragram.catalog.components import primitive_icon_svg
from infragram.exports import render_project_svg
from infragram.exports.palette import dark
from infragram.exports.render import _scene_for
from infragram.paths import skill_assets
from infragram.projects import CloudProject

render_module = importlib.import_module("infragram.builders.render")

TEMPLATE = skill_assets() / "templates" / "cloud" / "hybrid-bgp-edge.infragram.json"


@pytest.fixture(scope="module")
def project() -> CloudProject:
    return CloudProject.load(TEMPLATE)


def test_the_shipped_table_knows_the_line_icons_are_dark() -> None:
    """They are drawn in ``PRIMITIVE_INK``, a near-black: the case that
    started this. A table rebuilt without its tones fails here."""
    measured = [
        icon_id
        for icon_id in ("server", "router", "firewall", "switch")
        if _artwork(icon_id) is not None
    ]
    assert measured, "the shared set ships these"
    for icon_id in measured:
        assert ink.is_dark(_artwork(icon_id)), f"{icon_id} is drawn in the near-black ink"


def _artwork(icon_id: str) -> bytes | None:
    try:
        return primitive_icon_svg(icon_id)
    except KeyError:
        return None


def test_artwork_that_reads_on_a_dark_ground_is_left_alone() -> None:
    aws = sorted((skill_assets() / "icons" / "vendors" / "aws").rglob("*.svg"))
    assert aws, "the AWS library ships artwork"
    assert [path for path in aws if not ink.is_dark(path.read_bytes())], (
        "AWS's own colours read on a dark ground"
    )


def test_nothing_unmeasured_is_called_dark() -> None:
    assert ink.is_dark(b"") is False
    assert (
        ink.is_dark(b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="8" height="8"/></svg>')
        is False
    )


def test_the_colour_decides_not_the_shape() -> None:
    """A profile is keyed by shape, so a recoloured copy shares it; a tone is
    keyed by colour, because colour is the whole question."""
    artwork = primitive_icon_svg("server")
    lighter = artwork.replace(b"#16191f", b"#e8e8e8")
    assert ink.artwork_key(artwork) == ink.artwork_key(lighter)
    assert ink.tone_key(artwork) != ink.tone_key(lighter)
    assert ink.is_dark(artwork) and not ink.is_dark(lighter)


def test_a_dark_picture_draws_its_dark_artwork_light() -> None:
    # a drawing that places one dark glyph on two cards, to show the symbol is shared
    project = CloudProject.load(TEMPLATE.with_name("onprem-dr-backup.infragram.json"))
    scene = _scene_for(project, theme="dark")
    dark_nodes = [
        node
        for node in scene.root.walk()
        if node.icon is not None
        and ink.is_dark(
            (node.icon.markup or node.icon.path.read_text(encoding="utf-8")).encode("utf-8")
        )
    ]
    assert dark_nodes, "this drawing places artwork that needs it"
    svg = render_project_svg(project, background="paper", theme="dark")
    assert svg.count(f'<filter id="{render_module.INK_ON_DARK}"') == 1, "defined once"
    # one filtered use per card that draws such artwork; the symbols behind
    # them are still shared, so two cards with one icon emit one symbol
    assert svg.count(f'filter="url(#{render_module.INK_ON_DARK})"') == len(dark_nodes)
    drawings = {node.icon.slug for node in dark_nodes}
    assert len(drawings) < len(dark_nodes), "this drawing repeats one of them"


def test_a_frames_badge_is_left_as_its_tab_draws_it(project: CloudProject) -> None:
    """A badge sits on the frame's own tab, often a light one, where turning
    its lightness over would hide it -- the editor leaves it alone there."""
    import re

    svg = render_project_svg(project, background="paper", theme="dark")
    tabs = re.findall(r'<use href="#(icon-[^"]+)"[^>]*color="[^"]*"[^>]*/>', svg)
    filtered = re.findall(r'<use href="#([^"]+)"[^>]*filter="url\(#infragram-ink-on-dark\)"', svg)
    assert not set(tabs) & set(filtered), sorted(set(tabs) & set(filtered))


def test_a_light_picture_never_draws_through_the_filter(project: CloudProject) -> None:
    assert render_module.INK_ON_DARK not in render_project_svg(project, background="paper")


def test_a_dark_palette_says_it_is_dark() -> None:
    assert load_theme("onprem").dark is False
    assert dark(load_theme("onprem")).dark is True
