"""Colocation in an Equinix IBX, private links to three clouds over Fabric.

The company racks its own servers and storage in a cage in Equinix's Ashburn
metro (DC2). A Fabric port in the cage feeds a Fabric Cloud Router, which
holds one virtual connection per cloud: AWS Direct Connect, Azure
ExpressRoute and Google Cloud Partner Interconnect. A branch office reaches
the cage through a Network Edge SD-WAN device in the same metro, and the cage
peers with other networks on the Equinix Internet Exchange.

Equinix frames come from ``infragram.nodes.frames.equinix``, its products
from ``infragram.nodes.equinix``; each cloud's side of the link is drawn with
that cloud's own components.

Through the skill's launcher, from the plugin folder::

    python skills/infragram-architect/scripts/infragram.py compose examples/equinix_hybrid_interconnect.py \\
        --formats template,html,svg,png --output-dir dist
"""

from __future__ import annotations

from pathlib import Path

from infragram.author import Diagram, Edge
from infragram.nodes import infragram as shared
from infragram.nodes.aws import compute as aws_compute, networking_content_delivery as aws_net
from infragram.nodes.azure import compute as azure_compute, networking as azure_net
from infragram.nodes.equinix import compute, networking, storage
from infragram.nodes.frames import aws, azure, equinix, gcp, generic, onprem
from infragram.nodes.gcp import core_products as gcp_core, legacy as gcp_net

with Diagram(
    "Equinix hybrid interconnect",
    "Servers and storage colocated in an Equinix cage reach AWS, Azure and Google Cloud over "
    "private Fabric virtual connections from one Fabric Cloud Router; a branch joins through a "
    "Network Edge SD-WAN device, and the cage peers on the Equinix Internet Exchange.",
    slug="equinix-hybrid-interconnect",
) as diagram:
    with onprem.Site("Branch office").column():
        staff = shared.identity.PublicUsers("Staff", "branch LAN")
        branch = shared.networking.EdgeRouter("Branch router", "SD-WAN edge")

    with equinix.Metro("Ashburn metro (DC)").column():
        with equinix.IBX("IBX DC2").column():
            with equinix.Cage("Cage 0412").row():
                with equinix.Cabinet("Cabinet A01").column():
                    array = storage.ObjectStoreService("Storage array", "customer-owned")
                    app = compute.AppService("App servers", "customer-owned")
                port = networking.FabricPort("Fabric port", "10 Gbps")
            exchange = networking.InternetExchange("Internet Exchange", "public peering")
        sdwan = networking.NetworkEdgeSDWAN("Network Edge SD-WAN", "virtual device")

    with equinix.Fabric("Equinix Fabric"):
        router = networking.FabricCloudRouter("Fabric Cloud Router", "BGP · layer 3")

    with generic.Cloud("Public clouds").column():
        with aws.Cloud("AWS").row():
            dx = aws_net.DirectConnectGateway("Direct Connect gateway", "private VIF")
            ec2 = aws_compute.EC2("Workloads", "VPC us-east-1")
        with azure.Region("Azure East US").row():
            er = azure_net.ExpressrouteCircuits("ExpressRoute circuit", "Standard · 1 Gbps")
            vm = azure_compute.VirtualMachine("Workloads", "hub VNet")
        with gcp.Project("Google Cloud").row():
            pi = gcp_net.PartnerInterconnect("Partner Interconnect", "VLAN attachment")
            gce = gcp_core.ComputeEngine("Workloads", "us-east4")

    staff >> Edge("LAN") >> branch
    branch >> Edge("SD-WAN tunnel") >> sdwan
    app >> Edge("iSCSI") >> array
    app >> Edge("cross connect") >> port
    app >> Edge("peering") >> exchange
    port >> Edge("virtual connection") >> router
    sdwan >> Edge("device link") >> router
    router >> Edge("VC · AWS") >> dx
    router >> Edge("VC · Azure") >> er
    router >> Edge("VC · Google") >> pi
    dx >> Edge("private") >> ec2
    er >> Edge("private peering") >> vm
    pi >> Edge("private") >> gce


if __name__ == "__main__":
    print(diagram.export(Path("dist"), formats=("template", "html", "svg", "png")).html)
