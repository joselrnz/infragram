"""Two wires between one pair of components do not draw on top of each other.

A side has one connection point, so two connections between the same pair
share both anchors and trace the same line: one wire on the page, the other
invisible under it, with its kind, colour and arrowhead lost. The reader sees
two labels beside a single line and has no way to tell which is which.

Each takes a lane of its own through the middle. The editor's runtime holds
them apart the same way, so the picture and the page agree.
"""

from __future__ import annotations

import re

from infragram.author import Diagram, Edge
from infragram.builders.metrics import spec
from infragram.exports import render_project_svg
from infragram.nodes.aws import compute, databases

WIRE = re.compile(r'<path d="(M[^"]+)" fill="none" stroke="([^"]+)"([^>]*)>')


def two_wires() -> str:
    with Diagram(
        "Two wires", "Two connections between one pair.", slug="parallel-wires", providers=("aws",)
    ) as diagram:
        web = compute.EC2("Web", "application")
        sql = databases.RDS("SQL", "primary")
        web >> Edge("writes") >> sql
        web >> Edge("reads", dashed=True) >> sql
    return render_project_svg(diagram.to_project())


def one_wire() -> str:
    with Diagram(
        "One wire", "A single connection.", slug="single-wire", providers=("aws",)
    ) as diagram:
        web = compute.EC2("Web", "application")
        sql = databases.RDS("SQL", "primary")
        web >> Edge("writes") >> sql
    return render_project_svg(diagram.to_project())


def wires(svg: str) -> list[tuple[str, str, str]]:
    return [(path, paint, rest) for path, paint, rest in WIRE.findall(svg)]


def test_two_wires_between_one_pair_take_different_paths() -> None:
    drawn = wires(two_wires())
    assert len(drawn) == 2, f"expected two wires, found {len(drawn)}"
    first, second = drawn
    assert first[0] != second[0], "both wires trace the same line"


def test_each_wire_keeps_its_own_kind() -> None:
    """The point of telling them apart: the dashed one is still dashed, and
    still its own colour, rather than hidden under the solid one."""
    drawn = wires(two_wires())
    dashes = [rest for _, _, rest in drawn if "stroke-dasharray" in rest]
    assert len(dashes) == 1, "one of the two is dashed"
    assert len({paint for _, paint, _ in drawn}) == 2, "each wire keeps its own colour"


def test_the_lanes_sit_either_side_of_the_line_they_would_have_shared() -> None:
    """Held apart by the router's lane, half of it each way -- so a pair is
    centred on the line one wire alone would have taken."""
    lane = float(spec()["router"]["lane"])
    assert lane > 0

    assert len(wires(one_wire())) == 1
    offsets = sorted(_furthest(path) for path, _, _ in wires(two_wires()))
    assert offsets == [-lane / 2, lane / 2], offsets


def _furthest(path: str) -> float:
    """How far the wire's own run sits from the line its ends are on.

    A corner is rounded, so the points nearest the turn sit part of the way
    there; the run itself is the point furthest from where the wire starts
    and finishes.
    """
    ys = [float(y) for _, y in re.findall(r"[ML](-?[\d.]+),(-?[\d.]+)", path)]
    assert ys, path
    return max((y - ys[0] for y in ys), key=abs)


def test_a_lone_wire_takes_no_lane() -> None:
    """A wire with nothing to avoid runs straight: the lane is for the
    overlap, and a bend nobody needs is a bend nobody asked for."""
    alone = wires(one_wire())
    assert len(alone) == 1
    turns = len(re.findall(r"[QL]", alone[0][0]))
    both = wires(two_wires())
    assert all(len(re.findall(r"[QL]", path)) > turns for path, _, _ in both)
