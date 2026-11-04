"""A resource-tier glyph draws bare; a service keeps its card.

Vendor decks draw two tiers. A service is a coloured tile and reads well in
a titled card. A resource -- a NAT gateway, an internet gateway, a VPC
endpoint -- is a line glyph the deck places bare inside its subnet with a
caption beneath. The rule follows the artwork's tier through one function,
so the editor state, the static fallback and the sidebar all agree, and a
node's own saved choice still wins.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from infragram import compose
from infragram.builders.architecture import display_of, icon_for
from infragram.editor.shell import library_catalog_from_html
from infragram.exports import render_project_html
from infragram.models.topology import TopologyElement
from infragram.nodes import reset_ids
from infragram.nodes.aws import compute, networking_content_delivery as net
from infragram.nodes.frames import aws as frames
from infragram.projects import CloudProject

ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".claude-plugin").is_dir())
RSTUDIO = (
    ROOT
    / "plugin/skills/infragram-architect/assets/templates/cloud/rstudio-shiny-analytics-platform.infragram.json"
)


@pytest.fixture(autouse=True)
def _fresh_ids():
    reset_ids()


def _estate():
    cloud = frames.Cloud("AWS Cloud")
    vpc = cloud >> frames.Region("us-east-1") >> frames.VPC("VPC")
    public = vpc >> frames.PublicSubnet("Public")
    nat = public >> net.VPCNATGateway("NAT Gateway", "outbound only")
    igw = vpc >> net.VPCInternetGateway("Internet Gateway", "VPC ingress")
    app = vpc >> frames.PrivateSubnet("Private") >> compute.EC2("App server", "web tier")
    igw.to(nat, label="ingress")
    app.to(nat, label="egress")
    return [cloud], nat, igw, app


def _state(html: str) -> dict:
    match = re.search(r'<script[^>]*id="infragram-editor-state"[^>]*>(.*?)</script>', html, re.S)
    assert match
    return json.loads(match.group(1))


def _library(html: str) -> dict:
    return library_catalog_from_html(html)


def _static_groups(html: str, display: str) -> list[str]:
    return re.findall(rf'<g [^>]*data-node="([^"]*)" data-display="{display}">', html)


# ------------------------------------------------------------- the rule
def test_the_rule_reads_the_tier_and_the_nodes_own_choice_wins() -> None:
    elements, nat, igw, app = _estate()
    assert icon_for(nat).tier == "resource"
    assert icon_for(app).tier is None
    assert display_of(nat, "card", icon_for(nat)) == "icon"
    assert display_of(app, "card", icon_for(app)) == "card"
    assert display_of(app, "icon", icon_for(app)) == "icon"
    nat.attributes["editor_display_mode"] = "card"
    assert display_of(nat, "card", icon_for(nat)) == "card"


def test_a_plain_element_without_artwork_follows_the_project() -> None:
    plain = TopologyElement(id="x", name="X", type="server")
    assert display_of(plain, "card") == "card"
    assert display_of(plain, "icon") == "icon"


# --------------------------------------------------------- editor state
def test_resources_land_bare_in_a_card_diagram_and_carry_their_tier() -> None:
    elements, *_ = _estate()
    project = compose.to_project(elements, slug="d", title="D", description="d.", display="card")
    assert project.presentation.display == "card"
    state = _state(render_project_html(project))
    nodes = {node["name"]: node for node in state["nodes"]}
    assert state["canvas"]["displayMode"] == "card"
    assert nodes["NAT Gateway"]["displayMode"] == "icon"
    assert nodes["Internet Gateway"]["displayMode"] == "icon"
    assert nodes["App server"]["displayMode"] == "card"
    assert nodes["NAT Gateway"]["tier"] == "resource"
    assert nodes["App server"]["tier"] == "service"
    # sized as an icon node, not as a card with an empty text lane
    assert nodes["NAT Gateway"]["height"] == 116


def test_a_boxed_resource_stays_boxed_when_the_node_says_so() -> None:
    elements, nat, *_ = _estate()
    nat.attributes["editor_display_mode"] = "card"
    project = compose.to_project(elements, slug="d", title="D", description="d.", display="card")
    nodes = {node["name"]: node for node in _state(render_project_html(project))["nodes"]}
    assert nodes["NAT Gateway"]["displayMode"] == "card"
    assert nodes["Internet Gateway"]["displayMode"] == "icon"


# -------------------------------------------------------- static fallback
def test_the_static_fallback_draws_the_same_answer() -> None:
    elements, nat, igw, app = _estate()
    project = compose.to_project(elements, slug="d", title="D", description="d.", display="card")
    html = render_project_html(project)
    assert {nat.id, igw.id} <= set(_static_groups(html, "icon"))
    assert app.id in _static_groups(html, "card")


# --------------------------------------------------------------- sidebar
def test_the_sidebar_payload_carries_each_components_tier() -> None:
    elements, *_ = _estate()
    project = compose.to_project(elements, slug="d", title="D", description="d.", display="card")
    components = {c["qualifiedId"]: c for c in _library(render_project_html(project))["components"]}
    assert components["aws:vpc-nat-gateway"]["tier"] == "resource"
    assert components["aws:vpc-internet-gateway"]["tier"] == "resource"
    assert components["aws:ec2"]["tier"] == "service"


# ------------------------------------------------------- shipped template
def test_the_rstudio_template_shows_its_gateways_bare_and_its_services_carded() -> None:
    project = CloudProject.load(RSTUDIO)
    assert project.presentation.display == "card"
    nodes = _state(render_project_html(project))["nodes"]
    by_name: dict[str, set[str]] = {}
    for node in nodes:
        by_name.setdefault(node["name"], set()).add(node["displayMode"])
    assert by_name["NAT Gateway"] == {"icon"}
    assert by_name["Internet Gateway"] == {"icon"}
    assert by_name["Amazon ECS"] == {"card"}
