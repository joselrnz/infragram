"""Clicking an element that carries a table opens it in a popup beside the card.

A route table's card stays a card on the canvas; its routes appear only when
someone selects it, and go away with the selection.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from infragram.author import Diagram
from infragram.exports import render_project_html, render_timeout_ms
from infragram.nodes.azure import networking as net
from infragram.nodes.frames import azure as az

pytestmark = pytest.mark.skipif(
    os.environ.get("INFRAGRAM_RUN_BROWSER_TESTS") != "1",
    reason="set INFRAGRAM_RUN_BROWSER_TESTS=1 to run Chromium editor checks",
)

COLUMNS = ("Prefix", "Next hop type", "Next hop")
ROUTES = [
    ("0.0.0.0/0", "Virtual appliance", "10.0.1.4"),
    ("10.0.0.0/16", "VNet peering", "hub-vnet"),
    ("10.1.0.0/16", "VNet local", "-"),
    ("192.168.0.0/16", "Virtual network gateway", "ExpressRoute"),
]
POPUP = "[data-canvas-popup]"
CARD = '[data-graph-node][data-node-id="rt-spoke-prod"]'


def _page(tmp_path: Path) -> Path:
    with Diagram(
        "Spoke routes", "A route table and a firewall.", slug="spoke-routes", providers=("azure",)
    ) as diagram:
        with az.VNet("spoke-prod 10.1.0.0/16").row():
            firewall = net.Firewalls("Azure Firewall", "10.0.1.4")
            routes = net.RouteTables("rt-spoke-prod", "UDR").table(COLUMNS, ROUTES)
        routes >> firewall
    source = tmp_path / "spoke-routes.html"
    source.write_text(render_project_html(diagram.to_project()), encoding="utf-8")
    return source


def test_selecting_the_card_opens_its_table_and_deselecting_closes_it(tmp_path: Path) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    source = _page(tmp_path)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 960})
            page.goto(source.resolve().as_uri() + "?fresh=popup")
            page.wait_for_load_state("networkidle")
            popup = page.locator(POPUP)
            assert popup.is_hidden()

            page.locator(CARD).click()
            popup.wait_for(state="visible")
            assert popup.locator("header strong").text_content() == "rt-spoke-prod"
            assert popup.locator("th").all_text_contents() == list(COLUMNS)
            assert popup.locator("tbody tr").count() == len(ROUTES)
            assert popup.locator("tbody tr").first.locator("td").all_text_contents() == list(
                ROUTES[0]
            )

            # Beside the card, never on top of it.
            card, box = page.locator(CARD).bounding_box(), popup.bounding_box()
            assert (
                box["x"] >= card["x"] + card["width"]
                or box["x"] + box["width"] <= card["x"]
                or box["y"] >= card["y"] + card["height"]
                or box["y"] + box["height"] <= card["y"]
            )

            page.keyboard.press("Escape")
            popup.wait_for(state="hidden")

            page.locator(CARD).click()
            popup.wait_for(state="visible")
            popup.locator("[data-popup-close]").click()
            popup.wait_for(state="hidden")
            # The close button dismisses without deselecting the card.
            state = page.evaluate("() => window.infragramEditor.getState()")
            routes = next(node for node in state["nodes"] if node["id"] == "rt-spoke-prod")
            assert routes["attributes"]["table"]["columns"] == list(COLUMNS)
        finally:
            browser.close()


def test_a_card_without_a_table_shows_its_links_and_a_shared_card_nothing(tmp_path: Path) -> None:
    """A cloud component is read about on its vendor's site; a shared one
    names no vendor, so its card opens no popup."""
    sync_api = pytest.importorskip("playwright.sync_api")
    from infragram.nodes import infragram as shared

    with Diagram(
        "Spoke routes", "A firewall and its users.", slug="spoke-users", providers=("azure",)
    ) as diagram:
        users = shared.identity.PublicUsers("Users", "browsers")
        with az.VNet("spoke-prod 10.1.0.0/16"):
            firewall = net.Firewalls("Azure Firewall", "10.0.1.4")
        users >> firewall
    source = tmp_path / "spoke-users.html"
    source.write_text(render_project_html(diagram.to_project()), encoding="utf-8")
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 960})
            page.goto(source.resolve().as_uri() + "?fresh=nopopup")
            page.wait_for_load_state("networkidle")
            popup = page.locator(POPUP)
            details = page.locator("[data-context-details]")
            firewall = page.locator('[data-graph-node][data-node-id="azure-firewall"]')
            # Selecting a card to move or wire it opens nothing over the canvas...
            firewall.click()
            page.wait_for_timeout(200)
            assert popup.is_hidden()
            # ...Details in its right-click menu does.
            firewall.click(button="right")
            details.wait_for(state="visible")
            details.click()
            popup.wait_for(state="visible")
            assert popup.locator("[data-popup-table], [data-popup-price]").count() == 0
            link = popup.locator("[data-popup-links] a")
            assert link.count() == 1 and link.text_content() == "Search learn.microsoft.com"
            assert link.get_attribute("href").startswith(
                "https://learn.microsoft.com/en-us/search/?terms="
            )
            assert link.get_attribute("target") == "_blank" and "noopener" in link.get_attribute(
                "rel"
            )
            page.keyboard.press("Escape")
            popup.wait_for(state="hidden")
            # asking once is for that selection: coming back to the card asks again
            page.locator('[data-graph-node][data-node-id="users"]').click()
            firewall.click()
            page.wait_for_timeout(200)
            assert popup.is_hidden()
            # several cards have no one popup: no Details (a double click
            # selects, and shift adds to the selection)
            firewall.dblclick()
            page.locator('[data-graph-node][data-node-id="users"]').click(modifiers=["Shift"])
            firewall.click(button="right")
            page.locator("[data-canvas-context-menu]").wait_for(state="visible")
            assert details.is_hidden()
            page.keyboard.press("Escape")
            users = page.locator('[data-graph-node][data-node-id="users"]')
            users.click()
            page.wait_for_timeout(200)
            assert popup.is_hidden()
            users.click(button="right")
            page.locator("[data-canvas-context-menu]").wait_for(state="visible")
            # a card with nothing to show has no popup: its details are the inspector's
            details.click()
            page.wait_for_timeout(200)
            assert popup.is_hidden()
            assert (
                page.locator('[data-inspector-tab="style"]').get_attribute("aria-selected")
                == "true"
            )
        finally:
            browser.close()


def test_a_priced_card_shows_its_price_what_it_assumed_and_its_links(tmp_path: Path) -> None:
    """``--prices`` writes the price into the element; the card's Details show
    it with each size the diagram did not state marked assumed. Every cloud
    card is priced, so a price alone does not open the popup on a click."""
    sync_api = pytest.importorskip("playwright.sync_api")
    from infragram.nodes.aws import compute
    from infragram.nodes.frames import aws
    from infragram.pricing import Price

    with Diagram("Web", "Web servers.", slug="web-priced", providers=("aws",)) as diagram:
        with aws.Cloud("AWS Cloud"), aws.Region("us-east-1"):
            compute.EC2("Web servers").sizing(instance_type="m6i.large", count=3)
    project = diagram.to_project()
    web = project.topology.children[0].children[0].children[0]
    web.attributes["price"] = Price(
        monthly=210.24,
        hourly=0.096,
        sizing={
            "instance_type": "m6i.large",
            "region": "us-east-1",
            "os": "Linux",
            "count": 3,
            "hours": 730,
        },
        assumed=["os", "hours"],
        rate="EC2 on-demand, Linux, shared tenancy",
        source="AWS price list (aws.amazon.com/ec2/pricing)",
        published="2026-09-24",
        priced="2026-09-25",
    ).model_dump()
    source = tmp_path / "web-priced.html"
    source.write_text(render_project_html(project), encoding="utf-8")
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 960})
            page.goto(source.resolve().as_uri() + "?fresh=price")
            page.wait_for_load_state("networkidle")
            node = page.locator(f'[data-graph-node][data-node-id="{web.id}"]')
            node.click()
            popup = page.locator(POPUP)
            page.wait_for_timeout(300)
            assert popup.is_hidden(), "a click shows the flow, not the price"
            node.click(button="right")
            page.locator("[data-context-details]").click()
            popup.wait_for(state="visible")
            price = popup.locator("[data-popup-price]")
            assert price.locator(".canvas-popup__amount strong").text_content() == "≈ $210.24"
            assert "$0.096 an hour × 730 hours × 3" in price.text_content()
            rows = {
                row.locator("th").text_content(): row.locator("td").text_content()
                for row in price.locator("tr").all()
            }
            assert rows["Instance type"] == "m6i.large" and rows["Count"] == "3"
            assert (
                rows["Operating system"] == "Linux assumed"
                and rows["Hours a month"] == "730 assumed"
            )
            assert "published 2026-09-24" in price.text_content()
            hrefs = popup.locator("[data-popup-links] a").evaluate_all(
                "links => links.map(a => a.href)"
            )
            assert (
                hrefs[0] == "https://aws.amazon.com/ec2/"
                and "https://aws.amazon.com/ec2/pricing/on-demand/" in hrefs
            )
        finally:
            browser.close()


def _apart(a: dict, b: dict) -> bool:
    return (
        a["x"] + a["width"] <= b["x"]
        or b["x"] + b["width"] <= a["x"]
        or a["y"] + a["height"] <= b["y"]
        or b["y"] + b["height"] <= a["y"]
    )


@pytest.mark.parametrize("viewport", [(1440, 900), (1024, 640), (1920, 1080)])
def test_a_tall_popup_on_a_zoomed_out_page_covers_neither_its_card_nor_the_toolbar(
    tmp_path: Path, viewport: tuple[int, int]
) -> None:
    """A price and links together are taller than the room beside a card on a
    fitted three-tier page. The popup went on top of the card, and measured
    at the canvas's left edge it shrank when placed by the right one, wrapped,
    and grew back over the selection toolbar. It now takes a spot clear of
    both, scrolling when no spot holds it whole."""
    sync_api = pytest.importorskip("playwright.sync_api")
    from infragram.cli.user.compose import project_from_spec
    from infragram.paths import plugin_root
    from infragram.pricing import Price

    project = project_from_spec(plugin_root() / "examples" / "aws_three_tier.py")
    web = next(
        element for element in project.topology.index().values() if element.id == "web-servers"
    )
    web.attributes["price"] = Price(
        monthly=210.24,
        hourly=0.096,
        sizing={
            "instance_type": "m6i.large",
            "region": "us-east-1",
            "os": "Linux",
            "count": 3,
            "hours": 730,
        },
        assumed=["os", "hours"],
        rate="EC2 on-demand, Linux, shared tenancy, 2 vCPU, 8 GiB",
        source="AWS price list (aws.amazon.com/ec2/pricing)",
        published="2026-09-24",
        priced="2026-09-25",
    ).model_dump()
    source = tmp_path / "three-tier.html"
    source.write_text(render_project_html(project), encoding="utf-8")
    card = '[data-graph-node][data-node-id="web-servers"]'
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": viewport[0], "height": viewport[1]})
            page.goto(source.resolve().as_uri() + "?fresh=tall")
            page.wait_for_load_state("networkidle")
            # the editor is published once its first fit settles, which a slow
            # runner reaches after the network is idle
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            page.evaluate("() => window.infragramEditor.whenSettled()")
            popup = page.locator(POPUP)
            for opened in ("details", "details again"):
                if opened == "details again":
                    page.keyboard.press("Escape")
                    popup.wait_for(state="hidden")
                page.locator(card).click(button="right")
                page.locator("[data-context-details]").click()
                popup.wait_for(state="visible")
                page.wait_for_timeout(
                    150
                )  # the toolbar is placed a frame later, and the popup again with it
                # the card's own drawing, not the port dots a hover adds around it
                drawn = page.locator(f"{card} image, {card} rect").first.bounding_box()
                box = popup.bounding_box()
                toolbar = page.locator("[data-selection-toolbar]").bounding_box()
                canvas = page.locator(".canvas-viewport").bounding_box()
                assert _apart(box, drawn), (opened, viewport, box, drawn)
                # a click shows the card's flow, which draws no selection toolbar
                assert toolbar is None or _apart(box, toolbar), (opened, viewport, box, toolbar)
                assert (
                    canvas["x"] <= box["x"]
                    and box["x"] + box["width"] <= canvas["x"] + canvas["width"] + 1
                )
                assert (
                    canvas["y"] <= box["y"]
                    and box["y"] + box["height"] <= canvas["y"] + canvas["height"] + 1
                )
            assert popup.locator("[data-popup-links] a").count() == 5
        finally:
            browser.close()
