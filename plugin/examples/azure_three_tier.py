"""Three-tier web application on Azure, written as it would be described.

The Azure counterpart of ``aws_three_tier.py`` and ``gcp_three_tier.py``: the
same application drawn the way each cloud recommends building it. Here an
Application Gateway with WAF v2 takes the traffic in its own subnet, a Linux
scale set serves it from the application subnet, Azure SQL Database is
reached over a private endpoint, and Azure Bastion is the only way in for an
operator.

Frames are ``with`` blocks and whatever is written inside one belongs to it;
an arrow between two nodes is a wire. Frames come from
``infragram.nodes.frames.azure``, services from ``infragram.nodes.azure``, the
users from the shared library, and the document is inferred: components,
providers, kind and placement.

Through the skill's launcher, from the plugin folder::

    python skills/infragram-architect/scripts/infragram.py compose examples/azure_three_tier.py \
        --formats template,html,svg,png,terraform --output-dir dist
"""

from __future__ import annotations

from pathlib import Path

from infragram.author import Diagram, Edge
from infragram.nodes import infragram as shared
from infragram.nodes.azure import (
    compute,
    databases,
    monitor,
    networking as net,
    other,
    security,
    storage,
)
from infragram.nodes.frames import azure

with Diagram(
    "Three-tier web application on Azure",
    "Users reach an Application Gateway with WAF v2 in its own subnet; a Linux "
    "virtual machine scale set serves the application from the app subnet and "
    "reaches Azure SQL Database over a private endpoint in the data subnet, and "
    "Azure Bastion is the only way in for an operator. Assets live in a "
    "zone-redundant storage account, secrets in Key Vault, and Log Analytics "
    "collects the diagnostics.",
    slug="azure-three-tier-composed",
) as diagram:
    users = shared.identity.PublicUsers("Users", "browsers and apps")

    with azure.Subscription("Production subscription"), azure.Region("East US 2"):
        with azure.ResourceGroup("rg-web-prod").column().keep_order():
            with azure.VNet("VNet 10.10.0.0/16").row().keep_order():
                # The gateway beside the servers it balances, the private
                # endpoint beside the database it fronts.
                with azure.Subnet("snet-gateway 10.10.1.0/24"):
                    gateway = net.ApplicationGateways("Application Gateway", "WAF v2 - HTTPS :443")
                with azure.Subnet("snet-app 10.10.2.0/24"):
                    # what the export writes the scale set as
                    web = compute.VMScaleSets("Web servers", "3 x Standard_D2s_v5").sizing(
                        sku="Standard_D2s_v5", instances=3
                    )
                with azure.Subnet("snet-data 10.10.3.0/24"):
                    endpoint = other.PrivateEndpoints("Private endpoint", "Azure SQL - private DNS")
                with azure.Subnet("AzureBastionSubnet 10.10.4.0/26"):
                    bastion = net.Bastions("Azure Bastion", "operator SSH")

        with azure.ResourceGroup("rg-data-prod").row().keep_order():
            sql = databases.SQLDatabase("Azure SQL Database", "General Purpose - zone redundant")
            blobs = storage.StorageAccounts("Assets", "static content - ZRS")
            vault = security.KeyVaults("Key Vault", "database credentials")
            logs = monitor.LogAnalyticsWorkspacesMonitor("Log Analytics", "metrics - logs - alerts")

    users >> Edge("HTTPS") >> gateway
    gateway >> Edge("HTTP :8080") >> web
    web >> Edge("SQL") >> endpoint
    endpoint >> Edge("TDS 1433", dotted=True) >> sql
    bastion >> Edge("SSH", dashed=True) >> web
    web >> Edge("objects", dashed=True) >> blobs
    web >> Edge("credentials", dotted=True) >> vault
    web >> Edge("telemetry", dotted=True) >> logs


if __name__ == "__main__":
    print(diagram.export(Path("dist"), formats=("template", "html", "svg", "png")).html)
