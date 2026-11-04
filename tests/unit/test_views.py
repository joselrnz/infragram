"""A view: part of the one diagram, selected by rule, drawn on its own.

``--view`` takes a frame (a level: a subscription, a resource group, a
VNet), a rule (``tag:``, ``category:``, ``name:`` for a naming convention)
or a view the diagram declares. What is held here: a level stands on its
frame with nothing around it; a rule keeps the frames its components sit in;
a wire is drawn only when both ends are; an environment frame is never drawn
in a view and the view's name stands at the top instead; the result is a
document every export reads; and a document without views is unchanged.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from infragram.paths import skill_assets
from infragram.projects import CloudProject, View, ViewSelector
from infragram.projects.views import ViewError, frames_of, resolve, select

TEMPLATE = skill_assets() / "templates" / "cloud" / "azure-hub-spoke-landing-zone.infragram.json"


@pytest.fixture(scope="module")
def project() -> CloudProject:
    return CloudProject.load(TEMPLATE)


def _names(selected: CloudProject) -> set[str]:
    return {e.name for e in selected.topology.walk() if not e.children}


def _frames(selected: CloudProject) -> list[str]:
    return [frame.id for _, frame in frames_of(selected)]


def test_a_level_stands_on_its_frame(project: CloudProject) -> None:
    for name in ("landing-zone-production", "Landing zone · production"):
        selected, notes = select(project, resolve(project, name))
        assert notes == []
        assert _frames(selected)[0] == "landing-zone-production", "nothing is drawn around it"
        assert "microsoft-azure" not in _frames(selected)
        assert len(_names(selected)) == 6
        assert selected.slug == "azure-hub-spoke-landing-zone-landing-zone-production"
    vnet, _ = select(project, resolve(project, "hub-vnet-10-0-0-0-16"))
    assert _names(vnet) == {
        "ExpressRoute gateway",
        "VPN gateway",
        "Azure Firewall Premium",
        "Azure Bastion",
        "DNS Private Resolver",
        "Private DNS zones",
    }


def test_a_wire_is_drawn_only_when_both_ends_are(project: CloudProject) -> None:
    selected, _ = select(project, resolve(project, "rg-prod-app"))
    drawn = set(selected.topology.index())
    wires = [(e.id, c.target) for e in selected.topology.walk() for c in e.connections]
    assert wires and all(target in drawn for _, target in wires)
    assert ("vm-scale-set", "log-analytics-workspace") not in wires, "its other end is outside"
    assert ("vm-scale-set", "private-endpoints") in wires


def test_a_naming_convention_is_a_view_and_the_environment_frame_goes(
    project: CloudProject,
) -> None:
    selected, _ = select(project, resolve(project, "name:*prod*"))
    assert "landing-zones" not in _frames(selected), "the environment frame is not drawn"
    assert _frames(selected)[:2] == ["microsoft-azure", "landing-zone-production"]
    assert "Dev application VMs" not in _names(selected) and "VM scale set" in _names(selected)
    assert selected.presentation.notes[0] == "prod", "the view's name stands at the top"


def test_a_rule_keeps_the_frames_its_components_sit_in(project: CloudProject) -> None:
    selected, _ = select(project, resolve(project, "category:networking"))
    assert "Azure Firewall Premium" in _names(selected)
    assert "Azure SQL Database" not in _names(selected)
    assert "hub-vnet-10-0-0-0-16" in _frames(selected)
    assert "management-subscription" not in _frames(selected), "a frame left empty is not drawn"


def test_a_declared_view_includes_excludes_and_extends(project: CloudProject) -> None:
    declared = project.model_copy(
        update={
            "views": (
                View(
                    id="zones",
                    title="Landing zones",
                    include=(ViewSelector(within="landing-zones"),),
                ),
                View(
                    id="prod-data",
                    title="Production data",
                    extends="zones",
                    include=(ViewSelector(category="databases"), ViewSelector(id="key-vault")),
                    exclude=(ViewSelector(name="*dev*"),),
                ),
            )
        }
    )
    declared = CloudProject.model_validate(declared.model_dump())
    selected, _ = select(declared, resolve(declared, "prod-data"))
    assert _names(selected) == {"Azure SQL Database", "Key Vault"}
    assert selected.views == (), "a view's document offers no views of its own"
    assert sum(1 for e in selected.topology.walk() if e.name == "Azure SQL Database") == 1


def test_what_cannot_be_drawn_says_why(project: CloudProject) -> None:
    with pytest.raises(ViewError, match="2 frames are called 'Spoke VNet'.*spoke-vnet-10-1-0-0-16"):
        resolve(project, "Spoke VNet")
    with pytest.raises(ViewError, match="no view or frame 'landing-zone-prod'; did you mean"):
        resolve(project, "landing-zone-prod")
    with pytest.raises(ViewError, match="selects nothing"):
        select(project, resolve(project, "tag:env=nowhere"))
    gone = View(
        id="gone",
        include=(ViewSelector(within="deleted-frame"), ViewSelector(category="databases")),
    )
    _, notes = select(project, gone)
    assert notes == ["view 'gone' names 'deleted-frame', which the drawing does not hold"]


def test_the_document_holds_its_views_to_the_rules() -> None:
    payload = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    assert CloudProject.model_validate(payload).views == ()
    with pytest.raises(ValueError, match="exactly one of tag, category, name, within, id"):
        ViewSelector(tag="env=prod", category="databases")
    with pytest.raises(ValueError, match="key=value"):
        ViewSelector(tag="prod")
    with pytest.raises(ValueError, match="cannot be called that"):
        View(id="all")
    twice = {**payload, "views": [{"id": "a"}, {"id": "a"}]}
    with pytest.raises(ValueError, match="duplicate view id: a"):
        CloudProject.model_validate(twice)
    orphan = {**payload, "views": [{"id": "a", "extends": "b"}]}
    with pytest.raises(ValueError, match="extends unknown view 'b'"):
        CloudProject.model_validate(orphan)


def test_a_diagram_file_declares_views(tmp_path: Path) -> None:
    from infragram.cli.user.compose import project_from_spec

    spec = tmp_path / "shop.py"
    spec.write_text(
        """\
from infragram.author import Diagram, Edge
from infragram.nodes.aws.compute import EC2
from infragram.nodes.aws.databases import RDS
from infragram.nodes.frames import aws

with Diagram("Shop", slug="shop") as diagram:
    with aws.Cloud("AWS Cloud"):
        with aws.VPC("vpc-shop-prod") as prod:
            web = EC2("web-prod").tags(env="prod")
            db = RDS("db-prod").tags(env="prod")
        with aws.VPC("vpc-shop-dev"):
            dev = EC2("web-dev").tags(env="dev")
    web >> Edge("SQL") >> db
    diagram.view("prod", "Production", include=["tag:env=prod"])
    diagram.view("data", include=[prod], exclude=[web])
""",
        encoding="utf-8",
    )
    project = project_from_spec(spec)
    assert [view.id for view in project.views] == ["prod", "data"]
    assert project.views[1].include == (ViewSelector(within="vpc-shop-prod"),)
    prod, _ = select(project, resolve(project, "prod"))
    assert _names(prod) == {"web-prod", "db-prod"}
    data, _ = select(project, resolve(project, "data"))
    assert _names(data) == {"db-prod"}


def test_the_commands_draw_a_view_and_list_them(tmp_path: Path, capsys) -> None:
    from infragram.cli.user.export_project import main as export_project
    from infragram.cli.user.views import main as views

    args = [str(TEMPLATE), "--formats", "svg", "--verify", "--output-dir", str(tmp_path)]
    assert export_project([*args, "--view", "landing-zone-production"]) == 0
    printed = capsys.readouterr().out
    assert "VIEW     landing-zone-production: 6 of 27 components" in printed
    picture = tmp_path / "azure-hub-spoke-landing-zone-landing-zone-production.svg"
    assert picture.is_file() and f"OK {picture}" in printed, "the checker passes the view's picture"
    assert export_project([*args, "--view", "nowhere"]) == 2
    assert "no view or frame 'nowhere'" in capsys.readouterr().err
    assert export_project([*args, "--view", "all"]) == 2
    assert "declares no views" in capsys.readouterr().err
    assert views([str(TEMPLATE)]) == 0
    listed = capsys.readouterr().out
    assert (
        "FRAME        landing-zone-production: Landing zone · production [subscription] (6)"
        in listed
    )


def test_a_view_rule_in_any_script_draws(tmp_path: Path, capsys) -> None:
    from infragram.cli.user.export_project import main
    from infragram.projects import CloudProject
    from infragram.projects.views import resolve

    view = resolve(CloudProject.load(TEMPLATE), "name:wéb*")
    assert view.id == "name-w-b", "an id is ASCII, whatever the rule's script"
    args = [str(TEMPLATE), "--formats", "template", "--output-dir", str(tmp_path)]
    assert main([*args, "--view", "name:*próduction*"]) == 2, "it matches nothing, and says so"
    assert "selects nothing" in capsys.readouterr().err
    assert main([*args, "--view", "name:*· production*"]) == 0, capsys.readouterr().err
    written = [path.name for path in tmp_path.glob("*.infragram.json")]
    assert written == ["azure-hub-spoke-landing-zone-name-production.infragram.json"], written
