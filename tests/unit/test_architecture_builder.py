"""Layout invariants for the declarative architecture builder.

These test placement arithmetic, not markup: nodes must not overlap, a
cluster must actually contain its children, and the canvas must be large
enough for everything it was asked to draw. The rendered HTML is covered
separately by the skin, geometry, and self-check gates.
"""

from __future__ import annotations

import pytest

from infragram.builders.architecture import Node, Scene, place, render
from infragram.themes import Theme

THEME = Theme.from_colors(
    {
        "paper": "#0f1720",
        "paper_2": "#162635",
        "ink": "#f5f9fd",
        "muted": "#bfceda",
        "soft": "#8aa4b8",
        "accent": "#50a7e8",
        "link": "#78bced",
    }
)


def sample_scene() -> Scene:
    scene = Scene(slug="fixture", theme=THEME, title="Fixture", desc="A fixture diagram.")
    left = scene.cluster("Edge")
    left.node("Reader", "browser")
    outer = scene.cluster("Platform")
    inner = outer.cluster("Private network")
    inner.node("Gateway", "ingress")
    inner.node("Service", "runtime", focal=True)
    wide = scene.cluster("Consumers")
    row = wide.cluster("Tier", flow="row")
    row.node("Consumer A")
    row.node("Consumer B")
    return place(scene)


@pytest.fixture
def scene() -> Scene:
    """The placed sample scene the layout invariants below are asked of.

    Four tests take this by name. Without it pytest reports them as
    errors rather than failures, which is quiet enough that they can stop
    running without anyone noticing.
    """
    return sample_scene()


def overlaps(a: Node, b: Node) -> bool:
    return not (
        a.x + a.width <= b.x
        or b.x + b.width <= a.x
        or a.y + a.height <= b.y
        or b.y + b.height <= a.y
    )


def test_no_node_overlaps(scene: Scene) -> None:
    nodes = list(scene.root.walk())
    for i, a in enumerate(nodes):
        for b in nodes[i + 1 :]:
            if overlaps(a, b):
                raise AssertionError(f"nodes overlap: {a.name!r} and {b.name!r}")
    print(f"OK: {len(nodes)} nodes placed without overlap")


def test_clusters_contain_children(scene: Scene) -> None:
    for cl in scene.root.clusters():
        if cl is scene.root:
            continue
        for child in cl.children:
            cw, ch = (child.width, child.height)
            if not (
                cl.x <= child.x
                and child.x + cw <= cl.x + cl.width
                and cl.y <= child.y
                and child.y + ch <= cl.y + cl.height
            ):
                raise AssertionError(
                    f"cluster {cl.label!r} does not contain child at "
                    f"({child.x},{child.y},{cw},{ch}); cluster is "
                    f"({cl.x},{cl.y},{cl.width},{cl.height})"
                )
    print("OK: every cluster encloses its children")


def test_canvas_fits_content(scene: Scene) -> None:
    """A preset viewBox that is too small silently clips whole clusters."""
    for cl in scene.root.clusters():
        if cl is scene.root:
            continue
        if cl.x < 0 or cl.x + cl.width > scene.width:
            raise AssertionError(
                f"cluster {cl.label!r} runs off the canvas: "
                f"{cl.x}..{cl.x + cl.width} vs width {scene.width}"
            )
    for node in scene.root.walk():
        if node.y + node.height > scene.height:
            raise AssertionError(f"node {node.name!r} runs off the bottom of the canvas")
    print(f"OK: canvas {scene.width}x{scene.height} fits its content")


def test_nesting_is_recursive() -> None:
    """A cluster inside a cluster inside a cluster still measures correctly."""
    scene = Scene(slug="deep", theme=THEME, title="Deep", desc="Deep nesting.")
    a = scene.cluster("A")
    b = a.cluster("B")
    c = b.cluster("C")
    c.node("Leaf")
    place(scene)
    if not (a.width > b.width > c.width):
        raise AssertionError(f"nesting did not grow outward: {a.width} {b.width} {c.width}")
    print("OK: nested clusters grow outward from the leaf")


def test_render_is_deterministic(scene: Scene) -> None:
    if render(scene) != render(scene):
        raise AssertionError("render() is not deterministic")
    print("OK: render output is stable across calls")


def test_symbols_are_emitted_once_per_artwork() -> None:
    """Two nodes sharing an icon must not emit the symbol twice.

    Every icon lookup builds a fresh ProviderIcon, so deduping by object
    identity silently produced duplicate ids in one SVG document.
    """
    import re
    from collections import Counter

    from infragram.builders.architecture import from_topology
    from infragram.nodes import Group, reset_ids
    from infragram.nodes.azure import networking

    reset_ids()
    root = Group("Estate", "subscription")
    for name in ("Hub A", "Hub B", "Hub C"):
        zone = root >> Group(name, "vnet")
        zone >> networking.Bastions("Bastion", "operator access")

    scene = from_topology(root, THEME, slug="dupes", title="t", desc="d")
    ids = re.findall(r'<symbol[^>]*id="([^"]+)"', render(scene))
    repeated = {k: v for k, v in Counter(ids).items() if v > 1}
    if repeated:
        raise AssertionError(f"duplicate symbol ids: {repeated}")
    # Frames without a badge add one generic-glyph symbol per kind; the
    # artwork rule concerns the icon symbols.
    icons = [symbol_id for symbol_id in ids if symbol_id.startswith("icon-")]
    if len(icons) != 1:
        raise AssertionError(f"expected 1 icon symbol for 3 uses, got {len(icons)}: {ids}")
    print("OK: shared artwork emits exactly one <symbol>")


def test_two_packs_sharing_a_slug_keep_their_own_artwork() -> None:
    """Five libraries each ship an ``app-service``; one document may draw two.

    Symbols were keyed by slug alone, so the second pack's node borrowed the
    first pack's picture. Keyed by artwork, each pack gets its own symbol
    and its own <use>.
    """
    import re

    from infragram.builders.architecture import from_topology
    from infragram.nodes import Group, reset_ids
    from infragram.nodes.proxmox import compute as proxmox
    from infragram.nodes.vmware import compute as vmware

    reset_ids()
    root = Group("Migration", "site")
    root >> vmware.AppService("Old app", "vSphere")
    root >> proxmox.AppService("New app", "Proxmox")
    svg = render(from_topology(root, THEME, slug="shared-slug", title="t", desc="d"))
    symbols = re.findall(r'<symbol id="(icon-app-service[^"]*)"[^>]*>(.*?)</symbol>', svg, re.S)
    ids = [symbol_id for symbol_id, _ in symbols]
    if ids != ["icon-app-service", "icon-app-service-2"]:
        raise AssertionError(f"expected one symbol per pack, got {ids}")
    fills = [re.search(r'fill="(#[0-9a-f]{6})"', body).group(1) for _, body in symbols]
    if fills != ["#0091da", "#e57000"]:
        raise AssertionError(f"the tiles carry the wrong colours: {fills}")
    uses = re.findall(r'href="#(icon-app-service[^"]*)"', svg)
    if sorted(uses) != ["icon-app-service", "icon-app-service-2"]:
        raise AssertionError(f"each node must use its own symbol: {uses}")
    print("OK: two packs sharing a slug draw their own tiles")


def _searched(start, end, obstacles):
    """The search the renderer runs (``_route_uncached``, step 3): a stub
    out of each side, a wall behind each stub, the obstacles inflated by
    the clearance, and the anchors spliced back on."""
    from infragram.builders.render import _strip, _stub_point
    from infragram.builders.routing import Route, Router

    router = Router()
    boxes = [box.inflate(router.clearance) for box in obstacles]
    a, b = _stub_point(start, "right", boxes, router), _stub_point(end, "left", boxes, router)
    found = router.route_prepared(a, b, boxes, [_strip(start, a), _strip(end, b)])
    return None if found is None else Route(Router._tidy([start, *found.corners, end]))


def test_router_goes_around_an_obstacle() -> None:
    """A box squarely between two anchors must be routed around, not through."""
    from infragram.builders.routing import Point, Rect, Route

    start, end = Point(0, 100), Point(400, 100)
    wall = Rect(180, 40, 260, 160)

    if Route((start, end)).crossings([wall]) == 0:
        raise AssertionError("the test obstacle does not actually block a straight run")

    routed = _searched(start, end, [wall])
    if routed is None:
        raise AssertionError("router found no way around a single box")
    if routed.crossings([wall]) != 0:
        raise AssertionError(f"route still enters the obstacle: {routed.corners}")
    if len(routed) < 3:
        raise AssertionError(f"a detour needs corners, got {routed.corners}")
    print(f"OK: routed around an obstacle in {len(routed)} corners")


def test_router_falls_back_when_boxed_in() -> None:
    """Fully enclosed, the wire is still drawn -- the plain path on the
    facing sides, seated like any other -- never nothing."""
    from infragram.builders.architecture import load_theme
    from infragram.builders.render import _path_for, _route_uncached
    from infragram.builders.scene import Node, Scene, Style

    scene = Scene(slug="boxed", theme=load_theme("azure"), title="Boxed", desc="", style=Style())
    a = Node(name="a", ref="a", x=0, y=100, width=208, height=64)
    b = Node(name="b", ref="b", x=600, y=100, width=208, height=64)
    walls = [
        Node(name=f"w{i}", ref=f"w{i}", x=x, y=y, width=w, height=h)
        for i, (x, y, w, h) in enumerate(
            [
                (-500, -500, 2000, 580),
                (-500, 184, 2000, 600),
                (-500, -500, 490, 2000),
                (820, -500, 600, 2000),
                (220, 60, 360, 150),
            ]
        )
    ]
    for node in (a, b, *walls):
        scene.root.children.append(node)
    link = scene.link(a, b)
    routed = _route_uncached(link, scene)
    assert routed.plain and routed.sides == ("right", "left"), routed
    drawn = _path_for(link, scene)
    assert drawn.startswith("M208,132"), drawn
    print("OK: unroutable link falls back to the plain path on the facing sides")


def test_route_renders_a_closed_path() -> None:
    """to_path emits a well-formed path that starts where the route does."""
    from infragram.builders.routing import Point, Rect

    routed = _searched(Point(0, 100), Point(400, 100), [Rect(180, 40, 260, 160)])
    if routed is None:
        raise AssertionError("no route to render")
    d = routed.to_path()
    if not d.startswith("M0,100"):
        raise AssertionError(f"path does not start at the anchor: {d[:40]}")
    if d.count("Q") != len(routed) - 2:
        raise AssertionError(f"expected one curve per corner: {d}")
    print(f"OK: rendered {len(routed)} corners to a path with {d.count('Q')} curves")


def test_zones_carry_icons() -> None:
    """A container is still a service.

    Cluster artwork used to be dropped: only leaves resolved icons, and
    _symbols walked nodes only -- so a zone icon would reference a symbol
    that was never emitted.
    """
    import re

    from infragram.builders.architecture import from_topology
    from infragram.nodes import Group, reset_ids
    from infragram.nodes.azure import compute, networking

    reset_ids()
    # A generated class used as a container keeps the icon it already has.
    # The outermost element is a frame rather than a box, so the vnet is
    # nested one level in to be drawn at all.
    estate = Group("Estate", "subscription")
    vnet = networking.VirtualNetworks("Azure Virtual Network")
    subnet = Group("Control plane subnet", "subnet", icon=networking.Subnet)
    subnet >> compute.VirtualMachine("Control plane", "3 nodes")
    vnet >> subnet
    estate >> vnet

    markup = render(from_topology(estate, THEME, slug="zones", title="t", desc="d"))
    defined = set(re.findall(r'<symbol[^>]*id="([^"]+)"', markup))
    used = set(re.findall(r'<use href="#([^"]+)"', markup))
    dangling = used - defined
    if dangling:
        raise AssertionError(f"<use> without a <symbol>: {sorted(dangling)}")
    for expected in ("icon-virtual-networks", "icon-subnet"):
        if expected not in used:
            raise AssertionError(f"{expected} was never drawn; drew {sorted(used)}")
    print(f"OK: {len(used)} icons drawn across nodes and zones")


def test_zone_kind_does_not_summon_an_icon() -> None:
    """A Group's kind is a layout word, not an icon request.

    "subnet", "region" and "group" all name real icons in the catalogs, so
    the type fallback silently decorated every container with artwork the
    caller never asked for.
    """
    import re

    from infragram.builders.architecture import from_topology, load_icon_set
    from infragram.nodes import Group, reset_ids
    from infragram.nodes.azure import compute

    reset_ids()
    root = Group("Estate", "subscription")
    plain = Group("Control plane subnet", "subnet")  # kind only, no icon=
    plain >> compute.VirtualMachine("Host", "one")
    root >> plain

    scene = from_topology(
        root, THEME, slug="kinds", title="t", desc="d", icons=load_icon_set("azure")
    )
    zone = [c for c in scene.root.clusters() if c.label == "Control plane subnet"][0]
    if zone.icon is not None:
        raise AssertionError(f"kind {plain.type!r} pulled in {zone.icon.slug!r}")
    drawn = re.findall(r'<use href="#([^"]+)"', render(scene))
    if "icon-subnet" in drawn:
        raise AssertionError(f"an unrequested subnet icon was drawn: {drawn}")
    print("OK: a bare Group kind draws no artwork")


def test_skin_sets_its_own_heading_treatment() -> None:
    """A skin may state its heading face and weight; others inherit.

    The Azure drawings title semibold -- in Inter, embedded, not Segoe UI,
    which cannot ship and drew in whatever face the viewer had -- rather than
    at the default 400, and that belongs to the skin, not to every build
    script that happens to use it.
    """
    import re

    from infragram.builders.architecture import from_topology, load_theme
    from infragram.nodes import Group, reset_ids
    from infragram.nodes.azure import compute

    def heading_css(theme):
        reset_ids()
        root = Group("Estate", "subscription")
        zone = root >> Group("Zone", "vnet")
        zone >> compute.VirtualMachine("Host", "one")
        markup = render(from_topology(root, theme, slug="h", title="t", desc="d"))
        block = re.search(r"h1 \{(.*?)\}", markup, re.S).group(1)
        family = re.search(r"font-family: ([^;]+);", block).group(1)
        weight = re.search(r"font-weight: ([^;]+);", block).group(1)
        return family, weight

    azure_family, azure_weight = heading_css(load_theme("azure"))
    if "Inter" not in azure_family or azure_weight != "600":
        raise AssertionError(f"azure heading is {azure_family} / {azure_weight}")

    house_family, house_weight = heading_css(THEME)
    if "Inter" not in house_family or house_weight != "400":
        raise AssertionError(f"an undeclared skin drifted: {house_family} / {house_weight}")
    print(f"OK: azure heads at 600, undeclared skins stay at {house_weight}")


def test_border_says_what_kind_of_boundary() -> None:
    """A real perimeter draws solid; an invented grouping draws dashed."""
    import re

    from infragram.builders.architecture import from_topology
    from infragram.nodes import Group, reset_ids
    from infragram.nodes.azure import compute

    reset_ids()
    root = Group("Estate", "subscription")
    vnet = root >> Group("Virtual network", "vnet")  # a real perimeter
    logical = root >> Group("Shared services", "group")  # a reading aid
    vnet >> compute.VirtualMachine("Host", "one")
    logical >> compute.VirtualMachine("Service", "two")

    markup = render(from_topology(root, THEME, slug="edges", title="t", desc="d"))
    # A zone border is a closed path (the label seats in a corner tab), not a rect.
    zones = re.findall(r'<path d="M[^"]*Z"[^>]*?(stroke-dasharray="[^"]*")?/>', markup)
    solid = [z for z in zones if not z]
    dashed = [z for z in zones if z]
    if not solid or not dashed:
        raise AssertionError(f"expected both kinds, got {len(solid)} solid / {len(dashed)} dashed")
    print(f"OK: {len(solid)} solid perimeter(s), {len(dashed)} dashed grouping(s)")


def test_zone_fill_overrides_are_independent() -> None:
    """A zone kind may suppress or tint its fill without changing borders."""
    import re

    from infragram.builders.render import _cluster
    from infragram.builders.scene import Cluster, Scene, Style

    style = Style()
    if style.cluster.fills or style.cluster.fill_for("legacy") != "":
        raise AssertionError("fill overrides must default empty for compatibility")
    style.cluster.fills.update(
        {
            "open": "none",
            "role-tint": "accent",
            "hex-tint": "#248814",
        }
    )
    scene = Scene(title="t", desc="d", theme=THEME, slug="fills", style=style)

    def zone_fill(kind: str, depth: int = 0) -> str:
        markup = _cluster(
            Cluster(label=kind, kind=kind, depth=depth, x=10, y=20, width=200, height=100),
            scene,
        )
        match = re.search(r'<rect\b[^>]*\bfill="([^"]+)"', markup)
        if match is None:
            raise AssertionError(f"zone {kind!r} emitted no fill rect")
        return match.group(1)

    expected = {
        # An undeclared fill is none in both renderers; the depth tint is gone.
        "legacy": "none",
        "open": "none",
        "role-tint": "rgba(80,167,232,0.1)",
        "hex-tint": "rgba(36,136,20,0.1)",
    }
    actual = {
        "legacy": zone_fill("legacy", depth=1),
        "open": zone_fill("open"),
        "role-tint": zone_fill("role-tint"),
        "hex-tint": zone_fill("hex-tint"),
    }
    if actual != expected:
        raise AssertionError(f"zone fill overrides differ: {actual}")
    if style.cluster.color_for("role-tint") != "":
        raise AssertionError("a fill override leaked into the independent color map")
    print("OK: zone fills independently fall back, suppress, or tint by role/hex")


def test_aws_subnets_encode_routability() -> None:
    """The AWS provider preset owns every boundary channel and zone icon."""
    from infragram.builders import load_style

    style = load_style("aws")
    kinds = ("subnet-public", "subnet-private")
    maps = {
        "colors": style.cluster.colors,
        "dashes": style.cluster.dashes,
        "widths": style.cluster.widths,
        "radii": style.cluster.radii,
        "fills": style.cluster.fills,
    }
    for map_name, values in maps.items():
        missing = [kind for kind in kinds if kind not in values]
        if missing:
            raise AssertionError(f"AWS {map_name} silently falls through for {missing}")
    missing_badges = [kind for kind in kinds if kind not in style.cluster.icons]
    if missing_badges:
        raise AssertionError(f"AWS badges omit {missing_badges}")
    expected_colors = {
        "region": "#00a4a6",
        "vpc": "#8c4fff",
        "subnet-public": "#7aa116",
        "subnet-private": "#00a4a6",
    }
    actual_colors = {kind: style.cluster.colors[kind].lower() for kind in expected_colors}
    if actual_colors != expected_colors:
        raise AssertionError(f"AWS boundary palette differs from the reference: {actual_colors}")
    expected_fills = {
        "subnet-public": "#7aa116",
        "subnet-private": "#00a4a6",
    }
    actual_fills = {kind: style.cluster.fills[kind].lower() for kind in expected_fills}
    if actual_fills != expected_fills:
        raise AssertionError(f"AWS subnet tints differ from their own hue: {actual_fills}")
    # The deck draws the Region dotted and the Availability Zone dashed.
    # They share #00A4A6, so the line style is the only thing telling them
    # apart -- see tests/unit/test_aws_group_fidelity.py.
    if style.cluster.dashes["region"] != "2,3":
        raise AssertionError("AWS Region is not dotted like the reference")
    if style.cluster.dashes["zone"] != "5,4":
        raise AssertionError("AWS Availability Zone is not dashed like the reference")
    for kind in ("cloud", "region", "vpc", "zone", "location", "site"):
        if style.cluster.fills.get(kind) != "none":
            raise AssertionError(f"AWS {kind} must be transparent")
    # No auto-scaling entry: its service icon is a pink management tile
    # and the group border is orange, so the tab takes the semantic glyph.
    expected_icons = {
        "account": "aws:account",
        "auto-scaling": "aws:auto-scaling-group",
        "cloud": "aws:cloud-logo",
        "organization": "aws:organizations",
        "region": "aws:region",
        "site": "aws:corporate-data-center",
        "subnet-private": "aws:private-subnet",
        "subnet-public": "aws:public-subnet",
        "vpc": "aws:virtual-private-cloud-vpc",
    }
    if style.cluster.icons != expected_icons:
        raise AssertionError(f"AWS zone icons differ from the reference: {style.cluster.icons}")
    if "subnet" not in style.cluster.forbidden_kinds:
        raise AssertionError("AWS allows ambiguous kind='subnet'")
    if style.cluster.label_case != "preserve":
        raise AssertionError("AWS boundary labels must preserve standard title case")
    if style.cluster.label_font != "sans":
        raise AssertionError("AWS boundary labels must use the provider sans face")
    if style.cluster.label_tracking != "0":
        raise AssertionError("AWS boundary labels must not use technical-label tracking")
    if "Inter" not in style.sans:
        raise AssertionError(f"AWS style lost its standard type stack: {style.sans}")
    if style.mark_legend_gap != 12:
        raise AssertionError("AWS footer mark must reserve a 12px legend gap")
    if style.cluster.pad != 24:
        raise AssertionError("AWS nested boundaries must preserve the 24px reference gap")
    expected_links = {
        "vif": ("#147eba", 1.4, "7,4"),
        "vpn": ("#c7254e", 1.4, "8,3,2,3"),
        "local": ("", 1.1, None),
    }
    actual_links = {
        kind: (style.links[kind].color.lower(), style.links[kind].width, style.links[kind].dash)
        for kind in expected_links
        if kind in style.links
    }
    if actual_links != expected_links:
        raise AssertionError(f"AWS VPN link vocabulary differs from reference: {actual_links}")
    content_clearance = (
        style.canvas.height
        - style.canvas.content_bottom
        - style.canvas.legend_offset
        - style.mark_height
        - style.mark_legend_gap
    )
    if content_clearance < 16:
        raise AssertionError(
            f"AWS footer mark leaves only {content_clearance}px after diagram content"
        )
    print("OK: AWS public/private subnets carry complete, distinct zone styles")


def test_aws_style_is_automatic_and_rejects_ambiguous_subnets() -> None:
    """The AWS library's boundary preset comes from its theme, not per-script constants.

    Drawn the way an export draws an AWS document (exports/presets.py): the
    theme's style, copied, with a link kind added on top -- which must not cost
    the preset its zone styles or badges.
    """
    from infragram.builders import from_topology, load_icon_set, load_style, load_theme, render
    from infragram.builders.scene import LinkStyle, Style
    from infragram.nodes import Group, reset_ids
    from infragram.nodes.aws import compute

    def draw(root, slug: str, desc: str) -> str:
        style = load_style("aws").model_copy(deep=True)
        style.links["flow"] = LinkStyle(role="accent")
        scene = from_topology(
            root,
            load_theme("aws"),
            slug=slug,
            title="AWS",
            desc=desc,
            icons=load_icon_set("aws"),
            style=style,
            provider="aws",
        )
        return render(scene)

    reset_ids()
    root = Group("Estate", "estate")
    cloud = root >> Group("AWS Cloud", "cloud")
    region = cloud >> Group("AWS Region", "region")
    vpc = region >> Group("VPC", "vpc")
    public = vpc >> Group("Public subnet", "subnet-public")
    private = vpc >> Group("Private subnet", "subnet-private")
    public >> compute.EC2("Public host", "workload")
    private >> compute.EC2("Private host", "workload")

    markup = draw(root, "aws", "AWS zones")
    for token in (
        # The badges are the deck's own group boxes: the AWS Cloud mark and
        # the VPC box, not a third-party logo and not the VPC service icon.
        'id="icon-cloud-logo"',
        'id="icon-region"',
        'id="icon-virtual-private-cloud-vpc"',
        'id="icon-public-subnet"',
        'id="icon-private-subnet"',
        'fill="rgba(122,161,22,0.1)"',
        'fill="rgba(0,164,166,0.1)"',
        # The face every label is set in, and the same one in every
        # library: read from the default rather than written out, since a
        # literal here is what let two skins drift to a stack of their own.
        f'font-family="{Style().sans}"',
        ">AWS Cloud</text>",
    ):
        if token not in markup:
            raise AssertionError(f"automatic AWS style lost {token}")

    ambiguous = Group("Estate", "estate")
    subnet = ambiguous >> Group("Subnet", "subnet")
    subnet >> compute.EC2("Host", "workload")
    try:
        draw(ambiguous, "bad", "ambiguous")
    except ValueError as error:
        if "subnet-public" not in str(error) or "subnet-private" not in str(error):
            raise AssertionError(f"ambiguous subnet error is not actionable: {error}") from error
    else:
        raise AssertionError("AWS accepted ambiguous kind='subnet'")
    print("OK: theme=aws applies boundaries/icons and rejects ambiguous subnets")


def test_aws_zone_caption_clears_its_tab_without_a_dead_gap() -> None:
    """The glyph lives inside the tab, so its width must not be counted twice."""
    from infragram.builders import load_style
    from infragram.builders.architecture import load_icon_set, load_theme
    from infragram.builders.render import _cluster
    from infragram.builders.scene import Cluster, Scene

    style = load_style("aws")
    icon = load_icon_set("logos")["aws#mono"]
    cloud = Cluster(label="AWS Cloud", kind="cloud", icon=icon, x=10, y=20, width=200, height=100)
    scene = Scene(title="t", desc="d", theme=load_theme("aws"), slug="aws-tab", style=style)
    markup = _cluster(cloud, scene, {id(icon): "icon-aws-mono"})
    expected_x = cloud.x + style.cluster.tab + style.cluster.label_icon_gap
    if f'<text x="{expected_x}" ' not in markup:
        raise AssertionError(
            f"AWS caption is not {style.cluster.label_icon_gap}px from its tab: {markup}"
        )
    if ">AWS Cloud</text>" not in markup:
        raise AssertionError(f"AWS caption did not preserve title case: {markup}")
    print("OK: AWS zone caption sits beside its tab in standard title case")


def test_nested_aws_zone_captions_do_not_overlap() -> None:
    """Mixed tabbed/un-tabbed boundary captions need a full text-box gap."""
    import re

    from infragram.builders import load_style
    from infragram.builders.architecture import from_topology, load_icon_set, load_theme
    from infragram.builders.render import render_svg
    from infragram.nodes import Group, reset_ids
    from infragram.nodes.aws import compute

    reset_ids()
    root = Group("Estate", "estate")
    cloud = root >> Group("AWS Cloud", "cloud")
    region = cloud >> Group("AWS Region", "region")
    vpc = region >> Group("VPC · 10.0.0.0/16", "vpc")
    zone = vpc >> Group("Availability Zone A", "zone")
    subnet = zone >> Group("Public subnet · 10.0.0.0/24", "subnet-public")
    subnet >> compute.EC2("Amazon EC2 instance", "workload")

    style = load_style("aws")
    scene = from_topology(
        root,
        load_theme("aws"),
        slug="aws-labels",
        title="t",
        desc="d",
        icons=load_icon_set("aws"),
        style=style,
    )
    markup = render_svg(scene)
    found = re.findall(
        r'<text x="([\d.]+)" y="([\d.]+)"[^>]*font-size="([\d.]+)"[^>]*>'
        r"(AWS Cloud|AWS Region|VPC · 10\.0\.0\.0/16|Availability Zone A|"
        r"Public subnet · 10\.0\.0\.0/24)</text>",
        markup,
    )
    boxes = []
    for x, y, size, label in found:
        x, y, size = float(x), float(y), float(size)
        boxes.append(
            (
                label,
                x,
                y - size,
                x + len(label) * size * style.cluster.label_advance,
                y + size * 0.2,
            )
        )
    if len(boxes) != 5:
        raise AssertionError(f"expected five AWS boundary captions, got {found}")
    collisions = []
    for index, a in enumerate(boxes):
        for b in boxes[index + 1 :]:
            if a[1] < b[3] and a[3] > b[1] and a[2] < b[4] and a[4] > b[2]:
                collisions.append((a[0], b[0]))
    if collisions:
        raise AssertionError(f"AWS boundary captions overlap: {collisions}")
    print("OK: nested AWS boundary captions have disjoint measured boxes")


def test_brand_mark_clears_the_legend_lane() -> None:
    """A provider lockup belongs above the legend divider, never over its key."""
    import re

    from infragram.builders import load_style
    from infragram.builders.architecture import load_theme
    from infragram.builders.render import _mark
    from infragram.builders.scene import Scene

    style = load_style("aws")
    scene = Scene(
        title="t",
        desc="d",
        theme=load_theme("aws"),
        slug="mark",
        style=style,
        height=728,
        legend=[("solid", "Traffic")],
    )
    markup = "\n".join(_mark(scene))
    found = re.search(
        r'<svg data-brand-mark="" x="(\d+)" y="(\d+)" width="(\d+)" height="(\d+)"', markup
    )
    if not found:
        raise AssertionError("AWS brand mark was not emitted")
    _, y, _, height = map(int, found.groups())
    legend_y = scene.height - style.canvas.legend_offset
    if y + height > legend_y - 12:
        raise AssertionError(
            f"brand mark bottom {y + height} invades legend beginning at {legend_y}"
        )
    print("OK: provider mark clears the legend by at least 12px")


def test_zone_tab_reverses_monochrome_artwork() -> None:
    """A monochrome logo in a coloured zone tab must inherit paper white."""
    from infragram.builders.architecture import load_icon_set
    from infragram.builders.render import _cluster
    from infragram.builders.scene import Cluster, Scene, Style

    style = Style()
    style.cluster.colors["cloud"] = "#232f3e"
    icon = load_icon_set("logos")["aws#mono"]
    cloud = Cluster(label="AWS Cloud", kind="cloud", icon=icon, x=10, y=20, width=200, height=100)
    scene = Scene(title="t", desc="d", theme=THEME, slug="tab", style=style)
    markup = _cluster(cloud, scene, {id(icon): "icon-aws-mono"})
    # The tab seats half the kind's stroke inside the corner (the cloud draws
    # at 1.8 px), and the glyph keeps its 2 px inset within the tab.
    seat = style.cluster.width_for("cloud") / 2
    expected = (
        f'<use href="#icon-aws-mono" x="{10 + seat + 2:g}" y="{20 + seat + 2:g}" '
        'width="16" height="16" color="#0f1720" fill="#0f1720" aria-hidden="true"/>'
    )
    if expected not in markup:
        raise AssertionError(f"zone tab artwork is not reversed to paper white: {markup}")
    print("OK: monochrome zone-tab artwork inherits the paper colour")


def test_arrowheads_match_their_lines() -> None:
    """An arrowhead in another colour reads as a different link.

    Two fixed markers could not cover three link roles: everything that was
    not the accent got a muted head on a coloured line.
    """
    import re

    from infragram.builders.architecture import from_topology
    from infragram.builders.scene import LinkStyle, Style
    from infragram.nodes import Group, reset_ids
    from infragram.nodes.azure import compute

    reset_ids()
    style = Style()
    style.links.update(
        {
            "a": LinkStyle(role="accent"),
            "b": LinkStyle(role="link"),
            "c": LinkStyle(role="soft"),
            "d": LinkStyle(color="#009639"),
        }
    )
    root = Group("Estate", "subscription")
    hosts = [compute.VirtualMachine(f"Host {i}", "x") for i in range(5)]
    zone = root >> Group("Zone", "vnet")
    for host in hosts:
        zone >> host
    for kind, target in zip("abcd", hosts[1:], strict=True):
        hosts[0].to(target, kind=kind)

    markup = render(from_topology(root, THEME, slug="arrows", title="t", desc="d", style=style))
    defined = dict(
        zip(
            re.findall(r'<marker id="([^"]+)"', markup),
            re.findall(r'<marker[^>]*>\s*<path[^>]*fill="([^"]+)"', markup),
            strict=True,
        )
    )
    used = re.findall(r'stroke="(#[0-9a-fA-F]+)"[^/]*marker-end="url\(#([^)]+)\)"', markup)
    if len(used) < 4:
        raise AssertionError(f"expected four arrowed links, found {len(used)}")
    wrong = [(s, m) for s, m in used if defined.get(m, "").lower() != s.lower()]
    if wrong:
        raise AssertionError(f"arrowheads not matching their lines: {wrong}")
    print(f"OK: {len(used)} links, each with an arrowhead in its own colour")


def test_link_never_runs_through_its_own_endpoints() -> None:
    """A path may not cross the node it leaves or the one it arrives at.

    The anchor side used to be guessed from relative position -- "the target
    is to the right, so arrive at its left edge" -- which sent the path
    straight across the target whenever the route had to come round the
    other way. It showed up as a run along the target's own centre line.
    """
    import re

    from infragram.builders.architecture import from_topology
    from infragram.nodes import Group, reset_ids
    from infragram.nodes.azure import compute, networking

    reset_ids()
    root = Group("Estate", "subscription")
    # Stack the zones so the natural route has to double back.
    upper = root >> Group("Upper", "vnet")
    lower = root >> Group("Lower", "vnet")
    source = networking.NetworkInterfaces("Interface", "outbound")
    target = networking.Firewalls("Firewall", "egress")
    upper >> source
    for filler in range(3):
        lower >> compute.VirtualMachine(f"Filler {filler}", "in the way")
    lower >> target
    source.to(target, kind="solid")

    scene = from_topology(root, THEME, slug="anchors", title="t", desc="d")
    markup = render(scene)
    boxes = [(n.x, n.y, n.x + (n.width or 0), n.y + (n.height or 0)) for n in scene.root.walk()]

    def runs(path: str):
        out, cur = [], None
        for token in re.findall(r"[MLQ][-\d., ]*", path):
            head, nums = token[0], [float(v) for v in token[1:].replace(",", " ").split() if v]
            if head == "M":
                cur = (nums[0], nums[1])
            elif head == "L" and cur:
                out.append((cur, (nums[0], nums[1])))
                cur = (nums[0], nums[1])
            elif head == "Q" and cur and len(nums) >= 4:
                cur = (nums[2], nums[3])  # corner fillets are 7px
        return out

    def enters(run, box, pad=4):
        (x1, y1), (x2, y2) = run
        left, top, right, bottom = box
        return (
            min(x1, x2) < right - pad
            and max(x1, x2) > left + pad
            and min(y1, y2) < bottom - pad
            and max(y1, y2) > top + pad
        )

    offenders = [
        (run, box)
        for path in re.findall(r'<path d="(M[^"]+)" fill="none"', markup)
        for run in runs(path)
        for box in boxes
        if enters(run, box)
    ]
    if offenders:
        raise AssertionError(f"link runs through a node box: {offenders[0]}")
    print("OK: routed link clears every node box, endpoints included")


def test_zone_children_align_to_every_edge() -> None:
    """A zone insets its children equally on all four sides.

    ClusterStyle.header reserved interior space for a label that used to sit
    inside the box. Once the label moved onto the border that reservation
    became dead weight, and every zone carried 46px at the top against 20
    elsewhere -- children hanging low in their own box.
    """
    from infragram.builders.architecture import from_topology
    from infragram.nodes import Group, reset_ids
    from infragram.nodes.azure import compute

    reset_ids()
    root = Group("Estate", "subscription")
    outer = root >> Group("Outer", "vnet")
    inner = outer >> Group("Inner", "subnet")
    for index in range(2):
        inner >> compute.VirtualMachine(f"Host {index}", "workload")

    scene = from_topology(root, THEME, slug="inset", title="t", desc="d")
    checked = 0
    for cluster in scene.root.clusters():
        if cluster is scene.root or not cluster.children:
            continue
        kids = cluster.children
        insets = (
            min(k.x for k in kids) - cluster.x,
            (cluster.x + cluster.width) - max(k.x + (k.width or 0) for k in kids),
            min(k.y for k in kids) - cluster.y,
            (cluster.y + cluster.height) - max(k.y + (k.height or 0) for k in kids),
        )
        if len(set(insets)) != 1:
            raise AssertionError(f"{cluster.label!r} insets left/right/top/bottom = {insets}")
        checked += 1
    if not checked:
        raise AssertionError("no nested zones were measured")
    print(f"OK: {checked} zones inset their children equally on all four edges")
