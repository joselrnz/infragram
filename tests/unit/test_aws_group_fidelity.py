"""AWS group shapes must match the AWS Architecture Icons deck.

The deck defines each grouping shape's border colour, line style and label
position. The values below are transcribed from awslabs/aws-icons-for-plantuml
(`dist/Groups/*.puml`), which encodes them as
``$AWSGroupColoring(<group>, <colour>, <line>, <label>)`` -- AWS's own
project, so it is the closest machine-readable form of the deck.

A diagram that recolours these loses information a reader gets for free: the
teal of a Region, the purple of a VPC and the green of a public subnet are
how an AWS diagram is read at a glance.
"""

from __future__ import annotations

import pytest

from infragram.catalog import ARCHITECTURE_BOUNDARY_SPECS
from infragram.catalog.components import architecture_boundary_group
from infragram.editor.artwork import _boundary_component_style

#: kind -> (border colour, line style) straight from the deck.
AWS_GROUPS: dict[str, tuple[str, str]] = {
    "cloud": ("#232f3e", "solid"),
    "account": ("#e7157b", "solid"),
    "region": ("#00a4a6", "dotted"),
    "zone": ("#00a4a6", "dashed"),
    "vpc": ("#8c4fff", "solid"),
    "subnet-public": ("#7aa116", "solid"),
    "subnet-private": ("#00a4a6", "solid"),
    "security-group": ("#dd344c", "solid"),
    "auto-scaling": ("#ed7100", "dashed"),
    # AWS ships no Organizations group box. The frame takes its colour from the
    # Organizations *service* icon instead -- the same pink as the account box,
    # which is how AWS's own reference diagrams draw the boundary. It is the one
    # AWS frame whose colour is not from the group table, and frame-badges.json
    # records it as an exception with the reason.
    "organization": ("#e7157b", "dashed"),
    "site": ("#7d8998", "solid"),
    "location": ("#7d8998", "solid"),
}


def _line_style(dash: object) -> str:
    if not dash:
        return "solid"
    return "dotted" if str(dash).replace(" ", "").startswith(("1", "2")) else "dashed"


def _aws_frames() -> dict[str, str]:
    """AWS frame id -> its boundary kind."""
    return {
        spec[0]: spec[3]
        for spec in ARCHITECTURE_BOUNDARY_SPECS
        if architecture_boundary_group(spec[0]) == "aws"
    }


@pytest.mark.parametrize(("frame_id", "kind"), sorted(_aws_frames().items()))
def test_every_aws_frame_matches_the_icon_deck(frame_id: str, kind: str) -> None:
    expected = AWS_GROUPS.get(kind)
    assert expected is not None, f"{frame_id} uses kind {kind!r}, which the deck does not define"
    style = _boundary_component_style("aws", kind)
    assert style["stroke"].lower() == expected[0], f"{frame_id} border colour"
    assert _line_style(style.get("dash")) == expected[1], f"{frame_id} line style"


def test_the_deck_groups_we_claim_to_draw_all_exist() -> None:
    """Every group the deck defines that we model has a frame to draw it."""
    kinds = set(_aws_frames().values())
    for kind in (
        "cloud",
        "account",
        "region",
        "zone",
        "vpc",
        "subnet-public",
        "subnet-private",
        "security-group",
        "auto-scaling",
        "site",
    ):
        assert kind in kinds, f"no AWS frame draws the deck's {kind} group"


def test_region_and_availability_zone_stay_visually_distinct() -> None:
    """They share a colour, so the line style is the only thing telling them
    apart: the deck draws the Region dotted and the zone dashed."""
    region = _boundary_component_style("aws", "region")
    zone = _boundary_component_style("aws", "zone")
    assert region["stroke"].lower() == zone["stroke"].lower()
    assert _line_style(region.get("dash")) == "dotted"
    assert _line_style(zone.get("dash")) == "dashed"
    assert region.get("dash") != zone.get("dash")


def test_public_and_private_subnets_are_told_apart_by_colour() -> None:
    """Routability is the signal, and the deck encodes it as green vs teal."""
    public = _boundary_component_style("aws", "subnet-public")
    private = _boundary_component_style("aws", "subnet-private")
    assert public["stroke"].lower() == "#7aa116"
    assert private["stroke"].lower() == "#00a4a6"
