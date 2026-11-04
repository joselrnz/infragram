"""A frame's colour is the library's, until a dark ground swallows it.

AWS paints its cloud frame navy (#232f3e). On the dark canvas that is 1.4:1
-- a border and a title drawn where nobody can read them -- and the same
frame in the exported picture had the same problem. A colour that cannot
hold 3:1 against the ground is lifted by turning its lightness over and
keeping its hue, which leaves it recognisably the library's; a colour that
reads is left exactly as the library set it.

The lift is derived once, in ``frame_paint``, and the page carries the
result per frame (``dark`` in each boundary), so the canvas and the picture
cannot answer differently.
"""

from __future__ import annotations

import json
import re

import pytest

from infragram.builders.architecture import load_style, load_theme
from infragram.builders.frame_style import frame_paint
from infragram.catalog import load_default_provider_registry
from infragram.catalog.ink import on_dark
from infragram.exports import render_project_html
from infragram.exports.palette import canvas_tokens, dark
from infragram.paths import skill_assets
from infragram.projects import CloudProject
from infragram.themes.colour import contrast, relative_luminance

DARK_GROUND = "#141414"
FLOOR = 3.0


def _hue(colour: str) -> float:
    import colorsys

    red, green, blue = (int(colour.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hls(red, green, blue)[0]


def test_a_colour_that_reads_on_the_dark_ground_is_untouched() -> None:
    purple = load_style("aws").cluster.color_for("vpc")
    assert contrast(purple, DARK_GROUND) >= FLOOR
    assert on_dark(purple, DARK_GROUND) == purple


def test_a_colour_that_vanishes_is_lifted_and_keeps_its_hue() -> None:
    navy = "#232f3e"
    assert contrast(navy, DARK_GROUND) < FLOOR
    lifted = on_dark(navy, DARK_GROUND)
    assert contrast(lifted, DARK_GROUND) >= FLOOR
    assert abs(_hue(lifted) - _hue(navy)) < 0.02, (navy, lifted)
    assert relative_luminance(lifted) > relative_luminance(navy)


def test_anything_that_is_not_a_hex_colour_is_returned_as_it_came() -> None:
    for value in ("none", "currentColor", "rgba(0,0,0,.2)", "url(#dots)"):
        assert on_dark(value, DARK_GROUND) == value


def test_a_three_digit_hex_is_a_colour_too() -> None:
    """A skin or a frame style may write "#123"; reading it as three pairs
    raised on the empty third pair, which is a crash in an export rather
    than a colour left alone."""
    assert contrast("#123", DARK_GROUND) < FLOOR
    lifted = on_dark("#123", DARK_GROUND)
    assert contrast(lifted, DARK_GROUND) >= FLOOR
    assert on_dark("#123", DARK_GROUND) == on_dark("#112233", DARK_GROUND)
    assert on_dark("#fff", DARK_GROUND) == "#fff", "one that reads is untouched"


@pytest.mark.parametrize("provider", [p.id for p in load_default_provider_registry().providers])
def test_every_frame_a_library_draws_can_be_seen_on_the_dark_canvas(provider: str) -> None:
    style, theme = load_style(provider), dark(load_theme(provider))
    declared = getattr(style.cluster, "colors", None) or {}
    kinds = sorted(
        {*declared, "cloud", "vpc", "subnet", "region", "group", "site", "cluster", "organization"}
    )
    faint = []
    for kind in kinds:
        paint = frame_paint(style.cluster, theme, kind, depth=0)
        ratio = contrast(paint.stroke, theme["paper"])
        if ratio is not None and ratio < FLOOR:
            faint.append(f"{provider}/{kind}: {paint.stroke} is {ratio:.2f}:1")
    assert not faint, "\n".join(faint)


def test_a_light_picture_keeps_every_library_colour_exactly() -> None:
    for provider in ("aws", "azure"):
        style, theme = load_style(provider), load_theme(provider)
        for kind in ("cloud", "cluster", "vpc"):
            declared = style.cluster.color_for(kind)
            if declared and declared.startswith("#"):
                assert frame_paint(style.cluster, theme, kind).stroke == declared


def test_the_page_carries_what_the_picture_draws() -> None:
    """One derivation, two renderers: the boundary's ``dark`` look is what
    ``frame_paint`` gives on the dark palette."""
    template = skill_assets() / "templates" / "cloud" / "hybrid-bgp-edge.infragram.json"
    project = CloudProject.load(template)
    html = render_project_html(project)
    state = json.loads(
        re.search(r'id="infragram-editor-state"[^>]*>(.*?)</script>', html, re.S).group(1)
    )
    aws = next(frame for frame in state["boundaries"] if frame["name"] == "AWS Cloud")
    expected = frame_paint(load_style("aws").cluster, dark(load_theme("aws")), aws["kind"])
    assert aws["dark"]["stroke"] == expected.stroke
    assert aws["stroke"] != aws["dark"]["stroke"], "this frame is one that had to be lifted"
    assert aws["dark"]["iconUri"], "the badge is repainted for the tab it sits on"


def test_every_frame_in_a_page_can_be_seen_on_the_dark_canvas() -> None:
    """What a page carries is the difference, not a second copy of the look:
    a frame whose colour reads on the dark ground carries nothing, and the
    runtime draws it as it is. What has to hold for all of them is that the
    colour they end up drawn in can be seen."""
    ground = canvas_tokens("dark")["--canvas-bg"]
    for name in ("azure-aks-baseline", "hybrid-bgp-edge", "aws-three-tier-web"):
        template = skill_assets() / "templates" / "cloud" / f"{name}.infragram.json"
        html = render_project_html(CloudProject.load(template))
        state = json.loads(
            re.search(r'id="infragram-editor-state"[^>]*>(.*?)</script>', html, re.S).group(1)
        )
        assert state["boundaries"], name
        faint = []
        for frame in state["boundaries"]:
            drawn = (frame.get("dark") or {}).get("stroke", frame["stroke"])
            ratio = contrast(drawn, ground)
            if ratio is not None and ratio < FLOOR:
                faint.append(f"{name}: {frame['name']} is drawn {drawn}, {ratio:.2f}:1")
        assert not faint, "\n".join(faint)


def test_a_frame_that_needs_no_lift_carries_no_second_look() -> None:
    """The payload is the difference: carrying every frame's whole look again
    cost 87 KB on an AWS page, most of it a badge nobody would see change."""
    template = skill_assets() / "templates" / "cloud" / "aws-three-tier-web.infragram.json"
    html = render_project_html(CloudProject.load(template))
    state = json.loads(
        re.search(r'id="infragram-editor-state"[^>]*>(.*?)</script>', html, re.S).group(1)
    )
    carried = [frame for frame in state["boundaries"] if frame.get("dark")]
    assert carried, "the AWS cloud frame needs one"
    assert len(carried) < len(state["boundaries"]), "the rest read as they are"
    for frame in carried:
        assert "stroke" in frame["dark"], frame["name"]
