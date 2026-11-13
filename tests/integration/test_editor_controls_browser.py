"""Every control in the exported editor does what it says.

A control-by-control review of the chrome: each one is operated the way a
reader would -- a click, a key, a typed value -- and its effect is read back
from the editor's state or the page, not assumed from the click landing.

This is the suite the Material 3 port needed and did not have. That port
replaced every class on the page; nothing threw, and the faults showed up as
a card with no surface, a panel laid out as a plain stack and a button
variant that did not exist -- each found by eye, on a screenshot, one at a
time. A control that renders is not a control that works, and this is the
difference.

The fixture is an AWS document on purpose. The chrome is one UI across
nineteen libraries, so a suite that only ever drives it with the library it
was designed against proves the wrong thing.
"""

from __future__ import annotations

import os
import re
import zipfile
from contextlib import contextmanager
from pathlib import Path

import pytest

from infragram.author import Diagram, Edge
from infragram.exports import render_project_html, render_timeout_ms
from infragram.nodes import infragram as shared
from infragram.nodes.aws import (
    compute,
    containers,
    databases,
    networking_content_delivery as net,
    storage,
)
from infragram.nodes.frames import aws
from infragram.projects import CloudProject
from infragram.projects.parts import Layer
from infragram.terraform import folder_name, terraform_files

pytestmark = pytest.mark.skipif(
    os.environ.get("INFRAGRAM_RUN_BROWSER_TESTS") != "1",
    reason="set INFRAGRAM_RUN_BROWSER_TESTS=1 to run Chromium editor checks",
)

STATE = "() => window.infragramEditor.getState()"


def _menu_entry(page, action: str):
    """A right-click menu entry; one under More actions is opened to first."""
    entry = page.locator(f'[data-canvas-context-menu] [data-context-action="{action}"]')
    if entry.evaluate("element => Boolean(element.closest('[data-context-submenu-menu]'))"):
        page.locator("[data-context-submenu-toggle]").click()
    return entry


def _review_project() -> CloudProject:
    """Two cards inside a frame, three outside it, and three labelled wires."""
    with Diagram(
        "Control review",
        "Every control, operated once.",
        slug="control-review",
        providers=("aws",),
        display="card",
    ) as diagram:
        users = shared.identity.PublicUsers("Users", "browsers")
        with aws.VPC("vpc-review 10.0.0.0/16").row():
            balancer = net.ElasticLoadBalancing("Balancer", "HTTPS :443")
            web = compute.EC2("Web", "auto scaling")
        api = containers.ElasticKubernetesService("API", "EKS pods")
        sql = databases.RDS("SQL", "Multi-AZ")
        blobs = storage.SimpleStorageService("Blobs", "versioned")
        users >> Edge("HTTPS") >> balancer
        balancer >> Edge("HTTP") >> web
        api >> Edge("TDS", dashed=True) >> sql
        api >> blobs
    return diagram.to_project()


def _review_page(tmp_path: Path, libraries: str = "project") -> Path:
    source = tmp_path / f"control-review-{libraries}.html"
    source.write_text(render_project_html(_review_project(), libraries=libraries), encoding="utf-8")
    return source


@contextmanager
def _editor(
    tmp_path: Path,
    *,
    theme: str = "light",
    libraries: str = "project",
    viewport: tuple[int, int] = (1440, 900),
):
    """The page open in Chromium, with anything it logs as an error collected.

    A control that throws still looks like it worked from the outside -- the
    click lands, the handler dies, the state never moves -- so the page's own
    errors are part of what every test here asserts.
    """
    sync_api = pytest.importorskip("playwright.sync_api")
    source = _review_page(tmp_path, libraries)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(
                viewport={"width": viewport[0], "height": viewport[1]}, accept_downloads=True
            )
            errors: list[str] = []
            page.on("pageerror", lambda error: errors.append(f"pageerror: {error}"))
            page.on(
                "console",
                lambda message: (
                    errors.append(f"console: {message.text}") if message.type == "error" else None
                ),
            )
            page.goto(f"{source.resolve().as_uri()}?fresh={tmp_path.name}&theme={theme}")
            page.wait_for_load_state("load")
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            yield page, errors
            assert not errors, errors
        finally:
            browser.close()


def _state(page) -> dict:
    return page.evaluate(STATE)


def _node(page, name: str) -> dict:
    return next(node for node in _state(page)["nodes"] if node["name"] == name)


def _boundary(page, prefix: str) -> dict:
    return next(item for item in _state(page)["boundaries"] if item["name"].startswith(prefix))


def _edge(page, label: str) -> dict:
    return next(edge for edge in _state(page)["edges"] if edge.get("label") == label)


def _click_node(page, name: str, *, add: bool = False, button: str = "left") -> None:
    """One click on a card. With Shift it adds the card to the selection, and
    a right click selects it and opens its menu; a plain click only shows the
    card's flow, so a test that means to pick a card uses `_select_node`."""
    node_id = _node(page, name)["id"]
    page.locator(f'[data-graph-node][data-node-id="{node_id}"]').click(
        modifiers=["Shift"] if add else None, button=button
    )


def _select_node(page, name: str) -> None:
    """Pick a card for editing the way a reader does: a double click.

    A single click shows the card's flow and selects nothing. A double click
    on a card that is already selected opens its name for typing, so this is
    for a card that is not selected yet.
    """
    node_id = _node(page, name)["id"]
    page.locator(f'[data-graph-node][data-node-id="{node_id}"]').dblclick()


def _change(page, selector: str, value: str) -> None:
    """Type a value into a field and commit it, as leaving the field does."""
    field = page.locator(selector)
    field.fill(value)
    field.dispatch_event("change")


# ------------------------------------------------------------------ header


@pytest.mark.parametrize(
    "viewport",
    # the sidebar open beside a small window; collapsed at 900, the editor
    # 852 px wide; open on a laptop, the editor 928 px wide
    [(920, 531), (900, 800), (1300, 800)],
)
def test_narrow_header_keeps_toolbar_controls_clickable(
    tmp_path: Path, viewport: tuple[int, int]
) -> None:
    with _editor(tmp_path, viewport=viewport) as (page, _):
        toolbar = page.get_by_role("toolbar", name="Diagram controls")
        # every tool has room: none is pushed under the view switches
        assert toolbar.evaluate("el => el.scrollWidth <= el.clientWidth")
        # and the title keeps room for its name
        title = page.locator(".document-copy strong").bounding_box()
        assert title and title["width"] >= 80, title
        toolbar.get_by_role("button", name="Fit diagram to window").click(timeout=3000)
        grid = toolbar.get_by_role("button", name="Grid", exact=True)
        grid.click(timeout=3000)
        assert grid.get_attribute("aria-pressed") == "true"

        comments = page.locator("[data-comments-toggle]")
        comments.click(timeout=3000)
        assert page.locator("[data-comments-panel]").is_visible()
        page.locator("[data-comments-close]").click()

        inventory = page.locator("[data-inventory-toggle]")
        inventory.click(timeout=3000)
        assert inventory.get_attribute("aria-pressed") == "true"


def test_theme_palette_and_download_menu(tmp_path: Path) -> None:
    with _editor(tmp_path) as (page, _):
        body = page.locator("body")
        assert body.get_attribute("data-workspace-theme") == "light"

        toggle = page.locator("[data-theme-toggle]")
        assert toggle.get_attribute("aria-label") == "Theme: Light"
        # Three themes, the one in force checked; picking one closes the menu.
        theme_menu = page.locator("[data-theme-menu]")
        toggle.click()
        checked = [
            choice.get_attribute("aria-checked")
            for choice in theme_menu.locator("[data-theme-choice]").all()
        ]
        assert checked == ["true", "false", "false"]
        theme_menu.locator('[data-theme-choice="darker"]').click()
        assert theme_menu.get_attribute("open") is None
        assert body.get_attribute("data-workspace-theme") == "dark"
        assert body.get_attribute("data-workspace-palette") == "darker"
        assert toggle.get_attribute("aria-label") == "Theme: Darker"

        toggle.click()
        theme_menu.locator('[data-theme-choice="light"]').click()
        assert body.get_attribute("data-workspace-theme") == "light"
        assert body.get_attribute("data-workspace-palette") == "light"

        menu = page.locator("[data-download-menu]")
        assert menu.locator("summary").is_visible()
        menu.locator("summary").click()
        for hook, suffix in (
            ("data-download-template", ".infragram.json"),
            ("data-download-html", ".html"),
            ("data-download-svg", ".svg"),
        ):
            item = menu.locator(f"[{hook}]")
            assert item.is_visible(), hook
            assert suffix in item.text_content()

        with page.expect_download() as caught:
            menu.locator("[data-download-svg]").click()
        assert caught.value.suggested_filename.endswith(".svg")
        assert menu.get_attribute("open") is None

        # Mixed export settings belong to a panel; choosing quality keeps it
        # open, while Escape returns focus to its trigger.
        menu.locator("summary").click()
        assert page.get_by_role("dialog", name="Download diagram").is_visible()
        page.get_by_role("button", name="3× High", exact=True).click()
        assert menu.get_attribute("open") is not None
        assert menu.locator("[data-png-quality-label]").text_content() == "High"
        page.keyboard.press("Escape")
        assert menu.get_attribute("open") is None
        assert menu.locator("summary").evaluate("element => element === document.activeElement")

        # The whole panel fits a phone's viewport and allows every format to
        # scroll into view on a short screen.
        page.locator("[data-sidebar-logo-trigger]").click()
        page.set_viewport_size({"width": 375, "height": 667})
        menu.locator("summary").click()
        panel = page.get_by_role("dialog", name="Download diagram")
        box = panel.bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= 375
        assert box["y"] >= 0 and box["y"] + box["height"] <= 667
        assert menu.locator('[data-png-scale-choice="1"]').bounding_box()["height"] >= 44
        menu.locator("[data-download-html]").scroll_into_view_if_needed()
        assert menu.locator("[data-download-html]").is_visible()
        menu.locator("summary").click()


def _saved_terraform_tag(page) -> str:
    """The opening tag of the Terraform a page saved now would carry."""
    saved = page.evaluate("() => window.infragramEditor.exportHtml()")
    return re.search(r'<script[^>]*id="infragram-terraform"[^>]*>', saved).group(0)


def _download_terraform(page, style: str) -> dict[str, str]:
    """Choose a Terraform item and read the .zip it downloads: path -> text."""
    menu = page.locator("[data-download-menu]")
    menu.locator("summary").click()
    with page.expect_download() as caught:
        menu.locator(f'[data-download-terraform="{style}"]').click()
    folder = folder_name("control-review", style)
    assert caught.value.suggested_filename == f"{folder}.zip"
    with zipfile.ZipFile(caught.value.path()) as archive:
        assert archive.testzip() is None, "an entry's CRC does not match its bytes"
        assert all(name.startswith(f"{folder}/") for name in archive.namelist()), (
            "unzips into its folder"
        )
        return {
            name.removeprefix(f"{folder}/"): archive.read(name).decode("utf-8")
            for name in archive.namelist()
        }


def test_the_terraform_items_download_what_the_export_writes(tmp_path: Path) -> None:
    """The page carries the diagram's Terraform as the export wrote it, and
    each Terraform item downloads its folder as a .zip. Once the diagram is
    edited the files are still the exported diagram's, so the download says
    so -- and a page saved then is marked, so it says so too."""
    project = _review_project()
    with _editor(tmp_path) as (page, _):
        note = page.locator("[data-snackbar]")
        for style in ("resources", "modules"):
            assert _download_terraform(page, style) == terraform_files(project, style)[1], style
        assert "export it again" not in (note.text_content() or ""), "nothing was edited"
        assert "data-stale" not in _saved_terraform_tag(page)

        # Moving a card changes nothing the Terraform is written from.
        blobs = _node(page, "Blobs")
        box = page.locator(f'[data-graph-node][data-node-id="{blobs["id"]}"]').bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.mouse.down()
        page.mouse.move(
            box["x"] + box["width"] / 2 + 90, box["y"] + box["height"] / 2 + 60, steps=6
        )
        page.mouse.up()
        page.wait_for_timeout(250)
        assert (_node(page, "Blobs")["x"], _node(page, "Blobs")["y"]) != (blobs["x"], blobs["y"])
        _download_terraform(page, "resources")
        assert "export it again" not in (note.text_content() or ""), (
            "a move is not an edit of the Terraform"
        )

        page.evaluate(
            "([a, b]) => window.infragramEditor.connect(a, b)",
            [_node(page, "Web")["id"], _node(page, "SQL")["id"]],
        )
        assert _download_terraform(page, "resources") == terraform_files(project, "resources")[1]
        assert "export it again" in note.text_content(), (
            "an edited diagram's download says it is the exported one"
        )
        assert "data-stale" in _saved_terraform_tag(page), "the saved page is marked"

        # Undone, the diagram is the exported one again.
        page.locator('[data-editor-action="undo"]').click()
        page.evaluate("() => { document.querySelector('[data-snackbar]').textContent = ''; }")
        _download_terraform(page, "modules")
        assert "export it again" not in (note.text_content() or "")
        assert "data-stale" not in _saved_terraform_tag(page)


# ------------------------------------------------------------------ toolbar


def test_tidy_layout_puts_a_moved_card_back(tmp_path: Path) -> None:
    """The way out of a canvas somebody has pulled apart.

    What a reader made is kept -- names, details, styles, the frames they
    added -- and only geometry goes back, which is why the layout's own
    positions are taken by value before anything can touch them.
    """
    with _editor(tmp_path) as (page, _):
        was = _node(page, "API")
        handle = page.locator(f'[data-graph-node][data-node-id="{was["id"]}"]')
        box = handle.bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.mouse.down()
        page.mouse.move(
            box["x"] + box["width"] / 2 + 160, box["y"] + box["height"] / 2 + 110, steps=8
        )
        page.mouse.up()
        page.wait_for_timeout(250)
        assert (_node(page, "API")["x"], _node(page, "API")["y"]) != (was["x"], was["y"])

        # renaming it first: the tidy must not take the name back too
        page.locator('[data-inspector-tab="text"]').click()
        _change(page, '[data-content-control="name"]', "Cluster")

        page.locator('[data-editor-action="tidy-layout"]').click()
        page.wait_for_timeout(300)
        back = _node(page, "Cluster")
        assert (back["x"], back["y"]) == (was["x"], was["y"]), "geometry went back"
        assert back["name"] == "Cluster", "what the reader wrote stayed"


def test_toolbar_zoom_grid_undo_redo_and_delete(tmp_path: Path) -> None:
    with _editor(tmp_path) as (page, _):
        zoom = page.locator("[data-zoom-value]")
        opening = zoom.text_content()

        page.locator('[data-editor-action="zoom-in"]').click()
        assert zoom.text_content() != opening
        page.locator('[data-editor-action="zoom-reset"]').click()
        assert zoom.text_content() == "100%"
        page.locator('[data-editor-action="zoom-out"]').click()
        assert zoom.text_content() != "100%"
        page.locator('[data-editor-action="zoom-fit"]').click()
        assert zoom.text_content().endswith("%")

        # the grid opens hidden: a page is a drawing first
        grid = page.locator('[data-editor-action="toggle-grid"]')
        assert grid.get_attribute("aria-pressed") == "false"
        grid.click()
        assert grid.get_attribute("aria-pressed") == "true"
        assert _state(page)["canvas"]["showGrid"] is True
        grid.click()
        assert _state(page)["canvas"]["showGrid"] is False

        before = len(_state(page)["nodes"])
        _select_node(page, "Blobs")
        page.locator('[data-editor-action="delete"]').click()
        assert len(_state(page)["nodes"]) == before - 1

        page.locator('[data-editor-action="undo"]').click()
        assert len(_state(page)["nodes"]) == before
        page.locator('[data-editor-action="redo"]').click()
        assert len(_state(page)["nodes"]) == before - 1


# ------------------------------------------------------------------ sidebar


def test_sidebar_search_categories_and_rail(tmp_path: Path) -> None:
    with _editor(tmp_path) as (page, _):
        categories = page.locator("details[data-category-id]")
        assert categories.count() > 0

        search = page.locator("[data-sidebar-search]")
        search.fill("kubernetes")
        page.wait_for_timeout(250)
        shown = page.locator(".component-card[data-component-id]:visible")
        assert shown.count() > 0
        names = " ".join(shown.all_text_contents()).lower()
        assert "kubernetes" in names

        search.fill("")
        page.wait_for_timeout(250)

        # the brand row collapses the sidebar to its rail and back
        sidebar = page.locator("#provider-sidebar")
        wide = sidebar.bounding_box()["width"]
        page.locator("[data-sidebar-logo-trigger]").click()
        page.wait_for_timeout(300)
        assert sidebar.bounding_box()["width"] < wide
        page.locator("[data-sidebar-logo-trigger]").click()
        page.wait_for_timeout(300)
        assert sidebar.bounding_box()["width"] == wide


def test_library_menu_opens_and_applies(tmp_path: Path) -> None:
    with _editor(tmp_path, libraries="all") as (page, _):
        trigger = page.locator("[data-provider-menu-trigger]")
        assert trigger.get_attribute("aria-expanded") == "false"
        trigger.click()
        menu = page.locator("[data-provider-menu]")
        assert menu.is_visible()
        assert menu.locator("[data-provider-option]").count() > 1

        menu.locator("[data-provider-select-all]").click()
        assert all(box.is_checked() for box in menu.locator("[data-provider-option]").all())
        menu.locator("[data-provider-clear]").click()
        assert not any(box.is_checked() for box in menu.locator("[data-provider-option]").all())

        menu.locator('[data-provider-option="aws"]').check()
        menu.locator("[data-provider-apply]").click()
        page.wait_for_timeout(300)
        assert page.locator("[data-provider-summary]").text_content().strip() != ""


# ------------------------------------------------------------------ inspector


def test_inspector_tabs_collapse_and_diagram_settings(tmp_path: Path) -> None:
    with _editor(tmp_path) as (page, _):
        for panel in ("style", "text", "arrange", "layers", "diagram"):
            page.locator(f'[data-inspector-tab="{panel}"]').click()
            assert page.locator(f'[data-inspector-panel="{panel}"]').is_visible()

        inspector = page.locator("[data-right-inspector]")
        toggle = page.locator("[data-inspector-toggle]")
        assert inspector.get_attribute("data-collapsed") == "false"
        toggle.click()
        assert inspector.get_attribute("data-collapsed") == "true"
        toggle.click()
        assert inspector.get_attribute("data-collapsed") == "false"

        # the grid setting is a switch: it says what it is, not what it does
        switch = page.locator("[data-inspector-grid-toggle]")
        assert switch.get_attribute("role") == "switch"
        assert switch.get_attribute("aria-checked") == "false"
        switch.click()
        assert switch.get_attribute("aria-checked") == "true"
        assert _state(page)["canvas"]["showGrid"] is True
        switch.click()
        assert switch.get_attribute("aria-checked") == "false"

        # Connectors and Components are choices of two: each shows both and
        # marks the one in force, so picking the other changes the drawing
        # and picking the same one changes nothing.
        routing = page.locator("[data-inspector-routing]")
        assert routing.locator('[data-routing="around"]').get_attribute("aria-pressed") == "true"
        routing.locator('[data-routing="direct"]').click()
        assert _state(page)["canvas"]["routeAroundNodes"] is False
        assert routing.locator('[data-routing="direct"]').get_attribute("aria-pressed") == "true"
        routing.locator('[data-routing="around"]').click()
        assert _state(page)["canvas"]["routeAroundNodes"] is not False

        display = page.locator("[data-inspector-display]")
        display.locator('[data-project-display="icon"]').click()
        assert _state(page)["canvas"]["displayMode"] == "icon"
        display.locator('[data-project-display="card"]').click()
        assert _state(page)["canvas"]["displayMode"] == "card"

        # what the drawing holds, counted as it changes
        counts = {
            stat.get_attribute("data-diagram-stat"): int(stat.text_content())
            for stat in page.locator("[data-diagram-stat]").all()
        }
        state = _state(page)
        assert counts == {key: len(state[key]) for key in counts}
        assert counts["nodes"] > 0

        canvas = page.locator("[data-inspector-canvas]").text_content()
        assert "×" in canvas


def test_style_panel_display_modes_and_presets(tmp_path: Path) -> None:
    with _editor(tmp_path) as (page, _):
        page.locator('[data-inspector-tab="style"]').click()
        panel = '[data-inspector-panel="style"]'
        modes = page.locator(f"{panel} [data-display-mode]")
        presets = page.locator(f"{panel} [data-style-preset]")
        # nothing selected: both groups are out of reach
        assert all(item.is_disabled() for item in modes.all())
        assert all(item.is_disabled() for item in presets.all())

        _select_node(page, "Web")
        assert page.locator("[data-inspector-selection]").text_content().strip() == "Web"
        assert page.locator("[data-inspector-provider]").text_content().strip() != "—"

        page.locator(f'{panel} [data-display-mode="icon"]').click()
        assert _node(page, "Web")["displayMode"] == "icon"
        page.locator(f'{panel} [data-display-mode="card"]').click()
        assert _node(page, "Web")["displayMode"] == "card"

        # each outline sets a stroke of its own and nothing else
        strokes = set()
        for preset in ("accent-outline", "muted-outline", "danger-outline"):
            page.locator(f'{panel} [data-style-preset="{preset}"]').click()
            style = _node(page, "Web").get("style") or {}
            assert set(style) == {"stroke"}, (preset, style)
            strokes.add(style["stroke"])
        assert len(strokes) == 3
        # and neutral takes the outline off
        page.locator(f'{panel} [data-style-preset="neutral"]').click()
        assert "style" not in _node(page, "Web")


def test_text_panel_edits_a_card_and_its_type(tmp_path: Path) -> None:
    with _editor(tmp_path) as (page, _):
        _select_node(page, "Web")
        page.locator('[data-inspector-tab="text"]').click()

        _change(page, '[data-content-control="name"]', "Frontend")
        assert _node(page, "Frontend")["name"] == "Frontend"
        _change(page, '[data-content-control="detail"]', "two per zone")
        assert _node(page, "Frontend")["detail"] == "two per zone"

        _change(page, '[data-text-control="fontSize"]', "16")
        _change(page, '[data-text-control="opacity"]', "80")
        page.locator('[data-text-control="fontWeight"]').select_option("600")
        page.locator('[data-text-control="textAlign"]').select_option("center")
        text = _node(page, "Frontend").get("textStyle") or {}
        assert text.get("fontSize") == 16
        assert str(text.get("fontWeight")) == "600"
        assert text.get("textAlign") == "center"


def test_arrange_panel_geometry_order_and_transforms(tmp_path: Path) -> None:
    with _editor(tmp_path) as (page, _):
        _select_node(page, "API")
        page.locator('[data-inspector-tab="arrange"]').click()

        _change(page, '[data-exact-field="x"]', "600")
        _change(page, '[data-exact-field="y"]', "500")
        placed = _node(page, "API")
        assert (placed["x"], placed["y"]) == (600, 500)

        _change(page, '[data-exact-field="width"]', "240")
        assert _node(page, "API")["width"] == 240

        before = _node(page, "API")["order"]
        page.locator('[data-arrange-action="to-back"]').click()
        assert _node(page, "API")["order"] != before
        page.locator('[data-arrange-action="to-front"]').click()

        page.locator('[data-arrange-action="lock"]').click()
        assert _node(page, "API")["locked"] is True
        page.locator('[data-arrange-action="lock"]').click()
        assert not _node(page, "API").get("locked")

        # alignment needs two, so it is out of reach with one
        _click_node(page, "SQL", add=True)
        page.locator('[data-arrange-action="align-top"]').click()
        assert _node(page, "API")["y"] == _node(page, "SQL")["y"]

        page.locator('[data-arrange-action="group"]').click()
        assert any(item.get("userGroup") for item in _state(page)["boundaries"])


def test_layers_panel_lists_frames_and_layers(tmp_path: Path) -> None:
    with _editor(tmp_path) as (page, _):
        page.locator('[data-inspector-tab="layers"]').click()
        assert (
            page.locator("[data-frame-tree] [data-frame-tree-row]").count() > 0
            or page.locator("[data-frame-tree]").text_content().strip() != ""
        )
        rows = page.locator("[data-layer-list] [data-layer-row]")
        assert rows.count() > 0
        lock = page.locator("[data-layer-list] [data-layer-lock]").first
        opening = lock.get_attribute("aria-pressed")
        lock.click()
        assert lock.get_attribute("aria-pressed") != opening


def test_a_layer_row_names_the_library_its_name_leaves_out(tmp_path: Path) -> None:
    """A page can hold several libraries: a layer bound to one says which."""
    sync_api = pytest.importorskip("playwright.sync_api")
    project = _review_project()
    edge = Layer(
        id="edge-services", name="Edge services", provider="aws", order=len(project.layers)
    )
    project = project.model_copy(update={"layers": (*project.layers, edge)})
    source = tmp_path / "layers.html"
    source.write_text(render_project_html(project), encoding="utf-8")
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(f"{source.resolve().as_uri()}?fresh=layers")
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            page.locator('[data-inspector-tab="layers"]').click()
            rows = {
                row.locator(".md-list-item__headline").inner_text(): row.locator(
                    ".md-list-item__supporting"
                ).all_inner_texts()
                for row in page.locator("[data-layer-list] [data-layer-row]").all()
            }
            assert rows["Edge services"] == ["AWS"], rows
            # a layer already named for its library is not told it twice
            assert all(
                not supporting or supporting[0] not in name for name, supporting in rows.items()
            ), rows
        finally:
            browser.close()


# ------------------------------------------------------------------ canvas


def test_selection_toolbar_actions(tmp_path: Path) -> None:
    with _editor(tmp_path) as (page, _):
        _select_node(page, "API")
        toolbar = page.locator("[data-selection-toolbar]")
        assert toolbar.is_visible()
        assert page.locator("[data-selection-count-chip]").text_content().strip() == "1"

        before = len(_state(page)["nodes"])
        page.locator('[data-selection-action="duplicate"]').click()
        assert len(_state(page)["nodes"]) == before + 1

        page.locator('[data-selection-action="lock"]').click()
        assert any(node.get("locked") for node in _state(page)["nodes"])
        page.locator('[data-selection-action="lock"]').click()

        page.locator('[data-selection-action="delete"]').click()
        assert len(_state(page)["nodes"]) == before


def _toolbar_anchor(page) -> tuple[float, float]:
    """Where the toolbar hangs from: the middle of its bottom edge."""
    box = page.locator("[data-selection-toolbar]").bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"]


def test_the_selection_toolbar_moves_by_its_grip_and_stays_put(tmp_path: Path) -> None:
    """The toolbar floats over what it acts on, which is also what a reader
    is looking at. Dragged by its grip it stays where it was put -- over the
    next selection too -- until the grip is double-clicked."""
    with _editor(tmp_path) as (page, _):
        _select_node(page, "API")
        toolbar = page.locator("[data-selection-toolbar]")
        assert toolbar.get_attribute("data-pinned") is None
        start = _toolbar_anchor(page)

        # A press on the grip that does not move is a click: it pins nothing.
        page.locator("[data-selection-toolbar-grip]").click()
        assert toolbar.get_attribute("data-pinned") is None
        assert _toolbar_anchor(page) == start

        canvas = page.locator(".canvas-viewport").bounding_box()
        goal = (canvas["x"] + canvas["width"] / 2, canvas["y"] + canvas["height"] - 24)
        grip = page.locator("[data-selection-toolbar-grip]").bounding_box()
        page.mouse.move(grip["x"] + grip["width"] / 2, grip["y"] + grip["height"] / 2)
        page.mouse.down()
        page.mouse.move(
            grip["x"] + grip["width"] / 2 + goal[0] - start[0],
            grip["y"] + grip["height"] / 2 + goal[1] - start[1],
            steps=10,
        )
        page.mouse.up()
        moved = _toolbar_anchor(page)
        assert abs(moved[0] - goal[0]) <= 1 and abs(moved[1] - goal[1]) <= 1, (moved, goal)
        assert toolbar.get_attribute("data-pinned") is not None
        kept = page.evaluate(
            "() => JSON.parse(localStorage.getItem('infragram-workspace-layout')).selectionToolbar"
        )
        assert kept and kept["x"] > 0 and kept["y"] > 0, "kept with the panels' layout"

        _select_node(page, "SQL")
        page.wait_for_timeout(150)
        stayed = _toolbar_anchor(page)
        assert abs(stayed[0] - moved[0]) <= 1 and abs(stayed[1] - moved[1]) <= 1, (
            "it stays over the next selection"
        )

        page.locator("[data-selection-toolbar-grip]").dblclick()
        page.wait_for_timeout(150)
        assert toolbar.get_attribute("data-pinned") is None
        sql = page.locator(
            f'[data-graph-node][data-node-id="{_node(page, "SQL")["id"]}"] [data-node-surface]'
        ).bounding_box()
        assert _toolbar_anchor(page)[1] <= sql["y"] + 1, "back above what it acts on"
        assert (
            page.evaluate(
                "() => JSON.parse(localStorage.getItem('infragram-workspace-layout')).selectionToolbar"
            )
            is None
        )


def _park_at_edge(page, name: str, edge: str) -> None:
    """Scroll the canvas so a component sits at one edge of what is visible."""
    node_id = _node(page, name)["id"]
    page.evaluate(
        """([id, edge]) => {
      const viewport = document.querySelector('.canvas-viewport');
      const card = document.querySelector(`[data-graph-node][data-node-id="${id}"]`);
      const v = viewport.getBoundingClientRect(), c = card.getBoundingClientRect();
      if (edge === 'left') viewport.scrollLeft += c.left - v.left - 4;
      else viewport.scrollTop += c.top - v.top - 4;
    }""",
        [node_id, edge],
    )
    page.wait_for_timeout(250)


def _inside_the_canvas(page) -> dict:
    return page.evaluate("""() => {
      const v = document.querySelector('.canvas-viewport').getBoundingClientRect();
      const t = document.querySelector('[data-selection-toolbar]').getBoundingClientRect();
      return {left: t.left >= v.left - 0.5, right: t.right <= v.right + 0.5,
              top: t.top >= v.top - 0.5, bottom: t.bottom <= v.bottom + 0.5,
              toolbar: [t.left, t.top, t.right, t.bottom].map(Math.round),
              viewport: [v.left, v.top, v.right, v.bottom].map(Math.round)};
    }""")


def test_the_selection_toolbar_stays_inside_the_canvas(tmp_path: Path) -> None:
    """Centred above what it acts on, the toolbar used to run off the canvas:
    a component by the left edge had the count and both align buttons -- and
    the grip it is moved by -- behind the sidebar, and one at the top had the
    toolbar above the view. It slides back in, and flips below when there is
    no room above. (Upstreamed from the Azure edition with its fix.)"""
    with _editor(tmp_path, viewport=(1100, 760)) as (page, _):
        for _ in range(3):
            page.locator('[data-editor-action="zoom-in"]').click()
        page.wait_for_timeout(300)
        _select_node(page, "API")
        page.wait_for_timeout(250)

        _park_at_edge(page, "API", "left")
        # The case being tested: the card really is at the canvas's left edge.
        assert page.evaluate(
            """id => {
          const v = document.querySelector('.canvas-viewport').getBoundingClientRect();
          const c = document.querySelector(`[data-graph-node][data-node-id="${id}"]`).getBoundingClientRect();
          return c.left - v.left < 40;
        }""",
            _node(page, "API")["id"],
        ), "the card could not be brought to the left edge"
        where = _inside_the_canvas(page)
        assert where["left"] and where["right"], f"toolbar off the canvas sideways: {where}"

        _park_at_edge(page, "API", "top")
        where = _inside_the_canvas(page)
        assert where["top"], f"toolbar above the canvas: {where}"


def test_a_nodes_dots_stand_off_its_sides_and_its_wires_keep_the_ink(tmp_path: Path) -> None:
    """The dots a selected node shows are where a drag starts a wire, so they
    stand 10 screen pixels off the middle of each side of its outline, clear
    of the drawing. The wire itself still meets the ink: on a person, the side
    wires meet the shoulders, three quarters down the glyph."""
    with _editor(tmp_path) as (page, _):
        page.evaluate("() => window.infragramEditor.setDisplayMode('icon')")
        page.wait_for_timeout(300)
        users = _node(page, "Users")
        assert users["displayMode"] == "icon" and users.get("inkPorts"), (
            "a person's ports are set by hand"
        )
        _select_node(page, "Users")
        page.wait_for_timeout(200)
        found = page.evaluate(
            """id => {
          const node = document.querySelector(`[data-graph-node][data-node-id="${id}"]`);
          const inverse = node.ownerSVGElement.getScreenCTM().inverse();
          const dots = Object.fromEntries([...node.querySelectorAll('[data-node-port]')].map(group => {
            const box = group.querySelector('circle.node-port-dot').getBoundingClientRect();
            const origin = group.getScreenCTM();
            return [group.dataset.nodePort, {
              off: [box.x + box.width / 2 - origin.e, box.y + box.height / 2 - origin.f],
              size: box.width}];
          }));
          const ends = window.infragramEditor.getState().edges.filter(edge => edge.source === id).map(edge => {
            const path = document.querySelector(`[data-graph-edge][data-edge-id="${CSS.escape(edge.id)}"]`);
            return [Number(path.dataset.sourceX), Number(path.dataset.sourceY)];
          });
          const glyph = node.querySelector('image');
          return {dots, ends, glyph: {y: Number(glyph.getAttribute('y')), size: Number(glyph.getAttribute('height'))}};
        }""",
            users["id"],
        )
        outward = {"top": (0, -1), "right": (1, 0), "bottom": (0, 1), "left": (-1, 0)}
        for side, (dx, dy) in outward.items():
            dot = found["dots"][side]
            assert abs(dot["off"][0] - 10 * dx) <= 1.5 and abs(dot["off"][1] - 10 * dy) <= 1.5, (
                side,
                dot,
            )
            assert 9 <= dot["size"] <= 14, (side, dot)  # 5 px round, its stroke outside
        ends = found["ends"]
        assert ends, "the fixture wires Users to the balancer"
        top = users["y"] + found["glyph"]["y"]
        for end in ends:
            along = (end[1] - top) / found["glyph"]["size"]
            assert along > 0.65, (end, along)


def test_context_menu_actions(tmp_path: Path) -> None:
    with _editor(tmp_path) as (page, _):
        _click_node(page, "SQL", button="right")
        menu = page.locator("[data-canvas-context-menu]")
        assert menu.is_visible()
        assert menu.locator("[data-context-menu-title]").text_content().strip() == "SQL"

        _menu_entry(page, "display-icon").click()
        assert _node(page, "SQL")["displayMode"] == "icon"

        _click_node(page, "SQL", button="right")
        _menu_entry(page, "open-arrange").click()
        assert page.locator('[data-inspector-panel="arrange"]').is_visible()

        _click_node(page, "SQL", button="right")
        before = len(_state(page)["nodes"])
        menu.locator('[data-context-action="delete"]').click()
        assert len(_state(page)["nodes"]) == before - 1


# ------------------------------------------------------------------ drawer


def test_drawer_tabs_and_expansion(tmp_path: Path) -> None:
    """The bottom drawer has no counterpart in the other edition, so nothing
    else drives it."""
    with _editor(tmp_path) as (page, _):
        drawer = page.locator("[data-bottom-drawer]")
        assert drawer.get_attribute("data-expanded") == "false"

        page.locator("[data-bottom-toggle]").click()
        assert drawer.get_attribute("data-expanded") == "true"

        for panel in ("builder", "examples"):
            page.locator(f'[data-bottom-tab="{panel}"]').click()
            assert page.locator(f'[data-bottom-panel="{panel}"]').is_visible()

        page.locator("[data-bottom-toggle]").click()
        assert drawer.get_attribute("data-expanded") == "false"


# ------------------------------------------------------------------ drag


def test_a_palette_card_dropped_on_the_canvas_becomes_a_component(tmp_path: Path) -> None:
    """The drop target is the drawing itself.

    Dropping on `.diagram-stage` -- the box the drawing sits in -- does
    nothing at all, which is worth knowing before spending an afternoon on a
    gesture that was landing an inch wide.
    """
    with _editor(tmp_path) as (page, _):
        before = len(_state(page)["nodes"])
        page.locator("[data-sidebar-search]").fill("bucket")
        page.wait_for_timeout(350)
        card = page.locator(".component-card[data-component-id]:visible").first
        assert card.count() == 1
        assert card.get_attribute("draggable") == "true"

        card.drag_to(
            page.locator("svg[data-infragram-diagram]"), target_position={"x": 340, "y": 340}
        )
        page.wait_for_timeout(400)
        assert len(_state(page)["nodes"]) == before + 1


def test_dragging_a_card_moves_it_and_one_undo_puts_it_back(tmp_path: Path) -> None:
    with _editor(tmp_path) as (page, _):
        was = _node(page, "API")
        handle = page.locator(f'[data-graph-node][data-node-id="{was["id"]}"]')
        box = handle.bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.mouse.down()
        page.mouse.move(
            box["x"] + box["width"] / 2 + 140, box["y"] + box["height"] / 2 + 90, steps=8
        )
        page.mouse.up()
        page.wait_for_timeout(250)

        moved = _node(page, "API")
        assert (moved["x"], moved["y"]) != (was["x"], was["y"])

        page.locator('[data-editor-action="undo"]').click()
        page.wait_for_timeout(200)
        back = _node(page, "API")
        assert (back["x"], back["y"]) == (was["x"], was["y"])


def test_dragging_a_frame_carries_what_it_holds(tmp_path: Path) -> None:
    """A frame is a region. Moving the box and leaving its contents behind is
    the failure this is here for."""
    with _editor(tmp_path) as (page, _):
        frame = _boundary(page, "vpc-review")
        inside = [n for n in _state(page)["nodes"] if n.get("boundaryId") == frame["id"]]
        assert inside, "the fixture's frame holds cards"

        element = page.locator(f'[data-graph-boundary][data-boundary-id="{frame["id"]}"]')
        box = element.bounding_box()
        page.mouse.move(box["x"] + 40, box["y"] + 8)
        page.mouse.down()
        page.mouse.move(box["x"] + 40 + 100, box["y"] + 8 + 70, steps=8)
        page.mouse.up()
        page.wait_for_timeout(250)

        after = _state(page)
        now = next(b for b in after["boundaries"] if b["id"] == frame["id"])
        assert (now["x"], now["y"]) != (frame["x"], frame["y"])
        for was in inside:
            moved = next(n for n in after["nodes"] if n["id"] == was["id"])
            assert (moved["x"], moved["y"]) != (was["x"], was["y"]), was["name"]
            assert moved.get("boundaryId") == frame["id"]


def test_a_marquee_across_empty_canvas_selects_what_it_covers(tmp_path: Path) -> None:
    with _editor(tmp_path, viewport=(1600, 1000)) as (page, _):
        # on the drawing, not the pane around it: the marquee begins on a
        # pointerdown on the SVG, and the viewport's corner is outside it
        stage = page.locator("svg[data-infragram-diagram]").bounding_box()
        page.mouse.move(stage["x"] + 6, stage["y"] + 6)
        page.mouse.down()
        page.mouse.move(stage["x"] + stage["width"] - 6, stage["y"] + stage["height"] - 6, steps=12)
        assert page.locator("[data-marquee-selection]").count() == 1, "no marquee was drawn"
        page.mouse.up()
        page.wait_for_timeout(300)

        chip = page.locator("[data-selection-count-chip]")
        assert chip.is_visible(), "the selection toolbar did not come up"
        assert int(chip.text_content().strip()) > 1


def test_dragging_port_to_port_draws_a_connector(tmp_path: Path) -> None:
    """Port to port, and nothing else.

    A drag that ends on the middle of the target card connects nothing: the
    gesture has to land on the target's own seat. A preview wire follows the
    pointer while it is in flight, which is how a reader knows the drag took.
    """
    with _editor(tmp_path) as (page, _):
        before = len(_state(page)["edges"])
        source, target = _node(page, "SQL"), _node(page, "Blobs")
        page.locator(f'[data-graph-node][data-node-id="{source["id"]}"]').click()
        page.wait_for_timeout(250)

        start = page.locator(f'[data-node-id="{source["id"]}"] [data-node-port="right"]')
        end = page.locator(f'[data-node-id="{target["id"]}"] [data-node-port="left"]')
        assert start.count() == 1 and end.count() == 1
        # a card shows its dots on hover or selected; read each where it shows
        page.locator(f'[data-graph-node][data-node-id="{target["id"]}"]').hover()
        page.wait_for_timeout(200)
        b = end.bounding_box()
        page.locator(f'[data-graph-node][data-node-id="{source["id"]}"]').hover()
        page.wait_for_timeout(200)
        a = start.bounding_box()

        page.mouse.move(a["x"] + a["width"] / 2 - 6, a["y"] + a["height"] / 2)
        page.mouse.down()
        page.mouse.move((a["x"] + b["x"]) / 2, (a["y"] + b["y"]) / 2, steps=6)
        assert page.locator("[data-connection-preview]").count() == 1, "no wire followed the drag"
        page.mouse.move(b["x"] + b["width"] / 2 + 6, b["y"] + b["height"] / 2, steps=8)
        page.mouse.up()
        page.wait_for_timeout(350)

        after = _state(page)["edges"]
        assert len(after) == before + 1
        fresh = after[-1]
        assert {fresh["source"], fresh["target"]} == {source["id"], target["id"]}


def test_frame_presets_reach_the_palette_and_drop_a_nested_stack(tmp_path: Path) -> None:
    """The sidebar builds its catalog as a reader opens it, so a preset is
    not in the page until its category is. A count of zero means nothing was
    opened, not that the library ships none."""
    with _editor(tmp_path) as (page, _):
        assert page.locator("[data-frame-preset]").count() == 0, "the catalog is built lazily"

        for index in range(page.locator("details[data-category-id]").count()):
            page.locator("details[data-category-id]").nth(index).locator("summary").click()
            page.wait_for_timeout(150)
            if page.locator("[data-frame-preset]").count():
                break
        presets = page.locator("[data-frame-preset]")
        assert presets.count() > 0, "this library ships frame presets"

        # and a preset sits inside its own library's group, which is
        # collapsed too; the core frames' group comes first and has none
        group = page.locator("details.frame-group:has([data-frame-preset])").first
        if group.count() and group.get_attribute("open") is None:
            group.locator("> summary").click()
            page.wait_for_timeout(250)

        before = len(_state(page)["boundaries"])
        first = page.locator("[data-frame-preset]:visible").first
        assert first.count() == 1, "no preset is on screen once its group is open"
        first.scroll_into_view_if_needed()
        assert first.get_attribute("draggable") == "true"
        # a drop point inside the drawing: past its edge the stage behind it
        # takes the pointer and nothing lands
        stage = page.locator("svg[data-infragram-diagram]")
        box = stage.bounding_box()
        first.drag_to(stage, target_position={"x": box["width"] * 0.2, "y": box["height"] * 0.8})
        page.wait_for_timeout(700)
        assert len(_state(page)["boundaries"]) > before


# ------------------------------------------------------- the shortcut sheet


def test_the_shortcut_sheet_opens_on_the_key_it_advertises(tmp_path: Path) -> None:
    """Both ways in and both ways out, and the keyboard stays inside it.

    A sheet that Tab walks out of is worse than none: the reader is typing
    into a page the sheet covers, with no sign of where they are.
    """
    with _editor(tmp_path) as (page, _):
        sheet = page.locator("[data-shortcut-sheet]")
        assert sheet.is_hidden()

        page.locator('[data-editor-action="shortcuts"]').click()
        assert sheet.is_visible()
        assert sheet.get_attribute("aria-modal") == "true"
        close = sheet.locator("[data-shortcut-sheet-close]")
        assert page.evaluate(
            "() => document.activeElement.hasAttribute('data-shortcut-sheet-close')"
        )

        # Tab from the last stop comes back to the first, rather than
        # stepping out into the chrome the sheet is covering.
        stops = sheet.locator(
            "button, a[href], input, select, textarea, [tabindex]:not([tabindex='-1'])"
        )
        assert stops.count() >= 1
        for _ in range(stops.count() + 1):
            page.keyboard.press("Tab")
        assert page.evaluate(
            "() => document.querySelector('[data-shortcut-sheet]').contains(document.activeElement)"
        )

        # ... and the drawing behind it is left alone while it is open: the
        # keys the sheet needs are not also acting on a canvas the reader
        # cannot see. Delete would otherwise delete the selection.
        assert _state(page)["nodes"], "the fixture has something to lose"
        before = len(_state(page)["nodes"])
        nothing_selected = page.locator("[data-inspector-selection]").text_content().strip()
        page.keyboard.press("Delete")
        page.keyboard.press("Control+a")
        assert len(_state(page)["nodes"]) == before, "Delete reached the canvas"
        assert (
            page.locator("[data-inspector-selection]").text_content().strip() == nothing_selected
        ), "Ctrl+A reached the canvas"

        close.click()
        assert sheet.is_hidden()
        assert sheet.get_attribute("aria-modal") is None

        page.keyboard.press("?")
        assert sheet.is_visible()
        page.keyboard.press("Escape")
        assert sheet.is_hidden()


def test_typing_a_question_mark_into_a_field_does_not_open_the_sheet(tmp_path: Path) -> None:
    """The key is only a shortcut where nothing is being typed into."""
    with _editor(tmp_path) as (page, _):
        _select_node(page, "API")
        page.locator('[data-inspector-tab="text"]').click()
        name = page.locator('[data-content-control="name"]')
        name.click()
        name.type("Why?")
        assert page.locator("[data-shortcut-sheet]").is_hidden()
        assert "?" in name.input_value()


# ------------------------------------------------------------- the snackbar


def test_what_an_action_did_is_shown_and_not_only_announced(tmp_path: Path) -> None:
    """Every action reports what it did. The live region is sr-only, so
    before the snackbar those reports reached a screen reader and nobody
    else -- "Locked layer ..." included, which is the one a reader most
    needs when a drag does nothing.
    """
    with _editor(tmp_path) as (page, _):
        snackbar = page.locator("[data-snackbar]")
        assert snackbar.is_hidden(), "nothing has happened yet"
        # It must not read itself out: the live region already announces.
        assert snackbar.get_attribute("aria-hidden") == "true"

        page.locator('[data-editor-action="tidy-layout"]').click()
        assert snackbar.is_visible()
        assert "Tidied" in snackbar.text_content()

        # A second report replaces the first rather than stacking.
        page.locator('[data-editor-action="toggle-grid"]').click()
        assert snackbar.count() == 1
        assert "Tidied" not in snackbar.text_content()


def test_the_reports_that_would_flicker_are_announced_but_not_shown(tmp_path: Path) -> None:
    """A snackbar on every selection and every pixel of a drag is a snackbar
    nobody reads. Those still reach the live region."""
    with _editor(tmp_path) as (page, _):
        announced = page.locator("[data-search-status]")
        snackbar = page.locator("[data-snackbar]")

        node = _node(page, "Web")
        handle = page.locator(f'[data-graph-node][data-node-id="{node["id"]}"]')
        box = handle.bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.mouse.down()
        page.mouse.move(
            box["x"] + box["width"] / 2 + 80, box["y"] + box["height"] / 2 + 60, steps=6
        )
        page.mouse.up()
        page.wait_for_timeout(200)
        assert "moved" in announced.text_content().lower(), "it still reaches the live region"
        assert snackbar.is_hidden(), "moving a card is not news"

        # The contrast: an action a reader would want confirmed does show.
        page.locator('[data-editor-action="tidy-layout"]').click()
        assert snackbar.is_visible()


# ------------------------------------------------- what a picked wire offers


def _shown(page) -> list[str]:
    """The buttons the selection toolbar is actually offering."""
    return page.evaluate(
        "() => [...document.querySelectorAll("
        "'[data-selection-toolbar] [data-selection-action]')]"
        ".filter(button => !button.hidden).map(button => button.dataset.selectionAction)"
    )


def _pick_edge(page, label: str) -> dict:
    """Select a wire for editing: a double click, as for a card -- one click
    only shows the wire's flow."""
    edge = _edge(page, label)
    page.locator(f'[data-graph-edge][data-edge-id="{edge["id"]}"]').dblclick(force=True)
    page.wait_for_timeout(250)
    return edge


def test_a_picked_wire_gets_a_toolbar_of_its_own(tmp_path: Path) -> None:
    """It used to get nothing.

    The toolbar is positioned from the selection's bounds, which are built
    from nodes and frames, so a wire produced no bounds and the toolbar
    stayed hidden: a reader could select a connector and had no way to act
    on it but Delete.
    """
    with _editor(tmp_path) as (page, _):
        toolbar = page.locator("[data-selection-toolbar]")
        assert toolbar.is_hidden(), "nothing is picked yet"

        _select_node(page, "Web")
        on_object = _shown(page)
        assert "align-left" in on_object and "lock" in on_object
        assert not [name for name in on_object if name.startswith("edge-")], (
            "an object has no direction to reverse"
        )

        _pick_edge(page, "HTTPS")
        assert toolbar.is_visible(), "a picked wire gets a toolbar"
        on_edge = _shown(page)
        assert {"edge-edit-label", "edge-reverse", "edge-reset-route"} <= set(on_edge)
        assert "align-left" not in on_edge and "group" not in on_edge, (
            "a wire cannot be aligned or grouped"
        )
        assert "delete" in on_edge, "either way it can be deleted"


def test_edit_label_opens_the_text_panel_on_the_wire(tmp_path: Path) -> None:
    """The button has to reach the field, not merely exist. `openTextEditor`
    takes the item *and* its kind, and called with one argument it returns
    without doing anything -- a button that looks live and does nothing."""
    with _editor(tmp_path) as (page, _):
        _pick_edge(page, "HTTPS")
        page.locator('[data-selection-action="edge-edit-label"]').click()
        page.wait_for_timeout(300)
        assert page.locator('[data-inspector-panel="text"]').is_visible()
        label = page.locator('[data-edge-label-control="label"]')
        assert label.is_visible(), "the label field is where the reader was sent"
        assert label.input_value() == "HTTPS"


def test_reverse_swaps_the_ends_and_undo_puts_them_back(tmp_path: Path) -> None:
    with _editor(tmp_path) as (page, _):
        was = _pick_edge(page, "HTTPS")
        page.locator('[data-selection-action="edge-reverse"]').click()
        page.wait_for_timeout(250)
        now = _edge(page, "HTTPS")
        assert (now["source"], now["target"]) == (was["target"], was["source"])

        page.keyboard.press("Control+z")
        page.wait_for_timeout(250)
        back = _edge(page, "HTTPS")
        assert (back["source"], back["target"]) == (was["source"], was["target"])


def test_reset_route_is_offered_only_to_a_wire_somebody_shaped(tmp_path: Path) -> None:
    """A button that is always live is a button that says nothing. Reset
    route has nothing to reset until the wire has been bent or pinned."""
    with _editor(tmp_path) as (page, _):
        _pick_edge(page, "HTTPS")
        reset = page.locator('[data-selection-action="edge-reset-route"]')
        assert reset.is_disabled(), "nobody has shaped this wire"

        # Move the label by hand: where a label was put is part of the
        # route, the same as a bend or an end pinned to a side.
        page.keyboard.press("ArrowRight")
        page.wait_for_timeout(250)
        assert _edge(page, "HTTPS")["labelPlacement"]["mode"] == "manual"
        assert not reset.is_disabled(), "now there is something to reset"

        reset.click()
        page.wait_for_timeout(250)
        assert "labelPlacement" not in _edge(page, "HTTPS")
        assert reset.is_disabled(), "and nothing to reset again"


def test_the_lock_button_keeps_its_glyph(tmp_path: Path) -> None:
    """It is an icon button. Writing text into one removes the picture and
    leaves a word in a 32px circle, which is what it used to do the moment
    anything was selected."""
    with _editor(tmp_path) as (page, _):
        lock = page.locator('[data-selection-action="lock"]')
        glyphs = "() => document.querySelector('[data-selection-action=\"lock\"]').querySelectorAll('svg').length"

        _select_node(page, "Web")
        page.wait_for_timeout(200)
        assert page.evaluate(glyphs) == 1, "the padlock is still a padlock"
        assert lock.text_content().strip() == ""
        assert lock.get_attribute("aria-pressed") == "false"

        lock.click()
        page.wait_for_timeout(250)
        assert page.evaluate(glyphs) == 1, "and still one after locking"
        assert lock.text_content().strip() == ""
        assert lock.get_attribute("aria-pressed") == "true"
        assert "Unlock" in lock.get_attribute("aria-label")


def test_the_right_click_menu_offers_a_wire_its_own_entries(tmp_path: Path) -> None:
    with _editor(tmp_path) as (page, _):
        edge = _edge(page, "HTTPS")
        page.locator(f'[data-graph-edge][data-edge-id="{edge["id"]}"]').click(
            force=True, button="right"
        )
        page.wait_for_timeout(250)
        menu = page.locator("[data-canvas-context-menu]")
        assert menu.is_visible()
        assert not menu.locator('[data-context-action="edge-reverse"]').is_hidden()
        assert menu.locator('[data-context-action="group"]').is_hidden(), "a wire cannot be grouped"
        menu.locator('[data-context-action="edge-reverse"]').click()
        page.wait_for_timeout(250)
        now = _edge(page, "HTTPS")
        assert (now["source"], now["target"]) == (edge["target"], edge["source"])

        # ... and the other way: an object is offered none of them. Checking
        # only that a wire sees its entries would pass on a menu that shows
        # every entry to everything.
        _click_node(page, "Web", button="right")
        page.wait_for_timeout(250)
        assert menu.locator('[data-context-action="edge-reverse"]').is_hidden()
        assert menu.locator('[data-context-action="edge-reset-route"]').is_hidden()
        assert _menu_entry(page, "group").is_visible()


def test_a_panel_with_nothing_to_act_on_says_so(tmp_path: Path) -> None:
    """Style, Text and Arrange used to open on a row of dead controls when
    nothing was picked, with no hint that picking something was the point.

    The stylesheet has carried the rule for this since the Material 3 port
    and `empty_state()` has been a component all along; neither had anything
    to act on in the inspector.
    """
    with _editor(tmp_path) as (page, _):
        for tab, live in (
            ("style", "[data-style-preset]"),
            ("text", '[data-content-control="name"]'),
            ("arrange", "[data-arrange-action]"),
        ):
            page.locator(f'[data-inspector-tab="{tab}"]').click()
            panel = page.locator(f'[data-inspector-panel="{tab}"]')
            empty = panel.locator(".md-empty-state")

            assert panel.get_attribute("data-empty") == "true", tab
            assert empty.is_visible(), f"{tab}: no empty state"
            assert "Nothing selected" in empty.text_content()
            assert not panel.locator(live).first.is_visible(), (
                f"{tab}: dead controls are still on show"
            )
            # The heading stays, so the panel is still recognisable.
            assert panel.locator("h2").is_visible()

        _select_node(page, "Web")
        page.wait_for_timeout(250)
        for tab, live in (
            ("style", "[data-style-preset]"),
            ("text", '[data-content-control="name"]'),
            ("arrange", "[data-arrange-action]"),
        ):
            page.locator(f'[data-inspector-tab="{tab}"]').click()
            panel = page.locator(f'[data-inspector-panel="{tab}"]')
            assert panel.get_attribute("data-empty") == "false", tab
            assert not panel.locator(".md-empty-state").is_visible(), tab
            assert panel.locator(live).first.is_visible(), f"{tab}: the controls did not come back"


# ----------------------------------------- the canvas sets words like the picture


def test_labels_and_details_are_set_in_the_face_the_picture_uses(tmp_path: Path) -> None:
    """The canvas sets connector labels and detail lines in the face the
    static picture uses; if the two drift apart, the canvas a reader edits and
    the file they export set the same words in two faces."""
    from infragram.builders.scene import Style

    face = Style().sans.split(",")[0].strip("'\" ")
    with _editor(tmp_path) as (page, _):
        faces = page.evaluate("""() => {
          const svg = document.querySelector('[data-infragram-diagram]');
          const family = el => getComputedStyle(el).fontFamily.split(',')[0].replace(/["']/g, '').trim();
          return {
            labels: [...svg.querySelectorAll('[data-edge-label] text')].map(family),
            details: [...svg.querySelectorAll('[data-graph-node] text')]
              .filter(t => t.getAttribute('font-size') === '9' || t.getAttribute('font-size') === '10')
              .map(family),
          };
        }""")
    assert faces["labels"], "the fixture has labelled wires"
    assert set(faces["labels"]) == {face}, faces["labels"]
    assert faces["details"], "the fixture has detail lines"
    assert set(faces["details"]) == {face}, faces["details"]


def test_a_label_mask_is_sized_for_the_face_it_covers(tmp_path: Path) -> None:
    """The mask was sized at 0.62 em a character -- a mono measure -- around
    Roboto, which averages 0.50. A mono face an author picks is wider still,
    and tracked, and is measured as one."""
    with _editor(tmp_path) as (page, _):
        edge = _edge(page, "HTTPS")
        mask = page.locator(f'[data-edge-label="{edge["id"]}"] rect')
        text = page.locator(f'[data-edge-label="{edge["id"]}"] text')
        # 5 characters at 11 px: ceil((5 * 11 * 0.55 + 10) / 4) * 4
        assert mask.get_attribute("width") == "44"
        assert text.get_attribute("letter-spacing") == "0"

        # selected for editing, so the Text panel acts on the wire
        page.locator(f'[data-graph-edge][data-edge-id="{edge["id"]}"]').dblclick(force=True)
        page.locator('[data-inspector-tab="text"]').click()
        page.locator('[data-text-control="fontFamily"]').select_option("Geist Mono")
        page.wait_for_timeout(250)
        # the same five characters at the mono measure: ceil((5 * 11 * 0.72 + 10) / 4) * 4
        assert mask.get_attribute("width") == "52"
        assert text.get_attribute("letter-spacing") == "0.08em"
        assert "monospace" in text.get_attribute("font-family")


def test_a_selected_wire_reads_as_selected_at_a_glance(tmp_path: Path) -> None:
    with _editor(tmp_path) as (page, _):
        edge = _edge(page, "HTTPS")
        wire = page.locator(f'[data-graph-edge][data-edge-id="{edge["id"]}"]')
        # one click shows the wire's flow and selects nothing; the halo is
        # for a wire picked for editing, which takes a double click
        wire.click(force=True)
        page.wait_for_timeout(250)
        assert wire.get_attribute("data-focus-edge") == "true", "a click shows the wire's flow"
        halo = page.locator("[data-edge-selection-halo]")
        assert halo.count() == 0, "a flow is not a selection"
        wire.dblclick(force=True)
        page.wait_for_timeout(250)
        assert halo.count() == 1
        width = float(wire.get_attribute("stroke-width"))
        assert float(halo.get_attribute("stroke-width")) == width + 8
        assert float(halo.get_attribute("stroke-opacity")) == 0.3


def test_a_category_no_library_can_fill_is_not_listed(tmp_path: Path) -> None:
    """An AWS page offering "Energy & Power 0" is a row that can only ever
    say no. One the library selection merely leaves empty stays, so the list
    does not shift as libraries are switched on and off."""
    with _editor(tmp_path) as (page, _):
        shown = page.evaluate("""() => [...document.querySelectorAll('details[data-category-id]')]
          .map(d => [d.dataset.categoryId, !d.hidden,
                     Number(d.querySelector('[data-category-count]').textContent)])""")
    listed = {cid: count for cid, visible, count in shown if visible}
    hidden = {cid for cid, visible, _ in shown if not visible}
    assert "energy" in hidden and "facilities" in hidden, hidden
    assert "networking" in listed and listed["networking"] > 0
    assert all(count > 0 for count in listed.values()), listed


def test_a_caption_beside_a_vertical_wire_starts_beside_it(tmp_path: Path) -> None:
    """A caption on a vertical run is set beside the wire and read from it,
    not centred on a point off to one side -- the way the picture sets it."""
    sync_api = pytest.importorskip("playwright.sync_api")
    with Diagram(
        "Stacked",
        "Two cards, one above the other.",
        slug="stacked-caption",
        providers=("aws",),
        display="card",
    ) as diagram:
        with aws.VPC("vpc").column():
            web = compute.EC2("Web", "tier")
            sql = databases.RDS("SQL", "primary")
        web >> Edge("TDS") >> sql
    source = tmp_path / "stacked.html"
    source.write_text(render_project_html(diagram.to_project()), encoding="utf-8")
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1200, "height": 900})
            page.goto(f"{source.resolve().as_uri()}?fresh={tmp_path.name}")
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            placed = page.evaluate("""() => {
              const label = document.querySelector('[data-edge-label]');
              const wire = document.querySelector('[data-graph-edge]');
              const xs = (wire.getAttribute('d').match(/-?[\\d.]+(?=,)/g) || []).map(Number);
              return {anchor: label.querySelector('text').getAttribute('text-anchor'),
                      x: Number(label.dataset.labelX), wire: xs};
            }""")
        finally:
            browser.close()
    assert placed["anchor"] == "start", placed
    # just right of the wire -- 10 px, and a nudge clear of the cards -- and
    # reading away from it, rather than centred on a point off to one side
    assert any(0 < placed["x"] - x <= 16 for x in placed["wire"]), placed


def test_a_crowded_caption_tries_closer_to_the_ports_before_drifting(tmp_path: Path) -> None:
    """Between two cards with other wires about, the first spot on a wire
    can be free but nudged: it used to settle there, a few pixels off its
    wire. It now tries every point along the wire with less port room first,
    and a caption found that way sits exactly beside its own run."""
    sync_api = pytest.importorskip("playwright.sync_api")
    from infragram.nodes.azure import (
        compute as az_compute,
        databases as az_databases,
        networking as az_networking,
        storage as az_storage,
    )

    with Diagram(
        "Crowded", "Captions among several wires.", slug="crowded-captions", providers=("azure",)
    ) as diagram:
        lb = az_networking.LoadBalancers("Balancer", "entry")
        vm = az_compute.VirtualMachine("Web", "app tier")
        fn = az_compute.FunctionApps("Jobs", "workers")
        sql = az_databases.SQLDatabase("SQL", "primary")
        blob = az_storage.StorageAccounts("Blobs", "assets")
        lb >> Edge("HTTPS") >> vm
        vm >> Edge("reads", dashed=True) >> sql
        vm >> Edge("writes") >> sql
        fn >> Edge("metrics", dotted=True) >> blob
        vm >> Edge("sync", both=True) >> fn
        lb >> Edge(arrow="open") >> fn
        fn >> Edge("log", arrow="circle") >> sql
        blob >> Edge("replica", arrow="diamond", corners="sharp") >> sql
    source = tmp_path / "crowded.html"
    source.write_text(render_project_html(diagram.to_project()), encoding="utf-8")
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            page.goto(f"{source.resolve().as_uri()}?fresh={tmp_path.name}")
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            placed = page.evaluate(r"""() => {
              const state = window.infragramEditor.getState();
              const edge = state.edges.find(e => e.label === 'log');
              const label = document.querySelector(`[data-edge-label="${edge.id}"]`);
              const d = document.querySelector(`[data-graph-edge][data-edge-id="${edge.id}"]`).getAttribute('d');
              const points = [...d.matchAll(/(-?[\d.]+),(-?[\d.]+)/g)].map(m => [Number(m[1]), Number(m[2])]);
              return {x: Number(label.dataset.labelX), y: Number(label.dataset.labelY), points};
            }""")
        finally:
            browser.close()
    # beside a run of its own wire: the standard 12 px above a level one, or
    # right of an upright one within the 8 px a caption may be nudged (a run
    # another wire shares is left to a stretch this one runs alone)
    pairs = list(zip(placed["points"], placed["points"][1:], strict=False))
    level = [(a, b) for a, b in pairs if abs(a[1] - b[1]) < 0.01]
    upright = [(a, b) for a, b in pairs if abs(a[0] - b[0]) < 0.01]
    assert any(
        abs(placed["y"] - (a[1] - 12)) < 0.01 and min(a[0], b[0]) <= placed["x"] <= max(a[0], b[0])
        for a, b in level
    ) or any(
        10 <= placed["x"] - a[0] <= 18 and min(a[1], b[1]) <= placed["y"] <= max(a[1], b[1]) + 12
        for a, b in upright
    ), placed


def test_a_frame_dropped_from_a_gallery_joins_its_librarys_layer(tmp_path: Path) -> None:
    """The editor credited a dropped frame to a library by spotting it in the
    frame's id: "custom-boundary-aws-cloud" said AWS, "custom-boundary-region"
    -- the AWS Region frame -- said nothing, and a frame from eight of the
    libraries never did. Its gallery (frameGroup) names the library for all."""
    from infragram.projects import CloudProject

    template = (
        Path(__file__).parents[2]
        / "plugin"
        / "skills"
        / "infragram-architect"
        / "assets"
        / "templates"
        / "cloud"
        / "hybrid-bgp-edge.infragram.json"
    )
    sync_api = pytest.importorskip("playwright.sync_api")
    source = tmp_path / "gallery-layer.html"
    source.write_text(render_project_html(CloudProject.load(template)), encoding="utf-8")
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(f"{source.resolve().as_uri()}?fresh={tmp_path.name}")
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            dropped = page.evaluate("""() => {
              const editor = window.infragramEditor;
              const region = editor.getLibraryCatalog().components
                .find(component => component.serviceId === 'custom-boundary-region');
              editor.addBoundary(region, {x: 400, y: 900});
              const state = editor.getState();
              const frame = state.boundaries[state.boundaries.length - 1];
              return {group: region.frameGroup, id: region.serviceId, provider: frame.componentProvider,
                      layer: frame.layerId, project: state.provider};
            }""")
        finally:
            browser.close()
    assert dropped["group"] == "aws" and "aws" not in dropped["id"].split("-")
    assert dropped["project"] == "onprem"
    assert dropped["provider"] == "aws"
    assert dropped["layer"] == "provider:aws"


def test_dark_artwork_and_connector_labels_read_on_a_dark_canvas(tmp_path: Path) -> None:
    """Dark artwork -- the built-in line icons, a black vendor mark -- all but
    vanished on the dark themes, and connector labels sat in a dim grey. On a
    dark canvas such an icon is drawn light through one filter, colourful
    artwork is left as drawn, and a label takes the titles' white; the light
    theme draws exactly what it drew."""
    from infragram.projects import CloudProject

    template = (
        Path(__file__).parents[2]
        / "plugin"
        / "skills"
        / "infragram-architect"
        / "assets"
        / "templates"
        / "cloud"
        / "hybrid-bgp-edge.infragram.json"
    )
    sync_api = pytest.importorskip("playwright.sync_api")
    source = tmp_path / "dark-ink.html"
    source.write_text(render_project_html(CloudProject.load(template)), encoding="utf-8")
    read = """() => {
      const body = getComputedStyle(document.body);
      const names = selector => [...document.querySelectorAll('[data-graph-node]')]
        .filter(node => node.querySelector(selector))
        .map(node => node.querySelector('text')?.textContent.trim()).sort();
      return {
        filtered: names('image[filter]'),
        plain: names('image:not([filter])'),
        frame: (() => {
          const aws = [...document.querySelectorAll('[data-graph-boundary]')]
            .find(node => node.textContent.includes('AWS Cloud'));
          return aws ? aws.querySelector('[data-boundary-surface]').getAttribute('stroke') : '';
        })(),
        label: document.querySelector('[data-edge-label] text').getAttribute('fill'),
        text: body.getPropertyValue('--text-canvas').trim(),
        secondary: body.getPropertyValue('--text-secondary').trim(),
        filter: Boolean(document.querySelector('svg[data-infragram-diagram] defs #infragram-ink-on-dark')),
      };
    }"""
    seen = {}
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            for theme in ("dark", "darker", "light"):
                page = browser.new_page(viewport={"width": 1440, "height": 900})
                page.goto(f"{source.resolve().as_uri()}?fresh={theme}{tmp_path.name}&theme={theme}")
                page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
                seen[theme] = page.evaluate(read)
                if theme == "dark":
                    exported = page.evaluate("() => window.infragramEditor.exportSvg()")
                    assert 'filter="url(#infragram-ink-on-dark)"' in exported
                    assert 'id="infragram-ink-on-dark"' in exported
                page.close()
        finally:
            browser.close()
    dark_ink = ["Branch router", "Internet", "Perimeter firewall"]  # the PE routers are Cisco blue
    for theme in ("dark", "darker"):
        assert seen[theme]["filtered"] == dark_ink, seen[theme]
        # the blue Cisco icons and AWS's purple read as their vendors drew them
        assert (
            "Edge router R1" in seen[theme]["plain"] and "Transit Gateway" in seen[theme]["plain"]
        )
        assert seen[theme]["label"].lower() == seen[theme]["text"].lower()
    assert seen["light"]["filtered"] == []
    # the canvas text colour on the light canvas too: grey read as dim
    assert seen["light"]["label"].lower() == seen["light"]["text"].lower()
    # A library colour the dark ground would swallow is lifted, and it is the
    # value the document carries, which is what the picture draws
    # (tests/unit/test_dark_frames.py).
    from infragram.builders.architecture import load_style, load_theme
    from infragram.builders.frame_style import frame_paint
    from infragram.exports.palette import dark as dark_theme

    lifted = frame_paint(load_style("aws").cluster, dark_theme(load_theme("aws")), "cloud").stroke
    plain = frame_paint(load_style("aws").cluster, load_theme("aws"), "cloud").stroke
    assert seen["light"]["frame"].lower() == plain.lower()
    for theme in ("dark", "darker"):
        assert seen[theme]["frame"].lower() == lifted.lower(), seen[theme]["frame"]


def test_a_dark_picture_paints_what_the_dark_canvas_paints(tmp_path: Path) -> None:
    """The picture is drawn from the canvas's own colours, so every part a
    reader sees has to match: the ground, a card's face, its title, its
    detail line, a connector.

    The detail line is why this test exists. The renderer painted it from
    ``muted``, which the dark palette maps to the wire colour because a wire
    is painted from it too, so the picture set it at 3.9:1 on a card where
    the canvas sets it at 8.2:1. One palette entry cannot do both jobs on a
    dark ground, and no test compared the two renderers part by part.
    """
    import re as _re

    from infragram.exports import render_project_svg
    from infragram.projects import CloudProject

    template = (
        Path(__file__).parents[2]
        / "plugin"
        / "skills"
        / "infragram-architect"
        / "assets"
        / "templates"
        / "cloud"
        / "hybrid-bgp-edge.infragram.json"
    )
    project = CloudProject.load(template)
    sync_api = pytest.importorskip("playwright.sync_api")
    source = tmp_path / "dark-agreement.html"
    source.write_text(render_project_html(project), encoding="utf-8")
    card = "PE router A"
    detail = "provider edge"

    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(f"{source.resolve().as_uri()}?fresh={tmp_path.name}&theme=dark")
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            canvas = page.evaluate(
                """(name) => {
                  const node = [...document.querySelectorAll('[data-graph-node]')]
                    .find(item => item.textContent.includes(name));
                  const texts = [...node.querySelectorAll('text')];
                  return {
                    ground: getComputedStyle(document.body).getPropertyValue('--canvas-bg').trim(),
                    face: node.querySelector('[data-node-surface]').getAttribute('fill'),
                    title: texts[0].getAttribute('fill'),
                    detail: texts[1].getAttribute('fill'),
                    wire: document.querySelector('[data-graph-edge]').getAttribute('stroke'),
                  };
                }""",
                card,
            )
        finally:
            browser.close()

    svg = render_project_svg(project, background="paper", theme="dark")
    title = _re.search(rf'<text[^>]*fill="([^"]+)"[^>]*>{card}</text>', svg)
    line = _re.search(rf'<text[^>]*fill="([^"]+)"[^>]*>{detail}</text>', svg)
    ground = _re.search(r'<rect data-export-background=""[^>]*fill="([^"]+)"', svg)
    # a connector is the path that wears an arrowhead
    wire = _re.search(r'<path[^>]*stroke="([^"]+)"[^>]*marker-end="[^"]*"', svg)
    assert title and line and ground and wire, "the picture draws all of them"
    picture = {
        "title": title.group(1),
        "detail": line.group(1),
        "ground": ground.group(1),
        "wire": wire.group(1),
    }
    for part in ("title", "detail", "ground", "wire"):
        assert picture[part].lower() == canvas[part].lower(), (
            f"{part}: picture {picture[part]}, canvas {canvas[part]}"
        )


@pytest.mark.parametrize("theme", ["light", "dark", "darker"])
def test_a_disabled_control_is_dimmed_not_erased(tmp_path: Path, theme: str) -> None:
    """Undo and redo open disabled, and are the first controls anyone sees.

    ``--md-disabled-content`` is a colour-mix of the theme's on-surface. A
    custom property that reads another resolves where it is declared, so
    declared on ``:root`` -- the dark theme's block -- it carried the dark
    theme's ink into every other theme: on the light theme a disabled
    control was a pale grey on a pale surface, 1.08:1, which reads as
    missing rather than as disabled. Its ink has to sit on the same side of
    the surface as the theme's own text does.
    """
    with _editor(tmp_path, theme=theme) as (page, _):
        seen = page.evaluate(
            """() => {
              const undo = document.querySelector('[data-editor-action="undo"]');
              const body = getComputedStyle(document.body);
              const read = name => body.getPropertyValue(name).trim();
              return {
                disabled: undo.disabled,
                ink: getComputedStyle(undo).color,
                surface: read('--md-sys-color-surface'),
                text: read('--md-sys-color-on-surface'),
              };
            }"""
        )
    assert seen["disabled"], "undo opens with nothing to undo"
    # the ink is translucent: what a reader sees is it over this surface
    ground = _channels(seen["surface"])
    ink = _over(_channels(seen["ink"]), ground)
    ratio = _contrast(ink, ground)
    # Material dims a disabled control to 38% of the theme's own ink, which
    # is about 2.3:1 here; the stranded token gave 1.08:1, a control drawn
    # in the surface it sits on.
    assert ratio >= 1.8, f"{theme}: disabled {seen['ink']} on {seen['surface']} is {ratio:.2f}:1"


def _channels(colour: str) -> tuple[float, float, float, float]:
    """A computed colour as (r, g, b, a) in 0..1.

    Playwright gives ``color(srgb r g b / a)`` for a colour-mix, ``rgb()``
    for a plain colour, and a custom property's own text (often a hex) when
    it is read off the element.
    """
    import re as _re

    value = colour.strip()
    if value.startswith("#"):
        digits = value.lstrip("#")
        if len(digits) == 3:
            digits = "".join(channel * 2 for channel in digits)
        return (*(int(digits[index : index + 2], 16) / 255 for index in (0, 2, 4)), 1.0)
    numbers = [float(number) for number in _re.findall(r"[-\d.]+", value)]
    alpha = numbers[3] if len(numbers) > 3 else 1.0
    if value.startswith("color(srgb"):
        return (numbers[0], numbers[1], numbers[2], alpha)
    return (numbers[0] / 255, numbers[1] / 255, numbers[2] / 255, alpha)


def _over(
    front: tuple[float, float, float, float], back: tuple[float, float, float, float]
) -> tuple[float, float, float, float]:
    return (*(front[index] * front[3] + back[index] * (1 - front[3]) for index in range(3)), 1.0)


def _contrast(first: tuple[float, ...], second: tuple[float, ...]) -> float:
    def luminance(colour: tuple[float, ...]) -> float:
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in colour[:3]]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    one, two = luminance(first), luminance(second)
    return (max(one, two) + 0.05) / (min(one, two) + 0.05)


def test_a_page_opened_dark_starts_and_lifts_dark_ink_artwork(tmp_path: Path) -> None:
    """Opening dark measures each icon's ink. Every redraw while measurements
    were still out queued one more redraw per icon, so a page that opened dark
    on many dark-ink icons redrew without end and never started."""
    sync_api = pytest.importorskip("playwright.sync_api")
    from infragram.nodes import infragram as shared

    kinds = [
        shared.compute.BladeChassis,
        shared.compute.ConsoleServer,
        shared.compute.Cooling,
        shared.compute.DesktopClient,
        shared.compute.FailoverPair,
        shared.compute.FireSuppression,
        shared.compute.GPUServer,
        shared.compute.Generator,
        shared.compute.HPCNode,
        shared.compute.HaCluster,
        shared.compute.KVMConsole,
        shared.compute.Mainframe,
        shared.networking.AccessSwitch,
        shared.identity.Administrator,
    ]
    with Diagram("Dark ink", "Monochrome artwork.", slug="dark-ink", display="icon") as diagram:
        nodes = [kind(f"Item {index}") for index, kind in enumerate(kinds)]
        for source_node, target_node in zip(nodes, nodes[1:], strict=False):
            source_node >> target_node
    source = tmp_path / "dark-ink.html"
    source.write_text(render_project_html(diagram.to_project()), encoding="utf-8")
    lifted = "document.querySelectorAll('[data-graph-node] image[filter]').length"
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(f"{source.resolve().as_uri()}?fresh=dark-ink&theme=dark")
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            page.wait_for_function(f"{lifted} > 0", timeout=render_timeout_ms())
            # the same artwork beside its row in the inventory, lifted alike
            page.locator("[data-inventory-toggle]").click()
            page.wait_for_function(
                "document.querySelectorAll('img.resource-icon[data-ink-dark]').length > 0",
                timeout=render_timeout_ms(),
            )
            filters = page.evaluate(
                "[...document.querySelectorAll('img.resource-icon[data-ink-dark]')]"
                ".map(image => getComputedStyle(image).filter)"
            )
            assert set(filters) == {"invert(1) hue-rotate(180deg)"}, filters
        finally:
            browser.close()
