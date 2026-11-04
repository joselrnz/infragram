"""Crossing controls, saves, static fallback, transparent images and drag updates."""

from __future__ import annotations

import base64
import os
import re
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from infragram.exports import render_project_html, render_project_svg, render_timeout_ms
from infragram.paths import skill_assets
from infragram.projects import CloudProject

pytestmark = pytest.mark.skipif(
    os.environ.get("INFRAGRAM_RUN_BROWSER_TESTS") != "1",
    reason="set INFRAGRAM_RUN_BROWSER_TESTS=1 to run Chromium editor checks",
)


def crossing_project(display: str = "card", crossings: str = "plain") -> CloudProject:
    nodes = []
    for name, x, y, target, ports, kind in [
        ("app", 100, 350, "firewall", ("right", "left"), "solid"),
        ("firewall", 900, 350, None, (), "solid"),
        ("dns", 500, 80, "resolver", ("bottom", "top"), "dotted"),
        ("resolver", 500, 700, None, (), "dotted"),
    ]:
        attributes = {"editor_x": x, "editor_y": y, "editor_display_mode": display}
        if target:
            attributes["editor_edge_styles"] = {
                target: {
                    "source_port": ports[0],
                    "target_port": ports[1],
                }
            }
        nodes.append(
            {
                "id": name,
                "name": name.title(),
                "type": "service",
                "attributes": attributes,
                "connections": [{"target": target, "kind": kind}] if target else [],
            }
        )
    return CloudProject.model_validate(
        {
            "slug": "crossing-bridges",
            "title": "Crossing bridges",
            "description": "Independent paths.",
            "kind": "single-cloud",
            "providers": [{"id": "azure"}],
            "presentation": {"size": "fit", "display": display, "crossings": crossings},
            "topology": {
                "id": "root",
                "name": "Crossing bridges",
                "type": "group",
                "children": nodes,
            },
        }
    )


@pytest.mark.parametrize("display,theme", [("card", "light"), ("icon", "dark")])
def test_editor_downloads_png_and_editable_drawio(tmp_path: Path, display: str, theme: str) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    image = pytest.importorskip("PIL.Image")
    source = tmp_path / "downloads.html"
    source.write_text(render_project_html(crossing_project(display, "bridge")), encoding="utf-8")
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1500, "height": 1000})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(source.as_uri() + f"?fresh=downloads&theme={theme}")
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            page.evaluate("""() => {
                const api = window.infragramEditor;
                api.setEdgeLabel(api.getState().edges[0].id, 'DNS <&>');
                api.setEdgeLabelPlacement(api.getState().edges[0].id, {mode: 'manual', dx: 200, dy: -40});
            }""")
            svg = ET.fromstring(page.evaluate("window.infragramEditor.exportSvg()"))
            left, top, width, height = map(float, svg.attrib["viewBox"].split())
            expected_background = page.evaluate("""() => {
                const c = document.createElement('canvas').getContext('2d');
                c.fillStyle = getComputedStyle(document.body).getPropertyValue('--diagram-surface');
                c.fillRect(0,0,1,1); return [...c.getImageData(0,0,1,1).data];
            }""")
            crossing = svg.find(".//{*}mask/{*}circle")
            assert crossing is not None, "a safe crossing keeps its bridge in the exported picture"
            page.locator("[data-download-menu] > summary").click()
            with page.expect_download() as pending:
                page.locator("[data-download-png]").click()
            download = pending.value
            assert download.suggested_filename.endswith(".png")
            png = tmp_path / "diagram.png"
            download.save_as(png)
            with image.open(png) as picture:
                scale = 2  # Download defaults to sharp 2x PNGs.
                assert picture.size == (int(width * scale), int(height * scale))
                assert picture.convert("RGBA").getbbox(), "the exported drawing is not blank"
                pixels = picture.convert("RGBA")
                assert pixels.getpixel((0, 0)) == tuple(expected_background)
                cx = round((float(crossing.get("cx")) - left) * scale)
                cy = round((float(crossing.get("cy")) - top) * scale)
                crown = pixels.getpixel((cx, cy))
                gap = pixels.getpixel((cx, cy + 2 * scale))

                def contrast(pixel):
                    return sum(abs(a - b) for a, b in zip(pixel, expected_background, strict=True))

                assert contrast(crown) > contrast(gap), (
                    "the arc stays visible above its separated crossing"
                )
            page.locator("[data-download-menu] > summary").click()
            with page.expect_download() as pending:
                page.locator("[data-download-drawio]").click()
            drawing = tmp_path / "diagram.drawio"
            pending.value.save_as(drawing)
            root = ET.fromstring(drawing.read_text(encoding="utf-8"))
            assert root.find("diagram").get("infragram_crossings") == "bridge"
            cells = root.findall(".//mxCell[@edge='1']")
            assert len(cells) == 2
            assert all("jumpStyle=arc;jumpSize=16;" in cell.get("style") for cell in cells)
            assert {cell.get("source") for cell in cells} == {"node:app", "node:dns"}
            assert any(cell.get("value") == "DNS &lt;&amp;&gt;" for cell in cells)
            page.locator('[data-crossings="plain"]').click()
            plain = page.evaluate("window.infragramEditor.exportDrawio()")
            assert "jumpStyle=none;" in plain and "jumpStyle=arc;" not in plain
            page.evaluate("window.infragramEditor.expandCanvas(100000, 100000)")
            pixels = page.evaluate("""async () => {
                const bitmap = await createImageBitmap(await window.infragramEditor.exportPng());
                const size = [bitmap.width, bitmap.height]; bitmap.close(); return size;
            }""")
            assert max(pixels) <= 8192 and pixels[0] * pixels[1] <= 16 * 1024 * 1024
            assert not errors, errors
        finally:
            browser.close()


def test_storage_failure_offers_a_working_editor_download(tmp_path: Path) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    source = tmp_path / "storage.html"
    source.write_text(render_project_html(crossing_project()), encoding="utf-8")
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.add_init_script("""window.failSaves = true;
                const original = Storage.prototype.setItem;
                Storage.prototype.setItem = function(key, value) {
                    if (window.failSaves && key.startsWith('infragram-editor:')) {
                        throw new DOMException('Storage full', 'QuotaExceededError');
                    }
                    return original.call(this, key, value);
                };""")
            page.goto(source.as_uri() + "?fresh=storage-failure")
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            notice = page.locator("[data-save-notice]")
            assert notice.is_visible()
            page.evaluate(
                "window.infragramEditor.setEdgeLabel(window.infragramEditor.getState().edges[0].id, 'Edited DNS')"
            )
            with page.expect_download() as pending:
                page.locator("[data-save-download]").click()
            saved = tmp_path / "saved.html"
            pending.value.save_as(saved)
            html = saved.read_text(encoding="utf-8")
            assert "Edited DNS" in html
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert "data-save-notice" not in page.evaluate("window.infragramEditor.exportSvg()")
            page.goto(saved.as_uri() + "?fresh=downloaded")
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            assert page.evaluate("window.infragramEditor.getState().edges[0].label") == "Edited DNS"
            page.evaluate("window.failSaves = false; window.infragramEditor.setRouting(false)")
            assert not page.locator("[data-save-notice]").is_visible()
        finally:
            browser.close()


@pytest.mark.parametrize(
    "template,theme", [("aws-three-tier-web", "light"), ("azure-api", "dark"), ("blank", "light")]
)
def test_cloud_and_blank_exports_open_as_images_and_editable_models(
    tmp_path: Path, template: str, theme: str
) -> None:
    from infragram.convert import read_diagrams

    sync_api = pytest.importorskip("playwright.sync_api")
    image = pytest.importorskip("PIL.Image")
    if template == "blank":
        payload = crossing_project().model_dump()
        payload["topology"]["children"] = []
        project = CloudProject.model_validate(payload)
    else:
        project = CloudProject.load(
            skill_assets() / "templates" / "cloud" / f"{template}.infragram.json"
        )
    source = tmp_path / "cloud.html"
    source.write_text(render_project_html(project), encoding="utf-8")
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1500, "height": 1000})
            page.goto(source.as_uri() + f"?fresh=cloud-downloads&theme={theme}")
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            state = page.evaluate("window.infragramEditor.getState()")
            drawing = tmp_path / "cloud.drawio"
            drawing.write_text(
                page.evaluate("window.infragramEditor.exportDrawio()"), encoding="utf-8"
            )
            root = ET.fromstring(drawing.read_text(encoding="utf-8"))
            cells = {obj.get("id"): obj.find("mxCell") for obj in root.findall(".//object")}
            assert len(cells) == len(state["nodes"]) + len(state["boundaries"])
            filtered = page.evaluate("""() => [...document.querySelectorAll('[data-graph-node]')]
                .filter(node => node.querySelector('image[filter]')).map(node => node.dataset.nodeId)""")
            for cell in cells.values():
                parent = cell.get("parent")
                assert parent == "1" or parent in cells
            sketch = read_diagrams(drawing)[0]
            assert len(sketch.shapes) == len(cells)
            for node in state["nodes"]:
                style = cells[f"node:{node['id']}"].get("style")
                if node.get("iconUri"):
                    assert "image=data:" in style and ";base64," not in style
                if node["id"] in filtered:
                    encoded = style.split("image=data:image/svg+xml,", 1)[1].split(";", 1)[0]
                    assert b"infragram-ink-on-dark" in base64.b64decode(encoded)
            page.locator("[data-download-menu] > summary").click()
            with page.expect_download() as pending:
                page.locator("[data-download-png]").click()
            png = tmp_path / "cloud.png"
            pending.value.save_as(png)
            with image.open(png) as picture:
                assert picture.width > 0 and picture.height > 0
                if template != "blank":
                    assert picture.convert("RGB").getextrema()[0][0] < 200
            assert not page.locator("[data-save-notice]").is_visible()
        finally:
            browser.close()


@pytest.mark.parametrize("display", ["card", "icon"])
def test_crossing_option_survives_undo_save_and_static_export(tmp_path: Path, display: str) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    project = crossing_project(display)
    source = tmp_path / "crossing.html"
    source.write_text(render_project_html(project), encoding="utf-8")
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1500, "height": 1000})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(source.as_uri() + "?fresh=bridges")
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            plain = page.evaluate("() => window.infragramEditor.exportProject()")
            assert plain["presentation"]["crossings"] == "plain"
            page.locator('[data-crossings="bridge"]').click()
            assert page.locator('[data-graph-edge][data-crossing-count="1"]').count() == 1
            saved = page.evaluate("() => window.infragramEditor.exportProject()")
            assert saved["presentation"]["crossings"] == "bridge"
            assert saved["topology"] == plain["topology"]
            page.locator('[data-editor-action="undo"]').click()
            assert page.locator("[data-graph-edge][data-crossing-count]").count() == 0
            page.locator('[data-editor-action="redo"]').click()
            assert page.locator('[data-graph-edge][data-crossing-count="1"]').count() == 1
            picture = page.evaluate("() => window.infragramEditor.exportSvg()")
            html = page.evaluate("() => window.infragramEditor.exportHtml()")
            parsed = ET.fromstring(picture)
            assert len(parsed.findall(".//{*}mask")) == 1
            assert parsed.find('.//{*}path[@data-crossing-count="1"]') is not None
            assert len(parsed.findall(".//{*}path[@data-graph-edge]")) == 2
            assert parsed.find(".//{*}path[@stroke-dasharray]") is not None
            assert parsed.find(".//{*}path[@marker-end]") is not None
            # Moving the vertical wire also moves the other wire's bridge.
            old_x = page.locator("[data-crossing-mask] circle").get_attribute("cx")
            node_box = page.locator('[data-graph-node][data-node-id="dns"]').bounding_box()
            assert node_box
            x, y = node_box["x"] + node_box["width"] / 2, node_box["y"] + node_box["height"] / 2
            page.mouse.move(x, y)
            page.mouse.down()
            page.mouse.move(x + 70, y, steps=8)
            page.wait_for_function(
                "window.infragramEditor.getState().nodes.find(n=>n.id==='dns').x !== 500"
            )
            assert page.locator("[data-crossing-mask] circle").get_attribute("cx") != old_x
            page.mouse.up()
            html = page.evaluate("() => window.infragramEditor.exportHtml()")
            source.write_text(html, encoding="utf-8")
            page.goto(source.as_uri() + "?fresh=reopened")
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            assert page.locator('[data-crossings="bridge"]').get_attribute("aria-pressed") == "true"
            assert page.locator('[data-graph-edge][data-crossing-count="1"]').count() == 1
            page.locator("[data-theme-menu] > summary").click()
            page.locator('[data-theme-choice="dark"]').click()
            assert page.locator('[data-graph-edge][data-crossing-count="1"]').count() == 1
            page.locator('[data-crossings="plain"]').click()
            assert page.locator("[data-crossing-mask]").count() == 0
            assert page.locator("[data-graph-edge][mask]").count() == 0
            assert not errors, errors
        finally:
            browser.close()
    static = render_project_svg(CloudProject.model_validate(saved), background="transparent")
    assert 'data-crossing-count="1"' in static
    assert "A8,8" in static and "<mask" in static
    assert "data-crossing-count" not in render_project_svg(project)


def test_crossing_mask_is_transparent_in_real_png_export(tmp_path: Path) -> None:
    from infragram.exports import export_project

    image = pytest.importorskip("PIL.Image")
    result = export_project(
        crossing_project(crossings="bridge"),
        tmp_path,
        formats=("svg", "png"),
        background="transparent",
        scale=1,
    )
    svg = result.svg.read_text(encoding="utf-8")
    match = re.search(r'<mask[^>]*>.*?<circle cx="([\d.]+)" cy="([\d.]+)" r=', svg, re.S)
    assert match, svg[:300]
    x, y = map(float, match.groups())
    view = ET.fromstring(svg).attrib["viewBox"].split()
    left, top = map(float, view[:2])
    with image.open(result.png) as png:
        pixels = png.convert("RGBA")
        assert pixels.getpixel((round(x - left), round(y + 2 - top)))[3] < 30
        assert pixels.getpixel((round(x - left), round(y - top)))[3] > 150


@pytest.mark.parametrize("display", ["card", "icon"])
def test_long_notes_stay_outside_the_header_and_diagram(tmp_path: Path, display: str) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    project = crossing_project(display, "bridge")
    project.title = "A very long cloud network architecture title " * 12
    project.presentation.status = "REFERENCE EXAMPLE"
    project.presentation.notes = ("Explanation for companion documentation. " * 100,)
    project.presentation.drawn = "2026-10-03"
    source = tmp_path / "no-inline-notes.html"
    source.write_text(render_project_html(project), encoding="utf-8")
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(source.as_uri() + "?fresh=no-inline-notes")
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            for width in (390, 768, 1440):
                page.set_viewport_size({"width": width, "height": 900})
                page.wait_for_timeout(100)
                assert page.locator("[data-document-status],[data-status-block]").count() == 0
                assert (
                    project.presentation.status
                    not in page.locator("[data-editor-header]").inner_text()
                )
                bounds = page.evaluate("""() => {
                  const copy = document.querySelector('.document-copy').getBoundingClientRect();
                  const actions = document.querySelector('.document-actions').getBoundingClientRect();
                  const download = document.querySelector('[data-download-menu] > summary').getBoundingClientRect();
                  return {overlap:copy.right > actions.left, right:download.right,
                    overflow:document.documentElement.scrollWidth > innerWidth, width:innerWidth};
                }""")
                assert not bounds["overlap"] and not bounds["overflow"], bounds
                assert bounds["right"] <= bounds["width"], bounds
            saved = page.evaluate("() => window.infragramEditor.exportProject()")
            assert saved["presentation"]["notes"] == list(project.presentation.notes)
            svg = page.evaluate("() => window.infragramEditor.exportSvg()")
            assert "data-status-block" not in svg and "data-architecture-status" not in svg
            assert "REFERENCE EXAMPLE" not in svg
            assert "Explanation for companion documentation" not in svg
            assert 'data-crossing-count="1"' in svg
        finally:
            browser.close()
