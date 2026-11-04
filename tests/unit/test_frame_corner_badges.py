"""What applies to a frame is a badge on its top-right corner.

A subnet's network security group or route table is not *inside* the subnet
the way a machine is -- it applies to it. Azure's reference diagrams seat the
NSG on the subnet's corner, on the line, and the route table beside it; both
renderers draw it that way (``CORNER_BADGE`` in builders/scene.py and runtime
14-shapes), and the Azure import puts them there. Marks on a frame's other
sides were drawn by the static picture alone and stay retired.
"""

from __future__ import annotations

import json
import re

import pytest
from pydantic import ValidationError

from infragram.author import Diagram
from infragram.builders.architecture import from_topology, load_style, load_theme
from infragram.builders.scene import CORNER_BADGE, corner_layout, corner_row_width
from infragram.exports import render_project_html, render_project_svg
from infragram.models.topology import TopologyElement
from infragram.nodes import _scope, azure, reset_ids
from infragram.nodes.frames import azure as azure_frames


@pytest.fixture(autouse=True)
def _clean():
    _scope.reset()
    reset_ids()
    yield
    _scope.reset()


def _subnet(*badges: tuple[type, str], name: str = "snet-web") -> Diagram:
    with Diagram("Badges", "A subnet and what applies to it.", slug="badges") as diagram:
        with azure_frames.VNet("vnet-app"):
            subnet = azure_frames.Subnet(name)
            for source, label in badges:
                subnet.badge(source, label=label)
            with subnet:
                azure.VirtualMachine("vm-web")
    return diagram


def _uses(svg: str) -> list[dict[str, float]]:
    return [
        {"x": float(x), "y": float(y)}
        for x, y in re.findall(
            r'<use data-frame-badge="" href="[^"]+" x="([\d.-]+)" y="([\d.-]+)"', svg
        )
    ]


def test_a_badge_is_a_corner_mark_and_the_other_sides_stay_retired() -> None:
    subnet = azure_frames.Subnet("snet-web").badge(azure.NetworkSecurityGroups, label="nsg-web")
    assert [b.model_dump() for b in subnet.badges] == [
        {
            "icon": "network-security-groups",
            "collection": "azure",
            "label": "nsg-web",
            "side": "corner",
        }
    ]
    with pytest.raises(ValueError, match="is not drawn"):
        subnet.badge(azure.RouteTables, side="top")
    # an older document's mark on another side, or with no side, is refused
    for badge in (
        {"icon": "network-security-groups"},
        {"icon": "network-security-groups", "side": "top"},
    ):
        with pytest.raises(ValidationError, match="no longer drawn"):
            TopologyElement.model_validate(
                {"id": "s", "name": "s", "type": "subnet", "badges": [badge]}
            )


def test_a_document_writes_badges_only_where_there_are_some() -> None:
    project = _subnet((azure.NetworkSecurityGroups, "nsg-web")).to_project()
    document = json.loads(project.model_dump_json())
    elements = []

    def walk(element: dict) -> None:
        elements.append(element)
        for child in element.get("children", []):
            walk(child)

    walk(document["topology"])
    with_badges = [e for e in elements if "badges" in e]
    assert [e["name"] for e in with_badges] == ["snet-web"]
    assert with_badges[0]["badges"] == [
        {
            "icon": "network-security-groups",
            "collection": "azure",
            "label": "nsg-web",
            "side": "corner",
        }
    ]
    # and it reads back the same
    assert (
        type(project).model_validate_json(project.model_dump_json()).model_dump_json()
        == project.model_dump_json()
    )


def test_the_first_icon_sits_on_the_corner_and_the_rest_leftwards() -> None:
    slots = corner_layout(400, ["nsg-web", "rt-spoke"])
    c = CORNER_BADGE
    assert slots[0] == (400, 400 - c["icon"] / 2 - c["gap"])
    width = round(len("nsg-web") * c["font"] * c["advance"])
    assert slots[1][0] == slots[0][1] - width - c["spacing"] - c["icon"] / 2
    assert corner_row_width(["nsg-web"]) == round(c["icon"] / 2 + c["gap"] + width)


def test_the_static_picture_draws_them_on_the_frame_corner() -> None:
    project = _subnet(
        (azure.NetworkSecurityGroups, "nsg-web"), (azure.RouteTables, "Route table · rt-spoke")
    ).to_project()
    svg = render_project_svg(project)
    icons = _uses(svg)
    size = CORNER_BADGE["icon"]
    # the first icon centred on a frame's top-right corner point
    frames = [
        (float(x) + float(w), float(y))
        for x, y, w in re.findall(
            r'<rect x="([\d.-]+)" y="([\d.-]+)" width="([\d.-]+)" height="[\d.-]+" rx=', svg
        )
    ]
    assert (icons[0]["x"] + size / 2, icons[0]["y"] + size / 2) in frames
    assert icons[1]["x"] < icons[0]["x"] and icons[1]["y"] == icons[0]["y"]
    # names right-aligned beside their icons; a "Type · name" caption sets
    # the type in the frame's quiet tone
    assert ">nsg-web</text>" in svg
    assert re.search(
        r'<tspan fill="[^"]+" font-weight="500">Route table · </tspan>rt-spoke</text>', svg
    )


def test_a_frame_widens_so_its_title_and_badges_never_meet() -> None:
    long = "Route table · rt-spoke-egress-through-the-hub-firewall"
    plain = _subnet(name="s").to_project()
    badged = _subnet(
        (azure.NetworkSecurityGroups, "nsg-web"), (azure.RouteTables, long), name="s"
    ).to_project()

    def width(project) -> int:
        scene = from_topology(
            project.topology,
            load_theme("azure"),
            slug=project.slug,
            title=project.title,
            desc=project.description,
            style=load_style("azure"),
        )
        return next(cl.width for cl in scene.root.clusters() if cl.label == "s")

    assert width(badged) > width(plain)
    assert width(badged) >= corner_row_width(["nsg-web", long])


def test_the_editor_page_carries_the_badges_with_their_artwork() -> None:
    project = _subnet((azure.NetworkSecurityGroups, "nsg-web")).to_project()
    page = render_project_html(project)
    state = json.loads(
        re.search(
            r'<script type="application/json" id="infragram-editor-state"[^>]*>(.*?)</script>',
            page,
            re.S,
        ).group(1)
    )
    (subnet,) = [b for b in state["boundaries"] if b["name"] == "snet-web"]
    (badge,) = subnet["badges"]
    assert {k: badge[k] for k in ("icon", "collection", "label", "side")} == {
        "icon": "network-security-groups",
        "collection": "azure",
        "label": "nsg-web",
        "side": "corner",
    }
    assert badge["iconUri"].startswith("data:image/svg+xml")


def test_a_badge_whose_artwork_is_missing_is_not_drawn() -> None:
    with Diagram("Missing", "x.", slug="missing") as diagram:
        with azure_frames.Subnet("snet").badge("azure:no-such-icon", label="gone"):
            azure.VirtualMachine("vm")
    svg = render_project_svg(diagram.to_project())
    assert "data-frame-badge" not in svg and "gone" not in svg


def test_an_empty_badges_list_from_an_older_document_still_loads() -> None:
    """Every element of an older document carries ``"badges": []``; the
    marks were retired because the editor never drew them."""
    element = TopologyElement.model_validate(
        {
            "id": "snet",
            "name": "snet",
            "type": "subnet",
            "badges": [],
            "children": [{"id": "vm", "name": "VM", "type": "vm", "badges": []}],
        }
    )
    assert "badges" not in element.model_dump()
    assert element.children[0].id == "vm"


def test_a_document_with_badges_is_refused_with_the_reason() -> None:
    with pytest.raises(ValidationError, match="no longer drawn"):
        TopologyElement.model_validate(
            {
                "id": "snet",
                "name": "snet",
                "type": "subnet",
                "badges": [{"icon": "network-security-groups"}],
            }
        )
