"""Policy checks: the diagram rules, and the scanners read when installed.

The rules flag what a reviewer would stop -- a database in a public subnet,
the internet straight to a database or past the front door into a private
subnet, SSH, RDP or every port open to it -- and nothing in any shipped
template or example. A Terraform folder goes to Checkov or Trivy when one is
on the PATH, and is skipped, never failed, when neither is.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from infragram.paths import plugin_root, skill_assets
from infragram.review.policy import _checkov, _trivy, diagram_findings, scan_folder, scanner_on_path

RISKY = """\
from infragram.author import Diagram, Edge
from infragram.nodes import infragram as shared
from infragram.nodes.aws.compute import EC2
from infragram.nodes.aws.databases import RDS
from infragram.nodes.aws.networking_content_delivery import ElasticLoadBalancing
from infragram.nodes.frames import aws

with Diagram("Risky", slug="risky"):
    internet = shared.identity.PublicUsers("Internet")
    with aws.Cloud("AWS Cloud"), aws.VPC("VPC"):
        with aws.PublicSubnet("Public"):
            exposed = RDS("exposed-db")
        with aws.PrivateSubnet("Private"):
            app = EC2("app")
            lb = ElasticLoadBalancing("lb")
            kept = RDS("kept-db")
    internet >> Edge("SSH :22") >> app
    internet >> Edge("HTTPS :443") >> lb
    internet >> Edge("TCP 0-1024") >> kept
    lb >> Edge("HTTP :8080") >> app
    app >> Edge("SQL") >> kept
"""


@pytest.fixture
def risky(tmp_path: Path) -> Path:
    path = tmp_path / "risky.py"
    path.write_text(RISKY, encoding="utf-8")
    return path


def test_the_rules_flag_what_a_reviewer_would_stop(risky: Path) -> None:
    from infragram.cli.user.compose import project_from_spec

    found = {
        (finding.rule, finding.where) for finding in diagram_findings(project_from_spec(risky))
    }
    assert found == {
        ("database-in-public-subnet", "exposed-db"),
        ("internet-reaches-private-subnet", "app"),
        ("admin-port-open-to-internet", "app"),
        ("internet-reaches-database", "kept-db"),
        ("admin-port-open-to-internet", "kept-db"),
    }, "the load balancer is a front door: the internet reaching it is no finding"


def test_no_shipped_template_or_example_is_flagged() -> None:
    from infragram.cli.user.compose import project_from_spec
    from infragram.projects import CloudProject

    for path in sorted((skill_assets() / "templates" / "cloud").glob("*.infragram.json")):
        assert diagram_findings(CloudProject.load(path)) == [], path.name
    for path in sorted((plugin_root() / "examples").glob("*.py")):
        if not path.name.startswith("_"):
            assert diagram_findings(project_from_spec(path)) == [], path.name


def test_the_command_warns_and_fails_only_when_strict(risky: Path, capsys) -> None:
    from infragram.cli.user.check_policy import main

    assert main([str(risky)]) == 0
    printed = capsys.readouterr().out
    assert "POLICY   warning database-in-public-subnet exposed-db:" in printed
    assert printed.rstrip().endswith("WARN     5 finding(s)")
    assert main([str(risky), "--strict"]) == 1
    capsys.readouterr()


def test_a_folder_without_a_scanner_is_skipped(tmp_path: Path, monkeypatch, capsys) -> None:
    from infragram.cli.user.check_policy import main

    monkeypatch.setattr("shutil.which", lambda name: None)
    assert scanner_on_path() is None
    assert main([str(tmp_path)]) == 0
    assert "SKIP" in capsys.readouterr().out


CHECKOV = {
    "check_type": "terraform",
    "results": {
        "failed_checks": [
            {
                "check_id": "CKV_AWS_24",
                "check_name": "Ensure no security groups allow ingress from 0.0.0.0:0 to port 22",
                "resource": "aws_security_group.web",
                "file_path": "/main.tf",
                "file_line_range": [12, 30],
                "severity": None,
            }
        ]
    },
}
TRIVY = {
    "Results": [
        {
            "Target": "main.tf",
            "Misconfigurations": [
                {
                    "ID": "AVD-AWS-0107",
                    "AVDID": "AVD-AWS-0107",
                    "Title": "An ingress security group rule allows traffic from /0.",
                    "Severity": "CRITICAL",
                    "Status": "FAIL",
                    "CauseMetadata": {"Resource": "aws_security_group.web", "StartLine": 14},
                },
                {"ID": "AVD-AWS-0099", "Title": "passed", "Status": "PASS"},
            ],
        }
    ]
}


def test_the_scanners_reports_are_read() -> None:
    (checkov,) = _checkov(CHECKOV)
    assert checkov.rule == "CKV_AWS_24" and checkov.where == "aws_security_group.web (/main.tf:12)"
    assert checkov.severity == "warning" and checkov.source == "checkov"
    assert _checkov([CHECKOV, CHECKOV]) == [checkov, checkov], "one report per framework"
    (trivy,) = _trivy(TRIVY)
    assert trivy.rule == "AVD-AWS-0107" and trivy.severity == "critical"
    assert trivy.where == "aws_security_group.web (main.tf:14)"


def test_a_folder_is_scanned_by_the_scanner_on_the_path(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    from infragram.cli.user.check_policy import main

    ran: list[list[str]] = []

    def run(command, **_kwargs):
        ran.append(command)
        return subprocess.CompletedProcess(command, 1, json.dumps(TRIVY), "")

    monkeypatch.setattr("shutil.which", lambda name: f"/bin/{name}" if name == "trivy" else None)
    monkeypatch.setattr("subprocess.run", run)
    assert scanner_on_path() == "trivy"
    assert main([str(tmp_path), "--strict"]) == 1
    printed = capsys.readouterr().out
    assert f"SCANNED  {tmp_path} with trivy: 1 finding(s)" in printed
    assert ran[0][:4] == ["/bin/trivy", "config", "--format", "json"]
    monkeypatch.setattr(
        "subprocess.run", lambda command, **_: subprocess.CompletedProcess(command, 2, "", "boom")
    )
    assert scan_folder(tmp_path, "trivy") == []
    monkeypatch.setattr(
        "subprocess.run",
        lambda command, **_: subprocess.CompletedProcess(command, 2, "not json", "boom"),
    )
    with pytest.raises(RuntimeError, match="trivy wrote no report: boom"):
        scan_folder(tmp_path, "trivy")


def test_only_every_port_rules_are_errors() -> None:
    from infragram.review.policy import _EVERY_PORT

    assert not _EVERY_PORT.search("SSH via firewall")
    assert not _EVERY_PORT.search("install")
    for label in ("all traffic", "All TCP", "TCP 0-65535", "all ports"):
        assert _EVERY_PORT.search(label), label
