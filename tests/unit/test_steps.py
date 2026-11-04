"""A flow told in order: a numbered circle at the start of a wire's caption,
and a step list beside the drawing.

``Edge("push", step=1, says="A push to main starts the workflow")`` numbers a
caption; the document keeps ``step`` and ``step_text`` on the connection.
The static picture draws the circle in the caption's chip, which reaches
``render-metrics.json`` ``step.lead`` further left than its text so the
placement, the chip and the checker all count it, and draws the list right
of everything drawn. test_renderer_parity_browser.py holds the editor to the
same picture; test_steps_browser.py, the editor's save.
"""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from infragram.author import Diagram, Edge
from infragram.builders import metrics
from infragram.cli.user.checker import checker
from infragram.exports.render import render_project_svg
from infragram.models.topology import Connection
from infragram.nodes import infragram as shared
from infragram.projects import CloudProject

STEP = metrics.step()


def _pipeline(**third) -> CloudProject:
    with Diagram("Steps", "a flow told in order", slug="steps") as diagram:
        repo = shared.devops.BrandGithub("Repository")
        workflow = shared.devops.BrandGithubActions("Workflow")
        runner = shared.devops.CIRunner("Runner")
        artifact = shared.devops.SignedArtifact("Image")
        repo >> Edge("push", step=1, says="A push to main starts the workflow") >> workflow
        workflow >> Edge("runs on", step=2) >> runner
        runner >> Edge("build", **third) >> artifact
    return diagram.to_project()


def test_a_step_numbers_a_caption_and_the_document_keeps_it() -> None:
    project = _pipeline(step=3)
    steps = sorted(
        (c.step, c.step_text) for e in project.topology.walk() for c in e.connections if c.step
    )
    assert steps == [(1, "A push to main starts the workflow"), (2, None), (3, None)]
    again = CloudProject.model_validate_json(project.model_dump_json())
    assert [c.step for e in again.topology.walk() for c in e.connections] == [1, 2, 3]


def test_a_step_needs_a_caption_a_number_and_says_needs_a_step() -> None:
    with pytest.raises(ValidationError, match="numbers a caption"):
        Edge(step=1)
    with pytest.raises(ValidationError, match="1 to 99"):
        Edge("push", step=0)
    with pytest.raises(ValidationError, match="give it a step"):
        Edge("push", says="no number")
    with pytest.raises(ValidationError, match="give the wire a label"):
        Connection(target="x", step=1)


def test_the_static_picture_draws_each_circle_in_its_captions_chip_and_the_list_beside() -> None:
    svg = render_project_svg(_pipeline(step=3))
    circles = re.findall(r'<circle data-edge-step="(\d+)" cx="([-\d.]+)" cy="([-\d.]+)"', svg)
    assert [number for number, _x, _y in circles] == ["1", "2", "3"]
    numbers = re.findall(r'<text data-edge-step-number="(\d+)"[^>]*>(\d+)</text>', svg)
    assert numbers == [("1", "1"), ("2", "2"), ("3", "3")]
    # every circle stands inside a chip, left of the caption's text
    chips = [
        tuple(map(float, found))
        for found in re.findall(
            r'<rect x="([-\d.]+)" y="([-\d.]+)" width="([\d.]+)" height="([\d.]+)" rx="3"', svg
        )
    ]
    for _number, cx, cy in circles:
        cx, cy = float(cx), float(cy)
        assert any(
            x <= cx - STEP["radius"]
            and cx + STEP["radius"] <= x + width
            and y <= cy - STEP["radius"]
            and cy + STEP["radius"] <= y + height
            for x, y, width, height in chips
        ), (cx, cy)
    # the list closes right after its last row's group
    listed = re.search(r'<g data-step-list="" data-drawn-x="([\d.]+)">(.*?</g>)\s*</g>', svg, re.S)
    assert listed, "the step list"
    # each row names its step, so a click on it in the editor shows that step's wires
    assert re.findall(r'<g data-step-row="(\d+)">', listed.group(2)) == ["1", "2", "3"]
    size = f'font-size="{STEP["list_size"]:g}"'
    lines = re.findall(size + r"(?![^>]*font-weight)[^>]*>([^<]+)</text>", listed.group(2))
    assert lines == ["A push to main starts the workflow", "runs on", "build"]
    assert '<rect x="' in listed.group(2) and ">Steps</text>" in listed.group(2), (
        "a bordered panel with its heading"
    )
    width = float(re.search(r'viewBox="0 0 ([\d.]+)', svg).group(1))
    assert float(listed.group(1)) + 60 < width, "the canvas holds the list"


def test_each_cloud_marks_its_steps_its_own_way() -> None:
    """As the clouds' own drawings do: AWS numbers in Squid Ink and letters a
    second flow in dark red; Azure numbers in green circles and an outbound
    flow in blue squares; Google numbers in Blue 900 and letters a second
    flow in Green 900. A library without a convention squares its second."""
    from infragram.builders.architecture import load_theme

    marks = {
        cloud: (load_theme(cloud).step_mark(), load_theme(cloud).step_mark(second=True))
        for cloud in ("aws", "azure", "gcp", "onprem")
    }
    assert [(m.color, m.shape, m.marks) for m in marks["aws"]] == [
        ("#232f3e", "circle", "numbers"),
        ("#8b250b", "circle", "letters"),
    ]
    assert [(m.color, m.shape, m.marks) for m in marks["azure"]] == [
        ("#107c10", "circle", "numbers"),
        ("#4672c4", "square", "numbers"),
    ]
    assert [(m.color, m.shape, m.marks) for m in marks["gcp"]] == [
        ("#174ea6", "circle", "numbers"),
        ("#0d652d", "circle", "letters"),
    ]
    link = load_theme("onprem")["link"]
    assert [(m.color, m.shape) for m in marks["onprem"]] == [(link, "circle"), (link, "square")]
    assert (
        marks["gcp"][1].mark(1) == "A"
        and marks["gcp"][1].mark(26) == "Z"
        and marks["gcp"][1].mark(27) == "27"
    )


def _two_flows(theme: str, **extra) -> CloudProject:
    with Diagram("Flows", slug="two-flows", providers=(theme,)) as diagram:
        repo = shared.devops.BrandGithub("Repository")
        workflow = shared.devops.BrandGithubActions("Workflow")
        registry = shared.devops.SignedArtifact("Image")
        app = shared.devops.CIRunner("App")
        repo >> Edge("push", step=1) >> workflow
        workflow >> Edge("build", step=2) >> registry
        app >> Edge("pulls", step=1, flow="At runtime", says="The app pulls the image") >> registry
        for label, flow in extra.items():
            app >> Edge(label, step=2, flow=flow) >> repo
    return diagram.to_project()


def test_a_second_flow_is_marked_the_themes_second_way_and_listed_under_its_name() -> None:
    svg = render_project_svg(_two_flows("azure"))
    # Azure's outbound look: a blue square carrying the number
    square = re.search(
        r'<rect data-edge-step="1" data-cx="[-\d.]+" data-cy="[-\d.]+"[^>]*fill="#4672c4"/>', svg
    )
    assert square, "the second flow's badge is a blue square"
    assert len(re.findall(r'<circle data-edge-step="\d+"[^>]*fill="#107c10"', svg)) == 2
    listed = re.search(
        r'<g data-step-list="" data-drawn-x="[\d.]+">(.*?</g>)\s*</g>', svg, re.S
    ).group(1)
    assert ">At runtime</text>" in listed and ">The app pulls the image</text>" in listed
    assert '<g data-step-row="1" data-step-flow="At runtime">' in listed, (
        "a second flow's row names it"
    )
    assert (
        listed.index(">build</text>")
        < listed.index(">At runtime</text>")
        < listed.index(">The app pulls the image</text>")
    )
    # Google letters its second flow
    google = render_project_svg(_two_flows("gcp"))
    assert re.search(r'<text data-edge-step-number="1"[^>]*>A</text>', google)
    assert re.search(r'<circle data-edge-step="1"[^>]*fill="#0d652d"', google)


def test_a_second_flow_keeps_its_name_in_the_document_and_passes_the_checker() -> None:
    project = _two_flows("gcp")
    again = CloudProject.model_validate_json(project.model_dump_json())
    flows = sorted(
        (c.step_flow or "", c.step) for e in again.topology.walk() for c in e.connections if c.step
    )
    assert flows == [("", 1), ("", 2), ("At runtime", 1)]
    errors: list[str] = []
    checker().check_svg(render_project_svg(project), errors)
    assert errors == [], errors


def test_a_flow_needs_a_step_and_a_name_and_a_drawing_tells_two_flows_apart() -> None:
    with pytest.raises(ValidationError, match="give it a step too"):
        Edge("pulls", flow="At runtime")
    with pytest.raises(ValidationError, match="needs a name"):
        Edge("pulls", step=1, flow=" ")
    with pytest.raises(ValidationError, match="names the flow a step belongs to"):
        Connection(target="x", label="pulls", step_flow="At runtime")
    with pytest.raises(ValueError, match="one named second flow"):
        render_project_svg(_two_flows("aws", reads="Nightly"))


def test_a_picture_with_steps_passes_the_checker_and_reads_no_number_as_a_caption() -> None:
    svg = render_project_svg(_pipeline(step=3))
    check = checker()
    picture = check.read_picture(svg)
    assert sorted(picture.labels) and len(picture.labels) == 3
    errors: list[str] = []
    check.check_svg(svg, errors)
    assert errors == [], errors


def test_a_wire_with_no_step_draws_as_it_did() -> None:
    plain = render_project_svg(_pipeline())
    assert plain.count("data-edge-step=") == 2
    assert "data-step-list" in plain
    with Diagram("No steps", slug="no-steps") as diagram:
        (
            shared.devops.BrandGithub("Repository")
            >> Edge("push")
            >> shared.devops.BrandGithubActions("Workflow")
        )
    svg = render_project_svg(diagram.to_project())
    assert "data-edge-step" not in svg and "data-step-list" not in svg
