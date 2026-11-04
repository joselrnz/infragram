"""A draw.io or Visio file that declares an entity is refused before it is parsed.

Neither format declares one, so an ENTITY, or a DOCTYPE with an internal
subset where entities live, is a mistake or an attack (an expansion that
eats memory, a reference outside the file). The DOCTYPE draw.io writes at
the top of every SVG it exports names a public DTD and nothing else, and
still reads.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest

from infragram.convert import DiagramError, read_diagrams
from infragram.convert.xmlsafe import parse
from infragram.paths import repo_root

DRAWIO = repo_root() / "tests" / "fixtures" / "diagrams" / "aws-web.drawio"

_BOMB = (
    '<?xml version="1.0"?>\n<!DOCTYPE mxfile [\n  <!ENTITY a "aaaaaaaaaa">\n'
    '  <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">\n]>\n'
    '<mxfile><diagram name="Page-1"><mxGraphModel><root><mxCell id="0"/>'
    '<mxCell id="1" value="&b;" vertex="1" parent="0"/></root></mxGraphModel>'
    "</diagram></mxfile>"
)


@pytest.mark.parametrize(
    "text",
    [
        '<!DOCTYPE x [<!ENTITY e "e">]><x>&e;</x>',
        "<!doctype x [ ]><x/>",
        '<x><!ENTITY e SYSTEM "file:///etc/passwd"></x>',
        b'<!DOCTYPE x SYSTEM "x.dtd" [<!ENTITY e "e">]><x/>',
    ],
)
def test_a_declaration_is_refused(text: str | bytes) -> None:
    with pytest.raises(ET.ParseError, match="ENTITY"):
        parse(text)


def test_a_public_doctype_without_a_subset_reads() -> None:
    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
        '"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">\n<svg xmlns="http://www.w3.org/2000/svg"/>'
    )
    assert parse(svg).tag.endswith("svg")


def test_a_drawio_file_with_entities_is_refused(tmp_path: Path) -> None:
    bomb = tmp_path / "bomb.drawio"
    bomb.write_text(_BOMB, encoding="utf-8")
    with pytest.raises(DiagramError, match="ENTITY"):
        read_diagrams(bomb)


def test_a_drawio_svg_export_with_its_doctype_still_reads(tmp_path: Path) -> None:
    text = DRAWIO.read_text(encoding="utf-8")
    escaped = (
        text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
    )
    svg = tmp_path / "picture.drawio.svg"
    svg.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE svg PUBLIC "-//W3C//DTD SVG 1.1//EN" '
        '"http://www.w3.org/Graphics/SVG/1.1/DTD/svg11.dtd">\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" content="{escaped}"><g/></svg>',
        encoding="utf-8",
    )
    assert [s.title for s in read_diagrams(svg)] == [s.title for s in read_diagrams(DRAWIO)]


def test_a_visio_part_with_entities_is_refused_as_the_files_fault(tmp_path: Path) -> None:
    vsdx = tmp_path / "bomb.vsdx"
    with zipfile.ZipFile(vsdx, "w") as archive:
        archive.writestr(
            "visio/pages/pages.xml", '<!DOCTYPE Pages [<!ENTITY a "a">]><Pages>&a;</Pages>'
        )
    with pytest.raises(DiagramError, match="ENTITY"):
        read_diagrams(vsdx)


_SUBSET = '<?xml version="1.0" encoding="{enc}"?><!DOCTYPE x [<!ENTITY e "boom">]><x>&e;</x>'


@pytest.mark.parametrize(
    ("codec", "declared"),
    [
        ("utf-16", "UTF-16"),
        ("utf-16-le", "UTF-16"),
        ("utf-16-be", "UTF-16"),
        ("utf-8-sig", "UTF-8"),
    ],
)
def test_a_declaration_is_refused_in_any_encoding(codec: str, declared: str) -> None:
    data = _SUBSET.format(enc=declared).encode(codec)
    if codec in {"utf-16-le", "utf-16-be"}:
        data = ("﻿" + _SUBSET.format(enc=declared)).encode(codec)
    with pytest.raises(ET.ParseError, match="ENTITY"):
        parse(data)


def test_a_plain_utf16_document_still_reads() -> None:
    data = '<?xml version="1.0" encoding="UTF-16"?><x a="1"><y/></x>'.encode("utf-16")
    assert parse(data).find("y") is not None


def test_a_utf16_visio_file_with_entities_is_refused(tmp_path: Path) -> None:
    """The reproduced bypass: a .vsdx whose page parts are UTF-16 with an internal subset."""
    page = (
        '<?xml version="1.0" encoding="UTF-16"?>'
        '<!DOCTYPE PageContents [<!ENTITY a "aaaaaaaaaa">]>'
        '<PageContents xmlns="http://schemas.microsoft.com/office/visio/2012/main">'
        '<Shapes><Shape ID="1" Type="Shape"><Text>&a;</Text></Shape></Shapes>'
        "</PageContents>"
    ).encode("utf-16")
    pages = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Pages xmlns="http://schemas.microsoft.com/office/visio/2012/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<Page ID="0" Name="Page-1"><Rel r:id="rId1"/></Page></Pages>'
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Target="page1.xml" '
        'Type="http://schemas.microsoft.com/visio/2010/relationships/page"/></Relationships>'
    )
    path = tmp_path / "bypass.vsdx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("visio/pages/pages.xml", pages)
        archive.writestr("visio/pages/_rels/pages.xml.rels", rels)
        archive.writestr("visio/pages/page1.xml", page)
    with pytest.raises(DiagramError, match="ENTITY"):
        read_diagrams(path)
