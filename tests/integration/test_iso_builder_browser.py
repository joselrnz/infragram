"""The editor's 3D builder renders a spec in the page and adds a node that carries it.

The page carries the same scene the shipped set came from and the same
measurer. Turning a recipe's knobs in the drawer renders the item in the
page, measures it, and adds an ``infragram:custom-3d`` node with its spec,
artwork and ink in its attributes -- the form the static renderer already
draws -- so the document round-trips without the page.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from infragram.author import Diagram
from infragram.exports import render_project_html, render_project_svg
from infragram.nodes.onprem import iso_compute as compute
from infragram.projects import CloudProject

pytestmark = pytest.mark.skipif(
    os.environ.get("INFRAGRAM_RUN_BROWSER_TESTS") != "1",
    reason="set INFRAGRAM_RUN_BROWSER_TESTS=1 to run Chromium editor checks",
)

NODE = '[data-graph-node][data-component-id="custom-3d"]'


def _page(tmp_path: Path) -> Path:
    with Diagram(
        "Builder", "One shipped server.", slug="builder", providers=("onprem",)
    ) as diagram:
        compute.IsoRackServer("Shipped", "2U")
    source = tmp_path / "builder.html"
    source.write_text(render_project_html(diagram.to_project()), encoding="utf-8")
    return source


def test_the_builder_renders_a_spec_and_adds_a_node_that_carries_it(tmp_path: Path) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    source = _page(tmp_path)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 960})
            page.goto(source.resolve().as_uri() + "?fresh=builder")
            page.wait_for_load_state("networkidle")
            assert page.evaluate(
                "() => Boolean(window.iso3d && window.iso3d.recipes.includes('server'))"
            )
            assert page.evaluate("() => window.iso3d.knobs('server').map(k => k.name)") == [
                "units",
                "drivesN",
                "rows",
            ]

            # through the drawer: a 3U storage server with twelve bays and a database badge
            page.locator('[data-bottom-tab="builder"]').click()
            page.select_option("[data-iso-recipe]", "server")
            page.fill('[data-iso-knob="units"]', "3")
            page.fill('[data-iso-knob="drivesN"]', "12")
            page.select_option("[data-iso-family]", "storage")
            page.select_option("[data-iso-glyph]", "database")
            page.fill("[data-iso-name]", "DB-01")
            page.fill("[data-iso-detail]", "PostgreSQL 16")
            page.locator("[data-iso-preview]").click()
            page.wait_for_function(
                "() => !document.querySelector('[data-iso-add]').disabled", timeout=90_000
            )
            assert (
                page.locator("[data-iso-preview-image]")
                .get_attribute("src")
                .startswith("data:image/svg+xml")
            )
            page.locator("[data-iso-add]").click()
            node = page.locator(NODE)
            node.wait_for(state="visible")
            assert node.get_attribute("data-display-mode") == "icon"
            assert node.get_attribute("data-ink-edge"), (
                "the render is measured, so links seat on it"
            )

            saved = page.evaluate(
                "() => window.infragramEditor.getState().nodes.find(n => n.componentId === 'custom-3d')"
            )
            assert saved["name"] == "DB-01" and saved["detail"] == "PostgreSQL 16"
            spec = saved["attributes"]["iso"]
            assert (
                spec["recipe"] == "server"
                and spec["args"] == [3, 12]
                and spec["colour"] == "#0f9d8a"
            )
            assert spec["glyph"], "the database glyph rides in the spec"
            artwork = saved["attributes"]["iso_artwork"]
            assert artwork.startswith("<svg") and "data:image/png;base64," in artwork
            assert saved["attributes"]["iso_ink"]["edges"] == saved["inkEdges"]
            assert len(saved["attributes"]["iso_hash"]) == 16

            # the document round-trips without the page: the static renderer draws the carried artwork
            exported = page.evaluate("() => window.infragramEditor.exportProject()")
            project = CloudProject.model_validate(exported)
            element = next(
                item for item in project.topology.walk() if item.attributes.get("iso_artwork")
            )
            assert element.attributes["iso"]["recipe"] == "server"
            assert "data:image/png;base64," in render_project_svg(project)

            # and by the API, for an agent or a script
            page.evaluate(
                "() => window.infragramEditor.build3d("
                "{id: 'switch:[48]', recipe: 'switch', args: [48], kwargs: {}, colour: '#0f766e', glyph: ''},"
                "{name: 'Core', detail: '48 ports'})"
            )
            page.wait_for_function(
                f"() => document.querySelectorAll('{NODE}').length === 2", timeout=90_000
            )
        finally:
            browser.close()
