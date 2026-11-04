"""``infragram diff --exit-code`` and ``--comment``: the difference for a pipeline.

``--exit-code`` answers "did anything change?" as ``git diff --exit-code``
does: 0 the same, 1 different, and 2 for every error, a picture that fails
``--verify`` included, so a pipeline never mistakes a broken run for a change.
``--comment`` writes the report as Markdown for a pull request, in the layout
``import:terraform --comment`` gives a plan: the count, a table per kind of
change, the wires. Without either flag the command does what it always did.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from infragram.author import Diagram, Edge
from infragram.nodes import reset_ids
from infragram.nodes.aws import compute, databases, security_identity
from infragram.nodes.frames import aws as f
from infragram.paths import skill_assets
from infragram.review.diff import diff_comment, diff_projects


def _version(*, secrets: bool, cache: bool, db_detail: str, extra_subnet: bool = False):
    reset_ids()
    with Diagram("Shop") as diagram:
        with f.Cloud("AWS Cloud"), f.Region("us-east-1"), f.VPC("VPC"):
            with f.PrivateSubnet("Private"):
                web = compute.EC2("Web", "t3")
                db = databases.RDS("Database", db_detail)
                store = databases.Elasticache("Cache", "redis") if cache else None
            if extra_subnet:
                with f.PrivateSubnet("Batch"):
                    compute.EC2("Worker", "t3")
            vault = security_identity.SecretsManager("Secrets", "creds") if secrets else None
        web >> Edge("SQL") >> db
        if store is not None:
            web >> Edge("sessions") >> store
        if vault is not None:
            web >> Edge("credentials") >> vault
    return diagram.to_project()


@pytest.fixture
def versions(tmp_path: Path) -> tuple[Path, Path]:
    before = tmp_path / "before.infragram.json"
    before.write_text(
        _version(secrets=True, cache=False, db_detail="db.t3", extra_subnet=True).model_dump_json(),
        encoding="utf-8",
    )
    after = tmp_path / "after.infragram.json"
    after.write_text(
        _version(secrets=False, cache=True, db_detail="db.r7g | multi-az").model_dump_json(),
        encoding="utf-8",
    )
    return before, after


def test_the_exit_code_says_whether_the_versions_differ(versions, capsys) -> None:
    from infragram.cli.user.diff import main

    before, after = versions
    assert main([str(before), str(after), "--report-only", "--exit-code"]) == 1
    assert main([str(after), str(after), "--report-only", "--exit-code"]) == 0
    assert "Diff: 0 added, 0 changed, 0 removed" in capsys.readouterr().out
    assert main([str(before), str(after), "--report-only"]) == 0, "without it: 0, as before"


def test_an_error_is_two_and_never_reads_as_a_difference(
    versions, tmp_path: Path, monkeypatch, capsys
) -> None:
    from infragram.cli.user.diff import main

    before, after = versions
    assert main([str(tmp_path / "missing.json"), str(after), "--exit-code"]) == 2
    assert "ERROR" in capsys.readouterr().err
    # a picture that fails --verify exits 1 without the flag; with it, 1 means "different"
    monkeypatch.setattr("infragram.cli.user.export_project.run_export", lambda *_: 1)
    assert main([str(after), str(after), "--output-dir", str(tmp_path)]) == 1
    assert main([str(after), str(after), "--exit-code", "--output-dir", str(tmp_path)]) == 2
    monkeypatch.setattr("infragram.cli.user.export_project.run_export", lambda *_: 0)
    assert main([str(before), str(after), "--exit-code", "--output-dir", str(tmp_path)]) == 1
    capsys.readouterr()


def test_the_comment_is_markdown_for_a_pull_request(versions, tmp_path: Path, capsys) -> None:
    from infragram.cli.user.diff import main

    before, after = versions
    comment = tmp_path / "pr" / "diff.md"
    code = main([str(before), str(after), "--report-only", "--comment", str(comment)])
    assert code == 0
    assert f"COMMENT  {comment}" in capsys.readouterr().out
    text = comment.read_text(encoding="utf-8")
    assert text.startswith("### Diagram changes: Shop\n\n**Diff: 1 added, 1 changed, 3 removed")
    assert "#### + Added (1)\n\n| Element | In |\n|---|---|\n| Cache (`cache`) | Private |" in text
    assert "| Database (`database`) | detail `db.t3` → `db.r7g \\| multi-az` |" in text, (
        "a pipe in a value is escaped, or it would end the cell"
    )
    assert "#### − Removed (3)" in text and "| Batch (`batch`, frame) | VPC |" in text
    assert (
        "| + | Web | Cache | sessions |" in text and "| − | Web | Secrets | credentials |" in text
    )
    assert "`before.infragram.json` → `after.infragram.json`" in text
    assert text.endswith("</sub>\n")


def test_the_comment_on_two_equal_versions_says_so() -> None:
    same = diff_projects(
        _version(secrets=True, cache=True, db_detail="x"),
        _version(secrets=True, cache=True, db_detail="x"),
    )
    text = diff_comment(same, picture="diff.svg")
    assert same.identical
    assert "The two versions draw the same thing." in text
    assert "![What changed, drawn](diff.svg)" in text
    assert "####" not in text, "no tables when nothing changed"


def test_a_comment_that_cannot_be_written_is_an_error(versions, tmp_path: Path, capsys) -> None:
    from infragram.cli.user.diff import main

    before, after = versions
    blocker = tmp_path / "file"
    blocker.write_text("", encoding="utf-8")
    target = blocker / "diff.md"  # a folder that is a file
    assert main([str(before), str(after), "--report-only", "--comment", str(target)]) == 2
    assert "ERROR" in capsys.readouterr().err


TEMPLATE = skill_assets() / "templates" / "cloud" / "azure-hub-spoke-landing-zone.infragram.json"


def test_a_comment_never_replaces_the_diagram(tmp_path: Path, capsys) -> None:
    from infragram.cli.user.diff import main as diff

    copy = tmp_path / "after.infragram.json"
    copy.write_bytes(TEMPLATE.read_bytes())
    before = copy.read_bytes()
    assert diff([str(TEMPLATE), str(copy), "--report-only", "--comment", str(copy)]) == 2
    assert copy.read_bytes() == before
    assert "refusing to overwrite" in capsys.readouterr().err
