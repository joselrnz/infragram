"""Notes stay out of new diagrams; the checker still validates legacy status ink."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

from infragram.author import Diagram
from infragram.nodes import reset_ids
from infragram.nodes.aws import compute, databases
from infragram.nodes.frames import aws as frames

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())


def _checker():
    spec = importlib.util.spec_from_file_location(
        "project_check", ROOT / "plugin/skills/infragram-architect/scripts/project_check.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _static_svg() -> str:
    from infragram.exports import render_project_html

    reset_ids()
    with Diagram("Status line", drawn="2026-09-29") as diagram:
        with frames.Cloud("AWS Cloud"):
            api = compute.EC2("api")
            db = databases.RDS("db")
            api >> db
    html = render_project_html(diagram.to_project())
    match = re.search(r"<svg[^>]*data-infragram-diagram[^>]*>.*?</svg>", html, re.S)
    assert match
    # Earlier exports printed a date here. Keep a legacy picture fixture to
    # ensure those files remain checked, without making new exports print it.
    return match.group(0).replace(
        "</defs>",
        '</defs><g data-status-block=""><text x="36" y="50" font-size="8.5">'
        "drawn 2026-09-29</text></g>",
        1,
    )


@pytest.mark.parametrize("display", ["card", "icon"])
def test_notes_are_metadata_outside_headers_and_exported_diagrams(display: str) -> None:
    from infragram.editor.shell import project_from_html
    from infragram.exports import render_project_html, render_project_svg

    reset_ids()
    with Diagram(
        "A very long document title " * 10,
        display=display,
        status="PRIVATE REVIEW NOTE",
        notes=("Long explanation outside the diagram. " * 80,),
        drawn="2026-10-03",
    ) as diagram:
        compute.EC2("api")
    project = diagram.to_project()
    html = render_project_html(project)
    visible_markup = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.S)
    assert "data-document-status" not in html
    assert "data-architecture-status" not in html
    assert "data-status-block" not in visible_markup
    assert project.presentation.status not in visible_markup
    assert project.presentation.notes[0] not in visible_markup
    assert project_from_html(html).presentation == project.presentation
    svg = render_project_svg(project)
    assert "data-status-block" not in svg
    assert "data-architecture-status" not in svg
    assert project.presentation.status not in svg
    assert project.presentation.notes[0] not in svg


def _status_errors(svg: str) -> list[str]:
    errors: list[str] = []
    _checker().check_svg(svg, errors)
    return [error for error in errors if "status line" in error]


def test_the_status_line_is_read_as_tall_as_its_glyphs() -> None:
    picture = _checker().read_picture(_static_svg())
    assert len(picture.status) == 1
    line = picture.status[0]
    assert line.bottom - line.top > 8, (
        "the box holds ascenders and descenders, not just the baseline"
    )


def test_a_whole_status_line_passes_and_a_cropped_one_fails() -> None:
    svg = _static_svg()
    assert _status_errors(svg) == []
    line = _checker().read_picture(svg).status[0]
    view = re.search(r'viewBox="(-?[\d.]+) (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)"', svg)
    assert view
    x, _y, w, h = view.groups()
    # Start the picture two units above the baseline, as the editor's crop did.
    baseline = line.bottom - (line.bottom - line.top) * 0.25 / 1.05
    cropped = svg.replace(view.group(0), f'viewBox="{x} {baseline - 2:g} {w} {h}"', 1)
    assert _status_errors(cropped) == [
        "the status line above the drawing is cut off by the viewBox"
    ]
