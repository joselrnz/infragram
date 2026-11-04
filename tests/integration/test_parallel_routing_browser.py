"""Parallel data and DNS flows must route clear and retain their captions."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

from infragram.exports import render_project_html, render_timeout_ms
from infragram.projects import CloudProject

pytestmark = pytest.mark.skipif(
    os.environ.get("INFRAGRAM_RUN_BROWSER_TESTS") != "1",
    reason="set INFRAGRAM_RUN_BROWSER_TESTS=1 to run Chromium editor checks",
)
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("display", ["card", "icon"])
def test_parallel_flows_avoid_a_blocker_and_keep_labels_on_their_paths(
    tmp_path: Path, display: str
) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    project = CloudProject.model_validate(
        {
            "slug": "parallel-routing",
            "title": "Parallel routing",
            "description": "Data and DNS routes around an unrelated service.",
            "providers": [{"id": "azure"}],
            "kind": "single-cloud",
            "presentation": {"size": "fit"},
            "topology": {
                "id": "root",
                "name": "Parallel routing",
                "type": "group",
                "children": [
                    {
                        "id": "app",
                        "name": "Application",
                        "type": "service",
                        "attributes": {
                            "editor_x": 100,
                            "editor_y": 180,
                            "editor_edge_styles": {
                                "firewall": {"source_port": "bottom", "target_port": "left"}
                            },
                        },
                        "connections": [
                            {"target": "firewall", "kind": "solid", "label": "HTTPS"},
                            {"target": "firewall", "kind": "dotted", "label": "DNS"},
                        ],
                    },
                    {
                        "id": "blocker",
                        "name": "Unrelated service",
                        "type": "service",
                        "attributes": {"editor_x": 440, "editor_y": 180},
                    },
                    {
                        "id": "firewall",
                        "name": "Firewall",
                        "type": "service",
                        "attributes": {"editor_x": 820, "editor_y": 180},
                    },
                ],
            },
        }
    )
    source = tmp_path / "parallel.html"
    source.write_text(render_project_html(project), encoding="utf-8")
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(source.resolve().as_uri() + "?fresh=parallel")
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            page.evaluate("mode => window.infragramEditor.setDisplayMode(mode)", display)
            page.evaluate("() => window.infragramEditor.whenSettled()")
            saved = page.evaluate("() => window.infragramEditor.exportProject()")
            picture = page.evaluate("() => window.infragramEditor.exportSvg()")
        finally:
            browser.close()
    app = next(child for child in saved["topology"]["children"] if child["id"] == "app")
    assert [(wire["kind"], wire["label"]) for wire in app["connections"]] == [
        ("solid", "HTTPS"),
        ("dotted", "DNS"),
    ]
    spec = importlib.util.spec_from_file_location(
        "project_check", ROOT / "plugin/skills/infragram-architect/scripts/project_check.py"
    )
    checker = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(checker)
    errors: list[str] = []
    (tmp_path / "parallel.svg").write_text(picture, encoding="utf-8")
    checker.check_svg(picture, errors, saved)
    assert errors == [], errors
