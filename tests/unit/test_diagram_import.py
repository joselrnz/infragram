"""Diagrams from other tools into diagram files: ``import:diagram``.

Held here with fixtures under ``tests/fixtures/diagrams/``:

- draw.io reads every page, written plain, deflated, inside a PNG or inside
  an SVG; AWS groups become the AWS frames they are (cloud, region, VPC,
  public and private subnets by their colour's label), stencils the
  components they name (``instance2`` is EC2, ``resIcon=...rds`` RDS), an
  unlabelled group gives its shapes to its parent, a shape drawn around
  others holds them, a text cell is an annotation or a line's label, a
  line with a loose end is snapped to the shape under it or reported;
- Mermaid flowcharts read every node shape and link form, subgraphs with
  their direction, v11 ``@{}`` nodes and icons, ``click`` links; the
  architecture kind folds junctions into the lines they join; C4 reads
  boundaries, people, databases, ``Rel_Back`` and ``BiRel``; sequence
  diagrams are refused by name;
- PlantUML reads keywords, aliases, braces, every arrow, the AWS library's
  macros and groups, sprites and C4-PlantUML, and passes over notes,
  skin parameters and hidden links;
- Excalidraw reads bound labels, frames, bindings, loose arrows, library
  icons (a group of pieces) and Obsidian's LZ-compressed ``.excalidraw.md``;
- Visio reads masters, glued connectors, containers and inherited cells, and
  leaves background pages out;
- a Markdown page gives one diagram per Mermaid or PlantUML block, titled by
  its heading;
- the matcher prefers a stencil in its library, then an exact name, then a
  name the label holds, then what the words and the shape say, and never
  reaches into a cloud the diagram does not use for a common word;
- every fixture's diagram file composes, and the command writes one file and
  report per diagram, refuses to overwrite, picks pages and lists them.
"""

from __future__ import annotations

import base64
import struct
import urllib.parse
import zipfile
import zlib
from pathlib import Path

import pytest

from infragram.convert import (
    DiagramError,
    detect_format,
    draw_sketch,
    read_diagrams,
    write_sketch_report,
)
from infragram.convert.match import _WORDS, match_component, match_frame
from infragram.convert.mermaid import read_mermaid
from infragram.convert.model import Hint, Shape
from infragram.estate import Box, Card, write_spec
from infragram.estate.tables import component_class
from infragram.paths import repo_root

FIXTURES = repo_root() / "tests" / "fixtures" / "diagrams"
DRAWIO = FIXTURES / "aws-web.drawio"


def _walk(drawing) -> list[Box | Card]:
    return drawing.walk()


def _cards(drawing) -> dict[str, tuple[str, str]]:
    return {
        item.caption: (item.library, item.service_id)
        for item in _walk(drawing)
        if isinstance(item, Card)
    }


def _frames(drawing) -> dict[str, tuple[str, str]]:
    return {
        item.caption: (item.library, item.kind) for item in _walk(drawing) if isinstance(item, Box)
    }


def _parents(drawing) -> dict[str, str | None]:
    out: dict[str, str | None] = {}

    def visit(item, parent):
        out[item.caption] = parent
        if isinstance(item, Box):
            for child in item.children:
                visit(child, item.caption)

    for root in drawing.roots:
        visit(root, None)
    return out


def _wires(drawing) -> set[tuple[str, str, str, str]]:
    captions = {item.key: item.caption for item in _walk(drawing)}
    return {
        (
            captions[w.source],
            captions[w.target],
            w.label,
            "none" if w.plain else "both" if w.both else "dashed" if w.dashed else "forward",
        )
        for w in drawing.wires
    }


# ------------------------------------------------------------------ draw.io
def _compressed(text: str) -> str:
    """The file as draw.io writes it compressed: each page deflated, base64'd, URL-encoded."""
    import re

    def pack(match: re.Match[str]) -> str:
        model = match.group(2)
        deflater = zlib.compressobj(9, zlib.DEFLATED, -15)
        raw = deflater.compress(urllib.parse.quote(model, safe="").encode()) + deflater.flush()
        return f"{match.group(1)}{base64.b64encode(raw).decode()}</diagram>"

    return re.sub(
        r"(<diagram [^>]*>)\s*(<mxGraphModel.*?</mxGraphModel>)\s*</diagram>",
        pack,
        text,
        flags=re.DOTALL,
    )


def _png(text: str, chunk: bytes = b"tEXt") -> bytes:
    def part(kind: bytes, body: bytes) -> bytes:
        return (
            struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
        )

    header = part(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    data = part(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
    value = urllib.parse.quote(text, safe="").encode()
    # zTXt carries a compression method byte and deflated text; tEXt the text itself
    body = b"mxfile\x00\x00" + zlib.compress(value) if chunk == b"zTXt" else b"mxfile\x00" + value
    return b"\x89PNG\r\n\x1a\n" + header + part(chunk, body) + data + part(b"IEND", b"")


def test_drawio_reads_the_same_in_every_container(tmp_path: Path) -> None:
    text = DRAWIO.read_text(encoding="utf-8")
    plain = read_diagrams(DRAWIO)
    compressed = tmp_path / "packed.drawio"
    compressed.write_text(_compressed(text), encoding="utf-8")
    assert "<mxGraphModel" not in compressed.read_text(encoding="utf-8")
    png = tmp_path / "picture.drawio.png"
    png.write_bytes(_png(text))
    ztxt = tmp_path / "picture2.png"
    ztxt.write_bytes(_png(text, b"zTXt"))
    svg = tmp_path / "picture.drawio.svg"
    escaped = (
        text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
    )
    svg.write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" content="{escaped}"><g/></svg>', encoding="utf-8"
    )

    def shape(sketches):
        return [
            (
                [(s.key, s.label, s.kind, s.parent) for s in k.shapes],
                [(link.source, link.target, link.label) for link in k.links],
            )
            for k in sketches
        ]

    for other in (compressed, png, ztxt, svg):
        assert detect_format(other) == "drawio"
        assert shape(read_diagrams(other)) == shape(plain), other.name
    assert [s.title for s in plain] == ["Web tier", "Operations"]


def test_drawio_a_png_or_svg_without_a_diagram_is_refused(tmp_path: Path) -> None:
    bare = tmp_path / "shot.png"
    bare.write_bytes(_png("x")[:33] + _png("x")[-12:])
    with pytest.raises(DiagramError, match="Include a copy of my diagram"):
        read_diagrams(bare, "drawio")


def test_drawio_aws_page_draws_frames_stencils_and_lines() -> None:
    drawing = draw_sketch(read_diagrams(DRAWIO)[0])
    assert _frames(drawing) == {
        "AWS Cloud": ("aws", "cloud"),
        "us-east-1": ("aws", "region"),
        "VPC 10.0.0.0/16": ("aws", "vpc"),
        "Public subnet": ("aws", "subnet-public"),
        "Private subnet": ("aws", "subnet-private"),
    }
    cards = _cards(drawing)
    assert cards["Application"][1] == "elastic-load-balancing-application-load-balancer"
    assert cards["web-1"] == cards["web-2"] == ("aws", "ec2-instance")
    assert cards["Orders DB"] == ("aws", "rds")
    assert cards["Assets"] == ("aws", "simple-storage-service")
    assert cards["Thumbnailer"] == ("aws", "lambda-lambda-function")
    assert cards["Customers"] == ("aws", "general-users")
    parents = _parents(drawing)
    # the unlabelled group gave its Lambda to the region it sat in
    assert parents["Thumbnailer"] == "us-east-1"
    assert parents["web-1"] == "Private subnet" and parents["Private subnet"] == "VPC 10.0.0.0/16"
    card = next(i for i in _walk(drawing) if isinstance(i, Card) and i.caption == "web-2")
    assert ("owner", "team-web") in card.rows and ("tier", "frontend") in card.rows
    db = next(i for i in _walk(drawing) if isinstance(i, Card) and i.caption == "Orders DB")
    assert db.detail == "PostgreSQL 16"
    assert _wires(drawing) == {
        ("Customers", "Application", "HTTPS", "forward"),
        ("Application", "web-1", "", "forward"),
        ("Application", "web-2", "", "forward"),
        ("web-1", "Orders DB", "SQL", "dashed"),
        ("web-2", "Orders DB", "SQL", "dashed"),
        ("web-2", "Assets", "uploads", "both"),
        ("Assets", "Thumbnailer", "object created", "forward"),
    }
    assert any("text on its own" in why for why in drawing.left_out.values())
    assert any("cell e8" in note and "does not join two shapes" in note for note in drawing.notes)


def test_drawio_shapes_drawn_around_others_hold_them_and_loose_ends_snap() -> None:
    drawing = draw_sketch(read_diagrams(DRAWIO)[1])
    frames = _frames(drawing)
    assert frames["On-premises datacenter"] == ("generic", "site")
    # a rounded rectangle drawn behind Grafana holds it; its label names no frame kind
    assert frames["Monitoring zone"] == ("", "group")
    assert _parents(drawing)["Grafana"] == "Monitoring zone"
    cards = _cards(drawing)
    assert cards["Grafana"] == ("onprem", "monitoring-grafana")
    assert cards["Firewall"] == ("infragram", "firewall")
    assert cards["Artifacts"] == ("infragram", "generic-database")
    assert _wires(drawing) == {
        ("Build server", "Artifacts", "", "none"),
        ("Developers", "Build server", "push", "both"),
        ("Grafana", "Build server", "scrape", "forward"),
    }


# ------------------------------------------------------------------ Mermaid
def test_mermaid_flowchart_reads_every_node_and_link_form() -> None:
    [sketch] = read_diagrams(FIXTURES / "flowchart.mmd")
    assert sketch.title == "Checkout flow" and sketch.flow == "row" and not sketch.notes
    kinds = {s.key: s.kind for s in sketch.shapes}
    assert kinds["db"] == "database" and kinds["user"] == "ellipse" and kinds["pay"] == "hexagon"
    assert kinds["mail"] == "file"
    labels = {s.key: (s.label, s.detail) for s in sketch.shapes}
    assert labels["web"] == ("Storefront", "Next.js") and labels["user"] == ("Shopper", "")
    assert labels["worker"] == ("Fulfilment worker", "")
    backend = sketch.shape("backend")
    assert backend.container and backend.label == "Backend services" and backend.flow == "column"
    assert {s.key for s in sketch.shapes if s.parent == "backend"} == {"api", "pay", "q", "worker"}
    drawing = draw_sketch(sketch)
    assert drawing.direction == "right"
    cards = _cards(drawing)
    assert cards["Resize"] == ("aws", "lambda")
    assert cards["Stripe"] == ("infragram", "brand-stripe")
    assert cards["Orders DB"] == ("infragram", "generic-database")
    assert _wires(drawing) >= {
        ("Shopper", "CDN", "HTTPS", "forward"),
        ("Orders API", "order-events", "publishes", "forward"),
        ("order-events", "Fulfilment worker", "", "dashed"),
        ("Payment Service", "Stripe", "", "both"),
        ("Fulfilment worker", "Invoice mail", "", "none"),
        ("Fulfilment worker", "Resize", "", "forward"),
    }
    # ~~~ only spaces the picture
    assert not any(w[:2] == ("Storefront", "Stripe") for w in _wires(drawing))
    api = next(i for i in _walk(drawing) if isinstance(i, Card) and i.caption == "Orders API")
    assert ("Link", "https://example.com/orders") in api.rows


def test_mermaid_fans_chains_and_inline_labels() -> None:
    from infragram.convert.mermaid import read_mermaid

    sketch = read_mermaid(
        "graph TD\n  a & b --> c --> d\n  d -- sends to --> e\n  e == loud ==> f\n"
        "  f -. quiet .-> g\n  g <-- h\n  i[Label with (parens)] --- j",
        name="t",
    )
    links = {
        (link.source, link.target, link.label, link.direction, link.dashed) for link in sketch.links
    }
    assert links == {
        ("a", "c", "", "forward", False),
        ("b", "c", "", "forward", False),
        ("c", "d", "", "forward", False),
        ("d", "e", "sends to", "forward", False),
        ("e", "f", "loud", "forward", False),
        ("f", "g", "quiet", "forward", True),
        ("h", "g", "", "forward", False),
        ("i", "j", "", "none", False),
    }
    assert sketch.shape("i").label == "Label with (parens)"


def test_mermaid_architecture_folds_junctions() -> None:
    [sketch] = read_diagrams(FIXTURES / "architecture.mmd")
    drawing = draw_sketch(sketch)
    assert drawing.title == "Photo service"
    assert _frames(drawing) == {
        "Edge": ("", "group"),
        "AWS": ("aws", "cloud"),
        "VPC": ("aws", "vpc"),
    }
    assert _cards(drawing)["Uploader"] == ("aws", "lambda")
    assert _cards(drawing)["API"] == ("aws", "api-gateway")
    assert _wires(drawing) == {
        ("Internet", "API", "", "forward"),
        ("API", "Uploader", "", "forward"),
        ("Uploader", "Metadata", "", "none"),
        ("Uploader", "Photos", "", "none"),
    }


def test_mermaid_c4_reads_boundaries_people_and_relations() -> None:
    [sketch] = read_diagrams(FIXTURES / "c4-context.mmd")
    drawing = draw_sketch(sketch)
    assert drawing.title == "System Context diagram for Internet Banking System"
    assert _frames(drawing) == {"BankBoundary": ("", "group"), "BankBoundary2": ("", "group")}
    cards = _cards(drawing)
    assert cards["Banking Customer A"] == ("infragram", "public-users")
    assert cards["Database"] == ("infragram", "brand-postgres")
    assert cards["E-mail system"] == ("infragram", "mail-server")
    assert _parents(drawing)["Database"] == "BankBoundary2"
    wires = _wires(drawing)
    assert ("Banking Customer A", "Internet Banking System", "Uses", "both") in wires
    assert ("E-mail system", "Banking Customer A", "Sends e-mails to", "forward") in wires
    assert ("API Application", "Database", "Reads from and writes to (JDBC)", "forward") in wires


def test_mermaid_shapes_fills_and_lines_become_panels(tmp_path: Path) -> None:
    from infragram.cli.user.compose import project_from_spec

    [sketch] = read_diagrams(FIXTURES / "panels.mmd")
    shapes = {s.key: s for s in sketch.shapes}
    # ((circle)), {{hexagon}} and v11 doc are the panel's own outline
    assert shapes["customer"].outline == "ellipse"
    assert shapes["control"].outline == "hexagon"
    assert shapes["contract"].outline == "note"
    assert shapes["lb"].outline == ""
    # each <br> line under the caption stays a line
    assert shapes["customer"].detail == "HTTPS 443\npayments only when billing is enabled"
    # :::class, a classDef named for a tone, and style's fill by its hue
    assert {k: s.tone for k, s in shapes.items() if not s.container} == {
        "customer": "edge",
        "edge": "edge",
        "control": "managed",
        "lb": "edge",
        "gw": "private",
        "svc": "internal",
        "app": "private",
        "contract": "correction",
        "nogo": "blocker",
    }
    assert sketch.tones["edge"] == "public edge"
    assert sketch.tones["private"] == "private net"
    assert "correction" not in sketch.tones, "a style names no meaning for the legend"
    drawing = draw_sketch(sketch)
    cards = {i.key: i for i in drawing.walk() if isinstance(i, Card)}
    assert (cards["customer"].shape, cards["customer"].tone) == ("ellipse", "edge")
    # a panel the matcher could only guess at is a plain box; a named product keeps its icon
    assert (cards["nogo"].library, cards["nogo"].service_id) == ("infragram", "box")
    assert cards["lb"].service_id != "box"
    spec = tmp_path / "panels.py"
    text = write_spec(
        drawing, command="import:diagram panels.mmd", date="2026-11-01", filename=spec.name
    )
    assert "from infragram.nodes import Box" in text
    assert (
        "Box('Current implementation: NO-GO', 'no recorded deployment evidence').tone('blocker')"
        in text
    )
    assert ".shape('ellipse').tone('edge')" in text
    assert "    tones={'edge': 'public edge'," in text
    spec.write_text(text, encoding="utf-8")
    project = project_from_spec(spec)
    assert dict(project.presentation.tones)["blocker"] == "blocker"
    customer = next(e for e in project.topology.index().values() if e.name == "Customer")
    assert customer.attributes["shape"] == "ellipse" and customer.attributes["tone"] == "edge"


@pytest.mark.parametrize(
    ("name", "fill", "tone"),
    [
        ("blockerCell", "", "blocker"),
        ("", "#f96", "edge"),
        ("", "#9f9", "private"),
        ("", "#cce5ff", "internal"),
        ("", "#e0d0ff", "managed"),
        ("", "#ff6b6b", "blocker"),
        ("", "#eeeeee", "neutral"),
        ("", "#ffffff", ""),
        ("", "red", ""),
    ],
)
def test_a_fill_reads_as_the_tone_nearest_its_hue(name: str, fill: str, tone: str) -> None:
    from infragram.convert.mermaid import tone_of

    assert tone_of(name, fill) == tone


def test_mermaid_kinds_without_architecture_are_refused(tmp_path: Path) -> None:
    source = tmp_path / "hello.mmd"
    source.write_text("sequenceDiagram\n  Alice->>Bob: hi\n", encoding="utf-8")
    with pytest.raises(DiagramError, match="sequenceDiagram draws no architecture"):
        read_diagrams(source)


# ----------------------------------------------------------------- PlantUML
def test_plantuml_deployment_reads_keywords_braces_and_arrows() -> None:
    [sketch] = read_diagrams(FIXTURES / "deployment.puml")
    assert sketch.title == "Homelab deployment" and sketch.flow == "row"
    assert not [n for n in sketch.notes if "passed over" in n]
    drawing = draw_sketch(sketch)
    assert _frames(drawing) == {
        "k3s cluster": ("kubernetes", "cluster"),
        "media namespace": ("kubernetes", "namespace"),
    }
    parents = _parents(drawing)
    assert parents["Jellyfin"] == "media namespace" and parents["PostgreSQL"] == "k3s cluster"
    cards = _cards(drawing)
    assert cards["Family"] == ("infragram", "public-user")
    assert cards["PostgreSQL"] == ("infragram", "brand-postgres")
    assert cards["Home Assistant"] == ("infragram", "brand-home-assistant")
    assert _wires(drawing) == {
        ("Family", "Internet", "browses", "forward"),
        ("Internet", "Jellyfin", "HTTPS", "forward"),
        ("Sonarr", "PostgreSQL", "", "dashed"),
        ("Jellyfin", "NAS share", "reads media", "dashed"),
        ("Sonarr", "MQTT", "events", "forward"),
        ("Home Assistant", "MQTT", "", "forward"),
    }


def test_plantuml_cloud_library_macros_and_sprites() -> None:
    [sketch] = read_diagrams(FIXTURES / "aws.puml")
    drawing = draw_sketch(sketch)
    assert _frames(drawing) == {"cloud": ("aws", "cloud"), "Serverless VPC": ("aws", "vpc")}
    cards = _cards(drawing)
    assert cards == {
        "Public API": ("aws", "api-gateway"),
        "Orders function": ("aws", "lambda"),
        "Orders table": ("aws", "dynamodb"),
        "Receipts": ("aws", "simple-storage-service"),
        "Nightly report": ("aws", "lambda"),
    }
    fn = next(i for i in _walk(drawing) if isinstance(i, Card) and i.caption == "Orders function")
    assert fn.detail == "Python 3.12"
    assert ("Orders function", "Receipts", "receipt PDF", "dashed") in _wires(drawing)


def test_plantuml_c4_container() -> None:
    [sketch] = read_diagrams(FIXTURES / "c4-container.puml")
    drawing = draw_sketch(sketch)
    cards = _cards(drawing)
    assert cards["Customer"] == ("infragram", "public-users")
    assert cards["Event bus"] == ("onprem", "queue-kafka")
    assert cards["Database"] == ("infragram", "generic-database")
    assert cards["Single-Page App"] == ("infragram", "browser-client")
    assert ("Event bus", "Database", "Feeds", "forward") in _wires(drawing)


# --------------------------------------------------------------- Excalidraw
@pytest.mark.parametrize("name", ["shop.excalidraw", "shop.excalidraw.md"])
def test_excalidraw_scene(name: str) -> None:
    [sketch] = read_diagrams(FIXTURES / name)
    drawing = draw_sketch(sketch)
    assert _frames(drawing) == {"Production": ("generic", "environment")}
    cards = _cards(drawing)
    assert cards == {
        "Customers": ("infragram", "public-users"),
        "Orders API": ("infragram", "api-endpoint"),
        "Postgres": ("infragram", "brand-postgres"),
        "Redis cache": ("infragram", "brand-redis"),
        "Job queue": ("infragram", "message-queue"),
    }
    assert _wires(drawing) == {
        ("Orders API", "Postgres", "SQL", "forward"),
        ("Customers", "Orders API", "", "forward"),
        ("Orders API", "Job queue", "", "dashed"),
        ("Postgres", "Redis cache", "", "none"),
    }
    assert sorted(drawing.left_out.values()) == [
        "an unlabelled shape nothing links to: decoration",
        "text on its own: an annotation, not a component",
    ]


# -------------------------------------------------------------------- Visio
_VISIO = "http://schemas.microsoft.com/office/visio/2012/main"
_RELS = "http://schemas.openxmlformats.org/package/2006/relationships"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _vsdx(path: Path) -> Path:
    def shape(sid, master, x, y, w, h, text="", extra=""):
        cells = "".join(
            f'<Cell N="{n}" V="{v}"/>'
            for n, v in (("PinX", x), ("PinY", y), ("Width", w), ("Height", h))
            if v is not None
        )
        return (
            f'<Shape ID="{sid}" Type="Shape" Master="{master}">{cells}{extra}'
            + (f"<Text><cp IX='0'/>{text}</Text>" if text else "")
            + "</Shape>"
        )

    container = (
        '<Section N="User"><Row N="msvStructureType"><Cell N="Value" V="Container" U="STR"/></Row>'
        "</Section>"
    )
    connector = (
        '<Cell N="BeginX" V="0"/><Cell N="BeginY" V="0"/><Cell N="EndX" V="1"/><Cell N="EndY" V="1"/>'
        '<Cell N="EndArrow" V="13"/>'
    )
    page1 = (
        f'<PageContents xmlns="{_VISIO}"><Shapes>'
        + shape(1, 5, 4, 4, 6, 4, "Production VNet", container)
        + shape(2, 2, 2.5, 4, 0.5, 0.5, "App VM")
        + shape(3, 3, 5.5, 4, 0.5, 0.5, "Orders")
        + shape(4, 4, 9, 4, 0.6, 0.6, "")
        + shape(5, 6, 0, 0, None, None, "SQL", connector.replace('<Cell N="EndArrow" V="13"/>', ""))
        + shape(6, 6, 0, 0, None, None, "", connector)
        + shape(7, 1, 12, 12, 1, 1, "")
        + "</Shapes><Connects>"
        '<Connect FromSheet="5" FromCell="BeginX" ToSheet="2"/><Connect FromSheet="5" FromCell="EndX" ToSheet="3"/>'
        '<Connect FromSheet="6" FromCell="BeginX" ToSheet="4"/><Connect FromSheet="6" FromCell="EndX" ToSheet="2"/>'
        "</Connects></PageContents>"
    )
    masters = [
        (1, "Rectangle"),
        (2, "Azure Virtual Machine"),
        (3, "Azure SQL Database"),
        (4, "User"),
        (5, "Container 1"),
        (6, "Dynamic connector"),
    ]
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "visio/pages/pages.xml",
            f'<Pages xmlns="{_VISIO}" xmlns:r="{_R}"><Page ID="0" NameU="Page-1"><Rel r:id="rId1"/></Page>'
            f'<Page ID="1" NameU="Background" Background="1"><Rel r:id="rId2"/></Page></Pages>',
        )
        archive.writestr(
            "visio/pages/_rels/pages.xml.rels",
            f'<Relationships xmlns="{_RELS}"><Relationship Id="rId1" Target="page1.xml"/>'
            f'<Relationship Id="rId2" Target="page2.xml"/></Relationships>',
        )
        archive.writestr("visio/pages/page1.xml", page1)
        archive.writestr(
            "visio/pages/page2.xml",
            f'<PageContents xmlns="{_VISIO}"><Shapes>'
            + shape(1, 2, 1, 1, 1, 1, "Logo")
            + "</Shapes></PageContents>",
        )
        archive.writestr(
            "visio/masters/masters.xml",
            f'<Masters xmlns="{_VISIO}" xmlns:r="{_R}">'
            + "".join(
                f'<Master ID="{i}" NameU="{n}"><Rel r:id="m{i}"/></Master>' for i, n in masters
            )
            + "</Masters>",
        )
        archive.writestr(
            "visio/masters/_rels/masters.xml.rels",
            f'<Relationships xmlns="{_RELS}">'
            + "".join(f'<Relationship Id="m{i}" Target="master{i}.xml"/>' for i, _ in masters)
            + "</Relationships>",
        )
        for i, _ in masters:
            inherited = '<Cell N="LinePattern" V="2"/>' if i == 6 else ""
            archive.writestr(
                f"visio/masters/master{i}.xml",
                f'<MasterContents xmlns="{_VISIO}"><Shapes><Shape ID="5">{inherited}'
                '<Cell N="Width" V="0.5"/><Cell N="Height" V="0.5"/></Shape></Shapes></MasterContents>',
            )
    return path


def test_visio_masters_connectors_and_containers(tmp_path: Path) -> None:
    source = _vsdx(tmp_path / "estate.vsdx")
    assert detect_format(source) == "visio"
    sketches = read_diagrams(source)
    assert [s.title for s in sketches] == ["estate"]  # the background page is left out
    drawing = draw_sketch(sketches[0])
    assert _frames(drawing) == {"Production VNet": ("azure", "network")}
    cards = _cards(drawing)
    assert cards["App VM"] == ("azure", "virtual-machine")
    assert cards["Orders"] == ("azure", "sql-database")
    assert _parents(drawing)["Orders"] == "Production VNet"
    # the user's shape has no text: drawn under its component's own name
    user = next(c for c, (lib, sid) in cards.items() if sid in ("public-user", "general-user"))
    assert _wires(drawing) == {
        ("App VM", "Orders", "SQL", "dashed"),
        (user, "App VM", "", "dashed"),
    }


def test_visio_old_binary_is_refused(tmp_path: Path) -> None:
    old = tmp_path / "old.vsd"
    old.write_bytes(b"\xd0\xcf\x11\xe0")
    with pytest.raises(DiagramError, match="save it as .vsdx"):
        read_diagrams(old)


# ----------------------------------------------------------------- Markdown
def test_markdown_blocks_are_diagrams_titled_by_their_headings() -> None:
    sketches = read_diagrams(FIXTURES / "architecture-notes.md")
    assert [s.title for s in sketches] == ["Request path", "Batch jobs"]
    assert [s.format for s in sketches] == ["mermaid", "plantuml"]
    assert any("sequenceDiagram" in note for note in sketches[0].notes)
    cards = _cards(draw_sketch(sketches[0]))
    assert cards["Browser"] == ("infragram", "browser-client")
    assert cards["Redis"] == ("infragram", "brand-redis")


def test_formats_are_told_by_name_then_contents(tmp_path: Path) -> None:
    for name, text, fmt in (
        ("a.txt", "flowchart TD\n a-->b", "mermaid"),
        ("b.txt", "@startuml\na->b\n@enduml", "plantuml"),
        ("c.json", '{"type": "excalidraw", "elements": []}', "excalidraw"),
        ("d.xml", "<mxfile><diagram/></mxfile>", "drawio"),
    ):
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        assert detect_format(path) == fmt, name
    unknown = tmp_path / "e.txt"
    unknown.write_text("hello", encoding="utf-8")
    with pytest.raises(DiagramError, match="--format"):
        detect_format(unknown)


# ------------------------------------------------------------------ matching
@pytest.mark.parametrize(
    ("label", "hints", "kind", "preferred", "expected"),
    [
        (
            "",
            [Hint(provider="aws", phrase="lambda function")],
            "box",
            [],
            ("aws", "lambda-lambda-function"),
        ),
        (
            "",
            [Hint(provider="azure", phrase="function apps")],
            "box",
            [],
            ("azure", "function-apps"),
        ),
        ("", [Hint(provider="gcp", phrase="cloud run")], "box", [], ("gcp", "cloud-run")),
        ("", [Hint(provider="kubernetes", phrase="pod")], "box", [], ("kubernetes", "pod")),
        ("Orders DB (RDS)", [], "box", ["aws"], ("aws", "rds")),
        ("RDS", [], "box", [], ("aws", "rds")),
        ("Amazon S3", [], "box", [], ("aws", "simple-storage-service")),
        ("Cosmos DB", [], "box", [], ("azure", "azure-cosmos-db")),
        ("BigQuery", [], "box", [], ("gcp", "bigquery")),
        ("Postgres", [], "box", [], ("infragram", "brand-postgres")),
        ("Customer", [], "box", [], ("infragram", "public-users")),
        ("Server", [], "box", [], ("infragram", "virtual-machine")),
        ("Web Server", [], "box", [], ("infragram", "virtual-machine")),
        ("Browser", [], "box", [], ("infragram", "browser-client")),
        ("Internet", [], "box", [], ("infragram", "public-internet")),
        ("Internet Banking System", [], "box", [], ("infragram", "generic-container")),
        ("Orders", [], "database", [], ("infragram", "generic-database")),
        ("Session cache", [], "database", [], ("infragram", "generic-cache")),
        ("Someone", [], "actor", [], ("infragram", "public-user")),
    ],
)
def test_matching(label, hints, kind, preferred, expected) -> None:
    found = match_component(Shape(key="x", label=label, hints=hints, kind=kind), preferred)
    assert (found.library, found.service_id) == expected


def test_every_guess_is_a_real_shared_component() -> None:
    from infragram.convert.match import _DEFAULT, _KINDS

    for service in {s for _, s in _WORDS} | set(_KINDS.values()) | {_DEFAULT}:
        assert component_class("infragram", service), service


@pytest.mark.parametrize(
    ("label", "inside", "expected"),
    [
        ("Public subnet", {"aws": 2}, ("aws", "subnet-public")),
        ("snet-app", {"azure": 1}, ("azure", "subnet-private")),
        ("rg-prod-web", {"azure": 3}, ("azure", "resource-group")),
        ("us-east-1", {"aws": 1}, ("aws", "region")),
        ("VPC", {}, ("generic", "network")),
        ("team-a namespace", {}, ("kubernetes", "namespace")),
        ("Production", {}, ("generic", "environment")),
        ("Payments", {"aws": 1}, ("", "group")),
    ],
)
def test_frame_matching(label, inside, expected) -> None:
    from collections import Counter

    found = match_frame(Shape(key="x", label=label, container=True), Counter(inside), [])
    assert (found.library, found.kind) == expected


# -------------------------------------------------- the diagram files compose
@pytest.mark.parametrize("name", sorted(p.name for p in FIXTURES.iterdir()))
def test_every_fixture_writes_a_diagram_file_that_composes(name: str, tmp_path: Path) -> None:
    from infragram.cli.user.compose import project_from_spec

    for number, sketch in enumerate(read_diagrams(FIXTURES / name)):
        drawing = draw_sketch(sketch)
        spec = tmp_path / f"d{number}.py"
        spec.write_text(
            write_spec(
                drawing, command=f"import:diagram {name}", date="2026-09-29", filename=spec.name
            ),
            encoding="utf-8",
        )
        project = project_from_spec(spec)
        elements = project.topology.index()
        cards = [i for i in drawing.walk() if isinstance(i, Card)]
        assert sum(1 for e in elements.values() if e.component is not None) >= len(cards)
        report = write_sketch_report(
            sketch, drawing, command="import:diagram", date="2026-09-29", spec=spec.name
        )
        assert f"| Shapes read | {len(sketch.shapes)} |" in report


# ------------------------------------------------------------------- command
def test_command_writes_a_file_and_report_per_diagram(tmp_path: Path, capsys) -> None:
    from infragram.cli.user.import_diagram import import_diagram, import_drawio

    assert import_diagram([str(DRAWIO), "--list"]) == 0
    assert "Web tier" in capsys.readouterr().out
    out = tmp_path / "out"
    assert import_drawio([str(DRAWIO), "--no-export", "--output-dir", str(out)]) == 0
    assert sorted(p.name for p in out.iterdir()) == [
        "operations.import.md",
        "operations.py",
        "web-tier.import.md",
        "web-tier.py",
    ]
    assert "from infragram.nodes.frames import aws as aws_frames" in (
        out / "web-tier.py"
    ).read_text("utf-8")
    report = (out / "web-tier.import.md").read_text("utf-8")
    assert "| Shapes read | 14 |" in report and "text on its own" in report
    # a second run replaces what the first wrote; a hand-edited file is kept
    assert import_drawio([str(DRAWIO), "--no-export", "--output-dir", str(out)]) == 0
    capsys.readouterr()
    (out / "web-tier.py").write_text((out / "web-tier.py").read_text("utf-8") + "# mine\n", "utf-8")
    assert import_drawio([str(DRAWIO), "--no-export", "--output-dir", str(out)]) == 2
    assert "refusing to overwrite" in capsys.readouterr().err
    one = tmp_path / "one"
    assert (
        import_diagram(
            [str(DRAWIO), "--no-export", "--output-dir", str(one), "--page", "2", "--title", "Ops"]
        )
        == 0
    )
    assert sorted(p.name for p in one.iterdir()) == ["ops.import.md", "ops.py"]
    assert import_diagram([str(DRAWIO), "--no-export", "--title", "X"]) == 2
    assert "pick it with --page" in capsys.readouterr().err
    assert import_diagram([str(DRAWIO), "--page", "Nope", "--no-export"]) == 2


def test_command_refuses_a_file_it_cannot_read(tmp_path: Path, capsys) -> None:
    from infragram.cli.user.import_diagram import import_mermaid

    bad = tmp_path / "x.mmd"
    bad.write_text('pie\n  "a": 1\n', encoding="utf-8")
    assert import_mermaid([str(bad), "--no-export"]) == 2
    assert "draws no architecture" in capsys.readouterr().err


def test_readers_never_touch_the_network_or_the_disk_beyond_the_file() -> None:
    import inspect

    import infragram.convert as package

    for module in (
        package.drawio,
        package.mermaid,
        package.plantuml,
        package.excalidraw,
        package.visio,
    ):
        source = inspect.getsource(module)
        for word in ("urlopen", "requests", "subprocess", "socket"):
            assert word not in source, (module.__name__, word)


# -------------------------------------------- Mermaid subgraphs hold nodes declared above


def _mermaid_parents(text: str) -> dict[str, str | None]:
    return {shape.key: shape.parent for shape in read_mermaid(text, name="t").shapes}


def test_a_subgraph_holds_nodes_declared_above_it() -> None:
    parents = _mermaid_parents(
        "flowchart LR\n"
        "  user((User)) -->|HTTPS| alb[ALB]\n"
        "  alb --> api[API service]\n"
        "  subgraph vpc [VPC]\n"
        "    alb\n"
        "    api\n"
        "  end\n"
    )
    assert parents == {"user": None, "alb": "vpc", "api": "vpc", "vpc": None}


def test_declared_above_or_inside_draws_the_same() -> None:
    inside = _mermaid_parents(
        "flowchart LR\n"
        "  user((User)) -->|HTTPS| alb\n"
        "  subgraph vpc [VPC]\n"
        "    alb[ALB]\n"
        "    api[API service]\n"
        "  end\n"
        "  alb --> api\n"
    )
    above = _mermaid_parents(
        "flowchart LR\n"
        "  user((User)) -->|HTTPS| alb[ALB]\n"
        "  alb --> api[API service]\n"
        "  subgraph vpc [VPC]\n"
        "    alb\n"
        "    api\n"
        "  end\n"
    )
    assert inside == above


def test_an_inner_subgraph_keeps_its_nodes_and_a_link_after_end_moves_none() -> None:
    parents = _mermaid_parents(
        "flowchart TB\n"
        "  subgraph outer\n"
        "    subgraph inner\n"
        "      a\n"
        "    end\n"
        "    a --> b\n"
        "  end\n"
        "  a --> c\n"
    )
    assert parents["a"] == "inner"
    assert parents["inner"] == "outer"
    assert parents["b"] == "outer"
    assert parents["c"] is None


def test_a_subgraph_naming_itself_is_no_cycle() -> None:
    parents = _mermaid_parents("flowchart TB\n  subgraph s\n    s --> x\n  end\n")
    assert parents == {"s": None, "x": "s"}
