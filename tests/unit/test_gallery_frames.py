"""A frame placed from another library's gallery keeps that library's look, in both renderers.

An AWS Cloud frame in an on-premises project is AWS navy with AWS's badge on
the canvas (``_boundary_component_style``) and in the exported picture alike,
never on-premises grey with a generic glyph in one of them. Both renderers
resolve the one look (``frame_look`` in ``builders/architecture.py``), and
these hold them to it frame by frame.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from infragram.builders.architecture import load_style, load_theme
from infragram.builders.frame_style import frame_paint
from infragram.exports import render_project_html, render_project_svg
from infragram.exports.render import _scene_for
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


def _editor_frames(project: CloudProject) -> dict[str, dict]:
    html = render_project_html(project)
    match = re.search(r'<script[^>]*id="infragram-editor-state"[^>]*>(.*?)</script>', html, re.S)
    assert match
    return {frame["id"]: frame for frame in json.loads(match.group(1))["boundaries"]}


@pytest.mark.slow
@pytest.mark.parametrize(
    "path", sorted(TEMPLATES.glob("*.infragram.json")), ids=lambda path: path.name.split(".")[0]
)
def test_every_frame_is_painted_alike_by_the_editor_and_the_picture(path: Path) -> None:
    project = CloudProject.load(path)
    editor = _editor_frames(project)
    scene = _scene_for(project)
    differ = []
    for cluster in scene.root.clusters():
        if cluster is scene.root or cluster.ref not in editor:
            continue
        paint = frame_paint(
            cluster.look_style or scene.style.cluster,
            cluster.look_theme or scene.theme,
            cluster.kind,
            depth=cluster.depth,
        )
        frame = editor[cluster.ref]
        for key, static in (("stroke", paint.stroke), ("fill", paint.fill)):
            if str(static).lower() != str(frame.get(key)).lower():
                differ.append(
                    f"{cluster.label!r} ({cluster.group or 'own'}) {key}: picture {static}, editor {frame.get(key)}"
                )
    assert not differ, "\n".join(differ)


def test_a_frame_from_another_gallery_draws_in_that_gallerys_colour() -> None:
    """The case that disagreed: AWS frames inside an on-premises project."""
    project = CloudProject.load(TEMPLATES / "hybrid-bgp-edge.infragram.json")
    scene = _scene_for(project)
    aws = [cluster for cluster in scene.root.clusters() if cluster.group == "aws"]
    assert aws, "the template carries AWS frames"
    assert project.provider != "aws"
    assert all(cluster.look_style is not None for cluster in aws)
    svg = render_project_svg(project)
    cloud = next(cluster for cluster in aws if cluster.kind == "cloud")
    aws_paint = frame_paint(
        load_style("aws").cluster, load_theme("aws"), cloud.kind, depth=cloud.depth
    )
    own_paint = frame_paint(scene.style.cluster, scene.theme, cloud.kind, depth=cloud.depth)
    assert aws_paint.stroke.lower() != own_paint.stroke.lower(), (
        "the two looks differ, or this proves nothing"
    )
    border = re.search(rf'<path d="M{cloud.x},{cloud.y} [^"]*" fill="none" stroke="([^"]+)"', svg)
    assert border and border.group(1).lower() == aws_paint.stroke.lower()


def test_a_frame_of_the_projects_own_library_keeps_the_scenes_look() -> None:
    project = CloudProject.load(TEMPLATES / "aws-three-tier-web.infragram.json")
    scene = _scene_for(project)
    own = [cluster for cluster in scene.root.clusters() if cluster.group == project.provider]
    assert own
    assert all(cluster.look_style is None and cluster.look_theme is None for cluster in own)


def test_a_frame_from_a_librarys_gallery_sits_on_that_librarys_layer() -> None:
    """Credited to the project's first library, the AWS frames of an
    on-premises project sat on the on-premises layer: the inspector named the
    wrong library, and hiding or locking the AWS layer left its frames behind
    while it hid the AWS services inside them."""
    project = CloudProject.load(TEMPLATES / "hybrid-bgp-edge.infragram.json")
    assert project.provider == "onprem" and "aws" in project.provider_ids
    frames = _editor_frames(project).values()
    aws = [frame for frame in frames if frame.get("frameGroup") == "aws"]
    assert aws
    assert {frame["componentProvider"] for frame in aws} == {"aws"}
    assert {frame["layerId"] for frame in aws} == {"provider:aws"}
    own = [frame for frame in frames if frame.get("frameGroup") == "onprem"]
    assert own and {frame["layerId"] for frame in own} == {"provider:onprem"}


def test_a_core_frame_stays_with_the_projects_library() -> None:
    """The generic gallery is no library: its frames take the project's."""
    project = CloudProject.load(TEMPLATES / "zero-trust-identity.infragram.json")
    generic = [
        frame for frame in _editor_frames(project).values() if frame.get("frameGroup") == "generic"
    ]
    assert generic
    assert {frame["componentProvider"] for frame in generic} == {project.provider}


def test_a_layer_is_named_as_its_library_names_itself() -> None:
    """ "Aws" and "Onprem" were the ids title-cased; the editor names a layer
    it adds by the library's display name, and so does the document's."""
    import json as _json
    import re as _re

    from infragram.catalog import load_default_provider_registry

    registry = load_default_provider_registry()
    project = CloudProject.load(TEMPLATES / "hybrid-bgp-edge.infragram.json")
    html = render_project_html(project)
    state = _json.loads(
        _re.search(r'id="infragram-editor-state"[^>]*>(.*?)</script>', html, _re.S).group(1)
    )
    names = {layer["provider"]: layer["name"] for layer in state["layers"]}
    assert names == {"onprem": registry["onprem"].display_name, "aws": registry["aws"].display_name}
    assert names["aws"] == "AWS"
