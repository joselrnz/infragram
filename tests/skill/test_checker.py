"""The shipped checker refuses what the package refuses.

It is the one check an agent can run without the package, so a document the
package would reject, or a picture that would run or fetch something, fails
here too; and what an export writes by default passes, matched to its
document.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

from infragram.cli.user.checker import checker
from infragram.exports import render_project_html, render_project_svg
from infragram.models.topology import ComponentRef, Connection, TopologyElement
from infragram.paths import repo_root
from infragram.projects import CloudProject

CHECK = checker()
TEMPLATE = (
    repo_root()
    / "plugin"
    / "skills"
    / "infragram-architect"
    / "assets"
    / "templates"
    / "cloud"
    / "aws-three-tier-web.infragram.json"
)


def _document(element: dict) -> dict:
    """A schema-3 document holding one element."""
    return {
        "schema_version": 3,
        "slug": "probe",
        "title": "Probe",
        "description": "A probe.",
        "kind": "single-cloud",
        "providers": [{"id": "aws", "enabled": True}],
        "default_library": "aws",
        "layers": [{"id": "provider:aws", "name": "AWS", "kind": "provider", "provider": "aws"}],
        "topology": {"id": "root", "name": "Probe", "type": "group", "children": [element]},
    }


def _errors(element: dict) -> list[str]:
    errors: list[str] = []
    CHECK.check_project(_document(element), errors)
    return errors


def test_the_checker_knows_exactly_the_keys_the_models_accept() -> None:
    assert set(TopologyElement.model_fields) == CHECK.ELEMENT_KEYS
    assert set(Connection.model_fields) == CHECK.CONNECTION_KEYS
    assert set(ComponentRef.model_fields) == CHECK.COMPONENT_KEYS


def test_a_misspelt_key_is_refused_with_the_nearest_real_one() -> None:
    errors = _errors({"id": "web", "name": "Web", "type": "ec2", "conections": []})
    assert any("unknown key 'conections' (did you mean 'connections'?)" in e for e in errors), (
        errors
    )
    errors = _errors(
        {
            "id": "web",
            "name": "Web",
            "type": "ec2",
            "connections": [{"target": "web", "lable": "x"}],
        }
    )
    assert any("unknown key 'lable' (did you mean 'label'?)" in e for e in errors), errors


def test_corner_badges_load_and_the_retired_sides_are_refused() -> None:
    assert not [
        e
        for e in _errors({"id": "web", "name": "Web", "type": "ec2", "badges": []})
        if "badges" in e
    ]
    corner = {
        "icon": "network-security-groups",
        "collection": "azure",
        "label": "nsg-web",
        "side": "corner",
    }
    assert not [
        e
        for e in _errors({"id": "snet", "name": "Snet", "type": "subnet", "badges": [corner]})
        if "badges" in e
    ]
    for badge in ({"icon": "network-security-groups"}, {**corner, "side": "top"}):
        errors = _errors({"id": "snet", "name": "Snet", "type": "subnet", "badges": [badge]})
        assert any("badges[0]: marks on a frame's edge are no longer drawn" in e for e in errors), (
            errors
        )


def test_schema_three_gets_the_provider_and_layer_checks() -> None:
    errors = _errors(
        {
            "id": "vm",
            "name": "VM",
            "type": "vm",
            "layer_id": "provider:missing",
            "component": {"provider": "azure", "service_id": "virtual-machine"},
        }
    )
    assert any("'azure' is not installed in this project" in e for e in errors), errors
    assert any("unknown layer 'provider:missing'" in e for e in errors), errors


_SVG = '<svg xmlns="http://www.w3.org/2000/svg" data-infragram-diagram="true" viewBox="0 0 10 10">{}</svg>'


@pytest.mark.parametrize(
    ("markup", "safe"),
    [
        ('<image href="data:image/svg+xml;base64,AAAA"/>', True),
        ('<image href="data:image/png;base64,AAAA"/>', True),
        ('<rect fill="url(#gradient)"/>', True),
        ('<use href="data:image/svg+xml;base64,AAAA"/>', False),
        ('<a href="data:text/html;base64,AAAA"><rect/></a>', False),
        ('<a href="&#106;avascript:alert(1)"><rect/></a>', False),
        ('<a href="java&#9;script:alert(1)"><rect/></a>', False),
        ('<rect style="fill:url(https://example.test/beacon.png)"/>', False),
        ('<style>@import "https://example.test/a.css";</style>', False),
    ],
)
def test_a_picture_that_runs_or_fetches_is_refused(markup: str, safe: bool) -> None:
    errors: list[str] = []
    CHECK._check_markup_safety(_SVG.format(markup), errors)
    assert (errors == []) is safe, errors


def _png(path: Path, width: int, height: int) -> Path:
    header = struct.pack(">II", width, height) + bytes((8, 2, 0, 0, 0))
    path.write_bytes(CHECK.PNG_SIGNATURE + struct.pack(">I", 13) + b"IHDR" + header + b"\0" * 4)
    return path


def test_a_png_is_read_as_a_png(tmp_path: Path) -> None:
    ok, message = CHECK.check_path(_png(tmp_path / "picture.png", 3, 2))
    assert ok and "3 x 2 px" in message, message
    fake = tmp_path / "fake.png"
    fake.write_text("not an image", encoding="utf-8")
    ok, message = CHECK.check_path(fake)
    assert not ok and "not a PNG" in message, message


def test_a_folder_stands_for_the_files_in_it(tmp_path: Path, capsys) -> None:
    project = CloudProject.load(TEMPLATE)
    (tmp_path / f"{project.slug}.html").write_text(render_project_html(project), encoding="utf-8")
    (tmp_path / f"{project.slug}.svg").write_text(render_project_svg(project), encoding="utf-8")
    _png(tmp_path / f"{project.slug}.png", 4, 4)
    (tmp_path / "notes.md").write_text("not checked", encoding="utf-8")
    assert CHECK.main([str(tmp_path)]) == 0
    printed = capsys.readouterr().out
    assert printed.count("OK ") == 3, printed
    # A picture finds its document through the page beside it: an export
    # writes the page by default and the document file only when asked.
    # (The comparison itself runs on the editor-drawn SVG an export writes.)
    found = CHECK._sibling_project(tmp_path / f"{project.slug}.svg")
    assert found is not None and found["slug"] == project.slug
    empty = tmp_path / "empty"
    empty.mkdir()
    assert CHECK.main([str(empty)]) == 1


def test_help_is_help(capsys) -> None:
    with pytest.raises(SystemExit) as exited:
        CHECK.main(["--help"])
    assert exited.value.code == 0
    assert "infragram check" in capsys.readouterr().out
