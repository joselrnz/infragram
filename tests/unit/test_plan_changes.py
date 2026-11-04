"""A plan's changes, drawn: what it adds, changes, replaces and destroys.

``import:terraform`` of a plan reads ``resource_changes`` and marks every
card with its action (``.change("create")`` in the diagram file). Both
renderers show it through what they already draw: the card's fill and
outline in the action's colour, a mark on its detail line, and the plan's
count in the band above the drawing. A resource the plan destroys is read
from ``prior_state`` and drawn too, marked destroyed.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from infragram.author import Diagram
from infragram.exports import render_project_html, render_project_svg
from infragram.models.changes import ACTIONS, action_of, combined, plan_summary
from infragram.nodes import reset_ids
from infragram.nodes.aws import compute, databases
from infragram.paths import repo_root

FIXTURE = repo_root() / "tests/fixtures/estate/plan-changes.json"


@pytest.mark.parametrize(
    ("actions", "expected"),
    [
        (["create"], "create"),
        (["update"], "update"),
        (["delete"], "delete"),
        (["delete", "create"], "replace"),
        (["create", "delete"], "replace"),
        (["no-op"], None),
        (["read"], None),
    ],
)
def test_an_action_list_reads_as_one_action(actions, expected) -> None:
    assert action_of(actions) == expected


def test_a_card_of_several_resources_takes_one_action() -> None:
    assert combined(["create", "create"]) == "create"
    assert combined(["create", None, "update"]) == "update"
    assert combined(["update", "replace"]) == "replace"
    assert combined([None, None]) is None
    assert (
        plan_summary(["create", "update", None, "delete", "create"])
        == "2 to add, 1 to change, 1 to destroy"
    )


def test_the_plan_reader_marks_every_resource_and_the_one_it_destroys() -> None:
    from infragram.terraform.readstate import read_show_json

    estate = read_show_json(FIXTURE)
    changes = {found.address: found.change for found in estate.resources}
    assert changes["aws_instance.web[0]"] == "replace"
    assert changes["aws_db_instance.legacy"] == "delete", "destroyed: read from prior_state"
    assert changes["module.vpc.aws_vpc.this[0]"] is None


def test_the_import_writes_the_changes_into_the_diagram_file(tmp_path: Path, capsys) -> None:
    from infragram.cli.user.import_estate import import_terraform

    assert (
        import_terraform(
            [str(FIXTURE), "--title", "Plan", "--no-export", "--output-dir", str(tmp_path)]
        )
        == 0
    )
    spec = (tmp_path / "plan.py").read_text(encoding="utf-8")
    assert (
        ".change('replace')" in spec and ".change('delete')" in spec and ".change('create')" in spec
    )
    assert "notes=('Plan: 2 to add, 1 to change, 1 to replace, 1 to destroy',)" in spec


def _changed():
    reset_ids()
    with Diagram("Changed", display="card") as diagram:
        compute.EC2("web", "t3").change("create")
        databases.RDS("old", "db.t3").change("delete")
        compute.EC2("kept", "t3")
    return diagram.to_project()


def test_both_renderers_paint_the_change_the_same() -> None:
    project = _changed()
    svg = render_project_svg(project)
    create, delete = ACTIONS["create"], ACTIONS["delete"]
    assert f'fill="{create.fill}" stroke="{create.stroke}"' in svg
    assert f'fill="{delete.fill}" stroke="{delete.stroke}"' in svg
    assert "+ added · t3" in svg and "− destroyed · db.t3" in svg
    page = render_project_html(project)
    state = re.search(r'id="infragram-editor-state"[^>]*>(.*?)</script>', page, re.S).group(1)
    assert f'"stroke":"{create.stroke}"' in state.replace(" ", "")
    assert '"detail":"+ added' in state.replace(": ", ":")


def test_a_hand_styled_card_keeps_its_colours_and_the_static_picture_wears_them() -> None:
    reset_ids()
    with Diagram("Styled", display="card") as diagram:
        web = compute.EC2("web").change("create")
        web.attributes["editor_style"] = {"fill": "#123456", "stroke": "#abcdef"}
    svg = render_project_svg(diagram.to_project())
    assert 'fill="#123456" stroke="#abcdef"' in svg
    assert ACTIONS["create"].stroke not in svg


def test_an_unknown_change_is_refused() -> None:
    with pytest.raises(ValueError, match="change is one of"):
        compute.EC2("web").change("destroy")


def test_a_refresh_only_plan_marks_what_drifted(tmp_path: Path) -> None:
    import json

    from infragram.terraform.readstate import read_show_json

    plan = json.loads(FIXTURE.read_text(encoding="utf-8"))
    plan["resource_changes"] = [
        {"address": "aws_instance.web[0]", "change": {"actions": ["update"]}}
    ]
    plan["resource_drift"] = [
        {"address": "aws_instance.web[0]", "change": {"actions": ["update"]}},
        {"address": "module.vpc.aws_vpc.this[0]", "change": {"actions": ["update"]}},
        {"address": "module.vpc.aws_subnet.public[0]", "change": {"actions": ["no-op"]}},
    ]
    path = tmp_path / "refresh.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    changes = {found.address: found.change for found in read_show_json(path).resources}
    assert changes["module.vpc.aws_vpc.this[0]"] == "drift"
    assert changes["aws_instance.web[0]"] == "update", "the planned action wins"
    assert changes["module.vpc.aws_subnet.public[0]"] is None
    assert plan_summary(["drift", "drift", "create"]) == "1 to add, 2 drifted"


def test_the_comment_says_the_plan_in_words(tmp_path: Path) -> None:
    from infragram.cli.user.import_estate import import_terraform

    comment = tmp_path / "comment.md"
    assert (
        import_terraform(
            [
                str(FIXTURE),
                "--title",
                "Shop",
                "--no-export",
                "--output-dir",
                str(tmp_path),
                "--comment",
                str(comment),
            ]
        )
        == 0
    )
    text = comment.read_text(encoding="utf-8")
    assert "**Plan: 2 to add, 1 to change, 1 to replace, 1 to destroy**" in text
    assert "#### \u2212 Destroyed (1)" in text and "`aws_db_instance.legacy`" in text


def test_the_ci_recipe_draws_the_plan_and_applies_nothing() -> None:
    recipe = (
        repo_root() / "plugin/skills/infragram-architect/assets/ci/terraform-plan-diagram.yml"
    ).read_text("utf-8")
    assert "terraform show -json plan.out > plan.json" in recipe
    assert "infragram import:terraform" in recipe and "--comment diagram/comment.md" in recipe
    assert "terraform apply" not in recipe
