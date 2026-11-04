"""The legend strip is one group, and the export crop names it."""

from __future__ import annotations

from pathlib import Path

from infragram import exports
from infragram.exports import render_project_svg
from infragram.projects import CloudProject

TEMPLATES = (
    Path(__file__).resolve().parents[2]
    / "plugin"
    / "skills"
    / "infragram-architect"
    / "assets"
    / "templates"
    / "cloud"
)


def test_the_static_picture_groups_its_legend() -> None:
    svg = render_project_svg(CloudProject.load(TEMPLATES / "aws-site-to-site-vpn.infragram.json"))
    # an empty value, not a bare attribute: the standalone SVG must stay XML
    assert svg.count('<g data-legend-strip="">') == 1
    assert "LEGEND</text>" in svg.split('<g data-legend-strip="">', 1)[1].split("</g>", 1)[0]


def test_the_capture_crops_to_the_legend_strip() -> None:
    assert "[data-legend-strip]" in exports.browser._EDITOR_PNG_CAPTURE
