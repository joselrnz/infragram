"""An active-active estate across four clouds, written as it would be described.

Cloudflare owns the edge and steers traffic; AWS carries the primary region
and Azure the secondary, each serving the same application from its own
managed Kubernetes; GCP takes the analytics. The point of the drawing is the
seams -- where one provider hands to the next -- so those wires carry the
protocol, and the replication between the two databases is what makes the
pair active-active rather than a cold standby.

This is the multicloud path through the renderer: four provider libraries in
one document, so the workspace is branded multicloud rather than as whichever
library happened to be first.

Through the skill's launcher, from the plugin folder::

    python skills/infragram-architect/scripts/infragram.py compose examples/multicloud_resilient_edge.py \
        --formats template,html,svg,png --output-dir dist
"""

from __future__ import annotations

from pathlib import Path

from infragram.author import Diagram, Edge
from infragram.nodes import infragram as shared
from infragram.nodes.aws import containers as aws_containers, databases as aws_db
from infragram.nodes.azure import compute as azure_compute, databases as azure_db
from infragram.nodes.cloudflare import networking as cf_net, security as cf_security
from infragram.nodes.frames import aws, azure, cloudflare, gcp
from infragram.nodes.gcp import core_products as gcp_core, legacy as gcp_legacy

with Diagram(
    "Active-active estate across four clouds",
    "Cloudflare terminates TLS at the edge, shields the origins with WAF and bot "
    "management, and load-balances between two regions. AWS us-east-1 runs the "
    "primary EKS cluster against an Aurora writer; Azure West Europe runs the "
    "secondary AKS cluster against a geo-replicated SQL database. Both regions "
    "stream their events to BigQuery, where Looker reads the estate as one.",
    slug="multicloud-resilient-edge",
) as diagram:
    users = shared.identity.PublicUsers("Users", "worldwide")

    with cloudflare.Account("Cloudflare"), cloudflare.Zone("example.com"):
        with cloudflare.Network("Edge").column():
            waf = cf_security.WAF("WAF", "managed rulesets")
            bots = cf_security.BotManagement("Bot Management", "scores every request")
            steering = cf_net.LoadBalancing("Load Balancing", "geo-steered, health-checked")

    with aws.Cloud("AWS"), aws.Region("us-east-1"):
        with aws.VPC("VPC 10.10.0.0/16").row():
            primary = aws_containers.ElasticKubernetesService("EKS", "primary - 6 nodes")
            writer = aws_db.Aurora("Aurora", "writer - PostgreSQL")

    with azure.Tenant("Azure"), azure.Region("West Europe"):
        with azure.VNet("VNet 10.20.0.0/16").row():
            secondary = azure_compute.KubernetesServices("AKS", "secondary - 6 nodes")
            replica = azure_db.AzureSQL("Azure SQL", "geo-replica - read scale")

    with gcp.Organization("Google Cloud"), gcp.Project("estate-analytics"):
        with gcp.Region("us-central1").row():
            events = gcp_legacy.Pubsub("Pub/Sub", "estate events")
            warehouse = gcp_core.Bigquery("BigQuery", "unified event tables")
            looker = gcp_core.Looker("Looker", "one view of four clouds")

    users >> Edge("HTTPS") >> steering
    waf >> Edge("inspects", dotted=True) >> steering
    bots >> Edge("scores", dotted=True) >> steering
    steering >> Edge("origin - primary") >> primary
    steering >> Edge("origin - failover", dashed=True) >> secondary
    primary >> Edge("SQL") >> writer
    secondary >> Edge("SQL") >> replica
    writer >> Edge("replicates", dashed=True) >> replica
    primary >> Edge("events") >> events
    secondary >> Edge("events") >> events
    events >> Edge("load") >> warehouse
    warehouse >> Edge("query") >> looker


if __name__ == "__main__":
    print(diagram.export(Path("dist"), formats=("template", "html", "svg", "png")).html)
