"""Rebuild README media from the selected mascot and the current editor.

Run with Python, Playwright Chromium and FFmpeg installed. Browser captures
show the actual editor; FFmpeg animates the existing mascot without redrawing it.
"""

from __future__ import annotations

import base64
import runpy
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "plugin" / "src"))

from playwright.sync_api import sync_playwright  # noqa: E402

from infragram.exports import render_project_html  # noqa: E402
from infragram.projects import CloudProject  # noqa: E402

IMAGES = ROOT / "docs" / "images"
MEDIA = ROOT / "docs" / "media"
MASCOT = ROOT / "plugin/src/infragram/editor/ui/assets/mascot.png"
# The demo draws a shipped template: four sources through an ETL platform
# into a warehouse, marts and five reporting tools, in nested VLAN frames,
# with captioned, dashed and dotted wires -- enough for the flow to tell.
DEMO_TEMPLATE = (
    ROOT
    / "plugin/skills/infragram-architect/assets/templates/cloud"
    / "enterprise-data-integration.infragram.json"
)
# The longer tour: the same features on four clouds' architectures, each
# an example a reader can open (plugin/examples).
TOUR_EXAMPLES = (
    "aws_three_tier",
    "aws_github_actions_oidc",
    "azure_aks_baseline",
    "gcp_streaming_analytics",
)
LIT = "document.querySelectorAll('[data-graph-edge][data-focus-edge=true]').length"


def brand_assets() -> None:
    """Export the selected mint engraving and sizes used by offline editors."""
    master = MASCOT.read_bytes()
    master_size = int.from_bytes(master[16:20], "big")
    uri = "data:image/png;base64," + base64.b64encode(master).decode("ascii")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page()
        for size in (master_size, 512, 128, 64, 32):
            page.set_viewport_size({"width": size, "height": size})
            page.set_content(
                "<style>html,body{margin:0;background:transparent}"
                "img{display:block;width:100vw;height:100vh;border-radius:22%}</style>"
                f'<img src="{uri}" alt="Infragram pangolin engraving">'
            )
            page.locator("img").evaluate("img => img.decode()")
            if size in (128, 64, 32):
                page.screenshot(
                    path=str(MASCOT.with_name(f"mascot-{size}.png")), omit_background=True
                )
            if size != 64:
                filename = (
                    "infragram-mascot.png"
                    if size == master_size
                    else "infragram-engineer-icon.png"
                    if size == 512
                    else f"infragram-mascot-{size}.png"
                )
                page.screenshot(path=str(IMAGES / filename), omit_background=True)
        browser.close()
    # Small WebP exports retain the engraving without inflating every offline page.
    # The favicon stays PNG for browser compatibility.
    for size in (128, 64):
        source = MASCOT.with_name(f"mascot-{size}.png")
        encode(
            "-i",
            str(source),
            "-c:v",
            "libwebp",
            "-quality",
            "90",
            "-compression_level",
            "6",
            str(source.with_suffix(".webp")),
        )
        source.unlink()
    brand_banner()


def brand_banner() -> None:
    """Set the engraved mascot beside a quiet, cream wordmark."""
    banner_uri = "data:image/png;base64," + base64.b64encode(
        (IMAGES / "infragram-engineer-icon.png").read_bytes()
    ).decode("ascii")
    nested = (
        '<image x="1130" y="65" width="665" height="665" '
        f'href="{banner_uri}" aria-label="Infragram\'s engraved pangolin on mint"/>'
    )
    banner = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1983" height="793"
      viewBox="0 0 1983 793" role="img" aria-labelledby="header-title">
      <title id="header-title">Infragram Architect — a pangolin drawing a diagram</title>
      <style>
        .banner-background {{ fill: #141B24; }}
        .wordmark {{ fill: #F2E7D3; }} .subtitle {{ fill: #C4C2BA; }}
      </style>
      <rect class="banner-background" width="1983" height="793" rx="36"/>
      {nested}
      <g font-family="Georgia, 'Times New Roman', serif">
        <text class="wordmark" x="115" y="367" font-size="154" letter-spacing="-5">Infragram</text>
        <text class="wordmark" x="122" y="437" font-size="40">Architect</text>
        <text class="subtitle" x="122" y="528" font-size="33">Picture it. Watch it take shape.</text>
      </g>
      <g font-family="Segoe UI, Arial, sans-serif">
        <text class="subtitle" x="122" y="673" font-size="23">Open-source diagramming</text>
      </g>
    </svg>"""
    (IMAGES / "infragram-engineer-header.svg").write_text(banner, encoding="utf-8", newline="\n")


def brand_archive() -> None:
    files = [
        IMAGES / "infragram-mascot.png",
        IMAGES / "infragram-engineer-icon.png",
        IMAGES / "infragram-mascot-128.png",
        IMAGES / "infragram-mascot-32.png",
        IMAGES / "infragram-engineer-header.svg",
        IMAGES / "infragram-engineer-header-light.png",
        IMAGES / "infragram-engineer-header-dark.png",
        IMAGES / "infragram-engineer.gif",
    ]
    with zipfile.ZipFile(MEDIA / "infragram-brand-kit.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for file in files:
            archive.write(file, file.name)
        archive.writestr(
            "README.txt",
            "Infragram's engraved pangolin architect on mint\n\n"
            "Default: mint #C9EFDF; cream #FFF8EB; blue #008AD8; ink #191E27.\n"
            "The selected mascot is raster artwork; the banner SVG embeds a PNG.\n"
            "Mint mascot tiles have transparent rounded corners; banners use dark charcoal.\n"
            "Full-resolution mascot and PNG exports: 512, 128, and 32 px.\n"
            "Offline editor uses small WebP header/welcome images and a PNG favicon.\n"
            "Source: plugin/src/infragram/editor/ui/assets/mascot.png\n"
            "Rebuild: python scripts/docs/regenerate-media.py\n",
        )


def encode(*args: str) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("Install FFmpeg and add it to PATH before regenerating media")
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *args], check=True)


def mascot_loop() -> None:
    encode(
        "-loop",
        "1",
        "-framerate",
        "12",
        "-i",
        str(IMAGES / "infragram-engineer-icon.png"),
        "-f",
        "lavfi",
        "-i",
        "color=c=black@0.0:s=360x360:r=12:d=4,format=rgba",
        "-filter_complex",
        "[0:v]scale=320:320:flags=lanczos,format=rgba,"
        "rotate='0.012*sin(2*PI*t/4)':ow=340:oh=340:c=none[mascot];"
        "[1:v][mascot]overlay=x=10:y='10+2*sin(2*PI*t/2)':format=auto:shortest=1,"
        "split[palin][gifin];[palin]palettegen=reserve_transparent=1:max_colors=128[pal];"
        "[gifin][pal]paletteuse=dither=none:diff_mode=rectangle:alpha_threshold=128",
        "-t",
        "4",
        "-loop",
        "0",
        str(IMAGES / "infragram-engineer.gif"),
    )


def demo_project() -> CloudProject:
    return CloudProject.load(DEMO_TEMPLATE)


def example_project(name: str) -> CloudProject:
    module = runpy.run_path(str(ROOT / "plugin" / "examples" / f"{name}.py"), run_name="tour")
    return module["diagram"].to_project()


def open_editor(page, source: Path) -> None:
    page.goto(source.as_uri())
    page.wait_for_function("window.infragramEditor && window.infragramEditor.getState")
    page.locator(".app-mascot").wait_for()
    page.evaluate("() => window.infragramEditor.whenSettled()")


def fold(page, open_panels: bool) -> None:
    # with both panels folded the fit zoom nearly doubles, so the captions
    # stay readable and the flow's dashes keep marching in the GIF
    for toggle in ("[data-sidebar-logo-trigger]", "[data-inspector-toggle]"):
        if (page.locator(toggle).get_attribute("aria-expanded") == "true") != open_panels:
            page.locator(toggle).click()
    page.wait_for_timeout(400)
    page.locator('[data-editor-action="zoom-fit"]').click()


def card(page, node_id: str):
    return page.locator(f'[data-graph-node][data-node-id="{node_id}"]')


def park(page) -> None:
    # the pointer rests on the header, where no hover card can open over the
    # drawing at any zoom
    page.mouse.move(1100, 20)


def shown(page, wires: int | None, hold: int = 1900) -> None:
    """Hold the flow on screen once it animates ``wires`` wires (any, for
    None), with the pointer parked."""
    park(page)
    page.wait_for_function(f"{LIT} === {wires}" if wires is not None else f"{LIT} > 0")
    page.wait_for_timeout(hold)


def flow_of(page, node_id: str, hold: int = 1900) -> None:
    """A click on a card: every wire it joins animates, the rest steps back."""
    wires = page.evaluate(
        "id => window.infragramEditor.getState().edges"
        ".filter(e => e.source === id || e.target === id).length",
        node_id,
    )
    card(page, node_id).click()
    shown(page, wires, hold)


def frame_label(page, frame_id: str) -> tuple[float, float]:
    box = page.locator(f'[data-graph-boundary][data-boundary-id="{frame_id}"]').bounding_box()
    assert box is not None, frame_id
    return box["x"] + 90, box["y"] + 9


def empty_point(page) -> tuple[float, float]:
    point = page.evaluate("""() => {
      const v = document.querySelector('.canvas-viewport').getBoundingClientRect();
      for (let y = v.bottom - 60; y > v.top + 20; y -= 12)
        for (let x = v.right - 60; x > v.left + 20; x -= 12) {
          const el = document.elementFromPoint(x, y);
          if (el && el.closest('[data-infragram-diagram]') && !el.closest(
            '[data-graph-node],[data-graph-boundary],[data-edge-group],[data-edge-label]'))
            return [x, y];
        }
      return null; }""")
    assert point, "no empty canvas"
    return point[0], point[1]


def context_action(page, at: tuple[float, float], action: str) -> None:
    page.mouse.click(*at, button="right")
    page.locator(f'[data-context-action="{action}"]').click()
    park(page)


def wheel_zoom(page, at: tuple[float, float], steps: int) -> None:
    # the wheel zooms about the pointer, as a reader would close in on a part
    page.mouse.move(*at)
    for _ in range(steps):
        page.mouse.wheel(0, -100)
        page.wait_for_timeout(180)
    park(page)


def set_theme(page, choice: str) -> None:
    page.locator("[data-theme-menu] > summary").click()
    page.locator(f'[data-theme-choice="{choice}"]').click()


def recording_context(browser, scratch: Path):
    return browser.new_context(
        viewport={"width": 1600, "height": 1000},
        record_video_dir=str(scratch),
        record_video_size={"width": 1600, "height": 1000},
    )


def record_demo(scratch: Path) -> tuple[Path, float]:
    source = scratch / "editor.html"
    source.write_text(render_project_html(demo_project()), encoding="utf-8", newline="\n")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = recording_context(browser, scratch)
        page = context.new_page()
        started = time.monotonic()
        open_editor(page, source)
        # the video starts on the drawing fitted to the canvas, not mid-fit
        page.locator('[data-editor-action="zoom-fit"]').click()
        page.wait_for_timeout(600)
        lead_in = time.monotonic() - started
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def pause(ms: int = 1700) -> None:
            page.wait_for_timeout(ms)

        pause()
        search = page.locator("[data-sidebar-search]")
        search.press_sequentially("database", delay=110)
        pause()
        search.fill("")

        # The flow, stage by stage, following the data: a click on a card
        # animates its wires in the traffic's direction and steps the rest
        # back; a click on a frame or a caption shows that frame's or wire's.
        fold(page, open_panels=False)
        pause()
        # a source (extract), the ETL hub (four feeds in; cleanse, load and
        # publish out), data quality (cleanse; the catalog's dotted lineage),
        # the warehouse, the marts (publish; dashed retention, ODBC, SPSS)
        # and Power BI (DirectQuery; the analysts over HTTPS)
        for node_id in ("erp", "powercenter", "dq", "warehouse", "marts", "powerbi"):
            flow_of(page, node_id)
        page.mouse.click(*frame_label(page, "apps"))  # the source systems' frame
        shown(page, 4)
        page.locator('[data-edge-label][data-edge-id="edge-9"]').click()  # DirectQuery
        shown(page, 1)
        # and the lens on Power BI: everything its reports depend on, from the
        # four sources through the ETL platform and the warehouse
        card(page, "powerbi").click(button="right")
        page.locator('[data-context-action="lens-dependents"]').click()
        shown(page, 7, hold=3800)
        page.keyboard.press("Escape")
        fold(page, open_panels=True)
        pause()

        hub = card(page, "powercenter")
        hub.dblclick()
        page.locator('[data-inspector-tab="text"]').click()
        detail = page.locator('[data-content-control="detail"]')
        detail.fill("ETL mappings · nightly")
        detail.dispatch_event("change")
        assert (
            page.evaluate(
                "window.infragramEditor.getState().nodes.find(n => n.id === 'powercenter').detail"
            )
            == "ETL mappings · nightly"
        )
        pause()
        box = card(page, "metadata").bounding_box()
        assert box is not None
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x + 80, y + 40, steps=25)
        page.mouse.up()
        pause()
        page.locator('[data-editor-action="tidy-layout"]').click()
        page.locator('[data-inspector-tab="diagram"]').click()
        pause()
        page.locator('[data-project-display="card"]').click()
        pause()
        set_theme(page, "dark")
        pause()
        set_theme(page, "light")
        page.locator('[data-project-display="icon"]').click()
        pause()
        page.locator("[data-download-menu] > summary").click()
        pause()
        page.locator("[data-download-menu] > summary").click()
        pause()
        assert not errors, errors
        video = page.video
        assert video is not None
        context.close()
        recording = Path(video.path())

        banner_page = browser.new_page(viewport={"width": 1983, "height": 793})
        for theme in ("light", "dark"):
            banner_page.emulate_media(color_scheme=theme)
            banner_page.goto((IMAGES / "infragram-engineer-header.svg").as_uri())
            banner_page.screenshot(
                path=str(IMAGES / f"infragram-engineer-header-{theme}.png"),
                omit_background=True,
            )
        browser.close()
    return recording, lead_in


def tour_aws_three_tier(page) -> None:
    """The users' request through WAF, the load balancer, the web tier and
    its database, secrets, assets and telemetry."""
    for node_id in ("users", "aws-waf", "application-load-balancer", "web-servers"):
        flow_of(page, node_id)
    page.locator('[data-edge-label][data-edge-id="edge-6"]').click()  # credentials
    shown(page, 1)
    context_action(page, empty_point(page), "lens-internet")
    shown(page, 6, hold=3400)  # what the internet reaches
    page.keyboard.press("Escape")
    context_action(page, frame_label(page, "private-subnets"), "frame-display-card")
    page.wait_for_timeout(2200)


def tour_aws_github_oidc(page) -> None:
    """The pipeline's numbered steps in order, the second flow (At runtime),
    what the running service depends on, and the deploy role's details."""
    for node_id in (
        "repository",
        "deploy-workflow",
        "runner",
        "container-image",
        "production-approval",
        "oidc-token",
        "deploy-role",
        "web-service",
    ):
        flow_of(page, node_id)
    page.locator('[data-edge-label][data-edge-id="edge-13"]').click()  # pulls, At runtime
    shown(page, 1)
    card(page, "web-service").click(button="right")
    page.locator('[data-context-action="lens-dependents"]').click()
    shown(page, None, hold=3400)
    page.keyboard.press("Escape")
    card(page, "deploy-role").click(button="right")
    page.locator('[data-context-action="details"]').click()
    page.wait_for_timeout(2600)
    page.keyboard.press("Escape")


def tour_azure_aks(page) -> None:
    """In the dark theme: the whole picture's internet reach, then closer in,
    ingress to the pods, their private endpoints and their egress."""
    set_theme(page, "dark")
    page.wait_for_timeout(1500)
    context_action(page, empty_point(page), "lens-internet")
    shown(page, None, hold=3400)
    page.keyboard.press("Escape")
    box = card(page, "user-node-pool").bounding_box()
    assert box is not None
    wheel_zoom(page, (box["x"] + box["width"] / 2, box["y"] + box["height"]), 3)
    page.wait_for_timeout(900)
    for node_id in (
        "application-gateway",
        "internal-load-balancer",
        "user-node-pool",
        "private-endpoints",
        "azure-firewall",
    ):
        flow_of(page, node_id)
    page.mouse.click(*frame_label(page, "supply-chain-and-secrets"))
    shown(page, None)
    page.keyboard.press("Escape")
    set_theme(page, "light")


def tour_gcp_streaming(page) -> None:
    """The edge, serving, the stream into BigQuery, Looker's lineage back to
    the users, and the export menu."""
    for node_id in (
        "users",
        "global-load-balancer",
        "api-service",
        "pub-sub",
        "dataflow",
        "bigquery",
    ):
        flow_of(page, node_id)
    page.mouse.click(*frame_label(page, "data"))
    shown(page, None)
    card(page, "looker").click(button="right")
    page.locator('[data-context-action="lens-dependents"]').click()
    shown(page, None, hold=3400)
    page.keyboard.press("Escape")
    context_action(page, frame_label(page, "edge"), "frame-display-card")
    page.wait_for_timeout(1700)
    page.locator("[data-download-menu] > summary").click()
    page.wait_for_timeout(2200)
    page.locator("[data-download-menu] > summary").click()
    page.wait_for_timeout(1200)


#: Each architecture: its example, the name its GIF goes by, and the walk.
TOUR = (
    ("aws_three_tier", "aws", tour_aws_three_tier),
    ("aws_github_actions_oidc", "aws-pipeline", tour_aws_github_oidc),
    ("azure_aks_baseline", "azure", tour_azure_aks),
    ("gcp_streaming_analytics", "gcp", tour_gcp_streaming),
)


def record_tour(scratch: Path) -> list[tuple[Path, float]]:
    """The longer tour: AWS, AWS with numbered steps, Azure and Google Cloud,
    each walked stage by stage with the flow, its frames, captions, lenses,
    details, display modes and themes. Each architecture is its own
    recording, cut in once it is open and folded, so no page load shows."""
    takes = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for name, _label, walk in TOUR:
            source = scratch / f"{name}.html"
            source.write_text(
                render_project_html(example_project(name)), encoding="utf-8", newline="\n"
            )
            folder = scratch / name
            context = recording_context(browser, folder)
            page = context.new_page()
            errors: list[str] = []
            page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
            started = time.monotonic()
            open_editor(page, source)
            fold(page, open_panels=False)
            page.wait_for_timeout(600)
            lead_in = time.monotonic() - started
            page.wait_for_timeout(1700)
            walk(page)
            assert not errors, (name, errors)
            video = page.video
            assert video is not None
            context.close()
            takes.append((Path(video.path()), lead_in))
        browser.close()
    return takes


def to_mp4(recording: Path, lead_in: float, target: Path) -> None:
    encode(
        "-ss",
        str(lead_in),
        "-i",
        str(recording),
        "-an",
        "-r",
        "20",
        "-c:v",
        "libx264",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(target),
    )


def to_gif(movie: Path, target: Path, width: int = 1000) -> None:
    encode(
        "-i",
        str(movie),
        "-filter_complex",
        # Ten frames a second keep the flow's dashes marching. The marching
        # repaints whole regions every frame, so 32 colours, no dither and
        # rectangle diffs keep the GIFs small (the demo's is over 20 MB with
        # dithering); the vendor marks and the dark theme survive 32 colours.
        f"fps=10,scale={width}:-1:flags=lanczos,split[a][b];"
        "[a]palettegen=stats_mode=diff:max_colors=32[p];"
        "[b][p]paletteuse=dither=none:diff_mode=rectangle",
        "-loop",
        "0",
        str(target),
    )


def build_tour() -> None:
    """The tour's MP4, its architectures cut together, and a GIF for each
    architecture: one GIF of the whole tour would be over 15 MB, past what
    Markdown viewers and GitHub's image proxy show, so the README lays the
    four out as a grid, each a few MB, and links the whole MP4."""
    with tempfile.TemporaryDirectory(prefix="infragram-tour-") as folder:
        scratch = Path(folder)
        parts = []
        for index, (recording, lead_in) in enumerate(record_tour(scratch)):
            parts.append(scratch / f"part-{index}.mp4")
            to_mp4(recording, lead_in, parts[-1])
        listing = scratch / "parts.txt"
        listing.write_text("".join(f"file '{part.as_posix()}'\n" for part in parts))
        target = MEDIA / "infragram-tour.mp4"
        encode("-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(target))
        for part, (_name, label, _walk) in zip(parts, TOUR, strict=True):
            to_gif(part, IMAGES / f"infragram-tour-{label}.gif", width=800)


def main() -> None:
    brand_assets()
    mascot_loop()
    with tempfile.TemporaryDirectory(prefix="infragram-readme-") as folder:
        recording, lead_in = record_demo(Path(folder))
        to_mp4(recording, lead_in, MEDIA / "infragram-editor.mp4")
    to_gif(MEDIA / "infragram-editor.mp4", IMAGES / "infragram-editor.gif", width=900)
    build_tour()
    brand_archive()
    print("Regenerated selected pangolin PNGs, brand kit, GIFs, editor MP4 and banners")


if __name__ == "__main__":
    main()
