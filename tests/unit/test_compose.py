from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from infragram import compose
from infragram.exports import render_project_html
from infragram.nodes import Frame, Group, azure, infragram as shared, kubernetes, onprem, reset_ids
from infragram.nodes.aws import compute, databases, networking_content_delivery as aws_net
from infragram.nodes.frames import (
    aws as aws_frames,
    azure as azure_frames,
    generic,
    onprem as onprem_frames,
)
from infragram.projects import CloudProject

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())


@pytest.fixture(autouse=True)
def _fresh_ids():
    reset_ids()


def _aws_estate():
    cloud = aws_frames.Cloud("AWS Cloud")
    vpc = cloud >> aws_frames.Region("us-east-1") >> aws_frames.VPC("VPC 10.0.0.0/16")
    public = vpc >> aws_frames.PublicSubnet("Public subnet")
    private = vpc >> aws_frames.PrivateSubnet("Private subnet")
    alb = public >> aws_net.ElasticLoadBalancing("ALB", "HTTPS :443")
    web = private >> compute.EC2("Web servers", "ASG")
    db = private >> databases.RDS("PostgreSQL", "Multi-AZ")
    users = shared.identity.PublicUsers("Users", "internet")
    users.to(alb, label="HTTPS")
    alb.to(web, label="HTTP")
    web.to(db, label="SQL", direction="both")
    return [users, cloud], {"alb": alb, "web": web, "db": db, "vpc": vpc}


def test_frames_carry_gallery_identity_and_stay_frames_when_empty() -> None:
    vpc = aws_frames.VPC("Prod VPC")
    assert vpc.is_frame
    assert vpc.type == "vpc"
    assert vpc.component is not None
    assert vpc.component.icon_ref == "infragram:custom-boundary-vpc"
    assert vpc.attributes["editor_frame_group"] == "aws"
    assert isinstance(vpc, Frame)
    dmz = generic.DMZ("DMZ", flow="row")
    assert dmz.type == "dmz" and dmz.attributes["flow"] == "row"
    assert onprem_frames.Subnet("VLAN 10").component.service_id == "custom-boundary-onprem-subnet"
    assert azure_frames.VNet("hub-vnet").type == "network"


def test_qualify_writes_components_from_node_classes() -> None:
    zone = Group("Edge", "vnet")
    aks = zone >> azure.KubernetesServices("AKS", "private")
    mainframe = zone >> shared.compute.Mainframe("IBM z16", "z/OS")
    compose.qualify(zone)
    assert aks.component is not None
    assert aks.component.icon_ref == "azure:kubernetes-services"
    assert mainframe.component.icon_ref == "infragram:mainframe"
    assert zone.component is None  # a plain Group stays theme-styled by kind


def test_qualify_rejects_unknown_services_with_a_hint() -> None:
    node = azure.KubernetesServices("AKS")
    node.attributes["icon"] = "kubernetes-servicez"
    with pytest.raises(compose.ComposeError, match="kubernetes-services"):
        compose.qualify(node)


def test_infers_providers_and_kind() -> None:
    elements, _ = _aws_estate()
    project = compose.to_project(
        elements, slug="three-tier", title="Three tier", description="AWS estate."
    )
    assert project.provider_ids == ("aws",)
    assert project.kind == "single-cloud"
    assert project.default_library == "aws"
    assert project.presentation.size == "fit"
    assert project.topology.id == "root" and len(project.topology.children) == 2

    site = onprem_frames.Datacenter("DC1")
    site >> onprem.compute.Server("App server")
    vnet = azure_frames.VNet("hub") >> azure.Firewalls("Azure Firewall")
    hybrid = compose.to_project([site, vnet], slug="hybrid", title="Hybrid", description="x.")
    assert hybrid.kind == "hybrid" and set(hybrid.provider_ids) == {"onprem", "azure"}

    cluster = kubernetes.Pod("api") if hasattr(kubernetes, "Pod") else kubernetes.Deploy("api")
    platform = compose.to_project(cluster, slug="k8s", title="K8s", description="x.")
    assert platform.kind == "platform" and platform.provider_ids == ("kubernetes",)
    assert compose.infer_kind(("aws", "azure")) == "multicloud"


def test_direction_survives_from_dsl_to_document() -> None:
    elements, refs = _aws_estate()
    project = compose.to_project(elements, slug="dir", title="Dir", description="x.")
    web = project.topology.first(id=refs["web"].id)
    assert web is not None
    assert web.connections[0].direction == "both"
    dumped = json.loads(project.model_dump_json())
    assert json.dumps(dumped).count('"direction": "both"') == 1


def test_composed_project_renders_with_automatic_placement() -> None:
    elements, refs = _aws_estate()
    project = compose.to_project(elements, slug="placed", title="Placed", description="x.")
    for element in project.topology.walk():
        assert "editor_x" not in element.attributes
    html = render_project_html(project)
    # The graph state is the object that names the project slug; the library
    # payload before it also carries "nodes" (starter stacks), so anchor here.
    anchor = html.index('"projectSlug"')
    state = json.JSONDecoder().raw_decode(html[html.rfind("{", 0, anchor) :])[0]
    boundaries, nodes = state["boundaries"], state["nodes"]
    assert {b["kind"] for b in boundaries} >= {
        "cloud",
        "region",
        "vpc",
        "subnet-public",
        "subnet-private",
    }
    assert all(b.get("frameGroup") == "aws" for b in boundaries)
    assert all(b["iconUri"] for b in boundaries), "gallery frames should carry their glyphs"
    assert len(nodes) == 4
    assert all(n["iconUri"] for n in nodes), "every node class should resolve artwork"
    assert len({(n["x"], n["y"]) for n in nodes}) == 4, "cards should not stack"
    by_id = {n["id"]: n for n in nodes}
    assert by_id[refs["alb"].id]["componentQualifiedId"] == "aws:elastic-load-balancing"


def test_compose_export_defaults_and_root_wrapping(tmp_path: Path) -> None:
    single = shared.compute.Mainframe("IBM z16")
    result = compose.export(
        single,
        tmp_path,
        formats=("template",),
        slug="one",
        title="One",
        description="x.",
        providers=["onprem"],
    )
    saved = CloudProject.load(result.template)
    assert saved.topology.children[0].component.icon_ref == "infragram:mainframe"
    assert saved.provider_ids == ("onprem",)
    # A purely neutral estate is filed under the on-premises library, and a
    # provider frame alone is enough to name its library.
    neutral = compose.to_project(
        shared.compute.Mainframe("z"), slug="x", title="x", description="x."
    )
    assert neutral.provider_ids == ("onprem",) and neutral.kind == "platform"
    framed = compose.to_project(aws_frames.VPC("empty"), slug="y", title="y", description="y.")
    assert framed.provider_ids == ("aws",) and framed.kind == "single-cloud"
    with pytest.raises(compose.ComposeError):
        compose.to_project([], slug="z", title="z", description="z.")


@pytest.mark.slow
@pytest.mark.parametrize("example", sorted((ROOT / "plugin" / "examples").glob("*.py")))
def test_shipped_examples_compose_and_export_a_template(example: Path, tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "infragram",
            "compose",
            str(example),
            "--formats",
            "template",
            "--output-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={
            **__import__("os").environ,
            "PYTHONPATH": str(ROOT / "plugin" / "src"),
            "PYTHONIOENCODING": "utf-8",
        },
    )
    assert completed.returncode == 0, completed.stderr
    assert re.search(r"^PROJECT ", completed.stdout, re.M), completed.stdout
    template = next(tmp_path.glob("*.infragram.json"))
    project = CloudProject.load(template)
    assert len(project.topology.index()) > 8


def test_layout_orders_siblings_by_their_connections() -> None:
    """In the shipped AWS example the WAF sits over the load balancer, which
    drops straight onto the web tier, and the database is pulled left of the
    web tier (which talks to the region services on the right), so no wire
    crosses a card and every arrowhead lands on a straight shaft."""
    import runpy

    from infragram.author import latest_diagram

    spec = runpy.run_path(str(ROOT / "plugin/examples/aws_three_tier.py"), run_name="__spec__")
    project = spec.get("PROJECT") or latest_diagram().to_project()
    html = render_project_html(project)
    anchor = html.index('"projectSlug"')
    state = json.JSONDecoder().raw_decode(html[html.rfind("{", 0, anchor) :])[0]
    x = {node["name"]: node["x"] for node in state["nodes"]}
    y = {node["name"]: node["y"] for node in state["nodes"]}
    centre = {node["name"]: node["x"] + node["width"] / 2 for node in state["nodes"]}
    # The public subnet stacks: WAF over the load balancer, centred (the
    # balancer's card is wider, so their x differ while their centres agree).
    assert y["AWS WAF"] < y["Application Load Balancer"]
    assert centre["AWS WAF"] == centre["Application Load Balancer"]
    # The private row is reordered by its wires: the database moves left of
    # the web tier, which talks to the region services on the right.
    assert x["PostgreSQL"] < x["Web servers"]
    # and the pairing survived the reorder: every card kept its own artwork id
    ids = {node["name"]: node["componentQualifiedId"] for node in state["nodes"]}
    assert ids["PostgreSQL"] == "aws:rds" and ids["Web servers"] == "aws:ec2"
    assert ids["Users"] == "infragram:public-users"


def test_direction_down_stacks_the_top_level_frames() -> None:
    from infragram.author import Diagram
    from infragram.nodes.frames import generic
    from infragram.nodes.onprem import iso_energy as energy

    def placed(direction: str | None) -> dict[str, dict]:
        reset_ids()
        options = {"direction": direction} if direction else {}
        with Diagram("Tiers", slug="tiers", providers=("onprem",), **options) as diagram:
            with generic.Environment("One").row():
                energy.IsoSubstation("A")
            with generic.Environment("Two").row():
                energy.IsoSubstation("B")
        html = render_project_html(diagram.to_project())
        anchor = html.index('"projectSlug"')
        state = json.JSONDecoder().raw_decode(html[html.rfind("{", 0, anchor) :])[0]
        return {b["name"]: b for b in state["boundaries"]}

    side = placed(None)
    assert side["Two"]["x"] >= side["One"]["x"] + side["One"]["width"], "default: side by side"
    assert side["Two"]["y"] == side["One"]["y"]
    down = placed("down")
    assert down["Two"]["y"] >= down["One"]["y"] + down["One"]["height"], "down: stacked"
    assert down["Two"]["x"] == down["One"]["x"]
