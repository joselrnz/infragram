"""The connector anchoring cases as small diagrams, one project each.

The same five cases the reference drawing shows (``connector-anchors-cases.svg``)
and the checker test composes, exported through the real pipeline so the
pictures can be looked at rather than imagined: glyphs side by side, glyphs
stacked, a card to a glyph, a wire passing a third node, and many wires on
one side of a glyph. Every wire end meets its node at the card's edge or at
the glyph's own edge or the caption's underside -- the shipped checker
enforces it on these exports the same as on any other.

Through the skill's launcher, from the plugin folder::

    python skills/infragram-architect/scripts/infragram.py compose examples/connector_anchoring_cases.py

exports the five cases in one picture, each in its own frame. Run as a script
with the package installed (``python -m pip install <plugin folder>``),
``python examples/connector_anchoring_cases.py`` writes
``dist/anchoring-cases/<case>.html|svg|png`` for each case.
"""

from __future__ import annotations

from pathlib import Path

from infragram.author import Diagram, Edge
from infragram.nodes import infragram as shared
from infragram.nodes.aws import compute, networking_content_delivery as net
from infragram.nodes.frames import aws as frames, generic


def side_by_side() -> Diagram:
    with Diagram(
        "Glyphs side by side",
        "Sides face the other end, at the glyph's middle.",
        slug="anchoring-side-by-side",
    ) as diagram:
        internet = shared.networking.PublicInternet("Internet", "public")
        nat = net.VPCNATGateway("NAT gateway", "outbound")
        internet >> Edge("egress") >> nat
    return diagram


def stacked() -> Diagram:
    with Diagram(
        "Glyphs stacked",
        "Leaves under the caption, meets the glyph's top.",
        slug="anchoring-stacked",
    ) as diagram:
        with frames.Cloud("Stacked").column():
            users = shared.identity.PublicUsers("Users", "people")
            balancer = shared.networking.GenericLoadBalancer("Load balancer", "L7")
        users >> Edge("HTTPS") >> balancer
    return diagram


def card_to_glyph() -> Diagram:
    with Diagram(
        "Card to glyph",
        "A card's edge to a glyph's edge; the air beside the glyph is free.",
        slug="anchoring-card-to-glyph",
    ) as diagram:
        with frames.Cloud("AWS Cloud"), frames.Region("us-east-1"), frames.VPC("VPC"):
            with frames.PrivateSubnet("Private"):
                app = compute.EC2("App servers", "Auto Scaling group")
            with frames.PrivateSubnet("Endpoints"):
                endpoint = net.VPCEndpoints("VPC endpoint", "S3 gateway")
        app >> Edge("private") >> endpoint
    return diagram


def passing_a_third_node() -> Diagram:
    with Diagram(
        "Passing a third node",
        "Other nodes block their whole box, caption included.",
        slug="anchoring-passing-a-third-node",
    ) as diagram:
        with frames.Cloud("Row").row():
            client = shared.identity.PublicUsers("Client", "browser")
            shared.security.Firewall("Bastion", "jump host")
            api = net.APIGateway("API", "REST")
        client >> Edge("HTTPS") >> api
    return diagram


def many_wires_one_side() -> Diagram:
    with Diagram(
        "Many wires on one side",
        "Every wire on a side meets at the glyph's one point on that side.",
        slug="anchoring-many-wires",
    ) as diagram:
        hub = shared.networking.CoreSwitch("Core switch", "spine")
        leaves = [shared.networking.AccessSwitch(f"Leaf {n}", "access") for n in (1, 2, 3, 4)]
        hub >> Edge() >> leaves
    return diagram


CASES = (side_by_side, stacked, card_to_glyph, passing_a_third_node, many_wires_one_side)


def build_all() -> list[Diagram]:
    return [case() for case in CASES]


# What the compose runner exports when given this file: the five cases in one
# picture, each in its own frame. Run the file directly for five separate
# pictures.
with Diagram(
    "Connector anchoring cases",
    "The five drawn anchoring cases in one picture, each in its own frame.",
    slug="connector-anchoring-cases",
) as diagram:
    with generic.Environment("Connector anchoring cases").column():
        with generic.Environment("Side by side").row():
            internet = shared.networking.PublicInternet("Internet", "public")
            nat = net.VPCNATGateway("NAT gateway", "outbound")
        internet >> Edge("egress") >> nat

        with generic.Environment("Stacked").column():
            users = shared.identity.PublicUsers("Users", "people")
            balancer = shared.networking.GenericLoadBalancer("Load balancer", "L7")
        users >> Edge("HTTPS") >> balancer

        with frames.Cloud("Card to glyph"), frames.Region("us-east-1"), frames.VPC("VPC"):
            with frames.PrivateSubnet("Private"):
                app = compute.EC2("App servers", "Auto Scaling group")
            with frames.PrivateSubnet("Endpoints"):
                endpoint = net.VPCEndpoints("VPC endpoint", "S3 gateway")
        app >> Edge("private") >> endpoint

        with generic.Environment("Passing a third node").row():
            client = shared.identity.PublicUsers("Client", "browser")
            shared.security.Firewall("Bastion", "jump host")
            api = net.APIGateway("API", "REST")
        client >> Edge("HTTPS") >> api

        with generic.Environment("Many wires on one side").row():
            hub = shared.networking.CoreSwitch("Core switch", "spine")
            leaves = [shared.networking.AccessSwitch(f"Leaf {n}", "access") for n in (1, 2, 3, 4)]
        hub >> Edge() >> leaves


if __name__ == "__main__":
    out = Path("dist") / "anchoring-cases"
    for case in build_all():
        result = case.export(out, display="card", overwrite=True)
        print(result.png)
