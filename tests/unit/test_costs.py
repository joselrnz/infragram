"""What a diagram costs, added up, and Infracost's prices joined by address.

``costs`` adds up the prices a document carries by frame and for the whole,
keeping currencies apart; ``--infracost`` writes an Infracost breakdown's
prices into the elements drawn from its resources (their ``Resource``
rows), one drawn from several priced at their sum, and keeps what the
breakdown prices but the diagram does not draw in the total.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import pytest

from infragram.paths import repo_root, skill_assets
from infragram.pricing.infracost import addresses_of, apply_breakdown, read_breakdown
from infragram.pricing.rollup import rollup
from infragram.projects import CloudProject

PLAN = repo_root() / "tests/fixtures/estate/plan-changes.json"
BREAKDOWN = repo_root() / "tests/fixtures/estate/infracost-plan-changes.json"


@pytest.fixture(scope="module")
def imported(tmp_path_factory) -> Path:
    from infragram.cli.user.import_estate import import_terraform

    folder = tmp_path_factory.mktemp("costs")
    args = [str(PLAN), "--formats", "template", "--output-dir", str(folder)]
    assert import_terraform(args) == 0
    return next(folder.glob("*.infragram.json"))


def test_the_breakdown_is_joined_by_the_address_each_element_was_drawn_from(imported) -> None:
    project = CloudProject.load(imported)
    web = next(element for element in project.topology.walk() if element.name == "web-1")
    assert addresses_of(web) == ["aws_instance.web[0]"]
    joined = apply_breakdown(project, read_breakdown(BREAKDOWN), today="2026-09-29")
    priced = dict(joined.priced)
    assert priced[web.id].monthly == 30.37 and priced[web.id].rate == "Infracost, aws_instance"
    assert web.attributes["price"]["sizing"] == {"resources": "aws_instance.web[0]"}
    assert joined.undrawn == [("aws_cloudwatch_log_group.app", 1.5, "USD")], (
        "a usage-based resource without usage costs nothing, and is not listed"
    )


def test_one_element_drawn_from_several_resources_is_priced_at_their_sum(imported) -> None:
    project = CloudProject.load(imported)
    web = next(element for element in project.topology.walk() if element.name == "web-1")
    web.attributes["table"]["rows"].append(["Resource", "aws_cloudwatch_log_group.app"])
    joined = apply_breakdown(project, read_breakdown(BREAKDOWN))
    assert dict(joined.priced)[web.id].monthly == pytest.approx(31.87)
    assert joined.undrawn == []


def test_the_rollup_adds_up_by_frame_and_keeps_currencies_apart(imported) -> None:
    project = CloudProject.load(imported)
    joined = apply_breakdown(project, read_breakdown(BREAKDOWN))
    added = rollup(project, joined.undrawn)
    assert added.totals == {"USD": 181.88}, "the drawn and the undrawn"
    frames = {frame.path[-1]: frame for frame in added.frames}
    assert frames["AWS Cloud"].monthly == {"USD": 180.38} and frames["AWS Cloud"].count == 2
    assert frames["us-west-2a"].monthly == {"USD": 30.37}
    web = next(element for element in project.topology.walk() if element.name == "web-1")
    web.attributes["price"]["currency"] = "EUR"
    assert rollup(project).totals == {"EUR": 30.37, "USD": 150.01}, "never converted"
    rows = list(csv.DictReader(io.StringIO(added.csv())))
    assert [row["kind"] for row in rows].count("component") == 2
    assert rows[-1] == {
        "kind": "diagram",
        "id": "",
        "name": "plan-changes",
        "component": "",
        "frames": "",
        "monthly": "181.88",
        "hourly": "",
        "currency": "USD",
        "source": "",
        "assumed": "",
    }


def test_the_command_prints_and_writes_the_rollup(imported, tmp_path: Path, capsys) -> None:
    from infragram.cli.user.costs import main

    target = tmp_path / "costs.csv"
    # the breakdown's prices alone: the shipped tables would price the rest too
    assert (
        main([str(imported), "--no-prices", "--infracost", str(BREAKDOWN), "--csv", str(target)])
        == 0
    )
    printed = capsys.readouterr().out
    assert printed.startswith(
        "COSTS    plan-changes: about USD 181.88 a month, 2 components priced"
    )
    assert "UNDRAWN  aws_cloudwatch_log_group.app: USD 1.50" in printed
    assert target.read_text(encoding="utf-8").startswith("kind,id,name,component,frames")
    # the import's export priced it from the shipped tables: --no-prices adds up those
    assert main([str(imported), "--no-prices"]) == 0
    assert capsys.readouterr().out.startswith("COSTS    plan-changes: about USD ")
    (tmp_path / "bad.json").write_text(json.dumps({"x": 1}), encoding="utf-8")
    assert main([str(imported), "--infracost", str(tmp_path / "bad.json")]) == 2
    assert "not an Infracost breakdown" in capsys.readouterr().err


def test_an_export_draws_infracosts_prices_into_the_page(imported, tmp_path: Path, capsys) -> None:
    from infragram.cli.user.export_project import main

    out = tmp_path / "out"
    args = [str(imported), "--formats", "template", "--output-dir", str(out)]
    assert main([*args, "--infracost", str(BREAKDOWN)]) == 0
    assert "PRICED   2 components by infracost-plan-changes.json" in capsys.readouterr().out
    written = json.loads(next(out.glob("*.infragram.json")).read_text(encoding="utf-8"))
    prices = [
        element.attributes["price"]["monthly"]
        for element in CloudProject.model_validate(written).topology.walk()
        if "price" in element.attributes
    ]
    assert sorted(prices) == [30.37, 150.01]


TEMPLATE = skill_assets() / "templates" / "cloud" / "azure-hub-spoke-landing-zone.infragram.json"


def test_side_files_never_replace_what_the_tool_did_not_write(tmp_path: Path, capsys) -> None:
    from infragram.cli.user.costs import main as costs

    mine = tmp_path / "notes.csv"
    mine.write_text("my own notes\n", encoding="utf-8")
    assert costs([str(TEMPLATE), "--csv", str(mine)]) == 2
    assert "refusing to overwrite" in capsys.readouterr().err
    assert mine.read_text(encoding="utf-8") == "my own notes\n"
    assert costs([str(TEMPLATE), "--csv", str(tmp_path)]) == 2
    assert "is a folder" in capsys.readouterr().err
    fresh = tmp_path / "costs.csv"
    assert costs([str(TEMPLATE), "--csv", str(fresh)]) == 0
    assert costs([str(TEMPLATE), "--csv", str(fresh)]) == 0, "its own file it replaces"
    assert costs([str(TEMPLATE), "--csv", str(mine), "--force"]) == 0
    assert mine.read_text(encoding="utf-8").startswith("kind,id")


def test_counts_read_as_english(tmp_path: Path, capsys) -> None:
    from infragram.pricing.rollup import _count

    assert _count(1, "component") == "1 component" and _count(2, "wire") == "2 wires"
    from infragram.cli.user.import_estate import import_terraform

    args = [str(PLAN), "--no-export", "--output-dir", str(tmp_path)]
    assert import_terraform(args) == 0
    assert "1 wire)" in capsys.readouterr().out
