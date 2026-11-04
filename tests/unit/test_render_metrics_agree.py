"""Both renderers read one set of numbers.

A document is drawn twice: by this package, and by the editor runtime inside
an exported page. They are separate implementations of the same picture, and
they had drifted -- the detour margin, the corner radius, the widest an icon
card could grow and both dash patterns all differed, so the same document drew
differently depending on which renderer produced it. These tests fail if a
number is typed into either renderer again instead of read from the file.
"""

from __future__ import annotations

import importlib
import json
import re
from pathlib import Path

from infragram.builders import metrics
from infragram.builders.routing import Router
from infragram.builders.scene import GLYPH_TOP, NodeStyle, Style
from infragram.editor.bundle import runtime_script

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
RUNTIME = runtime_script()


def test_the_python_renderer_takes_its_numbers_from_the_file() -> None:
    router, icon, dashes = metrics.router(), metrics.icon_node(), metrics.link_dashes()
    live = Router()
    assert (live.clearance, live.stub, live.margin, live.turn_cost, live.radius) == (
        router["clearance"],
        router["stub"],
        router["margin"],
        router["turn_cost"],
        router["radius"],
    )
    style = Style()
    # The two ceilings are different things: a card with a text lane grows
    # further than a bare glyph, and only the Python renderer grows one.
    assert style.node.max_width == metrics.card()["max_width"]
    assert style.node.width == metrics.card()["width"]
    assert style.node.icon_width == icon["width"]
    assert style.node.icon_height == icon["height"]
    assert style.node.icon_glyph == icon["glyph"]
    assert style.links["dashed"].dash == dashes["dashed"]
    assert style.links["dotted"].dash == dashes["dotted"]


def test_the_python_renderer_sets_type_by_the_file() -> None:
    """A card's two lines, an icon's caption and every advance: the editor's
    numbers, read from the file (the runtime still types them until its next
    port; tests/integration/test_renderer_parity_browser.py holds the two
    pictures equal meanwhile)."""
    from infragram.builders import scene

    card, icon, text = metrics.card(), metrics.icon_node(), metrics.text()
    node = Style().node
    assert (
        node.title_size,
        node.detail_size,
        node.icon_size,
        node.icon_inset,
        node.text_inset,
    ) == (card["title_size"], card["detail_size"], card["icon"], card["icon_x"], card["text_x"])
    assert node.icon_detail_size == icon["detail_size"]
    assert (text["advance"], card["detail_advance"], icon["detail_advance"]) == (
        scene.TITLE_ADVANCE,
        scene.DETAIL_ADVANCE,
        scene.CAPTION_DETAIL_ADVANCE,
    )
    assert metrics.router()["grid"] == scene.GRID


def test_the_editor_runtime_reads_the_file_rather_than_repeating_it() -> None:
    """The runtime must name the spec, not the values."""
    assert "infragram-render-metrics" in RUNTIME, "the runtime reads the block the shell writes"
    for expression in (
        "METRICS.router.clearance",
        "METRICS.router.stub",
        "METRICS.router.margin",
        "METRICS.router.turn_cost",
        "METRICS.router.radius",
        "METRICS.router.straighten",
        "METRICS.icon_node.width",
        "METRICS.icon_node.max_width",
        "METRICS.link_dashes.dashed",
        "METRICS.link_dashes.dotted",
    ):
        assert expression in RUNTIME, f"the runtime should read {expression}"
    # And the old literals must be gone, or a future edit will silently split
    # the two renderers again.
    icon, dashes = metrics.icon_node(), metrics.link_dashes()
    for literal in (
        f"maxWidth: {icon['max_width']}",
        f"'{dashes['dashed']}'",
        f"'{dashes['dotted']}'",
    ):
        assert literal not in RUNTIME, f"{literal} is typed into the runtime instead of read"


def test_the_page_carries_the_same_numbers_the_package_uses() -> None:
    from infragram import compose
    from infragram.exports import render_project_html
    from infragram.nodes import infragram as shared, reset_ids
    from infragram.nodes.aws import networking_content_delivery as net

    reset_ids()
    internet = shared.networking.PublicInternet("Internet", "public")
    nat = net.VPCNATGateway("NAT gateway", "outbound")
    internet.to(nat, label="egress")
    html = render_project_html(
        compose.to_project([internet, nat], slug="m", title="M", description="m.", display="card")
    )
    block = re.search(r'id="infragram-render-metrics">(.*?)</script>', html, re.S)
    assert block, "the shell writes the metrics into the page"
    assert json.loads(block.group(1)) == metrics.spec()


def test_the_static_straighten_is_the_shared_metric() -> None:
    render_module = importlib.import_module("infragram.builders.render")
    assert metrics.router()["straighten"] == render_module.STRAIGHTEN


def test_cards_are_the_same_height_in_both_renderers() -> None:
    assert NodeStyle().height == metrics.card()["height"] == 64
    source = RUNTIME
    assert "ICON_NODE.height : CARD_HEIGHT" in source and "ICON_NODE.height : 72" not in source


def test_the_glyph_top_is_one_number_read_by_both_renderers() -> None:
    assert metrics.icon_node()["glyph_top"] == GLYPH_TOP
    source = RUNTIME
    assert source.count("captioned ? ICON_NODE.glyphTop") == 2 and "captioned ? 6" not in source
