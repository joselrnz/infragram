"""A card is sized for its own text, so the text is never cut.

A card grows to fit its name and detail line, then the width snaps up to the
4 px grid the layout works on. Three separate roundings sat between the width
a card asked for and the characters a renderer agreed to draw, and each one
threw away a fraction of a pixel in the same direction: the layout floored the
needed width before snapping it up, the static renderer floored the character
budget, and that renderer measured a card's detail line at a different advance
than the layout had reserved for it. Text that fitted exactly came out one
character short, with an ellipsis standing where the character should be.

The lengths below are the ones that failed in 0.1.62: a 21-character name and
detail lines of 29, 32 and 39 characters.
"""

from __future__ import annotations

import pytest

from infragram.author import Diagram
from infragram.exports import render_project_svg
from infragram.nodes import infragram as shared, reset_ids


@pytest.fixture(autouse=True)
def _fresh_ids():
    reset_ids()


def _svg(*pairs: tuple[str, str]) -> str:
    """One card per pair, drawn as cards, as a finished static SVG."""
    with Diagram(
        "Card text fits",
        "Every card is sized for its own text",
        slug="card-text-fits",
        display="card",
    ) as diagram:
        for name, detail in pairs:
            shared.identity.PublicUsers(name, detail)
    return render_project_svg(diagram.to_project())


@pytest.mark.parametrize("name", ["N" * 21, "W" * 20, "M" * 22])
def test_a_name_that_fits_is_drawn_whole(name: str) -> None:
    assert "…" not in _svg((name, ""))


@pytest.mark.parametrize("length", [29, 32, 39])
def test_a_detail_line_that_fits_is_drawn_whole(length: int) -> None:
    assert "…" not in _svg(("Service", "d" * length))


def test_the_layout_reserves_room_for_every_character_it_measured() -> None:
    """The width a card takes must cover the text the layout measured.

    This is the rounding itself rather than the picture: the needed width is
    a float, and snapping it to the grid has to round up, never down.
    """
    import math

    from infragram.builders import metrics
    from infragram.builders.scene import DETAIL_ADVANCE, TITLE_ADVANCE, Node, Style

    style = Style()
    # Only ``fit`` sizing grows a card to its text; a fixed preset promises a
    # box and truncates instead.
    style.canvas.fit = True
    ns = style.node
    end = metrics.card()["text_end"]
    for length in range(1, 80):
        for name, detail, needed in (
            ("x" * length, "", ns.text_inset + length * ns.title_size * TITLE_ADVANCE + end),
            ("x", "d" * length, ns.text_inset + length * DETAIL_ADVANCE + end),
        ):
            node = Node(name=name, detail=detail)
            node.resolve(style)
            if needed <= ns.width or needed > ns.max_width:
                continue
            assert node.width >= needed, f"{length} characters need {needed}, card is {node.width}"
            assert node.width == min(ns.max_width, math.ceil(needed / 4) * 4)


def _checker():
    import importlib.util
    from pathlib import Path

    root = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
    path = root / "plugin" / "skills" / "infragram-architect" / "scripts" / "project_check.py"
    spec = importlib.util.spec_from_file_location("project_check", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_checker_reports_text_that_was_cut() -> None:
    """The guard has to fail when the bug comes back, or it guards nothing."""
    checker = _checker()
    with Diagram(
        "Cut text", "A card whose text was cut", slug="cut-text", display="card"
    ) as diagram:
        shared.identity.PublicUsers("Readable name", "a detail line")
    project = diagram.to_project()
    svg = render_project_svg(project)
    payload = project.model_dump(mode="json")

    clean: list[str] = []
    checker.check_svg(svg, clean, payload)
    assert clean == []

    # The same picture with one card's name cut, as the old arithmetic drew it.
    cut = svg.replace(">Readable name<", ">Readable nam…<", 1)
    assert cut != svg
    found: list[str] = []
    checker.check_svg(cut, found, payload)
    assert any("text cut" in message for message in found), found
