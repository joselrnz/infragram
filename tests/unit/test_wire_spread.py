"""Wires that run along one line are drawn apart, and none runs along a border.

Two routes that take the same lane drew one on top of the other: the reader
saw one wire where there were two, and neither had room for its caption.
``routing.spread`` moves every interior run that shares a line with another
wire's run across the room either side of it, and a run alone off a frame's
border; the editor runtime does the same (``spreadWires``), and the browser
parity gate holds the two pictures to one another.
"""

from __future__ import annotations

from infragram.builders.routing import Point, Rect, spread
from infragram.editor.bundle import runtime_script

KNOBS = {"gap": 8.0, "least": 4.0, "end": 12.0, "reach": 48.0, "band": 4.0}


def _wire(*points: tuple[float, float]) -> list[Point]:
    return [Point(x, y) for x, y in points]


def _runs_at(wire, axis: str) -> list[float]:
    return [
        a.x if axis == "v" else a.y
        for a, b in zip(wire, wire[1:], strict=False)
        if (abs(a.x - b.x) < 0.01) == (axis == "v") and abs(a.x - b.x) + abs(a.y - b.y) > 1
    ]


def test_two_wires_up_one_lane_are_drawn_apart() -> None:
    # both leave to the right, climb x=100, and arrive from the left
    one = _wire((0, 200), (100, 200), (100, 0), (200, 0))
    two = _wire((0, 180), (100, 180), (100, 20), (200, 20))
    moved = spread([one, two], [], [], **KNOBS)
    first, second = (_runs_at(wire, "v")[0] for wire in moved)
    assert abs(first - second) == 8.0, (first, second)
    # the legs that meet the cards keep their side, only their length moves
    assert moved[0][0] == one[0] and moved[1][-1] == two[-1]


def test_a_wire_alone_moves_off_a_frame_border() -> None:
    wire = _wire((0, 200), (100, 200), (100, 0), (200, 0))
    border = [("v", 101.0, -50.0, 250.0)]
    (moved,) = spread([wire], [], border, **KNOBS)
    assert abs(_runs_at(moved, "v")[0] - 101.0) >= 4.0


def test_the_room_beside_the_lane_bounds_the_spread() -> None:
    one = _wire((0, 200), (100, 200), (100, 0), (200, 0))
    two = _wire((0, 180), (100, 180), (100, 20), (200, 20))
    # cards 3 px either side of the lane: no room to draw two wires apart
    walls = [Rect(60, 40, 97, 160), Rect(103, 40, 140, 160)]
    moved = spread([one, two], walls, [], **KNOBS)
    assert moved == [tuple(one), tuple(two)]


def test_a_wire_shaped_by_hand_is_left_alone() -> None:
    # the second wire was bent by hand: it comes in as None, is not moved,
    # and gives the first nothing to make room for
    one = _wire((0, 200), (100, 200), (100, 0), (200, 0))
    moved = spread([one, None], [], [], **KNOBS)
    assert moved[1] is None and moved[0] == tuple(one)


def test_the_editor_spreads_wires_by_the_same_rule() -> None:
    runtime = runtime_script()
    for marker in ("const spreadWires", "const spreadLanes", "ROUTE.spread", "laneSpread"):
        assert marker in runtime, marker
