"""The lenses of the right-click menu light the drawing and dim the rest.

A right-click on a card offers what depends on it; a right-click on empty
canvas offers what the internet reaches, what costs most and the tags the
cards wear. Each lights the way a single click's flow does, shows a tick
while it is on, ends on its own entry, on Escape or a click on empty canvas,
and leaves nothing in the document or the downloaded picture.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from infragram.exports import render_timeout_ms

pytestmark = pytest.mark.skipif(
    os.environ.get("INFRAGRAM_RUN_BROWSER_TESTS") != "1",
    reason="set INFRAGRAM_RUN_BROWSER_TESTS=1 to run Chromium editor checks",
)

SPEC = """\
from infragram.author import Diagram, Edge
from infragram.nodes import infragram as shared
from infragram.nodes.aws.compute import EC2
from infragram.nodes.aws.databases import RDS, Elasticache
from infragram.nodes.aws.networking_content_delivery import ElasticLoadBalancing
from infragram.nodes.frames import aws

with Diagram("Lenses", slug="lenses"):
    internet = shared.identity.PublicUsers("Internet")
    with aws.Cloud("AWS Cloud"), aws.VPC("VPC"):
        lb = ElasticLoadBalancing("lb")
        app = EC2("app").tags(env="prod", team="shop")
        worker = EC2("worker").tags(env="dev")
        db = RDS("db").tags(env="prod")
        cache = Elasticache("cache")
    internet >> Edge("HTTPS") >> lb >> Edge("HTTP") >> app >> Edge("SQL") >> db
    app >> Edge("cache") >> cache
    worker >> Edge("SQL") >> db
    app.attributes["price"] = {"monthly": 100.0, "hourly": 0.137, "currency": "USD"}
    db.attributes["price"] = {"monthly": 300.0, "hourly": 0.411, "currency": "USD"}
"""


def _lit(page) -> set[str]:
    return set(
        page.evaluate(
            "() => [...document.querySelectorAll('[data-graph-node][data-focus-dimmed=\"false\"]')]"
            ".map(element => element.getAttribute('aria-label'))"
        )
    )


def _canvas_menu(page, *, keep: bool = False) -> None:
    """Right-click the empty canvas, clear of every card and frame; Escape
    first ends whatever lens is on, unless it is to be kept."""
    if not keep:
        page.keyboard.press("Escape")
    point = page.evaluate(
        """() => {
          const box = document.querySelector('[data-graph-boundary]').getBoundingClientRect();
          return {x: box.left - 24, y: box.top - 24};
        }"""
    )
    page.mouse.click(point["x"], point["y"], button="right")
    page.locator("[data-canvas-context-menu]").wait_for(state="visible")


def test_the_lenses_light_what_they_name_and_end_cleanly(tmp_path: Path) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    from infragram.cli.user.compose import project_from_spec
    from infragram.exports import render_project_html

    spec = tmp_path / "lenses.py"
    spec.write_text(SPEC, encoding="utf-8")
    source = tmp_path / "lenses.html"
    source.write_text(render_project_html(project_from_spec(spec)), encoding="utf-8")
    everything = {"Internet", "lb", "app", "worker", "db", "cache"}
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 960})
            page.goto(source.resolve().as_uri() + "?fresh=lenses")
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            page.evaluate("() => window.infragramEditor.whenSettled()")
            menu = page.locator("[data-canvas-context-menu]")
            before = page.evaluate("() => JSON.stringify(window.infragramEditor.exportProject())")

            # the canvas menu holds its own entries and nothing about a selection
            _canvas_menu(page)
            shown = menu.locator("button:visible").all_inner_texts()
            assert shown == [
                "Paste here\nCtrl+V",
                "Show what the internet reaches",
                "Show what costs most",
                "Show env=prod (2)",
                "Show env=dev (1)",
                "Show team=shop (1)",
                # the view's entries, the same as on an item's menu
                "Zoom in\n+",
                "Zoom out\n-",
                "Fit all\n0",
                "Actual size\n1",
                "Scroll moves the map",
                "Tidy layout",
            ], shown
            menu.locator('[data-context-action="lens-internet"]').click()
            assert _lit(page) == everything - {"worker"}, "the worker is behind nothing public"

            # its entry carries the tick, and ends it
            _canvas_menu(page)
            internet = menu.locator('[data-context-action="lens-internet"]')
            assert internet.get_attribute("aria-checked") == "false", "Escape ended the lens"
            internet.click()
            _canvas_menu(page, keep=True)
            assert internet.get_attribute("aria-checked") == "true"
            internet.click()
            assert _lit(page) == everything

            # what costs most: the priced cards, tinted by their share
            _canvas_menu(page)
            menu.locator('[data-context-action="lens-cost"]').click()
            assert _lit(page) == {"app", "db"}
            heat = page.evaluate(
                "() => Object.fromEntries([...document.querySelectorAll('rect[data-cost-heat]')]"
                ".map(rect => [rect.parentElement.getAttribute('aria-label'),"
                " Number(rect.getAttribute('fill-opacity'))]))"
            )
            assert set(heat) == {"app", "db"} and heat["db"] > heat["app"]
            # and each says what it costs a month, above the card
            amounts = page.locator("text[data-cost-heat]").all_text_contents()
            assert len(amounts) == 2 and all(text.endswith("/mo") for text in amounts)
            picture = page.evaluate("() => window.infragramEditor.exportSvg()")
            assert "data-cost-heat" not in picture and "data-focus-dimmed" not in picture

            # a tag
            _canvas_menu(page)
            assert page.locator("[data-cost-heat]").count() == 0, "Escape took the tint with it"
            menu.locator('[data-tag="env=prod"]').click()
            assert _lit(page) == {"app", "db"}

            # what depends on the database: everything that leads to it
            page.keyboard.press("Escape")
            page.locator('[data-graph-node][aria-label="db"]').click(button="right")
            # each entry, without the shortcut written beside it
            names = [
                text.split("\n")[0] for text in menu.locator("button:visible").all_inner_texts()
            ]
            assert "Show what depends on this" in names and "Show what costs most" not in names
            assert "More actions" in names and "Delete" in names, (
                "the card's own menu is whole again"
            )
            menu.locator('[data-context-action="lens-dependents"]').click()
            assert _lit(page) == everything - {"cache"}
            page.keyboard.press("Escape")
            assert _lit(page) == everything

            after = page.evaluate("() => JSON.stringify(window.infragramEditor.exportProject())")
            assert after == before, "a lens changes nothing in the document"
        finally:
            browser.close()


def test_tags_are_written_once_and_read_back(tmp_path: Path) -> None:
    from infragram.cli.user.compose import project_from_spec

    spec = tmp_path / "lenses.py"
    spec.write_text(SPEC, encoding="utf-8")
    project = project_from_spec(spec)
    tags = {e.name: e.attributes.get("tags") for e in project.topology.walk() if e.attributes}
    assert tags["app"] == {"env": "prod", "team": "shop"} and tags["worker"] == {"env": "dev"}
