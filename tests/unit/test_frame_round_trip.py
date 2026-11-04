"""Frames the editor saved with nothing inside them must reopen as frames."""

from __future__ import annotations

import base64
import json
import re

import pytest

from infragram.catalog import architecture_boundary_default_size
from infragram.catalog.components import architecture_boundary_level
from infragram.editor.shell import library_catalog_from_html
from infragram.exports import render_project_html
from infragram.models.topology import TopologyElement
from infragram.projects import CloudProject


def _json_script(html: str, element_id: str) -> dict:
    match = re.search(
        rf'<script type="application/json" id="{element_id}"[^>]*>(.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    assert match is not None
    return json.loads(match.group(1))


def _frame(
    element_id: str,
    kind: str,
    name: str,
    *,
    x: int,
    y: int,
    width: int,
    height: int,
    children: list[dict] | None = None,
) -> dict:
    # Exactly what the editor's exportProject() writes for a placed frame:
    # the kind as type, the saved geometry, the gallery it came from and its
    # resolved paint, and no component reference.
    return {
        "id": element_id,
        "name": name,
        "type": kind,
        "attributes": {
            "editor_x": x,
            "editor_y": y,
            "editor_width": width,
            "editor_height": height,
            "editor_frame_group": "aws",
            "editor_boundary_style": {"stroke": "#232f3e", "fill": "none", "tabbed": True},
        },
        "children": list(children or []),
    }


def _project(children: list[dict]) -> CloudProject:
    return CloudProject.model_validate(
        {
            "schema_version": 2,
            "kind": "single-cloud",
            "slug": "frames-only",
            "title": "Frames only",
            "description": "A frame stack with nothing placed inside it yet.",
            "providers": [{"id": "aws", "enabled": True}],
            "default_library": "aws",
            "presentation": {"size": "fit"},
            "topology": {
                "id": "root",
                "name": "Frames only",
                "type": "group",
                "children": children,
            },
        }
    )


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"children": [{"id": "web", "name": "Web", "type": "service"}]}, True),
        (
            {
                "component": {
                    "provider": "infragram",
                    "service_id": "custom-boundary-vpc",
                    "icon_ref": "infragram:custom-boundary-vpc",
                }
            },
            True,
        ),
        ({"attributes": {"editor_frame_group": "aws"}}, True),
        ({"attributes": {"editor_boundary_style": {"stroke": "#8c4fff"}}}, True),
        ({}, False),
        ({"attributes": {"editor_width": 400, "editor_height": 280}}, False),
    ],
)
def test_is_frame_reads_children_or_an_explicit_frame_signal(payload: dict, expected: bool) -> None:
    element = TopologyElement.model_validate({"id": "vpc", "name": "VPC", "type": "vpc", **payload})

    assert element.is_frame is expected


def test_an_empty_frame_stack_reopens_as_boundaries_not_cards() -> None:
    stack = _frame(
        "aws-cloud",
        "cloud",
        "AWS Cloud",
        x=704,
        y=564,
        width=592,
        height=472,
        children=[
            _frame(
                "region",
                "region",
                "Region",
                x=728,
                y=588,
                width=544,
                height=424,
                children=[
                    _frame(
                        "vpc",
                        "vpc",
                        "VPC",
                        x=752,
                        y=612,
                        width=496,
                        height=376,
                        children=[
                            _frame(
                                "zone",
                                "zone",
                                "Availability Zone",
                                x=776,
                                y=636,
                                width=448,
                                height=328,
                                children=[
                                    _frame(
                                        "public-subnet",
                                        "subnet-public",
                                        "Public subnet",
                                        x=872,
                                        y=728,
                                        width=256,
                                        height=144,
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )

    state = _json_script(render_project_html(_project([stack])), "infragram-editor-state")

    assert state["nodes"] == []
    assert [boundary["id"] for boundary in state["boundaries"]] == [
        "aws-cloud",
        "region",
        "vpc",
        "zone",
        "public-subnet",
    ]
    innermost = state["boundaries"][-1]
    assert innermost["kind"] == "subnet-public"
    assert innermost["frameGroup"] == "aws"
    assert innermost["parentId"] == "zone"
    assert (innermost["x"], innermost["y"], innermost["width"], innermost["height"]) == (
        872,
        728,
        256,
        144,
    )


def test_an_empty_frame_without_a_saved_size_takes_its_kind_default() -> None:
    frame = {
        "id": "vpc",
        "name": "VPC",
        "type": "vpc",
        "attributes": {"editor_frame_group": "aws"},
    }

    state = _json_script(render_project_html(_project([frame])), "infragram-editor-state")

    assert state["nodes"] == []
    (boundary,) = state["boundaries"]
    assert (boundary["width"], boundary["height"]) == architecture_boundary_default_size("vpc")


@pytest.mark.parametrize(
    "provider", ["ovhcloud", "vultr", "akamai", "vmware", "proxmox", "cloudflare", "equinix"]
)
def test_a_preview_library_without_vendored_icons_still_exports_its_frames(provider: str) -> None:
    # These libraries ship a theme, a mark, and frames but no icon collection
    # yet. A single-library project for them must still render.
    project = CloudProject.model_validate(
        {
            "schema_version": 2,
            "kind": "single-cloud",
            "slug": f"{provider}-frames",
            "title": f"{provider} frames",
            "description": "One empty frame from a preview library.",
            "providers": [{"id": provider, "enabled": True}],
            "default_library": provider,
            "presentation": {"size": "fit"},
            "topology": {
                "id": "root",
                "name": "Frames",
                "type": "group",
                "children": [
                    {
                        "id": "region",
                        "name": "Region",
                        "type": "region",
                        "attributes": {"editor_frame_group": provider},
                    }
                ],
            },
        }
    )

    state = _json_script(render_project_html(project), "infragram-editor-state")

    assert [boundary["id"] for boundary in state["boundaries"]] == ["region"]
    assert state["nodes"] == []


def test_official_aws_group_icons_keep_their_glyph_on_the_tab() -> None:
    html = render_project_html(
        _project([_frame("region", "region", "Region", x=100, y=100, width=400, height=280)])
    )
    library = library_catalog_from_html(html)
    frames = {
        component["serviceId"]: component
        for component in library["components"]
        if component.get("componentKind") == "boundary"
    }

    for service_id in (
        "custom-boundary-region",
        "custom-boundary-vpc",
        "custom-boundary-public-subnet",
        "custom-boundary-private-subnet",
    ):
        uri = frames[service_id]["boundaryStyle"]["iconUri"]
        svg = base64.b64decode(uri.split(",", 1)[1]).decode("utf-8")
        # These AWS group icons are a white glyph on a coloured plate. Painting
        # the plate white too used to leave a blank square in the frame tab.
        assert "<path" in svg, service_id
        assert not re.search(r'<rect[^>]*width="40"[^>]*height="40"', svg), service_id


def test_public_and_private_subnet_glyphs_differ() -> None:
    html = render_project_html(
        _project([_frame("region", "region", "Region", x=100, y=100, width=400, height=280)])
    )
    library = library_catalog_from_html(html)
    icons = {
        component["serviceId"]: component["boundaryStyle"]["iconUri"]
        for component in library["components"]
        if component.get("componentKind") == "boundary" and component.get("boundaryStyle")
    }

    assert (
        icons["custom-boundary-public-subnet-generic"]
        != icons["custom-boundary-private-subnet-generic"]
    )


def test_a_team_sits_above_the_projects_it_owns() -> None:
    assert architecture_boundary_level("team") < architecture_boundary_level("project")


def test_a_gallery_frame_keeps_the_gallery_look_in_a_library_without_boundary_theme() -> None:
    # Local & On-Premises has no boundary block in its theme. A frame placed
    # from its gallery must still draw as the catalog shows it: tabbed, with
    # the kind's glyph, in the library's frame colour, captions as written.
    project = CloudProject.model_validate(
        {
            "schema_version": 2,
            "kind": "single-cloud",
            "slug": "onprem-frames",
            "title": "On-prem frames",
            "description": "One datacenter frame from the on-premises gallery.",
            "providers": [{"id": "onprem", "enabled": True}],
            "default_library": "onprem",
            "presentation": {"size": "fit"},
            "topology": {
                "id": "root",
                "name": "On-prem frames",
                "type": "group",
                "children": [
                    {
                        "id": "dc",
                        "name": "Corporate datacenter",
                        "type": "site",
                        "attributes": {"editor_frame_group": "onprem"},
                    }
                ],
            },
        }
    )

    state = _json_script(render_project_html(project), "infragram-editor-state")

    (frame,) = state["boundaries"]
    assert frame["tabbed"] is True
    assert frame["iconUri"].startswith("data:image/svg+xml")
    assert frame["labelCase"] == "preserve"
    assert frame["labelFont"] == "sans"
    assert frame["stroke"] == "#bdbdbd"
    assert frame["frameGroup"] == "onprem"


def test_a_saved_card_size_reopens_at_that_size() -> None:
    """A card's saved size is a card's size.

    The document default is icons, where the size is the mark's and this
    number means nothing, so the document that saved a card size says it
    draws cards.
    """
    web = {
        "id": "alb",
        "name": "Application Load Balancer",
        "type": "service",
        "attributes": {
            "editor_x": 528,
            "editor_y": 332,
            "editor_card_size": {"width": 288, "height": 72},
        },
    }

    project = _project([web])
    project.presentation.display = "card"
    state = _json_script(render_project_html(project), "infragram-editor-state")

    (card,) = state["nodes"]
    assert (card["width"], card["height"]) == (288, 72)
    assert card["cardSize"] == {"width": 288, "height": 72}


def test_a_connection_to_an_empty_frame_is_refused_not_dropped() -> None:
    web = {
        "id": "web",
        "name": "Web",
        "type": "service",
        "attributes": {"editor_x": 120, "editor_y": 120},
        "connections": [{"target": "vpc", "kind": "solid", "label": "PEERS"}],
    }
    frame = _frame("vpc", "vpc", "VPC", x=400, y=80, width=400, height=280)

    # An empty frame has nothing to seat a wire on. The link used to be
    # dropped without a word; the document is refused with the reason now,
    # since a silently missing wire loses a fact the author stated.
    with pytest.raises(ValueError, match="nothing drawn"):
        render_project_html(_project([web, frame]))
