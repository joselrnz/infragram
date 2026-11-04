"""The static picture follows the editor's geometry and routing policy.

A review of the static renderer against the editor runtime found the two
drawing the same document differently: a connection's direction and pinned
corners never reached the static picture, its legend swatch was painted in
the theme role while the wire wore the kind's own colour, a named accent
crashed inside ``rgba()``, the bottom anchor of a bare glyph ignored where
its ink sat, the lane grid sat a pixel off the editor's, a frame's title was
measured three different ways, and a boxed-in wire fell back to an unseated
path. These tests hold the static renderer to the one policy.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

import pytest

from infragram.builders import metrics
from infragram.builders.architecture import load_style, load_theme
from infragram.builders.ink import rgba
from infragram.builders.render import (
    _anchors,
    _drawn_corners,
    _node,
    _path_for,
    _route_uncached,
    cluster_label_rect,
    render_svg,
)
from infragram.builders.routing import Point, Rect
from infragram.builders.scene import (
    TITLE_MIN,
    TITLE_PAD,
    Cluster,
    Link,
    Node,
    NodeStyle,
    Scene,
    Style,
    glyph_square,
)
from infragram.catalog import ink
from infragram.editor.bundle import runtime_script
from infragram.exports import render_project_svg
from infragram.models import ProviderIcon

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
RUNTIME = runtime_script()
PLAIN = "A" * ink.EDGE_LINES


def _scene(*nodes: Node, style: Style | None = None, theme: str = "azure") -> Scene:
    scene = Scene(
        slug="review", theme=load_theme(theme), title="Review", desc="", style=style or Style()
    )
    for node in nodes:
        scene.root.children.append(node)
    return scene


def _card(name: str, x: int, y: int, width: int = 208, height: int = 64) -> Node:
    return Node(name=name, ref=name, x=x, y=y, width=width, height=height)


def _glyph_node(name: str, x: int, y: int, markup: str) -> Node:
    """A bare glyph carrying its own artwork, so its ink can be registered."""
    icon = ProviderIcon(
        slug=f"review-{name}",
        name=name,
        category="",
        path=Path("review") / f"{name}.svg",
        aliases=(),
        source_url="",
        source_release="",
        source_path="",
        terms_url="",
        sha256="",
        markup=markup,
    )
    return Node(name=name, ref=name, x=x, y=y, width=144, height=116, display="icon", icon=icon)


def _wires(svg: str) -> list[str]:
    layer = re.search(r'<g data-static-link-layer="true">(.*?)</g>', svg, re.S)
    assert layer
    return re.findall(r"<path\b[^>]*>", layer.group(1))


# -- 1. direction ------------------------------------------------------------


@pytest.mark.parametrize(
    "direction, start, end",
    [
        ("forward", False, True),
        ("both", True, True),
        ("none", False, False),
    ],
)
def test_a_connections_direction_decides_which_ends_wear_a_head(direction, start, end) -> None:
    a, b = _card("a", 0, 0), _card("b", 500, 0)
    scene = _scene(a, b)
    scene.link(a, b, direction=direction)
    (wire,) = _wires(render_svg(scene))
    assert ("marker-start=" in wire) is start, wire
    assert ("marker-end=" in wire) is end, wire
    if start or end:
        marker = re.search(r'marker-(?:start|end)="url\(#([^)]+)\)"', wire).group(1)
        assert re.search(
            rf'<marker id="{marker}"[^>]*orient="auto-start-reverse"', render_svg(scene)
        )
    else:
        assert "<marker" not in render_svg(scene), "no head, no marker"


def test_both_heads_trim_the_shaft_at_both_ends() -> None:
    a, b = _card("a", 0, 0), _card("b", 500, 200)
    scene = _scene(a, b)
    link = scene.link(a, b, direction="both")
    d = _path_for(link, scene)
    clear = metrics.load().router.radius  # any bend radius; the trim is the spec's tip_clear
    tip = __import__("infragram.builders.arrowheads", fromlist=["tip_clear"]).tip_clear()
    assert d.startswith(f"M{208 + tip:g},32"), d
    assert d.endswith(f"L{500 - tip:g},232"), d
    assert clear >= 0


def test_the_direction_travels_from_the_document_to_the_static_picture() -> None:
    from infragram.exports import render_project_svg
    from infragram.projects import CloudProject

    def project(direction: str) -> CloudProject:
        return CloudProject.model_validate(
            {
                "schema_version": 2,
                "kind": "single-cloud",
                "slug": "dir",
                "title": "Dir",
                "description": "d.",
                "providers": [{"id": "azure"}],
                "default_library": "azure",
                "topology": {
                    "id": "root",
                    "name": "Dir",
                    "type": "group",
                    "children": [
                        {
                            "id": "p",
                            "name": "Primary",
                            "type": "database",
                            "connections": [
                                {"target": "r", "kind": "dashed", "direction": direction}
                            ],
                        },
                        {"id": "r", "name": "Replica", "type": "database"},
                    ],
                },
            }
        )

    both = _wires(render_project_svg(project("both")))
    none = _wires(render_project_svg(project("none")))
    assert len(both) == 1 and "marker-start=" in both[0] and "marker-end=" in both[0]
    assert len(none) == 1 and "marker-" not in none[0]


# -- 2. waypoints ------------------------------------------------------------


def test_pinned_corners_are_the_route() -> None:
    a, b = _card("a", 0, 0), _card("b", 600, 0)
    blocker = _card("c", 300, -20)
    scene = _scene(a, blocker, b)
    # Bends are editor-canvas coordinates; they count on the drawing they were
    # pinned on, which is what a saved layout says this scene is.
    scene.saved_layout = True
    link = scene.link(a, b, waypoints=((240, 32), (240, 160), (560, 160), (560, 32)))
    routed = _route_uncached(link, scene)
    assert routed.sides == ("right", "left") and not routed.plain
    assert routed.corners == (
        Point(208, 32),
        Point(240, 32),
        Point(240, 160),
        Point(560, 160),
        Point(560, 32),
        Point(600, 32),
    )
    d = _path_for(link, scene)
    # square elbows by default, so the drawn wire turns on each pinned corner
    for x, y in ((240, 32), (240, 160), (560, 160), (560, 32)):
        assert f"L{x},{y}" in d and "Q" not in d, d
    # and the same through the document's own model
    assert Link(source=a, target=b, waypoints=((1, 2),)).waypoints == ((1.0, 2.0),)


def test_a_waypoint_on_the_anchors_line_collapses_into_it() -> None:
    a, b = _card("a", 0, 0), _card("b", 600, 0)
    scene = _scene(a, b)
    scene.saved_layout = True
    link = scene.link(a, b, waypoints=((300, 32),))
    assert _route_uncached(link, scene).corners == (Point(208, 32), Point(600, 32))


def test_pinned_corners_on_a_layout_placed_afresh_are_not_the_route() -> None:
    """The same bends on a scene the layout placed describe another drawing:
    the wire is routed around the blocker like any other."""
    a, b = _card("a", 0, 0), _card("b", 600, 0)
    blocker = _card("c", 300, -20)
    scene = _scene(a, blocker, b)
    link = scene.link(a, b, waypoints=((240, 32), (240, 160), (560, 160), (560, 32)))
    corners = _route_uncached(link, scene).corners
    assert Point(240, 160) not in corners and Point(560, 160) not in corners


# -- 3. legend ---------------------------------------------------------------


def test_the_legend_swatch_is_painted_in_the_kinds_own_colour() -> None:
    style = load_style("aws")
    scene = _scene(_card("a", 0, 0), style=style, theme="aws")
    scene.legend = [("vpn", "VPN"), ("solid", "Traffic")]
    svg = render_svg(scene)
    vpn = style.link("vpn")
    assert (
        vpn.color
        and f'x2="60" y2="{scene.height - style.canvas.legend_offset + 41}" stroke="{vpn.color}"'
        in svg
    ), svg[-1200:]
    assert f'stroke="{scene.theme[style.link("solid").role]}"' in svg


# -- 4. rgba -----------------------------------------------------------------


def test_rgba_takes_a_hex_colour_and_names_what_it_refuses() -> None:
    assert rgba("#fff", 0.5) == "rgba(255,255,255,0.5)"
    assert rgba("#0a0b0c", 1) == "rgba(10,11,12,1)"
    for bad in ("red", "rgb(1,2,3)", "#12345", "", "#ggg"):
        with pytest.raises(ValueError, match="#rgb or #rrggbb"):
            rgba(bad, 0.5)


def test_a_named_accent_is_refused_by_node_name_where_it_is_consumed() -> None:
    scene = _scene(_card("a", 0, 0))
    node = Node(name="Named", ref="n", x=0, y=0, width=208, height=64, accent="red")
    with pytest.raises(
        ValueError, match=r"node 'Named': accent 'red' is neither a theme role .* nor a hex colour"
    ):
        _node(node, scene, {})
    # a role and a hex both still draw
    for accent in ("accent", "#009639", "#963"):
        assert "<rect" in _node(
            Node(name="ok", x=0, y=0, width=208, height=64, accent=accent), scene, {}
        )


# -- 5. anchors on the ink-inset box --------------------------------------------


def test_top_and_bottom_anchors_sit_on_the_ink_boxes_centre_line() -> None:
    markup = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect x="16" width="48" height="64"/></svg>'
    node = _glyph_node("lop", 0, 0, markup)
    key = ink.artwork_key(markup.encode("utf-8"))
    ink.register(key, [0.25, 0.0, 0.0, 0.0], None)
    try:
        scene = _scene(node)
        left, top, size = glyph_square(node, scene.style)
        assert (left, top, size) == (40, 4, 64)
        anchors = _anchors(node, scene)
        centre = left + (0.25 * size + size) / 2  # the ink runs from 56 to 104: its middle is 80
        assert anchors["bottom"] == Point(centre, 116)
        assert anchors["top"] == Point(centre, top)
        assert anchors["left"] == Point(left + 16, top + size / 2)
        assert anchors["right"] == Point(left + size, top + size / 2)
        assert centre != node.cx, "the box centre is not the node centre for off-centre ink"
    finally:
        ink.register(key, None, None)


def test_a_cards_anchors_are_its_mid_edges() -> None:
    node = _card("a", 100, 200)
    assert _anchors(node, _scene(node)) == {
        "right": Point(308, 232),
        "left": Point(100, 232),
        "bottom": Point(204, 264),
        "top": Point(204, 200),
    }


# -- 6. lane grid --------------------------------------------------------------


def test_lanes_lie_on_the_inflated_edges_themselves() -> None:
    box = Rect(10, 20, 30, 40)
    assert box.edges_x == (10, 30) and box.edges_y == (20, 40)
    # a wire may run along a lane without entering the box it borders
    assert not box.blocks(Point(0, 20), Point(50, 20))
    assert box.blocks(Point(0, 21), Point(50, 21))


# -- 7. the frame title, measured once -------------------------------------------


def test_a_frames_title_is_measured_by_one_formula_in_three_places() -> None:
    style = Style()
    cs = style.cluster
    frame = metrics.frame()
    assert (cs.label_advance, TITLE_PAD, TITLE_MIN) == (
        frame["label_advance"],
        frame["label_pad"],
        frame["label_min"],
    )
    label = "Availability Zone A"
    expected = max(TITLE_MIN, len(label) * cs.label_size * cs.label_advance + TITLE_PAD) + cs.tab
    assert cs.title_width(label) == expected
    assert cs.title_width("") == 0
    # the routing obstacle
    cl = Cluster(label=label, x=100, y=50, width=400, height=200)
    rect = cluster_label_rect(cl, style)
    assert rect == Rect(100, 50 - cs.label_size, 100 + expected, 50 + cs.tab)
    # clamped to a narrow frame, never narrower than the minimum
    narrow = Cluster(label=label, x=100, y=50, width=60, height=200)
    assert cluster_label_rect(narrow, style).right == 160
    tiny = Cluster(label=label, x=100, y=50, width=10, height=200)
    assert cluster_label_rect(tiny, style).right == 100 + TITLE_MIN
    # the layout keeps a frame at least as wide as its title
    assert cl._title_width(style) == math.ceil(expected)
    # a frame icon reserves nothing extra: the tab already holds it
    cl.icon = ProviderIcon(
        slug="x",
        name="x",
        category="",
        path=Path("x.svg"),
        aliases=(),
        source_url="",
        source_release="",
        source_path="",
        terms_url="",
        sha256="",
        markup="<svg/>",
    )
    assert cluster_label_rect(cl, style).right == 100 + expected


def test_the_runtime_reads_the_same_title_numbers() -> None:
    box = re.search(r"const boundaryLabelBox = boundary => \{(.*?)\n  \};", RUNTIME, re.S)
    assert box, "boundaryLabelBox is missing from the runtime"
    body = box.group(1)
    for key in ("label_advance", "label_pad", "label_min"):
        assert key in body, f"boundaryLabelBox should read frame.{key}"
    assert "0.62" not in body and "* 0.58 + 12" not in body, (
        "the title formula is typed into the runtime"
    )


# -- 8. seat first, then the middle; the boxed-in fallback ---------------------------


def test_the_plain_paths_middle_is_the_middle_between_the_seated_ends() -> None:
    markup = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="48" height="64"/></svg>'
    node = _glyph_node("seat", 0, 0, markup)
    key = ink.artwork_key(markup.encode("utf-8"))
    # ink begins 16/64 in from the right along every line of the right side
    ink.register(key, None, "|".join([PLAIN, "Q" * ink.EDGE_LINES, PLAIN, PLAIN]))
    try:
        target = _card("b", 400, 200)
        scene = _scene(node, target)
        link = scene.link(node, target)
        routed = _route_uncached(link, scene)
        assert routed.plain and routed.sides == ("right", "left")
        assert routed.corners[0] == Point(104, 36), "the unseated anchor, on the glyph box"
        drawn = _drawn_corners(routed, node, target, scene)
        assert drawn[0] == Point(88, 36), "seated 16 px in on the ink"
        grid = metrics.router()["grid"]
        seated_mid = math.floor((88 + 400) / 2 / grid + 0.5) * grid
        assert drawn[1].x == drawn[2].x == seated_mid, drawn
        assert seated_mid != math.floor((104 + 400) / 2 / grid + 0.5) * grid, (
            "the test must tell the two apart"
        )
    finally:
        ink.register(key, None, None)


def test_boxed_in_the_wire_is_the_seated_plain_path_on_the_facing_sides() -> None:
    a, b = _card("a", 0, 100), _card("b", 600, 100)
    walls = [
        _card("w0", -500, -500, 2000, 580),
        _card("w1", -500, 184, 2000, 600),
        _card("w2", -500, -500, 490, 2000),
        _card("w3", 820, -500, 600, 2000),
        _card("w4", 220, 60, 360, 150),
    ]
    scene = _scene(a, b, *walls)
    link = scene.link(a, b)
    routed = _route_uncached(link, scene)
    assert routed.plain and routed.sides == ("right", "left")
    assert routed.corners == (Point(208, 132), Point(600, 132))
    assert _path_for(link, scene).startswith("M208,132 L"), "a head still trims the end"


def test_the_side_fallback_keeps_the_straightened_facing_anchor() -> None:
    source, target = _card("a", 0, 0), _card("b", 400, 2)
    walls = [
        _card("beside", 220, -100, 80, 200),
        _card("above", 380, -60, 260, 56),
        _card("below", 380, 72, 260, 58),
        _card("right", 612, -100, 40, 250),
    ]
    scene = _scene(source, target, *walls)
    link = scene.link(source, target)
    routed = _route_uncached(link, scene)
    assert not routed.plain
    assert routed.sides == ("bottom", "left"), routed
    assert routed.corners[-1] == Point(400, 32), (
        "the left anchor straightened onto the source's line, not its own 34"
    )
    assert routed.corners[0] == Point(104, 64)


# -- 9. icon-node width ------------------------------------------------------------


def test_an_icon_nodes_caption_width_is_ceiled_as_a_float() -> None:
    style = Style()
    style.canvas.fit = True
    node = Node(name="x" * 23, display="icon")
    node.resolve(style)
    caption = (
        23 * style.node.title_size * 0.58 + 16
    )  # 176.08: the float ceils to 180, its int to 176
    assert node.width == math.ceil(caption / 4) * 4 == 180


# -- 10. the ink table is loud ------------------------------------------------------


def test_a_missing_or_corrupt_ink_table_raises(monkeypatch, tmp_path: Path) -> None:
    ink.load_table.cache_clear()
    try:
        monkeypatch.setattr(ink, "table_path", lambda: tmp_path / "missing.json")
        with pytest.raises(FileNotFoundError, match="ink table is not shipped"):
            ink.load_table()
        ink.load_table.cache_clear()
        broken = tmp_path / "broken.json"
        broken.write_text('{"lines": 33, "edges": {"k": "AAA|AAA|AAA|AAA"}}', encoding="utf-8")
        monkeypatch.setattr(ink, "table_path", lambda: broken)
        with pytest.raises(ValueError, match="corrupt"):
            ink.load_table()
    finally:
        monkeypatch.undo()
        ink.load_table.cache_clear()
    assert ink.load_table().edges, "the shipped table loads again"


def test_the_tables_own_line_count_is_the_one_its_edges_are_held_to() -> None:
    five = "|".join(["A" * 5] * 4)
    assert ink.InkTable(lines=5, edges={"k": five}).edges["k"] == five
    with pytest.raises(ValueError, match="4 sides of 33 lines"):
        ink.InkTable(edges={"k": five})
    with pytest.raises(ValueError, match="at least 2"):
        ink.InkTable(lines=1)
    assert ink.load_table().lines == ink.EDGE_LINES


# -- 12. every metric is read ----------------------------------------------------------


def test_every_render_metric_is_read_by_a_renderer() -> None:
    spec = json.loads(metrics.spec_path().read_text(encoding="utf-8"))
    sources = "\n".join(
        p.read_text(encoding="utf-8") for p in (ROOT / "plugin/src/infragram/builders").glob("*.py")
    )
    sources += RUNTIME
    # kind -> value tables (a frame kind's width, a tone's paint): their keys
    # are data, not metrics
    data_maps = {"widths", "tones"}

    def keys(node, path=""):
        for key, value in node.items():
            if key in ("note", "description"):
                continue
            yield f"{path}{key}", key
            if isinstance(value, dict) and key not in data_maps:
                yield from keys(value, f"{path}{key}.")

    unread = [path for path, key in keys(spec) if not re.search(rf"\b{re.escape(key)}\b", sources)]
    assert not unread, f"render-metrics.json keys no renderer reads: {unread}"


def test_the_python_renderer_reads_the_metrics_it_used_to_type() -> None:
    icon, card, frame = metrics.icon_node(), metrics.card(), metrics.frame()
    style = Style()
    assert style.node.width == card["width"]
    assert (style.node.icon_width, style.node.icon_height, style.node.icon_glyph) == (
        icon["width"],
        icon["height"],
        icon["glyph"],
    )
    assert style.node.icon_caption_min_height == icon["caption_min_height"]
    assert style.cluster.label_icon_inset == frame["icon_inset"]
    assert style.cluster.label_baseline_divisor == frame["baseline_divisor"]
    # a shorter bare glyph centres its square, the way the runtime does
    short = Node(name="s", display="icon", x=0, y=0, width=64, height=48)
    assert glyph_square(short, style) == (12, 4, 40)
    assert NodeStyle().icon_caption_min_height == icon["caption_min_height"]


def test_the_canvas_holds_a_caption_set_beside_the_rightmost_wire() -> None:
    """The editor's canvas is larger than its content and its export is
    cropped to what is drawn, captions included; the static picture grows to
    hold a caption hanging past its content instead of cutting it off."""
    import re

    from infragram.exports.render import look_variant
    from infragram.projects import CloudProject

    project = CloudProject.load(
        ROOT
        / "plugin/skills/infragram-architect/assets/templates/cloud/vdi-remote-work.infragram.json"
    )
    svg = render_project_svg(look_variant(project, "icon"))
    width, height = (
        float(value) for value in re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg).groups()
    )
    chips = [
        (float(x), float(y), float(w), float(h))
        for x, y, w, h in re.findall(
            r'<rect x="([-\d.]+)" y="([-\d.]+)" width="([\d.]+)" height="([\d.]+)" rx="3"', svg
        )
    ]
    assert chips, "the template's wires carry captions"
    assert (
        max(x + w for x, _, w, _ in chips) <= width and max(y + h for _, y, _, h in chips) <= height
    )
