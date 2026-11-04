"""The page's own clipboard: copy, cut, paste and duplicate, driven in Chromium.

Not the system clipboard. An exported diagram is one file with no server
behind it, and reading the real clipboard needs a permission prompt that would
land in the middle of a drag -- so the page keeps its own, and Ctrl+C means
"this diagram's copy" the way it does in any drawing tool.

What makes this worth a browser test rather than a unit test is that every
interesting case is about *implication*: a frame has to bring what it holds, a
connector has to come along only when both of its ends do, a pasted copy has
to be a new object rather than a second reference to the old one, and the
copies have to land somewhere a reader can see them. None of that is visible
from the markup.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from infragram.exports import render_project_html, render_timeout_ms
from infragram.projects import CloudProject

pytestmark = pytest.mark.skipif(
    os.environ.get("INFRAGRAM_RUN_BROWSER_TESTS") != "1",
    reason="set INFRAGRAM_RUN_BROWSER_TESTS=1 to run Chromium editor checks",
)


def _settled(page) -> None:
    page.wait_for_load_state("load")
    page.wait_for_function("window.infragramEditor", timeout=render_timeout_ms())


def clipboard_project() -> CloudProject:
    """Two components inside a frame, joined, and one outside it.

    The frame is what makes the test interesting: copying it has to bring the
    two components and the wire between them, and leave the loose one behind.
    """
    return CloudProject.model_validate(
        {
            "schema_version": 2,
            "kind": "single-cloud",
            "slug": "clipboard-e2e",
            "title": "Clipboard E2E",
            "description": "A browser test for the page's own clipboard.",
            "providers": [{"id": "azure"}],
            "default_library": "azure",
            # The saved layout below reaches past a 960 x 600 page, and both
            # renderers draw a saved layout where it was left, so the canvas
            # fits the drawing rather than promising the default preset's size.
            "presentation": {"size": "fit"},
            "topology": {
                "id": "root",
                "name": "Clipboard E2E",
                "type": "group",
                "children": [
                    {
                        "id": "tier",
                        "name": "Tier",
                        "type": "group",
                        "children": [
                            {
                                "id": "web",
                                "name": "Web",
                                "type": "service",
                                "attributes": {"editor_x": 160, "editor_y": 200},
                                "connections": [
                                    {"target": "api", "kind": "solid", "label": "HTTP"}
                                ],
                            },
                            {
                                "id": "api",
                                "name": "API",
                                "type": "service",
                                "attributes": {"editor_x": 420, "editor_y": 200},
                            },
                        ],
                    },
                    {
                        "id": "client",
                        "name": "Client",
                        "type": "client",
                        "attributes": {"editor_x": 160, "editor_y": 560},
                    },
                ],
            },
        }
    )


@pytest.fixture()
def editor(tmp_path: Path):
    """A rendered page, open in Chromium, with the runtime attached."""
    sync_api = pytest.importorskip("playwright.sync_api")
    source = tmp_path / "clipboard.html"
    source.write_text(render_project_html(clipboard_project()), encoding="utf-8")
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1440, "height": 960})
            page.goto(source.resolve().as_uri() + "?fresh=clipboard")
            _settled(page)
            yield page
        finally:
            browser.close()


def state(page) -> dict:
    return page.evaluate("() => window.infragramEditor.getState()")


def ids(items) -> set[str]:
    return {item["id"] for item in items}


def test_copying_a_component_and_pasting_it_makes_a_second_one(editor) -> None:
    """The plain case, and the one thing that must never happen: a paste that
    hands back the same object under a new name."""
    before = state(editor)
    editor.locator('[data-graph-node][data-node-id="client"]').dblclick()
    editor.keyboard.press("Control+c")
    editor.keyboard.press("Control+v")

    after = state(editor)
    assert len(after["nodes"]) == len(before["nodes"]) + 1
    fresh = [node for node in after["nodes"] if node["id"] not in ids(before["nodes"])]
    assert len(fresh) == 1
    copy, original = fresh[0], next(n for n in before["nodes"] if n["id"] == "client")
    assert copy["id"] != original["id"]
    assert copy["name"] == original["name"]
    # somewhere a reader can see it, not underneath what it was copied from
    assert (copy["x"], copy["y"]) != (original["x"], original["y"])


def test_moving_a_pasted_copy_leaves_the_original_where_it_was(editor) -> None:
    """The guarantee a reader actually relies on after pasting.

    Two things hold it up -- `selectionBundle` clones what it picks up, and
    `pasteBundle` spreads that into a fresh object -- so removing either one
    alone leaves this passing. It is here for the property, not as a guard on
    one line: it is the check that says what a paste is *for*.
    """
    editor.locator('[data-graph-node][data-node-id="client"]').dblclick()
    editor.keyboard.press("Control+c")
    editor.keyboard.press("Control+v")
    original_before = next(n for n in state(editor)["nodes"] if n["id"] == "client")

    editor.locator('[data-inspector-tab="arrange"]').click()
    field = editor.locator('[data-exact-field="x"]')
    assert field.is_enabled(), "the pasted copy is the single selection"
    field.fill("900")
    field.press("Enter")

    nodes = {node["id"]: node for node in state(editor)["nodes"]}
    copy = next(
        node for node in nodes.values() if node["name"] == "Client" and node["id"] != "client"
    )
    assert copy["x"] == 900, "the copy moved"
    assert nodes["client"]["x"] == original_before["x"], "the original did not"


def test_copying_a_frame_brings_what_it_holds_and_the_wire_between_them(editor) -> None:
    """A frame is a region, not a rectangle. Copying one has to bring the
    components inside it and the connector joining them -- and has to leave
    the component outside it alone."""
    before = state(editor)
    tier = next(b for b in before["boundaries"] if b["id"] == "tier")
    editor.locator(f'[data-graph-boundary][data-boundary-id="{tier["id"]}"]').dblclick()
    editor.keyboard.press("Control+c")
    editor.keyboard.press("Control+v")

    after = state(editor)
    assert len(after["boundaries"]) == len(before["boundaries"]) + 1
    assert len(after["nodes"]) == len(before["nodes"]) + 2, "the two inside it came too"
    assert len(after["edges"]) == len(before["edges"]) + 1, "the wire between them came too"

    new_frame = next(b for b in after["boundaries"] if b["id"] not in ids(before["boundaries"]))
    new_nodes = [n for n in after["nodes"] if n["id"] not in ids(before["nodes"])]
    assert {n["boundaryId"] for n in new_nodes} == {new_frame["id"]}, (
        "the copies sit in the copy of the frame, not in the original"
    )

    new_edge = next(e for e in after["edges"] if e["id"] not in ids(before["edges"]))
    assert {new_edge["source"], new_edge["target"]} == {n["id"] for n in new_nodes}, (
        "the copied wire joins the copies, not the originals"
    )


def test_a_connector_is_not_copied_when_only_one_of_its_ends_is(editor) -> None:
    """Half a connector is not a connector. Copying one component of a joined
    pair brings the component and nothing else."""
    before = state(editor)
    editor.locator('[data-graph-node][data-node-id="web"]').dblclick()
    editor.keyboard.press("Control+c")
    editor.keyboard.press("Control+v")

    after = state(editor)
    assert len(after["nodes"]) == len(before["nodes"]) + 1
    assert len(after["edges"]) == len(before["edges"]), "no dangling wire came along"


def test_cut_removes_the_selection_and_paste_puts_it_back(editor) -> None:
    before = state(editor)
    editor.locator('[data-graph-node][data-node-id="client"]').dblclick()
    editor.keyboard.press("Control+x")
    assert len(state(editor)["nodes"]) == len(before["nodes"]) - 1

    editor.keyboard.press("Control+v")
    after = state(editor)
    assert len(after["nodes"]) == len(before["nodes"])
    assert "Client" in [node["name"] for node in after["nodes"]]


def test_duplicate_does_not_disturb_what_was_copied(editor) -> None:
    """Duplicating is not a copy: whatever is on the clipboard stays there,
    so Ctrl+D followed by Ctrl+V pastes what you copied, not what you
    duplicated."""
    editor.locator('[data-graph-node][data-node-id="client"]').dblclick()
    editor.keyboard.press("Control+c")
    editor.locator('[data-graph-node][data-node-id="web"]').dblclick()
    editor.keyboard.press("Control+d")
    editor.keyboard.press("Control+v")

    names = [node["name"] for node in state(editor)["nodes"]]
    assert names.count("Client") == 2, "the paste used the clipboard, not the duplicate"
    assert names.count("Web") == 2, "the duplicate happened too"


def test_each_paste_of_one_copy_lands_somewhere_new(editor) -> None:
    """Three pastes should give three copies a reader can see, not one stack
    of three."""
    editor.locator('[data-graph-node][data-node-id="client"]').dblclick()
    editor.keyboard.press("Control+c")
    for _ in range(3):
        editor.keyboard.press("Control+v")

    copies = [node for node in state(editor)["nodes"] if node["name"] == "Client"]
    assert len(copies) == 4
    places = {(node["x"], node["y"]) for node in copies}
    assert len(places) == 4, f"copies landed on top of each other: {places}"


def test_a_pasted_copy_is_selected_and_unlocked(editor) -> None:
    """What lands is what you are now holding, and it can be moved straight
    away -- a copy of a locked object that is itself locked cannot."""
    editor.evaluate("() => window.infragramEditor.getState()")
    editor.locator('[data-graph-node][data-node-id="client"]').dblclick()
    editor.keyboard.press("Control+c")
    editor.keyboard.press("Control+v")

    after = state(editor)
    copy = next(
        node for node in after["nodes"] if node["name"] == "Client" and node["id"] != "client"
    )
    assert not copy.get("locked")
    assert (
        editor.locator(f'[data-graph-node][data-node-id="{copy["id"]}"]').get_attribute(
            "data-selected"
        )
        == "true"
    ), "the copy is what is selected now"
    assert (
        editor.locator('[data-graph-node][data-node-id="client"]').get_attribute("data-selected")
        != "true"
    ), "and the original is not"


def test_a_paste_is_one_undo(editor) -> None:
    """A paste that takes several undos to take back is a paste nobody will
    risk."""
    before = state(editor)
    editor.locator('[data-graph-node][data-node-id="client"]').dblclick()
    editor.keyboard.press("Control+c")
    editor.keyboard.press("Control+v")
    assert len(state(editor)["nodes"]) == len(before["nodes"]) + 1

    editor.locator('[data-editor-action="undo"]').click()
    assert len(state(editor)["nodes"]) == len(before["nodes"])


def test_the_selection_toolbar_duplicates(editor) -> None:
    before = state(editor)
    editor.locator('[data-graph-node][data-node-id="client"]').dblclick()
    editor.locator('[data-selection-action="duplicate"]').click()
    assert len(state(editor)["nodes"]) == len(before["nodes"]) + 1


def test_the_right_click_menu_offers_copy_and_pastes_where_it_was_opened(editor) -> None:
    """Paste from the menu lands under the pointer, which is the only reason
    to reach for the menu rather than Ctrl+V."""
    editor.locator('[data-graph-node][data-node-id="client"]').dblclick()
    editor.keyboard.press("Control+c")

    target = editor.locator('[data-graph-node][data-node-id="api"]').bounding_box()
    editor.mouse.move(target["x"] + 260, target["y"] + 40)
    editor.locator('[data-graph-node][data-node-id="api"]').click(button="right")
    paste = editor.locator('[data-context-action="paste"]')
    assert paste.is_enabled(), "something is on the clipboard, so Paste is offered"
    paste.click()

    copy = next(
        node
        for node in state(editor)["nodes"]
        if node["name"] == "Client" and node["id"] != "client"
    )
    original = next(node for node in state(editor)["nodes"] if node["id"] == "client")
    assert copy["x"] > original["x"], "it landed where the menu was opened, not beside the original"


def test_paste_is_offered_only_once_something_is_held(editor) -> None:
    editor.locator('[data-graph-node][data-node-id="client"]').click(button="right")
    assert editor.locator('[data-context-action="paste"]').is_hidden(), (
        "nothing is held, so a card's menu leaves Paste out"
    )
    editor.keyboard.press("Escape")

    # the right click selected it, and Escape only closed the menu
    editor.locator('[data-graph-node][data-node-id="client"]').click()
    editor.keyboard.press("Control+c")
    editor.locator('[data-graph-node][data-node-id="client"]').click(button="right")
    assert editor.locator('[data-context-action="paste"]').is_enabled()
