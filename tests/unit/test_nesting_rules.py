"""Frames nest the way the clouds do, and the checker says so.

The review's new user copied the shipped Azure example, which drew one
resource group inside another, and drew an AWS subnet inside an Azure
subscription; every check said OK. The checker now refuses a frame of a kind
no vendor nests inside its own kind, and one cloud's frames or services
inside another cloud's frame. No shipped template or example does either.
"""

from __future__ import annotations

from pathlib import Path

from infragram.cli.user.checker import checker
from infragram.cli.user.compose import project_from_spec

HEAD = """\
from infragram.author import Diagram
from infragram.nodes.aws.compute import EC2
from infragram.nodes.aws.databases import RDS
from infragram.nodes.azure.compute import VirtualMachine
from infragram.nodes.frames import aws, azure
"""


def _problems(tmp_path: Path, body: str) -> list[str]:
    spec = tmp_path / "d.py"
    spec.write_text(HEAD + body, encoding="utf-8")
    document = tmp_path / "d.infragram.json"
    project_from_spec(spec).save(document)
    errors: list[str] = []
    module = checker()
    payload = __import__("json").loads(document.read_text(encoding="utf-8"))
    module.check_nesting(payload, errors)
    return errors


def test_a_resource_group_inside_a_resource_group_is_refused(tmp_path: Path) -> None:
    errors = _problems(
        tmp_path,
        """
with Diagram("Nested"):
    with azure.Subscription("Prod"), azure.ResourceGroup("rg-web"):
        VirtualMachine("web")
        with azure.ResourceGroup("rg-data"):
            VirtualMachine("db")
""",
    )
    assert len(errors) == 1
    assert "resource-group 'rg-data' inside the resource-group 'rg-web'" in errors[0]


def test_one_clouds_frames_never_sit_in_anothers(tmp_path: Path) -> None:
    errors = _problems(
        tmp_path,
        """
with Diagram("Mixed"):
    with azure.Subscription("Prod"):
        VirtualMachine("web")
        with aws.PublicSubnet("public"):
            RDS("db")
""",
    )
    assert any("is aws, inside azure's subscription frame 'Prod'" in error for error in errors)


def test_side_by_side_is_fine(tmp_path: Path) -> None:
    assert (
        _problems(
            tmp_path,
            """
with Diagram("Fine"):
    with azure.Subscription("Prod"):
        with azure.ResourceGroup("rg-web"):
            VirtualMachine("web")
        with azure.ResourceGroup("rg-data"):
            VirtualMachine("db")
    with aws.Cloud("AWS"), aws.VPC("vpc"):
        EC2("api")
""",
        )
        == []
    )


ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())


def test_the_three_tier_template_keeps_its_web_servers_private() -> None:
    """Its description says the web servers sit in private subnets, so both do."""
    from infragram.projects import CloudProject

    project = CloudProject.load(
        ROOT
        / "plugin/skills/infragram-architect/assets/templates/cloud/aws-three-tier-web.infragram.json"
    )
    parent_type = {
        child.id: element.type for element in project.topology.walk() for child in element.children
    }
    assert parent_type["web-a"] == parent_type["web-b"] == "subnet-private"
