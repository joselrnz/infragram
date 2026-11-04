"""A click shows the flow, a double click edits -- with a mouse and on a phone.

A single click (or tap) on a component animates its wires in the traffic's
direction and steps the rest of the drawing back, without selecting it; a
double click (or double tap) selects it for editing, and a double click on
what is already selected edits its text. Wires and frames follow the same
rule. On a phone the drawing is the whole screen: the library is a drawer
that adds a tapped component, the inspector a sheet from the bottom, one
finger pans unless it lands on what is selected, and a finger held down
opens the item's menu. A tablet keeps the desktop layout, and its inspector
opens over the drawing.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from infragram.author import Diagram, Edge
from infragram.exports import render_project_html, render_timeout_ms
from infragram.nodes import _scope, azure, infragram as shared, reset_ids
from infragram.nodes.frames import azure as azure_frames

pytestmark = pytest.mark.skipif(
    os.environ.get("INFRAGRAM_RUN_BROWSER_TESTS") != "1",
    reason="set INFRAGRAM_RUN_BROWSER_TESTS=1 to run Chromium editor checks",
)

STATE = """() => ({
  selected: [...document.querySelectorAll('[data-graph-node][data-selected="true"]')].map(e => e.dataset.nodeId),
  selectedEdges: [...document.querySelectorAll('[data-edge-label][data-selected="true"]')].map(e => e.dataset.edgeId),
  flow: [...document.querySelectorAll('[data-graph-edge][data-focus-edge="true"]')].map(e => e.dataset.edgeId).sort(),
  dimmedNodes: [...document.querySelectorAll('[data-graph-node][data-focus-dimmed="true"]')].map(e => e.dataset.nodeId).sort(),
  inspectorOpen: !document.body.classList.contains('inspector-collapsed'),
  drawerOpen: !document.body.classList.contains('sidebar-collapsed'),
  menu: !document.querySelector('[data-canvas-context-menu]').hidden,
  nodes: window.infragramEditor.getState().nodes.length,
})"""


def _page(tmp_path: Path) -> Path:
    _scope.reset()
    reset_ids()
    with Diagram(
        "Flows", "Three tiers and a jump box.", slug="flows", providers=("azure",)
    ) as diagram:
        # outside every frame, so a drag has room to move it
        users = shared.identity.PublicUsers("users")
        with azure_frames.VNet("vnet-app").row():
            with azure_frames.Subnet("snet-web").column():
                gateway = azure.ApplicationGateways("agw")
                web = azure.VirtualMachine("vm-web")
            with azure_frames.Subnet("snet-data").column():
                db = azure.SQLDatabase("sql-db")
                jump = azure.VirtualMachine("vm-jump")
        users >> Edge("HTTPS") >> gateway
        gateway >> Edge("HTTPS") >> web
        web >> Edge("SQL") >> db
        jump >> Edge("SSH", both=True) >> web
    source = tmp_path / "flows.html"
    source.write_text(render_project_html(diagram.to_project()), encoding="utf-8")
    return source


def _open(page, source: Path, token: str) -> None:
    page.goto(f"{source.resolve().as_uri()}?fresh={token}")
    page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())
    page.evaluate("() => window.infragramEditor.whenSettled()")


def _centre(page, selector: str) -> tuple[float, float]:
    box = page.locator(selector).bounding_box()
    assert box, selector
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def _node(page, name: str) -> str:
    return page.evaluate(
        f"() => window.infragramEditor.getState().nodes.find(n => n.name === {name!r}).id"
    )


def _edges_of(page, node_id: str) -> list[str]:
    return sorted(
        page.evaluate(f"""() => window.infragramEditor.getState().edges
      .filter(e => e.source === {node_id!r} || e.target === {node_id!r}).map(e => e.id)""")
    )


def _empty_point(page) -> tuple[float, float]:
    return tuple(
        page.evaluate("""() => { const v = document.querySelector('.canvas-viewport').getBoundingClientRect();
      for (let y = v.bottom - 20; y > v.top + 20; y -= 12) for (let x = v.left + 20; x < v.right - 20; x += 12) {
        const el = document.elementFromPoint(x, y);
        if (el && el.closest('[data-infragram-diagram]')
            && !el.closest('[data-graph-node],[data-graph-boundary],[data-edge-group],[data-edge-label]')) return [x, y];
      } return null; }""")
    )


# ---------------------------------------------------------------- desktop


def test_a_click_shows_the_flow_and_a_double_click_edits(tmp_path: Path) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    source = _page(tmp_path)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            _open(page, source, "flow")
            web = _node(page, "vm-web")
            card = _centre(page, f'[data-graph-node][data-node-id="{web}"]')
            page.mouse.click(*card)
            state = page.evaluate(STATE)
            # its three wires animate, what they do not reach steps back, and
            # nothing is selected
            assert state["flow"] == _edges_of(page, web)
            # the press gave the drawing the keyboard, without the keyboard's
            # ring; a key brings the ring back, round the canvas
            ring = "() => getComputedStyle(document.querySelector('.canvas-viewport')).outlineStyle"
            drawing = (
                "() => getComputedStyle(document.querySelector('.diagram-stage svg')).outlineStyle"
            )
            assert page.evaluate(ring) == "none"
            page.keyboard.press("Shift")
            assert page.evaluate(ring) == "solid"
            # a toolbar button, then a card: the engine draws its own ring
            # round the whole drawing, far past the screen, unless the
            # drawing's :focus takes it off
            page.locator('[data-editor-action="zoom-fit"]').click()
            card = _centre(page, f'[data-graph-node][data-node-id="{web}"]')
            page.mouse.click(*card)
            assert page.evaluate(drawing) == "none"
            # zoomed out to fit, the grid's lines stay far enough apart to read as one
            assert (
                float(
                    page.evaluate(
                        "() => getComputedStyle(document.querySelector('.diagram-stage'))"
                        ".getPropertyValue('--editor-grid-minor-px')"
                    ).rstrip("px")
                )
                >= 10
            )
            assert state["selected"] == [] and state["dimmedNodes"] == [_node(page, "users")]
            assert (
                page.locator(
                    '[data-graph-edge][data-focus-edge="true"][data-edge-direction="both"]'
                ).count()
                == 1
            )

            page.mouse.dblclick(*card)
            state = page.evaluate(STATE)
            assert state["selected"] == [web] and state["flow"] == [] and state["inspectorOpen"]
            # the inspector opens on what was selected, not on the whole drawing
            assert (
                page.locator('[data-inspector-tab="style"]').get_attribute("aria-selected")
                == "true"
            )
            assert (
                page.locator(f'[data-graph-node][data-node-id="{web}"] [data-node-port]').count()
                == 4
            )

            # a double click on what is selected edits its text
            page.mouse.dblclick(*card)
            page.wait_for_function(
                "document.activeElement?.matches('[data-content-control=\"name\"]')"
            )

            # a double click on a card's connection point selects the card too:
            # a press there starts a wire, which leaves the browser no dblclick
            page.keyboard.press("Escape")
            page.mouse.click(*_empty_point(page))
            jump = _node(page, "vm-jump")
            dot = _centre(
                page,
                f'[data-graph-node][data-node-id="{jump}"] [data-node-port="right"] circle.node-port-dot',
            )
            page.mouse.dblclick(*dot)
            assert page.evaluate(STATE)["selected"] == [jump]

            page.keyboard.press("Escape")
            page.mouse.click(*_empty_point(page))
            state = page.evaluate(STATE)
            assert state["selected"] == [] and state["flow"] == []
        finally:
            browser.close()


def test_a_wire_and_a_frame_show_their_flow_and_a_drag_still_moves(tmp_path: Path) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    source = _page(tmp_path)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            _open(page, source, "wire")
            sql = page.evaluate(
                "() => window.infragramEditor.getState().edges.find(e => e.label === 'SQL').id"
            )
            label = _centre(page, f'[data-edge-label="{sql}"]')
            page.mouse.click(*label)
            assert page.evaluate(STATE)["flow"] == [sql]
            page.mouse.dblclick(*label)
            assert page.evaluate(STATE)["selectedEdges"] == [sql]

            # a frame: the wires of what is inside it
            data = page.evaluate(
                "() => window.infragramEditor.getState().boundaries.find(b => b.name === 'snet-data')"
            )
            page.mouse.click(*_empty_point(page))
            frame = page.locator(
                f'[data-graph-boundary][data-boundary-id="{data["id"]}"] [data-boundary-surface]'
            )
            box = frame.bounding_box()
            page.mouse.click(box["x"] + box["width"] - 12, box["y"] + box["height"] - 12)
            inside = {_node(page, "sql-db"), _node(page, "vm-jump")}
            expected = sorted({edge for node in inside for edge in _edges_of(page, node)})
            assert page.evaluate(STATE)["flow"] == expected

            # press and drag moves a card that was not selected, and selects it
            jump = _node(page, "users")
            before = page.evaluate(
                f"() => window.infragramEditor.getState().nodes.find(n => n.id === {jump!r})"
            )
            x, y = _centre(page, f'[data-graph-node][data-node-id="{jump}"]')
            page.mouse.move(x, y)
            page.mouse.down()
            page.mouse.move(x + 40, y + 24, steps=6)
            page.mouse.up()
            after = page.evaluate(
                f"() => window.infragramEditor.getState().nodes.find(n => n.id === {jump!r})"
            )
            assert (after["x"], after["y"]) != (before["x"], before["y"])
            assert page.evaluate(STATE)["selected"] == [jump]
        finally:
            browser.close()


def test_the_flow_ends_on_escape_and_never_reaches_a_download(tmp_path: Path) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    source = _page(tmp_path)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            _open(page, source, "export")
            web = _node(page, "vm-web")
            page.mouse.click(*_centre(page, f'[data-graph-node][data-node-id="{web}"]'))
            assert page.evaluate(STATE)["flow"]
            svg = page.evaluate("() => window.infragramEditor.exportSvg()")
            assert 'data-focus-edge="true"' not in svg and "data-focus-dimmed" not in svg
            page.keyboard.press("Escape")
            assert page.evaluate(STATE)["flow"] == []
        finally:
            browser.close()


# ---------------------------------------------------------------- touch


def _touch_page(browser, width: int, height: int):
    context = browser.new_context(
        viewport={"width": width, "height": height},
        device_scale_factor=2,
        is_mobile=width < 700,
        has_touch=True,
    )
    page = context.new_page()
    return context, page


class _Finger:
    def __init__(self, context, page) -> None:
        self.cdp = context.new_cdp_session(page)
        self.page = page

    def _send(self, kind: str, x: float | None = None, y: float | None = None) -> None:
        points = [] if kind == "touchEnd" else [{"x": x, "y": y, "id": 1}]
        self.cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": points})

    def tap(self, x: float, y: float) -> None:
        self._send("touchStart", x, y)
        self._send("touchEnd")

    def double_tap(self, x: float, y: float) -> None:
        # Chromium schedules the gesture, so a slow protocol round trip
        # cannot turn a tap into a hold or separate the double tap's inputs.
        self.cdp.send(
            "Input.synthesizeTapGesture",
            {
                "x": x,
                "y": y,
                "duration": 50,
                "tapCount": 2,
                "gestureSourceType": "touch",
            },
        )

    def drag(self, x0: float, y0: float, x1: float, y1: float, steps: int = 8) -> None:
        self._send("touchStart", x0, y0)
        for i in range(1, steps + 1):
            self._send("touchMove", x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps)
        self._send("touchEnd")

    def hold(self, x: float, y: float) -> None:
        self._send("touchStart", x, y)
        self.page.wait_for_timeout(750)
        self._send("touchEnd")


@pytest.mark.parametrize("width,height", [(390, 844), (820, 1180)])
def test_double_tap_uses_input_time_when_delivery_is_delayed(tmp_path: Path, width, height) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    source = _page(tmp_path)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            context, page = _touch_page(browser, width, height)
            _open(page, source, "delayed-touch")
            web = _node(page, "vm-web")
            x, y = _centre(page, f'[data-graph-node][data-node-id="{web}"]')
            page.evaluate("""() => {
              window.touchReceipts = [];
              document.addEventListener('pointerup', event => {
                if (event.pointerType === 'touch') window.touchReceipts.push({
                  input: event.timeStamp, received: performance.now()});
              }, true);
            }""")
            cdp = context.new_cdp_session(page)
            origin = time.time()
            for offset in (0, 0.08):
                cdp.send(
                    "Input.dispatchTouchEvent",
                    {
                        "type": "touchStart",
                        "touchPoints": [{"x": x, "y": y, "id": 1}],
                        "timestamp": origin + offset,
                    },
                )
                cdp.send(
                    "Input.dispatchTouchEvent",
                    {
                        "type": "touchEnd",
                        "touchPoints": [],
                        "timestamp": origin + offset + 0.01,
                    },
                )
                if offset == 0:
                    # The input stays 80 ms apart while delivery waits on a busy page.
                    page.wait_for_timeout(600)
            receipts = page.evaluate("window.touchReceipts")
            assert len(receipts) == 2
            assert 75 <= receipts[1]["input"] - receipts[0]["input"] <= 85
            assert receipts[1]["received"] - receipts[0]["received"] >= 500
            state = page.evaluate(STATE)
            assert state["selected"] == [web] and state["inspectorOpen"], state
        finally:
            browser.close()


def test_a_phone_gets_the_whole_screen_and_edits_by_touch(tmp_path: Path) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    source = _page(tmp_path)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            context, page = _touch_page(browser, 390, 844)
            _open(page, source, "phone")
            layout = page.evaluate("""() => ({
              page: document.documentElement.scrollWidth,
              canvas: document.querySelector('.canvas-viewport').getBoundingClientRect().width,
              toolbar: document.querySelector('.editor-toolbar').getBoundingClientRect().right,
              library: getComputedStyle(document.querySelector('[data-editor-action="library"]')).display,
              sidebar: document.querySelector('.provider-sidebar').getBoundingClientRect().right,
            })""")
            # nothing runs off the side; the drawing is the width of the screen
            assert layout["page"] == 390 and layout["canvas"] == 390 and layout["toolbar"] <= 390
            assert layout["library"] != "none" and layout["sidebar"] <= 0
            state = page.evaluate(STATE)
            assert not state["inspectorOpen"] and not state["drawerOpen"]

            finger = _Finger(context, page)
            web = _node(page, "vm-web")
            card = f'[data-graph-node][data-node-id="{web}"]'
            finger.tap(*_centre(page, card))
            page.wait_for_timeout(300)
            state = page.evaluate(STATE)
            assert state["flow"] == _edges_of(page, web) and state["selected"] == []
            # one finger across a card not selected pans the drawing
            jump = _node(page, "vm-jump")
            other = f'[data-graph-node][data-node-id="{jump}"]'
            fixed = page.evaluate(
                f"() => window.infragramEditor.getState().nodes.find(n => n.id === {jump!r})"
            )
            scroll = page.evaluate(
                "() => { const v = document.querySelector('.canvas-viewport');"
                " return [v.scrollLeft, v.scrollTop]; }"
            )
            x, y = _centre(page, other)
            finger.drag(x, y, x - 30, y - 30)
            page.wait_for_timeout(300)
            assert (
                page.evaluate(
                    f"() => window.infragramEditor.getState().nodes.find(n => n.id === {jump!r})"
                )
                == fixed
            )
            assert (
                page.evaluate(
                    "() => { const v = document.querySelector('.canvas-viewport');"
                    " return [v.scrollLeft, v.scrollTop]; }"
                )
                != scroll
            )

            page.wait_for_timeout(400)
            finger.double_tap(*_centre(page, card))
            page.wait_for_timeout(500)
            state = page.evaluate(STATE)
            assert state["selected"] == [web] and state["inspectorOpen"]
            # on the selection's own tab: the finger's click that follows the
            # double tap, now over the sheet, chose nothing
            assert (
                page.locator('[data-inspector-tab="style"]').get_attribute("aria-selected")
                == "true"
            )
            # the sheet takes its room from the drawing: the card stays in view
            sheet = page.locator(".right-inspector").bounding_box()
            assert page.locator(card).bounding_box()["y"] < sheet["y"]

            # one finger moves what is selected
            users = _node(page, "users")
            loose = f'[data-graph-node][data-node-id="{users}"]'
            page.wait_for_timeout(400)
            finger.double_tap(*_centre(page, loose))
            page.wait_for_timeout(500)
            assert page.evaluate(STATE)["selected"] == [users]
            before = page.evaluate(
                f"() => window.infragramEditor.getState().nodes.find(n => n.id === {users!r})"
            )
            x, y = _centre(page, loose)
            finger.drag(x, y, x + 24, y + 16)
            page.wait_for_timeout(300)
            after = page.evaluate(
                f"() => window.infragramEditor.getState().nodes.find(n => n.id === {users!r})"
            )
            assert (after["x"], after["y"]) != (before["x"], before["y"])

            # a finger held down opens the item's menu, and lifting it chooses nothing
            finger.hold(*_centre(page, other))
            page.wait_for_timeout(300)
            state = page.evaluate(STATE)
            assert state["menu"] and state["selected"] == [jump]
            page.keyboard.press("Escape")

            # the library: a drawer from the Components button; a tap adds
            finger.tap(*_centre(page, '[data-editor-action="library"]'))
            page.wait_for_timeout(500)
            assert page.evaluate(STATE)["drawerOpen"]
            categories = page.locator(".provider-sidebar details[data-category-id] > summary")
            for index in range(categories.count()):
                summary = categories.nth(index)
                summary.scroll_into_view_if_needed()
                box = summary.bounding_box()
                finger.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                page.wait_for_timeout(250)
                if page.locator(".provider-sidebar [data-component-id]:visible").count():
                    break
            tile = page.locator(".provider-sidebar [data-component-id]:visible").first
            tile.scroll_into_view_if_needed()
            count = page.evaluate(STATE)["nodes"]
            box = tile.bounding_box()
            finger.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.wait_for_timeout(500)
            state = page.evaluate(STATE)
            assert state["nodes"] == count + 1 and not state["drawerOpen"]

            # a tap on empty canvas puts the sheet away
            finger.tap(*_empty_point(page))
            page.wait_for_timeout(300)
            state = page.evaluate(STATE)
            assert state["selected"] == [] and not state["inspectorOpen"]
        finally:
            browser.close()


def test_a_tablet_keeps_the_desktop_layout_and_opens_the_inspector_over_the_drawing(
    tmp_path: Path,
) -> None:
    sync_api = pytest.importorskip("playwright.sync_api")
    source = _page(tmp_path)
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            context, page = _touch_page(browser, 820, 1180)
            _open(page, source, "tablet")
            assert page.evaluate("() => document.documentElement.scrollWidth") <= 820
            # the inspector would lie over the drawing: it starts closed
            assert not page.evaluate(STATE)["inspectorOpen"]
            # the rail, not the phone's Components button
            assert (
                page.evaluate(
                    "() => getComputedStyle(document.querySelector("
                    "'[data-editor-action=\"library\"]')).display"
                )
                == "none"
            )
            finger = _Finger(context, page)
            web = _node(page, "vm-web")
            finger.double_tap(*_centre(page, f'[data-graph-node][data-node-id="{web}"]'))
            page.wait_for_timeout(500)
            state = page.evaluate(STATE)
            assert state["selected"] == [web] and state["inspectorOpen"]
            panel = page.evaluate("""() => { const i = document.querySelector('.right-inspector');
              return {width: i.getBoundingClientRect().width,
                      tabs: getComputedStyle(i.querySelector('.md-tabs')).display}; }""")
            assert panel["width"] > 200 and panel["tabs"] != "none"
            # a finger's targets
            button = page.locator('[data-editor-action="undo"]').bounding_box()
            assert button["width"] >= 44 and button["height"] >= 44
        finally:
            browser.close()
