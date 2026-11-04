"""A frame's corner badges in the editor: where the static picture draws them,
clear of the wires, and kept when the page is saved.

Both renderers seat a subnet's NSG on its top-right corner point and its
route table beside it (``CORNER_BADGE`` in builders/scene.py and runtime
14-shapes). This opens the exported page in Chromium and holds the editor to
the static picture, badge by badge.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from infragram.author import Diagram, Edge
from infragram.exports import render_project_html, render_project_svg, render_timeout_ms
from infragram.nodes import _scope, azure, reset_ids
from infragram.nodes.frames import azure as azure_frames

pytestmark = pytest.mark.skipif(
    os.environ.get("INFRAGRAM_RUN_BROWSER_TESTS") != "1",
    reason="set INFRAGRAM_RUN_BROWSER_TESTS=1 to run Chromium editor checks",
)

BADGES = [
    {
        "icon": "network-security-groups",
        "collection": "azure",
        "label": "nsg-web",
        "side": "corner",
    },
    {
        "icon": "route-tables",
        "collection": "azure",
        "label": "Route table · rt-spoke",
        "side": "corner",
    },
]


def _project():
    _scope.reset()
    reset_ids()
    with Diagram(
        "Subnet badges",
        "A subnet's NSG and route table on its corner.",
        slug="subnet-badges",
        providers=("azure",),
    ) as diagram:
        with azure_frames.VNet("vnet-app").column():
            gateway = azure.ApplicationGateways("agw-edge", "WAF v2")
            with (
                azure_frames.Subnet("snet-web")
                .badge(azure.NetworkSecurityGroups, label="nsg-web")
                .badge(azure.RouteTables, label="Route table · rt-spoke")
                .row()
            ):
                web = azure.VirtualMachine("vm-web-1")
                azure.VirtualMachine("vm-web-2")
        gateway >> Edge("HTTPS") >> web
    return diagram.to_project()


def _static(project) -> tuple[list[tuple[float, float]], list[tuple[float, float, str]]]:
    svg = render_project_svg(project)
    icons = [
        (float(x), float(y))
        for x, y in re.findall(
            r'<use data-frame-badge(?:="")? href="[^"]+" x="([\d.-]+)" y="([\d.-]+)"', svg
        )
    ]
    names = [
        (float(x), float(y), re.sub(r"<[^>]+>", "", text))
        for x, y, text in re.findall(
            r'<text data-frame-badge-label(?:="")? x="([\d.-]+)" y="([\d.-]+)"[^>]*>(.*?)</text>',
            svg,
        )
    ]
    return icons, names


def test_the_editor_draws_the_badges_where_the_picture_does_and_saves_them(tmp_path: Path) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    project = _project()
    source = tmp_path / "subnet-badges.html"
    source.write_text(render_project_html(project), encoding="utf-8")
    icons, names = _static(project)
    assert len(icons) == 2 and [name for *_, name in names] == ["nsg-web", "Route table · rt-spoke"]
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 960})
            page.goto(source.resolve().as_uri() + "?fresh=badges")
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            page.evaluate("() => window.infragramEditor.whenSettled()")
            drawn = page.evaluate("""() => ({
              icons: [...document.querySelectorAll('[data-graph-boundary] image[data-frame-badge]')]
                .map(el => [Number(el.getAttribute('x')), Number(el.getAttribute('y'))]),
              names: [...document.querySelectorAll('[data-graph-boundary] text[data-frame-badge-label]')]
                .map(el => [Number(el.getAttribute('x')), Number(el.getAttribute('y')), el.textContent]),
            })""")
            # the same geometry, badge by badge
            assert [tuple(point) for point in drawn["icons"]] == icons
            assert [tuple(name) for name in drawn["names"]] == names

            # the wire into the subnet keeps out of the badges, as it keeps
            # out of the frame's title
            crossing = page.evaluate("""() => {
              const boxes = [...document.querySelectorAll('[data-graph-boundary] image[data-frame-badge], [data-graph-boundary] text[data-frame-badge-label]')]
                .map(el => el.getBBox());
              const path = document.querySelector('path[data-graph-edge]').getAttribute('d');
              const points = [...path.matchAll(/(-?[\\d.]+),(-?[\\d.]+)/g)].map(m => [Number(m[1]), Number(m[2])]);
              const hits = (ax, ay, bx, by, b) => Math.max(ax, bx) > b.x && Math.min(ax, bx) < b.x + b.width
                && Math.max(ay, by) > b.y && Math.min(ay, by) < b.y + b.height;
              return points.slice(1).some((p, i) => boxes.some(b => hits(points[i][0], points[i][1], p[0], p[1], b)));
            }""")
            assert not crossing

            # saved: the document's badges, artwork left out
            exported = page.evaluate("() => window.infragramEditor.exportProject()")

            def find(element):
                if element["name"] == "snet-web":
                    return element
                return next(
                    (hit for child in element.get("children", []) if (hit := find(child))), None
                )

            assert find(exported["topology"])["badges"] == BADGES
        finally:
            browser.close()
