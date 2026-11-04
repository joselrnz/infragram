"""The page adds up what the export priced: the header's chip, the Cost tab's
total, its fixed and usage parts, each frame's subtotal, every item with its
lines, what was assumed, and what is free or not priced and why."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from infragram.author import Diagram
from infragram.exports import render_project_html
from infragram.pricing import Price, PriceLine, walk

pytestmark = pytest.mark.skipif(
    os.environ.get("INFRAGRAM_RUN_BROWSER_TESTS") != "1",
    reason="set INFRAGRAM_RUN_BROWSER_TESTS=1 to run Chromium editor checks",
)


def _line(label: str, quantity: float, unit: str, rate: float, kind: str = "fixed") -> PriceLine:
    return PriceLine(
        label=label,
        quantity=quantity,
        unit=unit,
        rate=rate,
        amount=round(quantity * rate, 4),
        kind=kind,
        assumed=kind == "usage",
    )


def _priced(lines: list[PriceLine], assumed: list[str]) -> dict:
    fixed = round(sum(item.amount for item in lines if item.kind == "fixed"), 2)
    usage = round(sum(item.amount for item in lines if item.kind == "usage"), 2)
    return Price(
        monthly=round(fixed + usage, 2),
        hourly=0.0,
        sizing={"region": "us-east-1", "hours": 730},
        assumed=assumed,
        rate="a test rate",
        source="a test table",
        priced="2026-10-08",
        lines=lines,
        fixed=fixed,
        usage=usage,
        origin="table",
    ).model_dump()


def _page(tmp_path: Path) -> Path:
    from infragram.nodes.aws import compute, databases, security_identity, storage
    from infragram.nodes.frames import aws

    with Diagram("Costed", "A priced diagram.", slug="costed", providers=("aws",)) as diagram:
        with aws.Cloud("AWS Cloud"), aws.Region("us-east-1"):
            with aws.VPC("VPC"):
                compute.EC2("Web")
                databases.RDS("Database")
            storage.SimpleStorageService("Assets")
            security_identity.IdentityAccessManagementRole("Role")
            security_identity.SecretsManager("Secrets")
    project = diagram.to_project()
    by_name = {element.name: element for element, _ in walk(project.topology)}
    by_name["Web"].attributes["price"] = _priced([_line("m6i.large", 1460, "hours", 0.096)], [])
    by_name["Database"].attributes["price"] = _priced(
        [_line("db.t3.micro", 730, "hours", 0.018), _line("storage", 20, "GB-month", 0.115)],
        ["instance_class"],
    )
    by_name["Assets"].attributes["price"] = _priced(
        [_line("Standard storage", 100, "GB-month", 0.023, "usage")], ["storage_gb"]
    )
    by_name["Role"].attributes["unpriced"] = "free: IAM roles cost nothing"
    by_name["Secrets"].attributes["unpriced"] = "not in the test table"
    source = tmp_path / "costed.html"
    source.write_text(render_project_html(project), encoding="utf-8")
    return source


def test_the_chip_and_the_cost_tab_add_up_what_the_export_priced(tmp_path: Path) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    source = _page(tmp_path)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(source.resolve().as_uri() + "?fresh=cost")
            page.wait_for_function("window.infragramEditor && window.infragramEditor.getState")
            # 140.16 + 13.14 + 2.30 + 2.30 = 157.90, in the inspector's Cost tab
            page.locator('[data-inspector-tab="cost"]').click()
            panel = page.locator('[data-inspector-panel="cost"]')
            panel.wait_for(state="visible")
            assert panel.locator(".cost-total").inner_text() == "≈ $157.90 a month"
            split = panel.locator(".cost-split").inner_text().split("\n")
            facts = dict(zip(split[::2], split[1::2], strict=True))
            assert facts["Fixed"] == "$155.60" and facts["Usage"] == "$2.30"
            assert facts["Priced"] == "3 of 4" and facts["Free"] == "1"
            assert facts["Sizes assumed"] == "2"
            # each frame adds up everything inside it, however deep
            frames = dict(
                row.split("\n") for row in panel.locator("[data-cost-frame]").all_inner_texts()
            )
            assert any(
                key.startswith("VPC") and value == "$155.60" for key, value in frames.items()
            )
            # items come most expensive first, each opening onto its lines
            items = panel.locator("[data-cost-item]")
            assert items.first.get_attribute("data-cost-item").startswith("web")
            database = panel.locator("[data-cost-item]", has_text="Database")
            database.locator("summary").click()
            assert database.locator("tr").count() == 2
            unpriced = panel.locator("[data-cost-unpriced]").inner_text()
            assert "Secrets: not in the test table" in unpriced and "1 free" in unpriced
            # Show on canvas: the card's flow, and its popup with the lines
            database.locator("[data-cost-show]").click()
            popup = page.locator("[data-canvas-popup]")
            popup.wait_for(state="visible")
            assert popup.locator("[data-popup-lines] tr").count() == 2
            assert not errors, errors
        finally:
            browser.close()


def test_a_diagram_with_no_prices_shows_no_chip(tmp_path: Path) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    from infragram.nodes.aws import compute

    with Diagram("Bare", "Nothing priced.", slug="bare", providers=("aws",)) as diagram:
        compute.EC2("Web")
    source = tmp_path / "bare.html"
    source.write_text(render_project_html(diagram.to_project()), encoding="utf-8")
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(source.resolve().as_uri() + "?fresh=bare")
            page.wait_for_function("window.infragramEditor && window.infragramEditor.getState")
            assert page.locator('[data-inspector-tab="cost"]').is_hidden()
        finally:
            browser.close()
