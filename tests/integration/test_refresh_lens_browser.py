"""A page that says what changed since the last read lights it on request.

The Azure edition's export:azure --refresh writes, on each component added or
changed since an earlier read, a ``refresh`` mark, and on the root the
account with what was removed. This edition writes neither, but its editor
reads them: the canvas menu offers the lens only where such marks are, it
lights the marked cards, and the status names what was removed.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from infragram.author import Diagram
from infragram.exports import render_project_html
from infragram.nodes.azure import compute, databases, security

pytestmark = pytest.mark.skipif(
    os.environ.get("INFRAGRAM_RUN_BROWSER_TESTS") != "1",
    reason="set INFRAGRAM_RUN_BROWSER_TESTS=1 to run Chromium editor checks",
)

LENS = '[data-context-action="lens-refresh"]'


def _page(tmp_path: Path, *, marked: bool) -> Path:
    with Diagram("Refresh", "Read twice.", slug="refresh", providers=("azure",)) as diagram:
        vm = compute.VirtualMachine("vm-app")
        database = databases.SQLDatabase("sqldb-orders")
        vault = security.KeyVaults("kv-prod")
        vm >> database
        vm >> vault
    if marked:
        database.attributes["refresh"] = {"status": "changed", "fields": ["sku"]}
        vault.attributes["refresh"] = {"status": "added"}
    project = diagram.to_project()
    if marked:
        project.topology.attributes["refresh"] = {
            "since": "2026-09-29T12:00:00+00:00",
            "added": 1,
            "changed": 1,
            "removed": [{"name": "log-prod", "type": "microsoft.operationalinsights/workspaces"}],
        }
    source = tmp_path / f"refresh-{marked}.html"
    source.write_text(render_project_html(project), encoding="utf-8")
    return source


@pytest.mark.parametrize("marked", [True, False])
def test_the_lens_lights_what_changed_and_names_what_went(tmp_path: Path, marked: bool) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    source = _page(tmp_path, marked=marked)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 960})
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(source.resolve().as_uri() + "?fresh=refresh")
            page.wait_for_load_state("networkidle")
            box = page.locator("[data-infragram-diagram]").bounding_box()
            assert box is not None
            page.mouse.click(box["x"] + 6, box["y"] + 6, button="right")
            if not marked:
                assert page.locator(LENS).is_hidden()
                return
            page.locator(LENS).click()
            lit = page.evaluate(
                "[...document.querySelectorAll('[data-graph-node]')]"
                ".filter(node => node.dataset.focusDimmed === 'false')"
                ".map(node => node.getAttribute('aria-label')).sort()"
            )
            assert lit == ["kv-prod", "sqldb-orders"]
            status = page.locator("[data-snackbar]").inner_text()
            assert "1 added, 1 changed, 1 removed: log-prod" in status
            assert errors == []
        finally:
            browser.close()
