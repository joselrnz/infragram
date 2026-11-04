"""The JSON Schema of an ``.infragram.json`` document ships, and stays current.

An editor pointed at it completes keys, flags a misspelt one and shows each
field's description while a document is written by hand. It is generated
from the model the package validates with; this test fails the moment the
shipped copy falls behind (regenerate it with ``infragram schema``, written
with LF endings).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from infragram.cli.user.schema import main
from infragram.paths import repo_root
from infragram.projects import CloudProject
from infragram.projects.schema import project_schema, schema_path

TEMPLATES = repo_root() / "plugin/skills/infragram-architect/assets/templates"


def test_the_shipped_schema_is_the_models() -> None:
    shipped = json.loads(schema_path().read_text(encoding="utf-8"))
    assert shipped == project_schema(), "run: infragram schema, and write it to " + str(
        schema_path()
    )
    assert b"\r\n" not in schema_path().read_bytes()


def test_every_shipped_template_and_a_current_document_validate() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    validator = jsonschema.Draft202012Validator(project_schema())
    for path in sorted(TEMPLATES.rglob("*.infragram.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert not list(validator.iter_errors(payload)), path.name
        current = json.loads(
            CloudProject.model_validate(payload).model_dump_json(exclude_none=True)
        )
        assert not list(
            validator.iter_errors({"$schema": "infragram-project.schema.json", **current})
        ), path.name
    assert list(validator.iter_errors({"schema_version": 3, "slug": "x", "titel": "typo"}))


def test_a_document_may_name_its_schema(tmp_path: Path) -> None:
    template = next(TEMPLATES.rglob("*.infragram.json"))
    payload = {
        "$schema": "./infragram-project.schema.json",
        **json.loads(template.read_text("utf-8")),
    }
    project = CloudProject.model_validate(payload)
    assert "$schema" not in project.model_dump_json()
    with pytest.raises(ValueError, match=r"\$schema must be a string"):
        CloudProject.model_validate({**payload, "$schema": 3})


def test_the_command_prints_the_schema_and_its_path(capsys) -> None:
    assert main([]) == 0
    assert json.loads(capsys.readouterr().out)["title"] == "Infragram Architect project"
    assert main(["--path"]) == 0
    assert capsys.readouterr().out.strip().endswith("infragram-project.schema.json")
