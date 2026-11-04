"""Writing a diagram as described builds the same document as assembling it.

Nesting is containment, an arrow is a wire, and ``infragram compose`` finds
the diagram a file wrote. The older forms keep working underneath.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from infragram.author import Diagram, Edge, latest_diagram, slugify
from infragram.nodes import Group, _scope, reset_ids
from infragram.nodes.azure import compute, databases, networking, storage
from infragram.nodes.frames import azure as az
from infragram.patterns import Blueprint
from infragram.projects import CloudProject

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())


@pytest.fixture(autouse=True)
def _clean_scopes():
    _scope.reset()
    reset_ids()
    yield
    _scope.reset()


def _shape(element) -> tuple:
    """What the picture depends on: id, name, kind, children and wires."""
    wires = tuple((c.target, c.kind, c.label, c.direction) for c in element.connections)
    return (
        element.id,
        element.name,
        element.type,
        wires,
        tuple(_shape(child) for child in element.children),
    )


def _azure_described() -> CloudProject:
    with Diagram("Azure hierarchy: tenant to subnet", "The ownership chain.") as diagram:
        with az.Tenant("Contoso - Microsoft Entra tenant"):
            with az.ManagementGroup("Platform management group"):
                with az.Subscription("Production subscription"):
                    with az.ResourceGroup("rg-prod-web"):
                        with az.VNet("vnet-prod - 10.10.0.0/16"):
                            with az.Subnet("snet-web - 10.10.1.0/24"):
                                appgw = networking.ApplicationGateways(
                                    "Application Gateway", "WAF v2"
                                )
                                web = compute.VirtualMachine("Web tier", "VM scale set")
                            with az.Subnet("snet-app - 10.10.2.0/24"), az.AKS("aks-prod"):
                                api = compute.KubernetesServices("API workloads", "AKS pods")
                            with az.Subnet("snet-data - 10.10.3.0/24"):
                                sql = databases.SQLDatabase("Azure SQL", "private endpoint")
                                blobs = storage.StorageAccounts(
                                    "Storage account", "private endpoint"
                                )
        appgw >> Edge("HTTPS") >> web
        web >> Edge("internal") >> api
        api >> Edge("TDS 1433", dashed=True) >> sql
        api >> Edge("blob", dashed=True) >> blobs
    return diagram.to_project()


def _azure_assembled() -> CloudProject:
    reset_ids()
    plan = Blueprint.fresh(
        "azure-hierarchy-tenant-to-subnet",
        "Azure hierarchy: tenant to subnet",
        "The ownership chain.",
    )
    plan.kind = "single-cloud"
    plan.providers = ("azure",)
    (tenant,) = plan.add(az.Tenant("Contoso - Microsoft Entra tenant"))
    mg = tenant >> az.ManagementGroup("Platform management group")
    sub = mg >> az.Subscription("Production subscription")
    rg = sub >> az.ResourceGroup("rg-prod-web")
    vnet = rg >> az.VNet("vnet-prod - 10.10.0.0/16")
    web_subnet = vnet >> az.Subnet("snet-web - 10.10.1.0/24")
    appgw = web_subnet >> networking.ApplicationGateways("Application Gateway", "WAF v2")
    web = web_subnet >> compute.VirtualMachine("Web tier", "VM scale set")
    app_subnet = vnet >> az.Subnet("snet-app - 10.10.2.0/24")
    aks = app_subnet >> az.AKS("aks-prod")
    api = aks >> compute.KubernetesServices("API workloads", "AKS pods")
    data_subnet = vnet >> az.Subnet("snet-data - 10.10.3.0/24")
    sql = data_subnet >> databases.SQLDatabase("Azure SQL", "private endpoint")
    blobs = data_subnet >> storage.StorageAccounts("Storage account", "private endpoint")
    plan.link(appgw, web, label="HTTPS")
    plan.link(web, api, label="internal")
    plan.link(api, sql, label="TDS 1433", kind="dashed")
    plan.link(api, blobs, label="blob", kind="dashed")
    return plan.to_project()


def test_the_described_diagram_is_the_assembled_document() -> None:
    described, assembled = _azure_described(), _azure_assembled()
    assert described.slug == assembled.slug == "azure-hierarchy-tenant-to-subnet"
    assert described.kind == assembled.kind == "single-cloud"
    assert [p.id for p in described.providers] == [p.id for p in assembled.providers] == ["azure"]
    assert _shape(described.topology) == _shape(assembled.topology)


def test_nesting_is_containment_and_two_frames_in_one_with_nest_in_order() -> None:
    with Diagram("Nest") as diagram:
        with az.VNet("vnet") as vnet:
            with az.Subnet("snet"), az.AKS("aks") as aks:
                pod = compute.KubernetesServices("pods")
    (root,) = diagram.roots
    assert root is vnet
    (subnet,) = vnet.children
    assert subnet.type == "subnet-private"
    assert subnet.children == [aks]
    assert aks.children == [pod]


def test_between_nodes_the_arrow_is_a_wire_in_every_direction() -> None:
    with Diagram("Wires"):
        with Group("Zone", "group"):
            a = compute.VirtualMachine("A")
            b = compute.VirtualMachine("B")
            c = compute.VirtualMachine("C")
            d = compute.VirtualMachine("D")
        assert (a >> b) is b
        a << c  # c to a
        a - d  # no arrowheads
        a >> Edge("fan out", dashed=True) >> [b, c]
    assert [(w.target, w.kind, w.label, w.direction) for w in a.connections] == [
        ("b", "solid", "", "forward"),
        ("d", "solid", "", "none"),
        ("b", "dashed", "fan out", "forward"),
        ("c", "dashed", "fan out", "forward"),
    ]
    assert [(w.target, w.direction) for w in c.connections] == [("a", "forward")]
    assert b.connections == []


def test_reverse_edge_and_both_heads() -> None:
    with Diagram("Reverse"):
        with Group("Zone", "group"):
            primary = compute.VirtualMachine("Primary")
            replica = compute.VirtualMachine("Replica")
        primary << Edge("replicates") << replica
        primary >> Edge("peering", both=True) >> replica
    assert [(w.target, w.label, w.direction) for w in replica.connections] == [
        ("primary", "replicates", "forward")
    ]
    assert [(w.target, w.label, w.direction) for w in primary.connections] == [
        ("replica", "peering", "both")
    ]


def test_frames_still_nest_with_the_old_operator_and_never_twice() -> None:
    vnet = az.VNet("vnet")
    subnet = vnet >> az.Subnet("snet")
    vm = subnet >> compute.VirtualMachine("Host")
    assert vnet.children == [subnet] and subnet.children == [vm]
    subnet >> vm
    assert subnet.children == [vm]


def test_layout_hints_are_methods_not_arguments() -> None:
    with Diagram("Hints", direction="right") as diagram:
        with az.VNet("vnet").row():
            with az.Subnet("ordered").keep_order():
                compute.VirtualMachine("Host")
    (vnet,) = diagram.roots
    assert vnet.attributes["flow"] == "row"
    assert vnet.children[0].attributes["arrange"] == "manual"
    assert diagram.topology().attributes["flow"] == "row"


def test_slug_providers_and_kind_are_inferred() -> None:
    project = _azure_described()
    assert project.slug == slugify("Azure hierarchy: tenant to subnet")
    assert project.description == "The ownership chain."
    assert project.default_library == "azure"
    # what Diagram() writes when nothing asks otherwise: the document
    # default, bare marks
    assert project.presentation.display == "icon"


def test_an_empty_diagram_says_so() -> None:
    from infragram.compose import ComposeError

    with Diagram("Nothing") as diagram:
        pass
    with pytest.raises(ComposeError, match="no elements"):
        diagram.to_project()


def test_the_compose_command_picks_up_the_diagram_a_file_wrote(tmp_path: Path) -> None:
    spec = tmp_path / "spec.py"
    spec.write_text(
        "from infragram.author import Diagram, Edge\n"
        "from infragram.nodes.frames import azure as az\n"
        "from infragram.nodes.azure import compute\n"
        "with Diagram('One frame, one host'):\n"
        "    with az.ResourceGroup('rg'):\n"
        "        compute.VirtualMachine('Host', 'one')\n",
        encoding="utf-8",
    )
    from infragram.cli.user.compose import project_from_spec

    project = project_from_spec(spec)
    assert isinstance(project, CloudProject)
    assert project.slug == "one-frame-one-host"
    assert [element.type for element in project.topology.walk()][1:] == [
        "resource-group",
        "virtual-machine",
    ] or project.topology.children[0].type == "resource-group"
    assert latest_diagram() is not None


@pytest.mark.slow
@pytest.mark.parametrize(
    "name", sorted(p.name for p in (ROOT / "plugin" / "examples").glob("*.py"))
)
def test_every_shipped_example_builds_and_passes_the_picture_checks(name: str) -> None:
    from infragram.cli.user.checker import checker
    from infragram.cli.user.compose import project_from_spec
    from infragram.exports import render_project_svg

    project = project_from_spec(ROOT / "plugin" / "examples" / name)
    assert len(list(project.topology.walk())) > 8
    errors: list[str] = []
    checker().check_svg(render_project_svg(project), errors, project.model_dump(mode="json"))
    assert not errors, errors


def test_explicit_placement_takes_a_node_back_from_the_open_frame() -> None:
    from infragram.nodes.azure import compute

    with Diagram("Claim") as diagram:
        with Group("Outer", "group") as outer:
            inner = Group("Inner", "group")
            node = compute.VirtualMachine("Host")  # adopted by Outer on construction
            inner >> node  # explicitly placed: leaves Outer
    assert outer.children == [inner]
    assert inner.children == [node]
    assert diagram.roots == [outer]


def test_a_pattern_attached_inside_a_frame_nests_once() -> None:
    from infragram.nodes.aws import compute, databases
    from infragram.nodes.frames import aws
    from infragram.patterns.aws import MultiAZ

    def private_tier(subnet, zone):
        zone.part("web", subnet >> compute.EC2("Web servers", "Auto Scaling"))
        zone.part("db", subnet >> databases.RDS("PostgreSQL", "Multi-AZ"))

    with Diagram("Pattern in a frame") as diagram:
        with aws.VPC("VPC 10.0.0.0/16").row() as vpc:
            zones = MultiAZ(2, private=private_tier).attach(vpc)
        zones.part_for("web", "A") >> Edge("SQL") >> zones.part_for("db", "A")
    project = diagram.to_project()
    seen: dict[str, int] = {}
    for element in project.topology.walk():
        seen[element.id] = seen.get(element.id, 0) + 1
    assert all(count == 1 for count in seen.values()), {k: v for k, v in seen.items() if v > 1}
    assert [child.type for child in vpc.children] == ["zone", "zone"]
    assert all(child.type != "zone" or len(child.children) == 1 for child in vpc.children)
    assert diagram.roots == [vpc]


def test_a_misspelt_keyword_fails_with_the_nearest_real_one() -> None:
    from infragram.nodes.aws import compute as aws_compute
    from infragram.nodes.frames import aws

    with pytest.raises(TypeError, match=r"'detial' \(did you mean 'detail'\?\)"):
        aws_compute.EC2("Web", detial="t3.large")
    with pytest.raises(TypeError, match=r"'flwo' \(did you mean 'flow'\?\)"):
        aws.PrivateSubnet("Private", flwo="row")


def test_keys_of_your_own_go_in_attributes() -> None:
    node = compute.VirtualMachine("Host", attributes={"owner": "team-a"}, detail="2 vCPU")
    assert node.attributes["owner"] == "team-a" and node.attributes["detail"] == "2 vCPU"


def test_a_look_the_renderer_does_not_know_is_refused_where_it_is_written() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="card"):
        Diagram("Looks", display="cards")


def test_a_misspelt_document_key_is_refused_at_load() -> None:
    from pydantic import ValidationError

    from infragram.models.topology import TopologyElement

    with pytest.raises(ValidationError, match="conections"):
        TopologyElement.model_validate(
            {"id": "a", "name": "A", "type": "service", "conections": []}
        )


def test_export_refuses_document_options_it_would_ignore(tmp_path: Path) -> None:
    from infragram import compose

    with pytest.raises(TypeError, match="format"):
        compose.export(_azure_described(), tmp_path, format=("svg",))


def test_a_node_built_before_the_block_keeps_its_id_beside_a_namesake_inside() -> None:
    reset_ids()
    outside = compute.VirtualMachine("Web")
    with Diagram("Two webs", providers=("azure",)) as diagram:
        inside = compute.VirtualMachine("Web")
        diagram.add(outside)
    assert outside.id == "web" and inside.id == "web-2"
    ids = [element.id for element in diagram.to_project().topology.walk()]
    assert len(ids) == len(set(ids))


def test_a_closed_diagram_frees_its_ids_for_the_next() -> None:
    reset_ids()
    with Diagram("First", providers=("azure",)) as first:
        compute.VirtualMachine("Web")
    with Diagram("Second", providers=("azure",)) as second:
        compute.VirtualMachine("Web")
    assert first.roots[0].id == "web" and second.roots[0].id == "web"


def test_a_node_hoisted_after_its_frame_closed_has_one_parent() -> None:
    reset_ids()
    with Diagram("Hoist", providers=("azure",)) as diagram:
        with az.VNet("vnet"):
            with az.Subnet("first"):
                vm = compute.VirtualMachine("Host")
            second = az.Subnet("second")
        second.add(vm)
    parents = [
        element
        for element in diagram.topology().walk()
        if any(child is vm for child in element.children)
    ]
    assert [parent.name for parent in parents] == ["second"]
    ids = [element.id for element in diagram.to_project().topology.walk()]
    assert len(ids) == len(set(ids))
