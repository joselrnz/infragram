"""An export carries its own ground.

Exports used to be transparent, deliberately: a picture with no background
drops onto any page and takes its colour. For a light-only product that was
the wrong default. A transparent PNG in a dark viewer, a dark chat client or
a terminal shows dark text on black, which is what people actually saw, and
the diagram they opened looked broken rather than adaptable.

The default is now the theme's own paper -- white -- painted over the whole
viewBox including the margin. ``background="transparent"`` still asks for the
old behaviour, and a hex colour asks for anything else.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from infragram.exports import (
    DEFAULT_EXPORT_BACKGROUND,
    ExportError,
    export_project,
    finish_standalone_svg,
    render_project_svg,
    resolve_background,
)
from infragram.projects import CloudProject

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
TEMPLATE = (
    ROOT
    / "plugin/skills/infragram-architect/assets/templates/cloud/aws-site-to-site-vpn.infragram.json"
)
THREE_TIER = (
    ROOT
    / "plugin/skills/infragram-architect/assets/templates/cloud/aws-three-tier-web.infragram.json"
)
GROUND = re.compile(r'<rect data-export-background="[^"]*"([^>]*)>')


def test_the_default_is_the_theme_paper_not_transparency() -> None:
    assert DEFAULT_EXPORT_BACKGROUND == "paper"
    assert resolve_background(DEFAULT_EXPORT_BACKGROUND, "#ffffff") == "#ffffff"


@pytest.mark.parametrize("asked", ["transparent", "none", ""])
def test_transparency_is_still_available(asked: str) -> None:
    assert resolve_background(asked, "#ffffff") is None


@pytest.mark.parametrize("colour", ["#fff", "#f5f5f5", "#0F1B2A"])
def test_a_hex_colour_passes_through(colour: str) -> None:
    assert resolve_background(colour, "#ffffff") == colour


def test_a_colour_name_is_refused_rather_than_guessed() -> None:
    with pytest.raises(ExportError, match="unknown export background"):
        resolve_background("chartreuse", "#ffffff")


def test_the_ground_covers_the_whole_view_box() -> None:
    """Including the margin, so no corner of the file is clear."""
    svg = (
        '<svg viewBox="-8 48 1280 2128" xmlns="http://www.w3.org/2000/svg">'
        "<title>t</title><desc>d</desc><g/></svg>"
    )
    finished = finish_standalone_svg(svg, "#ffffff")
    match = GROUND.search(finished)
    assert match is not None, "no ground was painted"
    for attribute in ('x="-8"', 'y="48"', 'width="1280"', 'height="2128"', 'fill="#ffffff"'):
        assert attribute in match.group(1), attribute


def test_the_ground_sits_behind_the_drawing() -> None:
    """After the title and defs, before anything drawn, or it hides the picture."""
    svg = (
        '<svg viewBox="0 0 10 10" xmlns="http://www.w3.org/2000/svg">'
        '<title>t</title><desc>d</desc><defs><marker id="m"/></defs>'
        '<rect data-boundary-surface="" x="1" y="1" width="2" height="2"/></svg>'
    )
    finished = finish_standalone_svg(svg, "#ffffff")
    assert finished.index("data-export-background") > finished.index("</defs>")
    assert finished.index("data-export-background") < finished.index("data-boundary-surface")


def test_the_ground_never_lands_inside_a_node_group() -> None:
    """Every node group carries a <title> of its own. Placing the ground after
    the last closing title/desc/defs in the document put it inside the last
    group, translated with it, in every real export. It belongs after the
    root preamble and before the first drawn element."""
    svg = (
        '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" role="img">\n'
        "  <title>Estate</title>\n  <desc>Two cards.</desc>\n"
        '  <defs><marker id="m"/><style>text{font-family:x}</style></defs>\n'
        '  <g data-graph-node="a" transform="translate(10 10)"><title>A</title>'
        '<rect data-node-surface="" width="20" height="10"/></g>\n'
        '  <g data-graph-node="b" transform="translate(50 50)"><title>B</title>'
        '<rect data-node-surface="" width="20" height="10"/></g>\n</svg>'
    )
    finished = finish_standalone_svg(svg, "#ffffff")
    ground = finished.index("data-export-background")
    assert ground > finished.index("</desc>")
    assert ground > finished.index("</defs>")
    assert ground < finished.index("<g ")
    assert finished.count("data-export-background") == 1


def test_the_ground_follows_the_font_defs_when_the_document_had_none() -> None:
    """The font faces are inserted first; the ground must still come after them."""
    svg = (
        '<svg viewBox="0 0 10 10" xmlns="http://www.w3.org/2000/svg">'
        '<title>t</title><g data-graph-node="n"><title>N</title><rect width="1" height="1"/>'
        "<text font-family=\"'Inter', sans-serif\">N</text></g></svg>"
    )
    finished = finish_standalone_svg(svg, "#ffffff")
    ground = finished.index("data-export-background")
    assert "@font-face" in finished[:ground], "the faces come before the ground"
    assert ground > finished.rindex("</defs>", 0, finished.index("<g "))
    assert ground < finished.index("<g ")


def _root_preamble_end(svg: str) -> int:
    """Where the root <defs> closes; symbols inside it carry paths that draw nothing."""
    return svg.index("</defs>") + len("</defs>")


def test_a_real_static_render_puts_the_ground_before_everything_drawn() -> None:
    project = CloudProject.load(THREE_TIER)
    svg = render_project_svg(project, background="#ffffff")
    ground = svg.index("data-export-background")
    assert ground > _root_preamble_end(svg)
    drawn = re.compile(r"<path|<rect data-node|<g ")
    assert drawn.search(svg, _root_preamble_end(svg), ground) is None, (
        "a drawing element precedes the ground"
    )
    assert drawn.search(svg, ground) is not None, "the picture follows the ground"


@pytest.mark.parametrize(
    "asked,expected",
    [
        ("paper", "#ffffff"),
        ("#f5f5f5", "#f5f5f5"),
    ],
)
def test_the_static_render_reads_a_background_the_way_the_exporter_does(asked, expected) -> None:
    project = CloudProject.load(THREE_TIER)
    match = GROUND.search(render_project_svg(project, background=asked))
    assert match is not None and f'fill="{expected}"' in match.group(1)
    assert "data-export-background" not in render_project_svg(project, background="transparent")
    assert "data-export-background" not in render_project_svg(project), "None still paints nothing"
    with pytest.raises(ExportError, match="unknown export background"):
        render_project_svg(project, background="chartreuse")


def test_asking_for_nothing_paints_nothing() -> None:
    svg = '<svg viewBox="0 0 10 10" xmlns="http://www.w3.org/2000/svg"><g/></svg>'
    assert "data-export-background" not in finish_standalone_svg(svg, None)


@pytest.mark.parametrize(
    "background,expected",
    [
        ("paper", "#ffffff"),
        ("#f5f5f5", "#f5f5f5"),
    ],
)
def test_a_real_export_carries_the_ground(tmp_path: Path, background: str, expected: str) -> None:
    """End to end, through the fallback that runs without a browser."""

    def no_browser(source, output, theme=None, display=None, background=None):
        raise ExportError("no browser (simulated)")

    project = CloudProject.load(TEMPLATE)
    export_project(
        project,
        tmp_path,
        formats=("svg",),
        svg_renderer=no_browser,
        overwrite=True,
        background=background,
    )
    svg = (tmp_path / f"{project.slug}.svg").read_text(encoding="utf-8")
    match = GROUND.search(svg)
    assert match is not None, "the fallback render lost the ground"
    assert f'fill="{expected}"' in match.group(1)


def test_a_transparent_export_is_still_clear(tmp_path: Path) -> None:
    def no_browser(source, output, theme=None, display=None, background=None):
        raise ExportError("no browser (simulated)")

    project = CloudProject.load(TEMPLATE)
    export_project(
        project,
        tmp_path,
        formats=("svg",),
        svg_renderer=no_browser,
        overwrite=True,
        background="transparent",
    )
    assert "data-export-background" not in (tmp_path / f"{project.slug}.svg").read_text(
        encoding="utf-8"
    )


def test_the_svg_finisher_finds_its_tags_on_the_text_itself() -> None:
    # A dotted capital I lower-cases to two code points, so a position found
    # in the lower-cased text sliced the original one character off.
    svg = (
        '<svg viewBox="0 0 10 10"><TITLE>İstanbul İzmir İstanbul</TITLE><rect width="1" height="1"/>'
        "<text font-family=\"'Inter', sans-serif\">İzmir</text></svg>"
    )
    finished = finish_standalone_svg(svg, background="#ffffff")
    ET.fromstring(finished)  # well-formed
    assert "</TITLE>\n        <defs>" in finished
    assert finished.index("data-export-background") > finished.index("</defs>")
    assert "İstanbul İzmir İstanbul" in finished
