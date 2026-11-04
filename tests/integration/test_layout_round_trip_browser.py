"""What is moved in the editor comes back to the Python diagram file.

A card dragged in the exported page, the document downloaded, ``layout:save
--for`` the diagram file, and the next ``compose`` draws the card where it was
dropped; a card the file adds later is still placed by the layout, and the
diagram file itself is never touched.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from infragram.exports import render_timeout_ms
from infragram.paths import repo_root

pytestmark = pytest.mark.skipif(
    os.environ.get("INFRAGRAM_RUN_BROWSER_TESTS") != "1",
    reason="set INFRAGRAM_RUN_BROWSER_TESTS=1 to run Chromium editor checks",
)


def test_a_dragged_card_stays_where_it_was_dropped(tmp_path: Path) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    from infragram.cli.user.compose import main as compose, project_from_spec
    from infragram.cli.user.layout import main as layout_save
    from infragram.exports.render import _scene_for

    spec = tmp_path / "three_tier.py"
    shutil.copy(repo_root() / "plugin/examples/aws_three_tier.py", spec)
    assert compose([str(spec), "--formats", "html", "--output-dir", str(tmp_path / "one")]) == 0
    page_file = next((tmp_path / "one").glob("*.html"))

    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(f"{page_file.resolve().as_uri()}?fresh=layout")
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            page.evaluate("() => window.infragramEditor.whenSettled()")
            state = page.evaluate("() => window.infragramEditor.getState()")
            watch = next(node for node in state["nodes"] if node["name"] == "CloudWatch")
            card = page.locator(f'[data-graph-node][data-node-id="{watch["id"]}"]')
            box = card.bounding_box()
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.mouse.down()
            page.mouse.move(
                box["x"] + box["width"] / 2 + 60, box["y"] + box["height"] / 2 + 140, steps=8
            )
            page.mouse.up()
            moved = next(
                node
                for node in page.evaluate("() => window.infragramEditor.getState()")["nodes"]
                if node["id"] == watch["id"]
            )
            assert (moved["x"], moved["y"]) != (watch["x"], watch["y"]), "the drag moved the card"
            saved = page.evaluate("() => window.infragramEditor.exportProject()")
        finally:
            browser.close()

    downloaded = tmp_path / "saved.infragram.json"
    downloaded.write_text(json.dumps(saved), encoding="utf-8")
    before = spec.read_text(encoding="utf-8")
    assert layout_save([str(downloaded), "--for", str(spec)]) == 0
    assert (tmp_path / "three_tier.layout.json").is_file()
    assert spec.read_text(encoding="utf-8") == before, "the diagram file is never touched"

    # the next compose draws the card where it was dropped
    from infragram.compose.layout_file import apply_layout, layout_path

    project = project_from_spec(spec)
    assert apply_layout(project, layout_path(spec)) == []
    node = next(node for node in _scene_for(project).root.walk() if node.ref == watch["id"])
    assert (node.x, node.y) == (moved["x"], moved["y"])
