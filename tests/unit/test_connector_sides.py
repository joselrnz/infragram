"""A side chosen for a connector's end is kept by both renderers.

A node has one connection point a side. The editor lets a reader
pin the side each end of a wire uses -- the Text tab's *Leaves from* and
*Arrives at* -- and writes the choice beside the wire's style, in
``editor_edge_styles[<target>]``. It has to survive the trip: the static
renderer anchors the wire there, and the page built from the same document
opens with the same choice in the panel.
"""

from __future__ import annotations

import json
import re

import pytest

from infragram import compose
from infragram.editor.state import _pinned_side
from infragram.exports import render_project_html
from infragram.exports.render import _scene_for
from infragram.nodes import infragram as shared, reset_ids
from infragram.nodes.azure import compute


@pytest.fixture(autouse=True)
def _fresh_ids():
    reset_ids()


def _pair(**style):
    """Two components and a wire, with whatever style the case pins on it."""
    users = shared.identity.PublicUsers("Users", "customers")
    app = compute.VirtualMachine("App server", "web")
    users.to(app, label="HTTPS")
    if style:
        users.attributes["editor_edge_styles"] = {app.id: dict(style)}
    return (
        compose.to_project(
            [users, app], slug="sides", title="Sides", description="Sides.", display="card"
        ),
        users,
        app,
    )


def _scene_link(project):
    scene = _scene_for(project)
    assert len(scene.links) == 1
    return scene.links[0]


def _editor_edges(html: str) -> list[dict]:
    match = re.search(r'<script[^>]*id="infragram-editor-state"[^>]*>(.*?)</script>', html, re.S)
    assert match
    return json.loads(match.group(1))["edges"]


def test_a_wire_with_no_side_chosen_is_anchored_where_the_nodes_stand() -> None:
    project, _users, _app = _pair()
    link = _scene_link(project)
    assert (link.source_side, link.target_side) == (None, None)
    edge = _editor_edges(render_project_html(project))[0]
    assert (edge["sourcePort"], edge["targetPort"]) == ("auto", "auto")


@pytest.mark.parametrize("side", ["top", "right", "bottom", "left"])
def test_a_side_pinned_on_either_end_reaches_the_static_renderer(side: str) -> None:
    project, _users, _app = _pair(source_port=side, target_port=side)
    link = _scene_link(project)
    assert (link.source_side, link.target_side) == (side, side)


def test_a_pinned_side_opens_in_the_editor_as_that_side() -> None:
    project, _users, app = _pair(source_port="bottom", target_port="top")
    edge = _editor_edges(render_project_html(project))[0]
    assert (edge["sourcePort"], edge["targetPort"]) == ("bottom", "top")
    # and the panel's own reader agrees, element by element
    element = next(item for item in project.topology.walk() if item.connections)
    connection = element.connections[0]
    assert connection.target == app.id
    assert _pinned_side(element, connection, "source_port") == "bottom"
    assert _pinned_side(element, connection, "target_port") == "top"


def test_the_side_is_kept_apart_from_the_wire_style_the_editor_edits() -> None:
    project, _users, _app = _pair(source_port="left", stroke="#c7254e", width=2.0)
    edge = _editor_edges(render_project_html(project))[0]
    assert edge["sourcePort"] == "left"
    assert edge["style"] == {"stroke": "#c7254e", "width": 2.0}, (
        "a side is not a style: the Style panel must not show it as one"
    )


def test_a_side_that_is_not_a_side_is_ignored() -> None:
    project, _users, _app = _pair(source_port="sideways", target_port=None)
    link = _scene_link(project)
    assert (link.source_side, link.target_side) == (None, None)
    edge = _editor_edges(render_project_html(project))[0]
    assert (edge["sourcePort"], edge["targetPort"]) == ("auto", "auto")


def test_a_pinned_side_moves_where_the_wire_meets_its_card() -> None:
    """The wire leaves the side it was given, not the facing one."""
    facing = _scene_link(_pair()[0])
    pinned = _scene_link(_pair(source_port="top")[0])
    assert facing.source_side is None and pinned.source_side == "top"
    from infragram.builders.render import _anchors, _route_for

    project, _users, _app = _pair(source_port="top")
    scene = _scene_for(project)
    link = scene.links[0]
    route = _route_for(link, scene)
    assert route is not None
    top = _anchors(link.source, scene)["top"]
    assert (round(route.corners[0].x), round(route.corners[0].y)) == (round(top.x), round(top.y))


def test_a_side_written_in_python_reaches_the_drawing() -> None:
    """``Edge(..., leaves=...)`` is the same choice the Text tab makes."""
    from infragram.author import Diagram, Edge
    from infragram.nodes.frames import azure as az

    with Diagram("Sides", "Sides.", slug="sides-dsl", providers=("azure",)) as diagram:
        with az.VNet("vnet-demo"):
            gateway = compute.VirtualMachine("Gateway", "WAF")
            web = compute.VirtualMachine("Web", "scale set")
        gateway >> Edge("HTTPS", leaves="bottom", arrives="top") >> web
    project = diagram.to_project()
    link = _scene_link(project)
    assert (link.source_side, link.target_side) == ("bottom", "top")
    edge = _editor_edges(render_project_html(project))[0]
    assert (edge["sourcePort"], edge["targetPort"]) == ("bottom", "top")


def test_a_side_python_does_not_know_is_refused_where_it_is_written() -> None:
    from infragram.author import Edge

    with pytest.raises(ValueError, match="unknown side"):
        Edge("HTTPS", leaves="sideways")


def test_a_second_wire_between_a_pair_cannot_ask_for_other_sides() -> None:
    """The sides live beside the pair's style, keyed by the target, so two
    parallel wires share them; one that asks for others is refused where
    it is written rather than drawn with whichever came last."""
    from infragram.author import Diagram, Edge
    from infragram.nodes.frames import azure as az

    with Diagram("Sides", "Sides.", slug="sides-twice", providers=("azure",)):
        with az.VNet("vnet-demo"):
            gateway = compute.VirtualMachine("Gateway", "WAF")
            web = compute.VirtualMachine("Web", "scale set")
        gateway >> Edge("HTTPS", leaves="bottom") >> web
        gateway >> Edge("health", leaves="bottom") >> web  # the same sides: fine
        with pytest.raises(ValueError, match="pair of sides"):
            gateway >> Edge("WSS", leaves="right") >> web


def test_a_pinned_end_keeps_its_side_when_the_router_has_to_try_others(monkeypatch) -> None:
    """Boxed in on the facing sides, the static router tries other pairs;
    an end the author pinned is not one it may move, as in the editor
    (routeSides keeps a port that is not 'auto')."""
    import importlib

    render = importlib.import_module("infragram.builders.render")
    project, _users, _app = _pair(source_port="top")
    scene = _scene_for(project)
    link = scene.links[0]

    class Found:
        corners: list = []

    calls = []

    def first_pair_boxed_in(self, a, b, boxes, walls, rails=(), fences=()):
        calls.append((a, b))
        return None if len(calls) <= 2 else Found()

    # every straight path is blocked, and the pinned pair finds no way
    # round, so the router has to reach for another pair of sides
    monkeypatch.setattr(render.Rect, "blocks", lambda self, a, b: True)
    monkeypatch.setattr(render.Router, "route_prepared", first_pair_boxed_in)
    route = render._route_uncached(link, scene)
    assert len(calls) > 2, "the router never went looking past the pinned pair"
    assert route.sides[0] == "top"
