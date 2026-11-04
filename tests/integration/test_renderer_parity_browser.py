"""The static picture is the editor's picture.

Every exported SVG and PNG is drawn by the editor runtime in Chromium. The
static renderer draws the same document without a browser: it is what an
agent with no Chromium gets, the picture every page carries before its
script runs, and the one the golden gate locks. The two are separate
implementations, and they had drifted -- detail text half a point apart,
cards two pixels off the editor's grid, a detour taken over a card where
the export took it under, captions in another size and on the other side of
their wire. This holds them to one picture, for every shipped template in
both looks: the same components on the same boxes, the same frames, every
wire along the same corners, every line of a card's text and every glyph in
the same place and type, every frame title, and every caption where the
editor puts it.
"""

from __future__ import annotations

import html
import os
import re
from pathlib import Path

import pytest

from infragram.cli.user.checker import checker
from infragram.exports import extract_svg, playwright_svg_renderer, render_project_html
from infragram.exports.render import look_variant
from infragram.projects import CloudProject

pytestmark = pytest.mark.skipif(
    os.environ.get("INFRAGRAM_RUN_BROWSER_TESTS") != "1",
    reason="browser suite; set INFRAGRAM_RUN_BROWSER_TESTS=1",
)

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
TEMPLATES = sorted(
    (ROOT / "plugin" / "skills" / "infragram-architect" / "assets" / "templates" / "cloud").glob(
        "*.infragram.json"
    )
)
#: Coordinates agree to a twentieth of a pixel; the two print floats differently.
TOLERANCE = 0.05
CHECK = checker()
_STATIC_LINKS = re.compile(r'<g data-static-link-layer="true">(.*?)</g>', re.S)
_CAPTION = re.compile(
    r'<g data-edge-label="[^"]*"[^>]*data-label-x="([-\d.e]+)" '
    r'data-label-y="([-\d.e]+)"[^>]*>(.*?)</g>',
    re.S,
)
_ARTWORK = re.compile(r"<(?:image|use)\b[^>]*>")


def _pictures(template: Path | CloudProject, look: str, scratch: Path) -> tuple[str, str]:
    """(static, editor) pictures of one template (or project) in one look."""
    project = template if isinstance(template, CloudProject) else CloudProject.load(template)
    variant = project if look == project.presentation.display else look_variant(project, look)
    html = render_project_html(variant)
    page = scratch / f"{project.slug}-{look}.html"
    page.write_text(html, encoding="utf-8", newline="\n")
    out = scratch / f"{project.slug}-{look}.svg"
    playwright_svg_renderer(page, out, theme="light", display=None)
    return extract_svg(html), out.read_text(encoding="utf-8")


def _text(raw: str, body: str, dx: float = 0.0, dy: float = 0.0) -> tuple:
    attrs = CHECK._attrs(raw)
    # the text as drawn: the static picture writes an apostrophe as &#x27;,
    # the editor as itself, and both draw the same
    return (
        html.unescape(CHECK._TAG.sub("", body)).strip(),
        float(attrs.get("x", 0)) + dx,
        float(attrs.get("y", 0)) + dy,
        attrs.get("font-size"),
        attrs.get("font-family", "").split(",")[0].strip("'\" "),
        attrs.get("font-weight", "400"),
        attrs.get("text-anchor", "start"),
    )


def _node_marks(svg: str, static: bool) -> dict[str, list[tuple]]:
    """Each node's lines of text and its artwork, in canvas coordinates."""
    marks: dict[str, list[tuple]] = {}
    groups = (
        [
            (node_id, 0.0, 0.0, body)
            for _i, _e, node_id, _d, body in CHECK._STATIC_NODE_GROUP.findall(svg)
        ]
        if static
        else [
            (node_id, float(dx), float(dy), body)
            for _h, node_id, _d, dx, dy, body in CHECK._NODE_GROUP.findall(svg)
        ]
    )
    for node_id, dx, dy, body in groups:
        rows = [_text(raw, text, dx, dy) for raw, text in CHECK._TEXT.findall(body)]
        for tag in _ARTWORK.findall(body):
            attrs = CHECK._attrs(tag)
            rows.append(
                (
                    "artwork",
                    float(attrs.get("x", 0)) + dx,
                    float(attrs.get("y", 0)) + dy,
                    attrs.get("width"),
                    attrs.get("height"),
                )
            )
        marks[node_id] = sorted(rows, key=lambda row: (row[0], round(row[1]), round(row[2])))
    return marks


def _frame_titles(svg: str, static: bool) -> list[tuple]:
    if static:
        layer = CHECK._STATIC_CLUSTER_LAYER.search(svg)
        bodies = [layer.group(1)] if layer else []
    else:
        bodies = [body for _id, body in CHECK._BOUNDARY_GROUP.findall(svg)]
    titles = [_text(raw, text) for body in bodies for raw, text in CHECK._TEXT.findall(body)]
    return sorted(titles, key=lambda row: (row[0], round(row[1]), round(row[2])))


def _captions(svg: str, static: bool) -> list[tuple]:
    if static:
        layer = _STATIC_LINKS.search(svg)
        rows = [
            _text(raw, text)
            for raw, text in CHECK._TEXT.findall(layer.group(1) if layer else "")
            if "data-edge-step-number" not in raw
        ]
    else:
        rows = []
        for x, y, body in _CAPTION.findall(svg):
            # the text's own offset in the caption's group: a step's circle
            # comes first beside a vertical wire, so its text starts after it
            content, dx, dy, *rest = _text(*CHECK._TEXT.findall(body)[0])
            rows.append((content, float(x) + dx, float(y) + dy, *rest))
    return sorted(rows, key=lambda row: (row[0], round(row[1]), round(row[2])))


def _wires(picture) -> list[list[tuple[float, float]]]:
    return sorted(
        ([(x, y) for x, y in edge["points"]] for edge in picture.edges),
        key=lambda points: [(round(x), round(y)) for x, y in points],
    )


def _same(a, b) -> bool:
    """Equal, with numbers allowed the tolerance."""
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, float) or isinstance(b, float):
        return (
            isinstance(a, (int, float)) and isinstance(b, (int, float)) and abs(a - b) <= TOLERANCE
        )
    return a == b


def _box(box) -> tuple[float, float, float, float]:
    return box.left, box.top, box.right, box.bottom


def _mismatch(what: str, here: list, there: list) -> list[str]:
    """What differs between two sorted lists, pair by pair, then any left over."""
    if _same(here, there):
        return []
    pairs = [(a, b) for a, b in zip(here, there, strict=False) if not _same(a, b)][:2]
    lines = [f"{what}: {a} here, {b} in the editor" for a, b in pairs]
    if len(here) != len(there):
        lines.append(f"{what}: {len(here)} here, {len(there)} in the editor")
    return lines


# a step's badge: a circle, or a square (a second flow on Azure) whose centre it carries
_STEP_CIRCLE = re.compile(
    r'<(?:circle|rect) data-edge-step="(\d+)" (?:data-)?cx="([-\d.e]+)" (?:data-)?cy="([-\d.e]+)"'
)
_STEP_LIST = re.compile(r'<g data-step-list="" data-drawn-x="([-\d.e]+)"([^>]*)>')


def _steps(svg: str, static: bool) -> list[tuple[int, float, float]]:
    """Every step circle, where it stands on the canvas: the editor draws its
    circle inside the caption's group, translated to the caption."""
    if static:
        layer = _STATIC_LINKS.search(svg)
        found = [
            (int(n), float(x), float(y))
            for n, x, y in _STEP_CIRCLE.findall(layer.group(1) if layer else "")
        ]
    else:
        found = [
            (int(n), float(gx) + float(x), float(gy) + float(y))
            for gx, gy, body in _CAPTION.findall(svg)
            for n, x, y in _STEP_CIRCLE.findall(body)
        ]
    return sorted(found)


def _differences(static: str, editor: str) -> list[str]:
    s, e = CHECK.read_picture(static), CHECK.read_picture(editor)
    problems = []
    if set(s.nodes) != set(e.nodes):
        problems.append(f"components differ: {sorted(set(s.nodes) ^ set(e.nodes))}")
    problems += [
        f"{node_id}: box {_box(s.nodes[node_id])} here, {_box(e.nodes[node_id])} in the editor"
        for node_id in sorted(set(s.nodes) & set(e.nodes))
        if not _same(_box(s.nodes[node_id]), _box(e.nodes[node_id]))
    ]
    problems += _mismatch(
        "frame",
        sorted(_box(box) for box in s.frames.values()),
        sorted(_box(box) for box in e.frames.values()),
    )
    problems += _mismatch("wire", _wires(s), _wires(e))
    marks = _node_marks(static, True), _node_marks(editor, False)
    problems += [
        f"{node_id}: text {marks[0].get(node_id)} here, {marks[1].get(node_id)} in the editor"
        for node_id in sorted(set(marks[0]) | set(marks[1]))
        if not _same(marks[0].get(node_id), marks[1].get(node_id))
    ]
    problems += _mismatch("frame title", _frame_titles(static, True), _frame_titles(editor, False))
    problems += _mismatch("caption", _captions(static, True), _captions(editor, False))
    problems += _mismatch("step", _steps(static, True), _steps(editor, False))
    return problems


@pytest.mark.parametrize("look", ["card", "icon"])
@pytest.mark.parametrize(
    "template", TEMPLATES, ids=lambda path: path.name.removesuffix(".infragram.json")
)
def test_the_static_picture_is_the_editors(template: Path, look: str, tmp_path: Path) -> None:
    static, editor = _pictures(template, look, tmp_path)
    problems = _differences(static, editor)
    assert not problems, f"{template.name} [{look}]:\n  " + "\n  ".join(problems)


@pytest.mark.parametrize("look", ["card", "icon"])
# entra: seven sign-in steps and two of the setup, in Azure's blue squares
@pytest.mark.parametrize("cloud", ["aws", "azure", "gcp", "entra"])
def test_a_flow_told_in_steps_draws_the_same_in_both(cloud: str, look: str, tmp_path: Path) -> None:
    """A wire's step circle sits in its caption's chip in both renderers, and
    the step list stays where the static picture set it, right of the
    drawing: the editor moves it only when its content grows past it."""
    from infragram.cli.user.compose import project_from_spec

    project = project_from_spec(ROOT / "plugin" / "examples" / f"{cloud}_github_actions_oidc.py")
    static, editor = _pictures(project, look, tmp_path)
    problems = _differences(static, editor)
    # nine: eight of the pipeline and one at runtime, or seven of the sign-in and two of the setup
    assert len(_steps(static, True)) == 9, _steps(static, True)
    drawn = _STEP_LIST.search(static)
    exported = _STEP_LIST.search(editor)
    assert drawn and exported and drawn.group(1) == exported.group(1), (drawn, exported)
    assert "transform" not in exported.group(2), exported.group(0)
    assert not problems, f"{cloud} [{look}]:\n  " + "\n  ".join(problems)


@pytest.mark.parametrize("look", ["card", "icon"])
def test_twin_wires_whose_lane_is_blocked_draw_the_same_in_both(look: str, tmp_path: Path) -> None:
    """The bot's two wires to the vault join the same two cards, and the lane
    between them runs through the git server: the editor drops the lane and
    routes both around it, and the static picture has to do the same, or it
    draws them through the card the editor goes around."""
    from infragram.cli.user.compose import project_from_spec

    project = project_from_spec(ROOT / "plugin" / "examples" / "selfhosted_cicd_oidc.py")
    static, editor = _pictures(project, look, tmp_path)
    errors: list[str] = []
    CHECK.check_svg(static, errors, project.model_dump(mode="json"))
    assert not errors, errors
    problems = _differences(static, editor)
    assert not problems, f"selfhosted_cicd_oidc [{look}]:\n  " + "\n  ".join(problems)


@pytest.mark.parametrize("look", ["card", "icon"])
def test_wires_go_around_frames_they_have_nothing_to_do_with_in_both(
    look: str, tmp_path: Path
) -> None:
    """The private endpoints reach Redis, Storage and Key Vault past the
    operations group, which holds none of them: both renderers pay for each
    border a wire crosses of such a frame, take the lanes beside it, and
    draw the same way around."""
    from infragram.cli.user.compose import project_from_spec

    project = project_from_spec(ROOT / "plugin" / "examples" / "azure_web_app_front_door.py")
    static, editor = _pictures(project, look, tmp_path)
    problems = _differences(static, editor)
    assert not problems, f"azure_web_app_front_door [{look}]:\n  " + "\n  ".join(problems)
