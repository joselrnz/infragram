"""A long frame wraps into a grid; a caption sits where its wire runs alone.

The layout knew two axes, so a subnet of twenty servers inside a VPC of
fifteen subnets came out 416 px wide and 43,032 px tall. A frame whose axis
the author left to the layout now wraps into rows once it holds six children
and its one axis runs past a limit, with the column count that brings it
nearest 16:10; ``.grid()`` asks for it outright, and ``.row()``/``.column()``
keep a frame on one axis. The top level wraps only a far longer line: a
left-to-right chain is often the point of a diagram.

Wires that leave one side of a card leave from its one point and
run together before they part. Their captions used to sit on that shared
trunk, where each names any of them; they now go where their own wire runs
alone, in both renderers (builders/captions.py ``shares_run``, runtime
14-shapes ``sharesRun``).
"""

from __future__ import annotations

import re

from infragram.author import Diagram
from infragram.builders import captions
from infragram.exports import render_project_svg
from infragram.nodes import reset_ids
from infragram.nodes.aws import compute, management_tools, security_identity, storage
from infragram.nodes.frames import aws as f


def _size(project) -> tuple[float, float]:
    svg = render_project_svg(project)
    view = re.search(r'viewBox="(-?[\d.]+) (-?[\d.]+) ([\d.]+) ([\d.]+)"', svg)
    return float(view.group(3)), float(view.group(4))


def _estate(subnets: int, per: int, *, declared: str | None = None):
    reset_ids()
    with Diagram(f"{subnets}x{per}") as diagram:
        with f.Cloud("AWS Cloud"), f.Region("us-east-1"), f.VPC("VPC"):
            for index in range(subnets):
                subnet = f.PrivateSubnet(f"subnet {index}")
                if declared:
                    getattr(subnet, declared)()
                with subnet:
                    for server in range(per):
                        compute.EC2(f"app {index}-{server}")
    return diagram.to_project()


def test_a_long_estate_wraps_into_a_shape_not_a_column() -> None:
    width, height = _size(_estate(15, 20))
    assert 0.8 < width / height < 2.5, (width, height)
    assert height < 4000


def test_a_declared_column_stays_a_column() -> None:
    width, height = _size(_estate(1, 8, declared="column"))
    assert height > 3 * width


def test_grid_wraps_even_a_short_frame() -> None:
    reset_ids()
    with Diagram("Asked for a grid") as diagram:
        with f.PrivateSubnet("subnet").grid():
            for server in range(4):
                compute.EC2(f"app {server}")
    width, height = _size(diagram.to_project())
    reset_ids()
    with Diagram("Left to the layout") as plain:
        with f.PrivateSubnet("subnet").row():
            for server in range(4):
                compute.EC2(f"app {server}")
    row_width, row_height = _size(plain.to_project())
    assert width < row_width and height > row_height


def test_a_short_frame_keeps_its_axis() -> None:
    # five cards are a line, not a shape: below grid_min nothing wraps, so
    # the frame is one card wide or one card tall
    reset_ids()
    with Diagram("Five") as diagram:
        with f.PrivateSubnet("subnet"):
            servers = [compute.EC2(f"app {server}") for server in range(5)]
    from infragram.exports.render import _scene_for

    scene = _scene_for(diagram.to_project())
    xs = {node.x for node in scene.root.walk()}
    ys = {node.y for node in scene.root.walk()}
    assert len(servers) == 5 and (len(xs) == 1 or len(ys) == 1), (xs, ys)
    assert all(cluster.arranged != "grid" for cluster in scene.root.clusters())


def test_shares_run_finds_a_trunk_and_not_a_wire_alone() -> None:
    class P:
        def __init__(self, x: float, y: float) -> None:
            self.x, self.y = x, y

    trunk_a = [P(0, 100), P(300, 100), P(300, 0)]
    trunk_b = [P(0, 100), P(500, 100), P(500, 0)]
    wires = [trunk_a, trunk_b]
    assert captions.shares_run((150, 100, True), trunk_a, wires)
    assert not captions.shares_run((300, 50, False), trunk_a, wires)
    assert not captions.shares_run((400, 100, True), trunk_b, [trunk_b])


def test_captions_leave_the_shared_trunk() -> None:
    from infragram.author import Edge

    reset_ids()
    with Diagram("Fan out") as diagram:
        with f.Cloud("AWS Cloud"):
            web = compute.EC2("web")
            bucket = storage.SimpleStorageService("assets")
            secrets = security_identity.SecretsManager("secrets")
            watch = management_tools.Cloudwatch("watch")
            web >> Edge("objects", dashed=True) >> bucket
            web >> Edge("credentials", dotted=True) >> secrets
            web >> Edge("telemetry", dotted=True) >> watch
    svg = render_project_svg(diagram.to_project())
    spots = [
        (float(m.group(1)), float(m.group(2)))
        for m in re.finditer(
            r'<text[^>]*x="([\d.]+)" y="([\d.]+)"[^>]*>(?:objects|credentials|telemetry)</text>',
            svg,
        )
    ]
    assert len(spots) == 3
    # three captions, three places: not three chips in a row on one line
    assert len({round(y) for _, y in spots}) > 1 or len({round(x) for x, _ in spots}) == 3
