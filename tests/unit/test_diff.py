"""``infragram diff``: two versions of a diagram, drawn as what changed."""

from __future__ import annotations

from pathlib import Path

from infragram.author import Diagram, Edge
from infragram.models.changes import ACTIONS
from infragram.nodes import reset_ids
from infragram.nodes.aws import compute, databases, security_identity
from infragram.nodes.frames import aws as f
from infragram.review.diff import diff_projects


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


def test_added_changed_and_removed_are_marked_on_the_second_version() -> None:
    before = _version(secrets=True, cache=False, db_detail="db.t3", extra_subnet=True)
    after = _version(secrets=False, cache=True, db_detail="db.r7g")
    difference = diff_projects(before, after)
    assert difference.added == ["Cache"]
    assert sorted(difference.removed) == ["Batch", "Secrets", "Worker"]
    assert difference.changed == [("Database", ["detail db.t3 → db.r7g"])]
    marks = {
        element.name: element.attributes.get("change")
        for element in difference.project.topology.walk()
    }
    assert (
        marks["Cache"] == "create"
        and marks["Database"] == "update"
        and marks["Secrets"] == "delete"
    )
    assert marks["Web"] is None
    assert "− Batch" in marks, "a removed frame carries the mark on its title"
    assert difference.project.presentation.notes[0].startswith(
        "Diff: 1 added, 1 changed, 3 removed"
    )


def test_wires_added_and_removed_take_the_change_colours() -> None:
    difference = diff_projects(
        _version(secrets=True, cache=False, db_detail="x"),
        _version(secrets=False, cache=True, db_detail="x"),
    )
    assert difference.wires_added == ["Web → Cache (sessions)"]
    assert difference.wires_removed == ["Web → Secrets (credentials)"]
    web = next(element for element in difference.project.topology.walk() if element.name == "Web")
    strokes = {
        target: style["stroke"] for target, style in web.attributes["editor_edge_styles"].items()
    }
    assert sorted(strokes.values()) == sorted([ACTIONS["create"].stroke, ACTIONS["delete"].stroke])


def test_the_same_document_twice_changes_nothing() -> None:
    same = diff_projects(
        _version(secrets=True, cache=True, db_detail="x"),
        _version(secrets=True, cache=True, db_detail="x"),
    )
    assert same.summary == "0 added, 0 changed, 0 removed; wires 0 added, 0 removed"


def test_the_command_reads_diagram_files_and_documents(tmp_path: Path, capsys) -> None:
    from infragram.cli.user.diff import main

    before = tmp_path / "before.infragram.json"
    before.write_text(
        _version(secrets=True, cache=False, db_detail="x").model_dump_json(), encoding="utf-8"
    )
    after = tmp_path / "after.infragram.json"
    after.write_text(
        _version(secrets=False, cache=True, db_detail="x").model_dump_json(), encoding="utf-8"
    )
    assert main([str(before), str(after), "--report-only"]) == 0
    printed = capsys.readouterr().out
    assert "+ Cache" in printed and "− Secrets" in printed
    assert (
        main([str(before), str(after), "--formats", "svg", "--output-dir", str(tmp_path / "out")])
        == 0
    )
    assert (tmp_path / "out" / "shop-diff.svg").is_file()
