"""A flow told in steps, in the editor: it draws each step in its caption,
saves every step back into the document, keeps the step list right of
what it draws as the drawing grows, and shows a step's wires when its row in
the list is clicked. test_renderer_parity_browser.py holds the
two renderers to one picture of the same documents."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from infragram.cli.user.compose import project_from_spec
from infragram.exports import render_project_html, render_timeout_ms
from infragram.projects import CloudProject

pytestmark = pytest.mark.skipif(
    os.environ.get("INFRAGRAM_RUN_BROWSER_TESTS") != "1",
    reason="set INFRAGRAM_RUN_BROWSER_TESTS=1 to run Chromium editor checks",
)

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())


def _connections(document: dict) -> list[dict]:
    found: list[dict] = []

    def walk(element: dict) -> None:
        found.extend(element.get("connections") or [])
        for child in element.get("children") or []:
            walk(child)

    walk(document["topology"])
    return found


def test_the_editor_draws_saves_and_keeps_the_steps_beside_the_drawing(tmp_path: Path) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    project = project_from_spec(ROOT / "plugin" / "examples" / "aws_github_actions_oidc.py")
    source = tmp_path / "steps.html"
    source.write_text(render_project_html(project), encoding="utf-8", newline="\n")
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(f"pageerror: {error}"))
            page.goto(f"{source.resolve().as_uri()}?fresh={tmp_path.name}")
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())

            # each step in its caption: the circle, and its number after the caption's text
            assert page.locator("[data-edge-label] circle[data-edge-step]").count() == 9
            first = page.locator("[data-edge-label]:has(circle[data-edge-step='1']) text").first
            assert first.text_content() == "push", "the caption is the group's first text"
            # the runtime flow is AWS's second: lettered, in dark red
            runtime = page.locator("[data-edge-label]:has(text:text-is('pulls'))")
            assert runtime.locator("[data-edge-step-number]").text_content() == "A"
            assert runtime.locator("circle[data-edge-step]").get_attribute("fill") == "#8b250b"

            # saved, every step, its flow and what the list says of it comes back, and loads
            document = page.evaluate("window.infragramEditor.exportProject()")
            steps = sorted(
                (c.get("step_flow", ""), c["step"], c.get("step_text", ""))
                for c in _connections(document)
                if "step" in c
            )
            assert [(flow, number) for flow, number, _ in steps] == [
                ("", n) for n in range(1, 9)
            ] + [("At runtime", 1)]
            assert steps[0][2] == "A push to main starts the deploy workflow"
            CloudProject.model_validate(document)

            # the list stands where it was drawn; pushed right, the drawing takes it along
            step_list = page.locator("[data-step-list]")
            assert step_list.get_attribute("transform") is None
            drawn_x = float(step_list.get_attribute("data-drawn-x"))
            page.evaluate(
                """drawnX => window.infragramEditor.addNode({
                id: 'far-right', qualifiedId: 'aws:far-right', provider: 'aws', name: 'Far right',
                detail: 'grows the drawing', category: 'compute', iconUri: ''
            }, {x: drawnX + 200, y: 200})""",
                drawn_x,
            )
            page.wait_for_function(
                "document.querySelector('[data-step-list]').hasAttribute('transform')"
            )
            shifted = page.evaluate(
                "document.querySelector('[data-step-list]').getAttribute('transform')"
            )
            assert shifted.startswith("translate("), shifted
            assert not errors, errors
        finally:
            browser.close()


def _lit(page) -> dict:
    return page.evaluate(
        """() => ({
            edges: [...document.querySelectorAll('[data-edge-group]:not([data-focus-dimmed="true"])')]
                .map(group => group.dataset.edgeGroup).sort(),
            rows: [...document.querySelectorAll('[data-step-row]:not([data-focus-dimmed="true"])')]
                .map(row => `${row.dataset.stepFlow || ''}:${row.dataset.stepRow}`),
        })"""
    )


def _told(page, number: int, flow: str) -> list[str]:
    return page.evaluate(
        """([number, flow]) => window.infragramEditor.getState().edges
            .filter(edge => Number(edge.step) === number && (edge.stepFlow || '') === flow)
            .map(edge => edge.id).sort()""",
        [number, flow],
    )


def test_a_click_on_a_row_of_the_step_list_shows_that_steps_wires(tmp_path: Path) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    project = project_from_spec(ROOT / "plugin" / "examples" / "aws_github_actions_oidc.py")
    source = tmp_path / "steps.html"
    source.write_text(render_project_html(project), encoding="utf-8", newline="\n")
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(f"pageerror: {error}"))
            page.goto(f"{source.resolve().as_uri()}?fresh={tmp_path.name}")
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            page.evaluate("window.infragramEditor.whenSettled()")
            page.locator("[data-step-list]").scroll_into_view_if_needed()
            everything = _lit(page)
            assert len(everything["rows"]) == 9, everything

            # a main-flow row: its wire lights, the others and the other rows step back
            page.locator('[data-step-row="3"]:not([data-step-flow])').click()
            third = _told(page, 3, "")
            assert third, "the example has a step 3"
            assert _lit(page) == {"edges": third, "rows": [":3"]}
            assert page.locator("[data-graph-edge][data-focus-edge='true']").count() == len(third)

            # the second flow's row lights the second flow's wire, not main step 1
            page.locator('[data-step-row="1"][data-step-flow="At runtime"]').click()
            assert _lit(page) == {"edges": _told(page, 1, "At runtime"), "rows": ["At runtime:1"]}

            # the gap between a badge and its text is the row too
            row = page.locator('[data-step-row="2"]:not([data-step-flow])').bounding_box()
            page.mouse.click(row["x"] + 18, row["y"] + row["height"] / 2)
            assert _lit(page)["rows"] == [":2"]

            # a wire's own click marks its row in the list
            page.keyboard.press("Escape")
            page.locator(f'[data-edge-label="{third[0]}"]').click()
            assert _lit(page) == {"edges": [third[0]], "rows": [":3"]}
            page.keyboard.press("Escape")
            assert _lit(page) == everything, "Escape ends it"
            assert not errors, errors
        finally:
            browser.close()
