"""Legend display is independent of downloads; every picture uses the same key."""

from __future__ import annotations

import base64
import io
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from infragram.exports import render_project_html, render_timeout_ms
from infragram.projects import CloudProject

pytestmark = pytest.mark.skipif(
    os.environ.get("INFRAGRAM_RUN_BROWSER_TESTS") != "1", reason="opt-in browser tests"
)
TEMPLATES = Path(__file__).parents[2] / "plugin/skills/infragram-architect/assets/templates/cloud"
SVG = "{http://www.w3.org/2000/svg}"


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_legend_display_exports_and_saved_page(tmp_path: Path, theme: str) -> None:
    sync = pytest.importorskip("playwright.sync_api")
    source = tmp_path / "legend.html"
    source.write_text(
        render_project_html(
            CloudProject.load(TEMPLATES / "digitalocean-kubernetes-cluster.infragram.json"),
            libraries="project",
        ),
        encoding="utf-8",
    )
    with sync.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"{source.as_uri()}?theme={theme}")
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            legend = page.locator("[data-diagram-legend]")
            assert not legend.is_visible()
            page.get_by_role("switch", name="Show legend", exact=True).click()
            assert legend.is_visible()
            assert "Solid connector" in legend.inner_text()
            assert "Boundary / frame" in legend.inner_text()
            assert (
                page.evaluate("window.infragramEditor.exportSvg().includes('data-legend-strip')")
                is False
            )
            page.get_by_role("switch", name="Legend in exports", exact=True).click()
            page.get_by_role("switch", name="Show legend", exact=True).click()
            assert not legend.is_visible()
            enabled = page.evaluate("window.infragramEditor.exportSvg()")
            picture = ET.fromstring(enabled)
            ground = picture.find(f"{SVG}rect[@data-export-background]")
            assert ground is not None
            assert ground.get("fill") == page.evaluate(
                "getComputedStyle(document.querySelector('[data-infragram-diagram]'))"
                ".getPropertyValue('--diagram-surface').trim()"
            )
            assert any(
                "@font-face" in (element.text or "") for element in picture.iter(f"{SVG}style")
            )
            transparent = ET.fromstring(
                page.evaluate("window.infragramEditor.exportSvg({background:'transparent'})")
            )
            assert transparent.find(f"{SVG}rect[@data-export-background]") is None
            strip = next(
                element for element in picture.iter() if "data-legend-strip" in element.attrib
            )
            panel = strip.find(f"{SVG}rect")
            assert panel is not None
            world = [float(value) for value in picture.get("viewBox").split()]
            assert float(panel.get("y")) + float(panel.get("height")) <= world[1] + world[3]
            assert float(panel.get("x")) + float(panel.get("width")) <= world[0] + world[2]
            labels = [element.text for element in strip.iter(f"{SVG}text")]
            assert "Legend" in labels
            assert not ET.fromstring(
                page.evaluate("window.infragramEditor.exportSvg({includeLegend:false})")
            ).findall(f".//{SVG}g[@data-legend-strip]")
            drawio = ET.fromstring(page.evaluate("window.infragramEditor.exportDrawio()"))
            assert drawio.find(".//mxCell[@id='infragram:legend']") is not None
            assert drawio.find(".//mxCell[@id='infragram:legend:label:0']") is not None
            samples = drawio.findall(".//mxCell[@parent='infragram:legend'][@edge='1']")
            assert samples and all(
                sample.find("mxGeometry/mxPoint[@as='sourcePoint']") is not None
                and sample.find("mxGeometry/mxPoint[@as='targetPoint']") is not None
                for sample in samples
            )
            assert (
                ET.fromstring(
                    page.evaluate("window.infragramEditor.exportDrawio({includeLegend:false})")
                ).find(".//mxCell[@id='infragram:legend']")
                is None
            )
            # PNG consumes the same SVG option; inspect actual encoded images.
            pngs = page.evaluate("""async () => {
              const read = blob => new Promise(resolve => { const reader = new FileReader();
                reader.onload = () => resolve(reader.result.split(',')[1]); reader.readAsDataURL(blob); });
              return [await read(await window.infragramEditor.exportPng({includeLegend:false})),
                await read(await window.infragramEditor.exportPng({includeLegend:true}))];
            }""")
            from PIL import Image

            images = [Image.open(io.BytesIO(base64.b64decode(data))) for data in pngs]
            assert all(image.width > 0 and image.height > 0 for image in images)
            assert images[0].tobytes() != images[1].tobytes()
            saved = tmp_path / "saved-legend.html"
            saved.write_text(page.evaluate("window.infragramEditor.exportHtml()"), encoding="utf-8")
            page.goto(saved.as_uri())
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            assert not page.locator("[data-diagram-legend]").is_visible()
            assert (
                page.get_by_role("switch", name="Legend in exports", exact=True).get_attribute(
                    "aria-checked"
                )
                == "true"
            )
            page.locator("[data-download-menu] > summary").click()
            export_choice = page.get_by_role(
                "checkbox", name="Include legend in PNG, SVG & draw.io"
            )
            assert export_choice.is_checked()
            export_choice.uncheck()
            assert (
                page.evaluate("window.infragramEditor.exportSvg().includes('data-legend-strip')")
                is False
            )
            page.locator("[data-download-menu] > summary").click()
            page.set_viewport_size({"width": 390, "height": 844})
            page.get_by_role("switch", name="Show legend", exact=True).click()
            assert page.locator("[data-diagram-legend]").is_visible()
            geometry = page.evaluate("""() => {
              const canvas = document.querySelector('.canvas-viewport').getBoundingClientRect();
              const key = document.querySelector('[data-diagram-legend]').getBoundingClientRect();
              return {canvasHeight:canvas.height, clear:key.top >= canvas.bottom - 1,
                fits:key.right <= innerWidth};
            }""")
            assert geometry["canvasHeight"] > 40 and geometry["clear"] and geometry["fits"], (
                geometry
            )
            assert not errors, errors
        finally:
            browser.close()


def test_undo_keeps_export_preferences_and_caption_exports(tmp_path: Path) -> None:
    sync = pytest.importorskip("playwright.sync_api")
    project = CloudProject.load(TEMPLATES / "digitalocean-kubernetes-cluster.infragram.json")
    source = tmp_path / "preferences.html"
    source.write_text(render_project_html(project), encoding="utf-8")
    with sync.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(source.as_uri())
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            before = page.evaluate("window.infragramEditor.getState().edges[0].label")
            page.evaluate("""() => {
              const api = window.infragramEditor;
              api.setEdgeLabel(api.getState().edges[0].id, 'Changed caption');
            }""")
            page.get_by_role("switch", name="Legend in exports", exact=True).click()
            page.locator('[data-title-placement="caption"]').click()
            page.locator("[data-download-menu] > summary").click()
            page.get_by_role("button", name="4× Maximum", exact=True).click()
            page.keyboard.press("Escape")
            page.get_by_role("button", name="Undo", exact=True).click()
            state = page.evaluate("window.infragramEditor.getState()")
            assert state["edges"][0]["label"] == before
            assert state["canvas"]["pngScale"] == 4
            assert state["canvas"]["exportLegend"] is True
            assert state["canvas"]["titlePlacement"] == "caption"
            svg = ET.fromstring(page.evaluate("window.infragramEditor.exportSvg()"))
            caption = svg.find(f".//{SVG}g[@data-export-title]")
            assert caption is not None
            assert project.title == " ".join(caption.itertext())
            strip = svg.find(f".//{SVG}g[@data-legend-strip]/{SVG}rect")
            assert float(strip.get("y")) > max(
                float(line.get("y")) for line in caption.iter(f"{SVG}text")
            )
            drawio_text = page.evaluate("window.infragramEditor.exportDrawio()")
            drawio = ET.fromstring(drawio_text)
            assert drawio.find(".//mxCell[@infragram_role='caption']").get("value")
            from infragram.convert import read_diagrams

            drawing = tmp_path / "caption.drawio"
            drawing.write_text(drawio_text, encoding="utf-8")
            sketch = read_diagrams(drawing)[0]
            assert len(sketch.shapes) == len(state["nodes"]) + len(state["boundaries"])
            assert f"Title: {project.title}" in sketch.notes
            page.locator('[data-title-placement="hidden"]').click()
            assert "data-export-title" not in page.evaluate("window.infragramEditor.exportSvg()")
            assert "infragram:title" not in page.evaluate("window.infragramEditor.exportDrawio()")
        finally:
            browser.close()


def test_authored_legend_is_preserved_and_can_be_omitted(tmp_path: Path) -> None:
    sync = pytest.importorskip("playwright.sync_api")
    project = CloudProject.load(TEMPLATES / "aws-site-to-site-vpn.infragram.json")
    source = tmp_path / "authored.html"
    source.write_text(render_project_html(project, libraries="project"), encoding="utf-8")
    with sync.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(source.as_uri())
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            exported = page.evaluate("window.infragramEditor.exportSvg()")
            root = ET.fromstring(exported)
            text = " ".join(root.itertext())
            for _kind, label in project.presentation.legend:
                assert label in text
            assert len(root.findall(f".//{SVG}g[@data-legend-strip]")) == 1
            omitted = ET.fromstring(
                page.evaluate("window.infragramEditor.exportSvg({includeLegend:false})")
            )
            assert not omitted.findall(f".//{SVG}g[@data-legend-strip]")
        finally:
            browser.close()
