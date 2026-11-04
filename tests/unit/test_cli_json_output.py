"""``--json`` on ``diff``, ``check:policy``, ``costs`` and ``views``: one JSON
document on stdout, for CI and agents.

Each carries the facts its text report prints, under snake_case keys, with
lists sorted where their order means nothing, and stdout holds the document
alone: whatever else the command says (the files an export wrote, a price
fetched, a CSV written) goes to stderr. The exit status is the one the text
report gives.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from infragram.author import Diagram, Edge
from infragram.nodes import reset_ids
from infragram.nodes.aws import compute, databases, security_identity
from infragram.nodes.frames import aws as f
from infragram.paths import skill_assets


def _parsed(capsys) -> tuple[dict, str]:
    """The JSON document stdout holds (json.loads refuses anything beside it), and stderr."""
    captured = capsys.readouterr()
    return json.loads(captured.out), captured.err


# ------------------------------------------------------------------- diff
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
        _version(secrets=False, cache=True, db_detail="db.r7g").model_dump_json(), encoding="utf-8"
    )
    return before, after


def test_diff_json_lists_every_change_with_ids_and_values(versions, capsys) -> None:
    from infragram.cli.user.diff import main

    before, after = versions
    assert main([str(before), str(after), "--report-only", "--json"]) == 0
    report, _ = _parsed(capsys)
    assert report["identical"] is False
    assert report["summary"] == "1 added, 1 changed, 3 removed; wires 1 added, 1 removed"
    assert report["counts"] == {
        "added": 1,
        "changed": 1,
        "removed": 3,
        "wires_added": 1,
        "wires_removed": 1,
    }
    assert [item["id"] for item in report["added"]] == ["cache"]
    assert report["added"][0]["parent"] == "private"
    (changed,) = report["changed"]
    assert changed["id"] == "database" and changed["name"] == "Database"
    assert changed["fields"] == [{"field": "detail", "before": "db.t3", "after": "db.r7g"}]
    assert [item["id"] for item in report["removed"]] == ["batch", "secrets", "worker"], "by id"
    frames = {item["id"]: item["is_frame"] for item in report["removed"]}
    assert frames == {"batch": True, "secrets": False, "worker": False}, "a frame's mark: its title"
    assert report["wires_added"] == [
        {
            "source": "web",
            "source_name": "Web",
            "target": "cache",
            "target_name": "Cache",
            "label": "sessions",
        }
    ]
    assert report["wires_removed"][0]["target"] == "secrets"


def test_diff_json_keeps_stdout_for_the_document_while_it_draws(
    versions, tmp_path: Path, capsys
) -> None:
    from infragram.cli.user.diff import main

    before, after = versions
    out = tmp_path / "out"
    args = [str(after), str(after), "--json", "--formats", "svg", "--output-dir", str(out)]
    assert main(args) == 0
    assert (out / "shop-diff.svg").is_file(), "--json still draws"
    report, err = _parsed(capsys)
    assert report["identical"] is True and report["added"] == [] and report["changed"] == []
    assert "shop-diff.svg" in err, "what the export wrote is said on stderr"


# ----------------------------------------------------------- check:policy
RISKY = """\
from infragram.author import Diagram, Edge
from infragram.nodes import infragram as shared
from infragram.nodes.aws.compute import EC2
from infragram.nodes.aws.databases import RDS
from infragram.nodes.frames import aws

with Diagram("Risky", slug="risky"):
    internet = shared.identity.PublicUsers("Internet")
    with aws.Cloud("AWS Cloud"), aws.VPC("VPC"):
        with aws.PublicSubnet("Public"):
            exposed = RDS("Exposed DB")
        with aws.PrivateSubnet("Private"):
            app = EC2("App server")
    internet >> Edge("SSH :22") >> app
"""
TRIVY = {
    "Results": [
        {
            "Target": "main.tf",
            "Misconfigurations": [
                {
                    "AVDID": "AVD-AWS-0107",
                    "Title": "An ingress security group rule allows traffic from /0.",
                    "Severity": "CRITICAL",
                    "Status": "FAIL",
                    "CauseMetadata": {"Resource": "aws_security_group.web", "StartLine": 14},
                }
            ],
        }
    ]
}


@pytest.fixture
def risky(tmp_path: Path) -> Path:
    path = tmp_path / "risky.py"
    path.write_text(RISKY, encoding="utf-8")
    return path


def test_policy_json_names_the_element_and_keeps_the_exit_status(risky: Path, capsys) -> None:
    from infragram.cli.user.check_policy import main

    assert main([str(risky), "--json"]) == 0
    report, _ = _parsed(capsys)
    assert report["verdict"] == "warn" and report["strict"] is False
    assert report["total"] == 3 and report["by_severity"] == {"warning": 3}
    assert set(report["rules"]) >= {"database-in-public-subnet", "admin-port-open-to-internet"}
    assert report["sources"] == [
        {
            "path": str(risky),
            "kind": "diagram",
            "status": "read",
            "scanner": None,
            "findings": 3,
            "note": "",
        }
    ]
    rules = [(item["rule"], item["element_id"]) for item in report["findings"]]
    assert rules == sorted(rules), "findings are sorted"
    exposed = next(i for i in report["findings"] if i["rule"] == "database-in-public-subnet")
    assert exposed["element_id"] == "exposed-db" and exposed["element_name"] == "Exposed DB"
    assert exposed["source"] == "diagram" and exposed["file"] is None
    assert main([str(risky), "--json", "--strict"]) == 1
    assert _parsed(capsys)[0]["verdict"] == "fail"


def test_policy_json_carries_the_scanners_resource_file_and_line(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    from infragram.cli.user.check_policy import main

    monkeypatch.setattr("shutil.which", lambda name: f"/bin/{name}" if name == "trivy" else None)
    monkeypatch.setattr(
        "subprocess.run",
        lambda command, **_: subprocess.CompletedProcess(command, 1, json.dumps(TRIVY), ""),
    )
    scanned, empty = tmp_path / "tf", tmp_path / "other"
    scanned.mkdir()
    empty.mkdir()
    assert main([str(scanned), "--json"]) == 0
    report, _ = _parsed(capsys)
    assert report["sources"][0]["status"] == "scanned"
    assert report["sources"][0]["scanner"] == "trivy"
    (finding,) = report["findings"]
    assert finding["source"] == "trivy" and finding["rule"] == "AVD-AWS-0107"
    assert finding["severity"] == "critical" and finding["element_id"] is None
    assert (finding["resource"], finding["file"], finding["line"]) == (
        "aws_security_group.web",
        "main.tf",
        14,
    )
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert main([str(empty), "--json"]) == 0
    report, _ = _parsed(capsys)
    assert report["verdict"] == "ok" and report["findings"] == []
    assert (
        report["sources"][0]["status"] == "skipped" and "no scanner" in report["sources"][0]["note"]
    )


def test_policy_json_error_is_two_with_nothing_on_stdout(tmp_path: Path, capsys) -> None:
    from infragram.cli.user.check_policy import main

    assert main([str(tmp_path / "missing.infragram.json"), "--json"]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and "ERROR" in captured.err


# ------------------------------------------------------------------ costs
@pytest.fixture
def priced(tmp_path: Path) -> Path:
    reset_ids()
    with Diagram("Priced shop") as diagram:
        with f.Cloud("AWS Cloud"), f.VPC("VPC"):
            compute.EC2("Web", "t3")
            databases.RDS("Database", "db.t3")
        compute.EC2("Edge box", "t3")
    project = diagram.to_project()
    index = project.topology.index()
    index["web"].attributes["price"] = {
        "monthly": 30.37,
        "hourly": 0.0416,
        "currency": "USD",
        "source": "AWS price list",
        "assumed": ["tenancy", "os"],
    }
    index["database"].attributes["price"] = {"monthly": 150.0, "currency": "USD", "source": "x"}
    index["edge-box"].attributes["price"] = {"monthly": 12.5, "currency": "EUR", "source": "y"}
    path = tmp_path / "priced.infragram.json"
    path.write_text(project.model_dump_json(), encoding="utf-8")
    return path


def test_costs_json_adds_up_by_frame_and_currency(priced: Path, tmp_path: Path, capsys) -> None:
    from infragram.cli.user.costs import main

    target = tmp_path / "costs.csv"
    assert main([str(priced), "--json", "--csv", str(target)]) == 0
    report, err = _parsed(capsys)
    assert report["title"] == "Priced shop" and report["priced"] == 3
    assert report["totals"] == {"EUR": 12.5, "USD": 180.37}, "currencies apart, never converted"
    assert list(report["totals"]) == ["EUR", "USD"], "sorted by currency"
    cloud, vpc = report["frames"]
    assert (cloud["frame_id"], cloud["level"], cloud["path"]) == ("aws-cloud", 0, ["AWS Cloud"])
    assert (vpc["name"], vpc["level"], vpc["monthly"], vpc["count"]) == (
        "VPC",
        1,
        {"USD": 180.37},
        2,
    )
    assert [item["element_id"] for item in report["items"]] == ["database", "web", "edge-box"]
    web = report["items"][1]
    assert web["frames"] == ["AWS Cloud", "VPC"] and web["hourly"] == 0.0416
    assert web["assumed"] == ["os", "tenancy"] and web["source"] == "AWS price list"
    assert report["undrawn"] == [] and report["notes"] == []
    assert target.is_file() and "CSV" in err, "the CSV line goes to stderr beside the JSON"


def test_costs_json_moves_the_price_lines_to_stderr(priced: Path, monkeypatch, capsys) -> None:
    from infragram.cli.user.costs import main

    def fetched(project, source: str = "table") -> list[str]:
        print("PRICED   web: USD 30.37 a month")
        return ["not priced: the database"]

    monkeypatch.setattr("infragram.cli.user.export_project.print_prices", fetched)
    assert main([str(priced), "--prices", "--json"]) == 0
    report, err = _parsed(capsys)
    assert report["notes"] == ["not priced: the database"]
    assert "PRICED   web" in err and "NOTE     not priced" in err
    assert main([str(priced), "--prices"]) == 0
    assert capsys.readouterr().out.startswith("PRICED   web"), "without --json, as before"


# ------------------------------------------------------------------ views
TEMPLATE = skill_assets() / "templates" / "cloud" / "azure-hub-spoke-landing-zone.infragram.json"


def test_views_json_lists_frames_by_level(capsys) -> None:
    from infragram.cli.user.views import main

    assert main([str(TEMPLATE), "--json"]) == 0
    report, _ = _parsed(capsys)
    assert report["slug"] == "azure-hub-spoke-landing-zone" and report["views"] == []
    frames = {frame["id"]: frame for frame in report["frames"]}
    assert frames["landing-zone-production"] == {
        "id": "landing-zone-production",
        "name": "Landing zone · production",
        "type": "subscription",
        "level": 2,
        "parent": "landing-zones",
        "components": 6,
    }
    assert frames["microsoft-azure"]["level"] == 0 and frames["microsoft-azure"]["parent"] is None
    assert report["rule_kinds"] == ["tag", "category", "name", "within", "id"]


def test_views_json_spells_declared_views_as_view_takes_them(tmp_path: Path, capsys) -> None:
    from infragram.cli.user.views import main

    spec = tmp_path / "shop.py"
    spec.write_text(
        """\
from infragram.author import Diagram
from infragram.nodes.aws.compute import EC2
from infragram.nodes.aws.databases import RDS
from infragram.nodes.frames import aws

with Diagram("Shop", slug="shop") as diagram:
    with aws.Cloud("AWS Cloud"):
        with aws.VPC("vpc-shop-prod") as prod:
            web = EC2("web-prod").tags(env="prod")
            RDS("db-prod").tags(env="prod")
    diagram.view("prod", "Production", include=["tag:env=prod"])
    diagram.view("data", include=[prod], exclude=[web], extends="prod")
""",
        encoding="utf-8",
    )
    assert main([str(spec), "--json"]) == 0
    report, _ = _parsed(capsys)
    assert report["views"] == [
        {
            "id": "prod",
            "title": "Production",
            "extends": None,
            "include": ["tag:env=prod"],
            "exclude": [],
        },
        {
            "id": "data",
            "title": "data",
            "extends": "prod",
            "include": ["within:vpc-shop-prod"],
            "exclude": ["id:web-prod"],
        },
    ]
