"""Three-tier web application on Google Cloud, written as it would be described.

The Google Cloud counterpart of ``aws_three_tier.py`` and
``azure_three_tier.py``: the same application drawn the way each cloud
recommends building it. Here a global external Application Load Balancer
behind Cloud Armor takes the traffic, a managed instance group serves it from
a private subnet with Cloud NAT for its way out, and Cloud SQL for PostgreSQL
answers on a private IP.

Frames are ``with`` blocks and whatever is written inside one belongs to it;
an arrow between two nodes is a wire. Frames come from
``infragram.nodes.frames.gcp``, services from ``infragram.nodes.gcp``, the
users from the shared library, and the document is inferred: components,
providers, kind and placement.

Through the skill's launcher, from the plugin folder::

    python skills/infragram-architect/scripts/infragram.py compose examples/gcp_three_tier.py \
        --formats template,html,svg,png,terraform --output-dir dist
"""

from __future__ import annotations

from pathlib import Path

from infragram.author import Diagram, Edge
from infragram.nodes import Group, infragram as shared
from infragram.nodes.frames import gcp
from infragram.nodes.gcp import core_products as core, legacy

with Diagram(
    "Three-tier web application on Google Cloud",
    "Users reach a global external Application Load Balancer behind Cloud Armor; "
    "a managed instance group serves the application from a private subnet, "
    "leaves through Cloud NAT, and talks to Cloud SQL for PostgreSQL on a private "
    "IP. Assets live in Cloud Storage, secrets in Secret Manager, and Cloud "
    "Monitoring watches the project.",
    slug="gcp-three-tier-composed",
) as diagram:
    users = shared.identity.PublicUsers("Users", "browsers and apps")

    with gcp.Project("web-prod"), gcp.Region("us-central1"):
        # The global edge beside the network, Cloud Armor over the balancer,
        # so the balancer's wire runs straight across onto the servers.
        with Group("Global edge").column():
            armor = legacy.CloudArmor("Cloud Armor", "WAF - managed rules")
            balancer = legacy.CloudLoadBalancing("Application Load Balancer", "global - HTTPS :443")

        with gcp.VPC("VPC web-prod").column():
            with gcp.Subnet("snet-app 10.10.0.0/20").row():
                # what the export writes the servers as
                web = core.ComputeEngine("Web servers", "3 x e2-standard-2").sizing(
                    machine_type="e2-standard-2", count=3
                )
                nat = legacy.CloudNAT("Cloud NAT", "egress for private VMs")
            db = core.CloudSQL("PostgreSQL", "Cloud SQL - HA - private IP")

        bucket = core.CloudStorage("Assets", "static content - versioned")
        secrets = legacy.SecretManager("Secret Manager", "database credentials")
        watch = legacy.CloudMonitoring("Cloud Monitoring", "metrics - logs - alerts")

    users >> Edge("HTTPS") >> balancer
    armor >> Edge("inspects", dotted=True) >> balancer
    balancer >> Edge("HTTP :8080") >> web
    web >> Edge("egress", dashed=True) >> nat
    web >> Edge("SQL") >> db
    web >> Edge("objects", dashed=True) >> bucket
    web >> Edge("credentials", dotted=True) >> secrets
    web >> Edge("telemetry", dotted=True) >> watch


if __name__ == "__main__":
    print(diagram.export(Path("dist"), formats=("template", "html", "svg", "png")).html)
