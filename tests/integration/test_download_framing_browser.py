"""Downloaded pictures fit the drawing, regardless of zoom or empty canvas size."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from infragram.exports import render_project_html, render_timeout_ms
from infragram.projects import CloudProject

pytestmark = pytest.mark.skipif(
    os.environ.get("INFRAGRAM_RUN_BROWSER_TESTS") != "1", reason="opt-in browser tests"
)
TEMPLATE = (
    Path(__file__).parents[2]
    / "plugin/skills/infragram-architect/assets/templates/cloud/digitalocean-kubernetes-cluster.infragram.json"
)
SVG = "{http://www.w3.org/2000/svg}"


def _box(svg: str) -> tuple[float, ...]:
    return tuple(float(value) for value in ET.fromstring(svg).get("viewBox").split())


@pytest.mark.parametrize("theme", ["light", "dark"])
@pytest.mark.parametrize("display", ["card", "icon"])
def test_downloads_crop_content_and_apply_png_resolution(
    tmp_path: Path, theme: str, display: str
) -> None:
    sync = pytest.importorskip("playwright.sync_api")
    Image = pytest.importorskip("PIL.Image")
    source = tmp_path / "download-review.html"
    source.write_text(
        render_project_html(CloudProject.load(TEMPLATE), libraries="project"), encoding="utf-8"
    )
    with sync.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900}, accept_downloads=True)
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(f"{source.as_uri()}?theme={theme}&display={display}")
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            page.evaluate("mode => window.infragramEditor.setDisplayMode(mode)", display)
            page.evaluate("window.infragramEditor.whenSettled()")
            assert page.evaluate("window.infragramEditor.getState().canvas.displayMode") == display
            before = _box(page.evaluate("window.infragramEditor.exportSvg({includeLegend:false})"))
            # Reproduce the report: a small drawing inside a huge working canvas.
            page.evaluate("window.infragramEditor.expandCanvas(20000,16000)")
            page.evaluate("window.infragramEditor.whenSettled()")
            after = _box(page.evaluate("window.infragramEditor.exportSvg({includeLegend:false})"))
            assert after == before, (before, after)
            assert after[2] < 5000 and after[3] < 5000, after
            page.get_by_role("button", name="Zoom out", exact=True).click()
            assert (
                _box(page.evaluate("window.infragramEditor.exportSvg({includeLegend:false})"))
                == after
            )
            page.get_by_role("switch", name="Legend in exports", exact=True).click()
            with_legend = page.evaluate("window.infragramEditor.exportSvg()")
            key = ET.fromstring(with_legend).find(f".//{SVG}g[@data-legend-strip]")
            assert key is not None
            crop = _box(with_legend)
            panel = key.find(f"{SVG}rect")
            assert float(panel.get("y")) + float(panel.get("height")) <= crop[1] + crop[3] - 20
            menu = page.locator("[data-download-menu]")

            def download(control: str, name: str) -> Path:
                if menu.get_attribute("open") is None:
                    menu.locator("summary").click()
                with page.expect_download() as event:
                    menu.locator(control).click()
                target = tmp_path / name
                event.value.save_as(target)
                return target

            svg_file = download("[data-download-svg]", "review.svg")
            assert _box(svg_file.read_text(encoding="utf-8")) == crop
            # 2x is the default; explicitly choose 1x and 4x through the menu.
            sizes = {}
            for scale in (2, 1, 4):
                if menu.get_attribute("open") is None:
                    menu.locator("summary").click()
                choice = menu.locator(f'[data-png-scale-choice="{scale}"]')
                if scale == 2:
                    assert choice.get_attribute("aria-pressed") == "true"
                else:
                    choice.click()
                    assert choice.get_attribute("aria-pressed") == "true"
                assert menu.locator('[data-png-scale-choice][aria-pressed="true"]').count() == 1
                picture = download("[data-download-png]", f"review-{scale}x.png")
                image = Image.open(picture)
                sizes[scale] = image.size
                effective = min(
                    scale,
                    8192 / crop[2],
                    8192 / crop[3],
                    (16 * 1024 * 1024 / crop[2] / crop[3]) ** 0.5,
                )
                assert image.width == max(1, int(crop[2] * effective))
                assert image.height == max(1, int(crop[3] * effective))
                assert image.width * image.height <= 16 * 1024 * 1024
                assert max(image.size) <= 8192
                if effective < scale:
                    assert (
                        f"{image.width} × {image.height} px"
                        in page.locator("[data-snackbar]").text_content()
                    )
            assert sizes[2][0] > sizes[1][0] and sizes[4][0] >= sizes[2][0], sizes
            drawio_file = download("[data-download-drawio]", "review.drawio")
            drawio = ET.parse(drawio_file)
            model = drawio.find(".//mxGraphModel")
            assert float(model.get("dx")) < 5000 and float(model.get("dy")) < 5000
            assert drawio.find(".//mxCell[@id='infragram:legend']") is not None
            html_file = download("[data-download-html]", "review.html")
            page.goto(html_file.as_uri())
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            page.locator("[data-download-menu] > summary").click()
            assert (
                page.get_by_role("button", name="4× Maximum", exact=True).get_attribute(
                    "aria-pressed"
                )
                == "true"
            )
            assert not errors, errors
        finally:
            browser.close()


@pytest.mark.parametrize("saved_scale,expected", [(0, 2), (5, 2), ("3", 3), (2.5, 2)])
def test_saved_png_quality_is_normalised(
    tmp_path: Path, saved_scale: object, expected: int
) -> None:
    sync = pytest.importorskip("playwright.sync_api")
    source = tmp_path / "quality.html"
    source.write_text(render_project_html(CloudProject.load(TEMPLATE)), encoding="utf-8")
    with sync.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(source.as_uri())
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            page.evaluate(
                """scale => {
              const state = window.infragramEditor.getState(); state.canvas.pngScale = scale;
              const key = Object.keys(localStorage).find(key => {
                try { return JSON.parse(localStorage.getItem(key))?.schemaVersion === 3; }
                catch (_) { return false; }
              });
              if (!key) throw new Error('Saved editor state not found');
              localStorage.setItem(key, JSON.stringify(state));
            }""",
                saved_scale,
            )
            page.reload()
            page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
            assert page.evaluate("window.infragramEditor.getState().canvas.pngScale") == expected
            page.locator("[data-download-menu] > summary").click()
            assert (
                page.locator(f'[data-png-scale-choice="{expected}"]').get_attribute("aria-pressed")
                == "true"
            )
            assert page.locator("[data-png-quality-label]").inner_text() != "undefined"
        finally:
            browser.close()
