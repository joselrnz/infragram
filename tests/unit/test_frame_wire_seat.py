"""A wire aimed at a frame lands on the nearest card in it, not the first.

``node >> Edge("x") >> vpc`` is a wire to a frame, and only something drawn
can carry an end of one, so the frame resolves to a card inside itself. That
card used to be whichever the author happened to write first, so a wire could
set off across the whole frame to reach a card at the far side, cutting
through the cards in between -- and the checker then objected to the picture
instead of to the choice that made it.

Both renderers seat through one rule (``scene.seat_toward``): the static
picture re-seats once the layout has settled, and the editor state seats
against the same placed geometry, so an exported HTML and an exported SVG
agree about which card a frame's wire touches.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from infragram import exports
from infragram.author import Diagram, Edge
from infragram.editor.state import _editor_state
from infragram.exports import render_project_svg
from infragram.exports.render import _scene_for
from infragram.nodes import infragram as shared, reset_ids
from infragram.nodes.aws import compute
from infragram.nodes.azure import compute as azure_compute
from infragram.nodes.frames import aws as frames, azure as az

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())


@pytest.fixture(autouse=True)
def _fresh_ids():
    reset_ids()


def _checker():
    path = ROOT / "plugin" / "skills" / "infragram-architect" / "scripts" / "project_check.py"
    spec = importlib.util.spec_from_file_location("project_check", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _three_card_frame():
    with Diagram("Wire to a frame", "A wire aimed at a frame", slug="wire-to-frame") as diagram:
        users = shared.identity.PublicUsers("Users", "browsers")
        vpc = frames.VPC("VPC")
        with vpc:
            compute.EC2("First card", "one")
            compute.EC2("Second card", "two")
            compute.EC2("Third card", "three")
        users >> Edge("into the VPC") >> vpc
    return diagram.to_project()


def test_the_static_picture_seats_the_wire_on_the_nearest_card() -> None:
    project = _three_card_frame()
    scene = _scene_for(project)
    link = scene.links[0]
    nearest = min(
        (node for node in scene.root.walk() if node is not link.source),
        key=lambda node: (node.cx - link.source.cx) ** 2 + (node.cy - link.source.cy) ** 2,
    )
    assert link.target is nearest, f"seated on {link.target.name!r}, nearest is {nearest.name!r}"


def test_the_editor_seats_the_wire_on_the_same_card() -> None:
    """One rule, or an exported page and an exported picture disagree."""
    project = _three_card_frame()
    scene = _scene_for(project)
    state = _editor_state(project, scene, {})
    assert len(state["edges"]) == 1
    edge = state["edges"][0]
    link = scene.links[0]
    assert edge["source"] == link.source.ref
    assert edge["target"] == link.target.ref


def test_a_frame_wire_draws_a_picture_the_checker_accepts() -> None:
    project = _three_card_frame()
    errors: list[str] = []
    _checker().check_svg(render_project_svg(project), errors, project.model_dump(mode="json"))
    assert errors == [], errors


def test_a_wire_out_of_a_frame_leaves_from_the_nearest_card() -> None:
    with Diagram("Wire from a frame", "A wire leaving a frame", slug="wire-from-frame") as diagram:
        vpc = frames.VPC("VPC")
        with vpc:
            compute.EC2("First card", "one")
            compute.EC2("Second card", "two")
            compute.EC2("Third card", "three")
        outside = shared.identity.PublicUsers("Outside", "readers")
        vpc >> Edge("out of the VPC") >> outside
    project = diagram.to_project()
    scene = _scene_for(project)
    link = scene.links[0]
    nearest = min(
        (node for node in scene.root.walk() if node is not link.target),
        key=lambda node: (node.cx - link.target.cx) ** 2 + (node.cy - link.target.cy) ** 2,
    )
    assert link.source is nearest


def test_a_wire_to_an_empty_frame_or_to_its_own_first_node_is_refused() -> None:
    reset_ids()
    with Diagram("Empty", providers=("azure",)) as diagram:
        web = azure_compute.VirtualMachine("Web")
        empty = az.Subnet("empty")
        web.to(empty)
    with pytest.raises(ValueError, match="nothing drawn"):
        exports.render._scene_for(diagram.to_project())
    reset_ids()
    with Diagram("Self", providers=("azure",)) as diagram:
        with az.Subnet("snet") as subnet:
            host = azure_compute.VirtualMachine("Host")
        subnet.to(host)
    with pytest.raises(ValueError, match="same"):
        exports.render._scene_for(diagram.to_project())
