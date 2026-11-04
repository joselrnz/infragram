"""A dark picture is drawn without a browser, in the canvas's own colours.

``export:project --theme dark`` used to mean "open the editor in Chromium and
capture what it drew": a machine without a browser got the light picture and
a note, and `infragram render` had no dark at all. The static renderer draws
dark from the same tokens the page paints its canvas with
(``exports/palette.py``), so the two cannot disagree about what dark is.
"""

from __future__ import annotations

import re

import pytest

from infragram.builders.architecture import load_theme
from infragram.exports import render_project_svg
from infragram.exports.palette import ROLE_TOKENS, canvas_tokens, dark
from infragram.paths import skill_assets
from infragram.projects import CloudProject

TEMPLATE = skill_assets() / "templates" / "cloud" / "hybrid-bgp-edge.infragram.json"


@pytest.fixture(scope="module")
def project() -> CloudProject:
    return CloudProject.load(TEMPLATE)


def _colours(svg: str) -> set[str]:
    return {value.lower() for value in re.findall(r'(?:fill|stroke)="(#[0-9a-fA-F]{3,6})"', svg)}


def test_the_dark_palette_is_the_pages_own_tokens() -> None:
    tokens = canvas_tokens("dark")
    theme = dark(load_theme("onprem"))
    for role, token in ROLE_TOKENS.items():
        assert theme[role] == tokens[token], role
    # a library's own colours are the library's, on any ground
    plain = load_theme("onprem")
    assert theme["accent"] == plain["accent"] and theme["link"] == plain["link"]


def test_a_dark_picture_is_drawn_on_the_dark_canvas(project: CloudProject) -> None:
    dark_svg = render_project_svg(project, background="paper", theme="dark")
    light_svg = render_project_svg(project, background="paper", theme="light")
    tokens = canvas_tokens("dark")
    assert tokens["--canvas-bg"].lower() in dark_svg.lower()
    assert tokens["--text-canvas"].lower() in _colours(dark_svg)
    assert tokens["--text-canvas"].lower() not in _colours(light_svg)
    # and the light picture is untouched by any of this
    assert light_svg == render_project_svg(project, background="paper")


def test_a_dark_picture_carries_no_light_paper(project: CloudProject) -> None:
    """The failure this guards is a dark export on a white ground."""
    dark_svg = render_project_svg(project, background="paper", theme="dark")
    light_paper = load_theme(project.provider)["paper"].lower()
    ground = re.search(r'<rect data-export-background=""[^>]*fill="([^"]+)"', dark_svg)
    assert ground, "the picture paints its ground"
    assert ground.group(1).lower() == canvas_tokens("dark")["--canvas-bg"].lower()
    light_ground = re.search(
        r'<rect data-export-background=""[^>]*fill="([^"]+)"',
        render_project_svg(project, background="paper"),
    )
    assert light_ground and light_ground.group(1).lower() == light_paper


def test_darker_is_its_own_palette(project: CloudProject) -> None:
    darker = render_project_svg(project, background="paper", theme="darker")
    assert canvas_tokens("darker")["--canvas-bg"].lower() in darker.lower()
    assert darker != render_project_svg(project, background="paper", theme="dark")


def test_an_unknown_palette_is_refused(project: CloudProject) -> None:
    with pytest.raises(ValueError, match="unknown palette"):
        render_project_svg(project, theme="midnight")


def test_every_ink_in_a_dark_picture_stands_out_from_its_ground() -> None:
    """The same floors the canvas is held to (test_canvas_contrast.py): a
    dark picture nobody can read is not a dark picture."""

    def luminance(colour: str) -> float:
        value = colour.lstrip("#")
        channels = [int(value[i : i + 2], 16) / 255 for i in (0, 2, 4)]
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    theme = dark(load_theme("onprem"))
    ground = luminance(theme["paper"])
    for role, floor in (("ink", 4.5), ("soft", 4.5), ("muted", 3.0)):
        ink = luminance(theme[role])
        ratio = (max(ink, ground) + 0.05) / (min(ink, ground) + 0.05)
        assert ratio >= floor, f"{role} {theme[role]} on {theme['paper']} is {ratio:.2f}:1"
