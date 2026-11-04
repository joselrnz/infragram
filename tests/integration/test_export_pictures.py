"""Exported pictures: the crop keeps the legend, and an automatic caption sits on its wire."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from infragram.exports import export_project, render_project_html, render_timeout_ms
from infragram.projects import CloudProject

pytestmark = pytest.mark.skipif(
    os.environ.get("INFRAGRAM_RUN_BROWSER_TESTS") != "1",
    reason="browser suite; set INFRAGRAM_RUN_BROWSER_TESTS=1",
)

TEMPLATES = (
    Path(__file__).resolve().parents[2]
    / "plugin"
    / "skills"
    / "infragram-architect"
    / "assets"
    / "templates"
    / "cloud"
)

_LABEL_DISTANCES = """
() => {
  const svg = document.querySelector('[data-infragram-diagram]');
  const out = [];
  svg.querySelectorAll('[data-edge-label]').forEach(label => {
    const text = label.querySelector('text');
    const id = label.dataset.edgeId || label.getAttribute('data-edge-label');
    const wire = svg.querySelector(`[data-graph-edge][data-edge-id="${id}"]`);
    if (!text || !wire) return;
    // the group is translated to the caption's anchor; the text's box sits
    // around its origin, so measure from the box, not from the anchor
    const x = Number(label.dataset.labelX);
    const y = Number(label.dataset.labelY);
    const box = text.getBBox();
    const left = x + box.x, right = left + box.width, top = y + box.y, bottom = top + box.height;
    const total = wire.getTotalLength();
    let best = Infinity;
    for (let step = 0; step <= 200; step += 1) {
      const point = wire.getPointAtLength(total * step / 200);
      const dx = Math.max(left - point.x, 0, point.x - right);
      const dy = Math.max(top - point.y, 0, point.y - bottom);
      best = Math.min(best, Math.hypot(dx, dy));
    }
    out.push({id, label: text.textContent, distance: Math.round(best), wire: Math.round(total), width: Math.round(box.width)});
  });
  return out;
}
"""


def _settled(page) -> None:
    page.wait_for_load_state("load")
    page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())


def test_the_exported_picture_keeps_the_whole_legend(tmp_path: Path) -> None:
    project = CloudProject.load(TEMPLATES / "aws-site-to-site-vpn.infragram.json")
    assert project.presentation.legend, "the template carries a legend"
    result = export_project(project, tmp_path, formats=("template", "html", "svg"))
    svg = result.svg.read_text(encoding="utf-8")
    box = [float(v) for v in re.search(r'viewBox="([^"]+)"', svg).group(1).split()]
    # the DOM serialises the bare attribute as data-legend-strip=""
    strip = re.search(r'<g data-legend-strip(?:="")?>(.*?)</g>', svg, flags=re.S)
    assert strip is not None, "the legend strip travels as one group"
    lowest = max(float(y) for y in re.findall(r'\sy="([\d.]+)"', strip.group(1)))
    assert box[1] + box[3] >= lowest, (
        f"the crop ends at {box[1] + box[3]} above the legend's last line at {lowest}"
    )
    for _kind, text in project.presentation.legend:
        assert text in strip.group(1)


@pytest.mark.parametrize(
    "name", ["aws-three-tier-web", "azure-web-app-front-door", "campus-lan-wan"]
)
def test_an_automatic_caption_sits_on_its_wire(name: str, tmp_path: Path) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    source = tmp_path / f"{name}.html"
    source.write_text(
        render_project_html(CloudProject.load(TEMPLATES / f"{name}.infragram.json")),
        encoding="utf-8",
    )
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1600, "height": 1000})
            page.goto(source.resolve().as_uri())
            _settled(page)
            distances = page.evaluate(_LABEL_DISTANCES)
        finally:
            browser.close()
    assert distances, "the template has captions"
    # A caption's box sits a few pixels off its wire; a nudge off a card may
    # add a little. Thirty pixels is still beside the wire; a hundred is
    # floating. A caption wider than its whole wire -- a long name on a short
    # hop between two neighbours -- cannot sit on it and is allowed the
    # nudge above the pair, as the static picture gives it.
    far = [d for d in distances if d["distance"] > (100 if d["width"] >= d["wire"] else 30)]
    # One caption may still be pushed off by a frame title its wire hugs;
    # any more are floating in empty space.
    assert len(far) <= 1, far


def test_an_icon_written_with_xlink_exports_through_the_editor(tmp_path: Path) -> None:
    """Hetzner's RX server says ``xlink:href``. The editor serialises its
    export as HTML, which never writes that namespace down, so the export did
    not parse as XML: the SVG and the PNG silently fell back to the automatic
    layout -- a reader's own layout lost -- and the note said the runtime had
    missed a ten-second deadline it met in two."""
    import xml.etree.ElementTree as ET

    from infragram.author import Diagram
    from infragram.nodes.hetzner import compute

    with Diagram(
        "RX", "One server whose artwork uses xlink.", slug="xlink-export", providers=("hetzner",)
    ) as diagram:
        compute.RxServer("RX server", "arm64")
    result = export_project(diagram.to_project(), tmp_path, formats=("svg", "png"), overwrite=True)

    assert not result.notes, f"fell back to the automatic layout: {result.notes}"
    svg = (tmp_path / "xlink-export.svg").read_bytes()
    assert b"xlink:" in svg, "the fixture no longer exercises the prefix"
    ET.fromstring(svg)
    assert (tmp_path / "xlink-export.png").stat().st_size > 0


def test_a_wire_aimed_at_a_frame_passes_the_checker(tmp_path: Path) -> None:
    """A wire may be aimed at a frame; both renderers seat it on the card
    inside the frame nearest the other end (compose.md). The checker used to
    hold every wire to the document's own pair of ids, so it refused the
    seated wire as one the document does not connect, and ``--verify``
    failed every diagram that wired a frame."""
    from infragram.author import Diagram, Edge
    from infragram.cli.user.checker import checker
    from infragram.nodes.aws import compute, databases, networking_content_delivery as net
    from infragram.nodes.frames import aws as frames

    with Diagram(
        "Frame wires", "A transit gateway attached to two VPCs.", slug="frame-wires"
    ) as diagram:
        with frames.Cloud("AWS Cloud"), frames.Region("eu-west-1"):
            gateway = net.TransitGateway("tgw")
            with frames.VPC("a · 10.0.0.0/16") as vpc_a, frames.PrivateSubnet("app"):
                compute.EC2("web")
            with frames.VPC("b · 10.1.0.0/16") as vpc_b, frames.PrivateSubnet("data"):
                databases.RDS("db")
        gateway >> Edge("attachment") >> vpc_a
        gateway >> Edge("attachment") >> vpc_b
    result = export_project(
        diagram.to_project(),
        tmp_path,
        formats=("template", "svg"),
        overwrite=True,
        check=checker().check_path,
    )

    assert not result.notes, result.notes
    failed = [message for _name, ok, message in result.checks if not ok]
    assert not failed, failed
