"""A save from the editor keeps what the editor does not model.

``exportProject()`` rebuilds the topology from the canvas. An element's
``role`` (``hub`` draws the focal card) and the root element's id, type and
attributes have no place on the canvas, so the rebuild used to drop the role,
call the root ``root`` and leave its attributes out. They come back from the
document the page opened, unchanged.
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
from infragram.nodes.aws.compute import EC2
from infragram.nodes.frames import aws

with Diagram("Keep", slug="keep"):
    with aws.VPC("VPC"):
        hub = EC2("hub")
        spoke = EC2("spoke")
    hub >> Edge("x") >> spoke
"""


def _roles(element: dict, found: dict[str, str | None] | None = None) -> dict[str, str | None]:
    found = {} if found is None else found
    for child in element.get("children") or []:
        found[child["id"]] = child.get("role")
        _roles(child, found)
    return found


def test_a_save_keeps_roles_and_the_root(tmp_path: Path) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    from infragram.cli.user.compose import project_from_spec
    from infragram.exports import render_project_html
    from infragram.projects import CloudProject

    spec = tmp_path / "keep.py"
    spec.write_text(SPEC, encoding="utf-8")
    project = project_from_spec(spec)
    root = project.topology
    root.id = "keep-system"
    root.attributes = {"owner": "platform", "tier": 2}
    vpc = root.children[0]
    vpc.role = "boundary"
    hub = next(child for child in vpc.children if child.name == "hub")
    hub.role = "hub"
    original = project.model_dump(mode="json")

    source = tmp_path / "keep.html"
    source.write_text(render_project_html(project), encoding="utf-8")
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            page.goto(source.resolve().as_uri() + "?fresh=keep")
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            page.evaluate("() => window.infragramEditor.whenSettled()")
            saved = page.evaluate("() => window.infragramEditor.exportProject()")
        finally:
            browser.close()

    topology = saved["topology"]
    assert topology["id"] == "keep-system"
    assert topology.get("attributes") == {"owner": "platform", "tier": 2}
    assert topology["type"] == original["topology"]["type"]
    assert _roles(topology) == _roles(original["topology"])
    assert _roles(topology)[hub.id] == "hub"

    # the saved document reads back as a project with the same root and roles
    again = CloudProject.model_validate(saved)
    assert again.topology.id == "keep-system"
    assert again.topology.first(role="hub").id == hub.id
