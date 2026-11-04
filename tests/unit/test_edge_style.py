"""One wire's own colour and width, written with ``Edge(color=, width=)``.

Restyling one wire used to mean writing ``attributes["editor_edge_styles"]``
on the source element by hand, keyed by the target's id. The document and
both renderers already carried a wire's ``stroke`` and ``width``; Edge now
writes them, and a misspelt keyword says what was meant instead of a bare
TypeError.
"""

from __future__ import annotations

import re

import pytest

from infragram.author import Diagram, Edge
from infragram.exports import render_project_html, render_project_svg
from infragram.nodes import reset_ids
from infragram.nodes.aws import compute, storage
from infragram.nodes.azure import compute as azure_compute


def _pair():
    reset_ids()
    return compute.EC2("web"), storage.SimpleStorageService("bucket")


def test_color_and_width_reach_the_document_and_the_picture() -> None:
    reset_ids()
    with Diagram("Styled wire") as diagram:
        web = compute.EC2("web")
        bucket = storage.SimpleStorageService("bucket")
        web >> Edge("exfiltration", color="#d13438", width=2.5) >> bucket
    project = diagram.to_project()
    source = next(element for element in project.topology.index().values() if element.name == "web")
    target = next(
        element for element in project.topology.index().values() if element.name == "bucket"
    )
    assert source.attributes["editor_edge_styles"][target.id] == {"stroke": "#d13438", "width": 2.5}
    html = render_project_html(project)
    svg = re.search(r"<svg[^>]*data-infragram-diagram[^>]*>.*?</svg>", html, re.S).group(0)
    assert re.search(r'<path[^>]*stroke="#d13438"[^>]*stroke-width="2\.5"', svg), (
        "the static picture wears it"
    )


@pytest.mark.parametrize(
    ("keywords", "message"),
    [
        ({"color": "red"}, "a hex colour"),
        ({"width": 12}, "0.5 to 8"),
    ],
)
def test_a_colour_or_width_out_of_range_is_refused(keywords, message) -> None:
    with pytest.raises(ValueError, match=message):
        Edge("x", **keywords)


def test_a_misspelt_keyword_says_what_was_meant() -> None:
    with pytest.raises(TypeError, match="did you mean dashed="):
        Edge("x", dashd=True)
    with pytest.raises(TypeError, match="did you mean color="):
        Edge("x", colour="#fff")


def test_a_parallel_wire_cannot_ask_for_another_colour() -> None:
    web, bucket = _pair()
    web >> Edge("one", color="#d13438") >> bucket
    with pytest.raises(ValueError, match="parallel wires"):
        web >> Edge("two", color="#0078d4") >> bucket


def test_the_static_picture_draws_a_wires_own_colour_and_width() -> None:
    reset_ids()
    with Diagram("Styled", providers=("azure",)) as diagram:
        web = azure_compute.VirtualMachine("Web")
        db = azure_compute.VirtualMachine("DB")
        web >> db
    web.attributes["editor_edge_styles"] = {db.id: {"stroke": "#ff0000", "width": 3}}
    svg = render_project_svg(diagram.to_project())
    assert 'stroke="#ff0000" stroke-width="3"' in svg
